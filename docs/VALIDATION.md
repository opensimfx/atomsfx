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

## The look bench (1.0)

`tools/render_look.py` renders every preset in desktop Blender (5.2.3, Metal GPU, AgX as a user sees it) over a
ring of hills from 1 to 20 km, with the camera at eye height and the horizon in frame (a low sun near the frame
edge, a high sun behind the camera, the moon or south at night, a fog bank seen from a hillside), and writes a
contact sheet. Every look change toward 1.0 was judged on these sheets. Findings that changed the design (details
in SYSTEM_DESIGN 5 and 6):

- the haze emission fill turned a 35 km-visibility day into a milky whiteout: it now applies only to optically thick
  fog (`objects.fog_fill`);
- clouds at the old 0.02 /m rendered grey on their sunlit side even at 128 volume bounces; physical densities
  (0.05 /m) plus the Mie/soft-lobe blend render bright cumulus with shaded bases;
- an emitting cloud deck lit the ground orange at sunset (emission adds energy in proportion to optical depth);
- a cloud layer inside the haze dome lost its light-linked sun; the dome now ends under the cloud base;
- coincident volume faces streaked (and cost 3x the render time);
- a Light Path node in the cloud shader made Metal >20x slower; the fog shader is unaffected;
- night and twilight rendered black at exposure 0: auto exposure, with the sky's irradiance measured on a white
  plane (`skyview.SKY_IRRADIANCE`) and the on-screen key tuned per scene (`physics.CINEMATIC_KEY`);
- overcast needs 32+ volume bounces to light the underside of the deck (12 rendered a storm-dark sky).

The bench is a judgement aid, not a test: no image is compared automatically.

## Not covered

Blender versions other than 5.2 LTS (5.2.1 wheel, 5.2.3 desktop for the look bench); GPU Cycles in CI (the look bench runs on
Metal locally); Windows; EEVEE in CI or on GPU-less machines (opt-in);
EEVEE image quality beyond non-black output (no reference-image comparison); interactive UI drawing; render-farm
animation without the add-on; the visual quality of the presets (judged by eye on the look bench, not compared automatically); long-running memory use; stereo and
panoramic cameras (the sky is direction-based so should work, untested); scene unit scales other than metres (all
lengths are Blender units = metres).
