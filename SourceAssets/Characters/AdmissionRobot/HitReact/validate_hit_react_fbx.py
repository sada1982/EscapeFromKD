import json
from pathlib import Path

import bpy


root = Path(__file__).resolve().parent
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(root.parent / 'Export' / 'SK_AdmissionRobot_All.fbx'))
reference = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
hierarchy = {b.name: b.parent.name if b.parent else None for b in reference.data.bones}
rest = {b.name: b.matrix_local.copy() for b in reference.data.bones}
reference_scale = list(reference.scale)
reference_action = next(a for a in bpy.data.actions if 'Idle' in a.name)
reference.animation_data.action = reference_action
bpy.context.scene.frame_set(int(reference_action.frame_range[0]))
bpy.context.view_layer.update()
reference_idle = {p.name: p.matrix.copy() for p in reference.pose.bones}
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(root / 'AN_Admission_HitReact.fbx'))
rig = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
result = {
    'reference_bones': len(hierarchy),
    'imported_bones': len(rig.data.bones),
    'hierarchy_identical': hierarchy == {b.name: b.parent.name if b.parent else None for b in rig.data.bones},
    'maximum_rest_matrix_error': max(abs(rest[b.name][r][c] - b.matrix_local[r][c]) for b in rig.data.bones for r in range(4) for c in range(4)),
    'reference_object_scale': reference_scale,
    'imported_object_scale': list(rig.scale),
    'imported_actions': [(a.name, list(a.frame_range)) for a in bpy.data.actions],
    'mesh_count': len([o for o in bpy.data.objects if o.type == 'MESH']),
}
bpy.context.scene.frame_set(int(rig.animation_data.action.frame_range[0]))
first = {p.name: p.matrix.copy() for p in rig.pose.bones}
result['start_vs_existing_idle_matrix_error'] = max(abs(reference_idle[p.name][r][c] - p.matrix[r][c]) for p in rig.pose.bones for r in range(4) for c in range(4))
bpy.context.scene.frame_set(int(rig.animation_data.action.frame_range[1]))
result['endpoint_matrix_error'] = max(abs(first[p.name][r][c] - p.matrix[r][c]) for p in rig.pose.bones for r in range(4) for c in range(4))
(root / 'fbx_roundtrip_validation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result))
