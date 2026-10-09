"""Plans de coupe (b-roll) proposes au bon moment.

Ou : sur les mots-concepts du texte (mots en couleur, noms forts) et sur les coupes franches a
l'interieur d'un plan (pause resserree) qu'un plan de coupe masque. Jamais pendant l'accroche ni sur la
derniere phrase de l'appel a l'action ; jamais sur un nom de marque, un petit mot, un chiffre ou un adverbe.
Quoi : les videos du dossier media/broll/ (indexees par CLIP une fois, comme la recherche ; les medias
deja pris dans les banques y sont ranges), en option les prises du projet qui ne sont pas face camera,
et les banques de medias libres (banques/) la ou la bibliotheque n'a rien de bon. 3 propositions par
emplacement ; le monteur choisit (un clic) ou ignore. En mode automatique, seul un plan de confiance
« haute » est insere (mot concret que l'IA juge illustrable, image tres proche, pas de visage d'inconnu
sauf si la phrase parle de personnes), au plus un toutes les ~12 s ; les autres restent des propositions
(reel.suggestions.broll)."""
import hashlib
import json
import re
import time
from pathlib import Path

import numpy as np

from . import media, montage, search
from .media import ROOT
from .reel import NUMBERS, STOP, WEAK, _brands, _rel
from .script import normalize

BROLL = ROOT / 'media/broll'
CACHE = ROOT / 'projects/_cache'
LOCAL_OK = 0.25    # CLIP : en dessous, la bibliotheque n'a rien de bon pour l'emplacement -> banques
LOCAL_AUTO = 0.31  # CLIP : confiance « haute » pour un plan de la bibliotheque (insere seul en mode automatique)
LOCAL_MARGE = 0.015  # ... et nettement meilleur que la 2e video de la bibliotheque (sinon CLIP hesite)
AUTO_ECART = 12.0  # mode automatique : au plus un plan de coupe toutes les ~12 s
BUDGET = 6         # banques : emplacements cherches au plus par passage
# personnes a l'image : un visage d'inconnu n'illustre rien, sauf si la phrase parle justement de personnes
PERSON_PROMPTS = ["a photo of a person's face", 'a portrait of a man', 'a portrait of a woman',
                  'a person talking on the phone', "the back of a person's head"]
THING_PROMPTS = ['a photo of an object', 'a photo of a room or a building', 'a chart or a computer screen',
                 'a close-up of hands and objects', 'a landscape or a street']
PEOPLE = re.compile(r'\b(person|persons|people|man|men|woman|women|guy|girl|boy|team|employee|employees|worker|staff|'
                    r'customer|customers|client|clients|agent|receptionist|sales\w*|business(man|woman|people)|'
                    r'entrepreneur|someone|colleague|manager|setter|caller|operator|face|portrait|family|crowd)\b', re.I)
# ... la phrase DITE (pas la description imaginee par l'IA, qui met presque toujours quelqu'un a l'image)
PEOPLE_FR = re.compile(r"\b(gens|personnes?|quelqu'un|employ[ée]e?s?|setters?|setteurs?|clients?|clientes?|[ée]quipes?|"
                       r"agents?|vendeu\w*|r[ée]ceptionnist\w*|patron\w*|entrepreneur\w*|coll[èe]gues?|famille|"
                       r"enfants?|femmes?|hommes?|people|person|employees?|customers?|team)\b", re.I)


def source_doc(path):
    """Source « plan de coupe » d'un fichier local (video ou image fixe), media optimise servi par /projects.
    Un media pris dans une banque garde son credit et ses mots-cles (fiche .json a cote du fichier)."""
    path = Path(path)
    sid = 'b' + hashlib.sha1(str(path.resolve()).lower().encode()).hexdigest()[:7]
    try:
        name = str(path.relative_to(BROLL))
    except ValueError:
        name = path.name
    credit = None
    meta_file = path.with_suffix('.json')
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding='utf-8'))
            credit = {'provider': meta.get('providerName') or meta.get('provider', ''), 'author': meta.get('author', ''),
                      'url': meta.get('pageUrl', ''), 'license': (meta.get('license') or {}).get('name', '')}
            if meta.get('tags'):
                name = ', '.join(meta['tags'][:3])
        except Exception:
            credit = None
    if path.suffix.lower() in media.IMAGE_EXT:
        from PIL import Image
        proxy = media.optimized_image(path, CACHE / 'optimises')
        with Image.open(proxy) as im:
            w, h = im.size
        doc = {'name': name, 'proxy': _rel(proxy), 'path': str(path.resolve()), 'duration': 60.0, 'width': w, 'height': h,
               'still': True}
    else:
        proxy = media.optimized(path, 0, CACHE / 'optimises')
        info = media.probe(proxy)
        doc = {'name': name, 'proxy': _rel(proxy), 'path': str(path.resolve()), 'duration': info['duration'],
               'width': info['width'], 'height': info['height']}
    doc.update({'samples': [], 'roomtone': None, 'kind': 'broll'})
    if credit:
        doc['credit'] = credit
    return sid, doc


def library():
    """Videos du dossier media/broll (dont celles deja prises dans les banques) : {id: source du reel}."""
    out = {}
    if not BROLL.exists():
        return out
    for path in media.list_videos(BROLL):
        try:
            sid, doc = source_doc(path)
        except Exception as e:  # fichier abime ou incomplet : ignore, les autres restent utilisables
            print(f'Plan de coupe ignore ({path.name}) : {e}')
            continue
        out[sid] = doc
    return out


def add_asset(project_dir, rid, provider, asset_id, kind='video', query=''):
    """Media d'une banque -> source du reel : telecharge une seule fois (media/broll/banques/), media optimise."""
    from . import banques
    reel = montage.load(project_dir, rid)
    path, meta = banques.download(provider, asset_id, kind, target=(reel['width'], reel['height']), query=query)
    sid, doc = source_doc(path)
    montage.update(project_dir, rid, lambda r: r['sources'].__setitem__(sid, doc))
    return {'source': sid, 'sources': {sid: doc}, 'media': meta}


def _content_word(words, k, brands):
    """Mot qui porte une idee illustrable : pas un petit mot, un mot vague, un chiffre, un adverbe ni un nom propre."""
    from .sobriete import nom_propre
    n = normalize(words[k]['w'].strip(' ,.!?;:«»"')).strip("'")
    if "'" in n:  # « qu'on », « l'experimenter » : on juge le mot apres l'apostrophe
        n = n.split("'")[-1]
    return not (len(n) < 4 or n in STOP or n in WEAK or n in NUMBERS or n in brands or n.endswith('ment')
                or n.isdigit() or nom_propre(words, k))


def _slots(reel, seg, min_gap=4.0, auto=False):
    """Emplacements : mots-concepts et coupes franches (temps du montage), hors accroche et hors derniere
    phrase de l'appel a l'action (relecture du monteur, sobriete.py)."""
    from .sobriete import reperes
    rep = reperes(reel, seg)
    total = seg['duration']
    lo, hi = rep['accroche'] + 0.3, min(total - 1.0, rep['cta'] if rep['cta'] is not None else total - 1.0)
    slots = []
    words = seg['words']
    brands = {normalize(b).strip("'") for b in _brands(reel)}
    # coupes franches dans un meme plan (resserrage) : un plan de coupe les masque ; le mot retenu est le mot
    # fort le plus proche (jamais « des », « qu'on »...), sinon aucun : la coupe reste une simple proposition
    video = seg['video']
    for a, b in zip(video, video[1:]):
        at = round(max(0, b['out_start'] - 0.6), 2)
        if a['clip'] == b['clip'] and b['out_start'] > 1.5 and lo <= at and at + 1.6 <= hi:
            near = [k for k, w in enumerate(words) if abs(w['start'] - b['out_start']) < 2.0]
            ctx = ' '.join(words[k]['w'] for k in near)
            strong = sorted((k for k in near if _content_word(words, k, brands)),
                            key=lambda k: (not words[k].get('hl'), abs(words[k]['start'] - b['out_start'])))
            slots.append({'at': at, 'duration': 1.6, 'word': words[strong[0]]['w'].strip(' ,.!?«»') if strong else '',
                          'context': ctx, 'reason': 'masquer la coupe'})
    # mots-concepts : seulement les mots mis en valeur (en couleur, ou proposes par l'IA) ; un simple mot long
    # (« puissiez », « concerne ») n'est pas une idee a illustrer
    proposed = {(c, i) for c, idx in ((reel.get('suggestions') or {}).get('words') or {}).items() for i in idx}
    for k, w in enumerate(words):
        if w['start'] < lo or w['start'] + 1.8 > hi or not _content_word(words, k, brands):
            continue
        strong = w.get('hl') or (w.get('clip'), w.get('index')) in proposed
        if not strong:
            continue
        ctx = ' '.join(x['w'] for x in words if abs(x['start'] - w['start']) < 1.6)
        near = ' '.join(x['w'] for x in words[max(0, k - 2):k + 3])
        slots.append({'at': round(max(0, w['start'] - 0.15), 2), 'duration': 1.8, 'word': w['w'].strip(' ,.!?«»'), 'context': ctx,
                      'near': near, 'reason': 'illustrer « %s »' % w['w'].strip(' ,.!?«»'), 'hl': bool(w.get('hl'))})
    # un emplacement toutes les ~4 s au plus : priorite aux coupes a masquer puis aux mots en couleur (en mode
    # automatique, aux mots : une coupe n'est jamais masquee seule) ; un meme mot n'est illustre qu'une fois
    slots.sort(key=lambda s: ((s['reason'] == 'masquer la coupe') if auto else (s['reason'] != 'masquer la coupe'),
                              not s.get('hl'), s['at']))
    kept, words_used = [], set()
    for s in slots:
        key = normalize(s['word']).strip("'") if s['reason'] != 'masquer la coupe' else None
        if key in words_used:
            continue
        if all(abs(s['at'] - k['at']) >= min_gap for k in kept):
            kept.append(s)
            if key:
                words_used.add(key)
    return sorted(kept, key=lambda s: s['at'])


def _translate(texts):
    """CLIP comprend l'anglais : traduction groupee par l'IA locale (sinon texte tel quel)."""
    from . import llm
    if not texts or not llm.available():
        return texts
    try:
        with llm.session():
            data = llm.ask_json('Tu traduis en anglais des descriptions de plans video. Reponds en JSON.',
                                'Traduis chaque element en une courte description visuelle en anglais (ce qu\'on verrait a l\'image). '
                                'Reponds {"en": [...]} dans le meme ordre.\n' + json.dumps(texts, ensure_ascii=False))
        en = data.get('en') or []
        return [str(e) for e in en] if len(en) == len(texts) else texts
    except Exception:
        return texts


def suggest(project_dir, rid, include_rushes=False, external=True, auto=False):
    """Propositions de plans de coupe pour un reel : bibliotheque media/broll (+ prises du projet), puis banques
    pour les emplacements ou la bibliotheque n'a rien de bon. auto=True : insere les plans surs."""
    import torch
    from . import banques
    reel = montage.load(project_dir, rid)
    candidates = dict(library())
    if include_rushes:
        # autres prises du projet (plans d'illustration tournes avec les rushs, prises non retenues)
        project = json.loads((Path(project_dir) / 'project.json').read_text(encoding='utf-8'))
        used = {c['source'] for c in reel['clips']}
        for sid, s in project['sources'].items():
            if sid in used:
                continue
            if sid in reel['sources']:
                candidates[sid] = reel['sources'][sid]
                continue
            proxy = media.optimized(s['path'], s.get('rotate', 0), CACHE / 'optimises')
            info = media.probe(proxy)
            candidates[sid] = {'name': s['name'], 'proxy': _rel(proxy), 'path': s['path'], 'duration': s['duration'],
                               'width': info['width'], 'height': info['height'], 'samples': [], 'roomtone': None, 'kind': 'broll'}
    seg = montage.compute(reel)
    slots = _slots(reel, seg, auto=auto)
    for s in slots:
        s['candidates'], s['externes'] = [], []
    use_banks = external and bool(banques.active('video'))
    if not slots or (not candidates and not use_banks):
        msg = ('Aucun moment a illustrer dans ce montage.' if not slots else
               'Aucune video dans media/broll et aucune banque configuree : ajoute des plans de coupe dans ce dossier ou une cle dans cles-api.env.')
        return {'slots': slots, 'sources': {}, 'inseres': 0, 'broll': reel.get('broll') or [], 'message': msg}
    texts = [s['context'] or s['word'] for s in slots]
    # un seul passage de l'IA locale : recherches pour les banques + description anglaise pour CLIP ; en mode
    # automatique, l'IA dit aussi si la phrase gagne a etre illustree (sans son avis : rien n'est insere seul)
    plans = banques.queries_for([{'text': t, 'context': ''} for t in texts]) if use_banks or auto else []
    queries = [p['description'] for p in plans] if plans else _translate(texts)
    for k, s in enumerate(slots):
        s['illustrable'] = bool(plans[k]['illustrable']) if plans else None
        s['ia'] = bool(plans[k]['llm']) if plans else False
        s['description'] = queries[k]
        s['requetes'] = list(plans[k]['queries']) if plans else []
    if candidates:
        model, _, tok, dev = search._model()
        with torch.no_grad():
            q = model.encode_text(tok(queries).to(dev)).float()
            q = (q / q.norm(dim=-1, keepdim=True)).cpu().numpy()
            pk = model.encode_text(tok(PERSON_PROMPTS + THING_PROMPTS).to(dev)).float()
            pk = (pk / pk.norm(dim=-1, keepdim=True)).cpu().numpy()
        index = {}
        for sid, s in candidates.items():
            try:
                index[sid] = search.index_source({**s, 'proxy': str(montage.proxy_path(s))}, use_vision=False)
            except Exception as e:  # un fichier abime de la bibliotheque ne bloque pas les autres
                print(f"Plan de coupe ignore ({s.get('name')}) : {e}")
        used_at = {}
        for k, slot in enumerate(slots):
            scored = []
            for sid, idx in index.items():
                emb = np.array(idx['emb'])
                if not len(emb):
                    continue
                dur = candidates[sid]['duration']
                sims = emb @ q[k]
                # meilleure seconde de la prise ; on evite de reprendre le meme instant deux fois
                for j in np.argsort(-sims)[:3]:
                    t = float(idx['times'][j])
                    if any(abs(t - u) < 2 for u in used_at.get(sid, [])):
                        continue
                    t = max(0.0, min(t - 0.3, dur - slot['duration'] - 0.05))
                    # une personne a l'image ? (CLIP : visages, nuques, gens au telephone contre objets et lieux)
                    logits = 100 * (pk @ emb[j])
                    p = np.exp(logits - logits.max())
                    person = float(p[:len(PERSON_PROMPTS)].sum() / p.sum())
                    scored.append({'source': sid, 'name': candidates[sid]['name'], 't': round(t, 2), 'score': round(float(sims[j]), 3),
                                   'proxy': candidates[sid]['proxy'], 'personne': round(person, 2)})
                    break
            scored.sort(key=lambda c: -c['score'])
            slot['candidates'] = scored[:3]
            if scored:
                used_at.setdefault(scored[0]['source'], []).append(scored[0]['t'])
                # confiance du meilleur plan : « haute » seulement si CLIP est net (score et avance sur le 2e)
                gap = scored[0]['score'] - (scored[1]['score'] if len(scored) > 1 else 0.0)
                scored[0]['confidence'] = ('haute' if scored[0]['score'] >= LOCAL_AUTO and gap >= LOCAL_MARGE else
                                           'moyenne' if scored[0]['score'] >= LOCAL_OK else 'faible')

    messages = []
    if use_banks and plans:
        # banque : seulement la ou la bibliotheque n'a rien de bon, et au plus BUDGET emplacements par passage
        # (mots en couleur d'abord) : l'API est faite pour des requetes humaines, pas en masse
        weak = [k for k, s in enumerate(slots) if not (s['candidates'] and s['candidates'][0]['score'] >= LOCAL_OK) and plans[k]['illustrable']]
        weak.sort(key=lambda k: (not slots[k].get('hl'), slots[k]['at']))
        if len(weak) > BUDGET:
            messages.append(f'Banque : {BUDGET} moments sur {len(weak)} cherches (les plus importants).')
        for k in weak[:BUDGET]:
            s, plan = slots[k], plans[k]
            s['requetes'] = plan['queries']
            try:
                found = banques.gather(plan['queries'][:2 if auto else 3], 'video', plan['lang'], per_query=15, limit=30)
            except banques.BanqueErreur as e:
                messages.append(str(e))
                break
            ctx = {'queries': plan['queries'], 'description': plan['description'], 'target': (reel['width'], reel['height']),
                   'need': s['duration'], 'style': reel.get('template'), 'llm': plan['llm']}
            s['externes'] = banques.rank(found, ctx, analyse_top=2 if auto else 0)[:3]

    inserted = []
    if auto:
        # l'IA juge aussi si le mot est une chose concrete a montrer (« telephone », « vacances ») et pas une idee
        # abstraite (« temps », « risque », « rapide ») : une image au hasard n'illustre pas une idee
        concept = [s for s in slots if s['reason'] != 'masquer la coupe' and s.get('word')]
        for s, ok in zip(concept, _concrete(concept)):
            s['concret'] = ok
        taken = [float(b.get('at', 0)) for b in reel.get('broll') or []]
        # les plans les plus surs d'abord (mots en couleur), puis un seul toutes les ~12 s
        for s in sorted(slots, key=lambda s: (not s.get('hl'), -(s['candidates'][0]['score'] if s['candidates'] else 0))):
            why = _not_auto(s)
            if why:
                s['pourquoi'] = why
                continue
            if any(abs(s['at'] - t) < AUTO_ECART for t in taken):
                s['pourquoi'] = 'un seul plan de coupe toutes les ~12 s'
                continue
            local = s['candidates'][0] if _safe_local(s) else None
            ext = next((c for c in s['externes'] if _safe_external(s, c)), None)
            # pas de mode fige : plein ecran ou encadre est choisi a l'affichage selon le format (brollMode)
            if local:
                inserted.append({'source': local['source'], 'in': local['t'], 'at': s['at'], 'duration': s['duration'], 'word': s['word'],
                                 'auto': True, 'reason': s['reason'], 'confidence': 'haute'})
            elif ext:
                try:
                    added = add_asset(project_dir, rid, ext['provider'], ext['id'], ext['type'], ext.get('query', ''))
                except banques.BanqueErreur as e:
                    messages.append(str(e))
                    continue
                candidates[added['source']] = added['sources'][added['source']]
                inserted.append({'source': added['source'], 'in': ext['start'], 'at': s['at'], 'duration': s['duration'], 'word': s['word'],
                                 'auto': True, 'reason': s['reason'], 'confidence': 'haute'})
            else:
                s['pourquoi'] = 'aucune image assez sûre (confiance moyenne ou faible, ou visage d\'un inconnu)'
                continue
            taken.append(s['at'])

    # seules les sources proposees (ou inserees) entrent dans le reel : la bibliotheque peut etre grande
    wanted = {c['source'] for s in slots for c in s['candidates']} | {b['source'] for b in inserted}
    added_count = []
    used = {b['at'] for b in inserted}
    # mode automatique : ce qui n'est pas insere reste une proposition visible dans l'editeur
    pending = [{'at': s['at'], 'duration': s['duration'], 'word': s['word'], 'context': s['context'], 'reason': s['reason'],
                'pourquoi': s.get('pourquoi', ''),
                'candidates': [{k: c[k] for k in ('source', 'name', 't', 'score', 'confidence', 'personne') if k in c}
                               for c in s['candidates'][:3]],
                'externes': [{k: c.get(k) for k in ('provider', 'id', 'type', 'preview', 'score', 'confidence', 'start')}
                             for c in s['externes'][:3]]}
               for s in slots if s['at'] not in used and (s['candidates'] or s['externes'])] if auto else None

    def apply(r):
        r['sources'].update({sid: candidates[sid] for sid in wanted if sid in candidates and sid not in r['sources']})
        if inserted:
            current = list(r.get('broll') or [])
            stamp = int(time.time() * 1000)
            for k, b in enumerate(inserted):
                if not any(abs(x['at'] - b['at']) < 1.0 for x in current):
                    current.append({'id': f'b{stamp:x}{k}', **b})
                    added_count.append(b)
            r['broll'] = sorted(current, key=lambda x: x['at'])
        if pending is not None:
            r.setdefault('suggestions', {'banners': [], 'words': {}, 'emojis': {}})['broll'] = pending

    reel = montage.update(project_dir, rid, apply)
    return {'slots': slots, 'sources': {sid: reel['sources'][sid] for sid in wanted if sid in reel['sources']},
            'inseres': len(added_count), 'broll': reel.get('broll') or [], 'message': ' '.join(messages)}


def _not_auto(slot):
    """Pourquoi un emplacement ne recoit jamais de plan seul (None : il peut, si l'image est sure)."""
    if slot['reason'] == 'masquer la coupe':
        return 'coupe à masquer : pas une idée à illustrer, à décider par le monteur'
    if not slot.get('word'):
        return 'aucun mot fort'
    if not slot.get('ia'):
        return "l'IA locale n'a pas pu juger la phrase"
    if slot.get('illustrable') is False:
        return "l'IA juge que la phrase ne gagne rien à être illustrée"
    if not slot.get('concret'):
        return f"« {slot['word']} » est une idée, pas une chose concrète à montrer"
    return None


def _concrete(slots):
    """Mode automatique : le mot designe-t-il, dans sa phrase, une chose concrete et filmable ? (IA locale, un appel,
    temperature 0). Sans reponse sure : non (rien n'est insere seul)."""
    from . import llm
    if not slots or not llm.available():
        return [False] * len(slots)
    lines = '\n'.join(f'[{i}] mot « {s["word"]} » dans « {s["context"]} »' for i, s in enumerate(slots))
    try:
        with llm.session():
            data = llm.ask_json(llm.EDITOR,
                                "Pour chaque mot, dans sa phrase : designe-t-il une chose CONCRETE qu'on peut filmer et que le "
                                "spectateur s'attend a voir (un objet, un lieu, une action visible : telephone, bureau, argent, "
                                "vacances, maladie) ? Un mot abstrait (temps, risque, rapide, cher, heures, interet, processus), "
                                "un adverbe, un verbe vague, un nom de marque ou un chiffre : false.\n" + lines +
                                '\nReponds avec CHAQUE numero : {"concret": {"0": true ou false, "1": true ou false, ...}}',
                                temperature=0.0, max_tokens=80 + 12 * len(slots))
        ok = data.get('concret') or {}
        if isinstance(ok, list):  # ancienne forme : une liste, acceptee seulement si elle est complete
            ok = {str(i): x for i, x in enumerate(ok)} if len(ok) == len(slots) else {}
        # un numero oublie par l'IA vaut « non »
        return [ok.get(str(i)) is True or str(ok.get(str(i))).strip().lower() in ('true', 'oui', 'yes')
                for i in range(len(slots))]
    except Exception as e:
        print(f'IA locale indisponible ({e}) : aucun plan de coupe insere seul.')
    return [False] * len(slots)


def _about_people(slot):
    """La phrase dite parle-t-elle de personnes (employe, setter, clients, gens...) autour du mot illustre ?"""
    return bool(PEOPLE_FR.search(str(slot.get('near') or slot.get('word') or '')))


def _safe_local(slot):
    """Plan de la bibliotheque insere seul : confiance haute, et pas de personne a l'image si la phrase n'en parle pas."""
    c = slot['candidates'][0] if slot['candidates'] else None
    if not c or c.get('confidence') != 'haute':
        return False
    return c.get('personne', 1.0) < 0.5 or _about_people(slot)


def _safe_external(slot, c):
    """Media d'une banque insere seul : confiance haute (banques.rank) et pas de personne si la phrase n'en parle pas."""
    if not (c.get('auto') and c.get('confidence') == 'haute'):
        return False
    person = bool(PEOPLE.search(' '.join(str(t) for t in c.get('tags') or [])))
    return not person or _about_people(slot)
