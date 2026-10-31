# Physics

Every formula here is implemented in `atmosfx/core/` and covered by `tests/`. Source algorithms are cited; the code
is written from the published formulae, not copied from any product.

## 1. Time and coordinates

- **Julian date** from a civil date (Meeus ch. 7). Local time plus a UTC offset is converted to UTC first; hours
  beyond 24 or below 0 roll the date.
- **Sidereal time**: GMST = 280.46061837 + 360.98564736629 (JD - 2451545) + 0.000387933 T^2 - T^3/38710000 degrees
  (Meeus 12.4); local = GMST + east longitude. Checked against Meeus example 12.a (197.693195 degrees).
- **Horizon coordinates** from hour angle H = LST - RA, declination d, latitude p:
  `E = -cos d sin H`, `N = -sin p cos d cos H + cos p sin d`, `U = sin p sin d + cos p cos d cos H`.
  Azimuth is measured from north through east; the scene frame has +X east and +Y north, rotated about Z by the
  **North offset** (the compass bearing of scene +Y).
- **Refraction** (Bennett 1982): `R[arcmin] = 1 / tan(h + 7.31 / (h + 4.4))`, scaled for pressure and temperature;
  0.57 degrees at the horizon. Applied to the Sun and Moon.
- **Precession** (IAU 1976 angles zeta, z, theta) takes J2000 star coordinates to the equinox of date. Nutation and
  proper motion are ignored (< 0.01 degree and < 0.1 arcsecond per year for these stars).

## 2. Sun

Meeus ch. 25 low-accuracy theory, with nutation and aberration corrections to the apparent longitude.
Checked against example 25.a: RA and Dec within 0.01 degree. The angular diameter is 0.5334 degrees divided by the
distance in AU. Sunrise/sunset use the standard altitude -0.833 degrees; checked for the equator on the equinox and
London on the solstice to within 6 minutes.

## 3. Moon

Meeus ch. 47 with the 32 largest longitude/distance terms and 30 latitude terms plus the three additive terms.
Checked against example 47.a: longitude 133.1627 (reference 133.1627), latitude -3.2286 (-3.2291), distance
368428 km (368409.7), RA 134.6841 (134.6885), Dec 13.7701 (13.7684): **errors below 0.005 degree**. Topocentric
parallax is applied to first order.

**Phase** (Meeus ch. 48): the phase angle `i = atan2(R sin psi, D - R cos psi)` with psi the geocentric elongation;
illuminated fraction `k = (1 + cos i) / 2`. Waxing/waning from the ecliptic longitude difference.
New and full moon were checked at the instants of the 11 January and 25 January 2024 syzygies.

**In the shader** the Moon is a unit sphere: for a pixel at unit-disc coordinates `u` (tangent plane) the surface normal
toward the observer is `n = u - m sqrt(1 - |u|^2)`; the light direction is the *true* direction to the Sun. Lit =
`max(n . L, 0)`. That reproduces the terminator and the orientation of the bright limb; the limb orientation render
test passes. Surface albedo is procedural noise (no lunar texture is shipped).

## 4. Stars

- **Catalogue**: 119 stars, V mag -1.46 to 3.71, J2000 RA/Dec, B-V. Entered by hand; validated by separations (Orion's
  belt 2.7, Pointers 5.4, Southern Cross 6.0, Vega-Altair 34.2 degrees, ...). Not machine-verified against Hipparcos.
- **Synthetic field**: counts follow the observed law `N(<m) = 171 * 3.1^(m - 3)` (Bright Star Catalogue counts;
  ~9000 stars to magnitude 6.5), magnitudes drawn by inverse CDF between 2.8 and the limit, positions uniform on
  the sphere with a rejection weight `(1 + 2.5 exp(-(b/15)^2)) / 3.5` that concentrates them toward the galactic plane.
  The generator is seeded and deterministic.
- **Brightness**: Pogson `flux = 10^(-0.4 m)`. Each star is a Gaussian point-spread of width
  `sigma = 0.75 + 0.22 max(0, 3 - m)` pixels (cap 2.2), so bright stars read bigger. Peak value =
  flux relative to a magnitude-6.5 star times `(0.75 / sigma)^2`.
- **Limiting magnitude** is a luminance threshold in the shader: `threshold = 0.6 * 10^(0.4 (6.5 - m_lim))`.
- **Colour**: B-V to temperature (Ballesteros 2012) `T = 4600 (1/(0.92 BV + 1.7) + 1/(0.92 BV + 0.62))`, blackbody
  chromaticity (Kim et al. 2002) to linear sRGB, desaturated 65 % toward white (night vision is nearly achromatic).
- **Milky Way** (procedural): galactic latitude Gaussian sigma 0.22 rad, bulge sigma 0.75 rad in longitude and 0.38 in
  latitude, dust lanes where a 4 cycles/rad noise exceeds 0.50-0.64. The galactic frame is the Hipparcos J2000
  rotation matrix; the galactic centre maps to (1, 0, 0) and the pole to (0, 0, 1) in the tests.
- **Visibility**: `limiting_magnitude(sun_el, moon_el, moon_fraction, base, clouds)`: climbs from -4 (day) to `base`
  over 0 to -18 degrees of sun elevation with a 0.8 power ease, loses up to 2.5 mag to a high full moon
  `2.5 f sin(alt)^0.7`, and 3 mag at full cloud. An empirical model, not a radiative-transfer result.

## 5. Atmosphere and the sun lamp

- **Air mass** (Kasten and Young 1989): `m = 1 / (sin h + 0.50572 (6.07995 + h)^-1.6364)`, 38 at the horizon.
- **Rayleigh optical depth** at sea level: `tau_R(l) = 0.008569 l^-4 (1 + 0.0113 l^-2 + 0.00013 l^-4)` (l in um),
  0.0973 at 550 nm.
- **Aerosol** (Angstrom): `tau_a(l) = beta l^-1.3` with `beta = 0.05 x` the *Aerosols* multiplier.
- **Ozone** (Chappuis band): small fixed optical depths per RGB channel, unchanged with altitude.
- **Transmittance** per channel at RGB wavelengths 640/550/460 nm: `exp(-tau m)`. Above an altitude `z`, Rayleigh and
  aerosol depths are scaled by `exp(-z/8000)` and `exp(-z/1200)`: this is why the cloud sun is brighter and less red.
- **Lamp strength** = anchor x (luminance-weighted transmittance at the elevation / the same at 90 degrees).
  **Lamp colour** = transmittance ratio to the zenith case, normalised (a daylight-white-balanced camera: noon sun
  is neutral, 10 degrees is (1, 0.69, 0.40), 5 degrees (1, 0.47, 0.15), 2 degrees (1, 0.22, 0.02)).
- **Disc radiance** = strength / solid angle (`pi r^2`): 44 000 for a 3.0 lamp, so it saturates like a real sun.

## 6. Moon photometry

Allen (1976): `m(alpha) = -12.73 + 0.026 |alpha| + 4e-9 alpha^4`; illuminance `10^(-0.4 (m + 14.18))` lux
(0.26 lux above the atmosphere, 0.20 at the zenith after extinction; the same formula gives 1.06e5 lux for the Sun's magnitude -26.74, a 6 % check). Extinction `exp(-0.3 m_air)`.
The lamp strength is `anchor x E(phase, elevation) / E(full, zenith)`. A *physical* anchor (about 1e-5 in Blender units)
would need 18 stops of exposure compensation; the default 0.12 is artistic. The lamp is faded out as the Sun
rises (`smoothstep(3, -5, sun_el)`) because the artistic anchor otherwise rivals the Sun at dusk.

## 7. Visibility, fog and haze

Koschmieder: `V = -ln(eps) / sigma_t`, with the WMO contrast threshold `eps = 0.02`, so `sigma_t = 3.912 / V`
(1 km -> 0.003912 1/m; the test checks that transmittance over V is exactly 2 %). The density falls off as
`exp(-(z - base)/H)`. Classes: dense fog < 50 m, thick < 200 m, moderate < 500 m, light < 1 km, mist < 2 km,
haze < 5 km, light haze < 10 km, clear < 20 km, very clear < 50 km, exceptionally clear beyond.
The haze dome radius is `1.4 V` (transmittance 0.3 % at the edge).

## 8. Clouds

- **Extinction** `sigma_t` in 1/m is the peak density; kind defaults range from 0.003 (cirrus) to 0.030
  (cumulonimbus). Optical depth through a layer is roughly `sigma_t x thickness x fill`; real cumulus is 5-50.
  Render defaults sit in the low half of that range because a path tracer with a few volume bounces darkens thick
  clouds (measured: 0.05 /m cumulus rendered as dark storm cloud; 0.02 /m reads as cumulus).
- **Phase**: two Henyey-Greenstein lobes, forward `g` 0.7-0.85 and a back lobe -0.25 at 25 %.
- **Coverage**: quantile of the normal shape field (see SYSTEM_DESIGN 5.4).
- **Wind** `v` (m/s) shifts the noise lookup by `-v t freq`, with `t = (frame - 1)/fps` seconds.
- **Genera** altitude/thickness follow WMO levels for mid-latitudes (`physics.CLOUD_TYPE_ALTITUDES_M`).

## 9. Accuracy summary

| Quantity | Accuracy | Basis |
|---|---|---|
| Sun position | ~0.01 degree | Meeus 25.a |
| Moon position | < 0.005 degree on the worked example | Meeus 47.a |
| Sidereal time | 1e-4 degree | Meeus 12.a |
| Star alignment in a render | 0.05-0.08 degree | Cycles render check |
| Sun disc alignment in a render | 0.09 degree | Cycles render check |
| Moon limb orientation | direction agrees (component error 0.17) | Cycles render check |
| Sunrise/sunset | within ~6 minutes | two reference places |
| Absolute brightness | artistic | section 6 and SYSTEM_DESIGN 7 |

Not modelled: planets, aurora, airglow variation, aerial perspective colour shift beyond single-colour fog, planet
curvature, cloud-to-cloud shadows between layers beyond what the path tracer does, lunar libration.
