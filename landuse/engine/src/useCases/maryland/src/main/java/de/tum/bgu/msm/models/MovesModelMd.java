package de.tum.bgu.msm.models;

import de.tum.bgu.msm.container.DataContainer;
import de.tum.bgu.msm.data.dwelling.Dwelling;
import de.tum.bgu.msm.data.household.Household;
import de.tum.bgu.msm.data.person.Occupation;
import de.tum.bgu.msm.data.person.Person;
import de.tum.bgu.msm.data.school.SchoolDataMd;
import de.tum.bgu.msm.models.relocation.moves.HousingStrategy;
import de.tum.bgu.msm.models.relocation.moves.MovesModelImpl;
import de.tum.bgu.msm.models.relocation.moves.MovesStrategy;
import de.tum.bgu.msm.properties.Properties;
import de.tum.bgu.msm.schools.DataContainerWithSchools;
import de.tum.bgu.msm.schools.PersonWithSchool;

import java.util.Random;

/**
 * Moves model of the Maryland study (Baltimore 2026, stage 2b): after every household move that changes the home
 * zone, the students of the household get the school nearest to the new home (SchoolDataMd), keeping their school
 * type. moveHousehold is the one place through which all relocations pass: regular moves, in-migration
 * (InOutMigrationImpl.inmigrateHh), divorce, leaving the parental household and marriage, so the school follows the
 * household in every case. Students who move within their zone keep their school.
 */
public class MovesModelMd extends MovesModelImpl {

    private final SchoolDataMd schoolData;
    private final HousingStrategy housingStrategyMd;   // Baltimore 2026 (2026-11-18): for the two-level residential location model

    public MovesModelMd(DataContainer dataContainer, Properties properties, MovesStrategy movesStrategy,
                        HousingStrategy housingStrategy, Random random) {
        super(dataContainer, properties, movesStrategy, housingStrategy, random);
        this.schoolData = (SchoolDataMd) ((DataContainerWithSchools) dataContainer).getSchoolData();
        this.housingStrategyMd = housingStrategy;
    }

    /** Baltimore 2026 (2026-11-18): the two-level model when resloc.twolevel is on (set up in HousingStrategyMstm.setup), else null */
    private de.tum.bgu.msm.models.resloc.ReslocTwoLevel twoLevel() {
        return housingStrategyMd instanceof HousingStrategyMstm ? ((HousingStrategyMstm) housingStrategyMd).getTwoLevel() : null;
    }

    /** Baltimore 2026 (2026-11-19a): end-of-year check of the two-level model's live vacancy counter against the vacancy lists */
    @Override
    public void endYear(int year) {
        super.endYear(year);
        final de.tum.bgu.msm.models.resloc.ReslocTwoLevel m = twoLevel();
        if (m != null) m.checkVacancies("end of the moves of " + year);
    }

    /** Baltimore 2026 (2026-11-18, resloc.twolevel): PUMA, then dwelling (ReslocTwoLevel.search); otherwise region, then dwelling */
    @Override
    public int searchForNewDwelling(Household household) {
        final de.tum.bgu.msm.models.resloc.ReslocTwoLevel m = twoLevel();
        return m == null ? super.searchForNewDwelling(household) : m.search(household, null);
    }

    /** in-migrant placed inside its target region (InOutMigrationImpl regional control) */
    @Override
    public int searchForNewDwelling(Household household, de.tum.bgu.msm.data.Region region) {
        final de.tum.bgu.msm.models.resloc.ReslocTwoLevel m = twoLevel();
        return m == null ? super.searchForNewDwelling(household, region) : m.search(household, region);
    }

    /** Baltimore 2026 (resloc): the simulation year for the dwelling-age term of the estimated dwelling choice */
    @Override
    public void prepareYear(int year) {
        de.tum.bgu.msm.models.resloc.ReslocModel.currentYear = year;
        super.prepareYear(year);
    }

    @Override
    public void moveHousehold(Household hh, int idOldDD, int idNewDD) {
        final Dwelling oldDwelling = idOldDD > 0 ? dataContainer.getRealEstateDataManager().getDwelling(idOldDD) : null;
        final int oldZone = oldDwelling == null ? -1 : oldDwelling.getZoneId();
        super.moveHousehold(hh, idOldDD, idNewDD);
        de.tum.bgu.msm.models.resloc.ReslocModel.recordMove(hh.getId());   // Baltimore 2026: years in the dwelling (move-or-not)
        de.tum.bgu.msm.models.resloc.ReslocTwoLevel.recordMove(hh.getId());   // 2026-11-18: the same for the two-level model
        final Dwelling newDwelling = dataContainer.getRealEstateDataManager().getDwelling(idNewDD);
        final int newZone = newDwelling == null ? -1 : newDwelling.getZoneId();
        if (newZone < 0) {
            return;
        }
        for (Person person : hh.getPersons().values()) {
            if (person.getOccupation() != Occupation.STUDENT || !(person instanceof PersonWithSchool)) {
                continue;
            }
            PersonWithSchool pp = (PersonWithSchool) person;
            if (pp.getSchoolId() > 0 && newZone == oldZone) {
                continue;
            }
            schoolData.assignSchool(pp, schoolData.currentBand(pp));
        }
    }
}
