"""Alignement d'une transcription sur les phrases du script (alignement local tolerant aux ecarts)."""
import re
from difflib import SequenceMatcher

from .script import tokens

MATCH, NEAR, MISMATCH, GAP = 2.0, 1.0, -1.0, -1.0
END = re.compile(r'[.!?…]["»”]?$')


def take_tokens(words):
    """Jetons normalises de la prise, chacun relie a son mot Whisper (indice)."""
    out = []
    for i, w in enumerate(words):
        for t in tokens(w['w']):
            out.append((t, i))
    return out


def _stops(ttoks, words, pause=0.8):
    """Jetons qui terminent une phrase dans la prise : ponctuation finale ou pause marquee apres le mot.
    Un passage ne s'etend jamais par-dessus (il prendrait la fin de la phrase d'avant ou le debut de la suivante)."""
    out = set()
    if not words:
        return out
    for j, (_, i) in enumerate(ttoks):
        last_of_word = j + 1 == len(ttoks) or ttoks[j + 1][1] != i
        if not last_of_word:
            continue
        nxt = words[i + 1] if i + 1 < len(words) else None
        if END.search(words[i]['w'].strip()) or (nxt is not None and nxt['start'] - words[i]['end'] > pause):
            out.add(j)
    return out


def _sim(a, b):
    if a == b:
        return MATCH
    if min(len(a), len(b)) >= 4 and SequenceMatcher(None, a, b).ratio() >= 0.75:
        return NEAR
    if min(len(a), len(b)) >= 2 and abs(len(a) - len(b)) == 1 and (a.startswith(b) or b.startswith(a)):
        return NEAR  # « pi » / « pis », « ca » / « cas »
    return MISMATCH


def _local(ref, hyp, blocked):
    """Smith-Waterman : meilleur passage de `hyp` (jetons de prise) correspondant a `ref` (phrase)."""
    n, m = len(ref), len(hyp)
    H = [[0.0] * (m + 1) for _ in range(n + 1)]
    best = (0.0, 0, 0)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if blocked[j - 1]:
                continue
            s = max(0.0, H[i - 1][j - 1] + _sim(ref[i - 1], hyp[j - 1]), H[i - 1][j] + GAP, H[i][j - 1] + GAP)
            H[i][j] = s
            if s > best[0]:
                best = (s, i, j)
    score, i, j = best
    if score <= 0:
        return None
    matched, exact, ref_hit, j_end, i_end = 0, 0, set(), j, i
    while i > 0 and j > 0 and H[i][j] > 0:
        diag = H[i - 1][j - 1] + _sim(ref[i - 1], hyp[j - 1])
        if abs(H[i][j] - diag) < 1e-9:
            sim = _sim(ref[i - 1], hyp[j - 1])
            if sim > 0:
                matched += 1
                exact += sim == MATCH
                ref_hit.add(i - 1)
            i, j = i - 1, j - 1
        elif abs(H[i][j] - (H[i - 1][j] + GAP)) < 1e-9:
            i -= 1
        else:
            j -= 1
    return {'score': score, 'h0': j, 'h1': j_end, 'r0': i, 'r1': i_end, 'matched': matched, 'exact': exact, 'ref_hit': ref_hit}


def _rescue(h, ref, hyp, blocked, stops):
    """Mots du script retrouves tels quels juste avant ou juste apres le passage aligne (le comedien a change un
    mot au milieu : « crazy god damn old people » dit « crazy fucking old people »). Jamais au-dela d'une fin
    de phrase ou d'une pause de la prise."""
    before = set(ref[:h['r0']])
    j, found = h['h0'] - 1, []
    while before and j >= 0 and h['h0'] - j <= h['r0'] + 2 and not blocked[j] and j not in stops:
        if hyp[j] in before:
            found.append(j)
        j -= 1
    if found:
        idx = [k for k in range(h['r0']) if ref[k] in {hyp[x] for x in found}]
        h['h0'] = min(found)
        h['ref_hit'] |= set(idx)
        h['matched'] += len(idx)
        h['exact'] += len(idx)
        h['r0'] = min(idx)
    after = set(ref[h['r1']:])
    j, found = h['h1'], []
    while after and j < len(hyp) and j - h['h1'] < len(ref) - h['r1'] + 2 and not blocked[j] and (j - 1) not in stops:
        if hyp[j] in after:
            found.append(j)
        j += 1
    if found:
        idx = [k for k in range(h['r1'], len(ref)) if ref[k] in {hyp[x] for x in found}]
        h['h1'] = max(found) + 1
        h['ref_hit'] |= set(idx)
        h['matched'] += len(idx)
        h['exact'] += len(idx)
        h['r1'] = max(idx) + 1


def find(sentence_tokens, ttoks, min_coverage=0.5, max_hits=4, words=None):
    """Toutes les tentatives de la phrase dans la prise (une prise peut contenir plusieurs essais).
    words (mots Whisper de la prise) : fins de phrase et pauses, que les passages ne franchissent pas.
    Une phrase tres courte doit etre retrouvee mot pour mot (« There. » n'est pas « here », « Thank you. »
    n'est pas un « you » isole)."""
    hyp = [t for t, _ in ttoks]
    blocked = [False] * len(hyp)
    stops = _stops(ttoks, words) if words else set()
    n = len(sentence_tokens)
    need_exact = n if n <= 1 else 2 if n <= 3 else 0
    hits = []
    for _ in range(max_hits + 3):
        if len(hits) >= max_hits:
            break
        h = _local(sentence_tokens, hyp, blocked)
        if not h:
            break
        _rescue(h, sentence_tokens, hyp, blocked, stops)
        coverage = h['matched'] / n
        if coverage < min_coverage:
            break
        if h['exact'] < need_exact:
            # correspondance trop faible pour une phrase courte : on l'ecarte et on cherche plus loin
            for k in range(h['h0'], h['h1']):
                blocked[k] = True
            continue
        # Mots du debut de phrase non reconnus mais bien prononces juste avant : on les reprend
        # (sans remonter dans la phrase precedente).
        while h['r0'] > 0 and h['h0'] > 0 and not blocked[h['h0'] - 1] and (h['h0'] - 1) not in stops:
            h['h0'] -= 1
            h['r0'] -= 1
        span = h['h1'] - h['h0']
        h.update(coverage=coverage, inserted=max(0, span - h['matched']),
                 w0=ttoks[h['h0']][1], w1=ttoks[h['h1'] - 1][1],
                 missing_start=min(h['ref_hit']) > 1, missing_end=max(h['ref_hit']) < n - 2)
        hits.append(h)
        for k in range(h['h0'], h['h1']):
            blocked[k] = True
    return hits
