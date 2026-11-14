# County view

The validation of every stage, county by county: all 24 Maryland counties for the population and land use, and the six
counties of the study area (Baltimore City and the counties of Baltimore, Anne Arundel, Howard, Harford and Carroll) for
every stage.

!!! info "How to read the figures"
    Heatmaps: total variation distance between the model and the ACS for each county and variable, in percentage points;
    bold above the 5 pp limit. The six study counties are above the line. Bars: orange model, dark grey observed. County
    samples of the ACS are small, so differences of a few points in the smaller counties are within its sampling error.

## Synthetic population, 2016

The base population against the ACS PUMS 2014–2018, by county. **151 of 168** county × variable cells are within 5 pp,
16 between 5 and 10, one above 10 (household size in Baltimore City, where one-person households are too few).

<figure markdown>
  ![](../../assets/img/validation/county/fig_county_heat_population.png)
  <figcaption>Synthetic population of 2016 against the ACS PUMS 2014–2018: total variation distance by county and variable.</figcaption>
</figure>

### Every variable in the study counties

=== "Household size"

    ![](../../assets/img/validation/county/fig_county_population_household.png)

=== "Cars"

    ![](../../assets/img/validation/county/fig_county_population_cars.png)

=== "Household income"

    ![](../../assets/img/validation/county/fig_county_population_income.png)

=== "Age"

    ![](../../assets/img/validation/county/fig_county_population_age.png)

=== "Employment, 16+"

    ![](../../assets/img/validation/county/fig_county_population_employed.png)

=== "Sex"

    ![](../../assets/img/validation/county/fig_county_population_sex.png)

=== "Adults 18–34 with parents"

    ![](../../assets/img/validation/county/fig_county_population_adults.png)


## Land use, 2024

The 2024 population of the land-use model (mean of five seeds) against the ACS PUMS 2024, by county, after eight years of
simulation. **131 of 168** cells are within 5 pp, 35 between 5 and 10, two above 10.

<figure markdown>
  ![](../../assets/img/validation/county/fig_county_heat_landuse.png)
  <figcaption>Land use in 2024 against the ACS PUMS 2024: total variation distance by county and variable.</figcaption>
</figure>

### Every variable in the study counties

=== "Household size"

    ![](../../assets/img/validation/county/fig_county_landuse_household.png)

=== "Cars"

    ![](../../assets/img/validation/county/fig_county_landuse_cars.png)

=== "Household income"

    ![](../../assets/img/validation/county/fig_county_landuse_income.png)

=== "Age"

    ![](../../assets/img/validation/county/fig_county_landuse_age.png)

=== "Employment, 16+"

    ![](../../assets/img/validation/county/fig_county_landuse_employed.png)

=== "Sex"

    ![](../../assets/img/validation/county/fig_county_landuse_sex.png)

=== "Adults 18–34 with parents"

    ![](../../assets/img/validation/county/fig_county_landuse_adults.png)


### Population, jobs and workplaces

| County | Persons ÷ Census, 2016 | Persons ÷ Census, 2024 | Filled jobs ÷ LODES, 2016 | Filled jobs ÷ LODES, 2023 | Jobs in home county, model / LODES, 2016 | Jobs in home county, model / LODES, 2023 |
|---|---:|---:|---:|---:|---:|---:|
| Baltimore City | 1.000 | 1.000 | 1.06 | 1.08 | 57.2 / 47.4 % | 56.3 / 46.2 % |
| Baltimore County | 1.000 | 1.000 | 0.99 | 1.00 | 52.8 / 43.1 % | 52.5 / 41.6 % |
| Anne Arundel | 1.000 | 1.000 | 1.04 | 1.08 | 53.9 / 47.0 % | 54.7 / 42.9 % |
| Howard | 1.000 | 1.000 | 1.00 | 0.97 | 42.5 / 33.2 % | 41.2 / 32.1 % |
| Harford | 1.000 | 1.000 | 1.17 | 1.16 | 57.4 / 39.0 % | 55.4 / 38.8 % |
| Carroll | 1.000 | 0.940 | 1.01 | 1.03 | 43.8 / 33.6 % | 44.8 / 32.3 % |

County populations are controlled to the Census estimates; Carroll falls 6 % short in 2024 because the county runs out of
vacant dwellings. The home-county job share is higher than in LODES in every county. LODES counts jobs rather than workers; the
comparison with the ACS commute below, which counts workers, is closer.

## All stages in the study counties

<figure markdown>
  ![](../../assets/img/validation/county/fig_county_composition.png)
  <figcaption>(a) Land use 2024 against the ACS 2024: total variation distance of four attributes, with the 5 pp limit; (b) commuters
  working in their home county, activity model 2024 against the ACS 2024.</figcaption>
</figure>

<figure markdown>
  ![](../../assets/img/validation/county/fig_county_ratios.png)
  <figcaption>(a) 2024 persons ÷ Census estimate and filled jobs ÷ LODES 2023; (b) traffic ÷ counts (passenger vehicles,
  mainline stations) and weekday passenger-vehicle miles ÷ MDOT SHA mileage. Traffic carries residents only.</figcaption>
</figure>

| County | Persons ÷ Census | Filled jobs ÷ LODES | Household size TVD | Cars TVD | Income TVD | Work in home county, model / ACS | Commute flows TVD vs ACS | Count stations | Traffic ÷ counts | Vehicle-miles ÷ MDOT |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Baltimore City | 1.000 | 1.08 | 9.3 pp | 1.0 pp | 3.5 pp | 56.5 / 61.8 % | 5.7 pp | 572 | 0.81 | 0.74 |
| Baltimore County | 1.000 | 1.00 | 3.7 pp | 0.7 pp | 3.7 pp | 53.1 / 51.7 % | 3.7 pp | 750 | 0.83 | 0.82 |
| Anne Arundel | 1.000 | 1.08 | 4.3 pp | 2.1 pp | 6.2 pp | 50.9 / 59.9 % | 9.2 pp | 443 | 0.81 | 0.80 |
| Howard | 1.000 | 0.97 | 6.6 pp | 2.0 pp | 4.8 pp | 39.2 / 44.9 % | 5.9 pp | 178 | 0.76 | 0.73 |
| Harford | 1.000 | 1.16 | 3.0 pp | 3.0 pp | 4.9 pp | 54.6 / 56.5 % | 2.9 pp | 210 | 0.77 | 0.75 |
| Carroll | 0.940 | 1.03 | 6.9 pp | 2.8 pp | 8.5 pp | 43.3 / 46.6 % | 7.6 pp | 154 | 0.97 | 0.95 |

TVD: total variation distance against the ACS 2024. Traffic ÷ counts: passenger vehicles at the mainline count stations of
the county.
