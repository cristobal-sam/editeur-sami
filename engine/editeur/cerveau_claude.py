"""Cerveau creatif par Claude (en option) : UN appel structure par montage, garde dans le reel, verifie par les regles.

Claude lit la transcription numerotee du montage (plus le script, le sujet, la marque et les regles du style) et rend :
le message de la pub, son public et sa promesse ; les temps du recit (accroche, tension, solution, preuve, explication,
appel a l'action) ; les mots forts des sous-titres ; les fautes de transcription ; le bandeau d'accroche ; le texte des
cartes (notification, chiffre, liste, bouton, mot) ; le debut de l'appel a l'action ; un titre court.

Argent : UN appel par montage (claude_api.appeler, tache « cerveau », modele et effort des reglages). Le resultat est
garde dans reel["claude"]["cerveau"] = {signature, modele, date, cout, resultat, ...}. La signature ne depend que du
montage (plans, prises, instants des mots, mots coupes) : un changement de style, une reouverture, « Relancer l'IA » ou un
nouveau montage automatique des memes mots relisent ce resultat sans rappeler Claude. --forcer (ligne de commande) refait
l'appel. Entree compacte : un mot = « numero:mot », ponctuation seule omise, script tronque. Un appel PAYE sans resultat
utilisable (refus, reponse coupee ou illisible) est note dans reel["claude"]["cerveau_echec"] : le meme montage avec le
meme modele n'est pas repaye (sauf --forcer). Un seul cerveau a la fois par montage (verrou entre processus) : un
« Relancer l'IA » pendant un montage automatique attend puis relit le resultat au lieu de payer un 2e appel.

Tout est verifie par les regles locales AVANT usage et ce qui ne passe pas est ecarte (liste « ecartes ») : mots outils et
mots vagues (reel._units), un mot par idee et jamais deux groupes de sous-titres voisins (reel_highlights), chiffres dits,
rien d'invente (mots ancres dans la parole), francais (orthographe.verifier), bandeau (auto._banner_ok), titres de
notification (galerie.valid_title), rien sur l'accroche sauf le bandeau. Les modules qui demandaient l'IA locale lisent ce
resultat d'abord (reel.rehighlight, auto._finish, galerie, creative, graphismes) ; sans resultat utilisable (Claude eteint,
pas de cle, plafond, credit epuise, hors ligne, refus, reponse illisible), leur chemin local (Qwen et regles) reste
exactement celui d'avant. Retouches a la main (hlAuto, mot corrige apres l'appel) et verrous toujours respectes ; la
relecture de sobriete passe apres.

Un element d'un plan dont la prise ou les mots ont change depuis l'appel (empreinte reel._words_sig) n'est plus utilise.

Ligne de commande (une ligne JSON) : python -m editeur.cerveau_claude <dossier_projet> --reel script [--forcer]
EDITEUR_CLAUDE=0 eteint ce module ; EDITEUR_LLM=0 (tests « sans IA ») aussi, sauf EDITEUR_CLAUDE=1.
Tests (faux client, aucun appel reel) : docs/claude-api/tests/test_cerveau.py."""
import argparse
import copy
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from contextlib import contextmanager
from pathlib import Path

from . import claude_api, montage, verrous
from .script import normalize

VERSION = 1          # forme du resultat et de la consigne : la changer refait l'appel (signature)
TACHE = 'cerveau'
ROLES = ('accroche', 'tension', 'solution', 'preuve', 'explication', 'cta')
ROLE_CREATIF = {'tension': 'probleme'}  # creative.py appelle « probleme » le temps « Tension »
TYPES = ('notification', 'chiffre', 'liste', 'bouton', 'mot')
SORTIE_MAX = 10000   # jetons de sortie au plus (reflexion comprise) : sert aussi a l'estimation haute du budget
SCRIPT_MAX = 2500    # caracteres du script ecrit envoyes au plus
ACCROCHE_MAX = 12.0  # s : l'accroche du recit ne depasse jamais 12 s ni 30 % de la video
GARDE_ECARTES = 40
ATTENTE_VERROU = 200.0  # s : un 2e traitement du meme montage attend la fin du 1er (appel <= 120 s + 2 reprises du SDK)

LANGUES = {'fr': 'français (Québec)', 'en': 'anglais', 'es': 'espagnol', 'de': 'allemand', 'it': 'italien', 'pt': 'portugais'}
# ce que chaque grammaire de style montre par-dessus l'image (design.mode du style)
CASES = {'produit': 'notifications, chiffres, listes, bouton d’appel à l’action',
         'tech': 'notifications de téléphone',
         'editorial': 'mots géants (les mots forts)', 'collage': 'autocollants (les mots forts)',
         'infographie': 'chiffres', 'comparatif': 'chiffres comparés', 'hormozi': 'emojis',
         'documentaire': 'titres discrets', None: 'sous-titres seulement'}
# mots anglais courants (titres de carte ecrits en anglais dans une video en francais)
_ANGLAIS = set('new received sent reply replied missed incoming free week weeks day days learn waiting hours save '
               'cheaper faster call calls now today click button offer trial'.split())
# un mot qui porte le sens : une « correction » ne le change jamais en un autre
_SENS = set('ne n pas plus jamais rien aucun aucune non moins sans personne guere not no never none nothing'.split())
# niveau de langue quebecois : jamais « corrige »
_QUEBECOIS = set('pis ben pantoute toe moe icitte faque tse chu ouin astheure tantot frette char blonde chum'.split())

_MOT = {'type': 'object', 'properties': {'clip': {'type': 'string'}, 'i': {'type': 'integer'}},
        'required': ['clip', 'i'], 'additionalProperties': False}
SCHEMA = {
    'type': 'object',
    'properties': {
        'message': {'type': 'string'},
        'public': {'type': 'string'},
        'promesse': {'type': 'string'},
        'beats': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'role': {'type': 'string', 'enum': list(ROLES)}, 'debut_mot': _MOT, 'fin_mot': _MOT,
                           'raison': {'type': 'string'}},
            'required': ['role', 'debut_mot', 'fin_mot', 'raison'], 'additionalProperties': False}},
        'mots_forts': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'clip': {'type': 'string'}, 'i0': {'type': 'integer'}, 'i1': {'type': 'integer'},
                           'raison': {'type': 'string'}},
            'required': ['clip', 'i0', 'i1', 'raison'], 'additionalProperties': False}},
        'corrections': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'clip': {'type': 'string'}, 'i': {'type': 'integer'}, 'avant': {'type': 'string'},
                           'apres': {'type': 'string'}, 'raison': {'type': 'string'}},
            'required': ['clip', 'i', 'avant', 'apres', 'raison'], 'additionalProperties': False}},
        'bandeau': {'anyOf': [{'type': 'object', 'properties': {'texte': {'type': 'string'}}, 'required': ['texte'],
                               'additionalProperties': False}, {'type': 'null'}]},
        'cartes': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'beat': {'type': 'integer'}, 'type': {'type': 'string', 'enum': list(TYPES)},
                           'texte': {'type': 'string'}, 'secondaire': {'type': 'string'}, 'raison': {'type': 'string'}},
            'required': ['beat', 'type', 'texte', 'secondaire', 'raison'], 'additionalProperties': False}},
        'cta': {'anyOf': [{'type': 'object', 'properties': {'clip': {'type': 'string'}, 'i0': {'type': 'integer'}},
                           'required': ['clip', 'i0'], 'additionalProperties': False}, {'type': 'null'}]},
        'titre': {'type': 'string'},
    },
    'required': ['message', 'public', 'promesse', 'beats', 'mots_forts', 'corrections', 'bandeau', 'cartes', 'cta', 'titre'],
    'additionalProperties': False,
}

# Consigne STABLE (mise en cache par claude_api) : tout ce qui est propre a la video va dans le contenu.
SYSTEME = """Tu es le directeur créatif et le monteur principal de publicités courtes (reels verticaux) pour un entrepreneur du Québec. On te donne la transcription EXACTE d'un montage déjà coupé, plan par plan : chaque mot est précédé de son numéro dans le plan (« 12:mot ») ; un numéro absent est un mot coupé. Tu ne vois pas l'image. Tu décides ce qui sera mis en valeur ; un moteur local vérifie tout et retire ce qui enfreint une règle.

Règles absolues
1. Rien d'inventé : aucun chiffre, résultat, promesse, nom ou fait qui n'est pas dit. Les textes à l'écran reprennent les mots dits (reformulation courte permise, même sens).
2. Vise toujours les mots par leur plan et leur numéro, exactement comme dans la transcription.
3. Sobriété de monteur : un seul élément par-dessus l'image à la fois ; rien sur l'accroche sauf le bandeau ; au plus une carte par temps du récit, seulement si elle aide à comprendre.
4. Langue correcte (accords, accents, infinitifs), dans la langue de la vidéo ; textes courts, sans point final.

Champs
- message : l'idée de la vidéo en une phrase. public : à qui elle parle (quelques mots). promesse : le bénéfice promis, tel qu'il est dit.
- beats : le récit dans l'ordre, sans chevauchement, qui couvre toute la parole. Le premier est toujours « accroche » (la première phrase, parfois deux, 12 s au plus). Rôles : accroche ; tension (le problème vécu) ; solution (ce qui est proposé, comment ça marche) ; preuve (chiffre, garantie, fait vérifiable dit) ; explication ; cta (ce qui est demandé au spectateur). debut_mot et fin_mot : premier et dernier mot du temps. raison : 10 mots au plus.
- mots_forts : les mots en couleur des sous-titres. Environ un par idée (une phrase, ou un morceau de longue phrase), seulement s'il porte le message : un chiffre avec son unité (« cinq fois moins cher », « trois heures »), le bénéfice, la douleur ou le coût, la marque, un verbe fort, le texte du bouton. i0..i1 : un mot, ou 2 à 4 mots qui se lisent ensemble. Jamais un petit mot seul (le, de, vos, est, pour, que, ça, vous...) ni un verbe vague (faire, dire, avoir, aller, mettre). Pas deux mots en couleur dans des sous-titres qui se suivent. Un mot fort dans l'accroche et un dans l'appel à l'action. raison : 6 mots au plus.
- corrections : fautes de transcription seulement, un mot à la fois : homophones et accords (« transférez » après « de » -> « transférer » ; consigne donnée à « vous » « appuyer » -> « appuyez » ; « sont closé » -> « closés »), mot mal entendu évident (« Pi » -> « Puis »). avant : le mot exactement comme il est écrit ; apres : UN seul mot corrigé. Ne change jamais le sens, un nom propre, un chiffre, la ponctuation ni le niveau de langue (québécois permis : « pis », « ben »). Dans le doute, rien.
- bandeau : titre en haut de l'image pendant l'accroche, 7 mots au plus, en MAJUSCULES, une phrase naturelle et correcte qui pique la curiosité, faite de mots dits dans la vidéo, jamais la première phrase recopiée ; null si aucun bon titre.
- cartes : éléments à l'écran, jamais pendant l'accroche, au plus un par temps. beat = numéro du temps dans « beats » (0 = le premier). Types : notification (titre réaliste d'une notification de téléphone, 2 à 6 mots, ex. « Nouveau lead reçu », « Lead en attente depuis 3 h » ; secondaire vide) ; chiffre (le chiffre dit avec son unité, ex. « 5× moins cher » ; secondaire vide) ; liste (texte : titre de 2 ou 3 mots ; secondaire : 2 à 4 éléments dits, 1 à 4 mots chacun, séparés par « | ») ; bouton (texte : l'action EXACTE dite, mot pour mot, ex. « En savoir plus » ; secondaire : l'offre dite juste avant, ex. « 1 semaine gratuite », sinon vide) ; mot (un seul mot fort dit, affiché en géant ; secondaire vide). Préfère les types que le style montre. raison : 10 mots au plus.
- cta : premier mot de la dernière demande d'action (null s'il n'y en a pas).
- titre : titre court de la vidéo (3 à 6 mots) pour la liste des vidéos.
Réponds seulement avec le JSON demandé."""


# ---------- petits outils ----------
def _eteint_env():
    """Claude coupe pour ce processus : EDITEUR_CLAUDE=0, ou EDITEUR_LLM=0 (« aucune IA », tests) sans EDITEUR_CLAUDE=1."""
    if os.environ.get('EDITEUR_CLAUDE') == '0':
        return True
    return os.environ.get('EDITEUR_LLM', '1') == '0' and os.environ.get('EDITEUR_CLAUDE') != '1'


def _actif():
    """Claude permis (processus + reglage « actif ») : un resultat garde n'est utilise que dans ce cas. Pas d'appel."""
    if _eteint_env():
        return False
    try:
        return bool(claude_api.reglages().get('actif'))
    except Exception:
        return False


def _visible(w):
    return isinstance(w, dict) and not w.get('cut') and bool(str(w.get('w') or '').strip())


def _texte(x, n=200):
    return re.sub(r'\s+', ' ', str(x or '')).strip()[:n]


def _propre(x):
    """Texte d'ecran : espaces, guillemets et ponctuation de fin retires (la longueur est controlee par l'appelant)."""
    t = re.sub(r'\s+', ' ', str(x or '')).strip().strip('«»"“”').strip()
    return t.rstrip('.;,: ').strip()


def _sans_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', str(s)) if unicodedata.category(c) != 'Mn')


def _coeur(w):
    """Mot sans la ponctuation qui l'entoure (« «transférez», » -> « transférez »)."""
    from .orthographe import _parts
    return _parts(str(w or '').strip())[1].replace('’', "'")


def _distance(a, b):
    """Distance d'edition (Levenshtein) entre deux mots."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _jetons(texte):
    return [t for t in (normalize(x).strip("'") for x in re.split(r"[\s'’\-|]+", str(texte or ''))) if t]


def _nombres(texte):
    """Nombres ecrits dans un texte d'ecran : chiffres et nombres en lettres (sauf « un / une », articles)."""
    from .graphismes import NUMBER_WORDS
    t = str(texte or '').replace('×', ' ')
    out = {float(d.replace(',', '.')) for d in re.findall(r'\d+(?:[.,]\d+)?', t)}
    out |= {float(NUMBER_WORDS[x]) for x in _jetons(t) if x in NUMBER_WORDS and x not in ('un', 'une')}
    return out


def _langue_ok(texte, lang):
    """Texte d'ecran dans la langue de la video et sans faute probable (orthographe.verifier, francais)."""
    if lang != 'fr':
        return True
    from . import orthographe
    from .reel import STOP_EN, STOP_FR
    toks = _jetons(texte)
    en = sum(1 for x in toks if (x in STOP_EN and x not in STOP_FR) or x in _ANGLAIS)
    fr = sum(1 for x in toks if x in STOP_FR and x not in STOP_EN)
    if en and en >= fr:
        return False
    t = str(texte or '')
    return not orthographe.verifier(t.lower() if t.isupper() else t, 'fr')


def _temps(reel):
    """{(plan, indice): (debut, fin)} dans le montage (meme calcul approche que creative._sentences et galerie._times :
    duree des plans, vitesse ; sans le resserrage) et la duree totale."""
    out, elapsed = {}, 0.0
    for c in reel.get('clips') or []:
        speed = c.get('speed') or 1
        t0 = float(c.get('in') or 0)
        for i, w in enumerate(c.get('words') or []):
            if isinstance(w, dict) and 'start' in w:
                a = elapsed + max(0.0, float(w['start']) - t0) / speed
                b = elapsed + max(0.0, float(w.get('end', w['start'])) - t0) / speed
                out[(c['id'], i)] = (round(a, 3), round(max(a, b), 3))
        elapsed += max(0.0, float(c.get('out') or 0) - t0) / speed
    return out, elapsed


def _ordre(reel):
    """Tous les mots du montage, dans l'ordre : [(plan, indice)]."""
    return [(c['id'], i) for c in reel.get('clips') or [] for i in range(len(c.get('words') or []))]


def _style(reel, style=None):
    if isinstance(style, dict):
        return style
    try:
        from .reel import list_templates
        tid = style or reel.get('template')
        return next((t for t in list_templates() if t['id'] == tid), None) or {}
    except Exception:
        return {}


def signature(reel):
    """Empreinte du MONTAGE (pas du style) : plans dans l'ordre, prise, instant de chaque mot et mots coupes. Le texte n'y
    entre pas : une correction (de Claude ou du monteur) ne relance pas d'appel."""
    h = hashlib.sha256(f'cerveau-v{VERSION}'.encode())
    for c in reel.get('clips') or []:
        h.update(f"|{c.get('id')}|{c.get('source')}|".encode('utf-8'))
        for w in c.get('words') or []:
            if isinstance(w, dict):
                h.update(f"{float(w.get('start') or 0):.2f}{'x' if w.get('cut') else ''},".encode())
    return h.hexdigest()[:20]


def _empreintes(reel):
    from .reel import _words_sig
    return {c['id']: _words_sig(c.get('words') or []) for c in reel.get('clips') or [] if isinstance(c.get('words'), list)}


def _marque(reel, brand=None):
    """Nom de marque a donner a Claude : charte du client, sinon la marque de l'utilisateur si elle est dite."""
    name = ((brand or {}).get('name') or '').strip()
    if name:
        return name
    try:
        from .galerie import app_name
        n = app_name(reel)
        return '' if n == 'Messages' else n
    except Exception:
        return ''


def _script(project):
    """Blocs du script ecrit (intention ; peut contenir des fautes) ; rien en mode sans script."""
    s = (project or {}).get('script') or {}
    if not s.get('blocks') or s.get('title') == 'Sans script':
        return []
    out, total = [], 0
    for b in s['blocks']:
        t = _texte(b.get('text'), 2000)
        if not t:
            continue
        t = t[:max(0, SCRIPT_MAX - total)]
        if not t:
            break
        out.append((str(b.get('id') or ''), t))
        total += len(t)
    return out


# ---------- invite ----------
def invite(reel, info=None, style=None, marque=None, project=None):
    """-> (systeme, contenu) : consigne stable (mise en cache) et texte propre a cette video, compact."""
    from . import sobriete
    from .reel import reel_language
    tpl = _style(reel, style)
    lang = reel_language(reel)
    info = info or reel.get('auto') or {}
    temps, total = _temps(reel)
    mode = (tpl.get('design') or reel.get('design') or {}).get('mode')
    b = sobriete.budget(tpl)
    mots = [{'w': w['w'], 'start': temps[(c['id'], i)][0], 'end': temps[(c['id'], i)][1]}
            for c in reel.get('clips') or [] for i, w in enumerate(c.get('words') or []) if _visible(w) and (c['id'], i) in temps]
    hook = sobriete.accroche_fin(mots, total, b) if mots else 0.0
    lignes = [f"Vidéo : {info.get('typeLabel') or info.get('type') or 'vidéo'} ; langue : {LANGUES.get(lang, lang)} ; "
              f"durée du montage : {total:.0f} s."]
    if marque:
        lignes.append(f'Marque : {marque}.')
    bandeau = (tpl.get('banner') or {}).get('enabled', True)
    lignes.append(f"Style : {tpl.get('name') or reel.get('template') or 'inconnu'} ({tpl.get('id') or reel.get('template') or '-'}). "
                  f"Ce style montre à l'écran : {CASES.get(mode, CASES[None])} ; dans tous les styles, graphismes proposés : "
                  f"chiffre, liste de bénéfices, mot géant. Au plus {b['par_minute']} éléments par minute, {b['ecart']:g} s "
                  f"entre deux, un seul à la fois. Accroche ≈ {hook:.1f} s : rien d'autre que le bandeau"
                  + ('' if bandeau else ' (ce style cache le bandeau : propose-le quand même s’il est bon)') + '.')
    script = _script(project)
    if script:
        lignes.append("Script écrit (intention ; il peut contenir des fautes) :")
        lignes += [f'[{k}] {t}' for k, t in script]
    lignes.append('Transcription du montage (numéro:mot ; numéro absent = mot coupé) :')
    cta = reel.get('ctaBlock')
    for c in reel.get('clips') or []:
        vis = [(i, w) for i, w in enumerate(c.get('words') or []) if _visible(w)]
        if not vis:
            continue
        t0 = temps.get((c['id'], vis[0][0]), (0.0, 0.0))[0]
        lignes.append(f"[{c['id']}] bloc {c.get('block') or '-'}{' (appel à l’action du script)' if cta and c.get('block') == cta else ''}"
                      f' · {t0:.1f} s')
        lignes.append(' '.join(f"{i}:{str(w['w']).strip()}" for i, w in vis))
    return SYSTEME, '\n'.join(lignes)


# ---------- verification de la reponse ----------
def valider(reel, data, style=None):
    """Reponse de Claude -> (resultat verifie, ecartes). Chaque element est controle par les regles locales ; un element
    qui ne passe pas est retire (raison courte en francais dans « ecartes »), jamais corrige en silence."""
    from . import galerie, graphismes, sobriete
    from .reel import _brands, _caption_words, _units, _words, reel_highlights, reel_language, NUMBERS, STOP, WEAK
    NUMBER_WORDS = graphismes.NUMBER_WORDS
    _NOMBRES = set(NUMBER_WORDS) | NUMBERS  # nombres en lettres : jamais « corriges » en un autre nombre ou un autre mot
    data = data if isinstance(data, dict) else {}
    ecartes = []

    def ecarter(quoi, pourquoi):
        if len(ecartes) < GARDE_ECARTES:
            ecartes.append(f'{quoi} : {pourquoi}')

    lang = reel_language(reel)
    clips = {c['id']: c for c in reel.get('clips') or [] if isinstance(c.get('words'), list)}
    temps, total = _temps(reel)
    ordre = _ordre(reel)
    pos = {k: n for n, k in enumerate(ordre)}
    tous = _dits_tous(reel)  # nombres dits dans toute la video

    def mot(m, cachable=True):
        """{clip, i} -> (plan, indice) d'un mot garde (et visible si cachable est faux), sinon None."""
        if not isinstance(m, dict):
            return None
        c, i = clips.get(str(m.get('clip'))), m.get('i')
        if c is None or not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(c['words']):
            return None
        w = c['words'][i]
        if not _visible(w) or (not cachable and w.get('hide')) or (c['id'], i) not in temps:
            return None
        return c['id'], i

    def visibles(a, z):
        return [k for k in ordre[pos[a]:pos[z] + 1] if _visible(clips[k[0]]['words'][k[1]]) and k in temps]

    # temps du recit : dans l'ordre, sans chevauchement ; le premier est l'accroche (12 s / 30 % au plus)
    beats, carte_vers = [], {}
    fin_prec = -1
    for n, b in enumerate(data.get('beats') or []):
        b = b if isinstance(b, dict) else {}
        role, a, z = b.get('role'), mot(b.get('debut_mot')), mot(b.get('fin_mot'))
        quoi = f'temps {n + 1}'
        if role not in ROLES:
            ecarter(quoi, 'rôle inconnu')
        elif not a or not z:
            ecarter(quoi, 'mot introuvable ou coupé')
        elif pos[a] > pos[z]:
            ecarter(quoi, 'fin avant le début')
        elif pos[a] <= fin_prec:
            ecarter(quoi, 'chevauche le temps précédent')
        elif role == 'accroche' and beats:
            ecarter(quoi, "une seule accroche, au début")
        else:
            carte_vers[n] = len(beats)
            beats.append({'role': role, 'debut': {'clip': a[0], 'i': a[1]}, 'fin': {'clip': z[0], 'i': z[1]},
                          'raison': _texte(b.get('raison'), 120)})
            fin_prec = pos[z]
    premier = next((k for k in ordre if _visible(clips[k[0]]['words'][k[1]]) and k in temps), None)
    if beats:
        a0 = (beats[0]['debut']['clip'], beats[0]['debut']['i'])
        if beats[0]['role'] != 'accroche' or premier is None or temps[a0][0] - temps[premier][0] > 1.0:
            ecarter('temps du récit', "le premier temps n'est pas l'accroche du début : plan des règles gardé")
            beats, carte_vers = [], {}
    if beats:
        acc = beats[0]
        a, z = (acc['debut']['clip'], acc['debut']['i']), (acc['fin']['clip'], acc['fin']['i'])
        limite = min(ACCROCHE_MAX, 0.3 * total)
        if temps[z][1] > limite:
            dedans = [k for k in visibles(a, z) if temps[k][1] <= limite]
            fins = [k for k in dedans if re.search(r'[.!?…]["»”)\]]*$', str(clips[k[0]]['words'][k[1]]['w']).strip())]
            k = (fins or dedans or [None])[-1]
            if k is None:
                ecarter('accroche', f'plus longue que {limite:.0f} s : plan des règles gardé')
                beats, carte_vers = [], {}
            else:
                ecarter('accroche', f'raccourcie à {temps[k][1]:.1f} s (12 s et 30 % de la vidéo au plus)')
                acc['fin'] = {'clip': k[0], 'i': k[1]}
    if beats:
        parole = temps[ordre[max(pos[k] for k in ordre if _visible(clips[k[0]]['words'][k[1]]) and k in temps)]][1] - temps[premier][0]
        couvert = sum(max(0.0, temps[(b['fin']['clip'], b['fin']['i'])][1] - temps[(b['debut']['clip'], b['debut']['i'])][0])
                      for b in beats)
        if len(beats) < 2 or couvert < 0.5 * max(0.1, parole):
            ecarter('temps du récit', 'trop peu de récit couvert : plan des règles gardé')
            beats, carte_vers = [], {}
    fin_accroche = temps[(beats[0]['fin']['clip'], beats[0]['fin']['i'])][1] if beats else 0.0

    # mots forts : jamais un mot outil ni un mot vague seul, puis la selection commune (un par idee, groupes voisins)
    brands = _brands(reel)
    marques = {normalize(x).replace(' ', '') for x in brands if x}
    unites, spans, vus, proposes = {}, {}, set(), set()
    for n, m in enumerate(data.get('mots_forts') or []):
        m = m if isinstance(m, dict) else {}
        c, i0, i1 = clips.get(str(m.get('clip'))), m.get('i0'), m.get('i1')
        quoi = f"mot fort {n + 1}"
        if c is not None:
            proposes.add(c['id'])  # plan ou Claude voulait des mots forts (tous ecartes -> les regles le reprennent)
        if c is None or not all(isinstance(x, int) and not isinstance(x, bool) for x in (i0, i1)) or not 0 <= i0 <= i1 < len(c['words']):
            ecarter(quoi, 'mot introuvable')
            continue
        quoi = f"« {' '.join(str(w.get('w', '')) if isinstance(w, dict) else str(w) for w in c['words'][i0:i1 + 1])[:40]} »"
        if i1 - i0 > 3:
            ecarter(quoi, 'plus de 4 mots')
            continue
        if any(not _visible(w) or w.get('hide') for w in c['words'][i0:i1 + 1]):
            ecarter(quoi, 'mot coupé ou masqué')
            continue
        if c['id'] not in unites:
            unites[c['id']] = _units(_words(c['words']), lang, marques)
        s = set(range(i0, i1 + 1))
        if not any(set(u['span']) & s for u in unites[c['id']]):
            ecarter(quoi, 'petit mot ou mot vague')
            continue
        if any(s & set(o) for o in spans.get(c['id'], [])) or (c['id'], i0) in vus:
            ecarter(quoi, 'en double')
            continue
        vus.add((c['id'], i0))
        spans.setdefault(c['id'], []).append(list(range(i0, i1 + 1)))
    gardes = []
    if spans:
        # meme selection qu'a l'usage (reel.rehighlight avec cerveau_claude.mots) : tous les plans en mode « Claude »
        liste = [c for c in reel.get('clips') or [] if isinstance(c.get('words'), list)]
        sel = reel_highlights(liste, _caption_words(reel), lang, brands=brands,
                              force={c['id']: spans.get(c['id'], []) for c in liste})
        for cid, ss in spans.items():
            on = set(sel.get(cid) or [])
            for s in ss:
                raison = next((_texte(m.get('raison'), 80) for m in data.get('mots_forts') or []
                               if isinstance(m, dict) and str(m.get('clip')) == cid and m.get('i0') == s[0]), '')
                if on & set(s):
                    gardes.append({'clip': cid, 'i0': s[0], 'i1': s[-1], 'raison': raison})
                else:
                    ecarter(f"« {' '.join(str(clips[cid]['words'][k]['w']) for k in s)[:40]} »",
                            'même idée, mot répété ou sous-titre voisin déjà en couleur')

    # corrections : fautes de transcription seulement (un mot, meme sens, temps des mots inchanges)
    corrections, deja = [], set()
    for n, k in enumerate(data.get('corrections') or []):
        k = k if isinstance(k, dict) else {}
        c, i = clips.get(str(k.get('clip'))), k.get('i')
        quoi = f'correction {n + 1}'
        if c is None or not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(c['words']):
            ecarter(quoi, 'mot introuvable')
            continue
        w = c['words'][i]
        if not isinstance(w, dict):
            ecarter(quoi, 'mot introuvable')
            continue
        cur, av, ap = _coeur(w.get('w')), _coeur(k.get('avant')), _coeur(k.get('apres'))
        quoi = f'« {cur} » -> « {ap} »'
        if w.get('cut'):
            ecarter(quoi, 'mot coupé')
        elif verrous.is_locked(c):
            ecarter(quoi, 'plan verrouillé')
        elif (c['id'], i) in deja:
            ecarter(quoi, 'en double')
        elif not ap or re.search(r'\s', ap) or len(ap) > 40:
            ecarter(quoi, 'un seul mot attendu')
        elif av.lower() != cur.lower():
            ecarter(quoi, "le mot n'est pas celui de la transcription")
        elif ap == cur:
            continue  # rien a changer
        elif re.search(r'\d', cur + ap):
            ecarter(quoi, 'un chiffre ne se corrige pas')
        else:
            a0, b0 = _sans_accents(cur.lower()), _sans_accents(ap.lower())
            if a0 in _QUEBECOIS:
                ecarter(quoi, 'niveau de langue gardé')
            elif ((a0 in _SENS or b0 in _SENS) and a0 != b0) or a0.startswith("n'") != b0.startswith("n'"):
                ecarter(quoi, 'le sens changerait')  # negation (« pas », « n'est » -> « c'est »), plus / moins...
            elif ({a0, b0} & _NOMBRES) and NUMBER_WORDS.get(a0, a0) != NUMBER_WORDS.get(b0, b0):
                ecarter(quoi, 'un chiffre ne se corrige pas')  # « deux » -> « dix », « six » -> « dix », « mille » -> « ville »
            elif sobriete.nom_propre(c['words'], i) and a0 != 'pi':
                ecarter(quoi, 'nom propre')
            elif _distance(a0, b0) > max(2, len(a0) // 3):
                ecarter(quoi, 'trop différent : le sens changerait')
            else:
                deja.add((c['id'], i))
                corrections.append({'clip': c['id'], 'i': i, 'avant': cur, 'apres': ap, 'raison': _texte(k.get('raison'), 80)})

    # bandeau : 7 mots au plus, majuscules, chiffres dits, mots dits (meme racine), pas la 1re phrase recopiee, correct
    bandeau, bandeau_ecarte = None, False
    bd = data.get('bandeau')
    if isinstance(bd, dict) and _propre(bd.get('texte')):
        t = _propre(bd.get('texte')).upper()
        n = len(t.split())
        bandeau_ecarte = True  # propose mais refuse : le chemin local (IA locale relue) garde la main pour le bandeau
        if not 2 <= n <= 7 or len(t) > 60 or '…' in t or '...' in t:
            ecarter(f'bandeau « {t[:60]} »', '2 à 7 mots attendus')
        elif not _nombres(t) <= tous:
            ecarter(f'bandeau « {t} »', 'chiffre qui n’est pas dit')
        elif not _bandeau_ok(reel, t):
            ecarter(f'bandeau « {t} »', 'mots qui ne sont pas dits, ou première phrase recopiée')
        elif not _langue_ok(t, lang):
            ecarter(f'bandeau « {t} »', 'faute probable ou autre langue')
        else:
            bandeau, bandeau_ecarte = t, False

    # cartes : un temps valide qui n'est pas l'accroche, texte court, chiffres et mots dits, langue correcte
    cartes, prises = [], set()
    for n, ca in enumerate(data.get('cartes') or []):
        ca = ca if isinstance(ca, dict) else {}
        typ, bi = ca.get('type'), ca.get('beat')
        texte, sec = _propre(ca.get('texte')), _propre(ca.get('secondaire'))
        quoi = f'carte « {texte[:40]} »'
        if typ not in TYPES:
            ecarter(quoi, 'type inconnu')
            continue
        if not isinstance(bi, int) or isinstance(bi, bool) or bi not in carte_vers:
            ecarter(quoi, 'temps du récit inconnu')
            continue
        j = carte_vers[bi]
        b = beats[j]
        if b['role'] == 'accroche':
            ecarter(quoi, "rien sur l'accroche sauf le bandeau")
            continue
        if (j, typ) in prises:
            ecarter(quoi, 'déjà une carte de ce type pour ce temps')
            continue
        cles = visibles((b['debut']['clip'], b['debut']['i']), (b['fin']['clip'], b['fin']['i']))
        ws = [clips[k[0]]['words'][k[1]] for k in cles]
        dits = _dits(reel, cles)
        mots_t = texte.split()
        if not texte or '…' in texte + sec or '...' in texte + sec or galerie.TECH_LABEL.search(texte + ' ' + sec):
            ecarter(quoi, 'texte vide ou technique')
            continue
        if not _nombres(texte) <= dits or not _nombres(sec) <= dits:
            ecarter(quoi, 'chiffre qui n’est pas dit dans ce temps')
            continue
        if not _langue_ok(texte, lang) or (sec and typ != 'liste' and not _langue_ok(sec, lang)):
            ecarter(quoi, 'faute probable ou autre langue')
            continue
        carte = {'beat': j, 'type': typ, 'texte': texte, 'secondaire': '', 'raison': _texte(ca.get('raison'), 120)}
        if typ == 'notification':
            if not 2 <= len(mots_t) <= 6 or len(texte) > 42 or not graphismes._anchored(ws, texte):
                ecarter(quoi, 'notification de 2 à 6 mots sur ce qui est dit')
                continue
        elif typ == 'chiffre':
            if not _nombres(texte) or len(mots_t) > 5 or len(texte) > 32:
                ecarter(quoi, 'un chiffre dit, 5 mots au plus')
                continue
        elif typ == 'liste':
            items = [_propre(x) for x in sec.split('|') if _propre(x)]
            if not 1 <= len(mots_t) <= 4 or not 2 <= len(items) <= 4 or any(len(x.split()) > 4 or len(x) > 32 for x in items):
                ecarter(quoi, 'liste de 2 à 4 éléments courts')
                continue
            if not all(graphismes._anchored(ws, x) and _langue_ok(x, lang) for x in items):
                ecarter(quoi, 'élément de liste qui n’est pas dit')
                continue
            carte['secondaire'] = '|'.join(items)
        elif typ == 'bouton':
            ancre = _suite(clips, cles, texte)
            if not 1 <= len(mots_t) <= 5 or ancre is None:
                ecarter(quoi, "le texte du bouton n'est pas dit mot pour mot")
                continue
            if temps[ancre][0] < fin_accroche:
                ecarter(quoi, "rien sur l'accroche sauf le bandeau")
                continue
            if sec:
                if len(sec.split()) > 5 or not _nombres(sec) <= tous or not graphismes._anchored(
                        [w for c in clips.values() for w in c['words'] if _visible(w)], sec, every=True) or not _langue_ok(sec, lang):
                    ecarter(f'offre « {sec[:40]} »', "l'offre n'est pas dite : bouton sans offre")
                    sec = ''
            carte.update(secondaire=sec, ancre={'clip': ancre[0], 'i': ancre[1]}, longueur=len(mots_t))
        elif typ == 'mot':
            cible = normalize(_coeur(texte)).strip("'")
            ancre = next((k for k in cles if normalize(_coeur(clips[k[0]]['words'][k[1]]['w'])).strip("'") == cible
                          and not clips[k[0]]['words'][k[1]].get('hide')), None)
            if len(mots_t) != 1 or ancre is None or cible in STOP or cible in WEAK or len(cible) < 4:
                ecarter(quoi, 'un seul mot fort dit dans ce temps')
                continue
            carte['ancre'] = {'clip': ancre[0], 'i': ancre[1]}
        prises.add((j, typ))
        cartes.append(carte)

    # appel a l'action : un mot garde apres l'accroche
    cta = None
    m = data.get('cta')
    if isinstance(m, dict):
        k = mot({'clip': m.get('clip'), 'i': m.get('i0')})
        if k and temps[k][0] >= fin_accroche:
            cta = {'clip': k[0], 'i0': k[1]}
        else:
            ecarter("début de l'appel à l'action", 'mot introuvable, coupé ou dans l’accroche')

    titre = _propre(data.get('titre'))
    if titre and (not 2 <= len(titre.split()) <= 8 or len(titre) > 60 or not _nombres(titre) <= tous
                  or not _langue_ok(titre, lang)):
        ecarter(f'titre « {titre[:60]} »', 'titre de 2 à 8 mots, sans chiffre inventé')
        titre = ''
    # message, public, promesse : affiches dans la direction creative ; un chiffre qui n'est pas dit les retire
    textes = {}
    for k, n in (('message', 240), ('public', 160), ('promesse', 240)):
        textes[k] = _texte(data.get(k), n)
        if textes[k] and not _nombres(textes[k]) <= tous:
            ecarter(k, 'chiffre qui n’est pas dit')
            textes[k] = ''
    return {**textes,
            'beats': beats, 'mots_forts': gardes, 'corrections': corrections, 'bandeau': bandeau, 'cartes': cartes,
            'cta': cta, 'titre': titre, 'bandeau_ecarte': bandeau_ecarte, 'mots_plans': sorted(proposes)}, ecartes


def _dits(reel, cles):
    """Nombres dits par ces mots [(plan, indice)] (chiffres, nombres en lettres, avec leur unite)."""
    from .galerie import _said_numbers
    par = {}
    for cid, i in cles:
        par.setdefault(cid, []).append(i)
    clips = {c['id']: c for c in reel.get('clips') or []}
    out = set()
    for cid, idx in par.items():
        if cid in clips:
            out |= _said_numbers(clips[cid], idx)
    return out


def _dits_tous(reel):
    return _dits(reel, [(c['id'], i) for c in reel.get('clips') or [] for i, w in enumerate(c.get('words') or []) if _visible(w)])


def _bandeau_ok(reel, texte):
    """Meme verification que le bandeau du montage automatique (auto._banner_ok) : chaque mot fort est dit (meme racine)
    et ce n'est pas la premiere phrase recopiee."""
    from .auto import _banner_ok
    essai = {**reel, 'banner': {'text': texte}, 'suggestions': {'banners': [texte]}}
    return bool(_banner_ok(essai))


def _suite(clips, cles, texte):
    """Premier mot (plan, indice) ou le texte est dit mot pour mot dans ces mots (ponctuation ignoree), sinon None."""
    voulu = [x for x in (normalize(_coeur(t)).strip("'") for t in str(texte).split()) if x]
    if not voulu:
        return None
    mots = [(k, normalize(_coeur(clips[k[0]]['words'][k[1]]['w'])).strip("'")) for k in cles]
    mots = [(k, x) for k, x in mots if x]
    for n in range(len(mots) - len(voulu) + 1):
        if [x for _, x in mots[n:n + len(voulu)]] == voulu and len({k[0] for k, _ in mots[n:n + len(voulu)]}) == 1:
            return mots[n][0]
    return None


# ---------- appel ----------
def _local(raison, cout=0.0, **extra):
    return {'ok': False, 'source': 'local', 'raison': raison, 'cout': round(float(cout or 0), 6), **extra}


def _resume(entree, source):
    """Compte rendu court : cout de CE traitement (0 $ pour un resultat garde, deja paye a son appel)."""
    res = entree.get('resultat') or {}
    paye = float(entree.get('cout') or 0)
    return {'ok': True, 'source': source, 'raison': '', 'modele': entree.get('modele'), 'cout': paye if source == 'claude' else 0.0,
            'cout_texte': claude_api._argent(paye) if source == 'claude' else
            f'0,00 $ (résultat gardé, payé {claude_api._argent(paye)} le {str(entree.get("date") or "")[:10]})',
            'titre': res.get('titre') or '', 'ecartes': len(entree.get('ecartes') or []),
            'compte': {k: len(res.get(k) or []) for k in ('beats', 'mots_forts', 'corrections', 'cartes')}}


@contextmanager
def _un_a_la_fois(project_dir, rid, attente=None):
    """Un seul cerveau a la fois pour un meme montage, entre processus (« Relancer l'IA » pendant un montage automatique,
    clic sur « Idées de Claude » au meme moment) : le second attend la fin du premier, puis relit son resultat au lieu de
    payer un 2e appel. Verrou du systeme (rendu tout seul si le processus s'arrete). -> True si pris ; False apres
    l'attente (on n'appelle pas) ; True aussi si aucun verrou n'est possible (comme claude_api : mieux qu'un blocage)."""
    nom = hashlib.sha1(f'{Path(project_dir).resolve()}|{rid}'.encode('utf-8')).hexdigest()[:16]
    chemin = Path(claude_api.VERROU).parent / 'claude-verrous' / f'cerveau-{nom}.lock'
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        f = open(chemin, 'a+b')
    except OSError:
        f = None
    pris = f is None
    fin = time.time() + (ATTENTE_VERROU if attente is None else attente)
    while not pris:
        try:
            f.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            pris = True
        except OSError:
            if time.time() >= fin:
                break
            time.sleep(0.25)
    try:
        yield pris
    finally:
        if f is not None:
            if pris:
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


def _deja(reel, sig, cache=None):
    """Resultat garde pour ce montage (meme version et signature) : celui du reel, sinon celui d'un reel precedent."""
    for e in ((reel.get('claude') or {}).get('cerveau'), cache):
        if isinstance(e, dict) and e.get('version') == VERSION and e.get('signature') == sig and isinstance(e.get('resultat'), dict):
            return e
    return None


def _echec_paye(reel, sig, modele, echec=None):
    """Appel deja PAYE sans resultat utilisable pour ce montage et ce modele (reel, sinon reel precedent), ou None."""
    for e in ((reel.get('claude') or {}).get('cerveau_echec'), echec):
        try:
            paye = float((e or {}).get('cout') or 0) > 0
        except (TypeError, ValueError, AttributeError):
            paye = False
        if isinstance(e, dict) and paye and e.get('version') == VERSION and e.get('signature') == sig and e.get('modele') == modele:
            return e
    return None


def _noter_echec(project_dir, rid, sig, modele, raison, cout):
    """Garde dans le reel un appel paye qui n'a rien donne : le meme montage n'est pas repaye avec le meme modele."""
    try:
        cout = float(cout or 0)
    except (TypeError, ValueError):
        cout = 0.0
    if cout <= 0:
        return  # rien de paye (hors ligne, credit epuise, plafond...) : un nouvel essai ne coute rien de plus
    e = {'version': VERSION, 'signature': sig, 'modele': modele, 'date': time.strftime('%Y-%m-%dT%H:%M:%S'),
         'cout': round(cout, 6), 'raison': _texte(raison, 300)}
    try:
        montage.update(project_dir, rid, lambda x: x.setdefault('claude', {}).__setitem__('cerveau_echec', e))
    except (OSError, ValueError):
        pass


def _local_echec(e):
    raison = _texte(str(e.get('raison') or '').replace(claude_api.RELAIS, ''), 160).rstrip(' .')
    if raison and not raison.startswith('Claude'):
        raison = raison[:1].lower() + raison[1:]
    return _local(f"Claude a déjà lu ce montage le {str(e.get('date') or '')[:10]} sans résultat utilisable"
                  + (f' : {raison}' if raison else '') + f" ; {claude_api._argent(e.get('cout'))} payés. Pour ne pas payer "
                  "deux fois la même chose, l'outil continue en local. Une coupe, une autre prise ou un autre modèle de "
                  "Claude permet de réessayer.")


def _relire(project_dir, rid, e, appliquer):
    """Resultat deja garde (aucun appel) : recopie dans le reel si besoin, corrections posees si demande."""
    if not claude_api.reglages().get('actif'):
        return _local(f"Claude est éteint dans les réglages. {claude_api.RELAIS}")
    entree = copy.deepcopy(e)
    out = _resume(entree, 'garde')
    try:
        out['corrections'] = _enregistrer(project_dir, rid, entree, appliquer)
    except OSError as x:
        return _local(f'Montage occupé : résultat de Claude non recopié ({str(x)[:100]}). {claude_api.RELAIS}')
    return out


def lancer(project_dir, rid='script', info=None, style=None, brand=None, forcer=False, appliquer=True, cache=None,
           echec=None):
    """Cerveau de ce montage : resultat garde (meme signature) ou UN appel a Claude, verifie puis garde dans
    reel["claude"]["cerveau"]. appliquer : les corrections de transcription sont posees (reel en mode « auto » seulement ;
    en mode « suggestion », elles restent des propositions). cache / echec : resultat / appel paye sans resultat d'un reel
    precedent (nouveau montage automatique des memes mots : pas de nouvel appel). forcer : appel meme si ce montage a deja
    ete lu (ou deja paye sans resultat). Ne leve jamais pour un probleme de Claude.
    -> {ok, source ('claude' | 'garde' | 'local'), raison, modele, cout, titre, ecartes, compte, corrections}"""
    project_dir = Path(project_dir)
    if _eteint_env():
        return _local("Claude coupé pour ce traitement (EDITEUR_CLAUDE=0 ou EDITEUR_LLM=0). L'outil continue en local.")
    try:
        reel = montage.load(project_dir, rid)
    except (OSError, ValueError) as e:
        return _local(f'Montage illisible ({str(e)[:120]}).')
    if not any(_visible(w) for c in reel.get('clips') or [] for w in c.get('words') or []):
        return _local('Aucune parole dans ce montage : rien à confier à Claude.')
    sig = signature(reel)
    gardee = None if forcer else _deja(reel, sig, cache)
    if gardee is not None:
        return _relire(project_dir, rid, gardee, appliquer)
    r = claude_api.reglages()
    modele = claude_api.modele_pour(TACHE, r)
    deja = None if forcer else _echec_paye(reel, sig, modele, echec)
    if deja is not None:
        return _local_echec(deja)
    s = claude_api.statut()
    if not s.get('pret'):
        return _local(s.get('raison') or f"Claude n'est pas prêt. {claude_api.RELAIS}")
    with _un_a_la_fois(project_dir, rid) as pris:
        if not pris:
            return _local("Claude lit déjà ce montage pour un autre traitement : l'outil continue en local (aucun "
                          "deuxième appel payé). Relance dans une minute pour reprendre son résultat.")
        try:  # relu sous le verrou : un autre traitement vient peut-etre de garder son resultat
            reel = montage.load(project_dir, rid)
        except (OSError, ValueError) as e:
            return _local(f'Montage illisible ({str(e)[:120]}).')
        sig = signature(reel)
        if not forcer:
            gardee = _deja(reel, sig, cache)
            if gardee is not None:
                return _relire(project_dir, rid, gardee, appliquer)
            deja = _echec_paye(reel, sig, modele, echec)
            if deja is not None:
                return _local_echec(deja)
        try:
            project = json.loads((project_dir / 'project.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            project = None
        systeme, contenu = invite(reel, info, style, _marque(reel, brand), project)
        rep = claude_api.appeler(TACHE, systeme, contenu, SCHEMA, video=(str(project_dir), rid),
                                 effort=r.get('effort_cerveau'), max_tokens=SORTIE_MAX, modele=modele)
        if not rep.get('ok'):
            raison = rep.get('raison') or f'Claude n’a pas répondu. {claude_api.RELAIS}'
            _noter_echec(project_dir, rid, sig, modele, raison, rep.get('cout'))
            return _local(raison, rep.get('cout'), modele=rep.get('modele'))
        try:
            resultat, ecartes = valider(reel, rep.get('donnees'), style)
        except Exception as e:  # reponse imprevue : jamais d'exception vers le montage
            raison = f'Réponse de Claude inutilisable ({str(e)[:120]}). {claude_api.RELAIS}'
            _noter_echec(project_dir, rid, sig, modele, raison, rep.get('cout'))
            return _local(raison, rep.get('cout'))
        entree = {'version': VERSION, 'signature': sig, 'modele': rep.get('modele'), 'modele_demande': modele,
                  'nom': claude_api.NOMS.get(rep.get('modele'), rep.get('modele')),
                  'date': time.strftime('%Y-%m-%dT%H:%M:%S'), 'cout': rep.get('cout', 0.0), 'request_id': rep.get('request_id'),
                  'jetons': rep.get('jetons'), 'repli': bool(rep.get('repli')), 'clips': _empreintes(reel),
                  'resultat': resultat, 'ecartes': ecartes}
        out = _resume(entree, 'claude')
        try:
            out['corrections'] = _enregistrer(project_dir, rid, entree, appliquer)
        except OSError as e:  # rare : reel ouvert ailleurs pendant 1 s ; l'appel est paye mais son resultat n'est pas garde
            return _local(f'Montage occupé : résultat de Claude non enregistré ({str(e)[:100]}). {claude_api.RELAIS}',
                          rep.get('cout'), modele=rep.get('modele'))
        return out


def _enregistrer(project_dir, rid, entree, appliquer):
    """Garde le resultat dans le reel (relu juste avant d'ecrire : une retouche faite pendant l'appel n'est pas perdue) et,
    si demande, pose les corrections. Rien n'est ecrit si rien ne change (resultat deja garde, aucune correction a poser).
    Un reel occupe un instant par un autre lecteur (Windows) : 3 essais. -> nombre de corrections posees."""
    try:
        actuel = montage.load(project_dir, rid)
        essai = {**actuel, 'claude': {**(actuel.get('claude') or {}), 'cerveau': entree}}
        a_poser = appliquer and actuel.get('aiMode') != 'suggestion' and corrections_proposees(essai)
        if (actuel.get('claude') or {}).get('cerveau') == entree and not a_poser:
            return 0
    except (OSError, ValueError):
        pass
    poses, avant = [], list(entree.get('corrections_posees') or [])

    def f(x):
        poses.clear()
        e = dict(entree)
        claude = x.setdefault('claude', {})
        claude['cerveau'] = e
        claude.pop('cerveau_echec', None)  # ce montage a maintenant un resultat
        if appliquer and x.get('aiMode') != 'suggestion':
            poses.extend(appliquer_corrections(x))
            if poses:
                e['corrections_posees'] = (avant + poses)[-60:]
    for essai_n in range(3):
        try:
            montage.update(project_dir, rid, f)
            break
        except PermissionError:
            if essai_n == 2:
                raise
            time.sleep(0.3)
    return len(poses)


# ---------- resultat garde : lecture pour les autres passes ----------
def resultat(reel):
    """Resultat du cerveau utilisable maintenant, sinon None : Claude permis (reglage actif, pas EDITEUR_CLAUDE=0 /
    EDITEUR_LLM=0) et un appel garde dans le reel avec cette version. « _plans » : plans inchanges depuis l'appel (meme
    empreinte des mots) ; les elements des autres plans ne sont plus utilises."""
    e = ((reel or {}).get('claude') or {}).get('cerveau')
    if not isinstance(e, dict) or e.get('version') != VERSION or not isinstance(e.get('resultat'), dict) or not _actif():
        return None
    from .reel import _words_sig
    sigs = e.get('clips') or {}
    plans = {c['id'] for c in reel.get('clips') or [] if isinstance(c.get('words'), list)
             and sigs.get(c['id']) == _words_sig(c['words'])}
    return {**e['resultat'], '_plans': plans, '_modele': e.get('modele'), '_nom': e.get('nom')}


def _bornes(reel, res):
    """Temps du recit dans le montage (temps approches, comme galerie et creative) : [(debut, fin, mots) ou None]."""
    temps, _ = _temps(reel)
    ordre = _ordre(reel)
    pos = {k: n for n, k in enumerate(ordre)}
    clips = {c['id']: c for c in reel.get('clips') or []}
    out = []
    for b in res.get('beats') or []:
        a, z = (b['debut']['clip'], b['debut']['i']), (b['fin']['clip'], b['fin']['i'])
        if a not in pos or z not in pos or pos[a] > pos[z] or a[0] not in res['_plans'] or z[0] not in res['_plans']:
            out.append(None)
            continue
        vis = [k for k in ordre[pos[a]:pos[z] + 1] if k in temps and _visible(clips[k[0]]['words'][k[1]])]
        out.append((temps[vis[0]][0], temps[vis[-1]][1], vis) if vis else None)
    return out


def mots(reel):
    """{plan: [[indices]]} : mots forts de Claude pour reel.reel_highlights (force) ; un plan inchange ou Claude ne propose
    rien -> [] (Claude n'y met rien). None sans resultat utilisable, ou si AUCUN mot fort de Claude ne passe les regles
    (indices faux...) : les regles choisissent alors, comme sans Claude. Un plan dont tous les mots forts proposes sont
    ecartes est laisse aux regles (jamais un plan presque sans couleur parce que Claude s'est trompe de numero)."""
    res = resultat(reel)
    if res is None or not res.get('mots_forts'):
        return None
    gardes = {m.get('clip') for m in res['mots_forts']}
    rates = set(res.get('mots_plans') or ()) - gardes
    out = {cid: [] for cid in res['_plans'] if cid not in rates}
    for m in res['mots_forts']:
        if m.get('clip') in out:
            out[m['clip']].append(list(range(int(m['i0']), int(m['i1']) + 1)))
    return out


def bandeau(reel):
    """Bandeau de Claude (verifie) ; '' : Claude n'en propose pas ; None : pas de resultat, ou bandeau propose mais ecarte
    par les regles (chemin local : bandeau de l'IA locale relu, comme sans Claude)."""
    res = resultat(reel)
    if res is None:
        return None
    if res.get('bandeau'):
        return res['bandeau']
    return None if res.get('bandeau_ecarte') else ''


def beats_creatifs(reel, sentences):
    """Temps du recit de Claude au format de creative.build (memes champs que creative._merge), ou None (regles)."""
    from . import creative
    res = resultat(reel)
    if res is None or not res.get('beats'):
        return None
    clips = {c['id']: c for c in reel.get('clips') or []}
    out = []
    for b, borne in zip(res['beats'], _bornes(reel, res)):
        if not borne:
            continue
        start, end, vis = borne
        role = ROLE_CREATIF.get(b['role'], b['role'])
        texte = ' '.join(str(clips[k[0]]['words'][k[1]]['w']).strip() for k in vis if not clips[k[0]]['words'][k[1]].get('hide'))
        out.append({'id': '', 'role': role, 'label': creative.LABELS[role], 'start': round(start, 3), 'end': round(end, 3),
                    'clip': vis[0][0], 'index': vis[0][1],
                    'sentences': [s['id'] for s in sentences if s['start'] < end + 0.05 and s['end'] > start - 0.05],
                    'evidence': texte[:180], 'visualIntent': creative.INTENTS[role], 'reason': b.get('raison') or '',
                    'source': 'claude'})
    if len(out) < 2 or out[0]['role'] != 'accroche':
        return None
    for i, beat in enumerate(out):
        beat['id'] = f'b{i + 1}'
        beat['intensity'] = round(min(1, .42 + i / max(1, len(out) - 1) * .45 + (.12 if beat['role'] in ('preuve', 'cta') else 0)), 2)
    return out


def direction(reel):
    """Message, public, promesse et titre de Claude pour creativePlan.direction, ou None."""
    res = resultat(reel)
    if res is None:
        return None
    return {'message': res.get('message') or '', 'public': res.get('public') or '', 'promesse': res.get('promesse') or '',
            'titre': res.get('titre') or '', 'nom': res.get('_nom') or ''}


def titres_notifications(reel, cands):
    """Titres de notification de Claude pour galerie._notifications (a la place des titres de l'IA locale) :
    {phrase: titre verifie par galerie.valid_title, ou None si Claude ne voit rien a illustrer dans ce temps}. Une idee
    d'un plan change depuis l'appel n'est pas dans le resultat (Claude ne l'a pas lue : l'IA locale la traite).
    None sans resultat (l'IA locale garde la main)."""
    from .galerie import valid_title
    from .graphismes import _anchored
    res = resultat(reel)
    if res is None:
        return None
    bornes = _bornes(reel, res)
    par_temps = {}
    for n, ca in enumerate(res.get('cartes') or []):
        if ca.get('type') == 'notification':
            par_temps.setdefault(ca['beat'], []).append((n, ca['texte']))
    pris, out = set(), {}
    for c in sorted(cands, key=lambda c: c['at']):
        if c['clip']['id'] not in res['_plans']:
            continue  # plan change depuis l'appel : pas d'avis de Claude sur cette idee
        bi = next((n for n, b in enumerate(bornes) if b and b[0] - .3 <= c['at'] <= b[1] + .5), None)
        titre = None
        # la carte du meme temps qui parle de CETTE idee (un mot dit en commun) et dont les chiffres y sont dits
        idee = [c['clip']['words'][k] for k in c['idea']]
        for n, texte in par_temps.get(bi) or []:
            t = valid_title(texte, c['clip'], c['idea']) if n not in pris and _anchored(idee, texte) else None
            if t:
                titre = t
                pris.add(n)
                break
        out[c['phrase']] = titre
    return out


def bouton(reel):
    """Bouton d'appel a l'action propose par Claude (texte dit mot pour mot, offre dite) quand les regles n'en trouvent pas :
    {clip, index, texte, secondaire, longueur} ou None."""
    res = resultat(reel)
    if res is None:
        return None
    clips = {c['id']: c for c in reel.get('clips') or []}
    for ca in res.get('cartes') or []:
        a = ca.get('ancre') or {}
        if ca.get('type') != 'bouton' or a.get('clip') not in res['_plans']:
            continue
        ws = clips[a['clip']]['words']
        n = int(ca.get('longueur') or len(ca['texte'].split()))
        if a['i'] < len(ws) and all(_visible(w) and not w.get('hide') for w in ws[a['i']:a['i'] + n]):
            return {'clip': a['clip'], 'index': a['i'], 'texte': ca['texte'], 'secondaire': ca.get('secondaire') or '', 'longueur': n}
    return None


def pour_graphismes(reel, words):
    """Ce que graphismes._ai demandait a l'IA locale (benefices, mot choc), d'apres les cartes de Claude, avec leurs instants
    dans le montage (words : mots de montage.compute, avec clip et index). None sans resultat (l'IA locale garde la main) ;
    pas de carte « liste » ou « mot » : Claude n'en voit pas (pas de liste ; le mot choc retombe sur la regle simple)."""
    res = resultat(reel)
    if res is None:
        return None
    t = {(w.get('clip'), w.get('index')): float(w['start']) for w in words or [] if 'clip' in w and 'start' in w}
    bornes = _bornes(reel, res)
    out = {'benefices': [], 'mot_choc': None, 'source': 'claude'}
    for ca in res.get('cartes') or []:
        b = bornes[ca['beat']] if 0 <= ca['beat'] < len(bornes) else None
        if not b:
            continue
        role = res['beats'][ca['beat']]['role']
        # cases cochees = benefices : une liste du probleme (couts subis) n'en est pas une
        if ca['type'] == 'liste' and not out['benefices'] and role not in ('accroche', 'tension'):
            items = [x for x in str(ca.get('secondaire') or '').split('|') if x.strip()][:4]
            if len(items) >= 2:
                out.update(benefices=items, benefices_titre=ca['texte'], benefices_at=next((t[k] for k in b[2] if k in t), None))
        elif ca['type'] == 'mot' and not out['mot_choc'] and ca.get('ancre'):
            k = (ca['ancre']['clip'], ca['ancre']['i'])
            if k in t and k[0] in res['_plans']:
                out.update(mot_choc=ca['texte'], mot_choc_at=t[k])
    return out


def corrections_proposees(reel, plans=None):
    """Corrections de Claude encore applicables : le mot n'a pas change depuis l'appel, plan ni coupe ni verrouille, et le
    mot n'a pas ete remis a la main sur son texte d'origine (« asr » = texte actuel : une correction defaite par le monteur
    n'est jamais reposee)."""
    res = resultat(reel)
    if res is None:
        return []
    clips = {c['id']: c for c in reel.get('clips') or []}
    out = []
    for k in res.get('corrections') or []:
        c = clips.get(k.get('clip'))
        if c is None or k['clip'] not in res['_plans'] or (plans is not None and k['clip'] not in plans) or verrous.is_locked(c):
            continue
        w = c['words'][k['i']] if 0 <= k['i'] < len(c['words']) else None
        if not isinstance(w, dict) or w.get('cut'):
            continue
        cur = _coeur(w.get('w')).lower()
        if cur != k['avant'].lower() or (w.get('asr') is not None and _coeur(w['asr']).lower() == cur):
            continue
        out.append(dict(k))
    return out


def _avec_casse(nouveau, ancien):
    if len(ancien) > 1 and ancien.isupper():
        return nouveau.upper()
    if ancien[:1].isupper():
        return nouveau[:1].upper() + nouveau[1:]
    return nouveau[:1].lower() + nouveau[1:]


def appliquer_corrections(reel):
    """Pose les corrections de Claude encore applicables : texte seulement (temps des mots gardes), ponctuation et
    majuscule du mot d'origine gardees, texte d'origine dans « asr ». Jamais sur un plan verrouille ni sur un mot change
    depuis l'appel (retouche du monteur). -> [{clip, i, avant, apres}] poses."""
    from .orthographe import _parts
    clips = {c['id']: c for c in reel.get('clips') or []}
    poses = []
    for k in corrections_proposees(reel):
        w = clips[k['clip']]['words'][k['i']]
        av, coeur, ap = _parts(str(w['w']).strip())
        nouveau = f"{av}{_avec_casse(k['apres'], coeur)}{ap}"
        if nouveau != w['w']:
            w.setdefault('asr', w['w'])
            poses.append({'clip': k['clip'], 'i': k['i'], 'avant': w['w'], 'apres': nouveau})
            w['w'] = nouveau
    return poses


def suggestions(reel, libres, max_words, lang, brands, keep):
    """Propositions de « Relancer l'IA » d'apres Claude : mots en couleur (Claude d'abord, regles en complement, meme budget
    avec les mots deja colores), bandeau de Claude en tete, corrections de transcription proposees ; emojis gardes."""
    from .reel import reel_highlights
    force = {k: v for k, v in (mots(reel) or {}).items() if k in libres}
    clips = reel.get('clips') or []
    hl = reel_highlights(clips, max_words, lang, only=set(libres), brands=brands, keep=keep, force=force)
    prev = reel.get('suggestions') or {}
    words = {c['id']: [i for i in hl.get(c['id'], []) if i < len(c['words']) and not c['words'][i].get('hl')] for c in clips}
    b = bandeau(reel)
    banners = ([b] if b else []) + [x for x in prev.get('banners') or [] if x != b]
    return {'banners': banners[:3], 'words': words, 'emojis': dict(prev.get('emojis') or {}),
            'corrections': corrections_proposees(reel, set(libres))}


# ---------- ligne de commande ----------
def habiller(project_dir, rid='script'):
    """Pose le resultat garde sur le reel, comme a la fin d'un montage automatique mais sans rien reconstruire : corrections
    (deja posees par lancer), mots en couleur, bandeau, plan creatif, scenes du style, graphismes proposes, relecture de
    sobriete, choregraphie. Une version « avant cerveau Claude » est gardee. Verrous et retouches a la main jamais touches.
    -> resume."""
    from . import choregraphie, creative, galerie, graphismes, sobriete
    from .reel import _brands, _caption_words, reel_language, rehighlight
    path = montage.reel_path(project_dir, rid)
    reel = montage.load(project_dir, rid)
    if resultat(reel) is None:
        return {}
    dossier = Path(project_dir) / 'versions' / str(rid or 'script')
    dossier.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y-%m-%dT%H-%M-%S', time.gmtime())  # meme horodatage que les versions du serveur (UTC)
    copie = dossier / f'{stamp} avant cerveau Claude.json'
    for n in range(2, 100):  # deux habillages dans la meme seconde : jamais une version ecrasee
        if not copie.exists():
            break
        copie = dossier / f'{stamp} avant cerveau Claude ({n}).json'
    copie.write_bytes(path.read_bytes())
    rapport = {'version': copie.name}

    def textes(r):
        with verrous.sous_protection(r):
            if r.get('aiMode') == 'suggestion':
                libres = {c['id'] for c in r['clips'] if not verrous.is_locked(c)}
                cur = {c['id']: {i for i, w in enumerate(c['words']) if w.get('hl')} for c in r['clips']}
                r['suggestions'] = {**(r.get('suggestions') or {}),
                                    **suggestions(r, libres, _caption_words(r), reel_language(r), _brands(r), cur)}
            else:
                rehighlight(r)
                b = bandeau(r)
                ban = r.get('banner') or {}
                # un bandeau verifie de Claude remplace l'actuel ; sans proposition, le bandeau actuel (deja relu au
                # montage, ou ecrit par le monteur) reste tel quel : jamais efface par cet habillage
                if b and not verrous.protege(ban):
                    r['banner'] = {**ban, 'text': b}
                    sug = r.setdefault('suggestions', {})
                    sug['banners'] = [b] + [x for x in sug.get('banners') or [] if x != b][:2]
            creative.apply(r, r.get('auto'), _style(r))
            galerie.prepare(r)
    montage.update(project_dir, rid, textes)
    try:  # graphismes proposes (listes de benefices, mot geant) d'apres Claude ; graphismes.suggest relit le reel sur le disque
        trouves = graphismes.suggest(project_dir, rid)
    except Exception as e:
        print(f'Graphismes ignores ({e}).', file=sys.stderr)
        trouves = None

    def fin(r):
        tpl = _style(r)
        if trouves is not None:
            auto_g = tpl.get('graphismes') == 'auto'
            with verrous.sous_protection(r):
                # meme regle que auto._finish : les graphismes poses a la main ou acceptes restent ; les automatiques sont refaits
                garde = [g for g in r.get('graphics') or [] if verrous.protege(g) or not (g.get('suggested') or g.get('auto'))]
                # un graphisme deja accepte n'est pas propose une 2e fois au meme moment ; identifiants jamais en double
                ids = {g.get('id') for g in garde}
                neufs = []
                for g in trouves:
                    if any(o.get('kind') == g.get('kind') and abs(float(o.get('at', -99)) - float(g.get('at', 0))) < 2.5
                           for o in garde):
                        continue
                    if g.get('id') in ids:
                        g = {**g, 'id': f"{g['id']}-c{len(ids) + len(neufs) + 1}"}
                    neufs.append({**g, 'suggested': not (auto_g and g.get('confiance') == 'haute'),
                                  **({'auto': True} if auto_g and g.get('confiance') == 'haute' else {})})
                    ids.add(neufs[-1]['id'])
                r['graphics'] = garde + neufs
        try:
            rep = sobriete.relire(r, tpl, tout=False)
            r['sobriete'] = {k: rep[k] for k in ('retires', 'deplaces', 'corriges', 'gardes', 'resume')}
            rapport['sobriete'] = rep['resume']
        except Exception as e:
            print(f'Relecture du monteur ignoree ({e}).', file=sys.stderr)
        try:
            choregraphie.actualiser(r, tpl)
        except Exception as e:
            print(f'Choregraphie ignoree ({e}).', file=sys.stderr)
        rapport['mots_en_couleur'] = sum(1 for c in r['clips'] for w in c['words'] if w.get('hl'))
        rapport['scenes'] = sum(1 for s in r.get('styleScenes') or [] if not s.get('hidden'))
        rapport['bandeau'] = (r.get('banner') or {}).get('text') or ''
    montage.update(project_dir, rid, fin)
    return rapport


def executer(project_dir, rid='script', forcer=False):
    """« python -m editeur.cerveau_claude » : cerveau (garde ou un appel), puis habillage du reel avec son resultat."""
    out = lancer(project_dir, rid, forcer=forcer, appliquer=True)
    if out.get('ok'):
        out['habillage'] = habiller(project_dir, rid)
    return out


def main(argv=None):
    try:  # avant tout message (accents) : une sortie redirigee de Windows (cp1252) ferait planter un simple print
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog='python -m editeur.cerveau_claude',
                                 description="Cerveau créatif par Claude : un appel par montage (gardé), puis habillage du reel.")
    ap.add_argument('projet', help='dossier du projet (projects/<nom>)')
    ap.add_argument('--reel', default='script', help='version du reel (script, v1...)')
    ap.add_argument('--forcer', action='store_true', help='refaire l’appel même si ce montage a déjà été lu (coûte un appel)')
    a = ap.parse_args(argv)
    out = executer(a.projet, a.reel, forcer=a.forcer)
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
