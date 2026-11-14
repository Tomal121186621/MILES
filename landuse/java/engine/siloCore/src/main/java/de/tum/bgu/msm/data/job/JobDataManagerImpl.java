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
package de.tum.bgu.msm.data.job;


import com.google.common.collect.ConcurrentHashMultiset;
import com.google.common.collect.Multiset;
import de.tum.bgu.msm.common.datafile.TableDataSet;
import de.tum.bgu.msm.data.Region;
import de.tum.bgu.msm.data.Zone;
import de.tum.bgu.msm.data.accessibility.CommutingTimeProbability;
import de.tum.bgu.msm.data.geo.GeoData;
import de.tum.bgu.msm.data.person.Occupation;
import de.tum.bgu.msm.data.person.Person;
import de.tum.bgu.msm.data.travelTimes.TravelTimes;
import de.tum.bgu.msm.io.output.DefaultJobWriter;
import de.tum.bgu.msm.properties.Properties;
import de.tum.bgu.msm.properties.modules.JobDataProperties;
import de.tum.bgu.msm.simulator.UpdateListener;
import de.tum.bgu.msm.utils.SampleException;
import de.tum.bgu.msm.utils.Sampler;
import de.tum.bgu.msm.utils.SiloUtil;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.matsim.api.core.v01.TransportMode;

import java.io.PrintWriter;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;


/**
 * Keeps data of dwellings and non-residential floorspace
 * Author: Rolf Moeckel, PB Albuquerque
 * Created on 22 February 2013 in Rhede
 **/
public class JobDataManagerImpl implements UpdateListener, JobDataManager {
    
    private final static Logger logger = LogManager.getLogger(JobDataManagerImpl.class);

    private final GeoData geoData;
    private final Properties properties;
    private final JobFactory jobFactory;

    private final JobData jobData;
    private final TravelTimes travelTimes;
    private final CommutingTimeProbability commutingTimeProbability;

    private int highestJobIdInUse;

    private final Map<Integer, List<Job>> vacantJobsByRegion = new LinkedHashMap<>();
    private final Map<Integer, Double> zonalJobDensity;

    private final Map<Integer, Map<Integer,Map<String,Float>>> jobsByYearByZoneByIndustry = new ConcurrentHashMap<>();

    public JobDataManagerImpl(Properties properties,
                              JobFactory jobFactory, JobData jobData, GeoData geoData,
                              TravelTimes travelTimes, CommutingTimeProbability commutingTimeProbability) {
        this.geoData = geoData;
        this.properties = properties;
        this.jobFactory = jobFactory;
        this.jobData = jobData;
        this.travelTimes = travelTimes;
        this.commutingTimeProbability = commutingTimeProbability;
        this.zonalJobDensity = new LinkedHashMap<>();
    }

    @Override
    public void setup() {
        identifyHighestJobId();
        calculateEmploymentForecast();
        identifyVacantJobs(); //this step may be not needed - seem to be a duplicate of the method execution in the first "prepare year"
    }

    @Override
    public void prepareYear(int year) {
        if (jcRespec) loadAccw(year);   // Baltimore 2026 (respec): accessibility of the latest year <= year
        final String verify = System.getProperty("silo.jobchoice.verify");
        if (verify != null && !verify.isBlank()) verifyRts(verify);
        calculateJobDensityByZone();
        identifyVacantJobs();
        poolYear = year; poolStart = 0; poolAdded = 0; poolTaken = 0; poolJobs = jobData.getJobs().size(); poolNext = 100000;
        for (List<Job> l : vacantJobsByRegion.values()) poolStart += l.size();
        poolLog.info("Vacancy pool " + year + " start: " + poolStart + " vacant of " + poolJobs + " jobs (" + String.format("%.2f", 100. * poolStart / Math.max(1, poolJobs)) + " %)");
    }

    // Baltimore 2026 (2026-10-28): vacancy-chain accounting. Every job vacated during the year (quit, job-to-job change, death,
    // out-migration, school enrolment) enters the vacancy lists at once (quitJob / releaseJob -> addJobToVacancyList) and new
    // jobs of the job-market update as well (addJob); jobs removed by the update do not. Logged under the logger
    // "...VacancyPool" (not filtered by the quiet log configuration): pool share after every 100,000 jobs taken, and the totals.
    private static final Logger poolLog = LogManager.getLogger("de.tum.bgu.msm.data.job.VacancyPool");
    private int poolYear; private long poolStart, poolAdded, poolTaken, poolJobs, poolNext;
    private void poolTakenOne() {
        poolTaken++;
        if (poolTaken >= poolNext) {
            poolNext += 100000;
            poolLog.info("Vacancy pool " + poolYear + " after " + poolTaken + " jobs taken: " + (poolStart + poolAdded - poolTaken) + " open ("
                    + String.format("%.2f", 100. * (poolStart + poolAdded - poolTaken) / Math.max(1, poolJobs)) + " %), " + poolAdded + " vacated so far");
        }
    }

    @Override
    public void endYear(int year) {
        poolLog.info("Vacancy pool " + year + " end: start " + poolStart + " + vacated or added " + poolAdded + " - taken by the job choice " + poolTaken
                + " = " + (poolStart + poolAdded - poolTaken) + " (jobs taken outside the choice and removed vacancies not counted)");
        if (DEBUG_JC && dbgN > 0) logger.error("DEBUG job choice " + year + ": searches " + dbgN + ", expected car time under the weights " + String.format("%.1f", dbgExpT / dbgN)
                + ", realised " + String.format("%.1f", dbgRealT / dbgN) + ", zones with a vacancy " + String.format("%.0f", dbgZones / dbgN) + ", nearest vacancy " + String.format("%.1f", dbgTmin / dbgN) + " min, MD homes " + String.format("%.3f", dbgHome / dbgN));
        dbgN = 0; dbgExpT = dbgRealT = dbgZones = dbgTmin = dbgHome = 0;
        if (!Properties.get().jobData.jobsIntermediatesFileName.equals("")) {
            final String outputDirectory = properties.main.baseDirectory + "scenOutput/" + properties.main.scenarioName +"/";
            String filejj = outputDirectory
                    + properties.jobData.jobsIntermediatesFileName
                    + "_"
                    + year + ".csv";
            new DefaultJobWriter(this.jobData.getJobs()).writeJobs(filejj);
        }
    }

    @Override
    public void endSimulation() {
        final String outputDirectory = properties.main.baseDirectory + "scenOutput/" + properties.main.scenarioName +"/";
        String filejj = outputDirectory
                + properties.jobData.jobsFinalFileName
                + "_"
                + properties.main.endYear + ".csv";
        new DefaultJobWriter(this.jobData.getJobs()).writeJobs(filejj);
    }

    @Override
    public Job getJobFromId(int jobId) {
        return jobData.get(jobId);
    }

    @Override
    public Collection<Job> getJobs() {
        return jobData.getJobs();
    }
    
    @Override
    public void removeJob(int id) {
        jobData.removeJob(id);
    }

    private void identifyHighestJobId() {
        highestJobIdInUse = 0;
        for (Job job: jobData.getJobs()) {
            highestJobIdInUse = Math.max(highestJobIdInUse, job.getId());
        }
    }

    @Override
    public int getNextJobId() {
        // increase highestJobIdInUse by 1 and return value
        return ++highestJobIdInUse;
    }

    @Override
    public List<Integer> getNextJobIds(int amount) {
        // increase highestJobIdInUse by 1 and return value
        List<Integer> ids = new ArrayList<>();
        for (int i = 0; i < amount; i++) {
            ids.add(++highestJobIdInUse);
        }
        return ids;
    }

    private void calculateEmploymentForecast() {
        if (properties.jobData.jobForecastMethod.equals(JobDataProperties.JobForecastMethod.INTERPOLATION)) {
            interpolateEmploymentForecast();
            logger.info("Forecasted jobs from employment forecast file");
        } else if (properties.jobData.jobForecastMethod.equals(JobDataProperties.JobForecastMethod.RATE)){
            calculateEmploymentForecastWithRate();
            logger.info("Forecasted jobs with growth rate");
        }

    }

    private void calculateEmploymentForecastWithRate() {
        int year = properties.main.startYear;
        Map<Integer, Map<String, Float>> jobCountBaseyear = new LinkedHashMap<>();
        jobsByYearByZoneByIndustry.put(year, jobCountBaseyear);
        //initialize maps with count = 0
        for (Zone zone : geoData.getZones().values()){
            Map<String, Float> jobsInThisZone = new LinkedHashMap<>();
            jobCountBaseyear.put(zone.getZoneId(), jobsInThisZone);
            for (String jobType : JobType.getJobTypes()){
                jobsInThisZone.put(jobType, 0.f);
            }
        }
        //count jobs in SP of base year
        for (Job job : jobData.getJobs()){
            int zoneId = job.getZoneId();
            String jobType = job.getType();
            jobCountBaseyear.get(zoneId).put(jobType, jobCountBaseyear.get(zoneId).get(jobType) + 1);
        }
        logger.info("Count of jobs in synthetic population of the base year completed");
        //forecast the following years
        year++;
        while (year <= properties.main.endYear){
            Map<Integer, Map<String, Float>> jobCountThisyear = new LinkedHashMap<>();
            jobsByYearByZoneByIndustry.put(year, jobCountThisyear);
            for (int zone : geoData.getZones().keySet()) {
                Map<String, Float> jobCountThisZone = new LinkedHashMap<>();
                for (String jobType : JobType.getJobTypes()){
                    jobCountThisZone.put(jobType, (float)(jobCountBaseyear.get(zone).get(jobType)*
                            Math.pow(1+properties.jobData.growthRateInPercentByJobType.get(jobType)/100,year - properties.main.startYear)));
                }
                jobCountThisyear.put(zone, jobCountThisZone);
            }
            year++;
        }
    }

    private void interpolateEmploymentForecast(){

        TableDataSet jobs;
        try {
            final String filename = properties.main.baseDirectory + "/" + properties.jobData.jobControlTotalsFileName;
            jobs = SiloUtil.readCSVfile(filename);
        } catch (Exception ee) {
            throw new RuntimeException(ee);
        }
        jobs.buildIndex(jobs.getColumnPosition("SMZ"));
        new JobType(properties.jobData.jobTypes);

        //read the headers
        String[] labels = jobs.getColumnLabels();
        String[] jobTypes = JobType.getJobTypes();
        List<String> years = new ArrayList<>();

        //find the years that are defined in the job forecast
        String jobTypeName = jobTypes[0];
        for (String label : labels) {
            if (label.contains(jobTypeName)) {
                String year = (label.substring(jobTypeName.length(), label.length()));
                if (!years.contains(year)) {
                    years.add(year);
                }
            }
        }
        //proof the rest of job types are in the file
        for (int i = 1; i < jobTypes.length; i++) {
            for (String year : years) {
                boolean found = false;
                for (String label : labels) {
                    if (label.equals(jobTypes[i] + year)) {
                        found = true;
                    }
                }
                if (!found) {
                    throw new RuntimeException("Not defined all job types for year " + year);
                }
            }
        }

        // Baltimore 2026 (change 4a, study notes 8.D 2026-06-11): the forecast years must be in chronological order for the
        // interpolation below; they were taken in the order of the file's columns, which interpolated on the wrong segment.
        years.sort(java.util.Comparator.comparingInt(Integer::parseInt));
        String[] yearsGiven = years.toArray(new String[0]);

        String dir = properties.main.baseDirectory + "scenOutput/" + properties.main.scenarioName + "/employmentForecast/";
        SiloUtil.createDirectoryIfNotExistingYet(dir);

            int previousFixedYear = Integer.parseInt(yearsGiven[0]);
            int nextFixedYear;
            int interpolatedYear = previousFixedYear;
            for (int i = 0; i < yearsGiven.length - 1; i++) {
                nextFixedYear = Integer.parseInt(yearsGiven[i + 1]);
                while (interpolatedYear <= nextFixedYear) {
                    Map<Integer, Map<String, Float>> jobsThisyear = new LinkedHashMap<>();
                    jobsByYearByZoneByIndustry.put(2000 + interpolatedYear, jobsThisyear);
                    final String forecastFileName = dir + properties.jobData.employmentForeCastFile + (2000 + interpolatedYear) + ".csv";
                    final PrintWriter pw = SiloUtil.openFileForSequentialWriting(forecastFileName, false);
                    final StringBuilder builder = new StringBuilder("zone");
                    for (String jobType : JobType.getJobTypes()) {
                        builder.append(",").append(jobType);
                    }
                    builder.append("\n");
                    for (int zone : geoData.getZones().keySet()) {
                        Map<String, Float> jobsThisZone = new LinkedHashMap<>();
                        jobsThisyear.put(zone, jobsThisZone);
                        builder.append(zone);
                        for (int jobTp = 0; jobTp < JobType.getNumberOfJobTypes(); jobTp++) {
                            final int index = jobs.getIndexedRowNumber(zone);
                            float currentValue;
                            if (interpolatedYear == previousFixedYear) {
                                //todo look at a different place if it is the base year!
                                currentValue = jobs.getValueAt(index, JobType.getJobType(jobTp) + yearsGiven[i]);
                            } else if (interpolatedYear == nextFixedYear) {
                                currentValue = jobs.getValueAt(index, JobType.getJobType(jobTp) + yearsGiven[i + 1]);
                            } else {
                                final float previousFixedValue = jobs.getValueAt(index, JobType.getJobType(jobTp) + yearsGiven[i]);
                                final float nextFixedValue = jobs.getValueAt(index, JobType.getJobType(jobTp) + yearsGiven[i + 1]);
                                currentValue = previousFixedValue + (nextFixedValue - previousFixedValue) * (interpolatedYear - previousFixedYear) /
                                        (nextFixedYear - previousFixedYear);
                            }

                            jobsThisZone.put(JobType.getJobType(jobTp), currentValue);
                            builder.append(",").append(currentValue);
                        }
                        builder.append("\n");
                    }
                    pw.print(builder.toString());
                    pw.close();
                    interpolatedYear++;
                }
                previousFixedYear = nextFixedYear;
            }


    }
    

    @Override
    public float getJobForecast(int year, int zone, String jobType){
        return jobsByYearByZoneByIndustry.get(year).get(zone).get(jobType);
    }

    /**
     * identify vacant jobs by region (one-time task at beginning of model run only)
     */
    private void identifyVacantJobs() {
        identifyVacantJobsInner();
        if (jcRts3 && !Boolean.getBoolean("silo.jobchoice.verify.fileShares")) updateJobMixShares();
    }

    private void identifyVacantJobsInner() {
        logger.info("  Identifying vacant jobs");
        // Baltimore 2026 (change 4b, study notes 8.D 2026-06-14): rebuild the index from scratch every time it is called.
        // It is called at setup and in every prepareYear; appending without clearing left jobs that had been removed or
        // filled during the year in the vacant lists, so job seekers were matched to stale entries.
        vacantJobsByRegion.clear();
        vacByZone = null;
        jobsByZoneType = null;
        for (Job jj : jobData.getJobs()) {
            if (jj.getWorkerId() == -1) {
                int region = geoData.getZones().get(jj.getZoneId()).getRegion().getId();

                vacantJobsByRegion.putIfAbsent(region, new ArrayList<>());
                vacantJobsByRegion.get(region).add(jj);
                vacZoneAdd(jj);
                if (jj.getId() == SiloUtil.trackJj) {
                    SiloUtil.trackWriter.println("Added job " + jj.getId() + " to list of vacant jobs.");
                }
            }
            // Baltimore 2026 (2026-10-28): all jobs (filled and vacant) by zone and type, the size term of the estimated model
            if (jj.getZoneId() > 0) {
                if (jobsByZoneType == null) { int mx = 0; for (Zone z : geoData.getZones().values()) mx = Math.max(mx, z.getZoneId()); jobsByZoneType = new double[mx + 1][JC_TYPES.length]; }
                if (jj.getZoneId() < jobsByZoneType.length) jobsByZoneType[jj.getZoneId()][typeIndex(jj)]++;
            }
        }
    }

    /**
     * Person quits job and the job is added to the vacantJobList
     * @param makeJobAvailableToOthers
     * @param person
     */
    @Override
    public void quitJob(boolean makeJobAvailableToOthers, Person person) {
        // <makeJobAvailableToOthers> is false if this job disappears from the job market
        if (person == null) {
            return;
        }
        final int workplace = person.getJobId();
        Job jb = jobData.get(workplace);
        if (jb == null) {
            // Baltimore 2026 (study notes 8.D 2026-06-13): the person's job was removed earlier in the same year (job-market update) or
            // the person was cloned without a job; there is nothing to release, only the person's state to correct.
            person.setWorkplace(-1);
            if (person.getOccupation() == Occupation.EMPLOYED) person.setOccupation(Occupation.UNEMPLOYED);
            return;
        }
        if (jb.getWorkerId() != person.getId()) {
            // Baltimore 2026: the job belongs to another person (the in-migrant copy of a worker had inherited the original's
            // job id): releasing it would make the holder's job vacant while the holder still works there
            person.setWorkplace(-1);
            if (person.getOccupation() == Occupation.EMPLOYED) person.setOccupation(Occupation.UNEMPLOYED);
            return;
        }
        if (makeJobAvailableToOthers) {
            addJobToVacancyList(jb);
        }
        jb.setWorkerID(-1);
        person.setWorkplace(-1);
        person.setOccupation(Occupation.UNEMPLOYED);
        // Baltimore 2026: at job loss the wage is replaced by the unemployment benefit, half of the previous earnings up to the Maryland
        // maximum weekly benefit ($430, i.e. $22,360 a year); the income then stays flat in real terms (IncomeAdjustment)
        person.setLastWage(person.getAnnualIncome());
        person.setIncome(Math.min(person.getAnnualIncome() / 2, 22360));
        // Baltimore 2026: the benefit is paid for at most 26 weeks (Maryland); the income adjustment at the end of the year after
        // the job loss replaces it by the non-wage income of a non-employed person (IncomeAdjustment)
        person.setBenefitYears(2);
    }
    
    private int getNumberOfVacantJobsByRegion(int region) {
        return vacantJobsByRegion.getOrDefault(region, Collections.EMPTY_LIST).size();
    }
    
    @Override
    public Job findVacantJob(Zone homeZone, Collection<Region> regions) {
        return findVacantJob(homeZone, regions, 2);
    }

    @Override
    public Job findVacantJob(Zone homeZone, Collection<Region> regions, int earningsClass) {
        // select vacant job for person living in homeZone

        if (homeZone != null) {
            return findVacantJobByCommuteTime(homeZone, regions, earningsClass);
        }

        Sampler<Region> regionSampler = new Sampler<>(regions.size(), Region.class, SiloUtil.getRandomObject());

        if (homeZone != null) {
            // person has home location (i.e., is not inmigrating right now)
            for (Region reg : regions) {
                int numberOfVacantJobs = getNumberOfVacantJobsByRegion(reg.getId());
                if (numberOfVacantJobs > 0) {
                    int travelTime_min = (int) ((travelTimes.getTravelTimeToRegion(homeZone, reg,
                            properties.transportModel.peakHour_s, TransportMode.car) + 0.5));
                    //todo make region probability sensitve to mode choice to find a vacant job
                    final double prob = commutingTimeProbability.getCommutingTimeProbability(Math.max(1, travelTime_min), TransportMode.car) * (double) numberOfVacantJobs;
                    regionSampler.incrementalAdd(reg, prob);
                }
            }
            if (regionSampler.getCumulatedProbability() == 0) {
                // could not find job in reasonable distance. Person will have to commute far and is likely to relocate in the future
                // Baltimore 2026 (change 1 of the study notes, 8.B.1): use a FRESH sampler here. The first loop already advanced the
                // sampler's internal index; re-adding regions to the same sampler overflowed its regions.size() slots
                // (ArrayIndexOutOfBoundsException in Sampler.incrementalAdd, seen in year 2018 of the earlier runs).
                regionSampler = new Sampler<>(regions.size(), Region.class, SiloUtil.getRandomObject());
                for (Region reg : regions) {
                    if (getNumberOfVacantJobsByRegion(reg.getId()) > 0) {
                        int travelTime_min = (int) ((travelTimes.getTravelTimeToRegion(homeZone, reg,
                                properties.transportModel.peakHour_s, TransportMode.car) + 0.5));
                        final double prob = 1. / Math.max(1, travelTime_min);
                        regionSampler.incrementalAdd(reg, prob);
                    }
                }
            }
        } else {
            // person has no home location because (s)he is inmigrating right now and a dwelling has not been chosen yet
            for (Region reg : regions) {
                int numberOfJobs = getNumberOfVacantJobsByRegion(reg.getId());
                if (numberOfJobs > 0) {
                    regionSampler.incrementalAdd(reg, (double) numberOfJobs);
                }
            }
        }

        if (regionSampler.getCumulatedProbability() == 0) {
            logger.warn("No jobs remaining. Could not find new job.");
            return null;
        }
        int selectedRegion = -1;
        try {
            selectedRegion = regionSampler.sampleObject().getId();
        } catch (SampleException e) {
            e.printStackTrace();
        }

        List<Job> eligibleJobs = vacantJobsByRegion.get(selectedRegion);
        Job selectedJob = eligibleJobs.remove(SiloUtil.getRandomObject().nextInt(eligibleJobs.size()));
        // Baltimore 2026: the zone index (exact workplace choice) and this list share the jobs; skip entries filled meanwhile
        while ((selectedJob.getWorkerId() > 0 || jobData.get(selectedJob.getId()) == null) && !eligibleJobs.isEmpty()) {
            selectedJob = eligibleJobs.remove(SiloUtil.getRandomObject().nextInt(eligibleJobs.size()));
        }
        if (selectedJob.getWorkerId() > 0 || jobData.get(selectedJob.getId()) == null) return null;

        if (selectedJob.getId() == SiloUtil.trackJj) {
            SiloUtil.trackWriter.println("Removed job " + selectedJob.getId() + " from list of vacant jobs.");
        }
        return selectedJob;
    }


    private static final int JOB_SEARCH_SAMPLE = 500;   // Baltimore 2026: 2000 tripled the run time (37 vs 13 min for 2016-2020) for little gain
    private double[] jobSearchImpedance;   // Baltimore 2026: weight by whole minute of car travel time, null = commute-time distribution

    /** Baltimore 2026: f(t) = observed share of base-year commutes at t / share of all home-job pairs at t (job.search.impedance.file) */
    private double impedance(int minutes) {
        if (jobSearchImpedance == null) {
            final String file = properties.jobData.jobSearchImpedanceFile;
            if (file == null || file.isBlank()) {
                jobSearchImpedance = new double[0];
            } else {
                final List<Double> w = new ArrayList<>();
                try (java.io.BufferedReader r = new java.io.BufferedReader(new java.io.FileReader(properties.main.baseDirectory + file))) {
                    final List<String> h = Arrays.asList(r.readLine().split(","));
                    final int iM = h.indexOf("minutes"), iW = h.indexOf("weight");
                    String line;
                    while ((line = r.readLine()) != null) {
                        final String[] f = line.split(",");
                        final int m = Integer.parseInt(f[iM].trim());
                        while (w.size() <= m) w.add(0.);
                        w.set(m, Double.parseDouble(f[iW].trim()));
                    }
                } catch (java.io.IOException e) {
                    throw new RuntimeException("Could not read job search impedance file " + file, e);
                }
                jobSearchImpedance = w.stream().mapToDouble(Double::doubleValue).toArray();
                logger.info("Job search impedance read from " + file + " (" + jobSearchImpedance.length + " minutes)");
            }
        }
        if (jobSearchImpedance.length == 0) {
            return commutingTimeProbability.getCommutingTimeProbability(Math.max(1, minutes), TransportMode.car);
        }
        return minutes < jobSearchImpedance.length ? jobSearchImpedance[Math.max(0, minutes)] : 0.;
    }

    // Baltimore 2026 (2026-10-26): vacant jobs indexed by zone and type (RET, OFF, IND, OTH) for the exact workplace choice
    private static final String[] JC_TYPES = {"RET", "OFF", "IND", "OTH"};
    private List<Job>[][] vacByZone;
    private Zone[] zoneById;

    @SuppressWarnings("unchecked")
    private void vacZoneAdd(Job job) {
        if (vacByZone == null) {
            int max = 0;
            for (Zone z : geoData.getZones().values()) max = Math.max(max, z.getZoneId());
            vacByZone = new List[max + 1][];
            zoneById = new Zone[max + 1];
            for (Zone z : geoData.getZones().values()) zoneById[z.getZoneId()] = z;
        }
        final int z = job.getZoneId();
        if (z <= 0 || z >= vacByZone.length || zoneById[z] == null) return;
        if (vacByZone[z] == null) { vacByZone[z] = new List[JC_TYPES.length]; for (int k = 0; k < JC_TYPES.length; k++) vacByZone[z][k] = new ArrayList<>(); }
        vacByZone[z][typeIndex(job)].add(job);
    }

    private static int typeIndex(Job job) {
        final String t = job.getType() == null ? "" : job.getType().replace("\"", "");
        for (int k = 0; k < JC_TYPES.length; k++) if (JC_TYPES[k].equals(t)) return k;
        return JC_TYPES.length - 1;
    }

    /**
     * Baltimore 2026 (2026-10-26): exact workplace choice over ALL vacant jobs of the year. The earlier draw from 500 vacancies
     * sampled uniformly (1 % of the pool or less) rarely contained the few vacancies near the home, so the choice fell on distant
     * ones: hires of 2016 had a mean car time of 61 min with the estimated weights (38 min on the full set). Here
     * P(zone z, type k) = n_zk exp(g_k + V_hz) / sum, n_zk = vacant jobs of type k in zone z (the size term, coefficient 1), then
     * one of those jobs at random. Entries that were filled or removed since they were listed are dropped when drawn.
     * 2026-10-27 (job.choice.model = rts): the size term has the estimated coefficient mu (mu_size, 1 when absent): the zone is
     * drawn with weight S_z^mu exp(V_hz), S_z = sum_k e^g_k n_zk, and the type within the zone with e^g_k n_zk / S_z; V_hz uses
     * the attributes of the job seeker (Seeker) and the work-tour mode-choice logsum of the seeker's segment.
     */
    private Job chooseVacantJobMnl(Zone home, int cls) {
        return chooseVacantJobMnl(home, seeker(cls, null, 0), null);
    }

    @Override
    public Job findBetterJob(Zone homeZone, Job current, int earningsClass) {
        if (homeZone == null || current == null || !jobChoice()) return null;
        return chooseVacantJobMnl(homeZone, seeker(earningsClass, null, 0), current);
    }

    @Override
    public Job findBetterJob(Zone homeZone, Job current, int earningsClass, Person person, int householdIncome) {
        if (homeZone == null || current == null || !jobChoice()) return null;
        return chooseVacantJobMnl(homeZone, seeker(earningsClass, person, householdIncome), current);
    }

    @Override
    public Job findVacantJob(Zone homeZone, Collection<Region> regions, int earningsClass, Person person, int householdIncome) {
        if (homeZone != null && jobChoice()) return chooseVacantJobMnl(homeZone, seeker(earningsClass, person, householdIncome), null);
        return findVacantJob(homeZone, regions, earningsClass);
    }

    @Override
    public void releaseJob(Job job) {
        job.setWorkerID(-1);
        if (job.getZoneId() > 0 && geoData.getZones().containsKey(job.getZoneId())) {
            synchronized (vacantJobsByRegion) { addJobToVacancyList(job); }
        }
    }

    /** Baltimore 2026 (2026-10-27): the job seeker as the workplace choice sees him or her. cls = LODES earnings class (lodes
     * specification); the rest is used by the rts specification (jobchoice/rts_common.py): female, young (age < 30), old (>= 55),
     * kids (a household member under 18), w2 (2+ workers, the seeker counted as one), car segment (0 no car, 1 fewer cars than
     * workers, 2 at least as many), income group of the household income with the seeker's wage (1 < 40k, 2 40-75k, 3 75-125k,
     * 4 >= 125k, 2016 $). Without the person (calls without it): the base person (male, 30-54, no child, one worker, cars >=
     * workers) and the income group of the earnings class (1 -> 1, 2 -> 2, 3 -> 3). */
    private static final class Seeker {
        int cls = 2, carSeg = 2, incGroup = 2;
        double female, young, old, kids, w2, lic, hhs;   // lic, hhs: rts3 (2026-10-28)
    }

    private static Seeker seeker(int cls, Person p, int householdIncome) {
        final Seeker s = new Seeker();
        s.cls = cls;
        s.incGroup = cls == 1 ? 1 : (cls == 3 ? 3 : 2);
        if (p == null) return s;
        s.female = p.getGender() == de.tum.bgu.msm.data.person.Gender.FEMALE ? 1 : 0;
        s.lic = p.hasDriverLicense() ? 1 : 0;
        s.young = p.getAge() < 30 ? 1 : 0;
        s.old = p.getAge() >= 55 ? 1 : 0;
        final de.tum.bgu.msm.data.household.Household hh = p.getHousehold();
        int workers = 1, kids = 0, cars = 0;
        if (hh != null) {
            cars = hh.getAutos();
            for (Person m : hh.getPersons().values()) {
                if (m.getAge() < 18) kids++;
                if (m.getId() != p.getId() && m.getOccupation() == Occupation.EMPLOYED) workers++;
            }
        }
        s.kids = kids > 0 ? 1 : 0;
        s.hhs = hh == null ? 1 : Math.min(8, hh.getHhSize());
        s.w2 = workers >= 2 ? 1 : 0;
        s.carSeg = cars <= 0 ? 0 : (cars < workers ? 1 : 2);
        s.incGroup = householdIncome < 40000 ? 1 : (householdIncome < 75000 ? 2 : (householdIncome < 125000 ? 3 : 4));
        return s;
    }

    /** current != null: job-to-job search; a vacancy is drawn with the estimated choice, then kept only if it beats the current
     * job in a binary logit on the job-level utilities (g_type + V, without the size term); null = the current job is kept */
    private static final boolean DEBUG_JC = Boolean.getBoolean("silo.debug.jobchoice");
    private long dbgN = 0; private double dbgExpT = 0, dbgRealT = 0, dbgZones = 0, dbgTmin = 0, dbgHome = 0;
    /** Baltimore 2026 (2026-10-28): jobs (filled + vacant) by zone id and type at the start of the year */
    private double[][] jobsByZoneType;

    private Job chooseVacantJobMnl(Zone home, Seeker sk, Job current) {
        if (vacByZone == null) return null;
        // Baltimore 2026 (2026-10-28): job.choice.size = jobs (option; default vacancies): a zone is chosen with the estimated model's size term,
        // S_z = sum_k e^g_k N_zk over ALL its jobs (filled and vacant, as in estimation), among the zones that still have a vacant
        // job, then a vacant job of the zone with probability e^g_k n_zk / sum (type by vacancies). With the vacancies as the size
        // term (job.choice.size = vacancies, the rule up to 4646a77), a zone's weight fell with every job taken during the year,
        // so the later searchers were sent to the zones with leftover vacancies. Tested in smoke_rtswp_jobsize: no effect (52 min in
        // both), because the binding constraint is that the vacancies run out during the year: with -Dsilo.debug.jobchoice=true the
        // 2016 searchers saw a vacancy in 681 of 1,587 zones on average, the nearest one 46.5 min away; the draws follow the
        // weights (expected 57.5 min, realised 57.5). The model over all zones gives 28 min (jobchoice/diag_engine_choice.py).
        final boolean sizeJobs = !"vacancies".equals(properties.jobData.jobChoiceSize) && jobsByZoneType != null;
        final int hz = home.getZoneId();
        final double[] gk = new double[JC_TYPES.length];
        for (int k = 0; k < gk.length; k++) gk[k] = Math.exp(jcCoef.getOrDefault("g_" + JC_TYPES[k], 0.));
        final double[] eff = jcRts ? rtsCoefficients(sk, jcState[hz], hz) : null;
        final double mu = jcCoef.getOrDefault("mu_size", 1.);
        final double[] ezZone = mu != 1. ? new double[vacByZone.length] : null;
        final Random rnd = SiloUtil.getRandomObject();
        final int maxOffers = Math.max(1, properties.jobData.jobChangeOffers);
        int offers = 0;
        double[] w = null; double sum = 0, stay = 0;
        for (int attempt = 0; attempt < 100 + maxOffers; attempt++) {
          if (w == null) {
            w = new double[vacByZone.length * JC_TYPES.length];
            sum = 0;
            for (int z = 1; z < vacByZone.length; z++) {
                final List<Job>[] l = vacByZone[z];
                if (l == null) continue;
                int n = 0;
                for (List<Job> x : l) n += x.size();
                if (n == 0) continue;
                final double t = travelTimes.getTravelTime(home, zoneById[z], properties.transportModel.peakHour_s, TransportMode.car);
                final double ez = Math.exp(jcRts ? rtsUtility(hz, z, t, sk, eff) : zoneUtility(hz, z, t, sk.cls));
                if (sizeJobs) {
                    double sz = 0, sv = 0;
                    for (int k = 0; k < l.length; k++) { sz += (z < jobsByZoneType.length ? jobsByZoneType[z][k] : 0) * gk[k]; sv += l[k].size() * gk[k]; }
                    if (sz <= 0) sz = sv;
                    final double zw = Math.pow(sz, mu) * ez;
                    if (ezZone != null) ezZone[z] = ez;
                    for (int k = 0; k < l.length; k++) {
                        if (l[k].isEmpty()) continue;
                        final double x = zw * l[k].size() * gk[k] / sv;
                        w[z * JC_TYPES.length + k] = x; sum += x;
                    }
                } else if (mu == 1.) {
                    for (int k = 0; k < l.length; k++) {
                        if (l[k].isEmpty()) continue;
                        final double x = l[k].size() * gk[k] * ez;
                        w[z * JC_TYPES.length + k] = x; sum += x;
                    }
                } else {
                    double sz = 0;
                    for (int k = 0; k < l.length; k++) sz += l[k].size() * gk[k];
                    final double f = Math.pow(sz, mu - 1.);
                    ezZone[z] = ez;
                    for (int k = 0; k < l.length; k++) {
                        if (l[k].isEmpty()) continue;
                        final double x = l[k].size() * gk[k] * ez * f;
                        w[z * JC_TYPES.length + k] = x; sum += x;
                    }
                }
            }
            stay = 0;
            if (current != null) {
                final Zone cz = zoneById != null && current.getZoneId() < zoneById.length ? zoneById[current.getZoneId()] : null;
                if (cz == null) return null;
                final double t = travelTimes.getTravelTime(home, cz, properties.transportModel.peakHour_s, TransportMode.car);
                stay = gk[typeIndex(current)] * Math.exp(jcRts ? rtsUtility(hz, cz.getZoneId(), t, sk, eff) : zoneUtility(hz, cz.getZoneId(), t, sk.cls));
            }
          }
            if (sum <= 0 || Double.isNaN(sum)) { if (current == null) logger.warn("No jobs remaining. Could not find new job."); return null; }
            if (DEBUG_JC && attempt == 0) {
                double et = 0; int nz = 0; double tmin = 1e9;
                for (int i = 0; i < w.length; i++) if (w[i] > 0) { final double ti = travelTimes.getTravelTime(home, zoneById[i / JC_TYPES.length], properties.transportModel.peakHour_s, TransportMode.car); et += w[i] * ti; tmin = Math.min(tmin, ti); }
                for (int z = 1; z < vacByZone.length; z++) if (vacByZone[z] != null) { int nn = 0; for (List<Job> x : vacByZone[z]) nn += x.size(); if (nn > 0) nz++; }
                dbgN++; dbgExpT += et / sum; dbgZones += nz; dbgTmin += tmin; dbgHome += jcState[hz] == 24 ? 1 : 0;
            }
            double u = rnd.nextDouble() * sum; int sel = -1;
            for (int i = 0; i < w.length; i++) { if (w[i] <= 0) continue; sel = i; u -= w[i]; if (u <= 0) break; }
            final List<Job> list = vacByZone[sel / JC_TYPES.length][sel % JC_TYPES.length];
            final int r = rnd.nextInt(list.size());
            final Job job = list.get(r);
            list.set(r, list.get(list.size() - 1)); list.remove(list.size() - 1);
            if (jobData.get(job.getId()) == null || job.getWorkerId() > 0) { w = null; continue; }   // filled or removed after it was listed: recompute
            if (current != null) {
                // job-to-job: each drawn vacancy (an offer) against the current job, binary logit on the job-level utilities
                // g_type + V; up to job.change.offers offers, the current job is kept if none is accepted
                final double vc = mu == 1. ? w[sel] / (list.size() + 1)   // w = n g_k exp(V) with n = list size before the draw: one job of the drawn zone and type
                        : gk[sel % JC_TYPES.length] * ezZone[sel / JC_TYPES.length];
                if (rnd.nextDouble() * (vc + stay) < stay) {
                    list.add(job);
                    if (++offers >= maxOffers) return null;   // keeps the current job
                    continue;
                }
            }
            if (DEBUG_JC) dbgRealT += travelTimes.getTravelTime(home, zoneById[job.getZoneId()], properties.transportModel.peakHour_s, TransportMode.car);
            poolTakenOne();
            final List<Job> regionList = vacantJobsByRegion.get(zoneById[job.getZoneId()].getRegion().getId());
            if (regionList != null) regionList.remove(job);
            if (job.getId() == SiloUtil.trackJj) SiloUtil.trackWriter.println("Removed job " + job.getId() + " from list of vacant jobs.");
            return job;
        }
        logger.warn("No jobs remaining. Could not find new job.");
        return null;
    }

    private double zoneUtility(int homeZoneId, int jz, double t, int cls) {
        final int hs = jcState[homeZoneId], js = jcState[jz];
        final boolean high = cls == 3, low = cls == 1;
        final double crossState = hs != js ? 1 : 0, crossCounty = jcCounty[homeZoneId] != jcCounty[jz] ? 1 : 0, toDc = (js == 11 && hs != 11) ? 1 : 0;
        return (jcCoef.get("b_time") + (low ? jcCoef.getOrDefault("b_time_low", 0.) : 0) + (high ? jcCoef.getOrDefault("b_time_high", 0.) : 0)) * t
                + jcCoef.get("b_lntime") * Math.log1p(Math.max(0, t))
                + (jcCoef.get("b_state") + (high ? jcCoef.getOrDefault("b_state_high", 0.) : 0)) * crossState
                + jcCoef.getOrDefault("b_county", 0.) * crossCounty + jcCoef.getOrDefault("b_to_dc", 0.) * toDc;
    }

    // ---- Baltimore 2026 (2026-10-27): rts specification (jobchoice/rts_common.py, ESTIMATION_REPORT_RTS.md). Coefficients are named
    // b_<base>[X<var>...]: base t (car peak min), lt (ln(1 + t)), ls (work-tour mode-choice logsum of the seeker's segment), intra
    // (same zone), cs (another state), cc (another county), dc (DC workplace, home outside DC), reg_<r> (workplace region r of the
    // zones file); var female, young, old, kids, w2, car0, car1, g1, g3, g4 (Seeker), hva / hdc (home in Virginia / DC). The person
    // variables are constant within a search, so they fold into one coefficient per base variable (rtsCoefficients).
    // 2026-10-28 (rts3, jobchoice/job_choice_rts3_spec.md): bases hiearn (share of the zone's jobs earning > $3,333 a month, fixed,
    // zone attribute file) and off_sh, ret_sh, ind_sh (office / retail / industrial share of all the zone's jobs, recomputed every year
    // from the job list); person variables lic (driving licence), hhs (household size, capped at 8), rurh (rural home zone, attribute file)
    // 2026-11-09 (job.choice.model = respec, side_experiments/respec_2026-11/step_by_step/workplace w04 final): base accw = non-work
    // logsum accessibility of the workplace zone for the seeker's segment (car segment against workers x income group, the indexing
    // of the estimation data w01_data.py), read from job.choice.accessibility.file; the centred person interactions of the estimation
    // (t x (x - mean)) are folded into b_t in the coefficient file
    private static final String[] RTS_BASE = {"t", "lt", "ls", "intra", "cs", "cc", "dc", "hiearn", "off_sh", "ret_sh", "ind_sh", "accw"};
    private static final List<String> RTS_VARS = Arrays.asList("female", "young", "old", "kids", "w2", "car0", "car1", "g1", "g3", "g4", "hva", "hdc", "lic", "hhs", "rurh");
    private double[] jcHiearn = new double[0], jcOffSh = new double[0], jcRetSh = new double[0], jcIndSh = new double[0], jcRural = new double[0];
    private boolean jcRts3;
    private boolean jcRts;
    private boolean jcRespec;
    private double[][] jcAccw;       // [carSeg * 4 + incGroup - 1][zone id] (respec)
    private String jcAccwFile;
    private String[] jcRegionNames = new String[0];
    private int[] jcRegion;          // region index of a zone id, -1 = base region
    private float[][] jcLogsum;      // [carSeg * 4 + incGroup - 1][index(h) * n + index(j)]
    private int[] jcLsIndex;         // zone id -> matrix index
    private int jcLsN;

    private double rtsVar(String v, Seeker s, int homeState, int homeZone) {
        switch (v) {
            case "female": return s.female;
            case "young": return s.young;
            case "old": return s.old;
            case "kids": return s.kids;
            case "w2": return s.w2;
            case "car0": return s.carSeg == 0 ? 1 : 0;
            case "car1": return s.carSeg == 1 ? 1 : 0;
            case "g1": return s.incGroup == 1 ? 1 : 0;
            case "g3": return s.incGroup == 3 ? 1 : 0;
            case "g4": return s.incGroup == 4 ? 1 : 0;
            case "hva": return homeState == 51 ? 1 : 0;
            case "hdc": return homeState == 11 ? 1 : 0;
            case "lic": return s.lic;
            case "hhs": return s.hhs;
            case "rurh": return homeZone >= 0 && homeZone < jcRural.length ? jcRural[homeZone] : 0;
            default: throw new IllegalArgumentException("unknown job choice variable " + v);
        }
    }

    /** index of the base variable of a coefficient name (b_<base>X...), RTS_BASE.length + region index for reg_<r>, -1 = not a utility term */
    private int rtsBaseIndex(String base) {
        for (int i = 0; i < RTS_BASE.length; i++) if (RTS_BASE[i].equals(base)) return i;
        if (base.startsWith("reg_")) {
            for (int i = 0; i < jcRegionNames.length; i++) if (jcRegionNames[i].equals(base.substring(4))) return RTS_BASE.length + i;
            throw new IllegalArgumentException("job choice region " + base + " not in the zones file");
        }
        throw new IllegalArgumentException("unknown job choice variable " + base);
    }

    private double[] rtsCoefficients(Seeker s, int homeState, int homeZone) {
        final double[] e = new double[RTS_BASE.length + jcRegionNames.length];
        for (Map.Entry<String, Double> c : jcCoef.entrySet()) {
            if (!c.getKey().startsWith("b_")) continue;
            final String[] parts = c.getKey().substring(2).split("X");
            double x = c.getValue();
            for (int q = 1; q < parts.length; q++) x *= rtsVar(parts[q], s, homeState, homeZone);
            e[rtsBaseIndex(parts[0])] += x;
        }
        return e;
    }

    private double rtsUtility(int hz, int jz, double t, Seeker s, double[] e) {
        final int hs = jcState[hz], js = jcState[jz];
        double v = e[0] * t + e[1] * Math.log1p(Math.max(0, t));
        if (e[2] != 0) v += e[2] * jcLogsum[s.carSeg * 4 + s.incGroup - 1][jcLsIndex[hz] * jcLsN + jcLsIndex[jz]];
        if (hz == jz) v += e[3];
        if (jcRts3 && jz < jcHiearn.length) v += e[7] * jcHiearn[jz] + e[8] * jcOffSh[jz] + e[9] * jcRetSh[jz] + e[10] * jcIndSh[jz];
        if (e[11] != 0) v += e[11] * jcAccw[s.carSeg * 4 + s.incGroup - 1][jz];
        if (hs != js) v += e[4];
        if (jcCounty[hz] != jcCounty[jz]) v += e[5];
        if (js == 11 && hs != 11) v += e[6];
        final int r = jcRegion[jz];
        if (r >= 0) v += e[RTS_BASE.length + r];
        return v;
    }

    private Map<String, Double> jcCoef;   // Baltimore 2026: estimated workplace choice, empty map = not used
    private int[] jcState, jcCounty;

    private boolean jobChoice() {
        if (jcCoef == null) loadJobChoice();
        return !jcCoef.isEmpty();
    }

    private synchronized void loadJobChoice() {
        if (jcCoef == null) {
            final Map<String, Double> c = new HashMap<>();
            final String file = properties.jobData.jobChoiceCoefficientsFile;
            if (file != null && !file.isBlank()) {
                try {
                    final List<String> cl = java.nio.file.Files.readAllLines(java.nio.file.Paths.get(properties.main.baseDirectory + file));
                    for (String line : cl.subList(1, cl.size())) {
                        final String[] f = line.split(",");
                        if (f.length >= 2) c.put(f[0].trim(), Double.parseDouble(f[1].trim()));
                    }
                    final List<String> zl = java.nio.file.Files.readAllLines(java.nio.file.Paths.get(properties.main.baseDirectory + properties.jobData.jobChoiceZonesFile));
                    final List<String> h = Arrays.asList(zl.get(0).split(","));
                    final int iZ = h.indexOf("zone"), iS = h.indexOf("state"), iC = h.indexOf("county"), iR = h.indexOf("region");
                    int max = 0;
                    for (String line : zl.subList(1, zl.size())) max = Math.max(max, Integer.parseInt(line.split(",")[iZ].trim()));
                    jcState = new int[max + 1]; jcCounty = new int[max + 1];
                    final String[] regionOf = new String[max + 1];
                    for (String line : zl.subList(1, zl.size())) {
                        final String[] f = line.split(",");
                        final int z = Integer.parseInt(f[iZ].trim());
                        jcState[z] = Integer.parseInt(f[iS].trim()); jcCounty[z] = Integer.parseInt(f[iC].trim());
                        if (iR >= 0) regionOf[z] = f[iR].trim();
                    }
                    jcRespec = "respec".equals(properties.jobData.jobChoiceModel);
                    jcRts3 = "rts3".equals(properties.jobData.jobChoiceModel) || jcRespec;
                    jcRts = "rts".equals(properties.jobData.jobChoiceModel) || jcRts3;
                    if (jcRts) loadRts(c, regionOf, max);
                    if (jcRts3) loadRts3(max);
                    else if (!jcRts && !"lodes".equals(properties.jobData.jobChoiceModel)) throw new IllegalArgumentException("job.choice.model must be lodes, rts, rts3 or respec: " + properties.jobData.jobChoiceModel);
                } catch (java.io.IOException e) {
                    throw new RuntimeException("Could not read the job choice files " + file, e);
                }
                logger.info("Workplace choice: estimated MNL (" + properties.jobData.jobChoiceModel + " specification) " + c);
            }
            jcCoef = c;
        }
    }

    /** rts specification: workplace regions (zones file, column region; the regions with a reg_ coefficient are indexed, the others
     * are the base) and the logsum matrices (job.choice.logsum.dir: zones.csv with idx,zone and ls_c<carSeg>_g<incGroup>.f32, float32
     * little endian, n x n row-major in the order of zones.csv) */
    /** rts3: hiearn and rural from the zone attribute file (fixed); the job-mix shares start from the file and are recomputed from
     * the job list in every identifyVacantJobs (start of the year) */
    private void loadRts3(int maxZone) throws java.io.IOException {
        final List<String> zl = java.nio.file.Files.readAllLines(java.nio.file.Paths.get(properties.main.baseDirectory + properties.jobData.jobChoiceZoneAttributesFile));
        final List<String> h = Arrays.asList(zl.get(0).split(","));
        final int iZ = h.indexOf("zone"), iH = h.indexOf("hiearn"), iO = h.indexOf("off_sh"), iR = h.indexOf("ret_sh"), iI = h.indexOf("ind_sh"), iU = h.indexOf("rural");
        jcHiearn = new double[maxZone + 1]; jcOffSh = new double[maxZone + 1]; jcRetSh = new double[maxZone + 1]; jcIndSh = new double[maxZone + 1]; jcRural = new double[maxZone + 1];
        for (String line : zl.subList(1, zl.size())) {
            final String[] f = line.split(",");
            final int z = Integer.parseInt(f[iZ].trim());
            if (z > maxZone) continue;
            jcHiearn[z] = Double.parseDouble(f[iH].trim()); jcRural[z] = Double.parseDouble(f[iU].trim());
            jcOffSh[z] = Double.parseDouble(f[iO].trim()); jcRetSh[z] = Double.parseDouble(f[iR].trim()); jcIndSh[z] = Double.parseDouble(f[iI].trim());
        }
        if (!Boolean.getBoolean("silo.jobchoice.verify.fileShares")) updateJobMixShares();
        logger.info("Workplace choice (rts3): zone attributes read from " + properties.jobData.jobChoiceZoneAttributesFile);
        if (jcRespec) {
            jcAccw = new double[12][maxZone + 1];
            loadAccw(properties.main.startYear);
        }
    }

    /** Baltimore 2026 (respec): non-work logsum accessibility by segment and zone from job.choice.accessibility.file ({year}: latest <= year) */
    private void loadAccw(int year) {
        final String pat = properties.jobData.jobChoiceAccessibilityFile;
        if (pat == null || pat.isBlank()) {
            if (jcCoef != null && jcCoef.containsKey("b_accw") || jcCoef == null) throw new IllegalArgumentException("job.choice.model = respec needs job.choice.accessibility.file");
            return;
        }
        final String p0 = java.nio.file.Paths.get(pat).isAbsolute() ? pat : properties.main.baseDirectory + pat;
        int y = year;
        while (y >= 1990 && !new java.io.File(p0.replace("{year}", String.valueOf(y))).exists()) y--;
        if (y < 1990) throw new IllegalArgumentException("no job choice accessibility file for year <= " + year + ": " + p0);
        final String f = p0.replace("{year}", String.valueOf(y));
        if (f.equals(jcAccwFile)) return;
        final String[] cars = {"nocar", "carlt", "carge"}, groups = {"LOW", "MEDIUM", "HIGH", "VERY_HIGH"};
        for (double[] a : jcAccw) Arrays.fill(a, 0.);
        int n = 0;
        try {
            final List<String> l = java.nio.file.Files.readAllLines(java.nio.file.Paths.get(f));
            final List<String> h = Arrays.asList(l.get(0).split(","));
            final int iZ = h.indexOf("zone"), iS = h.indexOf("segment"), iP = h.indexOf("purpose"), iA = h.indexOf("A");
            for (String line : l.subList(1, l.size())) {
                final String[] x = line.split(",");
                if (!"nonwork".equals(x[iP].trim())) continue;
                final int z = Integer.parseInt(x[iZ].trim());
                if (z >= jcAccw[0].length) continue;
                final String sg = x[iS].trim(); final int u = sg.lastIndexOf('_');
                final int g = Arrays.asList(groups).indexOf(sg.substring(0, u)), c = Arrays.asList(cars).indexOf(sg.substring(u + 1));
                if (g < 0 || c < 0) continue;
                final double a = Double.parseDouble(x[iA].trim());
                jcAccw[c * 4 + g][z] = Double.isNaN(a) ? 0. : a; n++;
            }
        } catch (java.io.IOException e) { throw new RuntimeException("Could not read " + f, e); }
        jcAccwFile = f;
        logger.info("Workplace choice (respec): non-work accessibility of the workplace read from " + f + " (" + n + " values)");
    }

    /**
     * Baltimore 2026 (2026-10-28): verification of the rts / rts3 utility against reference values, without a simulation. With
     * -Dsilo.jobchoice.verify=<workers.csv>;<zone_jobs.csv>;<out.csv> (and -Dsilo.jobchoice.verify.fileShares=true to keep the
     * attribute file's job-mix shares) the first prepareYear computes, for every test worker (columns test_id, home_zone, female, age,
     * car_segment, income_group, driving_licence, hh_size_capped_8), V_j = mu ln S_j + the engine's rtsUtility for every zone of
     * zone_jobs.csv (zone, RET, OFF, IND, OTH: the N_jk of the size term), writes test_id, zone, V, ln_prob and exits.
     */
    private void verifyRts(String spec) {
        final String[] f = spec.split(";");
        if (!jobChoice() || !jcRts) throw new IllegalStateException("verification needs job.choice.model = rts or rts3");
        try {
            final List<String> zl = java.nio.file.Files.readAllLines(java.nio.file.Paths.get(f[1]));
            final List<String> zh = Arrays.asList(zl.get(0).split(","));
            final int nz = zl.size() - 1; final int[] zid = new int[nz]; final double[] lnS = new double[nz];
            final double mu = jcCoef.getOrDefault("mu_size", 1.);
            for (int i = 0; i < nz; i++) {
                final String[] x = zl.get(i + 1).split(",");
                zid[i] = Integer.parseInt(x[zh.indexOf("zone")].trim());
                double sz = 0;
                for (int k = 0; k < JC_TYPES.length; k++) sz += Double.parseDouble(x[zh.indexOf(JC_TYPES[k])].trim()) * Math.exp(jcCoef.getOrDefault("g_" + JC_TYPES[k], 0.));
                lnS[i] = sz > 0 ? mu * Math.log(sz) : Double.NEGATIVE_INFINITY;
            }
            final List<String> wl = java.nio.file.Files.readAllLines(java.nio.file.Paths.get(f[0]));
            final List<String> wh = Arrays.asList(wl.get(0).split(","));
            try (java.io.PrintWriter out = new java.io.PrintWriter(f[2])) {
                out.println("test_id,zone,V,ln_prob");
                for (String line : wl.subList(1, wl.size())) {
                    final String[] x = line.split(",");
                    final Seeker sk = new Seeker();
                    final int age = Integer.parseInt(x[wh.indexOf("age")].trim());
                    sk.female = Double.parseDouble(x[wh.indexOf("female")].trim()); sk.young = age < 30 ? 1 : 0; sk.old = age >= 55 ? 1 : 0;
                    sk.carSeg = Integer.parseInt(x[wh.indexOf("car_segment")].trim()); sk.incGroup = Integer.parseInt(x[wh.indexOf("income_group")].trim());
                    sk.lic = Double.parseDouble(x[wh.indexOf("driving_licence")].trim()); sk.hhs = Double.parseDouble(x[wh.indexOf("hh_size_capped_8")].trim());
                    if (wh.contains("kids")) sk.kids = Double.parseDouble(x[wh.indexOf("kids")].trim());   // respec: children in the household (0/1)
                    if (wh.contains("workers")) sk.w2 = Double.parseDouble(x[wh.indexOf("workers")].trim()) >= 2 ? 1 : 0;   // respec
                    final int hz = Integer.parseInt(x[wh.indexOf("home_zone")].trim());
                    final double[] eff = rtsCoefficients(sk, jcState[hz], hz);
                    final double[] v = new double[nz]; double mx = Double.NEGATIVE_INFINITY;
                    for (int i = 0; i < nz; i++) {
                        final double tt = travelTimes.getTravelTime(geoData.getZones().get(hz), geoData.getZones().get(zid[i]), properties.transportModel.peakHour_s, TransportMode.car);
                        v[i] = lnS[i] + rtsUtility(hz, zid[i], tt, sk, eff); mx = Math.max(mx, v[i]);
                    }
                    double se = 0; for (double vi : v) se += Math.exp(vi - mx);
                    final double lse = mx + Math.log(se);
                    for (int i = 0; i < nz; i++) out.println(x[wh.indexOf("test_id")].trim() + "," + zid[i] + "," + v[i] + "," + (v[i] - lse));
                }
            }
        } catch (java.io.IOException e) { throw new RuntimeException("verification failed", e); }
        logger.error("Workplace-choice verification written to " + f[2] + "; exiting");
        System.exit(0);
    }

    /** rts3: office / retail / industrial shares of all jobs (filled and vacant) of every zone, from the job list */
    private void updateJobMixShares() {
        if (!jcRts3 || jobsByZoneType == null) return;
        for (int z = 0; z < jcOffSh.length && z < jobsByZoneType.length; z++) {
            final double[] n = jobsByZoneType[z];
            final double tot = n[0] + n[1] + n[2] + n[3];
            jcRetSh[z] = tot > 0 ? n[0] / tot : 0; jcOffSh[z] = tot > 0 ? n[1] / tot : 0; jcIndSh[z] = tot > 0 ? n[2] / tot : 0;   // JC_TYPES = RET, OFF, IND, OTH
        }
    }

    private void loadRts(Map<String, Double> c, String[] regionOf, int maxZone) throws java.io.IOException {
        final List<String> regs = new ArrayList<>();
        for (String k : c.keySet()) {
            if (!k.startsWith("b_")) continue;
            final String[] parts = k.substring(2).split("X");
            for (int q = 1; q < parts.length; q++) if (!RTS_VARS.contains(parts[q])) throw new IllegalArgumentException("unknown job choice variable " + parts[q] + " in " + k);
            if (parts[0].startsWith("reg_")) { if (!regs.contains(parts[0].substring(4))) regs.add(parts[0].substring(4)); }
            else if (!Arrays.asList(RTS_BASE).contains(parts[0])) throw new IllegalArgumentException("unknown job choice variable " + parts[0] + " in " + k);
        }
        Collections.sort(regs);
        jcRegionNames = regs.toArray(new String[0]);
        jcRegion = new int[maxZone + 1];
        Arrays.fill(jcRegion, -1);
        for (int z = 0; z <= maxZone; z++) if (regionOf[z] != null) jcRegion[z] = regs.indexOf(regionOf[z]);
        final String dir = properties.main.baseDirectory + properties.jobData.jobChoiceLogsumDir + "/";
        final List<String> zl = java.nio.file.Files.readAllLines(java.nio.file.Paths.get(dir + "zones.csv"));
        final List<String> h = Arrays.asList(zl.get(0).split(","));
        final int iI = h.indexOf("idx"), iZ = h.indexOf("zone");
        jcLsN = zl.size() - 1;
        jcLsIndex = new int[maxZone + 1];
        Arrays.fill(jcLsIndex, -1);
        for (String line : zl.subList(1, zl.size())) {
            final String[] f = line.split(",");
            final int z = Integer.parseInt(f[iZ].trim());
            if (z <= maxZone) jcLsIndex[z] = Integer.parseInt(f[iI].trim());
        }
        for (int z = 1; z <= maxZone; z++) if (jcState[z] > 0 && jcLsIndex[z] < 0) throw new IllegalArgumentException("zone " + z + " missing in " + dir + "zones.csv");
        jcLogsum = new float[12][];
        for (int s = 0; s < 3; s++) {
            for (int g = 1; g <= 4; g++) {
                final byte[] b = java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(dir + "ls_c" + s + "_g" + g + ".f32"));
                if (b.length != 4L * jcLsN * jcLsN) throw new IllegalArgumentException("logsum file size " + b.length + " for " + jcLsN + " zones: ls_c" + s + "_g" + g);
                final float[] a = new float[jcLsN * jcLsN];
                java.nio.ByteBuffer.wrap(b).order(java.nio.ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(a);
                jcLogsum[s * 4 + g - 1] = a;
            }
        }
        logger.info("Workplace choice (rts): regions " + Arrays.toString(jcRegionNames) + ", mode-choice logsums of 12 segments read from " + dir + " (" + jcLsN + " zones)");
    }
    /**
     * Baltimore 2026 (estimated workplace choice, 2_silo/jobchoice/ESTIMATION_REPORT.md): weight of one sampled vacant job =
     * exp(V), V = g_type + b_time t + b_lntime ln(1+t) + b_time_low t low + b_time_high t high + (b_state + b_state_high high)
     * crossState + b_county crossCounty + b_to_dc toDC, t = car peak time (min). The candidates are a uniform sample of the
     * vacancies of the year, so a zone's number of vacancies of each type is the size term (coefficient 1, estimated 0.997).
     */
    private double jobChoiceWeight(int homeZoneId, Job job, double t, int cls) {
        final int jz = job.getZoneId();
        final int hs = jcState[homeZoneId], js = jcState[jz];
        final boolean high = cls == 3, low = cls == 1;
        final double crossState = hs != js ? 1 : 0, crossCounty = jcCounty[homeZoneId] != jcCounty[jz] ? 1 : 0, toDc = (js == 11 && hs != 11) ? 1 : 0;
        final String type = job.getType() == null ? "" : job.getType().replace("\"", "");
        final double v = jcCoef.getOrDefault("g_" + type, 0.) + (jcCoef.get("b_time") + (low ? jcCoef.getOrDefault("b_time_low", 0.) : 0) + (high ? jcCoef.getOrDefault("b_time_high", 0.) : 0)) * t
                + jcCoef.get("b_lntime") * Math.log1p(Math.max(0, t))
                + (jcCoef.get("b_state") + (high ? jcCoef.getOrDefault("b_state_high", 0.) : 0)) * crossState
                + jcCoef.getOrDefault("b_county", 0.) * crossCounty + jcCoef.getOrDefault("b_to_dc", 0.) * toDc;
        return Math.exp(v);
    }

    /**
     * Baltimore 2026 (job choice by commute time from the home): the region of the job was chosen with the commute-time
     * probability of the shortest travel time from the home zone to any zone of the region times the region's number of
     * vacant jobs, and the job inside the region at random. Adjacent regions with many vacancies therefore looked as close
     * as the home region and the job inside the region was placed without regard to the home: the share of Maryland
     * workers employed in their home county fell from 55 % (base year) to 37 % in 2020 and 21 % in 2024 (LODES 2016-2023:
     * 49 % to 47 %), the commute utility of the housing choice fell every year and with it the satisfaction of the
     * households, which raised the move rate year after year. The job is now drawn from a random sample of
     * {@value #JOB_SEARCH_SAMPLE} vacant jobs of all regions (each vacant job equally likely) with probability proportional
     * to an impedance of the zone-to-zone car travel time from the home zone (if none is within reach, proportional to
     * 1 / travel time), i.e. a destination choice over vacant jobs. The impedance (job.search.impedance.file,
     * input_build/build_job_search_impedance.py) is the observed share of base-year commutes at each travel time divided
     * by the share of all home-job pairs at that time, so that hires reproduce the base-year commute-time distribution;
     * the commute-time distribution itself as impedance counts the opportunities twice (hires in 2017 had a median
     * commute of 51 min against 26 min of the base-year workers).
     */
    private Job findVacantJobByCommuteTime(Zone homeZone, Collection<Region> regions, int earningsClass) {
        if (jobChoice()) return chooseVacantJobMnl(homeZone, earningsClass);
        final List<List<Job>> lists = new ArrayList<>();
        int total = 0;
        for (Region reg : regions) {
            final List<Job> l = vacantJobsByRegion.get(reg.getId());
            if (l != null && !l.isEmpty()) { lists.add(l); total += l.size(); }
        }
        if (total == 0) {
            logger.warn("No jobs remaining. Could not find new job.");
            return null;
        }
        final Random rnd = SiloUtil.getRandomObject();
        final int k = Math.min(JOB_SEARCH_SAMPLE, total);
        final int[] candList = new int[k], candIndex = new int[k];
        final double[] w = new double[k], wFar = new double[k];
        double sum = 0, sumFar = 0;
        for (int i = 0; i < k; i++) {
            int r = rnd.nextInt(total), li = 0;
            while (r >= lists.get(li).size()) { r -= lists.get(li).size(); li++; }
            candList[i] = li; candIndex[i] = r;
            final Job job = lists.get(li).get(r);
            // Baltimore 2026: the vacancy lists are built in prepareYear; a job removed afterwards by the job-market update stays in
            // them, and hires into removed jobs (about 50,000 a year in the 2016-2020 check) lost them again at the year-end check
            if (jobData.get(job.getId()) == null || job.getWorkerId() > 0) { w[i] = 0; wFar[i] = 0; continue; }
            final double ttExact = travelTimes.getTravelTime(homeZone, geoData.getZones().get(job.getZoneId()), properties.transportModel.peakHour_s, TransportMode.car);
            final int tt = (int) (ttExact + 0.5);
            w[i] = jobChoice() ? jobChoiceWeight(homeZone.getZoneId(), job, ttExact, earningsClass) : impedance(tt);
            wFar[i] = 1. / Math.max(1, tt);
            sum += w[i]; sumFar += wFar[i];
        }
        if (sum <= 0 && sumFar <= 0) {
            logger.warn("No jobs remaining. Could not find new job.");
            return null;
        }
        final double[] weights = sum > 0 ? w : wFar;
        double u = rnd.nextDouble() * (sum > 0 ? sum : sumFar);
        int sel = -1;
        for (int i = 0; i < k; i++) { if (weights[i] <= 0) continue; sel = i; u -= weights[i]; if (u <= 0) break; }
        final Job selectedJob = lists.get(candList[sel]).remove(candIndex[sel]);
        if (selectedJob.getId() == SiloUtil.trackJj) {
            SiloUtil.trackWriter.println("Removed job " + selectedJob.getId() + " from list of vacant jobs.");
        }
        return selectedJob;
    }

    /**
     * add job jobId to vacancy list
     * @param job
     */
    private void addJobToVacancyList(Job job) {
        poolAdded++;

        int region = geoData.getZones().get(job.getZoneId()).getRegion().getId();
        vacantJobsByRegion.putIfAbsent(region, new ArrayList<>());
        vacantJobsByRegion.get(region).add(job);
        vacZoneAdd(job);

        if (job.getId() == SiloUtil.trackJj) {
            SiloUtil.trackWriter.println("Added job " + job.getId() + " to list of vacant jobs.");
        }
        }




    private void calculateJobDensityByZone() {
        final Multiset<Integer> counter = ConcurrentHashMultiset.create();
        jobData.getJobs().parallelStream().forEach(j -> counter.add(j.getZoneId()));
        geoData.getZones().forEach((id, zone) -> zonalJobDensity.put(id, (double) (counter.count(id) / zone.getArea_sqmi())));
    }


    @Override
    public double getJobDensityInZone(int zone) {
        return zonalJobDensity.get(zone);
    }

    @Override
    public int getJobDensityCategoryOfZone(int zone) {
        // return job density category 1 to 10 of zone
        //TODO: magic numbers
        float[] densityCategories = {0.f, 0.143f, 0.437f, 0.865f, 1.324f, 1.8778f, 2.664f, 3.99105f, 6.f, 12.7f};
        for (int i = 0; i < densityCategories.length; i++) {
            if (zonalJobDensity.get(zone) < densityCategories[i]) {
                return i;
            }
        }
        return densityCategories.length;
    }

    @Override
    public void addJob(Job jj) {
        this.jobData.addJob(jj);
        // Baltimore 2026: a vacant job added during the year (job-market update, which runs after the vacancy lists are built in
        // prepareYear) is offered at once; before, it waited a year: the lists ran empty (4.4 million exhausted searches in the
        // 2016-2020 check) while 3 % of the jobs stayed vacant, and the young age groups, who need hires, stayed 3-8 % below the
        // ACS employment rate. Lists are rebuilt from scratch in prepareYear, so jobs read at setup are not counted twice.
        // the job-market update adds jobs from several threads: the append to the region list is synchronized
        if (jj.getWorkerId() == -1 && jj.getZoneId() > 0 && geoData.getZones().containsKey(jj.getZoneId())) {
            synchronized (vacantJobsByRegion) { addJobToVacancyList(jj); }
        }
    }

    @Override
    public JobFactory getFactory() {
        return jobFactory;
    }

    @Override
    public Map<Integer, List<Job>> getVacantJobsByRegion() {
        return vacantJobsByRegion;
    }
}
