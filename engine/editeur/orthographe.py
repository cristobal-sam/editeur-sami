"""Relecture d'orthographe des mots transcrits (francais), sans toucher aux temps des mots.

La transcription recopie le son : « avant de vous le transférez », « appuyer sur le bouton » dit a « vous », « vos leads sont
closé », « Pi là ». Ces fautes s'affichent dans les sous-titres et dans les interfaces (un parcours « Qualifier ->
Transférez »). Regles sures seulement (homophones é / er / ez, accord apres « sont », « Pi ») : en cas de doute, rien ne
change. Chaque mot corrige garde son texte d'origine dans `asr`. Jamais sur un plan verrouille ; appelee a la creation du
reel (mots neufs), jamais sur une retouche du monteur."""
import re
import unicodedata

_PREP = ('de', "d'", 'à', 'a', 'pour', 'sans', 'par')
_CLITIQUES = ('le', 'la', 'les', "l'", 'lui', 'leur', 'vous', 'nous', 'me', "m'", 'te', "t'", 'se', "s'", 'y', 'en')
_MODAUX = ('peux', 'peut', 'pouvez', 'pouvons', 'peuvent', 'pourrez', 'pourriez', 'pourra', 'pourront', 'veux', 'veut', 'voulez',
           'voulons', 'veulent', 'voudriez', 'voudrais', 'dois', 'doit', 'devez', 'devons', 'doivent', 'devriez', 'devrait', 'vais',
           'vas', 'va', 'allez', 'allons', 'vont', 'faut', 'sais', 'sait', 'savez', 'aimeriez', 'aimerais', 'venez', 'viens')
_ADVERBES = ('bien', 'mieux', 'vite', 'rapidement', 'tout', 'toujours', 'jamais', 'pas', 'plus', 'déjà', 'deja', 'vraiment',
             'aussi', 'encore', 'mal', 'souvent', 'tous', 'toutes', 'simplement', 'directement', 'facilement')
_NOMS_EZ = ('nez', 'chez', 'assez', 'rez', 'raz')
_ETRE_PLURIEL = ('sont', 'étaient', 'etaient', 'seront', 'soient', 'furent', 'seraient')
# apres un imperatif « appuyez / cliquez / allez » : la suite habituelle d'une consigne
_SUITE_CONSIGNE = ('sur', 'le', 'la', 'les', "l'", 'ici', 'maintenant', 'vite', 'dès', 'des', 'simplement', 'directement', 'au', 'aux',
                   'dans', 'en', 'sans', 'tout', 'juste')
_LIAISONS_DEBUT = ('alors', 'donc', 'puis', 'ensuite', 'maintenant', 'et')
_FIN_PHRASE = re.compile(r'[.!?…]["»”)\]]*$')
# Accord du nom avec son determinant (le -s du pluriel ne s'entend pas : la transcription le met au hasard, « avec de la
# publicités »). Determinants toujours singuliers / toujours pluriels ; « le / la / l' » peuvent etre des pronoms devant un
# verbe (« tu la prends », « je le fais ») : jamais apres un sujet ou un autre pronom. « ces / ses / tes » (homophones de
# « c'est / s'est / t'es ») et « les » (pronom tres courant : « on les appelle ») ne sont jamais utilises.
_DET_SING = ('la', 'le', 'une', 'un', 'cette', 'cet', 'ce', 'chaque', 'votre', 'notre', 'ma', 'ta', 'sa', 'mon', 'ton', 'son', 'du', 'au')
_DET_PLUR = ('des', 'vos', 'nos', 'mes', 'plusieurs', 'quelques')
_AVANT_PRONOM = ('je', "j'", 'tu', 'il', 'elle', 'on', 'nous', 'vous', 'ils', 'elles', 'ne', "n'", 'me', "m'", 'te', "t'", 'se', "s'",
                 'lui', 'leur', 'y', 'en', 'qui', 'que', "qu'", 'ça', 'ca', 'cela')
_INVARIABLES = set(('temps corps poids fonds gens puits remords mœurs moeurs alors ailleurs plusieurs leurs mes tes ses nos vos ces des '
                    'les plus moins tous toutes très tres après apres vers depuis sans sous dans jamais toujours parfois autres mêmes '
                    'memes quelques certains certaines divers diverses nombreux nombreuses chez mais puis donc ainsi lors dehors fois '
                    'mois pays prix choix voix bras dos repas cas pas avis devis colis tapis permis fils jus succès accès progrès '
                    'procès process business focus bonus virus campus news sens gars tiers univers travers revers envers mars ours '
                    'volontiers legs lacs').split())
_NOMBRES = set(('deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize vingt trente quarante '
                'cinquante soixante cent cents mille million milliard').split())
_FIN_INVARIABLE = ('ss', 'us', 'is', 'os', 'as', 'ès', 'ys', 'ours', 'mps', 'rps', 'ids', 'nds')
_FIN_PLURIEL = ('é', 'ée', 'e', 'tion', 'sion', 'eur', 'er', 'ent', 'ant', 'at', 'ot', 'it', 'ard', 'ond', 'in', 'on', 'ain', 'ad')


def _sans_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def _parts(w):
    """« «transférez», » -> ('«', 'transférez', '», ') : ponctuation avant, mot, ponctuation apres."""
    m = re.match(r"^([^\w]*)(.*?)([^\w’']*)$", w, re.S)
    return (m.group(1), m.group(2), m.group(3)) if m else ('', w, '')


def _core(w):
    return _parts(w)[1].lower().replace('’', "'")


def _clitique(c):
    return c in _CLITIQUES or c.endswith("'") and c in _CLITIQUES


def _apostrophe(c):
    """« l'expérimenter » -> (\"l'\", 'expérimenter') ; sans apostrophe -> ('', c)."""
    m = re.match(r"^([a-zà-ÿ]{1,3}')(.+)$", c)
    return (m.group(1), m.group(2)) if m else ('', c)


def _remplacer_fin(w, ancienne, nouvelle):
    avant, mot, apres = _parts(w)
    if not mot.lower().endswith(ancienne):
        return w
    base = mot[: len(mot) - len(ancienne)]
    fin = nouvelle.upper() if mot[-1:].isupper() and len(mot) > 1 and mot[-2:].isupper() else nouvelle
    return f'{avant}{base}{fin}{apres}'


def _prec(cores, i, n=1):
    """Indice du mot n positions avant i, en sautant les clitiques ; None si absent."""
    j = i - 1
    while j >= 0 and _clitique(cores[j]):
        j -= 1
    return j if j >= 0 else None


def _debut_proposition(words, cores, i):
    """Le mot i commence une proposition : debut, apres une virgule / un point, ou apres « alors / donc » qui en commence une."""
    if i == 0:
        return True
    prev = str(words[i - 1].get('w') or '')
    if _FIN_PHRASE.search(prev.strip()) or prev.rstrip('»”") ').endswith((',', ';', ':')):
        return True
    if cores[i - 1] in _LIAISONS_DEBUT:
        return _debut_proposition(words, cores, i - 1)
    return False


def _phrase(words, i):
    """Mots (en minuscules) de la phrase qui contient le mot i, jusqu'a lui."""
    out = []
    for j in range(i - 1, -1, -1):
        if _FIN_PHRASE.search(str(words[j].get('w') or '').strip()):
            break
        out.append(_core(str(words[j].get('w') or '')))
    return list(reversed(out))


def _accord_determinant(cores, i, c):
    """Nom (ou adjectif) mal accorde avec le determinant qui le precede directement -> (fin, nouvelle fin) pour
    _remplacer_fin, ou None. Singulier : « de la publicités », « chaque leads », « l'entreprises ». Pluriel (prudent) :
    « vos lead », « des publicité ». Jamais un pronom devant un verbe, un mot invariable, un nombre ni un mot court."""
    det, base = _apostrophe(c)
    k = i - 1  # mot avant le determinant (sujet ou pronom -> « le / la / l' » est un pronom)
    if not det:
        if i == 0:
            return None
        det, k = cores[i - 1], i - 2
    if not re.fullmatch(r"[a-zà-ÿœ]+", base) or len(base) < 4 or base in _INVARIABLES or base in _NOMBRES:
        return None
    avant = cores[k] if k >= 0 else ''
    if det in _DET_SING or det == "l'":
        if det in ('la', 'le', "l'") and (avant in _AVANT_PRONOM or _apostrophe(avant)[0] in ("j'", "n'", "m'", "t'", "s'", "qu'")):
            return None
        if base.endswith('s') and not base.endswith(_FIN_INVARIABLE):
            return ('s', '')
        return None
    if det in _DET_PLUR and not base.endswith(('s', 'x', 'z')):
        fins = ('é', 'ée', 'tion', 'sion', 'eur') if det == 'des' else _FIN_PLURIEL  # « des » peut être « dès » mal transcrit
        if base.endswith(fins) and not base.endswith('ment') and base not in ('maintenant', 'demain', 'avant', 'pendant', 'devant', 'durant'):
            return (base[-1], base[-1] + 's')
    return None


def corriger_mots(words, lang='fr', vouvoiement=None):
    """Corrige en place les mots d'un plan (liste de {w, start, end...}) ; -> [(indice, avant, apres, regle)]. Mots coupes ou
    masques compris (le texte reste juste). vouvoiement : la video s'adresse a « vous » (sinon deduit des mots du plan)."""
    if lang != 'fr' or not words:
        return []
    cores = [_core(str(w.get('w') or '')) for w in words]
    if vouvoiement is None:
        vouvoiement = cores.count('vous') >= 2 and cores.count('vous') > cores.count('tu') + cores.count('toi')
    changes = []

    def change(i, nouveau, regle):
        avant = str(words[i]['w'])
        if nouveau and nouveau != avant:
            words[i].setdefault('asr', avant)
            words[i]['w'] = nouveau
            cores[i] = _core(nouveau)
            changes.append((i, avant, nouveau, regle))

    for i, w in enumerate(words):
        raw = str(w.get('w') or '')
        avant, mot, apres = _parts(raw)
        c = cores[i]
        if not mot or (mot[:1].isupper() and i > 0 and not _FIN_PHRASE.search(str(words[i - 1].get('w') or '').strip())
                       and c != 'pi'):
            continue  # nom propre ou mot en capitales au milieu d'une phrase : jamais touche
        _, base = _apostrophe(c)
        j = _prec(cores, i)
        jc = cores[j] if j is not None else ''
        # « Pi là » : « Puis »
        if c == 'pi' and i + 1 < len(words):
            change(i, f"{avant}{'P' if mot[:1].isupper() else 'p'}uis{apres}", 'puis')
            continue
        # infinitif apres une preposition (avec ses pronoms) : « avant de vous le transférez » -> « transférer »
        if base.endswith('ez') and base not in _NOMS_EZ and len(base) > 4 and jc in _PREP and j is not None and j < i:
            change(i, _remplacer_fin(raw, 'ez', 'er'), 'infinitif après une préposition')
            continue
        # infinitif apres un verbe comme pouvoir, vouloir, aller : « vous allez payé » -> « payer »
        if jc in _MODAUX and j is not None and len(base) > 4 and (base.endswith('ez') and base not in _NOMS_EZ or base.endswith('é')):
            change(i, _remplacer_fin(raw, 'ez' if base.endswith('ez') else 'é', 'er'), 'infinitif après un verbe')
            continue
        # deux infinitifs coordonnes : « à bien qualifier et éduqué » -> « éduquer »
        if c in ('et', 'ou') or not (base.endswith(('é', 'ez')) and len(base) > 4):
            pass
        elif i >= 2 and cores[i - 1] in ('et', 'ou'):
            k = i - 2
            while k >= 0 and cores[k] in _ADVERBES:
                k -= 1
            left = cores[k] if k >= 0 else ''
            ctx = cores[max(0, k - 3):k]
            if left.endswith('er') and len(left) > 4 and any(x in _PREP or x in _MODAUX for x in ctx):
                change(i, _remplacer_fin(raw, 'ez' if base.endswith('ez') else 'é', 'er'), 'infinitifs coordonnés')
                continue
        # consigne donnee a « vous » : « si vous voulez…, appuyer sur le bouton » -> « appuyez »
        if (vouvoiement and base.endswith('er') and len(base) > 4 and i + 1 < len(words) and cores[i + 1] in _SUITE_CONSIGNE
                and _debut_proposition(words, cores, i) and jc not in _PREP and jc not in _MODAUX):
            phrase = _phrase(words, i)
            si_vous = any(phrase[k] == 'si' and phrase[k + 1] == 'vous' for k in range(len(phrase) - 1))
            if si_vous or (i > 0 and cores[i - 1] in _LIAISONS_DEBUT):
                change(i, _remplacer_fin(raw, 'er', 'ez'), 'consigne à « vous »')
                continue
        # accord apres « sont » : « vos leads sont closé » -> « closés »
        k = i - 1
        while k >= 0 and cores[k] in _ADVERBES:
            k -= 1
        if k >= 0 and cores[k] in _ETRE_PLURIEL and len(base) > 3 and not _apostrophe(c)[0]:
            if base.endswith('ée'):
                change(i, _remplacer_fin(raw, 'ée', 'ées'), 'accord au pluriel')
                continue
            elif base.endswith('é'):
                change(i, _remplacer_fin(raw, 'é', 'és'), 'accord au pluriel')
                continue
        # accord avec le determinant : « avec de la publicités » -> « publicité », « vos lead » -> « leads »
        nouveau = _accord_determinant(cores, i, c)
        if nouveau is not None:
            change(i, _remplacer_fin(raw, *nouveau), 'accord avec le déterminant')
    # majuscule en debut de phrase (« complète. alors » -> « Alors »)
    for i in range(1, len(words)):
        raw = str(words[i].get('w') or '')
        avant, mot, apres = _parts(raw)
        if mot[:1].isalpha() and mot[:1].islower() and _FIN_PHRASE.search(str(words[i - 1].get('w') or '').strip()) \
                and not _FIN_PHRASE.search(str(words[i - 1].get('w') or '').strip()).group(0).startswith('…'):
            change(i, f'{avant}{mot[:1].upper()}{mot[1:]}{apres}', 'majuscule')
    return changes


def corriger(reel, ids=None):
    """Relit les mots de chaque plan (ou des plans `ids`) du reel ; plans verrouilles jamais touches. -> [changements]."""
    from . import verrous
    from .reel import reel_language
    lang = reel_language(reel)
    if lang != 'fr':
        return []
    tous = [str(w.get('w') or '').lower() for c in reel.get('clips') or [] for w in c.get('words') or []]
    vous = sum(1 for x in tous if _core(x) == 'vous')
    tu = sum(1 for x in tous if _core(x) in ('tu', 'toi'))
    out = []
    for c in reel.get('clips') or []:
        if (ids is not None and c['id'] not in ids) or verrous.is_locked(c):
            continue
        for i, avant, apres, regle in corriger_mots(c.get('words') or [], lang, vouvoiement=vous >= 3 and vous > tu):
            out.append({'plan': c['id'], 'mot': i, 'avant': avant, 'apres': apres, 'regle': regle})
    return out


# Verbes d'action des parcours (« Qualifier -> Transférer ») : toujours a l'infinitif, quelle que soit la forme dite
_INFINITIFS = {'fr': (('qualifi', 'Qualifier'), ('educ', 'Éduquer'), ('transfer', 'Transférer'), ('repond', 'Répondre'),
                      ('rappel', 'Rappeler'), ('appel', 'Appeler'), ('deleg', 'Déléguer'), ('relanc', 'Relancer'), ('envo', 'Envoyer'),
                      ('convert', 'Convertir'), ('sign', 'Signer'), ('clos', 'Closer'), ('vend', 'Vendre')),
               'en': (('qualif', 'Qualify'), ('educat', 'Educate'), ('transfer', 'Transfer'), ('respond', 'Respond'), ('answer', 'Answer'),
                      ('callback', 'Call back'), ('call', 'Call'), ('delegat', 'Delegate'), ('follow', 'Follow up'), ('send', 'Send'),
                      ('convert', 'Convert'), ('sign', 'Sign'), ('clos', 'Close'), ('sell', 'Sell'))}


def infinitif(mot, lang='fr'):
    """Libelle d'action a l'infinitif (« transférez », « éduqué » -> « Transférer », « Éduquer ») ; mot inconnu : le mot dit,
    avec une majuscule, ramene a l'infinitif s'il finit comme un verbe du 1er groupe conjugue."""
    lang = 'en' if lang == 'en' else 'fr'
    m = _parts(str(mot))[1]
    n = _sans_accents(m.lower())
    for stem, inf in _INFINITIFS[lang]:
        if n.startswith(stem):
            return inf
    if lang == 'fr':
        for fin in ('ées', 'és', 'ée', 'ez', 'é'):
            if m.lower().endswith(fin) and len(m) > len(fin) + 3:
                m = m[: len(m) - len(fin)] + 'er'
                break
    return m[:1].upper() + m[1:]


def verifier(texte, lang='fr'):
    """Fautes probables dans un texte affiche (interface, sous-titre) : [(mot, correction, regle)]. Meme regles que
    corriger_mots, sur une copie (rien n'est modifie)."""
    mots = [{'w': x} for x in str(texte or '').split()]
    return [(a, b, r) for _, a, b, r in corriger_mots(mots, lang, vouvoiement=True) if r != 'majuscule']
