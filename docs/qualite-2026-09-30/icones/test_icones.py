"""Ronde 4 « icônes » : tests hors ligne de la banque d'icônes (engine/editeur/banque.py) et parité avec l'interface.
    python ..\\docs\\qualite-2026-09-30\\icones\\test_icones.py        (depuis engine/, environnement charge)
Bac : runtime/cache/tmp/icones-ronde4/bac-<hasard>/assets : JONCTION EN LECTURE vers assets/banque/icones (retiree a la fin
avec os.rmdir : le lien seulement) + un dossier import/ d'essai (SVG au nom accentue, PNG, SVG piege, SVG multicolore).
Reels : copies EN MEMOIRE des reels figes docs/direction-creative-v2/tests/fixtures/projects/script1 et script2.
Ne touche ni au vrai catalogue, ni aux projets, ni au serveur."""
import copy
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIX = ROOT / 'docs/direction-creative-v2/tests/fixtures'
sys.path.insert(0, str(ROOT / 'engine'))
os.environ['EDITEUR_LLM'] = '0'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
from editeur import banque  # noqa: E402

BAC_PARENT = ROOT / 'runtime/cache/tmp/icones-ronde4'
REELS = {k: json.loads((FIX / f'projects/{k}/reels/script.json').read_text(encoding='utf-8')) for k in ('script1', 'script2')}
REGLES_TS = ROOT / 'docs/direction-creative-v2/tests/banque/regles-ts.mjs'


def jonction(lien, cible):
    import _winapi
    _winapi.CreateJunction(str(cible), str(lien))


def png(w, h, rgba=(30, 160, 90, 255)):
    """PNG minimal (une couleur) ecrit a la main."""
    raw = b''.join(b'\x00' + bytes(rgba) * w for _ in range(h))
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


class Icones(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        BAC_PARENT.mkdir(parents=True, exist_ok=True)
        cls.bac = Path(tempfile.mkdtemp(prefix='bac-', dir=BAC_PARENT))
        a = cls.bac / 'assets'
        (a / 'banque').mkdir(parents=True)
        cls.lien = a / 'banque/icones'
        jonction(cls.lien, ROOT / 'assets/banque/icones')
        imp = a / 'banque/import'
        (imp / 'Finance').mkdir(parents=True)
        (imp / 'Sac d’argent é.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                                               'stroke-width="2"><circle cx="12" cy="13" r="8"/><path d="M9 5h6"/></svg>', encoding='utf-8')
        (imp / 'Finance/coin.png').write_bytes(png(64, 48))
        (imp / 'Finance/LICENSE.txt').write_text('Pack Finance — licence commerciale (essai)\n', encoding='utf-8')
        (imp / 'piege.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><script>alert(1)</script></svg>', encoding='utf-8')
        # multicolore (deux couleurs ecrites en dur) : couleurs du fichier gardees ; une seule couleur ecrite en dur serait
        # recolorable (icone monochrome d'un pack, voir monoToCurrent de vectors.tsx)
        (imp / 'multi.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10" fill="#ff0000"/>'
                                       '<circle cx="5" cy="5" r="2" fill="#0000ff"/></svg>', encoding='utf-8')
        shutil.copy2(ROOT / 'assets/banque/import/LISEZMOI.txt', imp / 'LISEZMOI.txt')
        print(f'BAC={cls.bac}')
        cls.rapport = banque.construire_icones(cls.bac)
        print('construire_icones :', json.dumps(cls.rapport, ensure_ascii=False))
        cls.cat = json.loads((a / banque.CATALOGUE_ICONES).read_text(encoding='utf-8'))
        cls.par_id = {e['id']: e for e in cls.cat['entrees']}

    @classmethod
    def tearDownClass(cls):
        try:
            os.rmdir(cls.lien)  # le lien seulement, jamais sa cible
        except OSError:
            pass

    # ------------------------------------------------------------ 1. catalogue
    def test_1_catalogue(self):
        a = self.bac / 'assets'
        e = self.cat['entrees']
        lucide = [x for x in e if x['source'] == 'lucide']
        svgs = len(list((ROOT / 'assets/banque/icones/lucide').glob('*.svg')))
        dico = json.loads((ROOT / 'assets/banque/icones/dictionnaire-lucide-fr.json').read_text(encoding='utf-8'))
        print(f'icones : {len(e)} (Lucide {len(lucide)} sur {svgs} SVG, dont {len(dico["icones"])} choisies a la main ; importees '
              f'{self.rapport["importees"]}) ; ecartees : {[(x["fichier"], x["raison"]) for x in self.cat["ecartes"]]}')
        self.assertEqual(len(lucide), svgs, 'chaque icone Lucide est indexee')
        self.assertGreaterEqual(svgs, 1800)
        self.assertEqual(self.cat['compte'], {'icone': len(e)})
        ids = [x['id'] for x in e]
        self.assertEqual(len(ids), len(set(ids)))
        cats = {}
        for x in e:
            self.assertEqual(x['type'], 'icone')
            self.assertRegex(x['id'], r'^[A-Za-z0-9_.:-]{1,120}$')
            for k in ('nom', 'categorie', 'licence', 'provenance', 'apercu', 'fichier'):
                self.assertTrue(str(x.get(k) or '').strip(), f'{x["id"]} : {k}')
            self.assertTrue((a / x['fichier']).is_file(), x['fichier'])
            self.assertRegex(x['fichier'], r'^[A-Za-z0-9][A-Za-z0-9/_.-]*\.(svg|png)$', 'chemin accepte par le serveur (vecteurs)')
            self.assertTrue(x['motsCles'] and set(x['formats']) == set(banque.FORMATS))
            cats[x['categorie']] = cats.get(x['categorie'], 0) + 1
        print('categories :', json.dumps(cats, ensure_ascii=False))
        for c in ('finance', 'vente', 'marketing', 'communication', 'téléphone', 'temps', 'sécurité', 'croissance', 'personnes', 'accord',
                  'immobilier', 'santé', 'éducation'):
            self.assertGreaterEqual(cats.get(c, 0), 8, f'categorie « {c} » bien garnie')
        self.assertLess(cats.get('divers', 0), len(lucide) * 0.12, 'moins de 12 % d’icones sans categorie')
        hs = self.par_id['icone:lucide:handshake']
        self.assertEqual((hs['nom'], hs['categorie']), ('Poignée de main', 'accord'))
        self.assertIn('ISC', hs['licence'])
        self.assertIn('LICENSE', hs['licence'])
        self.assertIn('1.49.0', hs['provenance'])
        self.assertTrue(hs['params']['trait'] and hs['params']['style'] == 'verre' and hs['params']['ratio'] == 1)
        self.assertIn('Feather', self.par_id['icone:lucide:calendar']['licence'], 'dessin derive de Feather : MIT signale')
        self.assertNotIn('Feather', hs['licence'])
        # nom de repli traduit mot a mot
        self.assertEqual(self.par_id['icone:lucide:arrow-up-right']['nom'], 'Flèche montante')
        self.assertTrue(self.par_id['icone:lucide:align-center-vertical']['nom'].startswith('Aligner'))
        # reconstruction a l'identique : aucune ecriture
        f = a / banque.CATALOGUE_ICONES
        avant = f.stat().st_mtime_ns
        data = banque._charger_icones(self.bac)
        self.assertEqual(f.stat().st_mtime_ns, avant, 'signature inchangee : pas de reconstruction')
        self.assertEqual(len(data['entrees']), len(e))

    # ------------------------------------------------------------ 2. import
    def test_2_import(self):
        a = self.bac / 'assets'
        imp = [x for x in self.cat['entrees'] if x['source'] == 'import']
        print('importees :', [(x['nom'], x['categorie'], x['fichier'], x['licence']) for x in imp])
        self.assertEqual(len(imp), 3, 'SVG accentue, PNG, SVG multicolore (le piege est refuse)')
        refus = {x['fichier']: x['raison'] for x in self.cat['ecartes']}
        self.assertIn('script', refus['banque/import/piege.svg'])
        for x in imp:
            self.assertTrue(x['licence'].startswith('À vérifier (importé)'))
        sac = next(x for x in imp if x['nom'].startswith('Sac'))
        self.assertTrue(sac['fichier'].startswith('banque/apercus/import/') and (a / sac['fichier']).is_file(), 'copie au nom simple')
        self.assertTrue((a / 'banque/import/Sac d’argent é.svg').is_file(), 'original intact')
        self.assertTrue(sac['params']['recolorable'] and sac['params']['trait'])
        coin = next(x for x in imp if x['fichier'].endswith('coin.png'))
        self.assertEqual((coin['categorie'], coin['params']['png'], coin['params']['ratioDessin']), ('finance', True, 0.75))
        self.assertIn('Finance/LICENSE.txt', coin['licence'], 'licence du pack trouvee dans son dossier')
        multi = next(x for x in imp if x['nom'] == 'Multi')
        self.assertFalse(multi['params']['recolorable'], 'couleurs ecrites en dur : gardees')
        self.assertNotIn('LISEZMOI', multi['licence'], 'le mode d’emploi n’est pas une licence')
        # un fichier ajoute : re-indexe tout seul a la lecture suivante
        (a / 'banque/import/nouvelle.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor">'
                                                      '<path d="M4 12h16"/></svg>', encoding='utf-8')
        c = banque.catalogue({'type': 'icone', 'q': 'nouvelle'}, racine=self.bac)
        self.assertEqual(c['entrees'][0]['id'], 'icone:import:nouvelle', 'icone importee : en tete de sa recherche')
        self.__class__.cat = json.loads((a / banque.CATALOGUE_ICONES).read_text(encoding='utf-8'))
        self.__class__.par_id = {e['id']: e for e in self.cat['entrees']}

    # ------------------------------------------------------------ 3. recherche FR / EN
    def test_3_recherche(self):
        tous = self.cat['entrees']
        f = banque.filtrer
        def ids(q, n=8):
            return [x['id'].split(':')[-1] for x in f(tous, {'type': 'icone', 'q': q})[:n]]
        res = {q: ids(q) for q in ('poignée de main', 'poignee de main', 'argent', 'téléphone', 'telephone', 'handshake', 'money', 'maison',
                                   'rendez-vous', 'sécurité', 'croissance')}
        for q, r in res.items():
            print(f'« {q} » -> {r}')
        self.assertEqual(res['poignée de main'][:2], ['handshake', 'heart-handshake'])
        self.assertEqual(res['poignée de main'], res['poignee de main'], 'insensible aux accents')
        self.assertTrue({'banknote', 'coins', 'hand-coins', 'piggy-bank'} <= set(ids('argent', 12)), 'argent : billets, pieces, tirelire')
        self.assertEqual(res['téléphone'][0], 'phone')
        self.assertTrue({'phone', 'phone-call', 'smartphone'} <= set(ids('téléphone', 12)))
        self.assertEqual(res['téléphone'], res['telephone'])
        self.assertEqual(res['handshake'][0], 'handshake', 'recherche en anglais')
        self.assertTrue(res['money'], 'mots-cles anglais de Lucide')
        self.assertEqual(res['maison'][0], 'house')
        self.assertTrue(f(tous, {'type': 'icone', 'categorie': 'finance'}) and all(x['categorie'] == 'finance' for x in f(tous, {'categorie': 'finance'})))
        # catalogue historique inchange : 4 types, icones seulement sur demande
        self.assertEqual(banque.TYPES, ('effet', 'son', 'vecteur', 'template'))
        with self.assertRaises(ValueError):
            f(tous, {'type': 'musique'})

    # ------------------------------------------------------------ 4. « Ajouter » : vecteur + meta.icone, meme regle que l'interface
    def test_4_ajouter_et_parite(self):
        r = copy.deepcopy(REELS['script2'])
        e = self.par_id['icone:lucide:handshake']
        champ, el = banque.element_pour_reel(e, r, 15.37)
        self.assertEqual(champ, 'vectors')
        self.assertEqual(el['meta'], {'icone': {'style': 'verre', 'nom': 'Poignée de main', 'banque': 'icone:lucide:handshake'}})
        self.assertEqual((el['asset'], el['w'], el['duration'], el['couleurs'], el['couleursManuelles'], el['manual']),
                         ('banque/icones/lucide/handshake.svg', 0.22, 2.5, {'principale': None, 'secondaire': None, 'contour': None}, False, True))
        for st in banque.STYLES_ICONE:
            self.assertEqual(banque.element_pour_reel(e, r, 15.37, style=st)[1]['meta']['icone']['style'], st)
        self.assertEqual(banque.element_pour_reel(e, r, 1, style='inconnu')[1]['meta']['icone']['style'], 'verre')
        coin = next(x['id'] for x in self.cat['entrees'] if x['fichier'].endswith('coin.png'))
        self.assertEqual(coin, 'icone:import:Finance-coin')
        info = banque.ajouter(r, self.par_id[coin], 20.0, style='plein')
        self.assertTrue(info['visible'] and r['vectors'][-1]['asset'].endswith('coin.png'))
        # cles et bornes du serveur (validateV2 : VECTOR_KEYS, meta <= 2 Ko, chemin de ressource)
        cles = {'id', 'asset', 'at', 'duration', 'x', 'y', 'w', 'rotation', 'opacite', 'couleurs', 'couleursManuelles', 'anim', 'auto', 'locked',
                'manual', 'raison', 'suggested', 'sobriete', 'meta'}
        self.assertTrue(set(el) <= cles and len(json.dumps(el['meta'])) < 2048 and -1 <= el['x'] <= 2 and -1 <= el['y'] <= 2)
        # parite avec app/ui/banque.tsx (regles-ts.mjs : filtres + « Ajouter »)
        reels = {'s1': copy.deepcopy(REELS['script1']), 's2': copy.deepcopy(REELS['script2'])}
        filtres = [{'type': 'icone'}, {'type': 'icone', 'q': 'poignée de main'}, {'q': 'argent'}, {'q': 'TÉLÉPHONE'}, {'categorie': 'finance'},
                   {'type': 'icone', 'q': 'money'}, {'q': 'importé'}, {'format': '16:9', 'q': 'maison'}]
        choix = ['icone:lucide:handshake', 'icone:lucide:phone', 'icone:lucide:piggy-bank', coin,
                 next(x['id'] for x in self.cat['entrees'] if x['source'] == 'import' and x['fichier'].startswith('banque/apercus/'))]
        ajouts = [{'reel': k, 'id': i, 'at': at} for k in reels for i in choix for at in (3.2, 15.37)]
        tmp = Path(tempfile.mkdtemp(prefix='regles-', dir=self.bac))
        (tmp / 'cas.json').write_text(json.dumps({'filtres': filtres, 'reels': reels, 'ajouts': ajouts, 'couleurs': []}, ensure_ascii=False), encoding='utf-8')
        p = subprocess.run(['node', str(REGLES_TS), str(self.bac / 'assets' / banque.CATALOGUE_ICONES), str(tmp / 'cas.json'), str(tmp / 'ts.json')],
                           capture_output=True, text=True, encoding='utf-8', timeout=300)
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        ts = json.loads((tmp / 'ts.json').read_text(encoding='utf-8'))
        for fl, got in zip(filtres, ts['filtres']):
            self.assertEqual(got, [x['id'] for x in banque.filtrer(self.cat['entrees'], fl)], f'filtre {fl} : interface = moteur')
        mots = {k: banque._mots_dits(v) for k, v in reels.items()}
        cadres = {k: (lambda t, v=v: banque._cadre(v, t)) for k, v in reels.items()}
        n = 0
        for a_, t_ in zip(ajouts, ts['ajouts']):
            champ, el = banque.element_pour_reel(self.par_id[a_['id']], reels[a_['reel']], a_['at'], mots[a_['reel']], cadres[a_['reel']])
            self.assertNotIn('erreur', t_, t_.get('erreur'))
            self.assertEqual(t_['champ'], champ)
            self.assertEqual({k: v for k, v in t_['element'].items() if k != 'id'}, {k: v for k, v in el.items() if k != 'id'}, f'{a_}')
            n += 1
        print(f'parite interface = moteur : {len(filtres)} filtres, {n} ajouts identiques (hors id)')

    # ------------------------------------------------------------ 5. gros pack achete (relecture ronde 4)
    def test_5_gros_pack(self):
        """1 500 icones dans un dossier profond : indexees vite (licence cherchee une fois par dossier), chemins acceptes par le
        serveur (160 caracteres au plus, sinon copie au nom simple), identifiants uniques (meme nom en SVG et en PNG, debut de
        chemin commun tronque), noms anglais trouves en francais, une couleur ecrite en dur = recolorable."""
        import time
        bac = Path(tempfile.mkdtemp(prefix='pack-', dir=BAC_PARENT))
        imp = bac / 'assets/banque/import'
        profond = imp / 'Pack-Finance-Glassmorphism-Icons-Premium-Collection-2025/SVG/Outline/24px-stroke-2'
        profond.mkdir(parents=True)
        mono = ('<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
                '<path d="M4 12h16" stroke="#1E1E1E" stroke-width="2"/></svg>')
        for i in range(1500):
            (profond / f'finance-icon-money-bag-dollar-currency-savings-outline-24px-{i:04d}.svg').write_text(mono, encoding='utf-8')
        (imp / 'Pack-Finance-Glassmorphism-Icons-Premium-Collection-2025/License.txt').write_text('licence du pack', encoding='utf-8')
        (bac / 'assets/banque/icones').mkdir(parents=True)  # dictionnaire seulement (mots anglais -> francais), sans Lucide
        shutil.copy2(ROOT / 'assets' / banque.DICO_ICONES, bac / 'assets' / banque.DICO_ICONES)
        (imp / 'Doubles').mkdir()
        (imp / 'Doubles/coin.svg').write_text(mono, encoding='utf-8')
        (imp / 'Doubles/coin.png').write_bytes(png(16, 16))
        t0 = time.time()
        r = banque.construire_icones(bac)
        duree = time.time() - t0
        cat = json.loads((bac / 'assets' / banque.CATALOGUE_ICONES).read_text(encoding='utf-8'))
        e = cat['entrees']
        print(f'gros pack : {r} en {duree:.1f} s ; ecartes {cat["ecartes"][:3]}')
        self.assertEqual((len(e), cat['ecartes']), (1502, []), 'tout est indexe, rien d’ecarte (ni identifiant en double)')
        self.assertEqual(len({x['id'] for x in e}), 1502)
        self.assertLess(duree, 30, 'gros pack indexe en quelques secondes (avant : plus de 3 minutes)')
        for x in e:
            self.assertLessEqual(len(x['fichier']), 160, 'chemin accepte par le serveur (vecteur du reel)')
            self.assertRegex(x['fichier'], r'^[A-Za-z0-9][A-Za-z0-9/_.-]*\.(svg|png)$')
            self.assertTrue((bac / 'assets' / x['fichier']).is_file())
            self.assertLessEqual(len(x['id']), 120)
        sac = next(x for x in e if x['fichier'].endswith('.svg') and 'Pack' in x['provenance'])
        self.assertIn('License.txt', sac['licence'], 'licence du pack trouvee dans un dossier parent')
        self.assertTrue(sac['params']['recolorable'], 'une seule couleur ecrite en dur : suit la charte')
        self.assertTrue(banque.filtrer(e, {'type': 'icone', 'q': 'argent'}), 'nom anglais « money » trouve en francais')
        self.assertEqual(sorted(x['fichier'] for x in e if 'Doubles' in x['fichier']), ['banque/import/Doubles/coin.png', 'banque/import/Doubles/coin.svg'],
                         'meme nom en SVG et en PNG : les deux gardes')


if __name__ == '__main__':
    r = unittest.main(exit=False, verbosity=2).result
    ok = r.wasSuccessful()
    print('ICONES: OK' if ok else 'ICONES: ECHEC')
    sys.exit(0 if ok else 1)
