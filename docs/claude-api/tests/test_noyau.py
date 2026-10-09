"""Tests du noyau Claude (engine/editeur/claude_api.py + « python -m editeur claude ... »), SANS aucun appel reel :
faux client Anthropic, fausse cle, reglages / registre / journal dans un bac a sable (runtime/cache/tmp/<unique>).

    cd D:\\Tools\\editeur_sami\\engine
    ..\\runtime\\venv\\Scripts\\python.exe ..\\docs\\claude-api\\tests\\test_noyau.py [--garder]

Cas : calcul des couts (3 modeles, repli serveur), forme de la requete par modele (Haiku : ni effort ni repli ;
Sonnet / Opus : effort + beta de repli), relance prudente apres un 400, refus de budget (video, jour, mois, credit),
credit epuise (phrase + statut.credit_epuise + pause de 10 min), refus de securite, reponse coupee, cle refusee,
hors ligne, delai, panne, registre abime reconstruit, pas de cle, reglages (validation stricte), modele par tache,
ligne de commande (bac a sable), le VRAI SDK sur un faux transport local (en-tetes beta / espace de travail, corps
JSON, vraies classes de reponse et d'erreur ; aucun reseau), cle d'organisation sans espace de travail, et la cle
jamais ecrite ni affichee (balayage de tout le bac a sable).
--garder : ne supprime pas le bac a sable a la fin."""
import base64
import copy
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ICI = Path(__file__).resolve().parent
ROOT = ICI.parents[2]
sys.path.insert(0, str(ROOT / 'engine'))
import anthropic  # noqa: E402
import httpx2  # noqa: E402
from editeur import claude_api as ca  # noqa: E402

FAUSSE = 'sk-ant-api03-FAUSSE-CLE-de-test-0123456789abcdefXYZ'
MORCEAU = 'FAUSSE-CLE-de-test'  # partie distinctive : ne doit apparaitre NULLE PART
SYS_SECRET = 'CONSIGNE-SYSTEME-PRIVEE-7Q'
TXT_SECRET = 'CONTENU-PRIVE-DE-LA-VIDEO-4K'
SCHEMA = {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}, 'required': ['ok'], 'additionalProperties': False}
BAC = ROOT / 'runtime/cache/tmp' / f'test-noyau-claude-{uuid.uuid4().hex[:10]}'
ORIGINAL = {'client': ca._client, 'cle': ca._cle}
bilan = []
sorties = []  # tout ce que le module a rendu (balaye a la fin pour la cle)


def verifier(nom, ok, detail=''):
    bilan.append({'test': nom, 'ok': bool(ok), 'detail': str(detail)[:300]})
    print(('OK   ' if ok else 'ECHEC') + f' {nom}' + (f' — {str(detail)[:300]}' if detail and not ok else ''))


# ---------- faux client ----------
class FauxMessages:
    def __init__(self, parent, beta):
        self.parent, self.beta = parent, beta

    def create(self, **p):
        self.parent.appels.append(('beta' if self.beta else 'messages', copy.deepcopy(p)))
        r = self.parent.reponses.pop(0) if self.parent.reponses else reponse()
        if isinstance(r, BaseException):
            raise r
        return r(p) if callable(r) else r


class FauxClient:
    def __init__(self, reponses=()):
        self.appels, self.reponses = [], list(reponses)
        self.messages = FauxMessages(self, False)
        self.beta = SimpleNamespace(messages=FauxMessages(self, True))


def reponse(texte='{"ok": true}', stop='end_turn', usage=None, model='claude-sonnet-5-5', rid='req_faux_1',
            details=None, content=None):
    u = usage or {'input_tokens': 120, 'output_tokens': 30, 'cache_read_input_tokens': 0, 'cache_creation_input_tokens': 0}
    return SimpleNamespace(stop_reason=stop, stop_details=details, model=model, _request_id=rid, usage=u,
                           content=content if content is not None else [SimpleNamespace(type='text', text=texte)])


def _req():
    return httpx2.Request('POST', 'https://api.anthropic.com/v1/messages')


def erreur(cls, code, message, genre='invalid_request_error'):
    resp = httpx2.Response(code, request=_req(), headers={'request-id': f'req_err_{code}'})
    body = {'type': 'error', 'error': {'type': genre, 'message': message}}
    return cls(f'Error code: {code} - {body}', response=resp, body=body)


CREDIT_400 = ('Your credit balance is too low to access the Anthropic API. Please go to Plans & Billing to upgrade or '
              'purchase credits.')


def installer(client, cle=FAUSSE):
    ca._client = lambda k: client
    ca._cle = lambda: cle
    return client


def remise(reglages=None):
    """Bac a sable vierge : reglages par defaut (+ modifications), registre et journal vides, memoire de session videe."""
    for f in (ca.REGLAGES, ca.REGISTRE, ca.JOURNAL, ca.REGISTRE.with_name(ca.REGISTRE.name + '.abime')):
        try:
            f.unlink()
        except FileNotFoundError:
            pass
    ca._sans_session.clear()
    ca._en_cours.clear()
    ca._clients.clear()
    if reglages:
        ca.ecrire_reglages(reglages)


def appel(tache='cerveau', **kw):
    kw.setdefault('video', 'video1/script')
    r = ca.appeler(tache, SYS_SECRET, f'{TXT_SECRET} : donne le JSON.', SCHEMA, **kw)
    sorties.append(r)
    return r


def stat():
    s = ca.statut()
    sorties.append(s)
    return s


# ---------- cas ----------
def cas_prix():
    verifier('prix Sonnet 5.5', ca.prix('claude-sonnet-5-5') == {'entree': 2.0, 'sortie': 10.0, 'cache_lu': 0.2, 'cache_ecrit': 2.5})
    verifier('prix Haiku 4.5', ca.prix('claude-haiku-4-5') == {'entree': 1.0, 'sortie': 5.0, 'cache_lu': 0.1, 'cache_ecrit': 1.25})
    verifier('prix Opus 5.5', ca.prix('claude-opus-5-5') == {'entree': 4.0, 'sortie': 20.0, 'cache_lu': 0.2, 'cache_ecrit': 5.0})
    verifier('prix : identifiant date = alias', ca.prix('claude-haiku-4-5-20251001') == ca.prix('claude-haiku-4-5'))
    verifier('prix : modele inconnu -> None', ca.prix('claude-x-9') is None)
    u = {'input_tokens': 1000, 'output_tokens': 500, 'cache_read_input_tokens': 2000, 'cache_creation_input_tokens': 4000}
    for m, attendu in (('claude-sonnet-5-5', 0.0174), ('claude-haiku-4-5', 0.0087), ('claude-opus-5-5', 0.0344)):
        verifier(f'cout {m}', abs(ca.cout(u, m) - attendu) < 1e-9, ca.cout(u, m))
    # objet du SDK (attributs) plutot que dict
    verifier('cout : usage objet', abs(ca.cout(SimpleNamespace(**u), 'claude-sonnet-5-5') - 0.0174) < 1e-9)
    # repli serveur : chaque tentative a son tarif
    it = {'iterations': [{'type': 'message', 'input_tokens': 1000, 'output_tokens': 0},
                         {'type': 'fallback_message', 'model': 'claude-sonnet-5', 'input_tokens': 1000, 'output_tokens': 500}],
          'input_tokens': 1000, 'output_tokens': 500}
    c, j, note = ca.detail_cout(it, 'claude-sonnet-5-5')
    verifier('cout repli Sonnet 5.5 -> Sonnet 5 (tentatives)', abs(c - 0.009) < 1e-9 and j['entree'] == 2000 and not note, (c, j, note))
    it2 = {'iterations': [{'type': 'message', 'input_tokens': 1000, 'output_tokens': 200},
                          {'type': 'fallback_message', 'input_tokens': 1000, 'output_tokens': 500}]}
    c2, _, n2 = ca.detail_cout(it2, 'claude-opus-5-5', 'claude-opus-4-8')
    verifier('cout repli Opus 5.5 -> Opus 4.8 (modele de la reponse)', abs(c2 - 0.0255) < 1e-9 and not n2, (c2, n2))
    c3, _, n3 = ca.detail_cout(it2, 'claude-opus-5-5')
    verifier('cout repli sans modele connu -> tarif demande + note', abs(c3 - (0.008 + 0.014)) < 1e-9 and 'inconnu' in n3, (c3, n3))
    it4 = {'iterations': [{'type': 'fallback_message', 'model': 'claude-x-9', 'input_tokens': 1000, 'output_tokens': 0}]}
    c4, _, n4 = ca.detail_cout(it4, 'claude-haiku-4-5')
    verifier('cout tentative de modele inconnu -> tarif demande + note', abs(c4 - 0.001) < 1e-9 and 'claude-x-9' in n4, (c4, n4))
    e1 = ca.estimation_video('claude-sonnet-5-5')
    e2 = ca.estimation_video('claude-haiku-4-5')
    e3 = ca.estimation_video('claude-opus-5-5')
    verifier('estimation_video : Haiku < Sonnet < Opus', e2['par_video'] < e1['par_video'] < e3['par_video']
             and e2['critique'] < e1['critique'] < e3['critique'], (e1, e2, e3))
    verifier('estimation_video Sonnet sous le plafond par video', 0 < e1['par_video'] + e1['critique'] < 0.25
             and e1['videos_avec_credit'] >= 10 and 'par vidéo' in e1['texte'], e1)


def cas_forme():
    remise()
    img = np.zeros((1920, 1080, 3), dtype=np.uint8)
    img[:, :, 0] = 200
    for m, plat in (('claude-haiku-4-5', True), ('claude-sonnet-5-5', False), ('claude-opus-5-5', False)):
        cl = installer(FauxClient([reponse(model=m)]))
        r = appel(modele=m, images=[('12,4 s', img)], max_tokens=4000)
        verifier(f'{m} : appel ok', r['ok'] and r['donnees'] == {'ok': True} and r['modele'] == m, r)
        quel, p = cl.appels[0]
        oc = p.get('output_config') or {}
        verifier(f'{m} : point d\'entree', quel == ('messages' if plat else 'beta'), quel)
        verifier(f'{m} : jamais de thinking / tool_choice / pre-remplissage',
                 'thinking' not in p and 'tool_choice' not in p and [x['role'] for x in p['messages']] == ['user'], list(p))
        verifier(f'{m} : sortie structuree', oc.get('format') == {'type': 'json_schema', 'schema': SCHEMA}, oc)
        if plat:
            verifier(f'{m} : ni effort ni repli ni beta', 'effort' not in oc and 'betas' not in p and 'fallbacks' not in p, p.keys())
        else:
            verifier(f'{m} : effort explicite + repli serveur',
                     oc.get('effort') == 'medium' and p.get('betas') == ['server-side-fallback-2026-07-01']
                     and p.get('fallbacks') == 'default', {k: p.get(k) for k in ('betas', 'fallbacks')} | {'oc': oc.get('effort')})
        sysb = p.get('system') or []
        verifier(f'{m} : consigne systeme en cache', len(sysb) == 1 and sysb[0]['text'] == SYS_SECRET
                 and sysb[0].get('cache_control') == {'type': 'ephemeral'}, sysb)
        blocs = p['messages'][0]['content']
        types = [b['type'] for b in blocs]
        verifier(f'{m} : legende, image JPEG puis texte', types == ['text', 'image', 'text'] and blocs[0]['text'] == '12,4 s'
                 and blocs[2]['text'].startswith(TXT_SECRET), types)
        src = blocs[1]['source']
        jpg = base64.standard_b64decode(src['data'])
        verifier(f'{m} : image base64 JPEG reduite', src['type'] == 'base64' and src['media_type'] == 'image/jpeg'
                 and jpg[:2] == b'\xff\xd8' and r['jetons']['images'] == 1, src['media_type'])
        verifier(f'{m} : max_tokens transmis', p['max_tokens'] == 4000)
    from PIL import Image
    import io
    w, h = Image.open(io.BytesIO(jpg)).size
    verifier('image reduite a 540 x 960', (w, h) == (540, 960), (w, h))
    # effort selon la tache, et effort impose
    remise()
    for tache, attendu, impose in (('consigne', 'low', None), ('critique_visuelle', 'medium', None),
                                   ('cerveau', 'high', 'high'), ('cerveau', 'medium', 'xhigh')):
        cl = installer(FauxClient())
        appel(tache, effort=impose)
        verifier(f'effort de « {tache} » ({impose or "réglage"})', cl.appels[0][1]['output_config'].get('effort') == attendu,
                 cl.appels[0][1]['output_config'])
    # modele par tache
    remise({'modeles_taches': {'critique': 'claude-haiku-4-5'}})
    cl = installer(FauxClient([reponse(model='claude-haiku-4-5'), reponse()]))
    appel('critique_visuelle')
    appel('consigne')
    verifier('modele par tache (critique -> Haiku, consigne -> general)',
             cl.appels[0][1]['model'] == 'claude-haiku-4-5' and cl.appels[0][0] == 'messages'
             and cl.appels[1][1]['model'] == 'claude-sonnet-5-5' and cl.appels[1][0] == 'beta', [a[1]['model'] for a in cl.appels])
    verifier('modele_pour', ca.modele_pour('critique') == 'claude-haiku-4-5' and ca.modele_pour('test') == 'claude-sonnet-5-5'
             and ca.modele_pour('cerveau') == 'claude-sonnet-5-5')
    # essai() (claude test) avec le faux client : Haiku, 50 jetons, aucun effort
    remise()
    cl = installer(FauxClient([reponse(model='claude-haiku-4-5', usage={'input_tokens': 300, 'output_tokens': 6})]))
    r = ca.essai()
    sorties.append(r)
    p = cl.appels[0][1]
    verifier('essai : Haiku, max_tokens 50, sans effort', cl.appels[0][0] == 'messages' and p['model'] == 'claude-haiku-4-5'
             and p['max_tokens'] == 50 and 'effort' not in p['output_config'] and r['ok'], (p['model'], r['raison']))
    verifier('essai : cout affiche', abs(r['cout'] - 0.00033) < 1e-9 and r['cout_texte'] == '0,0003 $', (r['cout'], r['cout_texte']))


def cas_relance():
    remise()
    cl = installer(FauxClient([erreur(anthropic.BadRequestError, 400, 'fallbacks: Extra inputs are not permitted'), reponse()]))
    r = appel()
    verifier('400 sur le repli -> relance UNE fois sans beta', r['ok'] and len(cl.appels) == 2 and cl.appels[1][0] == 'messages'
             and 'fallbacks' not in cl.appels[1][1] and cl.appels[1][1]['output_config'].get('effort') == 'medium'
             and 'repli' in r['note'], (len(cl.appels), r['note']))
    cl.appels.clear()
    appel()
    verifier('… et ce modele s\'en passe pour la session', len(cl.appels) == 1 and cl.appels[0][0] == 'messages')
    remise()
    cl = installer(FauxClient([erreur(anthropic.BadRequestError, 400, 'output_config.effort: Input should be low'), reponse()]))
    r = appel()
    verifier('400 sur l\'effort -> relance sans effort (repli garde)', r['ok'] and len(cl.appels) == 2
             and 'effort' not in cl.appels[1][1]['output_config'] and cl.appels[1][0] == 'beta', r['note'])
    remise()
    cl = installer(FauxClient([erreur(anthropic.BadRequestError, 400, 'messages: roles must alternate')]))
    r = appel()
    verifier('autre 400 : pas de relance', not r['ok'] and len(cl.appels) == 1 and 'erreur 400' in r['raison'], r['raison'])
    remise()
    cl = installer(FauxClient([erreur(anthropic.BadRequestError, 400, 'effort not supported'),
                               erreur(anthropic.BadRequestError, 400, 'fallbacks not supported')]))
    r = appel()
    verifier('une seule relance au plus', not r['ok'] and len(cl.appels) == 2, len(cl.appels))
    remise()
    cl = installer(FauxClient([erreur(anthropic.BadRequestError, 400, 'thinking: unsupported')]))
    r = appel(modele='claude-haiku-4-5')
    verifier('Haiku : rien a retirer -> pas de relance', not r['ok'] and len(cl.appels) == 1, len(cl.appels))


def cas_budget():
    remise({'plafond_video': 0.01})
    cl = installer(FauxClient())
    r = appel()
    verifier('plafond par video : refus sans appel', not r['ok'] and not cl.appels and 'Plafond par vidéo' in r['raison']
             and 'local' in r['raison'], r['raison'])
    remise({'plafond_jour': 0.02})
    r = appel(video=None)
    verifier('plafond du jour : refus sans appel', not r['ok'] and not cl.appels and 'Plafond du jour' in r['raison'], r['raison'])
    remise({'plafond_mois': 0.02})
    r = appel()
    verifier('plafond du mois : refus sans appel', not r['ok'] and not cl.appels and 'Plafond du mois' in r['raison'], r['raison'])
    remise({'credit_depart': 0.05})
    r = appel()
    verifier('credit restant trop bas : refus sans appel', not r['ok'] and not cl.appels and 'Crédit Claude presque épuisé' in r['raison'],
             r['raison'])
    # estimation haute : sortie maximale comprise (Sonnet, 8000 jetons -> au moins 0,08 $)
    remise()
    r = appel()
    verifier('estimation haute >= sortie maximale', r['estimation'] >= 0.08 and r['ok'], r['estimation'])
    # credit restant = depart - depenses depuis credit_date (les depenses d'avant ne comptent pas)
    remise()
    ca._inscrire({'date': '2026-09-30T10:00:00', 'tache': 'cerveau', 'video': 'v/script', 'cout': 0.7, 'ok': True})
    ca._inscrire({'date': ca._maintenant(), 'tache': 'cerveau', 'video': 'v/script', 'cout': 0.4, 'ok': True})
    ca.ecrire_reglages({'credit_date': ca._jour()})
    s = stat()
    verifier('credit_restant_estime = depart - depenses depuis la date', abs(s['credit_restant_estime'] - 1.6) < 1e-9, s['credit_restant_estime'])
    ca._inscrire({'date': ca._maintenant(), 'tache': 'cerveau', 'video': 'v/script', 'cout': 5.0, 'ok': True})
    s = stat()
    verifier('credit restant jamais negatif + pas pret', s['credit_restant_estime'] == 0 and not s['pret']
             and 'épuisé' in s['raison'], (s['credit_restant_estime'], s['raison']))
    # deux appels en meme temps (fils) : chacun inscrit, totaux justes
    remise()
    installer(FauxClient([reponse(), reponse()]))
    fils = [threading.Thread(target=appel) for _ in range(2)]
    [f.start() for f in fils]
    [f.join() for f in fils]
    s = stat()
    lignes = ca.JOURNAL.read_text(encoding='utf-8').splitlines()
    verifier('deux appels simultanes : 2 lignes, 2 appels du jour', len(lignes) == 2 and s['appels_jour'] == 2, (len(lignes), s['appels_jour']))
    verifier('aucun fichier temporaire oublie', not list(BAC.rglob('*.tmp')), list(BAC.rglob('*.tmp')))


def cas_credit():
    remise()
    cl = installer(FauxClient([erreur(anthropic.BadRequestError, 400, CREDIT_400)]))
    r = appel()
    verifier('credit epuise : phrase exacte', not r['ok'] and r['raison'] == ca.CREDIT_EPUISE and len(cl.appels) == 1, r['raison'])
    verifier('credit epuise : request_id garde', r['request_id'] == 'req_err_400', r['request_id'])
    s = stat()
    verifier('statut.credit_epuise + pas pret', s['credit_epuise'] and not s['pret'] and s['raison'] == ca.CREDIT_EPUISE, s)
    r = appel()
    verifier('pendant 10 min : plus aucun appel', not r['ok'] and len(cl.appels) == 1 and r['raison'] == ca.CREDIT_EPUISE)
    reg = json.loads(ca.REGISTRE.read_text(encoding='utf-8'))
    reg['credit_epuise'] = '2026-01-01T00:00:00'  # il y a longtemps : on reessaie
    ca._ecrire_json(ca.REGISTRE, reg)
    s = stat()
    verifier('apres 10 min : pret, avertissement garde', s['pret'] and s['credit_epuise'] and s['avertissement'], s['avertissement'])
    cl.reponses.append(reponse())
    r = appel()
    s = stat()
    verifier('un appel reussi efface l\'alerte', r['ok'] and not s['credit_epuise'] and len(cl.appels) == 2)
    remise()
    installer(FauxClient([erreur(anthropic.APIStatusError, 402, 'billing problem', 'billing_error')]))
    r = appel()
    verifier('402 billing_error -> credit epuise', r['raison'] == ca.CREDIT_EPUISE and stat()['credit_epuise'], r['raison'])
    ca.ecrire_reglages({'credit_depart': 5.0, 'credit_date': ca._jour()})
    s = stat()
    verifier('recharge (nouveau credit) : alerte effacee', not s['credit_epuise'] and s['pret'] and s['credit_restant_estime'] == 5.0, s)


def cas_reponses():
    remise()
    cl = installer(FauxClient([reponse(texte='', stop='refusal', details={'category': 'cyber'},
                                       usage={'input_tokens': 500, 'output_tokens': 40})]))
    r = appel()
    verifier('refus de securite : pas ok, phrase claire', not r['ok'] and 'refusé' in r['raison'] and 'cyber' in r['raison']
             and r['donnees'] is None, r['raison'])
    verifier('refus : cout inscrit quand meme', abs(r['cout'] - 0.0014) < 1e-9 and abs(ca.depense_video('video1/script') - 0.0014) < 1e-9, r['cout'])
    installer(FauxClient([reponse(texte='{"ok": tr', stop='max_tokens')]))
    r = appel()
    verifier('reponse coupee (max_tokens)', not r['ok'] and 'coupée' in r['raison'], r['raison'])
    installer(FauxClient([reponse(texte='pas du json')]))
    r = appel()
    verifier('JSON illisible', not r['ok'] and 'illisible' in r['raison'], r['raison'])
    fb = [SimpleNamespace(type='text', text='{"ok": fa'), SimpleNamespace(type='fallback'),
          SimpleNamespace(type='text', text='{"ok": true}')]
    installer(FauxClient([reponse(content=fb, model='claude-sonnet-5',
                                  usage={'input_tokens': 0, 'output_tokens': 0,
                                         'iterations': [{'type': 'message', 'input_tokens': 100, 'output_tokens': 10},
                                                        {'type': 'fallback_message', 'input_tokens': 100, 'output_tokens': 10}]})]))
    r = appel()
    verifier('repli serveur en cours de reponse : JSON du modele de repli', r['ok'] and r['donnees'] == {'ok': True}
             and r['repli'] and r['modele'] == 'claude-sonnet-5', r)
    ln = json.loads(ca.JOURNAL.read_text(encoding='utf-8').splitlines()[-1])
    verifier('journal : modele servi + modele demande', ln['modele'] == 'claude-sonnet-5' and ln['modele_demande'] == 'claude-sonnet-5-5'
             and ln['repli'] is True, ln)


def cas_erreurs():
    cas = [
        ('cle refusee (401)', erreur(anthropic.AuthenticationError, 401, f'invalid x-api-key {FAUSSE}', 'authentication_error'), 'clé refusée'),
        ('acces refuse (403)', erreur(anthropic.PermissionDeniedError, 403, 'no access', 'permission_error'), 'accès refusé'),
        ('limite (429)', erreur(anthropic.RateLimitError, 429, 'rate limited', 'rate_limit_error'), 'limite'),
        ('panne (500)', erreur(anthropic.InternalServerError, 500, 'boom', 'api_error'), 'réessaie plus tard'),
        ('surcharge (529)', erreur(anthropic.OverloadedError, 529, 'overloaded', 'overloaded_error'), 'réessaie plus tard'),
        ('hors ligne', anthropic.APIConnectionError(request=_req()), 'hors ligne'),
        ('delai depasse', anthropic.APITimeoutError(request=_req()), 'à temps'),
        ('erreur imprevue (cle dans le message)', RuntimeError(f'boom {FAUSSE}'), 'inattendue'),
    ]
    for nom, exc, mot in cas:
        remise()
        cl = installer(FauxClient([exc]))
        r = appel()
        verifier(f'{nom} : phrase claire, chemin local', not r['ok'] and mot in r['raison'].lower() and 'local' in r['raison']
                 and MORCEAU not in r['raison'] and len(cl.appels) == 1, r['raison'])
    ln = json.loads(ca.JOURNAL.read_text(encoding='utf-8').splitlines()[-1])
    verifier('erreur inscrite au journal (sans la cle)', ln['ok'] is False and ln['type_erreur'] == 'autre'
             and MORCEAU not in json.dumps(ln), ln)
    remise()
    installer(FauxClient([anthropic.APITimeoutError(request=_req())]))
    r = appel()
    verifier('delai : note « cout inconnu »', 'coût inconnu' in r['note'], r['note'])
    remise()
    ca._client = lambda k: (_ for _ in ()).throw(RuntimeError(f'client {FAUSSE}'))
    ca._cle = lambda: FAUSSE
    r = appel()
    verifier('client impossible a creer : pas d\'exception', not r['ok'] and MORCEAU not in r['raison'], r['raison'])


def cas_registre():
    remise()
    installer(FauxClient([reponse(usage={'input_tokens': 1000, 'output_tokens': 100}) for _ in range(3)]))
    for _ in range(3):
        appel()
    total = round(sum(json.loads(x)['cout'] for x in ca.JOURNAL.read_text(encoding='utf-8').splitlines()), 6)
    ca.REGISTRE.write_text('{ abime', encoding='utf-8')
    with open(ca.JOURNAL, 'ab') as f:
        f.write(b'{"date": "2026-10-02T1')  # ligne coupee : ignoree
    s = stat()
    reg = json.loads(ca.REGISTRE.read_text(encoding='utf-8'))
    verifier('registre abime -> reconstruit depuis le journal', abs(s['depense_jour'] - total) < 1e-4 and s['appels_jour'] == 3
             and ca._valide(reg), (s['depense_jour'], total))
    verifier('registre abime garde a cote (.abime)', ca.REGISTRE.with_name(ca.REGISTRE.name + '.abime').exists())
    ca.REGISTRE.write_text('[1, 2]', encoding='utf-8')
    s = stat()
    verifier('registre de forme inattendue -> reconstruit', s['appels_jour'] == 3, s['appels_jour'])
    installer(FauxClient([reponse(usage={'input_tokens': 1000, 'output_tokens': 100})]))
    appel()
    ca.REGISTRE.unlink()
    s = stat()
    verifier('ligne coupee du journal : l\'appel suivant n\'est pas perdu', s['appels_jour'] == 4, s['appels_jour'])
    v = ca.couts('video1/script', 3)
    sorties.append(v)
    verifier('couts d\'une video : ses appels detailles', v['video']['nb'] == 4 and len(v['video']['appels']) == 4
             and set(v['video']['appels'][0]) == {'date', 'tache', 'modele', 'jetons', 'cout', 'request_id', 'ok', 'erreur'}
             and set(v['video']['appels'][0]['jetons']) == {'entree', 'sortie', 'cache_lu', 'cache_ecrit', 'images'}, v['video'])
    verifier('couts : 3 jours + credit', len(v['jours']) == 3 and 'restant_estime' in v['credit'], v.keys())
    s = stat()
    verifier('dernier appel', s['dernier_appel'] and set(s['dernier_appel']) == {'date', 'tache', 'cout', 'modele'}, s['dernier_appel'])
    textes = ca.JOURNAL.read_text(encoding='utf-8') + ca.REGISTRE.read_text(encoding='utf-8')
    verifier('journal et registre : jamais l\'invite', SYS_SECRET not in textes and TXT_SECRET not in textes)


def cas_pret():
    remise()
    cl = installer(FauxClient(), cle=None)
    s = stat()
    verifier('pas de cle : pas pret, phrase claire', not s['cle'] and not s['pret'] and 'clé' in s['raison'], s['raison'])
    r = appel()
    verifier('pas de cle : aucun appel', not r['ok'] and not cl.appels and 'Aucune clé' in r['raison'], r['raison'])
    remise({'actif': False})
    installer(cl)
    s = stat()
    r = appel()
    verifier('Claude eteint : pas pret, aucun appel', not s['pret'] and 'éteint' in s['raison'] and not r['ok'] and not cl.appels)
    remise()
    s = stat()
    attendu = {'cle', 'actif', 'modele', 'modeles_taches', 'plafonds', 'depense_jour', 'depense_mois', 'credit_restant_estime',
               'appels_jour', 'dernier_appel', 'credit_epuise', 'pret', 'raison'}
    verifier('statut : champs attendus', attendu <= set(s) and s['pret'] and s['cle'] is True and s['dernier_appel'] is None
             and s['modele'] == 'claude-sonnet-5-5' and s['credit_restant_estime'] == 2.0, sorted(set(attendu) - set(s)))
    r = ca.appeler('cerveau', SYS_SECRET, '   ', SCHEMA)
    verifier('contenu vide : refus sans appel', not r['ok'] and 'vide' in r['raison'] and not cl.appels)
    r = ca.appeler('cerveau', SYS_SECRET, 'x', None)
    verifier('schema manquant : refus sans appel', not r['ok'] and 'Schéma' in r['raison'] and not cl.appels)


def cas_reglages():
    remise()
    r = ca.reglages()
    lu = json.loads(ca.REGLAGES.read_text(encoding='utf-8'))
    verifier('reglages par defaut crees', r == ca.DEFAUTS and lu == ca.DEFAUTS, lu)
    verifier('defauts : Sonnet 5.5, plafonds 0,25 / 0,75 / 2 $, credit 2 $',
             r['modele'] == 'claude-sonnet-5-5' and (r['plafond_video'], r['plafond_jour'], r['plafond_mois']) == (0.25, 0.75, 2.0)
             and r['credit_depart'] == 2.0 and r['critique_auto'] is False and r['effort_consigne'] == 'low')
    mauvais = [
        {'modele': 'claude-opus-4-1'}, {'modele': 'gpt-4o'}, {'effort_cerveau': 'xhigh'}, {'effort_critique': 'max'},
        {'plafond_jour': -1}, {'plafond_mois': 1001}, {'plafond_video': 'beaucoup'}, {'plafond_video': True},
        {'credit_depart': float('nan')}, {'credit_date': '2026-13-01'}, {'credit_date': '02/10/2026'},
        {'credit_date': '2026-W40-5'}, {'images_critique': 0}, {'images_critique': 49}, {'images_critique': 2.5},
        {'largeur_images': 100}, {'actif': 'oui'}, {'inconnu': 1}, {'modeles_taches': {'montage': 'claude-haiku-4-5'}},
        {'modeles_taches': {'critique': 'claude-3-opus'}}, {'modeles_taches': 'claude-haiku-4-5'}, {}, [],
        {'espace_travail': 'mon-espace'}, {'espace_travail': 12},
    ]
    refuses = 0
    for p in mauvais:
        try:
            ca.ecrire_reglages(p)
        except ValueError as e:
            refuses += 1 if str(e) and any(c in str(e) for c in 'éèàÉ:') else 0
    verifier(f'reglages refuses ({len(mauvais)} cas, phrase en francais)', refuses == len(mauvais), refuses)
    verifier('fichier inchange apres les refus', json.loads(ca.REGLAGES.read_text(encoding='utf-8')) == ca.DEFAUTS)
    try:
        ca.ecrire_reglages({'plafond_jour': 0.5, 'modele': 'mauvais'})
        tout_ou_rien = False
    except ValueError:
        tout_ou_rien = ca.reglages()['plafond_jour'] == 0.75
    verifier('tout ou rien', tout_ou_rien)
    r = ca.ecrire_reglages({'modele': 'claude-haiku-4-5', 'effort_cerveau': 'high', 'plafond_jour': 0.5, 'images_critique': 20,
                            'credit_date': '2026-10-15', 'credit_depart': 3, 'modeles_taches': {'critique': 'claude-opus-5-5'}})
    verifier('reglages acceptes', r['modele'] == 'claude-haiku-4-5' and r['effort_cerveau'] == 'high' and r['plafond_jour'] == 0.5
             and r['images_critique'] == 20 and r['credit_date'] == '2026-10-15' and r['credit_depart'] == 3.0
             and r['modeles_taches'] == {'cerveau': None, 'critique': 'claude-opus-5-5', 'consigne': None}, r)
    r = ca.ecrire_reglages({'modeles_taches': {'cerveau': 'claude-sonnet-5-5'}})
    verifier('modele par tache : fusion', r['modeles_taches'] == {'cerveau': 'claude-sonnet-5-5', 'critique': 'claude-opus-5-5',
                                                                 'consigne': None}, r['modeles_taches'])
    r = ca.ecrire_reglages({'modeles_taches': None})
    verifier('modele par tache : null remet tout au general', r['modeles_taches'] == {t: None for t in ca.TACHES})
    r1 = ca.ecrire_reglages({'espace_travail': ' wrkspc_011CZkZaBF1tNoB5wlCeusgy '})['espace_travail']
    r2 = ca.ecrire_reglages({'espace_travail': ''})['espace_travail']
    verifier('espace de travail : accepte (espaces retires), vide = aucun', r1 == 'wrkspc_011CZkZaBF1tNoB5wlCeusgy' and r2 is None)
    ca.REGLAGES.write_text('{"modele": "claude-opus-5-5", "plafond_jour": -4, "effort_critique": "max", "modeles_taches": '
                           '{"critique": "inconnu", "consigne": "claude-haiku-4-5"}}', encoding='utf-8')
    r = ca.reglages()
    verifier('fichier edite a la main : valeurs abimees = defaut', r['modele'] == 'claude-opus-5-5' and r['plafond_jour'] == 0.75
             and r['effort_critique'] == 'medium' and r['modeles_taches'] == {'cerveau': None, 'critique': None,
                                                                             'consigne': 'claude-haiku-4-5'}, r)
    ca.REGLAGES.write_text('{ abime', encoding='utf-8')
    verifier('fichier illisible : defauts, fichier garde', ca.reglages() == ca.DEFAUTS
             and ca.REGLAGES.read_text(encoding='utf-8') == '{ abime')


def cas_cli():
    remise()
    installer(FauxClient([reponse()]))
    appel()  # une depense pour la ligne de commande
    env = dict(os.environ, EDITEUR_ROOT=str(BAC), ANTHROPIC_API_KEY=FAUSSE, PYTHONIOENCODING='utf-8')
    env['TEMP'] = env['TMP'] = str(BAC / 'tmp')
    (BAC / 'tmp').mkdir(parents=True, exist_ok=True)

    def cli(*args, **kw):
        p = subprocess.run([sys.executable, '-m', 'editeur', 'claude', *args], cwd=str(ROOT / 'engine'), env=kw.get('env', env),
                           capture_output=True, text=True, encoding='utf-8', timeout=180)
        sorties.append(p.stdout + p.stderr)
        return p
    p = cli('statut')
    s = json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 and p.stdout.strip() else {}
    verifier('CLI statut : JSON, cle presente, rien de secret', p.returncode == 0 and s.get('cle') is True and s.get('appels_jour') == 1
             and MORCEAU not in p.stdout, p.stderr[-300:] or s)
    p = cli('reglages', '--json', '{"plafond_jour": 0.5}')
    verifier('CLI reglages --json', p.returncode == 0 and json.loads(p.stdout)['plafond_jour'] == 0.5, p.stderr[-200:])
    p = cli('reglages', '--json', '{"modele": "gpt-4o"}')
    verifier('CLI reglage refuse : phrase seule, code 1', p.returncode == 1 and 'Modèle inconnu' in p.stderr and 'Traceback' not in p.stderr,
             p.stderr[-200:])
    p = cli('reglages', '--json', '{abime')
    verifier('CLI JSON illisible', p.returncode == 1 and 'illisible' in p.stderr, p.stderr[-200:])
    p = cli('couts', '--video', 'video1/script', '--jours', '3')
    c = json.loads(p.stdout) if p.returncode == 0 else {}
    verifier('CLI couts --video', p.returncode == 0 and c['video']['nb'] == 1 and len(c['jours']) == 3, p.stderr[-200:])
    p = cli('test', '--modele', 'gpt-4o')
    verifier('CLI test --modele inconnu : refus sans appel', p.returncode == 1 and 'Modèle inconnu' in p.stderr, p.stderr[-200:])
    sans = {k: v for k, v in env.items() if k != 'ANTHROPIC_API_KEY'}
    p = cli('statut', env=sans)
    s = json.loads(p.stdout) if p.returncode == 0 else {}
    verifier('CLI statut sans cle : pas pret', p.returncode == 0 and s.get('cle') is False and not s.get('pret'), p.stderr[-200:])


def cas_sdk_local():
    """Le VRAI SDK anthropic, mais branche sur un faux transport local (aucun reseau, aucun appel facture) : verifie la
    requete telle qu'elle partirait (en-tetes, corps JSON) et la lecture des vraies classes de reponse du SDK."""
    vus = []
    file_rep = []

    def transport(req):
        vus.append({'url': str(req.url), 'beta': req.headers.get('anthropic-beta'), 'espace': req.headers.get('anthropic-workspace-id'),
                    'cle_ok': req.headers.get('x-api-key') == FAUSSE, 'corps': json.loads(req.content.decode('utf-8'))})
        code, corps = file_rep.pop(0)
        return httpx2.Response(code, json=corps, headers={'request-id': f'req_mock_{len(vus)}'})

    def msg(model, texte='{"ok": true}', usage=None):
        return (200, {'id': 'msg_1', 'type': 'message', 'role': 'assistant', 'model': model,
                      'content': [{'type': 'text', 'text': texte}], 'stop_reason': 'end_turn', 'stop_sequence': None,
                      'usage': usage or {'input_tokens': 200, 'output_tokens': 12, 'cache_creation_input_tokens': 0,
                                         'cache_read_input_tokens': 0}})

    def err(code, genre, texte):
        return (code, {'type': 'error', 'error': {'type': genre, 'message': texte}})

    ca._client = ORIGINAL['client']  # le vrai _client (en-tetes, delai, tentatives) avec un faux transport
    ca._TRANSPORT_TEST = httpx2.MockTransport(transport)
    ca._cle = lambda: FAUSSE
    remise()
    file_rep[:] = [msg('claude-sonnet-5-5')]
    r = appel()
    c = vus[-1]['corps']
    verifier('SDK local Sonnet : en-tete beta + corps', r['ok'] and vus[-1]['beta'] == 'server-side-fallback-2026-07-01'
             and c.get('fallbacks') == 'default' and c['output_config'].get('effort') == 'medium' and 'thinking' not in c
             and 'betas' not in c and c['output_config']['format']['type'] == 'json_schema'
             and c['system'][0].get('cache_control') == {'type': 'ephemeral'}, {k: c.get(k) for k in ('fallbacks', 'output_config')})
    verifier('SDK local : request_id + cout lus sur la vraie reponse', r['request_id'] == 'req_mock_1'
             and abs(r['cout'] - (200 * 2 + 12 * 10) / 1e6) < 1e-12, (r['request_id'], r['cout']))
    file_rep[:] = [msg('claude-haiku-4-5')]
    r = appel(modele='claude-haiku-4-5')
    c = vus[-1]['corps']
    verifier('SDK local Haiku : ni beta, ni effort, ni repli', r['ok'] and not vus[-1]['beta'] and 'fallbacks' not in c
             and 'effort' not in c['output_config'] and 'thinking' not in c, vus[-1]['beta'])
    file_rep[:] = [err(400, 'invalid_request_error', 'fallbacks: Extra inputs are not permitted'), msg('claude-sonnet-5-5')]
    r = appel()
    verifier('SDK local : 400 sur le repli -> relance sans en-tete beta', r['ok'] and not vus[-1]['beta']
             and 'fallbacks' not in vus[-1]['corps'], vus[-1]['beta'])
    remise()
    file_rep[:] = [err(400, 'invalid_request_error', CREDIT_400)]
    r = appel()
    verifier('SDK local : credit epuise (vraie BadRequestError)', r['raison'] == ca.CREDIT_EPUISE and stat()['credit_epuise'], r['raison'])
    remise()
    file_rep[:] = [err(401, 'authentication_error', 'invalid x-api-key')]
    r = appel()
    verifier('SDK local : 401 -> cle refusee', 'clé refusée' in r['raison'].lower(), r['raison'])
    file_rep[:] = [(200, {'id': 'msg_2', 'type': 'message', 'role': 'assistant', 'model': 'claude-sonnet-5-5', 'content': [],
                          'stop_reason': 'refusal', 'stop_sequence': None, 'stop_details': {'type': 'refusal', 'category': 'bio'},
                          'usage': {'input_tokens': 50, 'output_tokens': 0}})]
    r = appel()
    verifier('SDK local : refus de securite lu', not r['ok'] and 'refusé' in r['raison'], r['raison'])
    # cle d'organisation sans espace de travail (vrai message d'Anthropic du 2026-10-02, appel non facture)
    remise()
    file_rep[:] = [err(400, 'invalid_request_error', 'This API key is not scoped to a workspace, so this request must '
                       'include the anthropic-workspace-id header with the ID of the workspace to use.')]
    r = appel()
    s = stat()
    n = len(vus)
    verifier('SDK local : cle sans espace de travail -> phrase claire, pas de relance', r['raison'] == ca.ESPACE_MANQUANT
             and not s['pret'] and s['espace_manquant'] and not vus[-1]['espace'], r['raison'])
    r = appel()
    verifier('… puis plus aucune demande inutile pendant 10 min', not r['ok'] and len(vus) == n and r['raison'] == ca.ESPACE_MANQUANT)
    ca.ecrire_reglages({'espace_travail': 'wrkspc_011CZkZaBF1tNoB5wlCeusgy'})
    s = stat()
    file_rep[:] = [msg('claude-sonnet-5-5')]
    r = appel()
    verifier('espace de travail indique : en-tete anthropic-workspace-id, corps inchange', s['pret'] and s['espace_travail']
             and r['ok'] and vus[-1]['espace'] == 'wrkspc_011CZkZaBF1tNoB5wlCeusgy' and 'workspace_id' not in vus[-1]['corps'], vus[-1]['espace'])
    file_rep[:] = [err(403, 'permission_error', 'The workspace wrkspc_011CZkZaBF1tNoB5wlCeusgy is not accessible.')]
    r = appel()
    verifier('espace de travail refuse : phrase claire', 'espace de travail' in r['raison'] and 'wrkspc_' in r['raison'], r['raison'])
    remise()
    os.environ['ANTHROPIC_WORKSPACE_ID'] = 'wrkspc_0ABCDEFGH123456789'
    try:
        file_rep[:] = [msg('claude-haiku-4-5')]
        r = appel(modele='claude-haiku-4-5')
        verifier('espace de travail par ANTHROPIC_WORKSPACE_ID', r['ok'] and vus[-1]['espace'] == 'wrkspc_0ABCDEFGH123456789')
    finally:
        os.environ.pop('ANTHROPIC_WORKSPACE_ID', None)
        ca._TRANSPORT_TEST = None
        ca._clients.clear()
    verifier('SDK local : la cle part seulement dans l\'en-tete x-api-key', all(v['cle_ok'] for v in vus)
             and MORCEAU not in json.dumps([v['corps'] for v in vus]))
    sorties.extend(vus)


def cas_cle_nulle_part():
    trouves = []
    for f in BAC.rglob('*'):
        if f.is_file():
            try:
                if MORCEAU in f.read_text(encoding='utf-8', errors='replace'):
                    trouves.append(str(f.relative_to(BAC)))
            except OSError:
                pass
    texte = json.dumps(sorties, ensure_ascii=False, default=str)
    verifier('la cle n\'est dans AUCUN fichier du bac a sable', not trouves, trouves)
    verifier('la cle n\'est dans AUCUNE sortie (resultats, statut, CLI)', MORCEAU not in texte and FAUSSE not in texte)
    verifier('masquage d\'un texte qui cite la cle', MORCEAU not in ca._masquer(f'x {FAUSSE} y') and '[clé masquée]' in ca._masquer(FAUSSE))


if __name__ == '__main__':
    garder = '--garder' in sys.argv
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    BAC.mkdir(parents=True, exist_ok=True)
    os.environ['ANTHROPIC_API_KEY'] = FAUSSE  # le vrai chargeur ne remplace jamais une variable deja definie
    ca.REGLAGES = BAC / 'styles/claude.json'
    ca.REGISTRE = BAC / 'projects/_claude.json'
    ca.JOURNAL = BAC / 'runtime/cache/claude-appels.jsonl'
    ca.VERROU = BAC / 'runtime/cache/claude.lock'
    os.environ.pop('ANTHROPIC_WORKSPACE_ID', None)
    debut = time.time()
    try:
        for cas in (cas_prix, cas_forme, cas_relance, cas_budget, cas_credit, cas_reponses, cas_erreurs, cas_registre,
                    cas_pret, cas_reglages, cas_cli, cas_sdk_local, cas_cle_nulle_part):
            try:
                cas()
            except Exception as e:  # un cas qui plante ne doit pas cacher les autres
                import traceback
                verifier(f'{cas.__name__} (plantage)', False, traceback.format_exc()[-600:])
    finally:
        ca._client, ca._cle, ca._TRANSPORT_TEST = ORIGINAL['client'], ORIGINAL['cle'], None
        if not garder:
            shutil.rmtree(BAC, ignore_errors=True)
    ko = [b for b in bilan if not b['ok']]
    print(f'\n{len(bilan) - len(ko)}/{len(bilan)} vérifications réussies en {time.time() - debut:.1f} s'
          + (f' — bac à sable gardé : {BAC}' if garder else ''))
    sys.exit(1 if ko else 0)
