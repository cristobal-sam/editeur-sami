"""Prépare les copies d'essai et le sujet commun des aperçus ; ne modifie aucun projet original."""
import copy
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'engine'))
os.environ['EDITEUR_LLM']='0'
from editeur import galerie, detourage, reel, produit
from editeur.media import FFMPEG

folder=ROOT/'docs/galerie-styles'
assets=ROOT/'assets/galerie-styles'
assets.mkdir(parents=True,exist_ok=True)
video=assets/'entrepreneur.mp4'
if not video.exists():
    subprocess.run([str(FFMPEG),'-v','error','-y','-loop','1','-i',str(folder/'source-entrepreneur.png'),
                    '-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t','6','-vf','scale=720:1280',
                    '-r','30','-c:v','libx264','-preset','fast','-pix_fmt','yuv420p','-c:a','aac',str(video)],check=True)
texts='Répondez à vos leads en 5 minutes, pas en 3 heures'.split()
words=[{'w':w,'start':round(i*.48,2),'end':round(i*.48+.42,2),'hl':i in (3,5,6,9,10),'hide':False,'cut':False} for i,w in enumerate(texts)]
preview={'id':'demo','project':'demo','variant':None,'title':'Réponse à vos leads','width':1080,'height':1920,'fps':30,
         'sources':{'presenter':{'proxy':video.relative_to(ROOT).as_posix(),'path':str(video),'name':'Entrepreneur fictif','duration':6,
                                'width':720,'height':1280,'samples':[[0,.5,.28,120,120,120,120]]}},
         'clips':[{'id':'c1','source':'presenter','block':'b1','signature':'demo','in':0,'out':6,'tighten':False,'words':words}],
         'zoom':{'auto':False,'strength':1,'push':0,'overrides':{}},'banner':{'enabled':False,'text':'','start':0,'end':4},
         'flash':{'enabled':False},'progress':{'enabled':False},'graphics':[],'broll':[],'audio':{'voice':'aucun','denoise':False,'roomTone':False}}
original=json.loads((ROOT/'projects/script1/reels/script.json').read_text(encoding='utf-8'))
# Même passage à chiffres pour toutes les identités ; copie d'un extrait réel de cinq secondes.
test=copy.deepcopy(original)
from editeur.graphismes import _number
choice=next((c for c in test['clips'] if any(_number(c['words'],i) for i in range(len(c['words'])))),test['clips'][0])
first=next((w for i,w in enumerate(choice['words']) if _number(choice['words'],i)),None)
if first:
    choice['in']=max(choice['in'],min(first['start']-1,choice['out']-5))
choice['out']=min(choice['out'],choice['in']+5)
choice['words']=[w for w in choice['words'] if choice['in']<=w['start'] and w['end']<=choice['out']]
choice.update(tighten=False,audioLead=0,audioTail=0,angle=None)
test.update(clips=[choice],graphics=[],broll=[],brand=None,title='Vérification galerie (copie)',width=360,height=640)
test['intro']={'enabled':False,'file':None,'duration':0,'text':''}
test['sources']={choice['source']:test['sources'][choice['source']]}
test['audio']={'voice':'naturel','denoise':True,'declip':False,'roomTone':False}
case=folder/'tests'
case.mkdir(exist_ok=True)
demo_product=produit.render(width=360,height=640,frames=90)
for tpl in reel.list_templates():
    if not tpl.get('preview'):continue
    for label,base in [('apercu',preview),('essai',test)]:
        r=copy.deepcopy(base)
        reel.apply_template(r,tpl['id'])
        galerie.sober(r)
        galerie.prepare(r,use_ai=False)
        if r['design']['mode'] in ('editorial','collage'):
            detourage.prepare(r)
        if r['design']['mode']=='produit':
            r['design']['productVideo']=demo_product
            # Démonstration explicitement choisie ; dans l'outil le monteur choisit son propre produit.
            if not r['styleScenes'] and r['clips'][0]['words']:
                r['styleScenes']=[{'id':'demo-produit','kind':'product','clip':r['clips'][0]['id'],'index':0,'text':'RyuCalls','duration':3,
                                  'x':.5,'y':.7,'scale':1,'rotation':0,'color':'#BFD3FF'}]
        (case/f"{tpl['id']}-{label}.json").write_text(json.dumps(r,ensure_ascii=False,indent=1),encoding='utf-8')
        print(label,tpl['id'],len(r['styleScenes']),'scènes',flush=True)
