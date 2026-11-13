AdmissionRobot HitReact - existing mannequin motion conversion

Source animation:
/Game/Characters/Mannequins/Anims/Rifle/HitReact/MM_HitReact_Front_Lgt_01
The original UE asset was exported through Animation Editor > Export Asset >
Animation Data. The source asset was not edited or saved.
MM_HitReact_Front_Lgt_01_Source.fbx is the unchanged exported source.

Output:
AN_Admission_HitReact.fbx: animation-only FBX, one take, no mesh.
AdmissionRobot_HitReact.blend: new source copy, original robot geometry and rig,
existing four actions plus AN_Admission_HitReact, saved at the reaction peak.
The existing AdmissionRobot_v01.blend and Export/ files were not modified.

Import into Unreal:
Choose the existing AdmissionRobot Skeleton, disable mesh import, enable animation.
Import as a new AnimSequence named AN_Admission_HitReact. Do not update the skeleton
reference pose and do not reimport the existing skeletal mesh.
Duration: 0.70 seconds, 30 fps, 22 keys, non-looping.
The FBX take is named AdmissionRig|Scene. Blender FBX roundtrip presents frames
2..23 because of the FBX start-time offset; the elapsed duration remains 0.70 s.
Play once, then return to the existing Idle animation.

Conversion:
Actual source frame-zero rotation deltas are applied over AdmissionRobot Idle.
Source spine_01/spine_03/spine_05 map to the robot's three spine bones; neck_02
maps to neck. Source head and arm changes retain their original timing.
Pelvis translation is retained; the legs receive two-bone IK to keep the enemy's
different proportions grounded. Root stays stationary. The document bone retains
its fixed transform relative to hand_l, so the paper remains physically held.
First and last frames match Idle exactly. This is a conversion of the existing
Manny reaction, not an unrelated newly authored stagger.

Checks:
24 bone hierarchy and FBX units match the existing robot export.
After FBX roundtrip, first pose differs from existing Idle by at most 0.00013 cm.
First/last FBX pose matrix difference is below 0.000008 cm.
Maximum foot movement: 0.0000022 cm. Geometry stays above floor Z=0.
Maximum document/hand relative matrix difference: 0.000034.
Blender treats the first pose of a mesh-free FBX as its bind/rest pose because
there is no skin bind-pose record. Compare animation poses, not that reconstructed
rest pose, when validating an animation-only import against a skinned FBX.

QA images: HitReact_Idle.png, HitReact_Peak.png.
Reports: hit_react_validation.json, fbx_roundtrip_validation.json.
Rebuild with Blender 5.3 background mode and retarget_hit_react.py.
