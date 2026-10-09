"""Export final d'un reel stylise (Remotion + mixage FFmpeg), sans passer par l'interface."""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .media import ROOT


def export_reel(project_dir, variant=None, on_progress=print):
    project_dir = Path(project_dir)
    reel = json.loads((project_dir / 'reels' / f"{variant or 'script'}.json").read_text(encoding='utf-8'))
    out_dir = Path(reel.get('delivery') or ROOT / 'livraisons')
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{reel['title']} - FINAL.mp4"
    node = shutil.which('node') or 'node'
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, dir=os.environ.get('TEMP'), encoding='utf-8') as f:
        json.dump({'reel': reel, 'out': str(out)}, f, ensure_ascii=False)
        job = f.name
    try:
        proc = subprocess.Popen([node, str(ROOT / 'remotion/render.mjs'), job], cwd=ROOT / 'remotion',
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        error, last = None, -1
        for line in proc.stdout:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get('error'):
                error = e['error']
            elif e.get('stage'):
                on_progress(f"   {e['stage']}...")
            elif 'progress' in e and int(e['progress'] * 10) != last:
                last = int(e['progress'] * 10)
                on_progress(f'   {last * 10} %')
        proc.wait()
        if proc.returncode or error:
            raise RuntimeError(error or proc.stderr.read()[-800:])
        if not out.exists() or out.stat().st_size == 0:
            raise RuntimeError("L'export n'a produit aucun fichier vidéo.")
    finally:
        os.unlink(job)
    return out
