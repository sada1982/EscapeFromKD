import argparse
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from build_furniture import build_prototypes
from build_materials import create_materials


def collection(name):
    result = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(result)
    return result


def move_to(obj, target):
    for current in list(obj.users_collection):
        current.objects.unlink(obj)
    target.objects.link(obj)
    return obj


def surface_uv(obj, material):
    uv = obj.data.uv_layers.active or obj.data.uv_layers.new(name='UVMap')
    physical_scale = material.name in ('KD_F03_ClassroomCarpet', 'KD_F03_CorridorCarpet', 'KD_F03_AcousticCeiling')
    for polygon in obj.data.polygons:
        normal_axis = max(range(3), key=lambda axis: abs(polygon.normal[axis]))
        axes = (1, 2) if normal_axis == 0 else ((0, 2) if normal_axis == 1 else (0, 1))
        points = [obj.data.vertices[obj.data.loops[index].vertex_index].co for index in polygon.loop_indices]
        minimum = [min(point[axis] for point in points) for axis in axes]
        span = [max(point[axis] for point in points)-minimum[index] for index,axis in enumerate(axes)]
        for loop_index, point in zip(polygon.loop_indices, points):
            value = [point[axis] if physical_scale else (point[axis]-minimum[index])/max(span[index],0.000001) for index,axis in enumerate(axes)]
            if material.name == 'KD_F03_LightOak' and normal_axis != 2 and span[1] > span[0]:
                value.reverse()
            uv.data[loop_index].uv = value


def box(name, center, size, material, target, bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    surface_uv(obj, material)
    move_to(obj, target)
    if bevel:
        modifier = obj.modifiers.new('Edge bevel', 'BEVEL')
        modifier.width = bevel
        modifier.segments = 2
    return obj


def boxes(name, items, material, target):
    vertices = []
    faces = []
    for center, size in items:
        index = len(vertices)
        x, y, z = center
        a, b, c = (value / 2 for value in size)
        vertices.extend([(x-a,y-b,z-c),(x+a,y-b,z-c),(x+a,y+b,z-c),(x-a,y+b,z-c),
                         (x-a,y-b,z+c),(x+a,y-b,z+c),(x+a,y+b,z+c),(x-a,y+b,z+c)])
        faces.extend([tuple(index+i for i in face) for face in
                      [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]])
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    target.objects.link(obj)
    surface_uv(obj, material)
    return obj


def cylinder(name, center, radius, depth, material, target, rotation=(0, 0, 0), vertices=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=center, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    move_to(obj, target)
    for face in obj.data.polygons:
        face.use_smooth = len(face.vertices) == 4
    return obj


def rail(name, start, end, material, target, radius=0.025):
    a, b = Vector(start), Vector(end)
    obj = cylinder(name, (a+b)/2, radius, (b-a).length, material, target, vertices=12)
    obj.rotation_euler = (b-a).to_track_quat('Z', 'Y').to_euler()
    return obj


def text(name, body, location, size, material, target, rotation=(math.pi/2, 0, 0), align='CENTER'):
    curve = bpy.data.curves.new(name, 'FONT')
    curve.body = body
    curve.align_x = align
    curve.align_y = 'CENTER'
    curve.size = size
    curve.extrude = 0.0004
    curve.materials.append(material)
    obj = bpy.data.objects.new(name, curve)
    target.objects.link(obj)
    obj.location = location
    obj.rotation_euler = rotation
    return obj


def area_light(name, location, power, size, target, aim=None):
    data = bpy.data.lights.new(name, 'AREA')
    data.energy = power
    data.shape = 'DISK'
    data.size = size
    obj = bpy.data.objects.new(name, data)
    target.objects.link(obj)
    obj.location = location
    if aim:
        obj.rotation_euler = (Vector(aim)-obj.location).to_track_quat('-Z', 'Y').to_euler()
    return obj


def camera(name, location, aim, target, lens=22, ortho=None):
    data = bpy.data.cameras.new(name)
    data.lens = lens
    data.clip_end = 250
    if ortho:
        data.type = 'ORTHO'
        data.ortho_scale = ortho
    obj = bpy.data.objects.new(name, data)
    target.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(aim)-obj.location).to_track_quat('-Z', 'Y').to_euler()
    return obj


def instance(prototype, name, position, target, rotation=0):
    obj = prototype.copy()
    obj.data = prototype.data
    obj.name = name
    target.objects.link(obj)
    obj.location = position
    obj.rotation_euler.z = rotation
    obj.hide_render = False
    obj.hide_set(False)
    return obj


def build():
    params = json.loads((ROOT / 'floor03_parameters.json').read_text(encoding='utf-8'))
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for old in list(bpy.data.collections):
        if old.users == 0 or old.name == 'Collection':
            bpy.data.collections.remove(old)
    bpy.context.preferences.filepaths.save_version = 0
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    scene.unit_settings.length_unit = 'METERS'
    scene['stage'] = 'Escape From KD / Floor 03 / First pass'
    scene['dimensions_are_provisional'] = True
    scene['source_parameters'] = 'floor03_parameters.json'
    scene['scope'] = '3F classroom, corridors, closed classroom shells, stair connections and closed lift'
    scene['notes'] = '\n'.join(params['notes'])
    structure = collection('10_Structure')
    ceilings = collection('11_Ceilings_Open_For_Overview')
    closed = collection('12_Closed_Classroom_Shells')
    furniture = collection('20_Start_Classroom_Furniture')
    fixtures = collection('21_Start_Classroom_Fixtures')
    glazing = collection('22_Windows_And_Sliding_Doors')
    corridor = collection('30_Corridors')
    stairs = collection('40_Stair_Core_Provisional')
    lighting = collection('50_Lighting')
    markers = collection('80_Layout_Markers')
    presentation = collection('90_Presentation')
    labels = collection('91_Overview_Labels')
    prototypes_collection = collection('99_Furniture_Prototypes')
    mats = create_materials(ROOT / 'Textures')
    prototypes = build_prototypes(mats, prototypes_collection)
    prototypes['desk'].scale = (params['desk_width']/1.8, params['desk_depth']/0.6, params['desk_height']/0.72)
    for obj in prototypes.values():
        obj.hide_render = True
        obj.hide_set(True)
    width, depth = params['classroom_width'], params['classroom_depth']
    height, thickness = params['ceiling_height'], params['wall_thickness']
    hall_width = params['corridor_width']

    def floor(name, bounds, material, target=structure, elevation=0):
        x0, x1, y0, y1 = bounds
        return box(name, ((x0+x1)/2, (y0+y1)/2, elevation-0.09), (x1-x0, y1-y0, 0.18), material, target)

    def wall_x(name, x, y0, y1, target=structure, material=None, bottom=0, top=None):
        top = height if top is None else top
        return box(name, (x, (y0+y1)/2, (bottom+top)/2), (thickness, y1-y0, top-bottom), material or mats['wall'], target)

    def wall_y(name, y, x0, x1, target=structure, material=None, bottom=0, top=None):
        top = height if top is None else top
        return box(name, ((x0+x1)/2, y, (bottom+top)/2), (x1-x0, thickness, top-bottom), material or mats['wall'], target)

    floor('Start_Classroom_Floor', (0, width, 0, depth), mats['carpet'])
    box('Start_Classroom_Ceiling', (width/2, depth/2, height+0.055), (width, depth, 0.11), mats['ceiling'], ceilings)
    wall_y('Classroom_Back_Wall', 0, 0, width)
    wall_y('Classroom_Teaching_Wall', depth, 0, width)
    wall_x('Window_Wall_Sill', width, 0, depth, bottom=0, top=0.92)
    wall_x('Window_Wall_Header', width, 0, depth, bottom=2.7)
    window_centers = [2.1, depth/2, depth-2.1]
    window_width = 2.65
    last_end = 0
    for index, center_y in enumerate(window_centers):
        low, high = center_y-window_width/2, center_y+window_width/2
        wall_x('Window_Pier_%02d' % index, width, last_end, low)
        box('Window_Glass_%02d' % index, (width, center_y, 1.81), (0.014, window_width, 1.78), mats['glass'], glazing)
        bars = [((width-0.04,low,1.81),(0.075,0.045,1.78)),((width-0.04,high,1.81),(0.075,0.045,1.78)),
                ((width-0.04,center_y,0.94),(0.075,window_width,0.045)),((width-0.04,center_y,2.68),(0.075,window_width,0.045))]
        boxes('Dark_Window_Frame_%02d' % index, bars, mats['frame'], glazing)
        blinds = [((width+0.005,center_y,1.01+j*0.052),(0.045,window_width-0.06,0.022)) for j in range(32)]
        boxes('Window_Blinds_%02d' % index, blinds, mats['metal'], glazing)
        last_end = high
    wall_x('Window_Last_Pier', width, last_end, depth)
    box('Exterior_Window_Skirting', (width-0.105,depth/2,0.055),(0.025,depth,0.11),mats['black'],glazing)
    box('Back_Skirting',(width/2,0.105,0.055),(width,0.025,0.11),mats['black'],fixtures)
    box('Front_Skirting',(width/2,depth-0.105,0.055),(width,0.025,0.11),mats['black'],fixtures)

    door_ranges = [(0.65, 0.65+params['door_width']), (depth-2.05, depth-2.05+params['door_width'])]
    wall_x('Hall_Glazing_Header', 0, 0, depth, glazing, bottom=2.6)
    solid_spans = [(0,door_ranges[0][0]),(door_ranges[0][1],door_ranges[1][0]),(door_ranges[1][1],depth)]
    for index, (y0,y1) in enumerate(solid_spans):
        wall_x('Hall_Glazing_Sill_%02d' % index, 0, y0, y1, glazing, bottom=0, top=0.85)
        box('Hall_Glass_%02d' % index, (0,(y0+y1)/2,1.725),(0.012,y1-y0,1.75),mats['glass'],glazing)
        count = max(1, math.ceil((y1-y0)/1.8))
        posts = [((0,y0+(y1-y0)*j/count,1.725),(0.19,0.085,1.75)) for j in range(count+1)]
        posts.extend([((0,(y0+y1)/2,0.87),(0.19,y1-y0,0.055)),((0,(y0+y1)/2,2.58),(0.19,y1-y0,0.055))])
        boxes('Hall_Glazing_Frames_%02d' % index,posts,mats['wall'],glazing)
        box('Hall_Skirting_%02d'%index,(0.105,(y0+y1)/2,0.055),(0.025,y1-y0,0.11),mats['black'],glazing)
    for index,(y0,y1) in enumerate(door_ranges):
        for y in (y0,y1):
            box('Door_Jamb_%d'%index,(0,y,1.15),(0.24,0.07,2.3),mats['wall'],glazing)
        box('Door_Top_Track_%d'%index,(-0.075,(y0+y1)/2,2.34),(0.15,2.6,0.08),mats['metal'],glazing)
        panel_center = y1+0.64 if index == 0 else y0-0.64
        panel_width = params['door_width']
        slot_center = panel_center+0.32
        left = panel_center-panel_width/2
        right = panel_center+panel_width/2
        door_parts = [((-0.12,(left+slot_center-0.065)/2,1.15),(0.055,slot_center-0.065-left,2.3)),
                      ((-0.12,(slot_center+0.065+right)/2,1.15),(0.055,right-slot_center-0.065,2.3)),
                      ((-0.12,slot_center,0.22),(0.055,0.13,0.44)),
                      ((-0.12,slot_center,2.18),(0.055,0.13,0.24))]
        boxes('Open_Wood_Sliding_Panel_%d'%index,door_parts,mats['wood'],glazing)
        box('Door_Slit_Glass_%d'%index,(-0.12,slot_center,1.25),(0.012,0.13,1.62),mats['glass'],glazing)
        box('Door_Inset_Handle_%d'%index,(-0.155,panel_center-0.43,1.05),(0.012,0.05,0.18),mats['metal'],glazing,0.014)
        text('Classroom_Name_%d'%index,'GAME PROGRAMMING LAB',(-0.115,(y0+y1)/2,2.76),0.105,mats['frame'],glazing,(math.pi/2,0,-math.pi/2))

    desk_index = 0
    seat_count = 0
    bank_centers = [(width-params['center_aisle_width'])/2-params['desk_width'],(width+params['center_aisle_width'])/2+params['desk_width']]
    for row in range(params['desk_rows']):
        y = params['desk_first_row_y']+row*params['desk_row_spacing']
        for bank, center in enumerate(bank_centers):
            for side in (-1,1):
                x = center+side*params['desk_width']/2
                instance(prototypes['desk'],'Student_Desk_%02d'%desk_index,(x,y,0),furniture)
                for seat_offset in (-0.45,0.45):
                    chair_x = x+seat_offset
                    instance(prototypes['chair'],'Student_Chair_%02d'%seat_count,(chair_x,y-0.63,0),furniture,0.035*math.sin(seat_count))
                    if seat_count % 2 == 0:
                        instance(prototypes['laptop'],'Student_Laptop_%02d'%seat_count,(chair_x+0.10,y-0.02,params['desk_height']),furniture)
                        instance(prototypes['mouse'],'Student_Mouse_%02d'%seat_count,(chair_x+0.39,y-0.13,params['desk_height']),furniture)
                    seat_count += 1
                desk_index += 1

    instance(prototypes['desk'],'Instructor_Desk',(7.3,depth-0.8,0),furniture)
    instance(prototypes['chair'],'Instructor_Chair',(7.3,depth-0.55,0),furniture,math.pi)
    instance(prototypes['laptop'],'Instructor_Laptop',(7.3,depth-0.8,params['desk_height']),furniture,math.pi)
    box('Whiteboard_Surface',(3.0,depth-0.18,1.75),(4.1,0.04,1.18),mats['whiteboard'],fixtures,0.02)
    whiteboard_frame = [((0.94,depth-0.17,1.75),(0.035,0.065,1.24)),((5.06,depth-0.17,1.75),(0.035,0.065,1.24)),
                        ((3.0,depth-0.17,1.14),(4.16,0.065,0.035)),((3.0,depth-0.17,2.36),(4.16,0.065,0.035))]
    for x in (1.25,4.75):
        whiteboard_frame.extend([((x,depth-0.18,0.6),(0.035,0.045,1.2)),((x,depth-0.28,0.075),(0.08,0.5,0.06))])
    boxes('Whiteboard_Stand_And_Frame',whiteboard_frame,mats['metal'],fixtures)
    box('Whiteboard_Tray',(3.0,depth-0.26,1.14),(3.95,0.17,0.03),mats['metal'],fixtures)
    box('Whiteboard_Eraser',(1.5,depth-0.27,1.18),(0.16,0.07,0.045),mats['poster_blue'],fixtures,0.01)
    cylinder('Clock_Rim',(3.0,depth-0.14,2.75),0.19,0.035,mats['metal'],fixtures,(math.pi/2,0,0),48)
    cylinder('Clock_Face',(3.0,depth-0.165,2.75),0.17,0.012,mats['whiteboard'],fixtures,(math.pi/2,0,0),48)
    for index in range(12):
        angle=index*math.tau/12
        tick=box('Clock_Tick_%02d'%index,(3.0+0.145*math.sin(angle),depth-0.176,2.75+0.145*math.cos(angle)),(0.008,0.004,0.025),mats['frame'],fixtures)
        tick.rotation_euler.y=angle
    rail('Clock_Hour_Hand',(3.0,depth-0.182,2.75),(2.93,depth-0.182,2.79),mats['frame'],fixtures,0.006)
    rail('Clock_Minute_Hand',(3.0,depth-0.182,2.75),(3.02,depth-0.182,2.88),mats['frame'],fixtures,0.004)
    box('Projection_Screen',(7.55,depth-0.108,2.05),(3.35,0.012,1.78),mats['screen'],fixtures)
    box('Projection_Screen_Roller',(7.55,depth-0.15,2.98),(3.5,0.12,0.095),mats['wall'],fixtures,0.015)
    box('Presentation_Display_Back',(width-0.72,depth-0.7,1.6),(1.05,0.065,0.62),mats['black'],fixtures,0.035)
    box('Presentation_Display',(width-0.72,depth-0.739,1.6),(0.99,0.006,0.55),mats['screen'],fixtures)
    rail('Presentation_Display_Stand',(width-0.72,depth-0.7,0.07),(width-0.72,depth-0.7,1.3),mats['metal'],fixtures,0.033)
    box('Presentation_Display_Foot',(width-0.72,depth-0.7,0.055),(0.7,0.6,0.065),mats['black'],fixtures,0.02)

    for index,(x,y) in enumerate([(2.6,3.2),(7.8,7.7)]):
        box('Ceiling_AC_Cassette_%d'%index,(x,y,height-0.045),(0.8,0.8,0.09),mats['wall'],ceilings,0.018)
        grille=[((x-0.28+j*0.055,y,height-0.095),(0.018,0.55,0.012)) for j in range(11)]
        boxes('Ceiling_AC_Grille_%d'%index,grille,mats['frame'],ceilings)
    grid=[]
    for index in range(1,math.ceil(width/0.6)):
        grid.append(((index*0.6,depth/2,height-0.007),(0.008,depth,0.006)))
    for index in range(1,math.ceil(depth/0.6)):
        grid.append(((width/2,index*0.6,height-0.007),(width,0.008,0.006)))
    boxes('Ceiling_Tile_Joints',grid,mats['metal'],ceilings)
    for x in (1.75,5.2,8.65):
        for y in (1.6,4.25,6.9,9.55):
            box('Ceiling_Luminaire',(x,y,height-0.07),(0.24,1.12,0.07),mats['metal'],ceilings,0.02)
            box('Ceiling_Light_Lens',(x,y,height-0.11),(0.19,1.04,0.018),mats['emission'],ceilings,0.01)
            area_light('Classroom_Soft_Light',(x,y,height-0.15),65,1.1,lighting)
    area_light('Window_Daylight',(width+1.5,depth/2,4.5),1250,8,lighting,(width/2,depth/2,0.5))
    for index,y in enumerate((1.25,2.2,4.8,6.5,9.1,10.2)):
        poster_mat=mats['poster_blue'] if index%2==0 else mats['poster_orange']
        box('Student_Poster_%02d'%index,(width-0.15,y,1.6),(0.018,0.48,0.68),poster_mat,fixtures)
        text('Poster_Heading_%02d'%index,'CREATE\nPLAY',(width-0.162,y,1.68),0.07,mats['whiteboard'],fixtures,(math.pi/2,0,-math.pi/2))
    shelf_x=1.2
    shelf_parts=[((shelf_x+offset,0.35,1.0),(0.025,0.5,1.95)) for offset in (-0.75,0.75)]
    shelf_parts.extend([((shelf_x,0.35,z),(1.55,0.5,0.035)) for z in (0.1,0.6,1.15,1.75)])
    boxes('Back_Equipment_Shelf',shelf_parts,mats['metal'],fixtures)
    for index in range(6):
        box('Equipment_Case_%02d'%index,(shelf_x-0.6+index*0.23,0.35,1.36),(0.18,0.38,0.38),mats['poster_blue'] if index%2==0 else mats['black'],fixtures,0.02)
    for x in (width-1.2,width-0.6):
        box('Back_Storage_Cabinet',(x,0.35,0.49),(0.58,0.48,0.95),mats['wood'],fixtures,0.015)
        box('Cabinet_Handle',(x+0.2,0.60,0.60),(0.018,0.025,0.15),mats['metal'],fixtures,0.005)

    corridor_end=depth+2.2
    floor('Right_Wing_Corridor',(-hall_width,0,0,corridor_end),mats['corridor'],corridor)
    floor('Connecting_Corridor',(-14.4,-hall_width,0,hall_width),mats['corridor'],corridor)
    floor('Left_Lobby',(-20.2,-14.4,-1,8.2),mats['corridor'],corridor)
    floor('Lift_Approach',(-14.4,-11.4,5.8,8.2),mats['corridor'],corridor)
    wall_x('Right_Corridor_Outer_Wall',-hall_width,hall_width,corridor_end,corridor)
    wall_y('Right_Corridor_End',corridor_end,-hall_width,0,corridor)
    wall_y('Right_Corridor_South',0,-hall_width,0,corridor)
    wall_y('Connector_South',0,-14.4,-hall_width,corridor)
    wall_y('Connector_North',hall_width,-14.4,-hall_width,corridor)
    wall_y('Lobby_South',-1,-20.2,-14.4,corridor)
    wall_x('Lobby_East_Lower',-14.4,-1,0,corridor)
    wall_x('Lobby_East_Middle',-14.4,hall_width,5.8,corridor)
    wall_y('Lift_Approach_South',5.8,-14.4,-11.4,corridor)
    wall_x('Lift_Approach_East',-11.4,5.8,8.2,corridor)
    for name,bounds in [('Right_Corridor',(-hall_width,0,0,corridor_end)),('Connector',(-14.4,-hall_width,0,hall_width)),('Lobby',(-20.2,-14.4,-1,8.2)),('Lift_Approach',(-14.4,-11.4,5.8,8.2))]:
        x0,x1,y0,y1=bounds
        box(name+'_Ceiling',((x0+x1)/2,(y0+y1)/2,height+0.05),(x1-x0,y1-y0,0.1),mats['ceiling'],ceilings)
    hall_light_positions=[(-hall_width/2,y) for y in (1.2,4.5,7.8,11.1)]+[(x,hall_width/2) for x in (-4,-7.5,-11)]+[(-17.3,1),(-17.3,5.5),(-12.9,7)]
    for index,(x,y) in enumerate(hall_light_positions):
        box('Hall_Light_%02d'%index,(x,y,height-0.055),(0.55,0.55,0.05),mats['emission'],ceilings,0.02)
        area_light('Hall_Illumination_%02d'%index,(x,y,height-0.13),75,1.2,lighting)
    glass_blocks=[]
    for row in range(7):
        for col in range(19):
            glass_blocks.append(((-hall_width+0.10,4.6+col*0.20,1.0+row*0.20),(0.02,0.184,0.184)))
    glass_block_material=mats['glass'].copy()
    glass_block_material.name='KD_F03_GlassBlocks'
    glass_block_shader=glass_block_material.node_tree.nodes.get('Principled BSDF')
    glass_block_shader.inputs['Base Color'].default_value=(0.22,0.34,0.39,1)
    glass_block_shader.inputs['Roughness'].default_value=0.24
    glass_block_shader.inputs['Transmission Weight'].default_value=0.25
    boxes('Corridor_Glass_Block_Feature',glass_blocks,glass_block_material,corridor)

    def closed_classroom(name,bounds,door_x,door_y):
        x0,x1,y0,y1=bounds
        floor(name+'_Floor',bounds,mats['carpet'],closed)
        wall_y(name+'_South',y0,x0,x1,closed)
        wall_y(name+'_North',y1,x0,x1,closed)
        wall_x(name+'_West',x0,y0,y1,closed)
        wall_x(name+'_East',x1,y0,y1,closed)
        box(name+'_Roof',((x0+x1)/2,(y0+y1)/2,height+0.055),(x1-x0,y1-y0,0.11),mats['wall'],closed)
        panel_x=door_x-0.11 if door_x==x0 else door_x+0.11
        box(name+'_Closed_Door',(panel_x,door_y,1.15),(0.045,1.25,2.3),mats['wood'],closed,0.015)
        box(name+'_Door_Slit',(panel_x-0.025 if door_x==x0 else panel_x+0.025,door_y+0.33,1.25),(0.012,0.13,1.6),mats['frame'],closed)
        label_x=panel_x-0.03 if door_x==x0 else panel_x+0.03
        rotation=(math.pi/2,0,-math.pi/2 if door_x==x0 else math.pi/2)
        text(name+'_Door_Label','CLASSROOM',(label_x,door_y,2.48),0.12,mats['frame'],closed,rotation)
        text(name+'_Overview_Label','CLOSED CLASSROOM',((x0+x1)/2,(y0+y1)/2,height+0.12),0.48,mats['frame'],labels,(0,0,0))
    closed_classroom('Adjacent_Classroom',(0,width,depth,depth+12.7),0,depth+1.15)
    closed_classroom('Left_Classroom',(-31.8,-20.2,-1,13.8),-20.2,3.1)

    floor('Stair_3F_Landing',(-20.2,-14.4,8.2,9.5),mats['concrete'],stairs)
    wall_x('Stair_Core_West',-20.2,8.2,13.3,stairs,bottom=-1.9,top=4.5)
    wall_x('Stair_Core_East',-14.4,8.2,13.3,stairs,bottom=-1.9,top=4.5)
    wall_y('Stair_Core_End',13.3,-20.2,-14.4,stairs,bottom=-1.9,top=4.5)
    flight_width=2.15
    for direction,center_x,name in [(-1,-18.85,'Down_To_2F'),(1,-15.85,'Up_To_4F')]:
        for index in range(params['stair_steps_per_preview_flight']):
            top=direction*params['stair_rise']*(index+1)
            center_y=9.5+(index+0.5)*params['stair_tread']
            box(name+'_Step_%02d'%index,(center_x,center_y,top-0.1),(flight_width,params['stair_tread'],0.20),mats['concrete'],stairs)
            box(name+'_Nosing_%02d'%index,(center_x,center_y-params['stair_tread']/2+0.022,top+0.008),(flight_width,0.045,0.015),mats['metal'],stairs)
        final_z=direction*params['stair_rise']*params['stair_steps_per_preview_flight']
        final_y=9.5+params['stair_tread']*params['stair_steps_per_preview_flight']
        floor(name+'_Provisional_Landing',(center_x-flight_width/2,center_x+flight_width/2,final_y,13.3),mats['concrete'],stairs,final_z)
        for x in (center_x-flight_width/2+0.07,center_x+flight_width/2-0.07):
            rail(name+'_Handrail',(x,9.35,0.95),(x,final_y,final_z+0.95),mats['metal'],stairs)
            for index in range(0,params['stair_steps_per_preview_flight'],2):
                y=9.5+(index+0.5)*params['stair_tread']
                z=direction*params['stair_rise']*(index+1)
                rail(name+'_Post_%02d'%index,(x,y,z),(x,y,z+0.92),mats['metal'],stairs,0.018)
        box(name+'_Sign_Back',(center_x,9.12,2.53),(1.7,0.04,0.32),mats['frame'],stairs,0.02)
        text(name+'_Sign','2F  DOWN' if direction<0 else '4F  UP',(center_x,9.09,2.53),0.2,mats['whiteboard'],stairs)
    area_light('Stair_Core_Light',(-17.3,10.5,4.25),210,3,lighting)
    lift_center=-12.9
    floor('Lift_Shaft_Base',(-14.4,-11.4,8.2,11.2),mats['concrete'],stairs)
    wall_x('Lift_Shaft_West',-14.4,8.2,11.2,stairs)
    wall_x('Lift_Shaft_East',-11.4,8.2,11.2,stairs)
    wall_y('Lift_Shaft_Back',11.2,-14.4,-11.4,stairs)
    wall_y('Lift_Closed_Front',8.2,-14.4,-11.4,stairs)
    box('Lift_Roof',(lift_center,9.7,height+0.05),(3,3,0.1),mats['wall'],stairs)
    box('Lift_Door_Frame',(lift_center,8.08,1.22),(2.25,0.12,2.44),mats['frame'],stairs,0.015)
    for x in (lift_center-0.495,lift_center+0.495):
        box('Lift_Closed_Door',(x,8.005,1.14),(0.98,0.035,2.28),mats['metal'],stairs,0.008)
    box('Lift_Indicator',(lift_center,7.99,2.63),(0.42,0.035,0.19),mats['black'],stairs,0.01)
    text('Lift_Floor_Number','3',(lift_center,7.966,2.63),0.14,mats['emission'],stairs)
    box('Lift_Call_Panel',(-11.69,8.06,1.15),(0.13,0.02,0.3),mats['metal'],stairs,0.012)
    cylinder('Lift_Call_Button',(-11.69,8.043,1.15),0.026,0.008,mats['black'],stairs,(math.pi/2,0,0),16)
    text('Lift_Overview_Label','LIFT',(-12.9,9.7,height+0.12),0.4,mats['frame'],labels,(0,0,0))

    for name,location in [('PlayerStart_Reference',(width/2,0.8,1.7)),('Classroom_Rear_Exit',(0,1.275,0)),('Stair_3F_Connection',(-18.85,8.85,0)),('Downstairs_Continuation',(-18.85,12.8,-1.7))]:
        obj=bpy.data.objects.new(name,None)
        markers.objects.link(obj)
        obj.location=location
        obj.empty_display_type='ARROWS'
        obj.empty_display_size=0.5
    interior_camera=camera('Camera_Classroom',(width-0.65,0.7,1.78),(width*0.44,depth-1.1,1.46),presentation,20)
    doorway_camera=camera('Camera_Entrance',(-1.55,1.05,1.75),(5.2,7.2,1.4),presentation,18)
    overview_camera=camera('Camera_Floor03_Overview',(36,-39,48),(-10,8,0),presentation,ortho=55)
    sun_data=bpy.data.lights.new('Daylight_Sun','SUN')
    sun_data.energy=1.0
    sun_data.angle=0.35
    sun=bpy.data.objects.new('Daylight_Sun',sun_data)
    lighting.objects.link(sun)
    sun.rotation_euler=(0.4,-0.35,-0.5)
    world=bpy.data.worlds.new('Soft_Daylight')
    world.use_nodes=True
    world.node_tree.nodes['Background'].inputs['Color'].default_value=(0.62,0.7,0.8,1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value=0.25
    scene.world=world
    scene.render.engine='CYCLES'
    scene.cycles.samples=48
    scene.cycles.use_denoising=True
    scene.cycles.max_bounces=8
    scene.cycles.transparent_max_bounces=8
    scene.cycles.device='GPU'
    prefs=bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type='OPTIX'
    prefs.refresh_devices()
    gpu_available=False
    for device in prefs.devices:
        device.use=device.type=='OPTIX'
        gpu_available=gpu_available or device.use
    if not gpu_available:
        scene.cycles.device='CPU'
    scene.render.resolution_x=1600
    scene.render.resolution_y=1000
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.render.film_transparent=False
    scene.view_settings.view_transform='AgX'
    scene.view_settings.exposure=0.4
    scene.camera=interior_camera
    labels.hide_render=True
    labels.hide_viewport=True
    for area in bpy.context.screen.areas if bpy.context.screen else []:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'
            area.spaces.active.clip_end=250
    bpy.ops.object.select_all(action='DESELECT')
    report={
        'blender_version':bpy.app.version_string,
        'units':'meters',
        'classroom_dimensions_m':[width,depth,height],
        'student_desks':desk_index,
        'student_chairs':seat_count,
        'student_laptops':seat_count//2,
        'center_aisle_m':params['center_aisle_width'],
        'corridor_width_m':hall_width,
        'door_opening_m':params['door_width'],
        'objects':len(scene.objects),
        'mesh_objects':sum(obj.type=='MESH' for obj in scene.objects),
        'shared_furniture_meshes':True,
        'ue_project_modified_by_build':False,
        'notes':params['notes']
    }
    (ROOT/'build_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    output=ROOT/'EscapeFromKD_Floor03_v01.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(output),compress=True)
    print('KD_BUILD_COMPLETE',json.dumps(report,ensure_ascii=False),flush=True)
    return scene,ceilings,labels,interior_camera,doorway_camera,overview_camera


def main():
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    parser=argparse.ArgumentParser()
    parser.add_argument('--no-render',action='store_true')
    options=parser.parse_args(args)
    scene,ceilings,labels,interior,doorway,overview=build()
    if options.no_render:
        return
    preview_dir=ROOT/'Previews'
    preview_dir.mkdir(exist_ok=True)
    for name,cam,cutaway in [('classroom',interior,False),('entrance',doorway,False),('floor03_overview',overview,True)]:
        scene.camera=cam
        ceilings.hide_render=cutaway
        labels.hide_render=not cutaway
        labels.hide_viewport=not cutaway
        scene.render.filepath=str(preview_dir/(name+'.png'))
        print('KD_RENDER_START',name,flush=True)
        bpy.ops.render.render(write_still=True)
        print('KD_RENDER_COMPLETE',name,flush=True)


if __name__=='__main__':
    main()
