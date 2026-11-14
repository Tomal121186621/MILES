# Known limitations

**No feedback from the assignment.**
: The land-use and activity models read fixed skims. Assigned morning-peak car times are a median 0.78 of the skim
  times on which locations were chosen.

**Weak response to time and cost in mode choice.**
: All time and cost coefficients are negative and significant but small. A 20 % higher car operating cost lowers
  car-driver kilometres by about 0.2 % (elasticity about −0.01), below the published range; the transit-time
  elasticity is about −0.2. The models reproduce current mode shares through their constants and socio-economic
  terms and respond weakly to price and time.

**Activity frequencies do not respond to travel conditions.**
: Frequencies, start times and durations come from survey distributions. They depend on the day's work or school
  episode, not on travel time, cost or the calendar year.

**Activity levels of 2024.**
: The model keeps the workplace attendance of 2017/18. More residents have a work activity than in the 2021–2024 time
  use survey, and discretionary activities do not follow the fall after 2019.

**Moves after 2020.**
: The calibrated move rate stays at its 2017–2020 level, while the observed rate fell after 2020.

**Residents only on the roads.**
: Trucks, commercial vehicles, visitors and through traffic are not modelled. Volumes fall short of counts outside
  the peaks and on roads with much freight.

**Correlated distance terms in the stop models.**
: The stop models combine highly correlated distance terms (variance inflation factors up to 32), each kept because
  it lowers the BIC; their individual coefficients are less precise than the fit suggests.

**Repeated use of the hold-out half.**
: The hold-out half was consulted more than once in the specification search of several models, so its fit is not a
  fully independent test.
