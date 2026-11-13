AdmissionRobot — ボーン追従の命中判定
2026-11-13

採用アセット:
  /Game/Main/Enemy/AdmissionRobot/PA_AdmissionRobot_HitCollision
  21ボーン、720個の凸形状。描画メッシュとアニメーションは変更しない。

BP_AdmissionRobot の CharacterMesh0 と KDStage の配置済み敵:
  EnablePerPolyCollision=false
  PhysicsAssetOverride=PA_AdmissionRobot_HitCollision
  QueryOnly / Visibility Block を維持。
  Capsule の Visibility Ignore を維持。
SkeletalMesh アセット自体の PerPoly 設定と元 PhysicsAsset は保持する。
新しい PhysicsAsset は UseSimpleAsComplex を使用し、既存の複雑な
Visibility Trace から命中点と法線を取得する。射撃グラフは変更しない。

生成方法:
1. Blender 5.3をバックグラウンドで起動し、build_collision_hulls.py を実行する。
   元の AdmissionRobot_v01.blend は読み込みのみ。保存しない。
   出力先は Saved/Automation/AdmissionRobotCollision/collision_hulls.json。
2. UEはPIEを停止する。通常のUnreal MCPで元の
   SK_AdmissionRobot_PhysicsAsset を上記の候補名へ複製する。
   既存の採用アセットを再生成する場合は、事前にバックアップを取る。
3. PhysicsAssetToolset.AddBody で不足する ball_l / ball_r / hand_l / hand_r /
   neck / spine_01 を追加する。既に存在する場合は追加不要。
4. MCPのSlateコンソールから apply_collision_hulls.py を実行する。
5. PhysicsAssetToolset.SetBodyPhysicsMode(pelvis, Kinematic) により
   物理メッシュを再構築する。検証後、対象アセットだけを保存する。
   Tool名と引数はその環境の describe_toolset で確認すること。

形状生成:
元メッシュの各連結部分が単一ボーンに100%ウェイトを持つことを検査し、
その部分を凸包へ分割する。凹部は面を空間分割し、凸包表面のサンプルが
元表面の外側へ0.05cm以上出る場合は最大12段まで再分割する。
頂点をBlender座標からUE座標へ変換し、各ボーンの基準姿勢の局所座標へ格納する。
毎フレームの全頂点スキニングと三角形加速構造の再構築を避ける。
近似形状であり、ポリゴン単位の判定と数学的に完全一致する方式ではない。
命中精度の検証条件と差異は Documentation/Optimization_20261113/Readme.txt を参照。

検証時の注意:
登録済みコンポーネントで方式を切り替える場合、先に
SetEnablePerPolyCollision(false)、次に SetPhysicsAsset を実行する。
UE5.8.4では逆順にすると物理状態破棄のアサーションが発生した。
採用したBPには実行中の切り替え処理を追加していない。
