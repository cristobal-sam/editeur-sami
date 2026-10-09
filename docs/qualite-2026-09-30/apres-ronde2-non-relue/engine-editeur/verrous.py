"""Verrous V2 : ce que le monteur a verrouille ou retouche a la main n'est JAMAIS modifie par une passe automatique.

Regle unique pour tout le moteur (docs/direction-creative-v2/SPEC.md) :
- ``locked: true``  : verrouille par le monteur (cadenas de l'interface) ;
- ``manual: true`` (ou ``edited: true``, ancien nom des scenes du style) : retouche ou pose a la main ;
- protege = verrouille OU retouche : une passe automatique (changement de style, relecture de sobriete, galerie,
  IA, cerveau creatif, choregraphie, « Refaire ce passage ») ne le deplace pas, ne le modifie pas, ne le retire pas.
  Il compte quand meme pour les chevauchements : les elements automatiques s'ecartent de lui (sobriete).

Deux niveaux de protection :
1. chaque passe demande ``protege(element)`` avant de toucher un element (branche dans sobriete, galerie, reel,
   creative) ;
2. filet de securite ``sous_protection(reel)`` autour de chaque passe : les elements proteges sont photographies
   avant, puis remis EXACTEMENT a l'identique apres (meme si la passe les avait retires ou changes).
   Avec ``plage=(debut, fin)`` (« Refaire ce passage »), tout ce qui est hors de la plage est aussi remis a
   l'identique : rien ne bouge avant ni apres le passage.

Notes et dessins de revision (``notes``, ``annotations``) : jamais touches par une passe automatique.
Plan creatif, choregraphie, bandeau : proteges en bloc quand ils portent ``locked: true``.
"""
import copy
from contextlib import contextmanager

# listes d'elements poses sur l'image, identifies par « id »
COLLECTIONS = ('graphics', 'broll', 'styleScenes', 'vectors')
# champs de revision : jamais modifies par une passe automatique
REVISION = ('notes', 'annotations')
# blocs proteges en entier quand ils portent locked: true
BLOCS = ('creativePlan', 'choreography', 'banner')
# champs d'un mot remis a l'identique hors de la plage (« Refaire ce passage »)
MOT = ('w', 'hl', 'hide', 'cut')
_ABSENT = object()


def is_locked(e):
    """Verrouille par le monteur (cadenas)."""
    return isinstance(e, dict) and bool(e.get('locked'))


def is_manual(e):
    """Pose ou retouche a la main (manual ; edited = ancien nom pour les scenes du style)."""
    return isinstance(e, dict) and bool(e.get('manual') or e.get('edited'))


def protege(e):
    """Aucune passe automatique ne doit modifier, deplacer ni retirer cet element."""
    return is_locked(e) or is_manual(e)


def modifiable(e, auto=False):
    """Une passe automatique peut-elle modifier ou retirer cet element ? auto : l'element est-il automatique (chaque
    passe a sa regle : scene du style = automatique par defaut, graphisme = si auto/generated...)."""
    return bool(auto) and not protege(e)


def partager(items):
    """-> (proteges, libres) en gardant l'ordre."""
    items = list(items or [])
    return [e for e in items if protege(e)], [e for e in items if not protege(e)]


def cle(e):
    """Identifiant stable d'un element : son id, sinon (bruitage sans id) « t|nom »."""
    if not isinstance(e, dict):
        return None
    if e.get('id') is not None:
        return str(e['id'])
    if 't' in e and 'name' in e:
        return f"{float(e['t']):.3f}|{e['name']}"
    return None


def fusionner(anciens, nouveaux):
    """Resultat d'une passe qui recalcule une liste : les anciens elements proteges sont gardes tels quels ; un nouvel
    element qui porte le meme identifiant qu'un protege est ecarte (le protege gagne). Les anciens libres sont remplaces
    par les nouveaux."""
    gardes = [copy.deepcopy(e) for e in anciens or [] if protege(e)]
    pris = {cle(e) for e in gardes}
    return [e for e in nouveaux or [] if cle(e) not in pris] + gardes


def garder_cues(anciens, nouveaux):
    """Choregraphie recalculee : cues verrouilles/retouches gardes ; un nouveau cue qui vise la meme cible qu'un cue
    protege (ou porte son id) est ecarte."""
    gardes = [copy.deepcopy(c) for c in anciens or [] if protege(c)]
    ids = {c.get('id') for c in gardes}
    cibles = {(c.get('cible') or {}).get('type', '') + ':' + str((c.get('cible') or {}).get('id', '')) for c in gardes}
    libres = [c for c in nouveaux or [] if c.get('id') not in ids
              and (c.get('cible') or {}).get('type', '') + ':' + str((c.get('cible') or {}).get('id', '')) not in cibles]
    return libres + gardes


def plan_verrouille(reel):
    return is_locked(reel.get('creativePlan'))


def choregraphie_verrouillee(reel):
    return is_locked(reel.get('choreography'))


# ---------- filet de securite ----------
def _dans(a, b, plage):
    """L'intervalle [a, b] touche-t-il la plage [debut, fin] ?"""
    return plage is None or (b > plage[0] and a < plage[1])


def _temps_mots(reel):
    """{(plan, indice): temps du montage} de chaque mot garde (meme calcul que l'apercu, via montage.compute)."""
    from . import montage
    try:
        seg = montage.compute(reel)
    except Exception:
        return {}
    return {(w['clip'], w['index']): float(w['start']) for w in seg.get('words') or []}


def _intervalle(nom, e, temps):
    """Temps du montage [debut, fin] d'un element, ou None si inconnu."""
    if nom == 'styleScenes':
        t = temps.get((e.get('clip'), e.get('index')))
        return None if t is None else (t, t + float(e.get('duration') or 2.4))
    if nom == 'cues':
        at = e.get('at')
        return None if at is None else (float(at), float(at) + float(e.get('duree') or 0))
    if nom == 'sfx':
        return (float(e.get('t') or 0), float(e.get('t') or 0) + 0.5)
    if e.get('at') is None:
        return None
    return float(e['at']), float(e['at']) + float(e.get('duration') or 0)


def instantane(reel, plage=None, temps=None):
    """Photographie de tout ce qu'une passe automatique n'a pas le droit de changer. plage : (debut, fin) du montage,
    tout ce qui est hors de la plage est aussi photographie ; temps : {(plan, indice): t} (calcule si besoin)."""
    reel = reel or {}
    if plage is not None and temps is None:
        temps = _temps_mots(reel)
    temps = temps or {}

    def garder(nom, e):
        if protege(e):
            return True
        if plage is None:
            return False
        iv = _intervalle(nom, e, temps)
        return iv is not None and not _dans(iv[0], iv[1], plage)

    snap = {'plage': plage, 'entiers': {}, 'listes': {}, 'sfx': [], 'cues': [], 'mots': {}, 'revision': {}}
    for k in REVISION:
        # aucune passe ne lit les notes ni les dessins : on garde la reference (pas de copie de milliers de points)
        snap['revision'][k] = reel.get(k, _ABSENT)
    for k in BLOCS:
        if is_locked(reel.get(k)):
            snap['entiers'][k] = copy.deepcopy(reel[k])
    for nom in COLLECTIONS:
        snap['listes'][nom] = [copy.deepcopy(e) for e in reel.get(nom) or [] if isinstance(e, dict) and garder(nom, e)]
    snap['sfx'] = [copy.deepcopy(e) for e in (reel.get('sfx') or {}).get('extra') or [] if isinstance(e, dict) and garder('sfx', e)]
    ch = reel.get('choreography') or {}
    if not is_locked(ch):
        snap['cues'] = [copy.deepcopy(c) for c in ch.get('cues') or [] if isinstance(c, dict) and garder('cues', c)]
    for c in reel.get('clips') or []:
        if is_locked(c):
            # plan verrouille : mots en couleur, masques et emojis figes
            snap['mots'][c['id']] = {'tout': True, 'sig': c.get('signature'), 'source': c.get('source'),
                                     'words': copy.deepcopy(c.get('words')), 'emojis': copy.deepcopy(c.get('emojis'))}
        elif plage is not None:
            hors = {i: {k: w[k] for k in MOT if k in w} for i, w in enumerate(c.get('words') or [])
                    if (c['id'], i) in temps and not _dans(temps[(c['id'], i)], temps[(c['id'], i)] + 0.05, plage)}
            emo = [copy.deepcopy(p) for p in c.get('emojis') or []
                   if (c['id'], p[0]) in temps and not _dans(temps[(c['id'], p[0])], temps[(c['id'], p[0])] + 0.05, plage)]
            dedans = {i for i in range(len(c.get('words') or [])) if i not in hors}
            snap['mots'][c['id']] = {'tout': False, 'sig': c.get('signature'), 'source': c.get('source'),
                                     'words': hors, 'emojis': emo, 'dedans': dedans}
            if not dedans and c['id'] in (reel.get('hlAuto') or {}):
                # plan entierement hors du passage : son historique de mots en couleur ne bouge pas non plus
                snap.setdefault('hlAuto', {})[c['id']] = copy.deepcopy(reel['hlAuto'][c['id']])
    return snap


def _remettre(items, gardes):
    """Remet chaque element garde a sa place (meme id) ou a la fin s'il a disparu."""
    items = list(items or [])
    pos = {cle(e): i for i, e in enumerate(items) if isinstance(e, dict)}
    for g in gardes:
        k = cle(g)
        if k in pos:
            items[pos[k]] = copy.deepcopy(g)
        else:
            items.append(copy.deepcopy(g))
            pos[k] = len(items) - 1
    return items


def restaurer(reel, snap):
    """Remet dans le reel tout ce que l'instantane protege. -> liste lisible de ce qui a du etre remis."""
    remis = []
    for k, v in snap['revision'].items():
        if v is _ABSENT:
            if k in reel:
                reel.pop(k)
                remis.append(k)
        elif reel.get(k) is not v:
            reel[k] = v
            remis.append(k)
    for k, v in snap['entiers'].items():
        if reel.get(k) != v:
            remis.append(k)
            reel[k] = copy.deepcopy(v)
    for nom, gardes in snap['listes'].items():
        if not gardes:
            continue
        avant = reel.get(nom)
        reel[nom] = _remettre(avant, gardes)
        if avant != reel[nom]:
            remis.append(nom)
        if nom in ('graphics', 'broll', 'vectors'):
            reel[nom].sort(key=lambda e: float(e.get('at') or 0))
    if snap['sfx']:
        sfx = reel.setdefault('sfx', {'enabled': True, 'transition': None, 'highlight': None, 'highlightGap': 4,
                                      'cta': None, 'start': None, 'volume': 0.6})
        avant = sfx.get('extra')
        sfx['extra'] = _remettre(avant, snap['sfx'])
        if avant != sfx['extra']:
            remis.append('sfx.extra')
    if snap['cues'] and not is_locked(reel.get('choreography')):
        ch = reel.setdefault('choreography', {'version': 1, 'cues': []})
        avant = ch.get('cues')
        ch['cues'] = _remettre(avant, snap['cues'])
        if avant != ch['cues']:
            remis.append('choreography.cues')
    by_id = {c['id']: c for c in reel.get('clips') or []}
    for cid, m in snap['mots'].items():
        c = by_id.get(cid)
        if c is None or c.get('source') != m['source'] or c.get('signature') != m['sig']:
            continue  # autre prise ou autres coupes : les anciens mots ne correspondent plus a ce plan
        if m['tout']:
            if c.get('words') != m['words'] or c.get('emojis') != m['emojis']:
                remis.append(f'plan {cid}')
            c['words'], c['emojis'] = copy.deepcopy(m['words']), copy.deepcopy(m['emojis'])
            continue
        for i, w in m['words'].items():
            if i < len(c.get('words') or []):
                mot = c['words'][i]
                if any(mot.get(k, _ABSENT) != w.get(k, _ABSENT) for k in MOT):
                    remis.append(f'mot {cid}/{i}')
                for k in MOT:
                    if k in w:
                        mot[k] = w[k]
                    else:
                        mot.pop(k, None)
        # emojis : ceux hors de la plage sont remis, ceux de la plage viennent de la passe
        dedans = [p for p in c.get('emojis') or [] if p[0] in m['dedans']]
        emojis = sorted(copy.deepcopy(m['emojis']) + dedans, key=lambda p: p[0])
        if emojis != (c.get('emojis') or []):
            remis.append(f'emojis {cid}')
        if emojis or 'emojis' in c:
            c['emojis'] = emojis
    for cid, h in (snap.get('hlAuto') or {}).items():
        reel.setdefault('hlAuto', {})[cid] = copy.deepcopy(h)
    return remis


@contextmanager
def sous_protection(reel, plage=None, temps=None):
    """Execute une passe automatique sans jamais perdre ce qui est protege (verrouille, retouche, revision) ni, avec
    plage, ce qui est hors du passage. Usage : ``with verrous.sous_protection(reel): passe(reel)``."""
    snap = instantane(reel, plage, temps)
    try:
        yield snap
    finally:
        snap['remis'] = restaurer(reel, snap)
