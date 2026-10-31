# Changelog

## Unreleased

- Verified Blender 5.2.1 LTS and EEVEE headlessly on macOS arm64; the fast suite and all Cycles/EEVEE render checks
  pass on both 5.0.1 and 5.2.1.
- Added four opt-in EEVEE render checks.
- Added a CI matrix for 5.0.1 (Python 3.11) and 5.2.1 (Python 3.13, Blender wheel archive).
- Excluded `.DS_Store`/`Thumbs.db` from the extension zip; documented the current verification status.

## 0.1.0 - first release

- Pure-Python core: atmospheric optics and photometry, Sun and Moon ephemeris (Meeus), sidereal time, precession,
  galactic frame, 119-star catalogue and star-map baker, cloud model, preset schema, sky-view derivation.
- Blender layer: sky node group (Nishita sky, stars, Milky Way, moon with phase, sun disc, 2D cloud deck, ground),
  volumetric cloud group, fog group, haze dome and fog bank objects, sun/moon lamps, light-linked cloud sun,
  quality tiers for Cycles and EEVEE, time animation handler, camera clip warning.
- UI: sidebar panels with readout, preset load/export/import, cloud layer list.
- 28 presets; docs; 97 unit tests and 22 headless Blender checks on Blender 5.0.1.

Known limitations are listed in the README under "Verification status".
