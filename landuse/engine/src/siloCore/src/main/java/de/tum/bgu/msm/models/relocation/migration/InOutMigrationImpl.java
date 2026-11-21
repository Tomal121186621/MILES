package de.tum.bgu.msm.models.relocation.migration;

import de.tum.bgu.msm.common.datafile.TableDataSet;
import de.tum.bgu.msm.container.DataContainer;
import de.tum.bgu.msm.data.dwelling.Dwelling;
import java.util.HashMap;
import java.util.Collections;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import de.tum.bgu.msm.data.household.HouseholdDataManager;
import de.tum.bgu.msm.data.household.Household;
import de.tum.bgu.msm.data.job.JobDataManager;
import de.tum.bgu.msm.data.person.Occupation;
import de.tum.bgu.msm.data.person.Person;
import de.tum.bgu.msm.events.impls.household.MigrationEvent;
import de.tum.bgu.msm.models.AbstractModel;
import de.tum.bgu.msm.models.autoOwnership.CreateCarOwnershipModel;
import de.tum.bgu.msm.models.demography.driversLicense.DriversLicenseModel;
import de.tum.bgu.msm.models.demography.employment.EmploymentModel;
import de.tum.bgu.msm.models.relocation.moves.MovesModel;
import de.tum.bgu.msm.models.relocation.moves.MovesModelImpl;
import de.tum.bgu.msm.properties.Properties;
import de.tum.bgu.msm.properties.modules.MovesProperties;
import de.tum.bgu.msm.utils.SiloUtil;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

import java.util.*;

/**
 * Adds exogenously given inmigrating and outmigrating households
 * Author: Rolf Moeckel, PB Albuquerque
 * Created on 15 January 2010 in Albuquerque
 **/
public class InOutMigrationImpl extends AbstractModel implements InOutMigration {

    private final static Logger logger = LogManager.getLogger(InOutMigrationImpl.class);

    private final EmploymentModel employment;
    private final MovesModel movesModel;
    private final CreateCarOwnershipModel carOwnership;
    private final DriversLicenseModel driversLicense;

    private MovesProperties.PopulationControlTotalMethod populationControlMethod;
    private TableDataSet tblInOutMigration;
    private TableDataSet tblPopulationTarget;
    // Baltimore 2026: per-region population control (regions = counties in Maryland)
    private final Map<Integer, Map<Integer, Integer>> targetByYearByRegion = new HashMap<>();   // year -> region -> persons
    private final Map<Integer, Integer> targetRegionOfInmigrant = new HashMap<>();              // clone household id -> region
    private int outMigrationPPCounter;
    // Baltimore 2026-11-16: out-migration propensity by age of the householder (oldest member) for the regional control
    private int[] owFrom, owTo; private double[] owWeight; private double owMax = 0;
    private int inMigrationPPCounter;
    // Baltimore 2026-11-17: persons arriving from outside per person and year by region (gross control of the end-of-year pass)
    private final Map<Integer, Double> inmigrationRate = new HashMap<>();
    private int lackOfDwellingFailedInmigration;
    private final java.util.TreeMap<Integer, Integer> failedByRegion = new java.util.TreeMap<>();   // Baltimore 2026 (2026-10-29): unplaced in-migrants by target region


    public InOutMigrationImpl( DataContainer dataContainer, EmploymentModel employment,
							   MovesModel movesModel, CreateCarOwnershipModel carOwnership,
							   DriversLicenseModel driversLicense, Properties properties, Random random) {
        super(dataContainer, properties, random);
        this.employment = employment;
        this.movesModel = movesModel;
        this.carOwnership = carOwnership;
        this.driversLicense = driversLicense;
    }


    @Override
    public void setup() {
        populationControlMethod = properties.moves.populationControlTotal;
        if (!properties.moves.outmigrationAgeWeightsFile.isEmpty()) {
            final TableDataSet w = SiloUtil.readCSVfile(properties.main.baseDirectory + properties.moves.outmigrationAgeWeightsFile);
            final int n = w.getRowCount(); owFrom = new int[n]; owTo = new int[n]; owWeight = new double[n];
            for (int i = 0; i < n; i++) {
                owFrom[i] = (int) w.getValueAt(i + 1, "age_from"); owTo[i] = (int) w.getValueAt(i + 1, "age_to");
                owWeight[i] = w.getValueAt(i + 1, "weight"); owMax = Math.max(owMax, owWeight[i]);
            }
            logger.info("Out-migration of the regional control weighted by the householder's age: " + n + " age bands from " + properties.moves.outmigrationAgeWeightsFile);
        }
        if (!properties.moves.populationControlInmigrationRateFile.isEmpty()) {
            final TableDataSet r = SiloUtil.readCSVfile(properties.main.baseDirectory + properties.moves.populationControlInmigrationRateFile);
            for (int i = 1; i <= r.getRowCount(); i++) inmigrationRate.put((int) r.getValueAt(i, "region"), (double) r.getValueAt(i, "rate"));
            logger.info("Regional control with gross migration: in-migration rates of " + inmigrationRate.size() + " regions from " + properties.moves.populationControlInmigrationRateFile);
        }
        double scaleFactor = properties.main.scaleFactor;
        if (populationControlMethod.equals(MovesProperties.PopulationControlTotalMethod.POPULATION)) {
            String fileName = properties.main.baseDirectory + properties.moves.populationCOntrolTotalFile;
            tblPopulationTarget = SiloUtil.readCSVfile(fileName);
            tblPopulationTarget.buildIndex(tblPopulationTarget.getColumnPosition("Year"));
            if (scaleFactor != 1.) {
                int periodLength = properties.main.endYear - properties.main.startYear + 1;
                for (int i = 0; i < periodLength; i++) {
                    int scaledPopulation = (int) (tblPopulationTarget.getValueAt(i + 1, "Population") * scaleFactor);
                    tblPopulationTarget.setValueAt(i + 1, "Population", scaledPopulation);
                }
            }
        } else if (populationControlMethod.equals(MovesProperties.PopulationControlTotalMethod.MIGRATION)) {
            String fileName = properties.main.baseDirectory + properties.moves.migrationFile;
            tblInOutMigration = SiloUtil.readCSVfile(fileName);
            tblInOutMigration.buildIndex(tblInOutMigration.getColumnPosition("Year"));
            if (scaleFactor != 1.) {
                int periodLength = properties.main.endYear - properties.main.startYear + 1;
                for (int i = 0; i < periodLength; i++) {
                    int scaledInmigration = (int) (tblInOutMigration.getValueAt(i + 1, "Inmigration") * scaleFactor);
                    tblInOutMigration.setValueAt(i + 1, "Inmigration", scaledInmigration);
                    int scaledOutmigration = (int) (tblInOutMigration.getValueAt(i + 1, "Outmigration") * scaleFactor);
                    tblInOutMigration.setValueAt(i + 1, "Outmigration", scaledOutmigration);
                }
            }
        } else if (populationControlMethod.equals(MovesProperties.PopulationControlTotalMethod.RATE)) {
            tblPopulationTarget = new TableDataSet();
            int periodLength = properties.main.endYear - properties.main.startYear + 1;
            int[] years = new int[periodLength];
            int[] populationByYear = new int[periodLength];
            int populationBaseYear = dataContainer.getHouseholdDataManager().getPersons().size();
            for (int i = 0; i < periodLength; i++) {
                years[i] = properties.main.startYear + i;
                populationByYear[i] = (int) Math.round(populationBaseYear * Math.pow(1 + properties.moves.populationGrowthRateInPercentage / 100, i));
            }
            tblPopulationTarget.appendColumn(years, "Year");
            tblPopulationTarget.appendColumn(populationByYear, "Population");
            tblPopulationTarget.buildIndex(tblPopulationTarget.getColumnPosition("Year"));


        } else if (populationControlMethod.equals(MovesProperties.PopulationControlTotalMethod.REGION)) {
            // Baltimore 2026: file in long format with a header Year,Region,Population
            final String fileName = properties.main.baseDirectory + properties.moves.populationControlTotalByRegionFile;
            final TableDataSet t = SiloUtil.readCSVfile(fileName);
            for (int row = 1; row <= t.getRowCount(); row++) {
                final int y = (int) t.getValueAt(row, "Year"), r = (int) t.getValueAt(row, "Region");
                final int pop = (int) Math.round(t.getValueAt(row, "Population") * scaleFactor);
                targetByYearByRegion.computeIfAbsent(y, k -> new HashMap<>()).put(r, pop);
            }
            logger.info("Population control by region: " + targetByYearByRegion.size() + " years from " + fileName);
        } else {
            final String message
                    = "Unknown property found for population.control.total, set to population or migration";
            logger.error(message);
            throw new RuntimeException(message);
        }
    }

    @Override
    public void prepareYear(int year) {
        lackOfDwellingFailedInmigration = 0;
        failedByRegion.clear();
    }

    /** Baltimore 2026-11-16: a household of the region to leave the state. Uniform as before, or, with outmigration.age.weights.file,
     *  in proportion to the out-migration propensity of the householder's age (age of the oldest member; rejection sampling). */
    private Household drawLeavingHousehold(List<Household> hhs) {
        if (owMax <= 0) return hhs.get((int) (hhs.size() * random.nextDouble()));
        for (int k = 0; k < 10000; k++) {
            final Household h = hhs.get((int) (hhs.size() * random.nextDouble()));
            int age = 0;
            for (Person p : h.getPersons().values()) age = Math.max(age, p.getAge());
            double w = owWeight[owWeight.length - 1];
            for (int i = 0; i < owFrom.length; i++) if (age >= owFrom[i] && age <= owTo[i]) { w = owWeight[i]; break; }
            if (age < owFrom[0]) w = owWeight[0];
            if (random.nextDouble() * owMax < w) return h;
        }
        return hhs.get((int) (hhs.size() * random.nextDouble()));
    }

    /** Baltimore 2026: households grouped by the region of their dwelling */
    private Map<Integer, List<Household>> householdsByRegion() {
        final Map<Integer, List<Household>> byRegion = new HashMap<>();
        for (Household hh : dataContainer.getHouseholdDataManager().getHouseholds()) {
            final Dwelling dd = dataContainer.getRealEstateDataManager().getDwelling(hh.getDwellingId());
            if (dd == null) continue;
            final int region = dataContainer.getGeoData().getZones().get(dd.getZoneId()).getRegion().getId();
            byRegion.computeIfAbsent(region, k -> new ArrayList<>()).add(hh);
        }
        return byRegion;
    }

    /** Baltimore 2026: in- and out-migrants per region so that every region reaches its own population target */
    private void migrateByRegion(int year, List<MigrationEvent> events) {
        final HouseholdDataManager householdDataManager = dataContainer.getHouseholdDataManager();
        // the year loop simulates the change from `year` to `year + 1`: aim at next year's target (the base year equals its own)
        final Map<Integer, Integer> targets = targetByYearByRegion.getOrDefault(year + 1, targetByYearByRegion.get(year));
        if (targets == null) {
            logger.warn("No regional population targets for year " + (year + 1) + "; no migration generated");
            return;
        }
        final Map<Integer, List<Household>> byRegion = householdsByRegion();
        int in = 0, out = 0;
        for (Map.Entry<Integer, Integer> e : targets.entrySet()) {
            final int region = e.getKey(), target = e.getValue();
            final List<Household> hhs = byRegion.getOrDefault(region, Collections.emptyList());
            if (hhs.isEmpty()) continue;
            int current = 0;
            for (Household hh : hhs) current += hh.getHhSize();
            if (target < current) {
                int created = 0;
                while (created < current - target) {
                    final Household h = drawLeavingHousehold(hhs);
                    events.add(new MigrationEvent(h, MigrationEvent.Type.OUT));
                    created += h.getHhSize();
                }
                out += created;
            } else if (target > current) {
                int created = 0;
                while (created < target - current) {
                    final Household h = hhs.get((int) (hhs.size() * random.nextDouble()));
                    final Household clone = householdDataManager.duplicateHousehold(h);
                    targetRegionOfInmigrant.put(clone.getId(), region);
                    events.add(new MigrationEvent(clone, MigrationEvent.Type.IN));
                    created += clone.getHhSize();
                }
                in += created;
            }
        }
        logger.info("  Regional population control " + year + ": " + in + " in-migrants and " + out + " out-migrants proposed over " + targets.size() + " regions");
    }

    /** Baltimore 2026, second pass of the regional control: after all events of the year (residential moves between regions
     *  included) the remaining gap of every region to its target is closed by out-migrating or in-migrating (cloning) randomly
     *  selected households of that region, so the region totals hold at the end of the year.
     *  2026-11-17, with population.control.inmigration.rate.file: gross migration.  A listed region out-migrates rate x population
     *  plus its decline to the target and then clones in households of its own until the target holds (rate x population plus its
     *  growth), so a declining region also receives in-migrants from outside, of its own composition.  Net only (before): a region
     *  with a falling target only lost households and its vacancies were filled by movers from other regions. */
    private void closeRegionalGaps(int year) {
        final Map<Integer, Integer> targets = targetByYearByRegion.getOrDefault(year + 1, targetByYearByRegion.get(year));
        if (targets == null) return;
        final HouseholdDataManager householdDataManager = dataContainer.getHouseholdDataManager();
        final Map<Integer, List<Household>> byRegion = householdsByRegion();
        int in = 0, out = 0, failed = 0, gross = 0;
        for (Map.Entry<Integer, Integer> e : targets.entrySet()) {
            final int region = e.getKey(), target = e.getValue();
            final List<Household> hhs = byRegion.getOrDefault(region, Collections.emptyList());
            if (hhs.isEmpty()) continue;
            int current = 0;
            for (Household hh : hhs) current += hh.getHhSize();
            final int exchange = (int) Math.round(inmigrationRate.getOrDefault(region, 0.) * current);
            gross += exchange;
            int attempts = 0, removed = 0;
            final int toRemove = exchange + Math.max(current - target, 0);
            while (removed < toRemove && attempts++ < 5 * hhs.size()) {
                final Household h = drawLeavingHousehold(hhs);
                if (householdDataManager.getHouseholdFromId(h.getId()) == null) continue;   // already out-migrated
                final int size = h.getHhSize();
                if (outMigrateHh(h.getId(), true)) removed += size;
            }
            out += removed;
            final int toAdd = target - (current - removed);
            int added = 0, consecutiveFailures = 0;
            final boolean untilNoVac = properties.moves.populationControlUntilNoVacancy;   // 2026-11-19a
            while (added < toAdd && (untilNoVac ? consecutiveFailures < 10000 && dataContainer.getRealEstateDataManager().getNumberOfVacantDDinRegion(region) > 0
                    : consecutiveFailures < 20)) {   // a region without vacant dwellings cannot grow further this year
                final Household h = hhs.get((int) (hhs.size() * random.nextDouble()));
                if (householdDataManager.getHouseholdFromId(h.getId()) == null) continue;   // out-migrated households are not copied
                final Household clone = householdDataManager.duplicateHousehold(h);
                targetRegionOfInmigrant.put(clone.getId(), region);
                if (inmigrateHh(clone)) { added += clone.getHhSize(); consecutiveFailures = 0; } else { failed++; consecutiveFailures++; }
            }
            in += added;
        }
        logger.info("  Regional population control " + year + ", end-of-year pass: " + in + " in-migrants and " + out + " out-migrants"
                + (gross > 0 ? " (gross exchange with outside " + gross + ")" : "") + (failed > 0 ? " (" + failed + " in-migrations without a dwelling)" : ""));
    }

    private void createInmigrants(int year, List<MigrationEvent> events, Household[] hhs) {
        HouseholdDataManager householdDataManager = dataContainer.getHouseholdDataManager();
        int inmigrants = 0;
        if (populationControlMethod.equals(MovesProperties.PopulationControlTotalMethod.MIGRATION)) {
            inmigrants = (int) tblInOutMigration.getIndexedValueAt(year, "Inmigration");
        } else {
            int currentPopulation = householdDataManager.getPersons().size();
            int target = (int) tblPopulationTarget.getIndexedValueAt(year, "Population");
            if (target > currentPopulation) {
                inmigrants = target - currentPopulation;
            }
        }
        int createdInmigrants = 0;
        while (createdInmigrants < inmigrants) {
            Household hh = hhs[(int) (hhs.length * this.random.nextDouble())];
            Household inmigratingHousehold = householdDataManager.duplicateHousehold(hh);
            events.add(new MigrationEvent(inmigratingHousehold, MigrationEvent.Type.IN));
            createdInmigrants += inmigratingHousehold.getHhSize();
        }
    }

    private void createOutmigrants(int year, List<MigrationEvent> events, Household[] hhs) {
        HouseholdDataManager householdDataManager = dataContainer.getHouseholdDataManager();
        int outmigrants = 0;
        if (populationControlMethod.equals(MovesProperties.PopulationControlTotalMethod.MIGRATION)) {
            outmigrants = (int) tblInOutMigration.getIndexedValueAt(year, "Outmigration");
        } else {
            int currentPopulation = householdDataManager.getPersons().size();
            int target = (int) tblPopulationTarget.getIndexedValueAt(year, "Population");
            if (target < currentPopulation) {
                outmigrants = currentPopulation - target;
            }
        }

        int createdOutMigrants = 0;
        while (createdOutMigrants < outmigrants) {
            Household selectedHousehold = hhs[(int) (hhs.length * this.random.nextDouble())];
            events.add(new MigrationEvent(selectedHousehold, MigrationEvent.Type.OUT));
            createdOutMigrants += selectedHousehold.getHhSize();

        }
    }

    @Override
    public Collection<MigrationEvent> getEventsForCurrentYear(int year) {
        final List<MigrationEvent> events = new ArrayList<>();

        logger.info("  Selecting outmigrants and creating inmigrants for the year " + year);
        final HouseholdDataManager householdDataManager = dataContainer.getHouseholdDataManager();

        if (populationControlMethod.equals(MovesProperties.PopulationControlTotalMethod.REGION)) {
            // Baltimore 2026: per-region targets replace the single regional total
            targetRegionOfInmigrant.clear();
            // 2026-11-17: the start-of-year proposal aimed at next year's target before the births and deaths of the year, so about the
            // natural increase was cloned in at the start (filling vacancies before the residential moves) and removed again at the end
            if (!properties.moves.populationControlEndOfYearOnly) migrateByRegion(year, events);
            else logger.info("  Regional population control " + year + ": end-of-year pass only (population.control.end.of.year.only)");
            outMigrationPPCounter = 0;
            inMigrationPPCounter = 0;
            return events;
        }
        Household[] hhs = householdDataManager.getHouseholds().toArray(new Household[0]);

        createOutmigrants(year, events, hhs);
        createInmigrants(year, events, hhs);

        outMigrationPPCounter = 0;
        inMigrationPPCounter = 0;

        return events;
    }

    @Override
    public boolean handleEvent(MigrationEvent event) {
        MigrationEvent.Type type = event.getType();
        switch (type) {
            case IN:
                return inmigrateHh(event.getHousehold());
            case OUT:
                return outMigrateHh(event.getHousehold().getId(), true);
            default:
                return false;
        }
    }

    private boolean inmigrateHh(Household hh) {
        // Inmigrate household with hhId from HashMap inmigratingHhData<Integer, int[]>


        HouseholdDataManager householdDataManager = dataContainer.getHouseholdDataManager();

        // Searching for employment has to be in a separate loop from setting up all persons, as finding a
        // job will change the household income and household type, which can only be calculated after all
        // persons are set up.
        // Baltimore 2026: under the regional control an in-migrant is placed inside its target region; the dwelling is searched
        // first, so that a household that finds no dwelling takes no job (its persons are discarded with it)
        Integer targetRegion = targetRegionOfInmigrant.remove(hh.getId());
        // 2026-11-19a (population.control.until.no.vacancy): a target region without any vacancy -> search without the region restriction
        if (targetRegion != null && properties.moves.populationControlUntilNoVacancy
                && dataContainer.getRealEstateDataManager().getNumberOfVacantDDinRegion(targetRegion) == 0) targetRegion = null;
        final int newDdId = targetRegion == null ? movesModel.searchForNewDwelling(hh)
                : movesModel.searchForNewDwelling(hh, dataContainer.getGeoData().getRegions().get(targetRegion));
        if (newDdId > 0) {
            // Baltimore 2026: the household and its persons are registered and placed in their dwelling before the job search:
            // EmploymentModel.lookForJob finds the person by id and searches from the home zone, so before this order the
            // copies never searched (person not yet registered) and kept the job id of the person they were copied from
            householdDataManager.addHousehold(hh);
            for (Person person : hh.getPersons().values()) {
                householdDataManager.addPerson(person);
            }
            movesModel.moveHousehold(hh, -1, newDdId);
            for (Person person : hh.getPersons().values()) {
                if (person.getOccupation() == Occupation.EMPLOYED) {
                    // the copy does not hold the job of the person it was copied from (the inherited job id made 11 % of the
                    // employed of 2024 point to another person's job); it searches a job of its own and keeps its earnings as
                    // the wage to return to; without a job it arrives unemployed (benefit rule as at a job loss)
                    if (person.getJobId() > 0) {
                        person.setWorkplace(-1);
                    }
                    person.setLastWage(person.getAnnualIncome());
                    employment.lookForJob(person.getId());
                    if (person.getJobId() < 1) {
                        person.setOccupation(Occupation.UNEMPLOYED);
                        person.setIncome(Math.min(person.getAnnualIncome() / 2, 22360));
                        person.setBenefitYears(2);
                    }
                }
                driversLicense.checkLicenseCreation(person.getId());
            }
            if (carOwnership != null) {
                carOwnership.simulateCarOwnership(hh); // set initial car ownership of new household
            }
            inMigrationPPCounter += hh.getHhSize();
            if (hh.getId() == SiloUtil.trackHh) {
                SiloUtil.trackWriter.println("Household " + hh.getId() + " inmigrated.");
            }
            return true;
        } else {
            lackOfDwellingFailedInmigration++;
            failedByRegion.merge(targetRegion == null ? -1 : targetRegion, 1, Integer::sum);
            return false;
        }
    }


    @Override
    public boolean outMigrateHh(int hhId, boolean overwriteEventRules) {
        // Household with ID hhId out migrates
        Household hh = dataContainer.getHouseholdDataManager().getHouseholdFromId(hhId);
        if (properties.eventRules.outMigration && !overwriteEventRules || hh == null) {
            return false;
        }
        outMigrationPPCounter += hh.getHhSize();
        if (hhId == SiloUtil.trackHh) {
            SiloUtil.trackWriter.println("Household " + hhId + " outmigrated.");
        }
        JobDataManager jobDataManager = dataContainer.getJobDataManager();
        for (Map.Entry<Integer, ? extends Person> person : hh.getPersons().entrySet()) {
            if (person.getValue().getJobId() > 0) {
                jobDataManager.quitJob(true, person.getValue());
            }
            if (person.getKey() == SiloUtil.trackPp) {
                SiloUtil.trackWriter.println(" Person " + person.getKey() + " outmigrated.");
            }
        }
        dataContainer.getHouseholdDataManager().removeHousehold(hhId);
        return true;
    }

    @Override
    public void endYear(int year) {
        if (populationControlMethod.equals(MovesProperties.PopulationControlTotalMethod.REGION)) {
            closeRegionalGaps(year);
        }
        //todo reconsider to print out model results and how to pass them to the ResultsMonitor
        logger.info("Total Inmigrants: " + inMigrationPPCounter);
        logger.info("Total OutmigrantsPP: " + outMigrationPPCounter);
        if (lackOfDwellingFailedInmigration > 0) {
            logger.warn("  Encountered " + lackOfDwellingFailedInmigration + " cases " +
                    "where household wanted to inmigrate but could not find vacant dwelling.");
            logger.warn("  Unplaced in-migrant households " + year + " by target region (-1 = none): " + failedByRegion);
        }
    }

    @Override
    public void endSimulation() {

    }


}