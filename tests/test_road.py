"""Tests for road geometry: bottlenecks, traffic lights, on-ramps."""

from traffic_flow.road import Bottleneck, OnRamp, Road, TrafficLight


def _road():
    return Road(
        length_m=3000.0, n_lanes=3, speed_limit=33.3,
        bottlenecks=[
            Bottleneck(kind="lane_drop", x_start=2000.0, x_end=3000.0,
                       lanes_after=2, t_start=100.0, t_end=500.0),
            Bottleneck(kind="speed_zone", x_start=1000.0, x_end=1500.0,
                       speed_limit=16.7),
            Bottleneck(kind="incident", x_start=2500.0, x_end=2520.0,
                       t_start=200.0, t_end=260.0),
        ],
        traffic_lights=[TrafficLight(x=1200.0, green=40.0, yellow=3.0,
                                     red=30.0)],
        on_ramps=[OnRamp(x_merge=1500.0)],
    )


def test_lanes_open_before_drop():
    road = _road()
    assert road.lanes_open_at(1500.0, 300.0) == 3


def test_lanes_open_after_drop_when_active():
    road = _road()
    assert road.lanes_open_at(2500.0, 300.0) == 2


def test_lanes_open_after_drop_window_ends():
    road = _road()
    assert road.lanes_open_at(2500.0, 600.0) == 3


def test_is_lane_open():
    road = _road()
    assert road.is_lane_open(2, 2500.0, 300.0) is False
    assert road.is_lane_open(1, 2500.0, 300.0) is True


def test_speed_limit_in_zone():
    road = _road()
    assert road.speed_limit_at(1200.0, 0.0) == 16.7
    assert road.speed_limit_at(500.0, 0.0) == 33.3


def test_incident_ahead():
    road = _road()
    assert road.incident_ahead(2000.0, 220.0) == 2500.0
    assert road.incident_ahead(2000.0, 100.0) is None  # not active yet
    assert road.incident_ahead(2600.0, 220.0) is None  # already passed


def test_bottleneck_active_window():
    b = Bottleneck(kind="speed_zone", x_start=0, x_end=100,
                   speed_limit=10.0, t_start=10.0, t_end=20.0)
    assert b.is_active(15.0) is True
    assert b.is_active(5.0) is False
    assert b.is_active(25.0) is False


def test_bottleneck_validation():
    import pytest

    with pytest.raises(ValueError):
        Bottleneck(kind="lane_drop", x_start=0, x_end=100)  # no lanes_after
    with pytest.raises(ValueError):
        Bottleneck(kind="mystery", x_start=0, x_end=100)


def test_traffic_light_cycle():
    tl = TrafficLight(x=100.0, green=40.0, yellow=3.0, red=30.0)
    assert tl.cycle == 73.0
    assert tl.state_at(0.0) == "green"
    assert tl.state_at(39.9) == "green"
    assert tl.state_at(41.0) == "yellow"
    assert tl.state_at(50.0) == "red"
    assert tl.state_at(73.0) == "green"  # new cycle
    assert tl.time_to_green(50.0) == 23.0
    assert tl.time_to_green(10.0) == 0.0


def test_next_light():
    road = _road()
    assert road.next_light(1000.0).x == 1200.0
    assert road.next_light(1300.0) is None


def test_road_validation():
    import pytest

    with pytest.raises(ValueError):
        Road(length_m=0, n_lanes=2)
    with pytest.raises(ValueError):
        Road(length_m=100, n_lanes=0)
