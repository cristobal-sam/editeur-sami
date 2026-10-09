"""Integration V2 (lead) : UN reel qui porte TOUTES les fonctions V2 a la fois (notes, dessins, banque, vecteurs, charte,
choregraphie, verrous, plan verrouille), puis toutes les passes automatiques reelles a la suite : nouvelle passe de l'IA
(cerveau creatif, galerie, relecture, choregraphie --tout, refresh_ai), changements de style et de charte, « Refaire ce
passage », montage automatique complet (auto._finish), et tous les anciens reels du projet.
    python ../docs/direction-creative-v2/tests/integration/test-integration.py      (depuis engine/, environnement charge)
Donnees : copies EN MEMOIRE des reels FIGES (fixtures/projects : jamais les projets vivants de l'utilisateur), et copies
de projet dans runtime/cache/tmp/dcv2-integration/integ-<hasard>/ ; IA locale coupee ; detourage et recherche de plans de
coupe neutralises (GPU). Controle final : AUCUN fichier des donnees figees n'a change pendant le test (dates et tailles).
Le reel final est ecrit dans le bac (reel-final.json)."""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from commun import BASE, CHARTE_A, CHARTE_B, FIX, RETOUCHE, ROOT, complet, couleurs_vecteur, lire, teinte  # noqa: E402
from editeur import auto, choregraphie, creative, galerie, montage, passage, sobriete, verrous  # noqa: E402
from editeur import reel as reelmod  # noqa: E402

BAC = Path(tempfile.mkdtemp(prefix='integ-', dir=BASE))


def empreinte_projets():
    """Taille + date de chaque fichier des donnees figees fixtures/projects (controle : le test n'y ecrit jamais). Les
    projets vivants de l'utilisateur ne sont ni lus ni surveilles : le vrai editeur peut y travailler pendant le test."""
    out = {}
    for d, _, fs in os.walk(FIX / 'projects'):
        for f in fs:
            p = Path(d) / f
            try:
                st = p.stat()
                out[str(p.relative_to(FIX))] = (st.st_size, int(st.st_mtime))
            except OSError:
                pass
    return out


AVANT_PROJETS = empreinte_projets()


# ---------------------------------------------------------------- invariants ----------------------------------------------------------------
LISTES = ('graphics', 'broll', 'vectors', 'styleScenes')


def proteges(r):
    """Tout ce qui est verrouille / retouche : {(champ, cle): element}."""
    out = {}
    for champ in LISTES:
        for e in r.get(champ) or []:
            if verrous.protege(e):
                out[(champ, e['id'])] = e
    for e in (r.get('sfx') or {}).get('extra') or []:
        if verrous.protege(e):
            out[('sfx.extra', verrous.cle(e))] = e
    for e in (r.get('choreography') or {}).get('cues') or []:
        if verrous.protege(e):
            out[('cue', e['id'])] = e
    return out


def temps_cibles(r, seg):
    """Temps ACTUEL de chaque cible de mouvement (la cible fait foi, SPEC §2.6), calcule ici independamment."""
    mots = {(w['clip'], w['index']): w['start'] for w in seg['words']}
    t = {}
    for g in r.get('graphics') or []:
        t[('graphics', g['id'])] = g['at']
    for v in r.get('vectors') or []:
        t[('vector', v['id'])] = v['at']
    for b in r.get('broll') or []:
        t[('broll', b['id'])] = b['at']
    for s in r.get('styleScenes') or []:
        if (s.get('clip'), s.get('index')) in mots:
            t[('design', s['id'])] = mots[(s['clip'], s['index'])]
    t[('banner', 'banner')] = float((r.get('banner') or {}).get('start') or 0)
    for (c, i), s in mots.items():
        t[('caption', f'{c}:{i}')] = s
    return t


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s1 = lire('projects/script1/reels/script.json')
        cls.s2 = lire('projects/script2/reels/script.json')
        cls.r, cls.pose = complet(cls.s2)
        (BAC / 'reel-complet.json').write_text(json.dumps(cls.r, ensure_ascii=False, indent=1), encoding='utf-8')

    def assert_proteges(self, avant, apres, quoi):
        pa, pb = proteges(avant), proteges(apres)
        for k, e in pa.items():
            self.assertIn(k, pb, f'{quoi} : {k} protege a disparu')
            self.assertEqual(pb[k], e, f'{quoi} : {k} protege modifie')
        self.assertEqual(apres.get('notes'), avant.get('notes'), f'{quoi} : notes modifiees')
        self.assertEqual(apres.get('annotations'), avant.get('annotations'), f'{quoi} : dessins modifies')
        self.assertEqual(apres['banner'], avant['banner'], f'{quoi} : bandeau verrouille modifie')
        ca = next(c for c in avant['clips'] if c.get('locked'))
        cb = next(c for c in apres['clips'] if c['id'] == ca['id'])
        self.assertEqual([w.get('hl') for w in cb['words']], [w.get('hl') for w in ca['words']], f'{quoi} : mots du plan verrouille')
        self.assertEqual(cb.get('emojis'), ca.get('emojis'), f'{quoi} : emojis du plan verrouille')

    def assert_choregraphie_sobre(self, r, quoi):
        """Jamais deux entrees en meme temps (mouvements automatiques), rien sur l'accroche sauf le bandeau, et chaque
        mouvement automatique a une raison."""
        seg = montage.compute(r)
        cues = [c for c in (r.get('choreography') or {}).get('cues') or [] if not c.get('desactive') and c['entree']['type'] != 'aucune']
        times = temps_cibles(r, seg)
        fen = []
        for c in cues:
            k = (c['cible']['type'], c['cible']['id'])
            if k not in times:
                continue  # element absent ou masque : le mouvement ne s'applique pas
            fen.append((times[k], times[k] + float(c['entree']['duree']), c))
        fen.sort(key=lambda x: x[0])
        for i, (a0, a1, ca) in enumerate(fen):
            for b0, b1, cb in fen[i + 1:]:
                if b0 >= a1 - 1e-6:
                    break
                both_user = verrous.protege(ca) and verrous.protege(cb)
                self.assertTrue(both_user, f'{quoi} : deux entrees en meme temps {ca["id"]} [{a0:.2f}-{a1:.2f}] et {cb["id"]} [{b0:.2f}-{b1:.2f}]')
        hook = sobriete.reperes(r, seg, sobriete.budget(choregraphie._template(r, None)))['accroche']
        for a0, _, c in fen:
            if c.get('auto') and not verrous.protege(c) and a0 < hook - .05:
                self.assertEqual(c['cible']['type'], 'banner', f'{quoi} : mouvement automatique sur l\'accroche ({c["id"]} a {a0:.2f} s < {hook:.2f} s)')
        for c in cues:
            if c.get('auto') and not verrous.protege(c):
                self.assertTrue(str(c.get('raison') or '').strip(), f'{quoi} : mouvement {c["id"]} sans raison')
        return len(fen)

    # 1. le reel complet est coherent, et la choregraphie ne cree ni ne deplace aucun element
    def test_1_reel_complet(self):
        r = self.r
        self.assertEqual(len(r['notes']), 4)
        self.assertEqual(len(r['annotations']), 4)
        self.assertTrue(all(e.get('manual') for e in (self.pose['chiffre'], self.pose['liste'], self.pose['son'], self.pose['etoile'], self.pose['coeur'])),
                        'tout ce que pose la banque est manual')
        avant = copy.deepcopy(r)
        choregraphie.actualiser(r, None)
        for champ in LISTES:
            self.assertEqual(r.get(champ), avant.get(champ), f'la choregraphie a modifie {champ}')
        self.assertEqual(r['sfx'], avant['sfx'])
        n = self.assert_choregraphie_sobre(r, 'reel complet')
        print(f'  reel complet : {len(r["choreography"]["cues"])} mouvements, {n} entrees actives, aucune simultanee')

    # 2. nouvelle passe de l'IA (cerveau creatif, galerie, relecture tout=True, choregraphie --tout) puis 3 styles
    def test_2_passe_ia_et_styles(self):
        avant = copy.deepcopy(self.r)
        r = copy.deepcopy(self.r)
        tpl = next(t for t in reelmod.list_templates() if t['id'] == r['template'])
        creative.apply(r, None, tpl)
        galerie.prepare(r, use_ai=False)
        sobriete.relire(r, tpl, tout=True)
        choregraphie.actualiser(r, tpl)
        self.assert_proteges(avant, r, 'passe de l\'IA')
        libre = next(v for v in r['vectors'] if v['id'] == 'v-libre')
        self.assertTrue(libre.get('suggested'), 'vecteur automatique libre sur l\'accroche : devient une proposition')
        self.assert_choregraphie_sobre(r, 'passe de l\'IA')
        for style in ('tech-application', 'documentaire', 'produit-3d', 'reel-impact'):
            reelmod.apply_template(r, style)
            self.assert_proteges(avant, r, f'style {style}')
            self.assert_choregraphie_sobre(r, f'style {style}')
            self.assertEqual(r['style']['highlight'], CHARTE_A['style']['highlight'], f'{style} : la charte passe par-dessus le style')
        (BAC / 'reel-apres-passes.json').write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')

    # 3. charte : un modele sans couleur suit la charte (A puis B) ; la retouche a la main reste
    def test_3_charte_et_retouche(self):
        r = copy.deepcopy(self.r)
        chiffre = lambda x: next(g for g in x['graphics'] if g['id'] == self.pose['chiffre']['id'])  # noqa: E731
        liste = lambda x: next(g for g in x['graphics'] if g['id'] == self.pose['liste']['id'])  # noqa: E731
        vec = lambda x, k: next(v for v in x['vectors'] if v['id'] == self.pose[k]['id'])  # noqa: E731
        self.assertEqual(teinte(chiffre(r), r), '#FF2D95', 'charte A : modele recolore automatiquement')
        self.assertEqual(couleurs_vecteur(r, vec(r, 'etoile'))['principale'], '#FF2D95', 'charte A : vecteur recolore')
        # charte B, puis changement de style (chemin du moteur : apply_template applique la charte par-dessus)
        r['brand'] = copy.deepcopy(CHARTE_B)
        reelmod.apply_template(r, 'reel-impact')
        self.assertEqual(teinte(chiffre(r), r), '#22C55E', 'charte B : le modele sans couleur suit la nouvelle charte')
        self.assertEqual(couleurs_vecteur(r, vec(r, 'etoile'))['principale'], '#22C55E', 'charte B : vecteur de la charte recolore')
        self.assertEqual(teinte(liste(r), r), RETOUCHE, 'retouche a la main gardee (modele)')
        self.assertEqual(liste(r)['props']['title'], 'Mes trois raisons', 'texte retouche garde')
        self.assertEqual(couleurs_vecteur(r, vec(r, 'coeur'))['principale'], RETOUCHE, 'retouche a la main gardee (vecteur)')
        # style immersif : les graphismes poses a la main restent dans le reel (et sont affiches : Reel.tsx userGraphic)
        reelmod.apply_template(r, 'tech-application')
        self.assertIn(self.pose['chiffre']['id'], [g['id'] for g in r['graphics'] if not g.get('suggested')])
        self.assertEqual(teinte(liste(r), r), RETOUCHE)

    # 4. « Refaire seulement ce passage » sur une copie du projet : rien ne change hors de la plage
    def test_4_passage(self):
        pdir = BAC / 'passage' / 'script2'
        (pdir / 'reels').mkdir(parents=True)
        shutil.copyfile(FIX / 'projects/script2/project.json', pdir / 'project.json')
        f = pdir / 'reels/script.json'
        f.write_text(json.dumps(self.r, ensure_ascii=False, indent=1), encoding='utf-8')
        avant = copy.deepcopy(self.r)
        seg = montage.compute(avant)
        a, b = 20.0, 32.0
        out = passage.refaire(pdir, 'script', a, b, {'ia': False})
        apres = json.loads(f.read_text(encoding='utf-8'))
        print(f'  passage {a}-{b} s : {out["resume"]}')
        self.assertTrue(out['modifie'], 'le passage a bien refait quelque chose (sinon le test ne prouverait rien)')
        dedans = next(v for v in apres['vectors'] if v['id'] == 'v-auto-dedans')
        self.assertTrue(dedans.get('suggested') or dedans['at'] != 22.3, 'dans la plage : le vecteur automatique en conflit est relu')
        self.assertEqual(next(v for v in apres['vectors'] if v['id'] == 'v-auto-dehors'), next(v for v in avant['vectors'] if v['id'] == 'v-auto-dehors'),
                         'hors de la plage : le vecteur automatique en conflit n\'est PAS touche')
        self.assert_proteges(avant, apres, 'passage')
        mots = {(w['clip'], w['index']): (w['start'], w['end']) for w in seg['words']}

        def dehors(at, dur):
            return at + dur <= a or at >= b

        def scene_t(s):
            return mots.get((s.get('clip'), s.get('index')), (None, None))[0]
        for champ in LISTES:
            def hors(e):
                at = scene_t(e) if champ == 'styleScenes' else e.get('at')
                return at is not None and dehors(at, float(e.get('duration') or 0))
            self.assertEqual([e for e in avant.get(champ) or [] if hors(e)], [e for e in apres.get(champ) or [] if hors(e)],
                             f'passage : {champ} hors de la plage modifies')
        sx = lambda r: [e for e in (r['sfx'].get('extra') or []) if dehors(e['t'], .5)]  # noqa: E731
        self.assertEqual(sx(avant), sx(apres), 'passage : bruitages hors plage')
        times = temps_cibles(avant, seg)
        cue_hors = lambda r: [c for c in (r.get('choreography') or {}).get('cues') or []  # noqa: E731
                              if (c['cible']['type'], c['cible']['id']) in times and dehors(times[(c['cible']['type'], c['cible']['id'])], float(c.get('duree') or 0))]
        self.assertEqual(cue_hors(avant), cue_hors(apres), 'passage : mouvements hors plage')
        for ca, cb in zip(avant['clips'], apres['clips']):
            self.assertEqual({k: v for k, v in ca.items() if k not in ('words', 'emojis')}, {k: v for k, v in cb.items() if k not in ('words', 'emojis')},
                             f'passage : plan {ca["id"]} (prise, coupes, vitesse) modifie')
            for i, (wa, wb) in enumerate(zip(ca['words'], cb['words'])):
                t0, t1 = mots.get((ca['id'], i), (None, None))
                if t0 is None or t1 <= a - .05 or t0 >= b + .05:
                    self.assertEqual(wa, wb, f'passage : mot hors plage {ca["id"]}/{i} « {wa["w"]} » modifie')
        geres = {'sobriete', 'hlAuto', 'graphics', 'broll', 'vectors', 'styleScenes', 'sfx', 'choreography', 'clips', 'creativePlan', 'suggestions'}
        for k in set(avant) | set(apres):
            if k not in geres:
                self.assertEqual(avant.get(k), apres.get(k), f'passage : champ « {k} » modifie')
        self.assertEqual({k: v for k, v in avant['sfx'].items() if k != 'extra'}, {k: v for k, v in apres['sfx'].items() if k != 'extra'})
        strip = lambda p: {**p, 'storyboard': [{k: v for k, v in s.items() if k != 'status'} for s in p.get('storyboard') or []]}  # noqa: E731
        self.assertEqual(strip(avant['creativePlan']), strip(apres['creativePlan']), 'passage : plan creatif (hors audit) modifie')
        self.assert_choregraphie_sobre(apres, 'passage')

    # 5. refresh_ai, ensure (changement de style par la ligne de commande du serveur) et « Refaire la choregraphie --tout »
    def test_5_sur_copie_projet(self):
        pdir = BAC / 'projet' / 'script2'
        (pdir / 'reels').mkdir(parents=True)
        shutil.copyfile(FIX / 'projects/script2/project.json', pdir / 'project.json')
        f = pdir / 'reels/script.json'
        f.write_text(json.dumps(self.r, ensure_ascii=False, indent=1), encoding='utf-8')
        avant = copy.deepcopy(self.r)
        reelmod.refresh_ai(pdir)
        self.assert_proteges(avant, json.loads(f.read_text(encoding='utf-8')), 'refresh_ai')
        reelmod.ensure(pdir, None, template='hormozi')
        self.assert_proteges(avant, json.loads(f.read_text(encoding='utf-8')), 'ensure --style hormozi')
        res = choregraphie.regenerer(pdir, 'script', libres=False)
        r = json.loads(f.read_text(encoding='utf-8'))
        self.assert_proteges({**avant, 'choreography': {'cues': [c for c in avant['choreography']['cues'] if c.get('locked')]}}, r, 'choregraphie --tout')
        self.assertTrue(any(c['id'] == avant['choreography']['cues'][1]['id'] and c.get('locked') for c in r['choreography']['cues']),
                        '--tout : le mouvement verrouille reste')
        self.assert_choregraphie_sobre(r, 'choregraphie --tout')
        print(f'  choregraphie --tout : {res["resume"][:140]}')
        (BAC / 'reel-final.json').write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')

    # 6. montage automatique complet (fin du pipeline de la Revision) : la choregraphie est creee, sobre, avec ses raisons
    def test_6_montage_automatique(self):
        # prises du projet : celles, FIGEES, du reel de Video 2 (medias optimises, echantillons, voix). Les videos brutes
        # de project.json ne sont pas relues (elles peuvent avoir ete supprimees par l'utilisateur : le test n'en depend pas)
        figees = lire('projects/script2/reels/script.json')['sources']

        def sources_figees(project, ids, cache, old_sources=None):
            manque = sorted(set(ids) - set(figees))
            assert not manque, f'prises absentes du reel fige : {manque}'
            return {sid: copy.deepcopy(figees[sid]) for sid in sorted(ids)}
        vrai_sources = reelmod._sources
        reelmod._sources = sources_figees
        try:
            self._montage_automatique()
        finally:
            reelmod._sources = vrai_sources

    def _montage_automatique(self):
        for style in ('tech-application', 'reel-impact'):
            pdir = BAC / f'auto-{style}' / 'script2'
            (pdir / 'reels').mkdir(parents=True)
            shutil.copyfile(FIX / 'projects/script2/project.json', pdir / 'project.json')
            auto._finish(pdir, style, {'type': 'publicite', 'titre': 'Essai'})
            r = json.loads((pdir / 'reels/script.json').read_text(encoding='utf-8'))
            self.assertEqual(r['template'], style)
            ch = r.get('choreography') or {}
            self.assertTrue(ch.get('cues'), f'{style} : le montage automatique cree la choregraphie')
            self.assertTrue(all(c.get('auto') and c.get('raison') for c in ch['cues']), f'{style} : chaque mouvement a une raison')
            n = self.assert_choregraphie_sobre(r, f'montage automatique {style}')
            for k in ('notes', 'annotations'):
                self.assertNotIn(k, r, f'{style} : {k} cree par le montage automatique')
            print(f'  montage automatique {style} : {len(ch["cues"])} mouvements, {n} entrees ; {str((ch.get("meta") or {}).get("resume", ""))[:110]}')

    # 7. tous les anciens reels figes (copies en memoire) : chaque passe fonctionne et n'ajoute aucun champ V2
    def test_7_anciens_reels(self):
        vus = 0
        for f in sorted((FIX / 'projects').glob('*/reels/*.json')):
            if f.parent.parent.name.startswith('_'):
                continue
            try:
                base = json.loads(f.read_text(encoding='utf-8'))
            except ValueError:
                continue
            if not isinstance(base, dict) or not base.get('clips'):
                continue
            r = copy.deepcopy(base)
            for k in ('notes', 'annotations', 'vectors', 'choreography'):
                r.pop(k, None)
            seg = montage.compute(r)
            self.assertGreater(seg['duration'], 0, f'{f.name} : montage vide')
            choregraphie.actualiser(r, None)  # sans choregraphie : rien n'est cree
            sobriete.relire(r, tout=False)
            if base.get('template') and not base.get('kind') in ('immobilier', 'evenement'):
                reelmod.apply_template(r, base['template'])
            for k in ('notes', 'annotations', 'vectors', 'choreography'):
                self.assertNotIn(k, r, f'{f.relative_to(FIX)} : {k} ajoute a un ancien reel')
            self.assertEqual(montage.compute(r)['duration'] > 0, True)
            vus += 1
        self.assertGreaterEqual(vus, 5)
        print(f'  {vus} anciens reels : passes executees, aucun champ V2 ajoute')

    # 8. notes et dessins : meme image apres fermeture/reouverture (fichier relu), apres toutes les passes automatiques et
    #    les changements de style ; dessins alignes dans les 4 formats (calcul de timeline.ts lui-meme, par Node)
    def test_8_ancres(self):
        avant = BAC / 'reel-complet.json'
        apres = BAC / 'reel-apres-passes.json'
        if not apres.exists():
            self.test_2_passe_ia_et_styles()
        out = subprocess.run(['node', str(Path(__file__).resolve().parent / 'ancres.mjs'), str(avant), str(apres)], capture_output=True,
                             text=True, encoding='utf-8', timeout=120)
        self.assertEqual(out.returncode, 0, out.stderr[-800:])
        res = json.loads(out.stdout.strip().splitlines()[-1])
        for n in res['notes']:
            self.assertIsNotNone(n['avant'], f'note {n["id"]} : ancre introuvable')
            self.assertEqual(n['avant'], n['relu'], f'note {n["id"]} : autre image apres reouverture du fichier')
            self.assertEqual(n['avant'], n['apres'], f'note {n["id"]} : autre image apres les passes et les styles')
        for fmt, e in res['alignement'].items():
            self.assertLess(e, 1e-6, f'{fmt} : dessin decale de {e} (repere de la prise)')
        self.assertEqual(set(res['alignement']), {'9:16', '16:9', '4:5', '1:1'})
        print(f"  notes : images {[n['avant'] for n in res['notes']]} identiques apres reouverture et apres les passes ; "
              f"dessins alignes en 4 formats (ecart max {max(res['alignement'].values()):.1e}) ; 1er point du 1er dessin dans l'image : {res['pixel']}")

    # 9. controle final : le test n'a rien ecrit dans ses donnees figees (fixtures/projects)
    def test_9_projects_intact(self):
        apres = empreinte_projets()
        change = sorted(k for k in set(AVANT_PROJETS) | set(apres) if AVANT_PROJETS.get(k) != apres.get(k))
        self.assertFalse(change, f'donnees figees fixtures/projects modifiees pendant le test : {change[:8]}')


if __name__ == '__main__':
    print(f'Bac : {BAC}')
    unittest.main(verbosity=2)
