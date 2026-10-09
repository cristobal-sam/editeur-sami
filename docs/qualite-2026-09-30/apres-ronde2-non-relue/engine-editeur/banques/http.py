"""Client HTTP commun aux banques : limite de requetes, reprises avec delai (429, erreurs serveur, reseau),
compteur de requetes, domaines verifies avant tout telechargement. La cle n'apparait jamais dans un message."""
import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from ..media import ROOT
from .base import BanqueErreur, Indisponible, LimiteAtteinte, NonConfiguree

CACHE = ROOT / 'runtime/cache/banques'
COMPTEUR = CACHE / 'compteur.json'
AGENT = 'EditeurSami/1.0 (monteur video local)'
RESEAU = (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError)


def write_json(path, data, indent=None):
    """Ecriture atomique (deux commandes peuvent tourner en meme temps)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'{path.name}.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding='utf-8')
    os.replace(tmp, path)


def read_counter():
    try:
        return json.loads(COMPTEUR.read_text(encoding='utf-8'))
    except Exception:
        return {}


def check_url(url, hosts):
    """Seulement https et les domaines de la banque (ex. pixabay.com et ses sous-domaines)."""
    u = urllib.parse.urlsplit(str(url))
    host = (u.hostname or '').lower()
    if u.scheme != 'https' or not any(host == h or host.endswith('.' + h) for h in hosts):
        raise BanqueErreur('Adresse de fichier refusee (domaine non autorise).')


class _Redirects(urllib.request.HTTPRedirectHandler):
    """Une redirection vers un autre domaine est refusee avant d'etre suivie."""

    def __init__(self, hosts):
        self.hosts = hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl, self.hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Http:
    def __init__(self, provider_id, secret=lambda: ''):
        self.pid = provider_id
        self.secret = secret  # la cle, seulement pour la masquer dans les messages

    def mask(self, text):
        s = self.secret()
        return str(text).replace(s, '***') if s else str(text)

    def _note(self, headers):
        """Compteur : requetes du jour et du mois, limite restante annoncee par la banque."""
        data = read_counter()
        c = data.setdefault(self.pid, {})
        day, month = time.strftime('%Y-%m-%d'), time.strftime('%Y-%m')
        if c.get('jour') != day:
            c['jour'], c['aujourdhui'] = day, 0
        if c.get('mois') != month:
            c['mois'], c['ce_mois'] = month, 0
        c['aujourdhui'] += 1
        c['ce_mois'] += 1
        h = {k.lower(): v for k, v in (headers or {}).items()}
        try:
            if 'x-ratelimit-remaining' in h:
                c['restant'] = int(h['x-ratelimit-remaining'])
                c['limite'] = int(h.get('x-ratelimit-limit') or 0)
                reset = int(float(h.get('x-ratelimit-reset') or 0))
                # Pixabay : secondes avant la remise a zero ; Pexels : horodatage UNIX
                c['reprise'] = reset if reset > 1e9 else time.time() + reset
        except ValueError:
            pass
        write_json(COMPTEUR, data)

    def _wait_quota(self):
        c = read_counter().get(self.pid, {})
        if c.get('restant', 1) <= 0:
            wait = c.get('reprise', 0) - time.time()
            if wait > 20:
                raise LimiteAtteinte(f'Limite de requetes de la banque atteinte : reessaie dans {int(wait // 60) + 1} min.')
            if wait > 0:
                time.sleep(wait + 0.5)

    def get(self, url, params=None, headers=None, timeout=20):
        """GET d'une API de banque avec reprises ; renvoie le corps (octets)."""
        if params:
            url += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
        self._wait_quota()
        delay = 1.5
        for attempt in range(4):
            req = urllib.request.Request(url, headers={'User-Agent': AGENT, **(headers or {})})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    body = r.read()
                    try:
                        self._note(dict(r.headers))
                    except OSError:
                        pass  # le compteur n'est qu'indicatif : la reponse compte plus
                    return body
            except urllib.error.HTTPError as e:
                try:
                    text = e.read().decode('utf-8', 'replace')[:300]
                except Exception:
                    text = ''
                if e.code == 429 and attempt < 3:
                    retry = e.headers.get('Retry-After') if e.headers else None
                    time.sleep(min(30.0, float(retry)) if retry and retry.isdigit() else delay)
                    delay *= 2.5
                    continue
                if e.code >= 500 and attempt < 2:
                    time.sleep(delay)
                    delay *= 2
                    continue
                if e.code == 429:
                    raise LimiteAtteinte('Trop de requetes vers la banque : reessaie dans une minute.')
                if e.code in (401, 403) or (e.code == 400 and 'key' in text.lower()):
                    raise NonConfiguree('Cle refusee par la banque : verifie la cle dans cles-api.env.')
                if e.code == 404:
                    raise BanqueErreur('Media introuvable dans la banque.')
                raise BanqueErreur(self.mask(f'Erreur {e.code} de la banque : {text}'))
            except RESEAU:
                if attempt < 2:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise Indisponible('Banque injoignable (connexion Internet ?).')
        raise Indisponible('Banque injoignable.')

    def download(self, url, dest, hosts, max_bytes=600 * 2 ** 20, timeout=60):
        """Telecharge un fichier d'une banque dans dest (fichier .part puis renommage). Domaine verifie,
        redirections verifiees, type de contenu verifie, taille plafonnee."""
        check_url(url, hosts)
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + '.part')
        opener = urllib.request.build_opener(_Redirects(hosts))
        delay = 2
        for attempt in range(3):
            req = urllib.request.Request(url, headers={'User-Agent': AGENT})
            try:
                with opener.open(req, timeout=timeout) as r, open(tmp, 'wb') as f:
                    ctype = (r.headers.get('content-type') or '').split(';')[0].strip().lower()
                    if not (ctype.startswith(('video/', 'image/')) or ctype in ('application/octet-stream', 'binary/octet-stream', '')):
                        raise BanqueErreur(f'Fichier inattendu ({ctype}).')
                    expected = int(r.headers.get('content-length') or 0)
                    n = 0
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        n += len(chunk)
                        if n > max_bytes:
                            raise BanqueErreur('Fichier trop gros.')
                        f.write(chunk)
                if expected and n < expected:
                    raise ConnectionError('telechargement incomplet')  # repris comme une coupure reseau
                if not n:
                    raise BanqueErreur('Fichier vide.')
                os.replace(tmp, dest)
                return dest
            except urllib.error.HTTPError as e:
                tmp.unlink(missing_ok=True)
                if e.code >= 500 and attempt < 2:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise BanqueErreur(f'Telechargement refuse par la banque (erreur {e.code}).')
            except BanqueErreur:
                tmp.unlink(missing_ok=True)
                raise
            except RESEAU:
                tmp.unlink(missing_ok=True)
                if attempt < 2:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise Indisponible('Telechargement impossible (connexion Internet ?).')
        raise Indisponible('Telechargement impossible.')

    def fetch(self, url, hosts, cache_file, max_bytes=40 * 2 ** 20, ttl=24 * 3600):
        """Apercu (vignette, petite video) garde en cache 24 h pour l'analyse."""
        cache_file = Path(cache_file)
        if cache_file.exists() and time.time() - cache_file.stat().st_mtime < ttl:
            return cache_file
        return self.download(url, cache_file, hosts, max_bytes=max_bytes, timeout=30)
