"""Headless Blender checks for AtmosFX. Run with a Python that has the ``bpy`` wheel (3.11, Blender 5.0.1 verified):

    python tests/blender_smoke.py            # fast checks (~20 s)
    ATMOSFX_RENDER_TESTS=1 python tests/blender_smoke.py     # adds Cycles alignment renders (~2 min on one core)

Exit status is the number of failed checks.
"""
import math
import os
import sys
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Euler, Matrix, Vector  # noqa: E402

import atmosfx  # noqa: E402
from atmosfx.core import astro, presets as P  # noqa: E402
from atmosfx.core.stars_data import BY_NAME  # noqa: E402
from atmosfx.scene import apply, objects, world  # noqa: E402
from atmosfx.ui import state  # noqa: E402

CHECKS = []


def check(fn):
    CHECKS.append(fn)
    return fn


def fresh(with_camera=True):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    atmosfx.register() if not hasattr(bpy.types.Scene, "atmosfx") else None
    scene = bpy.context.scene
    if with_camera:
        cd = bpy.data.cameras.new("Cam")
        cam = bpy.data.objects.new("Cam", cd)
        scene.collection.objects.link(cam)
        scene.camera = cam
    return scene


def all_links_valid():
    for tree in list(bpy.data.node_groups) + [m.node_tree for m in bpy.data.materials if m.node_tree] + \
            [w.node_tree for w in bpy.data.worlds if w.node_tree]:
        bad = [l for l in tree.links if not l.is_valid]
        assert not bad, f"{tree.name}: {len(bad)} invalid links"


@check
def register_and_create():
    scene = fresh()
    assert bpy.ops.atmosfx.add() == {"FINISHED"}
    s = scene.atmosfx
    assert s.created and world.is_ours(scene.world)
    names = {o.name for o in bpy.data.objects}
    assert {"AtmosFX Sun", "AtmosFX Moon"} <= names
    assert {"AtmosFX Sky", "AtmosFX Cloud", "AtmosFX Fog"} <= {g.name for g in bpy.data.node_groups}
    imgs = [i for i in bpy.data.images if i.name.startswith(world.STAR_PREFIX)]
    assert len(imgs) == 1 and imgs[0].packed_file is not None and imgs[0].is_float
    all_links_valid()


@check
def every_preset_applies():
    scene = fresh()
    s = scene.atmosfx
    for pid in P.ids():
        p = P.get(pid)
        state.write_preset(s, p)
        if not s.created:
            apply.create(scene)
        else:
            apply.refresh(scene)
        v = apply.last_view[scene.name]
        assert v is not None, pid
        n_clouds = sum(1 for o in bpy.data.objects if o.get(objects.ROLE_KEY) == "cloud")
        assert n_clouds == len(p.clouds), (pid, n_clouds)
        haze = bpy.data.objects.get(objects.HAZE_NAME) is not None
        dom = bpy.data.objects.get(objects.FOG_NAME) is not None
        assert haze == (p.fog.enabled and p.fog.mode in ("WORLD", "BOTH")), pid
        assert dom == (p.fog.enabled and p.fog.mode in ("DOMAIN", "BOTH")), pid
        sun = bpy.data.objects["AtmosFX Sun"].data
        assert sun.energy == (pytest_approx(v.sun_lamp_strength) if s.use_sun_lamp else 0.0), pid
    all_links_valid()


def pytest_approx(x, tol=1e-5):
    class A(float):
        def __eq__(self, other):
            return abs(float(other) - float(self)) <= tol * max(1.0, abs(float(self)))
    return A(x)


@check
def preset_enum_applies_through_the_property():
    scene = fresh()
    s = scene.atmosfx
    apply.create(scene)
    s.preset = "storm_cumulonimbus"
    assert len(s.clouds) == 2 and s.clouds[0].kind == "CUMULONIMBUS" and s.fog_enabled
    assert abs(s.sun_elevation - 28.0) < 1e-6


@check
def cloud_layer_operators():
    scene = fresh()
    s = scene.atmosfx
    state.write_preset(s, P.get("clear_noon"))
    apply.create(scene)
    for i in range(3):
        assert bpy.ops.atmosfx.cloud_add() == {"FINISHED"}
    assert len(s.clouds) == 3 and bpy.ops.atmosfx.cloud_add() == {"CANCELLED"}
    assert sorted(o.name for o in bpy.data.objects if o.get(objects.ROLE_KEY) == "cloud") == \
        ["AtmosFX Cloud 1", "AtmosFX Cloud 2", "AtmosFX Cloud 3"]
    s.active_cloud = 1
    bpy.ops.atmosfx.cloud_remove()
    assert len(s.clouds) == 2 and bpy.data.objects.get("AtmosFX Cloud 3") is None
    obj = bpy.data.objects["AtmosFX Cloud 1"]
    s.clouds[0].radius_m = 20000.0
    s.clouds[0].altitude_m = 2500.0
    assert tuple(obj.scale)[:2] == (20000.0, 20000.0) and obj.location.z == 2500.0
    s.clouds[0].enabled = False
    assert obj.hide_render
    s.clouds[0].kind = "STRATUS"                      # switching kind loads its defaults
    assert abs(s.clouds[0].altitude_m - 500.0) < 1e-6 and abs(s.clouds[0].thickness_m - 400.0) < 1e-6
    assert any(c.type == "COPY_LOCATION" for c in obj.constraints)
    s.clouds[0].follow_camera = False
    assert not obj.constraints


@check
def cloud_sun_is_light_linked_to_the_cloud_domains():
    scene = fresh()
    s = scene.atmosfx
    state.write_preset(s, P.get("sunset_clouds"))
    apply.create(scene)
    ground, cs = bpy.data.objects[objects.SUN_NAME], bpy.data.objects.get(objects.CLOUD_SUN_NAME)
    assert cs is not None and cs.data.energy > ground.data.energy
    names = {o.name for o in bpy.data.objects if o.get(objects.ROLE_KEY) == "cloud"}
    ex = ground.light_linking.receiver_collection
    inc = cs.light_linking.receiver_collection
    assert {o.name for o in ex.objects} == names and all(i.light_linking.link_state == "EXCLUDE" for i in ex.collection_objects)
    assert {o.name for o in inc.objects} == names and all(i.light_linking.link_state == "INCLUDE" for i in inc.collection_objects)
    s.clouds.clear()
    apply.refresh(scene)
    assert bpy.data.objects.get(objects.CLOUD_SUN_NAME) is None and ground.light_linking.receiver_collection is None
    assert bpy.data.collections.get(objects.LL_EXCLUDE) is None


@check
def fog_modes_create_the_right_objects():
    scene = fresh()
    s = scene.atmosfx
    state.write_preset(s, P.get("dense_fog"))
    apply.create(scene)
    assert bpy.data.objects.get(objects.HAZE_NAME) and not bpy.data.objects.get(objects.FOG_NAME)
    r, h, z0 = objects.haze_dimensions(s)
    assert r == 300.0 and z0 == -200.0 and abs(h - (5 * 300 + 200)) < 1e-6
    s.fog_mode = "DOMAIN"
    assert not bpy.data.objects.get(objects.HAZE_NAME) and bpy.data.objects.get(objects.FOG_NAME)
    s.fog_mode = "BOTH"
    assert bpy.data.objects.get(objects.HAZE_NAME) and bpy.data.objects.get(objects.FOG_NAME)
    s.fog_enabled = False
    assert not bpy.data.objects.get(objects.HAZE_NAME) and not bpy.data.objects.get(objects.FOG_NAME)
    s.fog_enabled, s.fog_mode, s.fog_visibility = True, "WORLD", 20000.0
    node = bpy.data.materials["AtmosFX Haze"].node_tree.nodes["AtmosFX Group"]
    assert abs(node.inputs["Density"].default_value - 3.912 / 20000.0) < 1e-6
    assert abs(objects.haze_dimensions(s)[0] - 28000.0) < 1e-6
    # no world volume is ever created (Cycles blanks the sky for infinite world volumes)
    out = next(n for n in scene.world.node_tree.nodes if n.bl_idname == "ShaderNodeOutputWorld")
    assert not out.inputs["Volume"].is_linked


@check
def time_driver_follows_the_frame_and_fps():
    scene = fresh()
    apply.create(scene)
    scene.frame_set(49)
    bpy.context.view_layer.update()
    node = scene.world.node_tree.nodes["AtmosFX Sky"].node_tree.nodes["AtmosFX Time"]
    assert abs(node.outputs[0].default_value - 2.0) < 1e-4            # (49 - 1) / 24 fps
    scene.render.fps = 48
    scene.frame_set(49)
    bpy.context.view_layer.update()
    assert abs(node.outputs[0].default_value - 1.0) < 1e-4


@check
def time_animation_handler_moves_the_sun():
    scene = fresh()
    s = scene.atmosfx
    state.write_preset(s, P.get("clear_noon"))
    s.time_mode, s.latitude, s.longitude, s.hour = "EARTH", 28.6, 77.2, 6.0
    s.utc_offset, s.animate_time, s.time_scale = 5.5, True, 2.0
    apply.create(scene)
    e0 = apply.last_view[scene.name].sun_elevation_deg
    scene.frame_set(121)                                              # 5 s at 24 fps -> 10 simulated hours
    e1 = apply.last_view[scene.name].sun_elevation_deg
    assert abs(apply.last_view[scene.name].effective_hour - 16.0) < 1e-6
    assert e1 != e0


@check
def euler_convention_matches_mathutils():
    for e in [(0.3, 0.5, 0.7), (-1.0, 0.2, 2.5), (2.0, -0.9, -0.4)]:
        mine = astro.euler_xyz_to_matrix(e)
        theirs = Euler(e, "XYZ").to_matrix()
        assert max(abs(mine[i][j] - theirs[i][j]) for i in range(3) for j in range(3)) < 1e-5     # mathutils is float32
        assert max(abs(a - b) for a, b in zip(astro.euler_xyz(theirs), e)) < 1e-5


@check
def lamps_point_at_the_sun_and_moon():
    scene = fresh()
    s = scene.atmosfx
    state.write_preset(s, P.get("full_moon_night"))
    apply.create(scene)
    bpy.context.view_layer.update()
    v = apply.last_view[scene.name]
    moon = bpy.data.objects["AtmosFX Moon"]
    shine = moon.matrix_world.to_3x3() @ Vector((0, 0, -1))           # a Sun lamp shines along local -Z
    assert (shine + Vector(v.moon_vec)).length < 1e-5                 # it travels from the Moon toward the scene
    assert abs(moon.data.angle - 2 * v.moon_radius_rad) < 1e-9
    sun = bpy.data.objects["AtmosFX Sun"]
    assert sun.hide_render and sun.data.energy == 0.0                 # sun far below the horizon
    state.write_preset(s, P.get("clear_noon"))
    apply.refresh(scene)
    bpy.context.view_layer.update()
    v = apply.last_view[scene.name]
    shine = sun.matrix_world.to_3x3() @ Vector((0, 0, -1))
    assert (shine + Vector(v.sun_vec)).length < 1e-5 and not sun.hide_render and sun.data.energy > 2.5


@check
def sky_node_follows_the_sun():
    scene = fresh()
    s = scene.atmosfx
    state.write_preset(s, P.get("clear_noon"))
    s.sun_elevation, s.sun_azimuth = 25.0, 100.0
    apply.create(scene)
    sky = scene.world.node_tree.nodes["AtmosFX Sky"].node_tree.nodes["Sky"]
    assert abs(math.degrees(sky.sun_elevation) - 25.0) < 1e-4
    assert abs(math.degrees(sky.sun_rotation) - 100.0) < 1e-4         # azimuth from +Y toward +X (measured by render)
    assert not sky.sun_disc and sky.sky_type == "MULTIPLE_SCATTERING"
    s.quality = "DRAFT"
    assert sky.sky_type == "SINGLE_SCATTERING"


@check
def render_settings_follow_the_quality_tier():
    scene = fresh()
    s = scene.atmosfx
    apply.create(scene)
    s.quality = "FINAL"
    assert scene.cycles.volume_bounces == 12 and scene.cycles.volume_step_rate == 0.75
    s.quality = "DRAFT"
    assert scene.cycles.volume_bounces == 2
    s.auto_render_settings = False
    scene.cycles.volume_bounces = 5
    s.quality = "FINAL"
    assert scene.cycles.volume_bounces == 5                           # the user opted out


@check
def camera_clip_warning_and_fix():
    scene = fresh()
    s = scene.atmosfx
    state.write_preset(s, P.get("fair_weather_cumulus"))
    apply.create(scene)
    cam = scene.camera
    cam.data.clip_end = 100.0
    assert apply.required_clip_end(s) >= 33000.0
    assert bpy.ops.atmosfx.fix_camera_clip() == {"FINISHED"}
    assert cam.data.clip_end >= apply.required_clip_end(s)


@check
def preset_file_round_trip_through_operators():
    scene = fresh()
    s = scene.atmosfx
    state.write_preset(s, P.get("sunset_clouds"))
    apply.create(scene)
    path = os.path.join(tempfile.mkdtemp(), "My Sunset.json")
    assert bpy.ops.atmosfx.preset_export(filepath=path) == {"FINISHED"}
    (p,) = P.load_file(path)
    assert p.id == "my_sunset" and P.validate(p) == []
    ref = P.get("sunset_clouds")
    assert abs(p.sun.elevation_deg - ref.sun.elevation_deg) < 1e-4 and p.clouds[0].kind == "ALTOCUMULUS"
    s.sun_elevation = 40.0
    s.clouds.clear()
    assert bpy.ops.atmosfx.preset_import(filepath=path) == {"FINISHED"}
    assert abs(s.sun_elevation - ref.sun.elevation_deg) < 1e-4 and len(s.clouds) == 1
    bad = os.path.join(tempfile.mkdtemp(), "bad.json")
    open(bad, "w").write('{"schema": 1, "presets": [{"id": "x y", "name": "X", "sun": {"elevation_deg": 500}}]}')
    try:
        bpy.ops.atmosfx.preset_import(filepath=bad)
        raise AssertionError("an invalid preset must be rejected")
    except RuntimeError as exc:                                          # operators that report ERROR raise in scripts
        assert "Invalid preset" in str(exc)
    assert abs(s.sun_elevation - ref.sun.elevation_deg) < 1e-4            # settings untouched by the rejected file


@check
def save_and_reload_keeps_everything():
    scene = fresh()
    s = scene.atmosfx
    state.write_preset(s, P.get("golden_hour"))
    apply.create(scene)
    path = os.path.join(tempfile.mkdtemp(), "atmos.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    scene = bpy.context.scene
    s = scene.atmosfx
    assert s.created and world.is_ours(scene.world) and abs(s.sun_elevation - 6.0) < 1e-6
    img = [i for i in bpy.data.images if i.name.startswith(world.STAR_PREFIX)][0]
    px = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    assert px.max() > 100.0, "packed star map lost its float data"
    assert apply.last_view.get(scene.name) is not None                  # load_post handler refreshed the scene
    all_links_valid()


@check
def remove_restores_the_previous_world_and_cleans_up():
    scene = fresh()
    mine = bpy.data.worlds.new("My World")
    scene.world = mine
    apply.create(scene)
    assert world.is_ours(scene.world)
    assert bpy.ops.atmosfx.remove() == {"FINISHED"}
    assert scene.world == mine and not scene.atmosfx.created
    left = [d.name for coll in (bpy.data.objects, bpy.data.node_groups, bpy.data.materials, bpy.data.meshes,
                                bpy.data.collections, bpy.data.worlds) for d in coll if d.name.startswith("AtmosFX")]
    left += [i.name for i in bpy.data.images if i.name.startswith(world.STAR_PREFIX)]
    assert not left, left


@check
def refresh_operator_rebuilds_groups():
    scene = fresh()
    apply.create(scene)
    before = bpy.data.node_groups["AtmosFX Sky"].as_pointer()
    assert bpy.ops.atmosfx.refresh() == {"FINISHED"}
    assert bpy.data.node_groups["AtmosFX Sky"].as_pointer() != before
    assert scene.world.node_tree.nodes["AtmosFX Sky"].node_tree.name == "AtmosFX Sky"
    all_links_valid()


@check
def star_image_cache_is_content_addressed():
    scene = fresh()
    s = scene.atmosfx
    s.star_resolution = "2048"
    apply.create(scene)
    a = [i.name for i in bpy.data.images if i.name.startswith(world.STAR_PREFIX)]
    assert len(a) == 1
    s.star_brightness = 3.0                                             # not part of the bake key
    assert [i.name for i in bpy.data.images if i.name.startswith(world.STAR_PREFIX)] == a
    s.star_seed = 7                                                     # is part of the key: new image, old one purged
    b = [i.name for i in bpy.data.images if i.name.startswith(world.STAR_PREFIX)]
    assert len(b) == 1 and b != a


# ------------------------------------------------------------------------- render checks
def _render_setup(scene, w=96, h=96, lens=300, samples=24):
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_depth = "32"
    scene.render.use_file_extension = False
    scene.camera.data.lens = lens
    scene.camera.data.clip_end = 1.0e6


def _render(scene, vec, w=96, h=96):
    cam = scene.camera
    cam.rotation_euler = Vector(vec).normalized().to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()
    scene.render.filepath = os.path.join(tempfile.gettempdir(), "atmosfx_check.exr")
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(scene.render.filepath)
    a = np.array(img.pixels[:]).reshape(h, w, 4)[..., :3]
    bpy.data.images.remove(img)
    return a @ np.array([0.2126, 0.7152, 0.0722])


def _peak_offset_deg(lum, lens, w=96):
    iy, ix = np.unravel_index(lum.argmax(), lum.shape)
    px_deg = math.degrees(36.0 / lens / w)
    return math.hypot(ix - w // 2 + 0.5, iy - w // 2 + 0.5) * px_deg


def render_checks():
    @check
    def stars_render_where_the_ephemeris_says():
        scene = fresh()
        s = scene.atmosfx
        state.write_preset(s, P.get("starry_night"))
        s.time_mode, s.latitude, s.longitude, s.utc_offset = "EARTH", 28.6, 77.2, 5.5
        s.year, s.month, s.day, s.hour = 2026, 1, 15, 20.5
        s.star_brightness, s.magnitude_limit, s.moon_enabled = 8.0, 6.5, False
        apply.create(scene)
        _render_setup(scene)
        v = apply.last_view[scene.name]
        for name in ("Sirius", "Rigel", "Betelgeuse"):
            st = BY_NAME[name]
            d = astro.mat_vec(v.scene_from_j2000, astro.radec_to_vec(st.ra_deg, st.dec_deg))
            assert d[2] > 0.2, name
            off = _peak_offset_deg(_render(scene, d), 300)
            assert off < 0.3, f"{name} rendered {off:.2f} degrees from its predicted position"

    @check
    def sun_disc_renders_at_the_predicted_direction():
        scene = fresh()
        s = scene.atmosfx
        state.write_preset(s, P.get("clear_noon"))
        s.time_mode, s.latitude, s.longitude, s.utc_offset = "EARTH", 28.6, 77.2, 5.5
        s.year, s.month, s.day, s.hour, s.fog_enabled = 2026, 3, 10, 15.0, False
        apply.create(scene)
        _render_setup(scene, lens=150, samples=8)
        v = apply.last_view[scene.name]
        assert _peak_offset_deg(_render(scene, v.sun_vec), 150) < 0.3

    @check
    def cloud_coverage_matches_the_setting():
        scene = fresh()
        scene.render.engine = "CYCLES"
        from atmosfx.nodes import volumes
        from atmosfx.core import clouds as C
        g = volumes.ensure_cloud_group(scene)
        mat = bpy.data.materials.new("dbg")
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission")
        gn = nt.nodes.new("ShaderNodeGroup")
        gn.node_tree = g
        nt.links.new(gn.outputs["Density"], em.inputs["Color"])
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        bpy.ops.mesh.primitive_plane_add(size=20000, location=(0, 0, 0))
        plane = bpy.context.object
        plane.data.materials.append(mat)
        cd = bpy.data.cameras.new("o")
        cd.type, cd.ortho_scale, cd.clip_end = "ORTHO", 20000, 1e6
        cam = bpy.data.objects.new("o", cd)
        scene.collection.objects.link(cam)
        scene.camera = cam
        cam.location = (0, 0, 9000)
        scene.world = bpy.data.worlds.new("W")
        _render_setup(scene, 160, 160, 50, 1)
        scene.camera.data.lens = 50
        k = C.kind("CUMULUS")
        for cov in (0.15, 0.4, 0.7):
            lay = type("L", (), dict(kind="CUMULUS", altitude_m=k.altitude_m, thickness_m=k.thickness_m, coverage=cov,
                                     density=0.02, scale_m=k.scale_m, detail=k.detail, anisotropy=0.8, wind_speed_ms=0,
                                     wind_dir_deg=0, seed=1, radius_m=1e6, edge_fade=0.0))
            plane.location.z = k.altitude_m + 0.5 * k.thickness_m
            for name, val in C.socket_values(lay, "PREVIEW").items():
                sock = gn.inputs.get(name)
                if sock is not None:
                    sock.default_value = val
            bpy.context.view_layer.update()
            lum = _render(scene, (0, 0, -1), 160, 160)
            frac = float((lum > 1e-3).mean())
            assert abs(frac - cov) < 0.12, f"coverage {cov} rendered as filled fraction {frac:.2f}"

    @check
    def world_with_haze_still_shows_the_sky():
        scene = fresh()
        s = scene.atmosfx
        state.write_preset(s, P.get("summer_haze"))
        apply.create(scene)
        _render_setup(scene, 64, 64, 22, 6)
        lum = _render(scene, (0, 1, 0.4), 64, 64)
        assert lum.mean() > 0.01, "sky went black with haze enabled"


def main() -> int:
    if os.environ.get("ATMOSFX_RENDER_TESTS"):
        render_checks()
    failed = 0
    for fn in CHECKS:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"{len(CHECKS) - failed}/{len(CHECKS)} Blender checks passed")
    return failed


if __name__ == "__main__":
    sys.exit(main())
