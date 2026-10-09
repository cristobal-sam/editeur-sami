"""Livraison : tous les montages et toutes les parties d'un script dans UN dossier,
avec des noms explicites et un LISEZ-MOI qui dit ce qu'est chaque video."""
import json
import re
from pathlib import Path

from . import render
from .media import ROOT

CTA = re.compile(r'\b(bouton|cliquez|cliquer|appuy\w*|lien|r[ée]serv\w*|abonne\w*|commentez)\b', re.I)


def _safe(name, limit=110):
    name = re.sub(r'[<>:"/\\|?*\n\r\t]', '', name).replace('’', "'")
    name = re.sub(r'\s+', ' ', name).strip(' .')
    return name[:limit].rstrip(' .,')


def _opening(text, words=7):
    w = re.sub(r'\s+', ' ', text).strip().split(' ')
    return ' '.join(w[:words]).rstrip(',;:.')


def _role(block, index, count):
    label = block['label']
    if index == 0 or 'hook' in label.lower():
        return 'HOOK'
    if index == count - 1 and CTA.search(block['text']):
        return "Appel à l'action"
    return '' if re.fullmatch(r'bloc \d+', label, re.I) else label


def deliver(project_dirs, script_path):
    out_dir = ROOT / 'livraisons' / _safe(Path(script_path).stem)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = ROOT / 'projects/_cache/livraisons' / f'{out_dir.name}.json'
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    if manifest_file.exists():  # on ne supprime que ce que la livraison precedente avait cree
        for f in json.loads(manifest_file.read_text(encoding='utf-8'))['files']:
            (out_dir / f['file']).unlink(missing_ok=True)
    files = []

    def emit(project_dir, name, kind, what, variant=None, timeline=None):
        out = out_dir / f'{_safe(name)}.mp4'
        _, duration = render.render(project_dir, variant=variant, out=out, timeline=timeline)
        project = json.loads((Path(project_dir) / 'project.json').read_text(encoding='utf-8'))
        clips = timeline or render.resolve_timeline(project, variant)
        sources = sorted({project['sources'][c['source']]['name'] for c in clips})
        files.append({'file': out.name, 'type': kind, 'description': what, 'duration': duration, 'sources': sources,
                      'text': ' '.join(c['text'] for c in clips)})
        print(f'   {out.name}  ({duration:.1f} s)')

    for pdir in project_dirs:
        pdir = Path(pdir)
        p = json.loads((pdir / 'project.json').read_text(encoding='utf-8'))
        video, blocks = p.get('label') or p['name'], p['script']['blocks']
        hook_variants = [v for v in p['variants'] if v['replaces_block']]

        # 1. Montages complets
        emit(pdir, f'{video} - 0 COMPLET' + (' - Hook original' if hook_variants else ''), 'montage complet',
             'Montage complet' + (' avec le hook du script' if hook_variants else ''))
        for n, v in enumerate(hook_variants, 1):
            emit(pdir, f'{video} - 0 COMPLET - Hook alternatif {n} ({_opening(v["clip"]["text"], 5)})',
                 'montage complet', f'Montage complet avec le hook alternatif {n}', variant=v['id'])

        # 2. Parties, dans l'ordre du script
        for bi, b in enumerate(blocks):
            clips = [c for c in p['timeline'] if c['block'] == b['id']]
            role = _role(b, bi, len(blocks))
            if clips:
                title = f"{role} original" if role == 'HOOK' and hook_variants else role
                name = f'{video} - {bi + 1} {title + " - " if title else ""}{_opening(b["text"])}'
                emit(pdir, name, 'partie', f'Partie {bi + 1} du script : {role or b["label"]}', timeline=clips)
            if bi == 0:
                for n, v in enumerate(hook_variants, 1):
                    emit(pdir, f'{video} - 1 HOOK alternatif {n} - {_opening(v["clip"]["text"])}', 'partie',
                         f'Hook alternatif {n} (texte hors script)', timeline=[v['clip']])
        p['delivery'] = str(out_dir)
        (pdir / 'project.json').write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding='utf-8')

    manifest_file.write_text(json.dumps({'script': str(script_path), 'files': files}, ensure_ascii=False, indent=1),
                             encoding='utf-8')
    lines = [f'LIVRAISON - {Path(script_path).stem}', '',
             'Chaque video est prete a publier (1080x1920, 30 i/s, son normalise a -14 LUFS).',
             '"0 COMPLET" = montage entier. Les numeros suivants = parties dans l\'ordre du script.', '']
    for f in files:
        lines += [f"{f['file']}", f"   {f['description']} - {f['duration']:.1f} s",
                  f"   Prise(s) d'origine : {', '.join(f['sources'])}",
                  f"   Texte : {f['text'][:220]}{'...' if len(f['text']) > 220 else ''}", '']
    (out_dir / 'LISEZ-MOI.txt').write_text('\n'.join(lines), encoding='utf-8-sig')
    return out_dir
