"""Animate a whole day over 240 frames and print the sun elevation at a few frames.

    python examples/day_timelapse.py

Uses Animate Time: the clock advances with the timeline, so no keyframes are needed. 24 hours over 10 seconds at 24 fps
is 2.4 simulated hours per second. The add-on must be enabled on whatever machine renders the frames.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

import atmosfx  # noqa: E402
from atmosfx.core import presets  # noqa: E402
from atmosfx.scene import apply  # noqa: E402
from atmosfx.ui import state  # noqa: E402

bpy.ops.wm.read_factory_settings(use_empty=True)
if not hasattr(bpy.types.Scene, "atmosfx"):
    atmosfx.register()
scene = bpy.context.scene
scene.render.fps = 24
scene.frame_start, scene.frame_end = 1, 240

s = scene.atmosfx
state.write_preset(s, presets.get("fair_weather_cumulus"))
s.time_mode, s.latitude, s.longitude, s.utc_offset = "EARTH", 51.5, -0.12, 1.0
s.year, s.month, s.day, s.hour = 2026, 6, 21, 0.0
s.animate_time, s.time_scale = True, 2.4
apply.create(scene)

for frame in (1, 60, 120, 180, 240):
    scene.frame_set(frame)
    v = apply.last_view[scene.name]
    print(f"frame {frame:3d}  local {v.effective_hour:5.2f} h  sun {v.sun_elevation_deg:+6.1f} deg  {v.twilight:22s} "
          f"stars to mag {v.limiting_magnitude:5.1f}")
