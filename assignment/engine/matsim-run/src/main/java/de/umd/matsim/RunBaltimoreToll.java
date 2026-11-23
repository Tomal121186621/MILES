package de.umd.matsim;

import org.matsim.api.core.v01.Scenario;
import org.matsim.api.core.v01.TransportMode;
import org.matsim.api.core.v01.population.Person;
import org.matsim.contrib.roadpricing.RoadPricingConfigGroup;
import org.matsim.contrib.roadpricing.RoadPricingModule;
import org.matsim.core.config.Config;
import org.matsim.core.config.ConfigUtils;
import org.matsim.core.config.groups.*;
import org.matsim.core.controler.AbstractModule;
import org.matsim.core.controler.Controler;
import org.matsim.core.controler.OutputDirectoryHierarchy.OverwriteFileSetting;
import org.matsim.core.population.PersonUtils;
import org.matsim.core.scenario.ScenarioUtils;

import java.util.List;
import java.util.Set;

/**
 * I-695 congestion-pricing MATSim runner (Phase 1 = toll-capable base).
 *
 * Extends the validated RunBaltimore assignment with an INNER-LOOP mode-choice response so a road-pricing
 * toll can shift mode / route / departure time with NO outer loop (MATSim-NYC recipe, paper Sec. 5):
 *
 *   1. The Maryland MNL mode-choice model is ported into the MATSim scorer per MODE_SCORER_MAPPING.md
 *      (per-mode ASC + travel-time coef + monetaryDistanceRate; car travel-time NORMALIZED to 0 and the
 *      time cost carried by marginalUtilityOfPerforming = 0.78/h; single car-anchored
 *      marginalUtilityOfMoney = 0.026 utils/$ so the toll is scored car-consistently).
 *   2. SubtourModeChoice (+ ReRoute + TimeAllocationMutator + ChangeExpBeta) lets residents re-choose.
 *      Car availability is honoured from the population's `autos`/`driversLicense` attributes.
 *   3. RoadPricing (org.matsim.contrib.roadpricing) adds the I-695 toll as monetary disutility when a
 *      toll file is supplied. With tollFile = NONE (Phase-1 base) no toll is applied — the run is the
 *      gate that must reproduce the validated base mode shares once the ASCs are re-anchored.
 *
 * The five mode ASCs are overridable at launch (-Dasc.car/-Dasc.pt/-Dasc.ride/-Dasc.walk/-Dasc.bike)
 * so the base can be re-anchored across short calibration passes (ASC += ln(target/sim)) WITHOUT
 * recompiling; car is the reference and stays 0. Everything else matches the validated base config
 * (flowCap 0.10, storageCap 0.13, stuckTime 120, removeStuckVehicles, endTime 36h).
 *
 * Usage: RunBaltimoreToll <network> <plans> <schedule> <vehicles> <outDir> <iterations> <flowCap>
 *                         [storageCap] [tollFile|NONE]
 */
public class RunBaltimoreToll {

    public static void main(String[] args) {
        String network    = args[0];
        String plans       = args[1];
        String schedule    = args[2];
        String vehicles    = args[3];
        String outDir      = args[4];
        int iterations     = Integer.parseInt(args[5]);
        double flowCap     = Double.parseDouble(args[6]);
        double storageCap  = args.length > 7 ? Double.parseDouble(args[7]) : 0.5;
        String tollFile    = args.length > 8 ? args[8] : "NONE";

        // --- re-anchorable mode ASCs (Sec. 3 pre-anchor starting values; car frozen at 0 reference) ---
        double ascCar  = Double.parseDouble(System.getProperty("asc.car",  "0.00"));
        double ascPt   = Double.parseDouble(System.getProperty("asc.pt",   "2.25"));
        double ascRide = Double.parseDouble(System.getProperty("asc.ride", "3.87"));
        double ascWalk = Double.parseDouble(System.getProperty("asc.walk", "3.97"));
        double ascBike = Double.parseDouble(System.getProperty("asc.bike", "-0.20"));

        int nThreads = Integer.parseInt(System.getProperty("threads", "8"));
        Config config = ConfigUtils.createConfig();
        config.global().setCoordinateSystem("EPSG:26985");
        config.global().setNumberOfThreads(nThreads);

        config.network().setInputFile(network);
        // R2 (2026-09-30): optional time-variant network for capacity policies (peak-hour shoulder lane).
        String changeEvents = System.getProperty("network.changeevents", "NONE");
        if (!"NONE".equals(changeEvents)) {
            config.network().setTimeVariantNetwork(true);
            config.network().setChangeEventsInputFile(changeEvents);
            System.out.println("[RunBaltimoreToll] time-variant network, change events = " + changeEvents);
        }
        config.plans().setInputFile(plans);

        // --- transit (pt routed on the mapped schedule) ---
        config.transit().setUseTransit(true);
        config.transit().setTransitScheduleFile(schedule);
        config.transit().setVehiclesFile(vehicles);
        config.transit().setTransitModes(Set.of("pt"));
        // stop search (defaults = all earlier runs). -Dpt.search.radius / -Dpt.extension.radius in metres.
        config.transitRouter().setSearchRadius(Double.parseDouble(System.getProperty("pt.search.radius", "4000.0")));
        config.transitRouter().setExtensionRadius(Double.parseDouble(System.getProperty("pt.extension.radius", "2000.0")));
        // transfer penalty of the SwissRailRaptor in utils per transfer (-Dpt.transfer.penalty; default 0 = all earlier runs).
        // The router costs in-vehicle time at (performing - marginal utility of pt travel) = 0.78 + 1.02 = 1.80 utils/h, so
        // 0.30 utils = 10 minutes of in-vehicle time.
        {
            ch.sbb.matsim.config.SwissRailRaptorConfigGroup srr = ConfigUtils.addOrGetModule(config, ch.sbb.matsim.config.SwissRailRaptorConfigGroup.class);
            srr.setTransferPenaltyBaseCost(Double.parseDouble(System.getProperty("pt.transfer.penalty", "0.0")));
            // 2026-11-16 -Dpt.car.access=true: intermodal access and egress of the SwissRailRaptor (SBB). Walk to every stop as before
            // (initial radius = pt.search.radius, extended by pt.extension.radius until a stop is found, as the non-intermodal router does); car only for persons with ptCarAccess = true
            // (household car and licence, set below) and only to stops with parkAndRide = true, routed to their accessLinkId_car link
            // (both stop attributes written by PreparePseudoPt). Car: initial 10 km, extended by 5 km up to -Dpt.car.radius (default 25 km).
            if (Boolean.getBoolean("pt.car.access")) {
                double sr = config.transitRouter().getSearchRadius(), er = config.transitRouter().getExtensionRadius();
                srr.setUseIntermodalAccessEgress(true);
                srr.addIntermodalAccessEgress(new ch.sbb.matsim.config.SwissRailRaptorConfigGroup.IntermodalAccessEgressParameterSet()
                        .setMode(TransportMode.walk).setInitialSearchRadius(sr).setSearchExtensionRadius(er).setMaxRadius(100000.0));
                double cr = Double.parseDouble(System.getProperty("pt.car.radius", "25000"));
                srr.addIntermodalAccessEgress(new ch.sbb.matsim.config.SwissRailRaptorConfigGroup.IntermodalAccessEgressParameterSet()
                        .setMode(TransportMode.car).setInitialSearchRadius(Math.min(10000.0, cr)).setSearchExtensionRadius(5000.0).setMaxRadius(cr)
                        .setPersonFilterAttribute("ptCarAccess").setPersonFilterValue("true")
                        .setStopFilterAttribute("parkAndRide").setStopFilterValue("true").setLinkIdAttribute("accessLinkId_car"));
                System.out.println("[RunBaltimoreToll] pt intermodal access: walk " + sr + " m, +" + er + " m steps; car " + cr + " m to park-and-ride stops");
            }
        }

        // --- controller ---
        config.controller().setOutputDirectory(outDir);
        // replication support: -Dseed=<long> (default = MATSim's 4711, identical to all earlier runs)
        config.global().setRandomSeed(Long.getLong("seed", 4711L));
        System.out.println("[RunBaltimoreToll] random seed = " + config.global().getRandomSeed());
        config.controller().setFirstIteration(0);
        config.controller().setLastIteration(iterations);
        config.controller().setOverwriteFileSetting(OverwriteFileSetting.deleteDirectoryIfExists);
        config.controller().setMobsim("qsim");
        // Disk-light calibration: the subsample re-anchor passes only need modestats.csv (written every
        // iteration at the output root regardless), so suppress the big per-iteration writes (events,
        // plans, snapshots, linkStats) and the end-of-run dump. The FINAL frozen-ASC base run sets
        // -Dwrite.outputs=true to restore full outputs for validation.
        boolean writeOutputs = Boolean.parseBoolean(System.getProperty("write.outputs", "true"));
        if (writeOutputs) {
            // 2026-11-02 (validation study, disk): -Dwrite.events.interval, -Dwrite.plans.interval, -Dlinkstats.interval, -Dlinkstats.average
            // override the defaults below (unset = unchanged behaviour)
            config.controller().setWriteEventsInterval(Integer.getInteger("write.events.interval", iterations));
            config.controller().setWritePlansInterval(Integer.getInteger("write.plans.interval", iterations));
            int linkStatsInterval = Integer.getInteger("linkstats.interval", Math.max(1, iterations / 8));
            config.linkStats().setWriteLinkStatsInterval(linkStatsInterval);
            config.linkStats().setAverageLinkStatsOverIterations(Integer.getInteger("linkstats.average", Math.min(5, linkStatsInterval)));
        } else {
            // disk-light calibration: no per-iteration events/plans/snapshots/linkStats, BUT keep the
            // end-of-run dump ON so output_plans.xml.gz is written (small on the subsample) for
            // warm-starting the next pass. (~15-25 MB; cleaned between passes.)
            config.controller().setWriteEventsInterval(0);
            config.controller().setWritePlansInterval(0);
            config.controller().setWriteSnapshotsInterval(0);
            config.controller().setDumpDataAtEnd(true);
            config.linkStats().setWriteLinkStatsInterval(0);
        }

        // --- qsim (scaled to the 10% sample) ---
        config.qsim().setFlowCapFactor(flowCap);
        config.qsim().setStorageCapFactor(storageCap);
        config.qsim().setStartTime(0);
        config.qsim().setEndTime(36 * 3600);
        config.qsim().setNumberOfThreads(nThreads);
        // Background layers (2026-10-04): -Dtrucks=true adds a 'truck' main mode (PCE -Dtruck.pcu, default 2.0) and route-only
        // replanning for agents with subpopulation 'background' (external, commercial and truck agents). Off by default = old runs unchanged.
        final boolean trucks = Boolean.parseBoolean(System.getProperty("trucks", "false"));
        final double truckPcu = Double.parseDouble(System.getProperty("truck.pcu", "2.0"));
        if (trucks) {
            config.qsim().setMainModes(List.of("car", "truck", "truckhz"));
            config.qsim().setVehiclesSource(QSimConfigGroup.VehiclesSource.modeVehicleTypesFromVehiclesData);
        } else {
            config.qsim().setMainModes(List.of("car"));
            config.qsim().setVehiclesSource(QSimConfigGroup.VehiclesSource.defaultVehicle);
        }
        config.qsim().setInsertingWaitingVehiclesBeforeDrivingVehicles(true);
        config.qsim().setStuckTime(120.0);
        // 2026-11-16 transit practice (Open Berlin scenario, MATSim developers): -Dqsim.remove.stuck=false keeps stuck vehicles in the
        // simulation (the MATSim default; true = all earlier runs, where a removed bus stranded everyone waiting for it).
        config.qsim().setRemoveStuckVehicles(Boolean.parseBoolean(System.getProperty("qsim.remove.stuck", "true")));
        // -Dpt.boarding=checkStopOnly: a passenger boards any vehicle that serves the planned alighting stop (matsim-code-examples
        // issue 119); default checkLineAndStop = all earlier runs.
        config.transit().setBoardingAcceptance(org.matsim.pt.config.TransitConfigGroup.BoardingAcceptance.valueOf(
                System.getProperty("pt.boarding", "checkLineAndStop")));

        // --- routing: car AND ride on the network; walk/bike teleported; pt via transit router ---
        // ride (car-passenger) is ROUTED ON THE CAR NETWORK so it experiences the SAME congested travel
        // times as car (its travel-time binding -> car's TravelTime, set on the Controler below). It is
        // NOT a qsim mainMode, so it is teleported over its network-route time and adds no extra traffic.
        // Previously ride was teleported at a fixed 43 km/h free-flow speed, which gave it an artificial
        // speed advantage over congested car -> ride became a mode-choice sink AND could not respond to
        // the toll's congestion/diversion in Phase 2. Routing on the network fixes both.
        config.routing().setNetworkModes(trucks ? List.of("car", "ride", "truck", "truckhz") : List.of("car", "ride"));
        config.routing().removeModeRoutingParams("ride");
        config.routing().removeModeRoutingParams("walk");
        config.routing().removeModeRoutingParams("bike");
        addTeleport(config, "walk", 1.3, 1.23);
        addTeleport(config, "bike", 1.3, 3.1);

        // --- scoring: activity types ---
        addAct(config, "home", 12*3600);
        addAct(config, "work", 8*3600);
        addAct(config, "education", 6*3600);
        addAct(config, "shopping", 2*3600);
        addAct(config, "other", 2*3600);
        addAct(config, "escort", (int)(0.25*3600));
        addAct(config, "eat",    (int)(0.75*3600));
        addAct(config, "errand", (int)(0.50*3600));
        addAct(config, "socialrec", (int)(1.5*3600));
        // 2026-10-03: person-specific durations + opening times (Open Berlin v6.4 practice). Activities in the plans are named
        // <type>_<duration in s>, 600-s bins up to 27 h; each bin is scored against its own typical duration. Opening/closing times
        // (Berlin): work 06-21, shopping 08-20; home and other open all day.  -Dact.durationbins=false to switch off.
        if (Boolean.parseBoolean(System.getProperty("act.durationbins", "true"))) {
            for (String t : new String[]{"home", "work", "shopping", "other"}) {
                for (long d = 600; d <= 97200; d += 600) {
                    ScoringConfigGroup.ActivityParams a = new ScoringConfigGroup.ActivityParams(t + "_" + d);
                    a.setTypicalDuration(d);
                    if (t.equals("work")) { a.setOpeningTime(6 * 3600); a.setClosingTime(21 * 3600); }
                    if (t.equals("shopping")) { a.setOpeningTime(Double.parseDouble(System.getProperty("shop.open", "8")) * 3600); a.setClosingTime(Double.parseDouble(System.getProperty("shop.close", "20")) * 3600); }
                    config.scoring().addActivityParams(a);
                }
            }
            System.out.println("[RunBaltimoreToll] duration-binned activity types registered (home/work/shopping/other x 162 bins; work 06-21, shopping 08-20)");
            // Schedule delay for work (Vickrey 1969 / Small 1982 scheduling model, as in the Austin MATSim pricing study):
            // type work_<duration>_<preferred arrival>.  Arriving before the preferred time = waiting before opening (earns nothing:
            // opportunity cost = performing 0.78 utils/h, close to Small's early penalty 0.61 x VTT); arriving after it = late arrival,
            // penalised at lateArrival = -2.4 x VTT (Small 1982) = -2.4 x 0.78 = -1.872 utils/h.  Same utility scale as the MNL-derived model.
            int nw = 0;
            for (long d = 1800; d <= 97200; d += 1800) {
                for (long pa = 0; pa < 86400; pa += 900) {
                    ScoringConfigGroup.ActivityParams a = new ScoringConfigGroup.ActivityParams("work_" + d + "_" + pa);
                    a.setTypicalDuration(d); a.setOpeningTime(pa); a.setLatestStartTime(pa);
                    config.scoring().addActivityParams(a); nw++;
                }
            }
            double lateArrival = Double.parseDouble(System.getProperty("late.arrival", String.valueOf(-2.4 * 0.78)));
            config.scoring().setLateArrival_utils_hr(lateArrival);
            System.out.println("[RunBaltimoreToll] schedule-delay work types registered: " + nw + "; lateArrival=" + lateArrival + " utils/h; early arrival = waiting before the preferred time");
        }

        // --- scoring: mode params ported from the MD MNL model (MODE_SCORER_MAPPING.md Sec. 3) ---
        // Global: car-anchored money utility + performing carries the (normalized-away) car time cost.
        config.scoring().setMarginalUtlOfWaiting_utils_hr(0.0);
        config.scoring().setPerforming_utils_hr(0.78);
        // waiting at a transit stop (-Dpt.waiting, utils/h). Unset = MATSim's default, the pt travel value (-1.02), as in all
        // earlier runs. -2.82 makes the routing cost of waiting (2.82 + 0.78 = 3.60 utils/h) twice that of in-vehicle time.
        if (System.getProperty("pt.waiting") != null)
            config.scoring().setMarginalUtlOfWaitingPt_utils_hr(Double.parseDouble(System.getProperty("pt.waiting")));
        // base (median-person) money utility anchored to Lin, Spissu & Cirillo (2024, TR-A 182):
        // pre-pandemic Express Lanes WTP $26-28/h -> $27/h in early-2020 dollars, expressed in
        // NOMINAL 2023 DOLLARS (CPI 2020->2023 ~ +17.8%) for unit consistency with the 2023 toll
        // rates: $31.8/h -> 0.78/31.8 = 0.0245 utils/$. Sensitivities: $27 (unadjusted), $36 (pandemic).
        config.scoring().setMarginalUtilityOfMoney(0.0245);
        // car: reference. travel-time coef normalized to 0; time cost = -performing. fuel ~$0.075/km.
        addMode(config, "car",  ascCar,   0.00, 0.0,       -0.000075);
        // pt: BUS-based, normalized (-1.80 + 0.78 = -1.02/h). fare $0.50/km.
        addMode(config, "pt",   ascPt,   -1.02, 0.0,       -0.0005);
        // ride: passenger time valued AS CAR TIME (performing channel only), matching DAYMAP's GC where
        // passenger time enters identically to driver time (VOT divides only the money term). The
        // earlier -1.11/h blend (bus-like published tables) made ride's time disutility 2.4x car's,
        // which under full-scale congestion crushed the switchable margin (measured: ride response to
        // ASC ~17x weaker than logit) and would have multiplied any scenario's congestion change into
        // ride share artifacts. (2026-07-13, full-scale calibration finding.)
        addMode(config, "ride", ascRide,  0.00, 0.0,       -0.000075);
        if (trucks) { addMode(config, "truck", 0.0, 0.00, 0.0, -0.000075); addMode(config, "truckhz", 0.0, 0.00, 0.0, -0.000075); }   // trucks: car-like scoring, route choice only
        // walk/bike: the source model penalizes these by tripLength (WALK -1.17/km, BIKE -0.28/km) with
        // NO time term. The original port put that on marginalUtilityOfDistance, but MATSim does not
        // effectively score distance on TELEPORTED legs (observed: avg walk trip ran to ~5.5 km with
        // walk person-hours EXCEEDING car's, and walk share was a growing attractor) -- so with net time
        // = +0.78-0.78 = 0, walk/bike were essentially free and over-chosen regardless of ASC. Fix:
        // convert the per-km penalty into the equivalent per-HOUR time disutility via the teleport speed
        // (walk 1.23 m/s = 4.43 km/h; bike 3.1 m/s = 11.16 km/h), which lands in the reliably-scored time
        // channel and is per-trip-equivalent to a working distance penalty:
        //   walk net -1.17/km * 4.43 km/h = -5.18/h  -> marginalUtilityOfTraveling = -5.18 + 0.78 = -4.40
        //   bike net -0.28/km * 11.16 km/h = -3.13/h -> marginalUtilityOfTraveling = -3.13 + 0.78 = -2.345
        addMode(config, "walk", ascWalk, -4.40,  0.0,  0.0);
        addMode(config, "bike", ascBike, -2.345, 0.0,  0.0);

        // 2026-11-16 -Dscoring=milesday: the travel terms of the DAYMAP commute tour-mode model (estimates of the current models,
        // estimation package 3_abit/mode_choice/mc_common.py), replacing the port of the earlier model above:
        //   generalised cost GC = minutes + 60 x cost / VOT, VOT = 0.5 x household income / 2,080 h (the usdot money utility of this
        //   runner), with every minute weighted alike: car, car passenger, transit door to door (walk access and egress, waits,
        //   in-vehicle, transfers; no transfer penalty) and drive access -> marginalUtilityOfTraveling 0 for every mode (net
        //   -performing), waiting for transit 0, utilityOfLineSwitch 0;
        //   money: car driver 0.1112 $/km (AAA 2017 fuel + maintenance, the estimation's operating cost), car passenger 0 (the
        //   driver pays), transit fares flat per ride (MTA $1.80, Metrobus $2.00) and so without effect on the route -> 0 per km;
        //   mode constants 0 (modes are fixed; a constant would only bias the access mode of transit trips).
        // Walk and bike enter the DAYMAP mode models by distance only, which matters for the choice of mode, not here (modes fixed).
        if ("milesday".equals(System.getProperty("scoring"))) {
            // addModeParams replaces the parameter set of the same mode
            addMode(config, "car",  0.0, 0.0, 0.0, -0.0001112);
            addMode(config, "ride", 0.0, 0.0, 0.0, 0.0);
            addMode(config, "pt",   0.0, 0.0, 0.0, 0.0);
            addMode(config, "walk", 0.0, 0.0, 0.0, 0.0);
            addMode(config, "bike", 0.0, 0.0, 0.0, 0.0);
            if (trucks) { addMode(config, "truck", 0.0, 0.0, 0.0, -0.0001112); addMode(config, "truckhz", 0.0, 0.0, 0.0, -0.0001112); }
            config.scoring().setMarginalUtlOfWaitingPt_utils_hr(0.0);
            // 2026-11-16 -Dpt.lineswitch (utils per transfer, default 0 = no transfer penalty). The SwissRailRaptor of MATSim 2024.0 takes
            // -utilityOfLineSwitch as the transfer cost when transferPenaltyCostPerTravelTimeHour = 0 (RaptorUtils), and costs travel time here
            // at performing = 0.78 utils/h, so -0.13 = 10 in-vehicle minutes (Open Berlin about 9 min; literature 5-20 min).
            config.scoring().setUtilityOfLineSwitch(Double.parseDouble(System.getProperty("pt.lineswitch", "0.0")));
            // a transit trip of DAYMAP stays a transit trip: the router does not replace it by a walk when a transit route exists
            // (DAYMAP's walk mode carries a distance penalty, not the minutes valued here)
            config.transitRouter().setDirectWalkFactor(Double.POSITIVE_INFINITY);
            // 2026-11-16 -Dpt.beeline: longest walk between two stops for a transfer (m; MATSim default 100, Open Berlin and the other VSP scenarios 300)
            if (System.getProperty("pt.beeline") != null)
                config.transitRouter().setMaxBeelineWalkConnectionDistance(Double.parseDouble(System.getProperty("pt.beeline")));
            System.out.println("[RunBaltimoreToll] scoring = milesday: every travel minute at -performing, car 0.1112 $/km, line switch " + config.scoring().getUtilityOfLineSwitch() + ", beeline " + config.transitRouter().getMaxBeelineWalkConnectionDistance() + " m, constants 0");
        }

        // --- replanning: inner-loop mode choice ON (residents may switch) ---
        // Plan-memory cap: with 3 innovation strategies each agent accumulates plans; on the full 280k
        // population this overflowed -Xmx13g (18 GB machine) and hung at ~it.11's mobsim start. Keep it
        // small (override with -Dplan.memory; 3 for the full-pop base, 5 is fine on subsamples).
        int planMemory = Integer.parseInt(System.getProperty("plan.memory", "5"));
        ReplanningConfigGroup strat = config.replanning();
        strat.setMaxAgentPlanMemorySize(planMemory);
        // 0.8 collapses mode shares in the last 20% (selection drains to best plan once SubtourModeChoice
        // stops injecting alternatives); calibrate and run pricing with -Dinnovoff=1.0 so the reported
        // shares are the innovation-on stationary equilibrium and toll-induced mode shifts stay possible.
        strat.setFractionOfIterationsToDisableInnovation(
                Double.parseDouble(System.getProperty("innovoff", "0.8")));

        // HYBRID design: mode choice is done by DAYMAP in the OUTER loop (price-elastic, on tolled skims);
        // MATSim's INNER loop only does route + departure-time (modes FIXED from the input plans). So
        // SubtourModeChoice is OFF by default. Set -Dmodechoice=true to re-enable the inner-loop mode
        // choice (legacy scorer-calibration path).
        boolean innerModeChoice = Boolean.parseBoolean(System.getProperty("modechoice", "false"));
        // Replanning search settings, overridable at launch (-Dreroute.weight, -Dtam.weight, -Dtam.range [s],
        // -Dtam.affectduration). Defaults = the values used for the paper base (MATSim convention; see
        // I695_pricing/00_research/replanning_settings_research.md for the evidence review of 2026-09-30).
        double rerouteW = Double.parseDouble(System.getProperty("reroute.weight", "0.15"));
        double tamW = Double.parseDouble(System.getProperty("tam.weight", "0.10"));
        double tamRange = Double.parseDouble(System.getProperty("tam.range", "1800"));
        boolean tamAffectDur = Boolean.parseBoolean(System.getProperty("tam.affectduration", "false"));
        if (innerModeChoice) {
            // SMC's uniform random injection puts a standing churn floor under every mode
            // (~weight-proportional); pt/bike targets sit below the floor at 0.15, so the
            // calibrated runs use -Dsmc.weight=0.04 (slack goes to ChangeExpBeta selection).
            double smcWeight = Double.parseDouble(System.getProperty("smc.weight", "0.15"));
            addStrategy(config, "SubtourModeChoice", smcWeight);
            addStrategy(config, "ReRoute", rerouteW);
            addStrategy(config, "TimeAllocationMutator", tamW);
            addStrategy(config, "ChangeExpBeta", 1.0 - rerouteW - tamW - smcWeight);
            config.subtourModeChoice().setModes(new String[]{"car","pt","ride","walk","bike"});
            config.subtourModeChoice().setChainBasedModes(new String[]{});
            config.subtourModeChoice().setConsiderCarAvailability(true);
            config.subtourModeChoice().setBehavior(
                    org.matsim.core.replanning.modules.SubtourModeChoice.Behavior.betweenAllAndFewerConstraints);
        } else {
            // fixed modes: route + departure-time inner loop only (weights sum to 1.0 without SMC)
            addStrategy(config, "ReRoute", rerouteW);
            addStrategy(config, "TimeAllocationMutator", tamW);
            addStrategy(config, "ChangeExpBeta", 1.0 - rerouteW - tamW);
        }
        if (trucks) {   // external, commercial and truck agents: route choice only (no mode or departure-time change)
            addStrategy(config, "ReRoute", rerouteW, "background");
            addStrategy(config, "ChangeExpBeta", 1.0 - rerouteW, "background");
        }
        config.timeAllocationMutator().setMutationRange(tamRange);
        config.timeAllocationMutator().setAffectingDuration(tamAffectDur);
        // 2026-10-03: mutate around the INITIAL end times (Open Berlin v6.4) so departure times cannot random-walk away over iterations
        boolean tamAroundInitial = Boolean.parseBoolean(System.getProperty("tam.aroundinitial", "true"));
        config.timeAllocationMutator().setMutateAroundInitialEndTimeOnly(tamAroundInitial);
        System.out.println("[RunBaltimoreToll] replanning: ReRoute=" + rerouteW + " TimeAllocationMutator=" + tamW
                + " (range=" + tamRange + " s, affectingDuration=" + tamAffectDur + ", aroundInitialEndTime=" + config.timeAllocationMutator().isMutateAroundInitialEndTimeOnly() + ") SubtourModeChoice="
                + (innerModeChoice ? System.getProperty("smc.weight", "0.15") : "off") + " ChangeExpBeta=rest");

        // --- optional road pricing (Phase-1 base runs with tollFile = NONE) ---
        boolean toll = tollFile != null && !tollFile.isEmpty() && !tollFile.equalsIgnoreCase("NONE");
        if (toll) {
            RoadPricingConfigGroup rp = ConfigUtils.addOrGetModule(config, RoadPricingConfigGroup.class);
            rp.setTollLinksFile(tollFile);
        }

        Scenario scenario = ScenarioUtils.loadScenario(config);

        // ride is now routed on the network, but the links are annotated only with mode "car", so the
        // "ride" sub-network would be empty (nof_nodes=0) and routing would fail. Allow "ride" on every
        // car link so ride shares the car network (and thus its congested travel times).
        int rideLinks = 0;
        for (org.matsim.api.core.v01.network.Link link : scenario.getNetwork().getLinks().values()) {
            Set<String> modes = link.getAllowedModes();
            if (modes.contains("car") && !modes.contains("ride")) {
                Set<String> nm = new java.util.HashSet<>(modes);
                nm.add("ride");
                link.setAllowedModes(nm);
                rideLinks++;
            }
        }
        System.out.println("[RunBaltimoreToll] added mode 'ride' to " + rideLinks + " car links");
        if (trucks) {
            int tl = 0;
            for (org.matsim.api.core.v01.network.Link link : scenario.getNetwork().getLinks().values()) {
                Set<String> modes = link.getAllowedModes();
                if (modes.contains("car") && !modes.contains("truck") && !link.getId().toString().startsWith("hot_")) {   // trucks barred from the HOT/peak lane
                    Set<String> nm = new java.util.HashSet<>(modes); nm.add("truck"); link.setAllowedModes(nm); tl++;
                }
            }
            java.util.Set<String> banned = new java.util.HashSet<>();
            String bf = System.getProperty("hazmat.banned.links", "");
            if (!bf.isEmpty()) { try { for (String l : java.nio.file.Files.readAllLines(java.nio.file.Paths.get(bf))) if (!l.isBlank()) banned.add(l.trim()); } catch (java.io.IOException e) { throw new RuntimeException(e); } }
            int hl = 0;
            for (org.matsim.api.core.v01.network.Link link : scenario.getNetwork().getLinks().values()) {
                String id = link.getId().toString(); Set<String> modes = link.getAllowedModes();
                if (modes.contains("car") && !id.startsWith("hot_") && !banned.contains(id)) { Set<String> nm = new java.util.HashSet<>(modes); nm.add("truckhz"); link.setAllowedModes(nm); hl++; }
            }
            System.out.println("[RunBaltimoreToll] hazmat trucks ('truckhz') on " + hl + " links; banned from " + banned.size() + " tunnel links");
            org.matsim.vehicles.Vehicles vs = scenario.getVehicles();
            for (String m : new String[]{"car", "ride", "truck", "truckhz"}) {
                org.matsim.api.core.v01.Id<org.matsim.vehicles.VehicleType> tid = org.matsim.api.core.v01.Id.create(m, org.matsim.vehicles.VehicleType.class);
                if (vs.getVehicleTypes().containsKey(tid)) continue;
                org.matsim.vehicles.VehicleType vt = org.matsim.vehicles.VehicleUtils.createVehicleType(tid);
                boolean tk = m.startsWith("truck"); vt.setPcuEquivalents(tk ? truckPcu : 1.0);
                vt.setMaximumVelocity(tk ? 29.1 : 50.0);     // trucks capped at 65 mph
                vt.setLength(tk ? 15.0 : 7.5);
                vt.setNetworkMode(m);
                vs.addVehicleType(vt);
            }
            System.out.println("[RunBaltimoreToll] trucks ON: mode 'truck' on " + tl + " links (not hot_), pcu=" + truckPcu + "; 'background' agents route-only");
        }

        // Set MATSim carAvail ("always"/"never") for SubtourModeChoice's considerCarAvailability.
        // PRIMARY: seed from DAYMAP's assigned mode -- any agent whose DAYMAP plan has a "car" (CAR_DRIVER)
        // leg demonstrably HAD a car for that trip, so carAvail=always. This guarantees MATSim can
        // reproduce DAYMAP's ~77% car-driver share and removes an artificial ceiling (the household
        // autos+license attributes marked ~4.7% of DAYMAP car-drivers as carless, e.g. autos=0 rounding or
        // a licensed 2nd driver in a 0-car record). FALLBACK for agents with no car leg: autos>0 & license.
        int carless = 0, seededByMode = 0;
        for (Person p : scenario.getPopulation().getPersons().values()) {
            boolean hadCarLeg = false;
            if (p.getSelectedPlan() != null) {
                for (org.matsim.api.core.v01.population.PlanElement pe : p.getSelectedPlan().getPlanElements()) {
                    if (pe instanceof org.matsim.api.core.v01.population.Leg
                            && "car".equals(((org.matsim.api.core.v01.population.Leg) pe).getMode())) {
                        hadCarLeg = true; break;
                    }
                }
            }
            Object autosAttr   = p.getAttributes().getAttribute("autos");
            Object licenseAttr = p.getAttributes().getAttribute("driversLicense");
            int autos = (autosAttr instanceof Number) ? ((Number) autosAttr).intValue()
                        : (autosAttr != null ? parseIntSafe(autosAttr.toString()) : 1);
            boolean licensed = licenseAttr == null || Boolean.parseBoolean(licenseAttr.toString());
            boolean carAvail = hadCarLeg || (autos > 0 && licensed);
            if (carAvail && !(autos > 0 && licensed)) seededByMode++;   // recovered by the DAYMAP-mode seed
            PersonUtils.setCarAvail(p, carAvail ? "always" : "never");
            if (autos > 0 && licensed) p.getAttributes().putAttribute("ptCarAccess", "true");   // intermodal car access filter
            if (!carAvail) carless++;
        }
        int nPop = scenario.getPopulation().getPersons().size();
        System.out.println("[RunBaltimoreToll] carAvail=never for " + carless + " / " + nPop
                + " residents (" + String.format("%.1f", 100.0 * (nPop - carless) / nPop)
                + "% always; " + seededByMode + " recovered by DAYMAP-mode seed)");
        System.out.println("[RunBaltimoreToll] ASCs  car=" + ascCar + " pt=" + ascPt + " ride=" + ascRide
                + " walk=" + ascWalk + " bike=" + ascBike + "  toll=" + (toll ? tollFile : "NONE"));

        // walk/bike max-distance cutoff for SubtourModeChoice (curing the non-motorized floor): walk
        // dropped from the choice set when the agent's longest trip > walk.maxdist, bike > bike.maxdist.
        final double walkMaxDist = Double.parseDouble(System.getProperty("walk.maxdist", "2000"));
        final double bikeMaxDist = Double.parseDouble(System.getProperty("bike.maxdist", "5000"));
        final String[] scModes = {"car", "pt", "ride", "walk", "bike"};
        System.out.println("[RunBaltimoreToll] walk.maxdist=" + walkMaxDist + "m  bike.maxdist=" + bikeMaxDist + "m");

        // --- INCOME-DEPENDENT MONEY UTILITY (equity response; 2026-07-12) ---
        // POWER FORM (2026-10-01, = the paper's Eq. votscale and DAYMAP's MarylandFullModeChoice):
        //   VOT_n = VOT_ref * clamp((hhIncome_n / refIncome)^elasticity, 0.4, 2.5)
        //   marginalUtilityOfMoney(person) = base / that factor
        // elasticity 0.6 (-Dincome.vot.elasticity; 0 = uniform), refIncome = -Dincome.vot.median if given
        // (DAYMAP uses $84,216/yr = 7018/month), else the population median. -Dincome.vot.form=linear
        // restores the earlier Bas Vicente & Cirillo linear-lambda form (kept for sensitivity only: it turns
        // negative above ~$210k and pinned 23% of residents on the clamp).
        final double votElast = Double.parseDouble(System.getProperty("income.vot.elasticity", "0.6"));
        final String votForm = System.getProperty("income.vot.form", "power");
        final double votMedianOverride = Double.parseDouble(System.getProperty("income.vot.median", "0"));
        // USDOT FORM (2026-11-02, -Dincome.vot.form=usdot; validation study): the value of time of DAYMAP's tour mode choice
        // (MarylandTourNestedModeChoice): VOT_n [$/h] = s x max(hhIncome_n, floor) / H, s = -Dvot.share (0.5, USDOT 2016 guidance for
        // local personal travel: 50 % of the hourly household income), H = -Dvot.hours (2,080 h/yr), floor = -Dvot.income.floor ($5,000/yr);
        // hhIncome = the person attribute 'hhIncome' (annual household income = 12 x sum over members of int(annual SILO income)/12, as
        // DAYMAP reads it; a missing attribute counts as 0 -> floor).  Car time costs the performing rate (car travel utility 0), so the
        // person's marginal utility of money = performing [utils/h] / VOT_n [$/h]; elasticity, median and the [0.4, 2.5] clamp are not used.
        final boolean usdot = "usdot".equals(votForm);
        final double votShare = Double.parseDouble(System.getProperty("vot.share", "0.5"));
        final double votHours = Double.parseDouble(System.getProperty("vot.hours", "2080"));
        final double votFloor = Double.parseDouble(System.getProperty("vot.income.floor", "5000"));
        java.util.List<Double> incs = new java.util.ArrayList<>();
        for (org.matsim.api.core.v01.population.Person p : scenario.getPopulation().getPersons().values()) {
            Object a = p.getAttributes().getAttribute("hhIncome");
            if (a instanceof Number) incs.add(((Number) a).doubleValue());
        }
        java.util.Collections.sort(incs);
        final double popMedianInc = incs.isEmpty() ? 75000.0 : incs.get(incs.size() / 2);
        final double medianInc = votMedianOverride > 0 ? votMedianOverride : popMedianInc;
        int nLo = 0, nHi = 0;
        for (double v : incs) { double f = IncomeScoringParams.votFactor(v, medianInc, votElast);
            if (f <= IncomeScoringParams.FACTOR_MIN) nLo++; else if (f >= IncomeScoringParams.FACTOR_MAX) nHi++; }
        if (usdot) {
            int nMiss = scenario.getPopulation().getPersons().size() - incs.size(), nFloor = 0; double[] v = new double[incs.size()]; int i = 0;
            for (double inc : incs) { if (inc < votFloor) nFloor++; v[i++] = votShare * Math.max(inc, votFloor) / votHours; }
            java.util.Arrays.sort(v); double perf = config.scoring().getPerforming_utils_hr();
            // the router (toll and fuel cost in the travel disutility) uses the GLOBAL marginal utility of money (with MATSim's log-normal
            // toll-routing randomness), not the per-person one: set it to the USDOT VOT of the population-median household income, so routing
            // is centred on the USDOT rule instead of the earlier $31.8/h anchor; scoring stays per person (the factor is relative to this base).
            double votMedian = v.length > 0 ? v[v.length / 2] : votShare * Math.max(popMedianInc, votFloor) / votHours;
            config.scoring().setMarginalUtilityOfMoney(perf / votMedian);
            System.out.println("[RunBaltimoreToll] usdot: global (routing) marginalUtilityOfMoney = " + perf + " / " + votMedian + " = " + (perf / votMedian));
            System.out.println("[RunBaltimoreToll] VOT form=usdot: VOT = " + votShare + " x max(hhIncome, " + votFloor + ") / " + votHours
                    + " $/h; marginalUtilityOfMoney = " + perf + " / VOT; persons with hhIncome " + incs.size() + ", missing " + nMiss + " (-> floor), below floor " + nFloor
                    + (v.length > 0 ? String.format("; VOT $/h p5 %.2f p25 %.2f median %.2f mean %.2f p75 %.2f p95 %.2f", v[(int) (0.05 * v.length)], v[(int) (0.25 * v.length)],
                    v[v.length / 2], java.util.Arrays.stream(v).average().orElse(0), v[(int) (0.75 * v.length)], v[(int) (0.95 * v.length)]) : ""));
        } else
        System.out.println("[RunBaltimoreToll] income-VOT form=" + votForm + " elasticity=" + votElast
                + "  reference hhIncome=" + medianInc + " (population median " + popMedianInc + ", n=" + incs.size() + ")"
                + (votForm.equals("power") ? "  at VOT-factor floor 0.4: " + nLo + "  at cap 2.5: " + nHi : ""));

        Controler controler = new Controler(scenario);
        // ride rides at CAR's congested travel time: bind ride's routing TravelTime to the car network
        // TravelTime (the congestion-aware TravelTimeCalculator output) and reuse car's disutility factory.
        // Also install the distance-constrained PermissibleModesCalculator for SubtourModeChoice.
        final Config cfgF = config;
        controler.addOverridingModule(new AbstractModule() {
            @Override public void install() {
                addTravelTimeBinding(TransportMode.ride).to(networkTravelTime());
                addTravelDisutilityFactoryBinding(TransportMode.ride).to(carTravelDisutilityFactoryKey());
                bind(org.matsim.core.population.algorithms.PermissibleModesCalculator.class)
                        .toInstance(new DistanceConstrainedPermissibleModes(scModes, walkMaxDist, bikeMaxDist));
                // park-and-ride tour rule for the intermodal car access (-Dpt.car.access): car access from home, car egress to home only
                if (Boolean.getBoolean("pt.car.access")) {
                    bind(ch.sbb.matsim.routing.pt.raptor.RaptorIntermodalAccessEgress.class).toInstance(new HomeCarAccessEgress());
                    // car access only for rail, metro and light rail (DAYMAP's train alternative)
                    addRoutingModuleBinding(TransportMode.pt).toProvider(RailOnlyCarAccessRouting.RoutingProvider.class);
                }
                // 2026-11-17 -Dpt.submodes=true: DAYMAP's sub-mode kept (population converter --pt-submodes): leg mode bus routed on the
                // bus routes only with walk access (BusOnlyRouting), leg mode train on the full schedule with car access to rail only, again on the rail routes when that rides no rail (TrainRouting)
                // (RailOnlyCarAccessRouting); both produce pt and walk legs, simulated and scored as pt
                if (Boolean.getBoolean("pt.submodes")) {
                    addRoutingModuleBinding("bus").toProvider(BusOnlyRouting.RoutingProvider.class);
                    addRoutingModuleBinding("train").toProvider(TrainRouting.RoutingProvider.class);
                }
                if (usdot) {
                    bind(org.matsim.core.scoring.functions.ScoringParametersForPerson.class)
                            .toInstance(new IncomeScoringParams(cfgF, votShare, votHours, votFloor));
                } else if (votElast > 0) {
                    bind(org.matsim.core.scoring.functions.ScoringParametersForPerson.class)
                            .toInstance(new IncomeScoringParams(cfgF, medianInc, votElast, votForm));
                }
            }
        });
        if (toll) {
            double discFactor = Double.parseDouble(System.getProperty("toll.discount.factor", "1.0"));
            double discThresh = Double.parseDouble(System.getProperty("toll.discount.threshold", "0"));
            final double tSU = Double.parseDouble(System.getProperty("truck.toll.su", "1.0")), tCU = Double.parseDouble(System.getProperty("truck.toll.cu", "1.0"));
            if ((discFactor < 1.0 && discThresh > 0) || tSU != 1.0 || tCU != 1.0) {
                // S6: person-specific discount via the contrib's TollFactor (charged AND routed consistently)
                final double df = discFactor, th = discThresh;
                org.matsim.contrib.roadpricing.TollFactor tf = (personId, vehicleId, linkId, time) -> {
                    org.matsim.api.core.v01.population.Person p =
                            scenario.getPopulation().getPersons().get(personId);
                    String pid = personId.toString();
                    if (pid.startsWith("su_")) return tSU;                                   // single-unit: MDTA 3-axle / 2-axle toll
                    if (pid.startsWith("cu_") || pid.startsWith("xl_") || pid.startsWith("xt_")) return tCU;   // combination: 5-axle / 2-axle
                    if (!(discFactor < 1.0 && discThresh > 0)) return 1.0;
                    if (p == null) return 1.0;
                    Object a = p.getAttributes().getAttribute("hhIncome");
                    double inc = Double.MAX_VALUE;
                    if (a instanceof Number) inc = ((Number) a).doubleValue();
                    else if (a != null) { try { inc = Double.parseDouble(a.toString()); } catch (Exception ignored) {} }
                    return inc < th ? df : 1.0;
                };
                org.matsim.contrib.roadpricing.RoadPricingScheme schemeWithFactor =
                        org.matsim.contrib.roadpricing.RoadPricingSchemeUsingTollFactor
                                .createAndRegisterRoadPricingSchemeUsingTollFactor(
                                        org.matsim.core.utils.io.IOUtils.resolveFileOrResource(tollFile),
                                        tf, scenario);
                System.out.println("[RunBaltimoreToll] toll discount ACTIVE: factor=" + df + " for hhIncome < " + th);
                controler.addOverridingModule(new RoadPricingModule(schemeWithFactor));
            } else {
                controler.addOverridingModule(new RoadPricingModule());
            }
        }
        controler.run();
    }

    private static int parseIntSafe(String s) {
        try { return (int) Double.parseDouble(s.trim()); } catch (Exception e) { return 1; }
    }

    /** Person-specific money utility. DEFAULT since 2026-10-01 = power form (see main): VOT scales with
     *  (hhIncome/reference)^0.6, clamped to [0.4, 2.5], identical to DAYMAP and the paper. The base (median)
     *  money utility 0.0245 utils/$ = $31.8/h is anchored to Lin, Spissu & Cirillo (2024, TR-A 182), a
     *  revealed-preference study of two Express Lanes in VIRGINIA ($26-28/h before the pandemic, no income data).
     *  LEGACY linear form (income.vot.form=linear), kept for sensitivity:
     *  Bas Vicente & Cirillo (2017, NTC2015-SU-R-09), Jara-Diaz &
     *  Videla (1989) form: V = b1(I-c) + b2(I-c)^2 + ... with I = income PER TRIP
     *  (= hhIncome / (2.88 trips/day x 260 working days), the report's transformation).
     *  Marginal utility of money: lambda(I) = b1 + 2*b2*I, MXL estimates b1=0.525, b2=-0.001
     *  (Fig.1, preferred mixed-logit model, Maryland Capital Beltway SP, n=766).
     *  MATSim's marginalUtilityOfMoney(person) = base * lambda(I_p)/lambda(I_median), so the median
     *  person keeps the base VOT anchor (set from Lin, Spissu & Cirillo 2024, TR-A 182: pre-pandemic
     *  Express Lanes WTP $26-28/h -> $27/h). The quadratic turns negative above the SP sample range
     *  (~$196k/yr hh income), so the RELATIVE factor is clamped (documented tail regularization). */
    static class IncomeScoringParams implements org.matsim.core.scoring.functions.ScoringParametersForPerson {
        static final double B1 = 0.525, TWO_B2 = -0.002;            // MXL (I-C) and 2x(I-C)^2 coefs
        static final double TRIPS_PER_YEAR = 2.88 * 260.0;          // income-per-trip transformation
        // SILO incomes are maintained in 2016 dollars; the coefficients are scaled to the survey's
        // 2011 dollars -> deflate incomes before evaluating lambda (CPI 2011->2016 ~ +6.7%).
        static final double INCOME_2016_TO_2011 = 1.0 / 1.067;
        static final double FACTOR_MIN = 0.4, FACTOR_MAX = 2.5;     // tail clamp = DAYMAP precedent (VOT_FACTOR_MIN/MAX in MarylandFullModeChoice); 0.25 variant = sensitivity run
        private final Config config;
        private final double medianIncome, elasticity; private final String form;
        private double votShare, votHours, votFloor;   // usdot form only
        /** usdot form: VOT [$/h] = share x max(hhIncome, floor) / hours; money factor = (performing / VOT) / base marginal utility of money. */
        IncomeScoringParams(Config config, double votShare, double votHours, double votFloor) {
            this(config, 0.0, 0.0, "usdot"); this.votShare = votShare; this.votHours = votHours; this.votFloor = votFloor;
        }
        double usdotFactor(double income) {
            double vot = votShare * Math.max(income, votFloor) / votHours;
            return config.scoring().getPerforming_utils_hr() / vot / config.scoring().getMarginalUtilityOfMoney();
        }
        /** VOT multiplier of the power form: clamp((income/reference)^elasticity, 0.4, 2.5). */
        static double votFactor(double income, double reference, double elasticity) {
            double f = Math.pow(Math.max(1.0, income) / reference, elasticity);
            return Math.max(FACTOR_MIN, Math.min(FACTOR_MAX, f));
        }
        /** Multiplier applied to the base marginal utility of money for one income. */
        static double moneyFactor(double income, double reference, double elasticity, String form) {
            if ("linear".equals(form)) { double f = lambda(income) / lambda(reference); return Math.max(FACTOR_MIN, Math.min(FACTOR_MAX, f)); }
            return 1.0 / votFactor(income, reference, elasticity);
        }
        private final java.util.Map<Long, org.matsim.core.scoring.functions.ScoringParameters> cache = new java.util.concurrent.ConcurrentHashMap<>();
        /** cache key = money factor rounded to 0.005: persons with (nearly) the same factor share one ScoringParameters object */
        private long personKey(org.matsim.api.core.v01.population.Person person) {
            double inc = medianIncome; Object a = person.getAttributes().getAttribute("hhIncome");
            if (a instanceof Number) inc = ((Number) a).doubleValue();
            else if (a != null) { try { inc = Double.parseDouble(a.toString()); } catch (Exception ignored) {} }
            if ("usdot".equals(form)) return Math.round(Math.log(usdotFactor(inc)) * 1000.0);   // key = factor on a 0.1 % log grid (range ~0.1-30)
            return Math.round(moneyFactor(inc, medianIncome, elasticity, form) / 0.005);
        }
        IncomeScoringParams(Config config, double medianIncome, double elasticity, String form) {
            this.config = config; this.medianIncome = medianIncome; this.elasticity = elasticity; this.form = form;
        }
        private static double lambda(double annualIncome) {
            double perTrip = annualIncome * INCOME_2016_TO_2011 / TRIPS_PER_YEAR;
            return B1 + TWO_B2 * perTrip;
        }
        @Override
        public org.matsim.core.scoring.functions.ScoringParameters getScoringParameters(
                org.matsim.api.core.v01.population.Person person) {
            return cache.computeIfAbsent(personKey(person), id -> {
                double inc = medianIncome;
                Object a = person.getAttributes().getAttribute("hhIncome");
                if (a instanceof Number) inc = ((Number) a).doubleValue();
                else if (a != null) { try { inc = Double.parseDouble(a.toString()); } catch (Exception ignored) {} }
                double factor = "usdot".equals(form) ? Math.exp(id / 1000.0) : id * 0.005;   // the rounded factor (key); the 0.5 % (usdot: 0.1 % relative) rounding is far below any behavioural effect
                org.matsim.core.scoring.functions.ScoringParameters.Builder b =
                        new org.matsim.core.scoring.functions.ScoringParameters.Builder(
                                config.scoring(), config.scoring().getScoringParameters(null), config.scenario());
                b.setMarginalUtilityOfMoney(config.scoring().getMarginalUtilityOfMoney() * factor);
                return b.build();
            });
        }
    }

    private static void addAct(Config c, String type, double dur) {
        ScoringConfigGroup.ActivityParams a = new ScoringConfigGroup.ActivityParams(type);
        a.setTypicalDuration(dur);
        c.scoring().addActivityParams(a);
    }
    private static void addMode(Config c, String mode, double constant, double travelUtilPerHr,
                                double distUtilPerM, double monetaryDistRate) {
        ScoringConfigGroup.ModeParams mp = new ScoringConfigGroup.ModeParams(mode);
        mp.setConstant(constant);
        mp.setMarginalUtilityOfTraveling(travelUtilPerHr);
        mp.setMarginalUtilityOfDistance(distUtilPerM);
        mp.setMonetaryDistanceRate(monetaryDistRate);
        c.scoring().addModeParams(mp);
    }
    private static void addTeleport(Config c, String mode, double beeline, double speed) {
        RoutingConfigGroup.TeleportedModeParams t = new RoutingConfigGroup.TeleportedModeParams(mode);
        t.setBeelineDistanceFactor(beeline);
        t.setTeleportedModeSpeed(speed);
        c.routing().addTeleportedModeParams(t);
    }
    private static void addStrategy(Config c, String name, double weight, String subpop) {
        ReplanningConfigGroup.StrategySettings ss = new ReplanningConfigGroup.StrategySettings();
        ss.setStrategyName(name); ss.setWeight(weight); ss.setSubpopulation(subpop);
        c.replanning().addStrategySettings(ss);
    }
    private static void addStrategy(Config c, String name, double weight) {
        ReplanningConfigGroup.StrategySettings ss = new ReplanningConfigGroup.StrategySettings();
        ss.setStrategyName(name);
        ss.setWeight(weight);
        c.replanning().addStrategySettings(ss);
    }
}
