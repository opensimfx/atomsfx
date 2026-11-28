"""Lightning flashes inside a cloud layer: when, how bright, and where (pure Python, no bpy).

A cloud-to-ground or intracloud flash is not one pulse: it is a few *return strokes* (typically 3-4, up to ~20)
some 40-100 ms apart, each lighting the cloud for a frame or two and leaving a short afterglow (Rakov and Uman,
Lightning: Physics and Effects, 2003). Flash starts follow a Poisson process at ``rate_per_min``; every flash
gets its own position inside the storm. Everything comes from a seeded RNG, so a scene renders the same flashes
every time and on every machine.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

STROKES_MIN, STROKES_MAX = 1, 4
STROKE_GAP_S = (0.04, 0.12)
AFTERGLOW = 0.3          # brightness one frame after a stroke, relative to the stroke


@dataclass
class Flash:
    start_frame: int
    strokes: list = field(default_factory=list)   # (frame, relative brightness 0..1)
    offset: tuple = (0.0, 0.0, 0.0)               # unit-disc position (x, y) and height share (z, 0..1)


def schedule(rate_per_min: float, frame_start: int, frame_end: int, fps: float, seed: int) -> list[Flash]:
    """Flashes between ``frame_start`` and ``frame_end`` (inclusive), in frame order."""
    if rate_per_min <= 0.0 or frame_end <= frame_start or fps <= 0.0:
        return []
    rng = random.Random(int(seed) * 7919 + 17)
    mean_gap_s = 60.0 / rate_per_min
    t = rng.expovariate(1.0 / mean_gap_s) * 0.5          # the first flash comes a little sooner
    out = []
    span_s = (frame_end - frame_start) / fps
    while t < span_s:
        f0 = frame_start + int(round(t * fps))
        strokes, ts = [], t
        for i in range(rng.randint(STROKES_MIN, STROKES_MAX)):
            if i:
                ts += rng.uniform(*STROKE_GAP_S)
            f = frame_start + int(round(ts * fps))
            # the first return stroke is usually the brightest
            strokes.append((f, 1.0 if i == 0 else rng.uniform(0.35, 0.8)))
        a, r = rng.uniform(0.0, 2.0 * math.pi), math.sqrt(rng.random())
        out.append(Flash(f0, strokes, (r * math.cos(a), r * math.sin(a), rng.uniform(0.25, 0.65))))
        t = ts + max(rng.expovariate(1.0 / mean_gap_s), 0.3)
    return out


def keyframes(flashes: list[Flash], peak: float) -> list[tuple[int, float]]:
    """(frame, strength) keys: dark before each flash, a spike per stroke, an afterglow frame, dark after.
    Overlapping strokes keep the brighter value."""
    keys: dict[int, float] = {}

    def put(f, v):
        keys[f] = max(keys.get(f, 0.0), v)

    for fl in flashes:
        put(fl.start_frame - 1, 0.0)
        for f, rel in fl.strokes:
            put(f, peak * rel)
            put(f + 1, peak * rel * AFTERGLOW)
            keys.setdefault(f + 2, 0.0)
        last = max(f for f, _ in fl.strokes)
        keys.setdefault(last + 2, 0.0)
    return sorted(keys.items())
