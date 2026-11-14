package abm.models.maryland;

import abm.data.plans.Purpose;
import abm.data.pop.Person;
import abm.models.activityGeneration.frequency.FrequencyGenerator;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;
import de.tum.bgu.msm.data.person.Occupation;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.HashMap;
import java.util.Map;
import java.util.Random;

/**
 * RTS-empirical WEEKLY activity generator that is calibrated so a single representative WEEKDAY,
 * extracted downstream (see validation/abit_day.py), reproduces the RTS DAILY tour distribution.
 *
 * ABIT is a weekly model: {@link #calculateNumberOfActivitiesPerWeek} returns a per-WEEK count that
 * the day-of-week assignment spreads across the 7-day diary, and a representative weekday is then
 * pulled out. The RTS coefficient file (rt_freq_rates.csv) holds tours/person/DAY, so those daily
 * rates must be converted to WEEKLY rates before feeding this method (the historical bug fed the raw
 * daily rate as if it were weekly, yielding ~1.4 tours per WHOLE WEEK, hence ~1 tour on a
 * representative weekday and WORK badly under-generated).
 *
 * Conversion used here (calibrated against the RTS daily by-purpose mix, WORK 0.54 / SHOP 0.27 /
 * OTHER 0.56 tours per traveler-day, count distribution ~71/22/6/1):
 *   - WORK (mandatory, gated to EMPLOYED): returns {@link #WORK_DAYS_PER_WEEK} = 5, i.e. a work tour
 *     on every weekday. {@link MarylandDayOfWeekMandatoryAssignment} concentrates those five workdays
 *     on Mon-Fri, so a worker has a work tour on essentially every weekday and the representative
 *     weekday always carries the commute.
 *   - EDUCATION (since stage 2b, 2026-10-21): a STUDENT with a school record (SILO schoolId -> schools.file) draws
 *     Binomial(5, p_band) school days per week, p_band = survey share of students with a school trip on a weekday
 *     (education.targets.file); before that 0, because SILO had no schools.
 *   - Discretionary (SHOP/OTHER/RECREATION/ACCOMPANY): Poisson(daily x {@link #WEEKDAY_WEEKLY_FACTOR}),
 *     scattered by {@link MarylandDayOfWeekDiscretionaryAssignment} over the five weekdays (Poisson
 *     thinning -> ~Poisson(daily) per weekday), so the representative weekday reproduces the RTS daily
 *     shop/other rate. The 6.0 factor is the empirically calibrated value (a naive daily x 7 over-
 *     generates once the representative-weekday is extracted).
 */
public class MarylandFrequencyGenerator implements FrequencyGenerator {

    private static final Map<Purpose, Double> baseRate = new HashMap<>();
    // EDUCATION (stage 2b, 2026-10-21): probability that a student makes a school tour on a weekday, by age band
    // (elementary 5-10, middle 11-13, high 14-17, postsec 18+), metric school_day_prob of education.targets.file
    // (Validation_2026/3_abit/targets_education.csv, from the RTS by education_targets.py). A student with a school
    // record draws Binomial(5, p) school days per week; the mandatory day-of-week assignment puts them on distinct
    // weekdays, so the representative weekday carries a school tour with probability p. Without the file: 0 tours.
    private static final Map<String, Double> eduDayProb = new HashMap<>();
    private static final int SCHOOL_DAYS_PER_WEEK = 5;
    private static boolean loaded = false;
    private final Random rnd = AbitUtils.getRandomObject();
    // an EMPLOYED person makes a work tour on every weekday (Mon-Fri); the mandatory day-of-week
    // assignment places these 5 workdays on the 5 weekdays.
    private static final int WORK_DAYS_PER_WEEK = 5;
    // daily->weekly conversion for discretionary purposes, calibrated PER PURPOSE against the RTS daily
    // by-purpose tour mix (see class javadoc; SHOP is slightly higher than the others). The
    // discretionary tours are concentrated on the representative weekday
    // (MarylandDayOfWeekDiscretionaryAssignment), so these factors size the daily bundle that day
    // carries. They absorb (a) the ~2x per-capita volume needed because a work-tour-every-weekday
    // population has ~2x the RTS pooled-day traveler pool, and (b) the ~40% of discretionary tours
    // dropped by destination choice for unreachable zones. Overridable via -D for recalibration.
    private static final double F_SHOP =
            Double.parseDouble(System.getProperty("abit.disc.factor.shop", "5.7"));
    private static final double F_OTHER =
            Double.parseDouble(System.getProperty("abit.disc.factor.other", "5.2"));
    private static double discFactor(Purpose purpose) {
        return purpose == Purpose.SHOPPING ? F_SHOP : F_OTHER;
    }

    public MarylandFrequencyGenerator() {
        if (!loaded) load();
    }

    // Validation_2026 stage 3 (2026-10-22): rates and weekly factors by purpose x person segment.  rt_freq_rates.csv has the
    // columns purpose,rate[,segment[,factor]]: segment = worker | student | nonworker | retiree | all (default all), factor =
    // the daily->weekly multiplier that the calibration adjusts (default: the -D factors above).  Weekly Poisson mean =
    // rate x factor; a (purpose, segment) row overrides the (purpose, all) row.  For EDUCATION the factor multiplies the
    // school-day probability of the band (capped at 1).
    private static final Map<String, Double> segRate = new HashMap<>();     // "PURPOSE|segment" -> rate
    private static final Map<String, Double> segFactor = new HashMap<>();   // "PURPOSE|segment" -> factor

    /** worker | student_<band> (elementary, middle, high, postsec by age) | retiree | toddler (under 5) | nonworker */
    static String segmentOf(Person person) {
        switch (person.getOccupation()) {
            case EMPLOYED: return "worker";
            case STUDENT: return "student_" + abm.io.input.MarylandLosDataReader.bandOf(person.getAge());
            case RETIREE: return "retiree";
            case TODDLER: return "toddler";
            default: return "nonworker";
        }
    }

    /** (purpose, segment) -> (purpose, student) for a student band -> (purpose, all) */
    private static Double lookup(Map<String, Double> m, Purpose p, String seg) {
        Double v = m.get(p + "|" + seg);
        if (v == null && seg.startsWith("student_")) v = m.get(p + "|student");
        return v != null ? v : m.get(p + "|all");
    }

    private static synchronized void load() {
        if (loaded) return;
        String f = AbitResources.instance.getString("rt.freq.rates");
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String[] h = br.readLine().split(",");
            int iP = -1, iR = -1, iS = -1, iF = -1;
            for (int i = 0; i < h.length; i++) {
                String c = h[i].trim().toLowerCase();
                if (c.equals("purpose")) iP = i; else if (c.equals("rate")) iR = i; else if (c.equals("segment")) iS = i; else if (c.equals("factor")) iF = i;
            }
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                Purpose p = Purpose.valueOf(r[iP].trim().toUpperCase());
                double rate = Double.parseDouble(r[iR].trim());
                String seg = iS >= 0 && r.length > iS && !r[iS].trim().isEmpty() ? r[iS].trim().toLowerCase() : "all";
                if (seg.equals("all")) baseRate.put(p, rate);
                segRate.put(p + "|" + seg, rate);
                if (iF >= 0 && r.length > iF && !r[iF].trim().isEmpty()) segFactor.put(p + "|" + seg, Double.parseDouble(r[iF].trim()));
            }
        } catch (Exception e) {
            throw new RuntimeException("MarylandFrequencyGenerator load failed", e);
        }
        String ef = AbitResources.instance.getString("education.targets.file");
        if (ef == null) {
            org.apache.log4j.Logger.getLogger(MarylandFrequencyGenerator.class).warn("education.targets.file not set: no EDUCATION tours");
        } else {
            try (BufferedReader br = new BufferedReader(new FileReader(ef))) {
                String[] h = br.readLine().split(",");
                int iB = -1, iM = -1, iV = -1;
                for (int i = 0; i < h.length; i++) {
                    if (h[i].trim().equals("band")) iB = i; else if (h[i].trim().equals("metric")) iM = i; else if (h[i].trim().equals("value")) iV = i;
                }
                String line;
                while ((line = br.readLine()) != null) {
                    String[] r = line.split(",");
                    if (r[iM].trim().equals("school_day_prob")) eduDayProb.put(r[iB].trim(), Double.parseDouble(r[iV].trim()));
                }
            } catch (Exception e) {
                throw new RuntimeException("education.targets.file load failed: " + ef, e);
            }
            org.apache.log4j.Logger.getLogger(MarylandFrequencyGenerator.class).info("EDUCATION school-day probability by band: " + eduDayProb);
        }
        org.apache.log4j.Logger.getLogger(MarylandFrequencyGenerator.class).info("frequency rates by purpose|segment: " + segRate + " factors: " + segFactor);
        loaded = true;
    }

    @Override
    public int calculateNumberOfActivitiesPerWeek(Person person, Purpose purpose) {
        Occupation occ = person.getOccupation();
        String seg = segmentOf(person);
        if (purpose == Purpose.EDUCATION) {
            // a student with a school record attends on each weekday with the survey probability of the age band
            if (occ != Occupation.STUDENT || person.getSchool() == null) return 0;
            Double p = eduDayProb.get(abm.io.input.MarylandLosDataReader.bandOf(person.getAge()));
            if (p == null) return 0;
            Double ef = lookup(segFactor, purpose, seg);
            double pp = Math.min(1.0, p * (ef != null ? ef : 1.0));
            int days = 0;
            for (int d = 0; d < SCHOOL_DAYS_PER_WEEK; d++) if (rnd.nextDouble() < pp) days++;
            return days;
        }
        if (purpose == Purpose.WORK) {
            // an EMPLOYED person works every weekday -> return the number of weekdays; the mandatory
            // day-of-week assignment places these on Mon-Fri (distinct days). Others: no work tour.
            return occ == Occupation.EMPLOYED ? WORK_DAYS_PER_WEEK : 0;
        }
        // discretionary: weekly Poisson mean = daily rate x weekly factor of the (purpose, segment); the discretionary
        // day-of-week assignment places them on the weekdays so the representative weekday reproduces the survey rate.
        // Persons under 5 (TODDLER) travel only when the rates file carries rows of the segment "toddler" (second pass of
        // stage 3, 2026-10-22: the survey's under-5s make 1.28 tours per traveller-day, 84 % as car passengers, and are
        // 6.5 % of its travellers); without such rows they make no tours, as before.
        if (occ == Occupation.TODDLER && !segRate.containsKey(purpose + "|toddler")) return 0;
        Double r = lookup(segRate, purpose, seg);
        double rate = r != null ? r : baseRate.getOrDefault(purpose, 0.0);
        Double fac = lookup(segFactor, purpose, seg);
        double factor = fac != null ? fac : discFactor(purpose);
        return poisson(rate * factor);
    }

    private int poisson(double lambda) {
        if (lambda <= 0) return 0;
        double l = Math.exp(-lambda), p = 1.0;
        int k = 0;
        do { k++; p *= rnd.nextDouble(); } while (p > l);
        return k - 1;
    }
}
