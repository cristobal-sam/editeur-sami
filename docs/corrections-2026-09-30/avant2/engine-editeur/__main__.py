"""Ligne de commande : python -m editeur <commande> ...

  derush <dossier_rushs> <script.docx> [--style reel-impact] [--sans-rendu]
        derushage + montages bruts dans livraisons/<script>/ ; avec --style, monte aussi
        chaque version dans ce style et exporte les « ... - FINAL.mp4 »
  render <dossier_projet>        refait la livraison apres une retouche du project.json
  reel <dossier_projet> [--variante v1] [--style id] [--plan c2 --prise 1 | --entree/--sortie s] [--exporter]
  styles                         liste les styles de montage disponibles
  ia | broll | graphismes | raccords | angles <dossier_projet> --reel v1   propositions (rien n'est applique
                                 sauf « angles ») ; resultat JSON
  declinaison <dossier_projet> --reel v1 [--duree 30] [--intention rapide|emotion]
  multicam <dossier_projet> [--prises t01,t02]      synchronise les cameras par le son
  visuel <dossier_videos> --type immobilier|evenement [--titre "12 rue X"] [--duree 30] [--musique id]
  banques statut | chercher "<requete>" [--type video|image --orientation portrait --qualite hd] |
          ajouter <dossier_projet> --reel v1 --fournisseur pixabay --id 123 | phrase <dossier_projet> --reel v1 --at 12.3
                                 banques de medias libres (cle dans cles-api.env) ; resultat JSON
"""
import argparse
import json
import sys
import time
from pathlib import Path

from . import deliver, derush
from .media import ROOT


def _versions(project_dir):
    project = json.loads((Path(project_dir) / 'project.json').read_text(encoding='utf-8'))
    return [None] + [v['id'] for v in project['variants']]


def main():
    ap = argparse.ArgumentParser(prog='editeur')
    sub = ap.add_subparsers(dest='cmd', required=True)
    d = sub.add_parser('derush', help='choisit les meilleures prises selon le script')
    d.add_argument('rushs')
    d.add_argument('script', nargs='?', help='script Word/texte ; sans script : montage a partir de la transcription')
    d.add_argument('--style', help='style de montage a appliquer automatiquement (voir : styles)')
    d.add_argument('--video', help='video a monter avec --style (ex. video1) ; par defaut la premiere')
    d.add_argument('--version', default='script', help='version a monter : script (defaut) ou v1, v2... (hooks alternatifs)')
    d.add_argument('--sans-rendu', action='store_true')
    d.add_argument('--sans-broll', action='store_true', help='avec --style : ne pas inserer de plans de coupe automatiques')
    d.add_argument('--langue', help='langue des rushs : fr (defaut), en, es... ou auto (detection)')
    d.add_argument('--format', choices=['9:16', '16:9', '4:5', '1:1'], help='format de depart des reels (defaut 9:16)')
    r = sub.add_parser('render', help='refait la livraison d\'un projet retouche')
    r.add_argument('projet')
    e = sub.add_parser('reel', help='prepare un reel stylise (et applique une retouche)')
    e.add_argument('projet')
    e.add_argument('--variante')
    e.add_argument('--style')
    e.add_argument('--plan', help='plan a retoucher (ex. c2)')
    e.add_argument('--prise', type=int, help='numero de prise a utiliser pour --plan')
    e.add_argument('--entree', type=float, default=0.0, help='decalage du debut du plan (s)')
    e.add_argument('--sortie', type=float, default=0.0, help='decalage de la fin du plan (s)')
    e.add_argument('--exporter', action='store_true')
    sub.add_parser('styles', help='liste les styles de montage')
    pr = sub.add_parser('produit', help='rend le produit choisi avec Blender')
    pr.add_argument('projet')
    pr.add_argument('--reel', default='script')
    dt = sub.add_parser('detourage', help='actualise le détourage après un changement de prise')
    dt.add_argument('projet')
    dt.add_argument('--reel', default='script')
    x = sub.add_parser('echange', help='exporte le montage pour DaVinci Resolve / Premiere (OTIO, XML, FCPXML, SRT)')
    x.add_argument('projet')
    x.add_argument('--variante')
    i = sub.add_parser('intro', help='titre d\'ouverture 3D rendu par Blender')
    i.add_argument('projet')
    i.add_argument('texte')
    i.add_argument('--couleur', default='#FFD400')
    i.add_argument('--police', default='Anton.ttf')
    i.add_argument('--duree', type=float, default=2.5)
    s = sub.add_parser('recherche', help='recherche en phrase naturelle dans les rushs d\'un projet')
    s.add_argument('projet')
    s.add_argument('requete')
    s.add_argument('--sans-vision', action='store_true')
    for name, help_ in (('ia', 'relance l\'IA : propositions de mots cles, emojis, bandeaux (rien n\'est applique)'),
                        ('broll', 'propose des plans de coupe (dossier media/broll) aux bons moments'),
                        ('graphismes', 'propose des elements graphiques (chiffres, cases cochees, mot geant, logo)'),
                        ('raccords', 'cherche les faux raccords a chaque coupe (experimental)'),
                        ('angles', 'multicamera : choisit l\'angle de chaque plan (qui parle)')):
        x = sub.add_parser(name, help=help_)
        x.add_argument('projet')
        x.add_argument('--reel', default='script', help='version du reel (script, v1, v1-30-s...)')
        x.add_argument('--tout', action='store_true', help='broll : proposer aussi les prises du projet')
        x.add_argument('--sans-vision', action='store_true')
        x.add_argument('--large', type=int, default=0, help='angles : un plan large tous les N plans')
        x.add_argument('--sans-banques', action='store_true', help='broll : ne pas chercher dans les banques de medias libres')
        x.add_argument('--auto', action='store_true', help='broll : inserer les plans dont l\'IA est sure')
    sr = sub.add_parser('style-ref', help='cree un style de montage en analysant une video deja montee (reference)')
    sr.add_argument('video')
    sr.add_argument('--nom', help='nom du style (defaut : « Ref. <nom du fichier> »)')
    au = sub.add_parser('auto', help='monte seul une video deposee (fichier ou dossier) : sujet, style adapte, montage complet')
    au.add_argument('unite', help='fichier video ou dossier de prises')
    au.add_argument('--client', help='charte client (styles/clients/<id>.json)')
    au.add_argument('--style', help='style impose (sinon choisi selon le sujet, styles/types.json)')
    au.add_argument('--livraison', help='dossier ou iront les videos finales')
    au.add_argument('--langue', default='auto')
    au.add_argument('--sans-banques', action='store_true')
    bq = sub.add_parser('banques', help='banques de medias libres : statut, chercher, ajouter (au reel), phrase (IA)')
    bq.add_argument('action', choices=['statut', 'chercher', 'ajouter', 'phrase'])
    bq.add_argument('cible', nargs='?', help='chercher : la requete ; ajouter / phrase : le dossier du projet')
    bq.add_argument('--type', choices=['video', 'image'], default='video')
    bq.add_argument('--orientation', choices=['portrait', 'paysage', 'carre'])
    bq.add_argument('--duree-min', type=float)
    bq.add_argument('--duree-max', type=float)
    bq.add_argument('--qualite', choices=['hd', '4k'])
    bq.add_argument('--page', type=int, default=1)
    bq.add_argument('--fournisseur', help='une seule banque (defaut : toutes les banques configurees)')
    bq.add_argument('--id', help='ajouter : identifiant du media dans la banque')
    bq.add_argument('--requete', default='', help='ajouter : requete qui a trouve le media (gardee dans sa fiche)')
    bq.add_argument('--reel', default='script')
    bq.add_argument('--at', type=float, default=0.0, help='phrase : instant du montage (s)')
    dcl = sub.add_parser('declinaison', help='cree une declinaison : 60/30/15 s et/ou intention (rapide, emotion)')
    dcl.add_argument('projet')
    dcl.add_argument('--reel', default='script')
    dcl.add_argument('--duree', type=float)
    dcl.add_argument('--intention', choices=['rapide', 'emotion'])
    mc = sub.add_parser('multicam', help='synchronise par le son les prises filmees en meme temps (plusieurs cameras)')
    mc.add_argument('projet')
    mc.add_argument('--prises', help='identifiants separes par des virgules (defaut : toutes)')
    vi = sub.add_parser('visuel', help='montage sans parole : immobilier ou evenement, cale sur la musique')
    vi.add_argument('dossier')
    vi.add_argument('--type', choices=['immobilier', 'evenement'], default='immobilier')
    vi.add_argument('--titre', help='titre / adresse affiche en bandeau')
    vi.add_argument('--duree', type=float, default=30)
    vi.add_argument('--musique', help='ambiance de musique (styles/musiques.json)')
    vi.add_argument('--sortie', help='dossier des projets (defaut : projects)')
    a = ap.parse_args()

    if a.cmd == 'detourage':
        from . import detourage, montage
        r = montage.update(a.projet, a.reel, detourage.prepare)
        print(json.dumps({'cutouts': r.get('cutouts', {})}, ensure_ascii=False))
    elif a.cmd == 'produit':
        from .produit import make
        print(json.dumps(make(a.projet, a.reel), ensure_ascii=False))
    elif a.cmd == 'ia':
        from .reel import refresh_ai
        print(json.dumps(refresh_ai(a.projet, None if a.reel == 'script' else a.reel), ensure_ascii=False))
    elif a.cmd == 'broll':
        from .broll import suggest
        print(json.dumps(suggest(a.projet, a.reel, include_rushes=a.tout, external=not a.sans_banques, auto=a.auto), ensure_ascii=False))
    elif a.cmd == 'style-ref':
        from .style_ref import build as build_style
        print(json.dumps(build_style(a.video, a.nom), ensure_ascii=False))
    elif a.cmd == 'auto':
        from .auto import run
        print(json.dumps(run(a.unite, a.client, a.style, a.langue, a.livraison, not a.sans_banques), ensure_ascii=False))
    elif a.cmd == 'banques':
        from . import banques
        try:
            if a.action == 'statut':
                out = banques.statut()
            elif a.action == 'chercher':
                opts = {'orientation': a.orientation, 'min_duration': a.duree_min, 'max_duration': a.duree_max,
                        'min_short': {'hd': 1000, '4k': 2000}.get(a.qualite), 'page': a.page, 'lang': 'auto'}
                out = banques.search(a.cible or '', a.type, opts, a.fournisseur)
            elif not a.cible:
                raise banques.BanqueErreur('Dossier du projet manquant.')
            elif a.action == 'ajouter':
                if not a.fournisseur or not a.id:
                    raise banques.BanqueErreur('--fournisseur et --id sont requis.')
                from .broll import add_asset
                out = add_asset(a.cible, a.reel, a.fournisseur, a.id, a.type, a.requete)
            else:
                out = banques.for_sentence(a.cible, a.reel, a.at)
        except banques.BanqueErreur as e:
            raise SystemExit(str(e))
        print(json.dumps(out, ensure_ascii=False))
    elif a.cmd == 'graphismes':
        from .graphismes import suggest
        print(json.dumps(suggest(a.projet, a.reel), ensure_ascii=False))
    elif a.cmd == 'raccords':
        from .raccords import check
        print(json.dumps(check(a.projet, a.reel, use_vision=not a.sans_vision), ensure_ascii=False))
    elif a.cmd == 'angles':
        from .multicam import auto_angles
        print(json.dumps(auto_angles(a.projet, a.reel, a.large), ensure_ascii=False))
    elif a.cmd == 'declinaison':
        from .declinaison import create
        print(json.dumps(create(a.projet, a.reel, a.duree, a.intention), ensure_ascii=False))
    elif a.cmd == 'multicam':
        from .multicam import sync
        groups = sync(a.projet, a.prises.split(',') if a.prises else None)
        print(json.dumps({'groupes': groups}, ensure_ascii=False))
    elif a.cmd == 'visuel':
        from .visuel import build
        p = build(a.dossier, a.type, a.sortie, None, a.titre, a.duree, a.musique)
        print(json.dumps({'projet': str(p)}, ensure_ascii=False))
    elif a.cmd == 'echange':
        from .echange import export_reel
        out, written, errors = export_reel(a.projet, a.variante)
        print(json.dumps({'dossier': str(out), 'fichiers': written, 'erreurs': errors}, ensure_ascii=False))
    elif a.cmd == 'intro':
        from .intro import make_intro
        out = make_intro(a.projet, a.texte, font=a.police, color=a.couleur, seconds=a.duree)
        print(json.dumps({'fichier': Path(out).resolve().relative_to(ROOT.resolve()).as_posix()}))
    elif a.cmd == 'recherche':
        from .search import search
        print(json.dumps(search(a.projet, a.requete, use_vision=not a.sans_vision), ensure_ascii=False))
    elif a.cmd == 'styles':
        from .reel import list_templates
        for t in list_templates():
            print(f"{t['id']:18} {t['name']} - {t['description']}")
    elif a.cmd == 'reel':
        from . import edit, reel
        if a.plan and a.prise is not None:
            edit.set_take(a.projet, a.plan, a.prise)
        if a.plan and (a.entree or a.sortie):
            edit.trim(a.projet, a.plan, a.entree, a.sortie)
        path = reel.ensure(a.projet, a.variante, template=a.style)
        if a.exporter:
            from .export import export_reel
            print(f'-> {export_reel(a.projet, a.variante)}')
        print(json.dumps({'reel': str(path)}))
    elif a.cmd == 'derush':
        t = time.time()
        if a.script:
            projects = derush.build(a.rushs, a.script, ROOT / 'projects', ROOT / 'projects/_cache', a.langue, a.format)
        else:
            from . import libre
            projects = libre.build_free(a.rushs, ROOT / 'projects', ROOT / 'projects/_cache', a.langue, a.format)
            a.script = str(Path(a.rushs).resolve())
        print(f'Derushage termine en {time.time() - t:.0f} s : {len(projects)} video(s).')
        for p in projects:
            print(f'   Rapport : {p / "rapport.md"}')
        if a.sans_rendu:
            return
        print('\nMontages bruts :')
        out = deliver.deliver(projects, a.script)
        if a.style:
            from . import reel
            from .export import export_reel
            # Un seul reel a la fois : la video et la version demandees.
            p = next((x for x in projects if x.name == a.video), None) if a.video else projects[0]
            if p is None:
                raise SystemExit(f"Video inconnue : {a.video} (disponibles : {', '.join(x.name for x in projects)})")
            v = None if a.version == 'script' else a.version
            if v not in _versions(p):
                raise SystemExit(f"Version inconnue pour {p.name} : {a.version} "
                                 f"(disponibles : script, {', '.join(x for x in _versions(p) if x)})")
            print(f'\nMontage automatique de {p.name} ({a.version}), style « {a.style} » :')
            reel.ensure(p, v, template=a.style, ai_mode='auto')  # montage sans intervention : l'IA applique
            chosen_tpl = next((t for t in reel.list_templates() if t['id'] == a.style), {})
            if not a.sans_broll and (chosen_tpl.get('broll') or {}).get('auto', False):
                # plans de coupe : seulement ceux dont l'IA est sure (bibliotheque media/broll, puis banques)
                try:
                    from .broll import suggest
                    found = suggest(p, v or 'script', auto=True, external=False)
                    if found.get('inseres'):
                        print(f"   {found['inseres']} plan(s) de coupe insere(s) automatiquement")
                except Exception as e:
                    print(f'   Plans de coupe automatiques ignores ({e}).')
            print(f'   -> {export_reel(p, v).name}')
        print(f'\nTout est dans : {out}')
    else:
        project = json.loads((Path(a.projet) / 'project.json').read_text(encoding='utf-8'))
        script = project['script']['path']
        siblings = [p.parent for p in (ROOT / 'projects').glob('*/project.json')
                    if json.loads(p.read_text(encoding='utf-8'))['script'].get('path') == script]
        out = deliver.deliver(sorted(siblings), script)
        print(f'\nTout est dans : {out}')


def _friendly(e):
    """Une phrase claire (ce qui s'est passe, quoi faire) ; le detail technique va dans runtime/cache/erreurs.log."""
    import subprocess
    text = str(e)
    low = text.lower()
    if 'out of memory' in low or 'cuda' in low and 'memory' in low:
        return "Memoire de la carte graphique pleine : ferme les logiciels lourds (jeux, montage) puis relance."
    if isinstance(e, subprocess.CalledProcessError):
        err = (e.stderr or b'')
        err = err.decode('utf-8', 'replace') if isinstance(err, bytes) else str(err)
        return f"Fichier video illisible ou abime (FFmpeg) : {err.strip().splitlines()[-1] if err.strip() else text}"[:400]
    if isinstance(e, FileNotFoundError):
        return f"Fichier introuvable : {getattr(e, 'filename', '') or text}"
    if isinstance(e, PermissionError):
        return f"Fichier utilise par un autre logiciel (ou copie en cours) : {getattr(e, 'filename', '') or text}. Reessaie dans un instant."
    if isinstance(e, json.JSONDecodeError):
        return "Fichier de projet abime (JSON illisible) : restaure une version dans l'onglet Versions, ou relance le montage."
    return f"Erreur inattendue : {text[:300]} (details dans runtime/cache/erreurs.log)"


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception as exc:
        import traceback
        try:
            log = ROOT / 'runtime/cache/erreurs.log'
            log.parent.mkdir(parents=True, exist_ok=True)
            with open(log, 'a', encoding='utf-8') as f:
                f.write(f"\n{time.strftime('%Y-%m-%d %H:%M:%S')} editeur {' '.join(sys.argv[1:])}\n{traceback.format_exc()}")
        except OSError:
            pass
        sys.exit(_friendly(exc))
