"""Road geometry: lanes, bottlenecks, traffic lights and on-ramps.

A road is a straight stretch of ``length_m`` metres with ``n_lanes``
lanes (lane 0 is the rightmost / slowest lane).  Bottlenecks change
the number of open lanes or the speed limit over a section and a time
window; a traffic light is a point obstacle with a green/yellow/red
cycle; an on-ramp injects vehicles at a merge point.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Bottleneck:
    """A local capacity restriction.

    kind:
        ``"lane_drop"`` -- lanes close downstream of ``x_start``
        (``lanes_after`` lanes stay open); ``"speed_zone"`` -- a
        reduced speed limit between ``x_start`` and ``x_end``;
        ``"incident"`` -- a full blockage of all lanes between
        ``x_start`` and ``x_end`` (e.g. a crash).
    t_start / t_end:
        Time window (s) during which the bottleneck is active.
        ``t_end=None`` means active until the end of the run.
    """

    kind: str
    x_start: float
    x_end: float
    lanes_after: int | None = None
    speed_limit: float | None = None
    t_start: float = 0.0
    t_end: float | None = None
    label: str = ""

    def __post_init__(self) -> None:
        if self.kind not in ("lane_drop", "speed_zone", "incident"):
            raise ValueError(f"unknown bottleneck kind: {self.kind!r}")
        if self.x_end < self.x_start:
            raise ValueError("x_end must be >= x_start")
        if self.kind == "lane_drop" and self.lanes_after is None:
            raise ValueError("lane_drop needs lanes_after")

    def is_active(self, t: float) -> bool:
        """True when the bottleneck restricts traffic at time ``t``."""
        if t < self.t_start:
            return False
        if self.t_end is not None and t >= self.t_end:
            return False
        return True

    def blocks_lane(self, lane: int, x: float, t: float) -> bool:
        """True when a vehicle in ``lane`` at ``x`` is blocked by this bottleneck."""
        if not self.is_active(t):
            return False
        if self.kind == "incident":
            return self.x_start <= x <= self.x_end
        if self.kind == "lane_drop":
            return (
                lane >= (self.lanes_after or 0)
                and x >= self.x_start
            )
        return False


@dataclass
class TrafficLight:
    """A simple fixed-time traffic light at one position.

    The cycle is green -> yellow -> red -> green ... starting with
    green at ``t = 0``.  Durations are in seconds.
    """

    x: float
    green: float = 40.0
    yellow: float = 3.0
    red: float = 30.0
    label: str = ""

    @property
    def cycle(self) -> float:
        """Total cycle length (s)."""
        return self.green + self.yellow + self.red

    def state_at(self, t: float) -> str:
        """``"green"``, ``"yellow"`` or ``"red"`` at time ``t``."""
        phase = t % self.cycle
        if phase < self.green:
            return "green"
        if phase < self.green + self.yellow:
            return "yellow"
        return "red"

    def time_to_green(self, t: float) -> float:
        """Seconds until the next green phase starts (0 if green now)."""
        if self.state_at(t) == "green":
            return 0.0
        phase = t % self.cycle
        return self.cycle - phase


@dataclass
class OnRamp:
    """An on-ramp that merges into lane 0 at ``x_merge``.

    ``merge_length`` is the length of the acceleration/merge zone
    (m) upstream of the merge point.  Ramp vehicles wait at the
    merge point until a gap in lane 0 is acceptable.
    """

    x_merge: float
    merge_length: float = 200.0
    label: str = ""
    queue: int = field(default=0, repr=False)


@dataclass
class Road:
    """A straight multi-lane road with bottlenecks, lights and ramps."""

    length_m: float
    n_lanes: int
    speed_limit: float = 33.3  # m/s (120 km/h)
    bottlenecks: list[Bottleneck] = field(default_factory=list)
    traffic_lights: list[TrafficLight] = field(default_factory=list)
    on_ramps: list[OnRamp] = field(default_factory=list)
    name: str = "road"

    def __post_init__(self) -> None:
        if self.length_m <= 0:
            raise ValueError("length_m must be positive")
        if self.n_lanes < 1:
            raise ValueError("n_lanes must be >= 1")
        if self.speed_limit <= 0:
            raise ValueError("speed_limit must be positive")

    def lanes_open_at(self, x: float, t: float) -> int:
        """Number of open lanes at position ``x`` and time ``t``."""
        lanes = self.n_lanes
        for b in self.bottlenecks:
            if b.kind == "lane_drop" and b.is_active(t) and x >= b.x_start:
                lanes = min(lanes, b.lanes_after or lanes)
        return lanes

    def is_lane_open(self, lane: int, x: float, t: float) -> bool:
        """True when ``lane`` is open at ``x`` and ``t``."""
        return lane < self.lanes_open_at(x, t)

    def speed_limit_at(self, x: float, t: float) -> float:
        """Effective speed limit (m/s) at ``x`` and ``t``."""
        limit = self.speed_limit
        for b in self.bottlenecks:
            if (
                b.kind == "speed_zone"
                and b.is_active(t)
                and b.x_start <= x <= b.x_end
                and b.speed_limit is not None
            ):
                limit = min(limit, b.speed_limit)
        return limit

    def incident_ahead(self, x: float, t: float) -> float | None:
        """Position of the nearest active incident downstream of ``x``.

        Returns ``None`` when no incident blocks the road ahead.
        """
        nearest: float | None = None
        for b in self.bottlenecks:
            if b.kind == "incident" and b.is_active(t) and b.x_end > x:
                if nearest is None or b.x_start < nearest:
                    nearest = b.x_start
        return nearest

    def next_light(self, x: float) -> TrafficLight | None:
        """The next traffic light downstream of ``x`` (or ``None``)."""
        ahead = [tl for tl in self.traffic_lights if tl.x > x]
        if not ahead:
            return None
        return min(ahead, key=lambda tl: tl.x)
