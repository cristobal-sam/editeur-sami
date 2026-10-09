"""« Refaire seulement ce passage » — MODULE DE L'AGENT « passage » (docs/direction-creative-v2/SPEC.md §9.5).

refaire(project_dir, rid, debut, fin) refait les decisions AUTOMATIQUES de l'habillage dans la plage [debut, fin]
(secondes du montage), et rien d'autre :
- mots en couleur des pages de sous-titres entierement dans la plage (meme selection que les styles :
  reel.reel_highlights ; mots colores ou decolores a la main gardes grace a reel['hlAuto']) ;
- scenes du style (galerie, reliees au cerveau creatif) et graphismes proposes (graphismes.suggest) dont tout
  l'intervalle est dans la plage ; plans de coupe et vecteurs automatiques de la plage relus ;
- relecture de sobriete limitee a la plage (un seul element a la fois, rien sur l'accroche sauf le bandeau) ;
- choregraphie de la plage (choregraphie.actualiser) ; mouvements orphelins de la plage retires.
Garanties (tests : docs/direction-creative-v2/tests/passage/) :
- tout ce qui n'est pas ENTIEREMENT dans la plage reste exactement tel quel : avant, apres, et aussi un element a
  cheval sur une borne (il sert d'obstacle fixe a la relecture) ;
- rien de verrouille ou de retouche ne change (verrous.protege, plan verrouille Clip.locked), ni les notes, les
  dessins, le bandeau, les emojis, le montage (prises, coupes, vitesses), la musique, les bruitages hors plage... :
  seuls les champs d'habillage automatique ci-dessus peuvent bouger (liste blanche, _garde) ;
- une version « avant refaire le passage » est gardee (versions/<reel>/, meme format que le serveur) :
  « Annuler » la restaure a l'octet pres. Rien a changer : le fichier n'est pas reecrit.
"""
import copy
import json
import math
import os
import re
import uuid
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import montage, verrous
from .media import ROOT

PAS_ENCORE = 'Refaire ce passage : pas encore disponible (en cours de construction).'  # garde pour compatibilite
MIN_DUREE = 0.3            # meme limite que la route du serveur
EPS = 1e-3
NOM_VERSION = 'avant refaire le passage'
TENUE, TENUE_FIN = 0.6, 0.4  # pages() de timeline.ts : une page reste 0,6 s apres son dernier mot (0,4 s a la fin)
LISTES = ('graphics', 'broll', 'vectors', 'styleScenes')
# champs que la passe a le droit de modifier (et seulement pour ce qui est entierement dans la plage)
GERES = set(LISTES) | {'clips', 'hlAuto', 'suggestions', 'sobriete', 'creativePlan', 'sfx', 'choreography'}
SCENES = {'notification': 'Notification', 'metric': 'Chiffre', 'comparison': 'Comparaison', 'keyword': 'Mot clé',
          'paper': 'Autocollant', 'product': 'Produit', 'dashboard': 'Tableau', 'flow': 'Parcours', 'cta': 'Bouton'}
GRAPHISMES = {'chiffre': 'Chiffre', 'coches': 'Liste de bénéfices', 'carte': 'Carte', 'motgeant': 'Mot géant',
              'logo': 'Logo'}


class PassageInvalide(ValueError):
    """Plage refusee ou montage introuvable : le message (en francais) est affiche tel quel dans l'interface."""


def _s(n):
    return 's' if n > 1 else ''


def _sec(t):
    return f'{t:.1f}'.replace('.', ',') + ' s'


def _tc(t):
    """0:37,9 (minutes:secondes du montage)."""
    t = max(0.0, float(t))
    m = int(t // 60)
    return f'{m}:{t - 60 * m:04.1f}'.replace('.', ',')


def _nombre(v, nom):
    try:
        x = float(v)
    except (TypeError, ValueError):
        x = float('nan')
    if not math.isfinite(x):
        raise PassageInvalide(f'Passage invalide : {nom} doit être un nombre de secondes.')
    return x


def verifier(debut, fin, total):
    """Plage [debut, fin] valide pour un montage de `total` s -> (debut, fin, remarques). Une fin apres la fin de la
    video y est ramenee ; tout le reste est refuse avec une phrase claire (PassageInvalide)."""
    a, b = _nombre(debut, 'le début'), _nombre(fin, 'la fin')
    notes = []
    if a < 0:
        raise PassageInvalide('Passage invalide : le début ne peut pas être avant 0 s.')
    if b <= a:
        raise PassageInvalide('Passage invalide : le début doit être avant la fin.')
    if a >= total:
        raise PassageInvalide(f'Passage invalide : il commence à {_tc(a)}, après la fin de la vidéo ({_tc(total)}).')
    if b > total:
        if b - total > 0.05:  # « Fin ici » tout au bout : l'arrondi de l'interface (3 decimales) n'est pas a signaler
            notes.append(f'Fin ramenée à la fin de la vidéo ({_tc(total)}).')
        b = total
    if b - a < MIN_DUREE:
        raise PassageInvalide(f'Passage trop court ({_sec(b - a)}) : choisis au moins {_sec(MIN_DUREE)}.')
    return round(a, 3), round(b, 3), notes


# ---------- la plage et le temps de chaque element ----------
class _Plage:
    """Plage du montage et temps de chaque element (meme calcul que l'apercu : montage.compute)."""

    def __init__(self, reel, seg, a, b):
        self.a, self.b = a, b
        self.mots = {(w['clip'], w['index']): (float(w['start']), float(w['end'])) for w in seg.get('words') or []}
        self.temps = {k: v[0] for k, v in self.mots.items()}
        self.pages = _pages(reel, seg)
        # mots dont la couleur peut changer : toute leur page de sous-titres est dans la plage (sinon l'image d'avant
        # ou d'apres la plage changerait), et leur plan n'est pas verrouille
        verrouilles = {c['id'] for c in reel.get('clips') or [] if verrous.is_locked(c)}
        self.eligibles = {}
        for debut, fin, cles in self.pages:
            if debut >= a - EPS and fin <= b + EPS:
                for cid, i in cles:
                    if cid not in verrouilles:
                        self.eligibles.setdefault(cid, set()).add(i)

    def iv(self, nom, e):
        """[debut, fin] d'un element dans le montage, ou None (inconnu : il n'est jamais touche)."""
        if not isinstance(e, dict):
            return None
        try:
            if nom == 'styleScenes':
                t = self.temps.get((e.get('clip'), e.get('index')))
                return None if t is None else (t, t + float(e.get('duration') or 2.4))
            if nom == 'cues':
                return None if e.get('at') is None else (float(e['at']), float(e['at']) + float(e.get('duree') or 0))
            if nom == 'sfx':
                return None if e.get('t') is None else (float(e['t']), float(e['t']))
            if nom == 'shots':
                return None if e.get('start') is None else (float(e['start']), float(e.get('end') or e['start']))
            if e.get('at') is None:
                return None
            return float(e['at']), float(e['at']) + float(e.get('duration') or 0)
        except (TypeError, ValueError):
            return None

    def dedans(self, nom, e):
        """Entierement dans la plage : la passe peut le refaire."""
        iv = self.iv(nom, e)
        return iv is not None and iv[0] >= self.a - EPS and iv[1] <= self.b + EPS

    def touche(self, nom, e):
        iv = self.iv(nom, e)
        return iv is not None and iv[1] > self.a and iv[0] < self.b


def _pages(reel, seg):
    """Pages de sous-titres, meme decoupage que pages() de timeline.ts : [(debut, fin affichee, [(plan, indice)])]."""
    # pages calculees par timeline.ts lui-meme (montage.compute) : exactement celles de l'image ; sinon, ancien decoupage
    if isinstance(seg.get('pages'), list):
        return [(float(p['start']), float(p['end']), [(w['clip'], w['index']) for w in p['words']]) for p in seg['pages'] if p.get('words')]
    hide = {(c['id'], i): bool(w.get('hide')) for c in reel.get('clips') or [] for i, w in enumerate(c.get('words') or [])
            if isinstance(w, dict)}
    mw = (reel.get('style') or {}).get('maxWords')
    words = [w for w in seg.get('words') or [] if not hide.get((w['clip'], w['index'])) and str(w.get('w') or '').strip()]
    groupes, cur = [], []
    ouvrant = ''
    for w in words:
        p = cur[-1] if cur else None
        # ponctuation seule : jamais une page vide (comme pages() de timeline.ts) ; un signe ouvrant va au mot suivant
        if not re.sub(r'[,.;:…]+$', '', re.sub(r'[«»"“”]', '', str(w['w']))).strip():
            if re.match(r'^[«“(\[¿¡]', str(w['w']).strip()):
                ouvrant += str(w['w']).strip()
                continue
            if p and p['clip'] == w['clip']:
                cur[-1] = {**p, 'w': str(p['w']) + str(w['w']).strip(), 'end': max(p['end'], w['end'])}
                continue
        if ouvrant:
            w = {**w, 'w': ouvrant + str(w['w'])}
            ouvrant = ''
        if p and ((mw is not None and len(cur) >= mw) or re.search(r'[.!?…]["»”)\]]*$', str(p['w']))
                  or w['start'] - p['end'] > 0.35 or p['clip'] != w['clip']):
            groupes.append(cur)
            cur = []
        cur.append(w)
    if cur:
        groupes.append(cur)
    out = []
    for k, g in enumerate(groupes):
        fin = g[-1]['end']
        fin = min(groupes[k + 1][0]['start'], fin + TENUE) if k + 1 < len(groupes) else fin + TENUE_FIN
        out.append((float(g[0]['start']), float(fin), [(w['clip'], w['index']) for w in g]))
    return out


@contextmanager
def _ia(permise):
    """IA locale permise ou non pendant la passe (graphismes._ai ne regarde que llm.available())."""
    from . import llm
    if permise:
        yield
        return
    avant = llm.available
    llm.available = lambda: False
    try:
        yield
    finally:
        llm.available = avant


def _ia_possible(options):
    from . import llm
    if options.get('ia') is False or os.environ.get('EDITEUR_LLM', '1') == '0':
        return False
    try:
        return bool(llm.available())
    except Exception:
        return False


# ---------- les passes, limitees a la plage ----------
def _mots(reel, P, info):
    """Mots en couleur des pages entierement dans la plage (selection commune reel_highlights). Les mots hors plage
    comptent dans le budget sans changer ; les retouches a la main (difference avec hlAuto) sont gardees."""
    from .reel import DEFAULT_STYLE, _brands, _words_sig, idea_groups, reel_highlights, reel_language
    info['hl'] = {}
    if reel.get('aiMode') == 'suggestion':
        info['remarques'].append('Mode « suggestion » : les mots en couleur restent ceux que tu as choisis.')
        return
    clips = [c for c in reel.get('clips') or [] if isinstance(c.get('words'), list)]
    touches = {c['id'] for c in clips if P.eligibles.get(c['id'])}
    if not touches:
        return
    doc = reel.get('hlAuto') or {}
    keep, exclude, hints = {}, {}, {}
    for c in clips:
        if c['id'] not in touches:
            continue
        ws, e = c['words'], P.eligibles[c['id']]
        cur = {i for i, w in enumerate(ws) if isinstance(w, dict) and w.get('hl')}
        rec = doc.get(c['id'])
        valide = bool(rec) and rec.get('sig') == _words_sig(ws)
        if valide:
            was, off = set(rec.get('on') or []), set(rec.get('off') or [])
            k_in = (cur - was) & e                    # colores a la main dans la plage : gardes
            x_in = ((was - cur) | (off - cur)) & e    # decolores a la main : jamais repris
            hints[c['id']] = {i: 1.5 for i in cur & was & e}
        else:
            k_in, x_in = set(), set()                 # ancien montage sans historique : origine inconnue
            hints[c['id']] = {i: 1.0 for i in cur & e}
        # hors plage : les mots colores restent colores (et comptent dans le budget) ; une idee entierement hors plage
        # est deja decidee (ses mots sans couleur ne sont pas repris)
        dehors = set()
        for idee in idea_groups(ws):
            if not set(idee) & e:
                dehors |= {i for i in idee if i not in cur}
        keep[c['id']] = (cur - e) | k_in
        exclude[c['id']] = x_in | dehors
        info['hl'][c['id']] = {'valide': valide, 'rec': copy.deepcopy(rec), 'keep': k_in, 'exclude': x_in}
    lang = reel_language(reel)
    mw = (reel.get('style') or {}).get('maxWords') or DEFAULT_STYLE['maxWords']
    # cerveau Claude (resultat garde dans le reel) : ses mots forts passent d'abord sur les plans de la plage inchanges
    # depuis son appel (meme regle que reel.rehighlight) ; sans resultat utilisable, les regles choisissent seules
    force = None
    if reel.get('claude'):
        try:
            from . import cerveau_claude
            m = cerveau_claude.mots(reel)
            force = {k: v for k, v in m.items() if k in touches} if m is not None else None
        except Exception:
            force = None
    for cid in force or {}:
        hints.pop(cid, None)
    sel = reel_highlights(clips, mw, lang, only=touches, brands=_brands(reel), keep=keep, exclude=exclude, hints=hints,
                          force=force)
    for c in clips:
        if c['id'] in touches:
            on = set(sel.get(c['id']) or [])
            for i in P.eligibles[c['id']]:
                if i < len(c['words']) and isinstance(c['words'][i], dict):
                    c['words'][i]['hl'] = i in on


def _scenes(reel, use_ai, info):
    """Scenes du style recalculees (galerie + raisons du cerveau creatif) ; _garde ne garde que celles de la plage.
    galerie.prepare est appele sans plage : sa selection par plage utilise des temps approches (sans le resserrage) ;
    la selection exacte (temps de montage.compute) est faite ici."""
    design = reel.get('design') or {}
    if not design.get('mode') or design.get('enabled') is False:
        return
    from . import galerie
    galerie.prepare(reel, use_ai=use_ai)


def _graphismes(reel, rid, P, tpl, ai, info):
    """Graphismes proposes (chiffres dits, liste de benefices, mot choc, logo) recalcules sur le reel EN COURS ; seuls
    ceux entierement dans la plage remplacent les graphismes automatiques ou proposes de la plage."""
    from . import graphismes
    box = ROOT / 'runtime' / 'cache' / 'tmp' / f'passage-{os.getpid()}-{uuid.uuid4().hex[:8]}'
    (box / 'reels').mkdir(parents=True, exist_ok=True)
    try:
        montage.save(box, rid, reel)  # graphismes.suggest relit le reel sur le disque : copie du reel en cours
        with _ia(ai):
            found = graphismes.suggest(box, rid)
    finally:
        for f in (box / 'reels').glob('*'):
            f.unlink(missing_ok=True)
        (box / 'reels').rmdir()
        box.rmdir()
    auto_g = (tpl or {}).get('graphismes') == 'auto'
    # sans IA, la liste de benefices (proposee par l'IA seulement) n'est pas recalculee : on garde l'ancienne
    refaits = {'chiffre', 'motgeant', 'logo'} | ({'coches'} if ai else set())
    old = list(reel.get('graphics') or [])
    libres = [g for g in old if isinstance(g, dict) and P.dedans('graphics', g) and not verrous.protege(g)
              and (g.get('auto') or g.get('suggested')) and not g.get('generated') and g.get('kind') in refaits]
    gardes = [g for g in old if isinstance(g, dict) and not any(g is x for x in libres)]
    pris = {g.get('id') for g in old if isinstance(g, dict)}

    def meme(g, n):
        """Meme idee (meme genre, meme chiffre) a moins de 2,5 s (ecart de graphismes.suggest ; la relecture deplace
        un element d'au plus 1,5 s)."""
        if g.get('kind') != n['kind'] or abs(float(g.get('at') or 0) - n['at']) >= 2.5:
            return False
        return n['kind'] != 'chiffre' or (g.get('props') or {}).get('value') == (n.get('props') or {}).get('value')
    neufs, utilises = [], set()
    for n in sorted((g for g in found if P.dedans('graphics', g)), key=lambda g: g['at']):
        if any(meme(g, n) for g in gardes):
            continue  # deja la (a cheval sur une borne, verrouille, pose a la main...) : pas de doublon
        m = min((g for g in libres if id(g) not in utilises and meme(g, n)),
                key=lambda g: abs(float(g.get('at') or 0) - n['at']), default=None)
        if m is not None:
            utilises.add(id(m))
        # affiche seul : un style « graphismes auto » et une raison sure, ou un graphisme automatique deja affiche ici
        auto = (auto_g and n.get('confiance') == 'haute') or bool(m is not None and m.get('auto') and not m.get('suggested'))
        gid = m['id'] if m is not None else n['id']
        k = 2
        while m is None and gid in pris:
            gid = f"{n['id']}-p{k}"
            k += 1
        pris.add(gid)
        doc = {k2: v for k2, v in n.items() if k2 not in ('id', 'suggested', 'auto')}
        neufs.append({'id': gid, **doc, 'suggested': not auto, **({'auto': True} if auto else {})})
    reel['graphics'] = sorted([g for g in old if not any(g is x for x in libres)] + neufs,
                              key=lambda g: float(g.get('at') or 0) if isinstance(g, dict) else 0)
    if not reel['graphics'] and 'graphics' not in info['avant']:
        reel.pop('graphics', None)


def _sobriete(reel, tpl, seg, P, info):
    """Relecture limitee a la plage. Un element a cheval sur une borne est un obstacle fixe (verrou temporaire, remis
    tel quel par _garde) ; un element de la plage que la relecture pousserait hors de la plage redevient une
    proposition a sa place (rien ne deborde sur l'avant ni l'apres)."""
    from . import sobriete
    avant = {}
    for nom in ('graphics', 'broll', 'vectors'):
        for e in reel.get(nom) or []:
            if isinstance(e, dict) and not verrous.protege(e) and P.dedans(nom, e):
                avant[(nom, verrous.cle(e))] = (e.get('at'), e.get('duration'))
    temp = set()
    for nom in LISTES:
        for e in reel.get(nom) or []:
            if isinstance(e, dict) and not verrous.protege(e) and P.touche(nom, e) and not P.dedans(nom, e):
                e['locked'] = True
                temp.add((nom, verrous.cle(e)))
    try:
        rel = sobriete.relire(reel, tpl, seg, tout=False, plage=(P.a, P.b))
    finally:
        for nom in LISTES:
            for e in reel.get(nom) or []:
                if isinstance(e, dict) and (nom, verrous.cle(e)) in temp:
                    e.pop('locked', None)
    for nom in ('graphics', 'vectors'):
        for e in reel.get(nom) or []:
            k = (nom, verrous.cle(e))
            if k in avant and not P.dedans(nom, e):
                e['at'], e['duration'] = avant[k]
                if not e.get('suggested'):
                    e['suggested'] = True
                    e.pop('auto', None)
                    e['sobriete'] = 'il sortait du passage refait'
                    rel['retires'].append(f"{'Vecteur' if nom == 'vectors' else 'Graphisme'} à {_sec(float(e['at']))} : "
                                          'gardé en proposition (il sortait du passage refait).')
    for e in list(reel.get('broll') or []):
        k = ('broll', verrous.cle(e))
        if k in avant and not P.dedans('broll', e):
            reel['broll'] = [x for x in reel['broll'] if x is not e]
            at, d = avant[k]
            reel.setdefault('suggestions', {}).setdefault('broll', []).append(
                {**{x: v for x, v in e.items() if x != 'auto'}, 'at': at, 'duration': d, 'raison': 'il sortait du passage refait'})
            rel['retires'].append(f'Plan de coupe à {_sec(float(at))} : gardé en proposition (il sortait du passage refait).')
    # proposition de plan de coupe creee par la relecture : ramenee dans la plage si elle deborde
    anciens = {_cle_sug(x) for x in (info['avant'].get('suggestions') or {}).get('broll') or [] if isinstance(x, dict)}
    for s in (reel.get('suggestions') or {}).get('broll') or []:
        if isinstance(s, dict) and _cle_sug(s) not in anciens and not P.dedans('broll', s):
            d = float(s.get('duration') or 0)
            s['at'] = round(max(P.a, min(float(s.get('at') or 0), P.b - d)), 2)
    return rel


def _choregraphie(reel, tpl, P, info):
    """Mouvements de la plage : choregraphie.actualiser (agent choregraphie), puis retrait des mouvements libres de la
    plage dont l'element a disparu ou a ete retire par la relecture."""
    from . import choregraphie
    try:
        choregraphie.actualiser(reel, tpl, plage=(P.a, P.b))
    except NotImplementedError:
        pass
    except Exception as e:  # la choregraphie est un plus : le passage ne doit jamais en dependre
        info['remarques'].append(f'Chorégraphie non recalculée ({str(e)[:120]}).')
    ch = reel.get('choreography')
    if not isinstance(ch, dict) or verrous.is_locked(ch) or not isinstance(ch.get('cues'), list):
        return
    vivants = {
        'graphics': {g.get('id') for g in reel.get('graphics') or [] if isinstance(g, dict) and not g.get('suggested')},
        'broll': {b.get('id') for b in reel.get('broll') or [] if isinstance(b, dict)},
        'vector': {v.get('id') for v in reel.get('vectors') or [] if isinstance(v, dict) and not v.get('suggested')},
        'design': {s.get('id') for s in reel.get('styleScenes') or [] if isinstance(s, dict) and not s.get('hidden')},
    }

    def garde(c):
        if not isinstance(c, dict) or verrous.protege(c) or not P.dedans('cues', c):
            return True
        cible = c.get('cible') or {}
        return cible.get('type') not in vivants or cible.get('id') in vivants[cible.get('type')]
    ch['cues'] = [c for c in ch['cues'] if garde(c)]


# ---------- la garde : rien hors de la plage, rien de protege ----------
def _cle_sug(e):
    return f"{float(e.get('at') or 0):.2f}|{e.get('source')}|{e.get('word')}"


def _cle(nom, e):
    return _cle_sug(e) if nom == 'suggestions.broll' else verrous.cle(e)


def _fusion(nom, anciens, nouveaux, P, iv_nom=None):
    """Liste finale : un ancien element protege ou pas entierement dans la plage reste tel quel, a sa place ; seuls les
    elements libres entierement dans la plage viennent de la passe (inseres a leur temps). Un element refait
    identique garde son ancienne ecriture ET sa place dans la liste (une liste pas triee par temps — propositions
    ajoutees a la fin, element glisse dans la timeline — ne doit pas etre reecrite quand rien ne change)."""
    iv_nom = iv_nom or nom
    anciens = [e for e in anciens or []]
    fixes = [e for e in anciens if not isinstance(e, dict) or verrous.protege(e) or not P.dedans(iv_nom, e)]
    ids_fixes = {id(e) for e in fixes}
    cles_fixes = {_cle(nom, e) for e in fixes if isinstance(e, dict)}
    libres = {_cle(nom, e): e for e in anciens if id(e) not in ids_fixes}
    neufs, vus, identiques = [], set(), {}
    for e in nouveaux or []:
        if not isinstance(e, dict) or verrous.protege(e) or not P.dedans(iv_nom, e):
            continue
        k = _cle(nom, e)
        if k is not None and (k in cles_fixes or k in vus):
            continue
        vus.add(k)
        if k is not None and k in libres and libres[k] == e:
            identiques[k] = copy.deepcopy(libres[k])  # rien n'a change : il reste a sa place
        else:
            neufs.append(copy.deepcopy(e))
    out = []
    for e in anciens:
        if id(e) in ids_fixes:
            out.append(copy.deepcopy(e))
        elif _cle(nom, e) in identiques:
            out.append(identiques.pop(_cle(nom, e)))
    for e in sorted(neufs, key=lambda x: P.iv(iv_nom, x)[0]):
        t = P.iv(iv_nom, e)[0]
        pos = next((i for i, x in enumerate(out) if (P.iv(iv_nom, x) or (-1e9,))[0] > t), len(out))
        out.insert(pos, e)
    return out


def _garde(avant, reel, P, info):
    """Reel final construit a partir de l'original : seuls changent les elements libres entierement dans la plage
    (listes d'habillage, mots en couleur des pages de la plage, propositions de plans de coupe, mouvements, bruitages
    de la plage) et l'audit du storyboard des plans qui touchent la plage. Tout le reste est l'original."""
    out = copy.deepcopy(avant)
    for nom in LISTES:
        liste = _fusion(nom, avant.get(nom), reel.get(nom), P)
        if liste or nom in avant:
            out[nom] = liste
    # mots en couleur : seulement ceux des pages de la plage, jamais un plan verrouille
    neufs = {c['id']: c for c in reel.get('clips') or [] if isinstance(c, dict)}
    for c in out.get('clips') or []:
        n = neufs.get(c.get('id'))
        e = P.eligibles.get(c.get('id')) or set()
        if n is None or not e or verrous.is_locked(c):
            continue
        for i in e:
            if i < len(c['words']) and i < len(n.get('words') or []) and isinstance(c['words'][i], dict):
                hl = bool(n['words'][i].get('hl'))
                if bool(c['words'][i].get('hl')) != hl:
                    c['words'][i]['hl'] = hl
    _hlauto(out, avant, P, info)
    # propositions : seules celles des plans de coupe de la plage
    sug = reel.get('suggestions') or {}
    if 'broll' in sug or 'broll' in (avant.get('suggestions') or {}):
        liste = _fusion('suggestions.broll', (avant.get('suggestions') or {}).get('broll'), sug.get('broll'), P, 'broll')
        if liste or 'broll' in (avant.get('suggestions') or {}):
            out.setdefault('suggestions', {})['broll'] = liste
    # bruitages poses un par un : seuls ceux de la plage (aucune passe actuelle n'en pose, filet pour l'avenir)
    if isinstance(reel.get('sfx'), dict) and isinstance(avant.get('sfx'), dict):
        extra = _fusion('sfx', avant['sfx'].get('extra'), reel['sfx'].get('extra'), P)
        if extra or 'extra' in avant['sfx']:
            out['sfx']['extra'] = extra
    # choregraphie : un bloc verrouille ne bouge pas ; sinon seuls les mouvements de la plage
    ch_a, ch_n = avant.get('choreography'), reel.get('choreography')
    if not verrous.is_locked(ch_a) and isinstance(ch_n, dict):
        cues = _fusion('cues', (ch_a or {}).get('cues'), ch_n.get('cues'), P)
        if isinstance(ch_a, dict):
            out['choreography']['cues'] = cues
        elif cues:
            out['choreography'] = {**{k: v for k, v in ch_n.items() if k != 'cues'}, 'cues': cues}
    return out


def _audit(final, P):
    """Storyboard : l'audit (pret / planifie) des plans qui touchent la plage est refait sur le reel FINAL (meme regle
    que creative.direct_scenes, sur une copie) ; rien d'autre du plan creatif ne change, un plan verrouille non plus."""
    plan = final.get('creativePlan')
    if not isinstance(plan, dict) or verrous.is_locked(plan) or not plan.get('storyboard'):
        return
    from . import creative, galerie
    tmp = copy.deepcopy(final)
    creative.direct_scenes(tmp, tmp.get('styleScenes') or [], galerie._times(tmp))
    neufs = {s.get('id'): s for s in tmp['creativePlan'].get('storyboard') or [] if isinstance(s, dict)}
    for s in plan['storyboard']:
        n = neufs.get(s.get('id')) if isinstance(s, dict) else None
        if n is not None and P.touche('shots', s):
            for k in ('status', 'execution'):
                if k in n and n[k] != s.get(k):
                    s[k] = copy.deepcopy(n[k])


def _hlauto(out, avant, P, info):
    """Historique des mots en couleur (reel['hlAuto']) des plans touches : les mots hors plage gardent leur etat, ceux
    de la plage sont notes automatiques (sauf retouches a la main). Un plan sans historique valide n'en recoit pas."""
    from .reel import _words_sig
    for c in out.get('clips') or []:
        h = info.get('hl', {}).get(c.get('id'))
        if not h or not h['valide']:
            continue
        e = P.eligibles.get(c['id']) or set()
        rec = h['rec']
        was, off = set(rec.get('on') or []), set(rec.get('off') or [])
        hl = {i for i in e if i < len(c['words']) and isinstance(c['words'][i], dict) and c['words'][i].get('hl')}
        on = sorted((was - e) | (hl - h['keep']))
        off = sorted((off - e) | h['exclude'])
        if on != sorted(was) or off != sorted(set(rec.get('off') or [])):
            out['hlAuto'][c['id']] = {**rec, 'sig': _words_sig(c['words']), 'on': on, 'off': off}


# ---------- compte rendu ----------
def _nom_el(nom, e):
    if nom == 'graphics':
        p = e.get('props') or {}
        chiffre = f"{p.get('prefix') or ''}{p.get('value')}{p.get('suffix') or ''}" if 'value' in p else ''
        txt = str(p.get('title') or p.get('text') or f"{chiffre} {p.get('label') or ''}").strip()
        base = GRAPHISMES.get(e.get('kind'), 'Graphisme')
    elif nom == 'styleScenes':
        txt = str(e.get('text') or '').strip()
        base = SCENES.get(e.get('kind'), 'Élément du style')
    elif nom == 'vectors':
        txt = str(e.get('asset') or '').split('/')[-1].rsplit('.', 1)[0]
        base = 'Vecteur'
    else:
        txt = str(e.get('word') or '').strip()
        base = 'Plan de coupe'
    return base + (f' « {txt} »' if txt else '')


def _visible(nom, e):
    return not (e.get('hidden') if nom == 'styleScenes' else e.get('suggested'))


def _compte_rendu(avant, final, P, rel, info):
    changes, n = [], 0
    sug_neuves = [x for x in (final.get('suggestions') or {}).get('broll') or [] if isinstance(x, dict)
                  and x not in ((avant.get('suggestions') or {}).get('broll') or [])]
    for nom in LISTES:
        a = {verrous.cle(e): e for e in avant.get(nom) or [] if isinstance(e, dict)}
        b = {verrous.cle(e): e for e in final.get(nom) or [] if isinstance(e, dict)}
        ou = lambda e: f' à {_sec(P.iv(nom, e)[0])}' if P.iv(nom, e) else ''
        pourquoi = lambda e: f" ({e['sobriete']})" if e.get('sobriete') and not _visible(nom, e) else ''
        for k, e in b.items():
            if k not in a:
                n += 1
                etat = 'ajouté' if _visible(nom, e) else ('proposé, masqué' if nom == 'styleScenes' else 'proposé, à accepter si tu le veux')
                changes.append(f'{_nom_el(nom, e)}{ou(e)} : {etat}{pourquoi(e)}.')
            elif a[k] != e:
                n += 1
                va, vb = _visible(nom, a[k]), _visible(nom, e)
                etat = 'refait' if va == vb else ('affiché' if vb else ('masqué' if nom == 'styleScenes' else 'passé en proposition'))
                changes.append(f'{_nom_el(nom, e)}{ou(e)} : {etat}{pourquoi(e) if va != vb else ""}.')
        for k, e in a.items():
            if k not in b:
                n += 1
                s = next((x for x in sug_neuves if nom == 'broll' and x.get('source') == e.get('source')
                          and x.get('word') == e.get('word')), None)
                etat = (f"gardé en proposition ({s.get('raison')})" if s is not None and s.get('raison') else
                        'gardé en proposition' if s is not None else 'retiré (le moteur ne le propose plus ici)')
                changes.append(f'{_nom_el(nom, e)}{ou(e)} : {etat}.')
    plus, moins = [], []
    ca = {c['id']: c for c in avant.get('clips') or []}
    for c in final.get('clips') or []:
        o = ca.get(c['id'])
        for i in sorted(P.eligibles.get(c['id']) or ()):
            if o and i < len(c['words']) and bool(c['words'][i].get('hl')) != bool(o['words'][i].get('hl')):
                mot = str(c['words'][i].get('w') or '').strip(' ,.!?;:«»"').upper()
                (plus if c['words'][i].get('hl') else moins).append(mot)
    if plus or moins:
        n += 1
        parts = []
        if plus:
            parts.append(f"en couleur : {', '.join('« ' + m + ' »' for m in plus[:8])}{' …' if len(plus) > 8 else ''}")
        if moins:
            parts.append(f"sans couleur : {', '.join('« ' + m + ' »' for m in moins[:8])}{' …' if len(moins) > 8 else ''}")
        changes.append('Mots ' + ' ; '.join(parts) + '.')
    sa = {_cle_sug(x) for x in (avant.get('suggestions') or {}).get('broll') or [] if isinstance(x, dict)}
    sb = {_cle_sug(x) for x in (final.get('suggestions') or {}).get('broll') or [] if isinstance(x, dict)}
    # un plan de coupe retire par la relecture et range en proposition est deja dit plus haut
    retires = {(e.get('source'), e.get('word')) for e in avant.get('broll') or [] if isinstance(e, dict)
               and verrous.cle(e) not in {verrous.cle(x) for x in final.get('broll') or [] if isinstance(x, dict)}}
    sb -= {_cle_sug(x) for x in sug_neuves if (x.get('source'), x.get('word')) in retires}
    if sa != sb:
        n += 1
        changes.append(f'Propositions de plans de coupe du passage : {len(sb - sa)} nouvelle{_s(len(sb - sa))}, '
                       f'{len(sa - sb)} retirée{_s(len(sa - sb))}.')
    cues_a = ((avant.get('choreography') or {}).get('cues') or [])
    cues_b = ((final.get('choreography') or {}).get('cues') or [])
    if cues_a != cues_b:
        n += 1
        changes.append(f'Chorégraphie du passage recalculée ({len(cues_b)} mouvement{_s(len(cues_b))} en tout).')
    # deplacements et corrections de la relecture (les retraits sont deja dits element par element, avec leur raison)
    for phrase in (rel or {}).get('deplaces', []) + (rel or {}).get('corriges', []):
        changes.append(f'Relecture : {phrase}')
    return changes, n


def _relecture(rel, avant, final, P):
    """Phrases de la relecture qui decrivent un VRAI changement. La passe repart de la proposition du moteur (ex. un
    chiffre a 7,4 s, la ou il est dit) ; la relecture le remet alors la ou elle l'avait deja mis (8,7 s) : pour le
    monteur rien n'a bouge, et « déplacé de 7,4 s à 8,7 s » serait faux. Une phrase est gardee si un element qui a
    change (ajoute, retire ou modifie) est au temps qu'elle cite ; sans temps cite, si un element a change."""
    rel = dict(rel or {})
    temps, arrivees, chiffres = set(), set(), set()
    for nom in LISTES:
        a = {verrous.cle(e): e for e in avant.get(nom) or [] if isinstance(e, dict)}
        b = {verrous.cle(e): e for e in final.get(nom) or [] if isinstance(e, dict)}
        for k in set(a) | set(b):
            if a.get(k) == b.get(k):
                continue
            for e in (a.get(k), b.get(k)):
                iv = P.iv(nom, e) if e is not None else None
                if iv:
                    temps.add(_sec(iv[0]))
                    if e is b.get(k):
                        arrivees.add(_sec(iv[0]))  # place finale d'un element qui a change
                if e is not None and nom == 'graphics' and e.get('kind') == 'chiffre':
                    p = e.get('props') or {}
                    chiffres.add(f"{p.get('prefix') or ''}{p.get('value')}{p.get('suffix') or ''}")
    sa = [x for x in (avant.get('suggestions') or {}).get('broll') or [] if isinstance(x, dict)]
    for x in (final.get('suggestions') or {}).get('broll') or []:
        if isinstance(x, dict) and x not in sa and P.iv('broll', x):
            temps.add(_sec(P.iv('broll', x)[0]))

    def utile(phrase):
        m = re.match(r'Chiffre (.+?) : libellé', str(phrase))
        if m:
            return m.group(1) in chiffres
        m = re.search(r'déplacé de \d+,\d s à (\d+,\d s)', str(phrase))
        if m:  # un deplacement : l'element doit etre vraiment arrive la (ni deja la avant, ni remis a sa place)
            return m.group(1) in arrivees
        cites = set(re.findall(r'\d+,\d s', str(phrase)))
        return bool(cites & temps) if cites else bool(temps or chiffres)
    for k in ('retires', 'deplaces', 'corriges'):
        rel[k] = [x for x in rel.get(k) or [] if utile(x)]
    return rel


def _proteges(avant, P):
    """Elements verrouilles ou retouches qui touchent la plage, et elements a cheval sur une borne."""
    prot = cheval = 0
    for nom in LISTES:
        for e in avant.get(nom) or []:
            if isinstance(e, dict) and P.touche(nom, e):
                if verrous.protege(e):
                    prot += 1
                elif not P.dedans(nom, e):
                    cheval += 1
    for c in (avant.get('choreography') or {}).get('cues') or []:
        if isinstance(c, dict) and verrous.protege(c) and P.touche('cues', c):
            prot += 1
    for e in (avant.get('sfx') or {}).get('extra') or []:
        if isinstance(e, dict) and verrous.protege(e) and P.touche('sfx', e):
            prot += 1
    plans = sum(1 for c in avant.get('clips') or [] if verrous.is_locked(c)
                and any(P.a < P.temps.get((c['id'], i), -1) < P.b for i in range(len(c.get('words') or []))))
    return prot, cheval, plans


# ---------- version « avant » et ecriture ----------
def _version(project_dir, rid, brut):
    """Garde le reel d'avant dans versions/<reel>/ (meme format que le serveur : « AAAA-MM-JJTHH-MM-SS nom.json »).
    La route du serveur vient souvent d'enregistrer exactement le meme contenu : on la reprend, sans doublon."""
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', str(rid)):
        raise PassageInvalide('Identifiant de version invalide.')
    d = Path(project_dir) / 'versions' / str(rid)
    d.mkdir(parents=True, exist_ok=True)
    miennes = sorted(f for f in d.glob('*.json') if NOM_VERSION in f.name)
    if miennes and miennes[-1].read_bytes() == brut:
        return miennes[-1].name
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S')
    name = f'{stamp} {NOM_VERSION}.json'
    k = 2
    while (d / name).exists():
        name = f'{stamp} {NOM_VERSION} ({k}).json'
        k += 1
    tmp = d / f'{name}.{os.getpid()}.tmp'
    tmp.write_bytes(brut)
    os.replace(tmp, d / name)
    return name


def refaire(project_dir, rid, debut, fin, options=None):
    """Refait l'habillage automatique du passage [debut, fin] du reel ; rien avant, rien apres, rien de verrouille.
    options : {'ia': False} pour ne pas appeler l'IA locale (sinon comme un changement de style : EDITEUR_LLM=0 la
    coupe aussi). -> {'debut', 'fin', 'changes': [phrases], 'resume', 'modifie', 'version', 'proteges', 'ia'}"""
    options = options or {}
    rid = rid or 'script'
    verifier(debut, fin, math.inf)  # refus immediat (nombres, ordre, duree) avant tout calcul
    path = montage.reel_path(project_dir, rid)
    if not path.exists():
        raise PassageInvalide('Montage introuvable : ouvre la vidéo dans l\'éditeur, puis réessaie.')
    brut = path.read_bytes()
    reel = json.loads(brut.decode('utf-8'))
    avant = copy.deepcopy(reel)
    seg = montage.compute(reel)
    a, b, remarques = verifier(debut, fin, float(seg['duration']))
    P = _Plage(reel, seg, a, b)
    from . import sobriete
    tpl = sobriete._template(reel, None)
    ai = _ia_possible(options)
    info = {'avant': avant, 'remarques': remarques}
    rel = None
    with ExitStack() as pile:
        if ai:
            # une seule session de l'IA locale pour toute la passe (sinon elle demarrerait deux fois)
            from . import llm
            try:
                pile.enter_context(llm.session())
            except Exception as e:
                ai = False
                remarques.append(f'IA locale indisponible ({str(e)[:120]}).')
        with verrous.sous_protection(reel, (a, b), P.temps):
            _mots(reel, P, info)
            _scenes(reel, ai, info)
            _graphismes(reel, rid, P, tpl, ai, info)
            rel = _sobriete(reel, tpl, seg, P, info)
            _choregraphie(reel, tpl, P, info)
    final = _garde(avant, reel, P, info)
    rel = _relecture(rel, avant, final, P)
    changes, n = _compte_rendu(avant, final, P, rel, info)
    design = avant.get('design') or {}
    if n and design.get('mode') and design.get('enabled') is not False:
        _audit(final, P)  # comme apres la galerie : le storyboard dit ce qui execute maintenant chaque plan
    prot, cheval, plans = _proteges(avant, P)
    passage = f'Passage {_tc(a)} → {_tc(b)}'
    fixes = []
    if prot:
        fixes.append(f'{prot} élément{_s(prot)} verrouillé{_s(prot)} ou retouché{_s(prot)} laissé{_s(prot)} tel{_s(prot)} quel{_s(prot)}')
    if plans:
        fixes.append(f'{plans} plan{_s(plans)} verrouillé{_s(plans)} (mots figés)')
    if cheval:
        fixes.append(f'{cheval} élément{_s(cheval)} à cheval sur une borne laissé{_s(cheval)} tel{_s(cheval)} quel{_s(cheval)}')
    fin_phrase = ' Rien n\'a bougé avant ni après' + (f' ; {", ".join(fixes)}.' if fixes else '.')
    modifie = final != avant
    version = None
    if modifie:
        if not n:
            changes.append('Historique des mots en couleur mis à jour (tes retouches à la main y sont notées) : '
                           'rien de visible ne change.' if final.get('hlAuto') != avant.get('hlAuto') else
                           'Détails internes mis à jour (ordre, raisons, audit du plan créatif) : rien de visible ne change.')
        resume = (f'{passage} refait : {n} changement{_s(n)}.' if n else f'{passage} refait : aucun changement visible.') + fin_phrase
        final['sobriete'] = {'retires': list(rel.get('retires') or []), 'deplaces': list(rel.get('deplaces') or []),
                             'corriges': list(rel.get('corriges') or []), 'gardes': rel.get('gardes', 0), 'resume': resume}
        if path.read_bytes() != brut:
            raise PassageInvalide('Le montage a été modifié pendant le calcul (retouche dans l\'éditeur ?) : rien n\'a '
                                  'été changé. Relance « Refaire ce passage ».')
        version = _version(project_dir, rid, brut)
        montage.save(project_dir, rid, final)
    else:
        resume = f'{passage} : rien à changer, l\'habillage automatique est déjà à jour.{fin_phrase}'
    if not ai:
        remarques.append('IA locale non utilisée : règles seules (la liste de bénéfices n\'est pas recalculée).')
    if any(P.touche('broll', x) for x in list(avant.get('broll') or []) + list((avant.get('suggestions') or {}).get('broll') or [])):
        remarques.append('Plans de coupe : pas cherchés à nouveau ici (onglet Ajouter → Plans de coupe) ; '
                         'ceux du passage sont seulement relus.')
    return {'debut': a, 'fin': b, 'changes': changes, 'resume': resume, 'modifie': modifie, 'version': version,
            'proteges': prot, 'aCheval': cheval, 'ia': ai, 'remarques': remarques}


redo = refaire  # nom anglais (demande de la passation) ; la signature du SPEC reste refaire()
