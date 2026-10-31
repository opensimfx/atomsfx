"""Convert between ``Preset`` dataclasses and the Blender property groups.

``MAP`` is the single table that says which preset field lives in which property. ``apply_preset`` writes a
preset into a scene (one refresh at the end); ``capture`` reads the scene back into a ``Preset`` for export.
"""
from __future__ import annotations

from ..core import clouds as cloudlib
from ..core import presets as P
from .props import suspend_updates

# (preset group, preset field, settings property)
MAP = [
    ("sun", "elevation_deg", "sun_elevation"), ("sun", "azimuth_deg", "sun_azimuth"),
    ("sun", "strength", "sun_strength"), ("sun", "size_scale", "sun_size_scale"),
    ("sky", "air_density", "air_density"), ("sky", "aerosol_density", "aerosol_density"),
    ("sky", "ozone_density", "ozone_density"), ("sky", "altitude_m", "sky_altitude"),
    ("sky", "strength", "sky_strength"), ("sky", "night_glow", "night_glow"),
    ("sky", "ground_enabled", "ground_enabled"), ("sky", "ground_color", "ground_color"),
    ("sky", "ground_blend", "ground_blend"),
    ("moon", "enabled", "moon_enabled"), ("moon", "phase", "moon_phase"),
    ("moon", "elevation_deg", "moon_elevation"), ("moon", "azimuth_deg", "moon_azimuth"),
    ("moon", "strength", "moon_strength"), ("moon", "size_scale", "moon_size_scale"),
    ("stars", "enabled", "stars_enabled"), ("stars", "brightness", "star_brightness"),
    ("stars", "magnitude_limit", "magnitude_limit"), ("stars", "milky_way", "milky_way"),
    ("stars", "density", "star_density"), ("stars", "seed", "star_seed"),
    ("deck", "enabled", "deck_enabled"), ("deck", "coverage", "deck_coverage"),
    ("deck", "altitude_m", "deck_altitude"), ("deck", "scale_m", "deck_scale"),
    ("deck", "opacity", "deck_opacity"), ("deck", "softness", "deck_softness"), ("deck", "fibre", "deck_fibre"),
    ("deck", "wind_speed_ms", "deck_wind_speed"), ("deck", "wind_dir_deg", "deck_wind_dir"),
    ("deck", "seed", "deck_seed"),
    ("fog", "enabled", "fog_enabled"), ("fog", "mode", "fog_mode"), ("fog", "visibility_m", "fog_visibility"),
    ("fog", "scale_height_m", "fog_scale_height"), ("fog", "base_altitude_m", "fog_base_altitude"),
    ("fog", "anisotropy", "fog_anisotropy"), ("fog", "noise_amount", "fog_noise_amount"),
    ("fog", "noise_scale_m", "fog_noise_scale"), ("fog", "absorption", "fog_absorption"),
    ("fog", "color", "fog_color"), ("fog", "domain_visibility_m", "fog_domain_visibility"),
    ("fog", "domain_radius_m", "fog_domain_radius"), ("fog", "domain_height_m", "fog_domain_height"),
]
LAYER_FIELDS = ("enabled", "kind", "altitude_m", "thickness_m", "coverage", "density", "scale_m", "detail",
                "anisotropy", "wind_speed_ms", "wind_dir_deg", "seed", "radius_m", "edge_fade")


def _write(s, prop: str, value) -> None:
    cur = getattr(s, prop)
    if isinstance(value, (list, tuple)):
        value = tuple(value)
    if isinstance(cur, bool):
        value = bool(value)
    setattr(s, prop, value)


def write_preset(s, p: P.Preset) -> None:
    """Write a preset into settings without triggering refreshes."""
    with suspend_updates():
        for grp, field, prop in MAP:
            _write(s, prop, getattr(getattr(p, grp), field))
        if p.sun.hour is not None:
            s.hour = p.sun.hour
        s.clouds.clear()
        for layer in p.clouds[:3]:
            item = s.clouds.add()
            for f in LAYER_FIELDS:
                setattr(item, f, getattr(layer, f))
        s.active_cloud = 0


def apply_preset(scene, p: P.Preset) -> None:
    from ..scene import apply
    s = scene.atmosfx
    write_preset(s, p)
    if p.id in P.ids():
        with suspend_updates():                 # assigning the enum must not re-enter this function
            s.preset = p.id
    if s.created:
        apply.refresh(scene)


def capture(s, preset_id: str = "user_preset", name: str = "User preset", category: str = "Special") -> P.Preset:
    p = P.Preset(id=preset_id, name=name, category=category, description="Exported from AtmosFX")
    for grp, field, prop in MAP:
        v = getattr(s, prop)
        if hasattr(v, "__len__") and not isinstance(v, str):
            v = tuple(round(float(x), 5) for x in v)
        elif isinstance(v, float):
            v = round(v, 5)
        setattr(getattr(p, grp), field, v)
    p.sun.hour = round(s.hour, 4) if s.time_mode == "EARTH" else None
    for item in s.clouds:
        p.clouds.append(P.CloudLayerCfg(**{f: getattr(item, f) for f in LAYER_FIELDS}))
    return p
