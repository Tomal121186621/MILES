package abm.models.maryland;

import abm.data.DataSet;
import abm.data.geo.MicroscopicLocation;
import abm.data.geo.Zone;
import abm.data.plans.*;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;
import abm.utils.PlanTools;
import de.tum.bgu.msm.data.person.Gender;
import de.tum.bgu.msm.data.person.Occupation;
import org.apache.log4j.Logger;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.*;

/**
 * RTS intermediate-stop generator (Tour-Based MITO model #04). Ordered logit per purpose x half
 * (outbound/inbound): P(0/1/2 stops) from thresholds tau_1, tau_2 and utility V = sum(b_v * x_v).
 * Applied as a post-processing pass over every home-based tour; stops are inserted with PlanTools
 * (rubber-banded to the main-activity zone). Purpose->spec: WORK=HBW, EDUCATION=HBE, SHOPPING=HBS,
 * OTHER/RECREATION/ACCOMPANY=HBO. Optional per-purpose x half calibration offsets hit RTS targets.
 */
public class MarylandStopModel {

    private static final Logger logger = Logger.getLogger(MarylandStopModel.class);
    private final DataSet dataSet;
    private final PlanTools planTools;
    private final Random rnd = AbitUtils.getRandomObject();

    // coefs.get(purpose+"_"+half).get(param)
    private final Map<String, Map<String, Double>> coef = new HashMap<>();
    private final Map<String, Double> offset = new HashMap<>();
    private final Map<String, Double> spread = new HashMap<>();

    // ---- intermediate-stop location index (corridor rubber-band) ----
    // Stops used to be pinned to the main-activity zone (0-distance stop<->anchor legs, which
    // collapsed the purpose trip-length means far below RTS). Instead we snap each stop to a real
    // intermediate zone drawn ALONG the home<->main corridor, so the stop legs carry a realistic
    // network distance (verified vs RTS). Location is the intermediate zone CENTROID so it stays
    // consistent with build_studyarea's per-zone POI placement.
    private int[] zoneIds;                 // zone id per index
    private double[] zX, zY;               // zone centroid coords
    private final Map<Long, List<Integer>> grid = new HashMap<>();   // spatial hash -> zone indices
    private static final double CELL = 3000.0;                       // grid cell size (m)
    private static long gkey(int gx, int gy) { return (((long) gx) << 32) ^ (gy & 0xffffffffL); }

    private static final Map<String, String[]> SPEC = new HashMap<>();
    static {
        SPEC.put("HBW", new String[]{"worker", "hiinc", "autos", "zerocar", "female", "senior", "center", "hhsize", "dist_primary", "autoDriver"});
        SPEC.put("HBS", new String[]{"hhsize", "autos", "zerocar", "hiinc", "female", "senior", "center", "dist_primary", "autoDriver"});
        SPEC.put("HBO", new String[]{"hhsize", "autos", "zerocar", "senior", "hiinc", "center", "child", "female", "dist_primary", "autoDriver"});
        SPEC.put("HBE", new String[]{"child", "hhsize", "autos", "zerocar", "female", "center", "dist_primary", "autoDriver"});
    }

    /**
     * RTS-derived intermediate-stop PURPOSE split by tour type. Derived from rts_trips_clean.csv by
     * reconstructing home-based tours (primary = longest-duration activity) and tabulating the purpose
     * distribution of the non-primary stops, weighted by wttrdfin. Fixes the prior bug where every stop
     * was hard-coded Purpose.OTHER (starved SHOP, inflated OTHER vs RTS).
     *
     * Two calibrations vs the raw RTS split:
     *  1. SHOPPING dampened by 0.60 (removed mass -> OTHER): ABIT over-generates discretionary stops on
     *     shop-heavy HBO/HBS tours, so the raw split overshoots SHOP (~0.19 vs RTS 0.165); 0.60 lands
     *     SHOP at 0.166 (verified in the v4 full-MSTM run).
     *  2. Intermediate stops carry only DISCRETIONARY purposes (SHOPPING/RECREATION/ACCOMPANY/OTHER);
     *     the raw WORK and EDUCATION stop mass is folded into OTHER. Rationale: ABIT places a work tour
     *     on every weekday, so faithfully labeling work stops (raw HBW WORK=0.236) inflated the WORK trip
     *     share to 0.272 (>> RTS 0.224 and the ~0.21 baseline). WORK/EDUCATION are mandatory activities,
     *     not discretionary stops; excluding them keeps WORK unchanged at its baseline while SHOP/OTHER
     *     are corrected. (OTHER's residual gap to RTS is the structural ABIT EDUCATION deficit.)
     * Order below: WORK, EDUCATION, SHOPPING, RECREATION, ACCOMPANY, OTHER (WORK/EDUCATION kept at 0).
     */
    private static final Purpose[] STOP_ORDER =
            {Purpose.WORK, Purpose.EDUCATION, Purpose.SHOPPING, Purpose.RECREATION, Purpose.ACCOMPANY, Purpose.OTHER};
    private static final Map<String, double[]> STOP_CDF = new HashMap<>();
    static {
        putStopDist("HBW", new double[]{0.0, 0.0, 0.0922, 0.0641, 0.1893, 0.6544});
        putStopDist("HBE", new double[]{0.0, 0.0, 0.0758, 0.1278, 0.2419, 0.5545});
        putStopDist("HBS", new double[]{0.0, 0.0, 0.2396, 0.0450, 0.1410, 0.5744});
        putStopDist("HBO", new double[]{0.0, 0.0, 0.1628, 0.0835, 0.1890, 0.5648});
    }
    private static void putStopDist(String sp, double[] p) {
        double[] cdf = new double[p.length];
        double c = 0;
        for (int i = 0; i < p.length; i++) { c += p[i]; cdf[i] = c; }
        STOP_CDF.put(sp, cdf);
    }

    // Validation_2026 stage 3, second pass (2026-10-22): stop purpose conditional on the TOUR PURPOSE and the stop position
    // (outbound / inbound), estimated from the estimation half of the survey (property stop.purpose.file; columns
    // tour_purpose,half,WORK,EDUCATION,SHOPPING,RECREATION,ACCOMPANY,OTHER with the probabilities).  WORK and EDUCATION
    // stops (a second work location, work errands) are drawn as the survey has them.  Without the file the fixed split
    // STOP_CDF by stop specification above stays in force.
    private final Map<String, double[]> stopPurposeCdf = new HashMap<>();   // "TOURPURPOSE_out" / "_in" -> cdf over STOP_ORDER

    /** Draw a stop purpose: survey split by tour purpose x position when loaded, else the tour-type split (seeded RNG). */
    private Purpose drawStopPurpose(String sp, Purpose tourPurpose, boolean outbound, Random rnd) {
        double[] cdf = stopPurposeCdf.get(tourPurpose + (outbound ? "_out" : "_in"));
        if (cdf == null) cdf = STOP_CDF.get(sp);
        if (cdf == null) return Purpose.OTHER;
        double u = rnd.nextDouble() * cdf[cdf.length - 1];
        for (int i = 0; i < cdf.length; i++) if (u < cdf[i]) return STOP_ORDER[i];
        return STOP_ORDER[STOP_ORDER.length - 1];
    }

    private void loadStopPurposes() {
        String f = AbitResources.instance.getString("stop.purpose.file");
        if (f == null || f.isBlank()) return;
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String[] h = br.readLine().split(",");
            int iT = -1, iH = -1; int[] iP = new int[STOP_ORDER.length];
            for (int i = 0; i < h.length; i++) {
                String c = h[i].trim();
                if (c.equals("tour_purpose")) iT = i; else if (c.equals("half")) iH = i;
                for (int k = 0; k < STOP_ORDER.length; k++) if (c.equals(STOP_ORDER[k].name())) iP[k] = i;
            }
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                double[] cdf = new double[STOP_ORDER.length]; double c = 0;
                for (int k = 0; k < STOP_ORDER.length; k++) { c += Double.parseDouble(r[iP[k]].trim()); cdf[k] = c; }
                stopPurposeCdf.put(r[iT].trim().toUpperCase() + "_" + r[iH].trim().toLowerCase(), cdf);
            }
            logger.info("MarylandStopModel: stop purposes by tour purpose x position from " + f + " (" + stopPurposeCdf.size() + " rows)");
        } catch (Exception e) {
            throw new RuntimeException("stop.purpose.file load failed: " + f, e);
        }
    }

    // Validation_2026 stage 3 (2026-10-22): with dest.choice.model = mnl the zone of a discretionary stop is drawn from the estimated
    // stop destination MNL (MarylandDestinationChoice.selectStopZoneMnl: detour relative to the home - primary destination path,
    // full choice set); WORK / EDUCATION stops and purposes without an estimated stop model keep the corridor rule below.
    private MarylandDestinationChoice mnlDc = null;

    public MarylandStopModel(DataSet dataSet) {
        this.dataSet = dataSet;
        this.planTools = new PlanTools(dataSet.getTravelTimes());
        loadCoefs();
        loadOffsets();
        loadStopPurposes();
        buildZoneIndex();
        boolean any = false;
        for (Purpose p : Purpose.getDiscretionaryPurposes()) any |= MarylandDestinationChoice.hasStopModel(p);
        if (any) { mnlDc = new MarylandDestinationChoice(dataSet); logger.info("MarylandStopModel: stop zones from the estimated destination MNL"); }
    }

    /** Build the zone-centroid arrays + spatial hash used to snap a corridor point to a real zone. */
    private void buildZoneIndex() {
        List<Zone> zs = new ArrayList<>(dataSet.getZones().values());
        zoneIds = new int[zs.size()];
        zX = new double[zs.size()];
        zY = new double[zs.size()];
        for (int i = 0; i < zs.size(); i++) {
            Zone z = zs.get(i);
            double x = z.getAttribute("x").map(o -> (double) o).orElse(0.0);
            double y = z.getAttribute("y").map(o -> (double) o).orElse(0.0);
            zoneIds[i] = z.getZoneId();
            zX[i] = x;
            zY[i] = y;
            grid.computeIfAbsent(gkey((int) Math.floor(x / CELL), (int) Math.floor(y / CELL)),
                    k -> new ArrayList<>()).add(i);
        }
    }

    /** Nearest zone index to (x,y), searching the spatial hash outward ring by ring. */
    private int nearestZone(double x, double y) {
        int cx = (int) Math.floor(x / CELL), cy = (int) Math.floor(y / CELL);
        int best = -1;
        double bestD = Double.MAX_VALUE;
        for (int r = 0; r <= 40; r++) {
            for (int gx = cx - r; gx <= cx + r; gx++) {
                for (int gy = cy - r; gy <= cy + r; gy++) {
                    if (r > 0 && gx > cx - r && gx < cx + r && gy > cy - r && gy < cy + r) continue; // ring only
                    List<Integer> cell = grid.get(gkey(gx, gy));
                    if (cell == null) continue;
                    for (int i : cell) {
                        double d = (zX[i] - x) * (zX[i] - x) + (zY[i] - y) * (zY[i] - y);
                        if (d < bestD) { bestD = d; best = i; }
                    }
                }
            }
            if (best >= 0 && r >= 1) break;  // found something and searched one extra ring for safety
        }
        return best;
    }

    /**
     * A real intermediate zone on the corridor between {@code a} and {@code b}. Draws a position
     * fraction f~U(0.15,0.85) plus a modest lateral offset (a realistic detour, not a straight snap),
     * snaps to the nearest zone and returns its CENTROID as the stop location.
     */
    private MicroscopicLocation intermediateLocation(MicroscopicLocation a, MicroscopicLocation b, Random rnd) {
        double ax = a.getX(), ay = a.getY(), bx = b.getX(), by = b.getY();
        double dx = bx - ax, dy = by - ay;
        double seg = Math.hypot(dx, dy);
        double f = 0.15 + rnd.nextDouble() * 0.70;
        double px = ax + f * dx, py = ay + f * dy;
        if (seg > 1.0) {                     // lateral detour ~ +/-15% of the segment length
            double nx = -dy / seg, ny = dx / seg;
            double lat = (rnd.nextDouble() - 0.5) * 0.30 * seg;
            px += nx * lat; py += ny * lat;
        }
        int zi = nearestZone(px, py);
        if (zi < 0) return b;                // fallback: keep anchor
        MicroscopicLocation loc = new MicroscopicLocation(zX[zi], zY[zi]);
        loc.setZone(dataSet.getZones().get(zoneIds[zi]));
        return loc;
    }

    private void loadCoefs() {
        String f = AbitResources.instance.getString("stopfreq.coefs");
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            br.readLine();
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                coef.computeIfAbsent(r[0].trim() + "_" + r[1].trim(), k -> new HashMap<>())
                        .put(r[2].trim(), Double.parseDouble(r[3].trim()));
            }
        } catch (Exception e) {
            throw new RuntimeException("stopfreq.coefs load failed", e);
        }
    }

    private void loadOffsets() {
        String f = AbitResources.instance.getString("stopfreq.offsets");
        if (f == null) return;
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            br.readLine();
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                offset.put(r[0].trim(), Double.parseDouble(r[1].trim()));
                if (r.length > 2) spread.put(r[0].trim(), Double.parseDouble(r[2].trim()));
            }
        } catch (Exception ignored) { }
    }

    private String spec(Purpose p) {
        switch (p) {
            case WORK: return "HBW";
            case EDUCATION: return "HBE";
            case SHOPPING: return "HBS";
            default: return "HBO"; // OTHER, RECREATION, ACCOMPANY
        }
    }

    public int run() {
        java.util.concurrent.atomic.AtomicInteger added = new java.util.concurrent.atomic.AtomicInteger();
        if (mnlDc == null) {
            // calibrated set without the estimated MNL: sequential over persons with the shared seeded generator (unchanged)
            for (Person person : dataSet.getPersons().values()) added.addAndGet(stopsOf(person, rnd));
        } else {
            // estimated stop destination MNL (full choice set, ~0.3 ms per stop): persons in parallel, each with its own generator
            // seeded from the run seed and the person id, so that the result does not depend on the thread schedule
            long base = rnd.nextLong();
            int threads = Math.max(1, AbitResources.instance.getInt("number.of.threads", 4));
            List<Person> ps = new ArrayList<>(dataSet.getPersons().values());
            java.util.concurrent.ForkJoinPool pool = new java.util.concurrent.ForkJoinPool(threads);
            try {
                pool.submit(() -> ps.parallelStream().forEach(p -> added.addAndGet(stopsOf(p, new Random(base ^ (0x9E3779B97F4A7C15L * (p.getId() + 1L))))))).get();
            } catch (Exception e) { throw new RuntimeException("stop model failed", e); }
            finally { pool.shutdown(); }
        }
        logger.info("MarylandStopModel inserted " + added.get() + " intermediate stops");
        return added.get();
    }

    private int stopsOf(Person person, Random rnd) {
        int added = 0;
        Plan plan = person.getPlan();
        if (plan == null) return 0;
        List<Tour> tours = new ArrayList<>(plan.getTours().values());
        for (Tour tour : tours) {
            Purpose p = tour.getMainActivity().getPurpose();
            if (p == Purpose.SUBTOUR) continue;
            String sp = spec(p);
            if (!coef.containsKey(sp + "_out")) continue;
            Map<String, Double> x = covariates(person, tour);
            int nOut = draw(sp, p, "out", x, rnd);
            int nIn = draw(sp, p, "in", x, rnd);
            for (int i = 0; i < nOut; i++) { if (addStop(plan, tour, true, sp, p, rnd)) added++; }
            for (int i = 0; i < nIn; i++) { if (addStop(plan, tour, false, sp, p, rnd)) added++; }
            // stop insertion creates new legs without a mode; re-apply the tour mode to all legs
            Mode tm = tour.getTourMode();
            if (tm != null) for (Leg leg : tour.getLegs().values()) leg.setLegMode(tm);
        }
        return added;
    }

    private Map<String, Double> covariates(Person person, Tour tour) {
        Household hh = person.getHousehold();
        int autos = hh.getNumberOfCars();
        double hhInc = 0;
        for (Person pp : hh.getPersons()) hhInc += pp.getMonthlyIncome_eur() * 12.0;
        double distMi = dataSet.getTravelDistances().getTravelDistanceInMeters(
                hh.getLocation(), tour.getMainActivity().getLocation(), Mode.UNKNOWN, 8 * 60) / 1609.34;
        boolean center = false;
        abm.data.geo.Zone z = dataSet.getZones().get(hh.getLocation().getZoneId());
        if (z != null && z.getBBSRType() == abm.data.geo.BBSRType.CORE_CITY) center = true;
        Map<String, Double> x = new HashMap<>();
        x.put("worker", person.getOccupation() == Occupation.EMPLOYED ? 1.0 : 0.0);
        x.put("hiinc", hhInc > 100000 ? 1.0 : 0.0);
        x.put("autos", (double) autos);
        x.put("zerocar", autos == 0 ? 1.0 : 0.0);
        x.put("female", person.getGender() == Gender.FEMALE ? 1.0 : 0.0);
        x.put("senior", person.getAge() >= 65 ? 1.0 : 0.0);
        x.put("child", person.getAge() < 18 ? 1.0 : 0.0);
        x.put("center", center ? 1.0 : 0.0);
        x.put("hhsize", (double) hh.getPersons().size());
        x.put("dist_primary", distMi);
        Mode tm = tour.getTourMode();
        x.put("autoDriver", tm == Mode.CAR_DRIVER ? 1.0 : 0.0);
        return x;
    }

    private int draw(String sp, Purpose tourPurpose, String half, Map<String, Double> x, Random rnd) {
        Map<String, Double> c = coef.get(sp + "_" + half);
        if (c == null) return 0;
        double v = 0;
        for (String var : SPEC.get(sp)) v += c.getOrDefault("b_" + var, 0.0) * x.getOrDefault(var, 0.0);
        // offset and spread: a row keyed by the tour purpose (HBO_RECREATION_out, second pass 2026-10-22: the pooled HBO
        // specification gets one offset per purpose) takes precedence over the row of the stop specification (HBO_out)
        String kp = sp + "_" + tourPurpose + "_" + half, ks = sp + "_" + half;
        double d = offset.containsKey(kp) ? offset.get(kp) : offset.getOrDefault(ks, 0.0);
        // spread widens/narrows the 1-vs-2-stop split independently of the any-stop
        // propensity (negative spread -> chained tours carry more stops), so the
        // multi-stop tour SHARE and the stops-per-tour mean can be matched jointly
        double s = spread.containsKey(kp) ? spread.get(kp) : spread.getOrDefault(ks, 0.0);
        double t1 = c.get("tau_1"), t2 = c.get("tau_2");
        double cdf0 = 1.0 / (1.0 + Math.exp(-(t1 - (v + d))));
        double cdf1 = 1.0 / (1.0 + Math.exp(-(t2 + s - (v + d))));
        double u = rnd.nextDouble();
        return u < cdf0 ? 0 : u < cdf1 ? 1 : 2;
    }

    private boolean addStop(Plan plan, Tour tour, boolean outbound, String sp, Purpose tourPurpose, Random rnd) {
        if (tour.getActivities().isEmpty() || tour.getLegs().isEmpty()) return false;
        Activity stop = new Activity(tour.getMainActivity().getPerson(), drawStopPurpose(sp, tourPurpose, outbound, rnd));
        stop.setDiscretionaryActivityType(DiscretionaryActivityType.ON_MANDATORY_TOUR);
        stop.setDayOfWeek(tour.getMainActivity().getDayOfWeek());
        // Corridor rubber-band: place the stop on a real intermediate zone along the home<->main
        // segment (was: pinned to the main-activity zone, which gave 0-distance stop legs and
        // collapsed the purpose trip-length means). Location is that zone's centroid.
        MicroscopicLocation homeLoc = plan.getDummyHomeActivity() != null
                ? (MicroscopicLocation) plan.getDummyHomeActivity().getLocation()
                : (MicroscopicLocation) tour.getMainActivity().getPerson().getHousehold().getLocation();
        MicroscopicLocation mainLoc = (MicroscopicLocation) tour.getMainActivity().getLocation();
        if (mnlDc != null && MarylandDestinationChoice.hasStopModel(stop.getPurpose()))
            stop.setLocation(mnlDc.selectStopZoneMnl(tour.getMainActivity().getPerson(), tour, stop.getPurpose(), outbound, homeLoc, mainLoc, rnd));
        else stop.setLocation(intermediateLocation(homeLoc, mainLoc, rnd));
        stop.setStartTime_min(0);
        stop.setEndTime_min(15);
        try {
            if (outbound) planTools.addStopBefore(plan, stop, tour);
            else planTools.addStopAfter(plan, stop, tour);
            return true;
        } catch (Exception e) {
            return false;
        }
    }
}
