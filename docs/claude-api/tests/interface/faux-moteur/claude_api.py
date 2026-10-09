# FAUX claude_api (copie de test) : seulement ce que le serveur lit sans appel (estimation_video par modele).
MODELES = ('claude-sonnet-5-5', 'claude-haiku-4-5', 'claude-opus-5-5')
_PAR_VIDEO = {'claude-sonnet-5-5': (0.0451, 0.0289, 0.055), 'claude-haiku-4-5': (0.015, 0.0107, 0.0213), 'claude-opus-5-5': (0.0902, 0.0577, 0.11)}


def estimation_video(modele=None):
    m = modele if modele in MODELES else MODELES[0]
    c, k, r = _PAR_VIDEO[m]
    return {'modele': m, 'nom': m, 'cerveau': c, 'consigne': k, 'critique': r, 'par_video': round(c + k, 4),
            'videos_avec_credit': int(2.0 // (c + k)), 'texte': f'Environ {c + k:.2f} $ par vidéo (faux).'}
