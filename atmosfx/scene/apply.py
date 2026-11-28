"""Orchestrator: settings -> SkyParams -> SkyView -> world, lamps, domains, render settings."""
from __future__ import annotations

import calendar
import math

import bpy
from bpy.app.handlers import persistent

from ..core import clouds as cloudlib
from ..core.skyview import SkyParams, SkyView, compute_view
from . import objects, world

_busy = False
last_view: dict[str, SkyView] = {}

QUALITY = {
    #           cycles step rate, preview rate, max steps, bounces | eevee tile, samples, shadows
    "DRAFT": (3.0, 6.0, 512, 8, "8", 48, False),
    "PREVIEW": (1.5, 3.0, 1024, 32, "4", 64, True),
    "FINAL": (0.75, 1.5, 2048, 96, "2", 128, True),
}


def _try(obj, attr: str, value) -> None:
    try:
        setattr(obj, attr, value)
    except (AttributeError, TypeError, ValueError):
        pass


def apply_render_settings(scene, s) -> None:
    if not s.auto_render_settings:
        return
    step, pstep, steps, bounces, tile, samples, shadows = QUALITY[s.quality]
    scale = cloudlib.step_rate_scale([l for l in s.clouds if l.enabled])
    cy = getattr(scene, "cycles", None)
    if cy is not None:
        _try(cy, "volume_step_rate", step * scale)
        _try(cy, "volume_preview_step_rate", pstep * scale)
        _try(cy, "volume_max_steps", steps)
        _try(cy, "volume_bounces", bounces)
        if getattr(cy, "max_bounces", bounces) < bounces:      # the total cap would silently clamp volume bounces
            _try(cy, "max_bounces", bounces)
    ev = getattr(scene, "eevee", None)
    if ev is not None:
        _try(ev, "volumetric_tile_size", tile)
        _try(ev, "volumetric_samples", samples)
        _try(ev, "use_volumetric_shadows", shadows)
        _try(ev, "use_volume_custom_range", True)
        far = max([l.radius_m for l in s.clouds] + [s.fog_domain_radius, objects.haze_dimensions(s)[0], 3000.0])
        _try(ev, "volumetric_end", min(far, 60000.0))


def required_clip_end(s) -> float:
    """Camera clip end needed so no cloud or haze domain is cut off (a cut domain simply vanishes)."""
    need = 0.0
    for l in s.clouds:
        if l.enabled:
            need = max(need, 2.2 * l.radius_m)
    if s.fog_enabled and s.fog_mode in ("WORLD", "BOTH"):
        need = max(need, 2.2 * objects.haze_dimensions(s)[0])
    if s.fog_enabled and s.fog_mode in ("DOMAIN", "BOTH"):
        need = max(need, 2.2 * s.fog_domain_radius)
    return need


def cloud_cover(s) -> float:
    """Sun and star dimming from the 2D deck. Volumetric layers are NOT counted: they cast real shadows and block
    real stars in the render, so dimming the lamp for them as well would count them twice."""
    if s.deck_enabled:
        return s.deck_coverage * s.deck_opacity * 0.5
    return 0.0


def cloud_lit_altitude(s) -> float:
    """Mean mid-height of the enabled volumetric layers (m), 0 when there are none. Drives the cloud sun."""
    mids = [l.altitude_m + 0.5 * l.thickness_m for l in s.clouds if l.enabled]
    return min(sum(mids) / len(mids), 9000.0) if mids else 0.0


def cloud_light(s) -> float:
    """Share of clear-sky ground light left under the enabled volumetric layers, for the auto exposure."""
    from ..core import physics
    f = 1.0
    for l in s.clouds:
        if l.enabled:
            f *= physics.cloud_light_factor(l.coverage, cloudlib.optical_depth(l, mean_fill=0.7))
    return f


def volumetric_cover(s) -> float:
    """Combined sky cover of the enabled volumetric layers (random overlap)."""
    clear = 1.0
    for l in s.clouds:
        if l.enabled:
            clear *= 1.0 - min(max(l.coverage, 0.0), 1.0)
    return 1.0 - clear


def params_from_settings(scene, s) -> SkyParams:
    day = min(s.day, calendar.monthrange(s.year, s.month)[1])
    fps = scene.render.fps / (scene.render.fps_base or 1.0)
    return SkyParams(
        time_mode=s.time_mode, sun_elevation=s.sun_elevation, sun_azimuth=s.sun_azimuth,
        latitude=s.latitude, longitude=s.longitude, year=s.year, month=s.month, day=day, hour=s.hour,
        utc_offset=s.utc_offset, north_offset=s.north_offset, refraction=s.refraction,
        sun_strength=s.sun_strength, sun_size_scale=s.sun_size_scale, use_sun_lamp=s.use_sun_lamp,
        aerosol_density=s.aerosol_density, eclipse=s.eclipse,
        moon_enabled=s.moon_enabled, moon_phase=s.moon_phase, moon_elevation=s.moon_elevation,
        moon_azimuth=s.moon_azimuth, moon_strength=s.moon_strength, moon_size_scale=s.moon_size_scale,
        stars_enabled=s.stars_enabled, star_brightness=s.star_brightness, magnitude_limit=s.magnitude_limit,
        milky_way=s.milky_way, sky_strength=s.sky_strength, night_glow=s.night_glow,
        cloud_cover=cloud_cover(s), cloud_lit_altitude_m=cloud_lit_altitude(s),
        cloud_light=cloud_light(s), cloud_cover_volumetric=volumetric_cover(s), animate_time=s.animate_time, time_scale=s.time_scale,
        frame=scene.frame_current, frame_start=scene.frame_start, fps=fps,
    )


def refresh(scene: bpy.types.Scene) -> SkyView | None:
    """Re-derive and push everything. Cheap enough for live editing; the star bake is cached by content."""
    global _busy
    s = scene.atmosfx
    if not s.created or _busy:
        return None
    _busy = True
    try:
        view = compute_view(params_from_settings(scene, s))
        world.update(scene, s, view, s.quality)
        objects.update_lamps(scene, s, view)
        objects.update_cloud_layers(scene, s, view, s.quality)
        objects.update_cloud_sun(scene, s, view)
        objects.update_fog(scene, s, view)
        apply_render_settings(scene, s)
        if s.auto_exposure:
            scene.view_settings.exposure = view.exposure + s.exposure_bias
        last_view[scene.name] = view
        return view
    finally:
        _busy = False


def create(scene: bpy.types.Scene) -> None:
    s = scene.atmosfx
    if not world.is_ours(scene.world):
        s.previous_world = scene.world
    s.created = True
    objects.ensure_collection(scene)
    world.ensure_world(scene)
    refresh(scene)


def remove(scene: bpy.types.Scene) -> None:
    s = scene.atmosfx
    prev = s.previous_world
    objects.remove_all()
    if world.is_ours(scene.world):
        scene.world = prev if prev is not None and not world.is_ours(prev) else None
    w = bpy.data.worlds.get(world.WORLD_NAME)
    if w is not None and w.users == 0:
        bpy.data.worlds.remove(w)
    for g in list(bpy.data.node_groups):
        if g.name.startswith("AtmosFX") and g.users == 0:
            bpy.data.node_groups.remove(g)
    for m in list(bpy.data.materials):
        if m.name.startswith("AtmosFX") and m.users == 0:
            bpy.data.materials.remove(m)
    for me in list(bpy.data.meshes):
        if me.name.startswith("AtmosFX") and me.users == 0:
            bpy.data.meshes.remove(me)
    for img in list(bpy.data.images):
        if img.name.startswith(world.STAR_PREFIX) and img.users == 0:
            bpy.data.images.remove(img)
    s.previous_world = None
    s.created = False
    last_view.pop(scene.name, None)


# ------------------------------------------------------------------------------ handlers
@persistent
def _on_frame(scene, depsgraph=None):
    s = getattr(scene, "atmosfx", None)
    if s is not None and s.created and s.animate_time:
        refresh(scene)


@persistent
def _on_load(_dummy=None):
    for scene in bpy.data.scenes:
        s = getattr(scene, "atmosfx", None)
        if s is not None and s.created:
            try:
                refresh(scene)
            except Exception as exc:          # a stale file must never block loading
                print(f"AtmosFX: refresh on load failed for {scene.name}: {exc}")


def register_handlers() -> None:
    for lst, fn in ((bpy.app.handlers.frame_change_post, _on_frame), (bpy.app.handlers.load_post, _on_load)):
        if fn not in lst:
            lst.append(fn)


def unregister_handlers() -> None:
    for lst, fn in ((bpy.app.handlers.frame_change_post, _on_frame), (bpy.app.handlers.load_post, _on_load)):
        while fn in lst:
            lst.remove(fn)
