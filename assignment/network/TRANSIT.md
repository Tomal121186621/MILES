# Transit feed check (MTA Maryland GTFS, downloaded 2026-10-21)

Feeds: `fetch_gtfs.sh` (URLs from https://www.mta.maryland.gov/developer-resources, served from mdotmta-gtfs.s3.amazonaws.com). Headways are computed
from the first departure of every trip on the representative weekday 2026-10-21 (Wednesday, every feed's calendar in force), averaged over the two directions.

| feed | version / validity | routes in feed | routes on the weekday | trips on the weekday | published route count (mta.maryland.gov/schedule, 2026-10-21) |
|---|---|---|---|---|---|
| local-bus | 20260821 / 20260821-20270206 | 66 | 66 | 6,052 | 66 (12 CityLink + 54 numbered LocalLink/Express) |
| light-rail | - / 20230423-20261231 | 1 | 1 | 304 | 1 |
| metro | - / 20240101-20261231 | 1 | 1 | 247 | 1 |
| marc | - / 20221114-20261231 | 3 | 3 | 96 | 3 (Brunswick, Penn, Camden) |
| commuter-bus | - / 20210829-20261231 | 37 | 37 | 394 | 37 |

Route counts agree with the schedule page for every feed.

## Headways of the core routes (minutes, GTFS weekday)

| route | trips | AM peak 7-9 | midday 10-14 | PM peak 16-18 | evening 19-22 |
|---|---|---|---|---|---|
| CityLink BLUE | 159 | 15.0 | 14.2 | 16.0 | 22.5 |
| CityLink BROWN | 154 | 14.2 | 15.0 | 15.0 | 30.0 |
| CityLink GOLD | 212 | 8.9 | 10.0 | 10.4 | 21.2 |
| CityLink GREEN | 150 | 11.6 | 14.6 | 16.0 | 30.8 |
| CityLink LIME | 173 | 12.0 | 11.7 | 12.0 | 21.2 |
| CityLink NAVY | 177 | 10.9 | 14.6 | 10.4 | 21.2 |
| CityLink ORANGE | 186 | 8.8 | 14.6 | 10.4 | 20.0 |
| CityLink PINK | 162 | 15.2 | 14.1 | 16.0 | 20.0 |
| CityLink PURPLE | 168 | 10.4 | 15.5 | 11.0 | 21.2 |
| CityLink RED | 209 | 8.1 | 12.0 | 8.9 | 19.0 |
| CityLink SILVER | 169 | 11.4 | 15.5 | 12.0 | 20.0 |
| CityLink YELLOW | 160 | 12.0 | 15.5 | 12.6 | 20.0 |
| LIGHT RAILLINK | 304 | 7.5 | 9.0 | 8.0 | 10.0 |
| METRO SUBWAYLINK | 247 | 8.0 | 10.0 | 8.3 | 11.2 |

Against the published service:
- CityLink (12 routes): GTFS AM-peak headways 8-15 min (mean 11.5), midday 10-16, evening 19-31. Published: 10 min peak, 15-20 min off-peak, 30 min late evening (BaltimoreLink design standard for the 12 CityLink routes; MTA/BMC outreach presentation, 2016).
  9 of 12 routes meet the 10-minute peak standard within 2 minutes; the others run every 12-15 minutes in the peak, which is the level MTA's route pages state for them.
- Metro SubwayLink: GTFS 8 min AM peak, 10 min midday, 11 min evening. Published: 8-10 min weekday peak, 11 min weekday evening, 15 min weekends (MTA service description, Maryland open-data record, 2016).
- Light RailLink: GTFS 7.5 min AM peak (two branches on the common trunk), 9 min midday. no published headway retrieved (the MTA schedule pages returned HTTP 500 on 2026-10-21); the GTFS value stands alone.

The MATSim transit schedule is built from these feeds and those of the regional operators in `4_matsim/transit/` (2026-10-22, `TRANSIT_BUILD.md`).
Ridership comparison (MTA ridership by route) belongs to the assignment validation (stage 4 report).

Tables: `data/transit_gtfs_routes.csv`, `data/transit_gtfs_headways.csv`, `data/transit_gtfs_headways_core.csv`.
