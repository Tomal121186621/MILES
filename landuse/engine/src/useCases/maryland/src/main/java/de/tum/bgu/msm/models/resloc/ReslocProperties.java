package de.tum.bgu.msm.models.resloc;

import java.io.FileReader;
import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Properties;

/**
 * Baltimore 2026 (residential location model estimated on Baltimore-region data, 2_silo/resloc/ESTIMATION_REPORT.md):
 * the properties of the estimated model, read from the run's properties file (SiloMstm passes its path), so that siloCore's
 * property modules stay unchanged.
 *
 *   resloc.model                  mstm (default: the inherited MSTM utility scripts) | mnl (the estimated nested model)
 *   resloc.region.coefficients    input/resloc_region_mnl.csv     (parameter,estimate[,robust_se])
 *   resloc.dwelling.coefficients  input/resloc_dwelling_mnl.csv   (level,parameter,estimate[,robust_se]); level = zone | dwelling
 *   resloc.region.attributes      input/resloc_region_attributes.csv  (region,state,school,crime[,growth])
 *   resloc.spec                   record (default: the model of record) | respec (2026-11-09: the re-specified model,
 *                                 ReslocRespecUtility; coefficient files *_respec.csv)
 *   resloc.region.adjacency       respec: county pairs sharing a boundary (region_a,region_b)
 *   resloc.respec.accessibility.file  respec: accessibility of the zone part (pattern with {year}; the multimodal logsum of the
 *                                 estimation); blank = accessibility.logsum.file
 *   resloc.transit.skim           transit door-to-door peak time (FROM,TO,VALUE csv.gz; >= 999 = no path), as in the estimation
 *   resloc.acceptance             satisfaction (default: a searching household moves only if the found dwelling is better than its
 *                                 current one; under mnl compared with V_A + V_B - ln D_zt, otherwise with the satisfaction utility) | none
 *   resloc.move.scale             scale of the gap in the estimated move-or-not decision (default 1)
 *   resloc.move.duration          coefficient of ln(1 + years in the dwelling) (default 0)
 *   resloc.move.reference         kappa: the gap is taken relative to kappa x the gap at the start of the tenure (default 0)
 *   resloc.move.search.size       dwellings sampled per search, K in the log-sum ln K + ln mean exp(.) (default 20)
 *   resloc.tenure.file            years in the dwelling of the base-year households by age (age_from,age_to,dur_from,dur_to,share)
 *   resloc.iv.dwelling.sample     market dwellings per region for the dwelling inclusive value (default 200)
 *   accessibility.model           hansen (default: AccessibilityImpl) | logsum (AccessibilityLogsumMd)
 *   accessibility.logsum.file     path of the logsum accessibility file with {year} for the skim year, e.g.
 *                                 ../../../data/accessibility_{year}.csv (relative paths are relative to base.directory)
 *   accessibility.logsum.car.labels   labels of the car-availability segments, default nocar,carlt,carge
 *                                 (segment = <INCOME GROUP>_<car label>, e.g. LOW_nocar)
 */
public final class ReslocProperties {

    private static Properties p = new Properties();
    private static String baseDirectory = "";

    private ReslocProperties() {}

    public static void initialize(String propertiesFile) {
        Properties q = new Properties();
        try (FileReader r = new FileReader(propertiesFile)) {
            q.load(r);
        } catch (IOException e) {
            throw new RuntimeException("Could not read " + propertiesFile, e);
        }
        p = q;
        baseDirectory = q.getProperty("base.directory", "").trim();
    }

    public static String get(String key, String def) {
        String v = p.getProperty(key);
        return v == null || v.trim().isEmpty() ? def : v.trim();
    }

    public static boolean isMnl() {
        return "mnl".equalsIgnoreCase(get("resloc.model", "mstm"));
    }

    public static boolean isLogsumAccessibility() {
        return "logsum".equalsIgnoreCase(get("accessibility.model", "hansen"));
    }

    public static boolean acceptanceNone() {
        return "none".equalsIgnoreCase(get("resloc.acceptance", "satisfaction"));
    }

    /** absolute path: as given if absolute, else relative to base.directory */
    public static String path(String key, String def) {
        String v = get(key, def);
        if (v == null) return null;
        Path x = Paths.get(v);
        return x.isAbsolute() ? v : Paths.get(baseDirectory).resolve(v).normalize().toString();
    }
}
