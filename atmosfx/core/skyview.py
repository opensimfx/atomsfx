"""Turn user parameters into every number the Blender layer needs. Pure Python.

``SkyParams`` is a plain bag of values (the scene layer fills it from property groups, tests fill it by hand);
``compute_view`` returns a ``SkyView`` with the sun/moon directions, lamp strengths and colours, star and Milky
Way gains, ground and cloud-deck radiance, and the two Mapping-node Euler rotations for the celestial sphere.
Nothing here imports ``bpy``, so the whole chain from "June 21, 22:30 at 28N 77E" to "this socket value" is
unit-tested without Blender.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import astro, physics, starmap

# Display calibration (see docs/PHYSICS.md "Display calibration"). Absolute scales are artistic; ratios physical.
STAR_GAIN = 0.08
# Blender 5.0's Sky Texture radiance is ~30x brighter than a 3.0-strength Sun lamp implies (measured: zenith blue
# ~7 at noon, giving a sky:sun irradiance ratio near 5:1; real clear skies are ~1:10). SKY_SCALE restores the ratio.
SKY_SCALE = 0.03
MOON_GLOW = 0.012                       # sky radiance added by a full moon at the zenith (display units)
MOON_COLOR_TINT = (0.80, 0.92, 1.08)     # moonlight looks cooler than its 4100 K colour (Purkinje shift; film grades it blue)

# Horizontal irradiance (luminance-weighted, display units) that the AtmosFX sky alone delivers at sky strength 1,
# by sun elevation. Measured in Blender 5.2.3 Cycles: a white Lambertian plane lit by the world only, lamps
# hidden (tools: VALIDATION.md "Sky irradiance"). The floor below -8 degrees is the night glow.
SKY_IRRADIANCE = ((90.0, 0.472), (60.0, 0.442), (40.0, 0.391), (25.0, 0.331), (15.0, 0.268), (8.0, 0.192),
                  (4.0, 0.123), (2.0, 0.0817), (0.0, 0.0412), (-1.0, 0.0251), (-2.0, 0.0138), (-3.0, 0.00734),
                  (-4.0, 0.00424), (-5.0, 0.00298), (-6.0, 0.00244), (-8.0, 0.00198), (-10.0, 0.00175),
                  (-12.0, 0.00163), (-15.0, 0.00154), (-18.0, 0.00151))
SKY_WEIGHT = 2.0       # the sky is usually in frame: its light counts extra, so a sky-lit (twilight, moonless) scene
                       # is exposed for the sky, not for the dark ground, and does not come out as a bright grey sky
CLOUD_BOUNCE = 0.3     # share of the cloud sun a broken deck sends down when the sun is low (exposure only)
NOON_IRRADIANCE = 3.47 + SKY_WEIGHT * 0.472   # sun lamp 3.0 at the zenith plus the weighted sky: exposure 0


def sky_irradiance(sun_elevation_deg: float) -> float:
    el = sun_elevation_deg
    if el >= SKY_IRRADIANCE[0][0]:
        return SKY_IRRADIANCE[0][1]
    if el <= SKY_IRRADIANCE[-1][0]:
        return SKY_IRRADIANCE[-1][1]
    for (e0, v0), (e1, v1) in zip(SKY_IRRADIANCE, SKY_IRRADIANCE[1:]):
        if e1 <= el <= e0:
            t = (el - e0) / (e1 - e0)
            return math.exp(math.log(v0) + (math.log(v1) - math.log(v0)) * t)
    return SKY_IRRADIANCE[-1][1]


def auto_exposure(display_irradiance: float, real_lux: float) -> float:
    """Film exposure (stops) that renders the scene at its cinematic key: as bright as noon minus
    ``physics.cinematic_key_stops``. ``display_irradiance`` is the sky-weighted irradiance (ground light plus
    SKY_WEIGHT x the sky's share). Clamped to [-3, 10]."""
    ev = math.log2(NOON_IRRADIANCE / max(display_irradiance, 1e-6)) - physics.cinematic_key_stops(real_lux)
    return min(max(ev, -3.0), 10.0)


@dataclass
class SkyParams:
    time_mode: str = "ARTISTIC"          # ARTISTIC or EARTH
    sun_elevation: float = 45.0
    sun_azimuth: float = 135.0
    latitude: float = 40.0
    longitude: float = 0.0
    year: int = 2026
    month: int = 6
    day: int = 21
    hour: float = 12.0                   # local civil time, hours
    utc_offset: float = 0.0
    north_offset: float = 0.0
    refraction: bool = True
    # sun
    sun_strength: float = 3.0
    sun_size_scale: float = 1.0
    use_sun_lamp: bool = True
    aerosol_density: float = 1.0
    # moon
    moon_enabled: bool = True
    moon_phase: float = 0.5
    moon_elevation: float = 40.0
    moon_azimuth: float = 200.0
    moon_strength: float = 0.12
    moon_size_scale: float = 1.0
    # stars
    stars_enabled: bool = True
    star_brightness: float = 1.0
    magnitude_limit: float = 6.0
    milky_way: float = 1.0
    # sky
    sky_strength: float = 1.0
    night_glow: float = 0.0015
    cloud_cover: float = 0.0             # 2D-deck coverage; dims the sun lamp and stars (volumetric clouds cast real shadows)
    cloud_lit_altitude_m: float = 0.0    # mean altitude of the volumetric layers; > 0 enables the separate cloud sun
    cloud_light: float = 1.0             # share of ground light left under the volumetric layers (exposure only)
    cloud_cover_volumetric: float = 0.0  # combined cover of the volumetric layers (exposure only)
    # time animation (frame is the current frame; ignored unless animate_time)
    # solar eclipse: magnitude (share of the Sun's diameter the Moon covers; >= 1 total)
    eclipse: float = 0.0
    animate_time: bool = False
    time_scale: float = 1.0              # simulated hours per real second
    frame: float = 1.0
    frame_start: float = 1.0
    fps: float = 24.0


@dataclass
class SkyView:
    # directions (scene frame, unit)
    sun_vec: tuple
    moon_vec: tuple
    moon_light_vec: tuple
    # angles / readouts
    sun_elevation_deg: float
    sun_azimuth_deg: float
    moon_elevation_deg: float
    moon_phase_angle_deg: float
    moon_fraction: float
    moon_waxing: bool
    moon_phase_name: str
    twilight: str
    limiting_magnitude: float
    lst_deg: float
    effective_hour: float
    # sun
    sun_lamp_strength: float
    sun_color: tuple
    sun_radius_rad: float
    sun_disc_radiance: float
    cloud_sun_strength: float
    cloud_sun_color: tuple
    # moon
    moon_lamp_strength: float
    moon_color: tuple
    moon_radius_rad: float
    moon_disc_radiance: float
    # stars
    celestial_euler: tuple
    galactic_euler: tuple
    star_brightness: float
    star_threshold: float
    milky_way_strength: float
    # sky / ground / deck
    night_glow: float
    sky_strength: float
    ground_strength: float
    deck_color: tuple
    deck_sun_light: tuple = (0.0, 0.0, 0.0)
    fog_ambient: tuple = (0.0, 0.0, 0.0)
    cloud_ambient: tuple = (0.0, 0.0, 0.0)
    cloud_top: tuple = (0.0, 0.0, 0.0)
    cloud_glow: tuple = (1.0, 1.0, 1.0)
    cloud_glow_strength: float = 0.0
    moon_glow: float = 0.0
    exposure: float = 0.0
    scene_from_j2000: tuple = field(default=())
    eclipse_offset: float = 10.0        # Moon-Sun centre separation, solar radii (10 = no eclipse)
    eclipse_visible: float = 1.0        # share of the solar disc left uncovered
    corona: float = 0.0                 # corona radiance at the limb
    eclipse_glow: tuple = (0.0, 0.0, 0.0)


def effective_hour(p: SkyParams) -> float:
    if not p.animate_time:
        return p.hour
    return p.hour + (p.frame - p.frame_start) / max(p.fps, 1e-6) * p.time_scale


def aerosol_beta(aerosol_density: float) -> float:
    """Angstrom turbidity coefficient from the Sky Texture 'Aerosol' multiplier (1.0 -> 0.05, clear continental)."""
    return 0.05 * max(aerosol_density, 0.0)


def compute_view(p: SkyParams) -> SkyView:
    hour = effective_hour(p)
    jd = astro.jd_from_local(p.year, p.month, p.day, hour, p.utc_offset)
    st = astro.compute(jd, p.latitude, p.longitude, p.north_offset, p.refraction)
    beta = aerosol_beta(p.aerosol_density)

    # ------------------------------------------------------------------- sun
    if p.time_mode == "EARTH":
        sun_vec, sun_el = st.sun_vec, st.sun_alt_app_deg
        sun_az = st.sun_az_deg
    else:
        sun_vec = astro.artistic_sun(p.sun_elevation, p.sun_azimuth)
        sun_el, sun_az = p.sun_elevation, p.sun_azimuth % 360.0

    sun_ratio = physics.sun_strength_ratio(sun_el, beta)
    # eclipse: the lamp keeps the uncovered share of the disc; the sky is lit by it too, down to the totality floor
    ecl_vis = physics.eclipse_visible_fraction(p.eclipse) if p.eclipse > 0.0 else 1.0
    sky_f = max(ecl_vis, physics.ECLIPSE_TOTALITY_SKY)
    sky_strength = p.sky_strength * sky_f
    cloud_dim = 1.0 - 0.85 * min(max(p.cloud_cover, 0.0), 1.0) ** 1.5
    sun_lamp = p.sun_strength * sun_ratio * cloud_dim * ecl_vis
    sun_color = physics.sun_color_rgb(sun_el, beta) if sun_el > -2.0 else (1.0, 0.0, 0.0)
    sun_diam = (st.sun_diameter_deg if p.time_mode == "EARTH" else physics.SUN_ANGULAR_DIAMETER_DEG) * p.sun_size_scale
    sun_r = math.radians(sun_diam) / 2.0
    sun_solid = math.pi * sun_r * sun_r
    # camera-visible radiance: the full (unclouded) beam, so the disc stays a disc even when a lamp does the lighting
    sun_disc = p.sun_strength * sun_ratio / sun_solid if sun_el > -1.0 else 0.0
    # the sun that lights volumetric clouds: same elevation, less air above the cloud, so brighter and less red
    if p.cloud_lit_altitude_m > 0.0:
        cloud_sun = p.sun_strength * physics.sun_strength_ratio(sun_el, beta, p.cloud_lit_altitude_m) * ecl_vis
        cloud_sun_color = physics.sun_color_rgb(sun_el, beta, altitude_m=p.cloud_lit_altitude_m) if sun_el > -4.0 else (1.0, 0.0, 0.0)
        if sun_el <= -4.0:
            cloud_sun = 0.0
    else:
        cloud_sun, cloud_sun_color = 0.0, (1.0, 1.0, 1.0)

    # ------------------------------------------------------------------ moon
    if p.time_mode == "EARTH":
        moon_vec, moon_el = st.moon_vec, st.moon_alt_app_deg
        phase_angle, fraction, waxing = st.moon_phase_angle_deg, st.moon_fraction, st.moon_waxing
        light_vec = st.moon_light_vec
        moon_diam = st.moon_diameter_deg * p.moon_size_scale
        dist_km = st.moon_distance_km
    else:
        moon_vec = astro.altaz_to_enu(p.moon_elevation, p.moon_azimuth)
        moon_el = p.moon_elevation
        phase_angle, waxing, fraction = astro.phase_to_angle_deg(p.moon_phase)
        light_vec = astro.artistic_moon_light_dir(moon_vec, phase_angle, waxing)
        moon_diam = physics.MOON_ANGULAR_DIAMETER_DEG * p.moon_size_scale
        dist_km = 384400.0
    moon_on = p.moon_enabled
    sun_below = sun_el < -0.5
    # the artistic moon anchor is far above the physical ratio to the sun, so fade the lamp out as the sun rises
    moon_day_fade = physics.smoothstep(3.0, -5.0, sun_el)
    moon_lamp = (physics.moon_lamp_strength(phase_angle, moon_el, p.moon_strength, dist_km)
                 if moon_on else 0.0) * cloud_dim * moon_day_fade
    moon_full_lamp = physics.moon_lamp_strength(0.0, moon_el, p.moon_strength, dist_km) if moon_on and moon_el > -1 else 0.0
    moon_r = math.radians(moon_diam) / 2.0
    moon_solid = math.pi * moon_r * moon_r
    # disc radiance uses the *full-phase* strength; the shader's Lambert term supplies the phase
    moon_disc = moon_full_lamp / moon_solid * 0.9 if moon_on else 0.0
    moon_rgb = tuple(c * t for c, t in zip(physics.blackbody_rgb(physics.MOON_LIGHT_TEMPERATURE_K), MOON_COLOR_TINT))

    # ----------------------------------------------------------------- stars
    lim = physics.limiting_magnitude(sun_el, moon_el if moon_on else -90.0, fraction, p.magnitude_limit, p.cloud_cover)
    # totality: the sky is as dark as deep twilight and the brightest stars and planets come out
    lim = max(lim, 3.0 * physics.smoothstep(0.97, 1.0, p.eclipse)) if p.eclipse > 0.0 else lim
    star_gain = STAR_GAIN * p.star_brightness if p.stars_enabled else 0.0
    threshold = starmap.luminance_threshold(min(lim, p.magnitude_limit))
    # Milky Way fades as the sky brightens: gone near limiting magnitude 4.5
    mw_vis = physics.smoothstep(3.5, 5.8, lim)
    milky = star_gain * p.milky_way * mw_vis
    cel = astro.mapping_rotation_celestial(st.scene_from_j2000)
    gal = astro.mapping_rotation_galactic(st.scene_from_j2000)

    # ----------------------------------------------------- ground and cloud deck
    amb = physics.sky_ambient_scale(sun_el)
    ground = (sun_lamp * max(math.sin(math.radians(sun_el)), 0.0) / math.pi
              + 0.25 * sky_strength * amb
              + moon_lamp * max(math.sin(math.radians(moon_el)), 0.0) / math.pi)
    lit = physics.cloud_lit_color(sun_el, beta)
    moon_k = moon_lamp / max(p.moon_strength, 1e-6) if moon_on else 0.0
    deck_color = tuple(1.25 * sky_strength * c + 0.02 * moon_k * m for c, m in zip(lit, moon_rgb))

    ratio_k = max(sun_ratio, 0.0) ** 0.6 if sun_el > -4.0 else 0.0
    deck_sun = tuple(c * ratio_k * cloud_dim * ecl_vis for c in sun_color)
    glow = MOON_GLOW * moon_k
    # radiance a fog droplet 'sees' from multiple scattering: diffuse sky light plus a share of the sun's forward
    # scatter. Path tracing with a handful of volume bounces cannot build this up in thick fog (it renders black),
    # so the fog shaders emit it directly, in proportion to density.
    sky_amb = 0.25 * sky_strength * amb
    fog_amb = tuple(sky_amb * c + 0.10 * sun_lamp * sc + 0.4 * moon_lamp * m
                    for c, sc, m in zip((0.85, 0.92, 1.0), sun_color if sun_el > -2.0 else (0.0, 0.0, 0.0), moon_rgb))
    cloud_ambient, cloud_top, cloud_glow, cloud_glow_strength = physics.cloud_scatter_lighting(
        sun_el, sun_color, cloud_sun_color, cloud_sun, sky_amb, moon_lamp, moon_rgb)

    # ------------------------------------------------------------- exposure
    sin_s = max(math.sin(math.radians(sun_el)), 0.0)
    sin_m = max(math.sin(math.radians(moon_el)), 0.0)
    # a low sun lights broken cloud from the side and the deck sends that light down (golden ground at sunset);
    # an overcast deck sends little, a high sun is already counted by cloud_light
    broken = 4.0 * p.cloud_cover_volumetric * (1.0 - p.cloud_cover_volumetric)
    sky_e = (sky_strength * sky_irradiance(sun_el) * cloud_dim + glow * 1.5) * p.cloud_light
    e_display = ((sun_lamp * sin_s) * p.cloud_light + (1.0 + SKY_WEIGHT) * sky_e + moon_lamp * sin_m
                 + CLOUD_BOUNCE * cloud_sun * broken * physics.smoothstep(20.0, 3.0, sun_el))
    e_real = (physics.daylight_illuminance_lux(sun_el, beta) * sky_f * cloud_dim * p.cloud_light
              + (physics.moon_illuminance_lux(phase_angle, moon_el, dist_km) * cloud_dim if moon_on else 0.0))
    exposure = auto_exposure(e_display, e_real)

    return SkyView(
        sun_vec=tuple(sun_vec), moon_vec=tuple(moon_vec), moon_light_vec=tuple(light_vec),
        sun_elevation_deg=sun_el, sun_azimuth_deg=sun_az, moon_elevation_deg=moon_el,
        moon_phase_angle_deg=phase_angle, moon_fraction=fraction, moon_waxing=waxing,
        moon_phase_name=astro.moon_phase_name(fraction, waxing), twilight=physics.twilight_name(sun_el),
        limiting_magnitude=lim, lst_deg=st.lst_deg, effective_hour=hour,
        sun_lamp_strength=sun_lamp, sun_color=sun_color, sun_radius_rad=sun_r, sun_disc_radiance=sun_disc,
        cloud_sun_strength=cloud_sun, cloud_sun_color=cloud_sun_color,
        moon_lamp_strength=moon_lamp, moon_color=moon_rgb, moon_radius_rad=moon_r, moon_disc_radiance=moon_disc,
        celestial_euler=cel, galactic_euler=gal, star_brightness=star_gain, star_threshold=threshold,
        milky_way_strength=milky, night_glow=p.night_glow, sky_strength=sky_strength * SKY_SCALE,
        ground_strength=ground, deck_color=deck_color,
        deck_sun_light=deck_sun, moon_glow=glow, fog_ambient=fog_amb,
        cloud_ambient=cloud_ambient, cloud_top=cloud_top, cloud_glow=cloud_glow,
        cloud_glow_strength=cloud_glow_strength, exposure=exposure, scene_from_j2000=st.scene_from_j2000,
        eclipse_offset=physics.eclipse_offset(p.eclipse) if p.eclipse > 0.0 else 10.0,
        eclipse_visible=ecl_vis,
        # totality on AtmosFX's night scale (see physics.ECLIPSE_TOTALITY_SKY): a corona like the full moon and
        # an orange horizon glow
        corona=(physics.ECLIPSE_CORONA_MOON * 0.9 * p.moon_strength / max(sun_solid, 1e-9)
                * physics.smoothstep(0.985, 1.0, p.eclipse)),   # only once the photosphere is gone
        eclipse_glow=tuple(c * p.sky_strength * SKY_SCALE * physics.ECLIPSE_HORIZON_GLOW
                           * physics.smoothstep(0.97, 1.0, p.eclipse)
                           for c in (1.0, 0.5, 0.22)),
    )
