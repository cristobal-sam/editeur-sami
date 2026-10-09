import json
from pathlib import Path

import librosa
import numpy as np

ROOT = Path('D:/Tools/editeur_sami')
for m in json.loads((ROOT / 'styles/musiques.json').read_text(encoding='utf-8')):
    y, sr = librosa.load(str(ROOT / 'assets/music' / f"{m['id']}.ogg"), sr=22050, mono=True)
    env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=512)
    bt = float(np.atleast_1d(librosa.beat.beat_track(onset_envelope=env, sr=sr, hop_length=512)[0])[0])
    # tempogram : pic d'autocorrelation, sans a priori
    tg = librosa.autocorrelate(env - env.mean())
    lags = np.arange(len(tg))
    bpm_axis = 60 * sr / 512 / np.maximum(lags, 1)
    ok = (bpm_axis >= 60) & (bpm_axis <= 180)
    best = bpm_axis[ok][np.argmax(tg[ok])]
    # battements : ecart median entre temps
    _, beats = librosa.beat.beat_track(onset_envelope=env, sr=sr, hop_length=512, start_bpm=m['bpm'])
    ibi = np.median(np.diff(librosa.frames_to_time(beats, sr=sr, hop_length=512)))
    print(f"{m['id']:<12} meta {m['bpm']:4d} | beat_track {bt:6.1f} | autocorr {best:6.1f} | beats(prior meta) {60 / ibi:6.1f}")
