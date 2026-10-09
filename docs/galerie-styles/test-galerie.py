import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'engine'))
os.environ['EDITEUR_LLM']='0'
from editeur import galerie,reel,graphismes

class GalerieTests(unittest.TestCase):
    def setUp(self):
        self.r=json.loads((ROOT/'docs/galerie-styles/tests/hormozi-apercu.json').read_text(encoding='utf-8'))
    def test_ten_styles_and_resources(self):
        styles=[t for t in reel.list_templates() if t.get('preview')]
        self.assertEqual(len(styles),10)
        for t in styles:
            self.assertTrue((ROOT/'assets'/t['preview']).is_file(),t['id'])
            mood=t['music']['mood']
            if mood:self.assertTrue((ROOT/'assets/music'/f'{mood}.ogg').is_file(),mood)
    def test_style_keeps_takes_text_and_custom_elements(self):
        r=self.r
        r['clips'][0]['words'][0]['hide']=True
        r['clips'][0]['words'][1]['cut']=True
        r['graphics']=[{'id':'manuel','kind':'carte','at':2,'duration':2,'props':{'title':'Mon texte'}}]
        before=copy.deepcopy(r)
        for t in reel.list_templates():
            if not t.get('preview'):continue
            reel.apply_template(r,t['id'])
            for c,old in zip(r['clips'],before['clips']):
                self.assertEqual((c['source'],c['in'],c['out']),(old['source'],old['in'],old['out']))
                self.assertEqual([{k:v for k,v in w.items() if k!='hl'} for w in c['words']],
                                 [{k:v for k,v in w.items() if k!='hl'} for w in old['words']])
            self.assertEqual(r['graphics'],before['graphics'])
            self.assertTrue(r['design']['suppressExtras'])
    def test_comparison_does_not_reverse_claim(self):
        reel.apply_template(self.r,'comparatif')
        s=self.r['styleScenes'][0]
        self.assertEqual(s['text'],'3 heures')
        self.assertEqual(s['secondary'],'5 minutes')
    def test_no_comparison_in_ordinary_negation(self):
        r=self.r
        for w,t in zip(r['clips'][0]['words'],"Ce n'est pas mieux de rester comme avant sans rien changer".split()):w['w']=t
        reel.apply_template(r,'comparatif')
        self.assertFalse(r['styleScenes'])
    def test_numbers_require_units_or_magnitude(self):
        for words,expected in [('un employé',None),('une heure',(1.0,'',' h',2)),('cinq pour demain',None),('cinq pour cent',(5.0,'',' %',3))]:
            self.assertEqual(graphismes._number([{'w':s} for s in words.split()],0),expected)
    def test_existing_reel_style_does_not_rebuild(self):
        box=Path(tempfile.mkdtemp(prefix='galerie-test-',dir=ROOT/'runtime/cache/tmp'))
        (box/'reels').mkdir()
        (box/'project.json').write_text('{}',encoding='utf-8')
        (box/'reels/script.json').write_text(json.dumps(self.r),encoding='utf-8')
        result=reel.ensure(box,template='luxe-minimal')
        loaded=json.loads(result.read_text(encoding='utf-8'))
        self.assertEqual(loaded['template'],'luxe-minimal')
        self.assertEqual(loaded['title'],self.r['title'])
        self.assertEqual(loaded['sources'],self.r['sources'])

if __name__=='__main__':unittest.main(verbosity=2)
