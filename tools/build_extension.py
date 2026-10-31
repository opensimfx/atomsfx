"""Build the installable Blender extension zip.

    python tools/build_extension.py            # -> dist/atmosfx-<version>.zip

The zip holds the contents of ``atmosfx/`` at its root (``blender_manifest.toml`` first), as Blender's extension
installer expects. The script refuses to build if the manifest is malformed, if the version disagrees with
``pyproject.toml``, or if anything under ``core/`` imports ``bpy`` (the pure core must stay testable without it).
"""
from __future__ import annotations

import ast
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "atmosfx")
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache"}
EXCLUDE_SUFFIX = (".pyc", ".pyo", ".orig", ".rej", ".swp")


def read_toml_value(text: str, key: str) -> str | None:
    m = re.search(rf'^{re.escape(key)}\s*=\s*"([^"]*)"', text, re.M)
    return m.group(1) if m else None


def check_manifest() -> tuple[str, str]:
    with open(os.path.join(PKG, "blender_manifest.toml"), encoding="utf-8") as fh:
        text = fh.read()
    required = ("schema_version", "id", "version", "name", "tagline", "maintainer", "type", "blender_version_min")
    missing = [k for k in required if read_toml_value(text, k) is None]
    if missing:
        raise SystemExit(f"manifest is missing: {', '.join(missing)}")
    ident, version = read_toml_value(text, "id"), read_toml_value(text, "version")
    if not re.fullmatch(r"[a-z0-9_]+", ident):
        raise SystemExit(f"manifest id {ident!r} must be lowercase letters, digits and underscores")
    if len(read_toml_value(text, "tagline")) > 64:
        raise SystemExit("manifest tagline is longer than 64 characters")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"manifest version {version!r} is not semantic (x.y.z)")
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as fh:
        pv = read_toml_value(fh.read(), "version")
    if pv != version:
        raise SystemExit(f"version mismatch: manifest {version} vs pyproject {pv}")
    return ident, version


def check_core_is_pure() -> None:
    bad = []
    for dirpath, _dirs, files in os.walk(os.path.join(PKG, "core")):
        for f in files:
            if f.endswith(".py"):
                tree = ast.parse(open(os.path.join(dirpath, f), encoding="utf-8").read())
                for node in ast.walk(tree):
                    names = []
                    if isinstance(node, ast.Import):
                        names = [a.name.split(".")[0] for a in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                        names = [node.module.split(".")[0]]
                    if any(n in ("bpy", "bmesh", "mathutils", "bpy_extras") for n in names):
                        bad.append(os.path.join(dirpath, f))
    if bad:
        raise SystemExit("core/ must not import Blender modules: " + ", ".join(sorted(set(bad))))


def main() -> int:
    ident, version = check_manifest()
    check_core_is_pure()
    out_dir = os.path.join(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{ident}-{version}.zip")
    files = []
    for dirpath, dirs, names in os.walk(PKG):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
        for n in sorted(names):
            if not n.endswith(EXCLUDE_SUFFIX):
                files.append(os.path.join(dirpath, n))
    files.sort(key=lambda p: (os.path.relpath(p, PKG) != "blender_manifest.toml", os.path.relpath(p, PKG)))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, os.path.relpath(p, PKG).replace(os.sep, "/"))
    size = os.path.getsize(out)
    print(f"built {os.path.relpath(out, ROOT)}  ({len(files)} files, {size / 1024:.0f} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
