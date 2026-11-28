# User Guide

## 1. Basics

Everything is in the 3D Viewport sidebar (**N**) under **AtmosFX**. Pick a preset, press **Add Atmosphere**. AtmosFX
creates:

| Created | What it is |
|---|---|
| `AtmosFX World` | the sky (your previous world is remembered and restored by **Remove Atmosphere**) |
| `AtmosFX Sun`, `AtmosFX Moon` | Sun lamps aimed by the ephemeris |
| `AtmosFX Sun Clouds` | a second sun for cloud layers only (light-linked), when clouds exist and no fog volume overlaps them |
| `AtmosFX Cloud 1..3` | cylinder volume domains, one per cloud layer |
| `AtmosFX Haze`, `AtmosFX Fog Domain` | haze dome / fog bank when fog is on |
| `AtmosFX Stars <hash>` | the baked star image, packed into the .blend |

All of them live in the `AtmosFX` collection (the light-linking collections are internal). Do not rename them.
Everything is regenerated from the panel settings, so edit the settings, not the objects (you may move cloud and fog
objects in X/Y and scale them; AtmosFX owns their Z and size).

## 2. The panels

**Main** - preset, *Load preset*, rebuild button, **Quality** (Draft / Preview / Final), *Live update*,
*Set render* (let AtmosFX configure volume settings), **Auto exposure** and its *Bias*, camera clip warning, remove.
Auto exposure sets *Color Management > Exposure* from the scene's light, so noon, golden hour, blue hour and a moonlit
or starry night each render at a cinematic brightness: night darker than day, but legible. Turn it off to keep your
own exposure; use *Bias* to grade brighter or darker.

**Time and Place**
- *Artistic*: sun elevation and azimuth by hand. Stars still follow the date and place.
- *Earth*: latitude, longitude, date, local time, UTC offset. *North offset* is the compass bearing your scene's +Y axis
  points to (0 = +Y is north). *Use Current Date and Time* reads this computer's clock.
- *Animate time*: the clock advances with the timeline at *Hours per second*: 1.0 is one simulated hour per second of
  animation (24 hours take 24 s at any frame rate).

**Sky and Sun** - air, aerosols, ozone, viewpoint altitude, sky strength, night glow, *Sun lamp* (on: a lamp lights the
scene and the sky disc is camera-only; off: the disc in the sky lights the scene, noisier), sun strength and size,
ground below the horizon.
*Art Direction* (all neutral by default): **Sun halo** and **Halo size** (a bright aureole around the Sun: hazy
air, thin cloud, a lens look), **Horizon offset** (lowers the horizon line for cameras on hills or aircraft, or
hides it behind terrain), **Sky tint** and **Horizon tint** (colour grades overhead and toward the horizon) and
**Solar eclipse**: the share of the Sun's diameter the Moon covers. The disc becomes a real crescent and the light
and sky dim with the covered area; at 1 (totality) the sky turns to twilight with an orange glow all round the
horizon, the brightest stars come out and a pearly corona surrounds the black disc.

**Moon** - phase, elevation and azimuth (Artistic only; Earth mode computes them), lamp strength, size.
*Moon size 1.5-3* gives the familiar "big moon" photograph look.

**Stars** - brightness, limiting magnitude, Milky Way strength, faint-star density, seed, star map resolution.
2K is soft; 4K is the default; 8K is sharp and needs about 2 GB of RAM while baking.

**Clouds** - a list of up to three layers. Each: kind (loads that kind's typical numbers), base altitude, thickness,
**coverage** (= fraction of the sky filled), density (extinction per metre; real cumulus is 0.03-0.1), feature
size, detail, ice forward scatter (cirrus only; water clouds use their droplets' Mie phase), wind speed and
direction (cirrus streaks and altocumulus rows line up with the wind), seed, radius, edge fade, *Follow camera*.
**Storm cell** piles cloud up in one place: set a strength, then the bearing and distance from the world origin and
a radius. The cell drifts with the wind; aim your camera at it for a single towering cloud. **Evolution** makes
cloud grow and dissolve in place as well as drift (1 = real cumulus, which turns over in about 15 minutes; 0 =
frozen shapes); it costs no render time. **Lightning** sets flashes per minute lighting the layer from inside (in
the storm cell when there is one), each flash a few return strokes a few frames apart, keyed over the scene's frame
range; *Flash brightness* scales them. *Relative cost* is a rough guide.
**2D Cloud Deck** - a high cloud layer drawn in the sky: no render cost, no shadows, ideal for cirrus.

**Fog and Haze** - *Haze* (a dome around the camera), *Domain* (a fog bank you place) or *Both*. Visibility in metres
with its WMO class, scale height, base altitude, anisotropy, patchiness, absorption (smog), colour.

**Readout** - sun elevation and azimuth, phase of day, sun lamp strength, air mass, moon phase and illumination,
limiting magnitude, sunrise and sunset in Earth mode.

**Preset Files** - export your current atmosphere as JSON; import one.

## 3. Recipes

**A real night sky.** Preset *Starry night*; Earth mode; enter your latitude/longitude/date; set the time after
astronomical twilight (the readout says "night"). Face the camera toward the Milky Way. Render with AgX and *Auto
exposure* on; adjust *Stars* brightness 1-2.

**Golden-hour landscape.** Preset *Golden hour*. Aim the camera within 60 degrees of the sun azimuth.
Raise *Aerosols* for redder light. Clouds at this hour are lit by the cloud sun, which is brighter and less red than
the light on the ground, so they glow gold while the land is already dim; the 2D deck picks up the same warmth.

**A day in 10 seconds.** Earth mode, *Animate time* on, *Hours per second* = 2.4 for 24 hours in 10 s at any frame
rate. The add-on must be enabled when you render on another machine.

**Ground fog in a valley.** Preset *Valley fog bank*; move and scale `AtmosFX Fog Domain` to cover the valley (Z is
managed from *Base altitude*).

**Overcast.** Preset *Overcast*, or raise *Coverage* of a stratus layer to 0.95+. Auto exposure lifts the darker
scene about two stops, as a camera would.

**A storm on the horizon.** Preset *Storm cell*: one cumulonimbus 22 km to the north-north-east. Point the camera at
bearing 20 degrees, slightly up. Move it with the layer's *Cell bearing* and *Cell distance*; keep the sun behind or
beside the camera for lit towers and a dark base.

## 4. Rendering

**Always raise the camera's Clip End** above the radius of your clouds and haze: a domain beyond the clip distance
vanishes silently. The main panel warns and fixes it.

**Cycles** (recommended). Volume bounces per tier: Draft 8, Preview 32, Final 96. Clouds get their brightness from
real bounces, so Draft clouds look greyer (a small emission fill compensates). Measured on an Apple M-series GPU at
480x270 and 32 samples, Preview: clear and twilight presets 1-3 s, fair-weather cumulus ~50 s, big cumulus ~85 s;
CPU rendering is many times slower. Use the GPU and denoising for real work. If *Set render* is on, AtmosFX sets the
volume bounces (and raises *Max Bounces* if it is lower), plus the step rate and max steps used by *Volume > Biased*.

**EEVEE.** Volume range is the froxel range: AtmosFX sets `volumetric_end` to the largest domain radius (capped at 60 km),
but fog and clouds farther than the froxel grid resolves will look coarse. The EEVEE path renders AtmosFX presets
headlessly on Blender 5.2 LTS, but volume detail is coarser than Cycles and the result has not been
compared frame-for-frame.

**Colour management.** Brightness assumes AgX (Blender's default view). With *Auto exposure* off, daylight is right at
0 EV and night needs several stops more. Stars and the Milky Way fade at dark exposures by design; raise *Star
brightness* instead of exposure.

**Viewport.** *Live update* recomputes everything on each edit: the star bake is cached, so only seed, density and
resolution changes rebake (a fraction of a second at 4K). Turn *Live update* off while typing many values.

## 5. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Clouds or haze missing in the render | Camera Clip End too small. Use *Fix Camera Clipping*. |
| Haze render is slow | Heterogeneous bounded volume; lower the *Quality* tier, reduce the haze radius by lowering visibility, or use the 2D deck. |
| Sky is black with fog on | You turned fog on in your own world volume. AtmosFX never does that; delete the world volume (Cycles blanks the frame for infinite volumes). |
| Stars missing in daylight/twilight | By design: the limiting magnitude falls with the sun's elevation. Check the *Readout*. |
| Moon not visible | Elevation below the horizon, or *Moon* off. In Earth mode it follows the real moon: check the phase in the readout. |
| Everything is too bright or too dark | Use the *Bias* next to *Auto exposure*, or turn it off and set Exposure yourself. |
| Night renders black | *Auto exposure* is off; turn it on or raise Exposure by 5-8 stops. |
| Clouds look grey on their sunlit side | Quality is Draft (8 bounces), or *Density* is far below real values (0.03-0.1 for water clouds): thin clouds let light pass through instead of reflecting it. Use Preview or Final. |
| Vertical streaks in fog or clouds | Two volume objects share a face. AtmosFX keeps its own apart; check volumes of your own that touch a cloud base. |
| File opens with missing star map | The image is packed; if you unpacked it, press the rebuild button. |
| Preset import fails | Look at the message: the file is validated against the schema; a newer schema number is refused. |

## 6. Python

```python
import bpy
from atmosfx.core import presets
from atmosfx.ui import state
from atmosfx.scene import apply

scene = bpy.context.scene
state.write_preset(scene.atmosfx, presets.get("golden_hour"))
apply.create(scene)
scene.atmosfx.time_mode = "EARTH"; scene.atmosfx.latitude = 28.6; scene.atmosfx.longitude = 77.2
```

See `examples/quickstart.py` and `examples/day_timelapse.py`.
