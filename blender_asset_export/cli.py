"""Headless export for build scripts and CI.

    blender -b scene.blend --python -m blender_asset_export.cli -- --out build/assets [--budget budget.json]
    python -m blender_asset_export.cli scene.blend --out build/assets      (with the `bpy` pip module)

Exit code 0 when every asset is within budget, 1 when any is over, 2 on bad arguments.
"""

import argparse
import sys

import bpy

from .budget import Budget
from .export import export_scene


def _argv() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="blender_asset_export")
    parser.add_argument("blend", nargs="?", help="a .blend to open (omit when Blender already opened one)")
    parser.add_argument("--out", required=True, help="output directory for .glb files and manifest.json")
    parser.add_argument("--budget", help="budget JSON (keys: max_tris, max_materials, name_pattern, ...)")
    parser.add_argument("--export-failing", action="store_true", help="export over-budget assets as well")
    try:
        args = parser.parse_args(_argv() if argv is None else argv)
        budget = Budget.load(args.budget) if args.budget else Budget()
    except (SystemExit, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.blend:
        bpy.ops.wm.open_mainfile(filepath=args.blend)
    manifest = export_scene(bpy.context.scene, args.out, budget, args.export_failing)
    for asset in manifest["assets"]:
        status = "ok  " if asset["passed"] else "FAIL"
        print(f"{status} {asset['name']}: {asset['tris']} tris, {len(asset['materials'])} materials"
              + ("" if asset["passed"] else f" - {'; '.join(asset['problems'])}"))
    return 0 if manifest["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
