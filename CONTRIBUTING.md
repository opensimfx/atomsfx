# Contributing

- Physics and anything that can be computed without Blender belongs in `atmosfx/core/` (no `bpy` imports; the build
  tool enforces it) with a test in `tests/`. Blender code only applies those numbers to nodes and objects.
- Every number that reaches a shader should come from `core/skyview.py`, so the unit tests cover it.
- Presets live in the table in `tools/gen_presets.py`; run it and `tools/gen_preset_docs.py` and commit the output.
- Before sending a change: `python -m pytest` and, with the `bpy` wheel available, `python tests/blender_smoke.py`.
- Changing a node group? Bump its `*_VERSION` constant so existing files rebuild it, and keep every conclusion about
  Blender's behaviour backed by a measurement (see the "Measured conventions" table in docs/SYSTEM_DESIGN.md).
- Licensing: do not paste code, shaders, node groups, textures or data from other add-ons, including ones you own a
  licence for. Original work only.
