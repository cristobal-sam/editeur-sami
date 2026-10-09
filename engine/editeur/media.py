"""Acces aux medias via FFmpeg : sondage, audio decode, images echantillonnees."""
import json
import os
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(os.environ.get('EDITEUR_ROOT') or Path(__file__).resolve().parents[2])
FFMPEG = str(ROOT / 'tools/ffmpeg/bin/ffmpeg.exe')
FFPROBE = str(ROOT / 'tools/ffmpeg/bin/ffprobe.exe')
VIDEO_EXT = {'.mp4', '.mov', '.m4v', '.mkv', '.avi', '.mts', '.webm'}
IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp'}

# Rotation a appliquer (degres, sens horaire) -> filtre FFmpeg
ROTATION_FILTER = {0: '', 90: 'transpose=1', 180: 'transpose=1,transpose=1', 270: 'transpose=2'}


def run(args, **kw):
    return subprocess.run(args, capture_output=True, check=True, **kw)


def probe(path):
    out = run([FFPROBE, '-v', 'error', '-show_entries',
               'stream=codec_type,codec_name,width,height,r_frame_rate:stream_side_data=rotation:format=duration',
               '-of', 'json', str(path)]).stdout
    data = json.loads(out)
    video = next(s for s in data['streams'] if s['codec_type'] == 'video')
    num, den = map(int, video['r_frame_rate'].split('/'))
    rotation = int((video.get('side_data_list') or [{}])[0].get('rotation', 0) or 0)
    return {'duration': float(data['format']['duration']), 'width': video['width'], 'height': video['height'],
            'fps': num / den, 'fps_ratio': video['r_frame_rate'], 'container_rotation': rotation,
            'has_audio': any(s['codec_type'] == 'audio' for s in data['streams'])}


def decode_audio(path, sr=16000):
    """Audio mono float32 a `sr` Hz (vide si la video n'a pas de piste son : drone, capture d'ecran...)."""
    if not probe(path)['has_audio']:
        return np.zeros(0, dtype=np.float32)
    raw = run([FFMPEG, '-v', 'error', '-i', str(path), '-vn', '-ac', '1', '-ar', str(sr), '-f', 'f32le', '-']).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def sample_frames(path, fps=2.0, width=320, rotate=0, start=None, duration=None):
    """Images RGB echantillonnees (liste de (temps, ndarray HxWx3))."""
    info = probe(path)
    rot = ROTATION_FILTER[rotate]
    w, h = (info['height'], info['width']) if rotate in (90, 270) else (info['width'], info['height'])
    height = int(round(width * h / w / 2) * 2)
    vf = ','.join(filter(None, [rot, f'fps={fps}', f'scale={width}:{height}']))
    args = [FFMPEG, '-v', 'error']
    if start is not None:
        args += ['-ss', f'{start:.3f}']
    args += ['-i', str(path)]
    if duration is not None:
        args += ['-t', f'{duration:.3f}']
    args += ['-vf', vf, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    raw = run(args).stdout
    size = width * height * 3
    t0 = start or 0.0
    return [(t0 + i / fps, np.frombuffer(raw[i * size:(i + 1) * size], np.uint8).reshape(height, width, 3))
            for i in range(len(raw) // size)]


def optimized(path, rotate, cache_dir):
    """Media optimise d'une prise : redresse, cadre d'origine conserve (1080 px sur le petit cote), 30 i/s,
    image cle toutes les 0,5 s (saut instantane dans l'apercu), son AAC lisible par le navigateur.
    Le recadrage vers le format du reel (9:16, 16:9, 4:5, 1:1) se fait a l'affichage, en suivant le sujet.
    Cree une seule fois ; sert a l'apercu ET a l'export."""
    out = Path(cache_dir) / f'{cache_name(path)}.mp4'
    stamp = out.with_suffix('.key')
    info = probe(path)
    w, h = (info['height'], info['width']) if rotate in (90, 270) else (info['width'], info['height'])
    vertical_916 = abs(w / h - 9 / 16) < 0.01
    # une prise deja en 9:16 donne le meme fichier qu'avant (cle v1) : pas de re-encodage inutile
    key = f'{file_key(path)}-{rotate}-' + ('v1' if vertical_916 else 'v2-cadre')
    if out.exists() and stamp.exists() and stamp.read_text() == key:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    size = 'scale=1080:1920' if vertical_916 else ('scale=-2:1080' if w >= h else 'scale=1080:-2')
    vf = ','.join(filter(None, [ROTATION_FILTER[rotate], size, 'setsar=1', 'fps=30', 'format=yuv420p']))
    tmp = out.with_suffix('.part.mp4')
    encoders = (['-c:v', 'h264_nvenc', '-preset', 'p5', '-rc', 'vbr', '-cq', '17', '-b:v', '0', '-bf', '0'],
                ['-c:v', 'libx264', '-preset', 'fast', '-crf', '16', '-bf', '0'])
    for enc in encoders:  # GPU, sinon processeur
        try:
            run([FFMPEG, '-v', 'error', '-y', '-i', str(path), '-vf', vf, *enc, '-g', '15',
                 '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2', '-movflags', '+faststart', str(tmp)])
            break
        except subprocess.CalledProcessError:
            continue
    tmp.replace(out)
    stamp.write_text(key)
    return out


def clean_voice(path, cache_dir, declip=False):
    """Voix nettoyee d'une prise pour l'APERCU : meme debruitage que l'export (RNNoise + expandeur doux), passe-haut,
    niveau ramene vers -16 LUFS. Creee une fois (cache) ; l'apercu fait ainsi entendre ce qui sera livre."""
    import re
    out = Path(cache_dir) / f'{cache_name(path)}.voix.m4a'
    stamp = out.with_name(out.name + '.key')
    key = f'{file_key(path)}-v2-{int(bool(declip))}'
    if out.exists() and stamp.exists() and stamp.read_text() == key:
        return out
    if not probe(path)['has_audio']:
        return None
    rnn = ROOT / 'models/rnnoise/sh.rnnn'
    den = "arnndn=m='%s':mix=0.9" % str(rnn).replace('\\', '/').replace(':', '\\:') if rnn.exists() else 'afftdn=nr=12:nf=-40'
    dur = probe(path)['duration']
    # -4 dB avant RNNoise (cretes au-dela du plein niveau = debordement) ; silence ajoute puis recoupe (trame finale NaN)
    chain = ','.join(filter(None, ['adeclip' if declip else '', 'highpass=f=80', 'volume=-4dB', 'apad=pad_dur=0.2', den,
                                   'agate=threshold=0.015:ratio=2:range=0.1:attack=5:release=300:knee=4', f'atrim=0:{dur:.3f}']))
    meas = subprocess.run([FFMPEG, '-hide_banner', '-nostats', '-i', str(path), '-vn', '-af', chain + ',ebur128', '-f', 'null', '-'],
                          capture_output=True, text=True, encoding='utf-8', errors='replace')
    found = re.findall(r'I:\s+(-?[\d.]+) LUFS', meas.stderr)
    level = float(found[-1]) if found else -16.0
    gain = max(-15.0, min(20.0, -16.0 - level)) if level > -70 else 0.0
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + '.part.m4a')
    run([FFMPEG, '-v', 'error', '-y', '-i', str(path), '-vn', '-af', f'{chain},volume={gain:.2f}dB,alimiter=limit=0.95:level=false',
         '-c:a', 'aac', '-b:a', '160k', '-ar', '48000', '-ac', '2', str(tmp)])
    tmp.replace(out)
    stamp.write_text(key)
    return out


def optimized_image(path, cache_dir, max_side=2160):
    """Image fixe (plan de coupe) : JPEG redresse de 2160 px au plus, servi a l'apercu et a l'export."""
    from PIL import Image, ImageOps
    out = Path(cache_dir) / f'{cache_name(path)}.jpg'
    stamp = out.with_suffix('.key')
    key = f'{file_key(path)}-img1'
    if out.exists() and stamp.exists() and stamp.read_text() == key:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        im.thumbnail((max_side, max_side))
        im.save(out, 'JPEG', quality=92)
    stamp.write_text(key)
    return out


def list_videos(folder):
    return sorted(p for p in Path(folder).rglob('*') if p.suffix.lower() in VIDEO_EXT)


def cache_name(path):
    """Nom de cache unique : deux prises « 3.MP4 » dans des dossiers differents ne se melangent pas."""
    import hashlib
    p = Path(path).resolve()
    return f'{p.stem}-{hashlib.sha1(str(p).lower().encode()).hexdigest()[:8]}'


def file_key(path):
    st = Path(path).stat()
    return f'{st.st_size}-{int(st.st_mtime)}'
