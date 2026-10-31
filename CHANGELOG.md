# Changelog

## Unreleased

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
