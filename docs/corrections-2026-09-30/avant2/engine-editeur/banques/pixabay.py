"""Pixabay : images et videos libres (licence Pixabay : usage commercial permis, credit non obligatoire).

Regles de l'API (https://pixabay.com/api/docs/) respectees par le service :
- 100 requetes par 60 s (en-tetes X-RateLimit-*), resultats gardes en cache 24 h ;
- liens d'images valables 24 h, pas de lien permanent : le media retenu est telecharge ;
- montrer la source des medias la ou les resultats sont affiches ; pas de telechargement en masse."""
import json

from .base import BanqueErreur, MediaProvider, media

API = 'https://pixabay.com/api/'


class PixabayProvider(MediaProvider):
    id = 'pixabay'
    name = 'Pixabay'
    env_key = 'PIXABAY_API_KEY'
    hosts = ('pixabay.com',)  # pixabay.com, cdn.pixabay.com
    video_orientation = False  # l'API video n'a pas de filtre d'orientation
    license = {'name': 'Licence de contenu Pixabay', 'url': 'https://pixabay.com/service/license-summary/',
               'summary': "Usage commercial et modification permis, credit non obligatoire. Interdit : revendre le "
                          "fichier tel quel, usage trompeur, personnes ou marques reconnaissables dans une pub."}

    def _query(self, path, params):
        return json.loads(self.http.get(API + path, {'key': self.key, **params}))

    @staticmethod
    def _params(query, o):
        p = {'q': query[:100], 'lang': o.get('lang') or 'en', 'safesearch': 'true',
             'per_page': max(3, min(200, int(o.get('per_page') or 20))), 'page': int(o.get('page') or 1)}
        for k in ('min_width', 'min_height'):
            if o.get(k):
                p[k] = int(o[k])
        return p

    def _video(self, h):
        v = h.get('videos') or {}
        files = []
        for n in ('tiny', 'small', 'medium', 'large'):
            r = v.get(n) or {}
            if r.get('url') and r.get('width'):
                files.append({'name': n, 'width': r['width'], 'height': r['height'], 'size': r.get('size', 0), 'url': r['url']})
        smallest = min(files, key=lambda f: f['width'] * f['height']) if files else None
        thumb = next(((v.get(n) or {}).get('thumbnail') for n in ('small', 'medium', 'tiny', 'large') if (v.get(n) or {}).get('thumbnail')), '')
        return media(self, h['id'], 'video', width=0, height=0, duration=h.get('duration'), preview=thumb,
                     preview_video=smallest['url'] if smallest else None, page_url=h.get('pageURL', ''),
                     author=h.get('user', ''), author_url=f"https://pixabay.com/users/{h.get('user', '')}-{h.get('user_id', '')}/",
                     tags=[t.strip() for t in str(h.get('tags', '')).split(',')], files=files,
                     stats={'downloads': h.get('downloads', 0), 'likes': h.get('likes', 0), 'views': h.get('views', 0),
                            'kind': h.get('type', '')})

    def _image(self, h):
        w, hh = h.get('imageWidth', 0), h.get('imageHeight', 0)

        def scaled(side):
            k = min(1.0, side / max(w, hh)) if w and hh else 1.0
            return round(w * k), round(hh * k)

        files = []
        if h.get('largeImageURL'):
            files.append({'name': 'large', **dict(zip(('width', 'height'), scaled(1280))), 'size': 0, 'url': h['largeImageURL']})
        if h.get('fullHDURL'):  # acces complet de l'API seulement
            files.append({'name': 'fullhd', **dict(zip(('width', 'height'), scaled(1920))), 'size': 0, 'url': h['fullHDURL']})
        if h.get('imageURL'):
            files.append({'name': 'original', 'width': w, 'height': hh, 'size': h.get('imageSize', 0), 'url': h['imageURL']})
        web = h.get('webformatURL') or ''
        return media(self, h['id'], 'image', width=w, height=hh, preview=web.replace('_640', '_340') if web else h.get('previewURL', ''),
                     page_url=h.get('pageURL', ''), author=h.get('user', ''),
                     author_url=f"https://pixabay.com/users/{h.get('user', '')}-{h.get('user_id', '')}/",
                     tags=[t.strip() for t in str(h.get('tags', '')).split(',')], files=files,
                     stats={'downloads': h.get('downloads', 0), 'likes': h.get('likes', 0), 'views': h.get('views', 0),
                            'kind': h.get('type', '')})

    def search_videos(self, query, o):
        p = self._params(query, o)
        p['video_type'] = o.get('video_type') or 'all'
        return [self._video(h) for h in self._query('videos/', p).get('hits', [])]

    def search_images(self, query, o):
        p = self._params(query, o)
        p['image_type'] = 'photo'
        orient = {'portrait': 'vertical', 'paysage': 'horizontal'}.get(o.get('orientation'))
        if orient:
            p['orientation'] = orient
        return [self._image(h) for h in self._query('', p).get('hits', [])]

    def get_asset(self, asset_id, kind):
        hits = self._query('videos/' if kind == 'video' else '', {'id': str(asset_id)}).get('hits') or []
        if not hits:
            raise BanqueErreur('Media introuvable dans la banque.')
        return self._video(hits[0]) if kind == 'video' else self._image(hits[0])
