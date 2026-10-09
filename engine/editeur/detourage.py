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

VERSION = 'v8-rvm-bords'          # nouvelle cle : anciens masques MediaPipe (v3) et premiers essais RVM (v4) regeneres
                                  # (v5 : deux personnes gardees, couleur des bords du corps, score sans fausse alerte ;
                                  # v6-v8, 2 oct. 2026 : bord pris sur un decor clair recalcule par la couleur, doigts flous
                                  # plus opaques, or des boucles d'oreilles garde ; detourage_rvm._fond_clair / _mains)
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


SCENE_VERSION = 6  # 6 : haut reel de la tete et largeur du visage (head)


def _alphas(doc, pas=3, taille=(270, 480)):
    """Alpha (0-1, taille reduite) d'une image sur `pas` du detourage, avec son indice."""
    import cv2
    import numpy as np
    folder = ROOT / (doc.get('frames') or '')
    files = sorted(folder.glob('*.webp')) if doc.get('frames') else []
    for i, f in enumerate(files):
        if i % pas:
            continue
        im = cv2.imdecode(np.fromfile(str(f), np.uint8), cv2.IMREAD_UNCHANGED)
        if im is None or im.ndim < 3 or im.shape[2] < 4:
            continue
        yield i, cv2.resize(im[:, :, 3], taille, interpolation=cv2.INTER_AREA).astype(np.float32) / 255, im


def _coin(w, h, x0, y0, nx, ny):
    """Rectangle de l'image coupe par la droite (x0, y0, normale nx, ny), du cote ou la normale pointe (Sutherland-Hodgman)."""
    rect = [(0, 0), (w, 0), (w, h), (0, h)]
    side = lambda p: (p[0] - x0) * nx + (p[1] - y0) * ny
    poly = []
    for i, p in enumerate(rect):
        q = rect[(i + 1) % 4]
        sp, sq = side(p), side(q)
        if sp >= 0:
            poly.append(p)
        if sp * sq < 0:
            k = sp / (sp - sq)
            poly.append((p[0] + (q[0] - p[0]) * k, p[1] + (q[1] - p[1]) * k))
    return poly


def occultant(presence):
    """Objet fixe du decor d'origine qui cachait une partie de la personne (table du bureau au premier plan). Signature dans
    la carte de presence (part des images ou la personne occupe chaque pixel) : une DROITE NETTE en bas de l'image, le corps
    toujours present jusqu'a elle (>= 0,85) et presque jamais au-dela (<= 0,35 : une main posee un instant est permise),
    oblique (20 a 72 degres : ni le cote vertical d'un buste, ni l'epaule), qui ferme un COIN du bas de l'image. Un bord du
    corps qui bouge est flou dans cette carte ; un bras coupe par la table, lui, s'arrete toujours sur la meme droite.
    Essai ecarte (2 oct. 2026) : chercher la droite dans l'image mediane de la prise quand la presence ne la montre pas
    trouvait le pied d'une chaise plutot que la table ; une prise sans droite nette garde son detourage tel quel.
    -> polygone [[x, y], ...] (0-1, cadre de la prise) du cote de l'objet, ou None. Sans ce cache, le studio montrait un bras
    coupe en diagonale et un coin de bois sous la main."""
    import cv2
    import numpy as np
    P = presence
    h, w = P.shape
    lisse = cv2.GaussianBlur(P, (3, 3), 0)
    gx = cv2.Sobel(lisse, cv2.CV_32F, 1, 0, ksize=3) / 8
    gy = cv2.Sobel(lisse, cv2.CV_32F, 0, 1, ksize=3) / 8
    net = (np.hypot(gx, gy) > 0.07).astype(np.uint8) * 255
    net[: int(h * 0.55)] = 0
    net[:, :3] = net[:, -3:] = 0
    lignes = cv2.HoughLinesP(net, 1, np.pi / 180, threshold=30, minLineLength=int(0.1 * h), maxLineGap=6)
    best = None
    for x0, y0, x1, y1 in (lignes.reshape(-1, 4) if lignes is not None else []):
        ang = abs(np.degrees(np.arctan2(y1 - y0, x1 - x0)))
        ang = min(ang, 180 - ang)
        if not 20 <= ang <= 72:
            continue
        L = float(np.hypot(x1 - x0, y1 - y0))
        nx, ny = -(y1 - y0) / L, (x1 - x0) / L  # normale
        a, b = [], []
        for k in np.linspace(0.05, 0.95, 24):
            x, y = x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
            a.append(P[int(np.clip(y + ny * 6, 0, h - 1)), int(np.clip(x + nx * 6, 0, w - 1))])
            b.append(P[int(np.clip(y - ny * 6, 0, h - 1)), int(np.clip(x - nx * 6, 0, w - 1))])
        ma, mb = float(np.median(a)), float(np.median(b))
        if ma <= 0.35 and mb >= 0.85:
            normale = (nx, ny)  # cote a = objet
        elif mb <= 0.35 and ma >= 0.85:
            normale = (-nx, -ny)
        else:
            continue
        poly = _coin(w, h, x0, y0, *normale)
        if len(poly) < 3 or len(poly) > 4:
            continue
        pts = np.array(poly, np.float32)
        aire = cv2.contourArea(pts) / (w * h)
        masque = np.zeros((h, w), np.uint8)
        cv2.fillPoly(masque, [pts.astype(np.int32)], 1)
        vide = float(P[masque > 0].mean()) if masque.any() else 1.0
        # un coin du bas (il touche le bas ET un cote), petit, presque toujours vide de personne
        bas = pts[:, 1].max() >= h - 1
        cote = pts[:, 0].min() <= 1 or pts[:, 0].max() >= w - 1
        if not (bas and cote) or not 0.01 <= aire <= 0.2 or vide > 0.2 or pts[:, 1].min() < h * 0.5:
            continue
        if best is None or L > best[0]:
            best = (L, poly)
    if not best:
        return None
    return [[round(float(x) / w, 4), round(float(y) / h, 4)] for x, y in best[1]]


def meme_decor(path_a, t_a, path_b, t_b, poly):
    """Deux prises filmees du meme endroit (camera immobile entre elles) : l'objet du polygone (0-1) a la meme image dans
    les deux (ecart moyen des luminances normalisees < 0,08)."""
    import cv2
    import numpy as np
    vues = []
    for path, t in ((path_a, t_a), (path_b, t_b)):
        cap = cv2.VideoCapture(str(path))
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, fr = cap.read()
        cap.release()
        if not ok:
            return False
        vues.append(cv2.cvtColor(cv2.resize(fr, (270, 480), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype(np.float32))
    masque = np.zeros((480, 270), np.uint8)
    cv2.fillPoly(masque, [(np.array(poly) * [270, 480]).astype(np.int32)], 1)
    masque = cv2.erode(masque, np.ones((7, 7), np.uint8))
    if masque.sum() < 200:
        return False
    a, b = vues[0][masque > 0], vues[1][masque > 0]
    return float(np.mean(np.abs(a / max(1.0, a.mean()) - b / max(1.0, b.mean())))) < 0.08


def lumiere(doc, path, src, start, fps):
    """Cote de la lumiere principale sur le visage (fenetre du bureau...) : moitie gauche / droite du visage (pixels de la
    personne) sur quelques images. -> {'side': -1 (vient de la gauche de l'image) | 1, 'k': ecart 0-1} ou None."""
    import cv2
    import numpy as np
    piste = [p for p in (src.get('track') or []) if len(p) >= 4]
    if not piste:  # visage de l'analyse v3 de la prise (boite MediaPipe : centre, largeur en part de la largeur)
        f = ROOT / 'projects/_cache/analysis' / (Path(src.get('proxy') or '').stem + '.analysis.json')
        try:
            piste = [[x['t'], x['face']['cx'], x['face']['cy'], x['face'].get('w', .24)]
                     for x in json.loads(f.read_text(encoding='utf-8')).get('frames') or [] if x.get('face')]
        except (OSError, ValueError, KeyError, TypeError):
            piste = []
    if not piste:
        return None
    cap = cv2.VideoCapture(str(path))
    gauche, droite = [], []
    try:
        for i, a, im in _alphas(doc, pas=24, taille=(270, 480)):
            t = start + i / fps
            proches = [p for p in piste if abs(p[0] - t) <= 0.5]
            if not proches:
                continue
            cx, cy, fw = (float(np.median([p[k] for p in proches])) for k in (1, 2, 3))
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, fr = cap.read()
            if not ok:
                continue
            H, W = fr.shape[:2]
            al = cv2.resize(im[:, :, 3], (W, H), interpolation=cv2.INTER_LINEAR)
            g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY).astype(np.float32)
            x0, x1 = int((cx - fw * 0.42) * W), int((cx + fw * 0.42) * W)
            y0, y1 = int((cy - fw * 0.3 * W / H) * H), int((cy + fw * 0.5 * W / H) * H)
            xm = int(cx * W)
            if x0 < 0 or x1 > W or y0 < 0 or y1 > H or x1 - x0 < 20:
                continue
            zl, zr = (al[y0:y1, x0:xm] > 200), (al[y0:y1, xm:x1] > 200)
            if zl.sum() < 50 or zr.sum() < 50:
                continue
            gauche.append(float(g[y0:y1, x0:xm][zl].mean()))
            droite.append(float(g[y0:y1, xm:x1][zr].mean()))
    finally:
        cap.release()
    if len(gauche) < 2:
        return None
    L, R = float(np.median(gauche)), float(np.median(droite))
    return {'side': -1 if L >= R else 1, 'k': round(abs(L - R) / max(1.0, L, R), 3)}


def _visages(src):
    """Visage de la prise [[t, cx, cy, w]] (part de l'image) : piste de recadrage, sinon boites de l'analyse v3 de la prise."""
    piste = [p[:4] for p in (src.get('track') or []) if len(p) >= 4]
    if piste:
        return piste
    f = ROOT / 'projects/_cache/analysis' / (Path(src.get('proxy') or '').stem + '.analysis.json')
    try:
        return [[x['t'], x['face']['cx'], x['face']['cy'], x['face'].get('w', .24)]
                for x in json.loads(f.read_text(encoding='utf-8')).get('frames') or [] if x.get('face')]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def tete(doc, src, start, fps):
    """Haut REEL de la tete (cheveux compris) dans la prise, lu dans l'alpha du detourage, et largeur du visage (boite de
    l'analyse, mediane sur 0,8 s : une fausse detection isolee ne compte pas) : [[t de la prise, y 0-1, largeur 0-1], ...]
    toutes les 0,1 s, lisse (mediane sur 0,5 s). Colonne du visage seulement (+- 0,35 largeur de visage : une main levee a
    cote ne compte pas). L'estimation d'avant (centre du visage - 1,1 largeur de visage, largeur par defaut 25 %) placait la
    tete jusqu'a 5 % de l'image trop haut : la camera du studio reculait ou descendait la personne pour rien (appel final
    filme trop large, juge n° 2 du 2 oct. 2026). None si le visage n'est pas connu."""
    import numpy as np
    vis = _visages(src)
    if not vis:
        return None
    pts = []
    for i, a, _ in _alphas(doc, pas=3, taille=(270, 480)):
        t = start + i / fps
        proches = [p for p in vis if abs(p[0] - t) <= 0.4]
        if not proches:
            continue
        cx, fw = float(np.median([p[1] for p in proches])), float(np.median([p[3] for p in proches]))
        h, w = a.shape
        x0, x1 = int(max(0, (cx - fw * .35) * w)), int(min(w, (cx + fw * .35) * w))
        if x1 - x0 < 4:
            continue
        lignes = np.where((a[:, x0:x1] > .5).mean(axis=1) >= .3)[0]
        if len(lignes):
            pts.append([round(t, 2), float(lignes[0]) / h, fw])
    if len(pts) < 3:
        return None
    ys = [p[1] for p in pts]
    return [[t, round(float(np.median(ys[max(0, k - 2):k + 3])), 4), round(fw, 4)] for k, (t, _, fw) in enumerate(pts)]


def scene(doc, path, src, start, fps):
    """Ce que le studio doit savoir du decor d'origine d'un plan detoure : lumiere principale, objet fixe qui cachait la
    personne et haut reel de la tete (cache scene.json dans le dossier du detourage). Jamais bloquant."""
    folder = ROOT / (doc.get('frames') or '')
    if not doc.get('frames') or not folder.is_dir():
        return {}
    cache = folder / 'scene.json'
    try:
        old = json.loads(cache.read_text(encoding='utf-8'))
        if old.get('version') == SCENE_VERSION:
            return {k: v for k, v in old.items() if k != 'version' and v}
    except (OSError, ValueError):
        pass
    import numpy as np
    out = {'version': SCENE_VERSION, 'light': None, 'occluder': None, 'head': None}
    try:
        acc, n = None, 0
        for _, a, _ in _alphas(doc):
            acc = (a > 0.5).astype(np.float32) if acc is None else acc + (a > 0.5)
            n += 1
        if n >= 8:
            out['occluder'] = occultant(acc / n)
        out['light'] = lumiere(doc, path, src, start, fps)
    except Exception as e:  # analyse en plus : le detourage reste utilisable
        from .detourage_rvm import journal
        journal(f'Analyse du décor du détourage impossible ({e}).')
    try:
        out['head'] = tete(doc, src, start, fps)
    except Exception as e:
        from .detourage_rvm import journal
        journal(f'Haut de la tête non mesuré dans le détourage ({e}).')
    try:
        cache.write_text(json.dumps(out), encoding='utf-8')
    except OSError:
        pass
    return {k: v for k, v in out.items() if k != 'version' and v}


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
                doc = cutout(path, c['in'], c['out'], reel['fps'], _sujet(src))
                # studio : lumiere principale et objet fixe du decor d'origine (table au premier plan), pour l'integration
                info = scene(doc, path, src, c['in'], reel['fps']) if doc.get('engine') else {}
                reel['cutouts'][c['id']] = {**doc, **info, 'source': c['source'], 'proxy': src['proxy']}
            except Exception as e:
                if bloquant:
                    raise
                journal(f"Détourage du plan {c['id']} impossible ({e}) : prise d'origine gardée.")
    try:
        _propager_occultants(reel)
    except Exception as e:  # analyse en plus : jamais bloquant
        journal(f'Objet du décor non reporté entre les prises ({e}).')


def _presence(doc):
    import numpy as np
    acc, n = None, 0
    for _, a, _ in _alphas(doc):
        acc = (a > 0.5).astype(np.float32) if acc is None else acc + (a > 0.5)
        n += 1
    return acc / n if n else None


def _propager_occultants(reel):
    """Meme decor (camera immobile entre les prises) : la table vue nettement dans une prise cache aussi le bras dans les
    autres, ou elle n'apparait pas nettement dans la carte de presence (bras qui bouge beaucoup). Gardee seulement si la
    personne n'occupe presque jamais ce coin dans la prise (<= 0,3 en moyenne)."""
    import cv2
    import numpy as np
    from . import montage
    cuts = reel.get('cutouts') or {}
    avec = [(cid, d) for cid, d in cuts.items() if d.get('occluder')]
    for cid, d in cuts.items():
        if d.get('occluder') or not d.get('engine') or not avec:
            continue
        src = reel['sources'].get(d.get('source')) or {}
        for oid, od in avec:
            osrc = reel['sources'].get(od.get('source')) or {}
            ta = [d['start'] + 0.3, (d['start'] + d['end']) / 2, d['end'] - 0.3]
            tb = [od['start'] + 0.3, (od['start'] + od['end']) / 2, od['end'] - 0.3]
            pa, pb = montage.proxy_path(src), montage.proxy_path(osrc)
            if sum(meme_decor(pa, x, pb, y, od['occluder']) for x, y in zip(ta, tb)) < 2:
                continue
            P = _presence(d)
            if P is None:
                break
            masque = np.zeros(P.shape, np.uint8)
            cv2.fillPoly(masque, [(np.array(od['occluder']) * [P.shape[1], P.shape[0]]).astype(np.int32)], 1)
            if masque.any() and float(P[masque > 0].mean()) <= 0.3:
                d['occluder'] = od['occluder']
                d['occluderFrom'] = oid
            break
    # camera deplacee entre les prises (decor different a l'image) : la table d'une autre prise est reprise si CETTE prise
    # montre, image par image, des coupes droites de la personne sur la meme droite (bras pose derriere la table). Juge n° 2
    # (2 oct. 2026) : a 0:41,67, l'avant-bras de la prise c4 restait coupe en pointe pendant 4 images.
    avec = [(cid, d) for cid, d in cuts.items() if d.get('occluder') and not d.get('occluderFrom')]
    for cid, d in cuts.items():
        if d.get('occluder') or not d.get('engine') or not avec:
            continue
        for oid, od in avec:
            trouve = occultant_confirme(d, od['occluder'])
            if trouve:
                d['occluder'] = trouve['poly']
                d['occluderFrom'] = oid
                if trouve.get('track'):
                    d['occluderTrack'] = trouve['track']
                break


def _bord_libre(poly):
    """Cote du polygone d'un occultant qui n'est pas sur le bord de l'image (le bord de la table) -> ((x0, y0), (x1, y1))."""
    for i, a in enumerate(poly):
        b = poly[(i + 1) % len(poly)]
        if not ((a[0] <= .002 and b[0] <= .002) or (a[0] >= .998 and b[0] >= .998) or (a[1] >= .998 and b[1] >= .998)
                or (a[1] <= .002 and b[1] <= .002)):
            return a, b
    return None


def coupes_droites(doc, pas=3, taille=(270, 480)):
    """Droites ou la personne s'arrete NET dans une image (corps d'un cote > 0,85, vide de l'autre < 0,1), dans la moitie
    basse, obliques (20 a 72 degres) -> ([(x0, y0, x1, y1, indice de l'image)] en pixels de `taille`, carte de presence,
    nombre d'images lues)."""
    import cv2
    import numpy as np
    out, pres, n = [], None, 0
    for i, a, _ in _alphas(doc, pas=pas, taille=taille):
        h, w = a.shape
        b = (a > .5).astype(np.uint8)
        pres = b.astype(np.float32) if pres is None else pres + b
        n += 1
        e = cv2.Canny(b * 255, 50, 150)
        e[: int(h * .5)] = 0
        e[:, :2] = 0
        e[:, -2:] = 0
        e[-2:] = 0
        L = cv2.HoughLinesP(e, 1, np.pi / 180, threshold=18, minLineLength=int(.06 * h), maxLineGap=4)
        for x0, y0, x1, y1 in (L.reshape(-1, 4) if L is not None else []):
            ang = abs(np.degrees(np.arctan2(y1 - y0, x1 - x0))) % 180
            if not 20 <= min(ang, 180 - ang) <= 72:
                continue
            ln = float(np.hypot(x1 - x0, y1 - y0))
            nx, ny = -(y1 - y0) / ln, (x1 - x0) / ln
            pa, pb = [], []
            for k in np.linspace(.1, .9, 9):
                x, y = x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
                pa.append(a[int(np.clip(y + ny * 4, 0, h - 1)), int(np.clip(x + nx * 4, 0, w - 1))])
                pb.append(a[int(np.clip(y - ny * 4, 0, h - 1)), int(np.clip(x - nx * 4, 0, w - 1))])
            ma, mb = float(np.median(pa)), float(np.median(pb))
            if (ma > .85 and mb < .1) or (mb > .85 and ma < .1):
                out.append((int(x0), int(y0), int(x1), int(y1), i))
    return out, (pres / n if n else None), n


def occultant_confirme(doc, poly, taille=(270, 480)):
    """Table d'une autre prise (polygone 0-1) reprise dans celle-ci : la personne y est coupee net sur une droite proche du
    bord de cette table (angle <= 6 degres, ecart <= 7 % de la hauteur au milieu du bord : la camera d'un telephone derive)
    dans au moins 4 images (et 3 % des images), et presque jamais dans le coin de la table (presence <= 0,3).
    -> {'poly': coin de la coupe mediane (0-1), 'track': [[t, a, b], ...] bord image par image} ou None."""
    import cv2
    import numpy as np
    w, h = taille
    bord = _bord_libre(poly)
    if not bord:
        return None
    lignes, P, total = coupes_droites(doc, taille=taille)
    if P is None or not lignes:
        return None
    (ax, ay), (bx, by) = [(p[0] * w, p[1] * h) for p in bord]
    ang0 = np.degrees(np.arctan2(by - ay, bx - ax)) % 180
    mx, my = (ax + bx) / 2, (ay + by) / 2
    ln0 = float(np.hypot(bx - ax, by - ay)) or 1.0
    n0x, n0y = -(by - ay) / ln0, (bx - ax) / ln0
    cx, cy = float(np.mean([p[0] for p in poly])) * w, float(np.mean([p[1] for p in poly])) * h
    if (cx - mx) * n0x + (cy - my) * n0y < 0:  # normale du bord orientee vers la table
        n0x, n0y = -n0x, -n0y
    proches = []
    for x0, y0, x1, y1, i in lignes:
        ang = np.degrees(np.arctan2(y1 - y0, x1 - x0)) % 180
        if min(abs(ang - ang0), 180 - abs(ang - ang0)) > 6:
            continue
        ln = float(np.hypot(x1 - x0, y1 - y0))
        nx, ny = -(y1 - y0) / ln, (x1 - x0) / ln
        if abs((mx - x0) * nx + (my - y0) * ny) <= .07 * h:  # ecart des deux droites au milieu du bord de la table
            # position le long de la normale (negatif : du cote de la personne) au milieu du bord
            proj = (x0 + (x1 - x0) * ((mx - x0) * (x1 - x0) + (my - y0) * (y1 - y0)) / ln ** 2 - mx) * n0x \
                + (y0 + (y1 - y0) * ((mx - x0) * (x1 - x0) + (my - y0) * (y1 - y0)) / ln ** 2 - my) * n0y
            proches.append((proj, x0, y0, x1, y1, i))
    if len({p[5] for p in proches}) < max(4, .03 * total):
        return None

    def coin_de(x0, y0, x1, y1):
        ln = float(np.hypot(x1 - x0, y1 - y0))
        nx, ny = -(y1 - y0) / ln, (x1 - x0) / ln
        if nx * n0x + ny * n0y < 0:
            nx, ny = -nx, -ny
        return _coin(w, h, x0, y0, nx, ny)

    def libres(coin):
        """Sommets du coin qui ne sont pas des coins de l'image (les deux bouts du bord de la table)."""
        return [p for p in coin if not ((p[0] <= .5 or p[0] >= w - .5) and (p[1] <= .5 or p[1] >= h - .5))]

    # bord retenu pour l'image fixe : la coupe mediane (la table la plupart du temps)
    _, x0, y0, x1, y1, _ = sorted(proches, key=lambda p: p[0])[len(proches) // 2]
    coin = coin_de(x0, y0, x1, y1)
    if not 3 <= len(coin) <= 4 or len(libres(coin)) != 2:
        return None
    pts = np.array(coin, np.float32)
    masque = np.zeros((h, w), np.uint8)
    cv2.fillPoly(masque, [pts.astype(np.int32)], 1)
    aire = cv2.contourArea(pts) / (w * h)
    bas = pts[:, 1].max() >= h - 1
    cote = pts[:, 0].min() <= 1 or pts[:, 0].max() >= w - 1
    if not (bas and cote) or not .01 <= aire <= .2 or pts[:, 1].min() < h * .5 or float(P[masque > 0].mean()) > .3:
        return None
    poly = [[round(float(x) / w, 4), round(float(y) / h, 4)] for x, y in coin]
    # la camera d'un telephone derive : la coupe bouge d'une image a l'autre. Piste [t de la prise, a, b] : coordonnee libre
    # (sur le bord de l'image) de chaque bout du bord de la table, image par image (coupe la plus avancee de l'image),
    # lissee ; le studio y pose le bureau a chaque instant (sinon le bras restait coupe en pointe la ou la coupe change).
    ref = libres(coin)
    axes = [0 if min(p[0], w - p[0]) <= .5 else 1 for p in ref]  # 0 : sur un bord vertical (y libre), 1 : en bas/haut (x libre)
    piste = {}
    for i in sorted({p[5] for p in proches}):
        _, a0, b0, a1, b1, _ = min((p for p in proches if p[5] == i), key=lambda p: p[0])
        c = coin_de(a0, b0, a1, b1)
        lib = libres(c)
        if len(c) != len(coin) or len(lib) != 2:
            continue
        lib = sorted(lib, key=lambda p: min(np.hypot(p[0] - ref[0][0], p[1] - ref[0][1]), 1e9))
        piste[i] = [lib[0][1 - axes[0]] / (h if axes[0] == 0 else w), lib[1][1 - axes[1]] / (h if axes[1] == 0 else w)]
    if len(piste) >= 4:
        ks = sorted(piste)
        track = []
        for j, i in enumerate(ks):
            voisins = [piste[ks[m]] for m in range(max(0, j - 2), min(len(ks), j + 3))]
            track.append([round(doc['start'] + i / (doc.get('fps') or 30), 3),
                          round(float(np.median([v[0] for v in voisins])), 4), round(float(np.median([v[1] for v in voisins])), 4)])
        return {'poly': poly, 'track': track}
    return {'poly': poly}
