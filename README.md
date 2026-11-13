# traffic-flow-simulator

Microscopic traffic flow simulator in pure Python: **IDM** car-following
(Treiber et al. 2000) + **MOBIL** lane changing (Kesting et al. 2007),
with congestion analysis (fundamental diagram, shockwave tracking,
travel time, queues, HCM level of service), visualisation and reporting.
No SUMO, no commercial tools — just NumPy/Matplotlib.

## Background

Traffic flow theory in one paragraph: flow `q`, density `k` and
space-mean speed `v` obey `q = k·v` (Greenshields 1935); the
Lighthill–Whitham–Richards theory (1955/56) says disturbances travel
as kinematic waves and pile up into shockwaves that move *backwards*
at ~15–20 km/h; microscopically, each driver follows the Intelligent
Driver Model, and lane changes follow MOBIL. At high density these
local rules generate phantom jams with no bottleneck at all — proven
with real drivers by Sugiyama et al. (2008). See
[`docs/RESEARCH.md`](docs/RESEARCH.md) for the full theory and
references.

## Project structure

```
traffic-flow-simulator/
├── traffic_flow/
│   ├── idm.py            # Intelligent Driver Model (Treiber et al. 2000)
│   ├── mobil.py          # MOBIL lane-changing model (Kesting et al. 2007)
│   ├── vehicle.py        # vehicle types (car/truck/bus) + driver profiles
│   ├── road.py           # road, bottlenecks, traffic lights, on-ramps
│   ├── demand.py         # time-varying demand profiles + Poisson arrivals
│   ├── simulator.py      # discrete-time simulator (dt = 0.1 s)
│   ├── trajectory.py     # trajectory/event recording + independent checks
│   ├── analysis.py       # detectors, FD fit, shockwaves, delay, queues, LOS
│   ├── fundamental.py    # Greenshields fundamental diagram
│   ├── los.py            # HCM level of service (density thresholds)
│   ├── ramp_metering.py  # ALINEA feedback ramp metering (Papageorgiou 1991)
│   ├── visualization.py  # space-time, FD, speed-time, queue plots
│   ├── report.py         # Markdown report + static HTML dashboard
│   ├── scenarios.py      # scenario loading + run pipeline
│   └── cli.py            # CLI: simulate / analyze / compare / report
├── scenarios/            # 5 bundled scenarios (JSON)
├── tests/                # 132 pytest tests, incl. independent verification
├── examples/             # run_examples.sh + outputs from real runs
└── docs/RESEARCH.md      # theory + verified references
```

## Installation

```bash
pip install -r requirements.txt   # numpy, matplotlib, PyYAML, pytest
```

## Usage

```bash
# Run one scenario (writes trajectory.csv, events.json, metrics.json,
# 4 plots, report.md and dashboard.html into the output directory)
python3 -m traffic_flow simulate --scenario scenarios/rush_hour_bottleneck.json \
    --out examples/output/rush_hour_bottleneck

# Recompute metrics from a saved run, without re-simulating
python3 -m traffic_flow analyze --input examples/output/rush_hour_bottleneck

# Compare two runs (e.g. ramp metering off vs on)
python3 -m traffic_flow compare --a examples/output/ramp_metering_off \
    --b examples/output/ramp_metering_on --out examples/output/ramp_metering_comparison

# Regenerate the reports from a saved run
python3 -m traffic_flow report --input examples/output/stop_and_go_wave

# Run all bundled scenarios
bash examples/run_examples.sh
```

A scenario is a JSON (or YAML) file describing the road, the demand
profile, bottlenecks, traffic lights, on-ramps and optional ramp
metering — see `scenarios/*.json`.

## Example results

All numbers below are from real runs (`bash examples/run_examples.sh`,
2026-11-13; full tables in `examples/output/<scenario>/report.md`).
Seeds are fixed, so every number reproduces exactly.

| Scenario | Entered | Throughput | Mean speed | Mean delay | LOS |
|---|---:|---:|---:|---:|---|
| `freeway_free_flow` (3 lanes, 1200 veh/h, 20 min) | 351 | 960 veh/h | 101.0 km/h | 3.8 s | **A** |
| `rush_hour_bottleneck` (3→2 lanes, peak 4200 veh/h, 40 min) | 1987 | 2857.5 veh/h | 83.0 km/h | 141.1 s | **C** |
| `stop_and_go_wave` (2 lanes, 3600 veh/h + 60 s incident, 25 min) | 1394 | 3057.6 veh/h | 65.8 km/h | 65.3 s | **F** |
| `ramp_metering_off` (main 2400 + ramp 900 veh/h, 30 min) | 1592 | 3056.0 veh/h | 94.6 km/h | 11.4 s | **B** |
| `ramp_metering_on` (same, ALINEA metering) | 1482 | 2828.0 veh/h | 97.1 km/h | 10.3 s | **B** |

Highlights:

- **Bottleneck.** The 3→2 lane drop under a 4200 veh/h peak builds a
  queue of up to **160 vehicles / 1642 m**; mean travel time rises to
  240.5 s (free-flow ≈ 99 s). Greenshields fit on 1-min detector bins:
  vf = 115.5 km/h, kj = 44.6 veh/km, capacity 1289 veh/h/lane,
  R² = 0.82.
- **Stop-and-go wave.** After the 60 s incident clears, a wave
  propagates **backwards at −15.64 km/h (R² = 0.999)** — the same
  order as the ~20 km/h measured by Sugiyama et al. (2008). Greenshields
  fit: vf = 100.1 km/h, kj = 81.7 veh/km, capacity 2045 veh/h/lane,
  R² = 0.79. LOS F.
- **Ramp metering (ALINEA).** Metering raises mainline speed
  (+2.5 km/h) and lowers density (10.9 → 9.9 veh/km/lane) and mainline
  delay (11.4 → 10.3 s) — but the price is paid on the ramp: mean ramp
  wait rises from 16.1 s to **346.2 s** and the ramp queue grows to
  125 vehicles. Total completed throughput is lower in the fixed
  30-min horizon (2828 vs 3056 veh/h) because ramp vehicles are still
  queued at the end. This is the classic metering trade-off, not a
  free lunch, and the comparison table reports both sides.

## Design decisions

- **SI units internally** (m, s, m/s); km/h only for display.
- **Semi-implicit (ballistic) Euler** integration, dt = 0.1 s; IDM
  acceleration is clamped to emergency braking (−9 m/s²) so a
  zero gap can never produce a non-finite position.
- **Heterogeneous traffic**: car/truck/bus types × aggressive/normal/
  cautious driver profiles, with ±5 % seeded parameter jitter.
  Parameters sit inside the ranges reported by Treiber & Kesting
  (2013); they are the simulator's calibration, not measurements of
  a specific real road.
- **Vehicles are conserved**: entered = completed + still on road +
  queued at entry/ramps (checked by test).
- **Analysis is independent of the simulator**: every metric is
  recomputed from saved trajectories/events, so `analyze` can verify
  a run without re-simulating it, and the tests re-derive headline
  numbers (travel time, `q = k·v`, Greenshields capacity) with a
  second implementation.

## Limitations & future work

- No driver reaction time or perception error (IDM reacts instantly);
  real drivers' ~1 s delay matters for stability analysis.
- Deterministic drivers apart from seeded jitter and Poisson
  arrivals — real flow–density data scatters more widely.
- One straight road: no junctions, route choice, or signal
  coordination; traffic lights are fixed-time only.
- Parameters are not calibrated to loop-detector data from any real
  freeway — capacities are the *model's* capacities.
- Natural extensions: reaction-time delay, Wiedemann-style
  psycho-physical car-following, coordinated ramp metering,
  calibration against real detector data.

## Tests

```bash
python3 -m pytest tests/ -q
# 132 passed
```

Coverage includes IDM known-case accelerations, MOBIL safety/incentive
criteria, vehicle conservation, no-collision checks, LOS boundaries,
ALINEA behaviour, CLI end-to-end runs, and independent verification
(travel time recomputed from raw trajectories; `q = k·v` identity on
detector bins; Greenshields capacity hand-computed as
`vf·kj/4 = 4500 veh/h`).

## License

MIT — see [LICENSE](LICENSE).
