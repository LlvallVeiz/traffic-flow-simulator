"""Scenario definitions and the run pipeline.

A scenario is a JSON (or YAML) file describing the road, the demand
profile, bottlenecks, traffic lights, on-ramps and optional ramp
metering.  :func:`run_scenario` executes it end to end and writes
all artefacts into an output directory:

* ``trajectory.csv`` -- sampled trajectories
* ``events.json`` -- entry/exit events per vehicle
* ``metrics.json`` -- congestion metrics
* ``space_time.png`` / ``fundamental.png`` / ``speed_time.png`` /
  ``queues.png`` -- figures
* ``report.md`` / ``dashboard.html`` -- reports
"""

from __future__ import annotations

import json
import os

from .analysis import summarize
from .ramp_metering import AlineaMeter
from .report import write_metrics, write_reports
from .simulator import Simulator, build_demand, build_road
from .visualization import (
    plot_fundamental,
    plot_queues,
    plot_space_time,
    plot_speed_time,
)

BUILTIN_SCENARIOS = [
    "freeway_free_flow",
    "rush_hour_bottleneck",
    "stop_and_go_wave",
    "ramp_metering_off",
    "ramp_metering_on",
]


def scenarios_dir() -> str:
    """Directory holding the bundled scenario files."""
    return os.path.join(os.path.dirname(__file__), "..", "scenarios")


def load_scenario(path: str) -> dict:
    """Load a scenario from a JSON or YAML file."""
    with open(path) as fh:
        if path.endswith((".yaml", ".yml")):
            import yaml

            cfg = yaml.safe_load(fh)
        else:
            cfg = json.load(fh)
    if "name" not in cfg:
        cfg["name"] = os.path.splitext(os.path.basename(path))[0]
    return cfg


def list_scenarios() -> list[str]:
    """Names of the bundled scenarios."""
    return list(BUILTIN_SCENARIOS)


def run_scenario(cfg: dict, out_dir: str, seed: int | None = None) -> dict:
    """Run one scenario and write every artefact to ``out_dir``.

    Returns the metrics dict.
    """
    seed = cfg.get("seed", 42) if seed is None else seed
    road = build_road(cfg)
    demand = build_demand(cfg)
    ramp_demands = {}
    for ramp_cfg in cfg.get("on_ramps", []):
        ramp_demands[ramp_cfg["x_merge"]] = build_demand(
            {"demand": {"intervals": ramp_cfg["demand"]["intervals"]}}
        ) if "demand" in ramp_cfg else None
    ramp_demands = {k: v for k, v in ramp_demands.items() if v is not None}

    metering = None
    meter_cfg = cfg.get("ramp_metering")
    if meter_cfg and meter_cfg.get("enabled"):
        metering = AlineaMeter(
            target_density=meter_cfg.get("target_density", 25.0),
            gain=meter_cfg.get("gain", 70.0),
            rate_min=meter_cfg.get("rate_min", 240.0),
            rate_max=meter_cfg.get("rate_max", 1800.0),
            cycle=meter_cfg.get("cycle", 20.0),
            initial_rate=meter_cfg.get("initial_rate", 900.0),
        )

    detectors = cfg.get("detectors", [road.length_m / 2.0])
    sim = Simulator(
        road, demand, ramp_demands,
        duration=cfg.get("duration", 1800.0),
        dt=cfg.get("dt", 0.1),
        seed=seed,
        sample_dt=cfg.get("sample_dt", 2.0),
        detector_positions=detectors,
        ramp_metering=metering,
        mix=cfg.get("mix"),
        driver_mix=cfg.get("driver_mix"),
        jitter=cfg.get("jitter", 0.05),
        scenario_name=cfg["name"],
    )
    result = sim.run()
    metrics = summarize(result)
    result.metrics = metrics

    os.makedirs(out_dir, exist_ok=True)
    result.recorder.samples_to_csv(os.path.join(out_dir, "trajectory.csv"))
    result.recorder.events_to_json(os.path.join(out_dir, "events.json"))
    write_metrics(metrics, os.path.join(out_dir, "metrics.json"))
    with open(os.path.join(out_dir, "scenario.json"), "w") as fh:
        json.dump(cfg, fh, indent=2)

    plots: dict[str, str] = {}
    plots["space_time"] = plot_space_time(
        result.recorder.samples, road.length_m, result.duration,
        os.path.join(out_dir, "space_time.png"),
    )
    stats = metrics["segment_stats"]
    plots["fundamental"] = plot_fundamental(
        stats, metrics.get("fundamental_diagram_fit"),
        os.path.join(out_dir, "fundamental.png"),
    )
    plots["speed_time"] = plot_speed_time(
        stats, os.path.join(out_dir, "speed_time.png"))
    plots["queues"] = plot_queues(
        result.entry_queue_series, result.ramp_queue_series,
        os.path.join(out_dir, "queues.png"))
    write_reports(metrics, cfg, out_dir,
                  {k: os.path.basename(v) for k, v in plots.items()})
    return metrics
