"""Tempo sous la voix : choix des bandes et estimation fine (tempogramme de Fourier + harmoniques)."""
import json
from pathlib import Path

import librosa
import numpy as np

OUT = Path('D:/Tools/editeur_sami/runtime/cache/tmp/musique-eval')
SR, HOP = 22050, 512
FPS = SR / HOP
F = librosa.mel_frequencies(n_mels=64, fmin=30, fmax=11000)
D = np.load(OUT / 'spectres.npz')
cases = [c for c in json.loads((OUT / 'cas.json').read_text(encoding='utf-8')) if c['musique']]


def envelope(P, weights):
    L = 10 * np.log10(np.maximum(P, 1e-10))
    L = np.maximum(L, L.max() - 80)
    d = np.maximum(0, np.diff(L, axis=1))
    env = (weights[:, None] * d).sum(axis=0) / max(1e-6, weights.sum())
    # retire la tendance lente (voix : syllabes et phrases)
    k = int(FPS * 0.4) | 1
    env = env - np.convolve(env, np.ones(k) / k, 'same')
    return np.maximum(env, 0)


def fourier_tempo(env, lo=55, hi=200, step=0.1, prior=True):
    t = np.arange(len(env)) / FPS
    env = env - env.mean()
    grid = np.arange(lo, hi, step)

    def mag(bpm):
        f = np.asarray(bpm) / 60
        return np.abs(np.exp(-2j * np.pi * np.outer(f, t)) @ env) / len(env)
    s1, s2, s4 = mag(grid), mag(grid * 2), mag(grid * 4)
    sal = s1 + 0.5 * s2 + 0.25 * s4
    if prior:
        sal = sal * np.exp(-0.5 * (np.log2(grid / 105) / 0.9) ** 2)
    k = int(np.argmax(sal))
    # clarte : pic / mediane
    clarity = float(sal[k] / (np.median(sal) + 1e-9))
    return float(grid[k]), clarity


def ok(est, true):
    return abs(est - true) / true <= 0.04


def ok8(est, true):
    return min(abs(e - true) / true for e in (est, est * 2, est / 2)) <= 0.04


def dominance_weights(P):
    L = 10 * np.log10(np.maximum(P, 1e-10))
    spread = np.percentile(L, 90, axis=1) - np.percentile(L, 10, axis=1)
    return np.exp(-spread / 12)


methods = {
    'toutes': lambda P: np.ones(64),
    'graves<150': lambda P: (F < 150).astype(float),
    'aigus>5k': lambda P: (F > 5000).astype(float),
    'graves+aigus': lambda P: ((F < 150) | (F > 5000)).astype(float),
    'dominance': dominance_weights,
    'dominance*(g+a)': lambda P: dominance_weights(P) * (0.3 + ((F < 150) | (F > 5000))),
}
for name, wf in methods.items():
    res = {'voix': [0, 0, 0], 'seule': [0, 0, 0]}
    for c in cases:
        P = D[f"{c['id']}|mel"]
        est, cl = fourier_tempo(envelope(P, wf(P)))
        g = 'voix' if c['voix'] else 'seule'
        res[g][0] += ok(est, c['tempo'])
        res[g][1] += ok8(est, c['tempo'])
        res[g][2] += 1
    print(f"{name:<18} sous la voix {100 * res['voix'][0] / res['voix'][2]:3.0f} % (octave {100 * res['voix'][1] / res['voix'][2]:3.0f} %)"
          f" | seule {100 * res['seule'][0] / res['seule'][2]:3.0f} % (octave {100 * res['seule'][1] / res['seule'][2]:3.0f} %)")
