import math

import pytest

from atmosfx.core import astro, physics, starmap
from atmosfx.core.stars_data import BY_NAME, CATALOG


def sep(a, b):
    return astro.angular_separation_deg(astro.radec_to_vec(BY_NAME[a].ra_deg, BY_NAME[a].dec_deg),
                                        astro.radec_to_vec(BY_NAME[b].ra_deg, BY_NAME[b].dec_deg))


@pytest.mark.parametrize("a,b,expected,tol", [
    ("Dubhe", "Merak", 5.4, 0.1), ("Betelgeuse", "Rigel", 18.5, 0.3), ("Sirius", "Procyon", 25.7, 0.1),
    ("Alnitak", "Mintaka", 2.7, 0.1), ("Vega", "Altair", 34.2, 0.1), ("Vega", "Deneb", 23.8, 0.2),
    ("Acrux", "Gacrux", 6.0, 0.1), ("Arcturus", "Spica", 32.7, 0.2), ("Castor", "Pollux", 4.5, 0.1),
    ("Rigil Kentaurus", "Hadar", 4.4, 0.1)])
def test_known_angular_separations(a, b, expected, tol):
    assert sep(a, b) == pytest.approx(expected, abs=tol)


def test_catalogue_integrity():
    assert len(CATALOG) >= 100 and len(BY_NAME) == len(CATALOG)             # unique names
    for s in CATALOG:
        assert 0 <= s.ra_deg < 360 and -90 <= s.dec_deg <= 90 and -1.6 <= s.mag <= 4.0 and -0.5 <= s.bv <= 2.2
    assert BY_NAME["Sirius"].mag == min(s.mag for s in CATALOG)
    assert BY_NAME["Polaris"].dec_deg == pytest.approx(89.26, abs=0.01)
    assert sum(1 for s in CATALOG if s.mag < 1.5) == 21                      # the 21 first-magnitude stars


def test_equirect_conventions_round_trip():
    # measured on Blender 5.0.1: +X at u=0.5, +Y at u=0.25, -Y at u=0.75, v = 0.5 + asin(z)/pi
    assert starmap.dir_to_equirect((1, 0, 0)) == pytest.approx((0.5, 0.5))
    assert starmap.dir_to_equirect((0, 1, 0)) == pytest.approx((0.25, 0.5))
    assert starmap.dir_to_equirect((0, -1, 0)) == pytest.approx((0.75, 0.5))
    assert starmap.dir_to_equirect((0, 0, 1))[1] == pytest.approx(1.0)
    for d in [(0.3, 0.5, 0.8), (-0.7, 0.1, -0.4), (0.0, -0.9, 0.2)]:
        n = astro.unit(d)
        assert starmap.equirect_to_dir(*starmap.dir_to_equirect(n)) == pytest.approx(n, abs=1e-9)


def test_peak_and_threshold_scale_with_magnitude():
    assert starmap.star_peak(starmap.REF_MAG) == pytest.approx(1.0)
    assert starmap.star_peak(0.0) > 50                                      # magnitude 0 is ~250x a limiting star, softened by its larger PSF
    assert starmap.star_peak(-1.46) > starmap.star_peak(1.0) > starmap.star_peak(4.0) > starmap.star_peak(6.5)
    assert starmap.luminance_threshold(6.5) < starmap.luminance_threshold(4.5) < starmap.luminance_threshold(2.0)
    # a star exactly at the limit is shown, one two magnitudes fainter is hidden
    thr = starmap.luminance_threshold(5.0)
    assert starmap.star_peak(5.0) > thr and starmap.star_peak(7.0) < thr


def test_star_count_law():
    assert starmap.count_below(3.0) == pytest.approx(171)
    assert 8000 < starmap.count_below(6.5) < 10000                          # ~9000 stars to magnitude 6.5


def test_bake_key_is_deterministic_and_sensitive():
    k = starmap.bake_key(4096, 2048, 1, 6.5, 1.0)
    assert k == starmap.bake_key(4096, 2048, 1, 6.5, 1.0)
    assert k != starmap.bake_key(2048, 1024, 1, 6.5, 1.0) and k != starmap.bake_key(4096, 2048, 2, 6.5, 1.0)


def test_bake_places_stars_where_the_catalogue_says():
    np = pytest.importorskip("numpy")
    w, h = 1024, 512
    img = starmap.bake_star_map(w, h, seed=1)
    assert img.shape == (h, w, 3) and img.dtype == np.float32
    lum = img @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    for name in ("Sirius", "Vega", "Canopus", "Polaris"):
        s = BY_NAME[name]
        u, v = starmap.dir_to_equirect(astro.radec_to_vec(s.ra_deg, s.dec_deg))
        x, y = int(u * w), int(v * h)
        patch = lum[max(y - 4, 0):y + 5, max(x - 4, 0):x + 5]
        assert patch.max() > 0.5 * starmap.star_peak(s.mag) * 0.5, name
    assert lum.max() == pytest.approx(starmap.star_peak(-1.46), rel=0.3)       # Sirius is the brightest pixel


def test_bake_is_reproducible_and_seeded():
    np = pytest.importorskip("numpy")
    a = starmap.bake_star_map(512, 256, seed=3)
    b = starmap.bake_star_map(512, 256, seed=3)
    c = starmap.bake_star_map(512, 256, seed=4)
    assert np.array_equal(a, b) and not np.array_equal(a, c)


def test_synthetic_field_is_denser_in_the_milky_way():
    np = pytest.importorskip("numpy")
    rng = np.random.default_rng(1)
    vecs, mags, bv = starmap._synthetic_stars(rng, 6.5, 1.0, 119)
    g = np.array(astro.GALACTIC_FROM_J2000)
    b = np.degrees(np.arcsin(np.clip((vecs @ g.T)[:, 2], -1, 1)))
    assert len(vecs) == int(starmap.count_below(6.5)) - 119
    assert mags.min() >= 2.7 and mags.max() <= 6.5 + 1e-6
    in_band = (np.abs(b) < 10).mean()
    assert in_band > 0.25                                   # a uniform sky would put only 17 % within 10 degrees
