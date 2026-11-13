import json
import time
from pathlib import Path
import unreal

root = Path(r"C:/Users/motoo/OneDrive/デスクトップ/まとめ/個人業務/ゲーム開発/UnrealEngine/GameProject_OPC/EscapeFromKD/Saved/Automation/StageOptimization_20261113")
job = json.loads((root / "capture_job.json").read_text(encoding="utf-8"))
worlds = unreal.EditorLevelLibrary.get_pie_worlds(False)
if len(worlds) != 1:
    raise RuntimeError("Expected exactly one PIE world")
world = worlds[0]
for command in job.get("commands", []):
    unreal.SystemLibrary.execute_console_command(world, command)
unreal.SystemLibrary.execute_console_command(world, "r.GPUCsvStatsEnabled 1")
unreal.SystemLibrary.execute_console_command(world, "r.ProfileGPU.ShowUI 0")
start = time.perf_counter()
handle = None

def begin_capture(delta_seconds):
    if time.perf_counter() - start < job.get("warmup", 8):
        return
    try:
        controller = unreal.GameplayStatics.get_player_controller(world, 0)
        metadata = {
            "label": job["label"],
            "world": world.get_path_name(),
            "viewport_size": list(controller.get_viewport_size()),
            "commands": job.get("commands", []),
            "screen_percentage": unreal.SystemLibrary.get_console_variable_string_value("r.ScreenPercentage"),
            "dynamic_resolution": unreal.SystemLibrary.get_console_variable_string_value("r.DynamicRes.OperationMode"),
            "vsync": unreal.SystemLibrary.get_console_variable_string_value("r.VSync"),
            "max_fps": unreal.SystemLibrary.get_console_variable_string_value("t.MaxFPS"),
            "frames": job.get("frames", 600)
        }
        (root / (job["label"] + "_metadata.json")).write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        unreal.SystemLibrary.execute_console_command(world, "CsvProfile STARTFILE=" + job["label"] + ".csv")
        unreal.SystemLibrary.execute_console_command(world, "CsvProfile FRAMES=" + str(job.get("frames", 600)))
    finally:
        unreal.unregister_slate_post_tick_callback(handle)

handle = unreal.register_slate_post_tick_callback(begin_capture)

