"""Blender Asset Export: one .glb per asset, checked against a budget, with a manifest for the engine."""

bl_info = {
    "name": "Asset Export (glTF + budget)",
    "author": "",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Asset Export",
    "description": "Export each collection as a .glb, checked against a triangle/material budget, with a manifest",
    "category": "Import-Export",
}

import bpy

from . import budget as budget_mod
from . import export as export_mod


class AssetExportSettings(bpy.types.PropertyGroup):
    out_dir: bpy.props.StringProperty(name="Output", subtype="DIR_PATH", default="//export/")
    max_tris: bpy.props.IntProperty(name="Max triangles", default=20000, min=1)
    max_materials: bpy.props.IntProperty(name="Max materials", default=4, min=1)
    require_uv: bpy.props.BoolProperty(name="Require UVs", default=True)
    require_applied_transform: bpy.props.BoolProperty(name="Require applied transforms", default=True)
    export_failing: bpy.props.BoolProperty(name="Export failing assets too", default=False)
    summary: bpy.props.StringProperty(default="")

    def budget(self) -> budget_mod.Budget:
        return budget_mod.Budget(
            max_tris=self.max_tris,
            max_materials=self.max_materials,
            require_uv=self.require_uv,
            require_applied_transform=self.require_applied_transform,
        )


class EXPORT_OT_asset_budget(bpy.types.Operator):
    """Check every asset against the budget and export the ones that pass"""

    bl_idname = "export_scene.asset_budget"
    bl_label = "Check and Export"

    def execute(self, context):
        settings = context.scene.asset_export
        out_dir = bpy.path.abspath(settings.out_dir)
        manifest = export_mod.export_scene(context.scene, out_dir, settings.budget(), settings.export_failing)
        failing = [a for a in manifest["assets"] if not a["passed"]]
        lines = [f"{len(manifest['assets'])} assets, {len(failing)} over budget"]
        lines += [f"{a['name']}: {'; '.join(a['problems'])}" for a in failing]
        settings.summary = "\n".join(lines)
        self.report({"INFO"} if not failing else {"WARNING"}, lines[0])
        return {"FINISHED"}


class VIEW3D_PT_asset_export(bpy.types.Panel):
    bl_label = "Asset Export"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Asset Export"

    def draw(self, context):
        settings = context.scene.asset_export
        layout = self.layout
        for prop in ("out_dir", "max_tris", "max_materials", "require_uv",
                     "require_applied_transform", "export_failing"):
            layout.prop(settings, prop)
        layout.operator(EXPORT_OT_asset_budget.bl_idname, icon="EXPORT")
        if settings.summary:
            box = layout.box()
            for line in settings.summary.splitlines():
                box.label(text=line)


CLASSES = (AssetExportSettings, EXPORT_OT_asset_budget, VIEW3D_PT_asset_export)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.asset_export = bpy.props.PointerProperty(type=AssetExportSettings)


def unregister():
    del bpy.types.Scene.asset_export
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
