"""Continuite / faux raccords (experimental) : a chaque coupe, on compare la derniere image du plan
qui se termine et la premiere du plan suivant.

1. Mesures simples (toujours) : couleur du haut du corps (vetements), position et taille du visage
   (saut de cadre), lumiere generale.
2. Vision de l'IA locale (Qwen, si disponible) : vetements, accessoires, coiffure, objet en main, decor.
   Une alerte n'est gardee que si l'IA la confirme avec les images inversees (sinon trop d'inventions).
Resultat : alertes sur la timeline, a verifier par le monteur (l'IA se trompe encore souvent)."""
import io
import json

import numpy as np

from . import media, montage

PROMPT = ("Voici deux images qui se suivent dans un montage video (image 1 = fin d'un plan, image 2 = debut du plan suivant, "
          "la meme personne). Cherche seulement les FAUX RACCORDS d'objets : vetement different, accessoire qui apparait ou "
          "disparait (lunettes, bijou, montre, micro), coiffure, objet tenu en main qui change, decor ou objet du decor qui change. "
          "IGNORE completement : position et gestes des mains, posture, expression, bouche, regard, cadrage, legere difference "
          "de lumiere : ce sont des changements normaux entre deux prises. "
          'Reponds en JSON : {"differences": ["courte phrase", ...], "gravite": 0 a 3} '
          "(0 = aucun probleme, 3 = faux raccord evident). Pas d'invention : si tu n'es pas sur, liste vide et gravite 0.")


def _frame(src, t):
    rgb = media.sample_frames(montage.proxy_path(src), fps=10, width=384, start=max(0.0, t), duration=0.12)
    return rgb[0][1] if rgb else None


def _torso(rgb, face):
    """Couleur moyenne sous le visage (haut du corps / vetements)."""
    h, w = rgb.shape[:2]
    if face:
        x0, x1 = int((face['cx'] - face['w']) * w), int((face['cx'] + face['w']) * w)
        y0, y1 = int((face['cy'] + face['h'] * 0.9) * h), int((face['cy'] + face['h'] * 2.2) * h)
    else:
        x0, x1, y0, y1 = int(w * 0.3), int(w * 0.7), int(h * 0.6), int(h * 0.9)
    patch = rgb[max(0, y0):max(1, min(h, y1)), max(0, x0):max(1, min(w, x1))].reshape(-1, 3)
    return patch.mean(axis=0) if len(patch) else None


def _measure(a, b):
    from .analyze import detect_face
    fa, fb = detect_face(a), detect_face(b)
    notes, grav = [], 0
    ta, tb = _torso(a, fa), _torso(b, fb)
    if ta is not None and tb is not None:
        d = float(np.linalg.norm(ta - tb))
        if d > 45:
            notes.append(f'couleur des vetements differente (ecart {d:.0f})')
            grav = max(grav, 2 if d > 70 else 1)
    if fa and fb:
        size = fb['w'] / max(1e-3, fa['w'])
        if 0.85 < size < 1.18 and abs(fa['cx'] - fb['cx']) + abs(fa['cy'] - fb['cy']) < 0.05:
            notes.append('meme cadre avant et apres : coupe franche visible (zoom, plan de coupe ou J-cut conseille)')
            grav = max(grav, 1)
    la, lb = float(a.mean()), float(b.mean())
    if abs(la - lb) > 28:
        notes.append(f'lumiere tres differente ({la:.0f} -> {lb:.0f})')
        grav = max(grav, 1)
    return notes, grav


def check(project_dir, rid, use_vision=True):
    reel = montage.load(project_dir, rid)
    seg = montage.compute(reel)
    video = seg['video']
    pairs = []
    for a, b in zip(video, video[1:]):
        jump = a['source'] != b['source'] or abs(b['src_in'] - a['src_out']) > 0.2
        if jump:
            pairs.append((a, b))
    results = []
    vision = None
    if use_vision:
        from . import llm
        if llm.available() and llm.MMPROJ.exists():
            vision = llm
    ctx = vision.session(vision=True) if vision else None
    if ctx:
        ctx.__enter__()
    try:
        for a, b in pairs:
            ia = _frame(reel['sources'][a['source']], a['src_out'] - 0.1)
            ib = _frame(reel['sources'][b['source']], b['src_in'] + 0.05)
            if ia is None or ib is None:
                continue
            notes, grav = _measure(ia, ib)
            if vision:
                try:
                    data = _ask_pair(ia, ib)
                    g = int(data.get('gravite') or 0)
                    # l'IA de vision se trompe souvent : on ne garde que ce qu'elle juge net ET qu'elle confirme
                    # quand on lui montre les images dans l'autre ordre (elimine la plupart des inventions)
                    if g >= 2:
                        g = min(g, int(_ask_pair(ib, ia).get('gravite') or 0))
                    if g >= 2:
                        notes += [f'IA : {d}' for d in data.get('differences') or []][:3]
                        grav = max(grav, g)
                except Exception as e:
                    notes.append(f'vision indisponible ({str(e)[:60]})')
            if notes:
                results.append({'t': round(b['out_start'], 2), 'clipA': a['clip'], 'clipB': b['clip'], 'gravite': grav, 'notes': notes})
    finally:
        if ctx:
            ctx.__exit__(None, None, None)
    return results


def _ask_pair(a, b):
    """Deux images dans le meme message (Qwen vision via llama.cpp)."""
    import base64
    import urllib.request
    from PIL import Image
    from . import llm

    def enc(rgb):
        buf = io.BytesIO()
        Image.fromarray(rgb).save(buf, 'JPEG', quality=85)
        return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
    content = [{'type': 'text', 'text': PROMPT}, {'type': 'image_url', 'image_url': {'url': enc(a)}},
               {'type': 'image_url', 'image_url': {'url': enc(b)}}]
    body = json.dumps({'messages': [{'role': 'user', 'content': content}], 'temperature': 0.1, 'max_tokens': 250,
                       'response_format': {'type': 'json_object'}}).encode()
    req = urllib.request.Request(f'{llm.URL}/v1/chat/completions', data=body, headers={'content-type': 'application/json'})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(json.loads(r.read())['choices'][0]['message']['content'])
