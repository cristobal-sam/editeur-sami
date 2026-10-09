"""Exports COURTS (3 s, l'un apres l'autre) de reels ou la banque a pose un son, un vecteur et un modele, compares a un
export de reference du meme passage SANS ces ajouts : le son s'entend au bon instant (piste des effets et fichier final),
le vecteur et le modele se voient (images extraites, pixels, planches a regarder).
    python ../docs/direction-creative-v2/tests/banque/test-export-banque.py      (depuis engine/, environnement charge)
Copies EN MEMOIRE des reels figes fixtures/projects/script2 (Reel Impact, sans habillage) et script1 (Tech, avec habillage) : rien
n'est ecrit dans projects/, media/ ni livraisons/. Bac : runtime/cache/tmp/dcv2-banque/export-<hasard>/ (videos, pistes,
images, planches)."""
import copy
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FIX = HERE.parent / 'fixtures'  # donnees figees des tests
sys.path.insert(0, str(ROOT / 'engine'))
os.environ['EDITEUR_LLM'] = '0'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from editeur import banque  # noqa: E402

FFMPEG = str(ROOT / 'tools/ffmpeg/bin/ffmpeg.exe')
BAC = Path(tempfile.mkdtemp(prefix='export-', dir=ROOT / 'runtime/cache/tmp/dcv2-banque'))
CAT = {e['id']: e for e in banque.catalogue()['entrees']}
SR = 48000


def lire(p):
    return json.loads((FIX / f'projects/{p}/reels/script.json').read_text(encoding='utf-8'))


def exporter(reel, nom, debut, secondes=3.0):
    """Export court (render.mjs, comme la file d'exports) ; GARDER_PISTES garde la piste des effets (.fx.raw)."""
    out = BAC / f'{nom}.mp4'
    job = BAC / f'{nom}.job.json'
    fps = reel['fps']
    job.write_text(json.dumps({'reel': reel, 'out': str(out), 'frameRange': [round(debut * fps), round((debut + secondes) * fps) - 1]},
                              ensure_ascii=False), encoding='utf-8')
    r = subprocess.run(['node', str(ROOT / 'remotion/render.mjs'), str(job)], cwd=ROOT / 'remotion', capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env={**os.environ, 'GARDER_PISTES': '1'}, timeout=900)
    (BAC / f'{nom}.log').write_text(r.stdout + '\n' + r.stderr, encoding='utf-8')
    assert r.returncode == 0 and out.is_file(), f'export {nom} : echec\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}'
    return out


def db(x):
    return 20 * math.log10(float(np.sqrt(np.mean(np.square(x)))) + 1e-12) if len(x) else -240.0


def piste_fx(out):
    return np.fromfile(str(out) + '.fx.raw', dtype='<f4').reshape(-1, 2).mean(axis=1)


def pcm(video):
    r = subprocess.run([FFMPEG, '-v', 'error', '-i', str(video), '-vn', '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype='<f4')


def image(video, t, nom):
    p = BAC / f'{nom}.png'
    subprocess.run([FFMPEG, '-v', 'error', '-y', '-ss', f'{t:.3f}', '-i', str(video), '-frames:v', '1', str(p)], check=True)
    return p


def zone(p, z):
    im = np.asarray(Image.open(p).convert('RGB')).astype(int)
    h, w, _ = im.shape
    x0, y0, x1, y1 = z
    return im[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)]


def pixels(p, z, rgb, tol=60):
    """Part des pixels de la zone (x0, y0, x1, y1 en 0-1) proches de la couleur rgb."""
    return float((np.abs(zone(p, z) - np.array(rgb)).sum(axis=2) < tol).mean())


def ecart(p1, p2, z):
    """Difference moyenne (0-255, par canal) entre deux images dans la zone."""
    return float(np.abs(zone(p1, z) - zone(p2, z)).mean())


def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def planche(images, nom):
    ims = [Image.open(p).convert('RGB').resize((360, 640)) for p in images]
    out = Image.new('RGB', (360 * len(ims) + 8 * (len(ims) + 1), 656), (17, 19, 24))
    for i, im in enumerate(ims):
        out.paste(im, (8 + i * 368, 8))
    p = BAC / f'{nom}.jpg'
    out.save(p, quality=88)
    return p


VERROU = ROOT / 'runtime/cache/tmp/dcv2-banque/export.verrou'


class ExportBanque(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Un seul export a la fois : d'autres sessions lancent aussi ces essais (verrou, perime apres 20 min)."""
        import time
        debut = time.time()
        while True:
            try:
                os.close(os.open(VERROU, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                break
            except FileExistsError:
                if time.time() - VERROU.stat().st_mtime > 1200:
                    VERROU.unlink(missing_ok=True)
                elif time.time() - debut > 900:
                    raise unittest.SkipTest('un autre essai d\'export tourne depuis plus de 15 min')
                time.sleep(2)
        print(f'BAC={BAC}')

    @classmethod
    def tearDownClass(cls):
        VERROU.unlink(missing_ok=True)

    def tearDown(self):
        # pistes brutes (~60 Mo par export) : lues pendant l'essai, inutiles ensuite ; videos, images et planches gardees
        for motif in ('*.fx.raw', '*.mix.wav', '*.voix.wav'):
            for f in BAC.glob(motif):
                f.unlink(missing_ok=True)

    def son(self, out, ref, debut, t_son, duree, fps):
        """Le son pose a t_son (temps du montage) est-il dans l'export, au bon instant, et audible ?"""
        # 1. piste des effets (musique + bruitages, exactement ce qui est mixe) : la difference AVEC - SANS = le son seul
        fx, fx0 = piste_fx(out), piste_fx(ref)
        d = fx - fx0
        actif = np.flatnonzero(np.abs(d) > 1e-5)
        t0 = actif[0] / SR if len(actif) else None
        fin = actif[-1] / SR if len(actif) else None
        a, b = int(t_son * SR), int((t_son + min(duree, 0.5)) * SR)
        son, musique = db(d[a:b]), db(fx0[a:b])
        hors = np.concatenate([d[:max(0, a - 1)], d[int((t_son + duree + 0.05) * SR):]])
        print(f'  piste des effets : son seul {son:.1f} dB, musique au meme instant {musique:.1f} dB ; son present de {t0:.4f} a {fin:.3f} s'
              f' (pose a {t_son:.3f} s, dure {duree:.2f} s) ; ailleurs {db(hors):.1f} dB')
        self.assertIsNotNone(t0, 'le son est dans la piste des effets')
        self.assertLessEqual(abs(t0 - t_son), 1 / fps + 1e-3, 'il part au bon instant (a une image pres)')
        self.assertLessEqual(fin, t_son + duree + 1 / fps, 'et nulle part ailleurs')
        # 2. fichier final (voix + musique + effets, -14 LUFS, limiteur) : export AVEC contre export SANS
        x, y = pcm(out), pcm(ref)
        n = min(len(x), len(y))
        x, y = x[:n], y[:n]
        a, b = int((t_son - debut) * SR), int((t_son - debut + min(duree, 0.5)) * SR)
        masque = np.ones(n, bool)
        masque[max(0, a - int(0.05 * SR)):int((t_son - debut + duree + 0.1) * SR)] = False
        k = float(np.dot(x[masque], y[masque]) / (np.dot(y[masque], y[masque]) + 1e-12))  # gain de normalisation propre a chaque export
        r = x - k * y
        dans, ailleurs, mix = db(r[a:b]), db(r[masque]), db(x[a:b])
        print(f'  fichier final : son de la banque {dans:.1f} dB, mixage a cet instant {mix:.1f} dB (le son est {mix - dans:.1f} dB sous le mixage) ;'
              f' difference ailleurs {ailleurs:.1f} dB (gain relatif des deux exports {k:.4f})')
        self.assertGreater(dans - ailleurs, 20, 'le son est dans le fichier final, a cet instant seulement')
        return {'fx_son': son, 'fx_musique': musique, 'final_son': dans, 'final_mix': mix, 'final_ailleurs': ailleurs, 'debut': t0}

    def test_1_sans_habillage(self):
        """Reel Impact (script2) : son Kenney (impact lourd), vecteur flèche, modèle « liste cochée »."""
        base = lire('script2')
        r = copy.deepcopy(base)
        mots = banque._mots_dits(r)
        son = next(i for i in CAT if i.startswith('son:kenney:impact-sounds-impactMetal_heavy_000'))
        i_son = banque.ajouter(r, CAT[son], 15.5, mots)
        i_vec = banque.ajouter(r, CAT['vecteur:fleche'], 15.2, mots)
        i_tpl = banque.ajouter(r, CAT['template:liste-benefices'], 16.6, mots)
        i_vec['element']['duration'] = 1.2   # meme objet que dans le reel : 15,2 -> 16,4 s
        i_tpl['element']['duration'] = 1.3   # 16,6 -> 17,9 s
        self.assertTrue(i_son['visible'] and i_vec['visible'] and i_tpl['visible'])
        self.assertEqual((i_son['champ'], i_vec['champ'], i_tpl['champ']), ('sfx.extra', 'vectors', 'graphics'))
        out = exporter(r, 'a-avec-la-banque', 15.0)
        ref = exporter(base, 'a-reference', 15.0)
        print(f'volume des bruitages de ce reel : {r["sfx"]["volume"]} ; gain du son : {i_son["element"]["gain"]}')
        s = self.son(out, ref, 15.0, 15.5, CAT[son]['duree'], r['fps'])
        self.assertGreater(s['final_son'], s['final_mix'] - 20, 'assez fort pour s\'entendre sous la voix')
        # images : vecteur (15,9 s), entre les deux (16,5 s), liste cochee (17,3 s), comparees a la reference
        coul = banque.palette(r)['principale']
        f = {n: (image(out, t, f'a-{n}'), image(ref, t, f'a-{n}-reference')) for n, t in (('vecteur', 0.9), ('entre', 1.5), ('liste', 2.3))}
        v, g = i_vec['element'], i_tpl['element']
        tv = banque.taille_element(r, 'vectors', None, {'w': v['w'], 'ratio': CAT['vecteur:fleche']['params']['ratio']})
        tg = banque.taille_element(r, 'graphics', 'coches', g['props'])
        z_vec = (v['x'] - tv['w'] / 2, v['y'] - tv['h'] / 2, v['x'] + tv['w'] / 2, v['y'] + tv['h'] / 2)  # fleche, placee hors du visage
        z_tpl = (0.10, g['props']['y'], 0.90, g['props']['y'] + tg['h'])  # cases cochees (y = bord haut)
        print(f'  positions : fleche centre ({v["x"]}, {v["y"]}) ; liste bord haut {g["props"]["y"]}')
        mesures = {'fleche': (ecart(*f['vecteur'], z_vec), pixels(f['vecteur'][0], z_vec, hexrgb(coul)), pixels(f['vecteur'][1], z_vec, hexrgb(coul))),
                   'entre (fleche)': (ecart(*f['entre'], z_vec), pixels(f['entre'][0], z_vec, hexrgb(coul)), 0.0),
                   'entre (liste)': (ecart(*f['entre'], z_tpl), pixels(f['entre'][0], z_tpl, hexrgb(coul)), 0.0),
                   'liste': (ecart(*f['liste'], z_tpl), pixels(f['liste'][0], z_tpl, hexrgb(coul)), pixels(f['liste'][1], z_tpl, hexrgb(coul)))}
        for k, (e, p, p0) in mesures.items():
            print(f'  image « {k} » : difference avec la reference {e:.1f} / 255 ; pixels couleur charte {coul} {p:.1%} (reference {p0:.1%})')
        self.assertGreater(mesures['fleche'][0], 30)
        self.assertGreater(mesures['fleche'][1], 0.15, 'la fleche est aux couleurs de la charte / du style')
        self.assertLess(mesures['entre (fleche)'][0], 3, 'entre les deux : image identique a la reference')
        self.assertLess(mesures['entre (liste)'][0], 3)
        self.assertGreater(mesures['liste'][0], 30)
        self.assertGreater(mesures['liste'][1], 0.02)
        print('PLANCHE_A=' + str(planche([f['vecteur'][0], f['entre'][0], f['liste'][0], f['liste'][1]], 'planche-a')))

    def test_2_avec_habillage(self):
        """Tech (script1, bruitages coupés) : « Activer les bruitages », son créé ici (impact cinéma), modèle notification
        -> scène du style ancrée au mot dit."""
        base = lire('script1')
        r = copy.deepcopy(base)
        mots = banque._mots_dits(r)
        self.assertFalse(r['sfx']['enabled'])
        i_son = banque.ajouter(r, CAT['son:banque:impact-cinema'], 16.4, mots)
        self.assertFalse(i_son['visible'], 'bruitages coupés : le dire')
        r['sfx'] = {**r['sfx'], 'enabled': True}  # bouton « Activer les bruitages » (ne change rien d'autre)
        i_tpl = banque.ajouter(r, CAT['template:notification'], 16.2, mots)
        self.assertEqual((i_tpl['champ'], i_tpl['element']['kind']), ('styleScenes', 'notification'))
        self.assertIs(r['styleScenes'][0], i_tpl['element'], 'en tete : passe devant une scene automatique au meme moment')
        w = banque._mot_a(mots, 16.2)
        print(f'scene ancree au mot « {w["w"]} » ({w["start"]:.2f} s)')
        ref_reel = copy.deepcopy(base)
        ref_reel['sfx'] = {**ref_reel['sfx'], 'enabled': True}  # meme reglage, sans les ajouts
        out = exporter(r, 'b-avec-la-banque', 16.0)
        ref = exporter(ref_reel, 'b-reference', 16.0)
        print(f'volume des bruitages de ce reel : {r["sfx"]["volume"]} ; gain du son : {i_son["element"]["gain"]}')
        self.son(out, ref, 16.0, 16.4, CAT['son:banque:impact-cinema']['duree'], r['fps'])
        t_img = w['start'] - 16.0 + 1.0
        f1, f0 = image(out, t_img, 'b-notification'), image(ref, t_img, 'b-notification-reference')
        z = (0.08, 0.13, 0.92, 0.27)  # carte de notification centree en y 0,2
        e_carte, e_bas = ecart(f1, f0, z), ecart(f1, f0, (0.08, 0.30, 0.92, 0.60))
        print(f'  image « notification » : difference avec la reference {e_carte:.1f} / 255 dans la carte, {e_bas:.1f} / 255 sous la carte')
        self.assertGreater(e_carte, 25, 'la notification apparait a l\'endroit prevu')
        print('PLANCHE_B=' + str(planche([f1, f0], 'planche-b')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
