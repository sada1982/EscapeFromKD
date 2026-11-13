import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector


ROOT = Path(__file__).resolve().parent
EXPORT = ROOT / 'Export'
PREVIEW = ROOT / 'Previews'
for directory in (EXPORT, PREVIEW):
    directory.mkdir(exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.unit_settings.scale_length = 1.0
scene.render.fps = 30
parts = []
document_parts = []


def material(name, color, metallic=0.0, roughness=0.4, emission=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Roughness'].default_value = roughness
    shader.inputs['Emission Color'].default_value = (*color, 1)
    shader.inputs['Emission Strength'].default_value = emission
    mat.diffuse_color = (*color, 1)
    return mat


ivory = material('M_Admission_Ivory', (.68, .72, .75), .55, .29)
edge = material('M_Admission_Titanium', (.30, .37, .40), .8, .32)
dark = material('M_Admission_Joint', (.022, .029, .035), .30, .48)
rubber = material('M_Admission_Grip', (.009, .014, .018), .05, .63)
cyan = material('M_Admission_Cyan', (.015, .53, .64), .35, .24, 2.3)
paper = material('M_Admission_Agreement', (.9, .88, .80), 0, .77)
paper_image = bpy.data.images.load(str(ROOT / 'Textures/T_AdmissionAgreement_BaseColor.png'))
tex = paper.node_tree.nodes.new('ShaderNodeTexImage')
tex.image = paper_image
paper.node_tree.links.new(tex.outputs['Color'], paper.node_tree.nodes['Principled BSDF'].inputs['Base Color'])


def select_only(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def finish(obj, name, mat, bone, bevel=0.0, collection=None):
    obj.name = name
    select_only(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if bevel:
        modifier = obj.modifiers.new('Manufactured edge', 'BEVEL')
        modifier.width = bevel
        modifier.segments = 3
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.use_smooth = True
    if bone:
        group = obj.vertex_groups.new(name=bone)
        group.add(list(range(len(obj.data.vertices))), 1.0, 'REPLACE')
    (collection if collection is not None else parts).append(obj)
    return obj


def sphere(name, center, size, mat, bone, segments=24, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=center)
    obj = bpy.context.object
    obj.scale = size
    return finish(obj, name, mat, bone)


def box(name, center, size, mat, bone, bevel=.008, collection=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.scale = size
    return finish(obj, name, mat, bone, bevel, collection)


def cylinder(name, a, b, radius, mat, bone, vertices=20):
    a, b = Vector(a), Vector(b)
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=(b-a).length, location=(a+b)*.5)
    obj = bpy.context.object
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(b-a)
    return finish(obj, name, mat, bone, .002)


def tube(name, points, radius, mat, bone):
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    curve.resolution_u = 8
    curve.bevel_depth = radius
    curve.bevel_resolution = 3
    spline = curve.splines.new('POLY')
    spline.points.add(len(points)-1)
    for item, position in zip(spline.points, points):
        item.co = (*position, 1)
    obj = bpy.data.objects.new(name, curve)
    scene.collection.objects.link(obj)
    select_only(obj)
    bpy.ops.object.convert(target='MESH')
    return finish(obj, name, mat, bone)


def loft(name, a, b, width, depth, mat, bone, profile=None, steps=24):
    a, b = Vector(a), Vector(b)
    axis = (b-a).normalized()
    front = Vector((0, -1, 0))
    front = (front-axis*front.dot(axis)).normalized()
    if front.length < .1:
        front = Vector((0, 0, 1))
    side = front.cross(axis).normalized()
    if profile is None:
        profile = [(0, .52), (.07, .85), (.22, 1), (.55, .91), (.84, .69), (.97, .50), (1, .44)]
    vertices = []
    for t, radius in profile:
        center = a+(b-a)*t
        for index in range(steps):
            angle = 2*math.pi*index/steps
            vertices.append(center+side*(math.cos(angle)*width*radius)+front*(math.sin(angle)*depth*radius))
    faces = []
    for ring in range(len(profile)-1):
        for j in range(steps):
            faces.append((ring*steps+j, ring*steps+(j+1)%steps, (ring+1)*steps+(j+1)%steps, (ring+1)*steps+j))
    faces.extend([tuple(reversed(range(steps))), tuple((len(profile)-1)*steps+j for j in range(steps))])
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    return finish(obj, name, mat, bone)


def plate(name, outline, front_y, bulge, mat, bone, thickness=.018):
    center = Vector((sum(x for x,z in outline)/len(outline), front_y-bulge, sum(z for x,z in outline)/len(outline)))
    n = len(outline)
    vertices = [(x, front_y, z) for x,z in outline] + [center] + [(x, front_y+thickness, z) for x,z in outline]
    faces = [(j, (j+1)%n, n) for j in range(n)]
    faces += [(j, n+1+j, n+1+(j+1)%n, (j+1)%n) for j in range(n)]
    faces.append(tuple(n+1+j for j in reversed(range(n))))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    return finish(obj, name, mat, bone, .005)


bones = {}


def bone(name, head, tail, parent=None):
    bones[name] = {'head': Vector(head), 'tail': Vector(tail), 'parent': parent}


bone('root', (0,0,0), (0,0,.15))
bone('pelvis', (0,0,.97), (0,0,1.075), 'root')
bone('spine_01', (0,0,1.075), (0,0,1.20), 'pelvis')
bone('spine_02', (0,0,1.20), (0,0,1.36), 'spine_01')
bone('spine_03', (0,0,1.36), (0,0,1.53), 'spine_02')
bone('neck', (0,0,1.53), (0,0,1.635), 'spine_03')
bone('head', (0,0,1.635), (0,0,1.86), 'neck')
for suffix, sign in [('l',1),('r',-1)]:
    shoulder = (sign*.235,0,1.49)
    elbow = (.35,-.065,1.17) if sign == 1 else (-.345,0,1.18)
    wrist = (.425,-.345,1.205) if sign == 1 else (-.385,-.035,.93)
    hand_tip = (.435,-.395,1.18) if sign == 1 else (-.395,-.055,.855)
    bone('clavicle_'+suffix, (sign*.04,0,1.49), shoulder, 'spine_03')
    bone('upperarm_'+suffix, shoulder, elbow, 'clavicle_'+suffix)
    bone('lowerarm_'+suffix, elbow, wrist, 'upperarm_'+suffix)
    bone('hand_'+suffix, wrist, hand_tip, 'lowerarm_'+suffix)
    bone('thigh_'+suffix, (sign*.103,0,.97), (sign*.108,-.025,.54), 'pelvis')
    bone('calf_'+suffix, (sign*.108,-.025,.54), (sign*.108,0,.115), 'thigh_'+suffix)
    bone('foot_'+suffix, (sign*.108,0,.115), (sign*.108,-.16,.06), 'calf_'+suffix)
    bone('ball_'+suffix, (sign*.108,-.16,.06), (sign*.108,-.225,.055), 'foot_'+suffix)
bone('document', (.29,-.402,1.205), (.29,-.402,1.305), 'hand_l')

bpy.ops.object.armature_add(enter_editmode=True, location=(0,0,0))
rig = bpy.context.object
rig.name = 'AdmissionRig'
rig.data.name = 'SKEL_AdmissionRobot'
rig.data.edit_bones.remove(rig.data.edit_bones[0])
for name, data in bones.items():
    edit = rig.data.edit_bones.new(name)
    edit.head = data['head']
    edit.tail = data['tail']
    if data['parent']:
        edit.parent = rig.data.edit_bones[data['parent']]
    edit.use_connect = False
bpy.ops.object.mode_set(mode='OBJECT')
rig.show_in_front = True
for p in rig.pose.bones:
    p.rotation_mode = 'QUATERNION'

# Internal suit and compact pelvic structure.
sphere('Thorax core', (0,.005,1.365), (.193,.102,.207), dark, 'spine_03')
sphere('Abdominal core', (0,0,1.16), (.121,.083,.165), dark, 'spine_02')
sphere('Pelvic core', (0,0,.995), (.147,.096,.10), dark, 'pelvis')
for i,z in enumerate((1.09,1.145,1.20)):
    xw = (.096,.112,.121)[i]
    plate('Floating abdominal plate '+str(i), [(-xw,z+.027),(-xw*.65,z-.027),(0,z-.052),(xw*.65,z-.027),(xw,z+.027),(0,z+.053)], -.092, .024, ivory, 'spine_01' if i == 0 else 'spine_02')
for sign in (-1,1):
    outline = [(sign*.012,1.497),(sign*.070,1.525),(sign*.157,1.494),(sign*.203,1.435),(sign*.176,1.353),(sign*.101,1.288),(sign*.025,1.328)]
    if sign < 0:
        outline.reverse()
    plate('Sculpted pectoral '+str(sign), outline, -.091, .045, ivory, 'spine_03')
    tube('Pectoral accent '+str(sign), [(sign*.035,-.132,1.340),(sign*.082,-.134,1.317),(sign*.114,-.123,1.338)], .0022, cyan, 'spine_03')
    plate('Lower oblique '+str(sign), [(sign*.075,1.19),(sign*.142,1.14),(sign*.144,1.048),(sign*.091,1.06),(sign*.065,1.12)], -.054, .012, edge, 'spine_01')
    plate('Hip floating plate '+str(sign), [(sign*.035,1.055),(sign*.113,1.067),(sign*.161,1.005),(sign*.14,.935),(sign*.094,.91),(sign*.051,.968)], -.065, .027, ivory, 'pelvis')
plate('Pelvic front', [(-.055,1.015),(-.052,.925),(0,.875),(.052,.925),(.055,1.015),(0,1.04)], -.085, .016, edge, 'pelvis')
loft('Spinal column', (0,.09,1.075),(0,.096,1.51), .052,.025,edge,'spine_02')
for sign in (-1,1):
    sphere('Scapula armor '+str(sign), (sign*.097,.084,1.405),(.083,.047,.125),ivory,'spine_03')
    tube('Rear cyan seam '+str(sign),[(sign*.04,.12,1.31),(sign*.073,.126,1.36)],.002,cyan,'spine_03')
cylinder('Neck flexor',(0,0,1.525),(0,0,1.65),.041,dark,'neck')
loft('Raised ceramic collar',(0,0,1.51),(0,0,1.596),.065,.057,ivory,'neck',[(0,1),(.25,.99),(.78,.72),(1,.70)])
for z in (1.604,1.619):
    bpy.ops.mesh.primitive_torus_add(major_radius=.047, minor_radius=.0025, major_segments=24, minor_segments=6, location=(0,0,z))
    finish(bpy.context.object,'Neck flex ring',edge,'neck')

# Smooth faceless helmet with a narrow cyan optical seam.
sphere('Helmet dark inner', (0,.006,1.747),(.102,.094,.132),dark,'head',32,20)
sphere('Cranial shell', (0,.020,1.769),(.101,.088,.121),ivory,'head',32,20)
face_rows = [(1.871,.014,-.031),(1.858,.052,-.068),(1.821,.083,-.089),(1.770,.088,-.101),(1.722,.071,-.104),(1.685,.047,-.089),(1.672,.024,-.075)]
verts=[]
for z,w,y in face_rows:
    for j in range(13):
        u=-1+2*j/12
        verts.append((u*w,y+.020*u*u,z+.004*u*u))
faces=[]
for i in range(len(face_rows)-1):
    for j in range(12):
        faces.append((i*13+j,i*13+j+1,(i+1)*13+j+1,(i+1)*13+j))
mesh=bpy.data.meshes.new('Sculpted face mesh')
mesh.from_pydata(verts,[],faces)
mesh.update()
obj=bpy.data.objects.new('Featureless faceplate',mesh)
scene.collection.objects.link(obj)
finish(obj,'Featureless faceplate',ivory,'head')
mod=obj.modifiers.new('Smooth facial curvature','SUBSURF')
mod.levels=2
select_only(obj)
bpy.ops.object.modifier_apply(modifier=mod.name)
mod=obj.modifiers.new('Faceplate thickness','SOLIDIFY')
mod.thickness=.007
select_only(obj)
bpy.ops.object.modifier_apply(modifier=mod.name)
tube('Dark optical seam',[(-.075,-.087,1.718),(-.046,-.103,1.701),(0,-.108,1.686),(.046,-.103,1.701),(.075,-.087,1.718)],.007,dark,'head')
tube('Cyan optical ribbon',[(-.074,-.094,1.718),(-.044,-.109,1.702),(0,-.114,1.688),(.044,-.109,1.702),(.074,-.094,1.718)],.0027,cyan,'head')
for sign in(-1,1):
    sphere('Temple panel '+str(sign),(sign*.091,.018,1.755),(.012,.048,.070),edge,'head')
    sphere('Temple ceramic '+str(sign),(sign*.099,.022,1.763),(.006,.034,.048),ivory,'head')

for suffix,sign in [('l',1),('r',-1)]:
    upper = bones['upperarm_'+suffix]
    lower = bones['lowerarm_'+suffix]
    thigh = bones['thigh_'+suffix]
    calf = bones['calf_'+suffix]
    sphere('Shoulder joint '+suffix,upper['head'],(.055,.050,.055),dark,'upperarm_'+suffix)
    loft('Layered shoulder shell '+suffix,upper['head']+Vector((sign*.005,0,.037)),upper['head'].lerp(upper['tail'],.43)+Vector((sign*.023,0,0)),.079,.074,ivory,'upperarm_'+suffix,[(0,.32),(.10,.76),(.24,1),(.60,.94),(.88,.75),(1,.65)])
    loft('Upper arm underlay '+suffix,upper['head'],upper['tail'],.049,.047,dark,'upperarm_'+suffix)
    loft('Upper arm armor '+suffix,upper['head'].lerp(upper['tail'],.34),upper['head'].lerp(upper['tail'],.92),.056,.052,ivory,'upperarm_'+suffix)
    sphere('Elbow spherical joint '+suffix,lower['head'],(.048,.046,.047),dark,'lowerarm_'+suffix)
    cylinder('Elbow cap '+suffix,lower['head']+Vector((sign*.039,0,0)),lower['head']+Vector((sign*.050,0,0)),.027,edge,'lowerarm_'+suffix)
    loft('Forearm underlay '+suffix,lower['head'],lower['tail'],.039,.041,dark,'lowerarm_'+suffix)
    loft('Forearm sculpted shell '+suffix,lower['head'].lerp(lower['tail'],.13),lower['head'].lerp(lower['tail'],.93),.059,.057,ivory,'lowerarm_'+suffix,[(0,.53),(.08,.85),(.27,1),(.54,.88),(.82,.64),(1,.53)])
    sphere('Wrist socket '+suffix,lower['tail'],(.031,.032,.031),dark,'hand_'+suffix)
    sphere('Hip socket '+suffix,thigh['head'],(.071,.065,.074),dark,'thigh_'+suffix)
    loft('Thigh underlay '+suffix,thigh['head'],thigh['tail'],.067,.062,dark,'thigh_'+suffix)
    loft('Thigh armor '+suffix,thigh['head'].lerp(thigh['tail'],.10),thigh['head'].lerp(thigh['tail'],.94),.079,.074,ivory,'thigh_'+suffix,[(0,.64),(.07,.84),(.23,1),(.49,.91),(.76,.67),(.94,.46),(1,.41)])
    sphere('Knee joint '+suffix,calf['head'],(.052,.048,.051),dark,'calf_'+suffix)
    kneex=calf['head'].x
    plate('Knee armor '+suffix,[(kneex-.041,.58),(kneex-.043,.535),(kneex,.496),(kneex+.043,.535),(kneex+.041,.58),(kneex,.602)],-.058,.012,edge,'calf_'+suffix,.012)
    cylinder('Knee side cap '+suffix,calf['head']+Vector((sign*.045,0,0)),calf['head']+Vector((sign*.057,0,0)),.025,edge,'calf_'+suffix)
    loft('Shin flexor '+suffix,calf['head'],calf['tail'],.041,.043,dark,'calf_'+suffix)
    loft('Shin long armor '+suffix,calf['head'].lerp(calf['tail'],.13),calf['head'].lerp(calf['tail'],.89),.058,.064,ivory,'calf_'+suffix,[(0,.61),(.09,.84),(.27,1),(.52,.81),(.82,.56),(1,.44)])
    sphere('Ankle joint '+suffix,calf['tail'],(.033,.034,.034),dark,'foot_'+suffix)
    x=sign*.108
    box('Foot rubber sole '+suffix,(x,-.067,.024),(.109,.255,.032),rubber,'foot_'+suffix,.014)
    sphere('Boot instep '+suffix,(x,-.050,.075),(.052,.113,.056),ivory,'foot_'+suffix)
    box('Heel cage '+suffix,(x,.036,.075),(.082,.071,.095),edge,'foot_'+suffix,.013)
    box('Toe shell '+suffix,(x,-.142,.057),(.105,.103,.056),ivory,'ball_'+suffix,.018)
    tube('Shin optical seam '+suffix,[(x+sign*.035,-.048,.401),(x+sign*.029,-.043,.34)],.0017,cyan,'calf_'+suffix)

# Hands have separate curved mechanical fingers around the paper board.
sphere('Left palm',( .435,-.375,1.198),(.025,.026,.052),dark,'hand_l')
sphere('Left dorsal armor',(.449,-.363,1.201),(.016,.022,.047),ivory,'hand_l')
for i in range(4):
    z=1.232-i*.023
    pts=[(.451,-.375,z),(.437,-.405,z-.003),(.408,-.420,z-.005),(.391,-.416,z-.007)]
    for j in range(3):
        cylinder('Left finger %s %s'%(i,j),pts[j],pts[j+1],.008,edge if j != 1 else dark,'hand_l',12)
        sphere('Left knuckle %s %s'%(i,j),pts[j],(.009,.009,.009),dark,'hand_l',12,8)
tube('Left thumb',[(.425,-.352,1.24),(.396,-.364,1.255),(.377,-.394,1.247)],.010,edge,'hand_l')
sphere('Right palm',(-.397,-.050,.887),(.035,.024,.047),dark,'hand_r')
sphere('Right hand armor',(-.398,-.025,.888),(.030,.010,.039),ivory,'hand_r')
for i in range(4):
    x=-.421+i*.018
    pts=[(x,-.052,.857),(x,-.060,.833),(x,-.074,.814),(x,-.087,.816)]
    for j in range(3):
        cylinder('Right finger %s %s'%(i,j),pts[j],pts[j+1],.0068,edge if j !=1 else dark,'hand_r',12)
tube('Right thumb',[(-.368,-.045,.900),(-.354,-.064,.873),(-.362,-.083,.857)],.0085,edge,'hand_r')

# The clipboard is an independent rigid mesh region attached to its own bone.
box('Clipboard rim',(.29,-.402,1.205),(.250,.017,.349),dark,'document',.011,document_parts)
box('Clipboard paper stack',(.29,-.413,1.205),(.227,.004,.325),paper,'document',.002,document_parts)
verts=[(.178,-.416,1.044),(.402,-.416,1.044),(.402,-.416,1.366),(.178,-.416,1.366)]
mesh=bpy.data.meshes.new('Agreement printed face')
mesh.from_pydata(verts,[],[(0,1,2,3)])
mesh.update()
obj=bpy.data.objects.new('Agreement printed face',mesh)
scene.collection.objects.link(obj)
uv=mesh.uv_layers.new(name='UVMap')
for loop,coord in zip(mesh.loops,[(0,0),(1,0),(1,1),(0,1)]):
    uv.data[loop.index].uv=coord
finish(obj,'Agreement printed face',paper,'document',collection=document_parts)
box('Clip steel upper',(.29,-.421,1.371),(.110,.014,.022),edge,'document',.004,document_parts)
box('Clip steel bar',(.29,-.428,1.351),(.104,.008,.009),edge,'document',.003,document_parts)
for sign in (-1,1):
    box('Clip side '+str(sign),(.29+sign*.048,-.426,1.360),(.007,.008,.022),edge,'document',.002,document_parts)


def joined(objects,name):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.object.join()
    obj=bpy.context.object
    obj.name=name
    return obj


clipboard=joined(document_parts,'SM_AdmissionClipboard')
clipboard_static=clipboard.copy()
clipboard_static.data=clipboard.data.copy()
scene.collection.objects.link(clipboard_static)
clipboard_static.name='SM_AdmissionClipboard_Standalone'
clipboard_static.data.transform(Matrix.Translation(-bones['document']['head']))
clipboard_static.data.transform(Matrix.Scale(100,4))
scene.unit_settings.scale_length=.01
select_only(clipboard_static)
bpy.ops.export_scene.fbx(filepath=str(EXPORT/'SM_AdmissionClipboard.fbx'),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',use_mesh_modifiers=True,mesh_smooth_type='FACE',bake_anim=False,path_mode='COPY',embed_textures=True)
bpy.data.objects.remove(clipboard_static,do_unlink=True)
body=joined(parts+[clipboard],'SK_AdmissionRobot')
select_only(body)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.mesh.select_all(action='DESELECT')
bpy.ops.object.mode_set(mode='OBJECT')
for polygon in body.data.polygons:
    polygon.select=body.data.materials[polygon.material_index]!=paper
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=.006)
bpy.ops.object.mode_set(mode='OBJECT')
foot_vertices={}
for suffix in ('l','r'):
    indices={body.vertex_groups['foot_'+suffix].index,body.vertex_groups['ball_'+suffix].index}
    foot_vertices[suffix]=[vertex.co.copy() for vertex in body.data.vertices if any(group.group in indices for group in vertex.groups)]
body.data.transform(Matrix.Scale(100,4))
rig.data.transform(Matrix.Scale(100,4))
modifier=body.modifiers.new('Admission skeleton','ARMATURE')
modifier.object=rig
body.parent=rig
select_only(body)
for poly in body.data.polygons:
    poly.use_smooth=True
body['document_bone']='document'
body['design']='AdmissionRobot approved concept v02, paper 入学承諾書, options はい / YES'


def ik_joint(a,b,l1,l2,hint):
    delta=b-a
    distance=min(delta.length,l1+l2-.0001)
    direction=delta.normalized()
    offset=(l1*l1-l2*l2+distance*distance)/(2*distance)
    height=math.sqrt(max(0,l1*l1-offset*offset))
    perpendicular=(hint-direction*hint.dot(direction)).normalized()
    return a+direction*offset+perpendicular*height


def set_world(name,head,tail,reference):
    rest=rig.data.bones[name]
    rest_direction=(rest.tail_local-rest.head_local).normalized()
    target_direction=(tail-head).normalized()
    rotation=(reference@rest_direction).rotation_difference(target_direction)@reference@rest.matrix_local.to_quaternion()
    matrix=rotation.to_matrix().to_4x4()
    matrix.translation=head*100
    rig.pose.bones[name].matrix=matrix
    bpy.context.view_layer.update()


def animate_pose(kind,frame,length):
    cycle=2*math.pi*(frame-1)/length
    fall_t=min(1,(frame-1)/42) if kind=='Fall' else 0
    falling=max(0,min(1,(fall_t-.13)/.74))
    falling=falling*falling*(3-2*falling)
    if kind=='Walk':
        dz=-.044+.013*(1-math.cos(2*cycle))
        lean=.035
        yaw=.025*math.sin(cycle)
        roll=.015*math.sin(cycle)
    elif kind=='Run':
        dz=-.074+.037*(1-math.cos(2*cycle))
        lean=.12
        yaw=.038*math.sin(cycle)
        roll=.026*math.sin(cycle)
    elif kind=='Fall':
        dz=-.795*falling-.06*math.sin(math.pi*fall_t)
        lean=.03+.05*math.sin(math.pi*fall_t)
        yaw=-.10*falling
        roll=-1.48*falling
    else:
        dz=.003*math.sin(cycle)
        lean=.008*math.sin(cycle)
        yaw=0
        roll=0
    rotation=Quaternion((0,0,1),yaw)@Quaternion((0,1,0),roll)@Quaternion((1,0,0),lean)
    pelvis=Vector((-.12*falling,0,.97+dz))
    def transform(p):
        result=pelvis+rotation@(Vector(p)-Vector((0,0,.97)))
        if kind=='Fall':
            result.z+=.075*falling*max(0,min(1,(p[2]-.97)/.50))
        return result
    world={}
    world['root']=(Vector((0,0,0)),Vector((0,0,.15)),Quaternion())
    for name in ('pelvis','spine_01','spine_02','spine_03','neck','head','clavicle_l','clavicle_r'):
        world[name]=(transform(bones[name]['head']),transform(bones[name]['tail']),rotation)
    for suffix,sign,phase in [('l',1,cycle),('r',-1,cycle+math.pi)]:
        hip=transform(bones['thigh_'+suffix]['head'])
        if kind in ('Walk','Run'):
            stride=.225 if kind=='Walk' else .30
            lift=.065 if kind=='Walk' else .145
            ankle=Vector((sign*.108,-stride*math.cos(phase),.115+lift*max(0,-math.sin(phase))))
            foot_pitch=.13*math.sin(phase) if kind=='Walk' else .32*math.sin(phase)
            foot_rotation=Quaternion((1,0,0),foot_pitch)
            foot_min=min((ankle+foot_rotation@(vertex-bones['foot_'+suffix]['head'])).z for vertex in foot_vertices[suffix])
            ankle.z+=.005+lift*max(0,-math.sin(phase))-foot_min
            toe=ankle+foot_rotation@(bones['foot_'+suffix]['tail']-bones['foot_'+suffix]['head'])
            ball_end=toe+foot_rotation@(bones['ball_'+suffix]['tail']-bones['ball_'+suffix]['head'])
            knee=ik_joint(hip,ankle,(bones['thigh_'+suffix]['tail']-bones['thigh_'+suffix]['head']).length,(bones['calf_'+suffix]['tail']-bones['calf_'+suffix]['head']).length,Vector((0,-1,0)))
        else:
            ankle_local=bones['foot_'+suffix]['head'].copy()
            if kind=='Fall':
                ankle_local.y-= (.18 if sign==1 else -.09)*falling
                ankle_local.z+= (.12 if sign==1 else .04)*falling
            ankle=transform(ankle_local)
            if kind=='Fall':
                final_ankle=Vector((.57,-.12,.16)) if sign==1 else Vector((.63,.03,.10))
                final_min=min((final_ankle+rotation@(vertex-bones['foot_'+suffix]['head'])).z for vertex in foot_vertices[suffix])
                final_ankle.z+=(.085 if sign==1 else .005)-final_min
                ankle=ankle.lerp(final_ankle,falling)
            knee=ik_joint(hip,ankle,(bones['thigh_'+suffix]['tail']-bones['thigh_'+suffix]['head']).length,(bones['calf_'+suffix]['tail']-bones['calf_'+suffix]['head']).length,rotation@Vector((0,-1,0)))
            toe=ankle+rotation@(bones['foot_'+suffix]['tail']-bones['foot_'+suffix]['head'])
            ball_end=toe+rotation@(bones['ball_'+suffix]['tail']-bones['ball_'+suffix]['head'])
            foot_rotation=rotation
        world['thigh_'+suffix]=(hip,knee,rotation)
        world['calf_'+suffix]=(knee,ankle,rotation)
        world['foot_'+suffix]=(ankle,toe,foot_rotation)
        world['ball_'+suffix]=(toe,ball_end,foot_rotation)
        shoulder=transform(bones['upperarm_'+suffix]['head'])
        if sign==1:
            wrist_local=bones['hand_l']['head'].copy()
            if kind=='Run':
                wrist_local+=Vector((-.07,.08,.085))
            elif kind=='Walk':
                wrist_local+=Vector((0,-.008*math.sin(cycle),.01*math.sin(2*cycle)))
            elif kind=='Fall':
                wrist_local+=Vector((.11,-.04,.06))*falling
            wrist=transform(wrist_local)
            hand_tail=wrist+rotation@(bones['hand_l']['tail']-bones['hand_l']['head'])
            elbow=ik_joint(shoulder,wrist,(bones['upperarm_l']['tail']-bones['upperarm_l']['head']).length,(bones['lowerarm_l']['tail']-bones['lowerarm_l']['head']).length,rotation@Vector((.6,.3,-1)))
        else:
            wrist_local=bones['hand_r']['head'].copy()
            if kind=='Walk':
                wrist_local+=Vector((-.005,-.19*math.cos(cycle),.035*(1-math.cos(cycle))))
            elif kind=='Run':
                wrist_local=Vector((-.34,-.13-.19*math.cos(cycle),1.17+.06*math.sin(cycle)))
            wrist=transform(wrist_local)
            if kind=='Fall':
                wrist=wrist.lerp(Vector((-.40,-.26,.25)),falling)
            elbow_hint=rotation@Vector((-.5,.35,-.7))
            if kind=='Fall':
                elbow_hint=elbow_hint.lerp(Vector((0,0,1)),falling)
            elbow=ik_joint(shoulder,wrist,(bones['upperarm_r']['tail']-bones['upperarm_r']['head']).length,(bones['lowerarm_r']['tail']-bones['lowerarm_r']['head']).length,elbow_hint)
            hand_tail=wrist+(wrist-elbow).normalized()*(bones['hand_r']['tail']-bones['hand_r']['head']).length
        world['upperarm_'+suffix]=(shoulder,elbow,rotation)
        world['lowerarm_'+suffix]=(elbow,wrist,rotation)
        world['hand_'+suffix]=(wrist,hand_tail,rotation)
    for name in bones:
        if name=='document':
            rig.pose.bones[name].matrix_basis=Matrix.Identity(4)
        else:
            set_world(name,*world[name])
    if kind=='Fall':
        depsgraph=bpy.context.evaluated_depsgraph_get()
        evaluated=body.evaluated_get(depsgraph)
        lowest=min((evaluated.matrix_world@vertex.co).z for vertex in evaluated.data.vertices)
        if lowest<.5:
            root_matrix=rig.pose.bones['root'].matrix.copy()
            root_matrix.translation.z+=.5-lowest
            rig.pose.bones['root'].matrix=root_matrix
            bpy.context.view_layer.update()


actions={}
specs={'Idle':60,'Walk':30,'Run':20,'Fall':48}
rig.animation_data_create()
for kind,length in specs.items():
    action=bpy.data.actions.new('AN_Admission_'+kind)
    action.use_fake_user=True
    rig.animation_data.action=action
    for frame in range(1,length+2):
        scene.frame_set(frame)
        animate_pose(kind,frame,length)
        for pose in rig.pose.bones:
            pose.keyframe_insert(data_path='location',frame=frame,group=pose.name)
            pose.keyframe_insert(data_path='rotation_quaternion',frame=frame,group=pose.name)
            pose.keyframe_insert(data_path='scale',frame=frame,group=pose.name)
    actions[kind]=action

rig.animation_data.action=actions['Idle']
scene.frame_start=1
scene.frame_end=61
scene.frame_set(1)


def export_skeletal(path, all_actions):
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    body.select_set(True)
    bpy.context.view_layer.objects.active=rig
    bpy.ops.export_scene.fbx(filepath=str(path),check_existing=False,use_selection=True,object_types={'ARMATURE','MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',use_space_transform=True,bake_space_transform=False,use_mesh_modifiers=True,mesh_smooth_type='FACE',add_leaf_bones=False,primary_bone_axis='Y',secondary_bone_axis='X',use_armature_deform_only=True,armature_nodetype='NULL',bake_anim=True,bake_anim_use_all_bones=True,bake_anim_use_nla_strips=False,bake_anim_use_all_actions=all_actions,bake_anim_force_startend_keying=True,bake_anim_step=1.0,bake_anim_simplify_factor=0.0,path_mode='COPY',embed_textures=True)


export_skeletal(EXPORT/'SK_AdmissionRobot_All.fbx',True)
for kind,length in specs.items():
    rig.animation_data.action=actions[kind]
    scene.frame_start=1
    scene.frame_end=length+1
    scene.frame_set(1)
    export_skeletal(EXPORT/('SK_AdmissionRobot_'+kind+'.fbx'),False)

# Render-only studio is outside the selected FBX objects.
ground=material('Studio Ground',(.105,.115,.124),0,.80)
bpy.ops.mesh.primitive_plane_add(size=20000,location=(0,0,-.6))
bpy.context.object.name='Preview ground'
bpy.context.object.data.materials.append(ground)
worldmat=scene.world
worldmat.use_nodes=True
worldmat.node_tree.nodes['Background'].inputs[0].default_value=(.14,.16,.18,1)
worldmat.node_tree.nodes['Background'].inputs[1].default_value=.40


def area(name,location,power,color,size,target=(0,0,1)):
    data=bpy.data.lights.new(name,'AREA')
    data.energy=power*10000
    data.color=color
    data.shape='DISK'
    data.size=size*100
    obj=bpy.data.objects.new(name,data)
    scene.collection.objects.link(obj)
    obj.location=Vector(location)*100
    obj.rotation_euler=(Vector(target)*100-obj.location).to_track_quat('-Z','Y').to_euler()


area('Key softbox',(2,-3,4),450,(.91,.95,1),3)
area('Warm fill',(-3,-1.5,2.2),230,(1,.91,.80),2.6)
area('Rim strip',(1,2,3),550,(.65,.85,1),2)
bpy.ops.object.camera_add(location=(290,-540,235))
camera=bpy.context.object
camera.name='Preview Camera'
camera.rotation_euler=(Vector((0,-5,100))-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO'
camera.data.ortho_scale=225
camera.data.clip_end=100000
scene.camera=camera
scene.render.engine='CYCLES'
scene.cycles.device='CPU'
scene.cycles.samples=32
scene.cycles.use_denoising=True
scene.render.resolution_x=1100
scene.render.resolution_y=1100
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.view_settings.view_transform='AgX'
rig.animation_data.action=actions['Idle']
scene.frame_start=1
scene.frame_end=61
scene.frame_set(1)
paper_image.pack()
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'AdmissionRobot_v01.blend'))
report={
    'model':'SK_AdmissionRobot',
    'rig':'AdmissionRig',
    'skeleton':'SKEL_AdmissionRobot',
    'height_m':1.89,
    'blender_forward':'-Y',
    'up':'Z',
    'unit_m':.01,
    'geometry_units':'centimeters, actual vertex/rest-bone/keyframe translations; object scales 1',
    'fbx_apply_scale_options':'FBX_SCALE_UNITS',
    'bones':list(bones),
    'vertices':len(body.data.vertices),
    'polygons':len(body.data.polygons),
    'triangles':sum(len(poly.vertices)-2 for poly in body.data.polygons),
    'materials':[m.name for m in body.data.materials],
    'document_bone':'document',
    'document_parent':'hand_l',
    'document_text':'入学承諾書',
    'document_choices':['はい','YES'],
    'actions':{k:{'name':v.name,'fps':30,'frames':[1,specs[k]+1],'duration_seconds':specs[k]/30,'loop':k!='Fall','speed_cm_s':90 if k=='Walk' else 180 if k=='Run' else 0} for k,v in actions.items()},
    'skinning':'Rigid segmented plates weighted to deformation bones; clipboard is independent rigid geometry weighted to document bone.',
    'ue_note':'Import SK_AdmissionRobot_All.fbx with animations, convert scene and units. Verify character is approximately 189 cm tall. Locomotion clips are in-place. Fall finishes in side-lying pose and must not loop.'
}
(ROOT/'build_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
for kind,frame in [('Idle',1),('Walk',8),('Run',7),('Fall',44)]:
    rig.animation_data.action=actions[kind]
    scene.frame_set(frame)
    if kind=='Fall':
        camera.data.ortho_scale=235
        camera.location=(290,-540,230)
        camera.rotation_euler=(Vector((-10,0,45))-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(PREVIEW/('AdmissionRobot_'+kind+'.png'))
    bpy.ops.render.render(write_still=True)
print('ADMISSION_ROBOT_BUILD_COMPLETE '+str(ROOT))
