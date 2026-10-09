"""Banque locale d'effets, sons, vecteurs et templates (V2 — docs/direction-creative-v2/SPEC.md §9.1 et §9.2).

Tout est local, rien n'est telecharge :
- sons : assets/sfx/editeur (synthese sfxgen.py), assets/sfx/kenney (CC0, licence du pack conservee) et quelques sons
  CREES ICI avec les briques de sfxgen.py (swoosh, whoosh, impacts, risers) dans assets/banque/sons ;
- vecteurs : assets/banque/vecteurs/<nom>.svg + fiche <nom>.json, ecrits par l'agent « vecteurs » (lus s'ils existent,
  re-indexes des qu'ils changent : catalogue() compare une signature des dossiers) ;
- templates : les graphismes existants (chiffre, coches, carte, motgeant, logo) et les scenes des styles (notification,
  avant/apres, tableau, parcours, bouton d'appel a l'action, etiquette, mot cle) avec des reglages par defaut ;
- effets : transitions aux changements de partie (flash), grain (assets/overlays/grain.png), vignette, etalonnage.
La musique (assets/music) n'y est pas : le schema n'a pas de type « musique » (onglet Style → Musique).

Apercus (assets/banque/apercus) : forme d'onde PNG (FFmpeg showwavespic) pour chaque son, le SVG lui-meme pour un
vecteur, une maquette SVG dessinee ici pour chaque template et effet. Licence et provenance pour CHAQUE entree.

Catalogue : assets/banque/catalogue.json = {version, code, construit, signature, compte, ecartes, entrees: [ENTREE...]} ;
ENTREE = {id, type: 'effet'|'son'|'vecteur'|'template', nom, categorie, motsCles, intensite: 1|2|3, formats,
          apercu (relatif a assets/), fichier (relatif a assets/, null pour un template ou un effet), licence,
          provenance, params, description?, duree? (son), source}.
Le serveur lit ce fichier pour GET /api/banque/apercu/<id> ; l'interface (app/ui/banque.tsx) le lit aussi directement
(/assets/banque/catalogue.json) et applique les memes filtres et la meme regle « Ajouter » que ce module.

Icones (ronde 4) : catalogue A PART assets/banque/catalogue-icones.json (meme schema, type « icone ») — bibliotheque
Lucide (ISC, telechargee une fois dans assets/banque/icones/lucide avec sa licence) indexee en francais
(assets/banque/icones/dictionnaire-lucide-fr.json) + icones deposees par le monteur dans assets/banque/import (licence
« À vérifier (importé) »). Voir la section « icones » plus bas.
"""
import copy
import json
import math
import os
import random
import re
import shutil
import subprocess
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import media

TYPES = ('effet', 'son', 'vecteur', 'template')
FORMATS = ['9:16', '16:9', '4:5', '1:1']
VERSION = 1            # schema du catalogue (SPEC §9.1)
CODE = 7               # version des regles de ce module : la changer reconstruit le catalogue au prochain appel
CATALOGUE = 'banque/catalogue.json'    # relatif a assets/
LONGUEUR_MAX = 3.0     # l'export ne joue que les 3 premieres secondes d'un bruitage (remotion/render.mjs) : au-dela, ecarte
NIVEAU_CIBLE = -15.5   # dB : crete RMS (fenetres de 50 ms) des bruitages de l'editeur une fois SFX_GAIN applique
ID_OK = re.compile(r'^[A-Za-z0-9_.:-]{1,120}$')
ACCENT = '#FFD400'
EFFETS_DEFAUT = {'grain': 0, 'vignette': 0, 'grade': 'aucun'}
SFX_DEFAUT = {'enabled': False, 'transition': None, 'highlight': None, 'highlightGap': 4, 'cta': None, 'start': None, 'volume': 0.6}

LIBRE = "Création originale — libre de tout droit tiers"
EDITEUR = "Éditeur Sami — créé localement"

# ---------------------------------------------------------------- outils communs


def _assets(racine=None):
    return Path(racine or media.ROOT) / 'assets'


def _plat(s):
    """Minuscules sans accents (recherche et filtres insensibles aux accents)."""
    s = unicodedata.normalize('NFKD', str(s or '').lower())
    return ''.join(c for c in s if not unicodedata.combining(c))


def _slug(s):
    return re.sub(r'[^A-Za-z0-9_.-]+', '-', str(s)).strip('-')[:80] or 'x'


def _uid(prefix):
    """Meme forme que uid() des panneaux de l'interface."""
    return f'{prefix}{int(time.time() * 1000):x}{random.randint(0, 9999)}'


def _ffmpeg(racine=None):
    for p in (Path(racine or media.ROOT) / 'tools/ffmpeg/bin/ffmpeg.exe', Path(media.FFMPEG),
              Path(__file__).resolve().parents[2] / 'tools/ffmpeg/bin/ffmpeg.exe'):
        if p.is_file():
            return str(p)
    return shutil.which('ffmpeg')


def _ecrire(path, texte):
    """Ecrit seulement si le contenu change (dates des fichiers stables) ; ecriture atomique."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding='utf-8') == texte:
        return False
    tmp = path.with_name(f'{path.name}.{os.getpid()}.tmp')
    tmp.write_text(texte, encoding='utf-8')
    os.replace(tmp, path)
    return True


def _mots(*groupes):
    """Mots-cles uniques, dans l'ordre, sans vide."""
    out = []
    for g in groupes:
        for m in (g if isinstance(g, (list, tuple)) else [g]):
            m = str(m or '').strip()
            if m and m.lower() not in [x.lower() for x in out]:
                out.append(m)
    return out[:24]


# ---------------------------------------------------------------- sons : mesures, formes d'onde, gain


def _mesure(path):
    """Duree (s), crete (dBFS) et niveau (crete RMS sur 50 ms, dB) d'un son."""
    import numpy as np
    import soundfile as sf
    x, sr = sf.read(str(path), always_2d=True, dtype='float32')
    x = x.mean(axis=1)
    if not len(x):
        return {'duree': 0.0, 'crete': -99.0, 'niveau': -99.0}
    w = max(1, int(sr * 0.05))
    n = len(x) // w
    rms = float(np.sqrt((x[:n * w].reshape(n, w) ** 2).mean(axis=1)).max()) if n else float(np.sqrt((x ** 2).mean()))
    return {'duree': round(len(x) / sr, 3), 'crete': round(20 * math.log10(float(np.abs(x).max()) + 1e-9), 1),
            'niveau': round(20 * math.log10(rms + 1e-9), 1)}


def _gain(niveau):
    """Correction de volume pour qu'un son de la banque sonne comme les bruitages de l'editeur (SFX_GAIN)."""
    return round(min(3.0, max(0.15, 10 ** ((NIVEAU_CIBLE - niveau) / 20))), 2)


def _onde(ffmpeg, src, dst):
    """Forme d'onde PNG 240x64 (FFmpeg showwavespic, fond transparent)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f'{dst.stem}.{os.getpid()}.tmp.png')
    try:
        r = subprocess.run([ffmpeg, '-v', 'error', '-y', '-i', str(src), '-filter_complex',
                            'aformat=channel_layouts=mono,showwavespic=s=240x64:colors=0xFFD400:scale=sqrt',
                            '-frames:v', '1', '-update', '1', str(tmp)],
                           capture_output=True, timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if r.returncode or not tmp.is_file():
            return False
        os.replace(tmp, dst)
        return True
    finally:
        tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------- sons crees ici (briques de sfxgen.py)


def _sons_crees():
    """Sons originaux de la banque (graines fixes : toujours le meme fichier). nom -> (titre, categorie, mots, fabrique)."""
    import numpy as np
    from . import sfxgen as g
    rng = np.random.default_rng

    def mono_whoosh(d, f0, f1, seed, q=1.4, att=0.55):
        n = rng(seed).standard_normal(int(g.SR * d))
        return g._bandpass_sweep(n, f0, f1, q=q) * g._env(len(n), d * att, d * (1 - att), 1.6)

    def swoosh_rapide():
        return g.whoosh(0.22, 900, 7500, rng(31))

    def whoosh_grave():
        return g.whoosh(0.65, 110, 1500, rng(32))

    def whoosh_double():
        a = g.whoosh(0.22, 600, 5200, rng(33))
        b = g.whoosh(0.3, 5200, 700, rng(34))
        return np.concatenate([a, np.zeros((int(g.SR * 0.04), 2), dtype=np.float32), b]).astype(np.float32)

    def whoosh_aspire():
        d = 0.6
        n = rng(35).standard_normal(int(g.SR * d))
        x = g._bandpass_sweep(n, 300, 6500, q=1.2) * np.linspace(0, 1, len(n)) ** 3
        x[-int(g.SR * 0.012):] *= np.linspace(1, 0, int(g.SR * 0.012))
        return g._stereo(g._norm(x), 0.4)

    def whoosh_passage():
        return g._stereo(g._norm(mono_whoosh(0.55, 250, 4200, 36)), 0.95)

    def impact_sourd():
        t = g._t(1.6)
        sub = np.sin(2 * np.pi * (32 + 60 * np.exp(-t * 6)) * t) * np.exp(-t * 2.4)
        hit = rng(37).standard_normal(len(t)) * np.exp(-t * 60) * 0.25
        return g._stereo(g._norm(np.tanh(1.3 * (sub + hit))))

    def impact_claquant():
        t = g._t(0.5)
        crack = g._bandpass_sweep(rng(38).standard_normal(len(t)), 2400, 500, q=0.9) * np.exp(-t * 35)
        body = np.sin(2 * np.pi * 110 * t) * np.exp(-t * 12) * 0.6
        return g._stereo(g._norm(crack + body, 0.85))

    def impact_cinema():
        t = g._t(2.6)
        sub = np.sin(2 * np.pi * (36 + 90 * np.exp(-t * 8)) * t) * np.exp(-t * 2.2)
        tail = g._bandpass_sweep(rng(39).standard_normal(len(t)), 2200, 180, q=0.8) * np.exp(-t * 1.8) * 0.35
        ring = (np.sin(2 * np.pi * 220 * t) + 0.6 * np.sin(2 * np.pi * 331 * t)) * np.exp(-t * 2.5) * 0.12
        x = np.tanh(1.5 * (sub + tail + ring))
        x[-int(g.SR * 0.05):] *= np.linspace(1, 0, int(g.SR * 0.05))
        return g._stereo(g._norm(x), 0.2)

    def riser(d, f0, f1, t0, t1, seed, trem=False):
        t = g._t(d)
        noise = g._bandpass_sweep(rng(seed).standard_normal(len(t)), f0, f1, q=1.1)
        tone = np.sin(2 * np.pi * np.cumsum(np.geomspace(t0, t1, len(t))) / g.SR) * 0.35
        x = (noise + tone) * np.linspace(0, 1, len(t)) ** 2.2
        if trem:  # tremolo qui accelere : la tension monte
            x *= 0.75 + 0.25 * np.sin(2 * np.pi * np.cumsum(np.linspace(4, 16, len(t))) / g.SR)
        x[-int(g.SR * 0.015):] *= np.linspace(1, 0, int(g.SR * 0.015))
        return g._stereo(g._norm(x), 0.3)

    def riser_tension():
        t = g._t(2.0)
        f = np.geomspace(220, 440, len(t))
        tones = sum(a * np.sin(2 * np.pi * np.cumsum(f * k) / g.SR) for k, a in ((1, 0.5), (1.26, 0.35), (1.5, 0.3)))
        noise = g._bandpass_sweep(rng(40).standard_normal(len(t)), 400, 5000, q=1.3) * 0.5
        x = (tones + noise) * np.linspace(0, 1, len(t)) ** 2.5
        x[-int(g.SR * 0.015):] *= np.linspace(1, 0, int(g.SR * 0.015))
        return g._stereo(g._norm(x), 0.3)

    def swoosh_pop():
        a = g.whoosh(0.3, 500, 6000, rng(41))
        p = g.pop(1100, 0.09)
        out = np.zeros((len(a) + len(p), 2), dtype=np.float32)
        out[:len(a)] += a * 0.8
        at = int(g.SR * 0.26)
        out[at:at + len(p)] += p
        return g._stereo(g._norm(out.mean(axis=1)), 0.3)

    return {
        'swoosh-rapide': ('Swoosh rapide', 'whoosh', ['swoosh', 'rapide', 'coupe', 'passage'], swoosh_rapide),
        'whoosh-grave': ('Whoosh grave', 'whoosh', ['grave', 'lent', 'profond', 'passage'], whoosh_grave),
        'whoosh-double': ('Whoosh aller-retour', 'whoosh', ['double', 'aller-retour', 'transition'], whoosh_double),
        'whoosh-aspire': ('Whoosh aspiré (inversé)', 'whoosh', ['inversé', 'reverse', 'aspiration', 'avant une coupe'], whoosh_aspire),
        'whoosh-passage': ('Whoosh de gauche à droite', 'whoosh', ['stéréo', 'passage', 'panoramique', 'glisse'], whoosh_passage),
        'swoosh-pop': ('Swoosh + pop (apparition)', 'whoosh', ['apparition', 'révélation', 'pop', 'entrée'], swoosh_pop),
        'impact-sourd': ('Impact sourd', 'impact', ['boum', 'grave', 'basse', 'révélation'], impact_sourd),
        'impact-claquant': ('Impact claquant', 'impact', ['claque', 'frappe', 'sec', 'punch'], impact_claquant),
        'impact-cinema': ('Impact cinéma', 'impact', ['bande-annonce', 'trailer', 'boum', 'résonance'], impact_cinema),
        'riser-court': ('Riser court', 'montée', ['riser', 'montée', 'tension', 'court'], lambda: riser(0.9, 300, 6000, 220, 1200, 42)),
        'riser-long': ('Riser long', 'montée', ['riser', 'montée', 'tension', 'long', 'avant la révélation'],
                       lambda: riser(2.6, 150, 8000, 150, 1500, 43, trem=True)),
        'riser-tension': ('Montée de tension', 'montée', ['riser', 'suspense', 'tension', 'accords'], riser_tension),
    }


def _creer_sons(racine=None):
    """Cree les sons de la banque qui manquent (assets/banque/sons/*.wav) -> noms crees."""
    import soundfile as sf
    from . import sfxgen
    out = _assets(racine) / 'banque/sons'
    out.mkdir(parents=True, exist_ok=True)
    crees = []
    for nom, (_, _, _, fabrique) in _sons_crees().items():
        f = out / f'{nom}.wav'
        if f.is_file():
            continue
        tmp = out / f'{nom}.{os.getpid()}.tmp.wav'
        sf.write(tmp, fabrique(), sfxgen.SR, subtype='PCM_16')
        os.replace(tmp, f)
        crees.append(nom)
    _ecrire(out / 'LICENCE.txt', 'Sons synthetises localement pour la banque de l\'editeur (engine/editeur/banque.py, briques de '
                                 'engine/editeur/sfxgen.py). Creations originales, libres de tout droit tiers.\n')
    return crees


# ---------------------------------------------------------------- sons : description (categories, mots, intensite)

CAT_SONS = ['whoosh', 'impact', 'montée', 'pop', 'clic', 'ding', 'transition', 'glitch', 'validation', 'erreur', 'laser',
            'jingle', 'interface', 'pas', 'divers']
CAT_MOTS = {
    'whoosh': ['whoosh', 'swoosh', 'transition', 'mouvement'], 'impact': ['impact', 'choc', 'coup', 'boum', 'frappe'],
    'montée': ['riser', 'montée', 'tension', 'suspense'], 'pop': ['pop', 'apparition', 'bulle'],
    'clic': ['clic', 'bouton', 'tap', 'interface'], 'ding': ['ding', 'notification', 'message', 'alerte'],
    'transition': ['transition', 'passage', 'changement'], 'glitch': ['glitch', 'bug', 'numérique', 'électrique'],
    'validation': ['validation', 'succès', 'réussi', 'coché'], 'erreur': ['erreur', 'refus', 'raté'],
    'laser': ['laser', 'tir', 'science-fiction', 'jeu vidéo'], 'jingle': ['jingle', 'musical', 'fin', 'succès'],
    'interface': ['interface', 'application', 'menu', 'écran'], 'pas': ['pas', 'marche', 'bruitage'], 'divers': ['divers'],
}
CAT_BASE = {'impact': 3, 'montée': 2, 'whoosh': 2, 'glitch': 2, 'laser': 2, 'jingle': 2, 'transition': 2, 'erreur': 2}

SONS_EDITEUR = {
    'whoosh-court': ('Whoosh court', 'whoosh', ['rapide', 'coupe'], 2), 'whoosh-long': ('Whoosh long', 'whoosh', ['ample', 'lent'], 2),
    'whoosh-descendant': ('Whoosh descendant', 'whoosh', ['descente', 'sortie'], 2), 'pop': ('Pop', 'pop', ['apparition', 'mot'], 1),
    'pop-grave': ('Pop grave', 'pop', ['apparition', 'grave'], 1), 'click': ('Clic', 'clic', ['souris', 'bouton'], 1),
    'impact': ('Impact', 'impact', ['boum', 'révélation'], 3), 'riser': ('Riser (montée)', 'montée', ['tension', 'avant l’appel à l’action'], 2),
    'glitch': ('Glitch', 'glitch', ['numérique', 'bug'], 2), 'ding': ('Ding', 'ding', ['notification', 'cloche'], 1),
    'declencheur-photo': ('Déclencheur photo', 'clic', ['photo', 'appareil', 'capture'], 1),
}
# Sons de coupe varies (ronde « sons », 2026-10-02 : engine/editeur/sfxgen.py COUPES et KENNEY ; familles :
# styles/sons-transitions.json). Les « kenney-* » sont des copies Kenney (CC0) remises au niveau des autres.
SONS_COUPES = {
    'souffle-doux': ('Souffle doux', 'whoosh', ['doux', 'discret', 'coupe'], 1),
    'souffle-leger': ('Souffle léger', 'whoosh', ['léger', 'discret', 'rapide'], 1),
    'souffle-ample': ('Souffle ample', 'whoosh', ['ample', 'grave', 'lent'], 1),
    'whoosh-aerien-court': ('Whoosh aérien court', 'whoosh', ['aérien', 'rapide', 'coupe'], 2),
    'whoosh-aerien': ('Whoosh aérien', 'whoosh', ['aérien', 'moyen', 'passage'], 2),
    'whoosh-aerien-long': ('Whoosh aérien long', 'whoosh', ['aérien', 'long', 'cinéma'], 2),
    'whoosh-sourd': ('Whoosh sourd', 'whoosh', ['sourd', 'grave', 'feutré'], 1),
    'whoosh-tonal': ('Whoosh musical', 'whoosh', ['tonal', 'musical', 'moderne'], 2),
    'passage-gauche-droite': ('Passage de gauche à droite', 'whoosh', ['stéréo', 'passage', 'doppler', 'cinéma'], 2),
    'passage-droite-gauche': ('Passage de droite à gauche', 'whoosh', ['stéréo', 'passage', 'doppler'], 2),
    'passage-eclair': ('Passage éclair', 'whoosh', ['stéréo', 'rapide', 'éclair'], 2),
    'whoosh-chute': ('Whoosh + basse qui tombe', 'transition', ['sub drop', 'basse', 'révélation', 'cinéma'], 3),
    'whoosh-chute-court': ('Whoosh + basse courte', 'transition', ['sub drop', 'basse', 'punch'], 2),
    'aspiration': ('Son aspiré (inversé)', 'transition', ['inversé', 'reverse', 'aspiration', 'avant une coupe'], 2),
    'aspiration-longue': ('Son aspiré long', 'transition', ['inversé', 'reverse', 'montée', 'cinéma'], 2),
    'aspiration-tonale': ('Accord aspiré', 'transition', ['inversé', 'accord', 'musical', 'doux'], 2),
    'glisse-tonale-douce': ('Glissé musical doux', 'transition', ['musical', 'doux', 'sans souffle'], 1),
    'coupe-seche': ('Coupe sèche', 'transition', ['claquement', 'sec', 'punch', 'sans souffle'], 2),
    'tissu-glisse': ('Tissu qui glisse', 'transition', ['tissu', 'feutré', 'organique'], 1),
    'papier-glisse': ('Papier qui glisse', 'transition', ['papier', 'feuille', 'collage', 'organique'], 1),
    'papier-page': ('Page qu’on tourne', 'transition', ['page', 'papier', 'livre', 'collage'], 1),
    'arret-bande': ('Arrêt de bande', 'transition', ['tape stop', 'rétro', 'vhs', 'arrêt'], 2),
    'arret-bande-court': ('Arrêt de bande court', 'transition', ['tape stop', 'rétro', 'court'], 2),
    'rembobinage': ('Rembobinage', 'transition', ['rembobiner', 'rétro', 'vhs', 'cassette'], 2),
    'balayage-numerique': ('Balayage numérique', 'transition', ['numérique', 'écran', 'tech', 'montant'], 2),
    'balayage-numerique-descendant': ('Balayage numérique descendant', 'transition', ['numérique', 'écran', 'tech', 'descendant'], 2),
    'chirp-donnees': ('Bips de données', 'interface', ['données', 'bips', 'tech', 'chargement'], 1),
    'glitch-saccade': ('Glitch saccadé', 'glitch', ['saccade', 'bug', 'numérique'], 2),
    'glitch-roulement': ('Glitch en roulement', 'glitch', ['stutter', 'répétition', 'numérique'], 2),
    'glitch-bits': ('Bits écrasés', 'glitch', ['bitcrush', 'numérique', 'bruit'], 2),
    'ui-glisse': ('Glissé d’interface', 'interface', ['écran', 'glisse', 'application', 'carte'], 1),
    'ui-glisse-tonale': ('Glissé d’interface musical', 'interface', ['écran', 'glisse', 'tonal', 'application'], 1),
    'ui-tic': ('Tic d’interface', 'clic', ['tic', 'bouton', 'liste'], 1),
    'ui-tic-double': ('Double tic', 'clic', ['tic', 'double', 'liste'], 1),
    'ui-clic-doux': ('Clic doux', 'clic', ['clic', 'doux', 'bouton'], 1),
    'ui-bulle': ('Bulle d’interface', 'pop', ['bulle', 'apparition', 'application'], 1),
    'obturateur': ('Obturateur photo', 'clic', ['photo', 'appareil', 'déclencheur', 'capture'], 1),
    'pop-doux': ('Pop doux', 'pop', ['pop', 'doux', 'mot'], 1),
    'pop-bulle': ('Pop bulle', 'pop', ['bulle', 'apparition'], 1),
    'pop-bouchon': ('Pop bouchon', 'pop', ['bouchon', 'sec', 'apparition'], 1),
    'pop-goutte': ('Goutte', 'pop', ['goutte', 'eau', 'organique'], 1),
    'tap-bois': ('Tap de bois', 'pop', ['bois', 'frappe', 'organique'], 1),
    'impact-leger': ('Impact léger', 'impact', ['léger', 'preuve', 'chiffre'], 2),
    'impact-mat': ('Impact mat', 'impact', ['mat', 'sourd', 'preuve'], 2),
    'impact-coup-sec': ('Impact sec', 'impact', ['sec', 'punch', 'frappe'], 3),
    'impact-sub': ('Impact grave', 'impact', ['grave', 'basse', 'cinéma', 'révélation'], 3),
    'ding-cristal': ('Ding cristal', 'ding', ['cristal', 'notification', 'preuve'], 1),
    'riser-doux': ('Montée douce', 'montée', ['riser', 'doux', 'avant l’appel à l’action'], 2),
    'riser-numerique': ('Montée numérique', 'montée', ['riser', 'numérique', 'bips'], 2),
    'riser-souffle': ('Montée de souffle', 'montée', ['riser', 'souffle', 'tension'], 2),
    'riser-cinema': ('Montée cinéma', 'montée', ['riser', 'cinéma', 'accord', 'tension'], 3),
    'riser-bande': ('Démarrage de bande', 'montée', ['tape', 'rétro', 'démarrage'], 2),
    'kenney-selection': ('Sélection (Kenney)', 'interface', ['sélection', 'menu', 'kenney'], 1),
    'kenney-interrupteur': ('Interrupteur (Kenney)', 'clic', ['interrupteur', 'kenney'], 1),
    'kenney-bascule': ('Bascule (Kenney)', 'clic', ['bascule', 'kenney'], 1),
    'kenney-survol': ('Survol (Kenney)', 'clic', ['survol', 'kenney'], 1),
    'kenney-verre': ('Verre (Kenney)', 'ding', ['verre', 'kenney'], 1),
    'kenney-depot': ('Dépôt (Kenney)', 'pop', ['dépôt', 'kenney'], 1),
    'kenney-pep': ('Pep rétro (Kenney)', 'pop', ['rétro', '8-bit', 'kenney'], 1),
    'kenney-phaser': ('Phaser rétro (Kenney)', 'transition', ['rétro', '8-bit', 'phaser', 'kenney'], 2),
    'kenney-saut': ('Saut rétro (Kenney)', 'transition', ['rétro', '8-bit', 'saut', 'kenney'], 2),
    'kenney-descente': ('Descente rétro (Kenney)', 'transition', ['rétro', '8-bit', 'descendant', 'kenney'], 2),
    'kenney-bonus': ('Bonus rétro (Kenney)', 'montée', ['rétro', '8-bit', 'bonus', 'kenney'], 2),
    'kenney-impact-doux': ('Impact doux (Kenney)', 'impact', ['doux', 'kenney'], 1),
    'kenney-impact-bois': ('Impact bois (Kenney)', 'impact', ['bois', 'planche', 'kenney'], 2),
}
LICENCE_COUPES = 'Créé ici — ' + LIBRE

# Kenney : (pack, motif du nom de fichier, categorie) — premier motif qui correspond
KENNEY_CAT = [
    ('impact-sounds', r'^footstep', 'pas'), ('impact-sounds', r'.', 'impact'),
    ('digital-audio', r'^laser', 'laser'), ('digital-audio', r'^powerUp', 'montée'), ('digital-audio', r'^(zap|spaceTrash)', 'glitch'),
    ('digital-audio', r'^pep', 'pop'), ('digital-audio', r'(^tone|Tone)', 'ding'), ('digital-audio', r'.', 'transition'),
    ('interface-sounds', r'^(click|tick|select|switch|toggle|scroll)', 'clic'), ('interface-sounds', r'^confirmation', 'validation'),
    ('interface-sounds', r'^error', 'erreur'), ('interface-sounds', r'^(glass|bong|pluck|question)', 'ding'),
    ('interface-sounds', r'^glitch', 'glitch'), ('interface-sounds', r'^scratch', 'transition'), ('interface-sounds', r'.', 'interface'),
    ('music-jingles', r'.', 'jingle'),
    ('sci-fi-sounds', r'(explosion|impact)', 'impact'), ('sci-fi-sounds', r'^laser', 'laser'), ('sci-fi-sounds', r'^door', 'transition'),
    ('sci-fi-sounds', r'^forceField', 'montée'), ('sci-fi-sounds', r'.', 'divers'),
    ('ui-audio', r'.', 'clic'),
]
# mots des noms de fichiers Kenney -> francais (nom lisible et mots-cles)
FR = {
    'impact': 'impact', 'metal': 'métal', 'heavy': 'lourd', 'light': 'léger', 'medium': 'moyen', 'glass': 'verre', 'wood': 'bois',
    'plank': 'planche', 'plate': 'assiette', 'punch': 'coup de poing', 'soft': 'mat', 'tin': 'tôle', 'mining': 'pioche',
    'bell': 'cloche', 'generic': 'simple', 'footstep': 'pas', 'carpet': 'tapis', 'concrete': 'béton', 'grass': 'herbe',
    'snow': 'neige', 'laser': 'laser', 'phaser': 'phaser', 'power': 'bonus', 'up': 'montant', 'down': 'descendant', 'zap': 'zap',
    'pep': 'pep', 'sound': '', 'tone': 'bip', 'two': 'double', 'three': 'triple', 'high': 'aigu', 'low': 'grave',
    'random': 'aléatoire', 'space': 'spatial', 'trash': 'débris', 'phase': 'phase', 'jump': 'saut', 'back': 'retour',
    'bong': 'gong', 'click': 'clic', 'close': 'fermeture', 'confirmation': 'validation', 'drop': 'dépôt', 'error': 'erreur',
    'glitch': 'glitch', 'maximize': 'agrandir', 'minimize': 'réduire', 'open': 'ouverture', 'pluck': 'pincé',
    'question': 'question', 'scratch': 'scratch', 'scroll': 'défilement', 'select': 'sélection', 'switch': 'interrupteur',
    'tick': 'tic', 'toggle': 'bascule', 'jingles': 'jingle', 'hit': 'succès', 'nes': 'rétro 8-bit', 'pizzi': 'pizzicato',
    'sax': 'saxophone', 'steel': 'steel drum', 'door': 'porte', 'explosion': 'explosion', 'crunch': 'craquante',
    'force': 'champ de force', 'field': '', 'large': 'gros', 'retro': 'rétro', 'small': 'petit', 'frequency': 'basse fréquence',
    'slime': 'gluant', 'mouseclick': 'clic souris', 'mouserelease': 'relâché', 'rollover': 'survol', 'computer': 'ordinateur',
    'noise': 'bruit', 'engine': 'moteur',
}


def _jetons(stem):
    return re.findall(r'[A-Z]{2,}(?![a-z])|[A-Z]?[a-z]+|\d+', stem)


def _nom_kenney(stem):
    parts, num = [], None
    for j in _jetons(stem):
        if j.isdigit():
            num = int(j) + (1 if len(j) >= 3 else 0)  # « _000 » -> 1 ; « laser1 » -> 1
            continue
        fr = FR.get(j.lower(), j.lower())
        if fr and fr not in parts:
            parts.append(fr)
    nom = ' '.join(parts) or stem
    nom = nom[:1].upper() + nom[1:]
    return f'{nom} {num}' if num is not None else nom


def _intensite_son(categorie, jetons, mesure):
    j = {x.lower() for x in jetons}
    if 'heavy' in j:
        return 3
    if 'light' in j or 'soft' in j:
        return 1
    if 'medium' in j:
        return 2
    i = CAT_BASE.get(categorie, 1)
    if mesure['niveau'] > -9 and mesure['duree'] > 0.4:
        i += 1
    if mesure['niveau'] < -24:
        i -= 1
    return max(1, min(3, i))


def _pack_nom(dossier):
    """Nom du pack Kenney lu dans son License.txt (1re ligne utile)."""
    lic = dossier / 'License.txt'
    if not lic.is_file():
        return None
    for line in lic.read_text(encoding='utf-8', errors='replace').splitlines():
        if line.strip():
            return line.strip()
    return dossier.name


def _sons(racine, mesures, ecartes):
    """(entree, source absolue, apercu absolu) de tous les sons : editeur, crees ici, Kenney."""
    a = _assets(racine)
    out = []

    def ajoute(rel, src, nom, categorie, mots, intensite, licence, provenance, origine, name=None, description=''):
        m = mesures[rel]
        if m['duree'] > LONGUEUR_MAX:
            ecartes.append({'fichier': rel, 'raison': f"plus de {LONGUEUR_MAX:g} s (l'export coupe les bruitages à {LONGUEUR_MAX:g} s)"})
            return
        if m['duree'] <= 0.005 or m['crete'] < -60:
            ecartes.append({'fichier': rel, 'raison': 'silencieux ou vide'})
            return
        ap = f'banque/apercus/sons/{_slug(rel.replace("/", "-")[:-len(src.suffix)])}.png'
        params = {'gain': 1 if name else _gain(m['niveau']), 'duree': m['duree']}
        if name:
            params['name'] = name  # nom court : sfxEvents applique SFX_GAIN comme pour les bruitages du style
        out.append(({'id': f'son:{origine}:{_slug(rel.split("/", 2)[-1].rsplit(".", 1)[0].replace("/", ":"))}'[:120],
                     'type': 'son', 'nom': nom, 'categorie': categorie, 'motsCles': _mots(mots, CAT_MOTS.get(categorie, [])),
                     'intensite': intensite, 'formats': list(FORMATS), 'apercu': ap, 'fichier': rel, 'licence': licence,
                     'provenance': provenance, 'params': params, 'duree': m['duree'], 'source': origine,
                     **({'description': description} if description else {})}, src, a / ap))

    lic_editeur = (a / 'sfx/editeur/LICENCE.txt')
    voir = ' (assets/sfx/editeur/LICENCE.txt)' if lic_editeur.is_file() else ''
    for f in sorted((a / 'sfx/editeur').glob('*.wav')):
        rel = f'sfx/editeur/{f.name}'
        if f.stem in SONS_COUPES:  # sons de coupe varies : licence propre (copies Kenney : CC0 du pack d'origine)
            nom, cat, mots, inten = SONS_COUPES[f.stem]
            kenney = f.stem.startswith('kenney-')
            ajoute(rel, f, nom, cat, [*mots, 'éditeur', 'son de coupe'], inten,
                   'CC0 1.0 (domaine public)' + voir if kenney else LICENCE_COUPES + voir,
                   'Kenney.nl, copie remise au niveau des sons de coupe (engine/editeur/sfxgen.py, source et licence du pack '
                   'dans assets/sfx/editeur/LICENCE.txt)' if kenney else 'Créé localement (engine/editeur/sfxgen.py, sons de coupe)',
                   'editeur', name=f.stem)
            continue
        nom, cat, mots, inten = SONS_EDITEUR.get(f.stem, (f.stem.replace('-', ' ').capitalize(), 'divers', [], 1))
        ajoute(rel, f, nom, cat, [*mots, 'éditeur'], inten, LIBRE + voir,
               'Créé localement (engine/editeur/sfxgen.py)', 'editeur', name=f.stem)
    crees = _sons_crees()
    for f in sorted((a / 'banque/sons').glob('*.wav')):
        rel = f'banque/sons/{f.name}'
        nom, cat, mots, _ = crees.get(f.stem, (f.stem.replace('-', ' ').capitalize(), 'divers', [], None))
        inten = _intensite_son(cat, [], mesures[rel])
        ajoute(rel, f, nom, cat, [*mots, 'créé ici'], inten, LIBRE + ' (assets/banque/sons/LICENCE.txt)',
               'Créé localement pour la banque (engine/editeur/banque.py avec sfxgen.py)', 'banque')
    for pack in sorted(p for p in (a / 'sfx/kenney').glob('*') if p.is_dir()):
        titre = _pack_nom(pack)
        if not titre:
            ecartes.append({'fichier': f'sfx/kenney/{pack.name}', 'raison': 'pack sans License.txt : licence inconnue'})
            continue
        for f in sorted(pack.rglob('*.ogg')):
            if f.stem.lower() == 'preview':
                continue  # extrait de demonstration du pack
            rel = f.relative_to(a).as_posix()
            cat = next((c for pk, motif, c in KENNEY_CAT if pk == pack.name and re.search(motif, f.stem)), 'divers')
            jet = _jetons(f.stem)
            mots = [FR.get(j.lower(), '') for j in jet if not j.isdigit()] + [j.lower() for j in jet if not j.isdigit()]
            ajoute(rel, f, _nom_kenney(f.stem), cat, [*mots, 'kenney', titre.lower()],
                   _intensite_son(cat, jet, mesures[rel]), 'CC0 1.0 (domaine public)',
                   f'Kenney.nl — pack « {titre} » (assets/sfx/kenney/{pack.name}/License.txt)', 'kenney')
    return out


# ---------------------------------------------------------------- maquettes SVG (apercus des templates et des effets)

_POLICE = 'font-family="Segoe UI,Arial,sans-serif"'


def _svg(corps, fond='#15161a', personne=True, devant=''):
    silhouette = '<g fill="#2b2d35"><circle cx="160" cy="96" r="30"/><path d="M92 200c6-46 35-68 68-68s62 22 68 68z"/></g>' if personne else ''
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 200" width="320" height="200">'
            f'<rect width="320" height="200" rx="14" fill="{fond}"/>{devant}{silhouette}{corps}</svg>\n')


def _texte(x, y, t, taille=16, couleur='#fff', poids=800, ancre='middle', extra=''):
    t = str(t).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return f'<text x="{x}" y="{y}" {_POLICE} font-size="{taille}" font-weight="{poids}" fill="{couleur}" text-anchor="{ancre}" {extra}>{t}</text>'


def _maquette(forme, texte='', second=''):
    a = ACCENT
    if forme == 'chiffre':
        return _svg(_texte(160, 58, texte, 40, '#fff', 900, extra=f'stroke="{a}" stroke-width="1.5"') + _texte(160, 80, second, 12, a, 800))
    if forme == 'coches':
        rows = ''.join(f'<rect x="66" y="{62 + i * 30}" width="18" height="18" rx="4" fill="{a}"/>'
                       f'<path d="M70 {71 + i * 30}l4 4 7-8" stroke="#111" stroke-width="2.6" fill="none"/>'
                       f'<rect x="92" y="{66 + i * 30}" width="{150 - i * 22}" height="9" rx="4" fill="#fff"/>' for i in range(3))
        return _svg(f'<rect x="50" y="24" width="220" height="140" rx="14" fill="#0a0a0c" opacity=".88"/>'
                    + _texte(66, 48, texte or 'INCLUS', 14, a, 900, 'start') + rows)
    if forme == 'carte':
        x = 170 if second != 'gauche' else 30
        return _svg(f'<g transform="rotate({-4 if second != "gauche" else 4} {x + 60} 70)"><rect x="{x}" y="22" width="120" height="96" rx="12" fill="#fff"/>'
                    f'<rect x="{x}" y="22" width="120" height="34" rx="12" fill="{a}"/><rect x="{x}" y="44" width="120" height="12" fill="{a}"/>'
                    f'<rect x="{x + 10}" y="68" width="80" height="10" rx="4" fill="#111"/><rect x="{x + 10}" y="86" width="96" height="8" rx="4" fill="#999"/>'
                    f'<rect x="{x + 10}" y="100" width="60" height="8" rx="4" fill="#bbb"/></g>')
    if forme == 'motgeant':
        glow = f'<defs><filter id="g" x="-30%" y="-60%" width="160%" height="220%"><feGaussianBlur stdDeviation="6"/></filter></defs>'
        return _svg(glow + '<rect width="320" height="200" rx="14" fill="#000" opacity=".35"/>'
                    + _texte(160, 118, texte, 56 if len(texte) < 6 else 38, a, 900, extra='filter="url(#g)"')
                    + _texte(160, 118, texte, 56 if len(texte) < 6 else 38, '#fff', 900, extra=f'stroke="{a}" stroke-width="2"'))
    if forme == 'logo':
        return _svg(f'<circle cx="160" cy="92" r="44" fill="{a}"/>' + _texte(160, 99, 'LOGO', 20, '#111', 900)
                    + f'<path d="M110 150a60 60 0 0 0 100 0" stroke="#fff" stroke-width="3" fill="none" stroke-dasharray="6 6"/>', personne=False)
    if forme == 'notification':
        return _svg(f'<rect x="36" y="18" width="248" height="62" rx="14" fill="#121a2a" stroke="#ffffff30"/>'
                    f'<rect x="48" y="28" width="20" height="20" rx="6" fill="{a}"/>' + _texte(76, 43, second or 'Messages', 11, '#a9b8ce', 600, 'start')
                    + _texte(272, 43, 'maintenant', 10, a, 500, 'end') + _texte(48, 70, texte, 16, '#f6f9ff', 800, 'start'))
    if forme == 'comparison':
        return _svg(f'<rect x="36" y="110" width="120" height="70" fill="#301b22" /><rect x="36" y="110" width="120" height="5" fill="#d8a3a3"/>'
                    f'<rect x="164" y="110" width="120" height="70" fill="#0f342b"/><rect x="164" y="110" width="120" height="5" fill="{a}"/>'
                    + _texte(46, 132, 'AVANT', 10, '#e4b8b8', 700, 'start') + _texte(174, 132, 'APRÈS', 10, a, 700, 'start')
                    + _texte(46, 158, texte, 15, '#fff', 800, 'start') + _texte(174, 158, second, 15, '#fff', 800, 'start'))
    if forme == 'dashboard':
        items = (second or '').split('|')[:3]
        rows = ''.join(f'<rect x="54" y="{128 + i * 22 - 16}" width="212" height="18" rx="6" fill="#ffffff10"/>'
                       f'<circle cx="66" cy="{128 + i * 22 - 7}" r="5" fill="none" stroke="{a}" stroke-width="2"/>'
                       + _texte(78, 128 + i * 22 - 3, it, 10, '#fff', 650, 'start') for i, it in enumerate(items))
        return _svg(f'<rect x="42" y="84" width="236" height="104" rx="14" fill="#0e1625" stroke="#ffffff22"/>'
                    f'<circle cx="58" cy="100" r="5" fill="{a}"/>' + _texte(70, 104, texte, 13, '#fff', 800, 'start')
                    + _texte(266, 104, 'LIVE', 9, '#ffffff77', 600, 'end') + rows)
    if forme == 'flow':
        parts = [texte, *[p for p in (second or '').split('|') if p]][:3]
        boxes = ''.join(f'<rect x="{30 + i * 92}" y="126" width="80" height="44" rx="10" fill="{a if i == len(parts) - 1 else "#ffffff12"}" '
                        f'fill-opacity="{0.3 if i == len(parts) - 1 else 1}" stroke="{a if i == len(parts) - 1 else "#ffffff30"}"/>'
                        + _texte(70 + i * 92, 152, p, 11, '#fff', 720)
                        + (_texte(116 + i * 92, 153, '›', 18, a, 700) if i < len(parts) - 1 else '') for i, p in enumerate(parts))
        return _svg(f'<rect x="20" y="114" width="280" height="68" rx="14" fill="#060b15" opacity=".92"/>' + boxes)
    if forme == 'cta':
        return _svg(f'<defs><linearGradient id="c" x1="0" x2="1"><stop offset="0" stop-color="#8B5CF6"/><stop offset="1" stop-color="{a}"/></linearGradient></defs>'
                    f'<rect x="58" y="122" width="204" height="46" rx="23" fill="url(#c)"/>' + _texte(160, 151, f'{texte} →', 16, '#04101a', 900))
    if forme == 'paper':
        return _svg(f'<g transform="rotate(-4 160 140)"><rect x="80" y="112" width="160" height="56" fill="#fff9ec"/><rect x="80" y="162" width="160" height="6" fill="{a}"/>'
                    f'<rect x="130" y="104" width="52" height="14" fill="#d8bc80" opacity=".8" transform="rotate(5 156 111)"/>'
                    + _texte(160, 150, f'{texte} ↗', 22, '#151515', 900) + '</g>')
    if forme == 'keyword':
        return _svg('', devant=_texte(160, 120, texte, 64 if len(texte) < 7 else 44, a, 900))
    if forme == 'metric':
        return _svg(f'<rect x="80" y="18" width="160" height="80" rx="16" fill="#101827" stroke="{a}88"/>'
                    + _texte(160, 62, texte, 30, a, 850) + _texte(160, 84, second, 11, '#fff', 600)
                    + f'<rect x="100" y="90" width="120" height="3" rx="1.5" fill="{a}"/>')
    # effets
    if forme == 'flash-blanc':
        return _svg('<defs><radialGradient id="f"><stop offset="0" stop-color="#fff" stop-opacity=".95"/><stop offset="1" stop-color="#fff" stop-opacity=".35"/></radialGradient></defs>'
                    '<rect width="320" height="200" rx="14" fill="url(#f)"/>')
    if forme == 'flash-glitch':
        bars = ''.join(f'<rect x="{dx}" y="{y}" width="340" height="{h}" fill="{c}" opacity=".45"/>' for dx, y, h, c in
                       ((-12, 30, 14, '#00ffff'), (8, 64, 26, '#ff005a'), (-6, 110, 10, '#ffffff'), (14, 140, 20, '#00ffff'), (-10, 172, 12, '#ff005a')))
        return _svg(bars)
    if forme == 'flash-lumiere':
        return _svg('<defs><radialGradient id="l" cx=".7" cy=".35" r=".6"><stop offset="0" stop-color="#ffaa5a" stop-opacity=".95"/>'
                    '<stop offset=".45" stop-color="#ff5078" stop-opacity=".5"/><stop offset="1" stop-color="#ff5078" stop-opacity="0"/></radialGradient></defs>'
                    '<rect width="320" height="200" rx="14" fill="url(#l)"/>')
    if forme == 'vignette':
        o = 0.9 if texte == 'forte' else 0.55
        return _svg(f'<defs><radialGradient id="v" r=".75"><stop offset=".55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="{o}"/></radialGradient></defs>'
                    '<rect width="320" height="200" rx="14" fill="url(#v)"/>', fond='#5a6270')
    if forme == 'grade':
        ciel, sol, peau = {'chaud': ('#f3b27a', '#8a5a2b', '#e8a07a'), 'froid': ('#8fb6e8', '#3d5a73', '#c9b3ad'),
                           'contraste': ('#39a0ff', '#1d6b2a', '#f08a5d'), 'cinema': ('#6fa3a0', '#3b4b43', '#d49a6a'),
                           'noirblanc': ('#bdbdbd', '#4a4a4a', '#9a9a9a')}.get(texte, ('#9ac', '#565', '#dba'))
        return _svg(f'<rect width="320" height="120" rx="14" fill="{ciel}"/><circle cx="250" cy="48" r="20" fill="#fff6" />'
                    f'<rect y="120" width="320" height="80" fill="{sol}"/><g fill="{peau}"><circle cx="160" cy="96" r="30"/>'
                    '<path d="M92 200c6-46 35-68 68-68s62 22 68 68z"/></g>', personne=False)
    return _svg(_texte(160, 110, texte or forme, 20))


# ---------------------------------------------------------------- templates (graphismes et scenes existants)

NOMS_GRAPHISMES = {'chiffre': 'Chiffre qui défile', 'coches': 'Cases cochées', 'carte': 'Carte animée', 'motgeant': 'Mot géant lumineux',
                   'logo': 'Logo animé'}
NOMS_SCENES = {'metric': 'Chiffre encadré', 'notification': 'Notification de téléphone', 'comparison': 'Avant / Après',
               'keyword': 'Mot clé géant', 'paper': 'Étiquette papier', 'dashboard': 'Tableau de suivi', 'flow': 'Parcours en étapes',
               'cta': 'Bouton d’appel à l’action'}
CAT_TEMPLATES = ['titres', 'chiffres', 'listes', 'cartes', 'notifications', 'comparaisons', 'tableaux', 'parcours', 'cta', 'logos']


def _g(kind, props, duree):
    return {'kind': kind, 'props': props, 'duree': duree}


def _s(kind, text, secondary='', duree=2.4, y=0.5, scale=1.0):
    return {'kind': kind, 'text': text, 'secondary': secondary, 'duree': duree, 'x': 0.5, 'y': y, 'scale': scale, 'rotation': 0}


# (slug, nom, categorie, mots-cles, intensite, cible principale, graphisme, scene, maquette (forme, texte, second), options)
TEMPLATES = [
    ('mot-geant', 'Mot géant lumineux', 'titres', ['mot', 'géant', 'choc', 'titre', 'révélation', 'flash'], 3, 'graphics',
     _g('motgeant', {'text': 'WOW'}, 0.9), _s('paper', 'WOW', '', 1.6, 0.69), ('motgeant', 'WOW', ''), {'texteDit': True}),
    ('mot-choc-gratuit', 'Mot choc « GRATUIT »', 'titres', ['gratuit', 'offre', 'choc', 'titre', 'promo'], 3, 'graphics',
     _g('motgeant', {'text': 'GRATUIT'}, 1.2), _s('paper', 'Gratuit', '', 2.0, 0.69), ('motgeant', 'GRATUIT', ''), {}),
    ('etiquette-papier', 'Étiquette papier collée', 'titres', ['étiquette', 'papier', 'collage', 'autocollant', 'titre'], 2, 'styleScenes',
     _g('motgeant', {'text': 'SIMPLE'}, 1.2), _s('paper', 'Simple', '', 2.4, 0.69), ('paper', 'Simple', ''), {'texteDit': True}),
    ('mot-cle-geant', 'Mot clé géant derrière la personne', 'titres', ['mot clé', 'géant', 'derrière', 'éditorial', 'titre'], 3, 'styleScenes',
     _g('motgeant', {'text': 'LIBERTÉ'}, 1.2), _s('keyword', 'Liberté', '', 2.4, 0.69), ('keyword', 'LIBERTÉ', ''), {'texteDit': True}),
    ('chiffre-pourcentage', 'Chiffre qui défile — pourcentage', 'chiffres', ['chiffre', 'pourcentage', 'statistique', 'preuve', 'compteur'], 2, 'graphics',
     _g('chiffre', {'value': 100, 'prefix': '', 'suffix': ' %', 'label': 'TON TEXTE ICI'}, 2.2), _s('metric', '100 %', 'ton texte ici', 2.4, 0.24),
     ('chiffre', '100 %', 'TON TEXTE ICI'), {'aModifier': True}),
    ('chiffre-prix', 'Chiffre qui défile — prix', 'chiffres', ['chiffre', 'prix', 'argent', 'dollars', 'économie', 'compteur'], 2, 'graphics',
     _g('chiffre', {'value': 2400, 'prefix': '', 'suffix': ' $', 'label': 'TON TEXTE ICI'}, 2.2), _s('metric', '2 400 $', 'ton texte ici', 2.4, 0.24),
     ('chiffre', '2 400 $', 'TON TEXTE ICI'), {'aModifier': True}),
    ('chiffre-multiplicateur', 'Multiplicateur « ×5 »', 'chiffres', ['multiplicateur', 'fois', 'chiffre', 'comparaison', 'preuve'], 3, 'graphics',
     _g('chiffre', {'value': 5, 'prefix': '×', 'suffix': '', 'label': 'TON TEXTE ICI'}, 2.0), _s('metric', '×5', 'ton texte ici', 2.4, 0.24),
     ('chiffre', '×5', 'TON TEXTE ICI'), {'aModifier': True}),
    ('chiffre-encadre', 'Chiffre encadré', 'chiffres', ['chiffre', 'encadré', 'statistique', 'preuve', 'carte'], 2, 'styleScenes',
     _g('chiffre', {'value': 40, 'prefix': '+', 'suffix': ' %', 'label': 'TON TEXTE ICI'}, 2.2), _s('metric', '+40 %', 'ton texte ici', 2.4, 0.24),
     ('metric', '+40 %', 'ton texte ici'), {'aModifier': True}),
    ('liste-benefices', 'Liste cochée — 3 bénéfices', 'listes', ['liste', 'cases', 'cochées', 'bénéfices', 'avantages', 'inclus'], 1, 'graphics',
     _g('coches', {'title': 'Inclus', 'items': ['Premier bénéfice', 'Deuxième bénéfice', 'Troisième bénéfice']}, 3.5),
     _s('dashboard', 'Inclus', 'Premier bénéfice|Deuxième bénéfice|Troisième bénéfice', 3.0, 0.7, 0.92), ('coches', 'INCLUS', ''), {'aModifier': True}),
    ('liste-etapes', 'Liste — 3 étapes', 'listes', ['liste', 'étapes', 'marche à suivre', 'processus'], 1, 'graphics',
     _g('coches', {'title': 'En 3 étapes', 'items': ['Tu appelles', 'On s’occupe de tout', 'Tu profites']}, 3.5),
     _s('flow', 'Tu appelles', 'On s’occupe de tout|Tu profites', 3.0, 0.7), ('coches', 'EN 3 ÉTAPES', ''), {'aModifier': True}),
    ('carte-droite', 'Carte qui glisse — à droite', 'cartes', ['carte', 'glisse', 'entrée', 'photo', 'produit'], 1, 'graphics',
     _g('carte', {'title': 'Titre de la carte', 'subtitle': 'Sous-titre', 'image': '', 'side': 'droite'}, 2.5),
     _s('notification', 'Titre de la carte', 'Sous-titre', 2.5, 0.2), ('carte', '', 'droite'), {'aModifier': True}),
    ('carte-gauche', 'Carte qui glisse — à gauche', 'cartes', ['carte', 'glisse', 'entrée', 'photo', 'produit'], 1, 'graphics',
     _g('carte', {'title': 'Titre de la carte', 'subtitle': 'Sous-titre', 'image': '', 'side': 'gauche'}, 2.5),
     _s('notification', 'Titre de la carte', 'Sous-titre', 2.5, 0.2), ('carte', '', 'gauche'), {'aModifier': True}),
    ('notification', 'Notification de téléphone', 'notifications', ['notification', 'téléphone', 'message', 'texto', 'alerte', 'app'], 1, 'styleScenes',
     _g('carte', {'title': 'Nouveau message', 'subtitle': 'Messages · maintenant', 'image': '', 'side': 'droite'}, 2.4),
     _s('notification', 'Nouveau message', 'Messages', 2.4, 0.2), ('notification', 'Nouveau message', 'Messages'), {'aModifier': True}),
    ('avant-apres', 'Avant / Après', 'comparaisons', ['avant', 'après', 'comparaison', 'versus', 'résultat'], 2, 'styleScenes',
     _g('carte', {'title': 'Après : ton texte', 'subtitle': 'Avant : ton texte', 'image': '', 'side': 'droite'}, 3.0),
     _s('comparison', 'Avant', 'Après', 3.0, 0.69), ('comparison', 'Avant', 'Après'), {'aModifier': True}),
    ('tableau-suivi', 'Tableau de suivi', 'tableaux', ['tableau', 'suivi', 'interface', 'application', 'tech'], 2, 'styleScenes',
     _g('coches', {'title': 'Suivi', 'items': ['Étape 1', 'Étape 2', 'Étape 3']}, 3.0),
     _s('dashboard', 'Suivi', 'Étape 1|Étape 2|Étape 3', 3.0, 0.7, 0.92), ('dashboard', 'Suivi', 'Étape 1|Étape 2|Étape 3'), {'aModifier': True}),
    ('parcours', 'Parcours en étapes', 'parcours', ['parcours', 'étapes', 'flèches', 'processus', 'tech'], 2, 'styleScenes',
     _g('coches', {'title': 'Étapes', 'items': ['Répondre', 'Qualifier', 'Transférer']}, 3.0),
     _s('flow', 'Répondre', 'Qualifier|Transférer', 3.0, 0.7), ('flow', 'Répondre', 'Qualifier|Transférer'), {'aModifier': True}),
    ('bouton-cta', 'Bouton d’appel à l’action', 'cta', ['bouton', 'appel à l’action', 'cta', 'en savoir plus', 'fin', 'lien'], 2, 'styleScenes',
     _g('motgeant', {'text': 'EN SAVOIR PLUS'}, 1.5), _s('cta', 'En savoir plus', '', 3.0, 0.72), ('cta', 'En savoir plus', ''), {}),
    ('logo-anime', 'Logo animé du client', 'logos', ['logo', 'marque', 'charte', 'client'], 1, 'graphics',
     _g('logo', {}, 2.0), None, ('logo', '', ''), {'besoin': 'logo'}),
]


def _templates(racine):
    a = _assets(racine)
    out = []
    for slug, nom, cat, mots, inten, cible, graph, scene, (forme, t1, t2), opts in TEMPLATES:
        ap = f'banque/apercus/modeles/{slug}.svg'
        _ecrire(a / ap, _maquette(forme, t1, t2))
        params = {'cible': cible, **(graph or {}), **({'scene': scene} if scene else {}), **opts}
        code = 'remotion/src/graphics.tsx' if cible == 'graphics' else 'remotion/src/design.tsx'
        origine = NOMS_GRAPHISMES.get(graph['kind']) if cible == 'graphics' else NOMS_SCENES.get(scene['kind'])
        desc = {'graphics': 'Graphisme animé', 'styleScenes': 'Scène d’habillage'}[cible]
        out.append({'id': f'template:{slug}', 'type': 'template', 'nom': nom, 'categorie': cat,
                    'motsCles': _mots(mots, 'modèle', 'template'), 'intensite': inten, 'formats': list(FORMATS), 'apercu': ap,
                    'fichier': None, 'licence': 'Modèle de l’éditeur — libre d’usage (aperçu dessiné localement)',
                    'provenance': f'{EDITEUR} : « {origine} » ({code}) avec des réglages par défaut', 'params': params,
                    'description': desc, 'source': 'editeur'})
    return out


# ---------------------------------------------------------------- effets (transitions, texture, vignette, etalonnage)

CAT_EFFETS = ['transitions', 'texture', 'vignette', 'étalonnage']
EFFETS = [
    ('flash-blanc', 'Flash blanc', 'transitions', ['flash', 'blanc', 'coupe', 'transition'], 2, {'cible': 'flash', 'kind': 'blanc'}, ('flash-blanc', '')),
    ('flash-glitch', 'Glitch', 'transitions', ['glitch', 'numérique', 'transition', 'bug'], 3, {'cible': 'flash', 'kind': 'glitch'}, ('flash-glitch', '')),
    ('flash-lumiere', 'Fuite de lumière', 'transitions', ['lumière', 'chaud', 'transition', 'doux', 'film'], 2, {'cible': 'flash', 'kind': 'lumiere'}, ('flash-lumiere', '')),
    ('grain-leger', 'Grain de film léger', 'texture', ['grain', 'film', 'pellicule', 'texture'], 1, {'cible': 'effects', 'effects': {'grain': 0.35}}, None),
    ('grain-fort', 'Grain de film marqué', 'texture', ['grain', 'film', 'vintage', 'rétro', 'texture'], 2, {'cible': 'effects', 'effects': {'grain': 0.8}}, None),
    ('vignette-douce', 'Vignette douce', 'vignette', ['vignette', 'bords sombres', 'cinéma', 'focus'], 1, {'cible': 'effects', 'effects': {'vignette': 0.35}}, ('vignette', 'douce')),
    ('vignette-forte', 'Vignette marquée', 'vignette', ['vignette', 'bords sombres', 'dramatique'], 2, {'cible': 'effects', 'effects': {'vignette': 0.75}}, ('vignette', 'forte')),
    ('etalonnage-chaud', 'Étalonnage chaud', 'étalonnage', ['couleur', 'chaud', 'soleil', 'étalonnage'], 1, {'cible': 'effects', 'effects': {'grade': 'chaud'}}, ('grade', 'chaud')),
    ('etalonnage-froid', 'Étalonnage froid', 'étalonnage', ['couleur', 'froid', 'bleu', 'tech', 'étalonnage'], 1, {'cible': 'effects', 'effects': {'grade': 'froid'}}, ('grade', 'froid')),
    ('etalonnage-contraste', 'Contraste punchy', 'étalonnage', ['couleur', 'contraste', 'saturé', 'punch', 'étalonnage'], 2, {'cible': 'effects', 'effects': {'grade': 'contraste'}}, ('grade', 'contraste')),
    ('etalonnage-cinema', 'Look cinéma', 'étalonnage', ['couleur', 'cinéma', 'film', 'étalonnage'], 2, {'cible': 'effects', 'effects': {'grade': 'cinema'}}, ('grade', 'cinema')),
    ('etalonnage-noirblanc', 'Noir et blanc', 'étalonnage', ['couleur', 'noir et blanc', 'monochrome', 'étalonnage'], 2, {'cible': 'effects', 'effects': {'grade': 'noirblanc'}}, ('grade', 'noirblanc')),
]


def _effets(racine):
    a = _assets(racine)
    out = []
    grain = a / 'overlays/grain.png'
    for slug, nom, cat, mots, inten, params, maquette in EFFETS:
        if maquette is None:  # grain : la texture elle-meme sert d'apercu
            if not grain.is_file():
                continue
            ap, prov = 'overlays/grain.png', f'{EDITEUR} : texture assets/overlays/grain.png (Reel.tsx, grain de film)'
        else:
            ap = f'banque/apercus/effets/{slug}.svg'
            _ecrire(a / ap, _maquette(*maquette))
            quoi = {'flash': 'transition aux changements de partie', 'effects': 'réglage d’image'}[params['cible']]
            prov = f'{EDITEUR} : {quoi} (remotion/src/Reel.tsx)'
        desc = ('S’applique à chaque changement de partie de la vidéo' if params['cible'] == 'flash'
                else 'S’applique à toute la vidéo')
        out.append({'id': f'effet:{slug}', 'type': 'effet', 'nom': nom, 'categorie': cat, 'motsCles': _mots(mots, 'effet'),
                    'intensite': inten, 'formats': list(FORMATS), 'apercu': ap, 'fichier': None,
                    'licence': 'Effet de l’éditeur — libre d’usage', 'provenance': prov, 'params': params, 'description': desc,
                    'source': 'editeur'})
    return out


# ---------------------------------------------------------------- vecteurs (agent « vecteurs » : SVG + fiche)

_HEX = re.compile(r'^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$')
_SVG_INTERDIT = re.compile(r'<\s*script|<\s*foreignObject|\son[a-z]+\s*=|javascript:|(?:xlink:)?href\s*=\s*["\'](?!#)', re.I)


def _vecteurs(racine, ecartes):
    a = _assets(racine)
    d = a / 'banque/vecteurs'
    out = []
    if not d.is_dir():
        return out  # agent « vecteurs » pas encore passe : rien a lister (re-indexe des que le dossier change)
    for f in sorted(d.rglob('*.svg')):
        rel = f.relative_to(a).as_posix()
        try:
            texte = f.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            ecartes.append({'fichier': rel, 'raison': 'SVG illisible'})
            continue
        if len(texte) > 512 * 1024 or '<svg' not in texte or 'viewBox' not in texte:
            ecartes.append({'fichier': rel, 'raison': 'SVG invalide (balise svg ou viewBox absente, ou plus de 512 Ko)'})
            continue
        if _SVG_INTERDIT.search(texte):
            ecartes.append({'fichier': rel, 'raison': 'SVG refusé : script, lien externe ou objet étranger'})
            continue
        fiche = {}
        fj = f.with_suffix('.json')
        if fj.is_file():
            try:
                fiche = json.loads(fj.read_text(encoding='utf-8'))
            except ValueError:
                ecartes.append({'fichier': fj.relative_to(a).as_posix(), 'raison': 'fiche JSON illisible (valeurs par défaut)'})
                fiche = {}
        stem = f.relative_to(d).with_suffix('').as_posix()
        effet = fiche.get('type') == 'effet'
        anim = fiche.get('anim') if isinstance(fiche.get('anim'), dict) else {}
        couleurs = fiche.get('couleurs') if isinstance(fiche.get('couleurs'), dict) else {}
        vb = re.search(r'viewBox\s*=\s*["\']\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', texte)
        ratio = round(float(vb.group(2)) / float(vb.group(1)), 4) if vb and float(vb.group(1)) > 0 else 1.0
        params = {'duree': float(fiche.get('duree') or 2), 'largeur': float(fiche.get('largeur') or 0.35), 'ratio': ratio,
                  # #RRGGBB[AA] seulement (meme regle que le serveur) : une couleur « #fff » ferait refuser TOUTE la sauvegarde
                  'couleurs': {k: (couleurs.get(k) if isinstance(couleurs.get(k), str) and _HEX.match(couleurs.get(k)) else None)
                               for k in ('principale', 'secondaire', 'contour')},
                  'anim': {'entree': str(anim.get('entree') or 'pop')[:40], 'sortie': str(anim.get('sortie') or 'fondu')[:40]},
                  'recolorable': 'var(--v-' in texte,
                  # couleurs porteuses de sens (coche verte, croix rouge) : la charte ne les recolore pas
                  'garderCouleurs': bool(fiche.get('garderCouleurs'))}
        for k in ('x', 'y'):
            if isinstance(fiche.get(k), (int, float)):
                params[k] = float(fiche[k])
        if effet:
            params['cible'] = 'vector'
        try:
            inten = max(1, min(3, int(fiche.get('intensite') or 1)))
        except (TypeError, ValueError):
            inten = 1
        formats = [x for x in (fiche.get('formats') or FORMATS) if x in FORMATS] or list(FORMATS)
        nom = str(fiche.get('nom') or Path(stem).name.replace('-', ' ').replace('_', ' ').capitalize())[:80]
        out.append({'id': f'vecteur:{_slug(stem.replace("/", ":"))}'[:120], 'type': 'effet' if effet else 'vecteur', 'nom': nom,
                    'categorie': str(fiche.get('categorie') or 'formes')[:40],
                    'motsCles': _mots(fiche.get('motsCles') or [], _jetons(Path(stem).name), 'vecteur', 'forme'),
                    'intensite': inten, 'formats': formats, 'apercu': rel, 'fichier': rel,
                    'licence': str(fiche.get('licence') or 'À vérifier (fiche absente)')[:200],
                    'provenance': str(fiche.get('provenance') or f'Fichier déposé dans assets/banque/vecteurs (sans fiche)')[:300],
                    'params': params, 'source': 'vecteurs',
                    'description': str(fiche.get('description') or ('Vecteur recolorable' if params['recolorable'] else 'Vecteur'))[:200]})
    return out


# ---------------------------------------------------------------- icones (ronde 4 : Lucide + icones importees)
# Catalogue A PART (assets/banque/catalogue-icones.json, meme schema, type « icone ») : ~1 900 entrees qui ne doivent ni
# alourdir ni changer le catalogue des 4 types historiques (SPEC §9.1 ; l'interface lit les deux fichiers).
#  - bibliotheques : assets/banque/icones/<bibliotheque>/*.svg + LICENSE (+ tags.json : mots-cles anglais) ; noms,
#    categories et mots-cles francais : assets/banque/icones/dictionnaire-lucide-fr.json (icones choisies + regles de repli) ;
#  - import : assets/banque/import/** (SVG / PNG deposes par le monteur, packs achetes), licence « À vérifier (importé) ».
#    Un nom de fichier avec espaces ou accents est copie sous un nom simple dans assets/banque/apercus/import/ (le chemin
#    d'un vecteur du reel n'accepte que [A-Za-z0-9/_.-]) ; l'original n'est jamais modifie.
# « Ajouter » pose un VECTEUR (reel.vectors) avec meta.icone = {style: trait|plein|verre, nom, banque} : rendu par
# remotion/src/vectors.tsx (tuile de verre, pastille pleine ou trait), couleurs de la charte tant qu'elles sont null.
TYPE_ICONE = 'icone'
TYPES_FILTRE = TYPES + (TYPE_ICONE,)
CATALOGUE_ICONES = 'banque/catalogue-icones.json'    # relatif a assets/
CODE_ICONES = 2        # version des regles des icones : la changer reconstruit leur catalogue
STYLES_ICONE = ('trait', 'plein', 'verre')
ICONE_STYLE = 'verre'  # style propose par defaut (exemples de l'utilisateur : icones finance en verre)
ICONE_LARGEUR = 0.22   # part du petit cote de l'image (comme les vecteurs)
ICONE_DUREE = 2.5
ICONES = 'banque/icones'
IMPORT = 'banque/import'
IMPORT_COPIES = 'banque/apercus/import'
LICENCE_IMPORT = 'À vérifier (importé)'
DICO_ICONES = 'banque/icones/dictionnaire-lucide-fr.json'
_SEGMENT_SUR = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]*$')
_LICENCE_FICHIER = re.compile(r'^(licen[cs]e|copying|lisezmoi|readme)[\w .-]*$', re.I)


def _dico_icones(a):
    """Dictionnaire francais des icones (vide si absent : noms et categories de repli seulement)."""
    try:
        d = json.loads((a / DICO_ICONES).read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _categorie_icone(nom, mots_en, dico):
    """Categorie francaise d'une icone : regles sur les mots de son nom, puis sur ses mots-cles anglais, sinon « divers »."""
    jetons = set(nom.lower().split('-')) | {nom.lower()}
    for cat, declencheurs in dico.get('regles') or []:
        if jetons & set(declencheurs):
            return cat
    tags = set()
    for t in mots_en:
        t = str(t).lower()
        tags.add(t)
        tags.update(re.split(r'[^a-z0-9]+', t))
    for cat, declencheurs in dico.get('reglesTags') or []:
        if tags & set(declencheurs):
            return cat
    return 'divers'


def _nom_icone(nom, dico):
    """Nom francais de repli, mot a mot (« arrow-up-right » -> « Flèche haut droite »)."""
    mots = dico.get('mots') or {}
    parts = []
    for j in nom.split('-'):
        fr = mots.get(j.lower(), j)
        if fr and (not parts or parts[-1] != fr):
            parts.append(fr)
    s = ' '.join(parts) or nom
    return s[:1].upper() + s[1:]


def _svg_icone_ok(texte):
    """None si le SVG est utilisable comme icone, sinon la raison du refus (memes refus que les vecteurs)."""
    if len(texte) > 512 * 1024 or '<svg' not in texte:
        return 'SVG invalide (balise svg absente, ou plus de 512 Ko)'
    if 'viewBox' not in texte and not re.search(r'<svg[^>]*\swidth\s*=\s*["\']?\d[^>]*\sheight\s*=\s*["\']?\d', texte, re.S):
        return 'SVG invalide (ni viewBox, ni largeur et hauteur)'
    if _SVG_INTERDIT.search(texte):
        return 'SVG refusé : script, lien externe ou objet étranger'
    return None


def _trait_svg(texte):
    """Icone au trait (racine stroke=..., fill=none : Lucide, Tabler...) : elle peut se « tracer » (animation)."""
    m = re.search(r'<svg\b([^>]*)>', texte, re.S)
    racine = m.group(1) if m else ''
    stroke = re.search(r'\sstroke\s*=\s*["\']([^"\']+)', racine)
    fill = re.search(r'\sfill\s*=\s*["\']([^"\']+)', racine)
    return bool(stroke and stroke.group(1).strip() != 'none' and fill and fill.group(1).strip() == 'none')


def _params_icone(trait=True, png=False, ratio=1.0, recolorable=True, en=''):
    return {'duree': ICONE_DUREE, 'largeur': ICONE_LARGEUR, 'ratio': 1, 'ratioDessin': round(ratio, 4), 'style': ICONE_STYLE,
            'trait': bool(trait and not png), 'png': bool(png), 'recolorable': bool(recolorable and not png),
            'anim': {'entree': 'pop', 'sortie': 'fondu'}, 'en': en[:80]}


def _bibliotheque(a, d, dico, ecartes):
    """Icones d'une bibliotheque (assets/banque/icones/<nom>/) -> [(cle de tri, entree)]."""
    lib = d.name
    lic_f = next((f for f in sorted(d.iterdir()) if f.is_file() and _LICENCE_FICHIER.match(f.name) and 'licen' in f.name.lower()), None)
    if not lic_f:
        ecartes.append({'fichier': d.relative_to(a).as_posix(), 'raison': 'bibliothèque d’icônes sans fichier LICENSE : licence inconnue'})
        return []
    lic_txt = lic_f.read_text(encoding='utf-8', errors='replace')
    premiere = next((x.strip() for x in lic_txt.splitlines() if x.strip()), 'Licence du fichier')
    feather = set()
    m = re.search(r'derived from the Feather project:\s*(.+?)\n\s*\n', lic_txt, re.S)
    if m:
        feather = {x.strip() for x in m.group(1).replace('\n', ' ').split(',') if x.strip()}
    try:
        tags = json.loads((d / 'tags.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        tags = {}
    source = ''
    try:
        source = (d / 'SOURCE.txt').read_text(encoding='utf-8')
    except OSError:
        pass
    version = (re.search(r'Version\s*:\s*([\w.-]+)', source) or [None, ''])[1]
    titre = lib.capitalize()
    lic_rel = lic_f.relative_to(a).as_posix()
    choisies = (dico.get('icones') or {}) if lib == 'lucide' else {}
    rang_choisie = {k: i for i, k in enumerate(choisies)}  # ordre du dictionnaire = de la plus parlante a la moins parlante
    mots_cat = dico.get('motsCategorie') or {}
    out = []
    for f in sorted(d.glob('*.svg')):
        rel = f.relative_to(a).as_posix()
        if not _SEGMENT_SUR.match(f.name):
            ecartes.append({'fichier': rel, 'raison': 'nom de fichier non pris en charge (lettres, chiffres, - _ . seulement)'})
            continue
        try:
            texte = f.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            ecartes.append({'fichier': rel, 'raison': 'SVG illisible'})
            continue
        refus = _svg_icone_ok(texte)
        if refus:
            ecartes.append({'fichier': rel, 'raison': refus})
            continue
        stem = f.stem
        en = [str(x) for x in (tags.get(stem) or []) if isinstance(x, (str, int, float))]
        cure = choisies.get(stem)
        if isinstance(cure, list) and len(cure) >= 2:
            nom, cat = str(cure[0]), str(cure[1])
            mots_fr = [x.strip() for x in str(cure[2] if len(cure) > 2 else '').split(',') if x.strip()]
        else:
            cure = None
            nom = _nom_icone(stem, dico)
            cat = _categorie_icone(stem, en, dico)
            fr_tags = [(dico.get('mots') or {}).get(x.lower()) for x in en if ' ' not in x]
            mots_fr = [nom.lower(), *[x for x in fr_tags if x]]
        licence = f'ISC ({titre}) — libre, y compris commercial' if 'ISC' in premiere else premiere[:120]
        if stem in feather:
            licence += ' ; dessin dérivé de Feather (MIT, Cole Bemis)'
        e = {'id': f'icone:{_slug(lib)}:{_slug(stem)}'[:120], 'type': TYPE_ICONE, 'nom': nom[:80], 'categorie': cat[:40],
             'motsCles': _mots(mots_fr, mots_cat.get(cat, []), 'icône', stem, en),
             'intensite': 1, 'formats': list(FORMATS), 'apercu': rel, 'fichier': rel,
             'licence': f'{licence} (assets/{lic_rel})'[:200],
             'provenance': (f'{titre}{" v" + version if version else ""} — {lib}.dev, paquet npm « lucide-static » ; '
                            f'assets/{d.relative_to(a).as_posix()}/SOURCE.txt' if lib == 'lucide'
                            else f'Bibliothèque {titre} (assets/{d.relative_to(a).as_posix()})')[:300],
             'params': _params_icone(trait=_trait_svg(texte), en=stem), 'source': _slug(lib),
             'description': f'Icône {titre} « {stem} » — trait, plein ou verre, aux couleurs de ta charte'}
        out.append(((0, rang_choisie[stem]) if cure else (1, 0), e))
    return out


_NEUTRES = {'black', 'white', 'gray', 'grey', 'silver', 'dimgray', 'dimgrey', 'darkgray', 'darkgrey', 'lightgray', 'lightgrey', 'gainsboro'}


def _neutre(c):
    """Couleur « sans couleur » (noir, gris, blanc : saturation < 0,15), comme neutralPaint de vectors.tsx."""
    import colorsys
    s = str(c or '').strip().lower()
    if s in _NEUTRES:
        return True
    m = re.match(r'^#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$', s)
    if m:
        h = m.group(1)
        h = ''.join(x * 2 for x in h[:3]) if len(h) <= 4 else h[:6]
        rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    else:
        m = re.match(r'^rgba?\(\s*([\d.]+)%?[\s,]+([\d.]+)%?[\s,]+([\d.]+)%?', s)
        if not m:
            return False
        rgb = [min(255.0, float(x)) / 255 for x in m.groups()]
    return colorsys.rgb_to_hls(*rgb)[2] < 0.15


def _png_taille(b):
    """(largeur, hauteur) d'un PNG, ou None."""
    if b[:8] != b'\x89PNG\r\n\x1a\n' or len(b) < 24:
        return None
    import struct
    return struct.unpack('>II', b[16:24])


def _imports(a, ecartes, dico=None):
    """Icones deposees dans assets/banque/import/ (SVG, PNG) -> [(cle de tri, entree)]. Licence « À vérifier (importé) ».
    Packs de plusieurs milliers d'icones : licence cherchee une fois par dossier ; chemin trop long pour un vecteur du reel
    (serveur : 160 caracteres au plus) ou nom non pris en charge -> copie au nom simple ; identifiant trop long ou deja pris
    (meme nom en SVG et en PNG) -> rendu unique par une empreinte du chemin."""
    import hashlib
    d = a / IMPORT
    if not d.is_dir():
        return []
    mots_fr = (dico or {}).get('mots') or {}
    licences = {}  # dossier relatif -> fichier de licence du pack (ou None)

    def licence_de(dossiers):
        cle = '/'.join(dossiers)
        if cle not in licences:
            dd = d.joinpath(*dossiers) if dossiers else d
            try:
                # a la racine d'import, LISEZMOI.txt est le mode d'emploi de l'editeur, pas la licence d'un pack
                lic = next((g for g in sorted(dd.iterdir()) if _LICENCE_FICHIER.match(g.name) and g.is_file()
                            and not (not dossiers and g.name.lower() == 'lisezmoi.txt')), None)
            except OSError:
                lic = None
            licences[cle] = lic if lic is not None else (licence_de(dossiers[:-1]) if dossiers else None)
        return licences[cle]

    out = []
    ids = set()
    for f in sorted(d.rglob('*')):
        if f.suffix.lower() not in ('.svg', '.png') or f.name.startswith('.') or '.tmp' in f.name or not f.is_file():
            continue
        rel_imp = f.relative_to(d).as_posix()
        rel = f.relative_to(a).as_posix()
        png = f.suffix.lower() == '.png'
        st = f.stat()
        if st.st_size > (8 if png else 0.5) * 1024 * 1024:
            ecartes.append({'fichier': rel, 'raison': f'fichier trop lourd (plus de {"8 Mo" if png else "512 Ko"})'})
            continue
        trait, recolorable, ratio = False, False, 1.0
        if png:
            try:
                with open(f, 'rb') as fh:
                    tete_png = fh.read(32)
            except OSError:
                tete_png = b''
            taille = _png_taille(tete_png)
            if not taille or not taille[0] or not taille[1]:
                ecartes.append({'fichier': rel, 'raison': 'PNG illisible'})
                continue
            ratio = taille[1] / taille[0]
        else:
            try:
                texte = f.read_text(encoding='utf-8', errors='strict')
            except (OSError, UnicodeDecodeError):
                ecartes.append({'fichier': rel, 'raison': 'SVG illisible (texte UTF-8 attendu)'})
                continue
            refus = _svg_icone_ok(texte)
            if refus:
                ecartes.append({'fichier': rel, 'raison': refus})
                continue
            trait = _trait_svg(texte)
            # recolorable : peinture par currentColor, ou une seule couleur NEUTRE ecrite en dur (noir, gris, blanc : icone d'un
            # pack, elle suit la charte ; meme regle que monoToCurrent de vectors.tsx) ; une couleur vive (logo), plusieurs
            # couleurs ou un degrade : couleurs du fichier
            peintures = {m.group(1).strip().lower() for m in re.finditer(r'(?<![\w-])(?:fill|stroke)\s*[:=]\s*["\']?\s*([^"\';>}]+)', texte)}
            peintures -= {'none', 'currentcolor', 'transparent', 'inherit', ''}
            recolorable = not re.search(r'<(linear|radial)Gradient\b', texte) and not any(p.startswith(('url(', 'var(')) for p in peintures) \
                and (not peintures or (len(peintures) == 1 and _neutre(next(iter(peintures)))))
            vb = re.search(r'viewBox\s*=\s*["\']\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', texte)
            if vb and float(vb.group(1)) > 0:
                ratio = float(vb.group(2)) / float(vb.group(1))
        # chemin utilisable par un vecteur du reel (caracteres surs, 160 au plus pour le serveur) ; sinon copie au nom simple
        # (l'original n'est jamais touche)
        fichier = rel
        copie = None
        h = hashlib.sha1(rel_imp.encode('utf-8')).hexdigest()[:8]
        if len(rel) > 150 or not all(_SEGMENT_SUR.match(p) for p in rel_imp.split('/')):
            base = _slug(_plat(rel_imp[:-len(f.suffix)]).replace('/', '-'))[:60].strip('-._') or 'icone'
            copie = f'{IMPORT_COPIES}/{base}-{h}{f.suffix.lower()}'
            dst = a / copie
            try:
                if not dst.is_file() or dst.stat().st_size != st.st_size or int(dst.stat().st_mtime) != int(st.st_mtime):
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    tmp = dst.with_name(f'{dst.name}.{os.getpid()}.tmp')
                    shutil.copy2(f, tmp)
                    os.replace(tmp, dst)
            except OSError as x:
                ecartes.append({'fichier': rel, 'raison': f'copie au nom simple impossible ({str(x)[:80]})'})
                continue
            fichier = copie
        dossiers = rel_imp.split('/')[:-1]
        lic = licence_de(dossiers)
        nom = re.sub(r'[-_]+', ' ', f.stem).strip() or f.stem
        nom = nom[:1].upper() + nom[1:]
        mots_nom = [m for m in re.split(r'[\s_.-]+', f.stem) if m]
        # packs achetes aux noms anglais (« money-bag.svg ») : aussi trouves en francais (« argent », « sac »)
        traduits = [mots_fr.get(m.lower()) for m in mots_nom if isinstance(mots_fr.get(m.lower()), str)]
        ident = f'icone:import:{_slug(rel_imp[:-len(f.suffix)].replace("/", ":"))}'
        if len(ident) > 120 or ident in ids:
            # trop long (debut commun de deux chemins) ou meme nom en SVG et en PNG : empreinte du chemin complet
            ident = f'{ident[:106].rstrip("-.")}-{f.suffix.lower()[1:]}{h}'
        ids.add(ident)
        out.append(((-1, 0), {'id': ident, 'type': TYPE_ICONE,
                        'nom': nom[:80], 'categorie': (dossiers[0].lower() if dossiers else 'importées')[:40],
                        'motsCles': _mots(mots_nom, traduits, [x.lower() for x in dossiers], 'importé', 'icône', 'pack'),
                        'intensite': 1, 'formats': list(FORMATS), 'apercu': fichier, 'fichier': fichier,
                        'licence': (LICENCE_IMPORT + (f' — voir assets/{lic.relative_to(a).as_posix()}' if lic else ' — vérifie la licence du pack acheté'))[:200],
                        'provenance': (f'Déposé dans assets/{rel}' + (f' (copie au nom simplifié : assets/{copie})' if copie else ''))[:300],
                        'params': _params_icone(trait=trait, png=png, ratio=ratio, recolorable=recolorable, en=f.stem),
                        'source': 'import', 'description': f'Icône importée ({"PNG : couleurs du fichier" if png else "SVG"}) — trait, plein ou verre'}))
    return out


def _signature_icones(racine=None):
    """Empreinte des dossiers d'icones (nombre, date, taille) ; os.scandir : sous Windows, la date et la taille viennent
    de la liste du dossier (pas un appel par fichier : ~1 900 icones lues a chaque ouverture de la banque)."""
    a = _assets(racine)
    parts = [f'icones{CODE_ICONES}']

    def parcours(d, acc, prof=0):
        if prof > 12:  # lien de dossier qui boucle sur lui-meme : jamais de recursion sans fin
            return
        try:
            with os.scandir(d) as it:
                for x in it:
                    if x.is_dir(follow_symlinks=True):
                        parcours(x.path, acc, prof + 1)
                    elif x.is_file() and '.tmp' not in x.name:
                        st = x.stat()
                        acc[0], acc[1], acc[2] = acc[0] + 1, max(acc[1], int(st.st_mtime)), acc[2] + st.st_size
        except OSError:
            pass

    for rel in (ICONES, IMPORT):
        acc = [0, 0, 0]
        parcours(a / rel, acc)
        parts.append(f'{rel}:{acc[0]}:{acc[1]}:{acc[2]}')
    return '|'.join(parts)


def construire_icones(racine=None):
    """(Re)construit assets/banque/catalogue-icones.json (bibliotheques + import). -> rapport."""
    debut = time.time()
    a = _assets(racine)
    (a / 'banque').mkdir(parents=True, exist_ok=True)
    ecartes = []
    dico = _dico_icones(a)
    trouvees = []
    racine_ic = a / ICONES
    if racine_ic.is_dir():
        for d in sorted(p for p in racine_ic.iterdir() if p.is_dir()):
            trouvees += _bibliotheque(a, d, dico, ecartes)
    trouvees += _imports(a, ecartes, dico)
    ordre = {c: i for i, c in enumerate(dico.get('categories') or [])}
    # categories de la plus utile en publicite a la moins utile ; dans une categorie : importees, choisies (ordre du
    # dictionnaire : la plus parlante d'abord), puis les autres par nom ; l'ordre departage les resultats d'une recherche
    trouvees.sort(key=lambda x: (ordre.get(x[1]['categorie'], 90 if x[1]['source'] != 'import' else -1), x[0], _plat(x[1]['nom'])))
    vus = set()
    propres = []
    for _, e in trouvees:
        if not ID_OK.match(e['id']) or e['id'] in vus:
            ecartes.append({'fichier': e.get('fichier') or e['id'], 'raison': 'identifiant en double ou invalide'})
            continue
        vus.add(e['id'])
        propres.append(e)
    data = {'version': VERSION, 'code': CODE_ICONES, 'construit': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'signature': _signature_icones(racine), 'compte': {TYPE_ICONE: len(propres)}, 'ecartes': ecartes, 'entrees': propres}
    tete = json.dumps({k: v for k, v in data.items() if k != 'entrees'}, ensure_ascii=False)[:-1]
    texte = tete + ', "entrees": [\n' + ',\n'.join(json.dumps(e, ensure_ascii=False) for e in propres) + '\n]}\n'
    _ecrire(a / CATALOGUE_ICONES, texte)
    return {'entrees': len(propres), 'fichier': f'assets/{CATALOGUE_ICONES}', 'ecartes': len(ecartes),
            'importees': sum(1 for e in propres if e['source'] == 'import'), 'secondes': round(time.time() - debut, 1)}


def _charger_icones(racine=None):
    """Catalogue des icones a jour (reconstruit si une bibliotheque ou le dossier import a change)."""
    f = _assets(racine) / CATALOGUE_ICONES
    data = None
    if f.is_file():
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
        except ValueError:
            data = None
    if not data or data.get('code') != CODE_ICONES or data.get('signature') != _signature_icones(racine):
        construire_icones(racine)
        data = json.loads(f.read_text(encoding='utf-8'))
    return data


# ---------------------------------------------------------------- construction du catalogue


def _signature(racine=None):
    """Empreinte peu couteuse des dossiers sources (nombre, taille, date) : un changement reconstruit le catalogue."""
    a = _assets(racine)
    parts = [f'code{CODE}']
    for rel in ('sfx/editeur', 'sfx/kenney', 'banque/sons', 'banque/vecteurs', 'overlays'):
        n = m = s = 0
        d = a / rel
        if d.is_dir():
            for f in d.rglob('*'):
                if f.is_file() and '.tmp' not in f.name:
                    st = f.stat()
                    n, m, s = n + 1, max(m, int(st.st_mtime)), s + st.st_size
        parts.append(f'{rel}:{n}:{m}:{s}')
    return '|'.join(parts)


def construire(racine=None):
    """(Re)construit assets/banque/catalogue.json a partir des ressources locales. Incremental : les sons deja crees, les
    formes d'onde a jour et les mesures deja faites sont gardes. -> {'entrees': n, 'fichier', 'compte', 'ecartes', ...}"""
    debut = time.time()
    a = _assets(racine)
    (a / 'banque').mkdir(parents=True, exist_ok=True)
    crees = _creer_sons(racine)
    # mesures des sons (cache : taille + date)
    cache_f = a / 'banque/apercus/sons/mesures.json'
    try:
        cache = json.loads(cache_f.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        cache = {}
    mesures = {}
    fichiers = [*(a / 'sfx/editeur').glob('*.wav'), *(a / 'banque/sons').glob('*.wav'), *(a / 'sfx/kenney').rglob('*.ogg')]
    for f in fichiers:
        rel = f.relative_to(a).as_posix()
        st = f.stat()
        c = cache.get(rel)
        if c and c.get('taille') == st.st_size and c.get('date') == int(st.st_mtime):
            mesures[rel] = c
            continue
        try:
            mesures[rel] = {**_mesure(f), 'taille': st.st_size, 'date': int(st.st_mtime)}
        except Exception as e:  # fichier abime : ecarte, jamais bloquant
            mesures[rel] = {'duree': 0.0, 'crete': -99.0, 'niveau': -99.0, 'taille': st.st_size, 'date': int(st.st_mtime), 'erreur': str(e)[:120]}
    _ecrire(cache_f, json.dumps(mesures, ensure_ascii=False, sort_keys=True, indent=0))
    ecartes = []
    sons = _sons(racine, mesures, ecartes)
    # formes d'onde manquantes ou plus vieilles que le son
    ffmpeg = _ffmpeg(racine)
    a_faire = [(src, ap) for _, src, ap in sons if not ap.is_file() or ap.stat().st_mtime < src.stat().st_mtime]
    faites = 0
    if a_faire and ffmpeg:
        with ThreadPoolExecutor(max_workers=max(2, min(8, (os.cpu_count() or 4) - 2))) as pool:
            faites = sum(pool.map(lambda x: _onde(ffmpeg, *x), a_faire))
    entrees = []
    for e, _, ap in sons:
        if not ap.is_file():
            ecartes.append({'fichier': e['fichier'], 'raison': 'forme d’onde impossible (FFmpeg absent ou son illisible)'})
            continue
        entrees.append(e)
    entrees += _templates(racine) + _effets(racine) + _vecteurs(racine, ecartes)
    # ordre par defaut : type, puis sons crees/de l'editeur avant Kenney, puis categorie, puis nom
    rang_type = {'son': 0, 'template': 1, 'vecteur': 2, 'effet': 3}
    rang_source = {'banque': 0, 'editeur': 1, 'vecteurs': 1, 'kenney': 2}
    rang_cat = {c: i for i, c in enumerate(CAT_SONS + CAT_TEMPLATES + CAT_EFFETS)}
    entrees.sort(key=lambda e: (rang_type.get(e['type'], 9), rang_cat.get(e['categorie'], 50), rang_source.get(e.get('source'), 5),
                                _plat(e['nom'])))
    vus = set()
    propres = []
    for e in entrees:
        if not ID_OK.match(e['id']) or e['id'] in vus or not e.get('licence') or not e.get('provenance') or not e.get('apercu'):
            ecartes.append({'fichier': e.get('fichier') or e['id'], 'raison': 'identifiant en double ou invalide, ou licence/provenance/aperçu manquant'})
            continue
        vus.add(e['id'])
        propres.append(e)
    compte = {t: sum(1 for e in propres if e['type'] == t) for t in TYPES}
    data = {'version': VERSION, 'code': CODE, 'construit': time.strftime('%Y-%m-%dT%H:%M:%S'), 'signature': _signature(racine),
            'compte': compte, 'ecartes': ecartes, 'entrees': propres}
    # une entree par ligne : lisible et diffable
    tete = json.dumps({k: v for k, v in data.items() if k != 'entrees'}, ensure_ascii=False)[:-1]
    texte = tete + ', "entrees": [\n' + ',\n'.join(json.dumps(e, ensure_ascii=False) for e in propres) + '\n]}\n'
    _ecrire(a / CATALOGUE, texte)
    try:  # catalogue des icones (a part) : jamais bloquant pour celui des effets, sons, vecteurs et modeles
        icones = construire_icones(racine)
    except Exception as x:  # noqa: BLE001
        icones = {'entrees': 0, 'erreur': str(x)[:200]}
    return {'entrees': len(propres), 'fichier': f'assets/{CATALOGUE}', 'compte': compte, 'ecartes': len(ecartes),
            'sons_crees': crees, 'apercus_faits': faites, 'secondes': round(time.time() - debut, 1), 'icones': icones}


def _charger(racine=None):
    """Catalogue a jour : reconstruit s'il manque ou si un dossier source a change (vecteurs ajoutes, sons...)."""
    f = _assets(racine) / CATALOGUE
    data = None
    if f.is_file():
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
        except ValueError:
            data = None
    if not data or data.get('code') != CODE or data.get('signature') != _signature(racine):
        construire(racine)
        data = json.loads(f.read_text(encoding='utf-8'))
    return data


# ---------------------------------------------------------------- lecture : filtres, entree, apercu


def _score(e, mots):
    nom = _plat(e['nom'])
    return sum(3 if nom.startswith(m) else 2 if m in nom else 1 for m in mots)


def filtrer(entrees, filtres=None):
    """Memes regles que l'interface (banque.tsx) : type, categorie (sans accents), format, intensite exacte, q = tous les
    mots presents (debut de mot) dans le nom, la categorie, les mots-cles ou la description ; tri par pertinence si q."""
    f = filtres or {}
    typ = f.get('type') or None
    if typ and typ not in TYPES_FILTRE:
        raise ValueError(f'Type inconnu : {typ} (effet, son, vecteur, template ou icone).')
    cat = _plat(f.get('categorie') or '')
    fmt = f.get('format') or None
    inten = int(f['intensite']) if f.get('intensite') not in (None, '') else None
    mots = [m for m in re.split(r'[^a-z0-9]+', _plat(f.get('q') or '')) if m]
    out = []
    for e in entrees:
        if typ and e['type'] != typ:
            continue
        if cat and _plat(e['categorie']) != cat:
            continue
        if fmt and fmt not in (e.get('formats') or FORMATS):
            continue
        if inten and e.get('intensite') != inten:
            continue
        if mots:
            botte = _plat(' '.join([e['nom'], e['categorie'], ' '.join(e.get('motsCles') or []), e.get('description') or '']))
            jetons = [j for j in re.split(r'[^a-z0-9]+', botte) if j]
            if not all(any(j.startswith(m) for j in jetons) for m in mots):
                continue
        out.append(e)
    if mots:
        out.sort(key=lambda e: -_score(e, mots))  # tri stable : l'ordre du catalogue departage
    return out


def catalogue(filtres=None, racine=None):
    """Entrees du catalogue filtrees. filtres : {type, categorie, q (mots-cles, texte libre), format, intensite}.
    type « icone » : catalogue des icones (a part) ; sans type, les 4 types historiques seulement, sauf filtres['icones']
    vrai (les deux). Le catalogue des icones est remis a jour a chaque appel (icones deposees dans assets/banque/import).
    -> {'entrees': [...], 'total': n, 'categories': {type: [categorie...]}, 'filtres', 'compte', 'construit'}"""
    f = filtres or {}
    if f.get('type') == TYPE_ICONE:
        data = _charger_icones(racine)
        tous = data.get('entrees') or []
    else:
        data = _charger(racine)
        tous = data.get('entrees') or []
        try:
            ic = _charger_icones(racine)
            if f.get('icones'):
                tous = tous + (ic.get('entrees') or [])
        except Exception:  # noqa: BLE001 — une icone abimee ne bloque jamais la banque
            pass
    choisis = filtrer(tous, {k: v for k, v in f.items() if k != 'icones'})
    categories = {}
    for e in tous:
        lst = categories.setdefault(e['type'], [])
        if e['categorie'] not in lst:
            lst.append(e['categorie'])
    return {'entrees': choisis, 'total': len(choisis), 'categories': categories, 'filtres': filtres or {},
            'compte': data.get('compte') or {}, 'construit': data.get('construit'), 'version': data.get('version', VERSION)}


def entree(asset_id, racine=None):
    """Une entree du catalogue (ou du catalogue des icones) par son id (KeyError si inconnue)."""
    data = _charger_icones(racine) if str(asset_id).startswith(f'{TYPE_ICONE}:') else _charger(racine)
    for e in data.get('entrees') or []:
        if e['id'] == asset_id:
            return e
    raise KeyError(f'Ressource inconnue dans la banque : {asset_id}')


def apercu(asset_id, racine=None):
    """Chemin relatif a assets/ de l'apercu d'une entree."""
    return entree(asset_id, racine)['apercu']


# ---------------------------------------------------------------- « Ajouter » : meme regle que banque.tsx (SPEC §9.2)


def palette(reel):
    """Couleurs de la charte / du style (SPEC §9.3, meme ordre que vectorPalette de remotion/src/vectors.tsx)."""
    brand = reel.get('brand') or {}
    design = (reel.get('design') or {}) if design_actif(reel) else {}
    style = reel.get('style') or {}
    return {'principale': (brand.get('style') or {}).get('highlight') or design.get('accent') or style.get('highlight') or ACCENT,
            'secondaire': design.get('secondary') or brand.get('bannerBg') or style.get('color') or '#FFFFFF',
            'contour': style.get('stroke') or '#000000'}


def design_actif(reel):
    d = reel.get('design') or {}
    return d.get('mode') if d.get('mode') and d.get('enabled') is not False else None


def graphismes_visibles(reel):
    """Un style avec habillage (galerie) masque les graphismes ajoutes, sauf si le monteur les a rallumes."""
    return not design_actif(reel) or (reel.get('design') or {}).get('suppressExtras') is False


def forme_template(entry, reel):
    """Forme d'un template dans CE reel -> ('graphics' | 'styleScenes' | None, genre).
    Style avec habillage : la scene du style (les graphismes y sont masques) ; sinon le graphisme."""
    p = entry.get('params') or {}
    mode = design_actif(reel)
    if p.get('cible') == 'graphics' and p.get('kind') and graphismes_visibles(reel):
        return 'graphics', p['kind']
    sc = p.get('scene')
    if mode and sc:
        k = sc['kind']
        if mode == 'editorial':  # ce style n'affiche que le mot geant derriere la personne
            k = 'keyword' if k in ('keyword', 'paper', 'cta') else None
        elif k == 'keyword':
            k = 'paper'
        if k:
            return 'styleScenes', k
    if p.get('kind'):
        return 'graphics', p['kind']
    return None, None


def visible(entry, reel):
    """(True, '') ou (False, raison en francais) : l'element ajoute sera-t-il vu dans ce reel ?"""
    typ = entry.get('type')
    p = entry.get('params') or {}
    if typ == 'son':
        sfx = reel.get('sfx') or {}
        return (True, '') if sfx.get('enabled') else (False, 'Les bruitages sont coupés pour cette vidéo : active-les pour entendre ce son.')
    if typ == 'template':
        champ, _ = forme_template(entry, reel)
        if champ is None:
            return False, 'Ce modèle n’a pas de version pour ce style.'
        if p.get('besoin') == 'logo' and not (reel.get('brand') or {}).get('logo'):
            return False, 'Il faut une charte client avec un logo (onglet Style).'
        # un graphisme pose depuis la banque est « manual » : visible meme dans un style avec habillage (Reel.tsx)
    return True, ''


def _r3(v):
    """Arrondi a 3 decimales comme Math.round de l'interface (pas l'arrondi « au pair » de Python)."""
    return math.floor(v * 1000 + 0.5) / 1000


def _cadre(reel, t):
    """Partie de la prise visible a l'instant t : sourceRectAt de remotion/src/timeline.ts (cadrage qui suit le sujet,
    zooms, angle — meme calcul que l'apercu, l'export et l'interface), lance dans Node. None si indisponible."""
    import tempfile
    ts = next((p for p in (Path(media.ROOT) / 'remotion/src/timeline.ts', Path(__file__).resolve().parents[2] / 'remotion/src/timeline.ts')
               if p.is_file()), None)
    if not ts:
        return None
    code = ("import fs from 'node:fs';import {sourceRectAt} from " + json.dumps(ts.as_uri()) + ";"
            "const r=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));"
            "process.stdout.write(JSON.stringify(sourceRectAt(r,Number(process.argv[2]))));")
    tmpdir = Path(media.ROOT) / 'runtime/cache/tmp'
    tmpdir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, dir=tmpdir, encoding='utf-8') as f:
        json.dump(reel, f, ensure_ascii=False)
        name = f.name
    try:
        r = subprocess.run(['node', '--input-type=module', '-e', code, name, repr(float(t))], capture_output=True, text=True,
                           encoding='utf-8', timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    finally:
        Path(name).unlink(missing_ok=True)


def _mediane(xs):
    s = sorted(xs)
    n = len(s)
    return s[(n - 1) // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def visage(reel, cadre, duree):
    """Visage dans l'image (0-1) pendant [t, t + duree] : piste de recadrage (qui parle) sinon echantillons de la prise
    affichee. -> {x, y, w (largeur, part de la largeur de l'image)} ou None. Meme calcul que visageDansCadre (banque.tsx)."""
    if not cadre:
        return None
    src = reel['sources'].get(cadre['source']) or {}
    track = src.get('track') or []
    rows = track or src.get('samples') or []
    t = cadre['tSrc']
    pts = [p for p in rows if t - 0.3 <= p[0] <= t + duree]
    if not pts and rows:
        pts = [min(rows, key=lambda p: abs(p[0] - t))]
    if not pts:
        return None
    ws = [p[3] for p in pts if len(p) > 3 and p[3] > 0] if track else []
    return {'x': (_mediane([p[1] for p in pts]) - cadre['x']) / cadre['w'], 'y': (_mediane([p[2] for p in pts]) - cadre['y']) / cadre['h'],
            'w': (_mediane(ws) if ws else 0.26) / cadre['w']}


def place_libre(reel, face, taille):
    """Centre (x, y en 0-1) d'un element de taille {w, h} hors du visage : au-dessus de la tete s'il y a la place, sinon a
    cote (format large, si l'element peut se decaler), sinon entre le menton et les sous-titres, sinon le plus haut
    possible. None si le visage est inconnu. Meme regle que placeLibre (banque.tsx)."""
    if not face:
        return None
    W, H = reel['width'], reel['height']
    marge = 0.07 if H > W else 0.05
    demi = face['w'] / 2 + 0.03
    haut_visage = face['w'] * W / H
    tete = face['y'] - 0.75 * haut_visage
    menton = face['y'] + 0.6 * haut_visage
    w, h = taille['w'], taille['h']
    if tete - marge >= h + 0.02:
        return {'x': 0.5, 'y': _r3(marge + (tete - marge) / 2)}
    if taille.get('cote'):
        gauche, droite = face['x'] - demi, 1 - face['x'] - demi
        if max(gauche, droite) >= w + 0.03:
            x = face['x'] - demi - 0.015 - w / 2 if gauche >= droite else face['x'] + demi + 0.015 + w / 2
            return {'x': _r3(x), 'y': _r3(min(1 - marge - h / 2, max(marge + h / 2, face['y'])))}
    bas = 1 - marge if taille.get('sousTitres') is False else float((reel.get('style') or {}).get('position', 0.72)) - 0.02
    if bas - menton >= h + 0.02:
        return {'x': 0.5, 'y': _r3(menton + (bas - menton) / 2)}
    return {'x': 0.5, 'y': _r3(marge + h / 2)}


SCENES_TAILLE = {'notification': (0.79, 0.2), 'metric': (0.6, 0.3), 'cta': (0.7, 0.2), 'flow': (None, 0.22), 'dashboard': (None, 0.45),
                 'comparison': (None, 0.3), 'paper': (0.6, 0.16)}  # (largeur en part du petit cote, ou None = 0,9 de l'image ; hauteur)


def taille_element(reel, champ, kind, x):
    """Encombrement approximatif (part de la largeur / hauteur de l'image) d'un element pose, pour le placer.
    centre : la position donnee est le centre (sinon le bord haut). None : element plein ecran (pas de placement)."""
    W, H = reel['width'], reel['height']
    u = min(W, H)
    if champ == 'vectors':  # x['w'] : part du petit cote de l'image (remotion/src/vectors.tsx)
        return {'w': x['w'] * u / W, 'h': x['w'] * float(x.get('ratio') or 1) * u / H, 'cote': True, 'centre': True}
    if champ == 'graphics':
        if kind == 'chiffre':
            return {'w': 0.9, 'h': u * 0.28 / H, 'centre': True}
        if kind == 'coches':
            n = min(5, len([i for i in x.get('items') or [] if i]))
            return {'w': 0.8, 'h': u * (0.08 + (0.07 if x.get('title') else 0) + n * 0.089) / H, 'centre': False}
        if kind == 'carte':
            return {'w': u * 0.62 / W, 'h': u * (0.52 if x.get('image') else 0.25) / H, 'centre': False}
        return None
    s = SCENES_TAILLE.get(kind)
    if not s:
        return None
    w = s[0] * u / W if s[0] else 0.9
    return {'w': w, 'h': s[1] * u / H, 'cote': w < 0.6, 'centre': True, 'sousTitres': False}


def placer(reel, t, duree, champ, kind, x, cadre=None):
    """Position libre (hors du visage) d'un element pose a t -> {x, y} (y = bord haut pour coches et carte) ou None.
    cadre : fonction t -> sourceRectAt (deja calculee), False (pas de placement) ou None (calcul par Node)."""
    taille = taille_element(reel, champ, kind, x)
    if not taille:
        return None
    rect = cadre(t) if callable(cadre) else (_cadre(reel, t) if cadre is None else cadre)
    pos = place_libre(reel, visage(reel, rect, duree), taille)
    if not pos:
        return None
    return pos if taille['centre'] else {'x': pos['x'], 'y': _r3(pos['y'] - taille['h'] / 2)}


def _mots_dits(reel):
    """Mots du montage (temps du montage) dans l'ordre, sans les mots masques ni coupes."""
    from . import montage
    clips = {c['id']: c for c in reel['clips']}
    out = []
    for w in montage.compute(reel)['words']:
        ws = clips.get(w['clip'], {}).get('words', [])
        mot = ws[w['index']] if w['index'] < len(ws) else {}
        if not mot.get('hide') and str(w['w']).strip():
            out.append(w)
    return out


def _mot_a(mots, t):
    """Premier mot dit a partir de t (sinon le dernier)."""
    return next((w for w in mots if w['start'] >= t - 0.05), mots[-1] if mots else None)


def _mot_fort(mots, t):
    """Texte pre-rempli : premier mot d'au moins 3 lettres dit dans [t, t + 1,5 s], sinon None."""
    for w in mots:
        if w['start'] < t - 0.05:
            continue
        if w['start'] > t + 1.5:
            break
        m = re.sub(r'^[^\w]+|[^\w]+$', '', str(w['w']))
        if len(m) >= 3:
            return m
    return None


def element_pour_reel(entry, reel, at, mots=None, cadre=None, style=None):
    """Element a poser dans le reel pour « Ajouter » (meme regle que banque.tsx) -> (champ, element) :
    son -> ('sfx.extra', {id, t, name, gain, reason, manual}) ; vecteur -> ('vectors', VectorItem) ;
    template -> ('graphics', Graphic) ou ('styleScenes', StyleScene) ; effet -> ('flash', {...}) | ('effects', {...}) |
    ('vectors', ...) ; icone -> ('vectors', VectorItem avec meta.icone = {style, nom, banque}) ; style : trait, plein ou
    verre (defaut : celui du catalogue). Tout element pose est marque manual:true (aucune passe automatique n'y touchera).
    Vecteurs, graphismes et scenes sont places hors du visage (placer) ; cadre : sourceRectAt deja calcule (tests),
    False = pas de placement (positions par defaut du SPEC)."""
    typ = entry.get('type')
    p = entry.get('params') or {}
    t = round(max(0.0, float(at or 0)), 2)
    raison = f"Banque : {entry.get('nom') or entry.get('id')}"
    if typ == TYPE_ICONE:
        w = float(p.get('largeur') or ICONE_LARGEUR)
        duree = float(p.get('duree') or ICONE_DUREE)
        st = style if style in STYLES_ICONE else p.get('style') if p.get('style') in STYLES_ICONE else ICONE_STYLE
        anim = p.get('anim') or {}
        pos = placer(reel, t, duree, 'vectors', None, {'w': w, 'ratio': 1}, cadre)  # icone : boite carree (tuile, pastille)
        return 'vectors', {'id': _uid('v'), 'asset': entry['fichier'], 'at': t, 'duration': duree,
                           'x': float(pos['x'] if pos else 0.5), 'y': float(pos['y'] if pos else 0.35), 'w': w,
                           'rotation': 0, 'opacite': 1, 'couleurs': {'principale': None, 'secondaire': None, 'contour': None},
                           'couleursManuelles': False, 'anim': {'entree': anim.get('entree') or 'pop', 'sortie': anim.get('sortie') or 'fondu'},
                           'manual': True, 'raison': raison,
                           'meta': {'icone': {'style': st, 'nom': str(entry.get('nom') or '')[:80], 'banque': entry['id']}}}
    if typ == 'son':
        return 'sfx.extra', {'id': _uid('s'), 't': t, 'name': p.get('name') or entry['fichier'], 'gain': float(p.get('gain', 1)),
                             'reason': raison, 'manual': True}
    if typ == 'vecteur' or (typ == 'effet' and p.get('cible') == 'vector'):
        anim = p.get('anim') or {}
        w = float(p.get('largeur') or 0.35)
        duree = float(p.get('duree') or 2)
        pos = None if 'x' in p or 'y' in p else placer(reel, t, duree, 'vectors', None, {'w': w, 'ratio': p.get('ratio')}, cadre)
        return 'vectors', {'id': _uid('v'), 'asset': entry['fichier'], 'at': t, 'duration': duree,
                           'x': float(pos['x'] if pos else p.get('x', 0.5)), 'y': float(pos['y'] if pos else p.get('y', 0.35)), 'w': w,
                           # null = couleurs de la charte / du style ; garderCouleurs : couleurs d'origine du dessin
                           'rotation': 0, 'opacite': 1,
                           'couleurs': {k: ((p.get('couleurs') or {}).get(k) if p.get('garderCouleurs') else None)
                                        for k in ('principale', 'secondaire', 'contour')},
                           'couleursManuelles': bool(p.get('garderCouleurs')),
                           'anim': {'entree': anim.get('entree') or 'pop', 'sortie': anim.get('sortie') or 'fondu'},
                           'manual': True, 'raison': raison}
    if typ == 'effet':
        if p.get('cible') == 'flash':
            return 'flash', {'enabled': True, 'kind': p.get('kind') or 'blanc'}
        if p.get('cible') == 'effects':
            return 'effects', {**EFFETS_DEFAUT, **(reel.get('effects') or {}), **(p.get('effects') or {})}
        raise ValueError(f"Effet sans cible : {entry.get('id')}")
    if typ != 'template':
        raise ValueError(f'Type inconnu : {typ}')
    champ, kind = forme_template(entry, reel)
    if champ is None:
        raise ValueError('Ce modèle n’a pas de version pour ce style.')
    if p.get('texteDit') or champ == 'styleScenes':
        mots = _mots_dits(reel) if mots is None else mots
    dit = _mot_fort(mots, t) if p.get('texteDit') else None
    if champ == 'styleScenes':
        sc = p['scene']
        w = _mot_a(mots, t)
        if not w:
            raise ValueError('Aucun mot dit dans ce montage : impossible d’ancrer la scène.')
        duree = float(sc.get('duree') or 2.4)
        pos = placer(reel, w['start'], duree, 'styleScenes', kind, {}, cadre)
        return 'styleScenes', {'id': _uid('bq'), 'kind': kind, 'clip': w['clip'], 'index': w['index'], 'length': 1,
                               'text': dit or sc['text'], 'secondary': sc.get('secondary') or '', 'duration': duree,
                               'x': float(pos['x'] if pos else sc.get('x', 0.5)), 'y': float(pos['y'] if pos else sc.get('y', 0.5)),
                               'scale': float(sc.get('scale', 1)), 'rotation': float(sc.get('rotation', 0)),
                               'color': palette(reel)['principale'], 'manual': True}
    props = {**copy.deepcopy(p.get('props') or {}), 'banque': entry['id']}
    if dit and 'text' in props:
        props['text'] = dit
    duree = float(p.get('duree') or 2)
    if 'y' not in props:
        pos = placer(reel, t, duree, 'graphics', p['kind'], props, cadre)
        if pos:
            props['y'] = pos['y']
    return 'graphics', {'id': _uid('g'), 'kind': p['kind'], 'at': t, 'duration': duree, 'props': props,
                        'manual': True, 'raison': raison}


def ajouter(reel, entry, at, mots=None, cadre=None, style=None):
    """Pose l'element dans le reel (sur place) -> {'champ', 'element', 'visible', 'message'}. Scene du style : placee en
    tete de liste (elle passe devant une scene automatique au meme moment). style : trait, plein ou verre (icones)."""
    champ, el = element_pour_reel(entry, reel, at, mots, cadre, style)
    vu, pourquoi = visible(entry, reel)
    if champ == 'sfx.extra':
        sfx = reel.get('sfx') or dict(SFX_DEFAUT)
        sfx['extra'] = [*(sfx.get('extra') or []), el]
        reel['sfx'] = sfx
    elif champ in ('vectors', 'graphics'):
        reel[champ] = [*(reel.get(champ) or []), el]
    elif champ == 'styleScenes':
        reel['styleScenes'] = [el, *(reel.get('styleScenes') or [])]
    else:  # flash, effects : reglage de toute la video
        reel[champ] = el
    return {'champ': champ, 'element': el, 'visible': vu, 'message': pourquoi}
