"""Tests du cerveau Claude (engine/editeur/cerveau_claude.py) et de ses branchements (auto._finish, reel.refresh_ai,
reel.rehighlight, galerie, creative, graphismes), SANS aucun appel reel : faux client Anthropic, fausse cle, faux Qwen
(llm remplace), reglages / registre / journal de claude_api et COPIE de projects/script1 (project.json + reels/script.json)
dans un bac a sable runtime/cache/tmp/<unique>. Le vrai projet n'est que lu.

    cd D:\\Tools\\editeur_sami\\engine
    ..\\runtime\\venv\\Scripts\\python.exe ..\\docs\\claude-api\\tests\\test_cerveau.py [--garder]

Cas : invite compacte (taille mesuree, estimation $ avec Sonnet 5.5 et Haiku 4.5) ; forme de la requete (Sonnet : effort +
repli ; Haiku : rien de plus) ; verification (mots outils, idees, chiffres inventes, accroche, cartes, bandeau,
corrections) ; corrections seulement sur les mots listes (temps gardes) ; signature : 2e lecture, changement de style,
« Relancer l'IA », nouveau montage des memes mots = aucun nouvel appel, montage change ou --forcer = un appel ; Claude
eteint / pas de cle / plafond / hors ligne / refus -> chemin Qwen inchange ; retouches a la main (hlAuto) et verrous ;
branchements (mots en couleur, plan creatif, notifications, bouton, graphismes, bandeau, auto._finish) ; rien sur
l'accroche sauf le bandeau ; ligne de commande ; la cle jamais ecrite. Relecture du 2 oct. 2026 (cas_revue) : nombres en
lettres et negation jamais « corriges », appel paye sans resultat jamais repaye, correction defaite a la main jamais
reposee, mots forts tous faux -> regles, plan change -> IA locale pour ses notifications, bandeau ecarte -> chemin local,
habiller sans bandeau ni graphisme en double, un seul cerveau a la fois par montage (verrou, 2e processus).
--garder : ne supprime pas le bac a sable a la fin."""
import contextlib
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

ICI = Path(__file__).resolve().parent
ROOT = ICI.parents[2]
sys.path.insert(0, str(ROOT / 'engine'))
# chemins de l'IA locale ACTIFS (pour verifier qu'ils restent ceux d'avant), mais llm est remplace par un faux : aucun Qwen
os.environ['EDITEUR_LLM'] = '1'
os.environ['EDITEUR_CLAUDE'] = '1'
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
import anthropic  # noqa: E402
import httpx2  # noqa: E402
from editeur import auto, claude_api as ca, cerveau_claude as cc, creative, galerie, graphismes, llm, montage  # noqa: E402
from editeur import reel as reelmod, sobriete, verrous  # noqa: E402

SOURCE = ROOT / 'projects' / 'script1'
FAUSSE = 'sk-ant-api03-FAUSSE-CLE-cerveau-0123456789abcdefXYZ'
MORCEAU = 'FAUSSE-CLE-cerveau'
BAC = ROOT / 'runtime/cache/tmp' / f'test-cerveau-claude-{uuid.uuid4().hex[:10]}'
PROJ = BAC / 'script1'
bilan = []
mesures = {}


def verifier(nom, ok, detail=''):
    bilan.append({'test': nom, 'ok': bool(ok), 'detail': str(detail)[:300]})
    print(('OK   ' if ok else 'ECHEC') + f' {nom}' + (f' — {str(detail)[:300]}' if detail and not ok else ''))


# ---------- faux Claude ----------
class FauxMessages:
    def __init__(self, parent, beta):
        self.parent, self.beta = parent, beta

    def create(self, **p):
        self.parent.appels.append(('beta' if self.beta else 'messages', copy.deepcopy(p)))
        r = self.parent.reponses.pop(0) if self.parent.reponses else self.parent.defaut(p)
        if isinstance(r, BaseException):
            raise r
        return r


class FauxClient:
    def __init__(self, donnees=None, toujours=None):
        self.appels, self.reponses = [], []
        self.donnees, self.toujours = donnees, toujours  # toujours : reponse ou erreur rendue a CHAQUE appel
        self.messages = FauxMessages(self, False)
        self.beta = SimpleNamespace(messages=FauxMessages(self, True))

    def defaut(self, p):
        if self.toujours is not None:
            return self.toujours
        return reponse(self.donnees if self.donnees is not None else REPONSE(), p)


def reponse(donnees, p=None, stop='end_turn', model=None):
    texte = json.dumps(donnees, ensure_ascii=False)
    sys_txt = ''.join(b['text'] for b in (p or {}).get('system') or [])
    user = ''.join(b.get('text', '') for b in (p or {}).get('messages', [{}])[0].get('content', []))
    # usage realiste : ~3,8 caracteres par jeton en francais ; reflexion adaptative (Sonnet / Opus) comptee en sortie
    sortie = int(len(texte) / 3.8) + (2500 if (p or {}).get('betas') else 0)
    u = {'input_tokens': int(len(user) / 3.8) + 400, 'output_tokens': sortie, 'cache_read_input_tokens': 0,
         'cache_creation_input_tokens': int(len(sys_txt) / 3.8)}
    return SimpleNamespace(stop_reason=stop, stop_details=None, model=model or (p or {}).get('model', 'claude-sonnet-5-5'),
                           _request_id='req_faux_cerveau', usage=u, content=[SimpleNamespace(type='text', text=texte)])


def installer(client, cle=FAUSSE):
    def fabrique(k):
        assert k == FAUSSE, 'une vraie cle ne doit jamais etre utilisee dans ce test'
        return client
    ca._client = fabrique
    ca._cle = lambda: cle
    return client


# ---------- faux Qwen (llm) ----------
class FauxQwen:
    def __init__(self):
        self.appels = []

    def ask_json(self, system, user, temperature=0.3, max_tokens=2000):
        u = str(user)
        if 'notification de telephone' in u or 'phone notification' in u:
            self.appels.append('notifications')
            n = sum(1 for ligne in u.splitlines() if ligne[:1].isdigit())
            return {'notifications': [{'n': k + 1, 'titre': 'Nouveau message'} for k in range(n)]}
        if '"benefices"' in u:
            self.appels.append('benefices')
            return {'benefices': ['Setter qualifié', 'Réponse rapide', 'Sans risque'], 'benefices_titre': 'Avantages',
                    'benefices_debut': 'setter', 'mot_choc': 'gratuitement'}
        if 'Relis ce titre court' in u:
            self.appels.append('bandeau')
            titre = u.split('Titre : ', 1)[-1].split('\n', 1)[0]
            return {'probleme': '', 'titre': titre}
        if 'Relis ces titres courts' in u:
            self.appels.append('relecture')
            return {'ok': [True] * u.count('\n- ')}
        if "Voici la transcription d'un reel" in u:
            self.appels.append('editorial')
            return {'bandeaux': ['QWEN : VOTRE CONCURRENT APPELLE'], 'plans': {}}
        self.appels.append('autre')
        return {}


QWEN = FauxQwen()
llm.available = lambda: True
llm.session = contextlib.contextmanager(lambda vision=False: (yield))
llm.ask_json = QWEN.ask_json


# ---------- bac a sable ----------
def bac_claude():
    d = BAC / 'claude'
    d.mkdir(parents=True, exist_ok=True)
    ca.REGLAGES, ca.REGISTRE, ca.JOURNAL, ca.VERROU = d / 'claude.json', d / '_claude.json', d / 'appels.jsonl', d / 'claude.lock'
    for f in (ca.REGLAGES, ca.REGISTRE, ca.JOURNAL):
        f.unlink(missing_ok=True)
    ca._sans_session.clear()
    ca._en_cours.clear()
    ca._clients.clear()


TYPOS = {('c4', 0): 'Pi', ('c4', 54): 'transférez', ('c5', 16): 'appuyer'}  # fautes de transcription d'origine


def projet(typos=True, mutation=None):
    """Copie neuve de projects/script1 (lecture seule de l'original), avec les fautes de transcription d'origine."""
    if PROJ.exists():
        shutil.rmtree(PROJ)
    (PROJ / 'reels').mkdir(parents=True)
    shutil.copyfile(SOURCE / 'project.json', PROJ / 'project.json')
    r = json.loads((SOURCE / 'reels' / 'script.json').read_text(encoding='utf-8'))
    r.pop('claude', None)
    if typos:
        for c in r['clips']:
            for (cid, i), w in TYPOS.items():
                if c['id'] == cid:
                    c['words'][i]['w'] = w
                    c['words'][i].pop('asr', None)
    if mutation:
        mutation(r)
    montage.save(PROJ, 'script', r)
    galerie._TITLES.clear()
    QWEN.appels.clear()
    return r


def charger():
    return montage.load(PROJ, 'script')


def mot(r, cid, i):
    return next(c for c in r['clips'] if c['id'] == cid)['words'][i]


# ---------- reponse de Claude pour Video 1 (indices de la vraie transcription) ----------
def M(clip, i):
    return {'clip': clip, 'i': i}


def REPONSE():
    return {
        'message': 'Un setter formé répond à vos leads tout de suite, cinq fois moins cher qu’un employé.',
        'public': 'agences et entreprises qui achètent des leads',
        'promesse': 'Payer cinq fois moins cher qu’un employé',
        'beats': [
            {'role': 'accroche', 'debut_mot': M('c1', 0), 'fin_mot': M('c1', 18), 'raison': 'le concurrent rafle le lead'},
            {'role': 'tension', 'debut_mot': M('c1', 19), 'fin_mot': M('c2', 63), 'raison': 'coût d’un employé et lead perdu'},
            {'role': 'solution', 'debut_mot': M('c3', 0), 'fin_mot': M('c3', 26), 'raison': 'setter placé chez vous'},
            {'role': 'preuve', 'debut_mot': M('c3', 27), 'fin_mot': M('c3', 49), 'raison': 'cinq fois moins cher'},
            {'role': 'explication', 'debut_mot': M('c4', 0), 'fin_mot': M('c4', 54), 'raison': 'formation et intérêt commun'},
            {'role': 'cta', 'debut_mot': M('c5', 0), 'fin_mot': M('c5', 60), 'raison': 'essai gratuit une semaine'},
        ],
        'mots_forts': [
            {'clip': 'c1', 'i0': 16, 'i1': 16, 'raison': 'le rival'},
            {'clip': 'c1', 'i0': 13, 'i1': 13, 'raison': 'même idée que concurrent'},   # meme idee : ecarte
            {'clip': 'c1', 'i0': 1, 'i1': 1, 'raison': 'mot outil'},                    # « vous » : ecarte
            {'clip': 'c1', 'i0': 17, 'i1': 17, 'raison': 'mot outil'},                  # « le » : ecarte
            {'clip': 'c1', 'i0': 47, 'i1': 47, 'raison': 'bénéfice'},
            {'clip': 'c2', 'i0': 10, 'i1': 15, 'raison': 'trop long'},                  # 6 mots : ecarte
            {'clip': 'c2', 'i0': 15, 'i1': 15, 'raison': 'coût'},
            {'clip': 'c2', 'i0': 55, 'i1': 56, 'raison': 'chiffre et unité'},
            {'clip': 'c3', 'i0': 5, 'i1': 5, 'raison': 'marque'},
            {'clip': 'c3', 'i0': 35, 'i1': 38, 'raison': 'la preuve chiffrée'},
            {'clip': 'c4', 'i0': 32, 'i1': 32, 'raison': 'intérêt'},
            {'clip': 'c4', 'i0': 45, 'i1': 45, 'raison': 'verbe fort'},
            {'clip': 'c5', 'i0': 21, 'i1': 23, 'raison': 'texte du bouton'},
            {'clip': 'c5', 'i0': 37, 'i1': 37, 'raison': 'l’offre'},
            {'clip': 'c9', 'i0': 0, 'i1': 0, 'raison': 'plan inconnu'},                 # ecarte
            {'clip': 'c3', 'i0': 70, 'i1': 70, 'raison': 'hors du plan'},               # ecarte
        ],
        'corrections': [
            {'clip': 'c4', 'i': 0, 'avant': 'Pi', 'apres': 'Puis', 'raison': 'mot mal entendu'},
            {'clip': 'c4', 'i': 54, 'avant': 'transférez', 'apres': 'transférer', 'raison': 'infinitif après de'},
            {'clip': 'c5', 'i': 16, 'avant': 'appuyer', 'apres': 'appuyez', 'raison': 'consigne à vous'},
            {'clip': 'c3', 'i': 37, 'avant': 'moins', 'apres': 'plus', 'raison': 'sens inversé'},          # ecarte
            {'clip': 'c3', 'i': 35, 'avant': 'cinq', 'apres': 'six', 'raison': 'chiffre changé'},           # ecarte
            {'clip': 'c3', 'i': 5, 'avant': 'RyuCalls', 'apres': 'RyuCall', 'raison': 'nom propre'},        # ecarte
            {'clip': 'c2', 'i': 36, 'avant': 'fermés', 'apres': 'closés', 'raison': 'pas le bon mot'},     # ecarte
            {'clip': 'c1', 'i': 27, 'avant': 'entreprise', 'apres': 'entreprise du Québec', 'raison': 'deux mots'},  # ecarte
        ],
        'bandeau': {'texte': 'Votre concurrent appelle vos leads'},
        'cartes': [
            {'beat': 0, 'type': 'notification', 'texte': 'Nouveau lead', 'secondaire': '', 'raison': 'accroche'},       # ecarte
            {'beat': 1, 'type': 'notification', 'texte': 'Lead qui attend depuis 3 h', 'secondaire': '', 'raison': 'attente'},
            {'beat': 1, 'type': 'liste', 'texte': 'Coûts d’un employé',
             'secondaire': 'Salaire|Avantages sociaux|Vacances|Journées de maladie', 'raison': 'les coûts'},
            {'beat': 2, 'type': 'liste', 'texte': 'Votre setter',
             'secondaire': 'Setter qualifié|Formé par nos soins|Réponse rapide', 'raison': 'bénéfices'},
            {'beat': 3, 'type': 'chiffre', 'texte': '5× moins cher', 'secondaire': '', 'raison': 'preuve'},
            {'beat': 3, 'type': 'notification', 'texte': 'Gagnez 10 clients', 'secondaire': '', 'raison': 'invente'},  # ecarte
            {'beat': 4, 'type': 'mot', 'texte': 'pourcentage', 'secondaire': '', 'raison': 'intérêt commun'},
            {'beat': 5, 'type': 'bouton', 'texte': 'En savoir plus', 'secondaire': '1 semaine gratuite', 'raison': 'action'},
            {'beat': 9, 'type': 'mot', 'texte': 'leads', 'secondaire': '', 'raison': 'temps inconnu'},                  # ecarte
        ],
        'cta': {'clip': 'c5', 'i0': 16},
        'titre': 'Un setter chez vous, cinq fois moins cher',
    }


def lancer(**kw):
    return cc.lancer(PROJ, 'script', info={'type': 'pub', 'typeLabel': 'Marketing / pub'}, style='produit-3d', **kw)


# ---------- cas ----------
def cas_invite():
    r = projet()
    project = json.loads((PROJ / 'project.json').read_text(encoding='utf-8'))
    systeme, contenu = cc.invite(r, {'type': 'pub', 'typeLabel': 'Marketing / pub'}, 'produit-3d', cc._marque(r), project)
    verifier('invite : transcription numerotee par plan', '[c1]' in contenu and '0:Plus' in contenu and '54:transférez' in contenu)
    verifier('invite : script ecrit, sujet, marque et regles du style', all(x in contenu for x in (
        'Script écrit', 'Marketing / pub', 'RyuCalls', 'Tech 3D', 'rien d\'autre que le bandeau', 'éléments par minute')), contenu[:400])
    verifier('invite : consigne systeme stable (sans rien de la video)', 'RyuCalls' not in systeme and '[c1]' not in systeme)
    coupe = projet(mutation=lambda x: x['clips'][0]['words'][5].__setitem__('cut', True))
    _, c2 = cc.invite(coupe, None, 'produit-3d', '', None)
    ligne = next(x for x in c2.splitlines() if x.startswith('0:Plus'))
    verifier('invite : un mot coupe n\'est pas envoye (numero absent)', '5:à' not in ligne and ' 4:temps 6:appeler' in ligne, ligne[:80])
    schema = json.dumps(cc.SCHEMA, ensure_ascii=False)
    car = {'systeme': len(systeme), 'contenu': len(contenu), 'schema': len(schema)}
    sortie = len(json.dumps(REPONSE(), ensure_ascii=False))
    j_in = {k: round(v / 3.8) for k, v in car.items()}
    j_in_haut = {k: round(v / 3.5) for k, v in car.items()}
    j_out = round(sortie / 3.8)

    def cout(m, entree_sys, entree_var, sortie_j):
        p = ca.prix(m)
        return (entree_sys * p['cache_ecrit'] + entree_var * p['entree'] + sortie_j * p['sortie']) / 1e6
    sonnet = [cout('claude-sonnet-5-5', j_in['systeme'], j_in['contenu'] + j_in['schema'] + 300, j_out + t) for t in (1500, 4000)]
    haiku = cout('claude-haiku-4-5', 0, j_in['systeme'] + j_in['contenu'] + j_in['schema'] + 300, j_out)
    mesures['invite'] = {'caracteres': car, 'jetons_entree_estimes': j_in, 'jetons_entree_haut': j_in_haut,
                         'jetons_sortie_reponse_type': j_out, 'cout_sonnet_5_5': [round(x, 4) for x in sonnet],
                         'cout_haiku_4_5': round(haiku, 4),
                         'estimation_haute_claude_api': ca.estimer(systeme, contenu, sortie=cc.SORTIE_MAX,
                                                                   modele='claude-sonnet-5-5', schema=cc.SCHEMA)}
    print(f"     invite : {car} caracteres -> ~{sum(j_in.values())} jetons d'entree ; reponse type ~{j_out} jetons ; "
          f"Sonnet 5.5 ~{sonnet[0]:.3f} a {sonnet[1]:.3f} $ (reflexion 1 500 a 4 000 jetons), Haiku 4.5 ~{haiku:.3f} $")
    verifier('invite compacte (moins de 10 000 caracteres a envoyer)', car['contenu'] < 10000, car)
    verifier('estimation haute sous le plafond par video (0,25 $)', mesures['invite']['estimation_haute_claude_api'] < 0.25,
             mesures['invite']['estimation_haute_claude_api'])


def cas_validation():
    r = projet()
    res, ecartes = cc.valider(r, REPONSE())
    mf = {(m['clip'], m['i0']) for m in res['mots_forts']}
    verifier('mots forts : mots outils ecartes (vous, le)', ('c1', 1) not in mf and ('c1', 17) not in mf)
    verifier('mots forts : meme idee ecartee (un seul mot par idee)', ('c1', 16) in mf and ('c1', 13) not in mf, mf)
    verifier('mots forts : plus de 4 mots, plan inconnu, hors du plan ecartes', ('c2', 10) not in mf and not any(
        c in ('c9',) for c, _ in mf) and ('c3', 70) not in mf)
    bons = {('c1', 47), ('c2', 15), ('c2', 55), ('c3', 5), ('c3', 35), ('c4', 32), ('c4', 45), ('c5', 21), ('c5', 37)}
    verifier('mots forts : les bons choix gardes', len(bons & mf) >= 8, sorted(mf))
    # aucune idee avec deux mots forts gardes
    clips = {c['id']: c for c in r['clips']}
    double = []
    for cid in {c for c, _ in mf}:
        for idee in reelmod.idea_groups(clips[cid]['words']):
            n = [m for m in res['mots_forts'] if m['clip'] == cid and m['i0'] in idee]
            if len(n) > 1:
                double.append((cid, n))
    verifier('mots forts gardes : jamais deux dans la meme idee', not double, double)
    co = {(k['clip'], k['i']): k['apres'] for k in res['corrections']}
    verifier('corrections : les 3 fautes de transcription gardees',
             co == {('c4', 0): 'Puis', ('c4', 54): 'transférer', ('c5', 16): 'appuyez'}, co)
    texte = ' | '.join(ecartes)
    # revue du 2 oct. 2026 : « cinq » -> « six » est refuse comme nombre en lettres (avant : « trop différent ») ; le cas
    # « trop différent » est verifie a part dans cas_revue
    verifier('corrections ecartees : sens, chiffre, nom propre, mot different, deux mots',
             all(x in texte for x in ('le sens changerait', '« cinq » -> « six » : un chiffre', 'nom propre', "n'est pas celui",
                                      'un seul mot')), texte)
    verifier('bandeau : garde en majuscules', res['bandeau'] == 'VOTRE CONCURRENT APPELLE VOS LEADS', res['bandeau'])
    types = sorted((k['beat'], k['type']) for k in res['cartes'])
    verifier('cartes : accroche, chiffre invente et temps inconnu ecartes',
             types == [(1, 'liste'), (1, 'notification'), (2, 'liste'), (3, 'chiffre'), (4, 'mot'), (5, 'bouton')], types)
    b = next(k for k in res['cartes'] if k['type'] == 'bouton')
    verifier('carte bouton : texte dit mot pour mot (ancre) et offre dite', b.get('ancre') == {'clip': 'c5', 'i': 21}
             and b['secondaire'] == '1 semaine gratuite', b)
    verifier('temps du recit : 6 gardes, accroche d\'abord', [x['role'] for x in res['beats']] ==
             ['accroche', 'tension', 'solution', 'preuve', 'explication', 'cta'])
    verifier('cta et titre gardes', res['cta'] == {'clip': 'c5', 'i0': 16} and res['titre'].startswith('Un setter'), (res['cta'], res['titre']))
    # variantes : bandeau invente, accroche trop longue, premier temps qui n'est pas l'accroche, carte en anglais
    v = REPONSE()
    v['bandeau'] = {'texte': 'GAGNEZ 10 CLIENTS PAR SEMAINE'}
    v['beats'] = [{'role': 'accroche', 'debut_mot': M('c1', 0), 'fin_mot': M('c2', 63), 'raison': ''},
                  {'role': 'solution', 'debut_mot': M('c3', 0), 'fin_mot': M('c5', 60), 'raison': ''}]
    v['cartes'] = [{'beat': 1, 'type': 'notification', 'texte': 'New lead received', 'secondaire': '', 'raison': ''},
                   {'beat': 1, 'type': 'bouton', 'texte': 'Réservez maintenant', 'secondaire': '', 'raison': ''}]
    res2, ec2 = cc.valider(r, v)
    t2 = ' | '.join(ec2)
    verifier('bandeau avec un chiffre non dit ecarte', res2['bandeau'] is None and 'chiffre' in t2, t2)
    fin = res2['beats'][0]['fin'] if res2['beats'] else None
    verifier('accroche trop longue raccourcie a une fin de phrase (12 s au plus)', fin == {'clip': 'c1', 'i': 39}
             and 'raccourcie' in t2, (fin, t2))
    verifier('carte en anglais et bouton non dit ecartes', not res2['cartes'] and 'autre langue' in t2 and 'mot pour mot' in t2, t2)
    v3 = REPONSE()
    v3['beats'][0]['role'] = 'tension'
    res3, ec3 = cc.valider(r, v3)
    verifier('premier temps autre que l\'accroche : plan des regles garde', res3['beats'] == [] and res3['cartes'] == [], ec3[:3])
    res4, _ = cc.valider(r, {'nimporte': 'quoi'})
    verifier('reponse vide ou de travers : rien garde, aucune erreur', not any(res4[k] for k in ('beats', 'mots_forts', 'corrections', 'cartes')))


def cas_appel_et_signature():
    bac_claude()
    projet()
    fc = installer(FauxClient())
    out = lancer()
    verifier('1er appel : ok, source claude', out.get('ok') and out.get('source') == 'claude' and len(fc.appels) == 1, out)
    kind, p = fc.appels[0]
    verifier('requete Sonnet 5.5 : beta de repli, effort des reglages, sortie structuree du schema', kind == 'beta'
             and p['model'] == 'claude-sonnet-5-5' and p['output_config'].get('effort') == 'medium'
             and p['output_config']['format']['schema'] == cc.SCHEMA and p['max_tokens'] == cc.SORTIE_MAX
             and p.get('fallbacks') == 'default' and 'thinking' not in p and 'tool_choice' not in p, {k: p.get(k) for k in ('model', 'max_tokens')})
    verifier('consigne systeme mise en cache, contenu a part', p['system'][-1].get('cache_control') == {'type': 'ephemeral'}
             and p['system'][0]['text'] == cc.SYSTEME and '[c1]' in p['messages'][0]['content'][0]['text'])
    r = charger()
    e = (r.get('claude') or {}).get('cerveau') or {}
    verifier('resultat garde dans reel.claude.cerveau {signature, modele, date, cout, resultat}',
             all(k in e for k in ('signature', 'modele', 'date', 'cout', 'resultat')) and e['signature'] == cc.signature(r)
             and e['cout'] > 0 and e['modele'] == 'claude-sonnet-5-5', {k: e.get(k) for k in ('signature', 'modele', 'cout')})
    mesures['appel_type'] = {'jetons': e.get('jetons'), 'cout': e.get('cout')}
    print(f"     appel type (faux, usage realiste) : {e.get('jetons')} -> {e.get('cout')} $")
    verifier('cout inscrit au registre (video script1/script)', abs(ca.depense_video('script1/script') - e['cout']) < 1e-9)
    out2 = lancer()
    verifier('meme montage : resultat garde, aucun nouvel appel', out2.get('source') == 'garde' and len(fc.appels) == 1, out2)
    r = charger()
    reelmod.apply_template(r, 'editorial-cinetique')
    montage.save(PROJ, 'script', r)
    reelmod.apply_template(r, 'produit-3d')
    montage.save(PROJ, 'script', r)
    out3 = lancer()
    verifier('changement de style : aucun nouvel appel', out3.get('source') == 'garde' and len(fc.appels) == 1)
    sug = reelmod.refresh_ai(PROJ, None)
    verifier("« Relancer l'IA » sur le meme montage : aucun nouvel appel, propositions de Claude",
             len(fc.appels) == 1 and sug.get('banners', [None])[0] == 'VOTRE CONCURRENT APPELLE VOS LEADS', sug.get('banners'))
    ancien = copy.deepcopy(charger()['claude']['cerveau'])
    projet()  # nouveau montage automatique des memes mots (le reel est refait sans « claude »)
    out4 = lancer(cache=ancien)
    verifier('nouveau montage des memes mots : resultat de l\'ancien reel relu, aucun appel',
             out4.get('source') == 'garde' and len(fc.appels) == 1 and (charger().get('claude') or {}).get('cerveau'), out4)
    r = charger()
    r['clips'][3]['words'][10]['cut'] = True
    montage.save(PROJ, 'script', r)
    out5 = lancer()
    verifier('montage change (mot coupe) : un nouvel appel', out5.get('source') == 'claude' and len(fc.appels) == 2, out5)
    out6 = lancer(forcer=True)
    verifier('--forcer : un nouvel appel', out6.get('source') == 'claude' and len(fc.appels) == 3)
    # Haiku 4.5 pour le cerveau : requete simple (ni effort, ni repli, ni beta)
    ca.ecrire_reglages({'modeles_taches': {'cerveau': 'claude-haiku-4-5'}})
    lancer(forcer=True)
    kind, p = fc.appels[-1]
    verifier('Haiku 4.5 : messages.create simple, sans effort ni repli', kind == 'messages' and p['model'] == 'claude-haiku-4-5'
             and 'effort' not in p['output_config'] and 'betas' not in p and 'fallbacks' not in p)
    ca.ecrire_reglages({'modeles_taches': {'cerveau': None}})


def cas_corrections():
    bac_claude()
    avant = projet()
    installer(FauxClient())
    out = lancer()
    r = charger()
    changes = []
    for c0, c1 in zip(avant['clips'], r['clips']):
        for i, (a, b) in enumerate(zip(c0['words'], c1['words'])):
            if a['w'] != b['w']:
                changes.append((c0['id'], i, a['w'], b['w']))
            if (a['start'], a['end']) != (b['start'], b['end']):
                changes.append(('TEMPS', c0['id'], i))
    verifier('corrections posees seulement sur les mots listes (temps des mots gardes)', sorted(changes) == sorted(
        [('c4', 0, 'Pi', 'Puis'), ('c4', 54, 'transférez', 'transférer'), ('c5', 16, 'appuyer', 'appuyez')]), changes)
    verifier('texte d\'origine garde (asr) et nombre annonce', mot(r, 'c4', 54).get('asr') == 'transférez' and out.get('corrections') == 3, out)
    # « Relancer l'IA » sur une copie neuve : les corrections deviennent des propositions (rien n'est applique)
    projet()
    sug = reelmod.refresh_ai(PROJ, None)
    verifier("« Relancer l'IA » : corrections proposees, mots inchanges", len(sug.get('corrections') or []) == 3
             and mot(charger(), 'c4', 54)['w'] == 'transférez', sug.get('corrections'))
    # retouche du monteur apres l'appel : le mot change n'est plus corrige
    r = charger()
    mot(r, 'c5', 16)['w'] = 'Appuie'
    montage.save(PROJ, 'script', r)
    poses = cc.appliquer_corrections(r)
    verifier('mot retouche a la main apres l\'appel : jamais recorrige', ('c5', 16) not in {(p['clip'], p['i']) for p in poses}
             and mot(r, 'c5', 16)['w'] == 'Appuie', poses)
    # plan verrouille avant l'appel : aucune correction sur lui
    bac_claude()
    projet(mutation=lambda x: x['clips'][3].__setitem__('locked', True))
    installer(FauxClient())
    lancer()
    r = charger()
    verifier('plan verrouille : ses mots ne sont jamais corriges', mot(r, 'c4', 0)['w'] == 'Pi' and mot(r, 'c4', 54)['w'] == 'transférez'
             and mot(r, 'c5', 16)['w'] == 'appuyez')


def cas_branchements():
    bac_claude()
    projet()
    installer(FauxClient())
    lancer()
    r = charger()
    galerie.sober(r)  # meme passe que le montage automatique (mots en couleur revalides)
    hl = {(c['id'], i) for c in r['clips'] for i, w in enumerate(c['words']) if w.get('hl')}
    gardes = {(m['clip'], i) for m in r['claude']['cerveau']['resultat']['mots_forts'] for i in range(m['i0'], m['i1'] + 1)}
    verifier('mots en couleur : ceux de Claude d\'abord', gardes <= hl, sorted(gardes - hl))
    seuls = []
    for c in r['clips']:
        for run in reelmod._runs([i for i, w in enumerate(c['words']) if w.get('hl')]):
            if all(reelmod._core(c['words'][i]['w']) in reelmod.STOP or not reelmod._core(c['words'][i]['w']) for i in run):
                seuls.append((c['id'], [c['words'][i]['w'] for i in run]))
    verifier('mots en couleur : jamais un mot outil seul', not seuls, seuls)
    tpl = next(t for t in reelmod.list_templates() if t['id'] == 'produit-3d')
    plan = creative.build(r, r.get('auto'), tpl)
    verifier('plan creatif : temps du recit de Claude (accroche, tension -> probleme...)', 'Claude' in plan['source'] and
             [b['role'] for b in plan['beats']] == ['accroche', 'probleme', 'solution', 'preuve', 'explication', 'cta']
             and plan['direction'].get('message', '').startswith('Un setter'), plan['source'])
    QWEN.appels.clear()
    galerie._TITLES.clear()
    creative.apply(r, r.get('auto'), tpl)
    galerie.prepare(r)
    textes = [s['text'] for s in r.get('styleScenes') or [] if s.get('kind') == 'notification']
    verifier('notifications : titre de Claude (verifie), sans l\'IA locale', 'Lead qui attend depuis 3 h' in textes
             and 'notifications' not in QWEN.appels, (textes, QWEN.appels))
    montage.save(PROJ, 'script', r)
    QWEN.appels.clear()
    g = graphismes.suggest(PROJ, 'script')
    coches = next((x for x in g if x['kind'] == 'coches'), None)
    choc = next((x for x in g if x['kind'] == 'motgeant'), None)
    verifier('graphismes : liste de benefices de Claude (pas la liste des couts), sans l\'IA locale', coches and
             'Formé par nos soins' in coches['props']['items'] and 'Salaire' not in coches['props']['items']
             and 'benefices' not in QWEN.appels, (coches, QWEN.appels))
    verifier('graphismes : mot geant de Claude', choc and choc['props']['text'] == 'POURCENTAGE', choc)
    # bouton : sans « en savoir plus » reconnu par les regles, le bouton dit de Claude
    bac_claude()

    def reserver(x):
        for c in x['clips']:
            if c['id'] == 'c5':
                for i, t in ((21, 'Réservez'), (22, 'votre'), (23, 'appel'), (51, 'Réservez'), (52, 'votre'), (53, 'appel')):
                    c['words'][i]['w'] = t
    projet(mutation=reserver)
    rep = REPONSE()
    rep['cartes'] = [k for k in rep['cartes'] if k['type'] != 'bouton'] + [
        {'beat': 5, 'type': 'bouton', 'texte': 'Réservez votre appel', 'secondaire': '1 semaine gratuite', 'raison': ''}]
    rep['mots_forts'] = [m for m in rep['mots_forts'] if m['clip'] != 'c5']
    installer(FauxClient(rep))
    lancer()
    r = charger()
    galerie.prepare(r)
    cta = [s for s in r.get('styleScenes') or [] if s.get('kind') == 'cta']
    verifier('bouton : texte dit de Claude quand les regles ne trouvent rien', cta and cta[0]['text'] == 'Réservez votre appel'
             and cta[0]['secondary'] == '1 semaine gratuite', [(s['text'], s['secondary']) for s in cta])


def cas_finish():
    """auto._finish de bout en bout sur la copie : le derushage (ensure), le detourage, les plans de coupe et le controle sont
    remplaces (rien de lourd) ; tout le reste est le vrai code."""
    from editeur import broll, controle, detourage
    vrais = (auto.reelmod.ensure, detourage.prepare, broll.suggest, controle.controler)
    try:
        for claude_pret in (True, False):
            bac_claude()
            original = projet()
            fc = installer(FauxClient())
            if not claude_pret:
                ca.ecrire_reglages({'actif': False})
            auto.reelmod.ensure = lambda pdir, *a, **k: montage.save(pdir, 'script', copy.deepcopy(original))
            detourage.prepare = lambda r, *a, **k: None
            broll.suggest = lambda *a, **k: {}
            controle.controler = lambda r, *a, **k: (_ for _ in ()).throw(RuntimeError('controle remplace dans ce test'))
            info = {'type': 'pub', 'typeLabel': 'Marketing / pub', 'titre': 'Titre de Qwen', 'style': 'produit-3d'}
            with contextlib.redirect_stdout(io.StringIO()):
                auto._finish(PROJ, 'produit-3d', info)
            r = charger()
            seg = montage.compute(r)
            rep = sobriete.reperes(r, seg)
            temps = {(w['clip'], w['index']): w['start'] for w in seg['words']}
            sur = [s['text'] for s in r.get('styleScenes') or [] if not s.get('hidden')
                   and temps.get((s['clip'], s['index']), 99) < rep['accroche']]
            sur += [g['kind'] for g in r.get('graphics') or [] if not g.get('suggested') and g['at'] < rep['accroche']]
            if claude_pret:
                verifier('_finish : un seul appel, resultat garde, titre de Claude', len(fc.appels) == 1 and info.get('cerveau', {}).get('ok')
                         and r['auto']['titre'].startswith('Un setter'), info.get('cerveau'))
                verifier('_finish : bandeau de Claude, sans relecture locale', r['banner']['text'] == 'VOTRE CONCURRENT APPELLE VOS LEADS'
                         and 'bandeau' not in QWEN.appels, (r['banner'], QWEN.appels))
                verifier('_finish : corrections posees, notifications et graphismes sans l\'IA locale', mot(r, 'c4', 54)['w'] == 'transférer'
                         and not {'notifications', 'benefices'} & set(QWEN.appels), QWEN.appels)
                verifier('_finish : plan creatif de Claude', 'Claude' in r['creativePlan']['source'])
            else:
                verifier('Claude eteint : _finish sans appel, chemin local (Qwen : notifications, benefices)', len(fc.appels) == 0
                         and {'notifications', 'benefices'} <= set(QWEN.appels) and not r.get('claude')
                         and r['creativePlan']['source'] == 'règles vérifiables', (len(fc.appels), QWEN.appels))
                verifier('Claude eteint : mots inchanges (pas de correction), titre de Qwen garde', mot(r, 'c4', 54)['w'] == 'transférez'
                         and r['auto']['titre'] == 'Titre de Qwen' and info.get('cerveau', {}).get('source') == 'local', info.get('cerveau'))
            verifier(f"rien sur l'accroche sauf le bandeau ({'Claude' if claude_pret else 'local'})", not sur, sur)
    finally:
        auto.reelmod.ensure, detourage.prepare, broll.suggest, controle.controler = vrais
        ca.ecrire_reglages({'actif': True})


def cas_repli():
    """Claude indisponible : chemin Qwen exactement celui d'avant (et aucun appel)."""
    situations = [
        ('Claude eteint dans les reglages', lambda: ca.ecrire_reglages({'actif': False}), None),
        ('pas de cle', lambda: None, 'sans cle'),
        ('plafond par video atteint', lambda: ca.ecrire_reglages({'plafond_video': 0.001}), None),
        ('hors ligne', lambda: None, anthropic.APIConnectionError(request=httpx2.Request('POST', 'https://api.anthropic.com/v1/messages'))),
        ('refus de securite', lambda: None, reponse({}, stop='refusal')),
        ('credit epuise', lambda: None, 'credit'),
    ]
    for nom, reglage, quoi in situations:
        bac_claude()
        projet()
        if quoi == 'credit':
            body = {'type': 'error', 'error': {'type': 'invalid_request_error',
                                               'message': 'Your credit balance is too low to access the Anthropic API.'}}
            quoi = anthropic.BadRequestError(f'Error code: 400 - {body}', response=httpx2.Response(
                400, request=httpx2.Request('POST', 'https://api.anthropic.com/v1/messages')), body=body)
            nom_credit = True
        else:
            nom_credit = False
        echec = quoi if isinstance(quoi, (BaseException, SimpleNamespace)) else None
        fc = installer(FauxClient(toujours=echec), cle=None if quoi == 'sans cle' else FAUSSE)
        reglage()
        out = lancer()
        # un echec reseau ou un refus peut etre retente par « Relancer l'IA » (clic explicite) ; le credit epuise bloque 10 min
        attendu_appels = (1 if nom_credit else 2) if echec is not None else 0
        QWEN.appels.clear()
        galerie._TITLES.clear()
        sug = reelmod.refresh_ai(PROJ, None)
        r = charger()
        galerie.prepare(r)
        graphismes.suggest(PROJ, 'script')
        verifier(f'{nom} : chemin local, raison en francais, Qwen utilise (mots, bandeaux, notifications, benefices)',
                 not out.get('ok') and out.get('source') == 'local' and out.get('raison') and len(fc.appels) <= attendu_appels
                 and {'editorial', 'notifications', 'benefices'} <= set(QWEN.appels) and not cc.resultat(r)
                 and (sug.get('banners') or [''])[0] == 'QWEN : VOTRE CONCURRENT APPELLE',
                 (out.get('raison'), len(fc.appels), QWEN.appels, sug.get('banners')))
        quoi = 'credit' if nom_credit else quoi
        if quoi == 'credit':
            verifier('credit epuise : la phrase exacte', out.get('raison') == ca.CREDIT_EPUISE, out.get('raison'))
    ca.ecrire_reglages({'actif': True, 'plafond_video': 0.25})
    # un resultat garde ne sert plus si Claude est eteint ensuite : l'IA locale reprend la main
    bac_claude()
    projet()
    installer(FauxClient())
    lancer()
    ca.ecrire_reglages({'actif': False})
    r = charger()
    QWEN.appels.clear()
    galerie._TITLES.clear()
    galerie.prepare(r)
    verifier('resultat garde mais Claude eteint ensuite : ignore, Qwen reprend', cc.resultat(r) is None and 'notifications' in QWEN.appels)
    ca.ecrire_reglages({'actif': True})
    os.environ['EDITEUR_CLAUDE'] = '0'
    try:
        verifier('EDITEUR_CLAUDE=0 : resultat garde ignore et aucun appel', cc.resultat(charger()) is None
                 and not lancer(forcer=True).get('ok'))
    finally:
        os.environ['EDITEUR_CLAUDE'] = '1'


def cas_retouches():
    bac_claude()
    projet()
    installer(FauxClient())
    lancer()
    r = charger()
    galerie.sober(r)  # mots de Claude poses, notes dans hlAuto comme choix automatiques
    montage.save(PROJ, 'script', r)
    # le monteur decolore « concurrent » (choix de Claude) et colore « garantis »
    r = charger()
    mot(r, 'c1', 16)['hl'] = False
    mot(r, 'c3', 30)['hl'] = True
    verrou = copy.deepcopy(next(c for c in r['clips'] if c['id'] == 'c2'))
    next(c for c in r['clips'] if c['id'] == 'c2')['locked'] = True
    verrou['locked'] = True
    reelmod.apply_template(r, 'editorial-cinetique')  # changement de style : revalidation des mots en couleur
    verifier('mot decolore a la main : Claude ne le recolore pas', not mot(r, 'c1', 16)['hl'])
    verifier('mot colore a la main : garde', mot(r, 'c3', 30)['hl'])
    c2 = next(c for c in r['clips'] if c['id'] == 'c2')
    verifier('plan verrouille : mots en couleur exactement ceux du monteur', [w.get('hl') for w in c2['words']] == [w.get('hl') for w in verrou['words']])
    # bandeau verrouille : habiller ne le change pas
    r['banner'] = {'enabled': True, 'text': 'MON BANDEAU', 'start': 0, 'end': 4.5, 'locked': True}
    montage.save(PROJ, 'script', r)
    with contextlib.redirect_stdout(io.StringIO()):
        rap = cc.habiller(PROJ, 'script')
    r = charger()
    verifier('habiller : bandeau verrouille garde, version « avant » gardee', r['banner']['text'] == 'MON BANDEAU'
             and (PROJ / 'versions' / 'script' / rap.get('version', '-')).exists(), rap)


def cas_ligne_de_commande():
    bac_claude()
    projet()
    fc = installer(FauxClient())
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cc.main([str(PROJ), '--reel', 'script'])
    ligne = buf.getvalue().strip().splitlines()[-1]
    out = json.loads(ligne)
    verifier('python -m editeur.cerveau_claude : une ligne JSON, appel + habillage', code == 0 and out.get('ok') and len(fc.appels) == 1
             and out.get('habillage', {}).get('version'), out)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cc.main([str(PROJ), '--reel', 'script'])
    out = json.loads(buf.getvalue().strip().splitlines()[-1])
    verifier('ligne de commande relancee : resultat garde, aucun nouvel appel', out.get('source') == 'garde' and len(fc.appels) == 1, out)
    # vrai processus, Claude coupe par l'environnement : aucun appel possible, une ligne JSON, code 0
    env = {**os.environ, 'EDITEUR_CLAUDE': '0', 'PYTHONIOENCODING': 'utf-8'}
    p = subprocess.run([sys.executable, '-m', 'editeur.cerveau_claude', str(PROJ), '--reel', 'script'], cwd=ROOT / 'engine',
                       capture_output=True, text=True, encoding='utf-8', env=env, timeout=120)
    try:
        out = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        out = {}
    verifier('processus separe (EDITEUR_CLAUDE=0) : JSON, chemin local, code 0', p.returncode == 0 and out.get('source') == 'local',
             (p.returncode, p.stdout[-300:], p.stderr[-300:]))


def cas_revue():
    """Defauts trouves a la relecture (2 oct. 2026) : nombres en lettres et negation jamais « corriges » ; appel paye sans
    resultat jamais repaye ; correction defaite a la main jamais reposee ; mots forts de Claude tous faux -> regles ; plan
    change -> notifications par l'IA locale ; bandeau ecarte -> chemin local ; habiller garde le bandeau sans proposition et
    ne double pas les graphismes ; un seul cerveau a la fois par montage (verrou entre processus)."""
    import time
    tpl = next(t for t in reelmod.list_templates() if t['id'] == 'produit-3d')
    # 1. corrections : un nombre en lettres, une negation, un mot trop different
    r = projet()
    v = REPONSE()
    v['corrections'] = [{'clip': 'c2', 'i': 45, 'avant': 'deux', 'apres': 'dix', 'raison': ''},
                        {'clip': 'c4', 'i': 2, 'avant': 'c’est', 'apres': "n'est", 'raison': ''},
                        {'clip': 'c1', 'i': 16, 'avant': 'concurrent', 'apres': 'client', 'raison': ''}]
    res, ec = cc.valider(r, v)
    t = ' | '.join(ec)
    verifier('corrections : nombre en lettres (deux -> dix), negation (c\'est -> n\'est), mot trop different jamais poses',
             not res['corrections'] and '« deux » -> « dix » : un chiffre' in t and "« c'est » -> « n'est » : le sens changerait" in t
             and '« concurrent » -> « client » : trop différent' in t, t)
    # 2. appel PAYE sans resultat (reponse coupee) : ni un 2e lancement, ni « Relancer l'IA », ni un nouveau montage des
    # memes mots ne repaient ; --forcer, un autre modele ou un montage change, oui
    bac_claude()
    projet()
    fc = installer(FauxClient(toujours=reponse({}, stop='max_tokens')))
    o1, o2 = lancer(), lancer()
    QWEN.appels.clear()
    sug = reelmod.refresh_ai(PROJ, None)
    e = (charger().get('claude') or {}).get('cerveau_echec') or {}
    verifier("reponse coupee (payee) : notee, ni un 2e lancement ni « Relancer l'IA » ne repaient (Qwen a la place)",
             len(fc.appels) == 1 and not o1.get('ok') and not o2.get('ok') and 'déjà lu ce montage' in o2.get('raison', '')
             and e.get('cout', 0) > 0 and (sug.get('banners') or [''])[0] == 'QWEN : VOTRE CONCURRENT APPELLE'
             and sug.get('corrections') == [], (len(fc.appels), o2.get('raison'), e, sug.get('banners')))
    ancien = copy.deepcopy(e)
    projet()  # nouveau montage automatique des memes mots (auto._finish passe echec=)
    o3 = lancer(echec=ancien)
    verifier('nouveau montage des memes mots : appel deja paye sans resultat pas repaye', len(fc.appels) == 1
             and 'déjà lu' in o3.get('raison', ''), o3)
    lancer(forcer=True)
    verifier('--forcer : un nouvel essai', len(fc.appels) == 2)
    ca.ecrire_reglages({'modeles_taches': {'cerveau': 'claude-haiku-4-5'}})
    lancer()
    verifier('autre modele de Claude : un nouvel essai', len(fc.appels) == 3)
    ca.ecrire_reglages({'modeles_taches': {'cerveau': None}})
    fc.toujours = None
    r = charger()
    r['clips'][1]['words'][10]['cut'] = True
    montage.save(PROJ, 'script', r)
    o5 = lancer()
    verifier("montage change puis reponse valide : resultat garde, note d'echec retiree", o5.get('ok') and len(fc.appels) == 4
             and not (charger().get('claude') or {}).get('cerveau_echec'), o5)
    # hors ligne (rien de paye) : pas de note, un nouvel essai reste permis
    bac_claude()
    projet()
    fc = installer(FauxClient(toujours=anthropic.APIConnectionError(request=httpx2.Request('POST', 'https://api.anthropic.com/v1/messages'))))
    lancer()
    verifier('hors ligne (rien de paye) : aucune note d\'echec', not (charger().get('claude') or {}).get('cerveau_echec'))
    # 3. correction defaite a la main (« asr » garde par l'interface) : jamais reposee par un resultat garde
    bac_claude()
    projet()
    installer(FauxClient())
    lancer()
    r = charger()
    w = mot(r, 'c5', 16)
    pose = w['w'] == 'appuyez' and w.get('asr') == 'appuyer'
    w['w'] = 'appuyer'
    montage.save(PROJ, 'script', r)
    out = lancer()
    verifier('correction defaite a la main : jamais reposee', pose and out.get('source') == 'garde' and out.get('corrections') == 0
             and mot(charger(), 'c5', 16)['w'] == 'appuyer', (pose, out))
    # 4. mots forts de Claude tous faux (petits mots) : les regles choisissent, exactement comme sans Claude ; un plan dont
    # tous les mots proposes sont ecartes est laisse aux regles
    bac_claude()
    projet()
    rep = REPONSE()
    rep['mots_forts'] = [{'clip': 'c1', 'i0': 1, 'i1': 1, 'raison': ''}, {'clip': 'c2', 'i0': 0, 'i1': 0, 'raison': ''}]
    installer(FauxClient(rep))
    lancer()
    r = charger()
    ca.ecrire_reglages({'actif': False})
    sans = copy.deepcopy(r)
    galerie.sober(sans)
    ca.ecrire_reglages({'actif': True})
    galerie.sober(r)
    hl = lambda x: {(c['id'], i) for c in x['clips'] for i, w in enumerate(c['words']) if w.get('hl')}
    verifier('mots forts de Claude tous ecartes : mots en couleur des regles (comme sans Claude)', cc.mots(r) is None
             and hl(r) == hl(sans) and len(hl(r)) >= 5, (len(hl(r)), len(hl(sans))))
    rep = REPONSE()
    rep['mots_forts'] = [m for m in rep['mots_forts'] if m['clip'] != 'c2'] + [{'clip': 'c2', 'i0': 0, 'i1': 0, 'raison': ''}]
    bac_claude()
    projet()
    installer(FauxClient(rep))
    lancer()
    m = cc.mots(charger()) or {}
    verifier('plan dont tous les mots forts proposes sont ecartes : laisse aux regles', 'c2' not in m and m.get('c1'), sorted(m))
    # 5. plan change depuis l'appel : ses notifications passent par l'IA locale (pas « Claude ne voit rien »)
    bac_claude()
    projet()
    installer(FauxClient())
    lancer()
    r = charger()
    for w in next(c for c in r['clips'] if c['id'] == 'c2')['words']:
        w['start'], w['end'] = round(w['start'] + 0.01, 3), round(w['end'] + 0.01, 3)
    QWEN.appels.clear()
    galerie._TITLES.clear()
    creative.apply(r, r.get('auto'), tpl)
    galerie.prepare(r)
    textes = [s['text'] for s in r.get('styleScenes') or [] if s.get('kind') == 'notification']
    verifier("plan change depuis l'appel : l'IA locale titre ses idees (le titre de Claude n'y est plus)",
             'c2' not in cc.resultat(r)['_plans'] and 'notifications' in QWEN.appels and 'Lead qui attend depuis 3 h' not in textes,
             (textes, QWEN.appels))
    # 6. bandeau : propose mais ecarte -> chemin local (None) ; aucun -> '' ; habiller garde alors le bandeau actuel
    bac_claude()
    projet()
    rep = REPONSE()
    rep['bandeau'] = {'texte': 'GAGNEZ 10 CLIENTS'}
    installer(FauxClient(rep))
    lancer()
    verifier('bandeau de Claude ecarte par les regles : chemin local (IA locale relue)', cc.bandeau(charger()) is None)
    bac_claude()
    projet()
    rep = REPONSE()
    rep['bandeau'] = None
    installer(FauxClient(rep))
    lancer()
    r = charger()
    r['banner'] = {**(r.get('banner') or {}), 'enabled': True, 'text': 'CHAQUE LEAD REÇOIT UNE RÉPONSE RAPIDE'}
    montage.save(PROJ, 'script', r)
    with contextlib.redirect_stdout(io.StringIO()):
        cc.habiller(PROJ, 'script')
    verifier('Claude sans bandeau : habiller garde le bandeau actuel (jamais efface)', cc.bandeau(r) == ''
             and charger()['banner']['text'] == 'CHAQUE LEAD REÇOIT UNE RÉPONSE RAPIDE', charger().get('banner'))
    # 7. habiller apres acceptation des graphismes : ni doublon au meme moment ni identifiant en double
    r = charger()
    for g in r.get('graphics') or []:
        g['suggested'] = False  # « Accepter » de l'interface
        g.pop('auto', None)
    montage.save(PROJ, 'script', r)
    with contextlib.redirect_stdout(io.StringIO()):
        rap = cc.habiller(PROJ, 'script')
    gs = charger().get('graphics') or []
    ids = [g['id'] for g in gs]
    doubles = [(a['kind'], a['at']) for n, a in enumerate(gs) for b in gs[n + 1:] if a['kind'] == b['kind'] and abs(a['at'] - b['at']) < 2.5]
    verifier('habiller apres acceptation : ni graphisme en double ni identifiant en double, 2 versions « avant » distinctes',
             gs and len(set(ids)) == len(ids) and not doubles
             and len(list((PROJ / 'versions' / 'script').glob('*avant cerveau Claude*.json'))) >= 2, (ids, doubles, rap))
    # 8. un seul cerveau a la fois par montage : verrou tenu -> aucun appel ; verrou tenu par un AUTRE processus qui garde
    # son resultat -> le second attend puis relit ce resultat (aucun 2e appel)
    bac_claude()
    projet()
    fc = installer(FauxClient())
    attente = cc.ATTENTE_VERROU
    cc.ATTENTE_VERROU = 0.5
    try:
        with cc._un_a_la_fois(PROJ, 'script') as pris:
            o = lancer()
        verifier('verrou tenu par un autre traitement : aucun appel, chemin local', pris and not o.get('ok') and len(fc.appels) == 0
                 and 'déjà ce montage' in o.get('raison', ''), o)
        o = lancer()
        entree = copy.deepcopy(charger()['claude']['cerveau'])
        verifier('verrou rendu : un appel', o.get('ok') and len(fc.appels) == 1)
        projet()  # meme montage, sans resultat
        f_entree, drapeau = BAC / 'entree.json', BAC / 'verrou-pris.txt'
        f_entree.write_text(json.dumps(entree, ensure_ascii=False), encoding='utf-8')
        drapeau.unlink(missing_ok=True)
        code = (f"import sys, json, time\nsys.path.insert(0, {str(ROOT / 'engine')!r})\nfrom pathlib import Path\n"
                f"from editeur import claude_api as ca, cerveau_claude as cc, montage\nca.VERROU = Path({str(ca.VERROU)!r})\n"
                f"e = json.loads(Path({str(f_entree)!r}).read_text(encoding='utf-8'))\n"
                f"with cc._un_a_la_fois(Path({str(PROJ)!r}), 'script') as pris:\n"
                f"    Path({str(drapeau)!r}).write_text('1' if pris else '0')\n    time.sleep(1.5)\n"
                f"    montage.update(Path({str(PROJ)!r}), 'script', lambda x: x.setdefault('claude', {{}}).__setitem__('cerveau', e))\n")
        p = subprocess.Popen([sys.executable, '-c', code], cwd=ROOT / 'engine', env={**os.environ, 'EDITEUR_CLAUDE': '0'})
        for _ in range(200):
            if drapeau.exists():
                break
            time.sleep(0.05)
        cc.ATTENTE_VERROU = 30
        o = lancer()
        p.wait(timeout=60)
        verifier('2e traitement pendant un appel en cours (autre processus) : attend, relit son resultat, aucun 2e appel',
                 drapeau.exists() and drapeau.read_text() == '1' and o.get('source') == 'garde' and len(fc.appels) == 1, o)
    finally:
        cc.ATTENTE_VERROU = attente


def cas_cle_jamais_ecrite():
    trouve = []
    for f in BAC.rglob('*'):
        if f.is_file():
            try:
                if MORCEAU in f.read_text(encoding='utf-8', errors='replace'):
                    trouve.append(str(f))
            except OSError:
                pass
    verifier('la cle n\'apparait dans aucun fichier du bac a sable', not trouve, trouve)


def main():
    garder = '--garder' in sys.argv
    BAC.mkdir(parents=True, exist_ok=True)
    reel_avant = (SOURCE / 'reels' / 'script.json').read_bytes()
    try:
        for cas in (cas_invite, cas_validation, cas_appel_et_signature, cas_corrections, cas_branchements, cas_retouches,
                    cas_finish, cas_repli, cas_ligne_de_commande, cas_revue, cas_cle_jamais_ecrite):
            try:
                cas()
            except Exception as e:  # un cas qui plante ne cache pas les autres
                import traceback
                traceback.print_exc()
                verifier(f'{cas.__name__} : sans exception', False, repr(e))
        verifier('le vrai projet (projects/script1/reels/script.json) n\'a pas change',
                 (SOURCE / 'reels' / 'script.json').read_bytes() == reel_avant)
    finally:
        if not garder:
            shutil.rmtree(BAC, ignore_errors=True)
    n_ok = sum(1 for b in bilan if b['ok'])
    print(f'\n{n_ok}/{len(bilan)} reussis' + (f' — bac garde : {BAC}' if garder else ''))
    print('MESURES ' + json.dumps(mesures, ensure_ascii=False))
    return 0 if n_ok == len(bilan) else 1


if __name__ == '__main__':
    sys.exit(main())
