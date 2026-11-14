package abm.data.plans;


import de.tum.bgu.msm.data.Id;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.Set;

public enum Purpose implements Id {


    HOME,
    WORK,
    EDUCATION,
    ACCOMPANY,
    SHOPPING,
    OTHER,
    RECREATION,
    SUBTOUR;

    public static Set<Purpose> getMandatoryPurposes(){
        Set<Purpose> purposes = new LinkedHashSet<>();
        purposes.add(WORK);
        purposes.add(EDUCATION);
        return purposes;
    }

    public static Set<Purpose> getDiscretionaryPurposes(){
        Set<Purpose> purposes = new LinkedHashSet<>();
        // fixed order (LinkedHashSet): the discretionary purposes are placed on weekdays in this order, so a hash order that
        // varies between JVM runs would change the results; the order is the one the calibration ran with
        purposes.add(ACCOMPANY);
        purposes.add(OTHER);
        purposes.add(RECREATION);
        purposes.add(SHOPPING);
        return purposes;
    }

    public static Set<Purpose> getAllPurposes(){
        Set<Purpose> purposes = new LinkedHashSet<>();
        purposes.add(WORK);
        purposes.add(EDUCATION);
        // fixed order (LinkedHashSet): the discretionary purposes are placed on weekdays in this order, so a hash order that
        // varies between JVM runs would change the results; the order is the one the calibration ran with
        purposes.add(ACCOMPANY);
        purposes.add(OTHER);
        purposes.add(RECREATION);
        purposes.add(SHOPPING);
        return purposes;
    }

    public static ArrayList<Purpose> getSortedPurposes(){
        ArrayList<Purpose> purposes = new ArrayList<>();
        purposes.add(WORK);
        purposes.add(EDUCATION);
        purposes.add(ACCOMPANY);
        purposes.add(OTHER);
        purposes.add(SHOPPING);
        purposes.add(RECREATION);
        return purposes;
    }


    @Override
    public int getId() {
        return this.ordinal();
    }
}
