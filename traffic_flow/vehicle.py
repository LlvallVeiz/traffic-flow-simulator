"""Vehicle types and driver profiles.

A vehicle is a driver-vehicle unit: a physical type (car, truck, bus)
fixes its length and its base dynamic limits, while a driver profile
(aggressive, normal, cautious) scales the IDM behavioural parameters.
The combination yields the heterogeneous traffic stream that makes
multi-lane simulation interesting: trucks are long and slow, cautious
drivers keep larger time gaps, aggressive drivers accept smaller ones.

Parameter values are chosen inside the ranges reported for the IDM in
Treiber & Kesting (2013): ``a`` in [0.5, 2.5] m/s^2, ``b`` in
[1, 3] m/s^2, ``T`` in [0.8, 2.0] s, ``s0`` in [1, 3] m.  They are
the simulator's calibration, not claimed measurements of a specific
real road.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .idm import IDMParams

# ---------------------------------------------------------------------------
# Vehicle types
# ---------------------------------------------------------------------------

#: Base parameters per vehicle type: length (m), desired speed (m/s),
#: max acceleration (m/s^2), comfortable deceleration (m/s^2),
#: desired time headway (s), minimum gap (m).
VEHICLE_TYPES = {
    "car": {
        "length": 4.5,
        "v0": 33.3,  # 120 km/h
        "max_accel": 1.4,
        "comfort_decel": 2.0,
        "time_headway": 1.2,
        "min_gap": 2.0,
    },
    "truck": {
        "length": 12.0,
        "v0": 22.2,  # 80 km/h
        "max_accel": 0.8,
        "comfort_decel": 1.5,
        "time_headway": 1.6,
        "min_gap": 2.5,
    },
    "bus": {
        "length": 11.0,
        "v0": 25.0,  # 90 km/h
        "max_accel": 1.0,
        "comfort_decel": 1.8,
        "time_headway": 1.5,
        "min_gap": 2.5,
    },
}

#: Driver profiles scale the base parameters of the vehicle type.
#: ``v0_factor`` scales the desired speed, ``T_factor`` the time
#: headway and ``a_factor`` the maximum acceleration.
DRIVER_PROFILES = {
    "aggressive": {"v0_factor": 1.10, "T_factor": 0.70, "a_factor": 1.40},
    "normal": {"v0_factor": 1.00, "T_factor": 1.00, "a_factor": 1.00},
    "cautious": {"v0_factor": 0.90, "T_factor": 1.50, "a_factor": 0.75},
}

#: Default traffic mix (fraction of each vehicle type).
DEFAULT_MIX = {"car": 0.80, "truck": 0.12, "bus": 0.08}

#: Default driver mix (fraction of each profile).
DEFAULT_DRIVER_MIX = {"aggressive": 0.20, "normal": 0.60, "cautious": 0.20}


def make_idm_params(
    vehicle_type: str,
    driver_profile: str = "normal",
    speed_limit: float | None = None,
    jitter: float = 0.0,
    rng: random.Random | None = None,
) -> IDMParams:
    """Build IDM parameters for a (type, profile) combination.

    Parameters
    ----------
    vehicle_type:
        One of ``"car"``, ``"truck"``, ``"bus"``.
    driver_profile:
        One of ``"aggressive"``, ``"normal"``, ``"cautious"``.
    speed_limit:
        Road speed limit (m/s); the desired speed is capped at it.
    jitter:
        Relative random spread applied to ``v0`` and ``T``
        (e.g. 0.05 = +/-5 %).  Needs ``rng`` to have an effect.
    rng:
        Random generator used for the jitter.
    """
    if vehicle_type not in VEHICLE_TYPES:
        raise ValueError(f"unknown vehicle type: {vehicle_type!r}")
    if driver_profile not in DRIVER_PROFILES:
        raise ValueError(f"unknown driver profile: {driver_profile!r}")
    base = VEHICLE_TYPES[vehicle_type]
    prof = DRIVER_PROFILES[driver_profile]
    v0 = base["v0"] * prof["v0_factor"]
    if speed_limit is not None:
        v0 = min(v0, speed_limit)
    time_headway = base["time_headway"] * prof["T_factor"]
    max_accel = base["max_accel"] * prof["a_factor"]
    if jitter and rng is not None:
        v0 *= 1.0 + rng.uniform(-jitter, jitter)
        time_headway *= 1.0 + rng.uniform(-jitter, jitter)
    return IDMParams(
        v0=v0,
        time_headway=time_headway,
        min_gap=base["min_gap"],
        max_accel=max_accel,
        comfort_decel=base["comfort_decel"],
    )


def draw_type(rng: random.Random, mix: dict[str, float] | None = None) -> str:
    """Draw a vehicle type from a mix (fractions must sum to ~1)."""
    mix = mix or DEFAULT_MIX
    r = rng.random()
    acc = 0.0
    for kind, frac in mix.items():
        acc += frac
        if r <= acc:
            return kind
    return list(mix)[-1]


def draw_profile(rng: random.Random, mix: dict[str, float] | None = None) -> str:
    """Draw a driver profile from a mix (fractions must sum to ~1)."""
    mix = mix or DEFAULT_DRIVER_MIX
    r = rng.random()
    acc = 0.0
    for name, frac in mix.items():
        acc += frac
        if r <= acc:
            return name
    return list(mix)[-1]


@dataclass
class Vehicle:
    """One simulated vehicle (a driver-vehicle unit).

    ``x`` is the position of the front bumper (m from the road start),
    ``v`` the speed (m/s).  ``entry_time`` / ``exit_time`` are used for
    travel-time statistics; ``entered_via`` is ``"main"`` or ``"ramp"``.
    """

    id: int
    kind: str
    profile: str
    length: float
    params: IDMParams
    lane: int = 0
    x: float = 0.0
    v: float = 0.0
    entry_time: float = 0.0
    exit_time: float | None = None
    entered_via: str = "main"
    lane_changes: int = 0
    accel: float = field(default=0.0, repr=False)

    @property
    def rear_x(self) -> float:
        """Position of the rear bumper."""
        return self.x - self.length

    @property
    def speed_kmh(self) -> float:
        """Speed in km/h (display unit)."""
        return self.v * 3.6

    def free_flow_travel_time(self, road_length: float) -> float:
        """Travel time (s) if the vehicle cruised at its desired speed."""
        return road_length / self.params.v0


def create_vehicle(
    vehicle_id: int,
    rng: random.Random,
    *,
    kind: str | None = None,
    profile: str | None = None,
    mix: dict[str, float] | None = None,
    driver_mix: dict[str, float] | None = None,
    speed_limit: float | None = None,
    jitter: float = 0.05,
    lane: int = 0,
    x: float = 0.0,
    v: float = 0.0,
    entry_time: float = 0.0,
    entered_via: str = "main",
) -> Vehicle:
    """Create a vehicle with randomly drawn type/profile (seeded ``rng``)."""
    kind = kind or draw_type(rng, mix)
    profile = profile or draw_profile(rng, driver_mix)
    params = make_idm_params(
        kind, profile, speed_limit=speed_limit, jitter=jitter, rng=rng
    )
    return Vehicle(
        id=vehicle_id,
        kind=kind,
        profile=profile,
        length=VEHICLE_TYPES[kind]["length"],
        params=params,
        lane=lane,
        x=x,
        v=v,
        entry_time=entry_time,
        entered_via=entered_via,
    )
