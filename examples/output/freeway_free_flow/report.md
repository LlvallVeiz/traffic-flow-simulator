# Traffic Flow Report -- freeway_free_flow

Three-lane freeway, light demand (1200 veh/h), no bottleneck. Baseline: free-flow conditions, LOS A expected.

## Summary

| Metric | Value |
|---|---|
| Duration | 1200 s (20.0 min) |
| Vehicles entered | 351 |
| Vehicles completed | 320 |
| Throughput | 960.0 veh/h |
| Mean speed | 101.02 km/h |
| Mean density | 3.30 veh/km/lane |
| Max flow per lane | 640.0 veh/h/ln |
| Level of Service (HCM) | **A** |
| Lane changes | 698 |

## Travel time

| Metric | Value |
|---|---|
| Mean travel time | 102.59 s |
| Median travel time | 96.15 s |
| 95th percentile | 137.70 s |
| Free-flow travel time | 98.80 s |
| Mean delay | 3.79 s |
| Mean speed (from travel time) | 107.25 km/h |

## Queues

| Metric | Value |
|---|---|
| Max queued vehicles (slow, <5 km/h) | 0 |
| Max queue extent | 0.0 m |
| Slow vehicle-seconds | 0.0 veh-s |
| Max entry queue | 0 |
| Max ramp queue | 0 |
| Ramp vehicles merged | 0 |
| Mean ramp wait | n/a |
| Max ramp wait | n/a |

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
