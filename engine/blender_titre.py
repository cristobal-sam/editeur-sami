"""Titre d'ouverture 3D rendu par Blender (fond transparent), superpose au debut du reel.
blender --background --factory-startup --python blender_titre.py -- <texte> <police.ttf> <#couleur> <dossier_images> <largeur> <hauteur> <images>"""
import math
import sys

import bpy

args = sys.argv[sys.argv.index('--') + 1:]
text, font, color, out_dir = args[0], args[1], args[2], args[3]
width, height, frames = int(args[4]), int(args[5]), int(args[6])
fps = 30

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE'
scene.render.resolution_x, scene.render.resolution_y = width, height
scene.render.fps = fps
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.frame_start, scene.frame_end = 1, frames
scene.render.filepath = out_dir.rstrip('/\\') + '/f_'

# Texte en relief, centre, coupe en lignes
bpy.ops.object.text_add(location=(0, 0, 0))
obj = bpy.context.object
obj.data.body = text.upper()
obj.data.font = bpy.data.fonts.load(font)
obj.data.align_x = 'CENTER'
obj.data.align_y = 'CENTER'
obj.data.size = 0.5
obj.data.extrude = 0.09
obj.data.bevel_depth = 0.012
obj.data.space_line = 0.95
box = obj.data.text_boxes[0]
box.width, box.height = 3.0, 0
box.x, box.y = -1.5, 0
obj.data.overflow = 'NONE'

r, g, b = (int(color.lstrip('#')[i:i + 2], 16) / 255 for i in (0, 2, 4))
mat = bpy.data.materials.new('Titre')
mat.use_nodes = True
bsdf = mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (r, g, b, 1)
bsdf.inputs['Metallic'].default_value = 0.55
bsdf.inputs['Roughness'].default_value = 0.25
obj.data.materials.append(mat)    # relief entier dans la couleur du style
obj.data.bevel_resolution = 2

# Lumiere et camera
bpy.ops.object.light_add(type='AREA', location=(2.5, -4, 5))
bpy.context.object.data.energy = 900
bpy.context.object.data.size = 6
bpy.ops.object.light_add(type='AREA', location=(-3, -2, -1))
bpy.context.object.data.energy = 250
bpy.ops.object.camera_add(location=(0, -9.5, 0), rotation=(math.radians(90), 0, 0))
cam = bpy.context.object
cam.data.lens = 50
scene.camera = cam
world = bpy.data.worlds.new('Monde')
world.color = (0.02, 0.02, 0.02)
scene.world = world

# Animation : bascule + zoom a l'entree, tenue, sortie vers la camera
enter, leave = int(fps * 0.6), frames - int(fps * 0.35)
for f, rot, s, y in ((1, 88, 0.55, 0), (enter, 0, 1.0, 0), (leave, -3, 1.04, 0), (frames, -8, 1.25, -2.5)):
    obj.rotation_euler = (math.radians(90 + rot), 0, 0)
    obj.scale = (s, s, s)
    obj.location = (0, y, 0)
    obj.keyframe_insert('rotation_euler', frame=f)
    obj.keyframe_insert('scale', frame=f)
    obj.keyframe_insert('location', frame=f)
cam.location = (0, -9.8, 0)
cam.keyframe_insert('location', frame=1)
cam.location = (0, -9.0, 0)
cam.keyframe_insert('location', frame=frames)

bpy.ops.render.render(animation=True)
