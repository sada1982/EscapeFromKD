Escape From KD — 自宅環境でのCPU最適化
2026-11-13

結果
敵の毎フレームのポリゴン衝突更新が主なCPU負荷だった。
ボーンに追従する凸形状のPhysicsAssetへ変更し、描画モデル・画質を維持した。
自宅PCの測定範囲では60 FPSを上回った。全環境・全経路の最低値の保証ではない。

変更した実行データ
・Content/Main/Enemy/BP_AdmissionRobot.uasset
  CharacterMesh0: EnablePerPolyCollision true → false
  PhysicsAssetOverride None → PA_AdmissionRobot_HitCollision
・Content/Main/Stage/KDStage.umap
  配置済みAdmissionRobot_PreviewのCharacterMesh0にも上記2設定を適用。
・Content/Main/Enemy/AdmissionRobot/PA_AdmissionRobot_HitCollision.uasset（追加）
  21ボーン / 720凸形状。QueryOnly、UseSimpleAsComplex。
  新規uassetも既存.gitattributesによりGit LFS対象。

変更しなかった範囲
既存Content/Configの346ファイルを開始時のSHA256と照合し、変更は上記2件だけ。
You / BP_Rifle / BP_Floor03、敵の描画メッシュ・マテリアル・アニメーション、
元PhysicsAsset、ステージのメッシュ・衝突・照明、Configは同一。
SkeletalMeshアセット自身のPerPolyフラグは保持し、使用するMeshComponentで無効化。
射撃グラフや敵の反応グラフは編集していない。HP・死亡・AIは追加していない。
OptimizedV03の家具候補は引き続き未導入。

原因の確認
最初はPIE内の敵MeshComponentのPerPolyフラグだけを切り替えた。
同条件のA→B→A（各600フレーム、1280×722、Epic）:
                         平均FPS   GT Animation(ms)
  PerPoly ON               42.46      16.638
  PerPoly OFF             118.97       0.290
  PerPoly ONへ復帰          42.39      16.637
当たり判定を残した凸形状候補でも118.93 FPS / Animation 0.329 ms。
CPUトレースではUpdateKinematicBonesToAnim、SkinPerPolyVertices、
AABBTreeの更新負荷を確認。UE5.8.4のPhysAnim.cppのPerPoly分岐とも整合した。
CSVのAnimationカテゴリはアニメ再生だけでなく、この衝突更新も含んでいる。

1080pの測定
PC: Core i9-14900K / RTX 4080 SUPER 16 GB、UE5.8.4 CL58902052、D3D12 SM6。
浮動PIEウィンドウ。実際のViewportSize=1920×1080、r.ScreenPercentage=100。
Epic、VSync=0、t.MaxFPS=0、DynamicResolution=0。
TSR履歴200、VSM4096、Lumen Atlas4096、HWRT=1を維持。
各測定は10秒ウォームアップ後600フレーム。測定中はMCP操作・Slate観測なし。
バックグラウンド制限を計測時だけ解除し、終了時に元へ戻した。

                                      平均FPS  1% Low FPS  GT Animation(ms)
  変更前・実習室                       42.62      33.81        16.773
  候補・実習室                        118.03      66.47         0.354
  保存・PIE再開始後・実習室            114.18      51.54         0.375
  保存・PIE再開始後・廊下              117.75      72.46         0.368
  保存・PIE再開始後・階段前            119.06      68.18         0.322
  保存・PIE再開始後・連射              116.84      62.11         0.430

1% Lowは最も遅い6フレームの平均時間から算出。
表にはCSV開始直後の遅い1フレーム（約36～48ms）も含めた。
変更後の各CSVで60 FPS未満はこの先頭1フレームだけで、残り599フレームは
すべて60 FPS以上。先頭フレームを隠さず、別途csv_startup_frame_analysis.jsonに記録。
さらにCSVを起動しない通常動作を実習室で1200フレーム観測:
  平均118.56 FPS、最低77.82 FPS、1% Low 92.94 FPS、60 FPS未満0フレーム。
証拠はpassive_classroom.json。全ステージの絶対的な最低FPSを示す値ではない。

測定位置（UE cm、Pitch/Yaw）
実習室 (402,-73,98.15), (0,-90)
廊下 (-105,-850,98.15), (-3,90)
階段前 (-1100,350,98.15), (-8,180)
連射は階段前から既存IA_Fireへ入力を注入。測定用に照準を敵へ保持した。
リコイルの通常動作は別のGameplay検証で確認しており、連射計測中の照準保持は
本番グラフへの変更ではない。
VRAM使用量は約5.0～5.5GB。職場のRTX 3050 Laptop 4GBでは再測定が必要。
今回の自宅測定だけで職場環境の60 FPS達成とは扱わない。

命中精度と動作の確認
・Blenderの元メッシュ: 全頂点が単一ボーンへ100%ウェイトであることを検査。
・基準姿勢の68840本のレイ比較: 命中/非命中の差0。
  1mmを超える命中距離差25本、最大約1.77cm。細部をかすめる方向で発生。
・UEで同じ姿勢に固定して比較し、Idle / Walk / Run / Fall / HitReactを検査。
  合計129670本。従来当たるのに候補で抜ける例0本。
  従来非命中・候補命中は輪郭付近の3本。共通命中の平均位置差は各姿勢
  0.001～0.002cm程度、最大約1.054cm。法線にも細部の近似差がある。
  この方式はポリゴン単位の判定と数学的に完全一致するものではない。
・実際のEnhanced Input経由で腰だめ、ADS、連射、リロードを実行。
  ADS状態とADSAlpha=1、敵の火花・よろけ・待機復帰、連続命中時の反応を記録。
  腰だめ1発後の視点Pitchは-8→-7.2度。既存0.8度のリコイルを確認。
  リロード中/完了後の状態、射撃停止とADS解除を確認。
  保存後にPIEを再開始し、同じ確認を実施。
・入学承諾書の描画アセットは変更なし。ゲーム内の表示も確認。
・主要4BPはすべてBS_UP_TO_DATE。終了時PIE停止、未保存Map/Contentなし。

検証中に発生した問題
未保存の候補をPIEへ割り当てる試験で、PerPolyがONのままSetPhysicsAssetを
実行した後にOFFへ切り替え、UEの物理状態破棄アサーションで一度クラッシュした。
既存データを保存する前の試験であり、Content/Configの未変更を照合した。
Editorを再起動し、ユーザーが復元ダイアログを閉じてMCP接続を復旧。
UEのソースを確認し、先にPerPolyをOFF、その後PhysicsAssetを設定する順序へ修正。
以後の比較・保存・PIE再開始では同じ問題は発生していない。
採用BPに実行中の衝突方式切り替え処理は追加していない。

証拠と再生成
Evidence/Verification.json: 動作チェック、変更範囲、主要BP状態。
Evidence/FinalRuntimeSettings.json: 元の描画・計測設定への復旧記録。
Evidence/Measurements/: 全CSVの集計と条件。Evidence/CSV.zip: 生CSV10件。
Evidence/pose_suite.json / hull_ray_comparison.json: 命中比較。
Evidence/HipHit.png / ADSHit.png: 保存後の実射画像。
SourceAssets/Characters/AdmissionRobot/Collision/: 生成スクリプトと再生成手順。
詳細な試行・クラッシュログ・CPUトレースはSaved/Automation/HomeOptimization_20261113。
Gitコミット・プッシュは実施していない。
