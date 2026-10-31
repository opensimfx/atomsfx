"""Sidebar panels (3D View > N panel > AtmosFX)."""
import math

import bpy

from ..core import astro, clouds as cloudlib, physics
from ..scene import apply

_events_cache: dict = {}


def _settings(context):
    return context.scene.atmosfx


class _Base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AtmosFX"


class _Sub(_Base):
    bl_parent_id = "ATMOSFX_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _settings(context).created


def _col(layout, s, names, **kw):
    col = layout.column(**kw)
    for n in names:
        col.prop(s, n)
    return col


class ATMOSFX_PT_main(_Base, bpy.types.Panel):
    bl_label = "AtmosFX"
    bl_idname = "ATMOSFX_PT_main"

    def draw(self, context):
        s = _settings(context)
        lay = self.layout
        lay.prop(s, "preset", text="")
        if not s.created:
            lay.operator("atmosfx.add", icon="WORLD")
            lay.label(text="Creates a sky, sun, moon, stars, clouds and fog.", icon="INFO")
            return
        row = lay.row(align=True)
        row.operator("atmosfx.apply_preset", text="Load preset", icon="IMPORT")
        row.operator("atmosfx.refresh", text="", icon="FILE_REFRESH")
        lay.prop(s, "quality")
        row = lay.row()
        row.prop(s, "live", toggle=True, icon="PLAY")
        row.prop(s, "auto_render_settings", text="Set render")
        cam = context.scene.camera
        need = apply.required_clip_end(s)
        if cam is not None and cam.type == "CAMERA" and cam.data.clip_end < need:
            box = lay.box()
            box.alert = True
            box.label(text=f"Camera clip end {cam.data.clip_end:,.0f} m cuts off", icon="ERROR")
            box.label(text=f"clouds/haze (need {need:,.0f} m).")
            box.operator("atmosfx.fix_camera_clip", icon="CAMERA_DATA")
        lay.operator("atmosfx.remove", icon="TRASH")


class ATMOSFX_PT_time(_Sub, bpy.types.Panel):
    bl_label = "Time and Place"
    bl_idname = "ATMOSFX_PT_time"

    def draw(self, context):
        s, lay = _settings(context), self.layout
        lay.prop(s, "time_mode", expand=True)
        if s.time_mode == "ARTISTIC":
            _col(lay, s, ("sun_elevation", "sun_azimuth"))
            lay.label(text="Stars follow the date and place below.", icon="INFO")
        _col(lay, s, ("latitude", "longitude"))
        row = lay.row(align=True)
        row.prop(s, "year", text="")
        row.prop(s, "month", text="")
        row.prop(s, "day", text="")
        _col(lay, s, ("hour", "utc_offset", "north_offset"))
        lay.operator("atmosfx.set_now", icon="TIME")
        lay.prop(s, "refraction")
        box = lay.box()
        box.prop(s, "animate_time")
        if s.animate_time:
            box.prop(s, "time_scale")


class ATMOSFX_PT_sky(_Sub, bpy.types.Panel):
    bl_label = "Sky and Sun"
    bl_idname = "ATMOSFX_PT_sky"

    def draw(self, context):
        s, lay = _settings(context), self.layout
        _col(lay, s, ("air_density", "aerosol_density", "ozone_density", "sky_altitude", "sky_strength", "night_glow"))
        lay.separator()
        lay.prop(s, "use_sun_lamp")
        _col(lay, s, ("sun_strength", "sun_size_scale"))
        lay.separator()
        lay.prop(s, "ground_enabled")
        if s.ground_enabled:
            _col(lay, s, ("ground_color", "ground_blend"))


class ATMOSFX_PT_moon(_Sub, bpy.types.Panel):
    bl_label = "Moon"
    bl_idname = "ATMOSFX_PT_moon"

    def draw_header(self, context):
        self.layout.prop(_settings(context), "moon_enabled", text="")

    def draw(self, context):
        s, lay = _settings(context), self.layout
        lay.active = s.moon_enabled
        if s.time_mode == "ARTISTIC":
            _col(lay, s, ("moon_phase", "moon_elevation", "moon_azimuth"))
        else:
            lay.label(text="Phase and position follow the date.", icon="INFO")
        _col(lay, s, ("moon_strength", "moon_size_scale"))


class ATMOSFX_PT_stars(_Sub, bpy.types.Panel):
    bl_label = "Stars"
    bl_idname = "ATMOSFX_PT_stars"

    def draw_header(self, context):
        self.layout.prop(_settings(context), "stars_enabled", text="")

    def draw(self, context):
        s, lay = _settings(context), self.layout
        lay.active = s.stars_enabled
        _col(lay, s, ("star_brightness", "magnitude_limit", "milky_way", "star_density", "star_seed", "star_resolution"))


class ATMOSFX_UL_clouds(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.label(text=f"{index + 1}. {cloudlib.kind(item.kind).label}")
        row.label(text=f"{item.altitude_m:.0f} m")


class ATMOSFX_PT_clouds(_Sub, bpy.types.Panel):
    bl_label = "Clouds"
    bl_idname = "ATMOSFX_PT_clouds"

    def draw(self, context):
        s, lay = _settings(context), self.layout
        row = lay.row()
        row.template_list("ATMOSFX_UL_clouds", "", s, "clouds", s, "active_cloud", rows=3)
        col = row.column(align=True)
        col.operator("atmosfx.cloud_add", text="", icon="ADD")
        col.operator("atmosfx.cloud_remove", text="", icon="REMOVE")
        if s.clouds:
            layer = s.clouds[min(s.active_cloud, len(s.clouds) - 1)]
            lay.prop(layer, "kind")
            col = lay.column(align=True)
            for n in ("altitude_m", "thickness_m", "coverage", "density", "scale_m", "detail", "anisotropy"):
                col.prop(layer, n)
            col = lay.column(align=True)
            for n in ("wind_speed_ms", "wind_dir_deg", "seed", "radius_m", "edge_fade"):
                col.prop(layer, n)
            lay.prop(layer, "follow_camera")
            cost = cloudlib.estimate_domain_cost(layer, s.quality)
            lay.label(text=f"Relative cost: {cost:.1f}", icon="TIME")


class ATMOSFX_PT_deck(_Sub, bpy.types.Panel):
    bl_label = "2D Cloud Deck"
    bl_idname = "ATMOSFX_PT_deck"
    bl_parent_id = "ATMOSFX_PT_clouds"

    def draw_header(self, context):
        self.layout.prop(_settings(context), "deck_enabled", text="")

    def draw(self, context):
        s, lay = _settings(context), self.layout
        lay.active = s.deck_enabled
        _col(lay, s, ("deck_coverage", "deck_altitude", "deck_scale", "deck_opacity", "deck_softness",
                      "deck_fibre", "deck_wind_speed", "deck_wind_dir", "deck_seed"))


class ATMOSFX_PT_fog(_Sub, bpy.types.Panel):
    bl_label = "Fog and Haze"
    bl_idname = "ATMOSFX_PT_fog"

    def draw_header(self, context):
        self.layout.prop(_settings(context), "fog_enabled", text="")

    def draw(self, context):
        s, lay = _settings(context), self.layout
        lay.active = s.fog_enabled
        lay.prop(s, "fog_mode", expand=True)
        if s.fog_mode in ("WORLD", "BOTH"):
            lay.prop(s, "fog_visibility")
            lay.label(text=physics.visibility_class(s.fog_visibility).capitalize()
                      + f"  (sigma {physics.koschmieder_extinction(max(s.fog_visibility, 5.0)):.5f} /m)")
        if s.fog_mode in ("DOMAIN", "BOTH"):
            _col(lay, s, ("fog_domain_visibility", "fog_domain_radius", "fog_domain_height"))
        _col(lay, s, ("fog_scale_height", "fog_base_altitude", "fog_anisotropy", "fog_noise_amount",
                      "fog_noise_scale", "fog_absorption", "fog_color"))


class ATMOSFX_PT_info(_Sub, bpy.types.Panel):
    bl_label = "Readout"
    bl_idname = "ATMOSFX_PT_info"

    def draw(self, context):
        s, lay = _settings(context), self.layout
        v = apply.last_view.get(context.scene.name)
        if v is None:
            lay.label(text="No data yet")
            return
        col = lay.column(align=True)
        col.label(text=f"Sun: {v.sun_elevation_deg:+.1f}\u00b0 elevation, {v.sun_azimuth_deg:.0f}\u00b0 azimuth")
        col.label(text=f"Phase of day: {v.twilight}")
        col.label(text=f"Sun lamp: {v.sun_lamp_strength:.3f}   air mass {physics.airmass(v.sun_elevation_deg):.2f}")
        col.label(text=f"Moon: {v.moon_phase_name}, {v.moon_fraction * 100:.0f}% lit, {v.moon_elevation_deg:+.0f}\u00b0")
        col.label(text=f"Limiting magnitude: {v.limiting_magnitude:.1f}")
        col.label(text=f"Local time used: {astro.format_hour(v.effective_hour % 24.0)}")
        if s.time_mode == "EARTH":
            key = (s.year, s.month, s.day, round(s.latitude, 2), round(s.longitude, 2), s.utc_offset)
            if key not in _events_cache:
                import calendar
                d = min(s.day, calendar.monthrange(s.year, s.month)[1])
                _events_cache.clear()
                _events_cache[key] = astro.sun_events(s.year, s.month, d, s.utc_offset, s.latitude, s.longitude)
            ev = _events_cache[key]
            col.label(text=f"Sunrise {astro.format_hour(ev['sunrise'])}   Sunset {astro.format_hour(ev['sunset'])}")


class ATMOSFX_PT_presets(_Sub, bpy.types.Panel):
    bl_label = "Preset Files"
    bl_idname = "ATMOSFX_PT_presets"

    def draw(self, context):
        row = self.layout.row(align=True)
        row.operator("atmosfx.preset_export", icon="EXPORT")
        row.operator("atmosfx.preset_import", icon="IMPORT")


CLASSES = (ATMOSFX_PT_main, ATMOSFX_PT_time, ATMOSFX_PT_sky, ATMOSFX_PT_moon, ATMOSFX_PT_stars, ATMOSFX_UL_clouds,
           ATMOSFX_PT_clouds, ATMOSFX_PT_deck, ATMOSFX_PT_fog, ATMOSFX_PT_info, ATMOSFX_PT_presets)
