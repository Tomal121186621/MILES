package de.umd.matsim;

import ch.sbb.matsim.routing.pt.raptor.DefaultRaptorIntermodalAccessEgress;
import ch.sbb.matsim.routing.pt.raptor.RaptorIntermodalAccessEgress;
import ch.sbb.matsim.routing.pt.raptor.RaptorParameters;
import ch.sbb.matsim.routing.pt.raptor.RaptorStopFinder;
import org.matsim.api.core.v01.Id;
import org.matsim.api.core.v01.TransportMode;
import org.matsim.api.core.v01.network.Link;
import org.matsim.api.core.v01.population.*;

import java.util.List;

/**
 * Park-and-ride tour rule (as the car_pt / pt_car modes of the eqasim Paris study): car access only from home, car egress only to
 * home. A car access leg that does not start at the person's home link, or a car egress leg that does not end there, gets a
 * prohibitive disutility, so the SwissRailRaptor falls back to walk for that end of the trip. Everything else is the default cost.
 */
public class HomeCarAccessEgress implements RaptorIntermodalAccessEgress {
    private static final double PROHIBITIVE = 1.0e6;
    private final DefaultRaptorIntermodalAccessEgress delegate = new DefaultRaptorIntermodalAccessEgress();

    @Override
    public RIntermodalAccessEgress calcIntermodalAccessEgress(List<? extends PlanElement> legs, RaptorParameters params, Person person,
                                                             RaptorStopFinder.Direction direction) {
        RIntermodalAccessEgress r = delegate.calcIntermodalAccessEgress(legs, params, person, direction);
        Id<Link> home = homeLink(person);
        if (home == null) return r;
        for (PlanElement pe : legs) {
            if (!(pe instanceof Leg leg) || !TransportMode.car.equals(leg.getMode()) || leg.getRoute() == null) continue;
            Id<Link> end = direction == RaptorStopFinder.Direction.ACCESS ? leg.getRoute().getStartLinkId() : leg.getRoute().getEndLinkId();
            if (!home.equals(end)) return new RIntermodalAccessEgress(r.routeParts, r.disutility + PROHIBITIVE, r.travelTime, r.direction);
        }
        return r;
    }

    private static Id<Link> homeLink(Person person) {
        Plan plan = person.getSelectedPlan();
        if (plan == null) return null;
        for (PlanElement pe : plan.getPlanElements())
            if (pe instanceof Activity a && a.getType().startsWith("home") && a.getLinkId() != null) return a.getLinkId();
        return null;
    }
}
