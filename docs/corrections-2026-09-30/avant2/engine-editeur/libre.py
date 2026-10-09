"""Montage sans script : a partir de la seule transcription.
Decoupe la parole en phrases, retire le bavardage et les prises abandonnees, et quand une phrase est
redite, garde la derniere version complete (les versions precedentes deviennent des prises alternatives)."""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from . import media, script as scriptmod
from .derush import ABORTED, _span_times, _words_text, load_takes, project_format, project_name, slug

PAUSE = 0.7          # pause qui separe deux phrases
PAUSE_SENTENCE = 0.25  # pause suffisante apres un point
# Mots de plateau : une phrase faite uniquement de ces mots est du bavardage
CHATTER_WORDS = set('ok okay oui ouais non alors bon go vas y attends ah oh euh hum parfait genial super daccord merci allez '
                    'cest pret moteur action coupe cut '
                    # plateau en anglais
                    'set and yeah yes yep nope no right sure fine thanks lets again reset rolling speed camera mark clap please'.split())
BACKSTAGE = re.compile(r"(pas (encore )?parti|c'?est (tu )?parti|on tourne|[çc]a tourne|tu m'?as-?tu dit|j'?ai pas entendu|"
                       r"[çc]a a pas march|c'?est bon l[àa]|on la refait|"
                       r"\bcamera set\b|we'?re rolling|mark it|from the top|one more time|can we reset)", re.I)


def utterances(words):
    """Phrases prononcees : [(i0, i1)] indices de mots inclus."""
    out, start = [], 0
    for k in range(1, len(words)):
        gap = words[k]['start'] - words[k - 1]['end']
        if gap > PAUSE or (re.search(r'[.!?]$', words[k - 1]['w']) and gap > PAUSE_SENTENCE):
            out.append((start, k - 1))
            start = k
    if words:
        out.append((start, len(words) - 1))
    return out


def _tokens(text):
    return scriptmod.tokens(text)


def _same_sentence(a, b):
    """Meme phrase redite, ou debut abandonne d'une phrase reprise ensuite."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    if SequenceMatcher(None, ta, tb).ratio() >= 0.6:
        return True
    head = tb[:len(ta)]
    return len(ta) >= 3 and SequenceMatcher(None, ta, head).ratio() >= 0.75  # faux depart


HOOK = re.compile(r'hook|accroche|intro', re.I)
ALT = re.compile(r'alt|variante|\bv\d', re.I)
CTA = re.compile(r"\b(bouton|cliqu\w*|appuy\w*|lien|r[ée]serv\w*|abonn\w*|contact\w*|inscri\w*|appel\w* (nous|maintenant)|"
                 r"click|link|book|subscribe|sign up|call us|dm)\b", re.I)


def _natural(name):
    """Ordre naturel des fichiers : 2, 3... 10 (et pas 10 avant 2)."""
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r'(\d+)', name)]


def _label_chatter(texts):
    """Une seule question a l'IA locale : chaque phrase est-elle du CONTENU, du PLATEAU (consignes, « action », equipe)
    ou un FAUX DEPART ? Renvoie les indices a retirer (vide si l'IA n'est pas disponible)."""
    from . import llm
    if not texts or not llm.available():
        return set()
    drop = set()
    try:
        with llm.session():
            for base in range(0, len(texts), 60):
                chunk = texts[base:base + 60]
                lines = '\n'.join(f'[{k}] {t[:200]}' for k, t in enumerate(chunk))
                data = llm.ask_json(
                    llm.EDITOR,
                    "Voici les phrases entendues pendant un tournage, dans l'ordre (une par ligne).\n" + lines + "\n\n"
                    "Pour chacune : « contenu » (ce que le public doit entendre dans la video finale), « plateau » (consignes, reglages, "
                    "« action », « coupez », discussion de l'equipe, commentaire hors video) ou « faux_depart » (phrase abandonnee puis "
                    'reprise). Reponds {"etiquettes": ["contenu", ...]} dans le meme ordre, une etiquette par phrase.',
                    temperature=0.0, max_tokens=40 + 12 * len(chunk))
                tags = data.get('etiquettes') or []
                if len(tags) != len(chunk):
                    continue  # reponse incomplete : on ne retire rien de ce paquet
                drop |= {base + k for k, tg in enumerate(tags) if str(tg).strip().lower() in ('plateau', 'faux_depart', 'faux depart')}
    except Exception as e:
        print(f'IA locale indisponible ({e}) : bavardage retire par regles seulement.')
    return drop


def build_free(folder, out_root, cache_root, language=None, fmt=None):
    """Montage sans script. Ordre : accroche (fichiers « hook ») d'abord, puis les autres fichiers dans l'ordre naturel,
    appel a l'action a la fin ; une phrase redite n'apparait qu'une fois (derniere version) ; bavardage de plateau
    retire (regles + IA locale). Les autres accroches deviennent des variantes (« Hook alternatif »)."""
    folder, out_root, cache = Path(folder).resolve(), Path(out_root).resolve(), Path(cache_root).resolve()
    takes = load_takes(folder, cache, vocabulary='', language=language)
    groups = {}
    for t in takes:
        groups.setdefault(t['group'], []).append(t)
    projects = []
    for group, gtakes in groups.items():
        # 1. toutes les phrases : accroches d'abord, puis ordre naturel des fichiers
        ordered = sorted(gtakes, key=lambda x: (not HOOK.search(Path(x['rel']).stem), _natural(x['rel'])))
        items = []
        for t in ordered:
            utts = utterances(t['words'])
            for u, (i0, i1) in enumerate(utts):
                text = _words_text(t['words'][i0:i1 + 1])
                toks = [x.replace("'", '') for x in _tokens(text)]
                if ABORTED.search(text) or BACKSTAGE.search(text) or all(x in CHATTER_WORDS for x in toks) or len(toks) < 2:
                    continue
                # bout de phrase isole (moins de 3 mots, sans ponctuation finale, rien juste apres) : bavardage
                nxt = utts[u + 1] if u + 1 < len(utts) else None
                if len(toks) < 3 and not re.search(r'[.!?…]$', text) and not (nxt and t['words'][nxt[0]]['start'] - t['words'][i1]['end'] < 0.8):
                    continue
                items.append({'take': t, 'i0': i0, 'i1': i1, 'text': text, 'replaced_by': None,
                              'hook': bool(HOOK.search(Path(t['rel']).stem))})
        drop = _label_chatter([it['text'] for it in items])
        items = [it for k, it in enumerate(items) if k not in drop]
        # 2. une phrase redite (n'importe ou dans le dossier) est remplacee par sa derniere version ;
        #    les accroches sont traitees a part (une prise d'accroche entiere, voir 3)
        for a in range(len(items)):
            if items[a]['hook']:
                continue
            for b in range(a + 1, len(items)):
                if not items[b]['hook'] and _same_sentence(items[a]['text'], items[b]['text']):
                    items[a]['replaced_by'] = b
                    break
        kept = [k for k, it in enumerate(items) if it['replaced_by'] is None and not it['hook']]

        def versions(k):  # toutes les versions d'une phrase conservee (la plus recente d'abord)
            chain = [k]
            for a in range(k - 1, -1, -1):
                if items[a]['replaced_by'] in chain:
                    chain.append(a)
            return chain

        def clip_of(k, cid, bid):
            opts = []
            for v in versions(k):
                it = items[v]
                start, end = _span_times(it['take'], it['i0'], it['i1'])
                opts.append({'source': it['take']['id'], 'in': start, 'out': end, 'score': 1.0 if v == k else 0.8,
                             'notes': [] if v == k else ['version precedente de la phrase'], 'parts': {},
                             'text': it['text'], 'words': it['take']['words'][it['i0']:it['i1'] + 1], 'flags': []})
            best = opts[0]
            return {'id': cid, 'block': bid, 'sentences': [bid], 'tighten': True,
                    **{x: best[x] for x in ('source', 'in', 'out', 'text', 'words', 'flags')}, 'choice': 0, 'takes': opts}

        # 3. accroches : chaque fichier « hook » est une prise ENTIERE de l'accroche. Les prises qui disent la meme chose
        #    sont regroupees ; dans chaque groupe on garde la derniere prise complete. Le groupe principal (fichiers qui ne
        #    sont pas « alternatif ») ouvre la video, les autres deviennent des variantes (« Hook alternatif »).
        by_take = {}
        for k, it in enumerate(items):
            if it['hook']:
                by_take.setdefault(it['take']['id'], []).append(k)
        takes_h = sorted(by_take.values(), key=lambda ks: _natural(items[ks[0]]['take']['rel']))
        clusters = []
        for ks in takes_h:
            text = ' '.join(items[k]['text'] for k in ks)
            for cl in clusters:
                if SequenceMatcher(None, _tokens(text), _tokens(cl[0]['text'])).ratio() >= 0.5:
                    cl.append({'ks': ks, 'text': text})
                    break
            else:
                clusters.append([{'ks': ks, 'text': text}])

        def pick(cl):  # derniere prise complete (au moins 85 % du texte le plus long du groupe)
            longest = max(len(m['text']) for m in cl)
            return [m for m in cl if len(m['text']) >= 0.85 * longest][-1]['ks']

        def is_alt(cl):
            return all(ALT.search(Path(items[m['ks'][0]]['take']['rel']).stem) for m in cl)
        clusters.sort(key=lambda cl: (is_alt(cl), -len(cl)))
        hooks = [pick(cl) for cl in clusters]
        main_hook = hooks[0] if hooks else []
        rest = kept
        ctas = [k for k in rest if CTA.search(items[k]['text'])]
        body = [k for k in rest if k not in ctas]
        timeline, blocks = [], []
        if main_hook:
            blocks.append({'id': 'h', 'label': 'Accroche', 'text': ' '.join(items[k]['text'] for k in main_hook)})
            for k in main_hook:
                timeline.append(clip_of(k, f'c{len(timeline) + 1}', 'h'))
        for k in body + ctas:
            bid = f'u{len(blocks) + 1}'
            blocks.append({'id': bid, 'label': 'Appel a l\'action' if k in ctas else f'Phrase {len(blocks) + 1}', 'text': items[k]['text']})
            timeline.append(clip_of(k, f'c{len(timeline) + 1}', bid))
        variants = []
        for n, ks in enumerate(hooks[1:], 1):
            t = items[ks[0]]['take']
            w0, w1 = items[ks[0]]['i0'], items[ks[-1]]['i1']
            start, end = _span_times(t, w0, w1)
            text = ' '.join(items[k]['text'] for k in ks)
            clip = {'id': f'v{n}c1', 'source': t['id'], 'block': 'h', 'sentences': [], 'in': start, 'out': end, 'tighten': True,
                    'text': text, 'words': t['words'][w0:w1 + 1], 'flags': [], 'choice': 0,
                    'takes': [{'source': t['id'], 'in': start, 'out': end, 'score': 1.0, 'notes': [], 'parts': {}, 'text': text,
                               'words': t['words'][w0:w1 + 1], 'flags': []}]}
            variants.append({'id': f'v{n}', 'label': f'Hook alternatif {n}', 'replaces_block': 'h', 'clip': clip, 'score': 1.0,
                             'notes': [], 'alternatives': []})
        if not timeline:
            continue
        title = group if group != '.' else (folder.stem if folder.is_file() else folder.name)
        name = project_name(out_root, slug(title), folder, alt=folder.parent.name if folder.is_file() else folder.name)
        used = {t['id'] for t in gtakes}
        project = {
            'version': 1, 'name': name, 'label': title, 'mode': 'sans-script',
            'script': {'file': folder.name, 'path': str(folder), 'id': 's1', 'title': 'Sans script', 'blocks': blocks},
            'format': project_format(fmt), 'langue': language or 'fr',
            'audio': {'loudness_lufs': -14, 'denoise': False,
                      'declip': any(sum(t['analysis']['audio']['clip_events']) for t in gtakes)},
            'sources': {t['id']: {'path': str(t['path']), 'name': t['rel'], 'rotate': t['analysis']['rotate'],
                                  'proxy': str(media.optimized(t['path'], t['analysis']['rotate'], cache / 'optimises')),
                                  'transcript': str(cache / 'transcripts' / f"{media.cache_name(t['path'])}.transcript.json"),
                                  'duration': t['analysis']['probe']['duration'], 'fps': t['analysis']['probe']['fps']}
                        for t in takes if t['id'] in used},
            'timeline': timeline, 'variants': variants,
        }
        pdir = out_root / name
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / 'project.json').write_text(json.dumps(project, ensure_ascii=False, indent=1), encoding='utf-8')
        removed = [it for it in items if it['replaced_by'] is not None]
        report = [f'# Montage sans script — {project["label"]}', '',
                  f'{len(timeline)} phrase(s) gardee(s), {len(removed)} version(s) redite(s) ecartee(s).', '', '## Phrases', '']
        report += [f"{n}. {c['text']}" for n, c in enumerate(timeline, 1)]
        report += ['', '## Versions ecartees (disponibles comme prises alternatives)', '']
        report += [f"- {it['take']['rel']} : « {it['text'][:100]} »" for it in removed]
        (pdir / 'rapport.md').write_text('\n'.join(report) + '\n', encoding='utf-8')
        projects.append(pdir)
    return projects
