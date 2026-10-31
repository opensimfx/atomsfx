# User guide

## 1. Basics

Everything is in the 3D Viewport sidebar (**N**) under **AtmosFX**. Pick a preset, press **Add Atmosphere**. AtmosFX
creates:

| Created | What it is |
|---|---|
| `AtmosFX World` | the sky (your previous world is remembered and restored by **Remove Atmosphere**) |
| `AtmosFX Sun`, `AtmosFX Moon` | Sun lamps aimed by the ephemeris |
| `AtmosFX Sun Clouds` | a second sun for cloud layers only (light-linked), when clouds exist |
| `AtmosFX Cloud 1..3` | cylinder volume domains, one per cloud layer |
| `AtmosFX Haze`, `AtmosFX Fog Domain` | haze dome / fog bank when fog is on |
| `AtmosFX Stars <hash>` | the baked star image, packed into the .blend |

All of them live in the `AtmosFX` collection (the light-linking collections are internal). Do not rename them.
Everything is regenerated from the panel settings, so edit the settings, not the objects (you may move cloud and fog
objects in X/Y and scale them; AtmosFX owns their Z and size).

## 2. The panels

**Main** - preset, *Load preset*, rebuild button, **Quality** (Draft / Preview / Final), *Live update*,
*Set render* (let AtmosFX configure volume settings), camera clip warning, remove.

**Time and Place**
- *Artistic*: sun elevation and azimuth by hand. Stars still follow the date and place.
- *Earth*: latitude, longitude, date, local time, UTC offset. *North offset* is the compass bearing your scene's +Y axis
  points to (0 = +Y is north). *Use Current Date and Time* reads this computer's clock.
- *Animate time*: the clock advances with the timeline at *Hours per second*: 1.0 is one simulated hour per second of
  animation (24 hours take 24 s at any frame rate).

**Sky and Sun** - air, aerosols, ozone, viewpoint altitude, sky strength, night glow, *Sun lamp* (on: a lamp lights the
scene and the sky disc is camera-only; off: the disc in the sky lights the scene, noisier), sun strength and size,
ground below the horizon.

**Moon** - phase, elevation and azimuth (Artistic only; Earth mode computes them), lamp strength, size.
*Moon size 1.5-3* gives the familiar "big moon" photograph look.

**Stars** - brightness, limiting magnitude, Milky Way strength, faint-star density, seed, star map resolution.
2K is soft; 4K is the default; 8K is sharp and needs about 2 GB of RAM while baking.

**Clouds** - a list of up to three layers. Each: kind (loads that kind's typical numbers), base altitude, thickness,
**coverage** (= fraction of the sky filled), density, feature size, detail, forward scatter, wind speed and
direction, seed, radius, edge fade, *Follow camera*. *Relative cost* is a rough guide.
**2D Cloud Deck** - a high cloud layer drawn in the sky: no render cost, no shadows, ideal for cirrus.

**Fog and Haze** - *Haze* (a dome around the camera), *Domain* (a fog bank you place) or *Both*. Visibility in metres
with its WMO class, scale height, base altitude, anisotropy, patchiness, absorption (smog), colour.

**Readout** - sun elevation and azimuth, phase of day, sun lamp strength, air mass, moon phase and illumination,
limiting magnitude, sunrise and sunset in Earth mode.

**Preset Files** - export your current atmosphere as JSON; import one.

## 3. Recipes

**A real night sky.** Preset *Starry night*; Earth mode; enter your latitude/longitude/date; set the time after
astronomical twilight (the readout says "night"). Face the camera toward the Milky Way. Render with Filmic/AgX,
exposure 0, and *Stars* brightness 1-2.

**Golden-hour landscape.** Preset *Golden hour*. Aim the camera within 60 degrees of the sun azimuth.
Raise *Aerosols* for redder light. Clouds at this hour are lit by the cloud sun.

**A day in 10 seconds.** Earth mode, *Animate time* on, *Hours per second* = 2.4 for 24 hours in 10 s at any frame
rate. The add-on must be enabled when you render on another machine.

**Ground fog in a valley.** Preset *Valley fog bank*; move and scale `AtmosFX Fog Domain` to cover the valley (Z is
managed from *Base altitude*).

**Overcast.** Preset *Overcast*, or raise *Coverage* of a stratus layer to 0.95+. Lower *Sun strength* if you want
flatter light; the sky:sun balance changes only when you do.

## 4. Rendering

**Always raise the camera's Clip End** above the radius of your clouds and haze: a domain beyond the clip distance
vanishes silently. The main panel warns and fixes it.

**Cycles** (recommended). Draft gives a quick look; Final turns on 12 volume bounces. On one CPU core, a 640x360
frame with one cloud layer is minutes at 12 samples; use a GPU and denoising for real work. If *Set render* is on,
AtmosFX sets `volume_step_rate`, `volume_max_steps` and `volume_bounces` per tier.

**EEVEE.** Volume range is the froxel range: AtmosFX sets `volumetric_end` to the largest domain radius (capped at 60 km),
but fog and clouds farther than the froxel grid resolves will look coarse. The EEVEE path renders AtmosFX presets
headlessly on Blender 5.0.1 and 5.2.1 LTS, but volume detail is coarser than Cycles and the result has not been
compared frame-for-frame.

**Colour management.** The brightness anchors assume AgX or Filmic at 0 EV. Stars and the Milky Way vanish at very
dark exposures by design; raise *Star brightness* instead of exposure.

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
| Everything is too bright | The anchors assume AgX/Filmic at 0 EV. Lower *Sky strength* and *Sun strength*, not exposure, for artistic changes. |
| Clouds look grey with dark bases | Expected in 0.1 (see the README's known limitations). Lower density, raise coverage gaps, or use the 2D deck. |
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
