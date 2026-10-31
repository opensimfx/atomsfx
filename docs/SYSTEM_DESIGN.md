# System design

## 1. Principles

1. **Physics first, in one place.** Everything computable without Blender lives in `atmosfx/core/` and is covered by
   unit tests. The Blender layer only applies those numbers.
2. **One derivation point.** `core/skyview.compute_view(SkyParams) -> SkyView` produces *every* value that reaches a
   shader socket or lamp. If a number is on screen, a test can reproduce it.
3. **Measure Blender, don't remember it.** Conventions (sun rotation, equirect mapping, Euler order) were measured
   with headless renders and are pinned by tests; see section 6.
4. **Bounded volumes only.** No world volume (section 5.1).
5. **Content-addressed caches.** Anything expensive is keyed by a hash of the state that produces it.
6. **Honest scale.** Ratios are physical; absolute brightness anchors are artistic and named (section 7).

## 2. Layers

```
ui/        properties (scene.atmosfx), operators, panels, preset <-> settings conversion
 |  update callbacks / operators
scene/     apply.refresh(scene): the orchestrator;  world.py  objects.py
 |  SkyParams -> SkyView
nodes/     dsl.py (builder)  sky.py  volumes.py      <- only place node trees are built
core/      physics  astro  stars_data  starmap  clouds  presets  skyview  identity     <- no bpy
```

Dependencies point downward only. `core/` is checked for Blender imports by `tools/build_extension.py` and by the
unit tests running in a plain interpreter.

## 3. Data flow

```
user edits a property ------------------------------.
preset load (ui/state.write_preset) ----------------+--> scene.atmosfx (PropertyGroup)
frame change with Animate Time (handler) ------------'            |
                                                                  v
                    scene/apply.params_from_settings  ->  core.skyview.SkyParams
                                                                  |  compute_view
                                                                  v
                                                              SkyView
          .---------------------+------------------+----------------+-----------------.
          v                     v                  v                v                 v
   world.update          objects.update_lamps   update_cloud_layers  update_cloud_sun  update_fog
 (sky group sockets,    (sun, moon lamps)      (cylinder domains,   (2nd sun + light   (haze dome,
  Nishita node props,                           cloud group          linking)           fog bank)
  star image)                                   sockets)
```

`refresh()` is re-entrancy guarded and cheap enough for live editing. A property change inside `suspend_updates()`
(used by preset loading and by operators that set several properties) triggers nothing; one `refresh` follows.

## 4. Node groups

All three groups are rebuilt from code when missing or when their `atmosfx_version` custom property differs from the
constant in the source, so a file saved by an older build upgrades itself on load.

### 4.1 `AtmosFX Sky` (world)

Inputs are listed in `nodes/sky.py: INPUTS`; composited in this order:

| # | Layer | Notes |
|---|---|---|
| 1 | Nishita **Sky Texture** | multiple scattering (single in Draft). `sun_disc` is always off; we draw our own disc. |
| 2 | Night glow | constant blue-green airglow, stronger toward the horizon |
| 3 | Stars | `Environment Texture` of the baked J2000 float image, vector rotated by a **Mapping** node whose Euler comes from the ephemeris; hidden below a luminance threshold (the limiting magnitude); faded near the horizon |
| 4 | Milky Way | second Mapping into galactic coordinates; Gaussian band in latitude, bulge in longitude, two noises for lanes and clumps |
| 5 | Moon | disc by angular distance; surface normal reconstructed on a unit sphere; Lambert term with the **true Sun direction**, so phase and bright limb are correct; procedural maria; earthshine floor |
| 5b | Moon glow | halo plus faint overall lift, tinted like moonlight |
| 6 | Sun | disc radiance = lamp strength / solid angle, limb darkening 0.45 |
| 7 | 2D cloud deck | ray/plane intersection at the deck altitude, stretched noise (fibre), wind by a time node, lit by ambient + a forward-scatter lobe toward the sun |
| 8 | Ground | below the horizon, soft blend |

Sun and moon discs are gated by *Light Path > Is Camera Ray* when a lamp lights the scene, so the world never
double-lights it.

### 4.2 `AtmosFX Cloud` (volume)

World-space position, so objects can be moved and scaled freely. Density =
`smoothstep(field, threshold, threshold + softness) * Density * radial_fade` where
`field = fbm(p * frequency, octaves) + anvil - 0.32 (1 - profile) - detail_erosion`.
`profile` is the height profile of the kind (flat base, rounded top). Two Henyey-Greenstein lobes (forward `g`,
back -0.25 at 25 %) approximate cloud phase, plus an **ambient/top emission and a forward-scatter halo** for the
multiple scattering a bounded path tracer cannot build up (section 5.4). Outputs `Volume`, plus `Density`, `Field`
and `Base Noise` for diagnostics (the coverage test renders the `Density` output).

### 4.3 `AtmosFX Fog` (volume)

`density = sigma0 * exp(-max(z - base, 0) / H) * patchiness * edge_fade`; scatter + absorption + an **ambient
in-scatter emission** proportional to density (section 5.3).

## 5. Decisions that are not obvious

### 5.1 Fog is a bounded dome, not a world volume

An infinite world volume in Cycles makes every ray that leaves the scene travel an infinite distance: the medium
swallows it and the **whole frame renders black** (reproduced with a single Volume Scatter and any density from
6.5e-5 to 1e-3, with sampling, step size and bounce settings varied). So "world" fog is `AtmosFX Haze`, a cylinder of
radius `1.4 x visibility` (transmittance there is 0.3 %, so the edge is invisible) and height `5 x scale height`
that follows the camera in X/Y. A fog bank is the same object type with its own size and visibility.
Cost: a bounded heterogeneous volume, still the most expensive thing in a scene; see the user guide.

### 5.2 Clouds get their own sun (light linking)

The sunlight that reaches a cloud at 4 km crossed far less air than the light at the ground. One lamp cannot be
right for both, so `AtmosFX Sun` is light-linked to **exclude** the cloud domains and `AtmosFX Sun Clouds`,
attenuated at the mean mid-height of the layers, is linked to **include only** them. Cloud domains still block the
ground sun (shadow linking is untouched), so cloud shadows on the ground are correct. Verified: light linking
restricts a Sun lamp's effect on a volume object in Cycles (test lamp lit the volume only when linked to it). The
EEVEE render path is checked for liveness, but the light-linking restriction itself is not separately measured there.

### 5.3 Fog emits its ambient light

In thick fog the light a droplet receives is mostly multiply scattered. With the handful of volume bounces a render
can afford, a dense fog path-traces to black (measured: the "dense fog" preset rendered 0.000 everywhere). The fog
shaders add an Emission term `density * ambient`, where `ambient` is the diffuse sky light plus a share of the sun's
forward scatter (`skyview.fog_ambient`). Physically this is the equilibrium radiance of a scattering medium.
It slightly double counts single scattering; that is accepted.

### 5.4 Clouds emit their multiple scattering

Like fog, a cloud is mostly multiply scattered light, and a path tracer with a handful of volume bounces renders
thick layers too dark and too grey. The cloud shader therefore adds an emission proportional to local density:

`ambient -> top` mixed by `smoothstep(height, 0.35, 0.9)`, plus a forward-scatter halo
`density * Glow Strength * max(dot(-Incoming, Sun), 0)^8`.

`physics.cloud_scatter_lighting` derives the colours from the same inputs as the lamps: a cool blue base while the
sun is high (shadowed underside), a warm base once the sun is low (the beam comes from below), a bright top scaled
by the cloud-height sun strength, and a halo that grows as the beam reddens. Anchors were tuned against Cycles
renders of `sunset_clouds` and `fair_weather_cumulus`. This is display calibration, not radiative transfer: it
double counts a little single scattering, which is accepted for the same reason as the fog term.

### 5.5 Cloud coverage means filled area

The shape field is approximately normal (mean 0.50, sd 0.08 for normalised fractal noise, measured by rendering a
density slice). `coverage_threshold(c) = 0.5 - 0.08 * probit(c)` makes the filled fraction equal `c`. Measured
filled fractions for coverage 0.1 / 0.25 / 0.4 / 0.6 / 0.8 were 0.09 / 0.23 / 0.37 / 0.57 / 0.77. The render test
repeats this and requires agreement within 0.12.

### 5.6 Clouds and the sun lamp are not double counted

Volumetric clouds cast real shadows and hide real stars in the render, so they do *not* reduce the lamp or the star
limiting magnitude. Only the 2D deck (which casts nothing) does.

### 5.7 Star map

`core/starmap.bake_star_map` returns a float array in the J2000 frame; the scene layer wraps it in a half-float,
`Non-Color` image, packs it, and names it `AtmosFX Stars <hash>`, where the hash covers resolution, seed, density and
the catalogue version. Changing brightness, limiting magnitude or time never rebakes (the shader thresholds and
rotates). The image's colour space and precision **must be set before the pixels**: changing either on a generated
image regenerates it blank (found the hard way; a test pins it).

### 5.8 Time

Cloud, deck and fog motion use a `Value` node driven by the expression `(frame - 1) / fps * fps_base`, so wind is
frame-rate independent and needs no Python at render time. Earth-mode clock animation needs the ephemeris and runs in
a persistent `frame_change_post` handler (so the add-on must be enabled on a render farm).

### 5.9 Quality tiers

| | Draft | Preview | Final |
|---|---|---|---|
| Sky | single scattering | multiple | multiple |
| Cloud noise octaves | 2 | 4 | 7 |
| Cycles volume step rate / bounces / max steps | 3.0 / 2 / 512 | 1.5 / 4 / 1024 | 0.75 / 12 / 2048 |
| EEVEE volume tile / samples / shadows | 8 / 48 / off | 4 / 64 / on | 2 / 128 / on |

The step rate is multiplied by `clouds.step_rate_scale`, a per-layer optical-depth budget collapsed into one
scene value (Cycles exposes one step rate): a dense layer keeps the table value, while a scene made only of thin
layers (cirrus, thin altostratus) relaxes it. "Configure render settings" can be switched off; the add-on then
touches nothing.

## 6. Measured conventions (Blender 5.0.1; checks re-run on 5.2.1)

| Fact | Measurement | Pinned by |
|---|---|---|
| Sky Texture `sun_rotation` is the azimuth from +Y toward +X | brightest pixel of 8 sign/swap variants | `sky_node_follows_the_sun`, render check |
| `Texture Coordinate > Generated` in a world is the unit ray direction | colour = vector probe | node group design |
| Environment texture: +X at u=0.5, +Y at u=0.25, -Y at u=0.75, v = 0.5 + asin(z)/pi | UV-coded image sampled in 8 directions | `test_equirect_conventions_round_trip` |
| Mapping node (point) applies the Euler 'XYZ' rotation matrix `Rz Ry Rx` | star alignment within 0.08 degrees | `stars_render_where_the_ephemeris_says` |
| `mathutils` Euler matrices are float32 | tolerance 1e-5 | `euler_convention_matches_mathutils` |
| A Sun lamp shines along its local -Z | lamp matrix check | `lamps_point_at_the_sun_and_moon` |
| Default `Camera.clip_end` silently removes volumes 1-3 km away | ortho slice vanished | camera clip warning and operator |
| `Sky Texture` radiance is ~30x a 3.0-strength sun lamp's scale | zenith blue ~7 at noon | `SKY_SCALE` |
| Any world volume blanks the Cycles frame | single Volume Scatter probe | haze-dome design |
| A bpy wheel needs `read_factory_settings(use_empty=True)` before scenes render | worlds rendered black otherwise | test harness |
| EEVEE's engine identifier is `BLENDER_EEVEE` in 5.0.1 and 5.2.1; headless EEVEE renders work on macOS arm64 | four presets rendered, non-black | `eevee_*` checks |
| EEVEE 96x96/8-sample renders of AtmosFX presets take ~0.4 s each on an M-series Mac | timing while writing the checks | `eevee_*` checks |
| Cloud multiple-scatter fill: at 52 degrees the base is blue (B/R 2.0) and the top is 8x brighter; at 4 degrees the base is warm (R/B 3.2) and the halo strength is 20x noon | `cloud_scatter_lighting` values, Cycles previews of `fair_weather_cumulus` and `sunset_clouds` | `test_cloud_lighting_*` |
| Blender 5.2.1 LTS passes the fast suite and every Cycles/EEVEE render check unchanged | 27/27 with both render flags, macOS arm64 | CI matrix, `ATMOSFX_*` suites |

## 7. Calibration constants (artistic anchors)

| Constant | Value | Where | Meaning |
|---|---|---|---|
| Sun strength at 90 degrees | 3.0 | property | Blender convention for daylight at 0 EV |
| Moon strength, full, zenith | 0.12 | property | physical value (~1e-5) would need 18 stops of exposure |
| `SKY_SCALE` | 0.03 | `skyview` | restores a plausible sky:sun irradiance ratio |
| `STAR_GAIN` | 0.08 | `skyview` | eye-calibrated for a dark-sky render |
| `MILKY_WAY_SCALE` | 0.22 | `nodes/sky.py` | eye-calibrated |
| `MOON_GLOW` | 0.012 | `skyview` | eye-calibrated |
| `CLOUD_LOW_SUN_FILL` / `CLOUD_TOP_LOW_FILL` | 0.16 / 0.20 | `physics` | warm underside/top multiple-scatter fill at low sun |
| `CLOUD_GLOW_LOW_GAIN` | 4.0 | `physics` | forward-scatter halo at low sun |

## 8. Preset schema

`core/presets.Preset` with nested `SunCfg`, `SkyCfg`, `MoonCfg`, `StarsCfg`, `CloudLayerCfg` (list, max 3), `DeckCfg`,
`FogCfg`. JSON file: `{"schema": 1, "presets": [...]}`; a newer schema number is refused. `ui/state.MAP` is the
single table mapping preset fields to properties; `write_preset` and `capture` both use it.

## 9. Failure behaviour

- Invalid preset file: operator reports an error and changes nothing.
- A saved file whose groups are older: rebuilt on load (`load_post` handler); a failure there is printed, never raised.
- Missing optional properties on other Blender versions (`volumetric_end`, ...): set through `try/except`.
- Day-of-month beyond the month's length is clamped.

## 10. Known limits

Flat domains (no planet curvature); clouds repeat per domain and fade at the radius; the haze dome follows the
camera in X/Y only; the sky is one hemisphere model for one viewpoint; no planets, no aurora; star proper motion and
nutation are ignored; EEVEE froxel range caps how far fog and clouds can be seen.
