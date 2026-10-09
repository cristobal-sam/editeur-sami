# FAUX « python -m editeur.critique_claude <video.mp4> --reel <reel.json | export.json | dossier_projet id> [--rapport r]
# [--json] » : MEME ligne de commande que engine/editeur/critique_claude.py (revue 2026-10-02 : l'ancienne version factice
# acceptait « <projet> --reel <rid> --video f », que le vrai module refuse). 1 s ; avis comme critique() : {titre, ok, statut,
# message, note, verdict, problemes [{temps, gravite, probleme, suggestion}], cout, cout_avis, cache...} ; range dans le
# rapport du controle de cette video s'il existe (section « claude », comme controle.ajouter_avis_claude) -> « resume ».
# Marqueur runtime/cache/faux-critique-plafond : avis refuse (ok = false, message « plafond »), comme le vrai module.
import argparse
import json
import time
from pathlib import Path

from . import _faux as F

F.journal('critique_claude')
p = argparse.ArgumentParser()
p.add_argument('video')
p.add_argument('--reel', nargs='+', required=True)
p.add_argument('--rapport')
p.add_argument('--refaire', action='store_true')
p.add_argument('--json', action='store_true')
a = p.parse_args()
if not Path(a.video).is_file():
    raise SystemExit(f'Vidéo introuvable : {a.video}')
if len(a.reel) == 2:
    _, reel = F.reel_de(a.reel[0], a.reel[1])
else:
    d = F.lire(a.reel[0], {}) or {}
    reel = d.get('reel') if isinstance(d.get('reel'), dict) else d
time.sleep(1)
video = f"{reel.get('project')}/{reel.get('id')}"
base = {'version': 1, 'titre': 'Avis de Claude', 'modele': 'claude-sonnet-5-5', 'nom_modele': 'Claude Sonnet 5.5',
        'date': time.strftime('%Y-%m-%d %H:%M'), 'video': a.video, 'images': [{'t': 0.8, 'raison': 'accroche'}]}
if F.marque('critique-plafond'):
    avis = {**base, 'ok': False, 'statut': 'plafond', 'message': 'Avis de Claude non demandé : plafond atteint',
            'detail': 'Plafond du jour atteint (test).', 'cout': 0.0, 'cout_avis': 0.0, 'cache': False}
else:
    avis = {**base, 'ok': True, 'statut': 'ok', 'message': '', 'detail': '', 'note': 6.5,
            'verdict': 'Rythme correct ; le texte final est trop petit (faux avis).', 'points_forts': ['accroche claire'],
            'problemes': [{'temps': 0.8, 'gravite': 'important', 'probleme': 'Sous-titre collé au bord', 'suggestion': 'le remonter un peu'}],
            'prochaine_amelioration': 'Grossir le texte final.', 'compte': {'bloquant': 0, 'important': 1, 'conseil': 0},
            'cout': 0.052, 'cout_avis': 0.052, 'cout_texte': '0,05 $', 'cache': False}
    F.depense(video, 'critique', 0.052)
# rapport du controle de CETTE video (runtime/cache/controle/<projet>-<reel>/export-*/controle.json), comme le vrai module
rapport = None
base_ctl = F.ROOT / 'runtime' / 'cache' / 'controle' / f"{reel.get('project')}-{reel.get('id')}"
for f in sorted(base_ctl.glob('export-*/controle.json')) if base_ctl.is_dir() else []:
    r = F.lire(f, {}) or {}
    if Path(r.get('video') or '').resolve() == Path(a.video).resolve():
        rapport = (f, r)
resume = None
if rapport:
    f, r = rapport
    r['claude'] = {k: avis[k] for k in ('ok', 'statut', 'message', 'note', 'verdict', 'problemes', 'cout_avis', 'modele', 'date') if k in avis}
    F.ecrire(f, r)
    resume = {'note': r.get('note', 8.0), 'verdict': r.get('verdict', ''), 'compte': r.get('compte', {}), 'date': time.strftime('%Y-%m-%d %H:%M'),
              'constats': r.get('constats', []), 'claude': r['claude']}
out = {**avis, 'rapport': str(rapport[0]) if rapport else None, 'resume': resume}
if a.json:
    F.sortie(out)
else:  # le vrai module ecrit alors un texte (pas de JSON) : le serveur doit passer --json
    print(f"Avis de Claude : {avis.get('note')}/10")
