"""The ``AtmosFX Sky`` world node group.

Everything in the world shader lives in one group whose inputs the scene layer drives. Layers, in the order
they are composited:

1. Blender's Nishita **Sky Texture** (multiple scattering) for scattering colour.
2. **Night glow** (airglow), a faint blue-green floor.
3. **Stars**: an equirectangular float image baked in the J2000 frame, rotated into the scene by a Mapping node
   whose Euler comes from the ephemeris, thresholded by luminance to implement a limiting magnitude.
4. **Milky Way**: procedural noise masked by galactic latitude/longitude (a second ephemeris Euler).
5. **Moon disc**: lit by a Lambert model on a sphere using the true Sun direction, so phase and the bright
   limb come out right; procedural maria.
6. **Sun disc**: physically scaled radiance (strength / solid angle) with limb darkening. By default visible to
   camera rays only because a Sun lamp does the lighting.
7. **2D cloud deck** projected on a plane at altitude (cheap cirrus / altostratus, no shadows).
8. **Ground** below the horizon.
"""
from __future__ import annotations

import bpy

from .dsl import Builder

GROUP_NAME = "AtmosFX Sky"
GROUP_VERSION = 4

# name, socket type, default, (min, max)
INPUTS = [
    ("Sun Direction", "NodeSocketVector", (0.0, 1.0, 0.5), None),
    ("Sun Color", "NodeSocketColor", (1.0, 0.95, 0.85, 1.0), None),
    ("Sun Disc Radiance", "NodeSocketFloat", 40000.0, (0.0, 1e9)),
    ("Sun Angular Radius", "NodeSocketFloat", 0.00466, (1e-4, 1.0)),
    ("Disc Camera Only", "NodeSocketFloat", 1.0, (0.0, 1.0)),
    ("Moon Direction", "NodeSocketVector", (0.0, -1.0, -0.5), None),
    ("Moon Light Direction", "NodeSocketVector", (0.0, 1.0, 0.5), None),
    ("Moon Color", "NodeSocketColor", (1.0, 0.93, 0.8, 1.0), None),
    ("Moon Radiance", "NodeSocketFloat", 0.0, (0.0, 1e9)),
    ("Moon Angular Radius", "NodeSocketFloat", 0.0046, (1e-4, 1.0)),
    ("Celestial Rotation", "NodeSocketVector", (0.0, 0.0, 0.0), None),
    ("Galactic Rotation", "NodeSocketVector", (0.0, 0.0, 0.0), None),
    ("Star Brightness", "NodeSocketFloat", 0.0, (0.0, 1e6)),
    ("Star Threshold", "NodeSocketFloat", 1.0, (0.0, 1e6)),
    ("Milky Way Strength", "NodeSocketFloat", 0.0, (0.0, 1e6)),
    ("Sky Strength", "NodeSocketFloat", 1.0, (0.0, 100.0)),
    ("Night Glow", "NodeSocketFloat", 0.0, (0.0, 10.0)),
    ("Night Glow Color", "NodeSocketColor", (0.30, 0.45, 0.90, 1.0), None),
    ("Ground Color", "NodeSocketColor", (0.18, 0.17, 0.16, 1.0), None),
    ("Ground Strength", "NodeSocketFloat", 0.5, (0.0, 100.0)),
    ("Ground Enabled", "NodeSocketFloat", 1.0, (0.0, 1.0)),
    ("Ground Blend", "NodeSocketFloat", 0.02, (0.0, 0.5)),
    ("Deck Opacity", "NodeSocketFloat", 0.0, (0.0, 1.0)),
    ("Deck Threshold", "NodeSocketFloat", 0.6, (0.0, 1.0)),
    ("Deck Softness", "NodeSocketFloat", 0.25, (0.01, 1.0)),
    ("Deck Altitude", "NodeSocketFloat", 8000.0, (100.0, 50000.0)),
    ("Deck Frequency", "NodeSocketFloat", 1.0 / 6000.0, (1e-7, 1.0)),
    ("Deck Fibre", "NodeSocketFloat", 1.0, (1.0, 20.0)),
    ("Deck Wind Velocity", "NodeSocketVector", (15.0, 0.0, 0.0), None),
    ("Deck Seed Offset", "NodeSocketVector", (0.0, 0.0, 0.0), None),
    ("Deck Color", "NodeSocketColor", (1.0, 1.0, 1.0, 1.0), None),
    ("Deck Sun Light", "NodeSocketColor", (0.0, 0.0, 0.0, 1.0), None),
    ("Moon Glow", "NodeSocketFloat", 0.0, (0.0, 10.0)),
]

MILKY_WAY_SCALE = 0.22          # Milky Way radiance relative to a limiting-magnitude star pixel (visual calibration)


def add_time_driver(tree: bpy.types.NodeTree, node_name: str, scene: bpy.types.Scene) -> None:
    """Drive ``tree.nodes[node_name]`` (a Value node) with scene time in seconds: (frame - 1) / fps * fps_base."""
    path = f'nodes["{node_name}"].outputs[0].default_value'
    try:
        tree.driver_remove(path)
    except (TypeError, RuntimeError, ValueError):
        pass
    fc = tree.driver_add(path)
    drv = fc.driver
    drv.type = "SCRIPTED"
    drv.expression = "(frame - 1) / fps * base"
    for name, data_path in (("fps", "render.fps"), ("base", "render.fps_base")):
        v = drv.variables.new()
        v.name = name
        v.type = "SINGLE_PROP"
        v.targets[0].id_type = "SCENE"
        v.targets[0].id = scene
        v.targets[0].data_path = data_path


def build_group(scene: bpy.types.Scene) -> bpy.types.NodeTree:
    """(Re)build the group from scratch and return it."""
    old = bpy.data.node_groups.get(GROUP_NAME)
    if old is not None:
        old.name = GROUP_NAME + ".old"
        old.use_fake_user = False
    tree = bpy.data.node_groups.new(GROUP_NAME, "ShaderNodeTree")
    tree["atmosfx_version"] = GROUP_VERSION
    b = Builder(tree)
    for name, stype, default, rng in INPUTS:
        Builder.add_input(tree, name, stype, default, *(rng or (None, None)))
    Builder.add_output(tree, "Background", "NodeSocketShader")

    gin = b.node("NodeGroupInput", "Inputs")
    gout = b.node("NodeGroupOutput", "Outputs")
    gi = lambda name: gin.outputs[name]          # noqa: E731

    b.col()
    tc = b.node("ShaderNodeTexCoord")
    d = tc.outputs["Generated"]                  # world-space ray direction
    dx, dy, dz = b.sep(d)
    time_node = b.node("ShaderNodeValue", "AtmosFX Time")
    time_s = time_node.outputs[0]

    # ------------------------------------------------------------- 1. Nishita sky
    b.col()
    sky = b.node("ShaderNodeTexSky", "Sky", sky_type="MULTIPLE_SCATTERING", sun_disc=False)
    sky_col = b.scale_rgb(sky.outputs["Color"], gi("Sky Strength"))

    # ------------------------------------------------------------- 2. night glow
    horizon_w = b.math("SUBTRACT", 1.0, b.math("MULTIPLY", dz, dz), clamp=True)
    glow_k = b.math("MULTIPLY", gi("Night Glow"), b.math("ADD", 0.4, b.math("MULTIPLY", horizon_w, 0.6)))
    glow = b.scale_rgb(gi("Night Glow Color"), glow_k)

    # ------------------------------------------------------------------ 3. stars
    b.col()
    d_eq = b.mapping(d, rot=gi("Celestial Rotation"))
    env = b.node("ShaderNodeTexEnvironment", "Star Map", interpolation="Linear", projection="EQUIRECTANGULAR")
    b.set(env.inputs["Vector"], d_eq)
    star_rgb = env.outputs["Color"]
    lum = b.luminance(star_rgb)
    thr = gi("Star Threshold")
    star_mask = b.smoothstep(lum, b.math("MULTIPLY", thr, 0.35), b.math("MULTIPLY", thr, 0.9))
    extinction = b.smoothstep(dz, -0.03, 0.18)                        # stars fade into horizon haze
    star_k = b.math("MULTIPLY", b.math("MULTIPLY", star_mask, gi("Star Brightness")), extinction)
    stars = b.scale_rgb(star_rgb, star_k)

    # --------------------------------------------------------------- 4. Milky Way
    b.col()
    g = b.mapping(d, rot=gi("Galactic Rotation"))
    gx, gy, gz = b.sep(g)
    lat = b.math("ARCSINE", b.math("MINIMUM", b.math("MAXIMUM", gz, -1.0), 1.0))
    lon = b.math("ARCTAN2", gy, gx)

    def gauss(x, sigma):
        t = b.math("DIVIDE", x, sigma)
        return b.math("EXPONENT", b.math("MULTIPLY", b.math("MULTIPLY", t, t), -1.0))

    band = gauss(lat, 0.22)
    bulge = b.math("MULTIPLY", gauss(lon, 0.75), gauss(lat, 0.38))
    n_dust = b.noise(g, 4.0, 5.0, 0.62)
    n_cloud = b.noise(g, 14.0, 3.0, 0.5)
    lanes = b.math("MULTIPLY", b.smoothstep(n_dust, 0.50, 0.64), band)
    cloudiness = b.math("ADD", 0.45, b.math("MULTIPLY", n_cloud, 1.1))
    mw_i = b.math("MULTIPLY",
                  b.math("ADD", b.math("MULTIPLY", b.math("MULTIPLY", band, 0.55), cloudiness),
                         b.math("MULTIPLY", bulge, 1.5)),
                  b.math("SUBTRACT", 1.0, b.math("MULTIPLY", lanes, 0.75)))
    mw_col = b.mix_rgb(b.math("MINIMUM", b.math("MULTIPLY", bulge, 1.4), 1.0), (0.72, 0.82, 1.0, 1.0), (1.0, 0.78, 0.52, 1.0))
    mw_k = b.math("MULTIPLY", b.math("MULTIPLY", mw_i, gi("Milky Way Strength")), b.math("MULTIPLY", extinction, MILKY_WAY_SCALE))
    mw = b.scale_rgb(mw_col, mw_k)

    # ------------------------------------------------------------------- 5. moon
    b.col()
    cam = b.node("ShaderNodeLightPath").outputs["Is Camera Ray"]
    gate = b.mix(gi("Disc Camera Only"), 1.0, cam)                  # 1 -> camera rays only
    m = gi("Moon Direction")
    cos_m = b.dot(d, m)
    r_m = gi("Moon Angular Radius")
    edge_in = b.math("COSINE", b.math("MULTIPLY", r_m, 0.97))
    edge_out = b.math("COSINE", b.math("MULTIPLY", r_m, 1.03))
    m_mask = b.smoothstep(cos_m, edge_out, edge_in)
    t_m = b.vmath("SUBTRACT", d, b.vmath("SCALE", m, scale=cos_m))
    u_m = b.vmath("SCALE", t_m, scale=b.math("DIVIDE", 1.0, b.math("MAXIMUM", b.math("SINE", r_m), 1e-6)))
    rho2 = b.dot(u_m, u_m)
    z_m = b.math("SQRT", b.math("SUBTRACT", 1.0, rho2, clamp=True))
    n_m = b.vmath("SUBTRACT", u_m, b.vmath("SCALE", m, scale=z_m))  # surface normal toward the observer
    lit = b.math("MAXIMUM", b.dot(n_m, gi("Moon Light Direction")), 0.0)
    maria = b.noise(n_m, 2.4, 4.0, 0.55)
    albedo = b.mix(b.smoothstep(maria, 0.42, 0.58), 1.0, 0.62)
    earthshine = 0.012
    m_shade = b.math("ADD", b.math("MULTIPLY", lit, albedo), earthshine)
    moon_k = b.math("MULTIPLY", b.math("MULTIPLY", m_mask, gi("Moon Radiance")), b.math("MULTIPLY", m_shade, gate))
    moon = b.scale_rgb(gi("Moon Color"), moon_k)

    # moonlit sky: a halo around the Moon plus a faint overall lift, tinted like the moonlight
    halo = b.math("EXPONENT", b.math("MULTIPLY", b.math("SUBTRACT", 1.0, cos_m), -12.0))
    lift = b.math("ADD", 0.35, b.math("MULTIPLY", b.math("MAXIMUM", dz, 0.0), 0.65))
    moon_glow_k = b.math("MULTIPLY", gi("Moon Glow"), b.math("ADD", b.math("MULTIPLY", halo, 1.6), b.math("MULTIPLY", lift, 0.4)))
    moon_glow = b.scale_rgb(gi("Moon Color"), moon_glow_k)

    # -------------------------------------------------------------------- 6. sun
    s = gi("Sun Direction")
    cos_s = b.dot(d, s)
    r_s = gi("Sun Angular Radius")
    s_in = b.math("COSINE", b.math("MULTIPLY", r_s, 0.985))
    s_out = b.math("COSINE", b.math("MULTIPLY", r_s, 1.015))
    s_mask = b.smoothstep(cos_s, s_out, s_in)
    t_s = b.vmath("SUBTRACT", d, b.vmath("SCALE", s, scale=cos_s))
    rho_s = b.math("DIVIDE", b.length(t_s), b.math("MAXIMUM", b.math("SINE", r_s), 1e-6))
    mu = b.math("SQRT", b.math("SUBTRACT", 1.0, b.math("MULTIPLY", rho_s, rho_s), clamp=True))
    limb = b.math("SUBTRACT", 1.0, b.math("MULTIPLY", b.math("SUBTRACT", 1.0, mu), 0.45))
    sun_k = b.math("MULTIPLY", b.math("MULTIPLY", s_mask, gi("Sun Disc Radiance")), b.math("MULTIPLY", limb, gate))
    sun = b.scale_rgb(gi("Sun Color"), sun_k)

    # ------------------------------------------------------------- composite 1-6
    b.col()
    celestial = b.add_rgb(stars, mw)
    bg = b.add_rgb(b.add_rgb(sky_col, glow), celestial)
    bg = b.add_rgb(bg, b.add_rgb(b.add_rgb(moon, sun), moon_glow))

    # ---------------------------------------------------------------- 7. cloud deck
    dz_safe = b.math("MAXIMUM", dz, 1e-4)
    dist = b.math("DIVIDE", gi("Deck Altitude"), dz_safe)
    p_deck = b.vmath("SCALE", d, scale=dist)
    wind_off = b.vmath("SCALE", gi("Deck Wind Velocity"), scale=time_s)
    px, py, _pz = b.sep(p_deck)
    plane = b.comb(px, py, 0.0)
    fib = gi("Deck Fibre")
    freq = gi("Deck Frequency")
    sc_vec = b.comb(freq, b.math("MULTIPLY", freq, fib), freq)
    loc = b.vmath("SUBTRACT", gi("Deck Seed Offset"), b.vmath("MULTIPLY", wind_off, sc_vec))
    deck_p = b.mapping(plane, loc=loc, scale=sc_vec)
    n_deck = b.noise(deck_p, 1.0, 5.0, 0.58)
    soft = gi("Deck Softness")
    thr_d = gi("Deck Threshold")
    a_raw = b.smoothstep(n_deck, thr_d, b.math("ADD", thr_d, b.math("MULTIPLY", soft, 0.25)))
    fade = b.smoothstep(dz, 0.01, 0.16)
    alpha = b.math("MULTIPLY", b.math("MULTIPLY", a_raw, fade), gi("Deck Opacity"))
    sun_lobe = b.math("EXPONENT", b.math("MULTIPLY", b.math("SUBTRACT", 1.0, cos_s), -7.0))
    deck_rgb = b.add_rgb(gi("Deck Color"), b.scale_rgb(gi("Deck Sun Light"), b.math("ADD", 0.25, b.math("MULTIPLY", sun_lobe, 1.6))))
    bg = b.mix_rgb(alpha, bg, deck_rgb)

    # ------------------------------------------------------------------ 8. ground
    g_mask = b.math("MULTIPLY", b.smoothstep(dz, gi("Ground Blend"), b.math("MULTIPLY", gi("Ground Blend"), -1.0)),
                    gi("Ground Enabled"))
    ground = b.scale_rgb(gi("Ground Color"), gi("Ground Strength"))
    bg = b.mix_rgb(g_mask, bg, ground)

    b.col()
    bgn = b.node("ShaderNodeBackground", "Background")
    b.set(bgn.inputs["Color"], bg)
    b.set(bgn.inputs["Strength"], 1.0)
    tree.links.new(bgn.outputs[0], gout.inputs["Background"])

    add_time_driver(tree, "AtmosFX Time", scene)
    if old is not None:
        bpy.data.node_groups.remove(old)
    return tree


def ensure_group(scene: bpy.types.Scene) -> bpy.types.NodeTree:
    tree = bpy.data.node_groups.get(GROUP_NAME)
    if tree is None or tree.get("atmosfx_version") != GROUP_VERSION:
        tree = build_group(scene)
    return tree
