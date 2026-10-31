"""Blender-version helpers. AtmosFX targets Blender 5.x; tested headless on 5.0.1."""
import bpy

VERSION = bpy.app.version


def at_least(major: int, minor: int = 0) -> bool:
    return VERSION >= (major, minor, 0)
