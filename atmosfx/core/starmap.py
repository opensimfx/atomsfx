"""Bake the star sphere into an equirectangular float array (J2000 equatorial frame).

* Real stars come from ``stars_data.CATALOG`` (about 120 stars to magnitude 3.7).
* The rest of the naked-eye sky (to ``mag_limit``) is synthesised with the observed star-count law
  ``N(<m) = 171 * 3.1**(m - 3)`` (Bright Star Catalogue counts), denser toward the galactic plane.
* Each star is a Gaussian point-spread whose width grows slowly with brightness, so bright stars read
  larger on screen; its peak value is flux relative to a limiting-magnitude star, so the shader can
  threshold on pixel luminance to implement a limiting magnitude.

The array uses Blender's environment-texture convention (row 0 is the south pole, ``u = 0.5 - atan2(y, x) / 2pi``),
and ``numpy`` is imported lazily so the rest of ``core`` stays dependency-free.
"""
from __future__ import annotations

import math

from . import astro, physics
from .identity import state_hash
from .stars_data import CATALOG, CATALOG_VERSION

REF_MAG = 6.5            # the faintest star the bake can contain; its peak value is 1.0
SIGMA_REF_PX = 0.75      # point-spread sigma of a limiting star, in pixels


def equirect_to_dir(u: float, v: float) -> tuple[float, float, float]:
    """Direction for texture coordinates (u, v in 0..1), Blender environment-texture convention.

    Measured on Blender 5.0.1: +X is at u = 0.5, +Y at u = 0.25, -Y at u = 0.75, and v = 0.5 + asin(z) / pi.
    """
    lon = (0.5 - u) * 2.0 * math.pi
    lat = (v - 0.5) * math.pi
    return (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))


def dir_to_equirect(d: tuple[float, float, float]) -> tuple[float, float]:
    u = 0.5 - math.atan2(d[1], d[0]) / (2.0 * math.pi)
    v = math.atan2(d[2], math.hypot(d[0], d[1])) / math.pi + 0.5
    return u, v


def star_sigma_px(mag: float) -> float:
    return min(SIGMA_REF_PX + 0.22 * max(0.0, 3.0 - mag), 2.2)


def star_peak(mag: float) -> float:
    """Peak pixel value of a star: flux relative to REF_MAG, normalised by its point-spread area."""
    s = star_sigma_px(mag)
    return (physics.star_flux(mag) / physics.star_flux(REF_MAG)) * (SIGMA_REF_PX / s) ** 2


def luminance_threshold(mag_limit: float) -> float:
    """Pixel-luminance threshold that hides stars fainter than ``mag_limit`` (used by the shader)."""
    return physics.star_flux(mag_limit) / physics.star_flux(REF_MAG) * 0.6


def count_below(mag: float) -> float:
    return 171.0 * 3.1 ** (mag - 3.0)


def bake_key(width: int, height: int, seed: int, mag_limit: float, density: float) -> str:
    return state_hash({"v": CATALOG_VERSION, "w": width, "h": height, "seed": seed,
                       "limit": round(mag_limit, 2), "density": round(density, 3)})[:10]


def _synthetic_stars(rng, mag_limit: float, density: float, n_real: int):
    """Positions (J2000 unit vectors), magnitudes and B-V for the stars not in the catalogue."""
    import numpy as np

    total = int(count_below(mag_limit) * density) - n_real
    if total <= 0:
        return np.zeros((0, 3)), np.zeros(0), np.zeros(0)
    # magnitudes: inverse CDF of N(<m) restricted to [2.8, mag_limit]
    m0 = 2.8
    c0, c1 = count_below(m0), count_below(mag_limit)
    u = rng.random(total)
    mags = 3.0 + np.log((u * (c1 - c0) + c0) / 171.0) / math.log(3.1)
    # positions: uniform on the sphere with galactic-plane weighting (rejection sampling)
    g = np.array(astro.GALACTIC_FROM_J2000)
    vecs = np.empty((0, 3))
    while len(vecs) < total:
        n = (total - len(vecs)) * 3 + 64
        v = rng.normal(size=(n, 3))
        v /= np.linalg.norm(v, axis=1, keepdims=True)
        b = np.degrees(np.arcsin(np.clip((v @ g.T)[:, 2], -1, 1)))
        w = (1.0 + 2.5 * np.exp(-((b / 15.0) ** 2))) / 3.5
        keep = rng.random(n) < w
        vecs = np.vstack([vecs, v[keep]])
    vecs = vecs[:total]
    bv = np.clip(rng.normal(0.7, 0.45, size=total), -0.2, 1.8)
    return vecs, mags, bv


def bake_star_map(width: int = 4096, height: int = 2048, seed: int = 1, mag_limit: float = REF_MAG,
                  density: float = 1.0):
    """Return a float32 array (height, width, 3). Row 0 = south pole."""
    import numpy as np

    mag_limit = min(mag_limit, REF_MAG)
    rng = np.random.default_rng(seed)
    img = np.zeros((height, width, 3), dtype=np.float32)

    cat = [s for s in CATALOG if s.mag <= mag_limit]
    syn_v, syn_m, syn_bv = _synthetic_stars(rng, mag_limit, density, len(cat))

    stars = [(astro.radec_to_vec(s.ra_deg, s.dec_deg), s.mag, s.bv) for s in cat]
    stars += [(tuple(v), float(m), float(b)) for v, m, b in zip(syn_v, syn_m, syn_bv)]

    lat_rows = ((np.arange(height) + 0.5) / height - 0.5) * math.pi
    lon_cols = (0.5 - (np.arange(width) + 0.5) / width) * 2.0 * math.pi
    sin_lat, cos_lat = np.sin(lat_rows), np.cos(lat_rows)
    px_rad = math.pi / height

    color_cache: dict[int, tuple[float, float, float]] = {}
    for d, mag, bv in stars:
        u, v = dir_to_equirect(d)
        cx, cy = u * width - 0.5, v * height - 0.5
        sig = star_sigma_px(mag)
        sig_th = sig * px_rad
        lat0 = math.asin(max(-1.0, min(1.0, d[2])))
        wy = int(math.ceil(4.0 * sig))
        wx = int(math.ceil(4.0 * sig / max(math.cos(lat0), 0.05)))
        wx = min(wx, width // 2 - 1)
        y0, y1 = max(int(round(cy)) - wy, 0), min(int(round(cy)) + wy + 1, height)
        xs = (np.arange(int(round(cx)) - wx, int(round(cx)) + wx + 1)) % width
        if y1 <= y0:
            continue
        sl, cl = sin_lat[y0:y1][:, None], cos_lat[y0:y1][:, None]
        lon = lon_cols[xs][None, :]
        lon0 = (0.5 - u) * 2.0 * math.pi
        cos_t = sl * math.sin(lat0) + cl * math.cos(lat0) * np.cos(lon - lon0)
        theta2 = 2.0 * (1.0 - np.clip(cos_t, -1.0, 1.0))               # ~theta^2 for small angles
        prof = np.exp(-theta2 / (2.0 * sig_th * sig_th)) * star_peak(mag)
        key = int(round(bv * 20))
        rgb = color_cache.get(key)
        if rgb is None:
            rgb = color_cache[key] = physics.star_rgb(key / 20.0)
        patch = prof[..., None] * np.array(rgb, dtype=np.float32)[None, None, :]
        rows = slice(y0, y1)
        img[rows][:, xs, :] += patch.astype(np.float32)
    return img


def bake_stats(img) -> dict:
    """Small summary used by tests and the diagnostics panel."""
    import numpy as np

    lum = img @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    return {"max": float(lum.max()), "mean": float(lum.mean()), "lit_fraction": float((lum > 0.1).mean())}
