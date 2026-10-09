"""Recherche en phrase naturelle dans les rushs d'un projet :
« plans ou elle montre le telephone », « exterieur jour », « quand elle parle du salaire »...
Trois index combines, construits une fois par prise (cache) :
  - CLIP : ce que montrent les images (1 image/s)
  - la transcription : ce qui est dit
  - une description de chaque scene par la vision de Qwen (scenes detectees par PySceneDetect)"""
import io
import json
from pathlib import Path

import numpy as np

from . import media, transcribe
from .media import ROOT
from .script import normalize, tokens

CACHE = ROOT / 'projects/_cache/recherche'
_clip = None


def _model():
    global _clip
    if _clip is None:
        import open_clip
        import torch
        dev = 'cuda' if torch.cuda.is_available() else 'cpu'
        model, _, prep = open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k', device=dev)
        _clip = (model.eval(), prep, open_clip.get_tokenizer('ViT-B-32'), dev)
    return _clip


def _scenes(proxy):
    """Debuts de scenes (s) ; au moins le debut de la prise."""
    try:
        from scenedetect import ContentDetector, detect
        found = [s[0].get_seconds() for s in detect(str(proxy), ContentDetector(threshold=27))]
    except Exception:
        found = []
    return found or [0.0]


def index_source(src, use_vision=True):
    """Index d'une prise (cache) : embeddings CLIP par seconde + descriptions des scenes."""
    import torch
    from PIL import Image
    proxy = Path(src['proxy'] if Path(src['proxy']).is_absolute() else ROOT / src['proxy'])
    out = CACHE / f"{media.cache_name(src['path'])}.json"
    if out.exists():
        data = json.loads(out.read_text(encoding='utf-8'))
        if data.get('key') == media.file_key(proxy) and (data.get('captions') or not use_vision):
            return data
    model, prep, _, dev = _model()
    frames = media.sample_frames(proxy, fps=1, width=360)
    with torch.no_grad():
        batch = torch.stack([prep(Image.fromarray(rgb)) for _, rgb in frames]).to(dev)
        emb = model.encode_image(batch).float()
        emb = (emb / emb.norm(dim=-1, keepdim=True)).cpu().numpy()
    captions = []
    if use_vision:
        from . import llm
        if llm.available() and llm.MMPROJ.exists():
            try:
                with llm.session(vision=True):
                    for start in _scenes(proxy)[:6]:
                        t = min(start + 1.0, max(0.0, src['duration'] - 0.5))
                        rgb = media.sample_frames(proxy, fps=1, width=512, start=t, duration=0.9)[0][1]
                        buf = io.BytesIO()
                        Image.fromarray(rgb).save(buf, 'JPEG', quality=85)
                        captions.append({'t': round(t, 2), 'text': llm.describe_image(buf.getvalue())})
            except Exception as e:
                print(f'Vision indisponible ({e}) : recherche par image et par parole seulement.')
    data = {'key': media.file_key(proxy), 'times': [round(t, 2) for t, _ in frames],
            'emb': np.round(emb, 4).tolist(), 'captions': captions}
    CACHE.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data), encoding='utf-8')
    return data


def _english(query):
    """CLIP comprend l'anglais : traduction rapide par l'IA locale si disponible."""
    from . import llm
    if not llm.available():
        return query
    try:
        with llm.session():
            return llm.ask_text('Tu traduis des requetes de recherche video du francais vers l anglais. Reponds seulement la traduction.',
                                query, max_tokens=60)
    except Exception:
        return query


def search(project_dir, query, limit=12, use_vision=True):
    import torch
    project = json.loads((Path(project_dir) / 'project.json').read_text(encoding='utf-8'))
    from .reel import STOP
    meta = set('quand elle il ils parle parlent dit disent montre montrent plan plans moment moments ou trouve trouver '
               'video videos scene scenes image images personne quelqu'.split())
    q_tokens = [t for t in tokens(query) if len(t) > 2 and t not in STOP and t not in meta] or [t for t in tokens(query) if len(t) > 2]
    model, _, tok, dev = _model()
    with torch.no_grad():
        q = model.encode_text(tok([_english(query)]).to(dev)).float()
        q = (q / q.norm(dim=-1, keepdim=True)).cpu().numpy()[0]
    results = []
    for sid, src in project['sources'].items():
        idx = index_source(src, use_vision)
        sims = np.array(idx['emb']) @ q if idx['emb'] else np.array([])
        # image : meilleur moment de la prise
        if len(sims):
            k = int(sims.argmax())
            results.append({'source': sid, 'name': src['name'], 't': idx['times'][k], 'score': float(sims[k]) * 3.2 - 0.6,
                            'why': 'image', 'text': ''})
        # parole : mots de la requete prononces
        words = transcribe.transcribe(src['path'], ROOT / 'projects/_cache/transcripts')['words']
        norm = [normalize(w['w']).strip("'") for w in words]
        for i in range(len(words)):
            window = norm[i:i + 12]
            hits = sum(1 for t in q_tokens if t in window)
            if q_tokens and hits / len(q_tokens) >= 0.5 and norm[i] in q_tokens:
                results.append({'source': sid, 'name': src['name'], 't': words[i]['start'], 'score': 0.4 + 0.6 * hits / len(q_tokens),
                                'why': 'parole', 'text': ' '.join(w['w'] for w in words[i:i + 12])})
                break
        # description de la scene
        for c in idx.get('captions', []):
            ct = set(tokens(c['text']))
            hits = sum(1 for t in q_tokens if t in ct)
            if q_tokens and hits:
                results.append({'source': sid, 'name': src['name'], 't': c['t'], 'score': 0.3 + 0.6 * hits / len(q_tokens),
                                'why': 'description', 'text': c['text']})
    results.sort(key=lambda r: -r['score'])
    seen, out = set(), []
    for r in results:  # un resultat par prise et par raison
        key = (r['source'], r['why'])
        if key in seen:
            continue
        seen.add(key)
        r['proxy'] = Path(project['sources'][r['source']]['proxy']).resolve().relative_to(ROOT.resolve()).as_posix()
        out.append(r)
    return out[:limit]
