"""Ephemeris for AtmosFX: Sun, Moon, sidereal time, celestial-to-scene rotation matrices.

Pure Python, no ``bpy``. Sources (algorithms only, implemented from the published formulae):

* Jean Meeus, *Astronomical Algorithms* 2nd ed.: ch. 7 (Julian day), ch. 12 (sidereal time),
  ch. 25 (low-accuracy Sun), ch. 47 (Moon, truncated series), ch. 16 (refraction, Bennett),
  ch. 48 (phase angle).
* IAU 1976 precession angles (Lieske et al.) for J2000 star coordinates.
* Hipparcos galactic frame matrix (ESA SP-1200, vol. 1, sec. 1.5.3).

Accuracy: Sun ~0.01 degree, Moon ~0.02 degree (28 longitude terms), stars limited by precession
(no nutation, no proper motion). Plenty for a sky render; not a navigation tool.

Conventions: scene +X = east, +Y = north, +Z = up when ``north_offset_deg`` is 0. Azimuth is measured
from north through east. ``north_offset_deg`` is the compass bearing of the scene's +Y axis.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

D2R = math.pi / 180.0
R2D = 180.0 / math.pi
J2000 = 2451545.0
SYNODIC_MONTH_DAYS = 29.530588853

Mat3 = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
Vec3 = tuple[float, float, float]


# ------------------------------------------------------------------ linear algebra
def mat_mul(a: Mat3, b: Mat3) -> Mat3:
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))  # type: ignore


def mat_vec(m: Mat3, v: Vec3) -> Vec3:
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))  # type: ignore


def transpose(m: Mat3) -> Mat3:
    return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))  # type: ignore


def rot_x(a: float) -> Mat3:
    c, s = math.cos(a), math.sin(a)
    return ((1, 0, 0), (0, c, -s), (0, s, c))


def rot_y(a: float) -> Mat3:
    c, s = math.cos(a), math.sin(a)
    return ((c, 0, s), (0, 1, 0), (-s, 0, c))


def rot_z(a: float) -> Mat3:
    c, s = math.cos(a), math.sin(a)
    return ((c, -s, 0), (s, c, 0), (0, 0, 1))


def euler_xyz(m: Mat3) -> Vec3:
    """Euler angles (radians) of ``m = Rz(c) @ Ry(b) @ Rx(a)``, i.e. Blender's 'XYZ' order."""
    sy = -m[2][0]
    b = math.asin(max(-1.0, min(1.0, sy)))
    if abs(sy) < 0.999999:
        a = math.atan2(m[2][1], m[2][2])
        c = math.atan2(m[1][0], m[0][0])
    else:                                    # gimbal lock: fold roll into a
        a = math.atan2(-m[1][2], m[1][1])
        c = 0.0
    return a, b, c


def euler_xyz_to_matrix(e: Vec3) -> Mat3:
    return mat_mul(rot_z(e[2]), mat_mul(rot_y(e[1]), rot_x(e[0])))


def unit(v: Vec3) -> Vec3:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def angular_separation_deg(a: Vec3, b: Vec3) -> float:
    d = max(-1.0, min(1.0, sum(x * y for x, y in zip(unit(a), unit(b)))))
    return math.acos(d) * R2D


def radec_to_vec(ra_deg: float, dec_deg: float) -> Vec3:
    ra, dec = ra_deg * D2R, dec_deg * D2R
    return (math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec))


def vec_to_radec(v: Vec3) -> tuple[float, float]:
    ra = math.atan2(v[1], v[0]) * R2D % 360.0
    dec = math.asin(max(-1.0, min(1.0, v[2]))) * R2D
    return ra, dec


# ------------------------------------------------------------------------ time
def jd_from_datetime(dt: datetime) -> float:
    """Julian date (UT) of an aware or naive-UTC datetime. Meeus ch. 7, Gregorian calendar."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    y, m = dt.year, dt.month
    d = dt.day + (dt.hour + (dt.minute + (dt.second + dt.microsecond / 1e6) / 60.0) / 60.0) / 24.0
    if m <= 2:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + b - 1524.5


def utc_from_local(year: int, month: int, day: int, hour: float, utc_offset_h: float) -> datetime:
    """UTC datetime for a local civil date and fractional hour (hour may be negative or exceed 24)."""
    local = datetime(year, month, day, tzinfo=timezone.utc) + timedelta(hours=hour)
    return local - timedelta(hours=utc_offset_h)


def jd_from_local(year: int, month: int, day: int, hour: float, utc_offset_h: float) -> float:
    return jd_from_datetime(utc_from_local(year, month, day, hour, utc_offset_h))


def centuries(jd: float) -> float:
    return (jd - J2000) / 36525.0


def gmst_deg(jd: float) -> float:
    """Greenwich mean sidereal time in degrees. Meeus eq. 12.4."""
    t = centuries(jd)
    return (280.46061837 + 360.98564736629 * (jd - J2000) + 0.000387933 * t * t - t ** 3 / 38710000.0) % 360.0


def local_sidereal_deg(jd: float, lon_deg: float) -> float:
    return (gmst_deg(jd) + lon_deg) % 360.0


# ------------------------------------------------------------------------- sun
def sun_equatorial(jd: float) -> dict:
    """Apparent Sun, Meeus ch. 25 (0.01 degree). Returns ra, dec (deg), distance (AU), ecliptic longitude."""
    t = centuries(jd)
    l0 = (280.46646 + 36000.76983 * t + 0.0003032 * t * t) % 360.0
    m = (357.52911 + 35999.05029 * t - 0.0001537 * t * t) % 360.0
    e = 0.016708634 - 0.000042037 * t - 0.0000001267 * t * t
    mr = m * D2R
    c = ((1.914602 - 0.004817 * t - 0.000014 * t * t) * math.sin(mr)
         + (0.019993 - 0.000101 * t) * math.sin(2 * mr) + 0.000289 * math.sin(3 * mr))
    true_lon = l0 + c
    nu = m + c
    r_au = 1.000001018 * (1 - e * e) / (1 + e * math.cos(nu * D2R))
    omega = 125.04 - 1934.136 * t
    lam = true_lon - 0.00569 - 0.00478 * math.sin(omega * D2R)
    eps0 = 23.0 + (26.0 + (21.448 - t * (46.8150 + t * (0.00059 - t * 0.001813))) / 60.0) / 60.0
    eps = eps0 + 0.00256 * math.cos(omega * D2R)
    lr, er = lam * D2R, eps * D2R
    ra = math.atan2(math.cos(er) * math.sin(lr), math.cos(lr)) * R2D % 360.0
    dec = math.asin(math.sin(er) * math.sin(lr)) * R2D
    return {"ra": ra, "dec": dec, "distance_au": r_au, "lon": lam % 360.0, "obliquity": eps}


# ------------------------------------------------------------------------ moon
# Meeus Table 47.A: (D, M, M', F, sum_l [1e-6 deg], sum_r [1e-3 km])
_MOON_LR = (
    (0, 0, 1, 0, 6288774, -20905355), (2, 0, -1, 0, 1274027, -3699111), (2, 0, 0, 0, 658314, -2955968),
    (0, 0, 2, 0, 213618, -569925), (0, 1, 0, 0, -185116, 48888), (0, 0, 0, 2, -114332, -3149),
    (2, 0, -2, 0, 58793, 246158), (2, -1, -1, 0, 57066, -152138), (2, 0, 1, 0, 53322, -170733),
    (2, -1, 0, 0, 45758, -204586), (0, 1, -1, 0, -40923, -129620), (1, 0, 0, 0, -34720, 108743),
    (0, 1, 1, 0, -30383, 104755), (2, 0, 0, -2, 15327, 10321), (0, 0, 1, 2, -12528, 0),
    (0, 0, 1, -2, 10980, 79661), (4, 0, -1, 0, 10675, -34782), (0, 0, 3, 0, 10034, -23210),
    (4, 0, -2, 0, 8548, -21636), (2, 1, -1, 0, -7888, 24208), (2, 1, 0, 0, -6766, 30824),
    (1, 0, -1, 0, -5163, -8379), (1, 1, 0, 0, 4987, -16675), (2, -1, 1, 0, 4036, -12831),
    (2, 0, 2, 0, 3994, -10445), (4, 0, 0, 0, 3861, -11650), (2, 0, -3, 0, 3665, 14403),
    (0, 1, -2, 0, -2689, -7003), (2, 0, -1, 2, -2602, 0), (2, -1, -2, 0, 2390, 10056),
    (1, 0, 1, 0, -2348, 6322), (2, -2, 0, 0, 2236, -9884),
)
# Meeus Table 47.B: (D, M, M', F, sum_b [1e-6 deg])
_MOON_B = (
    (0, 0, 0, 1, 5128122), (0, 0, 1, 1, 280602), (0, 0, 1, -1, 277693), (2, 0, 0, -1, 173237),
    (2, 0, -1, 1, 55413), (2, 0, -1, -1, 46271), (2, 0, 0, 1, 32573), (0, 0, 2, 1, 17198),
    (2, 0, 1, -1, 9266), (0, 0, 2, -1, 8822), (2, -1, 0, -1, 8216), (2, 0, -2, -1, 4324),
    (2, 0, 1, 1, 4200), (2, 1, 0, -1, -3359), (2, -1, -1, 1, 2463), (2, -1, 0, 1, 2211),
    (2, -1, -1, -1, 2065), (0, 1, -1, -1, -1870), (4, 0, -1, -1, 1828), (0, 1, 0, 1, -1794),
    (0, 0, 0, 3, -1749), (0, 1, -1, 1, -1565), (1, 0, 0, 1, -1491), (0, 1, 1, 1, -1475),
    (0, 1, 1, -1, -1410), (0, 1, 0, -1, -1344), (1, 0, 0, -1, -1335), (0, 0, 3, 1, 1107),
    (4, 0, 0, -1, 1021), (4, 0, -1, 1, 833),
)


def moon_ecliptic(jd: float) -> dict:
    """Geocentric Moon, Meeus ch. 47 truncated: longitude/latitude (deg), distance (km)."""
    t = centuries(jd)
    lp = 218.3164477 + 481267.88123421 * t - 0.0015786 * t * t + t ** 3 / 538841.0 - t ** 4 / 65194000.0
    d = 297.8501921 + 445267.1114034 * t - 0.0018819 * t * t + t ** 3 / 545868.0 - t ** 4 / 113065000.0
    m = 357.5291092 + 35999.0502909 * t - 0.0001536 * t * t + t ** 3 / 24490000.0
    mp = 134.9633964 + 477198.8675055 * t + 0.0087414 * t * t + t ** 3 / 69699.0 - t ** 4 / 14712000.0
    f = 93.2720950 + 483202.0175233 * t - 0.0036539 * t * t - t ** 3 / 3526000.0 + t ** 4 / 863310000.0
    a1 = (119.75 + 131.849 * t) * D2R
    a2 = (53.09 + 479264.290 * t) * D2R
    a3 = (313.45 + 481266.484 * t) * D2R
    e = 1.0 - 0.002516 * t - 0.0000074 * t * t
    dr, mr, mpr, fr = d * D2R, m * D2R, mp * D2R, f * D2R
    sl = sr = sb = 0.0
    for cd, cm, cmp_, cf, l, r in _MOON_LR:
        arg = cd * dr + cm * mr + cmp_ * mpr + cf * fr
        ef = e ** abs(cm)
        sl += l * ef * math.sin(arg)
        sr += r * ef * math.cos(arg)
    for cd, cm, cmp_, cf, b in _MOON_B:
        arg = cd * dr + cm * mr + cmp_ * mpr + cf * fr
        sb += b * (e ** abs(cm)) * math.sin(arg)
    lpr = lp * D2R
    sl += 3958 * math.sin(a1) + 1962 * math.sin(lpr - fr) + 318 * math.sin(a2)
    sb += (-2235 * math.sin(lpr) + 382 * math.sin(a3) + 175 * math.sin(a1 - fr)
           + 175 * math.sin(a1 + fr) + 127 * math.sin(lpr - mpr) - 115 * math.sin(lpr + mpr))
    return {"lon": (lp + sl / 1e6) % 360.0, "lat": sb / 1e6, "distance_km": 385000.56 + sr / 1e3}


def moon_equatorial(jd: float) -> dict:
    ecl = moon_ecliptic(jd)
    t = centuries(jd)
    omega = 125.04452 - 1934.136261 * t
    eps = (23.439291 - 0.0130042 * t) + 0.00256 * math.cos(omega * D2R)   # mean + nutation in obliquity
    lam, bet, er = ecl["lon"] * D2R, ecl["lat"] * D2R, eps * D2R
    ra = math.atan2(math.sin(lam) * math.cos(er) - math.tan(bet) * math.sin(er), math.cos(lam)) * R2D % 360.0
    dec = math.asin(math.sin(bet) * math.cos(er) + math.cos(bet) * math.sin(er) * math.sin(lam)) * R2D
    return {"ra": ra, "dec": dec, "distance_km": ecl["distance_km"], "lon": ecl["lon"], "lat": ecl["lat"]}


# ------------------------------------------------------------------- precession
def precession_matrix(jd: float) -> Mat3:
    """J2000 equatorial -> mean equator of date (IAU 1976 angles zeta, z, theta)."""
    t = centuries(jd)
    zeta = (2306.2181 * t + 0.30188 * t * t + 0.017998 * t ** 3) / 3600.0 * D2R
    z = (2306.2181 * t + 1.09468 * t * t + 0.018203 * t ** 3) / 3600.0 * D2R
    theta = (2004.3109 * t - 0.42665 * t * t - 0.041833 * t ** 3) / 3600.0 * D2R
    return mat_mul(rot_z(-z), mat_mul(rot_y(theta), rot_z(-zeta)))


# Hipparcos: J2000 equatorial -> galactic (rows = galactic x, y, z axes in equatorial coordinates)
GALACTIC_FROM_J2000: Mat3 = (
    (-0.0548755604, -0.8734370902, -0.4838350155),
    (0.4941094279, -0.4448296300, 0.7469822445),
    (-0.8676661490, -0.1980763734, 0.4559837762),
)


# ----------------------------------------------------------- horizon coordinates
def equatorial_to_enu(ra_deg: float, dec_deg: float, lst_deg: float, lat_deg: float) -> Vec3:
    """Unit vector (east, north, up) of an equatorial direction (of date) for an observer."""
    h = (lst_deg - ra_deg) * D2R
    d, p = dec_deg * D2R, lat_deg * D2R
    e = -math.cos(d) * math.sin(h)
    n = -math.sin(p) * math.cos(d) * math.cos(h) + math.cos(p) * math.sin(d)
    u = math.sin(p) * math.sin(d) + math.cos(p) * math.cos(d) * math.cos(h)
    return (e, n, u)


def enu_to_altaz(v: Vec3) -> tuple[float, float]:
    alt = math.asin(max(-1.0, min(1.0, v[2]))) * R2D
    az = math.atan2(v[0], v[1]) * R2D % 360.0
    return alt, az


def altaz_to_enu(alt_deg: float, az_deg: float) -> Vec3:
    a, z = alt_deg * D2R, az_deg * D2R
    return (math.cos(a) * math.sin(z), math.cos(a) * math.cos(z), math.sin(a))


def enu_to_scene(v: Vec3, north_offset_deg: float = 0.0) -> Vec3:
    """Rotate an ENU vector into the scene frame (scene +Y points to bearing ``north_offset_deg``)."""
    return mat_vec(rot_z(north_offset_deg * D2R), v)


def refraction_deg(true_alt_deg: float, pressure_hpa: float = 1010.0, temp_c: float = 10.0) -> float:
    """Atmospheric refraction in degrees, Bennett (1982) with Meeus pressure/temperature factor."""
    h = max(true_alt_deg, -1.9)
    r_arcmin = 1.0 / math.tan((h + 7.31 / (h + 4.4)) * D2R)
    r_arcmin *= (pressure_hpa / 1010.0) * (283.0 / (273.0 + temp_c))
    return r_arcmin / 60.0 if true_alt_deg > -1.9 else 0.0


def equatorial_to_scene_matrix(lst_deg: float, lat_deg: float, north_offset_deg: float = 0.0,
                               jd: float | None = None) -> Mat3:
    """Matrix taking a J2000 equatorial unit vector to the scene frame.

    ``jd`` adds precession; ``None`` treats the vector as already being of date.
    """
    lat = lat_deg * D2R
    # equatorial of date -> hour-angle frame (rotate by -LST about the pole)
    hf = rot_z(-lst_deg * D2R)
    # hour-angle frame -> east, north, up
    a = ((0.0, 1.0, 0.0), (-math.sin(lat), 0.0, math.cos(lat)), (math.cos(lat), 0.0, math.sin(lat)))
    m = mat_mul(rot_z(north_offset_deg * D2R), mat_mul(a, hf))
    if jd is not None:
        m = mat_mul(m, precession_matrix(jd))
    return m


def mapping_rotation_celestial(scene_from_j2000: Mat3) -> Vec3:
    """Euler XYZ (radians) for a Mapping node that takes a scene direction to a J2000 direction."""
    return euler_xyz(transpose(scene_from_j2000))


def mapping_rotation_galactic(scene_from_j2000: Mat3) -> Vec3:
    """Euler XYZ for a Mapping node taking a scene direction to a galactic direction."""
    return euler_xyz(mat_mul(GALACTIC_FROM_J2000, transpose(scene_from_j2000)))


# ------------------------------------------------------------------ sky state
@dataclass(frozen=True)
class SkyState:
    jd: float
    lst_deg: float
    sun_alt_deg: float            # geometric
    sun_alt_app_deg: float        # with refraction
    sun_az_deg: float
    sun_vec: Vec3                 # scene frame, apparent
    sun_distance_au: float
    sun_diameter_deg: float
    moon_alt_deg: float           # topocentric geometric
    moon_alt_app_deg: float
    moon_az_deg: float
    moon_vec: Vec3
    moon_distance_km: float
    moon_diameter_deg: float
    moon_elongation_deg: float
    moon_phase_angle_deg: float
    moon_fraction: float
    moon_waxing: bool
    moon_age_days: float
    moon_light_vec: Vec3          # direction from the Moon toward the Sun, scene frame
    scene_from_j2000: Mat3

    @property
    def moon_phase_name(self) -> str:
        return moon_phase_name(self.moon_fraction, self.moon_waxing)


def moon_phase_name(fraction: float, waxing: bool) -> str:
    if fraction < 0.03:
        return "new moon"
    if fraction > 0.97:
        return "full moon"
    if 0.47 < fraction < 0.53:
        return "first quarter" if waxing else "last quarter"
    if fraction < 0.5:
        return "waxing crescent" if waxing else "waning crescent"
    return "waxing gibbous" if waxing else "waning gibbous"


def compute(jd: float, lat_deg: float, lon_deg: float, north_offset_deg: float = 0.0,
            refraction: bool = True) -> SkyState:
    """Full sky state for a Julian date (UT) and an observer on Earth."""
    lst = local_sidereal_deg(jd, lon_deg)
    sun = sun_equatorial(jd)
    moon = moon_equatorial(jd)

    s_enu = equatorial_to_enu(sun["ra"], sun["dec"], lst, lat_deg)
    s_alt, s_az = enu_to_altaz(s_enu)
    s_alt_app = s_alt + (refraction_deg(s_alt) if refraction else 0.0)

    m_enu = equatorial_to_enu(moon["ra"], moon["dec"], lst, lat_deg)
    m_alt_geo, m_az = enu_to_altaz(m_enu)
    parallax = math.asin(6378.14 / moon["distance_km"]) * R2D
    m_alt = m_alt_geo - parallax * math.cos(m_alt_geo * D2R)            # topocentric (to first order)
    m_alt_app = m_alt + (refraction_deg(m_alt) if refraction else 0.0)

    s_vec = enu_to_scene(altaz_to_enu(s_alt_app, s_az), north_offset_deg)
    m_vec = enu_to_scene(altaz_to_enu(m_alt_app, m_az), north_offset_deg)

    # phase (Meeus ch. 48)
    cos_psi = (math.sin(sun["dec"] * D2R) * math.sin(moon["dec"] * D2R)
               + math.cos(sun["dec"] * D2R) * math.cos(moon["dec"] * D2R) * math.cos((sun["ra"] - moon["ra"]) * D2R))
    psi = math.acos(max(-1.0, min(1.0, cos_psi)))
    r_sun_km = sun["distance_au"] * 149597870.7
    i = math.atan2(r_sun_km * math.sin(psi), moon["distance_km"] - r_sun_km * math.cos(psi))
    phase_angle = i * R2D
    fraction = 0.5 * (1.0 + math.cos(i))
    dlon = (moon["lon"] - sun["lon"]) % 360.0
    waxing = dlon < 180.0
    age = dlon / 360.0 * SYNODIC_MONTH_DAYS

    # direction toward the Sun as seen from the Moon (parallel rays): the geocentric Sun direction
    sun_dir_scene = enu_to_scene(s_enu, north_offset_deg)

    return SkyState(
        jd=jd, lst_deg=lst, sun_alt_deg=s_alt, sun_alt_app_deg=s_alt_app, sun_az_deg=s_az, sun_vec=s_vec,
        sun_distance_au=sun["distance_au"],
        sun_diameter_deg=0.5334 / sun["distance_au"],
        moon_alt_deg=m_alt, moon_alt_app_deg=m_alt_app, moon_az_deg=m_az, moon_vec=m_vec,
        moon_distance_km=moon["distance_km"], moon_diameter_deg=0.5286 * 384400.0 / moon["distance_km"],
        moon_elongation_deg=psi * R2D, moon_phase_angle_deg=phase_angle, moon_fraction=fraction,
        moon_waxing=waxing, moon_age_days=age, moon_light_vec=sun_dir_scene,
        scene_from_j2000=equatorial_to_scene_matrix(lst, lat_deg, north_offset_deg, jd),
    )


def compute_local(year: int, month: int, day: int, hour: float, utc_offset_h: float,
                  lat_deg: float, lon_deg: float, north_offset_deg: float = 0.0,
                  refraction: bool = True) -> SkyState:
    return compute(jd_from_local(year, month, day, hour, utc_offset_h), lat_deg, lon_deg,
                   north_offset_deg, refraction)


# --------------------------------------------------------------- artistic mode
def artistic_sun(elevation_deg: float, azimuth_deg: float) -> Vec3:
    """Scene vector of a hand-placed sun (azimuth from +Y toward +X, matching the Sky Texture node)."""
    return altaz_to_enu(elevation_deg, azimuth_deg)


def phase_to_angle_deg(phase: float) -> tuple[float, bool, float]:
    """Moon phase 0..1 (0 new, 0.25 first quarter, 0.5 full, 0.75 last quarter) ->
    (phase angle deg, waxing, illuminated fraction)."""
    p = phase % 1.0
    k = 0.5 * (1.0 - math.cos(2.0 * math.pi * p))
    return math.acos(max(-1.0, min(1.0, 2.0 * k - 1.0))) * R2D, p < 0.5, k


def artistic_moon_light_dir(moon_vec: Vec3, phase_angle_deg: float, waxing: bool) -> Vec3:
    """Direction from the Moon to the 'Sun' that produces the requested phase for a hand-placed Moon.

    Convention: seen by a level observer looking at the Moon, a waxing Moon is lit on the right
    (west when facing south in the northern hemisphere), a waning Moon on the left.
    """
    psi = (180.0 - phase_angle_deg) * D2R                               # elongation
    up = (0.0, 0.0, 1.0)
    right = (moon_vec[1] * up[2] - moon_vec[2] * up[1], moon_vec[2] * up[0] - moon_vec[0] * up[2],
             moon_vec[0] * up[1] - moon_vec[1] * up[0])                  # moon x up
    if math.sqrt(sum(x * x for x in right)) < 1e-6:                     # Moon at the zenith
        right = (1.0, 0.0, 0.0)
    right = unit(right)
    if not waxing:
        right = (-right[0], -right[1], -right[2])
    c, s = math.cos(psi), math.sin(psi)
    return unit(tuple(c * m + s * r for m, r in zip(moon_vec, right)))  # type: ignore[arg-type]


# ----------------------------------------------------------------- sun events
def sun_altitude_local(year: int, month: int, day: int, hour: float, utc_offset_h: float,
                       lat_deg: float, lon_deg: float) -> float:
    jd = jd_from_local(year, month, day, hour, utc_offset_h)
    lst = local_sidereal_deg(jd, lon_deg)
    s = sun_equatorial(jd)
    return enu_to_altaz(equatorial_to_enu(s["ra"], s["dec"], lst, lat_deg))[0]


def sun_events(year: int, month: int, day: int, utc_offset_h: float, lat_deg: float, lon_deg: float,
               threshold_deg: float = -0.833) -> dict:
    """Local civil hour of sunrise, solar noon and sunset (None when the Sun never crosses).

    Bisection on the altitude with the standard -0.833 degree threshold (refraction + semi-diameter).
    """
    step = 10.0 / 60.0
    samples = [(h * step, sun_altitude_local(year, month, day, h * step, utc_offset_h, lat_deg, lon_deg))
               for h in range(int(24 / step) + 1)]
    noon = max(samples, key=lambda s: s[1])
    rise = set_ = None

    def refine(h0: float, h1: float) -> float:
        a0 = sun_altitude_local(year, month, day, h0, utc_offset_h, lat_deg, lon_deg) - threshold_deg
        for _ in range(40):
            hm = 0.5 * (h0 + h1)
            am = sun_altitude_local(year, month, day, hm, utc_offset_h, lat_deg, lon_deg) - threshold_deg
            if (a0 < 0) == (am < 0):
                h0, a0 = hm, am
            else:
                h1 = hm
        return 0.5 * (h0 + h1)

    for (h0, a0), (h1, a1) in zip(samples, samples[1:]):
        if a0 < threshold_deg <= a1 and rise is None:
            rise = refine(h0, h1)
        if a0 >= threshold_deg > a1 and set_ is None:
            set_ = refine(h0, h1)
    return {"sunrise": rise, "sunset": set_, "noon": noon[0], "noon_altitude": noon[1]}


def format_hour(h: float | None) -> str:
    if h is None:
        return "--:--"
    total = int(round(h * 60.0)) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"
