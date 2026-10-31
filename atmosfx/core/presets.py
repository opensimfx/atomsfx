"""Preset data model. A preset is a complete, serialisable description of an atmosphere.

``Preset`` (and its sub-configs) is the single schema shared by the built-in library
(``data/presets.json``), the user's exported presets, and the Blender property groups
(``ui/state.py`` converts between them). Pure Python, no ``bpy``.
"""
from __future__ import annotations

import json
import os
import typing
from dataclasses import MISSING, asdict, dataclass, field, fields, is_dataclass, replace
from typing import Optional

from . import clouds as cloudlib

SCHEMA_VERSION = 1


@dataclass
class SunCfg:
    elevation_deg: float = 45.0      # artistic mode
    azimuth_deg: float = 135.0       # compass bearing, 0 = +Y, 90 = +X
    hour: Optional[float] = None     # Earth mode: local civil hour, None keeps the current time
    strength: float = 3.0            # Sun-lamp strength at 90 degrees (Blender units)
    size_scale: float = 1.0          # 1 = physical 0.53 degrees


@dataclass
class SkyCfg:
    air_density: float = 1.0
    aerosol_density: float = 1.0
    ozone_density: float = 1.0
    altitude_m: float = 0.0
    strength: float = 1.0
    night_glow: float = 0.0015
    ground_enabled: bool = True
    ground_color: tuple = (0.18, 0.17, 0.16)
    ground_blend: float = 0.02


@dataclass
class MoonCfg:
    enabled: bool = True
    phase: float = 0.5               # artistic mode: 0 new, 0.25 first quarter, 0.5 full
    elevation_deg: float = 40.0
    azimuth_deg: float = 200.0
    strength: float = 0.12           # lamp strength of a full moon at the zenith
    size_scale: float = 1.0


@dataclass
class StarsCfg:
    enabled: bool = True
    brightness: float = 1.0
    magnitude_limit: float = 6.0
    milky_way: float = 1.0
    density: float = 1.0
    seed: int = 1


@dataclass
class CloudLayerCfg:
    enabled: bool = True
    kind: str = "CUMULUS"
    altitude_m: float = 1500.0
    thickness_m: float = 1400.0
    coverage: float = 0.4
    density: float = 0.05
    scale_m: float = 900.0
    detail: float = 0.6
    anisotropy: float = 0.8
    wind_speed_ms: float = 6.0
    wind_dir_deg: float = 90.0
    seed: int = 1
    radius_m: float = 15000.0
    edge_fade: float = 0.35


@dataclass
class DeckCfg:
    """A 2D high cloud deck drawn in the world shader: cheap, infinite, casts no shadows."""
    enabled: bool = False
    coverage: float = 0.4
    altitude_m: float = 8000.0
    scale_m: float = 6000.0
    opacity: float = 0.7
    softness: float = 0.25
    fibre: float = 1.0               # >1 stretches the noise along the wind into streaks
    wind_speed_ms: float = 15.0
    wind_dir_deg: float = 90.0
    seed: int = 3


@dataclass
class FogCfg:
    enabled: bool = False
    mode: str = "WORLD"              # WORLD (whole scene), DOMAIN (a box you place), BOTH
    visibility_m: float = 20000.0
    scale_height_m: float = 1500.0
    base_altitude_m: float = 0.0
    anisotropy: float = 0.4
    noise_amount: float = 0.0
    noise_scale_m: float = 400.0
    absorption: float = 0.0
    color: tuple = (1.0, 1.0, 1.0)
    domain_visibility_m: float = 400.0   # density of the placeable fog domain (DOMAIN / BOTH modes)
    domain_radius_m: float = 2000.0
    domain_height_m: float = 400.0


@dataclass
class Preset:
    id: str
    name: str
    category: str = "Sky"
    description: str = ""
    tags: list = field(default_factory=list)
    sun: SunCfg = field(default_factory=SunCfg)
    sky: SkyCfg = field(default_factory=SkyCfg)
    moon: MoonCfg = field(default_factory=MoonCfg)
    stars: StarsCfg = field(default_factory=StarsCfg)
    clouds: list = field(default_factory=list)
    deck: DeckCfg = field(default_factory=DeckCfg)
    fog: FogCfg = field(default_factory=FogCfg)


# --------------------------------------------------------------------- (de)serialising
def _build(tp, data):
    """Recursively construct dataclass instances from plain JSON data, using the field type hints."""
    origin = typing.get_origin(tp)
    if is_dataclass(tp):
        hints = typing.get_type_hints(tp)
        kwargs = {}
        for f in fields(tp):
            if f.name in data:
                kwargs[f.name] = _build(hints[f.name], data[f.name])
        return tp(**kwargs)
    if origin in (list, typing.List):
        return list(data)
    if origin is typing.Union:                       # Optional[X]
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        return None if data is None else _build(args[0], data)
    if tp is tuple:
        return tuple(data)
    return data


def preset_from_dict(data: dict) -> Preset:
    d = dict(data)
    clouds = [_build(CloudLayerCfg, c) for c in d.pop("clouds", [])]
    p = _build(Preset, d)
    p.clouds = clouds
    return p


def preset_to_dict(p: Preset) -> dict:
    d = asdict(p)
    for sub in ("sky",):
        d[sub]["ground_color"] = list(d[sub]["ground_color"])
    d["fog"]["color"] = list(d["fog"]["color"])
    return d


def derive(base: Preset, **overrides) -> Preset:
    """Copy ``base`` with nested overrides, e.g. ``derive(p, id="x", sun={"elevation_deg": 5})``."""
    out = replace(base, tags=list(base.tags), clouds=[replace(c) for c in base.clouds])
    for key, val in overrides.items():
        cur = getattr(out, key)
        if key == "clouds":
            out.clouds = [c if isinstance(c, CloudLayerCfg) else _build(CloudLayerCfg, c) for c in val]
        elif isinstance(val, dict) and is_dataclass(cur):
            setattr(out, key, replace(cur, **{k: (tuple(v) if isinstance(v, list) else v) for k, v in val.items()}))
        else:
            setattr(out, key, val)
    return out


# ---------------------------------------------------------------------------- validation
RANGES = {
    ("sun", "elevation_deg"): (-90, 90), ("sun", "azimuth_deg"): (0, 360), ("sun", "hour"): (0, 24),
    ("sun", "strength"): (0, 100), ("sun", "size_scale"): (0.1, 20),
    ("sky", "air_density"): (0, 10), ("sky", "aerosol_density"): (0, 50), ("sky", "ozone_density"): (0, 10),
    ("sky", "altitude_m"): (0, 60000), ("sky", "strength"): (0, 20), ("sky", "night_glow"): (0, 1),
    ("sky", "ground_blend"): (0, 0.5),
    ("moon", "phase"): (0, 1), ("moon", "elevation_deg"): (-90, 90), ("moon", "azimuth_deg"): (0, 360),
    ("moon", "strength"): (0, 10), ("moon", "size_scale"): (0.1, 10),
    ("stars", "brightness"): (0, 50), ("stars", "magnitude_limit"): (-2, 6.5), ("stars", "milky_way"): (0, 10),
    ("stars", "density"): (0.1, 4),
    ("deck", "coverage"): (0, 1), ("deck", "altitude_m"): (1000, 20000), ("deck", "scale_m"): (100, 100000),
    ("deck", "opacity"): (0, 1), ("deck", "softness"): (0.01, 1), ("deck", "fibre"): (1, 12),
    ("fog", "visibility_m"): (5, 200000), ("fog", "scale_height_m"): (1, 50000), ("fog", "anisotropy"): (-0.9, 0.95),
    ("fog", "noise_amount"): (0, 1), ("fog", "absorption"): (0, 1), ("fog", "domain_visibility_m"): (5, 200000),
}
LAYER_RANGES = {
    "altitude_m": (0, 20000), "thickness_m": (50, 15000), "coverage": (0, 1), "density": (0.0005, 0.5),
    "scale_m": (50, 20000), "detail": (0, 1), "anisotropy": (0, 0.95), "wind_speed_ms": (0, 100),
    "radius_m": (1000, 100000), "edge_fade": (0, 0.95),
}
FOG_MODES = ("WORLD", "DOMAIN", "BOTH")


def validate(p: Preset) -> list[str]:
    """Return a list of human-readable problems (empty means valid)."""
    errs: list[str] = []
    if not p.id or not p.id.replace("_", "").isalnum():
        errs.append(f"id {p.id!r} must be alphanumeric with underscores")
    for (grp, name), (lo, hi) in RANGES.items():
        v = getattr(getattr(p, grp), name)
        if v is not None and not (lo <= v <= hi):
            errs.append(f"{grp}.{name}={v} outside [{lo}, {hi}]")
    if p.fog.mode not in FOG_MODES:
        errs.append(f"fog.mode {p.fog.mode!r} not in {FOG_MODES}")
    if len(p.clouds) > 3:
        errs.append("at most 3 cloud layers")
    for i, c in enumerate(p.clouds):
        if c.kind.upper() not in cloudlib.KINDS:
            errs.append(f"clouds[{i}].kind {c.kind!r} unknown")
        for name, (lo, hi) in LAYER_RANGES.items():
            v = getattr(c, name)
            if not (lo <= v <= hi):
                errs.append(f"clouds[{i}].{name}={v} outside [{lo}, {hi}]")
    return errs


# ------------------------------------------------------------------------------ library
_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "presets.json")
_cache: dict[str, Preset] | None = None
CATEGORIES = ("Time of day", "Night sky", "Weather", "Fog and haze", "Special")


def load_file(path: str) -> list[Preset]:
    with open(path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    if doc.get("schema", 1) > SCHEMA_VERSION:
        raise ValueError(f"preset file schema {doc.get('schema')} is newer than this add-on ({SCHEMA_VERSION})")
    return [preset_from_dict(d) for d in doc["presets"]]


def library(refresh: bool = False) -> dict[str, Preset]:
    global _cache
    if _cache is None or refresh:
        _cache = {p.id: p for p in load_file(_DATA)}
    return _cache


def get(preset_id: str) -> Preset:
    lib = library()
    if preset_id not in lib:
        raise KeyError(f"unknown preset {preset_id!r}")
    return lib[preset_id]


def ids() -> list[str]:
    return list(library())


def by_category() -> dict[str, list[Preset]]:
    out: dict[str, list[Preset]] = {c: [] for c in CATEGORIES}
    for p in library().values():
        out.setdefault(p.category, []).append(p)
    return out


def save_file(path: str, presets: list[Preset]) -> None:
    doc = {"schema": SCHEMA_VERSION, "presets": [preset_to_dict(p) for p in presets]}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
