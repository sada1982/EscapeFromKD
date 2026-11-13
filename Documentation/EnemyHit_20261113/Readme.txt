Escape From KD — 敵の被弾反応
作業日: 2026-11-13

変更内容
・敵に弾が命中した位置へ、白黄色の発光とオレンジ色の火花を生成する。
・命中面の法線方向へ火花を放出する。生成位置は既存の ImpactPoint + ImpactNormal * 2 cm を使用。
・敵は約 0.70 秒の被弾モーションを再生し、元の待機／歩行／走行状態へ戻る。
・連続命中時は反応を先頭から再生し直す。
・HP、ApplyDamage、被弾による転倒、死亡処理は追加していない。

アセット
/Game/Effects/Weapons/NS_EnemyHitSparks
  既存 NS_RifleImpact を元にした敵専用 Niagara System。
  白黄色コア 32 cm / 0.20 秒。
  火花 38 個、長さ 10–18 cm、幅 2.5–4 cm、速度 700 cm/s、放射角 80 度。
  火花寿命 0.25–0.50 秒、System は一度だけ再生して自動破棄。
  既存の汎用着弾 FX と共有マテリアルは変更していない。

/Game/Main/Enemy/AdmissionRobot/AN_Admission_HitReact
  既存 MM_HitReact_Front_Lgt_01 を Blender で敵骨格へ変換。
  0.70 秒、非加算、既存 SK_AdmissionRobot_Skeleton を使用。
  入学承諾書と左手の位置関係を保ち、足は床上に固定。
  元の敵モデルおよび Idle / Walk / Run / Fall の FBX は変更していない。
  編集用 Blender と変換スクリプト:
  SourceAssets/Characters/AdmissionRobot/HitReact/

/Game/Main/Enemy/BP_AdmissionRobot
  ReactToBulletHit(ImpactPoint, ImpactNormal): 火花生成と被弾アニメーション開始。
  UpdateHitReaction: 再生終了後に元の状態へ復帰。
  新規変数: HitReactAnimation、IsHitReacting、HitReactEndTime。
  既存プレビュー動作は、よろけ再生中のみ一時停止する。
  既存 PlayFall は残すが、被弾処理から呼ばない。

/Game/Main/Character/You
  TraceShot に CastToBP_AdmissionRobot と ReactToBulletHit の 2 ノードを追加。
  敵なら専用火花、敵以外なら既存の汎用着弾 FX を実行。
  どちらも既存の弾痕生成へ合流する。
  他の 12 グラフはノード種類・位置・ピン値・接続すべて変更前と一致。
  旧 TraceShot の 41 ノードも種類・位置・ピン値を保持。最終 43 ノード。

命中判定
  敵の Capsule の Visibility 応答は Ignore のまま。
  敵 Mesh の Visibility を Block とし、QueryOnly を維持。
  SkeletalMesh と MeshComponent の PerPolyCollision を有効化し、
  既存の複雑な Visibility Trace で外形上の命中位置を取得する。

KDStage
  配置済み AdmissionRobot_Preview の PreviewEnabled を false に変更。
  自動で歩行・走行・転倒を繰り返す前回のデモを止め、射撃確認時は待機する。
  アクターの位置、ステージ、照明、PlayerStart は変更していない。

検証
  実際の左クリック射撃で火花、よろけ、待機への復帰を PIE で確認。
  Hit_HipFire.png は実際のゲーム内描画。画像生成による合成ではない。
  RuntimeVerification_Hip.json は射撃直後／反応中／復帰後の状態記録。
  ADS 保持入力の自動検証では IsADS が true にならず、ADS での実射確認は未完了。
  この確認のために ADS の実装は変更していない。共有の TraceShot を修正し、
  UpdateADS・Aim・Fire を含む他 12 グラフが不変であることを監査した。
  撮影用の時間倍率は 1.0 に戻し、画面メッセージ表示を復旧し、PIE を終了した。
  グラフ監査の原本:
  Saved/Automation/EnemyHit_20261113/final_graph_audit.json
  変更前のバックアップ:
  Saved/Automation/EnemyHit_20261113/Before/

調整箇所
  派手さは NS_EnemyHitSparks の発生数、サイズ、寿命、速度で調整する。
  モーションの差し替えは敵 BP の HitReactAnimation を変更する。
  実行時間はアニメーションの長さから取得する。

