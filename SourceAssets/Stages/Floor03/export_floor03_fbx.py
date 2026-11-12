import hashlib
import json
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'EscapeFromKD_Floor03_v01.blend'
OUTPUT = ROOT / 'Export'


def bounds(obj):
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return {
        'min': [min(point[index] for point in points) for index in range(3)],
        'max': [max(point[index] for point in points) for index in range(3)],
    }


def texture_scale(material):
    for node in material.node_tree.nodes:
        if node.type == 'TEX_IMAGE' and node.inputs['Vector'].is_linked:
            source = node.inputs['Vector'].links[0].from_node
            if source.type == 'VECT_MATH' and source.operation == 'SCALE':
                return float(source.inputs[3].default_value)
    return 1.0


def export_material(source, material_map, material_report):
    if source in material_map:
        return material_map[source]
    name = source.name
    shader = source.node_tree.nodes.get('Principled BSDF')
    images = [node.image for node in source.node_tree.nodes if node.type == 'TEX_IMAGE' and node.image]
    material_report[name] = {
        'base_color_linear': list(shader.inputs['Base Color'].default_value),
        'roughness': float(shader.inputs['Roughness'].default_value),
        'metallic': float(shader.inputs['Metallic'].default_value),
        'transmission': float(shader.inputs['Transmission Weight'].default_value),
        'ior': float(shader.inputs['IOR'].default_value),
        'emission_color_linear': list(shader.inputs['Emission Color'].default_value),
        'emission_strength': float(shader.inputs['Emission Strength'].default_value),
        'image_files': [str(Path(bpy.path.abspath(image.filepath)).resolve()) for image in images],
        'uv_scale_baked': texture_scale(source),
    }
    source.name = 'SOURCE_' + name
    result = source.copy()
    result.name = name
    for node in result.node_tree.nodes:
        if node.type == 'VECT_MATH' and node.operation == 'SCALE':
            node.inputs[3].default_value = 1.0
    material_map[source] = result
    return result


def copy_mesh(source, destination, depsgraph, material_map, material_report):
    evaluated = source.evaluated_get(depsgraph)
    mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
    mesh.transform(source.matrix_world)
    original_materials = list(mesh.materials)
    scales = [texture_scale(material) if material else 1.0 for material in original_materials]
    for uv_layer in mesh.uv_layers:
        for polygon in mesh.polygons:
            scale = scales[polygon.material_index] if polygon.material_index < len(scales) else 1.0
            if scale != 1.0:
                for loop_index in polygon.loop_indices:
                    uv_layer.data[loop_index].uv *= scale
    for index, material in enumerate(original_materials):
        if material:
            mesh.materials[index] = export_material(material, material_map, material_report)
    obj = bpy.data.objects.new('EXPORT_' + source.name, mesh)
    destination.objects.link(obj)
    obj.matrix_world = Matrix.Identity(4)
    return obj


def write_fbx(path, objects):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.fbx(
        filepath=str(path),
        check_existing=False,
        use_selection=True,
        use_visible=False,
        object_types={'MESH'},
        global_scale=1.0,
        apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_NONE',
        axis_forward='-Y',
        axis_up='Z',
        use_space_transform=True,
        bake_space_transform=False,
        use_mesh_modifiers=True,
        mesh_smooth_type='FACE',
        use_tspace=True,
        use_triangles=True,
        bake_anim=False,
        path_mode='COPY',
        embed_textures=True,
        use_custom_props=False,
        add_leaf_bones=False,
    )


def main():
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    OUTPUT.mkdir(exist_ok=True)
    destination = bpy.data.collections.new('FBX_Export_Only')
    bpy.context.scene.collection.children.link(destination)
    names = {
        'Structure': '10_Structure',
        'Ceilings': '11_Ceilings_Open_For_Overview',
        'ClosedClassrooms': '12_Closed_Classroom_Shells',
        'ClassroomFixtures': '21_Start_Classroom_Fixtures',
        'GlazingFrames': '22_Windows_And_Sliding_Doors',
        'Glass': '22_Windows_And_Sliding_Doors',
        'Corridors': '30_Corridors',
        'StairCore': '40_Stair_Core_Provisional',
        'Desks': '20_Start_Classroom_Furniture',
        'Chairs': '20_Start_Classroom_Furniture',
        'Laptops': '20_Start_Classroom_Furniture',
        'Mice': '20_Start_Classroom_Furniture',
    }
    prefixes = {
        'Desks': ('Student_Desk_', 'Instructor_Desk'),
        'Chairs': ('Student_Chair_', 'Instructor_Chair'),
        'Laptops': ('Student_Laptop_', 'Instructor_Laptop'),
        'Mice': ('Student_Mouse_',),
    }
    source_groups = {}
    for group, collection_name in names.items():
        sources = [obj for obj in bpy.data.collections[collection_name].objects if obj.type in {'MESH', 'FONT'}]
        if group in prefixes:
            sources = [obj for obj in sources if obj.name.startswith(prefixes[group])]
        if group in ('GlazingFrames', 'Glass'):
            glass_sources = {obj for obj in sources if any(material and material.name == 'KD_F03_ClearGlass' for material in obj.data.materials)}
            sources = [obj for obj in sources if (obj in glass_sources) == (group == 'Glass')]
        source_groups[group] = sources
    source_objects = [obj for objects in source_groups.values() for obj in objects]
    assert len(source_objects) == len(set(source_objects)), 'Export groups overlap'
    assert len(source_groups['Desks']) == 25
    assert len(source_groups['Chairs']) == 49
    assert len(source_groups['Laptops']) == 25
    assert len(source_groups['Mice']) == 24
    depsgraph = bpy.context.evaluated_depsgraph_get()
    material_map = {}
    material_report = {}
    exported = []
    group_report = []
    for group, sources in source_groups.items():
        assert sources, group
        copies = [copy_mesh(obj, destination, depsgraph, material_map, material_report) for obj in sources]
        bpy.ops.object.select_all(action='DESELECT')
        for obj in copies:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = copies[0]
        bpy.ops.object.join()
        obj = bpy.context.object
        obj.name = 'SM_F03_' + group
        obj.data.name = obj.name
        bpy.context.view_layer.update()
        obj.data.calc_loop_triangles()
        filename = obj.name + '.fbx'
        record = {
            'group': group,
            'asset_name': obj.name,
            'fbx': str(OUTPUT / filename),
            'source_objects': [source.name for source in sources],
            'source_count': len(sources),
            'bounds_blender_m': bounds(obj),
            'vertices': len(obj.data.vertices),
            'triangles': len(obj.data.loop_triangles),
            'uv_layers': [layer.name for layer in obj.data.uv_layers],
            'material_slots': [material.name for material in obj.data.materials],
            'origin_blender_m': list(obj.location),
        }
        write_fbx(OUTPUT / filename, [obj])
        record['file_bytes'] = (OUTPUT / filename).stat().st_size
        group_report.append(record)
        exported.append(obj)
        print('KD_EXPORTED_GROUP', group, len(sources), record['triangles'], flush=True)
    combined = OUTPUT / 'EscapeFromKD_Floor03_v01.fbx'
    write_fbx(combined, exported)
    all_bounds = [record['bounds_blender_m'] for record in group_report]
    report = {
        'source_blend': str(SOURCE),
        'source_blend_sha256': source_hash,
        'blender_version': bpy.app.version_string,
        'source_units': 'meters',
        'fbx_export': {'axis_forward': '-Y', 'axis_up': 'Z', 'apply_unit_scale': True, 'apply_scale_options': 'FBX_SCALE_NONE', 'global_scale': 1.0},
        'combined_fbx': str(combined),
        'combined_bytes': combined.stat().st_size,
        'source_object_count': len(source_objects),
        'bounds_blender_m': {
            'min': [min(bound['min'][index] for bound in all_bounds) for index in range(3)],
            'max': [max(bound['max'][index] for bound in all_bounds) for index in range(3)],
        },
        'groups': group_report,
        'materials': material_report,
        'excluded': ['lighting', 'cameras', 'world', 'layout marker empties', 'overview labels', 'hidden furniture prototypes'],
        'notes': ['Materials with UV scale nodes have their scale baked into export mesh UVs.', 'Original Blender file is not overwritten.', 'Collision and Unreal materials require validation in Unreal Editor.'],
    }
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(combined), use_anim=False)
    imported = [obj for obj in bpy.data.objects if obj not in before and obj.type == 'MESH']
    bpy.context.view_layer.update()
    imported_bounds = [bounds(obj) for obj in imported]
    roundtrip_bounds = {
        'min': [min(bound['min'][index] for bound in imported_bounds) for index in range(3)],
        'max': [max(bound['max'][index] for bound in imported_bounds) for index in range(3)],
    }
    max_error = max(abs(roundtrip_bounds[side][index]-report['bounds_blender_m'][side][index]) for side in ('min','max') for index in range(3))
    report['roundtrip_validation'] = {
        'mesh_count': len(imported),
        'all_meshes_have_uv': all(len(obj.data.uv_layers) > 0 for obj in imported),
        'bounds_blender_m': roundtrip_bounds,
        'maximum_bounds_error_m': max_error,
    }
    assert len(imported) == len(exported)
    assert max_error < 0.001, str(roundtrip_bounds)
    assert report['roundtrip_validation']['all_meshes_have_uv']
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash
    (OUTPUT / 'export_manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('KD_EXPORT_COMPLETE', json.dumps({'groups':len(exported),'sources':len(source_objects),'triangles':sum(record['triangles'] for record in group_report),'combined_fbx':str(combined),'roundtrip':report['roundtrip_validation']},ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
