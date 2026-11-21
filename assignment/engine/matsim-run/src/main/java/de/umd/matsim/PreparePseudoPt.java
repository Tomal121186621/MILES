package de.umd.matsim;

import org.matsim.api.core.v01.Coord;
import org.matsim.api.core.v01.Id;
import org.matsim.api.core.v01.Scenario;
import org.matsim.api.core.v01.TransportMode;
import org.matsim.api.core.v01.network.Link;
import org.matsim.api.core.v01.network.Network;
import org.matsim.api.core.v01.network.Node;
import org.matsim.core.config.ConfigUtils;
import org.matsim.core.network.NetworkUtils;
import org.matsim.core.network.algorithms.TransportModeNetworkFilter;
import org.matsim.core.network.io.MatsimNetworkReader;
import org.matsim.core.scenario.ScenarioUtils;
import org.matsim.pt.transitSchedule.api.*;
import org.matsim.pt.utils.CreatePseudoNetwork;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;

/**
 * Transit on its own links, following the Open Berlin scenario (matsim-application CreateTransitScheduleFromGtfs, 2024.0):
 *  1 the network keeps only its car links (modes reduced to car); the links of the mapped schedule are dropped;
 *  2 pt2matsim child stops ("parent.link:id") are merged into one stop per parent (Berlin: mergeToParent);
 *  3 CreatePseudoNetwork adds one "pt_" link between consecutive stops (capacity 100,000 veh/h);
 *  4 link free speeds are raised so that no service is late, with 30 s at every stop for boarding and alighting (Berlin's rule);
 *  5 stops listed in the park-and-ride file get parkAndRide = true and accessLinkId_car = the nearest car link, for the
 *    SwissRailRaptor intermodal car access (SBB: stopFilterAttribute / linkIdAttribute).
 * Usage: PreparePseudoPt network.xml.gz schedule.xml.gz park_ride_stops.csv networkOut.xml.gz scheduleOut.xml.gz
 */
public class PreparePseudoPt {

    public static void main(String[] args) throws Exception {
        Scenario sc = ScenarioUtils.createScenario(ConfigUtils.createConfig());
        new MatsimNetworkReader(sc.getNetwork()).readFile(args[0]);
        new TransitScheduleReader(sc).readFile(args[1]);
        Network net = sc.getNetwork();
        TransitSchedule sched = sc.getTransitSchedule();

        // 1 car links only
        List<Id<Link>> drop = new ArrayList<>();
        for (Link l : net.getLinks().values()) {
            if (!l.getAllowedModes().contains(TransportMode.car)) drop.add(l.getId());
            else l.setAllowedModes(Set.of(TransportMode.car));
        }
        drop.forEach(net::removeLink);
        List<Id<Node>> lonely = new ArrayList<>();
        for (Node n : net.getNodes().values()) if (n.getInLinks().isEmpty() && n.getOutLinks().isEmpty()) lonely.add(n.getId());
        lonely.forEach(net::removeNode);
        System.out.println("[PreparePseudoPt] removed " + drop.size() + " non-car links, " + lonely.size() + " isolated nodes");

        // 2 merge child stops into their parent
        Map<String, TransitStopFacility> parents = new LinkedHashMap<>();
        for (TransitStopFacility f : sched.getFacilities().values()) {
            String p = parentId(f.getId().toString());
            parents.computeIfAbsent(p, k -> {
                TransitStopFacility n = sched.getFactory().createTransitStopFacility(Id.create(k, TransitStopFacility.class), f.getCoord(), false);
                n.setName(f.getName());
                return n;
            });
        }
        for (TransitLine line : sched.getTransitLines().values())
            for (TransitRoute r : line.getRoutes().values())
                for (TransitRouteStop s : r.getStops()) s.setStopFacility(parents.get(parentId(s.getStopFacility().getId().toString())));
        // minimal transfer times: the pt2matsim relations join children of one parent (0 s) and become void; others move to the parents
        MinimalTransferTimes mtt = sched.getMinimalTransferTimes();
        List<String[]> rel = new ArrayList<>();
        for (MinimalTransferTimes.MinimalTransferTimesIterator it = mtt.iterator(); it.hasNext(); ) {
            it.next();
            rel.add(new String[]{it.getFromStopId().toString(), it.getToStopId().toString(), Double.toString(it.getSeconds())});
        }
        for (String[] r : rel) mtt.remove(Id.create(r[0], TransitStopFacility.class), Id.create(r[1], TransitStopFacility.class));
        int kept = 0;
        for (String[] r : rel) {
            String a = parentId(r[0]), b = parentId(r[1]);
            if (a.equals(b)) continue;
            mtt.set(Id.create(a, TransitStopFacility.class), Id.create(b, TransitStopFacility.class), Double.parseDouble(r[2])); kept++;
        }
        System.out.println("[PreparePseudoPt] minimal transfer times: " + rel.size() + " -> " + kept + " between different parents");
        int nChild = sched.getFacilities().size();
        new ArrayList<>(sched.getFacilities().values()).forEach(sched::removeStopFacility);
        parents.values().forEach(sched::addStopFacility);
        System.out.println("[PreparePseudoPt] stops: " + nChild + " -> " + parents.size() + " parents");

        // 2b spread identical times of consecutive stops (Berlin: AdjustSameDepartureTimes, matsim-application, copied): GTFS
        // non-timepoint stops carry the time of the preceding timepoint, which gives artefacts on a pseudo network
        int nAdj = 0;
        for (TransitLine line : sched.getTransitLines().values()) {
            for (TransitRoute route : new ArrayList<>(line.getRoutes().values())) {
                List<TransitRouteStop> ns = adjustSameTimes(sched.getFactory(), route);
                if (ns == null) continue;
                line.removeRoute(route);
                TransitRoute nr = sched.getFactory().createTransitRoute(route.getId(), route.getRoute(), ns, route.getTransportMode());
                nr.setDescription(route.getDescription());
                for (Map.Entry<String, Object> e : route.getAttributes().getAsMap().entrySet()) nr.getAttributes().putAttribute(e.getKey(), e.getValue());
                route.getDepartures().values().forEach(nr::addDeparture);
                line.addRoute(nr);
                nAdj++;
            }
        }
        System.out.println("[PreparePseudoPt] routes with identical consecutive stop times spread: " + nAdj);

        // 3 pseudo network (Berlin: linkFreeSpeed 0.1 m/s, capacity 100,000, then step 4)
        new CreatePseudoNetwork(sched, net, "pt_", 0.1, 100000.0).createNetwork();

        // 4 free speeds so that no service is delayed (copied from CreateTransitScheduleFromGtfs, MATSim 2024.0)
        for (TransitLine line : sched.getTransitLines().values()) {
            for (TransitRoute route : line.getRoutes().values()) {
                List<TransitRouteStop> st = route.getStops();
                if (st.size() < 2) continue;
                double lastDep = st.get(0).getDepartureOffset().seconds();
                double minStop = 30.0;
                LinkedList<Id<Link>> ids = new LinkedList<>();
                ids.add(route.getRoute().getStartLinkId()); ids.addAll(route.getRoute().getLinkIds()); ids.add(route.getRoute().getEndLinkId());
                for (int i = 1; i < st.size(); i++) {
                    TransitRouteStop rs = st.get(i);
                    double stopDur = rs.getDepartureOffset().isDefined() ? rs.getDepartureOffset().seconds() - rs.getArrivalOffset().seconds() : minStop;
                    double tt = Math.max(1, rs.getArrivalOffset().seconds() - lastDep - 1.0 - (stopDur >= minStop ? 0 : (minStop - stopDur)));
                    Id<Link> stopLink = rs.getStopFacility().getLinkId();
                    List<Id<Link>> sub = new ArrayList<>();
                    do { sub.add(ids.removeFirst()); } while (!sub.contains(stopLink));
                    double len = 0; for (Id<Link> id : sub) len += net.getLinks().get(id).getLength();
                    for (Id<Link> id : sub) { Link l = net.getLinks().get(id); if (l.getFreespeed() < len / tt) l.setFreespeed(len / tt); }
                    lastDep = rs.getDepartureOffset().isDefined() ? rs.getDepartureOffset().seconds() : rs.getArrivalOffset().seconds();
                }
            }
        }

        // 5 park-and-ride stops
        Set<String> pr = new HashSet<>();
        List<String> rows = Files.readAllLines(Paths.get(args[2]));
        for (String row : rows.subList(1, rows.size())) if (!row.isBlank()) pr.add(row.split(",", 2)[0].trim());
        Network car = NetworkUtils.createNetwork();
        new TransportModeNetworkFilter(net).filter(car, Set.of(TransportMode.car));
        int nPr = 0;
        for (TransitStopFacility f : sched.getFacilities().values()) {
            if (!pr.contains(copyBase(f.getId().toString()))) continue;
            Link l = NetworkUtils.getNearestLink(car, f.getCoord());
            f.getAttributes().putAttribute("parkAndRide", "true");
            f.getAttributes().putAttribute("accessLinkId_car", l.getId().toString());
            nPr++;
        }
        System.out.println("[PreparePseudoPt] park-and-ride stop facilities: " + nPr + " (parents listed " + pr.size() + ")");

        NetworkUtils.writeNetwork(net, args[3]);
        new TransitScheduleWriter(sched).writeFile(args[4]);
        System.out.println("[PreparePseudoPt] network links " + net.getLinks().size() + ", stop facilities " + sched.getFacilities().size());
    }

    private static org.matsim.core.utils.misc.OptionalTime add(org.matsim.core.utils.misc.OptionalTime x, double t) {
        return x.isDefined() ? org.matsim.core.utils.misc.OptionalTime.defined(x.seconds() + t) : x;
    }

    private static TransitRouteStop copy(TransitScheduleFactory f, TransitRouteStop s, double t) {
        TransitRouteStop n = f.createTransitRouteStop(s.getStopFacility(), add(s.getArrivalOffset(), t), add(s.getDepartureOffset(), t));
        n.setAwaitDepartureTime(s.isAwaitDepartureTime());
        return n;
    }

    /** AdjustSameDepartureTimes.adjustDepartures (matsim-application): last stop shifted at 10 m/s, inner runs spread evenly. */
    private static List<TransitRouteStop> adjustSameTimes(TransitScheduleFactory f, TransitRoute route) {
        List<TransitRouteStop> st = new ArrayList<>(route.getStops());
        boolean adj = false;
        if (st.size() > 1) {
            TransitRouteStop last = st.get(st.size() - 1), prev = st.get(st.size() - 2);
            var ld = last.getDepartureOffset().or(last.getArrivalOffset()); var pd = prev.getDepartureOffset().or(prev.getArrivalOffset());
            if (ld.isDefined() && pd.isDefined() && ld.equals(pd)) {
                double dist = Math.max(20, org.matsim.core.utils.geometry.CoordUtils.calcEuclideanDistance(last.getStopFacility().getCoord(), prev.getStopFacility().getCoord()));
                st.set(st.size() - 1, copy(f, last, dist / 10)); adj = true;
            }
        }
        for (int i = 0; i < st.size() - 1; ) {
            var dep = st.get(i).getDepartureOffset().or(st.get(i).getArrivalOffset());
            if (!dep.isDefined()) { i++; continue; }
            org.matsim.core.utils.misc.OptionalTime arr = null;
            int j = i + 1;
            for (; j < st.size(); j++) { arr = st.get(j).getArrivalOffset().or(st.get(j).getDepartureOffset()); if (!dep.equals(arr)) break; }
            if (arr == null) { i++; continue; }
            if (j > i + 1) {
                double diff = (arr.seconds() - dep.seconds()) / (j - i);
                for (int k = i + 1; k < j; k++) { st.set(k, copy(f, st.get(k), (int) (diff * (k - i)))); adj = true; }
            }
            i = j;
        }
        return adj ? st : null;
    }

    private static String parentId(String id) { int k = id.indexOf(".link:"); return k < 0 ? id : id.substring(0, k); }

    /** CreatePseudoNetwork names copies of a stop "<id>.<n>". */
    private static String copyBase(String id) { return id.matches(".*\\.\\d+$") ? id.substring(0, id.lastIndexOf('.')) : id; }
}
