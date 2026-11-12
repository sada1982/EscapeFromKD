import bpy
import bmesh
from mathutils import Vector
from build_floor03 import surface_uv


def _bounds(obj):
    points=[obj.matrix_world@Vector(v) for v in obj.bound_box]
    return ([min(p[i] for p in points) for i in range(3)],
            [max(p[i] for p in points) for i in range(3)])


def _touches(a,b):
    low_a,high_a=_bounds(a)
    low_b,high_b=_bounds(b)
    return all(min(high_a[i],high_b[i])-max(low_a[i],low_b[i])>=-0.00001 for i in range(3))


def _boolean(target,other,operation):
    bpy.context.view_layer.objects.active=target
    modifier=target.modifiers.new('Resolve architectural junction','BOOLEAN')
    modifier.operation=operation
    modifier.solver='EXACT'
    modifier.object=other
    bpy.ops.object.modifier_apply(modifier=modifier.name)
    bpy.context.view_layer.update()
    if not target.data.polygons:
        raise RuntimeError('Empty junction mesh: '+target.name)


def _merge_contacts(objects):
    remaining=list(objects)
    while remaining:
        base=remaining.pop(0)
        pending=True
        while pending:
            pending=False
            for other in list(remaining):
                if not _touches(base,other): continue
                _boolean(base,other,'UNION')
                remaining.remove(other)
                bpy.data.objects.remove(other,do_unlink=True)
                pending=True


def _remove_degenerate_faces(obj,joined=False):
    obj.data.calc_loop_triangles()
    if not joined and not any(t.area<1e-10 or min((obj.data.vertices[a].co-obj.data.vertices[b].co).length
               for a,b in zip(t.vertices,t.vertices[1:]+t.vertices[:1]))<0.00001
               for t in obj.data.loop_triangles): return
    bm=bmesh.new()
    bm.from_mesh(obj.data)
    # Weld only sub-0.01 mm cut fragments before FBX float conversion can collapse them.
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=0.00001)
    bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=0.00001)
    if joined:
        bmesh.ops.dissolve_limit(bm,angle_limit=0.0001,verts=list(bm.verts),edges=list(bm.edges),delimit={'MATERIAL'})
    if obj.name.startswith(('Opposite_gallery_back','Opposite_gallery_return')):
        # Align wall edge vertices with the floor cut to avoid needle-shaped triangles.
        for height in (-0.18,0):
            bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=0.000001,
                                  plane_co=obj.matrix_world.inverted()@Vector((0,0,height)),
                                  plane_no=obj.matrix_world.to_3x3().transposed()@Vector((0,0,1)))
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.calc_area()<1e-10],context='FACES')
    if joined:
        bm.normal_update()
        edges=[e for e in bm.edges if len(e.link_faces)==2
               and e.link_faces[0].material_index==e.link_faces[1].material_index
               and e.link_faces[0].normal.dot(e.link_faces[1].normal)>0.999999]
        bmesh.ops.beautify_fill(bm,faces=list(bm.faces),edges=edges)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    if joined: surface_uv(obj,obj.data.materials[0])


def repair_junctions():
    # Union only the audited solid trim families; this preserves their outside shape.
    corridors=bpy.data.collections['Survey_Corridors']
    def parts(collection,prefixes):
        return sorted([o for o in collection.objects if o.type=='MESH' and o.name.startswith(prefixes)],key=lambda o:o.name)
    _merge_contacts(parts(corridors,('Atrium_pier','Atrium_end_pier')))
    _merge_contacts(parts(corridors,('Atrium_cap','Glassblock_pier')))
    _merge_contacts(parts(corridors,('Atrium_header',)))
    _merge_contacts(parts(corridors,('Black_skirt',)))
    _merge_contacts(parts(bpy.data.collections['Survey_Structure'],('Black_skirt',)))
    fixtures=bpy.data.collections['Survey_ClassroomFixtures']
    for prefix in ('GameLab_whiteboard_frame','AdjacentLab_whiteboard_frame'):
        _merge_contacts(parts(fixtures,(prefix,)))
    _merge_contacts(parts(bpy.data.collections['Survey_Ceilings'],('AC_dark_vent',)))

    # The mortar grid contains intersecting boxes inside a single mesh.
    for grid in parts(corridors,('Glassblock_mortar',)):
        bpy.ops.object.select_all(action='DESELECT')
        grid.select_set(True)
        bpy.context.view_layer.objects.active=grid
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.separate(type='LOOSE')
        bpy.ops.object.mode_set(mode='OBJECT')
        pieces=[o for o in bpy.context.selected_objects if o!=grid]
        for other in pieces:
            _boolean(grid,other,'UNION')
            bpy.data.objects.remove(other,do_unlink=True)

    # Floor slabs own their exposed edges; cut the intersecting header/wall volume away.
    slabs=parts(corridors,('3F_gallery_floor','Opposite_gallery_floor',
                          'Near_gallery_context_floor','Front_gallery_context_floor'))
    for wall in parts(corridors,('Atrium_header','Opposite_gallery_return','Opposite_gallery_back')):
        for slab in slabs:
            if _touches(wall,slab): _boolean(wall,slab,'DIFFERENCE')
    # Exact coplanar cuts can leave zero-area triangulation fragments at shared edges.
    for obj in corridors.objects:
        if obj.type=='MESH':
            _remove_degenerate_faces(obj,obj.name.startswith(('Atrium_cap','Atrium_header','Glassblock_mortar','Opposite_gallery_back','Opposite_gallery_return')))
