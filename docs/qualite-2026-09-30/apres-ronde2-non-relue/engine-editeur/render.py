"""Rendu d'un projet (project.json) en MP4 vertical avec FFmpeg (encodage GPU NVENC si disponible).
Les rushs ne sont jamais modifies ; le projet peut etre retouche puis rendu a nouveau."""
import json
from pathlib import Path

from .media import FFMPEG, ROTATION_FILTER, run

TIGHT_GAP, KEEP_BEFORE, KEEP_AFTER = 0.45, 0.12, 0.15


def resolve_timeline(project, variant=None):
    """Plans du montage ; une variante remplace les plans de son bloc (ex. hook alternatif)."""
    timeline = project['timeline']
    v = next((x for x in project.get('variants', []) if x['id'] == variant), None) if variant else None
    if not v:
        return timeline
    out, placed = [], False
    for clip in timeline:
        if clip['block'] == v['replaces_block']:
            if not placed:
                out.append(v['clip'])
                placed = True
            continue
        out.append(clip)
    return out if placed else [v['clip']] + timeline


def segments(clip):
    """Decoupe un plan aux pauses internes trop longues (resserrage facon reel)."""
    if not clip.get('tighten') or len(clip['words']) < 2:
        return [(clip['in'], clip['out'], clip['words'])]
    segs, cur_start, cur_words = [], clip['in'], [clip['words'][0]]
    for a, b in zip(clip['words'], clip['words'][1:]):
        if b['start'] - a['end'] > TIGHT_GAP:
            segs.append((cur_start, a['end'] + KEEP_AFTER, cur_words))
            cur_start, cur_words = b['start'] - KEEP_BEFORE, []
        cur_words.append(b)
    segs.append((cur_start, clip['out'], cur_words))
    return segs


def _nvenc_available():
    try:
        run([FFMPEG, '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=256x256:d=0.1',
             '-c:v', 'h264_nvenc', '-f', 'null', '-'])
        return True
    except Exception:
        return False


def render(project_dir, variant=None, out=None, timeline=None):
    """Rend le montage complet (ou `timeline`, une selection de plans) vers `out`."""
    project_dir = Path(project_dir)
    project = json.loads((project_dir / 'project.json').read_text(encoding='utf-8'))
    fmt, audio = project['format'], project['audio']
    W, H, FPS = fmt['width'], fmt['height'], fmt['fps']
    parts, captions, segs, t_out = [], [], [], 0.0
    for clip in timeline or resolve_timeline(project, variant):
        src = project['sources'][clip['source']]
        for start, end, words in segments(clip):
            end = start + max(1, round((end - start) * FPS)) / FPS  # duree en images entieres : pas de derive
            parts.append((src, start, end))
            segs.append({'clip': clip['id'], 'source': clip['source'], 'src_in': round(start, 4),
                         'src_out': round(end, 4), 'out_start': round(t_out, 4)})
            captions += [{'w': w['w'], 'start': round(t_out + w['start'] - start, 3),
                          'end': round(t_out + w['end'] - start, 3), 'clip': clip['id']} for w in words]
            t_out += end - start

    args, filters = [FFMPEG, '-v', 'error', '-y'], []
    for i, (src, start, end) in enumerate(parts):
        args += ['-ss', f'{start:.3f}', '-t', f'{end - start:.3f}', '-i', src['path']]
        vf = ','.join(filter(None, [ROTATION_FILTER[src['rotate']],
                                    f'scale={W}:{H}:force_original_aspect_ratio=increase', f'crop={W}:{H}',
                                    'setsar=1', f'fps={FPS}', 'format=yuv420p']))
        d = end - start
        filters.append(f'[{i}:v]{vf}[v{i}]')
        filters.append(f'[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,'
                       f'afade=t=in:d=0.012,afade=t=out:st={max(0, d - 0.015):.3f}:d=0.015[a{i}]')
    filters.append(''.join(f'[v{i}][a{i}]' for i in range(len(parts))) + f'concat=n={len(parts)}:v=1:a=1[v][araw]')
    chain = ['adeclip' if audio.get('declip') else '', 'highpass=f=70',
             f"arnndn=m='{_rnnoise()}'" if audio.get('denoise') else '',
             f"loudnorm=I={audio.get('loudness_lufs', -14)}:TP=-1.5:LRA=11", 'aresample=48000']
    filters.append('[araw]' + ','.join(filter(None, chain)) + '[a]')
    video = (['-c:v', 'h264_nvenc', '-preset', 'p6', '-tune', 'hq', '-rc', 'vbr', '-cq', '20', '-b:v', '0', '-maxrate', '12M', '-bufsize', '24M']
             if _nvenc_available() else ['-c:v', 'libx264', '-preset', 'medium', '-crf', '18'])
    out = Path(out) if out else project_dir / 'exports' / f"{project['name']}{'-' + variant if variant else ''}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    args += ['-filter_complex', ';'.join(filters), '-map', '[v]', '-map', '[a]', *video,
             '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(out)]
    run(args)
    # Minutage mot par mot de la video exportee (pour les sous-titres), garde avec le projet.
    cap = project_dir / 'captions' / f'{out.stem}.json'
    cap.parent.mkdir(exist_ok=True)
    cap.write_text(json.dumps({'duration': round(t_out, 4), 'fps': FPS, 'segments': segs, 'words': captions},
                              ensure_ascii=False, indent=1), encoding='utf-8')
    return out, round(t_out, 2)


def _rnnoise():
    from .media import ROOT
    return str(ROOT / 'models/rnnoise/sh.rnnn').replace('\\', '/').replace(':', '\\:')
