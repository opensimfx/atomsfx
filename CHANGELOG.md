# Changelog

## Unreleased

- The extension zip now contains the GPL-3.0 `LICENSE`.
- Requires Blender 5.2 LTS (was 5.0); CI runs the test suites on the 5.2 wheel on Linux, Windows and macOS.

Realism and look work toward 1.0, measured on Blender 5.2.3 with a new look bench (`tools/render_look.py`).

- **Art direction** (Sky and Sun, neutral by default): *Sun halo* and *Halo size*, *Horizon offset*, *Sky tint* and
  *Horizon tint*.
- **Solar eclipse**: the Moon covers the share of the Sun's diameter you set; the disc becomes a crescent, the sun
  lamp and sky dim with the uncovered area (circle-overlap geometry); totality brings twilight, an orange glow all
  round the horizon, the brightest stars and the corona.
- **Evolution** (per cloud layer): cloud grows and dissolves in place as well as drifting with the wind (1 = real
  cumulus, ~15 min per feature). Free: the noise space scrolls up through the layer (a 4D noise cost 16 % more).
- **Lightning** (per cloud layer): flashes per minute that light the cloud from inside, in the storm cell when
  there is one; each flash is 1-4 return strokes 40-120 ms apart with an afterglow, seeded so renders repeat.

- **Clouds rebuilt** for Blender 5's null-scattering renderer:
  - Shape after Schneider (2015): a 2D weather field (cloud comes in groups and gaps), Perlin noise blended with
    inverted Worley noise (cauliflower billows), a sharp flat base, tops that narrow into domes, wispy eroded
    bases, and a downwind *fibre* stretch (cirrus streaks, rows of altocumulus).
  - Physical densities from liquid water content and droplet size (cumulus 0.05 /m, was 0.02): the old values
    were calibrated for the biased ray marcher and now rendered clouds that light passed straight through.
  - Light: the droplets' Mie phase (silver linings) blended with a soft lobe, so light diffuses out of thick
    cloud; real volume bounces (Draft 8, Preview 32, Final 96) instead of the emission fill, which added energy in
    proportion to optical depth (a sunset altocumulus deck lit the ground orange). Draft keeps a small fill.
  - Coverage recalibrated per kind (measured field statistics), and edge softness per kind (crisp cumulus, soft
    stratus).
  - **Storm cell**: any layer can pile cloud up in a disc at a bearing and distance, anchored in world space and
    drifting with the wind. The *Storm cell* preset uses it for one towering cumulonimbus.
- **Aerial perspective**: the haze dome now carries clean air (Rayleigh scattering, blue-weighted, 8 km scale
  height) as well as aerosol, so distant ridges turn blue before they grey. *Visibility* still describes the whole
  atmosphere (aerosol = Koschmieder total minus air). The dome reaches at least 40 km and ends under the lowest cloud
  base.
- **Haze no longer whites out**: the fog's multiple-scatter emission only applies where the fog is optically thick
  (none for haze, full for dense fog), and only to camera rays.
- **Auto exposure** (on by default, with a bias): sets *Exposure* from the scene's light so blue hour, moonlit and
  starry nights render legible instead of black, and golden hour holds its sky. Real illuminance from the U.S.
  Naval Observatory twilight table, compressed to a cinematic key (night ~3-5 stops under noon, not 18).
- Moonlit sky is the day sky's Rayleigh blue instead of moon-tinted brown; moonlight is graded cooler.
- Fixed: a cloud layer inside the haze dome lost its cloud sun (Cycles light linking does not separate overlapping
  volumes) and rendered grey; volumes never share a face any more (coincident faces streaked and cost time).
- Presets retuned: *Clear morning* is clearer, *Storm front* became *Storm cell*, cirrus layers reach 40 km.

## 0.3.0 - alpha (GitHub release v0.3.0-alpha.1, 2026-11-16)

- The README shows three 960 x 540 renders like the other OpenSimFX add-ons (golden hour, starry night, sunset
  clouds; `tools/render_preview.py` now defaults to 960 px wide);
  the other 17 gallery renders are kept locally, not in the repository.
- `docs/REFERENCES.md` keeps the licensing statement and the scientific sources; working research notes are no
  longer published.
- Repository layout shared by the four OpenSimFX add-ons (CONTRIBUTING.md, Repository conventions):
  `docs/TESTING.md` is now `docs/DEVELOPMENT.md` (suites, adding a test) and the new `docs/VALIDATION.md` (what
  the checks guarantee, measurements, what is not covered), so every add-on has the same nine docs; the README
  links them in the shared order and shows the add-on icon (`.github/logo.png`).
- UI follows the shared OpenSimFX conventions (`docs/UI_STYLE.md`, identical in all four add-ons):
  Blender's label-left property layout in every panel, a large *Add* button, *Remove* separated
  at the bottom, and *Live update* / *Set render* on separate rows (the shared row clipped).

## 0.2.0 - alpha (GitHub release 0.2.0-alpha.1)

- Version bumped to 0.2.0 so the add-on matches its release (the first 0.2.0-alpha.1 zip still reported 0.1.0).
- Fixed the manifest website URL (the repository is `atomsfx`).
- Verified Blender 5.2.1 LTS and EEVEE headlessly on macOS arm64; the fast suite and all Cycles/EEVEE render checks
  pass on both 5.0.1 and 5.2.1.
- Added four opt-in EEVEE render checks.
- Added a CI matrix for 5.0.1 (Python 3.11) and 5.2.1 (Python 3.13, Blender wheel archive).
- Excluded `.DS_Store`/`Thumbs.db` from the extension zip; documented the current verification status.
- Cloud look-dev: density-weighted multiple-scatter fill (bright tops, dark blue bases at high sun, warm undersides
  and a backlit forward-scatter halo at low sun), derived from the sun by `physics.cloud_scatter_lighting`.
- The 2D cloud deck now warms at sunset instead of staying white-grey.
- Volume step rate follows a per-layer optical-depth budget (`clouds.step_rate_scale`); thin high layers can use
  coarser steps when no dense layer is present.

## 0.1.0 - first release

- Pure-Python core: atmospheric optics and photometry, Sun and Moon ephemeris (Meeus), sidereal time, precession,
  galactic frame, 119-star catalogue and star-map baker, cloud model, preset schema, sky-view derivation.
- Blender layer: sky node group (Nishita sky, stars, Milky Way, moon with phase, sun disc, 2D cloud deck, ground),
  volumetric cloud group, fog group, haze dome and fog bank objects, sun/moon lamps, light-linked cloud sun,
  quality tiers for Cycles and EEVEE, time animation handler, camera clip warning.
- UI: sidebar panels with readout, preset load/export/import, cloud layer list.
- 28 presets; docs; 97 unit tests and 22 headless Blender checks on Blender 5.0.1.

Known limitations are listed in the README under "Verification status".
