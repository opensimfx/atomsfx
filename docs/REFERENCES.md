# References and Licensing

## 1. Licensing

AtmosFX is GPL-3.0-or-later and original work. Its node groups, star baker, star catalogue, noise formulations and
presets were written for this project; it contains no code, shaders, node groups, textures, images or data from
other add-ons. Contributions must keep it that way (see CONTRIBUTING.md).

## 2. Algorithm and data sources (published formulae, implemented from the papers/books)

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

## 3. Brightness calibration

Display constants (sun 3.0, moon 0.12, sky scale 0.03, star gain 0.08, Milky Way 0.22, moon glow 0.012) were set by
rendering and looking, under Blender 5.0.1 without an OpenColorIO configuration (the `bpy` wheel ships without one), so
previews are tone-mapped with an ACES fit. They have not been checked under AgX/Filmic in an interactive session.
