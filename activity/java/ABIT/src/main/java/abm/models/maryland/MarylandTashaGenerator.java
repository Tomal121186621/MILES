package abm.models.maryland;

import abm.data.DataSet;
import abm.data.geo.Location;
import abm.data.geo.MicroscopicLocation;
import abm.data.geo.Zone;
import abm.data.plans.*;
import abm.data.pop.Household;
import abm.data.pop.Person;
import abm.models.ModelSetup;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;
import de.tum.bgu.msm.data.person.Occupation;
import org.apache.log4j.Logger;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.PrintWriter;
import java.time.DayOfWeek;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicLongArray;

/**
 * TASHA-style activity generation and scheduling for the Maryland use case (Validation_2026 stage 3, 2026-10-22), after
 * Roorda, Miller &amp; Habib (2008), Transportation Research Part A 42, 360-375, pp. 362-364, and Miller &amp; Roorda (2003).
 * Switched on by the property {@code tasha.generation = true} (RunAbitMarylandLos); it then replaces PlanGenerator (frequency,
 * day-of-week and time assignment, PlanTools insertion) and MarylandStopModel.  Without the property nothing changes.
 *
 * <p>Activity generation: random draws from the observed joint distributions of the estimation half of the 2017/18 RTS
 * (3_abit/tasha_distributions.py; files in the directory {@code tasha.dir}):
 * <ol><li>frequency of each activity type, P(n | type, person segment, household class, prior band), prior band = number of
 *     episodes of the types that precede the type in the precedence order (TASHA's schedule attribute); joint activities are
 *     generated once per household, P(n | type, household composition, workers), with their participants;</li>
 * <li>start time given frequency, P(15-min arrival bin | type, segment, frequency, episode index, schedule attribute: none /
 *     only other / work-or-school episodes earlier in the precedence order);</li>
 * <li>duration given start time, P(duration | type, segment, start band, frequency 1 / 2+).</li></ol>
 * Each lookup falls back to the next coarser cell when the cell has fewer records than the minimum (the fallback order is the
 * order of the levels in the files; the level used is counted and written to output/tasha_summary.csv).
 *
 * <p>Activity types and precedence (TASHA's list; the 'other' categories split by ABIT purpose): WB work business, WAHB
 * work-at-home business, PW primary work (usual workplace, start before 15:00), SW secondary work (usual workplace, from 15:00),
 * RHW return home from work, SCH school (also enrolled workers, non-workers, daycare / preschool of under-5s), JO_REC / JO_OTH
 * joint other, JS joint shopping, IO_REC / IO_ACC / IO_OTH individual other, IS individual shopping.  The workplace type of a
 * worker (usual workplace / at home / none) is a person attribute drawn from P(type | age band) of the survey workers.
 *
 * <p>Location (before scheduling, as in TASHA): PW / SW the usual workplace (SILO job); SCH the school record, else (and for
 * WB, WAHB, daycare) a distance-band model: P(car-distance band | type, origin) of the survey times the attraction of the zones
 * in the band (WB from the usual workplace for workers with one, else from home); discretionary types: the model's destination
 * choice from home (the estimated MNL when dest.choice.model = mnl); RHW at home.  After the tours are formed, a chained
 * discretionary episode that is not the main activity of its tour is relocated with the estimated stop MNL (detour between home
 * and the main activity; {@code relocate.stops}; the direction for improvement that Roorda et al. give first).
 *
 * <p>Scheduling (rule based, TASHA): the episodes enter the schedules type by type in the order of precedence; a schedule
 * starts as one at-home episode.  An episode that conflicts with the episodes already scheduled (including the travel between
 * them) is accommodated by (1) moving the previous episode earlier and the next one later, as far as their own neighbours allow
 * and by at most {@code max.shift.min} (30) min from their drawn start, (2) shortening the previous, the new and the next episode
 * to at least {@code shorten.min.frac} (50 %) of their original duration (with {@code protect.precedence}, a neighbour of higher
 * precedence than the new episode is shifted but not shortened), and otherwise (3) it is rejected and regenerated (new start
 * time and duration) up to {@code max.regenerate} (10) times.  A joint episode is inserted into the schedules of all its
 * participants together and is rolled back and regenerated jointly; a participant is dropped only after the regenerations.
 * Clean-up: primary / secondary work episodes of {@code cleanup.work.max.min} (30) min or less are removed; an RHW without work on
 * both sides is dropped.  Tours: between two consecutive out-of-home episodes the person returns home when an at-home stay drawn
 * from the observed at-home durations between two out-of-home episodes (type HOME, by arrival band; times
 * {@code home.stay.factor}) fits into the time left after the travel via home; otherwise the person travels directly, the
 * episode of lower precedence moves towards the other by {@code chain.slack.to.next} (0.5) of the slack and the earlier one stays
 * until it is time to leave.  The main activity of a tour is its work episode (PW, SW, WB, WAHB, in this order), else its school
 * episode, else its longest episode; the others are its stops.  Tour mode: the model's tour mode choice.
 *
 * <p>Work-based subtours (2026-11-03, {@code subtour.file} in tasha_params): once the work episodes are scheduled, each work
 * episode at the usual workplace gets an outing with the estimated logit (work duration, arrival, secondary work, age, cars,
 * children, workplace density, commute distance); the outing's stops, purposes, departure and durations come from the
 * distributions of the estimation half, the first stop from the estimated MNL OTHER_wbs anchored at the workplace, further stops
 * from the sequential stop MNL; the work episode is split around it and the outing is chained directly (no return-home
 * decision); its legs walk with the estimated logit, else keep the work tour's mode.  The survey distributions see the merged work
 * episode (tasha_distributions.subtours).  Joint episodes: one draw per joint episode and side is shared by its participants in
 * the return-home decision ({@code joint.common.draws}); the return-home logit has joint interaction terms.  Accompany
 * frequency of persons 16+ by driving licence.
 *
 * <p>Transit leg modes (2026-11-03, {@code transit.legmode.file} in tasha_params or the property of the same name; absent = every
 * leg keeps the tour mode): after the household stage of the tour mode choice and the outing modes, each leg of a bus or train
 * tour (outing legs excluded) gets its mode from the multinomial logit of 3_abit/tasha_estimation/estimate_transit_legs.py
 * (estimation half of the RTS): transit (the tour mode), walk, car passenger, car driver, bike; legs in time order, with the mode
 * of the previous leg and, on the last leg, a car-driver first leg in the utility.  Availability: walk up to walk.max.km, bike up
 * to bike.max.km, car driver for persons 16+ with a licence when a household car is free during the tour (the car-driver tours
 * of the household and earlier transit tours with a car-driver leg hold the cars, as in the household stage); transit and car
 * passenger always.  A leg whose zones are outside the LOS matrices keeps the tour mode.  The draws use a stream of their own
 * (household id and day), so every other draw of the generator is unchanged.
 *
 * <p>Calibration variant (optional): property {@code tasha.freq.factors} = file type,segment,factor; the frequency of the type
 * for the segment (segment * = all; joint types: household) is scaled by the factor (factor &lt;= 1: binomial thinning of the
 * drawn count; &gt; 1: a second independent draw is added with probability factor - 1), so the mean scales by the factor.
 */
public class MarylandTashaGenerator {

    private static final Logger logger = Logger.getLogger(MarylandTashaGenerator.class);

    static final String[] TYPES = {"WB", "WAHB", "PW", "SW", "RHW", "SCH", "JO_REC", "JO_OTH", "JS", "IO_REC", "IO_ACC", "IO_OTH", "IS"};
    static final Set<String> JOINT = new HashSet<>(Arrays.asList("JO_REC", "JO_OTH", "JS"));
    static final Set<String> WORKT = new HashSet<>(Arrays.asList("WB", "WAHB", "PW", "SW"));
    private static final Map<String, Purpose> PURPOSE = new HashMap<>();
    static {
        PURPOSE.put("WB", Purpose.WORK); PURPOSE.put("WAHB", Purpose.WORK); PURPOSE.put("PW", Purpose.WORK); PURPOSE.put("SW", Purpose.WORK);
        PURPOSE.put("RHW", Purpose.HOME); PURPOSE.put("SCH", Purpose.EDUCATION); PURPOSE.put("JO_REC", Purpose.RECREATION);
        PURPOSE.put("JO_OTH", Purpose.OTHER); PURPOSE.put("JS", Purpose.SHOPPING); PURPOSE.put("IO_REC", Purpose.RECREATION);
        PURPOSE.put("IO_ACC", Purpose.ACCOMPANY); PURPOSE.put("IO_OTH", Purpose.OTHER); PURPOSE.put("IS", Purpose.SHOPPING);
    }
    private static final String[] WTYPES = {"worker_usual", "worker_home", "worker_none"};

    // ------------------------------------------------------------------------------------------------ distributions
    private final Map<String, double[]> freqP = new HashMap<>(), freqH = new HashMap<>(), startD = new HashMap<>(), durD = new HashMap<>();
    private final Map<String, double[]> partK = new HashMap<>(), locBand = new HashMap<>();
    private final Map<String, Double> propensity = new HashMap<>(), factor = new HashMap<>();
    private double[] durEdges; private double[] startBands; private int[] wAge; private final List<double[]> wShares = new ArrayList<>();
    private double[] distLo;
    private double homeMinSlack = 15, homeStayFactor = 1.0, shortenFrac = 0.5; private boolean relocateStops = true; private int maxShift = 60; private boolean protect = false; private double slackToNext = 1.0; private int maxRegen = 10, cleanupWork = 30, startStep = 15;
    private static final int DAY_END_EXTRA = 180;   // an activity may end up to 03:00 of the next day
    // 2026-10-23 (finalisation): estimated return-home rule, conditional regeneration, estimated anchored locations, diagnostics
    private final Map<String, Double> rhCoef = new LinkedHashMap<>(); private double rhMinSlack = 5; private double attK = 0, attQ0 = 0, attCap = 0.6; private String attFile = null; private final Map<Integer, Double> zoneWfh = new HashMap<>();
    private final AtomicLong nAttHome = new AtomicLong(), nAttWorkers = new AtomicLong();
    private boolean jointCommonDraws = false, rhHonor = false; private final AtomicLong nRhHonored = new AtomicLong();
    private boolean regenCond = false, regenBand = false, relocateJoint = false, jointAnyStop = false;
    private boolean episodesOut = false; private final java.util.concurrent.ConcurrentLinkedQueue<String> epLines = new java.util.concurrent.ConcurrentLinkedQueue<>();
    private final AtomicLong nMainReloc = new AtomicLong(), nRegenBand = new AtomicLong(), nJointReloc = new AtomicLong(), nRegenCond = new AtomicLong(), nRegenNoWindow = new AtomicLong(), nRhLogit = new AtomicLong(), nRhInfeasible = new AtomicLong(), nLocMnl = new AtomicLong();
    static final String[] RH_VARS = {"const", "sl_0_05", "sl_05_1", "sl_1_2", "sl_2_4", "sl_4_inf", "lnslack", "detour_km", "lndetour", "dhome_km",
            "a_work", "a_school", "a_acc", "a_shop", "a_joint", "e_work", "e_school", "e_acc", "e_shop", "e_joint",
            "worker", "stud_k12", "stud_ps", "retiree", "toddler", "nep3", "nep4", "nep5", "am", "pm", "ev", "jj", "jmand",
            // re-specified return-home logit (2026-11-09, respec_2026-11/step_by_step/activity/a03_return.py, 3_abit/coef_respec): female,
            // driving licence, household size, a household member under 16, no car, fewer cars than licensed drivers, household
            // income < $50k / >= $100k (12 x the members' monthly incomes), number of out-of-home episodes of the day
            "female", "lic", "hhsize", "kids", "car0", "carshort", "inc_low", "inc_high", "nep"};
    // tasha.debug.file (2026-11-09, unit check of the re-specified models): the inputs and utilities of the first tasha.debug.n
    // (default 200) evaluations of the return-home logit (RH), the outing logit (WBSGEN) and the outing-mode logit (WBSMODE)
    /** types whose person frequency has licence cells first (tasha_params freq.licence.types, ';'-separated; default IO_ACC as
     *  before; coef_respec 2026-11-10: IO_ACC;IS;IO_REC;IO_OTH) */
    private final Set<String> licTypes = new HashSet<>(Collections.singletonList("IO_ACC"));
    private boolean jointFreqMand = false; private final Map<String, AtomicLong> nJointBand = new java.util.concurrent.ConcurrentHashMap<>();
    private boolean jointMembersMand = false; private final Map<String, Double> propMand = new HashMap<>();
    private void loadPropMand(String f) {
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            Map<String, Integer> h = header(br.readLine()); String line;
            while ((line = br.readLine()) != null) { if (line.isBlank()) continue; String[] r = line.split(","); propMand.put(r[h.get("seg")].trim(), Double.parseDouble(r[h.get("propensity")].trim())); }
        } catch (Exception e) { throw new RuntimeException("joint.propensity.mand.file: " + f, e); }
    }
    private boolean jointStartCond = false; static final Set<String> MANDT = new HashSet<>(Arrays.asList("WB", "WAHB", "PW", "SW", "SCH"));
    private final AtomicLong nJointStartM = new AtomicLong(), nJointStartN = new AtomicLong(), nJointStartCell = new AtomicLong();
    private String dbgFile = null; private int dbgN = 200; private final Map<String, AtomicLong> dbgCount = new java.util.concurrent.ConcurrentHashMap<>();
    private void dbg(String tag, String line) {
        if (dbgFile == null || dbgCount.computeIfAbsent(tag, k -> new AtomicLong()).getAndIncrement() >= dbgN) return;
        synchronized (this) { try (java.io.PrintWriter pw = new java.io.PrintWriter(new java.io.FileWriter(dbgFile, true))) { pw.println(tag + "," + line); } catch (Exception ignored) { } }
    }
    /** household attributes of the re-specified activity models: {female, lic, hhsize, kids (a member under 16), cars, licensed drivers, annual income} */
    private static double[] hhAttrs(Person p) {
        Household hh = p.getHousehold(); int d = 0; boolean u16 = false; double inc = 0;
        for (Person q : hh.getPersons()) { if (q.isHasLicense()) d++; if (q.getAge() < 16) u16 = true; inc += q.getMonthlyIncome_eur(); }
        return new double[]{p.getGender() == de.tum.bgu.msm.data.person.Gender.FEMALE ? 1 : 0, p.isHasLicense() ? 1 : 0, hh.getPersons().size(), u16 ? 1 : 0, hh.getNumberOfCars(), d, 12 * inc};
    }

    // counters: fallback level used per family (frequency person 0..5, household 0..2, start 0..4, duration 0..3)
    private final AtomicLongArray fbFreq = new AtomicLongArray(9), fbFreqH = new AtomicLongArray(3), fbStart = new AtomicLongArray(6), fbDur = new AtomicLongArray(5);
    private final AtomicLong nFreqLic = new AtomicLong(), nRhTight = new AtomicLong(); private final java.util.concurrent.atomic.DoubleAdder rhTightP = new java.util.concurrent.atomic.DoubleAdder();
    private final AtomicLong nGen = new AtomicLong(), nIns = new AtomicLong(), nShift = new AtomicLong(), nShorten = new AtomicLong(), nRegen = new AtomicLong(),
            nReject = new AtomicLong(), nClean = new AtomicLong(), nHomeBreak = new AtomicLong(), nDirect = new AtomicLong(), nJointDrop = new AtomicLong(), nReloc = new AtomicLong();
    private final Map<String, AtomicLong> genByType = new java.util.concurrent.ConcurrentHashMap<>(), schedByType = new java.util.concurrent.ConcurrentHashMap<>();

    private final DataSet dataSet;
    private final ModelSetup setup;
    private final List<Zone> zones;
    private final MicroscopicLocation[] zoneLoc;
    private final double[] intraKm;
    private final Map<Integer, Integer> zIdx = new HashMap<>();
    private final Map<Integer, byte[]> bandCache = new java.util.concurrent.ConcurrentHashMap<>();
    private final Map<String, double[]> attraction = new HashMap<>();
    private final int days;
    private boolean hasHomeDur = false;

    public MarylandTashaGenerator(DataSet dataSet, ModelSetup setup) {
        this.dataSet = dataSet; this.setup = setup;
        String dir = AbitResources.instance.getString("tasha.dir");
        if (dir == null || dir.isBlank()) throw new RuntimeException("tasha.generation = true requires tasha.dir");
        this.days = Math.max(1, Math.min(5, AbitResources.instance.getInt("tasha.days", 1)));
        loadParams(dir + "/tasha_params.csv");
        try {   // property transit.legmode.file (absolute path; 'none' switches the component off) overrides tasha_params
            String tl = AbitResources.instance.getString("transit.legmode.file");
            if (tl != null && !tl.isBlank()) { if (tl.trim().equalsIgnoreCase("none")) { tlOn = false; } else loadTransitLegs(tl.trim()); }
        } catch (Exception e) { if (e instanceof RuntimeException && e.getMessage() != null && e.getMessage().startsWith("transit.legmode")) throw (RuntimeException) e; }
        loadDist(dir + "/tasha_frequency.csv", true);
        loadDist(dir + "/tasha_start.csv", false);
        loadDist(dir + "/tasha_duration.csv", false);
        loadSmall(dir);
        hasHomeDur = durD.containsKey("HOME|*|*|*");
        try { episodesOut = Boolean.parseBoolean(String.valueOf(AbitResources.instance.getString("tasha.episodes.out")).trim()); } catch (Exception ignored) { }
        try { String af = AbitResources.instance.getString("tasha.attendance.file"); if (af != null && !af.isBlank()) attFile = af.trim(); } catch (Exception ignored) { }
        if (attFile != null) loadAttendance(attFile);
        String ff = AbitResources.instance.getString("tasha.freq.factors");
        if (ff != null && !ff.isBlank()) loadFactors(ff);
        zones = new ArrayList<>(dataSet.getZones().values());
        zoneLoc = new MicroscopicLocation[zones.size()]; intraKm = new double[zones.size()];
        for (int i = 0; i < zones.size(); i++) {
            Zone z = zones.get(i); zIdx.put(z.getZoneId(), i);
            double x = z.getAttribute("x").map(o -> (double) o).orElse(0.0), y = z.getAttribute("y").map(o -> (double) o).orElse(0.0);
            zoneLoc[i] = new MicroscopicLocation(x, y); zoneLoc[i].setZone(z);
            intraKm[i] = z.getAreaKm2() > 0 ? 0.5 * Math.sqrt(z.getAreaKm2()) : 1.0;
        }
        attraction.put("WB", attr("jj.total")); attraction.put("WAHB", attraction.get("WB")); attraction.put("SCH", attr("students"));
        double[] dc = attr("hh.total"), jj = attraction.get("WB"); double[] d2 = new double[dc.length];
        for (int i = 0; i < dc.length; i++) d2[i] = dc[i] + jj[i];
        attraction.put("DAYCARE", d2);
        logger.info("TASHA generator: " + freqP.size() + " person frequency, " + freqH.size() + " household frequency, " + startD.size() + " start-time, "
                + durD.size() + " duration distributions; " + days + " weekday(s); home.min.slack " + homeMinSlack + " min; factors " + factor.size()
                + "; return-home logit " + (rhCoef.isEmpty() ? "off" : rhCoef.size() + " terms") + "; conditional regeneration " + regenCond + "; episodes output " + episodesOut);
    }

    private double[] attr(String key) {
        double[] a = new double[zones.size()];
        for (int i = 0; i < zones.size(); i++) a[i] = zones.get(i).getAttribute(key).map(o -> ((Number) o).doubleValue()).orElse(0.0);
        return a;
    }

    // ------------------------------------------------------------------------------------------------ loading
    private static double[] parse(String s) {
        String[] p = s.split(";"); double[] v = new double[p.length];
        for (int i = 0; i < p.length; i++) v[i] = Double.parseDouble(p[i].trim());
        return v;
    }

    private static double[] cdf(double[] p) {
        double[] c = new double[p.length]; double s = 0;
        for (int i = 0; i < p.length; i++) { s += p[i]; c[i] = s; }
        if (s <= 0) return null;
        for (int i = 0; i < c.length; i++) c[i] /= s;
        return c;
    }

    private static Map<String, Integer> header(String line) {
        Map<String, Integer> h = new HashMap<>(); String[] c = line.split(",");
        for (int i = 0; i < c.length; i++) h.put(c[i].trim(), i);
        return h;
    }

    private void loadParams(String f) {
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            br.readLine(); String line;
            while ((line = br.readLine()) != null) {
                int k = line.indexOf(','); String key = line.substring(0, k).trim(), v = line.substring(k + 1).trim();
                switch (key) {
                    case "home.min.slack": homeMinSlack = Double.parseDouble(v); break;
                    case "home.stay.factor": homeStayFactor = Double.parseDouble(v); break;
                    case "relocate.stops": relocateStops = Boolean.parseBoolean(v); break;
                    case "max.shift.min": maxShift = (int) Double.parseDouble(v); break;
                    case "protect.precedence": protect = Boolean.parseBoolean(v); break;
                    case "chain.slack.to.next": slackToNext = Double.parseDouble(v); break;
                    case "shorten.min.frac": shortenFrac = Double.parseDouble(v); break;
                    case "max.regenerate": maxRegen = (int) Double.parseDouble(v); break;
                    case "cleanup.work.max.min": cleanupWork = (int) Double.parseDouble(v); break;
                    case "start.step": startStep = (int) Double.parseDouble(v); break;
                    case "home.return.file": if (!v.isBlank()) loadReturnHome(new java.io.File(f).getParent() + "/" + v); break;
                    case "home.return.min.slack": rhMinSlack = Double.parseDouble(v); break;
                    case "regen.conditional": regenCond = Boolean.parseBoolean(v); break;
                    case "regen.band.first": regenBand = Boolean.parseBoolean(v); break;
                    case "attendance.file": if (!v.isBlank()) attFile = v.startsWith("/") ? v : new java.io.File(f).getParent() + "/" + v; break;
                    case "attendance.k": attK = Double.parseDouble(v); break;
                    case "attendance.q0": attQ0 = Double.parseDouble(v); break;
                    case "attendance.cap": attCap = Double.parseDouble(v); break;
                    case "relocate.joint": relocateJoint = Boolean.parseBoolean(v); break;
                    case "joint.common.draws": jointCommonDraws = Boolean.parseBoolean(v); break;
                    case "home.return.honor": rhHonor = Boolean.parseBoolean(v); break;
                    case "subtour.file": if (!v.isBlank()) loadSubtours(new java.io.File(f).getParent() + "/" + v); break;
                    case "debug.file": dbgFile = v.isBlank() ? null : v; break;
                    case "joint.start.conditional": jointStartCond = Boolean.parseBoolean(v); break;
                    case "joint.members.mandatory": jointMembersMand = Boolean.parseBoolean(v); break;
                    case "joint.freq.mandatory": jointFreqMand = Boolean.parseBoolean(v); break;
                    case "joint.propensity.mand.file": if (!v.isBlank()) loadPropMand(new java.io.File(f).getParent() + "/" + v); break;
                    case "freq.licence.types": licTypes.clear(); for (String q : v.split(";")) if (!q.isBlank()) licTypes.add(q.trim()); break;
                    case "debug.n": dbgN = (int) Double.parseDouble(v); break;
                    case "transit.legmode.file": if (!v.isBlank()) loadTransitLegs(new java.io.File(f).getParent() + "/" + v); break;
                    case "relocate.joint.mode": jointAnyStop = v.trim().equalsIgnoreCase("anystop"); break;
                    case "duration.edges": durEdges = parse(v); break;
                    case "start.bands": startBands = parse(v); break;
                    case "worker.age.bands": { double[] a = parse(v); wAge = new int[a.length]; for (int i = 0; i < a.length; i++) wAge[i] = (int) a[i]; break; }
                    case "dist.bins": distLo = parse(v); break;
                    default:
                        if (key.startsWith("worker.type.share.")) {
                            int i = Integer.parseInt(key.substring("worker.type.share.".length()));
                            while (wShares.size() <= i) wShares.add(null);
                            wShares.set(i, cdf(parse(v)));
                        }
                }
            }
        } catch (Exception e) { throw new RuntimeException("tasha params load failed: " + f, e); }
    }

    /** Work attendance (2026-10-23): county work-at-home shares p_c of the simulated year (countyfips,p; property
     *  tasha.attendance.file overrides the file of tasha_params) mapped to the zones through zone.attributes.file. */
    private void loadAttendance(String f) {
        Map<Integer, Double> cp = new HashMap<>();
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            Map<String, Integer> h = header(br.readLine()); String line;
            while ((line = br.readLine()) != null) { if (line.isBlank()) continue; String[] r = line.split(","); cp.put(Integer.parseInt(r[h.get("countyfips")].trim()), Double.parseDouble(r[h.get("p")].trim())); }
        } catch (Exception e) { throw new RuntimeException("attendance file load failed: " + f, e); }
        String zf = AbitResources.instance.getString("zone.attributes.file");
        try (BufferedReader br = new BufferedReader(new FileReader(zf))) {
            Map<String, Integer> h = header(br.readLine()); String line;
            while ((line = br.readLine()) != null) { String[] r = line.split(","); Double p = cp.get(Integer.parseInt(r[h.get("countyfips")].trim())); if (p != null) zoneWfh.put(Integer.parseInt(r[h.get("id")].trim()), p); }
        } catch (Exception e) { throw new RuntimeException("zone.attributes.file (attendance) failed: " + zf, e); }
        logger.info("TASHA attendance: " + cp.size() + " counties, " + zoneWfh.size() + " zones from " + f + "; k " + attK + ", q0 " + attQ0);
    }

    /** P(at the usual workplace today) = (1 - min(cap, k p_c)) (1 - q0); 1 when the attendance step is off */
    private double attendProb(Location home) {
        if (attFile == null) return 1.0;
        Double p = zoneWfh.get(home.getZoneId()); double pc = p == null ? 0.0 : p;
        return (1 - Math.min(attCap, attK * pc)) * (1 - attQ0);
    }

    /** estimated binary logit of a return home between two consecutive out-of-home episodes (variable,value; RH_VARS) */
    private void loadReturnHome(String f) {
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            Map<String, Integer> h = header(br.readLine()); String line;
            while ((line = br.readLine()) != null) {
                if (line.isBlank()) continue; String[] r = line.split(",");
                String k = r[h.get("variable")].trim();
                if (!Arrays.asList(RH_VARS).contains(k)) throw new RuntimeException("unknown return-home variable " + k);
                rhCoef.put(k, Double.parseDouble(r[h.get("value")].trim()));
            }
        } catch (Exception e) { throw new RuntimeException("home.return.file load failed: " + f, e); }
    }

    // ------------------------------------------------------------------------------------------------ work-based subtours
    // (2026-11-03; 3_abit/tasha_estimation/estimate_subtours.py, estimation half of the RTS): binary logit of an outing from the
    // usual workplace during a work episode, distributions of the outings, stops, purposes, departures and stop durations, binary
    // logit of walking on the outing against keeping the mode of the work tour
    static final String[] WBS_PURP = {"IS", "IO_REC", "IO_OTH", "IO_ACC"};
    /** person / household terms of the outing-mode logit evaluated with wbsVar (2026-11-09); multi and km separately */
    static final String[] WBS_MODE_HH = {"car0", "carshort", "age_u30", "age_55p", "female", "inc_low", "inc_high", "kids"};
    static final Set<String> WBS_MODE_KEYS = new HashSet<>(Arrays.asList("const", "lnkm", "km", "cbd_w", "lnretden_w", "tm_cd", "tm_cp", "multi",
            "car0", "carshort", "age_u30", "age_55p", "female", "inc_low", "inc_high", "kids"));
    private final Map<String, Double> wbsGen = new HashMap<>(), wbsMode = new HashMap<>();
    private double[] wbsNOut, wbsNStops, wbsLeave, wbsDurEdges; private final Map<String, double[]> wbsPurp = new HashMap<>(), wbsDur = new HashMap<>();
    private int wbsMinBefore = 45, wbsMinAfter = 45; private double wbsAccKm = 2; private boolean wbsOn = false;
    private double[] zoneCbd, zoneRetDen;
    private final AtomicLong nWbsEp = new AtomicLong(), nWbsOut = new AtomicLong(), nWbsStops = new AtomicLong(), nWbsNoFit = new AtomicLong(), nWbsWalk = new AtomicLong(), nWbsOutMode = new AtomicLong();

    private void loadSubtours(String f) {
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            br.readLine(); String line;
            while ((line = br.readLine()) != null) {
                if (line.isBlank()) continue; int k = line.indexOf(','); String key = line.substring(0, k).trim(), v = line.substring(k + 1).trim();
                if (key.startsWith("gen.")) wbsGen.put(key.substring(4), Double.parseDouble(v));
                else if (key.startsWith("mode.")) wbsMode.put(key.substring(5), Double.parseDouble(v));
                else if (key.equals("n.outings")) wbsNOut = cdf(parse(v));
                else if (key.equals("n.stops")) wbsNStops = cdf(parse(v));
                else if (key.equals("leave")) wbsLeave = parse(v);
                else if (key.startsWith("purpose.")) wbsPurp.put(key.substring(8), cdf(parse(v)));
                else if (key.equals("dur.edges")) wbsDurEdges = parse(v);
                else if (key.startsWith("dur.")) wbsDur.put(key.substring(4), cdf(parse(v)));
                else if (key.equals("min.before")) wbsMinBefore = (int) Double.parseDouble(v);
                else if (key.equals("min.after")) wbsMinAfter = (int) Double.parseDouble(v);
                else if (key.equals("acc.km")) wbsAccKm = Double.parseDouble(v);
            }
        } catch (Exception e) { throw new RuntimeException("subtour.file load failed: " + f, e); }
        wbsOn = !wbsGen.isEmpty();
        for (String k : wbsMode.keySet()) if (!WBS_MODE_KEYS.contains(k)) throw new RuntimeException("unknown outing-mode variable mode." + k + " in " + f);
    }

    /** zone variables of the workplace (lazy): cbd = at least 10,000 jobs per km2, ln(1 + retail jobs per km2) */
    private synchronized void zoneDensity() {
        if (zoneCbd != null) return;
        double[] cbd = new double[zones.size()], rd = new double[zones.size()];
        for (int i = 0; i < zones.size(); i++) {
            Zone z = zones.get(i); double area = Math.max(z.getAreaKm2(), 0.05);
            double ret = z.getAttribute("jj.retail").map(o -> ((Number) o).doubleValue()).orElse(0.0), off = z.getAttribute("jj.office").map(o -> ((Number) o).doubleValue()).orElse(0.0),
                   oth = z.getAttribute("jj.other").map(o -> ((Number) o).doubleValue()).orElse(0.0);
            cbd[i] = (ret + off + oth) / area >= 10000 ? 1 : 0; rd[i] = Math.log1p(ret / area);
        }
        zoneRetDen = rd; zoneCbd = cbd;
    }

    private double wbsVar(String k, Person p, Household hh, Ep w, Location home, Location work) {
        double h = w.dur() / 60.0;
        switch (k) {
            case "const": return 1;
            case "sp_0_4": return Math.min(h, 4); case "sp_4_7": return Math.max(0, Math.min(h, 7) - 4); case "sp_7_inf": return Math.max(0, h - 7);
            case "arr_early": return w.start < 420 ? 1 : 0; case "arr_late": return w.start >= 600 ? 1 : 0; case "sw": return w.type.equals("SW") ? 1 : 0;
            case "age_u30": return p.getAge() < 30 ? 1 : 0; case "age_55p": return p.getAge() >= 55 ? 1 : 0;
            case "female": return p.getGender() == de.tum.bgu.msm.data.person.Gender.FEMALE ? 1 : 0;
            case "inc_low": case "inc_high": { double inc = 0; for (Person q : hh.getPersons()) inc += q.getMonthlyIncome_eur(); inc *= 12; return k.equals("inc_low") ? (inc < 50000 ? 1 : 0) : (inc >= 100000 ? 1 : 0); }
            case "car0": return hh.getNumberOfCars() <= 0 ? 1 : 0;
            case "carshort": { int d = 0; for (Person q : hh.getPersons()) if (q.isHasLicense()) d++; return hh.getNumberOfCars() > 0 && hh.getNumberOfCars() < d ? 1 : 0; }
            case "kids": { for (Person q : hh.getPersons()) if (q.getAge() < 16) return 1; return 0; }
            case "cbd_w": { zoneDensity(); Integer i = zIdx.get(work.getZoneId()); return i == null ? 0 : zoneCbd[i]; }
            case "lnretden_w": { zoneDensity(); Integer i = zIdx.get(work.getZoneId()); return i == null ? 0 : zoneRetDen[i]; }
            case "lncomm": return Math.log1p(km(home, work));
            case "lnacc2": {
                Integer oi = zIdx.get(work.getZoneId()); if (oi == null) return 0; double s = 0;
                for (int j = 0; j < zones.size(); j++) {
                    double d = j == oi ? intraKm[oi] : km(zoneLoc[oi], zoneLoc[j]);
                    if (d <= wbsAccKm) { Zone z = zones.get(j); s += z.getAttribute("jj.retail").map(o -> ((Number) o).doubleValue()).orElse(0.0) + z.getAttribute("jj.other").map(o -> ((Number) o).doubleValue()).orElse(0.0); }
                }
                return Math.log1p(s);
            }
            default: throw new RuntimeException("unknown subtour variable " + k);
        }
    }

    private int drawBinIn(double[] p, int step, int lo, int hi, Random r) {   // minute in [lo, hi] from binned probabilities p
        if (hi < lo) return -1; double tot = 0; double[] w = new double[p.length];
        for (int k = 0; k < p.length; k++) { int a = Math.max(lo, k * step), b = Math.min(hi + 1, (k + 1) * step); if (b > a) { w[k] = p[k] * (b - a) / (double) step; tot += w[k]; } }
        if (tot <= 0) return lo + r.nextInt(hi - lo + 1);
        double u = r.nextDouble() * tot; int k = 0; for (; k < p.length - 1; k++) { u -= w[k]; if (u < 0) break; }
        int a = Math.max(lo, k * step), b = Math.min(hi + 1, (k + 1) * step); return a + r.nextInt(Math.max(1, b - a));
    }

    private static final Map<String, Purpose> WBS_DEST = new HashMap<>();
    static { WBS_DEST.put("IS", Purpose.SHOPPING); WBS_DEST.put("IO_REC", Purpose.RECREATION); WBS_DEST.put("IO_OTH", Purpose.OTHER); WBS_DEST.put("IO_ACC", Purpose.ACCOMPANY); }

    /** Outings from the usual workplace (work-based subtours): for each work episode at the usual workplace, the estimated logit
     *  of an outing; then the outings (1 or 2), their stops (1-3), purposes, departure (restricted to the work episode with at least
     *  min.before / min.after minutes of work before / after) and stop durations from the distributions of the estimation half;
     *  first stop from the estimated MNL segment OTHER_wbs anchored at the workplace (else the primary MNL of the purpose), further
     *  stops from the sequential stop MNL between the previous stop and the workplace.  The work episode is split into the work
     *  before the outing, the stops, and the continuation.  Durations are shortened proportionally (at least 5 min) when the outing
     *  does not fit; else the outing is dropped. */
    private void subtours(Person p, String sg, List<Ep> sc, Location home, Location work, Household hh, int off, Random r, int[] outingId) {
        if (!wbsOn || work == null || !(setup.getDestinationChoice() instanceof MarylandDestinationChoice)) return;
        MarylandDestinationChoice dc = (MarylandDestinationChoice) setup.getDestinationChoice();
        List<Ep> roots = new ArrayList<>(); for (Ep e : sc) if ((e.type.equals("PW") || e.type.equals("SW")) && e.loc == work && !e.cont) roots.add(e);
        for (Ep w0 : roots) {
            nWbsEp.incrementAndGet();
            double v = 0; for (Map.Entry<String, Double> en : wbsGen.entrySet()) v += en.getValue() * wbsVar(en.getKey(), p, hh, w0, home, work);
            if (dbgFile != null) { double[] ha = hhAttrs(p); dbg("WBSGEN", p.getId() + "," + w0.type + "," + w0.start + "," + w0.dur() + "," + home.getZoneId() + "," + work.getZoneId() + ","
                    + p.getAge() + "," + ha[0] + "," + ha[6] + "," + ha[4] + "," + ha[5] + "," + ha[3] + "," + v); }
            if (r.nextDouble() >= 1.0 / (1.0 + Math.exp(-v))) continue;
            int nOut = 1 + (wbsNOut == null ? 0 : drawIndex(wbsNOut, r));
            Ep w = w0;
            for (int o = 0; o < nOut; o++) {
                int lo = w.start + wbsMinBefore, hi = w.end - wbsMinAfter - 20; if (o == 0 && nOut > 1) hi = Math.min(hi, (w.start + w.end) / 2);
                int leave = drawBinIn(wbsLeave, 15, lo, hi, r); if (leave < 0) { nWbsNoFit.incrementAndGet(); break; }
                int ns = 1 + (wbsNStops == null ? 0 : drawIndex(wbsNStops, r)); String band = leave < 660 ? "0" : leave < 840 ? "1" : "2";
                String[] ty = new String[ns]; int[] du = new int[ns]; Location[] loc = new Location[ns];
                Location prev = work; int t = leave;
                for (int k = 0; k < ns; k++) {
                    double[] pc = wbsPurp.getOrDefault(band, wbsPurp.get("1")); ty[k] = WBS_PURP[drawIndex(pc, r)];
                    double[] dcdf = wbsDur.get(ty[k]); int bi = drawIndex(dcdf, r);
                    du[k] = (int) Math.max(1, Math.round(wbsDurEdges[bi] + r.nextDouble() * (wbsDurEdges[Math.min(bi + 1, wbsDurEdges.length - 1)] - wbsDurEdges[bi])));
                    Purpose dp = WBS_DEST.get(ty[k]);
                    if (k == 0 && MarylandDestinationChoice.hasSegment("OTHER_wbs")) loc[k] = dc.selectAnchoredZoneMnl("OTHER_wbs", p, work, off + t, r);   // estimated on the outings' first stops
                    else if (k == 0 && MarylandDestinationChoice.hasSegment(dp + "_primary")) loc[k] = dc.selectAnchoredZoneMnl(dp + "_primary", p, work, off + t, r);
                    else if (k > 0 && MarylandDestinationChoice.hasSegment(dp + "_seq_stop")) loc[k] = dc.selectTwoAnchorZoneMnl(dp + "_seq_stop", p, prev, work, off + t, r);
                    else loc[k] = work;
                    prev = loc[k];
                }
                // timing: travel from the workplace through the stops and back
                int travel = 0; prev = work; int[] tts = new int[ns + 1];
                for (int k = 0; k < ns; k++) { tts[k] = tt(prev, loc[k], leave); travel += tts[k]; prev = loc[k]; }
                tts[ns] = tt(prev, work, leave); travel += tts[ns];
                int room = w.end - wbsMinAfter - leave - travel, sum = 0; for (int d : du) sum += d;
                if (room < 5 * ns) { nWbsNoFit.incrementAndGet(); break; }
                if (sum > room) { double f = room / (double) sum; for (int k = 0; k < ns; k++) du[k] = Math.max(5, (int) Math.floor(du[k] * f)); }
                int end0 = w.end; w.end = leave; w.root = true; int id = ++outingId[0];
                Integer wi = zIdx.get(work.getZoneId()), si = zIdx.get(loc[0].getZoneId());
                double km1 = km(work, loc[0]); zoneDensity();
                double wv = wbsMode.getOrDefault("const", 0.0) + wbsMode.getOrDefault("lnkm", 0.0) * Math.log1p(km1)
                        + wbsMode.getOrDefault("cbd_w", 0.0) * (wi == null ? 0 : zoneCbd[wi]) + wbsMode.getOrDefault("lnretden_w", 0.0) * (wi == null ? 0 : zoneRetDen[wi]);
                // re-specified outing-mode logit (2026-11-09, activity/a02_outing_mode.py): household cars and more than one stop on the outing
                for (String k2 : WBS_MODE_HH) { Double b2 = wbsMode.get(k2); if (b2 != null) wv += b2 * wbsVar(k2, p, hh, w, home, work); }
                if (wbsMode.containsKey("multi")) wv += wbsMode.get("multi") * (ns > 1 ? 1 : 0);
                if (wbsMode.containsKey("km")) wv += wbsMode.get("km") * km1;
                int cur = leave; int idx = sc.indexOf(w) + 1;
                for (int k = 0; k < ns; k++) {
                    cur += tts[k]; Ep s = new Ep(ty[k], cur, du[k], loc[k], 0); s.sub = true; s.outing = id; s.walkV0 = wv; s.src = "wbs_" + (k == 0 ? "first_stop" : "seq_stop");
                    if (dbgFile != null) s.dbg = p.getId() + "," + work.getZoneId() + "," + loc[0].getZoneId() + "," + ns;
                    sc.add(idx++, s); cur += du[k]; nWbsStops.incrementAndGet();
                }
                cur += tts[ns];
                Ep c = new Ep(w.type, cur, Math.max(1, end0 - cur), work, 0); c.cont = true; c.outing = id; c.src = "wbs_continuation";
                sc.add(idx, c); nWbsOut.incrementAndGet();
                w = c;
            }
        }
    }

    /** frequency: level,type,seg,hh,prior,n,mean,probs; start: type,seg,f,i,n,probs,level; duration: type,seg,band,n,probs,level */
    private void loadDist(String f, boolean freq) {
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            Map<String, Integer> h = header(br.readLine()); String line;
            boolean start = h.containsKey("f");
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                double[] c = cdf(parse(r[h.get("probs")]));
                if (c == null) continue;
                String ty = r[h.get("type")].trim(), seg = r[h.get("seg")].trim();
                if (freq) {
                    String key = ty + "|" + seg + "|" + r[h.get("hh")].trim() + "|" + r[h.get("prior")].trim();
                    (r[h.get("level")].trim().equals("household") ? freqH : freqP).put(key, c);
                } else if (start) startD.put(ty + "|" + seg + "|" + r[h.get("f")].trim() + "|" + r[h.get("i")].trim() + "|" + (h.containsKey("pb") ? r[h.get("pb")].trim() : "*"), c);
                else durD.put(ty + "|" + seg + "|" + r[h.get("band")].trim() + "|" + (h.containsKey("fd") ? r[h.get("fd")].trim() : "*"), c);
            }
        } catch (Exception e) { throw new RuntimeException("tasha distribution load failed: " + f, e); }
    }

    private void loadSmall(String dir) {
        try (BufferedReader br = new BufferedReader(new FileReader(dir + "/tasha_joint_participants.csv"))) {
            Map<String, Integer> h = header(br.readLine()); String line;
            while ((line = br.readLine()) != null) { String[] r = line.split(","); double[] c = cdf(parse(r[h.get("probs")])); if (c != null) partK.put(r[h.get("type")].trim() + "|" + r[h.get("hhsize")].trim(), c); }
        } catch (Exception e) { throw new RuntimeException("tasha_joint_participants.csv", e); }
        try (BufferedReader br = new BufferedReader(new FileReader(dir + "/tasha_joint_propensity.csv"))) {
            Map<String, Integer> h = header(br.readLine()); String line;
            while ((line = br.readLine()) != null) { String[] r = line.split(","); propensity.put(r[h.get("seg")].trim(), Double.parseDouble(r[h.get("propensity")].trim())); }
        } catch (Exception e) { throw new RuntimeException("tasha_joint_propensity.csv", e); }
        try (BufferedReader br = new BufferedReader(new FileReader(dir + "/tasha_location_bands.csv"))) {
            Map<String, Integer> h = header(br.readLine()); String line;
            while ((line = br.readLine()) != null) { String[] r = line.split(","); locBand.put(r[h.get("type")].trim() + "|" + r[h.get("origin")].trim(), parse(r[h.get("probs")])); }
        } catch (Exception e) { throw new RuntimeException("tasha_location_bands.csv", e); }
    }

    private void loadFactors(String f) {
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            Map<String, Integer> h = header(br.readLine()); String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                factor.put(r[h.get("type")].trim() + "|" + r[h.get("segment")].trim(), Double.parseDouble(r[h.get("factor")].trim()));
            }
        } catch (Exception e) { throw new RuntimeException("tasha.freq.factors load failed: " + f, e); }
    }

    // ------------------------------------------------------------------------------------------------ draws with fallback
    private static int drawIndex(double[] cdf, Random r) {
        double u = r.nextDouble(); int lo = 0, hi = cdf.length - 1;
        while (lo < hi) { int m = (lo + hi) >>> 1; if (cdf[m] < u) lo = m + 1; else hi = m; }
        return lo;
    }

    static String group(String seg) {
        if (seg.startsWith("worker")) return "worker";
        if (seg.startsWith("student") || seg.equals("toddler")) return "student";
        return "other";
    }

    /** P(n | type, segment, household class, prior band) with the fallback of tasha_distributions.py.  First level (2026-11-02):
     *  the mandatory band, 'M' when a work or school episode of a preceding type is in the schedule ('N' otherwise), followed by
     *  the number of the other preceding episodes (0, 1, 2+); then the band of all preceding episodes (0, 1, 2+). */
    private int drawFreq(String ty, String seg, String hhc, int prior, int mand, Random r) { return drawFreq(ty, seg, hhc, prior, mand, "", r); }

    /** lic (2026-11-03): "~L" / "~N" for a person 16+ with / without a driving licence, "" otherwise; the accompany frequency
     *  (IO_ACC) has licence cells first (tasha_distributions.py), then the cells without the licence */
    private int drawFreq(String ty, String seg, String hhc, int prior, int mand, String lic, Random r) {
        String pb = String.valueOf(Math.min(prior, 2)), g = group(seg), mb = (mand > 0 ? "M" : "N") + Math.min(Math.max(0, prior - mand), 2);
        if (!lic.isEmpty() && licTypes.contains(ty)) {
            String sl = seg + lic, gl = g + lic;
            String[] lk = {ty + "|" + sl + "|" + hhc + "|" + mb, ty + "|" + sl + "|*|" + mb, ty + "|" + gl + "|*|" + mb, ty + "|" + sl + "|*|" + pb, ty + "|" + gl + "|*|" + pb, ty + "|" + sl + "|*|*", ty + "|" + gl + "|*|*"};
            for (String k : lk) { double[] c = freqP.get(k); if (c != null) { nFreqLic.incrementAndGet(); return drawIndex(c, r); } }
        }
        String[] keys = {ty + "|" + seg + "|" + hhc + "|" + mb, ty + "|" + seg + "|*|" + mb, ty + "|" + g + "|*|" + mb,
                ty + "|" + seg + "|" + hhc + "|" + pb, ty + "|" + seg + "|*|" + pb, ty + "|" + g + "|*|" + pb, ty + "|*|*|" + pb, ty + "|" + seg + "|*|*", ty + "|*|*|*"};
        for (int l = 0; l < keys.length; l++) {
            double[] c = freqP.get(keys[l]);
            if (c != null) { fbFreq.incrementAndGet(l); return drawIndex(c, r); }
        }
        return 0;
    }

    /** household joint frequency conditional on the members' work / school that day (band MN / MS / MA; joint.freq.mandatory), then
     *  the cells without the band */
    private int drawFreqHhBand(String ty, String comp, String wk, String band, Random r) {
        for (String k : new String[]{ty + "|" + comp + "|" + wk + "|" + band, ty + "|" + comp + "|*|" + band, ty + "|*|*|" + band}) { double[] c = freqH.get(k); if (c != null) return drawIndex(c, r); }
        return drawFreqHh(ty, comp, wk, r);
    }

    private int drawFreqHh(String ty, String comp, String wk, Random r) {
        String[] keys = {ty + "|" + comp + "|" + wk + "|*", ty + "|" + comp + "|*|*", ty + "|*|*|*"};
        for (int l = 0; l < keys.length; l++) {
            double[] c = freqH.get(keys[l]);
            if (c != null) { fbFreqH.incrementAndGet(l); return drawIndex(c, r); }
        }
        return 0;
    }

    private int scaled(int n, String ty, String seg, java.util.function.IntSupplier redraw, Random r) {
        Double f = factor.get(ty + "|" + seg); if (f == null) f = factor.get(ty + "|*");
        if (f == null || f == 1.0) return n;
        if (f < 1.0) { int k = 0; for (int i = 0; i < n; i++) if (r.nextDouble() < f) k++; return k; }
        double extra = f - 1.0; int m = n;
        while (extra > 0) { if (r.nextDouble() < Math.min(1.0, extra)) m += redraw.getAsInt(); extra -= 1.0; }
        return m;
    }

    /** prior: the schedule attribute of the start time, 0 = no earlier episode, 1 = only other episodes, 2 = work / school episodes */
    private int drawStart(String ty, String seg, int f, int i, int prior, Random r) {
        double[] c = startCdf(ty, seg, f, i, prior);
        return c == null ? 8 * 60 : drawIndex(c, r) * startStep + r.nextInt(startStep);
    }

    /** the start-time cdf of the cell (with fallback; the level used is counted) */
    private double[] startCdf(String ty, String seg, int f, int i, int prior) {
        if (prior >= 10) {   // joint episode, conditional on the participants' work / school that day (JM / JN), then the cells below
            String jp = prior == 11 ? "JM" : "JN", fs = String.valueOf(Math.min(f, 3)), is = String.valueOf(Math.min(i, 3));
            for (String k : new String[]{ty + "|" + seg + "|" + fs + "|" + is + "|" + jp, ty + "|*|" + fs + "|" + is + "|" + jp, ty + "|*|*|*|" + jp}) { double[] c = startD.get(k); if (c != null) { nJointStartCell.incrementAndGet(); return c; } }
            prior = 0;
        }
        String fs = String.valueOf(Math.min(f, 3)), is = String.valueOf(Math.min(i, 3)), g = group(seg), pb = prior >= 2 ? "M" : prior == 1 ? "O" : "0";
        String[] keys = {ty + "|" + seg + "|" + fs + "|" + is + "|" + pb, ty + "|" + seg + "|" + fs + "|" + is + "|*", ty + "|" + g + "|" + fs + "|" + is + "|*",
                ty + "|*|" + fs + "|" + is + "|*", ty + "|*|" + fs + "|*|*", ty + "|*|*|*|*"};
        for (int l = 0; l < keys.length; l++) {
            double[] c = startD.get(keys[l]);
            if (c != null) { fbStart.incrementAndGet(l); return c; }
        }
        return null;
    }

    /** Free windows of a schedule for an episode at loc: room[s] = latest end of an episode that starts at minute s (0..1439),
     *  -1 when s lies in no free window (travel from the previous and to the next episode included; day start at home at 0:00,
     *  day end at home by dayEnd). */
    private int[] freeRoom(List<Ep> sc, Location loc, Location home, int dayEnd) {
        int[] room = new int[1440]; Arrays.fill(room, -1);
        int lo = tt(home, loc, 0);
        for (int q = 0; q <= sc.size(); q++) {
            Ep nx = q < sc.size() ? sc.get(q) : null;
            int hi = nx == null ? dayEnd - tt(loc, home, dayEnd) : nx.start - tt(loc, nx.loc, nx.start);
            for (int m = Math.max(0, lo); m < Math.min(1440, hi); m++) room[m] = hi;
            if (nx != null) lo = nx.end + tt(nx.loc, loc, nx.end);
        }
        return room;
    }

    /** TASHA reject-and-regenerate, conditional form (regen.conditional): a start drawn from the episode's own start-time
     *  distribution restricted to the minutes at which an episode of at least dmin minutes fits into a free window of every
     *  schedule in rooms (the participants), then a duration from its duration distribution truncated to the room left in that
     *  window.  Returns {start, duration} or null when no start is feasible. */
    private int[] drawInWindows(List<int[]> rooms, String ty, String seg, String dseg, int f, int i, int prior, int dmin, Random r) {
        return drawInWindows(rooms, ty, seg, dseg, f, i, prior, dmin, r, 0, 1440);
    }

    /** the same restricted to starts in [from, to) (the start band of the original draw, regen.band.first) */
    private int[] drawInWindows(List<int[]> rooms, String ty, String seg, String dseg, int f, int i, int prior, int dmin, Random r, int from, int to) {
        double[] c = startCdf(ty, seg, f, i, prior); if (c == null) return null;
        int nb = c.length; double[] w = new double[nb]; double tot = 0;
        int[] room = new int[1440];
        for (int m = 0; m < 1440; m++) { int x = Integer.MAX_VALUE; for (int[] ro : rooms) x = Math.min(x, ro[m] < 0 ? -1 : ro[m]); room[m] = x; }
        for (int k = 0; k < nb; k++) {
            double pk = c[k] - (k > 0 ? c[k - 1] : 0); if (pk <= 0) continue; int ok = 0;
            for (int m = Math.max(from, k * startStep); m < Math.min(Math.min(1440, to), (k + 1) * startStep); m++) if (room[m] >= 0 && room[m] - m >= dmin) ok++;
            w[k] = pk * ok / (double) startStep; tot += w[k];
        }
        if (tot <= 0) return null;
        double u = r.nextDouble() * tot; int k = 0; for (; k < nb - 1; k++) { u -= w[k]; if (u < 0) break; }
        List<Integer> ms = new ArrayList<>();
        for (int m = Math.max(from, k * startStep); m < Math.min(Math.min(1440, to), (k + 1) * startStep); m++) if (room[m] >= 0 && room[m] - m >= dmin) ms.add(m);
        if (ms.isEmpty()) return null;
        int st = ms.get(r.nextInt(ms.size()));
        int du = drawDurationTrunc(ty, dseg, st, f, room[st] - st, r);
        return new int[]{st, Math.max(1, du)};
    }

    /** [from, to) minutes of the start band (start.bands) that contains the minute */
    private int[] bandRange(int startMin) {
        int b = band(Math.max(0, Math.min(startMin, 1439)));
        return new int[]{(int) Math.round(startBands[b] * 60), (int) Math.round(startBands[Math.min(b + 1, startBands.length - 1)] * 60)};
    }

    private int band(int startMin) {
        double h = startMin / 60.0; int b = 0;
        for (int k = 0; k < startBands.length - 1; k++) if (h >= startBands[k]) b = k;
        return b;
    }

    /** duration from the cell of drawDuration truncated to at most maxDur minutes (exact truncation of the binned distribution) */
    private int drawDurationTrunc(String ty, String seg, int startMin, int f, int maxDur, Random r) {
        String b = String.valueOf(band(Math.min(startMin, 1439))), g = group(seg), fd = f <= 0 ? "*" : f == 1 ? "1" : "2+";
        String[] keys = {ty + "|" + seg + "|" + b + "|" + fd, ty + "|" + seg + "|" + b + "|*", ty + "|" + g + "|" + b + "|*", ty + "|*|" + b + "|*", ty + "|*|*|*"};
        for (int l = 0; l < keys.length; l++) {
            double[] c = durD.get(keys[l]);
            if (c == null) continue;
            fbDur.incrementAndGet(l);
            double fmax = 0;   // F(maxDur)
            for (int k = 0; k < c.length; k++) {
                double lo = durEdges[k], hi = durEdges[Math.min(k + 1, durEdges.length - 1)], pk = c[k] - (k > 0 ? c[k - 1] : 0);
                if (maxDur >= hi) fmax = c[k]; else { if (maxDur > lo && hi > lo) fmax += pk * (maxDur - lo) / (hi - lo); break; }
            }
            if (fmax <= 0) return Math.max(1, maxDur);
            double u = r.nextDouble() * fmax; int k = 0; while (k < c.length - 1 && c[k] < u) k++;
            double lo = durEdges[k], hi = Math.min(durEdges[Math.min(k + 1, durEdges.length - 1)], maxDur), pk = c[k] - (k > 0 ? c[k - 1] : 0);
            double fr = pk > 0 ? (u - (k > 0 ? c[k - 1] : 0)) / pk : r.nextDouble();
            return (int) Math.max(1, Math.min(maxDur, Math.round(lo + fr * (durEdges[Math.min(k + 1, durEdges.length - 1)] - lo))));
        }
        return Math.max(1, Math.min(30, maxDur));
    }

    private int drawDuration(String ty, String seg, int startMin, int f, Random r) {
        String b = String.valueOf(band(Math.min(startMin, 1439))), g = group(seg), fd = f <= 0 ? "*" : f == 1 ? "1" : "2+";
        String[] keys = {ty + "|" + seg + "|" + b + "|" + fd, ty + "|" + seg + "|" + b + "|*", ty + "|" + g + "|" + b + "|*", ty + "|*|" + b + "|*", ty + "|*|*|*"};
        for (int l = 0; l < keys.length; l++) {
            double[] c = durD.get(keys[l]);
            if (c != null) {
                fbDur.incrementAndGet(l); int k = drawIndex(c, r);
                double lo = durEdges[k], hi = durEdges[Math.min(k + 1, durEdges.length - 1)];
                return (int) Math.max(1, Math.round(lo + r.nextDouble() * (hi - lo)));
            }
        }
        return 30;
    }

    // ------------------------------------------------------------------------------------------------ location band model
    private byte[] bandsFrom(int oi) {
        return bandCache.computeIfAbsent(oi, k -> {
            byte[] b = new byte[zones.size()];
            for (int j = 0; j < zones.size(); j++) {
                double km = j == oi ? intraKm[oi] : dataSet.getTravelDistances().getTravelDistanceInMeters(zoneLoc[oi], zoneLoc[j], Mode.UNKNOWN, 8 * 60) / 1000.0;
                int bb = 0; for (int q = 0; q < distLo.length; q++) if (km >= distLo[q]) bb = q;
                b[j] = (byte) bb;
            }
            return b;
        });
    }

    private Location bandLocation(String ltype, String origin, Location from, Random r) {
        double[] pb = locBand.get(ltype + "|" + origin); if (pb == null) pb = locBand.get(ltype + "|home");
        double[] a = attraction.get(ltype.equals("SCH") || ltype.equals("DAYCARE") ? ltype : "WB");
        Integer oi = zIdx.get(from.getZoneId());
        if (pb == null || a == null || oi == null) return from;
        byte[] bz = bandsFrom(oi);
        double[] tot = new double[pb.length];
        for (int j = 0; j < bz.length; j++) tot[bz[j]] += a[j];
        double[] w = new double[pb.length]; double s = 0;
        for (int q = 0; q < pb.length; q++) { w[q] = tot[q] > 0 ? pb[q] : 0; s += w[q]; }
        if (s <= 0) return from;
        double u = r.nextDouble() * s; int q = 0;
        for (; q < pb.length - 1; q++) { u -= w[q]; if (u < 0) break; }
        double v = r.nextDouble() * tot[q];
        for (int j = 0; j < bz.length; j++) {
            if (bz[j] != q) continue;
            v -= a[j];
            if (v < 0) { MicroscopicLocation l = new MicroscopicLocation(zoneLoc[j].getX(), zoneLoc[j].getY()); l.setZone(zones.get(j)); return l; }
        }
        return from;
    }

    // ------------------------------------------------------------------------------------------------ episodes and schedule
    static final class Ep {
        final String type; final Purpose purpose; int start, end; final int orig, start0; Location loc; final int jointId;
        String src = ""; int regen = 0, first = -1;   // diagnostics: location source, regenerations used, first drawn start
        // work-based subtour (2026-11-03): sub = stop of an outing from the workplace, cont = the return to the workplace, root =
        // the work episode the outing leaves from; outing = id of the outing within the household; walkV0 = the part of the
        // outing-mode utility known at scheduling (constant, distance to the first stop, workplace density)
        boolean sub = false, cont = false, root = false; int outing = 0; double walkV0 = 0; String dbg = null;
        Ep(String type, int start, int dur, Location loc, int jointId) { this.type = type; this.purpose = PURPOSE.get(type); this.start = start; this.end = start + dur; this.orig = dur; this.start0 = start; this.loc = loc; this.jointId = jointId; }
        int dur() { return end - start; }
        boolean fixed() { return sub || cont || root; }
        Ep(Ep o) { type = o.type; purpose = o.purpose; start = o.start; end = o.end; orig = o.orig; start0 = o.start0; loc = o.loc; jointId = o.jointId; src = o.src; regen = o.regen; first = o.first;
                   sub = o.sub; cont = o.cont; root = o.root; outing = o.outing; walkV0 = o.walkV0; dbg = o.dbg; }
    }

    private int tt(Location a, Location b, int t) {
        if (a.getZoneId() == b.getZoneId() && a == b) return 0;
        return Math.max(1, dataSet.getTravelTimes().getTravelTimeInMinutes(a, b, Mode.UNKNOWN, t));
    }

    /** TASHA insertion: shift neighbours, shorten to >= shortenFrac of the original durations, else false (caller regenerates). */
    private boolean insert(List<Ep> s, Ep e, Location home, int dayEnd) {
        int idx = 0; while (idx < s.size() && s.get(idx).start <= e.start) idx++;
        Ep p = idx > 0 ? s.get(idx - 1) : null, n = idx < s.size() ? s.get(idx) : null;
        Ep pp = idx > 1 ? s.get(idx - 2) : null, nn = idx + 1 < s.size() ? s.get(idx + 1) : null;
        int needB = p == null ? tt(home, e.loc, e.start) - e.start : p.end + tt(p.loc, e.loc, p.end) - e.start;
        int needA = n == null ? e.end + tt(e.loc, home, e.end) - dayEnd : e.end + tt(e.loc, n.loc, e.end) - n.start;
        if (needB <= 0 && needA <= 0) { s.add(idx, e); return true; }
        int pS = p != null ? p.start : 0, pE = p != null ? p.end : 0, nS = n != null ? n.start : 0, nE = n != null ? n.end : 0, eS = e.start, eE = e.end;
        boolean shifted = false, shortened = false;
        // (1) shift: the previous episode earlier, the next one later, as far as their own neighbours allow
        if (needB > 0 && p != null && !p.fixed()) {
            int room = p.start - (pp == null ? tt(home, p.loc, p.start) : pp.end + tt(pp.loc, p.loc, pp.end));
            room = Math.min(room, maxShift - (p.start0 - p.start));   // displacement from the drawn start bounded by max.shift.min
            int sh = Math.min(needB, Math.max(0, room)); if (sh > 0) { p.start -= sh; p.end -= sh; needB -= sh; shifted = true; }
        }
        if (needA > 0 && n != null && !n.fixed()) {
            int lim = nn == null ? dayEnd - tt(n.loc, home, n.end) : nn.start - tt(n.loc, nn.loc, n.end);
            int room = Math.min(lim - n.end, maxShift - (n.start - n.start0));
            int sh = Math.min(needA, Math.max(0, room)); if (sh > 0) { n.start += sh; n.end += sh; needA -= sh; shifted = true; }
        }
        // (2) shorten the previous, the new and the next episode to at least shortenFrac of the original duration
        int eMin = (int) Math.ceil(shortenFrac * e.orig);
        if (needB > 0) {
            int canP = p == null || p.fixed() || (protect && prec(p.type) < prec(e.type)) ? 0 : Math.max(0, p.dur() - (int) Math.ceil(shortenFrac * p.orig)), canE = Math.max(0, e.dur() - eMin);
            int cp = Math.min(canP, (needB + 1) / 2), ce = Math.min(canE, needB - cp); cp = Math.min(canP, needB - ce);
            if (p != null) p.end -= cp; e.start += ce; needB -= cp + ce; if (cp + ce > 0) shortened = true;
        }
        if (needA > 0) {
            int canN = n == null || n.fixed() || (protect && prec(n.type) < prec(e.type)) ? 0 : Math.max(0, n.dur() - (int) Math.ceil(shortenFrac * n.orig)), canE = Math.max(0, e.dur() - eMin);
            int cn = Math.min(canN, (needA + 1) / 2), ce = Math.min(canE, needA - cn); cn = Math.min(canN, needA - ce);
            if (n != null) n.start += cn; e.end -= ce; needA -= cn + ce; if (cn + ce > 0) shortened = true;
        }
        if (needB > 0 || needA > 0 || e.dur() < 1) {   // (3) reject: restore
            if (p != null) { p.start = pS; p.end = pE; } if (n != null) { n.start = nS; n.end = nE; } e.start = eS; e.end = eE;
            return false;
        }
        if (shifted) nShift.incrementAndGet(); if (shortened) nShorten.incrementAndGet();
        s.add(idx, e); return true;
    }

    // ------------------------------------------------------------------------------------------------ run
    public void run(int threads) {
        long base = AbitUtils.getRandomObject().nextLong();
        tlSeed = base ^ 0x2545F4914F6CDD1DL;   // transit leg modes: a stream of their own
        List<Household> hhs = new ArrayList<>(dataSet.getHouseholds().values());
        hhs.sort(Comparator.comparingInt(Household::getId));
        java.util.concurrent.ForkJoinPool pool = new java.util.concurrent.ForkJoinPool(Math.max(1, threads));
        try {
            pool.submit(() -> hhs.parallelStream().forEach(hh -> {
                Random r = new Random(base ^ (0x9E3779B97F4A7C15L * (hh.getId() + 1L)));
                for (int d = 0; d < days; d++) household(hh, DayOfWeek.values()[d], r);
            })).get();
        } catch (Exception e) { throw new RuntimeException("TASHA generator failed", e); }
        finally { pool.shutdown(); }
        writeSummary();
    }

    private String segment(Person p, Random r) {
        Object cached = p.getAttribute("tasha.seg").orElse(null);
        if (cached != null) return (String) cached;
        String s;
        switch (p.getOccupation()) {
            case EMPLOYED: {
                int a = 0; for (int k = 0; k < wAge.length; k++) if (p.getAge() >= wAge[k]) a = k;
                double[] c = wShares.size() > a && wShares.get(a) != null ? wShares.get(a) : null;
                s = c == null ? "worker_usual" : WTYPES[drawIndex(c, r)];
                if (s.equals("worker_usual") && (p.getJob() == null || p.getJob().getLocation() == null)) s = "worker_none";
                break;
            }
            case STUDENT: s = "student_" + abm.io.input.MarylandLosDataReader.bandOf(Math.max(5, p.getAge())); break;
            case RETIREE: s = "retiree"; break;
            case TODDLER: s = "toddler"; break;
            default: s = "nonworker";
        }
        p.setAttribute("tasha.seg", s);
        return s;
    }

    private void household(Household hh, DayOfWeek day, Random r) {
        List<Person> ps = hh.getPersons(); int off = day.ordinal() * 1440, dayEnd = 1440 + DAY_END_EXTRA;
        Location home = hh.getLocation();
        boolean child = false; int nwk = 0;
        for (Person p : ps) { if (p.getAge() < 16) child = true; if (p.getOccupation() == Occupation.EMPLOYED) nwk++; }
        String hhc = ps.size() == 1 ? "single" : child ? "multi_child" : "multi_nochild";
        String comp = child ? "child" : ps.size() == 2 ? "two_adult" : "three_adult", wk = nwk > 0 ? "1+" : "0";
        Map<Person, String> seg = new HashMap<>();
        for (Person p : ps) seg.put(p, segment(p, r));
        // ---- joint episodes (household level): frequency, start, duration, participants and the common location
        List<Joint> joints = new ArrayList<>();
        int jid = 0;
        if (ps.size() >= 2) {
            for (String ty : new String[]{"JO_REC", "JO_OTH", "JS"}) {
                int n0 = drawFreqHh(ty, comp, wk, r);
                int n = scaled(n0, ty, "household", () -> drawFreqHh(ty, comp, wk, r), r);
                for (int i = 1; i <= n; i++) {
                    nGen.incrementAndGet(); genByType.computeIfAbsent(ty, k -> new AtomicLong()).incrementAndGet();
                    Joint j = new Joint(); j.ty = ty; j.n = n; j.i = i; j.id = ++jid;
                    j.st = drawStart(ty, comp, n, i, 0, r); j.du = drawDuration(ty, "*", j.st, n, r);
                    double[] kc = partK.get(ty + "|" + Math.min(5, ps.size()));
                    int k = Math.min(ps.size(), 2 + (kc == null ? 0 : drawIndex(kc, r)));
                    List<Person> pool = new ArrayList<>(ps);
                    for (int q = 0; q < k && !pool.isEmpty(); q++) {
                        double s = 0; for (Person p : pool) s += propensity.getOrDefault(seg.get(p), 0.5);
                        double u = r.nextDouble() * s; Person sel = pool.get(pool.size() - 1);
                        for (Person p : pool) { u -= propensity.getOrDefault(seg.get(p), 0.5); if (u < 0) { sel = p; break; } }
                        j.who.add(sel); pool.remove(sel);
                    }
                    Activity probe = new Activity(j.who.get(0), PURPOSE.get(ty)); probe.setStartTime_min(off + j.st); probe.setEndTime_min(off + j.st + j.du); probe.setDayOfWeek(day);
                    setup.getDestinationChoice().selectMainActivityDestination(j.who.get(0), probe);
                    j.loc = probe.getLocation();
                    joints.add(j);
                }
            }
        }
        // ---- the agendas of all members, type by type in the order of precedence (a joint episode enters the schedules of all
        //      its participants together: rolled back and regenerated jointly, a member is dropped only after max.regenerate)
        Map<Person, List<Ep>> sched = new HashMap<>(); Map<Person, Integer> prior = new HashMap<>(), nWork = new HashMap<>(), nMand = new HashMap<>(); Map<Person, Location> workLoc = new HashMap<>();
        for (Person p : ps) {
            if (p.getPlan() == null) { Plan.initializePlan(p); setup.getHabitualModeChoice().chooseHabitualMode(p); }
            sched.put(p, new ArrayList<>()); prior.put(p, 0); nWork.put(p, 0); nMand.put(p, 0);
            workLoc.put(p, seg.get(p).equals("worker_usual") && p.getJob() != null ? p.getJob().getLocation() : null);
        }
        // work attendance (attendance.file): a worker with a usual workplace attends with attendProb; then PW and SW are drawn
        // conditional on at least one of them (rejection), else neither
        Map<Person, Boolean> attend = new HashMap<>(); Map<Person, Integer> swDrawn = new HashMap<>(); int[] outingId = {0};
        if (attFile != null) for (Person p : ps) if (workLoc.get(p) != null) {
            nAttWorkers.incrementAndGet(); boolean at = r.nextDouble() < attendProb(home); attend.put(p, at); if (!at) nAttHome.incrementAndGet();
        }
        boolean jointsRedrawn = false;
        for (String ty : TYPES) {
            if (JOINT.contains(ty)) {
                if (jointFreqMand && !jointsRedrawn && ps.size() >= 2) {
                    // joint.freq.mandatory (2026-11-10, coef_respec): the joint episodes of the household are generated now, after the
                    // members' mandatory episodes, with the frequency conditional on how many members have a work or school episode
                    // that day (MN none, MS some, MA all; household rows of tasha_frequency.csv with prior = the band); start,
                    // duration, number of participants and the participants as before (the participants then again by
                    // joint.members.mandatory, the start by joint.start.conditional)
                    int nm = 0; for (Person p : ps) { boolean m = false; for (Ep x : sched.get(p)) if (MANDT.contains(x.type)) m = true; if (m) nm++; }
                    String band = nm == 0 ? "MN" : nm == ps.size() ? "MA" : "MS";
                    joints.clear(); int jid2 = 0;
                    for (String jt : new String[]{"JO_REC", "JO_OTH", "JS"}) {
                        int n0 = drawFreqHhBand(jt, comp, wk, band, r);
                        int n = scaled(n0, jt, "household", () -> drawFreqHhBand(jt, comp, wk, band, r), r);
                        for (int i = 1; i <= n; i++) {
                            nGen.incrementAndGet(); genByType.computeIfAbsent(jt, k -> new AtomicLong()).incrementAndGet();
                            Joint j = new Joint(); j.ty = jt; j.n = n; j.i = i; j.id = ++jid2;
                            j.st = drawStart(jt, comp, n, i, 0, r); j.du = drawDuration(jt, "*", j.st, n, r);
                            double[] kc = partK.get(jt + "|" + Math.min(5, ps.size()));
                            int k = Math.min(ps.size(), 2 + (kc == null ? 0 : drawIndex(kc, r)));
                            for (int q = 0; q < k; q++) j.who.add(ps.get(q));   // placeholders: drawn below (joint.members.mandatory)
                            Activity probe = new Activity(j.who.get(0), PURPOSE.get(jt)); probe.setStartTime_min(off + j.st); probe.setEndTime_min(off + j.st + j.du); probe.setDayOfWeek(day);
                            setup.getDestinationChoice().selectMainActivityDestination(j.who.get(0), probe); j.loc = probe.getLocation();
                            joints.add(j);
                        }
                    }
                    jointsRedrawn = true; nJointBand.computeIfAbsent(band, b -> new AtomicLong()).incrementAndGet();
                }
                for (Joint j : joints) {
                    if (!j.ty.equals(ty)) continue;
                    // joint.start.conditional (2026-11-10, coef_respec): the start is drawn now, after the participants' mandatory
                    // episodes are placed, from the start distribution conditional on whether any participant has a work or school
                    // episode that day (cells JM / JN of tasha_start.csv, tasha_distributions.py); the common location again for it
                    // joint.members.mandatory (2026-11-10, coef_respec): the participants are drawn again now, with the number drawn
                    // before, by the propensity of their segment and whether they have a work or school episode that day
                    // (tasha_joint_propensity_mand.csv: segment|M, segment|N; a missing cell takes the segment's propensity)
                    if (jointMembersMand && !propMand.isEmpty()) {
                        int k = j.who.size(); List<Person> pool = new ArrayList<>(ps); j.who.clear();
                        Map<Person, Double> pw = new HashMap<>();
                        for (Person p : pool) {
                            boolean m = false; for (Ep x : sched.get(p)) if (MANDT.contains(x.type)) m = true;
                            pw.put(p, propMand.getOrDefault(seg.get(p) + "|" + (m ? "M" : "N"), propensity.getOrDefault(seg.get(p), 0.5)));
                        }
                        for (int q = 0; q < k && !pool.isEmpty(); q++) {
                            double sm = 0; for (Person p : pool) sm += pw.get(p);
                            double u = r.nextDouble() * sm; Person sel = pool.get(pool.size() - 1);
                            for (Person p : pool) { u -= pw.get(p); if (u < 0) { sel = p; break; } }
                            j.who.add(sel); pool.remove(sel);
                        }
                    }
                    int jpc = 0;
                    if (jointStartCond) {
                        boolean jm = false; for (Person p : j.who) for (Ep x : sched.get(p)) if (MANDT.contains(x.type)) jm = true;
                        jpc = jm ? 11 : 10; j.st = drawStart(ty, comp, j.n, j.i, jpc, r); j.du = drawDuration(ty, "*", j.st, j.n, r);
                        Activity probe = new Activity(j.who.get(0), PURPOSE.get(ty)); probe.setStartTime_min(off + j.st); probe.setEndTime_min(off + j.st + j.du); probe.setDayOfWeek(day);
                        setup.getDestinationChoice().selectMainActivityDestination(j.who.get(0), probe); j.loc = probe.getLocation();
                        if (jm) nJointStartM.incrementAndGet(); else nJointStartN.incrementAndGet();
                    }
                    boolean ok = false; int first = j.st, used = 0;
                    for (int a = 0; a <= maxRegen && !ok; a++) {
                        if (a > 0) {
                            nRegen.incrementAndGet(); used = a;
                            if (regenCond) {   // conditional on the free windows common to all participants
                                List<int[]> rooms = new ArrayList<>(); for (Person p : j.who) rooms.add(freeRoom(sched.get(p), j.loc, home, dayEnd));
                                int dmin = Math.max(5, (int) Math.ceil(shortenFrac * Math.min(j.du, 60))); int[] sd = null;
                                if (regenBand && a == 1) { int[] bd = bandRange(first); sd = drawInWindows(rooms, ty, comp, "*", j.n, j.i, jpc, dmin, r, bd[0], bd[1]); if (sd != null) nRegenBand.incrementAndGet(); }
                                if (sd == null) sd = drawInWindows(rooms, ty, comp, "*", j.n, j.i, jpc, dmin, r);
                                if (sd == null) { nRegenNoWindow.incrementAndGet(); break; }
                                nRegenCond.incrementAndGet(); j.st = sd[0]; j.du = sd[1];
                            } else { j.st = drawStart(ty, comp, j.n, j.i, jpc, r); j.du = drawDuration(ty, "*", j.st, j.n, r); }
                        }
                        Map<Person, List<Ep>> trial = new HashMap<>(); boolean all = true;
                        for (Person p : j.who) {
                            List<Ep> c = new ArrayList<>(); for (Ep x : sched.get(p)) c.add(new Ep(x));
                            Ep je = new Ep(ty, j.st, j.du, j.loc, j.id); je.src = "joint_mnl_home"; je.regen = used; je.first = first;
                            if (!insert(c, je, home, dayEnd)) { all = false; break; }
                            trial.put(p, c);
                        }
                        if (all) { sched.putAll(trial); ok = true; }
                    }
                    for (Person p : j.who) {
                        Ep je = new Ep(ty, j.st, j.du, j.loc, j.id); je.src = "joint_mnl_home"; je.regen = used; je.first = first;
                        boolean in = ok || insert(sched.get(p), je, home, dayEnd);
                        if (in) { nIns.incrementAndGet(); schedByType.computeIfAbsent(ty, k -> new AtomicLong()).incrementAndGet(); } else nJointDrop.incrementAndGet();
                        prior.put(p, prior.get(p) + 1);
                    }
                }
                continue;
            }
            for (Person p : ps) {
                String sg = seg.get(p); List<Ep> sc = sched.get(p); Location wl = workLoc.get(p);
                final int pr = prior.get(p), sb = nMand.get(p) > 0 ? 2 : pr > 0 ? 1 : 0;
                final int nm = nMand.get(p);
                final String lic = p.getAge() >= 16 ? (p.isHasLicense() ? "~L" : "~N") : "";
                int n0 = drawFreq(ty, sg, hhc, pr, nm, lic, r);
                int n = scaled(n0, ty, sg, () -> drawFreq(ty, sg, hhc, pr, nm, lic, r), r);
                if (ty.equals("RHW")) n = Math.min(n, Math.max(0, nWork.get(p) - 1));
                if ((ty.equals("PW") || ty.equals("SW")) && wl == null) n = 0;
                Boolean at = attend.get(p);
                if (at != null && ty.equals("PW")) {
                    if (!at) { n = 0; swDrawn.put(p, 0); }
                    else {
                        int nsw = 0;
                        for (int t = 0; t < 50; t++) {
                            if (t > 0) { int m0 = drawFreq("PW", sg, hhc, pr, nm, r); n = scaled(m0, "PW", sg, () -> drawFreq("PW", sg, hhc, pr, nm, r), r); }
                            final int prs = pr + n, nms = nm + n; int s0 = drawFreq("SW", sg, hhc, prs, nms, r); nsw = scaled(s0, "SW", sg, () -> drawFreq("SW", sg, hhc, prs, nms, r), r);
                            if (n + nsw >= 1) break;
                        }
                        swDrawn.put(p, nsw);
                    }
                }
                if (at != null && ty.equals("SW")) n = swDrawn.getOrDefault(p, n);
                for (int i = 1; i <= n; i++) {
                    nGen.incrementAndGet(); genByType.computeIfAbsent(ty, k -> new AtomicLong()).incrementAndGet();
                    String[] src = {""};
                    Location loc = location(ty, sg, p, home, wl, i, n, sb, off, r, src);
                    boolean ok = false; int first = -1, firstDur = 30;
                    for (int a = 0; a <= maxRegen && !ok; a++) {
                        int st, du;
                        if (a > 0) nRegen.incrementAndGet();
                        if (a > 0 && regenCond) {   // conditional on the free windows of the schedule; room >= shortenFrac x the first draw (<= 60 min)
                            List<int[]> rooms = Collections.singletonList(freeRoom(sc, loc, home, dayEnd)); int dmin = Math.max(5, (int) Math.ceil(shortenFrac * Math.min(60, firstDur)));
                            int[] sd = null;
                            if (regenBand && a == 1) { int[] bd = bandRange(first); sd = drawInWindows(rooms, ty, sg, sg, n, i, sb, dmin, r, bd[0], bd[1]); if (sd != null) nRegenBand.incrementAndGet(); }
                            if (sd == null) sd = drawInWindows(rooms, ty, sg, sg, n, i, sb, dmin, r);
                            if (sd == null) { nRegenNoWindow.incrementAndGet(); break; }
                            nRegenCond.incrementAndGet(); st = sd[0]; du = sd[1];
                        } else { st = drawStart(ty, sg, n, i, sb, r); du = drawDuration(ty, sg, st, n, r); }
                        if (first < 0) { first = st; firstDur = du; }
                        Ep ep = new Ep(ty, st, du, loc, 0); ep.src = src[0]; ep.regen = a; ep.first = first;
                        ok = insert(sc, ep, home, dayEnd);
                    }
                    if (ok) { nIns.incrementAndGet(); schedByType.computeIfAbsent(ty, k -> new AtomicLong()).incrementAndGet(); } else nReject.incrementAndGet();
                }
                prior.put(p, pr + n);
                if (WORKT.contains(ty)) nWork.put(p, nWork.get(p) + n);
                if (WORKT.contains(ty) || ty.equals("SCH")) nMand.put(p, nMand.get(p) + n);
            }
            // work-based subtours (2026-11-03): once the work episodes at the usual workplace are scheduled
            if (ty.equals("SW") && wbsOn) for (Person p : ps) subtours(p, seg.get(p), sched.get(p), home, workLoc.get(p), hh, off, r, outingId);
        }
        for (Person p : ps) {
            List<Ep> sc = sched.get(p);
            // clean-up: primary / secondary work episodes of cleanupWork minutes or less are removed
            sc.removeIf(x -> { boolean c = (x.type.equals("PW") || x.type.equals("SW")) && x.dur() <= cleanupWork && !x.root && !x.cont; if (c) nClean.incrementAndGet(); return c; });
            // a return home from work needs work on both sides; otherwise it is dropped (it is an ordinary at-home time)
            for (int q = sc.size() - 1; q >= 0; q--) {
                if (!sc.get(q).type.equals("RHW")) continue;
                boolean before = q > 0 && WORKT.contains(sc.get(q - 1).type), after = q + 1 < sc.size() && WORKT.contains(sc.get(q + 1).type);
                if (!before || !after) sc.remove(q);
            }
        }
        // tours: chains of every member first, then the household-level relocation of chained joint episodes, then the tours
        Map<Person, List<List<Ep>>> chains = new HashMap<>();
        Map<Integer, double[]> ju = new HashMap<>(); if (jointCommonDraws) for (Joint j : joints) ju.put(j.id, new double[]{r.nextDouble(), r.nextDouble()});
        for (Person p : ps) chains.put(p, formChains(p, seg.get(p), sched.get(p), home, r, jointCommonDraws ? ju : null));
        // the main discretionary episode of a chain with stops is relocated (tour-complexity term) BEFORE the joint stops are
        // located against it (2026-11-02; before, relocateJoint used the main's first location, which buildTourObjects then
        // replaced, and the joint stops' detours were two to three times those of the other stops)
        for (Person p : ps) for (List<Ep> c : chains.get(p)) relocateMain(p, c, off, r);
        if (relocateJoint) relocateJoint(ps, chains, home, off, r);
        Map<Tour, Integer> mainJoint = new IdentityHashMap<>();   // identity: Tour.hashCode changes with its legs and mode
        Map<Activity, Ep> subActs = new IdentityHashMap<>();
        for (Person p : ps) buildTourObjects(p, seg.get(p), chains.get(p), home, off, day, r, hh, mainJoint, subActs);
        // household stage of the estimated tour mode choice (2026-10-26): joint tours travel together, household cars are allocated
        if (setup.getTourModeChoice() instanceof MarylandTourNestedModeChoice) ((MarylandTourNestedModeChoice) setup.getTourModeChoice()).resolveHousehold(hh, mainJoint, r);
        // (2026-11-03) mode of the outings from the workplace: walk with the estimated logit, else the mode of the work tour
        if (!subActs.isEmpty()) outingModes(ps, subActs, r);
        // (2026-11-03) mode of each leg of a transit tour: estimated MNL (transitLegModes)
        if (tlOn) transitLegModes(hh, ps, subActs, mainJoint, day);
    }

    private static final class Joint { String ty; int n, i, st, du, id; Location loc; final List<Person> who = new ArrayList<>(); }

    private Location location(String ty, String sg, Person p, Location home, Location workLoc, int i, int n, int prior, int off, Random r, String[] src) {
        switch (ty) {
            case "PW": case "SW": src[0] = "usual_workplace"; return workLoc;
            case "RHW": src[0] = "home"; return home;
            case "WB":
                if (workLoc != null && MarylandDestinationChoice.hasSegment("WORK_wbwork_stop") && setup.getDestinationChoice() instanceof MarylandDestinationChoice) {
                    int st = drawStart(ty, sg, n, i, prior, r); nLocMnl.incrementAndGet(); src[0] = "mnl_WORK_wbwork_stop";   // two anchors: home and workplace
                    return ((MarylandDestinationChoice) setup.getDestinationChoice()).selectTwoAnchorZoneMnl("WORK_wbwork_stop", p, home, workLoc, st, r);
                }
                return workLoc != null ? anchored("WORK_wbwork", "WB", "work", ty, sg, p, workLoc, i, n, prior, r, src) : anchored("WORK_wbhome", "WB", "home", ty, sg, p, home, i, n, prior, r, src);
            case "WAHB": return anchored("WORK_wahb", "WAHB", "home", ty, sg, p, home, i, n, prior, r, src);
            case "SCH":
                if (p.getSchool() != null && p.getSchool().getLocation() != null) { src[0] = "school_record"; return p.getSchool().getLocation(); }
                return sg.equals("toddler") ? anchored("EDUCATION_daycare", "DAYCARE", "home", ty, sg, p, home, i, n, prior, r, src)
                                            : anchored("EDUCATION_nonstud", "SCH", "home", ty, sg, p, home, i, n, prior, r, src);
            default: {
                Activity probe = new Activity(p, PURPOSE.get(ty)); probe.setDayOfWeek(DayOfWeek.MONDAY);
                int st = drawStart(ty, sg, n, i, prior, r); probe.setStartTime_min(off + st); probe.setEndTime_min(off + st + 30);
                setup.getDestinationChoice().selectMainActivityDestination(p, probe);
                src[0] = "mnl_home";
                return probe.getLocation();
            }
        }
    }

    /** location of an anchored type: the estimated MNL segment when the coefficient file has it (2026-10-23), else the band model */
    private Location anchored(String key, String ltype, String origin, String ty, String sg, Person p, Location anchor, int i, int n, int prior, Random r, String[] src) {
        if (MarylandDestinationChoice.hasSegment(key) && setup.getDestinationChoice() instanceof MarylandDestinationChoice) {
            int st = drawStart(ty, sg, n, i, prior, r); nLocMnl.incrementAndGet(); src[0] = "mnl_" + key;
            return ((MarylandDestinationChoice) setup.getDestinationChoice()).selectAnchoredZoneMnl(key, p, anchor, st, r);
        }
        src[0] = "band_" + ltype + "_" + origin;
        return bandLocation(ltype, origin, anchor, r);
    }

    private static int prec(String ty) { for (int i = 0; i < TYPES.length; i++) if (TYPES[i].equals(ty)) return i; return TYPES.length; }

    private static int rank(String ty) {
        switch (ty) { case "PW": return 0; case "SW": return 1; case "WB": return 2; case "WAHB": return 3; case "SCH": return 4; default: return 5; }
    }

    /** chains (home-based tours) from the schedule; ABIT Tour objects with legs; tour mode choice */
    private double km(Location a, Location b) {
        Integer ia = zIdx.get(a.getZoneId()), ib = zIdx.get(b.getZoneId());
        if (ia != null && ia.equals(ib)) return intraKm[ia];
        int m = dataSet.getTravelDistances().getTravelDistanceInMeters(a, b, Mode.UNKNOWN, 8 * 60);
        return m > 0 ? Math.min(300.0, m / 1000.0) : 300.0;
    }

    private static boolean isAcc(Ep e) { return e.purpose == Purpose.ACCOMPANY; }
    private static boolean isShop(Ep e) { return e.purpose == Purpose.SHOPPING; }

    /** Estimated return-home logit (home.return.file, 2026-10-23): P(home between the consecutive out-of-home episodes a and e).
     *  Variables (3_abit/tasha_return_home.py, the same definitions on the survey): slack = the time at home if the person went
     *  home (e.start - a.end - car minutes a -> home - car minutes home -> e), piecewise-linear in hours (knots 0.5, 1, 2, 4) and
     *  ln(minutes); detour via home d(a,home) + d(home,e) - d(a,e) (km, car-distance skim, intrazonal 0.5 sqrt(area)) and its
     *  ln(1 + km); d(a, home); purpose of a and e (work incl. work business, school, accompany, shopping; joint; base: other
     *  individual discretionary); person segment (base: non-worker); out-of-home episodes of the day (3, 4, 5+; base 2); time of
     *  day of the end of a (am < 9:00, pm 15-19, ev >= 19; base midday). */
    private double returnHomeProb(Ep a, Ep e, String sg, Location home, int nEp, int slack, Person person) {
        double h = slack / 60.0, dah = km(a.loc, home), dhe = km(home, e.loc), dae = km(a.loc, e.loc), det = Math.max(0.0, dah + dhe - dae);
        boolean aw = WORKT.contains(a.type), ew = WORKT.contains(e.type);
        double[] x = new double[RH_VARS.length]; int k = 0;
        x[k++] = 1; x[k++] = Math.min(h, 0.5); x[k++] = Math.max(0, Math.min(h, 1) - 0.5); x[k++] = Math.max(0, Math.min(h, 2) - 1); x[k++] = Math.max(0, Math.min(h, 4) - 2); x[k++] = Math.max(0, h - 4);
        x[k++] = Math.log(Math.max(1, slack)); x[k++] = det; x[k++] = Math.log1p(det); x[k++] = dah;
        x[k++] = aw ? 1 : 0; x[k++] = a.type.equals("SCH") ? 1 : 0; x[k++] = isAcc(a) ? 1 : 0; x[k++] = isShop(a) ? 1 : 0; x[k++] = a.jointId != 0 ? 1 : 0;
        x[k++] = ew ? 1 : 0; x[k++] = e.type.equals("SCH") ? 1 : 0; x[k++] = isAcc(e) ? 1 : 0; x[k++] = isShop(e) ? 1 : 0; x[k++] = e.jointId != 0 ? 1 : 0;
        x[k++] = sg.startsWith("worker") ? 1 : 0; x[k++] = (sg.equals("student_elementary") || sg.equals("student_middle") || sg.equals("student_high")) ? 1 : 0;
        x[k++] = sg.equals("student_postsec") ? 1 : 0; x[k++] = sg.equals("retiree") ? 1 : 0; x[k++] = sg.equals("toddler") ? 1 : 0;
        x[k++] = nEp == 3 ? 1 : 0; x[k++] = nEp == 4 ? 1 : 0; x[k++] = nEp >= 5 ? 1 : 0;
        x[k++] = a.end < 540 ? 1 : 0; x[k++] = a.end >= 900 && a.end < 1140 ? 1 : 0; x[k++] = a.end >= 1140 ? 1 : 0;
        // 2026-11-03: two joint episodes; a joint episode next to a work or school episode
        boolean aj = a.jointId != 0, ej = e.jointId != 0, am = aw || a.type.equals("SCH"), em = ew || e.type.equals("SCH");
        x[k++] = aj && ej ? 1 : 0; x[k++] = (aj && em) || (ej && am) ? 1 : 0;
        double[] ha = hhAttrs(person);
        x[k++] = ha[0]; x[k++] = ha[1]; x[k++] = ha[2]; x[k++] = ha[3]; x[k++] = ha[4] <= 0 ? 1 : 0; x[k++] = ha[4] > 0 && ha[4] < ha[5] ? 1 : 0;
        x[k++] = ha[6] < 50000 ? 1 : 0; x[k++] = ha[6] >= 100000 ? 1 : 0; x[k++] = nEp;
        double v = 0; for (int q = 0; q < RH_VARS.length; q++) { Double b = rhCoef.get(RH_VARS[q]); if (b != null) v += b * x[q]; }
        if (dbgFile != null) dbg("RH", person.getId() + "," + a.type + "," + a.purpose + "," + (a.jointId != 0 ? 1 : 0) + "," + a.end + "," + a.loc.getZoneId() + ","
                + e.type + "," + e.purpose + "," + (e.jointId != 0 ? 1 : 0) + "," + e.loc.getZoneId() + "," + home.getZoneId() + "," + sg + "," + nEp + "," + slack + ","
                + ha[0] + "," + ha[1] + "," + ha[2] + "," + ha[3] + "," + ha[4] + "," + ha[5] + "," + ha[6] + "," + v);
        return 1.0 / (1.0 + Math.exp(-v));
    }

    private static Ep mainOf(List<Ep> c) {
        Ep m = c.get(0);
        for (Ep e : c) if (rank(e.type) < rank(m.type) || (rank(e.type) == rank(m.type) && rank(e.type) == 5 && e.dur() > m.dur())) m = e;
        return m;
    }

    /** chains (home-based tours) of a schedule: the return-home decision between consecutive out-of-home episodes */
    private List<List<Ep>> formChains(Person person, String sg, List<Ep> sched, Location home, Random r) { return formChains(person, sg, sched, home, r, null); }

    /** ju (2026-11-03): one uniform draw per joint episode and side (arrival, departure), common to its participants, so that the
     *  members of a joint activity take the return-home decision next to it together (they travel together) */
    private List<List<Ep>> formChains(Person person, String sg, List<Ep> sched, Location home, Random r, Map<Integer, double[]> ju) {
        List<List<Ep>> chains = new ArrayList<>(); List<Ep> cur = new ArrayList<>();
        int nEp = 0; for (Ep x : sched) if (!x.type.equals("RHW") && !x.sub && !x.cont) nEp++;   // as in the survey: an outing and its return are not episodes of the day
        for (int q = 0; q < sched.size(); q++) {
            Ep e = sched.get(q);
            if (e.type.equals("RHW")) { if (!cur.isEmpty()) { chains.add(cur); cur = new ArrayList<>(); } continue; }
            if (!cur.isEmpty() && (e.sub || e.cont)) { cur.add(e); continue; }   // the outing and the return to the workplace: direct
            if (!cur.isEmpty()) {
                Ep a = cur.get(cur.size() - 1);
                int arr = a.end + tt(a.loc, home, a.end), slack = e.start - arr - tt(home, e.loc, e.start);
                boolean goHome;
                if (!rhCoef.isEmpty()) {
                    // estimated rule: the binary logit of a return home; infeasible when the time at home would be below
                    // home.return.min.slack, and never between two work episodes (lunch at home is the RHW type)
                    if (slack < rhMinSlack || (WORKT.contains(a.type) && WORKT.contains(e.type))) {
                        goHome = false; nRhInfeasible.incrementAndGet();
                        if (!(WORKT.contains(a.type) && WORKT.contains(e.type))) {
                            double pr = returnHomeProb(a, e, sg, home, nEp, Math.max(1, slack), person); nRhTight.incrementAndGet(); rhTightP.add(pr);
                            // (2026-11-03, home.return.honor) the logit is estimated on every pair whatever its gap: a drawn return home
                            // is kept by moving the next episode later (by at most max.shift.min from its drawn start, before the next
                            // episode) and, for the rest, ending the previous one earlier (to shorten.min.frac of its duration); joint
                            // and work-based subtour episodes are not moved
                            if (rhHonor) {
                                double u = ju != null && e.jointId != 0 && ju.containsKey(e.jointId) ? ju.get(e.jointId)[0]
                                         : ju != null && a.jointId != 0 && ju.containsKey(a.jointId) ? ju.get(a.jointId)[1] : r.nextDouble();
                                if (u < pr) {
                                    int need = (int) Math.ceil(rhMinSlack - slack), shE = 0, cutA = 0;
                                    if (e.jointId == 0 && !e.fixed()) {
                                        Ep nx = q + 1 < sched.size() ? sched.get(q + 1) : null;
                                        int lim = nx == null ? 1440 + DAY_END_EXTRA - tt(e.loc, home, e.end) : nx.start - tt(e.loc, nx.loc, e.end);
                                        shE = Math.max(0, Math.min(need, Math.min(lim - e.end, maxShift - (e.start - e.start0))));
                                    }
                                    if (need - shE > 0 && a.jointId == 0 && !a.fixed()) cutA = Math.max(0, Math.min(need - shE, a.dur() - (int) Math.ceil(shortenFrac * a.orig)));
                                    if (shE + cutA >= need) { e.start += shE; e.end += shE; a.end -= cutA; goHome = true; nRhHonored.incrementAndGet(); }
                                }
                            }
                        }
                    }
                    else {
                        double u = ju != null && e.jointId != 0 && ju.containsKey(e.jointId) ? ju.get(e.jointId)[0]
                                 : ju != null && a.jointId != 0 && ju.containsKey(a.jointId) ? ju.get(a.jointId)[1] : r.nextDouble();
                        goHome = u < returnHomeProb(a, e, sg, home, nEp, slack, person); nRhLogit.incrementAndGet();
                    }
                } else {
                    // the person goes home when an at-home stay drawn from the observed at-home durations between two out-of-home
                    // episodes (type HOME, by arrival band) fits into the slack; without that distribution: the fixed minimum slack
                    double need = hasHomeDur ? homeStayFactor * drawDuration("HOME", sg, Math.max(0, arr), 0, r) : homeMinSlack;
                    goHome = slack >= need;
                }
                if (goHome) { chains.add(cur); cur = new ArrayList<>(); nHomeBreak.incrementAndGet(); }
                else {
                    int gap = e.start - (a.end + tt(a.loc, e.loc, a.end));
                    int sh = (int) Math.round(slackToNext * Math.max(0, gap));
                    if (prec(e.type) >= prec(a.type)) { e.start -= sh; e.end -= sh; }      // the next episode is not more important: it moves earlier
                    else { a.start += sh; a.end += sh; }                                  // else the earlier episode moves later
                    a.end = Math.max(a.end, e.start - tt(a.loc, e.loc, a.end)); nDirect.incrementAndGet();
                }
            }
            cur.add(e);
        }
        if (!cur.isEmpty()) chains.add(cur);
        return chains;
    }

    /** Joint episodes chained to other episodes (relocate.joint, 2026-10-23): a joint episode is relocated with the estimated
     *  stop MNL of its purpose (anchors home and the main activity of a participant's chain) when it is not the main activity of
     *  any participant's chain (relocate.joint.mode = allstops), or when it is a stop in the chain of at least one participant
     *  (mode = anystop; the anchor chain is one whose main activity is work or school if there is one, else the first chain in
     *  which it is a stop); the common location is given to every participant. */
    private void relocateJoint(List<Person> ps, Map<Person, List<List<Ep>>> chains, Location home, int off, Random r) {
        if (!(setup.getDestinationChoice() instanceof MarylandDestinationChoice)) return;
        MarylandDestinationChoice dc = (MarylandDestinationChoice) setup.getDestinationChoice();
        Map<Integer, List<Ep>> copies = new LinkedHashMap<>(); Map<Integer, Boolean> isMain = new HashMap<>(); Map<Integer, Object[]> anchor = new HashMap<>();
        for (Person p : ps) {
            List<List<Ep>> cs = chains.get(p); if (cs == null) continue;
            for (List<Ep> c : cs) {
                Ep m = mainOf(c);
                for (Ep e : c) {
                    if (e.jointId == 0) continue;
                    copies.computeIfAbsent(e.jointId, k -> new ArrayList<>()).add(e);
                    if (e == m || c.size() == 1) { isMain.put(e.jointId, true); continue; }
                    // a stop here: anchor on this chain.  2026-11-02: prefer a chain with a discretionary main (before: a work / school
                    // main).  In the estimation half 75 % of the joint episodes that are stops lie on tours with a discretionary main,
                    // with detours of 6.3 km (9.3 km on work / school tours); anchored on the work / school chain, the common location
                    // was far from the other participants' chains (detours 12-17 km)
                    Object[] cur = anchor.get(e.jointId);
                    if (cur == null || (rank(((Ep) cur[1]).type) < 5 && rank(m.type) >= 5)) anchor.put(e.jointId, new Object[]{p, m, e.start < m.start});
                }
            }
        }
        for (Map.Entry<Integer, List<Ep>> en : copies.entrySet()) {
            int id = en.getKey(); Ep e0 = en.getValue().get(0);
            if (!anchor.containsKey(id) || (!jointAnyStop && isMain.getOrDefault(id, false)) || !Purpose.getDiscretionaryPurposes().contains(e0.purpose) || !MarylandDestinationChoice.hasStopModel(e0.purpose)) continue;
            Object[] an = anchor.get(id); Ep m = (Ep) an[1];
            Location nl = dc.selectStopZoneMnl((Person) an[0], e0.purpose, (Boolean) an[2], home, m.loc, off + m.start, m.purpose, r);
            for (Ep e : en.getValue()) { e.loc = nl; e.src = "joint_stop_mnl"; }
            nJointReloc.incrementAndGet();
        }
    }

    /** main discretionary episode of a chain with stops: relocated with the primary MNL's tour-complexity term (2026-10-23); the
     *  main of a single-episode chain keeps its draw (flag 0); joint episodes keep the household's location */
    private void relocateMain(Person person, List<Ep> c, int off, Random r) {
        Ep m = mainOf(c);
        if (c.size() > 1 && m.jointId == 0 && m.src.equals("mnl_home") && setup.getDestinationChoice() instanceof MarylandDestinationChoice
                && MarylandDestinationChoice.hasMultiTerm(m.purpose)) {
            m.loc = ((MarylandDestinationChoice) setup.getDestinationChoice()).selectPrimaryZoneMnl(person, m.purpose, off + m.start, true, r);
            m.src = "mnl_home_multi"; nMainReloc.incrementAndGet();
        }
    }

    private void buildTourObjects(Person person, String sg, List<List<Ep>> chains, Location home, int off, DayOfWeek day, Random r, Household hh, Map<Tour, Integer> mainJoint, Map<Activity, Ep> subActs) {
        Plan plan = person.getPlan();
        Activity homeBefore = null; int lastHomeArr = off;
        for (List<Ep> c : chains) {
            Ep m = mainOf(c);
            relocateMain(person, c, off, r);   // no-op: done in household() before the joint stops are located
            Map<Ep, Activity> acts = new LinkedHashMap<>();
            for (Ep e : c) {
                Activity a = new Activity(person, e.purpose); a.setStartTime_min(off + e.start); a.setEndTime_min(off + e.end); a.setLocation(e.loc); a.setDayOfWeek(day);
                if (e != m) a.setDiscretionaryActivityType(DiscretionaryActivityType.ON_MANDATORY_TOUR);
                else if (!Purpose.getMandatoryPurposes().contains(e.purpose)) a.setDiscretionaryActivityType(DiscretionaryActivityType.PRIMARY);
                acts.put(e, a);
            }
            Activity main = acts.get(m);
            for (Ep e : c) if (e.sub || e.cont) subActs.put(acts.get(e), e);
            Tour tour = new Tour(main, plan.getTours().size() + 1);
            for (Activity a : acts.values()) { if (a != main) { int k = a.getStartTime_min(); while (tour.getActivities().containsKey(k)) k++; tour.getActivities().put(k, a); } a.setTour(tour); }
            mainJoint.put(tour, m.jointId);
            // tour mode before the stops are located (the stop MNL has the tour-mode flag); the estimated tour model draws with the
            // household's random stream (reproducible across thread schedules)
            if (setup.getTourModeChoice() instanceof MarylandTourNestedModeChoice) ((MarylandTourNestedModeChoice) setup.getTourModeChoice()).chooseMode(person, tour, r);
            else setup.getTourModeChoice().chooseMode(person, tour);
            // chained discretionary stops: location relative to the anchors of the tour (home and the main activity) from the
            // estimated stop MNL (detour), instead of the home-based draw made before scheduling (Roorda et al.'s first direction
            // for improvement); joint episodes keep the household's common location
            if (relocateStops && setup.getDestinationChoice() instanceof MarylandDestinationChoice) {
                MarylandDestinationChoice dc = (MarylandDestinationChoice) setup.getDestinationChoice();
                Location prev = home;   // sequential anchors (2026-10-23): the stops of the chain in time order
                for (Ep e : c) {
                    boolean stop = !(e == m || e.sub || e.jointId != 0 || !Purpose.getDiscretionaryPurposes().contains(e.purpose) || !MarylandDestinationChoice.hasStopModel(e.purpose));
                    if (stop) {
                        boolean out = e.start < m.start; Location nl;
                        if (MarylandDestinationChoice.hasSeqStopModel(e.purpose)) { nl = dc.selectSeqStopZoneMnl(person, tour, e.purpose, out, prev, out ? main.getLocation() : home, r); e.src = "seq_stop_mnl"; }
                        else { nl = dc.selectStopZoneMnl(person, tour, e.purpose, out, home, main.getLocation(), r); e.src = "stop_mnl"; }
                        e.loc = nl; acts.get(e).setLocation(nl); nReloc.incrementAndGet();
                    }
                    prev = e.loc;
                }
            }
            if (episodesOut) {
                int pos = 0; StringBuilder sb = new StringBuilder();
                for (Ep e : c) {
                    sb.setLength(0);
                    sb.append(person.getId()).append(',').append(hh.getId()).append(',').append(sg).append(',').append(e.type).append(',').append(e.src).append(',')
                      .append(e.start).append(',').append(e.end).append(',').append(e.start0).append(',').append(e.first).append(',').append(e.regen).append(',')
                      .append(e.loc.getZoneId()).append(',').append(plan.getTours().size() + 1).append(',').append(pos++).append(',').append(c.size()).append(',')
                      .append(e == m ? 1 : 0).append(',').append(m.type).append(',').append(e.jointId).append(',').append(main.getLocation().getZoneId());
                    epLines.add(sb.toString());
                }
            }
            Ep first = c.get(0), last = c.get(c.size() - 1);
            int t0 = tt(home, first.loc, first.start), leave = Math.max(lastHomeArr, off + first.start - t0); t0 = off + first.start - leave;
            Activity hb = homeBefore != null ? homeBefore : new Activity(person, Purpose.HOME);
            if (homeBefore == null) { hb.setStartTime_min(Math.min(lastHomeArr, leave)); hb.setLocation(home); hb.setDayOfWeek(day); }
            hb.setEndTime_min(leave);
            Leg l0 = new Leg(hb, acts.get(first)); l0.setTravelTime_min(t0); tour.getLegs().put(leave, l0);
            for (int q = 0; q + 1 < c.size(); q++) {
                Ep a = c.get(q), b = c.get(q + 1); Leg l = new Leg(acts.get(a), acts.get(b));
                l.setTravelTime_min(Math.max(0, b.start - a.end)); int k = off + a.end; while (tour.getLegs().containsKey(k)) k++; tour.getLegs().put(k, l);
            }
            int t1 = tt(last.loc, home, last.end);
            Activity ha = new Activity(person, Purpose.HOME); ha.setStartTime_min(off + last.end + t1); ha.setEndTime_min(off + 1439); ha.setLocation(home); ha.setDayOfWeek(day);
            Leg l1 = new Leg(acts.get(last), ha); l1.setTravelTime_min(t1); int k1 = off + last.end; while (tour.getLegs().containsKey(k1)) k1++; tour.getLegs().put(k1, l1);
            for (Leg l : tour.getLegs().values()) l.setLegMode(tour.getTourMode());
            int key = main.getStartTime_min(); while (plan.getTours().containsKey(key)) key++;
            plan.getTours().put(key, tour);
            homeBefore = ha; lastHomeArr = ha.getStartTime_min();
        }
    }

    private void outingModes(List<Person> ps, Map<Activity, Ep> subActs, Random r) {
        Map<Integer, Boolean> walk = new HashMap<>();
        for (Person p : ps) for (Tour t : p.getPlan().getTours().values()) {
            Mode tm = t.getTourMode();
            for (Leg l : t.getLegs().values()) {
                Ep nx = subActs.get(l.getNextActivity()), pv = subActs.get(l.getPreviousActivity());
                Ep s = nx != null && nx.sub ? nx : (pv != null && pv.sub && nx != null && nx.cont ? pv : null);
                if (s == null) continue;
                Boolean wk = walk.get(s.outing);
                if (wk == null) {
                    double v = s.walkV0 + wbsMode.getOrDefault("tm_cd", 0.0) * (tm == Mode.CAR_DRIVER ? 1 : 0) + wbsMode.getOrDefault("tm_cp", 0.0) * (tm == Mode.CAR_PASSENGER ? 1 : 0);
                    if (dbgFile != null && s.dbg != null) dbg("WBSMODE", s.dbg + "," + tm + "," + v);
                    wk = tm != Mode.WALK && r.nextDouble() < 1.0 / (1.0 + Math.exp(-v)); walk.put(s.outing, wk); nWbsOutMode.incrementAndGet(); if (wk) nWbsWalk.incrementAndGet();
                }
                if (wk) l.setLegMode(Mode.WALK);
            }
        }
    }

    // ------------------------------------------------------------------------------------------------ transit leg modes
    // (2026-11-03; 3_abit/tasha_estimation/estimate_transit_legs.py, estimation half of the RTS)
    static final String[] TL_ALT = {"TR", "WK", "CP", "CD", "BK"};
    static final String[] TL_VARS = {"first", "last", "mid", "main", "km", "lnkm", "ttr", "nopath", "peak", "wash", "work", "school", "cars0", "carshort", "lic",
            "age_u18", "age_65p", "stops", "rail", "prevCD", "prevCP", "prevWK", "firstCD"};
    private final double[][] tlB = new double[TL_ALT.length][TL_VARS.length]; private final double[] tlAsc = new double[TL_ALT.length];
    private double tlWalkMax = 8, tlBikeMax = 30; private boolean tlOn = false; private long tlSeed = 0;
    private final AtomicLong nTlTours = new AtomicLong(), nTlLegs = new AtomicLong(), nTlOuting = new AtomicLong(), nTlNoZone = new AtomicLong(), nTlNoCar = new AtomicLong();
    private final AtomicLongArray nTlMode = new AtomicLongArray(TL_ALT.length);

    /** coefficients (key,value): ASC_<alt>, <variable>_<alt> (TL_VARS x TL_ALT, TR the reference), walk.max.km, bike.max.km */
    private void loadTransitLegs(String f) {
        for (double[] b : tlB) Arrays.fill(b, 0.0); Arrays.fill(tlAsc, 0.0); int k = 0;
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            br.readLine(); String line;
            while ((line = br.readLine()) != null) {
                if (line.isBlank()) continue; int c = line.indexOf(','); String key = line.substring(0, c).trim(); double v = Double.parseDouble(line.substring(c + 1).trim());
                if (key.equals("walk.max.km")) { tlWalkMax = v; continue; }
                if (key.equals("bike.max.km")) { tlBikeMax = v; continue; }
                int u = key.lastIndexOf('_'); String var = key.substring(0, u), alt = key.substring(u + 1);
                int a = Arrays.asList(TL_ALT).indexOf(alt), x = Arrays.asList(TL_VARS).indexOf(var);
                if (a < 0 || (x < 0 && !var.equals("ASC"))) throw new RuntimeException("transit.legmode: unknown term " + key);
                if (x < 0) tlAsc[a] = v; else tlB[a][x] = v; k++;
            }
        } catch (RuntimeException e) { throw e; } catch (Exception e) { throw new RuntimeException("transit.legmode file load failed: " + f, e); }
        tlOn = k > 0;
        logger.info("TASHA transit leg modes: " + k + " terms from " + f + "; walk up to " + tlWalkMax + " km, bike up to " + tlBikeMax + " km");
    }

    /** the largest number of windows in use at one instant of [t0, t1) */
    private static int overlap(List<int[]> held, int t0, int t1) {
        int mx = 0; List<Integer> pts = new ArrayList<>(); pts.add(t0);
        for (int[] w : held) if (w[0] < t1 && t0 < w[1] && w[0] > t0) pts.add(w[0]);
        for (int s : pts) { int c = 0; for (int[] u : held) if (u[0] <= s && s < u[1]) c++; mx = Math.max(mx, c); }
        return mx;
    }

    private void transitLegModes(Household hh, List<Person> ps, Map<Activity, Ep> subActs, Map<Tour, Integer> built, DayOfWeek day) {
        List<Tour> mine = new ArrayList<>(); Map<Tour, Person> who = new IdentityHashMap<>();
        for (Person p : ps) for (Tour t : p.getPlan().getTours().values()) if (built.containsKey(t)) { mine.add(t); who.put(t, p); }
        boolean any = false; for (Tour t : mine) any |= t.getTourMode() == Mode.BUS || t.getTourMode() == Mode.TRAIN;
        if (!any) return;
        Random rl = new Random(tlSeed ^ (0xC2B2AE3D27D4EB4FL * (hh.getId() + 1L)) ^ (31L * day.ordinal()));
        int cars = hh.getNumberOfCars(), drivers = 0; for (Person q : ps) if (q.isHasLicense()) drivers++;
        double wash = MarylandTourNestedModeChoice.washington(hh.getLocation().getZoneId()) ? 1 : 0;
        // the household's cars are held by its car-driver tours (household stage of the tour mode choice)
        List<int[]> held = new ArrayList<>();
        for (Tour t : mine) if (t.getTourMode() == Mode.CAR_DRIVER && !t.getLegs().isEmpty()) held.add(window(t));
        Map<String, Integer> vi = new HashMap<>(); for (int i = 0; i < TL_VARS.length; i++) vi.put(TL_VARS[i], i);
        int iFirst = vi.get("first"), iLast = vi.get("last"), iMid = vi.get("mid"), iMain = vi.get("main"), iKm = vi.get("km"), iLnkm = vi.get("lnkm"), iTtr = vi.get("ttr"),
            iNop = vi.get("nopath"), iPeak = vi.get("peak"), iWash = vi.get("wash"), iWork = vi.get("work"), iSch = vi.get("school"), iC0 = vi.get("cars0"), iCs = vi.get("carshort"),
            iLic = vi.get("lic"), iU18 = vi.get("age_u18"), i65 = vi.get("age_65p"), iSt = vi.get("stops"), iRail = vi.get("rail"), iPcd = vi.get("prevCD"), iPcp = vi.get("prevCP"),
            iPwk = vi.get("prevWK"), iFcd = vi.get("firstCD");
        for (Tour t : mine) {
            Mode tm = t.getTourMode(); if (tm != Mode.BUS && tm != Mode.TRAIN) continue;
            Person p = who.get(t); nTlTours.incrementAndGet();
            Activity main = t.getMainActivity(); String seg = MarylandTourNestedModeChoice.segment(main.getPurpose());
            List<Leg> legs = new ArrayList<>(t.getLegs().values()); int n = legs.size();
            int[] w = window(t); boolean carFree = cars > 0 && overlap(held, w[0], w[1]) < cars;
            boolean elig = p.isHasLicense() && p.getAge() >= 16 && carFree;
            if (p.isHasLicense() && p.getAge() >= 16 && cars > 0 && !carFree) nTlNoCar.incrementAndGet();
            int prev = -1, firstMode = -1; boolean usedCar = false;
            double[] x = new double[TL_VARS.length], v = new double[TL_ALT.length]; boolean[] av = new boolean[TL_ALT.length];
            for (int q = 0; q < n; q++) {
                Leg l = legs.get(q); Activity a = l.getPreviousActivity(), b = l.getNextActivity();
                Ep nx = subActs.get(b), pv = subActs.get(a);
                if ((nx != null && nx.sub) || (pv != null && pv.sub && nx != null && nx.cont)) { nTlOuting.incrementAndGet(); continue; }   // outingModes
                int dep = a.getPurpose() == Purpose.HOME ? b.getStartTime_min() - l.getTravelTime_min() : a.getEndTime_min();
                double[] los = MarylandTourNestedModeChoice.legLos(a.getLocation().getZoneId(), b.getLocation().getZoneId(), dep, tm == Mode.TRAIN);
                if (los == null) { nTlNoZone.incrementAndGet(); prev = 0; if (firstMode < 0) firstMode = 0; continue; }   // keeps the tour mode
                double km = los[0]; boolean ok = !Double.isNaN(los[1]); int per = (int) los[2];
                boolean first = q == 0, last = q == n - 1;
                boolean isMain = a == main || b == main || (pv != null && pv.cont && main.getPurpose() == Purpose.WORK && a.getLocation().getZoneId() == main.getLocation().getZoneId());
                Arrays.fill(x, 0.0);
                x[iFirst] = first ? 1 : 0; x[iLast] = last ? 1 : 0; x[iMid] = !first && !last ? 1 : 0; x[iMain] = isMain ? 1 : 0;
                x[iKm] = km; x[iLnkm] = Math.log1p(km); x[iTtr] = ok ? los[1] / 10.0 : 0; x[iNop] = ok ? 0 : 1; x[iPeak] = per == 0 || per == 2 ? 1 : 0; x[iWash] = wash;
                x[iWork] = seg.equals("work") ? 1 : 0; x[iSch] = seg.equals("school") ? 1 : 0; x[iC0] = cars <= 0 ? 1 : 0; x[iCs] = cars > 0 && cars < drivers ? 1 : 0;
                x[iLic] = p.isHasLicense() ? 1 : 0; x[iU18] = p.getAge() < 18 ? 1 : 0; x[i65] = p.getAge() >= 65 ? 1 : 0; x[iSt] = n > 2 ? 1 : 0; x[iRail] = tm == Mode.TRAIN ? 1 : 0;
                x[iPcd] = prev == 3 ? 1 : 0; x[iPcp] = prev == 2 ? 1 : 0; x[iPwk] = prev == 1 ? 1 : 0; x[iFcd] = last && !first && firstMode == 3 ? 1 : 0;
                av[0] = true; av[1] = km <= tlWalkMax; av[2] = true; av[3] = elig; av[4] = km <= tlBikeMax;
                double vmax = Double.NEGATIVE_INFINITY;
                for (int k = 0; k < TL_ALT.length; k++) {
                    double s = tlAsc[k]; for (int i = 0; i < x.length; i++) s += tlB[k][i] * x[i];
                    v[k] = s; if (av[k]) vmax = Math.max(vmax, s);
                }
                double sum = 0; for (int k = 0; k < TL_ALT.length; k++) { v[k] = av[k] ? Math.exp(v[k] - vmax) : 0; sum += v[k]; }
                double u = rl.nextDouble() * sum, c = 0; int alt = 0;
                for (int k = 0; k < TL_ALT.length; k++) { if (v[k] <= 0) continue; c += v[k]; alt = k; if (u <= c) break; }
                l.setLegMode(alt == 0 ? tm : alt == 1 ? Mode.WALK : alt == 2 ? Mode.CAR_PASSENGER : alt == 3 ? Mode.CAR_DRIVER : Mode.BIKE);
                prev = alt; if (firstMode < 0) firstMode = alt; if (alt == 3) usedCar = true;
                nTlLegs.incrementAndGet(); nTlMode.incrementAndGet(alt);
            }
            if (usedCar) held.add(w);
        }
    }

    /** departure from home to the return home of a tour */
    private static int[] window(Tour t) {
        Leg f = t.getLegs().get(t.getLegs().firstKey()), l = t.getLegs().get(t.getLegs().lastKey());
        return new int[]{f.getPreviousActivity().getEndTime_min(), l.getNextActivity().getStartTime_min()};
    }

    private void writeSummary() {
        StringBuilder sb = new StringBuilder("measure,value\n");
        long[] f = new long[9]; long ft = 0; for (int i = 0; i < 9; i++) { f[i] = fbFreq.get(i); ft += f[i]; }
        for (int i = 0; i < 9; i++) sb.append("freq_person_level").append(i).append(',').append(ft > 0 ? (double) f[i] / ft : 0).append('\n');
        long ht = 0; for (int i = 0; i < 3; i++) ht += fbFreqH.get(i);
        for (int i = 0; i < 3; i++) sb.append("freq_household_level").append(i).append(',').append(ht > 0 ? (double) fbFreqH.get(i) / ht : 0).append('\n');
        long st = 0; for (int i = 0; i < 6; i++) st += fbStart.get(i);
        for (int i = 0; i < 6; i++) sb.append("start_level").append(i).append(',').append(st > 0 ? (double) fbStart.get(i) / st : 0).append('\n');
        long dt = 0; for (int i = 0; i < 5; i++) dt += fbDur.get(i);
        for (int i = 0; i < 5; i++) sb.append("duration_level").append(i).append(',').append(dt > 0 ? (double) fbDur.get(i) / dt : 0).append('\n');
        sb.append("episodes_generated,").append(nGen.get()).append('\n').append("episodes_scheduled,").append(nIns.get()).append('\n')
          .append("insertions_with_shift,").append(nShift.get()).append('\n').append("insertions_with_shortening,").append(nShorten.get()).append('\n')
          .append("regenerations,").append(nRegen.get()).append('\n').append("rejected_after_regeneration,").append(nReject.get()).append('\n')
          .append("joint_participations_dropped,").append(nJointDrop.get()).append('\n').append("cleanup_work_removed,").append(nClean.get()).append('\n')
          .append("stops_relocated,").append(nReloc.get()).append('\n').append("home_breaks,").append(nHomeBreak.get()).append('\n').append("direct_links,").append(nDirect.get()).append('\n')
          .append("regenerations_conditional,").append(nRegenCond.get()).append('\n').append("regenerations_in_original_band,").append(nRegenBand.get()).append('\n').append("regenerations_no_window,").append(nRegenNoWindow.get()).append('\n')
          .append("return_home_logit_draws,").append(nRhLogit.get()).append('\n').append("return_home_infeasible,").append(nRhInfeasible.get()).append('\n')
          .append("locations_estimated_mnl,").append(nLocMnl.get()).append('\n').append("attendance_workers,").append(nAttWorkers.get()).append('\n')
          .append("attendance_at_home_or_absent,").append(nAttHome.get()).append('\n').append("joint_relocated,").append(nJointReloc.get()).append('\n').append("mains_relocated_multi,").append(nMainReloc.get()).append('\n')
          .append("wbs_work_episodes,").append(nWbsEp.get()).append('\n').append("wbs_outings,").append(nWbsOut.get()).append('\n').append("wbs_stops,").append(nWbsStops.get()).append('\n')
          .append("wbs_outings_not_fitting,").append(nWbsNoFit.get()).append('\n').append("wbs_outings_walk,").append(nWbsWalk.get()).append('\n').append("wbs_outings_mode_drawn,").append(nWbsOutMode.get()).append('\n')
          .append("freq_licence_cells,").append(nFreqLic.get()).append('\n')
          .append(jointFreqMand ? "joint_households_band_MN," + nJointBand.getOrDefault("MN", new AtomicLong()).get() + "\njoint_households_band_MS," + nJointBand.getOrDefault("MS", new AtomicLong()).get() + "\njoint_households_band_MA," + nJointBand.getOrDefault("MA", new AtomicLong()).get() + "\n" : "")
          .append(jointStartCond ? "joint_start_with_mandatory," + nJointStartM.get() + "\njoint_start_without_mandatory," + nJointStartN.get() + "\njoint_start_conditional_cells," + nJointStartCell.get() + "\n" : "")
          .append("transit_leg_tours,").append(nTlTours.get()).append('\n').append("transit_legs_drawn,").append(nTlLegs.get()).append('\n')
          .append("transit_legs_outing_skipped,").append(nTlOuting.get()).append('\n').append("transit_legs_zone_outside_los,").append(nTlNoZone.get()).append('\n')
          .append("transit_tours_no_free_car,").append(nTlNoCar.get()).append('\n')
          .append("return_home_too_tight,").append(nRhTight.get()).append('\n').append("return_home_too_tight_expected_returns,").append(rhTightP.sum()).append('\n').append("return_home_honored_by_shift,").append(nRhHonored.get()).append('\n');
        for (int k = 0; k < TL_ALT.length; k++) sb.append("transit_legs_").append(TL_ALT[k]).append(',').append(nTlMode.get(k)).append('\n');
        for (String t : TYPES) sb.append("generated_").append(t).append(',').append(genByType.getOrDefault(t, new AtomicLong()).get()).append('\n')
                                 .append("scheduled_").append(t).append(',').append(schedByType.getOrDefault(t, new AtomicLong()).get()).append('\n');
        logger.info("TASHA summary:\n" + sb);
        String out = AbitResources.instance.getString("base.directory") + "/output/";
        try { new java.io.File(out).mkdirs(); try (PrintWriter pw = new PrintWriter(out + "tasha_summary.csv")) { pw.print(sb); } }
        catch (Exception e) { logger.warn("could not write tasha_summary.csv", e); }
        if (episodesOut) {
            try (PrintWriter pw = new PrintWriter(new java.io.BufferedWriter(new java.io.FileWriter(out + "tasha_episodes.csv"), 1 << 20))) {
                pw.println("person_id,household_id,seg,type,src,start,end,start_drawn,first_start,regen,zone,tour,pos,tour_len,main,main_type,joint_id,main_zone");
                for (String l : epLines) pw.println(l);
            } catch (Exception e) { logger.warn("could not write tasha_episodes.csv", e); }
        }
    }
}
