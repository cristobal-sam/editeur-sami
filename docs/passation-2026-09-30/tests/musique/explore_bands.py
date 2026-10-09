"""Par bande mel : part des images ou la musique domine la voix (pistes separees)."""
import random
import sys

import librosa
import numpy as np

sys.path.insert(0, 'D:/Tools/editeur_sami/runtime/cache/tmp/musique-eval')
import build_set as B  # noqa: E402

sr = 22050
rng = random.Random(3)
voices = {'sami1': B.edited_voice([B.V1 / '2.MP4', B.V1 / '3.MP4'], 25, rng),
          'bingo': B.edited_voice([B.BINGO / '19A-2.mov', B.BINGO / '12G-3.mov'], 25, rng)}
mel = librosa.filters.mel(sr=sr, n_fft=2048, n_mels=40, fmin=30, fmax=11000)
freqs = librosa.mel_frequencies(n_mels=40, fmin=30, fmax=11000)
tot = {}
for vn, (vy, vw) in voices.items():
    vy = vy * 10 ** ((-16 - B.lufs(vy)) / 20)
    V = mel @ np.abs(librosa.stft(librosa.resample(vy, orig_sr=44100, target_sr=sr), n_fft=2048, hop_length=512)) ** 2
    for track in ['electro', 'emotion', 'energique', 'cinematique', 'lofi', 'luxe']:
        my, _ = B.music_variant(track, 'exact', len(vy) / B.SR)
        my = np.pad(my, (0, max(0, len(vy) - len(my))))[:len(vy)]
        my = my * 10 ** ((-16 - 19 - B.lufs(my)) / 20)
        M = mel @ np.abs(librosa.stft(librosa.resample(my, orig_sr=44100, target_sr=sr), n_fft=2048, hop_length=512)) ** 2
        n = min(V.shape[1], M.shape[1])
        dom = (M[:, :n] > V[:, :n]).mean(axis=1)
        tot.setdefault(vn, []).append(dom)
for vn, d in tot.items():
    d = np.mean(d, axis=0)
    print(vn, ' '.join(f'{f:.0f}:{x:.2f}' for f, x in zip(freqs, d)))
