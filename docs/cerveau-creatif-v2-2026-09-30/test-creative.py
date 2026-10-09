"""Tests courts du directeur créatif V2, sans serveur, rendu ni IA."""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'engine'))

from editeur import creative, galerie, reel


# Copie FIGÉE de Vidéo 1 en Tech 3D gardée à côté de ce fichier : le test ne lit jamais les projets vivants de
# l'utilisateur (projects/script1 peut changer de style, être retouché ou supprimé à tout moment).
source = json.loads((ROOT / 'docs/cerveau-creatif-v2-2026-09-30/avant/script-video1.json').read_text(encoding='utf-8'))
assert source.get('template') == 'produit-3d', 'la copie figée de Vidéo 1 doit être en Tech 3D'
work = copy.deepcopy(source)
template = next(t for t in reel.list_templates() if t['id'] == 'produit-3d')
plan = creative.apply(work, work.get('auto'), template)

assert plan['version'] == 2
assert plan['beats'], 'le plan narratif est vide'
assert plan['beats'][0]['role'] == 'accroche'
assert any(b['role'] == 'solution' for b in plan['beats'])
assert any(b['role'] == 'cta' for b in plan['beats'])
assert all(b['evidence'] in ' '.join(w['w'] for c in work['clips'] for w in c['words']) for b in plan['beats'] if len(b['sentences']) == 1)
assert 0 <= plan['quality']['confidence'] <= 1
assert 0 <= plan['quality']['coverage'] <= 1
assert len(plan['storyboard']) == len(plan['beats'])
assert all(s['evidence'] and s['fallback'] and s['engine'] for s in plan['storyboard'])
assert not any(s['engine'] == 'blender' for s in plan['storyboard']), 'Blender ne doit pas partir sans produit réel'
assert any(s['role'] == 'preuve' for s in plan['storyboard']), 'les preuves chiffrées doivent être reconnues'

galerie.prepare(work, use_ai=False)
visible = [s for s in work.get('styleScenes', []) if not s.get('hidden')]
assert visible, 'aucune scène exécutée par le style'
assert all(s.get('creativeBeat') and s.get('creativeReason') for s in visible)
assert all(s.get('creativeShot') for s in visible)
assert all(s['status'] in ('prêt', 'planifié') for s in work['creativePlan']['storyboard'])
assert not [s for s in work['creativePlan']['storyboard'] if s['status'] == 'planifié' and s['engine'] != 'blender'], \
    'le storyboard Tech doit être entièrement exécutable avec les scènes existantes'

# Avec une vraie ressource produit, Blender devient une option légitime pour la révélation.
with_product = copy.deepcopy(source)
with_product.setdefault('design', {})['productImage'] = 'assets/produit-reel.png'
product_plan = creative.build(with_product, with_product.get('auto'), template)
assert any(s['engine'] == 'blender' for s in product_plan['storyboard'] if s['role'] == 'solution')

# Une décision verrouillée par le monteur ne doit jamais être écrasée.
locked = copy.deepcopy(work)
locked['creativePlan']['locked'] = True
locked['creativePlan']['summary'] = 'Plan validé à la main'
creative.apply(locked, locked.get('auto'), template)
assert locked['creativePlan']['summary'] == 'Plan validé à la main'

# Changer de style reconstruit la grammaire visuelle, mais garde un plan valide.
changed = copy.deepcopy(source)
reel.apply_template(changed, 'editorial-cinetique')
assert changed.get('creativePlan', {}).get('version') == 2
assert changed['creativePlan']['beats'][0]['role'] == 'accroche'

print('CERVEAU CREATIF V2: OK')
print(plan['summary'])
print(' -> '.join(b['label'] for b in plan['beats']))
