package abm.models.maryland;

import abm.data.plans.Activity;
import abm.data.plans.Purpose;
import abm.data.plans.Tour;
import abm.models.activityGeneration.time.DayOfWeekDiscretionaryAssignment;
import abm.properties.AbitResources;
import abm.utils.AbitUtils;

import java.time.DayOfWeek;

/**
 * Maryland discretionary day-of-week assignment.  The chain extracts ONE representative weekday per person for MATSim
 * (pipeline/abit_to_matsim_pop.py, ABIT/validation/abit_day.pick_day): since the second pass of stage 3 (2026-10-22) this
 * is MONDAY for every person, and a person without legs on Monday is a non-traveller on the representative day.  The
 * weekly model therefore has to reproduce the survey's Monday: the discretionary activities of a person are placed on
 * the five weekdays with the weights
 *
 *     w(Mon) = disc.monday.weight (M; the old property abit.disc.pmon = 0.5 corresponds to M = 4, the default),
 *     w(Tue..Fri) = 1,
 *     x disc.freeday.weight (K, default 1) for a weekday on which the person has NO mandatory tour (a worker's
 *       telework / absence day, a student's day without school).
 *
 * K reproduces the survey's day-level dependence between mandatory and discretionary travel (estimation half: travelling
 * workers without a work tour make 1.17 discretionary tours against 0.27 for those with one; students 1.14 against 0.24
 * on days without / with a school tour) and is the lever by which the Monday traveller share and the school-tour rate per
 * travelling student are met with the weekly school-day probability kept at the survey value.  M is collinear with the
 * weekly frequency factors for persons without mandatory tours and is kept at its default.  Both are read from the
 * properties (run_params.csv of the coefficient set); the old system property abit.disc.pmon is no longer used.
 *
 * The mandatory tours of the person are in the plan when this is called (PlanGenerator: mandatory tours first, then the
 * primary discretionary activities one by one), so the free weekdays are known.
 */
public class MarylandDayOfWeekDiscretionaryAssignment implements DayOfWeekDiscretionaryAssignment {

    private static final double M = AbitResources.instance.getDouble("disc.monday.weight", 4.0);
    private static final double K = AbitResources.instance.getDouble("disc.freeday.weight", 1.0);
    // same-day penalty C (disc.sameday.penalty, default 0): the weight of a weekday is divided by (1 + C n_d), n_d = the
    // person's discretionary tours already placed on that day.  With C = 0 the weekly Poisson count is thinned
    // independently onto the days, so the Monday count is Poisson and the share of persons without a tour on Monday is
    // fixed by the tours per traveller (e^-lambda); C > 0 spreads a person's activities over distinct days, which keeps
    // the probability of at least one Monday tour and lowers the multi-tour mass, so for a given tours-per-traveller
    // rate more persons travel.  It is the lever of the traveller share of persons without mandatory tours (second
    // pass, 2026-10-22), calibrated to the survey share of household members other than workers and students.
    private static final double C = AbitResources.instance.getDouble("disc.sameday.penalty", 0.0);
    private static final DayOfWeek[] WEEKDAYS = {DayOfWeek.MONDAY, DayOfWeek.TUESDAY, DayOfWeek.WEDNESDAY, DayOfWeek.THURSDAY, DayOfWeek.FRIDAY};

    @Override
    public void assignDayOfWeek(Activity activity) {
        boolean[] mandatory = new boolean[7]; int[] nDisc = new int[7];
        if (activity.getPerson() != null && activity.getPerson().getPlan() != null) {
            for (Tour t : activity.getPerson().getPlan().getTours().values()) {
                Activity main = t.getMainActivity();
                if (main == null || main.getDayOfWeek() == null) continue;
                if (Purpose.getMandatoryPurposes().contains(main.getPurpose())) mandatory[main.getDayOfWeek().getValue() - 1] = true;
                else nDisc[main.getDayOfWeek().getValue() - 1]++;
            }
        }
        double[] w = new double[WEEKDAYS.length]; double sum = 0;
        for (int i = 0; i < WEEKDAYS.length; i++) {
            int d = WEEKDAYS[i].getValue() - 1;
            w[i] = (i == 0 ? M : 1.0) * (mandatory[d] ? 1.0 : K) / (1.0 + C * nDisc[d]);
            sum += w[i];
        }
        double u = AbitUtils.getRandomObject().nextDouble() * sum;
        for (int i = 0; i < WEEKDAYS.length; i++) {
            u -= w[i];
            if (u < 0) { activity.setDayOfWeek(WEEKDAYS[i]); return; }
        }
        activity.setDayOfWeek(DayOfWeek.FRIDAY);
    }
}
