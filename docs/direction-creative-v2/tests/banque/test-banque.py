"""Tests hors ligne (sans IA, sans export) de la banque locale V2 (engine/editeur/banque.py + regles de app/ui/banque.tsx).
    python ../docs/direction-creative-v2/tests/banque/test-banque.py      (depuis engine/, environnement charge)
Bac : runtime/cache/tmp/dcv2-banque/catalogue-<hasard>/ : assets/ propre au bac (catalogue, sons crees, apercus) avec des
JONCTIONS EN LECTURE vers assets/sfx et assets/overlays (retirees a la fin avec os.rmdir : le lien seulement, jamais sa
cible). Reels : copies EN MEMOIRE des reels figes fixtures/projects/script1 et script2 (jamais reecrits)."""
import copy
import functools
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FIX = HERE.parent / 'fixtures'  # donnees figees des tests
sys.path.insert(0, str(ROOT / 'engine'))
os.environ['EDITEUR_LLM'] = '0'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
import soundfile as sf  # noqa: E402
from editeur import banque, llm, montage, sobriete, verrous  # noqa: E402
from editeur import reel as reelmod  # noqa: E402

llm.available = lambda: False  # aucune IA locale pendant ces essais
PYTHON = sys.executable
BAC_PARENT = ROOT / 'runtime/cache/tmp/dcv2-banque'
REELS = {k: json.loads((FIX / f'projects/{k}/reels/script.json').read_text(encoding='utf-8')) for k in ('script1', 'script2')}


def jonction(lien, cible):
    import _winapi
    _winapi.CreateJunction(str(cible), str(lien))


def est_jonction(p):
    try:
        return bool(os.lstat(p).st_file_attributes & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT
    except (OSError, AttributeError):
        return False


def png_taille(p):
    b = Path(p).read_bytes()[:24]
    assert b[:8] == b'\x89PNG\r\n\x1a\n', f'{p} : pas un PNG'
    return struct.unpack('>II', b[16:24])


def sans_id(el):
    return {k: v for k, v in el.items() if k != 'id'}


class Banque(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        BAC_PARENT.mkdir(parents=True, exist_ok=True)
        cls.bac = Path(tempfile.mkdtemp(prefix='catalogue-', dir=BAC_PARENT))
        a = cls.bac / 'assets'
        (a / 'banque').mkdir(parents=True)
        cls.liens = [a / 'sfx', a / 'overlays']
        jonction(a / 'sfx', ROOT / 'assets/sfx')
        jonction(a / 'overlays', ROOT / 'assets/overlays')
        print(f'BAC={cls.bac}')
        cls.rapport = banque.construire(cls.bac)
        print('construire (bac, sans vecteurs) :', json.dumps(cls.rapport, ensure_ascii=False))
        cls.cat = json.loads((a / banque.CATALOGUE).read_text(encoding='utf-8'))

    @classmethod
    def tearDownClass(cls):
        for lien in cls.liens:
            if est_jonction(lien):
                os.rmdir(lien)  # retire le lien seulement

    # ------------------------------------------------------------ 1. construction
    def test_1_construction(self):
        a = self.bac / 'assets'
        compte = self.cat['compte']
        attendus_sons = len(list((ROOT / 'assets/sfx/editeur').glob('*.wav'))) + len(banque._sons_crees())
        kenney = 0
        for f in (ROOT / 'assets/sfx/kenney').rglob('*.ogg'):
            if f.stem.lower() != 'preview' and sf.info(str(f)).duration <= banque.LONGUEUR_MAX:
                kenney += 1
        attendus_sons += kenney
        print(f'comptes : {compte} (sons attendus : {attendus_sons} dont Kenney {kenney})')
        self.assertEqual(compte['son'], attendus_sons)
        self.assertEqual(compte['template'], len(banque.TEMPLATES))
        self.assertEqual(compte['effet'], len(banque.EFFETS))
        self.assertEqual(compte['vecteur'], 0, 'aucun vecteur dans ce bac : liste vide, sans erreur')
        ids = [e['id'] for e in self.cat['entrees']]
        self.assertEqual(len(ids), len(set(ids)), 'identifiants uniques')
        for e in self.cat['entrees']:
            self.assertRegex(e['id'], r'^[A-Za-z0-9_.:-]{1,120}$')
            self.assertIn(e['type'], banque.TYPES)
            for k in ('nom', 'categorie', 'licence', 'provenance', 'apercu'):
                self.assertTrue(str(e.get(k) or '').strip(), f'{e["id"]} : « {k} » manque')
            self.assertIn(e['intensite'], (1, 2, 3))
            self.assertTrue(e['motsCles'] and set(e['formats']) <= set(banque.FORMATS))
            self.assertFalse('..' in e['apercu'].split('/') or e['apercu'].startswith('/'), 'apercu toujours sous assets/')
            self.assertTrue((a / e['apercu']).is_file(), f'{e["id"]} : apercu absent ({e["apercu"]})')
            if e['fichier']:
                self.assertTrue((a / e['fichier']).is_file(), f'{e["id"]} : fichier absent')
                self.assertFalse(e['fichier'].startswith('music/'), 'la musique n\'est pas dans la banque (pas de type « musique »)')
            if e['type'] == 'son':
                self.assertLessEqual(e['duree'], banque.LONGUEUR_MAX)
                self.assertTrue(0 < e['params']['gain'] <= 4)
                self.assertEqual(png_taille(a / e['apercu']), (240, 64), 'forme d\'onde 240 x 64')
                if e['source'] == 'kenney':
                    self.assertIn('CC0', e['licence'])
                    lic = re.search(r'assets/(sfx/kenney/[^/]+/License\.txt)', e['provenance'])
                    self.assertTrue(lic and (ROOT / 'assets' / lic.group(1)).is_file(), 'licence du pack Kenney conservee')
                if e['source'] == 'banque':
                    self.assertIn('Créé localement', e['provenance'])
        crees = sorted(p.stem for p in (a / 'banque/sons').glob('*.wav'))
        self.assertEqual(crees, sorted(banque._sons_crees()), 'sons crees ici (sfxgen.py)')
        self.assertTrue((a / 'banque/sons/LICENCE.txt').is_file())
        for nom in crees:
            info = sf.info(str(a / f'banque/sons/{nom}.wav'))
            self.assertTrue(0.1 < info.duration <= banque.LONGUEUR_MAX and info.samplerate == 48000 and info.channels == 2, nom)
        self.assertTrue(all(x['raison'] for x in self.cat['ecartes']))
        par_type = {t: sorted({e['categorie'] for e in self.cat['entrees'] if e['type'] == t}) for t in banque.TYPES}
        print('categories :', json.dumps(par_type, ensure_ascii=False))
        # meme contenu reconstruit a l'identique (hors date) : aucune forme d'onde refaite
        r2 = banque.construire(self.bac)
        self.assertEqual(r2['apercus_faits'], 0)
        self.assertEqual(r2['sons_crees'], [])

    # ------------------------------------------------------------ 2. vecteurs : absents, ajoutes, refuses, re-indexes
    def test_2_vecteurs_reindexes(self):
        a = self.bac / 'assets'
        d = a / 'banque/vecteurs'
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'assets/banque/vecteurs/fleche.svg', d / 'fleche.svg')
        shutil.copy2(ROOT / 'assets/banque/vecteurs/fleche.json', d / 'fleche.json')
        (d / 'sans-fiche.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" '
                                          'style="fill:var(--v-principale,#f00)"/></svg>', encoding='utf-8')
        (d / 'piege.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><script>alert(1)</script></svg>', encoding='utf-8')
        (d / 'lien.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><image href="http://x.y/a.png"/></svg>', encoding='utf-8')
        c = banque.catalogue({'type': 'vecteur'}, racine=self.bac)  # le dossier a change : re-indexe tout seul
        ids = sorted(e['id'] for e in c['entrees'])
        self.assertEqual(ids, ['vecteur:fleche', 'vecteur:sans-fiche'])
        fl = next(e for e in c['entrees'] if e['id'] == 'vecteur:fleche')
        self.assertEqual((fl['nom'], fl['categorie'], fl['apercu'], fl['fichier']), ('Flèche droite', 'flèches', 'banque/vecteurs/fleche.svg', 'banque/vecteurs/fleche.svg'))
        self.assertIn('Création originale', fl['licence'])
        self.assertTrue(fl['params']['recolorable'])
        sf_ = next(e for e in c['entrees'] if e['id'] == 'vecteur:sans-fiche')
        self.assertEqual(sf_['licence'], 'À vérifier (fiche absente)')
        cat = json.loads((a / banque.CATALOGUE).read_text(encoding='utf-8'))
        refus = {x['fichier']: x['raison'] for x in cat['ecartes']}
        self.assertIn('script', refus['banque/vecteurs/piege.svg'])
        self.assertIn('lien externe', refus['banque/vecteurs/lien.svg'])
        # la vraie bibliotheque de l'agent « vecteurs » (lue par une jonction, jamais modifiee)
        shutil.rmtree(d)
        jonction(d, ROOT / 'assets/banque/vecteurs')
        self.liens.append(d)
        c = banque.catalogue({}, racine=self.bac)
        vrais = len(list((ROOT / 'assets/banque/vecteurs').glob('*.svg')))
        self.assertEqual(c['compte']['vecteur'] + sum(1 for e in c['entrees'] if e['type'] == 'effet' and e['source'] == 'vecteurs'), vrais)
        print(f'vecteurs de l\'agent « vecteurs » indexes : {c["compte"]["vecteur"]} sur {vrais} SVG')
        self.__class__.cat = json.loads((a / banque.CATALOGUE).read_text(encoding='utf-8'))

    # ------------------------------------------------------------ 3. filtres
    def test_3_filtres(self):
        tous = self.cat['entrees']
        f = banque.filtrer
        sons = f(tous, {'type': 'son'})
        self.assertTrue(sons and all(e['type'] == 'son' for e in sons) and len(sons) == self.cat['compte']['son'])
        wh = f(tous, {'type': 'son', 'categorie': 'whoosh'})
        self.assertTrue(all(e['categorie'] == 'whoosh' for e in wh))
        self.assertTrue({'son:banque:swoosh-rapide', 'son:editeur:whoosh-court', 'son:banque:whoosh-grave'} <= {e['id'] for e in wh})
        self.assertEqual([e['id'] for e in f(tous, {'categorie': 'montee'})], [e['id'] for e in f(tous, {'categorie': 'montée'})], 'categorie sans accents')
        a, b = f(tous, {'q': 'fleche'}), f(tous, {'q': 'FLÈCHE'})
        self.assertEqual([e['id'] for e in a], [e['id'] for e in b], 'recherche insensible aux accents et a la casse')
        self.assertIn('vecteur:fleche', [e['id'] for e in a])
        im = f(tous, {'q': 'impact métal'})
        self.assertTrue(im)
        for e in im:
            j = banque._plat(' '.join([e['nom'], e['categorie'], *e['motsCles'], e.get('description', '')]))
            self.assertTrue('impact' in j and 'metal' in j, e['id'])
        self.assertTrue(all(e['intensite'] == 3 for e in f(tous, {'intensite': 3})))
        self.assertTrue(all(e['type'] == 'template' and e['intensite'] == 1 for e in f(tous, {'type': 'template', 'intensite': 1})))
        self.assertTrue(f(tous, {'q': 'riser'})[0]['nom'].lower().startswith('riser'), 'pertinence : nom qui commence par le mot')
        self.assertEqual(len(f(tous, {'format': '16:9'})), len(tous))
        faux = [{**tous[0], 'id': 'x:1', 'formats': ['9:16']}]
        self.assertEqual(f(faux, {'format': '16:9'}), [])
        self.assertEqual(f(tous, {'q': 'zzzqqq'}), [])
        with self.assertRaises(ValueError):
            f(tous, {'type': 'musique'})
        for t in banque.TYPES:
            self.assertTrue(f(tous, {'type': t, 'q': ''}), f'au moins une entree de type {t}')
        print('filtres : sons', len(sons), '· whoosh', len(wh), '· « fleche »', len(a), '· « impact métal »', len(im))

    # ------------------------------------------------------------ 4. ligne de commande (sortie JSON)
    def test_4_cli(self):
        env = {**os.environ, 'EDITEUR_ROOT': str(self.bac), 'PYTHONIOENCODING': 'utf-8'}  # comme le serveur (app/server.mjs)
        r = subprocess.run([PYTHON, '-m', 'editeur', 'banque', 'catalogue', '--type', 'son', '--categorie', 'whoosh', '--q', 'rapide'],
                           cwd=ROOT / 'engine', env=env, capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertTrue(out['total'] >= 1 and all(e['type'] == 'son' and e['categorie'] == 'whoosh' for e in out['entrees']))
        self.assertIn('son', out['categories'])
        r = subprocess.run([PYTHON, '-m', 'editeur', 'banque', 'apercu', 'template:mot-geant'], cwd=ROOT / 'engine', env=env,
                           capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertEqual(json.loads(r.stdout.strip().splitlines()[-1]), {'id': 'template:mot-geant', 'apercu': 'banque/apercus/modeles/mot-geant.svg'})
        print('CLI :', out['total'], 'whoosh « rapide »')

    # ------------------------------------------------------------ 5. memes regles dans l'interface et dans le moteur
    def test_5_regles_ts_identiques(self):
        s1, s2 = copy.deepcopy(REELS['script1']), copy.deepcopy(REELS['script2'])
        edito = copy.deepcopy(s1)
        edito['design'] = {**edito['design'], 'mode': 'editorial'}
        rallume = copy.deepcopy(s1)
        rallume['design'] = {**rallume['design'], 'suppressExtras': False}
        marque = copy.deepcopy(s2)
        marque['brand'] = {'client': 'x', 'name': 'Client X', 'logo': 'assets/clients/x/logo.png', 'logoPosition': 'haut-droite', 'logoSize': .16,
                           'logoOpacity': .85, 'bannerBg': '#112233', 'bannerColor': '#FFFFFF', 'style': {'highlight': '#FF3355'},
                           'outro': {'enabled': False, 'text': '', 'duration': 2}}
        reels = {'s1': s1, 's2': s2, 'edito': edito, 'rallume': rallume, 'marque': marque}
        tous = self.cat['entrees']
        filtres = [{}, {'type': 'son'}, {'type': 'son', 'categorie': 'whoosh'}, {'q': 'fleche'}, {'q': 'FLÈCHE'}, {'q': 'impact métal'},
                   {'intensite': 3}, {'type': 'template', 'intensite': 1}, {'q': 'riser'}, {'categorie': 'montee'}, {'format': '4:5', 'q': 'liste'},
                   {'type': 'vecteur', 'q': 'cercle'}, {'q': 'notification'}]
        choix = [e['id'] for e in tous if e['type'] in ('template', 'effet', 'vecteur')] + \
            ['son:editeur:whoosh-court', 'son:banque:impact-cinema', next(e['id'] for e in tous if e['source'] == 'kenney')]
        ajouts = [{'reel': r, 'id': i, 'at': 15.37} for r in reels for i in choix]
        vec = {'id': 'v1', 'asset': 'banque/vecteurs/fleche.svg', 'at': 1, 'duration': 2, 'x': .5, 'y': .35, 'w': .35, 'rotation': 0, 'opacite': 1,
               'couleurs': {'principale': None, 'secondaire': None, 'contour': None}, 'couleursManuelles': False, 'anim': {'entree': 'pop', 'sortie': 'fondu'}}
        retouche = {**vec, 'couleurs': {'principale': '#00AAFF', 'secondaire': None, 'contour': None}, 'couleursManuelles': True}
        couleurs = [{'reel': 's2', 'vecteur': vec}, {'reel': 'marque', 'vecteur': vec}, {'reel': 'marque', 'vecteur': retouche}, {'reel': 's2', 'vecteur': retouche}]
        tmp = Path(tempfile.mkdtemp(prefix='regles-', dir=self.bac))
        (tmp / 'cas.json').write_text(json.dumps({'filtres': filtres, 'reels': reels, 'ajouts': ajouts, 'couleurs': couleurs}, ensure_ascii=False), encoding='utf-8')
        r = subprocess.run(['node', str(HERE / 'regles-ts.mjs'), str(self.bac / 'assets' / banque.CATALOGUE), str(tmp / 'cas.json'), str(tmp / 'ts.json')],
                           capture_output=True, text=True, encoding='utf-8', timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        ts = json.loads((tmp / 'ts.json').read_text(encoding='utf-8'))
        for f, ids in zip(filtres, ts['filtres']):
            self.assertEqual(ids, [e['id'] for e in banque.filtrer(tous, f)], f'filtre {f} : interface = moteur')
        mots = {k: banque._mots_dits(v) for k, v in reels.items()}
        # sourceRectAt (Node, timeline.ts) memorise par reel et par instant : meme cadre que l'interface
        cadres = {k: functools.lru_cache(maxsize=None)(lambda t, v=v: banque._cadre(v, t)) for k, v in reels.items()}
        par_id = {e['id']: e for e in tous}
        champs = {}
        for a_, t_ in zip(ajouts, ts['ajouts']):
            e, rr = par_id[a_['id']], reels[a_['reel']]
            try:
                champ, el = banque.element_pour_reel(e, rr, a_['at'], mots[a_['reel']], cadres[a_['reel']])
            except ValueError as x:
                self.assertIn('erreur', t_, f'{a_} : le moteur refuse ({x}), l\'interface doit refuser aussi')
                continue
            self.assertNotIn('erreur', t_, f'{a_} : {t_.get("erreur")}')
            self.assertEqual(t_['champ'], champ, f'{a_}')
            self.assertEqual(sans_id(t_['element']), sans_id(el), f'{a_} : element identique (hors id)')
            vu, pourquoi = banque.visible(e, rr)
            self.assertEqual((t_['visible']['ok'], t_['visible']['pourquoi']), (vu, pourquoi), f'{a_} : visibilite')
            self.assertTrue(el.get('manual') or champ in ('flash', 'effects'), 'tout element pose est marque manual')
            champs.setdefault(a_['reel'], {}).setdefault(champ, 0)
            champs[a_['reel']][champ] += 1
        print('ajouts compares (interface = moteur) :', json.dumps(champs, ensure_ascii=False))
        self.assertGreater(champs['s1'].get('styleScenes', 0), 10, 'style avec habillage : les modeles deviennent des scenes du style')
        self.assertEqual(champs['s2'].get('styleScenes', 0), 0, 'sans habillage : graphismes seulement')
        self.assertGreater(champs['rallume'].get('graphics', 0), 5, 'graphismes rallumes dans le style : graphismes')
        # charte : recolore automatiquement un vecteur ; une couleur retouchee reste
        c = ts['couleurs']
        self.assertEqual(c[0]['principale'], s2['style']['highlight'])
        self.assertEqual(c[1]['principale'], '#FF3355', 'la charte recolore le vecteur pose par la banque')
        self.assertEqual(c[2]['principale'], '#00AAFF', 'retouche manuelle gardee malgre la charte')
        self.assertEqual(c[3]['principale'], '#00AAFF')
        print('couleurs :', c[:3])

    # ------------------------------------------------------------ 6. ajouter dans un reel, puis style + relecture automatique
    def test_6_ajouter_puis_passes_automatiques(self):
        tous = {e['id']: e for e in self.cat['entrees']}
        r = copy.deepcopy(REELS['script2'])
        mots = banque._mots_dits(r)
        kenney = next(i for i in tous if i.startswith('son:kenney:impact-sounds-impactMetal_heavy'))
        infos = [banque.ajouter(r, tous[i], at, mots) for i, at in
                 ((kenney, 15.5), ('son:editeur:whoosh-court', 20.0), ('vecteur:fleche', 15.2), ('vecteur:coche', 21.0),
                  ('template:liste-benefices', 16.6), ('template:mot-geant', 25.0), ('effet:etalonnage-cinema', 0), ('effet:flash-lumiere', 0))]
        ext = r['sfx']['extra'][-2:]
        self.assertEqual(ext[0]['name'], tous[kenney]['fichier'])
        self.assertEqual(ext[0]['gain'], tous[kenney]['params']['gain'])
        self.assertEqual(ext[1]['name'], 'whoosh-court', 'bruitage de l\'editeur : nom court (SFX_GAIN)')
        self.assertTrue(all(x['manual'] and x['reason'].startswith('Banque : ') for x in ext))
        v1, v2 = r['vectors']
        self.assertEqual(v1['couleurs'], {'principale': None, 'secondaire': None, 'contour': None})
        self.assertFalse(v1['couleursManuelles'])
        self.assertTrue(v2['couleursManuelles'] and v2['couleurs']['principale'], 'coche : couleurs d\'origine gardees')
        g1, g2 = r['graphics'][-2:]
        self.assertEqual((g1['kind'], g1['props']['banque'], g1['manual']), ('coches', 'template:liste-benefices', True))
        self.assertEqual(g2['kind'], 'motgeant')
        attendu = banque._mot_fort(mots, 25.0)
        self.assertEqual(g2['props']['text'], attendu or 'WOW', 'mot geant pre-rempli avec le mot dit a cet instant')
        # places hors du visage (meme cadrage que l'image : sourceRectAt)
        W, H = r['width'], r['height']
        for nom, el, cx, cy, taille in (
                ('fleche', v1, v1['x'], v1['y'], banque.taille_element(r, 'vectors', None, {'w': v1['w'], 'ratio': tous['vecteur:fleche']['params']['ratio']})),
                ('liste', g1, 0.5, None, banque.taille_element(r, 'graphics', 'coches', g1['props']))):
            face = banque.visage(r, banque._cadre(r, el['at']), el['duration'])
            if cy is None:
                cy = g1['props']['y'] + taille['h'] / 2
            hv = face['w'] * W / H
            chevauche = not (cx + taille['w'] / 2 < face['x'] - face['w'] / 2 or cx - taille['w'] / 2 > face['x'] + face['w'] / 2
                             or cy + taille['h'] / 2 < face['y'] - 0.6 * hv or cy - taille['h'] / 2 > face['y'] + 0.55 * hv)
            print(f'placement {nom} : centre ({cx:.3f}, {cy:.3f}), taille {taille["w"]:.2f} x {taille["h"]:.2f} ; visage ({face["x"]:.3f}, {face["y"]:.3f}),'
                  f' largeur {face["w"]:.3f} -> {"CHEVAUCHE" if chevauche else "hors du visage"}')
            self.assertFalse(chevauche, f'{nom} : pose sur le visage')
        self.assertEqual(r['effects']['grade'], 'cinema')
        self.assertEqual(r['flash'], {'enabled': True, 'kind': 'lumiere'})
        self.assertTrue(all(i['visible'] for i in infos), [i['message'] for i in infos])
        poses = copy.deepcopy({'extra': ext, 'vectors': r['vectors'], 'graphics': [g1, g2]})
        # changement de style (avec et sans habillage) + relecture de sobriete : rien de pose par la banque ne bouge
        for style in ('tech-application', 'reel-impact'):
            reelmod.apply_template(r, style)
            self.assertEqual([x for x in r['sfx']['extra'] if x.get('id') in {e['id'] for e in poses['extra']}], poses['extra'], style)
            self.assertEqual([v for v in r.get('vectors', []) if v['id'] in {v['id'] for v in poses['vectors']}], poses['vectors'], style)
            self.assertEqual([g for g in r['graphics'] if g['id'] in {g1['id'], g2['id']}], poses['graphics'], style)
        sobriete.relire(r, 'reel-impact', tout=True)
        self.assertEqual([g for g in r['graphics'] if g['id'] in {g1['id'], g2['id']}], poses['graphics'], 'relecture tout=True')
        self.assertTrue(all(verrous.protege(x) for x in [*poses['extra'], *poses['vectors'], *poses['graphics']]))
        # style avec habillage (script1, Tech) : modele -> scene du style, en tete de liste, ancree au mot dit
        s = copy.deepcopy(REELS['script1'])
        ms = banque._mots_dits(s)
        info = banque.ajouter(s, tous['template:notification'], 20.0, ms)
        sc = s['styleScenes'][0]
        self.assertEqual((info['champ'], sc['kind'], sc['manual']), ('styleScenes', 'notification', True))
        w = banque._mot_a(ms, 20.0)
        self.assertEqual((sc['clip'], sc['index']), (w['clip'], w['index']))
        self.assertEqual(sc['color'], banque.palette(s)['principale'])
        info = banque.ajouter(s, tous['template:logo-anime'], 30.0, ms)
        self.assertFalse(info['visible'], 'logo sans charte : le dire')
        info = banque.ajouter(s, tous['son:banque:riser-court'], 22.0, ms)
        self.assertFalse(info['visible'])
        self.assertIn('coupés', info['message'], 'bruitages coupes dans ce reel : le dire')
        fige = copy.deepcopy(sc)
        reelmod.apply_template(s, 'tech-application')
        self.assertIn(fige, s['styleScenes'], 'scene posee par la banque gardee au changement de style')


if __name__ == '__main__':
    unittest.main(verbosity=2)
