package abm.models.maryland;

import abm.data.DataSet;
import abm.data.plans.*;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.models.modeChoice.TourModeChoice;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;
import de.tum.bgu.msm.data.person.Gender;
import org.apache.log4j.Logger;

import java.io.*;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.channels.FileChannel;
import java.util.*;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.atomic.AtomicLong;
import java.util.zip.GZIPInputStream;

/**
 * Tour mode choice in the specification of Chayan &amp; Cirillo (2024), re-estimated as a tour model on the estimation half of the
 * 2017/18 Regional Travel Survey (Validation_2026/3_abit/mode_choice/estimate_gc.py, Biogeme).  One model per tour segment (work,
 * school, shopping, other), multinomial or nested logit (nests auto = car driver + car passenger, transit = bus + train,
 * non-motorised = walk + bike; Biogeme's nest parameter mu &gt;= 1; a segment without mu_* parameters is an MNL).
 *
 * <p>Modes CD (car driver, reference), WK, BK, CP (car passenger, shared ride folded in), BUS, TRAIN.  Utility of mode m:
 * <pre>
 *   V_m = ASC_m + b_age,m age + b_male,m male + b_lic,m licence + b_hhsize,m hhsize + b_autos,m autos
 *         + b_core_o,m core(home) + b_rural_o,m rural(home) [+ b_core_d,m core(main) + b_rural_d,m rural(main)]
 *         + b_gc(,m) GC_m + b_km,m km                      (socio, area and km terms on the non-reference modes)
 *   GC_m = T_m + 60 C_m / VOT_h (minutes),  VOT_h = s x household income / 2,080 h  (USDOT 2016 guidance, local personal travel:
 *          s = 0.5 of the hourly household income; property mc.vot.share), income floor $5,000 / yr
 * </pre>
 * Round trip: outbound home -&gt; main activity in the period of the main activity's start, return in the period of its end (AM 6-9,
 * MD 9-15, PM 15-19, NT 19-6).  T, C: CD car minutes, km x 0.1112 $/km (AAA 2017) + toll; CP car minutes, 0; BUS door-to-door
 * minutes of the bus-only schedule and the fare; TRAIN door-to-door minutes of the full-schedule path when it uses rail (walk
 * access, else drive access with the car operating cost of the access leg) and the fare; a half without a raptor path takes the
 * regional (MSTM) bus / rail skim when it has one; WK, BK no GC.  Fares (2017): MTA $1.80; WMATA Metrorail $2.25-$6.00 peak,
 * $2.00-$3.85 off-peak by distance, Metrobus $2.00 (both ends in the Washington region); MARC min(8, 4 + km/15) for rail paths over
 * 30 km.  Matrices: {@code mc.los.dir} (3_abit/mode_choice/export_mc.py).
 *
 * <p>Availability: CD with a licence, age 16+ and a household car; CP always; BUS / TRAIN when both halves have a path; walk up to
 * 12 km and bike up to 50 km round trip.  All legs of the tour (its stops) take the tour mode.  Household stage
 * ({@link #resolveHousehold}): joint tours travel together (one mode from the summed utilities, one driver), then the household's
 * cars are allocated to overlapping car-driver tours by their utility advantage; within-household ride sharing is not modelled.
 *
 * <p>Re-specified models (2026-11-09, side_experiments/respec_2026-11/step_by_step/mode_choice m08_sequence.py / m09_school.py,
 * coefficient set 3_abit/coef_respec): terms switched on only by their keys in the coefficient file, so a file without them
 * (coef_tasha) gives the earlier utilities unchanged:
 * <pre>
 *   time, cost      generic minutes and $ of CD, CP, BUS, TRAIN (time + cost form: T_m and C_m of GC_m above, toll in C_CD)
 *   kids_m          household with a person under 18 (prep_dc_data.people: children = persons under 18)
 *   park_CD         paid-parking share of the main-activity zone's area (prep_tours.park_area: 0 Baltimore City CBD, 1 other
 *                   Baltimore City, 2 DC CBD, 3 other DC, 4 other CBD zone, 5 elsewhere; CBD = at least 10,000 jobs per km2 of the
 *                   run's job file; shares of property mc.park.share.file, park_area,share)
 *   stops_CD        tour with at least one stop besides the main activity
 * </pre>
 * {@link #logsum} gives the logsum of these models for a round trip between two zones (stop and location models of the same set,
 * variable {@code lstour} of MarylandDestinationChoice).
 *
 * <p>Properties: {@code mode.choice.model = tour_nl}, {@code mc.coef.file} (segment,parameter,value), {@code mc.los.dir},
 * {@code mc.vot.share} (0.5), {@code mc.asc.adjust} (segment,alt,delta: calibrated variant only), {@code mc.toll.file}
 * (FROM,TO,VALUE $ per car-driver half-tour, gzipped CSV), {@code mc.tours.out}.  Toll hook {@link #setToll(double)}: $ per
 * car-driver half-tour, added to C_CD.
 */
public class MarylandTourNestedModeChoice implements TourModeChoice {

    private static final Logger logger = Logger.getLogger(MarylandTourNestedModeChoice.class);
    static final String[] ALT = {"CD", "WK", "BK", "CP", "BUS", "TRAIN"};
    static final int CD = 0, WK = 1, BK = 2, CP = 3, BUS = 4, TRAIN = 5;
    static final String[] PER = {"AM", "MD", "PM", "NT"};
    static final String[] NEST_NAME = {"auto", "transit", "nonmot"};
    static final int[] NEST_OF = {0, 2, 2, 0, 1, 1};
    static final double OPC_KM = 0.179 / 1.60934, FARE_MTA = 1.80, INC_FLOOR = 5000.0, HOURS = 2080.0, DRIVE_KMH = 25.0;
    static final double WALK_MAX = 12.0, BIKE_MAX = 50.0;
    static final String[] SOCIO = {"age", "male", "lic", "hhsize", "autos", "core_o", "rural_o", "core_d", "rural_d", "joint", "short", "acc", "rec",
            "kids", "park", "stops"};   // kids, park, stops: re-specified models (2026-11-09)
    /** household-structure terms (2026-11-02, mode_choice/estimate_hh.py): joint = main activity a joint household episode, short =
     *  fewer cars than licensed drivers (at least one car), acc / rec = accompanying / recreation tour of the 'other' segment.
     *  joint and short are estimation controls applied as 0 (property mc.zero.terms): the household stage produces the joint
     *  tours' passengers and the car shortages explicitly, so applying them as well would count them twice. */
    private static final Set<String> zeroTerms = new HashSet<>(Arrays.asList("joint", "short"));

    private static boolean loaded = false;
    private static int n;
    private static final Map<Integer, Integer> zIdx = new HashMap<>();
    private static int[] bbsr; private static boolean[] wmata;
    private static float[] dist, priorBus, priorTrain;
    private static final float[][] carT = new float[4][], wBus = new float[4][], wAll = new float[4][], wRail = new float[4][], dAll = new float[4][], dRail = new float[4][], dAcc = new float[4][];
    private static final Map<String, Map<String, Double>> coef = new HashMap<>();
    private static final Map<String, double[]> ascAdj = new HashMap<>();
    private static float[] tollOd = null;
    private static volatile double tollUsd = 0.0;
    private static double votShare = 0.5;
    private static boolean toursOut = false, toursFull = false, applyShort = false, applyJoint = false, cdEstimation = false;
    /** paid-parking share by LOS zone index (mc.park.share.file; null without the property) */
    private static double[] parkZone = null;
    /** coefficients of a segment in arrays (index = ALT, SOCIO); absent terms are flagged, so they add nothing */
    static final class Cf {
        final double[] asc = new double[6], km = new double[6], gc = new double[6]; final double[][] so = new double[6][SOCIO.length];
        final boolean[][] has = new boolean[6][SOCIO.length]; double time, cost; boolean hasTime, hasCost, nested; final double[] mu = {1, 1, 1}; final boolean[] hasAsc = new boolean[6];
        Cf(Map<String, Double> b) {
            for (int a = 0; a < 6; a++) {
                asc[a] = b.getOrDefault("ASC_" + ALT[a], 0.0); km[a] = b.getOrDefault("km_" + ALT[a], 0.0); gc[a] = b.getOrDefault("gc_" + ALT[a], b.getOrDefault("gc", 0.0));
                for (int s = 0; s < SOCIO.length; s++) { Double c = b.get(SOCIO[s] + "_" + ALT[a]); if (c != null) { so[a][s] = c; has[a][s] = true; } }
            }
            hasTime = b.containsKey("time"); time = b.getOrDefault("time", 0.0); hasCost = b.containsKey("cost"); cost = b.getOrDefault("cost", 0.0);
            nested = b.containsKey("mu_auto") || b.containsKey("mu_transit") || b.containsKey("mu_nonmot");
            for (int a = 0; a < 6; a++) hasAsc[a] = b.containsKey("ASC_" + ALT[a]);
            for (int k = 0; k < 3; k++) mu[k] = b.getOrDefault("mu_" + NEST_NAME[k], 1.0);
        }
    }
    private static final Map<String, Cf> cf = new HashMap<>();
    private static final ConcurrentLinkedQueue<String> tourLines = new ConcurrentLinkedQueue<>();
    private static final AtomicLong nTours = new AtomicLong(), nJointGroups = new AtomicLong(), nJointTours = new AtomicLong(), nCdTours = new AtomicLong(),
            nRealloc = new AtomicLong(), nHhConflict = new AtomicLong(), nHh = new AtomicLong();

    private final Random rnd = AbitUtils.getRandomObject();

    public MarylandTourNestedModeChoice(DataSet dataSet) {
        synchronized (MarylandTourNestedModeChoice.class) { if (!loaded) { load(); loaded = true; } if (parkZone == null) loadPark(dataSet); }
    }

    /** the LOS matrices and coefficients without a mode-choice object (MarylandDestinationChoice, variable lstour) */
    static synchronized void ensureLoaded(DataSet dataSet) { if (!loaded) { load(); loaded = true; } if (parkZone == null) loadPark(dataSet); }

    /** paid-parking share of every LOS zone (property mc.park.share.file: park_area,share; area class of prep_tours.park_area from
     *  the zone's county (zone.attributes.file) and its jobs per km2 (jj.retail + jj.office + jj.other of the run, area at least
     *  0.05 km2, as MarylandDestinationChoice's cbd) */
    private static void loadPark(DataSet dataSet) {
        String pf = AbitResources.instance.getString("mc.park.share.file");
        if (pf == null || pf.trim().isEmpty()) return;
        double[] share = new double[6];
        for (String[] r : csv(pf.trim())) share[Integer.parseInt(r[0].trim())] = Double.parseDouble(r[1].trim());
        Map<Integer, Integer> county = new HashMap<>();
        String zf = AbitResources.instance.getString("zone.attributes.file");
        try (BufferedReader br = new BufferedReader(new FileReader(zf))) {
            String[] h = br.readLine().split(","); int iId = -1, iC = -1;
            for (int i = 0; i < h.length; i++) { if (h[i].trim().equals("id")) iId = i; if (h[i].trim().equals("countyfips")) iC = i; }
            String l; while ((l = br.readLine()) != null) { String[] r = l.split(","); county.put(Integer.parseInt(r[iId].trim()), Integer.parseInt(r[iC].trim())); }
        } catch (IOException e) { throw new RuntimeException("mode choice parking: zone.attributes.file " + zf, e); }
        double[] pz = new double[n]; int[] nArea = new int[6];
        for (Map.Entry<Integer, Integer> e : zIdx.entrySet()) {
            abm.data.geo.Zone z = dataSet.getZones().get(e.getKey()); int i = e.getValue(), area = 5;
            if (z != null) {
                double jobs = 0; for (String k : new String[]{"jj.retail", "jj.office", "jj.other"}) jobs += z.getAttribute(k).map(o -> ((Number) o).doubleValue()).orElse(0.0);
                boolean cbd = jobs / Math.max(z.getAreaKm2(), 0.05) >= 10000; int c = county.getOrDefault(e.getKey(), 0);
                area = c == 24510 ? (cbd ? 0 : 1) : c == 11001 ? (cbd ? 2 : 3) : cbd ? 4 : 5;
            }
            pz[i] = share[area]; nArea[area]++;
        }
        parkZone = pz;
        logger.info("Tour mode choice: paid-parking shares " + Arrays.toString(share) + " by area class; zones per class " + Arrays.toString(nArea));
    }

    public static void setToll(double usdPerHalfTour) { tollUsd = usdPerHalfTour; }

    // ------------------------------------------------------------------------------------------------ input
    private static float[] mat(String dir, String name) {
        File f = new File(dir, name + ".f32");
        try (FileChannel ch = new FileInputStream(f).getChannel()) {
            ByteBuffer b = ByteBuffer.allocate((int) ch.size()).order(ByteOrder.LITTLE_ENDIAN);
            while (b.hasRemaining()) if (ch.read(b) < 0) break;
            b.flip(); float[] a = new float[n * n]; b.asFloatBuffer().get(a);
            return a;
        } catch (IOException e) { throw new RuntimeException("mode choice LOS " + f, e); }
    }

    private static List<String[]> csv(String f) {
        List<String[]> rows = new ArrayList<>();
        try (BufferedReader br = new BufferedReader(new FileReader(f))) { br.readLine(); String l; while ((l = br.readLine()) != null) if (!l.trim().isEmpty()) rows.add(l.split(",")); }
        catch (IOException e) { throw new RuntimeException("mode choice input " + f, e); }
        return rows;
    }

    private static void load() {
        String dir = AbitResources.instance.getString("mc.los.dir");
        List<String[]> zr = csv(new File(dir, "zones.csv").getPath());
        n = zr.size(); bbsr = new int[n]; wmata = new boolean[n];
        for (String[] r : zr) { int i = Integer.parseInt(r[0]); zIdx.put(Integer.parseInt(r[1]), i); bbsr[i] = Integer.parseInt(r[2]); wmata[i] = Integer.parseInt(r[3]) == 1; }
        dist = mat(dir, "dist"); priorBus = mat(dir, "prior_bus"); priorTrain = mat(dir, "prior_train");
        for (int p = 0; p < 4; p++) {
            carT[p] = mat(dir, "car_" + PER[p]);
            wBus[p] = mat(dir, "walk_" + PER[p] + "_bus"); wAll[p] = mat(dir, "walk_" + PER[p] + "_all"); wRail[p] = mat(dir, "walk_" + PER[p] + "_rail");
            dAll[p] = mat(dir, "drive_" + PER[p] + "_all"); dRail[p] = mat(dir, "drive_" + PER[p] + "_rail"); dAcc[p] = mat(dir, "drive_" + PER[p] + "_acc");
        }
        for (String[] r : csv(AbitResources.instance.getString("mc.coef.file"))) coef.computeIfAbsent(r[0].trim(), k -> new HashMap<>()).put(r[1].trim(), Double.parseDouble(r[2].trim()));
        String vs = AbitResources.instance.getString("mc.vot.share"); if (vs != null && !vs.trim().isEmpty()) votShare = Double.parseDouble(vs.trim());
        String af = AbitResources.instance.getString("mc.asc.adjust");
        if (af != null && !af.trim().isEmpty()) {
            for (String[] r : csv(af.trim())) { int a = Arrays.asList(ALT).indexOf(r[1].trim()); if (a >= 0) ascAdj.computeIfAbsent(r[0].trim(), k -> new double[6])[a] += Double.parseDouble(r[2].trim()); }
            logger.info("Tour mode choice: ASC adjustments of the calibrated variant from " + af);
        }
        String tf = AbitResources.instance.getString("mc.toll.file");
        if (tf != null && !tf.trim().isEmpty()) {
            tollOd = new float[n * n];
            try (BufferedReader br = new BufferedReader(new InputStreamReader(new GZIPInputStream(new FileInputStream(tf.trim()))))) {
                br.readLine(); String l;
                while ((l = br.readLine()) != null) {
                    String[] r = l.split(","); Integer i = zIdx.get(Integer.parseInt(r[0])), j = zIdx.get(Integer.parseInt(r[1]));
                    if (i != null && j != null) tollOd[i * n + j] = Float.parseFloat(r[2]);
                }
            } catch (IOException e) { throw new RuntimeException("mode choice toll file " + tf, e); }
        }
        for (Map.Entry<String, Map<String, Double>> e : coef.entrySet()) cf.put(e.getKey(), new Cf(e.getValue()));
        toursOut = Boolean.parseBoolean(AbitResources.instance.getString("mc.tours.out"));
        toursFull = Boolean.parseBoolean(AbitResources.instance.getString("mc.tours.full"));
        String zt = AbitResources.instance.getString("mc.zero.terms");
        if (zt != null) { zeroTerms.clear(); for (String t : zt.split("[;,]")) if (!t.trim().isEmpty()) zeroTerms.add(t.trim()); }
        // 2026-11-09 (author's choice for coef_respec): mc.apply.short = true applies 'fewer cars than drivers' as estimated;
        // mc.apply.joint = true applies 'joint' as estimated to the tours whose main activity is a joint household episode (known at
        // the household stage, resolveHousehold); mc.cd.availability = estimation: car driver available by the estimation rule only
        // (licence, age 16+, a household car), the household stage does not take cars away from overlapping car-driver tours (the
        // overlaps beyond the car count are only counted, mc_summary.csv)
        applyShort = Boolean.parseBoolean(AbitResources.instance.getString("mc.apply.short"));
        applyJoint = Boolean.parseBoolean(AbitResources.instance.getString("mc.apply.joint"));
        String ca = AbitResources.instance.getString("mc.cd.availability"); cdEstimation = ca != null && ca.trim().equalsIgnoreCase("estimation");
        if (applyShort) zeroTerms.remove("short");
        String jmo = AbitResources.instance.getString("mc.joint.model"); jointGroupModel = jmo != null && jmo.trim().equalsIgnoreCase("group");
        String jr = AbitResources.instance.getString("mc.joint.rule"); jointRep = jr != null && jr.trim().equalsIgnoreCase("representative");
        String jd = AbitResources.instance.getString("mc.joint.driver"); jointDriverHH = jd != null && jd.trim().equalsIgnoreCase("household");
        String al = AbitResources.instance.getString("mc.car.allocation"); tashaAlloc = al != null && al.trim().equalsIgnoreCase("tasha");
        String em = AbitResources.instance.getString("mc.car.allocation.exhaustive.max"); if (em != null && !em.trim().isEmpty()) exhaustiveMax = Integer.parseInt(em.trim());
        if (applyJoint) zeroTerms.remove("joint");
        logger.info("Tour mode choice (estimated, GC form, VOT share " + votShare + "): " + n + " zones, segments " + coef.keySet());
    }

    static String segment(Purpose p) {
        switch (p) { case WORK: return "work"; case EDUCATION: return "school"; case SHOPPING: return "shopping"; default: return "other"; }
    }

    static int period(int minute) {
        int h = ((minute % 1440) + 1440) % 1440 / 60;
        return h >= 6 && h < 9 ? 0 : h >= 9 && h < 15 ? 1 : h >= 15 && h < 19 ? 2 : 3;
    }

    /** one-way fare (2017 $), mc_common.fare_rule */
    static double fare(double rail, double km, int o, int d, boolean peak) {
        if (rail >= 0.5 && km > 30.0) return Math.min(8.0, 4.0 + km / 15.0);
        if (wmata[o] && wmata[d]) {
            if (rail < 0.5) return 2.00;
            double x = Math.max(0.0, Math.min(1.0, (km / 1.60934 - 3.0) / 12.0));
            return peak ? 2.25 + x * (6.00 - 2.25) : 2.00 + x * (3.85 - 2.00);
        }
        return FARE_MTA;
    }

    /** level of service of one leg (2026-11-03, MarylandTashaGenerator transit leg modes; the same matrices and rules as
     *  3_abit/tasha_estimation/estimate_transit_legs.leg_los): {car-distance km, transit minutes with walk access (bus tour: the
     *  bus-only schedule, else the rail path; train tour: the rail path, else the bus-only schedule; the regional prior where the
     *  period skim has no path; NaN without a path or for an intrazonal leg), period index}; null when the matrices are not loaded
     *  or a zone is outside them */
    static double[] legLos(int oZone, int dZone, int minute, boolean rail) {
        if (!loaded) return null;
        Integer oi = zIdx.get(oZone), di = zIdx.get(dZone);
        if (oi == null || di == null) return null;
        int k = oi * n + di, p = period(minute);
        double tb = wBus[p][k]; if (Double.isNaN(tb)) tb = priorBus[k];
        double tr = wRail[p][k] >= 0.5 ? wAll[p][k] : Double.NaN; if (Double.isNaN(tr)) tr = priorTrain[k];
        double t = rail ? (Double.isNaN(tr) ? tb : tr) : (Double.isNaN(tb) ? tr : tb);
        if (oi.intValue() == di.intValue()) t = Double.NaN;
        return new double[]{dist[k], t, p};
    }

    /** zone in the Washington region (WMATA counties of the LOS zone table) */
    static boolean washington(int zone) { Integer i = zIdx.get(zone); return i != null && wmata[i]; }

    // ------------------------------------------------------------------------------------------------ utilities
    static final class Eval { double[] v = new double[6]; boolean[] av = new boolean[6]; double[] p = new double[6]; double km; String seg; int window0, window1;
        double[] gc, T, C, x; }   // kept for the group model of joint tours (mc.joint.model = group)

    /** round-trip level of service home h -> main m (LOS indices), outbound period po, return period pr:
     *  {car minutes, km, bus ok (1/0), bus minutes, bus $, train ok, train minutes, train $} */
    static double[] los(int h, int m, int po, int pr) {
        double carMin = carT[po][h * n + m] + carT[pr][m * n + h], km = dist[h * n + m] + dist[m * n + h];
        double busT = 0, busC = 0, trT = 0, trC = 0; boolean busOk = h != m, trOk = h != m;
        int[][] halves = {{h, m, po}, {m, h, pr}};
        for (int[] hv : halves) {
            int a = hv[0], b = hv[1], p = hv[2], k = a * n + b, kh = h * n + m; boolean peak = p == 0 || p == 2; double kmh = dist[k];
            double tb = wBus[p][k]; if (Double.isNaN(tb)) tb = priorBus[k];
            if (Double.isNaN(tb)) busOk = false; else { busT += tb; busC += fare(0.0, kmh, a, b, peak); }
            double tt = wRail[p][k] >= 0.5 ? wAll[p][k] : Double.NaN, cc = 0;
            if (Double.isNaN(tt) && dRail[p][kh] >= 0.5 && !Double.isNaN(dAll[p][kh])) { tt = dAll[p][kh]; cc = dAcc[p][kh] / 60.0 * DRIVE_KMH * OPC_KM; }
            if (Double.isNaN(tt)) tt = priorTrain[k];
            if (Double.isNaN(tt)) trOk = false; else { trT += tt; trC += fare(1.0, kmh, a, b, peak) + cc; }
        }
        return new double[]{carMin, km, busOk ? 1 : 0, busT, busC, trOk ? 1 : 0, trT, trC};
    }

    /** utilities of the six modes: ASC, km, GC (or time + cost) and the SOCIO terms present in the segment's coefficients */
    static void utilities(Cf c, double[] adj, double km, double[] gc, double[] T, double[] C, double[] x, double[] v) {
        for (int a = 0; a < 6; a++) {
            double u = c.asc[a] + (adj != null ? adj[a] : 0.0) + c.km[a] * km;
            if (a == CD || a == CP || a == BUS || a == TRAIN) {
                u += c.gc[a] * gc[a];
                if (c.hasTime) u += c.time * T[a];
                if (c.hasCost) u += c.cost * C[a];
            }
            for (int s = 0; s < SOCIO.length; s++) if (c.has[a][s]) u += c.so[a][s] * x[s];
            v[a] = u;
        }
    }

    /** person and household attributes of the tour models: SOCIO values that do not depend on the zones or the tour, VOT, car-driver availability */
    static final class PA { final double[] x = new double[SOCIO.length]; double vot; boolean cd; }

    static PA personAttrs(Person person) {
        Household hh = person.getHousehold(); PA pa = new PA();
        int drivers = 0; double incM = 0; boolean u18 = false;
        for (Person q : hh.getPersons()) { if (q.isHasLicense()) drivers++; incM += q.getMonthlyIncome_eur(); if (q.getAge() < 18) u18 = true; }
        int cars = hh.getNumberOfCars(), age = person.getAge();
        pa.vot = votShare * Math.max(12.0 * incM, INC_FLOOR) / HOURS;
        pa.x[0] = age; pa.x[1] = person.getGender() == Gender.MALE ? 1.0 : 0.0; pa.x[2] = person.isHasLicense() ? 1.0 : 0.0;
        pa.x[3] = hh.getPersons().size(); pa.x[4] = cars; pa.x[10] = cars > 0 && cars < drivers ? 1.0 : 0.0; pa.x[13] = u18 ? 1.0 : 0.0;
        pa.cd = person.isHasLicense() && cars > 0 && age >= 16;
        return pa;
    }

    /** segment of the re-specified tour models for a destination purpose (mode_logsum_new.MODEL_OF) */
    static String logsumSegment(Purpose p) { return segment(p); }

    /**
     * Logsum of the tour model of segment seg (re-specified models, 2026-11-09; mode_logsum_new.mode_logsum_new) for a round trip
     * from zone hZone to zone mZone, outbound period po and return period pr (0 AM, 1 MD, 2 PM, 3 NT): ln sum_m exp(V_m), nested
     * models in Biogeme's form ln sum_k exp((1/mu_k) ln sum_{m in k} exp(mu_k V_m)).  The person terms from pa, the tour terms
     * stops, joint, acc, rec as given (the estimation of the stop models: stops = 1, joint = 0), 'short' as estimated (not the
     * zero terms of the mode choice, which the household stage replaces), no ASC adjustment.  NaN when a zone is outside the LOS
     * zones.
     */
    static double logsum(String seg, PA pa, int hZone, int mZone, int po, int pr, double stops, double joint, double acc, double rec) {
        Integer hi = zIdx.get(hZone), mi = zIdx.get(mZone);
        if (hi == null || mi == null) return Double.NaN;
        int h = hi, m = mi; Cf c = cf.get(seg);
        double[] L = los(h, m, po, pr); double km = L[1];
        double[] T = {L[0], 0, 0, L[0], L[2] > 0 ? L[3] : 0, L[5] > 0 ? L[6] : 0}, C = {km * OPC_KM + 2 * tollUsd + (tollOd != null ? tollOd[h * n + m] + tollOd[m * n + h] : 0.0), 0, 0, 0, L[2] > 0 ? L[4] : 0, L[5] > 0 ? L[7] : 0};
        double[] gc = new double[6];
        gc[CD] = T[CD] + 60.0 * C[CD] / pa.vot; gc[CP] = T[CP]; gc[BUS] = L[2] > 0 ? T[BUS] + 60.0 * C[BUS] / pa.vot : 0; gc[TRAIN] = L[5] > 0 ? T[TRAIN] + 60.0 * C[TRAIN] / pa.vot : 0;
        double[] x = pa.x.clone();
        x[5] = bbsr[h] == 10 ? 1.0 : 0.0; x[6] = bbsr[h] == 40 ? 1.0 : 0.0; x[7] = bbsr[m] == 10 ? 1.0 : 0.0; x[8] = bbsr[m] == 40 ? 1.0 : 0.0;
        x[9] = joint; x[11] = acc; x[12] = rec; x[14] = parkZone != null ? parkZone[m] : 0.0; x[15] = stops;
        boolean[] av = {pa.cd, km <= WALK_MAX, km <= BIKE_MAX, true, L[2] > 0, L[5] > 0};
        double[] v = new double[6]; utilities(c, null, km, gc, T, C, x, v);
        double vmax = Double.NEGATIVE_INFINITY; for (int a = 0; a < 6; a++) if (av[a]) vmax = Math.max(vmax, v[a]);
        if (!c.nested) { double s = 0; for (int a = 0; a < 6; a++) if (av[a]) s += Math.exp(v[a] - vmax); return vmax + Math.log(s); }
        double[] sum = new double[3]; boolean[] has = new boolean[3];
        for (int a = 0; a < 6; a++) if (av[a]) { int k = NEST_OF[a]; sum[k] += Math.exp(c.mu[k] * (v[a] - vmax)); has[k] = true; }
        double den = 0; for (int k = 0; k < 3; k++) if (has[k]) den += Math.exp(Math.log(sum[k]) / c.mu[k]);
        return vmax + Math.log(den);
    }

    Eval evaluate(Person person, Tour tour) {
        Activity main = tour.getMainActivity(); Household hh = person.getHousehold();
        Integer hi = zIdx.get(hh.getLocation().getZoneId()), mi = zIdx.get(main.getLocation().getZoneId());
        Eval e = new Eval(); e.seg = segment(main.getPurpose());
        if (hi == null || mi == null) { e.av[CP] = true; e.p[CP] = 1; e.window0 = main.getStartTime_min(); e.window1 = main.getEndTime_min(); return e; }
        int h = hi, m = mi, po = period(main.getStartTime_min()), pr = period(main.getEndTime_min());
        double[] L = los(h, m, po, pr);
        double carMin = L[0], km = L[1]; e.km = km;
        boolean busOk = L[2] > 0, trOk = L[5] > 0; double busT = L[3], busC = L[4], trT = L[6], trC = L[7];
        PA pa = personAttrs(person); double vot = pa.vot; int age = person.getAge();
        double toll = 2 * tollUsd + (tollOd != null ? tollOd[h * n + m] + tollOd[m * n + h] : 0.0);
        double[] gc = new double[6], T = new double[6], C = new double[6];
        gc[CD] = carMin + 60.0 * (km * OPC_KM + toll) / vot; gc[CP] = carMin;
        gc[BUS] = busOk ? busT + 60.0 * busC / vot : 0; gc[TRAIN] = trOk ? trT + 60.0 * trC / vot : 0;
        T[CD] = carMin; C[CD] = km * OPC_KM + toll; T[CP] = carMin; T[BUS] = busOk ? busT : 0; C[BUS] = busOk ? busC : 0; T[TRAIN] = trOk ? trT : 0; C[TRAIN] = trOk ? trC : 0;
        double[] x = pa.x.clone();
        Purpose mp = main.getPurpose();
        x[9] = 0.0; x[11] = mp == Purpose.ACCOMPANY ? 1.0 : 0.0; x[12] = mp == Purpose.RECREATION ? 1.0 : 0.0;
        x[5] = bbsr[h] == 10 ? 1.0 : 0.0; x[6] = bbsr[h] == 40 ? 1.0 : 0.0; x[7] = bbsr[m] == 10 ? 1.0 : 0.0; x[8] = bbsr[m] == 40 ? 1.0 : 0.0;
        x[14] = parkZone != null ? parkZone[m] : 0.0; x[15] = tour.getActivities().size() > 1 ? 1.0 : 0.0;
        for (String zt : zeroTerms) { int s = Arrays.asList(SOCIO).indexOf(zt); if (s >= 0) x[s] = 0.0; }
        int t0 = Integer.MAX_VALUE, t1 = Integer.MIN_VALUE;
        for (Activity a : tour.getActivities().values()) { t0 = Math.min(t0, a.getStartTime_min()); t1 = Math.max(t1, a.getEndTime_min()); }
        e.window0 = t0 - (int) carT[po][h * n + m]; e.window1 = t1 + (int) carT[pr][m * n + h];
        e.av[CD] = pa.cd; e.av[CP] = true; e.av[BUS] = busOk; e.av[TRAIN] = trOk; e.av[WK] = km <= WALK_MAX; e.av[BK] = km <= BIKE_MAX;
        Map<String, Double> b = coef.get(e.seg); double[] adj = ascAdj.get(e.seg);
        utilities(cf.get(e.seg), adj, km, gc, T, C, x, e.v);
        if (jointGroupModel) { e.gc = gc; e.T = T; e.C = C; e.x = x; }
        probabilities(b, e.v, e.av, e.p);
        return e;
    }

    /** MNL, or nested logit with Biogeme's normalisation (mu_m >= 1 within the nest, 1 at the root) */
    static void probabilities(Map<String, Double> b, double[] v, boolean[] av, double[] p) {
        boolean nested = b.containsKey("mu_auto") || b.containsKey("mu_transit") || b.containsKey("mu_nonmot");
        double vmax = Double.NEGATIVE_INFINITY; for (int a = 0; a < 6; a++) if (av[a]) vmax = Math.max(vmax, v[a]);
        if (!nested) {
            double s = 0; for (int a = 0; a < 6; a++) { p[a] = av[a] ? Math.exp(v[a] - vmax) : 0; s += p[a]; }
            for (int a = 0; a < 6; a++) p[a] /= s; return;
        }
        double[] mu = new double[3], sum = new double[3], ls = new double[3]; boolean[] has = new boolean[3];
        for (int k = 0; k < 3; k++) mu[k] = b.getOrDefault("mu_" + NEST_NAME[k], 1.0);
        for (int a = 0; a < 6; a++) if (av[a]) { int k = NEST_OF[a]; sum[k] += Math.exp(mu[k] * (v[a] - vmax)); has[k] = true; }
        double den = 0; for (int k = 0; k < 3; k++) if (has[k]) { ls[k] = Math.log(sum[k]) / mu[k]; den += Math.exp(ls[k]); }
        for (int a = 0; a < 6; a++) { if (!av[a]) { p[a] = 0; continue; } int k = NEST_OF[a]; p[a] = Math.exp(ls[k]) / den * Math.exp(mu[k] * (v[a] - vmax)) / sum[k]; }
    }

    // ------------------------------------------------------------------------------------------------ choice and household stage
    static final class Rec { final Person person; final Tour tour; final Eval e; int alt; boolean joint, realloc; double[] u, uJ, vJ; boolean[] avJ; Rec(Person p, Tour t, Eval e) { person = p; tour = t; this.e = e; } }

    // ------------------------------------------------------------------------------------------------ TASHA car allocation
    // mc.car.allocation = tasha (2026-11-09, coef_respec; Miller, Roorda & Carrasco 2005): every person-tour draws random utilities
    // of its model (kept for every alternative) and takes the best available; at the household stage the car-driver tours (the
    // car-driver members of a joint group count as one unit, 2026-11-10) whose windows (leaving home
    // to returning) overlap beyond the household's cars form conflict sets; per set the cars go to the feasible subset with the
    // highest household utility (exhaustive up to mc.car.allocation.exhaustive.max tours, default 12, greedy by utility loss beyond);
    // a tour without a car takes its best other alternative from its own drawn utilities.  Car passenger stays available as
    // estimated; no ride-sharing facilitation step (joint tours carry the shared household rides).
    private static boolean tashaAlloc = false, jointDriverHH = false, jointRep = false, jointGroupModel = false; static int exhaustiveMax = 12;
    private static final AtomicLong nRepGroupModel = new AtomicLong();
    private static final AtomicLong nRepGroups = new AtomicLong(), nRepMembers = new AtomicLong(), nRepUnavail = new AtomicLong();
    private static final AtomicLong nHhJoint = new AtomicLong(), nHhJointCar = new AtomicLong();
    private static final AtomicLong nConfSets = new AtomicLong(), nConfUnits = new AtomicLong(), nGreedy = new AtomicLong(), nReassigned = new AtomicLong(),
            nCdUnits = new AtomicLong(), nViolAfter = new AtomicLong(), nReassignedTours = new AtomicLong();
    private static final AtomicLong[] reassignedTo = {new AtomicLong(), new AtomicLong(), new AtomicLong(), new AtomicLong(), new AtomicLong(), new AtomicLong()};

    /** positive stable variate with Laplace transform exp(-t^a), 0 < a < 1 (Kanter 1975) */
    static double stable(double a, Random r) {
        double U = Math.PI * r.nextDouble(), E = -Math.log(1.0 - r.nextDouble());
        while (U <= 0) U = Math.PI * r.nextDouble();
        return Math.sin(a * U) / Math.pow(Math.sin(U), 1.0 / a) * Math.pow(Math.sin((1 - a) * U) / E, (1 - a) / a);
    }

    /** random utilities of the estimated model: MNL u = V + Gumbel; nested logit (Biogeme form, mu_k >= 1 in the nest, 1 at the
     *  root) u_m = V_m + (nu_m + ln S_k) / mu_k, nu iid Gumbel, S_k positive stable of index 1/mu_k (exact GEV draw: the maximum of
     *  a nest is Gumbel at its inclusive value, within the nest a logit of scale mu_k); unavailable: -infinity */
    static double[] drawU(Cf c, double[] v, boolean[] av, Random r) {
        double[] u = new double[6], eta = new double[3];
        if (c.nested) for (int k = 0; k < 3; k++) { double lam = 1.0 / c.mu[k]; eta[k] = lam >= 1.0 - 1e-12 ? 0.0 : lam * Math.log(stable(lam, r)); }
        for (int a = 0; a < 6; a++) {
            if (!av[a]) { u[a] = Double.NEGATIVE_INFINITY; continue; }
            double nu = -Math.log(-Math.log(1.0 - r.nextDouble() * (1 - 1e-16)));
            u[a] = c.nested ? v[a] + nu / c.mu[NEST_OF[a]] + eta[NEST_OF[a]] : v[a] + nu;
        }
        return u;
    }

    /** members of a representative group take the representative's mode a (car driver: the others ride as car passenger); a member
     *  for whom a is not available takes its own best alternative other than car driver (counted) */
    static void repAssign(List<Rec> g, Rec rp, int a) {
        for (Rec x : g) {
            if (x == rp) x.alt = a;
            else if (a == CD) x.alt = CP;
            else if (x.e.av[a]) x.alt = a;
            else { x.alt = argmax(x.u, true); nRepUnavail.incrementAndGet(); }
        }
        nRepMembers.addAndGet(g.size());
    }

    /** best alternative other than car driver and car passenger (CP when no other is available) */
    static int argmaxNonCar(double[] u) { int b = -1; for (int a = 0; a < 6; a++) if (a != CD && a != CP && u[a] > Double.NEGATIVE_INFINITY && (b < 0 || u[a] > u[b])) b = a; return b < 0 ? CP : b; }

    static int argmax(double[] u, boolean noCd) { int b = -1; for (int a = 0; a < 6; a++) if (!(noCd && a == CD) && u[a] > Double.NEGATIVE_INFINITY && (b < 0 || u[a] > u[b])) b = a; return b < 0 ? CP : b; }

    /** largest number of the intervals [w0, w1) of the selected units in use at one instant */
    static int maxConcurrent(int[] w0, int[] w1, boolean[] sel) {
        int mx = 0;
        for (int i = 0; i < w0.length; i++) { if (!sel[i]) continue; int c = 0; for (int j = 0; j < w0.length; j++) if (sel[j] && w0[j] <= w0[i] && w0[i] < w1[j]) c++; mx = Math.max(mx, c); }
        return mx;
    }

    /** the cars of one household: keep[i] = unit i keeps the car; the feasible assignment (at most `cars` kept units in use at
     *  any instant) with the largest sum of gains (gain = utility of car driver - utility of the best other alternative), over
     *  the connected sets of overlapping windows; stats[0] conflict sets, [1] units in them, [2] sets solved greedily */
    static boolean[] allocate(int cars, int[] w0, int[] w1, double[] gain, long[] stats) {
        int n = w0.length; boolean[] keep = new boolean[n]; Arrays.fill(keep, true);
        Integer[] ord = new Integer[n]; for (int i = 0; i < n; i++) ord[i] = i; Arrays.sort(ord, (a, b) -> Integer.compare(w0[a], w0[b]));
        int i0 = 0;
        while (i0 < n) {   // connected sets of overlapping windows
            List<Integer> comp = new ArrayList<>(); int end = w1[ord[i0]]; int k = i0;
            while (k < n && (k == i0 || w0[ord[k]] < end)) { comp.add(ord[k]); end = Math.max(end, w1[ord[k]]); k++; }
            i0 = k;
            int m = comp.size(); int[] a0 = new int[m], a1 = new int[m]; double[] g = new double[m]; boolean[] all = new boolean[m]; Arrays.fill(all, true);
            for (int q = 0; q < m; q++) { a0[q] = w0[comp.get(q)]; a1[q] = w1[comp.get(q)]; g[q] = gain[comp.get(q)]; }
            if (maxConcurrent(a0, a1, all) <= cars) continue;
            stats[0]++; stats[1] += m; boolean[] best = new boolean[m];
            if (m <= exhaustiveMax) {
                double bv = Double.NEGATIVE_INFINITY;
                for (int mask = 0; mask < (1 << m); mask++) {
                    boolean[] s = new boolean[m]; double v = 0; for (int q = 0; q < m; q++) if ((mask >> q & 1) == 1) { s[q] = true; v += g[q]; }
                    if (v > bv + 1e-12 && maxConcurrent(a0, a1, s) <= cars) { bv = v; best = s; }
                }
            } else {
                stats[2]++; Integer[] go = new Integer[m]; for (int q = 0; q < m; q++) go[q] = q; Arrays.sort(go, (a, b) -> Double.compare(g[b], g[a]));
                for (int q : go) { best[q] = true; if (maxConcurrent(a0, a1, best) > cars) best[q] = false; }
            }
            for (int q = 0; q < m; q++) keep[comp.get(q)] = best[q];
        }
        return keep;
    }

    /** window of a tour for the allocation (2026-11-10): leaving home (departure of the first leg from home) to returning home
     *  (arrival of the last leg at home), from the tour's legs of the schedule, as in the estimation data
     *  (m10_car_availability.py: leave, arrive); the legs exist at the household stage.  Without legs: the evaluation window. */
    private static int[] legWindow(Rec x) {
        int w0 = Integer.MAX_VALUE, w1 = Integer.MIN_VALUE;
        for (Map.Entry<Integer, Leg> en : x.tour.getLegs().entrySet()) {
            Leg l = en.getValue();
            if (l.getPreviousActivity() != null && l.getPreviousActivity().getPurpose() == Purpose.HOME) w0 = Math.min(w0, l.getPreviousActivity().getEndTime_min());
            if (l.getNextActivity() != null && l.getNextActivity().getPurpose() == Purpose.HOME) w1 = Math.max(w1, l.getNextActivity().getStartTime_min());
        }
        return w0 == Integer.MAX_VALUE || w1 == Integer.MIN_VALUE ? new int[]{x.e.window0, x.e.window1} : new int[]{w0, w1};
    }

    /** household stage with the TASHA allocation (mc.car.allocation = tasha) */
    private void resolveTasha(Household hh, Map<Tour, Integer> mainJoint, Map<Integer, List<Rec>> groups, List<Rec> recs, Random r) {
        List<List<Rec>> units = new ArrayList<>(); List<double[]> uu = new ArrayList<>(); List<int[]> win = new ArrayList<>();
        Map<Integer, Object[]> repUnits = new HashMap<>();
        Set<Rec> inGroup = new HashSet<>();
        // joint tours (2026-11-10, coef_respec): every member keeps the choice from its own drawn utilities (the joint term per person,
        // as estimated: each member of a joint tour is a record of its own in the estimation data); no summed group draw.  The
        // car-driver members of a joint group are ONE car unit (as in the estimation availability rule, m10_car_availability.py):
        // window = the union of their windows, gain = the sum of their utility losses; a unit without a car: each of its members
        // takes the best other alternative of its own utilities.
        for (List<Rec> g : groups.values()) {
            if (g.size() < 2) continue; nJointGroups.incrementAndGet(); nJointTours.addAndGet(g.size()); inGroup.addAll(g);
            if (jointRep) {
                // mc.joint.rule = representative (2026-11-10; TASHA / GTAModel V4 JointTourRep): the representative is the member with
                // car driver available (licence, 16+, a household car), the oldest of them; without one the oldest member, and car
                // driver is not available to the group.  The representative's own drawn choice (joint term as estimated) is the group's:
                // car driver -> the representative drives, the others ride as car passenger; another mode -> every member takes it
                // where available to the member, else the member's own best alternative other than car driver.  The group is one car
                // unit (the representative's window; gain = the representative's loss); without a car the group takes the
                // representative's best alternative other than car driver under the same rule.
                Rec rp = null;
                for (Rec x : g) { x.joint = true; if (x.e.av[CD] && (rp == null || x.person.getAge() > rp.person.getAge())) rp = x; }
                if (rp == null) for (Rec x : g) if (rp == null || x.person.getAge() > rp.person.getAge()) rp = x;
                double[] ur = rp.u;
                Cf cj = jointGroupModel ? cf.get(rp.e.seg + "_joint") : null;
                if (cj != null && rp.e.gc != null) {
                    // mc.joint.model = group (2026-11-10, m11_joint_group.py): the representative applies the group-level model of the
                    // segment (coefficients <segment>_joint): the representative's tour variables, joint = 1; car driver available when a
                    // member has it, the other modes as for the representative; a mode without a constant in the group model is not
                    // available (not chosen by any estimation group)
                    double[] xj = rp.e.x.clone(); xj[9] = 1.0; double[] vj = new double[6]; boolean[] avj = rp.e.av.clone();
                    avj[CD] = false; for (Rec x : g) avj[CD] |= x.e.av[CD];
                    for (int a = 1; a < 6; a++) if (cj.asc[a] == 0.0 && !cj.hasAsc[a]) avj[a] = false;
                    utilities(cj, null, rp.e.km, rp.e.gc, rp.e.T, rp.e.C, xj, vj);
                    ur = drawU(cj, vj, avj, r); rp.vJ = vj; rp.avJ = avj; nRepGroupModel.incrementAndGet();
                }
                rp.uJ = ur;
                int a0 = ur[CD] > Double.NEGATIVE_INFINITY ? argmax(ur, false) : argmax(ur, true); repAssign(g, rp, a0); nRepGroups.incrementAndGet();
                if (a0 == CD) {
                    double[] U = new double[6]; Arrays.fill(U, Double.NEGATIVE_INFINITY); U[CD] = ur[CD] - ur[argmax(ur, true)]; U[CP] = 0.0;
                    repUnits.put(units.size(), new Object[]{g, rp}); units.add(Collections.singletonList(rp)); uu.add(U); win.add(legWindow(rp));
                }
                continue;
            }
            if (jointDriverHH) {
                // mc.joint.driver = household (2026-11-10): car or not drawn once per group with the probability that at least one
                // member drives, 1 - prod(1 - p_CD,m) (one common uniform); car: the member with car driver available and the
                // largest drawn advantage u_CD - max(other u) drives, the members whose own choice is a car mode ride as car
                // passenger, the others keep their choices; non-car (or nobody can drive): the members whose own choice is a car mode
                // take their best non-car alternative.  The group is one car unit (the driver's window; gain = the driver's loss).
                double q = 1; Rec drv = null; double best = Double.NEGATIVE_INFINITY;
                for (Rec x : g) { x.joint = true; q *= 1 - x.e.p[CD]; if (x.e.av[CD]) { double adv = x.u[CD] - x.u[argmax(x.u, true)]; if (adv > best) { best = adv; drv = x; } } }
                boolean car = drv != null && r.nextDouble() < 1 - q; nHhJoint.incrementAndGet(); if (car) nHhJointCar.incrementAndGet();
                for (Rec x : g) {
                    boolean carUser = x.alt == CD || x.alt == CP;
                    if (car) { if (x == drv) x.alt = CD; else if (carUser) x.alt = CP; }
                    else if (carUser) x.alt = argmaxNonCar(x.u);
                }
                if (car) {
                    int[] w = legWindow(drv); double[] U = new double[6]; Arrays.fill(U, Double.NEGATIVE_INFINITY); U[CD] = best; U[CP] = 0.0;
                    units.add(Collections.singletonList(drv)); uu.add(U); win.add(w);
                }
                continue;
            }
            List<Rec> cdm = new ArrayList<>(); for (Rec x : g) { x.joint = true; if (x.alt == CD) cdm.add(x); }
            if (cdm.isEmpty()) continue;
            int w0 = Integer.MAX_VALUE, w1 = Integer.MIN_VALUE; double gn = 0;
            for (Rec x : cdm) { int[] w = legWindow(x); w0 = Math.min(w0, w[0]); w1 = Math.max(w1, w[1]); gn += x.u[CD] - x.u[argmax(x.u, true)]; }
            double[] U = new double[6]; Arrays.fill(U, Double.NEGATIVE_INFINITY); U[CD] = gn; U[CP] = 0.0;   // gain carrier
            units.add(cdm); uu.add(U); win.add(new int[]{w0, w1});
        }
        for (Rec x : recs) if (!inGroup.contains(x) && x.alt == CD) { units.add(Collections.singletonList(x)); uu.add(x.u); win.add(legWindow(x)); }
        int n = units.size(); nCdUnits.addAndGet(n); nCdTours.addAndGet(n);
        int[] w0 = new int[n], w1 = new int[n]; double[] gain = new double[n];
        for (int i = 0; i < n; i++) { w0[i] = win.get(i)[0]; w1[i] = win.get(i)[1]; double[] U = uu.get(i); gain[i] = U[CD] - U[argmax(U, true)]; }
        long[] st = new long[3]; int cars = hh.getNumberOfCars();
        boolean[] keep = allocate(cars, w0, w1, gain, st);
        nConfSets.addAndGet(st[0]); nConfUnits.addAndGet(st[1]); nGreedy.addAndGet(st[2]); if (st[0] > 0) nHhConflict.incrementAndGet();
        for (int i = 0; i < n; i++) {
            if (keep[i]) continue;
            Object[] gr = repUnits.get(i);
            if (gr != null) {   // representative group without a car: the representative's best alternative other than car driver
                @SuppressWarnings("unchecked") List<Rec> g = (List<Rec>) gr[0]; Rec rp = (Rec) gr[1]; int a = argmax(rp.uJ != null ? rp.uJ : rp.u, true);
                repAssign(g, rp, a); nReassigned.incrementAndGet(); nRealloc.incrementAndGet();
                for (Rec x : g) { x.realloc = true; nReassignedTours.incrementAndGet(); reassignedTo[x.alt].incrementAndGet(); }
                continue;
            }
            nReassigned.incrementAndGet(); nRealloc.incrementAndGet();
            for (Rec x : units.get(i)) { x.alt = argmax(x.u, true); x.realloc = true; nReassignedTours.incrementAndGet(); reassignedTo[x.alt].incrementAndGet(); }
        }
        if (maxConcurrent(w0, w1, keep) > cars) nViolAfter.incrementAndGet();   // check: no instant with more car-driver tours than cars
        for (Rec x : recs) apply(x);
        if (toursOut) for (Rec x : recs) line(x, mainJoint.getOrDefault(x.tour, 0));
    }
    private static final ThreadLocal<List<Rec>> pending = ThreadLocal.withInitial(ArrayList::new);

    private static int draw(double[] p, boolean[] av, Random r) {
        double s = 0; for (int a = 0; a < 6; a++) if (av[a]) s += p[a];
        double u = r.nextDouble() * s, c = 0; int sel = -1;
        for (int a = 0; a < 6; a++) { if (!av[a] || p[a] <= 0) continue; c += p[a]; sel = a; if (u <= c) break; }
        return sel < 0 ? CP : sel;
    }

    private static Mode modeOf(int alt) {
        switch (alt) { case CD: return Mode.CAR_DRIVER; case CP: return Mode.CAR_PASSENGER; case BUS: return Mode.BUS; case TRAIN: return Mode.TRAIN; case WK: return Mode.WALK; default: return Mode.BIKE; }
    }

    private static void apply(Rec x) {
        Mode mode = modeOf(x.alt); x.tour.setTourMode(mode);
        for (Leg leg : x.tour.getLegs().values()) leg.setLegMode(mode);   // the stops of the tour inherit its mode
    }

    private static boolean[] noCar(boolean[] av) { boolean[] b = av.clone(); b[CD] = false; return b; }

    /** probabilities of the tour's model without car driver (the next-best choice of a tour that loses the car) */
    private static double[] withoutCar(Rec x) { double[] p = new double[6]; probabilities(coef.get(x.e.seg), x.e.v, noCar(x.e.av), p); return p; }

    /** person-level choice, before the stops of the tour are located; the household stage may revise it */
    public void chooseMode(Person person, Tour tour, Random r) {
        Eval e = evaluate(person, tour); Rec x = new Rec(person, tour, e);
        if (tashaAlloc) { x.u = drawU(cf.get(e.seg), e.v, e.av, r); x.alt = argmax(x.u, false); } else x.alt = draw(e.p, e.av, r);
        apply(x);
        pending.get().add(x); nTours.incrementAndGet();
    }

    /**
     * Household stage (TASHA: Miller, Roorda &amp; Carrasco 2005), after every member's tours are formed.
     * 1. Joint tours (main activity a joint episode, tours of two or more members): one mode for all, drawn from the model of the
     *    segment (its nests and nest parameters) on the sum of the participants' utilities; car driver is available when a participant can drive, the participant with the
     *    largest V_CD - V_CP drives and the others are passengers; every other mode needs all participants to have it.
     * 2. Vehicle allocation: car-driver tours whose time windows (departure from home to return) overlap and outnumber the
     *    household's cars: the cars go to the tours with the largest V_CD - max(other available V); the others take a mode drawn
     *    from their model without car driver (a joint group that loses its car redraws jointly without car driver).
     */
    public void resolveHousehold(Household hh, Map<Tour, Integer> mainJoint, Random r) {
        List<Rec> recs = new ArrayList<>(pending.get()); pending.get().clear();
        if (recs.isEmpty()) return;
        nHh.incrementAndGet();
        Map<Integer, List<Rec>> groups = new LinkedHashMap<>();
        for (Rec x : recs) { Integer j = mainJoint.get(x.tour); if (j != null && j != 0) groups.computeIfAbsent(j, k -> new ArrayList<>()).add(x); }
        if (applyJoint) {   // joint household tour: the estimated joint terms, then the person-level draw again
            int sj = Arrays.asList(SOCIO).indexOf("joint"); Cf c0;
            for (List<Rec> g : groups.values()) for (Rec x : g) {
                c0 = cf.get(x.e.seg); boolean any = false;
                for (int a = 0; a < 6; a++) if (c0.has[a][sj]) { x.e.v[a] += c0.so[a][sj]; if (x.u != null) x.u[a] += c0.so[a][sj]; any = true; }
                if (!any) continue;
                probabilities(coef.get(x.e.seg), x.e.v, x.e.av, x.e.p);
                if (tashaAlloc) x.alt = argmax(x.u, false); else x.alt = draw(x.e.p, x.e.av, r);
                apply(x);
            }
        }
        if (tashaAlloc) { resolveTasha(hh, mainJoint, groups, recs, r); return; }
        for (List<Rec> g : groups.values()) if (g.size() >= 2) { jointChoice(g, false, r); nJointGroups.incrementAndGet(); nJointTours.addAndGet(g.size()); }
        int cars = hh.getNumberOfCars();
        List<Rec> cd = new ArrayList<>(); for (Rec x : recs) if (x.alt == CD) cd.add(x);
        nCdTours.addAndGet(cd.size());
        cd.sort((a, b) -> Double.compare(advantage(b), advantage(a)));
        List<int[]> held = new ArrayList<>(); boolean conflict = false;
        for (Rec x : cd) {
            if (x.alt != CD) continue;
            if (maxOverlap(held, x.e.window0, x.e.window1) < cars) { held.add(new int[]{x.e.window0, x.e.window1}); continue; }
            conflict = true; nRealloc.incrementAndGet();
            if (cdEstimation) continue;   // counted, not reallocated
            Integer j = mainJoint.get(x.tour); List<Rec> g = j != null && j != 0 ? groups.get(j) : null;
            if (g != null && g.size() >= 2) { jointChoice(g, true, r); for (Rec y : g) y.realloc = true; }
            else { x.alt = draw(withoutCar(x), noCar(x.e.av), r); x.realloc = true; apply(x); }
        }
        if (conflict) nHhConflict.incrementAndGet();
        if (toursOut) for (Rec x : recs) line(x, mainJoint.getOrDefault(x.tour, 0));
    }

    private static double advantage(Rec x) {
        double best = Double.NEGATIVE_INFINITY; for (int a = 0; a < 6; a++) if (a != CD && x.e.av[a]) best = Math.max(best, x.e.v[a]);
        return x.e.v[CD] - best;
    }

    /** the largest number of held windows in use at one instant of [t0, t1) */
    private static int maxOverlap(List<int[]> held, int t0, int t1) {
        int mx = 0; List<Integer> pts = new ArrayList<>(); pts.add(t0);
        for (int[] w : held) if (w[0] < t1 && t0 < w[1] && w[0] > t0) pts.add(w[0]);
        for (int s : pts) { int c = 0; for (int[] u : held) if (u[0] <= s && s < u[1]) c++; mx = Math.max(mx, c); }
        return mx;
    }

    private void jointChoice(List<Rec> g, boolean noCarAll, Random r) {
        double[] v = new double[6]; boolean[] av = new boolean[6]; Arrays.fill(av, true);
        Rec driver = null; double best = Double.NEGATIVE_INFINITY;
        for (Rec x : g) if (x.e.av[CD] && x.e.v[CD] - x.e.v[CP] > best) { best = x.e.v[CD] - x.e.v[CP]; driver = x; }
        av[CD] = driver != null && !noCarAll;
        for (int a = 0; a < 6; a++) if (a != CD) for (Rec x : g) av[a] &= x.e.av[a];
        for (int a = 0; a < 6; a++) { if (!av[a]) continue; for (Rec x : g) v[a] += (a == CD && x != driver) ? x.e.v[CP] : x.e.v[a]; }
        // the group's choice has the structure of the estimated model of its segment (nests and their parameters; 2026-11-02:
        // before, a flat logit of the summed utilities ignored the auto nest, which made a household driver less likely than the
        // members' own models do)
        double[] p = new double[6];
        probabilities(coef.get(g.get(0).e.seg), v, av, p);
        int alt = draw(p, av, r);
        for (Rec x : g) { x.alt = (alt == CD && x != driver) ? CP : alt; x.joint = true; apply(x); }
    }

    private static void line(Rec x, int jointId) {
        Person person = x.person; Tour tour = x.tour; Eval e = x.e; Activity main = tour.getMainActivity(); StringBuilder sb = new StringBuilder();
        sb.append(person.getId()).append(',').append(person.getHousehold().getId()).append(',').append(main.getPurpose()).append(',').append(e.seg).append(',')
          .append(person.getHousehold().getLocation().getZoneId()).append(',').append(main.getLocation().getZoneId()).append(',').append(main.getStartTime_min()).append(',')
          .append(main.getEndTime_min()).append(',').append(tour.getActivities().size()).append(',').append(String.format(Locale.US, "%.3f", e.km)).append(',')
          .append(ALT[x.alt]).append(',').append(tour.getTourMode()).append(',').append(x.joint ? 1 : 0).append(',').append(x.realloc ? 1 : 0).append(',').append(jointId);
        for (int a = 0; a < 6; a++) sb.append(',').append(String.format(Locale.US, "%.5f", e.p[a]));
        if (toursFull) {   // unit check of the re-specified models (mc.tours.full): utilities, availability, full-precision probabilities
            for (int a = 0; a < 6; a++) sb.append(',').append(e.av[a] ? Double.toString(e.v[a]) : "");
            for (int a = 0; a < 6; a++) sb.append(',').append(Double.toString(e.p[a]));
            if (jointGroupModel) for (int a = 0; a < 6; a++) sb.append(',').append(x.vJ != null && x.avJ[a] ? Double.toString(x.vJ[a]) : "");
        }
        tourLines.add(sb.toString());
    }

    @Override public void chooseMode(Person person, Tour tour) { chooseMode(person, tour, rnd); }
    @Override public void chooseMode(Person person, Tour tour, Purpose purpose) { chooseMode(person, tour, rnd); }
    @Override public Mode chooseMode(Person person, Tour tour, Purpose purpose, Boolean carAvailable) { chooseMode(person, tour, rnd); return tour.getTourMode(); }
    @Override public void checkCarAvailabilityAndChooseMode(Household h, Person p, Tour t, Purpose pu) { chooseMode(p, t, rnd); }

    /** writes output/mc_tours.csv (mc.tours.out = true) and output/mc_summary.csv */
    public static void finish() {
        logger.info("Tour mode choice: " + nTours.get() + " tours; joint groups " + nJointGroups.get() + "; car-driver tours reallocated " + nRealloc.get() + " of " + nCdTours.get());
        String out = AbitResources.instance.getString("base.directory") + "/output/";
        new File(out).mkdirs();
        if (toursOut) {
            try (PrintWriter pw = new PrintWriter(new BufferedWriter(new FileWriter(out + "mc_tours.csv"), 1 << 20))) {
                pw.println("person_id,household_id,purpose,segment,home_zone,main_zone,start,end,n_act,km,alt,mode,joint,realloc,joint_id,p_CD,p_WK,p_BK,p_CP,p_BUS,p_TRAIN"
                        + (toursFull ? ",V_CD,V_WK,V_BK,V_CP,V_BUS,V_TRAIN,pf_CD,pf_WK,pf_BK,pf_CP,pf_BUS,pf_TRAIN" + (jointGroupModel ? ",VJ_CD,VJ_WK,VJ_BK,VJ_CP,VJ_BUS,VJ_TRAIN" : "") : ""));
                for (String l : tourLines) pw.println(l);
            } catch (IOException e) { logger.warn("could not write mc_tours.csv", e); }
        }
        try (PrintWriter pw = new PrintWriter(out + "mc_summary.csv")) {
            pw.println("measure,value"); pw.println("tours," + nTours.get()); pw.println("households," + nHh.get());
            pw.println("joint_groups," + nJointGroups.get()); pw.println("joint_tours," + nJointTours.get());
            pw.println("car_driver_tours_before_allocation," + nCdTours.get());
            pw.println((cdEstimation ? "car_driver_tours_beyond_car_count_not_reallocated," : "car_driver_tours_reallocated,") + nRealloc.get());
            pw.println("households_with_a_car_conflict," + nHhConflict.get());
            if (tashaAlloc) {
                pw.println("tasha_car_driver_units," + nCdUnits.get()); pw.println("tasha_conflict_sets," + nConfSets.get()); pw.println("tasha_units_in_conflict_sets," + nConfUnits.get());
                pw.println("tasha_conflict_sets_greedy," + nGreedy.get()); pw.println("tasha_units_reassigned," + nReassigned.get()); pw.println("tasha_tours_reassigned," + nReassignedTours.get());
                for (int a = 0; a < 6; a++) pw.println("tasha_reassigned_to_" + ALT[a] + "," + reassignedTo[a].get());
                pw.println("tasha_households_overlap_beyond_cars_after," + nViolAfter.get());
                if (jointRep) { pw.println("joint_groups_representative," + nRepGroups.get()); pw.println("joint_members_representative," + nRepMembers.get());
                    pw.println("joint_members_group_mode_unavailable," + nRepUnavail.get()); if (jointGroupModel) pw.println("joint_groups_group_model," + nRepGroupModel.get()); }
                if (jointDriverHH) { pw.println("joint_groups_household_driver," + nHhJoint.get()); pw.println("joint_groups_by_car," + nHhJointCar.get()); }
            }
        } catch (IOException e) { logger.warn("could not write mc_summary.csv", e); }
    }
}
