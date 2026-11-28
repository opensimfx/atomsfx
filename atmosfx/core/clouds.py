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
    density: float          # peak extinction coefficient [1/m]: sigma = 3 LWC / (2 rho_w r_eff) (Kokhanovsky 2004),
                            # e.g. cumulus LWC 0.3-0.5 g/m3, r_eff 10 um -> 0.045-0.075
    scale_m: float
    detail: float
    anisotropy: float       # forward Henyey-Greenstein g
    bottom_ramp: float      # fraction of the thickness over which density ramps up from the base
    top_ramp: float         # fraction over which it ramps down below the top
    anvil: float            # widening near the top (cumulonimbus)
    stretch: float          # >1 flattens the noise vertically (layered clouds)
    note: str
    droplet_um: float = 20.0  # liquid droplet diameter for the Mie phase (2 x effective radius, Kokhanovsky 2004)
    ice: float = 0.0          # share of ice-crystal (Henyey-Greenstein) phase: 1 for cirrus
    billow: float = 0.5       # Worley share of the shape: rounded lumps (cumulus) vs smooth sheets (stratus)
    roundness: float = 1.0    # how fast the threshold rises with height: domed tops
    weather: float = 0.6      # strength of the 2D cover pattern (groups and gaps)
    field_mean: float = 0.50  # measured shape-field statistics at mid-height (coverage calibration)
    field_std: float = 0.08
    edge: float = 0.4         # width of the density ramp above the threshold, in field standard deviations
    fibre: float = 1.0        # stretch along the wind: streaks of cirrus, rows of altocumulus


KINDS: dict[str, CloudKind] = {k.key: k for k in (
    CloudKind("CUMULUS", "Cumulus", 1500.0, 1400.0, 0.40, 0.050, 900.0, 0.60, 0.80, 0.06, 0.45, 0.0, 1.0,
              "Fair-weather puffs with flat bases and cauliflower tops.", 20.0, 0.0, 0.65, 1.8, 0.7, 0.4316, 0.067, 0.12),
    CloudKind("STRATOCUMULUS", "Stratocumulus", 1200.0, 500.0, 0.60, 0.030, 1400.0, 0.40, 0.78, 0.12, 0.35, 0.0, 2.0,
              "Low lumpy sheet, broken or continuous.", 16.0, 0.0, 0.45, 0.6, 0.5, 0.4795, 0.06, 0.25, 1.3),
    CloudKind("STRATUS", "Stratus", 500.0, 400.0, 0.92, 0.025, 2500.0, 0.20, 0.70, 0.20, 0.40, 0.0, 3.0,
              "Uniform grey blanket; sun disc usually hidden.", 12.0, 0.0, 0.15, 0.2, 0.25, 0.4954, 0.0658, 0.8),
    CloudKind("ALTOCUMULUS", "Altocumulus", 4500.0, 600.0, 0.50, 0.025, 600.0, 0.50, 0.80, 0.10, 0.40, 0.0, 1.5,
              "Mid-level cloudlets in rows or patches (mackerel sky).", 14.0, 0.0, 0.55, 0.6, 0.5, 0.4835, 0.055, 0.2, 1.6),
    CloudKind("ALTOSTRATUS", "Altostratus", 4800.0, 1200.0, 0.85, 0.010, 3000.0, 0.20, 0.72, 0.25, 0.40, 0.0, 3.0,
              "Thin grey veil, the sun looks like through frosted glass.", 10.0, 0.5, 0.1, 0.2, 0.3, 0.496, 0.0675, 0.9, 2.0),
    CloudKind("CUMULONIMBUS", "Cumulonimbus", 1200.0, 9000.0, 0.25, 0.070, 3500.0, 0.70, 0.85, 0.04, 0.25, 0.8, 0.8,
              "Towering storm cloud with an anvil top.", 30.0, 0.0, 0.6, 0.5, 0.8, 0.4925, 0.0756, 0.12),
    CloudKind("CIRRUS", "Cirrus", 8500.0, 900.0, 0.40, 0.003, 3000.0, 0.60, 0.82, 0.25, 0.40, 0.0, 4.0,
              "High wispy ice-crystal streaks.", 20.0, 1.0, 0.0, 0.0, 0.5, 0.5109, 0.0832, 0.7, 6.0),
)}

QUALITY_OCTAVES = {"DRAFT": 2.0, "PREVIEW": 4.0, "FINAL": 7.0}
# Emission fill per quality tier: only Draft (4 volume bounces) needs it; Preview (12) and Final (32) bounce for real.
QUALITY_FILL = {"DRAFT": 0.6, "PREVIEW": 0.0, "FINAL": 0.0}


def kind(key: str) -> CloudKind:
    try:
        return KINDS[key.upper()]
    except KeyError:
        raise KeyError(f"unknown cloud kind {key!r}; choose from {sorted(KINDS)}") from None


FIELD_MEAN = 0.50       # default shape-field statistics; each kind carries its own measured pair
FIELD_STD = 0.08
EDGE_SOFTNESS = 0.08    # legacy default ramp width; kinds now set theirs as a multiple of the field sd (``edge``)


def coverage_threshold(coverage: float, mean: float = FIELD_MEAN, std: float = FIELD_STD) -> float:
    """Field level above which cloud exists, chosen so the *filled area fraction* at mid-height equals ``coverage``.

    The shape field is close to normal at mid-height (each kind's mean and sd were measured by rendering the
    shader's Field output on a 25 x 25 cell slice, Blender 5.2.3; q10 and q90 sit within 0.002 of the normal
    quantiles), so the threshold is the (1 - coverage) quantile: mean - sd * probit(coverage).
    Coverage 0 and 1 are exact.
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


# Evolution: the noise space scrolls up by this many feature sizes per second at Evolution 1, so a cloud feature
# turns over in about 15 minutes, the life of a fair-weather cumulus cell (observed 10-20 min).
EVOLUTION_RATE = 1.0 / 900.0
LIGHTNING_PEAK = 0.15    # emission per unit extinction at the brightest stroke (render-calibrated at dusk: 400
                         # whited out the frame, 0.4 lit the whole scene; daytime flashes stay faint, as in reality)

CELL_GAIN = 5.0     # a full-strength cell lifts the field by 5 sd: solid cloud in its core whatever the coverage


def cell_center(layer) -> tuple[float, float, float]:
    """World position of a layer's storm cell at time 0 (it drifts with the layer's wind in the shader)."""
    b = math.radians(getattr(layer, "cell_bearing_deg", 0.0))
    d = getattr(layer, "cell_distance_m", 0.0)
    return (d * math.sin(b), d * math.cos(b), 0.0)


def socket_values(layer, quality: str = "PREVIEW") -> dict:
    """Values for the inputs of the shared cloud node group. ``layer`` is a ``CloudLayerCfg``-like object."""
    k = kind(layer.kind)
    return {
        "Base Altitude": layer.altitude_m,
        "Thickness": layer.thickness_m,
        "Threshold": coverage_threshold(layer.coverage, k.field_mean, k.field_std),
        "Softness": k.edge * k.field_std,
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
        "Fibre": k.fibre,
        "Radius": layer.radius_m,
        "Inner Radius": layer.radius_m * (1.0 - min(max(layer.edge_fade, 0.0), 0.95)),
        "Anisotropy": layer.anisotropy,
        "Droplet Diameter": k.droplet_um,
        "Ice": k.ice,
        "Billow": k.billow,
        "Roundness": k.roundness,
        "Weather": k.weather,
        "Fill": QUALITY_FILL.get(quality, 0.35),
        "Cell Center": cell_center(layer),
        "Cell Radius": max(getattr(layer, "cell_radius_m", 7000.0), 1.0),
        "Cell Strength": CELL_GAIN * k.field_std * min(max(getattr(layer, "cell", 0.0), 0.0), 1.0),
        "Evolution": EVOLUTION_RATE * max(getattr(layer, "evolution", 0.0), 0.0),
    }


def lightning_keys(layer, frame_start: int, frame_end: int, fps: float, domain_xy=(0.0, 0.0)):
    """Strength keys and per-flash positions for a layer's lightning (see core.lightning). Flashes sit in the
    storm cell (drifting with the wind like it) when the layer has one, otherwise anywhere in the inner part of
    the layer around ``domain_xy``; at 25-65 % of the layer's depth, where the charge regions are."""
    from . import lightning
    rate = max(getattr(layer, "lightning", 0.0), 0.0)
    flashes = lightning.schedule(rate, frame_start, frame_end, fps, getattr(layer, "seed", 1))
    peak = LIGHTNING_PEAK * max(getattr(layer, "lightning_brightness", 1.0), 0.0)
    wind = wind_vector(layer.wind_speed_ms, layer.wind_dir_deg)
    cell = getattr(layer, "cell", 0.0) > 0.0
    out = []
    for fl in flashes:
        t = (fl.start_frame - 1) / fps
        if cell:
            cx, cy, _ = cell_center(layer)
            cx, cy, r = cx + wind[0] * t, cy + wind[1] * t, 0.5 * getattr(layer, "cell_radius_m", 7000.0)
        else:
            cx, cy, r = domain_xy[0], domain_xy[1], 0.4 * layer.radius_m
        pos = (cx + fl.offset[0] * r, cy + fl.offset[1] * r, layer.altitude_m + fl.offset[2] * layer.thickness_m)
        out.append((fl, pos))
    radius = min(max(0.35 * layer.thickness_m, 500.0), 3000.0)
    return lightning.keyframes(flashes, peak), out, radius


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
