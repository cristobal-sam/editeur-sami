"""Analyse image et son d'une prise : orientation, visage, nettete, niveaux audio. Resultat en cache."""
import json
from pathlib import Path

import numpy as np

from .media import ROOT, cache_name, decode_audio, file_key, probe, sample_frames

FACE_MODEL = ROOT / 'models/mediapipe/blaze_face_short_range.tflite'
LANDMARK_MODEL = ROOT / 'models/mediapipe/face_landmarker.task'
VERSION = 3  # a incrementer quand le contenu de l'analyse change (invalide le cache)
_detector = None
_landmarker = None

# Expressions du visage (blendshapes MediaPipe) qui traduisent un jeu vivant
EXPRESSIVE = ('browInnerUp', 'browOuterUpLeft', 'browOuterUpRight', 'mouthSmileLeft', 'mouthSmileRight',
              'eyeWideLeft', 'eyeWideRight', 'cheekSquintLeft', 'cheekSquintRight', 'mouthPressLeft', 'mouthPressRight')
GAZE = ('eyeLookOutLeft', 'eyeLookOutRight', 'eyeLookInLeft', 'eyeLookInRight',
        'eyeLookUpLeft', 'eyeLookUpRight', 'eyeLookDownLeft', 'eyeLookDownRight')


def _landmarks():
    global _landmarker
    if _landmarker is None:
        from mediapipe.tasks.python import BaseOptions, vision
        _landmarker = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(LANDMARK_MODEL)), output_face_blendshapes=True, num_faces=1))
    return _landmarker


def performance(rgb):
    """Jeu d'acteur sur une image : expressivite, regard hors camera, clignement (0..1), ou None."""
    import mediapipe as mp
    res = _landmarks().detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
    if not res.face_blendshapes:
        return None
    b = {c.category_name: c.score for c in res.face_blendshapes[0]}
    return {'expr': round(float(np.mean([b.get(k, 0) for k in EXPRESSIVE])), 3),
            'gaze_off': round(float(max(b.get(k, 0) for k in GAZE)), 3),
            'blink': round((b.get('eyeBlinkLeft', 0) + b.get('eyeBlinkRight', 0)) / 2, 3)}


def face_color(rgb, face):
    """Couleur moyenne du centre du visage (R, G, B 0..255) : base de l'harmonisation des prises."""
    if not face:
        return None
    h, w = rgb.shape[:2]
    x0, x1 = int((face['cx'] - face['w'] * 0.3) * w), int((face['cx'] + face['w'] * 0.3) * w)
    y0, y1 = int((face['cy'] - face['h'] * 0.3) * h), int((face['cy'] + face['h'] * 0.3) * h)
    patch = rgb[max(0, y0):max(1, y1), max(0, x0):max(1, x1)].reshape(-1, 3)
    return [round(float(v), 1) for v in patch.mean(axis=0)] if len(patch) else None


def _faces():
    global _detector
    if _detector is None:
        from mediapipe.tasks.python import BaseOptions, vision
        _detector = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=str(FACE_MODEL)), min_detection_confidence=0.5))
    return _detector


def detect_face(rgb):
    """Visage le plus grand : {'cx','cy','w','h','score'} en fractions de l'image, ou None."""
    import mediapipe as mp
    res = _faces().detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
    if not res.detections:
        return None
    h, w = rgb.shape[:2]
    d = max(res.detections, key=lambda d: d.bounding_box.width * d.bounding_box.height)
    b = d.bounding_box
    return {'cx': (b.origin_x + b.width / 2) / w, 'cy': (b.origin_y + b.height / 2) / h,
            'w': b.width / w, 'h': b.height / h, 'score': round(d.categories[0].score, 3)}


ROTATION_RULE = 2  # version de la regle ci-dessous (les analyses tournees avec l'ancienne regle sont refaites)


def detect_rotation(path, duration):
    """Rotation (0/90/180/270) qui donne un visage droit ; certains telephones enregistrent couche sans le dire.
    Le detecteur donne des scores moyens (0,5-0,75) meme pour un visage de travers et environ 0,9 a l'endroit : on ne
    tourne que si une orientation est NETTEMENT meilleure que l'image telle quelle (moyenne >= 0,75, au moins 3 visages
    tres nets sur 5, +0,12 sur l'image droite). Une fausse detection isolee ne fait plus tourner une prise horizontale."""
    times = [duration * f for f in (0.2, 0.35, 0.5, 0.65, 0.8)]
    scores = {}
    for rot in (0, 90, 270, 180):
        row = []
        for t in times:
            frames = sample_frames(path, fps=1, width=360, rotate=rot, start=t, duration=0.9)
            face = frames and detect_face(frames[0][1])
            row.append(face['score'] if face else 0.0)
        scores[rot] = row
    # vote image par image (les images sans visage ne comptent pas) : l'orientation au visage le plus net, si elle
    # bat l'image droite ; il faut au moins 2 votes, plus que l'image droite, et des visages nets (180 : plus exigeant)
    votes, won = {}, {}
    for k in range(len(times)):
        col = {r: scores[r][k] for r in scores}
        r = max(col, key=col.get)
        if col[r] < 0.6:
            continue
        if r != 0 and col[r] - col[0] < 0.06:
            r = 0
        votes[r] = votes.get(r, 0) + 1
        won.setdefault(r, []).append(col[r])
    best = max((90, 270, 180), key=lambda r: votes.get(r, 0))
    n = votes.get(best, 0)
    if n >= 2 and n > votes.get(0, 0) and sum(won[best]) / n >= (0.8 if best == 180 else 0.72):
        return best
    return 0


def _sharpness(rgb):
    import cv2
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _clip_events(path, n_windows):
    """Ecretages reels (>= 3 echantillons consecutifs au maximum) par fenetre de 100 ms, a 48 kHz."""
    from .media import FFMPEG, run
    if n_windows <= 0 or not probe(path)['has_audio']:
        return [0] * max(0, n_windows)
    raw = run([FFMPEG, '-v', 'error', '-i', str(path), '-vn', '-af', 'pan=mono|c0=c0', '-ar', '48000',
               '-f', 's16le', '-']).stdout
    clipped = (np.abs(np.frombuffer(raw, np.int16).astype(np.int32)) >= 32700).astype(np.int8)
    edges = np.diff(np.concatenate([[0], clipped, [0]]))
    starts, ends = np.where(edges == 1)[0], np.where(edges == -1)[0]
    counts = np.zeros(n_windows, dtype=int)
    for s in starts[(ends - starts) >= 3]:
        counts[min(n_windows - 1, s // 4800)] += 1
    return counts.tolist()


def analyze(path, cache_dir):
    cache = Path(cache_dir) / f'{cache_name(path)}.analysis.json'
    key = file_key(path)
    if cache.exists():
        data = json.loads(cache.read_text(encoding='utf-8'))
        if data.get('key') == key and data.get('version') == VERSION:
            if not data.get('rotate') or data.get('rotv') == ROTATION_RULE:
                return data
            # prise tournee par l'ancienne regle : on ne re-verifie que la rotation ; si elle ne change pas, l'analyse reste
            if detect_rotation(path, data['probe']['duration']) == data['rotate']:
                data['rotv'] = ROTATION_RULE
                cache.write_text(json.dumps(data), encoding='utf-8')
                return data
    info = probe(path)
    rotate = detect_rotation(path, info['duration'])
    frames = []
    for t, rgb in sample_frames(path, fps=4, width=360, rotate=rotate):
        face = detect_face(rgb)
        frames.append({'t': round(t, 3), 'face': face, 'sharp': round(_sharpness(rgb), 1),
                       'jeu': performance(rgb) if face else None, 'color': face_color(rgb, face),
                       'luma': round(float(rgb.mean()), 1)})
    audio = decode_audio(path, sr=16000)
    win = 1600  # 100 ms
    blocks = audio[:len(audio) // win * win].reshape(-1, win)
    rms = 20 * np.log10(np.sqrt((blocks ** 2).mean(axis=1)) + 1e-9)
    data = {'key': key, 'version': VERSION, 'rotv': ROTATION_RULE, 'source': str(path), 'probe': info, 'rotate': rotate,
            'frames': frames, 'audio': {'step': 0.1, 'rms_db': np.round(rms, 1).tolist(),
                                        'clip_events': _clip_events(path, len(rms))}}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data), encoding='utf-8')
    return data


def window_metrics(analysis, start, end):
    """Qualite image/son entre deux instants de la prise."""
    fr = [f for f in analysis['frames'] if start <= f['t'] <= end] or analysis['frames']
    faces = [f['face'] for f in fr if f['face']]
    a = analysis['audio']
    i0, i1 = int(start / a['step']), max(int(end / a['step']), int(start / a['step']) + 1)
    rms = np.array(a['rms_db'][i0:i1] or [-90.0])
    jeu = [f['jeu'] for f in fr if f.get('jeu')]
    voiced = rms[rms > -40]
    # Regard : compare a la position habituelle dans la prise (camera un peu plus haute ou plus basse que les yeux)
    habit = np.median([f['jeu']['gaze_off'] for f in analysis['frames'] if f.get('jeu')] or [0.3])
    return {'expressivity': float(np.mean([j['expr'] for j in jeu])) if jeu else 0.0,
            'gaze_on': float(np.mean([j['gaze_off'] < habit + 0.2 and j['blink'] < 0.6 for j in jeu])) if jeu else 0.0,
            'blinks': float(np.mean([j['blink'] > 0.5 for j in jeu])) if jeu else 0.0,
            'voice_energy': float(np.std(voiced)) if len(voiced) > 3 else 0.0,
            'face_ratio': len(faces) / max(1, len(fr)),
            'face_center': float(np.mean([abs(f['cx'] - 0.5) for f in faces])) if faces else 0.5,
            'sharpness': float(np.median([f['sharp'] for f in fr])),
            'loudness_db': float(np.percentile(rms, 75)),
            'clips_per_s': sum(a['clip_events'][i0:i1]) / max(0.1, end - start)}
