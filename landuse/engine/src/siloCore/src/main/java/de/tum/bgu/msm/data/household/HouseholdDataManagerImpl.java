/*
 * Copyright  2005 PB Consult Inc.
 *
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 *
 */
package de.tum.bgu.msm.data.household;

import de.tum.bgu.msm.data.dwelling.Dwelling;
import de.tum.bgu.msm.data.dwelling.DwellingData;
import de.tum.bgu.msm.data.dwelling.RealEstateDataManager;
import de.tum.bgu.msm.data.person.Gender;
import de.tum.bgu.msm.data.person.Occupation;
import de.tum.bgu.msm.data.person.Person;
import de.tum.bgu.msm.data.person.PersonFactory;
import de.tum.bgu.msm.io.output.DefaultHouseholdWriter;
import de.tum.bgu.msm.io.output.DefaultPersonWriter;
import de.tum.bgu.msm.properties.Properties;
import de.tum.bgu.msm.util.concurrent.ConcurrentExecutor;
import de.tum.bgu.msm.utils.SiloUtil;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.*;

/**
 * @author Greg Erhardt
 * Created on Dec 2, 2009
 */
public class HouseholdDataManagerImpl implements HouseholdDataManager {

    private final static Logger logger = LogManager.getLogger(HouseholdDataManagerImpl.class);

    private final HouseholdData householdData;
    private final DwellingData dwellingData;

    private final PersonFactory ppFactory;
    private final HouseholdFactory hhFactory;
    private final Properties properties;

    //TODO: get rid of data manager dependecy!
    private final RealEstateDataManager realEstateDataManager;

    private int highestHouseholdIdInUse;
    private int highestPersonIdInUse;

    private float[][][] avgIncomeByGenderByAgeByOccupation;
    private int[][][] baseYearEarningsByGenderByAge;   // Baltimore 2026: incomes of employed persons in the base year, by sex and age
    private int[][][] baseYearNonEmployedIncomeByGenderByAge;   // Baltimore 2026: incomes of non-employed (unemployed) persons in the base year
    private int currentYear;

    private Map<Integer, Household> householdMementos = new LinkedHashMap<>();

    public HouseholdDataManagerImpl(HouseholdData householdData, DwellingData dwellingData,
                                    PersonFactory ppFactory, HouseholdFactory hhFactory,
                                    Properties properties, RealEstateDataManager realEstateDataManager) {
        this.householdData = householdData;
        this.dwellingData = dwellingData;
        this.ppFactory = ppFactory;
        this.hhFactory = hhFactory;
        this.properties = properties;
        this.realEstateDataManager = realEstateDataManager;
    }

    @Override
    public void setup() {
        identifyHighestHouseholdAndPersonId();
        avgIncomeByGenderByAgeByOccupation = calculateIncomeDistribution();
        collectBaseYearEarnings();
        currentYear = properties.main.baseYear;
    }

    @Override
    public void prepareYear(int year) {
        currentYear = year;
    }

    /** Baltimore 2026: base-year incomes of employed persons by sex and single year of age, the pool of drawBaseYearEarnings */
    private void collectBaseYearEarnings() {
        baseYearEarningsByGenderByAge = collectBaseYearIncomes(Occupation.EMPLOYED, true);
        baseYearNonEmployedIncomeByGenderByAge = collectBaseYearIncomes(Occupation.UNEMPLOYED, false);
    }

    private int[][][] collectBaseYearIncomes(Occupation occupation, boolean positiveOnly) {
        final List<List<List<Integer>>> pool = new ArrayList<>();
        for (int g = 0; g < 2; g++) {
            final List<List<Integer>> byAge = new ArrayList<>();
            for (int a = 0; a < 100; a++) byAge.add(new ArrayList<>());
            pool.add(byAge);
        }
        for (Person pp : householdData.getPersons()) {
            if (pp.getOccupation() == occupation && (!positiveOnly || pp.getAnnualIncome() > 0)) {
                pool.get(pp.getGender().ordinal()).get(Math.min(99, pp.getAge())).add(Math.max(0, pp.getAnnualIncome()));
            }
        }
        final int[][][] out = new int[2][100][];
        for (int g = 0; g < 2; g++) {
            for (int a = 0; a < 100; a++) {
                out[g][a] = pool.get(g).get(a).stream().mapToInt(Integer::intValue).toArray();
            }
        }
        return out;
    }

    @Override
    public int drawBaseYearNonEmployedIncome(Gender gender, int age, Random random) {
        final int v = drawFrom(baseYearNonEmployedIncomeByGenderByAge, gender, age, random);
        return v >= 0 ? v : (int) getAverageIncome(gender, Math.max(0, Math.min(99, age)), Occupation.UNEMPLOYED);
    }

    /** a random income of the pool of ages a-2..a+2 (widened until it holds at least 50 incomes); -1 if the pool is empty */
    private static int drawFrom(int[][][] incomes, Gender gender, int age, Random random) {
        final int g = gender.ordinal(), a = Math.max(0, Math.min(99, age));
        for (int w = 2; w < 100; w++) {
            int n = 0;
            for (int x = Math.max(0, a - w); x <= Math.min(99, a + w); x++) n += incomes[g][x].length;
            if (n < 50) continue;
            int k = random.nextInt(n);
            for (int x = Math.max(0, a - w); x <= Math.min(99, a + w); x++) {
                if (k < incomes[g][x].length) return incomes[g][x][k];
                k -= incomes[g][x].length;
            }
        }
        return -1;
    }

    @Override
    public int drawBaseYearEarnings(Gender gender, int age, Random random) {
        final int g = gender.ordinal(), a = Math.max(0, Math.min(99, age));
        // pool of ages a-2..a+2 (widened until it holds at least 50 incomes)
        for (int w = 2; w < 100; w++) {
            int n = 0;
            for (int x = Math.max(0, a - w); x <= Math.min(99, a + w); x++) n += baseYearEarningsByGenderByAge[g][x].length;
            if (n < 50) continue;
            int k = random.nextInt(n);
            for (int x = Math.max(0, a - w); x <= Math.min(99, a + w); x++) {
                final int[] inc = baseYearEarningsByGenderByAge[g][x];
                if (k < inc.length) {
                    final double growth = Math.pow(1 + properties.householdData.realWageGrowthRate, Math.max(0, currentYear - properties.main.baseYear));
                    return (int) Math.round(inc[k] * growth);
                }
                k -= inc.length;
            }
        }
        return (int) getAverageIncome(gender, a, Occupation.EMPLOYED);
    }

    @Override
    public void endYear(int year) {
        householdMementos.clear();
        adjustIncome();

        final String outputDirectory = properties.main.baseDirectory + "scenOutput/" + properties.main.scenarioName;

        if (!Properties.get().householdData.householdIntermediatesFileName.equals("")) {
            String filehh = outputDirectory + "/" + properties.householdData.householdFinalFileName + "_"
                    + year
                    + ".csv";
            new DefaultHouseholdWriter(this.householdData.getHouseholds()).writeHouseholds(filehh);
        }

        if (!Properties.get().householdData.personIntermediatesFileName.equals("")) {
            String filepp = outputDirectory + "/" + properties.householdData.personIntermediatesFileName + "_"
                    + year
                    + ".csv";
            new DefaultPersonWriter(householdData).writePersons(filepp);
        }
    }

    @Override
    public void endSimulation() {
        final String outputDirectory = properties.main.baseDirectory + "scenOutput/" + properties.main.scenarioName;
        String filehh = outputDirectory +"/"+ properties.householdData.householdFinalFileName + "_"
                + properties.main.endYear
                + ".csv";
        new DefaultHouseholdWriter(this.householdData.getHouseholds()).writeHouseholds(filehh);

        String filepp = outputDirectory +"/"+ properties.householdData.personFinalFileName + "_"
                + properties.main.endYear
                + ".csv";
        new DefaultPersonWriter(householdData).writePersons(filepp);
    }

    @Override
    public float getAverageIncome(Gender gender, int age, Occupation occupation) {
        return avgIncomeByGenderByAgeByOccupation[gender.ordinal()][age][occupation==Occupation.EMPLOYED?1:0];
    }

    @Override
    public Household getHouseholdFromId(int householdId) {
        return householdData.getHousehold(householdId);
    }

    @Override
    public Collection<Household> getHouseholds() {
        return Collections.unmodifiableCollection(householdData.getHouseholds());
    }

    @Override
    public Person getPersonFromId(int id) {
        return householdData.getPerson(id);
    }

    /** Baltimore 2026 (2026-11-19d): observer of persons leaving the population (death, out-migration, dissolution); null = none */
    public static volatile java.util.function.Consumer<Person> personRemovalListener = null;

    @Override
    public void removePerson(int id) {
        removePersonFromHousehold(householdData.getPerson(id));
        final java.util.function.Consumer<Person> l = personRemovalListener;
        if (l != null && householdData.getPerson(id) != null) l.accept(householdData.getPerson(id));
        householdData.removePerson(id);
    }

    @Override
    public Collection<Person> getPersons() {
        return householdData.getPersons();
    }

    @Override
    public void removePersonFromHousehold(Person person) {
        Household household = person.getHousehold();
        if (household != null) {
            household.removePerson(person.getId());
            person.setHousehold(null);
            if (household.getPersons().isEmpty()) {
                removeHousehold(household.getId());
            }
            if (household.getId() == SiloUtil.trackHh || person.getId() == SiloUtil.trackPp) {
                SiloUtil.trackWriter.println("Person " +
                        person.getId() + " was removed from household " + household.getId() + ".");
            }
        }
    }

    @Override
    public void addPersonToHousehold(Person person, Household household) {
        // add existing person per (not a newborn child) to household
        if (household.getPersons().containsKey(person.getId())) {
            throw new IllegalArgumentException("Person " + person.getId() + " was already added to household " + household.getId());
        }
        household.addPerson(person);
        person.setHousehold(household);
        if (person.getId() == SiloUtil.trackPp || household.getId() == SiloUtil.trackHh) {
            SiloUtil.trackWriter.println("A person " +
                    "(not a child) named " + person.getId() + " was added to household " + household.getId() + ".");
        }
    }

    @Override
    public int getNextHouseholdId() {
        return ++highestHouseholdIdInUse;
    }

    @Override
    public int getNextPersonId() {
        return ++highestPersonIdInUse;
    }

    @Override
    public int getHighestHouseholdIdInUse() {
        return highestHouseholdIdInUse;
    }

    @Override
    public int getHighestPersonIdInUse() {
        return highestPersonIdInUse;
    }

    @Override
    public void removeHousehold(int householdId) {
        // remove household and add dwelling to vacancy list

        Household household = householdData.getHousehold(householdId);
        int dwellingId = household.getDwellingId();
        if (dwellingId != -1) {
            Dwelling dd = dwellingData.getDwelling(dwellingId);
            dd.setResidentID(-1);
            realEstateDataManager.addDwellingToVacancyList(dd);

        }
        for (Person pp : household.getPersons().values()) {
            pp.setHousehold(null);
            final java.util.function.Consumer<Person> l = personRemovalListener;
            if (l != null) l.accept(pp);
            householdData.removePerson(pp.getId());
        }
        householdData.removeHousehold(householdId);
        householdMementos.remove(householdId);
        if (householdId == SiloUtil.trackHh) {
            SiloUtil.trackWriter.println("Households " + householdId + " was removed");
        }
    }


//    public void summarizePopulation(DataContainer dataContainer) {
//        // summarize population for summary file
//

//
//
//
//
//

//        // labor participation and commuting distance

//        // todo: Add distance in kilometers to this summary
//

//    }

    private void identifyHighestHouseholdAndPersonId() {
        // identify highest household ID and highest person ID in use
        highestHouseholdIdInUse = 0;
        for (Household hh : householdData.getHouseholds()) {
            highestHouseholdIdInUse = Math.max(highestHouseholdIdInUse, hh.getId());
        }
        highestPersonIdInUse = 0;
        for (Person pp : householdData.getPersons()) {
            highestPersonIdInUse = Math.max(highestPersonIdInUse, pp.getId());
        }
    }


    private float[][][] calculateIncomeDistribution() {
        // calculate income distribution by age, gender and occupation

        // income by gender, age and unemployed/employed
        float[][][] averageIncome = new float[2][100][2];
        int[][][] count = new int[2][100][2];
        for (Person pp : householdData.getPersons()) {
            int age = Math.min(99, pp.getAge());
            int occupation = 0;
            if (pp.getOccupation() == Occupation.EMPLOYED) {
                occupation = 1;
            }
            averageIncome[pp.getGender().ordinal()][age][occupation] += pp.getAnnualIncome();
            count[pp.getGender().ordinal()][age][occupation]++;
        }
        for (int i = 0; i < averageIncome.length; i++) {
            for (int j = 0; j < averageIncome[i].length; j++) {
                for (int k = 0; k < averageIncome[i][j].length; k++) {
                    if (count[i][j][k] > 0) {
                        averageIncome[i][j][k] = averageIncome[i][j][k] / count[i][j][k];
                    }
                }
            }
        }
        // smooth out income
        for (int i = 0; i < averageIncome.length; i++) {
            for (int j = 2; j < averageIncome[i].length - 2; j++) {
                for (int k = 0; k < averageIncome[i][j].length; k++) {
                    averageIncome[i][j][k] = (averageIncome[i][j - 2][k] / 4f + averageIncome[i][j - 1][k] / 2f +
                            averageIncome[i][j][k] + averageIncome[i][j + 1][k] / 2f + averageIncome[i][j + 2][k] / 4f) / 2.5f;
                }
            }
        }
        return averageIncome;
    }

    private void adjustIncome() {
        // select who will get a raise or drop in salary
        float[][][] currentIncomeDistribution = calculateIncomeDistribution();
        final double realWageGrowthRate = Properties.get().householdData.realWageGrowthRate;
        final int retireeIncomeFloor = Properties.get().householdData.retireeIncomeFloor;
        // Baltimore 2026 (study notes 8.D 2026-06-15): a CPU-bounded pool instead of an unbounded cached one; with ~12 M persons
        // the cached service exhausted the native threads of the machine.
        ConcurrentExecutor<Void> executor = ConcurrentExecutor.fixedPoolService(Properties.get().householdData.incomeAdjustmentThreads);
        for (Person person : householdData.getPersons()) {
            executor.addTaskToQueue(new IncomeAdjustment(person, currentIncomeDistribution, avgIncomeByGenderByAgeByOccupation, realWageGrowthRate, retireeIncomeFloor, this));   // Baltimore 2026: base-year age profile of earnings
        }
        executor.execute();


    }




    @Override
    public void saveHouseholdMemento(Household hh) {
        Household householdMemento = hhFactory.duplicate(hh, hh.getId());
        //do not confuse with duplicate household. That one changes the id of the hh, while this methods keeps it.
        //similarly, the memento hh should keep the dwelling id of the original, otherwise silo will understand that
        //was always relocated.
        householdMemento.setDwelling(hh.getDwellingId());
        for (Person originalPerson : hh.getPersons().values()) {
            Person personDuplicate = ppFactory.duplicate(originalPerson, getNextPersonId());
            personDuplicate.setRole(originalPerson.getRole());
            addPersonToHousehold(personDuplicate, householdMemento);
        }
        householdMementos.putIfAbsent(hh.getId(), householdMemento);
    }

    /**
     * //TODO
     * @return
     */
    @Override
    public Collection<Household> getHouseholdMementos() {
        return householdMementos.values();
    }

    @Override
    public void addPerson(Person person) {
        householdData.addPerson(person);
    }

    @Override
    public void addHousehold(Household household) {
        householdData.addHousehold(household);
    }

    @Override
    public PersonFactory getPersonFactory() {
        return this.ppFactory;
    }

    @Override
    public HouseholdFactory getHouseholdFactory() {
        return this.hhFactory;
    }

    /**
     * Duplicates the given household by copying household attributes and individual persons.
     * Ids of persons and the household as well as spatial relationships like dwelling, jobs and schools
     * are not copied. Household roles are preserved.
     *
     * @param original the original household to be copied
     * @return a duplication of the original household and its persons
     */
    @Override
    public Household duplicateHousehold(Household original) {
        Household duplicate = hhFactory.duplicate(original, getNextHouseholdId());
        for (Person originalPerson : original.getPersons().values()) {
            Person personDuplicate = ppFactory.duplicate(originalPerson, getNextPersonId());
            personDuplicate.setRole(originalPerson.getRole());
            addPersonToHousehold(personDuplicate, duplicate);
        }
        return duplicate;
    }
}
