import hashlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'EscapeFromKD_Floor03_v03.blend'
REPORT = ROOT / 'optimization_report.json'


def bounds(obj):
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return {'min':[min(v[i] for v in points) for i in range(3)],
            'max':[max(v[i] for v in points) for i in range(3)]}


def main():
    report = json.loads(REPORT.read_text(encoding='utf-8'))
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    results = []
    for group in report['groups']:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=str(ROOT / 'Export' / ('SM_F03V03_' + group['name'] + '.fbx')), use_image_search=False)
        imported = [obj for obj in bpy.data.objects if obj not in before and obj.type == 'MESH']
        assert len(imported) == 1
        obj = imported[0]
        obj.data.calc_loop_triangles()
        measured = bounds(obj)
        error = max(abs(measured[side][i]-group['bounds'][side][i]) for side in ['min','max'] for i in range(3))
        assert error < 0.001
        assert len(obj.data.loop_triangles) == group['triangles']
        assert list(layer.name for layer in obj.data.uv_layers) == group['uv_layers']
        results.append({'group':group['name'],'triangles':len(obj.data.loop_triangles),
                        'bounds_error_m':error,'uv_layers':[u.name for u in obj.data.uv_layers],
                        'materials':[m.name for m in obj.data.materials]})
        bpy.data.objects.remove(obj, do_unlink=True)

    preview = ROOT / 'Previews'
    preview.mkdir(exist_ok=True)
    scene = bpy.data.scenes.new('Furniture_Optimization_VisualCheck')
    bpy.context.window.scene = scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 16
    scene.cycles.use_denoising = True
    scene.render.threads_mode = 'FIXED'
    scene.render.threads = 4
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 700
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    world = bpy.data.worlds.new('FurnitureCheckWorld')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.18,0.18,0.18,1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.5
    scene.world = world
    for name,location,power,size in [('Key',(1.5,-2.0,2.5),150,2),('Fill',(-1.5,0.5,1.6),90,2)]:
        data = bpy.data.lights.new(name,'AREA')
        data.energy = power
        data.shape = 'DISK'
        data.size = size
        obj = bpy.data.objects.new(name,data)
        scene.collection.objects.link(obj)
        obj.location = location
        obj.rotation_euler = (Vector((0,0,0.4))-obj.location).to_track_quat('-Z','Y').to_euler()
    camera_data = bpy.data.cameras.new('FurnitureCheckCamera')
    camera = bpy.data.objects.new('FurnitureCheckCamera',camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera_data.type = 'ORTHO'
    data_pairs = [('Chair_Main',bpy.data.objects['Chair_Prototype'].data,bpy.data.meshes['F03V03_Chair_main'],(1.0,-1.7,1.15),(0,-0.02,0.42),1.50,0.70),
                  ('Laptop',bpy.data.objects['Laptop_Prototype'].data,bpy.data.meshes['F03V03_Laptop_KeyBevelReduced'],(0.43,-0.63,0.50),(0,0.025,0.10),0.95,0.45)]
    images = []
    for label,original,reduced,position,target,scale,separation in data_pairs:
        camera.location = position
        camera.rotation_euler = (Vector(target)-camera.location).to_track_quat('-Z','Y').to_euler()
        camera_data.ortho_scale = scale
        rotation = camera.rotation_euler.to_quaternion()
        right = rotation @ Vector((1,0,0))
        up = rotation @ Vector((0,1,0))
        created = []
        for side,(suffix,mesh) in zip([-1,1],[('BEFORE',original),('AFTER',reduced)]):
            obj = bpy.data.objects.new('Compare_'+label,mesh)
            scene.collection.objects.link(obj)
            obj.location = right * (side * separation * 0.5)
            created.append(obj)
            text_data = bpy.data.curves.new('Label_'+suffix,'FONT')
            text_data.body = suffix
            text_data.align_x = 'CENTER'
            text_data.size = scale * 0.035
            text_obj = bpy.data.objects.new('Label_'+suffix,text_data)
            scene.collection.objects.link(text_obj)
            text_obj.location = Vector(target) + right * (side * separation * 0.5) - up * (scale * 0.30)
            text_obj.rotation_euler = camera.rotation_euler
            created.append(text_obj)
        scene.render.filepath = str(preview/(label+'_Comparison.png'))
        bpy.ops.render.render(write_still=True)
        images.append(scene.render.filepath)
        for obj in created:
            bpy.data.objects.remove(obj,do_unlink=True)
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash
    result = {'roundtrip':results,'images':images,'optimized_source_unchanged':True}
    (ROOT/'validation_report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('FURNITURE_VALIDATION_COMPLETE',json.dumps(result),flush=True)


if __name__=='__main__':
    main()
