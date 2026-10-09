"""Recadrage intelligent : piste de la personne qui parle dans une prise (plusieurs intervenants).

Pour chaque image (5 par seconde) : tous les visages (MediaPipe, jusqu'a 4) avec l'ouverture de la bouche.
Les visages sont suivis d'une image a l'autre (position), l'intervenant actif est celui dont la bouche
bouge le plus pendant que le son est voise ; on ne change pas d'intervenant pour un simple « hum »
(maintien minimum). Resultat : [[t, cx, cy, largeur]] lisse, utilise par l'affichage (timeline.ts framing).
Resultat en cache (projects/_cache/analysis/<prise>.cadrage.json)."""
import json
from pathlib import Path

import numpy as np

from .media import ROOT, cache_name, decode_audio, file_key, sample_frames

VERSION = 1
FPS = 5
HOLD = 1.2        # duree minimale sur un intervenant (s)
SWITCH = 0.5      # l'autre doit dominer au moins ce temps pour qu'on change (s)
_marker = None


def _landmarker():
    global _marker
    if _marker is None:
        from mediapipe.tasks.python import BaseOptions, vision
        from .analyze import LANDMARK_MODEL
        _marker = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(LANDMARK_MODEL)), output_face_blendshapes=True, num_faces=4))
    return _marker


def faces(rgb):
    """Tous les visages d'une image : [{'cx','cy','w','jaw'}] en fractions de l'image."""
    import mediapipe as mp
    res = _landmarker().detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
    out = []
    for lm, bs in zip(res.face_landmarks, res.face_blendshapes or [[]] * len(res.face_landmarks)):
        xs = [p.x for p in lm]
        ys = [p.y for p in lm]
        b = {c.category_name: c.score for c in bs}
        out.append({'cx': float(np.mean(xs)), 'cy': float(np.mean(ys)), 'w': float(max(xs) - min(xs)),
                    'jaw': float(b.get('jawOpen', 0.0))})
    return out


def _persons(frames):
    """Suivi simple : chaque visage est rattache a la personne la plus proche (position horizontale)."""
    persons = []  # [{'cx': moyenne, 'pts': {i: face}}]
    for i, fs in enumerate(frames):
        for f in sorted(fs, key=lambda f: -f['w']):
            best = min(persons, key=lambda p: abs(p['cx'] - f['cx']), default=None)
            if best is not None and abs(best['cx'] - f['cx']) < 0.12 and i not in best['pts']:
                best['pts'][i] = f
                best['cx'] = 0.8 * best['cx'] + 0.2 * f['cx']
            else:
                persons.append({'cx': f['cx'], 'pts': {i: f}})
    # on oublie les visages vus trop peu de temps (faux positifs, passants)
    return [p for p in persons if len(p['pts']) >= max(3, len(frames) * 0.1)]


def track(proxy, cache_dir=None):
    """Piste de recadrage d'une prise : [[t, cx, cy, w]] a 5 i/s, ou [] si aucun visage."""
    proxy = Path(proxy)
    cache = Path(cache_dir or ROOT / 'projects/_cache/analysis') / f'{cache_name(proxy)}.cadrage.json'
    key = f'{file_key(proxy)}-{VERSION}'
    if cache.exists():
        data = json.loads(cache.read_text(encoding='utf-8'))
        if data.get('key') == key:
            return data['track']
    sampled = sample_frames(proxy, fps=FPS, width=480)
    frames = [faces(rgb) for _, rgb in sampled]
    times = [round(t, 3) for t, _ in sampled]
    persons = _persons(frames)
    result = []
    if persons:
        n = len(frames)
        audio = decode_audio(proxy, sr=16000)
        hop = 16000 // FPS
        rms = [20 * np.log10(np.sqrt(np.mean(audio[i * hop:(i + 1) * hop] ** 2)) + 1e-9) if i * hop < len(audio) else -90
               for i in range(n)]
        # activite de la bouche : variation de l'ouverture, lissee sur ~0,6 s
        act = np.zeros((len(persons), n))
        for k, p in enumerate(persons):
            jaw = np.array([p['pts'][i]['jaw'] if i in p['pts'] else np.nan for i in range(n)])
            d = np.abs(np.diff(jaw, prepend=jaw[0]))
            d[np.isnan(d)] = 0
            act[k] = np.convolve(d, np.ones(7) / 7, mode='same')  # ~1,4 s centre : bascule juste avant la replique
        cur = int(np.argmax(act[:, :FPS * 2].sum(axis=1))) if n else 0
        since, rival, rival_since = 0.0, None, 0.0
        for i in range(n):
            t = i / FPS
            if rms[i] > -38 and len(persons) > 1:
                best = int(np.argmax(act[:, i]))
                if best != cur and act[best, i] > act[cur, i] * 1.3 + 0.005:
                    if rival != best:
                        rival, rival_since = best, t
                    if t - rival_since >= SWITCH and t - since >= HOLD:
                        cur, since, rival = best, t, None
                else:
                    rival = None
            p = persons[cur]
            # position de l'intervenant : image courante, sinon la plus proche ou il est visible
            near = p['pts'].get(i) or p['pts'][min(p['pts'], key=lambda j: abs(j - i))]
            result.append([times[i], near['cx'], near['cy'], near['w']])
        # lissage (moyenne glissante ~0,8 s) sans melanger deux intervenants
        arr = np.array(result)
        sm = arr.copy()
        for i in range(n):
            j0, j1 = max(0, i - 2), min(n, i + 3)
            same = [j for j in range(j0, j1) if abs(arr[j, 1] - arr[i, 1]) < 0.15]
            sm[i, 1:] = arr[same, 1:].mean(axis=0)
        result = [[round(float(v), 3) for v in row] for row in sm]
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({'key': key, 'persons': len(persons), 'track': result}), encoding='utf-8')
    return result


def speaking(proxy, start, end, cache_dir=None):
    """Activite de parole visible (bouche) entre deux instants d'une prise, 0..1 : sert au choix d'angle multicamera."""
    proxy = Path(proxy)
    cache = Path(cache_dir or ROOT / 'projects/_cache/analysis') / f'{cache_name(proxy)}.bouche.json'
    key = f'{file_key(proxy)}-{VERSION}'
    data = json.loads(cache.read_text(encoding='utf-8')) if cache.exists() else {}
    if data.get('key') != key:
        sampled = sample_frames(proxy, fps=FPS, width=480)
        jaws = []
        for t, rgb in sampled:
            fs = faces(rgb)
            jaws.append([round(t, 3), max((f['jaw'] for f in fs), default=None), max((f['w'] for f in fs), default=0)])
        data = {'key': key, 'jaw': jaws}
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data), encoding='utf-8')
    pts = [(j, w) for t, j, w in data['jaw'] if start <= t <= end and j is not None]
    if len(pts) < 3:
        return 0.0
    jaw = np.array([p[0] for p in pts])
    # bouche qui bouge + visage assez grand (gros plan sur la personne qui parle)
    return float(min(1.0, np.mean(np.abs(np.diff(jaw))) * 12) * min(1.0, np.median([p[1] for p in pts]) * 4))
