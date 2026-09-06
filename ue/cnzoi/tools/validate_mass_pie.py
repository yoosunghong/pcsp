"""Two real PIE start/stop cycles; launch only in a dedicated test Editor.

Use -ExecutePythonScript=<this file> -PCSP_PIEValidation. Does not save assets.
The explicit opt-in permits this script to close its own Editor after testing.
"""
import time
import traceback

import unreal

assert "-PCSP_PIEValidation" in unreal.SystemLibrary.get_command_line()
unreal.EditorPythonScripting.set_keep_python_script_alive(True)

level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert level.load_level("/Game/PCSP/Maps/Map_PCSPDistrict_Portfolio")
state = {"phase": "begin", "cycle": 1, "since": time.monotonic(), "started": time.monotonic()}


def finish(passed):
    unreal.log(f"PCSP_PIE_VALIDATION result={'PASS' if passed else 'FAIL'} cycles={state['cycle']}")
    unreal.unregister_slate_post_tick_callback(state["handle"])
    if level.is_in_play_in_editor():
        level.editor_request_end_play()
    unreal.SystemLibrary.quit_editor()


def tick(delta):
    try:
        now = time.monotonic()
        assert now - state["started"] < 240, "PIE validation timed out"
        phase = state["phase"]
        if phase == "begin" and now - state["since"] > 2:
            unreal.log(f"PCSP_PIE_VALIDATION begin cycle={state['cycle']}")
            level.editor_request_begin_play()
            state.update(phase="playing", since=now)
        elif phase == "playing" and level.is_in_play_in_editor():
            world = editor.get_game_world()
            if not world or unreal.GameplayStatics.get_time_seconds(world) < 8:
                return
            controller = unreal.GameplayStatics.get_player_controller(world, 0)
            assert isinstance(controller, unreal.PCSPDemoPlayerController)
            assert not unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PCSPAgentCharacter)
            controller.focus_nearest_agent()
            controller.cycle_agent(1)
            hud = controller.get_editor_property("demo_hud")
            assert hud and hud.is_in_viewport()
            hud.refresh_hud()
            snapshot = hud.get_agent_snapshot()
            run = hud.get_run_snapshot()
            assert snapshot.mass_entity and len(snapshot.needs) == 8
            assert len(snapshot.recent_events) > 0
            assert run.agent_count == 1024 and run.zone_count in (96, 118), run
            button = hud.find_widget("Btn_ToggleCamera")
            assert isinstance(button, unreal.Button) and button.get_is_enabled()
            # Exercise the same native callback bound to the actual UMG button.
            before = controller.is_third_person_camera_active()
            hud.call_method("HandleCameraButtonClicked")
            assert controller.is_third_person_camera_active() != before
            hud.call_method("HandleCameraButtonClicked")
            assert controller.is_third_person_camera_active() == before
            assert hud.get_editor_property("ViewModel") == controller.get_view_model()
            unreal.log(f"PCSP_PIE_VALIDATION runtime PASS cycle={state['cycle']} "
                       f"agents={run.agent_count} zones={run.zone_count} "
                       f"needs={len(snapshot.needs)} history={len(snapshot.recent_events)} "
                       "button_callback=true legacy_viewmodel=true")
            level.editor_request_end_play()
            state.update(phase="stopping", since=now)
        elif phase == "stopping" and not level.is_in_play_in_editor():
            state.update(phase="cooldown", since=now)
        elif phase == "cooldown" and now - state["since"] > 3:
            unreal.log(f"PCSP_PIE_VALIDATION teardown complete cycle={state['cycle']}")
            if state["cycle"] == 2:
                finish(True)
            else:
                state.update(phase="begin", cycle=2, since=now)
    except Exception:
        unreal.log_error("PCSP_PIE_VALIDATION " + traceback.format_exc())
        finish(False)


state["handle"] = unreal.register_slate_post_tick_callback(tick)
