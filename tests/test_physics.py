import math

import pytest

from atmosfx.core import physics as ph


def test_koschmieder_round_trip_and_known_value():
    assert ph.koschmieder_extinction(1000.0) == pytest.approx(0.003912, rel=1e-3)
    s = ph.koschmieder_extinction(5000.0)
    assert ph.visibility_from_extinction(s) == pytest.approx(5000.0)
    # transmittance at the visibility distance is the 2 % contrast threshold
    assert ph.transmittance(s, 5000.0) == pytest.approx(0.02)
    with pytest.raises(ValueError):
        ph.koschmieder_extinction(0)


def test_height_density_and_visibility_grows_with_height():
    assert ph.height_density(1.0, 0.0, 0.0, 100.0) == pytest.approx(1.0)
    assert ph.height_density(1.0, 100.0, 0.0, 100.0) == pytest.approx(math.exp(-1))
    assert ph.height_density(1.0, -50.0, 0.0, 100.0) == 1.0            # below the base: full density
    v0 = ph.horizontal_visibility_at(1000.0, 0.0, 0.0, 100.0)
    v1 = ph.horizontal_visibility_at(1000.0, 300.0, 0.0, 100.0)
    assert v0 == pytest.approx(1000.0) and v1 > 15 * v0


@pytest.mark.parametrize("v,name", [(30, "dense fog"), (300, "moderate fog"), (1500, "mist"), (8000, "light haze"),
                                    (15000, "clear"), (90000, "exceptionally clear")])
def test_visibility_classes(v, name):
    assert ph.visibility_class(v) == name


def test_airmass_kasten_young():
    assert ph.airmass(90) == pytest.approx(1.0, abs=0.001)
    assert ph.airmass(30) == pytest.approx(2.0, abs=0.01)
    assert ph.airmass(0) == pytest.approx(38.0, abs=0.5)               # Kasten & Young horizon value


def test_rayleigh_depth_at_550nm():
    assert ph.rayleigh_optical_depth(0.55) == pytest.approx(0.0973, abs=0.001)
    assert ph.rayleigh_optical_depth(0.45) > 4 * ph.rayleigh_optical_depth(0.65)   # lambda^-4: why the sky is blue


def test_sun_colour_reddens_with_lower_sun():
    hi, lo = ph.sun_color_rgb(90), ph.sun_color_rgb(3)
    assert hi == pytest.approx((1.0, 1.0, 1.0), abs=1e-6)             # white-balanced to the zenith
    assert lo[0] == 1.0 and lo[1] < 0.5 and lo[2] < lo[1]
    raw = ph.sun_color_rgb(90, white_balance=False)
    assert raw[0] >= raw[2]                                           # physical source: warmer than white


def test_sun_strength_ratio_monotonic_and_zero_below_horizon():
    vals = [ph.sun_strength_ratio(e) for e in (90, 60, 30, 10, 5, 1)]
    assert vals == sorted(vals, reverse=True) and vals[0] == pytest.approx(1.0)
    assert ph.sun_strength_ratio(-5) == 0.0
    assert ph.sun_lamp_strength(90, anchor=3.0) == pytest.approx(3.0)


def test_direct_irradiance_in_plausible_range():
    assert 900 < ph.direct_irradiance_w_m2(90) < 1150                  # clear-sky DNI at sea level


def test_blackbody_known_points():
    x, y = ph.blackbody_xy(6500)
    assert (x, y) == pytest.approx((0.3135, 0.3237), abs=0.002)        # Planckian locus at 6500 K
    r, g, b = ph.blackbody_rgb(2000)
    assert r == 1.0 and b < 0.2                                       # candle-flame orange
    r, g, b = ph.blackbody_rgb(12000)
    assert b == 1.0 and r < 0.8                                       # blue-white


def test_star_colours_by_bv():
    assert ph.bv_to_temperature(0.0) == pytest.approx(10000, rel=0.05)   # Vega-like
    assert ph.bv_to_temperature(1.85) < 4000                              # Betelgeuse-like
    red, blue = ph.star_rgb(1.8), ph.star_rgb(-0.2)
    assert red[0] > red[2] and blue[2] > blue[0]


def test_moon_photometry():
    assert ph.moon_illuminance_lux(0, 90) == pytest.approx(0.2, abs=0.08)   # full moon at zenith
    assert ph.moon_illuminance_lux(90, 90) < 0.15 * ph.moon_illuminance_lux(0, 90)
    assert ph.moon_illuminance_lux(0, -5) == 0.0
    assert ph.moon_apparent_magnitude(0) == pytest.approx(-12.73)
    assert ph.moon_apparent_magnitude(90) == pytest.approx(-10.1, abs=0.1)
    assert ph.moon_lamp_strength(0, 90, anchor=0.12) == pytest.approx(0.12)
    assert ph.illuminance_from_magnitude(ph.SUN_MAGNITUDE) == pytest.approx(1.0e5, rel=0.15)


def test_star_flux_and_pogson():
    assert ph.star_flux(0) == 1.0
    assert ph.star_flux(5) == pytest.approx(0.01)


@pytest.mark.parametrize("h,name", [(10, "day"), (-3, "civil twilight"), (-9, "nautical twilight"),
                                    (-15, "astronomical twilight"), (-30, "night")])
def test_twilight_names(h, name):
    assert ph.twilight_name(h) == name


def test_limiting_magnitude_behaviour():
    assert ph.limiting_magnitude(30) < -3                              # no stars in daylight
    assert ph.limiting_magnitude(-30) == pytest.approx(6.5)
    dark, moony = ph.limiting_magnitude(-30), ph.limiting_magnitude(-30, 60, 1.0)
    assert moony < dark - 1.5                                          # a full moon washes out faint stars
    assert ph.limiting_magnitude(-30, clouds=1.0) == pytest.approx(3.5)
    seq = [ph.limiting_magnitude(h) for h in (0, -6, -12, -18)]
    assert seq == sorted(seq)


def test_cloud_lit_colour_and_helpers():
    assert max(ph.cloud_lit_color(40)) == pytest.approx(1.0, abs=0.05)
    assert max(ph.cloud_lit_color(-10)) == 0.0
    assert ph.cloud_transmission_estimate(0.0, 5.0) == 1.0
    assert ph.cloud_transmission_estimate(1.0, 5.0) == pytest.approx(math.exp(-5))
    assert ph.horizon_distance_m(1.7) == pytest.approx(4650, rel=0.01)   # eye-level horizon, ~4.7 km
    assert ph.exposure_ev(1e5) == 0.0 and ph.exposure_ev(1e2, compensation=0.5) == pytest.approx(4.98, abs=0.05)


def test_sun_at_altitude_is_brighter_and_less_red():
    ground = ph.sun_transmittance_rgb(3.0)
    cloud = ph.sun_transmittance_rgb(3.0, altitude_m=4000.0)
    assert all(c > g for c, g in zip(cloud, ground))
    assert cloud[2] / cloud[0] > 3 * ground[2] / ground[0]              # far less blue removed above the lower air
    assert ph.sun_strength_ratio(3.0, altitude_m=4000.0) > 3 * ph.sun_strength_ratio(3.0)
    assert ph.sun_strength_ratio(90.0) == pytest.approx(1.0)
    assert ph.sun_strength_ratio(90.0, altitude_m=4000.0) > 1.0         # a little more than at the ground
    c0, c4 = ph.sun_color_rgb(3.0), ph.sun_color_rgb(3.0, altitude_m=4000.0)
    assert c4[1] > c0[1] and c4[2] > c0[2]                              # golden clouds, red ground
