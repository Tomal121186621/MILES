package de.umd.matsim;

import ch.sbb.matsim.routing.pt.raptor.RaptorInVehicleCostCalculator;
import ch.sbb.matsim.routing.pt.raptor.RaptorParametersForPerson;
import ch.sbb.matsim.routing.pt.raptor.RaptorRouteSelector;
import ch.sbb.matsim.routing.pt.raptor.RaptorStaticConfig;
import ch.sbb.matsim.routing.pt.raptor.RaptorStopFinder;
import ch.sbb.matsim.routing.pt.raptor.RaptorTransferCostCalculator;
import ch.sbb.matsim.routing.pt.raptor.RaptorUtils;
import ch.sbb.matsim.routing.pt.raptor.SwissRailRaptor;
import ch.sbb.matsim.routing.pt.raptor.SwissRailRaptorData;
import ch.sbb.matsim.routing.pt.raptor.SwissRailRaptorRoutingModule;
import com.google.inject.name.Named;
import jakarta.inject.Inject;
import jakarta.inject.Provider;
import org.matsim.api.core.v01.Id;
import org.matsim.api.core.v01.Scenario;
import org.matsim.api.core.v01.population.Person;
import org.matsim.api.core.v01.population.PlanElement;
import org.matsim.core.config.Config;
import org.matsim.core.router.RoutingModule;
import org.matsim.core.router.RoutingRequest;
import org.matsim.pt.transitSchedule.TransitScheduleFactoryImpl;
import org.matsim.pt.transitSchedule.api.MinimalTransferTimes;
import org.matsim.pt.transitSchedule.api.TransitLine;
import org.matsim.pt.transitSchedule.api.TransitRoute;
import org.matsim.pt.transitSchedule.api.TransitRouteStop;
import org.matsim.pt.transitSchedule.api.TransitSchedule;
import org.matsim.pt.transitSchedule.api.TransitStopFacility;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * 2026-11-17 (-Dpt.submodes=true): routing of MAST's bus trips (leg mode bus) on the bus routes of the schedule only (transport
 * mode bus: MTA local, LocalLink, commuter coaches and the other bus operators), with walk access and egress only, as MAST's bus
 * alternative was defined (bus-only schedule skims of 3_abit/mode_choice, walk access).  Train trips (leg mode train) are routed on
 * the full schedule with car access to rail (RailOnlyCarAccessRouting), as its train alternative.  The legs of both are pt and walk
 * legs as for mode pt (simulated, scored and counted alike); the routing mode (bus / train) keeps the trip on its sub-mode in
 * re-routing.  Before, every transit leg was mode pt and the router chose rail or bus freely.
 */
public class BusOnlyRouting implements RoutingModule {
    private final RoutingModule delegate;

    BusOnlyRouting(RoutingModule delegate) { this.delegate = delegate; }

    @Override
    public List<? extends PlanElement> calcRoute(RoutingRequest request) {
        Person p = request.getPerson();
        if (p == null) return delegate.calcRoute(request);
        Object old = p.getAttributes().getAttribute("ptCarAccess");   // walk access only (the intermodal car access is filtered by this attribute)
        p.getAttributes().putAttribute("ptCarAccess", "false");
        try { return delegate.calcRoute(request); }
        finally { if (old == null) p.getAttributes().removeAttribute("ptCarAccess"); else p.getAttributes().putAttribute("ptCarAccess", old); }
    }

    private static final java.util.Map<String, SwissRailRaptorData> DATA = new java.util.HashMap<>();

    /** raptor data of the bus routes, built once (shared by the router threads, as SwissRailRaptorData is) */
    static SwissRailRaptorData busData(Scenario sc, Config config) { return data(sc, config, Set.of("bus")); }

    /** raptor data of the routes whose transport mode is in modes, built once per mode set */
    static synchronized SwissRailRaptorData data(Scenario sc, Config config, Set<String> modes) {
        String key = String.join(",", new java.util.TreeSet<>(modes));
        if (DATA.containsKey(key)) return DATA.get(key);
        TransitSchedule full = sc.getTransitSchedule();
        TransitSchedule bus = new TransitScheduleFactoryImpl().createTransitSchedule();
        Set<Id<TransitStopFacility>> used = new HashSet<>(); int nRoutes = 0;
        for (TransitLine l : full.getTransitLines().values()) {
            TransitLine nl = null;
            for (TransitRoute r : l.getRoutes().values()) {
                if (!modes.contains(r.getTransportMode())) continue;
                if (nl == null) nl = bus.getFactory().createTransitLine(l.getId());
                nl.addRoute(r); nRoutes++;
                for (TransitRouteStop rs : r.getStops()) used.add(rs.getStopFacility().getId());
            }
            if (nl != null) bus.addTransitLine(nl);
        }
        for (Id<TransitStopFacility> id : used) bus.addStopFacility(full.getFacilities().get(id));
        MinimalTransferTimes.MinimalTransferTimesIterator it = full.getMinimalTransferTimes().iterator();
        while (it.hasNext()) {
            it.next();
            if (used.contains(it.getFromStopId()) && used.contains(it.getToStopId())) bus.getMinimalTransferTimes().set(it.getFromStopId(), it.getToStopId(), it.getSeconds());
        }
        RaptorStaticConfig sconf = RaptorUtils.createStaticConfig(config);
        SwissRailRaptorData d = SwissRailRaptorData.create(bus, sc.getTransitVehicles(), sconf, sc.getNetwork(), null);
        System.out.println("[BusOnlyRouting] raptor data of " + key + ": " + bus.getTransitLines().size() + " lines, " + nRoutes + " routes, " + used.size() + " stops");
        DATA.put(key, d); return d;
    }

    public static class RoutingProvider implements Provider<RoutingModule> {
        @Inject Scenario scenario;
        @Inject Config config;
        @Inject @Named("walk") RoutingModule walkRouter;
        @Inject RaptorParametersForPerson parametersForPerson;
        @Inject RaptorRouteSelector routeSelector;
        @Inject RaptorStopFinder stopFinder;
        @Inject RaptorInVehicleCostCalculator inVehicleCostCalculator;
        @Inject RaptorTransferCostCalculator transferCostCalculator;

        @Override
        public RoutingModule get() {
            SwissRailRaptor raptor = new SwissRailRaptor(busData(scenario, config), parametersForPerson, routeSelector, stopFinder,
                    inVehicleCostCalculator, transferCostCalculator);
            return new BusOnlyRouting(new SwissRailRaptorRoutingModule(raptor, scenario.getTransitSchedule(), scenario.getNetwork(), walkRouter));
        }
    }
}
