"""Tests des corrections generales demandees par le juge independant n° 2 (2 octobre 2026), depuis engine/ :
    python ..\\docs\\qualite-2026-09-30\\tests\\test_juge2.py

Donnees FIGEES seulement (jamais un projet vivant de l'utilisateur) :
- docs/qualite-2026-09-30/tests/cas/juge2-p3d.json (Video 1 en Tech 3D cinematique apres ce cycle) ;
- images de detourage SYNTHETIQUES ecrites dans runtime/cache/tmp/test-juge2-<pid>/ (haut de la tete, table qui derive).

Couvre : accord du nom avec son determinant (« de la publicités »), fin tenue, badge de preuve dite, bande sombre au bord
de l'image (controle), recul de camera repete (controle), haut reel de la tete et table suivie image par image (detourage)."""
import copy
import json
import os
import shutil
import sys
from pathlib import Path

os.environ['EDITEUR_LLM'] = '0'  # regles seules : resultat reproductible
ICI = Path(__file__).resolve().parent
ROOT = ICI.parents[2]
sys.path.insert(0, str(ROOT / 'engine'))

import numpy as np  # noqa: E402

from editeur import controle, detourage, galerie, orthographe, reel as reelmod  # noqa: E402

P3D = ICI / 'cas/juge2-p3d.json'
TMP = ROOT / 'runtime/cache/tmp' / f'test-juge2-{os.getpid()}'
resultats = []


def verifier(nom, ok, detail=''):
    resultats.append(bool(ok))
    print(('OK    ' if ok else 'ECHEC ') + nom + (f' — {detail}' if detail else ''))


def mots(texte):
    return [{'w': x, 'start': i * .3, 'end': i * .3 + .25, 'hl': False, 'hide': False} for i, x in enumerate(texte.split())]


def texte(ws):
    return ' '.join(w['w'] for w in ws)


def cas_orthographe():
    cas = {'leads avec de la publicités, ça vous concerne': 'leads avec de la publicité, ça vous concerne',
           'chaque leads reçoit une réponse': 'chaque lead reçoit une réponse', "pour l'entreprises": "pour l'entreprise",
           'votre entreprises grandit': 'votre entreprise grandit', 'vos lead attendent': 'vos leads attendent',
           'des publicité ici': 'des publicités ici'}
    mauvais = []
    for a, b in cas.items():
        ws = mots(a)
        orthographe.corriger_mots(ws, 'fr', True)
        if texte(ws) != b:
            mauvais.append(f'{a} -> {texte(ws)}')
    verifier('accord avec le déterminant : singulier après « de la / chaque / l’ / votre », pluriel après « vos / des »', not mauvais, '; '.join(mauvais))
    justes = ['tu la prends maintenant', 'je le fais souvent', 'vous le faites bien', 'le temps de répondre', 'au cours de la semaine',
              'cinq fois moins cher', 'des fois ça arrive', 'un des leads', 'un sens unique', 'le gars du bureau', 'dès maintenant',
              'on les appelle', 'au moins trois', 'un business rentable', 'ce mois-ci', "on l'appelles"]
    faux = []
    for t in justes:
        ws = mots(t)
        if any(r == 'accord avec le déterminant' for _, _, _, r in orthographe.corriger_mots(ws, 'fr', True)):
            faux.append(texte(ws))
    verifier('accord avec le déterminant : aucune fausse correction (pronoms, invariables, nombres)', not faux, '; '.join(faux))
    verifier('contrôle : « de la publicités » vu par la vérification d’orthographe',
             any(b == 'publicité,' for _, b, _ in orthographe.verifier('avec de la publicités, ça')))


def cas_fin_tenue():
    r = json.loads(P3D.read_text(encoding='utf-8'))
    c = r['clips'][-1]
    fin = max(w['end'] for w in c['words'] if not w.get('cut'))
    verifier('fin tenue (donnée figée) : la dernière prise continue après le dernier mot', c['out'] - fin >= 0.6, f"{c['out'] - fin:.2f} s")
    r2 = copy.deepcopy(r)
    r2['clips'][-1]['out'] = round(fin + .2, 3)
    res = reelmod.fin_tenue(r2)
    verifier('fin tenue : 0,8 s ajoutée si la prise continue sans parole', res and abs(r2['clips'][-1]['out'] - min(fin + .8, r2['sources'][c['source']]['duration'] - .05)) < 1e-6,
             str(res))
    r3 = copy.deepcopy(r)
    r3['clips'][-1]['out'] = round(fin + .2, 3)
    r3['clips'][-1]['locked'] = True
    verifier('fin tenue : jamais sur un plan verrouillé', reelmod.fin_tenue(r3) is None)
    r4 = copy.deepcopy(r)
    r4['clips'][-1]['out'] = round(fin + .2, 3)
    r4['sources'][c['source']] = {**r4['sources'][c['source']], 'duration': fin + .3}
    verifier('fin tenue : jamais au-delà de la prise', reelmod.fin_tenue(r4) is None)


def cas_badge():
    r = json.loads(P3D.read_text(encoding='utf-8'))
    t = galerie._times(r)
    h = galerie._hook_end(r, t)
    b = galerie._claim_scenes(r, t, h, 'fr')
    verifier('badge de preuve : « Formé par nos soins » trouvé, texte dit tel quel', any(x['text'] == 'Formé par nos soins' for x in b), str([x['text'] for x in b]))
    verifier('badge de preuve : liste d’un élément, jamais sur l’accroche', all(x['kind'] == 'list' and x.get('badge') and t[(x['clip'], x['index'])] >= h for x in b))
    ws = {'id': 'z', 'words': mots('je vous garantis un service rapide')}
    r2 = {'clips': [ws], 'style': {'highlight': '#fff'}, 'creativePlan': {}}
    verifier('badge de preuve : jamais un mot seul (« garantis »)', not galerie._claim_scenes(r2, {('z', i): 9 + i for i in range(6)}, 0, 'fr'))


def cas_bord():
    Y = np.full((1920, 1080), 26.0, np.float32)
    Y[:, :] += np.linspace(0, 8, 1080)[None, :]
    Y[:20] = 5.0
    b = controle.bande_bord(Y)
    verifier('contrôle : bande noire à bord net en haut détectée (20 px)', b and b[0][0] == 'haut' and b[0][1] == 20, str(b))
    Z = np.tile(np.linspace(4, 30, 1920)[:, None], (1, 1080)).astype(np.float32)  # fond sombre qui se dégrade doucement
    verifier('contrôle : un fond sombre en dégradé n’est pas une bande', not controle.bande_bord(Z), str(controle.bande_bord(Z)))
    verifier('contrôle : image uniformément noire (fondu) : pas une bande', not controle.bande_bord(np.zeros((1920, 1080), np.float32)))


def cas_reculs():
    class Ctx:
        pass
    ctx = Ctx()
    frames = []
    for i in range(300):
        t = i * .1
        s = 1.25
        for a in (5.0, 15.0, 25.0):  # trois reculs de 1,25 a 1,0 en 0,8 s
            if a <= t < a + .8:
                s = 1.25 - .25 * (t - a) / .8
            elif a + .8 <= t < a + 3:
                s = 1.0
        frames.append({'t': t, 'view': {'scale': s}})
    ctx.tl = {'frames': frames, 'video': [{'out_start': 0}]}
    r = controle._reculs_camera(ctx)
    verifier('contrôle : reculs de caméra en glissant répétés signalés', r and r[0]['code'] == 'recul-camera', r[0]['message'] if r else '')
    for f in frames:  # les memes changements d'un coup (relance) : rien
        f['view']['scale'] = 1.0 if any(a <= f['t'] < a + 3 for a in (5.0, 15.0, 25.0)) else 1.25
    verifier('contrôle : changement de cadre d’un coup (relance) non signalé', not controle._reculs_camera(ctx))


def _ecrire(dossier, alphas):
    import cv2
    dossier.mkdir(parents=True, exist_ok=True)
    for i, a in enumerate(alphas):
        im = np.zeros((480, 270, 4), np.uint8)
        im[..., :3] = 120
        im[..., 3] = a
        cv2.imencode('.webp', im, [cv2.IMWRITE_WEBP_QUALITY, 101])[1].tofile(str(dossier / f'{i:05d}.webp'))


def cas_detourage():
    import cv2
    try:
        # personne : tete ronde dont le haut est a y = 100 + i (px de 480), buste ; table qui derive en bas a gauche
        alphas, pistes = [], []
        for i in range(60):
            a = np.zeros((480, 270), np.uint8)
            cv2.ellipse(a, (135, 150 + i), (40, 50), 0, 0, 360, 255, -1)
            cv2.rectangle(a, (60, 200 + i), (210, 479), 255, -1)
            cv2.rectangle(a, (10, 330), (80, 479), 255, -1)  # bras pose sur la table
            y0 = 340 + i  # bord de la table : droite de pente 1 depuis (0, y0), elle descend de 1 px par image (camera qui derive)
            pts = np.array([[0, y0], [480 - y0, 480], [0, 480]], np.int32)
            cv2.fillPoly(a, [pts], 0)
            alphas.append(a)
            pistes.append(y0 / 480)
        d = TMP / 'synthetique'
        _ecrire(d, alphas)
        doc = {'frames': str(d.relative_to(ROOT)).replace('\\', '/'), 'start': 2.0, 'fps': 30, 'count': 60}
        src = {'track': [[2.0 + k / 10, .5, .31 + k / 300, .3] for k in range(25)]}
        h = detourage.tete(doc, src, 2.0, 30)
        attendu = [(100 + k) / 480 for k in range(0, 60, 3)]
        ecart = max(abs(p[1] - e) for p, e in zip(h, attendu)) if h else 1
        verifier('détourage : haut réel de la tête lu dans l’alpha (à 6 px près sur 480) avec la largeur du visage', h and ecart <= 6 / 480 and len(h[0]) == 3,
                 f'écart {ecart * 480:.1f} px')
        table = [[.5185, 1.0], [0.0, 1.0], [0.0, .7083]]  # table vue nettement dans une autre prise (meme pente)
        res = detourage.occultant_confirme(doc, table)
        ok = res and res.get('track') and len(res['track']) >= 10
        derive = res['track'][-1][2] - res['track'][0][2] if ok else 0
        verifier('détourage : table d’une autre prise reprise et suivie quand la caméra dérive', ok and derive > .05, f"{res and res['poly']} ; dérive {derive:.3f}")
        sans = [np.where(np.arange(480)[:, None] > 470, 0, a).astype(np.uint8) for a in alphas]  # pas de coupe droite : rien
        d2 = TMP / 'sans-table'
        for k in range(len(sans)):
            cv2.rectangle(sans[k], (0, 300), (90, 479), 255, -1)
        _ecrire(d2, sans)
        doc2 = {**doc, 'frames': str(d2.relative_to(ROOT)).replace('\\', '/')}
        verifier('détourage : sans coupe droite de la personne, aucune table inventée', detourage.occultant_confirme(doc2, table) is None)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)


cas_orthographe()
cas_fin_tenue()
cas_badge()
cas_bord()
cas_reculs()
cas_detourage()
print(f'\n{sum(resultats)}/{len(resultats)} vérifications réussies')
sys.exit(0 if all(resultats) else 1)
