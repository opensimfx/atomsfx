"""Objects AtmosFX owns: the collection, sun/moon lamps, cloud domains, fog domain."""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Vector

from ..core import clouds as cloudlib
from ..core import physics
from ..nodes import volumes
from ..nodes.dsl import Builder

COLLECTION = "AtmosFX"
ROLE_KEY = "atmosfx_role"
SUN_NAME, MOON_NAME = "AtmosFX Sun", "AtmosFX Moon"
CLOUD_SUN_NAME = "AtmosFX Sun Clouds"
LL_EXCLUDE = "AtmosFX Sun Exclude"          # cloud domains the ground sun must not light
LL_CLOUDS = "AtmosFX Sun Clouds Receivers"   # the only objects the cloud sun lights
CLOUD_PREFIX = "AtmosFX Cloud "
FOG_NAME = "AtmosFX Fog Domain"
HAZE_NAME = "AtmosFX Haze"
MESH_NAME = "AtmosFX Domain Cylinder"


def ensure_collection(scene: bpy.types.Scene) -> bpy.types.Collection:
    c = bpy.data.collections.get(COLLECTION)
    if c is None:
        c = bpy.data.collections.new(COLLECTION)
    if c.name not in scene.collection.children:
        scene.collection.children.link(c)
    return c


def owned_objects() -> list:
    return [o for o in bpy.data.objects if o.get(ROLE_KEY)]


def _link(obj, coll) -> None:
    if obj.name not in coll.objects:
        coll.objects.link(obj)


# ----------------------------------------------------------------------------- lamps
def _ensure_lamp(scene, name: str, role: str, location) -> bpy.types.Object:
    obj = bpy.data.objects.get(name)
    if obj is None:
        data = bpy.data.lights.new(name, "SUN")
        obj = bpy.data.objects.new(name, data)
        obj.location = location
        obj.rotation_mode = "QUATERNION"
    obj[ROLE_KEY] = role
    _link(obj, ensure_collection(scene))
    return obj


def _aim(obj, toward: tuple) -> None:
    """Point a Sun lamp so its light travels from direction ``toward`` into the scene (it shines along -Z)."""
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector(toward).to_track_quat("Z", "Y")


def update_lamps(scene, s, view) -> None:
    sun = _ensure_lamp(scene, SUN_NAME, "sun", (0.0, 0.0, 60.0))
    on = s.use_sun_lamp and view.sun_lamp_strength > 1e-5
    sun.data.energy = view.sun_lamp_strength if s.use_sun_lamp else 0.0
    sun.data.color = view.sun_color
    sun.data.angle = max(2.0 * view.sun_radius_rad, 1e-4)
    sun.hide_render = not on
    _aim(sun, view.sun_vec)

    moon = _ensure_lamp(scene, MOON_NAME, "moon", (4.0, 0.0, 60.0))
    mon = s.moon_enabled and view.moon_lamp_strength > 1e-7 and view.moon_elevation_deg > -1.0
    moon.data.energy = view.moon_lamp_strength if mon else 0.0
    moon.data.color = view.moon_color
    moon.data.angle = max(2.0 * view.moon_radius_rad, 1e-4)
    moon.hide_render = not mon
    _aim(moon, view.moon_vec)


def _ll_collection(name: str, members: list, state: str) -> bpy.types.Collection:
    """A light-linking collection (not part of the scene) holding exactly ``members`` in ``state``."""
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    want = {o.name for o in members}
    for o in list(c.objects):
        if o.name not in want:
            c.objects.unlink(o)
    for o in members:
        if o.name not in c.objects:
            c.objects.link(o)
    for item in c.collection_objects:
        item.light_linking.link_state = state
    return c


def update_cloud_sun(scene, s, view) -> None:
    """Light volumetric clouds with their own sun, via light linking.

    Sunlight reaching a cloud at 3 km has crossed far less air than at the ground, so at sunset the ground is
    already dim and red while the clouds are still bright and golden. One lamp cannot do both, so the ground sun
    excludes the cloud domains and a second sun, attenuated at cloud height, lights only them. Cloud domains still
    block the ground sun (shadow linking is untouched), so cloud shadows on the ground are unaffected.
    """
    cloud_objs = [o for o in bpy.data.objects if o.get(ROLE_KEY) == "cloud"]
    ground = bpy.data.objects.get(SUN_NAME)
    cs = bpy.data.objects.get(CLOUD_SUN_NAME)
    if not cloud_objs or not s.use_sun_lamp or ground is None:
        if cs is not None:
            bpy.data.objects.remove(cs, do_unlink=True)
        if ground is not None:
            ground.light_linking.receiver_collection = None
        for n in (LL_EXCLUDE, LL_CLOUDS):
            c = bpy.data.collections.get(n)
            if c is not None:
                bpy.data.collections.remove(c)
        return
    cs = _ensure_lamp(scene, CLOUD_SUN_NAME, "cloud_sun", (-4.0, 0.0, 60.0))
    on = view.cloud_sun_strength > 1e-5
    cs.data.energy = view.cloud_sun_strength
    cs.data.color = view.cloud_sun_color
    cs.data.angle = max(2.0 * view.sun_radius_rad, 1e-4)
    cs.hide_render = not on
    _aim(cs, view.sun_vec)
    ground.light_linking.receiver_collection = _ll_collection(LL_EXCLUDE, cloud_objs, "EXCLUDE")
    cs.light_linking.receiver_collection = _ll_collection(LL_CLOUDS, cloud_objs, "INCLUDE")


# -------------------------------------------------------------------------- domains
def _cylinder_mesh() -> bpy.types.Mesh:
    me = bpy.data.meshes.get(MESH_NAME)
    if me is not None:
        return me
    me = bpy.data.meshes.new(MESH_NAME)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=64, radius1=1.0, radius2=1.0, depth=1.0)
    bmesh.ops.translate(bm, vec=(0.0, 0.0, 0.5), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    return me


def _ensure_domain(scene, name: str, role: str) -> bpy.types.Object:
    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, _cylinder_mesh())
    obj[ROLE_KEY] = role
    obj.display_type = "WIRE"
    obj.hide_select = False
    obj.visible_shadow = True
    _link(obj, ensure_collection(scene))
    return obj


def _follow_camera(scene, obj, on: bool) -> None:
    con = obj.constraints.get("AtmosFX Follow")
    if on and scene.camera is not None:
        if con is None:
            con = obj.constraints.new("COPY_LOCATION")
            con.name = "AtmosFX Follow"
        con.target = scene.camera
        con.use_z = False
    elif con is not None:
        obj.constraints.remove(con)


def _volume_material(name: str, tree, builder=None):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
    nt = mat.node_tree
    if "AtmosFX Group" not in nt.nodes:
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        out.location = (500, 0)
        g = nt.nodes.new("ShaderNodeGroup")
        g.name = g.label = "AtmosFX Group"
        g.location = (200, 0)
        g.node_tree = tree                      # sockets only exist once a tree is assigned
        nt.links.new(g.outputs["Volume"], out.inputs["Volume"])
        if builder:
            builder(nt, g)
    return mat


def _fog_edge_fade(nt, group_node) -> None:
    """Fade a cylindrical fog object to zero at its side and top using Generated (0..1 bounding box) coordinates."""
    b = Builder(nt)
    b.x, b.y = -600.0, 0.0
    gen = b.node("ShaderNodeTexCoord").outputs["Generated"]
    gx, gy, gz = b.sep(gen)
    r = b.math("MULTIPLY", b.length(b.comb(b.math("SUBTRACT", gx, 0.5), b.math("SUBTRACT", gy, 0.5), 0.0)), 2.0)
    side = b.math("SUBTRACT", 1.0, b.smoothstep(r, 0.55, 1.0))
    top = b.math("SUBTRACT", 1.0, b.smoothstep(gz, 0.7, 1.0))
    nt.links.new(b.math("MULTIPLY", side, top), group_node.inputs["Edge Fade"])


def update_cloud_layers(scene, s, quality: str) -> None:
    coll = ensure_collection(scene)
    wanted = {CLOUD_PREFIX + str(i + 1) for i in range(len(s.clouds))}
    for o in list(bpy.data.objects):
        if o.get(ROLE_KEY) == "cloud" and o.name not in wanted:
            bpy.data.objects.remove(o, do_unlink=True)
    group = volumes.ensure_cloud_group(scene)
    for i, layer in enumerate(s.clouds):
        name = CLOUD_PREFIX + str(i + 1)
        obj = _ensure_domain(scene, name, "cloud")
        obj.scale = (layer.radius_m, layer.radius_m, layer.thickness_m)
        obj.location.z = layer.altitude_m
        obj.hide_render = not layer.enabled
        obj.hide_viewport = not layer.enabled
        _follow_camera(scene, obj, layer.follow_camera)
        mat = _volume_material(name, group)
        if not obj.data.materials:
            obj.data.materials.append(mat)
        else:
            obj.material_slots[0].material = mat
        # one mesh is shared, so assign the material on the object, not the mesh
        if obj.material_slots and obj.material_slots[0].link != "OBJECT":
            obj.material_slots[0].link = "OBJECT"
        obj.material_slots[0].material = mat
        node = mat.node_tree.nodes["AtmosFX Group"]
        node.node_tree = group
        for k, v in cloudlib.socket_values(layer, quality).items():
            sock = node.inputs.get(k)
            if sock is not None:
                try:
                    sock.default_value = v
                except TypeError:
                    sock.default_value = tuple(v)


def _fill_fog_object(scene, obj, name: str, s, visibility_m: float, ambient=(0.0, 0.0, 0.0)) -> None:
    mat = _volume_material(name, volumes.ensure_fog_group(scene), _fog_edge_fade)
    if not obj.data.materials:
        obj.data.materials.append(mat)
    obj.material_slots[0].link = "OBJECT"
    obj.material_slots[0].material = mat
    node = mat.node_tree.nodes["AtmosFX Group"]
    node.node_tree = volumes.ensure_fog_group(scene)
    vals = {
        "Density": physics.koschmieder_extinction(max(visibility_m, 5.0)), "Scale Height": s.fog_scale_height,
        "Base Altitude": s.fog_base_altitude, "Anisotropy": s.fog_anisotropy, "Color": (*s.fog_color, 1.0),
        "Absorption": s.fog_absorption, "Noise Amount": s.fog_noise_amount,
        "Noise Frequency": 1.0 / max(s.fog_noise_scale, 1.0), "Wind Velocity": (1.0, 0.0, 0.0),
        "Ambient": (*ambient, 1.0),
    }
    for k, v in vals.items():
        sock = node.inputs.get(k)
        if sock is not None:
            try:
                sock.default_value = v
            except TypeError:
                sock.default_value = tuple(v)


def haze_dimensions(s) -> tuple[float, float, float]:
    """(radius, height, base z) of the camera-following haze dome that stands in for world fog.

    Radius is 1.4 x visibility, where the 2 % contrast distance has fallen to 0.3 %, so the dome edge is invisible.
    Height is five scale heights, where the exponential profile is below 1 %, plus a skirt under the base altitude.
    """
    radius = min(max(1.4 * s.fog_visibility, 300.0), 120000.0)
    height = min(5.0 * s.fog_scale_height, 30000.0) + 200.0
    return radius, height, s.fog_base_altitude - 200.0


def update_fog(scene, s, view) -> None:
    for name, role, on in ((HAZE_NAME, "haze", s.fog_enabled and s.fog_mode in ("WORLD", "BOTH")),
                           (FOG_NAME, "fog", s.fog_enabled and s.fog_mode in ("DOMAIN", "BOTH"))):
        obj = bpy.data.objects.get(name)
        if not on:
            if obj is not None and obj.get(ROLE_KEY) == role:
                bpy.data.objects.remove(obj, do_unlink=True)
            continue
        obj = _ensure_domain(scene, name, role)
        if role == "haze":
            r, h, z0 = haze_dimensions(s)
            obj.scale = (r, r, h)
            obj.location.z = z0
            _follow_camera(scene, obj, True)
            _fill_fog_object(scene, obj, name, s, s.fog_visibility, view.fog_ambient)
        else:
            obj.scale = (s.fog_domain_radius, s.fog_domain_radius, s.fog_domain_height)
            obj.location.z = s.fog_base_altitude
            _fill_fog_object(scene, obj, name, s, s.fog_domain_visibility, view.fog_ambient)


def remove_all() -> None:
    for o in owned_objects():
        bpy.data.objects.remove(o, do_unlink=True)
    for n in (LL_EXCLUDE, LL_CLOUDS):
        c = bpy.data.collections.get(n)
        if c is not None:
            bpy.data.collections.remove(c)
    c = bpy.data.collections.get(COLLECTION)
    if c is not None and not c.objects and not c.children:
        bpy.data.collections.remove(c)
