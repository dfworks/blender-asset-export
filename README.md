# Blender Asset Export

Export game assets from Blender the same way every time, and refuse the ones that would break the game.

Each top-level collection in the scene is one asset (loose objects are one asset each). For every asset it:

- counts triangles **after modifiers**, as the exporter sees them, and checks them against a budget;
- checks material count, a naming rule, UV maps, and unapplied rotation or scale;
- exports the passing ones to `<name>.glb` (glTF 2.0, Y-up) and skips the failing ones unless told otherwise;
- writes `manifest.json` with triangles, bounds, materials, problems and a SHA-256 per file, so an engine or a
  build step can check what it is loading.

It runs in the UI (3D View sidebar > Asset Export) and headless for build scripts and CI:

```
blender -b level.blend --python-expr "import sys; from blender_asset_export import cli; sys.exit(cli.main())" -- --out build/assets --budget budget.json
python -m blender_asset_export.cli level.blend --out build/assets     # with `pip install bpy`
```

Exit code 0 means every asset is within budget, 1 means at least one is over, 2 means bad arguments.

`budget.json` (every key optional, unknown keys are refused):

```json
{"max_tris": 20000, "max_materials": 4, "name_pattern": "^[a-z][a-z0-9_]*$", "require_uv": true, "require_applied_transform": true}
```

Tests run headless against Blender's own `bpy` module: `pip install bpy pytest && python -m pytest tests -q`.
