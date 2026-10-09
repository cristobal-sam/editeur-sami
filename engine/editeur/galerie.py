"""Habillage motivé par les mots ; aucun média externe, aucune statistique inventée.

Regle de monteur (sobriete) : chaque element a une raison (un mot fort, un vrai chiffre, une idee), un seul a la
fois, rien sur l'accroche, jamais sur le visage. Les mots mis en avant viennent de la MEME selection que les
sous-titres (reel.auto_highlights / reel.key_blocks) : chiffre + unite, puis benefice/douleur, marque, verbe fort.
En cas de doute, l'element est cree masque : c'est une proposition que le monteur peut afficher."""
import copy
import re
import statistics

from . import orthographe, verrous
from .script import normalize

# textes techniques qui ne doivent jamais apparaitre a l'image
TECH_LABEL = re.compile(r'exemple|illustration|interface|d[ée]mo\b|mockup|example|pas une mesure', re.I)
# marque de l'utilisateur : nom d'application seulement si elle est dite dans la video
OWN_BRANDS = ('RyuCalls',)
KEY_MIN = 4.0  # force minimale d'un mot pour un habillage (chiffre + unite, benefice, marque, bouton)
CTA_UNIQUE = 14.0  # s : deux demandes du bouton plus proches -> un seul bouton tenu jusqu'a la fin (jamais il sort et revient)
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
    """Meme accroche que la relecture, sur les temps reels apres coupes et resserrage."""
    from . import montage, sobriete
    seg = montage.compute(reel)
    hook = sobriete.accroche_fin(seg['words'], seg['duration'], sobriete.budget(sobriete._template(reel, None)))
    # le plan creatif decide « visage et phrase seuls » pendant tout son temps d'accroche : aucune interface n'y est creee
    # (avant, une scene posee la etait masquee ensuite et prenait la place d'une scene utile juste apres)
    plan = reel.get('creativePlan') or {}
    if plan.get('enabled') is not False:
        for b in plan.get('beats') or []:
            if b.get('role') == 'accroche' and isinstance(b.get('end'), (int, float)):
                hook = max(hook, min(float(b['end']), 12.0, seg['duration'] * 0.3))
    return hook


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
    # deux indices dans la meme idee (lead + reponse, lead + appel) : idee claire, l'IA peut la reformuler mais pas l'effacer
    if lead and reply:
        return ('Reply sent to lead' if en else 'Réponse envoyée au lead'), 2.5
    if lead and call:
        return ('New lead to call' if en else 'Nouveau lead à appeler'), 2.5
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
    ai = None
    if use_ai and reel.get('claude'):
        # cerveau Claude (resultat garde dans le reel, aucun appel ici) : ses titres d'abord, verifies par valid_title ;
        # sans resultat utilisable, l'IA locale comme avant
        try:
            from . import cerveau_claude
            ai = cerveau_claude.titres_notifications(reel, shown + hidden)
        except Exception as e:
            print(f'Titres de Claude ignores ({e}).')
    if ai is None:
        ai = _ai_titles(shown + hidden, lang) if use_ai else {}
    else:
        # idees que Claude n'a pas lues (plan change depuis son appel) : l'IA locale, comme avant
        reste = [c for c in shown + hidden if c['phrase'] not in ai]
        if reste:
            ai = {**_ai_titles(reste, lang), **ai}
    scenes = []
    for c in sorted(shown + hidden, key=lambda c: c['at']):
        title = ai.get(c['phrase']) or c['title']
        if c['phrase'] in ai and ai[c['phrase']] is None and c['conf'] < 2.5:
            c['hidden'] = True  # l'IA ne voit rien a illustrer (idee a un seul indice) : proposition seulement
        spot = free_spot(reel, c['clip'], c['index'], height=0.11)
        scenes.append({'id': f"style-{c['clip']['id']}-{c['index']}", 'kind': 'notification', 'clip': c['clip']['id'],
                       'index': c['index'], 'length': 1, 'text': title, 'secondary': app, 'duration': 2.4,
                       **spot, 'rotation': 0, 'color': (reel.get('design') or {}).get('accent', reel['style']['highlight']),
                       **({'hidden': True} if any(c is h for h in hidden) or c.get('hidden') else {})})
    return scenes


# Enumerations dites (« un salaire, des avantages sociaux, des vacances et des journees de maladie ») : chaque element
# commence par un determinant, apres une virgule ou un « et / ou » ; il est montre au moment ou il est dit.
_DETS = {'fr': ('un', 'une', 'des', 'du', 'le', 'la', 'les', "l'", 'vos', 'votre', 'nos', 'notre', 'ses', 'son', 'sa', 'leur',
                'leurs', 'mes', 'mon', 'ma', 'tes', 'ton', 'ta', 'aucun', 'aucune', 'plus', 'moins'),
         'en': ('a', 'an', 'the', 'your', 'our', 'their', 'my', 'his', 'her', 'more', 'less', 'no')}
_LIAISONS = {'fr': ('et', 'ou', 'puis'), 'en': ('and', 'or', 'then')}
# fin d'un element : un complement qui ne fait plus partie du nom (« journees de maladie A PAYER », « salaire AU complet »)
_FIN_ITEM = {'fr': ('a', 'au', 'aux', 'pour', 'si', 'qui', 'que', 'qu', 'dont', 'peu', 'sans', 'avec', 'chez', 'quand', 'comme',
                    'est', 'sont', 'sera', 'seront', 'ont', 'va', 'vont', 'fait', 'font', 'peut', 'peuvent', 'doit', 'doivent',
                    'etait', 'etaient', 'reste', 'restent', 'coute', 'coutent'),
             'en': ('to', 'for', 'if', 'who', 'that', 'which', 'with', 'without', 'when', 'like', 'is', 'are', 'was', 'were',
                    'will', 'can', 'has', 'have', 'cost', 'costs')}
_DET_GARDE = ('plus', 'moins', 'aucun', 'aucune', 'more', 'less', 'no')  # determinant qui porte le sens : garde dans le texte
LISTE_MAX = 4


def enumerations(clip, lang='fr'):
    """Enumerations d'un plan : [(indices des noms, [textes])] ; au moins 3 elements de 1 a 3 mots, chacun introduit par
    un determinant apres une virgule ou une liaison (et / ou), dans la meme phrase. Rien n'est reformule : le texte de
    chaque element est celui qui est dit (determinant et complement retires)."""
    lang = 'en' if lang == 'en' else 'fr'
    words = clip['words']
    ok = [k for k, w in enumerate(words) if not w.get('cut') and not w.get('hide') and str(w.get('w') or '').strip()]
    norm = {k: normalize(str(words[k]['w']).strip(' ,.!?;:«»"()')) for k in ok}
    raw = {k: str(words[k]['w']).strip() for k in ok}
    fin = lambda k: re.search(r'[.!?…]["»”)\]]*$', raw[k]) is not None
    virgule = lambda k: raw[k].rstrip('»"”) ').endswith((',', ';'))
    dets, liaisons, stop = _DETS[lang], _LIAISONS[lang], _FIN_ITEM[lang]

    def det(k):
        n = norm.get(k, '')
        return n in dets or (lang == 'fr' and n.startswith(("l'", "d'")) and len(n) > 3)

    def item(pos):
        """Element qui commence au determinant ok[pos] -> (indice du nom, texte, position suivante) ou None."""
        k = ok[pos]
        n = norm[k]
        first = pos if (lang == 'fr' and n.startswith(("l'", "d'")) and n not in dets) or n in _DET_GARDE else pos + 1
        toks = []
        j = first
        while j < len(ok) and len(toks) < 3:
            kk = ok[j]
            if (j > first and (norm[kk] in liaisons or (norm[kk] in stop and norm[kk] != 'de') or det(kk))) or not norm[kk]:
                break
            toks.append(kk)
            if virgule(kk) or fin(kk):
                j += 1
                break
            j += 1
        if not toks:
            return None
        text = ' '.join(raw[x].strip(' ,.!?;:«»"()') for x in toks)
        if lang == 'fr' and n.startswith(("l'", "d'")) and n not in dets and toks[0] == k:
            text = re.sub(r"^[LlDd][’']", '', text)
        letters = re.sub(r'[^A-Za-zÀ-ÿ]', '', text)
        if len(letters) < 3 or re.search(r'\d', text):
            return None
        # le reste du complement (« au complet », « a payer ») jusqu'a la virgule ou la liaison suivante
        while j < len(ok) and not det(ok[j]) and norm[ok[j]] not in liaisons and not fin(ok[j - 1]) and not virgule(ok[j - 1]):
            j += 1
        return toks[0], text[:1].upper() + text[1:], j

    out, pos = [], 0
    while pos < len(ok):
        if not det(ok[pos]):
            pos += 1
            continue
        chain, p = [], pos
        while p < len(ok) and det(ok[p]):
            it = item(p)
            if not it:
                break
            chain.append(it)
            p = it[2]
            if p >= len(ok) or fin(ok[p - 1]):
                break
            # separateur : virgule a la fin de l'element, ou liaison (« et des vacances »)
            if p < len(ok) and norm[ok[p]] in liaisons:
                p += 1
            elif not virgule(ok[p - 1]):
                break
        texts = []
        for _, t, _ in chain:
            if normalize(t) not in [normalize(x) for x in texts]:
                texts.append(t)
        if len(chain) >= 3 and len(texts) == len(chain):
            chain = chain[:LISTE_MAX]
            out.append(([c[0] for c in chain], [c[1] for c in chain]))
            pos = p
        else:
            pos += 1
    return out


def _list_scenes(reel, times, hook_end, lang):
    """Liste du studio Tech 3D : chaque element d'une enumeration dite apparait sur son mot (pilules de verre) ; teinte
    chaude pendant le probleme (ce qu'on subit), couleur d'accent ailleurs (ce qu'on gagne)."""
    from . import creative
    plan = reel.get('creativePlan') or {}
    accent = (reel.get('design') or {}).get('accent', reel['style']['highlight'])
    scenes = []
    for clip in reel['clips']:
        for idx, texts in enumerations(clip, lang):
            at = times.get((clip['id'], idx[0]))
            last = times.get((clip['id'], idx[-1]))
            if at is None or last is None or at < hook_end or last - at > 7:
                continue
            beat = creative.beat_at(plan, at) or {}
            scenes.append({'id': f"style-{clip['id']}-{idx[0]}-liste", 'kind': 'list', 'clip': clip['id'], 'index': idx[0],
                           'length': 1, 'text': texts[0], 'secondary': '|'.join(texts[1:]), 'items': idx,
                           'duration': round(max(2.6, last - at + 1.6), 2), 'x': 0.5, 'y': 0.2, 'scale': 1, 'rotation': 0,
                           'color': '#FF7A66' if beat.get('role') == 'probleme' else accent})
    return scenes


# Promesses ou preuves dites en quelques mots : une pilule de verre avec une coche (« Formé par nos soins ✓ »), le temps de
# la dire. Expressions entieres seulement (jamais un mot seul comme « garantis ») ; le texte affiche est celui qui est dit.
_PREUVES = {'fr': (r"form[ée]e?s? par nos soins", r"sans engagement", r"sans risque", r"satisfaits? ou rembours[ée]e?s?",
                   r"sans frais(?: cach[ée]s)?", r"sans contrat", r"form[ée]e?s? (?:sur mesure|pour (?:vous|votre entreprise))"),
            'en': (r"trained by us", r"no commitment", r"risk[- ]free", r"money[- ]back guarantee", r"no hidden fees", r"no contract")}


def _claim_scenes(reel, times, hook_end, lang):
    """Badge de preuve (liste d'un element) sur une promesse dite en quelques mots ; remplit un long passage sans ecran
    (juge n° 2 : 10 s sans carte de 0:41,7 a 0:51,7), jamais sur l'accroche."""
    from . import creative
    plan = reel.get('creativePlan') or {}
    accent = (reel.get('design') or {}).get('accent', reel['style']['highlight'])
    pats = [re.compile(x, re.I) for x in _PREUVES.get(lang, _PREUVES['fr'])]
    out = []
    for clip in reel['clips']:
        words = clip['words']
        for i in range(len(words)):
            for n in range(5, 0, -1):
                seg = words[i:i + n]
                if len(seg) < n or any(x.get('cut') or x.get('hide') for x in seg):
                    continue
                txt = ' '.join(str(x['w']).strip(' ,.!?;:«»"') for x in seg)
                if not any(p.fullmatch(txt) for p in pats):
                    continue
                at = times.get((clip['id'], i))
                if at is None or at < hook_end:
                    continue
                beat = creative.beat_at(plan, at) or {}
                if beat.get('role') == 'probleme':
                    continue
                out.append({'id': f"style-{clip['id']}-{i}-preuve", 'kind': 'list', 'badge': True, 'clip': clip['id'], 'index': i,
                            'length': n, 'text': txt[:1].upper() + txt[1:], 'secondary': '', 'items': [i], 'duration': 2.6,
                            'x': 0.5, 'y': 0.2, 'scale': 1, 'rotation': 0, 'color': accent})
                break
    return out


_GRATUIT = re.compile(r'^(gratuit\w*|offert\w*|free)$')
_FEMININ = ('semaine', 'semaines', 'heure', 'heures', 'minute', 'minutes', 'seance', 'seances', 'h', 'min')
_DUREES = ('jour', 'jours', 'semaine', 'semaines', 'mois', 'heure', 'heures', 'minute', 'minutes', 'h', 'min', 'an', 'ans',
           'day', 'days', 'week', 'weeks', 'month', 'months')


def offre_dite(clip, index, lang='fr', fenetre=24):
    """Offre dite dans les mots qui precedent le bouton (au plus `fenetre` mots, meme plan) : une duree ET un mot de
    gratuite (« on place notre setter gratuitement ... pendant une semaine » -> « 1 semaine gratuite »). Rien d'autre
    n'est deduit : sans les deux, None."""
    from .graphismes import _number
    words = clip['words']
    lo = max(0, index - fenetre)
    vis = [k for k in range(lo, index) if not words[k].get('cut') and not words[k].get('hide')]
    free = any(_GRATUIT.match(normalize(str(words[k]['w']).strip(' ,.!?;:«»'))) for k in vis)
    if not free:
        return None
    for k in reversed(vis):
        n = _number(words, k)
        unit = (n[2] if n else '').strip()
        if n and unit and normalize(unit) in _DUREES:
            if lang == 'en':
                return f'{n[0]:g} {unit} free'
            fem = normalize(unit) in _FEMININ
            plural = n[0] > 1 and not unit.endswith(('s', 'x', 'h', 'min'))
            return f"{n[0]:g} {unit}{'s' if plural else ''} {'gratuite' if fem else 'gratuit'}{'s' if n[0] > 1 else ''}"
    return None


def offre_debut(clip, index, lang='fr', fenetre=24):
    """Premier mot de l'offre dite avant le bouton (le mot de gratuite ou la duree, le plus tot des deux), meme fenetre que
    offre_dite ; None sinon."""
    from .graphismes import _number
    words = clip['words']
    vis = [k for k in range(max(0, index - fenetre), index) if not words[k].get('cut') and not words[k].get('hide')]
    free = [k for k in vis if _GRATUIT.match(normalize(str(words[k]['w']).strip(' ,.!?;:«»')))]
    durees = [k for k in vis if (n := _number(words, k)) and n[2].strip() and normalize(n[2].strip()) in _DUREES]
    debut = min(free[:1] + durees[:1]) if free and durees else None
    return debut


# Mots d'un probleme vecu (attente, perte, concurrent...) : l'interface qui l'illustre prend une teinte chaude
_NEGATIF = re.compile(r'^(attend\w*|attente|perd\w*|perdu\w*|concurren\w*|trop|rate\w*|manqu\w*|oubli\w*|jamais|probleme\w*|'
                      r'retard\w*|lent\w*|wait\w*|lost|los[et]\w*|competitor\w*|never|late|slow\w*|miss\w*|problem\w*)$')
CHAUD = '#FF7A66'


def _negatif(reel, scene):
    """La phrase de l'interface decrit un probleme (attente, perte, concurrent) : mots de son idee."""
    from .reel import idea_groups
    clip = next((c for c in reel['clips'] if c['id'] == scene.get('clip')), None)
    if not clip:
        return False
    for idea in idea_groups(clip['words']):
        if scene.get('index') in idea:
            return any(_NEGATIF.match(normalize(clip['words'][k]['w']).split("'")[-1]) for k in idea)
    return False


def _product_scenes(reel, times, hook_end, lang, use_ai):
    """Interfaces premium du style Tech 3D, uniquement à partir de ce qui est réellement dit.

    Aucun faux écran de produit et aucune statistique inventée : le moteur met en scène un parcours, un tableau de
    suivi ou le vrai bouton d'appel à l'action seulement quand ces mots existent dans la phrase. Les notifications
    sûres restent le repli pour les idées simples (message, appel, réponse)."""
    from .reel import idea_groups
    action = re.compile(r'^(qualifi\w*|educ\w*|transfer\w*|repond\w*|appel\w*|rappel\w*|deleg\w*)$')
    lead = re.compile(r'^(lead\w*|prospect\w*)$')
    candidates = []
    ctas = []  # boutons d'appel a l'action dits (le premier et le dernier sont montres)
    for clip in reel['clips']:
        for idea in idea_groups(clip['words']):
            entries = [(k, normalize(clip['words'][k]['w']).strip("' ,.!?;:«»").split("'")[-1]) for k in idea]
            entries = [(k, n) for k, n in entries if n]
            if not entries:
                continue
            at = times.get((clip['id'], entries[0][0]), 0)
            if at < hook_end:
                continue
            raw = {k: clip['words'][k]['w'].strip(' ,.!?;:«»') for k, _ in entries}
            norms = [n for _, n in entries]
            # Le texte du bouton est repris mot pour mot, jamais reformulé.
            cta = None
            for pos in range(len(entries) - 1):
                pair = norms[pos:pos + 3]
                if pair[:2] == ['savoir', 'plus']:
                    cta = ' '.join(raw[entries[pos + j][0]] for j in range(2))
                    anchor = entries[pos][0]
                    break
                if pair == ['en', 'savoir', 'plus']:
                    cta = ' '.join(raw[entries[pos + j][0]] for j in range(3))
                    anchor = entries[pos][0]
                    break
            if cta and (clip.get('block') == reel.get('ctaBlock') or 'bouton' in norms or 'button' in norms):
                spot = free_spot(reel, clip, anchor, height=.14, width=.86, dur=3)
                ctas.append({'id': f"style-{clip['id']}-{anchor}", 'kind': 'cta', 'clip': clip['id'],
                    'index': anchor, 'length': len(cta.split()), 'text': cta, 'secondary': app_name(reel), 'duration': 3.0,
                    **spot, 'rotation': 0,
                    'color': (reel.get('design') or {}).get('accent', reel['style']['highlight'])})
                continue
            actions = [(k, raw[k]) for k, n in entries if action.match(n)]
            leads = [(k, raw[k]) for k, n in entries if lead.match(n)]
            if len(actions) >= 2:
                # libelles a l'infinitif (« transférez » dit -> « Transférer » ; jamais une faute recopiee de la transcription) ;
                # un parcours montre le debut et la fin du processus (deux etapes : lisible d'un coup d'oeil)
                labels = []
                for _, label in actions:
                    label = orthographe.infinitif(label, lang)
                    if label not in labels:
                        labels.append(label)
                if len(labels) > 2:
                    labels = [labels[0], labels[-1]]
                if len(labels) >= 2:
                    spot = free_spot(reel, clip, actions[0][0], height=.14, width=.9, dur=3)
                    candidates.append((4, {'id': f"style-{clip['id']}-{actions[0][0]}", 'kind': 'flow',
                        'clip': clip['id'], 'index': actions[0][0], 'length': 1, 'text': labels[0],
                        'secondary': '|'.join(labels[1:4]), 'duration': 3.0, **spot,
                        'rotation': 0, 'color': (reel.get('design') or {}).get('accent', reel['style']['highlight'])}))
                    continue
            if leads and actions:
                # un fait precis dit avec son chiffre (« un lead qui attend trois heures ») : la notification qui le dit
                # (« Lead en attente depuis 3 h ») vaut mieux qu'un tableau generique « Lead / Appelé ✓ », qui pendant un
                # probleme se lirait comme un succes
                if _notif_rule(clip, idea, lang)[1] >= 3:
                    continue
                labels = []
                for _, label in actions[:3]:
                    label = orthographe.infinitif(label, lang) if lang != 'fr' else (label[:1].upper() + label[1:])
                    if label not in labels:
                        labels.append(label)
                title = leads[0][1][:1].upper() + leads[0][1][1:]
                # Ce tableau est large : sur le côté il deviendrait illisible. On le pose sous le visage, les
                # sous-titres s'effaçant pendant ses trois secondes.
                spot = {'x': .5, 'y': .70, 'scale': .92}
                candidates.append((3, {'id': f"style-{clip['id']}-{leads[0][0]}", 'kind': 'dashboard',
                    'clip': clip['id'], 'index': leads[0][0], 'length': 1, 'text': title,
                    'secondary': '|'.join(labels), 'duration': 3.0, **spot,
                    'rotation': 0, 'color': (reel.get('design') or {}).get('accent', reel['style']['highlight'])}))
    if not ctas and use_ai and reel.get('claude'):
        # aucun « en savoir plus » reconnu par les regles : le bouton du cerveau Claude, si son texte est dit mot pour mot
        # (verifie par cerveau_claude) et apres l'accroche ; l'offre dite au-dessus, sinon la marque
        try:
            from . import cerveau_claude
            b = cerveau_claude.bouton(reel)
        except Exception as e:
            print(f'Bouton de Claude ignore ({e}).')
            b = None
        clip = next((c for c in reel['clips'] if b and c['id'] == b['clip']), None)
        if clip and times.get((clip['id'], b['index']), 0) >= hook_end:
            spot = free_spot(reel, clip, b['index'], height=.14, width=.86, dur=3)
            ctas.append({'id': f"style-{clip['id']}-{b['index']}", 'kind': 'cta', 'clip': clip['id'], 'index': b['index'],
                         'length': b['longueur'], 'text': b['texte'], 'secondary': b['secondaire'] or app_name(reel),
                         'duration': 3.0, **spot, 'rotation': 0,
                         'color': (reel.get('design') or {}).get('accent', reel['style']['highlight'])})
    # Bouton : a la premiere demande, et de nouveau a la DERNIERE (la video finit sur l'action demandee), avec au-dessus
    # l'offre reellement dite juste avant (« gratuitement ... une semaine » -> « 1 semaine gratuite ») plutot que la marque.
    if ctas:
        first, last = ctas[0], ctas[-1]
        t0 = times.get((first['clip'], first['index']), 0)
        t1 = times.get((last['clip'], last['index']), 0)
        clip = next(c for c in reel['clips'] if c['id'] == last['clip'])
        offer = offre_dite(clip, last['index'], lang) if last is not first else None
        lead = offre_debut(clip, last['index'], lang) if offer else None
        t_offre = times.get((clip['id'], lead)) if lead is not None else None
        # un bouton deja retouche ou verrouille par le monteur (autre que le bouton unique lui-meme) garde la main : le bouton
        # unique, pose au meme instant sous un autre identifiant, le cacherait a l'image (timeline.ts garde la 1re scene posee).
        # On garde alors les deux boutons d'avant (meme identifiant : le bouton protege gagne). Revue du 2 oct. 2026.
        cta_protege = any(isinstance(s, dict) and s.get('kind') == 'cta' and verrous.protege(s) and s.get('id') != f"{first['id']}-final"
                          for s in reel.get('styleScenes') or [])
        if last is not first and t1 - t0 <= CTA_UNIQUE and not cta_protege and (t_offre is None or t_offre > t0 + 0.8):
            # deux demandes proches (« appuyez sur le bouton » ... « alors appuyez sur le bouton ») : UN SEUL bouton, tenu de la
            # 1re demande jusqu'a la fin ; l'offre dite entre au-dessus quand elle est dite (champ offer). Avant : le bouton
            # sortait puis revenait 6 s plus tard, le haut de l'image restait vide entre les deux (juge n° 3 du 2 oct. 2026).
            merged = {**first, 'duration': round(t1 - t0 + 3.0, 2), 'id': f"{first['id']}-final"}
            if offer:
                merged.update({'secondary': offer, **({'offer': lead} if lead is not None else {}),
                               **({'offerClip': clip['id']} if clip['id'] != first['clip'] else {})})
            candidates.append((6, merged))
        else:
            candidates.append((5, first))
            if last is not first and t1 - t0 >= 6:
                # l'offre s'affiche quand elle est dite (badge), le bouton la rejoint sur son mot (champ lead)
                candidates.append((6, {**last, **({'secondary': offer} if offer else {}), **({'lead': lead} if lead is not None else {})}))
    # Une enumeration dite devient une liste qui se remplit au rythme de la voix (comme les pilules de la reference).
    for s in _list_scenes(reel, times, hook_end, lang):
        candidates.append((4, s))
    # Une notification fiable complète le montage quand aucun écran plus structuré n'illustre la même idée.
    for s in _notifications(reel, times, hook_end, lang, use_ai):
        candidates.append((2, s))
    # Un badge de preuve dite comble un long passage sans écran (priorité la plus basse, écart réduit : élément léger).
    for s in _claim_scenes(reel, times, hook_end, lang):
        candidates.append((1, s))
    if not candidates:
        return []
    total = max(times.values()) if times else 0
    # environ un écran toutes les 9 s (la relecture de sobriété applique ensuite le budget du style)
    budget = max(2, min(8, round(total / 9)))
    chosen = []
    for priority, scene in sorted(candidates, key=lambda x: (-x[0], times.get((x[1]['clip'], x[1]['index']), 0))):
        at = times.get((scene['clip'], scene['index']), 0)
        # le meme ecran n'est pas montre deux fois, sauf le bouton (premiere et derniere demande)
        if any(abs(at - times.get((old['clip'], old['index']), 0)) < (4.5 if scene.get('badge') else 6) or
               (old['kind'] == scene['kind'] != 'cta' and old['text'].lower() == scene['text'].lower()) for old in chosen):
            continue
        chosen.append(scene)
        if len(chosen) >= budget:
            break
    return sorted(chosen, key=lambda s: times.get((s['clip'], s['index']), 0))


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


def prepare(reel, use_ai=True, plage=None):
    """Scenes du style (reel['styleScenes']) recalculees a partir des mots. Les scenes verrouillees ou retouchees
    (verrous.protege) sont gardees telles quelles. plage=(debut, fin) : seules les scenes libres ancrees dans cette plage
    du montage sont remplacees (« Refaire ce passage ») ; les autres restent a l'identique."""
    anciennes = list(reel.get('styleScenes') or [])
    _prepare(reel, use_ai)
    nouvelles = reel.get('styleScenes') or []
    if plage is not None:
        times = _times(reel)
        dans = lambda s: plage[0] <= times.get((s.get('clip'), s.get('index')), -1) < plage[1]
        nouvelles = [s for s in nouvelles if dans(s)]
        anciennes_hors = [copy.deepcopy(s) for s in anciennes if not verrous.protege(s) and not dans(s)]
        ids = {s['id'] for s in anciennes_hors}
        nouvelles = [s for s in nouvelles if s['id'] not in ids] + anciennes_hors
    scenes = verrous.fusionner(anciennes, nouvelles)
    if scenes:
        reel['styleScenes'] = scenes
    else:
        reel.pop('styleScenes', None)


def _prepare(reel, use_ai=True):
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
    elif mode == 'produit':
        scenes = _product_scenes(reel, times, hook_end, lang, use_ai)
    last_at = -99.0
    for j, (clip, i, w) in enumerate(words if mode in ('infographie', 'comparatif', 'produit') else []):
        n = normalize(w['w']).strip(' ,.!?;:')
        kind, text, secondary, length = None, '', '', 1
        number = _number(clip['words'], i)
        at = times.get((clip['id'], i), 0)
        if mode in ('infographie', 'produit') and number:
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
        if not kind:
            continue
        # Une scène toutes les 4 s au plus, ancrée au mot : ni empilement ni effet à chaque coupe ; rien sur
        # l'accroche (sauf la comparaison, qui explique toute la phrase).
        if at < last_at + 4 or (kind == 'metric' and at < hook_end):
            continue
        last_at = at
        spot = free_spot(reel, clip, i, height=0.15) if kind == 'metric' else {'x': 0.5, 'y': 0.69, 'scale': 1}
        scenes.append({'id': f"style-{clip['id']}-{i}", 'kind': kind, 'clip': clip['id'], 'index': i,
                       'length': length, 'text': text, 'secondary': secondary, 'duration': 2.4,
                       **spot, 'rotation': 0,
                       'color': (reel.get('design') or {}).get('accent', reel['style']['highlight'])})
    if mode == 'produit':
        # Les nombres vrais et les écrans de parcours partagent le même budget visuel : un seul élément à la fois. Le plus
        # utile passe d'abord (bouton, liste, parcours, tableau, puis chiffre et notification), ensuite l'ordre du temps.
        rang = {'cta': 0, 'list': 1, 'flow': 1, 'dashboard': 2, 'metric': 3, 'notification': 3}
        spaced = []
        for scene in sorted(scenes, key=lambda s: (rang.get(s['kind'], 4), times.get((s['clip'], s['index']), 0))):
            at = times.get((scene['clip'], scene['index']), 0)
            # le bouton unique tenu jusqu'a la fin occupe toute sa duree (rien d'autre ne s'y pose)
            tenu = lambda old: old['kind'] == 'cta' and times.get((old['clip'], old['index']), 0) <= at <= times.get((old['clip'], old['index']), 0) + float(old.get('duration') or 0)
            if any(abs(at - times.get((old['clip'], old['index']), 0)) < 4 or tenu(old) for old in spaced):
                continue
            spaced.append(scene)
        scenes = sorted(spaced, key=lambda s: times.get((s['clip'], s['index']), 0))
    _aligner_pages(reel, scenes)
    from . import creative
    creative.direct_scenes(reel, scenes, times)
    if mode == 'produit':
        # notification, tableau ou chiffre d'un probleme vecu (« Lead en attente depuis 3 h ») : teinte chaude, jamais la
        # couleur d'accent du produit (une coche cyan pendant le probleme se lirait comme un succes)
        for sc in scenes:
            if sc.get('kind') in ('notification', 'dashboard', 'metric') and sc.get('creativeRole') == 'probleme' and _negatif(reel, sc):
                sc['color'] = CHAUD
    reel['styleScenes'] = scenes


# Interfaces dont le texte EST la parole (comme SAID_KINDS de timeline.ts) et mots vides / chiffres de sayTokens (timeline.ts)
_DIT = ('list', 'cta', 'flow', 'metric', 'paper')
_VIDES = set(('le la les l un une des du de d a au aux et ou en y ne n pas que qu qui ce c ca se s sa son ses ma mon mes ta ton tes '
              'nos notre vos votre leur leurs je j tu il elle on nous vous ils elles me m te t lui est sont pour par avec sans dans sur chez si '
              'the an of to and or in on at for is are it you we').split())
_NOMBRES = {'deux': '2', 'trois': '3', 'quatre': '4', 'cinq': '5', 'six': '6', 'sept': '7', 'huit': '8', 'neuf': '9', 'dix': '10', 'fois': 'x',
            'heure': 'h', 'heures': 'h', 'minute': 'min', 'minutes': 'min', 'two': '2', 'three': '3', 'five': '5', 'times': 'x'}


def _porteurs(texte):
    """Mots porteurs d'un texte (sayTokens de timeline.ts) : minuscules sans accents, pluriel simple retire, chiffres dits."""
    out = []
    for w in re.split(r'[^a-z0-9]+', normalize(str(texte or '')).replace('×', ' x ')):
        if not w:
            continue
        w = _NOMBRES.get(w, w[:-1] if len(w) > 3 and w.endswith('s') else w)
        if w not in _VIDES:
            out.append(w)
    return out


def _aligner_pages(reel, scenes):
    """Une interface qui REDIT la page de sous-titres en cours (parcours, liste, chiffre, bouton) entre avec la page : son mot
    d'ancrage devient le 1er mot de la page (au plus 0,6 s plus tot, meme plan). Sinon la page a moitie dite s'effacait juste
    avant la carte qui la redit (sous-titre eclair de 0,2 s, juge n° 3 du 2 oct. 2026). Sa fin ne bouge pas (duree allongee
    d'autant) et elle n'est jamais avancee contre la scene d'avant. Pages : celles de l'image (montage.compute -> timeline.ts) ;
    toute erreur laisse les scenes telles quelles."""
    cibles = [s for s in scenes if s.get('kind') in _DIT and not (s.get('kind') == 'cta' and isinstance(s.get('lead'), int))]
    if not cibles:
        return
    try:
        from . import montage
        pages = montage.compute(reel).get('pages') or []
    except Exception:
        return
    # temps du montage de chaque mot affiche (pages) : la scene avancee ne doit jamais tomber dans la demi-seconde qui suit la
    # fin de la scene d'avant (timeline.ts l'ecarterait alors : carte perdue), et elle garde sa fin (jamais un vide de plus avant
    # la carte suivante). Revue du 2 oct. 2026.
    debut = {(w['clip'], w['index']): float(w['start']) for p in pages for w in (p.get('words') or [])}

    def fin_avant(s, t):
        fins = [debut[(o['clip'], o['index'])] + max(.2, float(o.get('duration') or 0)) for o in scenes
                if o is not s and not o.get('hidden') and (o.get('clip'), o.get('index')) in debut and debut[(o['clip'], o['index'])] < t]
        return max(fins, default=-1e9)
    for s in cibles:
        for p in pages:
            ws = p.get('words') or []
            if not ws or not any(w['clip'] == s['clip'] and w['index'] == s['index'] for w in ws):
                continue
            a = next(w for w in ws if w['clip'] == s['clip'] and w['index'] == s['index'])
            premier = ws[0]
            if premier['clip'] != s['clip'] or premier['index'] >= s['index'] or not 0.02 < a['start'] - premier['start'] <= 0.6:
                break
            page = [t for w in ws for t in _porteurs(w['w'])]
            dit = set(t for x in [s.get('text'), *str(s.get('secondary') or '').split('|')] for t in _porteurs(x))
            hit = sum(1 for t in page if t in dit)
            if page and ((hit >= 2 and hit >= .5 * len(page)) or (hit >= 1 and hit == len(page))):
                avance = float(a['start']) - float(premier['start'])
                if float(premier['start']) >= fin_avant(s, float(a['start'])) + .5:
                    s['index'] = premier['index']
                    if s.get('duration'):
                        s['duration'] = round(float(s['duration']) + avance, 2)
            break


def sober(reel):
    """Corrige le chemin automatique complet, y compris ses propositions IA : mots en couleur revalides par la
    selection commune (un par idee, retouches a la main gardees) et graphismes generes retires."""
    from .reel import rehighlight
    rehighlight(reel)
    # Aucun effet automatique ne doit couvrir l'accroche. Les éléments posés à la main (ou verrouillés) restent intacts.
    reel['graphics'] = [g for g in reel.get('graphics', []) if not g.get('generated') or verrous.protege(g)]


def apply(reel, template):
    """Habillage d'un style : design, mots en couleur, scenes. Rien de verrouille ni de retouche n'est change."""
    with verrous.sous_protection(reel):
        _apply(reel, template)


def _apply(reel, template):
    from .reel import rehighlight
    emojis = {c['id']: copy.deepcopy(c.get('emojis', [])) for c in reel['clips']}
    manual = [copy.deepcopy(s) for s in reel.get('styleScenes', []) if verrous.protege(s)]
    old = reel.get('design') or {}
    reel['design'] = copy.deepcopy(template.get('design') or {})
    # Ressources réellement choisies par le monteur : gardées. Une ancienne vidéo générique sans photo/GLB source
    # n'est jamais réinjectée dans un nouveau montage.
    for k in ('productImage', 'productModel', 'title'):
        if k in old:
            reel['design'][k] = old[k]
    if (old.get('productImage') or old.get('productModel')) and old.get('productVideo'):
        reel['design']['productVideo'] = old['productVideo']
    if reel['design'].get('mode'):
        reel['design'].setdefault('suppressExtras', True)
        sober(reel)
    else:
        rehighlight(reel)  # meme selection au rythme des sous-titres du nouveau style
    prepare(reel)
    ids = {s['id'] for s in manual}
    reel['styleScenes'] = [s for s in reel.get('styleScenes', []) if s['id'] not in ids] + manual
    # Changer de style n'est pas un nouveau montage automatique : ces emojis peuvent etre des retouches.
    # Hormozi en genere dans prepare(), mais seul auto._finish les applique puis les relit avec tout=True.
    for c in reel['clips']:
        c['emojis'] = emojis[c['id']]
