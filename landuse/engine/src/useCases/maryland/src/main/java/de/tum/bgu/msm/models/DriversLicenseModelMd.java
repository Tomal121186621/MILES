package de.tum.bgu.msm.models;

import de.tum.bgu.msm.container.DataContainer;
import de.tum.bgu.msm.data.dwelling.Dwelling;
import de.tum.bgu.msm.data.geo.MstmZone;
import de.tum.bgu.msm.data.Zone;
import de.tum.bgu.msm.data.household.Household;
import de.tum.bgu.msm.data.person.Person;
import de.tum.bgu.msm.events.impls.person.LicenseEvent;
import de.tum.bgu.msm.models.demography.driversLicense.DriversLicenseModel;
import de.tum.bgu.msm.properties.Properties;
import de.tum.bgu.msm.utils.SiloUtil;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.*;

/**
 * Baltimore 2026 (2026-11-15b): driver's licences in the forecast years follow the Maryland age profile of the corrected base
 * (input_build/carfix_1115), replacing DriversLicenseModelImpl (Munich default odds for unlicensed persons 18+, so that the licence
 * rate went back to about 0.95 after 2016 and ages 16-17 fell to 0). Used only when drivers.license.targets.file is set
 * (ModelBuilderMstm); unset = DriversLicenseModelImpl, the runs of record unchanged.
 *
 * Target P(a, area): licence rate by age band and area (file: area,age_from,age_to,target[,source]; area = city (24510), study
 * (24003, 24005, 24013, 24025, 24027), rest (other Maryland counties), outside (zones outside Maryland; rest when absent)),
 * interpolated by single year of age: linear between the band mid-points (open last band: mid-point age_from + 5), the first segment
 * extended down to the first age of the table, constant above the last mid-point, clipped to [0, 1]; P = 0 below the first age.
 *
 * Yearly step (endYear, after all events of the year, so ages are those reached in the year): an unlicensed person of age a obtains a
 * licence with the cohort hazard h(a) = max(0, (P(a) - P(a-1)) / (1 - P(a-1))). Nobody loses a licence (persons leave only by death or
 * out-migration). In-migrants (checkLicenseCreation, called by InOutMigrationImpl after the household is placed): licence drawn at
 * P(age, area) of the destination; they are skipped by the step of the same year. No LicenseEvents are created.
 */
public class DriversLicenseModelMd extends AbstractModel implements DriversLicenseModel {

    private static final Logger logger = LogManager.getLogger(DriversLicenseModelMd.class);
    public static final String AREA_CITY = "city", AREA_STUDY = "study", AREA_REST = "rest", AREA_OUTSIDE = "outside";
    private static final Set<Integer> STUDY = new HashSet<>(Arrays.asList(24003, 24005, 24013, 24025, 24027));
    private static final int MAX_AGE = 120;

    private final String file;
    private final Map<String, double[]> profile = new HashMap<>();   // area -> P by single year of age 0..MAX_AGE
    private int firstAge = Integer.MAX_VALUE;
    private final Set<Integer> inmigrantsThisYear = new HashSet<>();

    public DriversLicenseModelMd(DataContainer dataContainer, Properties properties, String targetsFile, Random rnd) {
        super(dataContainer, properties, rnd);
        this.file = targetsFile;
        read();
    }

    private void read() {
        Map<String, List<double[]>> bands = new LinkedHashMap<>();   // area -> {age_from, age_to, target}
        try (BufferedReader r = new BufferedReader(new FileReader(file))) {
            List<String> h = Arrays.asList(r.readLine().trim().split(","));
            int ia = h.indexOf("area"), i0 = h.indexOf("age_from"), i1 = h.indexOf("age_to"), it = h.indexOf("target");
            if (ia < 0 || i0 < 0 || i1 < 0 || it < 0) throw new RuntimeException(file + ": needs columns area,age_from,age_to,target");
            String l;
            while ((l = r.readLine()) != null) {
                if (l.trim().isEmpty()) continue;
                String[] c = l.split(",");
                bands.computeIfAbsent(c[ia].trim(), k -> new ArrayList<>()).add(new double[]{Double.parseDouble(c[i0]), Double.parseDouble(c[i1]), Double.parseDouble(c[it])});
            }
        } catch (IOException e) {
            throw new RuntimeException("Could not read licence targets " + file, e);
        }
        for (Map.Entry<String, List<double[]>> e : bands.entrySet()) {
            List<double[]> b = e.getValue();
            b.sort(Comparator.comparingDouble(x -> x[0]));
            int n = b.size();
            double[] mid = new double[n], val = new double[n];
            for (int i = 0; i < n; i++) {
                double[] x = b.get(i);
                mid[i] = (i == n - 1 && x[1] >= 99) ? x[0] + 5 : (x[0] + x[1]) / 2.0;
                val[i] = x[2];
            }
            int a0 = (int) b.get(0)[0];
            firstAge = Math.min(firstAge, a0);
            double[] p = new double[MAX_AGE + 1];
            for (int a = 0; a <= MAX_AGE; a++) {
                if (a < a0) { p[a] = 0; continue; }
                double v;
                if (n == 1 || a >= mid[n - 1]) v = val[n - 1];
                else {
                    int k = 0;
                    while (k < n - 2 && a > mid[k + 1]) k++;   // segment [mid[k], mid[k+1]]; below mid[0] the first segment is extended
                    v = val[k] + (val[k + 1] - val[k]) * (a - mid[k]) / (mid[k + 1] - mid[k]);
                }
                p[a] = Math.max(0, Math.min(1, v));
            }
            profile.put(e.getKey(), p);
        }
        for (String a : new String[]{AREA_CITY, AREA_STUDY, AREA_REST}) {
            if (!profile.containsKey(a)) throw new RuntimeException(file + ": area " + a + " missing");
        }
        if (!profile.containsKey(AREA_OUTSIDE)) profile.put(AREA_OUTSIDE, profile.get(AREA_REST));
    }

    /** target licence rate P(age, area) */
    public double target(int age, String area) {
        return profile.get(area)[Math.max(0, Math.min(MAX_AGE, age))];
    }

    /** cohort hazard h(a) = max(0, (P(a) - P(a-1)) / (1 - P(a-1))) */
    public double hazard(int age, String area) {
        if (age < firstAge) return 0;
        double p = target(age, area), q = age <= 0 ? 0 : target(age - 1, area);
        return q >= 1 ? 0 : Math.max(0, (p - q) / (1 - q));
    }

    private String area(Person pp) {
        Household hh = pp.getHousehold();
        if (hh == null || hh.getDwellingId() <= 0) return null;
        Dwelling dd = dataContainer.getRealEstateDataManager().getDwelling(hh.getDwellingId());
        if (dd == null) return null;
        Zone z = dataContainer.getGeoData().getZones().get(dd.getZoneId());
        if (!(z instanceof MstmZone) || ((MstmZone) z).getCounty() == null) return null;
        int c = ((MstmZone) z).getCounty().getId();
        if (c == 24510) return AREA_CITY;
        if (STUDY.contains(c)) return AREA_STUDY;
        return c / 1000 == 24 ? AREA_REST : AREA_OUTSIDE;
    }

    @Override
    public void setup() {
        StringBuilder s = new StringBuilder();
        for (String a : new String[]{AREA_CITY, AREA_STUDY, AREA_REST, AREA_OUTSIDE}) {
            s.append(String.format(Locale.US, " %s P(16)=%.3f P(17)=%.3f P(18)=%.3f h(17)=%.3f h(18)=%.3f;", a, target(16, a), target(17, a), target(18, a), hazard(17, a), hazard(18, a)));
        }
        logger.info("licence model: maryland age profile on (drivers.license.targets.file = " + file + ");" + s);
    }

    @Override
    public void prepareYear(int year) {
        inmigrantsThisYear.clear();
    }

    @Override
    public Collection<LicenseEvent> getEventsForCurrentYear(int year) {
        return Collections.emptyList();
    }

    @Override
    public boolean handleEvent(LicenseEvent event) {
        return false;
    }

    @Override
    public void endYear(int year) {
        int candidates = 0, licensed = 0;
        for (Person pp : dataContainer.getHouseholdDataManager().getPersons()) {
            if (pp.hasDriverLicense() || pp.getAge() < firstAge || inmigrantsThisYear.contains(pp.getId())) continue;
            String a = area(pp);
            if (a == null) continue;
            candidates++;
            double h = hazard(pp.getAge(), a);
            if (h > 0 && random.nextDouble() < h) {
                licensed++;
                createLicense(pp);
            }
        }
        logger.info("licence model (maryland age profile), year " + year + ": " + licensed + " new licences among " + candidates
                + " unlicensed persons " + firstAge + "+; in-migrants drawn at P: " + inmigrantsThisYear.size());
        inmigrantsThisYear.clear();
    }

    @Override
    public void endSimulation() {
    }

    @Override
    public void checkLicenseCreation(int perId) {
        Person pp = dataContainer.getHouseholdDataManager().getPersonFromId(perId);
        if (pp == null) return;
        inmigrantsThisYear.add(perId);
        String a = area(pp);
        if (a == null) return;
        boolean lic = pp.getAge() >= firstAge && random.nextDouble() < target(pp.getAge(), a);
        pp.setDriverLicense(lic);   // a new person in the model: the licence of the person it was copied from is replaced by the draw
        if (pp.getId() == SiloUtil.trackPp && lic) {
            SiloUtil.trackWriter.println("Person " + pp.getId() + " obtained a drivers license (in-migrant).");
        }
    }

    private void createLicense(Person person) {
        person.setDriverLicense(true);
        if (person.getId() == SiloUtil.trackPp) {
            SiloUtil.trackWriter.println("Person " + person.getId() + " obtained a drivers license.");
        }
    }
}
