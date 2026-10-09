"""Document de style d'un reel (reels/<id>.json) : sous-titres, mots cles, zooms, bandeau...

Le montage (prises, coupes) reste dans project.json, partage par tous les reels du projet.
Le style est propre a chaque reel. Les retouches faites dans l'interface sont conservees
tant que le plan concerne ne change pas (meme prise, memes points de coupe)."""
import json
import re
import statistics
from pathlib import Path

from . import analyze, media, render
from .media import ROOT
from .script import normalize

# Mots outils (articles, pronoms, prepositions, auxiliaires...) : jamais en couleur. STOP (francais + anglais) sert
# aussi a la recherche, aux plans de coupe et aux bandeaux : n'y mettre que des mots sans contenu.
STOP_FR = set('''a au aux avec ca ce ces cet cette c d de des du elle elles en est et etre eux il ils je j l la le les leur
leurs lui m ma mais me meme memes mes moi mon n ne nos notre nous on ou par pas pour qu que qui s sa se ses son sur t ta te
tes toi ton tu un une vos votre vous y si plus tres bien fait faire dans comme tout tous toute toutes sans avoir
ete sont va vont peu puis pis ici alors donc parce aussi deja encore juste chaque quoi dont ont avez etes
quelqu'un quelque quelques chose cela ceci celui celle ceux celles lequel laquelle lesquels lesquelles car ni quand
lorsque puisque ainsi voici voila chez entre vers depuis pendant avant apres selon sous contre suis es sommes etait
etaient etais sera seront serait seraient soit soient ai as avons aura auront aurait auraient ait aie ayez eu vais vas
allons allez aller allait fais faisons faites font faisait fera ferait peux peut pouvons pouvez peuvent pouvait
pourrait pourrez puisse puissiez puissent veux veut voulons voulez veulent voulait voudrait dois doit devons devez
doivent devait devrait faut fallait faudrait estce questce toimeme moimeme vousmeme nousmeme luimeme ellememe
peutetre cestadire atil yatil euh heu ben bah hein ouais tse'''.split())
STOP_EN = set('''the a an and or but so of to in on at by for with from as is are was were be been being am i me my mine
myself we us our ours you your yours yourself he him his she her hers it its itself they them their theirs this that
these those what who whom whose which how why when where do does did done doing not no yes yeah yep have has had having
can could will would shall should may might must just there here now then than very really like get got gets getting
go goes going went gone gonna wanna gotta um uh oh ok okay if because while into onto about over under up down out off
too also even still all any some each every other another such own most much many let lets'''.split())
STOP = STOP_FR | STOP_EN
# Mots trop vagues pour etre mis en valeur seuls (verbes passe-partout, mots de remplissage)
WEAK = set('''chose choses gens truc trucs fois moment moments facon maniere cote niveau part type monde personne dire
dit dis disent disait voir vois voit voyez vu savoir sais sait savez savons mettre met mets mis prendre prend prends
pris venir vient viens viennent parler parle oui non merci bon bonne vrai vraie vraiment petit petite petits grand
grande soins cas combien moins mieux beaucoup assez trop rien aucun aucune autre autres certain certains plusieurs
tant tellement surtout seulement exemple genre ok okay bientot repondre question questions fortes commencer
thing things stuff way lot lots kind sort guy guys make makes made take takes took put puts say says said tell tells
told telling know knows knew think thinks thought want wants wanted need needs see sees saw look looks come comes came
give gives gave keep try well right only sure maybe actually basically literally probably pretty almost enough please
more less something someone anything anyone everything everyone nothing nobody one fine hey'''.split())
NUMBERS = set('''deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize vingt trente
quarante cinquante soixante septante huitante nonante cent cents mille million millions milliard milliards moitie
double triple two three four five six seven eight nine ten eleven twelve thirteen fifteen twenty thirty forty fifty
sixty seventy eighty ninety hundred hundreds thousand thousands billion half'''.split())
# unites de temps : « trois heures », « une semaine »
TIME = set('''seconde secondes minute minutes heure heures jour jours semaine semaines mois an ans annee annees
second seconds hour hours day days week weeks month months year years'''.split())
# un nom suit souvent un determinant (« un petit pourcentage », « your money »)
DETERMINERS = set('''le la les l un une des du au aux mon ton son ma ta sa mes tes ses nos vos notre votre leur leurs ce cet
cette ces chaque aucun the a an my your his her our their this that these those every no'''.split())
ADJ_BEFORE = set('petit petite petits vrai vraie bon bonne grand grande gros grosse nouveau nouvelle meilleur big small real good new'.split())
UNITS = TIME | set('fois pourcent pourcents dollars dollar piasses euros euro times percent bucks x k'.split())
# benefice, douleur, argent, urgence, resultat
STRONG = set('''gratuit gratuite gratuits gratuites gratuitement garanti garantie garantis garantit garantir garanties
rapide rapides rapidement vite immediatement instantanement concurrent concurrents concurrence client clients argent
salaire salaires risque risques cher chere chers prix offre offres resultat resultats secret secrets erreur erreurs
probleme problemes jamais toujours rentable rentables facile facilement simple econome economiser economisez economie
economies profit profits benefice benefices vente ventes vendre perdre perdez perdu perte pertes coute coutent couter
cout couts payer payez depenser gaspiller gaspillez arretez attention danger urgent maintenant aujourd'hui nouveau
nouvelle meilleur meilleure meilleurs pire incroyable enorme exclusif exclusive limite limitee dernier derniere
derniers chance succes reussir reussite gagner gagnez gagne doubler tripler exploser croissance
free guaranteed guarantee fast faster quickly instantly instant money cash salary risk risky cheap cheaper expensive
price offer results result secret mistake mistakes problem problems never always profitable easy easily save saving
savings profit profits sales sell lose losing lost loss cost costs pay paying spend waste stop warning urgent today new
best worst amazing incredible huge massive insane crazy exclusive limited last chance success win won winner winning
triple grow growth congratulations'''.split())
# action demandee (appel a l'action)
CTA_WORDS = set('''appuyez appuie appuyer cliquez clique cliquer reservez reserve reserver inscrivez inscris abonnez
abonne contactez contacte appelez ecrivez commentez partagez telechargez essayez decouvrez profitez rejoignez
commandez suivez click tap book subscribe join sign call dm comment share download grab claim order follow visit'''.split())
# expressions qui se lisent d'un bloc
EXPRESSIONS = [('right', 'now'), ('tout', 'de', 'suite'), ('sans', 'risque'),
               ('moins', 'cher'), ('plus', 'vite'), ('plus', 'rapide'), ('no', 'risk'), ('for', 'free'), ('en', 'savoir', 'plus'),
               ('temps', 'plein'), ('full', 'time')]
_ELISION = re.compile(r"^(?:[cdjlmnst]|qu|jusqu|lorsqu|puisqu|quoiqu)'")
_PUNCT = ' ,.!?;:«»"“”()…'
_CTA_ANY = re.compile(r"\b(bouton|cliquez|cliquer|appuy\w*|lien|r[ée]serv\w*|abonne\w*|contactez|inscri\w*|click|tap|link|"
                      r"subscribe|book|sign up|comment|follow|dm)\b", re.I)

DEFAULT_STYLE = {
    'preset': 'reel-impact',
    'font': 'Montserrat', 'weight': 900, 'uppercase': True,
    'size': 72, 'color': '#FFFFFF', 'highlight': '#FFD400', 'stroke': '#000000', 'strokeWidth': 12,
    'position': 0.68, 'maxWords': 3, 'pop': True,
}


def _reel_id(variant):
    return variant or 'script'


def _signature(clip):
    return f"{clip['source']}|{clip['in']}|{clip['out']}|{clip.get('tighten', True)}"


def _core(word):
    """Mot comparable sans l'article elide : « l'experimenter » -> « experimenter », « c'est » -> « est »."""
    return _ELISION.sub('', normalize(str(word)).strip("'"))


def _stem(core):
    """Racine grossiere pour reperer un meme mot repete (« leads » = « lead », « qualifie » = « qualifier »)."""
    if len(core) > 4 and core[-1] in 'sx':
        core = core[:-1]
    return core[:6]


def _is_stop(core, stop):
    if not core or (len(core) < 2 and not core.isdigit()) or core in stop:
        return True
    if "'" in core:  # contractions anglaises : don't, she's, you're, we'll...
        base, suf = core.split("'", 1)
        return (suf in ('s', 're', 've', 'll', 'd', 'm') and base in stop) or (suf == 't' and base.endswith('n'))
    return False


def _words(words):
    return [w if isinstance(w, dict) else {'w': str(w)} for w in words]


def caption_groups(words, max_words=3, tighten=True):
    """Groupes de mots affiches ensemble a l'ecran (meme decoupage que pages() de timeline.ts, pour un plan) :
    coupe au nombre de mots, sur la ponctuation de fin de phrase et sur les pauses gardees. -> [[indices]]"""
    res, cur = [], []
    for i, w in enumerate(words):
        if w.get('hide') or w.get('cut') or not str(w.get('w', '')).strip():
            continue
        if cur:
            p = words[cur[-1]]
            gap = w['start'] - p['end'] if 'start' in w and 'end' in p else 0
            if tighten and gap > 0.45:  # pause resserree au montage : il en reste 0,27 s
                gap = 0.27
            if len(cur) >= max_words or p['w'].rstrip().endswith(('.', '!', '?', '…')) or gap > 0.35:
                res.append(cur)
                cur = []
        cur.append(i)
    if cur:
        res.append(cur)
    return res


def _units(ws, language='fr', brands=(), theme=(), cta=False):
    """Candidats a la mise en couleur : un mot, ou un bloc (chiffre + unite, « En savoir plus », « how much »).
    -> [{'span': [indices], 'score', 'stem', 'num'}]"""
    stop = (STOP_EN if language == 'en' else STOP)
    raws = [str(w.get('w', '')) for w in ws]
    cores = [_core(r) for r in raws]
    off = [bool(w.get('hide') or w.get('cut')) for w in ws]
    letters = [re.sub(r'[^A-Za-zÀ-ÿ]', '', r) for r in raws]
    caps = [len(x) >= 2 and x.isupper() for x in letters]
    caps_ok = sum(caps) <= 0.3 * max(1, len(ws))  # transcription tout en majuscules : l'indice ne vaut rien
    ends = [r.rstrip(' »"”)').endswith(('.', '!', '?', '…', ':')) for r in raws]
    starts = [i == 0 or ends[i - 1] for i in range(len(ws))]
    titled = [bool(x[:1].isupper()) and not starts[i] for i, x in enumerate(letters)]
    title_ok = sum(titled) <= 0.4 * max(1, len(ws))
    stops = [_is_stop(c, stop) for c in cores]
    weak = [c in WEAK for c in cores]
    nums = [bool(re.search(r'\d', r)) or c in NUMBERS for r, c in zip(raws, cores)]

    # mot etire a l'oral (duree par syllabe bien au-dessus de l'habitude du plan) : insistance
    rates = {}
    for i, w in enumerate(ws):
        if i and not stops[i] and w.get('end', 0) > w.get('start', 0) and ws[i - 1].get('end') is not None \
                and w['start'] - ws[i - 1]['end'] < 0.3:
            rates[i] = (w['end'] - w['start']) / max(1, len(re.findall(r'[aeiouy]+', cores[i])))
    usual = statistics.median(rates.values()) if len(rates) >= 5 else None

    def score(i):
        """Poids d'un mot seul (None = jamais en couleur)."""
        c, raw = cores[i], raws[i]
        if off[i] or stops[i] and not nums[i]:
            return None
        loud = caps[i] and caps_ok and c not in ('ok', 'i')
        if weak[i] and not loud:
            return None
        s = (5.0 if re.search(r'\d', raw) else 4.0) if nums[i] else 1.0  # « 30 » ecrit en chiffres : une donnee
        if c in brands or re.search(r'[a-z][A-Z]', raw):
            s = max(s, 4.0)  # marque (RyuCalls, iPhone) : apres le chiffre et le benefice
        elif titled[i] and title_ok and len(c) > 2:
            s = max(s, 3.0)  # nom propre en milieu de phrase (Whisper met parfois des majuscules au hasard)
        if c in STRONG:
            s += 3
        if c in CTA_WORDS:
            s += 3  # le texte du bouton (« En savoir plus ») passe avant le verbe
        if c in TIME:
            s += 1.5
        if loud:
            s += 2.5  # « NON » ecrit en majuscules : insistance
        if raw.rstrip(' »"”').endswith('!'):
            s += 1
        if len(c) >= 8:
            s += 0.5
        if c.endswith('ment') and c not in STRONG and len(c) > 6:
            s -= 0.75  # adverbe (« directement », « vraiment ») : rarement le mot qui porte le message
        if _stem(c) in theme:
            s += 0.75  # mot de l'accroche repris plus loin : le sujet de la video
        if usual and i in rates and rates[i] > 1.7 * usual and ws[i]['end'] - ws[i]['start'] >= 0.35:
            s += 0.75
        before = [cores[k] for k in range(max(0, i - 2), i)]
        if before and (before[-1] in DETERMINERS or (len(before) == 2 and before[0] in DETERMINERS
                                                       and before[1] in ADJ_BEFORE)):
            s += 0.5  # un nom : il porte plus de sens qu'un verbe
        elif before and language != 'en' and before[-1] in ('de', 'a', 'pour', 'sans') and re.search(r'(er|ir|re)$', c):
            s -= 0.5  # infinitif (« pour repondre », « avant de commencer ») : rarement le mot cle
        return s

    single = [score(i) for i in range(len(ws))]
    # fin de phrase : le dernier mot plein porte souvent l'information
    for i in range(len(ws)):
        if ends[i]:
            j = next((k for k in range(i, max(-1, i - 2), -1) if single[k] is not None), None)
            if j is not None:
                single[j] += 0.5
    units = []
    for i in range(len(ws)):
        if off[i]:
            continue
        article = raws[i].strip(_PUNCT).lower() in (('a', 'an', 'one') if language == 'en' else ('un', 'une'))
        if nums[i] or (article and i + 1 < len(ws) and cores[i + 1] in TIME and not ends[i]):
            # chiffre + unite : « trois heures », « 30 % », « cinq fois moins cher », « une semaine »
            span, j = [i], i + 1
            while j < len(ws) and len(span) < 4 and not off[j] and not raws[span[-1]].rstrip(' »"”').endswith(
                    ('.', '!', '?', '…', ',', ';', ':')):
                last, sym = cores[span[-1]], raws[j].strip(_PUNCT)
                if len(span) == 1 and (sym in ('%', '$', '€') or cores[j] in UNITS or (cores[j] == 'pour' and j + 1 < len(ws)
                                                                                    and cores[j + 1] == 'cent')):
                    span += [j, j + 1] if cores[j] == 'pour' else [j]
                elif len(span) == 1 and single[j] is not None and not nums[j]:
                    span.append(j)  # « deux taches », « 100 clients »
                elif last in ('fois', 'times', 'x') and cores[j] in ('moins', 'plus', 'more', 'less'):
                    span.append(j)
                elif last in ('moins', 'plus', 'more', 'less') and not stops[j] and not nums[j]:
                    span.append(j)
                    break
                else:
                    break
                j = span[-1] + 1
            if nums[i]:
                digit = bool(re.search(r'\d', raws[i]))
                unit = (len(span) > 1 and (cores[span[1]] in UNITS or raws[span[1]].strip(_PUNCT) in ('%', '$', '€'))) \
                    or bool(re.search(r'\d\s*[%$€]|\d+/\d+', raws[i]))
                if unit:  # chiffre + unite (« trois heures », « cinq fois moins cher », « 30 % ») : toujours en premier
                    sc = 7.5 + 0.5 * digit + 0.5 * (len(span) >= 3)
                elif digit:  # « 100 clients » : une donnee, sans unite
                    sc = 3.5 + 0.5 * (len(span) > 1)
                else:  # « entre deux taches » : un nombre dit en passant, pas un chiffre fort
                    sc = 1.5 + (1.5 if len(span) > 1 and cores[span[1]] in STRONG else 0)
                units.append({'span': span, 'score': sc, 'stem': ' '.join(cores[k] for k in span[:2]), 'num': unit})
            elif len(span) > 1 and single[span[-1]] is not None:  # « une semaine » : une duree, se lit d'un bloc
                units.append({'span': span, 'score': max(3.5, single[span[-1]]), 'stem': _stem(cores[span[-1]]),
                              'num': False})
        opening = raws[i].lstrip()
        if opening and opening[0] in '«“"':
            # texte du bouton entre guillemets : « En savoir plus »
            k = i + 1 if not raws[i].strip(_PUNCT) else i
            span = []
            while k < len(ws) and len(span) <= 4 and not off[k]:
                if raws[k].strip(_PUNCT):
                    span.append(k)
                if re.search('[»”"]', raws[k][1:] if k == i else raws[k]):
                    break
                k += 1
            if span and len(span) <= 4 and k < len(ws):
                near = ' '.join(cores[max(0, i - 3):i])
                units.append({'span': span, 'score': 3.0 + (1.5 if re.search(r'bouton|button|lien|link', near) else 0)
                              + (2.5 if cta else 0), 'stem': ' '.join(cores[x] for x in span), 'num': False, 'cta': True,
                              'expr': True})  # texte du bouton : se lit d'un bloc, meme sur deux ecrans
        for ex in EXPRESSIONS:
            if tuple(cores[i:i + len(ex)]) == ex and not any(off[i:i + len(ex)]):
                best = max([single[k] for k in range(i, i + len(ex)) if single[k] is not None] or [2.5])
                button = ex == ('en', 'savoir', 'plus')
                units.append({'span': list(range(i, i + len(ex))), 'score': max(3.5, best + 1) + (2.5 if button and cta else 0),
                              'expr': True, 'stem': ' '.join(ex), 'num': False, 'cta': button})
        if single[i] is not None and not nums[i]:
            units.append({'span': [i], 'score': single[i], 'stem': _stem(cores[i]), 'num': False,
                          'cta': cores[i] in CTA_WORDS})
            j = i + 1
            if j < len(ws) and single[j] is not None and min(single[i], single[j]) >= 4 and not nums[j] \
                    and raws[i].strip() == raws[i].strip().rstrip(_PUNCT):
                # deux mots forts qui se suivent se lisent ensemble : « LAST CHANCE », « OFFRE INCROYABLE »
                units.append({'span': [i, j], 'score': max(single[i], single[j]) + 1,
                              'stem': _stem(cores[i]) + ' ' + _stem(cores[j]), 'num': False})
            elif j < len(ws) and single[j] is not None and title_ok and titled[i] and titled[j] \
                    and raws[i].strip() == raws[i].strip().rstrip(_PUNCT):
                # nom propre en deux mots (« Rio Cause », « Jean Tremblay ») : un seul bloc
                units.append({'span': [i, j], 'score': max(single[i], single[j]) + 0.5,
                              'stem': _stem(cores[i]) + ' ' + _stem(cores[j]), 'num': False})
    return units


IDEA_MIN, IDEA_MAX = 10, 20  # une idee : une phrase, ou un morceau de longue phrase (10 a 20 mots)
GAP_WORDS = 22  # passage de plus de ~7 s sans couleur : un mot moyen (score >= 2) peut etre repris
THRESHOLD = 3.0  # en dessous, l'idee reste sans couleur : un mot moyen n'est pas mis en valeur par defaut


def _visible(w):
    return not (w.get('hide') or w.get('cut')) and bool(str(w.get('w', '')).strip())


def _sentence_end(raw):
    return str(raw).rstrip(' »"”)').endswith(('.', '!', '?', '…'))


def idea_groups(words):
    """Idees d'un plan, pour le budget des mots en couleur (au plus un mot ou un bloc par idee) : chaque phrase ;
    une longue phrase est coupee sur une virgule ou un deux-points apres au moins IDEA_MIN mots, et au plus tard
    tous les IDEA_MAX mots. -> [[indices]]"""
    ws = _words(words)
    vis = [i for i, w in enumerate(ws) if _visible(w)]
    left = [0] * len(vis)  # mots restants jusqu'a la fin de la phrase : pas de petit bout de phrase isole
    for n in range(len(vis) - 2, -1, -1):
        left[n] = 0 if _sentence_end(ws[vis[n]]['w']) else left[n + 1] + 1
    res, cur = [], []
    for n, i in enumerate(vis):
        cur.append(i)
        raw = str(ws[i]['w']).rstrip(' »"”)')
        if _sentence_end(raw) or (len(cur) >= IDEA_MAX and left[n] >= 6) \
                or (raw.endswith((',', ';', ':')) and len(cur) >= IDEA_MIN and left[n] >= 5):
            res.append(cur)
            cur = []
    if cur:
        if res and len(cur) < 4 and not _sentence_end(ws[res[-1][-1]]['w']):
            res[-1].extend(cur)  # queue de phrase coupee par la fin du plan : meme idee
        else:
            res.append(cur)
    return res


def _runs(indices):
    """Indices consecutifs regroupes : [3, 4, 9] -> [[3, 4], [9]]."""
    out = []
    for i in sorted(indices):
        if out and i == out[-1][-1] + 1:
            out[-1].append(i)
        else:
            out.append([i])
    return out


def auto_highlights(words, max_words=3, language='fr', context=None, picks=None):
    """Choisit les mots a colorer d'un plan (selection commune a TOUS les chemins : automatique, IA, styles) :
    au plus un mot ou un bloc (« trois heures », « cinq fois moins cher ») par idee, seulement s'il est fort
    (chiffre + unite, puis benefice/douleur, marque, verbe fort), jamais un mot outil, jamais dans deux groupes de
    sous-titres qui se suivent, pas le meme mot partout.
    max_words : mots affiches ensemble par le style ; context : suivi entre les plans (voir reel_highlights), avec
    keep (indices colores a la main : gardes), exclude (decolores a la main : jamais repris) et hints
    ({indice: bonus}, anciens choix automatiques) ; picks : propositions de l'IA ([[indices]], la plus importante
    d'abord) — l'IA propose, les regles valident : une proposition de l'IA ne passe ni le budget ni les interdits."""
    ws = _words(words)
    ctx = context or {}
    seen = ctx.get('seen', {})
    keep = {i for i in (ctx.get('keep') or ()) if 0 <= i < len(ws)}
    exclude = set(ctx.get('exclude') or ())
    hints = ctx.get('hints') or {}
    units = _units(ws, language, ctx.get('brands', ()), ctx.get('theme', ()), ctx.get('cta', False))
    groups = caption_groups(ws, max(3, max_words), ctx.get('tighten', True))  # style « geant » : trois mots d'ecart au moins
    actual_groups = caption_groups(ws, max_words, ctx.get('tighten', True))
    gid = {i: g for g, grp in enumerate(groups) for i in grp}
    ideas = idea_groups(ws)
    iid = {i: n for n, idea in enumerate(ideas) for i in idea}
    # un bloc reste sur un seul ecran, sauf un chiffre et son unite (« CINQ FOIS » | « MOINS CHER ») ou une expression
    units = [u for u in units if all(i in gid for i in u['span']) and not set(u['span']) & (exclude | keep)
             and (u['num'] or u.get('expr') or len({gid[i] for i in u['span']}) == 1)]
    for rank, pick in enumerate(picks or []):
        inside = [u for u in units if set(u['span']) & set(pick)]
        if inside:
            best = max(inside, key=lambda u: (u['score'], len(set(u['span']) & set(pick))))
            best['ai'] = max(best.get('ai', 0), max(0.5, 1.5 - 0.25 * rank))  # un coup de pouce, pas un passe-droit
    for u in units:
        bonus = max([hints.get(i, 0) for i in u['span']] or [0])
        # ancien choix automatique verifie : garde sa place ; origine inconnue : aide seulement un mot deja correct
        hint = bonus if bonus >= 1.5 or u['score'] >= 2.0 else 0
        # un mot deja colore perd de sa force ; le chiffre cle et l'appel a l'action peuvent revenir
        u['final'] = u['score'] + max(u.get('ai', 0), hint) - (1.0 if u['num'] or u.get('cta') else 2.0) * seen.get(u['stem'], 0)
    units.sort(key=lambda u: (-u['final'], u['span'][0]))
    chosen, used, stems, used_ideas = [], set(), set(), set()

    def fits(u):
        if seen.get(u['stem'], 0) >= 2 or (u['stem'] in stems and not u.get('cta')):
            return False  # meme mot deja colore deux fois dans la video, ou deja dans ce plan (sauf l'appel a l'action)
        if iid.get(u['span'][0]) in used_ideas:
            return False  # une idee = un seul mot en couleur
        gs = {gid[i] for i in u['span']}
        if ctx.get('prev_tail') and 0 in gs:
            return False  # le dernier ecran du plan precedent est deja colore
        if any(abs(a - b) < 2 for a in gs for b in used):
            return False  # jamais deux groupes de sous-titres colores qui se suivent
        colored = set(u['span']) | {i for o in chosen for i in o['span']}
        full = [set(g) <= colored for g in actual_groups]
        return not any(a and b for a, b in zip(full, full[1:]))

    def take(u):
        chosen.append(u)
        used.update(gid[i] for i in u['span'] if i in gid)
        used_ideas.update(iid[i] for i in u['span'][:1] if i in iid)
        stems.add(u['stem'])

    for span in _runs(keep):  # choix du monteur : gardes tels quels, ils comptent dans le budget
        take({'span': span, 'stem': _stem(_core(ws[span[0]]['w'])), 'num': False, 'manual': True})
    # un mot decolore a la main : son idee reste sans couleur (on ne le remplace pas par un autre)
    used_ideas.update(iid[i] for i in exclude if i in iid)
    for u in units:
        if u['final'] >= THRESHOLD and fits(u):
            take(u)
    if ctx.get('hook'):
        # l'accroche (premiere phrase) a toujours un mot en valeur, meme simple
        first = []
        for i, w in enumerate(ws):
            if _visible(w):
                first.append(i)
                if _sentence_end(w['w']):
                    break
        if first and not any(set(u['span']) & set(first) for u in chosen):
            for u in units:
                if u['span'][0] in first and u['final'] >= 1.0 and fits(u):
                    take(u)
                    break
    # long passage sans aucune couleur (plus de GAP_WORDS mots, ~7 s) : la premiere idee du passage recoit son
    # meilleur mot s'il est correct (score >= 2), pour garder un rythme regulier sans mettre de mot faible
    order = [i for idea in ideas for i in idea]
    pos = {i: n for n, i in enumerate(order)}
    for idea in ideas:
        if iid[idea[0]] in used_ideas:
            continue
        marks = sorted(pos[i] for o in chosen for i in o['span'] if i in pos)
        before = max([m for m in marks if m < pos[idea[0]]], default=-ctx.get('since', GAP_WORDS))
        after = min([m for m in marks if m > pos[idea[-1]]], default=len(order))
        if after - before < GAP_WORDS:
            continue
        for u in units:
            if u['span'][0] in idea and u['final'] >= 2.0 and fits(u):
                take(u)
                break
    for u in chosen:
        seen[u['stem']] = seen.get(u['stem'], 0) + 1
    return {i for u in chosen for i in u['span']}


def _theme(clips, language='fr'):
    """Mots de l'accroche (1er plan) repris ailleurs dans la video : le sujet."""
    stop = (STOP_EN if language == 'en' else STOP)
    stems = [[_stem(c) for c in (_core(w['w']) for w in _words(cl['words'])) if not _is_stop(c, stop) and c not in WEAK
              and len(c) >= 4] for cl in clips]
    if len(stems) < 2:
        return set()
    count = {}
    for s in (s for cl in stems for s in cl):
        count[s] = count.get(s, 0) + 1
    # un mot dit partout (« leads ») est le decor, pas l'information : pas de bonus
    return {s for s in stems[0] if any(s in other for other in stems[1:]) and count[s] <= 5}


def reel_highlights(clips, max_words=3, language='fr', picks=None, only=None, brands=(), keep=None, exclude=None,
                    hints=None):
    """Mots en couleur de tous les plans, dans l'ordre du montage : l'accroche et l'appel a l'action sont couverts,
    un meme mot n'est pas colore partout. only : plans a calculer (les autres gardent leurs mots en couleur,
    qui comptent pour les repetitions). picks : {plan: [[indices]]} proposes par l'IA ; keep / exclude :
    {plan: indices} choisis a la main ; hints : {plan: {indice: bonus}}. -> {plan: [indices]}"""
    seen, out = {}, {}
    prev_tail, since = False, GAP_WORDS
    theme = _theme(clips, language)
    brands = {normalize(b).replace(' ', '') for b in brands if b}
    last = clips[-1] if clips else None
    cta_id = last['id'] if last and len(clips) > 1 and _CTA_ANY.search(' '.join(str(w.get('w', '')) for w in _words(last['words']))) else None
    for n, c in enumerate(clips):
        ws = _words(c['words'])
        gs = caption_groups(ws, max(3, max_words), c.get('tighten', True))
        vis = [i for i, w in enumerate(ws) if _visible(w)]
        if only is not None and c['id'] not in only:
            for w in ws:
                if w.get('hl'):
                    st = _stem(_core(w['w']))
                    seen[st] = seen.get(st, 0) + 1
            on = {i for i, w in enumerate(ws) if w.get('hl')}
        else:
            ctx = {'seen': seen, 'theme': theme, 'brands': brands, 'hook': n == 0, 'cta': c['id'] == cta_id,
                   'tighten': c.get('tighten', True), 'prev_tail': prev_tail, 'since': since,
                   'keep': (keep or {}).get(c['id']), 'exclude': (exclude or {}).get(c['id']),
                   'hints': (hints or {}).get(c['id'])}
            out[c['id']] = sorted(auto_highlights(ws, max_words, language, ctx, (picks or {}).get(c['id'])))
            on = set(out[c['id']])
        prev_tail = bool(gs and set(gs[-1]) & on)
        marked = [n for n, i in enumerate(vis) if i in on]
        since = len(vis) - 1 - marked[-1] if marked else since + len(vis)
    return out


def reel_language(reel):
    """Langue d'un reel deja monte : celle retenue au montage, sinon devinee par les petits mots dits."""
    lang = reel.get('langue') or reel.get('language')
    if lang and lang != 'auto':
        return lang
    fr = en = 0
    for c in reel.get('clips') or []:
        for w in _words(c.get('words') or []):
            k = _core(w.get('w', ''))
            fr += k in STOP_FR and k not in STOP_EN
            en += k in STOP_EN and k not in STOP_FR
    return 'en' if en > 1.5 * fr else 'fr'


def _words_sig(words):
    """Empreinte des mots d'un plan (leurs instants) : change si la prise ou le decoupage des mots change."""
    import hashlib
    return hashlib.md5('|'.join(f"{w.get('start', 0):.2f}" for w in _words(words)).encode()).hexdigest()[:12]


def mark_auto(reel, ids=None, manual=None, off=None):
    """Retient dans reel['hlAuto'] les mots colores par la selection automatique, pour reconnaitre ensuite ceux que
    le monteur a colores ou decolores a la main (gardes lors d'un changement de style). ids : plans a noter."""
    doc = reel.setdefault('hlAuto', {})
    present = {c['id'] for c in reel.get('clips') or []}
    for cid in [k for k in doc if k not in present]:
        del doc[cid]
    for c in reel.get('clips') or []:
        if ids is not None and c['id'] not in ids:
            continue
        on = {i for i, w in enumerate(_words(c['words'])) if w.get('hl')} - set((manual or {}).get(c['id'], ()))
        doc[c['id']] = {'sig': _words_sig(c['words']), 'on': sorted(on), 'off': sorted((off or {}).get(c['id'], ()))}
    return reel


def rehighlight(reel, language=None):
    """Revalide les mots en couleur d'un reel avec la selection commune (auto_highlights), au rythme des
    sous-titres de son style. Les mots colores ou decolores a la main (difference avec reel['hlAuto']) sont gardes ;
    les anciens choix automatiques (IA comprise) gardent leur place s'ils respectent encore les regles ; un reel sans
    historique (ancien montage) est remis au budget : un mot ou un bloc par idee."""
    clips = [c for c in reel.get('clips') or [] if isinstance(c.get('words'), list)]
    if not clips or reel.get('aiMode') == 'suggestion':
        return reel  # mode « suggestion » : le monteur decide, on ne colore rien de soi-meme
    lang = language or reel_language(reel)
    mw = (reel.get('style') or {}).get('maxWords') or DEFAULT_STYLE['maxWords']
    doc = reel.get('hlAuto') or {}
    keep, exclude, hints = {}, {}, {}
    for c in clips:
        cur = {i for i, w in enumerate(_words(c['words'])) if w.get('hl')}
        rec = doc.get(c['id'])
        if rec and rec.get('sig') == _words_sig(c['words']):
            was = set(rec.get('on') or [])
            keep[c['id']] = cur - was
            exclude[c['id']] = (was - cur) | (set(rec.get('off') or []) - cur)
            hints[c['id']] = {i: 1.5 for i in cur & was}
        else:
            hints[c['id']] = {i: 1.0 for i in cur}
    sel = reel_highlights(clips, mw, lang, brands=_brands(reel), keep=keep, exclude=exclude, hints=hints)
    for c in clips:
        on = set(sel.get(c['id'], []))
        for i, w in enumerate(c['words']):
            if isinstance(w, dict):
                w['hl'] = i in on
    return mark_auto(reel, {c['id'] for c in clips}, keep, exclude)


def key_blocks(reel, language=None):
    """Mots ou blocs en couleur du reel, avec leur force (meme classement que la selection : chiffre + unite,
    puis benefice/douleur, marque, verbe fort). Les habillages des styles (mot geant, autocollant...) s'en servent :
    un seul classement pour toute la video. -> [{'clip', 'index', 'length', 'text', 'score', 'num'}]"""
    lang = language or reel_language(reel)
    brands = {normalize(b).replace(' ', '') for b in _brands(reel) if b}
    out = []
    for c in reel.get('clips') or []:
        ws = _words(c['words'])
        units = _units(ws, lang, brands)
        on = [i for i, w in enumerate(ws) if w.get('hl') and _visible(w)]
        for run in _runs(on):
            inside = [u for u in units if set(u['span']) & set(run)]
            best = max(inside, key=lambda u: (len(set(u['span']) & set(run)), u['score'])) if inside else None
            text = ' '.join(ws[k]['w'].strip(' ,;:') for k in run).strip(_PUNCT)
            if text:
                out.append({'clip': c['id'], 'index': run[0], 'length': len(run), 'text': text,
                            'score': best['score'] if best else 0.0, 'num': bool(best and best['num'])})
    return out


def _caption_words(reel=None, template=None):
    """Nombre de mots affiches ensemble par les sous-titres : style du reel, sinon celui du style de montage."""
    st = (reel or {}).get('style') or {}
    if st.get('maxWords') and not template:
        return st['maxWords']
    try:
        tid = template or (reel or {}).get('template') or 'reel-impact'
        t = next((x for x in list_templates() if x['id'] == tid), None) or {}
        preset = next((p for p in caption_presets() if p['id'] == t.get('captions')), None) or {}
        return (t.get('style') or {}).get('maxWords') or (preset.get('style') or {}).get('maxWords') or DEFAULT_STYLE['maxWords']
    except Exception:
        return DEFAULT_STYLE['maxWords']


def _brands(reel=None):
    """Noms de marque connus (charte du reel, chartes clients) : toujours mis en valeur."""
    names = [((reel or {}).get('brand') or {}).get('name')]
    try:
        for f in (STYLES / 'clients').glob('*.json'):
            names.append(json.loads(f.read_text(encoding='utf-8')).get('name'))
    except Exception:
        pass
    return [n for n in names if n]


def merge_fragments(words):
    """Recolle les morceaux que Whisper separe : « Est -ce » -> « Est-ce », « quelqu 'un » -> « quelqu'un »."""
    out = []
    for w in words:
        text = w['w'].strip()
        if out and (text[:1] in "'’-" or out[-1]['w'].endswith(("'", '’', '-'))):
            out[-1] = {**out[-1], 'w': out[-1]['w'] + text, 'end': w['end']}
        else:
            out.append({**w, 'w': text})
    return out


def _default_banner(clips):
    first = next((c for c in clips if c['words']), None)
    if not first:
        return ''
    text = ' '.join(w['w'] for w in merge_fragments(first['words']))
    sentence = re.split(r'(?<=[?.!])\s', text)[0]
    words = sentence.split()
    return ' '.join(words[:8]).rstrip(',;:') + ('…' if len(words) > 8 else '')


def _delivery_dir(project):
    from .deliver import _safe
    return str(ROOT / 'livraisons' / _safe(Path(project['script']['file']).stem))


def _title(project, variant):
    """Meme nom que le montage complet de la livraison, pour s'y retrouver."""
    from .deliver import _opening, _safe
    label = project.get('label') or project['name']
    hooks = [v for v in project['variants'] if v['replaces_block']]
    for n, v in enumerate(hooks, 1):
        if v['id'] == variant:
            return _safe(f'{label} - 0 COMPLET - Hook alternatif {n} ({_opening(v["clip"]["text"], 5)})')
    return _safe(f'{label} - 0 COMPLET' + (' - Hook original' if hooks else ''))


STYLES = ROOT / 'styles'
CTA = re.compile(r"\b(bouton|cliquez|cliquer|appuy\w*|lien|r[ée]serv\w*|abonne\w*|contactez|inscri\w*)\b", re.I)


def list_templates():
    return [json.loads(f.read_text(encoding='utf-8')) for f in sorted((STYLES / 'montage').glob('*.json'))]


def caption_presets():
    return json.loads((STYLES / 'sous-titres.json').read_text(encoding='utf-8'))


def music_moods():
    return json.loads((STYLES / 'musiques.json').read_text(encoding='utf-8'))


def apply_template(reel, template_id):
    """Applique un style de montage complet. Les mots corriges, masques ou colores a la main sont gardes."""
    t = next((x for x in list_templates() if x['id'] == template_id), None)
    if not t:
        raise KeyError(f'Style de montage inconnu : {template_id}')
    preset = next((p for p in caption_presets() if p['id'] == t['captions']), caption_presets()[0])
    reel['template'] = t['id']
    # un style peut preciser ses sous-titres par-dessus le preset (styles crees depuis une video de reference)
    reel['style'] = {**DEFAULT_STYLE, **preset['style'], **(t.get('style') or {}), 'preset': preset['id']}
    reel['zoom'] = {**t['zoom'], 'overrides': reel.get('zoom', {}).get('overrides', {})}
    reel['banner'] = {**reel.get('banner', {'text': '', 'start': 0, 'end': None}), 'enabled': t['banner']['enabled']}
    reel['flash'] = dict(t['flash'])
    reel['effects'] = dict(t['effects'])
    reel['emoji'] = {'enabled': bool(t.get('emoji'))}
    reel['progress'] = {'enabled': bool(t.get('progress'))}
    mood = t['music'].get('mood')
    reel['music'] = {'enabled': bool(mood), 'mood': mood, 'file': f'music/{mood}.ogg' if mood else None,
                     'volume': t['music'].get('volume', 0.14)}
    reel['sfx'] = {'enabled': True, **t['sfx'], 'extra': (reel.get('sfx') or {}).get('extra', [])}
    if reel.get('brand'):  # la charte du client passe par-dessus le style de montage
        reel['style'].update({k: v for k, v in (reel['brand'].get('style') or {}).items() if v})
    from . import galerie
    galerie.apply(reel, t)
    return reel


def _editorial(clips, fresh_ids, want_banner, language='fr', max_words=3, brands=(), keep=None):
    """Mots cles, emojis et bandeau par l'IA locale ; regles simples si l'IA n'est pas disponible.
    Les mots en couleur : l'IA propose, les regles valident et completent sur toute la video (un par idee,
    groupes de sous-titres, repetitions, accroche, appel a l'action). keep : {plan: indices} deja colores
    (gardes, ils comptent dans le budget)."""
    import os
    from . import llm
    todo = [c for c in clips if c['id'] in fresh_ids]
    if not todo and not want_banner:
        return None
    if os.environ.get('EDITEUR_LLM', '1') == '0' or not llm.available():
        return None
    try:
        with llm.session():
            ed = llm.editorial([{'id': c['id'], 'words': c['words']} for c in (todo or clips)], language, max_words)
    except Exception as e:  # l'IA est un plus : le montage ne doit jamais en dependre
        print(f'IA locale indisponible ({e}) : regles simples utilisees.')
        return None
    if ed and ed.get('picks') is not None:
        ids = {c['id'] for c in (todo or clips)}
        ed['highlights'] = reel_highlights(clips, max_words, language, ed['picks'], only=ids, brands=brands, keep=keep)
    return ed


def _rel(path):
    """Chemin relatif au dossier de l'editeur, avec des « / » (utilisable comme URL)."""
    return Path(path).resolve().relative_to(ROOT.resolve()).as_posix()


def _roomtone(src, analysis, words, cache):
    """Fond d'ambiance d'une prise : la seconde la plus calme sans parole, extraite une fois."""
    from .media import FFMPEG, cache_name, run
    out = cache / 'ambiances' / f"{cache_name(src['path'])}.wav"
    if out.exists():
        return _rel(out)
    a = analysis['audio']
    rms, step = a['rms_db'], a['step']
    busy = [(w['start'] - 0.15, w['end'] + 0.15) for w in words]
    best, best_db = None, 0.0
    for i in range(0, max(0, len(rms) - 12)):
        t0, t1 = i * step, i * step + 1.2
        if any(s < t1 and e > t0 for s, e in busy):
            continue
        level = max(rms[i:i + 12])
        if best is None or level < best_db:
            best, best_db = t0, level
    if best is None or best_db > -30:  # pas de vrai silence : pas de fond d'ambiance
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    run([FFMPEG, '-v', 'error', '-y', '-ss', f'{best:.2f}', '-t', '1.2', '-i', src['path'], '-vn', '-ac', '2', '-ar', '48000',
         '-af', 'afade=t=in:d=0.1,afade=t=out:st=1.1:d=0.1', str(out)])
    return _rel(out)


def _sources(project, ids, cache, old_sources=None):
    """Prises utilisables par le reel : media optimise (cadre d'origine), echantillons visage/couleur, ambiance,
    piste de recadrage (prises horizontales), synchro multicamera. Les plans de coupe deja ajoutes sont gardes."""
    from . import cadrage, transcribe
    out = {}
    sync = {s: {'group': g['id'], 'offset': off} for g in project.get('multicam', []) for s, off in g['offsets'].items()}
    for sid in sorted(ids):
        src = project['sources'][sid]
        an = analyze.analyze(src['path'], cache / 'analysis')
        samples = []
        for f in an['frames']:
            if f.get('face') and f.get('color'):
                r, g, b = f['color']
                samples.append([f['t'], round(f['face']['cx'], 3), round(f['face']['cy'], 3),
                                round(0.299 * r + 0.587 * g + 0.114 * b, 1), r, g, b])
        words = transcribe.transcribe(src['path'], cache / 'transcripts')['words']
        # le media optimise suit la regle actuelle (cadre d'origine) ; ne re-encode que si elle a change
        proxy = Path(src['proxy']) if src.get('stab') else media.optimized(src['path'], src['rotate'], cache / 'optimises')
        info = media.probe(proxy)
        doc = {'name': src['name'], 'proxy': _rel(proxy), 'path': src['path'], 'duration': src['duration'],
               'width': info['width'], 'height': info['height'],
               'samples': samples, 'roomtone': _roomtone(src, an, words, cache)}
        try:  # voix debruitee pour l'apercu (l'export applique le meme traitement aux rushs d'origine)
            voice = media.clean_voice(src['path'], cache / 'voix', bool(project['audio'].get('declip')))
            if voice:
                doc['voice'] = _rel(voice)
        except Exception as e:
            print(f"Voix nettoyee indisponible pour {src['name']} ({e}) : apercu avec le son d'origine.")
        if info['width'] > info['height']:  # prise horizontale : on suit la personne qui parle
            doc['track'] = cadrage.track(proxy, cache / 'analysis')
        if sid in sync:
            doc['sync'] = sync[sid]
        out[sid] = doc
    for sid, s in (old_sources or {}).items():
        if s.get('kind') == 'broll' and sid not in out:
            out[sid] = s
    return out


def _angle_ids(project, clips):
    """Prises des groupes multicamera utilises par le montage (pour pouvoir changer d'angle)."""
    used = {c['source'] for c in clips}
    return {s for g in project.get('multicam', []) if used & set(g['offsets']) for s in g['offsets']}


def _clip_doc(c, prev=None, hl=None):
    """Plan du reel a partir du montage : garde les retouches si c'est la meme prise et les memes coupes.
    hl : mots en couleur deja choisis sur toute la video (reel_highlights), sinon choisis pour ce plan seul."""
    sig = _signature(c)
    if prev and prev.get('signature') == sig and 'source' in prev:
        return prev, False
    words = merge_fragments(c['words'])
    hl = set(hl) if hl is not None else auto_highlights(words)
    old = {round(w['start'], 2): w for w in (prev or {}).get('words', [])}
    doc_words = []
    for i, w in enumerate(words):
        o = old.get(round(w['start'], 2))
        doc_words.append({'w': o['w'] if o else w['w'], 'start': w['start'], 'end': w['end'],
                          'hl': o['hl'] if o else i in hl, 'hide': o.get('hide', False) if o else False,
                          'cut': o.get('cut', False) if o else False})
    return {'id': c['id'], 'block': c['block'], 'signature': sig, 'source': c['source'], 'in': c['in'], 'out': c['out'],
            'tighten': c.get('tighten', True), 'choice': c.get('choice', 0), 'words': doc_words,
            'emojis': (prev or {}).get('emojis', []), 'audioLead': (prev or {}).get('audioLead', 0),
            'audioTail': (prev or {}).get('audioTail', 0),
            'color': (prev or {}).get('color') or {'auto': True, 'exposure': 0, 'temperature': 0},
            **{k: c[k] for k in ('mute', 'speed') if k in c}}, prev is None or not old


def suggestions_from(clips, ed, banners=(), max_words=3, language='fr', brands=(), keep=None):
    """Propositions de l'IA (ou des regles) en attente de validation : mots en couleur, emojis, bandeaux.
    keep : mots deja colores ({plan: indices}) ; les propositions respectent le budget avec eux."""
    words, emojis, rules = {}, {}, None
    for c in clips:
        hl = (ed or {}).get('highlights', {}).get(c['id'])
        if hl is None:
            if rules is None:  # regles calculees une fois sur tous les plans (repetitions, accroche)
                rules = reel_highlights(clips, max_words, language, brands=brands, keep=keep)
            hl = rules.get(c['id'], [])
        words[c['id']] = [i for i in hl if i < len(c['words']) and not c['words'][i]['hl']]
        emojis[c['id']] = (ed or {}).get('emojis', {}).get(c['id'], [])
    return {'banners': list((ed or {}).get('banners') or banners), 'words': words, 'emojis': emojis}


def language_of(project):
    """Langue de la video : celle choisie au derushage, sinon celle detectee par la transcription."""
    lang = project.get('langue')
    if lang and lang != 'auto':
        return lang
    for src in project.get('sources', {}).values():
        try:
            return json.loads(Path(src['transcript']).read_text(encoding='utf-8')).get('language') or 'fr'
        except Exception:
            continue
    return 'fr'


def refresh_ai(project_dir, variant=None):
    """Relance l'IA sur tout le reel et range ses choix en propositions (rien n'est applique)."""
    reel_file = Path(project_dir) / 'reels' / f'{_reel_id(variant)}.json'
    reel = json.loads(reel_file.read_text(encoding='utf-8'))
    project = json.loads((Path(project_dir) / 'project.json').read_text(encoding='utf-8'))
    lang, mw, brands = language_of(project), _caption_words(reel), _brands(reel)
    # les mots deja colores restent et comptent dans le budget : on ne propose que ce qui manque
    current = {c['id']: {i for i, w in enumerate(c['words']) if w.get('hl')} for c in reel['clips']}
    ed = _editorial(reel['clips'], {c['id'] for c in reel['clips']}, want_banner=True, language=lang, max_words=mw,
                    brands=brands, keep=current)
    reel['suggestions'] = suggestions_from(reel['clips'], ed, [_default_banner(reel['clips'])], mw, lang, brands,
                                           keep=current)
    reel_file.write_text(json.dumps(reel, ensure_ascii=False, indent=1), encoding='utf-8')
    return reel['suggestions']


def ensure(project_dir, variant=None, template=None, ai_mode=None, **_):
    """Cree ou met a jour le reel (reels/<version>.json). Plus de video intermediaire : l'apercu et
    l'export lisent directement les medias optimises ; toute retouche est instantanee.
    ai_mode : 'auto' (l'IA applique ses choix) ou 'suggestion' (elle propose, le monteur valide)."""
    project_dir = Path(project_dir)
    project = json.loads((project_dir / 'project.json').read_text(encoding='utf-8'))
    cache = ROOT / 'projects/_cache'
    rid = _reel_id(variant)
    rdir = project_dir / 'reels'
    rdir.mkdir(exist_ok=True)
    reel_file = rdir / f'{rid}.json'
    old = json.loads(reel_file.read_text(encoding='utf-8')) if reel_file.exists() else None
    if old and template:
        # Un clic sur un style habille le reel courant, sans reconstruire les prises ni perdre les retouches.
        apply_template(old, template)
        from . import detourage
        detourage.prepare(old)
        reel_file.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding='utf-8')
        return reel_file
    if old and old.get('derivedFrom'):
        # declinaison (60/30/15 s, rapide...) : son montage lui est propre, on ne met a jour que le style
        if template:
            apply_template(old, template)
        reel_file.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding='utf-8')
        return reel_file
    timeline = render.resolve_timeline(project, variant)

    # Le montage du reel (ordre, prises, coupes) vit dans le reel une fois cree ; sinon, celui du derushage.
    old_clips = {c['id']: c for c in (old or {}).get('clips', [])}
    by_id = {c['id']: c for c in timeline}
    order = [c['id'] for c in (old or {}).get('clips', []) if c['id'] in by_id and 'source' in c] or [c['id'] for c in timeline]
    kept = {cid for cid in order if old_clips.get(cid) and 'source' in old_clips[cid]}
    # mots en couleur choisis sur toute la video, au rythme des sous-titres du style (les plans gardes comptent
    # pour les repetitions)
    lang, mw, brands = language_of(project), _caption_words(old, template), _brands(old)
    hls = reel_highlights([old_clips[cid] if cid in kept else {'id': cid, 'words': merge_fragments(by_id[cid]['words'])}
                           for cid in order], mw, lang, only=set(order) - kept, brands=brands)
    clips, fresh = [], set()
    for cid in order:
        prev = old_clips.get(cid)
        if cid in kept:  # deja au nouveau format : le reel fait foi
            clips.append(prev)
            continue
        doc, is_new = _clip_doc(by_id[cid], prev, hls.get(cid))
        clips.append(doc)
        if is_new:
            fresh.add(cid)

    ed = _editorial(clips, fresh, want_banner=not old, language=lang, max_words=mw, brands=brands)
    tpl = next((x for x in list_templates() if x['id'] == (template or (old or {}).get('template') or 'reel-impact')), {})
    mode = ai_mode or (old or {}).get('aiMode') or tpl.get('ia', 'auto')
    if mode == 'suggestion':
        # le monteur decide : les mots en couleur (IA ou regles) et les emojis deviennent des propositions
        new = [c for c in clips if c['id'] in fresh]
        for c in new:
            for w in c['words']:
                w['hl'] = False
            c['emojis'] = []
        sug = suggestions_from(new, ed, [] if old else [_default_banner(clips)], mw, lang, brands)
        prev = (old or {}).get('suggestions') or {'banners': [], 'words': {}, 'emojis': {}}
        sug = {'banners': sug['banners'] or prev['banners'], 'words': {**prev['words'], **sug['words']},
               'emojis': {**prev['emojis'], **sug['emojis']}}
    else:
        if ed:
            for c in clips:
                if c['id'] in fresh and ed['highlights'].get(c['id']):
                    for i, w in enumerate(c['words']):
                        w['hl'] = i in ed['highlights'][c['id']]
                if c['id'] in fresh:
                    c['emojis'] = ed['emojis'].get(c['id'], [])
        # les autres bandeaux proposes restent disponibles
        sug = {**((old or {}).get('suggestions') or {'words': {}, 'emojis': {}}),
               'banners': (ed or {}).get('banners') or ((old or {}).get('suggestions') or {}).get('banners', [])}

    ids = {c['source'] for c in clips}
    for c in timeline:
        ids |= {t['source'] for t in c.get('takes', [])}
    blocks = project['script']['blocks']
    cta = blocks[-1]['id'] if len(blocks) > 1 and CTA.search(blocks[-1]['text']) else None
    fmt = project['format']
    reel = {k: v for k, v in (old or {}).items() if k not in ('base', 'segments')}
    reel.update({
        'id': rid, 'project': project['name'], 'variant': variant, 'title': _title(project, variant),
        'delivery': project.get('delivery') or _delivery_dir(project),
        'width': fmt['width'], 'height': fmt['height'], 'fps': fmt['fps'],
        'sources': _sources(project, ids | _angle_ids(project, clips), cache, (old or {}).get('sources')),
        'clips': clips, 'ctaBlock': cta,
    })
    if old and 'width' in old:  # le format choisi dans l'interface (16:9, 4:5...) est garde
        reel['width'], reel['height'] = old['width'], old['height']
    # voix debruitee par defaut ; plus de « fond d'ambiance » (il rajoutait du bruit, surtout sous la musique)
    reel.setdefault('audio', {'voice': 'naturel', 'roomTone': False, 'denoise': True, 'declip': bool(project['audio'].get('declip'))})
    reel.setdefault('intro', {'enabled': False, 'text': '', 'file': None, 'duration': 2.5})
    reel['aiMode'] = mode
    reel['suggestions'] = sug
    # mots colores par la selection automatique : un changement de style gardera les retouches faites a la main
    mark_auto(reel, fresh)
    if not old:
        text = (ed or {}).get('banner') or _default_banner(clips)
        # le bandeau d'accroche reste pendant l'accroche, pas toute la video
        reel['banner'] = {'enabled': True, 'text': '' if mode == 'suggestion' else text, 'start': 0, 'end': 4.5}
        apply_template(reel, template or 'reel-impact')
    elif template:
        apply_template(reel, template)
    if (reel.get('design') or {}).get('mode') in ('editorial', 'collage'):
        from . import detourage
        detourage.prepare(reel)
    reel_file.write_text(json.dumps(reel, ensure_ascii=False, indent=1), encoding='utf-8')
    return reel_file
