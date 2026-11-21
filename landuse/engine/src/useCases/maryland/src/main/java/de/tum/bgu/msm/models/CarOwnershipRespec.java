package de.tum.bgu.msm.models;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.io.PrintWriter;
import java.util.*;

/**
 * Baltimore 2026 (2026-11-09, car.ownership.spec = respec): utilities of the re-specified car-ownership MNL
 * (side_experiments/respec_2026-11/step_by_step/car_ownership, s07_sequence.py final model; reference 0 cars), as a pure function
 * shared by CarOwnershipModelMd and the verification main().
 *
 * U_a = asc_a + b_a' x for a = 1, 2, 3+, x:
 *   workers            employed persons (PUMS ESR 1, 2, 4, 5; SILO Occupation.EMPLOYED), at most 6
 *   nonworking_adults  persons aged 16+ minus workers (workers capped at the persons 16+), at most 6
 *   children           persons under 16, at most 6
 *   single_person      one-person household
 *   sfd, multifamily   dwelling type single-family detached; multifamily (SILO MF234, MF5plus); reference SFA and MH / other
 *   bedrooms           bedrooms, at most 5
 *   ln_density         ln dwelling density of the PUMA (units per km2)
 *   acc_gain           non-work logsum accessibility of the household's income group with a car (carge) minus without (nocar),
 *                      housing-unit weighted mean over the PUMA's zones
 *   inc_lt25 .. inc_gt100  ln(max(income, 5000) / 50000), piecewise linear, bends at $25k, $50k, $100k (2016 $)
 *   age10, age10_sq    (age - 45) / 10 and its square; the estimation uses the PUMS householder (RELP 0), the engine the oldest
 *                      member (SILO stores no householder)
 *   inc_x_dens         ln income x (ln_density - c), c = estimation-sample mean of ln_density (coefficient file: alternative 0,
 *                      variable ln_density_centre)
 *   p16_2, p16_3, p16_4p   (2026-11-16a) persons 16+ = 2, 3, 4+ (reference 0-1), alternative-specific dummies replacing nonworking_adults in
 *                      car_ownership_coefficients_respec7.csv; a coefficient file without them (respec) scores as before
 * Coefficient file: alternative,variable,value (alternative 1, 2, 3 = 3+ cars; 0 = constants of the specification).
 */
public final class CarOwnershipRespec {

    private CarOwnershipRespec() {}

    public static final String[] VARS = {"workers", "nonworking_adults", "children", "single_person", "sfd", "multifamily", "bedrooms",
            "ln_density", "acc_gain", "inc_lt25", "inc_25_50", "inc_50_100", "inc_gt100", "age10", "age10_sq", "inc_x_dens",
            "p16_2", "p16_3", "p16_4p"};   // 2026-11-16a: persons 16+ = 2, 3, 4+ (reference 0-1); absent in a coefficient file = 0
    private static final double K0 = Math.log(0.5), K1 = 0, K2 = Math.log(2.0);

    /** variable vector in the order of VARS */
    public static double[] vars(int workers, int persons16, int children, int size, double income, int age, String dwellingType, int bedrooms,
                                double lnDensity, double accGain, double densityCentre) {
        final double w = Math.min(workers, 6), na = Math.min(persons16 - Math.min(workers, persons16), 6), ch = Math.min(children, 6);
        final double x = Math.log(Math.max(income, 5000) / 50000.);
        final double a10 = (age - 45) / 10.;
        return new double[]{w, na, ch, size == 1 ? 1 : 0, "SFD".equals(dwellingType) ? 1 : 0,
                ("MF234".equals(dwellingType) || "MF5plus".equals(dwellingType)) ? 1 : 0, Math.min(bedrooms, 5), lnDensity, accGain,
                Math.min(x, K0), Math.min(Math.max(x - K0, 0), K1 - K0), Math.min(Math.max(x - K1, 0), K2 - K1), Math.max(x - K2, 0),
                a10, a10 * a10, x * (lnDensity - densityCentre),
                persons16 == 2 ? 1 : 0, persons16 == 3 ? 1 : 0, persons16 >= 4 ? 1 : 0};
    }

    /** utilities of 1, 2, 3+ cars (0 cars = 0) */
    public static double[] utilities(Map<Integer, Map<String, Double>> coef, double[] x) {
        final double[] u = new double[3];
        for (int a = 1; a <= 3; a++) {
            final Map<String, Double> c = coef.getOrDefault(a, Map.of());
            double v = c.getOrDefault("asc", 0.);
            for (int k = 0; k < VARS.length; k++) v += c.getOrDefault(VARS[k], 0.) * x[k];
            u[a - 1] = v;
        }
        return u;
    }

    /** verification: in.csv (id,workers,persons16,children,size,income,age,type,bedrooms,ln_density,acc_gain) -> id,alt,V */
    public static void main(String[] a) throws IOException {
        final Map<Integer, Map<String, Double>> coef = new HashMap<>();
        try (BufferedReader r = new BufferedReader(new FileReader(a[0]))) {
            r.readLine(); String line;
            while ((line = r.readLine()) != null) {
                if (line.isBlank()) continue;
                final String[] x = line.split(",");
                coef.computeIfAbsent(Integer.parseInt(x[0].trim()), k -> new HashMap<>()).put(x[1].trim(), Double.parseDouble(x[2].trim()));
            }
        }
        final double centre = coef.get(0).get("ln_density_centre");
        try (BufferedReader r = new BufferedReader(new FileReader(a[1])); PrintWriter w = new PrintWriter(a[2])) {
            final List<String> h = Arrays.asList(r.readLine().split(","));
            w.println("id,alt,V"); String line;
            while ((line = r.readLine()) != null) {
                final String[] x = line.split(",");
                final double[] v = vars((int) Double.parseDouble(x[h.indexOf("workers")]), (int) Double.parseDouble(x[h.indexOf("persons16")]),
                        (int) Double.parseDouble(x[h.indexOf("children")]), (int) Double.parseDouble(x[h.indexOf("size")]), Double.parseDouble(x[h.indexOf("income")]),
                        (int) Double.parseDouble(x[h.indexOf("age")]), x[h.indexOf("type")], (int) Double.parseDouble(x[h.indexOf("bedrooms")]),
                        Double.parseDouble(x[h.indexOf("ln_density")]), Double.parseDouble(x[h.indexOf("acc_gain")]), centre);
                final double[] u = utilities(coef, v);
                for (int k = 0; k < 3; k++) w.println(x[h.indexOf("id")] + "," + (k + 1) + "," + u[k]);
            }
        }
    }
}
