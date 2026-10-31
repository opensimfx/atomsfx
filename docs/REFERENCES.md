# References, research and licensing

## 1. What informed the feature list

The brief was a sky/atmosphere add-on in the OpenSimFX family covering skies, stars, clouds and fog. Four sources were
studied for *what such a tool should offer*:

- **Pure-Sky Pro** (feature text supplied with the brief): procedural sky with volumetric clouds and moonlight,
  hybrid HDRI blending, cloud presets (cumulus, cumulonimbus, altocumulus), render modes, clouds that cast shadows,
  sky/cloud/fog preset libraries with export and import, mesh-to-cloud, tips about presets and preview quality.
- **PlanetSet** (documentation, `planetset-docs.readthedocs.io`): atmosphere driven by latitude/longitude/date/time;
  cloud layers of several types (simple, warped, a 2D cirrus layer, an exponential mist volume with altitude
  controls, and a "gobo" layer that only casts shadows).
- **Physical Starlight and Atmosphere** and **Physical Atmosphere 2** (documentation pages and the supplied
  packages): time and place driven sun, moon and stars, preset-based workflows, and the general shape of an
  extension packaged for Blender 5.x.
- **RainFX / FlowFX / BlastFX** (the sibling OpenSimFX repositories): repository layout, `core/` free of Blender
  imports, a generated preset table, documentation set, extension build script, and the honest "verification
  status" section in the README. AtmosFX follows RainFX most closely.

From these, AtmosFX takes **ideas**: an Earth/Artistic split, a 2D cirrus deck beside volumetric layers, shadow-aware
cloud domains, exportable JSON presets, quality tiers. Each was then specified and implemented from first principles.

## 2. Licensing of the supplied packages - read before reusing anything

The two uploaded archives were inspected for their licence terms and general structure only.

- `physical-starlight-and-atmosphere-1_9_4_vfxMed.zip`: its `LICENSE.md` and manifest declare GPL-3.0-or-later.
- `PhysicalAtmosphere2v309_vfxMed.zip`: the Python files are declared GPL-3.0-or-later, **but its `EULA.md` places the
  shaders, textures, world template and data under a proprietary end-user licence** that does not allow extracting,
  porting or reusing them elsewhere.
- Both file names carry a `_vfxMed` suffix, which suggests copies obtained from a third-party mirror rather than from the
  vendor. Check where your copies came from; this project cannot verify it.

**AtmosFX contains no code, shader, node group, texture, image or data file from either archive.** Its node groups,
star baker, catalogue, noise formulations and presets were written for this project. If you contribute, keep it that way
(CONTRIBUTING.md). GPL-licensed code can legally be reused in a GPL project with attribution, but that was neither needed
nor done.

## 3. Algorithm and data sources (published formulae, implemented from the papers/books)

| Topic | Source |
|---|---|
| Julian date, sidereal time, Sun, Moon, phase, refraction | J. Meeus, *Astronomical Algorithms*, 2nd ed.: ch. 7, 12, 16, 25, 47, 48 |
| Precession | IAU 1976 (Lieske et al.) angles zeta, z, theta |
| Galactic frame | Hipparcos catalogue, ESA SP-1200, vol. 1, section 1.5.3 (rotation matrix) |
| Air mass | Kasten and Young (1989) |
| Rayleigh optical depth | Froehlich and Shaw (1980) form as given by Bodhaine et al. (1999) |
| Aerosol optical depth | Angstrom law; typical turbidity coefficients |
| Moon magnitude | Allen, *Astrophysical Quantities* (1976) |
| Blackbody chromaticity | Kim et al. (2002) cubic spline approximation of the Planckian locus |
| B-V to temperature | Ballesteros (2012) |
| Star-count law | Bright Star Catalogue cumulative counts (about 3.1 per magnitude) |
| Visibility | Koschmieder (1924); WMO 2 % contrast threshold and visibility classes |
| Cloud phase | Henyey and Greenstein (1941), two lobes |
| Sky model | Blender's Sky Texture node (Nishita et al. 1993 family); AtmosFX configures it, it does not reimplement it |
| Node and API behaviour | Blender Python API and manual, plus the measurements listed in SYSTEM_DESIGN section 6 |

### Star catalogue provenance

The 119 stars (`core/stars_data.py`) were entered by hand from published J2000 positions and photometry rounded as
documented there. They are verified only by well-known angular separations in `tests/test_stars.py` and by the render
check that finds each star where the ephemeris puts it. A transcription error smaller than a few arcminutes would not
be caught. Replacing the table with a machine-read Hipparcos subset is on the roadmap.

## 4. Brightness calibration

Display constants (sun 3.0, moon 0.12, sky scale 0.03, star gain 0.08, Milky Way 0.22, moon glow 0.012) were set by
rendering and looking, under Blender 5.0.1 without an OpenColorIO configuration (the `bpy` wheel ships without one), so
previews are tone-mapped with an ACES fit. They have not been checked under AgX/Filmic in an interactive session.
