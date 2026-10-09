"""Bruitages de montage synthetises (whoosh, pop, impact, riser...). Creations originales : aucun droit tiers.
python -m editeur.sfxgen  -> assets/sfx/editeur/*.wav"""
import numpy as np
import soundfile as sf

from .media import ROOT

SR = 48000
OUT = ROOT / 'assets/sfx/editeur'


def _t(d):
    return np.arange(int(SR * d)) / SR


def _env(n, attack, release, curve=2.0):
    e = np.ones(n)
    a, r = int(SR * attack), int(SR * release)
    if a:
        e[:a] = np.linspace(0, 1, a) ** curve
    if r:
        e[-r:] = np.linspace(1, 0, r) ** curve
    return e


def _bandpass_sweep(noise, f0, f1, q=2.0):
    """Filtre passe-bande a frequence glissante (biquad applique echantillon par echantillon)."""
    out = np.zeros_like(noise)
    freqs = np.geomspace(f0, f1, len(noise))
    x1 = x2 = y1 = y2 = 0.0
    for i, x in enumerate(noise):
        w = 2 * np.pi * freqs[i] / SR
        alpha = np.sin(w) / (2 * q)
        b0, b2, a0, a1, a2 = alpha, -alpha, 1 + alpha, -2 * np.cos(w), 1 - alpha
        y = (b0 * x + b2 * x2 - a1 * y1 - a2 * y2) / a0
        x2, x1, y2, y1 = x1, x, y1, y
        out[i] = y
    return out


def _norm(x, peak=0.89):
    return (x / (np.abs(x).max() + 1e-9) * peak).astype(np.float32)


def _stereo(x, width=0.0):
    if not width:
        return np.stack([x, x], axis=1)
    pan = np.linspace(-width, width, len(x))
    return np.stack([x * (1 - pan) / 1, x * (1 + pan) / 1], axis=1) / (1 + width)


def whoosh(d=0.45, f0=300, f1=4500, rng=None):
    rng = rng or np.random.default_rng(1)
    n = rng.standard_normal(int(SR * d))
    x = _bandpass_sweep(n, f0, f1, q=1.4) * _env(len(n), d * 0.55, d * 0.45, 1.6)
    return _stereo(_norm(x), 0.6)


def pop(f=900, d=0.09):
    t = _t(d)
    x = np.sin(2 * np.pi * (f + 900 * np.exp(-t * 60)) * t) * np.exp(-t * 45)
    return _stereo(_norm(x, 0.8))


def click(d=0.03):
    rng = np.random.default_rng(3)
    x = rng.standard_normal(int(SR * d)) * np.exp(-_t(d) * 220)
    return _stereo(_norm(x, 0.7))


def impact(d=1.2):
    t = _t(d)
    sub = np.sin(2 * np.pi * (38 + 90 * np.exp(-t * 9)) * t) * np.exp(-t * 3.2)
    rng = np.random.default_rng(5)
    hit = rng.standard_normal(len(t)) * np.exp(-t * 28) * 0.5
    return _stereo(_norm(np.tanh(1.6 * (sub + hit))))


def riser(d=1.6):
    t = _t(d)
    rng = np.random.default_rng(7)
    noise = _bandpass_sweep(rng.standard_normal(len(t)), 200, 7000, q=1.1)
    tone = np.sin(2 * np.pi * np.cumsum(np.geomspace(180, 1400, len(t))) / SR) * 0.35
    x = (noise + tone) * np.linspace(0, 1, len(t)) ** 2.2
    x[-int(SR * 0.02):] *= np.linspace(1, 0, int(SR * 0.02))
    return _stereo(_norm(x), 0.3)


def glitch(d=0.35):
    rng = np.random.default_rng(11)
    t = _t(d)
    square = np.sign(np.sin(2 * np.pi * rng.choice([180, 360, 720, 1440], len(t) // 800 + 1).repeat(800)[:len(t)] * t))
    gate = (rng.random(len(t) // 600 + 1) > 0.35).repeat(600)[:len(t)]
    return _stereo(_norm(square * gate * _env(len(t), 0.005, 0.08) * 0.6))


def ding(f=1320, d=1.1):
    t = _t(d)
    x = sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * (3 + 2 * k)) for k, a in ((1, 1), (2.76, 0.4), (5.4, 0.15)))
    return _stereo(_norm(x, 0.7))


def shutter():
    rng = np.random.default_rng(13)
    a = rng.standard_normal(int(SR * 0.025)) * np.exp(-_t(0.025) * 150)
    gap = np.zeros(int(SR * 0.06))
    b = rng.standard_normal(int(SR * 0.04)) * np.exp(-_t(0.04) * 100) * 0.8
    return _stereo(_norm(np.concatenate([a, gap, b])))


SOUNDS = {
    'whoosh-court': lambda: whoosh(0.35),
    'whoosh-long': lambda: whoosh(0.7, 200, 3500, np.random.default_rng(2)),
    'whoosh-descendant': lambda: whoosh(0.5, 5000, 400, np.random.default_rng(4)),
    'pop': lambda: pop(),
    'pop-grave': lambda: pop(520, 0.12),
    'click': click,
    'impact': impact,
    'riser': riser,
    'glitch': glitch,
    'ding': ding,
    'declencheur-photo': shutter,
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, make in SOUNDS.items():
        sf.write(OUT / f'{name}.wav', make(), SR, subtype='PCM_16')
        print(name)
    (OUT / 'LICENCE.txt').write_text('Sons synthetises par l\'editeur (engine/editeur/sfxgen.py). Creations originales, '
                                     'libres de tout droit tiers.\n', encoding='utf-8')


if __name__ == '__main__':
    main()
