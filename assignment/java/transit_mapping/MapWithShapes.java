package de.umd.transit;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.matsim.api.core.v01.Coord;
import org.matsim.api.core.v01.Id;
import org.matsim.api.core.v01.TransportMode;
import org.matsim.api.core.v01.network.*;
import org.matsim.api.core.v01.population.Person;
import org.matsim.core.network.NetworkUtils;
import org.matsim.core.router.speedy.SpeedyALTFactory;
import org.matsim.core.router.util.LeastCostPathCalculator;
import org.matsim.core.router.util.TravelDisutility;
import org.matsim.core.router.util.TravelTime;
import org.matsim.core.utils.collections.QuadTree;
import org.matsim.core.utils.geometry.CoordUtils;
import org.matsim.pt.transitSchedule.api.*;
import org.matsim.pt2matsim.config.PublicTransitMappingConfigGroup;
import org.matsim.pt2matsim.mapping.PTMapper;
import org.matsim.pt2matsim.mapping.linkCandidateCreation.LinkCandidate;
import org.matsim.pt2matsim.mapping.networkRouter.ScheduleRouters;
import org.matsim.pt2matsim.mapping.networkRouter.ScheduleRoutersFactory;
import org.matsim.pt2matsim.mapping.networkRouter.ScheduleRoutersStandard;
import org.matsim.pt2matsim.tools.*;
import org.matsim.pt2matsim.tools.lib.RouteShape;
import org.matsim.vehicles.Vehicle;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * pt2matsim PublicTransitMapper with GTFS-shape-guided routing (TRANSIT_BUILD.md, step 3).
 * Same algorithm as org.matsim.pt2matsim.run.PublicTransitMapper (PTMapper: link candidates per stop, pseudo-routing between the
 * candidates of consecutive stops, artificial links where no path is cheap enough), with one change in the network router: a transit
 * route that has a GTFS shape is routed on the links of its schedule mode within CUT_BUFFER metres of the shape, and the cost of a
 * link is its travel cost (linkLength or travelTime, as configured) times (d / MAX_WEIGHT_DISTANCE + 0.1), set to 3 when that factor
 * exceeds 1, where d is the link's distance from the shape (the weighting of pt2matsim's ScheduleRoutersGtfsShapes).  The shape thus
 * decides between parallel streets, directions and loops, which the stop positions alone cannot.  Routes without a shape use
 * pt2matsim's standard router (ScheduleRoutersStandard) on the whole mode network.
 * Differences to ScheduleRoutersGtfsShapes: the corridor network of a shape is built once and shared by all mapper threads (that class
 * filters the full network and scans all its nodes per shape and per thread), nodes are found with a quadtree along the densified
 * shape, link costs are precomputed, and the corridor router is a Dijkstra on local indices (thread-safe: no shared state).
 * Usage: MapWithShapes ptmapper_config.xml shapes.txt EPSG cutBuffer maxWeightDistance
 */
public class MapWithShapes {
    static final Logger log = LogManager.getLogger(MapWithShapes.class);

    /** corridor graph and router of one (shape, schedule mode): a plain Dijkstra on local indices (MATSim's SpeedyALT sizes its arrays
     *  by the global number of node and link ids, about 100 MB per router on this network, which rules out one router per shape) */
    static final class Corridor {
        final Map<Id<Node>, Integer> idx = new HashMap<>(); final List<Node> nodes = new ArrayList<>(); final Map<Id<Link>, Double> cost = new HashMap<>();
        int[][] outTo; double[][] outCost; Link[][] outLink; int nLinks;
        Corridor(Collection<Node> ns, List<Link> ls, Map<Id<Link>, Double> c) {
            for (Node n : ns) { idx.put(n.getId(), nodes.size()); nodes.add(n); }
            List<List<Link>> out = new ArrayList<>(); for (int i = 0; i < nodes.size(); i++) out.add(new ArrayList<>());
            for (Link l : ls) out.get(idx.get(l.getFromNode().getId())).add(l);
            int n = nodes.size(); outTo = new int[n][]; outCost = new double[n][]; outLink = new Link[n][];
            for (int i = 0; i < n; i++) { List<Link> o = out.get(i); outTo[i] = new int[o.size()]; outCost[i] = new double[o.size()]; outLink[i] = new Link[o.size()];
                for (int k = 0; k < o.size(); k++) { Link l = o.get(k); outTo[i][k] = idx.get(l.getToNode().getId()); outCost[i][k] = c.get(l.getId()); outLink[i][k] = l; } }
            cost.putAll(c); nLinks = ls.size();
        }
        LeastCostPathCalculator.Path path(Id<Node> f, Id<Node> t) {
            Integer a = idx.get(f), b = idx.get(t); if (a == null || b == null) return null;
            int n = nodes.size(); double[] dist = new double[n]; Arrays.fill(dist, Double.POSITIVE_INFINITY); int[] prevNode = new int[n]; Link[] prevLink = new Link[n];
            PriorityQueue<double[]> pq = new PriorityQueue<>(Comparator.comparingDouble(x -> x[0])); dist[a] = 0; pq.add(new double[]{0, a});
            while (!pq.isEmpty()) {
                double[] top = pq.poll(); int u = (int) top[1]; if (top[0] > dist[u]) continue; if (u == b) break;
                for (int k = 0; k < outTo[u].length; k++) { int v = outTo[u][k]; double nd = dist[u] + outCost[u][k]; if (nd < dist[v]) { dist[v] = nd; prevNode[v] = u; prevLink[v] = outLink[u][k]; pq.add(new double[]{nd, v}); } }
            }
            if (!Double.isFinite(dist[b])) return null;
            LinkedList<Node> pn = new LinkedList<>(); LinkedList<Link> pl = new LinkedList<>(); double tt = 0; int v = b; pn.addFirst(nodes.get(v));
            while (v != a) { Link l = prevLink[v]; pl.addFirst(l); tt += l.getLength() / l.getFreespeed(); v = prevNode[v]; pn.addFirst(nodes.get(v)); }
            return new LeastCostPathCalculator.Path(new ArrayList<>(pn), new ArrayList<>(pl), tt, dist[b]);
        }
    }

    static final class Shared {
        final Map<TransitRoute, Corridor> byRoute = new ConcurrentHashMap<>();
        final AtomicInteger noShape = new AtomicInteger(), withShape = new AtomicInteger();
    }

    static double minDist(Coord c, List<Coord> pts) {
        double best = Double.POSITIVE_INFINITY;
        for (int i = 0; i + 1 < pts.size(); i++) best = Math.min(best, CoordUtils.distancePointLinesegment(pts.get(i), pts.get(i + 1), c));
        return pts.size() == 1 ? CoordUtils.calcEuclideanDistance(c, pts.get(0)) : best;
    }

    static Shared build(TransitSchedule schedule, Network network, Map<Id<RouteShape>, RouteShape> shapes, Map<String, Set<String>> assignment,
                        PublicTransitMappingConfigGroup.TravelCostType costType, double cutBuffer, double maxWeightDistance) {
        Shared sh = new Shared();
        Map<String, Network> modeNet = new HashMap<>(); Map<String, QuadTree<Node>> modeQT = new HashMap<>();
        for (Map.Entry<String, Set<String>> e : assignment.entrySet()) {
            if (e.getValue() == null || e.getValue().isEmpty()) continue;
            Network n = NetworkTools.createFilteredNetworkByLinkMode(network, e.getValue()); if (n.getNodes().isEmpty()) continue;
            double[] bb = NetworkUtils.getBoundingBox(n.getNodes().values());
            QuadTree<Node> qt = new QuadTree<>(bb[0], bb[1], bb[2], bb[3]); for (Node nd : n.getNodes().values()) qt.put(nd.getCoord().getX(), nd.getCoord().getY(), nd);
            modeNet.put(e.getKey(), n); modeQT.put(e.getKey(), qt);
            log.info("mode network for schedule mode " + e.getKey() + " (" + e.getValue() + "): " + n.getNodes().size() + " nodes, " + n.getLinks().size() + " links");
        }
        // one corridor per (shape, mode)
        Map<String, List<TransitRoute>> groups = new HashMap<>();
        for (TransitLine tl : schedule.getTransitLines().values()) for (TransitRoute tr : tl.getRoutes().values()) {
            Id<RouteShape> sid = ScheduleTools.getShapeId(tr);
            if (sid == null || !shapes.containsKey(sid) || !modeNet.containsKey(tr.getTransportMode())) { sh.noShape.incrementAndGet(); continue; }
            sh.withShape.incrementAndGet(); groups.computeIfAbsent(sid + "|" + tr.getTransportMode(), k -> new ArrayList<>()).add(tr);
        }
        log.info("routes with a shape: " + sh.withShape + " (" + groups.size() + " corridors), without: " + sh.noShape);
        AtomicInteger done = new AtomicInteger(); long t0 = System.currentTimeMillis();
        (Boolean.getBoolean("corridors.parallel") ? groups.entrySet().parallelStream() : groups.entrySet().stream()).forEach(g -> {
            String[] k = g.getKey().split("\\|"); String mode = k[1]; RouteShape shape = shapes.get(Id.create(k[0], RouteShape.class));
            Network mn = modeNet.get(mode); QuadTree<Node> qt = modeQT.get(mode);
            List<Coord> pts = new ArrayList<>(shape.getCoords()); Set<Node> nodes0 = new HashSet<>();
            for (int i = 0; i < pts.size(); i++) {
                Coord a = pts.get(i); nodes0.addAll(qt.getDisk(a.getX(), a.getY(), cutBuffer));
                if (i + 1 < pts.size()) {
                    Coord b = pts.get(i + 1); double L = CoordUtils.calcEuclideanDistance(a, b); int n = (int) Math.ceil(L / cutBuffer);
                    for (int j = 1; j < n; j++) { double f = (double) j / n; nodes0.addAll(qt.getDisk(a.getX() + f * (b.getX() - a.getX()), a.getY() + f * (b.getY() - a.getY()), cutBuffer)); }
                }
            }
            // one-hop expansion: the far node of every link that leaves or enters the buffer (long links, e.g. freeway segments, whose nodes lie outside it)
            Set<Node> ext = new HashSet<>(nodes0); for (Node nd : nodes0) { for (Link l : nd.getOutLinks().values()) ext.add(l.getToNode()); for (Link l : nd.getInLinks().values()) ext.add(l.getFromNode()); }
            Set<Node> nodes = ext;
            Map<Id<Link>, Double> cost = new HashMap<>(); List<Link> ls = new ArrayList<>(); Set<Id<Node>> nid = new HashSet<>(); for (Node nd : nodes) nid.add(nd.getId());
            for (Node nd : nodes) for (Link l : nd.getOutLinks().values()) {
                if (!nid.contains(l.getToNode().getId())) continue;
                ls.add(l);
                double d = Math.max(minDist(l.getFromNode().getCoord(), pts), minDist(l.getToNode().getCoord(), pts));
                double factor = d / maxWeightDistance + 0.1; if (factor > 1) factor = 3;
                cost.put(l.getId(), PTMapperTools.calcTravelCost(l, costType) * factor);
            }
            // deterministic order (HashSet order depends on identity hashes; equal-cost ties would otherwise be broken differently from run to run)
            List<Node> sortedNodes = new ArrayList<>(nodes); sortedNodes.sort(Comparator.comparing(nd -> nd.getId().toString())); ls.sort(Comparator.comparing(l -> l.getId().toString()));
            Corridor cor = new Corridor(sortedNodes, ls, cost);
            for (TransitRoute tr : g.getValue()) sh.byRoute.put(tr, cor);
            int dn = done.incrementAndGet(); if (dn % 20 == 0) { Runtime rt = Runtime.getRuntime(); log.info("corridors built: " + dn + "/" + groups.size() + " after " + (System.currentTimeMillis() - t0) / 1000 + " s; last " + g.getKey() + ": " + cor.nodes.size() + " nodes, " + cor.nLinks + " links, " + pts.size() + " shape points; heap used " + (rt.totalMemory() - rt.freeMemory()) / (1 << 20) + " MB"); }
        });
        log.info("corridors built: " + groups.size() + " in " + (System.currentTimeMillis() - t0) / 1000 + " s");
        return sh;
    }

    /** per mapper thread: corridor routing for routes with a shape, pt2matsim's standard router for the others (created on first use) */
    static final class HybridRouters implements ScheduleRouters {
        final Shared sh; final ScheduleRoutersStandard.Factory stdFactory; ScheduleRouters std; final PublicTransitMappingConfigGroup.TravelCostType costType; final boolean candDist;
        HybridRouters(Shared sh, ScheduleRoutersStandard.Factory f, PublicTransitMappingConfigGroup.TravelCostType costType, boolean candDist) { this.sh = sh; this.stdFactory = f; this.costType = costType; this.candDist = candDist; }
        ScheduleRouters std() { if (std == null) std = stdFactory.createInstance(); return std; }
        public LeastCostPathCalculator.Path calcLeastCostPath(LinkCandidate a, LinkCandidate b, TransitLine tl, TransitRoute tr) {
            return calcLeastCostPath(a.getLink().getToNode().getId(), b.getLink().getFromNode().getId(), tl, tr);
        }
        public LeastCostPathCalculator.Path calcLeastCostPath(Id<Node> f, Id<Node> t, TransitLine tl, TransitRoute tr) {
            Corridor c = sh.byRoute.get(tr); return c == null ? std().calcLeastCostPath(f, t, tl, tr) : c.path(f, t);
        }
        public double getMinimalTravelCost(TransitRouteStop a, TransitRouteStop b, TransitLine tl, TransitRoute tr) {
            double m = PTMapperTools.calcMinTravelCost(a, b, costType);
            if (m == 0) m = CoordUtils.calcEuclideanDistance(a.getStopFacility().getCoord(), b.getStopFacility().getCoord()) / 10;
            return m;
        }
        public double getLinkCandidateTravelCost(LinkCandidate lc) {
            Corridor c = sh.byRoute.get(lc.getStop().getTransitRoute());
            if (c == null) return std().getLinkCandidateTravelCost(lc);
            double dist = 0;
            if (candDist) dist = 2 * (costType == PublicTransitMappingConfigGroup.TravelCostType.travelTime ? lc.getStopFacilityDistance() / lc.getLink().getFreespeed() : lc.getStopFacilityDistance());
            Double k = c.cost.get(lc.getLink().getId());
            return dist + (k != null ? k : 3 * PTMapperTools.calcTravelCost(lc.getLink(), costType));
        }
    }

    public static void main(String[] args) {
        PublicTransitMappingConfigGroup config = PublicTransitMappingConfigGroup.loadConfig(args[0]);
        String shapesFile = args[1], crs = args[2]; double cutBuffer = Double.parseDouble(args[3]), maxW = Double.parseDouble(args[4]);
        TransitSchedule schedule = ScheduleTools.readTransitSchedule(config.getInputScheduleFile());
        Network network = NetworkTools.readNetwork(config.getInputNetworkFile());
        Map<Id<RouteShape>, RouteShape> shapes = ShapeTools.readShapesFile(shapesFile, crs);
        log.info("shapes read: " + shapes.size() + "; cut buffer " + cutBuffer + " m, max weight distance " + maxW + " m");
        Shared sh = build(schedule, network, shapes, config.getTransportModeAssignment(), config.getTravelCostType(), cutBuffer, maxW);
        ScheduleRoutersStandard.Factory std = new ScheduleRoutersStandard.Factory(schedule, network, config.getTransportModeAssignment(), config.getTravelCostType(), config.getRoutingWithCandidateDistance());
        ScheduleRoutersFactory f = () -> new HybridRouters(sh, std, config.getTravelCostType(), config.getRoutingWithCandidateDistance());
        PTMapper m = new PTMapper(schedule, network); m.run(config, null, f);
        ScheduleTools.writeTransitSchedule(m.getSchedule(), config.getOutputScheduleFile());
        NetworkTools.writeNetwork(network, config.getOutputNetworkFile());
        log.info("written " + config.getOutputScheduleFile() + " and " + config.getOutputNetworkFile());
    }
}
