"""Export every asset in a scene to its own .glb and write a manifest the engine can read."""

import hashlib
import json
from pathlib import Path

import bpy

from .budget import Budget, assets_in_scene, check_asset

MANIFEST_NAME = "manifest.json"
MANIFEST_VERSION = 1


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _export_glb(objects, path: Path) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
    )


def export_scene(scene, out_dir: str | Path, budget: Budget, export_failing: bool = False) -> dict:
    """Check each asset against the budget, export the ones that pass, and write manifest.json.

    Failing assets are listed in the manifest with their problems and are not exported unless
    export_failing is set, so an engine never silently loads an over-budget asset.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    entries = []
    for name, objects in sorted(assets_in_scene(scene).items()):
        report = check_asset(name, objects, depsgraph, budget)
        entry = report.to_dict()
        meshes = [o for o in objects if o.type == "MESH"]
        if meshes and (report.passed or export_failing):
            path = out / f"{name}.glb"
            _export_glb(meshes, path)
            entry["file"] = path.name
            entry["sha256"] = _sha256(path)
        entries.append(entry)
    manifest = {
        "version": MANIFEST_VERSION,
        "source": bpy.data.filepath or None,
        "blender": bpy.app.version_string,
        "budget": budget.__dict__,
        "assets": entries,
        "passed": all(e["passed"] for e in entries),
    }
    (out / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
