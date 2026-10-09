"""Changements de style par la vraie CLI, sur copies ; aucun projet original modifie."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0,str(ROOT/'engine'))
os.environ['EDITEUR_LLM']='0'
from editeur import reel,galerie,auto,montage,sobriete
BOX=Path(tempfile.mkdtemp(prefix='fable2-styles-',dir=ROOT/'runtime/cache/tmp'))
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,r):Path(p).write_text(json.dumps(r,ensure_ascii=False),encoding='utf-8')

class Moteur(unittest.TestCase):
    def setUp(self):
        self.r=load(ROOT/'projects/script1/reels/script.json')
        self.p=BOX/self._testMethodName
        (self.p/'reels').mkdir(parents=True,exist_ok=True)
        self.project=load(ROOT/'projects/script1/project.json')
        save(self.p/'project.json',self.project)
    def test_cli_quatre_styles_deux_videos(self):
        for name in ('script1','video1video1'):
            base=load(ROOT/'projects'/name/'reels/script.json')
            # Simule l'etat apres Refaire : les anciens elements non marques ne sont PAS effaces au changement de style.
            sobriete.relire(base,tout=True)
            base['title']='Titre retouche'
            base.setdefault('design',{})['title']='Titre documentaire retouche'
            base['graphics'].append({'id':'manuel','kind':'carte','at':10,'duration':1,
                                     'props':{'title':'Note manuelle'}})
            manual=copy.deepcopy(base['graphics'][-1])
            save(self.p/'project.json',load(ROOT/'projects'/name/'project.json'))
            for style in ('reel-karaoke','hormozi','editorial-cinetique','infographie'):
                with self.subTest(video=name,style=style):
                    save(self.p/'reels/script.json',base)
                    result=subprocess.run([sys.executable,'-m','editeur','reel',str(self.p),'--style',style],
                                          cwd=ROOT/'engine',capture_output=True,encoding='utf-8',timeout=600)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                    r=load(self.p/'reels/script.json')
                    self.assertEqual(r['template'],style)
                    self.assertEqual(r['title'],base['title'])
                    self.assertEqual(r['design']['title'],base['design']['title'])
                    self.assertEqual(next(g for g in r['graphics'] if g['id']=='manuel'),manual)
                    self.assertTrue(r['sobriete']['resume'])
                    seg=montage.compute(r); rep=sobriete.reperes(r,seg)
                    els=sorted(sobriete._elements(r,seg),key=lambda e:e['at'])
                    compact=[(e['type'],e['texte'],e['at'],e['fin']) for e in els]
                    self.assertFalse([e for e in els if e['at']<rep['accroche']],compact)
                    self.assertTrue(all(b['at']>=a['fin'] for a,b in zip(els,els[1:])),compact)
                    self.assertEqual(galerie._hook_end(r,galerie._times(r)),rep['accroche'])
                    print(name,style,r['sobriete']['resume'],flush=True)
    def test_emoji_manuel_conserve_en_hormozi(self):
        self.r['clips'][0]['emojis']=[[1,'🔥']]
        reel.apply_template(self.r,'hormozi')
        self.assertEqual(self.r['clips'][0]['emojis'],[[1,'🔥']])
    def test_emojis_masques_ne_reapparaissent_pas_apres_montage_auto(self):
        self.r['emoji']={'enabled':False}
        self.r['clips'][0]['emojis']=[[1,'🔥']]
        sobriete.relire(self.r,tout=True)
        self.assertEqual(self.r['clips'][0]['emojis'],[])
        self.assertIn([1,'🔥'],self.r['suggestions']['emojis'][self.r['clips'][0]['id']])
        reel.apply_template(self.r,'hormozi')
        self.assertEqual(self.r['clips'][0]['emojis'],[])
    def test_scene_retouchee_conservee_au_changement_de_style(self):
        scene={'id':'scene-retouchee','kind':'metric','clip':self.r['clips'][0]['id'],
               'index':8,'text':'Mon texte','duration':2,'edited':True,'hidden':True}
        self.r['styleScenes']=[copy.deepcopy(scene)]
        for style in ('infographie','reel-karaoke','hormozi'):
            reel.apply_template(self.r,style)
            self.assertEqual(next(s for s in self.r['styleScenes'] if s['id']==scene['id']),scene)
    def test_refresh_et_reconstruction_gardent_broll_et_titre(self):
        self.r['suggestions']={'banners':[],'words':{},'emojis':{},'broll':[{'word':'test','at':12}]}
        self.r['title']='Mon titre a garder'
        save(self.p/'reels/script.json',self.r)
        with patch.object(reel,'_editorial',return_value=None):
            self.assertEqual(reel.refresh_ai(self.p)['broll'],self.r['suggestions']['broll'])
            with patch.object(reel,'_sources',return_value=self.r['sources']):
                reel.ensure(self.p,ai_mode='suggestion')
        r=load(self.p/'reels/script.json')
        self.assertEqual(r['suggestions']['broll'],self.r['suggestions']['broll'])
        self.assertEqual(r['title'],self.r['title'])
    def test_montage_visuel_ne_reconstruit_rien(self):
        for kind in ('immobilier','evenement'):
            r=copy.deepcopy(self.r)
            r['kind']=kind
            r['banner']={'text':'12 RUE DES ÉRABLES','enabled':True,'start':.3,'end':4}
            r['audio']={'voice':'aucun'}
            save(self.p/'reels/script.json',r)
            with patch.object(reel,'ensure',side_effect=AssertionError('Ne pas reconstruire')), \
                 patch.object(auto,'_banner_correct',side_effect=AssertionError('Ne pas relire une adresse')):
                auto._finish(self.p,kind,{'type':kind},banks=False)
            after=load(self.p/'reels/script.json')
            for k in ('kind','banner','audio','clips','music'):
                self.assertEqual(after[k],r[k],k)
    def test_bandeau_masque_relu(self):
        r=self.r
        r['banner']={'text':'VOTRE CONCURRENT CLOSE VOS LEADS','enabled':False,'start':0,'end':4}
        r['suggestions']={'banners':[r['banner']['text']]}
        save(self.p/'reels/script.json',r)
        # ensure recoit un ancien montage archive ; ecrit seulement la copie de ce test.
        with patch.object(reel,'ensure',side_effect=lambda *a,**kw:save(self.p/'reels/script.json',r)), \
             patch.object(auto,'_banner_correct',return_value=None) as correct, \
             patch('editeur.graphismes.suggest',return_value=[]):
            auto._finish(self.p,'podcast-clip',{'type':'pub'},banks=False)
        correct.assert_called_once_with(r['banner']['text'])
        self.assertEqual(load(self.p/'reels/script.json')['banner']['text'],'')

if __name__=='__main__':
    print('COPIES='+str(BOX),flush=True)
    unittest.main(verbosity=2)
