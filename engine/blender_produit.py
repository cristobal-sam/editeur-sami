"""Studio produit local. Photo = carte 3D ; GLB = vrai modèle ; aucun produit inventé."""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

config = json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8'))
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x, scene.render.resolution_y = config['width'], config['height']
scene.render.resolution_percentage = 100
scene.render.fps = 30
scene.frame_start, scene.frame_end = 1, config['frames']
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = config['framesDir'] + '/f_'
scene.world = bpy.data.worlds.new('Studio')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.008,.009,.014,1)

def material(name, color, metallic=0, rough=.28):
    mat = bpy.data.materials.new(name)
    mat.use_nodes=True
    node=mat.node_tree.nodes['Principled BSDF']
    node.inputs['Base Color'].default_value=color
    node.inputs['Metallic'].default_value=metallic
    node.inputs['Roughness'].default_value=rough
    return mat

bpy.ops.object.empty_add()
root=bpy.context.object
root.name='Produit'
if config.get('model'):
    bpy.ops.import_scene.gltf(filepath=config['model'])
    objects=[o for o in scene.objects if o.type=='MESH']
    if not objects:
        raise ValueError('Le GLB ne contient aucun objet visible.')
    pts=[o.matrix_world@Vector(p) for o in objects for p in o.bound_box]
    low=Vector(tuple(min(p[k] for p in pts) for k in range(3)))
    high=Vector(tuple(max(p[k] for p in pts) for k in range(3)))
    center=(low+high)/2
    scale=3.3/max(high-low)
    for o in [o for o in scene.objects if o!=root and not o.parent]:
        o.parent=root
    root.scale=(scale,)*3
    root.location=-center*scale
    container=bpy.data.objects.new('Tourne',None)
    scene.collection.objects.link(container)
    root.parent=container
    root=container
else:
    bpy.ops.mesh.primitive_cube_add(size=1)
    card=bpy.context.object
    card.dimensions=(2,.13,3.4)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    card.parent=root
    card.data.materials.append(material('Carte',(.025,.032,.055,1),.6))
    bevel=card.modifiers.new('Bords arrondis','BEVEL');bevel.width=.11;bevel.segments=6
    card.modifiers.new('Normales','WEIGHTED_NORMAL')
    if config.get('image'):
        bpy.ops.mesh.primitive_plane_add(size=2,location=(0,-.071,0),rotation=(math.pi/2,0,0))
        photo=bpy.context.object;photo.parent=root;photo.scale=(.93,1.55,1)
        mat=material('Photo',(1,1,1,1),0,.35)
        texture=mat.node_tree.nodes.new('ShaderNodeTexImage')
        texture.image=bpy.data.images.load(config['image'])
        mat.node_tree.links.new(texture.outputs['Color'],mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
        photo.data.materials.append(mat)
    else:
        for text,z,size in [('RYUCALLS',.25,.24),('CARTE DÉMO',-.18,.12)]:
            bpy.ops.object.text_add(location=(-.83,-.075,z),rotation=(math.pi/2,0,0))
            obj=bpy.context.object;obj.parent=root;obj.data.body=text;obj.data.size=size;obj.data.extrude=.003
            obj.data.font=bpy.data.fonts.load(config['font'])
            obj.data.materials.append(material('Lettrage',(.76,.84,1,1),.3))

root.location.z+=.8
for frame,angle in [(1,-.30),(config['frames']//2,.30),(config['frames'],math.pi*1.8)]:
    root.rotation_euler.z=angle
    root.keyframe_insert('rotation_euler',frame=frame)
for curve in root.animation_data.action.fcurves if hasattr(root.animation_data.action,'fcurves') else []:
    for key in curve.keyframe_points:key.interpolation='LINEAR'
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-1))
floor=bpy.context.object;floor.data.materials.append(material('Sol noir',(.013,.015,.023,1),.85,.16))
for pos,power,color,size in [((3,-4,5),900,(.8,.9,1),5),((-3,-1,2),600,(1,.7,.45),3),((0,3,3),1100,(.5,.65,1),3)]:
    bpy.ops.object.light_add(type='AREA',location=pos)
    light=bpy.context.object;light.data.energy=power;light.data.color=color;light.data.size=size
    light.rotation_euler=(Vector((0,0,.5))-light.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(0,-9,2))
cam=bpy.context.object;cam.data.lens=48
cam.rotation_euler=(Vector((0,0,.5))-cam.location).to_track_quat('-Z','Y').to_euler()
scene.camera=cam
bpy.ops.render.render(animation=True)
