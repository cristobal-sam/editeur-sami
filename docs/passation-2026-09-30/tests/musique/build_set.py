"""Banc d'essai musique : voix reelles (rushs + mots en cache) melangees aux musiques de la bibliotheque."""
import json
import random
import re
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path('D:/Tools/editeur_sami')
FF = str(ROOT / 'tools/ffmpeg/bin/ffmpeg.exe')
OUT = ROOT / 'runtime/cache/tmp/musique-eval'
SR = 44100
TR = ROOT / 'projects/_cache/transcripts'
BINGO = ROOT / 'media/rushs/test-pratique/EditStock Free Sample From Bingo Night/Narrative - Bingo NIght'
V1 = ROOT / 'media/rushs/Vidéo 1'
V2 = ROOT / 'media/rushs/Vidéo 2'


def run(args):
    return subprocess.run(args, capture_output=True, check=True)


def decode(path, sr=SR, ss=None, t=None, af=None):
    a = [FF, '-v', 'error']
    if ss is not None:
        a += ['-ss', str(ss)]
    a += ['-i', str(path)]
    if t is not None:
        a += ['-t', str(t)]
    if af:
        a += ['-af', af]
    a += ['-vn', '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-']
    return np.frombuffer(run(a).stdout, np.float32).copy()


def write_wav(path, y, sr=SR):
    p = subprocess.run([FF, '-v', 'error', '-y', '-f', 'f32le', '-ar', str(sr), '-ac', '1', '-i', '-', str(path)],
                       input=y.astype(np.float32).tobytes(), capture_output=True)
    assert p.returncode == 0, p.stderr


def lufs(y, sr=SR):
    p = subprocess.run([FF, '-hide_banner', '-nostats', '-f', 'f32le', '-ar', str(sr), '-ac', '1', '-i', '-', '-af', 'ebur128',
                        '-f', 'null', '-'], input=y.astype(np.float32).tobytes(), capture_output=True)
    found = re.findall(r'I:\s+(-?[\d.]+) LUFS', p.stderr.decode('utf-8', 'replace'))
    return float(found[-1])


def words_of(stem_prefix):
    for f in TR.glob('*.transcript.json'):
        d = json.loads(f.read_text(encoding='utf-8'))
        if Path(d['source'].replace('\\', '/')).name == stem_prefix:
            return d['words']
    raise SystemExit(f'pas de transcription pour {stem_prefix}')


def edited_voice(files, target, rng, loose=False):
    """Voix montee facon pub : phrases mises bout a bout (coupes franches), mots recales."""
    out, words, t0 = [], [], 0.0
    for f in files:
        y = decode(f)
        ws = [w for w in words_of(f.name) if w['end'] - w['start'] < 3]
        groups, cur = [], []
        for w in ws:
            if cur and w['start'] - cur[-1]['end'] > (0.6 if loose else 0.35):
                groups.append(cur)
                cur = []
            cur.append(w)
        if cur:
            groups.append(cur)
        for g in groups:
            a = max(0.0, g[0]['start'] - 0.08)
            b = g[-1]['end'] + (rng.uniform(0.25, 0.7) if loose else rng.uniform(0.08, 0.22))
            seg = y[int(a * SR):int(b * SR)].copy()
            if len(seg) < SR * 0.3:
                continue
            fade = int(0.01 * SR)
            seg[:fade] *= np.linspace(0, 1, fade)
            seg[-fade:] *= np.linspace(1, 0, fade)
            for w in g:
                words.append({'w': w['w'], 'start': round(t0 + w['start'] - a, 3), 'end': round(t0 + w['end'] - a, 3)})
            out.append(seg)
            t0 += len(seg) / SR
            if t0 >= target:
                break
        if t0 >= target:
            break
    y = np.concatenate(out)
    return y, words


def music_variant(track, kind, dur):
    f = ROOT / 'assets/music' / f'{track}.ogg'
    if kind == 'exact':
        return decode(f, ss=15, t=dur), 1.0
    if kind == 'shiftA':  # +1 demi-ton, tempo x1,038, aigus -3 dB
        return decode(f, ss=38, t=dur * 1.1, af='aresample=44100,asetrate=44100*1.0595,aresample=44100,atempo=0.98,treble=g=-3:f=5000')[:int(dur * SR)], 1.0595 * 0.98
    if kind == 'shiftB':  # -1 demi-ton, tempo x0,963, basses +3 dB
        return decode(f, ss=4, t=dur * 1.1, af='aresample=44100,asetrate=44100*0.9439,aresample=44100,atempo=1.02,bass=g=3:f=100')[:int(dur * SR)], 0.9439 * 1.02
    raise ValueError(kind)


def master(y, name):
    """Mixage final facon pub : -14 LUFS, limiteur, AAC 128k (comme une video livree)."""
    g = -14.0 - lufs(y)
    wav = OUT / 'tmp.wav'
    write_wav(wav, y)
    run([FF, '-v', 'error', '-y', '-i', str(wav), '-af', f'volume={g:.2f}dB,alimiter=limit=0.89:level=false', '-c:a', 'aac',
         '-b:a', '128k', str(OUT / 'cas' / f'{name}.m4a')])
    wav.unlink()


def main():
    rng = random.Random(7)
    (OUT / 'cas').mkdir(parents=True, exist_ok=True)
    moods = [m['id'] for m in json.loads((ROOT / 'styles/musiques.json').read_text(encoding='utf-8'))]
    bpm = {m['id']: m['bpm'] for m in json.loads((ROOT / 'styles/musiques.json').read_text(encoding='utf-8'))}
    voices = {
        'sami1': edited_voice([V1 / '2.MP4', V1 / '3.MP4', V1 / '4.MP4', V1 / '5.MP4'], 36, rng),
        'sami2': edited_voice([V2 / '1.MP4', V2 / '3.MP4', V2 / '4.MP4', V2 / '5.MP4', V2 / 'VIDÉO 2 - V1 .MP4'], 36, rng),
        'bingo': edited_voice([BINGO / '19A-2.mov', BINGO / '12G-3.mov', BINGO / '12H-3.mov', BINGO / '18A-1.mov'], 36, rng),
    }
    cases = []
    for vn, (vy, vw) in voices.items():
        vy = vy * 10 ** ((-16 - lufs(vy)) / 20)
        dur = len(vy) / SR
        # parole seule : montee serree, pauses naturelles, et avec un souffle de fond (ventilation)
        master(vy, f'{vn}-parole')
        cases.append({'id': f'{vn}-parole', 'voix': vn, 'musique': False, 'mood': None, 'tempo': None, 'words': vw, 'duree': dur})
        from scipy.signal import lfilter
        wn = np.random.default_rng(1).standard_normal(len(vy))
        br = lfilter([1], [1, -0.98], wn)
        noise = (br / br.std() + 0.3 * wn).astype(np.float32)
        noise *= 10 ** ((-16 - 32 - lufs(noise)) / 20)
        master(vy + noise, f'{vn}-parole-souffle')
        cases.append({'id': f'{vn}-parole-souffle', 'voix': vn, 'musique': False, 'mood': None, 'tempo': None, 'words': vw, 'duree': dur})
        for k, track in enumerate(moods):
            for j, kind in enumerate(['exact', 'shiftA', 'shiftB']):
                my, fac = music_variant(track, kind, dur)
                my = np.pad(my, (0, max(0, len(vy) - len(my))))[:len(vy)]
                level = [-16, -19, -22][(k + j + list(voices).index(vn)) % 3]
                my = my * 10 ** ((-16 + level - lufs(my)) / 20)
                cid = f'{vn}-{track}-{kind}'
                master(vy + my, cid)
                cases.append({'id': cid, 'voix': vn, 'musique': True, 'mood': track, 'tempo': round(bpm[track] * fac, 1),
                              'niveau': level, 'variante': kind, 'words': vw, 'duree': dur})
        vy2, vw2 = edited_voice({'sami1': [V1 / 'HOOK.MP4', V1 / 'HOOK (2).MP4', V1 / 'Hook (4).MP4'],
                                 'sami2': [V2 / 'VIDÉO 2 - V2.MP4', V2 / '3.MP4'],
                                 'bingo': [BINGO / '19B-2.mov', BINGO / '19C-2.mov', BINGO / '20E-3.mov']}[vn], 30, rng, loose=True)
        vy2 = vy2 * 10 ** ((-16 - lufs(vy2)) / 20)
        master(vy2, f'{vn}-parole-pauses')
        cases.append({'id': f'{vn}-parole-pauses', 'voix': vn, 'musique': False, 'mood': None, 'tempo': None, 'words': vw2,
                      'duree': len(vy2) / SR})
    # musique seule (montage visuel sans voix)
    for track in moods:
        for kind in ['shiftA', 'shiftB']:
            my, fac = music_variant(track, kind, 30)
            master(my, f'seule-{track}-{kind}')
            cases.append({'id': f'seule-{track}-{kind}', 'voix': None, 'musique': True, 'mood': track, 'tempo': round(bpm[track] * fac, 1),
                          'variante': kind, 'words': [], 'duree': len(my) / SR})
    (OUT / 'cas.json').write_text(json.dumps(cases, ensure_ascii=False), encoding='utf-8')
    print(len(cases), 'cas')


if __name__ == '__main__':
    main()
