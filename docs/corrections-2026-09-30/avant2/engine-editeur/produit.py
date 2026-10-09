"""Blender : une photo devient une carte 3D ; un GLB garde sa géométrie réelle."""
import hashlib
import json
from pathlib import Path

from . import montage
from .intro import blender
from .media import ROOT, FFMPEG, run


def render(image=None, model=None, width=720, height=1280, frames=90):
    exe=blender()
    if not exe:
        raise ValueError('Blender est introuvable.')
    def asset(value):
        if not value:return None
        p=(ROOT/value).resolve()
        if not p.is_relative_to((ROOT/'assets').resolve()) or not p.is_file():
            raise ValueError('Choisis un fichier produit dans les ressources de l’outil.')
        return str(p)
    config={'image':asset(image),'model':asset(model),'width':width,'height':height,'frames':frames,
            'font':str(ROOT/'assets/fonts/Montserrat.ttf')}
    if config['model'] and Path(config['model']).suffix.lower()!='.glb':
        raise ValueError('Modèle GLB attendu (textures incluses).')
    key=hashlib.sha1(json.dumps(config,sort_keys=True).encode()).hexdigest()[:16]
    folder=ROOT/'runtime/cache/produits'/key
    folder.mkdir(parents=True,exist_ok=True)
    out=ROOT/'assets/produits'/f'{key}.mp4'
    out.parent.mkdir(parents=True,exist_ok=True)
    if not out.exists():
        config['framesDir']=str(folder)
        job=folder/'blender.json';job.write_text(json.dumps(config),encoding='utf-8')
        run([str(exe),'--background','--factory-startup','--disable-autoexec','--python',str(ROOT/'engine/blender_produit.py'),'--',str(job)])
        run([FFMPEG,'-v','error','-y','-framerate','30','-i',str(folder/'f_%04d.png'),'-c:v','libx264','-pix_fmt','yuv420p','-crf','19',str(out)])
    return out.relative_to(ROOT).as_posix()


def make(project_dir,rid):
    reel=montage.load(project_dir,rid)
    design=reel.get('design') or {}
    if design.get('mode')!='produit':raise ValueError('Choisis le style Produit 3D.')
    file=render(design.get('productImage'),design.get('productModel'))
    def apply(r):
        r['design']['productVideo']=file
        if not r.get('styleScenes') and r.get('clips') and r['clips'][0]['words']:
            c=r['clips'][0]
            r['styleScenes']=[{'id':'produit-manuel','kind':'product','clip':c['id'],'index':0,'text':'','duration':3,
                              'x':.5,'y':.7,'scale':1,'rotation':0,'color':'#BFD3FF'}]
    montage.update(project_dir,rid,apply)
    return {'file':file,'reel':montage.load(project_dir,rid)}
