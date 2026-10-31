"""Operators (all idnames are ``atmosfx.*``)."""
import os
import time

import bpy
from bpy.props import StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from ..core import clouds as cloudlib
from ..core import presets as presetlib
from ..scene import apply, world
from . import state
from .props import suspend_updates

DEFAULT_PRESET = "fair_weather_cumulus"


class ATMOSFX_OT_add(bpy.types.Operator):
    bl_idname = "atmosfx.add"
    bl_label = "Add Atmosphere"
    bl_description = "Create the AtmosFX world, sun and moon lamps and cloud domains from the selected preset"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        s = scene.atmosfx
        pid = s.preset if s.preset in presetlib.ids() else DEFAULT_PRESET
        state.write_preset(s, presetlib.get(pid))
        with suspend_updates():
            s.preset = pid
        apply.create(scene)
        self.report({"INFO"}, f"AtmosFX: created from preset '{presetlib.get(pid).name}'")
        return {"FINISHED"}


class ATMOSFX_OT_remove(bpy.types.Operator):
    bl_idname = "atmosfx.remove"
    bl_label = "Remove Atmosphere"
    bl_description = "Delete everything AtmosFX created and restore the previous world"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        apply.remove(context.scene)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)


class ATMOSFX_OT_refresh(bpy.types.Operator):
    bl_idname = "atmosfx.refresh"
    bl_label = "Refresh"
    bl_description = "Rebuild the node groups and the star map, then re-apply every setting"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        from ..nodes import sky, volumes
        sky.build_group(scene)
        volumes.build_cloud_group(scene)
        volumes.build_fog_group(scene)
        world.star_image(scene.atmosfx, force=True)
        world.ensure_world(scene)
        apply.refresh(scene)
        return {"FINISHED"}


class ATMOSFX_OT_apply_preset(bpy.types.Operator):
    bl_idname = "atmosfx.apply_preset"
    bl_label = "Apply Preset"
    bl_description = "Load the selected preset into the settings"
    bl_options = {"REGISTER", "UNDO"}

    preset_id: StringProperty()

    def execute(self, context):
        pid = self.preset_id or context.scene.atmosfx.preset
        state.apply_preset(context.scene, presetlib.get(pid))
        return {"FINISHED"}


class ATMOSFX_OT_set_now(bpy.types.Operator):
    bl_idname = "atmosfx.set_now"
    bl_label = "Use Current Date and Time"
    bl_description = "Set the date, local time and UTC offset from this computer's clock"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        t = time.localtime()
        s = context.scene.atmosfx
        with suspend_updates():
            s.year, s.month, s.day = t.tm_year, t.tm_mon, t.tm_mday
            s.hour = t.tm_hour + t.tm_min / 60.0 + t.tm_sec / 3600.0
            s.utc_offset = (t.tm_gmtoff or 0) / 3600.0
        apply.refresh(context.scene)
        return {"FINISHED"}


class ATMOSFX_OT_cloud_add(bpy.types.Operator):
    bl_idname = "atmosfx.cloud_add"
    bl_label = "Add Cloud Layer"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.atmosfx
        if len(s.clouds) >= 3:
            self.report({"WARNING"}, "At most 3 cloud layers")
            return {"CANCELLED"}
        with suspend_updates():
            item = s.clouds.add()
            k = cloudlib.kind("CUMULUS")
            item.altitude_m, item.thickness_m, item.coverage = k.altitude_m, k.thickness_m, k.coverage
            item.density, item.scale_m, item.detail = k.density, k.scale_m, k.detail
            item.seed = len(s.clouds)
            s.active_cloud = len(s.clouds) - 1
        apply.refresh(context.scene)
        return {"FINISHED"}


class ATMOSFX_OT_cloud_remove(bpy.types.Operator):
    bl_idname = "atmosfx.cloud_remove"
    bl_label = "Remove Cloud Layer"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.atmosfx
        if not s.clouds:
            return {"CANCELLED"}
        with suspend_updates():
            s.clouds.remove(min(s.active_cloud, len(s.clouds) - 1))
            s.active_cloud = max(0, min(s.active_cloud, len(s.clouds) - 1))
        apply.refresh(context.scene)
        return {"FINISHED"}


class ATMOSFX_OT_preset_export(bpy.types.Operator, ExportHelper):
    bl_idname = "atmosfx.preset_export"
    bl_label = "Export Preset"
    bl_description = "Save the current atmosphere as a JSON preset you can share"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        name = os.path.splitext(os.path.basename(self.filepath))[0]
        pid = "".join(c if c.isalnum() else "_" for c in name).strip("_").lower() or "user_preset"
        p = state.capture(context.scene.atmosfx, pid, name.replace("_", " ").title())
        presetlib.save_file(self.filepath, [p])
        self.report({"INFO"}, f"Saved {self.filepath}")
        return {"FINISHED"}


class ATMOSFX_OT_preset_import(bpy.types.Operator, ImportHelper):
    bl_idname = "atmosfx.preset_import"
    bl_label = "Import Preset"
    bl_description = "Load a preset exported from AtmosFX"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        try:
            presets = presetlib.load_file(self.filepath)
        except (OSError, ValueError, KeyError) as exc:
            self.report({"ERROR"}, f"Could not read preset: {exc}")
            return {"CANCELLED"}
        if not presets:
            self.report({"ERROR"}, "File contains no presets")
            return {"CANCELLED"}
        errs = presetlib.validate(presets[0])
        if errs:
            self.report({"ERROR"}, "Invalid preset: " + "; ".join(errs[:3]))
            return {"CANCELLED"}
        state.apply_preset(context.scene, presets[0])
        return {"FINISHED"}


class ATMOSFX_OT_fix_camera_clip(bpy.types.Operator):
    bl_idname = "atmosfx.fix_camera_clip"
    bl_label = "Fix Camera Clipping"
    bl_description = "Raise the active camera's clip end so clouds and haze are not cut off"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        cam = context.scene.camera
        if cam is None or cam.type != "CAMERA":
            self.report({"WARNING"}, "No active camera")
            return {"CANCELLED"}
        need = apply.required_clip_end(context.scene.atmosfx)
        cam.data.clip_end = max(cam.data.clip_end, need * 1.1, 1000.0)
        return {"FINISHED"}


CLASSES = (ATMOSFX_OT_fix_camera_clip, ATMOSFX_OT_add, ATMOSFX_OT_remove, ATMOSFX_OT_refresh, ATMOSFX_OT_apply_preset, ATMOSFX_OT_set_now,
           ATMOSFX_OT_cloud_add, ATMOSFX_OT_cloud_remove, ATMOSFX_OT_preset_export, ATMOSFX_OT_preset_import)
