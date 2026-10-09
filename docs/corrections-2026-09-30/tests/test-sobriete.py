"""Tests hors ligne (sans IA) de la sobriete : relecture du monteur, libelles des chiffres, titres, bandeau,
mots des plans de coupe, et les correctifs A1, A2, A3 et C de docs/taches-fable/RESULTAT-FABLE.md.
A lancer depuis n'importe ou (par exemple depuis engine/ avec l'environnement charge) :
    python ../docs/corrections-2026-09-30/tests/test-sobriete.py
Donnees (a cote de ce fichier) : copies des reels automatiques rates de script1 et video1video1
(script1-auto-origine.json, video1-auto-origine.json), montes AVANT la relecture du monteur. Rien n'est ecrit."""
import copy
import json
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]  # docs/corrections-2026-09-30/tests -> racine du projet
sys.path.insert(0, str(ROOT / 'engine'))
os.environ['EDITEUR_LLM'] = '0'
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
from editeur import auto, broll, derush, graphismes, llm, montage, sobriete  # noqa: E402
from editeur.script import normalize  # noqa: E402

llm.available = lambda: False  # aucune IA locale pendant ces essais


def overlays(reel, seg):
    """Elements visibles (bandeau compris), comme Reel.tsx pour un style sans habillage de galerie."""
    out = []
    b = reel.get('banner') or {}
    if b.get('enabled') and str(b.get('text') or '').strip():
        out.append((b.get('start') or 0, b.get('end') or seg['duration'], 'bandeau'))
    out += [(x['at'], x['at'] + x['duration'], 'plan') for x in reel.get('broll') or []]
    out += [(g['at'], g['at'] + g['duration'], g['kind']) for g in reel.get('graphics') or [] if not g.get('suggested')]
    return out


def fake_seg(sentences, clip='c1', hl=(), step=0.35, gap=1.0):
    """Segment de montage minimal, comme montage.compute : un mot toutes les 0,35 s, une pause d'une seconde
    entre deux phrases, aucune coupe. hl : mots (normalises) mis en couleur."""
    words, t = [], 0.0
    for sentence in sentences:
        for x in sentence.split():
            words.append({'w': x, 'start': round(t, 2), 'end': round(t + 0.3, 2), 'clip': clip, 'index': len(words),
                          'hl': normalize(x.strip(',.!?')) in hl})
            t += step
        t += gap
    return {'duration': round(t, 2), 'words': words, 'video': [], 'audio': []}


def start_of(seg, word):
    return next(w['start'] for w in seg['words'] if w['w'] == word)


class Sobriete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bad = json.loads((HERE / 'script1-auto-origine.json').read_text(encoding='utf-8'))
        cls.seg = montage.compute(cls.bad)

    def test_relecture_du_reel_rate(self):
        r = copy.deepcopy(self.bad)
        before = overlays(r, self.seg)
        self.assertEqual(len([o for o in before if o[0] < 3]), 3)  # bandeau + TEMPS + plan de coupe
        rep = sobriete.relire(r, seg=self.seg, tout=True)
        after = overlays(r, self.seg)
        # rien d'autre que le bandeau pendant les 3 premieres secondes ; et pas la premiere phrase coupee par « … »
        self.assertLessEqual({o[2] for o in after if o[0] < 3}, {'bandeau'})
        self.assertFalse(r['banner']['enabled'] and r['banner']['text'].endswith('…'))
        # un seul element a la fois, au moins 4 s entre deux
        after.sort()
        for a, b in zip(after, after[1:]):
            self.assertGreaterEqual(b[0] - a[1], 4.0 - 1e-6, (a, b))
        # plus de plan de coupe sur la marque, un chiffre ou un petit mot
        words = {x.get('word') for x in r.get('broll') or []}
        self.assertFalse(words & {'RyuCalls', 'deux', 'lead'})
        # la liste de benefices n'est jamais avant la solution (« C'est pour ca que chez RyuCalls », 28,8 s)
        for g in r['graphics']:
            if g['kind'] == 'coches' and not g.get('suggested'):
                self.assertGreaterEqual(g['at'], rep['reperes']['solution'] - 0.3)
        # rien n'est perdu : les elements retires sont en propositions
        self.assertEqual(len(r['graphics']), len(self.bad['graphics']))
        self.assertEqual(len(r['broll']) + len(r['suggestions']['broll']), len(self.bad['broll']))
        self.assertTrue(rep['retires'] and all(isinstance(x, str) for x in rep['retires']))

    def test_relecture_video1(self):
        """Meme relecture sur le second reel automatique rate (video1video1)."""
        r = json.loads((HERE / 'video1-auto-origine.json').read_text(encoding='utf-8'))
        seg = montage.compute(r)
        rep = sobriete.relire(r, seg=seg, tout=True)
        after = sorted(overlays(r, seg))
        self.assertLessEqual({o[2] for o in after if o[0] < rep['reperes']['accroche']}, {'bandeau'})
        for a, b in zip(after, after[1:]):
            self.assertGreaterEqual(b[0] - a[1], 4.0 - 1e-6, (a, b))
        self.assertTrue(rep['retires'])

    def test_elements_poses_a_la_main_intacts(self):
        r = copy.deepcopy(self.bad)
        rep = sobriete.relire(r, seg=self.seg, tout=False)  # aucun element n'est marque « auto »
        self.assertEqual(r['broll'], self.bad['broll'])
        self.assertEqual(r['graphics'], self.bad['graphics'])
        self.assertFalse(rep['retires'])

    def test_budget_du_style(self):
        self.assertEqual(sobriete.budget({})['ecart'], 4.0)
        b = sobriete.budget({'budget': {'par_minute': 99, 'ecart': 2, 'inconnu': 3}})
        self.assertEqual((b['par_minute'], b['ecart']), (30, 2.0))
        r = copy.deepcopy(self.bad)
        rep = sobriete.relire(r, {'budget': {'par_minute': 0}}, seg=self.seg, tout=True)
        self.assertFalse([g for g in r['graphics'] if not g.get('suggested')] + r['broll'])
        self.assertTrue(rep['retires'])

    def test_reperes(self):
        rep = sobriete.reperes(self.bad, self.seg)
        self.assertTrue(3.0 <= rep['accroche'] <= 6.0)
        self.assertAlmostEqual(rep['solution'], 28.8, delta=0.5)
        self.assertGreater(rep['cta'], 60)
        # script1 a un bloc d'appel a l'action (s1b5) : c'est lui qui donne le repere, pas les mots
        self.assertEqual(self.bad.get('ctaBlock'), 's1b5')
        sans_bloc = {**self.bad, 'ctaBlock': None}
        self.assertEqual(sobriete.reperes(sans_bloc, self.seg)['cta'], rep['cta'])  # ici les deux concordent

    def test_accroche_fin(self):
        """accroche_fin : la seule definition de l'accroche (galerie.py doit s'en servir a la place de HOOK_MAX)."""
        rep = sobriete.reperes(self.bad, self.seg)
        self.assertEqual(sobriete.accroche_fin(self.seg['words'], self.seg['duration']), rep['accroche'])
        self.assertEqual(sobriete.accroche_fin([], 10), 3.0)  # jamais moins de 3 s...
        self.assertEqual(sobriete.accroche_fin([], 2), 2.0)  # ...sauf si la video est plus courte
        seg = fake_seg(['Un deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize '
                        'dix-sept dix-huit dix-neuf vingt.'])  # 20 mots : la phrase dure 6,95 s
        self.assertEqual(sobriete.accroche_fin(seg['words'], seg['duration']), 6.0)  # phrase longue : accroche_max
        b = sobriete.budget({'budget': {'accroche_max': 3.0}})
        self.assertEqual(sobriete.accroche_fin(seg['words'], seg['duration'], b), 3.0)
        self.assertEqual(sobriete.reperes({'clips': []}, seg, b)['accroche'], 3.0)

    # --- A1 : bandeau regle sur « Toute la video » (banner.end = null, bouton de l'onglet Style) ---
    def test_A1_bandeau_toute_la_video(self):
        r = copy.deepcopy(self.bad)
        r['banner'] = {'enabled': True, 'text': 'VOTRE CONCURRENT VOUS BAT', 'start': 0, 'end': None}
        rep = sobriete.relire(r, seg=self.seg, tout=True)
        r2 = copy.deepcopy(self.bad)
        r2['banner'] = {'enabled': True, 'text': 'VOTRE CONCURRENT VOUS BAT', 'start': 0, 'end': 4.5}
        rep2 = sobriete.relire(r2, seg=self.seg, tout=True)
        self.assertGreater(rep['gardes'], 0)  # le bandeau ne bloque plus tout le reste
        self.assertEqual(rep['gardes'], rep2['gardes'])
        sans = lambda x: sorted(o for o in overlays(x, self.seg) if o[2] != 'bandeau')
        self.assertEqual(sans(r), sans(r2))  # memes elements gardes que pour un bandeau limite a l'accroche
        self.assertIsNone(r['banner']['end'])  # le reglage du monteur n'est pas touche
        self.assertTrue(r['banner']['enabled'])
        # pendant l'accroche, le bandeau reste le seul element
        self.assertLessEqual({o[2] for o in overlays(r, self.seg) if o[0] < rep['reperes']['accroche']}, {'bandeau'})

    # --- A2 : un mot d'appel a l'action (« contacte ») dit au milieu de la video ---
    PUB = ['Vos leads attendent trop longtemps au téléphone chaque jour.', 'Chaque minute perdue coûte un client.',
           'Chez nous un agent contacte vos leads en cinq minutes.', 'Vos ventes montent dès la première semaine.',
           'Votre équipe garde son temps pour vendre.', 'Vos clients sont rappelés le soir même.',
           "Essayez gratuitement dès aujourd'hui."]

    def test_A2_appel_a_l_action_au_milieu(self):
        seg = fake_seg(self.PUB)
        reel = {'clips': [{'id': 'c1', 'block': 'b1'}]}
        rep = sobriete.reperes(reel, seg)
        self.assertLess(start_of(seg, 'contacte'), seg['duration'] * 0.5)
        self.assertIsNone(rep['cta'])  # « contacte » au milieu n'est pas un appel a l'action : aucun repere
        # un plan de coupe apres cette phrase n'est plus retire (tout=True : il est automatique)
        r = {**reel, 'sources': {'b1': {'name': 'x'}}, 'width': 1080, 'height': 1920,
             'broll': [{'id': 'p1', 'source': 'b1', 'in': 0, 'at': start_of(seg, 'ventes') - 0.1, 'duration': 1.6,
                        'word': 'ventes', 'auto': True}]}
        out = sobriete.relire(r, {}, seg=seg, tout=True)
        self.assertEqual(len(r['broll']), 1, out['retires'])
        self.assertFalse(any('appel' in x for x in out['retires']))

    def test_A2_mot_d_action_dans_le_dernier_quart(self):
        seg = fake_seg(self.PUB[:-1] + ['Cliquez sur le lien pour essayer.'])
        rep = sobriete.reperes({'clips': [{'id': 'c1', 'block': 'b1'}]}, seg)
        self.assertEqual(rep['cta'], start_of(seg, 'Cliquez'))
        self.assertGreaterEqual(rep['cta'], seg['duration'] * 0.75)
        # la meme phrase dite au milieu (puis d'autres) : pas un appel a l'action
        seg2 = fake_seg(self.PUB[:3] + ['Cliquez sur le lien pour essayer.'] + self.PUB[3:])
        self.assertIsNone(sobriete.reperes({'clips': [{'id': 'c1', 'block': 'b1'}]}, seg2)['cta'])

    def test_A2_bloc_d_appel_a_l_action_du_script(self):
        seg = fake_seg(self.PUB)
        cut = start_of(seg, 'clients')
        for w in seg['words']:  # les deux dernieres phrases viennent du bloc « appel a l'action » du script
            w['clip'] = 'c2' if w['start'] >= cut - 0.5 else 'c1'
        reel = {'clips': [{'id': 'c1', 'block': 'b1'}, {'id': 'c2', 'block': 'b2'}], 'ctaBlock': 'b2'}
        rep = sobriete.reperes(reel, seg)
        # derniere phrase des mots de ce bloc, meme si « contacte » est dit plus tot
        self.assertEqual(rep['cta'], start_of(seg, 'Essayez'))
        # le bloc passe avant les mots : « Cliquez » au milieu ne deplace pas le repere
        seg2 = fake_seg(self.PUB[:3] + ['Cliquez sur le lien pour essayer.'] + self.PUB[3:])
        for w in seg2['words']:
            w['clip'] = 'c2' if w['start'] >= start_of(seg2, 'clients') - 0.5 else 'c1'
        self.assertEqual(sobriete.reperes(reel, seg2)['cta'], start_of(seg2, 'Essayez'))
        # bloc absent du montage (plans coupes) : on retombe sur les mots du dernier quart, sinon rien
        self.assertIsNone(sobriete.reperes({**reel, 'ctaBlock': 'b9'}, seg)['cta'])

    def test_A2_emplacements_de_plans_de_coupe(self):
        """broll._slots lit le meme repere : des emplacements APRES la phrase « contacte » quand ce n'est pas la fin."""
        hl = {'ventes', 'equipe', 'clients', 'vendre', 'rappeles'}
        seg = fake_seg(self.PUB, hl=hl)
        reel = {'clips': [{'id': 'c1', 'block': 'b1'}], 'suggestions': {}}
        slots = broll._slots(reel, seg)
        rep = sobriete.reperes(reel, seg)
        self.assertTrue(slots)
        self.assertTrue(all(s['at'] >= rep['accroche'] for s in slots))
        self.assertTrue(any(s['at'] > start_of(seg, 'contacte') + 1.0 for s in slots), slots)
        # avec un vrai appel a l'action a la fin : aucun emplacement dessus
        seg2 = fake_seg(self.PUB[:-1] + ['Cliquez sur le lien pour essayer.'], hl=hl | {'essayer'})
        rep2 = sobriete.reperes(reel, seg2)
        slots2 = broll._slots(reel, seg2)
        self.assertTrue(slots2)
        self.assertTrue(all(s['at'] + s['duration'] <= rep2['cta'] for s in slots2), slots2)

    # --- A3 : un emoji pose a la main n'est jamais « automatique » ---
    def test_A3_emoji_a_la_main(self):
        r = copy.deepcopy(self.bad)  # aiMode = auto, comme un montage automatique
        r['emoji'] = {'enabled': True}
        r['clips'][0]['emojis'] = [[1, '🔥']]  # pose a la main dans l'onglet Texte, sur l'accroche
        rep = sobriete.relire(r, seg=self.seg, tout=False)  # changement de style
        self.assertIn([1, '🔥'], r['clips'][0]['emojis'])
        self.assertFalse(any('Emoji' in x for x in rep['retires']), rep['retires'])
        els = sobriete._elements(r, self.seg)
        self.assertFalse(any(e['auto'] for e in els if e['type'] == 'emoji'))
        # montage automatique qui vient de finir (tout=True) : l'emoji sur l'accroche est nettoye, sans etre perdu
        r = copy.deepcopy(self.bad)
        r['emoji'] = {'enabled': True}
        r['clips'][0]['emojis'] = [[1, '🔥']]
        sobriete.relire(r, seg=self.seg, tout=True)
        self.assertNotIn([1, '🔥'], r['clips'][0]['emojis'])
        self.assertIn([1, '🔥'], r['suggestions']['emojis']['c1'])

    def test_A3_scenes_du_style(self):
        r = copy.deepcopy(self.bad)
        r['design'] = {'mode': 'infographie', 'enabled': True}
        r['styleScenes'] = [
            {'id': 's-auto', 'kind': 'metric', 'clip': 'c1', 'index': 1, 'text': '3 h', 'duration': 2.4},
            {'id': 's-main', 'kind': 'metric', 'clip': 'c1', 'index': 2, 'text': '5×', 'duration': 2.4, 'manual': True},
            {'id': 's-edit', 'kind': 'metric', 'clip': 'c1', 'index': 3, 'text': '2 j', 'duration': 2.4, 'edited': True}]
        rep = sobriete.relire(r, seg=self.seg, tout=False)
        by = {s['id']: s for s in r['styleScenes']}
        self.assertTrue(by['s-auto'].get('hidden'), rep['retires'])  # scene du style sur l'accroche : masquee
        self.assertFalse(by['s-main'].get('hidden'))  # posee a la main : respectee
        self.assertFalse(by['s-edit'].get('hidden'))  # retouchee : respectee
        self.assertEqual({e['obj']['id']: e['auto'] for e in sobriete._elements(r, self.seg) if e['type'] == 'scene'},
                         {'s-main': False, 's-edit': False})  # s-auto est deja masquee

    # --- C : « chez vos concurrents » n'est pas le debut de la solution ---
    def test_C_debut_de_la_solution(self):
        seg = fake_seg(['Vos leads attendent trop longtemps au téléphone chaque jour.',
                        'Chez vos concurrents on répond en trois heures.',
                        "C'est pour ça que chez RyuCalls on place un setter."])
        rep = sobriete.reperes({'clips': []}, seg)
        self.assertGreater(start_of(seg, 'Chez'), rep['accroche'])  # la phrase est bien relue
        self.assertEqual(rep['solution'], start_of(seg, "C'est"))
        for phrase in ('chez vous', 'chez vos concurrents', 'chez votre concurrent', 'chez les autres', 'chez le voisin',
                       'chez la concurrence', 'chez un concurrent', 'chez eux', 'chez elle', 'chez ces gens',
                       'chez leurs clients', 'chez des concurrents', 'chez mon ancien patron',
                       'chez nous'):  # « chez nous » etait deja exclu (c'est « avec nous » qui annonce la solution)
            self.assertIsNone(sobriete.SOLUTION.match(phrase + ' on attend'), phrase)
        for phrase in ('chez ryucalls on place', 'chez lemoine on repond', 'chez lesage on repond', 'avec nous on place',
                       'voici la solution'):
            self.assertTrue(sobriete.SOLUTION.match(phrase), phrase)

    def test_libelles_des_chiffres(self):
        w = lambda s: [{'w': x} for x in s.split()]
        self.assertEqual(graphismes._label(w("cinq fois moins cher qu'un employé"), 2), 'MOINS CHER')
        self.assertEqual(graphismes._label(w('trois heures a déjà été appelé'), 2), '')
        self.assertEqual(graphismes._label(w('deux fois plus de clients'), 2), 'PLUS DE CLIENTS')
        self.assertEqual(graphismes._label(w('deux fois plus de'), 2), '')
        self.assertEqual(graphismes._values('5 fois moins cher'), {5.0})

    def test_titres(self):
        self.assertEqual(derush.nice_label('Script 1', r'D:\x\Vidéo 1'), 'Vidéo 1')
        self.assertEqual(derush.nice_label('SCRIPT 2'), 'Vidéo 2')
        self.assertEqual(derush.nice_label('Offre de Noël', r'D:\x\Vidéo 1'), 'Offre de Noël')
        self.assertEqual(derush.nice_label('Script 3', r'D:\x\Lot 2026-09-30 10h51'), 'Vidéo 3')

    def test_bandeau(self):
        r = copy.deepcopy(self.bad)
        for text, ok in [('Plus vous prenez de temps à appeler un…', False), ('VOTRE CONCURRENT PRISE LE LEAD', False),
                         ('PLUS VOUS PRENEZ DE TEMPS À APPELER UN LEAD', False), ('VOTRE CONCURRENT CLOSE VOS LEADS', True)]:
            r['banner'] = {'enabled': True, 'text': text, 'start': 0, 'end': 4.5}
            r['suggestions'] = {'banners': [text], 'words': {}, 'emojis': {}}
            self.assertEqual(auto._banner_ok(r), ok, text)
        r['suggestions']['banners'] = []  # pas valide par l'IA : pas de bandeau
        self.assertFalse(auto._banner_ok(r))

    def test_mots_des_plans_de_coupe(self):
        words = [{'w': x, 'start': i, 'end': i + 0.5} for i, x in
                 enumerate("C'est pour ça que chez RyuCalls, on place un setter qualifié rapidement".split())]
        ok = {words[k]['w']: broll._content_word(words, k, set()) for k in range(len(words))}
        self.assertFalse(ok['RyuCalls,'])
        self.assertFalse(ok['rapidement'])
        self.assertFalse(ok['que'])
        self.assertTrue(ok['setter'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
