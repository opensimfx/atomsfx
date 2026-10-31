"""Render preset previews headless (Cycles, CPU). Needs the ``bpy`` wheel (Python 3.11, Blender 5.0.1).

    python tools/render_preview.py clear_noon golden_hour --out docs/img --width 640 --samples 32
    python tools/render_preview.py --all --out docs/img

The scene is a flat ground plane with a few stand-in objects so fog and aerial perspective have something to
act on. The camera looks toward ``--azimuth`` (default: the sun, or the moon at night) at ``--pitch`` degrees.
Previews are tone-mapped with an ACES fit (the bpy wheel ships without OpenColorIO configs); they are for
checking, not for grading.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def aces(x):
    import numpy as np
    x = x * 0.6
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    y = np.clip((x * (a * x + b)) / (x * (c * x + d) + e), 0, 1)
    return np.where(y <= 0.0031308, 12.92 * y, 1.055 * np.power(y, 1 / 2.4) - 0.055)


def build_scene(bpy):
    from mathutils import Vector
    scene = bpy.context.scene
    bpy.ops.mesh.primitive_plane_add(size=60000, location=(0, 0, -1.7))
    ground = bpy.context.object
    gm = bpy.data.materials.new("PreviewGround")
    gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.12, 0.10, 0.08, 1)
    gm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.95
    ground.data.materials.append(gm)
    sm = bpy.data.materials.new("PreviewObj")
    sm.use_nodes = True
    sm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.6, 0.6, 0.62, 1)
    for i, (x, y, h) in enumerate([(30, 80, 20), (-60, 160, 40), (90, 300, 60), (-150, 600, 90), (60, 1200, 150),
                                   (-300, 2500, 300), (200, 5000, 600)]):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, h / 2 - 1.7))
        o = bpy.context.object
        o.scale = (h * 0.4, h * 0.4, h)
        o.data.materials.append(sm)
    cam_data = bpy.data.cameras.new("PreviewCam")
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = (0, 0, 0)
    cam_data.clip_end = 1.0e6          # the default clip end silently cuts clouds and haze that are kilometres away
    scene.camera = cam
    return cam, cam_data


def render_one(bpy, cam, cam_data, scene, path, w, h, samples, azimuth, pitch, lens):
    import numpy as np
    from mathutils import Vector
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.cycles.samples = samples
    cam_data.lens = lens
    az, el = math.radians(azimuth), math.radians(pitch)
    d = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()
    tmp = path + ".exr"
    scene.render.filepath = tmp
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(tmp)
    arr = np.array(img.pixels[:]).reshape(h, w, 4)[..., :3]
    bpy.data.images.remove(img)
    os.remove(tmp)
    out = bpy.data.images.new("out", w, h, alpha=False)
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :3] = aces(arr)
    out.pixels.foreach_set(rgba.ravel())
    out.filepath_raw = path
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("presets", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "img"))
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--azimuth", type=float, default=None)
    ap.add_argument("--pitch", type=float, default=12.0)
    ap.add_argument("--lens", type=float, default=22.0)
    ap.add_argument("--quality", default="PREVIEW")
    ap.add_argument("--no-denoise", action="store_true", help="skip OpenImageDenoise (slower to converge)")
    args = ap.parse_args()

    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import atmosfx
    from atmosfx.core import presets as P
    from atmosfx.scene import apply
    atmosfx.register()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.use_denoising = not args.no_denoise
    if not args.no_denoise:
        scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_depth = "32"
    scene.render.use_file_extension = False
    cam, cam_data = build_scene(bpy)
    ids = P.ids() if args.all else args.presets
    os.makedirs(args.out, exist_ok=True)
    h = int(args.width * 9 / 16)
    for pid in ids:
        s = scene.atmosfx
        from atmosfx.ui import state
        state.write_preset(s, P.get(pid))
        s.quality = args.quality
        apply.create(scene) if not s.created else apply.refresh(scene)
        v = apply.last_view[scene.name]
        pitch = args.pitch
        if args.azimuth is not None:
            az = args.azimuth
        elif v.sun_elevation_deg > -3:
            az = v.sun_azimuth_deg
            pitch = min(max(v.sun_elevation_deg - 6.0, 4.0), 40.0)
        elif v.moon_elevation_deg > 5:
            az = math.degrees(math.atan2(v.moon_vec[0], v.moon_vec[1]))
            pitch = min(max(v.moon_elevation_deg - 4.0, 4.0), 45.0)
        else:
            az, pitch = 180.0, 30.0
        path = os.path.join(args.out, pid + ".png")
        render_one(bpy, cam, cam_data, scene, path, args.width, h, args.samples, az, pitch, args.lens)
        print("rendered", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
