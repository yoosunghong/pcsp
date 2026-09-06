"""Read-only diagnosis of legacy Blueprint HUD ownership and variables."""
import unreal

for path in (
    "/Game/PCSP/Blueprints/Widgets/WBP_PCSPDemoHUD",
    "/Game/PCSP/Blueprints/Player/BP_PCSPDemoPlayerController",
):
    bp = unreal.load_object(None, path)
    unreal.log_warning(f"PCSP_HUD_INSPECT asset={path} loaded={bool(bp)}")
    if not bp:
        continue
    cls = unreal.load_class(None, f"{path}.{path.rsplit('/', 1)[-1]}_C")
    cdo = unreal.get_default_object(cls)
    unreal.log_warning(f"PCSP_HUD_INSPECT native_type={type(cdo)} mro={type(cdo).__mro__}")
    unreal.log_warning(f"PCSP_HUD_INSPECT native_hud={isinstance(cdo, unreal.PCSPDemoHUDWidgetBase)} native_controller={isinstance(cdo, unreal.PCSPDemoPlayerController)}")
