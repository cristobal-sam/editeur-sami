"""Tests des corrections generales demandees par le juge independant n° 1 (2 octobre 2026), depuis engine/ :
    python ..\\docs\\qualite-2026-09-30\\tests\\test_juge1.py

Donnees FIGEES seulement (jamais un projet vivant de l'utilisateur) :
- docs/direction-creative-v2/tests/fixtures/projects/script1/reels/script.json (copie du reel de Video 1) ;
- docs/qualite-2026-09-30/tests/cas/juge1-p3d.json (meme video en Tech 3D cinematique, detourage RVM et analyse du decor).

Couvre : relecture d'orthographe (é / er / ez, accords, « Pi »), libelles de parcours a l'infinitif, notification du fait dit
plutot qu'un tableau generique pendant le probleme (teinte chaude), offre affichee quand elle est dite, objet fixe du decor
(table) detecte dans la carte de presence, controles nouveaux (parole sans sous-titres, zone haute 9:16, orthographe des
interfaces)."""
import copy
import json
import os
import sys
from pathlib import Path

os.environ['EDITEUR_LLM'] = '0'  # regles seules : resultat reproductible
ICI = Path(__file__).resolve().parent
ROOT = ICI.parents[2]
sys.path.insert(0, str(ROOT / 'engine'))

import numpy as np  # noqa: E402

from editeur import controle, detourage, galerie, orthographe, reel as reelmod  # noqa: E402
# Rushs (2 oct. 2026, integration Claude) : le lot « Lot 2026-09-30 10h51 » est parti a la corbeille (Video 1 supprimee
# puis redeposee) ; un rush absent des cas figes est lu dans la corbeille, en lecture seule (rushs.py)
from rushs import retrouver  # noqa: E402

FIXTURE = ROOT / 'docs/direction-creative-v2/tests/fixtures/projects/script1/reels/script.json'
P3D = ICI / 'cas/juge1-p3d.json'
resultats = []


def verifier(nom, ok, detail=''):
    resultats.append(bool(ok))
    print(('OK    ' if ok else 'ECHEC ') + nom + (f' — {detail}' if detail else ''))


def mots(texte):
    return [{'w': x, 'start': i * .3, 'end': i * .3 + .25, 'hl': False, 'hide': False} for i, x in enumerate(texte.split())]


def texte(ws):
    return ' '.join(w['w'] for w in ws)


def cas_orthographe():
    base = json.loads(FIXTURE.read_text(encoding='utf-8'))
    r = copy.deepcopy(base)
    ch = orthographe.corriger(r)
    vu = {(c['avant'], c['apres']) for c in ch}
    attendu = {('closé', 'closés'), ('Pi', 'Puis'), ('éduqué', 'éduquer'), ('transférez', 'transférer'), ('appuyer', 'appuyez')}
    verifier('orthographe : les fautes de la transcription de Vidéo 1 sont corrigées', attendu <= vu, str(sorted(vu)))
    # temps des mots intacts, texte d'origine garde
    same = all(w['start'] == w0['start'] and w['end'] == w0['end'] for c, c0 in zip(r['clips'], base['clips']) for w, w0 in zip(c['words'], c0['words']))
    asr = [w for c in r['clips'] for w in c['words'] if 'asr' in w]
    verifier('orthographe : temps des mots inchangés, texte d’origine gardé (asr)', same and len(asr) == len(ch), f'{len(asr)} mots')
    # plan verrouille : jamais touche
    r2 = copy.deepcopy(base)
    for c in r2['clips']:
        c['locked'] = True
    verifier('orthographe : plan verrouillé jamais touché', orthographe.corriger(r2) == [])
    # phrases justes : rien ne change (noms en -é, infinitif sujet, nom propre, « de la journée »)
    justes = ['Pour la société de qualité, vous allez payer.', 'Appeler un lead, ça prend du temps.', 'Le café est chez Martinez.',
              'Un employé de la journée.', 'Vous avez appelé le client.', 'Il faut le faire avant de partir.', 'Le lead est qualifié.']
    faux = []
    for t in justes:
        ws = mots(t)
        if orthographe.corriger_mots(ws, 'fr', True):
            faux.append(texte(ws))
    verifier('orthographe : aucune fausse correction sur des phrases justes', not faux, '; '.join(faux))
    cas = {'avant de vous le transférez': 'avant de vous le transférer', 'vous pouvez appelez vos leads': 'vous pouvez appeler vos leads',
           'Si vous hésitez, cliquez sur le lien.': 'Si vous hésitez, cliquez sur le lien.', 'Les ventes sont closé.': 'Les ventes sont closés.',
           'Merci. alors on commence.': 'Merci. Alors on commence.'}
    mauvais = []
    for a, b in cas.items():
        ws = mots(a)
        orthographe.corriger_mots(ws, 'fr', True)
        if texte(ws) != b:
            mauvais.append(f'{a} -> {texte(ws)}')
    verifier('orthographe : homophones é / er / ez et accords corrigés', not mauvais, '; '.join(mauvais))
    en = mots('please call me and transferez nothing')
    verifier('orthographe : jamais sur une vidéo en anglais', orthographe.corriger_mots(en, 'en') == [])
    inf = {'Transférez': 'Transférer', 'éduqué': 'Éduquer', 'Répondre': 'Répondre', 'qualifiez': 'Qualifier', 'appelé': 'Appeler'}
    verifier('parcours : verbes à l’infinitif', all(orthographe.infinitif(a) == b for a, b in inf.items()),
             str({a: orthographe.infinitif(a) for a in inf}))


def cas_galerie():
    r = json.loads(FIXTURE.read_text(encoding='utf-8'))
    orthographe.corriger(r)
    reelmod.apply_template(r, 'produit-3d')
    sc = [s for s in r.get('styleScenes') or [] if not s.get('hidden')]
    flows = [s for s in sc if s['kind'] == 'flow']
    labels = [[s['text']] + [x for x in str(s.get('secondary') or '').split('|') if x] for s in flows]
    verifier('galerie : parcours de 2 étapes, à l’infinitif', flows and all(len(l) == 2 and all(orthographe.infinitif(x) == x for x in l) for l in labels),
             str(labels))
    att = [s for s in sc if s['kind'] == 'notification' and 'attente' in s['text']]
    dash = [s for s in sc if s['kind'] == 'dashboard' and s['clip'] == 'c2']
    verifier('galerie : « Lead en attente depuis 3 h » au lieu du tableau « Lead / Appelé »', att and not dash,
             f"{[s['text'] for s in att]} / tableaux {[s['text'] for s in dash]}")
    verifier('galerie : le problème vécu prend la teinte chaude', att and all(s['color'] == galerie.CHAUD for s in att))
    ok_notif = [s for s in sc if s['kind'] == 'notification' and 'attente' not in s['text']]
    verifier('galerie : une notification de succès garde la couleur d’accent', all(s['color'] != galerie.CHAUD for s in ok_notif),
             str([(s['text'], s['color']) for s in ok_notif]))
    ctas = [s for s in sc if s['kind'] == 'cta']
    last = ctas[-1] if ctas else {}
    clip = next((c for c in r['clips'] if c['id'] == last.get('clip')), None)
    # 2 oct. 2026 (finition après le juge n° 3) : deux demandes proches = UN bouton tenu de la 1re demande à la fin ; l'offre
    # dite entre alors au-dessus de lui sur son mot (champ offer, après le bouton) au lieu d'ouvrir un 2e bouton (champ lead)
    mot = last.get('offer') if isinstance(last.get('offer'), int) else last.get('lead')
    lead_w = clip['words'][mot]['w'] if clip and isinstance(mot, int) else None
    verifier('galerie : l’offre dite entre sur son mot (« gratuitement »)', last.get('secondary') == '1 semaine gratuite'
             and lead_w and lead_w.lower().startswith('gratuit'), f"{last.get('secondary')} / {lead_w}")


def cas_occultant():
    h, w = 480, 270
    P = np.zeros((h, w), np.float32)
    P[60:, 70:220] = 1.0  # buste
    yy, xx = np.mgrid[0:h, 0:w]
    bord = (yy - 330) * 130 - (xx - 0) * 150  # droite de (0, 330) a (130, 480)
    P[(bord > 0) & (xx < 130)] = 0.0  # table au premier plan : le corps s'arrete net sur la diagonale
    P[(yy > 300) & (xx < 140) & (bord <= 0) & (xx > 20)] = 1.0  # le bras descend jusqu'a la table
    poly = detourage.occultant(P)
    verifier('détourage : table au premier plan trouvée (coin bas gauche)', poly is not None and min(p[0] for p in poly) == 0
             and max(p[1] for p in poly) == 1.0, str(poly))
    Q = np.zeros((h, w), np.float32)
    Q[60:, 70:220] = 1.0
    verifier('détourage : bords verticaux d’un buste immobile = pas d’objet', detourage.occultant(Q) is None)
    S = np.zeros((h, w), np.float32)
    S[60:, 70:220] = 1.0
    S[300:, 20:70] = np.linspace(0, 1, 50)[None, :] * 0.8  # bras qui bouge : bord flou
    verifier('détourage : bord flou (bras qui bouge) = pas d’objet', detourage.occultant(S) is None)


def cas_controle():
    if not P3D.exists():
        verifier('contrôle : cas Tech 3D figé présent', False, str(P3D))
        return
    r = retrouver(json.loads(P3D.read_text(encoding='utf-8')))
    res = controle.controler(r, profond=False)
    codes = {c['code']: c for c in res['constats']}
    imp = [c for c in res['constats'] if c['gravite'] in ('bloquant', 'important')]
    verifier('contrôle : Tech 3D corrigé sans bloquant ni important', not imp, '; '.join(c['message'] for c in imp))
    verifier('contrôle : sous-titres gardés pendant les interfaces (< 15 % de la parole sans texte)',
             'parole-sans-texte' not in codes or codes['parole-sans-texte']['gravite'] == 'conseil',
             codes.get('parole-sans-texte', {}).get('message', 'aucun constat'))
    # interface posee a la main tout en haut (5 %) : zone de la barre du haut
    m = copy.deepcopy(r)
    s = next(x for x in m['styleScenes'] if x['kind'] == 'notification' and not x.get('hidden'))
    s.update({'manual': True, 'y': 0.06, 'scale': 1})
    res2 = controle.controler(m, profond=False)
    zh = [c for c in res2['constats'] if c['code'] == 'zone-sure' and c['gravite'] == 'important']
    verifier('contrôle : interface sous la barre du haut (9:16) signalée', zh, '; '.join(c['message'] for c in res2['constats'] if c['code'] == 'zone-sure'))
    # faute dans un parcours
    m2 = copy.deepcopy(r)
    f = next(x for x in m2['styleScenes'] if x['kind'] == 'flow')
    f['secondary'] = 'Transférez'
    res3 = controle.controler(m2, profond=False)
    verifier('contrôle : faute dans une interface signalée', any(c['code'] == 'orthographe' and c['gravite'] == 'important' for c in res3['constats']))
    # ancienne regle (sous-titres masques pendant chaque interface) : signalee
    m3 = copy.deepcopy(r)
    for x in m3['styleScenes']:
        x.update({'manual': True, 'y': 0.69, 'duration': 6})
    res4 = controle.controler(m3, profond=False)
    verifier('contrôle : parole sans sous-titres signalée', any(c['code'] == 'parole-sans-texte' for c in res4['constats']))


cas_orthographe()
cas_galerie()
cas_occultant()
cas_controle()
print(f'\n{sum(resultats)}/{len(resultats)} vérifications réussies')
sys.exit(0 if all(resultats) else 1)
