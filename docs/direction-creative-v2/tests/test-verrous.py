"""Tests hors ligne (sans IA) des verrous V2 : un element verrouille ou retouche survit a toutes les passes automatiques.
    python ../docs/direction-creative-v2/tests/test-verrous.py      (depuis engine/, environnement charge)
Donnees : copies EN MEMOIRE des reels FIGES fixtures/projects/script1 et script2 ; refresh_ai et ensure travaillent sur
une COPIE du projet dans runtime/cache/tmp/dcv2-architecte/verrous-<hasard>/ (jamais sur projects/)."""
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIX = HERE / 'fixtures'  # donnees figees des tests (jamais les projets vivants de l'utilisateur)
sys.path.insert(0, str(ROOT / 'engine'))
os.environ['EDITEUR_LLM'] = '0'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
from editeur import creative, galerie, llm, montage, sobriete, verrous  # noqa: E402
from editeur import reel as reelmod  # noqa: E402

llm.available = lambda: False  # aucune IA locale pendant ces essais


def lire(rel):
    return json.loads(((FIX if rel.startswith('projects/') else ROOT) / rel).read_text(encoding='utf-8'))


def habille(r):
    """Ajoute au reel des elements V2 verrouilles / retouches / libres, places la ou une passe automatique les
    retirerait (sur l'accroche, colles les uns aux autres)."""
    r = copy.deepcopy(r)
    c0 = r['clips'][0]
    r['graphics'] = list(r.get('graphics') or []) + [
        {'id': 'g-verrou', 'kind': 'motgeant', 'at': 0.5, 'duration': 1.2, 'props': {'text': 'STOP'}, 'auto': True, 'locked': True},
        {'id': 'g-main', 'kind': 'chiffre', 'at': 1.0, 'duration': 1.5, 'props': {'value': 5, 'suffix': ' x'}, 'auto': True, 'manual': True},
        {'id': 'g-libre', 'kind': 'motgeant', 'at': 1.2, 'duration': 1.0, 'props': {'text': 'WOW'}, 'auto': True},
        {'id': 'g-genere', 'kind': 'logo', 'at': 30, 'duration': 1, 'props': {}, 'generated': True, 'locked': True},
    ]
    src = c0['source']
    r['broll'] = [{'id': 'b-verrou', 'source': src, 'in': 1.0, 'at': 0.8, 'duration': 1.5, 'word': 'truc', 'auto': True, 'locked': True},
                  {'id': 'b-libre', 'source': src, 'in': 2.0, 'at': 1.1, 'duration': 1.5, 'word': 'truc', 'auto': True}]
    r['vectors'] = [{'id': 'v-verrou', 'asset': 'banque/vecteurs/fleche.svg', 'at': 0.2, 'duration': 2, 'x': .5, 'y': .3, 'w': .3,
                     'rotation': 0, 'opacite': 1, 'couleurs': {'principale': '#FF0000', 'secondaire': None, 'contour': None},
                     'couleursManuelles': True, 'anim': {'entree': 'pop', 'sortie': 'fondu'}, 'auto': True, 'locked': True},
                    {'id': 'v-libre', 'asset': 'banque/vecteurs/cercle.svg', 'at': 0.4, 'duration': 2, 'x': .5, 'y': .3, 'w': .3,
                     'rotation': 0, 'opacite': 1, 'couleurs': {'principale': None, 'secondaire': None, 'contour': None},
                     'couleursManuelles': False, 'anim': {'entree': 'pop', 'sortie': 'fondu'}, 'auto': True}]
    r['styleScenes'] = list(r.get('styleScenes') or [])
    r['styleScenes'].append({'id': 'scene-verrou', 'kind': 'keyword', 'clip': c0['id'], 'index': 1, 'text': 'VERROU', 'duration': 2,
                             'x': .5, 'y': .5, 'scale': 1, 'rotation': 0, 'color': '#FF00FF', 'locked': True})
    r['sfx'] = {**(r.get('sfx') or {}), 'enabled': True, 'transition': None,
                'extra': [{'t': 9.0, 'name': 'riser', 'creative': True, 'reason': 'garde', 'locked': True, 'id': 'sfx-verrou'},
                          {'t': 11.0, 'name': 'ding', 'reason': 'pose a la main'}]}
    r['banner'] = {**r['banner'], 'enabled': True, 'text': 'MON BANDEAU FIGE', 'locked': True}
    r['notes'] = [{'id': 'n1', 't': 4.0, 'anchor': {'clip': c0['id'], 'src': c0['in'] + 4, 'sig': c0['signature']}, 'text': 'Couper ici ?',
                   'statut': 'ouverte', 'auteur': 'Sami', 'cree': '2026-09-30T20:00:00', 'modifie': '2026-09-30T20:00:00',
                   'contexte': {'titre': 'Vidéo 1', 'style': r.get('template', ''), 'format': '9:16', 'duree': 70}}]
    r['annotations'] = [{'id': 'a1', 'noteId': 'n1', 'outil': 'crayon', 'couleur': '#FF0000', 'epaisseur': 6, 'points': [[.4, .4], [.5, .5]],
                         'anchor': r['notes'][0]['anchor'], 'duree': 2}]
    r['choreography'] = {'version': 1, 'cues': [
        {'id': 'cue-verrou', 'cible': {'type': 'graphics', 'id': 'g-verrou'}, 'at': .5, 'duree': 1.2,
         'entree': {'type': 'pop', 'duree': .3, 'courbe': 'rebond'}, 'sortie': {'type': 'fondu', 'duree': .2, 'courbe': 'douce'},
         'sync': {'sur': 'mot', 'ref': 'c1:3'}, 'raison': 'choix du monteur', 'auto': False, 'locked': True},
        {'id': 'cue-libre', 'cible': {'type': 'graphics', 'id': 'g-libre'}, 'at': 1.2, 'duree': 1,
         'entree': {'type': 'glisse', 'direction': 'gauche', 'duree': .3, 'courbe': 'douce'}, 'sortie': {'type': 'aucune', 'duree': 0, 'courbe': 'lineaire'},
         'sync': {'sur': 'temps', 'ref': None}, 'raison': 'auto', 'auto': True, 'locked': False}]}
    return r


PROTEGES = {'graphics': ['g-verrou', 'g-main', 'g-genere'], 'broll': ['b-verrou'], 'vectors': ['v-verrou'], 'styleScenes': ['scene-verrou']}


class Verrous(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s1 = lire('projects/script1/reels/script.json')
        cls.s2 = lire('projects/script2/reels/script.json')

    def assert_intacts(self, avant, apres, quoi):
        for champ, ids in PROTEGES.items():
            ref = {e['id']: e for e in avant.get(champ) or []}
            got = {e['id']: e for e in apres.get(champ) or []}
            for i in ids:
                self.assertIn(i, got, f'{quoi} : {champ}/{i} a disparu')
                self.assertEqual(got[i], ref[i], f'{quoi} : {champ}/{i} a ete modifie')
        self.assertEqual(apres['banner'], avant['banner'], f'{quoi} : bandeau verrouille modifie')
        self.assertEqual(apres['notes'], avant['notes'], f'{quoi} : notes modifiees')
        self.assertEqual(apres['annotations'], avant['annotations'], f'{quoi} : dessins modifies')
        sfx = {verrous.cle(e): e for e in apres['sfx'].get('extra') or []}
        self.assertEqual(sfx.get('sfx-verrou'), avant['sfx']['extra'][0], f'{quoi} : bruitage verrouille')
        self.assertIn(verrous.cle(avant['sfx']['extra'][1]), sfx, f'{quoi} : bruitage pose a la main')
        cues = {c['id']: c for c in (apres.get('choreography') or {}).get('cues') or []}
        self.assertEqual(cues.get('cue-verrou'), avant['choreography']['cues'][0], f'{quoi} : mouvement verrouille')

    def test_regles(self):
        self.assertTrue(verrous.protege({'locked': True}) and verrous.protege({'manual': True}) and verrous.protege({'edited': True}))
        self.assertFalse(verrous.protege({'auto': True}) or verrous.protege(None) or verrous.protege([1, 'x']))
        self.assertFalse(verrous.modifiable({'auto': True, 'locked': True}, True))
        self.assertTrue(verrous.modifiable({'auto': True}, True))
        old = [{'id': 'a', 'locked': True, 'v': 1}, {'id': 'b', 'v': 1}]
        self.assertEqual(verrous.fusionner(old, [{'id': 'a', 'v': 2}, {'id': 'c'}]), [{'id': 'c'}, {'id': 'a', 'locked': True, 'v': 1}])
        cues = verrous.garder_cues([{'id': 'x', 'cible': {'type': 'graphics', 'id': 'g'}, 'locked': True}],
                                   [{'id': 'y', 'cible': {'type': 'graphics', 'id': 'g'}}, {'id': 'z', 'cible': {'type': 'design', 'id': 's'}}])
        self.assertEqual([c['id'] for c in cues], ['z', 'x'], 'un nouveau mouvement sur une cible verrouillee est ecarte')

    def test_changement_de_style(self):
        for depart in (self.s1, self.s2):
            for style in ('reel-impact', 'produit-3d', 'tech-application', 'documentaire'):
                avant = habille(depart)
                r = copy.deepcopy(avant)
                reelmod.apply_template(r, style)
                self.assert_intacts(avant, r, f'{depart["template"]} -> {style}')
                self.assertTrue(r['banner']['enabled'], 'bandeau verrouille : le style ne l\'eteint pas')
                # les elements libres, eux, sont bien relus (colles au bandeau sur l'accroche) quand le style les montre
                # (un style immersif masque graphismes et plans de coupe : la relecture les ignore alors)
                if not (r.get('design') or {}).get('mode'):
                    libres = [g for g in r['graphics'] if g['id'] == 'g-libre' and not g.get('suggested')]
                    self.assertFalse(libres and libres[0]['at'] < 2.9, f'{style} : le graphisme libre sur l\'accroche aurait du bouger')
                # une scene verrouillee survit meme a un style sans habillage, puis au retour
                reelmod.apply_template(r, 'reel-impact')
                reelmod.apply_template(r, 'produit-3d')
                self.assert_intacts(avant, r, f'aller-retour {style}')

    def test_plan_creatif_verrouille(self):
        r = habille(self.s1)
        r['creativePlan']['locked'] = True
        r['creativePlan']['summary'] = 'Plan validé à la main'
        fige = copy.deepcopy(r['creativePlan'])
        reelmod.apply_template(r, 'produit-3d')
        self.assertEqual(r['creativePlan'], fige, 'plan verrouille : ni recalcule ni audite')
        # plan libre : recalcule, bruitage creatif libre remplace, bruitage creatif verrouille garde
        r = habille(self.s2)
        r['sfx']['extra'].append({'t': 30.0, 'name': 'whoosh-court', 'creative': True, 'reason': 'ancien'})
        tpl = next(t for t in reelmod.list_templates() if t['id'] == 'reel-impact')
        creative.apply(r, None, tpl)
        extra = r['sfx']['extra']
        self.assertTrue(any(e.get('id') == 'sfx-verrou' for e in extra))
        self.assertFalse(any(e.get('reason') == 'ancien' for e in extra), 'bruitage creatif libre recalcule')
        self.assertEqual(sum(1 for e in extra if e.get('name') == 'riser' and abs(e['t'] - 9.0) < .01), 1, 'pas de doublon')

    def test_relecture_sobriete(self):
        avant = habille(self.s2)
        for tout in (True, False):
            r = copy.deepcopy(avant)
            rep = sobriete.relire(r, 'reel-impact', tout=tout)
            self.assert_intacts(avant, r, f'sobriete tout={tout}')
            self.assertGreaterEqual(rep['proteges'], 5)
            self.assertIn('verrouill', rep['resume'])
            libre = next(g for g in r['graphics'] if g['id'] == 'g-libre')
            self.assertTrue(libre.get('suggested') or libre['at'] >= 2.9, 'graphisme libre : retire ou deplace')
            self.assertFalse(any(b['id'] == 'b-libre' for b in r['broll']), 'plan de coupe libre sur l\'accroche retire')
            vl = next(v for v in r['vectors'] if v['id'] == 'v-libre')
            self.assertTrue(vl.get('suggested'), 'vecteur libre sur l\'accroche : proposition')

    def test_galerie(self):
        r = habille(self.s1)
        g = next(t for t in reelmod.list_templates() if t['id'] == 'tech-application')
        avant = copy.deepcopy(r)
        galerie.apply(r, g)
        self.assert_intacts(avant, r, 'galerie.apply')
        galerie.prepare(r, use_ai=False)
        self.assertIn('scene-verrou', [s['id'] for s in r['styleScenes']], 'galerie.prepare garde la scene verrouillee')
        galerie.sober(r)
        self.assertIn('g-genere', [x['id'] for x in r['graphics']], 'galerie.sober garde un graphisme genere verrouille')
        # plan verrouille : ses mots en couleur ne changent pas
        r = habille(self.s1)
        c = r['clips'][2]
        c['locked'] = True
        for w in c['words']:
            w['hl'] = False
        c['words'][0]['hl'] = True
        mots = copy.deepcopy(c['words'])
        reelmod.apply_template(r, 'reel-impact')
        self.assertEqual(r['clips'][2]['words'], mots, 'plan verrouille : mots en couleur figes')

    def test_plage(self):
        """Filet de securite de « Refaire ce passage » : rien ne change hors de la plage."""
        r = habille(self.s2)
        seg = montage.compute(r)
        temps = {(w['clip'], w['index']): w['start'] for w in seg['words']}
        avant = copy.deepcopy(r)
        plage = (15.0, 25.0)
        with verrous.sous_protection(r, plage, temps):
            # une passe brutale : tout retirer, tout recolorer
            r['graphics'], r['broll'], r['vectors'] = [], [], []
            r['sfx']['extra'] = []
            r['choreography']['cues'] = []
            for c in r['clips']:
                for w in c['words']:
                    w['hl'] = not w.get('hl')
                c['emojis'] = []
            r['graphics'].append({'id': 'g-nouveau', 'kind': 'motgeant', 'at': 18.0, 'duration': 1, 'props': {'text': 'NEUF'}, 'auto': True})
        self.assert_intacts(avant, r, 'plage')
        dedans = {(w['clip'], w['index']) for w in seg['words'] if plage[0] <= w['start'] < plage[1]}
        for c, ca in zip(r['clips'], avant['clips']):
            for i, (w, wa) in enumerate(zip(c['words'], ca['words'])):
                if (c['id'], i) in temps and (c['id'], i) not in dedans and not (temps[(c['id'], i)] < plage[1] and temps[(c['id'], i)] + .05 > plage[0]):
                    self.assertEqual(w.get('hl'), wa.get('hl'), f'mot hors plage {c["id"]}/{i} change')
        self.assertTrue(any(w.get('hl') != wa.get('hl') for c, ca in zip(r['clips'], avant['clips'])
                            for i, (w, wa) in enumerate(zip(c['words'], ca['words'])) if (c['id'], i) in dedans), 'la plage, elle, a change')
        self.assertIn('g-nouveau', [g['id'] for g in r['graphics']], 'un nouvel element dans la plage est garde')
        hors = [g['id'] for g in avant['graphics'] if g['at'] + g['duration'] <= plage[0] or g['at'] >= plage[1]]
        self.assertTrue(set(hors) <= {g['id'] for g in r['graphics']}, 'graphismes hors plage remis')
        # relecture limitee a la plage : les libres hors plage ne bougent pas
        r = habille(self.s2)
        avant = copy.deepcopy(r)
        sobriete.relire(r, 'reel-impact', tout=True, plage=plage)
        self.assertEqual(next(g for g in r['graphics'] if g['id'] == 'g-libre'), next(g for g in avant['graphics'] if g['id'] == 'g-libre'),
                         'hors plage : le graphisme libre ne bouge pas')

    def test_ancien_reel(self):
        """Un reel sans aucun champ V2 fonctionne comme avant et ne recoit aucun champ V2."""
        r = copy.deepcopy(self.s2)
        for k in ('notes', 'annotations', 'vectors', 'choreography'):
            r.pop(k, None)
        reelmod.apply_template(r, 'tech-application')
        sobriete.relire(r, tout=False)
        for k in ('notes', 'annotations', 'vectors', 'choreography'):
            self.assertNotIn(k, r, f'{k} ajoute a un ancien reel')


class SurCopie(unittest.TestCase):
    """refresh_ai et ensure ecrivent le reel : sur une copie du projet seulement."""

    @classmethod
    def setUpClass(cls):
        base = ROOT / 'runtime/cache/tmp/dcv2-architecte'
        base.mkdir(parents=True, exist_ok=True)
        cls.box = Path(tempfile.mkdtemp(prefix='verrous-', dir=base))
        cls.pdir = cls.box / 'script2'
        (cls.pdir / 'reels').mkdir(parents=True)
        shutil.copyfile(FIX / 'projects/script2/project.json', cls.pdir / 'project.json')
        cls.reel = habille(lire('projects/script2/reels/script.json'))
        cls.reel['clips'][1]['locked'] = True
        # pas de detourage (GPU, cache assets/detourage) pendant ces essais : seul le rangement du reel est teste
        from editeur import detourage
        cls._detourage = detourage.prepare
        detourage.prepare = lambda reel: None

    @classmethod
    def tearDownClass(cls):
        from editeur import detourage
        detourage.prepare = cls._detourage

    def ecrire(self):
        (self.pdir / 'reels/script.json').write_text(json.dumps(self.reel, ensure_ascii=False, indent=1), encoding='utf-8')

    def relu(self):
        return json.loads((self.pdir / 'reels/script.json').read_text(encoding='utf-8'))

    def test_refresh_ai(self):
        self.ecrire()
        sug = reelmod.refresh_ai(self.pdir)
        r = self.relu()
        self.assertEqual(sug['words'].get(self.reel['clips'][1]['id']), [], 'plan verrouille : aucune proposition')
        Verrous.assert_intacts(self, self.reel, r, 'refresh_ai')

    def test_ensure_style(self):
        self.ecrire()
        reelmod.ensure(self.pdir, None, template='produit-3d')
        Verrous.assert_intacts(self, self.reel, self.relu(), 'ensure --style')

    def test_ensure_complet(self):
        """Mise a jour complete (sans style) : les medias ne sont pas recalcules ici (_sources remplace)."""
        self.ecrire()
        garde = reelmod._sources
        reelmod._sources = lambda project, ids, cache, old=None: old
        try:
            reelmod.ensure(self.pdir, None)
        finally:
            reelmod._sources = garde
        Verrous.assert_intacts(self, self.reel, self.relu(), 'ensure')


if __name__ == '__main__':
    unittest.main(verbosity=2)
