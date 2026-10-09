"""Test du detourage RVM contre l'ancien MediaPipe, dans un BAC A SABLE (jamais les vrais caches assets/detourage).

Usage (environnement charge, depuis engine/) :
  python ../docs/qualite-2026-09-30/tests/test_detourage_rvm.py [--debut 5.0 --fin 9.0] [--refaire]

Le bac (runtime/cache/tmp/detourage-rvm-test par defaut) contient des JONCTIONS models/ et tools/ (lecture seule)
et une COPIE du media optimise de la prise : ne jamais l'effacer recursivement sans retirer les jonctions d'abord.
Prise testee : Video 1 (projects/script1), plan c3 = prise t02 (3.MP4), vue vers 28-42 s du montage.

Mesures (masques compares en 1080x1920 ; l'ancien 720x1280 est agrandi en bilineaire comme dans le navigateur) :
  marches    rugosite du contour alpha=0,5 : ecart moyen (px) au contour lisse sur 4 px (escaliers/encoches = grand)
  largeur    largeur moyenne de la transition 0,05-0,95 en pixels (grand = bord flou)
  morceaux   aire (px) des taches alpha>0,5 separees de la personne
  voiles     pixels alpha>0,03 a plus de 24 px du corps (ombres, fumee grise)
  table      alpha moyen sur deux zones ou l'on ne voit que la table
  scintil.   ecart moyen d'alpha entre images consecutives sur les pixels immobiles proches de la personne
  scint.bord somme des ecarts d'alpha (px) par image sur les bords immobiles
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

VRAI = Path(__file__).resolve().parents[3]
PREUVES = Path(__file__).resolve().parent / 'detourage-preuves'
TABLE = [(0, 1400, 120, 1520), (0, 1840, 60, 1920)]           # zones table seule (1080x1920), relevees a l'oeil
RECADRAGES = {'main-table': (0, 1440, 560, 1920), 'bras-droit': (700, 1150, 1080, 1650),
              'cheveux': (330, 600, 730, 900), 'epaule-cou': (200, 900, 600, 1250),
              'chaise-gauche': (0, 1050, 380, 1500)}
SOMBRE, VERT = np.array([0x0b, 0x13, 0x20], np.float32), np.array([0, 255, 0], np.float32)


def bac_a_sable(bac, proxy_rel):
    """Cree le bac : jonctions models/ tools/ (lecture), copie du media optimise, caches vides."""
    for d in ('assets/detourage', 'runtime/cache/tmp', Path(proxy_rel).parent.as_posix()):
        (bac / d).mkdir(parents=True, exist_ok=True)
    for lien in ('models', 'tools'):
        if not (bac / lien).exists():
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(bac / lien), str(VRAI / lien)], check=True, capture_output=True)
    copie = bac / proxy_rel
    if not copie.exists():
        shutil.copy2(VRAI / proxy_rel, copie)
    return copie


def decode(path, a, b, w, h):
    """Images de la source decodees exactement comme l'ancien detourage (-ss debut, fps)."""
    p = subprocess.Popen([str(VRAI / 'tools/ffmpeg/bin/ffmpeg.exe'), '-v', 'error', '-ss', str(a), '-t', str(b - a), '-i', str(path),
                          '-vf', 'fps=30', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    while True:
        raw = p.stdout.read(w * h * 3)
        if len(raw) != w * h * 3:
            break
        yield np.frombuffer(raw, np.uint8).reshape(h, w, 3)
    p.wait()


def charger(dossier, i, w, h):
    import cv2
    from PIL import Image
    im = np.array(Image.open(dossier / f'{i:05d}.webp').convert('RGBA')).astype(np.float32) / 255
    if im.shape[1] != w:  # comme le navigateur : mise a l'echelle bilineaire
        im = cv2.resize(im, (w, h), interpolation=cv2.INTER_LINEAR)
    return im[..., :3], im[..., 3]


def rugosite(a, sigma=4):
    """Ecart moyen (px) entre le contour alpha=0,5 (trace au demi-pixel) et ce meme contour lisse sur `sigma` px :
    les escaliers et encoches d'un masque basse resolution agrandi l'augmentent. Bords de l'image ignores."""
    import cv2
    from scipy.ndimage import gaussian_filter1d
    up = cv2.resize(a, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
    cs, _ = cv2.findContours((up > 0.5).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    tot, n = 0.0, 0
    for c in cs:
        if len(c) < 200:
            continue
        p = c[:, 0, :].astype(np.float32)
        dev = np.hypot(*(p - gaussian_filter1d(p, sigma * 2, axis=0, mode='wrap')).T) / 2
        ok = (p[:, 0] > 4) & (p[:, 0] < up.shape[1] - 5) & (p[:, 1] > 4) & (p[:, 1] < up.shape[0] - 5)
        tot += float(dev[ok].sum())
        n += int(ok.sum())
    return tot / max(1, n)


def mesures_bord(a, visage):
    import cv2
    marches = rugosite(a)
    dur = (a > 0.5).astype(np.uint8)
    contours, _ = cv2.findContours(dur, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    perimetre = sum(cv2.arcLength(c, True) for c in contours)
    largeur = float(((a > 0.05) & (a < 0.95)).sum() / max(1.0, perimetre))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(dur, connectivity=8)
    morceaux = 0
    if n > 1:
        h, w = a.shape
        principal = int(lab[min(h - 1, int(visage[1] * h)), min(w - 1, int(visage[0] * w))]) if visage else 0
        if not principal:
            principal = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        morceaux = int(stats[1:, cv2.CC_STAT_AREA].sum() - stats[principal, cv2.CC_STAT_AREA])
    dist = cv2.distanceTransform(1 - dur, cv2.DIST_L2, 3)
    voiles = int(((a > 0.03) & (dist > 24)).sum())
    table = float(np.mean([a[y0:y1, x0:x1].mean() for x0, y0, x1, y1 in TABLE]))
    return {'marches': marches, 'largeur': largeur, 'morceaux': morceaux, 'voiles': voiles, 'table': table}


def planche(nom, i, src, colonnes, box):
    """Grille : ligne 1 sur fond studio sombre, ligne 2 sur vert pur ; 1re colonne = source / alpha du nouveau."""
    from PIL import Image, ImageDraw
    x0, y0, x1, y1 = box
    lignes = []
    for fond in (SOMBRE, VERT):
        tuiles = []
        for titre, (rgb, a) in colonnes:
            c = rgb[y0:y1, x0:x1] * 255 * a[y0:y1, x0:x1, None] + fond * (1 - a[y0:y1, x0:x1, None])
            tuiles.append((c.clip(0, 255).astype(np.uint8), titre))
        premiere = (src[y0:y1, x0:x1], 'source') if fond is SOMBRE else \
            (np.repeat((colonnes[-1][1][1][y0:y1, x0:x1, None] * 255).astype(np.uint8), 3, 2), 'alpha nouveau')
        ligne = []
        for t, titre in [premiere] + tuiles:
            im = Image.fromarray(np.ascontiguousarray(t))
            d = ImageDraw.Draw(im)
            d.rectangle((0, 0, 8 * len(titre) + 10, 16), fill=(0, 0, 0))
            d.text((5, 3), titre, fill=(255, 255, 255))
            ligne += [np.array(im), np.full((y1 - y0, 6, 3), 255, np.uint8)]
        lignes += [np.concatenate(ligne[:-1], 1), np.full((6, sum(x.shape[1] for x in ligne[:-1]), 3), 255, np.uint8)]
    out = PREUVES / f'{nom}-image{i:03d}.png'
    Image.fromarray(np.concatenate(lignes[:-1], 0)).save(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--debut', type=float, default=5.0)
    ap.add_argument('--fin', type=float, default=9.0)
    ap.add_argument('--bac', default=str(VRAI / 'runtime/cache/tmp/detourage-rvm-test'))
    ap.add_argument('--images', default='24,39,100')
    ap.add_argument('--refaire', action='store_true', help='recalcule les detourages du bac (mesure de vitesse)')
    args = ap.parse_args()
    reel = json.loads((VRAI / 'projects/script1/reels/script.json').read_text(encoding='utf-8'))  # lecture seule
    clip = next(c for c in reel['clips'] if c['id'] == 'c3')
    src = reel['sources'][clip['source']]
    assert clip['in'] <= args.debut < args.fin <= clip['out'], 'plage hors du plan c3'
    bac = Path(args.bac)
    os.environ['EDITEUR_ROOT'] = str(bac)
    proxy = bac_a_sable(bac, src['proxy'])
    sys.path.insert(0, str(VRAI / 'engine'))
    from editeur import detourage, detourage_rvm
    assert detourage.ROOT == bac, 'le moteur doit ecrire dans le bac a sable'
    sujet = detourage._sujet(src)
    a, b, fps = args.debut, args.fin, reel['fps']
    PREUVES.mkdir(parents=True, exist_ok=True)
    cles = {v: detourage._cle(proxy, a, b, fps, v) for v in (detourage.VERSION, detourage.VERSION_MEDIAPIPE)}
    if args.refaire:  # uniquement les sorties de ce test, dans le bac
        for k in cles.values():
            for p in (bac / 'assets/detourage').glob(k + '*'):
                shutil.rmtree(p) if p.is_dir() else p.unlink()
    en_cache = any((bac / 'assets/detourage').glob(cles[detourage.VERSION] + '.json'))
    t = time.perf_counter()
    ancien = detourage.cutout_mediapipe(proxy, a, b, fps)
    t_ancien = (time.perf_counter() - t) * 1000 / ancien['count']
    t = time.perf_counter()
    nouveau = detourage.cutout(proxy, a, b, fps, sujet)
    t_nouveau = (time.perf_counter() - t) * 1000 / nouveau['count']
    import torch
    vram = torch.cuda.memory_allocated() if torch.cuda.is_available() else 0
    brut_dir = bac / 'assets/detourage/test-rvm-brut'
    if args.refaire or not (brut_dir / 'qualite.json').exists():
        m = detourage_rvm.Matteur()
        m.run(proxy, a, b, fps, brut_dir, sujet, {'lissage': 0, 'guide': False, 'despill': 0, 'composantes': False,
                                                  'voiles': False, 'plein': False})
        m.close()
    q = json.loads((bac / nouveau['quality']).read_text(encoding='utf-8'))

    # --- controles du format (le lecteur et l'export ne doivent rien changer) ---------------------------------
    erreurs = []
    for champ in ('file', 'start', 'end', 'width', 'height', 'frames', 'fps', 'count', 'fallback', 'quality', 'score'):
        if champ not in nouveau:
            erreurs.append(f'champ absent : {champ}')
    dn, da = bac / nouveau['frames'], bac / ancien['frames']
    if len(list(dn.glob('*.webp'))) != nouveau['count'] or json.loads((dn / 'complete.json').read_text())['count'] != nouveau['count']:
        erreurs.append('nombre d images incoherent')
    from PIL import Image
    with Image.open(dn / '00000.webp') as im:
        if im.mode != 'RGBA' or im.size != (src['width'], src['height']):
            erreurs.append(f'image {im.mode} {im.size}')
    if abs(nouveau['count'] - ancien['count']) > 1:
        erreurs.append(f"nombre d images {nouveau['count']} contre {ancien['count']} avant")
    if vram:
        erreurs.append(f'memoire graphique non liberee : {vram} octets')
    W, H = src['width'], src['height']

    # --- mesures image par image -------------------------------------------------------------------------------
    import cv2
    res = {n: {'marches': [], 'largeur': [], 'morceaux': [], 'voiles': [], 'table': [], 'scint': [], 'scint_bord': []}
           for n in ('ancien', 'brut', 'nouveau')}
    dossiers = {'ancien': da, 'brut': brut_dir, 'nouveau': dn}
    prec, alignement = {}, None
    choix = [int(x) for x in args.images.split(',')]
    sources = {}
    s_prec = None
    count = min(ancien['count'], nouveau['count'])
    for i, s in enumerate(decode(proxy, a, b, W, H)):
        if i >= count:
            break
        if i in choix:
            sources[i] = s.copy()
        flou = cv2.blur(s, (5, 5)).astype(np.int16)
        statique = None
        if s_prec is not None:
            statique = cv2.erode(((np.abs(flou - s_prec).max(2)) <= 3).astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
        s_prec = flou
        visage = detourage_rvm._point_sujet(sujet, a + i / fps)
        for n, d in dossiers.items():
            rgb, al = charger(d, i, W, H)
            if n == 'nouveau' and i == 0:  # alignement temporel : l'image 0 doit etre la source a `debut`
                alignement = rgb
            if i % 2 == 0:
                for k, v in mesures_bord(al, visage).items():
                    res[n][k].append(v)
            if statique is not None:
                p = prec[n]
                pres = statique & ((al > 0.02) | (p > 0.02))
                bord = statique & (((al > 0.05) & (al < 0.95)) | ((p > 0.05) & (p < 0.95)))
                diff = np.abs(al - p)
                res[n]['scint'].append((float(diff[pres].sum()), int(pres.sum())))
                res[n]['scint_bord'].append((float(diff[bord].sum()), int(bord.sum())))
            prec[n] = al
    # alignement : erreur RVB a l'interieur de la personne contre les images source voisines
    trames = list(decode(proxy, max(0, a - 2 / fps), a + 3 / fps, W, H))
    _, a0 = charger(dn, 0, W, H)
    dedans = a0 > 0.99
    ecarts = [float(np.abs(alignement[dedans] * 255 - t[dedans]).mean()) for t in trames[:5]]
    decalage = int(np.argmin(ecarts)) - 2
    if decalage != 0:
        erreurs.append(f'decalage temporel de {decalage} image(s)')

    resume = {}
    for n, r in res.items():
        resume[n] = {k: round(float(np.mean(v)), 4) for k, v in r.items() if k not in ('scint', 'scint_bord')}
        somme, nb = map(sum, zip(*r['scint']))
        resume[n]['scint'] = round(somme / max(1, nb), 5)       # par pixel immobile proche de la personne
        resume[n]['scint_bord'] = round(sum(s for s, _ in r['scint_bord']) / len(r['scint_bord']), 1)  # px par image
    resume['vitesse_ms_image'] = {'depuis_cache': en_cache, 'ancien_mediapipe_720p': round(t_ancien, 1), 'nouveau_rvm_1080p_total': round(t_nouveau, 1),
                                  'detail_nouveau': q['vitesse_ms_image'], 'moteur': q['moteur'], 'ratio': q['ratio']}
    resume['qualite'] = {'score_moyen': q['score_moyen'], 'score_min': q['score_min'], 'repli': q['repli']}
    resume['alignement_ecarts'] = [round(e, 2) for e in ecarts]

    # --- planches de comparaison -------------------------------------------------------------------------------
    images = []
    for i in choix:
        if i >= count:
            continue
        cols = [('ancien MediaPipe', charger(da, i, W, H)), ('RVM brut', charger(brut_dir, i, W, H)),
                ('nouveau RVM', charger(dn, i, W, H))]
        for nom, box in RECADRAGES.items():
            images.append(str(planche(nom, i, sources[i], cols, box)))
        images.append(str(planche('entier', i, sources[i], cols, (0, 0, W, H))))
    for p in [x for x in images if 'entier' in x]:  # image entiere reduite de moitie (lisible)
        with Image.open(p) as im:
            im.resize((im.width // 2, im.height // 2)).save(p)
    resume['planches'] = images
    resume['erreurs'] = erreurs
    (PREUVES / 'resultats.json').write_text(json.dumps(resume, ensure_ascii=False, indent=1), encoding='utf-8')

    print(f"{'':10}{'marches':>9}{'largeur':>9}{'morceaux':>10}{'voiles':>9}{'table':>8}{'scintil.':>10}{'scint.bord':>11}")
    for n in ('ancien', 'brut', 'nouveau'):
        r = resume[n]
        print(f"{n:10}{r['marches']:9.3f}{r['largeur']:9.2f}{r['morceaux']:10.0f}{r['voiles']:9.0f}{r['table']:8.3f}"
              f"{r['scint']:10.5f}{r['scint_bord']:11.1f}")
    print('vitesse', resume['vitesse_ms_image'])
    print('qualite', resume['qualite'], 'alignement', resume['alignement_ecarts'])
    print('planches', PREUVES)
    ok = not erreurs and resume['nouveau']['marches'] < resume['ancien']['marches'] and \
        resume['nouveau']['table'] < resume['ancien']['table'] and resume['nouveau']['voiles'] < resume['ancien']['voiles']
    print('RESULTAT', 'OK' if ok else 'ECHEC', erreurs)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
