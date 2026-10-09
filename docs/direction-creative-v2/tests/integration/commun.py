"""Commun aux tests d'integration V2 (lead) : environnement sans IA ni GPU, le reel de reference qui porte TOUTES les
fonctions V2 a la fois (complet), et les regles d'affichage utilisees pour verifier (teinte, couleurs des vecteurs).
Importe par test-integration.py et test-integration-export.py (depuis engine/)."""
import copy
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FIX = HERE.parent / 'fixtures'  # donnees figees des tests (jamais les projets vivants de l'utilisateur)
sys.path.insert(0, str(ROOT / 'engine'))
os.environ['EDITEUR_LLM'] = '0'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
from editeur import banque, choregraphie, llm, montage  # noqa: E402
from editeur import broll as brollmod, detourage  # noqa: E402

llm.available = lambda: False  # aucune IA locale (regles seules)
detourage.prepare = lambda reel: None  # pas de GPU ni de cache assets/detourage pendant ces essais
brollmod.suggest = lambda *a, **k: []  # pas de recherche CLIP de plans de coupe (media/broll vide de toute facon)

BASE = ROOT / 'runtime/cache/tmp/dcv2-integration'
BASE.mkdir(parents=True, exist_ok=True)
CAT = {e['id']: e for e in json.loads((ROOT / 'assets/banque/catalogue.json').read_text(encoding='utf-8'))['entrees']}
CHARTE_A = {'client': 'essai-a', 'name': 'Client Essai A', 'logo': None, 'logoPosition': 'haut-droite', 'logoSize': .16, 'logoOpacity': .85,
            'bannerBg': '#7C3AED', 'bannerColor': '#FFFFFF', 'style': {'highlight': '#FF2D95'}, 'outro': {'enabled': False, 'text': '', 'duration': 2.5}}
CHARTE_B = {**CHARTE_A, 'client': 'essai-b', 'name': 'Client Essai B', 'bannerBg': '#0A2A66', 'style': {'highlight': '#22C55E'}}
RETOUCHE = '#00C2FF'  # couleur choisie a la main par le monteur
MAGENTA = '#FF00FF'   # couleur des dessins de revision (temoin : jamais dans l'export)


def lire(rel):
    """« projects/... » : copie figee (fixtures/projects) ; le reste : dossier de l'editeur."""
    return json.loads(((FIX if rel.startswith('projects/') else ROOT) / rel).read_text(encoding='utf-8'))


def teinte(g, reel):
    """Couleur affichee d'un graphisme (meme regle que remotion/src/graphics.tsx : tint)."""
    return (g.get('props') or {}).get('color') or reel['style']['highlight']


def couleurs_vecteur(reel, v):
    """Couleurs affichees d'un vecteur : celles choisies, sinon la palette charte / style (vectors.tsx, banque.palette)."""
    pal = banque.palette(reel)
    return {k: v['couleurs'].get(k) or pal[k] for k in pal}


def mot_a(seg, t):
    return next(w for w in seg['words'] if w['start'] >= t and w['w'].strip())


def ancre(reel, seg, t):
    """Ancre (SPEC §2.2) du mot dit a t : plan, temps dans la prise, signature (comme anchorAtTime de timeline.ts)."""
    w = mot_a(seg, t)
    c = next(c for c in reel['clips'] if c['id'] == w['clip'])
    src = c['words'][w['index']]['start'] + .04
    return {'clip': c['id'], 'src': round(src, 4), 'sig': c['signature'], 'source': c['source'], 'image': c.get('angle') or c['source']}


def complet(base):
    """Le reel de reference : toutes les fonctions V2 a la fois, posees comme l'interface les pose. -> (reel, pose)"""
    r = copy.deepcopy(base)
    for k in ('notes', 'annotations', 'vectors', 'choreography'):
        r.pop(k, None)
    seg = montage.compute(r)
    # charte A (recolore automatiquement) : passe par-dessus le style, comme l'onglet Style
    r['brand'] = copy.deepcopy(CHARTE_A)
    r['style'] = {**r['style'], **CHARTE_A['style']}
    mots = banque._mots_dits(r)
    # banque : deux modeles (graphismes), un son, deux vecteurs (charte / couleurs a la main)
    pose = {}
    for cle, eid, at in (('chiffre', 'template:chiffre-pourcentage', 14.3), ('liste', 'template:liste-benefices', 22.0),
                         ('son', 'son:editeur:whoosh-court', 15.0), ('etoile', 'vecteur:etoile', 14.5), ('coeur', 'vecteur:coeur', 16.2)):
        assert eid in CAT, f'{eid} absent du catalogue'
        pose[cle] = banque.ajouter(r, CAT[eid], at, mots, cadre=False)['element']
    # retouches a la main (comme l'interface : props.color + manual ; couleurs du vecteur + couleursManuelles)
    g = next(x for x in r['graphics'] if x['id'] == pose['liste']['id'])
    g['props']['color'] = RETOUCHE
    g['props']['title'] = 'Mes trois raisons'
    v = next(x for x in r['vectors'] if x['id'] == pose['coeur']['id'])
    v['couleurs'] = {'principale': RETOUCHE, 'secondaire': '#0A2A66', 'contour': '#FFFFFF'}
    v['couleursManuelles'] = True
    # un graphisme et un vecteur VERROUILLES, places la ou une passe automatique les retirerait (sur l'accroche)
    r['graphics'].append({'id': 'g-verrou', 'kind': 'motgeant', 'at': 1.0, 'duration': 1.2, 'props': {'text': 'STOP'}, 'auto': True, 'locked': True})
    r['vectors'].append({'id': 'v-verrou', 'asset': 'banque/vecteurs/fleche.svg', 'at': 0.6, 'duration': 2, 'x': .5, 'y': .3, 'w': .3,
                         'rotation': 0, 'opacite': 1, 'couleurs': {'principale': None, 'secondaire': None, 'contour': None},
                         'couleursManuelles': False, 'anim': {'entree': 'glisse-gauche', 'sortie': 'fondu'}, 'auto': True, 'locked': True})
    # un vecteur automatique LIBRE au meme moment qu'un autre (la relecture doit trancher)
    r['vectors'].append({'id': 'v-libre', 'asset': 'banque/vecteurs/cercle.svg', 'at': 1.4, 'duration': 2, 'x': .5, 'y': .3, 'w': .3,
                         'rotation': 0, 'opacite': 1, 'couleurs': {'principale': None, 'secondaire': None, 'contour': None},
                         'couleursManuelles': False, 'anim': {'entree': 'pop', 'sortie': 'fondu'}, 'auto': True, 'raison': 'essai'})
    # deux vecteurs automatiques en conflit avec un autre element : l'un DANS la plage du test « passage » (22,3 s, sur
    # la liste posee a la main), l'autre HORS plage (36,7 s, sur le chiffre automatique « ×5 ») : seul le premier est relu
    for vid, at in (('v-auto-dedans', 22.3), ('v-auto-dehors', 36.7)):
        r['vectors'].append({'id': vid, 'asset': 'banque/vecteurs/etincelles.svg', 'at': at, 'duration': 1.5, 'x': .5, 'y': .4, 'w': .3,
                             'rotation': 0, 'opacite': 1, 'couleurs': {'principale': None, 'secondaire': None, 'contour': None},
                             'couleursManuelles': False, 'anim': {'entree': 'pop', 'sortie': 'fondu'}, 'auto': True, 'raison': 'essai'})
    # bandeau verrouille ; plan verrouille (mots en couleur et emojis figes)
    r['banner'] = {**r['banner'], 'enabled': True, 'text': 'BANDEAU DU MONTEUR', 'locked': True}
    c = r['clips'][2]
    c['locked'] = True
    for i, w in enumerate(c['words']):
        w['hl'] = i in (1, 4)
    c['emojis'] = [[2, '🔥']]
    # notes + dessins (ancres dans la prise ; dessins en magenta, temoin de l'export)
    r['notes'] = []
    r['annotations'] = []
    for i, (t, texte) in enumerate(((3.0, 'Accroche : trop lente ?'), (15.2, 'Garder ce whoosh'), (30.0, 'Couper la pause'), (46.0, 'CTA ok ✅'))):
        a = ancre(r, seg, t)
        r['notes'].append({'id': f'n{i}', 't': t, 'anchor': a, 'text': texte, 'statut': 'resolue' if i == 3 else 'ouverte', 'auteur': 'Sami',
                           'cree': '2026-09-30T21:00:00.000Z', 'modifie': '2026-09-30T21:00:00.000Z',
                           'contexte': {'titre': r['title'], 'style': r['template'], 'format': '9:16', 'duree': round(seg['duration'], 2),
                                        'phrase': ' '.join(w['w'] for w in seg['words'] if t - 1 < w['start'] < t + 2)[:200]}})
        r['annotations'].append({'id': f'a{i}', 'noteId': f'n{i}', 'outil': ('crayon', 'fleche', 'cercle', 'surligneur')[i], 'couleur': MAGENTA,
                                 'epaisseur': 40, 'points': [[.25, .35], [.5, .45], [.7, .6]], 'anchor': a, 'duree': 2})
    # choregraphie de l'IA, puis un mouvement retouche (plus lent) et un verrouille
    choregraphie.actualiser(r, None, creer=True)
    cues = r['choreography']['cues']
    assert len(cues) >= 2, f'choregraphie trop pauvre ({len(cues)})'
    cues[0] = {**cues[0], 'entree': {**cues[0]['entree'], 'duree': round(cues[0]['entree']['duree'] + .2, 3)}, 'manual': True}
    cues[1] = {**cues[1], 'locked': True}
    return r, pose
