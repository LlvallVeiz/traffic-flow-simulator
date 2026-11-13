"""Ramp metering: ALINEA feedback control and a fixed-rate meter.

ALINEA (Papageorgiou, Hadj-Salem & Blosseville, 1991) is a local
feedback law that keeps the traffic state downstream of a merge near
its critical value by adjusting the on-ramp release rate::

    r(k) = r(k-1) + K_R * (o* - o(k))

where ``r`` is the metering rate (veh/h), ``o(k)`` the measured
downstream occupancy (here: density in veh/km/lane) at control step
``k``, ``o*`` the target (critical) occupancy and ``K_R`` the
regulator gain.  Only one downstream detector is needed, which is
why ALINEA is deployed at hundreds of sites worldwide.

References
----------
Papageorgiou, M., Hadj-Salem, H., Blosseville, J.-M. (1991).
ALINEA: A local feedback control law for on-ramp metering.
Transportation Research Record, 1320, 58-64.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AlineaMeter:
    """ALINEA ramp meter.

    Attributes
    ----------
    target_density:
        Target downstream density ``o*`` (veh/km/lane), normally the
        critical density of the fundamental diagram.
    gain:
        Regulator gain ``K_R`` in (veh/h) per (veh/km/lane).
    rate_min / rate_max:
        Clamp on the metering rate (veh/h).
    cycle:
        Control update interval (s).
    initial_rate:
        Starting metering rate (veh/h).
    """

    target_density: float = 25.0
    gain: float = 70.0
    rate_min: float = 240.0
    rate_max: float = 1800.0
    cycle: float = 20.0
    initial_rate: float = 900.0
    rate: float | None = None

    def __post_init__(self) -> None:
        if self.rate is None:
            self.rate = self.initial_rate

    def update(self, measured_density: float) -> float:
        """Apply one ALINEA step and return the new rate (veh/h)."""
        assert self.rate is not None
        new_rate = self.rate + self.gain * (
            self.target_density - measured_density
        )
        self.rate = max(self.rate_min, min(self.rate_max, new_rate))
        return self.rate

    def headway(self) -> float:
        """Minimum time (s) between two released ramp vehicles."""
        assert self.rate is not None and self.rate > 0
        return 3600.0 / self.rate


@dataclass
class FixedRateMeter:
    """A meter that always releases at one fixed rate (comparison baseline)."""

    rate: float = 900.0

    def update(self, measured_density: float) -> float:
        """Fixed rate, independent of the measurement."""
        return self.rate

    def headway(self) -> float:
        """Minimum time (s) between two released ramp vehicles."""
        return 3600.0 / self.rate
