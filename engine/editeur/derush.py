"""Derushage automatique : choisit les meilleures prises pour chaque phrase d'un script et
produit un projet modifiable (projects/<nom>/project.json) + un rapport lisible."""
import json
import re
import statistics
from difflib import SequenceMatcher
from pathlib import Path

from . import align, analyze, media, script as scriptmod, transcribe

PAUSE_CUT = 0.45      # pause interne au-dela de laquelle on resserre (jump cut)
PAUSE_TAIL = 0.8      # pause qui termine une phrase
PAD_IN, PAD_OUT = 0.12, 0.20
# Phrases qui signalent une prise abandonnee sur le plateau
ABORTED = re.compile(r"d[ée]sol[ée]|on (va )?(recommence|reprend|revien|refai)|je (recommence|reprends)|"
                     r"attends?\b|excuse[zr]?|c'?est parti|on y va|coupez|[çc]a a pas march|"
                     # plateau en anglais (et « cut » dit au Quebec)
                     r"\bsorry\b|\breset\b|\bcut\b|one more time|from the top|hold on|(let'?s|we'?ll) (go|do (it|that|this)|try) again",
                     re.I)
WEIGHTS = {'fidelite': 0.40, 'fluidite': 0.20, 'jeu': 0.15, 'image': 0.12, 'son': 0.08, 'recence': 0.05}


def slug(text):
    t = scriptmod.normalize(text.replace(' ', '-').replace('_', '-'))
    return re.sub(r'-+', '-', ''.join(c if c.isalnum() else '-' for c in t)).strip('-') or 'projet'


GENERIC_TITLE = re.compile(r'^\s*\**\s*(script|vid[eé]o)\s*(\d+)\s*:?\s*$', re.I)
GENERIC_FOLDER = re.compile(r'^(rushs?|m[eé]dias?|entr[eé]e|vid[eé]os?|footage|tournage|lot .*|\.)$', re.I)


def nice_label(title, folder=None):
    """Nom affiche d'une video (titre du reel, nom du fichier livre). « Script 2 » (titre par defaut du lecteur de
    script quand le Word n'a pas d'intertitre, ou intertitre « SCRIPT 2 ») devient le nom du dossier depose s'il est
    donne et parlant (« Vidéo 1 »), sinon « Vidéo 2 ». Un vrai titre (« Offre de Noel ») est garde tel quel."""
    title = str(title or '').strip()
    m = GENERIC_TITLE.match(title)
    if not m:
        return title or 'Vidéo'
    if folder is not None:
        folder = Path(folder)
        name = (folder.stem if folder.suffix and not folder.is_dir() else folder.name).strip()
        if name and not GENERIC_FOLDER.match(name):
            return name
    return f'Vidéo {int(m.group(2))}'


def _origin(project_file):
    try:
        return str(Path(json.loads(project_file.read_text(encoding='utf-8'))['script']['path']).resolve()).lower()
    except Exception:
        return None


def project_name(out_root, name, origin, alt=''):
    """Nom du dossier projects/<nom> : jamais celui d'un AUTRE projet (autre script ou autre dossier de rushs),
    qui serait ecrase. origin = script (ou dossier des rushs sans script) ; alt = prefixe de repli (nom du script)."""
    origin = str(Path(origin).resolve()).lower()
    base = [name] + ([slug(f'{alt}-{name}')] if alt else [])
    for cand in base + [f'{base[-1]}-{n}' for n in range(2, 100)]:
        f = Path(out_root) / cand / 'project.json'
        if not f.exists() or _origin(f) == origin:
            return cand
    raise RuntimeError('Trop de projets du meme nom dans projects/.')


def _words_text(words):
    return ' '.join(w['w'] for w in words).replace(" '", "'").replace(" -", "-")


def _similar(a, b):
    return SequenceMatcher(None, scriptmod.tokens(a), scriptmod.tokens(b)).ratio()


def load_takes(folder, cache, vocabulary, language=None):
    """Prises d'un dossier (recursif) ou d'un seul fichier video (une video deposee seule)."""
    folder = Path(folder)
    base = folder.parent if folder.is_file() else folder
    takes = []
    for i, path in enumerate([folder] if folder.is_file() else media.list_videos(folder)):
        tr = transcribe.transcribe(path, cache / 'transcripts', language=language, vocabulary=vocabulary)
        an = analyze.analyze(path, cache / 'analysis')
        takes.append({'id': f't{i + 1:02d}', 'path': path, 'rel': str(path.relative_to(base)),
                      'group': str(path.parent.relative_to(base)), 'words': tr['words'],
                      'ttoks': align.take_tokens(tr['words']), 'analysis': an, 'mtime': path.stat().st_mtime})
    return takes


def _span_times(take, w0, w1):
    words, dur = take['words'], take['analysis']['probe']['duration']
    start = words[w0]['start'] - PAD_IN
    if w0 > 0:
        start = max(start, words[w0 - 1]['end'] + 0.04)
    end = words[w1]['end'] + PAD_OUT
    if w1 + 1 < len(words):
        end = min(end, words[w1 + 1]['start'] - 0.04)
    # jamais de coupe a l'interieur d'un mot garde (quand deux mots se touchent)
    start = min(start, words[w0]['start'])
    end = max(end, words[w1]['end'])
    return round(max(0.0, start), 3), round(min(dur, end), 3)


def correct_words(words, ref_text):
    """Sous-titres : les mots mal entendus par Whisper sont remplaces par ceux du script (« Ensemble en plus » ->
    « en savoir plus »), en gardant les temps de Whisper. Seulement sur de courts passages qui se ressemblent
    (une vraie reformulation du comedien reste telle quelle)."""
    ref = [w for w in re.split(r'\s+', ref_text.strip()) if w]
    if not words or not ref:
        return words
    norm = lambda w: scriptmod.normalize(w).strip("'")  # noqa: E731
    a, b = [norm(w['w']) for w in words], [norm(w) for w in ref]
    out = [dict(w) for w in words]
    # zones differentes entre deux passages identiques d'au moins 2 mots (un mot commun isole, comme « en » dans
    # « ensemble en » / « en savoir », fait partie de la zone)
    ops = SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
    regions, cur = [], None
    for k, (op, i1, i2, j1, j2) in enumerate(ops):
        solid = op == 'equal' and (i2 - i1 >= 2 or k in (0, len(ops) - 1))
        if solid:
            if cur:
                regions.append(cur)
                cur = None
            continue
        cur = [cur[0], i2, cur[2], j2] if cur else [i1, i2, j1, j2]
    if cur:
        regions.append(cur)
    for i1, i2, j1, j2 in regions:
        if not (0 < i2 - i1 <= 5 and 0 < j2 - j1 <= 5) or a[i1:i2] == b[j1:j2]:
            continue
        # mal entendu = ecrit presque pareil, OU Whisper doutait (mot < 0,7) sur un passage court de meme longueur ;
        # sinon c'est une vraie reformulation du comedien : les sous-titres suivent ce qu'il dit
        doubt = min(w.get('p', 1.0) for w in words[i1:i2]) < 0.7 and abs((i2 - i1) - (j2 - j1)) <= 1 and max(i2 - i1, j2 - j1) <= 3
        if SequenceMatcher(None, ''.join(a[i1:i2]), ''.join(b[j1:j2])).ratio() < 0.5 and not doubt:
            continue
        t0, t1 = words[i1]['start'], words[i2 - 1]['end']
        lens = [max(1, len(w)) for w in ref[j1:j2]]
        new, t = [], t0
        for w, n in zip(ref[j1:j2], lens):
            d = (t1 - t0) * n / sum(lens)
            new.append({**words[i1], 'w': w, 'start': round(t, 3), 'end': round(t + d, 3)})
            t += d
        out[i1:i2] = [None] * (i2 - i1)
        out[i1] = new
    flat = []
    for x in out:
        if x is None:
            continue
        flat.extend(x if isinstance(x, list) else [x])
    return flat


def _quality(take, hit, n_ref, refs, order):
    words = take['words'][hit['w0']:hit['w1'] + 1]
    gaps = [b['start'] - a['end'] for a, b in zip(words, words[1:])]
    long_pauses = sum(g > PAUSE_CUT for g in gaps)
    low = sum(w['p'] < 0.5 for w in words) / max(1, len(words))
    fluency = max(0.0, 1 - (0.2 * long_pauses + low + 0.8 * hit['inserted'] / n_ref))
    start, end = words[0]['start'], words[-1]['end']
    m = analyze.window_metrics(take['analysis'], start, end)
    image = 0.6 * m['face_ratio'] * max(0.0, 1 - 2 * m['face_center']) + 0.4 * min(1.0, m['sharpness'] / refs['sharp'])
    son = (1.0 if -40 < m['loudness_db'] < -8 else 0.5) * max(0.0, 1 - 0.1 * m['clips_per_s'])
    # Jeu : regard camera, expressivite du visage et energie de la voix (compares aux autres prises)
    jeu = (0.5 * m['gaze_on'] + 0.3 * min(1.0, m['expressivity'] / refs['expr'])
           + 0.2 * min(1.0, m['voice_energy'] / refs['energy']))
    parts = {'fidelite': hit['coverage'], 'fluidite': fluency, 'jeu': jeu, 'image': image, 'son': son, 'recence': order}
    notes = []
    if hit['coverage'] < 0.95:
        notes.append(f"{round((1 - hit['coverage']) * 100)} % du texte manquant ou different")
    if long_pauses:
        notes.append(f'{long_pauses} pause(s) longue(s)')
    if low > 0.1:
        notes.append('articulation peu claire par endroits')
    if m['face_ratio'] < 0.8:
        notes.append('visage absent par moments')
    if m['gaze_on'] < 0.7 and m['face_ratio'] > 0.5:
        notes.append(f"regard hors camera {round((1 - m['gaze_on']) * 100)} % du temps")
    if m['expressivity'] < refs['expr'] * 0.6:
        notes.append('jeu peu expressif')
    if m['clips_per_s'] > 2:
        notes.append(f"son sature ({m['clips_per_s']:.1f} pics/s)")
    return round(sum(WEIGHTS[k] * v for k, v in parts.items()), 4), {k: round(v, 3) for k, v in parts.items()}, notes


def _tail(take, w1):
    """Mots prononces juste apres la phrase, sans vraie pause (ajout ou reformulation)."""
    words, out = take['words'], []
    for k in range(w1 + 1, len(words)):
        prev_end = words[k - 1]['end']
        if words[k]['start'] - prev_end > PAUSE_TAIL:
            break
        out.append(k)
    return out


def _clean_region(take):
    """Pour une prise hors script : plus longue suite de paroles sans coupure (evite « c'est parti ? »)."""
    words = take['words']
    if not words:
        return None
    runs, cur = [], [0]
    for k in range(1, len(words)):
        if words[k]['start'] - words[k - 1]['end'] > 1.2:
            runs.append(cur)
            cur = []
        cur.append(k)
    runs.append(cur)
    runs = [r for r in runs if not ABORTED.search(_words_text([words[k] for k in r]))]
    best = max(runs, key=len, default=[])
    return (best[0], best[-1]) if len(best) >= 8 else None


FORMATS = {'9:16': (1080, 1920), '16:9': (1920, 1080), '4:5': (1080, 1350), '1:1': (1080, 1080)}


def project_format(fmt):
    """Format de depart des reels du projet (modifiable ensuite dans l'interface)."""
    w, h = FORMATS.get(fmt or '9:16', FORMATS['9:16'])
    return {'width': w, 'height': h, 'fps': 30}


def build(folder, script_path, out_root, cache_root, language=None, fmt=None):
    """language : langue des rushs ('fr' par defaut, 'en', 'auto'...) ; fmt : '9:16' (defaut), '16:9', '4:5', '1:1'."""
    folder, out_root, cache = Path(folder).resolve(), Path(out_root).resolve(), Path(cache_root).resolve()
    scripts = scriptmod.parse(script_path)
    vocabulary = ' '.join(b['text'] for s in scripts for b in s['blocks'])
    takes = load_takes(folder, cache, vocabulary, language)
    frames = [f for t in takes for f in t['analysis']['frames']]
    jeux = [f['jeu'] for f in frames if f.get('jeu')]
    energies = [analyze.window_metrics(t['analysis'], 0, t['analysis']['probe']['duration'])['voice_energy'] for t in takes]
    sharp_ref = {'sharp': statistics.median(f['sharp'] for f in frames) or 1.0,
                 'expr': (statistics.median(j['expr'] for j in jeux) if jeux else 0.1) or 0.1,
                 'energy': statistics.median(energies) or 1.0}

    # 1. Chaque prise est rattachee au script qu'elle recite le plus.
    hits = {}
    for t in takes:
        n_tokens = max(1, len(t['ttoks']))
        best = (0.0, '')
        for s in scripts:
            covered = 0
            for b in s['blocks']:
                for p in b['sentences']:
                    found = align.find(p['tokens'], t['ttoks'], words=t['words'])
                    hits[(t['id'], p['id'])] = found
                    covered += sum(h['matched'] for h in found)
            best = max(best, (covered / n_tokens, s['id']))
        # un seul script : une prise qui contient une vraie replique en fait partie, meme si elle est surtout
        # faite de bavardage de plateau (« Set. Action. … Holy shit. »)
        strong = sum(h['exact'] for (tid, _), found in hits.items() if tid == t['id'] for h in found)
        t['script'] = best[1] if best[0] >= 0.35 or (len(scripts) == 1 and strong >= 3) else None

    projects = []
    # une seule video du script dans ces rushs : elle porte le nom du dossier depose (« Vidéo 1 ») si le script
    # n'a pas de vrai titre ; sinon « Script 2 » -> « Vidéo 2 » (le mot que l'utilisateur emploie)
    single = sum(1 for s in scripts if any(t['script'] == s['id'] for t in takes)) == 1
    for s in scripts:
        mine = [t for t in takes if t['script'] == s['id']]
        if not mine:
            continue
        groups = statistics.mode(t['group'] for t in mine)
        base = slug(groups if groups != '.' else s['title'])
        name = project_name(out_root, base, script_path, alt=Path(script_path).stem)
        shown = groups if groups != '.' else nice_label(s['title'], folder if single else None)
        label = shown + ('' if name == base else f' ({Path(script_path).stem})')
        mtime_rank = {t['id']: i / max(1, len(mine) - 1) for i, t in enumerate(sorted(mine, key=lambda t: t['mtime']))}
        sentences = [(b, p) for b in s['blocks'] for p in b['sentences']]

        # 2. Candidats notes pour chaque phrase.
        cands = []
        for b, p in sentences:
            row = []
            for t in mine:
                found = sorted(hits[(t['id'], p['id'])], key=lambda h: h['h0'])
                for k, h in enumerate(found):
                    order = 0.5 * mtime_rank[t['id']] + 0.5 * (k / max(1, len(found) - 1) if len(found) > 1 else 1.0)
                    score, parts, notes = _quality(t, h, len(p['tokens']), sharp_ref, order)
                    start, end = t['words'][h['w0']]['start'], t['words'][h['w1']]['end']
                    row.append({'take': t, 'hit': h, 'score': score, 'parts': parts, 'notes': notes,
                                'start': start, 'end': end})
            cands.append(sorted(row, key=lambda c: -c['score']))

        # 3. Programmation dynamique : meilleures prises, en evitant les coupes inutiles.
        def joined(a, b):
            return a['take'] is b['take'] and 0 <= b['start'] - a['end'] < 2.0

        best = []
        for k, row in enumerate(cands):
            prev = next((best[j] for j in range(k - 1, -1, -1) if best[j]), None)
            layer = {}
            for ci, c in enumerate(row):
                if prev is None:
                    layer[ci] = (c['score'], None)
                    continue
                layer[ci] = max(((v[0] + c['score'] + (0.12 if joined(cands[pk][pi], c) else 0.0), (pk, pi))
                                 for pk, pl in [prev] for pi, v in pl.items()), key=lambda x: x[0])
            best.append((k, layer) if layer else None)
        choice = [None] * len(cands)
        last = next((b for b in reversed(best) if b), None)
        if last:
            k, layer = last
            ci = max(layer, key=lambda i: layer[i][0])
            while True:
                choice[k] = ci
                back = best[k][1][ci][1]
                if back is None:
                    break
                k, ci = back

        # 4. Regroupement en plans continus + gestion des ajouts improvises.
        clips, report_rows = [], []
        for k, (b, p) in enumerate(sentences):
            if choice[k] is None:
                report_rows.append({'block': b, 'sentence': p, 'chosen': None, 'alternatives': []})
                continue
            c = cands[k][choice[k]]
            report_rows.append({'block': b, 'sentence': p, 'chosen': c,
                                'alternatives': [a for i, a in enumerate(cands[k]) if i != choice[k]][:4]})
            if clips and clips[-1]['take'] is c['take'] and joined(clips[-1]['last'], c):
                clips[-1].update(w1=max(clips[-1]['w1'], c['hit']['w1']), last=c)
                clips[-1]['sentences'].append(p['id'])
            else:
                # jamais deux plans sur les memes mots d'une prise (doublon a l'image et au son)
                w0 = c['hit']['w0']
                for prev in clips:
                    if prev['take'] is c['take'] and prev['w0'] <= w0 <= prev['w1']:
                        w0 = prev['w1'] + 1
                if w0 > c['hit']['w1']:
                    report_rows[-1]['chosen'] = None
                    report_rows[-1]['doublon'] = True
                    continue
                clips.append({'take': c['take'], 'w0': w0, 'w1': c['hit']['w1'], 'first': c, 'last': c,
                              'block': b['id'], 'sentences': [p['id']], 'flags': []})
        for clip in clips:
            c, take = clip['last'], clip['take']
            tail = _tail(take, clip['w1'])
            if not tail:
                continue
            tail_text = _words_text([take['words'][i] for i in tail])
            k = next(i for i, (_, p) in enumerate(sentences) if p['id'] == clip['sentences'][-1])
            is_last_of_block = k + 1 == len(sentences) or sentences[k + 1][0]['id'] != clip['block']
            if c['hit']['missing_end']:
                clip['w1'] = tail[-1]
                clip['flags'].append(f'Fin reformulee par la personne : « {tail_text} »')
            elif is_last_of_block:
                others = [a for a in cands[k] if a['take'] is not take]
                seen = sum(1 for a in others if (tt := _tail(a['take'], a['hit']['w1'])) and
                           _similar(tail_text, _words_text([a['take']['words'][i] for i in tt])) >= 0.6)
                if seen >= 1:
                    clip['w1'] = tail[-1]
                    clip['flags'].append(f'Ajout hors script garde (dit dans {seen + 1} prises) : « {tail_text} »')
                else:
                    clip['flags'].append(f'Ajout hors script retire : « {tail_text} »')

        sent_text = {p['id']: p['text'] for _, p in sentences}

        def as_take(take, w0, w1, score, flags, rated=(), ref=''):
            start, end = _span_times(take, w0, w1)
            notes = list(dict.fromkeys(n for r in rated for n in r.get('notes', [])))
            parts = {k: round(sum(r['parts'][k] for r in rated) / len(rated), 3) for k in WEIGHTS} if rated else {}
            words = correct_words(take['words'][w0:w1 + 1], ref) if ref else take['words'][w0:w1 + 1]
            return {'source': take['id'], 'in': start, 'out': end, 'score': round(score, 3), 'notes': notes, 'parts': parts,
                    'text': _words_text(words), 'words': words, 'flags': flags}

        timeline = []
        for i, clip in enumerate(clips, 1):
            take = clip['take']
            k0 = next(j for j, (_, p) in enumerate(sentences) if p['id'] == clip['sentences'][0])
            k1 = next(j for j, (_, p) in enumerate(sentences) if p['id'] == clip['sentences'][-1])
            extended = clip['w1'] > clip['last']['hit']['w1']
            score = (clip['first']['score'] + clip['last']['score']) / 2
            ref = ' '.join(sent_text[x] for x in clip['sentences'])
            chosen = as_take(take, clip['w0'], clip['w1'], score, clip['flags'], (clip['first'], clip['last']), ref)
            # Autres prises couvrant les memes phrases : pour changer de prise en un clic dans l'interface.
            options = [chosen]
            for other in mine:
                if other is take:
                    continue
                firsts = [c for c in cands[k0] if c['take'] is other]
                for f in firsts:
                    lasts = [c for c in cands[k1] if c['take'] is other and c['hit']['w1'] >= f['hit']['w1']]
                    if not lasts:
                        continue
                    last = min(lasts, key=lambda c: c['hit']['w1'])
                    w1 = last['hit']['w1']
                    if extended and (tail := _tail(other, w1)):
                        w1 = tail[-1]
                    options.append(as_take(other, f['hit']['w0'], w1, (f['score'] + last['score']) / 2, [], (f, last), ref))
            options = [options[0]] + sorted(options[1:], key=lambda o: -o['score'])
            timeline.append({'id': f'c{i}', 'block': clip['block'], 'sentences': clip['sentences'], 'tighten': True,
                             **{k: chosen[k] for k in ('source', 'in', 'out', 'text', 'words', 'flags')},
                             'choice': 0, 'takes': options})

        # 5. Prises hors script du meme dossier : variantes (ex. hooks alternatifs).
        variants, unused = [], []
        first_block = s['blocks'][0]
        offs = [t for t in takes if t['script'] is None and t['group'] == groups]
        clusters = []
        for t in offs:
            region = _clean_region(t)
            if not region:
                unused.append({'take': t['rel'], 'raison': 'pas de passage exploitable (bavardage ou prise interrompue)',
                               'texte': _words_text(t['words'])})
                continue
            text = _words_text(t['words'][region[0]:region[1] + 1])
            for cl in clusters:
                if _similar(text, cl[0]['text']) >= 0.6:
                    cl.append({'take': t, 'region': region, 'text': text})
                    break
            else:
                clusters.append([{'take': t, 'region': region, 'text': text}])
        for n, cl in enumerate(clusters, 1):
            longest = max(len(m['text']) for m in cl)
            complete = [m for m in cl if len(m['text']) >= 0.85 * longest]
            for m in complete:
                t, (w0, w1) = m['take'], m['region']
                words = t['words'][w0:w1 + 1]
                fake = {'w0': w0, 'w1': w1, 'coverage': 1.0, 'inserted': 0}
                m['score'], m['parts'], m['notes'] = _quality(t, fake, max(1, len(words)), sharp_ref, mtime_rank.get(t['id'], 0.5))
            pick = max(complete, key=lambda m: m['score'])
            for m in cl:
                if m is not pick:
                    unused.append({'take': m['take']['rel'], 'raison': f'variante {n} : autre prise retenue' if m in complete
                                   else f'variante {n} : prise incomplete', 'texte': m['text']})
            t, (w0, w1) = pick['take'], pick['region']
            start, end = _span_times(t, w0, w1)
            is_hook = 'hook' in (first_block['label'] + t['rel']).lower()
            variants.append({'id': f'v{n}', 'label': f"{'Hook' if is_hook else 'Variante'} alternatif {n}",
                             'replaces_block': first_block['id'] if is_hook else None,
                             'clip': {'id': f'v{n}c1', 'source': t['id'], 'block': first_block['id'], 'sentences': [],
                                      'in': start, 'out': end, 'tighten': True, 'text': pick['text'],
                                      'words': t['words'][w0:w1 + 1], 'flags': ['Texte absent du script Word'],
                                      'choice': 0, 'takes': [as_take(m['take'], *m['region'], m['score'],
                                                                     ['Texte absent du script Word'], (m,))
                                                             for m in [pick] + [x for x in complete if x is not pick]]},
                             'score': pick['score'], 'notes': pick['notes'],
                             'alternatives': [m['take']['rel'] for m in complete if m is not pick]})

        used = {t['id'] for t in takes if t['script'] == s['id'] or t['group'] == groups}
        project = {
            'version': 1, 'name': name, 'label': label,
            'script': {'file': str(Path(script_path).name), 'path': str(Path(script_path).resolve()), 'id': s['id'], 'title': s['title'],
                                                   'blocks': [{k: b[k] for k in ('id', 'label', 'text')} for b in s['blocks']]},
            'format': project_format(fmt), 'langue': language or 'fr',
            'audio': {'loudness_lufs': -14, 'denoise': False,
                      'declip': any(sum(t['analysis']['audio']['clip_events']) for t in takes if t['id'] in used)},
            'sources': {t['id']: {'path': str(t['path']), 'name': t['rel'], 'rotate': t['analysis']['rotate'],
                                  'proxy': str(media.optimized(t['path'], t['analysis']['rotate'], cache / 'optimises')),
                                  'transcript': str(cache / 'transcripts' / f"{media.cache_name(t['path'])}.transcript.json"),
                                  'duration': t['analysis']['probe']['duration'], 'fps': t['analysis']['probe']['fps']}
                        for t in takes if t['id'] in used},
            'timeline': timeline, 'variants': variants,
            'alertes': [{'type': 'manquante', 'texte': r['sentence']['text']} for r in report_rows
                        if not r['chosen'] and not r.get('doublon')],
        }
        pdir = out_root / name
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / 'project.json').write_text(json.dumps(project, ensure_ascii=False, indent=1), encoding='utf-8')
        (pdir / 'rapport.md').write_text(_report(project, report_rows, unused, takes), encoding='utf-8')
        projects.append(pdir)
    return projects


def _fmt(t):
    return f'{int(t // 60)}:{t % 60:04.1f}'


def _report(project, rows, unused, takes):
    by_id = {t['id']: t for t in takes}
    L = [f"# Derushage — {project['name']}", '',
         f"Script : **{project['script']['title']}** ({project['script']['file']}). "
         f"{len(project['timeline'])} plan(s) retenu(s).", '', '## Montage', '']
    for c in project['timeline']:
        L.append(f"{c['id']}. {project['sources'][c['source']]['name']} {_fmt(c['in'])} → {_fmt(c['out'])} — "
                 f"« {c['text'][:80]}{'…' if len(c['text']) > 80 else ''} »")
    L += ['', '## Phrases du script', '']
    for r in rows:
        p = r['sentence']
        L.append(f"### {r['block']['label']} — « {p['text'][:90]}{'…' if len(p['text']) > 90 else ''} »")
        c = r['chosen']
        if not c:
            L += ['', '**Deja dite dans le plan precedent (meme passage de la prise).**' if r.get('doublon')
                  else '**⚠ Aucune prise ne contient cette phrase : a refilmer.**', '']
            continue
        L.append('')
        L.append(f"- **Retenue : {c['take']['rel']}** ({_fmt(c['start'])} → {_fmt(c['end'])}), note {c['score']:.2f}"
                 + (f" — {', '.join(c['notes'])}" if c['notes'] else ''))
        for a in r['alternatives']:
            L.append(f"- Autre : {a['take']['rel']} ({_fmt(a['start'])}), note {a['score']:.2f}"
                     + (f" — {', '.join(a['notes'])}" if a['notes'] else ''))
        L.append('')
    flags = [(c['id'], f) for c in project['timeline'] for f in c['flags']]
    if flags:
        L += ['## A verifier', ''] + [f'- Plan {cid} : {f}' for cid, f in flags] + ['']
    if project['variants']:
        L += ['## Variantes (texte hors script)', '']
        for v in project['variants']:
            src = project['sources'][v['clip']['source']]['name']
            L.append(f"- **{v['label']}** : {src}, note {v['score']:.2f} — « {v['clip']['text']} »")
    if unused:
        L += ['', '## Prises non utilisees', ''] + [f"- {u['take']} : {u['raison']} — « {u['texte'][:100]} »" for u in unused]
    return '\n'.join(L) + '\n'
