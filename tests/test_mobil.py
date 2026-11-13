"""Tests for the MOBIL lane-changing model."""

from traffic_flow.mobil import (
    MobilParams,
    mobil_incentive,
    mobil_should_change,
)

P = MobilParams(politeness=0.2, threshold=0.2, b_safe=4.0)


def test_no_gain_no_change():
    # Same acceleration in both lanes: no reason to change.
    assert not mobil_should_change(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, P)


def test_clear_gain_changes_lane():
    # Ego gains 2 m/s^2, followers unaffected.
    assert mobil_should_change(0.0, 2.0, 1.0, 1.0, 1.0, 1.0, P)


def test_unsafe_for_new_follower_blocks_change():
    # New follower would have to brake at -5 m/s^2 (> b_safe).
    assert not mobil_should_change(0.0, 2.0, 1.0, -5.0, 1.0, 1.0, P)


def test_safe_limit_exactly_at_b_safe_allowed():
    assert mobil_should_change(0.0, 2.0, 1.0, -4.0, 1.0, 1.0, P)


def test_politeness_blocks_selfish_change():
    # Ego gains 0.9, but both followers lose 2.0 each.
    # Selfish (p=0): 0.9 > 0.2 + 0.3 (bias) -> change.
    # Polite (p=1): 0.9 - 4.0 < 0.5 -> no change.
    selfish = MobilParams(politeness=0.0, threshold=0.2, b_safe=4.0)
    polite = MobilParams(politeness=1.0, threshold=0.2, b_safe=4.0)
    assert mobil_should_change(0.0, 0.9, 1.0, -1.0, 1.0, -1.0, selfish)
    assert not mobil_should_change(0.0, 0.9, 1.0, -1.0, 1.0, -1.0, polite)


def test_keep_right_bias():
    # A marginal gain (0.35) is enough to move right but not left.
    assert mobil_should_change(0.0, 0.35, 1.0, 1.0, 1.0, 1.0, P,
                                to_left=False)
    assert not mobil_should_change(0.0, 0.35, 1.0, 1.0, 1.0, 1.0, P,
                                   to_left=True)


def test_incentive_value_hand_computed():
    # own gain 1.0, followers: new +0.5, old -0.5 -> net others 0.
    val = mobil_incentive(0.0, 1.0, 0.0, 0.5, 0.0, -0.5, politeness=0.2)
    assert val == 1.0 + 0.2 * 0.0


def test_incentive_counts_followers():
    val = mobil_incentive(1.0, 2.0, 1.0, 0.0, 2.0, 2.0, politeness=0.5)
    # own +1.0, others (0-1) + (2-2) = -1.0 -> 1.0 + 0.5*(-1) = 0.5
    assert val == 0.5


def test_threshold_boundary():
    # Gain exactly at threshold does not trigger (strict inequality).
    assert not mobil_should_change(0.0, 0.2, 1.0, 1.0, 1.0, 1.0,
                                   MobilParams(politeness=0.0, threshold=0.2,
                                               b_safe=4.0, bias_left=0.0))
    assert mobil_should_change(0.0, 0.21, 1.0, 1.0, 1.0, 1.0,
                               MobilParams(politeness=0.0, threshold=0.2,
                                           b_safe=4.0, bias_left=0.0))
