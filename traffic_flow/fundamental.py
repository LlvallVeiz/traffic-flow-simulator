"""Fundamental diagram of traffic flow (Greenshields model).

The fundamental diagram relates flow ``q`` (veh/h), density ``k``
(veh/km) and space-mean speed ``v`` (km/h) through the identity::

    q = k * v

Greenshields (1935) proposed the first closed form: speed falls
linearly with density,

    v(k) = vf * (1 - k / kj)

where ``vf`` is the free-flow speed and ``kj`` the jam density.
The flow-density curve is then a parabola with its maximum
(capacity) at ``k = kj / 2``, ``v = vf / 2``::

    q_max = vf * kj / 4

References
----------
Greenshields, B. D. (1935). A study of traffic capacity.
Proceedings of the 14th Annual Meeting of the Highway Research
Board, 14, 448-477.
"""

from __future__ import annotations

import math


def greenshields_speed(k: float, vf: float, kj: float) -> float:
    """Speed (same unit as ``vf``) at density ``k`` (Greenshields)."""
    if k <= 0:
        return vf
    if k >= kj:
        return 0.0
    return vf * (1.0 - k / kj)


def greenshields_flow(k: float, vf: float, kj: float) -> float:
    """Flow at density ``k`` (Greenshields parabola)."""
    return k * greenshields_speed(k, vf, kj)


def greenshields_capacity(vf: float, kj: float) -> float:
    """Maximum flow ``vf * kj / 4`` (at ``k = kj / 2``)."""
    return vf * kj / 4.0


def greenshields_critical_density(kj: float) -> float:
    """Density at capacity, ``kj / 2``."""
    return kj / 2.0


def fit_greenshields(
    densities: list[float], speeds: list[float]
) -> dict[str, float]:
    """Least-squares fit of the Greenshields line ``v = vf - (vf/kj) * k``.

    Fits speed as a linear function of density and converts the
    intercept/slope back to ``vf`` and ``kj``.  Returns a dict with
    ``vf``, ``kj``, ``q_max``, ``k_crit``, ``r_squared`` and
    ``n_points``.  Raises ``ValueError`` on degenerate input.
    """
    if len(densities) != len(speeds):
        raise ValueError("densities and speeds must have the same length")
    n = len(densities)
    if n < 3:
        raise ValueError("need at least 3 points to fit the fundamental diagram")
    mean_k = sum(densities) / n
    mean_v = sum(speeds) / n
    s_kk = sum((k - mean_k) ** 2 for k in densities)
    if s_kk == 0:
        raise ValueError("densities have no variance; cannot fit")
    s_kv = sum((k - mean_k) * (v - mean_v) for k, v in zip(densities, speeds))
    slope = s_kv / s_kk
    intercept = mean_v - slope * mean_k
    if intercept <= 0 or slope >= 0:
        raise ValueError(
            "fit did not produce a decreasing speed-density line "
            f"(vf={intercept:.3f}, slope={slope:.3f})"
        )
    vf = intercept
    kj = -vf / slope
    ss_tot = sum((v - mean_v) ** 2 for v in speeds)
    ss_res = sum(
        (v - (intercept + slope * k)) ** 2 for k, v in zip(densities, speeds)
    )
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return {
        "vf": vf,
        "kj": kj,
        "q_max": greenshields_capacity(vf, kj),
        "k_crit": greenshields_critical_density(kj),
        "r_squared": r2,
        "n_points": float(n),
    }


def flow_density_speed_identity(
    flow: float, density: float, speed: float
) -> float:
    """Relative error of ``q = k * v`` (0 when the identity holds exactly)."""
    if density <= 0 or speed <= 0:
        return math.inf if flow != 0 else 0.0
    return abs(flow - density * speed) / (density * speed)
