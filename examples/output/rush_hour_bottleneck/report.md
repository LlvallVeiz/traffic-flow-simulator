# Traffic Flow Report -- rush_hour_bottleneck

Three-lane freeway with a lane drop to two lanes at x=2000 m. Demand rises from 1800 to 4200 veh/h during the peak (600-1800 s), above the two-lane bottleneck capacity, so a queue forms upstream of the drop and discharges after the peak.

## Summary

| Metric | Value |
|---|---|
| Duration | 2400 s (40.0 min) |
| Vehicles entered | 1987 |
| Vehicles completed | 1905 |
| Throughput | 2857.5 veh/h |
| Mean speed | 82.95 km/h |
| Mean density | 12.58 veh/km/lane |
| Max flow per lane | 1480.0 veh/h/ln |
| Level of Service (HCM) | **C** |
| Lane changes | 3827 |

## Travel time

| Metric | Value |
|---|---|
| Mean travel time | 240.50 s |
| Median travel time | 187.20 s |
| 95th percentile | 583.60 s |
| Free-flow travel time | 99.36 s |
| Mean delay | 141.13 s |
| Mean speed (from travel time) | 59.83 km/h |

## Queues

| Metric | Value |
|---|---|
| Max queued vehicles (slow, <5 km/h) | 160 |
| Max queue extent | 1641.5 m |
| Slow vehicle-seconds | 71874.0 veh-s |
| Max entry queue | 1 |
| Max ramp queue | 0 |
| Ramp vehicles merged | 0 |
| Mean ramp wait | n/a |
| Max ramp wait | n/a |

## Shockwaves (stop-and-go)

- No sustained stop-and-go wave detected.

## Fundamental diagram

- Greenshields fit: vf = 115.5 km/h, kj = 44.6 veh/km, capacity qmax = 1289 veh/h/ln (critical density 22.3 veh/km)
- Fit R^2 = 0.824 over 39 one-minute bins.

## Figures

- `space_time.png` -- space-time diagram (colour = speed)
- `fundamental.png` -- flow-density diagram with Greenshields fit
- `speed_time.png` -- space-mean speed and density vs time
- `queues.png` -- entry / ramp queue lengths vs time

## Method

Microscopic simulation with the Intelligent Driver Model (IDM, Treiber et al. 2000) for car-following and MOBIL (Kesting et al. 2007) for lane changing; discrete-time integration (dt = 0.1 s). See `docs/RESEARCH.md` for the theory and references.
