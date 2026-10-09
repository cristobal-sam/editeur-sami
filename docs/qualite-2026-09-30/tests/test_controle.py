"""Tests du controle qualite (engine/editeur/controle.py), uniquement sur des COPIES.

    cd D:\\Tools\\editeur_sami\\engine
    ..\\runtime\\venv\\Scripts\\python.exe ..\\docs\\qualite-2026-09-30\\tests\\test_controle.py [--rendre] [--vite]

Cas :
  1. apercu Tech 3D cinematique (copie du job de l'apercu + sa video 28-42 s) : les defauts connus DOIVENT sortir ;
  2. reel actuel de Video 1 (copie de projects/script1/reels/script.json), passe JSON ;
  3. cas propre (reel simple sans habillage) : AUCUN probleme, en JSON et sur un rendu de 4 s ;
  4. mutations du cas propre (un defaut injecte a la fois) : chaque defaut doit etre trouve.
--rendre : refait le rendu de 4 s du cas propre (remotion/render.mjs) s'il est absent.
--vite   : saute les passes video."""
import copy
import glob
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
ROOT = ICI.parents[2]
sys.path.insert(0, str(ROOT / 'engine'))
from editeur import controle  # noqa: E402
# Rushs (2 oct. 2026, integration Claude) : le lot « Lot 2026-09-30 10h51 » est parti a la corbeille (Video 1 supprimee
# puis redeposee) ; un rush absent des cas figes est lu dans la corbeille, en lecture seule (rushs.py)
from rushs import retrouver  # noqa: E402
_controler = controle.controler
controle.controler = lambda reel, *a, **k: _controler(retrouver(reel), *a, **k)

APERCU = ICI / 'cas/apercu-premium-28-42-copie.mp4'   # copie de runtime/cache/tmp/apercu-premium-8cCBmz/premium-28-42.mp4
RESULTATS = ICI / 'resultats'
bilan = []


def codes(r, gravites=('bloquant', 'important', 'conseil')):
    return [c['code'] for c in r['constats'] if c['gravite'] in gravites]


def verifier(nom, ok, detail=''):
    bilan.append({'test': nom, 'ok': bool(ok), 'detail': detail})
    print(('OK   ' if ok else 'ECHEC') + f' {nom}' + (f' — {detail}' if detail else ''))


def lancer(reel, nom, video=None, debut=0.0):
    sortie = RESULTATS / nom
    sortie.mkdir(parents=True, exist_ok=True)
    r = controle.controler(reel, video=video, debut=debut, sortie=sortie)
    (sortie / 'controle.json').write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
    (sortie / 'controle.txt').write_text(controle.texte_rapport(r), encoding='utf-8')
    return r


def cas_apercu(vite):
    reel = json.loads((ICI / 'cas/apercu-premium-job-copie.json').read_text(encoding='utf-8'))['reel']
    video = APERCU if (APERCU.exists() and not vite) else None
    r = lancer(reel, 'apercu-tech3d' + ('-video' if video else '-json'), video, 28.0)
    c = codes(r)
    txt = ' | '.join(x['message'] for x in r['constats'])
    # Attentes mises a jour le 01/10/2026 : le controle suit le rendu ACTUEL (design.tsx / Reel.tsx / graphics.tsx). Le
    # studio n'a plus de bandeau « VIDÉO 1 » ni de minuteur, ses interfaces sont grandes (verre a liseré clair) et sa
    # camera (studioView) pousse sur les temps forts : ces trois defauts de l'ancien apercu ne sont plus produits par le
    # rendu, donc plus signales. Ils restaient vrais sur l'ancienne video (aucune lecture de texte a l'image : pas d'OCR).
    verifier('apercu : plus de « VIDÉO 1 » ni de minuteur (bandeau technique retiré du studio)',
             not any(x['code'] == 'texte-interne' and ('VIDÉO 1' in x['message'] or 'compteur' in x['message']) for x in r['constats']))
    verifier('apercu : détourage basse résolution (JSON)', 'detourage-basse-resolution' in c)
    verifier('apercu : sous-titres petits (style de l’apercu : 58 px réduits pour tenir sur une ligne)',
             any(x['code'] == 'texte-petit' and 'Sous-titres' in x['message'] for x in r['constats']))
    verifier('apercu : interfaces du studio assez grandes (plus de « petit texte » sur les cartes)',
             not any(x['code'] == 'texte-petit' and 'carte' in x['message'] for x in r['constats']),
             '; '.join(x['message'] for x in r['constats'] if x['code'] == 'texte-petit'))
    # 02/10/2026 (ronde 3) : la camera du studio fait des relances de cadre (coupe franche = autre valeur de plan, « punch-in »
    # sur un debut de phrase ou un mot fort) : ce montage n'a plus de passage fige de plus de 6 s
    verifier('apercu : plus de cadre figé (relances de cadre du studio)',
             'cadre-fige' not in c and r['mesures'].get('plus_long_plan_fixe', 99) <= 6.0, f"plus long plan fixe {r['mesures'].get('plus_long_plan_fixe')} s")
    verifier('apercu : caméra du studio = relances visibles (plus de « zoom invisible »)',
             'zoom-invisible' not in c and r['mesures'].get('mouvements_camera_studio', 0) > 0, f"{r['mesures'].get('mouvements_camera_studio')} mouvement(s) de caméra")
    verifier('apercu : carte sur l’accroche', 'accroche-couverte' in c)
    verifier('apercu : cartes de verre à liseré → pas de « carte terne » estimée', 'carte-terne' not in c)
    verifier('apercu : pas de faux « visage couvert »', 'visage-couvert' not in c and 'visage-couvert-image' not in c, txt[:0])
    if video:
        # ancienne video (rendu du 30/09, sans camera ni cartes de verre) : seules les mesures independantes de la mise en
        # page actuelle sont attendues (detourage compare au masque de reference, son)
        verifier('apercu vidéo : restes de décor du détourage', 'detourage-restes' in codes(r, ('bloquant', 'important')))
        verifier('apercu vidéo : bords flous/escalier', 'detourage-bords' in c)
        verifier('apercu vidéo : voile gris', 'detourage-voile' in c)
        verifier('apercu vidéo : pas de faux « peu lisible » sur les sous-titres', not any(x['code'] == 'lisibilite-image' for x in r['constats']))
        L = r['mesures'].get('loudness') or {}
        verifier('apercu vidéo : loudness mesurée', L.get('I') is not None, f"I {L.get('I')} LUFS, TP {L.get('TP')} dBTP")
    return r


def cas_actuel():
    reel = json.loads((ICI / 'cas/script1-script-copie.json').read_text(encoding='utf-8'))
    r = lancer(reel, 'script1-actuel-json')
    verifier('reel actuel : aucun bloquant', not codes(r, ('bloquant',)), f"note {r['note']} ; {r['compte']}")
    verifier('reel actuel : cadre figé repéré', 'cadre-fige' in codes(r))
    return r


def cas_studio():
    """Studio Tech 3D au rendu du 01/10/2026 (copie du reel de l'apercu) : marque discrete, repli du detourage, camera,
    sous-titres sur une ligne, interfaces de verre. Tout vient des memes fonctions que le rendu (pont timeline.ts)."""
    base = json.loads((ICI / 'cas/apercu-premium-job-copie.json').read_text(encoding='utf-8'))['reel']
    d = Path(tempfile.mkdtemp(prefix='controle-studio-', dir=str(ROOT / 'runtime/cache/tmp')))
    try:
        def contexte(reel):
            return controle.Contexte(reel, controle.montage_calcule(reel, d))
        # 1. marque du client sans logo : seul texte du haut du studio ; avec un logo : plus rien en haut
        reel = copy.deepcopy(base)
        reel['brand'] = {'name': 'RyuCalls'}
        ctx = contexte(reel)
        t = 20.0
        hud = [e for e in controle.visibles(ctx, t) if e['genre'] == 'hud']
        verifier('studio : marque « RyuCalls » discrète en haut (aucun titre interne, aucun minuteur)',
                 [x['texte'] for e in hud for x in e['textes']] == ['RyuCalls'] and hud[0]['textes'][0]['px'] >= .03 * ctx.u - .5)
        reel['brand']['logo'] = 'assets/clients/x/logo.png'
        verifier('studio : charte avec logo → aucun texte en haut du studio', not [e for e in controle.visibles(contexte(reel), t) if e['genre'] == 'hud'])
        # 2. camera du studio : le visage grossit avec la poussee (studioView)
        ctx = contexte(copy.deepcopy(base))
        vues = [(fr['t'], fr['view']['scale']) for fr in ctx.tl['frames'] if fr.get('view')]
        t_max, s_max = max(vues, key=lambda x: x[1]) if vues else (None, 1)
        vb = ctx.visage(t_max) if t_max is not None else None
        seg, fr = ctx.segment(t_max) if t_max is not None else (None, {})
        brut = [p for p in ctx._analyse(seg['source']) if abs(p[0] - fr['tSrc']) <= .4] if seg else []
        largeur_sans = float(np.median([p[3] for p in brut])) * fr['f']['width'] if brut else None
        verifier('studio : caméra du studio appliquée au visage (boîte agrandie)',
                 bool(vb and largeur_sans and abs((vb[2] - vb[0]) / largeur_sans - s_max) < .02 and s_max > 1.02),
                 f"échelle max {s_max:.3f} à {t_max}")
        # 3. interfaces : verre a liseré, textes >= 0,046 u (ni « petit », ni « terne »)
        cartes = [e for t in range(0, int(ctx.total)) for e in controle.visibles(ctx, float(t)) if e['id'].startswith('scene:')]
        verifier('studio : interfaces de verre à liseré, textes ≥ 0,046 u', bool(cartes) and all(e['lisere'] for e in cartes)
                 and min(x['px'] for e in cartes for x in e['textes']) >= .046 * ctx.u - .5, f"{len({e['id'] for e in cartes})} interface(s)")
        # 4. sous-titres : une ligne si possible, police resserree jusqu'a 80 % au plus
        reel = copy.deepcopy(base)
        reel['style']['size'] = 76
        ctx = contexte(reel)
        tailles = [x['px'] for p in ctx.tl['pages'] for x in controle._sous_titres(ctx, p)['textes']]
        verifier('studio : sous-titres resserrés au plus à 80 % (76 px → ≥ 60,8 px)', bool(tailles) and min(tailles) >= .8 * 76 * ctx.u / 1080 - .01,
                 f"de {min(tailles):.1f} à {max(tailles):.1f} px")
        # 5. repli du detourage (cutouts[plan].fallback, secondes dans la prise) : conseil (le rendu montre la prise d'origine),
        #    studio et marque effaces pendant la plage
        reel = copy.deepcopy(base)
        reel['brand'] = {'name': 'RyuCalls'}
        c = reel['clips'][1]
        reel['cutouts'][c['id']]['fallback'] = [[c['in'] + 2.0, c['in'] + 4.0]]
        r = controle.controler(reel)
        rep = [x for x in r['constats'] if x['code'] == 'detourage-repli']
        verifier('studio : plage de repli → « detourage-repli » simple conseil (rendu à jour)',
                 len(rep) == 1 and rep[0]['gravite'] == 'conseil' and rep[0].get('plages'), rep[0]['message'] if rep else 'absent')
        ctx = contexte(reel)
        seg0 = next(s for s in ctx.tl['video'] if s['clip'] == c['id'])
        t_rep = seg0['out_start'] + 3.0 / (seg0.get('speed') or 1)
        verifier('studio : pendant le repli, plus de studio ni de marque (prise d’origine)', ctx.repli(t_rep) > .99
                 and not [e for e in controle.visibles(ctx, t_rep) if e['genre'] == 'hud'] and ctx.repli(seg0['out_start'] + .5) == 0)
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


def propre():
    subprocess.run([sys.executable, str(ICI / 'fabriquer_cas_propre.py')], check=True, capture_output=True)
    return json.loads((ICI / 'cas/propre.json').read_text(encoding='utf-8'))


def video_propre(rendre):
    if (ICI / 'cas/propre-12-16.mp4').exists() and not rendre:
        return ICI / 'cas/propre-12-16.mp4'
    trouve = sorted(glob.glob(str(ROOT / 'runtime/cache/tmp/controle-propre-*/propre-12-16.mp4')))
    if trouve:
        return Path(trouve[-1])
    if not rendre:
        return None
    d = Path(tempfile.mkdtemp(prefix='controle-propre-', dir=str(ROOT / 'runtime/cache/tmp')))
    out = d / 'propre-12-16.mp4'
    (d / 'job.json').write_text(json.dumps({'reel': propre(), 'out': str(out), 'frameRange': [360, 479]}, ensure_ascii=False), encoding='utf-8')
    subprocess.run(['node', 'render.mjs', str(d / 'job.json')], cwd=str(ROOT / 'remotion'), check=True, capture_output=True)
    return out if out.exists() else None


# 2026-10-02 (juge 1) : deux controles nouveaux trouvent de VRAIS defauts dans ce cas « propre » (transcription non relue :
# « Pi », « appuyer » dit a « vous » ; coupes franches au meme cadre de ce montage). Ils sont verifies a part (cas_juge1) ;
# le cas propre doit rester sans AUTRE constat.
NOUVEAUX_JUGE1 = ('orthographe', 'coupe-meme-cadre')


def _hors_juge1(r):
    return {**r, 'constats': [x for x in r['constats'] if x['code'] not in NOUVEAUX_JUGE1]}


def cas_propre(vite, rendre):
    reel = propre()
    r = lancer(reel, 'propre-json')
    nouveaux = sorted({x['code'] for x in r['constats'] if x['code'] in NOUVEAUX_JUGE1})
    verifier('propre : vrais défauts du cas trouvés (orthographe, coupes au même cadre), en conseil', nouveaux == sorted(NOUVEAUX_JUGE1)
             and all(x['gravite'] == 'conseil' for x in r['constats'] if x['code'] in NOUVEAUX_JUGE1), str(nouveaux))
    r = _hors_juge1(r)
    verifier('propre JSON : aucun constat', not r['constats'], '; '.join(x['message'] for x in r['constats']))
    if vite:
        return r
    v = video_propre(rendre)
    if v is None:
        verifier('propre vidéo : rendu de 4 s disponible', False, 'relancer avec --rendre')
        return r
    rv = lancer(reel, 'propre-video', v, 12.0)
    verifier('propre vidéo : aucun bloquant ni important', not codes(rv, ('bloquant', 'important')),
             '; '.join(x['message'] for x in rv['constats']) + f" | loudness {rv['mesures'].get('loudness')}")
    # meme rendu reduit de moitie (apercu basse resolution) puis dans un autre format : les boites du reel restent justes
    import shutil
    from editeur.media import FFMPEG
    d = Path(tempfile.mkdtemp(prefix='controle-revue-', dir=str(ROOT / 'runtime/cache/tmp')))
    try:
        demi, large = d / 'propre-demi.mp4', d / 'propre-16x9.mp4'
        subprocess.run([FFMPEG, '-v', 'error', '-y', '-i', str(v), '-vf', 'scale=540:960', '-c:a', 'copy', str(demi)], check=True)
        subprocess.run([FFMPEG, '-v', 'error', '-y', '-i', str(v), '-vf', 'crop=1080:608,scale=1920:1080', '-c:a', 'copy', str(large)], check=True)
        r2 = _hors_juge1(controle.controler(reel, video=demi, debut=12.0))
        verifier('propre vidéo réduite : seulement le conseil « format »', codes(r2) == ['format'] and r2['constats'][0]['gravite'] == 'conseil',
                 '; '.join(f"{x['gravite']} {x['message']}" for x in r2['constats']))
        r3 = _hors_juge1(controle.controler(reel, video=large, debut=12.0))
        verifier('vidéo d’un autre format : images non analysées, pas de faux constat', codes(r3) == ['format'] and not r3['mesures']['video']['images_controlees'],
                 '; '.join(f"{x['gravite']} {x['message']}" for x in r3['constats']))
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return rv


def mutation(nom, fn, attendu, gravites=('bloquant', 'important', 'conseil')):
    reel = copy.deepcopy(propre_base)
    fn(reel)
    r = lancer(reel, f'mutation-{nom}')
    trouve = [x for x in r['constats'] if x['code'] == attendu and x['gravite'] in gravites]
    autres = [x['code'] for x in r['constats'] if x['code'] != attendu]
    verifier(f'mutation {nom} → {attendu}', bool(trouve), (trouve[0]['message'] if trouve else '') + (f' | autres : {autres}' if autres else ''))
    return r, autres


def cas_mutations():
    faux = {}

    def scene(texte, y=.2, kind='notification', secondaire='RyuCalls', mot=30):
        def f(r):
            clip = r['clips'][1]
            r['design'] = {'enabled': True, 'mode': 'tech', 'accent': '#86B7FF', 'secondary': '#FFFFFF', 'suppressExtras': True}
            r['styleScenes'] = [{'id': 'm1', 'kind': kind, 'clip': clip['id'], 'index': mot, 'length': 1, 'text': texte, 'secondary': secondaire,
                                 'duration': 2.4, 'x': .5, 'y': y, 'scale': 1, 'rotation': 0}]
        return f

    def taille(r):
        r['style']['size'] = 40

    def chiffre(r):
        r['graphics'] = [{'id': 'g1', 'kind': 'chiffre', 'at': 14.0, 'duration': 2.2, 'props': {'value': 5, 'prefix': '×', 'label': 'MOINS CHER', 'y': .44}}]

    def media(r):
        sid = r['clips'][0]['source']
        r['sources'][sid]['proxy'] = 'projects/_cache/optimises/absent-controle.mp4'

    def chevauche(r):
        r['banner'] = {'enabled': True, 'text': 'Répondez en 5 minutes', 'start': 10, 'end': 16}
        r['graphics'] = [{'id': 'g2', 'kind': 'coches', 'at': 11.0, 'duration': 2.8, 'props': {'items': ['Setter qualifié', 'Réponse rapide'], 'y': .1}}]

    def musique(r):
        r['music']['volume'] = 1.0

    def fige(r):
        r['zoom'] = {'auto': False, 'strength': 1, 'push': 0, 'overrides': {}}

    def contraste(r):
        r['style'].update({'color': '#D8D8D8', 'highlight': '#E8E8E8', 'strokeWidth': 0, 'preset': 'bulle'})

    def accroche(r):
        r['graphics'] = [{'id': 'g3', 'kind': 'coches', 'at': 1.0, 'duration': 2.5, 'props': {'items': ['Réponse rapide'], 'y': .12}, 'auto': True}]

    tests = [('illustration', scene('ILLUSTRATION'), 'texte-interne', ('bloquant',)),
             ('nom-fichier', scene('Rendu final', secondaire='plan_03.mp4', kind='notification'), 'texte-interne', ('bloquant',)),
             ('sous-titres-40px', taille, 'texte-petit', ('important',)),
             ('chiffre-sur-visage', chiffre, 'visage-couvert', ('bloquant', 'important')),
             ('media-absent', media, 'media-manquant', ('bloquant',)),
             ('chevauchement', chevauche, 'chevauchement', ('important', 'conseil')),
             ('musique-forte', musique, 'musique-forte', ('important',)),
             ('cadre-fige', fige, 'cadre-fige', ('important', 'conseil')),
             ('contraste-bulle', contraste, 'contraste-faible', ('important', 'conseil')),
             ('graphisme-accroche', accroche, 'accroche-couverte', ('important',))]
    for nom, fn, attendu, gr in tests:
        _, autres = mutation(nom, fn, attendu, gr)
        faux[nom] = autres
    return faux


def cas_revue():
    """Non-regression des defauts trouves a la revue (faux positifs / negatifs), toujours sur des copies."""
    def essai(nom, fn):
        reel = copy.deepcopy(propre_base)
        fn(reel)
        return lancer(reel, f'revue-{nom}')

    def de(r, code, gravites=('bloquant', 'important', 'conseil')):
        return [x for x in r['constats'] if x['code'] == code and x['gravite'] in gravites]

    # 1. prise INUTILISEE absente (reel.sources garde les prises non montees) : l'export ne la lit pas
    def inutilisee(r):
        r['sources']['zz'] = {'name': 'prise non montée', 'proxy': 'projects/_cache/optimises/absente-zz.mp4', 'path': 'D:/absent/zz.MP4',
                              'duration': 5, 'width': 1080, 'height': 1920, 'samples': []}
    r = essai('source-inutilisee', inutilisee)
    verifier('revue : prise inutilisée absente → aucun « média manquant »', not de(r, 'media-manquant'), '; '.join(x['message'] for x in de(r, 'media-manquant')))

    # 2. voix nettoyee d'une prise UTILISEE absente : render.mjs refuse l'export -> bloquant
    def voix(r):
        r['sources'][r['clips'][0]['source']]['voice'] = 'projects/_cache/voix/absente-controle.voix.m4a'
    verifier('revue : voix nettoyée absente = bloquant', bool(de(essai('voix-absente', voix), 'media-manquant', ('bloquant',))))

    # 3. mot geant de 0,8 s sur le visage : effet de ponctuation voulu (voile 35 % + lueur) -> conseil, pas de faux contraste
    def mot(r):
        r['graphics'] = [{'id': 'mg', 'kind': 'motgeant', 'at': 14.0, 'duration': 0.8, 'props': {'text': 'WOW'}}]
    r = essai('motgeant', mot)
    verifier('revue : mot géant bref sur le visage = conseil seulement', de(r, 'visage-couvert') and not de(r, 'visage-couvert', ('bloquant', 'important')),
             '; '.join(f"{x['gravite']} {x['message']}" for x in de(r, 'visage-couvert')))
    verifier('revue : mot géant lumineux → pas de « peu contrasté »', not de(r, 'contraste-faible'))

    # 4. « exemple » dans une vraie phrase : au plus un conseil ; « EXAMPLE » seul (anglais) : bloquant
    def phrase(r):
        scene_fn = cas_mutations_scene('Un exemple concret : 5 leads rappelés')
        scene_fn(r)
    r = essai('exemple-phrase', phrase)
    verifier('revue : « exemple » dans une phrase ≠ important', not de(r, 'texte-interne', ('bloquant', 'important')))
    r = essai('example-anglais', cas_mutations_scene('EXAMPLE'))
    verifier('revue : « EXAMPLE » (anglais) = bloquant', bool(de(r, 'texte-interne', ('bloquant',))))
    r = essai('nan-quebecois', cas_mutations_scene('Nan, pas besoin d’employé'))
    verifier('revue : « Nan, … » (québécois) n’est pas un « NaN » technique', not de(r, 'texte-interne'))

    # 5. image tres sombre sans detourage : pas de faux « tiers vide » (aucun masque de la personne)
    orig = controle.Fonds._images
    controle.Fonds._images = lambda self, k: [(t, (im // 12).astype(im.dtype)) for t, im in orig(self, k)]
    try:
        r = essai('tres-sombre', lambda r: None)
    finally:
        controle.Fonds._images = orig
    verifier('revue : prise très sombre → pas de faux « tiers vide »', not de(r, 'tiers-vide'))

    # 6. deux personnes (prise horizontale) : le visage suivi est celui de la piste de cadrage (qui parle)
    reel = copy.deepcopy(propre_base)
    sid = reel['clips'][0]['source']
    reel['sources'][sid]['track'] = [[t / 5, .7, .35, .2] for t in range(0, 200)]
    d = Path(tempfile.mkdtemp(prefix='controle-revue-', dir=str(ROOT / 'runtime/cache/tmp')))
    try:
        ctx = controle.Contexte(reel, controle.montage_calcule(reel, d))
        pts = ctx._analyse(sid)
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)
    verifier('revue : deux personnes → visage de la piste de cadrage', bool(pts) and all(abs(p[1] - .7) < 1e-6 for p in pts))

    # 7. verdict honnete : un point important n'est jamais « Prêt à livrer »
    verifier('revue : verdict avec un point important ≠ « Prêt à livrer »',
             controle.verdict(9.0, [{'gravite': 'important'}]) != 'Prêt à livrer' and controle.verdict(9.7, [{'gravite': 'conseil'}]) == 'Prêt à livrer')


def cas_mutations_scene(texte):
    def f(r):
        clip = r['clips'][1]
        r['design'] = {'enabled': True, 'mode': 'tech', 'accent': '#86B7FF', 'secondary': '#FFFFFF', 'suppressExtras': True}
        r['styleScenes'] = [{'id': 'm1', 'kind': 'notification', 'clip': clip['id'], 'index': 30, 'length': 1, 'text': texte, 'secondary': 'RyuCalls',
                             'duration': 2.4, 'x': .5, 'y': .2, 'scale': 1, 'rotation': 0}]
    return f


def cas_sans_cuda(vite):
    """Carte graphique absente ou incoherente (is_available() vrai mais aucun appareil) : repli sur le processeur."""
    if vite:
        return
    code = ('import os,sys; os.environ["CUDA_VISIBLE_DEVICES"]=""; sys.path.insert(0, r"%s"); import numpy as np; '
            'from editeur.controle import Reference; r=Reference(); m=r.masque(np.zeros((192,108,3),np.uint8)); r.close(); print(r.dev, m.shape)') % (ROOT / 'engine')
    p = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, encoding='utf-8', errors='replace')
    verifier('sans CUDA : référence RVM sur le processeur, sans plantage', p.returncode == 0 and p.stdout.strip().startswith('cpu'),
             (p.stdout.strip() or p.stderr.strip()[-200:]))


def cas_relecture_r2(vite):
    """Relecture de la ronde 2 (01/10/2026) : compteur « REC » groupe, duree d'un apercu partiel qui commence a 0 s,
    hauteur reelle des notifications du studio (place reservee .3 u, contenu plus petit)."""
    # 1. Retro VHS : le compteur « REC · 00:12:05 » qui defile = UN constat (avant : un par valeur, 709 sur Video 1)
    r = propre()
    r['design'] = {'mode': 'vhs', 'enabled': True, 'accent': '#ECE3BF', 'secondary': '#FFFFFF', 'density': 4}
    rap = controle.controler(r)
    rec = [c for c in rap['constats'] if c['code'] == 'texte-interne' and 'REC' in c['message']]
    verifier('Retro VHS : le compteur REC qui défile = un seul constat', len(rec) == 1, f"{len(rec)} constat(s) REC, {len(rap['constats'])} au total"
             + (f" ; {rec[0]['message']}" if rec else ''))
    # 2. apercu partiel commencant a 0 s (job.json avec frameRange) : comparer a l'extrait, pas au montage entier
    v = ICI / 'cas/propre-12-16.mp4'
    base = propre()
    attendue = controle._duree_auto(v, base, {'out': str(v), 'frameRange': [0, 119]})
    verifier('aperçu partiel : durée attendue lue dans frameRange (4 s)', attendue is not None and abs(attendue - 4.0) < 1e-6, str(attendue))
    verifier('export complet (sans frameRange) : pas de durée d’extrait', controle._duree_auto(v, base, {'out': str(v)}) is None)
    if not vite and v.exists():
        sans = controle.controler(base, video=v, debut=0.0, duree_attendue=attendue, profond=False)
        avec = controle.controler(base, video=v, debut=0.0, profond=False)
        verifier('aperçu 0–4 s : pas de faux « durée différente du montage »', 'duree' not in codes(sans) and 'duree' in codes(avec),
                 f"avec l'extrait : {codes(sans)} ; sans : {[c['message'] for c in avec['constats'] if c['code'] == 'duree']}")
    # 3. studio Tech 3D : la notification a la hauteur de son contenu (StudioCard), pas toute la place reservee
    reel = json.loads((ICI / 'cas/apercu-premium-job-copie.json').read_text(encoding='utf-8'))['reel']
    d = Path(tempfile.mkdtemp(prefix='controle-r2-', dir=str(ROOT / 'runtime/cache/tmp')))
    try:
        ctx = controle.Contexte(reel, controle.montage_calcule(reel, d))
        kinds = {f"scene:{s.get('id')}": s.get('kind') for s in ctx.tl['scenes']}
        notifs = {}
        for t in np.arange(0, ctx.total, .5):
            for e in controle.visibles(ctx, float(t)):
                if kinds.get(e['id']) == 'notification':
                    notifs[e['id']] = (e['box'][3] - e['box'][1]) / ctx.u
        verifier('studio : notification à la hauteur de son contenu (< 0,3 u réservé, ≥ 0,2 u)',
                 bool(notifs) and all(.2 <= h < .29 for h in notifs.values()), ', '.join(f'{k} {h:.3f} u' for k, h in notifs.items()) or 'aucune notification')
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')  # console Windows (cp1252) : les « → » et accents ne doivent pas planter
    except (AttributeError, ValueError):
        pass
    vite = '--vite' in sys.argv
    rendre = '--rendre' in sys.argv
    RESULTATS.mkdir(parents=True, exist_ok=True)
    cas_apercu(vite)
    cas_actuel()
    cas_studio()
    cas_propre(vite, rendre)
    propre_base = propre()
    faux = cas_mutations()
    cas_revue()
    cas_relecture_r2(vite)
    cas_sans_cuda(vite)
    n = sum(1 for b in bilan if b['ok'])
    print(f'\n{n}/{len(bilan)} tests réussis')
    (RESULTATS / 'tests.json').write_text(json.dumps({'bilan': bilan, 'constats_en_plus_par_mutation': faux}, ensure_ascii=False, indent=1), encoding='utf-8')
    sys.exit(0 if n == len(bilan) else 1)
