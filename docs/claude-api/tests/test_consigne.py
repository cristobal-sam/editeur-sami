"""Tests de la boite « Dis a l'IA ce que tu veux changer » (engine/editeur/consigne.py + « python -m editeur.consigne »),
SANS aucun appel reel : faux client Anthropic (claude_api._client), fausse cle, Qwen simule (llm.available / llm.session /
consigne._qwen_requete), detourage simule ; reglages / registre / journal de Claude et COPIE de projects/script1 dans un
bac a sable (runtime/cache/tmp/<unique>), efface a la fin.

    cd D:\\Tools\\editeur_sami\\engine
    ..\\runtime\\venv\\Scripts\\python.exe ..\\docs\\claude-api\\tests\\test_consigne.py [--garder]

Cas : 12+ demandes realistes (quebecois, « ici », ambigue -> question, hors liste -> refus + note, element verrouille ->
refuse, suite « non, l'autre »), chaque operation verifiee et appliquee, « avant » remis a l'octet pres, historique
reel["consignes"], forme de la requete a Claude (Sonnet, effort, schema strict, cache), Claude eteint -> IA locale,
IA locale en panne -> regles, --simuler, retouche concurrente, ligne de commande, schema conforme a la sortie structuree,
taille de l'invite et cout par demande (Sonnet 5.5 / Haiku 4.5), rien d'exporte, cle jamais ecrite ; verrou jamais leve
par l'IA sans qu'on le demande, retouche + « refais ce passage » dans la meme demande, casse des valeurs de la sortie
structuree, famille de sons gardee au changement de style (sfxgen), regles simples (moment ecrit, « baisse-la »).
--garder : ne supprime pas le bac a sable a la fin."""
import contextlib
import copy
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

for _flux in (sys.stdout, sys.stderr):  # sortie redirigee (fichier, tube) sous Windows : cp1252 ne sait pas ecrire 🔒 ni ≤
    try:
        _flux.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass
ICI = Path(__file__).resolve().parent
ROOT = ICI.parents[2]
sys.path.insert(0, str(ROOT / 'engine'))
import anthropic  # noqa: E402
import httpx2  # noqa: E402
from editeur import claude_api as ca  # noqa: E402
from editeur import consigne as C  # noqa: E402
from editeur import detourage, llm, montage  # noqa: E402

FAUSSE = 'sk-ant-api03-FAUSSE-CLE-consigne-0123456789abcdefXYZ'
MORCEAU = 'FAUSSE-CLE-consigne'
BAC = ROOT / 'runtime/cache/tmp' / f'test-consigne-{uuid.uuid4().hex[:10]}'
PROJ = BAC / 'projects' / 'script1'
REEL = PROJ / 'reels' / 'script.json'
bilan, sorties, mesures = [], [], []


def verifier(nom, ok, detail=''):
    bilan.append({'test': nom, 'ok': bool(ok), 'detail': str(detail)[:300]})
    print(('OK   ' if ok else 'ECHEC') + f' {nom}' + (f' — {str(detail)[:300]}' if detail and not ok else ''))


# ---------- faux Claude ----------
class FauxMessages:
    def __init__(self, parent, beta):
        self.parent, self.beta = parent, beta

    def create(self, **p):
        self.parent.appels.append(('beta' if self.beta else 'messages', copy.deepcopy(p)))
        r = self.parent.reponses.pop(0) if self.parent.reponses else {'reponse': '', 'question': '', 'operations': [], 'refus': []}
        if isinstance(r, BaseException):
            raise r
        return SimpleNamespace(stop_reason='end_turn', stop_details=None, model=p['model'], _request_id='req_faux_consigne',
                               usage={'input_tokens': 4300, 'output_tokens': 380, 'cache_read_input_tokens': 2500,
                                      'cache_creation_input_tokens': 0},
                               content=[SimpleNamespace(type='text', text=json.dumps(r, ensure_ascii=False))])


class FauxClient:
    def __init__(self):
        self.appels, self.reponses = [], []
        self.messages = FauxMessages(self, False)
        self.beta = SimpleNamespace(messages=FauxMessages(self, True))


CLIENT = FauxClient()


def claude(*ops, question='', refus=(), reponse='C\'est fait.'):
    """Prochaine reponse du faux Claude (ce que Claude aurait compris de la demande)."""
    CLIENT.reponses.append({'reponse': reponse, 'question': question, 'operations': list(ops), 'refus': list(refus)})


# ---------- bac a sable ----------
ORIG = {}


def installer():
    BAC.mkdir(parents=True)
    (PROJ / 'reels').mkdir(parents=True)
    shutil.copy2(ROOT / 'projects/script1/project.json', PROJ / 'project.json')
    shutil.copy2(ROOT / 'projects/script1/reels/script.json', REEL)
    ORIG['brut'] = REEL.read_bytes()
    for k in ('REGLAGES', 'REGISTRE', 'JOURNAL', 'VERROU'):
        ORIG[k] = getattr(ca, k)
    ca.REGLAGES, ca.REGISTRE = BAC / 'claude/claude.json', BAC / 'claude/_claude.json'
    ca.JOURNAL, ca.VERROU = BAC / 'claude/claude-appels.jsonl', BAC / 'claude/claude.lock'
    ORIG['client'], ORIG['cle'] = ca._client, ca._cle
    ca._client = lambda k: CLIENT
    ca._cle = lambda: FAUSSE
    os.environ['ANTHROPIC_API_KEY'] = FAUSSE  # _masquer : jamais la vraie cle dans ce processus
    ca.ecrire_reglages({'plafond_video': 50.0, 'plafond_jour': 50.0, 'plafond_mois': 50.0, 'credit_depart': 50.0})
    # aucune IA locale ni detourage (GPU) pendant les tests
    ORIG['available'], ORIG['session'], ORIG['prepare'] = llm.available, llm.session, detourage.prepare
    llm.available = lambda: False
    ORIG['detourages'] = []
    detourage.prepare = lambda reel: ORIG['detourages'].append(reel.get('template'))


def remettre_reel(brut=None):
    REEL.write_bytes(brut or ORIG['brut'])
    shutil.rmtree(PROJ / 'versions', ignore_errors=True)
    for f in (PROJ / 'reels').glob('*.json'):
        if f.name != 'script.json':
            f.unlink()


def lire():
    return json.loads(REEL.read_text(encoding='utf-8'))


def sans_hist(r):
    return {k: v for k, v in r.items() if k != 'consignes'}


def lancer(texte, t=None, moteur='auto', simuler=False):
    r = C.appliquer(PROJ, 'script', texte, t, moteur, simuler)
    sorties.append(r)
    return r


def restaurer_comme_le_serveur(res, avant_brut):
    """POST …/restore {file: avant} = copie du fichier de versions/<version>/ sur le reel : octet pour octet."""
    src = PROJ / 'versions' / res['version'] / res['avant']
    shutil.copyfile(src, montage.reel_path(PROJ, res['version']))
    return montage.reel_path(PROJ, res['version']).read_bytes() == avant_brut


def commun(nom, res, avant_brut, n_hist):
    """Verifications de chaque demande appliquee : contrat, historique, « avant » exact."""
    cles = {'ok', 'version', 'avant', 'changements', 'refus', 'question', 'moteur', 'cout', 'note_ajoutee'}
    verifier(f'{nom} : champs du contrat', cles <= set(res) and res['ok'] is True, sorted(set(res)))
    r = lire()
    h = r.get('consignes') or []
    verifier(f'{nom} : historique +1', len(h) == n_hist + 1 and set(h[-1]) >= {'date', 'texte', 't', 'moteur', 'cout',
             'changements', 'refus', 'question'}, len(h))
    if res.get('avant'):
        verifier(f'{nom} : « avant » remet le montage à l\'octet près', restaurer_comme_le_serveur(res, avant_brut))


# ---------- cas ----------
def cas_forme_requete():
    remettre_reel()
    claude({'op': 'sous_titres_couleur', 'couleur': '#FFD400'}, reponse='Je mets les sous-titres en jaune.')
    n = len(CLIENT.appels)
    res = lancer('Mets les sous-titres en jaune')
    r = lire()
    verifier('1 jaune : couleur appliquée', r['style']['color'] == '#FFD400', r['style'].get('color'))
    verifier('1 jaune : moteur claude, coût compté', res['moteur'] == 'claude' and res['cout'] > 0, (res['moteur'], res['cout']))
    commun('1 jaune', res, ORIG['brut'], len(json.loads(ORIG['brut']).get('consignes') or []))
    genre, p = CLIENT.appels[n]
    verifier('requête : Sonnet 5.5 par défaut (beta + repli serveur)', genre == 'beta' and p['model'] == 'claude-sonnet-5-5'
             and p.get('betas') == [ca.BETA_REPLI] and p.get('fallbacks') == 'default', (genre, p.get('model')))
    verifier('requête : effort « low » (effort_consigne)', p['output_config'].get('effort') == 'low', p['output_config'].get('effort'))
    verifier('requête : max_tokens 1500', p['max_tokens'] == 1500, p['max_tokens'])
    verifier('requête : schéma strict de consigne.schema()', p['output_config']['format'] == {'type': 'json_schema', 'schema': C.schema()})
    verifier('requête : consigne système en cache', p['system'][-1].get('cache_control') == {'type': 'ephemeral'})
    verifier('requête : ni thinking, ni prefill, ni tool_choice', 'thinking' not in p and 'tool_choice' not in p
             and len(p['messages']) == 1 and p['messages'][0]['role'] == 'user')
    ctx = p['messages'][0]['content'][-1]['text']
    verifier('contexte : demande à la fin, éléments avec id', ctx.rstrip().endswith('« Mets les sous-titres en jaune »')
             and 'style-c1-43 · Notification' in ctx and 'PHRASES DITES' in ctx)
    verifier('dépense rangée sous la vidéo script1/script', ca.depense_video('script1/script') > 0)


def cas_musique():
    remettre_reel()
    claude({'op': 'musique_volume', 'sens': 'beaucoup_moins'})
    v0 = json.loads(ORIG['brut'])['music']['volume']
    res = lancer('La musique est ben trop forte, baisse-la stp')
    v1 = lire()['music']['volume']
    verifier('2 musique : volume ×0,45', abs(v1 - round(v0 * 0.45, 3)) < 1e-9, (v0, v1))
    commun('2 musique', res, ORIG['brut'], 0)


def cas_ici():
    remettre_reel()
    claude({'op': 'element_masquer', 'id': 'style-c1-43'})
    res = lancer('Enlève-moi la notification ici', t=10.0)
    s = next(x for x in lire()['styleScenes'] if x['id'] == 'style-c1-43')
    verifier('3 ici : notification masquée et marquée retouchée', s.get('hidden') is True and s.get('edited') and s.get('manual'), s)
    cues = [c for c in (lire().get('choreography') or {}).get('cues') or [] if (c.get('cible') or {}).get('id') == 'style-c1-43']
    verifier('3 ici : son mouvement de chorégraphie retiré', not cues, len(cues))
    verifier('3 ici : temps du lecteur donné à l\'IA', 'TEMPS DU LECTEUR : 10.0 s' in CLIENT.appels[-1][1]['messages'][0]['content'][-1]['text'])
    commun('3 ici', res, ORIG['brut'], 0)


def cas_zooms():
    remettre_reel()
    claude({'op': 'zooms', 'niveau': 'plus'})
    res = lancer('Plus de zooms')
    z = lire()['zoom']
    verifier('4 zooms : force 1,06 → 1,10, auto', z['auto'] is True and abs(z['strength'] - 1.1) < 1e-9, z)
    commun('4 zooms', res, ORIG['brut'], 0)


def cas_texte_carte():
    remettre_reel()
    claude({'op': 'element_texte', 'id': 'style-c2-52', 'texte': 'Lead perdu après 3 h'})
    res = lancer('Change le texte de la notif à 0:26 pour « Lead perdu après 3 h »')
    r = lire()
    s = next(x for x in r['styleScenes'] if x['id'] == 'style-c2-52')
    verifier('5 texte : texte changé, retouche figée', s['text'] == 'Lead perdu après 3 h' and s.get('edited') and s.get('manual'), s)
    # aucune saute : la place enregistree = la place que le rendu calculait juste avant la retouche
    libre = copy.deepcopy(r)
    for x in libre['styleScenes']:
        if x['id'] == 'style-c2-52':
            x.pop('edited', None), x.pop('manual', None)
    auto = next(p for p in C.calcul(libre)['scenes'] if p['id'] == 'style-c2-52')
    fige = next(p for p in C.calcul(r)['scenes'] if p['id'] == 'style-c2-52')
    verifier('5 texte : carte figée à sa place affichée (pas de saut)', all(abs(auto[k] - fige[k]) < 1e-3 for k in ('x', 'y', 'scale')),
             (auto, fige))
    verifier('5 texte : temps cité « 0:26 » détaillé dans le contexte', 'MOTS AUTOUR DE 26.0 s' in CLIENT.appels[-1][1]['messages'][0]['content'][-1]['text'])
    commun('5 texte', res, ORIG['brut'], 0)


def cas_couper():
    remettre_reel()
    M = C.calcul(json.loads(ORIG['brut']))
    mots = [w for w in M['words'] if 30.5 <= w['start'] <= 31.0]  # « on place un »
    claude({'op': 'couper', 'debut': mots[0]['start'], 'fin': mots[-1]['end']})
    res = lancer('Coupe le bout où je bégaie à 0:31')
    r = lire()
    coupes = [(c['id'], i) for c in r['clips'] for i, w in enumerate(c['words']) if w.get('cut')]
    attendus = [(w['clip'], w['index']) for w in mots]
    verifier('6 couper : mots entiers coupés (rétablissables)', sorted(coupes) == sorted(attendus), (coupes, attendus))
    d0, d1 = M['duration'], C.calcul(r)['duration']
    verifier('6 couper : vidéo plus courte', d1 < d0 - 0.2, (d0, d1))
    verifier('6 couper : compte rendu « coupé »', any('coupé' in c['detail'] for c in res['changements']), res['changements'][:2])
    commun('6 couper', res, ORIG['brut'], 0)


def cas_style():
    remettre_reel()
    brut = json.loads(ORIG['brut'])
    for s in brut['styleScenes']:
        if s['id'] == 'style-c5-21-final':
            s['locked'] = True  # verrouille : le changement de style ne doit pas le toucher
    REEL.write_text(json.dumps(brut, ensure_ascii=False, indent=1), encoding='utf-8')
    avant = REEL.read_bytes()
    claude({'op': 'style', 'style': 'hormozi'})
    res = lancer('Mets le style Hormozi')
    r = lire()
    verifier('7 style : Hormozi appliqué', r['template'] == 'hormozi' and (r.get('design') or {}).get('mode') == 'hormozi', r['template'])
    garde = next((x for x in r.get('styleScenes') or [] if x['id'] == 'style-c5-21-final'), None)
    verifier('7 style : élément verrouillé gardé tel quel', garde == next(x for x in brut['styleScenes'] if x['id'] == 'style-c5-21-final'))
    verifier('7 style : pas de détourage pour Hormozi', not ORIG['detourages'], ORIG['detourages'])
    commun('7 style', res, avant, 0)


def cas_declinaison():
    remettre_reel()
    claude({'op': 'declinaison', 'duree': 30, 'intention': 'aucune'})
    res = lancer('Fais-en une version de 30 secondes')
    verifier('8 déclinaison : original inchangé', REEL.read_bytes() == ORIG['brut'])
    nouveau = montage.reel_path(PROJ, res['version'])
    D = json.loads(nouveau.read_text(encoding='utf-8')) if nouveau.exists() else {}
    verifier('8 déclinaison : nouvelle version (derivedFrom script)', res['version'] != 'script' and D.get('derivedFrom') == 'script',
             res['version'])
    verifier('8 déclinaison : avant = id de l\'originale', res['avant'] == 'script')
    verifier('8 déclinaison : durée ≤ 32 s', D and C.calcul(D)['duration'] <= 32, D and C.calcul(D)['duration'])
    verifier('8 déclinaison : historique dans la nouvelle version', (D.get('consignes') or [{}])[-1].get('texte') == 'Fais-en une version de 30 secondes')


def cas_bruitages():
    remettre_reel()
    claude({'op': 'bruitages_quantite', 'niveau': 'moins'}, {'op': 'bruitages_varier', 'actif': True})
    res = lancer('Moins de bruitages pis varie les sons, y\'a toujours le même son de vent quand ça coupe')
    s = lire()['sfx']
    verifier('9 bruitages : moins (studio : plus de pop des mots ni de son au début)', s['start'] is None and s['highlight'] is None
             and s['enabled'] is True, s)
    verifier('9 bruitages : sons de transition variés (contrat « sons »)', s.get('varier') is True)
    commun('9 bruitages', res, ORIG['brut'], 0)
    # famille de sons : sfx.famille + sa reserve sfx.pool (le rendu ne lit que la reserve) ; regles simples aussi
    fams = C._familles()
    if not fams:
        print('INFO  9b famille de sons : catalogue styles/sons-transitions.json absent, cas sauté')
        return
    fid = 'doux' if 'doux' in fams else next(iter(fams))
    remettre_reel()
    claude({'op': 'bruitages_famille', 'famille': fid})
    res = lancer('Mets des sons plus doux quand ça coupe')
    s = lire()['sfx']
    pool = s.get('pool') or []
    verifier('9b famille : sfx.famille + réserve (≤ 32 sons présents, rôles connus)', s.get('famille') == fid and 0 < len(pool) <= 32
             and all((ROOT / 'assets/sfx/editeur' / f"{x['name']}.wav").exists() and x['role'] in
                     ('transition', 'interface', 'apparition', 'mot-fort', 'impact', 'cta') for x in pool), (s.get('famille'), len(pool)))
    ev = C.calcul(lire())['events']
    noms = {e['name'] for e in ev}
    verifier('9b famille : les sons de la vidéo viennent de la famille', noms & {x['name'] for x in pool}, sorted(noms)[:8])
    commun('9b famille', res, ORIG['brut'], 0)
    M = C.calcul(json.loads(ORIG['brut']))
    d = C._regles(f'des sons {fams[fid].lower()} svp', json.loads(ORIG['brut']), M, None)
    verifier('9b famille : règles simples aussi', d['operations'] == [{'op': 'bruitages_famille', 'famille': fid}], d)


def cas_ambigu():
    remettre_reel()
    claude(question='Qu\'est-ce que tu veux changer de couleur : les sous-titres, les mots en couleur ou une carte ?', reponse='')
    res = lancer('Change la couleur')
    r = lire()
    verifier('10 ambigu : question posée', bool(res['question']) and not res['changements'], res['question'])
    verifier('10 ambigu : rien d\'appliqué (seul l\'historique change)', sans_hist(r) == sans_hist(json.loads(ORIG['brut'])))
    verifier('10 ambigu : pas de version « avant »', res['avant'] is None and not (PROJ / 'versions').exists())
    verifier('10 ambigu : question gardée dans l\'historique', (r.get('consignes') or [{}])[-1].get('question') == res['question'])


def _note_valide(n):
    """Memes regles que noteOk / anchorOk de app/server.mjs (validateV2) : sinon la sauvegarde de l'editeur echouerait."""
    import re
    ok = set(n) <= {'id', 't', 'anchor', 'end', 'endAnchor', 'text', 'statut', 'auteur', 'cree', 'modifie', 'contexte', 'meta'}
    ok &= all(n.get(k) is not None for k in ('id', 't', 'anchor', 'text', 'statut', 'auteur', 'cree', 'modifie', 'contexte'))
    ok &= bool(re.fullmatch(r'[A-Za-z0-9_:.-]{1,120}', n['id'])) and 0 <= n['t'] <= 86400 and n['statut'] == 'ouverte'
    a = n['anchor']
    ok &= set(a) <= {'clip', 'src', 'sig', 'source', 'image'} and all(k in a for k in ('clip', 'src', 'sig'))
    ok &= len(n['text']) <= 2000 and len(n['auteur']) <= 80 and len(n['cree']) <= 40
    ok &= set(n['contexte']) <= {'titre', 'style', 'format', 'duree', 'phrase'} and len(json.dumps(n.get('meta') or {})) <= 2048
    return ok


def cas_hors_liste():
    remettre_reel()
    claude(refus=[{'demande': 'Ajouter une photo de la boutique à la fin', 'raison': 'Ajouter une image par écrit n\'est pas encore possible.'}],
           reponse='Je ne peux pas ajouter de photo : je laisse une note.')
    res = lancer('Ajoute une photo de ma boutique à la fin', t=69.0)
    r = lire()
    notes = r.get('notes') or []
    verifier('11 hors liste : refus avec raison', res['refus'] and res['refus'][0]['raison'], res['refus'])
    verifier('11 hors liste : note ouverte ajoutée à 1:09', res['note_ajoutee'] and notes and abs(notes[-1]['t'] - 69.0) < 0.05
             and 'Ajoute une photo' in notes[-1]['text'], notes[-1:] if notes else None)
    verifier('11 hors liste : note acceptée par le serveur (validateV2)', notes and _note_valide(notes[-1]), notes[-1:] if notes else None)
    commun('11 hors liste', res, ORIG['brut'], 0)


def cas_verrou():
    remettre_reel()
    brut = json.loads(ORIG['brut'])
    for s in brut['styleScenes']:
        if s['id'] == 'style-c2-52':
            s['locked'] = True
    REEL.write_text(json.dumps(brut, ensure_ascii=False, indent=1), encoding='utf-8')
    avant = REEL.read_bytes()
    claude({'op': 'element_texte', 'id': 'style-c2-52', 'texte': 'Perdu'})
    res = lancer('Change le texte de la notification « Lead en attente » pour « Perdu »')
    s = next(x for x in lire()['styleScenes'] if x['id'] == 'style-c2-52')
    verifier('12 verrou : élément verrouillé refusé (raison 🔒)', s['text'] == 'Lead en attente depuis 3 h' and res['refus']
             and 'verrouill' in res['refus'][0]['raison'], res['refus'])
    verifier('12 verrou : note laissée', res['note_ajoutee'] is True)
    commun('12 verrou', res, avant, 0)


def cas_suite():
    remettre_reel()
    claude({'op': 'element_couleur', 'id': 'style-c3-21', 'couleur': '#FF3B30'})
    res1 = lancer('Mets la carte du parcours en rouge', t=35.0)
    claude({'op': 'element_couleur', 'id': 'style-c4-45', 'couleur': '#FF3B30'})
    avant2 = REEL.read_bytes()
    res2 = lancer('Non, l\'autre parcours')
    ctx = CLIENT.appels[-1][1]['messages'][0]['content'][-1]['text']
    verifier('13 suite : la demande précédente est dans le contexte', 'DERNIÈRES DEMANDES' in ctx and 'Mets la carte du parcours' in ctx
             and 'Parcours en rouge' in ctx, ctx[-600:])
    sc = {x['id']: x for x in lire()['styleScenes']}
    verifier('13 suite : les deux parcours en rouge', sc['style-c3-21']['color'] == '#FF3B30' and sc['style-c4-45']['color'] == '#FF3B30')
    verifier('13 suite : historique des deux demandes', len(lire().get('consignes') or []) == 2)
    verifier('13 suite : « Annuler » le 2e remet le montage d\'après le 1er', restaurer_comme_le_serveur(res2, avant2))
    verifier('13 suite : « Annuler » le 1er remet l\'original', restaurer_comme_le_serveur(res1, ORIG['brut']))


def cas_mots():
    remettre_reel()
    claude({'op': 'mot_couleur', 'texte': 'setter', 'actif': True, 'partout': False},
           {'op': 'mot_corriger', 'avant': 'closés', 'apres': 'conclus', 'partout': True})
    res = lancer('Mets « setter » en couleur ici pis corrige closés par conclus', t=31.0)
    r = lire()
    hl = [(c['id'], i) for c in r['clips'] for i, w in enumerate(c['words']) if w.get('hl') and 'setter' in w['w'].lower()]
    verifier('14 mots : « setter » en couleur à 0:31 seulement', len(hl) == 1 and hl[0][0] == 'c3', hl)
    o = json.loads(ORIG['brut'])
    mots = {(c['id'], i): w for c in r['clips'] for i, w in enumerate(c['words'])}
    avant = {(c['id'], i): w for c in o['clips'] for i, w in enumerate(c['words'])}
    cibles = [k for k, w in avant.items() if w['w'] == 'closés']
    verifier('14 mots : « closés » corrigé (texte d\'origine gardé dans asr)', cibles and all(mots[k]['w'] == 'conclus'
             and mots[k].get('asr') == (avant[k].get('asr') or 'closés') for k in cibles), [mots[k] for k in cibles])
    voisins = [k for k, w in avant.items() if w['w'] in ('close.', 'closé,')]
    verifier('14 mots : mots voisins (« close. », « closé, ») non touchés', voisins and all(mots[k] == avant[k] for k in voisins))
    commun('14 mots', res, ORIG['brut'], 0)


def cas_emojis():
    remettre_reel()
    claude({'op': 'emojis', 'actif': True})
    res = lancer('Mets des emojis')
    r = lire()
    n = sum(len(c.get('emojis') or []) for c in r['clips'])
    verifier('15 emojis : affichés, ceux proposés posés', r['emoji']['enabled'] is True and n == 5, n)
    commun('15 emojis', res, ORIG['brut'], 0)


def cas_invalides():
    remettre_reel()
    claude({'op': 'element_masquer', 'id': 'carte-qui-n-existe-pas'}, {'op': 'sous_titres_couleur', 'couleur': 'jaune'},
           {'op': 'mot_geant_ajouter', 'texte': 'GRATUIT', 'debut': 500}, {'op': 'supprimer_tout', 'id': 'x'},
           {'op': 'musique_ambiance', 'ambiance': 'heavy-metal'}, {'op': 'bandeau_texte', 'texte': 'RÉPONDS VITE'})
    res = lancer('fais plein d\'affaires')
    r = lire()
    verifier('16 invalides : 5 refus (id, couleur, temps, opération, valeur)', len(res['refus']) == 5, [x['raison'] for x in res['refus']])
    verifier('16 invalides : la seule opération valide est faite', r['banner']['text'] == 'RÉPONDS VITE' and r['banner']['enabled'])
    verifier('16 invalides : couleur invalide non appliquée', r['style']['color'] == json.loads(ORIG['brut'])['style']['color'])
    verifier('16 invalides : note laissée pour les refus', res['note_ajoutee'] is True)
    commun('16 invalides', res, ORIG['brut'], 0)


def cas_deverrouiller():
    """L'IA ne leve jamais un verrou de son propre chef (pour changer un element verrouille) ; seulement si on le demande."""
    remettre_reel()
    brut = json.loads(ORIG['brut'])
    for s in brut['styleScenes']:
        if s['id'] == 'style-c2-52':
            s['locked'] = True
    REEL.write_text(json.dumps(brut, ensure_ascii=False, indent=1), encoding='utf-8')
    avant = REEL.read_bytes()
    ops = ({'op': 'element_verrou', 'id': 'style-c2-52', 'actif': False}, {'op': 'element_texte', 'id': 'style-c2-52', 'texte': 'Perdu'})
    claude(*ops)
    res = lancer('Change le texte de la notification pour « Perdu »')
    s = next(x for x in lire()['styleScenes'] if x['id'] == 'style-c2-52')
    verifier('31 verrou : pas levé par l\'IA sans qu\'on le demande', s.get('locked') is True and s['text'] == 'Lead en attente depuis 3 h'
             and len(res['refus']) == 2 and 'déverrouille' in res['refus'][0]['raison'], (s.get('locked'), s['text'], res['refus']))
    REEL.write_bytes(avant)
    claude(*ops)
    res = lancer('Déverrouille la notification pis change son texte pour « Perdu »')
    s = next(x for x in lire()['styleScenes'] if x['id'] == 'style-c2-52')
    verifier('31 verrou : levé quand on le demande', s.get('locked') is False and s['text'] == 'Perdu' and not res['refus'], res['refus'])


def cas_passage_retouche():
    """Carte retouchee ET « refais ce passage » dans la meme demande : la retouche est figee avant la passe (gardee)."""
    remettre_reel()
    claude({'op': 'element_texte', 'id': 'style-c3-21', 'texte': 'TEXTE IA'}, {'op': 'refaire_passage', 'debut': 33.0, 'fin': 40.0})
    res = lancer('Change le texte du parcours pis refais le passage de 0:33 à 0:40')
    s = next(x for x in lire()['styleScenes'] if x['id'] == 'style-c3-21')
    verifier('32 retouche + refaire le passage : la retouche reste', s['text'] == 'TEXTE IA' and s.get('edited') and s.get('manual'),
             {k: s.get(k) for k in ('text', 'edited', 'manual')})
    commun('32 retouche + passage', res, ORIG['brut'], 0)


def cas_casse():
    """Sortie structuree : la casse des valeurs « const » / « enum » n'est pas garantie (doc Anthropic) -> acceptee."""
    remettre_reel()
    police = next((p for p in C._polices() if ' ' in p), C._polices()[0])
    claude({'op': 'Sous_Titres_Police', 'police': police.lower()}, {'op': 'zooms', 'niveau': 'Plus'})
    res = lancer('Mets la police ' + police + ' pis plus de zooms')
    r = lire()
    verifier('33 casse : op et valeurs reconnues sans la casse', r['style'].get('font') == police and r['zoom']['auto'] is True
             and not res['refus'], (r['style'].get('font'), res['refus']))


def cas_style_sons():
    """Un changement de style garde les choix « sons de coupe » (famille, varier) : sfxgen.appliquer_famille."""
    fams = C._familles()
    if 'doux' not in fams:
        print('INFO  34 style + sons : famille « doux » absente, cas sauté')
        return
    remettre_reel()
    brut = json.loads(ORIG['brut'])
    brut['sfx'] = {**brut['sfx'], 'famille': 'doux', 'varier': True}
    REEL.write_text(json.dumps(brut, ensure_ascii=False, indent=1), encoding='utf-8')
    claude({'op': 'style', 'style': 'hormozi'})
    lancer('Mets le style Hormozi')
    s = lire()['sfx']
    from editeur import sfxgen
    verifier('34 style : famille de sons choisie gardée (réserve de sfxgen)', s.get('famille') == 'doux' and s.get('varier') is True
             and s.get('pool') == sfxgen.reserve('doux'), (s.get('famille'), len(s.get('pool') or [])))
    brut['sfx'] = {**json.loads(ORIG['brut'])['sfx'], 'varier': False}
    REEL.write_text(json.dumps(brut, ensure_ascii=False, indent=1), encoding='utf-8')
    claude({'op': 'style', 'style': 'hormozi'})
    lancer('Mets le style Hormozi')
    verifier('34 style : « toujours le même son » gardé', lire()['sfx'].get('varier') is False, lire()['sfx'].get('varier'))


def cas_regles_suite():
    """Regles simples (sans IA) : moment ecrit avant le lecteur, genre nomme, morceau qui continue le precedent."""
    reel = json.loads(ORIG['brut'])
    M = C.calcul(reel)
    d = C._regles('enlève la notification à 0:12', reel, M, 40.0)
    verifier('35 règles : « à 0:12 » passe avant le lecteur (40 s), la notification et pas le chiffre',
             d['operations'] == [{'op': 'element_masquer', 'id': 'style-c1-43'}], d)
    d = C._regles('La musique est ben trop forte, baisse-la stp', reel, M, None)
    verifier('35 règles : « baisse-la » = la musique, une seule baisse, aucun refus',
             d['operations'] == [{'op': 'musique_volume', 'sens': 'beaucoup_moins'}] and not d['refus'], d)
    d = C._regles("Quand ça coupe il y a toujours le même son de vent, j'aimerais en avoir plusieurs sortes", reel, M, None)
    verifier('35 règles : la phrase de l\'utilisateur -> sons variés, aucune note inutile',
             d['operations'] == [{'op': 'bruitages_varier', 'actif': True}] and not d['refus'], d)
    d = C._regles('change le style des sous-titres en jaune', reel, M, None)
    verifier('35 règles : « style des sous-titres » = sous-titres, pas le style du montage',
             d['operations'] == [{'op': 'sous_titres_couleur', 'couleur': '#FFD400'}], d)
    d = C._regles('baisse la musique, ajoute une photo', reel, M, None)
    verifier('35 règles : une autre demande n\'est pas avalée par le sujet d\'avant (refus + note)',
             d['operations'] == [{'op': 'musique_volume', 'sens': 'moins'}] and len(d['refus']) == 1, d)


def cas_passage():
    remettre_reel()
    claude({'op': 'refaire_passage', 'debut': 40.0, 'fin': 50.0})
    res = lancer('Refais l\'habillage entre 0:40 et 0:50')
    verifier('17 passage : passage.refaire lancé (compte rendu)', any(c['quoi'] == 'Passage' for c in res['changements']), res['changements'][:3])
    vs = list((PROJ / 'versions' / 'script').glob('*.json')) if (PROJ / 'versions' / 'script').exists() else []
    verifier('17 passage : une seule version « avant » (la nôtre)', len(vs) <= 1, [v.name for v in vs])
    if res['avant']:
        verifier('17 passage : « avant » remet le montage', restaurer_comme_le_serveur(res, ORIG['brut']))


def cas_local():
    """Claude eteint -> IA locale (Qwen simule) avec le MEME schema ; Qwen en panne -> regles."""
    remettre_reel()
    ca.ecrire_reglages({'actif': False})
    recu = {}

    def faux_qwen(sys_txt, contenu, sch):
        recu.update(sys=sys_txt, sch=sch, ctx=contenu)
        return {'reponse': 'Ok.', 'question': '', 'operations': [{'op': 'mots_forts_couleur', 'couleur': '#FF3B30'}], 'refus': []}
    vieux = C._qwen_requete
    llm.available, llm.session, C._qwen_requete = (lambda: True), (lambda vision=False: contextlib.nullcontext()), faux_qwen
    n = len(CLIENT.appels)
    try:
        res = lancer('mets les mots en couleur en rouge')
    finally:
        C._qwen_requete = vieux
    verifier('18 Claude éteint : IA locale utilisée, gratuite', res['moteur'] == 'local' and res['cout'] == 0 and len(CLIENT.appels) == n,
             (res['moteur'], res['cout']))
    verifier('18 Claude éteint : raison dite en français', any('éteint' in x for x in res['remarques']), res['remarques'])
    verifier('18 IA locale : même schéma et même consigne que Claude', recu.get('sch') == C.schema() and recu.get('sys') == C.systeme())
    verifier('18 IA locale : appliqué', lire()['style']['highlight'] == '#FF3B30')
    remettre_reel()

    @contextlib.contextmanager
    def en_panne(vision=False):
        raise RuntimeError('Le serveur IA local n\'a pas demarre')
        yield
    llm.session = en_panne
    try:
        res = lancer('Mets les sous-titres en jaune pis baisse la musique')
    finally:
        llm.available, llm.session = (lambda: False), ORIG['session']
    r = lire()
    verifier('19 IA locale en panne : règles simples', res['moteur'] == 'regles' and r['style']['color'] == '#FFD400'
             and r['music']['volume'] < json.loads(ORIG['brut'])['music']['volume'], (res['moteur'], res['changements']))
    verifier('19 IA locale en panne : raison dite', any('IA locale indisponible' in x for x in res['remarques']), res['remarques'])
    remettre_reel()
    try:
        C.appliquer(PROJ, 'script', 'mets les sous-titres en jaune', None, 'claude')
        verifier('20 --moteur claude + Claude éteint : erreur claire', False)
    except C.ConsigneErreur as e:
        verifier('20 --moteur claude + Claude éteint : erreur claire', 'éteint' in str(e), str(e))
    verifier('20 rien d\'écrit', REEL.read_bytes() == ORIG['brut'])
    ca.ecrire_reglages({'actif': True})
    # Claude hors ligne (erreur de connexion du SDK) -> local -> regles
    CLIENT.reponses.append(anthropic.APIConnectionError(request=httpx2.Request('POST', 'https://api.anthropic.com/v1/messages')))
    res = lancer('Mets les sous-titres en jaune')
    verifier('21 Claude hors ligne : règles, raison claire', res['moteur'] == 'regles' and any('connexion' in x.lower() or 'hors ligne' in x
             for x in res['remarques']) and lire()['style']['color'] == '#FFD400', res['remarques'])


def cas_simuler():
    remettre_reel()
    claude({'op': 'sous_titres_couleur', 'couleur': '#FFD400'}, {'op': 'style', 'style': 'hormozi'})
    res = lancer('jaune et style hormozi', simuler=True)
    verifier('22 simuler : rien d\'écrit', REEL.read_bytes() == ORIG['brut'] and not (PROJ / 'versions').exists())
    verifier('22 simuler : plan rendu', res['simule'] and len(res['changements']) == 2 and 'serait' in res['changements'][0]['detail'],
             res['changements'])


def cas_concurrence():
    remettre_reel()
    claude({'op': 'sous_titres_couleur', 'couleur': '#FFD400'})
    vieux = C._interpreter

    def pendant(*a, **k):
        out = vieux(*a, **k)
        r = lire()
        r['label'] = 'retouche faite dans l\'éditeur pendant le calcul'
        REEL.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
        return out
    C._interpreter = pendant
    try:
        C.appliquer(PROJ, 'script', 'mets les sous-titres en jaune', None, 'auto')
        verifier('23 retouche concurrente : refusée', False)
    except C.ConsigneErreur as e:
        verifier('23 retouche concurrente : refusée, la retouche est gardée', lire().get('label', '').startswith('retouche')
                 and lire()['style']['color'] != '#FFD400', str(e))
    finally:
        C._interpreter = vieux


def cas_cli():
    remettre_reel()
    env = {**os.environ, 'EDITEUR_LLM': '0', 'PYTHONIOENCODING': 'utf-8'}
    env.pop('ANTHROPIC_API_KEY', None)
    r = subprocess.run([sys.executable, '-m', 'editeur.consigne', str(PROJ), '--reel', 'script', '--texte=Mets les sous-titres en jaune',
                        '--t=12', '--moteur=local'], capture_output=True, text=True, encoding='utf-8', cwd=str(ROOT / 'engine'), env=env)
    lignes = [x for x in r.stdout.splitlines() if x.strip()]
    out = json.loads(lignes[-1]) if lignes else {}
    sorties.append(r.stdout + r.stderr)
    verifier('24 ligne de commande : une seule ligne JSON', r.returncode == 0 and len(lignes) == 1, (r.returncode, r.stdout[-300:], r.stderr[-300:]))
    verifier('24 ligne de commande : règles, appliqué', out.get('moteur') == 'regles' and lire()['style']['color'] == '#FFD400', out)
    r = subprocess.run([sys.executable, '-m', 'editeur.consigne', str(PROJ), '--reel', 'script', '--texte=   ', '--moteur=local'],
                       capture_output=True, text=True, encoding='utf-8', cwd=str(ROOT / 'engine'), env=env)
    out = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
    verifier('25 ligne de commande : texte vide -> code 1, phrase claire', r.returncode == 1 and out.get('ok') is False
             and 'Écris ta demande' in out.get('erreur', '') and 'Écris ta demande' in r.stderr, (r.returncode, out))


def cas_schema():
    sch = C.schema()
    interdits = {'minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum', 'multipleOf', 'minLength', 'maxLength',
                 'pattern', 'minItems', 'maxItems', 'uniqueItems', 'format', '$ref', '$defs', 'definitions'}
    fautes = []

    def walk(o, chemin):
        if isinstance(o, dict):
            if o.get('type') == 'object':
                props = o.get('properties') or {}
                if o.get('additionalProperties') is not False or sorted(o.get('required') or []) != sorted(props):
                    fautes.append(chemin)
                for k, v in props.items():  # noms de champs (ex. « format ») : pas des mots-cles du schema
                    walk(v, f'{chemin}.properties.{k}')
            for k, v in o.items():
                if k == 'properties':
                    continue
                if k in interdits:
                    fautes.append(f'{chemin}.{k}')
                walk(v, f'{chemin}.{k}')
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f'{chemin}[{i}]')
    walk(sch, '$')
    branches = sch['properties']['operations']['items']['anyOf']
    verifier('26 schéma : objets fermés, champs tous requis, aucun mot-clé non pris en charge', not fautes, fautes[:5])
    verifier('26 schéma : une branche par opération (op constant)', len(branches) == len(C.catalogue())
             and all(b['properties']['op'].get('const') for b in branches), len(branches))
    verifier('26 schéma : aucun champ facultatif ni type multiple (null)', '"null"' not in json.dumps(sch) and "'null'" not in json.dumps(sch))


def cas_taille_cout():
    """Taille de l'invite (jetons estimes a 3,5 caracteres) et cout par demande sur Sonnet 5.5 et Haiku 4.5."""
    reel = json.loads(ORIG['brut'])
    M = C.calcul(reel)
    sy, sch = C.systeme(), json.dumps(C.schema(), ensure_ascii=False)
    ctxs = [C.contexte(reel, M, t, x) for x, t in (('Mets les sous-titres en jaune', None), ('enlève la carte ici', 10.0),
                                                     ('coupe le bout où je bégaie à 0:31', 30.0))]
    j = lambda s: round(len(s) / ca.CAR_PAR_JETON)
    j_sys, j_sch, j_ctx = j(sy), j(sch), max(j(c) for c in ctxs)
    verifier('27 contexte ≤ ~4 000 jetons', j_ctx <= 4000, j_ctx)
    sortie = 450  # reponse typique (quelques operations) ; Sonnet : petite reflexion a l'effort « low » comprise
    for m in ('claude-sonnet-5-5', 'claude-haiku-4-5'):
        p = ca.prix(m)
        cache = m != 'claude-haiku-4-5' or j_sys >= 4096  # Haiku : pas de cache sous 4 096 jetons
        premier = (j_sys * (p['cache_ecrit'] if cache else p['entree']) + (j_sch + j_ctx + ca.SURCOUT_FORMAT) * p['entree']
                   + sortie * p['sortie']) / 1e6
        suivant = (j_sys * (p['cache_lu'] if cache else p['entree']) + (j_sch + j_ctx + ca.SURCOUT_FORMAT) * p['entree']
                   + sortie * p['sortie']) / 1e6
        haut = ca.estimer(sy, ctxs[-1], sortie=C.SORTIE_MAX, modele=m, schema=C.schema())
        mesures.append({'modele': m, 'jetons_systeme': j_sys, 'jetons_schema': j_sch, 'jetons_contexte': j_ctx,
                        'cout_premier': round(premier, 4), 'cout_suivant': round(suivant, 4), 'plafond_estime': round(haut, 4),
                        'demandes_avec_2_dollars': int(2.0 // suivant)})
    for x in mesures:
        print(f"   {x['modele']} : système {x['jetons_systeme']} + schéma {x['jetons_schema']} + contexte {x['jetons_contexte']} jetons ; "
              f"{x['cout_premier']} $ la 1re demande, {x['cout_suivant']} $ les suivantes (cache), estimation haute "
              f"{x['plafond_estime']} $ ; ~{x['demandes_avec_2_dollars']} demandes avec 2 $")
    verifier('27 coût Sonnet < 0,03 $ par demande', mesures[0]['cout_suivant'] < 0.03, mesures[0])


def cas_export():
    srv = (ROOT / 'app/server.mjs').read_text(encoding='utf-8')
    verifier('28 export : le serveur retire reel.consignes avant le rendu', 'consignes: _consignes' in srv)
    types = (ROOT / 'remotion/src/types.ts').read_text(encoding='utf-8')
    app = (ROOT / 'app/ui/App.tsx').read_text(encoding='utf-8')
    rev = (ROOT / 'app/ui/revision.tsx').read_text(encoding='utf-8')
    dans_types = 'consignes' in types.split('export const REVIEW_KEYS')[-1].split('\n')[0]
    editeur = dans_types or "'consignes']" in app
    revision = dans_types or 'consignes: _consignes' in rev
    # fichiers de l'integrateur : signale, sans echec, tant que ce n'est pas branche
    for nom, ok in (('éditeur (App.tsx)', editeur), ('Révision (revision.tsx)', revision)):
        print(('OK   ' if ok else 'INFO ') + f' 28 lecteur de l\'{nom} : reel.consignes retiré des props du Player'
              + ('' if ok else ' — à faire par l\'intégrateur'))


def cas_historique():
    remettre_reel()
    r = json.loads(ORIG['brut'])
    r['consignes'] = [{'date': '2026-10-01T10:00:00', 'texte': f'demande {k}', 't': None, 'moteur': 'regles', 'cout': 0,
                       'changements': [], 'refus': [], 'question': None} for k in range(C.HISTORIQUE)]
    REEL.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
    claude({'op': 'flash', 'actif': True})
    lancer('Ajoute des flashs')
    h = lire()['consignes']
    verifier('29 historique plafonné (50) et la plus récente gardée', len(h) == C.HISTORIQUE and h[-1]['texte'] == 'Ajoute des flashs'
             and h[0]['texte'] == 'demande 1', (len(h), h[0]['texte']))


def cas_cle():
    vus = []
    for f in BAC.rglob('*'):
        if f.is_file():
            try:
                if MORCEAU in f.read_text(encoding='utf-8', errors='ignore'):
                    vus.append(str(f))
            except OSError:
                pass
    vus += [str(s)[:80] for s in sorties if MORCEAU in json.dumps(s, ensure_ascii=False, default=str)]
    verifier('30 la clé n\'apparaît nulle part (bac, résultats, sorties)', not vus, vus[:3])


def main():
    garder = '--garder' in sys.argv
    t0 = time.time()
    installer()
    try:
        for cas in (cas_forme_requete, cas_musique, cas_ici, cas_zooms, cas_texte_carte, cas_couper, cas_style, cas_declinaison,
                    cas_bruitages, cas_ambigu, cas_hors_liste, cas_verrou, cas_suite, cas_mots, cas_emojis, cas_invalides,
                    cas_deverrouiller, cas_passage_retouche, cas_casse, cas_style_sons, cas_regles_suite,
                    cas_passage, cas_local, cas_simuler, cas_concurrence, cas_cli, cas_schema, cas_taille_cout, cas_export,
                    cas_historique, cas_cle):
            try:
                cas()
            except Exception as e:
                import traceback
                traceback.print_exc()
                verifier(f'{cas.__name__} : exception', False, f'{type(e).__name__}: {e}')
    finally:
        for k in ('REGLAGES', 'REGISTRE', 'JOURNAL', 'VERROU'):
            setattr(ca, k, ORIG[k])
        ca._client, ca._cle = ORIG['client'], ORIG['cle']
        llm.available, llm.session, detourage.prepare = ORIG['available'], ORIG['session'], ORIG['prepare']
        if not garder:
            shutil.rmtree(BAC, ignore_errors=True)
    n_ok = sum(1 for b in bilan if b['ok'])
    print(f'\n{n_ok}/{len(bilan)} vérifications réussies en {time.time() - t0:.0f} s' + (f' (bac gardé : {BAC})' if garder else ''))
    print('Appels réels à Claude : 0 (faux client) ; IA locale : simulée.')
    return 0 if n_ok == len(bilan) else 1


if __name__ == '__main__':
    sys.exit(main())
