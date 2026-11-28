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
(1 km -> 0.003912 1/m; the test checks that transmittance over V is exactly 2 %). Classes: dense fog < 50 m,
thick < 200 m, moderate < 500 m, light < 1 km, mist < 2 km, haze < 5 km, light haze < 10 km, clear < 20 km,
very clear < 50 km, exceptionally clear beyond.

The camera-following haze dome holds the two components of real air:

- **Clean air (Rayleigh)**: extinction per channel `beta(l) = tau_R(l) / 8000 m` x *Air*, about
  (6.6, 12.2, 25.3) x 1e-6 /m at sea level, falling off with an 8 km scale height, with Blender's Rayleigh phase.
  Over 20 km it removes 12 % of red and 40 % of blue light, which is why distant ridges turn blue before they turn
  grey (aerial perspective). Only the dome carries air; a local fog bank never adds it twice.
- **Aerosol** (haze, fog, smog, dust): the Koschmieder total minus the clean-air share at 550 nm, so *Visibility*
  describes the whole atmosphere (pure air alone is ~320 km). Falls off as `exp(-(z - base)/H)` and takes the
  fog colour, absorption and Henyey-Greenstein anisotropy.

Dome size: radius `max(1.4 V, 40 km)` (transmittance 0.3 % at 1.4 V; 40 km so ridges 20-30 km away have air to
turn blue in); height `max(5 H, 4 km)` (the profile below 1 %), but it ends 25 m under the lowest cloud base:
haze is the boundary layer, which cumulus bases cap, and Cycles light linking does not separate overlapping
volumes (see SYSTEM_DESIGN 5.4).

**Multiple-scatter fill.** Thick fog lit by a path tracer with a capped bounce count goes dark, so the fog shader
emits an ambient term in proportion to density. Light escapes a medium through its smallest dimension, so the
gain is `tier x smoothstep(1, 8, sigma_t H)` of the *vertical* optical depth: zero for haze (a clear day is ~0.15),
full for dense fog (~15). It is visible to camera rays only (a Light Path gate), so it brightens what is seen
without adding light to the scene.

## 8. Clouds

- **Extinction** from the microphysics (Kokhanovsky 2004): `sigma_t = 3 LWC / (2 rho_w r_eff)`. Kind defaults:
  cumulus 0.05 /m (LWC ~0.33 g/m3, r_eff 10 um), stratocumulus 0.03, stratus 0.025, altocumulus 0.025,
  altostratus 0.01, cumulonimbus 0.07, cirrus 0.003 (ice; optical depth ~3 through 900 m). Optical depth through a
  cumulus is 30-70, as in nature. Earlier versions used 0.02 because Blender's old biased ray marcher
  underestimated optical depth; under the null-scattering renderer of Blender 5 that renders clouds
  "transport-thin": light passes through instead of diffusing back out, and sunlit sides look grey.
- **Phase**: water clouds blend Blender's **Mie** phase for the droplet diameter (`2 r_eff`: 10-30 um by genus; the
  Jendersie and d'Eon 2023 fit for 5-50 um) with a weak-forward Henyey-Greenstein lobe (g 0.4, 60 %). Pure Mie has a
  very sharp forward peak (half of it g ~0.995), so light needs hundreds of bounces to diffuse back out of a thick
  cloud: cumulus stayed grey on its sunlit side even at 128 bounces. The soft lobe plays the role of the
  multiple-scattering octaves used in production (Wrenninge 2010; Hillaire 2016) and lets light diffuse in ~10
  bounces; the Mie share keeps the forward peak, so backlit edges glow (silver linings). Ice clouds (cirrus) use
  Henyey-Greenstein `g` 0.75.
- **Shape** (Schneider 2015, as shader nodes): a 2D weather field sets where cloud can form; the 3D field blends
  fractal Perlin noise with inverted fractal Worley noise (billows); the height profile gives a sharp flat base at
  the condensation level and raises the threshold with height, so lumps narrow into domes; an anvil term spreads
  the top of a cumulonimbus; erosion is wispy at the base and billowy at the top. The noise frame is turned to the
  wind, and a per-genus **fibre** stretches it downwind (cirrus 6: streaks; altocumulus 1.6: rows). A **storm
  cell** adds cover in a disc anchored in world space that drifts with the wind.
- **Coverage**: the (1 - coverage) quantile of the shape field at mid-height, from each kind's measured mean and
  standard deviation (see SYSTEM_DESIGN 5.5). Edge softness is a multiple of that deviation: crisp cumulus
  (0.12 sd), soft stratus (0.8 sd).
- **Multiple scattering**: real volume bounces (32 in Preview, 96 in Final; cheap, because most paths leave early:
  overcast at 12/32/64 bounces took 21/31/37 s, and only 32+ lit the underside of a stratus deck). Draft (8) adds the
  display-calibrated emission of `physics.cloud_scatter_lighting`; Preview and Final do not, because a
  non-absorbing, forward-scattering cloud lets every emitted photon escape, so emission adds energy in proportion
  to optical depth (an emitting altocumulus deck lit the ground orange at sunset).
- **Wind** `v` (m/s) shifts the noise lookup by `-v t freq`, with `t = (frame - 1)/fps` seconds.
- **Genera** altitude/thickness follow WMO levels for mid-latitudes (`physics.CLOUD_TYPE_ALTITUDES_M`).

### Evolution and lightning

- **Evolution** (modelled): the noise space scrolls up by `Evolution / 900 s` feature sizes per second, so features
  rise through the height profile, swell and dissolve; a fair-weather cumulus cell lives 10-20 minutes.
- **Lightning** (cited timing: Rakov and Uman 2003; modelled light): flash starts are a Poisson process at the set
  rate; each flash has 1-4 return strokes 40-120 ms apart, the first the brightest, each followed by a one-frame
  afterglow (30 %). A stroke is volume emission proportional to the cloud's extinction with a Gaussian falloff
  (0.35 x the layer's depth, 500-3000 m) around a point at 25-65 % of the layer's depth, so the cloud lights from
  inside and real bounces carry the light on. Positions sit in the storm cell (drifting with it) or the inner
  layer.

## 9. Exposure

Real light spans ~28 stops from noon (~120 000 lux) to starlight (~0.0007 lux). AtmosFX keeps physical ratios in
the day and compresses the night (the moon lamp anchor is artistic, section 6), and **auto exposure** sets
*Color Management > Exposure* so every scene renders at a cinematic brightness:

- Real illuminance: the direct beam from the transmittance model plus a diffuse sky term (730 lux at sunset,
  ~20 000 with a high sun); below the horizon the U.S. Naval Observatory twilight values (Bond and Henderson 1963):
  3.4 lux at the end of civil twilight, 0.008 at the end of nautical, 0.0007 starlight. Plus the Moon (section 6).
- Rendered irradiance: sun lamp x sin(elevation), the AtmosFX sky's measured irradiance (a white plane lit by the
  world only, Blender 5.2.3; 0.47 at noon, 0.041 at sunset, 0.0015 night-glow floor), moon lamp, and light bounced
  down by sunlit clouds. Sky light counts three times, because the sky is usually in frame: a sky-lit scene
  (twilight, moonless night) is exposed for the sky, not for the dark ground.
- Exposure = `log2(noon / rendered) - key(real)`, where the key is how many stops darker than noon the scene
  should look on screen: golden hour 1.1, sunset 1.3, civil twilight 1.9, blue hour 2.4, full moon 3.2,
  starlight 5 (tuned on the look bench). Clamped to -3..+10; *Exposure bias* adds to it.

### Solar eclipse

Magnitude m is the share of the Sun's diameter the Moon covers (Moon/Sun radius ratio k = 1.03). The centres
are d = 1 + k - 2m solar radii apart, and the uncovered share of the disc is 1 - (circle-overlap area) / pi
(limb darkening ignored); the sun lamp and the cloud sun scale by it, the sky by it down to a totality floor.
Physically the zenith at totality falls to ~1e-4 of daylight and the corona is ~1e-6 of the photosphere, but
AtmosFX compresses night (exposure caps at 10, the moon is boosted ~2e4), so totality is placed on that night
scale: the sky dims to 5e-3 (twilight), the horizon keeps an orange glow (5 % of the day sky), stars to
magnitude 3 come out, and the corona (radiance ~ rho^-6 beyond the limb, with streamers) appears once the
photosphere is fully covered (m > 0.985). The Moon's disc shows the colour of the sky in front of it, as it does.

## 10. Accuracy summary

| Quantity | Accuracy | Basis |
|---|---|---|
| Sun position | ~0.01 degree | Meeus 25.a |
| Moon position | < 0.005 degree on the worked example | Meeus 47.a |
| Sidereal time | 1e-4 degree | Meeus 12.a |
| Star alignment in a render | 0.05-0.08 degree | Cycles render check |
| Sun disc alignment in a render | 0.09 degree | Cycles render check |
| Moon limb orientation | direction agrees (component error 0.17) | Cycles render check |
| Sunrise/sunset | within ~6 minutes | two reference places |
| Absolute brightness | artistic; ratios physical by day, night compressed | sections 6, 9 and SYSTEM_DESIGN 7 |

Not modelled: planets, aurora, airglow variation, planet curvature, cloud-to-cloud shadows between layers beyond what the path tracer does, lunar libration.
