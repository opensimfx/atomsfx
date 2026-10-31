from atmosfx.core.identity import canonical, state_hash


def test_hash_is_order_independent_and_float_noise_tolerant():
    a = {"b": 1.0000001, "a": [1, 2, {"z": 0.5, "y": 2}]}
    b = {"a": [1, 2, {"y": 2, "z": 0.5}], "b": 1.0}
    assert state_hash(a) == state_hash(b)
    assert state_hash(a) != state_hash({"a": 1, "b": 1.1})


def test_canonical_is_stable_text():
    assert canonical({"x": (1, 2), "a": None}) == '{"a":null,"x":[1,2]}'
