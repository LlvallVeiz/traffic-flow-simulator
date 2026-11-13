"""Tests for demand profiles and Poisson arrival generation."""

import random

import pytest

from traffic_flow.demand import (
    ArrivalGenerator,
    DemandInterval,
    DemandProfile,
)


def test_rate_at_piecewise():
    p = DemandProfile([
        DemandInterval(0, 600, 1000),
        DemandInterval(600, 1200, 3000),
    ])
    assert p.rate_at(0) == 1000
    assert p.rate_at(599) == 1000
    assert p.rate_at(600) == 3000
    assert p.rate_at(2000) == 0


def test_constant_profile():
    p = DemandProfile.constant(1800, 3600)
    assert p.rate_at(100) == 1800
    assert p.total_expected == 1800.0


def test_rush_hour_profile():
    p = DemandProfile.rush_hour(base_rate=1000, peak_rate=4000,
                                peak_start=600, peak_end=1800, duration=2400)
    assert p.rate_at(100) == 1000
    assert p.rate_at(1000) == 4000
    assert p.rate_at(2000) == 1000
    assert p.total_expected == pytest.approx(
        1000 * 600 / 3600 + 4000 * 1200 / 3600 + 1000 * 600 / 3600)


def test_morning_evening_profile_peaks():
    p = DemandProfile.morning_evening(
        night_rate=200, morning_peak=4000, midday_rate=1500,
        evening_peak=3500, duration=86400)
    assert p.rate_at(8 * 3600) == 4000  # morning peak
    assert p.rate_at(12 * 3600) == 1500  # midday
    assert p.rate_at(18 * 3600) == 3500  # evening peak
    assert p.rate_at(2 * 3600) == 200  # night


def test_interval_expected_vehicles():
    iv = DemandInterval(0, 1800, 2000)
    assert iv.expected_vehicles == 1000.0


def test_invalid_interval():
    with pytest.raises(ValueError):
        DemandInterval(100, 100, 1000)
    with pytest.raises(ValueError):
        DemandInterval(0, 100, -5)


def test_arrivals_are_increasing_and_cover_horizon():
    p = DemandProfile.constant(3600, 600)
    gen = ArrivalGenerator(p, random.Random(3))
    times = []
    t = gen.next_arrival(0.0)
    while t is not None and t < 600:
        times.append(t)
        t = gen.next_arrival(t)
    assert times == sorted(times)
    assert len(times) > 400  # ~600 expected at 3600 veh/h
    assert len(times) < 800


def test_arrival_rate_matches_profile_statistically():
    p = DemandProfile.constant(3600, 3600)
    gen = ArrivalGenerator(p, random.Random(9))
    times = []
    t = gen.next_arrival(0.0)
    while t is not None and t < 3600:
        times.append(t)
        t = gen.next_arrival(t)
    # 3600 veh/h for 1 h -> about 3600 arrivals (+/- 5%).
    assert 3400 < len(times) < 3800


def test_no_arrivals_when_rate_zero():
    p = DemandProfile.constant(0, 600)
    gen = ArrivalGenerator(p, random.Random(1))
    assert gen.next_arrival(0.0) is None


def test_arrival_generator_skips_zero_rate_gap():
    p = DemandProfile([
        DemandInterval(0, 100, 0),
        DemandInterval(100, 200, 3600),
    ])
    gen = ArrivalGenerator(p, random.Random(2))
    t = gen.next_arrival(0.0)
    assert t is not None and t >= 100.0
