package de.tum.bgu.msm.models.resloc;

import de.tum.bgu.msm.container.DataContainer;
import de.tum.bgu.msm.data.Region;
import de.tum.bgu.msm.data.dwelling.Dwelling;
import de.tum.bgu.msm.data.dwelling.DwellingMstm;
import de.tum.bgu.msm.data.household.Household;
import de.tum.bgu.msm.data.household.HouseholdMstm;
import de.tum.bgu.msm.data.household.HouseholdUtil;
import de.tum.bgu.msm.data.job.Job;
import de.tum.bgu.msm.data.person.Occupation;
import de.tum.bgu.msm.data.person.Person;
import de.tum.bgu.msm.data.person.Race;
import de.tum.bgu.msm.models.relocation.moves.HousingStrategy;
import de.tum.bgu.msm.util.matrices.IndexedDoubleMatrix2D;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.matsim.api.core.v01.TransportMode;

import java.io.*;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.zip.GZIPInputStream;

/**
 * Baltimore 2026 (2026-11-18, resloc.twolevel = true; default false = the models of record unchanged): the two-level residential
 * location model estimated on ACS PUMS 2014-2018 movers (side_experiments/respec_2026-11/step_by_step/residential/r17_final.py with
 * the functions of r14_puma_two_level.py; coefficients r17_coef.csv -> input/resloc_*_coef_1118.csv by r18_export_silo.py).
 *
 * Level 2, dwelling d within the PUMA (18 terms), ln income x = ln(max(income, 5000) / 50000) (2016 $):
 *   V_d = (b + b' x) over30 + (b + b' x) ln max(cost, 100) + (b + b' x) max(0, need - bedrooms) + (b + b' x) max(0, bedrooms - need)
 *         + (b + b' x) built in the last 5 years + sum_type (b + b' x) [SFA, MF234, MF5plus, MH; SFD reference]
 *   over30 = max(min(12 cost / income, 3) - 0.3, 0), need = min(household size, 5).
 * Level 1, PUMA p (97 PUMAs of 2010), inclusive value coefficient 1:
 *   U_p = IV_p + b_lnM ln M_p + b_d2 clip(Tx - 20, 0, 40) + b_d3 max(Tx - 60, 0) + b_same same + b_adj adjacent + b_ss same state
 *         + b_com sum_workers ln(1 + t) + b_cc crime_p x children + b_dens lnddens_p + b_race own-race share of the PUMA's households
 *   IV_p = ln mean over (up to) 200 vacant dwellings of p sampled at the start of the year of exp(V_d) (estimation: 200 market
 *          dwellings of the PUMS pool); M_p = resloc.marketsize: vacancies (default) | stock | movers_prev_year (2026-11-18k).
 *   Geography exactly as r14.geography / upper_data, with SILO's current dwellings, jobs and households in place of 2016:
 *     PUMA attributes are means over the PUMA's zones with weights Wn_zp = w_attr_zp dd_z / sum (resloc_puma_zone_1118.csv), the
 *     origin is the migration PUMA (MIGPUMA) of the current home, O_mz = dd_z / sum over the MIGPUMA's zones; workplaces are the
 *     MIGPUMA (POWPUMA geography) of the workers' job zones, weights Pw_wz = jobs_z / sum;
 *     T_mp = sum_z O_mz sum_z' car_zz' Wn_z'p, same_mp = sum_z O_mz [Wn_zp > 0], Tx = T (1 - same),
 *     adjacent_mp = sum_z O_mz ADJ(first PUMA of z, p) (1 - same), same state = state of the MIGPUMA = state of p,
 *     commute = sum over workers of ln(1 + sum_z' (sum_z Wn_zp t_zz') Pw_wz'), t = car peak time, or the transit door-to-door time
 *     (missing 180, capped at 180) for a household without a car (missing car times 300);
 *     crime_p = sum_z Wn_zp crime_z (county crime index, fixed); lnddens_p = sum_z Wn_zp ln(max(dd_z, 1) / acres_z);
 *     own race: S_pr = sum_z Wn_zp n_zr / sum_r (...), n_zr = households of race r in zone z (HouseholdMstm.getRace(): white,
 *     black, hispanic, other), recomputed every year; race of a household = its householder's (2026-11-18k: base year the
 *     household file's race column, later households the oldest non-child member; raceIndex).
 *   A PUMA is available if it has dwellings and a vacant dwelling (and an inclusive value).
 * Search: the PUMA is drawn with P_p = exp(U_p) / sum, then 30 vacant dwellings of the PUMA uniformly (J = 30 as in the estimation),
 *   and one of them with exp(V_d) (income-restricted dwellings for which the household is not eligible get weight 0).
 *   In-migrants placed inside a target region (InOutMigrationImpl regional control) choose among the PUMAs with vacancies in the
 *   region (M = the region's vacancies in the PUMA), with no origin (same / bordering / same state / car time 0) and no commute
 *   (their persons still carry the job ids of the households they were copied from).
 * Move-or-not (structure of ReslocModel.moveProbability, the location utility replaced): utility of a dwelling d of PUMA p on the
 *   scale of the model, u(d) = U_p - IV_p + V_d - ln(vacancies of p) (2026-11-18k); 2026-11-19a: - ln M_p (the scale implied by the model, M as
 *   resloc.marketsize) in place of - ln vacancies; availability = live vacancies of the PUMA > 0, counted exactly (the probability of choosing d is exp(u(d)) / sum_p exp(U_p)); expected
 *   maximum utility EMU = ln sum_p exp(U_p) (the logsum of the two-level model); gap = EMU - u(current), gap0 = gap at the start of
 *   the tenure, P(search) = 1 - 1 / (1 + shift exp(scale (gap - kappa gap0) + gamma ln(1 + years in the dwelling))), with the
 *   properties of ReslocModel (move.or.not.binomial.log.shift.parameter, resloc.move.scale / reference / duration, resloc.tenure.file).
 *   Better-dwelling rule (HousingStrategyMstm.acceptsMove): u(d) without the origin terms (car time, same, bordering, same state).
 * Inclusive values are cached by (income on a 0.5 % log grid, bedrooms needed); the dwelling choice and the current dwelling use the
 * exact income. The verification main() evaluates the same functions on records exported from the estimation (r18_export_silo.py).
 */
public class ReslocTwoLevel {

    private static final Logger logger = LogManager.getLogger(ReslocTwoLevel.class);
    public static final String[] DW_VARS = {"over30", "over30_x_lninc", "lncost", "lncost_x_lninc", "bed_short", "bed_short_x_lninc",
            "bed_extra", "bed_extra_x_lninc", "new5", "new5_x_lninc", "SFA", "SFA_x_lninc", "MF234", "MF234_x_lninc", "MF5plus",
            "MF5plus_x_lninc", "MH", "MH_x_lninc"};
    public static final String[] PUMA_VARS = {"lnM", "d2", "d3", "same", "adjacent", "same_state", "commute_log", "crime_x_child", "lnddens", "own_race"};
    private static final String[] TYPES = {"SFA", "MF234", "MF5plus", "MH"};
    /** 2026-11-19g (r22_final.py): optional PUMA terms (0 when absent from the coefficient file): ln density x single-person household,
     *  x oldest member under 35, x ln(max(income, 5000) / 50000); core-city share = share of the PUMA's dwellings (Wn) in zones of
     *  DC 11001 or Baltimore City 24510 */
    public static final String[] PUMA_EXTRA = {"lnddens_x_single", "lnddens_x_young35", "core_share", "lnddens_x_lninc"};   // names of resloc_puma_coef_1119g.csv
    public static final int[] CORE_COUNTIES = {11001, 24510};
    public static final String[] RACES = {"white", "black", "hispanic", "other"};

    public static boolean enabled() {
        return Boolean.parseBoolean(ReslocProperties.get("resloc.twolevel", "false"));
    }

    // ============================================================================================ pure functions (shared with main)
    /** coefficients in the order of names; a name missing in the file is an error (IVd: default 1) */
    /** the optional terms in the order of names (0 when missing) */
    public static double[] readCoefOptional(String file, String[] names) {
        final Map<String, Double> m = new HashMap<>();
        for (String[] x : csv(file)) if (!x[0].equals("variable")) m.put(x[0].trim(), Double.parseDouble(x[1].trim()));
        final double[] b = new double[names.length];
        for (int i = 0; i < names.length; i++) b[i] = m.getOrDefault(names[i], 0.);
        return b;
    }

    public static double[] readCoef(String file, String[] names) {
        final Map<String, Double> m = new HashMap<>();
        for (String[] x : csv(file)) if (!x[0].equals("variable")) m.put(x[0].trim(), Double.parseDouble(x[1].trim()));
        final double[] b = new double[names.length];
        for (int i = 0; i < names.length; i++) {
            final Double v = m.get(names[i]);
            if (v == null) throw new RuntimeException("coefficient " + names[i] + " missing in " + file);
            b[i] = v;
        }
        if (m.containsKey("IVd") && Math.abs(m.get("IVd") - 1.0) > 1e-12) throw new RuntimeException("IVd must be 1 (inclusive value held at 1) in " + file);
        return b;
    }

    /** V_d of the dwelling level (r17_final.dw_final) */
    public static double dwellingUtility(double[] b, double income, int size, double cost, int bedrooms, String type, boolean new5) {
        final double inc = Math.max(income, 5000.), x = Math.log(inc / 50000.), need = Math.min(size, 5.);
        final double o = Math.max(Math.min(12. * cost / inc, 3.) - .3, 0.), lc = Math.log(Math.max(cost, 100.));
        final double bs = Math.max(0., need - bedrooms), be = Math.max(0., bedrooms - need), n5 = new5 ? 1. : 0.;
        double v = (b[0] + b[1] * x) * o + (b[2] + b[3] * x) * lc + (b[4] + b[5] * x) * bs + (b[6] + b[7] * x) * be + (b[8] + b[9] * x) * n5;
        for (int t = 0; t < TYPES.length; t++) if (TYPES[t].equals(type)) v += b[10 + 2 * t] + b[11 + 2 * t] * x;
        return v;
    }

    /** household variables of the PUMA level */
    public static final class HhVars {
        public double income; public int size; public boolean child, nocar; public int race;
        public boolean single, young;        // 2026-11-19g: one person; oldest member under 35
        public int originMig = -1;           // index of the MIGPUMA of the previous home, -1 = none (in-migrant)
        public int[] workMigs = new int[0];  // MIGPUMA index of each worker's job
    }

    /**
     * Geography of the PUMA level (r14.geography / upper_data), prepared from zone-level arrays: dwellings, jobs, households by race
     * (zone index order of zoneIds) and the car / transit skims (zone index x zone index, minutes, NaN = no value).
     */
    public static final class Geo {
        public final int[] zoneIds; final Map<Integer, Integer> zIdx = new HashMap<>();
        public final int[] pumaIds; final Map<Integer, Integer> pIdx = new HashMap<>();
        public final int[] migIds; final Map<Integer, Integer> mIdx = new HashMap<>();
        final int[][] zP; final double[][] zF, zW;    // zone -> PUMA entries: index, member share, attribute weight
        final int[] zoneMig;                          // MIGPUMA of a home / job in the zone
        final int[][] migZones;                       // zones with origin / workplace weight in the MIGPUMA
        final boolean[][] adj; final double[] crime, acres; final int[] pumaState, migState;
        final boolean[] excluded;                     // verification only: PUMAs without weight in the estimation (NaN weights there)
        final boolean emulateNaN;
        final double[] coreZ;                         // 2026-11-19g: zone in a core-city county (setZoneCounties)
        public double[] coreP;
        // prepared
        public double[] dw, crimeP, lnddP; public double[][] raceSh, T, same, adjacent, comCar, comPt;
        double[][] wn;                                // per zone entry: normalised weight Wn_zp

        public Geo(String pumaZone, String migZone, String zoneAttr, String adjacency, int[] excludedPumas) {
            final List<String[]> pz = csv(pumaZone), mz = csv(migZone), za = csv(zoneAttr), ad = csv(adjacency);
            final TreeSet<Integer> zs = new TreeSet<>(), ps = new TreeSet<>(), ms = new TreeSet<>();
            for (String[] x : skipHeader(pz)) { zs.add(Integer.parseInt(x[0])); ps.add(Integer.parseInt(x[1])); }
            for (String[] x : skipHeader(mz)) ms.add(Integer.parseInt(x[0]));
            zoneIds = zs.stream().mapToInt(Integer::intValue).toArray(); pumaIds = ps.stream().mapToInt(Integer::intValue).toArray();
            migIds = ms.stream().mapToInt(Integer::intValue).toArray();
            for (int i = 0; i < zoneIds.length; i++) zIdx.put(zoneIds[i], i);
            for (int i = 0; i < pumaIds.length; i++) pIdx.put(pumaIds[i], i);
            for (int i = 0; i < migIds.length; i++) mIdx.put(migIds[i], i);
            final int nz = zoneIds.length, np = pumaIds.length, nm = migIds.length;
            final List<List<double[]>> e = new ArrayList<>();
            for (int z = 0; z < nz; z++) e.add(new ArrayList<>());
            for (String[] x : skipHeader(pz)) e.get(zIdx.get(Integer.parseInt(x[0]))).add(new double[]{pIdx.get(Integer.parseInt(x[1])), Double.parseDouble(x[2]), Double.parseDouble(x[3])});
            zP = new int[nz][]; zF = new double[nz][]; zW = new double[nz][];
            for (int z = 0; z < nz; z++) {
                final List<double[]> l = e.get(z); l.sort(Comparator.comparingDouble(a -> a[0]));
                zP[z] = new int[l.size()]; zF[z] = new double[l.size()]; zW[z] = new double[l.size()];
                for (int k = 0; k < l.size(); k++) { zP[z][k] = (int) l.get(k)[0]; zF[z][k] = l.get(k)[1]; zW[z][k] = l.get(k)[2]; }
            }
            zoneMig = new int[nz]; Arrays.fill(zoneMig, -1);
            final List<List<Integer>> mzl = new ArrayList<>();
            for (int m = 0; m < nm; m++) mzl.add(new ArrayList<>());
            for (String[] x : skipHeader(mz)) {
                final int m = mIdx.get(Integer.parseInt(x[0])); final Integer z = zIdx.get(Integer.parseInt(x[1]));
                if (z == null) continue;
                if (Integer.parseInt(x[2]) == 1) mzl.get(m).add(z);
                if (Integer.parseInt(x[3]) == 1) zoneMig[z] = m;
            }
            migZones = new int[nm][];
            for (int m = 0; m < nm; m++) { final List<Integer> l = mzl.get(m); Collections.sort(l); migZones[m] = l.stream().mapToInt(Integer::intValue).toArray(); }
            crime = new double[nz]; acres = new double[nz]; Arrays.fill(acres, Double.NaN);
            for (String[] x : skipHeader(za)) {
                final Integer z = zIdx.get(Integer.parseInt(x[0]));
                if (z != null) { crime[z] = Double.parseDouble(x[1]); acres[z] = Double.parseDouble(x[2]); }
            }
            adj = new boolean[np][np];
            for (String[] x : skipHeader(ad)) adj[pIdx.get(Integer.parseInt(x[0]))][pIdx.get(Integer.parseInt(x[1]))] = true;
            pumaState = new int[np]; for (int p = 0; p < np; p++) pumaState[p] = pumaIds[p] / 100000;
            migState = new int[nm]; for (int m = 0; m < nm; m++) migState[m] = migIds[m] / 100000;
            excluded = new boolean[np];
            if (excludedPumas != null) for (int q : excludedPumas) excluded[pIdx.get(q)] = true;
            emulateNaN = excludedPumas != null && excludedPumas.length > 0;
            coreZ = new double[zoneIds.length];
            for (int z = 0; z < nz; z++) {
                if (zP[z].length == 0) throw new RuntimeException("zone " + zoneIds[z] + " without PUMA in " + pumaZone);
                double fs = 0; for (double f : zF[z]) fs += f;
                if (Math.abs(fs - 1) > 1e-6) throw new RuntimeException("zone " + zoneIds[z] + ": PUMA member shares sum to " + fs + " in " + pumaZone);
                if (zoneMig[z] < 0) throw new RuntimeException("zone " + zoneIds[z] + " without MIGPUMA in " + migZone);
                if (Double.isNaN(acres[z])) throw new RuntimeException("zone " + zoneIds[z] + " missing in " + zoneAttr);
            }
        }

        /** 2026-11-19g: core flag (0/1) of every zone (resloc_zone_core_1119g.csv or zone_inputs column core) */
        public void setZoneCore(Map<Integer, Double> core) {
            int n = 0;
            for (int z = 0; z < zoneIds.length; z++) {
                final Double c = core.get(zoneIds[z]);
                if (c == null) throw new RuntimeException("zone " + zoneIds[z] + " without core flag");
                coreZ[z] = c; n += c > 0 ? 1 : 0;
            }
            logger.info("Two-level residential location: " + n + " core-city zones (core flag file)");
        }

        /** 2026-11-19g: county FIPS of every zone (core-city share) */
        public void setZoneCounties(Map<Integer, Integer> county) {
            int n = 0;
            for (int z = 0; z < zoneIds.length; z++) {
                final Integer c = county.get(zoneIds[z]);
                if (c == null) throw new RuntimeException("zone " + zoneIds[z] + " without county");
                coreZ[z] = Arrays.stream(CORE_COUNTIES).anyMatch(x -> x == c) ? 1 : 0; n += (int) coreZ[z];
            }
            logger.info("Two-level residential location: " + n + " zones in the core-city counties " + Arrays.toString(CORE_COUNTIES));
        }

        public int zoneIndex(int zoneId) { final Integer i = zIdx.get(zoneId); return i == null ? -1 : i; }
        public int migIndex(int mig7) { final Integer i = mIdx.get(mig7); return i == null ? -1 : i; }

        /** PUMA index of a dwelling: the zone's PUMA; in a zone split by PUMAs by a hash of the dwelling id over the member shares */
        public int pumaOf(int zoneIndex, int dwellingId) {
            final int[] p = zP[zoneIndex];
            if (p.length == 1) return p[0];
            long h = (dwellingId + 0x632BE59BD9B4E019L) * 0x9E3779B97F4A7C15L; h ^= (h >>> 31); h *= 0xBF58476D1CE4E5B9L; h ^= (h >>> 29);
            final double u = (h >>> 11) * 0x1.0p-53;
            double c = 0;
            for (int k = 0; k < p.length; k++) { c += zF[zoneIndex][k]; if (u < c) return p[k]; }
            for (int k = p.length - 1; k >= 0; k--) if (zF[zoneIndex][k] > 0) return p[k];
            return p[0];
        }

        public void prepare(double[] dd, double[] jobs, double[][] race, double[][] car, double[][] pt) {
            final int nz = zoneIds.length, np = pumaIds.length, nm = migIds.length;
            dw = new double[np]; wn = new double[nz][];
            for (int z = 0; z < nz; z++) {
                wn[z] = new double[zP[z].length];
                for (int k = 0; k < zP[z].length; k++) if (!excluded[zP[z][k]]) { wn[z][k] = zW[z][k] * dd[z]; dw[zP[z][k]] += wn[z][k]; }
            }
            for (int z = 0; z < nz; z++) for (int k = 0; k < zP[z].length; k++) wn[z][k] = wn[z][k] / Math.max(dw[zP[z][k]], 1e-9);
            crimeP = new double[np]; lnddP = new double[np]; raceSh = new double[np][4]; coreP = new double[np];
            final double[] rs = new double[np];
            for (int z = 0; z < nz; z++) {
                final double ld = Math.log(Math.max(dd[z], 1) / acres[z]);
                for (int k = 0; k < zP[z].length; k++) {
                    final int p = zP[z][k]; final double w = wn[z][k];
                    if (w == 0) continue;
                    crimeP[p] += w * crime[z]; lnddP[p] += w * ld; coreP[p] += w * coreZ[z];
                    for (int r = 0; r < 4; r++) { raceSh[p][r] += w * race[z][r]; rs[p] += w * race[z][r]; }
                }
            }
            for (int p = 0; p < np; p++) for (int r = 0; r < 4; r++) raceSh[p][r] /= Math.max(rs[p], 1e-9);
            // first PUMA of each zone with a positive weight (r14: (Wn > 0).argmax(1)); 2026-11-18m: a zone without a positive weight takes
            // its own PUMA from the PUMA file (largest member share) instead of the first PUMA (such a zone has origin weight 0 anyway)
            final int[] zp = new int[nz];
            for (int z = 0; z < nz; z++) {
                int best = 0; for (int k = 1; k < zP[z].length; k++) if (zF[z][k] > zF[z][best]) best = k;
                zp[z] = emulateNaN ? 0 : zP[z][best];   // verification of the 1117 estimation (excluded PUMAs): r14's argmax gives 0
                for (int k = 0; k < zP[z].length; k++) if (wn[z][k] > 0) { zp[z] = zP[z][k]; break; }
            }
            // origin and workplace weights of the MIGPUMAs
            final double[][] O = new double[nm][], Pw = new double[nm][];
            for (int m = 0; m < nm; m++) {
                final int[] zz = migZones[m]; O[m] = new double[zz.length]; Pw[m] = new double[zz.length];
                double so = 0, sp = 0;
                for (int i = 0; i < zz.length; i++) { O[m][i] = dd[zz[i]]; Pw[m][i] = jobs[zz[i]]; so += O[m][i]; sp += Pw[m][i]; }
                for (int i = 0; i < zz.length; i++) { O[m][i] /= Math.max(so, 1e-9); Pw[m][i] /= Math.max(sp, 1e-9); }
            }
            T = new double[nm][np]; same = new double[nm][np]; adjacent = new double[nm][np];
            final double[] a = new double[nz];
            for (int m = 0; m < nm; m++) {
                Arrays.fill(a, 0);
                final int[] zz = migZones[m];
                for (int i = 0; i < zz.length; i++) {
                    final double o = O[m][i];
                    if (o == 0) continue;
                    final double[] row = car[zz[i]];
                    for (int j = 0; j < nz; j++) a[j] += o * row[j];
                    for (int k = 0; k < zP[zz[i]].length; k++) if (wn[zz[i]][k] > 0) same[m][zP[zz[i]][k]] += o;
                    for (int p = 0; p < np; p++) if (adj[zp[zz[i]]][p]) adjacent[m][p] += o;
                }
                for (int z = 0; z < nz; z++) for (int k = 0; k < zP[z].length; k++) T[m][zP[z][k]] += a[z] * wn[z][k];
                for (int p = 0; p < np; p++) adjacent[m][p] *= (1 - same[m][p]);
            }
            comCar = commute(car, Pw); comPt = commute(pt, Pw);
        }

        /** ln(1 + mean time from the PUMA's zones (Wn) to the MIGPUMA's job zones (Pw)), PUMA x MIGPUMA */
        private double[][] commute(double[][] t, double[][] Pw) {
            final int nz = zoneIds.length, np = pumaIds.length, nm = migIds.length;
            final double[][] tc = new double[np][nz];
            for (int z = 0; z < nz; z++) for (int k = 0; k < zP[z].length; k++) {
                final double w = wn[z][k];
                if (w == 0) continue;
                final double[] row = t[z], out = tc[zP[z][k]];
                for (int j = 0; j < nz; j++) out[j] += w * row[j];
            }
            final double[][] c = new double[np][nm];
            for (int p = 0; p < np; p++) for (int m = 0; m < nm; m++) {
                double s = 0; final int[] zz = migZones[m];
                for (int i = 0; i < zz.length; i++) s += tc[p][zz[i]] * Pw[m][i];
                c[p][m] = Math.log1p(s);
            }
            return c;
        }

        /** PUMA-level terms b'x without the inclusive value (NaN where the PUMA has no dwellings) */
        public double[] terms(double[] b, HhVars h, double[] lnM) { return terms(b, new double[PUMA_EXTRA.length], h, lnM); }

        public double[] terms(double[] b, double[] e, HhVars h, double[] lnM) {
            final int np = pumaIds.length; final double[] u = new double[np];
            for (int p = 0; p < np; p++) {
                if (!(dw[p] > 0)) { u[p] = Double.NaN; continue; }
                final int m = h.originMig;
                final double sm = m >= 0 ? same[m][p] : 0, tx = m >= 0 ? T[m][p] * (1 - sm) : 0, ad = m >= 0 ? adjacent[m][p] : 0;
                final double ss = m >= 0 && migState[m] == pumaState[p] ? 1 : 0;
                double com = 0;
                for (int w : h.workMigs) com += h.nocar ? comPt[p][w] : comCar[p][w];
                u[p] = b[0] * lnM[p] + b[1] * Math.min(Math.max(tx - 20, 0), 40) + b[2] * Math.max(tx - 60, 0) + b[3] * sm + b[4] * ad + b[5] * ss
                        + b[6] * com + b[7] * crimeP[p] * (h.child ? 1 : 0) + b[8] * lnddP[p] + b[9] * raceSh[p][h.race] + extra(e, h, p);
            }
            return u;
        }

        /** the terms of u(d) that do not depend on the origin (better-dwelling rule): ln M, commute, crime x children, density, race */
        /** 2026-11-19g: the optional terms of PUMA_EXTRA */
        public double extra(double[] e, HhVars h, int p) {
            final double x = Math.log(Math.max(h.income, 5000.) / 50000.);
            return lnddP[p] * (e[0] * (h.single ? 1 : 0) + e[1] * (h.young ? 1 : 0) + e[3] * x) + e[2] * coreP[p];
        }

        public double locationTerms(double[] b, double[] e, HhVars h, int p, double lnM) { return locationTerms(b, h, p, lnM) + extra(e, h, p); }

        public double locationTerms(double[] b, HhVars h, int p, double lnM) {
            double com = 0;
            for (int w : h.workMigs) com += h.nocar ? comPt[p][w] : comCar[p][w];
            return b[0] * lnM + b[6] * com + b[7] * crimeP[p] * (h.child ? 1 : 0) + b[8] * lnddP[p] + b[9] * raceSh[p][h.race];
        }
    }

    // ============================================================================================ engine
    private final DataContainer dc;
    private final HousingStrategy housing;
    private final Geo geo;
    private final double[] bDw, bPu, bEx;
    private final double[][] pt;
    private final int searchSize, ivSample;
    private final Random random;
    private int[] regionIds; private final Map<Integer, Integer> rIdx = new HashMap<>();
    private int[] zoneRegion;                     // region index of a zone index
    // per year
    private double[][] vacStart;                  // PUMA x region: vacant dwellings at the start of the year
    // 2026-11-18k: market size M of the PUMA term ln M (resloc.marketsize): vacancies (default; live vacant dwellings), stock (all
    // dwellings of the PUMA at the start of the year) or movers_prev_year (dwellings of the PUMA whose household moved in during the
    // previous simulated year; base year: households whose drawn years in the dwelling are 0, i.e. moved in within 12 months, ACS MV = 1,
    // from resloc.tenure.file). Availability of a PUMA is always: at least one vacant dwelling (live).
    private final String marketSize = ReslocProperties.get("resloc.marketsize", "vacancies").toLowerCase();
    private double[][] stockPR, moversPR;         // PUMA x region at the start of the year
    // 2026-11-18m: stock_turnover = fixed turnover rate r_p (resloc.turnover.file: puma7,turnover,...; r19_final.py) x all dwellings of
    // the PUMA (occupied + vacant, membership by f_member) at the start of the year
    private double[] turnover;
    // 2026-11-18k: race of the householder: base-year households from the race column of the household file (the synthetic population's
    // householder race, the variable of the estimation's PUMA shares); households formed later: the oldest member who is not a child
    // (fixed for the household once set)
    private static final Map<Integer, Race> householderRace = new ConcurrentHashMap<>();
    private double[] regVacStart;
    // 2026-11-19a: exact live vacancies by PUMA and region, kept by the vacancy-list observer of RealEstateDataManagerMstm
    // (vacate / occupy / construction / demolition); rebuilt from the lists at the start of every year and compared with them then
    // and at the end of every year (checkVacancies)
    private final Map<Integer, int[]> vacTracked = new HashMap<>();   // dwelling id -> {PUMA, region}
    private int[][] liveVac; private int[] livePuma;
    // 2026-11-19c (resloc.puma.vacancy.availability, default false): weight of PUMA p in the search and the move-or-not EMU x a_p,
    // a_p = min(1, live vacancy rate of p / its vacancy rate at the start of the first simulated year) (the old model's a_r per PUMA);
    // live rate = exact live vacancies / dwellings of p at the start of the year
    private final boolean pumaAvailability = Boolean.parseBoolean(ReslocProperties.get("resloc.puma.vacancy.availability", "false"));
    private double[] baseVacRate, stockP;
    // 2026-11-20b (resloc.county.vacancy.factor, default false): county vacancy factor inside the PUMA, the old model's a_r per county:
    // a_c = min(1, live vacancy rate of county (region) c / its vacancy rate at the start of the first simulated year); PUMA weight
    // x A_p = sum_c s_pc a_c (s_pc = share of the PUMA's dwellings in county c at the start of the year; in-migrants restricted to
    // region r: a_r), in the search and the move-or-not EMU; every sampled dwelling of the dwelling choice x a_c of its county.
    // Replaces a_p (resloc.puma.vacancy.availability is ignored when this switch is on). No free parameter.
    private final boolean countyFactor = Boolean.parseBoolean(ReslocProperties.get("resloc.county.vacancy.factor", "false"));
    private double[] regStock, regBaseRate;
    // 2026-11-20a (sensitivity, resloc.race.share.fixed2016, default false): the own-race share of every PUMA stays at its value of the
    // first simulated year (the 2016 base households), never updated
    private final boolean raceFixed = Boolean.parseBoolean(ReslocProperties.get("resloc.race.share.fixed2016", "false"));
    private double[][] raceSh0;
    private int[][] pumaRegions;                  // regions with vacancies of the PUMA at the start of the year
    private double[][] ivCost; private int[][] ivBed; private String[][] ivType; private boolean[][] ivNew;
    private final Map<Long, double[]> ivCache = new ConcurrentHashMap<>();
    // move-or-not (as ReslocModel)
    private final double moveScale = Double.parseDouble(ReslocProperties.get("resloc.move.scale", "1.0"));
    private final double moveDuration = Double.parseDouble(ReslocProperties.get("resloc.move.duration", "0.0"));
    private final double moveReference = Double.parseDouble(ReslocProperties.get("resloc.move.reference", "0.0"));
    private static final Map<Integer, Integer> moveInYear = new ConcurrentHashMap<>();
    private static final Map<Integer, double[]> gapAtEntry = new ConcurrentHashMap<>();
    private final List<double[]> tenureRows = new ArrayList<>();
    private final Random tenureRandom;
    // diagnostics
    private double dGap, dGapEff, dP; private long dN, nSearch, nFound, nNoPuma, nEmpty, nInmig;

    public ReslocTwoLevel(DataContainer dataContainer, HousingStrategy housingStrategy) {
        this.dc = dataContainer; this.housing = housingStrategy;
        bDw = readCoef(ReslocProperties.path("resloc.twolevel.dwelling.coefficients", "input/resloc_dwelling_coef_1118.csv"), DW_VARS);
        bPu = readCoef(ReslocProperties.path("resloc.twolevel.puma.coefficients", "input/resloc_puma_coef_1118.csv"), PUMA_VARS);
        bEx = readCoefOptional(ReslocProperties.path("resloc.twolevel.puma.coefficients", "input/resloc_puma_coef_1118.csv"), PUMA_EXTRA);
        geo = new Geo(ReslocProperties.path("resloc.twolevel.puma.zone.file", "input/resloc_puma_zone_1118.csv"),
                ReslocProperties.path("resloc.twolevel.mig.zone.file", "input/resloc_mig_zone_1118.csv"),
                ReslocProperties.path("resloc.twolevel.zone.attributes.file", "input/resloc_zone_attr_1118.csv"),
                ReslocProperties.path("resloc.twolevel.puma.adjacency.file", "input/resloc_puma_adjacency_1118.csv"), null);
        searchSize = Integer.parseInt(ReslocProperties.get("resloc.twolevel.search.size", "30"));
        ivSample = Integer.parseInt(ReslocProperties.get("resloc.twolevel.iv.dwelling.sample", "200"));
        pt = readSkim(ReslocProperties.path("resloc.transit.skim", "skims/transit_peak_time_d2d.csv.gz"), geo, 180, true);
        random = de.tum.bgu.msm.utils.SiloUtil.provideNewRandom();
        tenureRandom = de.tum.bgu.msm.utils.SiloUtil.provideNewRandom();
        readTenure(ReslocProperties.path("resloc.tenure.file", "input/tenure_by_age.csv"));
        if (!Arrays.asList("vacancies", "stock", "movers_prev_year", "stock_turnover").contains(marketSize))
            throw new RuntimeException("resloc.marketsize must be vacancies, stock, movers_prev_year or stock_turnover: " + marketSize);
        if ("stock_turnover".equals(marketSize)) {
            final String f = ReslocProperties.path("resloc.turnover.file", null);
            if (f == null) throw new RuntimeException("resloc.marketsize = stock_turnover needs resloc.turnover.file");
            turnover = readTurnover(f, geo);
        }
        readHouseholderRace();
        final Map<Integer, Integer> cty = new HashMap<>();
        for (de.tum.bgu.msm.data.Zone zz : dc.getGeoData().getZones().values()) cty.put(zz.getZoneId(), ((de.tum.bgu.msm.data.geo.MstmZone) zz).getCounty().getId());
        final String coreFile = ReslocProperties.path("resloc.twolevel.zone.core.file", null);
        if (coreFile != null) {
            final Map<Integer, Double> core = new HashMap<>();
            final List<String[]> cl = csv(coreFile); final List<String> chh = Arrays.asList(cl.get(0));
            for (String[] x : skipHeader(cl)) core.put(Integer.parseInt(x[chh.indexOf("zone")]), Double.parseDouble(x[chh.indexOf("core")]));
            geo.setZoneCore(core);
            int agree = 0;   // check against the counties of the zone system
            for (int z = 0; z < geo.zoneIds.length; z++) { final int cz = cty.get(geo.zoneIds[z]); if ((geo.coreZ[z] > 0) == Arrays.stream(CORE_COUNTIES).anyMatch(c -> c == cz)) agree++; }
            logger.info("Two-level residential location: core flags agree with the zone counties in " + agree + " of " + geo.zoneIds.length + " zones");
        } else geo.setZoneCounties(cty);
        logger.info("Two-level residential location: optional PUMA terms " + Arrays.toString(PUMA_EXTRA) + " = " + Arrays.toString(bEx));
        regionIds = dc.getGeoData().getRegions().keySet().stream().mapToInt(Integer::intValue).sorted().toArray();
        for (int i = 0; i < regionIds.length; i++) rIdx.put(regionIds[i], i);
        zoneRegion = new int[geo.zoneIds.length];
        for (int z = 0; z < geo.zoneIds.length; z++) {
            if (!dc.getGeoData().getZones().containsKey(geo.zoneIds[z])) throw new RuntimeException("zone " + geo.zoneIds[z] + " of the PUMA file not in the zone system");
            zoneRegion[z] = rIdx.get(dc.getGeoData().getZones().get(geo.zoneIds[z]).getRegion().getId());
        }
        de.tum.bgu.msm.data.RealEstateDataManagerMstm.vacancyListener = new de.tum.bgu.msm.data.RealEstateDataManagerMstm.VacancyListener() {
            @Override public void added(Dwelling dd) { vacancyAdded(dd); }
            @Override public void removed(int id) { vacancyRemoved(id); }
        };
        logger.info("Two-level residential location model (resloc.twolevel): " + geo.pumaIds.length + " PUMAs, " + geo.migIds.length
                + " migration PUMAs, " + geo.zoneIds.length + " zones; market size " + marketSize + "; search " + searchSize + " dwellings, inclusive value over " + ivSample + " vacancies");
    }

    // ------------------------------------------------------------------------------------------------ year preparation
    public void prepareYear() {
        final int nz = geo.zoneIds.length, np = geo.pumaIds.length, nr = regionIds.length;
        final double[] dd = new double[nz], jobs = new double[nz]; final double[][] race = new double[nz][4];
        for (Dwelling d : dc.getRealEstateDataManager().getDwellings()) { final int z = geo.zoneIndex(d.getZoneId()); if (z >= 0) dd[z]++; }
        for (Job j : dc.getJobDataManager().getJobs()) { final int z = geo.zoneIndex(j.getZoneId()); if (z >= 0) jobs[z]++; }
        for (Household hh : dc.getHouseholdDataManager().getHouseholds()) {
            final Dwelling d = dc.getRealEstateDataManager().getDwelling(hh.getDwellingId());
            if (d == null) continue;
            final int z = geo.zoneIndex(d.getZoneId());
            if (z >= 0) race[z][raceIndex(hh)]++;
        }
        final IndexedDoubleMatrix2D sk = dc.getTravelTimes().getPeakSkim(TransportMode.car);
        final double[][] car = new double[nz][nz];
        for (int a = 0; a < nz; a++) for (int b = 0; b < nz; b++) {
            final double t = sk.getIndexed(geo.zoneIds[a], geo.zoneIds[b]);
            car[a][b] = (Double.isNaN(t) || t >= 999) ? 300 : t;
        }
        geo.prepare(dd, jobs, race, car, pt);
        if (raceFixed) {   // 2026-11-20a (resloc.race.share.fixed2016): own-race shares of the PUMAs held at the first simulated year
            if (raceSh0 == null) { raceSh0 = new double[geo.raceSh.length][]; for (int p = 0; p < raceSh0.length; p++) raceSh0[p] = geo.raceSh[p].clone(); }
            else for (int p = 0; p < raceSh0.length; p++) geo.raceSh[p] = raceSh0[p].clone();
            logger.info("Two-level residential location: own-race shares of the PUMAs fixed at " + (raceSh0 == null ? ReslocModel.currentYear : "the first simulated year"));
        }
        // vacancies by PUMA and region, inclusive-value samples
        vacStart = new double[np][nr]; regVacStart = new double[nr];
        final List<List<Dwelling>> byPuma = new ArrayList<>();
        for (int p = 0; p < np; p++) byPuma.add(new ArrayList<>());
        for (int r = 0; r < nr; r++) {
            for (Dwelling d : dc.getRealEstateDataManager().getListOfVacantDwellingsInRegion(regionIds[r])) {
                final int p = pumaOf(d);
                if (p < 0) continue;
                vacStart[p][r]++; regVacStart[r]++; byPuma.get(p).add(d);
            }
        }
        checkVacancies("start of " + ReslocModel.currentYear);
        stockP = new double[np];
        for (Dwelling d : dc.getRealEstateDataManager().getDwellings()) { final int p = pumaOf(d); if (p >= 0) stockP[p]++; }
        if (baseVacRate == null) {
            baseVacRate = new double[np];
            for (int p = 0; p < np; p++) { double v = 0; for (int r = 0; r < nr; r++) v += vacStart[p][r]; baseVacRate[p] = stockP[p] > 0 ? v / stockP[p] : 0; }
        }
        if (pumaAvailability) {
            int below = 0; double amin = 1;
            for (int p = 0; p < np; p++) { double v = 0; for (int r = 0; r < nr; r++) v += vacStart[p][r]; final double a = avail(p, v); if (a < 1) below++; amin = Math.min(amin, a); }
            logger.info("Two-level residential location: PUMA vacancy availability on; " + below + " of " + np + " PUMAs below their base vacancy rate at the start of "
                    + ReslocModel.currentYear + ", lowest a_p " + String.format("%.3f", amin));
        }
        synchronized (vacTracked) {
            vacTracked.clear(); liveVac = new int[np][nr]; livePuma = new int[np];
            for (int r = 0; r < nr; r++) for (Dwelling d : dc.getRealEstateDataManager().getListOfVacantDwellingsInRegion(regionIds[r])) vacancyAdded(d);
        }
        stockPR = new double[np][nr]; moversPR = new double[np][nr];
        final List<List<Dwelling>> stockByPuma = new ArrayList<>();
        for (int p = 0; p < np; p++) stockByPuma.add(new ArrayList<>());
        {   // 2026-11-19a: the stock by PUMA and region always (scale ln M of u(d), regions of a PUMA)
            for (Dwelling d : dc.getRealEstateDataManager().getDwellings()) {
                final int p = pumaOf(d), z = geo.zoneIndex(d.getZoneId());
                if (p < 0) continue;
                stockPR[p][zoneRegion[z]]++; stockByPuma.get(p).add(d);
                if ("movers_prev_year".equals(marketSize) && d.getResidentId() > 0) {
                    final Household hh = dc.getHouseholdDataManager().getHouseholdFromId(d.getResidentId());
                    if (hh == null) continue;
                    final int years = yearsInDwelling(hh);   // draws the base-year tenure (resloc.tenure.file) when not known
                    final int start = de.tum.bgu.msm.properties.Properties.get().main.startYear;
                    if (ReslocModel.currentYear == start ? years == 0 : years == 1) moversPR[p][zoneRegion[z]]++;
                }
            }
        }
        regStock = new double[nr];
        for (int p = 0; p < np; p++) for (int r = 0; r < nr; r++) regStock[r] += stockPR[p][r];
        if (regBaseRate == null) { regBaseRate = new double[nr]; for (int r = 0; r < nr; r++) regBaseRate[r] = regStock[r] > 0 ? regVacStart[r] / regStock[r] : 0; }
        if (countyFactor) {
            int below = 0; double amin = 1;
            for (int r = 0; r < nr; r++) { if (regStock[r] <= 0) continue; final double a = aCounty(r); if (a < 1) below++; amin = Math.min(amin, a); }
            logger.info("Two-level residential location: county vacancy factor on; " + below + " of " + nr + " regions below their base vacancy rate at the start of "
                    + ReslocModel.currentYear + ", lowest a_c " + String.format("%.3f", amin));
        }
        pumaRegions = new int[np][];
        ivCost = new double[np][]; ivBed = new int[np][]; ivType = new String[np][]; ivNew = new boolean[np][];
        for (int p = 0; p < np; p++) {
            final List<Integer> l = new ArrayList<>();
            for (int r = 0; r < nr; r++) if (vacStart[p][r] > 0 || stockPR[p][r] > 0) l.add(r);
            pumaRegions[p] = l.stream().mapToInt(Integer::intValue).toArray();
            // 2026-11-19b: a PUMA without a vacancy at the start of the year takes its inclusive-value sample from all its dwellings,
            // so that it becomes available again as soon as a dwelling there is vacated during the year (before: no sample -> no
            // inclusive value -> unavailable for the whole year although vacancies reappeared; the regional control then failed)
            final List<Dwelling> v = byPuma.get(p).isEmpty() ? stockByPuma.get(p) : byPuma.get(p); v.sort(Comparator.comparingInt(Dwelling::getId)); Collections.shuffle(v, random);
            final int n = Math.min(ivSample, v.size());
            ivCost[p] = new double[n]; ivBed[p] = new int[n]; ivType[p] = new String[n]; ivNew[p] = new boolean[n];
            for (int i = 0; i < n; i++) {
                final Dwelling d = v.get(i);
                ivCost[p][i] = d.getPrice(); ivBed[p][i] = d.getBedrooms(); ivType[p][i] = d.getType().toString(); ivNew[p][i] = (ReslocModel.currentYear - d.getYearBuilt()) <= 5;
            }
        }
        ivCache.clear();
        if (dN > 0) logger.info(String.format("  Move-or-not (two-level) of the previous year: mean gap %.3f, mean gap - kappa gap0 %.3f, mean P %.4f over %d households",
                dGap / dN, dGapEff / dN, dP / dN, dN));
        if (nSearch > 0) logger.info("  Two-level search of the previous year: " + nSearch + " searches (" + nInmig + " in-migrants in a target region), "
                + nFound + " found a dwelling, " + nNoPuma + " without an available PUMA, " + nEmpty + " drew a PUMA without vacancies");
        dGap = dGapEff = dP = 0; dN = nSearch = nFound = nNoPuma = nEmpty = nInmig = 0;
        int avail = 0; double vac = 0;
        for (int p = 0; p < np; p++) { if (geo.dw[p] > 0 && byPuma.get(p).size() > 0) avail++; vac += byPuma.get(p).size(); }
        logger.info("Two-level residential location prepared for " + ReslocModel.currentYear + ": " + (long) Arrays.stream(dd).sum() + " dwellings, "
                + (long) vac + " vacant, " + avail + " of " + np + " PUMAs with vacancies");
    }

    public int pumaOf(Dwelling d) {
        final int z = geo.zoneIndex(d.getZoneId());
        return z < 0 ? -1 : geo.pumaOf(z, d.getId());
    }

    private static int raceIndex(Household hh) {
        Race r = householderRace.get(hh.getId());
        if (r == null) {   // household formed during the simulation: the oldest member who is not a child (any member if all are)
            Person best = null;
            for (Person p : hh.getPersons().values()) {
                final boolean adult = p.getRole() != de.tum.bgu.msm.data.person.PersonRole.CHILD;
                final boolean bAdult = best != null && best.getRole() != de.tum.bgu.msm.data.person.PersonRole.CHILD;
                if (best == null || (adult && !bAdult) || (adult == bAdult && (p.getAge() > best.getAge() || (p.getAge() == best.getAge() && p.getId() < best.getId())))) best = p;
            }
            r = best instanceof de.tum.bgu.msm.data.person.PersonMstm ? ((de.tum.bgu.msm.data.person.PersonMstm) best).getRace() : null;
            if (r == null) r = hh instanceof HouseholdMstm && ((HouseholdMstm) hh).getRace() != null ? ((HouseholdMstm) hh).getRace() : Race.other;
            if (hh.getId() > 0 && !hh.getPersons().isEmpty()) householderRace.put(hh.getId(), r);
        }
        return r.ordinal();
    }

    /** turnover rate by PUMA index; every PUMA must be listed with a positive rate */
    static double[] readTurnover(String f, Geo geo) {
        final List<String[]> l = csv(f); final List<String> h = Arrays.asList(l.get(0));
        final int iP = h.indexOf("puma7"), iT = h.indexOf("turnover");
        final double[] r = new double[geo.pumaIds.length]; Arrays.fill(r, Double.NaN);
        for (String[] x : skipHeader(l)) { final Integer p = geo.pIdx.get(Integer.parseInt(x[iP])); if (p != null) r[p] = Double.parseDouble(x[iT]); }
        for (int p = 0; p < r.length; p++) if (!(r[p] > 0)) throw new RuntimeException("PUMA " + geo.pumaIds[p] + " without a positive turnover rate in " + f);
        logger.info("Two-level residential location: market size = turnover x dwellings of the PUMA, rates from " + f);
        return r;
    }

    /** base-year householder race from the race column of the household file of the start year */
    private void readHouseholderRace() {
        final de.tum.bgu.msm.properties.Properties pr = de.tum.bgu.msm.properties.Properties.get();
        final String f = pr.main.baseDirectory + pr.householdData.householdFileName + "_" + pr.main.startYear + ".csv";
        final List<String[]> l = csv(f); final List<String> h = Arrays.asList(l.get(0));
        final int iI = h.indexOf("id"), iR = h.indexOf("race");
        if (iR < 0) { logger.warn("No race column in " + f + ": householder race from the oldest adult member"); return; }
        int n = 0;
        for (String[] x : skipHeader(l)) { householderRace.put(Integer.parseInt(x[iI]), Race.valueOf(x[iR].replace("\"", ""))); n++; }
        logger.info("Two-level residential location: householder race of " + n + " base-year households read from " + f);
    }

    /** vacant dwellings of PUMA p now (region r only if r >= 0): live region counts x the PUMA's share at the start of the year */
    /** ln M_p of the PUMA term (resloc.marketsize); region r >= 0: the part of the PUMA in region r */
    private double lnMarket(int p, int r) {
        if ("vacancies".equals(marketSize)) return Math.log(Math.max(market(p, r), 1.));
        final double[][] a = "movers_prev_year".equals(marketSize) ? moversPR : stockPR;
        double m = 0;
        for (int q = 0; q < a[p].length; q++) if (r < 0 || q == r) m += a[p][q];
        if (turnover != null) m *= turnover[p];
        return Math.log(Math.max(m, 1.));
    }

    /** a_p for v live vacancies of PUMA p (1 when resloc.puma.vacancy.availability is off) */
    /** a_c of region index r (live vacancies of the region / its stock at the start of the year, relative to the base rate) */
    private double aCounty(int r) {
        if (regStock == null || !(regStock[r] > 0) || !(regBaseRate[r] > 0)) return 1.0;
        return Math.min(1.0, dc.getRealEstateDataManager().getNumberOfVacantDDinRegion(regionIds[r]) / regStock[r] / regBaseRate[r]);
    }

    /** A_p = sum_c s_pc a_c (region r >= 0: a_r) */
    private double aPuma(int p, int r) {
        if (r >= 0) return aCounty(r);
        double s = 0, a = 0;
        for (int q : pumaRegions[p]) { s += stockPR[p][q]; a += stockPR[p][q] * aCounty(q); }
        return s > 0 ? a / s : 1.0;
    }

    private double avail(int p, double v) {
        if (!pumaAvailability || stockP == null || !(stockP[p] > 0) || !(baseVacRate[p] > 0)) return 1.0;
        return Math.min(1.0, v / stockP[p] / baseVacRate[p]);
    }

    /** live vacant dwellings of PUMA p (only those in region r if r >= 0), exact (2026-11-19a) */
    private double market(int p, int r) {
        synchronized (vacTracked) { return r < 0 ? livePuma[p] : liveVac[p][r]; }
    }

    private void vacancyAdded(Dwelling d) {
        if (d == null || liveVac == null) return;
        final int p = pumaOf(d), z = geo.zoneIndex(d.getZoneId());
        if (p < 0) return;
        synchronized (vacTracked) {
            if (vacTracked.containsKey(d.getId())) return;
            final int r = zoneRegion[z]; vacTracked.put(d.getId(), new int[]{p, r}); liveVac[p][r]++; livePuma[p]++;
        }
    }

    private void vacancyRemoved(int id) {
        if (liveVac == null) return;
        synchronized (vacTracked) {
            final int[] x = vacTracked.remove(id);
            if (x != null) { liveVac[x[0]][x[1]]--; livePuma[x[0]]--; }
        }
    }

    /** compares the live counts with a recount of the vacancy lists; logs the vacancies and PUMAs without vacancy */
    public void checkVacancies(String when) {
        if (liveVac == null) return;
        final int np = geo.pumaIds.length, nr = regionIds.length; final int[][] c = new int[np][nr];
        for (int r = 0; r < nr; r++) for (Dwelling d : dc.getRealEstateDataManager().getListOfVacantDwellingsInRegion(regionIds[r])) { final int p = pumaOf(d); if (p >= 0) c[p][r]++; }
        int bad = 0, zero = 0; long tot = 0, diff = 0;
        synchronized (vacTracked) {
            for (int p = 0; p < np; p++) {
                int s = 0; boolean ok = true;
                for (int r = 0; r < nr; r++) { s += c[p][r]; if (c[p][r] != liveVac[p][r]) { ok = false; diff += Math.abs(c[p][r] - liveVac[p][r]); } }
                if (!ok) bad++; if (s == 0) zero++; tot += s;
            }
        }
        if (bad > 0) logger.error("Two-level residential location, " + when + ": live vacancy counter differs from the recount of the vacancy lists in " + bad + " PUMAs (sum |diff| " + diff + ")");
        else logger.info("Two-level residential location, " + when + ": live vacancy counter equals the recount of the vacancy lists");
        logger.info("Two-level residential location, " + when + ": " + tot + " vacant dwellings, " + zero + " of " + np + " PUMAs without a vacancy");
    }

    // ------------------------------------------------------------------------------------------------ household
    private HhVars vars(Household hh, boolean inmigrant) {
        final HhVars h = new HhVars();
        h.income = HouseholdUtil.getAnnualHhIncome(hh); h.size = hh.getHhSize();
        int amax = 0;
        for (Person p : hh.getPersons().values()) { h.child |= p.getAge() < 18; amax = Math.max(amax, p.getAge()); }
        h.single = h.size == 1; h.young = amax < 35;
        h.race = raceIndex(hh);
        Dwelling cur = dc.getRealEstateDataManager().getDwelling(hh.getDwellingId());
        Household origin = null;
        if (cur == null && !inmigrant) {   // a household being formed searches from the home (and with the cars) of the household its members come from
            final Object od = hh.getAttribute(ReslocModel.ORIGIN_HOUSEHOLD).orElse(null);
            if (od instanceof Household) origin = (Household) od;
            if (origin == null) for (Person p : hh.getPersons().values()) {
                final Household ph = p.getHousehold();
                if (ph != null && ph != hh && ph.getDwellingId() > 0) { origin = ph; break; }
            }
            if (origin != null) cur = dc.getRealEstateDataManager().getDwelling(origin.getDwellingId());
        }
        h.nocar = !(hh.getAutos() > 0 || (hh.getDwellingId() <= 0 && origin != null && origin.getAutos() > 0));
        if (!inmigrant && cur != null) { final int z = geo.zoneIndex(cur.getZoneId()); h.originMig = z < 0 ? -1 : geo.zoneMig[z]; }
        if (!inmigrant) {
            final List<Integer> w = new ArrayList<>();
            for (Person p : hh.getPersons().values()) {
                if (p.getOccupation() != Occupation.EMPLOYED || p.getJobId() <= 0) continue;
                final Job j = dc.getJobDataManager().getJobFromId(p.getJobId());
                if (j == null) continue;
                final int z = geo.zoneIndex(j.getZoneId());
                if (z >= 0) w.add(geo.zoneMig[z]);
            }
            h.workMigs = w.stream().mapToInt(Integer::intValue).toArray();
        }
        return h;
    }

    /** inclusive values by PUMA (NaN without a sample), cached by income on a 0.5 % log grid and bedrooms needed */
    private double[] iv(HhVars h) {
        final long ki = Math.round(Math.log(Math.max(h.income, 5000.)) * 200.); final int need = Math.min(h.size, 5);
        return ivCache.computeIfAbsent(ki * 8 + need, k -> {
            final double inc = Math.exp(ki / 200.); final int np = geo.pumaIds.length; final double[] out = new double[np];
            for (int p = 0; p < np; p++) out[p] = inclusiveValue(bDw, inc, need, ivCost[p], ivBed[p], ivType[p], ivNew[p]);
            return out;
        });
    }

    /** ln mean exp(V_d) over the given dwellings (r14.upper_data); NaN when empty */
    public static double inclusiveValue(double[] b, double income, int size, double[] cost, int[] bed, String[] type, boolean[] new5) {
        if (cost.length == 0) return Double.NaN;
        final double[] v = new double[cost.length]; double mx = Double.NEGATIVE_INFINITY;
        for (int i = 0; i < v.length; i++) { v[i] = dwellingUtility(b, income, size, cost[i], bed[i], type[i], new5[i]); mx = Math.max(mx, v[i]); }
        double s = 0; for (double x : v) s += Math.exp(x - mx);
        return Math.log(s / v.length) + mx;
    }

    /** U_p of every PUMA (NEGATIVE_INFINITY = not available); region >= 0: in-migrant placed in that region */
    private double[] utilities(HhVars h, int region, double[] lnMout) {
        final int np = geo.pumaIds.length; final double[] lnM = new double[np], mk = new double[np];
        for (int p = 0; p < np; p++) { mk[p] = market(p, region); lnM[p] = lnMarket(p, region); }   // availability: a vacancy (mk > 0)
        final double[] t = geo.terms(bPu, bEx, h, lnM), iv = iv(h), u = new double[np];
        for (int p = 0; p < np; p++) u[p] = (mk[p] > 0 && !Double.isNaN(t[p]) && !Double.isNaN(iv[p])) ? t[p] + iv[p] : Double.NEGATIVE_INFINITY;
        if (countyFactor) { for (int p = 0; p < np; p++) if (!Double.isInfinite(u[p])) u[p] += Math.log(aPuma(p, region)); }   // 2026-11-20b: x A_p
        else if (pumaAvailability) for (int p = 0; p < np; p++) if (!Double.isInfinite(u[p])) u[p] += Math.log(avail(p, market(p, -1)));   // 2026-11-19c: x a_p
        if (lnMout != null) System.arraycopy(lnM, 0, lnMout, 0, np);
        return u;
    }

    // ------------------------------------------------------------------------------------------------ search
    /** dwelling id chosen by the household, -1 if none; targetRegion = in-migrant placed in that region (null: any) */
    public int search(Household household, Region targetRegion) {
        if (vacStart == null) prepareYear();
        final boolean inmig = targetRegion != null;
        final int r = inmig ? rIdx.getOrDefault(targetRegion.getId(), -1) : -1;
        final HhVars h = vars(household, inmig);
        final double[] u = utilities(h, r, null);
        nSearch++; if (inmig) nInmig++;
        for (int attempt = 0; attempt < 5; attempt++) {
            double mx = Double.NEGATIVE_INFINITY;
            for (double x : u) mx = Math.max(mx, x);
            if (Double.isInfinite(mx)) { nNoPuma++; return -1; }
            double s = 0; final double[] w = new double[u.length];
            for (int p = 0; p < u.length; p++) { w[p] = Double.isInfinite(u[p]) ? 0 : Math.exp(u[p] - mx); s += w[p]; }
            double x = random.nextDouble() * s; int p = -1;
            for (int q = 0; q < w.length; q++) { if (w[q] <= 0) continue; p = q; x -= w[q]; if (x <= 0) break; }
            final int id = chooseDwelling(household, h, p, r);
            if (id > 0) { nFound++; return id; }
            nEmpty++; u[p] = Double.NEGATIVE_INFINITY;   // no vacancy left in the PUMA (or none eligible): draw again without it
        }
        return -1;
    }

    private int chooseDwelling(Household household, HhVars h, int p, int r) {
        final List<Dwelling> cand = new ArrayList<>();
        for (int q : pumaRegions[p]) {
            if (r >= 0 && q != r) continue;
            for (Dwelling d : dc.getRealEstateDataManager().getListOfVacantDwellingsInRegion(regionIds[q])) if (pumaOf(d) == p) cand.add(d);
        }
        if (cand.isEmpty()) return -1;
        final int n = Math.min(searchSize, cand.size());
        final double[] w = new double[n]; final Dwelling[] dd = new Dwelling[n]; double s = 0;
        for (int i = 0; i < n; i++) {
            final int j = i + random.nextInt(cand.size() - i);
            final Dwelling d = cand.get(j); cand.set(j, cand.get(i)); cand.set(i, d); dd[i] = d;
            if (!housing.isHouseholdEligibleToLiveHere(household, (DwellingMstm) d)) continue;
            w[i] = dwellingUtility(bDw, h.income, h.size, d.getPrice(), d.getBedrooms(), d.getType().toString(), (ReslocModel.currentYear - d.getYearBuilt()) <= 5);
            if (countyFactor) {   // 2026-11-20b: x a_c of the dwelling's county (in logs; a_c = 0 cannot occur for a vacant dwelling of the county)
                final double ac = aCounty(zoneRegion[geo.zoneIndex(d.getZoneId())]);
                w[i] += Math.log(Math.max(ac, 1e-300));
            }
        }
        double mx = Double.NEGATIVE_INFINITY;
        for (int i = 0; i < n; i++) if (housing.isHouseholdEligibleToLiveHere(household, (DwellingMstm) dd[i])) mx = Math.max(mx, w[i]); else w[i] = Double.NEGATIVE_INFINITY;
        if (Double.isInfinite(mx)) return -1;
        for (int i = 0; i < n; i++) { w[i] = Double.isInfinite(w[i]) ? 0 : Math.exp(w[i] - mx); s += w[i]; }
        double x = random.nextDouble() * s;
        for (int i = 0; i < n; i++) { if (w[i] <= 0) continue; x -= w[i]; if (x <= 0) return dd[i].getId(); }
        for (int i = n - 1; i >= 0; i--) if (w[i] > 0) return dd[i].getId();
        return -1;
    }

    // ------------------------------------------------------------------------------------------------ move-or-not, better dwelling
    /** u(d) = U_p - IV_p + V_d - ln M_p, with the origin terms of the household's current home */
    private double dwellingUtility(HhVars h, Dwelling d, double[] lnMbuf) {
        final int p = d == null ? -1 : pumaOf(d);
        if (p < 0 || !(geo.dw[p] > 0)) return Double.NEGATIVE_INFINITY;
        final double lnM = lnMarket(p, -1);   // 2026-11-19a: scale - ln M_p (was - ln vacancies)
        final double[] lnMv = new double[geo.pumaIds.length]; lnMv[p] = lnM;
        final double t = geo.terms(bPu, bEx, h, lnMv)[p];
        return t + dwellingUtility(bDw, h.income, h.size, d.getPrice(), d.getBedrooms(), d.getType().toString(), (ReslocModel.currentYear - d.getYearBuilt()) <= 5) - lnM;
    }

    /** better-dwelling rule: u(d) without the origin terms */
    public double dwellingLevelUtility(Household household, Dwelling d) {
        if (vacStart == null) prepareYear();
        final int p = d == null ? -1 : pumaOf(d);
        if (p < 0 || !(geo.dw[p] > 0)) return Double.NEGATIVE_INFINITY;
        final HhVars h = vars(household, false);
        final double lnM = lnMarket(p, -1);   // 2026-11-19a: scale - ln M_p (was - ln vacancies)
        return geo.locationTerms(bPu, bEx, h, p, lnM) - lnM
                + dwellingUtility(bDw, h.income, h.size, d.getPrice(), d.getBedrooms(), d.getType().toString(), (ReslocModel.currentYear - d.getYearBuilt()) <= 5);
    }

    public double moveProbability(Household household, Dwelling current, double shift) {
        if (vacStart == null) prepareYear();
        final HhVars h = vars(household, false);
        final double[] u = utilities(h, -1, null);
        double mx = Double.NEGATIVE_INFINITY;
        for (double x : u) mx = Math.max(mx, x);
        if (Double.isInfinite(mx)) return 0;
        double s = 0; for (double x : u) if (!Double.isInfinite(x)) s += Math.exp(x - mx);
        final double emu = mx + Math.log(s);
        final double uc = dwellingUtility(h, current, null);
        if (Double.isInfinite(uc)) return 1;
        final int years = yearsInDwelling(household);
        final double gap = emu - uc;
        final int start = ReslocModel.currentYear - years;
        double[] g0 = gapAtEntry.get(household.getId());
        if (g0 == null || g0[0] != start) { g0 = new double[]{start, gap}; gapAtEntry.put(household.getId(), g0); }
        final double gapEff = gap - moveReference * g0[1];
        final double x = moveScale * gapEff + moveDuration * Math.log1p(years);
        final double p = 1 - 1 / (1 + shift * Math.exp(Math.max(-700, Math.min(700, x))));
        dGap += gap; dGapEff += gapEff; dP += p; dN++;
        return p;
    }

    public static void recordMove(int householdId) { moveInYear.put(householdId, ReslocModel.currentYear); }

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
            y = ReslocModel.currentYear - d;
            moveInYear.put(hh.getId(), y);
        }
        return Math.max(0, ReslocModel.currentYear - y);
    }

    private void readTenure(String file) {
        if (!new File(file).exists()) { logger.warn("No tenure file " + file + ": base-year households start with 0 years in their dwelling"); return; }
        final List<String[]> l = csv(file); final List<String> h = Arrays.asList(l.get(0));
        final int a0 = h.indexOf("age_from"), a1 = h.indexOf("age_to"), d0 = h.indexOf("dur_from"), d1 = h.indexOf("dur_to"), s = h.indexOf("share");
        for (String[] x : l.subList(1, l.size()))
            tenureRows.add(new double[]{Double.parseDouble(x[a0]), Double.parseDouble(x[a1]), Double.parseDouble(x[d0]), Double.parseDouble(x[d1]), Double.parseDouble(x[s])});
    }

    // ============================================================================================ input helpers
    static List<String[]> csv(String file) {
        final List<String[]> out = new ArrayList<>();
        try (BufferedReader r = new BufferedReader(new FileReader(file))) {
            String line;
            while ((line = r.readLine()) != null) {
                if (line.isBlank() || line.startsWith("#")) continue;
                final String[] x = line.split(",", -1);
                for (int i = 0; i < x.length; i++) x[i] = x[i].trim();
                out.add(x);
            }
        } catch (IOException e) {
            throw new RuntimeException("Could not read " + file, e);
        }
        return out;
    }

    /** CSV line split at commas outside double quotes */
    static String[] splitQuoted(String line) {
        final List<String> out = new ArrayList<>(); final StringBuilder b = new StringBuilder(); boolean q = false;
        for (char ch : line.toCharArray()) { if (ch == '"') q = !q; else if (ch == ',' && !q) { out.add(b.toString()); b.setLength(0); } else b.append(ch); }
        out.add(b.toString()); return out.toArray(new String[0]);
    }

    private static List<String[]> skipHeader(List<String[]> l) { return l.subList(1, l.size()); }

    /** FROM,TO,VALUE csv.gz in the zone index order of geo; values >= 999 or missing -> missing; cap: min(value, missing) */
    static double[][] readSkim(String file, Geo geo, double missing, boolean cap) {
        final int nz = geo.zoneIds.length; final double[][] m = new double[nz][nz];
        for (double[] row : m) Arrays.fill(row, missing);
        try (BufferedReader r = new BufferedReader(new InputStreamReader(new GZIPInputStream(new FileInputStream(file))))) {
            r.readLine(); String line;
            while ((line = r.readLine()) != null) {
                final String[] x = line.split(",");
                final int i = geo.zoneIndex(Integer.parseInt(x[0].trim())), j = geo.zoneIndex(Integer.parseInt(x[1].trim()));
                if (i < 0 || j < 0) continue;
                final double v = Double.parseDouble(x[2].trim());
                m[i][j] = (Double.isNaN(v) || v >= 999) ? missing : (cap ? Math.min(v, missing) : v);
            }
        } catch (IOException e) {
            throw new RuntimeException("Could not read skim " + file, e);
        }
        return m;
    }

    // ============================================================================================ verification
    /**
     * Verification against the estimation (r18_export_silo.py):
     *   dwelling <dwelling coef> <in.csv> <out.csv>        in: id,alt,income,size,cost,bedrooms,type,new5 -> id,alt,V
     *   puma <puma coef> <dwelling coef> <puma_zone> <mig_zone> <zone_attr> <adjacency> <car skim> <transit skim> <zone_inputs.csv>
     *        <pool.csv> <M.csv> <hh.csv> <out.csv> [excluded PUMAs, '|' separated]
     *        zone_inputs: zone,dwellings,jobs,n_white,n_black,n_hispanic,n_other; pool: puma7,cost,bedrooms,type,new5; M: puma7,M;
     *        hh: id,income,size,mig7,pow ('|' separated MIGPUMAs of the workers),nocar,child,race -> id,puma7,V (available PUMAs only)
     */
    public static void main(String[] a) throws IOException {
        if (a[0].equals("dwelling")) {
            final double[] b = readCoef(a[1], DW_VARS);
            final List<String[]> in = csv(a[2]); final List<String> h = Arrays.asList(in.get(0));
            try (PrintWriter w = new PrintWriter(a[3])) {
                w.println("id,alt,V");
                for (String[] x : skipHeader(in)) w.println(x[h.indexOf("id")] + "," + x[h.indexOf("alt")] + "," + dwellingUtility(b, Double.parseDouble(x[h.indexOf("income")]),
                        Integer.parseInt(x[h.indexOf("size")]), Double.parseDouble(x[h.indexOf("cost")]), Integer.parseInt(x[h.indexOf("bedrooms")]), x[h.indexOf("type")],
                        Integer.parseInt(x[h.indexOf("new5")]) == 1));
            }
            return;
        }
        final double[] bp = readCoef(a[1], PUMA_VARS), bd = readCoef(a[2], DW_VARS), be = readCoefOptional(a[1], PUMA_EXTRA);
        final int[] excl = a.length > 14 && !a[14].isBlank() ? Arrays.stream(a[14].split("\\|")).mapToInt(Integer::parseInt).toArray() : null;
        final Geo g = new Geo(a[3], a[4], a[5], a[6], excl);
        if (a.length > 15) {   // 2026-11-19g: zoneSystem.csv (ZoneId, COUNTYFIPS; quoted fields with commas allowed) for the core-city share
            final Map<Integer, Integer> cty = new HashMap<>();
            try (BufferedReader r = new BufferedReader(new FileReader(a[15]))) {
                final List<String> h = Arrays.asList(splitQuoted(r.readLine()));
                final int iz = h.indexOf("ZoneId"), ic = h.indexOf("COUNTYFIPS"); String line;
                while ((line = r.readLine()) != null) { if (line.isBlank()) continue; final String[] x = splitQuoted(line); cty.put(Integer.parseInt(x[iz].trim()), Integer.parseInt(x[ic].trim())); }
            }
            g.setZoneCounties(cty);
        }
        final int nz = g.zoneIds.length, np = g.pumaIds.length;
        final double[][] car = readSkim(a[7], g, 300, false), pt = readSkim(a[8], g, 180, true);
        final double[] dd = new double[nz], jobs = new double[nz]; final double[][] race = new double[nz][4];
        final List<String[]> zi = csv(a[9]); final List<String> zh = Arrays.asList(zi.get(0));
        for (String[] x : skipHeader(zi)) {
            final int z = g.zoneIndex(Integer.parseInt(x[zh.indexOf("zone")]));
            dd[z] = Double.parseDouble(x[zh.indexOf("dwellings")]); jobs[z] = Double.parseDouble(x[zh.indexOf("jobs")]);
            for (int r = 0; r < 4; r++) race[z][r] = Double.parseDouble(x[zh.indexOf("n_" + RACES[r])]);
        }
        if (zh.contains("core")) {   // 2026-11-19g
            final Map<Integer, Double> core = new HashMap<>();
            for (String[] x : skipHeader(zi)) core.put(Integer.parseInt(x[zh.indexOf("zone")]), Double.parseDouble(x[zh.indexOf("core")]));
            g.setZoneCore(core);
        }
        g.prepare(dd, jobs, race, car, pt);
        final Map<Integer, List<String[]>> pool = new HashMap<>();
        final List<String[]> pl = csv(a[10]); final List<String> ph = Arrays.asList(pl.get(0));
        for (String[] x : skipHeader(pl)) pool.computeIfAbsent(g.pIdx.get(Integer.parseInt(x[ph.indexOf("puma7")])), k -> new ArrayList<>()).add(x);
        final double[] lnM = new double[np], M = new double[np];
        for (String[] x : skipHeader(csv(a[11]))) { final int p = g.pIdx.get(Integer.parseInt(x[0])); M[p] = Double.parseDouble(x[1]); lnM[p] = Math.log(Math.max(M[p], 1.)); }
        final List<String[]> hl = csv(a[12]); final List<String> hh = Arrays.asList(hl.get(0));
        try (PrintWriter w = new PrintWriter(a[13])) {
            w.println("id,puma7,V");
            for (String[] x : skipHeader(hl)) {
                final HhVars h = new HhVars();
                h.income = Double.parseDouble(x[hh.indexOf("income")]); h.size = Integer.parseInt(x[hh.indexOf("size")]);
                h.originMig = g.migIndex(Integer.parseInt(x[hh.indexOf("mig7")])); h.nocar = Integer.parseInt(x[hh.indexOf("nocar")]) == 1;
                h.child = Integer.parseInt(x[hh.indexOf("child")]) == 1; h.race = Arrays.asList(RACES).indexOf(x[hh.indexOf("race")]);
                if (hh.contains("age_max")) { h.single = h.size == 1; h.young = Integer.parseInt(x[hh.indexOf("age_max")]) < 35; }
                final String pw = x[hh.indexOf("pow")];
                h.workMigs = pw.isBlank() ? new int[0] : Arrays.stream(pw.split("\\|")).mapToInt(s -> g.migIndex(Integer.parseInt(s.trim()))).filter(m -> m >= 0).toArray();
                final double[] t = g.terms(bp, be, h, lnM);
                for (int p = 0; p < np; p++) {
                    final List<String[]> d = pool.getOrDefault(p, Collections.emptyList());
                    final double[] c = new double[d.size()]; final int[] bed = new int[d.size()]; final String[] ty = new String[d.size()]; final boolean[] n5 = new boolean[d.size()];
                    for (int i = 0; i < c.length; i++) { final String[] y = d.get(i); c[i] = Double.parseDouble(y[ph.indexOf("cost")]); bed[i] = Integer.parseInt(y[ph.indexOf("bedrooms")]); ty[i] = y[ph.indexOf("type")]; n5[i] = Integer.parseInt(y[ph.indexOf("new5")]) == 1; }
                    final double iv = inclusiveValue(bd, h.income, h.size, c, bed, ty, n5);
                    if (Double.isNaN(iv) || Double.isNaN(t[p]) || !(M[p] > 0)) continue;
                    w.println(x[hh.indexOf("id")] + "," + g.pumaIds[p] + "," + (t[p] + iv));
                }
            }
        }
    }
}
