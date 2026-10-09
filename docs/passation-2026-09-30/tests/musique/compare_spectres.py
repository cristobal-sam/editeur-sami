"""Comparaison locale des signatures sur le banc d'essai conserve."""
import json
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[4]
BOX = ROOT / 'runtime/cache/tmp/musique-eval'
data = np.load(BOX / 'spectres.npz')
cases = json.loads((BOX / 'cas.json').read_text(encoding='utf-8'))
ids = [m['id'] for m in json.loads((ROOT / 'styles/musiques.json').read_text(encoding='utf-8'))]

def feature(m, q):
    level=m[3:45].sum(axis=0)
    m=m[:,level<=np.quantile(level,.15)]
    p = 10 * np.log10(np.maximum(np.quantile(m, q, axis=1), 1e-10))
    return p - p.mean()

rhythms = {r['id']: r for r in json.loads((BOX/'rythme-verification.json').read_text())}
bpms = np.array([m['bpm'] for m in json.loads((ROOT / 'styles/musiques.json').read_text(encoding='utf-8'))])
for q in (.2, .5):
    lib = np.stack([feature(data[f'lib-{k}|mel'], q) for k in ids])
    scale = np.maximum(lib.std(axis=0), 3)
    for gaps in (False, True):
        top1 = top3 = n = 0
        for c in cases:
            if not c['musique']:
                continue
            m = data[f"{c['id']}|mel"]
            if gaps:
                level=m[3:45].sum(axis=0)
                keep=level<=np.quantile(level,.15)
                if keep.sum() > 15:
                    m = m[:,keep]
            f = feature(m, q)
            d = np.sqrt(np.mean(((lib - f) / scale)**2, axis=1))
            tempo = rhythms[c['id']]['est']
            d = .4*d + np.minimum.reduce([abs(bpms-tempo*k) for k in (.5,1,2)])/25
            ranks = [ids[i] for i in np.argsort(d)]
            n += 1
            top1 += ranks[0] == c['mood']
            top3 += c['mood'] in ranks[:3]
        print(q, gaps, n, top1/n, top3/n, flush=True)
