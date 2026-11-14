package de.tum.bgu.msm.models;

import de.tum.bgu.msm.container.DataContainer;
import de.tum.bgu.msm.data.accessibility.Accessibility;
import de.tum.bgu.msm.data.dwelling.Dwelling;
import de.tum.bgu.msm.data.household.Household;
import de.tum.bgu.msm.data.household.HouseholdUtil;
import de.tum.bgu.msm.models.autoOwnership.CreateCarOwnershipModel;
import de.tum.bgu.msm.properties.Properties;
import de.tum.bgu.msm.utils.SiloUtil;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

/**
 * Baltimore 2026 household car ownership (0, 1, 2, 3+ vehicles). The open-source Maryland use case has no working
 * car-ownership model (its script resource is missing and nothing registers it), so new households kept zero cars.
 *
 * Multinomial logit with all coefficients in a data file, so the model is estimated and calibrated on the study area's
 * ACS PUMS (vehicles by workers, household size, income, county), nothing in code:
 *   car_ownership_coefficients.csv   header: alternative,variable,value
 *       alternative in {1,2,3}  (0 cars is the base);  variable in
 *       {asc, hhSize, workers, income_k (k = income class 1..12), transitAcc, density_k (k = job-density class 1..10),
 *        accLogsumGain (Baltimore 2026, accessibility.model = logsum: non-work logsum accessibility of the household's income
 *        group with cars minus without a car, A(inc_carge) - A(inc_nocar), utils, at the home zone)}
 *   car_ownership_region_constants.csv   header: region,asc1,asc2,asc3   (additive per-region constants, calibration result)
 * Income classes: < 10k, 10-15k, 15-30k, 30-40k, 40-50k, 50-60k, 60-75k, 75-100k, 100-125k, 125-150k, 150-200k, 200k+ (2016 $).
 *
 * Two uses:
 *   simulateCarOwnership(hh)  for a newly formed household (in-migrant, marriage, divorce, leaving the parental home)
 *   endYear                   re-draw only for households whose size or number of workers changed during the year, or
 *                             which were created during the year; all other households keep their cars
 *                             (re-drawing every household every year, as the old model did, erased the base-year distribution).
 */
public class CarOwnershipModelMd extends AbstractModel implements CreateCarOwnershipModel, ModelUpdateListener {

    private static final Logger logger = LogManager.getLogger(CarOwnershipModelMd.class);
    private static final int[] INCOME_BOUNDS = {10000, 15000, 30000, 40000, 50000, 60000, 75000, 100000, 125000, 150000, 200000};

    private final Accessibility accessibility;
    private final Map<Integer, Map<String, Double>> coef = new HashMap<>();     // alternative -> variable -> value
    private final Map<Integer, double[]> regionAsc = new HashMap<>();           // region -> [asc1, asc2, asc3]
    private final Map<Integer, long[]> lastState = new HashMap<>();             // hhId -> [size, workers]
    private int updatedThisYear, createdThisYear;

    // Baltimore 2026 (2026-11-09): car.ownership.spec = respec selects the re-specified model (CarOwnershipRespec); record (default)
    // = the model above, unchanged. Location variables at the PUMA level as in the estimation (car.ownership.respec.location.file:
    // puma,zone,hu,density_2016): ln dwelling density = ln(density_2016 x current stock / base-year stock of the PUMA, zones split
    // between PUMAs by their housing units), accessibility gain = housing-unit weighted mean of the zones' gain; a zone in several
    // PUMAs takes the hu-weighted mean over them; zones outside the file use their own dwellings per km2 and their own gain.
    private final boolean respec = "respec".equalsIgnoreCase(de.tum.bgu.msm.models.resloc.ReslocProperties.get("car.ownership.spec", "record"));
    private double densityCentre;
    private final Map<Integer, Integer> pumaIndex = new HashMap<>();
    private final Map<Integer, List<double[]>> zonePumas = new HashMap<>();   // zone -> {puma index, hu, share of the zone's hu}
    private double[] pumaDensity2016, pumaStockBase;
    private final Map<Integer, Double> zoneLnDensity = new HashMap<>();
    private final Map<String, Double> zoneGain = new HashMap<>();             // zone|group -> gain
    private static final String[] GROUPS = {"LOW", "MEDIUM", "HIGH", "VERY_HIGH"};

    public CarOwnershipModelMd(DataContainer dataContainer, Accessibility accessibility, Properties properties, Random rnd) {
        super(dataContainer, properties, rnd);
        this.accessibility = accessibility;
    }

    @Override
    public void setup() {
        final String base = properties.main.baseDirectory;
        readCoefficients(base + properties.householdData.carOwnershipCoefficientsFile);
        if (properties.householdData.carOwnershipRegionConstantsFile != null && !properties.householdData.carOwnershipRegionConstantsFile.isBlank()) {
            readRegionConstants(base + properties.householdData.carOwnershipRegionConstantsFile);
        }
        if (respec) {
            if (!coef.containsKey(0) || !coef.get(0).containsKey("ln_density_centre"))
                throw new RuntimeException("car.ownership.spec = respec: the coefficient file needs alternative 0, variable ln_density_centre");
            densityCentre = coef.get(0).get("ln_density_centre");
            readPumaFile(de.tum.bgu.msm.models.resloc.ReslocProperties.path("car.ownership.respec.location.file", "input/car_ownership_puma_respec.csv"));
            pumaStockBase = pumaStock();
            updateLocation();
        }
        rememberState();
        logger.info("Car ownership model: coefficients for " + coef.size() + " alternatives, region constants for " + regionAsc.size() + " regions");
    }

    private void readCoefficients(String file) {
        try (BufferedReader r = new BufferedReader(new FileReader(file))) {
            String[] h = r.readLine().split(","); int iA = col(h, "alternative"), iV = col(h, "variable"), iX = col(h, "value");
            String line;
            while ((line = r.readLine()) != null) {
                if (line.isBlank()) continue;
                String[] x = line.split(",");
                coef.computeIfAbsent(Integer.parseInt(x[iA].trim()), k -> new HashMap<>()).put(x[iV].trim(), Double.parseDouble(x[iX].trim()));
            }
        } catch (IOException e) { throw new RuntimeException("Could not read car ownership coefficients " + file, e); }
    }

    private void readRegionConstants(String file) {
        try (BufferedReader r = new BufferedReader(new FileReader(file))) {
            String[] h = r.readLine().split(","); int iR = col(h, "region"), i1 = col(h, "asc1"), i2 = col(h, "asc2"), i3 = col(h, "asc3");
            String line;
            while ((line = r.readLine()) != null) {
                if (line.isBlank()) continue;
                String[] x = line.split(",");
                regionAsc.put(Integer.parseInt(x[iR].trim()), new double[]{Double.parseDouble(x[i1].trim()), Double.parseDouble(x[i2].trim()), Double.parseDouble(x[i3].trim())});
            }
        } catch (IOException e) { throw new RuntimeException("Could not read car ownership region constants " + file, e); }
    }

    private static int col(String[] h, String n) {
        for (int i = 0; i < h.length; i++) if (h[i].trim().equals(n)) return i;
        throw new RuntimeException("Column " + n + " missing in car ownership file");
    }

    private void readPumaFile(String file) {
        final List<Double> dens = new ArrayList<>();
        try (BufferedReader r = new BufferedReader(new FileReader(file))) {
            String[] h = r.readLine().split(","); int iP = col(h, "puma"), iZ = col(h, "zone"), iH = col(h, "hu"), iD = col(h, "density_2016");
            String line;
            while ((line = r.readLine()) != null) {
                if (line.isBlank()) continue;
                String[] x = line.split(",");
                final int p = Integer.parseInt(x[iP].trim());
                Integer k = pumaIndex.get(p);
                if (k == null) { k = dens.size(); pumaIndex.put(p, k); dens.add(Double.parseDouble(x[iD].trim())); }
                zonePumas.computeIfAbsent(Integer.parseInt(x[iZ].trim()), q -> new ArrayList<>()).add(new double[]{k, Double.parseDouble(x[iH].trim()), 0});
            }
        } catch (IOException e) { throw new RuntimeException("Could not read car ownership location file " + file, e); }
        pumaDensity2016 = dens.stream().mapToDouble(Double::doubleValue).toArray();
        for (List<double[]> l : zonePumas.values()) {
            double t = 0; for (double[] e : l) t += e[1];
            for (double[] e : l) e[2] = t > 0 ? e[1] / t : 1. / l.size();
        }
        logger.info("Car ownership (respec): " + pumaDensity2016.length + " PUMAs, " + zonePumas.size() + " zones read from " + file);
    }

    private Map<Integer, Integer> dwellingsByZone() {
        final Map<Integer, Integer> n = new HashMap<>();
        for (Dwelling d : dataContainer.getRealEstateDataManager().getDwellings()) n.merge(d.getZoneId(), 1, Integer::sum);
        return n;
    }

    /** dwellings of each PUMA, zones split by their housing-unit shares */
    private double[] pumaStock() {
        final double[] s = new double[pumaDensity2016.length];
        final Map<Integer, Integer> n = dwellingsByZone();
        for (Map.Entry<Integer, List<double[]>> e : zonePumas.entrySet()) {
            final int dz = n.getOrDefault(e.getKey(), 0);
            for (double[] q : e.getValue()) s[(int) q[0]] += q[2] * dz;
        }
        return s;
    }

    /** ln density and accessibility gain of every zone for the current stock and accessibility (respec) */
    private void updateLocation() {
        final double[] s = pumaStock();
        final double[] lnD = new double[s.length];
        for (int p = 0; p < s.length; p++) lnD[p] = Math.log(pumaDensity2016[p] * (pumaStockBase[p] > 0 ? s[p] / pumaStockBase[p] : 1));
        final de.tum.bgu.msm.models.resloc.AccessibilityLogsumMd ls = accessibility instanceof de.tum.bgu.msm.models.resloc.AccessibilityLogsumMd
                ? (de.tum.bgu.msm.models.resloc.AccessibilityLogsumMd) accessibility : null;
        if (ls == null) throw new RuntimeException("car.ownership.spec = respec needs accessibility.model = logsum");
        // PUMA gain: hu-weighted mean over the PUMA's zones of A(carge) and of A(nocar), zones without a value skipped (s01_data.puma_location)
        final double[][] sc = new double[s.length][4], wc = new double[s.length][4], sn = new double[s.length][4], wn = new double[s.length][4];
        for (Map.Entry<Integer, List<double[]>> e : zonePumas.entrySet()) {
            for (int g = 0; g < 4; g++) {
                final double ac = ls.getLogsum(e.getKey(), GROUPS[g] + "_" + ls.carLabel(2), "nonwork"), an = ls.getLogsum(e.getKey(), GROUPS[g] + "_" + ls.carLabel(0), "nonwork");
                for (double[] q : e.getValue()) {
                    final int p = (int) q[0];
                    if (!Double.isNaN(ac)) { sc[p][g] += q[1] * ac; wc[p][g] += q[1]; }
                    if (!Double.isNaN(an)) { sn[p][g] += q[1] * an; wn[p][g] += q[1]; }
                }
            }
        }
        zoneLnDensity.clear(); zoneGain.clear();
        final Map<Integer, Integer> n = dwellingsByZone();
        for (de.tum.bgu.msm.data.Zone z : dataContainer.getGeoData().getZones().values()) {
            final List<double[]> l = zonePumas.get(z.getZoneId());
            if (l != null) {
                double d = 0; final double[] gg = new double[4];
                for (double[] q : l) {
                    final int p = (int) q[0]; d += q[2] * lnD[p];
                    for (int g = 0; g < 4; g++) gg[g] += q[2] * ((wc[p][g] > 0 ? sc[p][g] / wc[p][g] : 0) - (wn[p][g] > 0 ? sn[p][g] / wn[p][g] : 0));
                }
                zoneLnDensity.put(z.getZoneId(), d);
                for (int g = 0; g < 4; g++) zoneGain.put(z.getZoneId() + "|" + g, gg[g]);
            } else {
                final double km2 = z.getArea_sqmi() * 2.58999;
                zoneLnDensity.put(z.getZoneId(), Math.log(Math.max(n.getOrDefault(z.getZoneId(), 0), 1) / Math.max(km2, 1e-6)));
                for (int g = 0; g < 4; g++) {
                    final double v = ls.getLogsum(z.getZoneId(), GROUPS[g] + "_" + ls.carLabel(2), "nonwork") - ls.getLogsum(z.getZoneId(), GROUPS[g] + "_" + ls.carLabel(0), "nonwork");
                    zoneGain.put(z.getZoneId() + "|" + g, Double.isNaN(v) ? 0 : v);
                }
            }
        }
    }

    private double[] respecProbabilities(Household hh, Dwelling dd) {
        int p16 = 0, children = 0, amax = 0;
        for (de.tum.bgu.msm.data.person.Person p : hh.getPersons().values()) {
            if (p.getAge() >= 16) p16++; else children++;
            amax = Math.max(amax, p.getAge());
        }
        final String gname = hh.getHouseholdType().getIncomeCategory().name();
        int g = 0; for (int k = 0; k < 4; k++) if (GROUPS[k].equals(gname)) g = k;
        final double[] x = CarOwnershipRespec.vars(HouseholdUtil.getNumberOfWorkers(hh), p16, children, hh.getHhSize(), HouseholdUtil.getAnnualHhIncome(hh), amax,
                dd.getType().toString(), dd.getBedrooms(), zoneLnDensity.getOrDefault(dd.getZoneId(), 0.), zoneGain.getOrDefault(dd.getZoneId() + "|" + g, 0.), densityCentre);
        final double[] u = CarOwnershipRespec.utilities(coef, x);
        final int region = dataContainer.getGeoData().getZones().get(dd.getZoneId()).getRegion().getId();
        final double[] rAsc = regionAsc.getOrDefault(region, new double[]{0, 0, 0});
        final double[] e = new double[4]; e[0] = 1; double sum = 1;
        for (int a = 1; a <= 3; a++) { e[a] = Math.exp(u[a - 1] + rAsc[a - 1]); sum += e[a]; }
        for (int a = 0; a < 4; a++) e[a] /= sum;
        return e;
    }

    private static int incomeClass(int income) {
        for (int i = 0; i < INCOME_BOUNDS.length; i++) if (income < INCOME_BOUNDS[i]) return i + 1;
        return INCOME_BOUNDS.length + 1;
    }

    /** probabilities of 0, 1, 2, 3+ cars for this household at its current dwelling */
    double[] probabilities(Household hh) {
        final Dwelling dd = dataContainer.getRealEstateDataManager().getDwelling(hh.getDwellingId());
        if (dd == null) return new double[]{1, 0, 0, 0};
        if (respec) return respecProbabilities(hh, dd);
        final int size = hh.getHhSize();
        final int workers = HouseholdUtil.getNumberOfWorkers(hh);
        final int inc = incomeClass(HouseholdUtil.getAnnualHhIncome(hh));
        final double transitAcc = accessibility.getTransitAccessibilityForZone(dataContainer.getGeoData().getZones().get(dd.getZoneId()));
        final int density = dataContainer.getJobDataManager().getJobDensityCategoryOfZone(dd.getZoneId());
        final int region = dataContainer.getGeoData().getZones().get(dd.getZoneId()).getRegion().getId();
        final double[] rAsc = regionAsc.getOrDefault(region, new double[]{0, 0, 0});
        double gain = 0;
        if (accessibility instanceof de.tum.bgu.msm.models.resloc.AccessibilityLogsumMd) {
            final de.tum.bgu.msm.models.resloc.AccessibilityLogsumMd ls = (de.tum.bgu.msm.models.resloc.AccessibilityLogsumMd) accessibility;
            final String g = hh.getHouseholdType().getIncomeCategory().name();
            gain = ls.getLogsum(dd.getZoneId(), g + "_" + ls.carLabel(2), "nonwork") - ls.getLogsum(dd.getZoneId(), g + "_" + ls.carLabel(0), "nonwork");
            if (Double.isNaN(gain)) gain = 0;
        }
        final double[] expU = new double[4]; expU[0] = 1.0; double sum = 1.0;
        for (int a = 1; a <= 3; a++) {
            final Map<String, Double> c = coef.getOrDefault(a, Map.of());
            double u = c.getOrDefault("asc", 0.0) + rAsc[a - 1] + c.getOrDefault("hhSize", 0.0) * size + c.getOrDefault("workers", 0.0) * workers
                    + c.getOrDefault("transitAcc", 0.0) * transitAcc + c.getOrDefault("income_" + inc, 0.0) + c.getOrDefault("density_" + density, 0.0)
                    + c.getOrDefault("accLogsumGain", 0.0) * gain;
            expU[a] = Math.exp(u); sum += expU[a];
        }
        for (int a = 0; a < 4; a++) expU[a] /= sum;
        return expU;
    }

    @Override
    public void simulateCarOwnership(Household hh) {
        hh.setAutos(SiloUtil.select(probabilities(hh), random));
        lastState.put(hh.getId(), new long[]{hh.getHhSize(), HouseholdUtil.getNumberOfWorkers(hh)});
        createdThisYear++;
    }

    @Override
    public void run() {
        for (Household hh : dataContainer.getHouseholdDataManager().getHouseholds()) simulateCarOwnership(hh);
    }

    private void rememberState() {
        lastState.clear();
        for (Household hh : dataContainer.getHouseholdDataManager().getHouseholds()) {
            lastState.put(hh.getId(), new long[]{hh.getHhSize(), HouseholdUtil.getNumberOfWorkers(hh)});
        }
    }

    @Override
    public void prepareYear(int year) {
        updatedThisYear = 0; createdThisYear = 0;
        if (respec) updateLocation();
    }

    @Override
    public void endYear(int year) {
        for (Household hh : dataContainer.getHouseholdDataManager().getHouseholds()) {
            final long[] prev = lastState.get(hh.getId());
            final long size = hh.getHhSize(), workers = HouseholdUtil.getNumberOfWorkers(hh);
            if (prev == null || prev[0] != size || prev[1] != workers) {
                hh.setAutos(SiloUtil.select(probabilities(hh), random));
                updatedThisYear++;
            }
        }
        rememberState();
        logger.info("Car ownership " + year + ": re-drawn for " + updatedThisYear + " households with changed size or workers; " + createdThisYear + " new households");
    }

    @Override
    public void endSimulation() {}
}
