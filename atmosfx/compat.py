"""Blender-version helpers. AtmosFX targets Blender 5.2 LTS."""
import bpy

VERSION = bpy.app.version


def at_least(major: int, minor: int = 0) -> bool:
    return VERSION >= (major, minor, 0)
