# Changelog

## Unreleased

- The README shows three 960 x 540 renders like the other OpenSimFX add-ons (golden hour, starry night, sunset
  clouds; `tools/render_preview.py` now defaults to 960 px wide);
  the other 17 gallery renders are kept locally, not in the repository.
- Notes about the third-party add-ons that informed the feature list moved out of `docs/REFERENCES.md` into a
  local, ignored `private/` folder; the published references keep the licensing statement and the scientific
  sources.
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
