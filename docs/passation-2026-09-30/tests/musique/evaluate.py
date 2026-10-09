"""Evaluation de la detection de musique : presence, tempo, ambiance (top-1 / top-3).
Usage : python evaluate.py avant|apres [filtre]"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path('D:/Tools/editeur_sami')
OUT = ROOT / 'runtime/cache/tmp/musique-eval'
FF = str(ROOT / 'tools/ffmpeg/bin/ffmpeg.exe')
AVANT = ROOT / 'docs/passation-2026-09-30/avant'
os.environ['EDITEUR_ROOT'] = str(ROOT)
which = sys.argv[1]
sys.path.insert(0, str(AVANT if which == 'avant' else ROOT / 'engine'))
from editeur import media, style_ref  # noqa: E402

SIG = {}


def decode(path, sr=22050):
    p = str(path)
    if p not in SIG:
        raw = subprocess.run([FF, '-v', 'error', '-i', p, '-vn', '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'],
                             capture_output=True, check=True).stdout
        SIG[p] = np.frombuffer(raw, np.float32).copy()
    return SIG[p]


media.decode_audio = lambda path, sr=16000: decode(path, sr)


def ranking_avant(son):
    """Classement complet de l'ancien _mood (meme calcul, pour le top-3)."""
    moods = json.loads((style_ref.STYLES / 'musiques.json').read_text(encoding='utf-8'))
    tempo, energy, timbre = son.get('tempo'), son.get('energie', 0.6), son.get('timbre')
    lib = style_ref._library_timbres() if timbre else {}
    ref = np.array(timbre) if timbre else None
    vecs = {k: np.array(v['timbre']) for k, v in lib.items() if v.get('timbre')}
    scale = np.std(np.stack(list(vecs.values())), axis=0) + 1e-6 if len(vecs) >= 3 else None

    def dist(m):
        bpm = min(abs(m['bpm'] - tempo), abs(m['bpm'] - tempo / 2), abs(m['bpm'] - tempo * 2)) if tempo else 30
        d = bpm / 25 + abs(style_ref.MOOD_ENERGY.get(m['id'], 0.5) - energy)
        if ref is not None and scale is not None and m['id'] in vecs:
            d += 0.3 * float(np.linalg.norm((vecs[m['id']] - ref) / scale)) / np.sqrt(len(ref))
        return d
    return [m['id'] for m in sorted(moods, key=dist)]


def analyse(c):
    path = OUT / 'cas' / f"{c['id']}.m4a"
    son = style_ref._audio(path, c['words'], c['duree'])
    if which == 'avant':
        # l'ancien code ne calcule l'empreinte que si la musique est detectee ; on force le calcul pour mesurer
        # l'ambiance separement de la detection
        return {'musique': son['musique'], 'tempo': son['tempo'], 'rang': ranking_avant(son) if son['musique'] else
                ranking_avant({**son, 'timbre': None}), 'confiance': None}
    return {'musique': son['musique'], 'tempo': son['tempo'], 'rang': son.get('classement') or [],
            'confiance': son.get('confiance'), 'mood': style_ref._mood(son.get('tempo'), son.get('energie', 0.6), son.get('timbre'), son)}


def tempo_ok(est, true, octave):
    if not est or not true:
        return False
    cands = [est, est * 2, est / 2] if octave else [est]
    return min(abs(c - true) / true for c in cands) <= 0.04


def main():
    cases = json.loads((OUT / 'cas.json').read_text(encoding='utf-8'))
    if len(sys.argv) > 2:
        cases = [c for c in cases if sys.argv[2] in c['id']]
    rows, t0 = [], time.time()
    for c in cases:
        r = analyse(c)
        rows.append({**{k: c.get(k) for k in ('id', 'voix', 'musique', 'mood', 'tempo', 'variante', 'niveau')}, 'res': r})
    el = time.time() - t0
    (OUT / f'verification-{which}.json').write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding='utf-8')
    pos = [r for r in rows if r['musique']]
    neg = [r for r in rows if not r['musique']]
    tp = sum(r['res']['musique'] for r in pos)
    tn = sum(not r['res']['musique'] for r in neg)
    print(f'[{which}] {len(rows)} cas en {el:.0f} s ({el / max(1, len(rows)):.1f} s/cas)')
    print(f'Presence : musique trouvee {tp}/{len(pos)} ({100 * tp / max(1, len(pos)):.0f} %), '
          f'parole seule reconnue {tn}/{len(neg)} ({100 * tn / max(1, len(neg)):.0f} %)')

    def block(name, sel):
        if not sel:
            return
        errs = [min(abs(r['res']['tempo'] - r['tempo']), abs(r['res']['tempo'] * 2 - r['tempo']), abs(r['res']['tempo'] / 2 - r['tempo']))
                for r in sel if r['res']['tempo']]
        strict = sum(tempo_ok(r['res']['tempo'], r['tempo'], False) for r in sel)
        octv = sum(tempo_ok(r['res']['tempo'], r['tempo'], True) for r in sel)
        top1 = sum(bool(r['res']['rang']) and r['res']['rang'][0] == r['mood'] for r in sel)
        top3 = sum(r['mood'] in r['res']['rang'][:3] for r in sel)
        e2e = sum(r['res']['musique'] and ((r['res'].get('mood') or (r['res']['rang'] or [None])[0]) == r['mood']) for r in sel)
        print(f'  {name:<22} n={len(sel):3d} | tempo ±4 % : {100 * strict / len(sel):3.0f} % (x2/÷2 admis : {100 * octv / len(sel):3.0f} %), '
              f'erreur med. {np.median(errs) if errs else float("nan"):5.1f} BPM | ambiance top-1 {100 * top1 / len(sel):3.0f} %, '
              f'top-3 {100 * top3 / len(sel):3.0f} % | bout en bout {100 * e2e / len(sel):3.0f} %')
    block('tous (avec musique)', pos)
    block('sous la voix', [r for r in pos if r['voix']])
    block('  exacte', [r for r in pos if r['voix'] and r['variante'] == 'exact'])
    block('  decalee (A+B)', [r for r in pos if r['voix'] and r['variante'] != 'exact'])
    for lv in (-16, -19, -22):
        block(f'  niveau {lv} dB', [r for r in pos if r.get('niveau') == lv])
    for v in ('sami1', 'sami2', 'bingo'):
        block(f'  voix {v}', [r for r in pos if r['voix'] == v])
    block('musique seule', [r for r in pos if not r['voix']])
    conf = [r for r in pos if r['res'].get('confiance') is not None]
    if conf:
        for lo, hi in ((0, 0.4), (0.4, 0.7), (0.7, 1.01)):
            sel = [r for r in conf if lo <= r['res']['confiance'] < hi]
            if sel:
                ok = sum(r['res']['mood'] == r['mood'] for r in sel)
                print(f'  confiance [{lo:.1f}, {hi:.1f}[ : n={len(sel):3d}, ambiance choisie juste {100 * ok / len(sel):3.0f} %')
    if neg:
        print('  parole seule :', ', '.join(f"{r['id']}={'MUSIQUE' if r['res']['musique'] else 'ok'}" for r in neg))


if __name__ == '__main__':
    main()
