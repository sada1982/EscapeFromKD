Escape From KD — 入学承諾書ロボット 初版
作成・確認日: 2026-11-13

1. 完成内容
Blender 5.3で白銀装甲・暗い関節・シアンの顔ラインを持つ人型ロボットを作成した。
左手にクリップボードを持ち、紙面の表題は「入学承諾書」、選択肢は「はい」「YES」。
紙面に「強制」は記載していない。
独自リグに待機・歩行・走行・転倒を作成し、FBX経由でUEへ導入した。
KDStageに1体配置し、プレイヤーYouが存在するPIEで表示と各モーション・移動を確認した。

2. 主なファイル
編集元:
SourceAssets/Characters/AdmissionRobot/AdmissionRobot_v01.blend
UEへ読み込んだFBX:
SourceAssets/Characters/AdmissionRobot/Export/SK_AdmissionRobot_All.fbx
紙面:
SourceAssets/Characters/AdmissionRobot/Textures/T_AdmissionAgreement_BaseColor.png

UE Blueprint:
Content/Main/Enemy/BP_AdmissionRobot
UEモデル・Skeleton・PhysicsAsset・アニメーション:
Content/Main/Enemy/AdmissionRobot/
UEマテリアル:
Content/Main/Enemy/AdmissionRobot/Materials/
UE紙面テクスチャ:
Content/Main/Enemy/AdmissionRobot/Textures/

モデル生成・検証スクリプトと詳細レポートはBlender元ファイルと同じフォルダ。
BP構築に使用したMCPスクリプトは:
Saved/Automation/AdmissionRobot_20261113/build_enemy_blueprint_toolscript.py
この補助スクリプトは現在のプロジェクト内で必要な変数・関数を用意した後に実行したもの。
単独実行による新規プロジェクトの自動構築を保証するものではない。

3. ゲーム中で確認する方法
KDStageを開いて通常のPIEを開始し、実習室から廊下を通って階段・エレベーター前へ進む。
配置ActorのラベルはAdmissionRobot_Preview。
位置はX=-1400、Y=350、Z=98.15cm、Yaw=0。
確認ループ:
  待機2秒
  歩行3秒（90cm/s）
  180度向きを変え、待機0.3秒
  走行1.5秒（180cm/s）
  転倒1.6秒、その後約3秒最終姿勢を維持
  開始位置へ戻って繰り返す
通常のPlayerStartおよびYouの入力は変更していない。

BPのPreview Enabledは初期値false。KDStageの確認用インスタンスだけtrue。
このフラグは開始時に確認ループを起動するための設定。
停止した状態で見たい場合は、PIE開始前にこのインスタンスのPreview Enabledをfalseにする。
ゲーム本来の移動やAIを作る際は確認用フラグをfalseにして専用処理から各関数を呼ぶ。

4. アニメーションと呼び出し口
PlayIdle: Idleをループ再生、移動停止。
PlayWalk: Walkをループ再生、歩行速度90cm/sを設定。
PlayRun: Runをループ再生、走行速度180cm/sを設定。
PlayFall: 移動を停止・無効化し、Fallを1回再生して最終姿勢を保持。
ResetPreview: 開始位置・向きを復元し、待機へ戻す。

歩行・走行の前進はPreview Enabledがtrueかつ対象状態のとき、
Event TickのAddMovementInputで行う。PlayWalk/PlayRun単独に経路探索処理はない。
Idle 2.0秒 / Walk 1.0秒 / Run 約0.667秒 / Fall 1.6秒。
歩行・走行はルート移動を含まないin-placeアニメーション。
使用方式はAnimationSingleNode。今回の初版ではAnimation Blueprintによるブレンドは未実装。
独自24変形ボーンのリグで、UEではAdmissionRig親を含め25ボーン。
Mannyアニメーションをそのまま流用できる構成ではない。
転倒は自作アニメーションで、物理ラグドールではない。

5. 寸法・接地・書類
中立姿勢の頭頂高は約189cm。FBXの実座標とアニメーション移動量はcm、scaleは1。
UEインポート後のモデルBounds高さは約188.20cm（最低点0.8cm、最高点189.0cm）。
CharacterMesh0相対位置Z=-98.5cm、相対Yaw=-90度、scale=1。
Capsule半径34cm、Half Height96cm。
26,375頂点、52,084三角形、6マテリアルスロット。
書類とクリップボードは主Skeletal Meshに含まれ、documentボーンがhand_lに追従する。
別出力SM_AdmissionClipboard.fbxは代替素材。現在のBPへ追加すると二重になる。

6. 確認結果
Blender:
  未ウェイト頂点0、ウェイト合計誤差0。
  待機・歩行・走行のループ境界一致。
  全フレームの最低点と書類の手への追従を数値確認。
UE:
  モデルのcmスケール、4アニメーション、マテリアルを確認。
  BPはwarnings_as_errors=trueでコンパイル成功。
  PIEで歩行90cm/s、走行180cm/s、転倒時速度0と停止を確認。
  転倒の最終姿勢、開始位置への復帰、複数周回を確認。
  Blueprint Runtime Error / Accessed None / 敵関連Errorのログ検索結果は0件。
  実際のPIE画像を同じ資料フォルダへ保存。
詳細はVerification.jsonとBlender側validation_report.jsonを参照。
すべてのポーズ間の身体干渉や別スケルトンへのリターゲットは検証対象外。

7. 変更範囲と次工程
変更した既存LevelはKDStage（確認用Actorを1体追加）。
新規Enemyアセット、Blender元データ、FBX、検証画像・資料を追加。
You BP、既存の銃・射撃処理、ライティング、プロジェクト設定は変更していない。
You.uassetのSHA256が作業前後で一致し、作業前からの未保存状態も維持している。
撮影中だけ画面メッセージを非表示にし、撮影後は有効へ戻した。PIEは終了済み。

追跡AI・攻撃・被弾ダメージ・射撃から転倒への接続は今回の対象外。
今後、敵の行動と被弾処理を追加し、今回の移動・転倒モーションへ接続する。
既存のVRAM予算超過警告の原因対処は行っていない。

8. 証拠画像
UE_Agreement_Closeup.png: プレイヤー視点の敵と承諾書
UE_Idle.png: 待機
UE_Walk.png: 歩行
UE_Run.png: 走行
UE_Fall.png: 転倒
すべて実際のUE PIEから撮影した画像。
