"""« Dis à l'IA ce que tu veux changer » (contrat « consigne ») — MODULE DU GROUPE « consigne ».

L'utilisateur ecrit, avec ses mots, ce qu'il veut changer dans un montage deja fait (« mets les sous-titres en jaune »,
« enleve la carte a 0:12 », « la musique est trop forte », « coupe le bout ou je begaie a 0:31 », « mets le style
Hormozi », « fais-en une version de 30 secondes »...). Ce module :
1. resume le montage en ~4 000 jetons au plus (_contexte) : duree, format, style, phrases dites avec leurs temps, mots en
   couleur, sous-titres, bandeau, elements a l'image (id, temps, textes, etat, verrou), plans, musique, bruitages, temps du
   lecteur (« ici »), mots detailles autour de ce temps et des temps cites, 3 dernieres demandes de ce reel ;
2. fait traduire la demande en OPERATIONS d'une liste fermee (catalogue() : une operation par action, parametres types,
   cible par id ou par temps ; schema JSON strict, schema()) : Claude (claude_api.appeler, tache « consigne », sortie JSON
   structuree), sinon l'IA locale (Qwen par llm.session, meme schema en grammaire), sinon des regles simples en francais
   (_regles). Demande ambigue -> une question, rien n'est applique. Demande hors liste -> refus + raison ;
3. verifie chaque operation (id existants, temps dans la video, couleurs #RRGGBB, styles / ambiances / polices connus,
   element verrouille refuse) et l'applique en REUTILISANT les fonctions du moteur : reel.apply_template (style),
   detourage.prepare, llm._locate (mots dits), sobriete._retirer (masquer sans perdre), declinaison._reanchor (couper),
   passage.refaire (refaire un passage), declinaison.create (version courte), sfxgen.appliquer_famille (sons de coupe),
   sobriete.relire et choregraphie.actualiser (relecture de la plage touchee seulement). Un element retouche porte manual
   (scene : edited, figee a sa place affichee, comme design-panel.tsx) : aucune passe automatique ne le reprendra ; un
   verrou n'est leve que si la demande le dit (« deverrouille ») ;
4. enregistre : sur le MEME reel avec une copie « avant » dans versions/<reel>/ (meme format que le serveur ; « Annuler »
   = POST /api/reels/<p>/<v>/restore {file: avant}, a l'octet pres), ou sur une NOUVELLE version pour une declinaison
   (l'originale ne change pas ; avant = id de l'originale). Historique : reel["consignes"] (jamais exporte : le serveur le
   retire avant le rendu, l'interface avant le lecteur ; jamais modifie par le PUT de l'editeur, hors EDITABLE).
Rien n'est perdu : ce qui n'a pas pu etre fait devient une note de revision ouverte a l'instant demande.

Ligne de commande (une ligne JSON sur la sortie standard) :
  python -m editeur.consigne <dossier_projet> --reel <id> --texte "<demande>" [--t <s>] [--moteur auto|claude|local]
                             [--simuler]
  -> {ok, version (reel qui porte le resultat), avant (fichier de versions/<version>/ a restaurer, ou id de l'originale
      pour une declinaison, ou null), changements [{quoi, detail, t?}], refus [{demande, raison}], question (texte ou
      null), moteur ("claude" | "local" | "regles"), cout ($), note_ajoutee, reponse, remarques [..], modifie, simule}
  --moteur claude : Claude seulement (erreur s'il ne repond pas) ; local : jamais Claude ; auto (defaut) : Claude puis local.
  --simuler : plan seulement, rien n'est ecrit (l'IA est quand meme appelee).
Erreur (montage introuvable, texte vide...) : la ligne JSON porte ok=false et « erreur », la phrase va aussi sur la sortie
d'erreur, code de sortie 1.
Tests (aucun appel reel : faux client Claude, Qwen simule) : docs/claude-api/tests/test_consigne.py.
"""
import argparse
import copy
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from . import montage, verrous
from .media import ROOT

TEXTE_MAX = 800            # meme limite que la route du serveur
SORTIE_MAX = 1500          # jetons de sortie de Claude (reflexion comprise) ; une reponse fait ~150-500 jetons
CONTEXTE_MAX = 14000       # caracteres du resume (~4 000 jetons a 3,5 caracteres par jeton)
HISTORIQUE = 50            # demandes gardees dans reel["consignes"]
RAPPEL = 3                 # dernieres demandes montrees a l'IA (« non, l'autre carte »)
FENETRE = 4.0              # s de mots detailles autour du temps du lecteur et des temps cites
NOTE_TEXTE = 2000          # plafond du serveur (validateV2)
NOM_VERSION = 'avant IA'
ID_RE = re.compile(r'[A-Za-z0-9_-]{1,60}')
HEX = re.compile(r'#[0-9A-Fa-f]{6}')
FAMILLE_RE = re.compile(r'[a-z0-9-]{1,40}')
FORMATS = {'9:16': (1080, 1920), '16:9': (1920, 1080), '4:5': (1080, 1350), '1:1': (1080, 1080)}
LISTES = ('styleScenes', 'graphics', 'vectors', 'broll')
TYPE_RETRAIT = {'styleScenes': 'scene', 'graphics': 'graphic', 'vectors': 'vector', 'broll': 'broll'}
SCENES = {'notification': 'Notification', 'metric': 'Chiffre', 'comparison': 'Comparaison', 'keyword': 'Mot clé',
          'paper': 'Autocollant', 'product': 'Produit', 'dashboard': 'Tableau', 'flow': 'Parcours', 'cta': 'Bouton',
          'list': 'Liste'}
GRAPHISMES = {'chiffre': 'Chiffre', 'coches': 'Liste de bénéfices', 'carte': 'Carte', 'motgeant': 'Mot géant',
              'logo': 'Logo'}
GENRES = {'cartes': ('styleScenes',), 'graphismes': ('graphics',), 'plans_de_coupe': ('broll',),
          'vecteurs': ('vectors',), 'tout': LISTES}
POSITIONS = {'haut': 0.24, 'milieu': 0.5, 'bas': 0.72}
VOIX = ('naturel', 'radio', 'podcast', 'aucun')
COULEURS = {'jaune': '#FFD400', 'rouge': '#FF3B30', 'orange': '#FF8A00', 'vert': '#22C55E', 'bleu pale': '#38BDF8',
            'bleu ciel': '#38BDF8', 'bleu': '#2F80ED', 'turquoise': '#2DD4BF', 'cyan': '#22D3EE', 'violet': '#8B5CF6',
            'mauve': '#8B5CF6', 'rose': '#FF4FA3', 'or': '#F5C542', 'dore': '#F5C542', 'blanc': '#FFFFFF',
            'noir': '#000000', 'gris': '#9CA3AF'}
POLICES = ('Montserrat', 'Anton', 'Bebas Neue', 'Poppins', 'Inter', 'Oswald', 'Archivo Black', 'Bangers', 'Luckiest Guy',
           'Rubik', 'Barlow Condensed', 'Playfair Display', 'DM Serif Display', 'Permanent Marker', 'Kanit',
           'League Spartan', 'Manrope')
# ordre d'application : le style d'abord (il remet les reglages), la coupe et les passes longues a la fin
ORDRE = {'style': 0, 'sous_titres_modele': 1, 'element_verrou_ouvert': 2, 'couper': 8, 'refaire_passage': 9,
         'declinaison': 10, 'element_verrou_ferme': 7, 'note': 6}
LOURDES = ('style', 'refaire_passage', 'declinaison')
VIDE = {'ok': False, 'version': None, 'avant': None, 'changements': [], 'refus': [], 'question': None, 'moteur': None,
        'cout': 0.0, 'note_ajoutee': False, 'reponse': '', 'remarques': [], 'modifie': False, 'simule': False}


class ConsigneErreur(ValueError):
    """Demande impossible a traiter (montage introuvable, texte vide, Claude seul indisponible...) : la phrase (en
    francais) est affichee telle quelle."""


class _Refus(Exception):
    """Operation refusee : (demande, raison) en francais ; rien n'a ete change pour elle."""

    def __init__(self, demande, raison):
        super().__init__(raison)
        self.demande, self.raison = demande, raison


# ---------- petits outils ----------
def _norm(s):
    """Minuscules, sans accents, apostrophes droites, espaces simples."""
    s = unicodedata.normalize('NFKD', str(s or '').lower().replace('’', "'").replace('`', "'"))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', s).strip()


def _tc(t):
    """0:37,9 (minutes:secondes du montage)."""
    t = max(0.0, float(t or 0))
    m = int(t // 60)
    return f'{m}:{t - 60 * m:04.1f}'.replace('.', ',')


def _f(x, n=2):
    return f'{float(x):.{n}f}'.rstrip('0').rstrip('.').replace('.', ',') if x is not None else '?'


def _nom_couleur(c):
    c = str(c or '').upper()
    nom = next((k for k, v in COULEURS.items() if v == c), None)
    return f'{nom} ({c})' if nom else c


def _court(texte, n=60):
    texte = re.sub(r'\s+', ' ', str(texte or '')).strip()
    return texte if len(texte) <= n else texte[:n - 1].rstrip() + '…'


def _maintenant():
    return time.strftime('%Y-%m-%dT%H:%M:%S')


@contextmanager
def _silence():
    """Les passes du moteur ecrivent parfois des messages sur la sortie standard : vers la sortie d'erreur, pour que la
    ligne JSON du resultat reste seule (lastJson du serveur)."""
    with redirect_stdout(sys.stderr):
        yield


def _snap(t, fps):
    fps = fps or 30
    return round(round(float(t) * fps) / fps, 4)


def _format_de(reel):
    w, h = reel.get('width'), reel.get('height')
    return next((k for k, v in FORMATS.items() if v == (w, h)), f'{w}x{h}')


# ---------- valeurs fermees (fichiers des styles) ----------
def _styles():
    from .reel import list_templates
    return {t['id']: str(t.get('name') or t['id']) for t in list_templates()}


def _presets():
    from .reel import caption_presets
    return {p['id']: p for p in caption_presets()}


def _ambiances():
    """Ambiances de musique dont le fichier existe (assets/music/<id>.ogg) : {id: nom}."""
    from .reel import music_moods
    return {m['id']: str(m.get('name') or m['id']) for m in music_moods()
            if (ROOT / 'assets' / 'music' / f"{m['id']}.ogg").exists()}


def _polices():
    """Polices fournies (FONT_FILES de remotion/src/types.ts), sinon la liste connue."""
    try:
        src = (ROOT / 'remotion/src/types.ts').read_text(encoding='utf-8')
        bloc = re.search(r'FONT_FILES[^{]*\{(.*?)\n\}', src, re.S).group(1)
        noms = [a or b for a, b in re.findall(r"^\s*(?:'([^']+)'|([A-Za-z]+))\s*:", bloc, re.M)]
        if noms:
            return tuple(noms)
    except Exception:
        pass
    return POLICES


def _familles():
    """Familles des sons de transition (catalogue du groupe « sons », lu par sfxgen.familles() :
    styles/sons-transitions.json) : {id: nom} ; ids /^[a-z0-9-]{1,40}$/. Catalogue absent ou abime : {} (seule « auto »
    = famille du style est proposee)."""
    try:
        from .sfxgen import familles
        fams = familles().get('familles') or []
    except Exception:
        return {}
    out = {str(f['id']): str(f.get('nom') or f['id']) for f in fams if isinstance(f, dict) and f.get('id')}
    return {k: v for k, v in out.items() if FAMILLE_RE.fullmatch(k) and k != 'auto'}


# ---------- la liste fermee des operations ----------
S, N, B, I = {'type': 'string'}, {'type': 'number'}, {'type': 'boolean'}, {'type': 'integer'}


def _enum(vals):
    return {'type': 'string', 'enum': list(vals)}


def catalogue():
    """Operations permises -> {op: (groupe, description pour l'IA, {parametre: schema JSON})}. Valeurs fermees lues
    dans les fichiers des styles (stables : la consigne systeme et le schema restent en cache chez Anthropic)."""
    styles, presets, ambiances = _styles(), _presets(), _ambiances()
    familles = ['auto'] + list(_familles())
    return {
        # sous-titres
        'sous_titres_couleur': ('SOUS-TITRES', 'couleur du texte des sous-titres', {'couleur': S}),
        'mots_forts_couleur': ('SOUS-TITRES', 'couleur des mots mis en valeur (« mots en couleur ») des sous-titres',
                               {'couleur': S}),
        'sous_titres_modele': ('SOUS-TITRES', 'autre allure de sous-titres (police, taille, couleurs du modèle)',
                               {'modele': _enum(presets)}),
        'sous_titres_taille': ('SOUS-TITRES', 'sous-titres plus grands ou plus petits',
                               {'sens': _enum(('plus_grand', 'plus_petit'))}),
        'sous_titres_position': ('SOUS-TITRES', 'hauteur des sous-titres dans l\'image',
                                 {'position': _enum(POSITIONS)}),
        'sous_titres_majuscules': ('SOUS-TITRES', 'sous-titres en MAJUSCULES (true) ou en minuscules (false)',
                                   {'actif': B}),
        'sous_titres_police': ('SOUS-TITRES', 'police des sous-titres', {'police': _enum(_polices())}),
        'sous_titres_mots': ('SOUS-TITRES', 'nombre de mots par écran de sous-titres (1 à 6)', {'nombre': I}),
        # mots dits
        'mot_couleur': ('MOTS DITS', 'met (actif true) ou enlève (false) la couleur d\'un mot ou d\'une courte expression '
                                     'dite (copiée des PHRASES) ; partout false = l\'endroit le plus proche du temps du '
                                     'lecteur (sinon le premier)', {'texte': S, 'actif': B, 'partout': B}),
        'mot_corriger': ('MOTS DITS', 'corrige un mot mal écrit dans les sous-titres (même nombre de mots ; un mot peut '
                                      'devenir 3 mots au plus)', {'avant': S, 'apres': S, 'partout': B}),
        # bandeau
        'bandeau_texte': ('BANDEAU', 'texte du bandeau du haut (le bandeau s\'affiche)', {'texte': S}),
        'bandeau_afficher': ('BANDEAU', 'affiche (true) ou cache (false) le bandeau du haut', {'actif': B}),
        # elements a l'image
        'element_masquer': ('ÉLÉMENTS À L\'IMAGE', 'masque un élément (carte, graphisme, vecteur, plan de coupe) ; '
                                                  'il reste récupérable', {'id': S}),
        'element_afficher': ('ÉLÉMENTS À L\'IMAGE', 'affiche un élément masqué ou proposé', {'id': S}),
        'element_texte': ('ÉLÉMENTS À L\'IMAGE', 'texte principal d\'un élément (carte, bouton, chiffre, mot géant)',
                          {'id': S, 'texte': S}),
        'element_texte2': ('ÉLÉMENTS À L\'IMAGE', '2e ligne d\'un élément (offre du bouton, sous-titre ; liste : '
                                                 'éléments séparés par « | », même nombre)', {'id': S, 'texte': S}),
        'element_couleur': ('ÉLÉMENTS À L\'IMAGE', 'couleur d\'un élément', {'id': S, 'couleur': S}),
        'element_deplacer': ('ÉLÉMENTS À L\'IMAGE', 'fait commencer un élément à un autre moment (s)',
                             {'id': S, 'debut': N}),
        'element_duree': ('ÉLÉMENTS À L\'IMAGE', 'durée d\'affichage d\'un élément (s)', {'id': S, 'duree': N}),
        'element_verrou': ('ÉLÉMENTS À L\'IMAGE', 'verrouille (true) ou déverrouille (false) un élément, un plan (c1…) '
                                                 'ou « bandeau »', {'id': S, 'actif': B}),
        'tout_masquer': ('ÉLÉMENTS À L\'IMAGE', 'masque tous les éléments d\'un genre (sauf les verrouillés)',
                         {'genre': _enum(GENRES)}),
        'bouton_texte': ('ÉLÉMENTS À L\'IMAGE', 'texte du bouton d\'appel à l\'action', {'texte': S}),
        'mot_geant_ajouter': ('ÉLÉMENTS À L\'IMAGE', 'ajoute un gros mot à l\'écran (3 mots au plus) à ce moment (s)',
                              {'texte': S, 'debut': N}),
        # musique
        'musique_volume': ('MUSIQUE', 'musique plus ou moins forte',
                           {'sens': _enum(('plus', 'moins', 'beaucoup_plus', 'beaucoup_moins'))}),
        'musique_ambiance': ('MUSIQUE', 'autre musique (ambiance)', {'ambiance': _enum(ambiances or ['energique'])}),
        'musique_activer': ('MUSIQUE', 'met (true) ou enlève (false) la musique', {'actif': B}),
        # bruitages
        'bruitages_quantite': ('BRUITAGES (whoosh des coupes et des cartes, pops des mots…)',
                               'nombre de bruitages', {'niveau': _enum(('aucun', 'moins', 'normal', 'plus'))}),
        'bruitages_volume': ('BRUITAGES (whoosh des coupes et des cartes, pops des mots…)', 'bruitages plus ou moins forts',
                             {'sens': _enum(('plus', 'moins'))}),
        'bruitages_varier': ('BRUITAGES (whoosh des coupes et des cartes, pops des mots…)',
                             'sons de transition variés à chaque coupe (true) ou toujours le même (false)', {'actif': B}),
        'bruitages_famille': ('BRUITAGES (whoosh des coupes et des cartes, pops des mots…)',
                              'famille des sons de transition (« auto » = celle du style)', {'famille': _enum(familles)}),
        # image
        'emojis': ('IMAGE', 'montre (true) ou enlève (false) les emojis', {'actif': B}),
        'zooms': ('IMAGE', 'zooms et relances de cadre', {'niveau': _enum(('aucun', 'moins', 'plus'))}),
        'flash': ('IMAGE', 'flashs entre les parties', {'actif': B}),
        'barre_progression': ('IMAGE', 'barre de progression', {'actif': B}),
        'format': ('IMAGE', 'format de la vidéo', {'format': _enum(FORMATS)}),
        'voix': ('IMAGE', 'traitement de la voix à l\'export', {'traitement': _enum(VOIX)}),
        # montage
        'style': ('MONTAGE', 'applique un autre style de montage (garde les retouches)', {'style': _enum(styles)}),
        'couper': ('MONTAGE', 'retire de la vidéo le passage dit entre debut et fin (s, mots entiers)',
                   {'debut': N, 'fin': N}),
        'refaire_passage': ('MONTAGE', 'refait l\'habillage automatique de ce passage seulement (s)',
                            {'debut': N, 'fin': N}),
        'declinaison': ('MONTAGE', 'crée une NOUVELLE version plus courte et/ou d\'une autre intention (l\'originale ne '
                                   'change pas) ; duree 0 = même durée',
                        {'duree': {'type': 'integer', 'enum': [0, 15, 30, 60]},
                         'intention': _enum(('aucune', 'rapide', 'emotion'))}),
        'note': ('MONTAGE', 'laisse une note de révision à ce moment (s), pour plus tard', {'texte': S, 't': N}),
    }


def schema(cat=None):
    """Schema JSON de la reponse (sortie structuree de Claude, grammaire de Qwen) : chaque objet a
    additionalProperties false et TOUS ses champs dans required ; ni minimum, ni maxLength, ni pattern (non pris en
    charge), aucune recursion. Une branche anyOf par operation (« op » constant)."""
    cat = cat or catalogue()
    branches = []
    for op, (_, _, params) in cat.items():
        props = {'op': {'type': 'string', 'const': op}, **params}
        branches.append({'type': 'object', 'properties': props, 'required': list(props), 'additionalProperties': False})
    refus = {'type': 'object', 'properties': {'demande': S, 'raison': S}, 'required': ['demande', 'raison'],
             'additionalProperties': False}
    return {'type': 'object',
            'properties': {'reponse': S, 'question': S, 'operations': {'type': 'array', 'items': {'anyOf': branches}},
                           'refus': {'type': 'array', 'items': refus}},
            'required': ['reponse', 'question', 'operations', 'refus'], 'additionalProperties': False}


def _doc_param(nom, sch):
    if 'enum' in sch:
        vals = sch['enum']
        return f"{nom} ∈ {{{', '.join(map(str, vals))}}}" if len(vals) <= 20 else f"{nom} (liste plus bas)"
    return nom + {'number': ' (s)' if nom in ('debut', 'fin', 't', 'duree') else '', 'boolean': ' (true/false)',
                  'integer': ''}.get(sch.get('type'), '')


def systeme(cat=None):
    """Consigne systeme STABLE (mise en cache) : role, regles, operations, valeurs possibles, exemples."""
    cat = cat or catalogue()
    L = [
        "Tu es l'assistant de montage de l'Éditeur Sami : des publicités verticales courtes, déjà montées "
        "automatiquement. L'utilisateur (entrepreneur québécois, pas monteur) écrit ce qu'il veut changer, souvent en "
        "langage familier (« pis », « ben trop », « enlève-moi ça », fautes, sans accents). Tu reçois le RÉSUMÉ du montage "
        "puis la DEMANDE, et tu la traduis en opérations de la liste ci-dessous. Le logiciel applique tes opérations.",
        '',
        'RÈGLES',
        '1. Seulement ce qui est demandé, rien de plus.',
        "2. Les « id » viennent du résumé (ÉLÉMENTS À L'IMAGE, PLANS) : n'en invente jamais. Les temps sont en secondes du "
        "montage (0:31 = 31 s). « ici », « là », « à partir d'ici », « ce bout-là » = TEMPS DU LECTEUR.",
        "3. Demande ambiguë (deux éléments possibles, « change ça » sans temps du lecteur, couleur sans cible…) : "
        "n'applique rien ; pose UNE question courte dans « question » et laisse « operations » vide.",
        "4. Ce que la liste ne permet pas (ajouter une photo ou une vidéo, changer de prise, accélérer, titre 3D, logo, "
        "charte du client, effets spéciaux…) va dans « refus » avec une raison simple (une note sera laissée au monteur) ; "
        'fais quand même le reste.',
        "5. Un élément ou un plan marqué 🔒 est verrouillé : ne le change pas (mets-le dans « refus ») sauf pour le "
        'déverrouiller si on te le demande.',
        "6. « non, l'autre », « pas celle-là », « encore » : regarde DERNIÈRES DEMANDES pour savoir ce qui a déjà été fait.",
        '7. Couper (bégaiement, phrase de trop) : debut = début du premier mot à retirer, fin = fin du dernier (MOTS '
        'AUTOUR). Une version plus courte de toute la vidéo (30 s…) = declinaison, jamais couper.',
        '8. Couleurs en #RRGGBB : ' + ', '.join(f'{k} {v}' for k, v in COULEURS.items() if k not in ('dore', 'mauve', 'bleu ciel')) + '.',
        '9. « reponse » : une phrase courte en français simple (tutoiement) qui dit ce que tu fais. « question » : "" si tu '
        "n'en poses pas.",
        '',
        'OPÉRATIONS (op : paramètres — effet)',
    ]
    groupe = None
    for op, (g, desc, params) in cat.items():
        if g != groupe:
            L.append(f'[{g}]')
            groupe = g
        L.append(f"{op} : {', '.join(_doc_param(k, v) for k, v in params.items())} — {desc}")
    styles, ambiances, familles = _styles(), _ambiances(), _familles()
    L += ['', 'VALEURS',
          'style : ' + ' ; '.join(f'{k} ({v})' for k, v in styles.items()),
          'ambiance : ' + ' ; '.join(f'{k} ({v})' for k, v in ambiances.items()),
          'famille : auto (celle du style)' + ''.join(f' ; {k} ({v})' for k, v in familles.items()),
          'genre : cartes (éléments du style), graphismes, plans_de_coupe, vecteurs, tout',
          '',
          'EXEMPLES',
          'DEMANDE « mets les sous-titres en jaune » → {"reponse":"Je mets les sous-titres en jaune.","question":"",'
          '"operations":[{"op":"sous_titres_couleur","couleur":"#FFD400"}],"refus":[]}',
          'DEMANDE « enlève la carte ici » (TEMPS DU LECTEUR 12.0 ; la carte n2 est à 11.5–14.0) → {"reponse":"J\'enlève '
          'la carte de 0:11.","question":"","operations":[{"op":"element_masquer","id":"n2"}],"refus":[]}',
          'DEMANDE « change le texte » (pas de temps du lecteur, trois cartes) → {"reponse":"","question":"Quelle carte '
          'veux-tu changer, et quel texte veux-tu à la place ?","operations":[],"refus":[]}',
          'DEMANDE « ajoute une photo de ma boutique à la fin » → {"reponse":"Je ne peux pas ajouter de photo : je laisse '
          'une note.","question":"","operations":[],"refus":[{"demande":"Ajouter une photo de la boutique à la fin",'
          '"raison":"Ajouter une image par écrit n\'est pas encore possible : onglet Ajouter."}]}']
    return '\n'.join(L)


# ---------- pont vers remotion/src/timeline.ts (seule source des temps, comme controle.py) ----------
_PONT = r"""
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
const [tl, reelPath, tempsTexte] = process.argv.slice(2);
const T = await import(pathToFileURL(tl).href);
const reel = JSON.parse(fs.readFileSync(reelPath, 'utf8'));
const has = (k) => typeof T[k] === 'function';
const sur = (f, d) => { try { return f(); } catch { return d; } };
const temps = JSON.parse(tempsTexte || '[]');
process.stdout.write(JSON.stringify({
  duration: T.duration(reel),
  words: T.timedWords(reel).map(({w, clip, index, outStart, outEnd, hl, hide}) => ({w, clip, index, start: outStart, end: outEnd, hl: !!hl, hide: !!hide})),
  video: T.videoSegments(reel),
  // scenes du style a leur place AFFICHEE (studio : studioSpot) : une retouche les fige la, sans saut (design-panel.tsx)
  scenes: has('designScenes') ? sur(() => T.designScenes(reel).map((s) => ({id: s.id, kind: s.kind, at: s.at, end: s.end, x: s.x, y: s.y, scale: s.scale})), []) : [],
  studio: has('studioMode') ? sur(() => !!T.studioMode(reel), false) : false,
  events: has('sfxEvents') ? sur(() => T.sfxEvents(reel).map((e) => ({t: e.t, name: e.name, kind: e.kind})), []) : [],
  ancres: has('anchorAtTime') ? temps.map((t) => sur(() => T.anchorAtTime(reel, t), null)) : [],
}));
"""


def calcul(reel, temps=()):
    """Montage calcule par timeline.ts : {duration, words [{w, clip, index, start, end, hl, hide}], video, scenes
    (places affichees), studio, events (bruitages), ancres (anchorAtTime de chaque temps demande)}."""
    bac = ROOT / 'runtime' / 'cache' / 'tmp' / f'consigne-{os.getpid()}-{uuid.uuid4().hex[:8]}'
    bac.mkdir(parents=True, exist_ok=True)
    try:
        (bac / 'pont.mjs').write_text(_PONT, encoding='utf-8')
        (bac / 'reel.json').write_text(json.dumps(reel, ensure_ascii=False), encoding='utf-8')
        r = subprocess.run(['node', str(bac / 'pont.mjs'), str(ROOT / 'remotion/src/timeline.ts'), str(bac / 'reel.json'),
                            json.dumps([float(x) for x in temps])],
                           capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=str(ROOT / 'remotion'))
        if r.returncode:
            raise ConsigneErreur('Calcul du montage impossible (timeline.ts) : ' + (r.stderr or '').strip()[-400:])
        return json.loads(r.stdout)
    finally:
        shutil.rmtree(bac, ignore_errors=True)  # dossier neuf, fichiers seulement (aucune jonction)


# ---------- resume du montage (contexte envoye a l'IA) ----------
def _texte_graphisme(g):
    p = g.get('props') or {}
    k = g.get('kind')
    if k == 'chiffre':
        return f"{p.get('prefix') or ''}{p.get('value', '')}{p.get('suffix') or ''} {p.get('label') or ''}".strip()
    if k == 'coches':
        return ' | '.join([str(p.get('title') or '')] + [str(x) for x in p.get('items') or []]).strip(' |')
    if k == 'carte':
        return ' / '.join(x for x in (str(p.get('title') or ''), str(p.get('subtitle') or '')) if x)
    if k == 'motgeant':
        return str(p.get('text') or '')
    return ''


def _nom(nom, e):
    """Genre lisible d'un element : « Notification », « Chiffre », « Vecteur », « Plan de coupe »."""
    if nom == 'styleScenes':
        return SCENES.get(e.get('kind'), 'Carte du style')
    if nom == 'graphics':
        return GRAPHISMES.get(e.get('kind'), 'Graphisme')
    if nom == 'vectors':
        ic = (e.get('meta') or {}).get('icone') if isinstance(e.get('meta'), dict) else None
        return 'Icône' if ic else 'Vecteur'
    return 'Plan de coupe'


def _textes(reel, nom, e):
    if nom == 'styleScenes':
        return [x for x in (str(e.get('text') or ''), str(e.get('secondary') or '')) if x]
    if nom == 'graphics':
        t = _texte_graphisme(e)
        return [t] if t else []
    if nom == 'vectors':
        ic = (e.get('meta') or {}).get('icone') if isinstance(e.get('meta'), dict) else None
        return [str((ic or {}).get('nom') or str(e.get('asset') or '').split('/')[-1].rsplit('.', 1)[0])]
    src = (reel.get('sources') or {}).get(e.get('source')) or {}
    return [x for x in (str(src.get('name') or e.get('source') or ''), str(e.get('word') or '')) if x]


def _extras(reel):
    d = reel.get('design') or {}
    mode = d.get('mode') if d.get('enabled') is not False else None
    return not mode or d.get('suppressExtras') is False, mode


def _graphisme_visible(reel, g):
    """Meme regle que studioGraphicShown / overlayAt (timeline.ts) : pose ou retouche a la main, verrouille, preuve du
    storyboard, ou style sans habillage."""
    if g.get('suggested'):
        return False
    extras, _ = _extras(reel)
    if extras or g.get('manual') or g.get('locked'):
        return True
    story = (reel.get('creativePlan') or {}).get('storyboard') or []
    at = float(g.get('at') or 0)
    return bool(g.get('auto')) and any(s.get('engine') == 'remotion-graphisme' and float(s.get('start') or 0) - 0.3 <= at
                                       <= float(s.get('end') or 0) + 0.4 for s in story if isinstance(s, dict))


def _etat(reel, nom, e, places):
    extras, mode = _extras(reel)
    if nom == 'styleScenes':
        if e.get('hidden'):
            return 'masqué'
        if not mode:
            return 'masqué (ce style n\'affiche pas les cartes)'
        return 'affiché' if e.get('id') in places else 'pas affiché (mot coupé)'
    if nom == 'graphics':
        return ('proposé, masqué' if e.get('suggested') else 'affiché') if _graphisme_visible(reel, e) or e.get('suggested') \
            else 'masqué par le style'
    if nom == 'vectors':
        return 'proposé, masqué' if e.get('suggested') else 'affiché'
    return 'affiché' if extras else 'masqué par le style'


def intervalle(nom, e, M):
    """[debut, fin] d'un element dans le montage (scene : place affichee, sinon temps de son mot), ou None."""
    try:
        if nom == 'styleScenes':
            p = M['_places'].get(e.get('id'))
            if p:
                return float(p['at']), float(p['end'])
            w = M['_mots'].get((e.get('clip'), e.get('index')))
            return None if w is None else (float(w['start']), float(w['start']) + float(e.get('duration') or 2.4))
        if e.get('at') is None:
            return None
        return float(e['at']), float(e['at']) + float(e.get('duration') or 0)
    except (TypeError, ValueError):
        return None


def _index(M):
    """Index du montage calcule (mots par (plan, indice), places des scenes) ; garde dans M."""
    M.setdefault('_mots', {(w['clip'], w['index']): w for w in M.get('words') or []})
    M.setdefault('_places', {s['id']: s for s in M.get('scenes') or []})
    return M


def _temps_cites(texte):
    """Temps ecrits dans la demande (« 0:31 », « a 31 s », « 12 secondes ») -> [s]."""
    out = []
    for m in re.finditer(r'\b(\d{1,2}):(\d{2})(?:[.,](\d))?\b', texte):
        out.append(int(m.group(1)) * 60 + int(m.group(2)) + (int(m.group(3)) / 10 if m.group(3) else 0))
    for m in re.finditer(r'\b(\d{1,3}(?:[.,]\d)?)\s*(?:s|sec|secs|secondes?)\b', _norm(texte)):
        v = float(m.group(1).replace(',', '.'))
        if v not in (15.0, 30.0, 60.0) or not re.search(r'version|declin|duree|format|raccourc', _norm(texte)):
            out.append(v)
    return list(dict.fromkeys(round(x, 1) for x in out))[:3]


def _rappel(reel):
    lignes = []
    for i, c in enumerate([c for c in reel.get('consignes') or [] if isinstance(c, dict)][-RAPPEL:], 1):
        quoi = '; '.join(_court(x.get('detail'), 110) for x in (c.get('changements') or [])[:4] if isinstance(x, dict))
        if c.get('question'):
            quoi = (quoi + ' ; ' if quoi else '') + f"question posée : « {_court(c['question'], 120)} »"
        if c.get('refus'):
            quoi = (quoi + ' ; ' if quoi else '') + 'refusé : ' + '; '.join(
                _court(r.get('demande'), 60) for r in c['refus'][:2] if isinstance(r, dict))
        t = f" (lecteur à {c['t']:.1f} s)" if isinstance(c.get('t'), (int, float)) else ''
        lignes.append(f"{i}. « {_court(c.get('texte'), 160)} »{t} → {quoi or 'rien de changé'}")
    return lignes


def contexte(reel, M, t, texte):
    """Resume COMPACT du montage pour l'IA (texte, ~4 000 jetons au plus), demande a la fin."""
    _index(M)
    from .sobriete import phrases
    total = float(M['duration'])
    styles = _styles()
    st = reel.get('style') or {}
    pos = float(st.get('position') or 0.7)
    zone = 'haut' if pos < 0.38 else 'milieu' if pos < 0.6 else 'bas'
    L = [f"MONTAGE « {_court(reel.get('title'), 80)} » : {total:.1f} s, format {_format_de(reel)}, style "
         f"{reel.get('template') or '?'} ({styles.get(reel.get('template'), 'style inconnu')})",
         (f'TEMPS DU LECTEUR : {t:.1f} s (« ici », « là », « à partir d\'ici » = {t:.1f} s)' if t is not None
          else 'TEMPS DU LECTEUR : non fourni (« ici » est donc ambigu)'),
         f"SOUS-TITRES : modèle {st.get('preset', '?')} · police {st.get('font', '?')} · texte {st.get('color', '?')} · "
         f"mots en couleur {st.get('highlight', '?')} · taille {st.get('size', '?')} · position {pos:.2f} ({zone}) · "
         f"majuscules {'oui' if st.get('uppercase') else 'non'} · {st.get('maxWords', '?')} mots par écran"]
    b = reel.get('banner') or {}
    fin_b = 'fin' if b.get('end') is None else f"{float(b['end']):.1f}"
    L.append(f"BANDEAU : {'affiché' if b.get('enabled') and str(b.get('text') or '').strip() else 'masqué'} · texte "
             f"« {_court(b.get('text'), 80)} » · {float(b.get('start') or 0):.1f}–{fin_b} s"
             + (' · 🔒' if verrous.is_locked(b) else ''))
    # plans (id, debut, fin) dans le montage
    deb = {}
    for s in M.get('video') or []:
        a = float(s['out_start'])
        e = a + (float(s['src_out']) - float(s['src_in'])) / float(s.get('speed') or 1)
        d = deb.setdefault(s['clip'], [a, e])
        d[0], d[1] = min(d[0], a), max(d[1], e)
    verr = {c['id'] for c in reel.get('clips') or [] if verrous.is_locked(c)}
    L.append('PLANS : ' + ' · '.join(f"{cid} {a:.1f}–{e:.1f}{' 🔒' if cid in verr else ''}" for cid, (a, e) in deb.items()))
    # phrases dites, mots en couleur entre *etoiles*
    mots = [w for w in M.get('words') or [] if str(w.get('w') or '').strip()]
    ph = phrases(mots)

    def ligne(p, n=None):
        a, e, ws = p
        ws2 = ws if n is None or len(ws) <= n else ws[:n]
        txt = ' '.join(f"*{w['w']}*" if w.get('hl') else str(w['w']) for w in ws2) + (' …' if len(ws2) < len(ws) else '')
        return f"{a:.1f}–{e:.1f} [{ws[0]['clip']}] {txt}"
    L.append('PHRASES DITES (temps du montage ; *mot* = en couleur) :')
    corps = [ligne(p) for p in ph]
    if sum(len(x) for x in corps) > CONTEXTE_MAX * 0.45:  # longue video : phrases raccourcies (loin du lecteur d'abord)
        corps = [ligne(p, None if t is not None and p[0] - 15 <= t <= p[1] + 15 else 14) for p in ph]
    L += corps
    # mots detailles autour du lecteur et des temps cites (couper un begaiement au mot pres)
    for x in ([t] if t is not None else []) + [c for c in _temps_cites(texte) if t is None or abs(c - t) > FENETRE]:
        autour = [w for w in mots if x - FENETRE <= w['start'] <= x + FENETRE][:40]
        if autour:
            L.append(f'MOTS AUTOUR DE {x:.1f} s : ' + ' · '.join(f"{w['start']:.2f}–{w['end']:.2f} {w['w']}" for w in autour))
    # elements a l'image
    els = []
    for nom in LISTES:
        for e in reel.get(nom) or []:
            if not isinstance(e, dict) or e.get('id') is None:
                continue
            iv = intervalle(nom, e, M)
            tx = ' / '.join(f'« {_court(x, 50)} »' for x in _textes(reel, nom, e))
            marque = (' · 🔒' if verrous.is_locked(e) else '') + (' · retouché' if verrous.is_manual(e) else '')
            els.append((iv[0] if iv else 1e9, f"{e['id']} · {_nom(nom, e)} · "
                        f"{f'{iv[0]:.1f}–{iv[1]:.1f}' if iv else 'temps inconnu'} · {tx or 'sans texte'} · "
                        f"{_etat(reel, nom, e, M['_places'])}{marque}"))
    L.append("ÉLÉMENTS À L'IMAGE (id · genre · temps · texte · état) :" + ('' if els else ' aucun'))
    L += [x for _, x in sorted(els, key=lambda z: z[0])]
    m = reel.get('music') or {}
    amb = _ambiances()
    nom_m = f" ({amb[m['mood']]})" if m.get('mood') in amb else ''
    L.append(f"MUSIQUE : {m.get('mood') or 'aucune'}{nom_m} · volume {float(m.get('volume') or 0):.2f} · "
             f"{'allumée' if m.get('enabled') else 'éteinte'}")
    s = reel.get('sfx') or {}
    poses = [f"{float(x.get('t') or 0):.1f} {x.get('name')}" for x in s.get('extra') or [] if isinstance(x, dict)][:8]
    L.append(f"BRUITAGES : {'allumés' if s.get('enabled') else 'éteints'} · volume {float(s.get('volume') or 0):.2f} · "
             f"transitions {s.get('transition') or 'aucune'} · mots forts {s.get('highlight') or 'aucun'} (écart "
             f"{_f(s.get('highlightGap'), 1)} s) · début {s.get('start') or 'aucun'} · appel à l'action {s.get('cta') or 'aucun'}"
             f" · sons variés {'non' if s.get('varier') is False else 'oui'} · famille {s.get('famille') or 'auto'} · "
             f"{len(M.get('events') or [])} sons dans la vidéo" + (f" · posés : {', '.join(poses)}" if poses else ''))
    z = reel.get('zoom') or {}
    n_emo = sum(len(c.get('emojis') or []) for c in reel.get('clips') or [])
    n_sug = sum(len(v or []) for v in ((reel.get('suggestions') or {}).get('emojis') or {}).values())
    L.append(f"IMAGE : zooms {'auto' if z.get('auto') else 'non'} (force {_f(z.get('strength'), 3)}, poussée "
             f"{_f(z.get('push'), 3)}) · flash {'oui' if (reel.get('flash') or {}).get('enabled') else 'non'} · emojis "
             f"{'oui' if (reel.get('emoji') or {}).get('enabled') else 'non'} ({n_emo} posés, {n_sug} proposés) · barre de "
             f"progression {'oui' if (reel.get('progress') or {}).get('enabled') else 'non'} · voix "
             f"{(reel.get('audio') or {}).get('voice', 'naturel')}")
    rap = _rappel(reel)
    if rap:
        L.append('DERNIÈRES DEMANDES (de la plus ancienne à la plus récente) :')
        L += rap
    L.append(f'DEMANDE : « {texte} »')
    out = '\n'.join(L)
    if len(out) > CONTEXTE_MAX:  # garde-fou : la demande reste toujours a la fin
        out = out[:CONTEXTE_MAX - len(L[-1]) - 40] + '\n[… résumé tronqué]\n' + L[-1]
    return out


# ---------- interpretation : Claude, puis Qwen (local), puis regles ----------
def _forme(d):
    """Reponse de l'IA ramenee a {reponse, question, operations, refus} ; None si inutilisable."""
    if not isinstance(d, dict):
        return None
    ops = d.get('operations')
    if ops is None and isinstance(d.get('ops'), list):
        ops = d['ops']
    if not isinstance(ops, list):
        ops = []
    ref = [r for r in d.get('refus') or [] if isinstance(r, dict)] if isinstance(d.get('refus'), list) else []
    return {'reponse': str(d.get('reponse') or '').strip()[:400],
            'question': str(d.get('question') or '').strip()[:400],
            'operations': [o for o in ops if isinstance(o, dict)][:30],
            'refus': [{'demande': str(r.get('demande') or '')[:200], 'raison': str(r.get('raison') or '')[:300]}
                      for r in ref][:10]}


def _qwen_requete(sys_txt, contenu, sch):
    """Qwen (serveur llama.cpp deja demarre par llm.session) contraint par le MEME schema (grammaire json_schema) ;
    serveur qui refuse le schema (400) : llm.ask_json, comme les autres modules."""
    from . import llm
    body = json.dumps({'messages': [{'role': 'system', 'content': sys_txt}, {'role': 'user', 'content': contenu}],
                       'temperature': 0.1, 'max_tokens': SORTIE_MAX,
                       'response_format': {'type': 'json_schema',
                                           'json_schema': {'name': 'consigne', 'strict': True, 'schema': sch}}}).encode()
    req = urllib.request.Request(f'{llm.URL}/v1/chat/completions', data=body, headers={'content-type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(json.loads(r.read())['choices'][0]['message']['content'])
    except urllib.error.HTTPError as e:
        if e.code != 400:
            raise
    return llm.ask_json(sys_txt, contenu + '\nRéponds par un objet JSON {"reponse", "question", "operations", "refus"}.',
                        temperature=0.1, max_tokens=SORTIE_MAX)


def _qwen(sys_txt, contenu, sch):
    """-> (reponse ou None, remarque). IA locale coupee (EDITEUR_LLM=0), absente ou en panne : None."""
    from . import llm
    if os.environ.get('EDITEUR_LLM', '1') == '0':
        return None, 'IA locale coupée (EDITEUR_LLM=0) : règles simples.'
    try:
        dispo = bool(llm.available())
    except Exception:
        dispo = False
    if not dispo:
        return None, 'IA locale absente : règles simples.'
    try:
        with llm.session():
            d = _forme(_qwen_requete(sys_txt, contenu, sch))
        return d, '' if d is not None else 'Réponse de l\'IA locale illisible : règles simples.'
    except Exception as e:
        return None, f'IA locale indisponible ({_court(e, 120)}) : règles simples.'


def _interpreter(project_dir, rid, reel, M, t, texte, moteur):
    """-> (reponse {reponse, question, operations, refus}, moteur utilise, cout $, remarques, modele ou None)."""
    cat = catalogue()
    sch, sys_txt = schema(cat), systeme(cat)
    ctx = contexte(reel, M, t, texte)
    remarques, cout = [], 0.0
    if moteur in ('auto', 'claude'):
        from . import claude_api
        r = claude_api.appeler('consigne', sys_txt, ctx, sch, video=(str(project_dir), rid),
                               modele=claude_api.modele_pour('consigne'), max_tokens=SORTIE_MAX)
        cout += float(r.get('cout') or 0)
        d = _forme(r.get('donnees')) if r.get('ok') else None
        if d is not None:
            return d, 'claude', cout, remarques, r.get('modele')
        remarques.append(r.get('raison') or 'Réponse de Claude inutilisable. L\'outil continue en local.')
        if moteur == 'claude':
            raise ConsigneErreur(remarques[-1])
    d, rq = _qwen(sys_txt, ctx, sch)
    if d is not None:
        return d, 'local', cout, remarques, None
    if rq:
        remarques.append(rq)
    return _regles(texte, reel, M, t), 'regles', cout, remarques, None


# ---------- regles simples (sans IA) ----------
# « coupe la musique » = enlever ; « quand ca coupe » (une coupe du montage) n'est PAS une negation
NEG = (r"\b(?:enleve\w*|enlev|retire\w*|ote\w*|supprime\w*|efface\w*|cache\w*|coupe[rz]? (?:la|le|les|l'|moi|tous|toutes)|"
       r"arrete\w*|aucune?|sans|pas d[e']|pu d[e']|pus d[e']|plus du tout|veux pas|veux plus|retirez|enlevez)\b")
FILLER = re.compile(r"^(?:s'?il (?:te|vous) plait|stp|svp|merci\w*|ok|okay|bon|alors|la|ici|aussi|bin|ben|genre|"
                    r"j'?aimerais|je voudrais|peux[- ]tu|tu peux|est-ce que tu peux|pourrais-tu|)$")
# morceau qui n'est qu'un moment (« a 0:12 ») : le temps sert aux autres morceaux, ce n'est pas une demande
TEMPS_SEUL = re.compile(r"(?:(?:a|vers|de|du|au|a partir de|ici)\s+)?\d{1,2}:\d{2}(?:[.,]\d)?(?:\s*s)?|(?:a|vers)\s+\d{1,3}\s*(?:s|sec|secondes?)")
# morceau qui continue le precedent sans redire de quoi il parle (« la musique est trop forte, baisse-la » ; « ... le meme son
# de vent, j'aimerais en avoir plusieurs sortes ») : relu avec le sujet du morceau d'avant
SUITE = re.compile(r"-(?:la|le|les|lui)\b|\ben (?:avoir|mettre|faire|rajouter|ajouter)\b|plusieurs (?:sortes|genres|types)|"
                   r"\bdifferen|\bvari|\bpareils?\b|\b(?:plus|moins|trop) (?:forte?s?|gros|grosses?|petite?s?|grande?s?|basse?s?)\b")
AUTRE = re.compile(r'photo|image|video|logo|titre|carte|prise|voix|notification|bouton|cadre|texte|\bplan\b')
SUJETS = (('musique_', 'musique'), ('bruitages_', 'sons'), ('sous_titres_', 'sous-titres'), ('mots_forts_', 'mots en couleur'),
          ('bandeau_', 'bandeau'), ('zooms', 'zooms'), ('emojis', 'emojis'))
# genres d'elements nommes dans une demande d'enlever (« enleve la notification a 0:12 » : pas le chiffre voisin)
GENRES_DITS = ('notification', 'chiffre', 'liste', 'tableau', 'bouton', 'parcours', 'comparaison', 'mot geant', 'mot cle',
               'vecteur', 'icone', 'plan de coupe', 'logo', 'produit', 'autocollant')


def _couleur_dans(m):
    for k in sorted(COULEURS, key=len, reverse=True):
        if re.search(rf'\b{k}e?s?\b', m):
            return COULEURS[k]
    m2 = HEX.search(m)
    return m2.group(0).upper() if m2 else None


def _regles(texte, reel, M, t):
    """Repli sans IA : les demandes simples les plus courantes, une par morceau de phrase (« et », « pis », virgules).
    Un morceau non compris -> refus (une note sera laissee) ; une demande qui ne precise pas assez -> question."""
    _index(M)
    citations = re.findall(r'[«"“]\s*(.+?)\s*[»"”]', texte)
    brut = texte
    for k, c in enumerate(citations):
        brut = brut.replace(c, f' qq{k} ')
    morceaux = [x.strip() for x in re.split(r"\s*(?:[,;.!?]|\bet\b|\bpis\b|\bpuis\b|\bensuite\b|\baussi\b)\s*", _norm(brut))
                if x and x.strip()]
    ops, refus, questions, compris = [], [], [], []
    styles = _styles()
    amb = _ambiances()
    familles = _familles()
    temps = _temps_cites(texte)

    def cit(m):
        k = re.search(r'qq(\d)', m)
        return citations[int(k.group(1))] if k and int(k.group(1)) < len(citations) else None

    def un(m):
        """Un morceau de la demande : ops, questions, refus (et compris) completes sur place."""
        neg = bool(re.search(NEG, m))
        fort = bool(re.search(r'\b(?:beaucoup|vraiment|ben trop|bin trop|full|tellement|trop trop|way trop)\b', m))
        dur = re.search(r'\b(15|30|60)\s*(?:s|sec|secs|secondes?)\b', m)
        if dur and re.search(r'version|declin|fais|format|raccourc|duree|coupe', m):
            ops.append({'op': 'declinaison', 'duree': int(dur.group(1)),
                        'intention': 'rapide' if re.search(r'rapide|dynamique|nerveu', m) else
                        'emotion' if re.search(r'emotion|touchant', m) else 'aucune'})
        elif re.search(r'\bstyle\b', m) and not re.search(r'sous[- ]?titre|soustitre|caption|police', m):
            # le style dont le plus de mots (nom ou id) sont dans la demande ; egalite -> question
            score = {}
            for sid, nom in styles.items():
                mots_style = {x for x in re.split(r"[\s/'.-]+", f'{_norm(nom)} {sid}') if len(x) >= 3 or re.search(r'\d', x)}
                mots_style -= {'style', 'mon', 'les', 'des', 'une'}
                score[sid] = sum(1 for x in mots_style if re.search(rf'\b{re.escape(x)}\b', m))
            best = max(score.values(), default=0)
            gagnants = [s for s, n in score.items() if n == best and n > 0]
            if len(gagnants) == 1:
                ops.append({'op': 'style', 'style': gagnants[0]})
            elif gagnants:
                questions.append('Quel style veux-tu : ' + ' ou '.join(f'« {styles[s]} »' for s in gagnants[:4]) + ' ?')
            else:
                questions.append('Quel style veux-tu ? Par exemple : ' + ', '.join(list(styles.values())[:6]) + '…')
        elif re.search(r'\bmusique|\btoune|\bchanson|\bbeat\b|son de fond|fond musical', m):
            ambiance = next((k for k in amb if re.search(rf'\b{k[:5]}', m)), None)
            if re.search(r'\bpiano\b', m) and 'emotion' in amb:
                ambiance = 'emotion'
            if re.search(r'\bcalme|\brelax|\bdetente|\btranquille|\bchill', m) and 'lofi' in amb:
                ambiance = 'lofi'  # « une musique plus calme » : une autre ambiance, pas « remettre la musique »
            if neg and not re.search(r'trop|moins|baisse', m):
                ops.append({'op': 'musique_activer', 'actif': False})
            elif re.search(r'trop forte?|trop haute?|baisse|moins forte?|plus bas|plus douce?|moins haute?|enterre|couvre', m):
                ops.append({'op': 'musique_volume', 'sens': 'beaucoup_moins' if fort else 'moins'})
            elif re.search(r'pas assez|monte|plus forte?|augmente|entend (?:pas|presque pas)|trop basse?|trop faible', m):
                ops.append({'op': 'musique_volume', 'sens': 'beaucoup_plus' if fort else 'plus'})
            elif ambiance:
                ops.append({'op': 'musique_ambiance', 'ambiance': ambiance})
            elif re.search(r'remets|ajoute|met(?:s)? de la|met(?:s)? une', m):
                ops.append({'op': 'musique_activer', 'actif': True})
            else:
                questions.append('Que veux-tu changer à la musique : plus forte, moins forte, l\'enlever, ou une autre '
                                 'ambiance ?')
        elif re.search(r'emoji|emoticon|smiley|binette|bonhomme', m):
            if neg or re.search(r'trop', m):
                ops.append({'op': 'emojis', 'actif': False})
            else:
                ops.append({'op': 'emojis', 'actif': True})
        elif re.search(r'bruitage|effets? sonores?|\bsons?\b|whoosh|woosh|swoosh|wouch|\bvent\b|\bpops?\b|\bclics?\b', m) \
                and not re.search(r'\bvoix\b', m):
            fam = next((k for k, v in familles.items() if re.search(rf'\b(?:{re.escape(k)}|{re.escape(_norm(v))})s?\b', m)), None)
            if fam and not neg:
                ops.append({'op': 'bruitages_famille', 'famille': fam})
            elif re.search(r'meme son|toujours (?:le meme|pareil)|pareil|vari|differents?|plusieurs sortes|autres? sons?|'
                         r'change(?:r)? (?:le|les) sons?|\bvent\b', m) and \
                    not re.search(r'enleve|retire|aucun|supprime|coupe[rz]? (?:les|tous)|moins de|trop de', m):
                ops.append({'op': 'bruitages_varier', 'actif': True})
            elif re.search(r'trop forts?|baisse|moins forts?', m) and not re.search(r'trop de', m):
                ops.append({'op': 'bruitages_volume', 'sens': 'moins'})
            elif re.search(r'plus forts?|monte|pas assez forts?', m):
                ops.append({'op': 'bruitages_volume', 'sens': 'plus'})
            elif re.search(r'moins de|trop de|en trop|\bmoins\b', m):
                ops.append({'op': 'bruitages_quantite', 'niveau': 'moins'})
            elif neg:
                ops.append({'op': 'bruitages_quantite', 'niveau': 'aucun'})
            elif re.search(r'plus de|ajoute|rajoute|davantage|encore des', m):
                ops.append({'op': 'bruitages_quantite', 'niveau': 'plus'})
            else:
                questions.append('Que veux-tu changer aux bruitages : moins, plus, aucun, ou des sons variés ?')
        elif re.search(r'\bzoom|\bpunch|rapproche', m):
            if neg and not re.search(r'\bmoins\b|trop', m):
                ops.append({'op': 'zooms', 'niveau': 'aucun'})
            elif re.search(r'\bmoins\b|trop', m):
                ops.append({'op': 'zooms', 'niveau': 'moins'})
            else:
                ops.append({'op': 'zooms', 'niveau': 'plus'})
        elif re.search(r'bandeau|banniere|titre (?:du|en) haut|bande du haut', m):
            if cit(m) and not neg:
                ops.append({'op': 'bandeau_texte', 'texte': cit(m)})
            elif neg:
                ops.append({'op': 'bandeau_afficher', 'actif': False})
            elif re.search(r'affiche|montre|remets|remet', m):
                ops.append({'op': 'bandeau_afficher', 'actif': True})
            else:
                questions.append('Que veux-tu pour le bandeau : un autre texte (écris-le entre guillemets), ou l\'enlever ?')
        elif re.search(r'\bbouton\b|appel a l.action|\bcta\b', m) and cit(m):
            ops.append({'op': 'bouton_texte', 'texte': cit(m)})
        elif re.search(r'\bflash', m):
            ops.append({'op': 'flash', 'actif': not neg})
        elif re.search(r'barre de progression|progression', m):
            ops.append({'op': 'barre_progression', 'actif': not neg})
        elif re.search(r'\bcarre\b|1:1|horizonta|paysage|16:9|youtube|4:5|\bvertical', m) and \
                re.search(r'format|mets|met|en |fais', m):
            f = '1:1' if re.search(r'carre|1:1', m) else '16:9' if re.search(r'horizonta|paysage|16:9|youtube', m) else \
                '4:5' if '4:5' in m else '9:16'
            ops.append({'op': 'format', 'format': f})
        elif re.search(r'\bvoix\b', m) and re.search(r'radio|podcast|naturel', m):
            ops.append({'op': 'voix', 'traitement': 'radio' if 'radio' in m else 'podcast' if 'podcast' in m else 'naturel'})
        elif _couleur_dans(m):
            c = _couleur_dans(m)
            if re.search(r'\bmots?\b.*(?:cle|fort|couleur|important|surlign|valeur)|mots? en couleur|surlign', m):
                ops.append({'op': 'mots_forts_couleur', 'couleur': c})
            elif re.search(r'sous[- ]?titre|soustitre|\btexte|ecrit|lettre|caption', m):
                ops.append({'op': 'sous_titres_couleur', 'couleur': c})
            else:
                questions.append(f'Qu\'est-ce que tu veux en {_nom_couleur(c)} : le texte des sous-titres, les mots en '
                                 'couleur, ou une carte à l\'écran ?')
        elif re.search(r'sous[- ]?titre|soustitre|\btexte|ecrit|lettre', m) and \
                re.search(r'gros|grand|petit|majuscule|minuscule|en haut|plus haut|en bas|plus bas|milieu|centre', m):
            if re.search(r'majuscule', m):
                ops.append({'op': 'sous_titres_majuscules', 'actif': not neg})
            elif re.search(r'minuscule', m):
                ops.append({'op': 'sous_titres_majuscules', 'actif': False})
            elif re.search(r'plus petit|trop gros|trop grand|\bpetit', m):
                ops.append({'op': 'sous_titres_taille', 'sens': 'plus_petit'})
            elif re.search(r'gros|grand', m):
                ops.append({'op': 'sous_titres_taille', 'sens': 'plus_grand'})
            elif re.search(r'en haut|plus haut', m):
                ops.append({'op': 'sous_titres_position', 'position': 'haut'})
            elif re.search(r'milieu|centre', m):
                ops.append({'op': 'sous_titres_position', 'position': 'milieu'})
            else:
                ops.append({'op': 'sous_titres_position', 'position': 'bas'})
        elif neg and re.search(r'carte|notification|graphisme|chiffre|element|affichage|interface|tableau|liste|'
                               r'mot geant|vecteur|icone|plan de coupe|bouton|parcours|logo', m):
            # un moment ecrit (« a 0:12 ») passe avant le lecteur ; « ici », « la » (« là ») = temps du lecteur
            cites = _temps_cites(m) or temps
            quand = cites[0] if cites else (t if re.search(r'\bici\b|\bla\b|cette place|maintenant|ce moment|ce bout', m) else None)
            genres = [g for g in GENRES_DITS if re.search(rf'\b{g}', m)]
            if quand is None:
                questions.append('Quel élément veux-tu enlever ? Place la lecture dessus et dis « ici », ou donne le moment '
                                 '(ex. 0:12).')
            else:
                vis = []
                for nom in LISTES:
                    for e in reel.get(nom) or []:
                        iv = intervalle(nom, e, M) if isinstance(e, dict) else None
                        if iv and iv[0] - 0.3 <= quand <= iv[1] + 0.3 and _etat(reel, nom, e, M['_places']).startswith('affiché') \
                                and (not genres or any(g in _norm(_nom(nom, e)) for g in genres)):
                            vis.append(e)
                if len(vis) == 1:
                    ops.append({'op': 'element_masquer', 'id': str(vis[0]['id'])})
                elif not vis:
                    refus.append({'demande': _court(m, 120), 'raison': f"Aucun élément{f' de ce genre ({genres[0]})' if genres else ''}"
                                                                      f' affiché à {_tc(quand)}.'})
                    compris.append(m)
                else:
                    questions.append(f'Il y a {len(vis)} éléments à {_tc(quand)} : lequel veux-tu enlever ?')
        elif re.search(r'\bcouleur', m):
            questions.append('Quelle couleur veux-tu, et pour quoi : le texte des sous-titres, les mots en couleur, ou '
                             'une carte à l\'écran ?')

    sujet = None
    for m in morceaux:
        if FILLER.match(m) or len(m) < 3 or TEMPS_SEUL.fullmatch(m):
            continue
        avant, n = len(ops) + len(questions) + len(compris), len(ops)
        un(m)
        suite = len(ops) + len(questions) + len(compris) == avant and sujet and SUITE.search(m) and not AUTRE.search(m)
        if suite:
            un(f'{sujet} {m}')
        if len(ops) + len(questions) + len(compris) > avant:
            sujet = next((mot for o in reversed(ops[n:]) for pre, mot in SUJETS if o['op'].startswith(pre)), sujet)
            if suite:  # deja demande dans le morceau d'avant : pas deux fois (« trop forte, baisse-la » = une seule baisse)
                deja = {o['op'] for o in ops[:n]}
                ops[n:] = [o for o in ops[n:] if o['op'] not in deja]
            compris.append(m)
        else:
            refus.append({'demande': _court(m, 120), 'raison': 'Sans l\'IA (Claude et l\'IA locale indisponibles), je comprends '
                          'seulement les demandes simples : couleur des sous-titres, musique, emojis, bruitages, zooms, '
                          'bandeau, style, format, version de 15/30/60 s.'})
    if questions:
        return {'reponse': '', 'question': questions[0], 'operations': [], 'refus': []}
    return {'reponse': (f'Règles simples (sans IA) : {len(ops)} changement{"s" if len(ops) > 1 else ""}.' if ops else ''),
            'question': '', 'operations': ops, 'refus': refus}


# ---------- application des operations ----------
class _Edition:
    """Applique les operations validees sur une COPIE du reel (R) ; M = montage calcule AVANT les operations (les temps
    donnes par l'IA y renvoient)."""

    def __init__(self, project_dir, rid, reel, M, t, simule=False, texte=''):
        self.project_dir, self.rid, self.R, self.M = Path(project_dir), rid, reel, _index(M)
        self.total, self.t, self.simule = float(M['duration']), t, simule
        self.texte = str(texte or '')  # la demande telle qu'ecrite (deverrouiller : seulement si elle le dit)
        self.changements, self.refus, self.remarques = [], [], []
        self.figer, self.plages, self.notes = set(), [], []
        self.style_change = False
        self.passage = self.declinaison = self.coupe = None
        self.cat = catalogue()

    # -- compte rendu --
    def change(self, quoi, detail, t=None):
        c = {'quoi': quoi, 'detail': detail}
        if t is not None and math.isfinite(float(t)):
            c['t'] = round(float(t), 2)
        self.changements.append(c)

    def plage(self, a, b):
        if a is not None and b is not None:
            self.plages.append((float(a), float(b)))

    # -- verifications communes --
    def _nom_op(self, nom):
        """Nom d'operation du catalogue ; la sortie structuree ne garantit pas la casse des valeurs « const » / « enum »
        (doc Anthropic) : comparaison sans la casse."""
        if nom in self.cat or not isinstance(nom, str):
            return nom
        return next((k for k in self.cat if k.casefold() == nom.strip().casefold()), nom)

    def _types(self, op):
        """Parametres de l'operation conformes au schema (types, valeurs fermees, sans la casse) ; nombres finis."""
        nom = op.get('op')
        if nom not in self.cat:
            raise _Refus(f'Opération « {_court(nom, 40)} »', 'Je ne sais pas faire cette opération.')
        params = self.cat[nom][2]
        p = {}
        for k, sch in params.items():
            v = op.get(k)
            ty = sch.get('type')
            if v is None:
                raise _Refus(_decrire(op), f'Paramètre « {k} » manquant.')
            if ty == 'number':
                if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)):
                    raise _Refus(_decrire(op), f'« {k} » doit être un nombre de secondes.')
                v = float(v)
            elif ty == 'integer':
                if isinstance(v, bool) or not isinstance(v, (int, float)) or float(v) != int(v):
                    raise _Refus(_decrire(op), f'« {k} » doit être un nombre entier.')
                v = int(v)
            elif ty == 'boolean':
                if not isinstance(v, bool):
                    raise _Refus(_decrire(op), f'« {k} » doit être vrai ou faux.')
            elif not isinstance(v, str):
                raise _Refus(_decrire(op), f'« {k} » doit être un texte.')
            else:
                v = v.strip()
            if 'enum' in sch and v not in sch['enum']:
                v = next((x for x in sch['enum'] if isinstance(x, str) and isinstance(v, str) and x.casefold() == v.casefold()), v)
                if v not in sch['enum']:
                    raise _Refus(_decrire(op), f'Valeur inconnue pour « {k} » : {_court(v, 40)}.')
            p[k] = v
        return p

    def _couleur(self, op, c):
        if not HEX.fullmatch(c or ''):
            raise _Refus(_decrire(op), f'Couleur invalide « {_court(c, 20)} » (#RRGGBB attendu).')
        return c.upper()

    def _temps(self, op, x, nom='le moment'):
        if not 0 <= x <= self.total + 0.05:
            raise _Refus(_decrire(op), f'{nom[0].upper() + nom[1:]} ({_tc(x)}) est en dehors de la vidéo (0:00 à '
                                       f'{_tc(self.total)}).')
        return min(x, self.total)

    def _texte(self, op, x, n=60):
        x = re.sub(r'\s+', ' ', str(x or '')).strip()
        if not x:
            raise _Refus(_decrire(op), 'Texte vide.')
        if len(x) > n:
            raise _Refus(_decrire(op), f'Texte trop long ({len(x)} caractères, {n} au plus).')
        return x

    def _element(self, op, eid):
        for nom in LISTES:
            for e in self.R.get(nom) or []:
                if isinstance(e, dict) and str(e.get('id')) == str(eid):
                    return nom, e
        raise _Refus(_decrire(op), f'Élément « {_court(eid, 40)} » introuvable (il a peut-être changé avec le style).')

    def _libre(self, op, nom, e):
        if verrous.is_locked(e):
            raise _Refus(_decrire(op, nom, e), f'{_nom(nom, e)} verrouillé (🔒) : déverrouille-le d\'abord.')

    def _ou(self, nom, e):
        iv = intervalle(nom, e, self.M)
        return iv[0] if iv else None

    def _retouche(self, nom, e, figer=False):
        """Retouche du monteur : plus aucune passe automatique n'y touche. Scene affichee et encore automatique : figee
        a sa place affichee par _figer (edited pose APRES le calcul de cette place, sinon elle sauterait)."""
        e.pop('sobriete', None)
        if nom == 'styleScenes' and figer and not verrous.protege(e) and not e.get('hidden'):
            self.figer.add(str(e['id']))
        else:
            if nom == 'styleScenes':
                e['edited'] = True
            e['manual'] = True
        iv = intervalle(nom, e, self.M)
        if iv:
            self.plage(*iv)

    # -- sous-titres --
    def op_sous_titres_couleur(self, p, op):
        c = self._couleur(op, p['couleur'])
        st = self.R.setdefault('style', {})
        avant = st.get('color')
        st['color'] = c
        self.change('Sous-titres', f'Texte des sous-titres en {_nom_couleur(c)}' + (f' (avant {avant}).' if avant and avant != c else '.'))

    def op_mots_forts_couleur(self, p, op):
        c = self._couleur(op, p['couleur'])
        st = self.R.setdefault('style', {})
        avant = st.get('highlight')
        st['highlight'] = c
        self.change('Sous-titres', f'Mots en couleur en {_nom_couleur(c)}' + (f' (avant {avant}).' if avant and avant != c else '.'))

    def op_sous_titres_modele(self, p, op):
        pr = _presets()[p['modele']]
        self.R['style'] = {**(self.R.get('style') or {}), **pr['style'], 'preset': pr['id']}
        brand = self.R.get('brand') or {}
        if brand.get('style'):  # la charte du client passe par-dessus (comme reel._apply_template)
            self.R['style'].update({k: v for k, v in brand['style'].items() if v})
        self.change('Sous-titres', f"Sous-titres au modèle « {pr.get('name') or pr['id']} »"
                    + (' (couleurs de la charte gardées).' if brand.get('style') else '.'))

    def op_sous_titres_taille(self, p, op):
        st = self.R.setdefault('style', {})
        avant = float(st.get('size') or 72)
        apres = round(min(160.0, max(36.0, avant * (1.15 if p['sens'] == 'plus_grand' else 1 / 1.15))))
        st['size'] = apres
        self.change('Sous-titres', f"Sous-titres plus {'grands' if apres > avant else 'petits'} (taille {_f(avant, 0)} → {apres}).")

    def op_sous_titres_position(self, p, op):
        st = self.R.setdefault('style', {})
        st['position'] = POSITIONS[p['position']]
        self.change('Sous-titres', f"Sous-titres placés {'au ' if p['position'] == 'milieu' else 'en '}{p['position']}.")

    def op_sous_titres_majuscules(self, p, op):
        self.R.setdefault('style', {})['uppercase'] = p['actif']
        self.change('Sous-titres', 'Sous-titres en majuscules.' if p['actif'] else 'Sous-titres en minuscules.')

    def op_sous_titres_police(self, p, op):
        self.R.setdefault('style', {})['font'] = p['police']
        self.change('Sous-titres', f"Police des sous-titres : {p['police']}.")

    def op_sous_titres_mots(self, p, op):
        n = p['nombre']
        if not 1 <= n <= 6:
            raise _Refus(_decrire(op), 'Entre 1 et 6 mots par écran.')
        self.R.setdefault('style', {})['maxWords'] = n
        self.change('Sous-titres', f'{n} mot{"s" if n > 1 else ""} par écran au plus.')

    # -- mots dits --
    def _occurrences(self, op, texte, exact=False):
        """Endroits ou ce mot / cette expression est dit : [(plan, [indices], temps)] (llm._locate, plan par plan : mot
        exact ou meme racine). exact : mot exact seulement (une correction ne doit jamais toucher un mot voisin, comme
        « close » pour « closés »)."""
        from .llm import _locate
        from .reel import _core
        cles = [x for x in (_core(x) for x in texte.split()) if x]
        out = []
        for c in self.R.get('clips') or []:
            norm = [_core(w.get('w', '')) for w in c.get('words') or []]
            used = set()
            while True:
                if exact:
                    span = next((list(range(i, i + len(cles))) for i in range(len(norm) - len(cles) + 1)
                                 if i not in used and cles and norm[i:i + len(cles)] == cles), None)
                else:
                    span = _locate(norm, texte, used)
                if not span:
                    break
                used.update(span)
                w = self.M['_mots'].get((c['id'], span[0]))
                if w is not None and not any(c['words'][i].get('cut') for i in span):
                    out.append((c, span, float(w['start'])))
        if not out:
            raise _Refus(_decrire(op), f'Je ne trouve pas « {_court(texte, 40)} » dans ce qui est dit.')
        return sorted(out, key=lambda x: x[2])

    def _choisir(self, occ, partout):
        if partout:
            return occ
        if self.t is not None:
            return [min(occ, key=lambda x: abs(x[2] - self.t))]
        return occ[:1]

    def op_mot_couleur(self, p, op):
        texte = self._texte(op, p['texte'], 60)
        if len(texte.split()) > 4:
            raise _Refus(_decrire(op), 'Un mot ou une courte expression (4 mots au plus).')
        occ = self._choisir(self._occurrences(op, texte), p['partout'])
        bloques = [o for o in occ if verrous.is_locked(o[0])]
        occ = [o for o in occ if not verrous.is_locked(o[0])]
        if not occ:
            raise _Refus(_decrire(op), f"Le plan {bloques[0][0]['id']} est verrouillé (🔒) : ses mots en couleur sont figés.")
        for c, span, _ in occ:
            for i in span:
                c['words'][i]['hl'] = p['actif']
        ou = ', '.join(_tc(o[2]) for o in occ[:5]) + (' …' if len(occ) > 5 else '')
        self.change('Mots en couleur', f"« {texte} » {'en couleur' if p['actif'] else 'sans couleur'} ({ou})"
                    + (f" ; {len(bloques)} endroit(s) dans un plan verrouillé laissé(s) tel(s) quel(s)." if bloques else '.'), occ[0][2])

    def op_mot_corriger(self, p, op):
        avant, apres = self._texte(op, p['avant'], 60), self._texte(op, p['apres'], 60)
        na, nb = len(avant.split()), len(apres.split())
        if na > 4 or (na != nb and not (na == 1 and nb <= 3)):
            raise _Refus(_decrire(op), 'Même nombre de mots avant et après (ou un mot qui devient 3 mots au plus).')
        occ = self._choisir(self._occurrences(op, avant, exact=True), p['partout'])
        bloques = [o for o in occ if verrous.is_locked(o[0])]
        occ = [o for o in occ if not verrous.is_locked(o[0])]
        if not occ:
            raise _Refus(_decrire(op), f"Le plan {bloques[0][0]['id']} est verrouillé (🔒) : ses mots sont figés.")
        neufs = apres.split() if na == nb else [apres]
        for c, span, _ in occ:
            for i, mot in zip(span, neufs):
                w = c['words'][i]
                m = re.match(r'^([«“"(\[¿¡]*)(.*?)([,.;:!?…»”")\]]*)$', str(w.get('w') or ''))
                pre, coeur, suf = m.groups() if m else ('', w.get('w', ''), '')
                if coeur[:1].isupper() and mot[:1].islower():
                    mot = mot[:1].upper() + mot[1:]
                w.setdefault('asr', w.get('w'))  # texte d'origine de la transcription (comme orthographe.py)
                w['w'] = f'{pre}{mot}{suf}'
        self.change('Sous-titres', f"« {avant} » corrigé en « {apres} » ({', '.join(_tc(o[2]) for o in occ[:5])}).", occ[0][2])

    # -- bandeau --
    def op_bandeau_texte(self, p, op):
        texte = self._texte(op, p['texte'], 80)
        b = self.R.get('banner') or {'enabled': False, 'text': '', 'start': 0, 'end': 4.5}
        if verrous.is_locked(b):
            raise _Refus(_decrire(op), 'Bandeau verrouillé (🔒) : déverrouille-le d\'abord.')
        self.R['banner'] = {**b, 'text': texte, 'enabled': True, 'manual': True}
        self.change('Bandeau', f'Bandeau : « {texte} » (affiché).', float(b.get('start') or 0))

    def op_bandeau_afficher(self, p, op):
        b = self.R.get('banner') or {'enabled': False, 'text': '', 'start': 0, 'end': 4.5}
        if verrous.is_locked(b):
            raise _Refus(_decrire(op), 'Bandeau verrouillé (🔒) : déverrouille-le d\'abord.')
        if p['actif'] and not str(b.get('text') or '').strip():
            raise _Refus(_decrire(op), 'Le bandeau n\'a pas de texte : dis-moi quoi écrire dedans.')
        self.R['banner'] = {**b, 'enabled': p['actif'], 'manual': True}
        self.change('Bandeau', 'Bandeau affiché.' if p['actif'] else 'Bandeau caché.', float(b.get('start') or 0))

    # -- elements a l'image --
    def op_element_masquer(self, p, op, nom=None, e=None):
        if e is None:
            nom, e = self._element(op, p['id'])
        self._libre(op, nom, e)
        at = self._ou(nom, e)
        deja = (nom == 'styleScenes' and e.get('hidden')) or (nom in ('graphics', 'vectors') and e.get('suggested'))
        if deja:
            self.change(_nom(nom, e), f"{_nom(nom, e)} « {_court(' / '.join(_textes(self.R, nom, e)), 40)} » déjà masqué.", at)
            return
        from .sobriete import _retirer
        rap = {'retires': []}
        _retirer(self.R, {'obj': e, 'type': TYPE_RETRAIT[nom], 'kind': e.get('kind'), 'texte': '', 'at': at if at is not None else -1},
                 'retiré à ta demande', rap)
        if nom != 'broll':
            self._retouche(nom, e)
            e['sobriete'] = 'retiré à ta demande'
        elif at is not None:
            self.plage(at, at + float(e.get('duration') or 0))
        ou = 'Habillage du style' if nom == 'styleScenes' else 'onglet Graphismes' if nom != 'broll' else 'propositions de plans de coupe'
        tx = ' / '.join(_textes(self.R, nom, e))
        self.change(_nom(nom, e), f"{_nom(nom, e)}{f' « {_court(tx, 40)} »' if tx else ''}"
                    f"{f' à {_tc(at)}' if at is not None else ''} masqué (récupérable : {ou}).", at)

    def op_element_afficher(self, p, op):
        nom, e = self._element(op, p['id'])
        self._libre(op, nom, e)
        extras, mode = _extras(self.R)
        if nom == 'broll':
            raise _Refus(_decrire(op, nom, e), 'Ce plan de coupe est déjà dans le montage' + ('.' if extras else
                         ' ; ce style masque les plans de coupe.'))
        if nom == 'styleScenes':
            if not mode:
                raise _Refus(_decrire(op, nom, e), 'Ce style n\'affiche pas les cartes : choisis un style avec habillage.')
            if (e.get('clip'), e.get('index')) not in self.M['_mots']:
                raise _Refus(_decrire(op, nom, e), 'Le mot où cette carte apparaissait a été coupé.')
            e['hidden'] = False
            self._retouche(nom, e, figer=True)
        else:
            e['suggested'] = False
            e.pop('auto', None)
            self._retouche(nom, e)
        at = self._ou(nom, e)
        self.change(_nom(nom, e), f"{_nom(nom, e)} « {_court(' / '.join(_textes(self.R, nom, e)), 40)} »"
                    f"{f' à {_tc(at)}' if at is not None else ''} affiché.", at)

    def op_element_texte(self, p, op):
        nom, e = self._element(op, p['id'])
        self._libre(op, nom, e)
        texte = self._texte(op, p['texte'], 60)
        if nom == 'styleScenes':
            e['text'] = texte
            self._retouche(nom, e, figer=True)
        elif nom == 'graphics':
            champ = {'chiffre': 'label', 'motgeant': 'text', 'coches': 'title', 'carte': 'title'}.get(e.get('kind'))
            if not champ:
                raise _Refus(_decrire(op, nom, e), 'Ce graphisme n\'a pas de texte.')
            e.setdefault('props', {})[champ] = texte.upper() if e.get('kind') == 'motgeant' else texte
            self._retouche(nom, e)
        else:
            raise _Refus(_decrire(op, nom, e), f'Un {_nom(nom, e).lower()} n\'a pas de texte à changer.')
        self.change(_nom(nom, e), f'{_nom(nom, e)} : texte « {texte} ».', self._ou(nom, e))

    def op_element_texte2(self, p, op):
        nom, e = self._element(op, p['id'])
        self._libre(op, nom, e)
        texte = self._texte(op, p['texte'], 120)
        if nom == 'styleScenes':
            if e.get('kind') == 'list':
                avant = [x for x in str(e.get('secondary') or '').split('|') if x.strip()]
                neufs = [x.strip() for x in texte.split('|') if x.strip()]
                if len(neufs) != len(avant):
                    raise _Refus(_decrire(op, nom, e), f'Cette liste suit les mots dits : garde {len(avant)} élément(s) '
                                                       'séparés par « | ».')
                texte = '|'.join(neufs)
            e['secondary'] = texte
            self._retouche(nom, e, figer=True)
        elif nom == 'graphics' and e.get('kind') in ('carte', 'coches'):
            if e['kind'] == 'carte':
                e.setdefault('props', {})['subtitle'] = texte
            else:
                e.setdefault('props', {})['items'] = [x.strip() for x in texte.split('|') if x.strip()][:5]
            self._retouche(nom, e)
        else:
            raise _Refus(_decrire(op, nom, e), 'Cet élément n\'a pas de 2e ligne.')
        self.change(_nom(nom, e), f'{_nom(nom, e)} : 2e ligne « {texte.replace("|", " | ")} ».', self._ou(nom, e))

    def op_element_couleur(self, p, op):
        nom, e = self._element(op, p['id'])
        self._libre(op, nom, e)
        c = self._couleur(op, p['couleur'])
        if nom == 'styleScenes':
            e['color'] = c
            self._retouche(nom, e, figer=True)
        elif nom == 'graphics':
            e.setdefault('props', {})['color'] = c
            self._retouche(nom, e)
        elif nom == 'vectors':
            e['couleurs'] = {**(e.get('couleurs') or {'secondaire': None, 'contour': None}), 'principale': c}
            e['couleursManuelles'] = True
            self._retouche(nom, e)
        else:
            raise _Refus(_decrire(op, nom, e), 'Un plan de coupe n\'a pas de couleur à changer.')
        self.change(_nom(nom, e), f'{_nom(nom, e)} en {_nom_couleur(c)}.', self._ou(nom, e))

    def op_element_deplacer(self, p, op):
        nom, e = self._element(op, p['id'])
        self._libre(op, nom, e)
        debut = self._temps(op, p['debut'], 'le nouveau début')
        avant = self._ou(nom, e)
        if nom == 'styleScenes':
            if e.get('kind') in ('list', 'cta') or e.get('items') or e.get('lead') is not None or e.get('offer') is not None:
                raise _Refus(_decrire(op, nom, e), 'Cette carte suit les mots dits (liste, bouton) : elle ne se déplace pas.')
            mots = [w for w in self.M['words'] if not w.get('hide') and str(w.get('w') or '').strip()]
            if not mots:
                raise _Refus(_decrire(op, nom, e), 'Aucun mot dit où accrocher la carte.')
            w = min(mots, key=lambda x: abs(float(x['start']) - debut))
            e['clip'], e['index'] = w['clip'], w['index']
            self._retouche(nom, e, figer=True)
            debut = float(w['start'])
        else:
            d = float(e.get('duration') or 0)
            e['at'] = round(max(0.0, min(debut, self.total - min(d, 0.6))), 2)
            if e['at'] + d > self.total:
                e['duration'] = round(self.total - e['at'], 2)
            e['manual'] = True
            if nom != 'broll':
                self._retouche(nom, e)
            debut = e['at']
        if avant is not None:
            self.plage(avant, avant + 0.5)
        self.plage(debut, debut + 0.5)
        self.change(_nom(nom, e), f"{_nom(nom, e)} déplacé{f' de {_tc(avant)}' if avant is not None else ''} à {_tc(debut)}.", debut)

    def op_element_duree(self, p, op):
        nom, e = self._element(op, p['id'])
        self._libre(op, nom, e)
        at = self._ou(nom, e) or 0.0
        d = p['duree']
        if not 0.6 <= d <= 15:
            raise _Refus(_decrire(op, nom, e), 'Durée entre 0,6 et 15 s.')
        d = round(min(d, max(0.6, self.total - at)), 2)
        e['duration'] = d
        if nom == 'broll':
            e['manual'] = True
            self.plage(at, at + d)
        else:
            self._retouche(nom, e, figer=nom == 'styleScenes')
            self.plage(at, at + d)
        self.change(_nom(nom, e), f'{_nom(nom, e)} affiché {_f(d, 1)} s.', at)

    def op_element_verrou(self, p, op):
        eid = str(p['id'])
        if not p['actif'] and not re.search(r'verrou|cadenas|debarr|unlock|\block', _norm(self.texte)):
            # un verrou n'est jamais leve par l'IA de son propre chef (pour pouvoir changer un element verrouille)
            raise _Refus(_decrire(op), 'Je déverrouille un élément seulement si tu me le demandes (écris « déverrouille … »).')
        if _norm(eid) in ('bandeau', 'banner'):
            b = self.R.setdefault('banner', {'enabled': False, 'text': '', 'start': 0, 'end': 4.5})
            b['locked'] = p['actif']
            self.change('Bandeau', 'Bandeau verrouillé.' if p['actif'] else 'Bandeau déverrouillé.')
            return
        clip = next((c for c in self.R.get('clips') or [] if str(c.get('id')) == eid), None)
        if clip is not None:
            clip['locked'] = p['actif']
            self.change('Plan', f"Plan {eid} {'verrouillé (mots en couleur et emojis figés)' if p['actif'] else 'déverrouillé'}.")
            return
        nom, e = self._element(op, eid)
        e['locked'] = p['actif']
        self.change(_nom(nom, e), f"{_nom(nom, e)} {'verrouillé' if p['actif'] else 'déverrouillé'}.", self._ou(nom, e))

    def op_tout_masquer(self, p, op):
        n, bloques = 0, 0
        for nom in GENRES[p['genre']]:
            for e in list(self.R.get(nom) or []):
                if not isinstance(e, dict) or e.get('id') is None or not _etat(self.R, nom, e, self.M['_places']).startswith('affiché'):
                    continue
                if verrous.is_locked(e):
                    bloques += 1
                    continue
                self.op_element_masquer({'id': e['id']}, op, nom, e)
                n += 1
        if not n and not bloques:
            raise _Refus(_decrire(op), 'Rien de ce genre n\'est affiché.')
        if bloques:
            self.change('Éléments', f'{bloques} élément(s) verrouillé(s) laissé(s) affiché(s).')

    def op_bouton_texte(self, p, op):
        texte = self._texte(op, p['texte'], 40)
        cta = [s for s in self.R.get('styleScenes') or [] if isinstance(s, dict) and s.get('kind') == 'cta']
        vis = [s for s in cta if not s.get('hidden')] or cta
        if not vis:
            raise _Refus(_decrire(op), 'Il n\'y a pas de bouton d\'appel à l\'action dans ce montage.')
        libres = [s for s in vis if not verrous.is_locked(s)]
        if not libres:
            raise _Refus(_decrire(op), 'Le bouton est verrouillé (🔒) : déverrouille-le d\'abord.')
        for s in libres:
            s['text'] = texte
            self._retouche('styleScenes', s, figer=True)
        self.change('Bouton', f'Bouton : « {texte} »' + (f' ({len(libres)} boutons).' if len(libres) > 1 else '.'),
                    self._ou('styleScenes', libres[0]))

    def op_mot_geant_ajouter(self, p, op):
        texte = self._texte(op, p['texte'], 24)
        if len(texte.split()) > 3:
            raise _Refus(_decrire(op), '3 mots au plus pour un mot géant.')
        debut = self._temps(op, p['debut'])
        if debut > self.total - 0.5:
            raise _Refus(_decrire(op), 'Trop près de la fin de la vidéo.')
        pris = {str(g.get('id')) for g in self.R.get('graphics') or [] if isinstance(g, dict)}
        gid = next(x for x in (f'g-ia-{uuid.uuid4().hex[:6]}' for _ in range(50)) if x not in pris)
        g = {'id': gid, 'kind': 'motgeant', 'at': round(debut, 2), 'duration': round(min(1.2, self.total - debut), 2),
             'props': {'text': texte.upper()}, 'manual': True}
        self.R['graphics'] = sorted((self.R.get('graphics') or []) + [g], key=lambda x: float(x.get('at') or 0) if isinstance(x, dict) else 0)
        self.plage(debut, debut + g['duration'])
        self.change('Mot géant', f'Mot géant « {texte.upper()} » ajouté à {_tc(debut)}.', debut)

    # -- musique --
    def op_musique_volume(self, p, op):
        m = self.R.get('music')
        if not isinstance(m, dict) or not m.get('file'):
            raise _Refus(_decrire(op), 'Il n\'y a pas de musique : choisis d\'abord une ambiance.')
        f = {'plus': 1.35, 'moins': 0.7, 'beaucoup_plus': 1.8, 'beaucoup_moins': 0.45}[p['sens']]
        avant = float(m.get('volume') or 0.14)
        apres = round(min(0.8, max(0.02, avant * f)), 3)
        m['volume'] = apres
        allume = not m.get('enabled') and f > 1
        if allume:
            m['enabled'] = True
        self.change('Musique', f"Musique {'plus' if f > 1 else 'moins'} forte (volume {_f(avant, 3)} → {_f(apres, 3)})"
                    + (' et rallumée.' if allume else '.'))

    def op_musique_ambiance(self, p, op):
        amb = _ambiances()
        if p['ambiance'] not in amb:
            raise _Refus(_decrire(op), 'Musique introuvable dans assets/music.')
        m = self.R.get('music') if isinstance(self.R.get('music'), dict) else {'volume': 0.14}
        self.R['music'] = {**m, 'enabled': True, 'mood': p['ambiance'], 'file': f"music/{p['ambiance']}.ogg",
                           'volume': float(m.get('volume') or 0.14)}
        self.change('Musique', f"Musique : {amb[p['ambiance']]}.")

    def op_musique_activer(self, p, op):
        m = self.R.get('music') if isinstance(self.R.get('music'), dict) else {}
        if p['actif'] and not m.get('file'):
            raise _Refus(_decrire(op), 'Choisis d\'abord une ambiance de musique.')
        self.R['music'] = {**{'mood': None, 'file': None, 'volume': 0.14}, **m, 'enabled': p['actif']}
        self.change('Musique', 'Musique remise.' if p['actif'] else 'Musique enlevée.')

    # -- bruitages --
    def _sfx(self):
        s = self.R.get('sfx')
        if not isinstance(s, dict):
            s = self.R['sfx'] = {'enabled': True, 'transition': None, 'highlight': None, 'highlightGap': 5, 'cta': None,
                                 'start': None, 'volume': 0.4, 'extra': []}
        return s

    def op_bruitages_quantite(self, p, op):
        s, niv = self._sfx(), p['niveau']
        studio = bool(self.M.get('studio'))
        if niv == 'aucun':
            s['enabled'] = False
            self.change('Bruitages', 'Bruitages enlevés (musique et voix gardées).')
            return
        s['enabled'] = True
        gap = float(s.get('highlightGap') or 5)
        if niv == 'moins':
            parts = []
            if s.get('start'):
                s['start'] = None
                parts.append('plus de son au début')
            if s.get('highlight') and (studio or gap * 1.8 > 25):
                s['highlight'] = None
                parts.append('plus de « pop » sur les mots')
            elif s.get('highlight'):
                s['highlightGap'] = round(min(30.0, max(gap, 3.0) * 1.8), 1)
                parts.append(f"un « pop » sur les mots toutes les {_f(s['highlightGap'], 1)} s au plus")
            if not parts:
                s['volume'] = round(max(0.02, float(s.get('volume') or 0.4) * 0.75), 3)
                parts.append('bruitages un peu plus discrets')
            self.change('Bruitages', 'Moins de bruitages : ' + ', '.join(parts) + '.')
        elif niv == 'plus':
            s['highlightGap'] = round(max(2.5, gap / 1.6), 1)
            s['highlight'] = s.get('highlight') or 'pop'
            s['transition'] = s.get('transition') or 'whoosh-court'
            self.change('Bruitages', f"Plus de bruitages : un « {s['highlight']} » sur les mots forts toutes les "
                                     f"{_f(s['highlightGap'], 1)} s, un son à chaque coupe.")
        else:
            from .sobriete import _template
            tpl = _template(self.R, None)
            base = tpl.get('sfx') or {}
            for k in ('transition', 'highlight', 'highlightGap', 'cta', 'start', 'volume'):
                if k in base:
                    s[k] = base[k]
            self.change('Bruitages', 'Bruitages remis comme le style les prévoit.')

    def op_bruitages_volume(self, p, op):
        s = self._sfx()
        avant = float(s.get('volume') or 0.4)
        s['volume'] = round(min(1.0, max(0.02, avant * (1.3 if p['sens'] == 'plus' else 0.7))), 3)
        self.change('Bruitages', f"Bruitages {'plus' if p['sens'] == 'plus' else 'moins'} forts (volume {_f(avant, 3)} → "
                                 f"{_f(s['volume'], 3)}).")

    def op_bruitages_varier(self, p, op):
        s = self._sfx()
        s['varier'] = p['actif']
        self.change('Bruitages', 'Sons de transition variés : chaque coupe a son propre son.' if p['actif'] else
                    'Sons de transition : toujours le même son.')

    def op_bruitages_famille(self, p, op):
        """Famille des sons de coupe : sfxgen.appliquer_famille (groupe « sons », comme le panneau Sons de transition) ->
        sfx.famille + sa reserve sfx.pool (le rendu ne lit que la reserve) ; « auto » = la famille du style."""
        from . import sfxgen
        s = self._sfx()
        try:  # une famille choisie = des sons varies (« toujours le meme son » est leve)
            res = sfxgen.appliquer_famille(self.R, p['famille'], True if s.get('varier') is False else None)
        except Exception as e:
            raise _Refus(_decrire(op), f'Famille de sons impossible ({_court(e, 160)}).') from e
        self.change('Bruitages', f"Sons de transition de la famille « {res['nom']} »"
                                 f"{' (celle du style)' if p['famille'] == 'auto' else ''} : {res['sons']} sons qui changent "
                                 'à chaque coupe.')

    # -- image --
    def op_emojis(self, p, op):
        e = self.R.setdefault('emoji', {})
        e['enabled'] = p['actif']
        if not p['actif']:
            self.change('Emojis', 'Emojis enlevés (gardés en réserve).')
            return
        poses = sum(len(c.get('emojis') or []) for c in self.R.get('clips') or [])
        ajout = 0
        if not poses:  # emojis proposes par l'IA (onglet Texte) : on les pose, hors plans verrouilles
            sug = (self.R.get('suggestions') or {}).get('emojis') or {}
            for c in self.R.get('clips') or []:
                if verrous.is_locked(c):
                    continue
                paires = [list(x) for x in sug.get(c['id']) or [] if isinstance(x, (list, tuple)) and len(x) == 2
                          and isinstance(x[0], int) and x[0] < len(c.get('words') or []) and not c['words'][x[0]].get('cut')]
                if paires:
                    c['emojis'] = sorted(paires, key=lambda x: x[0])
                    sug[c['id']] = [x for x in sug.get(c['id']) or [] if list(x) not in paires]
                    ajout += len(paires)
        self.change('Emojis', 'Emojis affichés' + (f' ({ajout} posés, ceux proposés par l\'IA).' if ajout else
                    '.' if poses else ' (aucun emoji proposé pour cette vidéo : rien ne change à l\'image).'))

    def op_zooms(self, p, op):
        z = self.R.setdefault('zoom', {'auto': False, 'strength': 1.0, 'push': 0.0, 'overrides': {}})
        s0, p0 = float(z.get('strength') or 1.0), float(z.get('push') or 0.0)
        if p['niveau'] == 'aucun':
            z['auto'], z['push'] = False, 0.0
            self.change('Zooms', 'Zooms automatiques enlevés (cadre fixe).')
            return
        if p['niveau'] == 'plus':
            z['auto'] = True
            z['strength'] = round(min(1.25, max(s0, 1.0) + 0.04), 3)
            z['push'] = round(min(0.06, p0 + 0.01), 3)
        else:
            z['strength'] = round(max(1.0, s0 - 0.04), 3)
            z['push'] = round(max(0.0, p0 - 0.01), 3)
        self.change('Zooms', f"{'Plus' if p['niveau'] == 'plus' else 'Moins'} de zooms (force {_f(s0, 3)} → {_f(z['strength'], 3)}).")

    def op_flash(self, p, op):
        self.R['flash'] = {**(self.R.get('flash') or {'kind': 'blanc'}), 'enabled': p['actif']}
        self.change('Image', 'Flashs entre les parties ajoutés.' if p['actif'] else 'Flashs enlevés.')

    def op_barre_progression(self, p, op):
        self.R['progress'] = {**(self.R.get('progress') or {}), 'enabled': p['actif']}
        self.change('Image', 'Barre de progression affichée.' if p['actif'] else 'Barre de progression enlevée.')

    def op_format(self, p, op):
        self.R['width'], self.R['height'] = FORMATS[p['format']]
        self.change('Format', f"Format {p['format']}.")

    def op_voix(self, p, op):
        self.R['audio'] = {**(self.R.get('audio') or {'roomTone': False, 'declip': True}), 'voice': p['traitement']}
        self.change('Voix', f"Traitement de la voix : {p['traitement']} (entendu à l'export).")

    # -- montage --
    def op_style(self, p, op):
        nom = _styles()[p['style']]
        if self.simule:
            self.change('Style', f'Le style « {nom} » serait appliqué.')
            return
        from . import detourage
        from .reel import apply_template
        sons = copy.deepcopy(self.R.get('sfx')) if isinstance(self.R.get('sfx'), dict) else {}
        try:
            with _silence():
                apply_template(self.R, p['style'])  # verrous.sous_protection : retouches et verrous gardes
                if sons.get('famille') or isinstance(sons.get('varier'), bool):
                    # le style remet ses bruitages : les choix « sons de coupe » (varier, famille) sont gardes, comme
                    # sfxgen.appliquer_famille le prevoit apres un changement de style (« auto » = famille du nouveau style)
                    try:
                        from . import sfxgen
                        sfxgen.appliquer_famille(self.R, None, None, avant=sons)
                    except Exception as e:
                        self.remarques.append(f'Famille de sons non gardée ({_court(e, 120)}).')
                if detourage.needs_cutout(self.R):
                    self.remarques.append('Détourage de la personne pour ce style : il peut prendre quelques minutes la '
                                          'première fois.')
                    detourage.prepare(self.R)
        except Exception as e:
            raise _Refus(_decrire(op), f'Style impossible à appliquer ({_court(e, 160)}).') from e
        self.style_change = True
        self.change('Style', f'Style « {nom} » appliqué (tes retouches et les éléments verrouillés sont gardés).')

    def op_couper(self, p, op):
        a, b = self._temps(op, p['debut'], 'le début'), self._temps(op, p['fin'], 'la fin')
        if b - a < 0.15:
            raise _Refus(_decrire(op), 'Passage trop court : choisis le début et la fin des mots à retirer.')
        clips = {c['id']: c for c in self.R.get('clips') or []}
        cibles = [w for w in self.M['words'] if a - 0.02 <= (float(w['start']) + float(w['end'])) / 2 <= b + 0.02]
        if not cibles:
            raise _Refus(_decrire(op), f'Aucun mot entier entre {_tc(a)} et {_tc(b)}.')
        bloques = sorted({w['clip'] for w in cibles if verrous.is_locked(clips.get(w['clip']))})
        if bloques:
            raise _Refus(_decrire(op), f"Le plan {', '.join(bloques)} est verrouillé (🔒) : rien n'est coupé.")
        retire = sum(float(w['end']) - float(w['start']) for w in cibles)
        pris = {(w['clip'], w['index']) for w in cibles}
        if len(pris) >= len(self.M['words']) or retire > 0.5 * self.total:
            raise _Refus(_decrire(op), 'Coupe trop longue (plus de la moitié de la vidéo) : demande plutôt une version '
                                       'plus courte (15, 30 ou 60 s).')
        from . import declinaison
        from .sobriete import phrases
        base = copy.deepcopy(self.R)
        for w in cibles:
            clips[w['clip']]['words'][w['index']]['cut'] = True
        avant, apres = montage.compute(base), montage.compute(self.R)
        # accroche (1re phrase) et derniere phrase de l'appel a l'action : memes reperes que declinaison.create
        ph = phrases(sorted(avant['words'], key=lambda w: w['start']))
        cle = lambda p: [(w['clip'], w['index']) for w in p[2]]
        hook = cle(ph[0]) if ph else []
        cta_b = self.R.get('ctaBlock')
        cta = [p for p in ph if (clips.get(p[2][0]['clip']) or {}).get('block') == cta_b] or ph[-1:]
        rap = declinaison._reanchor(base, self.R, avant, apres, hook, cle(cta[-1]) if cta else [])  # les elements suivent leurs mots
        dit = ' '.join(str(w['w']) for w in cibles)
        self.coupe = (a, b)
        self.change('Montage', f'Passage {_tc(a)} → {_tc(b)} coupé : « {_court(dit, 80)} » ({len(cibles)} mot'
                               f'{"s" if len(cibles) > 1 else ""}, −{_f(float(avant["duration"]) - float(apres["duration"]), 1)} s ; '
                               'rétablissable dans l\'onglet Texte).', a)
        for part in ('retires', 'raccourcis', 'deplaces'):
            for x in rap.get(part) or []:
                self.change('Montage', x['message'][0].upper() + x['message'][1:] + '.', x.get('apres'))

    def op_refaire_passage(self, p, op):
        from .passage import PassageInvalide, verifier
        try:
            a, b, _ = verifier(p['debut'], p['fin'], self.total)
        except PassageInvalide as e:
            raise _Refus(_decrire(op), str(e)) from e
        if self.coupe:
            raise _Refus(_decrire(op), 'Une coupe change les temps : redemande « refaire ce passage » après celle-ci.')
        self.passage = (a, b)
        if self.simule:  # sinon : le compte rendu de passage.refaire (_passage)
            self.change('Passage', f'L\'habillage automatique serait refait de {_tc(a)} à {_tc(b)}.', a)

    def op_declinaison(self, p, op):
        duree, intention = p['duree'], p['intention']
        if not duree and intention == 'aucune':
            raise _Refus(_decrire(op), 'Dis-moi la durée (15, 30 ou 60 s) ou l\'intention (rapide, émotion).')
        if duree and duree >= self.total - 1:
            raise _Refus(_decrire(op), f'La vidéo fait déjà {_f(self.total, 1)} s.')
        self.declinaison = (duree or None, None if intention == 'aucune' else intention)
        quoi = ' '.join(x for x in (f'de {duree} s' if duree else '', {'rapide': 'rapide', 'emotion': 'émotion'}.get(intention, '')) if x)
        self.change('Nouvelle version', f"Nouvelle version {quoi} {'créée' if not self.simule else 'à créer'} (l'originale ne change pas).")

    def op_note(self, p, op):
        texte = self._texte(op, p['texte'], NOTE_TEXTE)
        t = self._temps(op, p['t'])
        self.notes.append((t, texte))
        self.change('Note', f'Note laissée à {_tc(t)} : « {_court(texte, 60)} ».', t)

    # -- tout --
    def appliquer(self, ops):
        def rang(o):
            k = o.get('op')
            if k == 'element_verrou':
                k = 'element_verrou_ouvert' if o.get('actif') is False else 'element_verrou_ferme'
            return ORDRE.get(k, 5)
        ops = [{**o, 'op': self._nom_op(o.get('op'))} for o in ops if isinstance(o, dict)]
        for o in sorted(ops, key=rang):
            try:
                p = self._types(o)
                getattr(self, f"op_{o['op']}")(p, o)
            except _Refus as r:
                self.refus.append({'demande': r.demande, 'raison': r.raison})
        return self


def _decrire(op, nom=None, e=None):
    """Ce qui etait demande, en francais (colonne « demande » d'un refus)."""
    k = op.get('op')
    quoi = {'element_masquer': 'Masquer', 'element_afficher': 'Afficher', 'element_texte': 'Changer le texte de',
            'element_texte2': 'Changer la 2e ligne de', 'element_couleur': 'Changer la couleur de',
            'element_deplacer': 'Déplacer', 'element_duree': 'Changer la durée de',
            'element_verrou': 'Déverrouiller' if op.get('actif') is False else 'Verrouiller'}
    if k in quoi:
        cible = f"{_nom(nom, e).lower()} « {_court(' / '.join(_textes({}, nom, e)) if nom != 'broll' else e.get('id'), 30)} »" \
            if e is not None else f"l'élément {_court(op.get('id'), 30)}"
        return f'{quoi[k]} {cible}'
    lib = {'sous_titres_couleur': 'Couleur des sous-titres', 'mots_forts_couleur': 'Couleur des mots en couleur',
           'mot_couleur': f"Mot « {_court(op.get('texte'), 30)} » en couleur", 'mot_corriger': f"Corriger « {_court(op.get('avant'), 30)} »",
           'bandeau_texte': 'Texte du bandeau', 'bandeau_afficher': 'Bandeau', 'bouton_texte': 'Texte du bouton',
           'mot_geant_ajouter': 'Ajouter un mot géant', 'musique_volume': 'Volume de la musique', 'musique_ambiance': 'Musique',
           'musique_activer': 'Musique', 'couper': 'Couper un passage', 'refaire_passage': 'Refaire un passage',
           'declinaison': 'Version plus courte', 'style': 'Changer de style', 'note': 'Note', 'tout_masquer': 'Tout masquer',
           'bruitages_famille': 'Famille de sons'}
    return lib.get(k, str(k or 'Opération').replace('_', ' ').capitalize())


# ---------- notes, historique, version « avant » ----------
def _note(R, calc, t, texte):
    """Note de revision ouverte (meme forme que newNote de revue.tsx ; acceptee par validateV2 du serveur) ou None."""
    ancre = (calc.get('ancres') or [None])[0]
    if not isinstance(ancre, dict) or not ID_RE.fullmatch(str(ancre.get('clip') or '')) or not isinstance(ancre.get('sig'), str):
        return None
    a = {'clip': ancre['clip'], 'src': round(float(ancre['src']), 4), 'sig': ancre['sig'][:400]}
    for k in ('source', 'image'):
        if isinstance(ancre.get(k), str) and re.fullmatch(r'[A-Za-z0-9_:.-]{1,120}', ancre[k]):
            a[k] = ancre[k]
    mots = calc.get('words') or []
    i = next((k for k, w in enumerate(mots) if float(w['end']) > t), len(mots) - 1)
    phrase = ' '.join(str(w['w']) for w in mots[max(0, i - 3): i + 5])[:200] if mots else ''
    iso = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    pris = {n.get('id') for n in R.get('notes') or [] if isinstance(n, dict)}
    nid = next(x for x in (f"n-{_base36(int(time.time() * 1000))}-{uuid.uuid4().hex[:6]}" for _ in range(50)) if x not in pris)
    return {'id': nid, 't': _snap(t, R.get('fps')), 'anchor': a, 'text': texte[:NOTE_TEXTE], 'statut': 'ouverte',
            'auteur': 'IA', 'cree': iso, 'modifie': iso,
            'contexte': {'titre': str(R.get('title') or '')[:300], 'style': str(R.get('template') or '')[:80],
                         'format': _format_de(R)[:20], 'duree': round(float(calc['duration']), 2),
                         **({'phrase': phrase} if phrase else {})},
            'meta': {'source': 'consigne'}}


def _base36(n):
    chiffres = '0123456789abcdefghijklmnopqrstuvwxyz'
    out = ''
    while n:
        n, r = divmod(n, 36)
        out = chiffres[r] + out
    return out or '0'


def _sauvegarde(project_dir, rid, brut, texte):
    """Copie EXACTE du reel d'avant dans versions/<reel>/ (meme format que le serveur : « AAAA-MM-JJTHH-MM-SS nom.json »,
    heure UTC) ; la derniere copie identique est reprise (pas de doublon). -> nom du fichier (« avant »)."""
    d = Path(project_dir) / 'versions' / rid
    d.mkdir(parents=True, exist_ok=True)
    existants = sorted(f for f in d.glob('*.json'))
    if existants and existants[-1].read_bytes() == brut:
        return existants[-1].name
    propre = re.sub(r'[^\w _-]', '', f'{NOM_VERSION} {texte}', flags=re.UNICODE)
    propre = re.sub(r'\s+', ' ', propre)[:60].strip() or NOM_VERSION
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S')
    nom, k = f'{stamp} {propre}.json', 2
    while (d / nom).exists():
        nom = f'{stamp} {propre} ({k}).json'
        k += 1
    tmp = d / f'{nom}.{os.getpid()}.tmp'
    tmp.write_bytes(brut)
    os.replace(tmp, d / nom)
    return nom


def _id_libre(project_dir, rid):
    """Identifiant de reel libre dans le VRAI projet (declinaison preparee dans un bac)."""
    if not montage.reel_path(project_dir, rid).exists():
        return rid
    for k in range(2, 500):
        tail = f'-{k}'
        x = rid[:60 - len(tail)] + tail
        if not montage.reel_path(project_dir, x).exists():
            return x
    raise ConsigneErreur('Trop de versions de ce montage : supprimes-en quelques-unes.')


class _Bac:
    """Dossier de projet temporaire (runtime/cache/tmp) : passage.refaire et declinaison.create lisent et ecrivent un
    reel sur le disque ; ils travaillent ici sur le reel EN COURS, sans toucher au vrai projet."""

    def __init__(self, rid, reel):
        self.dir = ROOT / 'runtime' / 'cache' / 'tmp' / f'consigne-bac-{os.getpid()}-{uuid.uuid4().hex[:8]}'
        (self.dir / 'reels').mkdir(parents=True, exist_ok=True)
        montage.save(self.dir, rid, reel)

    def __enter__(self):
        return self.dir

    def __exit__(self, *exc):
        shutil.rmtree(self.dir, ignore_errors=True)  # dossier neuf, fichiers seulement (aucune jonction)


def _passage(rid, R, a, b, ed):
    """passage.refaire sur le reel en cours (bac) -> reel refait (ou R tel quel) ; compte rendu dans ed."""
    from . import passage
    with _Bac(rid, R) as bac, _silence():
        res = passage.refaire(bac, rid, a, b)
        ed.change('Passage', str(res.get('resume') or f'Passage {_tc(a)} → {_tc(b)} refait.'), a)
        for c in (res.get('changes') or [])[:12]:
            ed.change('Passage', str(c), a)
        ed.remarques += [str(x) for x in res.get('remarques') or []]
        return montage.load(bac, rid) if res.get('modifie') else R


def _declinaison(project_dir, rid, R, duree, intention, ed):
    """declinaison.create sur le reel en cours (bac) -> (nouvel id libre dans le vrai projet, reel)."""
    from . import declinaison
    with _Bac(rid, R) as bac, _silence():
        res = declinaison.create(bac, rid, duree, intention)
        D = montage.load(bac, res['rid'])
    nid = _id_libre(project_dir, res['rid'])
    D['id'] = nid
    ed.change('Nouvelle version', f"Version « {res.get('label')} » : {_f(res.get('duree'), 1)} s"
              + (f", {len(res.get('phrases_coupees') or [])} phrase(s) coupée(s)" if res.get('phrases_coupees') else '') + '.')
    for m in (res.get('elements_resume') or [])[:8]:
        ed.change('Nouvelle version', str(m)[0].upper() + str(m)[1:] + '.')
    return nid, D


def _relire(R, ed):
    """Relecture du monteur limitee a la plage touchee (les retouches, protegees, ne bougent pas ; les elements
    automatiques qui les chevauchent s'ecartent), puis choregraphie de la meme plage."""
    if not ed.plages or ed.style_change:
        return
    from . import choregraphie, sobriete
    a = max(0.0, min(x for x, _ in ed.plages) - 0.3)
    b = min(ed.total, max(y for _, y in ed.plages) + 0.3)
    if b - a < 0.3:
        b = min(ed.total, a + 0.3)
    try:
        with _silence():
            rel = sobriete.relire(R, None, None, tout=False, plage=(a, b))
        phrases = list(rel.get('retires') or []) + list(rel.get('deplaces') or []) + list(rel.get('corriges') or [])
        for x in phrases[:8]:
            ed.change('Relecture', str(x))
        if phrases:
            R['sobriete'] = {k: rel[k] for k in ('retires', 'deplaces', 'corriges', 'gardes', 'resume') if k in rel}
    except Exception as e:
        ed.remarques.append(f'Relecture non faite ({_court(e, 120)}).')
    try:
        with _silence():
            choregraphie.actualiser(R, None, plage=(a, b))
    except Exception as e:  # la choregraphie est un plus : jamais bloquante
        ed.remarques.append(f'Chorégraphie non recalculée ({_court(e, 120)}).')


def _figer(R, ed, calc):
    """Scenes retouchees : figees a leur place AFFICHEE (x, y, scale de designScenes, comme design-panel.tsx) avant de
    porter edited (sinon la carte sauterait a sa place enregistree)."""
    places = {s['id']: s for s in calc.get('scenes') or []}
    for s in R.get('styleScenes') or []:
        if isinstance(s, dict) and str(s.get('id')) in ed.figer:
            p = places.get(s.get('id'))
            if p:
                for k in ('x', 'y', 'scale'):
                    if isinstance(p.get(k), (int, float)):
                        s[k] = round(float(p[k]), 4)
            s['edited'] = True
            s['manual'] = True


# ---------- la demande ----------
def appliquer(project_dir, rid, texte, t=None, moteur='auto', simuler=False):
    """Traduit la demande en operations et les applique (ou les simule). -> resultat du contrat (voir en tete)."""
    project_dir = Path(project_dir)
    rid = rid or 'script'
    if not ID_RE.fullmatch(str(rid)):
        raise ConsigneErreur('Identifiant de version invalide.')
    texte = re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', ' ', str(texte or '').replace('\r\n', '\n').replace('\r', '\n')).strip()
    if not texte:
        raise ConsigneErreur('Écris ta demande à l\'IA, par exemple : « enlève le bandeau du début ».')
    if len(texte) > TEXTE_MAX:
        raise ConsigneErreur(f'Ta demande est trop longue ({len(texte)} caractères, {TEXTE_MAX} au plus) : raccourcis-la.')
    if moteur not in ('auto', 'claude', 'local'):
        raise ConsigneErreur('Moteur inconnu : auto, claude ou local.')
    if t is not None and (isinstance(t, bool) or not math.isfinite(float(t)) or float(t) < 0):
        raise ConsigneErreur('Moment de la vidéo invalide (secondes).')
    path = montage.reel_path(project_dir, rid)
    if not path.exists():
        raise ConsigneErreur('Montage introuvable : ouvre la vidéo dans l\'éditeur, puis réessaie.')
    brut = path.read_bytes()
    try:
        reel = json.loads(brut.decode('utf-8'))
    except ValueError:
        raise ConsigneErreur('Montage abîmé (JSON illisible) : restaure une version dans l\'onglet Versions.') from None
    M = calcul(reel)
    total = float(M['duration'])
    remarques = []
    if t is not None:
        t = float(t)
        if t > total + 0.05:
            remarques.append(f'Temps du lecteur ({_tc(t)}) ramené à la fin de la vidéo ({_tc(total)}).')
        t = min(t, total)
    d, moteur_utilise, cout, rq, modele = _interpreter(project_dir, rid, reel, M, t, texte, moteur)
    remarques += rq
    res = {**VIDE, 'ok': True, 'version': rid, 'moteur': moteur_utilise, 'cout': round(cout, 6), 'reponse': d['reponse'],
           'simule': bool(simuler), 'remarques': remarques}
    question = d['question'] if d['question'] and d['question'].strip() else None
    entree = {'date': _maintenant(), 'texte': texte, 't': None if t is None else round(t, 2), 'moteur': moteur_utilise,
              'modele': modele, 'cout': round(cout, 6), 'reponse': d['reponse'], 'changements': [], 'refus': [],
              'question': question}
    if question:
        # rien n'est applique ; la question est gardee dans l'historique (la reponse suivante la verra)
        res['question'] = question
        if not simuler:
            _ecrire_historique(path, brut, reel, entree)
        return res
    R = copy.deepcopy(reel)
    ed = _Edition(project_dir, rid, R, M, t, simule=simuler, texte=texte).appliquer(d['operations'])
    refus = list(d['refus']) + ed.refus
    res.update(changements=ed.changements, refus=refus)
    if simuler:
        return {**res, 'remarques': remarques + ed.remarques}
    # passes longues sur le reel en cours : refaire un passage, puis la declinaison (nouvelle version)
    if ed.passage:
        if ed.figer:  # cartes retouchees par cette demande : figees AVANT la passe, sinon elle les referait (retouche perdue)
            _figer(R, ed, calcul(R))
            ed.figer.clear()
        try:
            R = _passage(rid, R, *ed.passage, ed)
        except Exception as e:
            refus.append({'demande': 'Refaire un passage', 'raison': f'Impossible ({_court(e, 160)}).'})
    # notes : celles demandees, et une note OUVERTE pour ce qui n'a pas pu etre fait (rien n'est perdu)
    notes = list(ed.notes)
    if refus:
        quand = t if t is not None else next(iter(_temps_cites(texte)), None)
        notes.append((min(quand or 0.0, total), _court(f"Demande à l'IA pas encore faite : « {texte} » — "
                                                       + ' ; '.join(f"{r['demande']} : {r['raison']}" for r in refus), NOTE_TEXTE)))
    if len(R.get('notes') or []) + len(notes) > 500:  # plafond du serveur (validateV2)
        ed.remarques.append('Trop de notes dans ce montage (500 au plus) : aucune note ajoutée.')
        notes = []
    if ed.figer or notes:
        calc2 = calcul(R, [q for q, _ in notes])  # places affichees des scenes retouchees + ancres des notes
        _figer(R, ed, calc2)
        ancres = list(calc2.get('ancres') or [])
        for k, (q, txt) in enumerate(notes):
            n = _note(R, {**calc2, 'ancres': [ancres[k] if k < len(ancres) else None]}, q, txt)
            if n:
                R['notes'] = (R.get('notes') or []) + [n]
                if refus and k == len(notes) - 1:
                    res['note_ajoutee'] = True
    _relire(R, ed)
    remarques += ed.remarques
    entree.update(changements=ed.changements[:30], refus=refus[:10], note_ajoutee=res['note_ajoutee'])
    res.update(changements=ed.changements, refus=refus, remarques=remarques)
    if ed.declinaison:
        try:
            nid, D = _declinaison(project_dir, rid, R, *ed.declinaison, ed)
        except Exception as e:  # le reste de la demande est quand meme enregistre (refus garde dans l'historique)
            refus.append({'demande': 'Version plus courte', 'raison': f'Impossible ({_court(e, 160)}).'})
            entree['refus'] = refus[:10]
            res['refus'] = refus
            ed.declinaison = None
        else:
            entree.update(changements=ed.changements[:30], version=nid, avant=rid)
            D['consignes'] = ([c for c in D.get('consignes') or [] if isinstance(c, dict)] + [entree])[-HISTORIQUE:]
            montage.save(project_dir, nid, D)
            return {**res, 'version': nid, 'avant': rid, 'changements': ed.changements, 'modifie': True}
    sans_historique = {k: v for k, v in R.items() if k != 'consignes'}
    modifie = sans_historique != {k: v for k, v in reel.items() if k != 'consignes'}
    if path.read_bytes() != brut:
        raise ConsigneErreur('Le montage a été modifié pendant que l\'IA travaillait (retouche dans l\'éditeur ?) : rien '
                             'n\'a été changé. Renvoie ta demande.')
    avant = _sauvegarde(project_dir, rid, brut, texte) if modifie else None
    entree['avant'] = avant
    R['consignes'] = ([c for c in reel.get('consignes') or [] if isinstance(c, dict)] + [entree])[-HISTORIQUE:]
    montage.save(project_dir, rid, R)
    return {**res, 'avant': avant, 'modifie': modifie}


def _ecrire_historique(path, brut, reel, entree):
    """Ajoute une entree a l'historique sans rien changer d'autre (question posee : pas de version « avant »)."""
    if path.read_bytes() != brut:
        raise ConsigneErreur('Le montage a été modifié pendant que l\'IA travaillait : renvoie ta demande.')
    R = dict(reel)
    R['consignes'] = ([c for c in reel.get('consignes') or [] if isinstance(c, dict)] + [entree])[-HISTORIQUE:]
    tmp = path.with_name(f'{path.name}.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(tmp, path)


# ---------- ligne de commande ----------
def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m editeur.consigne',
                                 description="« Dis à l'IA ce que tu veux changer » : applique une demande écrite à un montage.")
    ap.add_argument('projet', help='dossier du projet (projects/<video>)')
    ap.add_argument('--reel', default='script', help='version du reel (script, v1, v1-30-s...)')
    ap.add_argument('--texte', required=True, help='la demande, en français (800 caractères au plus)')
    ap.add_argument('--t', type=float, help='temps du lecteur (s, temps du montage) : « ici »')
    ap.add_argument('--moteur', choices=['auto', 'claude', 'local'], default='auto')
    ap.add_argument('--simuler', action='store_true', help='plan seulement : rien n\'est écrit')
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    try:
        out = appliquer(a.projet, a.reel, a.texte, a.t, a.moteur, a.simuler)
    except ConsigneErreur as e:
        print(json.dumps({**VIDE, 'erreur': str(e)}, ensure_ascii=False))
        raise SystemExit(str(e)) from None
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception as exc:  # defaut imprevu : trace dans runtime/cache/erreurs.log, phrase courte pour l'interface
        import traceback
        from .claude_api import _masquer  # jamais de cle, ni dans le journal ni a l'ecran
        try:
            log = ROOT / 'runtime/cache/erreurs.log'
            log.parent.mkdir(parents=True, exist_ok=True)
            with open(log, 'a', encoding='utf-8') as f:
                f.write(_masquer(f"\n{time.strftime('%Y-%m-%d %H:%M:%S')} editeur.consigne {' '.join(sys.argv[1:2])}\n"
                                 f"{traceback.format_exc()}"))
        except OSError:
            pass
        sys.exit(f'Erreur inattendue : {_masquer(str(exc))[:300]} (détails dans runtime/cache/erreurs.log)')
