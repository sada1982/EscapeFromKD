import hashlib
import json
from math import radians
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix

ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from export_floor03_fbx import bounds, copy_mesh, write_fbx
from build_floor03 import boxes

SOURCE = ROOT/'SurveyV02'/'EscapeFromKD_Floor03_v02.blend'
OUTPUT = ROOT/'SurveyV02'/'Export'
GROUPS = ['Structure','Ceilings','ClosedClassrooms','ClassroomFixtures','GlazingFrames',
          'Glass','Corridors','StairCore','Desks','Chairs','Laptops','Mice']
FLOOR02_ONLY_LIFT_PARTS = {'Lift_stainless_frame','Lift_closed_leaf','Lift_closed_leaf.001',
                           'Lift_center_seam','Lift_indicator','Lift_number'}


def repair_degenerate_uv(mesh):
    # Text extrusion and bevel side faces can have collapsed UVs; preserve every valid face.
    uv=mesh.uv_layers.active or mesh.uv_layers.new(name='UVMap')
    mesh.calc_loop_triangles()
    affected=set()
    for tri in mesh.loop_triangles:
        a,b,c=[uv.data[i].uv for i in tri.loops]
        determinant=(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x)
        if tri.area>1e-12 and abs(determinant)<1e-10:
            affected.add(tri.polygon_index)
    for index in affected:
        polygon=mesh.polygons[index]
        normal_axis=max(range(3),key=lambda i:abs(polygon.normal[i]))
        axes=[i for i in range(3) if i!=normal_axis]
        points=[mesh.vertices[mesh.loops[i].vertex_index].co for i in polygon.loop_indices]
        minimum=[min(p[i] for p in points) for i in axes]
        span=[max(p[i] for p in points)-minimum[j] for j,i in enumerate(axes)]
        for loop,p in zip(polygon.loop_indices,points):
            uv.data[loop].uv=[(p[i]-minimum[j])/max(span[j],1e-8) for j,i in enumerate(axes)]
    return len(affected)


def remove_degenerate_faces(mesh):
    # Remove zero-area bevel triangles from export copies, leaving the editable source untouched.
    bm=bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    degenerate=[face for face in bm.faces if face.calc_area()<1e-12]
    bmesh.ops.delete(bm,geom=degenerate,context='FACES')
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return len(degenerate)


def fit_stair_fire_door(copies, destination):
    parts={obj.name.removeprefix('EXPORT_'):obj for obj in copies}
    leaf=parts['Stair_floor_identity']
    # Park the leaf against the side wall. Keep the lettering and exit sign at their original scale.
    pivot=Matrix.Translation((-16.8,-5.64,1.5)).inverted()
    mount=Matrix.Translation((-16.398,-6.085,1.5)) @ Matrix.Rotation(radians(-90),4,'Z')
    leaf.data.transform(mount @ Matrix.Diagonal((1.5,1,1,1)) @ pivot)
    for name in ('Stair_floor_3','Stair_exit_sign','Stair_exit_glyph'):
        parts[name].data.transform(mount @ pivot)
    metal=parts['Stair_Up_nosing'].data.materials[0]
    frame=boxes('Fire_door_trim',[
        ((-16.394,-6.611,1.50),(0.048,0.023,3.00)),
        ((-16.394,-5.559,1.50),(0.048,0.023,3.00)),
        ((-16.394,-6.085,3.015),(0.048,1.075,0.025)),
        ((-16.377,-5.679,0.96),(0.010,0.008,0.085)),
        ((-16.377,-5.641,0.96),(0.010,0.008,0.085)),
        ((-16.377,-5.660,0.999),(0.010,0.030,0.007)),
        ((-16.377,-5.660,0.921),(0.010,0.030,0.007)),
    ],metal,destination)
    copies.append(frame)
    wall_material=parts['Stair_side'].data.materials[0]
    copies.append(boxes('Stair_wall_return',[
        ((-17.19,-5.70,1.435),(1.22,0.16,3.23)),
    ],wall_material,destination))


def main():
    source_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    OUTPUT.mkdir(exist_ok=True)
    destination=bpy.data.collections.new('Survey_Export')
    bpy.context.scene.collection.children.link(destination)
    depsgraph=bpy.context.evaluated_depsgraph_get()
    material_map={}
    material_report={}
    exported=[]
    records=[]
    for group in GROUPS:
        sources=[o for o in bpy.data.collections['Survey_'+group].objects if o.type in {'MESH','FONT'}]
        if group=='StairCore':
            # Keep the closed lift parts available to the 2F copy; 3F uses only the backing wall here.
            # The parked fire door also supersedes that projecting backing wall.
            sources=[o for o in sources if o.name not in FLOOR02_ONLY_LIFT_PARTS and o.name!='Lift_front']
        assert sources, group
        copies=[copy_mesh(o,destination,depsgraph,material_map,material_report) for o in sources]
        if group=='StairCore':
            fit_stair_fire_door(copies,destination)
        removed_faces=sum(remove_degenerate_faces(o.data) for o in copies) if group in {'Desks','Laptops'} else 0
        uv_repairs=sum(repair_degenerate_uv(o.data) for o in copies)
        bpy.ops.object.select_all(action='DESELECT')
        for obj in copies: obj.select_set(True)
        bpy.context.view_layer.objects.active=copies[0]
        bpy.ops.object.join()
        obj=bpy.context.object
        obj.name='SM_F03V02_'+group
        obj.data.name=obj.name
        bpy.context.view_layer.update()
        obj.data.calc_loop_triangles()
        path=OUTPUT/(obj.name+'.fbx')
        write_fbx(path,[obj])
        records.append({'group':group,'name':obj.name,'fbx':str(path),
                        'bounds_blender_m':bounds(obj),'triangles':len(obj.data.loop_triangles),
                        'source_count':len(sources),'uv_layers':[u.name for u in obj.data.uv_layers],
                        'repaired_uv_faces':uv_repairs,
                        'removed_degenerate_faces':removed_faces,
                        'material_slots':[m.name for m in obj.data.materials]})
        exported.append(obj)
        print('SURVEY_EXPORTED',group,records[-1]['triangles'],flush=True)
    combined=OUTPUT/'EscapeFromKD_Floor03_v02.fbx'
    write_fbx(combined,exported)
    # Reimport in a separate scene to verify FBX scale, UVs and all twelve mesh groups.
    bpy.ops.object.select_all(action='DESELECT')
    previous=set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(combined),use_image_search=False)
    imported=[o for o in bpy.data.objects if o not in previous and o.type=='MESH']
    assert len(imported)==len(GROUPS),len(imported)
    assert all(o.data.uv_layers for o in imported)
    def aggregate(objects):
        boxes=[bounds(o) for o in objects]
        return {'min':[min(b['min'][i] for b in boxes) for i in range(3)],
                'max':[max(b['max'][i] for b in boxes) for i in range(3)]}
    original_bounds=aggregate(exported)
    reimport_bounds=aggregate(imported)
    error=max(abs(original_bounds[k][i]-reimport_bounds[k][i]) for k in ['min','max'] for i in range(3))
    assert error<0.001,error
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==source_hash
    report={'source':str(SOURCE),'source_sha256':source_hash,'combined_fbx':str(combined),
            'groups':records,'materials':material_report,'total_triangles':sum(r['triangles'] for r in records),
            'roundtrip_mesh_count':len(imported),'roundtrip_bounds_error_m':error,'all_meshes_have_uv':True}
    (OUTPUT/'export_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('SURVEY_EXPORT_COMPLETE',json.dumps({'triangles':report['total_triangles'],'roundtrip_error_m':error}),flush=True)


if __name__=='__main__':
    main()
