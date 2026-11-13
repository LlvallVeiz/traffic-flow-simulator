"""Tests for the Greenshields fundamental diagram."""

import pytest

from traffic_flow.fundamental import (
    fit_greenshields,
    flow_density_speed_identity,
    greenshields_capacity,
    greenshields_critical_density,
    greenshields_flow,
    greenshields_speed,
)


def test_speed_at_zero_density_is_free_flow():
    assert greenshields_speed(0.0, 120.0, 150.0) == 120.0


def test_speed_at_jam_density_is_zero():
    assert greenshields_speed(150.0, 120.0, 150.0) == 0.0
    assert greenshields_speed(200.0, 120.0, 150.0) == 0.0


def test_speed_is_linear_in_density():
    # v = 120 * (1 - k/150): at k=75, v=60.
    assert greenshields_speed(75.0, 120.0, 150.0) == 60.0


def test_flow_is_density_times_speed():
    for k in (10.0, 50.0, 100.0):
        assert greenshields_flow(k, 120.0, 150.0) == pytest.approx(
            k * greenshields_speed(k, 120.0, 150.0))


def test_capacity_hand_computed():
    # qmax = vf * kj / 4 = 120 * 150 / 4 = 4500 veh/h.
    assert greenshields_capacity(120.0, 150.0) == 4500.0
    assert greenshields_flow(75.0, 120.0, 150.0) == 4500.0


def test_critical_density_is_half_jam_density():
    assert greenshields_critical_density(150.0) == 75.0


def test_fit_recovers_exact_parameters():
    # Synthetic noise-free Greenshields data.
    vf, kj = 100.0, 140.0
    ks = [10.0, 30.0, 50.0, 70.0, 90.0, 110.0]
    vs = [greenshields_speed(k, vf, kj) for k in ks]
    fit = fit_greenshields(ks, vs)
    assert fit["vf"] == pytest.approx(vf, rel=1e-9)
    assert fit["kj"] == pytest.approx(kj, rel=1e-9)
    assert fit["q_max"] == pytest.approx(vf * kj / 4, rel=1e-9)
    assert fit["r_squared"] == pytest.approx(1.0)


def test_fit_recovers_parameters_from_noisy_data():
    import random

    rng = random.Random(4)
    vf, kj = 90.0, 160.0
    ks = [10.0 + 10 * i for i in range(12)]
    vs = [greenshields_speed(k, vf, kj) + rng.uniform(-1.5, 1.5) for k in ks]
    fit = fit_greenshields(ks, vs)
    assert fit["vf"] == pytest.approx(vf, rel=0.05)
    assert fit["kj"] == pytest.approx(kj, rel=0.10)
    assert fit["r_squared"] > 0.95


def test_fit_rejects_degenerate_input():
    with pytest.raises(ValueError):
        fit_greenshields([10.0, 10.0, 10.0], [50.0, 50.0, 50.0])
    with pytest.raises(ValueError):
        fit_greenshields([10.0, 20.0], [50.0, 40.0])  # too few points
    with pytest.raises(ValueError):
        fit_greenshields([10.0, 20.0, 30.0], [50.0, 60.0, 70.0])  # rising


def test_flow_density_speed_identity():
    assert flow_density_speed_identity(2000.0, 25.0, 80.0) == pytest.approx(0.0)
    assert flow_density_speed_identity(2000.0, 25.0, 60.0) == pytest.approx(
        abs(2000 - 1500) / 1500)
