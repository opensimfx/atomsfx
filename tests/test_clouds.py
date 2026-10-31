import math
from types import SimpleNamespace

import pytest

from atmosfx.core import clouds as C


def layer(**kw):
    k = C.kind("CUMULUS")
    d = dict(kind="CUMULUS", altitude_m=k.altitude_m, thickness_m=k.thickness_m, coverage=0.4, density=k.density,
             scale_m=900.0, detail=0.6, anisotropy=0.8, wind_speed_ms=10.0, wind_dir_deg=90.0, seed=1,
             radius_m=15000.0, edge_fade=0.35)
    d.update(kw)
    return SimpleNamespace(**d)


def test_kinds_are_complete_and_physical():
    assert set(C.KINDS) == {"CUMULUS", "STRATOCUMULUS", "STRATUS", "ALTOCUMULUS", "ALTOSTRATUS", "CUMULONIMBUS", "CIRRUS"}
    for k in C.KINDS.values():
        assert 0 < k.coverage <= 1 and 0.5 <= k.stretch <= 5 and 0.6 <= k.anisotropy <= 0.9
        assert 0 < k.bottom_ramp < 1 and 0 < k.top_ramp < 1
    assert C.KINDS["CIRRUS"].altitude_m > C.KINDS["ALTOCUMULUS"].altitude_m > C.KINDS["CUMULUS"].altitude_m
    assert C.KINDS["CUMULONIMBUS"].thickness_m > 5000 and C.KINDS["CUMULONIMBUS"].anvil > 0
    with pytest.raises(KeyError):
        C.kind("soup")
    assert C.kind("cumulus").key == "CUMULUS"                       # case-insensitive


def test_coverage_threshold_is_the_quantile():
    from statistics import NormalDist
    assert C.coverage_threshold(0.5) == pytest.approx(C.FIELD_MEAN)
    assert C.coverage_threshold(0.0) > 1.0 and C.coverage_threshold(1.0) < 0.0
    seq = [C.coverage_threshold(c / 10) for c in range(1, 10)]
    assert seq == sorted(seq, reverse=True)                          # more coverage, lower threshold
    # fraction of a N(mean, sd) field above the threshold equals the coverage
    for c in (0.1, 0.4, 0.8):
        frac = 1 - NormalDist(C.FIELD_MEAN, C.FIELD_STD).cdf(C.coverage_threshold(c))
        assert frac == pytest.approx(c, abs=1e-6)


def test_wind_vector_compass():
    assert C.wind_vector(10, 0) == pytest.approx((0, 10, 0), abs=1e-9)           # north = +Y
    assert C.wind_vector(10, 90) == pytest.approx((10, 0, 0), abs=1e-9)          # east = +X
    assert C.wind_vector(0, 45) == (0.0, 0.0, 0.0)


def test_seed_offsets_are_stable_and_distinct():
    assert C.seed_offset(1) == C.seed_offset(1) and C.seed_offset(1) != C.seed_offset(2)
    assert all(abs(x) <= 500 for x in C.seed_offset(7))


def test_socket_values_content():
    v = C.socket_values(layer(), "FINAL")
    assert v["Base Altitude"] == 1500.0 and v["Thickness"] == 1400.0 and v["Octaves"] == 7.0
    assert v["Frequency"] == pytest.approx(1 / 900)
    assert v["Inner Radius"] == pytest.approx(15000 * 0.65)
    assert v["Wind Velocity"] == pytest.approx((10, 0, 0), abs=1e-9)
    assert v["Threshold"] == pytest.approx(C.coverage_threshold(0.4))
    assert v["Vertical Stretch"] == 1.0 and v["Anvil"] == 0.0
    cb = C.socket_values(layer(kind="CUMULONIMBUS"), "DRAFT")
    assert cb["Anvil"] > 0 and cb["Octaves"] == 2.0
    # edge fade can never reach a zero-width ramp
    assert C.socket_values(layer(edge_fade=5.0))["Inner Radius"] > 0


def test_step_rate_scale_uses_the_thin_layers_only_when_they_are_alone():
    cirrus = layer(thickness_m=900.0, density=0.003)
    dense = layer(thickness_m=1400.0, density=0.02)
    assert C.optical_depth(cirrus) == pytest.approx(1.35)
    assert C.step_rate_scale([]) == 1.0
    assert C.step_rate_scale([dense]) == 1.0
    assert C.step_rate_scale([cirrus]) > 1.0                    # thin layer: coarser steps are safe
    assert C.step_rate_scale([cirrus, dense]) == C.step_rate_scale([dense])   # the dense layer sets the rate


def test_height_profile_shapes():
    f = C.height_profile
    assert f(0.0, 0.1, 0.4) == 0.0 and f(1.0, 0.1, 0.4) == 0.0
    assert f(0.5, 0.1, 0.4) == pytest.approx(1.0)
    assert f(0.05, 0.1, 0.4) < 1.0 and f(0.95, 0.1, 0.4) < 1.0
    # flat-based cumulus: steep rise from the base, long taper to the top
    cu = C.KINDS["CUMULUS"]
    assert f(0.1, cu.bottom_ramp, cu.top_ramp) == pytest.approx(1.0) and f(0.9, cu.bottom_ramp, cu.top_ramp) < 0.2


def test_cost_estimate_scales_with_volume_and_quality():
    a, b = layer(), layer(radius_m=30000.0)
    assert C.estimate_domain_cost(b) == pytest.approx(4 * C.estimate_domain_cost(a))
    assert C.estimate_domain_cost(a, "FINAL") > C.estimate_domain_cost(a, "DRAFT")
