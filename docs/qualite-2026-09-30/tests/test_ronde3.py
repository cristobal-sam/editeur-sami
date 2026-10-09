"""Ronde 3 (02/10/2026) — moteur : listes enumerees, offre dite sur le bouton final, accroche du plan creatif,
bouton garde sur la derniere phrase d'appel a l'action, budget du style Tech 3D.
Depuis engine/ : python ..\\docs\\qualite-2026-09-30\\tests\\test_ronde3.py   (copie figee de Video 1, sans IA locale)"""
import copy
import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
os.environ['EDITEUR_LLM'] = '0'  # regles seules : resultat stable, aucun serveur d'IA lance
ICI = Path(__file__).resolve().parent
ROOT = ICI.parents[2]
sys.path.insert(0, str(ROOT / 'engine'))
from editeur import galerie, reel as R, sobriete  # noqa: E402

OK = KO = 0


def verifier(nom, cond, detail=''):
    global OK, KO
    OK, KO = OK + bool(cond), KO + (not cond)
    print(('OK    ' if cond else 'ECHEC ') + nom + (f' — {detail}' if detail else ''))


def mots(phrase):
    return {'words': [{'w': w, 'start': i * .3, 'end': i * .3 + .25} for i, w in enumerate(phrase.split())]}


# 1. Enumerations : ce qui est dit, rien d'invente ; prudent quand ce n'est pas une liste
cas = {
    "Ça veut dire un salaire au complet, des avantages sociaux, des vacances et des journées de maladie à payer.":
        ['Salaire', 'Avantages sociaux', 'Vacances', 'Journées de maladie'],
    "On vous offre plus de clients, plus de ventes et plus de temps libre.": ['Plus de clients', 'Plus de ventes', 'Plus de temps'],
    "Le lead, la réponse et le closing sont rapides.": ['Lead', 'Réponse', 'Closing'],
    "C'est simple, rapide et efficace.": None,
    "Un salaire, des vacances.": None,
    "Plus vous prenez de temps à appeler un lead, plus vous avez de chances que votre concurrent le close.": None,
}
for phrase, attendu in cas.items():
    trouve = galerie.enumerations(mots(phrase))
    textes = trouve[0][1] if trouve else None
    verifier(f'liste : « {phrase[:48]}… »', textes == attendu, str(textes))
verifier('liste (anglais) : more leads, more calls and more sales',
         [t for _, t in galerie.enumerations(mots('You get more leads, more calls and more sales.'), 'en')] == [['More leads', 'More calls', 'More sales']])

# 2. Offre dite avant le bouton
c = mots("Et pour que vous puissiez l'expérimenter sans risque, on place notre setter gratuitement dans votre entreprise "
         "pendant une semaine complète, alors appuyer sur le bouton « En savoir plus »")
i = next(k for k, w in enumerate(c['words']) if w['w'] == 'bouton')
verifier('offre : « gratuitement … une semaine » -> « 1 semaine gratuite »', galerie.offre_dite(c, i) == '1 semaine gratuite', str(galerie.offre_dite(c, i)))
c2 = mots("pendant une semaine complète, alors appuyer sur le bouton")
verifier('offre : une durée sans gratuité -> rien', galerie.offre_dite(c2, len(c2['words']) - 1) is None)
c3 = mots("on vous offre trois mois gratuits, cliquez sur le bouton")
verifier('offre : « trois mois gratuits » -> « 3 mois gratuits »', galerie.offre_dite(c3, len(c3['words']) - 1) == '3 mois gratuits', str(galerie.offre_dite(c3, len(c3['words']) - 1)))

# 3. Video 1 (copie figee) en Tech 3D : liste, notification apres l'accroche, deux boutons dont le dernier porte l'offre
base = json.loads((ROOT / 'docs/direction-creative-v2/tests/fixtures/projects/script1/reels/script.json').read_text(encoding='utf-8'))
r = copy.deepcopy(base)
R.apply_template(r, 'produit-3d')
sc = [s for s in r.get('styleScenes') or [] if not s.get('hidden')]
kinds = [s['kind'] for s in sc]
liste = next((s for s in sc if s['kind'] == 'list'), None)
verifier('Vidéo 1 : la liste des coûts est créée et visible', bool(liste) and liste['text'] == 'Salaire' and len(liste.get('items') or []) == 4,
         str(liste and (liste['text'], liste['secondary'])))
verifier('Vidéo 1 : la liste du problème est en teinte chaude', bool(liste) and liste['color'].upper() == '#FF7A66' and liste.get('creativeRole') == 'probleme')
ctas = [s for s in sc if s['kind'] == 'cta']
# 2 oct. 2026 (finition après le juge n° 3) : les deux demandes (9 s d'écart) donnent UN bouton tenu de la 1re demande à la fin
# (il ne sort plus pour revenir) ; l'offre dite entre au-dessus de lui sur son mot
_t = galerie._times(r)
_fin = max(_t.values())
verifier('Vidéo 1 : un bouton de la première demande jusqu’à la fin', len(ctas) == 1
         and _t[(ctas[0]['clip'], ctas[0]['index'])] + ctas[0]['duration'] >= _fin - 0.5, str([(s['index'], s['secondary'], s.get('duration')) for s in ctas]))
verifier('Vidéo 1 : le dernier bouton porte l’offre dite', bool(ctas) and ctas[-1]['secondary'] == '1 semaine gratuite')
times = galerie._times(r)
accroche = max(b['end'] for b in r['creativePlan']['beats'] if b['role'] == 'accroche')
avant = [s for s in r.get('styleScenes') or [] if times.get((s['clip'], s['index']), 99) < accroche]
verifier('Vidéo 1 : aucune interface créée pendant l’accroche du plan créatif', not avant, str([(s['kind'], s['text']) for s in avant]))
verifier('Vidéo 1 : relecture de sobriété sans retrait (budget du style Tech 3D)', not (r.get('sobriete') or {}).get('retires'),
         str((r.get('sobriete') or {}).get('retires')))
verifier('Vidéo 1 : au plus un écran toutes les ~6 s', all(
    abs(times[(a['clip'], a['index'])] - times[(b['clip'], b['index'])]) >= 4 for k, a in enumerate(sc) for b in sc[k + 1:]))

# 3 bis. Controle (passe JSON) de ce montage : le bouton redit a chaque demande n'est pas un « message repete » ; aucun
# passage fige de plus de 6 s, aucun probleme bloquant ou important
from editeur import controle  # noqa: E402
sortie = ROOT / 'runtime' / 'cache' / 'tmp' / 'test-ronde3-controle'
sortie.mkdir(parents=True, exist_ok=True)
rc = controle.controler(copy.deepcopy(r), sortie=sortie)
codes = {c['code']: c for c in rc['constats']}
verifier('contrôle : bouton redit avec la voix = pas un message répété', 'message-repete' not in codes)
verifier('contrôle : plus de cadre figé', 'cadre-fige' not in codes, (codes.get('cadre-fige') or {}).get('message', ''))
# la copie figee garde l'ancien detourage MediaPipe (signale a juste titre) : hors de ce test
graves = [c for c in rc['constats'] if c['gravite'] != 'conseil' and not c['code'].startswith('detourage')]
verifier('contrôle : aucun bloquant ni important (hors ancien détourage de la copie figée)', not graves,
         f"note {rc['note']} {rc['compte']} " + ' | '.join(c['code'] + ' : ' + c['message'][:140] for c in rc['constats'] if c['gravite'] != 'conseil'))
verifier('contrôle : sous-titres du studio au calcul du rendu (≥ 62 px)', not any(c['code'] == 'texte-petit' and 'Sous-titres' in c['message'] for c in rc['constats']))
r4 = copy.deepcopy(r)
n = next(s for s in r4['styleScenes'] if s['kind'] == 'notification')
r4['styleScenes'].append({**copy.deepcopy(n), 'id': 'test-doublon', 'index': n['index'] + 40 if n['index'] + 40 < len(next(c for c in r4['clips'] if c['id'] == n['clip'])['words']) else 0, 'hidden': False})
rc4 = controle.controler(r4, sortie=sortie)
verifier('contrôle : une carte NON redite par la voix et affichée 2 fois reste signalée', any(c['code'] == 'message-repete' for c in rc4['constats']))

# 4. Sobriete : le bouton reste sur la derniere phrase d'appel a l'action ; une autre scene y est raccourcie, pas retiree
r2 = copy.deepcopy(r)
dernier = ctas[-1] if ctas else None
autre = copy.deepcopy(dernier) if dernier else None
if autre:
    autre.update({'id': 'test-chiffre', 'kind': 'metric', 'text': '1 semaine', 'secondary': ''})
    # meme plan, ~2,5 s avant le bouton final : deborde sur la derniere phrase
    # 2 oct. 2026 : le bouton unique est ancré sur la 1re demande ; la scène de test se place ~2,5 s avant la DERNIÈRE
    # demande dite (mot « En » du dernier « En savoir plus » du plan)
    _mots = next(c for c in r['clips'] if c['id'] == dernier['clip'])['words']
    _der = max(k for k, w in enumerate(_mots) if w['w'].strip(' «»,.').lower() == 'savoir') - 1
    autre['index'] = max(0, _der - 9)
    autre['duration'] = 4.0
    r2['styleScenes'] = [s for s in r2['styleScenes'] if s['kind'] != 'cta'] + [dernier, autre]
r3 = copy.deepcopy(r2)
rep = sobriete.relire(r2, tout=True)
gardes = {s['id']: s for s in r2['styleScenes']}
verifier('sobriété : le bouton final passe avant une autre scène trop proche', bool(dernier) and not gardes[dernier['id']].get('hidden'),
         str(rep.get('retires')))
# sans bouton final : la scene qui deborde sur la derniere phrase est raccourcie et gardee
r3['styleScenes'] = [s for s in r3['styleScenes'] if s['id'] != (dernier or {}).get('id')]
sobriete.relire(r3, tout=True)
g3 = {s['id']: s for s in r3['styleScenes']}
verifier('sobriété : la scène qui déborde sur la dernière phrase est raccourcie (pas retirée)',
         bool(autre) and not g3['test-chiffre'].get('hidden') and g3['test-chiffre']['duration'] < 4.0,
         str(g3.get('test-chiffre', {}).get('duration')))

# 5. Autres styles inchanges : pas de liste ni de second bouton hors Tech 3D
for style in ('tech-application', 'hormozi', 'editorial-cinetique'):
    r3 = copy.deepcopy(base)
    R.apply_template(r3, style)
    verifier(f'{style} : aucune scène « liste »', not any(s['kind'] == 'list' for s in r3.get('styleScenes') or []))

print(f'\n{OK}/{OK + KO} vérifications réussies')
sys.exit(1 if KO else 0)
