import datetime as dt
import math

import pytest

from atmosfx.core import astro


def utc(*a):
    return dt.datetime(*a, tzinfo=dt.timezone.utc)


def test_julian_date_references():
    assert astro.jd_from_datetime(utc(2000, 1, 1, 12)) == pytest.approx(2451545.0)
    assert astro.jd_from_datetime(utc(1987, 4, 10, 0)) == pytest.approx(2446895.5)      # Meeus ex. 7.a
    assert astro.jd_from_local(2026, 6, 21, 12.0, 5.5) == pytest.approx(astro.jd_from_datetime(utc(2026, 6, 21, 6, 30)))


def test_local_time_rolls_over_midnight():
    assert astro.utc_from_local(2026, 1, 31, 25.0, 0) == utc(2026, 2, 1, 1)
    assert astro.utc_from_local(2026, 1, 1, -1.0, 0) == utc(2025, 12, 31, 23)


def test_gmst_meeus_example():
    assert astro.gmst_deg(2446895.5) == pytest.approx(197.693195, abs=1e-4)             # ex. 12.a


def test_sun_meeus_example_25a():
    s = astro.sun_equatorial(2448908.5)                                                 # 1992 Oct 13.0 TD
    assert s["ra"] == pytest.approx(198.38083, abs=0.01)
    assert s["dec"] == pytest.approx(-7.78507, abs=0.01)
    assert s["distance_au"] == pytest.approx(0.99766, abs=1e-4)


def test_moon_meeus_example_47a():
    m = astro.moon_equatorial(2448724.5)                                                # 1992 Apr 12.0 TD
    assert m["lon"] == pytest.approx(133.162655, abs=0.01)
    assert m["lat"] == pytest.approx(-3.229126, abs=0.01)
    assert m["distance_km"] == pytest.approx(368409.7, abs=60)
    assert m["ra"] == pytest.approx(134.688470, abs=0.02)
    assert m["dec"] == pytest.approx(13.768368, abs=0.02)


def test_moon_phases_at_known_instants():
    new = astro.compute(astro.jd_from_datetime(utc(2024, 1, 11, 11, 57)), 0, 0)         # new moon
    full = astro.compute(astro.jd_from_datetime(utc(2024, 1, 25, 17, 54)), 0, 0)        # full moon
    assert new.moon_fraction < 0.01 and new.moon_phase_name == "new moon"
    assert full.moon_fraction > 0.99 and full.moon_phase_name == "full moon"
    q = astro.compute(astro.jd_from_datetime(utc(2024, 1, 18, 3, 52)), 0, 0)            # first quarter
    assert q.moon_fraction == pytest.approx(0.5, abs=0.03) and q.moon_waxing


def test_sunrise_sunset_equator_and_london():
    e = astro.sun_events(2024, 3, 20, 0, 0.0, 0.0)
    assert e["sunrise"] == pytest.approx(6.07, abs=0.1) and e["sunset"] == pytest.approx(18.15, abs=0.1)
    l = astro.sun_events(2024, 6, 21, 1, 51.5, -0.12)                                   # BST
    assert l["sunrise"] == pytest.approx(4.72, abs=0.1) and l["sunset"] == pytest.approx(21.35, abs=0.1)
    assert l["noon_altitude"] == pytest.approx(61.9, abs=0.3)


def test_polar_day_has_no_sunset():
    e = astro.sun_events(2024, 6, 21, 0, 80.0, 0.0)
    assert e["sunrise"] is None and e["sunset"] is None


def test_horizon_conversion_and_compass():
    # Sun due south at local solar noon at 40N in March: azimuth 180, altitude 90-40+decl
    st = astro.compute_local(2024, 3, 20, 12.0, 0.0, 40.0, 0.0)
    assert st.sun_az_deg == pytest.approx(180.0, abs=3.0)
    assert 49.0 < st.sun_alt_deg < 51.5
    # round trip
    v = astro.altaz_to_enu(33.0, 211.0)
    assert astro.enu_to_altaz(v) == pytest.approx((33.0, 211.0))


def test_north_offset_rotates_the_scene():
    a = astro.enu_to_scene((0.0, 1.0, 0.0), 0.0)
    b = astro.enu_to_scene((0.0, 1.0, 0.0), 90.0)       # scene +Y points east: true north is at scene -X
    assert a == pytest.approx((0, 1, 0), abs=1e-9)
    assert b == pytest.approx((-1, 0, 0), abs=1e-9)


def test_refraction_values():
    assert astro.refraction_deg(0.0) == pytest.approx(0.575, abs=0.03)                  # the standard 34 arcmin at the horizon
    assert astro.refraction_deg(45.0) == pytest.approx(0.0161, abs=0.003)               # ~1 arcmin at 45 degrees
    assert astro.refraction_deg(-5.0) == 0.0


def test_polaris_altitude_equals_latitude():
    from atmosfx.core.stars_data import BY_NAME
    jd = astro.jd_from_datetime(utc(2026, 1, 15, 20))
    lst = astro.local_sidereal_deg(jd, 10.0)
    p = BY_NAME["Polaris"]
    ra, dec = astro.vec_to_radec(astro.mat_vec(astro.precession_matrix(jd), astro.radec_to_vec(p.ra_deg, p.dec_deg)))
    alt, az = astro.enu_to_altaz(astro.equatorial_to_enu(ra, dec, lst, 40.0))
    assert alt == pytest.approx(40.0, abs=1.2)          # within the pole offset (~0.7 degrees)
    assert min(az, 360 - az) < 2.0


def test_precession_is_a_rotation_and_small_near_j2000():
    p = astro.precession_matrix(astro.J2000)
    for i in range(3):
        for j in range(3):
            assert p[i][j] == pytest.approx(1.0 if i == j else 0.0, abs=1e-12)
    p = astro.precession_matrix(astro.J2000 + 36525 * 0.25)     # 25 years: about 0.35 degrees of RA drift
    v = astro.mat_vec(p, (1.0, 0.0, 0.0))
    assert 0.2 < astro.angular_separation_deg(v, (1, 0, 0)) < 0.5


def test_euler_round_trip_matches_blender_xyz_convention():
    for e in [(0.3, 0.5, 0.7), (-1.0, 0.2, 2.5), (2.0, -0.9, -0.4)]:
        m = astro.euler_xyz_to_matrix(e)
        assert astro.euler_xyz(m) == pytest.approx(e, abs=1e-9)
    # Rz(c) Ry(b) Rx(a) acting on +X
    m = astro.euler_xyz_to_matrix((0.0, 0.0, math.pi / 2))
    assert astro.mat_vec(m, (1, 0, 0)) == pytest.approx((0, 1, 0), abs=1e-12)


def test_scene_matrices_are_orthonormal():
    st = astro.compute_local(2026, 10, 26, 22.0, 5.5, 28.6, 77.2, 20.0)
    m = st.scene_from_j2000
    mt = astro.transpose(m)
    prod = astro.mat_mul(m, mt)
    for i in range(3):
        for j in range(3):
            assert prod[i][j] == pytest.approx(1.0 if i == j else 0.0, abs=1e-9)


def test_galactic_centre_direction_and_pole():
    gc = astro.radec_to_vec(266.405, -28.936)
    g = astro.mat_vec(astro.GALACTIC_FROM_J2000, gc)
    assert g == pytest.approx((1.0, 0.0, 0.0), abs=1e-3)
    ngp = astro.radec_to_vec(192.859, 27.128)
    assert astro.mat_vec(astro.GALACTIC_FROM_J2000, ngp) == pytest.approx((0.0, 0.0, 1.0), abs=1e-3)


def test_artistic_moon_phase_and_light_direction():
    ang, waxing, frac = astro.phase_to_angle_deg(0.5)
    assert ang == pytest.approx(0.0, abs=1e-6) and frac == pytest.approx(1.0) and not waxing
    ang, waxing, frac = astro.phase_to_angle_deg(0.25)
    assert ang == pytest.approx(90.0) and frac == pytest.approx(0.5) and waxing
    m = astro.altaz_to_enu(30.0, 200.0)
    # full moon: the light comes from the opposite side
    l = astro.artistic_moon_light_dir(m, 0.0, True)
    assert astro.angular_separation_deg(l, m) == pytest.approx(180.0, abs=0.01)
    # new moon: light from behind the Moon
    l = astro.artistic_moon_light_dir(m, 180.0, True)
    assert astro.angular_separation_deg(l, m) == pytest.approx(0.0, abs=0.01)
    # quarter: a right angle, to the right for a waxing moon, left for a waning moon
    lw = astro.artistic_moon_light_dir(m, 90.0, True)
    ln = astro.artistic_moon_light_dir(m, 90.0, False)
    assert astro.angular_separation_deg(lw, m) == pytest.approx(90.0, abs=0.01)
    assert astro.angular_separation_deg(lw, ln) == pytest.approx(180.0, abs=0.01)


def test_format_hour():
    assert astro.format_hour(6.5) == "06:30"
    assert astro.format_hour(None) == "--:--"
    assert astro.format_hour(23.999) == "00:00"
