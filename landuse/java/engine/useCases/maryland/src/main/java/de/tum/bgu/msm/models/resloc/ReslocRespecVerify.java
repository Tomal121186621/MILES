package de.tum.bgu.msm.models.resloc;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.io.PrintWriter;
import java.util.*;

/**
 * Baltimore 2026 (2026-11-09): verification harness of the re-specified residential location model. Evaluates the engine's
 * utility functions (ReslocRespecUtility, the code ReslocModel calls under resloc.spec = respec) on choice situations exported
 * from the estimation data, for comparison with the estimation utilities X beta (side_experiments/respec_2026-11/engine_check).
 *   zone     <zone/dwelling coef file> <in.csv> <out.csv>   in: id,alt,income,size,child,age_max,nocar,lnD,aw,an,lncost,sim,comlog
 *   dwelling <zone/dwelling coef file> <in.csv> <out.csv>   in: id,alt,income,size,child,age_max,cost,bedrooms,type,new5
 *   county   <county coef file> <in.csv> <out.csv>          in: id,alt,income,size,child,age_max,ivB,ivA,t,same,adj,same_state,com,growth,crime
 *   ivb      <zone/dwelling coef file> <hh.csv> <zones.csv> <acc.csv> <out.csv>
 *            hh: id,income,size,child,age_max,nocar,segment,group (0-3); zones: zone,D_SFD,D_SFA,D_MF,D_MH,lncost,sh_LOW..sh_VERY_HIGH,region
 *   iva      <zone/dwelling coef file> <hh.csv> <pool.csv> <out.csv>   pool: region,cost,bedrooms,type,new5
 * Output: id,alt,V (ivb / iva: id,region,V).
 */
public final class ReslocRespecVerify {

    private ReslocRespecVerify() {}

    private static List<Map<String, String>> csv(String f) throws IOException {
        final List<Map<String, String>> out = new ArrayList<>();
        try (BufferedReader r = new BufferedReader(new FileReader(f))) {
            final String[] h = r.readLine().split(",");
            String line;
            while ((line = r.readLine()) != null) {
                if (line.isBlank()) continue;
                final String[] x = line.split(",", -1);
                final Map<String, String> m = new HashMap<>();
                for (int i = 0; i < h.length; i++) m.put(h[i].trim(), x[i].trim());
                out.add(m);
            }
        }
        return out;
    }

    private static double d(Map<String, String> m, String k) { return Double.parseDouble(m.get(k)); }

    private static ReslocRespecUtility.HhVars hh(Map<String, String> m) {
        return new ReslocRespecUtility.HhVars(d(m, "income"), (int) d(m, "size"), d(m, "child") > 0, (int) d(m, "age_max"),
                m.containsKey("nocar") && d(m, "nocar") > 0);
    }

    public static void main(String[] a) throws IOException {
        final String mode = a[0];
        switch (mode) {
            case "zone": {
                final Map<String, Double> c = ReslocRespecUtility.read(a[1], "zone");
                try (PrintWriter w = new PrintWriter(a[3])) {
                    w.println("id,alt,V");
                    for (Map<String, String> m : csv(a[2])) {
                        final ReslocRespecUtility.HhVars h = hh(m);
                        final double[] lu = m.containsKey("lnddens") ? new double[]{d(m, "lnddens"), d(m, "lnjden"), d(m, "lnretden"), d(m, "mix"), d(m, "park")} : null;
                        final double v = ReslocRespecUtility.cell(c, h, d(m, "lnD"), d(m, "aw"), d(m, "an"), d(m, "lncost"), d(m, "sim"), lu)
                                + ReslocRespecUtility.commute(c, h, d(m, "comlog"));
                        w.println(m.get("id") + "," + m.get("alt") + "," + v);
                    }
                }
                break;
            }
            case "dwelling": {
                final Map<String, Double> c = ReslocRespecUtility.read(a[1], "dwelling");
                try (PrintWriter w = new PrintWriter(a[3])) {
                    w.println("id,alt,V");
                    for (Map<String, String> m : csv(a[2])) {
                        final double v = ReslocRespecUtility.dwelling(c, hh(m), d(m, "cost"), d(m, "bedrooms"), m.get("type"), d(m, "new5") > 0);
                        w.println(m.get("id") + "," + m.get("alt") + "," + v);
                    }
                }
                break;
            }
            case "county": {
                final Map<String, Double> c = ReslocRespecUtility.read(a[1], null);
                try (PrintWriter w = new PrintWriter(a[3])) {
                    w.println("id,alt,V");
                    for (Map<String, String> m : csv(a[2])) {
                        final double v = ReslocRespecUtility.county(c, hh(m), d(m, "ivB"), d(m, "ivA"), d(m, "t"), d(m, "same"), d(m, "adj"),
                                d(m, "same_state"), d(m, "com"), d(m, "growth"), d(m, "crime"));
                        w.println(m.get("id") + "," + m.get("alt") + "," + v);
                    }
                }
                break;
            }
            case "ivb": {
                final Map<String, Double> c = ReslocRespecUtility.read(a[1], "zone");
                final List<Map<String, String>> zs = csv(a[3]);
                final int nz = zs.size();
                final Map<Integer, Integer> zi = new HashMap<>();
                final TreeSet<Integer> regs = new TreeSet<>();
                for (Map<String, String> m : zs) regs.add((int) d(m, "region"));
                final List<Integer> rl = new ArrayList<>(regs);
                final double[][] D = new double[nz][4]; final double[] lnc = new double[nz]; final double[][] sh = new double[nz][4]; final int[] zr = new int[nz];
                final boolean hasLu = zs.get(0).containsKey("lnddens"); final double[][] lu = hasLu ? new double[nz][5] : null;
                final String[] T = {"SFD", "SFA", "MF", "MH"}, G = {"LOW", "MEDIUM", "HIGH", "VERY_HIGH"};
                for (int i = 0; i < nz; i++) {
                    final Map<String, String> m = zs.get(i);
                    zi.put((int) d(m, "zone"), i);
                    for (int t = 0; t < 4; t++) D[i][t] = d(m, "D_" + T[t]);
                    for (int g = 0; g < 4; g++) sh[i][g] = d(m, "sh_" + G[g]);
                    lnc[i] = d(m, "lncost"); zr[i] = rl.indexOf((int) d(m, "region"));
                    if (hasLu) for (int k = 0; k < 5; k++) lu[i][k] = d(m, ReslocRespecUtility.LU_NAMES[k]);
                }
                final Map<String, double[]> acc = new HashMap<>();
                for (Map<String, String> m : csv(a[4])) {
                    final Integer z = zi.get((int) d(m, "zone"));
                    if (z == null) continue;
                    acc.computeIfAbsent(m.get("segment") + "|" + m.get("purpose"), k -> new double[nz])[z] = d(m, "A");
                }
                try (PrintWriter w = new PrintWriter(a[5])) {
                    w.println("id,region,V");
                    for (Map<String, String> m : csv(a[2])) {
                        final int g = (int) d(m, "group");
                        final double[] sim = new double[nz];
                        for (int z = 0; z < nz; z++) sim[z] = sh[z][g];
                        final double[] iv = ReslocRespecUtility.ivB(c, hh(m), D, lnc, acc.get(m.get("segment") + "|work"), acc.get(m.get("segment") + "|nonwork"),
                                sim, lu, zr, rl.size());
                        for (int r = 0; r < iv.length; r++) w.println(m.get("id") + "," + rl.get(r) + "," + iv[r]);
                    }
                }
                break;
            }
            case "iva": {
                final Map<String, Double> c = ReslocRespecUtility.read(a[1], "dwelling");
                final TreeMap<Integer, List<Map<String, String>>> pool = new TreeMap<>();
                for (Map<String, String> m : csv(a[3])) pool.computeIfAbsent((int) d(m, "region"), k -> new ArrayList<>()).add(m);
                try (PrintWriter w = new PrintWriter(a[4])) {
                    w.println("id,region,V");
                    for (Map<String, String> m : csv(a[2])) {
                        final ReslocRespecUtility.HhVars h = hh(m);
                        for (Map.Entry<Integer, List<Map<String, String>>> e : pool.entrySet()) {
                            final List<Map<String, String>> l = e.getValue(); final int n = l.size();
                            final double[] cost = new double[n], bed = new double[n]; final String[] ty = new String[n]; final boolean[] nw = new boolean[n];
                            for (int i = 0; i < n; i++) { cost[i] = d(l.get(i), "cost"); bed[i] = d(l.get(i), "bedrooms"); ty[i] = l.get(i).get("type"); nw[i] = d(l.get(i), "new5") > 0; }
                            w.println(m.get("id") + "," + e.getKey() + "," + ReslocRespecUtility.ivA(c, h, cost, bed, ty, nw));
                        }
                    }
                }
                break;
            }
            default:
                throw new IllegalArgumentException("mode " + mode);
        }
    }
}
