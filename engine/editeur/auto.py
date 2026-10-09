"""Montage automatique d'une video deposee (flux « Revision ») : derushage, sujet de la video, style adapte,
montage complet (IA en mode auto, plans de coupe surs, musique du style), sans intervention.

Une « unite » est :
- un fichier video (une video ; plusieurs prises possibles dans le fichier) ; un script du meme nom a cote
  (pub1.mp4 + pub1.docx / pub1.txt) est utilise ;
- un dossier : plusieurs prises d'une meme video (avec ou sans script .docx/.txt dedans) ; avec un script a plusieurs
  videos (« Video 1 », « Video 2 »), une video par partie du script ; sans parole : montage visuel (immobilier/evenement).
Progression : lignes JSON {"stage", "progress"} ; resultat : derniere ligne JSON {"projets": [...]}. """
import json
import re
from pathlib import Path

from . import derush, libre, media, montage
from . import reel as reelmod
from .media import ROOT

TYPES = ROOT / 'styles' / 'types.json'
SCRIPT_EXT = ('.docx', '.txt', '.pdf')


def emit(stage, progress):
    print(json.dumps({'stage': stage, 'progress': round(progress, 3)}, ensure_ascii=False), flush=True)


def types():
    return json.loads(TYPES.read_text(encoding='utf-8'))


def find_script(unit):
    """Script d'une unite : fichier du meme nom a cote d'une video seule, ou unique .docx/.txt d'un dossier."""
    unit = Path(unit)
    if unit.is_file():
        return next((unit.with_suffix(e) for e in SCRIPT_EXT if unit.with_suffix(e).exists()), None)
    def choose(found):
        for extension in SCRIPT_EXT:
            matches = sorted(p for p in found if p.suffix.lower() == extension)
            if matches:
                if len(matches) > 1:
                    named = [p for p in matches if re.search(r'script|sc[eé]nario|screenplay', p.stem, re.I)]
                    if len(named) == 1:
                        return named[0]
                return matches[0] if len(matches) == 1 else None
        return None

    found = [p for p in unit.iterdir() if p.is_file() and p.suffix.lower() in SCRIPT_EXT
             and not p.name.startswith(('~$', '.'))]
    if found:
        return choose(found)
    # Les tournages placent souvent scenario, licence et lettre dans « Paperwork ».
    # Ne choisir un document imbrique que si son nom indique clairement un script.
    nested = [p for p in unit.rglob('*') if p.is_file() and p.suffix.lower() in SCRIPT_EXT
              and not p.name.startswith(('~$', '.'))
              and re.search(r'script|sc[eé]nario|screenplay', p.stem, re.I)]
    return choose(nested)


def _speech_words(unit):
    """Nombre de mots dits (transcriptions en cache, faites par le derushage)."""
    from . import transcribe
    paths = [Path(unit)] if Path(unit).is_file() else media.list_videos(unit)
    return sum(len(transcribe.transcribe(p, ROOT / 'projects/_cache/transcripts', language='auto')['words']) for p in paths)


def _visual_kind(unit):
    """Sans parole : visite immobiliere ou evenement ? (CLIP sur quelques images)."""
    try:
        import torch
        from PIL import Image
        from . import search
        model, prep, tok, dev = search._model()
        paths = ([Path(unit)] if Path(unit).is_file() else media.list_videos(unit))[:6]
        frames = [Image.fromarray(f) for p in paths for _, f in media.sample_frames(p, fps=0.5, width=320)[:2]]
        with torch.no_grad():
            img = model.encode_image(torch.stack([prep(f) for f in frames]).to(dev)).float()
            txt = model.encode_text(tok(['the interior or exterior of a house or apartment for sale',
                                         'people at a party, a show, a conference or an event']).to(dev)).float()
        img = img / img.norm(dim=-1, keepdim=True)
        txt = txt / txt.norm(dim=-1, keepdim=True)
        votes = (img @ txt.T).argmax(dim=1).tolist()
        return 'immobilier' if votes.count(0) >= votes.count(1) else 'evenement'
    except Exception:
        return 'immobilier'


CTA = re.compile(r"\b(appel\w*|contact\w*|r[ée]serv\w*|cliqu\w*|bouton|lien|offre|gratuit\w*|prix|client\w*|"
                 r"call|book|buy|offer|free|click)\b", re.I)


def _moods():
    return json.loads((ROOT / 'styles' / 'musiques.json').read_text(encoding='utf-8'))


def _mood_rule(kind, rate):
    """Musique de secours : debit rapide = energique ; temoignage = acoustique ; conseil = corporate ; etc."""
    return {'temoignage': 'acoustique', 'motivation': 'cinematique', 'podcast': 'lofi', 'annonce': 'luxe', 'fiction': 'suspense',
            'conseil': 'corporate'}.get(kind, 'energique' if rate >= 3 else 'corporate')


def classify(text, rate=2.5):
    """Sujet de la video (types.json), titre court et musique qui colle (musiques.json), par l'IA locale ;
    regles simples sinon. rate = debit de parole (mots/s)."""
    from . import llm
    kinds, moods = types(), _moods()
    text = ' '.join(text.split())[:3500]
    if llm.available() and text:
        menu = '\n'.join(f'- {k} : {v["description"]}' for k, v in kinds.items() if k not in ('immobilier', 'evenement'))
        music = '\n'.join(f"- {m['id']} : {m['name']} ({m['bpm']} BPM)" for m in moods)
        try:
            with llm.session():
                data = llm.ask_json(
                    llm.EDITOR,
                    f"Transcription d'une video brute (avant montage), debit {rate:.1f} mots/seconde :\n« {text} »\n\n"
                    f"Quel est le sujet de cette video ? Types possibles :\n{menu}\n\nQuelle musique de fond colle au propos, au ton et au debit ?\n{music}\n"
                    'Reponds {"type": "<un des types>", "musique": "<un des id de musique>", '
                    '"titre": "titre court et clair de 3 a 6 mots, dans la langue de la video", "raison": "une phrase courte en francais"}',
                    temperature=0.1, max_tokens=220)
            k = str(data.get('type', '')).strip().lower()
            mood = str(data.get('musique', '')).strip().lower()
            if k in kinds:
                return {'type': k, 'titre': str(data.get('titre') or '').strip()[:60], 'raison': str(data.get('raison') or '')[:200],
                        'musique': mood if any(m['id'] == mood for m in moods) else _mood_rule(k, rate), 'ia': True}
        except Exception as e:
            print(f'IA locale indisponible ({e}) : sujet devine par regles.')
    k = 'pub' if len(CTA.findall(text)) >= 2 else 'conseil' if text else 'autre'
    return {'type': k, 'titre': ' '.join(text.split()[:5]), 'raison': 'regles simples (IA locale indisponible)',
            'musique': _mood_rule(k, rate), 'ia': False}


def _title(pdir):
    """Titre du reel (et nom du fichier livre) : le nom de la video tel que l'utilisateur la connait (dossier depose
    ou intertitre du script, « Script 1 » -> « Vidéo 1 »), pas le titre invente par l'IA (qui reste dans la Revision)."""
    from .deliver import _safe
    p = json.loads((Path(pdir) / 'project.json').read_text(encoding='utf-8'))
    label = str(p.get('label') or p.get('name') or '').strip()
    stem = Path(str((p.get('script') or {}).get('file') or '')).stem
    if stem and label.endswith(f' ({stem})'):  # nom de dossier deja pris : la livraison est rangee par lot
        label = label[:-len(stem) - 3].strip()
    return _safe(derush.nice_label(label))


def _banner_ok(r):
    """Bandeau garde en automatique seulement si c'est un vrai titre court de l'IA (valide par llm._check_banners,
    range dans suggestions.banners) et pas une copie de la premiere phrase deja sous-titree."""
    from .script import normalize
    if r.get('kind') in ('immobilier', 'evenement') or not any(
            w.get('w', '').strip() and not w.get('cut') and not w.get('hide')
            for c in r.get('clips') or [] for w in c.get('words') or []):
        return True  # titre-adresse ou titre d'un montage visuel : pas un bandeau de parole
    text = str((r.get('banner') or {}).get('text') or '').strip()
    if not text or text.endswith(('…', '...')):
        return False
    key = lambda s: ' '.join(normalize(x) for x in str(s).split() if normalize(x))
    valid = {key(b) for b in (r.get('suggestions') or {}).get('banners') or []}
    if key(text) not in valid:
        return False
    first = next((c for c in r.get('clips') or [] if c.get('words')), None)
    said = key(' '.join(w['w'] for w in (first or {}).get('words', [])[:14]))
    if key(text) and said.startswith(key(text)[:max(12, int(len(key(text)) * 0.8))]):
        return False
    # sans relecture humaine : chaque mot fort du bandeau est dit dans la video (meme racine), sinon l'IA a pu
    # inventer (« VOTRE CONCURRENT PRISE LE LEAD ») ; mieux vaut pas de bandeau qu'un titre faux
    from .reel import STOP
    words = {normalize(w['w']).strip("'").split("'")[-1] for c in r.get('clips') or [] for w in c.get('words') or []}
    content = [t for t in (normalize(x).strip("'").split("'")[-1] for x in text.split()) if len(t) >= 4 and t not in STOP]
    return bool(content) and all(t in words or any(len(s) >= 5 and s[:5] == t[:5] for s in words) for t in content)


def _banner_correct(text):
    """Relecture du bandeau par l'IA locale (temperature 0) : elle le corrige s'il a une faute ou un mot manquant, sinon
    le recopie. L'IA juge mal (« VOTRE CONCURRENT PRISE LE LEAD » juge correct) mais corrige bien : un bandeau qu'elle
    change est refuse ; une simple correction d'accents est gardee. None : pas de bandeau."""
    from . import llm
    from .script import normalize
    try:
        with llm.session():
            # chercher d'abord un probleme (mot par mot) rend la relecture bien plus fiable que « est-ce correct ? »
            data = llm.ask_json(llm.EDITOR, "Relis ce titre court en francais (bandeau de video), mot par mot. Cherche d'abord "
                                "un probleme : faute d'accord ou de conjugaison, mot manquant (verbe, preposition), mot qui "
                                f"n'existe pas, phrase qui ne veut rien dire.\nTitre : {text}\n"
                                'Reponds {"probleme": "le probleme en 8 mots au plus, ou vide", '
                                '"titre": "le titre corrige, ou recopie EXACTEMENT s\'il est correct"}',
                                temperature=0.0, max_tokens=220)
    except Exception as e:
        print(f'Relecture du bandeau impossible ({e}) : pas de bandeau.')
        return None
    fixed = ' '.join(str(data.get('titre') or '').split()).strip().upper()
    key = lambda s: [normalize(x) for x in str(s).split() if normalize(x)]
    return fixed if fixed and key(fixed) == key(text) else None


def _finish(pdir, style, info, client=None, delivery=None, banks=True):
    """Reel complet du projet : style, IA en mode auto, cerveau Claude (en option, un appel par montage), charte du
    client, plans de coupe surs, puis relecture du monteur (sobriete.relire : un seul element a la fois, rien sur
    l'accroche sauf le bandeau, budget du style)."""
    pdir = Path(pdir)
    if delivery:
        p = json.loads((pdir / 'project.json').read_text(encoding='utf-8'))
        p['delivery'] = str(delivery)
        (pdir / 'project.json').write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding='utf-8')
    # un montage automatique repart du nouveau derushage : l'ancien reel est garde en version, puis refait
    old = pdir / 'reels' / 'script.json'
    visual = info.get('type') in ('immobilier', 'evenement')
    ancien_cerveau = ancien_echec = None
    if old.exists() and not visual:
        import shutil
        import time as _t
        try:  # cerveau Claude de l'ancien montage : relu si les mots sont les memes (pas de nouvel appel paye), et un appel
            # deja paye sans resultat sur ces memes mots n'est pas repaye
            ancien = json.loads(old.read_text(encoding='utf-8')).get('claude') or {}
            ancien_cerveau, ancien_echec = ancien.get('cerveau'), ancien.get('cerveau_echec')
        except (OSError, ValueError, AttributeError):
            ancien_cerveau = ancien_echec = None
        keep = pdir / 'versions' / 'script'
        keep.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(old, keep / f"{_t.strftime('%Y-%m-%dT%H-%M-%S')} avant montage automatique.json")
        old.unlink()
    if not visual or not old.exists():
        reelmod.ensure(pdir, None, template=style, ai_mode='auto')
    brand = None
    if client:
        f = ROOT / 'styles' / 'clients' / f'{client}.json'
        if f.exists():
            brand = json.loads(f.read_text(encoding='utf-8'))

    title = _title(pdir)
    if not visual:
        # cerveau Claude (en option) : UN appel par montage, verifie par les regles et garde dans le reel ; les passes
        # suivantes (bandeau, mots en couleur, plan creatif, cartes, graphismes) le lisent d'abord. Sans lui (eteint, pas de
        # cle, plafond, credit epuise, hors ligne...), le chemin local reste celui d'avant. Corrections de transcription posees.
        try:
            from . import cerveau_claude
            cerveau = cerveau_claude.lancer(pdir, 'script', info=info, style=style, brand=brand, cache=ancien_cerveau,
                                            echec=ancien_echec)
            info['cerveau'] = {k: cerveau.get(k) for k in ('ok', 'source', 'modele', 'cout', 'raison', 'ecartes', 'corrections')
                               if cerveau.get(k) not in (None, '')}
            if cerveau.get('ok') and cerveau.get('titre'):
                info['titre'] = cerveau['titre']
            if not cerveau.get('ok'):
                print(f"Cerveau Claude non utilise : {cerveau.get('raison')}")
        except Exception as e:  # le cerveau est un plus : le montage ne doit jamais en dependre
            print(f'Cerveau Claude ignore ({e}).')

    def apply(r):
        r['auto'] = info
        # nom de la video (« Vidéo 1 ») : c'est aussi le nom du fichier livre ; le titre de l'IA reste dans la Revision
        r['title'] = title or r.get('title')
        if delivery:
            r['delivery'] = str(delivery)
        if visual:
            # visuel.build a deja cale les prises sur la musique et regle le son et le titre-adresse.
            # Une charte peut colorer les sous-titres, sans remplacer ce montage par un reel de parole.
            if brand:
                r['brand'] = brand
                r['style'].update({k: v for k, v in (brand.get('style') or {}).items() if v})
            return
        if brand:
            r['brand'] = brand
            reelmod.apply_template(r, style)  # la charte passe par-dessus le style
        # L'accroche est deja dite et sous-titree : un vrai titre court de l'IA, ou pas de bandeau du tout
        # (jamais la premiere phrase recopiee et coupee par « … »)
        banner = r.get('banner') or {}
        claude = None
        if r.get('claude'):
            try:
                from . import cerveau_claude
                claude = cerveau_claude.bandeau(r)  # None : pas de resultat de Claude ; '' : Claude n'en propose pas
            except Exception as e:
                print(f'Bandeau de Claude ignore ({e}).')
        if claude is not None:
            # titre de Claude, deja verifie (mots dits, 7 mots au plus, pas la 1re phrase, sans faute) : pas de relecture locale
            text = claude or None
            if text:
                sug = r.setdefault('suggestions', {})
                sug['banners'] = [text] + [b for b in sug.get('banners') or [] if b != text][:2]
        else:
            text = banner.get('text') if _banner_ok(r) else None
            if text:  # meme masque : ne jamais faire reapparaitre un bandeau non relu au prochain style
                text = _banner_correct(text)
        r['banner'] = {**banner, 'text': text} if text else {**banner, 'enabled': False, 'text': ''}
        if not (r.get('design') or {}).get('mode'):
            r['flash']['enabled'] = False
            r['zoom']['auto'] = False
            r['sfx'].update(transition=None, highlight=None, start=None)
        if (r.get('design') or {}).get('mode') == 'documentaire' and not r['design'].get('title') and info.get('titre'):
            r['design']['title'] = str(info['titre'])  # le titre discret du documentaire, pas le nom du fichier
        # scene ou entrevue filmee a l'horizontale : on garde le 16:9 (une pub face camera reste en 9:16)
        rush = [s for s in r['sources'].values() if s.get('kind') != 'broll' and s.get('width')]
        if info.get('type') in ('fiction', 'podcast') and rush and sum(s['width'] > s['height'] for s in rush) * 2 > len(rush):
            r['width'], r['height'] = 1920, 1080
        mood = info.get('musique')
        if mood and (r.get('music') or {}).get('enabled') and (ROOT / 'assets' / 'music' / f'{mood}.ogg').exists():
            # la musique suit le propos de la video, pas seulement le style
            r['music'] = {**r['music'], 'mood': mood, 'file': f'music/{mood}.ogg'}
    montage.update(pdir, 'script', apply)
    if visual:
        return 0  # pas de generation d'habillage de parole sur le montage visuel
    from . import galerie
    montage.update(pdir, 'script', galerie.sober)
    tpl = next((t for t in reelmod.list_templates() if t['id'] == style), {})
    try:
        # plans de coupe seuls seulement si le style le demande ; meme alors, seuls les plans de confiance
        # « haute » sont inseres (broll.suggest), les autres restent des propositions
        from .broll import suggest
        if (tpl.get('broll') or {}).get('auto', False):
            suggest(pdir, 'script', external=False, auto=True)
    except Exception as e:
        print(f'Plans de coupe automatiques ignores ({e}).')
    try:
        # graphismes (chiffres dits, cases cochees, mot choc, logo) : tous proposes (onglet Graphismes) ; un style
        # dynamique (« graphismes »: « auto ») pose seuls ceux dont la raison est sure (confiance « haute » :
        # « ×5 MOINS CHER », un pourcentage, un montant, une liste de benefices vraiment dits, le logo)
        from . import graphismes
        found = graphismes.suggest(pdir, 'script')
        auto_g = tpl.get('graphismes') == 'auto'

        def put(r):
            keep = [g for g in (r.get('graphics') or []) if not g.get('suggested')]
            r['graphics'] = keep + [{**g, 'suggested': not (auto_g and g.get('confiance') == 'haute'),
                                     **({'auto': True} if auto_g and g.get('confiance') == 'haute' else {})} for g in found]
        montage.update(pdir, 'script', put)
    except Exception as e:
        print(f'Graphismes automatiques ignores ({e}).')
    report = {}

    def finish_design(r):
        # Le directeur créatif lit tout le montage avant que les modules d'habillage travaillent :
        # ils partagent ainsi le même arc narratif au lieu d'ajouter des effets indépendants.
        from . import creative
        creative.apply(r, info, tpl)
        galerie.prepare(r)
        from . import detourage
        detourage.prepare(r)
        # relecture du monteur : un seul element a la fois, rien sur l'accroche sauf le bandeau, budget du style
        from . import sobriete
        try:
            report.update(sobriete.relire(r, tpl, tout=True))
            r['sobriete'] = {k: report[k] for k in ('retires', 'deplaces', 'corriges', 'gardes', 'resume')}
        except Exception as e:  # la relecture est un plus : le montage ne doit jamais en dependre
            print(f'Relecture du monteur ignoree ({e}).')
        # V2 : choregraphie (comment chaque element entre et sort, avec sa raison, sur les mots et la musique) ;
        # apres la relecture : seuls les elements gardes recoivent un mouvement. Modifiable, jamais bloquante.
        try:
            from . import choregraphie
            choregraphie.actualiser(r, tpl, creer=True)
        except Exception as e:
            print(f'Choregraphie ignoree ({e}).')
    r = montage.update(pdir, 'script', finish_design)
    if report.get('resume'):
        info['sobriete'] = report['resume']
    # controle qualite automatique (passe JSON, sans rendu, quelques secondes) sur le montage FINI : note /10 et constats
    # pour l'ecran Revision (reel['controle'] + resume sur la fiche). Un plus : le montage ne doit jamais en dependre.
    try:
        from . import controle
        rapport = controle.controler(r)
        resume = controle.resume(rapport)
        # rapport complet au meme endroit que « Relancer le contrôle » (GET /controle, plugin), SEULEMENT pour un vrai projet
        # de ce dossier (ROOT/projects/<nom>) : le dossier des rapports porte le seul NOM du projet, une copie de test ou un
        # bac nomme « script1 » ecraserait sinon le rapport de la vraie Video 1
        if Path(pdir).resolve().parent == (ROOT / 'projects').resolve():
            try:
                controle.ecrire_rapport({**rapport, 'source': 'montage automatique'}, controle.dossier_rapport(Path(pdir).name, 'script'))
            except OSError as e:
                print(f'Rapport du controle non ecrit ({e}).')
        r = montage.update(pdir, 'script', lambda x: x.__setitem__('controle', resume))
        info['controle'] = {k: resume[k] for k in ('note', 'verdict', 'compte', 'date')}
    except Exception as e:
        print(f'Controle qualite ignore ({e}).')
    return sum(1 for b in r.get('broll') or [] if b.get('auto'))


def run(unit, client=None, style=None, language='auto', delivery=None, banks=True):
    """Monte automatiquement une unite. Renvoie {'projets': [{project, rid, type, typeLabel, titre, style, ...}]}.
    L'IA locale est demarree une seule fois pour tout le travail (sujet, mots cles, plans de coupe)."""
    from . import llm
    if llm.available():
        with llm.session():
            return _run(unit, client, style, language, delivery, banks)
    return _run(unit, client, style, language, delivery, banks)


def _run(unit, client, style, language, delivery, banks):
    unit = Path(unit).resolve()
    if not unit.exists():
        raise SystemExit(f'Introuvable : {unit}')
    kinds = types()
    cache = ROOT / 'projects/_cache'
    script = find_script(unit)
    pdf = [p.name for p in (unit.iterdir() if unit.is_dir() else []) if p.suffix.lower() in ('.doc', '.pages', '.rtf')]
    emit('Écoute et analyse des prises', 0.05)
    if not script and _speech_words(unit) < 15:
        # pas de parole : montage visuel cale sur la musique
        from . import visuel
        kind = _visual_kind(unit)
        emit('Montage visuel (' + kinds[kind]['label'] + ')', 0.4)
        pdir = visuel.build(unit, kind, ROOT / 'projects', cache, None, 30, None)
        info = {'type': kind, 'typeLabel': kinds[kind]['label'], 'titre': unit.stem if unit.is_file() else unit.name, 'raison': 'aucune parole : montage visuel',
                'style': kinds[kind]['style'], 'ia': False}
        _finish(pdir, style or kinds[kind]['style'], info, client, delivery, banks)
        return {'projets': [{'project': pdir.name, 'rid': 'script', **info}]}
    if script:
        projects = derush.build(unit, script, ROOT / 'projects', cache, language)
    else:
        projects = libre.build_free(unit, ROOT / 'projects', cache, language)
    if not projects:
        raise SystemExit("Aucune phrase exploitable dans cette video (bavardage seulement, ou son absent).")
    out = []
    for n, pdir in enumerate(projects):
        base = 0.45 + 0.5 * n / len(projects)
        emit('Compréhension du sujet', base)
        project = json.loads((Path(pdir) / 'project.json').read_text(encoding='utf-8'))
        text = ' '.join(c['text'] for c in project['timeline'])
        spoken = sum(max(0.1, c['out'] - c['in']) for c in project['timeline'])
        found = classify(text, len(text.split()) / max(1.0, spoken))
        kind = found['type'] if found['type'] in kinds else 'autre'
        chosen = style or kinds[kind]['style']
        info = {'type': kind, 'typeLabel': kinds[kind]['label'], 'titre': found['titre'] or project['label'], 'raison': found['raison'],
                'style': chosen, 'musique': found.get('musique'), 'ia': found['ia'],
                # a montrer dans la Revision : phrases du script absentes des prises, script non lu
                'alertes': [a['texte'] for a in project.get('alertes', [])][:8]
                + ([f"Script non lu ({', '.join(pdf)}) : enregistre-le en .docx, .txt ou PDF avec du texte."] if pdf and not script else [])}
        emit(f"Montage « {kinds[kind]['label']} »", base + 0.15 / len(projects))
        info['plansDeCoupe'] = _finish(pdir, chosen, info, client, delivery, banks)
        out.append({'project': Path(pdir).name, 'rid': 'script', **info})
    emit('Prête', 1.0)
    return {'projets': out}
