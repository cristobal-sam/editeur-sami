"""IA de texte locale (llama.cpp + Qwen3.5-9B, licence Apache 2.0) pour les choix editoriaux.
Demarre le serveur au besoin et l'arrete ensuite ; aucune connexion externe."""
import json
import os
import subprocess
import time
import urllib.request
from contextlib import contextmanager

from .media import ROOT

PORT = 8791
URL = f'http://127.0.0.1:{PORT}'
SERVER = ROOT / 'tools/llama/llama-server.exe'
MODEL = ROOT / 'models/llm/Qwen3.5-9B-Q4_K_M.gguf'


def _alive():
    try:
        with urllib.request.urlopen(f'{URL}/health', timeout=1) as r:
            return b'ok' in r.read()
    except Exception:
        return False


def available():
    return SERVER.exists() and MODEL.exists()


MMPROJ = ROOT / 'models/llm/Qwen3.5-9B-mmproj-F16.gguf'


def _pid_alive(pid):
    """Processus encore en vie ? (Windows : jamais os.kill, qui le terminerait.)"""
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return code.value == 259  # STILL_ACTIVE
    except Exception:
        return True


def _users(port, change=None):
    """Registre partage entre processus : qui utilise le serveur IA (pour ne jamais l'arreter sous les pieds d'un autre)."""
    f = ROOT / 'runtime/cache' / f'llama-{port}.json'
    try:
        data = json.loads(f.read_text(encoding='utf-8'))
    except Exception:
        data = {'server': None, 'users': []}
    data['users'] = [p for p in data.get('users', []) if _pid_alive(p)]
    if change:
        change(data)
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name(f'{f.name}.{os.getpid()}.tmp')
        tmp.write_text(json.dumps(data), encoding='utf-8')
        os.replace(tmp, f)
    return data


@contextmanager
def session(vision=False):
    """Utilise le serveur deja lance, sinon le demarre le temps de la tache (vision = module d'images en plus).
    Le serveur est partage : il n'est arrete que lorsque plus aucune tache (de n'importe quel processus) ne s'en sert."""
    global URL
    port = PORT + 1 if vision else PORT
    URL = f'http://127.0.0.1:{port}'
    proc = None
    if not _alive():
        log = open(ROOT / 'runtime/cache/llama.log', 'ab')
        extra = ['--mmproj', str(MMPROJ)] if vision else []
        proc = subprocess.Popen([str(SERVER), '-m', str(MODEL), *extra, '-ngl', '99', '-c', '16384', '--host', '127.0.0.1',
                                 '--port', str(port), '--jinja', '--reasoning-budget', '0'],
                                stdout=log, stderr=log, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        for _ in range(120):
            if _alive():
                break
            if proc.poll() is not None:
                raise RuntimeError('Le serveur IA local n\'a pas demarre (voir runtime/cache/llama.log).')
            time.sleep(0.5)
        _users(port, lambda d: d.update(server=proc.pid))
    me = os.getpid()
    _users(port, lambda d: d['users'].append(me))
    try:
        yield
    finally:
        def leave(d):
            if me in d['users']:
                d['users'].remove(me)  # une seule fois : les sessions imbriquees d'un meme processus comptent chacune
        data = _users(port, leave)
        if not data['users'] and data.get('server'):
            # plus personne : on arrete le serveur (le notre, ou celui d'une tache terminee)
            if proc:
                proc.terminate()
                try:
                    proc.wait(10)
                except Exception:
                    proc.kill()
            elif _pid_alive(data['server']):
                subprocess.run(['taskkill', '/PID', str(data['server']), '/T', '/F'], capture_output=True)
            _users(port, lambda d: d.update(server=None))


def ask_json(system, user, temperature=0.3, max_tokens=2000):
    body = json.dumps({'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                       'temperature': temperature, 'max_tokens': max_tokens,
                       'response_format': {'type': 'json_object'}}).encode()
    req = urllib.request.Request(f'{URL}/v1/chat/completions', data=body, headers={'content-type': 'application/json'})
    with urllib.request.urlopen(req, timeout=180) as r:
        content = json.loads(r.read())['choices'][0]['message']['content']
    return json.loads(content)


def ask_text(system, user, temperature=0.2, max_tokens=300):
    body = json.dumps({'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                       'temperature': temperature, 'max_tokens': max_tokens}).encode()
    req = urllib.request.Request(f'{URL}/v1/chat/completions', data=body, headers={'content-type': 'application/json'})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())['choices'][0]['message']['content'].strip()


def describe_image(jpeg_bytes):
    """Description courte d'une image (vision de Qwen), en francais."""
    import base64
    content = [{'type': 'text', 'text': "Decris ce plan video en une phrase courte en francais : lieu, personnes, action, "
                                        "cadrage, lumiere. Pas de preambule."},
               {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(jpeg_bytes).decode()}}]
    body = json.dumps({'messages': [{'role': 'user', 'content': content}], 'temperature': 0.2, 'max_tokens': 120}).encode()
    req = urllib.request.Request(f'{URL}/v1/chat/completions', data=body, headers={'content-type': 'application/json'})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())['choices'][0]['message']['content'].strip()


EDITOR = ("Tu es un monteur video expert en reels publicitaires francophones (Quebec). "
          "Tu reponds uniquement en JSON valide, sans commentaire.")


def _is_emoji(text):
    t = str(text).strip()
    return 0 < len(t) <= 8 and all(ord(ch) >= 0x2190 or ch in '‍️' for ch in t)


LANGS = {'fr': 'francais', 'en': 'anglais', 'es': 'espagnol', 'de': 'allemand', 'it': 'italien', 'pt': 'portugais'}
PROMPT_EXAMPLES = ('VOTRE CONCURRENT REPOND PLUS VITE', 'CHAQUE MINUTE VOUS COUTE UN CLIENT', "L'ERREUR QUI VOUS COUTE CHER")


def _check_banners(banners, clips, language='fr'):
    """Bandeaux de l'IA gardes seulement s'ils sont sains : pas un exemple du prompt recopie, ancres dans ce qui est dit
    (60 % des mots forts se retrouvent dans la video) et juges corrects par une relecture de l'IA (temperature 0)."""
    from .reel import STOP
    from .script import normalize
    said = {normalize(w).strip("'") for c in clips for w in c['words']}
    examples = {normalize(e).replace(' ', '') for e in PROMPT_EXAMPLES}

    def anchored(b):
        content = [t for t in (normalize(x).strip("'") for x in b.split()) if len(t) >= 4 and t not in STOP]
        if not content:
            return False
        hits = sum(1 for t in content if t in said or any(w.startswith(t[:5]) for w in said if len(w) >= 5))
        return hits / len(content) >= 0.6

    kept = [b for b in banners if normalize(b).replace(' ', '') not in examples and anchored(b)]
    if not kept:
        return []
    try:
        name = LANGS.get(language, 'francais')
        data = ask_json(EDITOR, f"Relis ces titres courts ({name}). Pour chacun : est-il grammaticalement correct, naturel et "
                                'comprehensible seul ? Reponds {"ok": [true|false, ...]} dans le meme ordre.\n'
                                + '\n'.join(f'- {b}' for b in kept), temperature=0.0, max_tokens=60)
        ok = data.get('ok') or []
        if len(ok) == len(kept):
            kept = [b for b, good in zip(kept, ok) if good is True or str(good).lower() in ('true', 'oui', 'yes')]
    except Exception:
        pass
    return kept


HIGHLIGHT_RULES = {
    'fr': ("Chaque element de « couleur » est copie EXACTEMENT du texte : un seul mot, ou 2 a 4 mots pour un chiffre avec "
           "son unite (« cinq fois moins cher », « trois heures », « 24/7 », « 30 % »), une expression ou le texte d'un "
           "bouton (« En savoir plus »). Choisis les mots qui portent le message : le chiffre, le benefice, la douleur ou "
           "le cout, la marque ou le produit, le verbe ou l'adjectif fort, l'action demandee a la fin. Jamais de petits "
           "mots seuls (le, de, pour, vos, notre, est, sont, que, qui, ca...), jamais de verbes vagues (faire, dire, "
           "avoir, aller, mettre...)."),
    'en': ("Each item of \"couleur\" is copied EXACTLY from the text: one word, or 2 to 4 words for a number with its "
           "unit (\"5x cheaper\", \"three hours\", \"24/7\", \"30%\"), a set phrase (\"right now\") or a button label. "
           "Pick the words that carry the message: the number, the benefit, the pain or cost, the brand or product, "
           "the strong verb or adjective, the call to action. Never small words alone (the, to, your, is, are, that, "
           "it, of...), never vague verbs (get, go, make, do, have...)."),
}


def _locate(norm, item, used):
    """Place un mot ou une expression de l'IA dans le plan -> [indices] ou None. Mot exact, sinon meme racine
    (« gratuit » -> « gratuitement ») ; une expression doit se suivre dans le texte."""
    from .reel import _core
    toks = [t for t in (_core(x) for x in str(item).split()) if t]
    if not toks or len(toks) > 4:
        return None

    def same(x, n):
        return x == n or (len(n) >= 5 and len(x) >= 5 and (x.startswith(n[:6]) or n.startswith(x[:6])))

    for exact in (True, False):
        for i in range(len(norm) - len(toks) + 1):
            if i in used:
                continue
            if all((norm[i + k] == t) if exact else same(norm[i + k], t) for k, t in enumerate(toks)):
                return list(range(i, i + len(toks)))
    return None


def editorial(clips, language='fr', max_words=3):
    """clips = [{'id', 'words': [str | {w, start, end...}]}] ->
    {'banner': str, 'banners': [3 x str], 'highlights': {id: [i]}, 'emojis': {id: [[i, e]]}, 'picks': {id: [[i]]}}
    L'IA cite les mots (plus fiable que des numeros) ; on les replace dans le texte. Mots en couleur : l'IA propose
    (picks, du plus important au moins important), les regles de reel.auto_highlights valident et completent
    (un par groupe de sous-titres, jamais un mot outil, pas deux colles, pas le meme partout).
    language : langue de la video (bandeaux et mots en couleur dans cette langue) ; max_words : mots par sous-titre."""
    from .reel import _core, _words, idea_groups, reel_highlights
    timed = [{'id': c['id'], 'words': _words(c['words'])} for c in clips]
    plain = [{'id': c['id'], 'words': [w['w'] for w in c['words']]} for c in timed]
    # nombre MAXIMUM de mots cles par plan : un par idee (phrase ou morceau de longue phrase), pas un par ecran
    want = {c['id']: max(1, len(idea_groups(c['words']))) if c['words'] else 0 for c in timed}
    text = '\n'.join(f"[{c['id']}] (au plus {want[c['id']]} mots cles) " + ' '.join(c['words']) for c in plain)
    user = (
        "Voici la transcription d'un reel, decoupee en plans (identifiant entre crochets, puis le nombre MAXIMUM de "
        "mots cles pour ce plan).\n"
        f"{text}\n\n"
        "Reponds avec cet objet JSON :\n"
        '{"bandeaux": ["3 titres accrocheurs DIFFERENTS de 3 a 7 mots en MAJUSCULES, tires du PREMIER plan (le hook)"],\n'
        ' "plans": {"<identifiant>": {"couleur": ["mot ou expression", ...], "emoji": [["mot", "emoji"]]}}}\n'
        "« couleur » = les mots mis en couleur dans les sous-titres, du plus important au moins important : "
        "AU PLUS UN par phrase ou idee (le nombre indique est un maximum ; en mettre moins est mieux qu'un mot faible). "
        "Ordre de priorite : 1) un chiffre avec son unite, 2) le benefice, la douleur ou le cout, 3) la marque ou le "
        "produit, 4) un verbe fort ; dans la derniere phrase, le texte du bouton. "
        + HIGHLIGHT_RULES['en' if language == 'en' else 'fr'] +
        " Mets un mot cle dans la premiere phrase (l'accroche) et dans l'appel a l'action. "
        "Evite de reprendre le meme mot dans tous les plans. "
        "Au plus un emoji par plan, seulement s'il illustre clairement le mot choisi. "
        'Format emoji : [["salaire", "💸"]]. '
        "Chaque bandeau est une phrase naturelle et correcte en francais qui pique la curiosite, par exemple : "
        "« VOTRE CONCURRENT REPOND PLUS VITE », « CHAQUE MINUTE VOUS COUTE UN CLIENT », "
        "« L'ERREUR QUI VOUS COUTE CHER »."
    )
    if language and language != 'fr':
        name = LANGS.get(language, language)
        user += (f"\nIMPORTANT : la video est en {name}. Les bandeaux sont ecrits en {name}, naturels et corrects "
                 f"(les exemples ci-dessus ne servent qu'a montrer le ton). Les mots en couleur sont copies du texte, en {name}.")
    data = ask_json(EDITOR, user)
    banners = [str(b).strip().upper()[:80] for b in (data.get('bandeaux') or [data.get('banner') or '']) if str(b).strip()]
    banners = _check_banners(list(dict.fromkeys(banners))[:3], plain, language)
    banner = banners[0] if banners else ''
    # L'IA ecrit parfois « [c2] » au lieu de « c2 » : on normalise les identifiants.
    plans = {str(k).strip('[] '): v for k, v in (data.get('plans') or {}).items() if isinstance(v, dict)}
    picks, em = {}, {}
    for c in plain:
        norm = [_core(w) for w in c['words']]
        plan = plans.get(c['id'])
        if plan is None:
            continue  # plan oublie par l'IA : les regles seules s'en chargent
        items = plan.get('couleur') or []
        found, used = [], set()
        for item in (items if isinstance(items, list) else [items]):
            span = _locate(norm, item if not isinstance(item, list) else ' '.join(map(str, item)), used)
            if span is None and len(str(item).split()) > 1:  # expression mal recopiee : son mot le plus long
                word = max(str(item).split(), key=lambda x: len(_core(x)))
                span = _locate(norm, word, used)
            if span:
                found.append(span)
                used.update(span)
        picks[c['id']] = found[:want[c['id']]]  # au-dela du budget, l'IA n'est pas ecoutee
    hl = reel_highlights(timed, max_words, language, picks)
    for c in plain:
        norm = [_core(w) for w in c['words']]
        plan = plans.get(c['id']) or {}
        em[c['id']] = []
        for item in (plan.get('emoji') or [])[:1]:
            if isinstance(item, list) and len(item) == 2:
                span, e = _locate(norm, item[0], set()), str(item[1])
                i = span[-1] if span else None
            else:  # emoji seul : on l'accroche au premier mot colore du plan
                i, e = (hl[c['id']][0] if hl.get(c['id']) else None), str(item)
            if i is not None and _is_emoji(e):
                em[c['id']].append([i, e.strip()[:8]])
    return {'banner': banner, 'banners': banners, 'highlights': hl, 'emojis': em, 'picks': picks}
