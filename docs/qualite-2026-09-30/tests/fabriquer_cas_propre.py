"""Fabrique le cas PROPRE du controle qualite : un reel simple, sans habillage, a partir d'une COPIE du reel
de Video 1 (aucune donnee reelle modifiee). Prise d'origine plein cadre, sous-titres lisibles (72 px, contour),
bandeau, emojis, graphismes, scenes, detourage et plans de coupe retires ; lente poussee de zoom par plan.

    python fabriquer_cas_propre.py            -> cas/propre.json
"""
import copy
import json
from pathlib import Path

ICI = Path(__file__).resolve().parent


def fabriquer():
    job = json.loads((ICI / 'cas/apercu-premium-job-copie.json').read_text(encoding='utf-8'))
    r = copy.deepcopy(job['reel'])
    r['id'] = 'propre'
    r['title'] = 'Répondez vite à vos leads'
    r['template'] = 'controle-propre'
    r['design'] = {'enabled': False}
    for k in ('styleScenes', 'graphics', 'broll', 'cutouts', 'creativePlan', 'brand'):
        r.pop(k, None)
    r['banner'] = {'enabled': False, 'text': '', 'start': 0, 'end': 4.5}
    r['emoji'] = {'enabled': False}
    r['progress'] = {'enabled': False}
    r['intro'] = {'enabled': False, 'text': '', 'file': None, 'duration': 2.5}
    r['flash'] = {'enabled': False, 'kind': 'blanc'}
    r['effects'] = {'grain': 0, 'vignette': 0, 'grade': 'aucun'}
    r['zoom'] = {'auto': True, 'strength': 1.08, 'push': 0.05, 'overrides': {}}
    r['style'] = {'preset': 'minimal', 'font': 'Inter', 'weight': 800, 'uppercase': False, 'size': 72, 'color': '#FFFFFF',
                  'highlight': '#FFD400', 'stroke': '#000000', 'strokeWidth': 4, 'position': 0.66, 'maxWords': 4, 'pop': False}
    r['sfx'] = {**(r.get('sfx') or {}), 'enabled': False}
    out = ICI / 'cas/propre.json'
    out.write_text(json.dumps(r, ensure_ascii=False), encoding='utf-8')
    return out


if __name__ == '__main__':
    print(fabriquer())
