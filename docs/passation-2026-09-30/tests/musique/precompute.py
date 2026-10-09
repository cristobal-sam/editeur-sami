"""Spectres mel (64 bandes) et chroma (puissance, additifs) de chaque cas et de chaque musique de la bibliotheque."""
import json
import subprocess
from pathlib import Path

import librosa
import numpy as np

ROOT = Path('D:/Tools/editeur_sami')
OUT = ROOT / 'runtime/cache/tmp/musique-eval'
FF = str(ROOT / 'tools/ffmpeg/bin/ffmpeg.exe')
SR, NFFT, HOP = 22050, 2048, 512
MEL = librosa.filters.mel(sr=SR, n_fft=NFFT, n_mels=64, fmin=30, fmax=11000)
CHR = librosa.filters.chroma(sr=SR, n_fft=NFFT)


def decode(p, sr=SR):
    raw = subprocess.run([FF, '-v', 'error', '-i', str(p), '-vn', '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def spec(y):
    P = np.abs(librosa.stft(y, n_fft=NFFT, hop_length=HOP)) ** 2
    return (MEL @ P).astype(np.float32), (CHR @ P).astype(np.float32)


cases = json.loads((OUT / 'cas.json').read_text(encoding='utf-8'))
data = {}
for c in cases:
    m, ch = spec(decode(OUT / 'cas' / f"{c['id']}.m4a"))
    data[f"{c['id']}|mel"], data[f"{c['id']}|chr"] = m, ch
for m in json.loads((ROOT / 'styles/musiques.json').read_text(encoding='utf-8')):
    y = decode(ROOT / 'assets/music' / f"{m['id']}.ogg")
    a, b = spec(y)
    data[f"lib-{m['id']}|mel"], data[f"lib-{m['id']}|chr"] = a, b
np.savez_compressed(OUT / 'spectres.npz', **data)
print(len(data))
