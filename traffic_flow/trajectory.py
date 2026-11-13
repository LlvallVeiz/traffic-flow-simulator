"""Trajectory recording and event logging.

The recorder stores two things:

* **samples** -- periodic snapshots ``(t, vehicle_id, x, lane, v, kind)``
  used for space-time diagrams, shockwave tracking and the
  independent travel-time check;
* **events** -- one record per vehicle with its entry/exit times,
  used for travel time, delay and throughput statistics.

Both are plain data (lists of dicts) so they can be written to CSV /
JSON and re-analysed later by the ``analyze`` CLI subcommand without
re-running the simulation.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field


@dataclass
class TrajectoryRecorder:
    """Collects trajectory samples and vehicle entry/exit events."""

    sample_dt: float = 2.0
    samples: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    _next_sample_t: float = field(default=0.0, repr=False)

    def record_entry(self, vehicle_id: int, kind: str, profile: str,
                     entry_time: float, entered_via: str,
                     desired_speed: float, entry_x: float = 0.0) -> None:
        """Log that a vehicle entered the road."""
        self.events.append({
            "vehicle_id": vehicle_id,
            "kind": kind,
            "profile": profile,
            "entry_time": entry_time,
            "exit_time": None,
            "entered_via": entered_via,
            "entry_x": entry_x,
            "desired_speed_mps": desired_speed,
            "lane_changes": 0,
            "completed": False,
        })

    def record_exit(self, vehicle_id: int, exit_time: float,
                    lane_changes: int) -> None:
        """Log that a vehicle left the road (front bumper passed the end)."""
        for ev in self.events:
            if ev["vehicle_id"] == vehicle_id:
                ev["exit_time"] = exit_time
                ev["lane_changes"] = lane_changes
                ev["completed"] = True
                return
        raise KeyError(f"no entry event for vehicle {vehicle_id}")

    def maybe_sample(self, t: float, vehicles) -> None:
        """Record one snapshot of all vehicles if the sample time is due."""
        if t + 1e-9 < self._next_sample_t:
            return
        self._next_sample_t = t + self.sample_dt
        for veh in vehicles:
            self.samples.append({
                "t": round(t, 3),
                "vehicle_id": veh.id,
                "x": round(veh.x, 3),
                "lane": veh.lane,
                "v": round(veh.v, 3),
                "kind": veh.kind,
            })

    # -- persistence ------------------------------------------------------

    def samples_to_csv(self, path: str) -> None:
        """Write samples to CSV (t, vehicle_id, x, lane, v, kind)."""
        with open(path, "w", newline="") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=["t", "vehicle_id", "x", "lane", "v", "kind"]
            )
            writer.writeheader()
            writer.writerows(self.samples)

    def events_to_json(self, path: str) -> None:
        """Write events to JSON."""
        with open(path, "w") as fh:
            json.dump(self.events, fh, indent=2)

    @staticmethod
    def samples_from_csv(path: str) -> list[dict]:
        """Read samples back from a CSV file."""
        with open(path, newline="") as fh:
            rows = list(csv.DictReader(fh))
        out = []
        for r in rows:
            out.append({
                "t": float(r["t"]),
                "vehicle_id": int(r["vehicle_id"]),
                "x": float(r["x"]),
                "lane": int(r["lane"]),
                "v": float(r["v"]),
                "kind": r["kind"],
            })
        return out

    @staticmethod
    def events_from_json(path: str) -> list[dict]:
        """Read events back from a JSON file."""
        with open(path) as fh:
            return json.load(fh)


def travel_time_from_samples(
    samples: list[dict], vehicle_id: int, road_length: float
) -> float | None:
    """Travel time (s) of one vehicle, recomputed from raw samples only.

    This is the *independent* implementation used for verification:
    it uses nothing but the sampled trajectory.  Entry is the first
    sample; exit is estimated by linear interpolation between the
    last sample before the road end and the first sample at/after it,
    or -- since exited vehicles are no longer sampled -- by
    extrapolating the last sample at its sampled speed.
    Returns ``None`` when the vehicle never reaches the end.
    """
    rows = [s for s in samples if s["vehicle_id"] == vehicle_id]
    if not rows:
        return None
    rows.sort(key=lambda s: s["t"])
    t_entry = rows[0]["t"]
    prev = rows[0]
    for row in rows[1:]:
        if row["x"] >= road_length:
            # Interpolate the crossing time of x = road_length.
            dx = row["x"] - prev["x"]
            if dx <= 0:
                return row["t"] - t_entry
            frac = (road_length - prev["x"]) / dx
            t_exit = prev["t"] + frac * (row["t"] - prev["t"])
            return t_exit - t_entry
        prev = row
    # No sample reaches the end (exited vehicles are not sampled):
    # extrapolate from the last sample at its sampled speed -- but
    # only if the vehicle is within ~3 s of travel of the end
    # (otherwise it genuinely did not finish in the window).
    last = rows[-1]
    if last["v"] > 0 and last["x"] < road_length:
        if (road_length - last["x"]) <= 3.0 * last["v"]:
            return last["t"] + (road_length - last["x"]) / last["v"] - t_entry
    return None
