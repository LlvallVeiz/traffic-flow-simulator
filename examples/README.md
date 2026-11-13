# Examples

Run every bundled scenario (plus the ramp-metering comparison) with:

```bash
bash examples/run_examples.sh
```

Each scenario writes into `examples/output/<scenario>/`:

| File | Contents |
|---|---|
| `trajectory.csv` | Sampled trajectories (t, vehicle_id, x, lane, v, kind), every 2 s |
| `events.json` | Entry/exit record per vehicle (travel time, lane changes) |
| `metrics.json` | All congestion metrics (throughput, LOS, delay, shockwave, …) |
| `scenario.json` | The scenario definition that was run |
| `space_time.png` | Space-time diagram (colour = speed) |
| `fundamental.png` | Flow–density diagram with Greenshields fit |
| `speed_time.png` | Space-mean speed and density vs time |
| `queues.png` | Entry / ramp queue lengths vs time |
| `report.md` | Human-readable report |
| `dashboard.html` | Static HTML dashboard (open in a browser) |

## Scenarios

| Scenario | What it shows |
|---|---|
| `freeway_free_flow` | 3-lane freeway, light demand (1200 veh/h): free flow, LOS A |
| `rush_hour_bottleneck` | Demand peak (4200 veh/h) against a 3→2 lane drop: queue formation and discharge |
| `stop_and_go_wave` | Near-capacity flow + a 60 s incident: a stop-and-go wave travelling backwards |
| `ramp_metering_off` | On-ramp merging with no control |
| `ramp_metering_on` | Same as above with ALINEA ramp metering |
| `ramp_metering_comparison` | `comparison.md`: off vs on, side by side |

Key results are summarised in the main `README.md` (section "Example results").
