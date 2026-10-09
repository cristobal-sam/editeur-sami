import copy
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'engine'))
os.environ['EDITEUR_LLM'] = '0'

from editeur.produit import render
from editeur.reel import apply_template


def main():
    source = json.loads((ROOT / 'projects/script1/reels/script.json').read_text(encoding='utf-8'))
    old = copy.deepcopy(source)
    old.setdefault('design', {})['productVideo'] = 'assets/produits/generique.mp4'
    old['design'].pop('productImage', None)
    old['design'].pop('productModel', None)
    reel = apply_template(old, 'produit-3d')
    assert 'productVideo' not in reel['design'], 'une animation sans vraie source produit a été conservée'
    shown = [s for s in reel.get('styleScenes', []) if not s.get('hidden')]
    kinds = {s['kind'] for s in shown}
    assert {'dashboard', 'flow', 'cta'} <= kinds, kinds
    assert any(s['kind'] == 'cta' and s['text'].lower() == 'en savoir plus' for s in shown)
    assert all(s['kind'] != 'product' for s in shown)
    try:
        render()
    except ValueError as exc:
        assert 'vraie photo' in str(exc)
    else:
        raise AssertionError('Blender a accepté de fabriquer un objet générique sans source')
    print('TEST PREMIUM OK : scènes liées aux paroles, CTA exact, aucun objet générique.')


if __name__ == '__main__':
    main()
