package de.tum.bgu.msm.properties.modules;

import de.tum.bgu.msm.properties.PropertiesUtil;

import java.util.ResourceBundle;

public final class MovesProperties {

    public final double racialRelevanceInZone;
    public final boolean provideLowIncomeSubsidy;


    public final PopulationControlTotalMethod populationControlTotal;
    public final String populationCOntrolTotalFile;
    public final String migrationFile;
    public final String populationControlTotalByRegionFile;
    public final String outmigrationAgeWeightsFile;
    public final boolean populationControlEndOfYearOnly;
    public final String populationControlInmigrationRateFile;
    public final boolean populationControlUntilNoVacancy;
    public final double populationGrowthRateInPercentage;

    public final boolean trackRelocations;

    public final float B_TIME;
    public final float B_PT;
    public final float B_EXP_HOUSING_UTILITY;
    // move-or-not binomial logit: P(move) = 1 - 1/(1 + shift * exp(scale * (satisfaction - current utility)))
    public final double moveOrNotScale;
    public final double moveOrNotShift;

    public enum PopulationControlTotalMethod {
        POPULATION, MIGRATION, RATE, REGION
    }

    public MovesProperties(ResourceBundle bundle) {
        PropertiesUtil.newPropertySubmodule("Relocation properties - control of population");
        populationControlTotal = PopulationControlTotalMethod.valueOf(
                PropertiesUtil.getStringProperty(bundle, "population.control.total", "rate").toUpperCase());
        populationCOntrolTotalFile = PropertiesUtil.getStringProperty(bundle, "total.population.control.total.file", "input/assumptions/populationControlTotal.csv");
        migrationFile = PropertiesUtil.getStringProperty(bundle, "inmigration.outmigration.file", "input/assumptions/inOutMigration.csv");
        // Baltimore 2026: population control per region (regions = counties in Maryland); long format Year,Region,Population
        populationControlTotalByRegionFile = PropertiesUtil.getStringProperty(bundle, "population.control.total.by.region.file", "input/assumptions/populationControlTotalByRegion.csv");
        // Baltimore 2026-11-16: leaving households of the regional control drawn by the out-migration propensity of the householder's
        // age (CSV age_from,age_to,weight); empty = uniform draw (the behaviour before)
        outmigrationAgeWeightsFile = PropertiesUtil.getStringProperty(bundle, "outmigration.age.weights.file", "");
        // Baltimore 2026-11-17: regional control only in the end-of-year pass (after births, deaths and moves); false = the start-of-year
        // proposal (gap to next year's target before the natural change of the year) plus the end-of-year pass (the behaviour before)
        populationControlEndOfYearOnly = PropertiesUtil.getBooleanProperty(bundle, "population.control.end.of.year.only", false);
        // Baltimore 2026-11-19a: true = the end-of-year pass places in-migrants in a region until its target holds or the region has no
        // vacant dwelling left (a failed placement while vacancies remain does not stop it; safety stop after 10,000 consecutive failures),
        // and an in-migrant whose target region has no vacancy searches without the region restriction; false = stop after 20
        // consecutive failures, no fallback (the behaviour before)
        populationControlUntilNoVacancy = PropertiesUtil.getBooleanProperty(bundle, "population.control.until.no.vacancy", false);
        // Baltimore 2026-11-17: gross migration in the end-of-year pass: CSV region,rate (persons arriving from outside per person and year);
        // a listed region clones rate x population from outside and out-migrates the same number plus its decline to the target; empty =
        // net control only (a region only gains or only loses, the behaviour before)
        populationControlInmigrationRateFile = PropertiesUtil.getStringProperty(bundle, "population.control.inmigration.rate.file", "");
        populationGrowthRateInPercentage = PropertiesUtil.getDoubleProperty(bundle, "population.growth.rate", 0. );

        PropertiesUtil.newPropertySubmodule("Relocation properties - social security parameters MSTM");
        racialRelevanceInZone = PropertiesUtil.getDoubleProperty(bundle, "relevance.of.race.in.zone.of.dwelling", 0.5);
        provideLowIncomeSubsidy = PropertiesUtil.getBooleanProperty(bundle, "provide.housing.subsidy.to.low.inc", false);

        trackRelocations = PropertiesUtil.getBooleanProperty(bundle, "track.relocations", true);

        B_TIME = (float) PropertiesUtil.getDoubleProperty(bundle, "mode.choice.impedance.coefficient", 10f);
        B_PT = (float) PropertiesUtil.getDoubleProperty(bundle, "mode.choice.pt.asc", 0f);
        B_EXP_HOUSING_UTILITY = (float) PropertiesUtil.getDoubleProperty(bundle, "mc.housing.time.coefficient.ratio", 20f);
        moveOrNotScale = PropertiesUtil.getDoubleProperty(bundle, "move.or.not.binomial.log.model.parameter", 10.);
        moveOrNotShift = PropertiesUtil.getDoubleProperty(bundle, "move.or.not.binomial.log.shift.parameter", 0.03);

    }
}
