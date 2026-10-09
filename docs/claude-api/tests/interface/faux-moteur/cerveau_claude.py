# FAUX « python -m editeur.cerveau_claude <projet> --reel <rid> » : 2 s d'attente, bandeau change, 0,031 $ au registre.
import argparse
import time

from . import _faux as F

F.journal('cerveau_claude')
p = argparse.ArgumentParser()
p.add_argument('projet')
p.add_argument('--reel', default='script')
a = p.parse_args()
time.sleep(2)
f, reel = F.reel_de(a.projet, a.reel)
reel.setdefault('banner', {})['text'] = 'Texte proposé par Claude (faux)'
F.ecrire(f, reel)
F.depense(f"{F.Path(a.projet).name}/{a.reel}", 'cerveau', 0.031)
F.sortie({'ok': True, 'cout': 0.031, 'moteur': 'claude', 'modele': 'claude-sonnet-5-5', 'resume': 'Mots forts, cartes et bandeau refaits.',
          'debug': f'jamais de clé : {F.FAUSSE_CLE}'})
