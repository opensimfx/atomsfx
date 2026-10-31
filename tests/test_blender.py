"""Runs tests/blender_smoke.py when the ``bpy`` wheel is available (it needs Python 3.11); skipped otherwise."""
import os
import subprocess
import sys

import pytest

pytest.importorskip("bpy")

HERE = os.path.dirname(os.path.abspath(__file__))


def test_blender_smoke_suite():
    env = dict(os.environ)
    r = subprocess.run([sys.executable, os.path.join(HERE, "blender_smoke.py")], capture_output=True, text=True,
                       timeout=900, env=env)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
