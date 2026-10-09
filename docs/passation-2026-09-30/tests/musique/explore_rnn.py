"""RNNoise comme estimation de la voix : retard, part de musique retiree, qualite du masque."""
import random
import subprocess
import sys

import numpy as np
import librosa

sys.path.insert(0, 'D:/Tools/editeur_sami/runtime/cache/tmp/musique-eval')
import build_set as B  # noqa: E402

FF = B.FF
RNN = 'D:/Tools/editeur_sami/models/rnnoise/sh.rnnn'


def arnndn(y, sr=44100):
    p = subprocess.run([FF, '-v', 'error', '-f', 'f32le', '-ar', str(sr), '-ac', '1', '-i', '-', '-af',
                        f"aresample=48000,arnndn=m='{RNN.replace(':', chr(92) + ':')}',aresample={sr}", '-f', 'f32le', '-'],
                       input=y.astype(np.float32).tobytes(), capture_output=True)
    assert p.returncode == 0, p.stderr.decode()
    out = np.frombuffer(p.stdout, np.float32).copy()
    print("  non finis :", int((~np.isfinite(out)).sum()), "sur", len(out))
    out = np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)
    return np.concatenate([out[441:], np.zeros(441, np.float32)])


rng = random.Random(7)
vy, vw = B.edited_voice([B.V1 / '2.MP4', B.V1 / '3.MP4'], 25, rng)
vy = vy * 10 ** ((-16 - B.lufs(vy)) / 20)
for track in ['electro', 'emotion', 'energique']:
    my, _ = B.music_variant(track, 'exact', len(vy) / B.SR)
    my = np.pad(my, (0, max(0, len(vy) - len(my))))[:len(vy)]
    my = my * 10 ** ((-16 - 19 - B.lufs(my)) / 20)
    mix = vy + my
    v_est = arnndn(mix)
    n = min(len(v_est), len(mix))
    # retard
    seg = slice(B.SR * 5, B.SR * 10)
    xc = np.correlate(v_est[seg], vy[seg], 'full')
    lag = int(np.argmax(xc)) - (seg.stop - seg.start - 1)
    print(track, 'retard', lag, 'echantillons')
    sr = 22050
    V = np.abs(librosa.stft(librosa.resample(vy[:n], orig_sr=44100, target_sr=sr), n_fft=2048, hop_length=512)) ** 2
    M = np.abs(librosa.stft(librosa.resample(my[:n], orig_sr=44100, target_sr=sr), n_fft=2048, hop_length=512)) ** 2
    X = np.abs(librosa.stft(librosa.resample(mix[:n], orig_sr=44100, target_sr=sr), n_fft=2048, hop_length=512)) ** 2
    E = np.abs(librosa.stft(librosa.resample(v_est[:n], orig_sr=44100, target_sr=sr), n_fft=2048, hop_length=512)) ** 2
    true_m = M / (M + V + 1e-12)  # part de musique vraie par case
    est_m = np.clip(1 - E / (X + 1e-12), 0, 1)
    music_dom = true_m > 0.5
    print(f'  cases dominees par la musique : {music_dom.mean():.2f} ; masque RNNoise (>0,5) : precision '
          f'{(music_dom & (est_m > 0.5)).sum() / max(1, (est_m > 0.5).sum()):.2f}, rappel {(music_dom & (est_m > 0.5)).sum() / max(1, music_dom.sum()):.2f}')
    # energie de musique dans l'estimation de voix (fuite)
    print(f'  musique restante dans la voix estimee : {10 * np.log10((np.minimum(E, M)).sum() / M.sum()):.1f} dB')
    # spectre moyen (bandes mel) de la musique vraie vs estimee
    mel = librosa.filters.mel(sr=sr, n_fft=2048, n_mels=32)
    lt_true = 10 * np.log10(mel @ M.mean(axis=1) + 1e-12)
    lt_mix = 10 * np.log10(mel @ X.mean(axis=1) + 1e-12)
    Pm = np.maximum(X - E, 0.05 * X)
    lt_sub = 10 * np.log10(mel @ Pm.mean(axis=1) + 1e-12)
    w = est_m > 0.6
    lt_msk = 10 * np.log10(mel @ ((X * w).sum(axis=1) / np.maximum(w.sum(axis=1), 1)) + 1e-12)
    for name, lt in (('melange', lt_mix), ('soustraction', lt_sub), ('masque', lt_msk)):
        d = (lt - lt.mean()) - (lt_true - lt_true.mean())
        print(f'  ecart de forme spectrale {name:<13}: {np.sqrt((d ** 2).mean()):.1f} dB')
