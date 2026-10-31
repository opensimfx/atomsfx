"""Cloud genera and the mapping from a layer description to shader parameters. No ``bpy``.

Cloud layers are volumetric domains (a cylinder of ``radius_m`` x ``thickness_m``) rendered by one shared
node group. This module decides *what* the group receives, so the numbers are testable and documented:

* a **kind** supplies a height profile (flat-based cumulus, rounded tops, anvils) and anisotropy;
* **coverage** [0..1] maps to a density-field threshold so 0 is clear and 1 is overcast;
* **scale_m** is the size of the largest cloud features in metres (noise frequency = 1 / scale);
* **wind** is a velocity; the shader multiplies it by scene time in seconds (frame / fps), so motion is
  frame-rate independent.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CloudKind:
    key: str
    label: str
    altitude_m: float
    thickness_m: float
    coverage: float
    density: float          # peak extinction coefficient [1/m]
    scale_m: float
    detail: float
    anisotropy: float       # forward Henyey-Greenstein g
    bottom_ramp: float      # fraction of the thickness over which density ramps up from the base
    top_ramp: float         # fraction over which it ramps down below the top
    anvil: float            # widening near the top (cumulonimbus)
    stretch: float          # >1 flattens the noise vertically (layered clouds)
    note: str


KINDS: dict[str, CloudKind] = {k.key: k for k in (
    CloudKind("CUMULUS", "Cumulus", 1500.0, 1400.0, 0.40, 0.020, 900.0, 0.60, 0.80, 0.06, 0.45, 0.0, 1.0,
              "Fair-weather puffs with flat bases and cauliflower tops."),
    CloudKind("STRATOCUMULUS", "Stratocumulus", 1200.0, 500.0, 0.60, 0.016, 1400.0, 0.40, 0.78, 0.12, 0.35, 0.0, 2.0,
              "Low lumpy sheet, broken or continuous."),
    CloudKind("STRATUS", "Stratus", 500.0, 400.0, 0.92, 0.012, 2500.0, 0.20, 0.70, 0.20, 0.40, 0.0, 3.0,
              "Uniform grey blanket; sun disc usually hidden."),
    CloudKind("ALTOCUMULUS", "Altocumulus", 4500.0, 600.0, 0.50, 0.012, 600.0, 0.50, 0.80, 0.10, 0.40, 0.0, 1.5,
              "Mid-level cloudlets in rows or patches (mackerel sky)."),
    CloudKind("ALTOSTRATUS", "Altostratus", 4800.0, 1200.0, 0.85, 0.006, 3000.0, 0.20, 0.72, 0.25, 0.40, 0.0, 3.0,
              "Thin grey veil, the sun looks like through frosted glass."),
    CloudKind("CUMULONIMBUS", "Cumulonimbus", 1200.0, 9000.0, 0.25, 0.030, 3500.0, 0.70, 0.85, 0.04, 0.25, 0.8, 0.8,
              "Towering storm cloud with an anvil top."),
    CloudKind("CIRRUS", "Cirrus", 8500.0, 900.0, 0.40, 0.003, 3000.0, 0.60, 0.82, 0.25, 0.40, 0.0, 4.0,
              "High wispy ice-crystal streaks."),
)}

QUALITY_OCTAVES = {"DRAFT": 2.0, "PREVIEW": 4.0, "FINAL": 7.0}
BACK_LOBE_G = -0.25
BACK_LOBE_WEIGHT = 0.25


def kind(key: str) -> CloudKind:
    try:
        return KINDS[key.upper()]
    except KeyError:
        raise KeyError(f"unknown cloud kind {key!r}; choose from {sorted(KINDS)}") from None


FIELD_MEAN = 0.50       # measured mean of the shape field at mid-height (normalised fractal noise)
FIELD_STD = 0.08        # measured standard deviation of that field (cumulonimbus slice: 0.081)
EDGE_SOFTNESS = 0.08    # width of the density ramp above the threshold


def coverage_threshold(coverage: float) -> float:
    """Field level above which cloud exists, chosen so the *filled area fraction* at mid-height equals ``coverage``.

    The shape field is approximately normal (mean 0.50, sd 0.08, measured by rendering a density slice), so the
    threshold is the (1 - coverage) quantile: 0.5 - 0.08 * probit(coverage). Coverage 0 and 1 are exact.
    """
    from statistics import NormalDist

    c = min(max(coverage, 0.0), 1.0)
    if c <= 0.005:
        return 1.5
    if c >= 0.995:
        return -0.5
    return FIELD_MEAN - FIELD_STD * NormalDist().inv_cdf(c)


def wind_vector(speed_ms: float, direction_deg: float) -> tuple[float, float, float]:
    """Velocity toward which the wind blows. ``direction_deg`` is a compass bearing in the scene
    (0 = +Y, 90 = +X)."""
    a = math.radians(direction_deg)
    return (speed_ms * math.sin(a), speed_ms * math.cos(a), 0.0)


def seed_offset(seed: int, span: float = 1000.0) -> tuple[float, float, float]:
    """Stable noise-space offset per seed (so seeds give unrelated but repeatable cloud fields)."""
    h = hashlib.sha1(f"atmosfx-cloud-{int(seed)}".encode()).digest()
    return tuple(((int.from_bytes(h[i * 4:(i + 1) * 4], "little") / 2 ** 32) - 0.5) * span for i in range(3))  # type: ignore


def socket_values(layer, quality: str = "PREVIEW") -> dict:
    """Values for the inputs of the shared cloud node group. ``layer`` is a ``CloudLayerCfg``-like object."""
    k = kind(layer.kind)
    return {
        "Base Altitude": layer.altitude_m,
        "Thickness": layer.thickness_m,
        "Threshold": coverage_threshold(layer.coverage),
        "Softness": EDGE_SOFTNESS,
        "Density": layer.density,
        "Frequency": 1.0 / max(layer.scale_m, 1.0),
        "Detail": layer.detail,
        "Octaves": QUALITY_OCTAVES.get(quality, 4.0),
        "Wind Velocity": wind_vector(layer.wind_speed_ms, layer.wind_dir_deg),
        "Seed Offset": seed_offset(layer.seed),
        "Bottom Ramp": k.bottom_ramp,
        "Top Ramp": k.top_ramp,
        "Anvil": k.anvil,
        "Vertical Stretch": k.stretch,
        "Radius": layer.radius_m,
        "Inner Radius": layer.radius_m * (1.0 - min(max(layer.edge_fade, 0.0), 0.95)),
        "Anisotropy": layer.anisotropy,
        "Back Anisotropy": BACK_LOBE_G,
        "Back Weight": BACK_LOBE_WEIGHT,
    }


def optical_depth(layer, mean_fill: float = 0.5) -> float:
    """Mean optical depth through a layer: ``density x thickness x fill``. A thin layer needs fewer samples."""
    return max(layer.density, 0.0) * max(layer.thickness_m, 0.0) * mean_fill


def step_rate_scale(layers, mean_fill: float = 0.5) -> float:
    """Multiplier for the Cycles volume step rate, from the enabled layers' optical depths.

    Cycles exposes one volume step rate for the whole scene, so a per-layer rate has to be collapsed into
    one: the most demanding layer decides. Dense layers keep the quality tier's rate; if every layer is
    optically thin (cirrus, thin altostratus) the step can be relaxed instead.
    """
    layers = list(layers)
    if not layers:
        return 1.0
    scales = []
    for layer in layers:
        tau = optical_depth(layer, mean_fill)
        if tau >= 8.0:
            scales.append(1.0)
        elif tau >= 3.0:
            scales.append(1.1)
        elif tau >= 1.0:
            scales.append(1.35)
        else:
            scales.append(1.8)
    return min(scales)


def height_profile(h: float, bottom_ramp: float, top_ramp: float) -> float:
    """Reference implementation of the height profile the shader evaluates (h in 0..1)."""
    def ss(e0, e1, x):
        t = min(max((x - e0) / (e1 - e0), 0.0), 1.0) if e1 != e0 else float(x >= e0)
        return t * t * (3 - 2 * t)

    if h <= 0.0 or h >= 1.0:
        return 0.0
    return ss(0.0, max(bottom_ramp, 1e-4), h) * (1.0 - ss(1.0 - max(top_ramp, 1e-4), 1.0, h))


def estimate_domain_cost(layer, quality: str = "PREVIEW") -> float:
    """Unit-less relative render cost of a layer (domain volume in km^3 x octaves), shown in the UI."""
    area_km2 = math.pi * (layer.radius_m / 1000.0) ** 2
    return area_km2 * (layer.thickness_m / 1000.0) * QUALITY_OCTAVES.get(quality, 4.0) / 100.0
