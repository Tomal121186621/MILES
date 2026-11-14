package de.tum.bgu.msm.properties.modules;

import de.tum.bgu.msm.properties.PropertiesUtil;

import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.ResourceBundle;

public final class JobDataProperties {

    public final String[] jobTypes;
    public final String jobsFileName;
    public final String jobsIntermediatesFileName;
    public final String jobsFinalFileName;
    public final JobForecastMethod jobForecastMethod;
    public final String jobControlTotalsFileName;
    public final String employmentForeCastFile;
    public final Map<String,Double> growthRateInPercentByJobType = new LinkedHashMap<>();
    public final String jobStartTimeDistributionFile;
    public final String jobDurationDistributionFile;
    /** Baltimore 2026: impedance of the vacant-job choice by car travel time (minutes,weight); blank = commute-time distribution */
    public final String jobSearchImpedanceFile;
    /** Baltimore 2026: estimated workplace-choice MNL (2_silo/jobchoice): coefficients (parameter,estimate) and zone attributes
     * (zone,state,county); when the coefficient file is set it replaces the impedance in the vacant-job choice */
    public final String jobChoiceCoefficientsFile;
    public final String jobChoiceZonesFile;
    /** Baltimore 2026 (2026-10-27): specification of the workplace choice, "lodes" (LODES 2017 estimate M4, earnings class only; the
     * default) or "rts" (re-estimated on the 2017/18 Regional Travel Survey, jobchoice/ESTIMATION_REPORT_RTS.md: person and
     * household attributes and the work-tour mode-choice logsum by car availability x income group, read from
     * job.choice.logsum.dir); the coefficient and zone files are those of the chosen specification */
    public final String jobChoiceModel;
    public final String jobChoiceLogsumDir;
    /** Baltimore 2026 (2026-10-28): size term of the workplace choice, vacancies (default) or jobs (all jobs of the zones that have a vacancy) */
    public final String jobChoiceSize;
    /** Baltimore 2026 (2026-10-28, job.choice.model = rts3): zone attributes (zone, hiearn, off_sh, ret_sh, ind_sh, rural) */
    public final String jobChoiceZoneAttributesFile;
    /** Baltimore 2026 (2026-11-09, job.choice.model = respec): logsum accessibility file (zone,segment,purpose,A; pattern with {year},
     * absolute or relative to base.directory) for the non-work accessibility of the workplace zone (base accw) */
    public final String jobChoiceAccessibilityFile;
    /** Baltimore 2026 (2026-10-28): yearly job-to-job change probability of a worker (JOLTS Maryland quits rate); 0 = off */
    public final double jobChangeRate;
    public final int jobChangeOffers;   // vacancies drawn (offers) per job-to-job search

    public enum JobForecastMethod {
        INTERPOLATION, RATE;
    }


    public JobDataProperties(ResourceBundle bundle) {
        PropertiesUtil.newPropertySubmodule("Job data properties");
        jobTypes = PropertiesUtil.getStringPropertyArray(bundle, "employment.types", new String[]{"Agri","Mnft","Util","Cons","Retl","Trns","Finc","Rlst","Admn","Serv"});

        PropertiesUtil.newPropertySubmodule("Job - forecasts");
        jobForecastMethod = JobForecastMethod.
                valueOf(PropertiesUtil.getStringProperty(bundle, "job.forecast.method", "rate").toUpperCase());
        jobControlTotalsFileName = PropertiesUtil.getStringProperty(bundle, "job.control.total", "input/assumptions/employmentForecast.csv");
        employmentForeCastFile = PropertiesUtil.getStringProperty(bundle, "interpol.empl.forecast", "interpolatedEmploymentForecast");
        //todo prepared for separate growth rates by industry
        if (jobForecastMethod.equals(JobForecastMethod.RATE)) {
            double overallJobGrowthRate = PropertiesUtil.getDoubleProperty(bundle, "job.growth.rate", 0.);
            for (String jobType : jobTypes) {
                //currently assign a unique
                growthRateInPercentByJobType.put(jobType, overallJobGrowthRate);
            }
        }

        PropertiesUtil.newPropertySubmodule("Job - synthetic jobs input");
        jobsFileName = PropertiesUtil.getStringProperty(bundle, "job.file.ascii", "microData/jj");
        jobsIntermediatesFileName = PropertiesUtil.getStringProperty(bundle, "job.intermediates.file.ascii", "microData/jj");
        jobsFinalFileName = PropertiesUtil.getStringProperty(bundle, "job.final.file.ascii", "microData/jj");

        PropertiesUtil.newPropertySubmodule("Job - job time input");
        jobStartTimeDistributionFile = PropertiesUtil.getStringProperty(bundle, "job.start.distribution.file", "input/jobStartTimeDistributions.csv");
        jobDurationDistributionFile = PropertiesUtil.getStringProperty(bundle, "job.duration.distribution.file", "input/jobDurationDistributions.csv");
        jobSearchImpedanceFile = PropertiesUtil.getStringProperty(bundle, "job.search.impedance.file", "");
        jobChoiceCoefficientsFile = PropertiesUtil.getStringProperty(bundle, "job.choice.coefficients.file", "");
        jobChoiceZonesFile = PropertiesUtil.getStringProperty(bundle, "job.choice.zones.file", "input/job_choice_zones.csv");
        jobChoiceModel = PropertiesUtil.getStringProperty(bundle, "job.choice.model", "lodes").trim().toLowerCase();
        jobChoiceLogsumDir = PropertiesUtil.getStringProperty(bundle, "job.choice.logsum.dir", "input/job_choice_logsums_rts");
        jobChoiceSize = PropertiesUtil.getStringProperty(bundle, "job.choice.size", "vacancies").trim().toLowerCase();
        jobChoiceZoneAttributesFile = PropertiesUtil.getStringProperty(bundle, "job.choice.zone.attributes.file", "input/job_choice_zone_attributes_rts3.csv");
        jobChoiceAccessibilityFile = PropertiesUtil.getStringProperty(bundle, "job.choice.accessibility.file", "");
        jobChangeRate = PropertiesUtil.getDoubleProperty(bundle, "job.change.rate", 0.);
        jobChangeOffers = PropertiesUtil.getIntProperty(bundle, "job.change.offers", 1);
    }
}
