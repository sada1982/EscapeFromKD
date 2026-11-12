from pathlib import Path

import bpy
import numpy as np


def _noise(seed, size=512):
    values = np.random.default_rng(seed).random((size, size)).astype(np.float32)
    smooth = values.copy()
    for distance in (1, 2, 4, 8):
        smooth = (
            smooth
            + np.roll(smooth, distance, axis=0)
            + np.roll(smooth, -distance, axis=0)
            + np.roll(smooth, distance, axis=1)
            + np.roll(smooth, -distance, axis=1)
        ) / 5.0
    return values, smooth


def _image(texture_dir, name, rgb):
    height, width = rgb.shape[:2]
    pixels = np.ones((height, width, 4), dtype=np.float32)
    pixels[:, :, :3] = np.clip(rgb, 0.0, 1.0)
    image = bpy.data.images.new(name, width=width, height=height, alpha=False)
    image.colorspace_settings.name = "sRGB"
    image.pixels.foreach_set(pixels.ravel())
    image.filepath_raw = str(texture_dir / (name + ".png"))
    image.file_format = "PNG"
    image.save()
    image.pack()
    return image


def _solid(name, color, roughness=0.5, metallic=0.0):
    material = bpy.data.materials.new("KD_F03_" + name)
    material.use_nodes = True
    material.diffuse_color = (*color, 1.0)
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    return material


def _textured(name, image, color, roughness, bump_distance=0.0, uv_scale=1.0):
    material = _solid(name, color, roughness)
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    shader = nodes.get("Principled BSDF")
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    texture.extension = "REPEAT"
    texture.location = (-400, 100)
    links.new(texture.outputs["Color"], shader.inputs["Base Color"])
    if uv_scale != 1.0:
        coordinate = nodes.new("ShaderNodeTexCoord")
        coordinate.location = (-800, 100)
        scale = nodes.new("ShaderNodeVectorMath")
        scale.operation = "SCALE"
        scale.inputs[3].default_value = uv_scale
        scale.location = (-600, 100)
        links.new(coordinate.outputs["UV"], scale.inputs[0])
        links.new(scale.outputs["Vector"], texture.inputs["Vector"])
    if bump_distance:
        bump = nodes.new("ShaderNodeBump")
        bump.location = (-180, -180)
        bump.inputs["Strength"].default_value = 0.3
        bump.inputs["Distance"].default_value = bump_distance
        links.new(texture.outputs["Color"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return material


def create_materials(texture_dir):
    texture_dir = Path(texture_dir)
    texture_dir.mkdir(parents=True, exist_ok=True)
    size = 512
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) / size
    tau = np.pi * 2.0
    fine, smooth = _noise(303)

    warp = 0.55 * np.sin(tau * x) + 0.2 * np.sin(tau * (2.0 * x + y))
    grain = np.sin(tau * (34.0 * y + warp))
    pores = np.power(0.5 + 0.5 * np.sin(tau * (79.0 * y + warp * 1.8)), 10)
    wood_variation = (grain * 0.017 - pores * 0.029 + (fine - 0.5) * 0.025)
    wood_rgb = np.array([0.67, 0.48, 0.27]) + wood_variation[:, :, None]
    wood_rgb += (smooth - 0.5)[:, :, None] * np.array([0.3, 0.24, 0.16])
    wood = _image(texture_dir, "wood_light_oak", wood_rgb)

    fine, smooth = _noise(304)
    weave = 0.008 * (np.sin(tau * 128.0 * x) * np.sin(tau * 128.0 * y))
    carpet_rgb = np.array([0.19, 0.205, 0.205])
    carpet_rgb = carpet_rgb + ((fine - 0.5) * 0.15 + (smooth - 0.5) * 0.45 + weave)[:, :, None]
    carpet = _image(texture_dir, "carpet_grey_blue", carpet_rgb)

    fine, smooth = _noise(305)
    corridor_rgb = np.array([0.33, 0.30, 0.26])
    corridor_rgb = corridor_rgb + ((fine - 0.5) * 0.17 + (smooth - 0.5) * 0.40)[:, :, None]
    corridor = _image(texture_dir, "corridor_warm_grey", corridor_rgb)

    fine, smooth = _noise(306)
    ceiling_rgb = np.broadcast_to(np.array([0.82, 0.81, 0.77]), (size, size, 3)).copy()
    ceiling_rgb -= (fine > 0.966)[:, :, None] * 0.19
    ceiling_rgb += (smooth - 0.5)[:, :, None] * 0.15
    ceiling = _image(texture_dir, "ceiling_acoustic", ceiling_rgb)

    screen_rgb = np.zeros((size, size, 3), dtype=np.float32)
    screen_rgb[:] = (0.015, 0.028, 0.055)
    screen_rgb[0:36, :] = (0.035, 0.07, 0.11)
    screen_rgb[38:477, 0:100] = (0.026, 0.045, 0.074)
    screen_rgb[480:, :] = (0.02, 0.18, 0.27)
    colors = [(0.21, 0.56, 0.70), (0.68, 0.55, 0.29), (0.47, 0.61, 0.39)]
    random = np.random.default_rng(307)
    for row in range(18):
        y0 = 64 + row * 21
        indent = 124 + (row % 4) * 14
        length = int(random.integers(100, 260))
        screen_rgb[y0:y0 + 4, indent:min(490, indent + length)] = colors[row % 3]
        screen_rgb[y0:y0 + 4, 111:117] = (0.10, 0.16, 0.21)
    for row in range(14):
        y0 = 62 + row * 28
        screen_rgb[y0:y0 + 4, 16:79 - (row % 3) * 8] = (0.15, 0.21, 0.26)
    screen = _image(texture_dir, "screen_editor", np.flipud(screen_rgb))

    keyboard_rgb = np.zeros((size, size, 3), dtype=np.float32)
    keyboard_rgb[:] = (0.019, 0.021, 0.027)
    for row in range(6):
        for column in range(15):
            x0 = 8 + column * 33
            y0 = 32 + row * 72
            keyboard_rgb[y0:y0 + 57, x0:x0 + 27] = (0.055, 0.060, 0.070)
            keyboard_rgb[y0 + 8:y0 + 11, x0 + 5:x0 + 11] = (0.27, 0.29, 0.31)
    keyboard_rgb[416:473, 140:340] = (0.060, 0.065, 0.075)
    keyboard = _image(texture_dir, "keyboard_keys", keyboard_rgb)

    poster_blue_rgb = np.zeros((size, size, 3), dtype=np.float32)
    poster_blue_rgb[:] = (0.022, 0.055, 0.12)
    blue_band = np.abs(y - x * 0.65 - 0.12) < 0.07
    poster_blue_rgb[blue_band] = (0.08, 0.44, 0.63)
    blue_ring = np.abs(np.sqrt((x - 0.54) ** 2 + (y - 0.48) ** 2) - 0.26) < 0.013
    poster_blue_rgb[blue_ring] = (0.49, 0.80, 0.87)
    for row in range(4):
        poster_blue_rgb[45 + row * 13:49 + row * 13, 42:360 - row * 30] = (0.66, 0.77, 0.79)
    poster_blue = _image(texture_dir, "poster_blue_abstract", poster_blue_rgb)

    poster_orange_rgb = np.zeros((size, size, 3), dtype=np.float32)
    poster_orange_rgb[:] = (0.17, 0.05, 0.025)
    orange_band = np.abs(x + y * 0.4 - 0.6) < 0.12
    poster_orange_rgb[orange_band] = (0.84, 0.37, 0.07)
    orange_circle = (x - 0.50) ** 2 + (y - 0.55) ** 2 < 0.14 ** 2
    poster_orange_rgb[orange_circle] = (0.97, 0.72, 0.27)
    for row in range(4):
        poster_orange_rgb[45 + row * 13:49 + row * 13, 42:360 - row * 30] = (0.87, 0.75, 0.52)
    poster_orange = _image(texture_dir, "poster_orange_abstract", poster_orange_rgb)

    materials = {
        "wood": _textured("LightOak", wood, (0.67, 0.48, 0.27), 0.47, 0.00035),
        "carpet": _textured("ClassroomCarpet", carpet, (0.19, 0.205, 0.205), 0.94, 0.002, 4.0),
        "corridor": _textured("CorridorCarpet", corridor, (0.33, 0.30, 0.26), 0.91, 0.002, 4.0),
        "wall": _solid("PaintWarmWhite", (0.80, 0.79, 0.73), 0.84),
        "ceiling": _textured("AcousticCeiling", ceiling, (0.82, 0.81, 0.77), 0.93, 0.001, 3.0),
        "metal": _solid("SilverMetal", (0.43, 0.47, 0.48), 0.32, 0.72),
        "black": _solid("BlackPlastic", (0.016, 0.021, 0.025), 0.45),
        "rubber": _solid("DarkRubber", (0.008, 0.011, 0.013), 0.83),
        "glass": _solid("ClearGlass", (0.91, 0.97, 0.98), 0.025),
        "frame": _solid("DarkWindowFrames", (0.018, 0.036, 0.034), 0.36, 0.28),
        "whiteboard": _solid("Whiteboard", (0.90, 0.92, 0.89), 0.27),
        "screen": _textured("LaptopScreen", screen, (0.035, 0.12, 0.22), 0.28),
        "keyboard": _textured("LaptopKeyboard", keyboard, (0.035, 0.04, 0.05), 0.50),
        "poster_blue": _textured("PosterBlue", poster_blue, (0.025, 0.15, 0.29), 0.73),
        "poster_orange": _textured("PosterOrange", poster_orange, (0.45, 0.19, 0.05), 0.73),
        "emission": _solid("LightDiffuser", (0.94, 0.97, 1.0), 0.35),
        "concrete": _solid("Concrete", (0.35, 0.36, 0.35), 0.91),
    }
    glass_shader = materials["glass"].node_tree.nodes.get("Principled BSDF")
    glass_shader.inputs["Transmission Weight"].default_value = 1.0
    glass_shader.inputs["IOR"].default_value = 1.46

    screen_shader = materials["screen"].node_tree.nodes.get("Principled BSDF")
    screen_texture = next(node for node in materials["screen"].node_tree.nodes if node.type == "TEX_IMAGE")
    materials["screen"].node_tree.links.new(screen_texture.outputs["Color"], screen_shader.inputs["Emission Color"])
    screen_shader.inputs["Emission Strength"].default_value = 0.5

    light_shader = materials["emission"].node_tree.nodes.get("Principled BSDF")
    light_shader.inputs["Emission Color"].default_value = (0.94, 0.97, 1.0, 1.0)
    light_shader.inputs["Emission Strength"].default_value = 3.0
    return materials
