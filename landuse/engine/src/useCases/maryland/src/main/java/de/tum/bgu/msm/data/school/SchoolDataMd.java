package de.tum.bgu.msm.data.school;

import de.tum.bgu.msm.data.MicroLocation;
import de.tum.bgu.msm.data.Zone;
import de.tum.bgu.msm.data.dwelling.Dwelling;
import de.tum.bgu.msm.data.dwelling.DwellingData;
import de.tum.bgu.msm.data.geo.GeoData;
import de.tum.bgu.msm.data.household.HouseholdData;
import de.tum.bgu.msm.data.person.Occupation;
import de.tum.bgu.msm.data.person.Person;
import de.tum.bgu.msm.data.travelTimes.TravelTimes;
import de.tum.bgu.msm.properties.Properties;
import de.tum.bgu.msm.schools.PersonWithSchool;
import de.tum.bgu.msm.schools.School;
import de.tum.bgu.msm.schools.SchoolData;
import de.tum.bgu.msm.utils.SiloUtil;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.locationtech.jts.geom.Coordinate;
import org.locationtech.jts.geom.Geometry;
import org.matsim.api.core.v01.TransportMode;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * School data of the Maryland study (Baltimore 2026, stage 2b).
 *
 * The school file (2_silo/input/schools_2016.csv, built by 2_silo/schools/build_schools.py) has one record per school
 * and grade band: SILO type 1 elementary (K-5), 2 middle and high (6-12), 3 post-secondary, and a finer band column
 * (elementary, middle, high, postsec); capacity = enrollment of the band, occupancy = synthetic students assigned
 * (counted up when a student takes a seat, down when the student leaves).
 *
 * Bands by age: elementary 5-10, middle 11-13, high 14-17, post-secondary 18 and older (Maryland grade spans). The
 * search unit is the band: a 15-year-old is ranked over the high-school records first and over the middle-school
 * records of the same SILO type only as a fallback (records without a band column serve every band of their type).
 *
 * Maryland dwellings carry no coordinates (dd_2016.csv has zone only), so the school search cannot work from a point
 * as SchoolDataImpl does. Instead the search works from the home zone: for a home zone and a band the schools are
 * ranked once by zone-to-zone car travel time of the peak skim (TravelTimes, the auto_peak_time skim of the run)
 * and, where the skim gives no value, by the straight-line distance between the zone centroid and the school at an
 * equivalent of 30 km/h; the ranking is cached per zone and band and rebuilt every year (skims may be updated in loop
 * years). The student takes the first school of the ranking with a free seat (occupancy < capacity); when every school
 * of the band is full the nearest school is taken anyway, so a student always gets a school. The offline assignment
 * of the 2016 base year (2_silo/schools/assign_students.py) applies the same rule to all students at once.
 *
 * Occupancy is recounted from the persons' schoolId at setup and at the start of every year, so seats of students who
 * died or out-migrated during a year are released at the latest at the year change.
 */
public class SchoolDataMd implements SchoolData {

    private static final Logger logger = LogManager.getLogger(SchoolDataMd.class);

    public static final int TYPE_ELEMENTARY = 1;
    public static final int TYPE_SECONDARY = 2;
    public static final int TYPE_POSTSECONDARY = 3;
    public static final int BAND_ANY = 0;
    public static final int BAND_ELEMENTARY = 1;
    public static final int BAND_MIDDLE = 2;
    public static final int BAND_HIGH = 3;
    public static final int BAND_POSTSECONDARY = 4;
    /** Maryland grade bands: K-5 ages 5-10, 6-8 ages 11-13, 9-12 ages 14-17, post-secondary from 18 */
    public static final int MIN_SECONDARY_AGE = 11;
    public static final int MIN_HIGH_AGE = 14;
    public static final int MIN_TERTIARY_AGE = 18;

    private static final double PEAK_TIME_S = 8 * 3600;
    private static final double FALLBACK_METRES_PER_MINUTE = 500;   // 30 km/h, used where the skim has no value

    private final GeoData geoData;
    private final DwellingData dwellingData;
    private final HouseholdData householdData;
    private final TravelTimes travelTimes;
    private final Properties properties;

    private final Map<Integer, School> schools = new ConcurrentHashMap<>();
    private final Map<Integer, List<School>> schoolsByType = new ConcurrentHashMap<>();
    private final Map<Long, School[]> rankingByZoneAndType = new ConcurrentHashMap<>();
    private final Map<Integer, Integer> bandBySchool = new ConcurrentHashMap<>();
    private final Map<Integer, Coordinate> zoneCentroids = new ConcurrentHashMap<>();
    private int noSkimValueCount = 0;
    private int fullTypeCount = 0;

    // Baltimore 2026 (2026-11-18j): school.choice.model = respec1118 -> the estimated school location choice (SchoolChoiceMd) for the
    // students assigned during the simulation; nearest (default) = the nearest school with a free seat (the rule above, unchanged)
    private final boolean choiceModel = "respec1118".equalsIgnoreCase(de.tum.bgu.msm.models.resloc.ReslocProperties.get("school.choice.model", "nearest"));
    private SchoolChoiceMd choice;
    // Baltimore 2026 (2026-11-19d, school.seat.release = true; default false = as before): the seat is freed at once when a person leaves
    // the population or stops being a student (listeners of HouseholdDataManagerImpl and PersonMstm), the education model changes the
    // band with the age the student reaches during the year (EducationModelMd), and the live occupancy is compared with a recount from
    // the persons at the end of every year (checkOccupancy)
    public static final boolean SEAT_RELEASE = Boolean.parseBoolean(de.tum.bgu.msm.models.resloc.ReslocProperties.get("school.seat.release", "false"));
    private Random choiceRandom;

    public SchoolDataMd(GeoData geoData, DwellingData dwellingData, HouseholdData householdData,
                        TravelTimes travelTimes, Properties properties) {
        this.geoData = geoData;
        this.dwellingData = dwellingData;
        this.householdData = householdData;
        this.travelTimes = travelTimes;
        this.properties = properties;
    }

    /** School type a student of this age attends in Maryland (K-5 / 6-12 / post-secondary). */
    public static int schoolTypeForAge(int age) {
        return typeForBand(bandForAge(age));
    }

    /** Grade band a student of this age attends in Maryland. */
    public static int bandForAge(int age) {
        if (age < MIN_SECONDARY_AGE) {
            return BAND_ELEMENTARY;
        } else if (age < MIN_HIGH_AGE) {
            return BAND_MIDDLE;
        } else if (age < MIN_TERTIARY_AGE) {
            return BAND_HIGH;
        } else {
            return BAND_POSTSECONDARY;
        }
    }

    /** SILO school type of a band (middle and high schools share type 2). */
    public static int typeForBand(int band) {
        switch (band) {
            case BAND_ELEMENTARY:
                return TYPE_ELEMENTARY;
            case BAND_MIDDLE:
            case BAND_HIGH:
                return TYPE_SECONDARY;
            default:
                return TYPE_POSTSECONDARY;
        }
    }

    /** Band code of the band column of the school file (0 when unknown). */
    public static int parseBand(String band) {
        switch (band.trim().toLowerCase()) {
            case "elementary":
                return BAND_ELEMENTARY;
            case "middle":
                return BAND_MIDDLE;
            case "high":
                return BAND_HIGH;
            case "postsec":
            case "postsecondary":
                return BAND_POSTSECONDARY;
            default:
                return BAND_ANY;
        }
    }

    /** Records the band of a school record (called by the reader; BAND_ANY = serves every band of its type). */
    public void setBand(int schoolId, int band) {
        bandBySchool.put(schoolId, band);
    }

    /** Band of a school record, or the band implied by its type when the file gave none. */
    public int bandOf(School school) {
        int band = bandBySchool.getOrDefault(school.getId(), BAND_ANY);
        if (band == BAND_ANY) {
            if (school.getType() == TYPE_ELEMENTARY) return BAND_ELEMENTARY;
            if (school.getType() == TYPE_POSTSECONDARY) return BAND_POSTSECONDARY;
        }
        return band;
    }

    /** Band the person attends: the band of the school record; without a record, the band for the age. */
    public int currentBand(PersonWithSchool person) {
        if (person.getSchoolId() > 0) {
            School school = schools.get(person.getSchoolId());
            if (school != null) {
                int band = bandOf(school);
                if (band != BAND_ANY) return band;
                return bandForAge(person.getAge());
            }
        }
        return bandForAge(person.getAge());
    }

    /** True when the person's school record does not serve the band of the person's age. */
    public boolean bandChangeDue(PersonWithSchool person) {
        if (person.getSchoolId() < 1) return true;
        School school = schools.get(person.getSchoolId());
        if (school == null) return true;
        int wanted = bandForAge(person.getAge());
        int band = bandOf(school);
        if (band == BAND_ANY) {
            return school.getType() != typeForBand(wanted);
        }
        return band != wanted;
    }

    /**
     * Gives the person a school of the band near the home zone: releases the seat held so far, takes a seat in the new
     * school and sets schoolId and schoolType. Returns the school, or null when no school of the band exists (the
     * person is then marked -2, student without a school record).
     */
    public School assignSchool(PersonWithSchool person, int band) {
        releaseSchool(person);
        School school = choiceModel ? chooseSchoolByModel(person, band) : getClosestSchoolOfBand(person, band);
        person.setSchoolType(typeForBand(band));
        if (school == null) {
            person.setSchoolId(-2);
            return null;
        }
        person.setSchoolId(school.getId());
        school.setOccupancy(school.getOccupancy() + 1);
        if (person.getId() == SiloUtil.trackPp) {
            SiloUtil.trackWriter.println("Person " + person.getId() + " assigned to school " + school.getId()
                    + " (band " + band + ", zone " + school.getZoneId() + ")");
        }
        return school;
    }

    /** Releases the seat of the person (schoolId -1 afterwards). */
    public void releaseSchool(PersonWithSchool person) {
        if (person.getSchoolId() > 0) {
            School school = schools.get(person.getSchoolId());
            if (school != null) {
                school.setOccupancy(Math.max(0, school.getOccupancy() - 1));
            }
        }
        person.setSchoolId(-1);
    }

    @Override
    public void addSchool(School school) {
        schools.put(school.getId(), school);
        schoolsByType.computeIfAbsent(school.getType(), k -> new ArrayList<>()).add(school);
        rankingByZoneAndType.clear();
    }

    @Override
    public School getSchoolFromId(int id) {
        return schools.get(id);
    }

    @Override
    public Collection<School> getSchools() {
        return schools.values();
    }

    /** SchoolData contract (search by SILO type): secondary students are searched in the band of their age. */
    @Override
    public School getClosestSchool(Person person, int schoolType) {
        int band;
        if (schoolType == TYPE_ELEMENTARY) {
            band = BAND_ELEMENTARY;
        } else if (schoolType == TYPE_POSTSECONDARY) {
            band = BAND_POSTSECONDARY;
        } else {
            band = person.getAge() < MIN_HIGH_AGE ? BAND_MIDDLE : BAND_HIGH;
        }
        return getClosestSchoolOfBand(person, band);
    }

    /** Nearest school of the band from the home zone with a free seat; the nearest school when all are full. */
    public School getClosestSchoolOfBand(Person person, int band) {
        int zoneId = homeZone(person);
        if (zoneId < 0) {
            logger.warn("Person " + person.getId() + " has no dwelling with a zone; no school assigned");
            return null;
        }
        School[] ranking = ranking(zoneId, band);
        if (ranking.length == 0) {
            logger.warn("No school of band " + band + " in the school file");
            return null;
        }
        for (School school : ranking) {
            if (school.getOccupancy() < school.getCapacity()) {
                return school;
            }
        }
        fullTypeCount++;
        return ranking[0];
    }

    /** Baltimore 2026 (2026-11-18j): school drawn from the estimated school location choice (SchoolChoiceMd); the nearest-school rule
     *  only when the band has no record in the choice set */
    private School chooseSchoolByModel(Person person, int band) {
        final int zoneId = homeZone(person);
        if (zoneId < 0) {
            logger.warn("Person " + person.getId() + " has no dwelling with a zone; no school assigned");
            return null;
        }
        final de.tum.bgu.msm.data.household.Household hh = person.getHousehold();
        final boolean car0 = hh.getAutos() <= 0;
        final double income = de.tum.bgu.msm.data.household.HouseholdUtil.getAnnualHhIncome(hh);
        final int race = person instanceof de.tum.bgu.msm.data.person.PersonMstm && ((de.tum.bgu.msm.data.person.PersonMstm) person).getRace() != null
                ? ((de.tum.bgu.msm.data.person.PersonMstm) person).getRace().ordinal() : -1;
        final de.tum.bgu.msm.util.matrices.IndexedDoubleMatrix2D car = travelTimes.getPeakSkim(TransportMode.car);
        final School s = choice.choose(zoneId, band, car0, income, race, (f, t) -> car.getIndexed(f, t), choiceRandom);
        return s != null ? s : getClosestSchoolOfBand(person, band);
    }

    /** Baltimore 2026 (2026-11-18j): records by band and students by zone x band x race for the school location choice */
    private void prepareChoice() {
        final Map<Integer, List<SchoolChoiceMd.Rec>> byBand = new HashMap<>();
        int noComponent = 0;
        for (School s : schools.values()) {
            int comp = choice.component(s.getId());
            if (comp < 0) { noComponent++; continue; }
            byBand.computeIfAbsent(bandOf(s), k -> new ArrayList<>()).add(new SchoolChoiceMd.Rec(s.getId(), s.getZoneId(), comp, s.getCapacity(), s));
        }
        choice.setRecords(byBand);
        final Map<Long, double[]> counts = new HashMap<>();
        for (Person person : householdData.getPersons()) {
            if (!(person instanceof PersonWithSchool) || !(person instanceof de.tum.bgu.msm.data.person.PersonMstm)) continue;
            final int sid = ((PersonWithSchool) person).getSchoolId();
            if (sid <= 0) continue;
            final School s = schools.get(sid);
            final de.tum.bgu.msm.data.person.Race r = ((de.tum.bgu.msm.data.person.PersonMstm) person).getRace();
            if (s == null || r == null) continue;
            counts.computeIfAbsent(SchoolChoiceMd.raceKey(s.getZoneId(), bandOf(s)), k -> new double[4])[r.ordinal()]++;
        }
        choice.setRaceCounts(counts);
        if (noComponent > 0) logger.warn("School location choice: " + noComponent + " school records without a size component (not chosen)");
    }

    @Override
    public void removeSchool(int id) {
        School removed = schools.remove(id);
        bandBySchool.remove(id);
        if (removed != null) {
            schoolsByType.getOrDefault(removed.getType(), new ArrayList<>()).remove(removed);
            rankingByZoneAndType.clear();
        }
    }

    private int homeZone(Person person) {
        if (person.getHousehold() == null) {
            return -1;
        }
        Dwelling dwelling = dwellingData.getDwelling(person.getHousehold().getDwellingId());
        return dwelling == null ? -1 : dwelling.getZoneId();
    }

    private School[] ranking(int zoneId, int band) {
        return rankingByZoneAndType.computeIfAbsent(((long) zoneId << 4) + band, key -> rank(zoneId, band));
    }

    /** Schools of the band's type ordered by (band of the record matches the band wanted, travel cost). */
    private School[] rank(int zoneId, int band) {
        List<School> candidates = schoolsByType.getOrDefault(typeForBand(band), Collections.emptyList());
        Zone home = geoData.getZones().get(zoneId);
        final double[] cost = new double[candidates.size()];
        final int[] mismatch = new int[candidates.size()];
        Integer[] order = new Integer[candidates.size()];
        for (int i = 0; i < candidates.size(); i++) {
            order[i] = i;
            cost[i] = costMinutes(home, candidates.get(i));
            int recordBand = bandOf(candidates.get(i));
            mismatch[i] = (recordBand == BAND_ANY || recordBand == band) ? 0 : 1;
        }
        final List<School> list = candidates;
        Arrays.sort(order, (a, b) -> {
            int c = Integer.compare(mismatch[a], mismatch[b]);
            if (c != 0) return c;
            c = Double.compare(cost[a], cost[b]);
            if (c != 0) return c;
            c = Integer.compare(list.get(b).getCapacity(), list.get(a).getCapacity());
            if (c != 0) return c;
            return Integer.compare(list.get(a).getId(), list.get(b).getId());
        });
        School[] ranked = new School[order.length];
        for (int i = 0; i < order.length; i++) {
            ranked[i] = candidates.get(order[i]);
        }
        return ranked;
    }

    private double costMinutes(Zone home, School school) {
        if (travelTimes != null && home != null) {
            Zone schoolZone = geoData.getZones().get(school.getZoneId());
            if (schoolZone != null) {
                double minutes = travelTimes.getTravelTime(home, schoolZone, PEAK_TIME_S, TransportMode.car);
                if (!Double.isNaN(minutes) && !Double.isInfinite(minutes) && minutes > 0) {
                    return minutes;
                }
            }
        }
        noSkimValueCount++;
        Coordinate from = centroid(home);
        Coordinate to = ((MicroLocation) school).getCoordinate();
        if (from == null || to == null) {
            return Double.MAX_VALUE;
        }
        return from.distance(to) / FALLBACK_METRES_PER_MINUTE;
    }

    private Coordinate centroid(Zone zone) {
        if (zone == null || zone.getZoneFeature() == null) {
            return null;
        }
        return zoneCentroids.computeIfAbsent(zone.getZoneId(),
                k -> ((Geometry) zone.getZoneFeature().getDefaultGeometry()).getCentroid().getCoordinate());
    }

    /** Occupancy = number of persons whose schoolId points at the school. */
    private void recountOccupancy() {
        for (School school : schools.values()) {
            school.setOccupancy(0);
        }
        int students = 0, withSchool = 0, withoutRecord = 0, danglingIds = 0;
        for (Person person : householdData.getPersons()) {
            if (!(person instanceof PersonWithSchool)) continue;
            PersonWithSchool pp = (PersonWithSchool) person;
            if (person.getOccupation() == Occupation.STUDENT) students++;
            if (pp.getSchoolId() > 0) {
                School school = schools.get(pp.getSchoolId());
                if (school == null) {
                    danglingIds++;
                    pp.setSchoolId(person.getOccupation() == Occupation.STUDENT ? -2 : -1);
                } else {
                    school.setOccupancy(school.getOccupancy() + 1);
                    withSchool++;
                }
            } else if (person.getOccupation() == Occupation.STUDENT) {
                withoutRecord++;
            }
        }
        if (danglingIds > 0) {
            logger.warn(danglingIds + " persons pointed at school ids missing in the school file; marked as without record");
        }
        logger.info("Schools: " + schools.size() + " records, " + students + " students, " + withSchool
                + " persons with a school, " + withoutRecord + " students without a school record");
    }

    /** true when the person's school record does not serve the band of the given age (2026-11-19d: the age at the end of the year) */
    public boolean bandChangeDue(PersonWithSchool person, int age) {
        if (person.getSchoolId() < 1) return true;
        School school = schools.get(person.getSchoolId());
        if (school == null) return true;
        int wanted = bandForAge(age);
        int band = bandOf(school);
        if (band == BAND_ANY) return school.getType() != typeForBand(wanted);
        return band != wanted;
    }

    /** live occupancy against a recount of the persons' school ids; logs the difference (2026-11-19d) */
    public void checkOccupancy(String when) {
        final Map<Integer, Integer> c = new HashMap<>();
        for (Person person : householdData.getPersons()) {
            if (!(person instanceof PersonWithSchool)) continue;
            final int sid = ((PersonWithSchool) person).getSchoolId();
            if (sid > 0 && schools.containsKey(sid)) c.merge(sid, 1, Integer::sum);
        }
        int bad = 0; long diff = 0, occ = 0, full = 0;
        for (School s : schools.values()) {
            final int n = c.getOrDefault(s.getId(), 0); occ += s.getOccupancy();
            if (n != s.getOccupancy()) { bad++; diff += Math.abs(n - s.getOccupancy()); }
            if (s.getCapacity() > 0 && s.getOccupancy() >= s.getCapacity()) full++;
        }
        if (bad > 0) logger.error("Schools, " + when + ": live occupancy differs from the recount of the persons in " + bad + " records (sum |diff| " + diff + ")");
        else logger.info("Schools, " + when + ": live occupancy equals the recount of the persons");
        logger.info("Schools, " + when + ": " + occ + " seats occupied, " + full + " of " + schools.size() + " records full");
    }

    @Override
    public void setup() {
        if (SEAT_RELEASE) {
            de.tum.bgu.msm.data.household.HouseholdDataManagerImpl.personRemovalListener = p -> { if (p instanceof PersonWithSchool) releaseSchool((PersonWithSchool) p); };
            de.tum.bgu.msm.data.person.PersonMstm.studentExitListener = p -> { releaseSchool(p); p.setSchoolType(0); };
            logger.info("Schools: seats are released when a person leaves the population or school (school.seat.release)");
        }
        logger.info("Setup of Maryland school data (zone-based search over " + schools.size() + " school records)");
        recountOccupancy();
        if (choiceModel) {
            final String b = "input/";
            choice = new SchoolChoiceMd(new String[]{
                    de.tum.bgu.msm.models.resloc.ReslocProperties.path("school.choice.coef.k8", b + "school_choice_coef_1118_k8.csv"),
                    de.tum.bgu.msm.models.resloc.ReslocProperties.path("school.choice.coef.hs", b + "school_choice_coef_1118_hs.csv"),
                    de.tum.bgu.msm.models.resloc.ReslocProperties.path("school.choice.coef.college", b + "school_choice_coef_1118_college.csv")},
                    de.tum.bgu.msm.models.resloc.ReslocProperties.path("school.choice.records.file", b + "school_choice_records_1118.csv"),
                    de.tum.bgu.msm.models.resloc.ReslocProperties.path("school.choice.inboundary.file", b + "school_choice_inboundary_1118.csv"),
                    de.tum.bgu.msm.models.resloc.ReslocProperties.path("school.choice.zone.attributes.file", b + "school_choice_zone_attr_1118.csv"),
                    properties.main.baseDirectory + properties.geo.zonalDataFile);
            // own random stream (not drawn from SiloUtil's generator, so the other models' streams are unchanged)
            choiceRandom = new Random(1118L * 1000003L + properties.main.randomSeed);
            prepareChoice();
            logger.info("School location choice: estimated model (school.choice.model = respec1118) for students assigned during the simulation");
        }
    }

    @Override
    public void prepareYear(int year) {
        if (SEAT_RELEASE) checkOccupancy("start of " + year);
        rankingByZoneAndType.clear();
        recountOccupancy();
        noSkimValueCount = 0;
        fullTypeCount = 0;
        if (choiceModel) {
            prepareChoice();
            choice.assigned = 0; choice.fallbackFull = 0; choice.noZone = 0;
        }
    }

    @Override
    public void endYear(int year) {
        if (SEAT_RELEASE) checkOccupancy("end of " + year);
        if (noSkimValueCount > 0) {
            logger.info("School search " + year + ": " + noSkimValueCount + " zone-school pairs ranked by straight-line distance (no skim value)");
        }
        if (fullTypeCount > 0) {
            logger.info("School search " + year + ": " + fullTypeCount + " assignments to the nearest school although every school of the type was full");
        }
        if (choiceModel) {
            logger.info("School location choice " + year + ": " + choice.assigned + " students assigned by the estimated model, " + choice.fallbackFull
                    + " of them with every zone of the band full (seat constraint dropped), " + choice.noZone + " without a zone of the band (nearest-school rule)");
        }
    }

    @Override
    public void endSimulation() {
    }
}
