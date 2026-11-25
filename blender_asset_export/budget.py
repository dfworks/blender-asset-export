"""Budget checks for game-ready assets: pure functions over Blender objects, no UI."""

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import bpy  # noqa: F401  (makes mathutils importable when run outside Blender)
from mathutils import Vector

UNIT_TOLERANCE = 1e-4


@dataclass(frozen=True)
class Budget:
    max_tris: int = 20000
    max_materials: int = 4
    name_pattern: str = r"^[a-z][a-z0-9_]*$"
    require_uv: bool = True
    require_applied_transform: bool = True

    @classmethod
    def load(cls, path: str | Path) -> "Budget":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"Unknown budget keys: {sorted(unknown)}")
        return cls(**data)


@dataclass
class AssetReport:
    name: str
    tris: int = 0
    materials: list[str] = field(default_factory=list)
    bounds_min: list[float] = field(default_factory=list)
    bounds_max: list[float] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.problems

    def to_dict(self) -> dict:
        return asdict(self) | {"passed": self.passed}


def triangle_count(obj, depsgraph) -> int:
    """Triangles after modifiers, as the exporter will see them."""
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        return len(mesh.loop_triangles)
    finally:
        evaluated.to_mesh_clear()


def world_bounds(objects) -> tuple[list[float], list[float]]:
    corners = [obj.matrix_world @ Vector(c) for obj in objects for c in obj.bound_box]
    if not corners:
        return [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
    lo = [min(c[i] for c in corners) for i in range(3)]
    hi = [max(c[i] for c in corners) for i in range(3)]
    return [round(v, 6) for v in lo], [round(v, 6) for v in hi]


def _transform_applied(obj) -> bool:
    scale_ok = all(abs(s - 1.0) < UNIT_TOLERANCE for s in obj.scale)
    rot_ok = all(abs(r) < UNIT_TOLERANCE for r in obj.rotation_euler)
    return scale_ok and rot_ok


def check_asset(name: str, objects, depsgraph, budget: Budget) -> AssetReport:
    """Check one asset: a collection (or a single object) that becomes one exported file."""
    report = AssetReport(name=name)
    meshes = [o for o in objects if o.type == "MESH"]
    if not meshes:
        report.problems.append("no mesh objects")
        return report
    if not re.match(budget.name_pattern, name):
        report.problems.append(f"name '{name}' does not match {budget.name_pattern}")
    materials = sorted({slot.material.name for o in meshes for slot in o.material_slots if slot.material})
    report.materials = materials
    report.tris = sum(triangle_count(o, depsgraph) for o in meshes)
    report.bounds_min, report.bounds_max = world_bounds(meshes)
    if report.tris > budget.max_tris:
        report.problems.append(f"{report.tris} triangles, budget is {budget.max_tris}")
    if len(materials) > budget.max_materials:
        report.problems.append(f"{len(materials)} materials, budget is {budget.max_materials}")
    for obj in meshes:
        if budget.require_uv and not obj.data.uv_layers:
            report.problems.append(f"'{obj.name}' has no UV map")
        if budget.require_applied_transform and not _transform_applied(obj):
            report.problems.append(f"'{obj.name}' has unapplied rotation or scale")
    return report


def assets_in_scene(scene) -> dict[str, list]:
    """Each top-level collection under the scene is one asset; loose objects are one asset each."""
    assets = {coll.name: list(coll.all_objects) for coll in scene.collection.children}
    for obj in scene.collection.objects:
        assets.setdefault(obj.name, [obj])
    return assets
