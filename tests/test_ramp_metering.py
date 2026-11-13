"""Tests for ramp metering (ALINEA feedback law and fixed meter)."""

from traffic_flow.ramp_metering import AlineaMeter, FixedRateMeter


def test_alinea_increases_rate_below_target():
    m = AlineaMeter(target_density=25.0, gain=70.0, initial_rate=900.0)
    new_rate = m.update(20.0)  # density below target
    assert new_rate == 900.0 + 70.0 * (25.0 - 20.0)


def test_alinea_decreases_rate_above_target():
    m = AlineaMeter(target_density=25.0, gain=70.0, initial_rate=900.0)
    new_rate = m.update(30.0)
    assert new_rate == 900.0 + 70.0 * (25.0 - 30.0)


def test_alinea_holds_rate_at_target():
    m = AlineaMeter(target_density=25.0, gain=70.0, initial_rate=900.0)
    assert m.update(25.0) == 900.0


def test_alinea_clamps_to_max():
    m = AlineaMeter(target_density=25.0, gain=70.0, initial_rate=1700.0,
                    rate_max=1800.0)
    assert m.update(0.0) == 1800.0


def test_alinea_clamps_to_min():
    m = AlineaMeter(target_density=25.0, gain=70.0, initial_rate=300.0,
                    rate_min=240.0)
    assert m.update(100.0) == 240.0


def test_alinea_headway_is_3600_over_rate():
    m = AlineaMeter(initial_rate=900.0)
    assert m.headway() == 4.0  # 3600/900 = one vehicle every 4 s
    m.update(0.0)
    assert m.headway() == 3600.0 / m.rate


def test_fixed_rate_meter_ignores_measurement():
    m = FixedRateMeter(rate=600.0)
    assert m.update(5.0) == 600.0
    assert m.update(80.0) == 600.0
    assert m.headway() == 6.0
