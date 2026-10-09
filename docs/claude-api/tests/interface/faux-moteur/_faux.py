# Outils communs du FAUX moteur de la copie de test (aucune IA, aucun reseau, aucun appel a Claude).
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'runtime' / 'cache'
REGISTRE = ROOT / 'projects' / '_claude.json'
REGLAGES = ROOT / 'styles' / 'claude.json'
FAUSSE_CLE = 'sk-ant-api03-FAUSSECLEDETESTnepasutiliser0123456789'
MODELES = ('claude-sonnet-5-5', 'claude-haiku-4-5', 'claude-opus-5-5')


def journal(nom):
    """Chaque appel du faux moteur est note (argv) dans runtime/cache/appels-moteur.log de la copie."""
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        with open(CACHE / 'appels-moteur.log', 'a', encoding='utf-8') as f:
            f.write(json.dumps({'t': time.time(), 'module': nom, 'argv': sys.argv[1:]}, ensure_ascii=False) + '\n')
    except OSError:
        pass


def marque(nom):
    return (CACHE / f'faux-{nom}').exists()


def lire(p, defaut=None):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return defaut


def ecrire(p, data):
    p = Path(p)
    tmp = p.with_name(p.name + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(tmp, p)


def depense(video, tache, cout, ok=True):
    """Comme claude_api._inscrire : registre (jour, mois, video) tenu a jour."""
    reg = lire(REGISTRE, None) or {'version': 1, 'jours': {}, 'mois': {}, 'videos': {}}
    d = time.strftime('%Y-%m-%dT%H:%M:%S')
    for coll, k in (('jours', d[:10]), ('mois', d[:7])):
        t = reg[coll].setdefault(k, {'cout': 0.0, 'appels': 0})
        t['cout'] = round(t['cout'] + cout, 6)
        t['appels'] += 1
    f = reg['videos'].setdefault(video, {'cout': 0.0, 'nb': 0, 'appels': []})
    f['cout'] = round(f['cout'] + cout, 6)
    f['nb'] += 1
    f['dernier'] = d
    f['appels'].append({'date': d, 'tache': tache, 'modele': 'claude-sonnet-5-5', 'cout': cout, 'ok': ok})
    reg['dernier'] = {'date': d, 'tache': tache, 'cout': cout, 'modele': 'claude-sonnet-5-5'}
    ecrire(REGISTRE, reg)


def sortie(obj):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        pass
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def reel_de(projet, rid):
    f = Path(projet) / 'reels' / f'{rid}.json'
    return f, json.loads(f.read_text(encoding='utf-8'))
