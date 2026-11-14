package abm.io.input;

import abm.data.DataSet;
import abm.data.geo.*;
import abm.data.pop.*;
import abm.data.travelInformation.MitoBasedTravelDistances;
import abm.data.travelInformation.MitoBasedTravelTimes;
import abm.data.plans.Mode;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;
import de.tum.bgu.msm.data.person.Disability;
import de.tum.bgu.msm.data.person.Gender;
import de.tum.bgu.msm.data.person.Occupation;
import de.tum.bgu.msm.data.travelTimes.SkimTravelTimes;
import org.apache.log4j.Logger;

import java.io.BufferedReader;
import java.io.FileReader;
import java.util.*;

/**
 * Level-of-service reader for the Maryland ABIT scenario. Loads:
 *  - the MSTM zone system (id + centroid coords + RegioStaR/BBSR crosswalk + area) from zone_attributes.csv,
 *  - real OMX car time + distance skims (zone-indexed) as ABIT travel times/distances,
 *  - a county-subset of the SILO calib5 population (hh/pp/jj/dd) with real home/job zones & coords,
 *  - household economic status (replicates EconomicStatusReader) and zone attraction sizes.
 * Designed to feed {@link abm.models.ModelSetupMaryland} (RTS-empirical daily models).
 */
public class MarylandLosDataReader implements DataReaderManager {

    private static final Logger logger = Logger.getLogger(MarylandLosDataReader.class);
    private final Random rnd = AbitUtils.getRandomObject();

    private final Map<Integer, double[]> zoneXY = new HashMap<>();
    private DataSet ds;

    // ---- workplace gravity (RTS HBW Tanner friction) ----
    private int[] workDestZones;               // candidate destination zones (jobs > 0)
    private double[] workDestAttr;             // job attraction per candidate
    private final Map<Integer, double[]> workCumCache = new HashMap<>();   // homeZone -> cumulative weights
    private final Map<Integer, Integer> reassignedWorkZone = new HashMap<>();  // personId -> LODES-calibrated work zone
    private final Map<Integer, int[]> zoneJobCounts = new HashMap<>();        // zone -> {all, retail, office, other} jobs of the full job file
    private double bt = -0.0274684, blt = -1.0998989;   // RTS HBW b_time, b_logtime
    private double eduMeanKm = 2.30 * 1.60934 * 0.65;  // RTS EDUCATION median 2.3mi -> exp mean
    private double workLongPen = 0.046, workLongT0 = 12;  // long-trip penalty (min); relaxed 0.065->0.046 so the
                                                          // home-based commute mean rises ~10.7->~12.8 mi to match
                                                          // RTS HBW (12.3-12.9); was over-decaying the long tail.
    private final Map<Integer, MicroscopicLocation> zoneLocCache = new HashMap<>();
    private int[] allZones;

    // ---- schools (stage 2b, 2026-10-21): records of schools.file (2_silo/input/schools_<year>.csv, one record per
    // school and grade band; columns id,zone,type,capacity,occupancy,coordX,coordY,startTime,duration,band,...);
    // a student points at a record through the schoolId column of the SILO person file (-1 none, -2 student
    // without a record -> nearest school of the age band by car skim, the rule of SILO SchoolDataMd). ----
    private static final String[] BANDS = {"elementary", "middle", "high", "postsec"};
    private final Map<String, List<School>> schoolsByBand = new HashMap<>();
    private final Map<Integer, Integer> schoolOccupancy = new HashMap<>();     // school id -> students assigned by SILO
    private final Map<String, School> nearestSchoolCache = new HashMap<>();   // "zone|band" -> school
    private boolean schoolsLoaded = false;

    @Override
    public DataSet readData() {
        DataSet dataSet = new DataSet();
        this.ds = dataSet;
        readZones(dataSet);
        readSkims(dataSet);
        readSchools(dataSet);
        loadFrictionParams();
        computeJobAttraction();

        String county = AbitResources.instance.getString("county.fips");
        int maxHh = AbitResources.instance.getInt("max.households", 50000);

        Map<Integer, Integer> hhZone = readDwellingsForCounty(dataSet, county, maxHh);
        Map<Integer, Integer> hhAutos = readHouseholdAutos(hhZone.keySet());
        buildHouseholds(dataSet, hhZone, hhAutos);
        readPersonsAndJobs(dataSet, hhZone.keySet());

        new EconomicStatusReader(dataSet).read();
        populateZones(dataSet);

        logger.info("Maryland LOS dataset: zones=" + dataSet.getZones().size()
                + " households=" + dataSet.getHouseholds().size()
                + " persons=" + dataSet.getPersons().size()
                + " jobs=" + dataSet.getJobs().size()
                + " schools=" + dataSet.getSchools().size());
        return dataSet;
    }

    private void readZones(DataSet dataSet) {
        String f = AbitResources.instance.getString("zone.attributes.file");
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String[] h = br.readLine().split(",");
            int iId = idx(h, "id"), iX = idx(h, "x"), iY = idx(h, "y");
            int iR2 = idx(h, "regioStaR2"), iR7 = idx(h, "regioStaR7"), iG5 = idx(h, "regStaRGe5");
            int iBb = idx(h, "bbsr"), iA = idx(h, "area_km2");
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                int id = Integer.parseInt(r[iId].trim());
                Zone z = new Zone(id);
                z.setRegioStaR2Type(RegioStaR2.valueOf(Integer.parseInt(r[iR2].trim())));
                z.setRegioStaR7Type(RegioStaR7.valueOf(Integer.parseInt(r[iR7].trim())));
                z.setRegioStaRGem5Type(RegioStaRGem5.valueOf(Integer.parseInt(r[iG5].trim())));
                z.setAreaType1(BBSRType.valueOf(Integer.parseInt(r[iBb].trim())));
                z.setAreaKm2(Double.parseDouble(r[iA].trim()));
                z.setDistToRail_meter(1000L);
                double zx = Double.parseDouble(r[iX].trim()), zy = Double.parseDouble(r[iY].trim());
                z.setAttribute("x", zx);
                z.setAttribute("y", zy);
                dataSet.getZones().put(id, z);
                zoneXY.put(id, new double[]{zx, zy});
            }
        } catch (Exception e) {
            throw new RuntimeException("readZones failed for " + f, e);
        }
        allZones = dataSet.getZones().keySet().stream().mapToInt(Integer::intValue).toArray();
        logger.info("Loaded " + dataSet.getZones().size() + " zones with centroids + region crosswalk");
    }

    /** Baltimore 2026: skims may be gzipped CSV (FROM,TO,VALUE), read by the pure-Java reader; the OMX reader needs an x86-64 HDF5
     *  native library that an arm64 JVM cannot load. The file type is decided by the file name. */
    private void readSkimAny(SkimTravelTimes tt, String mode, String file, String matrix, double factor, DataSet dataSet) {
        if (file != null && file.endsWith(".csv.gz")) tt.readSkimFromCsvGz(mode, file, factor, dataSet.getZones().values());
        else tt.readSkim(mode, file, matrix, factor);
    }

    private void readSkims(DataSet dataSet) {
        try {
            SkimTravelTimes tt = new SkimTravelTimes();
            // Congested-skim feedback: prefer abit.skim.traveltime.file (the working/congested skim the
            // feedback loop rewrites each iteration); fall back to the free-flow car.time.omx.file.
            String timeFile = AbitResources.instance.getString("abit.skim.traveltime.file");
            if (timeFile == null) timeFile = AbitResources.instance.getString("car.time.omx.file");
            String timeMat = AbitResources.instance.getString("car.time.omx.matrix");
            // traveltime_auto.omx is already in MINUTES -> factor 1.0 (not 1/60).
            // load under every mode name so PlanTools never hits a missing skim.
            for (Mode m : Mode.values()) {
                readSkimAny(tt, m.toString(), timeFile, timeMat, 1.0, dataSet);
            }
            // real transit time skims for the mode-choice generalized cost, if provided
            String busFile = AbitResources.instance.getString("bus.time.omx.file");
            if (busFile != null) readSkimAny(tt, Mode.BUS.toString(), busFile,
                    AbitResources.instance.getString("bus.time.omx.matrix"), 1.0, dataSet);
            String trainFile = AbitResources.instance.getString("train.time.omx.file");
            if (trainFile != null) {
                readSkimAny(tt, Mode.TRAIN.toString(), trainFile, AbitResources.instance.getString("train.time.omx.matrix"), 1.0, dataSet);
                readSkimAny(tt, Mode.TRAM_METRO.toString(), trainFile, AbitResources.instance.getString("train.time.omx.matrix"), 1.0, dataSet);
            }
            dataSet.setTravelTimes(new MitoBasedTravelTimes(tt));

            SkimTravelTimes dist = new SkimTravelTimes();
            String distFile = AbitResources.instance.getString("car.dist.omx.file");
            String distMat = AbitResources.instance.getString("car.dist.omx.matrix");
            readSkimAny(dist, Mode.UNKNOWN.toString(), distFile, distMat, 1., dataSet);
            dataSet.setTravelDistances(new MitoBasedTravelDistances(dist));
            logger.info("Loaded real OMX skims: time=" + timeFile + " dist=" + distFile);
        } catch (Exception e) {
            throw new RuntimeException("readSkims failed", e);
        }
    }

    /** Reads schools.file into the data set (same columns as the generic {@link SchoolReader}; startTime and duration are
     *  seconds in the file and minutes in {@link School}) plus the grade band of each record. Without the property the
     *  legacy placeholder (one random school per student) stays in force, with a warning. */
    private void readSchools(DataSet dataSet) {
        String f = AbitResources.instance.getString("schools.file");
        if (f == null) {
            logger.warn("schools.file not set: students get a placeholder school at an RTS-distance-drawn zone (no EDUCATION tours)");
            return;
        }
        // the school file is EPSG:26918 (SILO, 2_silo/input/zones.prj); this reader's coordinates (zone_attributes.csv,
        // home and job micro-locations, the MATSim export) are EPSG:26985, so the school coordinates are reprojected
        String crsIn = AbitResources.instance.getString("schools.crs"), crsOut = AbitResources.instance.getString("zone.crs");
        if (crsIn == null) crsIn = "EPSG:26918";
        if (crsOut == null) crsOut = "EPSG:26985";
        org.matsim.core.utils.geometry.CoordinateTransformation ct = crsIn.equalsIgnoreCase(crsOut) ? null
                : org.matsim.core.utils.geometry.transformations.TransformationFactory.getCoordinateTransformation(crsIn, crsOut);
        int dropped = 0;
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String[] h = br.readLine().split(",");
            int iId = idx(h, "id"), iZone = idx(h, "zone"), iType = idx(h, "type"), iCap = idx(h, "capacity"),
                    iOcc = idx(h, "occupancy"), iX = idx(h, "coordX"), iY = idx(h, "coordY"),
                    iStart = idx(h, "startTime"), iDur = idx(h, "duration");
            int iBand = -1;
            for (int i = 0; i < h.length; i++) if (strip(h[i]).equalsIgnoreCase("band")) iBand = i;
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                int zone = Integer.parseInt(r[iZone].trim());
                Zone z = dataSet.getZones().get(zone);
                if (z == null) { dropped++; continue; }
                int id = Integer.parseInt(r[iId].trim());
                String type = strip(r[iType]);
                double x = Double.parseDouble(r[iX].trim()), y = Double.parseDouble(r[iY].trim());
                if (ct != null) {
                    org.matsim.api.core.v01.Coord c = ct.transform(new org.matsim.api.core.v01.Coord(x, y));
                    x = c.getX(); y = c.getY();
                }
                MicroscopicLocation loc = new MicroscopicLocation(x, y);
                loc.setZone(z);
                School s = new School(id, type, Integer.parseInt(r[iCap].trim()), Integer.parseInt(r[iOcc].trim()), loc,
                        (int) (Double.parseDouble(r[iStart].trim()) / 60.), (int) (Double.parseDouble(r[iDur].trim()) / 60.));
                dataSet.getSchools().put(id, s);
                schoolOccupancy.put(id, Integer.parseInt(r[iOcc].trim()));
                // band: column if present, else the SILO type (1 elementary, 2 middle+high, 3 post-secondary)
                String band = iBand >= 0 ? strip(r[iBand]).toLowerCase() : null;
                if (band == null || band.isEmpty()) {
                    if (type.equals("1")) schoolsByBand.computeIfAbsent("elementary", k -> new ArrayList<>()).add(s);
                    else if (type.equals("3")) schoolsByBand.computeIfAbsent("postsec", k -> new ArrayList<>()).add(s);
                    else { schoolsByBand.computeIfAbsent("middle", k -> new ArrayList<>()).add(s); schoolsByBand.computeIfAbsent("high", k -> new ArrayList<>()).add(s); }
                } else {
                    schoolsByBand.computeIfAbsent(band, k -> new ArrayList<>()).add(s);
                }
            }
        } catch (Exception e) {
            throw new RuntimeException("readSchools failed for " + f, e);
        }
        schoolsLoaded = true;
        StringBuilder sb = new StringBuilder();
        for (String b : BANDS) sb.append(' ').append(b).append('=').append(schoolsByBand.getOrDefault(b, Collections.emptyList()).size());
        logger.info("Schools: " + dataSet.getSchools().size() + " records from " + f + " (" + dropped + " dropped, zone not in zone system; coordinates "
                + crsIn + (ct == null ? "" : " -> " + crsOut) + "); by band" + sb);
    }

    /** Age band of a student, the bands of SILO's SchoolDataMd / assign_students.py. */
    public static String bandOf(int age) {
        return age <= 10 ? "elementary" : age <= 13 ? "middle" : age <= 17 ? "high" : "postsec";
    }

    /** Nearest school of the band from the home zone by peak car time (straight-line at 30 km/h where the skim has no
     *  value), larger capacity first on ties; cached per zone and band. Students whose schoolId is -2 or unknown. */
    private School nearestSchool(int homeZone, String band) {
        return nearestSchoolCache.computeIfAbsent(homeZone + "|" + band, key -> {
            List<School> cands = schoolsByBand.getOrDefault(band, Collections.emptyList());
            MicroscopicLocation home = zoneCentroid(homeZone);
            School best = null; double bestT = Double.MAX_VALUE;
            for (School s : cands) {
                double t = ds.getTravelTimes().getTravelTimeInMinutes(home, s.getLocation(), Mode.CAR_DRIVER, 8 * 60);
                if (!(t > 0) || Double.isInfinite(t)) {
                    double[] a = zoneXY.getOrDefault(homeZone, new double[]{0, 0});
                    MicroscopicLocation sl = (MicroscopicLocation) s.getLocation();
                    t = Math.hypot(a[0] - sl.getX(), a[1] - sl.getY()) / 500.0;   // m -> min at 30 km/h
                }
                if (t < bestT || (t == bestT && best != null && s.getCapacity() > best.getCapacity())) { bestT = t; best = s; }
            }
            return best;
        });
    }

    private Map<Integer, Integer> readDwellingsForCounty(DataSet dataSet, String county, int maxHh) {
        // FULL-REGION mode: county == "ALL" -> keep all counties, random household sample of sample.fraction.
        boolean fullRegion = county == null || county.equalsIgnoreCase("ALL");
        Set<Integer> countyZones = fullRegion ? null : readCountyZones(county);
        double frac = AbitResources.instance.getDouble("sample.fraction", 1.0);
        Random sampleRng = new Random(20240702L);   // deterministic sample
        Map<Integer, Integer> hhZone = new LinkedHashMap<>();
        String f = AbitResources.instance.getString("dwellings.file");
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String[] h = br.readLine().split(",");
            int iZone = idx(h, "zone"), iHh = idx(h, "hhID");
            String line;
            while ((line = br.readLine()) != null && hhZone.size() < maxHh) {
                String[] r = line.split(",");
                int hid = Integer.parseInt(r[iHh].trim());
                if (hid <= 0) continue;
                int zone = Integer.parseInt(r[iZone].trim());
                if (!fullRegion && !countyZones.contains(zone)) continue;
                if (fullRegion && frac < 1.0 && sampleRng.nextDouble() >= frac) continue;
                hhZone.putIfAbsent(hid, zone);
            }
        } catch (Exception e) {
            throw new RuntimeException("readDwellings failed", e);
        }
        logger.info("Selected " + hhZone.size() + " households "
                + (fullRegion ? ("(FULL REGION, sample.fraction=" + frac + ")") : ("in county " + county)));
        return hhZone;
    }

    private Set<Integer> readCountyZones(String county) {
        Set<Integer> zones = new HashSet<>();
        String f = AbitResources.instance.getString("zone.attributes.file");
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String[] h = br.readLine().split(",");
            int iId = idx(h, "id"), iC = idx(h, "countyfips");
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                if (r[iC].trim().equals(county)) zones.add(Integer.parseInt(r[iId].trim()));
            }
        } catch (Exception e) {
            throw new RuntimeException("readCountyZones failed", e);
        }
        return zones;
    }

    private Map<Integer, Integer> readHouseholdAutos(Set<Integer> keptHh) {
        Map<Integer, Integer> autos = new HashMap<>();
        String f = AbitResources.instance.getString("households.file");
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String[] h = br.readLine().split(",");
            int iId = idx(h, "id"), iAutos = idx(h, "autos");
            String line;
            while ((line = br.readLine()) != null) {
                int c = line.indexOf(',');
                int id = Integer.parseInt(line.substring(0, c).trim());
                if (!keptHh.contains(id)) continue;
                String[] r = line.split(",");
                autos.put(id, Integer.parseInt(r[iAutos].trim()));
                if (autos.size() == keptHh.size()) break;
            }
        } catch (Exception e) {
            throw new RuntimeException("readHouseholdAutos failed", e);
        }
        return autos;
    }

    private void buildHouseholds(DataSet dataSet, Map<Integer, Integer> hhZone, Map<Integer, Integer> autos) {
        for (Map.Entry<Integer, Integer> e : hhZone.entrySet()) {
            int hid = e.getKey(), zone = e.getValue();
            MicroscopicLocation loc = locFor(zone);
            setZoneOnLoc(dataSet, loc, zone);
            Household hh = new Household(hid, loc, autos.getOrDefault(hid, 0));
            hh.setSimulated(Boolean.TRUE);
            hh.setPartition(2);
            dataSet.getHouseholds().put(hid, hh);
        }
    }

    private MicroscopicLocation locFor(int zoneId) {
        double[] xy = zoneXY.getOrDefault(zoneId, new double[]{0, 0});
        MicroscopicLocation loc = new MicroscopicLocation(xy[0] + (rnd.nextDouble() - 0.5) * 200,
                xy[1] + (rnd.nextDouble() - 0.5) * 200);
        // zone reference needed for skim lookups
        // (Zone object set below by caller via dataSet lookup)
        return loc;
    }

    private void setZoneOnLoc(DataSet dataSet, MicroscopicLocation loc, int zoneId) {
        Zone z = dataSet.getZones().get(zoneId);
        if (z != null) loc.setZone(z);
    }

    private void readPersonsAndJobs(DataSet dataSet, Set<Integer> keptHh) {
        // first pass over persons: capture attributes + collect employed person ids
        String pf = AbitResources.instance.getString("persons.file");
        List<String[]> kept = new ArrayList<>();
        Set<Integer> employedIds = new HashSet<>();
        int[] cols = new int[9];
        try (BufferedReader br = new BufferedReader(new FileReader(pf))) {
            String[] h = br.readLine().split(",");
            cols[0] = idx(h, "id"); cols[1] = idx(h, "hhid"); cols[2] = idx(h, "age");
            cols[3] = idx(h, "gender"); cols[4] = idx(h, "relationShip"); cols[5] = idx(h, "occupation");
            cols[6] = idx(h, "driversLicense"); cols[7] = idx(h, "income");
            cols[8] = -1;   // optional SILO column schoolId (-1 none, -2 student without record, > 0 school id)
            for (int i = 0; i < h.length; i++) if (strip(h[i]).equalsIgnoreCase("schoolId")) cols[8] = i;
            if (schoolsLoaded && cols[8] < 0) logger.warn("persons file has no schoolId column: every student gets the nearest school of the band");
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                int hhid = Integer.parseInt(r[cols[1]].trim());
                if (!keptHh.contains(hhid)) continue;
                kept.add(r);
                if (Integer.parseInt(r[cols[5]].trim()) == Occupation.EMPLOYED.ordinal()
                        || strip(r[cols[5]]).equals("1")) {
                    employedIds.add(Integer.parseInt(r[cols[0]].trim()));
                }
            }
        } catch (Exception e) {
            throw new RuntimeException("readPersons pass1 failed", e);
        }

        // WORK destination = LODES-calibrated workplace RE-ASSIGNMENT (workplace_reassign.py): reproduces the
        // observed home->work commute OD (24% inflow to BMR, 7.6% out-of-state, realistic lengths). Replaces
        // the old home-gravity sampleWorkZone() which discarded SILO workplaces and lost out-of-state inflow.
        // Falls back to sampleWorkZone() only for workers not present in the re-assignment file.
        //  EDUCATION -> RTS EDUCATION distance-calibrated draw (SILO has no schools)
        String wpf = AbitResources.instance.getString("workplace.reassign.file");
        if (wpf != null) {
            try (BufferedReader br = new BufferedReader(new FileReader(wpf))) {
                br.readLine();  // header person_id,home_zone,work_zone
                String line;
                while ((line = br.readLine()) != null) {
                    String[] p = line.split(",");
                    int wz = Integer.parseInt(p[2].trim());
                    if (wz > 0) reassignedWorkZone.put(Integer.parseInt(p[0].trim()), wz);
                }
            } catch (Exception e) { throw new RuntimeException("workplace.reassign.file read failed: " + wpf, e); }
            System.out.println("[workplace] loaded " + reassignedWorkZone.size() + " LODES-calibrated workplaces");
        }
        // Validation_2026 stage 3 (2026-10-22): property workplace.silo = true takes the workplace of every employed person
        // from the SILO job file (jobs.file: personId -> zone; the stage-1 assignment carried through the land-use model,
        // the contract of the integrated loop); workers without a job record fall back to the home gravity below.
        boolean siloWork = false;
        try { siloWork = Boolean.parseBoolean(AbitResources.instance.getString("workplace.silo")); } catch (Exception ignored) {}
        if (siloWork) {
            String jf = AbitResources.instance.getString("jobs.file"); int n = 0;
            try (BufferedReader br = new BufferedReader(new FileReader(jf))) {
                String[] h = br.readLine().split(",");
                int iZone = idx(h, "zone"), iPid = idx(h, "personId");
                int iType = -1; for (int i = 0; i < h.length; i++) if (strip(h[i]).equalsIgnoreCase("type")) iType = i;
                String line;
                while ((line = br.readLine()) != null) {
                    String[] p = line.split(",");
                    // jobs by zone and SILO type (RET retail, OFF office, else other) from the FULL job file, the attraction
                    // sizes of the destination choice (second pass of stage 3, 2026-10-22; independent of sample.fraction)
                    try {
                        int jz = Integer.parseInt(p[iZone].trim());
                        if (jz > 0) {
                            int[] c = zoneJobCounts.computeIfAbsent(jz, k -> new int[4]); c[0]++;
                            String ty = iType >= 0 && p.length > iType ? strip(p[iType]).toUpperCase() : "";
                            c[ty.startsWith("RET") ? 1 : ty.startsWith("OFF") ? 2 : 3]++;
                        }
                    } catch (NumberFormatException ignored) { }
                    int pid = Integer.parseInt(p[iPid].trim());
                    if (pid > 0 && employedIds.contains(pid)) {
                        int wz = Integer.parseInt(p[iZone].trim());
                        if (wz > 0 && zoneXY.containsKey(wz)) { reassignedWorkZone.putIfAbsent(pid, wz); n++; }
                    }
                }
            } catch (Exception e) { throw new RuntimeException("workplace.silo: jobs.file read failed: " + jf, e); }
            logger.info("[workplace] SILO job zones for " + n + " of " + employedIds.size() + " employed persons of the sample (others: home gravity)");
        }
        int jobSeq = 1, schoolSeq = 1;
        int stuById = 0, stuNearest = 0, stuNone = 0;
        for (String[] r : kept) {
            int id = Integer.parseInt(r[cols[0]].trim());
            int hhid = Integer.parseInt(r[cols[1]].trim());
            Household hh = dataSet.getHouseholds().get(hhid);
            int homeZone = hh.getLocation().getZoneId() == -1 ? firstZone(hh) : hh.getLocation().getZoneId();
            int age = Integer.parseInt(r[cols[2]].trim());
            Gender gender = Gender.valueOf(Integer.parseInt(r[cols[3]].trim()));
            Relationship rel = Relationship.valueOf(strip(r[cols[4]]).toLowerCase());   // SILO writes MARRIED/SINGLE/CHILD
            Occupation occ = Occupation.valueOf(Integer.parseInt(r[cols[5]].trim()));
            boolean lic = Boolean.parseBoolean(r[cols[6]].trim());
            int monthly = (int) (Double.parseDouble(r[cols[7]].trim()) / 12.0);

            Job job = null; School school = null;
            if (occ == Occupation.EMPLOYED) {
                // LODES-calibrated workplace; fall back to the home gravity only if this worker is missing
                int jz = reassignedWorkZone.getOrDefault(id, -1);
                if (jz <= 0) jz = sampleWorkZone(homeZone);
                MicroscopicLocation jl = locFor(jz); setZoneOnLoc(dataSet, jl, jz);
                job = new Job(jobSeq++, id, "OTH", jl, 8 * 60, 8 * 60);
                dataSet.getJobs().put(job.getId(), job);
            } else if (occ == Occupation.STUDENT) {
                if (schoolsLoaded) {
                    // SILO school assignment: schoolId > 0 -> record; -2 (or an id not in the file) -> nearest school
                    // of the age band by car skim, the rule of SILO's SchoolDataMd / assign_students.py
                    int sid = cols[8] >= 0 ? Integer.parseInt(r[cols[8]].trim()) : -2;
                    if (sid > 0) school = dataSet.getSchools().get(sid);
                    if (school != null) stuById++;
                    else {
                        school = nearestSchool(homeZone, bandOf(age));
                        if (school != null) stuNearest++; else stuNone++;
                    }
                } else {
                    int sz = sampleDistanceZone(homeZone, eduMeanKm);   // legacy placeholder (no schools.file)
                    MicroscopicLocation sl = locFor(sz); setZoneOnLoc(dataSet, sl, sz);
                    school = new School(schoolSeq++, "edu", 1, 0, sl, 8 * 60, 6 * 60);
                    dataSet.getSchools().put(school.getId(), school);
                }
            }
            Person p = new Person(id, hh, age, gender, rel, occ, lic, job, 8 * 60, 8 * 60, 8 * 60,
                    monthly, school, Disability.WITHOUT);
            hh.getPersons().add(p);
            dataSet.getPersons().put(id, p);
        }

        if (schoolsLoaded) {
            logger.info("Students: " + stuById + " with the SILO school record, " + stuNearest + " nearest school of the band (schoolId -2 or unknown), "
                    + stuNone + " without any school of the band (no EDUCATION tours)");
        }
    }

    private int firstZone(Household hh) {
        return hh.getLocation().getZoneId();
    }

    // attraction sizes per zone (mirrors DefaultDataReaderManager.populateZones)
    private void populateZones(DataSet dataSet) {
        String[] keys = {"hh.total", "jj.total", "jj.retail", "jj.office", "jj.other", "students"};
        Map<Zone, Map<String, Integer>> att = new HashMap<>();
        for (Zone z : dataSet.getZones().values()) {
            att.put(z, new HashMap<>());
            for (String k : keys) att.get(z).put(k, 0);
        }
        for (Household hh : dataSet.getHouseholds().values()) {
            Zone z = dataSet.getZones().get(hh.getLocation().getZoneId());
            if (z == null) continue;
            att.get(z).merge("hh.total", hh.getPersons().size(), Integer::sum);
            if (!schoolsLoaded) {   // legacy placeholder schools: one per sampled student
                for (Person pp : hh.getPersons()) {
                    if (pp.getOccupation() == Occupation.STUDENT && pp.getSchool() != null) {
                        Zone sz = dataSet.getZones().get(pp.getSchool().getLocation().getZoneId());
                        if (sz != null) att.get(sz).merge("students", 1, Integer::sum);
                    }
                }
            }
        }
        if (schoolsLoaded) {
            // students attractor from the school records (independent of sample.fraction): students assigned by SILO
            // (occupancy) when the file carries an assignment, else the enrolment (capacity)
            boolean useOcc = schoolOccupancy.values().stream().mapToInt(Integer::intValue).sum() > 0;
            for (School s : dataSet.getSchools().values()) {
                Zone sz = dataSet.getZones().get(s.getLocation().getZoneId());
                if (sz != null) att.get(sz).merge("students", useOcc ? schoolOccupancy.getOrDefault(s.getId(), 0) : s.getCapacity(), Integer::sum);
            }
        }
        if (!zoneJobCounts.isEmpty()) {
            // full job counts by zone and type (jobs.file, read with workplace.silo): the attraction sizes of the destination choice
            for (Map.Entry<Integer, int[]> e : zoneJobCounts.entrySet()) {
                Zone z = dataSet.getZones().get(e.getKey());
                if (z == null) continue;
                int[] c = e.getValue();
                att.get(z).merge("jj.total", c[0], Integer::sum); att.get(z).merge("jj.retail", c[1], Integer::sum);
                att.get(z).merge("jj.office", c[2], Integer::sum); att.get(z).merge("jj.other", c[3], Integer::sum);
            }
        } else {
            for (Job job : dataSet.getJobs().values()) {
                Zone z = dataSet.getZones().get(job.getLocation().getZoneId());
                if (z == null) continue;
                att.get(z).merge("jj.total", 1, Integer::sum);
                att.get(z).merge("jj.other", 1, Integer::sum);
            }
        }
        for (Zone z : dataSet.getZones().values()) {
            for (String k : keys) z.setAttribute(k, att.get(z).get(k));
        }
    }

    private void loadFrictionParams() {
        String f = AbitResources.instance.getString("dest.friction.file");
        if (f == null) return;
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String[] h = br.readLine().split(",");
            int iP = idx(h, "purpose"), iBt = idx(h, "b_time"), iBl = idx(h, "b_logtime");
            String line;
            while ((line = br.readLine()) != null) {
                String[] r = line.split(",");
                if (r[iP].trim().equalsIgnoreCase("WORK")) {
                    bt = Double.parseDouble(r[iBt].trim());
                    blt = Double.parseDouble(r[iBl].trim());
                }
            }
        } catch (Exception e) {
            logger.warn("dest.friction.file not loaded, using defaults: " + e.getMessage());
        }
    }

    private void computeJobAttraction() {
        Map<Integer, Integer> jobs = new HashMap<>();
        String f = AbitResources.instance.getString("jobs.file");
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String[] h = br.readLine().split(",");
            int iZone = idx(h, "zone");
            String line;
            while ((line = br.readLine()) != null) {
                int z = Integer.parseInt(line.split(",")[iZone].trim());
                jobs.merge(z, 1, Integer::sum);
            }
        } catch (Exception e) {
            throw new RuntimeException("computeJobAttraction failed", e);
        }
        List<Integer> cands = new ArrayList<>();
        for (Map.Entry<Integer, Integer> e : jobs.entrySet())
            if (zoneXY.containsKey(e.getKey())) cands.add(e.getKey());
        workDestZones = new int[cands.size()];
        workDestAttr = new double[cands.size()];
        for (int i = 0; i < cands.size(); i++) {
            workDestZones[i] = cands.get(i);
            workDestAttr[i] = jobs.get(cands.get(i));
        }
        logger.info("WORK gravity: " + workDestZones.length + " job-zones (total jobs " + jobs.values().stream().mapToInt(Integer::intValue).sum() + ")");
    }

    private MicroscopicLocation zoneCentroid(int zoneId) {
        return zoneLocCache.computeIfAbsent(zoneId, z -> {
            double[] xy = zoneXY.getOrDefault(z, new double[]{0, 0});
            MicroscopicLocation l = new MicroscopicLocation(xy[0], xy[1]);
            setZoneOnLoc(ds, l, z);
            return l;
        });
    }

    /** Draw a workplace zone from the RTS HBW Tanner-friction gravity given the home zone. Cached per home zone. */
    private int sampleWorkZone(int homeZone) {
        double[] cum = workCumCache.computeIfAbsent(homeZone, hz -> {
            MicroscopicLocation homeLoc = zoneCentroid(hz);
            double[] c = new double[workDestZones.length];
            double run = 0;
            for (int i = 0; i < workDestZones.length; i++) {
                double t = ds.getTravelTimes().getTravelTimeInMinutes(homeLoc, zoneCentroid(workDestZones[i]),
                        abm.data.plans.Mode.CAR_DRIVER, 8 * 60);
                if (!(t >= 0) || t > 300) t = 300;
                double fr = Math.pow(t + 1.0, blt) * Math.exp(bt * t);   // RTS HBW Tanner friction
                // out-of-sample long-tail correction (as in the tour pipeline): extra decay for long
                // trips only, so singly-constrained high-attraction downtown zones don't over-absorb.
                if (t > workLongT0) fr *= Math.exp(-workLongPen * (t - workLongT0));
                run += workDestAttr[i] * fr;
                c[i] = run;
            }
            return c;
        });
        double total = cum[cum.length - 1];
        if (total <= 0) return homeZone;
        double u = rnd.nextDouble() * total;
        int lo = 0, hi = cum.length - 1;
        while (lo < hi) { int m = (lo + hi) >>> 1; if (cum[m] < u) lo = m + 1; else hi = m; }
        return workDestZones[lo];
    }

    /** Pick the zone whose network distance from home is closest to a target drawn Exp(meanKm). */
    private int sampleDistanceZone(int homeZone, double meanKm) {
        MicroscopicLocation home = zoneCentroid(homeZone);
        double targetM = Math.max(200, Math.min(60000, -meanKm * Math.log(1 - rnd.nextDouble()) * 1000));
        int best = homeZone; double bestDiff = Double.MAX_VALUE;
        for (int i = 0; i < 300; i++) {
            int z = allZones[rnd.nextInt(allZones.length)];
            double d = ds.getTravelDistances().getTravelDistanceInMeters(home, zoneCentroid(z),
                    abm.data.plans.Mode.UNKNOWN, 8 * 60);
            double diff = Math.abs(d - targetM);
            if (diff < bestDiff) { bestDiff = diff; best = z; }
        }
        return best;
    }

    private static int idx(String[] header, String name) {
        for (int i = 0; i < header.length; i++) if (strip(header[i]).equalsIgnoreCase(name)) return i;
        throw new RuntimeException("Column '" + name + "' not in header");
    }

    private static String strip(String s) { return s.replace("\"", "").trim(); }
}
