# Runtime and storage

Measured on the development machine (Apple M5 Pro, 18 cores, 48 GB memory).

| Step | Heap | Threads | Time | Disk |
|---|---|---|---|---|
| CVAE training | – | CPU or GPU | early stopping (best epoch 197) | – |
| Base population export | – | – | – | about 1.1 GB of CSV (persons 614 MB) |
| SILO calibration run, 2016–2020 | 24 GB | 12 | about 42 min | |
| SILO run, 2016–2024 | 21–28 GB | 12 | about 1 h 40 min alone; 2 h 55 min with two in parallel | about 11 GB per run |
| MILES-Day, 10 % of households | 13 GB | 6 | about 6 min per replication | |
| MATSim, 10 % sample, 100 iterations | 32 GB | 12 | about 6 h per seed | plans 0.5 GB; events 1.3 GB |
| Transit mapping (pt2matsim) | ≤ 9 GB | – | – | |

!!! tip "Disk"
    `assignment/run_seeds.sh` extracts hourly link volumes after each seed, deletes the events and
    stops when less than 7 GB of disk is free.

## Scale of a 2024 run

| Item | Count |
|---|---|
| Households in the 10 % sample | 500,564 |
| Persons | 1,278,947 |
| Activities | 6.95 million |
| Trips (legs) | 4.33 million |
| Tours | 1.50 million |
| MATSim agents (residents touching the region) | 262,842, with 1.03 million legs |
