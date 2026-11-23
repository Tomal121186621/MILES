package de.umd.matsim;

import ch.sbb.matsim.routing.pt.raptor.RaptorInVehicleCostCalculator;
import ch.sbb.matsim.routing.pt.raptor.RaptorParametersForPerson;
import ch.sbb.matsim.routing.pt.raptor.RaptorRouteSelector;
import ch.sbb.matsim.routing.pt.raptor.RaptorStopFinder;
import ch.sbb.matsim.routing.pt.raptor.RaptorTransferCostCalculator;
import ch.sbb.matsim.routing.pt.raptor.SwissRailRaptor;
import ch.sbb.matsim.routing.pt.raptor.SwissRailRaptorRoutingModule;
import com.google.inject.name.Named;
import jakarta.inject.Inject;
import jakarta.inject.Provider;
import org.matsim.api.core.v01.Scenario;
import org.matsim.api.core.v01.population.Leg;
import org.matsim.api.core.v01.population.PlanElement;
import org.matsim.core.config.Config;
import org.matsim.core.router.RoutingModule;
import org.matsim.core.router.RoutingRequest;
import org.matsim.pt.routes.TransitPassengerRoute;
import org.matsim.pt.transitSchedule.api.TransitLine;
import org.matsim.pt.transitSchedule.api.TransitRoute;
import org.matsim.pt.transitSchedule.api.TransitSchedule;

import java.util.List;

/**
 * 2026-11-17 (-Dpt.submodes=true): routing of DAYMAP's train trips (leg mode train).  DAYMAP's train alternative is a path that
 * rides rail (the full-schedule path when it uses rail, else the drive-access rail path; 3_abit/mode_choice/mc_common.py), so a
 * train trip is routed on the full schedule with car access to rail (RailOnlyCarAccessRouting) and, when that route rides no rail,
 * metro or light rail, again on the rail routes only (walk access, and car access for persons with ptCarAccess); the full-schedule
 * route is kept when no rail route exists.
 */
public class TrainRouting implements RoutingModule {
    private final RoutingModule full, railOnly; private final TransitSchedule schedule;

    TrainRouting(RoutingModule full, RoutingModule railOnly, TransitSchedule schedule) { this.full = full; this.railOnly = railOnly; this.schedule = schedule; }

    @Override
    public List<? extends PlanElement> calcRoute(RoutingRequest request) {
        List<? extends PlanElement> r = full.calcRoute(request);
        if (r == null || ridesRail(r)) return r;
        List<? extends PlanElement> r2 = railOnly.calcRoute(request);
        return r2 != null && ridesRail(r2) ? r2 : r;
    }

    private boolean ridesRail(List<? extends PlanElement> r) {
        for (PlanElement pe : r) {
            if (!(pe instanceof Leg l) || !(l.getRoute() instanceof TransitPassengerRoute tr)) continue;
            TransitLine line = schedule.getTransitLines().get(tr.getLineId());
            TransitRoute route = line == null ? null : line.getRoutes().get(tr.getRouteId());
            if (route != null && RailOnlyCarAccessRouting.RAIL.contains(route.getTransportMode())) return true;
        }
        return false;
    }

    public static class RoutingProvider implements Provider<RoutingModule> {
        @Inject SwissRailRaptor raptor;
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
            TransitSchedule s = scenario.getTransitSchedule();
            RoutingModule full = new RailOnlyCarAccessRouting(new SwissRailRaptorRoutingModule(raptor, s, scenario.getNetwork(), walkRouter), s);
            SwissRailRaptor rr = new SwissRailRaptor(BusOnlyRouting.data(scenario, config, RailOnlyCarAccessRouting.RAIL), parametersForPerson, routeSelector,
                    stopFinder, inVehicleCostCalculator, transferCostCalculator);
            return new TrainRouting(full, new SwissRailRaptorRoutingModule(rr, s, scenario.getNetwork(), walkRouter), s);
        }
    }
}
