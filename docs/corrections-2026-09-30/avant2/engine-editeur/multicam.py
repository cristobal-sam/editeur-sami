"""Synchronisation multicamera par le son (podcasts, conferences filmes a plusieurs cameras).

Chaque camera enregistre le meme son : on aligne les enveloppes sonores par correlation (FFT),
a 1 ms pres puis affinee a l'echantillon. Les prises synchronisees forment un groupe dans
project.json (`multicam`) ; dans le montage, chaque plan peut afficher un autre angle du groupe
(le son reste celui de la prise du plan). Choix automatique de l'angle : la camera ou l'on voit
la bouche de la personne qui parle bouger (cadrage.speaking)."""
import json
from pathlib import Path

import numpy as np

from . import media, montage

SR = 8000
ENV_RATE = 1000  # enveloppe a 1 kHz : precision 1 ms


def _envelope(path, max_seconds=None):
    a = media.decode_audio(path, sr=SR)
    if max_seconds:
        a = a[:int(max_seconds * SR)]
    hop = SR // ENV_RATE
    a = np.abs(a[:len(a) // hop * hop]).reshape(-1, hop).mean(axis=1)
    # log + derivee positive : les attaques (syllabes, claps) comptent, pas le niveau general
    e = np.log1p(a * 1000)
    d = np.maximum(0, np.diff(e, prepend=e[0]))
    return (d - d.mean()) / (d.std() + 1e-9)


def offset(ref, other):
    """Decalage (s) du debut de `other` dans le temps de `ref` et confiance (pic / bruit de la correlation)."""
    a, b = _envelope(ref), _envelope(other)
    n = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    corr = np.fft.irfft(np.fft.rfft(a, n) * np.conj(np.fft.rfft(b, n)), n)
    corr = np.concatenate([corr[-(len(b) - 1):], corr[:len(a)]])  # lags de -(len(b)-1) a len(a)-1
    k = int(np.argmax(corr))
    lag = k - (len(b) - 1)
    confidence = float(corr[k] / (np.std(corr) * 8 + 1e-9))
    return lag / ENV_RATE, confidence


def sync(project_dir, source_ids=None, min_confidence=2.0):
    """Cree les groupes multicamera d'un projet : prises dont le son se recoupe. Ecrit project.json."""
    pfile = Path(project_dir) / 'project.json'
    project = json.loads(pfile.read_text(encoding='utf-8'))
    ids = list(source_ids or project['sources'])
    ids.sort(key=lambda s: -project['sources'][s]['duration'])
    groups, placed = [], set()
    for ref in ids:
        if ref in placed:
            continue
        g = {'id': f'm{len(groups) + 1}', 'ref': ref, 'offsets': {ref: 0.0}, 'confidence': {}}
        for other in ids:
            if other == ref or other in placed:
                continue
            off, conf = offset(project['sources'][ref]['path'], project['sources'][other]['path'])
            if conf >= min_confidence:
                g['offsets'][other] = round(off, 3)
                g['confidence'][other] = round(conf, 2)
        if len(g['offsets']) > 1:
            groups.append(g)
            placed |= set(g['offsets'])
    project['multicam'] = groups
    pfile.write_text(json.dumps(project, ensure_ascii=False, indent=1), encoding='utf-8')
    return groups


def auto_angles(project_dir, rid, wide_every=0):
    """Choisit l'angle de chaque plan multicamera : la camera ou la personne qui parle est la plus visible.
    wide_every > 0 : un plan large (camera de reference) tous les N plans, pour respirer."""
    from . import cadrage
    reel = montage.load(project_dir, rid)
    srcs = reel['sources']
    changed, prev = [], None
    for n, c in enumerate(reel['clips']):
        a = srcs.get(c['source'], {}).get('sync')
        if not a:
            continue
        angles = [s for s, v in srcs.items() if (v.get('sync') or {}).get('group') == a['group']]
        if wide_every and n % wide_every == wide_every - 1:
            best = min(angles, key=lambda s: srcs[s]['sync']['offset'] if False else 0)
        else:
            scores = {}
            for s in angles:
                shift = a['offset'] - srcs[s]['sync']['offset']
                scores[s] = cadrage.speaking(montage.proxy_path(srcs[s]), c['in'] + shift, c['out'] + shift)
            best = max(scores, key=scores.get)
            # on garde l'angle precedent si la difference est faible (evite les changements inutiles)
            if prev in scores and scores[prev] >= scores[best] * 0.85:
                best = prev
        c['angle'] = None if best == c['source'] else best
        prev = best
        changed.append({'clip': c['id'], 'angle': best})
    montage.save(project_dir, rid, reel)
    return changed
