"""Command-line interface.

Subcommands
-----------
simulate
    Run a scenario file (JSON/YAML) and write all artefacts.
analyze
    Recompute metrics from a saved run directory (trajectory.csv +
    events.json) without re-simulating.
compare
    Compare two runs (throughput, speed, travel time, delay, LOS).
report
    Regenerate report.md / dashboard.html from a saved run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .analysis import summarize
from .report import write_metrics, write_reports
from .scenarios import list_scenarios, load_scenario, run_scenario
from .simulator import SimulationResult
from .trajectory import TrajectoryRecorder
from .visualization import (
    plot_fundamental,
    plot_queues,
    plot_space_time,
    plot_speed_time,
)


def _load_run(run_dir: str) -> tuple[dict, SimulationResult]:
    """Load a saved run (metrics + raw data) from ``run_dir``."""
    with open(os.path.join(run_dir, "metrics.json")) as fh:
        metrics = json.load(fh)
    with open(os.path.join(run_dir, "scenario.json")) as fh:
        scenario = json.load(fh)
    rec = TrajectoryRecorder()
    rec.samples = TrajectoryRecorder.samples_from_csv(
        os.path.join(run_dir, "trajectory.csv"))
    rec.events = TrajectoryRecorder.events_from_json(
        os.path.join(run_dir, "events.json"))
    # Same detector choice as analysis.summarize: the middle detector
    # of the scenario's detector list.
    detectors = sorted(scenario.get("detectors", [scenario["road"]["length_m"] / 2.0]))
    det_x = detectors[len(detectors) // 2]
    result = SimulationResult(
        scenario_name=metrics["scenario"],
        road_length=scenario["road"]["length_m"],
        n_lanes=scenario["road"]["n_lanes"],
        duration=metrics["duration_s"],
        dt=scenario.get("dt", 0.1),
        seed=metrics["seed"],
        recorder=rec,
        detector_crossings={det_x: []},
        runtime_s=metrics.get("runtime_s", 0.0),
    )
    return scenario, result


def cmd_simulate(args: argparse.Namespace) -> int:
    cfg = load_scenario(args.scenario)
    metrics = run_scenario(cfg, args.out, seed=args.seed)
    print(f"scenario : {metrics['scenario']}")
    print(f"entered  : {metrics['vehicles_entered']} vehicles")
    print(f"completed: {metrics['vehicles_completed']} vehicles")
    print(f"throughput: {metrics['throughput_veh_per_h']:.1f} veh/h")
    print(f"mean speed: {metrics['mean_speed_kmh']} km/h")
    print(f"LOS      : {metrics['level_of_service']}")
    print(f"mean delay: {metrics['travel_time']['mean_delay_s']} s")
    print(f"output   : {args.out}")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    scenario, result = _load_run(args.input)
    # Rebuild detector crossings from the trajectory is not possible
    # from samples alone, so analyze re-derives flow from samples:
    # crossings are approximated by sampling crossings of the detector
    # line between consecutive samples of each vehicle.
    det_x = next(iter(result.detector_crossings))
    crossings: list[dict] = []
    by_vehicle: dict[int, list[dict]] = {}
    for s in result.recorder.samples:
        by_vehicle.setdefault(s["vehicle_id"], []).append(s)
    for vid, rows in by_vehicle.items():
        rows.sort(key=lambda r: r["t"])
        prev = rows[0]
        for row in rows[1:]:
            if prev["x"] < det_x <= row["x"]:
                crossings.append({"t": row["t"], "vehicle_id": vid,
                                  "v": row["v"], "kind": row["kind"]})
            prev = row
    result.detector_crossings = {det_x: crossings}
    metrics = summarize(result)
    write_metrics(metrics, os.path.join(args.input, "metrics.json"))
    print(f"scenario : {metrics['scenario']}")
    print(f"throughput: {metrics['throughput_veh_per_h']:.1f} veh/h")
    print(f"mean speed: {metrics['mean_speed_kmh']} km/h")
    print(f"LOS      : {metrics['level_of_service']}")
    print(f"mean delay: {metrics['travel_time']['mean_delay_s']} s")
    return 0


def _fmt_num(value, nd: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{nd}f}"


def _delta(va, vb, nd: int = 1) -> str:
    if va is None or vb is None:
        return "-"
    return f"{vb - va:+.{nd}f}"


def _compare_table(a: dict, b: dict) -> str:
    """Markdown comparison table for two metrics dicts."""
    def row(label: str, key: str, unit: str = "", nd: int = 1):
        va, vb = a[key], b[key]
        delta = vb - va if isinstance(va, (int, float)) and isinstance(vb, (int, float)) else None
        d = f"{delta:+.{nd}f}" if delta is not None else "-"
        return f"| {label} | {_fmt_num(va, nd)}{unit} | {_fmt_num(vb, nd)}{unit} | {d}{unit} |"

    def tt_row(label: str, key: str):
        va, vb = a["travel_time"][key], b["travel_time"][key]
        if va is None or vb is None:
            return f"| {label} | {_fmt_num(va)} s | {_fmt_num(vb)} s | - |"
        return (f"| {label} | {va:.1f} s | {vb:.1f} s | "
                f"{vb - va:+.1f} s |")

    lines = [
        f"# Comparison: {a['scenario']} vs {b['scenario']}",
        "",
        "| Metric | A | B | B - A |",
        "|---|---|---|---|",
        row("Throughput", "throughput_veh_per_h", " veh/h"),
        row("Mean speed", "mean_speed_kmh", " km/h", 2),
        row("Mean density", "mean_density_veh_per_km_per_lane",
            " veh/km/ln", 2),
        row("Max flow / lane", "max_flow_per_lane_veh_per_h", " veh/h/ln"),
        f"| LOS | {a['level_of_service']} | {b['level_of_service']} | - |",
        tt_row("Mean travel time", "mean_travel_time_s"),
        tt_row("Mean delay", "mean_delay_s"),
        f"| Max queued vehicles | {a['queue']['max_queued_vehicles']} | "
        f"{b['queue']['max_queued_vehicles']} | "
        f"{b['queue']['max_queued_vehicles'] - a['queue']['max_queued_vehicles']:+d} |",
        f"| Max queue extent | {a['queue']['max_queue_extent_m']:.0f} m | "
        f"{b['queue']['max_queue_extent_m']:.0f} m | "
        f"{b['queue']['max_queue_extent_m'] - a['queue']['max_queue_extent_m']:+.0f} m |",
        f"| Mean ramp wait | {_fmt_num(a['ramp_wait']['mean_wait_s'])} s | "
        f"{_fmt_num(b['ramp_wait']['mean_wait_s'])} s | "
        f"{_delta(a['ramp_wait']['mean_wait_s'], b['ramp_wait']['mean_wait_s'])} s |",
        f"| Max ramp queue | {a['queue']['max_ramp_queue']} | "
        f"{b['queue']['max_ramp_queue']} | "
        f"{b['queue']['max_ramp_queue'] - a['queue']['max_ramp_queue']:+d} |",
        "",
    ]
    return "\n".join(lines)


def cmd_compare(args: argparse.Namespace) -> int:
    with open(os.path.join(args.a, "metrics.json")) as fh:
        a = json.load(fh)
    with open(os.path.join(args.b, "metrics.json")) as fh:
        b = json.load(fh)
    table = _compare_table(a, b)
    print(table)
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "comparison.md"), "w") as fh:
            fh.write(table)
        with open(os.path.join(args.out, "comparison.json"), "w") as fh:
            json.dump({"a": a, "b": b}, fh, indent=2)
        print(f"comparison written to {args.out}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    scenario, result = _load_run(args.input)
    with open(os.path.join(args.input, "metrics.json")) as fh:
        metrics = json.load(fh)
    plots = {
        "space_time": "space_time.png",
        "fundamental": "fundamental.png",
        "speed_time": "speed_time.png",
        "queues": "queues.png",
    }
    out_dir = args.out or args.input
    os.makedirs(out_dir, exist_ok=True)
    write_reports(metrics, scenario, out_dir, plots)
    print(f"report written to {out_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="traffic-flow",
        description="Microscopic traffic flow simulator (IDM + MOBIL).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_sim = sub.add_parser("simulate", help="Run a scenario file.")
    p_sim.add_argument("--scenario", required=True,
                       help="Scenario JSON/YAML file.")
    p_sim.add_argument("--out", required=True, help="Output directory.")
    p_sim.add_argument("--seed", type=int, default=None,
                       help="Random seed (default: scenario seed).")
    p_sim.set_defaults(func=cmd_simulate)

    p_an = sub.add_parser("analyze", help="Recompute metrics from a saved run.")
    p_an.add_argument("--input", required=True, help="Run directory.")
    p_an.set_defaults(func=cmd_analyze)

    p_cmp = sub.add_parser("compare", help="Compare two runs.")
    p_cmp.add_argument("--a", required=True, help="First run directory.")
    p_cmp.add_argument("--b", required=True, help="Second run directory.")
    p_cmp.add_argument("--out", default=None, help="Output directory.")
    p_cmp.set_defaults(func=cmd_compare)

    p_rep = sub.add_parser("report", help="Regenerate reports from a saved run.")
    p_rep.add_argument("--input", required=True, help="Run directory.")
    p_rep.add_argument("--out", default=None, help="Output directory.")
    p_rep.set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
