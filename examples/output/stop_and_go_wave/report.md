# Traffic Flow Report -- stop_and_go_wave

Two-lane freeway near capacity (3600 veh/h). A 60 s full blockage (incident) at x=1500 m during t=400-460 s triggers a stop-and-go wave that propagates backwards after the blockage clears, as in the Sugiyama et al. (2008) ring experiment.

## Summary

| Metric | Value |
|---|---|
| Duration | 1500 s (25.0 min) |
| Vehicles entered | 1394 |
| Vehicles completed | 1274 |
| Throughput | 3057.6 veh/h |
| Mean speed | 65.76 km/h |
| Mean density | 28.04 veh/km/lane |
| Max flow per lane | 1980.0 veh/h/ln |
| Level of Service (HCM) | **F** |
| Lane changes | 822 |

## Travel time

| Metric | Value |
|---|---|
| Mean travel time | 148.08 s |
| Median travel time | 134.30 s |
| 95th percentile | 198.70 s |
| Free-flow travel time | 82.83 s |
| Mean delay | 65.25 s |
| Mean speed (from travel time) | 63.12 km/h |

## Queues

| Metric | Value |
|---|---|
| Max queued vehicles (slow, <5 km/h) | 67 |
| Max queue extent | 272.6 m |
| Slow vehicle-seconds | 10364.0 veh-s |
| Max entry queue | 1 |
| Max ramp queue | 0 |
| Ramp vehicles merged | 0 |
| Mean ramp wait | n/a |
| Max ramp wait | n/a |

## Shockwaves (stop-and-go)

- Detected: yes (138 front samples)
- Backward wave speed: **-15.64 km/h** (negative = travelling against traffic, as in Sugiyama et al. 2008)
- Fit R^2: 0.999

## Fundamental diagram

- Greenshields fit: vf = 100.1 km/h, kj = 81.7 veh/km, capacity qmax = 2045 veh/h/ln (critical density 40.9 veh/km)
- Fit R^2 = 0.785 over 25 one-minute bins.

## Figures

- `space_time.png` -- space-time diagram (colour = speed)
- `fundamental.png` -- flow-density diagram with Greenshields fit
- `speed_time.png` -- space-mean speed and density vs time
- `queues.png` -- entry / ramp queue lengths vs time

## Method

Microscopic simulation with the Intelligent Driver Model (IDM, Treiber et al. 2000) for car-following and MOBIL (Kesting et al. 2007) for lane changing; discrete-time integration (dt = 0.1 s). See `docs/RESEARCH.md` for the theory and references.
