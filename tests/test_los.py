"""Tests for HCM level-of-service thresholds."""

import pytest

from traffic_flow.los import (
    los_description,
    los_from_density,
    los_from_flow_speed,
)


@pytest.mark.parametrize("density,expected", [
    (0.0, "A"),
    (7.0, "A"),
    (7.01, "B"),
    (11.0, "B"),
    (11.01, "C"),
    (16.0, "C"),
    (16.01, "D"),
    (22.0, "D"),
    (22.01, "E"),
    (28.0, "E"),
    (28.01, "F"),
    (100.0, "F"),
])
def test_los_boundaries(density, expected):
    assert los_from_density(density) == expected


def test_los_negative_density_rejected():
    with pytest.raises(ValueError):
        los_from_density(-1.0)


def test_los_descriptions():
    assert "Free flow" in los_description("A")
    assert "Forced flow" in los_description("F")
    with pytest.raises(ValueError):
        los_description("G")


def test_los_from_flow_speed():
    # D = vp / S = 600 / 100 = 6 pc/km/ln -> A.
    assert los_from_flow_speed(600.0, 100.0) == "A"
    # D = 1800 / 60 = 30 -> F.
    assert los_from_flow_speed(1800.0, 60.0) == "F"
    # Zero speed -> F (standstill).
    assert los_from_flow_speed(1000.0, 0.0) == "F"
