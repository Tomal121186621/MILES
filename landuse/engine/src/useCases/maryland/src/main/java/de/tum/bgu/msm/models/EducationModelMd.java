package de.tum.bgu.msm.models;

import de.tum.bgu.msm.container.DataContainer;
import de.tum.bgu.msm.data.person.Occupation;
import de.tum.bgu.msm.data.person.Person;
import de.tum.bgu.msm.data.school.SchoolDataMd;
import de.tum.bgu.msm.schools.DataContainerWithSchools;
import de.tum.bgu.msm.schools.PersonWithSchool;
import de.tum.bgu.msm.schools.School;
import de.tum.bgu.msm.events.impls.person.EducationEvent;
import de.tum.bgu.msm.models.demography.education.EducationModel;
import de.tum.bgu.msm.properties.Properties;
import de.tum.bgu.msm.utils.SiloUtil;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Random;

/**
 * Age-triggered occupation transitions for the Maryland study (Baltimore 2026, replaces EducationModelImpl, which only
 * turned every student of 19 or older into an unemployed person at once).
 *
 * Three transitions, all with annual probabilities by single year of age read from a data file (so that they are
 * calibrated to the study area's ACS PUMS, not written in code):
 *   TODDLER -> STUDENT   at age 5 (deterministic)
 *   STUDENT -> UNEMPLOYED (enters the labour market) with schoolExitProb[age]; forced at the last age of the table
 *   EMPLOYED / UNEMPLOYED -> RETIREE with retireProbEmployed[age] / retireProbUnemployed[age]
 * On retirement the person leaves the job and keeps a share of the last earnings (demographics.retirement.income.replacement),
 * not below the retiree income floor (retiree.income.floor). The income rule afterwards keeps retiree income flat.
 *
 * File (demographics.education.transitions.file), one row per age with a header:
 *   age,schoolExitProb,retireProbEmployed,retireProbUnemployed
 * Ages not listed have probability 0.
 *
 * Stage 2b (schools): every student holds a seat in a school record (PersonWithSchool.schoolId). On school entry the
 * child gets the nearest elementary school with a free seat (SchoolDataMd, searched from the home zone); when the age
 * reaches the next band (11: middle, 14: high, 18: post-secondary) the student changes to the nearest school of the
 * new band; on school exit the seat is released. Students without a school record (-2, e.g. in-migrant clones that
 * found no school) get one at the next education event.
 */
public class EducationModelMd extends AbstractModel implements EducationModel {

    private static final Logger logger = LogManager.getLogger(EducationModelMd.class);
    private static final int MAX_AGE = 120;
    private static final int SCHOOL_ENTRY_AGE = 5;

    private final double[] schoolExit = new double[MAX_AGE + 1];
    private final double[] retireEmployed = new double[MAX_AGE + 1];
    private final double[] retireUnemployed = new double[MAX_AGE + 1];
    private int lastSchoolAge = -1;
    private final double replacement;
    private final int retireeFloor;
    private final SchoolDataMd schoolData;
    private int noSchoolWarnings = 0;
    // 2026-11-19d (school.seat.release): age of each student at the start of the year; the band follows the age reached during the year
    private final java.util.Map<Integer, Integer> startAge = new java.util.HashMap<>();

    public EducationModelMd(DataContainer dataContainer, Properties properties, Random rnd) {
        super(dataContainer, properties, rnd);
        this.replacement = properties.demographics.retirementIncomeReplacement;
        this.retireeFloor = properties.householdData.retireeIncomeFloor;
        this.schoolData = dataContainer instanceof DataContainerWithSchools
                ? (SchoolDataMd) ((DataContainerWithSchools) dataContainer).getSchoolData() : null;
    }

    @Override
    public void setup() {
        final String file = properties.main.baseDirectory + properties.demographics.educationTransitionsFile;
        try (BufferedReader r = new BufferedReader(new FileReader(file))) {
            String[] header = r.readLine().split(",");
            int iAge = indexOf(header, "age"), iSchool = indexOf(header, "schoolExitProb"), iRetE = indexOf(header, "retireProbEmployed"), iRetU = indexOf(header, "retireProbUnemployed");
            String line;
            while ((line = r.readLine()) != null) {
                if (line.isBlank()) continue;
                String[] f = line.split(",");
                int age = Integer.parseInt(f[iAge].trim());
                if (age < 0 || age > MAX_AGE) continue;
                schoolExit[age] = Double.parseDouble(f[iSchool].trim());
                retireEmployed[age] = Double.parseDouble(f[iRetE].trim());
                retireUnemployed[age] = Double.parseDouble(f[iRetU].trim());
                if (schoolExit[age] > 0) lastSchoolAge = Math.max(lastSchoolAge, age);
            }
        } catch (IOException e) {
            throw new RuntimeException("Could not read education transitions file " + file, e);
        }
        logger.info("Education/retirement transitions read from " + file + "; students leave school by age " + (lastSchoolAge + 1) + " at the latest");
    }

    private static int indexOf(String[] header, String name) {
        for (int i = 0; i < header.length; i++) if (header[i].trim().equals(name)) return i;
        throw new RuntimeException("Column " + name + " missing in the education transitions file");
    }

    @Override
    public Collection<EducationEvent> getEventsForCurrentYear(int year) {
        final List<EducationEvent> events = new ArrayList<>();
        startAge.clear();
        for (Person person : dataContainer.getHouseholdDataManager().getPersons()) {
            final Occupation occ = person.getOccupation();
            final int age = person.getAge();
            if (occ == Occupation.TODDLER && age >= SCHOOL_ENTRY_AGE) {
                events.add(new EducationEvent(person.getId()));
            } else if (occ == Occupation.STUDENT && SchoolDataMd.SEAT_RELEASE && schoolData != null && person instanceof PersonWithSchool
                    && schoolData.bandChangeDue((PersonWithSchool) person, age + 1)) {
                startAge.put(person.getId(), age);   // the band of the age at the end of the year (after this year's birthday)
                events.add(new EducationEvent(person.getId()));
            } else if (occ == Occupation.STUDENT && (age > lastSchoolAge || schoolExit[Math.min(age, MAX_AGE)] > 0
                    || schoolChangeDue(person))) {
                events.add(new EducationEvent(person.getId()));
            } else if ((occ == Occupation.EMPLOYED || occ == Occupation.UNEMPLOYED) && (retireEmployed[Math.min(age, MAX_AGE)] > 0 || retireUnemployed[Math.min(age, MAX_AGE)] > 0)) {
                events.add(new EducationEvent(person.getId()));
            }
        }
        return events;
    }

    /** A student needs a (new) school: no school record, or the age reached the next grade band. */
    private boolean schoolChangeDue(Person person) {
        if (schoolData == null || !(person instanceof PersonWithSchool)) return false;
        return schoolData.bandChangeDue((PersonWithSchool) person);
    }

    /** Gives the student the nearest school of the band for the age (releasing the seat held so far). */
    private void assignSchool(Person person) {
        if (schoolData == null || !(person instanceof PersonWithSchool)) return;
        final PersonWithSchool pp = (PersonWithSchool) person;
        final int band = SchoolDataMd.bandForAge(person.getAge());
        final School school = schoolData.assignSchool(pp, band);
        if (school == null && noSchoolWarnings++ < 20) {
            logger.warn("Person " + person.getId() + " (age " + person.getAge() + ") found no school of band " + band);
        }
    }

    @Override
    public boolean handleEvent(EducationEvent event) {
        final Person person = dataContainer.getHouseholdDataManager().getPersonFromId(event.getPersonId());
        if (person == null) return false;
        final int age = Math.min(person.getAge(), MAX_AGE);
        switch (person.getOccupation()) {
            case TODDLER:
                person.setOccupation(Occupation.STUDENT);
                person.setIncome(0);
                assignSchool(person);
                return true;
            case STUDENT:
                if (age > lastSchoolAge || random.nextDouble() < schoolExit[age]) {
                    person.setOccupation(Occupation.UNEMPLOYED);
                    person.setWorkplace(-1);
                    if (schoolData != null && person instanceof PersonWithSchool) {
                        schoolData.releaseSchool((PersonWithSchool) person);
                        ((PersonWithSchool) person).setSchoolType(0);
                    }
                    if (person.getId() == SiloUtil.trackPp) SiloUtil.trackWriter.println("Person " + person.getId() + " left school at age " + age);
                    return true;
                }
                final Integer a0 = startAge.get(person.getId());
                if (a0 != null) {   // 2026-11-19d: band of the age reached during this year
                    if (schoolData.bandChangeDue((PersonWithSchool) person, a0 + 1)) {
                        final School s = schoolData.assignSchool((PersonWithSchool) person, SchoolDataMd.bandForAge(a0 + 1));
                        if (s == null && noSchoolWarnings++ < 20) logger.warn("Person " + person.getId() + " found no school of band " + SchoolDataMd.bandForAge(a0 + 1));
                        return true;
                    }
                    return false;
                }
                if (schoolChangeDue(person)) {
                    assignSchool(person);
                    return true;
                }
                return false;
            case EMPLOYED:
            case UNEMPLOYED:
                final boolean unemployed = person.getOccupation() == Occupation.UNEMPLOYED;
                final double p = unemployed ? retireUnemployed[age] : retireEmployed[age];
                if (random.nextDouble() < p) {
                    final int last = person.getAnnualIncome();
                    if (!unemployed && person.getJobId() > 0) {
                        dataContainer.getJobDataManager().quitJob(true, person);
                    }
                    person.setOccupation(Occupation.RETIREE);
                    person.setWorkplace(-1);
                    person.setIncome(Math.max((int) Math.round(last * replacement), retireeFloor));
                    if (person.getId() == SiloUtil.trackPp) SiloUtil.trackWriter.println("Person " + person.getId() + " retired at age " + age);
                    return true;
                }
                return false;
            default:
                return false;
        }
    }

    @Override
    public void prepareYear(int year) {}

    @Override
    public void endYear(int year) {}

    @Override
    public void endSimulation() {}
}
