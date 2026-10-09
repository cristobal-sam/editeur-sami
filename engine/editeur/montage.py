"""Outils communs aux modules qui lisent un reel : calcul du montage (le meme que l'apercu, via
remotion/segments.mjs), chemins, phrases."""
import json
import re
import subprocess
import tempfile
from pathlib import Path

from .media import ROOT


def reel_path(project_dir, rid):
    return Path(project_dir) / 'reels' / f'{rid or "script"}.json'


def load(project_dir, rid):
    return json.loads(reel_path(project_dir, rid).read_text(encoding='utf-8'))


def save(project_dir, rid, reel):
    """Ecriture sure : fichier temporaire puis remplacement (une coupure ne laisse jamais un reel a moitie ecrit)."""
    import os
    path = reel_path(project_dir, rid)
    tmp = path.with_name(f'{path.name}.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(reel, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(tmp, path)


def update(project_dir, rid, fn):
    """Relit le reel juste avant d'ecrire (l'interface a pu le modifier pendant un long calcul), applique fn
    (qui modifie le reel sur place) et l'enregistre : on n'ecrase jamais les retouches faites entre-temps."""
    reel = load(project_dir, rid)
    fn(reel)
    save(project_dir, rid, reel)
    return reel


def compute(reel, light=False):
    """Montage calcule par remotion/src/timeline.ts : {duration, video, audio, words, pacing, ...}."""
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, dir=ROOT / 'runtime/cache/tmp', encoding='utf-8') as f:
        json.dump(reel, f, ensure_ascii=False)
        name = f.name
    try:
        out = subprocess.run(['node', str(ROOT / 'remotion/segments.mjs'), name] + (['--duree'] if light else []),
                             capture_output=True, text=True, encoding='utf-8', check=True).stdout
        return json.loads(out)
    finally:
        Path(name).unlink(missing_ok=True)


def proxy_path(src):
    p = Path(src['proxy'])
    return p if p.is_absolute() else ROOT / p


def sentences(clip):
    """Phrases d'un plan : [(i0, i1)] indices de mots (ponctuation ou pause > 0,5 s)."""
    words = [w for w in clip['words']]
    out, start = [], 0
    for k in range(1, len(words)):
        gap = words[k]['start'] - words[k - 1]['end']
        if re.search(r'[.!?…]$', words[k - 1]['w']) or gap > 0.5:
            out.append((start, k - 1))
            start = k
    if words:
        out.append((start, len(words) - 1))
    return out
