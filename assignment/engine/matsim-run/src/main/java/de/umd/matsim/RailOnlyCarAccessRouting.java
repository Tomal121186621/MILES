package de.umd.matsim;

import ch.sbb.matsim.routing.pt.raptor.SwissRailRaptor;
import ch.sbb.matsim.routing.pt.raptor.SwissRailRaptorRoutingModule;
import com.google.inject.name.Named;
import jakarta.inject.Inject;
import jakarta.inject.Provider;
import org.matsim.api.core.v01.Scenario;
import org.matsim.api.core.v01.TransportMode;
import org.matsim.api.core.v01.population.Leg;
import org.matsim.api.core.v01.population.Person;
import org.matsim.api.core.v01.population.PlanElement;
import org.matsim.core.router.RoutingModule;
import org.matsim.core.router.RoutingRequest;
import org.matsim.pt.routes.TransitPassengerRoute;
import org.matsim.pt.transitSchedule.api.TransitLine;
import org.matsim.pt.transitSchedule.api.TransitRoute;
import org.matsim.pt.transitSchedule.api.TransitSchedule;

import java.util.List;
import java.util.Set;

/**
 * Car access to transit only for rail, as in DAYMAP (drive access belongs to its train alternative; its bus alternative is walk
 * access): a SwissRailRaptor route with a car leg but no ride on rail, metro or light rail (the router may drive to a station lot and
 * walk to a bus stop there) is routed again without car access for that trip.
 */
public class RailOnlyCarAccessRouting implements RoutingModule {
    static final Set<String> RAIL = Set.of("rail", "subway", "tram");
    private final RoutingModule delegate;
    private final TransitSchedule schedule;

    RailOnlyCarAccessRouting(RoutingModule delegate, TransitSchedule schedule) { this.delegate = delegate; this.schedule = schedule; }

    @Override
    public List<? extends PlanElement> calcRoute(RoutingRequest request) {
        List<? extends PlanElement> r = delegate.calcRoute(request);
        Person p = request.getPerson();
        if (p == null || r == null || !usesCar(r) || usesRail(r)) return r;
        Object old = p.getAttributes().getAttribute("ptCarAccess");
        p.getAttributes().putAttribute("ptCarAccess", "false");
        try { return delegate.calcRoute(request); }
        finally { if (old == null) p.getAttributes().removeAttribute("ptCarAccess"); else p.getAttributes().putAttribute("ptCarAccess", old); }
    }

    private static boolean usesCar(List<? extends PlanElement> r) {
        for (PlanElement pe : r) if (pe instanceof Leg l && TransportMode.car.equals(l.getMode())) return true;
        return false;
    }

    private boolean usesRail(List<? extends PlanElement> r) {
        for (PlanElement pe : r) {
            if (!(pe instanceof Leg l) || !(l.getRoute() instanceof TransitPassengerRoute tr)) continue;
            TransitLine line = schedule.getTransitLines().get(tr.getLineId());
            TransitRoute route = line == null ? null : line.getRoutes().get(tr.getRouteId());
            if (route != null && RAIL.contains(route.getTransportMode())) return true;
        }
        return false;
    }

    /** replaces the SwissRailRaptor routing module of mode pt (same construction as SwissRailRaptorRoutingModuleProvider) */
    public static class RoutingProvider implements Provider<RoutingModule> {
        @Inject SwissRailRaptor raptor;
        @Inject Scenario scenario;
        @Inject @Named("walk") RoutingModule walkRouter;

        @Override
        public RoutingModule get() {
            return new RailOnlyCarAccessRouting(new SwissRailRaptorRoutingModule(raptor, scenario.getTransitSchedule(), scenario.getNetwork(), walkRouter),
                    scenario.getTransitSchedule());
        }
    }
}
