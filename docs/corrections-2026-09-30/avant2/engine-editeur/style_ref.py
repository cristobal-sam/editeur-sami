"""Style par reference : on depose une video deja montee (un reel qu'on aime) ; l'outil mesure son style et cree un
style de montage reutilisable (styles/montage/ref-<nom>.json), qu'on applique ensuite a n'importe quelle video.

Tout est local. Mesures :
- rythme : coupes (PySceneDetect), plans par minute ; recadrages plus serres sur la meme personne = zooms de relance ;
- plans de coupe : part des images sans la personne qui parle ;
- sous-titres, bandeau, emojis : IA de vision locale (Qwen) sur quelques images (position, majuscules, couleurs, mots) ;
- son : debit de parole (Whisper), musique sous la voix (niveau dans les silences), tempo (librosa), bruitages ;
- image : saturation, contraste, chaleur, vignettage, flashs blancs.
Chaque mesure est traduite en reglage de l'editeur (le style reste modifiable comme les autres)."""
import base64
import io
import json
import re
import statistics
import urllib.request
from pathlib import Path

import numpy as np

from . import analyze, media, transcribe
from .media import ROOT

STYLES = ROOT / 'styles'
CACHE = ROOT / 'projects/_cache'


def _slug(text):
    from .script import normalize
    t = normalize(str(text).replace(' ', '-').replace('_', '-').replace("'", '-'))
    return re.sub(r'-+', '-', ''.join(c if c.isalnum() else '-' for c in t)).strip('-')[:40] or 'reference'


# ---------- Mesures ----------
def _cuts(path, duration, fps=10):
    """Coupes, y compris les coupes seches d'un face camera (meme decor, cadre qui saute) que les detecteurs de
    scenes ratent : ecart entre deux images nettement plus fort que le mouvement normal juste avant."""
    frames = media.sample_frames(path, fps=fps, width=96)
    gray = [f.astype(np.float32).mean(axis=2) for _, f in frames]
    diffs = [float(np.abs(b - a).mean()) / 255 for a, b in zip(gray, gray[1:])]
    cuts = []
    for k, d in enumerate(diffs):
        local = np.median(diffs[max(0, k - 8):k]) if k >= 3 else 0.02
        t = frames[k + 1][0]
        if d > max(0.035, 4.5 * local) and (not cuts or t - cuts[-1] > 0.35):
            cuts.append(round(t, 2))
    shots = np.diff([0.0, *cuts, duration]) if duration else np.array([])
    return cuts, (float(np.median(shots)) if len(shots) else duration)


def _faces(an, cuts):
    """Part des images avec la personne ; zooms de relance = visage nettement plus grand (ou plus petit) de part et
    d'autre d'une coupe, a la meme place."""
    frames = an['frames']
    with_face = [f for f in frames if f.get('face')]
    ratio = len(with_face) / max(1, len(frames))
    punch = 0
    for c in cuts:
        before = [f['face'] for f in frames if f.get('face') and c - 0.6 <= f['t'] < c - 0.05]
        after = [f['face'] for f in frames if f.get('face') and c + 0.05 < f['t'] <= c + 0.6]
        if before and after:
            wb, wa = before[-1]['w'], after[0]['w']
            if abs(before[-1]['cx'] - after[0]['cx']) < 0.2 and max(wa, wb) / max(1e-3, min(wa, wb)) >= 1.12:
                punch += 1
    return ratio, punch


def _image(path):
    """Couleur moyenne des images : saturation, contraste, chaleur, vignettage, flashs."""
    frames = media.sample_frames(path, fps=2, width=240)
    if not frames:
        return {}
    sats, contrasts, warms, vign, lumas = [], [], [], [], []
    for _, rgb in frames:
        f = rgb.astype(np.float32) / 255
        mx, mn = f.max(axis=2), f.min(axis=2)
        sats.append(float(np.mean((mx - mn) / np.maximum(mx, 1e-3))))
        luma = 0.299 * f[..., 0] + 0.587 * f[..., 1] + 0.114 * f[..., 2]
        contrasts.append(float(luma.std()))
        warms.append(float(f[..., 0].mean() - f[..., 2].mean()))
        h, w = luma.shape
        corners = np.concatenate([luma[:h // 6, :w // 6].ravel(), luma[:h // 6, -w // 6:].ravel(),
                                  luma[-h // 6:, :w // 6].ravel(), luma[-h // 6:, -w // 6:].ravel()])
        center = luma[h // 3: 2 * h // 3, w // 3: 2 * w // 3]
        vign.append(float(corners.mean() / max(1e-3, center.mean())))
        lumas.append(float(luma.mean()))
    flashes = sum(1 for a, b in zip(lumas, lumas[1:]) if b > 0.85 and b - a > 0.25)
    return {'saturation': round(statistics.median(sats), 3), 'contraste': round(statistics.median(contrasts), 3),
            'chaleur': round(statistics.median(warms), 3), 'vignettage': round(statistics.median(vign), 3), 'flashs': flashes}


def _audio(path, words, duration):
    """Musique sous la voix, tempo, bruitages (attaques nettes hors parole), debit."""
    import librosa
    y = media.decode_audio(path, sr=22050)
    if not len(y):
        return {}
    hop = 512
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=22050, hop_length=hop)
    speech = np.zeros(len(rms), bool)
    for w in words:
        speech |= (times >= w['start'] - 0.05) & (times <= w['end'] + 0.05)
    db = 20 * np.log10(np.maximum(rms, 1e-5))
    speech_db = float(np.median(db[speech])) if speech.any() else -60.0
    gaps_db = float(np.median(db[~speech])) if (~speech).sum() > 20 else -60.0
    spectral = librosa.feature.melspectrogram(y=y, sr=22050, n_fft=2048, hop_length=hop,
                                             n_mels=64, fmin=30, fmax=11000)
    tempo, clarity = _music_rhythm(spectral)
    onsets = librosa.onset.onset_detect(y=y, sr=22050, hop_length=hop, units='time', backtrack=False)
    strength = librosa.onset.onset_strength(y=y, sr=22050, hop_length=hop)
    thr = np.percentile(strength, 97) if len(strength) else 0
    fx = [t for t in onsets if not any(w['start'] - 0.1 <= t <= w['end'] + 0.1 for w in words)
          and strength[min(len(strength) - 1, int(t * 22050 / hop))] >= thr]
    spoken = (words[-1]['end'] - words[0]['start']) if words else 0
    # energie de la musique : attaques par seconde dans les silences de la voix + niveau du fond
    silent_s = max(1e-3, float((~speech).sum()) * hop / 22050)
    in_gaps = sum(1 for t in onsets if not any(w['start'] - 0.05 <= t <= w['end'] + 0.05 for w in words))
    energy = 0.6 * min(1.0, in_gaps / silent_s / 4) + 0.4 * min(1.0, max(0.0, (gaps_db + 45) / 25))
    signature, background_ratio, flatness = _music_signature(spectral)
    # Les mots de Whisper peuvent couvrir presque toute une pub : analyser aussi les
    # 15 % de trames les moins dominees par la bande de la voix. Un bruit de piece
    # dans ces trames ne suffit pas : il faut un fond soutenu, tonal ou periodique.
    music = bool(np.max(rms) > 0.0003 and (
        (not words and clarity >= 2.8)
        or (bool(words) and (background_ratio > -17.5
                            or (flatness < 0.045 and background_ratio > -24)
                            or clarity >= 3.2))))
    ranking, distances = _music_ranking(tempo, signature)
    separation = max(0.0, (distances[1] - distances[0]) / max(0.2, distances[1])) if len(distances) > 1 else 0
    confidence = float(np.clip(0.25 + 0.35 * min(1, max(0, clarity - 2) / 5) + 0.4 * separation, 0, 0.95)) if music else 0.0
    timbre = None  # ancienne signature conservee dans l'API pour compatibilite
    return {'musique': bool(music), 'musique_db': round(gaps_db - speech_db, 1), 'tempo': round(tempo), 'energie': round(energy, 2),
            'timbre': timbre, 'classement': ranking, 'confiance': round(confidence, 2),
            'clarte_rythme': round(clarity, 2), 'fond_voix_db': round(background_ratio, 1),
            'methode': 'spectre normalise du fond et periodicite multibande',
            'bruitages_min': round(len(fx) / max(1e-3, duration / 60), 1),
            'mots_min': round(len(words) / max(1e-3, spoken / 60)) if spoken > 3 else 0}


VISION_Q = ("Tu regardes une image d'une video montee (reel). Reponds UNIQUEMENT en JSON : "
            '{"sous_titres": true|false, "position": "haut"|"milieu"|"bas", "majuscules": true|false, '
            '"couleur_texte": "#RRGGBB", "couleur_mot_en_valeur": "#RRGGBB" ou null, "contour": true|false, '
            '"fond_derriere_le_texte": true|false, "mots_visibles": nombre, "police": "grasse"|"fine"|"serif"|"manuscrite", '
            '"titre_en_haut": true|false, "emoji": true|false}. Les sous-titres sont le texte de ce qui est dit, '
            "pas un titre fixe.")


def _vision(path, words, duration):
    """Sous-titres et habillage, lus par l'IA de vision locale sur 4 images (moments ou l'on parle)."""
    from PIL import Image
    from . import llm
    if not (llm.available() and llm.MMPROJ.exists()):
        return []
    spoken = [w['start'] + 0.15 for w in words] or [duration * k / 5 for k in range(1, 5)]
    picks = [spoken[int(len(spoken) * k / 5)] for k in range(1, 5)] if len(spoken) >= 5 else spoken[:4]
    picks = [0.8] + picks  # le bandeau d'accroche est au debut
    out = []
    with llm.session(vision=True):
        for t in picks:
            try:
                rgb = media.sample_frames(path, fps=1, width=720, start=min(t, max(0.0, duration - 0.5)), duration=0.9)[0][1]
                buf = io.BytesIO()
                Image.fromarray(rgb).save(buf, 'JPEG', quality=88)
                content = [{'type': 'text', 'text': VISION_Q},
                           {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()}}]
                body = json.dumps({'messages': [{'role': 'user', 'content': content}], 'temperature': 0.1, 'max_tokens': 220,
                                   'response_format': {'type': 'json_object'}}).encode()
                req = urllib.request.Request(f'{llm.URL}/v1/chat/completions', data=body, headers={'content-type': 'application/json'})
                with urllib.request.urlopen(req, timeout=180) as r:
                    out.append(json.loads(json.loads(r.read())['choices'][0]['message']['content']))
            except Exception as e:
                print(f'Vision : image ignoree ({e})')
    return out


def _majority(items, key, default=None):
    vals = [i.get(key) for i in items if i.get(key) is not None]
    if not vals:
        return default
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
        return statistics.median(vals)
    return max(set(map(str, vals)), key=lambda v: [str(x) for x in vals].count(v))


def _hex(v, default):
    return v.upper() if isinstance(v, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', v) else default


# ---------- Traduction en reglages ----------
def _captions(vis):
    """Preset de sous-titres le plus proche + couleurs / majuscules / nombre de mots mesures."""
    caps = [v for v in vis[1:] if v.get('sous_titres')] or [v for v in vis if v.get('sous_titres')]
    if not caps:
        return 'minimal', {}, False
    words = int(round(float(_majority(caps, 'mots_visibles', 3) or 3)))
    upper = str(_majority(caps, 'majuscules', 'True')) == 'True'
    font = str(_majority(caps, 'police', 'grasse'))
    box = str(_majority(caps, 'fond_derriere_le_texte', 'False')) == 'True'
    stroke = str(_majority(caps, 'contour', 'True')) == 'True'
    color = _hex(_majority(caps, 'couleur_texte'), '#FFFFFF')
    hl = _hex(_majority(caps, 'couleur_mot_en_valeur'), None)
    pos = {'haut': 0.22, 'milieu': 0.5, 'bas': 0.72}.get(str(_majority(caps, 'position', 'bas')), 0.7)
    if words <= 1:
        preset = 'geant'
    elif font == 'serif':
        preset = 'elegant'
    elif box and color not in ('#FFFFFF',):
        preset = 'bulle'
    elif box:
        preset = 'boite'
    elif words >= 5 or font == 'fine':
        preset = 'karaoke' if hl else 'minimal'
    else:
        preset = 'impact' if stroke else 'neon'
    style = {'uppercase': upper, 'maxWords': max(1, min(7, words)), 'position': pos, 'color': color}
    if hl:
        style['highlight'] = hl
    if not stroke:
        style['strokeWidth'] = 0
    return preset, style, any(v.get('emoji') for v in caps)


# energie des ambiances de la bibliotheque (0 calme .. 1 tres energique)
MOOD_ENERGY = {'energique': 0.85, 'corporate': 0.6, 'electro': 0.8, 'cinematique': 0.6, 'lofi': 0.25, 'emotion': 0.15, 'tech': 0.6,
               'funk': 0.75, 'suspense': 0.5, 'acoustique': 0.35, 'luxe': 0.5, 'immobilier': 0.45}


def _music_signature(spectral):
    """Meme mesure pour la reference et la bibliotheque, independante du volume."""
    level = spectral[3:45].sum(axis=0)
    quiet = level <= np.quantile(level, 0.15)
    floor = np.median(spectral[:, quiet], axis=1)
    log = 10 * np.log10(np.maximum(floor, 1e-10))
    ratio = 10 * np.log10((floor.sum() + 1e-12) / (spectral.sum(axis=0).mean() + 1e-12))
    flatness = np.exp(np.mean(np.log(floor + 1e-12))) / (floor.mean() + 1e-12)
    return (log - log.mean()).tolist(), float(ratio), float(flatness)


def _music_rhythm(spectral):
    """Periodicite du fond : reduire les bandes tres variables dominees par la parole."""
    from scipy.ndimage import uniform_filter1d
    if spectral.shape[1] < 20:
        return 0.0, 0.0
    log = 10 * np.log10(np.maximum(spectral, 1e-10))
    spread = np.percentile(log, 90, axis=1) - np.percentile(log, 10, axis=1)
    weights = np.exp(-spread / 12) * np.r_[np.ones(3) * 2, np.ones(48) * 0.3, np.ones(13) * 2]
    env = np.average(np.maximum(np.diff(log), 0), axis=0, weights=weights)
    env = np.maximum(env - uniform_filter1d(env, 17), 0)
    size = max(16384, 1 << (len(env) - 1).bit_length())
    fft = np.abs(np.fft.rfft((env - env.mean()) * np.hanning(len(env)), n=size))
    freq = np.fft.rfftfreq(size, 512 / 22050)
    grid = np.arange(55, 201, 0.2)
    sal = sum(w * np.interp(grid * k / 60, freq, fft) for k, w in ((1, 1), (2, 0.5), (4, 0.25)))
    sal *= np.exp(-0.5 * (np.log2(grid / 105) / 0.9) ** 2)
    i = sal.argmax()
    return float(grid[i]), float(sal[i] / (np.median(sal) + 1e-9))


def _music_library():
    import librosa
    cache = ROOT / 'runtime/cache/musique-signatures-v1.json'
    try:
        data = json.loads(cache.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        data = {}
    changed = False
    for m in json.loads((STYLES / 'musiques.json').read_text(encoding='utf-8')):
        f = ROOT / 'assets/music' / f"{m['id']}.ogg"
        if not f.exists():
            continue
        key = media.file_key(f)
        if data.get(m['id'], {}).get('key') != key:
            y, sr = librosa.load(str(f), sr=22050, mono=True, duration=90)
            spectral = librosa.feature.melspectrogram(y=y, sr=sr, n_fft=2048, hop_length=512,
                                                     n_mels=64, fmin=30, fmax=11000)
            data[m['id']] = {'key': key, 'signature': _music_signature(spectral)[0], 'bpm': m['bpm']}
            changed = True
    if changed:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data), encoding='utf-8')
    return data


def _music_ranking(tempo, signature):
    moods = json.loads((STYLES / 'musiques.json').read_text(encoding='utf-8'))
    lib = _music_library()
    vectors = [v['signature'] for v in lib.values() if v.get('signature')]
    scale = np.maximum(np.std(vectors, axis=0), 3) if vectors else None
    def distance(m):
        bpm = min(abs(m['bpm'] - tempo * k) for k in (0.5, 1, 2)) / 25 if tempo else 1
        ref = lib.get(m['id'], {}).get('signature')
        if ref and scale is not None:
            return bpm + 0.4 * float(np.sqrt(np.mean(((np.array(ref) - signature) / scale) ** 2)))
        return bpm + abs(MOOD_ENERGY.get(m['id'], 0.5) - 0.5)
    scored = sorted((distance(m), m['id']) for m in moods)
    return [k for _, k in scored], [d for d, _ in scored]


def _timbre(y, sr, mask=None):
    """Empreinte du son (MFCC moyens et ecarts, brillance) : pour trouver la musique de la bibliotheque qui sonne pareil."""
    import librosa
    # sans le 1er coefficient (le volume) : la musique est plus basse sous la voix que dans la bibliotheque
    mf = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20, hop_length=512)[1:]
    cen = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=512)
    if mask is not None:
        n = min(mf.shape[1], len(mask))
        keep = mask[:n]
        if keep.sum() < 20:
            return None
        mf, cen = mf[:, :n][:, keep], cen[:, :n][:, keep]
    return np.concatenate([mf.mean(axis=1), mf.std(axis=1), [cen.mean() / 1000]]).tolist()


def _library_timbres():
    """Empreintes des musiques de la bibliotheque (calculees une fois, en cache)."""
    import librosa
    cache = ROOT / 'runtime/cache/musique-timbres.json'
    data = {}
    try:
        data = json.loads(cache.read_text(encoding='utf-8'))
    except Exception:
        pass
    changed = False
    for m in json.loads((STYLES / 'musiques.json').read_text(encoding='utf-8')):
        f = ROOT / 'assets/music' / f"{m['id']}.ogg"
        if not f.exists():
            continue
        key = media.file_key(f)
        if data.get(m['id'], {}).get('key') != key:
            y, sr = librosa.load(str(f), sr=22050, mono=True, duration=90)
            data[m['id']] = {'key': key, 'timbre': _timbre(y, sr), 'bpm': m['bpm']}
            changed = True
    if changed:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data), encoding='utf-8')
    return data


def _mood(tempo, energy, timbre=None, son=None):
    """Ambiance la plus proche : timbre de la musique entendue dans les silences (le plus fiable), tempo (souvent
    mesure double ou moitie sous la voix) et energie."""
    if son is not None:
        if not son.get('musique'):
            return None
        if son.get('classement'):
            return son['classement'][0]
    moods = json.loads((STYLES / 'musiques.json').read_text(encoding='utf-8'))
    lib = _library_timbres() if timbre else {}
    ref = np.array(timbre) if timbre else None
    vecs = {k: np.array(v['timbre']) for k, v in lib.items() if v.get('timbre')}
    scale = np.std(np.stack(list(vecs.values())), axis=0) + 1e-6 if len(vecs) >= 3 else None

    def dist(m):
        bpm = min(abs(m['bpm'] - tempo), abs(m['bpm'] - tempo / 2), abs(m['bpm'] - tempo * 2)) if tempo else 30
        d = bpm / 25 + abs(MOOD_ENERGY.get(m['id'], 0.5) - energy)
        # l'empreinte ne fait que departager : le fond sonore d'un montage fini (voix, bruit de piece) la brouille
        if ref is not None and scale is not None and m['id'] in vecs:
            d += 0.3 * float(np.linalg.norm((vecs[m['id']] - ref) / scale)) / np.sqrt(len(ref))
        return d
    return min(moods, key=dist)['id']


def analyse(path):
    """Toutes les mesures d'une video de reference (dict)."""
    path = Path(path).resolve()
    info = media.probe(path)
    dur = info['duration']
    words = transcribe.transcribe(path, CACHE / 'transcripts', language='auto')['words']
    an = analyze.analyze(path, CACHE / 'analysis')
    cuts, shot = _cuts(path, dur)
    face_ratio, punch = _faces(an, cuts)
    return {'fichier': path.name, 'duree': round(dur, 1), 'largeur': info['width'], 'hauteur': info['height'],
            'coupes_min': round(len(cuts) / max(1e-3, dur / 60), 1), 'plan_median': round(shot, 2),
            'zooms_min': round(punch / max(1e-3, dur / 60), 1), 'personne': round(face_ratio, 2),
            'image': _image(path), 'son': _audio(path, words, dur), 'vision': _vision(path, words, dur)}


def build(path, name=None):
    """Analyse la video et enregistre le style : renvoie {'id', 'name', 'description', 'mesures'}."""
    m = analyse(path)
    preset, cap_style, emoji = _captions(m['vision'])
    img, son = m['image'], m['son']
    fast = m['coupes_min'] >= 18
    grade = ('noirblanc' if img.get('saturation', 1) < 0.05 else 'contraste' if img.get('contraste', 0) > 0.23
             else 'chaud' if img.get('chaleur', 0) > 0.06 else 'froid' if img.get('chaleur', 0) < -0.04 else 'aucun')
    title = (name or f"Réf. {Path(path).stem}").strip()[:40]
    sid = f'ref-{_slug(title)}'
    banner = bool(m['vision'] and m['vision'][0].get('titre_en_haut'))
    music_on = son.get('musique', False)
    mood = _mood(son.get('tempo'), son.get('energie', 0.6), son.get('timbre'), son) if music_on else None
    vol = round(float(np.clip(0.2 + (son.get('musique_db', -18) + 18) * 0.01, 0.08, 0.3)), 2)
    sfx_rich = son.get('bruitages_min', 0) >= 4
    tpl = {
        'id': sid, 'name': title,
        'description': (f"D'après « {m['fichier']} » : {m['coupes_min']:.0f} coupes/min, zooms {'fréquents' if m['zooms_min'] >= 3 else 'légers'}, "
                        f"sous-titres {cap_style.get('maxWords', 3)} mots{' en majuscules' if cap_style.get('uppercase') else ''}"
                        + (f", musique ~{son.get('tempo')} BPM (confiance {'bonne' if son.get('confiance', 0) >= 0.7 else 'moyenne' if son.get('confiance', 0) >= 0.4 else 'faible'})"
                           if music_on else ', musique non détectée')
                        + (f", {round(100 * (1 - m['personne']))} % de plans de coupe" if m['personne'] < 0.85 else '') + '.'),
        'captions': preset,
        'style': cap_style,
        'zoom': {'auto': True, 'strength': 1.14 if m['zooms_min'] >= 3 or fast else 1.07, 'push': 0.03 if fast else 0.015},
        'banner': {'enabled': banner},
        'flash': {'enabled': img.get('flashs', 0) >= max(1, m['duree'] / 20), 'kind': 'blanc'},
        'effects': {'grain': 0.1, 'vignette': 0.3 if img.get('vignettage', 1) < 0.8 else 0.0, 'grade': grade},
        'emoji': emoji, 'progress': False,
        'music': {'mood': mood, 'volume': vol},
        'sfx': {'transition': 'whoosh-court' if sfx_rich or fast else None, 'highlight': 'pop' if sfx_rich else None,
                'highlightGap': 3.5, 'cta': 'riser' if sfx_rich else None, 'start': None, 'volume': 0.6},
        'broll': {'part': round(1 - m['personne'], 2)},
        'ia': 'auto',
        'reference': m,
    }
    out = STYLES / 'montage' / f'{sid}.json'
    out.write_text(json.dumps(tpl, ensure_ascii=False, indent=1), encoding='utf-8')
    return {'id': sid, 'name': title, 'description': tpl['description'], 'mesures': {k: v for k, v in m.items() if k != 'vision'}}
