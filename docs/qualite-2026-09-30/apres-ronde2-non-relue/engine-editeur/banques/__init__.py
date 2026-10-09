"""Recherche de medias externes (banques d'images et de videos libres) : UN service pour tout l'editeur.

  realisateur IA / recherche manuelle -> search() -> fournisseurs actifs (Pixabay, Pexels...) -> resultats
  au format commun (metadonnees + apercus : rien n'est telecharge) -> rank() -> choix -> download() (seulement
  le media retenu, une seule fois, avec sa fiche de licence) -> plan de coupe du reel (broll.add_asset).

Les cles sont lues dans les variables d'environnement, ou a defaut dans cles-api.env (racine de l'editeur).
Elles ne sortent jamais de ce module : ni interface, ni journal, ni cache."""
import hashlib
import json
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..media import ROOT
from .base import BanqueErreur, Indisponible, LimiteAtteinte, NonConfiguree, orientation
from .http import CACHE, Http, read_counter, write_json
from .pexels import PexelsProvider
from .pixabay import PixabayProvider

FOURNISSEURS = (PixabayProvider, PexelsProvider)  # ordre de preference ; ajouter une banque = une ligne ici
CLES = ROOT / 'cles-api.env'
BIBLIO = ROOT / 'media/broll/banques'  # medias retenus : font aussi partie de la bibliotheque media/broll
TTL = 24 * 3600  # Pixabay : resultats en cache 24 h (et liens valables 24 h)

__all__ = ['BanqueErreur', 'NonConfiguree', 'LimiteAtteinte', 'Indisponible', 'providers', 'active', 'statut', 'search',
           'gather', 'get_asset', 'download', 'cached_file', 'rank', 'queries_for', 'phrase_at', 'for_sentence']


# ---------- Fournisseurs et cles ----------
def _load_keys():
    """cles-api.env : lignes NOM_API_KEY=valeur ; une variable d'environnement deja definie a priorite."""
    if not CLES.exists():
        return
    for line in CLES.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = (x.strip() for x in line.split('=', 1))
        v = v.strip('"\'')
        if k.endswith('_API_KEY') and v and not os.environ.get(k):
            os.environ[k] = v


_instances = None


def providers():
    global _instances
    if _instances is None:
        _load_keys()
        _instances = []
        for cls in FOURNISSEURS:
            http = Http(cls.id)
            p = cls(http)
            http.secret = lambda p=p: p.key
            _instances.append(p)
    return _instances


def active(kind=None):
    return [p for p in providers() if p.active() and (kind is None or kind in p.types)]


def get_provider(pid):
    p = next((x for x in providers() if x.id == pid), None)
    if p is None:
        raise BanqueErreur('Banque inconnue.')
    if not p.active():
        raise NonConfiguree(f'{p.name} : aucune cle dans cles-api.env.')
    return p


def statut():
    """Etat des banques pour l'interface (jamais la cle)."""
    counter = read_counter()
    files = [f for f in BIBLIO.rglob('*') if f.is_file() and f.suffix.lower() not in ('.json', '.part')] if BIBLIO.exists() else []
    return {'fournisseurs': [{'id': p.id, 'nom': p.name, 'actif': p.active(), 'types': list(p.types),
                              'requetes': {k: v for k, v in counter.get(p.id, {}).items() if k in ('aujourdhui', 'ce_mois', 'restant', 'limite')}}
                             for p in providers()],
            'actif': bool(active()), 'fichierCles': CLES.name, 'bibliotheque': len(files)}


# ---------- Recherche (metadonnees et apercus seulement) ----------
def _norm_query(q):
    return ' '.join(str(q).split())[:100]


def _read(f):
    """Fichier de cache : illisible (coupure, disque plein) -> efface et ignore."""
    try:
        return json.loads(Path(f).read_text(encoding='utf-8'))
    except (ValueError, OSError):
        Path(f).unlink(missing_ok=True)
        return None


def _cached_search(p, query, kind, o):
    api = {k: o[k] for k in ('orientation', 'page', 'per_page', 'min_width', 'min_height', 'lang', 'video_type') if o.get(k)}
    if kind == 'video' and not getattr(p, 'video_orientation', True):
        api.pop('orientation', None)  # filtre fait apres coup : une seule requete pour toutes les orientations
    key = hashlib.sha1(json.dumps([p.id, kind, query.lower(), api], sort_keys=True).encode()).hexdigest()[:20]
    f = CACHE / 'recherches' / p.id / f'{key}.json'
    if f.exists() and time.time() - f.stat().st_mtime < TTL:
        cached = _read(f)
        if cached is not None:
            return cached, True
    res = (p.search_videos if kind == 'video' else p.search_images)(query, api)
    write_json(f, res)
    for a in res:  # fiche de chaque media : l'ajouter ensuite ne coute aucune requete (24 h)
        write_json(CACHE / 'medias' / f"{a['provider']}-{a['type']}-{a['id']}.json", a)
    return res, False


def _keep(a, o):
    """Filtres de l'interface : orientation, duree, qualite (la banque ne les propose pas toutes)."""
    if o.get('orientation') and a['orientation'] != o['orientation']:
        return False
    d = a.get('duration')
    if d is not None:
        if o.get('min_duration') and d < float(o['min_duration']):
            return False
        if o.get('max_duration') and d > float(o['max_duration']):
            return False
    if o.get('min_short') and min(a['width'], a['height']) < int(o['min_short']):
        return False
    return True


def _interleave(lists):
    """Resultats de plusieurs banques melanges a tour de role (chacune garde son ordre de pertinence)."""
    out, seen = [], set()
    for i in range(max((len(x) for x in lists), default=0)):
        for x in lists:
            if i < len(x) and (x[i]['provider'], x[i]['id']) not in seen:
                seen.add((x[i]['provider'], x[i]['id']))
                out.append(x[i])
    return out


def search(query, kind='video', options=None, provider=None):
    """Recherche dans les banques actives (ou une seule). Rien n'est telecharge ; cache 24 h."""
    o = dict(options or {})
    query = _norm_query(query)
    if not query:
        return {'resultats': [], 'erreurs': [], 'cache': True}
    if kind not in ('video', 'image'):
        raise BanqueErreur('Type de media inconnu.')
    targets = [get_provider(provider)] if provider else active(kind)
    if not targets:
        raise NonConfiguree('Aucune banque configuree : colle ta cle dans cles-api.env (voir README).')
    if o.get('orientation') and kind == 'video':
        # l'orientation est filtree apres coup pour les videos : on en demande plus
        o['per_page'] = max(int(o.get('per_page') or 20), 60)
    # lang='auto' (recherche tapee a la main) : on cherche en francais ET en anglais (« argent » vs « money »)
    langs = ['fr', 'en'] if o.get('lang') == 'auto' else [o.get('lang') or 'en']
    lists, errors, failures, cached = [], [], [], True
    for p in targets:
        for lang in langs:
            try:
                res, hit = _cached_search(p, query, kind, {**o, 'lang': lang})
                cached = cached and hit
                lists.append(res)
            except BanqueErreur as e:
                errors.append(f'{p.name} : {e}')
                failures.append(e)
                break
    if not lists and failures:
        # toutes les banques ont echoue : on garde la nature de l'erreur (limite, cle refusee, reseau)
        raise type(failures[0])(' ; '.join(errors))
    return {'resultats': [a for a in _interleave(lists) if _keep(a, o)], 'erreurs': errors, 'cache': cached}


def gather(queries, kind='video', lang='en', per_query=15, limit=40):
    """Plusieurs requetes (de la plus precise a la plus generale) -> candidats uniques, avec la requete d'origine."""
    out, seen = [], set()
    for rank_q, q in enumerate(queries):
        try:
            res = search(q, kind, {'per_page': per_query, 'lang': lang})['resultats']
        except (LimiteAtteinte, NonConfiguree, Indisponible):
            raise  # inutile d'essayer les requetes suivantes (hors connexion, limite, cle)
        except BanqueErreur as e:
            print(f'Banque : {e}')
            continue
        for i, a in enumerate(res):
            k = (a['provider'], a['id'])
            if k in seen:
                continue
            seen.add(k)
            out.append({**a, 'query': q, '_prior': 1.0 - 0.12 * rank_q - 0.015 * i})
        if len(out) >= limit:
            break
    return out[:limit]


def get_asset(pid, asset_id, kind):
    """Fiche d'un media : cache (24 h) sinon la banque."""
    f = CACHE / 'medias' / f'{pid}-{kind}-{asset_id}.json'
    if f.exists() and time.time() - f.stat().st_mtime < TTL:
        cached = _read(f)
        if cached is not None:
            return cached
    a = get_provider(pid).get_asset(asset_id, kind)
    write_json(f, a)
    return a


# ---------- Telechargement du media retenu (une seule fois) ----------
def _stem(pid, asset_id, kind):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', str(asset_id)) or not re.fullmatch(r'[a-z0-9]{1,20}', str(pid)):
        raise BanqueErreur('Identifiant de media invalide.')
    return f'{pid}-{kind}-{asset_id}'


def cached_file(pid, asset_id, kind):
    folder = BIBLIO / pid
    if not folder.exists():
        return None
    return next((f for f in sorted(folder.glob(_stem(pid, asset_id, kind) + '.*')) if f.suffix.lower() not in ('.json', '.part')), None)


def download(pid, asset_id, kind='video', quality='auto', target=(1080, 1920), query=''):
    """Telecharge le media retenu dans media/broll/banques/<banque>/ + sa fiche (.json : source, auteur, licence,
    requete, date). Deja telecharge : rien n'est refait."""
    existing = cached_file(pid, asset_id, kind)
    if existing:
        meta_file = existing.with_suffix('.json')
        return existing, ((_read(meta_file) or {}) if meta_file.exists() else {})
    p = get_provider(pid)
    a = get_asset(pid, asset_id, kind)
    f = p.pick_file(a, quality, target)
    ext = '.mp4' if kind == 'video' else ('.' + f['url'].split('?')[0].rsplit('.', 1)[-1].lower())
    if ext not in ('.mp4', '.jpg', '.jpeg', '.png', '.webp'):
        ext = '.mp4' if kind == 'video' else '.jpg'
    dest = BIBLIO / pid / f'{_stem(pid, asset_id, kind)}{ext}'
    try:
        f = p.download_asset(a, quality, dest, target)
    except (Indisponible, LimiteAtteinte):
        raise  # reseau coupe : redemander la fiche ne servirait a rien
    except BanqueErreur:
        # lien expire (plus de 24 h) : on redemande la fiche a la banque, une fois
        a = p.get_asset(asset_id, kind)
        write_json(CACHE / 'medias' / f'{pid}-{kind}-{asset_id}.json', a)
        f = p.download_asset(a, quality, dest, target)
    meta = {**p.get_metadata(a), 'provider': pid, 'asset_id': str(asset_id), 'file': dest.name,
            'rendition': {k: f[k] for k in ('name', 'width', 'height')}, 'query': query,
            'downloaded_at': time.strftime('%Y-%m-%d %H:%M:%S'), 'size': dest.stat().st_size}
    write_json(dest.with_suffix('.json'), meta, indent=1)
    return dest, meta


# ---------- Classement des candidats ----------
# Preferences par style de montage : mouvement vise (0 fixe .. 1 tres dynamique), animations acceptees
STYLE_PREFS = {
    'defaut': {'motion': 0.4, 'animation': False},
    'reel-impact': {'motion': 0.55, 'animation': False},
    'reel-karaoke': {'motion': 0.5, 'animation': False},
    'motivation-geant': {'motion': 0.6, 'animation': False},
    'pub-premium': {'motion': 0.3, 'animation': False},
    'minimal-propre': {'motion': 0.25, 'animation': False},
    'ugc-naturel': {'motion': 0.4, 'animation': False},
    'podcast-clip': {'motion': 0.35, 'animation': False},
    'immobilier': {'motion': 0.3, 'animation': False},
    'evenement': {'motion': 0.5, 'animation': False},
}
NEGATIVES = ['a picture with big text, letters or a watermark', 'a blurry, low quality picture',
             'a cartoon, an illustration or a 3d animation']


def _clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def _effective(a):
    """Taille du media optimise (1080 px sur le petit cote au plus ; image fixe : 2160 px au plus)."""
    w, h = a['width'], a['height']
    if not w or not h:
        return 0, 0
    k = min(1.0, 1080 / min(w, h)) if a['type'] == 'video' else min(1.0, 2160 / max(w, h))
    return w * k, h * k


def display_mode(W, H, w, h):
    """Meme regle que brollMode (remotion/src/timeline.ts) : un media d'une autre orientation que le montage
    passe en plan de coupe encadre (moitie droite) au lieu d'un plein ecran tres recadre."""
    target = orientation(W, H)
    return 'encadre' if target != 'carre' and orientation(w, h) != target else 'plein'


def _box(W, H, mode):
    """Surface du plan de coupe dans l'image (insetBox de timeline.ts pour 'encadre')."""
    if mode != 'encadre':
        return W, H
    return (W * 0.56, H * 0.52) if H > W * 1.05 else (W * 0.4, H * 0.8)


def _scores_meta(a, W, H, need, prefs):
    """Criteres sans image : orientation, agrandissement a l'export, duree, qualite (popularite), style."""
    target, o = orientation(W, H), a['orientation']
    mode = display_mode(W, H, a['width'], a['height'])
    # autre orientation : le plan est encadre (net, entier) ; un peu moins bien qu'un plein ecran natif
    orient = 1.0 if o == target else 0.85 if mode == 'encadre' else 0.7
    w, h = _effective(a)
    bw, bh = _box(W, H, mode)
    up = max(bw / w, bh / h) if w and h else 9
    res = 1.0 if up <= 1.05 else 0.8 if up <= 1.35 else 0.55 if up <= 1.8 else 0.3
    d = a.get('duration')
    dur = 1.0 if d is None or d >= need + 0.6 else 0.7 if d >= need else 0.15
    stats = a.get('stats') or {}
    pop = _clamp(math.log10(1 + stats['downloads']) / 5) if stats.get('downloads') else 0.4
    quality = 0.5 + 0.5 * pop
    style = 0.5 if (stats.get('kind') == 'animation' and not prefs['animation']) else 1.0
    return {'orient': orient, 'res': res, 'dur': dur, 'quality': quality, 'style': style, 'upscale': round(up, 2), 'mode': mode}


def _tag_relevance(a, terms):
    if not terms:
        return 0.0
    words = {w for t in a.get('tags', []) for w in re.findall(r'[a-z]+', t.lower())}
    words |= {w[:-1] for w in words if w.endswith('s')}
    hits = sum(1 for t in terms if t in words or t.rstrip('s') in words)
    return _clamp(hits / min(3, len(terms)))


def _fetch_previews(assets, video=False):
    """Vignettes (et petites videos d'apercu) en cache 24 h pour l'analyse ; en parallele."""
    def one(a):
        p = next((x for x in providers() if x.id == a['provider']), None)
        url = a.get('previewVideo') if video else a.get('preview')
        if not p or not url:
            return None
        ext = '.mp4' if video else '.jpg'
        try:
            return p.http.fetch(url, p.hosts, CACHE / 'apercus' / f"{a['provider']}-{a['type']}-{a['id']}{'-apercu' if video else ''}{ext}")
        except BanqueErreur as e:
            print(f'Apercu indisponible ({e}).')
            return None
    with ThreadPoolExecutor(8) as ex:
        return list(ex.map(one, assets))


def _motion_frames(path, duration):
    """Deux rafales de 3 images (a 30 % et 70 %) : mouvement moyen + images pour CLIP."""
    import numpy as np
    from .. import media
    frames, diffs = [], []
    d = max(1.0, float(duration or 4))
    for pos in (0.3, 0.7):
        try:
            burst = media.sample_frames(path, fps=10, width=224, start=max(0.0, d * pos), duration=0.25)
        except Exception:
            continue
        if not burst:
            continue
        frames.append(burst[0][1])
        gray = [f.mean(axis=2)[::4, ::4] for _, f in burst]
        diffs += [float(np.abs(b - a).mean()) / 255 for a, b in zip(gray, gray[1:])]
    motion = _clamp((sum(diffs) / len(diffs)) / 0.06) if diffs else None
    return frames, motion


def rank(assets, context, analyse_top=0):
    """Classe des candidats (tous fournisseurs) pour un emplacement du montage.
    context : queries, description (anglais), target (W, H), need (s), style, llm (bool).
    Chaque candidat recoit score (0-1), relevance, confidence (haute/moyenne/faible), reasons, auto, start."""
    if not assets:
        return []
    W, H = context.get('target') or (1080, 1920)
    need = float(context.get('need') or 2.0)
    prefs = STYLE_PREFS.get(context.get('style') or '', STYLE_PREFS['defaut'])
    queries = [q for q in context.get('queries', []) if q]
    terms = {w for q in queries for w in re.findall(r'[a-z]+', q.lower()) if len(w) > 2}
    for a in assets:
        a['_meta'] = _scores_meta(a, W, H, need, prefs)
        a['_tags'] = _tag_relevance(a, terms)
        m = a['_meta']
        a['_pre'] = 0.45 * a.get('_prior', 0.5) + 0.3 * a['_tags'] + 0.1 * m['orient'] + 0.1 * m['res'] + 0.05 * m['dur']
    assets = sorted(assets, key=lambda a: -a['_pre'])[:12]  # vignettes analysees : 12 au plus

    texts = [context['description']] if context.get('description') else []
    texts += [f'a photo of {q}' for q in queries[:4]]
    clip_ok = False
    try:
        import torch
        from PIL import Image
        from .. import search as clipsearch
        model, prep, tok, dev = clipsearch._model()
        thumbs = _fetch_previews(assets)
        with torch.no_grad():
            tq = model.encode_text(tok(texts + NEGATIVES).to(dev)).float()
            tq = tq / tq.norm(dim=-1, keepdim=True)
            npos = len(texts)

            def embed(images):
                x = torch.stack([prep(im) for im in images]).to(dev)
                e = model.encode_image(x).float()
                e = e / e.norm(dim=-1, keepdim=True)
                e = e.mean(0, keepdim=True)
                return e / e.norm(dim=-1, keepdim=True)

            for a, th in zip(assets, thumbs):
                if th is None or not texts:
                    continue
                try:
                    a['_emb'] = embed([Image.open(th).convert('RGB')])
                except Exception:
                    continue
            # analyse des meilleurs : petite video d'apercu -> mouvement + images en plus pour CLIP
            if analyse_top:
                def sim_of(a):
                    return float((a['_emb'] @ tq[:npos].T).max()) if '_emb' in a else 0.0
                best = sorted([a for a in assets if a['type'] == 'video' and '_emb' in a], key=lambda a: -(sim_of(a) + 0.2 * a['_pre']))[:analyse_top]
                clips = _fetch_previews(best, video=True)
                for a, path in zip(best, clips):
                    if path is None:
                        continue
                    frames, motion = _motion_frames(path, a.get('duration'))
                    a['_motion'] = motion
                    if frames:
                        e = embed([Image.fromarray(f) for f in frames])
                        both = a['_emb'] + e
                        a['_emb'] = both / both.norm(dim=-1, keepdim=True)
                        # debut du plan : l'image la plus proche du texte
                        sims = [float((embed([Image.fromarray(f)]) @ tq[:npos].T).max()) for f in frames]
                        pos = (0.3, 0.7)[max(range(len(sims)), key=lambda i: sims[i])] if len(sims) == 2 else 0.3
                        a['_start'] = float(a.get('duration') or 4) * pos - 0.3
            for a in assets:
                if '_emb' not in a:
                    continue
                sims = (a['_emb'] @ tq.T)[0]
                a['_clip'] = float(sims[:npos].max())
                logits = 100 * sims
                pos_logit = float(logits[:npos].max())
                neg = [float(x) for x in logits[npos:]]
                # probleme evident : texte/filigrane, flou, dessin anime (si le style n'en veut pas)
                checks = neg if not prefs['animation'] else neg[:2]
                a['_probleme'] = next((NEGATIVES[i] for i, v in enumerate(checks) if 1 / (1 + math.exp(pos_logit - v)) > 0.85), None)
        clip_ok = True
    except Exception as e:
        print(f'Analyse des images indisponible ({e}) : classement sur les mots-cles.')

    out = []
    for a in assets:
        m = a['_meta']
        if clip_ok and '_clip' in a:
            relevance = 0.7 * _clamp((a['_clip'] - 0.18) / 0.14) + 0.3 * a['_tags']
        else:
            relevance = 0.6 * a['_tags'] + 0.3 * _clamp(a.get('_prior', 0.5))
        motion = a.get('_motion')
        mscore = 0.7 if motion is None else 1 - abs(motion - prefs['motion']) / max(prefs['motion'], 1 - prefs['motion'])
        score = (0.52 * relevance + 0.14 * m['orient'] + 0.12 * m['res'] + 0.08 * m['dur'] + 0.06 * m['quality']
                 + 0.05 * mscore + 0.03 * m['style'])
        if relevance < 0.25:
            score *= 0.6
        problem = a.get('_probleme')
        haute = (score >= 0.72 and relevance >= 0.6 and m['orient'] >= 0.85 and m['res'] >= 0.8 and m['dur'] >= 0.7
                 and not problem and motion is not None and context.get('llm', True))
        confidence = 'haute' if haute else 'moyenne' if score >= 0.52 and relevance >= 0.4 else 'faible'
        reasons = ['très pertinent' if relevance >= 0.65 else 'pertinent' if relevance >= 0.4 else 'peu pertinent',
                   {'portrait': 'vertical', 'paysage': 'horizontal', 'carre': 'carré'}[a['orientation']]
                   + (' (encadré)' if m['mode'] == 'encadre' else '' if m['orient'] == 1.0 else ' (recadré)'),
                   a['quality'] + ('' if m['res'] >= 0.8 else ' (agrandi)')]
        if a.get('duration') is not None:
            reasons.append(f"{a['duration']} s" if m['dur'] >= 0.7 else f"trop court ({a['duration']} s)")
        if motion is not None:
            reasons.append('plan fixe' if motion < 0.12 else 'mouvement doux' if motion < 0.45 else 'dynamique')
        if problem:
            reasons.append({NEGATIVES[0]: 'texte ou filigrane possible', NEGATIVES[1]: 'flou possible',
                            NEGATIVES[2]: 'dessin animé'}[problem])
        d = float(a.get('duration') or 0)
        start = a.get('_start', 0.5)
        start = round(_clamp(start, 0.0, max(0.0, d - need - 0.1)), 2) if d else 0.0
        clean = {k: v for k, v in a.items() if not k.startswith('_')}
        out.append({**clean, 'score': round(score, 3), 'relevance': round(relevance, 3), 'confidence': confidence,
                    'reasons': reasons, 'auto': haute, 'start': start, 'mode': m['mode'],
                    'detail': {**m, 'clip': round(a.get('_clip', 0), 3), 'tags': round(a['_tags'], 2),
                               'motion': None if motion is None else round(motion, 2)}})
    return sorted(out, key=lambda c: -c['score'])


# ---------- Realisateur IA : quelles images pour quelle phrase ----------
SYSTEM = ("Tu es un monteur video expert en reels publicitaires francophones (Quebec) et en banques de videos libres. "
          "Tu reponds uniquement en JSON valide, sans commentaire.")
EXEMPLES = ('« J\'ai gagne 10 000 dollars » -> ["counting cash", "money", "business success"] ; '
            '« Je travaille depuis mon telephone » -> ["smartphone work", "texting", "phone office"] ; '
            '« On part en voyage » -> ["airport", "airplane window", "travel"]')


def _fallback_queries(text):
    """Sans IA locale : les mots forts de la phrase, cherches en francais (la banque traduit)."""
    from ..reel import STOP
    from ..script import tokens
    words = [w for w in tokens(text) if len(w) >= 5 and w not in STOP]
    return {'illustrable': bool(words), 'queries': list(dict.fromkeys(sorted(words, key=len, reverse=True)))[:3],
            'description': text, 'lang': 'fr', 'llm': False}


def queries_for(items):
    """items = [{'text', 'context'}] -> [{'illustrable', 'queries' (2-5, anglais, du precis au general),
    'description' (anglais, pour CLIP), 'lang', 'llm'}] en un seul appel a l'IA locale."""
    from .. import llm
    if not items:
        return []
    if llm.available():
        lines = '\n'.join(f'[{i}] « {it["text"]} »' + (f' (contexte : {it["context"]})' if it.get('context') else '')
                          for i, it in enumerate(items))
        user = ("Voici des phrases dites dans une video. Pour chacune, propose des recherches de plans de coupe (B-roll) "
                "dans une banque de videos libres.\n" + lines + "\n\nReponds avec cet objet JSON :\n"
                '{"plans": [{"i": 0, "illustrable": true, "requetes": ["2 a 5 recherches EN ANGLAIS de 1 a 3 mots, '
                'de la plus precise a la plus generale"], "description": "une phrase en anglais decrivant l\'image ideale"}]}\n'
                "Regles : des choses concretes et filmables (objets, lieux, gestes, personnes en action), jamais des idees "
                "abstraites ; pas de texte, de logo ni de marque ; illustrable = false si la phrase ne gagne rien a etre "
                f"illustree (salutation, transition). Exemples : {EXEMPLES}.")
        try:
            with llm.session():
                data = llm.ask_json(SYSTEM, user, temperature=0.2, max_tokens=300 + 160 * len(items))
            plans = {int(p.get('i', k)): p for k, p in enumerate(data.get('plans') or []) if isinstance(p, dict)}
            out = []
            for i, it in enumerate(items):
                p = plans.get(i) or {}
                rq = p.get('requetes')
                rq = [rq] if isinstance(rq, str) else rq if isinstance(rq, list) else []
                qs = [' '.join(str(q).split())[:60] for q in rq if len(str(q).strip()) >= 3][:5]
                ill = p.get('illustrable', True)
                ill = ill.strip().lower() not in ('false', '0', 'non', 'no') if isinstance(ill, str) else bool(ill)
                if not qs:
                    out.append(_fallback_queries(it['text']))
                    continue
                out.append({'illustrable': ill, 'queries': qs,
                            'description': str(p.get('description') or qs[0])[:200], 'lang': 'en', 'llm': True})
            return out
        except Exception as e:
            print(f'IA locale indisponible ({e}) : recherche sur les mots de la phrase.')
    return [_fallback_queries(it['text']) for it in items]


def phrase_at(words, t):
    """Phrase du montage a l'instant t : [{'w', 'start', 'end'}] (temps du montage) -> {text, start, end}."""
    groups, cur = [], []
    for k, w in enumerate(words):
        cur.append(w)
        nxt = words[k + 1] if k + 1 < len(words) else None
        if re.search(r'[.!?…]$', w['w'].strip()) or nxt is None or nxt['start'] - w['end'] > 0.6:
            groups.append(cur)
            cur = []
    if not groups:
        return None
    best = min(groups, key=lambda g: 0 if g[0]['start'] - 0.3 <= t <= g[-1]['end'] + 0.3 else min(abs(t - g[0]['start']), abs(t - g[-1]['end'])))
    i = groups.index(best)
    ctx = ' '.join(w['w'] for g in groups[max(0, i - 1):i] + groups[i + 1:i + 2] for w in g)
    return {'text': ' '.join(w['w'] for w in best), 'start': round(best[0]['start'], 2), 'end': round(best[-1]['end'], 2), 'context': ctx}


def for_sentence(project_dir, rid, at, kinds=('video',)):
    """« Trouver automatiquement un plan de coupe pour cette phrase » : comprend la phrase (IA locale), cherche
    dans les banques, classe, propose les 3 meilleurs. Rien n'est telecharge ni insere."""
    from .. import montage
    reel = montage.load(project_dir, rid)
    seg = montage.compute(reel)
    phrase = phrase_at(seg['words'], float(at))
    if not phrase:
        raise BanqueErreur('Aucune phrase a cet instant.')
    plan = queries_for([{'text': phrase['text'], 'context': phrase['context']}])[0]
    need = round(_clamp(phrase['end'] - phrase['start'], 1.5, 3.5), 2)
    ctx = {'queries': plan['queries'], 'description': plan['description'], 'target': (reel['width'], reel['height']),
           'need': need, 'style': reel.get('template'), 'llm': plan['llm']}
    found = []
    for kind in kinds:
        found += rank(gather(plan['queries'], kind, plan['lang']), ctx, analyse_top=4)
    found.sort(key=lambda c: -c['score'])
    message = ''
    if not found or found[0]['relevance'] < 0.4:
        # repli : photos (souvent plus nombreuses que les videos sur les idees precises)
        if 'image' not in kinds:
            found = sorted(found + rank(gather(plan['queries'][:3], 'image', plan['lang'], per_query=10), ctx), key=lambda c: -c['score'])
        if not found or found[0]['relevance'] < 0.4:
            message = 'Aucun plan vraiment pertinent : essaie une recherche manuelle avec tes mots.'
    if not plan['illustrable']:
        message = ("L'IA pense que cette phrase n'a pas besoin de plan de coupe." + (f' {message}' if message else '') if plan['llm']
                   else 'Pas de mot assez precis dans cette phrase : essaie une recherche manuelle avec tes mots.')
    return {'phrase': phrase, 'requetes': plan['queries'], 'description': plan['description'], 'duree': need,
            'candidats': found[:3], 'message': message, 'ia': plan['llm']}
