package de.tum.bgu.msm.data.dwelling;

import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;

/**
 * Baltimore 2026-11-17: structural vacancy rate by region (property structural.vacancy.file: region,rate). The dwelling-type defaults
 * (SFD/SFA/MH 3 %, MF234 4 %, MF5plus 5 %) lie above the vacancy of most Maryland counties in the 2016 base stock (1.5-2.7 % in the
 * suburbs, 5.8 % in Baltimore City, 12-19 % in the seasonal counties), so the pricing model raised prices every year wherever the base
 * vacancy was below the default and the search availability of ReslocModel steered movers to the regions above it. The file holds
 * the vacancy of each region in the 2016 base stock (base year taken as the market equilibrium; no free parameter). Without the file,
 * or for a region missing from it, the dwelling-type default applies (the model of record unchanged).
 */
public final class StructuralVacancy {
    private static final Logger logger = LogManager.getLogger(StructuralVacancy.class);
    private static final Map<Integer, Float> byRegion = new HashMap<>();

    private StructuralVacancy() {}

    public static void load(String file) {
        byRegion.clear();
        try (BufferedReader r = new BufferedReader(new FileReader(file))) {
            String[] h = r.readLine().split(","); int iR = Arrays.asList(h).indexOf("region"), iV = Arrays.asList(h).indexOf("rate");
            String line;
            while ((line = r.readLine()) != null) {
                if (line.isBlank()) continue;
                String[] f = line.split(","); byRegion.put(Integer.parseInt(f[iR].trim()), Float.parseFloat(f[iV].trim()));
            }
        } catch (IOException e) { throw new RuntimeException("Could not read structural vacancy " + file, e); }
        logger.info("Structural vacancy by region: " + byRegion.size() + " regions from " + file + " (pricing and residential search availability)");
    }

    public static float rate(int region, DwellingType type) {
        final Float v = byRegion.get(region);
        return v != null ? v : type.getStructuralVacancyRate();
    }
}
