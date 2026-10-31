import math

import pytest

from atmosfx.core import astro, physics
from atmosfx.core.skyview import SkyParams, compute_view, effective_hour


def view(**kw):
    return compute_view(SkyParams(**kw))


DELHI = dict(time_mode="EARTH", latitude=28.6, longitude=77.2, utc_offset=5.5, year=2026, month=6, day=21)


def test_artistic_noon_is_a_bright_white_sun():
    v = view(sun_elevation=65)
    assert v.sun_lamp_strength == pytest.approx(3.0 * physics.sun_strength_ratio(65, 0.05), rel=1e-6)
    assert v.sun_color[0] == 1.0 and v.sun_color[2] > 0.9
    assert v.sun_elevation_deg == 65 and v.twilight == "day"
    assert v.star_threshold > 1000 and v.milky_way_strength == 0          # no stars in daylight
    assert v.moon_lamp_strength == 0.0                                    # moonlight fades out in daylight


def test_sun_direction_matches_the_sky_node_convention():
    v = view(sun_elevation=30, sun_azimuth=90)                            # due east, 30 above the horizon
    assert v.sun_vec == pytest.approx((math.cos(math.radians(30)), 0.0, 0.5), abs=1e-9)
    v = view(sun_elevation=10, sun_azimuth=0)                             # due north = +Y
    assert v.sun_vec[1] > 0.98 and abs(v.sun_vec[0]) < 1e-9


def test_sunset_is_dim_and_orange():
    v = view(sun_elevation=2)
    assert v.sun_lamp_strength < 0.2 and v.sun_color[0] == 1.0 and v.sun_color[2] < 0.1
    assert 100 < v.sun_disc_radiance < 5000


def test_disc_radiance_is_strength_over_solid_angle():
    v = view(sun_elevation=90, sun_strength=3.0)
    omega = math.pi * v.sun_radius_rad ** 2
    assert v.sun_disc_radiance == pytest.approx(3.0 * physics.sun_strength_ratio(90) / omega, rel=1e-6)
    assert math.degrees(v.sun_radius_rad * 2) == pytest.approx(0.5334, abs=1e-3)
    big = view(sun_elevation=90, sun_size_scale=2.0)
    assert big.sun_radius_rad == pytest.approx(2 * v.sun_radius_rad)


def test_night_shows_stars_and_a_moon():
    v = view(sun_elevation=-35, moon_phase=0.5, moon_elevation=45)
    assert v.twilight == "night" and v.sun_lamp_strength == 0.0
    assert v.limiting_magnitude < 6.0                                      # full moon washes out the faintest stars
    assert v.moon_lamp_strength > 0.08 and v.moon_glow > 0
    dark = view(sun_elevation=-35, moon_enabled=False)
    assert dark.limiting_magnitude == pytest.approx(6.0) and dark.moon_lamp_strength == 0.0
    assert dark.star_threshold < v.star_threshold
    assert dark.milky_way_strength > v.milky_way_strength


def test_twilight_progression_of_star_visibility():
    thr = [view(sun_elevation=h, moon_enabled=False).star_threshold for h in (5, -3, -9, -15, -25)]
    assert thr == sorted(thr, reverse=True)


def test_moon_phase_geometry_artistic():
    full = view(sun_elevation=-30, moon_phase=0.5, moon_elevation=40, moon_azimuth=180)
    new = view(sun_elevation=-30, moon_phase=0.0, moon_elevation=40, moon_azimuth=180)
    assert astro.angular_separation_deg(full.moon_light_vec, full.moon_vec) == pytest.approx(180, abs=0.1)
    assert astro.angular_separation_deg(new.moon_light_vec, new.moon_vec) == pytest.approx(0, abs=0.1)
    assert full.moon_lamp_strength > 10 * new.moon_lamp_strength
    assert full.moon_fraction == pytest.approx(1.0) and new.moon_fraction == pytest.approx(0.0)


def test_earth_mode_matches_the_ephemeris_directly():
    v = view(hour=12.0, **DELHI)
    st = astro.compute_local(2026, 6, 21, 12.0, 5.5, 28.6, 77.2, 0.0)
    assert v.sun_vec == pytest.approx(st.sun_vec, abs=1e-9)
    assert v.sun_elevation_deg == pytest.approx(st.sun_alt_app_deg)
    assert 80 < v.sun_elevation_deg < 85                                  # near-overhead at the June solstice


def test_earth_mode_night_has_stars_and_physical_moon():
    v = view(hour=22.5, **DELHI)
    assert v.sun_elevation_deg < -25 and v.sun_lamp_strength == 0.0
    assert v.moon_waxing and 0.35 < v.moon_fraction < 0.65       # first quarter on the evening of 21 June 2026
    assert v.limiting_magnitude > 4


def test_time_animation_advances_the_clock():
    base = dict(animate_time=True, time_scale=2.0, fps=24.0, frame_start=1.0, hour=6.0)
    assert effective_hour(SkyParams(frame=1.0, **base)) == 6.0
    assert effective_hour(SkyParams(frame=25.0, **base)) == pytest.approx(8.0)       # 1 s at 2 h/s
    assert effective_hour(SkyParams(frame=25.0, animate_time=False, hour=6.0)) == 6.0
    a = view(hour=6.0, **DELHI)
    b = compute_view(SkyParams(frame=49.0, **base, **{k: v for k, v in DELHI.items()}))
    assert b.sun_elevation_deg > a.sun_elevation_deg                                  # sun climbs in the morning


def test_north_offset_rotates_everything_consistently():
    a = view(hour=15.0, north_offset=0.0, **DELHI)
    b = view(hour=15.0, north_offset=90.0, **DELHI)
    assert a.sun_elevation_deg == pytest.approx(b.sun_elevation_deg)
    assert a.sun_vec[2] == pytest.approx(b.sun_vec[2])
    rot = astro.mat_vec(astro.rot_z(math.pi / 2), a.sun_vec)
    assert b.sun_vec == pytest.approx(rot, abs=1e-9)


def test_clouds_dim_the_sun_and_stars():
    clear = view(sun_elevation=50)
    overcast = view(sun_elevation=50, cloud_cover=1.0)
    assert overcast.sun_lamp_strength == pytest.approx(0.15 * clear.sun_lamp_strength, rel=1e-6)
    assert overcast.sun_disc_radiance == pytest.approx(clear.sun_disc_radiance)        # the disc itself stays a disc
    n0 = view(sun_elevation=-40, moon_enabled=False)
    n1 = view(sun_elevation=-40, moon_enabled=False, cloud_cover=0.8)
    assert n1.limiting_magnitude < n0.limiting_magnitude - 2


def test_star_rotation_eulers_reproduce_the_scene_matrix():
    v = view(hour=22.0, **DELHI)
    m = v.scene_from_j2000
    inv = astro.euler_xyz_to_matrix(v.celestial_euler)          # what the Mapping node applies
    sirius = astro.radec_to_vec(101.287, -16.716)
    scene_dir = astro.mat_vec(m, sirius)
    assert astro.mat_vec(inv, scene_dir) == pytest.approx(sirius, abs=1e-9)
    gal = astro.euler_xyz_to_matrix(v.galactic_euler)
    assert astro.mat_vec(gal, scene_dir) == pytest.approx(astro.mat_vec(astro.GALACTIC_FROM_J2000, sirius), abs=1e-9)


def test_ground_brightness_follows_the_light():
    day, night = view(sun_elevation=60), view(sun_elevation=-40, moon_enabled=False)
    assert day.ground_strength > 20 * night.ground_strength > 0
    assert view(sun_elevation=60, sky_strength=0.0).ground_strength < day.ground_strength


def test_deck_colour_tracks_the_sun():
    noon, dusk, night = view(sun_elevation=50), view(sun_elevation=-4), view(sun_elevation=-30, moon_enabled=False)
    assert max(noon.deck_color) > 0.9 and max(night.deck_color) < 0.02
    assert max(noon.deck_sun_light) > max(dusk.deck_sun_light) >= 0.0
    assert night.deck_sun_light == (0.0, 0.0, 0.0)


def test_moon_size_scale_and_distance_effects():
    v1, v2 = view(sun_elevation=-30), view(sun_elevation=-30, moon_size_scale=2.0)
    assert v2.moon_radius_rad == pytest.approx(2 * v1.moon_radius_rad)
    assert math.degrees(v1.moon_radius_rad * 2) == pytest.approx(0.5286, abs=1e-3)


def test_cloud_lighting_has_a_dark_blue_base_and_a_bright_top():
    noon = view(sun_elevation=52, cloud_lit_altitude_m=2200)
    assert max(noon.cloud_ambient) < 0.05
    assert noon.cloud_ambient[2] > noon.cloud_ambient[0]               # shadowed base is blue
    assert noon.cloud_top[2] > 5 * noon.cloud_ambient[2]               # sunlit top dominates
    assert noon.cloud_glow_strength < 0.5                              # forward halo is subtle at high sun


def test_cloud_lighting_is_warm_and_backlit_at_sunset():
    noon = view(sun_elevation=52, cloud_lit_altitude_m=2200)
    dusk = view(sun_elevation=4, sun_azimuth=268, cloud_lit_altitude_m=4200)
    assert dusk.cloud_ambient[0] > 2.5 * dusk.cloud_ambient[2]         # light comes from below, and it is red
    assert dusk.cloud_top[0] > dusk.cloud_top[2]
    assert dusk.cloud_ambient[0] > 4 * noon.cloud_ambient[0]
    assert dusk.cloud_glow_strength > 5 * noon.cloud_glow_strength
    assert dusk.cloud_glow[0] > dusk.cloud_glow[2]                     # warm forward-scatter halo colour


def test_cloud_lighting_fades_at_night_and_tracks_the_moon():
    dark = view(sun_elevation=-35, moon_enabled=False, cloud_lit_altitude_m=3000)
    assert max(dark.cloud_ambient) < 0.005 and dark.cloud_glow_strength == 0.0
    moonlit = view(sun_elevation=-35, moon_enabled=True, moon_phase=0.5, cloud_lit_altitude_m=3000)
    assert max(moonlit.cloud_ambient) > 5 * max(dark.cloud_ambient)
    assert max(moonlit.cloud_top) > max(moonlit.cloud_ambient)


def test_cloud_deck_turns_warm_at_sunset():
    noon, dusk = view(sun_elevation=52), view(sun_elevation=4)
    assert noon.deck_color[2] > 0.85 * noon.deck_color[0]
    assert dusk.deck_color[2] < 0.7 * dusk.deck_color[0]


def test_cloud_sun_is_off_without_volumetric_layers_and_beats_the_ground_sun_at_sunset():
    plain = view(sun_elevation=3)
    assert plain.cloud_sun_strength == 0.0
    lit = view(sun_elevation=3, cloud_lit_altitude_m=3000.0)
    assert lit.cloud_sun_strength > 3 * lit.sun_lamp_strength
    assert lit.cloud_sun_color[1] > lit.sun_color[1] and lit.cloud_sun_color[2] > lit.sun_color[2]
    assert lit.sun_lamp_strength == pytest.approx(plain.sun_lamp_strength)          # the ground sun is unchanged
    noon = view(sun_elevation=70, cloud_lit_altitude_m=3000.0)
    assert noon.cloud_sun_strength == pytest.approx(noon.sun_lamp_strength, rel=0.15)
    night = view(sun_elevation=-20, cloud_lit_altitude_m=3000.0)
    assert night.cloud_sun_strength == 0.0
