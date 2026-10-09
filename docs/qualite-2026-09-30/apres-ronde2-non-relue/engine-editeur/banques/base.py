"""Banques de medias libres : format commun d'un media externe et interface d'un fournisseur.

Le reste de l'editeur ne connait que ce format : il ne sait pas quelle banque repond. Ajouter une banque =
un fichier dans ce dossier (une classe MediaProvider) + une ligne dans FOURNISSEURS (banques/__init__.py)."""
import os


class BanqueErreur(Exception):
    """Erreur lisible par l'utilisateur (ne contient jamais la cle)."""


class NonConfiguree(BanqueErreur):
    pass


class LimiteAtteinte(BanqueErreur):
    pass


class Indisponible(BanqueErreur):
    pass


def orientation(w, h):
    if not w or not h:
        return 'carre'
    r = w / h
    return 'portrait' if r < 0.95 else 'paysage' if r > 1.05 else 'carre'


def qualite(w, h):
    short = min(w or 0, h or 0)
    return '4K' if short >= 2000 else 'HD' if short >= 1000 else '720p' if short >= 700 else 'SD'


def media(provider, pid, kind, *, width, height, preview, page_url, author='', author_url='', duration=None,
          preview_video=None, tags=(), files=(), stats=None):
    """Media externe au format commun. files = rendus telechargeables [{name, width, height, size, url}] ;
    width/height = le plus grand rendu telechargeable (qualite reelle, pas celle de l'original)."""
    files = [f for f in files if f.get('url') and f.get('width')]
    if files:
        best = max(files, key=lambda f: f['width'] * f['height'])
        width, height = best['width'], best['height']
    return {
        'provider': provider.id, 'providerName': provider.name, 'id': str(pid), 'type': kind,
        'width': int(width or 0), 'height': int(height or 0), 'duration': duration,
        'orientation': orientation(width, height), 'quality': qualite(width, height),
        'preview': preview or '', 'previewVideo': preview_video, 'author': author or '', 'authorUrl': author_url or '',
        'pageUrl': page_url or '', 'tags': [t for t in tags if t], 'files': files, 'stats': stats or {},
        'license': provider.license,
    }


class MediaProvider:
    """Interface commune d'une banque. Les requetes passent par self.http (cache, limites, reprises, cle masquee)."""
    id = ''
    name = ''
    env_key = ''        # variable d'environnement de la cle (ou ligne de cles-api.env)
    types = ('video', 'image')
    hosts = ()          # domaines autorises pour les fichiers et les apercus
    license = {}

    def __init__(self, http):
        self.http = http

    @property
    def key(self):
        return os.environ.get(self.env_key, '').strip()

    def active(self):
        return bool(self.key)

    def search_videos(self, query, options):
        raise NotImplementedError

    def search_images(self, query, options):
        raise NotImplementedError

    def get_asset(self, asset_id, kind):
        raise NotImplementedError

    def get_preview(self, asset):
        return asset['preview']

    def get_metadata(self, asset):
        """Metadonnees gardees avec le fichier : source, auteur, licence."""
        return {k: asset.get(k) for k in ('provider', 'providerName', 'id', 'type', 'author', 'authorUrl', 'pageUrl', 'preview',
                                          'width', 'height', 'duration', 'tags', 'license')}

    def pick_file(self, asset, quality='auto', target=(1080, 1920)):
        """Rendu a telecharger. 'auto' : le plus petit qui garde 1080 px sur le petit cote (le media optimise
        de l'editeur ne garde pas plus) ; sinon le plus grand disponible."""
        files = sorted(asset['files'], key=lambda f: f['width'] * f['height'])
        if not files:
            raise BanqueErreur('Aucun fichier telechargeable pour ce media.')
        if quality and quality != 'auto':
            named = [f for f in files if f['name'] == quality]
            if named:
                return named[0]
        need = min(1080, min(target))
        return next((f for f in files if min(f['width'], f['height']) >= need), files[-1])

    def download_asset(self, asset, quality, dest, target=(1080, 1920)):
        """Telecharge le rendu choisi (domaine verifie) ; renvoie le rendu."""
        f = self.pick_file(asset, quality, target)
        self.http.download(f['url'], dest, self.hosts)
        return f
