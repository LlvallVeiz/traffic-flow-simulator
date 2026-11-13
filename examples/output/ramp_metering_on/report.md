# Traffic Flow Report -- ramp_metering_on

Same geometry and demand as ramp_metering_off, but with ALINEA ramp metering (Papageorgiou et al. 1991): the release rate adapts every 20 s to keep downstream density near the critical value of 25 veh/km/lane. Compare with ramp_metering_off.

## Summary

| Metric | Value |
|---|---|
| Duration | 1800 s (30.0 min) |
| Vehicles entered | 1482 |
| Vehicles completed | 1414 |
| Throughput | 2828.0 veh/h |
| Mean speed | 97.05 km/h |
| Mean density | 9.88 veh/km/lane |
| Max flow per lane | 1240.0 veh/h/ln |
| Level of Service (HCM) | **B** |
| Lane changes | 3232 |

## Travel time

| Metric | Value |
|---|---|
| Mean travel time | 99.35 s |
| Median travel time | 102.60 s |
| 95th percentile | 138.10 s |
| Free-flow travel time | 89.08 s |
| Mean delay | 10.26 s |
| Mean speed (from travel time) | 99.15 km/h |

## Queues

| Metric | Value |
|---|---|
| Max queued vehicles (slow, <5 km/h) | 0 |
| Max queue extent | 0.0 m |
| Slow vehicle-seconds | 0.0 veh-s |
| Max entry queue | 1 |
| Max ramp queue | 125 |
| Ramp vehicles merged | 300 |
| Mean ramp wait | 346.24 s |
| Max ramp wait | 649.20 s |

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
