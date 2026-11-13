"""Traffic demand: time-varying inflow profiles.

Demand is a piecewise-constant inflow rate (vehicles per hour) that
can follow a daily pattern -- e.g. a low night flow, a morning peak,
a midday plateau and an evening peak.  Vehicle arrivals within each
interval follow a Poisson process (exponential inter-arrival times),
which is the standard assumption for uncoordinated arrivals at a
freeway entry.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


@dataclass
class DemandInterval:
    """One constant-rate interval: [t_start, t_end) at ``rate_veh_per_h``."""

    t_start: float
    t_end: float
    rate_veh_per_h: float

    def __post_init__(self) -> None:
        if self.t_end <= self.t_start:
            raise ValueError("t_end must be > t_start")
        if self.rate_veh_per_h < 0:
            raise ValueError("rate must be >= 0")

    @property
    def duration(self) -> float:
        """Length of the interval in seconds."""
        return self.t_end - self.t_start

    @property
    def expected_vehicles(self) -> float:
        """Expected number of arrivals in this interval."""
        return self.rate_veh_per_h * self.duration / 3600.0


@dataclass
class DemandProfile:
    """A piecewise-constant demand profile over the simulation horizon."""

    intervals: list[DemandInterval] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.intervals = sorted(self.intervals, key=lambda i: i.t_start)

    def rate_at(self, t: float) -> float:
        """Inflow rate (veh/h) at time ``t`` (0 outside the profile)."""
        for iv in self.intervals:
            if iv.t_start <= t < iv.t_end:
                return iv.rate_veh_per_h
        return 0.0

    @property
    def total_expected(self) -> float:
        """Expected total number of arrivals over the whole profile."""
        return sum(iv.expected_vehicles for iv in self.intervals)

    @classmethod
    def constant(cls, rate_veh_per_h: float, duration: float) -> "DemandProfile":
        """A single constant-rate profile."""
        return cls([DemandInterval(0.0, duration, rate_veh_per_h)])

    @classmethod
    def rush_hour(
        cls,
        base_rate: float,
        peak_rate: float,
        peak_start: float,
        peak_end: float,
        duration: float,
    ) -> "DemandProfile":
        """Base flow with one peak window (e.g. a morning rush hour)."""
        intervals = []
        if peak_start > 0:
            intervals.append(DemandInterval(0.0, peak_start, base_rate))
        intervals.append(DemandInterval(peak_start, peak_end, peak_rate))
        if peak_end < duration:
            intervals.append(DemandInterval(peak_end, duration, base_rate))
        return cls(intervals)

    @classmethod
    def morning_evening(
        cls,
        night_rate: float,
        morning_peak: float,
        midday_rate: float,
        evening_peak: float,
        duration: float = 86400.0,
    ) -> "DemandProfile":
        """A full-day profile: night, morning peak, midday, evening peak.

        Peaks are 07:00-09:00 and 17:00-19:00; the remaining hours
        use ``midday_rate`` between the peaks and ``night_rate``
        outside 06:00-20:00.
        """
        h = 3600.0
        intervals = [
            DemandInterval(0.0, 6 * h, night_rate),
            DemandInterval(6 * h, 7 * h, midday_rate),
            DemandInterval(7 * h, 9 * h, morning_peak),
            DemandInterval(9 * h, 17 * h, midday_rate),
            DemandInterval(17 * h, 19 * h, evening_peak),
            DemandInterval(19 * h, 20 * h, midday_rate),
            DemandInterval(20 * h, duration, night_rate),
        ]
        return cls(intervals)


class ArrivalGenerator:
    """Generates Poisson arrivals for a demand profile.

    ``next_arrival(t)`` returns the time of the next arrival at or
    after ``t``.  The generator is seeded, so a run is reproducible.
    """

    def __init__(self, profile: DemandProfile, rng: random.Random):
        self.profile = profile
        self.rng = rng

    def next_arrival(self, t: float) -> float | None:
        """Next arrival time >= ``t`` (``None`` if no more demand)."""
        rate = self.profile.rate_at(t)
        if rate <= 0:
            # Skip ahead to the next interval with demand.
            for iv in self.profile.intervals:
                if iv.t_end > t and iv.rate_veh_per_h > 0:
                    t = max(t, iv.t_start)
                    rate = iv.rate_veh_per_h
                    break
            else:
                return None
        lam = rate / 3600.0  # arrivals per second
        gap = -math.log(1.0 - self.rng.random()) / lam
        arrival = t + gap
        # If the gap crosses into a different rate interval, restart
        # from the boundary so the rate change is respected.
        if self.profile.rate_at(arrival) != rate:
            for iv in self.profile.intervals:
                if iv.t_start <= t < iv.t_end:
                    return self.next_arrival(iv.t_end)
        return arrival
