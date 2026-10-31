"""Deterministic identity for physical state: hash a canonical JSON form.

Used as a content-addressed cache key (baked star maps, generated images) so a bake is rebuilt only when
the state that produces it changes. Floats are rounded to 6 decimals so UI float noise does not churn it.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def _norm(obj: Any) -> Any:
    if isinstance(obj, float):
        return round(obj, 6)
    if isinstance(obj, dict):
        return {str(k): _norm(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return [_norm(v) for v in obj]
    return obj


def canonical(obj: Any) -> str:
    return json.dumps(_norm(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def state_hash(obj: Any) -> str:
    return hashlib.sha1(canonical(obj).encode("utf-8")).hexdigest()
