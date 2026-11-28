"""Solar eclipse geometry and the lightning flash schedule (pure Python)."""
import math

import pytest

from atmosfx.core import lightning, physics


def test_eclipse_visible_fraction():
    assert physics.eclipse_visible_fraction(0.0) == 1.0
    assert physics.eclipse_visible_fraction(1.0) == pytest.approx(0.0, abs=1e-6)      # total (k > 1)
    # magnitude 0.5: the Moon's limb reaches the Sun's centre -> a bit under half the disc covered
    assert 0.55 < physics.eclipse_visible_fraction(0.5) < 0.65
    vals = [physics.eclipse_visible_fraction(m / 20) for m in range(21)]
    assert all(a >= b - 1e-12 for a, b in zip(vals, vals[1:])), "more magnitude never uncovers the Sun"
    # annular (Moon smaller): a ring of 1 - k^2 stays visible at central alignment
    assert physics.eclipse_visible_fraction(1.0, k=0.95) == pytest.approx(1 - 0.95 ** 2, abs=1e-6)


def test_eclipse_offset():
    assert physics.eclipse_offset(0.0) == pytest.approx(2.03)        # limbs just touching
    assert physics.eclipse_offset(1.0) == pytest.approx(0.03)


def test_eclipse_dims_lamp_and_sky():
    from atmosfx.core.skyview import SkyParams, compute_view
    day = compute_view(SkyParams(sun_elevation=50.0))
    half = compute_view(SkyParams(sun_elevation=50.0, eclipse=0.6))
    total = compute_view(SkyParams(sun_elevation=50.0, eclipse=1.0))
    assert half.sun_lamp_strength == pytest.approx(day.sun_lamp_strength * half.eclipse_visible, rel=1e-6)
    assert total.sun_lamp_strength == 0.0 and total.corona > 0.0 and max(total.eclipse_glow) > 0.0
    assert total.sky_strength == pytest.approx(day.sky_strength * physics.ECLIPSE_TOTALITY_SKY, rel=1e-6)
    assert day.eclipse_offset == 10.0 and day.corona == 0.0 and day.eclipse_glow == (0.0, 0.0, 0.0)


def test_lightning_schedule_is_deterministic_and_paced():
    a = lightning.schedule(6.0, 1, 24 * 600 + 1, 24.0, seed=3)      # 10 minutes at 6/min
    b = lightning.schedule(6.0, 1, 24 * 600 + 1, 24.0, seed=3)
    assert [(f.start_frame, f.strokes) for f in a] == [(f.start_frame, f.strokes) for f in b]
    assert 35 <= len(a) <= 90, len(a)                                  # ~60 expected (Poisson)
    assert all(lightning.STROKES_MIN <= len(f.strokes) <= lightning.STROKES_MAX for f in a)
    assert all(math.hypot(f.offset[0], f.offset[1]) <= 1.0 for f in a)
    assert lightning.schedule(0.0, 1, 1000, 24.0, 1) == []
    assert lightning.schedule(6.0, 1, 24 * 600 + 1, 24.0, seed=4) != a


def test_lightning_keys_are_dark_between_flashes():
    fl = [lightning.Flash(10, [(10, 1.0), (12, 0.5)]), lightning.Flash(40, [(40, 1.0)])]
    keys = dict(lightning.keyframes(fl, 100.0))
    assert keys[9] == 0.0 and keys[10] == 100.0 and keys[11] == pytest.approx(30.0) and keys[12] == 50.0
    assert keys[14] == 0.0 and keys[39] == 0.0 and keys[42] == 0.0
