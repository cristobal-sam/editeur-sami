"""Détourage local de la personne, mis en cache pour aperçu ET export ; aucune installation.

Moteur principal : RobustVideoMatting (detourage_rvm.py, carte graphique si possible), alpha pleine resolution,
stable dans le temps. Repli automatique : ancien detourage MediaPipe si RVM est indisponible.
Sortie inchangee pour le lecteur et l'export : assets/detourage/<cle>/00000.webp... (RGBA) + complete.json,
et dans le reel cutouts[clip] = {file, start, end, width, height, frames, fps, count, source, proxy}
plus, avec RVM : engine, score (moyenne 0-1), quality (chemin de qualite.json) et
fallback = [[t0, t1], ...] secondes DANS LA PRISE ou montrer la prise d'origine (decor assombri) plutot que
la personne detouree (voir detourage_rvm.rapport_qualite)."""
import hashlib
import json
import os
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

from .media import ROOT, FFMPEG

VERSION = 'v5-rvm-alpha'          # nouvelle cle : anciens masques MediaPipe (v3) et premiers essais RVM (v4) regeneres
                                  # (v5 : deux personnes gardees, couleur des bords du corps, score sans fausse alerte)
VERSION_MEDIAPIPE = 'v3-alpha-frames'
_MATTEUR = None
_SESSIONS = 0


def preview_frames(doc, fps):
    """Images alpha identiques dans le lecteur et le rendu, sans décodage VP9 matériel."""
    out=ROOT/doc['file']
    folder=out.with_suffix('')
    marker=folder/'complete.json'
    if not marker.exists():
        folder.mkdir(parents=True,exist_ok=True)
        subprocess.run([str(FFMPEG),'-v','error','-y','-c:v','libvpx-vp9','-i',str(out),
                        '-c:v','libwebp','-quality','90','-start_number','0',str(folder/'%05d.webp')],check=True)
        count=len(list(folder.glob('*.webp')))
        if not count:raise RuntimeError('Images détourées absentes.')
        marker.write_text(json.dumps({'count':count}),encoding='utf-8')
    return {**doc,'frames':folder.relative_to(ROOT).as_posix(),'fps':fps,
            'count':json.loads(marker.read_text(encoding='utf-8'))['count']}


def liberer():
    """Rend la memoire de la carte graphique (partagee avec les autres moteurs)."""
    global _MATTEUR
    if _MATTEUR is not None:
        _MATTEUR.close()
        _MATTEUR = None


@contextmanager
def session():
    """Garde le modele charge pendant plusieurs prises ; libere la carte graphique a la sortie."""
    global _SESSIONS
    _SESSIONS += 1
    try:
        yield
    finally:
        _SESSIONS -= 1
        if not _SESSIONS:
            liberer()


def _vider_cache():
    """Memoire graphique des calculs abandonnes (erreur) rendue tout de suite ; le modele charge reste."""
    import gc
    import sys
    torch = sys.modules.get('torch')
    if torch is not None and torch.cuda.is_available() and torch.cuda.device_count():
        gc.collect()
        torch.cuda.empty_cache()


def _matteur():
    global _MATTEUR
    if _MATTEUR is None:
        from .detourage_rvm import Matteur
        force = os.environ.get('EDITEUR_DETOURAGE_MODELE') or None
        try:
            _MATTEUR = Matteur(force)
        except RuntimeError as e:  # memoire graphique pleine : petit modele ; carte graphique en panne : processeur
            plein = 'out of memory' in str(e).lower()
            if not plein and 'cuda' not in str(e).lower():
                raise
            _vider_cache()
            if plein:
                try:
                    _MATTEUR = Matteur('mobilenetv3')
                except RuntimeError:
                    _MATTEUR = None
            if _MATTEUR is None:
                _MATTEUR = Matteur('mobilenetv3', 'cpu')
    return _MATTEUR


def _calculer(path, start, end, fps, subject, folder):
    """Calcul RVM dans <cle>.part puis renommage (jamais de dossier a moitie ecrit). Carte graphique pleine en
    cours de route (autre moteur lance) : nouvel essai avec le petit modele, puis sur le processeur. Autre erreur de
    la carte graphique (pilote, carte non prise en charge) : directement sur le processeur."""
    global _MATTEUR
    from .detourage_rvm import Matteur
    temp = folder.with_name(folder.name + '.part')
    replis = [('mobilenetv3', 'cuda'), ('mobilenetv3', 'cpu')]
    while True:
        if temp.exists():
            shutil.rmtree(temp)  # reste d'un calcul interrompu (dossier temporaire de ce module)
        try:
            rapport = _matteur().run(path, start, end, fps, temp, subject)
            break
        except RuntimeError as e:
            texte = str(e).lower()
            appareil = _MATTEUR.appareil if _MATTEUR else 'cuda'
            plein = 'out of memory' in texte
            if appareil != 'cuda' or not replis or not (plein or 'cuda' in texte):
                raise
            liberer()
            modele, dev = replis.pop(0)
            if dev == 'cuda' and not plein:
                modele, dev = replis.pop(0)
        _vider_cache()  # hors du bloc except : les images du calcul rate ne sont plus retenues
        _MATTEUR = Matteur(modele, dev)
    (temp / 'complete.json').write_text(json.dumps({'count': rapport['count']}), encoding='utf-8')
    if folder.exists():
        shutil.rmtree(folder)
    temp.replace(folder)
    return rapport


def _cle(path, start, end, fps, version):
    return hashlib.sha1(json.dumps([str(path), path.stat().st_mtime_ns, start, end, fps, version]).encode()).hexdigest()[:20]


def cutout(path, start, end, fps=30, subject=None):
    """Personne detouree de la plage [start, end] de la prise. subject = [[t, cx, cy], ...] (visage suivi,
    coordonnees 0-1) pour garder la bonne personne ; facultatif."""
    path = Path(path)
    if os.environ.get('EDITEUR_DETOURAGE_MOTEUR') == 'mediapipe':
        return cutout_mediapipe(path, start, end, fps)
    key = _cle(path, start, end, fps, VERSION)
    folder = ROOT / 'assets' / 'detourage' / key
    meta = folder.with_suffix('.json')
    if meta.exists() and (folder / 'complete.json').exists():
        return json.loads(meta.read_text(encoding='utf-8'))
    from .detourage_rvm import journal
    erreur = None
    try:
        with session():
            rapport = _calculer(path, start, end, fps, subject, folder)
    except Exception as e:  # jamais bloquant : l'ancien detourage reste disponible
        erreur = str(e)
    if erreur is not None:
        _vider_cache()  # la trace de l'erreur ne retient plus d'images sur la carte graphique pendant MediaPipe
        journal(f'Détourage RVM impossible ({erreur}) : ancien détourage utilisé.')
        return cutout_mediapipe(path, start, end, fps)
    rel = folder.relative_to(ROOT).as_posix()
    doc = {'file': rel, 'start': start, 'end': end, 'width': rapport['width'], 'height': rapport['height'],
           'frames': rel, 'fps': fps, 'count': rapport['count'], 'engine': rapport['moteur'],
           'score': rapport['score_moyen'], 'quality': f'{rel}/qualite.json', 'fallback': rapport['repli']}
    meta.write_text(json.dumps(doc), encoding='utf-8')
    return doc


def cutout_mediapipe(path, start, end, fps=30):
    """Ancien detourage (MediaPipe selfie, masque basse resolution) : repli et comparaison seulement."""
    import cv2
    import mediapipe as mp
    import numpy as np
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import ImageSegmenter, ImageSegmenterOptions
    path = Path(path)
    key = _cle(path, start, end, fps, VERSION_MEDIAPIPE)
    out = ROOT / 'assets' / 'detourage' / f'{key}.webm'
    meta = out.with_suffix('.json')
    if out.exists() and meta.exists():
        return preview_frames(json.loads(meta.read_text(encoding='utf-8')),fps)
    out.parent.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(path))
    sw, sh = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    width = min(720, sw) // 2 * 2
    height = round(sh * width / sw / 2) * 2
    options = ImageSegmenterOptions(base_options=BaseOptions(model_asset_path=str(ROOT / 'models/mediapipe/selfie_segmenter.tflite')),
                                   output_category_mask=False, output_confidence_masks=True)
    reader = subprocess.Popen([str(FFMPEG), '-v', 'error', '-ss', str(start), '-t', str(end-start), '-i', str(path),
                               '-vf', f'scale={width}:{height},fps={fps}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    temp = out.with_name(out.stem + '.part.webm')
    writer = subprocess.Popen([str(FFMPEG), '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', f'{width}x{height}',
                               '-r', str(fps), '-i', '-', '-an', '-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p', '-auto-alt-ref', '0',
                               '-b:v', '0', '-crf', '30', '-deadline', 'realtime', '-cpu-used', '6', str(temp)], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        count = 0
        with ImageSegmenter.create_from_options(options) as model:
            while True:
                raw = reader.stdout.read(width*height*3)
                if len(raw) != width*height*3:
                    break
                rgb = np.frombuffer(raw, np.uint8).reshape(height, width, 3)
                result = model.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb.copy()))
                mask = result.confidence_masks[0].numpy_view().copy()
                mask = cv2.GaussianBlur(cv2.resize(mask, (width, height)), (5, 5), 0)
                alpha = np.clip((mask - .15) / .7, 0, 1)
                writer.stdin.write(np.dstack([rgb, (alpha*255).astype(np.uint8)]).tobytes())
                count += 1
        writer.stdin.close()
        if reader.wait() or writer.wait() or not count:
            raise RuntimeError('Le détourage local n’a pas produit de vidéo.')
        temp.replace(out)
        doc = {'file': out.relative_to(ROOT).as_posix(), 'start': start, 'end': end, 'width': width, 'height': height}
        meta.write_text(json.dumps(doc), encoding='utf-8')
        return preview_frames(doc,fps)
    finally:
        if reader.poll() is None:
            reader.terminate()
        if writer.poll() is None:
            writer.terminate()


def _sujet(src):
    """Visage suivi de la prise : piste de recadrage [[t,cx,cy,w]] sinon echantillons [[t,cx,cy,...]]."""
    points = src.get('track') or src.get('samples') or []
    return [[p[0], p[1], p[2]] for p in points if len(p) >= 3]


def needs_cutout(reel):
    """Styles qui affichent la personne detouree : Editorial, Collage, Tech 3D cinematique (studio virtuel)."""
    design = reel.get('design') or {}
    return design.get('mode') in ('editorial', 'collage') or (design.get('mode') == 'produit' and bool(design.get('cinematic')))


def prepare(reel):
    """Detoure chaque plan du reel (plage utilisee seulement). Editorial / Collage : erreur bloquante comme avant.
    Tech 3D cinematique (applique aussi par le montage automatique) : un plan impossible a detourer (autre angle,
    media illisible, plage vide) garde sa prise d'origine, sans faire echouer le style ni le montage."""
    if not needs_cutout(reel):
        return
    from . import montage
    from .detourage_rvm import journal
    bloquant = (reel.get('design') or {}).get('mode') in ('editorial', 'collage')
    reel['cutouts'] = {}
    with session():
        for c in reel['clips']:
            if c.get('angle') and c['angle'] != c['source']:
                if bloquant:
                    raise ValueError('Détourage : utilise la prise principale ou prépare cet angle séparément.')
                journal(f"Détourage : plan {c['id']} filmé sous un autre angle, prise d'origine gardée.")
                continue
            src = reel['sources'][c['source']]
            try:
                path = montage.proxy_path(src)
                reel['cutouts'][c['id']] = {**cutout(path, c['in'], c['out'], reel['fps'], _sujet(src)),
                                           'source': c['source'], 'proxy': src['proxy']}
            except Exception as e:
                if bloquant:
                    raise
                journal(f"Détourage du plan {c['id']} impossible ({e}) : prise d'origine gardée.")
