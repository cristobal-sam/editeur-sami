# FAUX « python -m editeur.consigne » (contrat « consigne ») : aucune IA. « lent » dans le texte = 3 s d'attente (test du
# double clic) ; « ambigu » = question ; « refuse » = un refus ; sinon le bandeau est retire et une version « avant » gardee.
import argparse
import shutil
import time

from . import _faux as F

F.journal('consigne')
p = argparse.ArgumentParser()
p.add_argument('projet')
p.add_argument('--reel', default='script')
p.add_argument('--texte', required=True)
p.add_argument('--t', type=float)
p.add_argument('--moteur', default='auto', choices=['auto', 'claude', 'local'])
p.add_argument('--simuler', action='store_true')
a = p.parse_args()
if 'lent' in a.texte:
    time.sleep(3)
f, reel = F.reel_de(a.projet, a.reel)
video = f"{F.Path(a.projet).name}/{a.reel}"
if 'ambigu' in a.texte:
    F.sortie({'ok': True, 'version': a.reel, 'avant': None, 'changements': [], 'refus': [], 'question': 'Quel bandeau : celui du début ou celui de la fin ?',
              'moteur': 'claude', 'cout': 0.003, 'note_ajoutee': False})
    raise SystemExit(0)
changements = [{'quoi': 'Bandeau du début retiré', 'detail': 'il cachait le visage', **({'t': a.t} if a.t is not None else {})}]
refus = [{'demande': 'changer la voix', 'raison': 'la voix ne se change pas ici'}] if 'refuse' in a.texte else []
avant = None
if not a.simuler:
    d = F.Path(a.projet) / 'versions' / a.reel
    d.mkdir(parents=True, exist_ok=True)
    avant = time.strftime('%Y-%m-%dT%H-%M-%S') + ' avant consigne.json'
    shutil.copyfile(f, d / avant)
    reel.setdefault('banner', {})['enabled'] = False
    reel.setdefault('consignes', []).append({'date': time.strftime('%Y-%m-%dT%H:%M:%S'), 'texte': a.texte, 't': a.t, 'moteur': 'claude', 'cout': 0.004,
                                             'changements': changements, 'refus': refus, 'question': None})
    F.ecrire(f, reel)
    F.depense(video, 'consigne', 0.004)
F.sortie({'ok': True, 'version': a.reel, 'avant': avant, 'changements': changements, 'refus': refus, 'question': None,
          'moteur': 'local' if a.moteur == 'local' else 'claude', 'cout': 0.0 if a.moteur == 'local' else 0.004, 'note_ajoutee': False})
