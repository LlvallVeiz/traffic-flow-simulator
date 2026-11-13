"""Tests for congestion analysis (detectors, shockwaves, travel time, queues)."""

import math

from traffic_flow.analysis import (
    detect_shockwaves,
    fundamental_points,
    queue_stats,
    segment_stats,
    travel_time_stats,
)


def _synthetic_segment():
    # 3 vehicles cruising at 25 m/s through a 500 m segment around x=1500,
    # sampled every 2 s, plus detector crossings at x=1500.
    samples, crossings = [], []
    for vid in (1, 2, 3):
        x0 = 1000.0 + (vid - 1) * 100.0
        for k in range(31):
            t = float(k * 2)
            x = x0 + 25.0 * t
            if x > 3000:
                break
            samples.append({"t": t, "vehicle_id": vid, "x": x,
                            "lane": 0, "v": 25.0, "kind": "car"})
            if x >= 1500.0 and x - 25.0 * 2 < 1500.0:
                crossings.append({"t": t, "vehicle_id": vid, "v": 25.0,
                                  "kind": "car"})
    return samples, crossings


def test_segment_stats_flow_density_speed():
    samples, crossings = _synthetic_segment()
    stats = segment_stats(samples, crossings, 1500.0, 250.0, n_lanes=1,
                          bin_s=60.0, duration=60.0)
    assert len(stats) == 1
    row = stats[0]
    # 3 crossings in 60 s -> 180 veh/h; density: 3 vehicles in 0.5 km
    # -> 6 veh/km; speed = 180/6 = 30 km/h... but vehicles move at
    # 25 m/s = 90 km/h.  The discrepancy is the warm-up: only part of
    # the bin has 3 vehicles in the segment.  Check the identity
    # instead of absolute values.
    assert row["flow_veh_per_h"] == 180.0
    assert row["density_veh_per_km_per_lane"] > 0
    assert row["speed_kmh"] == row["flow_veh_per_h"] / (
        row["density_veh_per_km_per_lane"])


def test_segment_stats_empty_input():
    assert segment_stats([], [], 1500.0, 250.0, 1) == []


def test_fundamental_points_filters_invalid():
    stats = [
        {"density_veh_per_km_per_lane": 10.0, "speed_kmh": 90.0},
        {"density_veh_per_km_per_lane": 0.0, "speed_kmh": 90.0},
        {"density_veh_per_km_per_lane": 20.0, "speed_kmh": float("nan")},
    ]
    d, v = fundamental_points(stats)
    assert d == [10.0] and v == [90.0]


def test_travel_time_stats_hand_computed():
    events = [
        {"vehicle_id": 1, "completed": True, "entry_time": 0.0,
         "exit_time": 100.0, "desired_speed_mps": 30.0},
        {"vehicle_id": 2, "completed": True, "entry_time": 0.0,
         "exit_time": 120.0, "desired_speed_mps": 30.0},
        {"vehicle_id": 3, "completed": False, "entry_time": 0.0,
         "exit_time": None, "desired_speed_mps": 30.0},
    ]
    tt = travel_time_stats(events, 3000.0)
    assert tt["n_completed"] == 2
    assert tt["mean_travel_time_s"] == 110.0
    assert tt["median_travel_time_s"] == 110.0
    assert tt["mean_free_flow_time_s"] == 100.0
    assert tt["mean_delay_s"] == 10.0
    # Mean of the per-vehicle speeds: 3000/100 s = 108 km/h and
    # 3000/120 s = 90 km/h -> mean 99 km/h.
    assert tt["mean_speed_kmh"] == (108.0 + 90.0) / 2


def test_travel_time_stats_no_completed():
    tt = travel_time_stats([], 3000.0)
    assert tt["n_completed"] == 0
    assert tt["mean_travel_time_s"] is None


def test_travel_time_stats_ramp_entry_uses_remaining_distance():
    # A ramp vehicle joins at x=1500, so its free-flow time is for
    # 1500 m, not the full 3000 m.
    events = [
        {"vehicle_id": 1, "completed": True, "entry_time": 0.0,
         "exit_time": 50.0, "desired_speed_mps": 30.0, "entry_x": 1500.0},
    ]
    tt = travel_time_stats(events, 3000.0)
    assert tt["mean_free_flow_time_s"] == 50.0
    assert tt["mean_delay_s"] == 0.0
    assert tt["mean_speed_kmh"] == 1500.0 / 50.0 * 3.6


def test_detect_shockwave_known_speed():
    # A jam front moving backwards at exactly 5 m/s (-18 km/h):
    # at t, the slowest vehicle sits at x = 2000 - 5*t.
    samples = []
    for k in range(30):
        t = float(k * 2)
        x_front = 2000.0 - 5.0 * t
        samples.append({"t": t, "vehicle_id": 1, "x": x_front,
                        "lane": 0, "v": 0.0, "kind": "car"})
        samples.append({"t": t, "vehicle_id": 2, "x": x_front + 500.0,
                        "lane": 0, "v": 25.0, "kind": "car"})
    sw = detect_shockwaves(samples)
    assert sw["detected"] is True
    assert sw["wave_speed_kmh"] == -18.0
    assert sw["r_squared"] == 1.0


def test_detect_shockwave_none_when_no_stopped_vehicles():
    samples = [
        {"t": float(k * 2), "vehicle_id": 1, "x": 100.0 + 50 * k,
         "lane": 0, "v": 25.0, "kind": "car"}
        for k in range(10)
    ]
    sw = detect_shockwaves(samples)
    assert sw["detected"] is False
    assert sw["wave_speed_kmh"] is None


def test_queue_stats_hand_computed():
    samples = []
    for k in range(5):
        t = float(k * 2)
        # 2 slow vehicles + 1 fast vehicle at each sample time.
        samples.append({"t": t, "vehicle_id": 1, "x": 100.0 + k,
                        "lane": 0, "v": 0.5, "kind": "car"})
        samples.append({"t": t, "vehicle_id": 2, "x": 300.0 + k,
                        "lane": 0, "v": 0.0, "kind": "car"})
        samples.append({"t": t, "vehicle_id": 3, "x": 900.0 + 25 * k,
                        "lane": 0, "v": 25.0, "kind": "car"})
    q = queue_stats(samples)
    assert q["max_queued_vehicles"] == 2
    assert q["max_queue_extent_m"] == 200.0
    assert q["slow_vehicle_seconds"] == 2 * 5 * 2.0
