import json
import math
from pathlib import Path

import bpy
from io_scene_fbx import parse_fbx


ROOT = Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'AdmissionRobot_v01.blend'))
rig=bpy.data.objects['AdmissionRig']
body=bpy.data.objects['SK_AdmissionRobot']
report={'bone_count':len(rig.data.bones),'vertex_count':len(body.data.vertices),'uv_layers':[layer.name for layer in body.data.uv_layers],'unit_scale':bpy.context.scene.unit_settings.scale_length,'packed_images':[im.name for im in bpy.data.images if im.packed_file],'actions':{}}
report['unweighted_vertices']=sum(1 for vertex in body.data.vertices if not vertex.groups)
report['max_weight_sum_error']=max(abs(sum(group.weight for group in vertex.groups)-1) for vertex in body.data.vertices)
for kind,length in [('Idle',60),('Walk',30),('Run',20),('Fall',48)]:
    rig.animation_data.action=bpy.data.actions['AN_Admission_'+kind]
    mins=[]
    maxs=[]
    first_pose=None
    doc_relative=None
    doc_error=0
    for frame in range(1,length+2):
        bpy.context.scene.frame_set(frame)
        evaluated=body.evaluated_get(bpy.context.evaluated_depsgraph_get())
        z=[(evaluated.matrix_world@v.co).z for v in evaluated.data.vertices]
        mins.append(min(z))
        maxs.append(max(z))
        pose=[list(bone.matrix[row]) for bone in rig.pose.bones for row in range(4)]
        relative=rig.pose.bones['hand_l'].matrix.inverted()@rig.pose.bones['document'].matrix
        if first_pose is None:
            first_pose=pose
            doc_relative=relative.copy()
        doc_error=max(doc_error,max(abs(relative[row][column]-doc_relative[row][column]) for row in range(4) for column in range(4)))
    loop_error=max(abs(pose[row][column]-first_pose[row][column]) for row in range(len(pose)) for column in range(4))
    report['actions'][kind]={'frames':length+1,'min_z_cm':min(mins),'max_z_cm':max(maxs),'last_min_z_cm':mins[-1],'last_max_z_cm':maxs[-1],'loop_matrix_error':loop_error if kind!='Fall' else None,'document_hand_relative_matrix_error':doc_error}
tree,version=parse_fbx.parse(str(ROOT/'Export/SK_AdmissionRobot_All.fbx'))
report['fbx_version']=version
raw_vertices=[]
stacks=[]
def visit(element):
    if element.id==b'Vertices':
        raw_vertices.extend(element.props[0])
    if element.id==b'AnimationStack':
        stacks.append(str(element.props[1]))
    for child in element.elems:
        visit(child)
visit(tree)
report['fbx_native_mesh_bounds']={'min':[min(raw_vertices[i::3]) for i in range(3)],'max':[max(raw_vertices[i::3]) for i in range(3)]}
report['fbx_animation_stacks']=stacks
report['all_vertex_coordinates_finite']=all(math.isfinite(value) for value in raw_vertices)
(ROOT/'validation_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(report,indent=2,ensure_ascii=False))
