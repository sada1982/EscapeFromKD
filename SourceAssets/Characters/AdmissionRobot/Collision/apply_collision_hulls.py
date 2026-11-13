import json
from pathlib import Path
import unreal

out = Path(unreal.Paths.project_dir()).resolve()/'Saved/Automation/AdmissionRobotCollision'
assert not unreal.EditorLevelLibrary.get_pie_worlds(False), 'Stop PIE before editing collision assets'
mesh = unreal.load_asset('/Game/Main/Enemy/AdmissionRobot/SK_AdmissionRobot')
modifier = unreal.SkeletonModifier()
assert modifier.set_skeletal_mesh(mesh)
poses = {str(b):modifier.get_bone_transform(b, True) for b in modifier.get_all_bone_names()}
pa = unreal.load_asset('/Game/Main/Enemy/AdmissionRobot/PA_AdmissionRobot_HitCollision')
bodies = {str(o.get_editor_property('BoneName')):o for o in unreal.ObjectIterator()
          if o.get_outer()==pa and o.get_class().get_name()=='SkeletalBodySetup'}
groups = {}
def vec(v): return '(X=%.9f,Y=%.9f,Z=%.9f)'%(v.x,v.y,v.z)
for index,hull in enumerate(json.loads((out/'collision_hulls.json').read_text())['hulls']):
    pose = poses[hull['bone']]
    vertices = [unreal.MathLibrary.inverse_transform_location(pose,unreal.Vector(x,-y,z))
                for x,y,z in hull['vertices_blender_cm']]
    low = unreal.Vector(min(v.x for v in vertices),min(v.y for v in vertices),min(v.z for v in vertices))
    high = unreal.Vector(max(v.x for v in vertices),max(v.y for v in vertices),max(v.z for v in vertices))
    indices = [str(i) for tri in hull['triangles'] for i in reversed(tri)]
    text = '(VertexData=('+','.join(vec(v) for v in vertices)+'),IndexData=('+','.join(indices)+'),ElemBox=(Min='+vec(low)+',Max='+vec(high)+',IsValid=True),Name="HitHull_%d",CollisionEnabled=QueryOnly)'%index
    convex = unreal.KConvexElem()
    assert convex.import_text(text)
    groups.setdefault(hull['bone'],[]).append(convex)
assert set(groups)==set(bodies)
for bone,elements in groups.items():
    geometry = unreal.KAggregateGeom()
    geometry.set_editor_property('ConvexElems',elements)
    bodies[bone].set_editor_property('AggGeom',geometry)
    bodies[bone].set_editor_property('CollisionTraceFlag',unreal.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX)
(out/'applied_collision.json').write_text(json.dumps({b:len(e) for b,e in groups.items()},indent=2),encoding='utf-8')
print('COLLISION_HULLS_APPLIED')
