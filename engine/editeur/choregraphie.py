"""Choregraphie V2 : la maniere dont chaque element entre et sort de l'image, decidee par le directeur creatif et
toujours modifiable (docs/direction-creative-v2/SPEC.md §2.6 et §9.4). MODULE DE L'AGENT « choregraphie ».

reel['choreography'] = {version, cues: [Cue], locked?, meta?} (voir remotion/src/types.ts). Un mouvement (cue) ne
decide que la MANIERE (type d'entree/sortie, direction, duree, courbe) et sa synchro ; le temps de l'element fait foi
(cue.at / cue.duree n'en sont qu'une copie pour la piste de la timeline).

Regles :
- a partir du plan creatif (temps narratifs, roles, rythme, storyboard), des mots dits (montage.compute) et, quand la
  musique est connue, de la grille de ses temps (librosa, en cache dans runtime/cache/battements) ;
- grammaire par role : accroche = net et rapide ; tension = glisse ; revelation = zoom doux / trace ; preuve = « pop »
  sobre ; demonstration = fondu ; appel a l'action = stable ;
- chaque mouvement a une raison en francais (role, mot ou temps musical qui le motive) ;
- sobriete : jamais deux entrees au meme moment (l'element le moins prioritaire garde son animation d'origine) ; rien
  de nouveau sur l'accroche sauf le bandeau ; on ne cree ni ne deplace aucun element ;
- verrous : un mouvement verrouille ou retouche (verrous.protege) n'est jamais recalcule ; choreography.locked = rien
  ne change ; un ancien reel sans choregraphie n'en recoit pas lors d'un changement de style (creer=False) ; un
  element VERROUILLE, ou un vecteur pose/retouche a la main (son animation est choisie dans son reglage), garde sa
  maniere d'entrer : son mouvement reste identique et l'IA ne lui en ajoute pas.
"""
import json
import math
import re
from pathlib import Path

from . import verrous
from .media import ROOT
from .script import normalize

VERSION = 1
MAX_CUES = 1000
ID_OK = re.compile(r'^[A-Za-z0-9_:.-]{1,120}$')   # meme regle que le serveur (V2_ID)
MARGE = 0.15          # deux entrees separees de moins de 0,15 s arrivent « en meme temps »
ENTREE_PROPRE = 0.3   # un element sans mouvement ajoute entre quand meme (animation d'origine) pendant ~0,3 s
FIN_VIDEO = 0.08      # un element qui dure jusqu'a la fin de la video n'a pas de sortie
CACHE = ROOT / 'runtime' / 'cache' / 'battements'

ROLES = {'accroche': 'Accroche', 'probleme': 'Tension', 'solution': 'Révélation', 'preuve': 'Preuve',
         'explication': 'Démonstration', 'cta': "Appel à l'action"}
RYTHME = {'nerveux': 0.8, 'progressif': 1.0, 'posé': 1.25, 'pose': 1.25}
PRIORITE = {'banner': 100, 'graphics': 80, 'design': 60, 'vector': 45, 'broll': 40, 'caption': 10}
NOMS_MOUV = {'fondu': 'en fondu', 'glisse': 'en glissé', 'zoom': 'en zoom', 'pop': 'en « pop »', 'trace': 'en tracé',
             'aucune': 'sans mouvement ajouté'}
DEPUIS = {'gauche': 'depuis la gauche', 'droite': 'depuis la droite', 'haut': 'depuis le haut', 'bas': 'depuis le bas'}
VERS = {'gauche': 'vers la gauche', 'droite': 'vers la droite', 'haut': 'vers le haut', 'bas': 'vers le bas'}
NOMBRES = {'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf', 'dix', 'onze', 'douze',
           'quinze', 'vingt', 'trente', 'quarante', 'cinquante', 'cent', 'cents', 'mille', 'million', 'millions',
           'fois', 'pourcent', 'moitie'}

# (type, direction, duree de base, courbe) ; direction None = choisie selon la place de l'element
BASE = {
    'accroche': (('glisse', 'haut', .28, 'rapide'), ('fondu', None, .2, 'rapide'),
                 "entrée nette et rapide : l'accroche claque sans voler le visage"),
    'probleme': (('glisse', None, .45, 'douce'), ('glisse', None, .35, 'douce'),
                 "la tension glisse sans à-coup : la friction devient concrète"),
    'solution': (('zoom', None, .4, 'douce'), ('fondu', None, .3, 'douce'),
                 "zoom doux : la réponse se révèle comme une découverte"),
    'preuve': (('pop', None, .35, 'rebond'), ('fondu', None, .25, 'douce'),
               "« pop » sobre : la preuve frappe au moment exact où elle est dite"),
    'explication': (('fondu', None, .35, 'douce'), ('fondu', None, .3, 'douce'),
                    "simple fondu : la personne reste au centre de l'explication"),
    'cta': (('fondu', None, .3, 'douce'), ('fondu', None, .3, 'douce'),
            "appel à l'action stable : un seul point focal, aucun mouvement de trop"),
}


# ---------- outils ----------
def _t(x):
    return f'{x:.1f}'.replace('.', ',') + ' s'


def _norm(w):
    return normalize(str(w or '')).strip("'")


def _tokens(texte):
    return {_norm(x) for x in re.split(r"[\s\-–—/,.;:!?«»\"()]+", str(texte or '')) if _norm(x)}


def _template(reel, template):
    from . import sobriete
    return sobriete._template(reel, template)


def _cle(cible):
    cible = cible or {}
    return f"{cible.get('type', '')}:{cible.get('id', '')}"


def _cue_id(typ, tid):
    base = re.sub(r'[^A-Za-z0-9_:.-]+', '_', f'cue-{typ}-{tid}')
    return base[:120]


def _touche(a, b, plage):
    return plage is None or (b > plage[0] and a < plage[1])


def _sous_assets(parts):
    """Fichier sous assets/ ou None. parts : morceaux du chemin, sans « . » ni « .. » ; un lecteur (« C:/… », « C:x »)
    ferait sortir de assets/ sous Windows : refuse. (Pas de resolve() : assets/ peut contenir des jonctions.)"""
    if not parts or any(':' in p for p in parts):
        return None
    return ROOT / 'assets' / Path(*parts)


_TRACE = {}
# dossiers des icones de la banque (ronde 4) : meme liste que ICON_DIRS de remotion/src/vectors.tsx
_ICONES = ('banque/icones/', 'banque/import/', 'banque/apercus/import/')
_RACINE_SVG = re.compile(r'<svg\b[^>]*>', re.I | re.S)
_TRAIT_RACINE = re.compile(r'\sstroke\s*=\s*["\']([^"\']*)["\']', re.I)


def _icone_au_trait(svg):
    """Icone dont la racine porte un trait (Lucide : stroke="currentColor") : prepareIcon trace alors chaque forme
    (prepareSvg tracerTout), meme regle que remotion/src/vectors.tsx. Une icone pleine ne se trace pas."""
    try:
        m = _RACINE_SVG.search(svg.read_text(encoding='utf-8', errors='ignore')[:20000])
    except Exception:
        return False
    s = _TRAIT_RACINE.search(m.group(0)) if m else None
    return bool(s and s.group(1).strip().lower() != 'none')


def _trace_possible(asset):
    """Le dessin du vecteur a-t-il des traits a tracer (classe v-trait) ? Fiche <nom>.json (« trace »), sinon le SVG.
    Icone de la banque : trait sur la racine du SVG (_icone_au_trait).
    Sans trait, un « trace » ne se dessinerait pas : l'element garderait son animation d'origine."""
    parts = [p for p in str(asset or '').replace('\\', '/').split('/') if p and p not in ('.', '..')]
    key = '/'.join(parts)
    if key not in _TRACE:
        svg = _sous_assets(parts) if parts else None
        ok = False
        if svg is not None and key.lower().endswith('.svg') and key.startswith(_ICONES):
            ok = _icone_au_trait(svg)
        elif svg is not None:
            try:
                fiche = json.loads(svg.with_suffix('.json').read_text(encoding='utf-8'))
                ok = bool(fiche.get('trace'))
            except Exception:
                try:
                    ok = 'v-trait' in svg.read_text(encoding='utf-8', errors='ignore')
                except Exception:
                    ok = False
        _TRACE[key] = ok
    return _TRACE[key]


def _gele(e):
    """Element dont la maniere d'entrer ne change plus : element VERROUILLE (cadenas), ou vecteur pose/retouche a la
    main (son animation d'entree et de sortie est choisie dans son reglage). Son mouvement libre est garde tel quel ;
    s'il n'en a pas, l'IA ne lui en ajoute pas."""
    obj = e.get('obj') if isinstance(e.get('obj'), dict) else {}
    return verrous.is_locked(obj) or (e['type'] == 'vector' and verrous.protege(obj))


def _lieux(reel, seg, elements=None):
    """Temps actuel de chaque cible (« type:id » -> (debut, fin)) : le temps de l'element fait foi, pas le cache du
    mouvement (cue.at), qui peut dater d'avant un deplacement."""
    out = {f"{e['type']}:{e['id']}": (e['at'], e['fin']) for e in (elements if elements is not None else cibles(reel, seg))}
    out.update({f"caption:{p['id']}": (p['start'], p['end']) for p in pages(reel, seg)})
    return out


# ---------- grille musicale ----------
def grille(fichier):
    """Temps de la musique (s dans le fichier) calcules une fois par librosa puis gardes en cache :
    {bpm, beats, duree, source} ; None si le fichier est absent ou illisible (la synchro se fait alors sur les mots)."""
    parts = [p for p in str(fichier or '').replace('\\', '/').split('/') if p and p not in ('.', '..')]
    if not parts:
        return None
    f = _sous_assets(parts)
    if f is None or not f.is_file():
        return None
    st = f.stat()
    nom = re.sub(r'[^A-Za-z0-9_.-]+', '_', '/'.join(parts)) + f'-{st.st_size}-{int(st.st_mtime)}.json'
    cache = CACHE / nom
    if cache.is_file():
        try:
            return json.loads(cache.read_text(encoding='utf-8'))
        except Exception:
            pass
    try:
        import librosa
        import numpy as np
        y, sr = librosa.load(str(f), sr=22050, mono=True, duration=240)
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units='time')
        duree = float(librosa.get_duration(path=str(f)))
        beats = [float(b) for b in beats]
        tempo = float(np.atleast_1d(tempo)[0]) if np.size(tempo) else 0.0
    except Exception as e:  # la musique est un plus : sans elle, les mouvements suivent les mots
        print(f'Temps de la musique introuvables ({e}).')
        return None
    if len(beats) >= 8:
        # intro sans pulsation detectee : la grille est prolongee vers le debut, a la meme cadence (piege de visuel.py)
        periode = float(np.median(np.diff(beats)))
        tete, t = [], beats[0] - periode
        while t > 0.05:
            tete.append(t)
            t -= periode
        beats = sorted(tete) + beats
    else:
        beats = []
    data = {'version': 1, 'fichier': '/'.join(parts), 'bpm': round(tempo, 1), 'beats': [round(b, 3) for b in beats],
            'duree': round(duree, 3), 'source': 'librosa'}
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data), encoding='utf-8')
    except Exception:
        pass
    return data


def _bpm_catalogue(reel):
    mood = (reel.get('music') or {}).get('mood')
    try:
        moods = json.loads((ROOT / 'styles' / 'musiques.json').read_text(encoding='utf-8'))
        return next((m.get('bpm') for m in moods if m.get('id') == mood), None)
    except Exception:
        return None


def battements(reel, total):
    """Temps de la musique dans le montage (la musique commence avec la video et boucle) -> (temps, info)."""
    m = reel.get('music') or {}
    if not m.get('enabled') or not m.get('file'):
        return [], None
    g = grille(m['file'])
    if not g or not g.get('beats'):
        return [], g
    beats = g['beats']
    duree = float(g.get('duree') or 0)
    tours = 1 if duree <= 1 or duree > 240 else min(60, int(math.ceil(total / duree)) + 1)
    out = []
    for k in range(tours):
        out += [b + k * duree for b in beats if b + k * duree <= total + 0.5]
    info = {'bpm': _bpm_catalogue(reel) or g.get('bpm'), 'source': g.get('source')}
    return sorted(set(round(b, 3) for b in out)), info


# ---------- elements du montage (meme logique d'affichage que Reel.tsx) ----------
def _affiche(w):
    """Texte affiche d'un mot (displayWord de timeline.ts) : vide pour une ponctuation seule."""
    return re.sub(r'[,.;:…]+$', '', re.sub(r'[«»"“”]', '', str(w or ''))).strip()


def pages(reel, seg):
    """Pages de sous-titres, comme pages() de timeline.ts : [{id, start, end, mots}] (id = « plan:indice » du 1er mot)."""
    # pages calculees par timeline.ts lui-meme (montage.compute) : exactement celles de l'image ; sinon, ancien decoupage
    if isinstance(seg.get('pages'), list):
        return [{'id': f"{p['words'][0]['clip']}:{p['words'][0]['index']}", 'start': p['start'], 'end': p['end'], 'mots': list(p['words'])}
                for p in seg['pages'] if p.get('words')]
    clips = {c['id']: c for c in reel.get('clips') or []}
    maxw = int((reel.get('style') or {}).get('maxWords') or 3)

    def cache(w):
        c = clips.get(w['clip'])
        try:
            return bool(c['words'][w['index']].get('hide'))
        except (TypeError, IndexError, KeyError):
            return False

    mots = [w for w in seg.get('words') or [] if not cache(w) and str(w.get('w') or '').strip()]
    out, cur = [], []

    def flush():
        if cur:
            out.append({'id': f"{cur[0]['clip']}:{cur[0]['index']}", 'start': cur[0]['start'], 'end': cur[-1]['end'], 'mots': list(cur)})
        cur.clear()

    ouvrant = ''
    for w in mots:
        prev = cur[-1] if cur else None
        # ponctuation seule : jamais une page vide (comme pages() de timeline.ts) ; un signe ouvrant (« “ ( [) va au mot
        # suivant, les autres au mot d'avant
        if not _affiche(w['w']):
            if re.match(r'^[«“(\[¿¡]', str(w['w']).strip()):
                ouvrant += str(w['w']).strip()
                continue
            if prev and prev['clip'] == w['clip']:
                cur[-1] = {**prev, 'w': prev['w'] + str(w['w']).strip(), 'end': max(prev['end'], w['end'])}
                continue
        if ouvrant:
            w = {**w, 'w': ouvrant + str(w['w'])}
            ouvrant = ''
        if prev and (len(cur) >= maxw or re.search(r'[.!?…]["»”)\]]*$', prev['w']) or w['start'] - prev['end'] > 0.35 or prev['clip'] != w['clip']):
            flush()
        cur.append(w)
    flush()
    for i, p in enumerate(out):
        nxt = out[i + 1] if i + 1 < len(out) else None
        p['end'] = min(nxt['start'], p['end'] + 0.6) if nxt else p['end'] + 0.4
    return out


def scenes(reel, seg):
    """Scenes du style affichees, comme designScenes() de timeline.ts : [(scene, at, end)]."""
    design = reel.get('design') or {}
    if design.get('enabled') is False or not design.get('mode'):
        return []
    clips = {c['id']: c for c in reel.get('clips') or []}
    total = float(seg['duration'])
    mots = {}
    for w in seg.get('words') or []:
        c = clips.get(w['clip'])
        try:
            if c['words'][w['index']].get('hide'):
                continue
        except (TypeError, IndexError, KeyError):
            pass
        mots.setdefault((w['clip'], w['index']), w)
    out = []
    for s in reel.get('styleScenes') or []:
        if not isinstance(s, dict) or s.get('hidden'):
            continue
        w = mots.get((s.get('clip'), s.get('index')))
        if not w:
            continue
        at = max(0.0, float(w['start']))
        end = min(total, at + max(0.2, float(s.get('duration') or 2.4)))
        if any(at < e + 0.5 and end > a for _, a, e in out):
            continue
        out.append((s, at, end))
    return out


def _texte_graphisme(g):
    p = g.get('props') or {}
    if 'value' in p:
        return f"{p.get('prefix') or ''}{p.get('value')}{p.get('suffix') or ''} {p.get('label') or ''}".strip()
    return str(p.get('text') or p.get('title') or ' '.join(p.get('items') or []) or '')


def _y_graphisme(g):
    p = g.get('props') or {}
    y = p.get('y')
    base = {'chiffre': .3, 'coches': .32, 'carte': .3, 'motgeant': .5, 'logo': .5}.get(g.get('kind'), .4)
    return float(y) + (.1 if g.get('kind') in ('coches', 'carte') else 0) if isinstance(y, (int, float)) else base


def cibles(reel, seg):
    """Elements par-dessus l'image qui peuvent recevoir un mouvement : [{type, id, at, fin, kind, texte, y, obj, mot}]."""
    total = float(seg['duration'])
    design = reel.get('design') or {}
    mode = design.get('mode') if design.get('enabled') is not False else None
    extras = not mode or design.get('suppressExtras') is False
    shots = (reel.get('creativePlan') or {}).get('storyboard') or []
    out = []

    def add(typ, obj, tid, at, fin, kind, texte, y, mot=None):
        out.append({'type': typ, 'id': str(tid), 'at': round(float(at), 3), 'fin': round(min(float(fin), total), 3),
                    'kind': kind, 'texte': texte, 'y': y, 'obj': obj, 'mot': mot})

    for g in reel.get('graphics') or []:
        if not isinstance(g, dict) or g.get('suggested') or g.get('id') is None:
            continue
        at, dur = float(g.get('at') or 0), float(g.get('duration') or 0)
        # un style immersif masque les graphismes, sauf la preuve decidee par le storyboard (meme regle que Reel.tsx)
        prevu = g.get('auto') and any(s.get('engine') == 'remotion-graphisme' and at < float(s.get('end', 0)) + .4
                                      and at + dur > float(s.get('start', 0)) - .3 for s in shots)
        # pose ou verrouille par le monteur : visible aussi dans un style immersif (Reel.tsx, userGraphic)
        if extras or prevu or verrous.protege(g):
            add('graphics', g, g['id'], at, at + dur, g.get('kind'), _texte_graphisme(g), _y_graphisme(g))
    if extras:
        for b in reel.get('broll') or []:
            if isinstance(b, dict) and b.get('id') is not None:
                at = float(b.get('at') or 0)
                add('broll', b, b['id'], at, at + float(b.get('duration') or 0), 'broll', b.get('word') or '', .5)
    if mode != 'editorial':
        for s, at, end in scenes(reel, seg):
            if s.get('id') is not None:
                mot = next((w for w in seg.get('words') or [] if w['clip'] == s.get('clip') and w['index'] == s.get('index')), None)
                add('design', s, s['id'], at, end, s.get('kind'), s.get('text') or '', float(s.get('y') if s.get('y') is not None else .5), mot)
    for v in reel.get('vectors') or []:
        if isinstance(v, dict) and not v.get('suggested') and v.get('id') is not None:
            at = float(v.get('at') or 0)
            add('vector', v, v['id'], at, at + float(v.get('duration') or 0), 'vector',
                str(v.get('asset') or '').split('/')[-1].rsplit('.', 1)[0], float(v.get('y') if v.get('y') is not None else .5))
            out[-1]['trace'] = _trace_possible(v.get('asset'))
    b = reel.get('banner') or {}
    if b.get('enabled') and str(b.get('text') or '').strip():
        end = b.get('end')
        add('banner', b, 'banner', float(b.get('start') or 0), float(end) if end is not None else total, 'banner',
            str(b.get('text') or ''), .15)
    return [e for e in out if e['fin'] > e['at']]


# ---------- decisions ----------
def _role(plan, rep, at, texte):
    """Role narratif de l'instant : temps du plan creatif, sinon reperes de la relecture (accroche, solution, CTA)."""
    beats = (plan or {}).get('beats') or []
    if beats:
        from .creative import beat_at
        b = beat_at(plan, at)
        if b:
            return b.get('role') or 'explication', b
    if at < rep['accroche']:
        return 'accroche', None
    if rep.get('cta') is not None and at >= rep['cta'] - .3:
        return 'cta', None
    if re.search(r'\d', str(texte or '')):
        return 'preuve', None
    if rep.get('solution') is not None and at >= rep['solution']:
        return 'solution', None
    return 'probleme', None


def _direction(y):
    return 'haut' if y < .4 else 'bas' if y > .6 else 'droite'


def _prise_gardee(role, shot):
    """Revelation ou demonstration que le storyboard confie a la prise originale (« preuve humaine ») : rien de gratuit."""
    return bool(shot) and shot.get('engine') == 'prise-originale' and role in ('solution', 'explication')


def _grammaire(role, e, shot):
    """-> (entree, sortie, pourquoi) pour cet element et ce role."""
    entree, sortie, pourquoi = BASE.get(role, BASE['explication'])
    typ, kind = e['type'], e.get('kind')
    if _prise_gardee(role, shot):
        # le storyboard garde la prise pour cette revelation (credibilite humaine) : l'element se fait discret
        entree, sortie = ('fondu', None, .35, 'douce'), ('fondu', None, .3, 'douce')
        pourquoi = "le storyboard garde ici la prise originale : mouvement minimal, le visage porte le propos"
    elif typ == 'banner':
        if role != 'accroche':
            entree, sortie, pourquoi = ('fondu', None, .3, 'douce'), ('fondu', None, .25, 'douce'), "bandeau discret hors de l'accroche"
    elif typ == 'broll':
        if role in ('solution', 'preuve'):
            entree, pourquoi = ('zoom', None, .35, 'douce'), "le plan de coupe s'installe par une légère poussée, comme une révélation"
        else:
            entree, pourquoi = ('fondu', None, .2, 'rapide'), "le plan de coupe arrive franc, comme une coupe"
        sortie = ('fondu', None, .2, 'rapide')
    elif typ == 'vector':
        # tracé seulement si le dessin a des traits (sinon il ne se dessinerait pas)
        if role == 'solution' and e.get('trace'):
            entree, pourquoi = ('trace', 'gauche', .6, 'douce'), "le tracé se dessine pendant que l'idée est expliquée"
    elif typ == 'design':
        if kind == 'notification' and role in ('probleme', 'solution', 'explication'):
            entree, sortie = ('glisse', 'haut', .4, 'douce'), ('glisse', 'haut', .3, 'douce')
            pourquoi = "la notification tombe du haut, comme sur un téléphone" + (" : la tension devient concrète" if role == 'probleme' else '')
        elif kind in ('flow', 'dashboard') and role in ('solution', 'explication'):
            entree, pourquoi = ('trace', 'gauche', .55, 'douce'), "le parcours se dessine dans le sens de la lecture, au rythme de l'explication"
        elif kind == 'metric':
            entree, pourquoi = ('pop', None, .35, 'rebond'), "le chiffre dit arrive en « pop » sobre pour que la preuve frappe"
        elif kind == 'comparison':
            entree = ('glisse', 'gauche', .45, 'douce')
        elif kind == 'keyword':
            entree = ('pop', None, .3, 'rapide')
        elif kind == 'cta':
            entree, sortie, pourquoi = ('fondu', None, .3, 'douce'), ('fondu', None, .3, 'douce'), "le bouton se pose en fondu et reste stable : une seule action"
    elif typ == 'graphics':
        if kind == 'chiffre' and role in ('preuve', 'solution'):
            entree, pourquoi = ('pop', None, .35, 'rebond'), "« pop » sobre : le chiffre frappe au moment exact où il est dit"
        elif kind == 'chiffre' and role == 'accroche':
            entree, pourquoi = ('zoom', None, .28, 'rapide'), "zoom net et rapide : le chiffre de l'accroche arrive d'un coup"
        elif kind == 'chiffre':
            entree, pourquoi = ('zoom', None, .35, 'douce'), "zoom sobre : le chiffre dit s'installe sans voler la phrase"
        elif kind == 'coches':
            entree, pourquoi = ('glisse', 'bas', .45, 'douce'), "la liste des bénéfices monte depuis le bas, sans cacher le visage"
        elif kind == 'carte':
            entree, pourquoi = ('fondu', None, .3, 'douce'), "la carte glisse déjà d'elle-même : un simple fondu suffit"
        elif kind == 'motgeant':
            entree, pourquoi = ('zoom', None, .25, 'rapide'), "le mot choc arrive en zoom vif"
        elif kind == 'logo':
            entree = ('fondu', None, .35, 'douce') if role == 'cta' else ('pop', None, .35, 'rebond')
    return entree, sortie, pourquoi


def _mot(mots, e):
    """Mot dit qui motive l'element : l'ancre de la scene, sinon le mot le plus proche du debut qui lui ressemble."""
    if e.get('mot'):
        return e['mot']
    at = e['at']
    cands = [w for w in mots if at - .35 <= w['start'] <= at + .6 and str(w.get('w') or '').strip()]
    if not cands:
        return None
    toks = _tokens(e.get('texte'))
    chiffre = bool(re.search(r'\d', str(e.get('texte') or '')))

    def score(w):
        n = _norm(w['w'])
        s = abs(w['start'] - at)
        if n and n in toks:
            s -= 1
        if chiffre and (re.search(r'\d', w['w']) or n in NOMBRES):
            s -= .6
        if w.get('hl'):
            s -= .3
        return s
    return min(cands, key=score)


def _mouvement(spec, direction_auto, echelle, room):
    typ, direction, base, courbe = spec
    if typ == 'aucune':
        return {'type': 'aucune', 'direction': None, 'duree': 0.0, 'courbe': 'lineaire'}
    if typ in ('glisse', 'trace') and not direction:
        direction = direction_auto
    duree = max(0.12, min(base * echelle, room))
    return {'type': typ, 'direction': direction if typ in ('glisse', 'trace') else None, 'duree': round(duree, 2), 'courbe': courbe}


def _proche(beats, lo, hi, cible=None):
    dedans = [b for b in beats if lo <= b <= hi]
    if not dedans:
        return None
    return min(dedans, key=lambda b: abs(b - cible)) if cible is not None else dedans[0]


def _synchro(e, entree, sortie, mot, beats, bpm):
    """Cale la fin de l'entree sur le mot (ou le temps de la musique) et le debut de la sortie sur un temps.
    -> (entree, sortie, sync, phrase, musique) ; musique : l'entree ou la sortie tombe sur un temps de la musique."""
    at, fin = e['at'], e['fin']
    dur = fin - at
    sync, phrase, musique = {'sur': 'temps', 'ref': None}, '', False
    if entree['type'] != 'aucune':
        base = entree['duree']
        hi = min(base * 1.6, .45 * dur, 1.2)
        lo = min(base * .6, hi)
        land = None
        if mot:
            sync = {'sur': 'mot', 'ref': f"{mot['clip']}:{mot['index']}"}
            mot_txt = str(mot['w']).strip(' ,.;:!?«»"')
            fin_mot = float(mot['end'])
            if lo <= fin_mot - at <= hi:
                land = fin_mot
                phrase = f"en place à la fin du mot « {mot_txt} » ({_t(fin_mot)})"
            else:
                phrase = f"lancée sur le mot « {mot_txt} » ({_t(float(mot['start']))})"
            b = _proche(beats, at + lo, at + hi, land if land is not None else at + base)
            if b is not None and abs(b - (land if land is not None else at + base)) <= .12:
                land = b
                musique = True
                phrase += ', pile sur un temps de la musique'
        elif beats:
            b = _proche(beats, at + lo, at + hi)
            if b is not None:
                land = b
                musique = True
                sync = {'sur': 'battement', 'ref': round(b, 3)}
                phrase = f"calée sur un temps de la musique ({_t(b)}{f', {bpm:g} BPM' if bpm else ''})"
        if land is not None:
            entree = {**entree, 'duree': round(max(.12, land - at), 2)}
        if not phrase:
            phrase = ("dès son apparition, avec la première phrase" if e['type'] == 'banner'
                      else "au début de l'élément (aucun mot précis ne le lance)")
    else:
        phrase = "animation d'origine seulement"
    if sortie['type'] != 'aucune' and beats:
        base = sortie['duree']
        hi = min(base * 1.6, .35 * dur, 1.0)
        lo = min(base * .6, hi)
        b = _proche(beats, fin - hi, fin - lo, fin - base)
        if b is not None:
            sortie = {**sortie, 'duree': round(max(.1, fin - b), 2)}
            musique = True
            phrase += ' ; sortie lancée sur un temps de la musique'
    return entree, sortie, sync, phrase, musique


def _fenetre(c, lieux=None):
    """Fenetre d'entree [debut, fin] d'un mouvement actif, ou None. lieux (_lieux) : l'entree part du temps ACTUEL de
    l'element (un mouvement garde tel quel a un cache « at » qui peut dater d'avant un deplacement) ; element absent =
    le mouvement ne s'applique pas (None)."""
    if not isinstance(c, dict) or c.get('desactive'):
        return None
    m = c.get('entree') or {}
    if m.get('type') in (None, 'aucune'):
        return None
    at = float(c.get('at') or 0)
    if lieux is not None:
        lieu = lieux.get(_cle(c.get('cible')))
        if lieu is None:
            return None
        at = float(lieu[0])
    return (at, at + max(.05, float(m.get('duree') or 0)))


def _conflit(w, occupe):
    return next((o for o in occupe if w[0] < o[1] + MARGE and w[1] > o[0] - MARGE), None)


def _libelle_court(e):
    noms = {'graphics': 'le graphisme', 'design': "l'élément du style", 'broll': 'le plan de coupe', 'vector': 'le vecteur',
            'caption': 'le sous-titre', 'banner': 'le bandeau'}
    return noms.get(e['type'], "l'élément")


def _rythme(plan, seg):
    r = ((plan or {}).get('direction') or {}).get('rhythm')
    if r in RYTHME:
        return r
    mots = [w for w in seg.get('words') or [] if str(w.get('w') or '').strip()]
    rate = len(mots) / max(1.0, float(seg['duration']))
    return 'nerveux' if rate >= 3.2 else 'posé' if rate < 2.15 else 'progressif'


def proposer(reel, seg, template=None, fixes=(), plage=None, rep=None):
    """Mouvements automatiques pour les elements actuels. fixes : mouvements gardes tels quels (verrouilles, retouches,
    hors de la plage) : ils comptent pour la sobriete et leur cible n'en recoit pas d'autre.
    -> (cues, stats)."""
    from . import sobriete
    tpl = template if isinstance(template, dict) else _template(reel, template)
    rep = rep or sobriete.reperes(reel, seg, sobriete.budget(tpl))
    total = float(seg['duration'])
    plan = reel.get('creativePlan') or {}
    shots = {s.get('beat'): s for s in plan.get('storyboard') or [] if isinstance(s, dict)}
    rythme = _rythme(plan, seg)
    echelle = RYTHME.get(rythme, 1.0)
    beats, info = battements(reel, total)
    bpm = (info or {}).get('bpm')
    mots = [w for w in seg.get('words') or [] if str(w.get('w') or '').strip()]
    elements = cibles(reel, seg)
    lieux = _lieux(reel, seg, elements)
    pris = {_cle(c.get('cible')): c for c in fixes}
    stats = {'accroche': 0, 'conflits': 0, 'mot': 0, 'battement': 0, 'temps': 0, 'musique': 0, 'invalides': 0,
             'sous_titres': 0, 'geles': 0, 'rythme': rythme, 'bpm': bpm if beats else None}
    # sobriete : entrees deja prises (mouvements gardes, au temps ACTUEL de leur element ; animations d'origine des
    # elements sans mouvement)
    occupe = [w for w in (_fenetre(c, lieux) for c in fixes) if w]
    candidats = []
    for e in elements:
        k = f"{e['type']}:{e['id']}"
        propre = (e['at'], e['at'] + ENTREE_PROPRE)
        if k in pris:
            if not _fenetre(pris[k], lieux):
                occupe.append(propre)  # mouvement garde mais sans entree : l'animation d'origine entre quand meme
            continue
        if _gele(e):
            # element verrouille / vecteur regle a la main : sa maniere d'entrer ne change pas (aucun mouvement ajoute)
            stats['geles'] += 1
            occupe.append(propre)
            continue
        if not ID_OK.match(e['id']):
            stats['invalides'] += 1
            occupe.append(propre)
            continue
        if plage is not None and not _touche(e['at'], e['fin'], plage):
            occupe.append(propre)
            continue
        if e['type'] != 'banner' and e['at'] < rep['accroche'] - .05:
            # rien de nouveau sur l'accroche sauf le bandeau : l'element garde son animation d'origine
            stats['accroche'] += 1
            occupe.append((e['at'], e['at'] + ENTREE_PROPRE))
            continue
        if e['at'] >= rep['fin']:
            continue  # carte de fin de la charte : rien ne bouge
        candidats.append(e)
    candidats.sort(key=lambda e: (-PRIORITE.get(e['type'], 20), e['at']))
    cues = []
    for e in candidats:
        role, beat = _role(plan, rep, e['at'], e['texte'])
        if e['type'] == 'banner' and e['at'] < rep['accroche']:
            role = 'accroche'
        shot = shots.get((beat or {}).get('id'))
        spec_in, spec_out, pourquoi = _grammaire(role, e, shot)
        dur = e['fin'] - e['at']
        dauto = _direction(e['y'])
        entree = _mouvement(spec_in, dauto, echelle, .4 * dur)
        sortie = _mouvement(spec_out, dauto, echelle, .3 * dur)
        if e['fin'] >= total - FIN_VIDEO or (role == 'cta' and e['fin'] >= rep['fin'] - FIN_VIDEO):
            sortie = _mouvement(('aucune', None, 0, 'lineaire'), dauto, echelle, 0)
        mot = _mot(mots, e) if e['type'] != 'banner' else None
        entree, sortie, sync, phrase, musique = _synchro(e, entree, sortie, mot, beats, bpm)
        cue = {'id': _cue_id(e['type'], e['id']), 'cible': {'type': e['type'], 'id': e['id']},
               'at': round(e['at'], 3), 'duree': round(dur, 3), 'entree': entree, 'sortie': sortie, 'sync': sync,
               'raison': '', 'auto': True, 'locked': False,
               'meta': {'role': role, **({'beat': beat['id']} if beat and beat.get('id') else {})}}
        w = _fenetre(cue)
        gene = _conflit(w, occupe) if w else None
        if gene:
            stats['conflits'] += 1
            cue['entree'] = {'type': 'aucune', 'direction': None, 'duree': 0.0, 'courbe': 'lineaire'}
            phrase = (f"entrée simplifiée : un autre élément entre au même moment ({_t(gene[0])}), "
                      f"{_libelle_court(e)} garde son animation d'origine")
            occupe.append((e['at'], e['at'] + ENTREE_PROPRE))
        elif w:
            occupe.append(w)
        detail = f"{NOMS_MOUV[cue['entree']['type']]}"
        if cue['entree'].get('direction'):
            detail += ' ' + DEPUIS[cue['entree']['direction']]
        if cue['entree']['type'] != 'aucune':
            detail += f" ({cue['entree']['duree']:.2f} s)".replace('.', ',')
        sortie_txt = '' if cue['sortie']['type'] == 'aucune' else f" Sortie {NOMS_MOUV[cue['sortie']['type']]}" + (
            f" {VERS[cue['sortie']['direction']]}" if cue['sortie'].get('direction') else '') + '.'
        cue['raison'] = f"{ROLES.get(role, 'Passage')} : entrée {detail}, {phrase}. {pourquoi[:1].upper()}{pourquoi[1:]}.{sortie_txt}"[:500]
        stats[cue['sync']['sur']] += 1
        stats['musique'] += bool(musique and not gene)
        cues.append(cue)
    caps, stats['sous_titres'] = _sous_titres(reel, seg, plan, rep, elements, occupe, pris, plage, beats, bpm)
    for c in caps:
        stats[c['sync']['sur']] += 1
        stats['musique'] += 'temps de la musique' in c['raison']
    cues += caps
    cues.sort(key=lambda c: (c['at'], c['id']))
    return cues, stats


def _sous_titres(reel, seg, plan, rep, elements, occupe, pris, plage, beats, bpm):
    """Mise en valeur des sous-titres, avec parcimonie : la page de la preuve (« pop ») et celle qui ouvre la
    revelation (zoom doux), seulement quand aucun autre element n'est a l'ecran. Au plus 3 par video."""
    design = reel.get('design') or {}
    mode = design.get('mode') if design.get('enabled') is not False else None
    if mode == 'editorial':
        return [], 0  # l'Editorial remplace les sous-titres par sa typographie
    shots = {s.get('beat'): s for s in (plan or {}).get('storyboard') or [] if isinstance(s, dict)}
    beats_plan = [b for b in (plan or {}).get('beats') or [] if b.get('role') in ('preuve', 'solution')
                  and not _prise_gardee(b.get('role'), shots.get(b.get('id')))]
    if not beats_plan:
        return [], 0
    visibles = [(e['at'], e['fin']) for e in elements]
    out = []
    faits = set()
    for p in pages(reel, seg):
        if len(out) >= 3:
            break
        if p['start'] < rep['accroche'] or f"caption:{p['id']}" in pris or not ID_OK.match(p['id']):
            continue
        if plage is not None and not _touche(p['start'], p['end'], plage):
            continue
        beat = next((b for b in beats_plan if b['start'] - .25 <= p['start'] <= b['end'] and b['id'] not in faits), None)
        if not beat:
            continue
        texte = ' '.join(w['w'] for w in p['mots'])
        fort = [w for w in p['mots'] if w.get('hl')]
        if beat['role'] == 'preuve' and not (re.search(r'\d', texte) or any(_norm(w['w']) in NOMBRES for w in p['mots'])):
            continue
        if beat['role'] == 'solution' and not fort:
            continue
        # un seul element a la fois : si un graphisme, une scene ou un plan de coupe est la, il porte deja le moment
        if any(a < p['end'] + .3 and f > p['start'] - .3 for a, f in visibles):
            continue
        preuve = beat['role'] == 'preuve'
        entree = {'type': 'pop' if preuve else 'zoom', 'direction': None, 'duree': .25 if preuve else .3,
                  'courbe': 'rapide' if preuve else 'douce'}
        w = (p['start'], p['start'] + entree['duree'])
        if _conflit(w, occupe):
            continue
        mot = fort[0] if fort else p['mots'][0]
        mot_txt = str(mot['w']).strip(' ,.;:!?«»"')
        sync = {'sur': 'mot', 'ref': f"{mot['clip']}:{mot['index']}"}
        phrase = f"sur le mot « {mot_txt} » ({_t(float(mot['start']))})"
        b = _proche(beats, w[1] - .1, w[1] + .1, w[1])
        if b is not None and b > p['start'] + .12:
            entree['duree'] = round(b - p['start'], 2)
            phrase += ', pile sur un temps de la musique'
        occupe.append((p['start'], p['start'] + entree['duree']))
        faits.add(beat['id'])
        pourquoi = ("la phrase de la preuve est mise en valeur par un « pop » discret" if preuve
                    else "la première phrase de la révélation s'ouvre en zoom doux")
        out.append({'id': _cue_id('caption', p['id']), 'cible': {'type': 'caption', 'id': p['id']},
                    'at': round(p['start'], 3), 'duree': round(p['end'] - p['start'], 3), 'entree': entree,
                    'sortie': {'type': 'aucune', 'direction': None, 'duree': 0.0, 'courbe': 'lineaire'}, 'sync': sync,
                    'raison': f"{ROLES[beat['role']]} : sous-titre {NOMS_MOUV[entree['type']]}, {phrase}. "
                              f"{pourquoi[:1].upper()}{pourquoi[1:]} ; aucun autre élément n'est à l'écran.",
                    'auto': True, 'locked': False, 'meta': {'role': beat['role'], 'beat': beat['id']}})
    return out, len(out)


def _resume(cues, fixes, stats):
    n = len(cues)
    auto = n - len(fixes)
    s = lambda k: '' if k == 1 else 's'
    detail = []
    if stats['mot']:
        detail.append(f"{stats['mot']} sur les mots")
    if stats.get('bpm'):
        detail.append(f"{stats['musique']} sur les temps de la musique ({stats['bpm']:g} BPM)")
    txt = f"{n} mouvement{s(n)} : {auto} proposé{s(auto)} par l'IA" + (f" ({', '.join(detail)})" if detail else '')
    if fixes:
        txt += f" ; {len(fixes)} gardé{s(len(fixes))} tel{s(len(fixes))} quel{s(len(fixes))} (verrouillé{s(len(fixes))}, retouché{s(len(fixes))} ou hors du passage)"
    if stats.get('geles'):
        g = stats['geles']
        txt += f" ; {g} élément{s(g)} verrouillé{s(g)} ou vecteur{s(g)} réglé{s(g)} à la main sans mouvement ajouté"
    if stats['conflits']:
        txt += f" ; {stats['conflits']} entrée{s(stats['conflits'])} simplifiée{s(stats['conflits'])} pour éviter deux entrées au même moment"
    txt += f". Rythme {stats['rythme']} ; rien sur l'accroche sauf le bandeau."
    return txt[:400]


def actualiser(reel, template=None, plage=None, creer=False):
    """Appele par reel.apply_template apres la relecture (et par passage.py avec plage) : recalcule les mouvements
    libres pour les elements actuels, garde les mouvements proteges (verrouilles ou retouches), retire les mouvements
    libres dont l'element n'existe plus. Modifie le reel sur place et renvoie reel['choreography'].
    - choreography.locked : rien ne change ;
    - reel sans choregraphie : rien n'est cree (ancien reel inchange), sauf creer=True (fin du montage automatique,
      bouton « Refaire la choregraphie ») ;
    - plage=(debut, fin) : seuls les mouvements libres dont l'element touche la plage sont recalcules."""
    ch = reel.get('choreography')
    if not isinstance(ch, dict):
        if not creer:
            return None
        ch = None
    if verrous.is_locked(ch):
        return ch
    from . import montage, sobriete
    seg = montage.compute(reel)
    tpl = _template(reel, template)
    rep = sobriete.reperes(reel, seg, sobriete.budget(tpl))
    anciens = [c for c in (ch or {}).get('cues') or [] if isinstance(c, dict)]
    proteges = [c for c in anciens if verrous.protege(c)]
    hors = []
    elements = cibles(reel, seg)
    lieux = _lieux(reel, seg, elements)
    geles = {f"{e['type']}:{e['id']}" for e in elements if _gele(e)}
    for c in anciens:
        if verrous.protege(c):
            continue
        if _cle(c.get('cible')) in geles:
            hors.append(c)  # element verrouille / vecteur regle a la main : son mouvement reste identique
            continue
        if plage is not None:
            a, b = lieux.get(_cle(c.get('cible')), (float(c.get('at') or 0), float(c.get('at') or 0) + float(c.get('duree') or 0)))
            if not _touche(a, b, plage):
                hors.append(c)  # hors du passage : identique, octet pour octet
    fixes = proteges + hors
    nouveaux, stats = proposer(reel, seg, tpl, fixes, plage, rep)
    cues = verrous.garder_cues(anciens, nouveaux + hors)
    cues.sort(key=lambda c: (float(c.get('at') or 0), str(c.get('id'))))
    out = {'version': VERSION, 'cues': cues[:MAX_CUES],
           'meta': {'resume': _resume(cues, fixes, stats), 'rythme': stats['rythme'],
                    **({'bpm': stats['bpm']} if stats.get('bpm') else {})}}
    reel['choreography'] = out
    return out


def regenerer(project_dir, rid='script', libres=True):
    """Tache de POST /api/reels/<p>/<v>/choregraphie : recalcule la choregraphie du reel et l'enregistre (montage.update,
    qui relit le reel juste avant d'ecrire). libres=True : seulement les mouvements non proteges ; libres=False (--tout) :
    les retouches aussi, JAMAIS les mouvements verrouilles. -> {'cues': n, 'resume': str}"""
    from . import montage
    res = {}

    def fn(reel):
        ch = reel.get('choreography')
        if verrous.is_locked(ch):
            res.update(cues=len(ch.get('cues') or []),
                       resume="La chorégraphie est verrouillée : rien n'a changé (déverrouille-la pour la refaire).")
            return
        if not libres and isinstance(ch, dict):
            # --tout : les retouches sont refaites, jamais un mouvement verrouille ni celui d'un element verrouille
            geles = {f"{e['type']}:{e['id']}" for e in cibles(reel, montage.compute(reel)) if _gele(e)}
            ch['cues'] = [c for c in ch.get('cues') or [] if isinstance(c, dict)
                          and (verrous.is_locked(c) or _cle(c.get('cible')) in geles)]
        # filet de securite : rien de ce qui est verrouille ou retouche ailleurs dans le reel ne bouge
        with verrous.sous_protection(reel):
            out = actualiser(reel, None, creer=True)
        res.update(cues=len(out['cues']), resume=out['meta']['resume'])

    montage.update(project_dir, rid, fn)
    return res


if __name__ == '__main__':
    import sys
    print('Utiliser : python -m editeur choregraphie <projet> --reel <id> [--tout]', file=sys.stderr)
