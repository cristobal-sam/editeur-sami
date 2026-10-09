"""Mesure des mots en couleur : regles (et IA en option) sur des COPIES en memoire des reels (rien n'est ecrit).
usage : python mesure.py avant|nouveau [--llm fichier1,fichier2] [--sortie fichier.json]"""
import copy
import json
import os
import sys
from pathlib import Path

ROOT = Path('D:/Tools/editeur_sami')
os.environ['EDITEUR_ROOT'] = str(ROOT)
which = sys.argv[1]
if which == 'avant':
    sys.path.insert(0, str(ROOT / 'docs/passation-2026-09-30/avant'))
else:
    sys.path.insert(0, str(ROOT / 'engine'))
import editeur  # noqa
from editeur import reel as R  # noqa
from editeur.script import normalize  # noqa

print('module :', R.__file__)
REELS = ['projects/video1/reels/v1.json', 'projects/video1/reels/script.json', 'projects/video2/reels/script.json',
         'projects/scriptbingonightvideo1/reels/v1.json']
LLM = []
out_file = None
args = sys.argv[2:]
while args:
    a = args.pop(0)
    if a == '--llm':
        LLM = args.pop(0).split(',')
    elif a == '--sortie':
        out_file = args.pop(0)
    elif a == '--reels':
        REELS = args.pop(0).split(',')


def groups(words, max_words, tighten=True):
    """Meme decoupage que pages() de timeline.ts, pour un plan."""
    res, cur = [], []
    for i, w in enumerate(words):
        if w.get('hide') or w.get('cut') or not w['w'].strip():
            continue
        if cur:
            p = words[cur[-1]]
            gap = w['start'] - p['end']
            if tighten and gap > 0.45:
                gap = 0.27
            if len(cur) >= max_words or p['w'].rstrip().endswith(('.', '!', '?', '…')) or gap > 0.35:
                res.append(cur)
                cur = []
        cur.append(i)
    if cur:
        res.append(cur)
    return res


def show(words, hl, max_words):
    g = groups(words, max_words)
    parts = []
    for grp in g:
        parts.append(' '.join(('[' + words[i]['w'] + ']' if i in hl else words[i]['w']) for i in grp))
    covered = sum(1 for grp in g if any(i in hl for i in grp))
    runs, cur = [], []
    for i in sorted(hl):
        if cur and i != cur[-1] + 1:
            runs.append(cur)
            cur = []
        cur.append(i)
    if cur:
        runs.append(cur)
    blocs = [' '.join(words[i]['w'] for i in r) for r in runs if len(r) > 1]
    stop = [words[r[0]]['w'] for r in runs if len(r) == 1 and normalize(words[r[0]]['w']).strip("'") in R.STOP]
    return ' | '.join(parts), len(g), covered, blocs, stop


def rule_hl(clips, max_words, lang):
    if hasattr(R, 'reel_highlights'):
        return R.reel_highlights(clips, max_words=max_words, language=lang)
    return {c['id']: R.auto_highlights(c['words']) for c in clips}


result = {}
for f in REELS:
    reel = copy.deepcopy(json.loads((ROOT / f).read_text(encoding='utf-8')))
    mw = int(os.environ.get('MW') or (reel.get('style') or {}).get('maxWords', 3))
    project = json.loads((ROOT / f).parent.parent.joinpath('project.json').read_text(encoding='utf-8'))
    lang = R.language_of(project) if hasattr(R, 'language_of') else 'fr'
    print(f'\n===== {f}  (maxWords={mw}, langue={lang})')
    res = {'regles': {}, 'ia': {}}
    hls = rule_hl(reel['clips'], mw, lang)
    ed = None
    if f in LLM:
        from editeur import llm
        with llm.session():
            import time
            t0 = time.time()
            if hasattr(R, 'reel_highlights'):
                ed = R._editorial(reel['clips'], {c['id'] for c in reel['clips']}, want_banner=True, language=lang,
                                  max_words=mw, brands=R._brands(reel))
                print('  propositions IA :', {k: [' '.join(reel['clips'][[c['id'] for c in reel['clips']].index(k)]['words'][i]['w'] for i in p) for p in v] for k, v in (ed or {}).get('picks', {}).items()})
            else:
                ed = R._editorial(reel['clips'], {c['id'] for c in reel['clips']}, want_banner=True, language=lang)
            print(f'  (IA : {time.time() - t0:.1f} s)')
    tot = {'regles': [0, 0, 0], 'ia': [0, 0, 0]}
    for c in reel['clips']:
        words = c['words']
        print(f'-- {c["id"]} ({len(words)} mots)')
        for label, hl in (('regles', set(hls.get(c['id'], ()))),
                          ('ia', set((ed or {}).get('highlights', {}).get(c['id'], ())) if ed else None)):
            if hl is None:
                continue
            text, ng, cov, adj, stop = show(words, hl, mw)
            tot[label][0] += ng
            tot[label][1] += cov
            tot[label][2] += len(hl)
            print(f'  {label:6} {cov}/{ng} groupes, {len(hl)} mots, blocs={adj}, petits mots seuls={stop}')
            print('         ' + text)
            res[label][c['id']] = [words[i]['w'] for i in sorted(hl)]
    for label, (ng, cov, n) in tot.items():
        if n:
            print(f'  TOTAL {label} : {cov}/{ng} groupes avec un mot en couleur, {n} mots')
    if ed:
        print('  bandeaux :', ed.get('banners'))
    result[f] = res
if out_file:
    Path(out_file).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
