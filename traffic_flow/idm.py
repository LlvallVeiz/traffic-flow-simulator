"""Intelligent Driver Model (IDM) car-following model.

The IDM is a time-continuous car-following model introduced by
Treiber, Hennecke and Helbing (2000).  It describes the acceleration
of a vehicle as a function of its own speed, the gap to the vehicle
ahead and the speed difference to that vehicle::

    a = a_max * [1 - (v / v0)**delta - (s_star(v, dv) / s)**2]

    s_star(v, dv) = s0 + v * T + v * dv / (2 * sqrt(a_max * b))

with ``v`` the own speed, ``v0`` the desired (free-flow) speed,
``s`` the bumper-to-bumper gap to the leader, ``dv = v - v_leader``
the approach rate, ``s0`` the minimum (jam) gap, ``T`` the desired
time headway, ``a_max`` the maximum acceleration and ``b`` the
comfortable deceleration.  The model is essentially crash-free for
physically sensible parameters and reproduces free flow, congested
flow and stop-and-go waves.

References
----------
Treiber, M., Hennecke, A., Helbing, D. (2000). Congested traffic
states in empirical observations and microscopic simulations.
Physical Review E, 62(2), 1805-1824. doi:10.1103/PhysRevE.62.1805
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Physical floor on deceleration (m/s^2): emergency braking.  The
#: raw IDM formula diverges to -inf when the gap closes to zero, which
#: would push a vehicle's position to -inf in discrete time; clamping
#: keeps the dynamics physical and the simulation stable.
MAX_DECEL = 9.0


@dataclass(frozen=True)
class IDMParams:
    """Behavioural parameters of one driver-vehicle unit.

    All speeds in m/s, all distances in m, all times in s.

    Attributes
    ----------
    v0:
        Desired (free-flow) speed.
    time_headway:
        Desired net time gap ``T`` to the leader.
    min_gap:
        Minimum bumper-to-bumper gap ``s0`` in a standing queue.
    max_accel:
        Maximum acceleration ``a``.
    comfort_decel:
        Comfortable deceleration ``b``.
    delta:
        Acceleration exponent (4 is the standard value).
    """

    v0: float
    time_headway: float = 1.5
    min_gap: float = 2.0
    max_accel: float = 1.0
    comfort_decel: float = 1.5
    delta: float = 4.0

    def __post_init__(self) -> None:
        if self.v0 <= 0:
            raise ValueError("v0 must be positive")
        if self.time_headway <= 0:
            raise ValueError("time_headway must be positive")
        if self.min_gap < 0:
            raise ValueError("min_gap must be non-negative")
        if self.max_accel <= 0:
            raise ValueError("max_accel must be positive")
        if self.comfort_decel <= 0:
            raise ValueError("comfort_decel must be positive")
        if self.delta <= 0:
            raise ValueError("delta must be positive")


def desired_gap(v: float, dv: float, params: IDMParams) -> float:
    """Desired dynamic gap ``s*`` (m) at speed ``v`` and approach rate ``dv``.

    ``dv = v - v_leader``: positive when closing in on the leader.
    The interaction term ``v * dv / (2 * sqrt(a * b))`` makes the
    driver brake earlier (and harder) when approaching fast.
    """
    sqrt_ab = math.sqrt(params.max_accel * params.comfort_decel)
    s_star = params.min_gap + v * params.time_headway
    s_star += (v * dv) / (2.0 * sqrt_ab)
    return max(s_star, 0.0)


def idm_acceleration(
    v: float,
    v_leader: float | None,
    gap: float | None,
    params: IDMParams,
) -> float:
    """IDM acceleration (m/s^2) for a vehicle at speed ``v``.

    Parameters
    ----------
    v:
        Own speed in m/s (must be >= 0).
    v_leader:
        Speed of the leading vehicle in m/s, or ``None`` when there
        is no leader (free road ahead).
    gap:
        Bumper-to-bumper gap to the leader in m, or ``None`` when
        there is no leader.
    params:
        IDM behavioural parameters.

    Returns
    -------
    Acceleration in m/s^2.  Negative values mean braking.  When
    there is no leader the interaction term vanishes and the
    vehicle accelerates freely towards ``v0``.
    """
    if v < 0:
        raise ValueError("speed v must be >= 0")
    free_term = 1.0 - (v / params.v0) ** params.delta
    if v_leader is None or gap is None:
        return params.max_accel * free_term
    gap = max(gap, 0.0)
    dv = v - v_leader
    s_star = desired_gap(v, dv, params)
    interaction = (s_star / gap) ** 2 if gap > 0 else float("inf")
    accel = params.max_accel * (free_term - interaction)
    # Clamp to emergency braking: the raw formula diverges as the
    # gap closes to zero, which is unphysical in discrete time.
    return max(accel, -MAX_DECEL)


def free_acceleration(v: float, params: IDMParams) -> float:
    """Acceleration on an empty road (no leader)."""
    return idm_acceleration(v, None, None, params)


def equilibrium_gap(v: float, params: IDMParams) -> float:
    """Gap (m) at which a vehicle cruising at speed ``v`` has zero acceleration.

    At equilibrium the leader travels at the same speed (``dv = 0``),
    so ``a = 0`` gives ``s_eq = s*(v, 0) / sqrt(1 - (v/v0)**delta)``.
    Returns ``inf`` at ``v >= v0`` (no finite equilibrium gap exists:
    a vehicle at its desired speed never follows in equilibrium).
    """
    if v >= params.v0:
        return math.inf
    s_star = desired_gap(v, 0.0, params)
    return s_star / math.sqrt(1.0 - (v / params.v0) ** params.delta)


def equilibrium_flow(v: float, vehicle_length: float, params: IDMParams) -> float:
    """Equilibrium flow (veh/h/lane) of a homogeneous stream at speed ``v``.

    Uses the equilibrium gap plus the vehicle length as the space
    headway: ``q = v / (s_eq + L)``.  This is the IDM's own
    fundamental diagram for one lane of identical vehicles.
    """
    gap = equilibrium_gap(v, params)
    if math.isinf(gap):
        return 0.0
    headway = gap + vehicle_length
    if headway <= 0:
        return 0.0
    return 3600.0 * v / headway
