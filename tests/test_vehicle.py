"""Tests for vehicle types and driver profiles."""

import random

import pytest

from traffic_flow.vehicle import (
    DEFAULT_DRIVER_MIX,
    DEFAULT_MIX,
    VEHICLE_TYPES,
    create_vehicle,
    draw_profile,
    draw_type,
    make_idm_params,
)


def test_car_faster_than_truck():
    car = make_idm_params("car", "normal")
    truck = make_idm_params("truck", "normal")
    assert car.v0 > truck.v0
    assert car.max_accel > truck.max_accel


def test_truck_longer_than_car():
    assert VEHICLE_TYPES["truck"]["length"] > VEHICLE_TYPES["car"]["length"]


def test_bus_between_car_and_truck_speed():
    car = make_idm_params("car", "normal")
    bus = make_idm_params("bus", "normal")
    truck = make_idm_params("truck", "normal")
    assert truck.v0 < bus.v0 < car.v0


def test_aggressive_keeps_smaller_gap_than_cautious():
    agg = make_idm_params("car", "aggressive")
    cau = make_idm_params("car", "cautious")
    assert agg.time_headway < cau.time_headway
    assert agg.v0 > cau.v0
    assert agg.max_accel > cau.max_accel


def test_normal_profile_is_neutral():
    normal = make_idm_params("car", "normal")
    assert normal.v0 == VEHICLE_TYPES["car"]["v0"]
    assert normal.time_headway == VEHICLE_TYPES["car"]["time_headway"]


def test_speed_limit_caps_desired_speed():
    params = make_idm_params("car", "normal", speed_limit=20.0)
    assert params.v0 == 20.0


def test_unknown_type_raises():
    with pytest.raises(ValueError):
        make_idm_params("motorcycle", "normal")


def test_unknown_profile_raises():
    with pytest.raises(ValueError):
        make_idm_params("car", "reckless")


def test_draw_type_deterministic_with_seed():
    rng1, rng2 = random.Random(1), random.Random(1)
    assert [draw_type(rng1) for _ in range(20)] == [
        draw_type(rng2) for _ in range(20)
    ]


def test_draw_type_respects_mix():
    rng = random.Random(0)
    kinds = [draw_type(rng, {"car": 1.0}) for _ in range(10)]
    assert set(kinds) == {"car"}


def test_draw_profile_respects_mix():
    rng = random.Random(0)
    profs = [draw_profile(rng, {"cautious": 1.0}) for _ in range(10)]
    assert set(profs) == {"cautious"}


def test_create_vehicle_same_seed_same_params():
    v1 = create_vehicle(1, random.Random(5), jitter=0.0)
    v2 = create_vehicle(1, random.Random(5), jitter=0.0)
    assert (v1.kind, v1.profile, v1.params) == (v2.kind, v2.profile, v2.params)


def test_create_vehicle_jitter_changes_params():
    rng = random.Random(5)
    base = create_vehicle(1, random.Random(5), jitter=0.0)
    jittered = create_vehicle(1, rng, jitter=0.2)
    assert jittered.params.v0 != base.params.v0


def test_vehicle_free_flow_travel_time():
    v = create_vehicle(1, random.Random(0), kind="car", profile="normal",
                       jitter=0.0)
    assert v.free_flow_travel_time(3000.0) == 3000.0 / v.params.v0


def test_vehicle_rear_position():
    v = create_vehicle(1, random.Random(0), kind="car", profile="normal",
                       x=100.0, jitter=0.0)
    assert v.rear_x == 100.0 - v.length
    assert v.speed_kmh == v.v * 3.6
