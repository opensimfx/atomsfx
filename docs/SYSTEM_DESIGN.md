# System Design

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
| 5b | Moon glow | aureole (half moonlight, half sky blue) plus an overall lift in the day sky's Rayleigh blue |
| 6 | Sun | disc radiance = lamp strength / solid angle, limb darkening 0.45 |
| 7 | 2D cloud deck | ray/plane intersection at the deck altitude, stretched noise (fibre), wind by a time node, lit by ambient + a forward-scatter lobe toward the sun |
| 8 | Ground | below the horizon, soft blend |

Sun and moon discs are gated by *Light Path > Is Camera Ray* when a lamp lights the scene, so the world never
double-lights it.

### 4.2 `AtmosFX Cloud` (volume)

World-space position, so objects can be moved and scaled freely. Density =
`smoothstep(field, threshold, threshold + softness) * Density * radial_fade`, with

`field = mix(perlin, 0.55 worley + 0.12, billow) + anvil + weather + cell - 0.32 (1 - profile) - 0.18 roundness h^2 - erosion`

where `perlin` is fractal noise, `worley` inverted fractal Voronoi F1 (rounded lumps), `weather` a 2D field with
cells ~3x the cloud size, `cell` the optional storm cell, `profile` the kind's height ramps (sharp flat base) and
`erosion` high-frequency Worley, inverted toward the base (wisps) and billowy toward the top. The noise frame is
turned to the layer's wind and stretched downwind by the kind's `Fibre`. Scattering blends the
Mie phase of the droplets with a soft Henyey-Greenstein lobe (water) or uses Henyey-Greenstein (ice); an emission
fill exists for the Draft tier only (section 5.4). Outputs `Volume`, plus `Density`, `Field` and `Base Noise` for
diagnostics (the coverage calibration renders `Field`, the coverage test renders `Density`).

### 4.3 `AtmosFX Fog` (volume)

Aerosol: `density = sigma0 * exp(-max(z - base, 0) / H) * patchiness * edge_fade`, scatter + absorption. Clean air
(dome only): Rayleigh-phase scatter, blue-weighted per channel, 8 km scale height. Plus an ambient in-scatter
emission for optically thick fog, seen by camera rays only (section 5.3).

## 5. Decisions that are not obvious

### 5.1 Fog is a bounded dome, not a world volume

An infinite world volume in Cycles makes every ray that leaves the scene travel an infinite distance: the medium
swallows it and the **whole frame renders black** (reproduced with a single Volume Scatter and any density from
6.5e-5 to 1e-3, with sampling, step size and bounce settings varied). So "world" fog is `AtmosFX Haze`, a cylinder
that follows the camera in X/Y: radius `max(1.4 x visibility, 40 km)` (transmittance at 1.4 V is 0.3 %, so the edge
is invisible; 40 km so the clean air reaches distant ridges), height `max(5 x scale height, 4 km)`, ending 25 m under
the lowest cloud base (section 5.2). A fog bank is the same object type with its own size and visibility, and no air.

### 5.2 Clouds get their own sun (light linking), unless volumes overlap

The sunlight that reaches a cloud at 4 km crossed far less air than the light at the ground. One lamp cannot be
right for both, so `AtmosFX Sun` is light-linked to **exclude** the cloud domains and `AtmosFX Sun Clouds`,
attenuated at the mean mid-height of the layers, is linked to **include only** them. Cloud domains still block the
ground sun (shadow linking is untouched), so cloud shadows on the ground are correct.

Cycles light linking does **not** separate overlapping volumes. Measured on Blender 5.2.3: a cumulus layer inside
the haze dome lost the cloud sun and rendered grey on its sunlit side; with the dome capped below the cloud base the
same layer rendered bright white. So the dome ends 25 m under the lowest cloud base (haze is the boundary layer,
which cumulus bases cap; the gap also keeps faces from coinciding, see 5.10), and when a fog bank or a very low base
makes an overlap unavoidable, the split is dropped and one sun lights everything (`objects.haze_overlaps_clouds`).

### 5.3 Fog emits ambient light only where it is thick, and only for the camera

In thick fog the light a droplet receives is mostly multiply scattered; with the volume bounces a render can afford,
a dense fog path-traces too dark. The fog shader adds `density * ambient * Fill`, with `ambient` the diffuse sky
light plus a share of the sun's forward scatter (`skyview.fog_ambient`). The gain `Fill` is the tier's share
(Draft 1, Preview 0.5, Final 0.3) times `smoothstep(1, 8, sigma0 H)` of the vertical optical depth: light escapes a
layer through its thinnest dimension, so haze (a clear day is ~0.15) gets none and dense fog (~15) the full term.
Before this, a 35 km-visibility haze rendered as a milky whiteout. The emission is gated by *Light Path > Is Camera
Ray*: it brightens what is seen without lighting the scene (see 5.4 for why that matters).

### 5.4 Cloud light comes from real bounces

A cloud is mostly multiply scattered light. Earlier versions emitted a display-calibrated fill in proportion to
density. That is wrong in a medium that absorbs nothing and scatters forward: every emitted photon escapes, so the
emission adds energy in proportion to optical depth (measured: an altocumulus deck at sunset lit the ground orange,
as bright as the sky). Gating the fill to camera rays fixed that, but any Light Path node in the cloud shader made
Metal render it more than 20x slower (Blender 5.2.3; a 480 px frame did not finish in 20 minutes; the same node in
the fog shader is harmless), presumably because a path-dependent shader defeats the majorant grid that makes
null-scattering volumes fast. So Preview and Final use **no fill**: the phase blend (section 4.2, PHYSICS 8) lets
light diffuse out in tens of bounces, and the tiers bounce 32 and 96 times (bounces are cheap: most paths leave the
cloud early). Draft (8 bounces, viewport) keeps a 0.6 fill of `physics.cloud_scatter_lighting`.

### 5.5 Cloud coverage means filled area

The shape field at mid-height is close to normal. Each kind's mean and standard deviation were measured by
rendering the shader's `Field` output on an orthographic slice of 25 x 25 cloud cells (Blender 5.2.3, Final
octaves); q10 and q90 fall within 0.002 of the normal quantiles. `coverage_threshold(c, mean, sd) = mean - sd *
probit(c)` then makes the filled fraction equal `c`. The render test repeats the check and requires agreement
within 0.12.

| Kind | mean | sd | edge (sd) |
|---|---|---|---|
| Cumulus | 0.432 | 0.067 | 0.12 |
| Stratocumulus | 0.480 | 0.060 | 0.25 |
| Stratus | 0.495 | 0.066 | 0.8 |
| Altocumulus | 0.484 | 0.055 | 0.2 |
| Altostratus | 0.496 | 0.068 | 0.9 |
| Cumulonimbus | 0.493 | 0.076 | 0.12 |
| Cirrus | 0.511 | 0.083 | 0.7 |

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
| Cycles volume bounces | 8 | 32 | 96 |
| Cycles volume step rate / max steps (biased renderer only) | 3.0 / 512 | 1.5 / 1024 | 0.75 / 2048 |
| Cloud emission fill | 0.6 | 0 | 0 |
| Fog fill (times the optical-depth ramp) | 1.0 | 0.5 | 0.3 |
| EEVEE volume tile / samples / shadows | 8 / 48 / off | 4 / 64 / on | 2 / 128 / on |

Blender 5 renders volumes with null scattering by default, which ignores step rate and max steps; they still
apply when *Render > Volume > Biased* is on. The step rate is multiplied by `clouds.step_rate_scale`, a per-layer
optical-depth budget collapsed into one scene value. Max bounces is raised to the volume bounces when it is lower
(the total cap would clamp them). "Configure render settings" can be switched off; the add-on then touches nothing.

### 5.10 Volumes never share a face

Coincident faces of two volume objects (the haze dome's top on a cloud base, one layer's top on the next layer's
base) render as vertical streaks in Cycles and cost time (a cumulus frame: 181 s with streaks, 59 s without). Cloud
domains are padded `3 + 1.7 i` metres beyond their layer (the shader places density by absolute altitude, so the
padding is empty) and the dome stops 25 m short of the lowest base.

### 5.11 Auto exposure

`skyview.auto_exposure` sets *Color Management > Exposure* from the scene's light (PHYSICS 9). The rendered
irradiance uses a table of the AtmosFX sky's irradiance measured in Blender 5.2.3 (`skyview.SKY_IRRADIANCE`) and
counts sky light three times, because the sky is usually in frame; the darkening per scene comes from
`physics.CINEMATIC_KEY`, tuned on the look bench. It can be switched off or biased in the main panel.

## 6. Measured conventions (Blender 5.0.1; checks re-run on 5.2.1; 1.0 look work on 5.2.3)

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
| Cloud multiple-scatter fill (Draft only since 1.0): at 52 degrees the base is blue (B/R 2.0) and the top is 8x brighter; at 4 degrees the base is warm (R/B 3.2) and the halo strength is 20x noon | `cloud_scatter_lighting` values, Cycles previews of `fair_weather_cumulus` and `sunset_clouds` | `test_cloud_lighting_*` |
| AtmosFX sky irradiance on a horizontal white plane (world only): 0.472 at 90 degrees, 0.0412 at 0, 0.00298 at -5, floor 0.0015 | Blender 5.2.3 Cycles, Metal | `SKY_IRRADIANCE`, `test_sky_irradiance_table` |
| Light linking does not separate overlapping volumes | cumulus inside the haze dome lost its linked sun | `haze_overlaps_clouds`, section 5.2 |
| A Light Path node in the cloud shader makes Metal >20x slower; in the fog shader it is harmless | 480 px cumulus frame, Blender 5.2.3 | section 5.4 |
| Coincident volume faces streak | haze dome top on a cumulus base | section 5.10 |
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
| `CLOUD_LOW_SUN_FILL` / `CLOUD_TOP_LOW_FILL` | 0.16 / 0.20 | `physics` | warm underside/top multiple-scatter fill at low sun (Draft) |
| `CLOUD_GLOW_LOW_GAIN` | 4.0 | `physics` | forward-scatter halo at low sun (Draft) |
| Cloud phase blend | 60 % HG g 0.4 + 40 % Mie | `clouds`, cloud shader | stands in for multiple-scattering octaves |
| `CINEMATIC_KEY` | noon 0 ... starlight 5 stops | `physics` | on-screen darkening per real illuminance |
| `SKY_WEIGHT` | 2 | `skyview` | extra weight of sky light in the exposure |
| `CLOUD_BOUNCE` | 0.12 | `skyview` | light sent down by sunlit clouds, for the exposure |
| `MOON_COLOR_TINT` | (0.80, 0.92, 1.08) | `skyview` | moonlight graded cool (Purkinje shift) |

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
