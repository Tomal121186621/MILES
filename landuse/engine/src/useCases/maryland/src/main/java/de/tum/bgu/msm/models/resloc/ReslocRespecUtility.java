package de.tum.bgu.msm.models.resloc;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

/**
 * Baltimore 2026 (2026-11-09, resloc.spec = respec): utilities of the re-specified residential location model
 * (side_experiments/respec_2026-11/step_by_step/residential), as pure functions of the household and alternative variables, so
 * that the engine (ReslocModel) and the verification harness (ReslocRespecVerify) use the same code.
 *
 * Household variables (Hh): income in 2016 $ at least $5,000, lninc = ln(income / 50,000); size = persons; need = 1 for one person,
 * else min(size - 1, 4) (bedroom need); child = any person under 18; ageMax = age of the OLDEST member (all persons; the survey and
 * PUMS scripts use the oldest member, not a householder); age bands under 35 / 50-64 / 65+ (reference 35-49); hhs5 = min(size, 6) - 1
 * (zone part); nocar = household without a car.
 *
 * Zone x structure-type cell (r03 / r08 chosen form, multimodal accessibility):
 *   V_B = theta lnD + accW aw + accW_x_nocar aw nocar + an (accN + accN_x_child child + accN_x_ageU35 aU35 + accN_x_age50_64 a50
 *         + accN_x_age65 a65 + accN_x_hhs hhs5) + lncost (lncost + lncost_x_inc lninc + lncost_x_hhs hhs5) + sim share_own_group
 *         + 2026-11-10 land use of the zone: lnddens (b_lnddens + b_lnddens_x_nocar nocar + b_lnddens_x_child child) + b_lnjden lnjden
 *           + b_lnretden lnretden + b_mix mix + b_park park; lnddens = ln(dwellings / acre), lnjden = ln(1 + jobs / acre), lnretden =
 *           ln(1 + retail jobs / km2), mix = entropy of retail, office, other jobs and dwellings / ln 4, park = paid-parking share
 *         [+ commute_log sum_w ln(1+t) + commute_log_x_inc ... (commute part, separate)]
 * Dwelling (r06 final, terms and terms x ln income):
 *   V_A = sum_p (b_p + b_p_x_lninc lninc) x_p over p in {bur_lo, bur_mid, bur_hi, lncost, bed_short, bed_extra, new5}
 *         + type t != SFD: b_t + b_t_x_size (size - 1) + b_t_x_child child + b_t_x_ageU35 aU35 + b_t_x_age50_64 a50 + b_t_x_age65 a65
 *           + b_t_x_lninc lninc
 *   burden b = min(12 cost / income, 3), bur_lo = min(b, .3), bur_mid = min(max(b - .3, 0), .2), bur_hi = max(b - .5, 0);
 *   lncost = ln max(cost, 100); bed_short = max(0, need - bedrooms), bed_extra = max(0, bedrooms - need); new5 = built <= 5 years ago.
 *   (Household size in the type interactions is not capped, as in s04_dwelling.hh_terms.)
 * County (r05 step Ja, inclusive value of the dwelling part fixed at 1, no car-time effect below 20 min):
 *   U_r = lam_B IV_B + lam_A IV_A + d2 (b_d2 + b_d2_x_lninc lninc) + d3 (b_d3 + b_d3_x_lninc lninc) + d1 b_d1
 *         + same (b_same + b_same_x_age (ageMax - 50) / 10) + b_adjacent adj + b_same_state sameState
 *         + com (b_commute_log + b_commute_log_x_inc lninc) + b_growth growth_r + b_crime_x_child crime_r child (+ b_crime crime_r)
 *   d1 = min(t, 20), d2 = min(max(t - 20, 0), 40), d3 = max(t - 60, 0), t = car time to the county (0 for the current county);
 *   same = 1 for the current county (estimation: share of the origin area in the county); adj = county borders the current one
 *   (estimation: origin share in bordering counties, x (1 - same)).
 * Missing coefficients count as 0.
 */
public final class ReslocRespecUtility {

    private ReslocRespecUtility() {}

    public static final String[] DW_TYPES = {"SFA", "MF234", "MF5plus", "MH"};
    private static final String[] PRICE = {"bur_lo", "bur_mid", "bur_hi", "lncost", "bed_short", "bed_extra", "new5"};

    /** household variables of the re-specified model */
    public static final class HhVars {
        public final double inc, lninc, size, need, child, ageMax, aU35, a50, a65, hhs5, nocar;

        public HhVars(double income, int size, boolean child, int ageMax, boolean nocar) {
            this.inc = Math.max(income, 5000);
            this.lninc = Math.log(this.inc / 50000.);
            this.size = size;
            this.need = size <= 1 ? 1 : Math.min(size - 1, 4);
            this.child = child ? 1 : 0;
            this.ageMax = ageMax;
            this.aU35 = ageMax < 35 ? 1 : 0;
            this.a50 = (ageMax >= 50 && ageMax < 65) ? 1 : 0;
            this.a65 = ageMax >= 65 ? 1 : 0;
            this.hhs5 = Math.min(size, 6) - 1;
            this.nocar = nocar ? 1 : 0;
        }

        /** age band index for cache keys: 0 under 35, 1 35-49, 2 50-64, 3 65+ */
        public int ageBand() {
            return aU35 > 0 ? 0 : (a50 > 0 ? 2 : (a65 > 0 ? 3 : 1));
        }
    }

    private static double g(Map<String, Double> c, String n) {
        Double v = c.get(n);
        return v == null ? 0. : v;
    }

    /** cell utility without the commute; lnD = ln dwellings of the type in the zone (theta defaults to 1) */
    public static double cell(Map<String, Double> c, HhVars h, double lnD, double aw, double an, double lncost, double sim) {
        return cell(c, h, lnD, aw, an, lncost, sim, null);
    }

    /** land-use variables of a zone, in the order of LU_NAMES (null = none) */
    public static final String[] LU_NAMES = {"lnddens", "lnjden", "lnretden", "mix", "park"};

    public static double cell(Map<String, Double> c, HhVars h, double lnD, double aw, double an, double lncost, double sim, double[] lu) {
        double v = 0;
        if (lu != null) {
            v = lu[0] * (g(c, "lnddens") + g(c, "lnddens_x_nocar") * h.nocar + g(c, "lnddens_x_child") * h.child)
                    + g(c, "lnjden") * lu[1] + g(c, "lnretden") * lu[2] + g(c, "mix") * lu[3] + g(c, "park") * lu[4];
        }
        return v + c.getOrDefault("lnD", 1.) * lnD
                + aw * (g(c, "accW") + g(c, "accW_x_nocar") * h.nocar)
                + an * (g(c, "accN") + g(c, "accN_x_child") * h.child + g(c, "accN_x_ageU35") * h.aU35 + g(c, "accN_x_age50_64") * h.a50
                        + g(c, "accN_x_age65") * h.a65 + g(c, "accN_x_hhs") * h.hhs5)
                + lncost * (g(c, "lncost") + g(c, "lncost_x_inc") * h.lninc + g(c, "lncost_x_hhs") * h.hhs5)
                + g(c, "sim") * sim;
    }

    /** commute part of the cell utility; sumLog = sum over the workers of ln(1 + t) */
    public static double commute(Map<String, Double> c, HhVars h, double sumLog) {
        return sumLog * (g(c, "commute_log") + g(c, "commute_log_x_inc") * h.lninc);
    }

    /** dwelling utility; type = SILO dwelling type name (SFD is the reference) */
    public static double dwelling(Map<String, Double> c, HhVars h, double cost, double bedrooms, String type, boolean new5) {
        final double b = Math.min(12. * cost / h.inc, 3.);
        final double[] x = {Math.min(b, .3), Math.min(Math.max(b - .3, 0), .2), Math.max(b - .5, 0), Math.log(Math.max(cost, 100)),
                Math.max(0, h.need - bedrooms), Math.max(0, bedrooms - h.need), new5 ? 1 : 0};
        double v = 0;
        for (int i = 0; i < PRICE.length; i++) v += x[i] * (g(c, PRICE[i]) + g(c, PRICE[i] + "_x_lninc") * h.lninc);
        for (String t : DW_TYPES) {
            if (!t.equals(type)) continue;
            v += g(c, t) + g(c, t + "_x_size") * (h.size - 1) + g(c, t + "_x_child") * h.child + g(c, t + "_x_ageU35") * h.aU35
                    + g(c, t + "_x_age50_64") * h.a50 + g(c, t + "_x_age65") * h.a65 + g(c, t + "_x_lninc") * h.lninc;
        }
        return v;
    }

    /** county terms without the inclusive values; t = car time to the county (min; 0 for the current county) */
    public static double countyTerms(Map<String, Double> c, HhVars h, double t, double same, double adj, double sameState, double com,
                                     double growth, double crime) {
        final double d1 = Math.min(t, 20), d2 = Math.min(Math.max(t - 20, 0), 40), d3 = Math.max(t - 60, 0);
        return g(c, "d1") * d1 + d2 * (g(c, "d2") + g(c, "d2_x_lninc") * h.lninc) + d3 * (g(c, "d3") + g(c, "d3_x_lninc") * h.lninc)
                + same * (g(c, "same_region") + g(c, "same_x_age") * (h.ageMax - 50) / 10.) + g(c, "adjacent") * adj
                + g(c, "same_state") * sameState + com * (g(c, "commute_log") + g(c, "commute_log_x_inc") * h.lninc)
                + g(c, "growth") * growth + crime * (g(c, "crime") + g(c, "crime_x_child") * h.child);
    }

    /** full county utility */
    public static double county(Map<String, Double> c, HhVars h, double ivB, double ivA, double t, double same, double adj, double sameState,
                                double com, double growth, double crime) {
        return g(c, "IV_B") * ivB + g(c, "IV_A") * ivA + countyTerms(c, h, t, same, adj, sameState, com, growth, crime);
    }

    /**
     * IV_B by county = ln sum over the county's cells with dwellings of exp(cell utility without the commute).
     * D[z][t] dwellings by zone index and cell type (SFD, SFA, MF, MH); aw/an[z] accessibility of the household's segment;
     * sim[z] share of the zone's households in the household's income group; zoneRegion[z] county index.
     */
    public static double[] ivB(Map<String, Double> c, HhVars h, double[][] D, double[] lnCost, double[] aw, double[] an, double[] sim,
                               int[] zoneRegion, int nRegions) {
        return ivB(c, h, D, lnCost, aw, an, sim, null, zoneRegion, nRegions);
    }

    /** as above with the land-use variables by zone (lu[z] in the order of LU_NAMES; null = none) */
    public static double[] ivB(Map<String, Double> c, HhVars h, double[][] D, double[] lnCost, double[] aw, double[] an, double[] sim,
                               double[][] lu, int[] zoneRegion, int nRegions) {
        final int nz = D.length;
        final double[] mx = new double[nRegions], s = new double[nRegions];
        java.util.Arrays.fill(mx, Double.NEGATIVE_INFINITY);
        final double[] v = new double[nz * 4];
        for (int z = 0; z < nz; z++) for (int t = 0; t < 4; t++) {
            v[z * 4 + t] = D[z][t] > 0 ? cell(c, h, Math.log(D[z][t]), aw[z], an[z], lnCost[z], sim[z], lu == null ? null : lu[z]) : Double.NEGATIVE_INFINITY;
            if (D[z][t] > 0) mx[zoneRegion[z]] = Math.max(mx[zoneRegion[z]], v[z * 4 + t]);
        }
        for (int z = 0; z < nz; z++) for (int t = 0; t < 4; t++)
            if (D[z][t] > 0) s[zoneRegion[z]] += Math.exp(v[z * 4 + t] - mx[zoneRegion[z]]);
        final double[] out = new double[nRegions];
        for (int r = 0; r < nRegions; r++) out[r] = s[r] > 0 ? Math.log(s[r]) + mx[r] : Double.NEGATIVE_INFINITY;
        return out;
    }

    /** IV_A of one county = ln mean over its market dwellings of exp(V_A) */
    public static double ivA(Map<String, Double> c, HhVars h, double[] cost, double[] bedrooms, String[] type, boolean[] new5) {
        if (cost.length == 0) return 0;
        final double[] v = new double[cost.length];
        double m = Double.NEGATIVE_INFINITY;
        for (int i = 0; i < v.length; i++) { v[i] = dwelling(c, h, cost[i], bedrooms[i], type[i], new5[i]); m = Math.max(m, v[i]); }
        double s = 0;
        for (double x : v) s += Math.exp(x - m);
        return Math.log(s / v.length) + m;
    }

    /** coefficient file parameter,estimate (county) or level,parameter,estimate (zone / dwelling: level = zone | dwelling) */
    public static Map<String, Double> read(String file, String level) {
        final Map<String, Double> m = new HashMap<>();
        try (BufferedReader r = new BufferedReader(new FileReader(file))) {
            final String[] hd = r.readLine().split(",");
            int iL = -1, iP = -1, iE = -1;
            for (int i = 0; i < hd.length; i++) {
                final String x = hd[i].trim();
                if (x.equals("level")) iL = i; else if (x.equals("parameter")) iP = i; else if (x.equals("estimate")) iE = i;
            }
            String line;
            while ((line = r.readLine()) != null) {
                if (line.isBlank()) continue;
                final String[] x = line.split(",");
                if (level != null && iL >= 0 && !x[iL].trim().equals(level)) continue;
                m.put(x[iP].trim(), Double.parseDouble(x[iE].trim()));
            }
        } catch (IOException e) {
            throw new RuntimeException("Could not read " + file, e);
        }
        return m;
    }
}
