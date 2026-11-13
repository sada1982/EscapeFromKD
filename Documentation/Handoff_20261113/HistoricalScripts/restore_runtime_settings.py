import json
from pathlib import Path
import unreal
base = Path(r"C:/Users/motoo/OneDrive/デスクトップ/まとめ/個人業務/ゲーム開発/UnrealEngine/GameProject_OPC/EscapeFromKD/Saved/Automation/StageOptimization_20261113")
worlds = unreal.EditorLevelLibrary.get_pie_worlds(False)
world = worlds[0] if worlds else unreal.EditorLevelLibrary.get_editor_world()
commands = [
"CsvProfile STOP",
"r.TSR.History.ScreenPercentage 200",
"r.Shadow.Virtual.MaxPhysicalPages 4096",
"r.LumenScene.SurfaceCache.AtlasSize 4096",
"r.GPUCsvStatsEnabled 0",
"r.ProfileGPU.ShowUI 1"
]
for command in commands:
    unreal.SystemLibrary.execute_console_command(world, command)
names = ["r.TSR.History.ScreenPercentage", "r.Shadow.Virtual.MaxPhysicalPages", "r.LumenScene.SurfaceCache.AtlasSize", "r.GPUCsvStatsEnabled", "r.ProfileGPU.ShowUI", "r.ScreenPercentage", "r.DynamicRes.OperationMode", "r.Lumen.HardwareRayTracing", "t.MaxFPS", "r.VSync"]
result = {name: unreal.SystemLibrary.get_console_variable_string_value(name) for name in names}
(base / "restored_runtime_settings.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

