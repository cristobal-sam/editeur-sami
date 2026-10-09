"""Tests de l'avis de Claude (engine/editeur/critique_claude.py + section « Avis de Claude » de controle.py), SANS aucun
appel reel : faux client Anthropic, fausse cle, reglages / registre / journal / cache dans un bac a sable
(runtime/cache/tmp/<unique>) ; le vrai client du SDK est interdit pendant les tests (anthropic.Anthropic leve).

    cd D:\\Tools\\editeur_sami\\engine
    ..\\runtime\\venv\\Scripts\\python.exe ..\\docs\\claude-api\\tests\\test_critique.py [--garder]

Cas : choix des moments (nombre, temps, priorites, longs passages, extrait partiel, montage indisponible, vrai reel de
Video 1 avec le vrai pont timeline.ts), images (nombre, taille 540 x 960 / 960 x 540, JPEG, legendes), validation de la
reponse (note, verdict, temps, gravites, tri), forme de la requete (Sonnet : beta + effort ; Haiku par tache : simple),
couts inscrits au registre, cache (meme video + meme reel = gratuit ; reel change = nouvel avis ; deux demandes en meme
temps = un seul appel), plafonds (« Avis de Claude non demandé : plafond atteint »), credit epuise, Claude eteint ou sans
cle (rien n'est ajoute), refus, reponse inutilisable, fusion dans une COPIE d'un vrai rapport du controle (verdict
combine jamais « Prêt à livrer » avec un bloquant de Claude ; note locale inchangee), appel automatique apres export
seulement si critique_auto, ligne de commande (rapport retrouve, resume de la fiche, --estimer dans un vrai processus,
gratuit), cout estime par avis (16 images, Sonnet 5.5 / Haiku 4.5 / Opus 5.5), le VRAI SDK sur un faux transport local
(corps JSON reel avec les 16 images ; aucun reseau), et la cle jamais ecrite ni affichee.
--garder : ne supprime pas le bac a sable a la fin."""
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

ICI = Path(__file__).resolve().parent
ROOT = ICI.parents[2]
sys.path.insert(0, str(ROOT / 'engine'))
import anthropic  # noqa: E402
import httpx2  # noqa: E402
from PIL import Image  # noqa: E402
from editeur import claude_api as ca  # noqa: E402
from editeur import controle  # noqa: E402
from editeur import critique_claude as cc  # noqa: E402
from editeur.media import FFMPEG  # noqa: E402

FAUSSE = 'sk-ant-api03-FAUSSE-CLE-critique-0123456789abcdefXYZ'
MORCEAU = 'FAUSSE-CLE-critique'
BAC = ROOT / 'runtime/cache/tmp' / f'test-critique-claude-{uuid.uuid4().hex[:10]}'
VRAI_RAPPORT = ROOT / 'runtime/cache/controle/script1-script-qualite/export-9x16/controle.json'
VRAI_EXPORT = ROOT / 'runtime/cache/controle/script1-script-qualite/export-9x16/export.json'
ORIGINAL = {'client': ca._client, 'cle': ca._cle, 'Anthropic': anthropic.Anthropic, 'montage': cc.montage,
            'extraire': cc.extraire, 'controler': controle.controler, 'critique': cc.critique}
bilan = []
sorties = []


def verifier(nom, ok, detail=''):
    bilan.append({'test': nom, 'ok': bool(ok), 'detail': str(detail)[:300]})
    print(('OK   ' if ok else 'ECHEC') + f' {nom}' + (f' — {str(detail)[:300]}' if detail and not ok else ''))


class Interdit:
    """Le vrai client du SDK ne doit jamais etre cree pendant ces tests (aucun appel reel)."""
    def __init__(self, *a, **k):
        raise RuntimeError('client Anthropic réel interdit dans les tests')


# ---------- faux client ----------
class FauxMessages:
    def __init__(self, parent, beta):
        self.parent, self.beta = parent, beta

    def create(self, **p):
        with self.parent.verrou:
            self.parent.appels.append(('beta' if self.beta else 'messages', copy.deepcopy(p)))
            r = self.parent.reponses.pop(0) if self.parent.reponses else reponse()
        if isinstance(r, BaseException):
            raise r
        return r(p) if callable(r) else r


class FauxClient:
    def __init__(self, reponses=()):
        self.appels, self.reponses, self.verrou = [], list(reponses), threading.Lock()
        self.messages = FauxMessages(self, False)
        self.beta = SimpleNamespace(messages=FauxMessages(self, True))


USAGE = {'input_tokens': 14000, 'output_tokens': 2200, 'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 1000}
BON = {'note': 7.46, 'verdict': "Bonne pub, mais l'incrustation se voit encore à la fin. Le reste est propre.",
       'points_forts': ['Accroche directe', 'Cartes lisibles', 'Un seul bouton à la fin'],
       'problemes': [{'temps': 12.4, 'gravite': 'conseil', 'probleme': 'Cadre un peu long.', 'suggestion': 'Couper plus tôt.'},
                     {'temps': 3.2, 'gravite': 'bloquant', 'probleme': 'Mot « closer » mal écrit.', 'suggestion': 'Corriger le mot.'},
                     {'temps': 9.9, 'gravite': 'important', 'probleme': 'Halo clair autour des cheveux.', 'suggestion': 'Refaire le détourage.'}],
       'prochaine_amelioration': 'Corriger le mot mal écrit à 3 s.'}


def reponse(donnees=None, stop='end_turn', usage=None, model='claude-sonnet-5-5', texte=None):
    return SimpleNamespace(stop_reason=stop, stop_details=None, model=model, _request_id='req_faux_critique',
                           usage=usage or dict(USAGE),
                           content=[SimpleNamespace(type='text', text=texte if texte is not None else json.dumps(donnees or BON))])


def erreur(cls, code, message, genre='invalid_request_error'):
    resp = httpx2.Response(code, request=httpx2.Request('POST', 'https://api.anthropic.com/v1/messages'))
    body = {'type': 'error', 'error': {'type': genre, 'message': message}}
    return cls(f'Error code: {code} - {body}', response=resp, body=body)


def installer(client, cle=FAUSSE):
    ca._client = lambda k: client
    ca._cle = lambda: cle
    return client


def remise(reglages=None, cache=True):
    for f in (ca.REGLAGES, ca.REGISTRE, ca.JOURNAL, ca.REGISTRE.with_name(ca.REGISTRE.name + '.abime')):
        try:
            f.unlink()
        except FileNotFoundError:
            pass
    if cache:
        shutil.rmtree(cc.CACHE, ignore_errors=True)
    ca._sans_session.clear()
    ca._en_cours.clear()
    ca._clients.clear()
    if reglages:
        ca.ecrire_reglages(reglages)


# ---------- donnees de test ----------
REEL = {'id': 'v1', 'project': 'test-critique', 'title': 'Essai critique', 'template': 'produit-3d', 'width': 1080, 'height': 1920,
        'fps': 30, 'clips': [], 'ctaBlock': 's1b4',
        'design': {'mode': 'produit', 'enabled': True, 'cinematic': True},
        'style': {'uppercase': False},
        'creativePlan': {'summary': 'Répondre vite aux leads.', 'beats': [
            {'role': 'accroche', 'start': 0.1, 'end': 3.0, 'evidence': 'Plus vous attendez, plus vous perdez.'},
            {'role': 'probleme', 'start': 3.2, 'end': 9.0, 'evidence': 'Embaucher coûte cher.'},
            {'role': 'preuve', 'start': 9.2, 'end': 12.0, 'evidence': 'Cinq fois moins cher.'},
            {'role': 'cta', 'start': 15.0, 'end': 20.0, 'evidence': 'Appuyez sur le bouton.'}]},
        'graphics': [{'id': 'g1', 'kind': 'chiffre', 'at': 9.5, 'duration': 2.0, 'props': {'value': 5, 'prefix': '×', 'label': 'MOINS CHER'}},
                     {'id': 'g2', 'kind': 'motgeant', 'at': 6.0, 'duration': 1.0, 'props': {'text': 'SUGGERE'}, 'suggested': True}],
        'music': {'enabled': True, 'file': 'music/tech.ogg', 'mood': 'tech', 'volume': 0.2}}
TL = {'total': 20.0,
      'video': [{'out_start': 0.0, 'len': 5.0}, {'out_start': 5.0, 'len': 3.0}, {'out_start': 8.0, 'len': 7.0}, {'out_start': 15.0, 'len': 5.0}],
      'scenes': [{'kind': 'notification', 'at': 2.0, 'end': 4.4, 'shown': 'Réponse envoyée'},
                 {'kind': 'list', 'at': 6.0, 'end': 7.0, 'shown': 'CACHEE', 'hidden': True},
                 {'kind': 'cta', 'at': 16.0, 'end': 20.0, 'shown': 'En savoir plus'}],
      'pages': [{'start': 0.1, 'end': 1.0, 'shown': 'Plus vous attendez', 'vis': 0.9, 'cache': 0},
                {'start': 1.0, 'end': 2.2, 'shown': 'plus vous perdez', 'vis': 1.2, 'cache': 0},
                {'start': 16.0, 'end': 17.0, 'shown': 'En savoir plus', 'vis': 0, 'cache': 1.0}],
      'sfx': [{'t': 2.0, 'name': 'whoosh-court', 'kind': 'interface'}], 'blocks': [{'t': 15.0, 'block': 's1b4'}]}


def faire_video(nom, w, h, duree):
    out = BAC / nom
    subprocess.run([FFMPEG, '-v', 'error', '-y', '-f', 'lavfi', '-i', f'testsrc2=size={w}x{h}:rate=30:duration={duree}',
                    '-f', 'lavfi', '-i', f'sine=frequency=440:duration={duree}', '-c:v', 'libx264', '-preset', 'ultrafast',
                    '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', str(out)], check=True)
    return out


def rapport_copie():
    """COPIE d'un vrai rapport d'export (Video 1, 10/10 « Prêt à livrer ») ; rapport type si absent."""
    if VRAI_RAPPORT.is_file():
        return json.loads(VRAI_RAPPORT.read_text(encoding='utf-8'))
    return {'version': 2, 'reel': {'projet': 'script1', 'id': 'script', 'titre': 'Vidéo 1', 'style': 'produit-3d',
                                   'format': '1080x1920', 'duree': 71.47},
            'video': 'x.mp4', 'note': 10.0, 'verdict': 'Prêt à livrer', 'compte': {'bloquant': 0, 'important': 0, 'conseil': 0},
            'constats': [], 'mesures': {'loudness': {'I': -14.0, 'LRA': 3.1, 'TP': -1.0}}, 'duree_controle_s': 1.0}


def avis(problemes, note=7.0):
    return {'titre': 'Avis de Claude', 'ok': True, 'statut': 'ok', 'message': '', 'note': note, 'verdict': 'Correct.',
            'points_forts': ['Accroche'], 'problemes': problemes, 'prochaine_amelioration': 'Corriger.',
            'compte': {g: sum(1 for p in problemes if p['gravite'] == g) for g in cc.GRAVITES},
            'modele': 'claude-sonnet-5-5', 'nom_modele': 'Claude Sonnet 5.5', 'cout': 0.05, 'cout_avis': 0.05,
            'cout_texte': '0,05 $', 'cache': False, 'date': '2026-10-02 18:00', 'images': []}


def critiquer(video, reel=None, **kw):
    kw.setdefault('tl', TL)
    r = cc.critique(video, reel or REEL, **kw)
    sorties.append(r)
    return r


# ---------- cas ----------
def cas_moments():
    ms = cc.moments(REEL, TL, 20.0, 16)
    ts = [m['t'] for m in ms]
    verifier('moments : 16 images pour 20 s', len(ms) == 16, ts)
    verifier('moments : tries, distincts, dans la video', ts == sorted(set(ts)) and all(0 <= t < 20.0 for t in ts), ts)
    ecart = max(0.25, min(1.2, 20.0 / 16 / 2))
    verifier('moments : ecart minimal respecte', min(b - a for a, b in zip(ts, ts[1:])) >= ecart - 1 / 30 - 1e-6, ts)
    verifier('moments : temps alignes sur les images (30 i/s)', all(abs(t * 30 - round(t * 30)) < 0.31 for t in ts), ts)
    raisons = ' | '.join(m['raison'] for m in ms)
    verifier('moments : accroche (< 1 s)', any(m['t'] < 1 and 'accroche' in m['raison'] for m in ms), ms[:2])
    verifier("moments : appel a l'action (bouton a 16 s)", any(16 <= m['t'] <= 17 and "appel à l'action" in m['raison'] for m in ms))
    verifier('moments : fin de la video', any(m['t'] > 19.4 and 'fin' in m['raison'] for m in ms), ms[-1])
    verifier('moments : preuve', any('preuve' in m['raison'] for m in ms))
    verifier('moments : juste apres une coupe (0,2 s)', any(abs(m['t'] - 5.2) < 0.05 and 'coupe' in m['raison'] for m in ms), ms)
    verifier("moments : entree d'une carte", any(abs(m['t'] - 2.45) < 0.05 and 'entrée' in m['raison'] for m in ms), ms)
    verifier('moments : carte cachee et graphisme suggere ignores', 'CACHEE' not in raisons and 'SUGGERE' not in raisons, raisons)
    verifier('moments : images regulieres dans les longs passages', any('régulière' in m['raison'] for m in ms), raisons)
    for n in (1, 4, 8):
        ms_n = cc.moments(REEL, TL, 20.0, n)
        verifier(f'moments : exactement {n} si demande', len(ms_n) == n, [m['t'] for m in ms_n])
    verifier('moments : n = 4 -> les essentiels (accroche, action, fin, preuve)',
             [m['raison'].split(' ;')[0] for m in cc.moments(REEL, TL, 20.0, 4)]
             == ['accroche : début de la vidéo', 'preuve', "appel à l'action", 'fin de la vidéo'],
             [m['raison'] for m in cc.moments(REEL, TL, 20.0, 4)])
    court = cc.moments(REEL, {'total': 2.0}, 2.0, 16)
    tc = [m['t'] for m in court]
    verifier('moments : video de 2 s -> moins de 16, ecart >= 0,25 s', 1 <= len(court) < 16 and all(b - a >= 0.25 - 1 / 30 for a, b in zip(tc, tc[1:]))
             and all(0 <= t < 2 for t in tc), tc)
    part = cc.moments(REEL, TL, 8.0, 8, debut=10.0)
    verifier('moments : extrait partiel (debut 10 s) -> temps de la video', all(0 <= m['t'] < 8.0 for m in part) and len(part) == 8,
             [(m['t'], m['raison']) for m in part])
    sans = cc.moments(REEL, {}, 20.0, 16)
    verifier('moments : montage indisponible -> plan creatif + images regulieres', len(sans) == 16, [m['t'] for m in sans])


def cas_moments_vrai_reel():
    if not VRAI_EXPORT.is_file():
        verifier('vrai reel : export.json de Video 1 absent (cas saute)', True)
        return
    copie = BAC / 'export-video1.json'
    shutil.copyfile(VRAI_EXPORT, copie)
    reel = json.loads(copie.read_text(encoding='utf-8'))['reel']
    tl = cc.montage(reel)
    verifier('vrai reel : pont timeline.ts', bool(tl.get('video')) and tl.get('total', 0) > 60, list(tl)[:5])
    duree = round(tl['total'], 2)
    ms = cc.moments(reel, tl, duree, 16)
    coupes = [s['out_start'] for s in tl['video'][1:]]
    verifier('vrai reel : 16 images', len(ms) == 16, [m['t'] for m in ms])
    verifier('vrai reel : « juste apres la coupe » toujours dans les 0,6 s qui suivent une coupe',
             all(any(0 < m['t'] - c <= 0.62 for c in coupes) for m in ms if 'juste après la coupe' in m['raison']),
             [(m['t'], m['raison']) for m in ms if 'coupe' in m['raison']])
    verifier("vrai reel : appel a l'action pendant le bouton (59,8 s)", any(59.8 <= m['t'] <= 61 and "appel à l'action" in m['raison'] for m in ms))
    verifier('vrai reel : fin', ms[-1]['t'] > duree - 1)
    # description : texte exact des sous-titres et des cartes, coupes, son du rapport
    rap = rapport_copie()
    d = cc.description(reel, tl, duree, rap)
    verifier('vrai reel : description (coupes, cartes, sous-titres, son, controle local)',
             all(x in d for x in ('coupes à 12.63', 'En savoir plus', 'SOUS-TITRES', 'SON MESURÉ : -14.0 LUFS', 'CONTRÔLE LOCAL')), d[:300])
    verifier('vrai reel : description compacte (< 9000 caracteres)', len(d) < 9000, len(d))
    globals()['VRAI'] = {'reel': reel, 'tl': tl, 'duree': duree, 'description': d}


def cas_images(video, large):
    ms = cc.moments(REEL, TL, 20.0, 16)
    imgs = cc.extraire(video, [m['t'] for m in ms], 540)
    verifier('images : 16 images lues', len(imgs) == 16, len(imgs))
    tailles = {Image.open(io.BytesIO(j)).size for _, j, _ in imgs}
    verifier('images : 540 x 960 (petit cote = largeur_images)', tailles == {(540, 960)}, tailles)
    verifier('images : JPEG', all(j[:3] == b'\xff\xd8\xff' for _, j, _ in imgs))
    verifier('images : poids raisonnable (< 200 Ko chacune)', max(len(j) for _, j, _ in imgs) < 200_000, max(len(j) for _, j, _ in imgs))
    verifier('images : temps gardes', [t for t, _, _ in imgs] == [m['t'] for m in ms])
    fin = cc.extraire(video, [19.99], 540)
    verifier("images : instant au bord de la fin -> image lue quand meme", len(fin) == 1, fin and fin[0][0])
    h = cc.extraire(large, [1.0, 3.0], 540)
    verifier('images : video 16:9 -> 960 x 540', [x[2] for x in h] == [(960, 540)] * 2 and Image.open(io.BytesIO(h[0][1])).size == (960, 540))
    verifier('images : largeur 720 -> 720 x 1280', cc.extraire(video, [1.0], 720)[0][2] == (720, 1280))
    blocs = cc.blocs_images(imgs, {m['t']: m['raison'] for m in ms})
    verifier('images : legendes « Image i/16 — t s : raison »', blocs[0][0].startswith('Image 1/16 — 0.40 s : accroche'), blocs[0][0])
    b = blocs[0][1]
    verifier('images : bloc image base64 JPEG', b['type'] == 'image' and b['source']['media_type'] == 'image/jpeg'
             and b['source']['type'] == 'base64' and len(b['source']['data']) > 1000)
    if VRAI_EXPORT.is_file():
        vraie = json.loads(VRAI_EXPORT.read_text(encoding='utf-8')).get('out')
        if vraie and Path(vraie).is_file():  # lecture seule du vrai export
            r = cc.extraire(vraie, [0.4, 60.43], 540)
            verifier('images : vrai export de Video 1 (lecture seule) -> 540 x 960', [x[2] for x in r] == [(540, 960)] * 2)


def cas_schema():
    def objets(s, chemin='racine'):
        if s.get('type') == 'object':
            yield chemin, s
            for k, v in s['properties'].items():
                yield from objets(v, f'{chemin}.{k}')
        elif s.get('type') == 'array':
            yield from objets(s['items'], chemin + '[]')
    ok = all(o.get('additionalProperties') is False and sorted(o['required']) == sorted(o['properties']) for _, o in objets(cc.SCHEMA))
    verifier('schema : objets fermes, tous les champs requis', ok)
    verifier('schema : pas de contrainte non prise en charge (minimum, maxLength...)',
             not any(k in json.dumps(cc.SCHEMA) for k in ('minimum', 'maximum', 'minLength', 'maxLength', 'maxItems')))
    a, ec = cc.valider(copy.deepcopy(BON), 20.0)
    verifier('valider : note a une decimale (7,46 -> 7,5)', a['note'] == 7.5, a['note'])
    verifier('valider : verdict d\'une seule phrase', a['verdict'] == "Bonne pub, mais l'incrustation se voit encore à la fin.", a['verdict'])
    verifier('valider : problemes tries (bloquant, important, conseil)', [p['gravite'] for p in a['problemes']] == ['bloquant', 'important', 'conseil'])
    verifier('valider : compte par gravite', a['compte'] == {'bloquant': 1, 'important': 1, 'conseil': 1}, a['compte'])
    for note, attendu in ((11, 10.0), (-2, 0.0), ('8,5', 8.5), ('7/10', 7.0)):
        verifier(f'valider : note {note!r} -> {attendu}', cc.valider({**BON, 'note': note}, 20)[0]['note'] == attendu)
    for mauvais, nom in (({**BON, 'note': 'bien'}, 'note illisible'), ({k: v for k, v in BON.items() if k != 'verdict'}, 'verdict manquant'),
                         ({**BON, 'verdict': '   '}, 'verdict vide'), ('pas un objet', 'pas un objet')):
        try:
            cc.valider(mauvais, 20)
            verifier(f'valider : refus ({nom})', False)
        except ValueError as e:
            verifier(f'valider : refus ({nom})', bool(str(e)), e)
    ps = [{'temps': 25.0, 'gravite': 'important', 'probleme': 'hors video', 'suggestion': ''},
          {'temps': 20.3, 'gravite': 'conseil', 'probleme': 'presque la fin', 'suggestion': ''},
          {'temps': '0:12,5', 'gravite': 'critique', 'probleme': 'gravite inconnue', 'suggestion': ''},
          {'temps': -3, 'gravite': 'conseil', 'probleme': 'negatif', 'suggestion': ''},
          {'temps': 2, 'gravite': 'conseil', 'probleme': '   ', 'suggestion': 'vide'}]
    a, ec = cc.valider({**BON, 'problemes': ps}, 20.0)
    par = {p['probleme']: p for p in a['problemes']}
    verifier('valider : temps hors de la video -> None', par['hors video']['temps'] is None and par['negatif']['temps'] is None)
    verifier('valider : temps a 0,3 s apres la fin -> borne a la fin', par['presque la fin']['temps'] == 20.0)
    verifier('valider : « 0:12,5 » -> 12,5 s ; gravite inconnue -> conseil', par['gravite inconnue']['temps'] == 12.5
             and par['gravite inconnue']['gravite'] == 'conseil')
    verifier('valider : probleme sans texte ecarte', all(p['suggestion'] != 'vide' for p in a['problemes']) and len(a['problemes']) == 4
             and ec == 1, (ec, a['problemes']))
    beaucoup = [{'temps': i, 'gravite': 'conseil', 'probleme': f'p{i}', 'suggestion': ''} for i in range(15)]
    a, ec = cc.valider({**BON, 'problemes': beaucoup}, 20.0)
    verifier('valider : 12 problemes au plus', len(a['problemes']) == 12 and ec == 3, (len(a['problemes']), ec))


def cas_requete(video):
    remise()
    fc = installer(FauxClient([reponse()]))
    r = critiquer(video)
    verifier('critique : avis ok', r['ok'] and r['statut'] == 'ok' and r['note'] == 7.5 and r['message'] == '', r.get('message'))
    verifier('critique : un seul appel', len(fc.appels) == 1, len(fc.appels))
    voie, p = fc.appels[0]
    verifier('requete Sonnet : beta + repli serveur', voie == 'beta' and p['betas'] == [ca.BETA_REPLI] and p['fallbacks'] == 'default')
    verifier('requete : modele de la tache critique (Sonnet par defaut)', p['model'] == 'claude-sonnet-5-5' == r['modele'])
    verifier('requete : effort explicite (medium) + sortie structuree = SCHEMA', p['output_config'] == {'format': {'type': 'json_schema', 'schema': cc.SCHEMA},
                                                                                                        'effort': 'medium'}, p['output_config'])
    verifier('requete : ni thinking, ni tool_choice, ni pre-remplissage', 'thinking' not in p and 'tool_choice' not in p
             and len(p['messages']) == 1 and p['messages'][0]['role'] == 'user')
    verifier('requete : consigne systeme stable en cache', p['system'] == [{'type': 'text', 'text': cc.SYSTEME, 'cache_control': {'type': 'ephemeral'}}])
    contenu = p['messages'][0]['content']
    imgs = [b for b in contenu if b['type'] == 'image']
    verifier('requete : 16 images JPEG', len(imgs) == 16 and all(b['source']['media_type'] == 'image/jpeg' for b in imgs), len(imgs))
    verifier('requete : chaque image precedee de sa legende, texte du montage a la fin',
             all(contenu[2 * i]['type'] == 'text' and contenu[2 * i]['text'].startswith(f'Image {i + 1}/16') and contenu[2 * i + 1]['type'] == 'image'
                 for i in range(16)) and contenu[-1]['type'] == 'text' and contenu[-1]['text'].startswith(cc.CONSIGNE))
    verifier('requete : description (sous-titres exacts, cartes, son)', all(x in contenu[-1]['text'] for x in ('Plus vous attendez', 'notification « Réponse envoyée »', 'MUSIQUE : oui')))
    verifier('requete : 8000 jetons de sortie au plus', p['max_tokens'] == cc.SORTIE == 8000)
    cout = ca.cout(USAGE, 'claude-sonnet-5-5')
    verifier('critique : cout reel = jetons x tarif Sonnet', abs(r['cout'] - cout) < 1e-9 and r['cout_avis'] == r['cout'], (r['cout'], cout))
    verifier('critique : depense inscrite pour la video (projet/version)', abs(ca.depense_video('test-critique/v1') - cout) < 1e-9)
    j = [json.loads(x) for x in ca.JOURNAL.read_text(encoding='utf-8').splitlines()]
    verifier('journal : tache « critique », 16 images, sans invite', j[-1]['tache'] == 'critique' and j[-1]['jetons']['images'] == 16
             and 'Plus vous attendez' not in json.dumps(j))
    verifier('critique : images [{t, raison}] gardees', len(r['images']) == 16 and r['images'][0]['raison'].startswith('accroche'))
    # modele par tache : Haiku -> requete simple
    remise({'modeles_taches': {'critique': 'claude-haiku-4-5'}})
    fc = installer(FauxClient([reponse(model='claude-haiku-4-5')]))
    r = critiquer(video)
    voie, p = fc.appels[0]
    verifier('modele par tache : Haiku 4.5 -> messages.create simple (ni effort, ni beta)', r['ok'] and voie == 'messages' and p['model'] == 'claude-haiku-4-5'
             and 'effort' not in p['output_config'] and 'betas' not in p and r['nom_modele'] == 'Claude Haiku 4.5')


def cas_cache(video):
    remise()
    fc = installer(FauxClient([reponse(), reponse(), reponse()]))
    r1 = critiquer(video)
    r2 = critiquer(video)
    verifier('cache : meme video + meme reel -> aucun nouvel appel, gratuit', len(fc.appels) == 1 and r2['ok'] and r2['cache']
             and r2['cout'] == 0.0 and r2['cout_avis'] == r1['cout'] and r2['note'] == r1['note'], (len(fc.appels), r2.get('cache')))
    verifier('cache : depense inchangee', abs(ca.depense_video('test-critique/v1') - r1['cout']) < 1e-9)
    r3 = critiquer(video, {**REEL, 'controle': {'note': 3}})
    verifier('cache : champ « controle » du reel sans effet (meme signature)', r3['cache'] and len(fc.appels) == 1)
    r4 = critiquer(video, {**REEL, 'title': 'Autre titre'})
    verifier('cache : reel change -> nouvel avis', not r4['cache'] and len(fc.appels) == 2)
    r5 = critiquer(video, forcer=True)
    verifier('cache : --refaire (forcer) -> nouvel avis payant', not r5['cache'] and len(fc.appels) == 3 and r5['cout'] > 0)
    # deux demandes en meme temps pour la meme video : un seul appel
    remise()

    def lente(p):
        time.sleep(1.5)
        return reponse()
    fc = installer(FauxClient([lente, lente]))
    res = []
    fils = [threading.Thread(target=lambda: res.append(critiquer(video))) for _ in range(2)]
    for f in fils:
        f.start()
    for f in fils:
        f.join()
    verifier('cache : deux demandes en meme temps -> un seul appel, deux avis', len(fc.appels) == 1 and all(x['ok'] for x in res)
             and sorted(x['cache'] for x in res) == [False, True], (len(fc.appels), [x.get('cache') for x in res]))
    verifier('cache : plus de fichier « en cours » apres', not list(cc.CACHE.glob('*.en-cours')))


def cas_budget(video):
    remise({'plafond_video': 0.01})
    fc = installer(FauxClient([reponse()]))
    r = critiquer(video)
    verifier('plafond par video -> « Avis de Claude non demandé : plafond atteint »', not r['ok'] and r['statut'] == 'plafond'
             and r['message'] == 'Avis de Claude non demandé : plafond atteint' and 'Plafond par vidéo' in r['detail'], r.get('message'))
    verifier('plafond : aucun appel envoye', not fc.appels)
    remise({'plafond_jour': 0.15})
    fc = installer(FauxClient([reponse(usage={**USAGE, 'output_tokens': 15000})]))
    r = critiquer(video, {**REEL, 'title': 'jour 1'})  # ~0,18 $ depenses : plafond du jour (0,15 $) atteint
    verifier('plafond du jour : premier avis paye (~0,18 $)', r['ok'] and r['cout'] > 0.15, r.get('cout'))
    vus = []
    cc.extraire = lambda *a, **k: vus.append(1) or ORIGINAL['extraire'](*a, **k)
    try:
        r = critiquer(video, {**REEL, 'title': 'jour 2'})
    finally:
        cc.extraire = ORIGINAL['extraire']
    verifier('plafond du jour deja atteint -> refuse avant de preparer les images', r['statut'] == 'plafond' and not vus and len(fc.appels) == 1
             and r['message'] == cc.NON_DEMANDE and 'Plafond du jour' in r['detail'], (r.get('detail'), vus))
    remise({'credit_depart': 0.0})
    fc = installer(FauxClient([reponse()]))
    r = critiquer(video)
    verifier('credit estime epuise -> plafond atteint, aucun appel', r['statut'] == 'plafond' and r['message'] == cc.NON_DEMANDE and not fc.appels, r.get('detail'))
    remise()
    fc = installer(FauxClient([erreur(anthropic.BadRequestError, 400, 'Your credit balance is too low to access the Anthropic API.')]))
    r = critiquer(video)
    verifier('credit Anthropic epuise -> « Avis de Claude non demandé : crédit Anthropic épuisé »', r['statut'] == 'credit'
             and r['message'] == cc.CREDIT and r['detail'] == ca.CREDIT_EPUISE, r.get('message'))
    r = critiquer(video)
    verifier('credit epuise : pause de 10 min, plus aucun appel', r['statut'] == 'credit' and len(fc.appels) == 1)
    # un avis deja paye reste gratuit meme quand le plafond est atteint
    remise()
    fc = installer(FauxClient([reponse()]))
    critiquer(video)
    remise({'plafond_jour': 0.0}, cache=False)
    r = critiquer(video)
    verifier('plafond atteint mais avis deja paye -> avis du cache (gratuit)', r['ok'] and r['cache'] and len(fc.appels) == 1)


def cas_eteint(video):
    remise({'actif': False})
    fc = installer(FauxClient([reponse()]))
    r = critiquer(video)
    verifier('Claude eteint -> statut « eteint », aucun message, aucun appel', r['statut'] == 'eteint' and not r['ok'] and r['message'] == ''
             and not fc.appels)
    rap = rapport_copie()
    avant = copy.deepcopy(rap)
    controle.ajouter_avis_claude(rap, r)
    verifier('Claude eteint -> rien ajoute au rapport', rap == avant)
    controle.ajouter_avis_claude(rap, None)
    verifier('avis None -> rien ajoute au rapport', rap == avant)
    remise()
    fc = installer(FauxClient([reponse()]), cle=None)
    r = critiquer(video)
    verifier('pas de cle -> statut « eteint », aucun appel', r['statut'] == 'eteint' and not fc.appels)


def cas_erreurs(video):
    remise()
    fc = installer(FauxClient([reponse(stop='refusal')]))
    r = critiquer(video)
    verifier('refus de Claude -> « Avis de Claude impossible : … »', r['statut'] == 'erreur' and r['message'].startswith(cc.IMPOSSIBLE)
             and 'refusé' in r['message'], r.get('message'))
    fc = installer(FauxClient([reponse(texte='{"note": "super", "verdict": "x", "points_forts": [], "problemes": [], "prochaine_amelioration": ""}')]))
    r = critiquer(video)
    verifier('reponse inutilisable -> impossible, avec son cout', r['statut'] == 'erreur' and 'inutilisable' in r['message'] and '$' in r['message']
             and r['cout'] > 0, r.get('message'))
    verifier('reponse inutilisable : rien en cache', not list(cc.CACHE.glob('*.json')))
    r = critiquer(BAC / 'absente.mp4')
    verifier('video introuvable -> impossible', r['statut'] == 'erreur' and 'introuvable' in r['message'])
    fc = installer(FauxClient([erreur(anthropic.AuthenticationError, 401, 'invalid x-api-key', 'authentication_error')]))
    r = critiquer(video)
    verifier('cle refusee -> impossible (phrase du noyau)', r['statut'] == 'erreur' and 'Clé refusée' in r['message'])
    cc.extraire = lambda *a, **k: (_ for _ in ()).throw(RuntimeError(f'panne {FAUSSE}'))
    try:
        r = critiquer(video, {**REEL, 'title': 'panne'})
    finally:
        cc.extraire = ORIGINAL['extraire']
    verifier('panne imprevue -> pas d\'exception, cle masquee', r['statut'] == 'erreur' and MORCEAU not in json.dumps(r), r.get('message'))
    verifier('panne imprevue : verrou rendu', not list(cc.CACHE.glob('*.en-cours')))


def cas_fusion():
    base = rapport_copie()
    verifier('rapport copie : verdict local « Prêt à livrer »', base['verdict'] == 'Prêt à livrer', base['verdict'])
    note0 = base['note']
    rap = copy.deepcopy(base)
    a = avis([{'temps': 3.2, 'gravite': 'bloquant', 'probleme': 'Faute à l’écran.', 'suggestion': 'Corriger.'},
              {'temps': 9.9, 'gravite': 'conseil', 'probleme': 'Halo.', 'suggestion': 'Adoucir.'}], note=6.4)
    controle.ajouter_avis_claude(rap, a)
    verifier('fusion : section « claude » a part', rap['claude']['titre'] == 'Avis de Claude' and rap['claude']['note'] == 6.4)
    verifier('fusion : note locale inchangee', rap['note'] == note0 and rap['constats'] == base['constats'])
    verifier('fusion : bloquant de Claude -> verdict combine « À corriger avant de livrer »', rap['verdict'] == 'À corriger avant de livrer'
             and rap['verdict_local'] == 'Prêt à livrer', (rap['verdict'], rap.get('verdict_local')))
    res = controle.resume(rap)
    verifier('fusion : resume (fiche Revision) avec avis compact + verdict_local', res['claude']['note'] == 6.4 and res['verdict_local'] == 'Prêt à livrer'
             and res['claude']['problemes'][0]['gravite'] == 'bloquant' and res['verdict'] == 'À corriger avant de livrer')
    txt = controle.texte_rapport(rap)
    verifier('fusion : texte du rapport (« Avis de Claude », verdict local rappele)', 'Avis de Claude (Claude Sonnet 5.5, 0,05 $) : 6,4/10' in txt
             and '(contrôle local seul : Prêt à livrer)' in txt and '[BLOQUANT] 0:03,2  Faute' in txt, txt[-500:])
    sortie = BAC / 'rapport-fusion'
    controle.ecrire_rapport(rap, sortie)
    relu = json.loads((sortie / 'controle.json').read_text(encoding='utf-8'))
    verifier('fusion : controle.json + controle.txt ecrits (copie)', relu['claude']['note'] == 6.4 and 'Avis de Claude' in (sortie / 'controle.txt').read_text(encoding='utf-8'))
    controle.ajouter_avis_claude(rap, avis([{'temps': 1.0, 'gravite': 'conseil', 'probleme': 'Petit détail.', 'suggestion': ''}]))
    verifier('fusion : nouvel avis sans bloquant -> verdict local revient, sans cumul', rap['verdict'] == 'Prêt à livrer'
             and rap['verdict_local'] == 'Prêt à livrer' and rap['claude']['compte']['bloquant'] == 0)
    jamais = True
    for local in ('Prêt à livrer', 'Livrable, à améliorer', 'À corriger avant de livrer', 'Pas livrable en l’état'):
        r = {**copy.deepcopy(base), 'verdict': local}
        controle.ajouter_avis_claude(r, a)
        jamais &= r['verdict'] not in ('Prêt à livrer', 'Livrable, à améliorer')
        if local in ('À corriger avant de livrer', 'Pas livrable en l’état'):
            jamais &= r['verdict'] == local
    verifier('fusion : jamais « Prêt à livrer » ni « Livrable » avec un bloquant de Claude ; les verdicts plus durs restent', jamais)
    r = {**copy.deepcopy(base), 'verdict': 'Prêt à livrer'}
    controle.ajouter_avis_claude(r, avis([{'temps': 1.0, 'gravite': 'important', 'probleme': 'Moyen.', 'suggestion': ''}]))
    verifier('fusion : important de Claude seul -> verdict local garde', r['verdict'] == 'Prêt à livrer')
    r = copy.deepcopy(base)
    refus = {'titre': 'Avis de Claude', 'ok': False, 'statut': 'plafond', 'message': cc.NON_DEMANDE, 'detail': 'Plafond du jour atteint (…)'}
    controle.ajouter_avis_claude(r, refus)
    txt = controle.texte_rapport(r)
    verifier('fusion : plafond -> section avec « Avis de Claude non demandé : plafond atteint », verdict et note inchanges',
             r['claude']['message'] == cc.NON_DEMANDE and r['verdict'] == base['verdict'] and r['note'] == note0
             and 'Avis de Claude non demandé : plafond atteint' in txt and controle.resume(r)['claude']['message'] == cc.NON_DEMANDE)


def cas_auto(video):
    """controle.main : avis de Claude apres un export complet SEULEMENT si critique_auto (controler et critique simules)."""
    job = BAC / 'job-export.json'
    job.write_text(json.dumps({'reel': REEL, 'out': str(video)}), encoding='utf-8')
    simple = BAC / 'reel-seul.json'
    simple.write_text(json.dumps({**REEL, 'clips': []}), encoding='utf-8')
    appels = []
    controle.controler = lambda reel, **k: {**copy.deepcopy(rapport_copie()), 'video': str(k.get('video'))}
    cc.critique = lambda v, reel, **k: appels.append((v, k.get('rapport') is not None)) or avis(
        [{'temps': 2.0, 'gravite': 'bloquant', 'probleme': 'Texte de travail.', 'suggestion': 'Le retirer.'}])

    def lancer(args):
        with redirect_stdout(io.StringIO()):
            return controle.main(args)
    try:
        for auto in (False, True):
            remise({'critique_auto': auto})
            sortie = BAC / f'auto-{auto}'
            r = lancer([str(job), '--video', str(video), '--sortie', str(sortie)])
            ecrit = json.loads((sortie / 'controle.json').read_text(encoding='utf-8'))
            if not auto:
                verifier('auto : critique_auto faux (defaut) -> aucun avis demande', not appels and 'claude' not in r and 'claude' not in ecrit)
            else:
                verifier('auto : critique_auto vrai + export complet -> avis demande une fois (avec le rapport)', appels == [(str(video), True)], appels)
                verifier('auto : avis range dans controle.json, verdict combine', ecrit['claude']['note'] == 7.0 and ecrit['verdict'] == 'À corriger avant de livrer'
                         and ecrit['verdict_local'] == 'Prêt à livrer' and 'Avis de Claude' in (sortie / 'controle.txt').read_text(encoding='utf-8'))
        appels.clear()
        lancer([str(job), '--video', str(video), '--debut', '2', '--sortie', str(BAC / 'auto-partiel')])
        verifier('auto : apercu partiel (debut 2 s) -> pas d\'avis', not appels)
        lancer([str(simple), '--video', str(video), '--sortie', str(BAC / 'auto-hors-livraisons')])
        verifier('auto : video hors livraisons sans job d\'export -> pas d\'avis', not appels)
        remise({'critique_auto': False})
        verifier('auto : reglage critique_auto faux par defaut', ca.DEFAUTS['critique_auto'] is False)
    finally:
        controle.controler, cc.critique = ORIGINAL['controler'], ORIGINAL['critique']


def cas_cli(video):
    job = BAC / 'job-cli.json'
    job.write_text(json.dumps({'reel': REEL, 'out': str(video)}), encoding='utf-8')
    rap_dir = BAC / 'rapport-cli'
    controle.ecrire_rapport(rapport_copie(), rap_dir)
    cc.montage = lambda reel: copy.deepcopy(TL)
    try:
        remise()
        fc = installer(FauxClient([reponse()]))
        out = io.StringIO()
        with redirect_stdout(out):
            cc.main([str(video), '--reel', str(job), '--rapport', str(rap_dir), '--json'])
        ligne = json.loads(out.getvalue().strip().splitlines()[-1])
        sorties.append(ligne)
        relu = json.loads((rap_dir / 'controle.json').read_text(encoding='utf-8'))
        verifier('CLI : avis en une ligne JSON + rapport mis a jour', ligne['ok'] and ligne['rapport'].endswith('controle.json')
                 and relu['claude']['note'] == 7.5 and relu['verdict'] == 'À corriger avant de livrer' and len(fc.appels) == 1)
        verifier('CLI : « resume » (fiche de la Revision) avec l\'avis et le verdict combine', ligne['resume']['claude']['note'] == 7.5
                 and ligne['resume']['verdict'] == 'À corriger avant de livrer' and ligne['resume']['verdict_local'] == 'Prêt à livrer')
        out = io.StringIO()
        with redirect_stdout(out):
            cc.main([str(video), '--reel', str(job)])
        verifier('CLI : deuxieme fois -> deja paye (texte lisible), aucun appel', 'déjà payé' in out.getvalue() and len(fc.appels) == 1, out.getvalue()[:200])
        out = io.StringIO()
        with redirect_stdout(out):
            cc.main([str(video), '--reel', str(job), '--estimer', '--json', '--images', '8'])
        e = json.loads(out.getvalue().strip().splitlines()[-1])
        verifier('CLI --estimer : aucun appel, 8 images, cout par modele', len(fc.appels) == 1 and len(e['images']) == 8
                 and set(e['modeles']) == set(ca.MODELES) and e['estimation']['modele'] == 'claude-sonnet-5-5')
        remise({'plafond_video': 0.01})
        out = io.StringIO()
        with redirect_stdout(out):
            cc.main([str(video), '--reel', str(job), '--rapport', str(rap_dir), '--refaire'])
        relu = json.loads((rap_dir / 'controle.json').read_text(encoding='utf-8'))
        verifier('CLI : plafond -> message clair, rapport : section « non demandé », verdict local', 'Avis de Claude non demandé : plafond atteint' in out.getvalue()
                 and relu['claude']['statut'] == 'plafond' and relu['verdict'] == relu['verdict_local'] == 'Prêt à livrer', out.getvalue()[:200])
    finally:
        cc.montage = ORIGINAL['montage']
    verifier('CLI : pas de rapport d\'export pour ce reel -> rien a ranger', cc.rapport_export(REEL, video) is None)
    if VRAI_EXPORT.is_file():  # lecture seule : retrouve le rapport d'export de la vraie Video 1 par son fichier
        d = json.loads(VRAI_EXPORT.read_text(encoding='utf-8'))
        f = cc.rapport_export(d['reel'], d.get('out') or '')
        verifier('CLI : rapport d\'export retrouve par la video (vraie Video 1, lecture seule)', f is not None and f.resolve() == VRAI_RAPPORT.resolve(), f)
        verifier('CLI : autre video du meme reel -> pas ce rapport', cc.rapport_export(d['reel'], str(video)) is None)
    # vrai processus « python -m editeur.critique_claude --estimer » : gratuit (aucun appel), fausse cle par prudence
    env = {**os.environ, 'ANTHROPIC_API_KEY': FAUSSE}
    p = subprocess.run([sys.executable, '-m', 'editeur.critique_claude', str(video), '--reel', str(job), '--estimer', '--json', '--images', '4'],
                       cwd=str(ROOT / 'engine'), capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, timeout=300)
    try:
        e = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        e = {}
    sorties.append(p.stdout + p.stderr)
    verifier('CLI reelle --estimer (processus a part) : code 0, 4 images, estimation', p.returncode == 0 and len(e.get('images') or []) == 4
             and e.get('estimation', {}).get('typique', 0) > 0, (p.returncode, p.stderr[-300:]))


def cas_couts():
    """Cout estime d'un avis avec 16 images (description reelle de Video 1 si disponible)."""
    remise()
    contenu = cc.CONSIGNE + '\n\n' + (globals().get('VRAI') or {}).get('description', 'x' * 6000)
    tailles = [cc.taille(1080, 1920, 540)] * 16
    lignes = []
    for m in ('claude-sonnet-5-5', 'claude-haiku-4-5', 'claude-opus-5-5'):
        e = cc.estimation(16, m, contenu, tailles)
        lignes.append(e)
        print(f"      {e['nom']} : typique {e['typique']:.4f} $, au plus {e['maximum']:.4f} $ "
              f"(jetons : systeme {e['jetons']['systeme']}, texte {e['jetons']['texte']}, images {e['jetons']['images']}, sortie {e['jetons']['sortie']})")
    s, h, o = lignes
    verifier('cout : 16 images de 540 x 960 = 11 200 jetons', s['jetons']['images'] == 16 * 700, s['jetons']['images'])
    verifier('cout : Haiku moins cher que Sonnet, Sonnet moins cher qu\'Opus', h['typique'] < s['typique'] < o['typique'])
    verifier('cout : estimation haute Sonnet sous le plafond par video (0,25 $)', s['maximum'] < ca.DEFAUTS['plafond_video'], s['maximum'])
    verifier('cout : Opus au plus sous le plafond par video', o['maximum'] < ca.DEFAUTS['plafond_video'], o['maximum'])
    globals()['COUTS'] = {x['modele']: {'typique': x['typique'], 'maximum': x['maximum']} for x in lignes}


def cas_sdk_local(video):
    """Le VRAI SDK anthropic sur un faux transport local (aucun reseau, rien de facture) : corps JSON reel de l'avis
    (16 images base64 avant le texte, sortie structuree, en-tete beta du repli) et lecture de la vraie classe de reponse."""
    vus = []

    def transport(req):
        vus.append({'hote': req.url.host, 'beta': req.headers.get('anthropic-beta'), 'corps': json.loads(req.content.decode('utf-8'))})
        return httpx2.Response(200, headers={'request-id': 'req_mock_critique'}, json={
            'id': 'msg_c1', 'type': 'message', 'role': 'assistant', 'model': 'claude-sonnet-5-5',
            'content': [{'type': 'text', 'text': json.dumps(BON)}], 'stop_reason': 'end_turn', 'stop_sequence': None,
            'usage': {'input_tokens': 14500, 'output_tokens': 2100, 'cache_creation_input_tokens': 1100, 'cache_read_input_tokens': 0}})
    anthropic.Anthropic = ORIGINAL['Anthropic']
    ca._client, ca._TRANSPORT_TEST, ca._cle = ORIGINAL['client'], httpx2.MockTransport(transport), (lambda: FAUSSE)
    try:
        remise()
        r = critiquer(video)
        c = vus[-1]['corps'] if vus else {}
        blocs = (c.get('messages') or [{}])[0].get('content') or []
        verifier('SDK local : avis lu sur la vraie reponse (request_id, cout)', r['ok'] and r['request_id'] == 'req_mock_critique'
                 and abs(r['cout'] - (14500 * 2 + 1100 * 2.5 + 2100 * 10) / 1e6) < 1e-12, (r.get('message'), r.get('cout')))
        verifier('SDK local : un seul envoi, vers api.anthropic.com (faux transport)', len(vus) == 1 and vus[0]['hote'] == 'api.anthropic.com')
        verifier('SDK local : en-tete beta du repli, effort, schema, cache systeme', vus[-1]['beta'] == ca.BETA_REPLI and c.get('fallbacks') == 'default'
                 and c['output_config'] == {'format': {'type': 'json_schema', 'schema': cc.SCHEMA}, 'effort': 'medium'}
                 and c['system'][0]['cache_control'] == {'type': 'ephemeral'} and 'thinking' not in c and 'betas' not in c)
        verifier('SDK local : 16 images base64 JPEG avec legende, texte du montage en dernier',
                 sum(1 for b in blocs if b.get('type') == 'image' and b['source']['media_type'] == 'image/jpeg') == 16
                 and blocs[0]['type'] == 'text' and blocs[1]['type'] == 'image' and blocs[-1]['text'].startswith(cc.CONSIGNE))
        verifier('SDK local : la cle ne part pas dans le corps', MORCEAU not in json.dumps(c))
    finally:
        anthropic.Anthropic = Interdit
        ca._client, ca._TRANSPORT_TEST = ORIGINAL['client'], None
        ca._clients.clear()


def cas_cle_nulle_part():
    trouves = []
    for f in BAC.rglob('*'):
        if f.is_file() and f.suffix in ('.json', '.jsonl', '.txt', '.lock', '.en-cours'):
            if MORCEAU in f.read_text(encoding='utf-8', errors='replace'):
                trouves.append(str(f.relative_to(BAC)))
    verifier('la cle n\'est dans AUCUN fichier du bac a sable', not trouves, trouves)
    verifier('la cle n\'est dans AUCUNE sortie', MORCEAU not in json.dumps(sorties, ensure_ascii=False, default=str))


if __name__ == '__main__':
    garder = '--garder' in sys.argv
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    BAC.mkdir(parents=True, exist_ok=True)
    os.environ['ANTHROPIC_API_KEY'] = FAUSSE  # le vrai chargeur ne remplace jamais une variable deja definie
    os.environ.pop('ANTHROPIC_WORKSPACE_ID', None)
    anthropic.Anthropic = Interdit  # aucun vrai client : un oubli de faux client ferait echouer le test, sans reseau
    ca.REGLAGES = BAC / 'styles/claude.json'
    ca.REGISTRE = BAC / 'projects/_claude.json'
    ca.JOURNAL = BAC / 'runtime/cache/claude-appels.jsonl'
    ca.VERROU = BAC / 'runtime/cache/claude.lock'
    cc.CACHE = BAC / 'runtime/cache/claude-critiques'
    debut = time.time()
    try:
        video = faire_video('essai-9x16.mp4', 1080, 1920, 20)
        large = faire_video('essai-16x9.mp4', 1920, 1080, 6)
        etapes = [cas_moments, cas_moments_vrai_reel, lambda: cas_images(video, large), cas_schema, lambda: cas_requete(video),
                  lambda: cas_cache(video), lambda: cas_budget(video), lambda: cas_eteint(video), lambda: cas_erreurs(video),
                  cas_fusion, lambda: cas_auto(video), lambda: cas_cli(video), cas_couts, lambda: cas_sdk_local(video),
                  cas_cle_nulle_part]
        for cas in etapes:
            try:
                cas()
            except Exception:  # un cas qui plante ne doit pas cacher les autres
                import traceback
                verifier(f'{getattr(cas, "__name__", "cas")} (plantage)', False, traceback.format_exc()[-700:])
    finally:
        ca._client, ca._cle = ORIGINAL['client'], ORIGINAL['cle']
        anthropic.Anthropic = ORIGINAL['Anthropic']
        cc.montage, cc.extraire, cc.critique, controle.controler = (ORIGINAL['montage'], ORIGINAL['extraire'], ORIGINAL['critique'],
                                                                    ORIGINAL['controler'])
        if not garder:
            shutil.rmtree(BAC, ignore_errors=True)
    ko = [b for b in bilan if not b['ok']]
    if globals().get('COUTS'):
        print('\nCoût estimé par avis (16 images) : ' + ' ; '.join(f"{ca.NOMS[m]} ≈ {v['typique']:.3f} $ (au plus {v['maximum']:.3f} $)"
                                                               for m, v in COUTS.items()))
    print(f'\n{len(bilan) - len(ko)}/{len(bilan)} vérifications réussies en {time.time() - debut:.1f} s'
          + (f' — bac à sable gardé : {BAC}' if garder else ''))
    sys.exit(1 if ko else 0)
