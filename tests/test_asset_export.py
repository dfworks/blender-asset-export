"""Headless tests against Blender's `bpy` module (pip install bpy pytest)."""

import json
import struct
import sys
from pathlib import Path

import bpy  # must come first: it makes bmesh and mathutils importable
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import blender_asset_export  # noqa: E402
from blender_asset_export import cli  # noqa: E402
from blender_asset_export.budget import Budget  # noqa: E402
from blender_asset_export.export import export_scene  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    blender_asset_export.register()
    yield
    blender_asset_export.unregister()


def add_asset(name, subdivisions=0, materials=1, uv=True, scale=(1, 1, 1)):
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    obj = bpy.context.active_object
    for c in obj.users_collection:
        c.objects.unlink(obj)
    coll.objects.link(obj)
    obj.name = f"{name}_mesh"
    if subdivisions:
        mod = obj.modifiers.new("sub", "SUBSURF")
        mod.levels = subdivisions
    for i in range(materials):
        obj.data.materials.append(bpy.data.materials.new(f"{name}_mat{i}"))
    if not uv:
        while obj.data.uv_layers:
            obj.data.uv_layers.remove(obj.data.uv_layers[0])
    obj.scale = scale
    return obj


def glb_triangle_count(path: Path) -> int:
    """Read the JSON chunk of a .glb and sum the index counts of its primitives."""
    data = path.read_bytes()
    json_len = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20:20 + json_len])
    return sum(doc["accessors"][p["indices"]]["count"] // 3
               for mesh in doc["meshes"] for p in mesh["primitives"])


def test_clean_asset_exports_with_manifest(tmp_path):
    add_asset("crate")
    manifest = export_scene(bpy.context.scene, tmp_path, Budget())
    assert manifest["passed"]
    (asset,) = manifest["assets"]
    assert asset["tris"] == 12
    assert asset["bounds_min"] == [-0.5, -0.5, -0.5]
    glb = tmp_path / asset["file"]
    assert glb.exists() and len(asset["sha256"]) == 64
    assert glb_triangle_count(glb) == 12
    assert json.loads((tmp_path / "manifest.json").read_text())["assets"][0]["name"] == "crate"


def test_modifiers_count_toward_triangles_and_block_export(tmp_path):
    add_asset("rock", subdivisions=3)  # 6 * 4^3 quads = 768 tris
    manifest = export_scene(bpy.context.scene, tmp_path, Budget(max_tris=500))
    (asset,) = manifest["assets"]
    assert asset["tris"] == 768
    assert not asset["passed"] and "file" not in asset
    assert not (tmp_path / "rock.glb").exists()


def test_each_rule_reports_its_problem(tmp_path):
    add_asset("BadName", materials=3, uv=False, scale=(2, 2, 2))
    manifest = export_scene(bpy.context.scene, tmp_path, Budget(max_materials=2), export_failing=True)
    problems = " | ".join(manifest["assets"][0]["problems"])
    for expected in ("does not match", "3 materials", "no UV map", "unapplied rotation or scale"):
        assert expected in problems
    assert (tmp_path / "BadName.glb").exists()  # exported anyway because export_failing was set


def test_cli_exit_codes_and_budget_file(tmp_path, capsys):
    add_asset("crate")
    add_asset("tower", subdivisions=2)  # 192 tris
    budget = tmp_path / "budget.json"
    budget.write_text(json.dumps({"max_tris": 100}))
    assert cli.main(["--out", str(tmp_path / "out"), "--budget", str(budget)]) == 1
    out = capsys.readouterr().out
    assert "ok   crate" in out and "FAIL tower" in out
    budget.write_text(json.dumps({"max_tris": 1000}))
    assert cli.main(["--out", str(tmp_path / "out"), "--budget", str(budget)]) == 0
    budget.write_text(json.dumps({"max_triangles": 5}))
    assert cli.main(["--out", str(tmp_path / "out"), "--budget", str(budget)]) == 2


def test_operator_runs_from_ui(tmp_path):
    add_asset("crate")
    settings = bpy.context.scene.asset_export
    settings.out_dir = str(tmp_path)
    assert bpy.ops.export_scene.asset_budget() == {"FINISHED"}
    assert settings.summary.startswith("1 assets, 0 over budget")
