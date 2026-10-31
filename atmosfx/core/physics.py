"""Atmospheric optics and photometry used by AtmosFX. Pure Python, no ``bpy``.

Every function documents its source. Quantities are SI unless the name says
otherwise (``_deg``, ``_km``, ``_lux``). Blender-side modules never carry their
own physics; they call these functions so tests, docs and UI agree.
"""
from __future__ import annotations

import math

# ----------------------------------------------------------------- constants
EARTH_RADIUS_M = 6_371_000.0
RAYLEIGH_SCALE_HEIGHT_M = 8_000.0       # molecular scattering scale height
MIE_SCALE_HEIGHT_M = 1_200.0            # aerosol scale height (clean continental)
SOLAR_CONSTANT_W_M2 = 1361.0
SUN_ANGULAR_DIAMETER_DEG = 0.5334       # mean value
MOON_ANGULAR_DIAMETER_DEG = 0.5286      # mean value
SUN_LUX_ZENITH_CLEAR = 1.0e5            # illuminance of a high clear-sky sun
SUN_MAGNITUDE = -26.74
KOSCHMIEDER_CONTRAST = 0.02             # WMO visual-range contrast threshold
RGB_WAVELENGTHS_UM = (0.64, 0.55, 0.46)  # representative R, G, B wavelengths


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if x < lo else hi if x > hi else x


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def smoothstep(e0: float, e1: float, x: float) -> float:
    if e0 == e1:
        return 0.0 if x < e0 else 1.0
    t = clamp((x - e0) / (e1 - e0))
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------- visibility / fog
def koschmieder_extinction(visibility_m: float, contrast: float = KOSCHMIEDER_CONTRAST) -> float:
    """Extinction coefficient sigma_t [1/m] for a meteorological optical range.

    Koschmieder (1924): V = -ln(contrast) / sigma_t. With the WMO threshold of
    2 % this is sigma_t = 3.912 / V. A 1 km visibility gives 0.003912 1/m.
    """
    if visibility_m <= 0:
        raise ValueError("visibility must be > 0")
    return -math.log(contrast) / visibility_m


def visibility_from_extinction(sigma_t: float, contrast: float = KOSCHMIEDER_CONTRAST) -> float:
    if sigma_t <= 0:
        return math.inf
    return -math.log(contrast) / sigma_t


def transmittance(sigma_t: float, distance_m: float) -> float:
    """Beer-Lambert transmittance exp(-sigma_t * d)."""
    return math.exp(-sigma_t * distance_m)


def height_density(sigma0: float, height_m: float, base_m: float, scale_height_m: float) -> float:
    """Exponential density profile sigma(h) = sigma0 * exp(-(h - base) / H), 1 below ``base``."""
    if scale_height_m <= 0:
        return sigma0 if height_m <= base_m else 0.0
    return sigma0 * math.exp(-max(height_m - base_m, 0.0) / scale_height_m)


def vertical_optical_depth(sigma0: float, scale_height_m: float) -> float:
    """Optical depth of the whole exponential column straight up: sigma0 * H."""
    return sigma0 * scale_height_m


def horizontal_visibility_at(visibility_ground_m: float, height_m: float, base_m: float,
                             scale_height_m: float) -> float:
    """Visibility measured horizontally at ``height_m`` for a ground-referenced fog layer."""
    sigma = height_density(koschmieder_extinction(visibility_ground_m), height_m, base_m, scale_height_m)
    return visibility_from_extinction(sigma)


# WMO-style visibility classes, kept in metres.
VISIBILITY_CLASSES = (
    (50.0, "dense fog"),
    (200.0, "thick fog"),
    (500.0, "moderate fog"),
    (1000.0, "light fog"),
    (2000.0, "mist"),
    (5000.0, "haze"),
    (10000.0, "light haze"),
    (20000.0, "clear"),
    (50000.0, "very clear"),
    (math.inf, "exceptionally clear"),
)


def visibility_class(visibility_m: float) -> str:
    for limit, name in VISIBILITY_CLASSES:
        if visibility_m < limit:
            return name
    return VISIBILITY_CLASSES[-1][1]


# -------------------------------------------------------------------- air mass
def airmass(elevation_deg: float) -> float:
    """Relative optical air mass, Kasten & Young (1989). Valid down to the horizon (m ~ 38)."""
    h = max(elevation_deg, -0.5)
    return 1.0 / (math.sin(math.radians(h)) + 0.50572 * (6.07995 + h) ** -1.6364)


def rayleigh_optical_depth(wavelength_um: float, pressure_ratio: float = 1.0) -> float:
    """Vertical Rayleigh optical depth at sea level. Bodhaine et al. (1999) simplified form
    (Frohlich & Shaw 1980 coefficients). 0.0973 at 550 nm."""
    l = wavelength_um
    return pressure_ratio * 0.008569 * l ** -4 * (1.0 + 0.0113 * l ** -2 + 0.00013 * l ** -4)


def aerosol_optical_depth(wavelength_um: float, beta: float = 0.05, alpha: float = 1.3) -> float:
    """Angstrom law tau_a = beta * lambda^-alpha. beta ~0.02 pristine, 0.05 clear, 0.2 hazy, 0.5+ smog."""
    return beta * wavelength_um ** -alpha


def sun_transmittance_rgb(elevation_deg: float, aerosol_beta: float = 0.05,
                          ozone_tau: tuple[float, float, float] = (0.003, 0.021, 0.008),
                          altitude_m: float = 0.0) -> tuple[float, float, float]:
    """Direct-beam transmittance of the atmosphere above ``altitude_m`` per RGB channel.

    Rayleigh and aerosol optical depth fall off exponentially with height (scale heights 8 km and 1.2 km), so
    the sunlight reaching a cloud at 4 km has crossed far less air than the light at the ground: this is why
    clouds still glow orange after the ground is in shadow. Ozone sits above both, so it is unchanged.
    Ozone (Chappuis band) optical depths are representative values for 300 DU.
    """
    m = airmass(elevation_deg)
    kr = math.exp(-max(altitude_m, 0.0) / RAYLEIGH_SCALE_HEIGHT_M)
    ka = math.exp(-max(altitude_m, 0.0) / MIE_SCALE_HEIGHT_M)
    out = []
    for wl, tau_o in zip(RGB_WAVELENGTHS_UM, ozone_tau):
        tau = rayleigh_optical_depth(wl) * kr + aerosol_optical_depth(wl, aerosol_beta) * ka + tau_o
        out.append(math.exp(-tau * m))
    return tuple(out)  # type: ignore[return-value]


def direct_irradiance_w_m2(elevation_deg: float, aerosol_beta: float = 0.05, altitude_m: float = 0.0) -> float:
    """Direct normal irradiance at ``altitude_m`` (luminance-weighted over the RGB channels)."""
    if elevation_deg <= -1.0:
        return 0.0
    t = sun_transmittance_rgb(elevation_deg, aerosol_beta, altitude_m=altitude_m)
    return SOLAR_CONSTANT_W_M2 * (0.2126 * t[0] + 0.7152 * t[1] + 0.0722 * t[2])


def sun_strength_ratio(elevation_deg: float, aerosol_beta: float = 0.05, altitude_m: float = 0.0) -> float:
    """Direct irradiance at ``altitude_m`` relative to a 90 degree sun at the ground (same atmosphere)."""
    ref = direct_irradiance_w_m2(90.0, aerosol_beta)
    return direct_irradiance_w_m2(elevation_deg, aerosol_beta, altitude_m) / ref if ref > 0 else 0.0


def sun_lamp_strength(elevation_deg: float, anchor: float = 3.0, aerosol_beta: float = 0.05) -> float:
    """Blender Sun-lamp strength: ``anchor`` is the strength of the sun at 90 degrees.

    The *ratio* between elevations is physical (Beer-Lambert through the atmosphere); the
    absolute anchor is artistic and tied to the exposure you render with (3.0 suits AgX/Filmic at 0 EV).
    """
    return anchor * sun_strength_ratio(elevation_deg, aerosol_beta)


def sun_color_rgb(elevation_deg: float, aerosol_beta: float = 0.05,
                  white_balance: bool = True, altitude_m: float = 0.0) -> tuple[float, float, float]:
    """Linear RGB colour of the direct sun beam, normalised to max channel 1.

    With ``white_balance`` (default) the colour is relative to the same atmosphere with the Sun at the zenith,
    so a clear noon sun is neutral white and lower suns warm progressively, as a camera white-balanced for
    daylight would record. Without it the source is a 5778 K blackbody filtered by the full transmittance.
    """
    t = sun_transmittance_rgb(elevation_deg, aerosol_beta, altitude_m=altitude_m)
    if white_balance:
        ref = sun_transmittance_rgb(90.0, aerosol_beta)
        c = tuple(x / r for x, r in zip(t, ref))
    else:
        src = blackbody_rgb(5778.0)
        c = tuple(s * x for s, x in zip(src, t))
    m = max(c) or 1.0
    return tuple(x / m for x in c)  # type: ignore[return-value]


# ------------------------------------------------------------------ blackbody
def blackbody_xy(temp_k: float) -> tuple[float, float]:
    """CIE 1931 xy of a Planckian radiator, Kim et al. (2002) cubic splines, 1667-25000 K."""
    t = clamp(temp_k, 1667.0, 25000.0)
    if t <= 4000.0:
        x = -0.2661239e9 / t ** 3 - 0.2343589e6 / t ** 2 + 0.8776956e3 / t + 0.179910
    else:
        x = -3.0258469e9 / t ** 3 + 2.1070379e6 / t ** 2 + 0.2226347e3 / t + 0.240390
    if t <= 2222.0:
        y = -1.1063814 * x ** 3 - 1.34811020 * x ** 2 + 2.18555832 * x - 0.20219683
    elif t <= 4000.0:
        y = -0.9549476 * x ** 3 - 1.37418593 * x ** 2 + 2.09137015 * x - 0.16748867
    else:
        y = 3.0817580 * x ** 3 - 5.87338670 * x ** 2 + 3.75112997 * x - 0.37001483
    return x, y


def xy_to_linear_srgb(x: float, y: float) -> tuple[float, float, float]:
    Y = 1.0
    X = x / y * Y
    Z = (1.0 - x - y) / y * Y
    r = 3.2404542 * X - 1.5371385 * Y - 0.4985314 * Z
    g = -0.9692660 * X + 1.8760108 * Y + 0.0415560 * Z
    b = 0.0556434 * X - 0.2040259 * Y + 1.0572252 * Z
    return r, g, b


def blackbody_rgb(temp_k: float) -> tuple[float, float, float]:
    """Linear sRGB of a blackbody, scaled so the largest channel is 1."""
    r, g, b = xy_to_linear_srgb(*blackbody_xy(temp_k))
    r, g, b = max(r, 0.0), max(g, 0.0), max(b, 0.0)
    m = max(r, g, b) or 1.0
    return r / m, g / m, b / m


def bv_to_temperature(bv: float) -> float:
    """Star colour index B-V -> effective temperature, Ballesteros (2012)."""
    return 4600.0 * (1.0 / (0.92 * bv + 1.7) + 1.0 / (0.92 * bv + 0.62))


def star_rgb(bv: float, saturation: float = 0.65) -> tuple[float, float, float]:
    """Display colour of a star from B-V, desaturated toward white (human night vision is nearly achromatic)."""
    r, g, b = blackbody_rgb(clamp(bv_to_temperature(bv), 2500.0, 25000.0))
    return tuple(lerp(1.0, c, saturation) for c in (r, g, b))  # type: ignore[return-value]


# ------------------------------------------------------------------------ moon
def moon_apparent_magnitude(phase_angle_deg: float) -> float:
    """Apparent visual magnitude of the Moon, Allen (1976): -12.73 + 0.026|a| + 4e-9 a^4."""
    a = abs(phase_angle_deg)
    return -12.73 + 0.026 * a + 4.0e-9 * a ** 4


def illuminance_from_magnitude(m: float) -> float:
    """Illuminance in lux at the top of the atmosphere from apparent magnitude: 10^(-0.4 (m + 14.18))."""
    return 10.0 ** (-0.4 * (m + 14.18))


def moon_illuminance_lux(phase_angle_deg: float, elevation_deg: float, distance_km: float = 384400.0,
                         extinction_tau: float = 0.3) -> float:
    """Illuminance from the Moon at ground level (lux). Full moon at zenith ~0.25 lux."""
    if elevation_deg <= -1.0:
        return 0.0
    e = illuminance_from_magnitude(moon_apparent_magnitude(phase_angle_deg))
    e *= (384400.0 / distance_km) ** 2
    return e * math.exp(-extinction_tau * airmass(elevation_deg))


def moon_lamp_strength(phase_angle_deg: float, elevation_deg: float, anchor: float = 0.12,
                       distance_km: float = 384400.0) -> float:
    """Blender Sun-lamp strength for moonlight.

    ``anchor`` is the strength of a full moon at the zenith. The ratio to that reference
    is physical; the absolute anchor is artistic because a physical value (~1e-5 W/m2)
    needs 18 stops of exposure compensation.
    """
    ref = moon_illuminance_lux(0.0, 90.0)
    return anchor * moon_illuminance_lux(phase_angle_deg, elevation_deg, distance_km) / ref


def moon_illuminated_fraction(phase_angle_deg: float) -> float:
    return 0.5 * (1.0 + math.cos(math.radians(phase_angle_deg)))


MOON_LIGHT_TEMPERATURE_K = 4100.0       # reflected sunlight is redder than the Sun


# ----------------------------------------------------------------------- stars
def star_flux(magnitude: float) -> float:
    """Relative flux, 1 at magnitude 0 (Pogson: 100^(-m/5))."""
    return 10.0 ** (-0.4 * magnitude)


def twilight_name(sun_elevation_deg: float) -> str:
    h = sun_elevation_deg
    if h > 0.0:
        return "day"
    if h > -6.0:
        return "civil twilight"
    if h > -12.0:
        return "nautical twilight"
    if h > -18.0:
        return "astronomical twilight"
    return "night"


def limiting_magnitude(sun_elevation_deg: float, moon_elevation_deg: float = -90.0,
                       moon_fraction: float = 0.0, base: float = 6.5, clouds: float = 0.0) -> float:
    """Faintest naked-eye star magnitude under the current sky brightness (empirical).

    Twilight: the limit climbs from about -4 (daylight, Venus only) to ``base`` over 0 to -18 degrees of
    sun elevation. Moonlight: loses up to ~2.5 mag for a full moon high in the sky. Cloud cover removes more.
    """
    t = smoothstep(0.0, -18.0, sun_elevation_deg)
    # perceptual: brightness falls exponentially with depression, so ease toward the end
    m = lerp(-4.0, base, t ** 0.8)
    if moon_elevation_deg > 0.0:
        m -= 2.5 * moon_fraction * math.sin(math.radians(min(moon_elevation_deg, 90.0))) ** 0.7
    return m - 3.0 * clamp(clouds)


def sky_ambient_scale(sun_elevation_deg: float) -> float:
    """Relative ground-albedo brightness feeding the below-horizon dome (0 night .. 1 day)."""
    return smoothstep(-6.0, 20.0, sun_elevation_deg) * 0.85 + 0.01


def cloud_lit_color(sun_elevation_deg: float, aerosol_beta: float = 0.05) -> tuple[float, float, float]:
    """Colour of a sunlit high cloud deck (white-ish, tinted by the beam reaching it).

    Clouds are far above most of the air mass, so the reddening is weaker than at the ground.
    """
    h = max(sun_elevation_deg, -4.0)
    t = sun_transmittance_rgb(h, aerosol_beta * 0.4)
    m = max(t) or 1.0
    k = smoothstep(-6.0, 6.0, sun_elevation_deg)
    base = tuple(0.85 + 0.15 * (x / m) for x in t)
    return tuple(c * k for c in base)  # type: ignore[return-value]


def exposure_ev(illuminance_lux: float, reference_lux: float = SUN_LUX_ZENITH_CLEAR,
                compensation: float = 0.0) -> float:
    """EV that maps scene illuminance to display mid-grey, with partial compensation in [0, 1]."""
    if illuminance_lux <= 0:
        return 0.0
    return compensation * math.log2(reference_lux / illuminance_lux)


# ---------------------------------------------------------------------- clouds
CLOUD_TYPE_ALTITUDES_M = {
    # genus: (base_min, base_max, typical thickness) - WMO International Cloud Atlas levels, mid-latitudes
    "stratus": (0.0, 600.0, 400.0),
    "stratocumulus": (400.0, 2000.0, 500.0),
    "cumulus": (600.0, 2000.0, 1200.0),
    "cumulonimbus": (600.0, 2000.0, 8000.0),
    "altocumulus": (2000.0, 6000.0, 600.0),
    "altostratus": (2000.0, 6000.0, 1500.0),
    "cirrus": (6000.0, 12000.0, 800.0),
}


def cloud_optical_depth(extinction_per_m: float, thickness_m: float, mean_fill: float = 0.5) -> float:
    """Rough optical depth through a layer; real cumulus has tau 5-50, stratus 5-30, cirrus 0.03-3."""
    return extinction_per_m * thickness_m * mean_fill


def cloud_transmission_estimate(coverage: float, optical_depth: float) -> float:
    """Fraction of direct sun reaching the ground averaged over a layer (random-overlap approximation)."""
    return 1.0 - clamp(coverage) * (1.0 - math.exp(-optical_depth))


def horizon_distance_m(height_m: float, radius_m: float = EARTH_RADIUS_M) -> float:
    """Geometric distance to the horizon from a viewpoint ``height_m`` above a sphere."""
    return math.sqrt(2.0 * radius_m * height_m + height_m * height_m)


def apparent_angular_diameter_deg(true_diameter_m: float, distance_m: float) -> float:
    return math.degrees(2.0 * math.atan(0.5 * true_diameter_m / distance_m))
