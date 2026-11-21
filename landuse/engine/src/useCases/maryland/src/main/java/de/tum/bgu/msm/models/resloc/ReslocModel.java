package de.tum.bgu.msm.models.resloc;

import de.tum.bgu.msm.data.dwelling.StructuralVacancy;
import de.tum.bgu.msm.container.DataContainer;
import de.tum.bgu.msm.data.Region;
import de.tum.bgu.msm.data.Zone;
import de.tum.bgu.msm.data.dwelling.Dwelling;
import de.tum.bgu.msm.data.geo.GeoData;
import de.tum.bgu.msm.data.household.Household;
import de.tum.bgu.msm.data.household.HouseholdUtil;
import de.tum.bgu.msm.data.job.Job;
import de.tum.bgu.msm.data.person.Occupation;
import de.tum.bgu.msm.data.person.Person;
import de.tum.bgu.msm.util.matrices.IndexedDoubleMatrix2D;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.matsim.api.core.v01.TransportMode;

import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.FileReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.zip.GZIPInputStream;

/**
 * Baltimore 2026: the residential location choice model estimated on Baltimore-region data (2_silo/resloc,
 * ESTIMATION_REPORT.md), a three-level nested logit estimated sequentially:
 *   level 1  region r (44 SILO regions), ACS PUMS 2014-2018 movers:
 *            U_r = lam_B IV_B + lam_A IV_A + distance (piecewise, to other regions) + same region + same state
 *                  + commute ln(1+t) to the workers' job zones (x ln income) + school (x children) + crime (x children) [+ asc_r]
 *   level 2  zone x structure-type cell (z, t) within the region, 2017/18 RTS:
 *            V_B = theta ln D_zt + accessibility logsums (work, non-work; x children, x 65+, x no car) + commute ln(1+t)
 *                  (x ln income) + ln mean monthly cost of the zone (x ln income)
 *   level 3  dwelling d within the location, ACS PUMS movers within their PUMA:
 *            V_A = housing-cost burden (piecewise, knots 30 % and 50 % of income) + ln cost + bedroom shortfall / excess
 *                  (by income group) + structure type (x size, children, 65+, ln income) + built in the last 5 years
 * IV_B(r) = ln sum_cells exp(V_B without commute); IV_A(r) = ln mean over 200 vacant dwellings of r of exp(V_A).
 * In the engine the household samples 20 vacant dwellings of the chosen region uniformly (MovesModelImpl); dwelling d gets the
 * weight exp(V_A(d) + V_B(z,t) - ln D_zt): uniform sampling of vacancies contributes the size of the cell, so the estimated size
 * coefficient theta enters as (theta - 1) ln D_zt.
 * Every variable is defined as in the estimation scripts (s04_dwelling.py, s05_zone.py, s06_region.py). Income enters as the
 * midpoint of a $2,500 bin in the cached inclusive values (exact in the dwelling weights).
 *
 * Move-or-not (Baltimore 2026, replaces the inherited satisfaction utility, which contained race):
 *   utility of a dwelling d (zone z, cell t, region r) for household h, on the scale of the region level:
 *       u(d) = X_r + lam_B (V_B(z,t) - ln D_zt) + lam_A V_A(d)
 *   X_r = the region terms of U_r (distance from the current home, same region, same state, school, crime, commute; the commute
 *   from the dwelling's own zone); V_B - ln D_zt is the per-dwelling share of the cell utility (IV_B = ln sum_d exp(V_B - ln D_zt)).
 *   Expected maximum utility of the search set (a region drawn with P_r = exp(U_r) / sum exp(U_r) among regions with vacancies,
 *   then the best of K = 20 sampled dwellings, whose log-sum is ln K + ln mean exp(.)):
 *       EMU = sum_r P_r [ X_r + lam_B (IV_B(r) - ln N_r + ln K) + lam_A IV_A(r) ],  N_r = dwellings of region r
 *   gap = EMU - u(current); gap0 = the gap in the first year of the household's tenure (base year for base households)
 *   P(search) = 1 - 1 / (1 + shift exp(scale (gap - kappa gap0) + gamma ln(1 + years in the dwelling)))
 *   kappa = resloc.move.reference (1): the systematic utility of the current dwelling omits the household's own match with it
 *   (under random utility the chosen dwelling's utility is the log-sum of its choice set, not its systematic part); with kappa = 0
 *   the base households, whose dwellings come from the synthetic population and not from this model, had large gaps and the
 *   households that had moved small ones, and the mean search probability fell 11.6, 8.4, 7.6, 7.0 % in 2016-2019 as the
 *   population sorted. With kappa = 1 the decision responds to the change since the household moved in (income, household
 *   size, workplaces and commutes, prices, accessibility) and to the years in the dwelling.
 *   shift = move.or.not.binomial.log.shift.parameter (calibrated to the ACS move rate), scale = resloc.move.scale (1: the logit
 *   scale of the estimated region level), gamma = resloc.move.duration (from the ACS MV distribution, input_build/build_tenure.py).
 *   The household that searched moves only if V_A + V_B - ln D_zt of the found dwelling exceeds that of its current one
 *   (HousingStrategyMstm.acceptsMove, dwellingLevelUtility): the region-level moving costs already entered the region draw.
 */
public class ReslocModel {

    private static final Logger logger = LogManager.getLogger(ReslocModel.class);
    public static volatile int currentYear = 2016;
    private static final String[] CELL_TYPES = {"SFD", "SFA", "MF", "MH"};
    private static final String[] DW_TYPES = {"SFA", "MF234", "MF5plus", "MH"};

    private final DataContainer dataContainer;
    private final GeoData geoData;
    private final AccessibilityLogsumMd accessibility;
    private final Map<String, Double> cDw = new HashMap<>(), cZone = new HashMap<>(), cReg = new HashMap<>();
    private final int[] zoneIds; private final Map<Integer, Integer> zIdx = new HashMap<>();
    private final int[] regionIds; private final Map<Integer, Integer> rIdx = new HashMap<>();
    private final int[] zoneRegion; private final int[] regionState; private final int[] zoneState;
    private final double[] regSchool, regCrime;
    private final float[][] pt;           // transit door-to-door time, zone index x zone index (180 if no path)
    private final int ivSample;
    // per year
    private double[][] D;                 // dwellings by zone index and cell type
    private double[] lnCostZ;
    private float[][] tZoneRegion;        // car time from zone to region (dwelling-weighted over the region's zones)
    private float[][] tRegionZoneCar, tRegionZoneP;
    private List<List<Dwelling>> ivDwellings;
    private final Map<String, double[]> cacheIvB = new ConcurrentHashMap<>(), cacheIvA = new ConcurrentHashMap<>();
    private final Random random = new Random(20261022);
    private double[] regN;                // dwellings by region index (stock)
    // Baltimore 2026 (2026-11-14, switch resloc.region.vacancy.availability, default false = the model of record unchanged):
    // availability of a region in the search, a_r = min(1, v_r / v*_r), v_r = vacant dwellings of region r now (live count) / its
    // stock at the start of the year, v*_r = SILO's structural vacancy rate of the dwelling types (DwellingType.getStructuralVacancyRate,
    // SFD/SFA/MH 3 %, MF234 4 %, MF5plus 5 %) averaged over the region's stock. The estimated region level carries the size of the
    // stock (IV_B over ln D_zt), i.e. it assumes that vacancies are offered in proportion to the stock at the structural rate, as in
    // the observed market; below that rate a region is offered less often (constrained logit: an alternative is available with the
    // probability that it is not full; Martinez & Henriquez 2007, de Palma, Picard & Waddell 2007). No free parameter.
    // The weight of region r in the region draw of the search and in the expected maximum utility of the move-or-not decision
    // becomes exp(U_r) a_r (a_r = 1 when the switch is off, so the arithmetic of the record model is unchanged).
    private final boolean vacancyAvailability = Boolean.parseBoolean(ReslocProperties.get("resloc.region.vacancy.availability", "false"));
    private double[] regStructVac;        // stock-weighted structural vacancy rate by region index
    private final double moveScale = Double.parseDouble(ReslocProperties.get("resloc.move.scale", "1.0"));
    private final double moveDuration = Double.parseDouble(ReslocProperties.get("resloc.move.duration", "0.0"));
    private final double lnSearch = Math.log(Double.parseDouble(ReslocProperties.get("resloc.move.search.size", "20")));
    // years in the dwelling: year the household moved into its dwelling (MovesModelMd.moveHousehold records every relocation);
    // base-year households draw it from the ACS distribution by age of the oldest member (resloc.tenure.file)
    private static final Map<Integer, Integer> moveInYear = new ConcurrentHashMap<>();
    private final List<double[]> tenureRows = new ArrayList<>();   // age_from, age_to, dur_from, dur_to, share
    private final Random tenureRandom = de.tum.bgu.msm.utils.SiloUtil.provideNewRandom();
    private final double moveReference = Double.parseDouble(ReslocProperties.get("resloc.move.reference", "0.0"));
    private static final Map<Integer, double[]> gapAtEntry = new ConcurrentHashMap<>();   // household -> {tenure start year, gap}
    private double diagGap, diagGapEff, diagLnDur, diagP; private long diagN;

    // Baltimore 2026 (2026-11-09): resloc.spec = respec selects the re-specified model (ReslocRespecUtility); record (default) = the
    // model above, unchanged. Under respec: the zone part reads its own accessibility file (resloc.respec.accessibility.file, pattern
    // with {year}; the multimodal logsum A_ls of the estimation), the county part reads the school learning growth (column growth of
    // resloc.region.attributes) and the county adjacency (resloc.region.adjacency: region_a,region_b).
    private final boolean respec = "respec".equalsIgnoreCase(ReslocProperties.get("resloc.spec", "record"));
    private static final String[] INC_GROUPS = {"LOW", "MEDIUM", "HIGH", "VERY_HIGH"};
    private double[] regGrowth;
    private boolean[][] regAdjacent;
    private double[][] shareOwnGroup;     // zone index x income group: share of the zone's households in the group (current population)
    private final String accRespecPattern = ReslocProperties.path("resloc.respec.accessibility.file", "");
    private final Map<String, double[]> accRespec = new HashMap<>();   // segment|purpose -> A by zone index
    private int accRespecYear = Integer.MIN_VALUE;
    // Baltimore 2026 (2026-11-10, respec): land use of the zone part, recomputed in prepareYear from the current dwellings and jobs
    // (dwelling and job density, retail density, mix); acres and the paid-parking share fixed (resloc.respec.zone.attributes:
    // zone,acres,park); landUse[z] in the order of ReslocRespecUtility.LU_NAMES
    private double[] zoneAcres, zonePark;
    private double[][] landUse;

    public ReslocModel(DataContainer dataContainer, AccessibilityLogsumMd accessibility) {
        this.dataContainer = dataContainer;
        this.geoData = dataContainer.getGeoData();
        this.accessibility = accessibility;
        readCoefficients(ReslocProperties.path("resloc.dwelling.coefficients", "input/resloc_dwelling_mnl.csv"), true);
        readCoefficients(ReslocProperties.path("resloc.region.coefficients", "input/resloc_region_mnl.csv"), false);
        zoneIds = geoData.getZones().keySet().stream().mapToInt(Integer::intValue).sorted().toArray();
        for (int i = 0; i < zoneIds.length; i++) zIdx.put(zoneIds[i], i);
        regionIds = geoData.getRegions().keySet().stream().mapToInt(Integer::intValue).sorted().toArray();
        for (int i = 0; i < regionIds.length; i++) rIdx.put(regionIds[i], i);
        zoneRegion = new int[zoneIds.length];
        for (int i = 0; i < zoneIds.length; i++) zoneRegion[i] = rIdx.get(geoData.getZones().get(zoneIds[i]).getRegion().getId());
        regionState = new int[regionIds.length]; regSchool = new double[regionIds.length]; regCrime = new double[regionIds.length];
        regGrowth = new double[regionIds.length]; regAdjacent = new boolean[regionIds.length][regionIds.length];
        readRegionAttributes(ReslocProperties.path("resloc.region.attributes", "input/resloc_region_attributes.csv"));
        if (respec) readAdjacency(ReslocProperties.path("resloc.region.adjacency", "input/resloc_region_adjacency_respec.csv"));
        if (respec) readZoneAttributes(ReslocProperties.path("resloc.respec.zone.attributes", "input/resloc_zone_attributes_respec.csv"));
        zoneState = new int[zoneIds.length];
        for (int i = 0; i < zoneIds.length; i++) zoneState[i] = regionState[zoneRegion[i]];
        pt = readSkim(ReslocProperties.path("resloc.transit.skim", "skims/transit_peak_time_d2d.csv.gz"));
        ivSample = Integer.parseInt(ReslocProperties.get("resloc.iv.dwelling.sample", "200"));
        readTenure(ReslocProperties.path("resloc.tenure.file", "input/tenure_by_age.csv"));
        logger.info("Estimated residential location model" + (respec ? " (re-specified, resloc.spec = respec)" : "") + ": " + cDw.size()
                + " dwelling, " + cZone.size() + " zone, " + cReg.size() + " region coefficients");
        if (respec && !cReg.containsKey("IV_A")) throw new RuntimeException("resloc.spec = respec: the county coefficient file must list IV_A (fixed at 1)");
    }

    private void readZoneAttributes(String file) {
        zoneAcres = new double[zoneIds.length]; zonePark = new double[zoneIds.length]; Arrays.fill(zoneAcres, Double.NaN);
        try (BufferedReader r = new BufferedReader(new FileReader(file))) {
            String[] h = r.readLine().split(",");
            int iZ = col(h, "zone"), iA = col(h, "acres"), iP = col(h, "park");
            String line;
            while ((line = r.readLine()) != null) {
                if (line.isBlank()) continue;
                String[] x = line.split(",");
                Integer z = zIdx.get(Integer.parseInt(x[iZ].trim()));
                if (z == null) continue;
                zoneAcres[z] = Double.parseDouble(x[iA].trim()); zonePark[z] = Double.parseDouble(x[iP].trim());
            }
        } catch (IOException e) {
            throw new RuntimeException("Could not read the respec zone attributes " + file, e);
        }
        for (int z = 0; z < zoneIds.length; z++) if (Double.isNaN(zoneAcres[z])) throw new RuntimeException("zone " + zoneIds[z] + " missing in " + file);
    }

    /** land use of every zone from the current dwelling counts (dd) and jobs */
    private void updateLandUse(double[] dd) {
        final int nz = zoneIds.length;
        final double[][] jobs = new double[nz][4];   // RET, OFF, IND, OTH
        for (Job j : dataContainer.getJobDataManager().getJobs()) {
            final Integer z = zIdx.get(j.getZoneId());
            if (z == null) continue;
            final String t = j.getType() == null ? "" : j.getType().replace("\"", "");
            jobs[z]["RET".equals(t) ? 0 : "OFF".equals(t) ? 1 : "IND".equals(t) ? 2 : 3]++;
        }
        landUse = new double[nz][5];
        for (int z = 0; z < nz; z++) {
            final double a = zoneAcres[z], ret = jobs[z][0], all = jobs[z][0] + jobs[z][1] + jobs[z][2] + jobs[z][3];
            final double[] n = {ret, jobs[z][1], jobs[z][2] + jobs[z][3], dd[z]};
            final double tot = n[0] + n[1] + n[2] + n[3];
            double e = 0;
            for (double x : n) if (x > 0) { final double p = x / tot; e -= p * Math.log(p); }
            landUse[z][0] = Math.log(Math.max(dd[z], 1) / a);
            landUse[z][1] = Math.log1p(all / a);
            landUse[z][2] = Math.log1p(ret / (a * 0.00404686));
            landUse[z][3] = e / Math.log(4);
            landUse[z][4] = zonePark[z];
        }
    }

    private void readAdjacency(String file) {
        int n = 0;
        try (BufferedReader r = new BufferedReader(new FileReader(file))) {
            String[] h = r.readLine().split(",");
            int iA = col(h, "region_a"), iB = col(h, "region_b");
            String line;
            while ((line = r.readLine()) != null) {
                if (line.isBlank()) continue;
                String[] x = line.split(",");
                Integer a = rIdx.get(Integer.parseInt(x[iA].trim())), b = rIdx.get(Integer.parseInt(x[iB].trim()));
                if (a == null || b == null || a.equals(b)) continue;
                regAdjacent[a][b] = true; regAdjacent[b][a] = true; n++;
            }
        } catch (IOException e) {
            throw new RuntimeException("Could not read the county adjacency file " + file, e);
        }
        logger.info("Residential location (respec): " + n + " county adjacency pairs read from " + file);
    }

    /** Baltimore 2026 (respec): accessibility of the zone part, file of the latest year <= year (pattern with {year}) */
    private void loadRespecAccessibility(int year) {
        if (accRespecPattern == null || accRespecPattern.isBlank()) return;
        int y = year;
        while (y >= 1990 && !new java.io.File(accRespecPattern.replace("{year}", String.valueOf(y))).exists()) y--;
        if (y < 1990) throw new RuntimeException("No respec accessibility file for year <= " + year + " (" + accRespecPattern + ")");
        if (y == accRespecYear) return;
        accRespec.clear();
        final String file = accRespecPattern.replace("{year}", String.valueOf(y));
        try (BufferedReader r = new BufferedReader(new FileReader(file))) {
            String[] h = r.readLine().split(",");
            int iz = col(h, "zone"), is = col(h, "segment"), ip = col(h, "purpose"), ia = col(h, "A");
            String line;
            while ((line = r.readLine()) != null) {
                if (line.isBlank()) continue;
                String[] x = line.split(",");
                Integer z = zIdx.get(Integer.parseInt(x[iz].trim()));
                if (z == null) continue;
                accRespec.computeIfAbsent(x[is].trim() + "|" + x[ip].trim(), k -> { double[] a = new double[zoneIds.length]; Arrays.fill(a, Double.NaN); return a; })[z]
                        = Double.parseDouble(x[ia].trim());
            }
        } catch (IOException e) {
            throw new RuntimeException("Could not read the respec accessibility file " + file, e);
        }
        accRespecYear = y;
        logger.info("Residential location (respec): zone-part accessibility of year " + y + " loaded from " + file);
    }

    /** accessibility of the zone part: the respec file when given, else the engine's logsum accessibility */
    private double acc(int z, String seg, String purpose) {
        if (!respec || accRespec.isEmpty()) return accessibility.getLogsum(zoneIds[z], seg, purpose);
        final double[] a = accRespec.get(seg + "|" + purpose);
        if (a == null) throw new RuntimeException("Segment/purpose " + seg + "/" + purpose + " not in the respec accessibility file");
        return a[z];
    }

    // ------------------------------------------------------------------------------------------------ input
    private void readCoefficients(String file, boolean lower) {
        try (BufferedReader r = new BufferedReader(new FileReader(file))) {
            String[] h = r.readLine().split(",");
            int iL = lower ? col(h, "level") : -1, iP = col(h, "parameter"), iE = col(h, "estimate");
            String line;
            while ((line = r.readLine()) != null) {
                if (line.isBlank()) continue;
                String[] x = line.split(",");
                double v = Double.parseDouble(x[iE].trim());
                if (!lower) cReg.put(x[iP].trim(), v);
                else if (x[iL].trim().equals("zone")) cZone.put(x[iP].trim(), v);
                else cDw.put(x[iP].trim(), v);
            }
        } catch (IOException e) {
            throw new RuntimeException("Could not read resloc coefficients " + file, e);
        }
    }

    private void readRegionAttributes(String file) {
        try (BufferedReader r = new BufferedReader(new FileReader(file))) {
            String[] h = r.readLine().split(",");
            int iR = col(h, "region"), iS = col(h, "state"), iSc = col(h, "school"), iC = col(h, "crime");
            int iG = -1;   // Baltimore 2026 (respec): school learning growth (optional column)
            for (int i = 0; i < h.length; i++) if (h[i].trim().equals("growth")) iG = i;
            if (respec && iG < 0) throw new RuntimeException("resloc.spec = respec needs the column growth in " + file);
            String line;
            while ((line = r.readLine()) != null) {
                if (line.isBlank()) continue;
                String[] x = line.split(",");
                Integer k = rIdx.get(Integer.parseInt(x[iR].trim()));
                if (k == null) continue;
                regionState[k] = Integer.parseInt(x[iS].trim()); regSchool[k] = Double.parseDouble(x[iSc].trim()); regCrime[k] = Double.parseDouble(x[iC].trim());
                if (iG >= 0) regGrowth[k] = Double.parseDouble(x[iG].trim());
            }
        } catch (IOException e) {
            throw new RuntimeException("Could not read resloc region attributes " + file, e);
        }
    }

    private void readTenure(String file) {
        if (!new java.io.File(file).exists()) { logger.warn("No tenure file " + file + ": base-year households start with 0 years in their dwelling"); return; }
        try (BufferedReader r = new BufferedReader(new FileReader(file))) {
            String[] h = r.readLine().split(",");
            int a0 = col(h, "age_from"), a1 = col(h, "age_to"), d0 = col(h, "dur_from"), d1 = col(h, "dur_to"), s = col(h, "share");
            String line;
            while ((line = r.readLine()) != null) {
                if (line.isBlank()) continue;
                String[] x = line.split(",");
                tenureRows.add(new double[]{Double.parseDouble(x[a0]), Double.parseDouble(x[a1]), Double.parseDouble(x[d0]), Double.parseDouble(x[d1]), Double.parseDouble(x[s])});
            }
        } catch (IOException e) {
            throw new RuntimeException("Could not read tenure file " + file, e);
        }
    }

    /** Baltimore 2026: every relocation (move, in-migration, new household) starts a new tenure */
    public static void recordMove(int householdId) {
        moveInYear.put(householdId, currentYear);
    }

    private int yearsInDwelling(Household hh) {
        Integer y = moveInYear.get(hh.getId());
        if (y == null) {
            int amax = 0;
            for (Person p : hh.getPersons().values()) amax = Math.max(amax, p.getAge());
            double u = tenureRandom.nextDouble(), cum = 0, tot = 0;
            for (double[] t : tenureRows) if (amax >= t[0] && amax <= t[1]) tot += t[4];
            int d = 0;
            for (double[] t : tenureRows) {
                if (amax < t[0] || amax > t[1]) continue;
                cum += t[4] / Math.max(tot, 1e-12);
                if (u <= cum) { d = (int) t[2] + tenureRandom.nextInt((int) (t[3] - t[2]) + 1); break; }
            }
            y = currentYear - d;
            moveInYear.put(hh.getId(), y);
        }
        return Math.max(0, currentYear - y);
    }

    private float[][] readSkim(String file) {
        float[][] m = new float[zoneIds.length][zoneIds.length];
        for (float[] row : m) Arrays.fill(row, 180f);
        try (BufferedReader r = new BufferedReader(new InputStreamReader(new GZIPInputStream(new FileInputStream(file))))) {
            r.readLine();
            String line;
            while ((line = r.readLine()) != null) {
                String[] x = line.split(",");
                Integer i = zIdx.get(Integer.parseInt(x[0])), j = zIdx.get(Integer.parseInt(x[1]));
                if (i == null || j == null) continue;
                double v = Double.parseDouble(x[2]);
                m[i][j] = (float) (v >= 999 ? 180 : Math.min(v, 180));
            }
        } catch (IOException e) {
            throw new RuntimeException("Could not read transit skim " + file, e);
        }
        return m;
    }

    private static int col(String[] h, String n) {
        for (int i = 0; i < h.length; i++) if (h[i].trim().equals(n)) return i;
        throw new RuntimeException("Column " + n + " missing");
    }

    // ------------------------------------------------------------------------------------------------ year preparation
    public void prepareYear() {
        final int nz = zoneIds.length, nr = regionIds.length;
        D = new double[nz][4];
        double[] costSum = new double[nz], dd = new double[nz], sv = new double[nz];
        for (Dwelling d : dataContainer.getRealEstateDataManager().getDwellings()) {
            Integer i = zIdx.get(d.getZoneId());
            if (i == null) continue;
            D[i][cellType(d.getType().toString())]++;
            costSum[i] += d.getPrice(); dd[i]++;
            sv[i] += StructuralVacancy.rate(regionIds[zoneRegion[i]], d.getType());   // 2026-11-17: by region when structural.vacancy.file is set
        }
        lnCostZ = new double[nz];
        for (int i = 0; i < nz; i++) lnCostZ[i] = Math.log(Math.max(dd[i] > 0 ? costSum[i] / dd[i] : 100, 100));
        double[] regDd = new double[nr];
        for (int i = 0; i < nz; i++) regDd[zoneRegion[i]] += dd[i];
        regN = regDd;
        if (vacancyAvailability) {
            final double[] regSv = new double[nr];
            for (int i = 0; i < nz; i++) regSv[zoneRegion[i]] += sv[i];
            for (int r = 0; r < nr; r++) regSv[r] = regDd[r] > 0 ? regSv[r] / regDd[r] : 0;
            regStructVac = regSv;
            int below = 0; double amin = 1;
            for (int r = 0; r < nr; r++) { final double x = availability(r); if (x < 1) below++; amin = Math.min(amin, x); }
            logger.info("Residential location: vacancy availability on (resloc.region.vacancy.availability); " + below + " of " + nr
                    + " regions below their structural vacancy at the start of " + currentYear + ", lowest availability " + String.format("%.3f", amin));
        }
        final IndexedDoubleMatrix2D car = dataContainer.getTravelTimes().getPeakSkim(TransportMode.car);
        tZoneRegion = new float[nz][nr]; tRegionZoneCar = new float[nr][nz]; tRegionZoneP = new float[nr][nz];
        for (int a = 0; a < nz; a++) {
            final int ra = zoneRegion[a];
            final double wa = regDd[ra] > 0 ? dd[a] / regDd[ra] : 0;
            for (int b = 0; b < nz; b++) {
                double t = car.getIndexed(zoneIds[a], zoneIds[b]);
                if (!(t >= 0) || t > 300) t = 300;
                // zone a -> region of b, weighted by the dwellings of b
                final int rb = zoneRegion[b];
                if (regDd[rb] > 0) tZoneRegion[a][rb] += (float) (t * dd[b] / regDd[rb]);
                // region of a -> zone b, weighted by the dwellings of a
                tRegionZoneCar[ra][b] += (float) (wa * t);
                tRegionZoneP[ra][b] += (float) (wa * pt[a][b]);
            }
        }
        ivDwellings = new ArrayList<>();
        for (int r = 0; r < nr; r++) {
            List<Dwelling> v = new ArrayList<>(dataContainer.getRealEstateDataManager().getListOfVacantDwellingsInRegion(regionIds[r]));
            Collections.shuffle(v, random);
            ivDwellings.add(new ArrayList<>(v.subList(0, Math.min(ivSample, v.size()))));
        }
        cacheIvA.clear(); cacheIvB.clear();
        if (respec) {
            // share of the zone's households in each income group (estimation: 2016 synthetic population, r01_income_similarity.py)
            final double[][] cnt = new double[nz][4];
            for (Household hh : dataContainer.getHouseholdDataManager().getHouseholds()) {
                final Dwelling d = dataContainer.getRealEstateDataManager().getDwelling(hh.getDwellingId());
                if (d == null) continue;
                final Integer i = zIdx.get(d.getZoneId());
                if (i == null) continue;
                cnt[i][groupIndex(hh)]++;
            }
            shareOwnGroup = new double[nz][4];
            for (int i = 0; i < nz; i++) {
                final double tot = cnt[i][0] + cnt[i][1] + cnt[i][2] + cnt[i][3];
                for (int g = 0; g < 4; g++) shareOwnGroup[i][g] = tot > 0 ? cnt[i][g] / tot : 0;
            }
            loadRespecAccessibility(currentYear);
            updateLandUse(dd);
            final String dump = System.getProperty("silo.resloc.respec.dump");
            if (dump != null && !dump.isBlank()) dumpZoneArrays(dump + "/resloc_respec_zones_" + currentYear + ".csv");
        }
        if (diagN > 0) logger.info(String.format("  Move-or-not (estimated) of the previous year: mean gap %.3f, mean gap - kappa gap0 %.3f, mean ln(1+years) %.3f, mean P %.4f over %d households",
                diagGap / diagN, diagGapEff / diagN, diagLnDur / diagN, diagP / diagN, diagN));
        diagGap = diagGapEff = diagLnDur = diagP = 0; diagN = 0;
        logger.info("Residential location model prepared for " + currentYear + ": " + (int) Arrays.stream(dd).sum() + " dwellings");
    }

    private static int groupIndex(Household hh) {
        final String n = hh.getHouseholdType().getIncomeCategory().name();
        for (int g = 0; g < INC_GROUPS.length; g++) if (INC_GROUPS[g].equals(n)) return g;
        throw new RuntimeException("income category " + n);
    }

    /** Baltimore 2026 (respec, -Dsilo.resloc.respec.dump=<dir>): zone arrays of the year for the verification */
    private void dumpZoneArrays(String file) {
        try (java.io.PrintWriter w = new java.io.PrintWriter(file)) {
            w.println("zone,D_SFD,D_SFA,D_MF,D_MH,lncost,sh_LOW,sh_MEDIUM,sh_HIGH,sh_VERY_HIGH,region,lnddens,lnjden,lnretden,mix,park");
            for (int i = 0; i < zoneIds.length; i++)
                w.println(zoneIds[i] + "," + D[i][0] + "," + D[i][1] + "," + D[i][2] + "," + D[i][3] + "," + lnCostZ[i] + "," + shareOwnGroup[i][0] + ","
                        + shareOwnGroup[i][1] + "," + shareOwnGroup[i][2] + "," + shareOwnGroup[i][3] + "," + regionIds[zoneRegion[i]]
                        + "," + landUse[i][0] + "," + landUse[i][1] + "," + landUse[i][2] + "," + landUse[i][3] + "," + landUse[i][4]);
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
        logger.info("Residential location (respec): zone arrays written to " + file);
    }

    private static int cellType(String t) {
        switch (t) {
            case "SFD": return 0;
            case "SFA": return 1;
            case "MF234": case "MF5plus": return 2;
            default: return 3;
        }
    }

    // ------------------------------------------------------------------------------------------------ household terms
    /** Baltimore 2026: household attribute naming the household the members of a household being formed come from */
    public static final String ORIGIN_HOUSEHOLD = "reslocOriginHousehold";

    private final class Hh {
        final Household hh; final double inc, lninc, size, need, child, age65, nocar; final String group, seg;
        final int zone, region, state; final List<Integer> jobZones = new ArrayList<>();
        ReslocRespecUtility.HhVars v;   // Baltimore 2026 (respec): household variables of the re-specified model
        int gi, ageMax;                 // income group index, age of the oldest member
        Hh(Household hh, double incomeOverride) {
            this.hh = hh;
            inc = Math.max(incomeOverride > 0 ? incomeOverride : HouseholdUtil.getAnnualHhIncome(hh), 5000);
            lninc = Math.log(inc / 50000.);
            size = hh.getHhSize();
            need = size <= 1 ? 1 : Math.min(size - 1, 4);
            int amax = 0; boolean ch = false;
            for (Person p : hh.getPersons().values()) { amax = Math.max(amax, p.getAge()); ch |= p.getAge() < 18; }
            child = ch ? 1 : 0; age65 = amax >= 65 ? 1 : 0;
            group = hh.getHouseholdType().getIncomeCategory().name();
            seg = accessibility.segmentOf(hh);
            Dwelling cur = dataContainer.getRealEstateDataManager().getDwelling(hh.getDwellingId());
            // Baltimore 2026 (2026-10-26, jobchoice/DIAGNOSIS.md): a household being formed (leaving the parental home, divorce,
            // marriage into a new household) has no dwelling and no car yet; it was placed as if it came from nowhere (no
            // distance, same-region or same-state term) and without a car (commute on transit times): its workers kept their jobs
            // and their car commute rose from 32-48 to 86-87 min, 42 % of them working in Maryland against 70-80 % before. Such a
            // household now searches from the dwelling of the household its members come from and with that household's cars.
            Household origin = null;
            if (cur == null) {
                final Object od = hh.getAttribute(ORIGIN_HOUSEHOLD).orElse(null);
                if (od instanceof Household) origin = (Household) od;
                if (origin == null) {
                    for (Person p : hh.getPersons().values()) {
                        final Household ph = p.getHousehold();
                        if (ph != null && ph != hh && ph.getDwellingId() > 0) { origin = ph; break; }
                    }
                }
                if (origin != null) cur = dataContainer.getRealEstateDataManager().getDwelling(origin.getDwellingId());
            }
            nocar = (hh.getAutos() > 0 || (hh.getDwellingId() <= 0 && origin != null && origin.getAutos() > 0)) ? 0 : 1;
            Integer zi = cur == null ? null : zIdx.get(cur.getZoneId());
            zone = zi == null ? -1 : zi; region = zone < 0 ? -1 : zoneRegion[zone]; state = zone < 0 ? -1 : zoneState[zone];
            for (Person p : hh.getPersons().values()) {
                if (p.getOccupation() == Occupation.EMPLOYED && p.getJobId() > 0) {
                    Job j = dataContainer.getJobDataManager().getJobFromId(p.getJobId());
                    if (j == null) continue;
                    Integer k = zIdx.get(j.getZoneId());
                    if (k != null) jobZones.add(k);
                }
            }
            ageMax = amax;
            gi = groupIndex(hh);
            v = new ReslocRespecUtility.HhVars(inc, (int) size, ch, amax, nocar > 0);
        }
    }

    private static double c(Map<String, Double> m, String name, String group) {
        Double v = m.get(name + "_" + group);
        return v != null ? v : m.getOrDefault(name, 0.);
    }

    // ------------------------------------------------------------------------------------------------ level 3: dwelling
    private double vDwelling(Hh h, int cost, int bedrooms, String type, int yearBuilt) {
        if (respec) return ReslocRespecUtility.dwelling(cDw, h.v, cost, bedrooms, type, (currentYear - yearBuilt) <= 5);
        final double b = Math.min(12. * cost / h.inc, 3.);
        double v = c(cDw, "bur_lo", h.group) * Math.min(b, .3) + c(cDw, "bur_mid", h.group) * Math.min(Math.max(b - .3, 0), .2)
                + c(cDw, "bur_hi", h.group) * Math.max(b - .5, 0) + c(cDw, "lncost", h.group) * Math.log(Math.max(cost, 100))
                + c(cDw, "bed_short", h.group) * Math.max(0, h.need - bedrooms) + c(cDw, "bed_extra", h.group) * Math.max(0, bedrooms - h.need)
                + c(cDw, "new5", h.group) * ((currentYear - yearBuilt) <= 5 ? 1 : 0);
        for (String t : DW_TYPES) {
            if (t.equals(type)) {
                v += c(cDw, t, h.group) + c(cDw, t + "_x_size", h.group) * (h.size - 1) + c(cDw, t + "_x_child", h.group) * h.child
                        + c(cDw, t + "_x_age65", h.group) * h.age65 + c(cDw, t + "_x_lninc", h.group) * h.lninc;
            }
        }
        return v;
    }

    // ------------------------------------------------------------------------------------------------ level 2: zone x type cell
    private double vCellNoCommute(Hh h, int z, int t) {
        if (respec) return ReslocRespecUtility.cell(cZone, h.v, Math.log(D[z][t]), acc(z, h.seg, "work"), acc(z, h.seg, "nonwork"), lnCostZ[z], shareOwnGroup[z][h.gi], landUse[z]);
        final double aw = accessibility.getLogsum(zoneIds[z], h.seg, "work"), an = accessibility.getLogsum(zoneIds[z], h.seg, "nonwork");
        return cZone.getOrDefault("lnD", 1.) * Math.log(D[z][t]) + cZone.getOrDefault("accW", 0.) * aw + cZone.getOrDefault("accN", 0.) * an
                + cZone.getOrDefault("accN_x_child", 0.) * an * h.child + cZone.getOrDefault("accN_x_age65", 0.) * an * h.age65
                + cZone.getOrDefault("accW_x_nocar", 0.) * aw * h.nocar
                + cZone.getOrDefault("lncost", 0.) * lnCostZ[z] + cZone.getOrDefault("lncost_x_inc", 0.) * lnCostZ[z] * h.lninc;
    }

    private double zoneCommute(Hh h, int z) {
        double s = 0;
        for (int j : h.jobZones) {
            double t = h.nocar > 0 ? pt[z][j] : dataContainer.getTravelTimes().getPeakSkim(TransportMode.car).getIndexed(zoneIds[z], zoneIds[j]);
            s += Math.log1p(Math.max(0, Math.min(t, 300)));
        }
        if (respec) return ReslocRespecUtility.commute(cZone, h.v, s);
        return cZone.getOrDefault("commute_log", 0.) * s + cZone.getOrDefault("commute_log_x_inc", 0.) * s * h.lninc;
    }

    /**
     * Baltimore 2026: V_A + V_B - ln D_zt of the dwelling for the household (dwelling and zone levels with the commute from the
     * dwelling's zone; the log of the dwelling choice weight). The better-dwelling rule compares the found and the current dwelling
     * with it: the region-level moving costs (same region, same state, distance) already entered the region draw.
     */
    public double dwellingLevelUtility(Household household, Dwelling dd) {
        Hh h = new Hh(household, -1);
        Integer z = dd == null ? null : zIdx.get(dd.getZoneId());
        if (z == null) return Double.NEGATIVE_INFINITY;
        int t = cellType(dd.getType().toString());
        double lnD = Math.log(Math.max(D[z][t], 1));
        double vb = D[z][t] > 0 ? vCellNoCommute(h, z, t) : cZone.getOrDefault("lnD", 1.) * lnD + vCellNoCommute0(h, z);
        return vDwelling(h, dd.getPrice(), dd.getBedrooms(), dd.getType().toString(), dd.getYearBuilt()) + vb + zoneCommute(h, z) - lnD;
    }

    /** weight of a sampled vacant dwelling in the dwelling choice (exp of V_A + V_B - ln D_zt) */
    public double dwellingWeight(Household household, Dwelling dd) {
        Hh h = new Hh(household, -1);
        Integer z = zIdx.get(dd.getZoneId());
        if (z == null) return 0;
        int t = cellType(dd.getType().toString());
        if (D[z][t] <= 0) return 0;
        double v = vDwelling(h, dd.getPrice(), dd.getBedrooms(), dd.getType().toString(), dd.getYearBuilt())
                + vCellNoCommute(h, z, t) + zoneCommute(h, z) - Math.log(D[z][t]);
        return Math.exp(Math.max(-700, Math.min(700, v)));
    }

    // ------------------------------------------------------------------------------------------------ inclusive values
    private static double incBin(double inc) {
        double b = Math.floor(Math.min(Math.max(inc, 5000), 400000) / 2500.);
        return b * 2500 + 1250;
    }

    private double[] ivB(Household household, Hh h0) {
        final double ib = incBin(h0.inc);
        final String key = h0.seg + "|" + h0.child + "|" + h0.age65 + "|" + ib + (respec ? "|" + h0.v.ageBand() + "|" + h0.v.hhs5 + "|" + h0.v.nocar : "");
        if (respec) return cacheIvB.computeIfAbsent(key, k -> {
            Hh h = new Hh(household, ib);
            final int nz = zoneIds.length;
            final double[] aw = new double[nz], an = new double[nz], sim = new double[nz];
            for (int z = 0; z < nz; z++) { aw[z] = acc(z, h.seg, "work"); an[z] = acc(z, h.seg, "nonwork"); sim[z] = shareOwnGroup[z][h.gi]; }
            return ReslocRespecUtility.ivB(cZone, h.v, D, lnCostZ, aw, an, sim, landUse, zoneRegion, regionIds.length);
        });
        return cacheIvB.computeIfAbsent(key, k -> {
            Hh h = new Hh(household, ib);
            double[] s = new double[regionIds.length], mx = new double[regionIds.length];
            Arrays.fill(mx, Double.NEGATIVE_INFINITY);
            double[] v = new double[zoneIds.length * 4];
            for (int z = 0; z < zoneIds.length; z++) for (int t = 0; t < 4; t++) {
                v[z * 4 + t] = D[z][t] > 0 ? vCellNoCommute(h, z, t) : Double.NEGATIVE_INFINITY;
                mx[zoneRegion[z]] = Math.max(mx[zoneRegion[z]], v[z * 4 + t]);
            }
            for (int z = 0; z < zoneIds.length; z++) for (int t = 0; t < 4; t++)
                if (D[z][t] > 0) s[zoneRegion[z]] += Math.exp(v[z * 4 + t] - mx[zoneRegion[z]]);
            double[] out = new double[regionIds.length];
            for (int r = 0; r < out.length; r++) out[r] = s[r] > 0 ? Math.log(s[r]) + mx[r] : Double.NEGATIVE_INFINITY;
            return out;
        });
    }

    private double[] ivA(Household household, Hh h0) {
        final double ib = incBin(h0.inc);
        final String key = h0.group + "|" + ib + "|" + Math.min(h0.size, 10) + "|" + h0.child + "|" + h0.age65 + (respec ? "|" + h0.v.ageBand() : "");
        return cacheIvA.computeIfAbsent(key, k -> {
            Hh h = new Hh(household, ib);
            double[] out = new double[regionIds.length];
            for (int r = 0; r < out.length; r++) {
                List<Dwelling> l = ivDwellings.get(r);
                if (l.isEmpty()) { out[r] = 0; continue; }
                double[] v = new double[l.size()]; double m = Double.NEGATIVE_INFINITY;
                for (int i = 0; i < v.length; i++) {
                    Dwelling d = l.get(i);
                    v[i] = vDwelling(h, d.getPrice(), d.getBedrooms(), d.getType().toString(), d.getYearBuilt());
                    m = Math.max(m, v[i]);
                }
                double s = 0; for (double x : v) s += Math.exp(x - m);
                out[r] = Math.log(s / v.length) + m;
            }
            return out;
        });
    }

    // ------------------------------------------------------------------------------------------------ level 1: region
    /** region terms of U_r without the inclusive values; com = sum over the workers of ln(1 + commute time) */
    private double regionTerms(Hh h, int r, double com) {
        final boolean same = r == h.region;
        double t = (same || h.zone < 0) ? 0 : tZoneRegion[h.zone][r];
        if (respec) {
            final boolean adj = !same && h.region >= 0 && regAdjacent[h.region][r];
            return ReslocRespecUtility.countyTerms(cReg, h.v, t, same ? 1 : 0, adj ? 1 : 0, h.state == regionState[r] ? 1 : 0, com, regGrowth[r], regCrime[r])
                    + cReg.getOrDefault("asc_" + regionIds[r], 0.);
        }
        return c(cReg, "d1", h.group) * Math.min(t, 20) + c(cReg, "d2", h.group) * Math.min(Math.max(t - 20, 0), 40) + c(cReg, "d3", h.group) * Math.max(t - 60, 0)
                + c(cReg, "same_region", h.group) * (same ? 1 : 0) + c(cReg, "same_state", h.group) * (h.state == regionState[r] ? 1 : 0)
                + c(cReg, "commute_log", h.group) * com + c(cReg, "commute_log_x_inc", h.group) * com * h.lninc
                + c(cReg, "school", h.group) * regSchool[r] + c(cReg, "school_x_child", h.group) * regSchool[r] * h.child
                + c(cReg, "crime", h.group) * regCrime[r] + c(cReg, "crime_x_child", h.group) * regCrime[r] * h.child
                + cReg.getOrDefault("asc_" + regionIds[r], 0.);
    }

    private double regionCommute(Hh h, int r) {
        double com = 0;
        for (int j : h.jobZones) com += Math.log1p(h.nocar > 0 ? tRegionZoneP[r][j] : tRegionZoneCar[r][j]);
        return com;
    }

    /** systematic utility of every region (index order of regionIds) for the household */
    public double[] regionUtilities(Household household) {
        return regionUtilities(new Hh(household, -1), household);
    }

    private double[] regionUtilities(Hh h, Household household) {
        double[] b = ivB(household, h), a = ivA(household, h);
        double[] u = new double[regionIds.length];
        for (int r = 0; r < u.length; r++) {
            u[r] = c(cReg, "IV_B", h.group) * b[r] + c(cReg, "IV_A", h.group) * a[r] + regionTerms(h, r, regionCommute(h, r));
            if (Double.isInfinite(b[r]) || Double.isNaN(u[r])) u[r] = Double.NEGATIVE_INFINITY;
        }
        return u;
    }

    /** Baltimore 2026: utility of dwelling dd for the household on the region scale, u(d) = X_r + lam_B (V_B - ln D_zt) + lam_A V_A */
    public double dwellingUtility(Household household, Dwelling dd) {
        return dwellingUtility(new Hh(household, -1), dd);
    }

    private double dwellingUtility(Hh h, Dwelling dd) {
        Integer zi = dd == null ? null : zIdx.get(dd.getZoneId());
        if (zi == null) return Double.NEGATIVE_INFINITY;
        final int z = zi, t = cellType(dd.getType().toString()), r = zoneRegion[z];
        final double lnD = Math.log(Math.max(D[z][t], 1));
        double com = 0;
        for (int j : h.jobZones) {
            double tt = h.nocar > 0 ? pt[z][j] : dataContainer.getTravelTimes().getPeakSkim(TransportMode.car).getIndexed(zoneIds[z], zoneIds[j]);
            com += Math.log1p(Math.max(0, Math.min(tt, 300)));
        }
        final double vb = (D[z][t] > 0 ? vCellNoCommute(h, z, t) : cZone.getOrDefault("lnD", 1.) * lnD + vCellNoCommute0(h, z)) - lnD;
        final double va = vDwelling(h, dd.getPrice(), dd.getBedrooms(), dd.getType().toString(), dd.getYearBuilt());
        return regionTerms(h, r, com) + c(cReg, "IV_B", h.group) * vb + c(cReg, "IV_A", h.group) * va;
    }

    /** cell utility without the size term (for a dwelling whose cell is empty in the stock counts) */
    private double vCellNoCommute0(Hh h, int z) {
        if (respec) return ReslocRespecUtility.cell(cZone, h.v, 0, acc(z, h.seg, "work"), acc(z, h.seg, "nonwork"), lnCostZ[z], shareOwnGroup[z][h.gi], landUse[z]);
        final double aw = accessibility.getLogsum(zoneIds[z], h.seg, "work"), an = accessibility.getLogsum(zoneIds[z], h.seg, "nonwork");
        return cZone.getOrDefault("accW", 0.) * aw + cZone.getOrDefault("accN", 0.) * an
                + cZone.getOrDefault("accN_x_child", 0.) * an * h.child + cZone.getOrDefault("accN_x_age65", 0.) * an * h.age65
                + cZone.getOrDefault("accW_x_nocar", 0.) * aw * h.nocar
                + cZone.getOrDefault("lncost", 0.) * lnCostZ[z] + cZone.getOrDefault("lncost_x_inc", 0.) * lnCostZ[z] * h.lninc;
    }

    /** Baltimore 2026: probability that the household searches for another dwelling this year (see the class comment) */
    public double moveProbability(Household household, Dwelling current, double shift) {
        final Hh h = new Hh(household, -1);
        final double[] u = regionUtilities(h, household);
        final double lamB = c(cReg, "IV_B", h.group);
        double m = Double.NEGATIVE_INFINITY;
        final boolean[] ok = new boolean[u.length];
        for (int r = 0; r < u.length; r++) {
            ok[r] = !Double.isInfinite(u[r]) && regN[r] > 0 && dataContainer.getRealEstateDataManager().getNumberOfVacantDDinRegion(regionIds[r]) > 0;
            if (ok[r]) m = Math.max(m, u[r]);
        }
        if (Double.isInfinite(m)) return 0;
        double s = 0, e = 0;
        for (int r = 0; r < u.length; r++) {
            if (!ok[r]) continue;
            final double w = Math.exp(u[r] - m) * availability(r);   // 2026-11-14: x a_r (= 1 when resloc.region.vacancy.availability is off)
            s += w; e += w * (u[r] + lamB * (lnSearch - Math.log(regN[r])));
        }
        if (!(s > 0)) return 0;
        final double emu = e / s;
        final double uc = dwellingUtility(h, current);
        if (Double.isInfinite(uc)) return 1;
        final int years = yearsInDwelling(household);
        final double gap = emu - uc;
        final int start = currentYear - years;
        double[] g0 = gapAtEntry.get(household.getId());
        if (g0 == null || g0[0] != start) { g0 = new double[]{start, gap}; gapAtEntry.put(household.getId(), g0); }
        final double gapEff = gap - moveReference * g0[1];
        final double x = moveScale * gapEff + moveDuration * Math.log1p(years);
        final double p = 1 - 1 / (1 + shift * Math.exp(Math.max(-700, Math.min(700, x))));
        diagGap += gap; diagGapEff += gapEff; diagLnDur += Math.log1p(years); diagP += p; diagN++;
        return p;
    }

    /** Baltimore 2026 (2026-11-14): availability a_r of region index r in the search (see vacancyAvailability); 1 when the switch is off */
    public double availability(int r) {
        if (!vacancyAvailability || regN == null || regStructVac == null || regN[r] <= 0 || regStructVac[r] <= 0) return 1.0;
        final double v = dataContainer.getRealEstateDataManager().getNumberOfVacantDDinRegion(regionIds[r]) / regN[r];
        return Math.min(1.0, v / regStructVac[r]);
    }

    public int regionIndex(Region region) {
        return rIdx.get(region.getId());
    }
}
