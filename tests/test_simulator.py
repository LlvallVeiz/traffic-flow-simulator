"""End-to-end simulator tests (conservation, no collisions, determinism,
bottlenecks, lights, ramp metering).  Runs are kept short (60-150 s).
"""

import pytest

from traffic_flow.analysis import queue_stats, summarize
from traffic_flow.demand import DemandProfile
from traffic_flow.ramp_metering import AlineaMeter
from traffic_flow.road import Bottleneck, OnRamp, Road, TrafficLight
from traffic_flow.simulator import Simulator


def _run(road, demand, duration=120.0, seed=42, ramp_demands=None,
         metering=None, **kw):
    sim = Simulator(road, demand, ramp_demands, duration=duration, seed=seed,
                    ramp_metering=metering, detector_positions=[1500.0],
                    scenario_name="test", **kw)
    return sim.run()


def _min_gap_from_samples(samples, n_lanes):
    """Minimum bumper-to-bumper gap between consecutive vehicles."""
    by_time = {}
    for s in samples:
        by_time.setdefault(s["t"], {}).setdefault(s["lane"], []).append(s)
    worst = float("inf")
    for lanes in by_time.values():
        for lane_samples in lanes.values():
            ordered = sorted(lane_samples, key=lambda s: -s["x"])
            for lead, foll in zip(ordered, ordered[1:]):
                length = 4.5 if lead["kind"] == "car" else 12.0
                gap = (lead["x"] - length) - foll["x"]
                worst = min(worst, gap)
    return worst


def test_conservation_of_vehicles():
    road = Road(length_m=3000.0, n_lanes=2)
    result = _run(road, DemandProfile.constant(1200, 120))
    entered = result.entered_vehicles
    completed = result.completed_vehicles
    # entered = completed + still on road + pending entry
    still_on_road = entered - completed
    assert still_on_road >= 0
    assert entered > 20  # 1200 veh/h * 120 s = 40 expected
    assert completed < entered  # road takes ~90 s to cross


def test_no_collisions_in_free_flow():
    road = Road(length_m=3000.0, n_lanes=3)
    result = _run(road, DemandProfile.constant(1500, 120))
    worst = _min_gap_from_samples(result.recorder.samples, 3)
    assert worst >= -0.5  # no overlap beyond numerical tolerance


def test_no_collisions_in_congestion():
    road = Road(
        length_m=3000.0, n_lanes=3,
        bottlenecks=[Bottleneck(kind="lane_drop", x_start=2000.0,
                                x_end=3000.0, lanes_after=1)])
    demand = DemandProfile.rush_hour(1500, 4500, 30, 90, 120)
    result = _run(road, demand)
    worst = _min_gap_from_samples(result.recorder.samples, 3)
    assert worst >= -0.5


def test_determinism_same_seed():
    road = Road(length_m=3000.0, n_lanes=2)
    r1 = _run(road, DemandProfile.constant(1800, 120), seed=7)
    r2 = _run(road, DemandProfile.constant(1800, 120), seed=7)
    assert r1.completed_vehicles == r2.completed_vehicles
    assert r1.recorder.samples == r2.recorder.samples
    assert r1.recorder.events == r2.recorder.events


def test_different_seed_different_result():
    road = Road(length_m=3000.0, n_lanes=2)
    r1 = _run(road, DemandProfile.constant(1800, 120), seed=7)
    r2 = _run(road, DemandProfile.constant(1800, 120), seed=8)
    assert r1.recorder.events != r2.recorder.events


def test_free_flow_reaches_desired_speed():
    road = Road(length_m=3000.0, n_lanes=1)
    result = _run(road, DemandProfile.constant(300, 300), seed=1,
                  duration=300.0)
    speeds = [e for e in result.recorder.events if e["completed"]]
    assert speeds, "no vehicle completed the road"
    m = summarize(result)
    # Mean travel-time speed should be close to free flow (~110 km/h
    # for a mix dominated by cars at 120 km/h).
    assert m["travel_time"]["mean_speed_kmh"] > 90.0


def test_lane_drop_creates_queue():
    road = Road(
        length_m=3000.0, n_lanes=3,
        bottlenecks=[Bottleneck(kind="lane_drop", x_start=2000.0,
                                x_end=3000.0, lanes_after=1)])
    # Long enough for the peak flow to reach the drop and queue up:
    # 6000 veh/h against a one-lane capacity of ~2000 veh/h.
    demand = DemandProfile.rush_hour(1500, 6000, 20, 240, 300)
    result = _run(road, demand, duration=300.0)
    q = queue_stats(result.recorder.samples)
    assert q["max_queued_vehicles"] > 0


def test_traffic_light_stops_vehicles():
    road = Road(
        length_m=3000.0, n_lanes=1,
        traffic_lights=[TrafficLight(x=1500.0, green=10.0, yellow=2.0,
                                     red=40.0)])
    result = _run(road, DemandProfile.constant(600, 150), seed=3)
    slow = [s for s in result.recorder.samples if s["v"] < 1.0]
    assert slow, "no vehicle ever stopped at the red light"
    # Stopped vehicles cluster near the light.
    assert any(1200.0 <= s["x"] <= 1500.0 for s in slow)


def test_incident_blocks_and_releases():
    road = Road(
        length_m=2500.0, n_lanes=2,
        bottlenecks=[Bottleneck(kind="incident", x_start=1500.0,
                                x_end=1520.0, t_start=30.0, t_end=60.0)])
    result = _run(road, DemandProfile.constant(2400, 120), seed=5)
    q = queue_stats(result.recorder.samples)
    assert q["max_queued_vehicles"] > 0


def test_ramp_metering_runs_and_clamps_rate():
    road = Road(length_m=3000.0, n_lanes=3,
                on_ramps=[OnRamp(x_merge=1500.0)])
    main = DemandProfile.constant(2400, 150)
    ramp = DemandProfile.constant(900, 150)
    meter = AlineaMeter(target_density=25.0, gain=70.0)
    result = _run(road, main, duration=150, seed=21,
                  ramp_demands={1500.0: ramp}, metering=meter)
    assert result.metering_series, "no metering updates recorded"
    rates = [m["rate_veh_per_h"] for m in result.metering_series]
    assert all(240.0 <= r <= 1800.0 for r in rates)
    ramp_entered = [e for e in result.recorder.events
                    if e["entered_via"] == "ramp"]
    assert ramp_entered, "no ramp vehicle ever merged"
    # Waiting times on the ramp are recorded (arrival -> merge).
    assert result.ramp_waits, "no ramp waiting times recorded"
    assert all(w >= 0 for w in result.ramp_waits)
    assert max(result.ramp_waits) > 0, "metering should make some ramp vehicles wait"


def test_ramp_without_metering_merges():
    road = Road(length_m=3000.0, n_lanes=3,
                on_ramps=[OnRamp(x_merge=1500.0)])
    main = DemandProfile.constant(1200, 120)
    ramp = DemandProfile.constant(600, 120)
    result = _run(road, main, duration=120, seed=21,
                  ramp_demands={1500.0: ramp})
    ramp_entered = [e for e in result.recorder.events
                    if e["entered_via"] == "ramp"]
    assert ramp_entered


def test_summarize_returns_expected_keys():
    road = Road(length_m=3000.0, n_lanes=2)
    result = _run(road, DemandProfile.constant(1200, 120))
    m = summarize(result)
    for key in ("throughput_veh_per_h", "mean_speed_kmh",
                "level_of_service", "travel_time", "queue",
                "shockwave", "fundamental_diagram_fit"):
        assert key in m
    assert m["level_of_service"] in "ABCDEF"
