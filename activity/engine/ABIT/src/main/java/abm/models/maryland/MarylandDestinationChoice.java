package abm.models.maryland;

import abm.data.DataSet;
import abm.data.geo.Location;
import abm.data.geo.MicroscopicLocation;
import abm.data.geo.Zone;
import abm.data.plans.Activity;
import abm.data.plans.Mode;
import abm.data.plans.Purpose;
import abm.data.plans.Tour;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.models.destinationChoice.DestinationChoice;
import abm.properties.AbitResources;
import abm.properties.InternalProperties;
import abm.utils.AbitUtils;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.*;

/**
 * LOS-SENSITIVE gravity destination choice (Tour-Based MITO #02). The destination zone j is drawn with
 * probability  P(j|i) proportional to  attraction_j * f(t_ij),  where t_ij is the real car TIME skim
 * (so a congested/tolled skim shifts destinations closer — the property required for the I-695 study).
 *
 * Trip-length long-tail fix: f is a TWO-COMPONENT friction of travel time,
 *     f(t) = (t+1)^b_logtime * exp(b_time*t)  +  w2 * (t+1)^p2 * exp(b2*t),
 * fit jointly (per discretionary purpose) to the cleaned-RTS median AND mean AND CDF tail. The steep
 * first term sets the short-range bulk (median); the shallower-decay second term supplies the fat
 * long-trip tail that a single Tanner cannot reach without over-lengthening the median (it caps the
 * mean/median skew near ~1.4, but RTS SHOP/OTHER need ~1.8-2.1). Because BOTH terms decay in t, the
 * friction stays LOS-sensitive — a congested/tolled skim shifts destinations closer and the mean drops
 * (verified: skim x1.5 -> mean drops ~9-20%). Coefficients: input/maryland/coef/dest_friction_power.csv
 * (columns purpose,b_logtime,b_time,w2,p2,b2; w2=0 => single Tanner, e.g. WORK). No fixed empirical-
 * distance sampling is used, so destination choice remains fully impedance-driven.
 *
 * Validation_2026 stage 3 (2026-10-22): with dest.choice.model = mnl the estimated multinomial logit at the end of this class
 * replaces the gravity form for the purposes of dest.mnl.file (primary destinations here, stops through MarylandStopModel).
 *
 * Per-(home-zone x purpose) sampling CDFs are cached. A static timeScale (dest.time.scale, default 1.0)
 * multiplies skim time for the congestion/LOS-sensitivity test.
 */
public class MarylandDestinationChoice implements DestinationChoice {

    private static final Map<Purpose, Double> bLogTime = new HashMap<>();
    private static final Map<Purpose, Double> bTime = new HashMap<>();
    // Optional second friction component (fat long-trip tail): w2 * (t+1)^p2 * exp(b2*t).
    // When w2 == 0 the friction reduces to the single-term Tanner (backward compatible).
    private static final Map<Purpose, Double> tailW = new HashMap<>();
    private static final Map<Purpose, Double> tailLogTime = new HashMap<>();
    private static final Map<Purpose, Double> tailTime = new HashMap<>();
    private static boolean loaded = false;
    private static volatile double timeScale = 1.0;
    // county-border crossing disutility for discretionary destinations (calibrated to the
    // audited border-screenline counts; property-gated, inert when lambda == 0)
    private static double borderLambda = 0.0;
    private static double[][] borderSegs = null;      // rows: border,x1,y1,x2,y2

    private final DataSet dataSet;
    private final List<Zone> zones;
    private final int[] zoneIds;
    private final double[] attr;
    private final double[] intraKm;                 // intrazonal distance 0.5 sqrt(area), km (convention of the stage-3 metrics)
    private final MicroscopicLocation[] zoneLoc;
    private final Random rnd = AbitUtils.getRandomObject();
    // cache: homeZoneId -> purpose -> cumulative weights over zones
    private final Map<Long, double[]> cache = new java.util.concurrent.ConcurrentHashMap<>();

    // Validation_2026 stage 3, second pass (2026-10-22): purpose-specific attraction and distance-band constants.
    //  dest.attraction.file   purpose,hh.total,jj.total,jj.retail,jj.office,jj.other,students: attraction_j = 1 + sum(w_k x_kj) with
    //                         the zone attributes the reader builds (hh.total = sampled persons, scaled by 1/sample.fraction to the
    //                         scale of the job and student counts, which are full counts); a purpose without a row keeps the
    //                         default attraction above (population + 0.25 jobs).
    //  dest.distance.bands    purpose,lo_km,constant: the friction is multiplied by exp(constant) of the car-distance band of the
    //                         pair (bands [lo_km, next lo_km); intrazonal 0.5 sqrt(area)); calibrated per purpose to the survey's
    //                         trip-length distribution (short-distance term); a purpose without rows has no band term.
    private static final String[] ATTR_KEYS = {"hh.total", "jj.total", "jj.retail", "jj.office", "jj.other", "students"};
    private static final Map<Purpose, double[]> attrWeights = new HashMap<>();
    private static final Map<Purpose, double[]> bandLo = new HashMap<>();
    private static final Map<Purpose, double[]> bandC = new HashMap<>();
    private static double hhScale = 1.0;
    private static boolean fullJobs = false;
    private final Map<Purpose, double[]> attrByPurpose = new HashMap<>();

    public MarylandDestinationChoice(DataSet dataSet) {
        this.dataSet = dataSet;
        this.zones = new ArrayList<>(dataSet.getZones().values());
        this.zoneIds = new int[zones.size()];
        this.attr = new double[zones.size()];
        this.intraKm = new double[zones.size()];
        this.zoneLoc = new MicroscopicLocation[zones.size()];
        if (!loaded) load();
        for (int i = 0; i < zones.size(); i++) {
            Zone z = zones.get(i);
            zoneIds[i] = z.getZoneId();
            // discretionary attraction is population-dominant (retail/services follow residents and are
            // spatially distributed) so short local trips are reproduced; jobs down-weighted so shopping/
            // other are not all pulled to the (few) high-employment downtown zones.
            // (with workplace.silo the reader counts the jobs of the FULL job file, so hh.total, a sampled count, is scaled
            // to the same basis by 1/sample.fraction; without it both are sampled counts, as in the pristine model)
            attr[i] = 1.0
                    + z.getAttribute("hh.total").map(o -> (double) ((Integer) o)).orElse(0.0) * (fullJobs ? hhScale : 1.0)
                    + 0.25 * z.getAttribute("jj.total").map(o -> (double) ((Integer) o)).orElse(0.0);
            intraKm[i] = z.getAreaKm2() > 0 ? 0.5 * Math.sqrt(z.getAreaKm2()) : 1.0;
            double x = z.getAttribute("x").map(o -> (double) o).orElse(0.0);
            double y = z.getAttribute("y").map(o -> (double) o).orElse(0.0);
            MicroscopicLocation l = new MicroscopicLocation(x, y);
            l.setZone(z);
            zoneLoc[i] = l;
        }
        for (Map.Entry<Purpose, double[]> e : attrWeights.entrySet()) {
            double[] a = new double[zones.size()]; double[] w = e.getValue();
            for (int i = 0; i < zones.size(); i++) {
                Zone z = zones.get(i); double s = 1.0;
                for (int k = 0; k < ATTR_KEYS.length; k++) {
                    if (w[k] == 0.0) continue;
                    double v = z.getAttribute(ATTR_KEYS[k]).map(o -> (double) ((Integer) o)).orElse(0.0);
                    s += w[k] * (k == 0 ? v * hhScale : v);
                }
                a[i] = s;
            }
            attrByPurpose.put(e.getKey(), a);
        }
        if (mnlActive()) buildMnlArrays();
        if (mnlActive()) for (MnlSegment s : mnl.values()) for (int t : s.type) if (t == T_LSTOUR) { MarylandTourNestedModeChoice.ensureLoaded(dataSet); break; }
    }

    private static void loadAttractionAndBands() {
        try { hhScale = 1.0 / AbitResources.instance.getDouble("sample.fraction", 1.0); } catch (Exception ignored) {}
        try { fullJobs = Boolean.parseBoolean(AbitResources.instance.getString("workplace.silo")); } catch (Exception ignored) {}
        String f = AbitResources.instance.getString("dest.attraction.file");
        if (f != null && !f.isBlank()) {
            try (BufferedReader br = new BufferedReader(new FileReader(f))) {
                String[] h = br.readLine().split(","); int[] idx = new int[ATTR_KEYS.length]; int iP = -1;
                for (int i = 0; i < h.length; i++) {
                    if (h[i].trim().equals("purpose")) iP = i;
                    for (int k = 0; k < ATTR_KEYS.length; k++) if (h[i].trim().equals(ATTR_KEYS[k])) idx[k] = i;
                }
                String line;
                while ((line = br.readLine()) != null) {
                    String[] r = line.split(","); double[] w = new double[ATTR_KEYS.length];
                    for (int k = 0; k < ATTR_KEYS.length; k++) w[k] = idx[k] > 0 && r.length > idx[k] ? Double.parseDouble(r[idx[k]].trim()) : 0.0;
                    attrWeights.put(Purpose.valueOf(r[iP].trim().toUpperCase()), w);
                }
            } catch (Exception e) { throw new RuntimeException("dest.attraction.file load failed: " + f, e); }
            System.out.println("MarylandDestinationChoice: attraction weights by purpose for " + attrWeights.keySet() + " (hh.total x " + hhScale + ")");
        }
        f = AbitResources.instance.getString("dest.distance.bands");
        if (f != null && !f.isBlank()) {
            Map<Purpose, List<double[]>> rows = new HashMap<>();
            try (BufferedReader br = new BufferedReader(new FileReader(f))) {
                br.readLine(); String line;
                while ((line = br.readLine()) != null) {
                    String[] r = line.split(",");
                    rows.computeIfAbsent(Purpose.valueOf(r[0].trim().toUpperCase()), k -> new ArrayList<>())
                            .add(new double[]{Double.parseDouble(r[1].trim()), Double.parseDouble(r[2].trim())});
                }
            } catch (Exception e) { throw new RuntimeException("dest.distance.bands load failed: " + f, e); }
            for (Map.Entry<Purpose, List<double[]>> e : rows.entrySet()) {
                List<double[]> l = e.getValue(); l.sort(Comparator.comparingDouble(a -> a[0]));
                double[] lo = new double[l.size()], c = new double[l.size()];
                for (int i = 0; i < l.size(); i++) { lo[i] = l.get(i)[0]; c[i] = l.get(i)[1]; }
                bandLo.put(e.getKey(), lo); bandC.put(e.getKey(), c);
            }
            System.out.println("MarylandDestinationChoice: distance-band constants for " + bandLo.keySet());
        }
    }

    /** exp(band constant) of the pair for the purpose; 1 without bands. */
    private static double bandFactor(Purpose p, double km) {
        double[] lo = bandLo.get(p);
        if (lo == null) return 1.0;
        double[] c = bandC.get(p); int b = 0;
        for (int i = 0; i < lo.length; i++) if (km >= lo[i]) b = i;
        return Math.exp(c[b]);
    }

    public static void setTimeScale(double s) { timeScale = s; }

    private static synchronized void load() {
        if (loaded) return;
        String f = AbitResources.instance.getString("dest.power.friction");
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            br.readLine();
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                Purpose p = Purpose.valueOf(r[0].trim().toUpperCase());
                bLogTime.put(p, Double.parseDouble(r[1].trim()));
                bTime.put(p, r.length > 2 ? Double.parseDouble(r[2].trim()) : 0.0);
                tailW.put(p, r.length > 3 ? Double.parseDouble(r[3].trim()) : 0.0);
                tailLogTime.put(p, r.length > 4 ? Double.parseDouble(r[4].trim()) : 0.0);
                tailTime.put(p, r.length > 5 ? Double.parseDouble(r[5].trim()) : 0.0);
            }
        } catch (Exception e) {
            throw new RuntimeException("dest.power.friction load failed", e);
        }
        try { timeScale = AbitResources.instance.getDouble("dest.time.scale", 1.0); } catch (Exception ignored) {}
        loadAttractionAndBands();
        loadMnl();
        try {
            borderLambda = AbitResources.instance.getDouble("dest.border.lambda", 0.0);
            String bf = AbitResources.instance.getString("dest.border.file");
            if (borderLambda > 0 && bf != null && !bf.isBlank()) {
                List<double[]> rows = new ArrayList<>();
                try (BufferedReader br = new BufferedReader(new FileReader(bf))) {
                    br.readLine();
                    String line;
                    while ((line = br.readLine()) != null) {
                        String[] r = line.split(",");
                        rows.add(new double[]{Double.parseDouble(r[0]), Double.parseDouble(r[1]),
                                Double.parseDouble(r[2]), Double.parseDouble(r[3]), Double.parseDouble(r[4])});
                    }
                }
                borderSegs = rows.toArray(new double[0][]);
                System.out.println("MarylandDestinationChoice: border penalty lambda=" + borderLambda
                        + " over " + borderSegs.length + " segments");
            }
        } catch (Exception e) {
            System.err.println("border penalty disabled: " + e.getMessage());
            borderSegs = null;
        }
        loaded = true;
    }

    private static boolean segCross(double ax, double ay, double bx, double by,
                                    double cx, double cy, double dx, double dy) {
        double d1 = (by - ay) * (cx - ax) - (bx - ax) * (cy - ay);
        double d2 = (by - ay) * (dx - ax) - (bx - ax) * (dy - ay);
        double d3 = (dy - cy) * (ax - cx) - (dx - cx) * (ay - cy);
        double d4 = (dy - cy) * (bx - cx) - (dx - cx) * (by - cy);
        return d1 * d2 < 0 && d3 * d4 < 0;
    }

    /** number of distinct county borders (0-3) crossed by the straight o-d segment */
    private static int borderCrossings(double ox, double oy, double dx, double dy) {
        if (borderSegs == null) return 0;
        boolean[] hit = new boolean[3];
        for (double[] s : borderSegs) {
            int b = (int) s[0];
            if (!hit[b] && segCross(ox, oy, dx, dy, s[1], s[2], s[3], s[4])) hit[b] = true;
        }
        int n = 0;
        for (boolean h : hit) if (h) n++;
        return n;
    }

    private double[] cdfFor(Location home, Purpose purpose) {
        double blt = bLogTime.getOrDefault(purpose, bLogTime.getOrDefault(Purpose.OTHER, -1.3));
        double bt = bTime.getOrDefault(purpose, bTime.getOrDefault(Purpose.OTHER, -0.055));
        double w2 = tailW.getOrDefault(purpose, tailW.getOrDefault(Purpose.OTHER, 0.0));
        double p2 = tailLogTime.getOrDefault(purpose, tailLogTime.getOrDefault(Purpose.OTHER, 0.0));
        double b2 = tailTime.getOrDefault(purpose, tailTime.getOrDefault(Purpose.OTHER, 0.0));
        long key = ((long) home.getZoneId() << 8) ^ purpose.ordinal();
        double[] cached = cache.get(key);
        if (cached != null) return cached;
        double hx = 0, hy = 0;
        if (home instanceof MicroscopicLocation) {
            hx = ((MicroscopicLocation) home).getX();
            hy = ((MicroscopicLocation) home).getY();
        } else {
            for (int i = 0; i < zoneIds.length; i++) {
                if (zoneIds[i] == home.getZoneId()) { hx = zoneLoc[i].getX(); hy = zoneLoc[i].getY(); break; }
            }
        }
        double[] cum = new double[zones.size()];
        double run = 0;
        double[] a = attrByPurpose.getOrDefault(purpose, attr);
        boolean bands = bandLo.containsKey(purpose);
        int homeZone = home.getZoneId();
        for (int i = 0; i < zones.size(); i++) {
            double t = dataSet.getTravelTimes().getTravelTimeInMinutes(home, zoneLoc[i], Mode.CAR_DRIVER, InternalProperties.PEAK_HOUR_MIN);
            if (!(t >= 0) || t > 600) t = 600;
            t *= timeScale;
            // Two-component LOS-sensitive friction:
            //   f = (t+1)^blt * exp(bt*t)  +  w2 * (t+1)^p2 * exp(b2*t)
            // Term 1 is a steep Tanner that sets the short-range bulk (the trip-length MEDIAN); term 2 is a
            // shallower-decay power/exp tail that supplies the fat long-trip tail (the trip-length MEAN /
            // regional VMT). BOTH terms decay in travel time, so a slower/congested/tolled skim still
            // shifts destinations closer (mean drops) — the LOS-sensitivity the I-695 study needs. When
            // w2 == 0 this reduces to the original single Tanner.
            double fr = Math.pow(t + 1.0, blt) * Math.exp(bt * t);
            if (w2 != 0.0) fr += w2 * Math.pow(t + 1.0, p2) * Math.exp(b2 * t);
            if (borderLambda > 0 && borderSegs != null && purpose != Purpose.WORK) {
                int nc = borderCrossings(hx, hy, zoneLoc[i].getX(), zoneLoc[i].getY());
                if (nc > 0) fr *= Math.exp(-borderLambda * nc);
            }
            if (bands) {
                // distance-band constant of the pair (car-distance skim; intrazonal 0.5 sqrt(area), the metric's convention)
                double km;
                if (zoneIds[i] == homeZone) km = intraKm[i];
                else {
                    int m = dataSet.getTravelDistances().getTravelDistanceInMeters(home, zoneLoc[i], Mode.UNKNOWN, InternalProperties.PEAK_HOUR_MIN);
                    km = m > 0 ? m / 1000.0 : 300.0;
                }
                fr *= bandFactor(purpose, km);
            }
            run += a[i] * fr;
            cum[i] = run;
        }
        cache.put(key, cum);
        return cum;
    }

    @Override
    public void selectMainActivityDestination(Person person, Activity activity) {
        Location home = person.getHousehold().getLocation();
        if (mnlActive() && mnl.containsKey(activity.getPurpose() + "_primary")) {
            int sel = chooseMnl(mnl.get(activity.getPurpose() + "_primary"), person, idxOf(home.getZoneId()), -1,
                    activity.getStartTime_min(), null, null, false, rnd);
            activity.setLocation(jitter(zones.get(sel)));
            return;
        }
        double[] cum = cdfFor(home, activity.getPurpose());
        double total = cum[cum.length - 1];
        int sel;
        if (total <= 0) { sel = rnd.nextInt(zones.size()); }
        else {
            double u = rnd.nextDouble() * total;
            int lo = 0, hi = cum.length - 1;
            while (lo < hi) { int m = (lo + hi) >>> 1; if (cum[m] < u) lo = m + 1; else hi = m; }
            sel = lo;
        }
        activity.setLocation(jitter(zones.get(sel)));
    }

    @Override
    public void selectStopDestination(Person person, Tour tour, Activity activity) {
        // stop near an attraction-weighted zone (short detour)
        int sel = rnd.nextInt(zones.size());
        activity.setLocation(jitter(zones.get(sel)));
    }

    private MicroscopicLocation jitter(Zone z) {
        double x = z.getAttribute("x").map(o -> (double) o).orElse(0.0);
        double y = z.getAttribute("y").map(o -> (double) o).orElse(0.0);
        MicroscopicLocation loc = new MicroscopicLocation(x + (rnd.nextDouble() - 0.5) * 200, y + (rnd.nextDouble() - 0.5) * 200);
        loc.setZone(z);
        return loc;
    }

    // =============================================================================================================================
    // Estimated multinomial-logit destination choice (Validation_2026 stage 3, 2026-10-22; 3_abit/destination_choice/,
    // ESTIMATION_REPORT.md).  Property dest.choice.model = mnl switches it on (default: the calibrated gravity form above, kept for
    // comparison); dest.mnl.file = the coefficient file (segment,variable,value; segment = <PURPOSE>_primary | <PURPOSE>_stop).
    // The utility of zone j is computed exactly as in estimation (3_abit/destination_choice/dc_model.features), over the FULL
    // choice set of all zones (no sampling at application):
    //   V_j = mu ln(1 + S_j) + sum_k beta_k x_jk,   S_j = sum_c w_c x_jc  (c = pop, ret, off, oth, stu; base weight 1)
    // primary destinations: impedance = car distance from home (km; intrazonal 0.5 sqrt(area)); stops: detour via j relative
    // to the direct path between the tour anchors home and primary destination, max(0, d_aj + d_jb - d_ab).  Variables:
    //   d_<lo>_<hi> / dt_<lo>_<hi>   piecewise-linear impedance (segment lengths, km)    d, dt   linear impedance
    //   lnd / lndt                   ln(d) / ln(1 + dt)                                  lnd_<x>, lndt_<x>   x chooser flag
    //   cgt                          car generalized minutes of ABIT's car-driver alternative: time + (0.12 $/km x distance
    //                                + toll) x 60 / VOT_hh (VOT_hh = 30 $/h x the income factor of MarylandFullModeChoice;
    //                                stops: detour, max(0, g_aj + g_jb - g_ab))
    //   ctime                        car minutes (stops: detour minutes)                 ls  ABIT mode-choice logsum (stops:
    //                                                                                         LS_aj + LS_jb - LS_ab)
    //   intra, intra_a, intra_b      j = home / j = first anchor / j = second anchor
    //   bc, dcz, va, othst, cbd      Baltimore City, DC, Virginia, DE/PA/WV, >= 10,000 jobs per km2
    //   lnretden, mix                ln(1 + retail jobs per km2), land-use mix entropy of (pop, retail, office, other jobs)
    //   lnarea                       ln(zone area, km2, at least 0.05) (2026-11-17: one attraction variable per model, mu_size ln(1 + x)
    //                                with size weight 1 = beta ln(1 + x); ln area in place of the retail density)
    //   xcounty, xstate              j outside the county / state of the origin (stops: of both anchors)
    //   ptav, ptav_car0              bus door-to-door time from home < 120 min (x household without a car)
    // chooser flags x: inc0 (household < $50k), inc2 (>= $100k), car0 (no car), car1 (0 < cars < licensed drivers), child
    // (household with a person under 18), kid (person under 18), senior (65+), worker (employed), am (start 6-9), pm (15-19),
    // ev (19-6), nonauto (stop on a tour whose mode is not car), worktour (stop on a work or school tour), inbound (stop after
    // the primary activity).  Times of day: the start of the primary activity (stops: of the tour's primary activity).
    // =============================================================================================================================
    // multi (2026-10-23): the primary destination of a tour with at least one stop (TASHA generator: a main discretionary episode of a
    // chain of two or more episodes, relocated after the chains are formed); 0 in every other call
    // re-specified models (2026-11-09, 3_abit/coef_respec): male, hh1 (one-person household) and hhsize (persons, a count, not a flag)
    // for the interactions lnd_<x> / lndt_<x>; variable lstour = logsum of the re-specified tour mode models
    // (MarylandTourNestedModeChoice.logsum, accessibility_new/mode_logsum_new.py): round trip between the two zones of a leg, both
    // halves in the period of the time of day of the choice (the flags am / pm / ev), stops = 1 (stop segments; primary segments: the
    // multi flag), joint = 0, model of the purpose of the segment (shopping -> shopping; recreation, accompany, other -> other with
    // rec / acc; work -> work; education -> school); stops: LS(a, j) + LS(j, b) - LS(a, b), primary and anchored: LS(a, j).
    private static final String[] FLAGS = {"inc0", "inc2", "car0", "car1", "child", "kid", "senior", "worker", "am", "pm", "ev", "nonauto", "worktour", "inbound", "multi",
            "male", "hh1", "hhsize"};
    private static final String[] ZVARS = {"bc", "dcz", "va", "othst", "cbd", "lnretden", "mix", "lnarea"};
    private static final String[] SIZE = {"pop", "ret", "off", "oth", "stu"};
    private static final double[] KNOTS = {1, 2, 5, 10, 20, 50}, DKNOTS = {1, 2, 5, 10, 20};
    private static final int T_PIECE = 1, T_LIN = 2, T_LN = 3, T_LNX = 4, T_CTIME = 5, T_LS = 6, T_INTRA = 7, T_INTRA_A = 8, T_INTRA_B = 9,
            T_ZONE = 10, T_XCOUNTY = 11, T_XSTATE = 12, T_PTAV_CAR0 = 13, T_PTAV = 14, T_CGT = 15, T_LSTOUR = 16;
    private static String dcModel = "gravity";
    private static Set<String> debugSegs = null;                               // dest.mnl.debug.segments: only these segments (2026-10-23)
    private static String debugFile = null;                                   // dest.mnl.debug.file: utilities of the first 30 choices
    private static final java.util.concurrent.atomic.AtomicInteger debugCount = new java.util.concurrent.atomic.AtomicInteger(), debugCountStop = new java.util.concurrent.atomic.AtomicInteger();
    // dest.mnl.debug.per.segment (2026-11-09): the first dest.mnl.debug.n choices of EVERY segment (default: the first 30 primary and
    // 30 stop choices over all segments, as before); the line then also carries the flags nonauto, worktour, inbound, multi
    private static boolean debugPerSeg = false; private static int debugN = 30;
    private static final Map<String, java.util.concurrent.atomic.AtomicInteger> debugBySeg = new java.util.concurrent.ConcurrentHashMap<>();
    private static final Map<String, MnlSegment> mnl = new LinkedHashMap<>();
    private static final Map<Purpose, double[][]> mcCoef = new HashMap<>();   // purpose -> [variable][mode] of MarylandFullModeChoice
    private static final String[] MC_VARS = {"ASC", "age", "male", "license", "hhsize", "hhautos", "coreCity", "medCity", "rural", "gc", "tripLength"};

    private static final class MnlSegment {
        String key; boolean stop; Purpose purpose; double mu; double[] w = new double[SIZE.length];
        int[] type; int[] arg; double[] beta; double[] lo, hi; String[] names;
        double[] u0;   // zone-static part: mu ln(1 + S_j) + zone variables
    }

    // dense zone arrays of the MNL (index = position in `zones`)
    private float[] mTcar, mDraw, mDkm, mBus, mTrain;
    private double[] zPop, zRet, zOff, zOth, zStu, zArea;
    private double[][] zVar;
    private int[] zCounty, zState, zBbsr;
    private final Map<Integer, Integer> idx = new HashMap<>();

    private static boolean mnlActive() { return "mnl".equalsIgnoreCase(dcModel) && !mnl.isEmpty(); }

    /** true when the estimated MNL is active for stops of the purpose (MarylandStopModel asks before drawing a stop zone). */
    public static boolean hasStopModel(Purpose p) { return mnlActive() && mnl.containsKey(p + "_stop"); }

    private int idxOf(int zoneId) { Integer i = idx.get(zoneId); if (i == null) throw new RuntimeException("zone " + zoneId + " not in the zone system"); return i; }

    private static void loadMnl() {
        try { String m = AbitResources.instance.getString("dest.choice.model"); if (m != null && !m.isBlank()) dcModel = m.trim(); } catch (Exception ignored) {}
        if (!"mnl".equalsIgnoreCase(dcModel)) return;
        try { debugFile = AbitResources.instance.getString("dest.mnl.debug.file"); if (debugFile != null && debugFile.isBlank()) debugFile = null; } catch (Exception ignored) {}
        try { String ds = AbitResources.instance.getString("dest.mnl.debug.segments"); if (ds != null && !ds.isBlank()) debugSegs = new HashSet<>(Arrays.asList(ds.trim().split(";"))); } catch (Exception ignored) {}
        try { debugPerSeg = Boolean.parseBoolean(AbitResources.instance.getString("dest.mnl.debug.per.segment")); } catch (Exception ignored) {}
        try { String dn = AbitResources.instance.getString("dest.mnl.debug.n"); if (dn != null && !dn.isBlank()) debugN = Integer.parseInt(dn.trim()); } catch (Exception ignored) {}
        String f = AbitResources.instance.getString("dest.mnl.file");
        if (f == null || f.isBlank()) throw new RuntimeException("dest.choice.model = mnl requires dest.mnl.file");
        Map<String, List<String[]>> rows = new LinkedHashMap<>();
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String[] h = br.readLine().split(","); int iS = -1, iV = -1, iX = -1;
            for (int i = 0; i < h.length; i++) { String c = h[i].trim(); if (c.equals("segment")) iS = i; if (c.equals("variable")) iV = i; if (c.equals("value")) iX = i; }
            String line;
            while ((line = br.readLine()) != null) {
                if (line.isBlank()) continue; String[] r = line.split(",");
                rows.computeIfAbsent(r[iS].trim(), k -> new ArrayList<>()).add(new String[]{r[iV].trim(), r[iX].trim()});
            }
        } catch (Exception e) { throw new RuntimeException("dest.mnl.file load failed: " + f, e); }
        for (Map.Entry<String, List<String[]>> e : rows.entrySet()) {
            MnlSegment s = new MnlSegment(); s.key = e.getKey();
            String[] kp = s.key.split("_"); s.purpose = Purpose.valueOf(kp[0]); s.stop = kp[kp.length - 1].equalsIgnoreCase("stop");   // <PURPOSE>_stop, or <PURPOSE>_<name>_stop (2026-10-23)
            List<String> nm = new ArrayList<>(); List<Double> b = new ArrayList<>();
            for (String[] r : e.getValue()) {
                double v = Double.parseDouble(r[1]);
                if (r[0].equals("mu_size")) { s.mu = v; continue; }
                if (r[0].startsWith("size_")) { int k = Arrays.asList(SIZE).indexOf(r[0].substring(5)); if (k < 0) throw new RuntimeException("unknown size component " + r[0]); s.w[k] = v; continue; }
                nm.add(r[0]); b.add(v);
            }
            int n = nm.size(); s.names = nm.toArray(new String[0]); s.beta = new double[n]; s.type = new int[n]; s.arg = new int[n]; s.lo = new double[n]; s.hi = new double[n];
            for (int k = 0; k < n; k++) {
                String v = s.names[k]; s.beta[k] = b.get(k);
                String pre = s.stop ? "dt" : "d";
                if (v.startsWith(pre + "_") && Character.isDigit(v.charAt(pre.length() + 1))) {
                    String[] p = v.split("_"); s.type[k] = T_PIECE; s.lo[k] = Double.parseDouble(p[1]); s.hi[k] = p[2].equals("inf") ? Double.POSITIVE_INFINITY : Double.parseDouble(p[2]);
                } else if (v.equals(pre)) s.type[k] = T_LIN;
                else if (v.equals(s.stop ? "lndt" : "lnd")) s.type[k] = T_LN;
                else if (v.startsWith((s.stop ? "lndt" : "lnd") + "_")) {
                    s.type[k] = T_LNX; s.arg[k] = Arrays.asList(FLAGS).indexOf(v.substring(v.indexOf('_') + 1));
                    if (s.arg[k] < 0) throw new RuntimeException("unknown chooser flag in " + v);
                } else if (v.equals("ctime")) s.type[k] = T_CTIME;
                else if (v.equals("cgt")) s.type[k] = T_CGT;
                else if (v.equals("ls")) s.type[k] = T_LS;
                else if (v.equals("lstour")) s.type[k] = T_LSTOUR;
                else if (v.equals("intra")) s.type[k] = T_INTRA;
                else if (v.equals("intra_a")) s.type[k] = T_INTRA_A;
                else if (v.equals("intra_b")) s.type[k] = T_INTRA_B;
                else if (Arrays.asList(ZVARS).contains(v)) { s.type[k] = T_ZONE; s.arg[k] = Arrays.asList(ZVARS).indexOf(v); }
                else if (v.equals("xcounty")) s.type[k] = T_XCOUNTY;
                else if (v.equals("xstate")) s.type[k] = T_XSTATE;
                else if (v.equals("ptav_car0")) s.type[k] = T_PTAV_CAR0;
                else if (v.equals("ptav")) s.type[k] = T_PTAV;
                else throw new RuntimeException("dest.mnl.file: unknown variable " + v + " in segment " + s.key);
            }
            mnl.put(s.key, s);
        }
        // mode-choice coefficients for the logsum: the files of modechoice.dir as they are when the destination choice is first
        // constructed (before MarylandFullModeChoice re-anchors and rewrites them), i.e. the coefficient set of the run
        String dir = AbitResources.instance.getString("modechoice.dir");
        for (Purpose p : new Purpose[]{Purpose.SHOPPING, Purpose.RECREATION, Purpose.ACCOMPANY, Purpose.OTHER, Purpose.WORK}) {
            String mf = dir + "/modechoice_full_" + p.toString().toLowerCase() + ".csv";
            double[][] c = new double[MC_VARS.length][7];
            try (BufferedReader br = new BufferedReader(new FileReader(mf))) {
                String[] h = br.readLine().split(","); int[] col = new int[7];
                for (int m = 0; m < 7; m++) { col[m] = -1; for (int i = 0; i < h.length; i++) if (h[i].trim().equals(MarylandFullModeChoice.NAME[m])) col[m] = i; }
                String line;
                while ((line = br.readLine()) != null) {
                    String[] r = line.split(","); int v = Arrays.asList(MC_VARS).indexOf(r[0].trim());
                    if (v < 0) continue;
                    for (int m = 0; m < 7; m++) c[v][m] = Double.parseDouble(r[col[m]].trim());
                }
            } catch (Exception ex) { if (p != Purpose.WORK) throw new RuntimeException("mode coefficients for the logsum: " + mf, ex); continue; }
            mcCoef.put(p, c);
        }
        System.out.println("MarylandDestinationChoice: estimated MNL for " + mnl.keySet() + " from " + f);
    }

    /** Dense zone arrays and the zone-static utility parts (constructor, when the MNL is active). */
    private void buildMnlArrays() {
        int n = zones.size();
        for (int i = 0; i < n; i++) idx.put(zoneIds[i], i);
        Map<Integer, Integer> county = new HashMap<>();
        String zf = AbitResources.instance.getString("zone.attributes.file");
        try (BufferedReader br = new BufferedReader(new FileReader(zf))) {
            String[] h = br.readLine().split(","); int iId = -1, iC = -1;
            for (int i = 0; i < h.length; i++) { if (h[i].trim().equals("id")) iId = i; if (h[i].trim().equals("countyfips")) iC = i; }
            String line; while ((line = br.readLine()) != null) { String[] r = line.split(","); county.put(Integer.parseInt(r[iId].trim()), Integer.parseInt(r[iC].trim())); }
        } catch (Exception e) { throw new RuntimeException("zone.attributes.file (county) failed: " + zf, e); }
        zPop = new double[n]; zRet = new double[n]; zOff = new double[n]; zOth = new double[n]; zStu = new double[n]; zArea = new double[n];
        zCounty = new int[n]; zState = new int[n]; zBbsr = new int[n]; zVar = new double[ZVARS.length][n];
        for (int i = 0; i < n; i++) {
            Zone z = zones.get(i);
            zPop[i] = z.getAttribute("hh.total").map(o -> (double) ((Integer) o)).orElse(0.0) * hhScale;
            zRet[i] = z.getAttribute("jj.retail").map(o -> (double) ((Integer) o)).orElse(0.0);
            zOff[i] = z.getAttribute("jj.office").map(o -> (double) ((Integer) o)).orElse(0.0);
            zOth[i] = z.getAttribute("jj.other").map(o -> (double) ((Integer) o)).orElse(0.0);
            zStu[i] = z.getAttribute("students").map(o -> (double) ((Integer) o)).orElse(0.0);
            zArea[i] = z.getAreaKm2();
            zCounty[i] = county.getOrDefault(zoneIds[i], 0); zState[i] = zCounty[i] / 1000;
            zBbsr[i] = z.getBBSRType() == null ? 0 : z.getBBSRType().code();
            double area = Math.max(zArea[i], 0.05), jobs = zRet[i] + zOff[i] + zOth[i];
            zVar[0][i] = zCounty[i] == 24510 ? 1 : 0; zVar[1][i] = zCounty[i] == 11001 ? 1 : 0; zVar[2][i] = zState[i] == 51 ? 1 : 0;
            zVar[3][i] = (zState[i] == 10 || zState[i] == 42 || zState[i] == 54) ? 1 : 0; zVar[4][i] = jobs / area >= 10000 ? 1 : 0;
            zVar[5][i] = Math.log1p(zRet[i] / area);
            double[] s = {zPop[i], zRet[i], zOff[i], zOth[i]}; double tot = 0; for (double v : s) tot += v; double ent = 0;
            for (double v : s) { double sh = v / Math.max(tot, 1e-9); ent -= sh * Math.log(Math.max(sh, 1e-12)); }
            zVar[6][i] = ent / Math.log(4);
            zVar[7][i] = Math.log(area);
        }
        mTcar = new float[n * n]; mDraw = new float[n * n]; mDkm = new float[n * n]; mBus = new float[n * n]; mTrain = new float[n * n];
        for (int i = 0; i < n; i++) for (int j = 0; j < n; j++) {
            int k = i * n + j;
            mTcar[k] = dataSet.getTravelTimes().getTravelTimeInMinutes(zoneLoc[i], zoneLoc[j], Mode.CAR_DRIVER, InternalProperties.PEAK_HOUR_MIN);
            mBus[k] = dataSet.getTravelTimes().getTravelTimeInMinutes(zoneLoc[i], zoneLoc[j], Mode.BUS, InternalProperties.PEAK_HOUR_MIN);
            mTrain[k] = dataSet.getTravelTimes().getTravelTimeInMinutes(zoneLoc[i], zoneLoc[j], Mode.TRAIN, InternalProperties.PEAK_HOUR_MIN);
            int m = dataSet.getTravelDistances().getTravelDistanceInMeters(zoneLoc[i], zoneLoc[j], Mode.UNKNOWN, InternalProperties.PEAK_HOUR_MIN);
            mDraw[k] = (float) (m / 1000.0);
            double km = i == j ? intraKm[i] : (m > 0 ? m / 1000.0 : 300.0);
            mDkm[k] = (float) Math.min(km, 300.0);
        }
        for (MnlSegment s : mnl.values()) {
            s.u0 = new double[n];
            for (int j = 0; j < n; j++) {
                double S = s.w[0] * zPop[j] + s.w[1] * zRet[j] + s.w[2] * zOff[j] + s.w[3] * zOth[j] + s.w[4] * zStu[j];
                double u = s.mu * Math.log1p(S);
                for (int k = 0; k < s.type.length; k++) if (s.type[k] == T_ZONE) u += s.beta[k] * zVar[s.arg[k]][j];
                s.u0[j] = u;
            }
        }
    }

    /** person-level part of ABIT's mode utilities (MarylandFullModeChoice.probabilities): returns [a_m (without the origin's
     *  area-type terms), gc coefficient, trip-length coefficient, VOT_m] per mode, plus the area-type coefficients. */
    private static double[][] mcPerson(Purpose p, Person person) {
        double[][] c = mcCoef.get(p); if (c == null) c = mcCoef.get(Purpose.OTHER);
        Household hh = person.getHousehold();
        double age = person.getAge(), male = person.getGender() == de.tum.bgu.msm.data.person.Gender.MALE ? 1 : 0, lic = person.isHasLicense() ? 1 : 0;
        double hhsize = hh.getPersons().size(), autos = hh.getNumberOfCars(), inc = 0;
        for (Person pp : hh.getPersons()) inc += pp.getMonthlyIncome_eur();
        double vf = Math.pow(Math.max(1.0, inc) / MarylandFullModeChoice.VOT_INCOME_REF_USD_MTH, MarylandFullModeChoice.VOT_INCOME_ELASTICITY);
        vf = Math.max(MarylandFullModeChoice.VOT_FACTOR_MIN, Math.min(MarylandFullModeChoice.VOT_FACTOR_MAX, vf));
        double[][] r = new double[7][7];
        for (int m = 0; m < 7; m++) {
            r[m][0] = c[0][m] + c[1][m] * age + c[2][m] * male + c[3][m] * lic + c[4][m] * hhsize + c[5][m] * autos;
            r[m][1] = c[9][m]; r[m][2] = c[10][m]; r[m][3] = MarylandFullModeChoice.VOT[m] * vf;
            r[m][4] = c[6][m]; r[m][5] = c[7][m]; r[m][6] = c[8][m];
        }
        return r;
    }

    /** ln sum_m exp(V_m) of ABIT's mode model between zone indices o and d. */
    private double logsum(double[][] mp, int o, int d) {
        int n = zones.size(), k = o * n + d; double dist = mDraw[k]; int bb = zBbsr[o];
        double toll = MarylandFullModeChoice.getToll(), mx = Double.NEGATIVE_INFINITY; double[] v = new double[7];
        for (int m = 0; m < 7; m++) {
            double time = m == 5 ? mBus[k] : m == 6 ? mTrain[k] : mTcar[k];
            double money = dist * MarylandFullModeChoice.COST_PER_KM[m] + (MarylandFullModeChoice.AUTO[m] ? toll : 0.0);
            double gc = mp[m][3] > 0 ? time + money * 60.0 / mp[m][3] : 0.0;
            v[m] = mp[m][0] + (bb == 10 ? mp[m][4] : 0) + (bb == 20 ? mp[m][5] : 0) + (bb == 40 ? mp[m][6] : 0) + mp[m][1] * gc + mp[m][2] * dist;
            if (v[m] > mx) mx = v[m];
        }
        double s = 0; for (double x : v) s += Math.exp(x - mx);
        return mx + Math.log(s);
    }

    private static double votFactor(Person person) {
        double inc = 0; for (Person pp : person.getHousehold().getPersons()) inc += pp.getMonthlyIncome_eur();
        double vf = Math.pow(Math.max(1.0, inc) / MarylandFullModeChoice.VOT_INCOME_REF_USD_MTH, MarylandFullModeChoice.VOT_INCOME_ELASTICITY);
        return Math.max(MarylandFullModeChoice.VOT_FACTOR_MIN, Math.min(MarylandFullModeChoice.VOT_FACTOR_MAX, vf));
    }

    /** car generalized minutes between zone indices (car-driver GC of MarylandFullModeChoice). */
    private double gt(int o, int d, double votHh, double toll) {
        int k = o * zones.size() + d;
        return mTcar[k] + (mDraw[k] * MarylandFullModeChoice.COST_PER_KM[0] + toll) * 60.0 / votHh;
    }

    private static double[] flags(Person person, int startMin, Tour tour, Mode tourMode, boolean inbound) {
        Household hh = person.getHousehold(); double inc = 0; int drivers = 0; boolean child = false;
        for (Person pp : hh.getPersons()) { inc += pp.getMonthlyIncome_eur(); if (pp.isHasLicense()) drivers++; if (pp.getAge() < 18) child = true; }
        double annual = 12.0 * inc; int cars = hh.getNumberOfCars(); int h = ((startMin % 1440) + 1440) % 1440 / 60;
        double[] f = new double[FLAGS.length];
        f[0] = annual < 50000 ? 1 : 0; f[1] = annual >= 100000 ? 1 : 0; f[2] = cars <= 0 ? 1 : 0; f[3] = cars > 0 && cars < drivers ? 1 : 0;
        f[4] = child ? 1 : 0; f[5] = person.getAge() < 18 ? 1 : 0; f[6] = person.getAge() >= 65 ? 1 : 0;
        f[7] = person.getOccupation() == de.tum.bgu.msm.data.person.Occupation.EMPLOYED ? 1 : 0;
        f[8] = h >= 6 && h < 9 ? 1 : 0; f[9] = h >= 15 && h < 19 ? 1 : 0; f[10] = (h < 6 || h >= 19) ? 1 : 0;
        f[15] = person.getGender() == de.tum.bgu.msm.data.person.Gender.MALE ? 1 : 0; f[16] = hh.getPersons().size() == 1 ? 1 : 0; f[17] = hh.getPersons().size();
        if (tour != null) {
            f[11] = (tourMode != Mode.CAR_DRIVER && tourMode != Mode.CAR_PASSENGER) ? 1 : 0;
            Purpose tp = tour.getMainActivity().getPurpose(); f[12] = (tp == Purpose.WORK || tp == Purpose.EDUCATION) ? 1 : 0;
            f[13] = inbound ? 1 : 0;
        }
        return f;
    }

    /** Draw a zone index from the estimated MNL of the segment (full choice set). a = home (primary) or first anchor (stop),
     *  b = second anchor (stop; -1 for a primary destination). */
    private int chooseMnl(MnlSegment s, Person person, int a, int b, int startMin, Tour tour, Mode tourMode, boolean inbound, Random r) {
        return chooseMnl(s, person, a, b, startMin, tour, tourMode, inbound, r, null);
    }

    private int chooseMnl(MnlSegment s, Person person, int a, int b, int startMin, Tour tour, Mode tourMode, boolean inbound, Random r, double[] flOverride) {
        int n = zones.size(); double[] fl = flOverride != null ? flOverride : flags(person, startMin, tour, tourMode, inbound);
        boolean needLs = false; for (int t : s.type) if (t == T_LS) needLs = true;
        double[][] mp = needLs ? mcPerson(s.purpose, person) : null;
        double lsAB = needLs && s.stop ? logsum(mp, a, b) : 0;
        double dAB = s.stop ? mDkm[a * n + b] : 0, tAB = s.stop ? mTcar[a * n + b] : 0;
        boolean needG = false; for (int t : s.type) if (t == T_CGT) needG = true;
        double votHh = needG ? MarylandFullModeChoice.VOT[0] * votFactor(person) : 1.0, toll = MarylandFullModeChoice.getToll();
        double gAB = needG && s.stop ? gt(a, b, votHh, toll) : 0;
        boolean needLt = false; for (int t : s.type) if (t == T_LSTOUR) needLt = true;
        MarylandTourNestedModeChoice.PA lpa = null; String lseg = null; int lper = 1; double lstops = 0, lacc = 0, lrec = 0, ltAB = 0;
        if (needLt) {
            lpa = MarylandTourNestedModeChoice.personAttrs(person); lseg = MarylandTourNestedModeChoice.logsumSegment(s.purpose);
            lper = MarylandTourNestedModeChoice.period(startMin); lstops = s.stop ? 1 : fl[14];
            lacc = s.purpose == Purpose.ACCOMPANY ? 1 : 0; lrec = s.purpose == Purpose.RECREATION ? 1 : 0;
            if (s.stop) ltAB = MarylandTourNestedModeChoice.logsum(lseg, lpa, zoneIds[a], zoneIds[b], lper, lper, lstops, 0, lacc, lrec);
        }
        double[] V = new double[n]; double mx = Double.NEGATIVE_INFINITY;
        for (int j = 0; j < n; j++) {
            double imp = s.stop ? Math.max(0.0, mDkm[a * n + j] + mDkm[j * n + b] - dAB) : mDkm[a * n + j];
            double ln = s.stop ? Math.log1p(imp) : Math.log(imp);
            double u = s.u0[j];
            for (int k = 0; k < s.type.length; k++) {
                double x;
                switch (s.type[k]) {
                    case T_PIECE: x = Math.max(0.0, Math.min(imp, s.hi[k]) - s.lo[k]); break;
                    case T_LIN: x = imp; break;
                    case T_LN: x = ln; break;
                    case T_LNX: x = ln * fl[s.arg[k]]; break;
                    case T_CTIME: x = s.stop ? Math.max(0.0, mTcar[a * n + j] + mTcar[j * n + b] - tAB) : mTcar[a * n + j]; break;
                    case T_CGT: x = s.stop ? Math.max(0.0, gt(a, j, votHh, toll) + gt(j, b, votHh, toll) - gAB) : gt(a, j, votHh, toll); break;
                    case T_LS: x = s.stop ? logsum(mp, a, j) + logsum(mp, j, b) - lsAB : logsum(mp, a, j); break;
                    case T_LSTOUR: x = s.stop ? MarylandTourNestedModeChoice.logsum(lseg, lpa, zoneIds[a], zoneIds[j], lper, lper, lstops, 0, lacc, lrec)
                            + MarylandTourNestedModeChoice.logsum(lseg, lpa, zoneIds[j], zoneIds[b], lper, lper, lstops, 0, lacc, lrec) - ltAB
                            : MarylandTourNestedModeChoice.logsum(lseg, lpa, zoneIds[a], zoneIds[j], lper, lper, lstops, 0, lacc, lrec); break;
                    case T_INTRA: case T_INTRA_A: x = j == a ? 1 : 0; break;
                    case T_INTRA_B: x = j == b ? 1 : 0; break;
                    case T_XCOUNTY: x = (zCounty[j] != zCounty[a] && (!s.stop || zCounty[j] != zCounty[b])) ? 1 : 0; break;
                    case T_XSTATE: x = (zState[j] != zState[a] && (!s.stop || zState[j] != zState[b])) ? 1 : 0; break;
                    case T_PTAV_CAR0: x = (mBus[a * n + j] < 120 ? 1 : 0) * fl[2]; break;
                    case T_PTAV: x = mBus[a * n + j] < 120 ? 1 : 0; break;
                    default: x = 0;   // T_ZONE: in u0
                }
                if (s.type[k] != T_ZONE) u += s.beta[k] * x;
            }
            V[j] = u; if (u > mx) mx = u;
        }
        if (debugFile != null && (debugSegs == null || debugSegs.contains(s.key))
                && (debugPerSeg ? debugBySeg.computeIfAbsent(s.key, k -> new java.util.concurrent.atomic.AtomicInteger()).getAndIncrement() < debugN
                                : (s.stop ? debugCountStop : debugCount).getAndIncrement() < 30)) {
            synchronized (MarylandDestinationChoice.class) {
                try (java.io.PrintWriter pw = new java.io.PrintWriter(new java.io.FileWriter(debugFile, true))) {
                    for (int j = 0; j < n; j++) pw.println(s.key + "," + person.getId() + "," + zoneIds[a] + "," + (b >= 0 ? zoneIds[b] : -1) + "," + startMin + ","
                            + (tourMode == null ? "" : tourMode) + "," + inbound + "," + (tour == null ? "" : tour.getMainActivity().getPurpose()) + "," + zoneIds[j] + "," + V[j]
                            + (debugPerSeg ? "," + fl[11] + "," + fl[12] + "," + fl[13] + "," + fl[14] : ""));
                } catch (Exception ignored) { }
            }
        }
        double tot = 0; for (int j = 0; j < n; j++) { V[j] = Math.exp(V[j] - mx); tot += V[j]; }
        double uu = r.nextDouble() * tot, c = 0;
        for (int j = 0; j < n; j++) { c += V[j]; if (uu <= c) return j; }
        return n - 1;
    }

    /** true when the coefficient file has the segment (e.g. WORK_wbwork, EDUCATION_nonstud of the TASHA generator, 2026-10-23). */
    public static boolean hasSegment(String key) { return mnlActive() && mnl.containsKey(key); }

    /** Zone from the estimated MNL of an anchored segment (TASHA generator, 2026-10-23: work business from the usual workplace or
     *  from home, work-at-home business, school of persons without a school record, daycare): the utility of the primary form
     *  with the anchor in place of home (impedance = car distance from the anchor; intra = the anchor zone; xcounty / xstate
     *  relative to the anchor).  The location is the zone centroid. */
    public MicroscopicLocation selectAnchoredZoneMnl(String key, Person person, Location anchor, int startMin, Random r) {
        MnlSegment s = mnl.get(key);
        int sel = chooseMnl(s, person, idxOf(anchor.getZoneId()), -1, startMin, null, null, false, r);
        MicroscopicLocation l = new MicroscopicLocation(zoneLoc[sel].getX(), zoneLoc[sel].getY()); l.setZone(zones.get(sel));
        return l;
    }

    /** true when the coefficient file has the sequential stop model of the purpose (<PURPOSE>_seq_stop, 2026-10-23) */
    public static boolean hasSeqStopModel(Purpose p) { return mnlActive() && mnl.containsKey(p + "_seq_stop"); }

    /** Stop zone from the sequential stop MNL (TASHA generator, 2026-10-23): anchors a = the location the person comes from (home,
     *  the main activity or the previous stop), b = the next anchor (the main activity outbound, home inbound); tour flags as
     *  selectStopZoneMnl. */
    public MicroscopicLocation selectSeqStopZoneMnl(Person person, Tour tour, Purpose stopPurpose, boolean outbound, Location a, Location b, Random r) {
        MnlSegment s = mnl.get(stopPurpose + "_seq_stop");
        int sel = chooseMnl(s, person, idxOf(a.getZoneId()), idxOf(b.getZoneId()), tour.getMainActivity().getStartTime_min(), tour, tour.getTourMode(), !outbound, r);
        MicroscopicLocation l = new MicroscopicLocation(zoneLoc[sel].getX(), zoneLoc[sel].getY()); l.setZone(zones.get(sel));
        return l;
    }

    /** Primary destination from the estimated MNL with the tour-complexity flag set (TASHA generator, 2026-10-23: the main
     *  discretionary episode of a chain with stops is relocated once the chains are formed). */
    public MicroscopicLocation selectPrimaryZoneMnl(Person person, Purpose purpose, int startMin, boolean multi, Random r) {
        MnlSegment s = mnl.get(purpose + "_primary");
        double[] fl = flags(person, startMin, null, null, false); fl[14] = multi ? 1 : 0;
        int sel = chooseMnl(s, person, idxOf(person.getHousehold().getLocation().getZoneId()), -1, startMin, null, null, false, r, fl);
        MicroscopicLocation l = new MicroscopicLocation(zoneLoc[sel].getX(), zoneLoc[sel].getY()); l.setZone(zones.get(sel));
        return l;
    }

    /** true when the primary MNL of the purpose has a tour-complexity term */
    public static boolean hasMultiTerm(Purpose p) {
        MnlSegment s = mnl.get(p + "_primary"); if (s == null) return false;
        for (int k = 0; k < s.type.length; k++) if (s.type[k] == T_LNX && s.arg[k] == 14) return true;
        return false;
    }

    /** Zone from the estimated MNL of a two-anchor segment (stop form without a tour; TASHA generator, 2026-10-23: work business of
     *  a worker with a usual workplace, anchors home and workplace): impedance = detour via the zone between the two anchors. */
    public MicroscopicLocation selectTwoAnchorZoneMnl(String key, Person person, Location a, Location b, int startMin, Random r) {
        MnlSegment s = mnl.get(key);
        int sel = chooseMnl(s, person, idxOf(a.getZoneId()), idxOf(b.getZoneId()), startMin, null, null, false, r);
        MicroscopicLocation l = new MicroscopicLocation(zoneLoc[sel].getX(), zoneLoc[sel].getY()); l.setZone(zones.get(sel));
        return l;
    }

    /** Stop zone from the estimated stop MNL before the tour object exists (TASHA generator, 2026-10-23: a joint episode that is
     *  not the main activity of its chain is relocated at the household level): anchors home and the main activity; flags of the
     *  tour as the stop model reads them, with the tour mode taken as car (the mode is chosen after the locations). */
    public MicroscopicLocation selectStopZoneMnl(Person person, Purpose stopPurpose, boolean outbound, Location home, Location main, int mainStartMin, Purpose mainPurpose, Random r) {
        MnlSegment s = mnl.get(stopPurpose + "_stop");
        double[] fl = flags(person, mainStartMin, null, null, !outbound);
        fl[11] = 0; fl[12] = (mainPurpose == Purpose.WORK || mainPurpose == Purpose.EDUCATION) ? 1 : 0; fl[13] = outbound ? 0 : 1;
        int sel = chooseMnl(s, person, idxOf(home.getZoneId()), idxOf(main.getZoneId()), mainStartMin, null, null, !outbound, r, fl);
        MicroscopicLocation l = new MicroscopicLocation(zoneLoc[sel].getX(), zoneLoc[sel].getY()); l.setZone(zones.get(sel));
        return l;
    }

    /** Stop zone from the estimated MNL (MarylandStopModel, when hasStopModel(purpose)): anchors = home and the primary
     *  destination of the tour; the stop location is the zone centroid (the convention of the corridor rule). */
    public MicroscopicLocation selectStopZoneMnl(Person person, Tour tour, Purpose stopPurpose, boolean outbound, Location home, Location main, Random r) {
        MnlSegment s = mnl.get(stopPurpose + "_stop");
        int sel = chooseMnl(s, person, idxOf(home.getZoneId()), idxOf(main.getZoneId()), tour.getMainActivity().getStartTime_min(), tour, tour.getTourMode(), !outbound, r);
        MicroscopicLocation l = new MicroscopicLocation(zoneLoc[sel].getX(), zoneLoc[sel].getY()); l.setZone(zones.get(sel));
        return l;
    }
}
