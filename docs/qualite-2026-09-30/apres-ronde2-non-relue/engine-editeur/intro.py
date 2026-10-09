"""Titre d'ouverture 3D : rendu par Blender (logiciel local), converti en video transparente (WebM VP9)."""
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from .media import FFMPEG, ROOT, run

# Blender local : copie dans tools/ si elle existe, sinon celle deja installee sur le poste (lecture seule).
BLENDERS = [ROOT / 'tools/blender/blender.exe',
            Path(r'D:\Y0U\tools\portable\blender\blender-4.5.10-windows-x64\blender.exe')]


def blender():
    return next((b for b in BLENDERS if b.exists()), None)


def make_intro(project_dir, text, font='Anton.ttf', color='#FFD400', seconds=2.5, width=1080, height=1920):
    exe = blender()
    if not exe:
        raise RuntimeError('Blender introuvable (copier Blender dans tools/blender/).')
    frames = max(10, round(seconds * 30))
    key = hashlib.sha1(json.dumps([text, font, color, frames, width, height]).encode()).hexdigest()[:10]
    out = Path(project_dir) / 'intros' / f'intro-{key}.webm'
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / 'runtime/cache/tmp') as tmp:
        run([str(exe), '--background', '--factory-startup', '--python', str(ROOT / 'engine/blender_titre.py'), '--',
             text, str(ROOT / 'assets/fonts' / font), color, tmp, str(width), str(height), str(frames)])
        run([FFMPEG, '-v', 'error', '-y', '-framerate', '30', '-i', str(Path(tmp) / 'f_%04d.png'),
             '-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p', '-b:v', '0', '-crf', '28', '-row-mt', '1', '-auto-alt-ref', '0', str(out)])
    return out
