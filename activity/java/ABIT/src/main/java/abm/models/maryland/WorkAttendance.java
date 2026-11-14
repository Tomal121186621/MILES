package abm.models.maryland;

import abm.data.pop.Person;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.HashMap;
import java.util.Map;

/**
 * Daily work-attendance sampling (telework/absence correction).
 *
 * LODES anchors workplace ASSIGNMENT (job locations), but not every employed worker
 * physically commutes on a given day. For each mandatory work day, the worker stays
 * home with the usual worked-from-home probability of their home county (ACS PUMS
 * 2019-2023, weighted; see wfh_attendance CSV: countyfips,p).
 *
 * Enabled only when the property "wfh.attendance.file" is set; otherwise inert.
 * County of residence resolves through the existing zone.attributes.file (id,countyfips).
 */
public class WorkAttendance {

    private static volatile boolean initialized = false;
    private static Map<Integer, Double> zoneStayHomeP = null;

    private static synchronized void init() {
        if (initialized) return;
        initialized = true;
        try {
            String wfhFile = AbitResources.instance.getString("wfh.attendance.file");
            if (wfhFile == null || wfhFile.isBlank()) return;
            String zoneFile = AbitResources.instance.getString("zone.attributes.file");
            double dayFactor = 1.0;
            try { dayFactor = AbitResources.instance.getDouble("wfh.attendance.dayfactor", 1.0); } catch (Exception ignored) {}
            final double df = dayFactor;
            Map<Integer, Double> countyP = new HashMap<>();
            try (BufferedReader r = new BufferedReader(new FileReader(wfhFile))) {
                String line = r.readLine();               // header: countyfips,p
                while ((line = r.readLine()) != null) {
                    String[] t = line.split(",");
                    // day-level attendance: usual-WFH floor scaled by the calibrated
                    // day factor (hybrid workers' home days), capped at 0.6
                    double p = Math.min(0.6, df * Double.parseDouble(t[1].trim()));
                    countyP.put(Integer.parseInt(t[0].trim()), p);
                }
            }
            Map<Integer, Double> zp = new HashMap<>();
            try (BufferedReader r = new BufferedReader(new FileReader(zoneFile))) {
                String[] hdr = r.readLine().split(",");
                int idIdx = -1, ctyIdx = -1;
                for (int i = 0; i < hdr.length; i++) {
                    if (hdr[i].equalsIgnoreCase("id")) idIdx = i;
                    if (hdr[i].equalsIgnoreCase("countyfips")) ctyIdx = i;
                }
                String line;
                while ((line = r.readLine()) != null) {
                    String[] t = line.split(",");
                    Double p = countyP.get(Integer.parseInt(t[ctyIdx].trim()));
                    if (p != null) zp.put(Integer.parseInt(t[idIdx].trim()), p);
                }
            }
            zoneStayHomeP = zp;
            System.out.println("WorkAttendance: enabled for " + zp.size() + " zones ("
                    + countyP.size() + " counties)");
        } catch (Exception e) {
            System.err.println("WorkAttendance: disabled (" + e.getMessage() + ")");
            zoneStayHomeP = null;
        }
    }

    /** True if this worker stays home for this work day (sampled per work day). */
    public static boolean staysHome(Person person) {
        if (!initialized) init();
        if (zoneStayHomeP == null) return false;
        try {
            int zone = person.getHousehold().getLocation().getZoneId();
            Double p = zoneStayHomeP.get(zone);
            return p != null && AbitUtils.getRandomObject().nextDouble() < p;
        } catch (Exception e) {
            return false;
        }
    }
}
