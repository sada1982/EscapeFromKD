import bpy
import json
from pathlib import Path

root = Path(__file__).resolve().parent
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(root / 'MM_HitReact_Front_Lgt_01_Source.fbx'))
rig = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
report = {'objects': [(o.name, o.type, list(o.scale)) for o in bpy.context.scene.objects],
          'actions': [(a.name, list(a.frame_range)) for a in bpy.data.actions],
          'bones': [], 'poses': {}}
for b in rig.data.bones:
    report['bones'].append({'name': b.name, 'parent': b.parent.name if b.parent else None,
                            'head': list(b.head_local), 'tail': list(b.tail_local)})
for frame in (1, 3, 5, 8, 12, 16, 22):
    bpy.context.scene.frame_set(frame)
    report['poses'][str(frame)] = {b.name: {'loc': list(b.location),
         'quat': list(b.rotation_quaternion), 'euler': list(b.rotation_euler),
         'basis': [list(row) for row in b.matrix_basis],
         'matrix': [list(row) for row in b.matrix]} for b in rig.pose.bones}
(root / 'source_inspection.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('SOURCE_INSPECTION_COMPLETE', rig.name, len(rig.data.bones), report['actions'])
