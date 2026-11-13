"""Tests for trajectory recording and the independent travel-time check."""

import pytest

from traffic_flow.trajectory import (
    TrajectoryRecorder,
    travel_time_from_samples,
)


def _recorder_with_run(tmp_path):
    rec = TrajectoryRecorder(sample_dt=1.0)
    rec.record_entry(1, "car", "normal", 0.0, "main", 30.0)
    rec.record_entry(2, "truck", "normal", 5.0, "main", 22.0)
    rec.record_exit(1, 100.0, 2)
    rec.samples = [
        {"t": 0.0, "vehicle_id": 1, "x": 0.0, "lane": 0, "v": 30.0, "kind": "car"},
        {"t": 50.0, "vehicle_id": 1, "x": 1500.0, "lane": 0, "v": 30.0, "kind": "car"},
        {"t": 100.0, "vehicle_id": 1, "x": 3000.0, "lane": 0, "v": 30.0, "kind": "car"},
    ]
    return rec


def test_entry_exit_events(tmp_path):
    rec = _recorder_with_run(tmp_path)
    assert len(rec.events) == 2
    assert rec.events[0]["completed"] is True
    assert rec.events[0]["exit_time"] == 100.0
    assert rec.events[0]["lane_changes"] == 2
    assert rec.events[1]["completed"] is False
    assert rec.events[1]["exit_time"] is None


def test_exit_without_entry_raises():
    rec = TrajectoryRecorder()
    with pytest.raises(KeyError):
        rec.record_exit(99, 10.0, 0)


def test_travel_time_from_samples_exact():
    samples = [
        {"t": 0.0, "vehicle_id": 1, "x": 0.0, "lane": 0, "v": 30.0, "kind": "car"},
        {"t": 50.0, "vehicle_id": 1, "x": 1500.0, "lane": 0, "v": 30.0, "kind": "car"},
        {"t": 100.0, "vehicle_id": 1, "x": 3000.0, "lane": 0, "v": 30.0, "kind": "car"},
    ]
    assert travel_time_from_samples(samples, 1, 3000.0) == pytest.approx(100.0)


def test_travel_time_from_samples_interpolates_exit():
    # Samples every 10 s; the vehicle crosses x=3000 between t=90 and 100.
    samples = [
        {"t": 0.0, "vehicle_id": 1, "x": 0.0, "lane": 0, "v": 30.0, "kind": "car"},
        {"t": 90.0, "vehicle_id": 1, "x": 2700.0, "lane": 0, "v": 30.0, "kind": "car"},
        {"t": 100.0, "vehicle_id": 1, "x": 3000.0, "lane": 0, "v": 30.0, "kind": "car"},
    ]
    assert travel_time_from_samples(samples, 1, 3000.0) == pytest.approx(100.0)


def test_travel_time_none_when_never_exits():
    samples = [
        {"t": 0.0, "vehicle_id": 1, "x": 0.0, "lane": 0, "v": 30.0, "kind": "car"},
        {"t": 50.0, "vehicle_id": 1, "x": 1000.0, "lane": 0, "v": 30.0, "kind": "car"},
    ]
    assert travel_time_from_samples(samples, 1, 3000.0) is None
    assert travel_time_from_samples(samples, 99, 3000.0) is None


def test_samples_csv_round_trip(tmp_path):
    rec = _recorder_with_run(tmp_path)
    path = str(tmp_path / "traj.csv")
    rec.samples_to_csv(path)
    back = TrajectoryRecorder.samples_from_csv(path)
    assert back == rec.samples


def test_events_json_round_trip(tmp_path):
    rec = _recorder_with_run(tmp_path)
    path = str(tmp_path / "events.json")
    rec.events_to_json(path)
    back = TrajectoryRecorder.events_from_json(path)
    assert back == rec.events


def test_maybe_sample_respects_sample_dt():
    class FakeVeh:
        id, x, lane, v, kind = 1, 0.0, 0, 10.0, "car"

    rec = TrajectoryRecorder(sample_dt=2.0)
    rec.maybe_sample(0.0, [FakeVeh()])
    rec.maybe_sample(1.0, [FakeVeh()])
    rec.maybe_sample(2.0, [FakeVeh()])
    assert len(rec.samples) == 2  # t=0 and t=2 only
