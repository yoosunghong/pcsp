"""Bake BP_PCAPAgent's Manny skeletal mesh reference pose for Mass HISM use.

Run in a full UnrealEditor process with the bundled AnimToTexture editor plugin
enabled. Mesh conversion requires an editor RHI; commandlet/NullRHI execution
returns no converted mesh on UE 5.8.
"""

import unreal


SOURCE = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
DESTINATION_DIRECTORY = "/Game/PCSP/Mass"
DESTINATION_PACKAGE = f"{DESTINATION_DIRECTORY}/SM_Manny_Mass"
MASS_LOD_TRIANGLE_RATIO = 0.05


skeletal_mesh = unreal.EditorAssetLibrary.load_asset(SOURCE)
if not skeletal_mesh:
    raise RuntimeError(f"Could not load {SOURCE}")

if not unreal.EditorAssetLibrary.does_directory_exist(DESTINATION_DIRECTORY):
    unreal.EditorAssetLibrary.make_directory(DESTINATION_DIRECTORY)

existing = (
    unreal.EditorAssetLibrary.load_asset(DESTINATION_PACKAGE)
    if unreal.EditorAssetLibrary.does_asset_exist(DESTINATION_PACKAGE)
    else None
)
if existing:
    unreal.log(f"Mass Manny static mesh already exists: {DESTINATION_PACKAGE}")
    static_mesh = existing
else:
    static_mesh = unreal.AnimToTextureBPLibrary.convert_skeletal_mesh_to_static_mesh(
        skeletal_mesh, DESTINATION_PACKAGE, 0
    )
    if not static_mesh:
        raise RuntimeError("AnimToTexture skeletal-to-static conversion failed")

# Keep the Manny materials/silhouette but add a deliberately cheap LOD for the
# 1000-agent HISM tier. The runtime component forces LOD1 so nearby instances do
# not silently switch back to the expensive source mesh.
mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
lod_options = unreal.StaticMeshReductionOptions()
lod_options.auto_compute_lod_screen_size = False
lod_options.reduction_settings = [
    unreal.StaticMeshReductionSettings(percent_triangles=1.0, screen_size=1.0),
    unreal.StaticMeshReductionSettings(
        percent_triangles=MASS_LOD_TRIANGLE_RATIO, screen_size=0.0
    ),
]
lod_count = mesh_editor.set_lods(static_mesh, lod_options)
if lod_count < 2:
    raise RuntimeError(f"Expected two static-mesh LODs, got {lod_count}")

if not unreal.EditorAssetLibrary.save_loaded_asset(static_mesh, only_if_is_dirty=False):
    raise RuntimeError(f"Could not save {DESTINATION_PACKAGE}")

unreal.log(
    f"Baked Mass Manny static mesh: {static_mesh.get_path_name()} "
    f"(LOD1 triangle ratio={MASS_LOD_TRIANGLE_RATIO})"
)

# Allows the script to be used with full UnrealEditor.exe (required by mesh
# conversion on some RHIs) without leaving a temporary editor process open.
unreal.SystemLibrary.quit_editor()
