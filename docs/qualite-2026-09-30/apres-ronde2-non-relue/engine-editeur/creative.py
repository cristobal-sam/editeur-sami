"""Directeur créatif V2.

Ce module ne rend rien lui-même. Il lit le montage entier avant l'habillage et
produit une intention commune pour les modules existants : arc narratif,
fonction de chaque passage, rythme, langage visuel et repères sonores.

Le plan est toujours calculable sans IA. L'IA locale peut préciser l'audience,
la promesse et la fonction des phrases, mais ses réponses sont validées contre
les phrases réellement dites. Aucun chiffre, résultat ou objet n'est inventé.
"""
import re

from . import verrous
from .script import normalize

VERSION = 2
ROLES = ('accroche', 'probleme', 'solution', 'preuve', 'explication', 'cta')

PROBLEM = re.compile(r"\b(probleme|perd\w*|rat\w*|attend\w*|trop tard|cher|cout\w*|diffic\w*|sans|jamais|"
                     r"problem|lose|miss\w*|wait\w*|expensive|difficult)\b", re.I)
SOLUTION = re.compile(r"\b(solution|permet\w*|automat\w*|repond\w*|qualifi\w*|deleg\w*|transfer\w*|"
                      r"grace|avec|solution|allow\w*|automat\w*|reply|qualif\w*|delegate\w*)\b", re.I)
PROOF = re.compile(r"\b(resultat\w*|fois|pourcent|%|client\w*|gratuit\w*|semaine\w*|jour\w*|heure\w*|"
                   r"result\w*|times|percent|free|week\w*|day\w*|hour\w*)\b|\d", re.I)
CTA = re.compile(r"\b(cliqu\w*|appuy\w*|bouton|contact\w*|reserv\w*|inscri\w*|en savoir plus|"
                 r"click\w*|button|contact\w*|book\w*|learn more)\b", re.I)

LABELS = {
    'accroche': 'Accroche', 'probleme': 'Tension', 'solution': 'Révélation',
    'preuve': 'Preuve', 'explication': 'Démonstration', 'cta': "Passage à l'action",
}
INTENTS = {
    'accroche': "Visage et phrase seuls : obtenir l'attention sans masquer le message.",
    'probleme': "Rendre la friction concrète avec un contraste sobre ou une situation réelle.",
    'solution': "Montrer le mécanisme, le parcours ou l'interface au moment exact où il est expliqué.",
    'preuve': "Donner la priorité au chiffre ou au fait réellement prononcé, sans statistique ajoutée.",
    'explication': "Laisser respirer la personne et illustrer seulement l'idée indispensable.",
    'cta': "Nettoyer le cadre et faire du geste demandé l'unique point focal.",
}


def _storyboard(reel, beats, template):
    """Traduit l'arc narratif en décisions de réalisation exécutables.

    Le choix du moteur est volontairement conservateur : la prise réelle est le
    défaut, Remotion sert les informations, et Blender n'est autorisé qu'avec
    une vraie photo ou un modèle fourni.
    """
    mode = ((template or {}).get('design') or (reel.get('design') or {})).get('mode')
    design = reel.get('design') or {}
    real_product = bool(design.get('productImage') or design.get('productModel'))
    shots = []
    for beat in beats:
        role = beat['role']
        engine = 'prise-originale'
        shot = 'face-camera'
        composition = "Sujet lisible, regard prioritaire, sous-titres dégagés."
        asset = None
        fallback = "Conserver la meilleure prise avec un recadrage motivé."
        if role == 'accroche':
            shot = 'hero-face'
            composition = "Gros plan propre, aucun panneau concurrent, mouvement très léger vers le visage."
        elif role == 'probleme':
            shot = 'tension-reelle'
            composition = "Visage dominant, contraste plus dense ; une seule illustration si elle rend la friction concrète."
            asset = {'kind': 'broll-reel', 'status': 'optionnel',
                     'brief': "Situation réelle correspondant exactement au problème prononcé."}
        elif role == 'solution':
            engine = 'remotion-ui' if mode in ('produit', 'tech', 'infographie') else 'remotion-typographie'
            shot = 'revelation-interface' if engine == 'remotion-ui' else 'revelation-texte'
            composition = "Révélation synchronisée au verbe d'action, interface hors du visage, profondeur progressive."
            asset = {'kind': 'interface', 'status': 'prêt',
                     'brief': "Parcours construit uniquement avec les actions réellement dites."}
            norm_evidence = _norm_text(beat['evidence'])
            if re.search(r'pas juste|au hasard|random', norm_evidence):
                # Une preuve de sérieux portée par la personne est plus crédible qu'un faux badge d'interface.
                engine = 'prise-originale'
                shot = 'preuve-humaine'
                composition = "Conserver le visage et les gestes : la crédibilité humaine porte cette explication."
                asset = None
                fallback = "Recadrage lent vers le visage, sans panneau supplémentaire."
            if mode == 'produit' and real_product:
                engine = 'blender'
                shot = 'produit-hero-3d'
                asset = {'kind': 'produit-réel', 'status': 'fourni',
                         'brief': "Utiliser uniquement la photo ou le modèle produit attaché au montage."}
                fallback = "Interface Remotion liée aux paroles si la ressource 3D échoue."
        elif role == 'preuve':
            engine = 'remotion-graphisme'
            shot = 'preuve-chiffree'
            composition = "Chiffre ou fait réel en premier plan ; la personne reste visible comme source du propos."
            asset = {'kind': 'donnée-prononcée', 'status': 'prêt',
                     'brief': "Afficher exclusivement le chiffre ou le fait présent dans la phrase."}
        elif role == 'cta':
            engine = 'remotion-ui'
            shot = 'cta-unique'
            composition = "Cadre nettoyé, bouton exact, une seule action et aucune métrique concurrente."
            asset = {'kind': 'cta', 'status': 'prêt', 'brief': "Reprendre mot pour mot l'action prononcée."}
        shots.append({
            'id': f"shot-{beat['id']}", 'beat': beat['id'], 'role': role,
            'start': beat['start'], 'end': beat['end'], 'purpose': beat['visualIntent'],
            'evidence': beat['evidence'], 'shot': shot, 'engine': engine,
            'composition': composition, 'asset': asset, 'fallback': fallback,
            'reason': f"Décision motivée par le passage « {beat['evidence'][:90]} ».",
            'status': 'planifié',
        })
    return shots


def _clean(words):
    return ' '.join(w.get('w', '').strip() for w in words if not w.get('cut') and not w.get('hide')).strip()


def _norm_text(text):
    """Normalisation comparable qui conserve les séparations entre les mots."""
    return ' '.join(filter(None, (normalize(part).strip("'") for part in re.split(r"[\s\-–—]+", str(text)))))


def _sentences(reel):
    """Phrases avec leurs temps réels dans le montage, après coupes et vitesses."""
    from .montage import sentences
    out, elapsed = [], 0.0
    for clip in reel.get('clips') or []:
        speed = clip.get('speed') or 1
        for first, last in sentences(clip):
            visible = [(i, w) for i, w in enumerate(clip['words'][first:last + 1])
                       if not w.get('cut') and not w.get('hide') and w.get('w', '').strip()]
            if not visible:
                continue
            i0 = first + visible[0][0]
            i1 = first + visible[-1][0]
            text = _clean(clip['words'][i0:i1 + 1])
            if not text:
                continue
            start = elapsed + max(0, clip['words'][i0]['start'] - clip['in']) / speed
            end = elapsed + max(0, clip['words'][i1]['end'] - clip['in']) / speed
            out.append({'id': f"p{len(out) + 1}", 'clip': clip['id'], 'block': clip.get('block'),
                        'index': i0, 'lastIndex': i1, 'start': round(start, 3), 'end': round(end, 3),
                        'text': text})
        elapsed += max(0, clip.get('out', 0) - clip.get('in', 0)) / speed
    return out, elapsed


def _role(sentence, total, cta_block):
    text = _norm_text(sentence['text'])
    start = sentence['start']
    if start <= min(6.0, total * .12):
        return 'accroche'
    if sentence.get('block') == cta_block or (start >= total * .68 and CTA.search(text)):
        return 'cta'
    scores = {
        'probleme': 2 if PROBLEM.search(text) else 0,
        'solution': 2 if SOLUTION.search(text) else 0,
        'preuve': 2 if PROOF.search(text) else 0,
    }
    if max(scores.values()) > 0:
        if scores['preuve'] and re.search(r'\d|fois|%|pourcent|garanti|gratuit|semaine|resultat', text):
            return 'preuve'
        # Une phrase qui explique un mécanisme avec un chiffre reste une preuve
        # seulement si le chiffre/résultat est central ; sinon elle révèle la solution.
        if scores['solution'] and scores['preuve'] and not re.search(r'\d|fois|%|pourcent', text):
            return 'solution'
        return max(scores, key=scores.get)
    return 'explication'


def _merge(sentences, total, cta_block):
    beats = []
    for sentence in sentences:
        role = _role(sentence, total, cta_block)
        if beats and beats[-1]['role'] == role and sentence['start'] - beats[-1]['end'] < 2.0:
            beats[-1]['end'] = sentence['end']
            beats[-1]['sentences'].append(sentence['id'])
            beats[-1]['evidence'] = (beats[-1]['evidence'] + ' ' + sentence['text'])[:180]
            continue
        beats.append({'id': f"b{len(beats) + 1}", 'role': role, 'label': LABELS[role],
                      'start': sentence['start'], 'end': sentence['end'], 'clip': sentence['clip'],
                      'index': sentence['index'], 'sentences': [sentence['id']],
                      'evidence': sentence['text'][:180], 'visualIntent': INTENTS[role]})
    # Un plan utile reste lisible : fusionner les passages neutres très courts avec leur voisin.
    compact = []
    for beat in beats:
        if beat['role'] == 'explication' and beat['end'] - beat['start'] < 2.2 and compact:
            compact[-1]['end'] = beat['end']
            compact[-1]['sentences'] += beat['sentences']
            compact[-1]['evidence'] = (compact[-1]['evidence'] + ' ' + beat['evidence'])[:180]
        else:
            compact.append(beat)
    for i, beat in enumerate(compact):
        beat['id'] = f'b{i + 1}'
        beat['intensity'] = round(min(1, .42 + i / max(1, len(compact) - 1) * .45
                                      + (.12 if beat['role'] in ('preuve', 'cta') else 0)), 2)
    return compact


def _direction(reel, info, template, total, sentences):
    words = sum(len(s['text'].split()) for s in sentences)
    rate = words / max(1, total)
    mode = ((template or {}).get('design') or (reel.get('design') or {})).get('mode')
    density = ((template or {}).get('design') or {}).get('density', 3)
    rhythm = 'nerveux' if rate >= 3.2 else 'posé' if rate < 2.15 else 'progressif'
    return {
        'rhythm': rhythm,
        'wordsPerSecond': round(rate, 2),
        'visualGrammar': {
            'produit': 'studio cinématique + interfaces motivées',
            'tech': 'face caméra + notifications utiles',
            'documentaire': 'observation + titres discrets',
            'luxe': 'plans longs + typographie minimale',
            'editorial': 'mots forts + compositions éditoriales',
        }.get(mode, 'face caméra + accents motivés'),
        'density': max(1, min(5, int(density or 3))),
        'accent': (reel.get('design') or {}).get('accent') or (reel.get('style') or {}).get('highlight'),
        'objective': (info or {}).get('typeLabel') or (info or {}).get('type') or 'Vidéo claire et mémorable',
        'title': (info or {}).get('titre') or reel.get('title') or '',
    }


def _sound(beats, reel):
    cues = []
    for beat in beats:
        if beat['role'] == 'solution' and beat['start'] > 4:
            cues.append({'t': beat['start'], 'name': 'whoosh-court', 'reason': 'entrée de la solution'})
            break
    cta = next((b for b in beats if b['role'] == 'cta'), None)
    if cta:
        cues.append({'t': max(0, cta['start'] - 1.4), 'name': 'riser', 'reason': "préparer l'appel à l'action"})
    return {'arc': 'sobre au départ, montée à la révélation, espace net pour la conclusion', 'cues': cues[:2],
            'music': (reel.get('music') or {}).get('mood')}


def build(reel, info=None, template=None):
    """Construit un plan sûr et déterministe à partir du montage effectivement prononcé."""
    sentences, total = _sentences(reel)
    beats = _merge(sentences, total, reel.get('ctaBlock')) if sentences else []
    covered = sum(max(0, b['end'] - b['start']) for b in beats)
    roles = [b['role'] for b in beats]
    confidence = .45 + .1 * bool('accroche' in roles) + .15 * bool('solution' in roles) \
        + .15 * bool('preuve' in roles) + .15 * bool('cta' in roles)
    direction = _direction(reel, info, template, total, sentences)
    storyboard = _storyboard(reel, beats, template)
    assets = []
    for shot in storyboard:
        asset = shot.get('asset')
        if asset and asset.get('status') not in ('prêt', 'fourni'):
            assets.append({'shot': shot['id'], **asset, 'required': asset.get('status') != 'optionnel'})
    return {
        'version': VERSION, 'enabled': True, 'source': 'règles vérifiables',
        'summary': f"{direction['title'] or 'Vidéo'} : {len(beats)} temps narratifs, rythme {direction['rhythm']}.",
        'direction': direction, 'beats': beats, 'storyboard': storyboard, 'assets': assets,
        'sound': _sound(beats, reel),
        'guardrails': ["Aucun visuel sans rapport avec les mots prononcés.",
                       "Un seul message principal à l'écran.",
                       "Aucun effet automatique ne couvre l'accroche.",
                       "Les chiffres et résultats doivent être réellement dits."],
        'quality': {'confidence': round(min(1, confidence), 2),
                    'coverage': round(min(1, covered / max(1, total)), 2),
                    'hasHook': 'accroche' in roles, 'hasSolution': 'solution' in roles,
                    'hasProof': 'preuve' in roles, 'hasCta': 'cta' in roles},
    }


def apply(reel, info=None, template=None):
    """Pose le plan sur le reel. Un plan verrouillé par le monteur est préservé, ainsi que tout élément verrouillé ou
    retouché (verrous.sous_protection)."""
    old = reel.get('creativePlan') or {}
    if verrous.is_locked(old):
        return old
    with verrous.sous_protection(reel):
        plan = build(reel, info, template)
        reel['creativePlan'] = plan
        # Les styles sans bruitages de transition reçoivent au plus deux ponctuations motivées.
        # Les bruitages ajoutés à la main, verrouillés ou retouchés sont toujours conservés.
        sfx = reel.get('sfx') or {}
        if sfx.get('enabled') and not sfx.get('transition'):
            kept = [e for e in sfx.get('extra', []) if not e.get('creative') or verrous.protege(e)]
            automatic = [{**cue, 'creative': True} for cue in plan['sound']['cues']
                         if not any(k.get('name') == cue['name'] and abs(float(k.get('t', -99)) - cue['t']) < .3 for k in kept)]
            sfx['extra'] = kept + automatic
            reel['sfx'] = sfx
    return plan


def beat_at(plan, at):
    """Temps narratif auquel appartient un élément visuel."""
    beats = (plan or {}).get('beats') or []
    if not beats:
        return None
    inside = next((b for b in beats if b['start'] - .25 <= at <= b['end'] + .4), None)
    return inside or min(beats, key=lambda b: abs(b['start'] - at))


def direct_scenes(reel, scenes, times):
    """Relie chaque scène fabriquée par la galerie à une raison narrative explicite."""
    plan = reel.get('creativePlan') or {}
    for scene in scenes:
        at = times.get((scene.get('clip'), scene.get('index')), 0)
        beat = beat_at(plan, at)
        if not beat:
            continue
        scene['creativeBeat'] = beat['id']
        scene['creativeRole'] = beat['role']
        scene['creativeReason'] = beat['visualIntent']
        shot = next((s for s in (plan.get('storyboard') or []) if s.get('beat') == beat['id']), None)
        if shot:
            scene['creativeShot'] = shot['id']
    # Audit immédiat : ce qui existe déjà dans le reel devient « prêt ». Rien de lourd n'est lancé ici.
    # Un plan verrouillé par le monteur est figé, audit compris.
    if verrous.is_locked(plan):
        return scenes
    graphics = reel.get('graphics') or []
    for shot in plan.get('storyboard') or []:
        refs = [s['id'] for s in scenes if s.get('creativeShot') == shot['id'] and not s.get('hidden')]
        refs += [g['id'] for g in graphics if shot['start'] - .25 <= g.get('at', -99) <= shot['end'] + .4
                 and not g.get('suggested')]
        if shot['engine'] == 'prise-originale':
            shot['status'] = 'prêt'
            shot['execution'] = ['prise-originale']
        elif refs:
            shot['status'] = 'prêt'
            shot['execution'] = refs
        elif shot['engine'] == 'blender' and (reel.get('design') or {}).get('productVideo'):
            shot['status'] = 'prêt'
            shot['execution'] = ['design.productVideo']
        else:
            shot['status'] = 'planifié'
            shot['execution'] = []
    return scenes
