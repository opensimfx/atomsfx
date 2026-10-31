import json
import os

import pytest

from atmosfx.core import presets as P


def test_library_loads_and_is_valid():
    lib = P.library(refresh=True)
    assert len(lib) >= 25
    for pid, p in lib.items():
        assert P.validate(p) == [], pid
        assert pid == p.id and p.name and p.description


def test_every_category_is_populated_and_known():
    cats = P.by_category()
    assert set(cats) >= set(P.CATEGORIES)
    assert all(cats[c] for c in P.CATEGORIES)
    assert {p.category for p in P.library().values()} <= set(P.CATEGORIES)


def test_json_round_trip_is_lossless():
    for p in P.library().values():
        assert P.preset_from_dict(P.preset_to_dict(p)) == p


def test_file_round_trip(tmp_path):
    p = P.get("sunset_clouds")
    f = tmp_path / "x.json"
    P.save_file(str(f), [p])
    (back,) = P.load_file(str(f))
    assert back == p
    assert json.loads(f.read_text())["schema"] == P.SCHEMA_VERSION


def test_newer_schema_is_rejected(tmp_path):
    f = tmp_path / "x.json"
    f.write_text(json.dumps({"schema": 99, "presets": []}))
    with pytest.raises(ValueError):
        P.load_file(str(f))


def test_derive_does_not_mutate_the_base():
    base = P.get("clear_noon")
    out = P.derive(base, id="x", sun={"elevation_deg": 10.0}, fog={"visibility_m": 123.0},
                   clouds=[{"kind": "CIRRUS", "coverage": 0.2}])
    assert out.sun.elevation_deg == 10.0 and base.sun.elevation_deg != 10.0
    assert out.fog.visibility_m == 123.0 and out.fog.enabled == base.fog.enabled
    assert out.clouds[0].kind == "CIRRUS" and base.clouds == []


def test_validation_catches_problems():
    p = P.derive(P.get("clear_noon"), id="bad id!", sun={"elevation_deg": 120.0}, fog={"mode": "SOUP"})
    errs = P.validate(p)
    assert any("id" in e for e in errs) and any("elevation_deg" in e for e in errs) and any("mode" in e for e in errs)
    many = P.derive(P.get("clear_noon"), clouds=[{"kind": "CUMULUS"}] * 4)
    assert any("3 cloud layers" in e for e in P.validate(many))
    badkind = P.derive(P.get("clear_noon"), clouds=[{"kind": "SOUP"}])
    assert any("unknown" in e for e in P.validate(badkind))
    badrange = P.derive(P.get("clear_noon"), clouds=[{"coverage": 3.0}])
    assert any("coverage" in e for e in P.validate(badrange))


def test_unknown_preset_raises():
    with pytest.raises(KeyError):
        P.get("nope")


def test_presets_are_physically_sensible():
    lib = P.library()
    night = [p for p in lib.values() if p.category == "Night sky"]
    assert all(p.sun.elevation_deg < -5 for p in night)
    assert all(p.stars.enabled for p in night)
    dense = lib["dense_fog"]
    assert dense.fog.visibility_m < 200                                     # WMO dense fog / thick fog
    day = [p for p in lib.values() if p.category in ("Weather", "Time of day") and p.sun.elevation_deg > 20]
    assert day and all(not p.stars.enabled for p in day)
    assert lib["storm_cumulonimbus"].clouds[0].kind == "CUMULONIMBUS"
    assert len(lib["storm_cumulonimbus"].clouds) == 2
    assert lib["valley_fog"].fog.mode == "BOTH"


def test_preset_ids_match_the_generator():
    # the shipped JSON must be what tools/gen_presets.py produces
    import importlib.util
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location("gen_presets", os.path.join(root, "tools", "gen_presets.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert [p.id for p in mod.PRESETS] == list(P.library())
    for gen in mod.PRESETS:
        assert P.preset_from_dict(P.preset_to_dict(gen)) == P.get(gen.id)
