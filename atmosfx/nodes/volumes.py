"""Volume node groups: ``AtmosFX Cloud`` (volumetric cloud layer) and ``AtmosFX Fog`` (height fog).

Both groups read world-space position, so objects can be moved and scaled freely; the shader, not the mesh,
decides where the medium is. The domain mesh only bounds where the volume is evaluated.
"""
from __future__ import annotations

import bpy

from .dsl import Builder
from .sky import add_time_driver

CLOUD_GROUP = "AtmosFX Cloud"
FOG_GROUP = "AtmosFX Fog"
CLOUD_VERSION = 7
FOG_VERSION = 3

CLOUD_INPUTS = [
    ("Base Altitude", "NodeSocketFloat", 1500.0, (-1000.0, 50000.0)),
    ("Thickness", "NodeSocketFloat", 1400.0, (10.0, 20000.0)),
    ("Threshold", "NodeSocketFloat", 0.52, (-1.0, 2.0)),
    ("Softness", "NodeSocketFloat", 0.08, (0.005, 0.5)),
    ("Density", "NodeSocketFloat", 0.05, (0.0, 5.0)),
    ("Frequency", "NodeSocketFloat", 1.0 / 900.0, (1e-6, 1.0)),
    ("Detail", "NodeSocketFloat", 0.6, (0.0, 1.0)),
    ("Octaves", "NodeSocketFloat", 4.0, (0.0, 15.0)),
    ("Wind Velocity", "NodeSocketVector", (6.0, 0.0, 0.0), None),
    ("Seed Offset", "NodeSocketVector", (0.0, 0.0, 0.0), None),
    ("Bottom Ramp", "NodeSocketFloat", 0.06, (0.001, 1.0)),
    ("Top Ramp", "NodeSocketFloat", 0.45, (0.001, 1.0)),
    ("Anvil", "NodeSocketFloat", 0.0, (0.0, 1.0)),
    ("Vertical Stretch", "NodeSocketFloat", 1.0, (0.1, 20.0)),
    ("Radius", "NodeSocketFloat", 15000.0, (100.0, 200000.0)),
    ("Inner Radius", "NodeSocketFloat", 9750.0, (0.0, 200000.0)),
    ("Anisotropy", "NodeSocketFloat", 0.8, (0.0, 0.99)),
    ("Back Anisotropy", "NodeSocketFloat", -0.25, (-0.99, 0.0)),
    ("Back Weight", "NodeSocketFloat", 0.25, (0.0, 1.0)),
    ("Ambient", "NodeSocketColor", (0.0, 0.0, 0.0, 1.0), None),
    ("Top Color", "NodeSocketColor", (0.0, 0.0, 0.0, 1.0), None),
    ("Glow Color", "NodeSocketColor", (1.0, 1.0, 1.0, 1.0), None),
    ("Sun Direction", "NodeSocketVector", (0.0, 0.0, 1.0), None),
    ("Glow Strength", "NodeSocketFloat", 0.0, (0.0, 20.0)),
]

FOG_INPUTS = [
    ("Density", "NodeSocketFloat", 0.0002, (0.0, 10.0)),
    ("Scale Height", "NodeSocketFloat", 1500.0, (1.0, 100000.0)),
    ("Base Altitude", "NodeSocketFloat", 0.0, (-1000.0, 50000.0)),
    ("Anisotropy", "NodeSocketFloat", 0.4, (-0.9, 0.95)),
    ("Color", "NodeSocketColor", (1.0, 1.0, 1.0, 1.0), None),
    ("Absorption", "NodeSocketFloat", 0.0, (0.0, 1.0)),
    ("Noise Amount", "NodeSocketFloat", 0.0, (0.0, 1.0)),
    ("Noise Frequency", "NodeSocketFloat", 1.0 / 400.0, (1e-6, 1.0)),
    ("Wind Velocity", "NodeSocketVector", (1.0, 0.0, 0.0), None),
    ("Seed Offset", "NodeSocketVector", (0.0, 0.0, 0.0), None),
    ("Edge Fade", "NodeSocketFloat", 1.0, (0.0, 1.0)),
    ("Ambient", "NodeSocketColor", (0.0, 0.0, 0.0, 1.0), None),
]


def _new_tree(name: str, version: int):
    old = bpy.data.node_groups.get(name)
    if old is not None:
        old.name = name + ".old"
    tree = bpy.data.node_groups.new(name, "ShaderNodeTree")
    tree["atmosfx_version"] = version
    return tree, old


def _finish(old):
    if old is not None:
        bpy.data.node_groups.remove(old)


# ------------------------------------------------------------------------------- clouds
def build_cloud_group(scene: bpy.types.Scene) -> bpy.types.NodeTree:
    tree, old = _new_tree(CLOUD_GROUP, CLOUD_VERSION)
    b = Builder(tree)
    for name, stype, default, rng in CLOUD_INPUTS:
        Builder.add_input(tree, name, stype, default, *(rng or (None, None)))
    Builder.add_output(tree, "Volume", "NodeSocketShader")
    Builder.add_output(tree, "Density", "NodeSocketFloat")      # extinction in 1/m, for diagnostics and tests
    Builder.add_output(tree, "Field", "NodeSocketFloat")        # shape field before thresholding (diagnostics)
    Builder.add_output(tree, "Base Noise", "NodeSocketFloat")   # raw fractal noise (diagnostics)
    gin = b.node("NodeGroupInput", "Inputs")
    gout = b.node("NodeGroupOutput", "Outputs")
    gi = lambda n: gin.outputs[n]                               # noqa: E731

    b.col()
    pos = b.node("ShaderNodeNewGeometry").outputs["Position"]
    centre = b.node("ShaderNodeObjectInfo").outputs["Location"]
    time_s = b.node("ShaderNodeValue", "AtmosFX Time").outputs[0]
    px, py, pz = b.sep(pos)
    cx, cy, _cz = b.sep(centre)
    dist_xy = b.math("SQRT", b.math("ADD", b.math("POWER", b.math("SUBTRACT", px, cx), 2.0),
                                    b.math("POWER", b.math("SUBTRACT", py, cy), 2.0)))

    # height within the layer, 0 at the base and 1 at the top
    h = b.math("DIVIDE", b.math("SUBTRACT", pz, gi("Base Altitude")), b.math("MAXIMUM", gi("Thickness"), 1.0), clamp=True)
    up = b.smoothstep(h, 0.0, gi("Bottom Ramp"))
    down = b.math("SUBTRACT", 1.0, b.smoothstep(h, b.math("SUBTRACT", 1.0, gi("Top Ramp")), 1.0))
    profile = b.math("MULTIPLY", up, down)

    # noise space: metres * frequency, advected by wind velocity * time
    b.col()
    freq = gi("Frequency")
    stretch = gi("Vertical Stretch")
    scale_vec = b.comb(freq, freq, b.math("MULTIPLY", freq, stretch))
    wind = b.vmath("SCALE", gi("Wind Velocity"), scale=time_s)
    loc = b.vmath("SUBTRACT", gi("Seed Offset"), b.vmath("MULTIPLY", wind, scale_vec))
    q = b.mapping(pos, loc=loc, scale=scale_vec)
    base = b.noise(q, 1.0, gi("Octaves"), 0.55)
    q2 = b.mapping(q, scale=(6.3, 6.3, 6.3), loc=(17.0, 3.0, 11.0))
    erode = b.noise(q2, 1.0, b.math("MULTIPLY", gi("Octaves"), 0.6), 0.5)

    # shape: fractal field, cut by the height profile, widened near the top for anvils, eroded by detail
    anvil = b.math("MULTIPLY", gi("Anvil"), b.math("MULTIPLY", b.smoothstep(h, 0.6, 0.95), 0.22))
    field = b.math("SUBTRACT", b.math("ADD", base, anvil), b.math("MULTIPLY", b.math("SUBTRACT", 1.0, profile), 0.32))
    field = b.math("SUBTRACT", field, b.math("MULTIPLY", b.math("SUBTRACT", erode, 0.5), b.math("MULTIPLY", gi("Detail"), 0.55)))
    cloud = b.smoothstep(field, gi("Threshold"), b.math("ADD", gi("Threshold"), gi("Softness")))
    radial = b.math("SUBTRACT", 1.0, b.smoothstep(dist_xy, gi("Inner Radius"), gi("Radius")))
    density = b.math("MULTIPLY", b.math("MULTIPLY", cloud, gi("Density")), radial)

    b.col()
    fwd = b.node("ShaderNodeVolumeScatter", "Forward", phase="HENYEY_GREENSTEIN")
    back = b.node("ShaderNodeVolumeScatter", "Back", phase="HENYEY_GREENSTEIN")
    for n, g in ((fwd, gi("Anisotropy")), (back, gi("Back Anisotropy"))):
        b.set(n.inputs["Color"], (1.0, 1.0, 1.0, 1.0))
        b.set(n.inputs["Density"], density)
        b.set(n.inputs["Anisotropy"], g)
    mixer = b.node("ShaderNodeMixShader", "Lobes")
    b.set(mixer.inputs[0], gi("Back Weight"))
    tree.links.new(fwd.outputs[0], mixer.inputs[1])
    tree.links.new(back.outputs[0], mixer.inputs[2])

    # Multiple-scatter approximation: emission proportional to density. A path tracer with a few volume
    # bounces loses the light that real clouds keep bouncing; this restores it, dark-blue at the shadowed
    # base and bright at the sunlit top. See physics.cloud_scatter_lighting for the calibrated anchors.
    b.col()
    top_mix = b.smoothstep(h, 0.35, 0.9)
    ambient_color = b.mix_rgb(top_mix, gi("Ambient"), gi("Top Color"))
    ambient = b.node("ShaderNodeEmission", "Ambient In-scatter")
    b.set(ambient.inputs["Color"], ambient_color)
    b.set(ambient.inputs["Strength"], density)

    # Forward-scatter halo: strongest when the view points into the sun, which is what makes backlit
    # edges glow at sunset. The lobe is a power of the view/sun cosine, separate from the HG phase above.
    incoming = b.node("ShaderNodeNewGeometry").outputs["Incoming"]
    facing = b.math("MAXIMUM", b.math("MULTIPLY", b.dot(incoming, gi("Sun Direction")), -1.0), 0.0)
    phase = b.math("POWER", facing, 8.0)
    glow_strength = b.math("MULTIPLY", b.math("MULTIPLY", density, gi("Glow Strength")), phase)
    glow = b.node("ShaderNodeEmission", "Forward Glow")
    b.set(glow.inputs["Color"], gi("Glow Color"))
    b.set(glow.inputs["Strength"], glow_strength)

    add_ambient = b.node("ShaderNodeAddShader")
    tree.links.new(mixer.outputs[0], add_ambient.inputs[0])
    tree.links.new(ambient.outputs[0], add_ambient.inputs[1])
    add_glow = b.node("ShaderNodeAddShader")
    tree.links.new(add_ambient.outputs[0], add_glow.inputs[0])
    tree.links.new(glow.outputs[0], add_glow.inputs[1])
    tree.links.new(add_glow.outputs[0], gout.inputs["Volume"])
    tree.links.new(density, gout.inputs["Density"])
    tree.links.new(field, gout.inputs["Field"])
    tree.links.new(base, gout.inputs["Base Noise"])

    add_time_driver(tree, "AtmosFX Time", scene)
    _finish(old)
    return tree


# --------------------------------------------------------------------------------- fog
def build_fog_group(scene: bpy.types.Scene) -> bpy.types.NodeTree:
    tree, old = _new_tree(FOG_GROUP, FOG_VERSION)
    b = Builder(tree)
    for name, stype, default, rng in FOG_INPUTS:
        Builder.add_input(tree, name, stype, default, *(rng or (None, None)))
    Builder.add_output(tree, "Volume", "NodeSocketShader")
    gin = b.node("NodeGroupInput", "Inputs")
    gout = b.node("NodeGroupOutput", "Outputs")
    gi = lambda n: gin.outputs[n]                               # noqa: E731

    b.col()
    pos = b.node("ShaderNodeNewGeometry").outputs["Position"]
    time_s = b.node("ShaderNodeValue", "AtmosFX Time").outputs[0]
    _x, _y, z = b.sep(pos)
    above = b.math("MAXIMUM", b.math("SUBTRACT", z, gi("Base Altitude")), 0.0)
    falloff = b.math("EXPONENT", b.math("MULTIPLY", b.math("DIVIDE", above, gi("Scale Height")), -1.0))

    b.col()
    f = gi("Noise Frequency")
    wind = b.vmath("SCALE", gi("Wind Velocity"), scale=time_s)
    q = b.mapping(pos, loc=b.vmath("SUBTRACT", gi("Seed Offset"), b.vmath("SCALE", wind, scale=f)), scale=b.comb(f, f, b.math("MULTIPLY", f, 1.6)))
    n = b.noise(q, 1.0, 4.0, 0.55)
    wobble = b.math("MAXIMUM", b.math("ADD", 1.0, b.math("MULTIPLY", b.math("SUBTRACT", n, 0.5), b.math("MULTIPLY", gi("Noise Amount"), 4.0))), 0.0)
    density = b.math("MULTIPLY", b.math("MULTIPLY", b.math("MULTIPLY", gi("Density"), falloff), wobble), gi("Edge Fade"))

    b.col()
    sc = b.node("ShaderNodeVolumeScatter", "Scatter", phase="HENYEY_GREENSTEIN")
    b.set(sc.inputs["Color"], gi("Color"))
    b.set(sc.inputs["Density"], density)
    b.set(sc.inputs["Anisotropy"], gi("Anisotropy"))
    ab = b.node("ShaderNodeVolumeAbsorption", "Absorb")
    b.set(ab.inputs["Color"], gi("Color"))
    b.set(ab.inputs["Density"], b.math("MULTIPLY", density, gi("Absorption")))
    em = b.node("ShaderNodeEmission", "Ambient in-scatter")
    b.set(em.inputs["Color"], gi("Ambient"))
    b.set(em.inputs["Strength"], density)
    add = b.node("ShaderNodeAddShader")
    tree.links.new(sc.outputs[0], add.inputs[0])
    tree.links.new(ab.outputs[0], add.inputs[1])
    add2 = b.node("ShaderNodeAddShader")
    tree.links.new(add.outputs[0], add2.inputs[0])
    tree.links.new(em.outputs[0], add2.inputs[1])
    tree.links.new(add2.outputs[0], gout.inputs["Volume"])

    add_time_driver(tree, "AtmosFX Time", scene)
    _finish(old)
    return tree


def ensure_cloud_group(scene) -> bpy.types.NodeTree:
    t = bpy.data.node_groups.get(CLOUD_GROUP)
    return t if t is not None and t.get("atmosfx_version") == CLOUD_VERSION else build_cloud_group(scene)


def ensure_fog_group(scene) -> bpy.types.NodeTree:
    t = bpy.data.node_groups.get(FOG_GROUP)
    return t if t is not None and t.get("atmosfx_version") == FOG_VERSION else build_fog_group(scene)

