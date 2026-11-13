# Traffic Flow Report -- ramp_metering_off

Three-lane freeway with an on-ramp at x=1500 m. Mainline demand 2400 veh/h, ramp demand 900 veh/h, NO ramp metering: ramp vehicles merge on gap acceptance only. Compare with ramp_metering_on.

## Summary

| Metric | Value |
|---|---|
| Duration | 1800 s (30.0 min) |
| Vehicles entered | 1592 |
| Vehicles completed | 1528 |
| Throughput | 3056.0 veh/h |
| Mean speed | 94.57 km/h |
| Mean density | 10.91 veh/km/lane |
| Max flow per lane | 1340.0 veh/h/ln |
| Level of Service (HCM) | **B** |
| Lane changes | 3375 |

## Travel time

| Metric | Value |
|---|---|
| Mean travel time | 97.48 s |
| Median travel time | 102.45 s |
| 95th percentile | 137.60 s |
| Free-flow travel time | 86.04 s |
| Mean delay | 11.44 s |
| Mean speed (from travel time) | 97.15 km/h |

## Queues

| Metric | Value |
|---|---|
| Max queued vehicles (slow, <5 km/h) | 0 |
| Max queue extent | 0.0 m |
| Slow vehicle-seconds | 0.0 veh-s |
| Max entry queue | 1 |
| Max ramp queue | 21 |
| Ramp vehicles merged | 410 |
| Mean ramp wait | 16.05 s |
| Max ramp wait | 60.90 s |

## Shockwaves (stop-and-go)

- No sustained stop-and-go wave detected.

## Fundamental diagram

- Not enough varied bins to fit the Greenshields model.

## Figures

- `space_time.png` -- space-time diagram (colour = speed)
- `fundamental.png` -- flow-density diagram with Greenshields fit
- `speed_time.png` -- space-mean speed and density vs time
- `queues.png` -- entry / ramp queue lengths vs time

## Method

Microscopic simulation with the Intelligent Driver Model (IDM, Treiber et al. 2000) for car-following and MOBIL (Kesting et al. 2007) for lane changing; discrete-time integration (dt = 0.1 s). See `docs/RESEARCH.md` for the theory and references.
