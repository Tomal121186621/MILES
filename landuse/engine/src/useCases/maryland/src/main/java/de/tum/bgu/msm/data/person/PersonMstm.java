package de.tum.bgu.msm.data.person;

import de.tum.bgu.msm.data.household.Household;
import de.tum.bgu.msm.schools.PersonWithSchool;

import java.util.Optional;

/**
 * Maryland person. Baltimore 2026, stage 2b: implements {@link PersonWithSchool} so that every student points at a
 * record of the school file (schoolId > 0), has no school (-1) or is a student without a school record yet (-2, the
 * school type then follows from the age). schoolType: 1 elementary (K-5), 2 middle and high (6-12), 3 post-secondary.
 */
public final class PersonMstm implements PersonWithSchool {

    private final Person delegate;
    private Race race;
    private int schoolType = 0;
    private int schoolPlace = 0;
    private int schoolId = -1;

    PersonMstm(int id, int age, Gender gender, Occupation occupation,
               PersonRole role, int jobId, int income) {
        delegate = new PersonImpl(id, age, gender, occupation, role, jobId, income);
    }

    @Override
    public void setHousehold(Household householdId) {
        delegate.setHousehold(householdId);
    }

    @Override
    public Household getHousehold() {
        return delegate.getHousehold();
    }

    @Override
    public void setRole(PersonRole pr) {
        delegate.setRole(pr);
    }

    @Override
    public void birthday() {
        delegate.birthday();
    }

    @Override
    public void setIncome(int newIncome) {
        delegate.setIncome(newIncome);
    }

    @Override
    public void setWorkplace(int newWorkplace) {
        delegate.setWorkplace(newWorkplace);
    }

    @Override
    public void setOccupation(Occupation newOccupation) {
        final Occupation old = delegate.getOccupation();
        delegate.setOccupation(newOccupation);
        // Baltimore 2026 (2026-11-19d, school.seat.release): a student who stops being a student (school exit, job) frees the seat
        final java.util.function.Consumer<PersonMstm> l = studentExitListener;
        if (l != null && old == Occupation.STUDENT && newOccupation != Occupation.STUDENT) l.accept(this);
    }

    /** Baltimore 2026 (2026-11-19d): set by SchoolDataMd when school.seat.release = true; null = none */
    public static volatile java.util.function.Consumer<PersonMstm> studentExitListener = null;

    @Override
    public int getId() {
        return delegate.getId();
    }

    @Override
    public int getAge() {
        return delegate.getAge();
    }

    @Override
    public Gender getGender() {
        return delegate.getGender();
    }

    @Override
    public Occupation getOccupation() {
        return delegate.getOccupation();
    }

    private int lastWage = -1;

    @Override

    public int getLastWage() { return lastWage; }

    @Override

    public void setLastWage(int wage) { this.lastWage = wage; }

    private int benefitYears = 0;   // Baltimore 2026: see Person.getBenefitYears

    @Override
    public int getBenefitYears() { return benefitYears; }

    @Override
    public void setBenefitYears(int years) { this.benefitYears = years; }


    @Override
    public int getAnnualIncome() {
        return delegate.getAnnualIncome();
    }

    @Override
    public PersonType getType() {
        return delegate.getType();
    }

    @Override
    public PersonRole getRole() {
        return delegate.getRole();
    }

    @Override
    public int getJobId() {
        return delegate.getJobId();
    }

    @Override
    public void setDriverLicense(boolean driverLicense) {
        delegate.setDriverLicense(driverLicense);
    }

    @Override
    public boolean hasDriverLicense() {
        return delegate.hasDriverLicense();
    }

    public Race getRace() {
        return race;
    }

    @Override
    public void setSchoolType(int schoolType) {
        this.schoolType = schoolType;
    }

    @Override
    public int getSchoolType() {
        return schoolType;
    }

    @Override
    public void setSchoolPlace(int schoolPlace) {
        this.schoolPlace = schoolPlace;
    }

    @Override
    public int getSchoolPlace() {
        return schoolPlace;
    }

    @Override
    public int getSchoolId() {
        return schoolId;
    }

    @Override
    public void setSchoolId(int schoolId) {
        this.schoolId = schoolId;
    }

    @Override
    public String toString() {
        return delegate
                + "\nRace                 " + race
                + "\nSchool type          " + schoolType
                + "\nSchool id            " + schoolId;
    }

    public void setRace(Race race) {
        this.race = race;
    }

    @Override
    public Optional<Object> getAttribute(String key) {
        return delegate.getAttribute(key);
    }

    @Override
    public void setAttribute(String key, Object value) {
        delegate.setAttribute(key, value);
    }
}
