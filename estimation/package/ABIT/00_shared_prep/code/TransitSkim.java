package de.umd.skim;

import ch.sbb.matsim.config.SwissRailRaptorConfigGroup;
import ch.sbb.matsim.routing.pt.raptor.*;
import ch.sbb.matsim.routing.pt.raptor.SwissRailRaptorCore.TravelInfo;
import org.matsim.api.core.v01.Coord;
import org.matsim.api.core.v01.Id;
import org.matsim.api.core.v01.Scenario;
import org.matsim.api.core.v01.network.Link;
import org.matsim.core.config.Config;
import org.matsim.core.config.ConfigUtils;
import org.matsim.core.config.groups.RoutingConfigGroup;
import org.matsim.core.network.io.MatsimNetworkReader;
import org.matsim.core.scenario.ScenarioUtils;
import org.matsim.core.utils.geometry.CoordUtils;
import org.matsim.facilities.Facility;
import org.matsim.pt.transitSchedule.api.*;
import org.matsim.utils.objectattributes.attributable.AttributesImpl;
import org.matsim.vehicles.MatsimVehicleReader;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import java.util.zip.GZIPInputStream;
import java.util.zip.GZIPOutputStream;

/**
 * Zone-to-zone transit travel times with MATSim's SwissRailRaptor (the transit router of the assignment runs, MATSim 2024.0),
 * on the pt2matsim-mapped MTA schedule.  One raptor tree per origin centroid and departure time (walk access to the stops
 * within the search radius, in-vehicle time, waiting at the first stop and at transfers, transfer walks), then the walk from
 * every reachable stop to the destination centroid; the destination time is the minimum over its stops.  The skim value of a
 * pair is the mean over the departure times (even draws inside the peak window, so the initial wait averages over the headway).
 * Two schedules are routed: the full one (bus, light rail, metro, MARC) and the bus-only one (local and commuter bus).
 * Walk parameters are the ones of RunBaltimoreToll (teleported walk 1.23 m/s, beeline factor 1.3).  Access and egress walks are
 * limited to the search radius (argument; the router's extension to the nearest stop beyond it is not counted as transit: a pair
 * without a stop within the radius at both ends is unreachable).
 * <p>
 * A departure whose best path arrives more than maxTT minutes later (default 180: e.g. waiting for the afternoon commuter bus) does not
 * count; the pair is reachable when at least half of the departures count, and its value is the mean over those.
 * Usage: TransitSkim network schedule vehicles centroids.csv out.csv.gz depFromH depToH depStepMin searchRadius extensionRadius threads [maxTTmin]
 *   centroids.csv: zone,x,y (EPSG of the network)
 *   out.csv.gz:   FROM,TO,ALL,BUS,RAILSHARE,ACCESS,EGRESS,WAIT,TRANSFERS  (WAIT = minutes from the arrival at the first stop to the first boarding; TRANSFERS = mean number; minutes; ALL/BUS empty when unreachable; RAILSHARE = share of the
 *                 departures whose best full-schedule path uses light rail, metro or MARC; ACCESS/EGRESS = mean walk minutes of
 *                 the full-schedule path)
 */
public class TransitSkim {
    static final Set<String> RAIL = Set.of("rail", "subway", "tram", "train", "light_rail");

    static Facility fac(Coord c) {
        return new Facility() {
            public Id<Link> getLinkId() { return null; }
            public Coord getCoord() { return c; }
            public Map<String, Object> getCustomAttributes() { return new HashMap<>(); }
        };
    }

    static Config config(double searchRadius, double extensionRadius) {
        Config config = ConfigUtils.createConfig(new SwissRailRaptorConfigGroup());
        config.transit().setUseTransit(true);
        config.transitRouter().setSearchRadius(searchRadius);
        config.transitRouter().setExtensionRadius(extensionRadius);
        config.routing().removeModeRoutingParams("walk");
        RoutingConfigGroup.TeleportedModeParams t = new RoutingConfigGroup.TeleportedModeParams("walk");
        t.setBeelineDistanceFactor(1.3); t.setTeleportedModeSpeed(Double.parseDouble(System.getProperty("skim.access.speed", "1.23"))); config.routing().addTeleportedModeParams(t);   // skim.access.speed (m/s, default walk 1.23): drive-access skims of the tour mode choice (2026-10-26)
        return config;
    }

    static Scenario load(Config config, String net, String sched, String veh, boolean busOnly) {
        Scenario sc = ScenarioUtils.createScenario(config);
        new MatsimNetworkReader(sc.getNetwork()).readFile(net);
        new TransitScheduleReader(sc).readFile(sched);
        new MatsimVehicleReader(sc.getTransitVehicles()).readFile(veh);
        artificialRoutes(sc);
        if (busOnly) {
            TransitSchedule s = sc.getTransitSchedule();
            List<TransitLine> drop = new ArrayList<>();
            for (TransitLine l : s.getTransitLines().values()) {
                for (TransitRoute r : new ArrayList<>(l.getRoutes().values())) if (!"bus".equals(r.getTransportMode())) l.removeRoute(r);
                if (l.getRoutes().isEmpty()) drop.add(l);
            }
            for (TransitLine l : drop) s.removeTransitLine(l);
        }
        // stop facilities without a route (the bus-only filter leaves the rail stops behind; SwissRailRaptorData needs every facility on a route)
        TransitSchedule s = sc.getTransitSchedule(); Set<Id<TransitStopFacility>> used = new HashSet<>();
        for (TransitLine l : s.getTransitLines().values()) for (TransitRoute r : l.getRoutes().values()) for (TransitRouteStop rs : r.getStops()) used.add(rs.getStopFacility().getId());
        for (TransitStopFacility f : new ArrayList<>(s.getFacilities().values())) if (!used.contains(f.getId())) s.removeStopFacility(f);
        MinimalTransferTimes mtt = s.getMinimalTransferTimes(); List<Id<TransitStopFacility>[]> dropT = new ArrayList<>();
        for (MinimalTransferTimes.MinimalTransferTimesIterator it = mtt.iterator(); it.hasNext(); ) {
            it.next();
            if (!used.contains(it.getFromStopId()) || !used.contains(it.getToStopId())) dropT.add(new Id[]{it.getFromStopId(), it.getToStopId()});
        }
        for (Id<TransitStopFacility>[] p : dropT) mtt.remove(p[0], p[1]);
        return sc;
    }

    /** an unmapped schedule (no network routes, e.g. pt2matsim Gtfs2TransitSchedule output; the tour mode choice's regional
     *  schedule, 2026-10-26): every stop facility gets a loop link at its own node and every route the artificial link sequence
     *  loop(s0), s0->s1, loop(s1), ..., which is all the raptor needs (it routes on the timetable).  Mapped schedules are untouched. */
    static void artificialRoutes(Scenario sc) {
        org.matsim.api.core.v01.network.Network net = sc.getNetwork(); org.matsim.api.core.v01.network.NetworkFactory nf = net.getFactory();
        boolean any = false;
        for (TransitLine l : sc.getTransitSchedule().getTransitLines().values()) for (TransitRoute r : l.getRoutes().values()) if (r.getRoute() == null) { any = true; break; }
        if (!any) return;
        Map<Id<TransitStopFacility>, Link> loop = new HashMap<>(); int nl = 0;
        for (TransitStopFacility f : sc.getTransitSchedule().getFacilities().values()) {
            Id<org.matsim.api.core.v01.network.Node> nid = Id.createNodeId("ptart_" + f.getId());
            org.matsim.api.core.v01.network.Node nd = net.getNodes().get(nid);
            if (nd == null) { nd = nf.createNode(nid, f.getCoord()); net.addNode(nd); }
            Link lk = nf.createLink(Id.createLinkId("ptart_" + f.getId()), nd, nd); lk.setLength(1.0); lk.setFreespeed(30); lk.setAllowedModes(Set.of("pt"));
            net.addLink(lk); f.setLinkId(lk.getId()); loop.put(f.getId(), lk); nl++;
        }
        for (TransitLine l : sc.getTransitSchedule().getTransitLines().values()) for (TransitRoute r : l.getRoutes().values()) {
            if (r.getRoute() != null) continue;
            List<Id<Link>> mid = new ArrayList<>(); List<TransitRouteStop> st = r.getStops();
            for (int k = 1; k < st.size(); k++) {
                TransitStopFacility a = st.get(k - 1).getStopFacility(), b = st.get(k).getStopFacility();
                Id<Link> id = Id.createLinkId("ptart_" + a.getId() + "_" + b.getId());
                if (!net.getLinks().containsKey(id)) {
                    Link lk = nf.createLink(id, loop.get(a.getId()).getToNode(), loop.get(b.getId()).getFromNode());
                    lk.setLength(Math.max(1.0, CoordUtils.calcEuclideanDistance(a.getCoord(), b.getCoord()))); lk.setFreespeed(30); lk.setAllowedModes(Set.of("pt")); net.addLink(lk); nl++;
                }
                mid.add(id); if (k < st.size() - 1) mid.add(loop.get(b.getId()).getId());
            }
            r.setRoute(org.matsim.core.population.routes.RouteUtils.createLinkNetworkRouteImpl(loop.get(st.get(0).getStopFacility().getId()).getId(), mid, loop.get(st.get(st.size() - 1).getStopFacility().getId()).getId()));
        }
        System.out.println("unmapped schedule: artificial network routes on " + nl + " links");
    }

    static class Zone { int id; Coord c; Zone(int id, double x, double y) { this.id = id; this.c = new Coord(x, y); } }

    /** egress candidates of a zone: the stops within the search radius and their walk time */
    static Map<Id<TransitStopFacility>, Double> egress(SwissRailRaptorData data, Coord c, double r, double ext, double walkSpeed) {
        Collection<TransitStopFacility> stops = data.findNearbyStops(c.getX(), c.getY(), r);   // no extension beyond the search radius: a zone without a stop within r has no transit (the extension rule of the router would walk to the nearest stop however far)
        Map<Id<TransitStopFacility>, Double> m = new HashMap<>();
        for (TransitStopFacility s : stops) m.put(s.getId(), CoordUtils.calcEuclideanDistance(c, s.getCoord()) / walkSpeed);
        return m;
    }

    public static void main(String[] a) throws Exception {
        String net = a[0], sched = a[1], veh = a[2], centroids = a[3], out = a[4];
        double depFrom = Double.parseDouble(a[5]) * 3600, depTo = Double.parseDouble(a[6]) * 3600, step = Double.parseDouble(a[7]) * 60;
        double R = Double.parseDouble(a[8]), E = Double.parseDouble(a[9]); int threads = Integer.parseInt(a[10]);
        // drive access (2026-10-26, tour mode choice): -Dskim.access.radius (m) is the radius of the access search at the origin and
        // -Dskim.access.speed the access speed; egress stays a walk within R at 1.23 m/s / 1.3
        final double RA = Double.parseDouble(System.getProperty("skim.access.radius", String.valueOf(R)));
        final double maxTT = (a.length > 11 && !a[11].equals("debug") ? Double.parseDouble(a[11]) : 180) * 60; final double minShare = 0.5;   // a departure counts only when it arrives within maxTT; a pair is reachable when at least minShare of the departures do
        List<Double> deps = new ArrayList<>(); for (double t = depFrom; t < depTo - 1e-6; t += step) deps.add(t);
        List<Zone> zones = new ArrayList<>();
        try (BufferedReader br = new BufferedReader(new FileReader(centroids))) {
            String line = br.readLine();
            while ((line = br.readLine()) != null) { String[] f = line.split(","); zones.add(new Zone(Integer.parseInt(f[0]), Double.parseDouble(f[1]), Double.parseDouble(f[2]))); }
        }
        System.out.println("zones " + zones.size() + ", departures " + deps.size() + " (" + depFrom / 3600 + "-" + depTo / 3600 + " h every " + step / 60 + " min), search radius " + R + " m, extension " + E + " m, threads " + threads);
        Config config = config(RA, E);
        Scenario scAll = load(config, net, sched, veh, false), scBus = load(config, net, sched, veh, true);
        System.out.println("full schedule: " + scAll.getTransitSchedule().getTransitLines().size() + " lines, " + scAll.getTransitSchedule().getFacilities().size() + " stops; bus-only: " + scBus.getTransitSchedule().getTransitLines().size() + " lines");
        RaptorStaticConfig sconf = RaptorUtils.createStaticConfig(config); sconf.setOptimization(RaptorStaticConfig.RaptorOptimization.OneToAllRouting);
        SwissRailRaptorData dAll = SwissRailRaptorData.create(scAll.getTransitSchedule(), scAll.getTransitVehicles(), sconf, scAll.getNetwork(), null);
        SwissRailRaptorData dBus = SwissRailRaptorData.create(scBus.getTransitSchedule(), scBus.getTransitVehicles(), sconf, scBus.getNetwork(), null);
        RaptorParameters params = RaptorUtils.createParameters(config); double walkSpeed = 1.23 / 1.3; double maxAccess = RA / params.getBeelineWalkSpeed();   // access walks beyond the search radius (the router's extension to the nearest stop) do not count as transit
        System.out.println("beeline walk speed " + walkSpeed + " m/s (incl. factor), marginal utility pt " + params.getMarginalUtilityOfTravelTime_utl_s("pt") + " /s, waiting " + params.getMarginalUtilityOfWaitingPt_utl_s() + " /s");
        int n = zones.size();
        if (Arrays.asList(a).contains("debug")) {   // debug: print the full-schedule route of the pairs given as zone ids (o1 d1 o2 d2 ...) at the first departure
            SwissRailRaptor r = new SwissRailRaptor(dAll, new DefaultRaptorParametersForPerson(config), new LeastCostRaptorRouteSelector(), new DefaultRaptorStopFinder(config, new DefaultRaptorIntermodalAccessEgress(), Map.of()), new DefaultRaptorInVehicleCostCalculator(), new DefaultRaptorTransferCostCalculator());
            Map<Integer, Zone> byId = new HashMap<>(); for (Zone z : zones) byId.put(z.id, z);
            for (int k = Arrays.asList(a).indexOf("debug") + 1; k + 1 < a.length; k += 2) {
                Zone o = byId.get(Integer.parseInt(a[k])), d = byId.get(Integer.parseInt(a[k + 1])); double dep = deps.get(0);
                System.out.println("=== " + o.id + " -> " + d.id + " beeline " + Math.round(CoordUtils.calcEuclideanDistance(o.c, d.c)) + " m, dep " + dep / 3600);
                for (RaptorRoute rr : r.calcRoutes(fac(o.c), fac(d.c), dep, dep, dep, null, new AttributesImpl())) {
                    System.out.println(" calcRoutes: travel time " + rr.getTravelTime() / 60 + " min, transfers " + rr.getNumberOfTransfers() + ", cost " + rr.getTotalCosts());
                    for (RaptorRoute.RoutePart p : rr.getParts()) System.out.println("   " + p.mode + " " + (p.line == null ? "" : p.line.getId() + "/" + p.route.getTransportMode()) + " " + (p.fromStop == null ? "-" : p.fromStop.getId()) + " -> " + (p.toStop == null ? "-" : p.toStop.getId()) + " dep " + p.depTime / 3600 + " board " + p.boardingTime / 3600 + " arr " + p.arrivalTime / 3600 + " dist " + Math.round(p.distance));
                }
                Map<Id<TransitStopFacility>, TravelInfo> tree = r.calcTree(fac(o.c), dep, null, new AttributesImpl());
                Map<Id<TransitStopFacility>, Double> eg = egress(dAll, d.c, R, E, walkSpeed); double best = Double.POSITIVE_INFINITY; TravelInfo bi = null; double bw = 0; Id<TransitStopFacility> bs = null;
                for (Map.Entry<Id<TransitStopFacility>, Double> e : eg.entrySet()) { TravelInfo ti = tree.get(e.getKey()); if (ti == null || ti.isWalkOnly() || ti.accessTime > maxAccess) continue; double tt = ti.ptArrivalTime + e.getValue() - dep; if (tt < best) { best = tt; bi = ti; bw = e.getValue(); bs = e.getKey(); } }
                if (bi == null) { System.out.println(" tree: unreachable (" + eg.size() + " egress stops)"); continue; }
                System.out.println(" tree: " + best / 60 + " min via stop " + bs + " (egress walk " + bw / 60 + " min, " + eg.size() + " candidate stops); access " + bi.accessTime / 60 + " min from " + bi.departureStop + ", ptDep " + bi.ptDepartureTime / 3600 + " ptArr " + bi.ptArrivalTime / 3600 + " wait " + bi.waitingTime / 60 + " transfers " + bi.transferCount + " cost " + bi.travelCost);
                for (RaptorRoute.RoutePart p : bi.getRaptorRoute().getParts()) System.out.println("   " + p.mode + " " + (p.line == null ? "" : p.line.getId() + "/" + p.route.getTransportMode()) + " " + (p.fromStop == null ? "-" : p.fromStop.getId()) + " -> " + (p.toStop == null ? "-" : p.toStop.getId()) + " dep " + p.depTime / 3600 + " board " + p.boardingTime / 3600 + " arr " + p.arrivalTime / 3600 + " dist " + Math.round(p.distance));
            }
            return;
        }
        List<Map<Id<TransitStopFacility>, Double>> egAll = new ArrayList<>(), egBus = new ArrayList<>();
        for (Zone z : zones) { egAll.add(egress(dAll, z.c, R, E, walkSpeed)); egBus.add(egress(dBus, z.c, R, E, walkSpeed)); }
        float[][] all = new float[n][n], bus = new float[n][n], rail = new float[n][n], acc = new float[n][n], egr = new float[n][n], wai = new float[n][n], trf = new float[n][n];
        for (float[] row : all) Arrays.fill(row, Float.NaN); for (float[] row : bus) Arrays.fill(row, Float.NaN);
        ExecutorService ex = Executors.newFixedThreadPool(threads); List<Future<?>> fs = new ArrayList<>(); long t0 = System.currentTimeMillis();
        final int[] done = {0};
        for (int oi = 0; oi < n; oi++) {
            final int o = oi;
            fs.add(ex.submit(() -> {
                SwissRailRaptor rAll = new SwissRailRaptor(dAll, new DefaultRaptorParametersForPerson(config), new LeastCostRaptorRouteSelector(), new DefaultRaptorStopFinder(config, new DefaultRaptorIntermodalAccessEgress(), Map.of()), new DefaultRaptorInVehicleCostCalculator(), new DefaultRaptorTransferCostCalculator());
                SwissRailRaptor rBus = new SwissRailRaptor(dBus, new DefaultRaptorParametersForPerson(config), new LeastCostRaptorRouteSelector(), new DefaultRaptorStopFinder(config, new DefaultRaptorIntermodalAccessEgress(), Map.of()), new DefaultRaptorInVehicleCostCalculator(), new DefaultRaptorTransferCostCalculator());
                double[] sAll = new double[n], sBus = new double[n], sRail = new double[n], sAcc = new double[n], sEgr = new double[n], sWai = new double[n], sTrf = new double[n]; int[] cAll = new int[n], cBus = new int[n];
                Facility from = fac(zones.get(o).c);
                for (double dep : deps) {
                    Map<Id<TransitStopFacility>, TravelInfo> tree = rAll.calcTree(from, dep, null, new AttributesImpl());
                    Map<Id<TransitStopFacility>, TravelInfo> treeB = rBus.calcTree(from, dep, null, new AttributesImpl());
                    for (int d = 0; d < n; d++) {
                        if (d == o) continue;
                        double best = Double.POSITIVE_INFINITY; TravelInfo bi = null; double bw = 0;
                        for (Map.Entry<Id<TransitStopFacility>, Double> e : egAll.get(d).entrySet()) {
                            TravelInfo ti = tree.get(e.getKey());
                            if (ti == null || ti.isWalkOnly() || ti.accessTime > maxAccess) continue;
                            double tt = ti.ptArrivalTime + e.getValue() - dep;
                            if (tt < best) { best = tt; bi = ti; bw = e.getValue(); }
                        }
                        if (bi != null && best <= maxTT) {
                            sAll[d] += best; cAll[d]++; sAcc[d] += bi.accessTime; sEgr[d] += bw; sWai[d] += bi.waitingTime + Math.max(0, bi.ptDepartureTime - dep - bi.accessTime - bi.waitingTime); sTrf[d] += bi.transferCount;
                            boolean usesRail = false;
                            for (RaptorRoute.RoutePart p : bi.getRaptorRoute().getParts()) if (p.line != null && p.route != null && RAIL.contains(p.route.getTransportMode())) { usesRail = true; break; }
                            if (usesRail) sRail[d] += 1;
                        }
                        best = Double.POSITIVE_INFINITY; boolean any = false;
                        for (Map.Entry<Id<TransitStopFacility>, Double> e : egBus.get(d).entrySet()) {
                            TravelInfo ti = treeB.get(e.getKey());
                            if (ti == null || ti.isWalkOnly() || ti.accessTime > maxAccess) continue;
                            double tt = ti.ptArrivalTime + e.getValue() - dep;
                            if (tt < best) { best = tt; any = true; }
                        }
                        if (any && best <= maxTT) { sBus[d] += best; cBus[d]++; }
                    }
                }
                for (int d = 0; d < n; d++) {
                    if (cAll[d] >= minShare * deps.size()) { all[o][d] = (float) (sAll[d] / cAll[d] / 60); rail[o][d] = (float) (sRail[d] / cAll[d]); acc[o][d] = (float) (sAcc[d] / cAll[d] / 60); egr[o][d] = (float) (sEgr[d] / cAll[d] / 60); wai[o][d] = (float) (sWai[d] / cAll[d] / 60); trf[o][d] = (float) (sTrf[d] / cAll[d]); }
                    if (cBus[d] >= minShare * deps.size()) bus[o][d] = (float) (sBus[d] / cBus[d] / 60);
                }
                synchronized (done) { done[0]++; if (done[0] % 100 == 0) System.out.println("origins done " + done[0] + "/" + n + " after " + (System.currentTimeMillis() - t0) / 1000 + " s"); }
                return null;
            }));
        }
        for (Future<?> f : fs) f.get();
        ex.shutdown();
        System.out.println("routing finished in " + (System.currentTimeMillis() - t0) / 1000 + " s");
        long reach = 0, reachBus = 0;
        try (Writer w = new BufferedWriter(new OutputStreamWriter(new GZIPOutputStream(new FileOutputStream(out)), StandardCharsets.UTF_8))) {
            w.write("FROM,TO,ALL,BUS,RAILSHARE,ACCESS,EGRESS,WAIT,TRANSFERS\n");
            for (int o = 0; o < n; o++) for (int d = 0; d < n; d++) {
                if (Float.isNaN(all[o][d]) && Float.isNaN(bus[o][d])) continue;
                if (!Float.isNaN(all[o][d])) reach++; if (!Float.isNaN(bus[o][d])) reachBus++;
                w.write(zones.get(o).id + "," + zones.get(d).id + "," + (Float.isNaN(all[o][d]) ? "" : String.format("%.2f", all[o][d])) + "," + (Float.isNaN(bus[o][d]) ? "" : String.format("%.2f", bus[o][d])) + "," + String.format("%.3f", rail[o][d]) + "," + String.format("%.2f", acc[o][d]) + "," + String.format("%.2f", egr[o][d]) + "," + String.format("%.2f", wai[o][d]) + "," + String.format("%.3f", trf[o][d]) + "\n");
            }
        }
        System.out.println("pairs reachable: full schedule " + reach + ", bus only " + reachBus + " of " + ((long) n * (n - 1)) + "; written " + out);
    }
}
