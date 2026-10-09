"""Relecture finale du monteur (« sobriete ») : chaque effet a une raison, un seul element a la fois.

Appelee a la fin du montage automatique (auto._finish) et, apres, a chaque application d'un style. Regles :
- pendant l'accroche (la premiere phrase), rien d'autre que le bandeau ;
- un seul element par-dessus l'image a la fois (plan de coupe, graphisme, mot geant, emoji, scene du style) ;
- un ecart minimum entre deux elements (4 s par defaut) et un nombre maximum par minute (budget du style) ;
- pas de plan de coupe, de mot geant ni d'emoji sur la derniere phrase de l'appel a l'action ;
- la liste des benefices arrive quand la solution est presentee, jamais pendant le probleme ;
- un element sans raison (mot absent, texte vide, chiffre sans valeur, source manquante) est retire ;
- tout reste dans la duree de la video (et avant la carte de fin de la charte).
Rien n'est perdu : un graphisme retire redevient une proposition (onglet Graphismes), un plan de coupe va dans
les propositions (suggestions.broll), une scene du style est masquee (reactivable), un emoji retourne dans les
propositions de l'onglet Texte. Les elements poses a la main ne sont jamais touches (sauf tout=True : reel qui
vient d'etre monte automatiquement, ou tout est automatique)."""
import math
import re

from .script import normalize

# budget par defaut ; un style peut le preciser dans son champ facultatif « budget »
DEFAUT = {'simultanes': 1, 'ecart': 4.0, 'par_minute': 4, 'plans_de_coupe_ecart': 12.0, 'accroche_max': 6.0}
LIMITES = {'simultanes': (1, 3), 'ecart': (0.0, 20.0), 'par_minute': (0, 30), 'plans_de_coupe_ecart': (0.0, 60.0),
           'accroche_max': (2.0, 10.0)}
DECALAGE = 1.5   # un element libre (graphisme, plan de coupe) peut etre decale d'au plus 1,5 s apres son mot
MIN_DUREE = 0.6  # en dessous, un element coupe par la fin de la video n'a plus de sens
# plus la raison est forte, plus l'element est prioritaire
PRIORITE = {'logo': 90, 'chiffre': 80, 'coches': 75, 'carte': 70, 'scene': 60, 'motgeant': 50, 'broll': 40, 'emoji': 30}
NOMS = {'chiffre': 'Chiffre', 'coches': 'Liste de bénéfices', 'carte': 'Carte', 'motgeant': 'Mot géant', 'logo': 'Logo',
        'broll': 'Plan de coupe', 'emoji': 'Emoji', 'scene': 'Élément du style'}
CTA_MOTS = re.compile(r"\b(bouton|cliqu\w*|appuy\w*|lien|r[ée]serv\w*|abonn\w*|contact\w*|inscri\w*|t[ée]l[ée]charg\w*|"
                      r"[ée]cri(vez|s)[- ]nous|appelez|savoir plus|click|tap|book|subscribe|sign up|link)\b", re.I)
# debut de la partie « solution » d'une pub (apres le probleme)
SOLUTION = re.compile(r"\b(c'?est pour (ca|cela)|c'?est pourquoi|c'?est la qu|voici|la solution|grace a|"
                      r"chez (?!vous|toi|nous|moi|eux|lui|soi)[a-z0-9]+|avec (nous|notre|nos)|"
                      r"notre (service|solution|equipe|offre|methode)|"
                      r"on (vous )?(place|propose|offre|aide|s'occupe)|that'?s why|here'?s how|the solution|with our)\b")
FIN_PHRASE = re.compile(r'[.!?…]["»”)\]]*$')


def budget(template=None):
    """Budget d'effets du style (champ facultatif « budget »), borne a des valeurs raisonnables."""
    out = dict(DEFAUT)
    raw = (template or {}).get('budget') if isinstance(template, dict) else None
    for k, v in (raw or {}).items():
        if k in LIMITES and isinstance(v, (int, float)) and not isinstance(v, bool):
            lo, hi = LIMITES[k]
            out[k] = type(DEFAUT[k])(min(hi, max(lo, v)))
    return out


def _template(reel, template):
    if isinstance(template, dict):
        return template
    tid = template or reel.get('template')
    try:
        from .reel import list_templates
        return next((t for t in list_templates() if t['id'] == tid), {}) or {}
    except Exception:
        return {}


def phrases(words):
    """Phrases dites dans le montage : [(debut, fin, [mots])] (ponctuation ou pause de plus de 0,7 s)."""
    out, cur = [], []
    for k, w in enumerate(words):
        cur.append(w)
        nxt = words[k + 1] if k + 1 < len(words) else None
        if nxt is None or FIN_PHRASE.search(w['w'].strip()) or nxt['start'] - w['end'] > 0.7:
            out.append((cur[0]['start'], cur[-1]['end'], cur))
            cur = []
    return out


def nom_propre(words, k):
    """Nom propre ou marque (« RyuCalls », « Rio Cause » au milieu d'une phrase) : on n'illustre jamais un nom."""
    raw = words[k]['w'].strip(' ,.!?;:«»"()')
    if len(raw) < 2 or not raw[:1].isalpha():
        return False
    if any(c.isupper() for c in raw[1:]) and not raw.isupper():  # RyuCalls, iPhone
        return True
    if raw[0].isupper() and not raw.isupper() and k > 0:
        prev = words[k - 1]['w'].strip()
        return not FIN_PHRASE.search(prev) and not prev.endswith(':')
    return False


def reperes(reel, seg, b=None):
    """Temps cles du montage : fin de l'accroche, debut de la solution, debut de la derniere phrase d'appel a
    l'action, fin utile (avant la carte de fin de la charte)."""
    b = b or DEFAUT
    total = float(seg['duration'])
    words = [w for w in seg['words'] if w['w'].strip()]
    ph = phrases(words)
    # accroche : la premiere phrase (au moins 2,5 s, au plus accroche_max)
    hook = 0.0
    for s in ph:
        hook = s[1]
        if hook >= 2.5:
            break
    hook = max(min(3.0, total), min(hook, b['accroche_max'], total))
    # appel a l'action : derniere phrase qui demande une action (bouton, lien...), sinon derniere phrase du bloc CTA
    cta = None
    for s in reversed(ph):
        if CTA_MOTS.search(' '.join(w['w'] for w in s[2])):
            cta = s[0]
            break
    if cta is None and reel.get('ctaBlock'):
        block = {c['id']: c.get('block') for c in reel.get('clips', [])}
        mine = [s for s in ph if any(block.get(w['clip']) == reel['ctaBlock'] for w in s[2])]
        cta = mine[-1][0] if mine else None
    if cta is not None and cta < hook:
        cta = None
    # solution : premiere formule « c'est pour ca que chez... », « voici », « notre service »... apres l'accroche
    solution = None
    norm = [normalize(w['w'].strip(' ,.!?;:«»"')).strip("'") for w in words]
    for k, w in enumerate(words):
        if w['start'] < hook or not norm[k]:
            continue
        if SOLUTION.match(' '.join(x for x in norm[k:k + 6] if x)):
            solution = w['start']
            break
    if solution is None:  # sinon : premiere fois qu'un nom de marque est dit apres l'accroche
        solution = next((w['start'] for k, w in enumerate(words) if w['start'] >= hook and nom_propre(words, k)), None)
    outro = (reel.get('brand') or {}).get('outro') or {}
    fin = total - float(outro.get('duration') or 0) if outro.get('enabled') else total
    return {'duree': total, 'accroche': round(hook, 2), 'solution': solution, 'cta': cta, 'fin': max(0.0, fin)}


def _t(x):
    return f'{x:.1f}'.replace('.', ',') + ' s'


def _elements(reel, seg):
    """Elements visibles par-dessus l'image, comme dans Reel.tsx (les styles de la galerie masquent plans de coupe
    et graphismes, sauf suppressExtras false)."""
    design = reel.get('design') or {}
    mode = design.get('mode') if design.get('enabled') is not False else None
    extras = not mode or design.get('suppressExtras') is False
    words = {(w['clip'], w['index']): w for w in seg['words']}
    out = []
    if extras:
        for b in reel.get('broll') or []:
            out.append({'type': 'broll', 'kind': 'broll', 'obj': b, 'at': float(b.get('at') or 0),
                        'duree': float(b.get('duration') or 0), 'libre': True, 'auto': bool(b.get('auto')),
                        'texte': b.get('word') or ''})
        for g in reel.get('graphics') or []:
            if g.get('suggested'):
                continue
            p = g.get('props') or {}
            out.append({'type': 'graphic', 'kind': g.get('kind'), 'obj': g, 'at': float(g.get('at') or 0),
                        'duree': float(g.get('duration') or 0), 'libre': True,
                        'auto': bool(g.get('auto') or g.get('generated')),
                        'texte': str(p.get('title') or p.get('text') or p.get('label') or
                                     (f"{p.get('prefix') or ''}{p.get('value')}{p.get('suffix') or ''}" if 'value' in p else ''))})
    if (reel.get('emoji') or {}).get('enabled'):
        for c in reel.get('clips') or []:
            for pair in c.get('emojis') or []:
                w = words.get((c['id'], pair[0]))
                out.append({'type': 'emoji', 'kind': 'emoji', 'obj': pair, 'clip': c, 'at': w['start'] if w else -1,
                            'duree': 1.3, 'libre': False, 'auto': bool(reel.get('aiMode', 'auto') == 'auto'),
                            'texte': str(pair[1]), 'mot': w})
    # scenes du style (notification, chiffre, papier...) ; dans l'Editorial, les mots-cles SONT les sous-titres
    if mode and mode != 'editorial':
        for s in reel.get('styleScenes') or []:
            if s.get('hidden'):
                continue
            w = words.get((s.get('clip'), s.get('index')))
            out.append({'type': 'scene', 'kind': 'scene', 'obj': s, 'at': w['start'] if w else -1,
                        'duree': float(s.get('duration') or 2.4), 'libre': False, 'auto': True,
                        'texte': str(s.get('text') or ''), 'mot': w})
    for e in out:
        e['fin'] = e['at'] + e['duree']
        e['prio'] = PRIORITE.get(e['kind'] if e['type'] == 'graphic' else e['type'], 20)
    return out


def _petit_mot(reel, words, o):
    """Plan de coupe pose sur un mot qui n'est pas une idee : petit mot, chiffre, adverbe, nom de marque."""
    from .reel import NUMBERS, STOP, WEAK, _brands
    raw = str(o.get('word') or '').strip(' ,.!?;:«»"')
    n = normalize(raw).strip("'").split("'")[-1]
    if not n:
        return None
    if n in STOP or n in WEAK or n in NUMBERS or len(n) < 4 or n.endswith('ment'):
        return f'« {raw} » n\'est pas une chose à montrer (petit mot, chiffre ou adverbe)'
    brands = {normalize(b).strip("'") for b in _brands(reel)}
    near = [k for k, w in enumerate(words) if abs(w['start'] - float(o.get('at') or 0)) < 2.5
            and normalize(w['w'].strip(' ,.!?;:«»"')).strip("'").split("'")[-1] == n]
    if n in brands or any(nom_propre(words, k) for k in near):
        return f'« {raw} » est un nom (marque) : une image au hasard ne l\'illustre pas'
    return None


def _raison_manquante(reel, e, words=()):
    """Pourquoi l'element n'a pas de raison d'etre (None s'il en a une)."""
    o = e['obj']
    if e['type'] == 'broll':
        if o.get('source') not in (reel.get('sources') or {}):
            return 'sa vidéo est introuvable'
        if not str(o.get('word') or o.get('reason') or '').strip():
            return "il n'illustre aucun mot"
        return _petit_mot(reel, words, o)
    elif e['type'] == 'graphic':
        p = o.get('props') or {}
        k = o.get('kind')
        if k == 'chiffre' and not (isinstance(p.get('value'), (int, float)) and p['value'] > 0):
            return 'le chiffre est vide'
        if k == 'coches' and len([x for x in p.get('items') or [] if str(x).strip()]) < 2:
            return 'la liste a moins de deux bénéfices'
        if k == 'motgeant' and not str(p.get('text') or '').strip():
            return 'le mot est vide'
        if k == 'logo' and not (reel.get('brand') or {}).get('logo') and not p.get('file'):
            return "il n'y a pas de logo"
    elif e['type'] in ('emoji', 'scene'):
        if e.get('mot') is None:
            return 'son mot a été coupé'
        if e['type'] == 'scene' and o.get('kind') not in ('product', 'comparison') and not str(o.get('text') or '').strip():
            return 'son texte est vide'
    return None


def _libelle(e, report):
    """Chiffre : un libelle coupe (« A DEJA ETE », « MOINS CHER QU'UN ») est retire, le chiffre seul reste ; un petit
    nombre s'affiche directement (compter de 0 a 3 n'apporte rien)."""
    from .reel import STOP
    p = e['obj'].setdefault('props', {})
    value = p.get('value')
    if 'count' not in p and isinstance(value, (int, float)):
        p['count'] = value >= 10
    label = str(p.get('label') or '').strip()
    if not label:
        return
    toks = [normalize(t) for t in label.split()]
    last = toks[-1] if toks else ''
    if not last or "'" in last or last in STOP or len(last) < 3 or toks[0] not in ('plus', 'moins'):
        p['label'] = ''
        e['texte'] = f"{p.get('prefix') or ''}{value}{p.get('suffix') or ''}"
        report['corriges'].append(f'Chiffre {e["texte"]} : libellé « {label} » retiré (phrase coupée, sans sens seule).')


def _retirer(reel, e, raison, report):
    """Retire un element sans le perdre : il redevient une proposition (ou est masque)."""
    o = e['obj']
    nom = NOMS.get(e['kind'] if e['type'] == 'graphic' else e['type'], 'Élément')
    detail = f' « {e["texte"]} »' if e.get('texte') else ''
    if e['type'] == 'graphic':
        o['suggested'] = True
        o.pop('auto', None)
        o['sobriete'] = raison
        garde = 'gardé en proposition (onglet Graphismes)'
    elif e['type'] == 'broll':
        reel['broll'] = [b for b in reel.get('broll') or [] if b is not o]
        sug = reel.setdefault('suggestions', {}).setdefault('broll', [])
        if not any(abs(float(x.get('at', -99)) - e['at']) < 0.5 and x.get('source') == o.get('source') for x in sug):
            sug.append({**{k: v for k, v in o.items() if k != 'auto'}, 'raison': raison})
        garde = 'gardé en proposition'
    elif e['type'] == 'scene':
        o['hidden'] = True
        o['sobriete'] = raison
        garde = 'masqué (réactivable dans Habillage du style)'
    else:  # emoji -> propositions de l'onglet Texte
        c = e['clip']
        c['emojis'] = [p for p in c.get('emojis') or [] if p is not o]
        sug = reel.setdefault('suggestions', {}).setdefault('emojis', {}).setdefault(c['id'], [])
        if list(o) not in [list(x) for x in sug]:
            sug.append(list(o))
        garde = 'gardé en proposition (onglet Texte)'
    where = f' à {_t(e["at"])}' if e['at'] >= 0 else ''
    report['retires'].append(f'{nom}{detail}{where} retiré : {raison} ; {garde}.')


def _deplacer(e, at, raison, report):
    old = e['at']
    e['at'], e['fin'] = round(at, 2), round(at + e['duree'], 2)
    e['obj']['at'] = e['at']
    nom = NOMS.get(e['kind'] if e['type'] == 'graphic' else e['type'], 'Élément')
    detail = f' « {e["texte"]} »' if e.get('texte') else ''
    report['deplaces'].append(f'{nom}{detail} déplacé de {_t(old)} à {_t(e["at"])} : {raison}.')


def relire(reel, template=None, seg=None, tout=False):
    """Relecture du monteur sur un reel (modifie sur place). template : style (dict ou id ; par defaut celui du reel).
    tout=True : tous les elements sont automatiques (reel qui vient d'etre monte). Renvoie le rapport en francais :
    {'retires': [...], 'deplaces': [...], 'corriges': [...], 'gardes': n, 'resume': str, 'budget': {...}, 'reperes': {...}}."""
    from . import montage
    tpl = _template(reel, template)
    b = budget(tpl)
    seg = seg or montage.compute(reel)
    rep = reperes(reel, seg, b)
    report = {'retires': [], 'deplaces': [], 'corriges': [], 'gardes': 0, 'budget': b, 'reperes': rep}
    els = _elements(reel, seg)
    fixed = []  # bandeau (et titre 3D) : l'element de l'accroche, jamais retire ici
    banner = reel.get('banner') or {}
    if tout and banner.get('enabled') and str(banner.get('text') or '').strip().endswith(('…', '...')):
        # montage automatique : la premiere phrase recopiee et coupee n'est pas un titre
        report['retires'].append(f"Bandeau « {banner['text']} » retiré : c'est la première phrase recopiée et coupée.")
        reel['banner'] = banner = {**banner, 'enabled': False, 'text': ''}
    if banner.get('enabled') and str(banner.get('text') or '').strip():
        start = float(banner.get('start') or 0)
        end = float(banner['end']) if banner.get('end') is not None else rep['duree']
        fixed.append({'at': start, 'fin': min(end, rep['duree'])})
    intro = reel.get('intro') or {}
    if intro.get('enabled') and intro.get('file'):
        fixed.append({'at': 0.0, 'fin': float(intro.get('duration') or 2.5)})

    def removable(e):
        return tout or e['auto']

    kept = []
    for e in els:
        if not removable(e):
            kept.append(e)  # pose a la main : on ne touche a rien, mais il compte pour les chevauchements
            continue
        why = _raison_manquante(reel, e, seg['words'])
        if why:
            _retirer(reel, e, why, report)
            continue
        if e['type'] == 'graphic' and e['kind'] == 'chiffre':
            _libelle(e, report)
        # dans la duree de la video (et avant la carte de fin)
        if e['libre'] and e['fin'] > rep['fin']:
            if rep['fin'] - e['at'] >= MIN_DUREE and e['kind'] != 'coches':
                e['duree'] = round(rep['fin'] - e['at'], 2)
                e['fin'] = rep['fin']
                e['obj']['duration'] = e['duree']
                report['deplaces'].append(f"{NOMS.get(e['kind'], 'Élément')} raccourci pour finir avec la vidéo.")
            elif rep['fin'] - e['duree'] > rep['accroche']:
                _deplacer(e, rep['fin'] - e['duree'], 'il dépassait la fin de la vidéo', report)
            else:
                _retirer(reel, e, 'il dépasse la fin de la vidéo', report)
                continue
        elif e['fin'] > rep['fin'] + 0.05 and e['at'] >= rep['fin'] - MIN_DUREE:
            _retirer(reel, e, 'il tombe sur la carte de fin', report)
            continue
        # rien d'autre que le bandeau pendant l'accroche
        if e['at'] < rep['accroche']:
            if e['libre'] and rep['accroche'] - e['at'] <= DECALAGE and e['kind'] not in ('broll', 'motgeant'):
                _deplacer(e, rep['accroche'] + 0.05, "rien d'autre que le bandeau pendant l'accroche", report)
            else:
                _retirer(reel, e, "rien d'autre que le bandeau pendant l'accroche", report)
                continue
        # la derniere phrase de l'appel a l'action reste nette
        if rep['cta'] is not None and e['kind'] in ('broll', 'motgeant', 'emoji', 'scene') and e['fin'] > rep['cta'] + 0.2:
            _retirer(reel, e, "la dernière phrase de l'appel à l'action reste nette", report)
            continue
        # la liste des benefices arrive avec la solution, pas pendant le probleme
        if e['kind'] == 'coches':
            debut = rep['solution'] if rep['solution'] is not None else rep['duree'] * 0.55
            if e['at'] < debut - 0.3:
                if debut + e['duree'] <= rep['fin']:
                    _deplacer(e, debut, 'la liste arrive quand la solution est présentée', report)
                else:
                    _retirer(reel, e, 'la liste arrivait pendant le problème', report)
                    continue
        kept.append(e)

    # un seul element a la fois, un ecart minimum, un budget par minute ; priorite a la raison la plus forte
    ecart, maxi = b['ecart'], b['simultanes']
    quota = max(1, math.ceil(b['par_minute'] * rep['duree'] / 60)) if b['par_minute'] else 0
    accepted = [dict(f, fixe=True) for f in fixed]
    counted = 0

    def conflict(at, fin, e):
        over = [a for a in accepted if at < a['fin'] and a['at'] < fin]
        if len(over) >= maxi:
            return True
        near = [a for a in accepted if a not in over and max(at - a['fin'], a['at'] - fin) < ecart]
        if near:
            return True
        # plans de coupe : un seul toutes les ~12 s
        if e['kind'] == 'broll' and any(a.get('kind') == 'broll' and abs(a['at'] - at) < b['plans_de_coupe_ecart'] for a in accepted):
            return True
        return False

    order = sorted(kept, key=lambda e: (removable(e), -e['prio'], e['at']))
    for e in order:
        if not removable(e):
            accepted.append(e)
            if e['kind'] not in ('logo',):
                counted += 1
            continue
        if e['kind'] != 'logo' and quota and counted >= quota:
            _retirer(reel, e, f"le style prévoit au plus {b['par_minute']} éléments par minute", report)
            continue
        if not quota and e['kind'] != 'logo':
            _retirer(reel, e, 'ce style ne prévoit aucun élément par-dessus l\'image', report)
            continue
        if not conflict(e['at'], e['fin'], e):
            accepted.append(e)
            counted += e['kind'] != 'logo'
            continue
        moved = False
        if e['libre']:
            step = 0.25
            while step <= DECALAGE + 1e-6:
                at = e['at'] + step
                if at + e['duree'] <= rep['fin'] and not conflict(at, at + e['duree'], e) and not (
                        rep['cta'] is not None and e['kind'] in ('broll', 'motgeant') and at + e['duree'] > rep['cta'] + 0.2):
                    _deplacer(e, at, f'un seul élément à la fois, {ecart:g} s entre deux', report)
                    accepted.append(e)
                    counted += e['kind'] != 'logo'
                    moved = True
                    break
                step += 0.25
        if not moved:
            _retirer(reel, e, f'un seul élément à la fois, {ecart:g} s entre deux', report)
    report['gardes'] = len([a for a in accepted if not a.get('fixe')])
    if reel.get('broll'):
        reel['broll'] = sorted(reel['broll'], key=lambda x: x.get('at', 0))
    if reel.get('graphics'):
        reel['graphics'] = sorted(reel['graphics'], key=lambda x: x.get('at', 0))
    s = lambda n: 's' if n > 1 else ''
    n_r, n_d, n_c, n_g = len(report['retires']), len(report['deplaces']), len(report['corriges']), report['gardes']
    parts = [f'{n_r} élément{s(n_r)} retiré{s(n_r)}' if n_r else '', f'{n_d} déplacé{s(n_d)}' if n_d else '',
             f'{n_c} corrigé{s(n_c)}' if n_c else '']
    report['resume'] = ('Relecture : rien à changer.' if not (n_r or n_d or n_c) else
                        'Relecture : ' + ', '.join(x for x in parts if x)
                        + f' ; {n_g} gardé{s(n_g)} (un seul à la fois, rien sur l\'accroche sauf le bandeau).')
    return report
