package de.tum.bgu.msm.data.school;

import de.tum.bgu.msm.schools.School;

import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.FileReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.util.*;
import java.util.zip.GZIPInputStream;

/**
 * Baltimore 2026 (2026-11-18j, school.choice.model = respec1118): the estimated school location choice of
 * side_experiments/respec_2026-11/step_by_step/locations/l10_school.py (final models K-8, high school, college; estimation engine
 * 2_silo/schoolchoice/sc_03_engine.py, full choice set), used by SchoolDataMd.assignSchool for the students assigned during the
 * simulation (the base-year assignment of the input files is kept). Inputs (l11_export_silo.py): school_choice_coef_1118_<seg>.csv,
 * school_choice_records_1118.csv, school_choice_inboundary_1118.csv, school_choice_zone_attr_1118.csv.
 *
 * Utility of zone j for a student of segment k living in zone h (band b: elementary / middle for K-8, high, postsec):
 *   V_hj = mu ln S_hj + b_t t + b_lt ln(1+t) + b_intra [j = h] + b_cc [county differs] + b_cs [state differs]
 *          + b_ccpub [county differs] x public share + b_tXcar0 t car0 + b_tXg1 t g1 + b_tXg4 t g4 + b_cm cm_bj + b_qpub qpub_bj
 *          + b_qnone qnone_bj + b_qpubXg1 qpub_bj g1 + b_own own-race share_bj
 *   S_hj = sum_c exp(g_c) N_c,hj; K-12 components pub_out (weight 1), pub_in, priv with pub_in = min(sum_s a_hs N_s, pub_j) over the
 *   public records s of band b in zone j (a_hs = SABS in-boundary share), pub_out = pub_j - pub_in; college pub4 (weight 1), priv4, cc.
 *   N_s = capacity (enrolment of the band) of the record; public share = (pub_out + pub_in) / (pub_out + pub_in + priv) (K-12 only).
 *   t = car peak minutes (input/skims/auto_peak_time.csv.gz); car0 = household without a car; g1 / g4 = household income < $40k /
 *   >= $125k (2016 $); cm, qpub, qnone fixed zone inputs; own = share of race r among the zone's enrolment of the band: in the
 *   simulation recounted every year from the students assigned in SILO (race of PersonMstm), in the verification the estimation shares.
 * Choice (simulation): zones with a record of the band with capacity > 0; a zone is available while one of its records of the band has a
 * free seat (occupancy < capacity); if no zone has one, all zones (counted as fallback). Zone drawn with P ~ exp(V_hj); record within
 * the zone (records with a free seat, all after the fallback) with probability ~ exp(g_c) N_s (1 + (exp(g_pub_in) - 1) a_hs) for public
 * K-12 records, exp(g_c) N_s otherwise.
 */
public final class SchoolChoiceMd {

    public static final String[] RACES = {"white", "black", "hisp", "other"};   // order of the SILO Race enum (white, black, hispanic, other)
    private static final List<String> TERMS = Arrays.asList("b_t", "b_lt", "b_intra", "b_cc", "b_cs", "b_ccpub", "b_tXcar0", "b_tXg1", "b_tXg4",
            "b_cm", "b_qpub", "b_qnone", "b_qpubXg1", "b_qpubXg4", "b_own");

    /** coefficients of one segment */
    public static final class Coef {
        public double mu = 1;
        public final double[] g = new double[3];   // log weights of the components (index 0 = reference, 0)
        public final Map<String, Double> b = new HashMap<>();
        double b(String k) { return b.getOrDefault(k, 0.); }
    }

    /** segment of a band: 0 K-8 (elementary, middle), 1 high school, 2 college */
    public static int segment(int band) {
        if (band == SchoolDataMd.BAND_HIGH) return 1;
        if (band == SchoolDataMd.BAND_POSTSECONDARY) return 2;
        return 0;
    }

    /** component index of a record: K-12 pub -> 0 (split into pub_out / pub_in), priv -> 2; college pub4 -> 0, priv4 -> 1, cc -> 2 */
    public static int componentIndex(String c) {
        switch (c.trim()) {
            case "pub": case "pub4": return 0;
            case "priv4": return 1;
            case "priv": case "cc": return 2;
            default: throw new IllegalArgumentException("unknown school size component " + c);
        }
    }

    private static List<String[]> csv(String file) throws IOException {
        final List<String[]> out = new ArrayList<>();
        try (BufferedReader r = file.endsWith(".gz") ? new BufferedReader(new InputStreamReader(new GZIPInputStream(new FileInputStream(file))))
                : new BufferedReader(new FileReader(file))) {
            String line;
            while ((line = r.readLine()) != null) {
                if (line.isBlank() || line.startsWith("#")) continue;
                out.add(line.indexOf('"') >= 0 ? splitQuoted(line) : line.split(",", -1));
            }
        }
        return out;
    }

    /** comma split that keeps quoted fields together (zoneSystem.csv has names like "Baltimore City, MD") */
    private static String[] splitQuoted(String line) {
        final List<String> f = new ArrayList<>(); final StringBuilder b = new StringBuilder(); boolean q = false;
        for (int i = 0; i < line.length(); i++) {
            final char ch = line.charAt(i);
            if (ch == '"') q = !q;
            else if (ch == ',' && !q) { f.add(b.toString()); b.setLength(0); }
            else b.append(ch);
        }
        f.add(b.toString());
        return f.toArray(new String[0]);
    }

    private static int col(String[] h, String n) {
        for (int i = 0; i < h.length; i++) if (h[i].trim().equals(n)) return i;
        throw new RuntimeException("column " + n + " missing");
    }

    public static Coef readCoef(String file, int seg) {
        final Coef c = new Coef();
        try {
            final List<String[]> l = csv(file);
            for (String[] x : l.subList(1, l.size())) {
                final String k = x[0].trim(); final double v = Double.parseDouble(x[1].trim());
                if (k.equals("mu_size")) c.mu = v;
                else if (k.equals("g_pub_in") && seg < 2) c.g[1] = v;
                else if (k.equals("g_priv") && seg < 2) c.g[2] = v;
                else if (k.equals("g_priv4") && seg == 2) c.g[1] = v;
                else if (k.equals("g_cc") && seg == 2) c.g[2] = v;
                else if (TERMS.contains(k)) c.b.put(k, v);
                else throw new IllegalArgumentException("unknown school choice coefficient " + k + " in " + file);
            }
        } catch (IOException e) {
            throw new RuntimeException("Could not read " + file, e);
        }
        return c;
    }

    /**
     * Utility V_hj (pure function, shared by the simulation and the verification). n = component sizes of the zone for the home:
     * K-12 {pub_out, pub_in, priv}, college {pub4, priv4, cc}. Returns -infinity when the zone has no enrolment of the band.
     */
    public static double utility(Coef c, boolean k12, double[] n, double t, boolean intra, boolean otherCounty, boolean otherState,
                                 boolean car0, boolean g1, boolean g4, double cm, double qpub, double qnone, double own) {
        final double tot = n[0] + n[1] + n[2];
        if (!(tot > 0)) return Double.NEGATIVE_INFINITY;
        final double s = n[0] + n[1] * Math.exp(c.g[1]) + n[2] * Math.exp(c.g[2]);
        final double pubsh = k12 ? (n[0] + n[1]) / tot : 0;
        return c.mu * Math.log(s + 1e-12) + c.b("b_t") * t + c.b("b_lt") * Math.log1p(t) + c.b("b_intra") * (intra ? 1 : 0)
                + c.b("b_cc") * (otherCounty ? 1 : 0) + c.b("b_cs") * (otherState ? 1 : 0) + c.b("b_ccpub") * (otherCounty ? pubsh : 0)
                + c.b("b_tXcar0") * t * (car0 ? 1 : 0) + c.b("b_tXg1") * t * (g1 ? 1 : 0) + c.b("b_tXg4") * t * (g4 ? 1 : 0)
                + c.b("b_cm") * cm + c.b("b_qpub") * qpub + c.b("b_qnone") * qnone + c.b("b_qpubXg1") * qpub * (g1 ? 1 : 0)
                + c.b("b_qpubXg4") * qpub * (g4 ? 1 : 0) + c.b("b_own") * own;
    }

    // ------------------------------------------------------------------------------------------------ inputs
    private final Coef[] coef = new Coef[3];
    private final Map<Integer, Integer> componentById = new HashMap<>();
    private final Map<Long, Map<Integer, Double>> inBoundary = new HashMap<>();        // (home zone << 4 | band) -> school id -> a
    private final Map<Long, double[]> zoneAttr = new HashMap<>();                       // (zone << 4 | band) -> cm, qpub, qnone, sh_white..sh_other
    private final Map<Integer, int[]> stateCounty = new HashMap<>();                    // zone -> state, county

    /** reads coefficient files (index 0 K-8, 1 high school, 2 college), the record components, SABS shares, zone attributes, zone system */
    public SchoolChoiceMd(String[] coefFiles, String recordsFile, String inBoundaryFile, String zoneAttrFile, String zoneSystemFile) {
        for (int s = 0; s < 3; s++) if (coefFiles[s] != null) coef[s] = readCoef(coefFiles[s], s);
        try {
            List<String[]> l = csv(recordsFile); String[] h = l.get(0);
            int iI = col(h, "id"), iC = col(h, "component");
            for (String[] x : l.subList(1, l.size())) componentById.put(Integer.parseInt(x[iI].trim()), componentIndex(x[iC]));
            l = csv(inBoundaryFile); h = l.get(0);
            int iH = col(h, "home_zone"), iB = col(h, "band"), iS = col(h, "school_id"), iA = col(h, "a");
            for (String[] x : l.subList(1, l.size()))
                inBoundary.computeIfAbsent(key(Integer.parseInt(x[iH].trim()), SchoolDataMd.parseBand(x[iB])), k -> new HashMap<>())
                        .merge(Integer.parseInt(x[iS].trim()), Double.parseDouble(x[iA].trim()), Double::sum);
            l = csv(zoneAttrFile); h = l.get(0);
            final int iZ = col(h, "zone"), iBb = col(h, "band"), iCm = col(h, "cm"), iQ = col(h, "qpub"), iN = col(h, "qnone");
            final int[] iSh = new int[4];
            for (int r = 0; r < 4; r++) iSh[r] = col(h, "sh_" + RACES[r]);
            for (String[] x : l.subList(1, l.size())) {
                final double[] v = new double[7];
                v[0] = Double.parseDouble(x[iCm].trim()); v[1] = Double.parseDouble(x[iQ].trim()); v[2] = Double.parseDouble(x[iN].trim());
                for (int r = 0; r < 4; r++) v[3 + r] = Double.parseDouble(x[iSh[r]].trim());
                zoneAttr.put(key(Integer.parseInt(x[iZ].trim()), SchoolDataMd.parseBand(x[iBb])), v);
            }
            l = csv(zoneSystemFile); h = l.get(0);
            final int iZs = col(h, "ZoneId"), iSt = col(h, "STFIPS"), iCo = col(h, "COUNTYFIPS");
            for (String[] x : l.subList(1, l.size()))
                stateCounty.put(Integer.parseInt(x[iZs].trim()), new int[]{(int) Double.parseDouble(x[iSt].trim()), (int) Double.parseDouble(x[iCo].trim())});
        } catch (IOException e) {
            throw new RuntimeException("Could not read the school choice inputs", e);
        }
    }

    private static long key(int zone, int band) { return ((long) zone << 4) + band; }

    /** component of a record (from the records file); -1 = not in the file */
    public int component(int schoolId) { return componentById.getOrDefault(schoolId, -1); }

    // ------------------------------------------------------------------------------------------------ choice structures
    /** records of one band grouped by zone */
    public static final class Rec {
        final int id, zone, comp; final double cap; final School school;
        public Rec(int id, int zone, int comp, double cap, School school) { this.id = id; this.zone = zone; this.comp = comp; this.cap = cap; this.school = school; }
    }

    private static final class BandSet {
        int[] zones; double[][] n; Rec[][] recs; Map<Integer, Integer> zpos = new HashMap<>();
    }

    private final Map<Integer, BandSet> bands = new HashMap<>();
    private final Map<Long, double[]> raceCount = new HashMap<>();   // (zone << 4 | band) -> students by race (simulation)
    private boolean useFileShares = false;
    public long assigned, fallbackFull, noZone;

    /** (re)builds the zone sets of every band from the records (capacity > 0) */
    public void setRecords(Map<Integer, List<Rec>> recordsByBand) {
        bands.clear();
        for (Map.Entry<Integer, List<Rec>> e : recordsByBand.entrySet()) {
            final TreeMap<Integer, List<Rec>> byZone = new TreeMap<>();
            for (Rec r : e.getValue()) if (r.cap > 0) byZone.computeIfAbsent(r.zone, k -> new ArrayList<>()).add(r);
            final BandSet b = new BandSet(); final int nz = byZone.size();
            b.zones = new int[nz]; b.n = new double[nz][3]; b.recs = new Rec[nz][];
            int i = 0;
            for (Map.Entry<Integer, List<Rec>> z : byZone.entrySet()) {
                b.zones[i] = z.getKey(); b.recs[i] = z.getValue().toArray(new Rec[0]); b.zpos.put(z.getKey(), i);
                for (Rec r : b.recs[i]) b.n[i][r.comp] += r.cap;
                i++;
            }
            bands.put(e.getKey(), b);
        }
    }

    /** simulation: students by zone x band x race (race index 0-3, -1 unknown = not counted) */
    public void setRaceCounts(Map<Long, double[]> counts) { raceCount.clear(); raceCount.putAll(counts); }
    public static long raceKey(int zone, int band) { return key(zone, band); }

    private double own(int zone, int band, int race) {
        if (race < 0 || race > 3) return 0;
        if (useFileShares) { final double[] v = zoneAttr.get(key(zone, band)); return v == null ? 0 : v[3 + race]; }
        final double[] c = raceCount.get(key(zone, band));
        if (c == null) return 0;
        final double tot = c[0] + c[1] + c[2] + c[3];
        return tot > 0 ? c[race] / tot : 0;
    }

    public interface Time { double minutes(int fromZone, int toZone); }

    /** utilities of all zones of the band for the student (index of BandSet.zones), and the in-boundary shares a_hs of the home */
    private double[] utilities(int home, int band, boolean car0, boolean g1, boolean g4, int race, Time tt, BandSet b, Map<Integer, Double> ain) {
        final int seg = segment(band); final boolean k12 = seg < 2; final Coef c = coef[seg];
        final double[] pin = new double[b.zones.length];
        if (k12 && ain != null) {
            for (int i = 0; i < b.zones.length; i++)
                for (Rec r : b.recs[i]) if (r.comp == 0) { final Double a = ain.get(r.id); if (a != null) pin[i] += a * r.cap; }
        }
        final int[] sc = stateCounty.getOrDefault(home, new int[]{-1, -1});
        final double[] v = new double[b.zones.length];
        for (int i = 0; i < b.zones.length; i++) {
            final int j = b.zones[i];
            final double[] n = k12 ? new double[]{b.n[i][0] - Math.min(pin[i], b.n[i][0]), Math.min(pin[i], b.n[i][0]), b.n[i][2]} : b.n[i];
            final int[] scj = stateCounty.getOrDefault(j, new int[]{-2, -2});
            final double[] za = zoneAttr.get(key(j, band));
            v[i] = utility(c, k12, n, tt.minutes(home, j), j == home, sc[1] != scj[1], sc[0] != scj[0], car0, g1, g4,
                    za == null ? 0 : za[0], za == null ? 0 : za[1], za == null ? 0 : za[2], own(j, band, race));
        }
        return v;
    }

    /**
     * Simulation: chooses a school record of the band for a student at home zone home (see the class comment); null when the band has
     * no records. car0 = household without a car, income = household income (2016 $), race 0-3 (-1 unknown).
     */
    public School choose(int home, int band, boolean car0, double income, int race, Time tt, Random rnd) {
        final BandSet b = bands.get(band);
        if (b == null || b.zones.length == 0) { noZone++; return null; }
        final Map<Integer, Double> ain = inBoundary.get(key(home, band));
        final double[] v = utilities(home, band, car0, income < 40000, income >= 125000, race, tt, b, ain);
        final boolean[] free = new boolean[b.zones.length]; boolean any = false;
        for (int i = 0; i < free.length; i++) {
            for (Rec r : b.recs[i]) if (r.school.getOccupancy() < r.school.getCapacity()) { free[i] = true; break; }
            any |= free[i] && v[i] > Double.NEGATIVE_INFINITY;
        }
        if (!any) { fallbackFull++; Arrays.fill(free, true); }
        double m = Double.NEGATIVE_INFINITY;
        for (int i = 0; i < v.length; i++) if (free[i]) m = Math.max(m, v[i]);
        if (m == Double.NEGATIVE_INFINITY) { noZone++; return null; }
        final double[] w = new double[v.length]; double s = 0;
        for (int i = 0; i < v.length; i++) { w[i] = free[i] && v[i] > Double.NEGATIVE_INFINITY ? Math.exp(v[i] - m) : 0; s += w[i]; }
        int zi = pick(w, s, rnd);
        // record within the zone
        final Coef c = coef[segment(band)]; final boolean k12 = segment(band) < 2;
        final Rec[] rs = b.recs[zi]; final double[] rw = new double[rs.length]; double rsum = 0;
        for (int k = 0; k < rs.length; k++) {
            final Rec r = rs[k];
            if (any && r.school.getOccupancy() >= r.school.getCapacity()) continue;
            double x = r.cap * Math.exp(c.g[r.comp]);
            if (k12 && r.comp == 0) { final Double a = ain == null ? null : ain.get(r.id); x = r.cap * (1 + (Math.exp(c.g[1]) - 1) * (a == null ? 0 : a)); }
            rw[k] = x; rsum += x;
        }
        if (!(rsum > 0)) { for (int k = 0; k < rs.length; k++) { rw[k] = rs[k].cap; rsum += rw[k]; } }
        assigned++;
        return rs[pick(rw, rsum, rnd)].school;
    }

    private static int pick(double[] w, double s, Random rnd) {
        double u = rnd.nextDouble() * s; int last = -1;
        for (int i = 0; i < w.length; i++) { if (w[i] <= 0) continue; last = i; u -= w[i]; if (u <= 0) return i; }
        return last;
    }

    // ------------------------------------------------------------------------------------------------ verification
    /**
     * Verification of the utilities against the estimation code (l11_export_silo.py verify):
     *   args: segment (k8|hs|college) coefFile recordsFile inBoundaryFile zoneAttrFile zoneSystemFile carSkim rows.csv out.csv
     *   rows.csv: row,home_zone,band,car0,g,race (g 1-4 income group, race 0-3 or -1); own-race shares from the zone attribute file.
     *   out.csv: row,zone,V for every zone with enrolment of the row's band.
     */
    public static void main(String[] a) throws IOException {
        final int seg = Arrays.asList("k8", "hs", "college").indexOf(a[0]);
        final SchoolChoiceMd m = new SchoolChoiceMd(new String[]{seg == 0 ? a[1] : null, seg == 1 ? a[1] : null, seg == 2 ? a[1] : null}, a[2], a[3], a[4], a[5]);
        m.useFileShares = true;
        final Map<Integer, List<Rec>> byBand = new HashMap<>();
        List<String[]> l = csv(a[2]); String[] h = l.get(0);
        final int iI = col(h, "id"), iZ = col(h, "zone"), iB = col(h, "band"), iC = col(h, "component"), iK = col(h, "capacity");
        for (String[] x : l.subList(1, l.size()))
            byBand.computeIfAbsent(SchoolDataMd.parseBand(x[iB]), k -> new ArrayList<>()).add(new Rec(Integer.parseInt(x[iI].trim()),
                    Integer.parseInt(x[iZ].trim()), componentIndex(x[iC]), Double.parseDouble(x[iK].trim()), null));
        m.setRecords(byBand);
        final Map<Long, Double> skim = new HashMap<>();
        l = csv(a[6]); h = l.get(0);
        final int iF = col(h, "FROM"), iT = col(h, "TO"), iV = col(h, "VALUE");
        for (String[] x : l.subList(1, l.size())) skim.put(((long) Integer.parseInt(x[iF].trim()) << 20) + Integer.parseInt(x[iT].trim()), Double.parseDouble(x[iV].trim()));
        final Time tt = (f, t) -> skim.get(((long) f << 20) + t);
        l = csv(a[7]); h = l.get(0);
        final int rR = col(h, "row"), rH = col(h, "home_zone"), rB = col(h, "band"), rC = col(h, "car0"), rG = col(h, "g"), rRc = col(h, "race");
        try (PrintWriter w = new PrintWriter(a[8])) {
            w.println("row,zone,V");
            for (String[] x : l.subList(1, l.size())) {
                final int home = Integer.parseInt(x[rH].trim()), band = SchoolDataMd.parseBand(x[rB]), g = (int) Double.parseDouble(x[rG].trim());
                final BandSet b = m.bands.get(band);
                final double[] v = m.utilities(home, band, Double.parseDouble(x[rC].trim()) > 0, g == 1, g == 4, (int) Double.parseDouble(x[rRc].trim()), tt, b,
                        m.inBoundary.get(key(home, band)));
                for (int i = 0; i < v.length; i++) if (v[i] > Double.NEGATIVE_INFINITY) w.println(x[rR].trim() + "," + b.zones[i] + "," + v[i]);
            }
        }
    }
}
