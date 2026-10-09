"""Elements graphiques proposes par l'IA (piste Graphismes) : le monteur accepte, modifie ou refuse.

- chiffre : chaque nombre dit avec son unite (« 5 fois moins cher », « 2 400 $ », « 30 % ») ; libelle court
  seulement s'il a un sens (« MOINS CHER »), sinon le chiffre seul ; un petit nombre s'affiche directement
  (compter de 0 a 3 n'apporte rien)
- cases cochees : liste de benefices (cerveau Claude s'il a lu le montage, sinon IA locale) dits dans la video, au
  moment ou la SOLUTION est presentee (jamais pendant le probleme)
- mot geant lumineux : un mot fort APRES l'accroche (l'accroche n'a que le bandeau ; Claude, sinon IA locale, sinon le
  premier mot en couleur)
- logo anime : en fin de video si la charte du client a un logo
Chaque proposition porte une raison et une confiance (« haute » : peut etre posee seule par un style
dynamique ; sinon elle reste a valider). La relecture finale (sobriete.py) fait respecter le budget."""
import re

from . import montage
from .script import normalize

NUMBER_WORDS = {'un': 1, 'une': 1, 'deux': 2, 'trois': 3, 'quatre': 4, 'cinq': 5, 'six': 6, 'sept': 7, 'huit': 8, 'neuf': 9,
                'dix': 10, 'onze': 11, 'douze': 12, 'quinze': 15, 'vingt': 20, 'trente': 30, 'quarante': 40, 'cinquante': 50,
                'soixante': 60, 'cent': 100, 'mille': 1000}
UNITS = {'%': '%', 'pourcent': ' %', 'pour': ' %', '$': ' $', 'dollars': ' $', 'fois': '×', 'minutes': ' min', 'heures': ' h',
         'jours': ' jours', 'semaines': ' semaines', 'clients': ' clients', 'ans': ' ans', 'secondes': ' s'}
UNITS.update({'minute':' min','min':' min','heure':' h','h':' h','jour':' jour','semaine':' semaine','client':' client',
              'an':' an','seconde':' s','dollar':' $','hour':' h','hours':' h','seconds':' s','second':' s',
              'mois':' mois','day':' day','days':' days','week':' week','weeks':' weeks','month':' month','months':' months'})
COMPTE = 10  # a partir de 10, le chiffre defile depuis 0 ; en dessous il s'affiche directement


def _number(words, i):
    """Nombre dit a la position i (chiffres ou mots), avec son unite : (valeur, prefixe, suffixe, n mots) ou None."""
    raw = words[i]['w'].strip(' ,.!?;:')
    n = normalize(raw)
    digits = re.sub(r'[\s  ]', '', raw).replace(',', '.')
    m = re.match(r'^(\d+(?:\.\d+)?)(%|\$)?$', digits)
    if m:
        value, unit = float(m.group(1)), m.group(2)
    elif n in NUMBER_WORDS:
        value, unit = float(NUMBER_WORDS[n]), None
    else:
        return None
    suffix, used = (UNITS[unit] if unit else ''), 1
    if not unit and i + 1 < len(words):
        nxt = normalize(words[i + 1]['w'].strip(' ,.!?'))
        if nxt in UNITS and (nxt != 'pour' or i + 2 < len(words) and normalize(words[i + 2]['w']).startswith('cent')):
            suffix, used = UNITS[nxt], 2
            if nxt == 'pour' and i + 2 < len(words) and normalize(words[i + 2]['w']).startswith('cent'):
                used = 3
    if value < 10 and not suffix:  # « 2 taches » n'est pas un chiffre a mettre en avant ; « 5 fois », « 3 % » oui
        return None
    prefix = ''
    if suffix == '×':
        suffix, prefix = '', '×'
    return value, prefix, suffix, used


def _clean(raw):
    return raw.strip(' ,.!?;:«»"()')


def _label(words, j):
    """Libelle court apres le chiffre, seulement s'il a un sens seul : « (5 fois) MOINS CHER », « PLUS RAPIDE »,
    « PLUS DE CLIENTS ». Jamais une suite de mots coupee (« a deja ete », « moins cher qu'un ») : sinon ''."""
    from .reel import STOP
    if j >= len(words) or normalize(_clean(words[j]['w'])) not in ('plus', 'moins'):
        return ''
    out = [_clean(words[j]['w'])]
    for k in range(j + 1, min(len(words), j + 4)):
        raw = words[k]['w']
        tok = normalize(_clean(raw))
        if not tok or tok.startswith("qu") or "'" in tok:
            break
        if tok in ('de', 'd') and len(out) == 1:
            out.append(_clean(raw))
            if re.search(r'[,.!?;:]$', raw.strip()):
                break
            continue
        if tok in STOP or len(tok) < 3:
            break
        out.append(_clean(raw))
        break
    if len(out) < 2 or normalize(out[-1]) in ('de', 'd'):
        return ''
    return ' '.join(out).upper()


def suggest(project_dir, rid):
    from .sobriete import reperes
    reel = montage.load(project_dir, rid)
    seg = montage.compute(reel)
    words = seg['words']
    total = seg['duration']
    rep = reperes(reel, seg)
    hook, cta = rep['accroche'], rep['cta'] if rep['cta'] is not None else total
    out = []

    def add(kind, at, duration, confiance, raison, **props):
        at = max(0.0, min(at, total - duration))
        if any(abs(g['at'] - at) < 2.5 for g in out):
            return
        out.append({'id': f'g{len(out) + 1}-{kind}', 'kind': kind, 'at': round(at, 2), 'duration': duration, 'props': props,
                    'suggested': True, 'confiance': confiance, 'raison': raison})

    for i in range(len(words)):
        num = _number(words, i)
        if not num or words[i]['start'] < hook:  # rien d'autre que le bandeau pendant l'accroche
            continue
        value, prefix, suffix, used = num
        if value < 2 and suffix.strip() not in ('%', '$'):  # « une semaine » : un compteur « 1 » n'apporte rien
            continue
        label = _label(words, i + used)
        said = ' '.join(_clean(w['w']) for w in words[i:i + used])
        # sur : un multiplicateur avec son libelle (« ×5 MOINS CHER »), un pourcentage ou un montant
        sure = (prefix == '×' and bool(label)) or suffix.strip() in ('%', '$')
        add('chiffre', words[i]['start'] - 0.1, 2.2, 'haute' if sure else 'moyenne', f'chiffre dit : « {said} »',
            value=int(value) if value.is_integer() else value, prefix=prefix, suffix=suffix, label=label,
            count=value >= COMPTE, **{'from': 0})
    ai = None
    if reel.get('claude') and words:
        # cerveau Claude (resultat garde dans le reel, aucun appel ici) : ses cartes « liste » et « mot » d'abord ;
        # sans resultat utilisable, l'IA locale comme avant
        try:
            from . import cerveau_claude
            ai = cerveau_claude.pour_graphismes(reel, words)
        except Exception as e:
            print(f'Cartes de Claude ignorees ({e}).')
            ai = None
    if ai is None:
        ai = _ai(words, hook) if words else {}
    start = rep['solution'] if rep['solution'] is not None else total * 0.55
    if ai.get('benefices'):
        # benefices vraiment dits apres le debut de la solution (au moins un mot fort de chacun)
        later = [w for w in words if w['start'] >= start - 0.3]
        # un chiffre deja affiche (« ×5 MOINS CHER ») n'est pas repete dans la liste
        shown = {float(g['props']['value']) for g in out if g['kind'] == 'chiffre'}
        items = [b for b in ai['benefices'] if _anchored(later, b) and not (_values(b) & shown)]
        if len(items) >= 2:
            claude_at = ai.get('benefices_at')
            at = (claude_at if isinstance(claude_at, (int, float)) and start - 0.3 <= claude_at <= cta else
                  _locate(words, ai.get('benefices_debut') or '', after=start - 0.3, before=cta)) or start
            duration = min(4.5, 1.2 + 0.8 * len(items[:4]))
            if at + duration <= total:
                title = str(ai.get('benefices_titre') or '').strip()
                title = title if title and _anchored(words, title, every=True) else ''
                add('coches', at, duration, 'haute' if len(items) >= 3 and rep['solution'] is not None else 'moyenne',
                    'bénéfices dits quand la solution est présentée', items=items[:4], title=title)
    choc = ai.get('mot_choc')
    choc_at = ai.get('mot_choc_at')  # cerveau Claude : instant du mot dans le montage (verifie)
    if choc and isinstance(choc_at, (int, float)):
        at = choc_at if hook + 0.5 < choc_at < cta else None
    else:
        at = _locate(words, choc, after=hook + 0.5, before=cta) if choc else None
    if at is None:
        # premier mot en couleur apres l'accroche, qui porte une idee (pas un nom de marque ni un petit mot)
        from .reel import STOP, WEAK
        from .sobriete import nom_propre
        first = next((w for k, w in enumerate(words) if w.get('hl') and hook + 0.5 < w['start'] < min(cta, 25)
                      and len(normalize(_clean(w['w']))) >= 5 and normalize(_clean(w['w'])) not in STOP | WEAK
                      and not nom_propre(words, k)), None)
        choc, at = (_clean(first['w']), first['start']) if first else (None, None)
    if choc and at is not None:
        add('motgeant', at - 0.05, 0.9, 'moyenne', f'mot fort : « {choc} »', text=str(choc).upper())
    if (reel.get('brand') or {}).get('logo') and not (reel['brand'].get('outro') or {}).get('enabled'):
        add('logo', total - 2.0, 2.0, 'haute', 'logo du client à la fin')
    return sorted(out, key=lambda g: g['at'])


def _values(text):
    """Nombres ecrits dans un texte court (« 5 fois moins cher », « cinq fois ») : {5.0}."""
    out = set()
    for t in re.split(r"[\s'’-]+", str(text)):
        n = normalize(t)
        if re.fullmatch(r'\d+(\.\d+)?', n):
            out.add(float(n))
        elif n in NUMBER_WORDS and n not in ('un', 'une'):
            out.add(float(NUMBER_WORDS[n]))
    return out


def _anchored(words, text, every=False):
    """Le texte est-il dit ? Au moins un de ses mots forts (tous si every) se retrouve dans les mots (meme racine)."""
    from .reel import STOP
    toks = [t for t in (normalize(x).strip("'") for x in re.split(r"[\s'’-]+", str(text))) if len(t) >= 4 and t not in STOP]
    if not toks:
        return False
    said = {normalize(_clean(w['w'])).split("'")[-1] for w in words}
    hits = [t for t in toks if t in said or any(len(s) >= 5 and s[:5] == t[:5] for s in said)]
    return len(hits) == len(toks) if every else bool(hits)


def _locate(words, text, after=0.0, before=1e9):
    """Instant ou le texte est dit : fenetre de 8 mots qui contient le plus de ses mots (au moins la moitie)."""
    from .reel import STOP
    toks = {normalize(t).strip("'") for t in str(text).split()} - STOP
    toks = {t for t in toks if len(t) > 1}
    if not toks:
        return None
    norm = [normalize(w['w'].strip(' ,.!?;:')).strip("'") for w in words]
    best, best_hits = None, 0
    for i, w in enumerate(words):
        if not after <= w['start'] <= before or norm[i] not in toks:
            continue
        hits = len(toks & set(norm[i:i + 8]))
        if hits > best_hits:
            best, best_hits = w['start'], hits
    return best if best_hits == len(toks) else None


def _ai(words, hook=0.0):
    """Benefices et mot choc par l'IA locale ; {} si indisponible."""
    from . import llm
    if not llm.available():
        return {}
    text = ' '.join(w['w'] for w in words)
    after = ' '.join(w['w'] for w in words if w['start'] >= hook)
    try:
        with llm.session():
            data = llm.ask_json(llm.EDITOR,
                                f'Transcription d\'une publicite : {text}\n\n'
                                f'La meme, sans l\'accroche (premiere phrase) : {after[:1500]}\n\nReponds avec ce JSON : '
                                '{"benefices": ["3 ou 4 benefices tres courts (2 a 4 mots), avec les MOTS du texte"], '
                                '"benefices_titre": "titre de 2 ou 3 mots pour la liste", '
                                '"benefices_debut": "le mot exact du texte ou commence la partie qui presente la solution et ses benefices", '
                                '"mot_choc": "UN seul mot exact du texte SANS l\'accroche, le plus fort, a afficher en geant"}. '
                                'Si le texte ne liste aucun benefice, "benefices": [].', temperature=0.1)
        items = [str(x).strip() for x in data.get('benefices') or [] if str(x).strip()]
        return {**data, 'benefices': items[:4] if len(items) >= 2 else []}
    except Exception:
        return {}
