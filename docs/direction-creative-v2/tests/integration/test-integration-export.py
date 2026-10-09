"""Export COURT du reel de reference V2 (toutes les fonctions a la fois), par le VRAI chemin de la file d'exports
(node remotion/render.mjs <job.json>, lance depuis remotion/), puis controle des images, du son et des timecodes.
    python ../docs/direction-creative-v2/tests/integration/test-integration-export.py      (depuis engine/, environnement charge)
Quatre exports, UN A LA FOIS (verrou partage avec les essais d'export de la banque) :
  A : 14,0 -> 18,0 s, reel complet (charte A rose, notes + dessins magenta, whoosh de la banque a 15,0 s, 2 modeles,
      2 vecteurs, choregraphie) ;
  B : la meme chose SANS notes ni dessins ni whoosh ; B2 : B rendu une 2e fois. Deux rendus du MEME reel ne sont pas
      identiques au pixel pres (Chrome/GPU, ecart moyen ~1/255 : bruit de rendu, deja la avant la V2) : A - B doit rester
      au niveau de B - B2 partout, et aucun magenta la ou les dessins seraient -> notes/dessins absents ; A - B (son) = le
      whoosh seul ;
  C : 15,0 -> 17,0 s, charte B (verte) -> le modele et le vecteur « charte » changent de couleur, les retouches restent.
Sorties : runtime/cache/tmp/dcv2-integration/export-<hasard>/ (videos, images extraites, planche-integration.png a
REGARDER). Rien dans livraisons/ ni projects/. Pistes brutes (.fx.raw, .wav) effacees apres mesure."""
import copy
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from commun import BASE, CHARTE_B, RETOUCHE, ROOT, complet, lire  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

FFMPEG = str(ROOT / 'tools/ffmpeg/bin/ffmpeg.exe')
FFPROBE = str(ROOT / 'tools/ffmpeg/bin/ffprobe.exe')
SR = 48000
BAC = Path(tempfile.mkdtemp(prefix='export-', dir=BASE))
VERROU = ROOT / 'runtime/cache/tmp/dcv2-banque/export.verrou'  # meme verrou que les essais d'export de la banque
ROSE, VERT = (0xFF, 0x2D, 0x95), (0x22, 0xC5, 0x5E)
BLEU = tuple(int(RETOUCHE[i:i + 2], 16) for i in (1, 3, 5))


def exporter(reel, nom, debut, secondes):
    """Export court par render.mjs (comme la file d'exports) ; GARDER_PISTES garde la piste des effets (.fx.raw)."""
    out = BAC / f'{nom}.mp4'
    job = BAC / f'{nom}.job.json'
    fps = reel['fps']
    job.write_text(json.dumps({'reel': reel, 'out': str(out), 'frameRange': [round(debut * fps), round((debut + secondes) * fps) - 1]},
                              ensure_ascii=False), encoding='utf-8')
    t0 = time.time()
    r = subprocess.run(['node', str(ROOT / 'remotion/render.mjs'), str(job)], cwd=ROOT / 'remotion', capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env={**os.environ, 'GARDER_PISTES': '1'}, timeout=900)
    (BAC / f'{nom}.log').write_text(r.stdout + '\n' + r.stderr, encoding='utf-8')
    assert r.returncode == 0 and out.is_file(), f'export {nom} : echec\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}'
    print(f'  export {nom} : {secondes:.0f} s de montage en {time.time() - t0:.0f} s')
    return out


def sonde(video):
    r = subprocess.run([FFPROBE, '-v', 'error', '-count_frames', '-show_entries', 'stream=codec_type,codec_name,width,height,r_frame_rate,'
                        'nb_read_frames,sample_rate:format=duration', '-of', 'json', str(video)], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def images(video, w=1080, h=1920):
    """Toutes les images decodees (rgb24), une par une."""
    p = subprocess.Popen([FFMPEG, '-v', 'error', '-i', str(video), '-map', '0:v:0', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    n = w * h * 3
    try:
        while True:
            b = p.stdout.read(n)
            if len(b) < n:
                break
            yield np.frombuffer(b, np.uint8).reshape(h, w, 3)
    finally:  # lecture arretee avant la fin : FFmpeg est arrete proprement
        p.kill()
        p.wait()


def image_n(video, i, w=1080, h=1920):
    """L'image n° i (0 = premiere image du fichier), rgb24."""
    r = subprocess.run([FFMPEG, '-v', 'error', '-i', str(video), '-map', '0:v:0', '-vf', f'select=eq(n\\,{i})', '-frames:v', '1',
                        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(h, w, 3)


def pcm(video):
    r = subprocess.run([FFMPEG, '-v', 'error', '-i', str(video), '-vn', '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype='<f4')


def piste_fx(video):
    return np.fromfile(str(video) + '.fx.raw', dtype='<f4').reshape(-1, 2).mean(axis=1)


def db(x):
    return 20 * np.log10(np.sqrt(np.mean(np.square(x))) + 1e-12)


def part(im, zone, couleur, tol=60):
    """Part des pixels de la zone (x0, y0, x1, y1 en 0..1) proches de la couleur."""
    h, w, _ = im.shape
    x0, y0, x1, y1 = zone
    z = im[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)].astype(int)
    d = np.sqrt(((z - np.array(couleur)) ** 2).sum(axis=2))
    return float((d < tol).mean())


def magenta(im):
    return int(((im[..., 0] > 200) & (im[..., 1] < 90) & (im[..., 2] > 200)).sum())


class ExportIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        debut = time.time()
        while True:  # un seul export a la fois (d'autres essais peuvent tourner)
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
        r, pose = complet(lire('projects/script2/reels/script.json'))
        # mise en page lisible pour la planche : etoile (charte) en haut a gauche, coeur (retouche) en haut a droite,
        # chiffre (modele, charte) au centre, liste (modele retouche) deplacee dans la fenetre exportee
        by = lambda champ, k: next(e for e in r[champ] if e['id'] == pose[k]['id'])  # noqa: E731
        by('vectors', 'etoile').update(x=.22, y=.13, w=.26)
        by('vectors', 'coeur').update(x=.78, y=.13, w=.26)
        by('graphics', 'chiffre')['props']['y'] = .32
        liste = by('graphics', 'liste')
        liste.update(at=16.6, duration=2.0)
        liste['props']['y'] = .40
        cls.r, cls.pose = r, pose
        cls.fps = r['fps']
        (BAC / 'reel-A.json').write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
        sans = copy.deepcopy(r)
        sans.pop('notes')
        sans.pop('annotations')
        sans['sfx']['extra'] = [e for e in sans['sfx']['extra'] if e.get('id') != pose['son']['id']]
        c = copy.deepcopy(r)
        c['brand'] = copy.deepcopy(CHARTE_B)
        c['style'] = {**c['style'], **CHARTE_B['style']}  # comme l'onglet Style : la charte passe par-dessus le style
        cls.A = exporter(r, 'A-complet', 14.0, 4.0)
        cls.B = exporter(sans, 'B-sans-notes-ni-whoosh', 14.0, 4.0)
        cls.B2 = exporter(sans, 'B2-meme-reel-rendu-deux-fois', 14.0, 4.0)
        cls.C = exporter(c, 'C-charte-verte', 15.0, 2.0)

    @classmethod
    def tearDownClass(cls):
        VERROU.unlink(missing_ok=True)
        for motif in ('*.fx.raw', '*.mix.wav', '*.voix.wav'):
            for f in BAC.glob(motif):
                f.unlink(missing_ok=True)

    def test_1_fichiers_et_timecodes(self):
        for v, n in ((self.A, 120), (self.B, 120), (self.C, 60)):
            s = sonde(v)
            vid = next(x for x in s['streams'] if x['codec_type'] == 'video')
            aud = next(x for x in s['streams'] if x['codec_type'] == 'audio')
            dur = float(s['format']['duration'])
            print(f'  {v.name} : {vid["codec_name"]} {vid["width"]}x{vid["height"]} {vid["r_frame_rate"]} i/s, {vid["nb_read_frames"]} images, '
                  f'{aud["codec_name"]} {aud["sample_rate"]} Hz, {dur:.3f} s')
            self.assertEqual((vid['codec_name'], vid['width'], vid['height'], vid['r_frame_rate']), ('h264', 1080, 1920, '30/1'))
            self.assertEqual(int(vid['nb_read_frames']), n, 'nombre d\'images = duree demandee')
            self.assertEqual((aud['codec_name'], aud['sample_rate']), ('aac', '48000'))
            self.assertLess(abs(dur - n / 30), 0.05, 'duree du fichier')

    def test_2_notes_et_dessins_absents(self):
        """A (avec notes + dessins magenta) contre B (sans) : ecart au niveau du bruit de rendu (B contre B2), et AUCUN magenta
        la ou l'apercu affiche les dessins (temoin calcule par timeline.ts)."""
        ab, bb, mag_a, mag_b = [], [], 0, 0
        for ia, ib, ib2 in zip(images(self.A), images(self.B), images(self.B2)):
            ab.append(float(np.abs(ia.astype(np.int16) - ib).mean()))
            bb.append(float(np.abs(ib2.astype(np.int16) - ib).mean()))
            mag_a += magenta(ia)
            mag_b += magenta(ib)
        # temoin : les dessins visibles a 15,3 s et 16,0 s dans l'apercu, peints a l'epaisseur du calque
        temoin, dans_a, ecart_masque = 0, 0, []
        for t in (15.3, 16.0):
            pts = json.loads(subprocess.run(['node', str(Path(__file__).resolve().parent / 'ancres.mjs'), '--points', str(BAC / 'reel-A.json'), str(t)],
                                            capture_output=True, text=True, check=True).stdout)
            im = Image.new('L', (1080, 1920), 0)
            d = ImageDraw.Draw(im)
            for a in pts.values():
                d.line([(x * 1080, y * 1920) for x, y in a['points']], fill=255, width=max(2, int(a['epaisseur'] * 1080 / 2160)))
            masque = np.asarray(im) > 0
            i = round((t - 14.0) * 30)
            ia, ib = image_n(self.A, i), image_n(self.B, i)
            temoin += int(masque.sum())
            dans_a += int(((ia[..., 0] > 200) & (ia[..., 1] < 90) & (ia[..., 2] > 200) & masque).sum())
            ecart_masque.append(float(np.abs(ia.astype(np.int16) - ib)[masque].mean()))
        print(f'  ecart moyen par image : A-B {max(ab):.2f}/255 au plus, B-B2 (meme reel rendu deux fois) {max(bb):.2f}/255 au plus ;'
              f' pixels magenta : A {mag_a}, B {mag_b}')
        print(f"  temoin : les dessins de l'apercu couvriraient {temoin} pixels a 15,3 s et 16,0 s ; dans l'export A, {dans_a} y sont"
              f' magenta ; ecart A-B sous les dessins {max(ecart_masque):.1f}/255 (un dessin magenta donnerait plus de 100)')
        self.assertGreater(temoin, 5000, 'le temoin montre bien des dessins visibles pendant la fenetre exportee')
        self.assertLess(dans_a, temoin * 0.002, "aucun dessin dans l'export")
        self.assertLess(max(ecart_masque), 15, 'sous les dessins : seulement le bruit de rendu')
        self.assertLessEqual(max(ab), max(bb) * 1.5 + 0.5, 'A-B au niveau du bruit de rendu (B-B2)')

    def test_3_son_de_la_banque(self):
        """Le whoosh pose a 15,0 s : dans la piste des effets (A - B) au bon instant et nulle part ailleurs ; audible dans le
        fichier final ; niveau final sain."""
        d = piste_fx(self.A) - piste_fx(self.B)
        actif = np.flatnonzero(np.abs(d) > 1e-5)
        self.assertTrue(len(actif), 'le whoosh est dans la piste des effets')
        t0, t1 = actif[0] / SR, actif[-1] / SR
        print(f'  piste des effets : whoosh seul de {t0:.4f} a {t1:.3f} s (pose a 15,000 s, dure 0,35 s), {db(d[actif[0]:actif[-1]]):.1f} dB')
        self.assertLessEqual(abs(t0 - 15.0), 1 / 30 + 1e-3, 'il part a la bonne image')
        self.assertLessEqual(t1, 15.0 + 3.0 + 1 / 30, 'et nulle part ailleurs (bruitages coupes a 3 s)')
        st = subprocess.run([FFMPEG, '-v', 'error', '-i', str(self.A), '-vn', '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True, check=True)
        crete = float(np.abs(np.frombuffer(st.stdout, dtype='<f4')).max())  # crete sur chaque canal (pas le mono replie)
        x, y = pcm(self.A), pcm(self.B)
        n = min(len(x), len(y))
        x, y = x[:n], y[:n]
        a, b = int(1.0 * SR), int(1.35 * SR)
        masque = np.ones(n, bool)
        masque[int(.95 * SR):int(1.5 * SR)] = False
        k = float(np.dot(x[masque], y[masque]) / (np.dot(y[masque], y[masque]) + 1e-12))
        res = x - k * y
        dans, ailleurs = db(res[a:b]), db(res[masque])
        print(f'  fichier final : whoosh {dans:.1f} dB a 15,0-15,35 s, difference ailleurs {ailleurs:.1f} dB ; mixage {db(x):.1f} dB RMS, crete (canaux) {crete:.3f}')
        self.assertGreater(dans - ailleurs, 20, 'le whoosh est dans le fichier final, a cet instant seulement')
        self.assertLess(crete, 0.99, 'pas d\'ecretage (limiteur a -1 dB)')
        self.assertGreater(db(x), -40, 'le son du montage est bien la (voix + musique)')

    def test_4_couleurs_charte_et_retouches(self):
        """Charte A (rose) puis charte B (verte) : le modele et le vecteur sans couleur suivent ; la liste et le coeur retouches
        a la main restent bleus."""
        fa = {i: image_n(self.A, i) for i in (39, 87)}
        fc = {i: image_n(self.C, i) for i in (9, 57)}
        z_chiffre, z_etoile, z_coeur, z_liste = (.12, .24, .88, .40), (.10, .06, .34, .20), (.66, .06, .90, .20), (.10, .40, .90, .60)
        m = {
            'A chiffre (charte A)': part(fa[39], z_chiffre, ROSE), 'A etoile (charte A)': part(fa[39], z_etoile, ROSE),
            'A liste (retouche)': part(fa[87], z_liste, BLEU), 'A coeur (retouche)': part(fa[87], z_coeur, BLEU),
            'C chiffre (charte B)': part(fc[9], z_chiffre, VERT), 'C etoile (charte B)': part(fc[9], z_etoile, VERT),
            'C liste (retouche)': part(fc[57], z_liste, BLEU), 'C coeur (retouche)': part(fc[57], z_coeur, BLEU),
            'C chiffre encore rose ?': part(fc[9], z_chiffre, ROSE),
        }
        for k, v in m.items():
            print(f'  {k} : {v:.1%} des pixels de sa zone')
        for k in ('A chiffre (charte A)', 'C chiffre (charte B)'):
            self.assertGreater(m[k], .03, k)
        for k in ('A etoile (charte A)', 'C etoile (charte B)', 'A liste (retouche)', 'C liste (retouche)', 'A coeur (retouche)', 'C coeur (retouche)'):
            self.assertGreater(m[k], .03, k)
        self.assertLess(m['C chiffre encore rose ?'], .005, 'charte B : plus de rose sur le modele')

    def test_5_elements_a_leur_image(self):
        """Timecodes : le chiffre (14,3 s) et l'etoile (14,5 s) apparaissent a leur image (entree animee comprise)."""
        z_chiffre, z_etoile = (.12, .24, .88, .40), (.10, .06, .34, .20)
        premiers = {}
        for i, im in enumerate(images(self.A)):
            if i > 30:
                break
            for nom, z in (('chiffre', z_chiffre), ('etoile', z_etoile)):
                if nom not in premiers and part(im, z, ROSE) > .004:
                    premiers[nom] = i
        print(f'  premiere image visible : chiffre {premiers.get("chiffre")} (pose a l\'image 9 = 14,3 s), etoile {premiers.get("etoile")} (image 15 = 14,5 s)')
        self.assertTrue(9 <= premiers.get('chiffre', -1) <= 12, 'chiffre a son image')
        self.assertTrue(15 <= premiers.get('etoile', -1) <= 18, 'etoile a son image')

    def test_6_planche(self):
        """Planche d'images extraites (a REGARDER) : 8 images de A, 4 de C, avec le temps du montage."""
        prises = [('A', self.A, 14.0, k) for k in (0.2, 0.7, 1.2, 1.7, 2.2, 2.7, 3.2, 3.7)] + [('C', self.C, 15.0, k) for k in (0.3, 0.8, 1.3, 1.9)]
        vignettes = []
        for nom, v, debut, k in prises:
            p = BAC / f'{nom}-{debut + k:05.2f}.png'
            subprocess.run([FFMPEG, '-v', 'error', '-y', '-ss', f'{k:.3f}', '-i', str(v), '-frames:v', '1', '-vf', 'scale=270:480', str(p)], check=True)
            im = Image.open(p).convert('RGB')
            d = ImageDraw.Draw(im)
            d.rectangle([0, 0, 270, 22], fill=(0, 0, 0))
            d.text((6, 4), f'{nom} {debut + k:05.2f} s', fill=(255, 255, 255))
            vignettes.append(im)
        planche = Image.new('RGB', (270 * 6, 480 * 2), (20, 20, 20))
        for i, im in enumerate(vignettes):
            planche.paste(im, ((i % 6) * 270, (i // 6) * 480))
        out = BAC / 'planche-integration.png'
        planche.save(out)
        print(f'  planche a regarder : {out}')
        self.assertTrue(out.is_file())


if __name__ == '__main__':
    unittest.main(verbosity=2)
