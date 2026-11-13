import hashlib
import json
import math
import sys
from array import array
from collections import defaultdict
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = Path(__file__).resolve().parent
SOURCE = ROOT / 'SurveyV02' / 'EscapeFromKD_Floor03_v02.blend'
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from export_floor03_fbx import bounds, copy_mesh, write_fbx
from export_floor03_survey import repair_degenerate_uv, remove_degenerate_faces

MAIN_CHAIR_RATIO = 0.50
CAD_CHAIR_RATIO = 0.25
SLED_CHAIR_RATIO = 0.50
GROUPS = ['Structure','Ceilings','ClosedClassrooms','ClassroomFixtures','GlazingFrames',
          'Glass','Corridors','StairCore','Desks','Chairs','Laptops','Mice']


def triangles(mesh):
    mesh.calc_loop_triangles()
    return len(mesh.loop_triangles)


def geometry_hash(mesh):
    digest = hashlib.sha256()
    for values, field, width, code in [(mesh.vertices,'co',3,'f'),
                                       (mesh.loops,'vertex_index',1,'i'),
                                       (mesh.polygons,'material_index',1,'i')]:
        buffer = array(code, [0]) * (len(values) * width)
        values.foreach_get(field, buffer)
        digest.update(buffer.tobytes())
    for layer in mesh.uv_layers:
        buffer = array('f', [0]) * (len(layer.data) * 2)
        layer.data.foreach_get('uv', buffer)
        digest.update(buffer.tobytes())
    return digest.hexdigest()


def snapshot():
    result = {}
    for group in GROUPS:
        result[group] = []
        for obj in bpy.data.collections['Survey_' + group].objects:
            entry = {'name':obj.name,'matrix':[list(row) for row in obj.matrix_world],
                     'materials':[m.name if m else None for m in obj.data.materials]}
            if obj.type == 'MESH':
                entry['geometry_hash'] = geometry_hash(obj.data)
            elif obj.type == 'FONT':
                entry['text'] = obj.data.body
            result[group].append(entry)
        result[group].sort(key=lambda item: item['name'])
    return result


def surface_error(original, reduced):
    def bvh(mesh):
        return BVHTree.FromPolygons([v.co.copy() for v in mesh.vertices],
                                   [tuple(p.vertices) for p in mesh.polygons])
    def distance(source, target):
        tree = bvh(target)
        samples = [v.co for v in source.vertices] + [p.center for p in source.polygons]
        distances = [tree.find_nearest(point)[3] for point in samples]
        if any(value is None for value in distances):
            raise RuntimeError('Surface distance could not be measured')
        return max(distances), sum(distances)/len(distances)
    forward = distance(original, reduced)
    backward = distance(reduced, original)
    return {'max_m':max(forward[0],backward[0]),'mean_m':(forward[1]+backward[1])/2}


def reduce_chair(source, ratio, name):
    obj = source.copy()
    obj.data = source.data.copy()
    bpy.context.scene.collection.objects.link(obj)
    obj.hide_set(False)
    obj.hide_viewport = False
    bpy.context.view_layer.objects.active = obj
    modifier = obj.modifiers.new('FurnitureReduction', 'DECIMATE')
    modifier.ratio = ratio
    modifier.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    mesh = obj.data
    mesh.name = name
    error = surface_error(source.data, mesh)
    result = {'ratio':ratio,'before_triangles':triangles(source.data),
              'after_triangles':triangles(mesh),'surface_distance':error,
              'materials':[m.name for m in mesh.materials]}
    assert error['max_m'] < (0.006 if ratio >= 0.5 else 0.012), result
    assert result['materials'] == [m.name for m in source.data.materials]
    assert len(mesh.uv_layers) == len(source.data.uv_layers)
    bpy.data.objects.remove(obj, do_unlink=True)
    return mesh, result


def mesh_components(mesh):
    neighbors = defaultdict(set)
    for edge in mesh.edges:
        a,b = edge.vertices
        neighbors[a].add(b)
        neighbors[b].add(a)
    unseen = set(range(len(mesh.vertices)))
    components = []
    while unseen:
        seed = unseen.pop()
        members = {seed}
        pending = [seed]
        while pending:
            for neighbor in neighbors[pending.pop()]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    members.add(neighbor)
                    pending.append(neighbor)
        components.append(members)
    return components


def simplify_keyboard(source):
    mesh = source.data
    keyboard_slot = next(i for i,m in enumerate(mesh.materials) if m.name == 'KD_F03_LaptopKeyboard')
    selected = []
    for members in mesh_components(mesh):
        polygons = [p for p in mesh.polygons if p.vertices[0] in members]
        if set(p.material_index for p in polygons) != {keyboard_slot}:
            continue
        coords = [mesh.vertices[i].co for i in members]
        low = [min(v[i] for v in coords) for i in range(3)]
        high = [max(v[i] for v in coords) for i in range(3)]
        if high[2]-low[2] <= 0.0021:
            selected.append((members, polygons, low, high))
    assert len(selected) == 62, len(selected)
    removed_vertices = set().union(*(item[0] for item in selected))
    vertices = []
    remap = {}
    for vertex in mesh.vertices:
        if vertex.index not in removed_vertices:
            remap[vertex.index] = len(vertices)
            vertices.append(tuple(vertex.co))
    faces = []
    materials = []
    smooth = []
    uv_faces = {layer.name:[] for layer in mesh.uv_layers}
    for polygon in mesh.polygons:
        if polygon.vertices[0] in removed_vertices:
            continue
        faces.append(tuple(remap[i] for i in polygon.vertices))
        materials.append(polygon.material_index)
        smooth.append(polygon.use_smooth)
        for layer in mesh.uv_layers:
            uv_faces[layer.name].append([tuple(layer.data[i].uv) for i in polygon.loop_indices])
    corner_bits = [(0,0,0),(1,0,0),(1,1,0),(0,1,0),(0,0,1),(1,0,1),(1,1,1),(0,1,1)]
    box_faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    normals = [Vector(n) for n in [(0,0,-1),(0,0,1),(0,-1,0),(1,0,0),(0,1,0),(-1,0,0)]]
    for members, polygons, low, high in selected:
        corners = [Vector([high[i] if bit[i] else low[i] for i in range(3)]) for bit in corner_bits]
        offset = len(vertices)
        vertices.extend(tuple(v) for v in corners)
        for face, normal in zip(box_faces, normals):
            faces.append(tuple(offset+i for i in face))
            materials.append(keyboard_slot)
            smooth.append(False)
            planar = max((p for p in polygons if p.normal.dot(normal)>0.999), key=lambda p:p.area)
            axis = max(range(3),key=lambda i:abs(normal[i]))
            axes = [i for i in range(3) if i != axis]
            ids = list(planar.loop_indices)
            points = [mesh.vertices[mesh.loops[i].vertex_index].co for i in ids]
            basis = Matrix([(points[i][axes[0]],points[i][axes[1]],1.0) for i in range(3)])
            assert abs(basis.determinant()) > 1e-14
            for layer in mesh.uv_layers:
                original_uv = [layer.data[i].uv for i in ids]
                coefficients = [basis.inverted() @ Vector([original_uv[i][j] for i in range(3)]) for j in range(2)]
                uv_faces[layer.name].append([
                    tuple(c.dot(Vector((corners[i][axes[0]],corners[i][axes[1]],1.0))) for c in coefficients)
                    for i in face])
    result = bpy.data.meshes.new('F03V03_Laptop_KeyBevelReduced')
    result.from_pydata(vertices,[],faces)
    for material in mesh.materials:
        result.materials.append(material)
    for polygon,index,use_smooth in zip(result.polygons,materials,smooth):
        polygon.material_index=index
        polygon.use_smooth=use_smooth
    for name,values in uv_faces.items():
        layer=result.uv_layers.new(name=name)
        for polygon,uvs in zip(result.polygons,values):
            for index,uv in zip(polygon.loop_indices,uvs):
                layer.data[index].uv=uv
    result.update()
    return result, {'selected_key_parts':len(selected),'before_triangles':triangles(mesh),
                    'after_triangles':triangles(result),'surface_distance':surface_error(mesh,result)}


def main():
    source_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    before=snapshot()
    report={'source':str(SOURCE),'source_sha256':source_hash,'chairs':{},'groups':[]}
    chairs=list(bpy.data.collections['Survey_Chairs'].objects)
    presets=[('main',('GameLab_chair','Instructor_chair'),MAIN_CHAIR_RATIO),
             ('cad',('CADLab_chair',),CAD_CHAIR_RATIO),
             ('adjacent',('AdjacentLab_sled_chair',),SLED_CHAIR_RATIO)]
    changed=set()
    for key,prefixes,ratio in presets:
        objects=[obj for obj in chairs if obj.name.startswith(prefixes)]
        assert objects, key
        assert len({obj.data for obj in objects}) == 1
        mesh,record=reduce_chair(objects[0],ratio,'F03V03_Chair_'+key)
        record['instances']=len(objects)
        report['chairs'][key]=record
        for obj in objects:
            obj.data=mesh
            changed.add(obj.name)
    assert len(changed)==len(chairs)==173
    laptops=list(bpy.data.collections['Survey_Laptops'].objects)
    assert len({obj.data for obj in laptops}) == 1
    mesh,report['laptop']=simplify_keyboard(laptops[0])
    report['laptop']['instances']=len(laptops)
    for obj in laptops:
        obj.data=mesh
    after=snapshot()
    for group in GROUPS:
        if group not in {'Chairs','Laptops'}:
            assert before[group]==after[group], group
        else:
            for original,modified in zip(before[group],after[group]):
                assert original['name']==modified['name']
                assert original['matrix']==modified['matrix']
                assert original['materials']==modified['materials']
    report['other_ten_groups_unchanged']=True
    report['all_furniture_transforms_and_materials_unchanged']=True
    blend=OUTPUT/'EscapeFromKD_Floor03_v03.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend),check_existing=False)
    export_dir=OUTPUT/'Export'
    export_dir.mkdir(exist_ok=True)
    destination=bpy.data.collections.new('OptimizedV03_Export')
    bpy.context.scene.collection.children.link(destination)
    depsgraph=bpy.context.evaluated_depsgraph_get()
    material_map={}
    material_report={}
    for group in ['Chairs','Laptops']:
        objects=list(bpy.data.collections['Survey_'+group].objects)
        copies=[copy_mesh(obj,destination,depsgraph,material_map,material_report) for obj in objects]
        removed=sum(remove_degenerate_faces(obj.data) for obj in copies)
        repaired=sum(repair_degenerate_uv(obj.data) for obj in copies)
        bpy.ops.object.select_all(action='DESELECT')
        for obj in copies:
            obj.hide_set(False)
            obj.select_set(True)
        bpy.context.view_layer.objects.active=copies[0]
        bpy.ops.object.join()
        joined=bpy.context.object
        joined.name='SM_F03V03_'+group
        joined.data.name=joined.name
        bpy.context.view_layer.update()
        path=export_dir/(joined.name+'.fbx')
        write_fbx(path,[joined])
        report['groups'].append({'name':group,'fbx':str(path),'source_objects':len(objects),
                                'triangles':triangles(joined.data),'bounds':bounds(joined),
                                'materials':[m.name for m in joined.data.materials],
                                'uv_layers':[u.name for u in joined.data.uv_layers],
                                'removed_degenerate_faces':removed,'repaired_uv_faces':repaired})
    report['source_unchanged']=hashlib.sha256(SOURCE.read_bytes()).hexdigest()==source_hash
    assert report['source_unchanged']
    (OUTPUT/'optimization_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('OPTIMIZED_FURNITURE_COMPLETE',json.dumps(report),flush=True)


if __name__=='__main__':
    main()
