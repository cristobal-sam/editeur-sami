"""Bruitages de montage synthetises (whoosh, pop, impact, riser...). Creations originales : aucun droit tiers.

python -m editeur.sfxgen            -> assets/sfx/editeur/*.wav : les 11 sons d'origine (crees seulement s'ils manquent,
                                       jamais reecrits) + les sons de coupe varies (COUPES) + quelques sons Kenney (CC0)
                                       remis au meme niveau (KENNEY) + LICENCE.txt
python -m editeur.sfxgen mesures    -> une ligne JSON : sonie, niveau, crete, pic, duree, aigus de chaque son de coupe
python -m editeur.sfxgen planche    -> runtime/cache/tmp/sons/planche-sons.png (spectrogrammes a regarder)
python -m editeur.sfxgen familles   -> remesure pic et duree des sons de styles/sons-transitions.json (le reste est garde)
python -m editeur.sfxgen sons <dossier_projet> --reel <rid> --famille <id|auto> [--varier oui|non]
                                    -> famille de sons du reel (reserve « pool » ecrite dans le reel, version « avant »
                                       gardee dans versions/<rid>/) ; une ligne JSON

Sons de coupe (ronde « sons », 2026-10-02) : avant, chaque coupe et chaque entree d'interface jouait le meme
« whoosh-court » (le « meme son de vent »). Les familles (styles/sons-transitions.json) regroupent ces sons par role
(transition, interface, apparition, mot-fort, impact, cta) ; remotion/src/timeline.ts (sfxEvents) en tire un different a
chaque coupe. Niveau : tous les nouveaux sons sont ramenes a la meme SONIE (ponderation K comme le LUFS, sur 100 ms :
un souffle grave et un clic aigu de meme RMS ne sonnent pas pareil) ; ceux qui ne peuvent pas l'atteindre sans depasser
-1 dBFS (clics tres brefs) recoivent un gain dans SFX_GAIN (timeline.ts). Les familles ajustent ensuite chaque role
(mots forts plus discrets, montee avant l'appel a l'action plus presente). pic = instant (s depuis le debut du fichier)
ou le son atteint 90 % de son maximum : il tombe SUR la coupe. Controle a l'oeil : « planche » (spectrogrammes).
"""
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf

from .media import ROOT

SR = 48000
OUT = ROOT / 'assets/sfx/editeur'
FAMILLES = ROOT / 'styles/sons-transitions.json'
NIVEAU = -15.5          # dB : cible de la banque (banque.NIVEAU_CIBLE, crete RMS sur 50 ms) : mesure gardee pour comparer
SONIE = -11.0           # sonie de crete (ponderation K de la norme BS.1770, fenetre de 100 ms) des sons de coupe une fois
                        # SFX_GAIN applique : celle du whoosh-court d'origine (-11,0), pour qu'ils sonnent ensemble
CRETE_MAX = 0.891       # -1 dBFS : marge sous l'ecretage
AIGUS_MAX = 0.12        # part de l'energie au-dessus de 10 kHz au-dela de laquelle un son est juge dur
ROLES = ('transition', 'interface', 'apparition', 'mot-fort', 'impact', 'cta')
POOL_MAX = 32           # meme limite que la validation du serveur (PUT /api/reels)
NOM_VERSION = 'avant sons de coupe'


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


# ---------------------------------------------------------------- briques des sons de coupe (ronde « sons »)


def _f(x, kind, f, order=2):
    """Filtre de Butterworth (scipy) : kind lowpass | highpass | bandpass (f = (bas, haut))."""
    from scipy.signal import butter, sosfilt
    return sosfilt(butter(order, f, btype=kind, fs=SR, output='sos'), x, axis=0)


def _bruit(d, seed):
    return np.random.default_rng(seed).standard_normal(int(SR * d))


def _courbe(n, pts, log=False):
    """Courbe sur n echantillons par points [(position 0-1, valeur)] ; log : interpolation geometrique (frequences)."""
    xs = [p[0] for p in pts]
    ys = np.array([p[1] for p in pts], dtype=float)
    u = np.linspace(0, 1, n)
    return np.exp(np.interp(u, xs, np.log(ys))) if log else np.interp(u, xs, ys)


def _cloche(n, centre, largeur):
    """Enveloppe en cloche (gaussienne) : centre et largeur en part de la duree."""
    u = np.linspace(0, 1, n)
    return np.exp(-((u - centre) / largeur) ** 2)


def _bp_suivi(x, freqs, q=1.0):
    """Passe-bande a frequence variable (une frequence par echantillon) ; biquad echantillon par echantillon."""
    w = 2 * np.pi * np.clip(np.asarray(freqs, dtype=float), 20, SR * 0.45) / SR
    alpha = np.sin(w) / (2 * q)
    a0 = 1 + alpha
    b0 = (alpha / a0).tolist()
    a1 = (-2 * np.cos(w) / a0).tolist()
    a2 = ((1 - alpha) / a0).tolist()
    out = [0.0] * len(x)
    x1 = x2 = y1 = y2 = 0.0
    for i, xi in enumerate(np.asarray(x, dtype=float).tolist()):
        y = b0[i] * (xi - x2) - a1[i] * y1 - a2[i] * y2
        x2, x1, y2, y1 = x1, xi, y1, y
        out[i] = y
    return np.array(out)


def _osc(freq, forme='sin', phase=0.0):
    """Oscillateur a frequence variable (Hz par echantillon). 'saw' : harmoniques jusqu'a 7 kHz (ni repliement ni aigus durs)."""
    f = np.asarray(freq, dtype=float)
    ph = 2 * np.pi * np.cumsum(f) / SR + phase
    if forme == 'sin':
        return np.sin(ph)
    if forme == 'tri':
        return 2 / np.pi * np.arcsin(np.sin(ph))
    k_max = max(1, int(7000 / max(1.0, float(f.max()))))
    return sum(np.sin(k * ph) / k for k in range(1, k_max + 1)) * 0.6


def _pan(x, p):
    """Mono -> stereo a puissance constante ; p de -1 (gauche) a 1 (droite), nombre ou tableau (centre = mono double)."""
    a = (np.asarray(p, dtype=float) + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], axis=1) * np.sqrt(2)


def _ecrase(x, bits=5, tenue=3):
    """Son « numerique » : echantillons tenus (frequence d'echantillonnage reduite) et quantifies sur peu de bits."""
    x = np.asarray(x, dtype=float) / (np.abs(x).max() + 1e-9)
    y = np.repeat(x[::tenue], tenue)[:len(x)]
    q = 2 ** (bits - 1)
    return np.round(y * q) / q


def _vitesse(src, v):
    """Lit src a vitesse variable (v par echantillon de sortie : 1 = normale, 0 = arret) : arret ou demarrage de bande."""
    pos = np.clip(np.cumsum(v), 0, len(src) - 1)
    return np.interp(pos, np.arange(len(src)), src)


def _place(dst, x, t):
    """Ajoute x dans dst a l'instant t (s), sans deborder."""
    i = int(SR * t)
    n = min(len(x), len(dst) - i)
    if n > 0:
        dst[i:i + n] += x[:n]
    return dst


def _tic(d=0.05, f=3200, seed=60, vif=420):
    t = _t(d)
    n = _f(_bruit(d, seed), 'bandpass', (1800, 5200)) * np.exp(-t * vif)
    return n + 0.5 * np.sin(2 * np.pi * f * t) * np.exp(-t * vif * 0.8)


def _souffle(d, pts, q, seed, att=0.5, courbe=2.0, coupe=8000):
    """Souffle : bruit filtre dont la frequence suit pts [(position, Hz)], enveloppe montee/descente, sans aigus durs."""
    n = _bruit(d, seed)
    x = _bp_suivi(n, _courbe(len(n), pts, log=True), q) * _env(len(n), d * att, d * (1 - att), courbe)
    return _f(x, 'lowpass', coupe)


def _passage(d, pts, seed, gauche_droite=True, largeur=0.2, q=1.0):
    """Passage stereo (effet Doppler) : la frequence descend en passant, le son traverse l'image d'un cote a l'autre."""
    n = _bruit(d, seed)
    m = len(n)
    x = _bp_suivi(n, _courbe(m, pts, log=True), q) * _cloche(m, 0.52, largeur)
    air = _f(_bruit(d, seed + 1), 'bandpass', (2500, 6500)) * _cloche(m, 0.5, largeur * 0.7) * 0.18
    u = np.linspace(-1, 1, m)
    p = np.tanh(u * 2.4) * 0.92 * (1 if gauche_droite else -1)
    return _pan(_f(x + air, 'lowpass', 8500), p)


def _chute(d_whoosh, d, f_sub, seed):
    """Whoosh qui monte puis basse qui tombe (sub drop) sur la coupe ; harmoniques pour s'entendre sur un telephone."""
    out = np.zeros(int(SR * d))
    w = _souffle(d_whoosh, [(0, 450), (1, 3600)], 0.9, seed, att=0.85, courbe=2.2)
    _place(out, w * 0.55, 0)
    t = _t(d - d_whoosh * 0.8)
    f = f_sub[1] + (f_sub[0] - f_sub[1]) * np.exp(-t * 7)
    sub = np.tanh(2.2 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.exp(-t * 4.5)
    sub = _f(sub, 'lowpass', 1800)
    return _place(out, sub, d_whoosh * 0.8)


def _inverse(d, seed, coupe=(6000, 700), vif=5.0, tons=()):
    """Son qui s'eteint, joue a l'envers : il gonfle et s'arrete net (son « aspire » avant une coupe)."""
    t = _t(d)
    n = _bruit(d, seed)
    x = _bp_suivi(n, _courbe(len(n), [(0, coupe[0]), (1, coupe[1])], log=True), 0.7) * np.exp(-t * vif)
    for f, a in tons:
        x += a * sum(np.sin(2 * np.pi * f * k * t) / k ** 1.4 for k in (1, 2, 3)) * np.exp(-t * vif * 0.8)
    return _f(x[::-1], 'lowpass', 8000, order=4)


def _accord(d, notes, seed):
    """Accord doux (dents de scie filtrees) + un peu de souffle : matiere pour l'arret et le demarrage de bande."""
    t = _t(d)
    x = sum(_osc(np.full(len(t), f), 'saw') for f in notes) / len(notes)
    x += _f(_bruit(d, seed), 'lowpass', 2500) * 0.15
    return _f(x, 'lowpass', 4500)


def _arret_bande(d, seed, notes=(110, 165, 220, 277)):
    """Arret de bande : la vitesse tombe a zero, puis le « clac » du frein tombe sur la coupe."""
    m = int(SR * d * 0.82)
    v = (1 - np.linspace(0, 1, m)) ** 1.7
    src = _accord(d * 1.2, notes, seed)
    x = _vitesse(src, v) * v ** 0.5 * 0.55
    x = _f(x, 'lowpass', 3500)
    out = np.zeros(int(SR * d))
    _place(out, x, 0)
    tt = _t(0.12)
    clac = (np.sin(2 * np.pi * 140 * tt) * np.exp(-tt * 40) + _f(_bruit(0.12, seed + 3), 'lowpass', 1800) * np.exp(-tt * 70) * 0.6)
    return _place(out, clac, d * 0.8)


def _demarrage_bande(d, seed):
    """Demarrage de bande : le son part de tres grave et monte jusqu'a la vitesse normale, net sur la coupe."""
    m = int(SR * d)
    v = np.linspace(0.04, 1, m) ** 1.5
    x = _vitesse(_accord(d * 1.2, (130, 196, 262), seed), v) * np.linspace(0.2, 1, m) ** 1.5
    return _f(x, 'lowpass', 4000)


def _rembobinage(d, seed):
    """Bande qui rembobine : petits cris rapides qui montent + souffle de bande."""
    t = _t(d)
    m = len(t)
    f = np.zeros(m)
    seg = int(SR * 0.055)
    for k in range(0, m, seg):
        f[k:k + seg] = np.geomspace(500 + 60 * (k // seg), 2200 + 140 * (k // seg), len(f[k:k + seg]))
    x = _osc(f, 'tri') * 0.6 + _f(_bruit(d, seed), 'bandpass', (1000, 4000)) * 0.35
    x *= _env(m, d * 0.3, d * 0.25, 1.5)
    return _f(x, 'lowpass', 7000)


def _balayage(d, f0, f1, seed, bits=6, tenue=3):
    """Balayage numerique : son FM qui glisse, echantillons tenus (texture d'ecran), enveloppe montee/descente."""
    m = int(SR * d)
    f = _courbe(m, [(0, f0), (1, f1)], log=True)
    mod = np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR) * 2.0
    x = np.sin(2 * np.pi * np.cumsum(f) / SR + mod)
    x = _ecrase(x, bits, tenue) * 0.7 + _f(_bruit(d, seed), 'bandpass', (1500, 5000)) * 0.12
    return _f(x * _env(m, d * 0.55, d * 0.45, 1.6), 'lowpass', 7500, order=6)


def _chirp_donnees(d, seed):
    """Petits bips de donnees qui montent (ecran qui se remplit)."""
    rng = np.random.default_rng(seed)
    out = np.zeros(int(SR * d))
    k = 10
    for i in range(k):
        f = 600 * (2400 / 600) ** (i / (k - 1)) * (1 + rng.uniform(-0.04, 0.04))
        tt = _t(0.022)
        b = _osc(np.full(len(tt), f), 'tri') * _env(len(tt), 0.002, 0.012, 1.2) * (0.6 + 0.4 * i / k)
        _place(out, b, i * d * 0.85 / k)
    return _f(out, 'lowpass', 6500)


def _saccade(d, seed):
    """Glitch : tranches de 25-45 ms tirees au hasard (bourdon, bruit, silence), comme une image qui saute."""
    rng = np.random.default_rng(seed)
    out = np.zeros(int(SR * d))
    t0 = 0.0
    while t0 < d - 0.02:
        L = rng.uniform(0.025, 0.045)
        tt = _t(L)
        choix = rng.random()
        if choix < 0.45:
            g = _osc(np.full(len(tt), rng.choice([110, 165, 220, 440, 660])), 'saw')
        elif choix < 0.8:
            g = _f(_bruit(L, int(rng.integers(1000000))), 'bandpass', (600, 4500)) * 0.8
        else:
            g = np.zeros(len(tt))
        _place(out, g * _env(len(tt), 0.002, 0.004, 1), t0)
        t0 += L
    return _f(out * _env(len(out), 0.004, d * 0.3, 1.5), 'lowpass', 7000)


def _roulement(d, seed):
    """Roulement de glitch : le meme petit morceau repete de plus en plus vite jusqu'a la coupe."""
    grain_d = 0.05
    tt = _t(grain_d)
    grain = _osc(np.full(len(tt), 330), 'saw') * 0.7 + _f(_bruit(grain_d, seed), 'bandpass', (800, 3500)) * 0.4
    out = np.zeros(int(SR * d))
    t0, L, k = 0.0, 0.05, 0
    while t0 < d - 0.01:
        n = int(SR * L)
        g = grain[:n] * _env(n, 0.002, 0.004, 1) * (0.45 + 0.55 * t0 / d)
        _place(out, g, t0)
        t0 += L
        k += 1
        if k % 2 == 0:
            L = max(0.012, L * 0.78)
    return _f(out, 'lowpass', 6500)


def _bits(d, seed):
    """Bruit numerique ecrase (peu de bits), haché par morceaux."""
    rng = np.random.default_rng(seed)
    m = int(SR * d)
    x = _bruit(d, seed) * 0.6 + np.sin(2 * np.pi * 220 * _t(d))
    x = _ecrase(_f(x, 'lowpass', 3000), 3, 14)
    gate = (rng.random(m // 960 + 1) > 0.3).repeat(960)[:m].astype(float)
    gate = _f(gate, 'lowpass', 400)
    return _f(x * gate * _env(m, 0.003, d * 0.35, 1.4), 'lowpass', 6000)


def _papier(d, seed, f=(1500, 4500)):
    """Feuille qu'on fait glisser : souffle aigu grenu (froissement) avec petits craquements."""
    rng = np.random.default_rng(seed)
    m = int(SR * d)
    x = _bp_suivi(_bruit(d, seed), _courbe(m, [(0, f[0]), (1, f[1])], log=True), 0.8)
    grain = 0.55 + 0.45 * np.abs(_f(rng.standard_normal(m), 'lowpass', 70)) * 6
    crac = np.zeros(m)
    for i in rng.integers(0, m - 400, 14):
        crac[i:i + 200] += rng.standard_normal(200) * np.exp(-np.arange(200) / 30)
    x = x * np.clip(grain, 0, 1.6) + _f(crac, 'bandpass', (1500, 5000)) * 0.25
    return _f(x * _env(m, d * 0.55, d * 0.45, 1.8), 'lowpass', 7500)


def _page(d, seed):
    """Page qu'on tourne : battement de la feuille qui ralentit puis petite claque a la fin."""
    m = int(SR * d)
    x = _f(_bruit(d, seed), 'bandpass', (700, 3200))
    ff = _courbe(m, [(0, 32), (1, 12)])
    flutter = 0.5 + 0.5 * np.sin(2 * np.pi * np.cumsum(ff) / SR)
    x = x * flutter * _env(m, d * 0.6, d * 0.3, 1.6) * 0.7
    tt = _t(0.08)
    claque = _f(_bruit(0.08, seed + 2), 'lowpass', 2500) * np.exp(-tt * 60)
    return _f(_place(x, claque, d * 0.72), 'lowpass', 7000)


def _tissu(d, seed):
    """Tissu qu'on balaie : souffle grave et feutre, mouvement lent."""
    m = int(SR * d)
    x = _bp_suivi(_bruit(d, seed), _courbe(m, [(0, 300), (0.55, 1200), (1, 450)], log=True), 0.6)
    am = 0.7 + 0.3 * np.sin(2 * np.pi * 7 * _t(d) + 1.3)
    return _f(x * am * _env(m, d * 0.5, d * 0.5, 1.7), 'lowpass', 1800)


def _glisse_tonale(d, f0, f1, seed, air=0.2):
    """Glissando doux de deux sons purs (quinte), sans souffle de vent : transition musicale."""
    m = int(SR * d)
    f = _courbe(m, [(0, f0), (1, f1)], log=True)
    x = _osc(f) + 0.45 * _osc(f * 1.5) + 0.15 * _osc(f * 2)
    x += _f(_bruit(d, seed), 'bandpass', (900, 3500)) * air
    return _f(x * _env(m, d * 0.6, d * 0.4, 1.8), 'lowpass', 5000)


def _coupe_seche(seed):
    """Coupe seche : petit souffle puis claquement court avec un corps grave."""
    d = 0.26
    out = np.zeros(int(SR * d))
    _place(out, _souffle(0.09, [(0, 1200), (1, 4200)], 1.0, seed, att=0.95, courbe=2.5) * 0.35, 0)
    tt = _t(0.17)
    snap = _f(_bruit(0.17, seed + 1), 'bandpass', (1600, 5000)) * np.exp(-tt * 110)
    body = np.sin(2 * np.pi * (180 + 120 * np.exp(-tt * 60)) * tt) * np.exp(-tt * 28) * 0.8
    return _f(_place(out, snap + body, 0.085), 'lowpass', 8000)


def _bulle(d, f0, f1, vif, seed=0):
    """Bulle / pop rond : son pur qui glisse vers le haut et s'eteint vite."""
    t = _t(d)
    f = f1 + (f0 - f1) * np.exp(-t * 90)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * vif)
    if seed:
        x += _f(_bruit(d, seed), 'bandpass', (800, 3000)) * np.exp(-t * 300) * 0.25
    return _f(x, 'lowpass', 6000)


def _obturateur(seed):
    """Obturateur d'appareil photo : rideau, ressort, second rideau, petit choc grave."""
    d = 0.26
    out = np.zeros(int(SR * d))
    tt = _t(0.03)
    a = _f(_bruit(0.03, seed), 'bandpass', (2000, 5500)) * np.exp(-tt * 260)
    tr = _t(0.06)
    ressort = np.sin(2 * np.pi * 1900 * tr) * np.exp(-tr * 70) * 0.3
    b = _f(_bruit(0.03, seed + 1), 'bandpass', (1500, 4500)) * np.exp(-tt * 220) * 0.8
    tl = _t(0.08)
    choc = np.sin(2 * np.pi * 160 * tl) * np.exp(-tl * 45) * 0.6
    for x, at in ((a, 0.004), (ressort, 0.006), (b, 0.072), (choc, 0.074)):
        _place(out, x, at)
    return _f(out, 'lowpass', 8000)


def _modal(d, modes, seed, clic=0.4):
    """Petit objet frappe (bois, verre) : quelques resonances qui s'eteignent + attaque breve."""
    t = _t(d)
    x = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * r) for f, a, r in modes)
    x += _f(_bruit(d, seed), 'bandpass', (1500, 5000)) * np.exp(-t * 400) * clic
    return _f(x, 'lowpass', 8000)


def _choc(d, f0, f1, vif_corps, coupe, vif_bruit, seed, sat=1.4, snap=0.0):
    """Choc : corps grave dont la hauteur tombe + bruit filtre bref ; saturation douce (s'entend sur un telephone)."""
    t = _t(d)
    f = f1 + (f0 - f1) * np.exp(-t * 14)
    corps = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * vif_corps)
    x = corps + _f(_bruit(d, seed), 'lowpass', coupe) * np.exp(-t * vif_bruit) * 0.5
    if snap:
        x += _f(_bruit(d, seed + 1), 'bandpass', (1800, 5000)) * np.exp(-t * 120) * snap
    return _f(np.tanh(sat * x), 'lowpass', 7000)


def _cristal(d):
    """Ding de cristal doux (partiels sous 6 kHz)."""
    t = _t(d)
    x = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * r) for f, a, r in
            ((1318.5, 1.0, 4.0), (1975.5, 0.45, 6.0), (2637.0, 0.22, 9.0), (3951.0, 0.06, 14.0)))
    return x * _env(len(t), 0.003, 0.0, 1)


def _montee(d, f_bruit, tons, seed, courbe=2.2, trem=False, q=1.0):
    """Riser : bruit qui monte + sons qui montent, de plus en plus fort jusqu'a la fin (net sur l'appel a l'action)."""
    t = _t(d)
    m = len(t)
    x = _bp_suivi(_bruit(d, seed), _courbe(m, [(0, f_bruit[0]), (1, f_bruit[1])], log=True), q) * 0.7
    for f0, f1, a in tons:
        x += a * _osc(_courbe(m, [(0, f0), (1, f1)], log=True))
    x *= np.linspace(0, 1, m) ** courbe
    if trem:  # tremolo qui accelere : la tension monte
        x *= 0.75 + 0.25 * np.sin(2 * np.pi * np.cumsum(np.linspace(4, 18, m)) / SR)
    return _f(x, 'lowpass', 8000)


def _montee_numerique(d, seed):
    """Riser numerique : bips de plus en plus rapides et aigus + souffle qui monte."""
    out = np.zeros(int(SR * d))
    t0 = 0.0
    while t0 < d - 0.02:
        r = t0 / d
        f = 400 * 4 ** r
        tt = _t(0.03)
        _place(out, _osc(np.full(len(tt), f), 'tri') * _env(len(tt), 0.002, 0.02, 1.3) * (0.25 + 0.75 * r), t0)
        t0 += 0.125 * (1 - r) + 0.03
    m = len(out)
    out += _bp_suivi(_bruit(d, seed), _courbe(m, [(0, 400), (1, 4500)], log=True), 1.0) * np.linspace(0, 1, m) ** 2 * 0.5
    return _f(out, 'lowpass', 7500)


def _montee_cinema(d, seed):
    """Riser cinema : accord qui monte d'une octave, souffle et basse qui gonflent, tremolo qui accelere."""
    t = _t(d)
    m = len(t)
    g = np.geomspace(1, 2, m)
    x = sum(a * _osc(f * g) for f, a in ((110, 0.5), (165, 0.35), (220, 0.3), (330, 0.12)))
    x += _bp_suivi(_bruit(d, seed), _courbe(m, [(0, 150), (1, 5000)], log=True), 1.1) * 0.6
    x += np.tanh(2 * np.sin(2 * np.pi * 52 * t)) * 0.35
    x *= np.linspace(0, 1, m) ** 2.3
    x *= 0.78 + 0.22 * np.sin(2 * np.pi * np.cumsum(np.linspace(3, 16, m)) / SR)
    return _f(x, 'lowpass', 7500)


# nom -> (fabrique, attaque du fondu d'entree en s). Graines fixes : toujours le meme fichier.
COUPES = {
    # souffles et whooshes (transitions)
    'souffle-doux': (lambda: _pan(_souffle(0.42, [(0, 450), (1, 2200)], 0.9, 101, att=0.5, coupe=5500), np.linspace(-0.3, 0.3, int(SR * 0.42))), 0.002),
    'souffle-leger': (lambda: _pan(_souffle(0.3, [(0, 900), (1, 3800)], 1.0, 102, att=0.45, coupe=7000), np.linspace(0.25, -0.25, int(SR * 0.3))), 0.002),
    'souffle-ample': (lambda: _souffle(0.6, [(0, 250), (0.6, 1400), (1, 500)], 0.8, 103, att=0.55, coupe=4500), 0.002),
    'whoosh-aerien-court': (lambda: _pan(_souffle(0.32, [(0, 600), (1, 5200)], 0.7, 104, att=0.6, coupe=8500), np.linspace(-0.6, 0.6, int(SR * 0.32))), 0.002),
    'whoosh-aerien': (lambda: _pan(_souffle(0.62, [(0, 350), (0.55, 4200), (1, 900)], 0.8, 105, att=0.55, coupe=8500), np.linspace(-0.7, 0.7, int(SR * 0.62))), 0.002),
    'whoosh-aerien-long': (lambda: _pan(_souffle(0.95, [(0, 250), (0.6, 3000), (1, 600)], 0.8, 106, att=0.6, coupe=8000), np.linspace(-0.8, 0.8, int(SR * 0.95))), 0.002),
    'whoosh-sourd': (lambda: _souffle(0.5, [(0, 120), (0.55, 900), (1, 200)], 0.9, 107, att=0.55, coupe=2200), 0.002),
    'whoosh-tonal': (lambda: _souffle(0.55, [(0, 400), (0.55, 3000), (1, 700)], 1.2, 108, att=0.55, coupe=7000) * 0.8
                     + _glisse_tonale(0.55, 180, 520, 109, air=0) * 0.35, 0.002),
    'passage-gauche-droite': (lambda: _passage(0.7, [(0, 2600), (0.52, 1700), (1, 700)], 110, True, 0.2), 0.002),
    'passage-droite-gauche': (lambda: _passage(0.6, [(0, 3200), (0.52, 2000), (1, 800)], 112, False, 0.2), 0.002),
    'passage-eclair': (lambda: _passage(0.36, [(0, 5000), (0.5, 2500), (1, 900)], 114, True, 0.16), 0.002),
    'whoosh-chute': (lambda: _chute(0.36, 0.95, (95, 36), 116), 0.002),
    'whoosh-chute-court': (lambda: _chute(0.22, 0.6, (110, 45), 117), 0.002),
    'aspiration': (lambda: _inverse(0.8, 118, (4500, 700), 5.0), 0.002),
    'aspiration-longue': (lambda: _inverse(1.2, 119, (5000, 1200), 3.5), 0.002),
    'aspiration-tonale': (lambda: _inverse(1.0, 120, (3000, 600), 4.0, ((220, 0.5), (277.2, 0.35), (329.6, 0.3))), 0.002),
    'glisse-tonale-douce': (lambda: _glisse_tonale(0.45, 330, 660, 121), 0.002),
    'coupe-seche': (lambda: _coupe_seche(122), 0.002),
    'tissu-glisse': (lambda: _tissu(0.4, 123), 0.002),
    'papier-glisse': (lambda: _pan(_papier(0.45, 124), np.linspace(-0.4, 0.4, int(SR * 0.45))), 0.002),
    'papier-page': (lambda: _page(0.5, 125), 0.002),
    # bande, numerique, glitch
    'arret-bande': (lambda: _arret_bande(0.6, 126), 0.004),
    'arret-bande-court': (lambda: _arret_bande(0.36, 127, (147, 220, 294)), 0.004),
    'rembobinage': (lambda: _rembobinage(0.5, 128), 0.002),
    'balayage-numerique': (lambda: _pan(_balayage(0.3, 400, 2600, 129), np.linspace(-0.5, 0.5, int(SR * 0.3))), 0.002),
    'balayage-numerique-descendant': (lambda: _pan(_balayage(0.35, 2400, 300, 130), np.linspace(0.5, -0.5, int(SR * 0.35))), 0.002),
    'chirp-donnees': (lambda: _chirp_donnees(0.4, 131), 0.001),
    'glitch-saccade': (lambda: _saccade(0.4, 132), 0.002),
    'glitch-roulement': (lambda: _roulement(0.45, 133), 0.002),
    'glitch-bits': (lambda: _bits(0.3, 134), 0.002),
    # interface
    'ui-glisse': (lambda: _place(_souffle(0.28, [(0, 1200), (1, 3600)], 2.0, 135, att=0.6, coupe=7000) * 0.8, _tic(0.04, 2800, 136) * 0.35, 0.22), 0.002),
    'ui-glisse-tonale': (lambda: _glisse_tonale(0.22, 520, 1240, 137, air=0.12), 0.002),
    'ui-tic': (lambda: _tic(0.05, 3200, 138), 0.0005),
    'ui-tic-double': (lambda: _place(_place(np.zeros(int(SR * 0.11)), _tic(0.05, 3000, 139), 0), _tic(0.05, 3600, 140) * 0.8, 0.045), 0.0005),
    'ui-clic-doux': (lambda: _modal(0.07, ((900, 1.0, 90), (1800, 0.25, 140)), 141, clic=0.5), 0.0005),
    'ui-bulle': (lambda: _bulle(0.12, 350, 1100, 30), 0.001),
    'obturateur': (lambda: _obturateur(142), 0.0005),
    # pops et petits objets (mots forts, apparitions)
    'pop-doux': (lambda: _bulle(0.12, 780, 520, 35, 143), 0.001),
    'pop-bulle': (lambda: _bulle(0.1, 300, 1500, 45), 0.001),
    'pop-bouchon': (lambda: _modal(0.14, ((480, 1.0, 40), (1150, 0.3, 70)), 144, clic=0.9), 0.0005),
    'pop-goutte': (lambda: _bulle(0.16, 700, 1800, 28), 0.001),
    'tap-bois': (lambda: _modal(0.18, ((380, 1.0, 40), (1050, 0.5, 60), (2200, 0.2, 90)), 145, clic=0.5), 0.0005),
    # impacts (preuves, chiffres)
    'impact-leger': (lambda: _choc(0.45, 150, 95, 12, 3500, 45, 146), 0.0005),
    'impact-mat': (lambda: _choc(0.55, 85, 55, 8, 900, 25, 147, sat=1.8), 0.0005),
    'impact-coup-sec': (lambda: _choc(0.6, 70, 45, 6, 2500, 30, 148, sat=2.0, snap=0.6), 0.0005),
    'impact-sub': (lambda: _choc(1.0, 90, 38, 3, 1500, 40, 149, sat=2.4), 0.0005),
    'ding-cristal': (lambda: _cristal(0.9), 0.003),
    # risers (avant l'appel a l'action)
    'riser-doux': (lambda: _montee(0.8, (300, 2800), ((220, 440, 0.35), (330, 660, 0.25)), 150), 0.002),
    'riser-numerique': (lambda: _montee_numerique(1.0, 151), 0.002),
    'riser-souffle': (lambda: _pan(_montee(1.2, (200, 6000), (), 152, courbe=2.4, q=0.9), np.linspace(-0.3, 0.3, int(SR * 1.2))), 0.002),
    'riser-cinema': (lambda: _montee_cinema(1.6, 153), 0.002),
    'riser-bande': (lambda: _demarrage_bande(0.9, 154), 0.002),
}

# Sons Kenney (CC0) remis au niveau des autres : nom -> fichier sous assets/sfx/kenney (titres : banque.SONS_EDITEUR)
KENNEY = {
    'kenney-selection': 'interface-sounds/select_003.ogg',
    'kenney-interrupteur': 'interface-sounds/switch_003.ogg',
    'kenney-bascule': 'interface-sounds/toggle_002.ogg',
    'kenney-survol': 'ui-audio/rollover4.ogg',
    'kenney-verre': 'interface-sounds/glass_002.ogg',
    'kenney-depot': 'interface-sounds/drop_002.ogg',
    'kenney-pep': 'digital-audio/pepSound1.ogg',
    'kenney-phaser': 'digital-audio/phaserUp3.ogg',
    'kenney-saut': 'digital-audio/phaseJump2.ogg',
    'kenney-descente': 'digital-audio/highDown.ogg',
    'kenney-bonus': 'digital-audio/powerUp3.ogg',
    'kenney-impact-doux': 'impact-sounds/impactSoft_medium_001.ogg',
    'kenney-impact-bois': 'impact-sounds/impactPlank_medium_000.ogg',
}


# ---------------------------------------------------------------- mesures (memes regles que banque._mesure)


def _mono(x):
    x = np.asarray(x, dtype=float)
    return x.mean(axis=1) if x.ndim == 2 else x


def niveau(x):
    """Crete RMS sur des fenetres de 50 ms (dB), comme banque._mesure (RMS du tout si le son dure moins de 50 ms)."""
    m = _mono(x)
    w = int(SR * 0.05)
    n = len(m) // w
    rms = float(np.sqrt((m[:n * w].reshape(n, w) ** 2).mean(axis=1)).max()) if n else float(np.sqrt((m ** 2).mean()))
    return 20 * math.log10(rms + 1e-12)


def pic(x):
    """Instant (s) ou l'enveloppe (RMS sur 20 ms centree sur l'instant, silence avant le debut) atteint 90 % de son maximum :
    le moment qui doit tomber sur la coupe. Un clic ou un impact (attaque immediate) a son pic a 0."""
    m = _mono(x)
    w, h = int(SR * 0.02), int(SR * 0.0025)
    m = np.concatenate([np.zeros(w // 2), m, np.zeros(w // 2)])
    k = (len(m) - w) // h + 1
    idx = np.arange(w)[None, :] + h * np.arange(k)[:, None]
    env = np.sqrt((m[idx] ** 2).mean(axis=1))
    i = int(np.argmax(env >= 0.9 * env.max()))
    return round(i * h / SR, 3)


def sonie(x):
    """Sonie de crete : ponderation K (filtres de la norme BS.1770 a 48 kHz), moyenne glissante sur 100 ms, maximum,
    en LUFS (-0,691 + 10 log10 de la somme des canaux). Un son plus court que 100 ms est moyenne sur 100 ms."""
    from scipy.signal import lfilter
    x = np.asarray(x, dtype=float)
    if x.ndim == 1 or x.shape[1] == 1:  # mono (fichier Kenney mono compris) : meme son sur les deux canaux
        x = np.repeat(x.reshape(len(x), 1), 2, axis=1)
    y = lfilter([1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585], x, axis=0)
    y = lfilter([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621], y, axis=0)
    ms = (y ** 2).sum(axis=1)
    w = int(SR * 0.1)
    c = np.convolve(ms, np.ones(w) / w, 'valid') if len(ms) >= w else np.array([ms.sum() / w])
    return -0.691 + 10 * math.log10(float(c.max()) + 1e-12)


def aigus(x):
    """Part de l'energie au-dessus de 10 kHz (0-1)."""
    m = _mono(x)
    s = np.abs(np.fft.rfft(m)) ** 2
    f = np.fft.rfftfreq(len(m), 1 / SR)
    return float(s[f > 10000].sum() / (s.sum() + 1e-12))


def mesure(path):
    """{duree, crete (dBFS), niveau (dB, banque), sonie (LUFS), pic (s), aigus (0-1), dc, bord} d'un fichier son."""
    x, sr = sf.read(str(path), always_2d=True, dtype='float64')
    if sr != SR:
        raise ValueError(f'{path} : {sr} Hz (48000 attendu)')
    return {'duree': round(len(x) / SR, 3), 'crete': round(20 * math.log10(float(np.abs(x).max()) + 1e-12), 2),
            'niveau': round(niveau(x), 2), 'sonie': round(sonie(x), 2), 'pic': pic(x), 'aigus': round(aigus(x), 4),
            'dc': round(float(np.abs(x.mean(axis=0)).max()), 5),
            'bord': round(float(max(np.abs(x[:4]).max(), np.abs(x[-4:]).max())), 4)}


def gain_sonie(s):
    """Gain (SFX_GAIN) qui amene un son de sonie s a SONIE ; 1 s'il y est deja (a 0,2 dB pres)."""
    g = 10 ** ((SONIE - s) / 20)
    return 1.0 if abs(20 * math.log10(g)) < 0.2 else round(min(4.0, g), 2)


def _finir(x, entree=0.002, sortie=0.012):
    """Stereo, sans composante continue, fondus d'entree et de sortie (aucun clic), ramene a SONIE sans depasser -1 dBFS."""
    x = np.asarray(x, dtype=float)
    if x.ndim == 1 or x.shape[1] == 1:  # mono (fichier Kenney mono compris) : meme son sur les deux canaux
        x = np.repeat(x.reshape(len(x), 1), 2, axis=1)
    x = _f(x, 'highpass', 22)
    n = len(x)
    a, r = min(n // 3, max(2, int(SR * entree))), min(n // 2, max(2, int(SR * sortie)))
    e = np.ones(n)
    e[:a] = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, a))
    e[-r:] = np.minimum(e[-r:], 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, r)))
    e[0] = e[-1] = 0.0
    x = x * e[:, None]
    k = min(10 ** ((SONIE - sonie(x)) / 20), CRETE_MAX / (np.abs(x).max() + 1e-12))
    return (x * k).astype(np.float32)


def _kenney(rel):
    """Son Kenney (ogg) -> 48 kHz, silences du debut et de la fin retires."""
    from math import gcd
    from scipy.signal import resample_poly
    x, sr = sf.read(str(ROOT / 'assets/sfx/kenney' / rel), always_2d=True, dtype='float64')
    if sr != SR:
        g = gcd(SR, sr)
        x = resample_poly(x, SR // g, sr // g, axis=0)
    m = np.abs(x).max(axis=1)
    seuil = m.max() * 10 ** (-50 / 20)
    on = np.nonzero(m > seuil)[0]
    debut = max(0, on[0] - int(SR * 0.002))
    fin = min(len(x), on[-1] + int(SR * 0.02))
    return x[debut:fin]


def _ecrire_wav(path, x):
    """Ecrit seulement si le contenu change (dates des fichiers stables : la banque ne se reconstruit pas pour rien)."""
    tmp = path.with_name(f'{path.stem}.{os.getpid()}.tmp.wav')
    sf.write(tmp, x, SR, subtype='PCM_16')
    if path.is_file() and path.read_bytes() == tmp.read_bytes():
        tmp.unlink()
        return False
    os.replace(tmp, path)
    return True


def creer(noms=None):
    """Cree les sons de coupe (COUPES + KENNEY) -> {nom: mesure + gain}. noms : sous-ensemble (sinon tous)."""
    OUT.mkdir(parents=True, exist_ok=True)
    out = {}
    for nom, (fabrique, attaque) in COUPES.items():
        if noms and nom not in noms:
            continue
        _ecrire_wav(OUT / f'{nom}.wav', _finir(fabrique(), entree=attaque))
        out[nom] = mesure(OUT / f'{nom}.wav')
    for nom, rel in KENNEY.items():
        if noms and nom not in noms:
            continue
        _ecrire_wav(OUT / f'{nom}.wav', _finir(_kenney(rel), entree=0.001, sortie=0.015))
        out[nom] = mesure(OUT / f'{nom}.wav')
    for m in out.values():
        m['gain'] = gain_sonie(m['sonie'])
    return out


def _licence():
    lignes = ["Sons synthetises par l'editeur (engine/editeur/sfxgen.py). Creations originales, libres de tout droit tiers.",
              '', 'Exception : les fichiers « kenney-*.wav » sont des copies remises au niveau des autres (48 kHz, fondus,',
              'silences retires) de sons Kenney.nl, licence CC0 1.0 (domaine public) :']
    for nom, rel in KENNEY.items():
        pack = rel.split('/')[0]
        lignes.append(f'  {nom}.wav <- assets/sfx/kenney/{rel} (licence : assets/sfx/kenney/{pack}/License.txt)')
    return '\n'.join(lignes) + '\n'


def main_creer():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, make in SOUNDS.items():
        if not (OUT / f'{name}.wav').is_file():  # les sons d'origine ne sont jamais reecrits (reels deja exportes)
            sf.write(OUT / f'{name}.wav', make(), SR, subtype='PCM_16')
            print(name)
    mesures = creer()
    lic = _licence()
    f = OUT / 'LICENCE.txt'
    if not f.is_file() or f.read_text(encoding='utf-8') != lic:
        f.write_text(lic, encoding='utf-8')
    gains = {k: m['gain'] for k, m in mesures.items() if m['gain'] != 1.0}
    print(json.dumps({'sons': len(mesures), 'gains': gains}, ensure_ascii=False))


# ---------------------------------------------------------------- planche de spectrogrammes (controle a l'oeil)


def planche(noms=None, sortie=None):
    """Spectrogramme de chaque son (0-16 kHz, ligne a 10 kHz, trait au pic) -> chemin du PNG."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    noms = noms or [*COUPES, *KENNEY]
    sortie = Path(sortie or ROOT / 'runtime/cache/tmp/sons/planche-sons.png')
    sortie.parent.mkdir(parents=True, exist_ok=True)
    cols = 6
    rows = math.ceil(len(noms) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3.2, rows * 2.1), squeeze=False)
    for ax, nom in zip(axes.flat, noms):
        x, _ = sf.read(str(OUT / f'{nom}.wav'), always_2d=True, dtype='float64')
        m = mesure(OUT / f'{nom}.wav')
        from matplotlib import mlab
        mono = x.mean(axis=1) + 1e-9
        nfft = 1024 if len(mono) > 2048 else 256
        spec, _, _ = mlab.specgram(mono, NFFT=nfft, Fs=SR, noverlap=nfft * 3 // 4)
        haut = 10 * math.log10(float(spec.max()) + 1e-20)
        ax.specgram(mono, NFFT=nfft, Fs=SR, noverlap=nfft * 3 // 4, cmap='magma', vmin=haut - 70, vmax=haut)
        ax.set_ylim(0, 16000)
        ax.axhline(10000, color='cyan', lw=0.6, ls='--')
        ax.axvline(m['pic'], color='lime', lw=0.9)
        eff = m['sonie'] + 20 * math.log10(gain_sonie(m['sonie']))
        ax.set_title(f"{nom}\n{m['duree']:.2f} s · {eff:.1f} LUFS · aigus {m['aigus'] * 100:.1f} %", fontsize=7)
        ax.tick_params(labelsize=5)
    for ax in list(axes.flat)[len(noms):]:
        ax.axis('off')
    fig.tight_layout()
    fig.savefig(sortie, dpi=72)
    plt.close(fig)
    return sortie


# ---------------------------------------------------------------- familles de sons (styles/sons-transitions.json)

_cache = {}


def familles(path=None):
    """Catalogue des familles (relu si le fichier change)."""
    p = Path(path or FAMILLES)
    cle = (str(p), p.stat().st_mtime_ns if p.is_file() else 0)
    if _cache.get('cle') != cle:
        _cache.update(cle=cle, data=json.loads(p.read_text(encoding='utf-8')))
    return _cache['data']


def famille_du_style(reel, data=None):
    """Famille « auto » : celle que le style de montage choisit lui-meme (sfx.famille d'un style perso), sinon celle du style
    dans le catalogue (ou du style d'ou vient un style perso), sinon celle de son son de coupe, sinon la famille par defaut."""
    data = data or familles()
    ids = {f['id'] for f in data['familles']}
    styles = data.get('styles') or {}
    tpl = str(reel.get('template') or '')
    t = {}
    f = ROOT / 'styles/montage' / f'{tpl}.json'
    if re.fullmatch(r'[A-Za-z0-9_-]{1,80}', tpl) and f.is_file():
        try:
            t = json.loads(f.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            t = {}
    propre = (t.get('sfx') or {}).get('famille') if isinstance(t.get('sfx'), dict) else None
    for choix in (propre, styles.get(tpl), styles.get(str(t.get('depuis') or '')),
                  (data.get('sons') or {}).get((reel.get('sfx') or {}).get('transition')), data.get('defaut')):
        if choix in ids:
            return choix
    return data['familles'][0]['id']


def reserve(famille_id, data=None):
    """Reserve (« pool ») d'une famille pour le reel : [{name, pic, gain, role}] (POOL_MAX au plus)."""
    data = data or familles()
    fam = next((f for f in data['familles'] if f['id'] == famille_id), None)
    if not fam:
        raise ValueError(f'Famille de sons inconnue : {famille_id}.')
    pool = []
    for role in ROLES:
        for s in (fam.get('sons') or {}).get(role) or []:
            pool.append({'name': s['name'], 'pic': float(s.get('pic', 0)), 'gain': float(s.get('gain', 1)), 'role': role})
    return pool[:POOL_MAX]


def appliquer_famille(reel, famille=None, varier=None, avant=None, data=None):
    """Famille de sons du reel (sur place) : sfx.famille, sfx.pool (et sfx.varier si donne). famille None = garder le
    choix explicite d'avant (avant = sfx du reel avant un changement de style), sinon « auto » (famille du style). Ne
    touche ni aux sons du style (transition, highlight, cta, start), ni aux bruitages poses a la main.
    -> {famille, famille_utilisee, nom, sons, varier}"""
    data = data or familles()
    ids = {f['id'] for f in data['familles']}
    prec = avant if isinstance(avant, dict) else (reel.get('sfx') or {})
    if famille is None:
        famille = prec.get('famille') if prec.get('famille') in ids else 'auto'
    famille = str(famille)
    if famille != 'auto' and famille not in ids:
        raise ValueError(f"Famille de sons inconnue : {famille} (choix : auto, {', '.join(sorted(ids))}).")
    if varier is None and isinstance(prec.get('varier'), bool):
        varier = prec['varier']
    utilisee = famille_du_style(reel, data) if famille == 'auto' else famille
    sfx = reel.setdefault('sfx', {'enabled': True, 'transition': None, 'highlight': None, 'highlightGap': 4, 'cta': None,
                                  'start': None, 'volume': 0.6})
    sfx['famille'] = famille
    sfx['pool'] = reserve(utilisee, data)
    if varier is not None:
        sfx['varier'] = bool(varier)
    nom = next(f['nom'] for f in data['familles'] if f['id'] == utilisee)
    return {'famille': famille, 'famille_utilisee': utilisee, 'nom': nom, 'sons': len(sfx['pool']),
            'varier': sfx.get('varier', True) is not False}


def _version(project_dir, rid):
    """Garde le reel d'avant dans versions/<rid>/ (meme format que le serveur : « AAAA-MM-JJTHH-MM-SS nom.json »)."""
    from . import montage
    src = montage.reel_path(project_dir, rid)
    brut = src.read_bytes()
    d = Path(project_dir) / 'versions' / str(rid)
    d.mkdir(parents=True, exist_ok=True)
    miennes = sorted(f for f in d.glob('*.json') if NOM_VERSION in f.name)
    if miennes and miennes[-1].read_bytes() == brut:
        return miennes[-1].name
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S')
    name = f'{stamp} {NOM_VERSION}.json'
    k = 2
    while (d / name).exists():
        name = f'{stamp} {NOM_VERSION} ({k}).json'
        k += 1
    tmp = d / f'{name}.{os.getpid()}.tmp'
    tmp.write_bytes(brut)
    os.replace(tmp, d / name)
    return name


def sons(project_dir, rid, famille, varier=None):
    """Ligne de commande « sons » : famille de sons d'un reel, version « avant » gardee. -> resume (dict)."""
    from . import montage
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', str(rid)):
        raise ValueError('Identifiant de version invalide.')
    if not montage.reel_path(project_dir, rid).is_file():
        raise ValueError(f'Montage introuvable : {rid}.')
    data = familles()
    if famille != 'auto' and famille not in {f['id'] for f in data['familles']}:
        raise ValueError(f'Famille de sons inconnue : {famille}.')
    version = _version(project_dir, rid)
    res = {}
    montage.update(project_dir, rid, lambda r: res.update(appliquer_famille(r, famille, varier, data=data)))
    return {'ok': True, **res, 'version': version}


def ecrire_familles(data, path=None):
    """Ecrit le catalogue des familles, un son par ligne (lisible et facile a retoucher a la main)."""
    texte = json.dumps(data, ensure_ascii=False, indent=1)
    texte = re.sub(r'\{\n\s+("name"[^{}]*?)\n\s+\}', lambda m: '{' + ' '.join(x.strip() for x in m.group(1).split('\n')) + '}', texte)
    Path(path or FAMILLES).write_text(texte + '\n', encoding='utf-8')


def remesurer_familles(path=None):
    """Remesure pic et duree de chaque son des familles (le reste du fichier est garde) -> nombre de sons."""
    p = Path(path or FAMILLES)
    data = json.loads(p.read_text(encoding='utf-8'))
    n = 0
    for fam in data['familles']:
        for lst in (fam.get('sons') or {}).values():
            for s in lst:
                m = mesure(OUT / f"{s['name']}.wav")
                s['pic'], s['duree'] = m['pic'], m['duree']
                n += 1
    ecrire_familles(data, p)
    return n


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else 'creer'
    if cmd == 'creer':
        return main_creer()
    if cmd == 'mesures':
        print(json.dumps({n: mesure(OUT / f'{n}.wav') for n in [*COUPES, *KENNEY]}, ensure_ascii=False))
        return 0
    if cmd == 'planche':
        print(planche())
        return 0
    if cmd == 'familles':
        print(json.dumps({'sons': remesurer_familles()}))
        return 0
    if cmd == 'sons':
        import argparse
        ap = argparse.ArgumentParser(prog='editeur.sfxgen sons')
        ap.add_argument('projet')
        ap.add_argument('--reel', default='script')
        ap.add_argument('--famille', default='auto')
        ap.add_argument('--varier', choices=['oui', 'non'])
        a = ap.parse_args(argv[1:])
        try:
            res = sons(a.projet, a.reel, a.famille, None if a.varier is None else a.varier == 'oui')
        except (ValueError, OSError) as e:
            print(json.dumps({'ok': False, 'erreur': str(e)}, ensure_ascii=False))
            return 1
        print(json.dumps(res, ensure_ascii=False))
        return 0
    print(f'Commande inconnue : {cmd} (creer, mesures, planche, familles, sons).', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main() or 0)
