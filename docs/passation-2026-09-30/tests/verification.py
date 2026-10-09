"""Regressions des chantiers : lecture seule des vrais projets, ecriture dans un bac unique."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'engine'))
from editeur import script, auto, reel, declinaison, montage

class Verification(unittest.TestCase):
    def test_pdf_bingo(self):
        path=next((ROOT/'media/rushs/test-pratique').rglob('Bingo Night Script.pdf'))
        actual=script.parse(path)[0]['blocks']
        expected=script.parse(ROOT/'media/rushs/test-pratique/script-bingo-night.txt')[0]['blocks']
        self.assertEqual(actual,expected)
        self.assertEqual(auto.find_script(path.parent.parent),path)
        for other in path.parent.glob('*.pdf'):
            self.assertIsInstance(script.parse(other),list)

    def test_docx(self):
        path=next((ROOT/'media/rushs').rglob('SAM SCRIPT ADS 2026-08-11.docx'))
        self.assertEqual(script.parse(path),json.loads((ROOT/'docs/passation-2026-09-30/tests/pdf/avant-docx.json').read_text(encoding='utf-8')))

    def test_script_preference(self):
        box=Path(tempfile.mkdtemp(prefix='scripts-',dir=ROOT/'runtime/cache/tmp'))
        for name in ('script.pdf','script.txt','script.docx'):
            (box/name).touch()
        self.assertEqual(auto.find_script(box).suffix,'.docx')

    def test_highlights(self):
        self.assertEqual(reel.auto_highlights([]),set())
        self.assertEqual(reel.auto_highlights(['the'],language='en'),set())
        self.assertEqual(reel.auto_highlights(['gratuit']),{0})
        for lang,text in [('fr','Vous gagnez trois heures et cinq fois moins cher gratuitement'),('en','Save three hours and get your money back for free')]:
            for size in (1,2,3,5,8):
                words=[{'w':w,'start':i*.3,'end':i*.3+.2} for i,w in enumerate(text.split())]
                words[0]['hide']=True
                picked=reel.auto_highlights(words,size,lang,picks=[[0],[1,2],[3],[999]])
                self.assertNotIn(0,picked)
                self.assertTrue(all(0<=i<len(words) for i in picked))
                full=[set(g)<=picked for g in reel.caption_groups(words,size)]
                self.assertFalse(any(a and b for a,b in zip(full,full[1:])))

    def test_emotion(self):
        r=json.loads((ROOT/'docs/direction-creative-v2/tests/fixtures/projects/video1/reels/v1.json').read_text(encoding='utf-8'))
        declinaison._apply_intention(r,declinaison.INTENTIONS['emotion'])
        self.assertTrue(all(not c['tighten'] for c in r['clips']))

    def test_versions_preserved(self):
        box=Path(tempfile.mkdtemp(prefix='versions-',dir=ROOT/'runtime/cache/tmp'))
        (box/'reels').mkdir()
        base=json.loads((ROOT/'docs/direction-creative-v2/tests/fixtures/projects/video1/reels/v1.json').read_text(encoding='utf-8'))
        montage.save(box,'v1',base)
        first=declinaison.create(box,'v1')
        saved=montage.reel_path(box,first['rid']).read_bytes()
        second=declinaison.create(box,'v1')
        self.assertNotEqual(first['rid'],second['rid'])
        self.assertEqual(saved,montage.reel_path(box,first['rid']).read_bytes())

    def test_short_caption_boundaries(self):
        clips=[{'id':str(i),'words':[{'w':w,'start':0,'end':.5}]} for i,w in enumerate(['gratuit','argent','rapide'])]
        highlights=reel.reel_highlights(clips,max_words=1)
        self.assertFalse(highlights['0'] and highlights['1'])

    def test_music_silence_noise(self):
        from unittest.mock import patch
        import numpy as np
        from editeur import style_ref
        for y in (np.zeros(22050*3,dtype=np.float32),np.random.default_rng(22).normal(0,.01,22050*3).astype(np.float32)):
            with patch.object(style_ref.media,'decode_audio',return_value=y):
                self.assertFalse(style_ref._audio('synthetic',[],3)['musique'])

if __name__=='__main__':unittest.main(verbosity=2)
