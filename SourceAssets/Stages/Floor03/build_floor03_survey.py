import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from build_floor03 import box, boxes, cylinder, rail, text, camera, area_light, instance, surface_uv
from build_furniture import FurnitureMesh
from build_materials import _solid

OUTPUT = ROOT / 'SurveyV02'
GROUPS = ['Structure', 'Ceilings', 'ClosedClassrooms', 'ClassroomFixtures',
          'GlazingFrames', 'Glass', 'Corridors', 'StairCore', 'Desks', 'Chairs', 'Laptops', 'Mice']
HEIGHT = 3.05
LIGHTS = []


def polygon_slab(name, points, top, thickness, material, target):
    # Keep the floor's upper face outward so FBX collision has the same walkable surface.
    if sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(points, points[1:]+points[:1])) < 0:
        points = list(reversed(points))
    n = len(points)
    vertices = [(x, y, top-thickness) for x, y in points]+[(x, y, top) for x, y in points]
    faces = [tuple(reversed(range(n))), tuple(range(n, 2*n))]
    faces += [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    target.objects.link(obj)
    surface_uv(obj, material)
    return obj


def segment(name, a, b, bottom, top, material, target, thickness=0.16):
    length = math.dist(a, b)
    obj = box(name, ((a[0]+b[0])/2, (a[1]+b[1])/2, (bottom+top)/2),
              (length, thickness, top-bottom), material, target)
    obj.rotation_euler.z = math.atan2(b[1]-a[1], b[0]-a[0])
    return obj


def floor_rect(name, bounds, material, target, top=0):
    x0, x1, y0, y1 = bounds
    return polygon_slab(name, [(x0,y0),(x1,y0),(x1,y1),(x0,y1)], top, 0.18, material, target)


def light(name, position, target, energy=65, size=1.2, temperature=5000):
    obj = area_light(name, position, energy, size, target)
    LIGHTS.append({'name': name, 'location_blender_m': list(position),
                   'lumens': 1900 if temperature == 5000 else 1100,
                   'size_m': size, 'temperature': temperature})
    return obj


def main():
    OUTPUT.mkdir(exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'EscapeFromKD_Floor03_v01.blend'))
    prototypes = {key: bpy.data.objects[name] for key, name in
                  [('desk','Desk_Prototype'), ('chair','Chair_Prototype'),
                   ('laptop','Laptop_Prototype'), ('mouse','Mouse_Prototype')]}
    for obj in list(bpy.data.objects):
        if obj not in prototypes.values():
            bpy.data.objects.remove(obj, do_unlink=True)
    cols = {}
    for name in GROUPS+['Lighting', 'Presentation']:
        col = bpy.data.collections.new('Survey_'+name)
        bpy.context.scene.collection.children.link(col)
        cols[name] = col
    names = {'wood':'LightOak','carpet':'ClassroomCarpet','hall':'CorridorCarpet',
             'wall':'PaintWarmWhite','ceiling':'AcousticCeiling','metal':'SilverMetal',
             'black':'BlackPlastic','rubber':'DarkRubber','glass':'ClearGlass',
             'frame':'DarkWindowFrames','white':'Whiteboard','screen':'LaptopScreen',
             'blue':'PosterBlue','orange':'PosterOrange','light':'LightDiffuser','concrete':'Concrete'}
    mats = {key:bpy.data.materials['KD_F03_'+name] for key,name in names.items()}
    mats['door'] = _solid('V02_DoorOak', (0.48,0.29,0.085), 0.48)
    mats['cream'] = _solid('V02_DeskLaminate', (0.72,0.66,0.48), 0.48)
    mats['grey'] = _solid('V02_SeatFabric', (0.20,0.22,0.22), 0.94)
    mats['teal'] = _solid('V02_StairDoor', (0.018,0.075,0.09), 0.55)
    mats['red'] = _solid('V02_FireRed', (0.6,0.018,0.012), 0.4)
    mats['gold'] = _solid('V02_Brass', (0.63,0.46,0.17), 0.33, 0.65)
    mats['green'] = _solid('V02_ExitGreen', (0.015,0.38,0.20), 0.36)
    mats['block'] = _solid('V02_GlassBlock', (0.20,0.29,0.31), 0.19, 0.22)
    mats['projection'] = _solid('V02_Projection', (0.55,0.69,0.67), 0.9)
    mats['projection'].node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (0.18,0.25,0.23,1)
    mats['projection'].node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 0.4
    scene = bpy.context.scene
    scene['stage'] = 'Escape From KD / Floor 03 / Matterport visual survey V02'
    scene['dimensions_are_provisional'] = True
    scene['reference_url'] = 'https://my.matterport.com/show/?m=DG9hQWWe91g'
    scene['measurement_basis'] = 'Viewer floorplan sample 9.20m over 127px; traced perimeter and visual estimates, not a measured architectural plan.'
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 32
    scene.cycles.use_denoising = True
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.refresh_devices()
    for device in prefs.devices:
        device.use = device.type == 'OPTIX'
    scene.cycles.device = 'GPU' if any(d.use for d in prefs.devices) else 'CPU'
    scene.view_settings.exposure = 0
    scene.render.resolution_x = 1440
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    for proto in prototypes.values():
        proto.hide_render = True
        proto.hide_set(True)

    def wall(name, a, b, group='Structure', bottom=0, top=HEIGHT, material='wall', thickness=0.16):
        return segment(name, a, b, bottom, top, mats[material], cols[group], thickness)

    def trim(a, b, group='Structure', z=0):
        wall('Black_skirt', a, b, group, z, z+0.075, 'black', 0.022)

    def ceiling_rect(name, bounds):
        x0,x1,y0,y1 = bounds
        return box(name, ((x0+x1)/2,(y0+y1)/2,HEIGHT+0.06), (x1-x0,y1-y0,0.12),mats['ceiling'],cols['Ceilings'])

    def luminaire(name, x, y, group='Ceilings', axis=0):
        obj=box(name+'_housing',(x,y,HEIGHT-0.055),(0.19,1.22,0.055),mats['metal'],cols[group],0.008)
        obj.rotation_euler.z=axis
        obj=box(name+'_lens',(x,y,HEIGHT-0.087),(0.145,1.15,0.022),mats['light'],cols[group],0.007)
        obj.rotation_euler.z=axis

    def ac(x,y):
        box('AC_beige_cassette',(x,y,HEIGHT-0.045),(0.9,0.9,0.09),mats['cream'],cols['Ceilings'],0.02)
        box('AC_center',(x,y,HEIGHT-0.098),(0.56,0.56,0.018),mats['wall'],cols['Ceilings'])
        for dx,dy,sx,sy in [(-0.35,0,0.1,0.7),(0.35,0,0.1,0.7),(0,-0.35,0.7,0.1),(0,0.35,0.7,0.1)]:
            box('AC_dark_vent',(x+dx,y+dy,HEIGHT-0.094),(sx,sy,0.008),mats['frame'],cols['Ceilings'])
        for j in range(9):
            box('AC_fins',(x-0.23+j*0.057,y,HEIGHT-0.111),(0.009,0.53,0.008),mats['cream'],cols['Ceilings'])

    def window(name,a,b,bottom=0.93,top=2.7,frame='frame',group='GlazingFrames',blinds=True):
        a,b=Vector((*a,0)),Vector((*b,0))
        along=(b-a).normalized()
        normal=Vector((-along.y,along.x,0))
        wall(name+'_lower',a[:2],b[:2],group,0,bottom)
        wall(name+'_upper',a[:2],b[:2],group,top,HEIGHT)
        for z in (bottom,top):
            wall(name+'_horizontal_frame',a[:2],b[:2],group,z-0.026,z+0.026,frame,0.07)
        for t in (0,0.5,1):
            p=a+(b-a)*t
            box(name+'_jamb',(p.x,p.y,(bottom+top)/2),(0.065,0.065,top-bottom),mats[frame],cols[group])
        wall(name+'_pane',a[:2],b[:2],'Glass',bottom+0.025,top-0.025,'glass',0.008)
        if blinds:
            for j in range(int((top-bottom-0.08)/0.041)):
                z=bottom+0.05+j*0.041
                p=a+normal*0.03
                q=b+normal*0.03
                wall(name+'_blind',p[:2],q[:2],group,z,z+0.015,'metal',0.026)
            p=(a+b)/2+normal*0.06
            rail(name+'_blind_cord',(p.x,p.y,top-0.12),(p.x,p.y,bottom+0.55),mats['white'],cols[group],0.002)

    def wood_door(name,x,y,width=1.1,rotation=0,group='GlazingFrames'):
        # Slit is a true opening with glass, rather than a dark decal on a solid door.
        before=set(cols[group].objects)|set(cols['Glass'].objects)
        for center,size in [((-0.18,0,1.1),(width-0.36,0.055,2.2)),
                            ((width/2-0.105,0,1.1),(0.21,0.055,2.2)),
                            ((width/2-0.285,0,0.19),(0.15,0.055,0.38)),
                            ((width/2-0.285,0,2.08),(0.15,0.055,0.24))]:
            box(name,center,size,mats['door'],cols[group],0.003)
        box(name+'_slit',(width/2-0.285,0,1.17),(0.15,0.009,1.58),mats['glass'],cols['Glass'])
        rail(name+'_handle',(-width/2+0.12,-0.05,0.88),(-width/2+0.12,-0.05,1.12),mats['metal'],cols[group],0.014)
        created=(set(cols[group].objects)|set(cols['Glass'].objects))-before
        for obj in created:
            p=obj.location.copy()
            obj.location=(x+p.x*math.cos(rotation)-p.y*math.sin(rotation),y+p.x*math.sin(rotation)+p.y*math.cos(rotation),p.z)
            obj.rotation_euler.z+=rotation

    def poster(name,x,y,z,rotation=0,group='ClassroomFixtures',kind=0):
        obj=box(name,(x,y,z),(0.43,0.018,0.63),mats['blue' if kind%2==0 else 'orange'],cols[group])
        obj.rotation_euler.z=rotation
        n=Vector((math.sin(rotation),-math.cos(rotation),0))
        text(name+'_heading','STUDENT\nPROJECT',(x+n.x*0.012,y+n.y*0.012,z+0.14),0.052,mats['white'],cols[group],(math.pi/2,0,rotation))
        strip=box(name+'_footer',(x+n.x*0.013,y+n.y*0.013,z-0.255),(0.42,0.006,0.08),mats['white'],cols[group])
        strip.rotation_euler.z=rotation

    def whiteboard(name,x,y,width=2.9):
        group=cols['ClassroomFixtures']
        box(name,(x,y,1.62),(width,0.045,1.05),mats['white'],group,0.016)
        for px in (x-width/2,x+width/2):
            box(name+'_frame',(px,y-0.026,1.62),(0.022,0.04,1.1),mats['metal'],group)
        for z in (1.08,2.16):
            box(name+'_frame',(x,y-0.026,z),(width+0.03,0.04,0.022),mats['metal'],group)
        for px in (x-width/2+0.18,x+width/2-0.18):
            rail(name+'_leg',(px,y,0.06),(px,y,1.12),mats['metal'],group,0.022)
            rail(name+'_foot',(px,y-0.3,0.055),(px,y+0.25,0.055),mats['metal'],group,0.022)
        box(name+'_tray',(x,y-0.1,1.07),(width,0.15,0.025),mats['metal'],group)
        box(name+'_eraser',(x-width/3,y-0.11,1.10),(0.13,0.055,0.04),mats['blue'],group,0.007)

    def clock(x,y,z):
        group=cols['ClassroomFixtures']
        cylinder('Clock_frame',(x,y,z),0.145,0.025,mats['metal'],group,(math.pi/2,0,0),48)
        cylinder('Clock_face',(x,y-0.018,z),0.132,0.009,mats['white'],group,(math.pi/2,0,0),48)
        for i in range(12):
            angle=i*math.tau/12
            rail('Clock_tick',(x+0.105*math.sin(angle),y-0.025,z+0.105*math.cos(angle)),
                 (x+0.121*math.sin(angle),y-0.025,z+0.121*math.cos(angle)),mats['black'],group,0.002)
        rail('Clock_hand',(x,y-0.028,z),(x-0.065,y-0.028,z+0.025),mats['black'],group,0.004)
        rail('Clock_hand',(x,y-0.029,z),(x+0.015,y-0.029,z+0.10),mats['black'],group,0.003)

    # Start lab: the five rows and room proportions come from the viewer's floorplan.
    W,D=8.05,10.15
    floor_rect('GameLab_floor',(0,W,0,D),mats['carpet'],cols['Structure'])
    ceiling_rect('GameLab_ceiling',(0,W,0,D))
    wall('GameLab_back',(0,0),(W,0))
    wall('GameLab_teaching',(0,D),(W,D))
    for a,b in [((0.1,0.1),(W-0.1,0.1)),((0.1,D-0.1),(W-0.1,D-0.1))]: trim(a,b)
    cursor=0
    for i,cy in enumerate((1.9,5.0,8.1)):
        wall('Window_pier',(W,cursor),(W,cy-1.08))
        window('GameLab_window_%d'%i,(W,cy-1.08),(W,cy+1.08))
        cursor=cy+1.08
        for j in range(2): poster('Window_poster_%d_%d'%(i,j),W-0.13,cy-0.57+j*1.08,1.28,-math.pi/2,kind=i+j)
    wall('Window_last_pier',(W,cursor),(W,D))
    trim((W-0.09,0),(W-0.09,D))
    for a,b in [(0,0.7),(1.95,2.45),(7.7,8.25),(9.5,D)]: wall('Hall_partition_pier',(0,a),(0,b),'GlazingFrames')
    window('Hall_partition',(0,2.45),(0,7.7),0.85,2.72,'wall',blinds=False)
    for i,cy in enumerate((1.325,8.875)):
        wall('Door_header',(0,cy-0.625),(0,cy+0.625),'GlazingFrames',2.25,2.45)
        wall('Door_transom',(0,cy-0.625),(0,cy+0.625),'Glass',2.45,2.87,'glass',0.008)
        wall('Door_top',(0,cy-0.625),(0,cy+0.625),'GlazingFrames',2.87,HEIGHT)
        wood_door('GameLab_open_door',-0.13,cy+(1.24 if i==0 else -1.24),1.18,math.pi/2)
        text('GameLab_name','Game Programming Lab.1',(-0.10,cy,2.3),0.067,mats['black'],cols['GlazingFrames'],(math.pi/2,0,-math.pi/2))
    for x in (2.65,5.4):
        box('GameLab_ceiling_beam',(x,D/2,2.89),(0.28,D,0.32),mats['wall'],cols['Ceilings'])
    for x in (1.3,4.0,6.75):
        for y in (1.55,3.25,4.95,6.65,8.35):
            luminaire('GameLab_fluorescent',x,y)
    for x,y in [(2.0,3.9),(4.65,3.9),(4.65,7.3),(6.05,7.3)]: ac(x,y)
    for x in (1.5,4,6.5):
        for y in (2.0,4.3,6.6,8.9): light('F03_GameLab', (x,y,2.72),cols['Lighting'])
    for row in range(5):
        y=1.7+row*1.48
        for d,x in enumerate((1.22,2.72,5.32,6.82)):
            desk=instance(prototypes['desk'],'GameLab_desk_%d_%d'%(row,d),(x,y,0),cols['Desks'])
            desk.scale.x=1.5/1.8
            for seat,offset in enumerate((-0.37,0.37)):
                instance(prototypes['chair'],'GameLab_chair',(x+offset,y-0.58,0),cols['Chairs'],0.035*math.sin(row*8+d*2+seat))
            instance(prototypes['laptop'],'GameLab_laptop',(x-0.15,y-0.035,0.72),cols['Laptops'],0.04*math.sin(row+d))
            instance(prototypes['mouse'],'GameLab_mouse',(x+0.23,y-0.13,0.72),cols['Mice'])
            rail('Desk_power_cable',(x+0.2,y+0.22,0.67),(x+0.18,y+0.24,0.08),mats['black'],cols['ClassroomFixtures'],0.003)
            box('Desk_power_strip',(x,y+0.23,0.735),(0.25,0.04,0.025),mats['white'],cols['ClassroomFixtures'],0.005)
    instance(prototypes['desk'],'Instructor_desk',(5.8,9.48,0),cols['Desks'])
    instance(prototypes['chair'],'Instructor_chair',(5.8,9.82,0),cols['Chairs'],math.pi)
    instance(prototypes['laptop'],'Instructor_laptop',(5.8,9.48,0.72),cols['Laptops'],math.pi)
    whiteboard('GameLab_whiteboard',2.05,9.93)
    clock(2.05,10.01,2.47)
    box('Projection_surface',(5.1,10.045,2.04),(2.55,0.016,1.48),mats['projection'],cols['ClassroomFixtures'])
    box('Projection_roller',(5.1,9.99,2.83),(2.72,0.13,0.08),mats['wall'],cols['ClassroomFixtures'],0.015)
    text('Projection_code','// GAME PROGRAMMING\n\nvoid Update(float deltaTime)\n{\n    player.Move(direction);\n    camera.LookAt(target);\n}\n\n// Build  /  Run  /  Debug',(5.1,10.031,2.08),0.061,mats['frame'],cols['ClassroomFixtures'])
    box('Teaching_service_door',(7.05,10.045,1.04),(0.75,0.035,2.08),mats['wall'],cols['ClassroomFixtures'])
    box('Teaching_service_trim',(7.05,10.01,2.10),(0.79,0.025,0.035),mats['metal'],cols['ClassroomFixtures'])
    rail('Service_door_handle',(7.28,9.99,1.02),(7.40,9.99,1.02),mats['metal'],cols['ClassroomFixtures'],0.009)
    box('Display_monitor',(7.45,9.47,1.35),(0.92,0.06,0.54),mats['black'],cols['ClassroomFixtures'],0.025)
    box('Display_screen',(7.45,9.433,1.35),(0.85,0.008,0.47),mats['screen'],cols['ClassroomFixtures'])
    rail('Display_stand',(7.45,9.47,0.06),(7.45,9.47,1.1),mats['metal'],cols['ClassroomFixtures'],0.025)
    box('Display_foot',(7.45,9.47,0.035),(0.65,0.45,0.04),mats['black'],cols['ClassroomFixtures'])
    for x in (0.75,7.25):
        box('Glass_storage_cabinet',(x,0.29,0.95),(0.75,0.47,1.9),mats['wall'],cols['ClassroomFixtures'],0.012)
        for z in (0.35,0.85,1.35,1.82):
            box('Cabinet_front_dark',(x,0.532,z),(0.65,0.015,0.38),mats['frame'],cols['ClassroomFixtures'])
            for j in range(5): box('Cabinet_contents',(x-0.25+j*0.11,0.546,z),(0.07,0.01,0.23),mats['blue' if j%2 else 'cream'],cols['ClassroomFixtures'])
        box('Cabinet_center_rail',(x,0.557,1.0),(0.035,0.03,1.8),mats['metal'],cols['ClassroomFixtures'])
    for x in (5.7,6.4):
        box('Back_wood_cupboard',(x,0.3,0.42),(0.66,0.45,0.83),mats['wood'],cols['ClassroomFixtures'])
        for z in (1.04,1.43):
            box('Blue_equipment_crate',(x,0.3,z),(0.58,0.40,0.34),mats['blue'],cols['ClassroomFixtures'],0.018)
            box('Crate_lid',(x,0.3,z+0.18),(0.62,0.43,0.035),mats['frame'],cols['ClassroomFixtures'])
            box('Crate_label',(x,0.507,z),(0.24,0.008,0.11),mats['white'],cols['ClassroomFixtures'])

    # The L-shaped galleries surround an actual open atrium, not an enclosed corridor.
    hall_poly=[(0,10.15),(-2.18,10.15),(-2.18,0),(-13.12,0),(-15.2,-1),(-15.2,-5.7),(-16.5,-5.7),
               (-16.5,-6.67),(-10.37,-6.67),(-10.37,-6.16),(-6.81,-2.46),(0,-2.46)]
    polygon_slab('3F_gallery_floor',hall_poly,0,0.18,mats['hall'],cols['Corridors'])
    polygon_slab('3F_gallery_ceiling',hall_poly,HEIGHT+0.12,0.12,mats['ceiling'],cols['Ceilings'])
    wall('Gallery_rear_end',(0,0),(0,-2.46),'Corridors')
    wall('Connector_outer',(0,-2.46),(-6.81,-2.46),'Corridors')
    wall('Lobby_diagonal_display',(-6.81,-2.46),(-10.37,-6.16),'Corridors')
    wall('Lobby_short_return',(-10.37,-6.16),(-10.37,-6.67),'Corridors')
    for a,b in [((0,-2.37),(-6.75,-2.37)),((-6.75,-2.37),(-10.30,-6.10))]: trim(a,b,'Corridors')

    def gallery(a,b,level=0):
        a,b=Vector((*a,0)),Vector((*b,0))
        length=(b-a).length
        n=max(1,round(length/3.1))
        direction=(b-a)/length
        for i in range(n):
            p=a+(b-a)*i/n
            q=a+(b-a)*(i+1)/n
            wall('Atrium_parapet',p[:2],q[:2],'Corridors',level,level+0.72,'wall',0.16)
            wall('Atrium_cap',p[:2],q[:2],'Corridors',level+0.72,level+0.75,'wall',0.28)
            rail('Atrium_cream_handrail',(p.x,p.y,level+1.02),(q.x,q.y,level+1.02),mats['wall'],cols['Corridors'],0.04)
            for t in (0.08,0.92):
                v=p+(q-p)*t
                rail('Rail_bracket',(v.x,v.y,level+0.74),(v.x,v.y,level+1.02),mats['metal'],cols['Corridors'],0.013)
            wall('Atrium_header',p[:2],q[:2],'Corridors',level+2.7,level+3.16,'wall',0.28)
            box('Atrium_pier',(p.x,p.y,level+1.53),(0.25,0.25,3.06),mats['wall'],cols['Corridors'])
        box('Atrium_end_pier',(b.x,b.y,level+1.53),(0.25,0.25,3.06),mats['wall'],cols['Corridors'])

    for level in (-3.15,0,3.15):
        gallery((-2.18,0),(-2.18,10.15),level)
        gallery((-2.18,0),(-13.12,0),level)
        gallery((-13.12,0),(-13.12,10.15),level)
        for i in range(4):
            x=-12.9+i*2.68
            wall('Glassblock_surround',(x,10.15),(x+2.65,10.15),'Corridors',level,level+0.7)
            wall('Glassblock_surround',(x,10.15),(x+2.65,10.15),'Corridors',level+2.6,level+3.15)
            for xx in (x,x+2.65):
                box('Glassblock_pier',(xx,10.15,level+1.65),(0.22,0.18,2.0),mats['wall'],cols['Corridors'])
            cells=[((x+0.27+c*0.20,10.15,level+0.87+r*0.20),(0.181,0.10,0.181)) for r in range(8) for c in range(11)]
            boxes('Atrium_glass_blocks',cells,mats['block'],cols['Corridors'])
            grid=[((x+0.27+c*0.20,10.15,level+1.57),(0.018,0.12,1.8)) for c in range(12)]
            grid += [((x+1.37,10.15,level+0.77+r*0.2),(2.4,0.12,0.018)) for r in range(10)]
            boxes('Glassblock_mortar',grid,mats['wall'],cols['Corridors'])
    floor_rect('Atrium_visible_bottom',(-13.2,-2.1,0,10.3),mats['concrete'],cols['Corridors'],-6.3)
    # Close the visible gallery backgrounds so the atrium never opens onto the world void.
    wall('Opposite_gallery_back',(-15.2,0),(-15.2,10.23),'Corridors',-6.48,8.95)
    wall('Opposite_gallery_return',(-15.2,10.23),(-13.12,10.23),'Corridors',-6.48,8.95)
    wall('Atrium_far_backing',(-13.12,10.3),(-2.18,10.3),'Corridors',-6.48,8.95)
    for bottom,top in [(-6.48,-3.15),(6.3,8.95)]:
        wall('Atrium_near_enclosure',(0,0),(0,10.3),'Corridors',bottom,top)
        wall('Atrium_front_enclosure',(-15.2,0),(0,0),'Corridors',bottom,top)
    for level in (-3.15,0,3.15):
        floor_rect('Opposite_gallery_floor',(-15.2,-13.12,0,10.23),mats['hall'],cols['Corridors'],level)
        floor_rect('Opposite_gallery_soffit',(-15.2,-13.12,0,10.23),mats['ceiling'],cols['Ceilings'],level+3.15)
    for level in (-3.15,3.15):
        floor_rect('Near_gallery_context_floor',(-2.18,0,0,10.15),mats['hall'],cols['Corridors'],level)
        floor_rect('Near_gallery_context_soffit',(-2.18,0,0,10.15),mats['ceiling'],cols['Ceilings'],level+3.15)
        wall('Near_gallery_context_back',(0,0),(0,10.15),'Corridors',level,level+3.15)
        floor_rect('Front_gallery_context_floor',(-15.2,0,-2.46,0),mats['hall'],cols['Corridors'],level)
        floor_rect('Front_gallery_context_soffit',(-15.2,0,-2.46,0),mats['ceiling'],cols['Ceilings'],level+3.15)
        wall('Front_gallery_context_back',(-15.2,-2.46),(0,-2.46),'Corridors',level,level+3.15)
        wall('Front_gallery_context_return',(-15.2,-2.46),(-15.2,0),'Corridors',level,level+3.15)
    floor_rect('Atrium_roof',(-15.3,0.1,-0.1,10.3),mats['ceiling'],cols['Ceilings'],8.95)
    for x,y in [(-1.08,1),(-1.08,4),(-1.08,7.3),(-1.08,9.5),(-3.4,-1.23),(-6,-1.23),(-8.5,-2),(-11.5,-3),(-14.5,-4.8)]:
        cylinder('Gallery_downlight',(x,y,HEIGHT-0.024),0.10,0.025,mats['light'],cols['Ceilings'],vertices=32)
        light('F03_Gallery',(x,y,2.88),cols['Lighting'],70,1.1,4500)
    area_light('Atrium_skylight',(-7.5,5,8.7),1500,8,cols['Lighting'])
    LIGHTS.append({'name':'F03_Atrium','location_blender_m':[-7.5,5,8.5],'lumens':14000,'size_m':6,'temperature':5800})
    for i in range(5): poster('Gallery_student_work',-0.10,3.3+i*0.65,1.15,-math.pi/2,'Corridors',i)
    # The architectural model is represented as geometry rather than a flat photograph.
    display=box('Architecture_display_table',(-8.5,-3.95,0.73),(1.7,0.65,0.06),mats['wood'],cols['Corridors'])
    display.rotation_euler.z=math.pi/4
    for dx,dy in [(-0.5,-0.5),(0.5,0.5)]:
        box('Display_trestle',(-8.5+dx,-3.95+dy,0.36),(0.10,0.55,0.72),mats['wood'],cols['Corridors'])
    for row in range(3):
        for col in range(5):
            cx,cy=-8.95+col*0.22,-4.0+row*0.11
            box('Model_building',(cx,cy,0.86+row*0.11),(0.18,0.10,0.2),mats['cream' if col%2 else 'white'],cols['Corridors'])
            rail('Model_truss',(cx-0.1,cy,0.76),(cx+0.1,cy,1.18),mats['wood'],cols['Corridors'],0.006)
    for x,y in [(-8,-3.7),(-10.8,-6.3)]:
        poster('Architecture_presentation',x,y,1.18,math.pi/4,'Corridors')
        rail('Easel_leg',(x,y,0),(x,y,1.55),mats['wood'],cols['Corridors'],0.02)

    # Adjacent lab remains closed for gameplay, with a furnished interior visible through glazing.
    floor_rect('AdjacentLab_floor',(-2.18,W,10.31,20.3),mats['carpet'],cols['ClosedClassrooms'])
    ceiling_rect('AdjacentLab_ceiling',(-2.18,W,10.31,20.3))
    for a,b in [((-2.18,10.31),(-2.18,20.3)),((-2.18,20.3),(W,20.3)),((W,20.3),(W,10.31)),((W,10.31),(0,10.31))]: wall('AdjacentLab_wall',a,b,'ClosedClassrooms')
    wood_door('AdjacentLab_closed_door',-1.08,10.31,1.2,0,'ClosedClassrooms')
    wall('Adjacent_door_left',(-2.18,10.31),(-1.7,10.31),'ClosedClassrooms')
    wall('Adjacent_door_right',(-0.46,10.31),(0,10.31),'ClosedClassrooms')
    wall('Adjacent_door_header',(-1.7,10.31),(-0.46,10.31),'ClosedClassrooms',2.2,HEIGHT)
    text('AdjacentLab_name','Game Programming Lab.2',(-1.08,10.20,2.35),0.07,mats['frame'],cols['ClosedClassrooms'])
    sled=FurnitureMesh({'black':mats['black'],'metal':mats['metal'],'rubber':mats['rubber']})
    sled.box((0,0,0.43),(0.43,0.40,0.035),'black')
    sled.box((0,-0.19,0.64),(0.43,0.025,0.24),'black')
    for x in (-0.19,0.19):
        sled.cylinder((x,-0.2,0.03),(x,0.18,0.03),0.012,'metal')
        sled.cylinder((x,0.18,0.03),(x,0.12,0.43),0.012,'metal')
        sled.cylinder((x,-0.2,0.03),(x,-0.21,0.72),0.012,'metal')
    sled_proto=sled.finish('Survey_sled_chair_prototype',prototypes['chair'].users_collection[0],0.002)
    sled_proto.hide_render=True
    sled_proto.hide_set(True)
    for row in range(6):
        y=11.7+row*1.28
        for x in (-0.65,1.0,2.65,5.3,6.95):
            desk=instance(prototypes['desk'],'AdjacentLab_desk',(x,y,0),cols['Desks'])
            desk.scale.x=1.65/1.8
            desk.data=desk.data.copy()
            for idx,mat in enumerate(desk.data.materials):
                if mat.name=='KD_F03_LightOak': desk.data.materials[idx]=mats['cream']
            for dx in (-0.40,0.40): instance(sled_proto,'AdjacentLab_sled_chair',(x+dx,y-0.57,0),cols['Chairs'])
            if row==2:
                box('Console_demo_unit',(x,y,0.85),(0.25,0.04,0.18),mats['black'],cols['ClassroomFixtures'],0.01)
                box('Console_colored_controller',(x-0.14,y,0.85),(0.035,0.04,0.18),mats['red'],cols['ClassroomFixtures'],0.008)
    whiteboard('AdjacentLab_whiteboard',2.8,20.05,3.4)
    clock(2.8,20.15,2.5)
    for x in (-0.7,2.9,6.5):
        for y in (12,14.5,17,19.3):
            luminaire('AdjacentLab_fluorescent',x,y)
        for y in (13,16.3,19): light('F03_AdjacentLab',(x,y,2.8),cols['Lighting'])
    ac(2.9,14.5)
    ac(6.5,17)

    cad=[(-10.37,-6.67),(-10.37,-15.66),(-13.63,-19.07),(-19.28,-19.07),
         (-22.47,-15.8),(-22.47,-9.72),(-19.36,-6.67)]
    polygon_slab('CADLab_floor',cad,0,0.18,mats['carpet'],cols['ClosedClassrooms'])
    polygon_slab('CADLab_ceiling',cad,HEIGHT+0.12,0.12,mats['ceiling'],cols['Ceilings'])
    for i,(a,b) in enumerate(zip(cad,cad[1:])):
        if i in (3,5):
            av,bv=Vector(a),Vector(b)
            mid=(av+bv)/2
            along=(bv-av).normalized()
            low,high=mid-along*0.85,mid+along*0.85
            wall('CADLab_window_pier',a,low,'ClosedClassrooms')
            window('CADLab_corner_window',low,high,0.95,2.6,'wall')
            wall('CADLab_window_pier',high,b,'ClosedClassrooms')
        else:
            wall('CADLab_perimeter',a,b,'ClosedClassrooms')
    wall('CADLab_entry_wall',cad[-1],(-14.0,-6.67),'ClosedClassrooms')
    wall('CADLab_entry_wall',(-11.6,-6.67),cad[0],'ClosedClassrooms')
    wall('CADLab_transom',(-14,-6.67),(-11.6,-6.67),'Glass',2.2,2.75,'glass',0.008)
    wall('CADLab_header',(-14,-6.67),(-11.6,-6.67),'ClosedClassrooms',2.75,HEIGHT)
    for x in (-13.4,-12.2): wood_door('CADLab_closed_door',x,-6.67,1.2,math.pi,'ClosedClassrooms')
    text('CADLab_name','CAD Lab.',(-12.8,-6.57,2.83),0.11,mats['black'],cols['ClosedClassrooms'],(math.pi/2,0,math.pi))
    for row in range(6):
        x=-12.9-row*1.27
        for bank in (-8.85,-12.4,-15.95):
            for side in (-0.75,0.75):
                y=bank+side
                desk=instance(prototypes['desk'],'CADLab_desk',(x,y,0),cols['Desks'],math.pi/2)
                desk.scale.x=1.5/1.8
                desk.data=desk.data.copy()
                for idx,mat in enumerate(desk.data.materials):
                    if mat.name=='KD_F03_LightOak': desk.data.materials[idx]=mats['cream']
                for dy in (-0.37,0.37): instance(prototypes['chair'],'CADLab_chair',(x+0.57,y+dy,0),cols['Chairs'],math.pi/2)
    for x in (-12.5,-15.2,-18,-20.5):
        for y in (-8.6,-12.1,-15.6): luminaire('CADLab_fluorescent',x,y,axis=math.pi/2)
    for x in (-13.3,-16.4,-19.5):
        for y in (-8.9,-12.5,-16.1): light('F03_CADLab',(x,y,2.8),cols['Lighting'])
    for x,y in [(-14.5,-10.5),(-18,-14.3)]: ac(x,y)
    for x,y in [(-21,-10.8),(-21,-14.5)]:
        instance(prototypes['desk'],'CAD_instructor_desk',(x,y,0),cols['Desks'],math.pi/2)
    for x,y in [(-21.7,-9.9),(-21.7,-15.2)]:
        box('CAD_pinboard',(x,y,1.8),(0.06,1.7,1.25),mats['white'],cols['ClassroomFixtures'])
    # Stair continuation below/above the observed 3F entrance is deliberately bounded.
    # Its 10-step flights preserve the existing game's one-flight traversal scope.
    floor_rect('Stair_entry_landing',(-17.8,-15.2,-5.7,-1.0),mats['hall'],cols['StairCore'])
    ceiling_rect('Stair_entry_ceiling',(-17.8,-15.2,-5.7,-1.0))
    floor_rect('Stair_core_roof',(-22.4,-17.8,-5.8,-0.9),mats['ceiling'],cols['Ceilings'],4.85)
    wall('Lobby_stair_left',(-13.12,0),(-15.2,-1.0),'Corridors')
    wall('Lobby_stair_right',(-16.5,-5.5),(-16.5,-6.67),'Corridors')
    wall('Stair_side',(-17.8,-1),(-22.3,-1),'StairCore',-1.9,4.6)
    wall('Stair_side',(-17.8,-5.7),(-22.3,-5.7),'StairCore',-1.9,4.6)
    wall('Stair_end',(-22.3,-1),(-22.3,-5.7),'StairCore',-1.9,4.6)
    for direction,y,name in [(1,-4.7,'Up'),(-1,-2.0,'Down')]:
        for i in range(10):
            x=-17.8-(i+0.5)*0.28
            z=direction*(i+1)*0.17
            box('Stair_'+name+'_tread',(x,y,z-0.11),(0.28,1.5,0.22),mats['hall'],cols['StairCore'])
            box('Stair_'+name+'_nosing',(x+0.12,y,z+0.006),(0.04,1.5,0.012),mats['metal'],cols['StairCore'])
        floor_rect(name+'_half_landing',(-22.3,-20.6,y-0.75,y+0.75),mats['hall'],cols['StairCore'],direction*1.7)
        for yy in (y-0.77,y+0.77):
            vertices=[(x,yp,z+offset) for yp in (yy-0.06,yy+0.06)
                      for x,z in [(-17.8,0),(-20.6,direction*1.7)] for offset in (-0.08,0.86)]
            mesh=bpy.data.meshes.new('Stair_solid_balustrade')
            mesh.from_pydata(vertices,[],[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(1,3,7,5),(0,4,6,2)])
            mesh.materials.append(mats['wall'])
            mesh.update()
            panel=bpy.data.objects.new('Stair_'+name+'_solid_balustrade',mesh)
            cols['StairCore'].objects.link(panel)
            surface_uv(panel,mats['wall'])
            rail('Stair_'+name+'_handrail',(-17.75,yy,0.96),(-20.6,yy,direction*1.7+0.96),mats['metal'],cols['StairCore'],0.024)
    box('Stair_floor_identity',(-16.8,-5.64,1.5),(0.68,0.035,3.0),mats['teal'],cols['StairCore'])
    text('Stair_floor_3','3',(-16.8,-5.60,2.37),0.3,mats['gold'],cols['StairCore'],(math.pi/2,0,math.pi))
    box('Stair_exit_sign',(-16.7,-5.58,2.87),(0.31,0.10,0.15),mats['green'],cols['StairCore'])
    text('Stair_exit_glyph','EXIT',(-16.7,-5.51,2.87),0.075,mats['white'],cols['StairCore'],(math.pi/2,0,math.pi))
    wall('Lift_front',(-16.5,-5.5),(-14.2,-5.5),'StairCore')
    box('Lift_stainless_frame',(-15.25,-5.39,1.47),(2.05,0.08,2.94),mats['metal'],cols['StairCore'])
    for x in (-15.72,-14.78): box('Lift_closed_leaf',(x,-5.33,1.08),(0.925,0.035,2.16),mats['metal'],cols['StairCore'],0.003)
    box('Lift_center_seam',(-15.25,-5.305,1.08),(0.012,0.008,2.16),mats['black'],cols['StairCore'])
    box('Lift_indicator',(-15.25,-5.305,2.34),(0.8,0.012,0.095),mats['black'],cols['StairCore'])
    text('Lift_number','3',(-15.25,-5.293,2.34),0.063,mats['red'],cols['StairCore'],(math.pi/2,0,math.pi))
    light('F03_Stair',(-19,-3.35,4.0),cols['Lighting'],120,2.5,4500)
    light('F03_Lift',(-15,-3.7,2.85),cols['Lighting'],80,1.0,4500)
    for x,y in [(-14.2,-5.1),(-0.32,0.3)]:
        cylinder('Fire_extinguisher',(x,y,0.28),0.075,0.47,mats['red'],cols['Corridors'],vertices=24)
        box('Extinguisher_handle',(x,y,0.55),(0.14,0.05,0.03),mats['black'],cols['Corridors'])
        box('Extinguisher_label',(x,y-0.078,0.31),(0.105,0.008,0.20),mats['white'],cols['Corridors'])

    scene.world=bpy.data.worlds.get('Soft_Daylight')
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=0.18
    camera_specs=[('classroom',(4.02,0.73,1.7),(4,8,1.45),21),
                  ('gallery',(-1.05,8.5,1.7),(-1.05,0.2,1.45),23),
                  ('lobby',(-11.4,-2.6,1.7),(-16.7,-4.3,1.4),23),
                  ('cad',(-11.2,-12.3,1.7),(-21,-12.4,1.4),22)]
    cameras={name:camera('Camera_'+name,loc,aim,cols['Presentation'],lens) for name,loc,aim,lens in camera_specs}
    cameras['overview']=camera('Camera_overview',(21,-37,37),(-6,0,0),cols['Presentation'],ortho=46)
    scene.camera=cameras['classroom']
    for area in bpy.context.screen.areas if bpy.context.screen else []:
        if area.type=='VIEW_3D': area.spaces.active.region_3d.view_perspective='CAMERA'
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.object.select_all(action='DESELECT')
    output=OUTPUT/'EscapeFromKD_Floor03_v02.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(output),compress=True)
    report={'source_url':scene['reference_url'],'blender_version':bpy.app.version_string,
            'measurement_sample_m':9.20,'sample_floorplan_pixels':127,'meters_per_reference_pixel':9.2/127,
            'start_lab_dimensions_m':[W,D,HEIGHT],'start_lab_rows':5,'start_lab_student_desks':20,
            'start_lab_student_chairs':40,'groups':{name:len(cols[name].objects) for name in GROUPS},
            'lights':LIGHTS,'player_start_ue_cm':[402,-73,100],
            'walk_route_blender_m':[[4.02,0.73],[4.02,8.875],[-1.05,8.875],[-1.05,-1.2],[-8.8,-1.2],[-14.5,-3.2],[-16.5,-3.2],[-16.5,-2.0],[-21.5,-2.0]],
            'notes':['Viewer-derived proportions, not survey-grade dimensions.',
                     'Other classrooms remain closed, preserving the existing gameplay scope.',
                     'Visible atrium surroundings included; other complete floors are not built.',
                     'Stair flights beyond the photographed entrance are estimated.',
                     'Poster artwork, screen content and small equipment are representative original geometry/text, not scans.']}
    (OUTPUT/'survey_build_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('SURVEY_BUILD_COMPLETE',json.dumps(report,ensure_ascii=False),flush=True)
    if '--no-render' not in sys.argv:
        for name,cam in cameras.items():
            scene.camera=cam
            cols['Ceilings'].hide_render=name=='overview'
            scene.render.filepath=str(OUTPUT/(name+'.png'))
            print('SURVEY_RENDER_START',name,flush=True)
            bpy.ops.render.render(write_still=True)
            print('SURVEY_RENDER_COMPLETE',name,flush=True)


if __name__=='__main__':
    main()
