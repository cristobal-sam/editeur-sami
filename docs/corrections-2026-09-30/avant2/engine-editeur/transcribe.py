"""Transcription locale mot par mot (faster-whisper sur GPU), avec cache par fichier."""
import json
import os
from pathlib import Path

from .media import cache_name, decode_audio, file_key

_model = None


def _load():
    global _model
    if _model is None:
        import torch  # fournit les DLL CUDA (cuBLAS/cuDNN) utilisees par CTranslate2
        os.add_dll_directory(str(Path(torch.__file__).parent / 'lib'))
        os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')
        from faster_whisper import WhisperModel
        cuda = torch.cuda.is_available()
        _model = WhisperModel('large-v3-turbo', device='cuda' if cuda else 'cpu',
                              compute_type='float16' if cuda else 'int8')
    return _model


def transcribe(path, cache_dir, language=None, vocabulary=''):
    """Retourne {'words': [{'w','start','end','p'}], 'text', 'duration', 'language'}; resultat mis en cache.
    language : 'fr', 'en'... ou 'auto' (detection) ; None = la transcription deja faite, sinon le francais.
    Une langue differente de celle du cache refait la transcription."""
    cache = Path(cache_dir) / f'{cache_name(path)}.transcript.json'
    key = file_key(path)
    if cache.exists():
        data = json.loads(cache.read_text(encoding='utf-8'))
        if data.get('key') == key and (language in (None, 'auto') or data.get('language', 'fr') == language):
            return data
    lang = None if language == 'auto' else (language or 'fr')
    audio = decode_audio(path)
    if len(audio) < 16000 * 0.3:  # pas de son (ou presque) : aucun mot, sans charger Whisper
        data = {'key': key, 'source': str(path), 'duration': round(len(audio) / 16000, 3), 'language': lang or 'fr', 'text': '', 'words': []}
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
        return data
    segments, info = _load().transcribe(
        audio, language=lang, word_timestamps=True, beam_size=5,
        initial_prompt=vocabulary[:800] or None, condition_on_previous_text=False,
        vad_filter=True, vad_parameters={'min_silence_duration_ms': 300})
    words = []
    for seg in segments:
        for w in seg.words or []:
            words.append({'w': w.word.strip(), 'start': round(w.start, 3), 'end': round(w.end, 3),
                          'p': round(w.probability, 3)})
    data = {'key': key, 'source': str(path), 'duration': round(len(audio) / 16000, 3),
            'language': getattr(info, 'language', None) or lang or 'fr',
            'text': ' '.join(w['w'] for w in words), 'words': words}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    return data
