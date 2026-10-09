"""Revue adverse du detourage RVM (bac a sable, jamais les vrais caches) : cas difficiles.
  - nuit tres sombre (18A-1), foule / plusieurs personnes (12H-3, 19C-2), paysage 16:9 avec piste (12G-3) ;
  - deux personnes (Video 1 + son miroir) : les deux doivent rester, meme si la piste suit une seule personne ;
  - plage qui commence a 0 s, plage tres courte, plage qui depasse la fin du fichier ;
  - prepare() en Tech 3D cinematique : plan sous un autre angle / media illisible sans faire echouer le style ;
  - carte graphique en panne pendant le calcul, puis sans carte graphique (processeur) ;
  - faux positifs du score sur les autres plans reels de Video 1.
Usage (environnement charge, depuis engine/) :
  python ../docs/qualite-2026-09-30/tests/test_detourage_revue.py [--cas nuit,foule,...] [--refaire]
Le bac (runtime/cache/tmp/detourage-revue-q8w3/bac) contient des JONCTIONS models/ et tools/ : ne jamais l'effacer
recursivement sans retirer les jonctions d'abord.
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
PREUVES = Path(__file__).resolve().parent / 'detourage-preuves' / 'revue'
BAC = VRAI / 'runtime/cache/tmp/detourage-revue-q8w3/bac'
FF = str(VRAI / 'tools/ffmpeg/bin/ffmpeg.exe')
OPT = VRAI / 'projects/_cache/optimises'
SOMBRE, VERT = np.array([0x0b, 0x13, 0x20], np.float32), np.array([0, 255, 0], np.float32)
RESULTATS = []


def verifier(nom, ok, detail=''):
    RESULTATS.append((nom, bool(ok)))
    print(('OK   ' if ok else 'ECHEC') + f' {nom} {detail}', flush=True)


def preparer_bac():
    for d in ('assets/detourage', 'media', 'runtime/cache/tmp'):
        (BAC / d).mkdir(parents=True, exist_ok=True)
    for lien in ('models', 'tools'):
        if not (BAC / lien).exists():
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(BAC / lien), str(VRAI / lien)], check=True, capture_output=True)


def extrait(nom, source, debut, duree, vf=None):
    """Morceau court d'un media optimise (copie dans le bac), re-encode a 30 i/s (images cles denses)."""
    out = BAC / 'media' / f'{nom}.mp4'
    if not out.exists():
        cmd = [FF, '-v', 'error', '-y', '-ss', str(debut), '-t', str(duree), '-i', str(source)]
        if vf:
            cmd += ['-filter_complex', vf]
        cmd += ['-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '14', '-g', '15', '-pix_fmt', 'yuv420p', str(out)]
        subprocess.run(cmd, check=True)
    return out


def sujet_decale(points, debut, fx=1.0, dx=0.0):
    """Piste visage recalee sur l'extrait (temps - debut), x mis a l'echelle (image composee)."""
    return [[p[0] - debut, p[1] * fx + dx, p[2]] for p in points if len(p) >= 3 and debut - 1 <= p[0]]


def planche(nom, dossier, source, images, decal=0, echelle=0.35):
    """Images choisies : ligne haute sur fond studio sombre, ligne basse sur vert pur, source a gauche."""
    from PIL import Image
    tuiles = []
    cap = list(decode(source))
    for i in images:
        if not (dossier / f'{i:05d}.webp').exists():
            continue
        im = np.array(Image.open(dossier / f'{i:05d}.webp').convert('RGBA')).astype(np.float32) / 255
        if i + decal >= len(cap):
            continue
        src = cap[i + decal]
        if src.shape[:2] != im.shape[:2]:
            import cv2
            src = cv2.resize(src, (im.shape[1], im.shape[0]), interpolation=cv2.INTER_AREA)
        a = im[..., 3:]
        col = []
        for fond in (SOMBRE, VERT):
            col.append((im[..., :3] * 255 * a + fond * (1 - a)).clip(0, 255).astype(np.uint8))
        tuiles.append(np.concatenate([src, *col], 0))
    if not tuiles:
        return None
    g = np.concatenate([np.pad(t, ((0, 0), (0, 8), (0, 0)), constant_values=255) for t in tuiles], 1)
    out = PREUVES / f'{nom}.png'
    im = Image.fromarray(g)
    im.resize((int(im.width * echelle), int(im.height * echelle))).save(out)
    return out


def decode(path):
    import cv2
    cap = cv2.VideoCapture(str(path))
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    p = subprocess.Popen([FF, '-v', 'error', '-i', str(path), '-vf', 'fps=30', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         stdout=subprocess.PIPE)
    while True:
        raw = p.stdout.read(w * h * 3)
        if len(raw) != w * h * 3:
            break
        yield np.frombuffer(raw, np.uint8).reshape(h, w, 3)
    p.wait()


def lancer(detourage, nom, path, a, b, sujet=None, images=(0, 45, 90)):
    t = time.perf_counter()
    doc = detourage.cutout(path, a, b, 30, sujet)
    dt = time.perf_counter() - t
    q = json.loads((detourage.ROOT / doc['quality']).read_text(encoding='utf-8')) if doc.get('quality') else {}
    p = planche(nom, detourage.ROOT / doc['frames'], path, list(images), int(round(a * 30))) if doc.get('frames') else None
    print(f"  {nom}: {doc.get('engine')} {doc.get('count')} images en {dt:.1f} s, score {doc.get('score')}, repli {doc.get('fallback')}, "
          f"vitesse {q.get('vitesse_ms_image')}, planche {p}", flush=True)
    return doc, q


def cas_nuit(detourage):
    src = extrait('nuit-18A', OPT / '18A-1-81c54255.mp4', 2.0, 3.5)
    doc, q = lancer(detourage, 'nuit-18A', src, 0.5, 3.5)
    verifier('nuit : pas de plantage, images produites', doc.get('count', 0) >= 89, doc.get('count'))
    from PIL import Image
    a = np.array(Image.open(detourage.ROOT / doc['frames'] / '00000.webp'))[..., 3] / 255
    h, w = a.shape
    fauteuil = float(a[int(.30 * h):int(.55 * h), int(.38 * w):int(.47 * w)].mean())  # personne en fauteuil (2e personne)
    verifier('nuit : la personne en fauteuil reste (pas seulement le policier)', fauteuil > 0.3, round(fauteuil, 3))


def cas_foule(detourage, reel_bingo):
    s = reel_bingo['sources']['t02']
    src = extrait('foule-12H', OPT / '12H-3-3e4b5d92.mp4', 1.0, 3.5)
    doc, q = lancer(detourage, 'foule-12H', src, 0.5, 3.5, sujet_decale(s.get('samples') or [], 1.0))
    verifier('foule : pas de plantage', doc.get('count', 0) >= 89, doc.get('count'))
    verifier('foule : piste visage fausse (analyse perimee) ignoree, pas de repli sur toute la prise',
             q.get('visage_fiable') is False and not doc.get('fallback'), (q.get('visage_fiable'), doc.get('fallback')))
    src = extrait('foule-19C', OPT / '19C-2-ae3fa004.mp4', 2.0, 3.5)
    doc, q = lancer(detourage, 'foule-19C', src, 0.5, 3.5)
    verifier('foule 19C : pas de plantage', doc.get('count', 0) >= 89, doc.get('count'))
    verifier('foule 19C : deux personnes au premier plan gardees (rien de retire)', max(q['mesures']['retire']) < 0.05,
             max(q['mesures']['retire']))


def cas_paysage(detourage, reel_bingo):
    s = reel_bingo['sources']['t01']
    src = extrait('paysage-12G', OPT / '12G-3-26ef7460.mp4', 2.0, 3.5)
    doc, q = lancer(detourage, 'paysage-12G', src, 0.5, 3.5, sujet_decale(s['track'], 2.0))
    verifier('paysage 16:9 : taille conservee', (doc.get('width'), doc.get('height')) == (1920, 1080), (doc.get('width'), doc.get('height')))
    verifier('paysage 16:9 : pas de repli', not doc.get('fallback'), doc.get('fallback'))


def cas_deux(detourage, reel_v1):
    """Video 1 + miroir cote a cote : deux personnes. La piste suit la personne de GAUCHE."""
    s = reel_v1['sources']['t02']
    vf = '[0:v]split[a][b];[b]hflip[c];[a][c]hstack,scale=1920:-2'
    src = extrait('deux-personnes', VRAI / s['proxy'], 5.0, 3.0, vf)
    doc, q = lancer(detourage, 'deux-personnes', src, 0.5, 3.0, sujet_decale(s['samples'], 5.0, 0.5))
    from PIL import Image
    d = detourage.ROOT / doc['frames']
    manque = []
    for i in range(0, doc['count'], 10):
        a = np.array(Image.open(d / f'{i:05d}.webp'))[..., 3] / 255
        w = a.shape[1]
        g, dr = a[:, :w // 2].mean(), a[:, w // 2:].mean()
        if min(g, dr) < 0.5 * max(g, dr):
            manque.append((i, round(float(g), 3), round(float(dr), 3)))
    verifier('deux personnes : les deux gardees', not manque, manque[:5])


def cas_bords(detourage, reel_v1):
    s = reel_v1['sources']['t02']
    src = extrait('debut-fichier', VRAI / s['proxy'], 0.0, 2.0)
    doc, q = lancer(detourage, 'debut-0s', src, 0.0, 1.0, sujet_decale(s['samples'], 0.0), images=(0, 15, 29))
    verifier('plage a 0 s : 30 images', doc.get('count') == 30, doc.get('count'))
    doc, q = lancer(detourage, 'debut-0.2s', src, 0.2, 0.7, sujet_decale(s['samples'], 0.0), images=(0, 14))
    verifier('plage a 0,2 s : 15 images', doc.get('count') == 15, doc.get('count'))
    verifier('plage a 0,2 s : mouvement regulier (elle se recule) sans fausse alerte', not doc.get('fallback'),
             (doc.get('fallback'), q.get('scores')))
    try:
        doc = detourage.cutout(src, 1.0, 1.04, 30)
        verifier('plage tres courte (0,04 s) : 1 image', doc.get('count') in (1, 2), doc.get('count'))
    except Exception as e:
        verifier('plage tres courte (0,04 s) : 1 image', False, repr(e))
    try:
        doc = detourage.cutout(src, 1.5, 2.6, 30)  # fin au-dela du fichier (2 s)
        verifier('plage au-dela de la fin : images existantes', 10 <= doc.get('count', 0) <= 16, doc.get('count'))
    except Exception as e:
        verifier('plage au-dela de la fin : images existantes', False, repr(e))


def cas_faux_positifs(detourage, reel_v1):
    for c in reel_v1['clips']:
        if c['id'] == 'c3':
            continue
        s = reel_v1['sources'][c['source']]
        a = round(c['in'] + 1.0, 2)
        src = extrait(f"v1-{c['id']}", VRAI / s['proxy'], a - 1.0, 4.0)
        doc, q = lancer(detourage, f"v1-{c['id']}", src, 1.0, 4.0, sujet_decale(s['samples'], a - 1.0))
        verifier(f"Video 1 {c['id']} : pas de repli", not doc.get('fallback') and doc.get('score', 0) > 0.8,
                 (doc.get('score'), doc.get('fallback'), q.get('score_min')))


def cas_prepare(detourage):
    """Tech 3D cinematique (aussi applique par le montage automatique) : un plan sous un autre angle ou un media
    illisible garde sa prise d'origine sans faire echouer le style ; Editorial garde son erreur d'origine."""
    reel = {'fps': 30, 'design': {'mode': 'produit', 'cinematic': True},
            'sources': {'a': {'proxy': 'media/debut-fichier.mp4'}, 'b': {'proxy': 'media/absent.mp4'}},
            'clips': [{'id': 'bon', 'source': 'a', 'in': 0.5, 'out': 1.0},
                      {'id': 'angle', 'source': 'a', 'angle': 'b', 'in': 0.5, 'out': 1.0},
                      {'id': 'illisible', 'source': 'b', 'in': 0.0, 'out': 0.5}]}
    try:
        detourage.prepare(reel)
        ok = sorted(reel['cutouts']) == ['bon'] and reel['cutouts']['bon']['count'] == 15
        verifier('prepare Tech 3D : plans impossibles ignores, le bon plan detoure', ok, sorted(reel['cutouts']))
    except Exception as e:
        verifier('prepare Tech 3D : plans impossibles ignores, le bon plan detoure', False, repr(e))
    reel['design'] = {'mode': 'editorial'}
    try:
        detourage.prepare(reel)
        verifier('prepare Editorial : erreur d origine sur un autre angle', False, 'aucune erreur')
    except ValueError as e:
        verifier('prepare Editorial : erreur d origine sur un autre angle', 'angle' in str(e), str(e))


def cas_panne(detourage):
    """Carte graphique en panne pendant le calcul (pilote, carte non prise en charge) : RVM sur le processeur,
    pas l'ancien MediaPipe ; memoire graphique rendue."""
    from editeur import detourage_rvm as rvm
    vrai_run = rvm.Matteur.run

    def run_panne(self, *a, **k):
        if self.appareil == 'cuda':
            raise RuntimeError('CUDA error: no kernel image is available for execution on the device (simulation)')
        return vrai_run(self, *a, **k)
    rvm.Matteur.run = run_panne
    try:
        doc = detourage.cutout(BAC / 'media' / 'debut-fichier.mp4', 1.2, 1.5, 30)
    finally:
        rvm.Matteur.run = vrai_run
    verifier('panne carte graphique : RVM sur le processeur', doc.get('engine') == 'rvm-mobilenetv3' and doc.get('width') == 720
             and doc.get('count') == 9, {k: doc.get(k) for k in ('engine', 'width', 'count')})


def cas_processeur():
    """Sans carte graphique : processus separe (CUDA_VISIBLE_DEVICES vide), plage propre a ce cas (pas de cache)."""
    code = ('import sys,json,time;sys.path.insert(0,r"%s");from editeur import detourage;'
            't=time.perf_counter();d=detourage.cutout(r"%s",0.6,1.1,30);'
            'print("JSON"+json.dumps({"doc":d,"s":time.perf_counter()-t}))') % (VRAI / 'engine', BAC / 'media' / 'debut-fichier.mp4')
    env = {**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'EDITEUR_ROOT': str(BAC)}
    r = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    ligne = [x for x in r.stdout.splitlines() if x.startswith('JSON')]
    if not ligne:
        verifier('processeur : detourage sans carte graphique', False, r.stderr[-800:])
        return
    out = json.loads(ligne[-1][4:])
    q = json.loads((BAC / out['doc']['quality']).read_text(encoding='utf-8')) if out['doc'].get('quality') else {}
    verifier('processeur : detourage RVM sans carte graphique, en 720x1280', out['doc'].get('engine', '').startswith('rvm') and
             out['doc']['count'] == 15 and out['doc']['width'] == 720,
             f"{out['doc'].get('engine')} {q.get('appareil')} {out['s']:.1f} s pour 15 images, {q.get('vitesse_ms_image')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cas', default='nuit,foule,paysage,deux,bords,faux,prepare,panne,processeur')
    ap.add_argument('--refaire', action='store_true', help='efface les detourages du bac (pas les extraits)')
    args = ap.parse_args()
    preparer_bac()
    PREUVES.mkdir(parents=True, exist_ok=True)
    if args.refaire:
        for p in (BAC / 'assets/detourage').iterdir():
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    os.environ['EDITEUR_ROOT'] = str(BAC)
    sys.path.insert(0, str(VRAI / 'engine'))
    from editeur import detourage
    assert detourage.ROOT == BAC, 'le moteur doit ecrire dans le bac a sable'
    v1 = json.loads((VRAI / 'projects/script1/reels/script.json').read_text(encoding='utf-8'))  # lecture seule
    bingo = json.loads((VRAI / 'projects/scriptbingonightvideo1/reels/v1.json').read_text(encoding='utf-8'))  # lecture seule
    cas = args.cas.split(',')
    with detourage.session():
        if 'nuit' in cas:
            cas_nuit(detourage)
        if 'foule' in cas:
            cas_foule(detourage, bingo)
        if 'paysage' in cas:
            cas_paysage(detourage, bingo)
        if 'deux' in cas:
            cas_deux(detourage, v1)
        if 'bords' in cas:
            cas_bords(detourage, v1)
        if 'faux' in cas:
            cas_faux_positifs(detourage, v1)
        if 'prepare' in cas:
            cas_prepare(detourage)
    if 'panne' in cas:  # hors session : le modele de la carte graphique est deja rendu
        cas_panne(detourage)
    import torch
    if torch.cuda.is_available():
        verifier('memoire graphique rendue', torch.cuda.memory_allocated() == 0 and torch.cuda.memory_reserved() == 0,
                 f'{torch.cuda.memory_allocated()} / {torch.cuda.memory_reserved()} octets')
    if 'processeur' in cas:
        cas_processeur()
    ok = sum(r for _, r in RESULTATS)
    print(f'{ok}/{len(RESULTATS)} verifications reussies')
    return 0 if ok == len(RESULTATS) else 1


if __name__ == '__main__':
    sys.exit(main())
