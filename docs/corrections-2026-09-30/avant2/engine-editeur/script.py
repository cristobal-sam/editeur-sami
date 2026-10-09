"""Lecture d'un script (Word ou texte) : scripts > blocs > phrases, et normalisation des mots."""
import re
import unicodedata
from pathlib import Path

SCRIPT_HEADING = re.compile(r'^\s*\**\s*(script|vid[eé]o)\s*\d+\s*:?\s*$', re.I)
LABEL = re.compile(r'^\s*\**\s*([^:\n]{2,40})\s*:\s*$')
SENTENCE_END = re.compile(r'(?<=[.!?…])\s+')


def normalize(word):
    """Mot comparable : minuscules, sans accents ni ponctuation, apostrophes separees."""
    w = unicodedata.normalize('NFKD', word.lower().replace('’', "'"))
    w = ''.join(c for c in w if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9']", '', w)


def tokens(text):
    out = []
    for raw in re.split(r"[\s\-–—]+", text.replace('’', "'")):
        for part in re.split(r"(?<=')", raw):  # « c'est » -> « c' » + « est » comme Whisper
            n = normalize(part).strip("'")
            if n:
                out.append(n)
    return out


def _screenplay(pages):
    """Dialogue d'un scenario : les retraits distinguent personnages, repliques et action.

    Renvoie None pour un PDF ordinaire, qui conserve alors ses paragraphes.
    """
    rows = [line for page in pages for line in page]
    scene = re.compile(r'^(?:\d+\s+)?(?:INT\.?|EXT\.?|INT\./EXT\.|I/E\.)\s', re.I)
    if not any(scene.match(r['texte']) for r in rows):
        return None
    margin = min((r['x'] for r in rows if scene.match(r['texte'])), default=0)
    cue = re.compile(r"^[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ0-9 .'’\-]{0,35}(?:\s*\([^)]*\))?$")
    out, speaker, parts, dialog_x, parenthesis = [], None, [], None, 0

    def flush():
        nonlocal parts
        if speaker and parts:
            text = re.sub(r'\([^)]*\)', '', ' '.join(parts))
            text = ' '.join(text.split()).replace('’', "'")
            if text:
                out.append(f'{speaker}: {text}')
        parts = []

    for r in rows:
        text, x, h = r['texte'].strip(), r['x'], max(1, r['h'])
        if re.match(r'^\(?CONTINUED\)?[\s:.\d]*$|^\d+[.]?$', text, re.I):
            continue
        if scene.match(text):
            flush()
            speaker, dialog_x = None, None
            continue
        if cue.fullmatch(text) and x >= margin + 5 * h and not text.endswith(('TO BLACK', 'TO:', 'OUT.')):
            flush()
            speaker = re.sub(r'\s*\([^)]*\)', '', text).strip()
            dialog_x = None
            continue
        if speaker and (parenthesis or text.startswith('(')):
            parenthesis = max(0, parenthesis + text.count('(') - text.count(')'))
            continue
        if speaker and x >= margin + 2 * h and (dialog_x is None or abs(x - dialog_x) <= h):
            dialog_x = x
            parts.append(text)
        else:
            flush()
            speaker, dialog_x = None, None
    flush()
    return out or None


def _paragraphs(path):
    path = Path(path)
    if path.suffix.lower() == '.docx':
        import docx
        return [p.text for p in docx.Document(str(path)).paragraphs]
    if path.suffix.lower() == '.pdf':
        from . import pdftexte
        try:
            pages = pdftexte.lignes(path)
            return _screenplay(pages) or pdftexte.paragraphes(pages)
        except pdftexte.ErreurPdf as e:
            raise ValueError(f'Script PDF « {path.name} » : {e}') from e
    if path.suffix.lower() in ('.doc', '.pages', '.rtf'):
        raise SystemExit(f"Script « {path.name} » : format non lu. Enregistre-le en Word (.docx) ou en texte (.txt).")
    raw = path.read_bytes()
    for enc in ('utf-8-sig', 'utf-8', 'cp1252'):  # Bloc-notes ancien : ANSI (cp1252)
        try:
            return raw.decode(enc).splitlines()
        except UnicodeDecodeError:
            continue
    return raw.decode('latin-1').splitlines()


def split_sentences(text):
    """Phrases du script. Des points de suspension suivis d'un chiffre ou d'une minuscule ne coupent pas
    (« 65... 75... 80... 100. » est une seule phrase, dite d'un trait)."""
    parts = [p.strip() for p in SENTENCE_END.split(text) if p.strip()]
    merged = []
    for p in parts:
        if merged and re.search(r'(\.\.\.|…)$', merged[-1]) and re.match(r'[0-9a-zà-ÿ]', p):
            merged[-1] = f'{merged[-1]} {p}'
        else:
            merged.append(p)
    return merged or [text.strip()]


def parse(path):
    """Retourne [{'id','title','blocks':[{'id','label','text','sentences':[{'id','text','tokens'}]}]}]."""
    scripts, block_label = [], None
    for raw in _paragraphs(path):
        text = raw.strip().strip('*').strip()
        if not text:
            continue
        if SCRIPT_HEADING.match(text) or not scripts:
            if SCRIPT_HEADING.match(text):
                scripts.append({'title': text.strip(': '), 'blocks': []})
                continue
            scripts.append({'title': f'Script {len(scripts) + 1}', 'blocks': []})
        label = LABEL.match(text)
        if label:
            block_label = label.group(1).strip()
            continue
        if ':' in text[:60] and text.split(':', 1)[0].count(' ') < 5 and text.split(':', 1)[1].strip():
            block_label, text = text.split(':', 1)[0].strip(), text.split(':', 1)[1].strip()
        scripts[-1]['blocks'].append({'label': block_label or f'Bloc {len(scripts[-1]["blocks"]) + 1}', 'text': text})
        block_label = None
    for si, s in enumerate(scripts, 1):
        s['id'] = f's{si}'
        for bi, b in enumerate(s['blocks'], 1):
            b['id'] = f's{si}b{bi}'
            b['sentences'] = [{'id': f's{si}b{bi}p{pi}', 'text': t, 'tokens': tokens(t)}
                              for pi, t in enumerate(split_sentences(b['text']), 1)]
    return [s for s in scripts if s['blocks']]
