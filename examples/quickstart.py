"""Build an AtmosFX scene from a script.

    python examples/quickstart.py                  # headless, needs the bpy wheel; saves examples/quickstart.blend
    blender --python examples/quickstart.py        # in Blender with the add-on installed (adjust the import)

Optionally renders a frame: python examples/quickstart.py --render out.png
"""
import argparse
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402

import atmosfx  # noqa: E402
from atmosfx.core import presets  # noqa: E402
from atmosfx.scene import apply  # noqa: E402
from atmosfx.ui import state  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="golden_hour")
    ap.add_argument("--render", default=None, help="render one frame to this path (slow on CPU)")
    args = ap.parse_args()

    bpy.ops.wm.read_factory_settings(use_empty=True)
    if not hasattr(bpy.types.Scene, "atmosfx"):
        atmosfx.register()
    scene = bpy.context.scene

    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens, cam_data.clip_end = 24.0, 200000.0           # clip end must exceed the cloud/haze radius
    cam = bpy.data.objects.new("Camera", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    s = scene.atmosfx
    state.write_preset(s, presets.get(args.preset))
    # Earth mode: late afternoon in Delhi, 21 June 2026 (UTC+5.5)
    s.time_mode, s.latitude, s.longitude, s.utc_offset = "EARTH", 28.6, 77.2, 5.5
    s.year, s.month, s.day, s.hour = 2026, 6, 21, 18.0
    apply.create(scene)

    view = apply.last_view[scene.name]
    print(f"sun {view.sun_elevation_deg:+.1f} deg at azimuth {view.sun_azimuth_deg:.0f}; "
          f"{view.twilight}; moon {view.moon_phase_name} ({view.moon_fraction:.0%})")
    from mathutils import Vector
    az = math.radians(view.sun_azimuth_deg)
    toward_sun = Vector((math.sin(az), math.cos(az), math.tan(math.radians(8))))     # level-ish, 8 degrees up
    cam.rotation_euler = toward_sun.normalized().to_track_quat("-Z", "Y").to_euler()

    out = os.path.join(ROOT, "examples", "quickstart.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("saved", out)
    if args.render:
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = 16
        scene.render.resolution_x, scene.render.resolution_y = 960, 540
        scene.render.filepath = os.path.abspath(args.render)
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
