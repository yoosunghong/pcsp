import unreal


paths = [
    "/AnimToTexture/Characters/Mannequin/SM_Mannequin_BoneAnimation",
    "/AnimToTexture/Characters/Mannequin/Data/DA_BoneAnimation",
    "/AnimToTexture/Characters/Mannequin/Materials/BoneAnimation/MI_Body_BoneAnimation",
]

unreal.AssetRegistryHelpers.get_asset_registry().scan_paths_synchronous(["/AnimToTexture"], True)
for path in paths:
    asset = unreal.load_object(None, path)
    unreal.log_warning(f"PCSP_A2T_INSPECT asset={path} loaded={bool(asset)} class={asset.get_class().get_name() if asset else '-'}")
    if isinstance(asset, unreal.MaterialInstanceConstant):
        lib = unreal.MaterialEditingLibrary
        unreal.log_warning(f"PCSP_A2T_INSPECT vector_params={lib.get_vector_parameter_names(asset)}")
        unreal.log_warning(f"PCSP_A2T_INSPECT scalar_params={lib.get_scalar_parameter_names(asset)}")
        unreal.log_warning(f"PCSP_A2T_INSPECT texture_params={lib.get_texture_parameter_names(asset)}")
        names = lib.get_static_switch_parameter_names(asset)
        for name in names:
            value = lib.get_material_instance_static_switch_parameter_value(asset, name)
            unreal.log_warning(f"PCSP_A2T_INSPECT switch {name}={value}")
    if isinstance(asset, unreal.StaticMesh):
        unreal.log_warning(f"PCSP_A2T_INSPECT lods={asset.get_num_lods()} materials={asset.get_editor_property('static_materials')}")
    if asset and asset.get_class().get_name() == "AnimToTextureDataAsset":
        for name in ("sample_rate", "num_frames", "animations", "anim_sequences", "static_mesh", "skeletal_mesh"):
            try:
                unreal.log_warning(f"PCSP_A2T_INSPECT {name}={asset.get_editor_property(name)}")
            except Exception as exc:
                unreal.log_warning(f"PCSP_A2T_INSPECT {name}=ERROR:{exc}")
