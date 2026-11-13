import json
from pathlib import Path
import unreal
root = Path(r"C:/Users/motoo/OneDrive/デスクトップ/まとめ/個人業務/ゲーム開発/UnrealEngine/GameProject_OPC/EscapeFromKD")
assets = {
"You": "/Game/Main/Character/You",
"BP_Floor03": "/Game/Main/Stage/BP_Floor03",
"BP_AdmissionRobot": "/Game/Main/Enemy/BP_AdmissionRobot",
"BP_Rifle": "/Game/Main/Rifle/BP_Rifle"
}
result = {
"dirty_maps": [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()],
"dirty_content": [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()],
"pie_worlds": [w.get_path_name() for w in unreal.EditorLevelLibrary.get_pie_worlds(False)],
"editor_world": unreal.EditorLevelLibrary.get_editor_world().get_path_name(),
"blueprints": {}
}
for name, path in assets.items():
    asset = unreal.load_asset(path)
    result["blueprints"][name] = {"path":path,"exists":bool(asset),"status":str(asset.get_editor_property("status")) if asset else None}
(root / "Saved/Automation/StageOptimization_20261113/checkpoint_validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

