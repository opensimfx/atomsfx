# Validation

What the checks guarantee, what was measured while building AtmosFX, and what is not covered. The suites and how
to run them are in [DEVELOPMENT.md](DEVELOPMENT.md); sources and calibration in [REFERENCES.md](REFERENCES.md).

## What the render checks guarantee

- A star at its computed position (Sirius, Rigel, Betelgeuse in a January evening at 28.6N 77.2E) is the brightest
  pixel within 0.3 degrees of where the ephemeris says, through the whole chain: RA/Dec, precession, sidereal rotation,
  Euler angles, Mapping node, environment texture. Measured offsets: 0.05-0.08 degrees.
- The sun disc is at the predicted direction (measured 0.09 degrees); the Nishita glow peaks within the measurement noise
  of the same direction.
- On the one moon render inspected, the lit side matches the predicted direction of the sun as seen from the Moon.
- A density slice through the cloud group fills the area the coverage setting asks for (within 0.12).
- Haze does not black out the sky.

## What the EEVEE checks guarantee

Run only with `ATMOSFX_EEVEE_TESTS=1`, because EEVEE needs a GPU/display and CI runners do not have one. Verified on
macOS arm64 with the Blender 5.0.1 and 5.2.1 `bpy` wheels, where the engine identifier is `BLENDER_EEVEE` (the checks
also accept `BLENDER_EEVEE_NEXT`):

- `clear_noon`, `sunset_clouds` and `dense_fog` render to a non-black frame (mean luminance > 0.02, max > 0.2) with
  the quality tier's volume settings applied.
- A starry night renders dark (mean < 0.2) with bright star pixels (max > 0.2) covering at least 0.5 % of the frame.
  Measured on the check render: mean 0.015, 8 % of pixels above 0.05.
- The same four checks pass on 5.2.1; measured results are within sampling variation (the star field is identical:
  mean 0.015, 8 % of pixels above 0.05).
- This is a liveness check, not an image comparison: it catches a black EEVEE frame, a missing engine, or a broken
  world/volume shader, not subtle colour or density differences from Cycles.

## Measurements made while building (and where they are recorded)

All in SYSTEM_DESIGN section 6, with the test that pins each. The experiments that changed the design:
world volume blanks Cycles frames; the default camera clip end removes distant volumes; a generated image regenerates
blank if its colour space is changed after the pixels are set; Blender 5.0's sky radiance is ~30x the scale of a
3.0-strength sun; dense fog path-traces black without ambient emission; filled area vs coverage before and after the
quantile mapping (coverage 0.3 gave 5 % fill and 0.7 gave 91 % before).

## Not covered

Blender versions other than 5.0.1/5.2.1; GPU Cycles; Windows; EEVEE in CI or on GPU-less machines (opt-in);
EEVEE image quality beyond non-black output (no reference-image comparison); interactive UI drawing; render-farm
animation without the add-on; the visual quality of clouds (judged by eye only); long-running memory use; stereo and
panoramic cameras (the sky is direction-based so should work, untested); scene unit scales other than metres (all
lengths are Blender units = metres).
