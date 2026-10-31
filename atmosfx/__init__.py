"""AtmosFX - physically based skies, stars, moon, clouds and fog for Blender.

Package layout and design: see docs/SYSTEM_DESIGN.md
"""
# NOTE: keep this module free of top-level bpy imports. ``atmosfx.core`` must stay importable
# (and unit-testable) in a plain Python interpreter.


def register():
    from .scene import apply
    from .ui import ops, panels, props
    import bpy
    props.register()
    for c in ops.CLASSES + panels.CLASSES:
        bpy.utils.register_class(c)
    apply.register_handlers()


def unregister():
    from .scene import apply
    from .ui import ops, panels, props
    import bpy
    apply.unregister_handlers()
    for c in reversed(ops.CLASSES + panels.CLASSES):
        bpy.utils.unregister_class(c)
    props.unregister()
