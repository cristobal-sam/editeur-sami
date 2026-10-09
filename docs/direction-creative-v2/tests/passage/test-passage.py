"""Tests de « Refaire seulement ce passage » (engine/editeur/passage.py), hors ligne (sans IA), sur des COPIES.
    python ../docs/direction-creative-v2/tests/passage/test-passage.py      (depuis engine/, environnement charge)
Bac : runtime/cache/tmp/dcv2-passage/tests-<hasard>/ (copies des donnees figees fixtures/projects/script1 et script2 : project.json et
reels/script.json seulement ; styles et remotion/src copies pour l'essai en ligne de commande). Jamais projects/.
Les pages de sous-titres de reference viennent de remotion/src/timeline.ts (pages.mjs), pas du module teste."""
import copy
import hashlib
import json
import math
import os
import shutil
import subprocess
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
from editeur import llm, montage, passage, sobriete, verrous  # noqa: E402
from editeur.reel import STOP, _core, idea_groups  # noqa: E402

llm.available = lambda: False  # aucune IA locale pendant ces essais

(ROOT / 'runtime/cache/tmp/dcv2-passage').mkdir(parents=True, exist_ok=True)
BOX = Path(tempfile.mkdtemp(prefix='tests-', dir=ROOT / 'runtime/cache/tmp/dcv2-passage'))
LISTES = ('graphics', 'broll', 'vectors', 'styleScenes')
GERES = set(LISTES) | {'clips', 'hlAuto', 'suggestions', 'sobriete', 'creativePlan', 'sfx', 'choreography'}
N = [0]


def sha(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()


def installer(nom, modif=None):
    """Copie fraiche du projet reel `nom` dans le bac (un dossier par essai) ; modif(reel) facultatif."""
    N[0] += 1
    d = BOX / f'{nom}-{N[0]}'
    (d / 'reels').mkdir(parents=True)
    shutil.copy2(FIX / 'projects' / nom / 'project.json', d / 'project.json')
    shutil.copy2(FIX / 'projects' / nom / 'reels' / 'script.json', d / 'reels' / 'script.json')
    if modif:
        r = montage.load(d, 'script')
        modif(r)
        (d / 'reels' / 'script.json').write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
    return d


def pages_ts(reel):
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, dir=BOX, encoding='utf-8') as f:
        json.dump(reel, f, ensure_ascii=False)
    try:
        out = subprocess.run(['node', str(HERE / 'pages.mjs'), f.name], capture_output=True, text=True, encoding='utf-8',
                             check=True).stdout
    finally:
        Path(f.name).unlink(missing_ok=True)
    return json.loads(out)


def temps(reel):
    seg = montage.compute(reel)
    return seg, {(w['clip'], w['index']): w['start'] for w in seg['words']}


def iv(nom, e, t):
    if not isinstance(e, dict):
        return None
    if nom == 'styleScenes':
        s = t.get((e.get('clip'), e.get('index')))
        return None if s is None else (s, s + float(e.get('duration') or 2.4))
    if nom == 'cues':
        return float(e['at']), float(e['at']) + float(e.get('duree') or 0)
    if nom == 'sfx':
        return float(e['t']), float(e['t'])
    return None if e.get('at') is None else (float(e['at']), float(e['at']) + float(e.get('duration') or 0))


def entier(i, a, b):
    return i is not None and i[0] >= a - 1e-3 and i[1] <= b + 1e-3


def automatique(nom, e):
    if nom == 'graphics':
        return bool(e.get('auto') or e.get('suggested') or e.get('generated'))
    if nom in ('broll', 'vectors'):
        return bool(e.get('auto'))
    return True  # scenes du style : automatiques sauf retouche / verrou


def mots_de_plage(reel, a, b):
    """(plan, indice) des mots dont TOUTE la page de sous-titres (timeline.ts) est dans la plage."""
    return {(c, i) for p in pages_ts(reel) if p['start'] >= a - 1e-3 and p['end'] <= b + 1e-3 for c, i in p['words']}


class Passage(unittest.TestCase):
    # ---------- controle commun : rien hors de la plage, rien de protege ----------
    def hors_plage_identique(self, avant, apres, a, b):
        seg, t = temps(avant)
        for k in set(avant) | set(apres):
            if k not in GERES:
                self.assertEqual(avant.get(k), apres.get(k), f'champ « {k} » change')
        listes = [(nom, avant.get(nom) or [], apres.get(nom) or []) for nom in LISTES]
        listes.append(('cues', (avant.get('choreography') or {}).get('cues') or [], (apres.get('choreography') or {}).get('cues') or []))
        listes.append(('sfx', (avant.get('sfx') or {}).get('extra') or [], (apres.get('sfx') or {}).get('extra') or []))
        listes.append(('broll', (avant.get('suggestions') or {}).get('broll') or [], (apres.get('suggestions') or {}).get('broll') or []))
        n_fixes = 0
        for nom, A, B in listes:
            fa = [e for e in A if verrous.protege(e) or not entier(iv(nom, e, t), a, b)]
            fb = [e for e in B if verrous.protege(e) or not entier(iv(nom, e, t), a, b)]
            self.assertEqual(fa, fb, f'{nom} : un element hors de la plage (ou protege) a change')
            n_fixes += len(fa)
        for k in ('sfx', 'choreography', 'suggestions'):
            ra = {x: v for x, v in (avant.get(k) or {}).items() if x not in ('extra', 'cues', 'broll')}
            rb = {x: v for x, v in (apres.get(k) or {}).items() if x not in ('extra', 'cues', 'broll')}
            self.assertEqual(ra, rb, f'{k} : reglage change')
        # plan creatif : seul l'audit des plans du storyboard qui touchent la plage peut changer
        pa, pb = copy.deepcopy(avant.get('creativePlan')), copy.deepcopy(apres.get('creativePlan'))
        if pa and pb:
            for sa, sb in zip(pa.get('storyboard') or [], pb.get('storyboard') or []):
                if sa['end'] > a and sa['start'] < b and not pa.get('locked'):
                    for k in ('status', 'execution'):
                        sa.pop(k, None)
                        sb.pop(k, None)
        self.assertEqual(pa, pb, 'plan creatif change hors de l\'audit de la plage')
        # mots : seule la couleur des mots des pages ENTIEREMENT dans la plage peut changer
        dedans = mots_de_plage(avant, a, b)
        self.assertEqual(len(avant['clips']), len(apres['clips']))
        for ca, cb in zip(avant['clips'], apres['clips']):
            self.assertEqual({k: v for k, v in ca.items() if k != 'words'}, {k: v for k, v in cb.items() if k != 'words'},
                             f'plan {ca["id"]} change (prise, coupes, emojis...)')
            for i, (wa, wb) in enumerate(zip(ca['words'], cb['words'])):
                if (ca['id'], i) in dedans and not ca.get('locked'):
                    self.assertEqual({k: v for k, v in wa.items() if k != 'hl'}, {k: v for k, v in wb.items() if k != 'hl'})
                else:
                    self.assertEqual(wa, wb, f'mot {ca["id"]}/{i} « {wa.get("w")} » hors plage change')
        # historique des mots en couleur : inchange pour tout mot hors plage
        ha, hb = avant.get('hlAuto') or {}, apres.get('hlAuto') or {}
        self.assertEqual(set(ha), set(hb))
        for cid, rec in ha.items():
            e = {i for c, i in dedans if c == cid}
            for key in ('on', 'off'):
                self.assertEqual(set(rec.get(key) or []) - e, set(hb[cid].get(key) or []) - e, f'hlAuto {cid}.{key} hors plage')
            self.assertEqual({k: v for k, v in rec.items() if k not in ('on', 'off')},
                             {k: v for k, v in hb[cid].items() if k not in ('on', 'off')})
        return n_fixes, dedans

    def seuls_automatiques(self, avant, apres, a, b):
        """Dans la plage, ce qui a change est automatique et libre ; le reste est intact."""
        _, t = temps(avant)
        for nom in LISTES:
            for e in avant.get(nom) or []:
                if entier(iv(nom, e, t), a, b) and (verrous.protege(e) or not automatique(nom, e)):
                    self.assertIn(e, apres.get(nom) or [], f'{nom} {e.get("id")} (protege ou pose a la main) a change')
            for e in apres.get(nom) or []:
                if e not in (avant.get(nom) or []):
                    self.assertFalse(verrous.protege(e), f'{nom} {e.get("id")} : element protege cree ou change')
                    self.assertTrue(entier(iv(nom, e, t), a, b), f'{nom} {e.get("id")} : nouveau hors de la plage')

    # ---------- essais ----------
    def test_1_milieu_10s(self):
        """Plage de 10 s au milieu : hors plage identique ; dans la plage, seuls les automatiques changent ; verrous et
        retouches intacts ; « Annuler » (la version gardee) remet le fichier a l'octet pres."""
        a, b = 30.0, 40.0
        prep = {}

        def modif(r):
            _, t = temps(r)
            dedans = sorted(mots_de_plage(r, a, b), key=lambda k: t[k])
            hla = r['hlAuto']
            by = {c['id']: c for c in r['clips']}
            idee = lambda c, i: next(x for x in idea_groups(by[c]['words']) if i in x)
            couleurs = lambda c, i: sum(1 for k in idee(c, i) if by[c]['words'][k].get('hl'))
            petits = [(c, i) for c, i in dedans if _core(by[c]['words'][i]['w']) in STOP and not by[c]['words'][i].get('hl')
                      and hla.get(c) and set(idee(c, i)) <= {i2 for c2, i2 in dedans if c2 == c}]
            # un mot outil colore « par l'automatique » (perime) : la passe doit le recalculer (il perd sa couleur)
            c, i = min(petits, key=lambda k: couleurs(*k))
            by[c]['words'][i]['hl'] = True
            hla[c]['on'] = sorted(set(hla[c]['on']) | {i})
            prep['perime'] = (c, i)
            # un autre mot de la meme idee colore A LA MAIN (absent de hlAuto.on) : garde (il prend le budget de l'idee)
            c, i = next((c, k) for k in idee(c, i) if (c, k) in dedans and not by[c]['words'][k].get('hl'))
            by[c]['words'][i]['hl'] = True
            prep['main'] = (c, i)
            # un mot colore par l'automatique puis DECOLORE a la main : reste sans couleur
            auto_on = [(c, i) for c, i in dedans if by[c]['words'][i].get('hl') and i in hla.get(c, {}).get('on', [])
                       and i not in idee(*prep['perime'])]
            c, i = auto_on[0]
            by[c]['words'][i]['hl'] = False
            prep['decolore'] = (c, i)
            # scene automatique perimee dans la plage
            sc = next(s for s in r['styleScenes'] if entier(iv('styleScenes', s, t), a, b))
            sc['text'] = 'ANCIEN TEXTE'
            prep['scene'] = sc['id']
            c3 = next(c for c, i in dedans)
            i3 = next(i for c, i in dedans if c == c3)
            r['graphics'].append({'id': 'g-verrou', 'kind': 'motgeant', 'at': 32.0, 'duration': 1.0, 'props': {'text': 'VERROU'},
                                  'auto': True, 'locked': True})
            r['graphics'].append({'id': 'g-main', 'kind': 'chiffre', 'at': 33.5, 'duration': 1.2, 'props': {'value': 5},
                                  'manual': True})
            r['styleScenes'].append({'id': 'scene-main', 'kind': 'keyword', 'clip': c3, 'index': i3, 'length': 1, 'text': 'MAIN',
                                     'secondary': '', 'duration': 1.5, 'x': .5, 'y': .7, 'scale': 1, 'rotation': 0,
                                     'color': '#FF00FF', 'manual': True})
            vec = lambda vid, at, d, **k: {'id': vid, 'asset': 'banque/vecteurs/cercle.svg', 'at': at, 'duration': d, 'x': .5,
                                           'y': .3, 'w': .3, 'rotation': 0, 'opacite': 1,
                                           'couleurs': {'principale': None, 'secondaire': None, 'contour': None},
                                           'couleursManuelles': False, 'anim': {'entree': 'pop', 'sortie': 'fondu'}, **k}
            r['vectors'] = [vec('v-libre', 36.0, 1.5, auto=True), vec('v-verrou', 36.2, 1.5, auto=True, locked=True),
                            vec('v-cheval', 39.0, 2.0, auto=True), vec('v-dehors', 50.0, 2.0, auto=True),
                            vec('v-dehors2', 50.5, 2.0, auto=True)]
            move = {'type': 'fondu', 'duree': .3, 'courbe': 'douce'}
            cue = lambda cid, typ, tid, at, d, **k: {'id': cid, 'cible': {'type': typ, 'id': tid}, 'at': at, 'duree': d,
                                                     'entree': move, 'sortie': move, 'sync': {'sur': 'temps', 'ref': None},
                                                     'raison': 'essai', 'auto': True, 'locked': False, **k}
            r['choreography'] = {'version': 1, 'cues': [cue('q-verrou', 'graphics', 'g-verrou', 32.0, 1.0, locked=True),
                                                        cue('q-orphelin', 'graphics', 'g-disparu', 33.0, 1.0),
                                                        cue('q-dehors', 'graphics', 'g-disparu2', 50.0, 1.0),
                                                        cue('q-cheval', 'vector', 'v-cheval', 39.0, 2.0)]}
            anchor = {'clip': r['clips'][0]['id'], 'src': r['clips'][0]['in'] + 4, 'sig': r['clips'][0]['signature']}
            r['notes'] = [{'id': 'n1', 't': 34.0, 'anchor': anchor, 'text': 'Refaire ce passage', 'statut': 'ouverte',
                           'auteur': 'Sami', 'cree': '2026-09-30T20:00:00', 'modifie': '2026-09-30T20:00:00',
                           'contexte': {'titre': 'Vidéo 1', 'style': r['template'], 'format': '9:16', 'duree': 70}}]
            r['annotations'] = [{'id': 'a1', 'noteId': 'n1', 'outil': 'fleche', 'couleur': '#FF0000', 'epaisseur': 6,
                                 'points': [[.4, .4], [.5, .5]], 'anchor': anchor, 'duree': 2}]

        d = installer('script1', modif)
        f = d / 'reels' / 'script.json'
        brut, h0 = f.read_bytes(), sha(f)
        avant = json.loads(brut)
        out = passage.refaire(d, 'script', a, b)
        apres = montage.load(d, 'script')
        print(f"\n  [milieu 30-40 s] {out['resume']}")
        for ch in out['changes']:
            print(f'     - {ch}')
        self.assertTrue(out['modifie'])
        n_fixes, dedans = self.hors_plage_identique(avant, apres, a, b)
        self.seuls_automatiques(avant, apres, a, b)
        print(f'     ok : {n_fixes} elements hors plage/proteges identiques, {len(dedans)} mots de la plage relus')
        mot = lambda r, k: next(c for c in r['clips'] if c['id'] == k[0])['words'][k[1]]
        self.assertFalse(mot(apres, prep['perime']).get('hl'), 'mot outil colore par l\'automatique : recalcule')
        self.assertTrue(mot(apres, prep['main']).get('hl'), 'mot colore a la main : garde')
        self.assertFalse(mot(apres, prep['decolore']).get('hl'), 'mot decolore a la main : reste sans couleur')
        c, i = prep['decolore']
        self.assertIn(i, apres['hlAuto'][c]['off'], 'le decolorage a la main est note (off)')
        self.assertNotIn(prep['perime'][1], apres['hlAuto'][prep['perime'][0]]['on'])
        sc = next((s for s in apres['styleScenes'] if s['id'] == prep['scene']), None)
        self.assertTrue(sc is None or sc['text'] != 'ANCIEN TEXTE', 'scene automatique de la plage refaite')
        g = {x['id']: x for x in apres['graphics']}
        self.assertEqual(g['g-verrou'], next(x for x in avant['graphics'] if x['id'] == 'g-verrou'))
        self.assertEqual(g['g-main'], next(x for x in avant['graphics'] if x['id'] == 'g-main'))
        self.assertIn(next(s for s in avant['styleScenes'] if s['id'] == 'scene-main'), apres['styleScenes'])
        v = {x['id']: x for x in apres['vectors']}
        self.assertEqual(v['v-verrou'], avant['vectors'][1], 'vecteur verrouille intact')
        self.assertTrue(v['v-libre'].get('suggested'), 'vecteur automatique en conflit : retire par la sobriete')
        self.assertEqual(v['v-cheval'], avant['vectors'][2], 'vecteur a cheval sur la fin : intact')
        self.assertEqual([v['v-dehors'], v['v-dehors2']], avant['vectors'][3:], 'vecteurs hors plage : pas relus')
        cues = {q['id']: q for q in apres['choreography']['cues']}
        self.assertNotIn('q-orphelin', cues, 'mouvement orphelin de la plage retire')
        for q in ('q-verrou', 'q-dehors', 'q-cheval'):
            self.assertEqual(cues[q], next(x for x in avant['choreography']['cues'] if x['id'] == q), f'{q} garde tel quel')
        _, t = temps(apres)
        vivants = {'graphics': {x['id'] for x in apres['graphics'] if not x.get('suggested')},
                   'vector': {x['id'] for x in apres['vectors'] if not x.get('suggested')},
                   'design': {x['id'] for x in apres['styleScenes'] if not x.get('hidden')},
                   'broll': {x['id'] for x in apres.get('broll') or []}}
        for q in cues.values():
            if q['id'] not in ('q-verrou', 'q-dehors', 'q-cheval'):  # mouvements crees par la choregraphie dans la plage
                self.assertTrue(entier(iv('cues', q, t), a, b) and not verrous.protege(q), q['id'])
                if q['cible']['type'] in vivants:
                    self.assertIn(q['cible']['id'], vivants[q['cible']['type']], f"{q['id']} vise un element absent")
        self.assertEqual(apres['notes'], avant['notes'])
        self.assertEqual(apres['annotations'], avant['annotations'])
        self.assertEqual(out['proteges'], 5, 'g-verrou, g-main, scene-main, v-verrou, q-verrou')
        self.assertGreaterEqual(out['aCheval'], 1)
        self.assertIn('Rien n\'a bougé avant ni après', out['resume'])
        # « Annuler » : la version gardee remet le fichier exact
        vf = d / 'versions' / 'script' / out['version']
        self.assertTrue(vf.exists())
        self.assertEqual(vf.read_bytes(), brut)
        shutil.copyfile(vf, f)  # ce que fait POST /restore
        self.assertEqual(sha(f), h0)
        print(f"     ok : « Annuler » (version « {out['version']} ») remet le fichier a l'octet pres")

    def test_2_rien_a_changer(self):
        """Deux fois de suite sur la meme plage : la 2e fois rien ne change (fichier non reecrit, aucune version)."""
        d = installer('script1')
        f = d / 'reels' / 'script.json'
        first = passage.refaire(d, 'script', 44.0, 58.0)
        h1, n1 = sha(f), len(list((d / 'versions' / 'script').glob('*.json'))) if first['modifie'] else 0
        second = passage.refaire(d, 'script', 44.0, 58.0)
        print(f"\n  [deux fois 44-58 s] 1re : {first['resume']}")
        for ch in first['changes']:
            print(f'     - {ch}')
        print(f"                     2e : {second['resume']}")
        self.assertFalse(second['modifie'])
        self.assertIsNone(second['version'])
        self.assertEqual(sha(f), h1, 'fichier non reecrit')
        self.assertEqual(len(list((d / 'versions' / 'script').glob('*.json'))) if (d / 'versions').exists() else 0, n1)
        self.assertIn('rien à changer', second['resume'])

    def test_3_accroche_tech(self):
        """Plage sur l'accroche (style Tech, scenes + vecteurs) : rien d'automatique sur l'accroche sauf le bandeau ;
        un vecteur verrouille et un graphisme pose a la main y restent."""
        a, b = 0.0, 8.0

        def modif(r):
            vec = lambda vid, at, **k: {'id': vid, 'asset': 'banque/vecteurs/fleche.svg', 'at': at, 'duration': 1.5, 'x': .5,
                                        'y': .3, 'w': .3, 'rotation': 0, 'opacite': 1,
                                        'couleurs': {'principale': None, 'secondaire': None, 'contour': None},
                                        'couleursManuelles': False, 'anim': {'entree': 'pop', 'sortie': 'fondu'}, **k}
            r['vectors'] = [vec('v-accroche', 1.0, auto=True), vec('v-verrou', 2.0, auto=True, locked=True)]
            r['graphics'].append({'id': 'g-main', 'kind': 'motgeant', 'at': 1.5, 'duration': 1.0, 'props': {'text': 'MAIN'},
                                  'manual': True})
        d = installer('script1', modif)
        avant = montage.load(d, 'script')
        out = passage.refaire(d, 'script', a, b)
        apres = montage.load(d, 'script')
        print(f"\n  [accroche Tech 0-8 s] {out['resume']}")
        for ch in out['changes']:
            print(f'     - {ch}')
        self.hors_plage_identique(avant, apres, a, b)
        self.seuls_automatiques(avant, apres, a, b)
        seg, t = temps(apres)
        hook = sobriete.reperes(apres, seg)['accroche']
        v = {x['id']: x for x in apres['vectors']}
        self.assertTrue(v['v-accroche'].get('suggested'), 'vecteur automatique sur l\'accroche : retire')
        self.assertIn('accroche', v['v-accroche'].get('sobriete', ''))
        self.assertEqual(v['v-verrou'], avant['vectors'][1])
        self.assertIn(next(g for g in avant['graphics'] if g['id'] == 'g-main'), apres['graphics'])
        visibles = [s for s in apres.get('styleScenes') or [] if not s.get('hidden') and not verrous.protege(s)
                    and (iv('styleScenes', s, t) or (99,))[0] < hook]
        visibles += [x for x in apres['vectors'] if not x.get('suggested') and not verrous.protege(x) and x['at'] < hook]
        self.assertEqual(visibles, [], 'aucun element automatique visible sur l\'accroche')
        self.assertEqual(apres['banner'], avant['banner'], 'bandeau intact')
        print(f'     ok : accroche jusqu\'a {hook:.2f} s nette (vecteur automatique retire, verrou et pose a la main gardes)')

    def test_4_accroche_reel_impact(self):
        """Plage sur l'accroche (style Reel Impact, graphismes et plans de coupe comptes) : graphisme et plan de coupe
        automatiques de l'accroche retires (plan de coupe garde en proposition)."""
        a, b = 0.0, 10.0

        def modif(r):
            c0 = r['clips'][0]
            r['graphics'].append({'id': 'g-accroche', 'kind': 'motgeant', 'at': 2.0, 'duration': 1.0, 'props': {'text': 'WOW'},
                                  'auto': True})
            r['broll'] = [{'id': 'b-accroche', 'source': c0['source'], 'in': 1.0, 'at': 3.0, 'duration': 1.5, 'word': 'entreprise',
                           'auto': True, 'reason': 'essai', 'confidence': 'haute'}]
        d = installer('script2', modif)
        avant = montage.load(d, 'script')
        out = passage.refaire(d, 'script', a, b)
        apres = montage.load(d, 'script')
        print(f"\n  [accroche Reel Impact 0-10 s] {out['resume']}")
        for ch in out['changes']:
            print(f'     - {ch}')
        self.hors_plage_identique(avant, apres, a, b)
        self.seuls_automatiques(avant, apres, a, b)
        seg, _ = temps(apres)
        hook = sobriete.reperes(apres, seg)['accroche']
        vis = [g for g in apres['graphics'] if not g.get('suggested') and not verrous.protege(g) and g['at'] < hook
               and (g.get('auto') or g.get('generated'))]
        self.assertEqual(vis, [], 'aucun graphisme automatique visible sur l\'accroche')
        self.assertFalse([x for x in apres.get('broll') or [] if x['at'] < hook], 'plan de coupe retire de l\'accroche')
        self.assertTrue(any(s.get('source') == avant['broll'][0]['source'] and s.get('word') == 'entreprise'
                            for s in (apres.get('suggestions') or {}).get('broll') or []), 'plan de coupe garde en proposition')
        print(f'     ok : accroche jusqu\'a {hook:.2f} s nette ; plan de coupe garde en proposition')

    def test_5_plages_invalides(self):
        """Plages refusees avec des phrases claires en francais ; une fin apres la fin de la video y est ramenee."""
        cas = [((-1, 5), 'avant 0 s'), ((10, 5), 'le début doit être avant la fin'), ((5, 5), 'le début doit être avant la fin'),
               ((5, 5.1), 'Passage trop court'), ((float('nan'), 5), 'doit être un nombre'), (('abc', 3), 'doit être un nombre'),
               ((None, 3), 'doit être un nombre'), ((200, 210), 'après la fin de la vidéo'), ((70.8, 75), 'Passage trop court')]
        for (x, y), attendu in cas:
            with self.assertRaises(passage.PassageInvalide) as e:
                passage.verifier(x, y, 70.87)
            self.assertIn(attendu, str(e.exception), (x, y))
            print(f'\n  [refus] {x!s:>5} → {y!s:<5} : {e.exception}', end='')
        a, b, notes = passage.verifier(60, 999, 70.87)
        self.assertEqual((a, b), (60.0, 70.87))
        self.assertIn('Fin ramenée', notes[0])
        # « Fin ici » tout au bout : l'interface envoie la fin arrondie a 3 decimales (70,867 > 70,8666…) : pas de remarque
        a, b, notes = passage.verifier(60, 70.867, 70.86666)
        self.assertEqual((b, notes), (70.867, []))
        with self.assertRaises(passage.PassageInvalide) as e:
            passage.refaire(BOX / 'inexistant', 'script', 1, 5)
        self.assertIn('Montage introuvable', str(e.exception))
        d = installer('script1')
        h = sha(d / 'reels' / 'script.json')
        with self.assertRaises(passage.PassageInvalide):
            passage.refaire(d, 'script', 300, 310)
        self.assertEqual(sha(d / 'reels' / 'script.json'), h, 'refus : fichier inchange')
        self.assertFalse((d / 'versions').exists(), 'refus : aucune version')
        out = passage.refaire(d, 'script', 62.0, 999)
        self.assertAlmostEqual(out['fin'], 70.867, places=2)
        self.assertTrue(any('Fin ramenée' in x for x in out['remarques']))
        print()

    def test_6_ligne_de_commande(self):
        """python -m editeur passage : une ligne JSON ; plage invalide = message clair et code d'erreur."""
        root = BOX / 'racine-cli'
        if not root.exists():
            for rel in ('remotion/src', 'styles'):
                shutil.copytree(ROOT / rel, root / rel)
            shutil.copy2(ROOT / 'remotion/segments.mjs', root / 'remotion/segments.mjs')
            (root / 'runtime/cache/tmp').mkdir(parents=True)
        d = installer('script1')
        env = {**os.environ, 'EDITEUR_ROOT': str(root), 'PYTHONIOENCODING': 'utf-8', 'EDITEUR_LLM': '0'}
        run = lambda *x: subprocess.run([sys.executable, '-m', 'editeur', 'passage', str(d), '--reel', 'script', *x],
                                        cwd=ROOT / 'engine', env=env, capture_output=True, text=True, encoding='utf-8')
        r = run('--debut', '30', '--fin', '40')
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertIn('Passage 0:30,0 → 0:40,0', out['resume'])
        for args, attendu in ((('--debut', '500', '--fin', '510'), 'après la fin de la vidéo'),
                              (('--debut', '5', '--fin', '5.1'), 'Passage trop court'),
                              (('--debut', '8', '--fin', '3'), 'le début doit être avant la fin')):
            r = run(*args)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn(attendu, r.stderr)
            print(f'\n  [ligne de commande] {" ".join(args)} → code {r.returncode} : {r.stderr.strip().splitlines()[-1]}', end='')
        print()

    def test_7_plan_verrouille(self):
        """Plan verrouille (Clip.locked) dans la plage : ses mots en couleur ne bougent pas."""
        a, b = 42.0, 56.0

        def modif(r):
            _, t = temps(r)
            c = next(c for c in r['clips'] if any(a < t.get((c['id'], i), -1) < b for i in range(len(c['words']))))
            c['locked'] = True
            for i, w in enumerate(c['words']):
                if a < t.get((c['id'], i), -1) < b and _core(w['w']) in STOP and not w.get('hl'):
                    w['hl'] = True  # meme un mot outil colore reste colore : le plan est fige
                    r['hlAuto'][c['id']]['on'] = sorted(set(r['hlAuto'][c['id']]['on']) | {i})
                    break
        d = installer('script1', modif)
        avant = montage.load(d, 'script')
        out = passage.refaire(d, 'script', a, b)
        apres = montage.load(d, 'script')
        self.hors_plage_identique(avant, apres, a, b)
        for ca, cb in zip(avant['clips'], apres['clips']):
            if ca.get('locked'):
                self.assertEqual(ca, cb, 'plan verrouille intact')
                self.assertEqual(avant['hlAuto'][ca['id']], apres['hlAuto'][ca['id']])
        self.assertIn('plan verrouillé', out['resume'])
        print(f"\n  [plan verrouille 42-56 s] {out['resume']}")

    def test_8_ancien_reel(self):
        """Ancien reel sans historique des mots ni champ V2 : aucun champ ajoute, rien hors de la plage."""
        def modif(r):
            for k in ('hlAuto', 'notes', 'annotations', 'vectors', 'choreography'):
                r.pop(k, None)
        d = installer('script2', modif)
        avant = montage.load(d, 'script')
        out = passage.refaire(d, 'script', 20.0, 32.0)
        apres = montage.load(d, 'script')
        self.hors_plage_identique(avant, apres, 20.0, 32.0)
        for k in ('hlAuto', 'notes', 'annotations', 'vectors', 'choreography'):
            self.assertNotIn(k, apres, f'champ {k} ajoute a un ancien reel')
        print(f"\n  [ancien reel 20-32 s] {out['resume']}")

    def test_9_version_du_serveur_reprise(self):
        """La route du serveur garde deja « avant refaire le passage » : meme contenu = pas de doublon."""
        def modif(r):
            next(s for s in r['styleScenes'] if s['id'] == 'style-c3-21')['text'] = 'ANCIEN TEXTE'
        d = installer('script1', modif)
        v = d / 'versions' / 'script'
        v.mkdir(parents=True)
        nom = '2026-09-30T20-00-00 avant refaire le passage.json'
        shutil.copyfile(d / 'reels' / 'script.json', v / nom)
        out = passage.refaire(d, 'script', 30.0, 40.0)
        self.assertTrue(out['modifie'])
        self.assertEqual(out['version'], nom)
        self.assertEqual(len(list(v.glob('*.json'))), 1)

    def test_10_retouche_pendant_le_calcul(self):
        """Le reel est modifie (interface) pendant le calcul : rien n'est ecrase, aucune version, message clair."""
        def modif(r):
            next(s for s in r['styleScenes'] if s['id'] == 'style-c3-21')['text'] = 'ANCIEN TEXTE'
        d = installer('script1', modif)
        f = d / 'reels' / 'script.json'
        vrai = passage._choregraphie

        def interface(reel, tpl, P, info):
            vrai(reel, tpl, P, info)
            r = json.loads(f.read_text(encoding='utf-8'))
            r['banner']['text'] = 'RETOUCHE PENDANT LE CALCUL'
            f.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
        passage._choregraphie = interface
        try:
            with self.assertRaises(passage.PassageInvalide) as e:
                passage.refaire(d, 'script', 30.0, 40.0)
        finally:
            passage._choregraphie = vrai
        self.assertIn('modifié pendant le calcul', str(e.exception))
        self.assertEqual(montage.load(d, 'script')['banner']['text'], 'RETOUCHE PENDANT LE CALCUL')
        self.assertFalse((d / 'versions').exists())

    def test_11_pages_comme_timeline(self):
        """Les pages de sous-titres du module sont exactement celles de timeline.ts (aperçu / export)."""
        for nom in ('script1', 'script2'):
            r = json.loads((FIX / 'projects' / nom / 'reels' / 'script.json').read_text(encoding='utf-8'))
            seg = montage.compute(r)
            mine = passage._pages(r, seg)
            ref = pages_ts(r)
            self.assertEqual(len(mine), len(ref), nom)
            for (s, e, ws), p in zip(mine, ref):
                self.assertAlmostEqual(s, p['start'], places=6)
                self.assertAlmostEqual(e, p['end'], places=6)
                self.assertEqual([list(x) for x in ws], p['words'])
            print(f'\n  [pages] {nom} : {len(mine)} pages identiques a timeline.ts', end='')
        print()

    def test_12_quatre_plages_script2(self):
        """Plusieurs plages sur un 2e reel (Reel Impact, sans style de galerie) : toujours rien hors de la plage."""
        for a, b in ((5.0, 15.0), (12.3, 22.3), (30.0, 45.0), (45.0, 52.37)):
            d = installer('script2')
            avant = montage.load(d, 'script')
            out = passage.refaire(d, 'script', a, b)
            apres = montage.load(d, 'script')
            self.hors_plage_identique(avant, apres, a, b)
            self.seuls_automatiques(avant, apres, a, b)
            print(f"\n  [script2 {a}-{b}] {out['resume']}", end='')
        print()


    def test_13_mots_stables(self):
        """Sans rien retoucher, refaire un passage garde les memes mots en couleur (les choix automatiques encore
        valables gardent leur place : « cinq fois moins cher » reste en couleur)."""
        for nom, plages in (('script1', ((30.0, 40.0), (10.0, 25.0), (55.0, 70.8))), ('script2', ((30.0, 40.0),))):
            for a, b in plages:
                d = installer(nom)
                avant = montage.load(d, 'script')
                passage.refaire(d, 'script', a, b)
                apres = montage.load(d, 'script')
                hl = lambda r: {(c['id'], i) for c in r['clips'] for i, w in enumerate(c['words']) if w.get('hl')}
                self.assertEqual(hl(avant), hl(apres), f'{nom} {a}-{b} : mots en couleur changes sans raison')
            print(f'\n  [mots stables] {nom} : {len(plages)} plage(s), memes mots en couleur', end='')
        print()


    def test_14_ia_une_seule_session(self):
        """Avec l'IA locale (simulee) : une seule session ouverte pour toute la passe (le serveur IA ne demarre pas deux
        fois), l'IA qui ne repond pas laisse les regles travailler ; une IA qui ne demarre pas = regles seules, dit."""
        from contextlib import contextmanager
        journal = {'profondeur': 0, 'max': 0, 'ouvertures': 0, 'appels': []}

        @contextmanager
        def session(vision=False):
            journal['ouvertures'] += 1
            journal['profondeur'] += 1
            journal['max'] = max(journal['max'], journal['profondeur'])
            try:
                yield
            finally:
                journal['profondeur'] -= 1

        def ask_json(*a, **k):
            journal['appels'].append(journal['profondeur'])
            raise RuntimeError('IA simulee : pas de reponse')
        vrais = (llm.available, llm.session, llm.ask_json, os.environ.get('EDITEUR_LLM'))
        llm.available, llm.session, llm.ask_json = (lambda: True), session, ask_json
        os.environ['EDITEUR_LLM'] = '1'
        try:
            d = installer('script1')
            out = passage.refaire(d, 'script', 30.0, 40.0)
            self.assertTrue(out['ia'])
            self.assertTrue(journal['appels'], 'l\'IA a ete sollicitee')
            self.assertTrue(all(p >= 2 for p in journal['appels']), 'chaque appel a lieu DANS la session de la passe')

            @contextmanager
            def en_panne(vision=False):
                raise RuntimeError('Le serveur IA local n\'a pas demarre')
                yield
            llm.session = en_panne
            d = installer('script1')
            out = passage.refaire(d, 'script', 30.0, 40.0)
            self.assertFalse(out['ia'])
            self.assertTrue(any('IA locale indisponible' in r for r in out['remarques']))
        finally:
            llm.available, llm.session, llm.ask_json = vrais[:3]
            os.environ['EDITEUR_LLM'] = vrais[3] or '0'
        print(f"\n  [IA simulee] {journal['ouvertures']} ouverture(s) de session, appels a la profondeur {journal['appels']}")


    def test_15_liste_pas_triee(self):
        """Graphismes pas tries par temps (propositions ajoutees a la fin, element glisse dans la timeline) : rien a
        changer = fichier non reecrit, aucune version, pas de faux « historique mis a jour »."""
        def modif(r):
            r['graphics'] = sorted(r['graphics'], key=lambda g: -g['at'])
        for a, b in ((30.0, 40.0), (12.3, 22.3)):
            d = installer('script2', modif)
            f = d / 'reels' / 'script.json'
            h = sha(f)
            out = passage.refaire(d, 'script', a, b)
            self.assertFalse(out['modifie'], out['changes'])
            self.assertEqual(sha(f), h)
            self.assertFalse((d / 'versions').exists())
        print(f"\n  [liste pas triee] {out['resume']}")

    def test_16_relecture_sans_faux_deplacement(self):
        """Un chiffre que la relecture avait deja deplace (7,4 s -> 8,7 s) : la passe repart de 7,4 s, la relecture le
        remet a 8,7 s ; rien n'a bouge pour le monteur, le compte rendu ne dit pas « déplacé ». Un vrai deplacement,
        lui, est dit."""
        d = installer('script2')
        avant = montage.load(d, 'script')
        out = passage.refaire(d, 'script', 5.0, 15.0)
        apres = montage.load(d, 'script')
        g = lambda r: next(x for x in r['graphics'] if x['id'] == 'g1-chiffre')
        self.assertEqual(g(avant), g(apres))
        self.assertFalse([c for c in out['changes'] if 'déplacé' in c], out['changes'])
        self.assertFalse(apres['sobriete']['deplaces'])
        vec = {'id': 'v1', 'asset': 'banque/vecteurs/cercle.svg', 'at': 41.5, 'duration': 1.0, 'x': .5, 'y': .3, 'w': .3,
               'rotation': 0, 'opacite': 1, 'couleurs': {'principale': None, 'secondaire': None, 'contour': None},
               'couleursManuelles': False, 'anim': {'entree': 'pop', 'sortie': 'fondu'}, 'auto': True, 'raison': 'essai'}
        d = installer('script2', lambda r: r.__setitem__('vectors', [dict(vec)]))
        out = passage.refaire(d, 'script', 30.0, 50.0)
        v = montage.load(d, 'script')['vectors'][0]
        self.assertNotEqual(v['at'], 41.5)
        self.assertTrue(any('déplacé de 41,5 s' in c for c in out['changes']), out['changes'])
        print(f"\n  [relecture] vrai deplacement dit : {[c for c in out['changes'] if 'déplacé' in c][0]}")


if __name__ == '__main__':
    print(f'Bac : {BOX}')
    unittest.main(verbosity=2)
