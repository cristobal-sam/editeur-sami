"""Claude (API d'Anthropic), en option : le « cerveau creatif » (comprendre la pub, mots forts, textes des cartes et
notifications, bandeau, decoupage, fautes de transcription), la « critique visuelle » des images rendues et la boite
« Dis a l'IA ce que tu veux » (consigne).

Seul module de l'editeur qui parle a Claude. Les autres passes appellent ``appeler()`` et gardent leur chemin LOCAL
(Qwen) des que la reponse n'est pas ``ok`` : Claude eteint, pas de cle, plafond atteint, credit epuise, hors ligne,
refus, reponse coupee ou illisible. Rien n'est jamais bloquant : ``appeler()`` ne leve pas d'exception pour un
probleme d'API.

Fichiers :
  styles/claude.json                 reglages (modele, effort, plafonds, credit de depart) : reglages() /
                                     ecrire_reglages() ; cree avec les valeurs par defaut s'il manque
  projects/_claude.json              registre des depenses (par jour, par mois, par video « projet/version ») ;
                                     cree et tenu par ce module (ecriture atomique, verrou entre processus)
  runtime/cache/claude-appels.jsonl  journal ajout-seul, une ligne par appel (jetons, cout, request_id ; jamais
                                     d'invite ni de cle) : le registre est reconstruit a partir de lui s'il est abime
La cle (ANTHROPIC_API_KEY) est chargee depuis cles-api.env par banques._load_keys(). Elle ne sort jamais de ce module :
ni statut, ni journal, ni message (masquee si une erreur la cite). Une cle d'ORGANISATION (pas liee a un espace de
travail) exige l'en-tete anthropic-workspace-id : identifiant wrkspc_... du reglage espace_travail (pas un secret), sinon
de la variable ANTHROPIC_WORKSPACE_ID ; sans lui, Anthropic repond 400 (non facture) -> phrase claire et pause de 10 min.

Argent : l'utilisateur teste avec un petit credit (2 $). Modele par defaut : Claude Sonnet 5.5 (bon et economique) ;
Haiku 4.5 (le moins cher) et Opus 5.5 (le meilleur, 2 x plus cher) au choix, en general ou par tache. Avant chaque
appel, une estimation HAUTE (caracteres / 3,5 jetons + 800 jetons par image + sortie maximale) est comparee au credit
restant estime et aux plafonds par video, par jour et par mois ; au-dela, refus clair et chemin local. Un refus
« credit epuise » d'Anthropic bloque les appels pendant 10 minutes (pas de demandes inutiles).

Regles de l'API suivies (skill claude-api) : sortie structuree ``output_config.format`` (pas de pre-remplissage, pas de
tool_choice force), consigne systeme stable en tete avec ``cache_control``, images JPEG en base64 AVANT le texte,
stop_reason verifie avant de lire la reponse. Forme de la requete selon le modele :
  Sonnet 5.5 / Opus 5.5  client.beta.messages.create : output_config.effort explicite (low | medium | high), pas de
                         « thinking » (reflexion adaptative toujours active : « disabled » ou budget_tokens = 400),
                         repli serveur fallbacks="default" (beta server-side-fallback-2026-07-01)
  Haiku 4.5              client.messages.create simple : ni effort, ni thinking, ni repli, ni beta
Par prudence, une erreur 400 qui vise l'effort ou le repli (non facturee) relance UNE fois sans ce champ, et ce
modele s'en passe ensuite pour la session.

Tests : remplacer ``_client`` (fabrique : cle -> client) par un faux client qui offre ``messages.create(**params)`` et
``beta.messages.create(**params)`` ; ``_cle`` par une fonction qui rend une fausse cle ; et REGLAGES / REGISTRE /
JOURNAL / VERROU par des chemins de bac a sable. Ou remplacer ``appeler`` lui-meme. Jamais d'appel reel dans les tests
(docs/claude-api/tests/test_noyau.py).
"""
import base64
import hashlib
import io
import json
import math
import os
import re
import threading
import time
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

from .media import ROOT

REGLAGES = ROOT / 'styles/claude.json'
REGISTRE = ROOT / 'projects/_claude.json'
JOURNAL = ROOT / 'runtime/cache/claude-appels.jsonl'
VERROU = ROOT / 'runtime/cache/claude.lock'

# modeles proposes (liste fermee) : Sonnet 5.5 par defaut, Haiku 4.5 le moins cher, Opus 5.5 le meilleur
MODELES = ('claude-sonnet-5-5', 'claude-haiku-4-5', 'claude-opus-5-5')
NOMS = {'claude-sonnet-5-5': 'Claude Sonnet 5.5', 'claude-haiku-4-5': 'Claude Haiku 4.5',
        'claude-opus-5-5': 'Claude Opus 5.5'}
CONSEILS = {'claude-sonnet-5-5': 'Recommandé : bonne qualité, prix raisonnable.',
            'claude-haiku-4-5': 'Le moins cher (environ 2 fois moins que Sonnet), un peu moins fin.',
            'claude-opus-5-5': 'Le meilleur, mais environ 2 fois plus cher que Sonnet.'}
AVEC_EFFORT = ('claude-sonnet-5-5', 'claude-opus-5-5')  # Haiku 4.5 ne connait pas output_config.effort
AVEC_REPLI = ('claude-sonnet-5-5', 'claude-opus-5-5')   # repli serveur sur refus de securite (forme « default »)
BETA_REPLI = 'server-side-fallback-2026-07-01'
EFFORTS = ('low', 'medium', 'high')
TACHES = ('cerveau', 'critique', 'consigne')  # une tache « critique... » prend le modele / l'effort de « critique »
DELAI = 120.0           # s d'attente de la reponse avant d'abandonner (le SDK refait 2 fois 429 / 5xx / coupure)
ATTENTE_CREDIT = 600.0  # s sans nouvel appel apres un refus « credit epuise » d'Anthropic
SORTIE_MAX = 64000      # jetons de sortie au plus (Haiku 4.5 : 64 K ; Sonnet / Opus : 128 K)
DEFAUTS = {'actif': True, 'modele': 'claude-sonnet-5-5',
           'modeles_taches': {'cerveau': None, 'critique': None, 'consigne': None},  # None = modele general
           'effort_cerveau': 'medium', 'effort_critique': 'medium', 'effort_consigne': 'low',
           'plafond_video': 0.25, 'plafond_jour': 0.75, 'plafond_mois': 2.0,
           'credit_depart': 2.0, 'credit_date': '2026-10-02',
           'critique_auto': False, 'images_critique': 16, 'largeur_images': 540,
           'espace_travail': None}  # identifiant wrkspc_... (cle d'organisation sans espace de travail), sinon None
ESPACE = re.compile(r'wrkspc_[A-Za-z0-9]{8,64}')
ESPACE_MANQUANT = ("Cette clé Claude n'est liée à aucun espace de travail (workspace) : copie l'identifiant de "
                   "l'espace de travail (il commence par wrkspc_) depuis platform.claude.com (Settings → Workspaces) "
                   "dans les réglages de Claude, ou crée une clé dans un espace de travail. L'outil continue en local.")
BORNES = {'plafond_video': (0.0, 1000.0), 'plafond_jour': (0.0, 1000.0), 'plafond_mois': (0.0, 1000.0),
          'credit_depart': (0.0, 1000.0), 'images_critique': (1, 48), 'largeur_images': (256, 1080)}

# $ par million de jetons : (entree, sortie, lecture du cache) ; ecriture du cache (5 min) = 1,25 x entree.
# Tarifs officiels (skill claude-api, octobre 2026) ; les trois derniers : modeles de repli possibles (fallbacks).
PRIX = {
    'claude-sonnet-5-5': (2.0, 10.0, 0.20),
    'claude-haiku-4-5': (1.0, 5.0, 0.10),
    'claude-opus-5-5': (4.0, 20.0, 0.20),
    'claude-sonnet-5': (2.0, 10.0, 0.20),
    'claude-opus-5': (5.0, 25.0, 0.50),
    'claude-opus-4-8': (5.0, 25.0, 0.50),
}
CACHE_ECRITURE = 1.25
CAR_PAR_JETON = 3.5     # estimation large (le francais fait plutot 3,5 a 4 caracteres par jeton)
JETONS_IMAGE = 800      # une image 540 x 960 fait ~700 jetons (une case de 28 x 28 px = un jeton)
SURCOUT_FORMAT = 300    # consigne ajoutee par la sortie structuree (schema) : estimation large
# appels typiques (jetons) pour estimation_video() : consigne systeme, texte variable, images, sortie (reflexion
# comprise ; Haiku 4.5 ne reflechit pas : sortie x 0,5). A recaler sur le registre apres les premiers vrais appels.
PROFILS = {'cerveau': {'systeme': 3000, 'texte': 3500, 'images': 0, 'sortie': 3000},
           'consigne': {'systeme': 2500, 'texte': 3500, 'images': 0, 'sortie': 1500},
           'critique': {'systeme': 2000, 'texte': 1000, 'images': None, 'sortie': 2500}}  # None : images_critique
GARDE_APPELS = 40       # appels detailles gardes par video dans le registre (le journal garde tout)
GARDE_JOURS_VIDEO = 180  # une video sans appel depuis 180 jours sort du registre (pas du journal)
GARDE_JOURS = 400

RELAIS = "L'outil continue en local."
CREDIT_EPUISE = "Crédit Anthropic épuisé : recharge sur platform.claude.com (Billing). L'outil continue en local."

_verrou_local = threading.RLock()
_tenu = threading.local()
_en_cours = {}       # appels partis mais pas encore inscrits (meme processus) : jeton -> (video, estimation $)
_clients = {}
_sans_session = {}   # modele -> champs retires apres un 400 (« effort », « repli ») pour la session
_TRANSPORT_TEST = None  # tests seulement : faux transport httpx2 (le vrai SDK sans reseau)


# ---------- petits outils ----------
def _jour():
    return time.strftime('%Y-%m-%d')


def _maintenant():
    return time.strftime('%Y-%m-%dT%H:%M:%S')


def _argent(x):
    """0,42 $ ; 0,0042 $ pour les tout petits montants."""
    x = float(x or 0)
    return (f'{x:.2f}' if x >= 0.1 or x == 0 else f'{x:.4f}').replace('.', ',') + ' $'


def _champ(o, k, defaut=None):
    """Champ d'un objet du SDK ou d'un dict (faux clients des tests)."""
    if isinstance(o, dict):
        return o.get(k, defaut)
    return getattr(o, k, defaut)


def _entier(o, k):
    try:
        return int(_champ(o, k) or 0)
    except (TypeError, ValueError):
        return 0


def _masquer(texte):
    """Retire toute cle d'un texte (message d'erreur du SDK) avant de l'afficher ou de l'ecrire."""
    texte = str(texte or '')
    k = os.environ.get('ANTHROPIC_API_KEY')
    if k and len(k) >= 8:
        texte = texte.replace(k, '[clé masquée]')
    return re.sub(r'sk-ant-[A-Za-z0-9_\-]{4,}', '[clé masquée]', texte)


def _cle():
    """Cle Anthropic (via le chargeur commun des cles) ou None. Jamais affichee ni ecrite."""
    try:
        from .banques import _load_keys
        _load_keys()
    except Exception:
        pass
    return os.environ.get('ANTHROPIC_API_KEY') or None


def _sdk():
    """Module anthropic installe ? Sans l'importer (2,5 s) : statut() reste rapide pour l'interface."""
    try:
        import importlib.util
        return importlib.util.find_spec('anthropic') is not None
    except Exception:
        return False


def _espace(r=None):
    """Identifiant d'espace de travail (en-tete anthropic-workspace-id) : reglage espace_travail, sinon la variable
    ANTHROPIC_WORKSPACE_ID (aussi lue dans cles-api.env par le chargeur commun, appele par _cle) ; None si absent ou mal
    forme. Seulement utile pour une cle d'organisation."""
    for v in ((r or reglages()).get('espace_travail'), os.environ.get('ANTHROPIC_WORKSPACE_ID')):
        if isinstance(v, str) and ESPACE.fullmatch(v.strip()):
            return v.strip()
    return None


def _client(cle):
    """Client Anthropic (un par cle et espace de travail, reutilise) : 120 s d'attente au plus ; 2 nouvelles tentatives
    (429 / 5xx). L'espace de travail part en en-tete du client : le corps des requetes ne change pas."""
    import anthropic
    espace = _espace()
    k = hashlib.sha256(f'{cle}|{espace}'.encode('utf-8')).hexdigest()
    c = _clients.get(k)
    if c is None:
        opts = {'default_headers': {'anthropic-workspace-id': espace}} if espace else {}
        if _TRANSPORT_TEST is not None:
            opts['http_client'] = anthropic.DefaultHttpxClient(transport=_TRANSPORT_TEST)
        c = _clients[k] = anthropic.Anthropic(api_key=cle, timeout=anthropic.Timeout(DELAI, connect=15.0), max_retries=2,
                                              **opts)
    return c


def cle_video(video):
    """« projet/version » (ex. video1/script) a partir de « video1/script », (dossier, version) ou « video1 »."""
    if not video:
        return None
    if isinstance(video, (tuple, list)):
        projet, rid = (list(video) + [None, None])[:2]
        projet = Path(str(projet)).name
    else:
        parts = [p for p in str(video).replace('\\', '/').split('/') if p]
        if not parts:
            return None
        projet, rid = (parts[0], None) if len(parts) == 1 else (parts[-2], parts[-1])

    def propre(s):
        return re.sub(r'[^A-Za-z0-9_.-]', '_', str(s))[:60]
    return f'{propre(projet)}/{propre(rid or "script")}'


def _groupe(tache):
    """« cerveau », « critique » ou « consigne » (prefixe du nom de la tache), sinon None."""
    t = str(tache or '').lower()
    return next((g for g in TACHES if t.startswith(g)), None)


# ---------- ecriture sure et verrou entre processus ----------
def _ecrire_json(path, data, indent=1):
    """Fichier temporaire puis remplacement (une coupure ne laisse jamais un fichier a moitie ecrit)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'{path.name}.{os.getpid()}.{threading.get_ident()}.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding='utf-8')
    for essai in range(40):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:  # Windows : le fichier est ouvert un instant par un lecteur (serveur, interface)
            if essai == 39:
                try:
                    tmp.unlink()
                except OSError:
                    pass
                raise
            time.sleep(0.05)


def _prendre_verrou():
    """Verrou de fichier (runtime/cache/claude.lock) ; ~10 s au plus, ensuite on continue sans (mieux qu'un blocage)."""
    try:
        VERROU.parent.mkdir(parents=True, exist_ok=True)
        f = open(VERROU, 'a+b')
    except OSError:
        return None
    for _ in range(200):
        try:
            f.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return f
        except OSError:
            time.sleep(0.05)
    f.close()
    return None


def _rendre_verrou(f):
    if f is None:
        return
    try:
        f.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    f.close()


@contextmanager
def _verrou():
    """Section critique entre fils (RLock) et entre processus (fichier) ; reentrante dans un meme fil."""
    with _verrou_local:
        if getattr(_tenu, 'n', 0):
            _tenu.n += 1
            try:
                yield
            finally:
                _tenu.n -= 1
            return
        f = _prendre_verrou()
        _tenu.n = 1
        try:
            yield
        finally:
            _tenu.n = 0
            _rendre_verrou(f)


# ---------- reglages (styles/claude.json) ----------
def _valeur(k, v):
    """-> valeur validee ; ValueError (phrase en francais) sinon. « modeles_taches » : voir _taches()."""
    if k in ('actif', 'critique_auto'):
        if not isinstance(v, bool):
            raise ValueError(f'Réglage « {k} » : vrai ou faux attendu (true / false).')
        return v
    if k == 'modele':
        if not isinstance(v, str) or v not in MODELES:
            raise ValueError(f"Modèle inconnu : {str(v)[:40]}. Choix possibles : {', '.join(MODELES)}.")
        return v
    if k.startswith('effort_'):
        if not isinstance(v, str) or v not in EFFORTS:
            raise ValueError(f"Réglage « {k} » : {str(v)[:20]} inconnu. Choix possibles : {', '.join(EFFORTS)}.")
        return v
    if k == 'espace_travail':
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if not isinstance(v, str) or not ESPACE.fullmatch(v.strip()):
            raise ValueError("Espace de travail : l'identifiant commence par « wrkspc_ » (platform.claude.com → "
                             'Settings → Workspaces).')
        return v.strip()
    if k == 'credit_date':
        try:
            if not isinstance(v, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', v):
                raise ValueError
            return date.fromisoformat(v).isoformat()
        except ValueError:
            raise ValueError('Réglage « credit_date » : une date AAAA-MM-JJ est attendue (ex. 2026-10-02).') from None
    lo, hi = BORNES[k]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(f'Réglage « {k} » : un nombre est attendu.')
    if k.startswith('plafond_') or k == 'credit_depart':
        if not lo <= v <= hi:
            raise ValueError(f'Réglage « {k} » : entre {lo:g} et {hi:g} $.')
        return round(float(v), 4)
    if float(v) != int(v):
        raise ValueError(f'Réglage « {k} » : un nombre entier est attendu.')
    if not lo <= int(v) <= hi:
        raise ValueError(f'Réglage « {k} » : entre {lo} et {hi}.')
    return int(v)


def _taches(v, actuel):
    """Modele par tache : {"critique": "claude-haiku-4-5"} (les taches absentes gardent leur valeur ; null = modele
    general) ; null pour tout remettre au modele general. ValueError sinon."""
    if v is None:
        return {t: None for t in TACHES}
    if not isinstance(v, dict):
        raise ValueError('Réglage « modeles_taches » : un objet est attendu, ex. {"critique": "claude-haiku-4-5"}.')
    inconnues = [str(t) for t in v if t not in TACHES]
    if inconnues:
        raise ValueError(f"Tâche inconnue : {', '.join(inconnues)[:60]}. Tâches possibles : {', '.join(TACHES)}.")
    out = {t: (actuel or {}).get(t) for t in TACHES}
    for t, m in v.items():
        if m is not None and (not isinstance(m, str) or m not in MODELES):
            raise ValueError(f"Modèle inconnu pour « {t} » : {str(m)[:40]}. Choix possibles : {', '.join(MODELES)} "
                             '(ou null = modèle général).')
        out[t] = m
    return out


def reglages():
    """Reglages de Claude (styles/claude.json, cree avec les valeurs par defaut s'il manque). Une valeur abimee ou hors
    bornes vaut sa valeur par defaut (le fichier n'est pas reecrit : l'utilisateur est peut-etre en train de l'editer)."""
    r = json.loads(json.dumps(DEFAUTS))
    try:
        lu = json.loads(REGLAGES.read_text(encoding='utf-8-sig'))
    except FileNotFoundError:
        try:
            _ecrire_json(REGLAGES, r)
        except OSError:
            pass
        return r
    except (OSError, ValueError):
        return r
    if isinstance(lu, dict):
        for k in DEFAUTS:
            if k not in lu:
                continue
            if k == 'modeles_taches':
                if isinstance(lu[k], dict):
                    r[k] = {t: (m if m in MODELES else None) for t, m in
                            ((t, lu[k].get(t)) for t in TACHES)}
                continue
            try:
                r[k] = _valeur(k, lu[k])
            except ValueError:
                pass
    return r


def ecrire_reglages(patch):
    """Modifie des reglages (validation stricte, tout ou rien) -> reglages complets. ValueError si une valeur est refusee.
    Changer credit_depart ou credit_date (recharge) efface l'alerte « credit epuise » du registre ; changer
    espace_travail efface l'alerte « espace de travail manquant »."""
    if not isinstance(patch, dict) or not patch:
        raise ValueError('Réglages de Claude : un objet JSON est attendu, par exemple {"plafond_jour": 0.5}.')
    inconnus = [str(k) for k in patch if k not in DEFAUTS]
    if inconnus:
        raise ValueError(f"Réglage inconnu : {', '.join(inconnus)[:80]}. Réglages possibles : {', '.join(DEFAUTS)}.")
    with _verrou():
        r = reglages()
        for k, v in patch.items():
            r[k] = _taches(v, r[k]) if k == 'modeles_taches' else _valeur(k, v)
        _ecrire_json(REGLAGES, r)
        alertes = (['credit_epuise'] if 'credit_depart' in patch or 'credit_date' in patch else []) + \
            (['espace_manquant'] if 'espace_travail' in patch else [])
        if alertes:
            reg = _charger()
            if any(reg.get(a) for a in alertes):
                for a in alertes:
                    reg[a] = None
                _ecrire_json(REGISTRE, reg)
    return r


def modele_pour(tache, r=None):
    """Modele a utiliser pour une tache : reglage par tache (modeles_taches) sinon modele general."""
    r = r or reglages()
    g = _groupe(tache)
    m = (r.get('modeles_taches') or {}).get(g) if g else None
    return m if m in MODELES else r['modele']


def _effort_pour(tache, r):
    return r[f"effort_{_groupe(tache) or 'cerveau'}"]


# ---------- prix ----------
def prix(modele):
    """Tarif d'un modele en $ par million de jetons {entree, sortie, cache_lu, cache_ecrit}, ou None s'il est inconnu.
    Un identifiant date (claude-haiku-4-5-20251001) prend le tarif de son alias."""
    m = re.sub(r'-\d{8}$', '', str(modele or ''))
    p = PRIX.get(m)
    if not p:
        return None
    e, s, lu = p
    return {'entree': e, 'sortie': s, 'cache_lu': lu, 'cache_ecrit': round(e * CACHE_ECRITURE, 6)}


def _jetons_vides():
    return {'entree': 0, 'sortie': 0, 'cache_lu': 0, 'cache_ecrit': 0, 'images': 0}


def _cout_tranche(u, p):
    return (_entier(u, 'input_tokens') * p['entree'] + _entier(u, 'cache_creation_input_tokens') * p['cache_ecrit']
            + _entier(u, 'cache_read_input_tokens') * p['cache_lu'] + _entier(u, 'output_tokens') * p['sortie']) / 1e6


def _ajouter_jetons(j, u):
    j['entree'] += _entier(u, 'input_tokens')
    j['sortie'] += _entier(u, 'output_tokens')  # la reflexion fait partie des jetons de sortie
    j['cache_lu'] += _entier(u, 'cache_read_input_tokens')
    j['cache_ecrit'] += _entier(u, 'cache_creation_input_tokens')


def detail_cout(usage, modele, servi=None):
    """-> (cout $, jetons {entree, sortie, cache_lu, cache_ecrit, images}, note).
    usage.iterations (repli serveur : un autre modele a servi) : chaque tentative a son propre tarif (son modele, ou
    ``servi`` = modele de la reponse pour la tentative de repli) ; un modele inconnu est compte au tarif du modele
    demande (note)."""
    notes = []
    base = prix(modele)
    if base is None:
        plus_cher = max(PRIX, key=lambda m: PRIX[m][1])
        notes.append(f'tarif de {str(modele)[:40]} inconnu : compté au tarif de {plus_cher}')
        base = prix(plus_cher)
    jetons = _jetons_vides()
    tranches = [it for it in (_champ(usage, 'iterations') or []) if it is not None]
    total = 0.0
    if tranches:
        for it in tranches:
            m = _champ(it, 'model')
            if not m and _champ(it, 'type') == 'fallback_message':
                m = servi if servi and servi != modele else None
                if not m:
                    notes.append(f'modèle de repli inconnu : compté au tarif de {modele}')
            p = prix(m) if m else None
            if m and p is None:
                notes.append(f'tarif de {str(m)[:40]} inconnu : compté au tarif de {modele}')
            total += _cout_tranche(it, p or base)
            _ajouter_jetons(jetons, it)
    if not tranches or (total == 0 and _cout_tranche(usage, base) > 0):
        jetons = _jetons_vides()
        total = _cout_tranche(usage, base)
        _ajouter_jetons(jetons, usage)
    return round(total, 6), jetons, '; '.join(dict.fromkeys(notes))


def cout(usage, modele):
    """Cout en $ d'un appel : entree x tarif + ecriture cache x 1,25 x tarif + lecture cache + sortie (reflexion comprise)."""
    return detail_cout(usage, modele)[0]


def _jetons_texte(texte):
    return int(math.ceil(len(texte or '') / CAR_PAR_JETON))


def _texte_contenu(contenu):
    if isinstance(contenu, list):
        return ''.join(str(b.get('text') or '') for b in contenu if isinstance(b, dict))
    return str(contenu or '')


def estimer(systeme='', contenu='', images=0, sortie=8000, modele=None, schema=None, jetons_images=None):
    """Estimation HAUTE du cout d'un appel en $ (sans appel a l'API) : caracteres / 3,5 jetons, consigne systeme au tarif
    d'ecriture du cache, 800 jetons par image (ou jetons_images), plus la sortie maximale attendue."""
    p = prix(modele or reglages()['modele']) or prix(MODELES[0])
    sys_txt = systeme if isinstance(systeme, str) else ''.join(map(str, systeme or []))
    t_sys = _jetons_texte(sys_txt)
    t_in = _jetons_texte(_texte_contenu(contenu)) + SURCOUT_FORMAT
    if schema is not None:
        t_in += _jetons_texte(json.dumps(schema, ensure_ascii=False))
    t_img = int(jetons_images) if jetons_images is not None else int(images or 0) * JETONS_IMAGE
    return round((t_sys * p['cache_ecrit'] + (t_in + t_img) * p['entree'] + int(sortie or 0) * p['sortie']) / 1e6, 6)


def estimation_video(modele=None):
    """Cout TYPIQUE (pas un plafond) pour l'interface : cerveau + consigne d'une video, et une critique d'images
    (images_critique images). -> {modele, nom, cerveau, consigne, par_video, critique, videos_avec_credit, texte}."""
    r = reglages()
    m = modele if modele in MODELES else r['modele']
    p = prix(m)
    out = {'modele': m, 'nom': NOMS[m]}
    for tache, f in PROFILS.items():
        n_img = r['images_critique'] if f['images'] is None else f['images']
        sortie = f['sortie'] if m in AVEC_EFFORT else f['sortie'] * 0.5
        out[tache] = round((f['systeme'] * p['cache_ecrit'] + (f['texte'] + SURCOUT_FORMAT + n_img * 700) * p['entree']
                            + sortie * p['sortie']) / 1e6, 4)
    out['par_video'] = round(out['cerveau'] + out['consigne'], 4)
    out['videos_avec_credit'] = int(r['credit_depart'] // out['par_video']) if out['par_video'] > 0 else 0

    def environ(x):
        return 'moins de 0,01 $' if x < 0.01 else f'{x:.2f}'.replace('.', ',') + ' $'
    out['texte'] = (f"Environ {environ(out['par_video'])} par vidéo (idées + une demande) et "
                    f"{environ(out['critique'])} par relecture d'images avec {NOMS[m]}, soit à peu près "
                    f"{out['videos_avec_credit']} vidéos avec {_argent(r['credit_depart'])}.")
    return out


# ---------- registre des depenses (projects/_claude.json) et journal ----------
def _vide():
    return {'version': 1, 'jours': {}, 'mois': {}, 'videos': {}, 'dernier': None, 'credit_epuise': None,
            'espace_manquant': None, 'journal_octets': 0}


def _valide(reg):
    return isinstance(reg, dict) and all(isinstance(reg.get(k), dict) for k in ('jours', 'mois', 'videos'))


def _elaguer(reg, jour):
    try:
        d = date.fromisoformat(jour[:10])
    except ValueError:
        return
    limite_j = (d - timedelta(days=GARDE_JOURS)).isoformat()
    limite_v = (d - timedelta(days=GARDE_JOURS_VIDEO)).isoformat()
    for k in [k for k in reg['jours'] if k < limite_j]:
        del reg['jours'][k]
    for k in [k for k, f in reg['videos'].items() if str((f or {}).get('dernier') or '')[:10] < limite_v]:
        del reg['videos'][k]


def _ajouter(reg, e):
    """Ajoute un appel du journal aux totaux (jour, mois, video), au « dernier appel » et a l'alerte de credit."""
    d = str(e.get('date') or _maintenant())
    try:
        c = float(e.get('cout') or 0)
    except (TypeError, ValueError):
        c = 0.0
    for coll, k in (('jours', d[:10]), ('mois', d[:7])):
        t = reg[coll].setdefault(k, {'cout': 0.0, 'appels': 0})
        t['cout'] = round(float(t.get('cout') or 0) + c, 6)
        t['appels'] = int(t.get('appels') or 0) + 1
    v = e.get('video')
    if v:
        f = reg['videos'].setdefault(str(v), {'cout': 0.0, 'nb': 0, 'appels': []})
        f['cout'] = round(float(f.get('cout') or 0) + c, 6)
        f['nb'] = int(f.get('nb') or 0) + 1
        f['dernier'] = d
        f.setdefault('appels', []).append({k: e.get(k) for k in ('date', 'tache', 'modele', 'jetons', 'cout', 'request_id',
                                                                 'ok', 'erreur')})
        del f['appels'][:-GARDE_APPELS]
    reg['dernier'] = {'date': d, 'tache': e.get('tache'), 'cout': c, 'modele': e.get('modele'), 'video': v,
                      'ok': e.get('ok')}
    for genre, cle in (('credit', 'credit_epuise'), ('espace', 'espace_manquant')):
        if e.get('type_erreur') == genre:
            reg[cle] = d
        elif e.get('ok'):
            reg[cle] = None
    _elaguer(reg, d)


def _lire_fichier_registre():
    """-> registre, None s'il n'existe pas ; ValueError s'il est abime."""
    texte = None
    for _ in range(10):
        try:
            texte = REGISTRE.read_text(encoding='utf-8')
            break
        except FileNotFoundError:
            return None
        except PermissionError:  # remplacement en cours par un autre processus
            time.sleep(0.05)
    if texte is None:
        raise ValueError('registre illisible')
    reg = json.loads(texte)
    if not _valide(reg):
        raise ValueError('registre de forme inattendue')
    reg.setdefault('dernier', None)
    reg.setdefault('credit_epuise', None)
    reg.setdefault('espace_manquant', None)
    return reg


def _rattraper(reg):
    """Applique les lignes du journal ecrites apres le registre (tout le journal pour une reconstruction)."""
    try:
        taille = JOURNAL.stat().st_size
    except OSError:
        return reg
    deja = int(reg.get('journal_octets') or 0)
    if taille < deja:  # journal remplace ou raccourci a la main : on repart de sa taille actuelle
        reg['journal_octets'] = taille
        return reg
    if taille == deja:
        return reg
    with open(JOURNAL, 'rb') as f:
        f.seek(deja)
        morceau = f.read(taille - deja)
    for ligne in morceau.decode('utf-8', 'replace').splitlines():
        try:
            e = json.loads(ligne)
        except ValueError:
            continue  # ligne abimee (coupure pendant l'ecriture) : ignoree
        if isinstance(e, dict):
            _ajouter(reg, e)
    reg['journal_octets'] = taille
    return reg


def _charger():
    """Registre a jour ; manquant ou abime -> reconstruit depuis le journal (le fichier abime est garde a cote :
    projects/_claude.json.abime)."""
    try:
        reg = _lire_fichier_registre()
        abime = False
    except ValueError:
        reg, abime = None, True
    if reg is not None:
        return _rattraper(reg)
    if not abime and not JOURNAL.exists():
        return _vide()
    with _verrou():
        try:  # un autre processus l'a peut-etre deja repare
            reg = _lire_fichier_registre()
            if reg is not None:
                return _rattraper(reg)
        except ValueError:
            pass
        reg = _rattraper(_vide())
        try:
            if REGISTRE.exists():
                os.replace(REGISTRE, REGISTRE.with_name(REGISTRE.name + '.abime'))
            _ecrire_json(REGISTRE, reg)
        except OSError:
            pass
    return reg


def _inscrire(e):
    """Une ligne dans le journal (d'abord : il fait foi), puis le registre mis a jour."""
    with _verrou():
        reg = _charger()
        JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        with open(JOURNAL, 'a+b') as f:
            f.seek(0, os.SEEK_END)
            if f.tell():  # derniere ligne coupee (arret brutal) : on ne colle pas la nouvelle ligne derriere
                f.seek(-1, os.SEEK_END)
                if f.read(1) != b'\n':
                    f.write(b'\n')
            f.write((json.dumps(e, ensure_ascii=False) + '\n').encode('utf-8'))
        _ajouter(reg, e)
        try:
            reg['journal_octets'] = JOURNAL.stat().st_size
        except OSError:
            pass
        _ecrire_json(REGISTRE, reg)


def depense_video(video):
    """$ deja depenses pour une video (« projet/version »)."""
    f = _charger()['videos'].get(cle_video(video) or '') or {}
    return round(float(f.get('cout') or 0), 6)


def _depense_credit(reg, r):
    """$ depenses depuis credit_date (inclus) d'apres le registre."""
    return sum(float((t or {}).get('cout') or 0) for d, t in reg['jours'].items() if d >= r['credit_date'])


def _credit_restant(reg, r):
    return max(0.0, round(r['credit_depart'] - _depense_credit(reg, r), 6))


def _recent(d):
    """True si la date (AAAA-MM-JJTHH:MM:SS) date de moins de 10 minutes."""
    if not d:
        return False
    try:
        t = time.mktime(time.strptime(str(d)[:19], '%Y-%m-%dT%H:%M:%S'))
    except ValueError:
        return False
    return time.time() - t < ATTENTE_CREDIT


def _credit_recent(reg):
    """True si Anthropic a refuse un appel faute de credit il y a moins de 10 minutes."""
    return _recent(reg.get('credit_epuise'))


def _bloque(reg, r):
    """Phrase si un appel ne peut qu'echouer pour l'instant (credit epuise, ou cle d'organisation sans espace de travail
    il y a moins de 10 minutes et toujours aucun espace indique), sinon ''."""
    if _credit_recent(reg):
        return CREDIT_EPUISE
    if _recent(reg.get('espace_manquant')) and not _espace(r):
        return ESPACE_MANQUANT
    return ''


def _depenses(reg, video=None):
    auj = _jour()
    vol = sum(m for _, m in _en_cours.values())
    dj = float((reg['jours'].get(auj) or {}).get('cout') or 0) + vol
    dm = float((reg['mois'].get(auj[:7]) or {}).get('cout') or 0) + vol
    dv = None
    if video:
        dv = float((reg['videos'].get(video) or {}).get('cout') or 0) + sum(m for v, m in _en_cours.values() if v == video)
    return dj, dm, dv, vol


def _refus_budget(reg, r, video, est):
    """Phrase de refus si l'estimation haute ferait depasser le credit restant ou un plafond, sinon ''."""
    bloque = _bloque(reg, r)
    if bloque:
        return bloque
    dj, dm, dv, vol = _depenses(reg, video)
    reste = _credit_restant(reg, r) - vol
    if est > reste:
        return (f"Crédit Claude presque épuisé : il reste environ {_argent(max(0.0, reste))} sur "
                f"{_argent(r['credit_depart'])}, cet appel pourrait coûter jusqu'à {_argent(est)}. Après une recharge "
                f"sur platform.claude.com (Billing), indique le nouveau crédit dans les réglages. {RELAIS}")
    if dm + est > r['plafond_mois']:
        return (f"Plafond du mois atteint : {_argent(dm)} déjà dépensés, cet appel pourrait coûter jusqu'à {_argent(est)} "
                f"(plafond {_argent(r['plafond_mois'])}). {RELAIS}")
    if dj + est > r['plafond_jour']:
        return (f"Plafond du jour atteint : {_argent(dj)} déjà dépensés, cet appel pourrait coûter jusqu'à {_argent(est)} "
                f"(plafond {_argent(r['plafond_jour'])}). {RELAIS}")
    if video and dv + est > r['plafond_video']:
        return (f"Plafond par vidéo atteint pour {video} : {_argent(dv)} déjà dépensés, cet appel pourrait coûter "
                f"jusqu'à {_argent(est)} (plafond {_argent(r['plafond_video'])}). {RELAIS}")
    return ''


# ---------- statut ----------
def statut():
    """Etat de Claude pour l'interface et le plugin (jamais la cle : seulement « cle presente »)."""
    r = reglages()
    cle = bool(_cle())
    reg = _charger()
    auj = _jour()
    tj = reg['jours'].get(auj) or {}
    tm = reg['mois'].get(auj[:7]) or {}
    dj, dm = float(tj.get('cout') or 0), float(tm.get('cout') or 0)
    reste = _credit_restant(reg, r)
    epuise = bool(reg.get('credit_epuise'))
    raison = avertissement = ''
    if not r['actif']:
        raison = f'Claude est éteint dans les réglages. {RELAIS}'
    elif not cle:
        raison = f"Aucune clé Claude : ajoute la ligne ANTHROPIC_API_KEY=… dans cles-api.env (dossier de l'éditeur). {RELAIS}"
    elif not _sdk():
        raison = f'Module « anthropic » absent du moteur (runtime/venv). {RELAIS}'
    elif _bloque(reg, r):
        raison = _bloque(reg, r)
    elif reste <= 0:
        raison = (f"Crédit Claude estimé épuisé ({_argent(r['credit_depart'])} dépensés depuis le {r['credit_date']}). "
                  f"Après une recharge sur platform.claude.com (Billing), indique le nouveau crédit dans les réglages. {RELAIS}")
    elif dm >= r['plafond_mois']:
        raison = f"Plafond du mois atteint ({_argent(dm)} sur {_argent(r['plafond_mois'])}). {RELAIS}"
    elif dj >= r['plafond_jour']:
        raison = f"Plafond du jour atteint ({_argent(dj)} sur {_argent(r['plafond_jour'])}) jusqu'à demain. {RELAIS}"
    if epuise and not raison:
        avertissement = ('Le dernier appel a été refusé faute de crédit Anthropic. Si tu as rechargé, le prochain appel '
                         'le vérifiera.')
    elif reg.get('espace_manquant') and not _espace(r) and not raison:
        # pause de 10 minutes finie : le prochain appel reessaiera (un refus 400 n'est pas facture), mais l'interface doit
        # quand meme dire quoi faire (avant : bandeau rouge vide)
        avertissement = ESPACE_MANQUANT
    d = reg.get('dernier') or None
    dernier = {k: d.get(k) for k in ('date', 'tache', 'cout', 'modele')} if isinstance(d, dict) else None
    return {'cle': cle, 'actif': r['actif'], 'modele': r['modele'], 'nom_modele': NOMS[r['modele']],
            'modeles_taches': dict(r['modeles_taches']),
            'plafonds': {'video': r['plafond_video'], 'jour': r['plafond_jour'], 'mois': r['plafond_mois']},
            'depense_jour': round(dj, 4), 'depense_mois': round(dm, 4),
            'credit_depart': r['credit_depart'], 'credit_date': r['credit_date'],
            'credit_restant_estime': round(reste, 4), 'appels_jour': int(tj.get('appels') or 0),
            'dernier_appel': dernier, 'credit_epuise': epuise, 'pret': not raison, 'raison': raison,
            'avertissement': avertissement, 'critique_auto': r['critique_auto'],
            'espace_travail': bool(_espace(r)), 'espace_manquant': bool(reg.get('espace_manquant')) and not _espace(r),
            # cout typique par modele (pour le choix du modele dans l'interface : le serveur n'a plus a le demander a part)
            'modeles': [{'id': m, 'nom': NOMS[m], 'conseil': CONSEILS[m], 'prix': prix(m), 'estimation': estimation_video(m)}
                        for m in MODELES],
            'estimation': estimation_video(r['modele'])}


def disponible():
    """-> (pret, raison) : a demander avant de preparer un appel couteux (images...)."""
    s = statut()
    return s['pret'], s['raison']


def couts(video=None, jours=7):
    """Depenses des N derniers jours, du mois, du credit, et d'une video (ses appels) ou des 20 dernieres videos."""
    try:
        jours = max(1, min(int(jours or 7), GARDE_JOURS))
    except (TypeError, ValueError):
        jours = 7
    reg = _charger()
    r = reglages()
    auj = date.fromisoformat(_jour())
    liste = []
    for i in range(jours):
        d = (auj - timedelta(days=i)).isoformat()
        t = reg['jours'].get(d) or {}
        liste.append({'date': d, 'cout': round(float(t.get('cout') or 0), 4), 'appels': int(t.get('appels') or 0)})
    m = auj.isoformat()[:7]
    tm = reg['mois'].get(m) or {}
    out = {'jours': liste, 'total': round(sum(x['cout'] for x in liste), 4),
           'mois': {'mois': m, 'cout': round(float(tm.get('cout') or 0), 4), 'appels': int(tm.get('appels') or 0)},
           'credit': {'depart': r['credit_depart'], 'date': r['credit_date'],
                      'depense': round(_depense_credit(reg, r), 4), 'restant_estime': round(_credit_restant(reg, r), 4)},
           'plafonds': {'video': r['plafond_video'], 'jour': r['plafond_jour'], 'mois': r['plafond_mois']}}
    if video:
        k = cle_video(video)
        f = reg['videos'].get(k or '') or {}
        out['video'] = {'video': k, 'cout': round(float(f.get('cout') or 0), 4), 'nb': int(f.get('nb') or 0),
                        'appels': f.get('appels') or []}
    else:
        recents = sorted(reg['videos'].items(), key=lambda kv: str((kv[1] or {}).get('dernier') or ''), reverse=True)[:20]
        out['videos'] = [{'video': k, 'cout': round(float(f.get('cout') or 0), 4), 'nb': int(f.get('nb') or 0),
                          'dernier': f.get('dernier')} for k, f in recents]
    return out


# ---------- images ----------
def image_jpeg(source, largeur=540, qualite=82):
    """Image -> (JPEG en base64, (largeur, hauteur)), reduite pour tenir dans largeur x largeur*16/9 (portrait) ou
    l'inverse (paysage) : 540 x 960 ~ 700 jetons. source : chemin, octets, tableau numpy HxWx3 (media.sample_frames)
    ou image PIL."""
    from PIL import Image
    if isinstance(source, Image.Image):
        im = source.convert('RGB')
    elif isinstance(source, (bytes, bytearray)):
        with Image.open(io.BytesIO(bytes(source))) as im0:
            im = im0.convert('RGB')
    elif isinstance(source, (str, Path)):
        with Image.open(source) as im0:
            im = im0.convert('RGB')
    elif hasattr(source, 'shape'):
        import numpy as np
        a = np.asarray(source)
        if a.dtype != np.uint8:
            a = np.clip(a, 0, 255).astype(np.uint8)
        im = Image.fromarray(a).convert('RGB')
    else:
        raise ValueError('Image : format non reconnu (chemin, octets, tableau ou image PIL attendu).')
    w, h = im.size
    largeur = int(largeur or DEFAUTS['largeur_images'])
    f = min(1.0, largeur / max(1, min(w, h)), round(largeur * 16 / 9) / max(1, max(w, h)))
    if f < 1.0:
        im = im.resize((max(1, round(w * f)), max(1, round(h * f))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=qualite, optimize=True)
    return base64.standard_b64encode(buf.getvalue()).decode('ascii'), im.size


def _blocs_images(images, largeur):
    """-> (blocs, nombre d'images, jetons estimes). Un element peut etre (legende, image) : la legende (ex. « 12,4 s »)
    passe en texte juste avant son image. Un bloc {"type": "image", ...} deja forme est garde tel quel."""
    blocs, n, jetons = [], 0, 0
    for item in images or []:
        legende = None
        if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str):
            legende, item = item
        if isinstance(item, dict) and item.get('type') == 'image':
            bloc, t = item, JETONS_IMAGE
        else:
            data, (w, h) = image_jpeg(item, largeur)
            bloc = {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': data}}
            t = max(JETONS_IMAGE, math.ceil(w / 28) * math.ceil(h / 28))
        if legende:
            blocs.append({'type': 'text', 'text': legende})
        blocs.append(bloc)
        n += 1
        jetons += t
    return blocs, n, jetons


# ---------- appel ----------
def _parametres(modele, systeme, contenu, blocs_images, schema, effort, max_tokens, sans=()):
    """Requete Messages selon le modele : consigne systeme stable (cache), images puis texte, sortie structuree ;
    Sonnet / Opus : effort explicite + repli serveur (beta) ; Haiku : rien de plus. Jamais de « thinking », de
    pre-remplissage ni de tool_choice. sans : champs retires apres un 400 (« effort », « repli »)."""
    content = list(blocs_images)
    if isinstance(contenu, list):
        content += contenu
    else:
        content.append({'type': 'text', 'text': str(contenu)})
    oc = {'format': {'type': 'json_schema', 'schema': schema}}
    if modele in AVEC_EFFORT and 'effort' not in sans:
        oc['effort'] = effort
    p = {'model': modele, 'max_tokens': max_tokens, 'messages': [{'role': 'user', 'content': content}],
         'output_config': oc}
    textes = ([systeme] if isinstance(systeme, str) else [str(t) for t in systeme if t]) if systeme else []
    if textes:
        p['system'] = [{'type': 'text', 'text': t} for t in textes]
        p['system'][-1]['cache_control'] = {'type': 'ephemeral'}
    if modele in AVEC_REPLI and 'repli' not in sans:
        p['betas'] = [BETA_REPLI]
        p['fallbacks'] = 'default'
    return p


def _envoyer(client, params):
    """Avec repli serveur (« betas ») : client.beta.messages.create ; sinon client.messages.create."""
    if 'betas' in params:
        msg = client.beta.messages.create(**params)
    else:
        msg = client.messages.create(**params)
    return msg, _champ(msg, '_request_id')


def _lire(msg):
    """-> (donnees, raison, genre) : stop_reason d'abord (refus, reponse coupee), puis le JSON de la reponse."""
    stop = _champ(msg, 'stop_reason')
    if stop == 'refusal':
        cat = _champ(_champ(msg, 'stop_details'), 'category')
        quoi = f'filtre de sécurité « {cat} »' if cat else 'refus de sécurité'
        return None, f'Claude a refusé cette demande ({quoi}). {RELAIS}', 'refus'
    if stop == 'max_tokens':
        return None, f'Réponse de Claude coupée (limite de longueur atteinte). {RELAIS}', 'coupee'
    if stop not in (None, 'end_turn', 'stop_sequence'):
        return None, f'Réponse de Claude inattendue (arrêt « {stop} »). {RELAIS}', 'reponse'
    blocs = list(_champ(msg, 'content') or [])
    textes = [(i, _champ(b, 'text') or '') for i, b in enumerate(blocs) if _champ(b, 'type') == 'text']
    if not textes:
        return None, f'Réponse de Claude vide. {RELAIS}', 'reponse'
    # repli en cours de reponse : texte partiel, bloc « fallback », puis la suite par le modele de repli
    limite = max((i for i, b in enumerate(blocs) if _champ(b, 'type') == 'fallback'), default=-1)
    candidats = [textes[0][1], next((t for i, t in textes if i > limite), None), ''.join(t for _, t in textes)]
    for c in candidats:
        if not c:
            continue
        try:
            return json.loads(c), '', ''
        except ValueError:
            continue
    return None, f'Réponse de Claude illisible (JSON invalide). {RELAIS}', 'reponse'


def _erreur(e):
    """Erreur du SDK -> (phrase claire, genre), la plus precise d'abord ; jamais la cle."""
    try:
        import anthropic as a
    except Exception:
        a = None
    if a is not None:
        if isinstance(e, a.AuthenticationError):
            return f'Clé refusée par Anthropic (erreur 401) : vérifie la ligne ANTHROPIC_API_KEY de cles-api.env. {RELAIS}', 'cle'
        if isinstance(e, a.APIStatusError) and 'workspace' in (getattr(e, 'message', '') or str(e)).lower():
            espace = _espace()
            if isinstance(e, a.BadRequestError) and not espace:  # cle d'organisation : en-tete anthropic-workspace-id exige
                return ESPACE_MANQUANT, 'espace'
            if espace:
                return (f"L'espace de travail indiqué dans les réglages de Claude est refusé par Anthropic (erreur "
                        f"{int(getattr(e, 'status_code', 0) or 0)}) : vérifie l'identifiant wrkspc_…. {RELAIS}"), 'espace_refuse'
        if isinstance(e, a.PermissionDeniedError):
            return f"Accès refusé par Anthropic (erreur 403) : cette clé n'a pas le droit d'utiliser ce modèle. {RELAIS}", 'acces'
        if isinstance(e, a.NotFoundError):
            return f'Modèle Claude introuvable (erreur 404) : choisis un autre modèle dans les réglages. {RELAIS}', 'modele'
        if isinstance(e, a.RateLimitError):
            return f"Limite d'utilisation d'Anthropic atteinte (erreur 429) : réessaie dans quelques minutes. {RELAIS}", 'limite'
        if isinstance(e, a.RequestTooLargeError):
            return f"Demande trop lourde pour Claude (erreur 413) : moins d'images ou des images plus petites. {RELAIS}", 'taille'
        if isinstance(e, a.APIStatusError):
            m = _masquer(getattr(e, 'message', '') or str(e))
            code = int(getattr(e, 'status_code', 0) or 0)
            if 'credit balance' in m.lower() or code == 402 or getattr(e, 'type', None) == 'billing_error':
                return CREDIT_EPUISE, 'credit'
            if isinstance(e, a.BadRequestError):
                return f"Demande refusée par l'API Claude (erreur 400) : {m[:200]}. {RELAIS}", 'requete'
            if code >= 500:
                return f"Serveurs d'Anthropic surchargés ou en panne (erreur {code}) : réessaie plus tard. {RELAIS}", 'serveur'
            return f"Erreur de l'API Claude (erreur {code}) : {m[:200]}. {RELAIS}", 'api'
        if isinstance(e, a.APITimeoutError):
            return f"Claude n'a pas répondu à temps (plus de {DELAI:.0f} s). Réessaie plus tard. {RELAIS}", 'delai'
        if isinstance(e, a.APIConnectionError):
            return f'Pas de connexion Internet (hors ligne) ou Anthropic injoignable. {RELAIS}', 'reseau'
    return f'Erreur inattendue avec Claude : {_masquer(str(e))[:200]}. {RELAIS}', 'autre'


def _champs_refuses(e, params):
    """400 « invalid_request_error » qui vise l'effort, la reflexion, le repli ou la beta -> champs a retirer
    ({"effort"}, {"repli"}) ; ensemble vide sinon (dont le credit epuise)."""
    try:
        import anthropic as a
    except Exception:
        return set()
    if not isinstance(e, a.BadRequestError) or getattr(e, 'type', None) not in (None, 'invalid_request_error'):
        return set()
    m = _masquer(getattr(e, 'message', '') or str(e)).lower()
    if 'credit balance' in m or 'workspace' in m:
        return set()
    out = set()
    if 'effort' in params.get('output_config', {}) and ('effort' in m or 'thinking' in m):
        out.add('effort')
    if 'betas' in params and ('fallback' in m or 'beta' in m):
        out.add('repli')
    return out


def appeler(tache, systeme, contenu, schema, *, video=None, images=None, effort=None, max_tokens=8000, modele=None,
            estimation=None):
    """Un appel a Claude avec sortie JSON structuree. Ne leve pas d'exception pour un probleme d'API.

    tache       « cerveau », « critique », « consigne » (ou un nom qui commence ainsi : modele et effort de ce groupe) ;
                autre nom (« test »...) : modele general, effort du cerveau
    systeme     consigne STABLE (regles du style, du montage) : mise en cache ; texte ou liste de textes
    contenu     ce qui change a chaque appel (transcription, reel, demande...) : texte, ou liste de blocs {"type": "text"}
    schema      schema JSON de la reponse (objets : "additionalProperties": false et "required" complets)
    video       « projet/version » ou (dossier, version) : plafond par video et suivi des couts de la video
    images      liste d'images (chemin, octets, tableau numpy, image PIL) ou de (legende, image) : JPEG reduit a
                largeur_images, place AVANT le texte
    effort      low | medium | high (defaut : reglages de la tache ; ignore par Haiku 4.5)
    max_tokens  sortie maximale (reflexion comprise) : sert aussi a l'estimation haute du budget
    modele      un modele de MODELES (defaut : modele_pour(tache))
    estimation  (rare) jetons de sortie attendus au plus pour le controle du budget, ou {"sortie": n} / {"cout": $}
    -> {"ok", "donnees" (JSON lu ou None), "cout" ($ reel), "raison" (francais si pas ok), "jetons", "modele" (celui
       qui a servi), "request_id", "repli" (un modele de repli a servi), "estimation" ($), "secondes", "note"}"""
    debut = time.time()
    r = reglages()
    modele = modele if modele in MODELES else modele_pour(tache, r)
    nom_video = cle_video(video)
    res = {'ok': False, 'donnees': None, 'cout': 0.0, 'raison': '', 'jetons': _jetons_vides(), 'modele': modele,
           'request_id': None, 'repli': False, 'estimation': 0.0, 'secondes': 0.0, 'note': ''}
    if not r['actif']:
        return {**res, 'raison': f'Claude est éteint dans les réglages. {RELAIS}'}
    cle = _cle()
    if not cle:
        return {**res, 'raison': f'Aucune clé Claude (ANTHROPIC_API_KEY dans cles-api.env). {RELAIS}'}
    if not _sdk():
        return {**res, 'raison': f'Module « anthropic » absent du moteur (runtime/venv). {RELAIS}'}
    if not isinstance(schema, dict) or not schema:
        return {**res, 'raison': f'Schéma de réponse manquant (appel de « {str(tache)[:40]} »). {RELAIS}'}
    if not _texte_contenu(contenu).strip():
        return {**res, 'raison': f'Rien à envoyer à Claude (contenu vide). {RELAIS}'}
    try:
        blocs, n_img, t_img = _blocs_images(images, r['largeur_images'])
    except Exception as e:
        return {**res, 'raison': f'Image illisible pour Claude : {_masquer(str(e))[:160]}. {RELAIS}'}
    tache = str(tache or 'appel')[:40]
    if effort not in EFFORTS:
        effort = _effort_pour(tache, r)
    try:
        max_tokens = int(min(max(int(max_tokens), 16), SORTIE_MAX))
    except (TypeError, ValueError):
        max_tokens = 8000
    sortie, impose = max_tokens, None
    if isinstance(estimation, dict):
        if isinstance(estimation.get('cout'), (int, float)) and not isinstance(estimation.get('cout'), bool):
            impose = max(0.0, float(estimation['cout']))
        if isinstance(estimation.get('sortie'), (int, float)) and not isinstance(estimation.get('sortie'), bool):
            sortie = int(estimation['sortie'])
    elif isinstance(estimation, (int, float)) and not isinstance(estimation, bool) and estimation > 0:
        sortie = int(estimation)
    sortie = max(1, min(sortie, max_tokens))
    est = impose if impose is not None else estimer(systeme, contenu, sortie=sortie, modele=modele, schema=schema,
                                                    jetons_images=t_img)
    res['estimation'] = est

    with _verrou_local:  # controle du budget + reservation (les appels en vol du processus comptent)
        refus = _refus_budget(_charger(), r, nom_video, est)
        if refus:
            return {**res, 'raison': refus}
        jeton = object()
        _en_cours[jeton] = (nom_video, est)
    msg, rid, erreur, genre, notes = None, None, '', '', []
    servi, repli, donnees, ok, secondes = modele, False, None, False, 0.0
    c, jetons = 0.0, _jetons_vides()
    try:
        sans = set(_sans_session.get(modele, ()))
        try:
            client = _client(cle)
        except Exception as e:
            client, (erreur, genre) = None, _erreur(e)
        for _ in range(2 if client is not None else 0):
            params = _parametres(modele, systeme, contenu, blocs, schema, effort, max_tokens, sans)
            try:
                msg, rid = _envoyer(client, params)
                break
            except Exception as e:
                champs = _champs_refuses(e, params) - sans
                if champs and not notes:  # une seule relance (un 400 n'est pas facture)
                    sans |= champs
                    _sans_session.setdefault(modele, set()).update(champs)
                    notes.append(f"relancé sans {', '.join(sorted(champs))} (refusé par l'API pour ce modèle)")
                    continue
                (erreur, genre), rid = _erreur(e), getattr(e, 'request_id', None)
                if genre == 'delai':
                    notes.append('pas de réponse : coût inconnu (la demande a peut-être été facturée)')
                break
        if msg is not None:
            try:
                usage = _champ(msg, 'usage')
                servi = str(_champ(msg, 'model') or modele)
                c, jetons, note_prix = detail_cout(usage, modele, servi)
                if note_prix:
                    notes.append(note_prix)
                repli = any(_champ(it, 'type') == 'fallback_message' for it in (_champ(usage, 'iterations') or []))
                donnees, erreur, genre = _lire(msg)
            except Exception as e:  # forme de reponse imprevue : jamais d'exception vers le montage
                donnees, erreur, genre = None, f'Réponse de Claude inattendue ({_masquer(str(e))[:120]}). {RELAIS}', 'reponse'
        jetons['images'] = n_img
        ok = msg is not None and not erreur
        secondes = round(time.time() - debut, 1)
        entree = {'date': _maintenant(), 'tache': tache, 'video': nom_video, 'modele': servi, 'modele_demande': modele,
                  'effort': effort if modele in AVEC_EFFORT and 'effort' not in sans else None, 'jetons': jetons,
                  'cout': c, 'request_id': rid, 'ok': ok, 'erreur': erreur or None, 'type_erreur': genre or None,
                  'repli': repli, 'note': '; '.join(notes) or None, 'secondes': secondes}
        try:
            _inscrire(entree)
        except Exception as e:  # l'appel a eu lieu : on le dit, sans bloquer le montage
            notes.append(f'registre des coûts non mis à jour ({_masquer(str(e))[:80]})')
    except Exception as e:  # defaut imprevu de ce module : jamais d'exception vers le montage (chemin local)
        ok, erreur = False, f'Erreur inattendue avec Claude : {_masquer(str(e))[:160]}. {RELAIS}'
    finally:
        with _verrou_local:
            _en_cours.pop(jeton, None)
    return {**res, 'ok': ok, 'donnees': donnees if ok else None, 'cout': c, 'raison': erreur, 'jetons': jetons,
            'modele': servi, 'request_id': rid, 'repli': repli, 'note': '; '.join(notes), 'secondes': secondes}


def essai(modele=None):
    """« claude test » : UN seul tout petit appel reel (cle, credit, reseau, sortie structuree) ; 50 jetons de sortie au
    plus. Defaut : Haiku 4.5 (le moins cher, ~0,0005 $) ; modele : un autre modele de MODELES (Sonnet / Opus : verifie
    aussi l'effort et le repli serveur)."""
    m = modele if modele in MODELES else 'claude-haiku-4-5'
    schema = {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}, 'required': ['ok'], 'additionalProperties': False}
    r = appeler('test', 'Tu vérifies une connexion. Réponds seulement par le JSON demandé.', 'Réponds {"ok": true}.',
                schema, effort='low', max_tokens=50, modele=m)
    if r['ok'] and (r['donnees'] or {}).get('ok') is not True:
        r['ok'], r['raison'] = False, f'Réponse de Claude inattendue pour le test. {RELAIS}'
    r['cout_texte'] = _argent(r['cout'])
    return r
