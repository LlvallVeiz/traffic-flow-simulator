"""Independent verification: every headline number is recomputed with a
second implementation (or by hand) and must agree with the simulator.
"""

import pytest

from traffic_flow.analysis import segment_stats, summarize
from traffic_flow.demand import DemandProfile
from traffic_flow.fundamental import fit_greenshields
from traffic_flow.road import Road
from traffic_flow.simulator import Simulator
from traffic_flow.trajectory import travel_time_from_samples


def _run_free_flow(duration=300.0, rate=300.0, seed=1):
    road = Road(length_m=3000.0, n_lanes=1)
    sim = Simulator(road, DemandProfile.constant(rate, duration),
                    duration=duration, seed=seed,
                    detector_positions=[1500.0], scenario_name="verify")
    return sim.run()


def test_single_vehicle_travel_time_matches_free_flow():
    # Cars only, no jitter, low rate: vehicles barely interact, so the
    # travel time must be close to L / v0 (hand-computed per vehicle).
    road = Road(length_m=3000.0, n_lanes=1)
    sim = Simulator(road, DemandProfile.constant(120, 300),
                    duration=300, seed=1, detector_positions=[1500.0],
                    scenario_name="verify", mix={"car": 1.0},
                    driver_mix={"normal": 1.0}, jitter=0.0)
    result = sim.run()
    assert result.completed_vehicles > 0
    for ev in result.recorder.events:
        if not ev["completed"]:
            continue
        free = 3000.0 / ev["desired_speed_mps"]
        actual = ev["exit_time"] - ev["entry_time"]
        assert actual == pytest.approx(free, rel=0.05)


def test_travel_time_from_samples_matches_events():
    # Independent implementation: recompute each completed vehicle's
    # travel time from the raw sampled trajectory only.
    result = _run_free_flow(duration=240.0, rate=600.0, seed=2)
    checked = 0
    for ev in result.recorder.events:
        if not ev["completed"]:
            continue
        t_samples = travel_time_from_samples(
            result.recorder.samples, ev["vehicle_id"], 3000.0)
        t_events = ev["exit_time"] - ev["entry_time"]
        assert t_samples is not None
        # Sample-based estimate can differ by at most one sample
        # interval (2 s) plus interpolation error.
        assert t_samples == pytest.approx(t_events, abs=2.5)
        checked += 1
    assert checked > 0


def test_flow_density_speed_identity_on_real_run():
    # q = k * v must hold (within sampling noise) on detector bins
    # with enough vehicles.
    result = _run_free_flow(duration=600.0, rate=1200.0, seed=3)
    crossings = result.detector_crossings[1500.0]
    stats = segment_stats(result.recorder.samples, crossings, 1500.0,
                          250.0, 1, bin_s=60.0, duration=600.0)
    good = [r for r in stats if r["flow_veh_per_h"] > 300]
    assert good, "no bin with enough flow to check the identity"
    for r in good:
        q = r["flow_veh_per_h"]
        k, v = (r["density_veh_per_km_per_lane"], r["speed_kmh"])
        assert abs(q - k * v) / q < 0.15


def test_greenshields_fit_on_simulated_data_is_physical():
    # A rush-hour run spans free flow to congestion, so the
    # one-minute bins cover a wide density range and the Greenshields
    # fit must return plausible parameters.  The scatter is wide
    # (as in real flow-density data), so only a modest R^2 is required.
    road = Road(length_m=3000.0, n_lanes=2)
    sim = Simulator(
        road, DemandProfile.rush_hour(600, 4200, 300, 900, 1200),
        duration=1200, seed=4,
        detector_positions=[1500.0], scenario_name="verify")
    result = sim.run()
    metrics = summarize(result)
    fit = metrics["fundamental_diagram_fit"]
    assert fit is not None
    assert 60.0 < fit["vf"] < 130.0
    assert 50.0 < fit["kj"] < 300.0
    assert 1000.0 < fit["q_max"] < 4000.0
    assert fit["r_squared"] > 0.15


def test_hand_computed_capacity_matches_formula():
    # Greenshields with vf=120 km/h, kj=150 veh/km -> qmax=4500 veh/h.
    fit = fit_greenshields(
        [10.0, 30.0, 50.0, 70.0, 90.0, 110.0, 130.0],
        [112.0, 96.0, 80.0, 64.0, 48.0, 32.0, 16.0],
    )
    assert fit["vf"] == pytest.approx(120.0, rel=1e-6)
    assert fit["kj"] == pytest.approx(150.0, rel=1e-6)
    assert fit["q_max"] == pytest.approx(4500.0, rel=1e-6)


def test_throughput_matches_completed_count():
    result = _run_free_flow(duration=300.0, rate=900.0, seed=6)
    metrics = summarize(result)
    expected = result.completed_vehicles / 300.0 * 3600.0
    assert metrics["throughput_veh_per_h"] == pytest.approx(expected, rel=1e-6)
