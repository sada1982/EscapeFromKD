import json
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

root = Path(__file__).resolve().parents[4]
out = root / 'Saved/Automation/AdmissionRobotCollision'
out.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(root / 'SourceAssets/Characters/AdmissionRobot/AdmissionRobot_v01.blend'))
obj = bpy.data.objects['SK_AdmissionRobot']
mesh = obj.data
mesh.calc_loop_triangles()
parents = list(range(len(mesh.vertices)))
def find(i):
    while parents[i] != i:
        parents[i] = parents[parents[i]]
        i = parents[i]
    return i
for edge in mesh.edges:
    a,b = edge.vertices
    parents[find(a)] = find(b)
islands = {}
for vertex in mesh.vertices:
    islands.setdefault(find(vertex.index), []).append(vertex.index)
triangles = {}
for tri in mesh.loop_triangles:
    triangles.setdefault(find(tri.vertices[0]), []).append(list(tri.vertices))
hulls = []
def split_polygons(polygons, axis, middle, sign):
    result = []
    for polygon in polygons:
        clipped = []
        for a,b in zip(polygon,polygon[1:]+polygon[:1]):
            da,db = (a[axis]-middle)*sign,(b[axis]-middle)*sign
            if da <= 0.000001: clipped.append(a)
            if (da < 0 and db > 0) or (da > 0 and db < 0):
                clipped.append(a+(b-a)*(da/(da-db)))
        if len(clipped) >= 3: result.append(clipped)
    return result

def make_hulls(polygons, original, bone, island, depth=0):
    points = {tuple(round(c,6) for c in v):v for p in polygons for v in p}
    if len(points) < 4: return
    bm = bmesh.new()
    for point in points.values(): bm.verts.new(point)
    bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
    used = {v for f in bm.faces for v in f.verts}
    unused = [v for v in bm.verts if v not in used]
    if unused: bmesh.ops.delete(bm,geom=unused,context='VERTS')
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    bm.verts.index_update()
    volume = abs(bm.calc_volume())
    if volume < 0.000001:
        bm.free()
        return
    samples = [sum((v.co for v in f.verts), Vector())/len(f.verts) for f in bm.faces]
    samples += [(e.verts[0].co+e.verts[1].co)*0.5 for e in bm.edges]
    errors = []
    for point in samples:
        nearest,normal,index,distance = original.find_nearest(point)
        if (point-nearest).dot(normal)>0.00001: errors.append(distance)
    max_error = max(errors,default=0)
    if max_error > 0.05 and depth < 12:
        low = [min(p[i] for p in points.values()) for i in range(3)]
        high = [max(p[i] for p in points.values()) for i in range(3)]
        axis = max(range(3),key=lambda i:high[i]-low[i])
        middle = (low[axis]+high[axis])*0.5
        bm.free()
        for side in [-1,1]: make_hulls(split_polygons(polygons,axis,middle,side),original,bone,island,depth+1)
        return
    hulls.append({'bone':bone,'island':island,'volume_cm3':volume,'depth':depth,
                  'max_hull_surface_error_cm':max_error,
                  'vertices_blender_cm':[list(v.co) for v in bm.verts],
                  'triangles':[[v.index for v in f.verts] for f in bm.faces]})
    bm.free()

for island, indices in islands.items():
    weights = [mesh.vertices[i].groups for i in indices]
    assert all(len(g) == 1 and abs(g[0].weight-1) < 0.00001 for g in weights)
    bone = obj.vertex_groups[weights[0][0].group].name
    assert all(obj.vertex_groups[g[0].group].name == bone for g in weights)
    positions = [obj.matrix_world @ mesh.vertices[i].co for i in indices]
    mapping = {i:j for j,i in enumerate(indices)}
    faces = [[mapping[i] for i in t] for t in triangles[island]]
    original = BVHTree.FromPolygons(positions,faces,all_triangles=True)
    make_hulls([[positions[i] for i in face] for face in faces],original,bone,island)
(out/'collision_hulls.json').write_text(json.dumps({'hulls':hulls},indent=2),encoding='utf-8')
print('HULL_AUDIT',json.dumps({'count':len(hulls),'vertices':sum(len(h['vertices_blender_cm']) for h in hulls),
    'concave':[ {k:v for k,v in h.items() if k not in ['vertices_blender_cm','triangles']} for h in hulls if h['max_hull_surface_error_cm']>0.1],
    'flat':[h['island'] for h in hulls if h['volume_cm3']<0.0001]}),flush=True)
