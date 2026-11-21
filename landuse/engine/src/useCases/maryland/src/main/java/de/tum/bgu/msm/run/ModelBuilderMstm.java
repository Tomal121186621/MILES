package de.tum.bgu.msm.run;

import de.tum.bgu.msm.container.DataContainer;
import de.tum.bgu.msm.container.ModelContainer;
import de.tum.bgu.msm.data.dwelling.DwellingFactory;
import de.tum.bgu.msm.data.household.HouseholdFactory;
import de.tum.bgu.msm.data.person.PersonFactory;
import de.tum.bgu.msm.matsim.*;
import de.tum.bgu.msm.models.*;
import de.tum.bgu.msm.models.demography.birth.BirthModelImpl;
import de.tum.bgu.msm.models.demography.birth.DefaultBirthStrategy;
import de.tum.bgu.msm.models.demography.birthday.BirthdayModel;
import de.tum.bgu.msm.models.demography.birthday.BirthdayModelImpl;
import de.tum.bgu.msm.models.demography.death.DeathModel;
import de.tum.bgu.msm.models.demography.death.DeathModelImpl;
import de.tum.bgu.msm.models.demography.death.DefaultDeathStrategy;
import de.tum.bgu.msm.models.demography.divorce.DefaultDivorceStrategy;
import de.tum.bgu.msm.models.demography.divorce.DivorceModel;
import de.tum.bgu.msm.models.demography.divorce.DivorceModelImpl;
import de.tum.bgu.msm.models.demography.driversLicense.DefaultDriversLicenseStrategy;
import de.tum.bgu.msm.models.demography.driversLicense.DriversLicenseModel;
import de.tum.bgu.msm.models.demography.driversLicense.DriversLicenseModelImpl;
import de.tum.bgu.msm.models.demography.education.EducationModel;
import de.tum.bgu.msm.models.demography.education.EducationModelImpl;
import de.tum.bgu.msm.models.EducationModelMd;
import de.tum.bgu.msm.models.CarOwnershipModelMd;
import de.tum.bgu.msm.models.MovesStrategyMd;
import de.tum.bgu.msm.models.ScaledConstructionDemandStrategy;
import de.tum.bgu.msm.models.demography.employment.EmploymentModel;
import de.tum.bgu.msm.models.demography.employment.EmploymentModelImpl;
import de.tum.bgu.msm.models.demography.leaveParentalHousehold.DefaultLeaveParentalHouseholdStrategy;
import de.tum.bgu.msm.models.demography.leaveParentalHousehold.LeaveParentHhModel;
import de.tum.bgu.msm.models.demography.leaveParentalHousehold.LeaveParentHhModelImpl;
import de.tum.bgu.msm.models.demography.marriage.DefaultMarriageStrategy;
import de.tum.bgu.msm.models.demography.marriage.MarriageModel;
import de.tum.bgu.msm.models.jobmography.JobMarketUpdate;
import de.tum.bgu.msm.models.jobmography.JobMarketUpdateImpl;
import de.tum.bgu.msm.models.realEstate.construction.DefaultConstructionDemandStrategy;
import de.tum.bgu.msm.models.realEstate.construction.DefaultConstructionLocationStrategy;
import de.tum.bgu.msm.models.realEstate.demolition.DefaultDemolitionStrategy;
import de.tum.bgu.msm.models.realEstate.demolition.DemolitionModel;
import de.tum.bgu.msm.models.realEstate.demolition.DemolitionModelImpl;
import de.tum.bgu.msm.models.realEstate.pricing.DefaultPricingStrategy;
import de.tum.bgu.msm.models.realEstate.pricing.PricingModel;
import de.tum.bgu.msm.models.realEstate.pricing.PricingModelImpl;
import de.tum.bgu.msm.models.realEstate.renovation.DefaultRenovationStrategy;
import de.tum.bgu.msm.models.realEstate.renovation.RenovationModel;
import de.tum.bgu.msm.models.realEstate.renovation.RenovationModelImpl;
import de.tum.bgu.msm.models.relocation.migration.InOutMigrationImpl;
import de.tum.bgu.msm.models.relocation.moves.DefaultDwellingProbabilityStrategy;
import de.tum.bgu.msm.models.relocation.moves.DefaultMovesStrategy;
import de.tum.bgu.msm.models.relocation.moves.MovesModelImpl;
import de.tum.bgu.msm.models.relocation.moves.RegionProbabilityStrategyImpl;
import de.tum.bgu.msm.models.transportModel.TransportModel;
import de.tum.bgu.msm.properties.Properties;
import de.tum.bgu.msm.utils.SiloUtil;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.matsim.api.core.v01.Scenario;
import org.matsim.core.config.Config;
import org.matsim.core.scenario.ScenarioUtils;

public class ModelBuilderMstm {

    private final static Logger logger = LogManager.getLogger(ModelBuilderMstm.class);

    private ModelBuilderMstm() {}

    public static ModelContainer getModelContainerForMstm(DataContainer dataContainer, Properties properties, Config config) {

        PersonFactory ppFactory = dataContainer.getHouseholdDataManager().getPersonFactory();
        HouseholdFactory hhFactory = dataContainer.getHouseholdDataManager().getHouseholdFactory();
        DwellingFactory ddFactory = dataContainer.getRealEstateDataManager().getDwellingFactory();

        final BirthModelImpl birthModel = new BirthModelImpl(dataContainer, ppFactory, properties, new DefaultBirthStrategy(), SiloUtil.provideNewRandom());

        BirthdayModel birthdayModel = new BirthdayModelImpl(dataContainer, properties, SiloUtil.provideNewRandom());

        DeathModel deathModel = new DeathModelImpl(dataContainer, properties, new DefaultDeathStrategy(), SiloUtil.provideNewRandom());

        final HousingStrategyMstm housingStrategy = new HousingStrategyMstm(
                properties,
                dataContainer,
                dataContainer.getTravelTimes(),
                new DefaultDwellingProbabilityStrategy(),
                new DwellingUtilityStrategyMstm(),
                new RegionUilityStrategyMstm(), new RegionProbabilityStrategyImpl());

        MovesModelImpl movesModel = new MovesModelMd(dataContainer, properties,
                new MovesStrategyMd(properties.moves.moveOrNotScale, properties.moves.moveOrNotShift), housingStrategy, SiloUtil.provideNewRandom());   // Baltimore 2026: calibratable move-or-not; stage 2b: students follow the household to the nearest school
        // Baltimore 2026: data-driven car ownership for new households and for households whose composition changed
        CarOwnershipModelMd carOwnership = new CarOwnershipModelMd(dataContainer, dataContainer.getAccessibility(), properties, SiloUtil.provideNewRandom());


        DivorceModel divorceModel = new DivorceModelImpl(
                dataContainer, movesModel, carOwnership, hhFactory,
                properties, new DefaultDivorceStrategy(), SiloUtil.provideNewRandom());

        // 2026-11-15b: drivers.license.targets.file set = Maryland age profile (DriversLicenseModelMd); unset = the model of record.
        // One provideNewRandom() call either way, so the random streams of the other models stay as in the runs of record.
        final String licenceTargets = de.tum.bgu.msm.models.resloc.ReslocProperties.path("drivers.license.targets.file", null);
        DriversLicenseModel driversLicenseModel = licenceTargets == null
                ? new DriversLicenseModelImpl(dataContainer, properties, new DefaultDriversLicenseStrategy(), SiloUtil.provideNewRandom())
                : new de.tum.bgu.msm.models.DriversLicenseModelMd(dataContainer, properties, licenceTargets, SiloUtil.provideNewRandom());

        // Baltimore 2026: age-triggered school entry, school exit and retirement from a data file (EducationModelMd)
        EducationModel educationModel = new EducationModelMd(dataContainer, properties, SiloUtil.provideNewRandom());

        EmploymentModel employmentModel = new EmploymentModelImpl(dataContainer, properties, SiloUtil.provideNewRandom());

        LeaveParentHhModel leaveParentsModel = new LeaveParentHhModelImpl(dataContainer, movesModel,
                carOwnership, hhFactory, properties, new DefaultLeaveParentalHouseholdStrategy(), SiloUtil.provideNewRandom());

        JobMarketUpdate jobMarketUpdateModel = new JobMarketUpdateImpl(dataContainer, properties, SiloUtil.provideNewRandom());

        ConstructionModelMstm construction = new ConstructionModelMstm(dataContainer, ddFactory,
                properties, new DefaultConstructionLocationStrategy(), new ScaledConstructionDemandStrategy(properties.realEstate.constructionDemandScaler, properties.realEstate.constructionDemandScalersFile.isBlank() ? null : properties.main.baseDirectory + properties.realEstate.constructionDemandScalersFile), SiloUtil.provideNewRandom());   // Baltimore 2026: calibrated to building permits


        // Baltimore 2026-11-17: structural vacancy by region from the 2016 base stock (pricing and the search availability of ReslocModel;
        // construction keeps the dwelling-type defaults, its scalers are calibrated to the building permits)
        if (!properties.realEstate.structuralVacancyFile.isBlank())
            de.tum.bgu.msm.data.dwelling.StructuralVacancy.load(properties.main.baseDirectory + properties.realEstate.structuralVacancyFile);
        PricingModel pricing = new PricingModelImpl(dataContainer, properties, new DefaultPricingStrategy(), SiloUtil.provideNewRandom());

        RenovationModel renovation = new RenovationModelImpl(dataContainer, properties, new DefaultRenovationStrategy(), SiloUtil.provideNewRandom());

        ConstructionOverwriteMstm constructionOverwrite = new ConstructionOverwriteMstm(dataContainer, ddFactory, properties, SiloUtil.provideNewRandom());

        InOutMigrationImpl inOutMigration = new InOutMigrationImpl(dataContainer, employmentModel, movesModel,
                carOwnership, driversLicenseModel, properties, SiloUtil.provideNewRandom());

        DemolitionModel demolition = new DemolitionModelImpl(dataContainer, movesModel,
                inOutMigration, properties, new DefaultDemolitionStrategy(), SiloUtil.provideNewRandom());

        MarriageModel marriageModel = new MarriageModelMstm(dataContainer, movesModel, inOutMigration,
                carOwnership, hhFactory, properties, new DefaultMarriageStrategy(), SiloUtil.provideNewRandom());


        TransportModel transportModel;
        switch (properties.transportModel.transportModelIdentifier) {
            case MITO_MATSIM:
                logger.warn("Mito not implemented for Mstm. Defaulting to simple matsim transport model");
            case MATSIM:
                MatsimData matsimData = null;
                if (config != null) {
                    final Scenario scenario = ScenarioUtils.loadScenario(config);
                    matsimData = new MatsimData(config, properties, ZoneConnectorManagerImpl.ZoneConnectorMethod.RANDOM, dataContainer, scenario.getNetwork(), scenario.getTransitSchedule());
                }
                final SimpleMatsimScenarioAssembler scenarioAssembler = new SimpleMatsimScenarioAssembler(dataContainer, properties);
                transportModel = new MatsimTransportModel(dataContainer, config, properties, scenarioAssembler, matsimData);
                break;
            case NONE:
            default:
                transportModel = null;
        }

        final ModelContainer modelContainer = new ModelContainer(
                birthModel, birthdayModel,
                deathModel, marriageModel,
                divorceModel, driversLicenseModel,
                educationModel, employmentModel,
                leaveParentsModel, jobMarketUpdateModel,
                construction, demolition, pricing, renovation,
                constructionOverwrite, inOutMigration, movesModel, transportModel);
        modelContainer.registerModelUpdateListener(carOwnership);   // Baltimore 2026: yearly car-ownership update
        return modelContainer;
    }
}
