# Testing

## Suites

| Suite | Needs | Count | What it checks |
|---|---|---|---|
| `tests/test_physics.py` | Python | 25 | Koschmieder, air mass, Rayleigh, sun colour and strength (also with altitude), blackbody, star colours, Allen moon photometry, limiting magnitude, twilight names |
| `tests/test_astro.py` | Python | 18 | Julian date, GMST, Sun (Meeus 25.a), Moon (Meeus 47.a), phases at real syzygies, sunrise/sunset, refraction, precession, Euler convention, galactic frame, artistic moon geometry |
| `tests/test_stars.py` | Python, numpy | 18 | catalogue separations and integrity, measured equirect convention, PSF/threshold maths, bake placement, determinism, Milky Way weighting |
| `tests/test_clouds.py` | Python | 7 | kinds, quantile coverage mapping, wind vector, seeds, socket values, height profile, cost |
| `tests/test_presets.py` | Python | 10 | every shipped preset validates, JSON and file round trips, schema refusal, derive, physical sanity, generator parity |
| `tests/test_skyview.py` | Python | 17 | the full parameters-to-values chain: lamps, discs, stars, moon geometry, Earth vs Artistic, animation clock, north offset, cloud sun |
| `tests/test_identity.py` | Python | 2 | state hash stability |
| `tests/blender_smoke.py` | `bpy` 5.0.1 | 18 fast | register and create, all 28 presets apply with consistent objects, layer operators, fog modes, time driver, handler, lamp orientation, node property values, quality tiers, camera clip fix, preset operators, save/reload, remove/cleanup, refresh, star image cache |
| same, `ATMOSFX_RENDER_TESTS=1` | `bpy`, one CPU is enough | +4 renders | star alignment (< 0.3 degree), sun-disc alignment (< 0.3 degree), cloud coverage vs filled area, haze keeps the sky visible |
| `tests/test_blender.py` | `bpy` | 1 | runs the fast Blender suite from pytest (skipped without `bpy`) |

Run: `python -m pytest` (everything available) - `python tests/blender_smoke.py` -
`ATMOSFX_RENDER_TESTS=1 python tests/blender_smoke.py`.
The `bpy` wheel needs Python 3.11: `uv venv --python 3.11 venv311 && uv pip install --python venv311/bin/python bpy==5.0.1 pytest numpy`.
CI (`.github/workflows/ci.yml`) runs the unit suites, regenerates presets and docs and fails on drift, builds the zip,
and runs the fast Blender suite.

## What the render checks guarantee

- A star at its computed position (Sirius, Rigel, Betelgeuse in a January evening at 28.6N 77.2E) is the brightest
  pixel within 0.3 degrees of where the ephemeris says, through the whole chain: RA/Dec, precession, sidereal rotation,
  Euler angles, Mapping node, environment texture. Measured offsets: 0.05-0.08 degrees.
- The sun disc is at the predicted direction (measured 0.09 degrees); the Nishita glow peaks within the measurement noise
  of the same direction.
- On the one moon render inspected, the lit side matches the predicted direction of the sun as seen from the Moon.
- A density slice through the cloud group fills the area the coverage setting asks for (within 0.12).
- Haze does not black out the sky.

## Measurements made while building (and where they are recorded)

All in SYSTEM_DESIGN section 6, with the test that pins each. The experiments that changed the design:
world volume blanks Cycles frames; the default camera clip end removes distant volumes; a generated image regenerates
blank if its colour space is changed after the pixels are set; Blender 5.0's sky radiance is ~30x the scale of a
3.0-strength sun; dense fog path-traces black without ambient emission; filled area vs coverage before and after the
quantile mapping (coverage 0.3 gave 5 % fill and 0.7 gave 91 % before).

## Not covered

EEVEE rendering; Blender 5.2.1; GPU; Windows/macOS; interactive UI drawing; render-farm animation without the add-on;
the visual quality of clouds (judged by eye only); long-running memory use; stereo and panoramic cameras (the sky is
direction-based so should work, untested); scene unit scales other than metres (all lengths are Blender units = metres).

## Adding a test

Physics or derived values: a pure test in `tests/`. Anything that depends on Blender's behaviour: a check in
`blender_smoke.py`, and record the measurement in SYSTEM_DESIGN section 6 if it established a convention.
