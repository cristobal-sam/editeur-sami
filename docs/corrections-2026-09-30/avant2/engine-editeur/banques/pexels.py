"""Pexels : videos et photos libres (licence Pexels : usage commercial permis, credit non obligatoire).

Desactive tant que PEXELS_API_KEY est vide (creation de nouvelles cles suspendue en septembre 2026).
Regles de l'API (https://www.pexels.com/api/documentation/) : 200 requetes/h et 20 000/mois
(en-tetes X-Ratelimit-*), lien vers Pexels et credit du createur la ou les resultats sont affiches."""
import json
import re

from .base import BanqueErreur, MediaProvider, media

VIDEOS = 'https://api.pexels.com/videos/'
PHOTOS = 'https://api.pexels.com/v1/'
ORIENT = {'portrait': 'portrait', 'paysage': 'landscape', 'carre': 'square'}
LOCALES = {'fr': 'fr-FR', 'en': 'en-US'}


def _slug_tags(url):
    """Pexels ne donne pas de mots-cles : on lit ceux de l'adresse (…/video/billets-de-banque-1234/)."""
    m = re.search(r'/(?:video|photo)/([a-z0-9-]+?)-\d+/?$', url or '')
    return m.group(1).split('-') if m else []


class PexelsProvider(MediaProvider):
    id = 'pexels'
    name = 'Pexels'
    env_key = 'PEXELS_API_KEY'
    hosts = ('pexels.com', 'vimeo.com')  # videos.pexels.com, images.pexels.com (anciens liens : player.vimeo.com)
    license = {'name': 'Licence Pexels', 'url': 'https://www.pexels.com/license/',
               'summary': "Usage commercial et modification permis, credit non obligatoire. Interdit : revendre le "
                          "fichier tel quel, montrer une personne sous un mauvais jour ou laisser croire qu'elle recommande un produit."}

    def _get(self, url, params=None):
        return json.loads(self.http.get(url, params, headers={'Authorization': self.key}))

    @staticmethod
    def _params(query, o):
        p = {'query': query[:100], 'per_page': max(1, min(80, int(o.get('per_page') or 20))), 'page': int(o.get('page') or 1),
             'locale': LOCALES.get(o.get('lang') or 'en', 'en-US')}
        if ORIENT.get(o.get('orientation')):
            p['orientation'] = ORIENT[o['orientation']]
        short = min(int(o.get('min_width') or 0), int(o.get('min_height') or 0)) or max(int(o.get('min_width') or 0), int(o.get('min_height') or 0))
        if short >= 2000:
            p['size'] = 'large'
        elif short >= 1000:
            p['size'] = 'medium'
        return p

    def _video(self, v):
        files = [{'name': f"{f.get('quality') or 'fichier'}-{f.get('height')}", 'width': f.get('width') or 0,
                  'height': f.get('height') or 0, 'size': 0, 'url': f.get('link', '')}
                 for f in v.get('video_files', []) if 'mp4' in (f.get('file_type') or '') and f.get('width')]
        smallest = min(files, key=lambda f: f['width'] * f['height']) if files else None
        pics = [p.get('picture') for p in v.get('video_pictures', []) if p.get('picture')]
        user = v.get('user') or {}
        return media(self, v['id'], 'video', width=v.get('width'), height=v.get('height'), duration=v.get('duration'),
                     preview=v.get('image') or (pics[0] if pics else ''), preview_video=smallest['url'] if smallest else None,
                     page_url=v.get('url', ''), author=user.get('name', ''), author_url=user.get('url', ''),
                     tags=_slug_tags(v.get('url')), files=files, stats={'pictures': pics[:6]})

    def _photo(self, p):
        src = p.get('src') or {}
        w, h = p.get('width') or 0, p.get('height') or 0
        k = min(1.0, 1880 / w, 1300 / h) if w and h else 1.0  # large2x tient dans 1880 x 1300 (proportions gardees)
        files = []
        if src.get('large2x'):
            files.append({'name': 'large2x', 'width': round(w * k), 'height': round(h * k), 'size': 0, 'url': src['large2x']})
        if src.get('original'):
            files.append({'name': 'original', 'width': w, 'height': h, 'size': 0, 'url': src['original']})
        tags = _slug_tags(p.get('url')) or re.findall(r'[a-z]{3,}', (p.get('alt') or '').lower())
        return media(self, p['id'], 'image', width=w, height=h, preview=src.get('medium') or src.get('small', ''),
                     page_url=p.get('url', ''), author=p.get('photographer', ''), author_url=p.get('photographer_url', ''),
                     tags=tags, files=files, stats={})

    def search_videos(self, query, o):
        return [self._video(v) for v in self._get(VIDEOS + 'search', self._params(query, o)).get('videos', [])]

    def search_images(self, query, o):
        return [self._photo(p) for p in self._get(PHOTOS + 'search', self._params(query, o)).get('photos', [])]

    def get_asset(self, asset_id, kind):
        if not str(asset_id).isdigit():
            raise BanqueErreur('Identifiant Pexels invalide.')
        if kind == 'video':
            return self._video(self._get(VIDEOS + f'videos/{asset_id}'))
        return self._photo(self._get(PHOTOS + f'photos/{asset_id}'))
