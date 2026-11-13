import json
from pathlib import Path
import unreal
names = [
"t.MaxFPS", "r.VSync", "r.ScreenPercentage", "r.DynamicRes.OperationMode",
"sg.ResolutionQuality", "sg.ViewDistanceQuality", "sg.AntiAliasingQuality",
"sg.ShadowQuality", "sg.GlobalIlluminationQuality", "sg.ReflectionQuality",
"sg.PostProcessQuality", "sg.TextureQuality", "sg.EffectsQuality", "sg.ShadingQuality",
"r.Lumen.HardwareRayTracing", "r.Lumen.DiffuseIndirect.Allow", "r.Lumen.Reflections.Allow",
"r.Shadow.Virtual.Enable", "r.RayTracing", "r.RayTracing.Shadows",
"r.TSR.History.ScreenPercentage", "r.Streaming.PoolSize", "r.GPUCsvStatsEnabled",
"r.ProfileGPU.ShowUI"
]
data = {n: unreal.SystemLibrary.get_console_variable_string_value(n) for n in names}
data["editor_world"] = unreal.EditorLevelLibrary.get_editor_world().get_path_name()
data["dirty_maps"] = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
data["dirty_content"] = [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
Path(r"C:/Users/motoo/OneDrive/デスクトップ/まとめ/個人業務/ゲーム開発/UnrealEngine/GameProject_OPC/EscapeFromKD/Saved/Automation/StageOptimization_20261113/Before/runtime_settings.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

