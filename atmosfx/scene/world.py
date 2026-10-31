"""The AtmosFX world: the sky group and the baked star image.

Fog is NOT a world volume: Cycles treats an infinite world volume as an infinitely long medium and blanks every
ray that reaches the sky. Haze and fog are bounded volume objects (see ``objects.py``).
"""
from __future__ import annotations

import math

import bpy

from ..core import clouds as cloudlib
from ..core import physics, starmap
from ..nodes import sky as skynodes

WORLD_NAME = "AtmosFX World"
STAR_PREFIX = "AtmosFX Stars "
SKY_NODE = "AtmosFX Sky"


def is_ours(world) -> bool:
    return world is not None and world.name.startswith(WORLD_NAME)


def ensure_world(scene: bpy.types.Scene) -> bpy.types.World:
    w = bpy.data.worlds.get(WORLD_NAME)
    if w is None:
        w = bpy.data.worlds.new(WORLD_NAME)
    nt = w.node_tree
    if nt is None:                                       # older Blender: nodes are opt-in
        w.use_nodes = True
        nt = w.node_tree
    out = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputWorld"), None) or nt.nodes.new("ShaderNodeOutputWorld")
    out.target = "ALL"
    for n in list(nt.nodes):
        if n.bl_idname == "ShaderNodeBackground":
            nt.nodes.remove(n)
    out.location = (400, 0)
    sky_node = nt.nodes.get(SKY_NODE) or nt.nodes.new("ShaderNodeGroup")
    sky_node.name = sky_node.label = SKY_NODE
    sky_node.location = (0, 120)
    for stale in [n for n in nt.nodes if n.name == "AtmosFX Fog"]:          # worlds from earlier builds
        nt.nodes.remove(stale)
    sky_node.node_tree = skynodes.ensure_group(scene)
    if not any(l.from_node == sky_node and l.to_node == out and l.to_socket.name == "Surface" for l in nt.links):
        nt.links.new(sky_node.outputs["Background"], out.inputs["Surface"])
    _tune_world_sampling(w)
    scene.world = w
    return w


def _set(node, name: str, value) -> None:
    sock = node.inputs.get(name)
    if sock is None:
        return
    try:
        sock.default_value = value
    except TypeError:
        sock.default_value = tuple(value)


# --------------------------------------------------------------------------- star image
def star_image(s, force: bool = False):
    """Return the baked star image for the current seed/density/resolution, creating it if needed."""
    import numpy as np

    w = int(s.star_resolution)
    h = w // 2
    key = starmap.bake_key(w, h, s.star_seed, starmap.REF_MAG, s.star_density)
    name = STAR_PREFIX + key
    img = bpy.data.images.get(name)
    if img is not None and not force and img.size[0] == w:
        return img
    if img is not None:
        bpy.data.images.remove(img)
    arr = starmap.bake_star_map(w, h, s.star_seed, starmap.REF_MAG, s.star_density)
    rgba = np.empty((h, w, 4), dtype=np.float32)
    rgba[..., :3] = arr
    rgba[..., 3] = 1.0
    img = bpy.data.images.new(name, w, h, alpha=False, float_buffer=True)
    # colour space and precision must be set BEFORE the pixels: changing either regenerates a generated image
    try:
        img.colorspace_settings.name = "Non-Color"
    except TypeError:
        pass
    try:
        img.use_half_precision = True
    except AttributeError:
        pass
    img.pixels.foreach_set(rgba.ravel())
    img.pack()                                  # keeps the float data inside the .blend
    return img


def purge_stale_star_images(keep) -> None:
    """Remove star maps from earlier seeds/densities once nothing references them."""
    for other in list(bpy.data.images):
        if other.name.startswith(STAR_PREFIX) and other is not keep and other.users == 0:
            bpy.data.images.remove(other)


# ------------------------------------------------------------------------------- update
def update(scene: bpy.types.Scene, s, view, quality: str) -> None:
    """Push a ``SkyView`` and the settings into the world's node groups."""
    w = ensure_world(scene)
    nt = w.node_tree
    sky_node = nt.nodes[SKY_NODE]
    group = sky_node.node_tree

    # Nishita sky node properties live on the node, not on sockets
    sky = group.nodes["Sky"]
    sv = view.sun_vec
    sky.sky_type = "SINGLE_SCATTERING" if quality == "DRAFT" else "MULTIPLE_SCATTERING"
    sky.sun_disc = False
    sky.sun_elevation = math.asin(max(-1.0, min(1.0, sv[2])))
    sky.sun_rotation = math.atan2(sv[0], sv[1]) % (2.0 * math.pi)
    sky.altitude = s.sky_altitude
    sky.air_density = s.air_density
    sky.aerosol_density = s.aerosol_density
    sky.ozone_density = s.ozone_density

    env = group.nodes["Star Map"]
    img = star_image(s)
    if env.image != img:
        env.image = img
    purge_stale_star_images(img)

    vals = {
        "Sun Direction": sv, "Sun Color": (*view.sun_color, 1.0), "Sun Disc Radiance": view.sun_disc_radiance,
        "Sun Angular Radius": view.sun_radius_rad, "Disc Camera Only": 1.0 if s.use_sun_lamp else 0.0,
        "Moon Direction": view.moon_vec, "Moon Light Direction": view.moon_light_vec,
        "Moon Color": (*view.moon_color, 1.0),
        "Moon Radiance": view.moon_disc_radiance, "Moon Angular Radius": view.moon_radius_rad,
        "Celestial Rotation": view.celestial_euler, "Galactic Rotation": view.galactic_euler,
        "Star Brightness": view.star_brightness, "Star Threshold": view.star_threshold,
        "Milky Way Strength": view.milky_way_strength,
        "Sky Strength": view.sky_strength, "Night Glow": view.night_glow,
        "Ground Color": (*s.ground_color, 1.0), "Ground Strength": view.ground_strength,
        "Ground Enabled": 1.0 if s.ground_enabled else 0.0, "Ground Blend": s.ground_blend,
        "Deck Color": (*view.deck_color, 1.0), "Deck Sun Light": (*view.deck_sun_light, 1.0),
        "Moon Glow": view.moon_glow,
    }
    if s.deck_enabled:
        thr = cloudlib.coverage_threshold(s.deck_coverage)
        wind = cloudlib.wind_vector(s.deck_wind_speed, s.deck_wind_dir)
        vals.update({
            "Deck Opacity": s.deck_opacity, "Deck Threshold": thr, "Deck Softness": s.deck_softness,
            "Deck Altitude": s.deck_altitude, "Deck Frequency": 1.0 / max(s.deck_scale, 1.0),
            "Deck Fibre": s.deck_fibre, "Deck Wind Velocity": wind,
            "Deck Seed Offset": cloudlib.seed_offset(s.deck_seed, 400.0),
        })
    else:
        vals["Deck Opacity"] = 0.0
    for k, v in vals.items():
        _set(sky_node, k, v)



def _tune_world_sampling(w) -> None:
    """The sky is smooth and the discs are camera-only, so a small importance map is plenty; the default
    1024 map costs seconds of shader evaluation at every render start on a graph this size."""
    cy = getattr(w, "cycles", None)
    if cy is None:
        return
    try:
        cy.sampling_method = "MANUAL"
        cy.sample_map_resolution = 256
    except (AttributeError, TypeError):
        pass
