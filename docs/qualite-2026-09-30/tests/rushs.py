"""Rushs des cas figes (cas/*.json) — 2 oct. 2026 (integration Claude) : le lot « media/entree/Lot 2026-09-30 10h51 » a ete
mis a la corbeille par l'utilisateur (Video 1 supprimee a 16 h 13, puis redeposee dans un autre lot). Les cas figes gardent
l'ancien chemin des rushs : sans eux, le controle annoncait de faux « Fichier manquant : rush d'origine … » (6 echecs de
test_controle, 1 de test_juge1, 1 de test_juge2). Un rush absent est lu a sa place dans la corbeille (meme chemin sous
corbeille/<date nom>/media/entree/…), en LECTURE seule : rien n'est restaure ni deplace.
  from rushs import retrouver ; reel = retrouver(json.loads(...))"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _dans_corbeille(chemin):
    p = Path(chemin)
    parts = [x.lower() for x in p.parts]
    if 'entree' not in parts or 'media' not in parts:
        return None
    reste = Path(*p.parts[parts.index('media'):])  # media/entree/<lot>/<video>/<rush>
    for d in sorted((ROOT / 'corbeille').glob('*'), reverse=True):  # la plus recente d'abord
        f = d / reste
        if f.is_file():
            return f
    return None


def retrouver(reel):
    """Sur place : chemin de chaque rush absent remplace par sa copie de la corbeille (si elle existe). -> reel"""
    for s in (reel.get('sources') or {}).values():
        chemin = s.get('path') if isinstance(s, dict) else None
        if not chemin or Path(chemin).exists():
            continue
        f = _dans_corbeille(chemin)
        if f:
            s['path'] = str(f)
    return reel
