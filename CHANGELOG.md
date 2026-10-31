# Changelog

## Unreleased

- Verified EEVEE headlessly on macOS arm64 with Blender 5.0.1; added four opt-in EEVEE render checks.
- Added a CI workflow and excluded `.DS_Store`/`Thumbs.db` from the extension zip.
- Documented the missing Blender 5.2.1 wheel and the current verification status.

## 0.1.0 - first release

- Pure-Python core: atmospheric optics and photometry, Sun and Moon ephemeris (Meeus), sidereal time, precession,
  galactic frame, 119-star catalogue and star-map baker, cloud model, preset schema, sky-view derivation.
- Blender layer: sky node group (Nishita sky, stars, Milky Way, moon with phase, sun disc, 2D cloud deck, ground),
  volumetric cloud group, fog group, haze dome and fog bank objects, sun/moon lamps, light-linked cloud sun,
  quality tiers for Cycles and EEVEE, time animation handler, camera clip warning.
- UI: sidebar panels with readout, preset load/export/import, cloud layer list.
- 28 presets; docs; 97 unit tests and 22 headless Blender checks on Blender 5.0.1.

Known limitations are listed in the README under "Verification status".
