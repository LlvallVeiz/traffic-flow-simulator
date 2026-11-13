"""Congestion analysis: detectors, fundamental diagram, shockwaves,
travel time, queues and level of service.

All functions here work on the *recorded* data (trajectory samples,
detector crossings, entry/exit events) rather than on simulator
internals, so the ``analyze`` CLI command can recompute every number
from saved files -- and the tests can verify the same numbers with an
independent implementation.
"""

from __future__ import annotations

import math
import statistics

from .fundamental import fit_greenshields
from .los import los_from_density


def segment_stats(
    samples: list[dict],
    crossings: list[dict],
    x_center: float,
    half_width_m: float,
    n_lanes: int,
    bin_s: float = 60.0,
    duration: float | None = None,
) -> list[dict]:
    """Flow / density / space-mean speed per time bin at one location.

    Flow comes from detector crossings in the bin; density from the
    mean number of sampled vehicles inside
    ``[x_center - half_width_m, x_center + half_width_m]``; speed
    follows from the identity ``q = k * v``.  Bins with no crossings
    and no vehicles are skipped.
    """
    if duration is None:
        times = [s["t"] for s in samples] + [c["t"] for c in crossings]
        duration = max(times) if times else 0.0
    n_bins = max(1, int(math.ceil(duration / bin_s)))
    seg_len_km = 2.0 * half_width_m / 1000.0
    out = []
    for b in range(n_bins):
        t0, t1 = b * bin_s, (b + 1) * bin_s
        n_cross = sum(1 for c in crossings if t0 <= c["t"] < t1)
        flow = n_cross * 3600.0 / bin_s  # veh/h (all lanes)
        in_seg = [s for s in samples
                  if t0 <= s["t"] < t1
                  and abs(s["x"] - x_center) <= half_width_m]
        # Density: mean simultaneous count in the segment.
        sample_times = sorted({s["t"] for s in in_seg})
        if sample_times:
            counts = [
                sum(1 for s in in_seg if s["t"] == tt)
                for tt in sample_times
            ]
            mean_count = sum(counts) / len(counts)
        else:
            mean_count = 0.0
        density = mean_count / seg_len_km / n_lanes  # veh/km/lane
        speed = (flow / n_lanes / density) if density > 0 else float("nan")
        if n_cross == 0 and mean_count == 0:
            continue
        out.append({
            "t_mid": (t0 + t1) / 2.0,
            "flow_veh_per_h": flow,
            "flow_per_lane": flow / n_lanes,
            "density_veh_per_km_per_lane": density,
            "speed_kmh": speed,
        })
    return out


def fundamental_points(stats: list[dict]) -> tuple[list[float], list[float]]:
    """(densities, speeds) of bins with a meaningful speed, for FD fitting."""
    densities, speeds = [], []
    for row in stats:
        v = row["speed_kmh"]
        if math.isfinite(v) and v > 0 and row["density_veh_per_km_per_lane"] > 0:
            densities.append(row["density_veh_per_km_per_lane"])
            speeds.append(v)
    return densities, speeds


def detect_shockwaves(
    samples: list[dict], stopped_speed_ms: float = 1.0
) -> dict:
    """Track the upstream front of stopped traffic (a shockwave).

    At each sample time the front is the smallest ``x`` of a vehicle
    slower than ``stopped_speed_ms``.  A linear fit of front position
    against time gives the wave speed -- negative when the jam moves
    backwards, as in the Sugiyama et al. (2008) ring experiment
    (about -20 km/h).  Returns wave speed in km/h plus fit quality.
    """
    by_time: dict[float, list[dict]] = {}
    for s in samples:
        by_time.setdefault(s["t"], []).append(s)
    fronts: list[tuple[float, float]] = []
    for t in sorted(by_time):
        stopped = [s for s in by_time[t] if s["v"] < stopped_speed_ms]
        if stopped:
            fronts.append((t, min(s["x"] for s in stopped)))
    if len(fronts) < 5:
        return {
            "wave_speed_kmh": None,
            "r_squared": None,
            "n_points": len(fronts),
            "detected": False,
        }
    xs = [f[0] for f in fronts]
    ys = [f[1] for f in fronts]
    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0:
        return {"wave_speed_kmh": None, "r_squared": None,
                "n_points": n, "detected": False}
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = sxy / sxx  # m/s
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - (mean_y + slope * (x - mean_x))) ** 2
                 for x, y in zip(xs, ys))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    # A real stop-and-go wave is a *propagating* front: it must move
    # backwards at a clear speed with a clean linear fit.  A standing
    # queue (e.g. the tail of a bottleneck queue) has ~zero speed and
    # a poor fit and is not a travelling wave.
    detected = bool(r2 >= 0.5 and slope < 0)
    return {
        "wave_speed_kmh": slope * 3.6,
        "r_squared": r2,
        "n_points": n,
        "detected": detected,
        "duration_s": xs[-1] - xs[0],
    }


def travel_time_stats(events: list[dict], road_length: float) -> dict:
    """Travel time / delay statistics for completed vehicles."""
    completed = [e for e in events if e["completed"]]
    if not completed:
        return {
            "n_completed": 0, "mean_travel_time_s": None,
            "median_travel_time_s": None, "p95_travel_time_s": None,
            "mean_free_flow_time_s": None, "mean_delay_s": None,
            "mean_speed_kmh": None,
        }
    times = [e["exit_time"] - e["entry_time"] for e in completed]
    # Distance actually travelled: ramp vehicles join mid-road.
    distances = [
        road_length - e.get("entry_x", 0.0) for e in completed
    ]
    free = [d / e["desired_speed_mps"]
            for d, e in zip(distances, completed)]
    delays = [t - f for t, f in zip(times, free)]
    speeds = [d / t * 3.6 for d, t in zip(distances, times)]
    times_sorted = sorted(times)
    p95 = times_sorted[max(0, int(math.ceil(0.95 * len(times_sorted))) - 1)]
    return {
        "n_completed": len(completed),
        "mean_travel_time_s": statistics.mean(times),
        "median_travel_time_s": statistics.median(times),
        "p95_travel_time_s": p95,
        "mean_free_flow_time_s": statistics.mean(free),
        "mean_delay_s": statistics.mean(delays),
        "mean_speed_kmh": statistics.mean(speeds),
    }


def queue_stats(samples: list[dict], slow_speed_ms: float = 1.4) -> dict:
    """Queue extent from sampled trajectories.

    A vehicle counts as queued when slower than ``slow_speed_ms``
    (5 km/h).  Reports the worst simultaneous count, the worst
    spatial extent of the slow cluster, and the total vehicle-seconds
    spent slow.
    """
    by_time: dict[float, list[dict]] = {}
    for s in samples:
        by_time.setdefault(s["t"], []).append(s)
    max_count = 0
    max_extent = 0.0
    slow_vehicle_seconds = 0.0
    sample_dt = 2.0
    if len(by_time) >= 2:
        ts = sorted(by_time)
        sample_dt = statistics.median(
            [b - a for a, b in zip(ts, ts[1:])]
        )
    for t in sorted(by_time):
        slow = [s for s in by_time[t] if s["v"] < slow_speed_ms]
        slow_vehicle_seconds += len(slow) * sample_dt
        if len(slow) > max_count:
            max_count = len(slow)
        if len(slow) >= 2:
            xs = [s["x"] for s in slow]
            max_extent = max(max_extent, max(xs) - min(xs))
    return {
        "max_queued_vehicles": max_count,
        "max_queue_extent_m": max_extent,
        "slow_vehicle_seconds": slow_vehicle_seconds,
    }


def summarize(result, road=None) -> dict:
    """Compute the full metrics dict for a :class:`SimulationResult`."""
    rec = result.recorder
    events = rec.events
    samples = rec.samples
    duration = result.duration
    completed = sum(1 for e in events if e["completed"])
    throughput = completed / duration * 3600.0 if duration > 0 else 0.0

    # Detector / segment statistics (first detector, or road midpoint).
    det_x = (
        result.detector_crossings
        and sorted(result.detector_crossings)[len(result.detector_crossings) // 2]
    ) or result.road_length / 2.0
    crossings = result.detector_crossings.get(det_x, [])
    stats = segment_stats(
        samples, crossings, det_x, 250.0, result.n_lanes,
        bin_s=60.0, duration=duration,
    )
    densities, speeds = fundamental_points(stats)
    try:
        fd_fit = fit_greenshields(densities, speeds) if len(densities) >= 3 else None
    except ValueError:
        fd_fit = None
    if stats:
        mean_density = statistics.mean(
            r["density_veh_per_km_per_lane"] for r in stats
        )
        max_flow = max(r["flow_per_lane"] for r in stats)
        mean_speed = statistics.mean(
            r["speed_kmh"] for r in stats if math.isfinite(r["speed_kmh"])
        )
    else:
        mean_density, max_flow, mean_speed = 0.0, 0.0, float("nan")
    los = los_from_density(mean_density)

    tt = travel_time_stats(events, result.road_length)
    q = queue_stats(samples)
    sw = detect_shockwaves(samples)
    lane_changes = sum(e["lane_changes"] for e in events)
    max_entry_q = max((n for _, n in result.entry_queue_series), default=0)
    max_ramp_q = max((n for _, n in result.ramp_queue_series), default=0)

    metrics: dict = {
        "scenario": result.scenario_name,
        "duration_s": duration,
        "seed": result.seed,
        "runtime_s": round(result.runtime_s, 2),
        "vehicles_entered": result.entered_vehicles,
        "vehicles_completed": completed,
        "throughput_veh_per_h": round(throughput, 1),
        "mean_density_veh_per_km_per_lane": round(mean_density, 2),
        "max_flow_per_lane_veh_per_h": round(max_flow, 1),
        "mean_speed_kmh": round(mean_speed, 2) if math.isfinite(mean_speed) else None,
        "level_of_service": los,
        "ramp_wait": {
            "n_vehicles": len(result.ramp_waits),
            "mean_wait_s": (
                round(statistics.mean(result.ramp_waits), 2)
                if result.ramp_waits else None
            ),
            "max_wait_s": (
                round(max(result.ramp_waits), 2)
                if result.ramp_waits else None
            ),
        },
        "travel_time": {k: (round(v, 2) if isinstance(v, float) else v)
                        for k, v in tt.items()},
        "queue": {
            "max_queued_vehicles": q["max_queued_vehicles"],
            "max_queue_extent_m": round(q["max_queue_extent_m"], 1),
            "slow_vehicle_seconds": round(q["slow_vehicle_seconds"], 1),
            "max_entry_queue": max_entry_q,
            "max_ramp_queue": max_ramp_q,
        },
        "shockwave": {
            "detected": sw["detected"],
            "wave_speed_kmh": (
                round(sw["wave_speed_kmh"], 2)
                if sw["wave_speed_kmh"] is not None else None
            ),
            "r_squared": (
                round(sw["r_squared"], 3)
                if sw["r_squared"] is not None else None
            ),
            "n_points": sw["n_points"],
        },
        "lane_changes": lane_changes,
        "detector_x_m": det_x,
        "fundamental_diagram_fit": fd_fit,
        "segment_stats": [
            {k: (round(v, 3) if isinstance(v, float) else v)
             for k, v in row.items()}
            for row in stats
        ],
    }
    return metrics
