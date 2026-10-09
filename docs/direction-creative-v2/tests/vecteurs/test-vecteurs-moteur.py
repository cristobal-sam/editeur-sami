"""Vecteurs V2 cote moteur (sans IA) : un vecteur retouche ou verrouille, et ses couleurs choisies a la main, survivent a
un changement de style, a la relecture de sobriete, au cerveau creatif, a la galerie, a ensure et a refresh_ai.
    python ../docs/direction-creative-v2/tests/vecteurs/test-vecteurs-moteur.py      (depuis engine/, environnement charge)
Donnees : copies EN MEMOIRE des reels figes fixtures/projects/script1 et script2 ; ensure et refresh_ai travaillent sur une COPIE du
projet dans runtime/cache/tmp/dcv2-vecteurs/moteur-<hasard>/ (jamais sur projects/).
Avec VEC_SORTIE=<fichier.json>, les reels obtenus sont ecrits pour test-vecteurs.mjs (qui calcule les couleurs affichees
avec le vrai code de remotion/src/vectors.tsx)."""
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FIX = HERE.parent / 'fixtures'  # donnees figees des tests (jamais les projets vivants de l'utilisateur)
sys.path.insert(0, str(ROOT / 'engine'))
os.environ['EDITEUR_LLM'] = '0'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
from editeur import creative, galerie, llm, sobriete  # noqa: E402
from editeur import reel as reelmod  # noqa: E402

llm.available = lambda: False  # aucune IA locale pendant ces essais
SORTIE = {}
STYLES = ('tech-application', 'reel-impact', 'documentaire', 'hormozi', 'luxe-minimal')
MANUELLES = {'principale': '#00C2FF', 'secondaire': '#0A2A66', 'contour': '#FFFFFF'}
NULLES = {'principale': None, 'secondaire': None, 'contour': None}


def lire(rel):
    return json.loads(((FIX if rel.startswith('projects/') else ROOT) / rel).read_text(encoding='utf-8'))


def vecteur(i, nom, at, **k):
    return {'id': i, 'asset': f'banque/vecteurs/{nom}.svg', 'at': at, 'duration': 2.0, 'x': .5, 'y': .35, 'w': .35, 'rotation': 0,
            'opacite': 1, 'couleurs': dict(NULLES), 'couleursManuelles': False, 'anim': {'entree': 'pop', 'sortie': 'fondu'}, **k}


def habille(r):
    """4 vecteurs : couleurs a la main (retouche), charte (retouche, couleurs automatiques), verrouille, automatique libre."""
    r = copy.deepcopy(r)
    r['vectors'] = [
        vecteur('v-manuel', 'explosion', 20.0, couleurs=dict(MANUELLES), couleursManuelles=True, manual=True, rotation=-12, w=.42,
                raison='Ajouté à la main : Explosion de BD'),
        vecteur('v-charte', 'etoile', 24.0, manual=True, raison='Ajouté à la main : Étoile'),
        vecteur('v-verrou', 'cercle', 28.0, locked=True, anim={'entree': 'trace', 'sortie': 'fondu'}),
        vecteur('v-auto', 'fleche', 0.4, auto=True, raison='proposition automatique'),  # sur l'accroche : la relecture l'ecarte
    ]
    return r


PROTEGES = ('v-manuel', 'v-charte', 'v-verrou')


def palette_utile(r):
    """Ce que vectors.tsx lit pour recolorer."""
    return {k: r.get(k) for k in ('style', 'design', 'brand', 'vectors', 'template')}


class Vecteurs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s1 = lire('projects/script1/reels/script.json')
        cls.s2 = lire('projects/script2/reels/script.json')

    def intacts(self, avant, apres, quoi):
        ref = {v['id']: v for v in avant['vectors']}
        got = {v['id']: v for v in apres.get('vectors') or []}
        for i in PROTEGES:
            self.assertIn(i, got, f'{quoi} : {i} a disparu')
            self.assertEqual(got[i], ref[i], f'{quoi} : {i} a ete modifie')
        self.assertEqual(got['v-manuel']['couleurs'], MANUELLES, f'{quoi} : couleurs manuelles changees')
        self.assertTrue(got['v-manuel']['couleursManuelles'], f'{quoi} : couleursManuelles perdu')
        self.assertEqual(got['v-charte']['couleurs'], NULLES, f'{quoi} : le vecteur « charte » a recu des couleurs figees')

    def test_changements_de_style(self):
        for nom, depart in (('script2', self.s2), ('script1', self.s1)):
            avant = habille(depart)
            r = copy.deepcopy(avant)
            for style in STYLES:
                reelmod.apply_template(r, style)
                self.intacts(avant, r, f'{nom} -> {style}')
                SORTIE[f'{nom}:{style}'] = palette_utile(r)
            # aller-retour : rien n'a bouge
            reelmod.apply_template(r, depart['template'])
            self.intacts(avant, r, f'{nom} aller-retour')

    def test_sobriete_creatif_galerie(self):
        avant = habille(self.s2)
        for tout in (True, False):
            r = copy.deepcopy(avant)
            rep = sobriete.relire(r, 'reel-impact', tout=tout)
            self.intacts(avant, r, f'sobriete tout={tout}')
            auto = next(v for v in r['vectors'] if v['id'] == 'v-auto')
            self.assertTrue(auto.get('suggested'), 'vecteur automatique sur l\'accroche : devient une proposition')
            self.assertGreaterEqual(rep['proteges'], 3)
        r = copy.deepcopy(avant)
        tpl = next(t for t in reelmod.list_templates() if t['id'] == 'reel-impact')
        creative.apply(r, None, tpl)
        self.intacts(avant, r, 'cerveau creatif')
        r = habille(self.s1)
        avant1 = copy.deepcopy(r)
        galerie.apply(r, next(t for t in reelmod.list_templates() if t['id'] == 'tech-application'))
        galerie.prepare(r, use_ai=False)
        self.intacts(avant1, r, 'galerie')

    def test_charte(self):
        """Une charte appliquee comme le fait l'interface (panels2 : brand + style) ne touche pas aux donnees des vecteurs :
        seules les couleurs AFFICHEES changent (calculees dans vectors.tsx, voir test-vecteurs.mjs)."""
        r = habille(self.s2)
        avant = copy.deepcopy(r)
        brand = {'client': 'essai', 'name': 'Charte essai', 'logo': None, 'logoPosition': 'haut-droite', 'logoSize': .16, 'logoOpacity': .85,
                 'bannerBg': '#7C3AED', 'bannerColor': '#FFFFFF', 'style': {'highlight': '#FF2D95'}, 'outro': {'enabled': False, 'text': '', 'duration': 2.5}}
        r['brand'] = brand
        r['style'] = {**r['style'], 'highlight': '#FF2D95'}
        self.intacts(avant, r, 'charte')
        SORTIE['script2:charte'] = palette_utile(r)
        reelmod.apply_template(r, 'tech-application')  # la charte passe par-dessus le style (reel.py)
        self.intacts(avant, r, 'charte + style')
        SORTIE['script2:charte+tech-application'] = palette_utile(r)


class SurCopie(unittest.TestCase):
    """ensure et refresh_ai ecrivent le reel : sur une copie du projet seulement."""

    @classmethod
    def setUpClass(cls):
        base = ROOT / 'runtime/cache/tmp/dcv2-vecteurs'
        base.mkdir(parents=True, exist_ok=True)
        cls.box = Path(tempfile.mkdtemp(prefix='moteur-', dir=base))
        cls.pdir = cls.box / 'script2'
        (cls.pdir / 'reels').mkdir(parents=True)
        shutil.copyfile(FIX / 'projects/script2/project.json', cls.pdir / 'project.json')
        cls.reel = habille(lire('projects/script2/reels/script.json'))
        from editeur import detourage
        cls._detourage = detourage.prepare
        detourage.prepare = lambda reel: None  # pas de detourage (GPU) pendant ces essais

    @classmethod
    def tearDownClass(cls):
        from editeur import detourage
        detourage.prepare = cls._detourage

    def ecrire(self):
        (self.pdir / 'reels/script.json').write_text(json.dumps(self.reel, ensure_ascii=False, indent=1), encoding='utf-8')

    def relu(self):
        return json.loads((self.pdir / 'reels/script.json').read_text(encoding='utf-8'))

    def test_ensure_style(self):
        self.ecrire()
        reelmod.ensure(self.pdir, None, template='tech-application')
        r = self.relu()
        Vecteurs.intacts(self, self.reel, r, 'ensure --style')
        SORTIE['copie:ensure-tech-application'] = palette_utile(r)

    def test_refresh_ai(self):
        self.ecrire()
        reelmod.refresh_ai(self.pdir)
        Vecteurs.intacts(self, self.reel, self.relu(), 'refresh_ai')

    def test_ensure_complet(self):
        self.ecrire()
        garde = reelmod._sources
        reelmod._sources = lambda project, ids, cache, old=None: old
        try:
            reelmod.ensure(self.pdir, None)
        finally:
            reelmod._sources = garde
        Vecteurs.intacts(self, self.reel, self.relu(), 'ensure')


if __name__ == '__main__':
    prog = unittest.main(verbosity=2, exit=False)
    if os.environ.get('VEC_SORTIE'):
        Path(os.environ['VEC_SORTIE']).write_text(json.dumps(SORTIE, ensure_ascii=False), encoding='utf-8')
    sys.exit(0 if prog.result.wasSuccessful() else 1)
