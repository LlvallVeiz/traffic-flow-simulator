"""Tests for the Intelligent Driver Model (IDM)."""

import math

import pytest

from traffic_flow.idm import (
    IDMParams,
    desired_gap,
    equilibrium_flow,
    equilibrium_gap,
    free_acceleration,
    idm_acceleration,
)

CAR = IDMParams(v0=33.3, time_headway=1.5, min_gap=2.0,
                max_accel=1.0, comfort_decel=1.5)


def test_free_acceleration_at_standstill_is_max():
    assert free_acceleration(0.0, CAR) == pytest.approx(CAR.max_accel)


def test_free_acceleration_at_desired_speed_is_zero():
    assert free_acceleration(CAR.v0, CAR) == pytest.approx(0.0, abs=1e-9)


def test_free_acceleration_above_desired_speed_is_negative():
    assert free_acceleration(CAR.v0 * 1.2, CAR) < 0


def test_free_acceleration_decreases_with_speed():
    speeds = [0.0, 10.0, 20.0, 30.0]
    accels = [free_acceleration(v, CAR) for v in speeds]
    assert accels == sorted(accels, reverse=True)


def test_no_leader_equals_free_acceleration():
    assert idm_acceleration(10.0, None, None, CAR) == pytest.approx(
        free_acceleration(10.0, CAR)
    )


def test_approaching_stopped_leader_brakes_hard():
    # 20 m/s, 10 m behind a stopped vehicle: must brake harder than
    # the comfortable deceleration.
    a = idm_acceleration(20.0, 0.0, 10.0, CAR)
    assert a < -CAR.comfort_decel


def test_large_gap_approximates_free_acceleration():
    a = idm_acceleration(20.0, 20.0, 1000.0, CAR)
    assert a == pytest.approx(free_acceleration(20.0, CAR), abs=0.05)


def test_desired_gap_grows_with_speed():
    assert desired_gap(30.0, 0.0, CAR) > desired_gap(10.0, 0.0, CAR)


def test_desired_gap_grows_with_approach_rate():
    assert desired_gap(20.0, 10.0, CAR) > desired_gap(20.0, 0.0, CAR)
    assert desired_gap(20.0, -5.0, CAR) < desired_gap(20.0, 0.0, CAR)


def test_equilibrium_gap_gives_zero_acceleration():
    for v in (5.0, 10.0, 20.0, 30.0):
        gap = equilibrium_gap(v, CAR)
        a = idm_acceleration(v, v, gap, CAR)
        assert a == pytest.approx(0.0, abs=1e-6)


def test_equilibrium_gap_infinite_at_desired_speed():
    assert math.isinf(equilibrium_gap(CAR.v0, CAR))


def test_equilibrium_flow_positive_and_peaked():
    flows = [equilibrium_flow(v, 4.5, CAR) for v in (5, 10, 15, 20, 25, 30)]
    assert all(f > 0 for f in flows)
    # Flow rises then falls: the maximum is inside the range.
    assert max(flows) == flows[2] or max(flows) == flows[3]


def test_negative_speed_rejected():
    with pytest.raises(ValueError):
        idm_acceleration(-1.0, None, None, CAR)


def test_acceleration_is_finite_at_zero_gap():
    # Regression: the raw IDM formula diverges to -inf at gap 0,
    # which used to push vehicle positions to -inf.  The result must
    # be finite and no stronger than emergency braking.
    from traffic_flow.idm import MAX_DECEL

    a = idm_acceleration(20.0, 0.0, 0.0, CAR)
    assert a == -MAX_DECEL
    assert math.isfinite(a)


def test_invalid_params_rejected():
    with pytest.raises(ValueError):
        IDMParams(v0=0.0)
    with pytest.raises(ValueError):
        IDMParams(v0=30.0, max_accel=-1.0)
    with pytest.raises(ValueError):
        IDMParams(v0=30.0, time_headway=0.0)
