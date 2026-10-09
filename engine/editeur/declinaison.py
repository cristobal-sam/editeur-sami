"""Declinaisons automatiques d'un montage : 60 / 30 / 15 s et intentions (« rapide », « emotion »).

Duree : l'IA locale note l'importance de chaque phrase (regles simples sinon) ; on coupe les phrases
les moins importantes (mots marques « cut », donc retablissables dans l'onglet Texte) jusqu'a la
duree visee. La phrase d'accroche et la derniere phrase de l'appel a l'action sont protegees.
Intention : reglages de rythme, zooms, sous-titres, musique et transitions.
Reancrage : graphismes, plans de coupe, bruitages ajoutes, bandeau et zooms de relance sont places dans le
temps du montage ; apres la coupe, chacun suit le mot sous son debut, est raccourci s'il deborde sur une
partie coupee et retire si son mot a ete coupe. Logo et elements de fin restent a la fin, les graphismes de
l'appel a l'action sont gardes, aucun plan de coupe ne cache l'accroche ni la derniere phrase de l'appel.
Le resultat est une NOUVELLE version (reels/<id>-<suffixe>.json), comparable en A/B."""
import copy
import math
import re
import unicodedata

from . import montage

INTENTIONS = {
    'rapide': {'label': 'rapide', 'tighten': True, 'zoom': {'auto': True, 'strength': 1.2, 'push': 0.05},
               'style': {'maxWords': 2, 'pop': True}, 'flash': {'enabled': True, 'kind': 'blanc'},
               'music': 'energique', 'sfx': {'enabled': True, 'transition': 'whoosh-court', 'highlight': 'pop', 'highlightGap': 2.5}},
    'emotion': {'label': 'émotion', 'tighten': False, 'zoom': {'auto': False, 'strength': 1.06, 'push': 0.025},
                'style': {'maxWords': 4, 'pop': False}, 'flash': {'enabled': False, 'kind': 'lumiere'},
                'music': 'emotion', 'grade': 'cinema', 'lcut': 0.25,
                'sfx': {'highlight': None, 'transition': None}},
}

# un element qui finit a moins de 0,25 s de la fin est un element « de fin » (logo, carte d'appel a l'action)
END_TIE = 0.25
# duree minimale d'un element raccourci (sinon il clignote) : il deborde un peu sur la suite
MIN_HOLD = {'chiffre': 1.4, 'coches': 2.4, 'carte': 1.5, 'motgeant': 0.7, 'logo': 1.2, 'broll': 1.0}


def _importance(reel, items):
    """Note 1..10 de chaque phrase : IA locale, sinon regles (chiffres, mots en couleur, longueur)."""
    from . import llm
    rules = []
    for it in items:
        text = it['text']
        s = 5 + 2 * sum(1 for w in it['words'] if w.get('hl')) + (2 if re.search(r'\d', text) else 0)
        s -= 1 if len(it['words']) < 5 else 0
        rules.append(min(10, s))
    if not llm.available():
        return rules
    try:
        numbered = '\n'.join(f'{k}. {it["text"]}' for k, it in enumerate(items))
        with llm.session():
            data = llm.ask_json(llm.EDITOR,
                                f'Voici les {len(items)} phrases d\'une publicite video, numerotees dans l\'ordre :\n{numbered}\n\n'
                                'Note l\'importance de chaque phrase pour convaincre (10 = indispensable : promesse, preuve, '
                                'chiffre, benefice principal ; 1 = accessoire, repetition, transition). '
                                f'Reponds {{"notes": {{"0": note, "1": note, ...}}}} avec une note pour CHACUNE des {len(items)} '
                                f'phrases, numeros 0 a {len(items) - 1}.', temperature=0.0)
        raw = data.get('notes')
        # par numero de phrase (une liste mal comptee decalerait toutes les notes : on ne la garde que complete)
        if isinstance(raw, list):
            raw = {str(k): x for k, x in enumerate(raw)} if len(raw) == len(items) else {}
        notes = {}
        for k, x in (raw or {}).items():
            try:
                notes[int(str(k).strip().rstrip('.'))] = min(10.0, max(1.0, float(x)))
            except (TypeError, ValueError):
                pass
        if notes:
            return [0.7 * notes[k] + 0.3 * r if k in notes else r for k, r in enumerate(rules)]
    except Exception:
        pass
    return rules


def _carries(reel, avant, items):
    """+1 aux phrases qui portent un graphisme ou un plan de coupe place par le monteur (on les coupe en dernier)."""
    carte = _Carte(avant, avant)
    where = {}
    for k, it in enumerate(items):
        for i in range(it['i0'], it['i1'] + 1):
            where[(it['clip']['id'], i)] = k
    bonus = [0.0] * len(items)
    for x in (reel.get('graphics') or []) + (reel.get('broll') or []):
        if x.get('suggested') or not carte.bw:
            continue
        a = carte.anchor(x['at'])
        k = where.get((a['clip'], a['index']))
        if k is not None:
            bonus[k] = 1.0
    return bonus


def create(project_dir, rid, seconds=None, intention=None):
    base = montage.load(project_dir, rid)
    reel = copy.deepcopy(base)
    items = []
    for c in reel['clips']:
        for i0, i1 in montage.sentences(c):
            ws = c['words'][i0:i1 + 1]
            if all(w.get('cut') for w in ws):
                continue
            items.append({'clip': c, 'i0': i0, 'i1': i1, 'words': ws, 'text': ' '.join(w['w'] for w in ws), 'protected': False})
    # proteges : la premiere phrase (l'accroche) et la derniere phrase de l'appel a l'action (le « quoi faire »)
    hook = cta_last = None
    if items:
        items[0]['protected'] = True
        cta = [it for it in items if it['clip']['block'] == reel.get('ctaBlock')] or items[-1:]
        cta[-1]['protected'] = True
        hook, cta_last = items[0], cta[-1]
    # montage d'origine : les graphismes, plans de coupe et bruitages y sont places
    avant = montage.compute(base)
    removed = []
    label_parts = []
    # l'intention d'abord : le resserrage change la duree
    if intention in INTENTIONS:
        _apply_intention(reel, INTENTIONS[intention])
    if seconds:
        notes = [n + b for n, b in zip(_importance(reel, items), _carries(base, avant, items))]
        order = sorted((k for k, it in enumerate(items) if not it['protected']), key=lambda k: (notes[k], -len(items[k]['words'])))

        def with_cuts(cut):
            r = copy.deepcopy(reel)
            clips = {c['id']: c for c in r['clips']}
            for k in cut:
                it = items[k]
                for w in clips[it['clip']['id']]['words'][it['i0']:it['i1'] + 1]:
                    w['cut'] = True
            # un plan dont tous les mots sont coupes disparait du montage
            r['clips'] = [c for c in r['clips'] if not c['words'] or not all(w.get('cut') for w in c['words'])]
            return r

        def fits(cut):
            return montage.compute(with_cuts(cut), light=True)['duration'] <= seconds

        lo, hi = 0, len(order)
        if not fits([]):
            # 1. plus petit nombre de phrases (les moins importantes d'abord) a couper pour tenir la duree
            while lo < hi:
                mid = (lo + hi) // 2
                if fits(order[:mid]):
                    hi = mid
                else:
                    lo = mid + 1
        cut = list(order[:lo])
        # 2. remplissage : on retablit les phrases coupees les plus importantes qui tiennent encore
        for k in sorted(cut, key=lambda k: -notes[k]):
            trial = [x for x in cut if x != k]
            if fits(trial):
                cut = trial
        reel = with_cuts(cut)
        removed = [items[k]['text'] for k in sorted(cut)]
    apres = montage.compute(reel)
    keys = lambda it: [(it['clip']['id'], i) for i in range(it['i0'], it['i1'] + 1) if not it['clip']['words'][i].get('cut')] if it else []
    elements = _reanchor(base, reel, avant, apres, keys(hook), keys(cta_last))
    if seconds:
        label_parts.append(f'{int(seconds)} s')
    if intention in INTENTIONS:
        label_parts.append(INTENTIONS[intention]['label'])
    label = ' '.join(label_parts) or 'copie'
    suffix = re.sub(r'[^a-z0-9]+', '-', unicodedata.normalize('NFD', label.lower()).encode('ascii', 'ignore').decode()).strip('-')
    stem = f"{base['id']}-{suffix}"[:60]
    new_id, serial = stem, 2
    while montage.reel_path(project_dir, new_id).exists():
        tail = f'-{serial}'
        new_id = stem[:60 - len(tail)] + tail
        serial += 1
    reel.update({'id': new_id, 'derivedFrom': base['id'], 'label': label, 'title': f"{base['title']} - {label}"})
    montage.save(project_dir, new_id, reel)
    return {'rid': new_id, 'label': label, 'duree': round(apres['duration'], 1), 'phrases_coupees': removed,
            'elements': elements, 'elements_resume': [e['message'] for part in ('retires', 'raccourcis', 'deplaces') for e in elements[part]]}


def _apply_intention(reel, it):
    for c in reel['clips']:
        c['tighten'] = it['tighten']
        if it.get('lcut'):
            c['audioTail'] = max(c.get('audioTail', 0), it['lcut'])
    reel['zoom'] = {**reel['zoom'], **it['zoom']}
    reel['style'] = {**reel['style'], **it['style']}
    reel['flash'] = dict(it['flash'])
    if it.get('grade'):
        reel['effects'] = {**(reel.get('effects') or {'grain': 0, 'vignette': 0}), 'grade': it['grade']}
    mood = it['music']
    reel['music'] = {**(reel.get('music') or {'volume': 0.18}), 'enabled': True, 'mood': mood, 'file': f'music/{mood}.ogg'}
    reel['sfx'] = {**(reel.get('sfx') or {'enabled': True, 'cta': None, 'start': None, 'volume': 0.6, 'highlightGap': 4}), **it['sfx']}


# ---------- Reancrage des elements places dans le temps du montage ----------
def _len(s):
    """Duree d'un segment dans le montage (vitesse comprise)."""
    return (s['src_out'] - s['src_in']) / (s.get('speed') or 1)


def _seg_at(segs, t):
    """Segment du montage sous l'instant t (le dernier si t tombe pile sur la fin), None hors du montage."""
    for s in segs:
        if s['out_start'] - 1e-6 <= t < s['out_start'] + _len(s) - 1e-6:
            return s
    if segs and segs[-1]['out_start'] <= t <= segs[-1]['out_start'] + _len(segs[-1]) + 1e-3:
        return segs[-1]
    return None


class _Carte:
    """Correspondance entre le montage d'origine et la declinaison (temps du montage), par les segments
    (meme image de la meme prise) et par les mots (chaque mot garde a un nouveau temps)."""

    def __init__(self, avant, apres):
        self.bs, self.ds = avant['video'], apres['video']
        self.btotal, self.dtotal = avant['duration'], apres['duration']
        self.bw = sorted(avant['words'], key=lambda w: w['start'])
        self.dw = {(w['clip'], w['index']): w for w in apres['words']}
        # (fin de l'accroche avant, fin de l'accroche apres) : un element de fin ne remonte pas sur l'accroche
        self.hook = None

    def exact(self, t):
        """Meme instant de la meme prise dans la declinaison, sinon None (partie coupee ou pause resserree)."""
        s = _seg_at(self.bs, t)
        if s is None:
            return None
        src = s['src_in'] + (t - s['out_start']) * (s.get('speed') or 1)
        for d in self.ds:
            if d['clip'] == s['clip'] and d['src_in'] - 1e-3 <= src <= d['src_out'] + 1e-3:
                return d['out_start'] + (min(max(src, d['src_in']), d['src_out']) - d['src_in']) / (d.get('speed') or 1)
        return None

    def new(self, w):
        """Le mot dans la declinaison (None s'il a ete coupe)."""
        return self.dw.get((w['clip'], w['index']))

    def anchor(self, t):
        """Mot sous l'instant t : celui qu'on entend (le dernier commence si deux mots se touchent), sinon le suivant
        s'il arrive dans la demi-seconde, sinon le precedent."""
        inside = [w for w in self.bw if w['start'] - 0.02 <= t < w['end']]
        if inside:
            return inside[-1]
        nxt = next((w for w in self.bw if w['start'] > t), None)
        if nxt and nxt['start'] - t <= 0.5:
            return nxt
        prev = [w for w in self.bw if w['end'] <= t]
        return prev[-1] if prev else nxt

    def bounds(self, dword):
        """Debut et fin du segment de la declinaison qui contient ce mot."""
        s = _seg_at(self.ds, (dword['start'] + dword['end']) / 2)
        return (s['out_start'], s['out_start'] + _len(s)) if s else (dword['start'], dword['end'])

    def place(self, at, duration, keep=False, hold=0.0):
        """Nouvelle place d'un element [at, at + duration] du montage d'origine : (debut, duree, raison).
        debut None = retire (son mot a ete coupe). keep = garde meme si son mot est coupe (pose sur la suite)."""
        end = at + duration
        # element de fin (logo, carte de l'appel a l'action) : meme distance de la fin
        if end >= self.btotal - END_TIE and at > 0:
            start = max(0.0, self.dtotal - (self.btotal - at))
            if self.hook and at >= self.hook[0]:
                start = max(start, self.hook[1])
            return start, max(0.0, min(duration, self.dtotal - start)), 'fin'
        if not self.bw:
            # montage sans parole (immobilier, evenement) : la meme image seulement
            start = self.exact(at)
            if start is None:
                return None, 0, 'coupe'
            e = self.exact(end)
            return start, (e - start) if e is not None and e > start else min(duration, self.dtotal - start), None
        a = self.anchor(at)
        da = self.new(a)
        if da is None:
            if not keep:
                return None, 0, 'coupe'
            # garde : pose sur le premier mot garde qui suit
            k = self.bw.index(a)
            n = next((self.new(x) for x in self.bw[k + 1:] if self.new(x)), None)
            start = max(self.bounds(n)[0], n['start'] - 0.1) if n else max(0.0, self.dtotal - duration)
            return start, max(0.0, min(duration, self.dtotal - start)), 'garde'
        # debut : meme image si elle existe encore, sinon meme ecart avec son mot
        lead = at - a['start']
        start = self.exact(at)
        if start is None or abs((start - da['start']) - lead) > 0.05:
            start = da['start'] + lead
            if lead < 0:
                start = max(self.bounds(da)[0], start)
        start = max(0.0, start)
        if duration <= 0:
            return start, 0, None
        # fin : on s'arrete avant la premiere partie coupee (le reste de l'element tomberait sur une autre phrase)
        prev, stop, why = a, None, None
        for w in self.bw:
            if not a['start'] < w['start'] < end:
                continue
            if self.new(w) is None:
                stop, why = self.bounds(self.new(prev))[1], 'coupe-apres'
                break
            prev = w
        if stop is None:
            e = self.exact(end)
            if e is None or e <= start:
                dp = self.new(prev)
                e = min(dp['end'] + max(0.0, end - prev['end']), self.bounds(dp)[1])
            stop = e
        dur = min(duration, stop - start)
        if dur < duration - 0.05:
            why = why or 'resserre'
        if dur < min(duration, hold):
            dur = min(duration, hold)
        if dur > self.dtotal - start:
            dur, why = self.dtotal - start, 'depasse'
        return start, max(0.0, dur), why

    def until(self, t):
        """Fin d'une plage (bandeau) : meme image si elle existe encore, sinon fin du dernier mot garde avant t."""
        if t >= self.btotal - END_TIE:
            return self.dtotal
        e = self.exact(t)
        if e is not None:
            return e
        prev = [self.new(w) for w in self.bw if w['start'] < t and self.new(w)]
        return self.bounds(prev[-1])[1] if prev else 0.0


def _fit(at, duration, total):
    """Debut et duree arrondis au centieme sans jamais depasser la fin de la video."""
    at = round(max(0.0, at), 2)
    return {'at': at, 'duration': max(0.0, math.floor(min(duration, total - at) * 100 + 1e-6) / 100)}


def _graphic_name(g):
    p = g.get('props') or {}
    kind = g.get('kind')
    if kind == 'chiffre':
        return f"Chiffre « {p.get('prefix', '')}{p.get('value', '')}{p.get('suffix', '')} »"
    if kind == 'coches':
        return f"Liste « {p['title']} »" if p.get('title') else 'Cases cochées'
    if kind == 'carte':
        return f"Carte « {p['title']} »" if p.get('title') else 'Carte'
    if kind == 'motgeant':
        return f"Mot géant « {p.get('text', '')} »"
    if kind == 'logo':
        return 'Logo animé'
    return 'Graphisme'


REASONS = {
    'coupe': 'sa phrase a été coupée',
    'coupe-apres': 'la phrase qui suivait a été coupée',
    'resserre': 'les pauses ont été resserrées',
    'plage': 'des phrases de sa plage ont été coupées',
    'fin': 'reste à la fin',
    'garde': "sa phrase a été coupée : posé sur la phrase suivante",
    'depasse': 'dépassait la fin de la vidéo',
    'accroche': "pour ne pas cacher l'accroche",
    'appel': "pour ne pas cacher l'appel à l'action",
    'chevauche': 'aurait chevauché un autre élément',
    'suit': 'suit son élément',
    'lie': 'son élément a été retiré',
}


def _reanchor(base, reel, avant, apres, hook, cta):
    """Deplace, raccourcit ou retire les elements places dans le temps du montage d'origine (modifie reel).
    hook / cta : mots (plan, indice) de l'accroche et de la derniere phrase de l'appel a l'action.
    -> {'deplaces', 'raccourcis', 'retires'} : [{piste, element, avant, apres, duree_avant, duree, raison, message}]."""
    carte = _Carte(avant, apres)
    report = {'deplaces': [], 'raccourcis': [], 'retires': []}
    fr = lambda t: f'{t:.1f}'.replace('.', ',') + ' s'

    def note(piste, name, at, dur, new_at, new_dur, why=None, show=True):
        if not show:
            return
        e = {'piste': piste, 'element': name, 'avant': round(at, 2), 'duree_avant': round(dur, 2)}
        if new_at is None:
            e.update(apres=None, duree=0, raison=REASONS.get(why or 'coupe'))
            e['message'] = f"{name} : retiré ({e['raison']})"
            report['retires'].append(e)
            return
        e.update(apres=round(new_at, 2), duree=round(new_dur, 2))
        moved = abs(new_at - at) > 0.1
        if dur > 0 and new_dur < dur - 0.05:
            e['raison'] = REASONS.get(why or 'coupe-apres')
            e['message'] = f"{name} : raccourci à {fr(new_dur)}" + (f", déplacé de {fr(at)} à {fr(new_at)}" if moved else '') + f" ({e['raison']})"
            report['raccourcis'].append(e)
        elif moved:
            e['raison'] = REASONS.get(why) or 'suit sa phrase'
            e['message'] = f"{name} : déplacé de {fr(at)} à {fr(new_at)} ({e['raison']})"
            report['deplaces'].append(e)

    def span(keys, words):
        ws = [words[k] for k in keys if k in words]
        return (min(w['start'] for w in ws), max(w['end'] for w in ws)) if ws else None

    bwords = {(w['clip'], w['index']): w for w in avant['words']}
    b_hook, d_hook = span(hook, bwords), span(hook, carte.dw)
    d_cta = span(cta, carte.dw)
    if b_hook and d_hook:
        carte.hook = (b_hook[1], d_hook[1])
    # debut de l'appel a l'action (bloc ctaBlock, sinon sa derniere phrase) : ses graphismes sont gardes
    block_of = {c['id']: c['block'] for c in base['clips']}
    cta_starts = [w['start'] for w in avant['words'] if reel.get('ctaBlock') and block_of.get(w['clip']) == reel.get('ctaBlock')]
    b_cta = min(cta_starts) if cta_starts else (span(cta, bwords) or (carte.btotal,))[0]
    placed = []  # (debut d'origine, nouveau debut ou None) : les bruitages colles a un element le suivent

    def track(elems, kind_of, keep_of, piste, name_of, zones=()):
        """Place les elements d'une piste : [(origine, nouveau ou None, raison)]."""
        out = []
        for x in elems:
            s, d, why = carte.place(x['at'], x['duration'], keep=keep_of(x), hold=MIN_HOLD.get(kind_of(x), 1.2))
            if s is not None and (d < 0.3 or s >= carte.dtotal - 0.2):
                s, why = None, 'depasse'
            y = None if s is None else {**x, **_fit(s, d, carte.dtotal)}
            # zones protegees (plans de coupe) : on garde le plus long morceau hors de la zone
            for z, zwhy in zones:
                if y is None or not z or y['at'] + y['duration'] <= z[0] or y['at'] >= z[1]:
                    continue
                a0, a1 = y['at'], y['at'] + y['duration']
                piece = max([(a0, min(a1, z[0])), (max(a0, z[1]), a1)], key=lambda p: p[1] - p[0])
                if piece[1] - piece[0] < 0.6:
                    y, why = None, zwhy
                    break
                if 'in' in y:
                    y['in'] = round(y['in'] + piece[0] - a0, 3)
                y.update(_fit(piece[0], piece[1] - piece[0], carte.dtotal))
                why = zwhy
            out.append([x, y, why])
        # deux elements qui ne se chevauchaient pas ne doivent pas se chevaucher apres la coupe : un element pose
        # sur la phrase suivante (garde) attend la fin du precedent, sinon le precedent est raccourci
        live = [o for o in out if o[1] is not None and not o[0].get('suggested')]
        fixed = sorted([o for o in live if o[2] != 'garde'], key=lambda o: o[1]['at'])
        for o, nxt in zip(fixed, fixed[1:]):
            (x0, y0, _), (x1, y1, _) = o, nxt
            if y0 is None:
                continue
            before = x0['at'] + x0['duration'] <= x1['at'] + 0.05 or x1['at'] + x1['duration'] <= x0['at'] + 0.05
            if before and y0['at'] + y0['duration'] > y1['at'] + 0.02:
                d = round(y1['at'] - y0['at'] - 0.05, 2)
                if d < 0.6:
                    o[1], o[2] = None, 'chevauche'
                else:
                    y0['duration'], o[2] = d, o[2] or 'chevauche'
        busy = [(o[1]['at'], o[1]['at'] + o[1]['duration']) for o in fixed if o[1] is not None]
        for o in sorted([o for o in live if o[2] == 'garde'], key=lambda o: o[1]['at']):
            x, y = o[0], o[1]
            t, need, least = y['at'], y['duration'], min(x['duration'], MIN_HOLD.get(kind_of(x), 1.2))
            for a, b in sorted(busy):
                if b <= t:
                    continue
                if a >= t + need:
                    break
                if a - t >= least:
                    need = a - t - 0.05
                    break
                t = b + 0.05
            if t + least > carte.dtotal:
                o[1], o[2] = None, 'chevauche'
                continue
            y.update(_fit(t, need, carte.dtotal))
            busy.append((y['at'], y['at'] + y['duration']))
        for x, y, why in out:
            if not x.get('suggested'):
                placed.append((x['at'], None if y is None else y['at']))
            note(piste, name_of(x), x['at'], x['duration'], None if y is None else y['at'], 0 if y is None else y['duration'],
                 why, show=not x.get('suggested'))
        return [y for _, y, _ in out if y is not None]

    if reel.get('graphics'):
        # gardes meme si leur phrase est coupee : le logo et les graphismes de l'appel a l'action (sauf le chiffre et
        # le mot geant, qui affichent un mot dit : ils n'ont plus de sens sans lui)
        keep = lambda g: g.get('kind') == 'logo' or (g['at'] >= b_cta - 0.3 and g.get('kind') not in ('chiffre', 'motgeant'))
        reel['graphics'] = track(reel['graphics'], lambda g: g.get('kind'), keep, 'graphisme', _graphic_name)
    if reel.get('broll'):
        # aucun plan de coupe sur l'accroche ni sur la derniere phrase de l'appel a l'action
        zones = []
        if d_hook:
            zones.append(((d_hook[0] - 0.1, d_hook[1] + 0.1), 'accroche'))
        if d_cta:
            zones.append(((d_cta[0] - 0.1, d_cta[1] + 0.2), 'appel'))
        reel['broll'] = sorted(track(reel['broll'], lambda b: 'broll', lambda b: False, 'plan de coupe',
                                     lambda b: f"Plan de coupe « {b['word']} »" if b.get('word') else 'Plan de coupe', zones),
                               key=lambda b: b['at'])
    sfx = reel.get('sfx') or {}
    if sfx.get('extra'):
        kept = []
        for e in sfx['extra']:
            tied = next((p for p in placed if abs(e['t'] - p[0]) <= 0.12), None)
            if tied:
                t, why = (None, 'lie') if tied[1] is None else (tied[1] + e['t'] - tied[0], 'suit')
            else:
                t, _, why = carte.place(e['t'], 0)
                if t is not None and t > carte.dtotal - 0.1:
                    t, why = None, 'depasse'
            note('bruitage', f"Bruitage « {e.get('name', '')} »", e['t'], 0, t, 0, why)
            if t is not None:
                kept.append({**e, 't': round(max(0.0, t), 2)})
        sfx['extra'] = sorted(kept, key=lambda e: e['t'])
    banner = reel.get('banner')
    if banner:
        # le bandeau est une plage (debut -> fin) : son debut suit son mot, sa fin suit la meme image
        start, end = banner.get('start') or 0, banner.get('end')
        s = carte.place(start, 0, keep=True)[0] if start > 0 else 0.0
        new = {'start': round(s, 2)}
        if end is not None:
            e = carte.until(end)
            # un bandeau qui tenait dans l'accroche y reste
            if b_hook and d_hook and end <= b_hook[1] + 0.35:
                e = min(e, d_hook[1] + 0.35)
            new['end'] = round(min(carte.dtotal, max(e, s + 0.5)), 2)
        if banner.get('enabled') and (banner.get('text') or '').strip():
            dur, new_dur = (0, 0) if end is None else (end - start, new['end'] - new['start'])
            note('bandeau', 'Bandeau', start, dur, new['start'], new_dur, 'plage' if new_dur < dur - 0.05 else None)
        banner.update(new)
    overrides = (reel.get('zoom') or {}).get('overrides') or {}
    if overrides:
        # zooms de relance : par numero de segment, qui change apres la coupe
        new = {}
        for k, v in overrides.items():
            b = next((s for s in carte.bs if str(s['index']) == str(k)), None)
            hits = [d for d in carte.ds if b and d['clip'] == b['clip'] and min(d['src_out'], b['src_out']) - max(d['src_in'], b['src_in']) > 0.05]
            for d in hits:
                new.setdefault(str(d['index']), v)
            if b and not hits:
                note('zoom', 'Zoom de relance', b['out_start'], 0, None, 0)
        reel['zoom']['overrides'] = new
    return report
