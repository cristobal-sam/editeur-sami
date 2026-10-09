"""Retouches du montage (partagees par tous les reels du projet) : changer de prise, deplacer une coupe."""
import json
from pathlib import Path

from . import transcribe
from .media import ROOT


def _clips(project):
    yield from project['timeline']
    for v in project.get('variants', []):
        yield v['clip']


def find_clip(project, clip_id):
    clip = next((c for c in _clips(project) if c['id'] == clip_id), None)
    if not clip:
        raise KeyError(f'Plan introuvable : {clip_id}')
    return clip


def _words_between(project, source, t0, t1):
    """Mots de la transcription complete de la prise entre deux instants (pour une coupe elargie)."""
    src = project['sources'][source]
    data = transcribe.transcribe(src['path'], ROOT / 'projects/_cache/transcripts')
    return [w for w in data['words'] if w['end'] > t0 + 0.02 and w['start'] < t1 - 0.02]


def set_take(project_dir, clip_id, choice):
    path = Path(project_dir) / 'project.json'
    project = json.loads(path.read_text(encoding='utf-8'))
    clip = find_clip(project, clip_id)
    take = clip['takes'][choice]
    clip.update(choice=choice, **{k: take[k] for k in ('source', 'in', 'out', 'text', 'words', 'flags')})
    path.write_text(json.dumps(project, ensure_ascii=False, indent=1), encoding='utf-8')


def trim(project_dir, clip_id, d_in=0.0, d_out=0.0):
    path = Path(project_dir) / 'project.json'
    project = json.loads(path.read_text(encoding='utf-8'))
    clip = find_clip(project, clip_id)
    duration = project['sources'][clip['source']]['duration']
    new_in = round(min(max(0.0, clip['in'] + d_in), clip['out'] - 0.3), 3)
    new_out = round(max(min(duration, clip['out'] + d_out), new_in + 0.3), 3)
    clip['in'], clip['out'] = new_in, new_out
    clip['words'] = _words_between(project, clip['source'], new_in, new_out)
    clip['text'] = ' '.join(w['w'] for w in clip['words'])
    # La prise en cours garde ses nouveaux points de coupe si on y revient plus tard.
    if 'takes' in clip:
        clip['takes'][clip.get('choice', 0)].update(**{k: clip[k] for k in ('in', 'out', 'text', 'words')})
    path.write_text(json.dumps(project, ensure_ascii=False, indent=1), encoding='utf-8')
