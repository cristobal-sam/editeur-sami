"""Habillage motivé par les mots ; aucun média externe, aucune statistique inventée.

Regle de monteur (sobriete) : chaque element a une raison (un mot fort, un vrai chiffre, une idee), un seul a la
fois, rien sur l'accroche, jamais sur le visage. Les mots mis en avant viennent de la MEME selection que les
sous-titres (reel.auto_highlights / reel.key_blocks) : chiffre + unite, puis benefice/douleur, marque, verbe fort.
En cas de doute, l'element est cree masque : c'est une proposition que le monteur peut afficher."""
import copy
import re
import statistics

from .script import normalize

# textes techniques qui ne doivent jamais apparaitre a l'image
TECH_LABEL = re.compile(r'exemple|illustration|interface|d[ée]mo\b|mockup|example|pas une mesure', re.I)
# marque de l'utilisateur : nom d'application seulement si elle est dite dans la video
OWN_BRANDS = ('RyuCalls',)
HOOK_MAX = 4.5  # l'accroche : rien d'autre que le bandeau
KEY_MIN = 4.0  # force minimale d'un mot pour un habillage (chiffre + unite, benefice, marque, bouton)
_TITLES = {}  # titres de notification deja ecrits par l'IA (un seul appel par phrase et par processus)

_TRIGGER = re.compile(r'^(leads?|prospects?|notifications?|messages?|textos?|sms|courriels?|e?mails?|app|application|'
                      r'telephone|appels?|appel\w+|rappel\w*|repond\w*|reponses?|calls?|call\w+|texts?|repl\w+)$')


def _times(reel):
    """Instant approximatif (dans le montage) de chaque mot : {(plan, indice): t}."""
    out, elapsed = {}, 0.0
    for c in reel['clips']:
        speed = c.get('speed') or 1
        for i, w in enumerate(c['words']):
            if 'start' in w:
                out[(c['id'], i)] = elapsed + max(0.0, w['start'] - c['in']) / speed
        elapsed += max(0.0, c['out'] - c['in']) / speed
    return out


def _hook_end(reel, times):
    """Fin de l'accroche : premiere idee du premier plan (au plus HOOK_MAX s)."""
    from .reel import idea_groups
    first = next((c for c in reel['clips'] if c['words']), None)
    if not first:
        return 0.0
    ideas = idea_groups(first['words'])
    if not ideas:
        return 0.0
    last = ideas[0][-1]
    t = times.get((first['id'], last), 0.0) + max(0.0, first['words'][last].get('end', 0) - first['words'][last].get('start', 0))
    return min(HOOK_MAX, t)


def _face_at(src, t, dur=2.4):
    """Visage pendant la scene (0-1, cadre de la prise) : piste de recadrage, sinon echantillons. -> (cx, cy, w)"""
    track = [p for p in (src.get('track') or []) if t - 0.3 <= p[0] <= t + dur]
    pts = [(p[1], p[2], p[3] if len(p) > 3 else None) for p in track]
    if not pts:
        pts = [(p[1], p[2], None) for p in (src.get('samples') or []) if t - 0.6 <= p[0] <= t + dur + 0.6]
    if not pts:
        pts = [(p[1], p[2], None) for p in (src.get('samples') or [])]
    if not pts:
        return 0.5, 0.42, None
    ws = [p[2] for p in pts if p[2]]
    return (statistics.median(p[0] for p in pts), statistics.median(p[1] for p in pts),
            statistics.median(ws) if ws else None)


def free_spot(reel, clip, index, height=0.12, width=0.78, dur=2.4):
    """Place d'un encadre (centre x, y en 0-1 de l'image, echelle) hors du visage : dans l'espace au-dessus de la
    tete s'il suffit, sinon a cote du visage, sinon dans la zone des sous-titres (masques pendant l'encadre).
    Meme cadrage que framing() de timeline.ts. height / width : taille de l'encadre (hauteur en part de l'image,
    largeur en part du petit cote)."""
    W, H = reel['width'], reel['height']
    src = reel['sources'].get(clip['source']) or {}
    t = clip['words'][index].get('start', clip['in'])
    fx, fy, fw = _face_at(src, t, dur)
    sw, sh = src.get('width') or 1080, src.get('height') or 1920
    k = max(W / sw, H / sh)
    dw, dh = sw * k, sh * k
    left = min(0.0, max(W - dw, W / 2 - fx * dw))
    top = min(0.0, max(H - dh, H * 0.42 - fy * dh))
    x, y = (fx * dw + left) / W, (fy * dh + top) / H
    half_w = ((fw or 0.26) * dw / W) / 2 + 0.03  # demi-largeur du visage (+ cheveux)
    head_top = y - 0.13 * dh / H  # du centre du visage au haut de la tete, cheveux compris
    u = min(W, H)
    card_w = width * u / W  # largeur de l'encadre en part de la largeur de l'image
    margin = 0.06 if H > W else 0.05  # bord haut (interface des reseaux)
    if head_top - margin >= height + 0.02:
        return {'x': 0.5, 'y': round(margin + (head_top - margin) / 2, 3), 'scale': 1}
    room_left, room_right = x - half_w, 1 - x - half_w
    room = max(room_left, room_right)
    if room >= 0.3:
        scale = min(1.0, (room - 0.03) / card_w)
        cx = (x - half_w - 0.015 - card_w * scale / 2) if room_left >= room_right else (x + half_w + 0.015 + card_w * scale / 2)
        return {'x': round(cx, 3), 'y': round(max(margin + height / 2, y - 0.03), 3), 'scale': round(scale, 2)}
    return {'x': 0.5, 'y': round((reel.get('style') or {}).get('position', 0.72), 3), 'scale': 0.9}


def app_name(reel):
    """Nom affiche en tete de notification : la marque du reel, sinon la marque de l'utilisateur SI elle est dite
    dans la video, sinon un nom neutre."""
    from .reel import _brands
    brand = ((reel.get('brand') or {}).get('name') or '').strip()
    if brand:
        return brand
    said = ''.join(normalize(w['w']) for c in reel['clips'] for w in c['words'] if not w.get('cut'))
    for name in list(_brands(reel)) + list(OWN_BRANDS):
        if name and normalize(name).replace(' ', '') in said:
            return name
    return 'Messages'


def _said_numbers(clip, idea):
    from .graphismes import NUMBER_WORDS, _number
    vals = set()
    for k in idea:
        raw = clip['words'][k]['w']
        n = _number(clip['words'], k)
        if n:
            vals.add(n[0])
        core = normalize(raw.strip(' ,.!?;:'))
        if core in NUMBER_WORDS:
            vals.add(float(NUMBER_WORDS[core]))
        for d in re.findall(r'\d+(?:[.,]\d+)?', raw):
            vals.add(float(d.replace(',', '.')))
    return vals


def _time_number(clip, idea):
    """Premier nombre avec une unite de temps dit dans l'idee : « 3 h », « 5 min »."""
    from .graphismes import _number
    for k in idea:
        n = _number(clip['words'], k)
        if n and n[2].strip() in ('h', 'min', 's', 'jour', 'jours', 'semaine', 'semaines'):
            return f'{n[0]:g}{n[2]}'
    return None


def _notif_rule(clip, idea, lang):
    """Titre de notification par des regles simples -> (titre, confiance 0-3) ; 0 = rien de clair a illustrer."""
    toks = [normalize(clip['words'][k]['w']).split("'")[-1] for k in idea]
    lead = any(t in ('lead', 'leads', 'prospect', 'prospects') for t in toks)
    wait = any(t.startswith(('attend', 'attente', 'wait')) for t in toks)
    reply = any(t.startswith(('repond', 'reponse', 'repl', 'answer')) for t in toks)
    call = any(t.startswith(('appel', 'rappel', 'call')) or t in ('telephone', 'phone') for t in toks)
    msg = any(t in ('message', 'messages', 'texto', 'textos', 'sms', 'courriel', 'courriels', 'email', 'emails', 'text',
                    'texts') for t in toks)
    when = _time_number(clip, idea)
    en = lang == 'en'
    if lead and wait and when:
        return (f'Lead waiting for {when}' if en else f'Lead en attente depuis {when}'), 3
    if reply and when:
        return (f'Reply sent in {when}' if en else f'Réponse envoyée en {when}'), 3
    if lead and reply:
        return ('Reply sent to lead' if en else 'Réponse envoyée au lead'), 2
    if lead and call:
        return ('New lead to call' if en else 'Nouveau lead à appeler'), 2
    if lead:
        return ('New lead received' if en else 'Nouveau lead reçu'), 2
    if msg:
        return ('New message' if en else 'Nouveau message'), 2
    if reply:
        return ('Reply sent' if en else 'Réponse envoyée'), 1
    if call:
        return ('Incoming call' if en else 'Appel entrant'), 1
    return None, 0


def valid_title(title, clip, idea):
    """Titre de notification accepte seulement s'il est court (2 a 6 mots), sans points de suspension ni texte
    technique, sans chiffre qui n'est pas dit, et pas une phrase recopiee. -> titre propre ou None"""
    from .graphismes import NUMBER_WORDS
    t = re.sub(r'\s+', ' ', str(title or '')).strip().strip('«»"“”\'').strip()
    t = t.rstrip('.!;:, ')
    if not t or '…' in t or '...' in t or len(t) > 42 or TECH_LABEL.search(t):
        return None
    n = len(t.split())
    if n < 2 or n > 6:
        return None
    said = _said_numbers(clip, idea)
    for d in re.findall(r'\d+(?:[.,]\d+)?', t):
        if float(d.replace(',', '.')) not in said:
            return None  # chiffre invente
    toks = [normalize(x) for x in t.split()]
    for x in toks:
        if x in NUMBER_WORDS and x not in ('un', 'une') and float(NUMBER_WORDS[x]) not in said:
            return None
    from .reel import _core
    spoken = [_core(clip['words'][k]['w']) for k in idea]
    mine = [_core(x) for x in t.split()]
    grams = {tuple(spoken[i:i + 4]) for i in range(len(spoken) - 3)}
    if any(tuple(mine[i:i + 4]) in grams for i in range(len(mine) - 3)):
        return None  # morceau de phrase recopie (4 mots dits a la suite), pas une notification
    return t[0].upper() + t[1:]


def _ai_titles(cands, lang):
    """Titres reformules par l'IA locale (JSON strict, temperature 0), valides un par un ; None si l'IA ne sait pas."""
    import os
    from . import llm
    if os.environ.get('EDITEUR_LLM', '1') == '0' or not llm.available():
        return {}
    todo = [c for c in cands if (lang, c['phrase']) not in _TITLES]
    if todo:
        if lang == 'en':
            ask = ("For each numbered sentence of an ad, write the title of a realistic phone notification that the "
                   "business owner would receive and that illustrates the idea (examples: \"New lead received\", "
                   "\"Reply sent in 5 min\", \"Lead waiting for 3 h\", \"New message\"). Rules: 2 to 6 words, in "
                   "English, no ellipsis, no quotes, never copy the sentence; no number, brand or result that is not "
                   "said in the sentence. If the sentence is not about a lead, a message, a call or a reply, use null. "
                   'Answer {"notifications": [{"n": 1, "titre": "..." or null}]}.\n')
        else:
            ask = ("Pour chaque phrase numerotee d'une publicite, ecris le titre d'une notification de telephone "
                   "realiste, comme en recevrait l'entrepreneur, qui illustre l'idee (exemples : « Nouveau lead reçu », "
                   "« Réponse envoyée en 5 min », « Lead en attente depuis 3 h », « Nouveau message »). Regles : 2 a 6 "
                   "mots, en francais, sans points de suspension ni guillemets, ne recopie jamais la phrase ; aucun "
                   "chiffre, aucune marque ni aucun resultat qui ne soit pas dit dans la phrase. Si la phrase ne parle "
                   "ni d'un lead, ni d'un message, ni d'un appel, ni d'une reponse, mets null. "
                   'Reponds {"notifications": [{"n": 1, "titre": "..." ou null}]}.\n')
        try:
            with llm.session():
                data = llm.ask_json(llm.EDITOR, ask + '\n'.join(f"{n + 1}: {c['phrase']}" for n, c in enumerate(todo)),
                                    temperature=0, max_tokens=60 + 30 * len(todo))
            items = data.get('notifications') if isinstance(data, dict) else None
            for item in items if isinstance(items, list) else []:
                if isinstance(item, dict) and isinstance(item.get('n'), int) and 1 <= item['n'] <= len(todo):
                    c = todo[item['n'] - 1]
                    _TITLES[(lang, c['phrase'])] = valid_title(item.get("titre"), c["clip"], c["idea"]) \
                        if item.get('titre') else None
        except Exception as e:  # l'IA est un plus : les regles suffisent
            print(f'IA locale indisponible pour les notifications ({e}) : regles simples utilisees.')
            return {}
    return {c['phrase']: _TITLES.get((lang, c['phrase'])) for c in cands}


def _notifications(reel, times, hook_end, lang, use_ai):
    """Notifications du style Tech : une par idee qui parle d'un lead, d'un message, d'un appel ou d'une reponse ;
    peu nombreuses (une par 20 s environ, 8 s d'ecart), jamais sur l'accroche, hors du visage. Les idees moins
    claires deviennent des propositions masquees."""
    from .reel import idea_groups
    cands = []
    for clip in reel['clips']:
        for idea in idea_groups(clip['words']):
            trig = [k for k in idea if _TRIGGER.match(normalize(clip['words'][k]['w']).split("'")[-1])]
            if not trig:
                continue
            title, conf = _notif_rule(clip, idea, lang)
            at = times.get((clip['id'], trig[0]), 0)
            if not conf or at < hook_end:
                continue
            phrase = ' '.join(clip['words'][k]['w'] for k in idea)
            cands.append({'clip': clip, 'idea': idea, 'index': trig[0], 'at': at, 'title': title, 'conf': conf,
                          'phrase': phrase})
    if not cands:
        return []
    total = max(times.values()) if times else 0
    budget = max(1, round(total / 20))
    shown, hidden = [], []
    for c in sorted(cands, key=lambda c: (-c['conf'], c['at'])):
        if c['conf'] >= 2 and len(shown) < budget and all(abs(c['at'] - o['at']) >= 8 and o['title'] != c['title']
                                                          for o in shown):
            shown.append(c)
        elif len(hidden) < 3 and all(abs(c['at'] - o['at']) >= 4 for o in shown + hidden):
            hidden.append(c)
    app = app_name(reel)
    ai = _ai_titles(shown + hidden, lang) if use_ai else {}
    scenes = []
    for c in sorted(shown + hidden, key=lambda c: c['at']):
        title = ai.get(c['phrase']) or c['title']
        if c['phrase'] in ai and ai[c['phrase']] is None and c['conf'] < 3:
            c['hidden'] = True  # l'IA ne voit rien a illustrer : proposition seulement
        spot = free_spot(reel, c['clip'], c['index'], height=0.11)
        scenes.append({'id': f"style-{c['clip']['id']}-{c['index']}", 'kind': 'notification', 'clip': c['clip']['id'],
                       'index': c['index'], 'length': 1, 'text': title, 'secondary': app, 'duration': 2.4,
                       **spot, 'rotation': 0, 'color': (reel.get('design') or {}).get('accent', reel['style']['highlight']),
                       **({'hidden': True} if any(c is h for h in hidden) or c.get('hidden') else {})})
    return scenes


def _keyword_scenes(reel, mode, times, hook_end):
    """Mot geant (Editorial) ou autocollant (Collage) : les blocs deja en couleur, du plus fort au plus faible,
    seulement les blocs forts (KEY_MIN), un toutes les 6 s (8 s pour le Collage), jamais deux fois le meme mot,
    rien sur l'accroche."""
    from .reel import key_blocks
    clips = {c['id']: c for c in reel['clips']}
    blocks = []
    for b in key_blocks(reel):
        at = times.get((b['clip'], b['index']))
        if at is None or at < hook_end:
            continue
        blocks.append({**b, 'at': at})
    chosen, texts = [], set()
    gap = 6 if mode == 'editorial' else 8  # l'autocollant cache les sous-titres : plus rare
    for b in sorted(blocks, key=lambda b: (-b['score'], b['at'])):
        key = normalize(b['text'])
        if b['score'] < KEY_MIN or key in texts or any(abs(b['at'] - o['at']) < gap for o in chosen):
            continue  # un mot moyen reste en couleur dans les sous-titres, sans habillage en plus
        chosen.append(b)
        texts.add(key)
    accent = (reel.get('design') or {}).get('accent', reel['style']['highlight'])
    return [{'id': f"style-{b['clip']}-{b['index']}", 'kind': 'keyword' if mode == 'editorial' else 'paper',
             'clip': b['clip'], 'index': b['index'], 'length': b['length'], 'text': b['text'], 'secondary': '',
             'duration': 2.4, 'x': 0.5, 'y': 0.69, 'scale': 1, 'rotation': -4 if mode == 'collage' else 0,
             'color': accent} for b in sorted(chosen, key=lambda b: b['at']) if b['clip'] in clips]


def prepare(reel, use_ai=True):
    from .reel import reel_language
    mode = (reel.get('design') or {}).get('mode')
    if not mode:
        reel.pop('styleScenes', None)
        return
    lang = reel_language(reel)
    words = [(c, i, w) for c in reel['clips'] for i, w in enumerate(c['words'])
             if not w.get('cut') and not w.get('hide')]
    times = _times(reel)
    hook_end = _hook_end(reel, times)
    valid = {}
    if use_ai and mode == 'produit':
        from . import llm
        import os
        if os.environ.get('EDITEUR_LLM', '1') != '0' and llm.available():
            try:
                with llm.session():
                    data = llm.ask_json(llm.EDITOR,
                        f'Style {mode}. Choisis seulement des mots EXACTS dits dans cette transcription pour illustrer une idée. '
                        'Ne crée aucun chiffre, bénéfice, résultat, témoignage ni marque. '
                        'JSON {"indices": [indices de mots importants, maximum 6]}.\n' +
                        '\n'.join(f'{j}: {w["w"]}' for j, (_, _, w) in enumerate(words)), max_tokens=150, temperature=0)
                    valid = {int(i): True for i in data.get('indices', []) if isinstance(i, int) and 0 <= i < len(words)}
            except Exception:
                pass
    scenes = []
    from .graphismes import _number
    if mode == 'hormozi':
        elapsed, last_emoji = 0, -99
        for clip in reel['clips']:
            clip['emojis'] = []
            for i, w in enumerate(clip['words']):
                number = _number(clip['words'], i)
                at = elapsed + w['start'] - clip['in']
                if not w.get('cut') and not w.get('hide') and number and number[2].strip() in ('h', 'min', 's') and at >= 3 and at-last_emoji >= 8:
                    clip['emojis'].append([i, '⏱️'])
                    last_emoji = at
            elapsed += clip['out'] - clip['in']
    if mode in ('editorial', 'collage'):
        scenes = _keyword_scenes(reel, mode, times, hook_end)
    elif mode == 'tech':
        scenes = _notifications(reel, times, hook_end, lang, use_ai)
    last_at = -99.0
    for j, (clip, i, w) in enumerate(words if mode in ('infographie', 'comparatif', 'produit') else []):
        n = normalize(w['w']).strip(' ,.!?;:')
        kind, text, secondary, length = None, '', '', 1
        number = _number(clip['words'], i)
        at = times.get((clip['id'], i), 0)
        if mode == 'infographie' and number:
            value, prefix, suffix, length = number
            text = f'{prefix}{value:g}{suffix}'
            kind = 'metric'
            after = [normalize(x['w']).strip("'") for x in clip['words'][i + length:i + length + 2]]
            if prefix == '×' and len(after) == 2 and after[0] in ('moins', 'plus', 'less', 'more'):
                # « cinq fois moins cher » : « ×5 » seul ferait croire a « cinq fois plus »
                text = f"{value:g}× {' '.join(x['w'].strip(' ,.!?;:') for x in clip['words'][i + length:i + length + 2])}"
                length += 2
        elif mode == 'comparatif' and n in ('pas', 'contre', 'vs'):
            # Deux quantités explicites de part et d'autre ; « pas mieux » n'est pas une comparaison chiffrée.
            left = [(k, _number(clip['words'], k)) for k in range(max(0, i-9), i)]
            right = [(k, _number(clip['words'], k)) for k in range(i+1, min(len(clip['words']), i+10))]
            left = [(k,v) for k,v in left if v]
            right = [(k,v) for k,v in right if v]
            if left and right:
                k,a = left[-1]; l,b = right[0]
                first = ' '.join(x['w'].strip(' ,.!?') for x in clip['words'][k:k+a[3]])
                second = ' '.join(x['w'].strip(' ,.!?') for x in clip['words'][l:l+b[3]])
                kind = 'comparison'
                text, secondary = (second, first) if n == 'pas' else (first, second)
        elif mode == 'produit' and re.search(r'^(ryucalls|produit|carte|t[eé]l[eé]phone)$', n):
            kind, text = 'product', w['w'].strip(' ,.!?')
        if not kind:
            continue
        # Une scène toutes les 4 s au plus, ancrée au mot : ni empilement ni effet à chaque coupe ; rien sur
        # l'accroche (sauf la comparaison, qui explique toute la phrase).
        if at < last_at + 4 or (kind == 'metric' and at < hook_end):
            continue
        if mode == 'produit' and valid and j not in valid:
            continue
        last_at = at
        spot = free_spot(reel, clip, i, height=0.15) if kind == 'metric' else {'x': 0.5, 'y': 0.69, 'scale': 1}
        scenes.append({'id': f"style-{clip['id']}-{i}", 'kind': kind, 'clip': clip['id'], 'index': i,
                       'length': length, 'text': text, 'secondary': secondary, 'duration': 2.4,
                       **spot, 'rotation': 0,
                       'color': (reel.get('design') or {}).get('accent', reel['style']['highlight'])})
    reel['styleScenes'] = scenes


def sober(reel):
    """Corrige le chemin automatique complet, y compris ses propositions IA : mots en couleur revalides par la
    selection commune (un par idee, retouches a la main gardees) et graphismes generes retires."""
    from .reel import rehighlight
    rehighlight(reel)
    # Aucun effet automatique ne doit couvrir l'accroche. Les éléments posés à la main restent intacts.
    reel['graphics'] = [g for g in reel.get('graphics', []) if not g.get('generated')]


def apply(reel, template):
    from .reel import rehighlight
    old = reel.get('design') or {}
    reel['design'] = copy.deepcopy(template.get('design') or {})
    # Ressources produit choisies par le monteur : gardées en changeant de style.
    for k in ('productImage', 'productModel', 'productVideo'):
        if old.get(k):
            reel['design'][k] = old[k]
    if reel['design'].get('mode'):
        reel['design'].setdefault('suppressExtras', True)
        sober(reel)
    else:
        rehighlight(reel)  # meme selection au rythme des sous-titres du nouveau style
    prepare(reel)
