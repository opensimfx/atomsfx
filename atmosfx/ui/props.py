"""Scene settings. NOTE: no ``from __future__ import annotations`` here; Blender reads real annotations."""
import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty, PointerProperty, StringProperty)

from ..core import clouds as cloudlib
from ..core import presets as presetlib

_suspend = [0]


class suspend_updates:
    """Context manager: property update callbacks do nothing while it is active (bulk edits, preset load)."""

    def __enter__(self):
        _suspend[0] += 1

    def __exit__(self, *exc):
        _suspend[0] -= 1


def _settings_of(self):
    return self if isinstance(self, AtmosFXSettings) else self.id_data.atmosfx


def _upd(self, context):
    if _suspend[0]:
        return
    s = _settings_of(self)
    if not (s.created and s.live):
        return
    from ..scene import apply
    apply.refresh(self.id_data)


def _kind_changed(self, context):
    """Switching cloud kind loads that kind's typical altitude, thickness, density, scale and detail."""
    if _suspend[0]:
        return
    k = cloudlib.kind(self.kind)
    with suspend_updates():
        self.altitude_m, self.thickness_m, self.coverage = k.altitude_m, k.thickness_m, k.coverage
        self.density, self.scale_m, self.detail, self.anisotropy = k.density, k.scale_m, k.detail, k.anisotropy
    _upd(self, context)


def _preset_changed(self, context):
    if _suspend[0] or not self.preset:
        return
    from . import state
    state.apply_preset(self.id_data, presetlib.get(self.preset))


def F(default, lo, hi, name, desc="", soft=None, unit="NONE", prec=3, update=_upd, subtype="NONE", step=None):
    kw = dict(name=name, description=desc, default=default, min=lo, max=hi, unit=unit, precision=prec,
              update=update, subtype=subtype)
    if soft:
        kw["soft_min"], kw["soft_max"] = soft
    if step:
        kw["step"] = step
    return FloatProperty(**kw)


def B(default, name, desc="", update=_upd):
    return BoolProperty(name=name, description=desc, default=default, update=update)


def I(default, lo, hi, name, desc="", update=_upd):
    return IntProperty(name=name, description=desc, default=default, min=lo, max=hi, update=update)


def C(default, name, desc=""):
    return FloatVectorProperty(name=name, description=desc, default=default, size=3, subtype="COLOR",
                               min=0.0, max=1.0, update=_upd)


_preset_items_cache: list = []


def preset_items(self, context):
    global _preset_items_cache
    items = []
    for cat, plist in presetlib.by_category().items():
        for p in plist:
            items.append((p.id, p.name, f"{cat}: {p.description}"))
    _preset_items_cache = items
    return items


KIND_ITEMS = [(k.key, k.label, k.note) for k in cloudlib.KINDS.values()]


class AtmosFXCloudLayer(bpy.types.PropertyGroup):
    enabled: B(True, "Enabled")
    kind: EnumProperty(name="Kind", items=KIND_ITEMS, default="CUMULUS", update=_kind_changed,
                       description="Cloud genus; sets typical altitude, thickness and shape")
    altitude_m: F(1500.0, 0.0, 20000.0, "Base altitude", "Height of the cloud base above the world origin", prec=0)
    thickness_m: F(1400.0, 50.0, 15000.0, "Thickness", "Vertical extent of the layer", prec=0)
    coverage: F(0.4, 0.0, 1.0, "Coverage", "0 = clear, 1 = overcast", subtype="FACTOR", prec=2)
    density: F(0.02, 0.0005, 0.5, "Density", "Peak extinction coefficient in 1/m; higher is darker and more opaque", prec=4)
    scale_m: F(900.0, 50.0, 20000.0, "Feature size", "Size of the largest cloud features", prec=0)
    detail: F(0.6, 0.0, 1.0, "Detail", "Fine erosion of the cloud edges", subtype="FACTOR", prec=2)
    anisotropy: F(0.8, 0.0, 0.95, "Forward scatter", "Henyey-Greenstein g; real cloud droplets scatter strongly forward", prec=2)
    wind_speed_ms: F(6.0, 0.0, 100.0, "Wind speed", "Metres per second", prec=1)
    wind_dir_deg: F(90.0, 0.0, 360.0, "Wind direction", "Compass bearing the wind blows toward (0 = +Y, 90 = +X)", prec=0)
    seed: I(1, 0, 100000, "Seed", "Different seeds give different cloud fields")
    radius_m: F(15000.0, 1000.0, 100000.0, "Radius", "Domain radius; clouds fade to nothing at the edge", prec=0)
    edge_fade: F(0.35, 0.0, 0.95, "Edge fade", "Fraction of the radius used to fade out", subtype="FACTOR", prec=2)
    follow_camera: B(True, "Follow camera", "Keep the domain centred over the camera in X/Y (clouds stay put in world space)")


class AtmosFXSettings(bpy.types.PropertyGroup):
    created: BoolProperty(default=False)
    live: B(True, "Live update", "Apply changes as you edit")
    previous_world: PointerProperty(type=bpy.types.World)
    preset: EnumProperty(name="Preset", items=preset_items, update=_preset_changed)
    quality: EnumProperty(name="Quality", update=_upd, default="PREVIEW",
                          items=[("DRAFT", "Draft", "Fast viewport: single scattering, coarse volumes"),
                                 ("PREVIEW", "Preview", "Balanced"),
                                 ("FINAL", "Final", "Multiple scattering, fine volumes, volumetric shadows")])
    auto_render_settings: B(True, "Configure render settings", "Let AtmosFX set volume quality in Cycles and EEVEE for the chosen tier")

    # ---- time and place
    time_mode: EnumProperty(name="Mode", update=_upd, default="ARTISTIC",
                            items=[("ARTISTIC", "Artistic", "Place the sun and moon by hand"),
                                   ("EARTH", "Earth", "Sun, moon and stars follow a real place, date and time")])
    sun_elevation: F(45.0, -90.0, 90.0, "Sun elevation", "Degrees above the horizon", prec=1)
    sun_azimuth: F(135.0, 0.0, 360.0, "Sun azimuth", "Compass bearing (0 = +Y, 90 = +X)", prec=1)
    latitude: F(40.0, -90.0, 90.0, "Latitude", "Degrees north", prec=3)
    longitude: F(0.0, -180.0, 180.0, "Longitude", "Degrees east", prec=3)
    year: I(2026, 1900, 2100, "Year")
    month: I(6, 1, 12, "Month")
    day: I(21, 1, 31, "Day")
    hour: F(12.0, 0.0, 24.0, "Local time", "Hours, local civil time", soft=(0.0, 24.0), prec=2)
    utc_offset: F(0.0, -12.0, 14.0, "UTC offset", "Hours east of UTC for local time", prec=2)
    north_offset: F(0.0, 0.0, 360.0, "North offset", "Compass bearing of the scene's +Y axis", prec=1)
    refraction: B(True, "Refraction", "Include atmospheric refraction at low altitudes")
    animate_time: B(False, "Animate time", "Advance the clock with the timeline")
    time_scale: F(1.0, -1000.0, 1000.0, "Hours per second", "Simulated hours per real second of animation", prec=3)

    # ---- sun and sky
    use_sun_lamp: B(True, "Sun lamp", "Light the scene with a Sun lamp (the disc in the sky is then visible to the camera only)")
    sun_strength: F(3.0, 0.0, 100.0, "Sun strength", "Sun-lamp strength at 90 degrees; lower suns scale physically", prec=2)
    sun_size_scale: F(1.0, 0.1, 20.0, "Sun size", "1 = true angular size (0.53 degrees)", prec=2)
    air_density: F(1.0, 0.0, 10.0, "Air", "Molecular (Rayleigh) density, 1 = Earth at sea level", prec=2)
    aerosol_density: F(1.0, 0.0, 50.0, "Aerosols", "Dust, smoke and haze particles; also warms sunsets", prec=2)
    ozone_density: F(1.0, 0.0, 10.0, "Ozone", "Ozone layer density (deepens the blue of twilight)", prec=2)
    sky_altitude: F(0.0, 0.0, 60000.0, "Altitude", "Viewpoint height above sea level for the sky model", prec=0)
    sky_strength: F(1.0, 0.0, 20.0, "Sky strength", "Overall sky brightness", prec=2)
    night_glow: F(0.0015, 0.0, 1.0, "Night glow", "Airglow floor; keeps moonless nights from being pure black", prec=4)
    ground_enabled: B(True, "Ground below horizon", "Fill the lower hemisphere with a ground colour")
    ground_color: C((0.18, 0.17, 0.16), "Ground colour")
    ground_blend: F(0.02, 0.0, 0.5, "Horizon blend", "Softness of the horizon line", prec=3)

    # ---- moon
    moon_enabled: B(True, "Moon")
    moon_phase: F(0.5, 0.0, 1.0, "Phase", "0 new, 0.25 first quarter, 0.5 full, 0.75 last quarter", prec=3, subtype="FACTOR")
    moon_elevation: F(40.0, -90.0, 90.0, "Moon elevation", "Degrees (Artistic mode)", prec=1)
    moon_azimuth: F(200.0, 0.0, 360.0, "Moon azimuth", "Compass bearing (Artistic mode)", prec=1)
    moon_strength: F(0.12, 0.0, 10.0, "Moonlight", "Lamp strength of a full moon at the zenith", prec=3)
    moon_size_scale: F(1.0, 0.1, 10.0, "Moon size", "1 = true size; the 'moon illusion' look is about 1.5 to 3", prec=2)

    # ---- stars
    stars_enabled: B(True, "Stars")
    star_brightness: F(1.0, 0.0, 50.0, "Star brightness", "", prec=2)
    magnitude_limit: F(6.0, -2.0, 6.5, "Limiting magnitude", "Faintest visible star; twilight and moonlight lower it automatically", prec=1)
    milky_way: F(1.0, 0.0, 10.0, "Milky Way", "Strength of the Milky Way band", prec=2)
    star_density: F(1.0, 0.1, 4.0, "Star density", "Multiplier on the number of faint stars", prec=2)
    star_seed: I(1, 0, 100000, "Star seed", "Seed for the faint-star field")
    star_resolution: EnumProperty(name="Star map", update=_upd, default="4096",
                                  items=[("2048", "2K", "Fast, soft stars"), ("4096", "4K", "Balanced"),
                                         ("8192", "8K", "Sharp stars; 2 GB of RAM while baking")])

    # ---- clouds
    clouds: CollectionProperty(type=AtmosFXCloudLayer)
    active_cloud: IntProperty(default=0)
    deck_enabled: B(False, "2D cloud deck", "A cheap, infinite high cloud layer drawn in the sky (no shadows)")
    deck_coverage: F(0.4, 0.0, 1.0, "Coverage", "", subtype="FACTOR", prec=2)
    deck_altitude: F(8000.0, 1000.0, 20000.0, "Altitude", "", prec=0)
    deck_scale: F(6000.0, 100.0, 100000.0, "Feature size", "", prec=0)
    deck_opacity: F(0.7, 0.0, 1.0, "Opacity", "", subtype="FACTOR", prec=2)
    deck_softness: F(0.25, 0.01, 1.0, "Softness", "", subtype="FACTOR", prec=2)
    deck_fibre: F(1.0, 1.0, 12.0, "Fibre", "Stretch the clouds into streaks (cirrus)", prec=1)
    deck_wind_speed: F(15.0, 0.0, 100.0, "Wind speed", "Metres per second", prec=1)
    deck_wind_dir: F(90.0, 0.0, 360.0, "Wind direction", "", prec=0)
    deck_seed: I(3, 0, 100000, "Seed")

    # ---- fog
    fog_enabled: B(False, "Fog")
    fog_mode: EnumProperty(name="Mode", update=_upd, default="WORLD",
                           items=[("WORLD", "Haze", "Haze everywhere: a bounded dome that follows the camera"),
                                  ("DOMAIN", "Domain", "A fog bank you place and scale"),
                                  ("BOTH", "Both", "World haze plus a fog bank")])
    fog_visibility: F(20000.0, 5.0, 200000.0, "Visibility", "Meteorological optical range of the haze (Koschmieder, 2 % contrast)", prec=0)
    fog_scale_height: F(1500.0, 1.0, 50000.0, "Scale height", "Fog thins by 1/e over this height", prec=0)
    fog_base_altitude: F(0.0, -1000.0, 50000.0, "Base altitude", "Ground level of the fog", prec=1)
    fog_anisotropy: F(0.4, -0.9, 0.95, "Anisotropy", "Forward scattering of fog droplets", prec=2)
    fog_noise_amount: F(0.0, 0.0, 1.0, "Patchiness", "", subtype="FACTOR", prec=2)
    fog_noise_scale: F(400.0, 10.0, 20000.0, "Patch size", "", prec=0)
    fog_absorption: F(0.0, 0.0, 1.0, "Absorption", "Smoke and smog absorb light as well as scatter it", subtype="FACTOR", prec=2)
    fog_color: C((1.0, 1.0, 1.0), "Colour")
    fog_domain_visibility: F(400.0, 5.0, 200000.0, "Domain visibility", "Visibility inside the fog bank", prec=0)
    fog_domain_radius: F(2000.0, 50.0, 100000.0, "Domain radius", "", prec=0)
    fog_domain_height: F(400.0, 5.0, 10000.0, "Domain height", "", prec=0)


CLASSES = (AtmosFXCloudLayer, AtmosFXSettings)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.atmosfx = PointerProperty(type=AtmosFXSettings)


def unregister():
    del bpy.types.Scene.atmosfx
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
