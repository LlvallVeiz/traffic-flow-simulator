"""MOBIL lane-changing model.

MOBIL (Minimizing Overall Braking Induced by Lane changes) decides
*whether* to change lane; the IDM supplies the longitudinal
accelerations that MOBIL compares.  A lane change happens only when
two criteria hold:

Safety criterion
    The new follower in the target lane must not be forced to brake
    harder than ``b_safe`` after the change::

        a_follower_new_after >= -b_safe

Incentive criterion
    The change must improve the overall acceleration balance::

        (a_ego_new - a_ego) + p * [(a_follower_new_after - a_follower_new)
                                   + (a_follower_old_after - a_follower_old)]
        > threshold + bias

where ``p`` is the politeness factor (how much the driver cares
about the followers' loss), ``threshold`` is the minimum gain that
makes a change worthwhile, and ``bias`` encodes a keep-right
preference (positive when moving left, negative when moving right
in right-hand traffic).

References
----------
Kesting, A., Treiber, M., Helbing, D. (2007). General lane-changing
model MOBIL for car-following models. Transportation Research
Record, 1999, 86-94.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MobilParams:
    """MOBIL parameters (defaults from Kesting et al. 2007)."""

    politeness: float = 0.2
    threshold: float = 0.2  # m/s^2 minimum acceleration gain
    b_safe: float = 4.0  # m/s^2 maximum braking imposed on new follower
    bias_left: float = 0.3  # extra threshold for changing left
    bias_right: float = -0.3  # reduced threshold for changing right


def mobil_should_change(
    a_ego: float,
    a_ego_new: float,
    a_follower_new_before: float,
    a_follower_new_after: float,
    a_follower_old_before: float,
    a_follower_old_after: float,
    params: MobilParams | None = None,
    to_left: bool = True,
) -> bool:
    """Decide whether a discretionary lane change is worthwhile.

    Parameters
    ----------
    a_ego, a_ego_new:
        Ego vehicle's IDM acceleration in the current lane and in
        the target lane.
    a_follower_new_before / a_follower_new_after:
        Acceleration of the follower in the target lane before and
        after the change.
    a_follower_old_before / a_follower_old_after:
        Acceleration of the follower in the current lane before and
        after the change (after the change its leader is the ego
        vehicle's old leader).
    params:
        MOBIL parameters.
    to_left:
        Direction of the change (affects the keep-right bias).

    Returns
    -------
    True when both the safety and the incentive criterion hold.
    """
    params = params or MobilParams()
    # Safety criterion: do not force the new follower into hard braking.
    if a_follower_new_after < -params.b_safe:
        return False
    bias = params.bias_left if to_left else params.bias_right
    own_gain = a_ego_new - a_ego
    others_gain = (a_follower_new_after - a_follower_new_before) + (
        a_follower_old_after - a_follower_old_before
    )
    return own_gain + params.politeness * others_gain > params.threshold + bias


def mobil_incentive(
    a_ego: float,
    a_ego_new: float,
    a_follower_new_before: float,
    a_follower_new_after: float,
    a_follower_old_before: float,
    a_follower_old_after: float,
    politeness: float = 0.2,
) -> float:
    """The MOBIL incentive value (m/s^2); a change is attractive when
    it exceeds ``threshold + bias``."""
    own_gain = a_ego_new - a_ego
    others_gain = (a_follower_new_after - a_follower_new_before) + (
        a_follower_old_after - a_follower_old_before
    )
    return own_gain + politeness * others_gain
