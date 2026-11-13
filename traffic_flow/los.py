"""Level of Service (LOS) for basic freeway segments.

LOS grades operating conditions from A (best) to F (worst).  For a
basic freeway segment the Highway Capacity Manual (HCM) uses
*density* as the service measure: ``D = vp / S`` where ``vp`` is the
flow rate (passenger cars per hour per lane) and ``S`` the space-mean
speed.  The thresholds below are the HCM values in metric units
(pc/km/ln), as in HCM 2000 Exhibit 23-3 / HCM 6th edition
Chapter 12 (the imperial values are 11/18/26/35/45 pc/mi/ln).

References
----------
Transportation Research Board (2016). Highway Capacity Manual,
6th edition, Chapter 12 (Basic Freeway Segments).
"""

from __future__ import annotations

#: (upper density bound in pc/km/ln, LOS letter, description)
LOS_THRESHOLDS: list[tuple[float, str, str]] = [
    (7.0, "A", "Free flow - drivers unaffected by other traffic"),
    (11.0, "B", "Reasonably free flow - slight restrictions begin"),
    (16.0, "C", "Stable flow - speed and manoeuvring noticeably constrained"),
    (22.0, "D", "High-density stable flow - freedom to manoeuvre seriously restricted"),
    (28.0, "E", "At or near capacity - unstable, small disturbances cause breakdown"),
    (float("inf"), "F", "Forced flow - stop-and-go, queues, unpredictable travel time"),
]


def los_from_density(density_pc_per_km_per_lane: float) -> str:
    """LOS letter (A-F) for a basic freeway segment at this density.

    Density is in passenger cars per km per lane.  Demand above
    capacity is LOS F; callers should pass the measured density and
    separately flag ``demand > capacity`` when it applies.
    """
    if density_pc_per_km_per_lane < 0:
        raise ValueError("density must be >= 0")
    for bound, letter, _ in LOS_THRESHOLDS:
        if density_pc_per_km_per_lane <= bound:
            return letter
    return "F"  # pragma: no cover - inf bound above always matches


def los_description(letter: str) -> str:
    """One-line description of a LOS letter."""
    for _, code, desc in LOS_THRESHOLDS:
        if code == letter:
            return desc
    raise ValueError(f"unknown LOS letter: {letter!r}")


def los_from_flow_speed(
    flow_pc_per_h_per_lane: float, speed_kmh: float
) -> str:
    """LOS from flow (pc/h/ln) and space-mean speed (km/h): ``D = vp / S``."""
    if speed_kmh <= 0:
        return "F"
    density = flow_pc_per_h_per_lane / speed_kmh
    return los_from_density(density)
