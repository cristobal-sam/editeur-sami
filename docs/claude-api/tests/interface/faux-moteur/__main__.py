# FAUX moteur (copie de test « interface Claude ») : python -m editeur claude statut|reglages|couts, controle, reel.
# Aucun reseau, aucune cle, aucun appel a Claude. Marqueurs (runtime/cache/faux-*) : statut-ko (le moteur echoue),
# fuite (le statut contient une fausse cle : le serveur doit la masquer), credit-epuise, eteint.
import json
import sys
import time
from datetime import date

from . import _faux as F

F.journal('editeur')
args = sys.argv[1:]
cmd = args[0] if args else ''


def opt(name, default=None):
    for a in args:
        if a.startswith(name + '='):
            return a[len(name) + 1:]
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else default


DEFAUTS = {'actif': True, 'modele': 'claude-sonnet-5-5', 'modeles_taches': {'cerveau': None, 'critique': None, 'consigne': None},
           'effort_cerveau': 'medium', 'effort_critique': 'medium', 'effort_consigne': 'low', 'plafond_video': 0.25,
           'plafond_jour': 0.75, 'plafond_mois': 2.0, 'credit_depart': 2.0, 'credit_date': time.strftime('%Y-%m-%d'),
           'critique_auto': False, 'images_critique': 16, 'largeur_images': 540, 'espace_travail': None}


def reglages():
    r = dict(DEFAUTS)
    r.update(F.lire(F.REGLAGES, {}) or {})
    return r


def statut():
    if F.marque('statut-ko'):
        raise SystemExit('Moteur en panne (test).')
    r = reglages()
    reg = F.lire(F.REGISTRE, {}) or {}
    auj = time.strftime('%Y-%m-%d')
    dj = float(((reg.get('jours') or {}).get(auj) or {}).get('cout') or 0)
    nj = int(((reg.get('jours') or {}).get(auj) or {}).get('appels') or 0)
    dm = float(((reg.get('mois') or {}).get(auj[:7]) or {}).get('cout') or 0)
    depuis = sum(float((t or {}).get('cout') or 0) for d, t in (reg.get('jours') or {}).items() if d >= r['credit_date'])
    reste = max(0.0, round(r['credit_depart'] - depuis, 4))
    epuise = F.marque('credit-epuise')
    raison = ''
    if not r['actif']:
        raison = "Claude est éteint dans les réglages. L'outil continue en local."
    elif epuise:
        raison = "Crédit Anthropic épuisé : recharge sur platform.claude.com (Billing). L'outil continue en local."
    noms = {'claude-sonnet-5-5': 'Claude Sonnet 5.5', 'claude-haiku-4-5': 'Claude Haiku 4.5', 'claude-opus-5-5': 'Claude Opus 5.5'}
    out = {'cle': True, 'actif': r['actif'], 'modele': r['modele'], 'nom_modele': noms[r['modele']], 'modeles_taches': r['modeles_taches'],
           'plafonds': {'video': r['plafond_video'], 'jour': r['plafond_jour'], 'mois': r['plafond_mois']},
           'depense_jour': round(dj, 4), 'depense_mois': round(dm, 4), 'credit_depart': r['credit_depart'], 'credit_date': r['credit_date'],
           'credit_restant_estime': reste, 'appels_jour': nj, 'dernier_appel': reg.get('dernier'), 'credit_epuise': epuise,
           'pret': not raison, 'raison': raison, 'avertissement': '', 'critique_auto': r['critique_auto'],
           'espace_travail': bool(r.get('espace_travail')), 'espace_manquant': False,
           # pas d'« estimation » par modele : le serveur la complete (estimation_video du moteur)
           'modeles': [{'id': m, 'nom': noms[m], 'conseil': '…', 'prix': {}} for m in F.MODELES],
           'estimation': {'modele': r['modele'], 'nom': noms[r['modele']], 'cerveau': 0.0451, 'consigne': 0.0289, 'critique': 0.055,
                          'par_video': 0.074, 'videos_avec_credit': 27, 'texte': 'Environ 0,07 $ par vidéo.'}}
    if F.marque('fuite'):
        out['avertissement'] = f'erreur du SDK : clé {F.FAUSSE_CLE} refusée'
        out['cle'] = F.FAUSSE_CLE  # jamais : le serveur ne doit garder que vrai / faux
    return out


if cmd == 'claude':
    action = args[1] if len(args) > 1 else ''
    if action == 'statut':
        F.sortie(statut())
    elif action == 'reglages':
        patch = opt('--json')
        r = reglages()
        if patch:
            p = json.loads(patch)
            for k, v in p.items():
                if k not in DEFAUTS:
                    raise SystemExit(f'Réglage inconnu : {k}.')
                if k == 'credit_date':
                    try:
                        date.fromisoformat(v)
                    except ValueError:
                        raise SystemExit('Réglage « credit_date » : une date AAAA-MM-JJ est attendue (ex. 2026-10-02).')
                if k == 'modeles_taches' and v is not None:
                    r[k] = {**r[k], **v}
                else:
                    r[k] = v
            F.ecrire(F.REGLAGES, r)
        F.sortie(r)
    elif action == 'couts':
        reg = F.lire(F.REGISTRE, {}) or {}
        video = opt('--video')
        auj = time.strftime('%Y-%m-%d')
        out = {'jours': [{'date': auj, 'cout': round(float(((reg.get('jours') or {}).get(auj) or {}).get('cout') or 0), 4),
                          'appels': int(((reg.get('jours') or {}).get(auj) or {}).get('appels') or 0)}],
               'total': 0.0, 'mois': {'mois': auj[:7], 'cout': float(((reg.get('mois') or {}).get(auj[:7]) or {}).get('cout') or 0), 'appels': 0},
               'credit': {'depart': 2.0, 'date': auj, 'depense': 0.0, 'restant_estime': statut()['credit_restant_estime']},
               'plafonds': {'video': 0.25, 'jour': 0.75, 'mois': 2.0}}
        out['total'] = out['jours'][0]['cout']
        if video:
            f = (reg.get('videos') or {}).get(video) or {}
            out['video'] = {'video': video, 'cout': f.get('cout', 0), 'nb': f.get('nb', 0), 'appels': f.get('appels', [])}
        else:
            out['videos'] = [{'video': k, 'cout': v.get('cout', 0), 'nb': v.get('nb', 0), 'dernier': v.get('dernier')} for k, v in (reg.get('videos') or {}).items()]
        F.sortie(out)
    else:
        raise SystemExit('action inconnue')
elif cmd == 'controle':
    rapport = {'version': 1, 'date': time.strftime('%Y-%m-%d %H:%M'), 'note': 8.0, 'verdict': 'Correct (faux contrôle).',
               'compte': {'bloquant': 0, 'important': 0, 'conseil': 1}, 'video': opt('--video'), 'format': '1080x1920', 'total': 1,
               'constats': [{'gravite': 'conseil', 'code': 'divers', 'temps': 1.0, 'fin': None, 'message': 'Petit détail', 'suggestion': 'rien d’urgent'}]}
    # comme controle.main : apres un export complet (video + export.json), avis de Claude SEULEMENT si critique_auto
    # (controle._avis_auto, dans CE controle : le serveur ne relance pas de critique a part) ; trace « controle-avis »
    if opt('--video') and reglages().get('critique_auto') is True:
        F.journal('controle-avis')
        rapport['claude'] = {'ok': True, 'statut': 'ok', 'note': 7.0, 'verdict': 'Avis automatique (faux).', 'cout_avis': 0.05,
                             'problemes': [{'temps': 2.0, 'gravite': 'conseil', 'probleme': 'Carte un peu longue', 'suggestion': 'la raccourcir'}]}
    if opt('--sortie'):  # rapport complet range (lu ensuite par la critique de cette video)
        F.Path(opt('--sortie')).mkdir(parents=True, exist_ok=True)
        F.ecrire(F.Path(opt('--sortie')) / 'controle.json', rapport)
    rapport['resume'] = {k: rapport[k] for k in ('note', 'verdict', 'compte', 'date', 'constats', 'claude') if k in rapport}
    F.sortie(rapport)
elif cmd == 'reel':
    F.sortie({'ok': True})
else:
    raise SystemExit(f'Faux moteur : commande « {cmd} » non prévue dans la copie de test.')
