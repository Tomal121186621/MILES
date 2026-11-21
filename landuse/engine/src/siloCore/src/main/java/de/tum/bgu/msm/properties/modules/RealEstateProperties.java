package de.tum.bgu.msm.properties.modules;

import de.tum.bgu.msm.properties.PropertiesUtil;

import java.util.ResourceBundle;

public class RealEstateProperties {

    public final String dwellingsFileName;
    public final String dwellingsIntermediatesFileName;
    public final String dwellingsFinalFileName;
    public final boolean constructionOverwriteDwelling;
    public final boolean traceOverwriteDwellings;
    public final String overWriteDwellingsTraceFile;
    public final String constructionOverwriteDwellingFile;
    public final boolean makeSomeNewDdAffordable;
    public final float affordableDwellingsShare;
    public final float levelOfAffordability;
    public final float constructionLogModelBeta;
    public final float constructionLogModelInflator;
    public final double constructionDemandScaler;
    public final String constructionDemandScalersFile;
    /** Baltimore 2026: whether demand that a region cannot build (no land) is built anywhere else in the area (default true, inherited) */
    public final boolean constructionReallocateUnrealized;
    /** Baltimore 2026: shares of the listed regions in the construction of each dwelling type (type,region,share); empty = engine allocation */
    public final String constructionRegionSharesFile;
    /** Baltimore 2026 (2026-10-29): observed permits by year and region (year, region, units_1, units_2_4, units_5plus); the listed
     * regions build exactly these units each year (1-unit split over SFD, SFA, MH by the engine's demand); replaces the shares file */
    public final String constructionRegionPermitsFile;
    public final boolean pricingAfterEventModels;   // Baltimore 2026-11-17: see Simulator.finishYear
    public final String structuralVacancyFile;   // Baltimore 2026-11-17: region,rate (StructuralVacancy); empty = the dwelling-type defaults

    public RealEstateProperties(ResourceBundle bundle) {
        PropertiesUtil.newPropertySubmodule("Real state properties");
        PropertiesUtil.newPropertySubmodule("Real state - dwelling input data");
        dwellingsFileName = PropertiesUtil.getStringProperty(bundle, "dwelling.file.ascii", "microData/dd");
        dwellingsIntermediatesFileName = PropertiesUtil.getStringProperty(bundle, "dwelling.intermediates.file.ascii", "microData/dd");
        dwellingsFinalFileName = PropertiesUtil.getStringProperty(bundle, "dwelling.final.file.ascii", "microData/dd");

        PropertiesUtil.newPropertySubmodule("Real state - model parameters and input");
        constructionOverwriteDwelling = PropertiesUtil.getBooleanProperty(bundle, "construct.dwelling.use.overwrite", false);
        traceOverwriteDwellings = PropertiesUtil.getBooleanProperty(bundle, "trace.use.of.overwrite.dwellings", false);
        overWriteDwellingsTraceFile = PropertiesUtil.getStringProperty(bundle, "trace.file.for.overwrite.dwellings", "useOfOverwriteDwellings");
        constructionOverwriteDwellingFile = PropertiesUtil.getStringProperty(bundle, "construct.dwelling.overwrite", "input/assumptions/dwellingOverwrite_empty.csv");
        makeSomeNewDdAffordable = PropertiesUtil.getBooleanProperty(bundle, "make.new.dwellings.partly.affordable", false);
        affordableDwellingsShare = (float) PropertiesUtil.getDoubleProperty(bundle, "share.of.affordable.dwellings", 1.0);
        levelOfAffordability = (float) PropertiesUtil.getDoubleProperty(bundle, "level.of.affordability.setting", 0.3);
        constructionLogModelBeta = (float) PropertiesUtil.getDoubleProperty(bundle, "construct.dwelling.mn.log.model.beta", 0.5);
        constructionDemandScaler = PropertiesUtil.getDoubleProperty(bundle, "construct.dwelling.demand.scaler", 1.0);   // Baltimore 2026 calibration lever
        constructionDemandScalersFile = PropertiesUtil.getStringProperty(bundle, "construct.dwelling.demand.scalers.file", "");
        constructionLogModelInflator = (float) PropertiesUtil.getDoubleProperty(bundle, "construct.dwelling.mn.log.model.inflator", 1.5);
        constructionReallocateUnrealized = PropertiesUtil.getBooleanProperty(bundle, "construct.dwelling.reallocate.unrealized", true);
        constructionRegionSharesFile = PropertiesUtil.getStringProperty(bundle, "construct.dwelling.region.shares.file", "");
        constructionRegionPermitsFile = PropertiesUtil.getStringProperty(bundle, "construct.dwelling.region.permits.file", "");
        structuralVacancyFile = PropertiesUtil.getStringProperty(bundle, "structural.vacancy.file", "");
        pricingAfterEventModels = PropertiesUtil.getBooleanProperty(bundle, "pricing.after.population.control", false);
    }
}
