"""Tests hors ligne (sans IA) de la choregraphie V2 (engine/editeur/choregraphie.py).
    python ../docs/direction-creative-v2/tests/choregraphie/test-choregraphie.py      (depuis engine/, environnement charge)
Donnees : COPIES du reel fige fixtures/projects/script1 (Video 1) et de sa version Tech 3D cinematique
(docs/cerveau-creatif-v2-2026-09-30/avant/script-video1.json) dans runtime/cache/tmp/dcv2-choregraphie/essai-<hasard>/.
Rien n'est ecrit dans les donnees figees (verifie a la fin : empreinte du reel fige inchangee)."""
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'engine'))
os.environ['EDITEUR_LLM'] = '0'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
from editeur import choregraphie, llm, montage, sobriete, verrous  # noqa: E402
from editeur import reel as reelmod  # noqa: E402

llm.available = lambda: False  # aucune IA locale pendant ces essais

FIX = HERE.parent / 'fixtures'  # donnees figees des tests (jamais les projets vivants de l'utilisateur)
VRAI = FIX / 'projects/script1/reels/script.json'
TECH3D = ROOT / 'docs/cerveau-creatif-v2-2026-09-30/avant/script-video1.json'
ID = re.compile(r'^[A-Za-z0-9_:.-]{1,120}$')
TYPES = {'fondu', 'glisse', 'zoom', 'pop', 'trace', 'aucune'}
COURBES = {'douce', 'rapide', 'rebond', 'lineaire'}
DIRS = {'gauche', 'droite', 'haut', 'bas', None}
CIBLES = {'graphics', 'design', 'broll', 'vector', 'caption', 'banner'}
CUE_KEYS = {'id', 'cible', 'at', 'duree', 'entree', 'sortie', 'sync', 'raison', 'auto', 'locked', 'desactive', 'manual', 'meta'}


def empreinte(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()


def fenetres(cues):
    out = []
    for c in cues:
        if c.get('desactive') or c['entree']['type'] == 'aucune':
            continue
        out.append((c['at'], c['at'] + max(.05, c['entree']['duree']), c['id']))
    return out


class Choregraphie(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hash_vrai = empreinte(VRAI)
        base = ROOT / 'runtime/cache/tmp/dcv2-choregraphie'
        base.mkdir(parents=True, exist_ok=True)
        cls.box = Path(tempfile.mkdtemp(prefix='essai-', dir=base))
        cls.pdir = cls.box / 'script1'
        (cls.pdir / 'reels').mkdir(parents=True)
        shutil.copyfile(FIX / 'projects/script1/project.json', cls.pdir / 'project.json')
        shutil.copyfile(VRAI, cls.pdir / 'reels/script.json')
        shutil.copyfile(TECH3D, cls.pdir / 'reels/tech3d.json')
        cls.sans = {rid: montage.load(cls.pdir, rid) for rid in ('script', 'tech3d')}
        print(f'bac : {cls.box}')

    @classmethod
    def tearDownClass(cls):
        assert empreinte(VRAI) == cls.hash_vrai, 'le reel fige fixtures/projects/script1 a ete modifie !'
        print('reel fige fixtures/projects/script1/reels/script.json inchange (empreinte identique)')

    def ecrire(self, rid, r):
        montage.save(self.pdir, rid, r)

    def verifier(self, r, quoi):
        """Chaque mouvement est valide (memes regles que le serveur), motive, synchronise, sans entree simultanee,
        et rien sur l'accroche sauf le bandeau."""
        ch = r['choreography']
        cues = ch['cues']
        seg = montage.compute(r)
        rep = sobriete.reperes(r, seg, sobriete.budget(sobriete._template(r, None)))
        mots = {f"{w['clip']}:{w['index']}" for w in seg['words']}
        lieux = {f"{e['type']}:{e['id']}" for e in choregraphie.cibles(r, seg)}
        lieux |= {f"caption:{p['id']}" for p in choregraphie.pages(r, seg)}
        self.assertLessEqual(len(json.dumps(ch.get('meta') or {}, ensure_ascii=False).encode()), 2048, f'{quoi} : meta trop gros')
        self.assertEqual(len({c['id'] for c in cues}), len(cues), f'{quoi} : ids en double')
        for c in cues:
            self.assertTrue(set(c) <= CUE_KEYS, f'{quoi} : champ inconnu {set(c) - CUE_KEYS}')
            self.assertTrue(ID.match(c['id']) and ID.match(c['cible']['id']), f'{quoi} : id invalide {c["id"]}')
            self.assertIn(c['cible']['type'], CIBLES)
            for m in (c['entree'], c['sortie']):
                self.assertIn(m['type'], TYPES)
                self.assertIn(m['courbe'], COURBES)
                self.assertIn(m.get('direction'), DIRS)
                self.assertTrue(0 <= m['duree'] <= 10)
            self.assertIn(c['sync']['sur'], {'mot', 'temps', 'battement'})
            if c['sync']['sur'] == 'mot':
                self.assertIn(c['sync']['ref'], mots, f'{quoi} : mot de synchro introuvable')
            self.assertTrue(10 < len(c['raison']) <= 500, f'{quoi} : raison absente')
            self.assertIsInstance(c['auto'], bool)
            self.assertIsInstance(c['locked'], bool)
            self.assertLessEqual(len(json.dumps(c.get('meta') or {}, ensure_ascii=False).encode()), 2048)
            self.assertIn(f"{c['cible']['type']}:{c['cible']['id']}", lieux, f'{quoi} : cible absente {c["cible"]}')
            if c['auto'] and not verrous.protege(c) and c['cible']['type'] != 'banner':
                self.assertGreaterEqual(c['at'], rep['accroche'] - .05, f'{quoi} : mouvement sur l\'accroche {c["id"]} ({c["at"]})')
        w = fenetres(cues)
        for i, a in enumerate(w):
            for b in w[i + 1:]:
                self.assertFalse(a[0] < b[1] and a[1] > b[0], f'{quoi} : deux entrees en meme temps {a} {b}')
        return seg, rep

    def test_1_generation(self):
        """Video 1 (copie) : mouvements motives, synchronises sur les mots ou la musique, aucune entree simultanee."""
        for rid in ('script', 'tech3d'):
            self.ecrire(rid, copy.deepcopy(self.sans[rid]))
            t = time.time()
            out = choregraphie.regenerer(self.pdir, rid)
            r = montage.load(self.pdir, rid)
            cues = r['choreography']['cues']
            print(f"\n[{rid} / {r.get('template')}] {out['cues']} mouvements en {time.time() - t:.1f} s — {out['resume']}")
            for c in cues:
                print(f"  {c['at']:6.2f} {c['cible']['type']:8} {c['cible']['id']:14} {c['entree']['type']:6} {c['entree']['duree']:.2f}s "
                      f"{c['entree']['courbe']:7} sync={c['sync']['sur']:9} | {c['raison'][:110]}")
            self.assertEqual(out['cues'], len(cues))
            self.assertGreaterEqual(len(cues), 3, f'{rid} : trop peu de mouvements')
            seg, rep = self.verifier(r, rid)
            self.assertTrue(any(c['sync']['sur'] == 'mot' for c in cues), 'aucun mouvement sur un mot')
            self.assertTrue(any('temps de la musique' in c['raison'] for c in cues), 'aucun mouvement sur la musique')
            roles = {c['meta']['role'] for c in cues}
            self.assertTrue({'preuve', 'solution'} & roles or {'probleme'} & roles)
            # la preuve « x5 moins cher » (Video 1) entre en « pop » sur « cinq »
            if rid == 'script':
                g2 = next(c for c in cues if c['cible']['id'] == 'g2-chiffre')
                self.assertEqual(g2['entree']['type'], 'pop')
                self.assertIn('cinq', g2['raison'])
            # rien n'a ete cree ni deplace : memes elements qu'avant
            for k in ('graphics', 'broll', 'styleScenes', 'vectors', 'banner', 'clips'):
                self.assertEqual(r.get(k), self.sans[rid].get(k), f'{rid} : {k} modifie par la choregraphie')

    def test_2_verrous_et_retouches(self):
        """Un mouvement verrouille survit a « Refaire » (meme --tout) ; une retouche survit a « Refaire » (libres)."""
        r = copy.deepcopy(self.sans['script'])
        choregraphie.actualiser(r, creer=True)
        cues = r['choreography']['cues']
        a, b = cues[0], cues[1]
        a.update(locked=True, entree={'type': 'trace', 'direction': 'droite', 'duree': 1.2, 'courbe': 'lineaire'}, raison='choix du monteur : tracé lent')
        b.update(manual=True, desactive=True)
        verrou, retouche = copy.deepcopy(a), copy.deepcopy(b)
        self.ecrire('script', r)
        choregraphie.regenerer(self.pdir, 'script')
        got = {c['id']: c for c in montage.load(self.pdir, 'script')['choreography']['cues']}
        self.assertEqual(got[a['id']], verrou, 'verrouille modifie par Refaire')
        self.assertEqual(got[b['id']], retouche, 'retouche modifiee par Refaire')
        self.assertEqual(sum(1 for c in got.values() if c['cible'] == a['cible']), 1, 'deux mouvements sur la meme cible')
        out = choregraphie.regenerer(self.pdir, 'script', libres=False)
        got = {c['id']: c for c in montage.load(self.pdir, 'script')['choreography']['cues']}
        self.assertEqual(got[a['id']], verrou, 'verrouille modifie par Refaire --tout')
        self.assertFalse(got[b['id']].get('manual') or got[b['id']].get('desactive'), '--tout : la retouche est recalculee')
        print(f"\n--tout : {out['resume']}")
        # choregraphie entierement verrouillee : rien ne change, meme avec --tout
        r = montage.load(self.pdir, 'script')
        r['choreography']['locked'] = True
        avant = copy.deepcopy(r['choreography'])
        self.ecrire('script', r)
        out = choregraphie.regenerer(self.pdir, 'script', libres=False)
        self.assertEqual(montage.load(self.pdir, 'script')['choreography'], avant)
        self.assertIn('verrouillée', out['resume'])

    def test_3_changement_de_style(self):
        """Changement de style (aller-retour) : le mouvement verrouille et la retouche restent identiques ; les libres
        suivent les elements du nouveau style ; une choregraphie verrouillee ne bouge pas du tout."""
        r = copy.deepcopy(self.sans['tech3d'])
        choregraphie.actualiser(r, creer=True)
        cues = r['choreography']['cues']
        a = next(c for c in cues if c['cible']['type'] == 'design')
        a.update(locked=True, sortie={'type': 'zoom', 'direction': None, 'duree': .5, 'courbe': 'rebond'})
        b = next(c for c in cues if c['id'] != a['id'])
        b.update(manual=True, entree={**b['entree'], 'duree': 1.0})
        verrou, retouche = copy.deepcopy(a), copy.deepcopy(b)
        for style in ('reel-impact', 'tech-application', 'produit-3d'):
            reelmod.apply_template(r, style)
            got = {c['id']: c for c in r['choreography']['cues']}
            self.assertEqual(got.get(a['id']), verrou, f'{style} : mouvement verrouille modifie')
            self.assertEqual(got.get(b['id']), retouche, f'{style} : retouche modifiee')
            libres = [c for c in r['choreography']['cues'] if not verrous.protege(c)]
            print(f"\n{style} : {len(r['choreography']['cues'])} mouvements ({len(libres)} libres) — {r['choreography']['meta']['resume']}")
            self.assertTrue(all(c['auto'] for c in libres))
        r['choreography']['locked'] = True
        avant = copy.deepcopy(r['choreography'])
        reelmod.apply_template(r, 'reel-impact')
        self.assertEqual(r['choreography'], avant, 'choregraphie verrouillee changee par le style')

    def test_4_ancien_reel(self):
        """Un reel sans choregraphie n'en recoit pas au changement de style (image et fichier comme avant)."""
        r = copy.deepcopy(self.sans['script'])
        r.pop('choreography', None)
        reelmod.apply_template(r, 'reel-impact')
        self.assertNotIn('choreography', r)
        self.assertIsNone(choregraphie.actualiser(r))
        self.assertNotIn('choreography', r)

    def test_5_plage(self):
        """actualiser(plage) (« Refaire ce passage ») : les mouvements hors du passage restent octet pour octet."""
        r = copy.deepcopy(self.sans['script'])
        choregraphie.actualiser(r, creer=True)
        for c in r['choreography']['cues']:
            c['raison'] = 'ancienne ' + c['raison']  # marque : un mouvement recalcule perd ce prefixe
        avant = {c['id']: copy.deepcopy(c) for c in r['choreography']['cues']}
        plage = (33.0, 40.0)
        choregraphie.actualiser(r, plage=plage)
        apres = {c['id']: c for c in r['choreography']['cues']}
        dedans = hors = 0
        for k, c in avant.items():
            if c['at'] + c['duree'] <= plage[0] or c['at'] >= plage[1]:
                self.assertEqual(apres.get(k), c, f'hors plage : {k} change')
                hors += 1
            elif k in apres:
                self.assertFalse(apres[k]['raison'].startswith('ancienne'), f'dans la plage : {k} non recalcule')
                dedans += 1
        self.assertTrue(hors and dedans, f'essai sans objet (hors={hors}, dedans={dedans})')
        self.verifier(r, 'plage')

    def test_6_sobriete(self):
        """Deux elements automatiques qui arrivent en meme temps : un seul entre avec un mouvement, l'autre garde son
        animation d'origine (raison dite) ; rien n'est retire ni deplace par la choregraphie."""
        r = copy.deepcopy(self.sans['script'])
        r['design'] = {**(r.get('design') or {}), 'suppressExtras': False}
        r['graphics'] = [{'id': 'g-a', 'kind': 'chiffre', 'at': 44.0, 'duration': 2.0, 'props': {'value': 3, 'suffix': ' h'}, 'auto': True},
                         {'id': 'g-b', 'kind': 'motgeant', 'at': 44.05, 'duration': 1.5, 'props': {'text': 'VITE'}, 'auto': True},
                         {'id': 'g-hook', 'kind': 'motgeant', 'at': 1.0, 'duration': 1.5, 'props': {'text': 'STOP'}, 'manual': True}]
        graphics = copy.deepcopy(r['graphics'])
        choregraphie.actualiser(r, creer=True)
        cues = {c['cible']['id']: c for c in r['choreography']['cues']}
        self.assertEqual(r['graphics'], graphics, 'la choregraphie a change les elements')
        actifs = [k for k in ('g-a', 'g-b') if cues[k]['entree']['type'] != 'aucune']
        self.assertEqual(len(actifs), 1, f'deux entrees en meme temps : {actifs}')
        simple = cues['g-b' if actifs == ['g-a'] else 'g-a']
        self.assertIn('même moment', simple['raison'])
        self.assertNotIn('g-hook', cues, "mouvement sur l'accroche")
        self.verifier(r, 'sobriete')

    def test_7_pages_identiques_a_l_image(self):
        """Pages de sous-titres et scenes du style : memes temps que timeline.ts (pages, designScenes)."""
        for rid in ('script', 'tech3d'):
            r = self.sans[rid]
            seg = montage.compute(r)
            f = self.box / f'{rid}-pages.json'
            f.write_text(json.dumps(r, ensure_ascii=False), encoding='utf-8')
            js = self.box / 'pages.mjs'
            url = (ROOT / 'remotion/src/timeline.ts').as_uri()
            js.write_text(f"import fs from 'node:fs'; import {{pages, designScenes}} from '{url}';\n"
                          "const r = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));\n"
                          "console.log(JSON.stringify({pages: pages(r).map(p => [`${p.words[0].clip}:${p.words[0].index}`, p.start, p.end]),"
                          " scenes: designScenes(r).map(s => [s.id, s.at, s.end])}));\n", encoding='utf-8')
            ts = json.loads(subprocess.run(['node', str(js), str(f)], capture_output=True, text=True, encoding='utf-8', check=True).stdout)
            py = [[p['id'], p['start'], p['end']] for p in choregraphie.pages(r, seg)]
            self.assertEqual([p[0] for p in py], [p[0] for p in ts['pages']], f'{rid} : pages differentes')
            for a, b in zip(py, ts['pages']):
                self.assertAlmostEqual(a[1], b[1], places=6)
                self.assertAlmostEqual(a[2], b[2], places=6)
            sc = [[s['id'], a, e] for s, a, e in choregraphie.scenes(r, seg)]
            self.assertEqual([s[0] for s in sc], [s[0] for s in ts['scenes']], f'{rid} : scenes differentes')
            for a, b in zip(sc, ts['scenes']):
                self.assertAlmostEqual(a[1], b[1], places=6)
            print(f'\n{rid} : {len(py)} pages et {len(sc)} scenes identiques a timeline.ts')

    def test_8_musique(self):
        """Grille de la musique : librosa une fois, puis cache ; tempo coherent avec styles/musiques.json."""
        g = choregraphie.grille('music/tech.ogg')
        self.assertIsNotNone(g)
        self.assertLess(abs(g['bpm'] - 122), 4, f"tempo {g['bpm']}")
        self.assertGreater(len(g['beats']), 50)
        t = time.time()
        self.assertEqual(choregraphie.grille('music/tech.ogg'), g)
        self.assertLess(time.time() - t, .5, 'cache non utilise')
        self.assertIsNone(choregraphie.grille('../cles-api.env'))
        self.assertIsNone(choregraphie.grille('music/absente.ogg'))
        r = copy.deepcopy(self.sans['script'])
        beats, info = choregraphie.battements(r, 71.6)
        self.assertTrue(beats and beats[-1] <= 72.1 and info['bpm'] == 122, 'grille en boucle sur la duree du montage')
        r['music']['enabled'] = False
        self.assertEqual(choregraphie.battements(r, 71.6), ([], None))

    def test_9_ligne_de_commande(self):
        """python -m editeur choregraphie <projet> --reel <id> [--tout] : une ligne JSON, code 0."""
        self.ecrire('script', copy.deepcopy(self.sans['script']))
        py = ROOT / 'runtime/venv/Scripts/python.exe'
        for extra in ([], ['--tout']):
            p = subprocess.run([str(py), '-m', 'editeur', 'choregraphie', str(self.pdir), '--reel', 'script', *extra],
                               cwd=ROOT / 'engine', capture_output=True, text=True, encoding='utf-8',
                               env={**os.environ, 'EDITEUR_LLM': '0', 'PYTHONIOENCODING': 'utf-8'})  # comme le serveur
            self.assertEqual(p.returncode, 0, p.stderr[-800:])
            out = json.loads(p.stdout.strip().splitlines()[-1])
            self.assertGreater(out['cues'], 0)
            self.assertIn('mouvement', out['resume'])
        print(f"\nligne de commande : {out}")

    def test_10_elements_verrouilles(self):
        """(revue) Un element VERROUILLE garde sa maniere d'entrer (mouvement identique aux changements de style, meme
        avec --tout) ; un vecteur pose a la main garde l'animation choisie dans son reglage (aucun mouvement ajoute) ;
        un « trace » n'est jamais propose a un vecteur sans trait."""
        r = copy.deepcopy(self.sans['script'])
        r.pop('choreography', None)
        vec = lambda nom, at, **k: {'id': f'v-{nom}', 'asset': f'banque/vecteurs/{nom}.svg', 'at': at, 'duration': 2.0, 'x': .5,
                                    'y': .45, 'w': .35, 'rotation': 0, 'opacite': 1, 'couleurs': {'principale': None, 'secondaire': None,
                                    'contour': None}, 'couleursManuelles': False, 'anim': {'entree': 'glisse-gauche', 'sortie': 'fondu'}, **k}
        # pendant les revelations (29,7 s et 48,1 s) : fleche verrouillee, explosion posee a la main, deux vecteurs automatiques
        r['vectors'] = [vec('fleche', 30.4, manual=True, locked=True), vec('explosion', 49.0, manual=True),
                        vec('cercle', 31.0, auto=True), vec('etoile', 49.6, auto=True)]
        choregraphie.actualiser(r, creer=True)
        cues = {c['cible']['id']: c for c in r['choreography']['cues']}
        self.assertNotIn('v-fleche', cues, 'mouvement ajoute a un vecteur verrouille')
        self.assertNotIn('v-explosion', cues, 'mouvement ajoute a un vecteur pose a la main')
        for k in ('v-cercle', 'v-etoile'):
            if k in cues:
                trace_ok = k == 'v-cercle'
                self.assertTrue(cues[k]['entree']['type'] != 'trace' or trace_ok, f'{k} : trace propose a un dessin sans trait')
        self.verifier(r, 'vecteurs')
        # graphisme verrouille : son mouvement (libre) reste identique au changement de style et a « Refaire --tout »
        g = next(x for x in r['graphics'] if x['id'] == 'g2-chiffre')
        g['locked'] = True
        avant = copy.deepcopy(cues['g2-chiffre'])
        for style in ('reel-impact', 'documentaire', 'tech-application'):
            reelmod.apply_template(r, style)
            got = next(c for c in r['choreography']['cues'] if c['cible']['id'] == 'g2-chiffre')
            self.assertEqual(got, avant, f'{style} : mouvement du graphisme verrouille change')
        self.ecrire('script', r)
        choregraphie.regenerer(self.pdir, 'script', libres=False)
        got = next(c for c in montage.load(self.pdir, 'script')['choreography']['cues'] if c['cible']['id'] == 'g2-chiffre')
        self.assertEqual(got, avant, '--tout : mouvement du graphisme verrouille change')

    def test_11_temps_actuel_et_chemins(self):
        """(revue) La sobriete compte un mouvement garde au temps ACTUEL de son element (le cache cue.at peut dater
        d'avant un deplacement) ; la grille musicale ne sort jamais de assets/ (lecteur « C:/… »)."""
        r = copy.deepcopy(self.sans['script'])
        r.pop('choreography', None)
        r['vectors'] = [{'id': 'vx', 'asset': 'banque/vecteurs/coeur.svg', 'at': 12.0, 'duration': 2, 'x': .5, 'y': .5, 'w': .3,
                         'rotation': 0, 'opacite': 1, 'couleurs': {'principale': None, 'secondaire': None, 'contour': None},
                         'couleursManuelles': False, 'anim': {'entree': 'pop', 'sortie': 'fondu'}, 'manual': True}]
        base = choregraphie.actualiser(r, None, creer=True)
        notif = next(c for c in base['cues'] if c['cible']['type'] == 'design' and c['entree']['type'] != 'aucune')
        base['cues'].append({'id': 'cue-vector-vx', 'cible': {'type': 'vector', 'id': 'vx'}, 'at': 12.0, 'duree': 2.0,
                             'entree': {'type': 'zoom', 'direction': None, 'duree': .4, 'courbe': 'douce'},
                             'sortie': {'type': 'fondu', 'direction': None, 'duree': .3, 'courbe': 'douce'},
                             'sync': {'sur': 'temps', 'ref': None}, 'raison': 'retouche du monteur', 'auto': False,
                             'locked': False, 'manual': True})
        r['vectors'][0]['at'] = notif['at']  # le vecteur est glisse dans la piste Graphismes, sur l'entree de la notification
        out = choregraphie.actualiser(r, None)
        new = next(c for c in out['cues'] if c['id'] == notif['id'])
        self.assertEqual(new['entree']['type'], 'aucune', 'deux entrees au meme moment (cache at perime)')
        self.assertIn('même moment', new['raison'])
        for p in ('C:/Windows/win.ini', 'C:x.ogg', 'D:/Tools/editeur_sami/assets/music/tech.ogg'):
            self.assertIsNone(choregraphie.grille(p), p)


if __name__ == '__main__':
    unittest.main(verbosity=2)
