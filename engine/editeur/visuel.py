"""Montages visuels (sans texte a suivre) : immobilier et evenementiel.

Immobilier : chaque video est stabilisee (vidstab, 2 passes), decoupee en scenes (PySceneDetect) ;
dans chaque scene on garde le passage le plus net et le plus fluide ; CLIP reconnait la piece et
le montage suit l'ordre d'une visite (facade, entree, salon, cuisine... terrasse, vue). Les coupes
tombent sur les temps de la musique (librosa) ; titre = adresse.
Evenementiel : meilleurs plans (nettete, mouvement, visages) dans l'ordre chronologique, coupes sur
la musique, et 1 ou 2 citations de l'orateur (transcription) gardees avec leur son.
Le resultat est un projet normal (project.json + reel) : tout reste modifiable dans l'interface."""
import json
import os
from pathlib import Path

import numpy as np

from . import media, search
from .derush import ABORTED, _words_text, project_name, slug
from .media import ROOT

KINDS = {
    'immobilier': {'template': 'immobilier', 'music': 'immobilier', 'stabilize': True, 'order': 'pieces', 'beats': (4, 8), 'quotes': False},
    'evenement': {'template': 'evenement', 'music': 'energique', 'stabilize': False, 'order': 'chrono', 'beats': (2, 4), 'quotes': True},
}
ROOMS = [('facade', 'Façade', 'the exterior facade of a house seen from the street'), ('entree', 'Entrée', 'an entrance hallway with a front door'),
         ('salon', 'Salon', 'a living room with a sofa'), ('cuisine', 'Cuisine', 'a kitchen with cabinets and countertop'),
         ('salle-a-manger', 'Salle à manger', 'a dining room with a table and chairs'), ('bureau', 'Bureau', 'a home office with a desk'),
         ('chambre', 'Chambre', 'a bedroom with a bed'), ('salle-de-bain', 'Salle de bain', 'a bathroom with a shower, bathtub or sink'),
         ('sous-sol', 'Sous-sol', 'a basement or laundry room'), ('terrasse', 'Terrasse / cour', 'a backyard, garden, terrace or swimming pool'),
         ('vue', 'Vue', 'an aerial drone view or a scenic view')]


def stabilized(proxy):
    """Media optimise stabilise (vidstab 2 passes), en cache a cote du media optimise."""
    proxy = Path(proxy)
    out = proxy.with_name(proxy.stem + '-stab.mp4')
    if out.exists() and out.stat().st_mtime >= proxy.stat().st_mtime:
        return out
    trf = proxy.with_suffix('.trf')
    # vidstab veut un chemin sans « : » de lecteur : on travaille dans le dossier du fichier
    cwd = proxy.parent
    media.run([media.FFMPEG, '-v', 'error', '-y', '-i', proxy.name, '-vf', f'vidstabdetect=shakiness=6:accuracy=12:result={trf.name}',
               '-f', 'null', '-'], cwd=cwd)
    tmp = out.with_suffix('.part.mp4')
    for enc in (['-c:v', 'h264_nvenc', '-preset', 'p5', '-cq', '18', '-b:v', '0', '-bf', '0'], ['-c:v', 'libx264', '-crf', '17', '-bf', '0']):
        try:
            media.run([media.FFMPEG, '-v', 'error', '-y', '-i', proxy.name, '-vf',
                       f'vidstabtransform=input={trf.name}:smoothing=30:zoom=4:optzoom=0,unsharp=5:5:0.5',
                       *enc, '-g', '15', '-c:a', 'copy', '-movflags', '+faststart', tmp.name], cwd=cwd)
            break
        except Exception:
            continue
    tmp.replace(out)
    trf.unlink(missing_ok=True)
    return out


def _shots(proxy, duration, length):
    """Dans chaque scene : le passage de `length` s le plus net et le plus fluide. [(debut, fin, note, image du milieu)]"""
    import cv2
    starts = search._scenes(proxy) + [duration]
    frames = media.sample_frames(proxy, fps=2, width=320)
    sharp = np.array([cv2.Laplacian(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), cv2.CV_64F).var() for _, rgb in frames])
    motion = np.array([0.0] + [float(np.abs(frames[i][1].astype(np.int16) - frames[i - 1][1]).mean()) for i in range(1, len(frames))])
    ref_sharp = np.median(sharp) or 1.0
    out = []
    for a, b in zip(starts, starts[1:]):
        a, b = a + 0.25, b - 0.25  # jamais sur le raccord de la camera
        if b - a < min(1.2, length):
            continue
        best = None
        t = a
        while t + min(length, b - a) <= b + 1e-6:
            idx = [i for i, (ft, _) in enumerate(frames) if t <= ft <= t + length]
            if idx:
                s = float(np.mean(sharp[idx])) / ref_sharp
                m = float(np.mean(motion[idx]))
                # un mouvement doux est bien (travelling), un mouvement fort = tremblement ou panoramique trop rapide
                score = min(1.5, s) - max(0.0, (m - 6) / 12)
                if best is None or score > best[2]:
                    best = (round(t, 2), round(min(b, t + length), 2), score, frames[idx[len(idx) // 2]][1])
            t += 0.5
        if best:
            out.append(best)
    return out


def _rooms(images):
    """Piece reconnue (CLIP) pour chaque image : [(id, libelle, confiance)]."""
    import torch
    from PIL import Image
    model, prep, tok, dev = search._model()
    with torch.no_grad():
        txt = model.encode_text(tok([f'a photo of {d}' for _, _, d in ROOMS]).to(dev)).float()
        txt = txt / txt.norm(dim=-1, keepdim=True)
        img = model.encode_image(torch.stack([prep(Image.fromarray(i)) for i in images]).to(dev)).float()
        img = img / img.norm(dim=-1, keepdim=True)
        probs = (100 * img @ txt.T).softmax(dim=-1).cpu().numpy()
    return [(ROOMS[int(p.argmax())][0], ROOMS[int(p.argmax())][1], float(p.max())) for p in probs]


def _beats(music_file):
    import librosa
    y, sr = librosa.load(str(music_file), sr=22050, mono=True, duration=240)
    _, beats = librosa.beat.beat_track(y=y, sr=sr, units='time')
    beats = [float(b) for b in beats]
    if len(beats) < 8:  # pas de pulsation claire : un temps toutes les 0,5 s
        return [i * 0.5 for i in range(480)]
    # intro sans pulsation detectee : on prolonge la grille vers le debut, a la meme cadence
    period = float(np.median(np.diff(beats)))
    head = []
    t = beats[0] - period
    while t > 0.05:
        head.append(t)
        t -= period
    return [0.0] + sorted(head) + beats


def _quotes(takes, cache, n=2):
    """Citations de l'orateur : les phrases les plus longues et propres de la transcription."""
    from . import libre, transcribe
    found = []
    for sid, path in takes:
        words = transcribe.transcribe(path, cache / 'transcripts')['words']
        for i0, i1 in libre.utterances(words):
            text = _words_text(words[i0:i1 + 1])
            dur = words[i1]['end'] - words[i0]['start']
            if i1 - i0 >= 6 and 2.5 <= dur <= 9 and not ABORTED.search(text):
                found.append({'source': sid, 'words': words[i0:i1 + 1], 'text': text, 'score': (i1 - i0) / dur})
    return sorted(found, key=lambda q: -q['score'])[:n]


def build(folder, kind='immobilier', out_root=None, cache_root=None, title=None, seconds=30, music=None):
    cfg = KINDS[kind]
    folder = Path(folder).resolve()
    out_root = Path(out_root or ROOT / 'projects')
    cache = Path(cache_root or ROOT / 'projects/_cache')
    videos = [folder] if folder.is_file() else media.list_videos(folder)  # une video seule marche aussi
    if not videos:
        raise SystemExit(f'Aucune video dans {folder}')
    mood = music or cfg['music']
    music_file = ROOT / 'assets/music' / f'{mood}.ogg'
    beats = _beats(music_file)  # commence a 0 : la video commence avec la musique
    period = float(np.median(np.diff(beats)))
    lo_b, hi_b = cfg['beats']
    sources, shots = {}, []
    for n, path in enumerate(videos, 1):
        sid = f't{n:02d}'
        print(f'   {path.name} : preparation{" et stabilisation" if cfg["stabilize"] else ""}...')
        proxy = media.optimized(path, 0, cache / 'optimises')
        if cfg['stabilize']:
            proxy = stabilized(proxy)
        info = media.probe(path)
        sources[sid] = {'path': str(path), 'name': str(path.relative_to(folder.parent if folder.is_file() else folder)), 'rotate': 0, 'proxy': str(proxy), 'stab': cfg['stabilize'],
                        'transcript': str(cache / 'transcripts' / f'{media.cache_name(path)}.transcript.json'),
                        'duration': info['duration'], 'fps': info['fps'], 'mtime': path.stat().st_mtime}
        for a, b, score, img in _shots(proxy, media.probe(proxy)['duration'], period * hi_b):
            shots.append({'source': sid, 'in': a, 'out': b, 'score': score, 'img': img, 'order': (n, a)})
    if not shots:
        raise SystemExit('Aucun plan exploitable (videos trop courtes ou floues).')
    if cfg['order'] == 'pieces':
        for s, (rid, label, conf) in zip(shots, _rooms([s['img'] for s in shots])):
            s.update(room=rid, label=label, conf=conf)
        rank = {r[0]: i for i, r in enumerate(ROOMS)}
        # meilleurs plans d'abord (limite par la duree), puis ordre de visite
        budget = int(seconds / (period * (lo_b + hi_b) / 2)) + 1
        chosen = sorted(shots, key=lambda s: -s['score'])[:budget]
        chosen.sort(key=lambda s: (rank[s['room']], s['order']))
    else:
        for s in shots:
            s.update(room='moment', label='Moments')
        budget = int(seconds / (period * (lo_b + hi_b) / 2)) + 1
        chosen = sorted(sorted(shots, key=lambda s: -s['score'])[:budget], key=lambda s: (sources[s['source']]['mtime'], s['order']))
    # durees calees sur les temps de la musique : chaque plan dure un nombre entier de temps
    timeline, t_beat, blocks = [], 0, []
    quotes = _quotes([(sid, s['path']) for sid, s in sources.items()], cache) if cfg['quotes'] else []
    slots = {max(1, len(chosen) // 3): quotes[0]} if quotes else {}
    if len(quotes) > 1:
        slots[max(2, 2 * len(chosen) // 3)] = quotes[1]
    for i, s in enumerate(chosen):
        if i in slots:
            q = slots.pop(i)
            start, end = q['words'][0]['start'] - 0.12, q['words'][-1]['end'] + 0.25
            # on termine la citation sur un temps de la musique pour que la suite reste calee
            t0 = beats[t_beat] if t_beat < len(beats) else t_beat * period
            k = next((j for j in range(t_beat + 1, len(beats)) if beats[j] - t0 >= end - start), t_beat + int((end - start) / period) + 1)
            dur = (beats[k] if k < len(beats) else k * period) - t0
            timeline.append({'id': f'c{len(timeline) + 1}', 'block': 'citation', 'sentences': [], 'tighten': False, 'source': q['source'],
                             'in': round(start, 3), 'out': round(start + dur, 3), 'text': q['text'], 'words': q['words'], 'flags': [],
                             'choice': 0, 'takes': [], 'mute': False})
            t_beat = k
            if 'citation' not in [b['id'] for b in blocks]:
                blocks.append({'id': 'citation', 'label': 'Citation', 'text': q['text']})
        avail = s['out'] - s['in']
        t0 = beats[t_beat] if t_beat < len(beats) else t_beat * period
        k = t_beat + hi_b
        while k > t_beat + lo_b and ((beats[k] if k < len(beats) else k * period) - t0) > avail:
            k -= 1
        dur = min(avail, (beats[k] if k < len(beats) else k * period) - t0)
        timeline.append({'id': f'c{len(timeline) + 1}', 'block': s['room'], 'sentences': [], 'tighten': False, 'source': s['source'],
                         'in': s['in'], 'out': round(s['in'] + dur, 3), 'text': '', 'words': [], 'flags': [], 'choice': 0, 'takes': [], 'mute': True})
        if s['room'] not in [b['id'] for b in blocks]:
            blocks.append({'id': s['room'], 'label': s['label'], 'text': ''})
        t_beat = k
        if (beats[t_beat] if t_beat < len(beats) else t_beat * period) >= seconds:
            break
    base_name = folder.stem if folder.is_file() else folder.name
    label = title or base_name
    name = project_name(out_root, slug(f'{base_name}-{kind}'), folder, alt=folder.parent.name)
    project = {
        'version': 1, 'name': name, 'label': label, 'mode': kind,
        'script': {'file': folder.name, 'path': str(folder), 'id': 's1', 'title': label, 'blocks': blocks},
        'format': {'width': 1080, 'height': 1920, 'fps': 30},
        'audio': {'loudness_lufs': -14, 'denoise': False, 'declip': False},
        'sources': {k: {x: v for x, v in s.items() if x != 'mtime'} for k, s in sources.items()},
        'timeline': timeline, 'variants': [], 'music': {'mood': mood, 'beats': beats[:400]},
    }
    pdir = out_root / name
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / 'project.json').write_text(json.dumps(project, ensure_ascii=False, indent=1), encoding='utf-8')
    report = [f'# Montage {kind} — {label}', '', f'{len(timeline)} plans, musique « {mood} » (un temps = {period:.2f} s).', '']
    report += [f"{c['id']}. {sources[c['source']]['name']} {c['in']:.1f} → {c['out']:.1f} s — "
               f"{next(b['label'] for b in blocks if b['id'] == c['block'])}" + (f" : « {c['text']} »" if c['text'] else '') for c in timeline]
    (pdir / 'rapport.md').write_text('\n'.join(report) + '\n', encoding='utf-8')
    # le reel : style du type de montage, titre en bandeau, musique seule (plans muets)
    from . import reel as reelmod
    os.environ.setdefault('EDITEUR_LLM', '0')
    rfile = reelmod.ensure(pdir, None, template=cfg['template'], ai_mode='auto')
    doc = json.loads(rfile.read_text(encoding='utf-8'))
    doc['kind'] = kind
    doc['banner'] = {'enabled': True, 'text': label.upper(), 'start': 0.3, 'end': round(min(4.0, beats[min(len(beats) - 1, 8)]), 2)}
    doc['audio'] = {'voice': 'naturel' if quotes else 'aucun', 'roomTone': False, 'declip': False}
    doc['music'] = {**doc['music'], 'enabled': True, 'mood': mood, 'file': f'music/{mood}.ogg'}
    rfile.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
    return pdir
