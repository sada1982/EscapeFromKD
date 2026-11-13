import hashlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector


ROOT = Path(__file__).resolve().parent
SOURCE_BLEND = ROOT.parent / 'AdmissionRobot_v01.blend'
SOURCE_FBX = ROOT / 'MM_HitReact_Front_Lgt_01_Source.fbx'
source_hash = hashlib.sha256(SOURCE_BLEND.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(SOURCE_BLEND))
scene = bpy.context.scene
rig = bpy.data.objects['AdmissionRig']
mesh = bpy.data.objects['SK_AdmissionRobot']
rig.animation_data.action = bpy.data.actions['AN_Admission_Idle']
scene.frame_set(1)
bpy.context.view_layer.update()
idle = {p.name: p.matrix.copy() for p in rig.pose.bones}
idle_basis = {p.name: p.matrix_basis.copy() for p in rig.pose.bones}
hierarchy = [(b.name, b.parent.name if b.parent else None) for b in rig.data.bones]
before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=str(SOURCE_FBX))
source_rig = next(o for o in bpy.data.objects if o not in before and o.type == 'ARMATURE')
source_action = source_rig.animation_data.action
source_poses = {}
for frame in range(1, 23):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    source_poses[frame] = {p.name: source_rig.matrix_world @ p.matrix for p in source_rig.pose.bones}
source_base = source_poses[1]
mapping = {'pelvis': 'pelvis', 'spine_01': 'spine_01', 'spine_02': 'spine_03',
           'spine_03': 'spine_05', 'neck': 'neck_02', 'head': 'head'}
for side in ('l', 'r'):
    for part in ('clavicle', 'upperarm', 'lowerarm', 'hand'):
        mapping[part + '_' + side] = part + '_' + side


def pose_matrix(rotation, position):
    matrix = rotation.to_matrix().to_4x4()
    matrix.translation = position
    return matrix


def solve_knee(hip, ankle, length1, length2, idle_hip, idle_knee):
    offset = ankle - hip
    distance = offset.length
    direction = offset.normalized()
    along = (length1 * length1 - length2 * length2 + distance * distance) / (2 * distance)
    height = math.sqrt(max(0, length1 * length1 - along * along))
    hint = idle_knee - idle_hip
    perpendicular = hint - direction * hint.dot(direction)
    if perpendicular.length < .001:
        hint = Vector((0, -1, 0))
        perpendicular = hint - direction * hint.dot(direction)
    return hip + direction * along + perpendicular.normalized() * height


def align_bone(name, head, tail):
    baseline = idle[name]
    direction0 = baseline.to_quaternion() @ Vector((0, 1, 0))
    rotation = direction0.rotation_difference((tail - head).normalized()) @ baseline.to_quaternion()
    return pose_matrix(rotation, head)


for obj in list(bpy.data.objects):
    if obj not in before:
        bpy.data.objects.remove(obj, do_unlink=True)
if source_action.users == 0:
    bpy.data.actions.remove(source_action)
action = bpy.data.actions.new('AN_Admission_HitReact')
action.use_fake_user = True
rig.animation_data.action = action
scene.render.fps = 30
scene.frame_start = 1
scene.frame_end = 22
scene.frame_set(1)
foot_errors = []
pelvis_reach_corrections = []
peak_angle = (0, 1)
for frame in range(1, 23):
    scene.frame_set(frame)
    matrices = {}
    source = source_poses[frame]
    displacement = source['pelvis'].translation - source_base['pelvis'].translation
    hip_offset = idle['pelvis'].translation + displacement
    for side in ('l', 'r'):
        thigh = rig.data.bones['thigh_' + side]
        calf = rig.data.bones['calf_' + side]
        ankle = idle['foot_' + side].translation
        hip = idle['thigh_' + side].translation + displacement
        limit = thigh.length + calf.length - .02
        horizontal = Vector((hip.x - ankle.x, hip.y - ankle.y, 0)).length
        highest = ankle.z + math.sqrt(max(0, limit * limit - horizontal * horizontal))
        if hip.z > highest:
            correction = hip.z - highest
            displacement.z -= correction
            hip_offset.z -= correction
            pelvis_reach_corrections.append([frame, correction])
    for bone in rig.data.bones:
        name = bone.name
        if frame in (1, 22):
            matrices[name] = idle[name].copy()
            continue
        if bone.parent:
            parent_name = bone.parent.name
            inherited = matrices[parent_name] @ idle[parent_name].inverted() @ idle[name]
        else:
            inherited = idle[name].copy()
        if name in mapping:
            src_name = mapping[name]
            delta = source[src_name].to_quaternion() @ source_base[src_name].to_quaternion().inverted()
            rotation = delta @ idle[name].to_quaternion()
            position = hip_offset if name == 'pelvis' else inherited.translation
            matrices[name] = pose_matrix(rotation, position)
            if name == 'head' and delta.angle > peak_angle[0]:
                peak_angle = (delta.angle, frame)
        else:
            matrices[name] = inherited
    if frame not in (1, 22):
        for side in ('l', 'r'):
            thigh_name = 'thigh_' + side
            calf_name = 'calf_' + side
            foot_name = 'foot_' + side
            ball_name = 'ball_' + side
            hip = matrices[thigh_name].translation
            ankle = idle[foot_name].translation
            length1 = (idle[calf_name].translation - idle[thigh_name].translation).length
            length2 = (idle[foot_name].translation - idle[calf_name].translation).length
            knee = solve_knee(hip, ankle, length1, length2,
                              idle[thigh_name].translation, idle[calf_name].translation)
            matrices[thigh_name] = align_bone(thigh_name, hip, knee)
            matrices[calf_name] = align_bone(calf_name, knee, ankle)
            matrices[foot_name] = idle[foot_name].copy()
            matrices[ball_name] = idle[ball_name].copy()
    for bone in rig.data.bones:
        pose = rig.pose.bones[bone.name]
        pose.matrix = matrices[bone.name]
        bpy.context.view_layer.update()
        pose.rotation_mode = 'QUATERNION'
        pose.keyframe_insert('location', frame=frame, group=pose.name)
        pose.keyframe_insert('rotation_quaternion', frame=frame, group=pose.name)
        pose.keyframe_insert('scale', frame=frame, group=pose.name)
    foot_errors.append(max((rig.pose.bones['foot_' + side].matrix.translation - idle['foot_' + side].translation).length for side in ('l', 'r')))

validation = {'source_asset': '/Game/Characters/Mannequins/Anims/Rifle/HitReact/MM_HitReact_Front_Lgt_01',
              'source_fbx_sha256': hashlib.sha256(SOURCE_FBX.read_bytes()).hexdigest(),
              'original_blend_sha256_before': source_hash,
              'action': action.name, 'duration_seconds': .7, 'fps': 30, 'keys': 22,
              'bone_hierarchy': hierarchy, 'rotation_mapping': mapping,
              'method': 'World-space rotation deltas from source frame 0 over Admission Idle; five source spine joints mapped to three target joints. Pelvis translation retained, two-bone foot planting, hand-local clipboard unchanged. Exact Idle at both ends.',
              'max_foot_drift_cm': max(foot_errors), 'pelvis_reach_corrections_cm': pelvis_reach_corrections,
              'peak_head_delta_degrees': math.degrees(peak_angle[0]), 'peak_frame': peak_angle[1]}
minimum_z = []
grip_errors = []
idle_grip = idle['hand_l'].inverted() @ idle['document']
for frame in range(1, 23):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = mesh.evaluated_get(depsgraph)
    evaluated_mesh = evaluated.to_mesh()
    minimum_z.append(min((evaluated.matrix_world @ vertex.co).z for vertex in evaluated_mesh.vertices))
    evaluated.to_mesh_clear()
    grip = rig.pose.bones['hand_l'].matrix.inverted() @ rig.pose.bones['document'].matrix
    grip_errors.append(max(abs(grip[row][col] - idle_grip[row][col]) for row in range(4) for col in range(4)))
validation['minimum_geometry_z_cm'] = min(minimum_z)
validation['max_clipboard_relative_error'] = max(grip_errors)
validation['final_idle_matrix_error'] = max(abs(rig.pose.bones[name].matrix[row][col] - idle[name][row][col]) for name in idle for row in range(4) for col in range(4))
bpy.ops.object.select_all(action='DESELECT')
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
scene.frame_set(1)
bpy.ops.export_scene.fbx(filepath=str(ROOT / 'AN_Admission_HitReact.fbx'), check_existing=False,
    use_selection=True, object_types={'ARMATURE'}, axis_forward='-Y', axis_up='Z',
    apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', use_space_transform=True,
    bake_space_transform=False, add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X',
    use_armature_deform_only=True, armature_nodetype='NULL', bake_anim=True,
    bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False, bake_anim_use_all_actions=False,
    bake_anim_force_startend_keying=True, bake_anim_step=1.0, bake_anim_simplify_factor=0.0)
scene.frame_set(peak_angle[1])
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / 'AdmissionRobot_HitReact.blend'))
validation['original_blend_sha256_after'] = hashlib.sha256(SOURCE_BLEND.read_bytes()).hexdigest()
validation['original_source_unchanged'] = validation['original_blend_sha256_after'] == source_hash
(ROOT / 'hit_react_validation.json').write_text(json.dumps(validation, indent=2), encoding='utf-8')
scene.render.resolution_x = 900
scene.render.resolution_y = 900
scene.cycles.samples = 24
for label, frame in (('Idle', 1), ('Peak', peak_angle[1])):
    scene.frame_set(frame)
    scene.render.filepath = str(ROOT / ('HitReact_' + label + '.png'))
    bpy.ops.render.render(write_still=True)
print('HIT_REACT_COMPLETE', json.dumps(validation))
