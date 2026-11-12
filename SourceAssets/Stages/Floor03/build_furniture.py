import math

import bpy
from mathutils import Matrix, Vector


class FurnitureMesh:
    def __init__(self, materials):
        self.materials = materials
        self.material_names = []
        self.vertices = []
        self.faces = []
        self.face_materials = []
        self.face_smoothing = []
        self.face_uvs = []

    def add_faces(self, faces, material, smooth=False, uvs=None):
        if material not in self.material_names:
            self.material_names.append(material)
        material_index = self.material_names.index(material)
        self.faces.extend(faces)
        self.face_materials.extend([material_index] * len(faces))
        self.face_smoothing.extend([smooth] * len(faces))
        if uvs is not None:
            self.face_uvs.extend(uvs)
        else:
            for face in faces:
                if len(face) == 4:
                    self.face_uvs.append(((0, 0), (1, 0), (1, 1), (0, 1)))
                else:
                    self.face_uvs.append(tuple(
                        (0.5 + 0.5 * math.cos(math.tau * index / len(face)),
                         0.5 + 0.5 * math.sin(math.tau * index / len(face)))
                        for index in range(len(face))))

    def box(self, center, size, material, rotation=None):
        offset = len(self.vertices)
        center = Vector(center)
        half = Vector(size) * 0.5
        corners = [
            (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
            (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
        ]
        for corner in corners:
            vertex = Vector((corner[0] * half.x, corner[1] * half.y,
                             corner[2] * half.z))
            if rotation is not None:
                vertex = rotation @ vertex
            self.vertices.append(tuple(center + vertex))
        faces = [
            (0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
            (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7),
        ]
        face_uvs = [
            ((0, 0), (0, 1), (1, 1), (1, 0)),
            ((0, 0), (1, 0), (1, 1), (0, 1)),
            ((0, 0), (1, 0), (1, 1), (0, 1)),
            ((0, 0), (1, 0), (1, 1), (0, 1)),
            ((1, 0), (0, 0), (0, 1), (1, 1)),
            ((1, 0), (0, 0), (0, 1), (1, 1)),
        ]
        self.add_faces([tuple(offset + index for index in face)
                        for face in faces], material, uvs=face_uvs)

    def cylinder(self, start, end, radius, material, sides=16):
        offset = len(self.vertices)
        start = Vector(start)
        end = Vector(end)
        axis = (end - start).normalized()
        helper = Vector((0, 0, 1))
        if abs(axis.dot(helper)) > 0.95:
            helper = Vector((0, 1, 0))
        side = axis.cross(helper).normalized()
        up = axis.cross(side).normalized()
        for center in (start, end):
            for index in range(sides):
                angle = math.tau * index / sides
                vertex = center + radius * (side * math.cos(angle)
                                             + up * math.sin(angle))
                self.vertices.append(tuple(vertex))
        faces = []
        for index in range(sides):
            next_index = (index + 1) % sides
            faces.append((offset + index, offset + next_index,
                          offset + sides + next_index, offset + sides + index))
        self.add_faces(faces, material, smooth=True)
        self.add_faces([
            tuple(offset + index for index in reversed(range(sides))),
            tuple(offset + sides + index for index in range(sides)),
        ], material)

    def ellipsoid(self, center, radii, material, segments=20, rings=10):
        offset = len(self.vertices)
        center = Vector(center)
        self.vertices.append(tuple(center + Vector((0, 0, radii[2]))))
        for ring in range(1, rings):
            latitude = math.pi * ring / rings
            for segment in range(segments):
                longitude = math.tau * segment / segments
                self.vertices.append((
                    center.x + radii[0] * math.sin(latitude) * math.cos(longitude),
                    center.y + radii[1] * math.sin(latitude) * math.sin(longitude),
                    center.z + radii[2] * math.cos(latitude),
                ))
        bottom = len(self.vertices)
        self.vertices.append(tuple(center - Vector((0, 0, radii[2]))))
        faces = []
        for segment in range(segments):
            next_segment = (segment + 1) % segments
            faces.append((offset, offset + 1 + segment,
                          offset + 1 + next_segment))
        for ring in range(rings - 2):
            first = offset + 1 + ring * segments
            second = first + segments
            for segment in range(segments):
                next_segment = (segment + 1) % segments
                faces.append((first + segment, second + segment,
                              second + next_segment, first + next_segment))
        last = offset + 1 + (rings - 2) * segments
        for segment in range(segments):
            next_segment = (segment + 1) % segments
            faces.append((last + segment, bottom, last + next_segment))
        self.add_faces(faces, material, smooth=True)

    def finish(self, name, collection, bevel_width):
        mesh = bpy.data.meshes.new(name + "_Mesh")
        mesh.from_pydata(self.vertices, [], self.faces)
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for material_name in self.material_names:
            mesh.materials.append(self.materials[material_name])
        for polygon, material_index, smooth, face_uvs in zip(
                mesh.polygons, self.face_materials, self.face_smoothing,
                self.face_uvs):
            polygon.material_index = material_index
            polygon.use_smooth = smooth
            for loop_index, uv in zip(polygon.loop_indices, face_uvs):
                uv_layer.data[loop_index].uv = uv
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        collection.objects.link(obj)
        if bevel_width:
            bevel = obj.modifiers.new("EdgeSoftness", "BEVEL")
            bevel.width = bevel_width
            bevel.segments = 2
            bevel.limit_method = "ANGLE"
            bevel.angle_limit = math.radians(40)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=bevel.name)
        return obj


def build_prototypes(materials, collection):
    desk = FurnitureMesh(materials)
    desk.box((0, 0, 0.7075), (1.8, 0.6, 0.025), "wood")
    desk.box((0, 0, 0.691), (1.77, 0.575, 0.008), "black")
    desk.box((0, 0.19, 0.625), (1.45, 0.035, 0.045), "metal")
    for x in (-0.70, 0.70):
        desk.cylinder((x, 0, 0.045), (x, 0, 0.687), 0.026, "metal")
        desk.box((x, 0, 0.028), (0.058, 0.50, 0.043), "metal")
        desk.box((x, 0, 0.675), (0.055, 0.48, 0.025), "metal")
        for y in (-0.22, 0.22):
            desk.box((x, y, 0.006), (0.065, 0.075, 0.012), "rubber")
    desk_obj = desk.finish("Desk_Prototype", collection, 0.004)

    chair = FurnitureMesh(materials)
    chair.ellipsoid((0, 0, 0.415), (0.225, 0.215, 0.025), "black")
    chair.ellipsoid((0, -0.005, 0.391), (0.205, 0.195, 0.017), "rubber")
    chair.ellipsoid((0, -0.185, 0.705), (0.215, 0.044, 0.145), "black")
    chair.cylinder((0, -0.105, 0.365), (0, -0.235, 0.575), 0.024, "black")
    chair.cylinder((0, -0.235, 0.575), (0, -0.230, 0.735), 0.022, "black")
    chair.cylinder((0, -0.245, 0.590), (0, -0.270, 0.590), 0.034, "rubber")
    chair.box((0, -0.015, 0.365), (0.16, 0.16, 0.035), "black")
    chair.cylinder((0, 0, 0.075), (0, 0, 0.365), 0.025, "metal")
    for ring in range(10):
        z = 0.185 + ring * 0.015
        chair.cylinder((0, 0, z), (0, 0, z + 0.009), 0.036, "rubber")
    chair.cylinder((0.07, -0.06, 0.365), (0.19, -0.06, 0.365), 0.006, "metal")
    chair.box((0.19, -0.06, 0.365), (0.055, 0.028, 0.018), "black")
    for leg in range(5):
        angle = math.tau * leg / 5 + math.pi * 0.5
        direction = Vector((math.cos(angle), math.sin(angle), 0))
        tangent = Vector((-direction.y, direction.x, 0))
        outer = direction * 0.195
        chair.cylinder((0, 0, 0.100), (outer.x, outer.y, 0.058), 0.016, "black")
        chair.cylinder((outer.x, outer.y, 0.027),
                       (outer.x, outer.y, 0.065), 0.009, "metal")
        wheel_center = Vector((outer.x, outer.y, 0.024))
        for side in (-1, 1):
            center = wheel_center + tangent * (side * 0.013)
            chair.cylinder(center - tangent * 0.008, center + tangent * 0.008,
                           0.024, "rubber", sides=12)
    chair_obj = chair.finish("Chair_Prototype", collection, 0.002)

    laptop = FurnitureMesh(materials)
    laptop.box((0, 0, 0.008), (0.34, 0.235, 0.016), "black")
    laptop.box((0, 0.024, 0.0165), (0.295, 0.108, 0.001), "rubber")
    for row in range(5):
        for column in range(12):
            x = -0.132 + column * 0.024
            y = -0.014 + row * 0.019
            laptop.box((x, y, 0.0175), (0.020, 0.015, 0.0015), "keyboard")
    laptop.box((0, -0.027, 0.0175), (0.118, 0.010, 0.0015), "keyboard")
    laptop.box((0, -0.073, 0.0167), (0.105, 0.057, 0.001), "keyboard")
    laptop.cylinder((-0.145, 0.104, 0.020), (0.145, 0.104, 0.020),
                    0.008, "black")
    tilt = math.radians(14)
    screen_rotation = Matrix.Rotation(-tilt, 3, "X")
    hinge = Vector((0, 0.108, 0.023))
    panel_center = hinge + screen_rotation @ Vector((0, 0, 0.105))
    laptop.box(panel_center, (0.34, 0.012, 0.21), "black", screen_rotation)
    display_center = panel_center + screen_rotation @ Vector((0, -0.0063, 0.002))
    laptop.box(display_center, (0.305, 0.001, 0.174), "screen", screen_rotation)
    camera_center = panel_center + screen_rotation @ Vector((0, -0.0067, 0.096))
    laptop.ellipsoid(camera_center, (0.0015, 0.001, 0.0015), "rubber", 12, 6)
    laptop_obj = laptop.finish("Laptop_Prototype", collection, 0.0015)

    mouse = FurnitureMesh(materials)
    mouse.ellipsoid((0, 0, 0.0175), (0.030, 0.050, 0.0175), "black")
    mouse.box((0, 0.013, 0.0343), (0.0008, 0.038, 0.0008), "rubber")
    mouse.cylinder((-0.004, 0.012, 0.034), (0.004, 0.012, 0.034),
                   0.005, "rubber", sides=12)
    mouse_obj = mouse.finish("Mouse_Prototype", collection, 0)

    return {"desk": desk_obj, "chair": chair_obj,
            "laptop": laptop_obj, "mouse": mouse_obj}
