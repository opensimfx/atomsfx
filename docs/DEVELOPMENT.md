# Development and Testing

Set up, run and extend the test suites. Build the extension with `python tools/build_extension.py`
(`dist/atmosfx-<version>.zip`); see also [CONTRIBUTING.md](../CONTRIBUTING.md).

## Suites

| Suite | Needs | Count | What it checks |
|---|---|---|---|
| `tests/test_physics.py` | Python | 25 | Koschmieder, air mass, Rayleigh, sun colour and strength (also with altitude), blackbody, star colours, Allen moon photometry, limiting magnitude, twilight names |
| `tests/test_astro.py` | Python | 18 | Julian date, GMST, Sun (Meeus 25.a), Moon (Meeus 47.a), phases at real syzygies, sunrise/sunset, refraction, precession, Euler convention, galactic frame, artistic moon geometry |
| `tests/test_stars.py` | Python, numpy | 18 | catalogue separations and integrity, measured equirect convention, PSF/threshold maths, bake placement, determinism, Milky Way weighting |
| `tests/test_clouds.py` | Python | 8 | kinds, quantile coverage mapping, wind vector, seeds, socket values, height profile, cost, step-rate budget |
| `tests/test_presets.py` | Python | 10 | every shipped preset validates, JSON and file round trips, schema refusal, derive, physical sanity, generator parity |
| `tests/test_skyview.py` | Python | 21 | the full parameters-to-values chain: lamps, discs, stars, moon geometry, Earth vs Artistic, animation clock, north offset, cloud sun, multiple-scatter cloud lighting |
| `tests/test_identity.py` | Python | 2 | state hash stability |
| `tests/blender_smoke.py` | `bpy` 5.0.1 / 5.2.1 | 19 fast | register and create, all 28 presets apply with consistent objects, layer operators, fog modes, time driver, handler, lamp orientation, node property values, quality tiers, camera clip fix, preset operators, save/reload, remove/cleanup, refresh, star image cache, cloud lighting sockets |
| same, `ATMOSFX_RENDER_TESTS=1` | `bpy`, one CPU is enough | +4 renders | star alignment (< 0.3 degree), sun-disc alignment (< 0.3 degree), cloud coverage vs filled area, haze keeps the sky visible |
| same, `ATMOSFX_EEVEE_TESTS=1` | `bpy`, a GPU/display | +4 renders | clear sky, sunset clouds, dense fog and stars render non-black in EEVEE; the night sky stays dark and contains bright star pixels |
| `tests/test_blender.py` | `bpy` | 1 | runs the fast Blender suite from pytest (skipped without `bpy`) |

Run: `python -m pytest` (everything available) - `python tests/blender_smoke.py` -
`ATMOSFX_RENDER_TESTS=1 python tests/blender_smoke.py` - `ATMOSFX_EEVEE_TESTS=1 python tests/blender_smoke.py`.
The `bpy` wheel needs Python 3.11 for Blender 5.0.1 or Python 3.13 for 5.2.1. PyPI hosts 5.0.1; newer wheels are at
<https://download.blender.org/pypi/>:

```bash
uv venv --python 3.11 venv311 && uv pip install --python venv311/bin/python bpy==5.0.1 pytest numpy
uv venv --python 3.13 venv313 && uv pip install --python venv313/bin/python bpy==5.2.1 \
    --extra-index-url https://download.blender.org/pypi/ pytest numpy
```

CI (`.github/workflows/ci.yml`) runs the unit suites and the fast Blender suite on 5.0.1 and 5.2.1, regenerates
presets and docs and fails on drift (5.0.1), builds the zip, and uploads it as an artifact.

What the render checks guarantee, the measurements made while building and what is not covered are in
[VALIDATION.md](VALIDATION.md).

## Adding a test

Physics or derived values: a pure test in `tests/`. Anything that depends on Blender's behaviour: a check in
`blender_smoke.py`, and record the measurement in SYSTEM_DESIGN section 6 if it established a convention.
