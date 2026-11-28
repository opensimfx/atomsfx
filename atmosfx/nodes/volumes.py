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
CLOUD_VERSION = 14  # 14: evolution (noise scrolls up through the layer), lightning inside the cloud
FOG_VERSION = 5

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
    ("Fibre", "NodeSocketFloat", 1.0, (1.0, 20.0)),                # stretch along the wind (cirrus streaks)
    ("Radius", "NodeSocketFloat", 15000.0, (100.0, 200000.0)),
    ("Inner Radius", "NodeSocketFloat", 9750.0, (0.0, 200000.0)),
    ("Anisotropy", "NodeSocketFloat", 0.75, (0.0, 0.99)),         # ice clouds (HG)
    ("Droplet Diameter", "NodeSocketFloat", 20.0, (5.0, 50.0)),   # liquid clouds (Mie), micrometres
    ("Ice", "NodeSocketFloat", 0.0, (0.0, 1.0)),                  # 0 liquid (Mie), 1 ice (HG)
    ("Billow", "NodeSocketFloat", 0.5, (0.0, 1.0)),               # Worley share of the 3D shape
    ("Roundness", "NodeSocketFloat", 1.0, (0.0, 4.0)),            # threshold rise with height (domes)
    ("Weather", "NodeSocketFloat", 0.6, (0.0, 2.0)),              # strength of the 2D cover pattern
    ("Fill", "NodeSocketFloat", 1.0, (0.0, 4.0)),                 # multiple-scatter fill gain
    ("Cell Center", "NodeSocketVector", (0.0, 15000.0, 0.0), None),  # storm cell, world XY at time 0
    ("Cell Radius", "NodeSocketFloat", 7000.0, (1.0, 1e6)),
    ("Cell Strength", "NodeSocketFloat", 0.0, (0.0, 5.0)),         # field lift at the cell core
    ("Diffuse Share", "NodeSocketFloat", 0.6, (0.0, 1.0)),        # share of scattering through the soft HG lobe
    ("Diffuse Anisotropy", "NodeSocketFloat", 0.4, (-0.5, 0.95)), # g of that lobe
    ("Ambient", "NodeSocketColor", (0.0, 0.0, 0.0, 1.0), None),
    ("Top Color", "NodeSocketColor", (0.0, 0.0, 0.0, 1.0), None),
    ("Glow Color", "NodeSocketColor", (1.0, 1.0, 1.0, 1.0), None),
    ("Sun Direction", "NodeSocketVector", (0.0, 0.0, 1.0), None),
    ("Glow Strength", "NodeSocketFloat", 0.0, (0.0, 20.0)),
    ("Evolution", "NodeSocketFloat", 0.0, (0.0, 1.0)),            # shape change in place, noise units per second
    ("Lightning Strength", "NodeSocketFloat", 0.0, (0.0, 1e9)),   # keyed per flash (0 between flashes)
    ("Lightning Position", "NodeSocketVector", (0.0, 0.0, 2000.0), None),
    ("Lightning Radius", "NodeSocketFloat", 1500.0, (1.0, 1e5)),
    ("Lightning Color", "NodeSocketColor", (0.75, 0.82, 1.0, 1.0), None),
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
    ("Fill", "NodeSocketFloat", 1.0, (0.0, 4.0)),                 # multiple-scatter fill gain (quality tier)
    ("Air Density", "NodeSocketFloat", 0.0, (0.0, 1.0)),          # sea-level Rayleigh extinction, blue, 1/m
    ("Air Color", "NodeSocketColor", (0.26, 0.48, 1.0, 1.0), None),  # Rayleigh extinction ratios R:G:B
    ("Air Scale Height", "NodeSocketFloat", 8000.0, (100.0, 100000.0)),
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
    """Cloud density and lighting.

    Shape (after Schneider 2015, adapted to shader nodes): a 2D *weather* field decides where cloud can form,
    so cover comes in groups and gaps instead of a uniform spotty sheet; the 3D field is fractal Perlin noise
    blended with inverted fractal Worley noise ("Billow"), which thresholds into rounded cauliflower lumps;
    the height profile gives a sharp flat base at the condensation level and *raises the threshold with
    height* ("Roundness"), so each lump narrows upward into a dome; an anvil term spreads the top of a
    cumulonimbus; high-frequency erosion makes the base wispy and the top billowy.

    Light: liquid clouds use the Mie phase of their droplets (Blender 4.3+, Jendersie and d'Eon 2023 fit),
    whose sharp forward peak gives silver linings; ice clouds use Henyey-Greenstein. Real volume bounces carry
    the multiple scattering; the emission fill only restores what the bounce cap of a quality tier cuts off.
    """
    tree, old = _new_tree(CLOUD_GROUP, CLOUD_VERSION)
    b = Builder(tree)
    for name, stype, default, rng in CLOUD_INPUTS:
        Builder.add_input(tree, name, stype, default, *(rng or (None, None)))
    Builder.add_output(tree, "Volume", "NodeSocketShader")
    Builder.add_output(tree, "Density", "NodeSocketFloat")      # extinction in 1/m, for diagnostics and tests
    Builder.add_output(tree, "Field", "NodeSocketFloat")        # shape field before thresholding (diagnostics)
    Builder.add_output(tree, "Base Noise", "NodeSocketFloat")   # 3D shape noise before height shaping
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
    # the noise frame is turned to the wind (x' downwind, y' across), so "Fibre" can draw cloud out along it
    # (cirrus streaks, rows of altocumulus); the advection is then a shift along x' only
    freq = gi("Frequency")
    stretch = gi("Vertical Stretch")
    wv = gi("Wind Velocity")
    wx, wy, _wz = b.sep(wv)
    speed = b.length(b.comb(wx, wy, 0.0))
    inv = b.math("DIVIDE", 1.0, b.math("MAXIMUM", speed, 1e-4))
    ux = b.math("ADD", b.math("MULTIPLY", wx, inv), b.math("LESS_THAN", speed, 1e-4))     # (1, 0) when calm
    uy = b.math("MULTIPLY", wy, inv)
    rx = b.math("ADD", b.math("MULTIPLY", px, ux), b.math("MULTIPLY", py, uy))
    ry = b.math("SUBTRACT", b.math("MULTIPLY", py, ux), b.math("MULTIPLY", px, uy))
    scale_vec = b.comb(b.math("DIVIDE", freq, gi("Fibre")), freq, b.math("MULTIPLY", freq, stretch))
    wind = b.vmath("SCALE", wv, scale=time_s)
    drift = b.comb(b.math("MULTIPLY", speed, time_s), 0.0, 0.0)
    loc = b.vmath("SUBTRACT", gi("Seed Offset"), b.vmath("MULTIPLY", drift, scale_vec))
    # Evolution: the noise space also scrolls slowly upward, so features rise through the height profile, swell
    # and dissolve in place the way convective cloud does, on top of drifting with the wind. Free: a 4D noise
    # (time as the 4th axis) cost 16 % more render time (measured, cumulus_day 640 px).
    loc = b.vmath("ADD", loc, b.comb(0.0, 0.0, b.math("MULTIPLY", time_s, gi("Evolution"))))
    q = b.mapping(b.comb(rx, ry, pz), loc=loc, scale=scale_vec)
    qx, qy, _qz = b.sep(q)

    # weather: where cloud can form (2D, cells ~3x the cloud size)
    weather = b.noise(b.comb(b.math("MULTIPLY", qx, 0.31), b.math("MULTIPLY", qy, 0.31), 7.3), 1.0, 3.0, 0.5)
    w_shift = b.math("MULTIPLY", b.math("SUBTRACT", weather, 0.5), gi("Weather"))

    # 3D shape: fractal Perlin blended with inverted fractal Worley
    perlin = b.noise(q, 1.0, gi("Octaves"), 0.55)
    worley = b.billow(q, 1.7, 2.0, 0.45)
    base = b.mix(gi("Billow"), perlin, b.math("ADD", b.math("MULTIPLY", worley, 0.55), 0.12))

    b.col()
    anvil = b.math("MULTIPLY", gi("Anvil"), b.math("MULTIPLY", b.smoothstep(h, 0.6, 0.95), 0.22))
    dome = b.math("MULTIPLY", gi("Roundness"), b.math("MULTIPLY", h, h))
    # storm cell: a disc of extra cover anchored in world space and drifting with the wind
    ccx, ccy, _ccz = b.sep(b.vmath("ADD", gi("Cell Center"), wind))
    d_cell = b.math("SQRT", b.math("ADD", b.math("POWER", b.math("SUBTRACT", px, ccx), 2.0),
                                   b.math("POWER", b.math("SUBTRACT", py, ccy), 2.0)))
    cell = b.math("SUBTRACT", 1.0, b.smoothstep(d_cell, b.math("MULTIPLY", gi("Cell Radius"), 0.3), gi("Cell Radius")))
    w_shift = b.math("ADD", w_shift, b.math("MULTIPLY", cell, gi("Cell Strength")))
    field = b.math("ADD", b.math("ADD", base, anvil), w_shift)
    field = b.math("SUBTRACT", field, b.math("MULTIPLY", b.math("SUBTRACT", 1.0, profile), 0.32))
    field = b.math("SUBTRACT", field, b.math("MULTIPLY", dome, 0.18))
    # erosion: Worley billows toward the top, inverted (wispy) toward the base
    q_hf = b.mapping(q, scale=(5.3, 5.3, 5.3), loc=(17.0, 3.0, 11.0))
    hf = b.billow(q_hf, 1.0, b.math("MULTIPLY", gi("Octaves"), 0.25), 0.5)
    hf_n = b.mix(b.smoothstep(h, 0.05, 0.35), b.math("SUBTRACT", 1.0, hf), hf)
    field = b.math("SUBTRACT", field, b.math("MULTIPLY", b.math("SUBTRACT", 0.6, hf_n), b.math("MULTIPLY", gi("Detail"), 0.14)))
    cloud = b.smoothstep(field, gi("Threshold"), b.math("ADD", gi("Threshold"), gi("Softness")))
    radial = b.math("SUBTRACT", 1.0, b.smoothstep(dist_xy, gi("Inner Radius"), gi("Radius")))
    density = b.math("MULTIPLY", b.math("MULTIPLY", cloud, gi("Density")), radial)

    b.col()
    # Phase: a blend of the droplets' physical Mie phase and a weak-forward Henyey-Greenstein lobe. Pure Mie (forward
    # peak g ~ 0.86 overall, half of it ~0.995) needs hundreds of bounces before light diffuses back out of a thick
    # cloud: cumulus stayed grey on its sunlit side even at 128 bounces. Production renderers handle that with
    # multiple-scattering octaves (Wrenninge 2010; Frostbite, UE) that soften the phase for later orders; a ray-depth
    # switch needs a Light Path node, which makes Metal render this shader >20x slower (Blender 5.2.3), so the
    # softening applies to every order through a fixed share ("Diffuse Share"). The Mie share keeps the forward
    # peak that makes silver linings and glowing backlit edges.
    liquid = b.node("ShaderNodeVolumeScatter", "Droplets", phase="MIE")
    b.set(liquid.inputs["Color"], (1.0, 1.0, 1.0, 1.0))
    b.set(liquid.inputs["Density"], density)
    b.set(liquid.inputs["Diameter"], gi("Droplet Diameter"))
    soft = b.node("ShaderNodeVolumeScatter", "Diffuse Lobe", phase="HENYEY_GREENSTEIN")
    b.set(soft.inputs["Color"], (1.0, 1.0, 1.0, 1.0))
    b.set(soft.inputs["Density"], density)
    b.set(soft.inputs["Anisotropy"], gi("Diffuse Anisotropy"))
    water = b.node("ShaderNodeMixShader", "Water Phase")
    b.set(water.inputs[0], gi("Diffuse Share"))
    tree.links.new(liquid.outputs[0], water.inputs[1])
    tree.links.new(soft.outputs[0], water.inputs[2])
    ice = b.node("ShaderNodeVolumeScatter", "Ice", phase="HENYEY_GREENSTEIN")
    b.set(ice.inputs["Color"], (1.0, 1.0, 1.0, 1.0))
    b.set(ice.inputs["Density"], density)
    b.set(ice.inputs["Anisotropy"], gi("Anisotropy"))
    mixer = b.node("ShaderNodeMixShader", "Phase")
    b.set(mixer.inputs[0], gi("Ice"))
    tree.links.new(water.outputs[0], mixer.inputs[1])
    tree.links.new(ice.outputs[0], mixer.inputs[2])

    # Multiple-scatter fill for the Draft tier only (4 volume bounces): emission proportional to density, dark blue
    # at the shadowed base and warm at the top at low sun (physics.cloud_scatter_lighting). Preview and Final set
    # Fill to 0 and let real bounces do it: a non-absorbing, forward-scattering cloud lets every emitted photon
    # escape, so emission adds energy in proportion to optical depth (a tau-7 deck lit the ground orange). Gating it
    # to camera rays with a Light Path node made Metal render the cloud shader >20x slower (Blender 5.2.3).
    b.col()
    top_mix = b.smoothstep(h, 0.35, 0.9)
    ambient_color = b.mix_rgb(top_mix, gi("Ambient"), gi("Top Color"))
    ambient = b.node("ShaderNodeEmission", "Ambient In-scatter")
    b.set(ambient.inputs["Color"], ambient_color)
    b.set(ambient.inputs["Strength"], b.math("MULTIPLY", density, gi("Fill")))

    # Forward-scatter halo at low sun: the warm glow of backlit edges, which the bounce cap also starves.
    incoming = b.node("ShaderNodeNewGeometry").outputs["Incoming"]
    facing = b.math("MAXIMUM", b.math("MULTIPLY", b.dot(incoming, gi("Sun Direction")), -1.0), 0.0)
    phase = b.math("POWER", facing, 8.0)
    glow_strength = b.math("MULTIPLY", b.math("MULTIPLY", b.math("MULTIPLY", density, gi("Glow Strength")), phase), gi("Fill"))
    glow = b.node("ShaderNodeEmission", "Forward Glow")
    b.set(glow.inputs["Color"], gi("Glow Color"))
    b.set(glow.inputs["Strength"], glow_strength)

    add_ambient = b.node("ShaderNodeAddShader")
    tree.links.new(mixer.outputs[0], add_ambient.inputs[0])
    tree.links.new(ambient.outputs[0], add_ambient.inputs[1])
    add_glow = b.node("ShaderNodeAddShader")
    tree.links.new(add_ambient.outputs[0], add_glow.inputs[0])
    tree.links.new(glow.outputs[0], add_glow.inputs[1])

    # Lightning inside the cloud: the channel's light, scattered by the droplets around it, so the cloud lights up
    # from within where it is dense near the flash (Gaussian falloff of Lightning Radius). Real bounces then carry
    # it through the rest of the cloud and onto the ground. Strength is keyed per stroke by the scene layer.
    b.col()
    rel = b.vmath("SUBTRACT", pos, gi("Lightning Position"))
    r2 = b.math("DIVIDE", b.dot(rel, rel), b.math("MAXIMUM", b.math("POWER", gi("Lightning Radius"), 2.0), 1.0))
    bolt_k = b.math("MULTIPLY", b.math("MULTIPLY", gi("Lightning Strength"), density),
                    b.math("EXPONENT", b.math("MULTIPLY", r2, -1.0)))
    bolt = b.node("ShaderNodeEmission", "Lightning")
    b.set(bolt.inputs["Color"], gi("Lightning Color"))
    b.set(bolt.inputs["Strength"], bolt_k)
    add_bolt = b.node("ShaderNodeAddShader")
    tree.links.new(add_glow.outputs[0], add_bolt.inputs[0])
    tree.links.new(bolt.outputs[0], add_bolt.inputs[1])
    tree.links.new(add_bolt.outputs[0], gout.inputs["Volume"])
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

    # clean air: molecular (Rayleigh) scattering with its own 8 km scale height, blue-weighted per channel
    air = b.math("MULTIPLY", b.math("MULTIPLY", gi("Air Density"), gi("Edge Fade")),
                 b.math("EXPONENT", b.math("MULTIPLY", b.math("DIVIDE", b.math("MAXIMUM", z, 0.0), gi("Air Scale Height")), -1.0)))
    air_sc = b.node("ShaderNodeVolumeScatter", "Air", phase="RAYLEIGH")
    b.set(air_sc.inputs["Color"], gi("Air Color"))
    b.set(air_sc.inputs["Density"], air)

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
    seen = b.node("ShaderNodeLightPath").outputs["Is Camera Ray"]          # a display term (see the cloud fill)
    b.set(em.inputs["Strength"], b.math("MULTIPLY", b.math("MULTIPLY", density, gi("Fill")), seen))
    add = b.node("ShaderNodeAddShader")
    tree.links.new(sc.outputs[0], add.inputs[0])
    tree.links.new(ab.outputs[0], add.inputs[1])
    add2 = b.node("ShaderNodeAddShader")
    tree.links.new(add.outputs[0], add2.inputs[0])
    tree.links.new(em.outputs[0], add2.inputs[1])
    add3 = b.node("ShaderNodeAddShader")
    tree.links.new(add2.outputs[0], add3.inputs[0])
    tree.links.new(air_sc.outputs[0], add3.inputs[1])
    tree.links.new(add3.outputs[0], gout.inputs["Volume"])

    add_time_driver(tree, "AtmosFX Time", scene)
    _finish(old)
    return tree


def ensure_cloud_group(scene) -> bpy.types.NodeTree:
    t = bpy.data.node_groups.get(CLOUD_GROUP)
    return t if t is not None and t.get("atmosfx_version") == CLOUD_VERSION else build_cloud_group(scene)


def ensure_fog_group(scene) -> bpy.types.NodeTree:
    t = bpy.data.node_groups.get(FOG_GROUP)
    return t if t is not None and t.get("atmosfx_version") == FOG_VERSION else build_fog_group(scene)

