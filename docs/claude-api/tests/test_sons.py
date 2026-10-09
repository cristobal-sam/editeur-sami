"""Tests des sons de coupe varies (ronde « sons » : engine/editeur/sfxgen.py, styles/sons-transitions.json, banque.py),
SANS aucun appel a Claude. Les reels et dossiers ecrits le sont dans un bac a sable (runtime/cache/tmp/<unique>), jamais
dans les projets de l'utilisateur.

    cd D:\\Tools\\editeur_sami\\engine
    ..\\runtime\\venv\\Scripts\\python.exe ..\\docs\\claude-api\\tests\\test_sons.py [--garder]

Cas : fichiers (au moins 40 sons crees ici + copies Kenney, 48 kHz stereo, 3 s au plus), meme sonie a 2 dB pres une fois
SFX_GAIN applique (et SFX_GAIN de timeline.ts = celui du moteur), ni ecretage, ni composante continue, ni clic au debut ou
a la fin, pas d'aigus durs, pic mesure (familles et reserves par defaut de timeline.ts), fiches de la banque (categorie,
licence « créé ici » ou CC0), catalogue des familles valide (6 au moins, tous les roles, 32 sons au plus, chaque style de
styles/montage relie), appliquer_famille (auto, choix gardes, refus en francais), ligne de commande « sons » (version
« avant » gardee, reel inchange en cas d'erreur), sons d'origine jamais reecrits.
--garder : ne supprime pas le bac a sable a la fin."""
import copy
import json
import math
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import numpy as np
import soundfile as sf

ICI = Path(__file__).resolve().parent
ROOT = ICI.parents[2]
sys.path.insert(0, str(ROOT / 'engine'))
from editeur import banque, sfxgen  # noqa: E402

PYTHON = str(ROOT / 'runtime/venv/Scripts/python.exe')
BAC = ROOT / 'runtime/cache/tmp' / f'test-sons-{uuid.uuid4().hex[:10]}'
ENV = dict(os.environ, PYTHONIOENCODING='utf-8')  # comme le serveur (sorties JSON avec accents)
NOUVEAUX = [*sfxgen.COUPES, *sfxgen.KENNEY]
bilan = []


def verifier(nom, ok, detail=''):
    bilan.append({'test': nom, 'ok': bool(ok), 'detail': str(detail)[:300]})
    print(('OK   ' if ok else 'ECHEC') + f' {nom}' + (f' — {str(detail)[:300]}' if detail and not ok else ''))


def sfx_gain_ts():
    """SFX_GAIN lu dans remotion/src/timeline.ts (la meme table que l'apercu et l'export)."""
    src = (ROOT / 'remotion/src/timeline.ts').read_text(encoding='utf-8')
    bloc = re.search(r'export const SFX_GAIN: Record<string, number> = \{(.*?)\n\};', src, re.S).group(1)
    return {m.group(1) or m.group(2): float(m.group(3)) for m in re.finditer(r"(?:'([a-z0-9-]+)'|([a-z0-9]+)):\s*([0-9.]+)", bloc)}


def pool_defaut_ts():
    """SFX_POOL_DEFAUT lu dans timeline.ts : {cle: [(nom, pic, gain)]}."""
    src = (ROOT / 'remotion/src/timeline.ts').read_text(encoding='utf-8')
    bloc = re.search(r'export const SFX_POOL_DEFAUT[^=]*= \{(.*?)\n\};', src, re.S).group(1)
    out = {}
    for m in re.finditer(r"'([a-z-]+:[a-z-]+)': \[(.*?)\]\],", bloc, re.S):
        out[m.group(1)] = [(a, float(b), float(c)) for a, b, c in re.findall(r"\['([a-z0-9-]+)', ([0-9.]+), ([0-9.]+)\]", m.group(2) + ']')]
    return out


MESURES = {}


def mesure(nom):
    if nom not in MESURES:
        MESURES[nom] = sfxgen.mesure(sfxgen.OUT / f'{nom}.wav')
    return MESURES[nom]


# ---------- 1. fichiers ----------
def cas_fichiers():
    verifier('au moins 40 sons de coupe crees ici (synthese, sans droit tiers)', len(sfxgen.COUPES) >= 40, len(sfxgen.COUPES))
    absents = [n for n in NOUVEAUX if not (sfxgen.OUT / f'{n}.wav').is_file()]
    verifier(f'les {len(NOUVEAUX)} fichiers existent dans assets/sfx/editeur', not absents, absents)
    if absents:
        return
    mal = []
    for n in NOUVEAUX:
        info = sf.info(str(sfxgen.OUT / f'{n}.wav'))
        if info.samplerate != 48000 or info.channels != 2 or info.subtype != 'PCM_16' or not 0.004 < info.duration <= banque.LONGUEUR_MAX:
            mal.append((n, info.samplerate, info.channels, info.subtype, round(info.duration, 3)))
    verifier('48 kHz, stereo, PCM 16 bits, 3 s au plus (l\'export coupe a 3 s)', not mal, mal)
    nouveaux = set(NOUVEAUX)
    verifier('aucun nom deja pris par un son d\'origine ou de la banque', not (nouveaux & set(sfxgen.SOUNDS))
             and not (nouveaux & set(banque._sons_crees())))


# ---------- 2. niveau, ecretage, continu, bords, aigus ----------
def cas_qualite():
    gains = sfx_gain_ts()
    hors, ecart_gain, ecrete, dc, bords, aigus = [], [], [], [], [], []
    for n in NOUVEAUX:
        m = mesure(n)
        g = gains.get(n, 1.0)
        eff = m['sonie'] + 20 * math.log10(g)
        if abs(eff - sfxgen.SONIE) > 2:
            hors.append((n, round(eff, 1)))
        if abs(g - sfxgen.gain_sonie(m['sonie'])) > 0.021:
            ecart_gain.append((n, g, sfxgen.gain_sonie(m['sonie'])))
        if m['crete'] > -0.9:
            ecrete.append((n, m['crete']))
        if m['dc'] > 0.005:
            dc.append((n, m['dc']))
        if m['bord'] > 0.05:
            bords.append((n, m['bord']))
        if m['aigus'] > sfxgen.AIGUS_MAX:
            aigus.append((n, m['aigus']))
    effs = [mesure(n)['sonie'] + 20 * math.log10(gains.get(n, 1.0)) for n in NOUVEAUX]
    verifier(f'meme sonie a 2 dB pres une fois SFX_GAIN applique (cible {sfxgen.SONIE} LUFS, {min(effs):.1f} a {max(effs):.1f})', not hors, hors)
    verifier('SFX_GAIN de timeline.ts = gain calcule par le moteur (clics brefs seulement)', not ecart_gain, ecart_gain)
    verifier('aucun ecretage (crete sous -0,9 dBFS)', not ecrete, ecrete)
    verifier('aucune composante continue (moyenne < 0,005)', not dc, dc)
    verifier('aucun clic au debut ni a la fin (4 premiers / derniers echantillons < 0,05)', not bords, bords)
    verifier(f'pas d\'aigus durs (energie au-dessus de 10 kHz <= {sfxgen.AIGUS_MAX:.0%})', not aigus, aigus)
    legacy = {k: v for k, v in gains.items() if k in sfxgen.SOUNDS}
    verifier('gains des 11 sons d\'origine inchanges', legacy == {'click': 2.2, 'declencheur-photo': 1.5, 'ding': 1.0, 'glitch': 0.15,
                                                             'impact': 0.34, 'pop-grave': 0.6, 'pop': 0.6, 'riser': 1.6,
                                                             'whoosh-court': 1.25, 'whoosh-descendant': 1.07, 'whoosh-long': 1.2}, legacy)
    # pic : le moment fort (90 % du maximum de l'enveloppe) ; un riser l'a a la fin, un impact au debut
    p = {n: mesure(n)['pic'] for n in ('riser-cinema', 'impact-sub', 'aspiration', 'whoosh-aerien')}
    verifier('pic mesure : riser et son aspire a la fin, impact au debut, whoosh au milieu',
             p['riser-cinema'] > 1.3 and p['aspiration'] > 0.65 and p['impact-sub'] < 0.03 and 0.2 < p['whoosh-aerien'] < 0.45, p)


# ---------- 3. banque ----------
def cas_banque():
    manquent = [n for n in NOUVEAUX if n not in banque.SONS_COUPES]
    verifier('chaque nouveau son a sa fiche dans banque.SONS_COUPES', not manquent and set(banque.SONS_COUPES) == set(NOUVEAUX), manquent)
    mal = [n for n, (titre, cat, mots, inten) in banque.SONS_COUPES.items()
           if cat not in banque.CAT_SONS or inten not in (1, 2, 3) or not titre or not mots]
    verifier('categories de la banque (whoosh, transition, pop, impact...) et intensite 1-3', not mal, mal)
    # catalogue construit dans le bac a sable : assets/sfx/editeur copie, rien d'autre
    a = BAC / 'banque' / 'assets'
    shutil.copytree(sfxgen.OUT, a / 'sfx/editeur')
    mesures = {f'sfx/editeur/{f.name}': banque._mesure(f) for f in (a / 'sfx/editeur').glob('*.wav')}
    ecartes = []
    entrees = {e['fichier'].split('/')[-1][:-4]: e for e, _, _ in banque._sons(BAC / 'banque', mesures, ecartes)}
    pb = []
    for n in NOUVEAUX:
        e = entrees.get(n)
        if not e:
            pb.append((n, 'absent'))
            continue
        lic_ok = 'CC0' in e['licence'] if n.startswith('kenney-') else e['licence'].startswith('Créé ici')
        if not lic_ok or e['params'].get('name') != n or e['params'].get('gain') != 1 or e['categorie'] != banque.SONS_COUPES[n][1]:
            pb.append((n, e['licence'][:40], e['params']))
    verifier('catalogue : licence « Créé ici » (ou CC0 pour les copies Kenney), nom court (SFX_GAIN), bonne categorie', not pb, pb)
    verifier('aucun son de coupe ecarte par la banque', not [x for x in ecartes if any(n in x['fichier'] for n in NOUVEAUX)], ecartes)
    vieux = [e for n, e in entrees.items() if n in sfxgen.SOUNDS and 'Créé ici' in e['licence']]
    verifier('les sons d\'origine gardent leur fiche d\'avant', not vieux and entrees['whoosh-court']['nom'] == 'Whoosh court')
    verifier('banque.CODE change (catalogue reconstruit au prochain appel)', banque.CODE >= 7, banque.CODE)
    reel = json.loads((ROOT / 'assets' / banque.CATALOGUE).read_text(encoding='utf-8'))
    ids = {e['id'] for e in reel['entrees']}
    verifier('le vrai catalogue de la banque contient les sons de coupe', all(f'son:editeur:{n}' in ids for n in NOUVEAUX),
             [n for n in NOUVEAUX if f'son:editeur:{n}' not in ids][:5])


# ---------- 4. familles ----------
def cas_familles():
    data = json.loads(sfxgen.FAMILLES.read_text(encoding='utf-8'))
    fams = data['familles']
    ids = [f['id'] for f in fams]
    verifier('au moins 6 familles, identifiants valides et uniques', len(fams) >= 6 and len(set(ids)) == len(ids)
             and all(re.fullmatch(r'[a-z0-9-]{1,40}', i) for i in ids), ids)
    verifier('familles attendues (doux, punchy, tech, cinema, retro, glitch, organique)',
             {'doux', 'punchy', 'tech', 'cinema', 'retro', 'glitch', 'organique'} <= set(ids))
    verifier('nom francais et description courte pour chacune', all(f['nom'] and 10 < len(f['description']) < 160 for f in fams))
    roles_ok, trop, sons_pb, pic_pb = [], [], [], []
    for f in fams:
        if set(f['sons']) != set(sfxgen.ROLES) or not all(f['sons'][r] for r in sfxgen.ROLES):
            roles_ok.append(f['id'])
        if sum(len(v) for v in f['sons'].values()) > sfxgen.POOL_MAX:
            trop.append(f['id'])
        for role, lst in f['sons'].items():
            for s in lst:
                if not (sfxgen.OUT / f"{s['name']}.wav").is_file() or not 0 < s['gain'] <= 4 or not s.get('licence') \
                        or not s.get('titre') or set(s) != {'name', 'titre', 'pic', 'gain', 'duree', 'licence'}:
                    sons_pb.append((f['id'], role, s.get('name')))
                    continue
                m = mesure(s['name'])
                if abs(s['pic'] - m['pic']) > 0.002 or abs(s['duree'] - m['duree']) > 0.002 or not 0 <= s['pic'] < s['duree']:
                    pic_pb.append((f['id'], s['name'], s['pic'], m['pic']))
                if s['licence'] != ('CC0 (Kenney.nl)' if s['name'].startswith('kenney-') else 'créé ici'):
                    sons_pb.append((f['id'], s['name'], s['licence']))
    verifier('chaque famille a des sons pour les 6 roles', not roles_ok, roles_ok)
    verifier(f'{sfxgen.POOL_MAX} sons au plus par famille (limite du serveur)', not trop, trop)
    verifier('chaque son : fichier present, gain 0-4, titre et licence', not sons_pb, sons_pb[:6])
    verifier('pic et duree = ceux mesures sur le fichier', not pic_pb, pic_pb[:6])
    styles = sorted(p.stem for p in (ROOT / 'styles/montage').glob('*.json'))
    sans = [s for s in styles if data['styles'].get(s) not in ids]
    verifier(f'chaque style de styles/montage ({len(styles)}) a sa famille', not sans, sans)
    verifier('famille par defaut et familles par son de coupe valides', data['defaut'] in ids and all(v in ids for v in data['sons'].values()))
    sobres = [s for s in styles if not (json.loads((ROOT / 'styles/montage' / f'{s}.json').read_text(encoding='utf-8')).get('sfx') or {}).get('transition')]
    verifier('les styles sobres (sans son de coupe) restent sans son de coupe (rien n\'est change dans styles/montage)',
             len(sobres) >= 10, sobres)
    # reserves par defaut de timeline.ts : sons presents, pic mesure
    defaut = pool_defaut_ts()
    pb = [(k, n, p) for k, lst in defaut.items() for n, p, g in lst
          if not (sfxgen.OUT / f'{n}.wav').is_file() or abs(p - mesure(n)['pic']) > 0.002 or not 0 < g <= 4]
    verifier(f'reserves par defaut de timeline.ts ({len(defaut)}) : sons presents, pic = mesure', len(defaut) >= 10 and not pb, pb[:5])
    verifier('chaque reserve par defaut contient le son du style (le caractere du style reste)',
             all(k.split(':')[1] in [n for n, _, _ in lst] or k.startswith('interface:') for k, lst in defaut.items()))


# ---------- 5. appliquer_famille ----------
def reel_essai(template='reel-impact', transition='whoosh-court'):
    return {'template': template, 'sfx': {'enabled': True, 'transition': transition, 'highlight': 'pop', 'highlightGap': 3.5,
                                          'cta': 'riser', 'start': None, 'volume': 0.6, 'extra': [{'t': 3.0, 'name': 'ding', 'manual': True}]}}


def cas_appliquer():
    data = sfxgen.familles()
    r = reel_essai()
    avant = copy.deepcopy(r['sfx'])
    res = sfxgen.appliquer_famille(r, 'tech')
    pool = r['sfx']['pool']
    tech = {s['name'] for v in next(f for f in data['familles'] if f['id'] == 'tech')['sons'].values() for s in v}
    verifier('famille choisie : reserve de cette famille, roles notes, 32 au plus', res['famille_utilisee'] == 'tech'
             and r['sfx']['famille'] == 'tech' and {p['name'] for p in pool} == tech and len(pool) <= 32
             and {p['role'] for p in pool} == set(sfxgen.ROLES) and all(set(p) == {'name', 'pic', 'gain', 'role'} for p in pool), res)
    verifier('les sons du style et les bruitages poses a la main ne changent pas',
             all(r['sfx'][k] == avant[k] for k in ('transition', 'highlight', 'cta', 'start', 'volume', 'extra')))
    verifier('varier absent tant qu\'on ne le choisit pas (absent = varier)', 'varier' not in r['sfx'] and res['varier'] is True)
    r2 = reel_essai('produit-3d')
    sfxgen.appliquer_famille(r2, 'auto', varier=False)
    verifier('auto : famille du style (Tech 3D -> tech), varier non garde', r2['sfx']['famille'] == 'auto'
             and r2['sfx']['pool'] == sfxgen.reserve('tech') and r2['sfx']['varier'] is False)
    # changement de style : le choix explicite d'avant est garde, « auto » suit le nouveau style
    r3 = reel_essai('documentaire', None)
    sfxgen.appliquer_famille(r3, avant={'famille': 'retro', 'varier': False})
    r4 = reel_essai('documentaire', None)
    sfxgen.appliquer_famille(r4, avant={'famille': 'auto'})
    verifier('changement de style : famille choisie a la main gardee, « auto » suit le style', r3['sfx']['famille'] == 'retro'
             and r3['sfx']['varier'] is False and r4['sfx']['pool'] == sfxgen.reserve('cinema') and r4['sfx']['transition'] is None)
    r5 = reel_essai('mon-style-inconnu', 'glitch')
    verifier('style perso inconnu : famille d\'apres son son de coupe', sfxgen.famille_du_style(r5) == 'glitch')
    try:
        sfxgen.appliquer_famille(reel_essai(), 'n-existe-pas')
        verifier('famille inconnue refusee en francais', False)
    except ValueError as e:
        verifier('famille inconnue refusee en francais', 'Famille de sons inconnue' in str(e), e)


# ---------- 6. ligne de commande « sons » (bac a sable) ----------
def cas_cli():
    projet = BAC / 'projet'
    (projet / 'reels').mkdir(parents=True)
    r = reel_essai('reel-karaoke', 'glitch')
    (projet / 'reels' / 'script.json').write_text(json.dumps(r, ensure_ascii=False), encoding='utf-8')
    brut = (projet / 'reels' / 'script.json').read_bytes()
    p = subprocess.run([PYTHON, '-m', 'editeur.sfxgen', 'sons', str(projet), '--reel', 'script', '--famille', 'auto', '--varier', 'non'],
                       cwd=ROOT / 'engine', capture_output=True, text=True, encoding='utf-8', timeout=120, env=ENV)
    out = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {}
    apres = json.loads((projet / 'reels' / 'script.json').read_text(encoding='utf-8'))
    versions = list((projet / 'versions' / 'script').glob('*avant sons de coupe*.json'))
    verifier('CLI sons : une ligne JSON, reel ecrit (famille auto du Karaoke = glitch, varier non)', p.returncode == 0 and out.get('ok')
             and out.get('famille_utilisee') == 'glitch' and apres['sfx']['varier'] is False and apres['sfx']['famille'] == 'auto'
             and apres['sfx']['pool'] == sfxgen.reserve('glitch'), (p.returncode, p.stdout[-300:], p.stderr[-300:]))
    verifier('CLI sons : version « avant » gardee (meme contenu que le reel d\'avant)', len(versions) == 1 and versions[0].read_bytes() == brut
             and out.get('version') == versions[0].name, [v.name for v in versions])
    avant = (projet / 'reels' / 'script.json').read_bytes()
    p = subprocess.run([PYTHON, '-m', 'editeur.sfxgen', 'sons', str(projet), '--reel', 'script', '--famille', 'disco'],
                       cwd=ROOT / 'engine', capture_output=True, text=True, encoding='utf-8', timeout=120, env=ENV)
    out = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {}
    verifier('CLI sons : famille inconnue -> code 1, message en francais, reel inchange', p.returncode == 1 and not out.get('ok')
             and 'inconnue' in out.get('erreur', '') and (projet / 'reels' / 'script.json').read_bytes() == avant, p.stdout[-200:])
    p = subprocess.run([PYTHON, '-m', 'editeur.sfxgen', 'sons', str(projet), '--reel', '../x', '--famille', 'doux'],
                       cwd=ROOT / 'engine', capture_output=True, text=True, encoding='utf-8', timeout=120, env=ENV)
    verifier('CLI sons : identifiant de version invalide refuse', p.returncode == 1 and 'invalide' in p.stdout, p.stdout[-200:])


# ---------- 7. les sons d'origine ne sont jamais reecrits ----------
def cas_origine():
    out = BAC / 'origine'
    out.mkdir(parents=True)
    faux = np.zeros((4800, 2), dtype=np.float32)
    sf.write(out / 'whoosh-court.wav', faux, 48000, subtype='PCM_16')
    brut = (out / 'whoosh-court.wav').read_bytes()
    garde = sfxgen.OUT, sfxgen.creer
    try:
        sfxgen.OUT = out
        sfxgen.creer = lambda noms=None: {}  # seulement la partie « sons d'origine » de main_creer
        sfxgen.main_creer()
    finally:
        sfxgen.OUT, sfxgen.creer = garde
    verifier('python -m editeur.sfxgen : un son d\'origine deja present n\'est jamais reecrit', (out / 'whoosh-court.wav').read_bytes() == brut)
    verifier('python -m editeur.sfxgen : un son d\'origine absent est recree', (out / 'pop.wav').is_file() and (out / 'LICENCE.txt').is_file())
    lic = (sfxgen.OUT / 'LICENCE.txt').read_text(encoding='utf-8')
    verifier('LICENCE.txt : origine de chaque copie Kenney et licence de son pack',
             all(f'{n}.wav <- assets/sfx/kenney/{rel}' in lic for n, rel in sfxgen.KENNEY.items()) and 'CC0' in lic)


if __name__ == '__main__':
    garder = '--garder' in sys.argv
    BAC.mkdir(parents=True, exist_ok=True)
    try:
        for cas in (cas_fichiers, cas_qualite, cas_banque, cas_familles, cas_appliquer, cas_cli, cas_origine):
            print(f'--- {cas.__name__}')
            try:
                cas()
            except Exception as e:  # un cas qui plante est un echec, les autres continuent
                import traceback
                traceback.print_exc()
                verifier(f'{cas.__name__} sans exception', False, repr(e))
    finally:
        if not garder:
            shutil.rmtree(BAC, ignore_errors=True)
    ko = [b for b in bilan if not b['ok']]
    print(f'\n{len(bilan) - len(ko)}/{len(bilan)} verifications reussies' + (f' ; bac garde : {BAC}' if garder else ''))
    sys.exit(1 if ko else 0)
