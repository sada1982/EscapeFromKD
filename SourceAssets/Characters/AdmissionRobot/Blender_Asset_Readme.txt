Admission Robot / Blender source
2026-11-13

AdmissionRobot_v01.blend is the editable source. Blender 5.3 was used.
The approved concept drawings in Concepts were preserved.

The character is a dedicated segmented humanoid model with a custom 24-bone
deformation rig. It follows the player's humanoid proportions and material
language; it is not the full Manny skeleton and does not claim drop-in Manny
animation compatibility. Armor pieces have rigid bone weights, with dark
overlapping joint housings. The paper and clipboard are rigid geometry bound
to the document bone, a child of hand_l. The paper texture is packed in the
blend and also supplied separately in Textures.

Blender uses metric unit scale 0.01. Mesh coordinates, rest bones and animation
translations are authored/exported in centimeters, with object scale 1.
Character neutral height is approximately 189 cm. Forward is Blender -Y;
up is Z. Verify the imported facing direction on the UE mesh component.

Import Export/SK_AdmissionRobot_All.fbx as a skeletal mesh with animations.
It contains these four animation takes at 30 fps:
  AN_Admission_Idle: 2.0 seconds, looping.
  AN_Admission_Walk: 1.0 second, looping, intended translation 90 cm/s.
  AN_Admission_Run: 0.666667 second, looping, intended translation 180 cm/s.
  AN_Admission_Fall: 1.6 seconds, one shot, holds the side-fall end pose.
Walk and Run are in-place. Actor movement must provide their translation.
Fall should not loop. Keep the actor at its standing floor origin during Fall.
The FBX exporter prefixes take names with AdmissionRig|.
Separate skeletal FBX files for each action and a standalone clipboard FBX
are included as source/export alternatives; do not instantiate both clipboard
versions on the same enemy because the main skeletal mesh already holds one.

The paper title is 入学承諾書 and its two choices are はい and YES.
Material slots in the primary mesh:
  0 M_Admission_Joint
  1 M_Admission_Ivory
  2 M_Admission_Titanium
  3 M_Admission_Grip
  4 M_Admission_Agreement
  5 M_Admission_Cyan

build_agreement_texture.py generates the printable paper texture with the
installed Yu Gothic fonts through Pillow. build_admission_robot.py builds
the Blender asset, exports FBX and renders Idle/Walk/Run/Fall previews.
validate_admission_robot.py checks weights, loops, document attachment,
per-frame ground bounds and raw FBX dimensions/action stacks. The measured
results are in build_report.json and validation_report.json.

All source changes in this subtask are limited to this AdmissionRobot folder.
Unreal import, Blueprint behavior and PIE verification are separate steps.
