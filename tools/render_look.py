"""Look bench: render presets in desktop Blender (GPU when available, AgX view) to judge how they look.

    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/render_look.py -- \
        --out /tmp/look [--quality PREVIEW|FINAL] [--width 960] [--samples 64] [preset ...]

No presets means all 28. The scene is render_preview.py's ground and stand-in blocks plus a ring of hills from
1 to 20 km, so aerial perspective has ridges to act on. The camera stands at eye height and always keeps the
horizon in frame: a low sun sits near the frame edge (backlight), a high sun is behind the camera's shoulder, at
night it looks at the moon or south. Renders go through Blender's own colour management (AgX, as a user sees
it), and each preset's render time is printed. Environment: ATMOSFX_CPU=1 forces the CPU.
``--view sun|away`` overrides the framing; ``--sheet`` writes contact_sheet.png (needs ffmpeg).
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import render_preview as RP  # noqa: E402  (stand-in scene and camera)


def use_gpu(scene) -> str:
    if os.environ.get("ATMOSFX_CPU") == "1":
        scene.cycles.device = "CPU"
        return "CPU"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("METAL", "OPTIX", "CUDA", "HIP", "ONEAPI"):
        try:
            prefs.compute_device_type = kind
        except TypeError:
            continue
        prefs.get_devices()
        devs = [d for d in prefs.devices if d.type == kind]
        if devs:
            for d in prefs.devices:
                d.use = d.type == kind
            scene.cycles.device = "GPU"
            return kind
    scene.cycles.device = "CPU"
    return "CPU"


def add_hills(bpy, seed: int = 3) -> None:
    """A 48 km square of terrain: flat within 600 m of the camera, rising to rolling ridges beyond 1 km."""
    import numpy as np
    n, half = 361, 24000.0
    xs = np.linspace(-half, half, n)
    X, Y = np.meshgrid(xs, xs)
    rng = np.random.default_rng(seed)
    Z = np.zeros_like(X)
    for octave in range(6):                                  # sum of rotated sines: cheap fbm
        k = 2 * math.pi / (9000.0 / 2.1 ** octave)
        for _ in range(3):
            a, ph = rng.uniform(0, math.pi), rng.uniform(0, 2 * math.pi)
            Z += np.sin(k * (X * math.cos(a) + Y * math.sin(a)) + ph) / 1.9 ** octave
    R = np.hypot(X, Y)
    ramp = np.clip((R - 600.0) / 6000.0, 0.0, 1.0) ** 1.5
    Z = (Z - Z.min()) * 110.0 * ramp - 1.75
    verts = np.stack([X, Y, Z], -1).reshape(-1, 3)
    i = np.arange(n - 1)
    a = (i[:, None] * n + i[None, :]).ravel()
    faces = np.stack([a, a + 1, a + n + 1, a + n], -1)
    me = bpy.data.meshes.new("LookHills")
    me.from_pydata(verts.tolist(), [], faces.tolist())
    me.shade_smooth() if hasattr(me, "shade_smooth") else None
    ob = bpy.data.objects.new("LookHills", me)
    bpy.context.scene.collection.objects.link(ob)
    m = bpy.data.materials.new("LookHills")
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.09, 0.10, 0.06, 1)       # dry grass / scrub albedo ~0.1
    bsdf.inputs["Roughness"].default_value = 0.95
    me.materials.append(m)


def frame(v, view: str):
    """Camera azimuth and pitch (degrees) for a SkyView."""
    if v.sun_elevation_deg > -3:
        if view == "sun" or (view == "auto" and v.sun_elevation_deg < 22):
            return v.sun_azimuth_deg + 24.0, min(max(v.sun_elevation_deg * 0.5, 3.0), 12.0)
        return v.sun_azimuth_deg + 150.0, 7.0
    if v.moon_elevation_deg > 5:
        return math.degrees(math.atan2(v.moon_vec[0], v.moon_vec[1])) + 20.0, min(max(v.moon_elevation_deg * 0.6, 6.0), 30.0)
    return 180.0, 22.0


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("presets", nargs="*")
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--quality", default="PREVIEW")
    ap.add_argument("--lens", type=float, default=24.0)
    ap.add_argument("--view", default="auto", choices=("auto", "sun", "away"))
    ap.add_argument("--sheet", action="store_true")
    args = ap.parse_args(argv)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    import atmosfx
    from atmosfx.core import presets as P
    from atmosfx.scene import apply
    from atmosfx.ui import state

    atmosfx.register()
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    device = use_gpu(scene)
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = os.environ.get("ATMOSFX_LOOK", "None")   # Blender's default: what a user sees
    scene.render.image_settings.file_format = "PNG"
    cam, cam_data = RP.build_scene(bpy)
    add_hills(bpy)
    os.makedirs(args.out, exist_ok=True)
    w, h = args.width, int(args.width * 9 / 16)
    scene.render.resolution_x, scene.render.resolution_y = w, h
    cam_data.lens = args.lens
    print(f"[look] device {device}, quality {args.quality}, {w}x{h}, {args.samples} samples", flush=True)
    for pid in args.presets or P.ids():
        s = scene.atmosfx
        state.write_preset(s, P.get(pid))
        s.quality = args.quality
        if os.environ.get("ATMOSFX_NOFOG") == "1":
            s.fog_enabled = False
        if os.environ.get("ATMOSFX_NODECK") == "1":
            s.deck_enabled = False
        if "ATMOSFX_CLOUDDENS" in os.environ:
            for l in s.clouds:
                l.density *= float(os.environ["ATMOSFX_CLOUDDENS"])
        if os.environ.get("ATMOSFX_NOCLOUDS") == "1":
            for l in s.clouds:
                l.enabled = False
        # ATMOSFX_SET="eclipse=1,halo_strength=5" (settings), ATMOSFX_LAYER="evolution=2,lightning=6" (every cloud
        # layer), ATMOSFX_FRAME=48 (render that frame)
        for var, targets in (("ATMOSFX_SET", [s]), ("ATMOSFX_LAYER", list(s.clouds))):
            for item in filter(None, os.environ.get(var, "").split(",")):
                k, v = item.split("=")
                for t in targets:
                    cur = getattr(t, k)
                    setattr(t, k, type(cur)(float(v)) if not hasattr(cur, "__len__") else tuple(float(x) for x in v.split(":")))
        apply.create(scene) if not s.created else apply.refresh(scene)
        if "ATMOSFX_FRAME" in os.environ:
            scene.frame_set(int(os.environ["ATMOSFX_FRAME"]))
        scene.cycles.samples = args.samples           # after the quality tier, which sets its own
        if "ATMOSFX_BOUNCES" in os.environ:
            scene.cycles.volume_bounces = int(os.environ["ATMOSFX_BOUNCES"])
            scene.cycles.max_bounces = max(scene.cycles.max_bounces, scene.cycles.volume_bounces)
        if "ATMOSFX_CLOUDFILL" in os.environ:
            for m in bpy.data.materials:
                if m.name.startswith("AtmosFX Cloud") and m.node_tree:
                    g = m.node_tree.nodes["AtmosFX Group"]
                    g.inputs["Fill"].default_value *= float(os.environ["ATMOSFX_CLOUDFILL"])
                    g.inputs["Glow Strength"].default_value *= float(os.environ["ATMOSFX_CLOUDFILL"])
        if os.environ.get("ATMOSFX_NOCLOUDSUN") == "1" and bpy.data.objects.get("AtmosFX Sun Clouds"):
            bpy.data.objects["AtmosFX Sun Clouds"].hide_render = True
        if os.environ.get("ATMOSFX_NOLINK") == "1" and bpy.data.objects.get("AtmosFX Sun Clouds"):
            bpy.data.objects["AtmosFX Sun Clouds"].hide_render = True
            bpy.data.objects["AtmosFX Sun"].light_linking.receiver_collection = None
        for key, sock in (("ATMOSFX_FOGFILL", "Fill"), ("ATMOSFX_AIR", "Air Density")):   # bench overrides
            if key in os.environ:
                for m in bpy.data.materials:
                    if m.name.startswith(("AtmosFX Haze", "AtmosFX Fog")) and m.node_tree:
                        g = m.node_tree.nodes.get("AtmosFX Group")
                        if g is not None:
                            g.inputs[sock].default_value *= float(os.environ[key])
        v = apply.last_view[scene.name]
        az, pitch = frame(v, args.view)
        pitch = float(os.environ.get("ATMOSFX_PITCH", pitch))
        cam.location.z = 0.0
        if s.fog_enabled and s.fog_mode in ("DOMAIN", "BOTH"):          # a fog bank is seen from a hillside
            cam.location.z = s.fog_base_altitude + s.fog_domain_height * 2.5
            pitch = -4.0
        from mathutils import Vector
        a, e = math.radians(az), math.radians(pitch)
        d = Vector((math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)))
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        if os.environ.get("ATMOSFX_AIM_SUN") == "1":                 # close-ups of the solar disc (eclipses)
            cam.rotation_euler = Vector(v.sun_vec).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = os.path.join(args.out, pid + ".png")
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"[look] {pid}: {time.time() - t0:.1f}s exposure {scene.view_settings.exposure:+.2f} "
              f"sun {v.sun_elevation_deg:.1f}deg", flush=True)
    if args.sheet:
        import subprocess
        names = args.presets or P.ids()
        cols = 4
        inputs = []
        for pid in names:
            inputs += ["-i", os.path.join(args.out, pid + ".png")]
        rows = (len(names) + cols - 1) // cols
        pads = "".join(f"[{i}:v]" for i in range(len(names)))      # row-major, in the order printed above
        layout = "|".join(("+".join(["w0"] * (i % cols)) or "0") + "_" + ("+".join(["h0"] * (i // cols)) or "0")
                          for i in range(len(names)))
        flt = f"{pads}xstack=inputs={len(names)}:layout={layout}:fill=black"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", flt,
                        os.path.join(args.out, "contact_sheet.png")], check=False)
        print(f"[look] sheet {rows}x{cols}", flush=True)
    return 0


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    code = main(argv)
    sys.stdout.flush()
    os._exit(code)
