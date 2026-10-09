"""Lecture du texte d'un PDF sans librairie externe (zlib, re) : scripts exportes de Word, Google Docs, Final Draft,
Celtx, Pages... Objets (flux d'objets et tables xref compressees comprises), filtres Flate/LZW/ASCIIHex/ASCII85,
pages dans l'ordre, polices (ToUnicode, Differences, WinAnsi/MacRoman/Standard, table cmap TrueType), lignes
reconstituees par leur position. Un PDF scanne (image seule) ou protege donne un message clair (ErreurPdf).

lignes(pdf) -> pages de lignes {'x','x1','y','h','texte'} (points, y vers le haut) ; paragraphes(pages) -> texte suivi ;
texte(pdf) -> un paragraphe par ligne."""
import base64
import binascii
import math
import re
import struct
import unicodedata
import zlib
from collections import Counter
from pathlib import Path


class ErreurPdf(Exception):
    """PDF dont on ne peut pas lire le texte (message pour l'utilisateur)."""


# ---------- syntaxe PDF ----------

class Name(str):
    """/Nom"""


class Kw(str):
    """Mot-cle ou operateur (obj, stream, Tj, BT...)."""


class Ref:
    __slots__ = ('num', 'gen')

    def __init__(self, num, gen):
        self.num, self.gen = num, gen


class Stream:
    """Flux : dictionnaire + donnees brutes, decodees a la demande."""

    def __init__(self, d, raw, doc):
        self.d, self.raw, self.doc, self._data = d, raw, doc, None

    def get(self, key, default=None):
        return self.d.get(key, default)

    def data(self):
        if self._data is None:
            try:
                self._data = _decode(self.doc, self.d, self.raw)
            except Exception:
                self._data = b''
            self._data = self._data or b''
        return self._data


class _Fin(Exception):
    pass


_B = rb'\x00\t\n\x0c\r '  # blancs PDF
_REG = rb'[^\x00\t\n\x0c\r ()<>\[\]{}/%]'
_WS = re.compile(rb'(?:[' + _B + rb']+|%[^\r\n]*)*+')
_TOKEN = re.compile(rb'(?:[' + _B + rb']+|%[^\r\n]*)*+(?:(<<|>>|[\[\]{}])|(\()|<([0-9A-Fa-f' + _B + rb']*)>|/(' + _REG
                    + rb'*)|(' + _REG + rb'+))')
_NUM = re.compile(rb'[+-]?(?:\d+\.?\d*|\.\d+)$')
_REF = re.compile(rb'[' + _B + rb']+(\d+)[' + _B + rb']+R(?![^' + _B + rb'()<>\[\]{}/%])')
_LIT = re.compile(rb'[()\\]')
_ESC = {ord('n'): b'\n', ord('r'): b'\r', ord('t'): b'\t', ord('b'): b'\b', ord('f'): b'\f'}


def _literal(data, pos):
    """Chaine (...) : pos est juste apres la parenthese ouvrante. -> (octets, position suivante)."""
    out, depth = bytearray(), 1
    while True:
        m = _LIT.search(data, pos)
        if not m:
            out += data[pos:]
            return bytes(out), len(data)
        i = m.start()
        out += data[pos:i]
        c = data[i]
        if c == 0x5C:  # barre oblique inverse
            nxt = data[i + 1] if i + 1 < len(data) else None
            pos = i + 2
            if nxt is None:
                pos = i + 1
            elif nxt in _ESC:
                out += _ESC[nxt]
            elif 0x30 <= nxt <= 0x37:  # octal \ddd
                j = i + 1
                while j < len(data) and j < i + 4 and 0x30 <= data[j] <= 0x37:
                    j += 1
                out.append(int(data[i + 1:j], 8) & 0xFF)
                pos = j
            elif nxt == 0x0D:  # fin de ligne echappee
                pos = i + 3 if data[i + 2:i + 3] == b'\n' else i + 2
            elif nxt != 0x0A:
                out.append(nxt)
        elif c == 0x28:
            depth += 1
            out.append(c)
            pos = i + 1
        else:
            depth -= 1
            if depth == 0:
                return bytes(out), i + 1
            out.append(c)
            pos = i + 1


def _hex(h):
    h = re.sub(rb'[^0-9A-Fa-f]', b'', h)
    return binascii.unhexlify(h + b'0' if len(h) % 2 else h)


def _obj(data, pos, refs=True):
    """Objet PDF a partir de pos -> (valeur, position suivante). Nombres, /Noms (Name), chaines (bytes), tableaux,
    dictionnaires, references (Ref), mots-cles (Kw)."""
    m = _TOKEN.match(data, pos)
    if not m:
        w = _WS.match(data, pos).end()
        if w >= len(data):
            raise _Fin()
        return Kw(''), w + 1  # caractere parasite : ignore
    end = m.end()
    t = m.group(1)
    if t:
        if t == b'<<':
            d = {}
            while True:
                m2 = _TOKEN.match(data, end)
                if not m2:
                    if _WS.match(data, end).end() >= len(data):
                        return d, len(data)
                    end = _WS.match(data, end).end() + 1
                    continue
                if m2.group(1) == b'>>':
                    return d, m2.end()
                key, end = _obj(data, end, refs)
                if not isinstance(key, Name):
                    continue
                m3 = _TOKEN.match(data, end)
                if m3 and m3.group(1) == b'>>':
                    d[key] = None
                    return d, m3.end()
                d[key], end = _obj(data, end, refs)
        if t == b'[':
            arr = []
            while True:
                m2 = _TOKEN.match(data, end)
                if not m2:
                    if _WS.match(data, end).end() >= len(data):
                        return arr, len(data)
                    end = _WS.match(data, end).end() + 1
                    continue
                if m2.group(1) == b']':
                    return arr, m2.end()
                v, end = _obj(data, end, refs)
                arr.append(v)
        return Kw(t.decode('latin-1')), end
    if m.group(2):
        return _literal(data, end)
    if m.group(3) is not None:
        return _hex(m.group(3)), end
    if m.group(4) is not None:
        raw = m.group(4)
        if b'#' in raw:
            raw = re.sub(rb'#([0-9A-Fa-f]{2})', lambda x: bytes([int(x.group(1), 16)]), raw)
        return Name(raw.decode('utf-8', 'replace') if raw.isascii() is False else raw.decode('latin-1')), end
    tok = m.group(5)
    if _NUM.match(tok):
        if b'.' in tok:
            return float(tok), end
        n = int(tok)
        if refs:
            r = _REF.match(data, end)
            if r:
                return Ref(n, int(r.group(1))), r.end()
        return n, end
    word = tok.decode('latin-1')
    if word == 'true':
        return True, end
    if word == 'false':
        return False, end
    if word == 'null':
        return None, end
    return Kw(word), end


# ---------- filtres ----------

def _inflate(data):
    try:
        return zlib.decompress(data)
    except zlib.error:
        pass
    for wbits in (15, -15):  # flux tronque ou abime : on garde ce qui se decompresse
        d, out = zlib.decompressobj(wbits), []
        try:
            for i in range(0, len(data), 4096):
                out.append(d.decompress(data[i:i + 4096]))
        except zlib.error:
            pass
        if any(out):
            return b''.join(out)
    return b''


def _lzw(data, early=1):
    out, table = bytearray(), [bytes([i]) for i in range(256)] + [b'', b'']
    bits, buf, nbits, prev = 9, 0, 0, None
    for byte in data:
        buf = ((buf << 8) | byte) & 0xFFFFFF
        nbits += 8
        while nbits >= bits:
            nbits -= bits
            code = (buf >> nbits) & ((1 << bits) - 1)
            if code == 256:
                table, bits, prev = table[:258], 9, None
                continue
            if code == 257:
                return bytes(out)
            if code < len(table):
                entry = table[code]
                if prev is not None and len(table) < 4096:
                    table.append(prev + entry[:1])
            elif prev is not None and code == len(table):
                entry = prev + prev[:1]
                table.append(entry)
            else:
                return bytes(out)
            out += entry
            prev = entry
            if len(table) + early >= (1 << bits) and bits < 12:
                bits += 1
    return bytes(out)


def _a85(data):
    data = re.sub(rb'[' + _B + rb']', b'', data)
    if data.startswith(b'<~'):
        data = data[2:]
    if b'~>' in data:
        data = data[:data.index(b'~>')]
    try:
        return base64.a85decode(data)
    except ValueError:
        return base64.a85decode(data[:len(data) - len(data) % 5]) if len(data) >= 5 else b''


def _rl(data):
    out, i = bytearray(), 0
    while i < len(data):
        n = data[i]
        i += 1
        if n == 128:
            break
        if n < 128:
            out += data[i:i + n + 1]
            i += n + 1
        else:
            out += data[i:i + 1] * (257 - n)
            i += 1
    return bytes(out)


def _predict(data, p):
    """Predicteurs PNG (10-15) et TIFF (2) des flux compresses (tables xref surtout)."""
    pred = int(p.get('Predictor') or 1)
    if pred < 2:
        return data
    colors, bpc, cols = int(p.get('Colors') or 1), int(p.get('BitsPerComponent') or 8), int(p.get('Columns') or 1)
    bpp, row = max(1, colors * bpc // 8), (colors * bpc * cols + 7) // 8
    out = bytearray()
    if pred == 2:
        if bpc != 8:
            return data
        for i in range(0, len(data), row):
            cur = bytearray(data[i:i + row])
            for j in range(bpp, len(cur)):
                cur[j] = (cur[j] + cur[j - bpp]) & 255
            out += cur
        return bytes(out)
    prev = bytearray(row)
    for i in range(0, len(data), row + 1):
        ft, cur = data[i], bytearray(data[i + 1:i + 1 + row])
        cur.extend(bytes(row - len(cur)))
        if ft == 1:
            for j in range(bpp, row):
                cur[j] = (cur[j] + cur[j - bpp]) & 255
        elif ft == 2:
            for j in range(row):
                cur[j] = (cur[j] + prev[j]) & 255
        elif ft == 3:
            for j in range(row):
                cur[j] = (cur[j] + ((cur[j - bpp] if j >= bpp else 0) + prev[j]) // 2) & 255
        elif ft == 4:
            for j in range(row):
                a, b, c = (cur[j - bpp] if j >= bpp else 0), prev[j], (prev[j - bpp] if j >= bpp else 0)
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                cur[j] = (cur[j] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out += cur
        prev = cur
    return bytes(out)


def _decode(doc, d, raw):
    filters, parms = doc.r(d.get('Filter')), doc.r(d.get('DecodeParms'))
    if not filters:
        return raw
    if not isinstance(filters, list):
        filters, parms = [filters], [parms]
    elif not isinstance(parms, list):
        parms = [parms] * len(filters)
    data = raw
    for i, f in enumerate(filters):
        f = str(doc.r(f))
        p = doc.r(parms[i]) if i < len(parms) else None
        p = p if isinstance(p, dict) else {}
        if f in ('FlateDecode', 'Fl'):
            data = _predict(_inflate(data), p)
        elif f in ('LZWDecode', 'LZW'):
            data = _predict(_lzw(data, int(p.get('EarlyChange', 1))), p)
        elif f in ('ASCIIHexDecode', 'AHx'):
            data = _hex(data.split(b'>')[0])
        elif f in ('ASCII85Decode', 'A85'):
            data = _a85(data)
        elif f in ('RunLengthDecode', 'RL'):
            data = _rl(data)
        elif f != 'Crypt':
            return None  # image (DCT, JPX, CCITT, JBIG2) : pas de texte
    return data


# ---------- document : table des objets, pages ----------

_OBJHDR = re.compile(rb'[' + _B + rb']*(\d+)[' + _B + rb']+(\d+)[' + _B + rb']+obj')
_STREAM = re.compile(rb'[' + _B + rb']*stream(?:\r\n|\n|\r)?')
_XSUB = re.compile(rb'[' + _B + rb']*(\d+)[ \t]+(\d+)[ \t]*(?=[\r\n])')
_XENT = re.compile(rb'[' + _B + rb']*(\d{1,10})[ \t]+(\d{1,5})[ \t]+([nf])')


class _Doc:
    def __init__(self, data):
        self.data, self.xref, self.trailer = data, {}, {}
        self.cache, self.stms, self.fonts, self._scan = {}, {}, {}, None
        try:
            self._read_xref()
        except Exception:
            self.xref = {}
        if not isinstance(self.r(self.trailer.get('Root')), dict):
            self._rebuild()

    # -- table xref (classique, compressee, hybride, mises a jour successives)
    def _read_xref(self):
        data = self.data
        at = data.rfind(b'startxref')
        pos = int(re.match(rb'startxref[' + _B + rb']+(\d+)', data[at:at + 40]).group(1))
        seen = set()
        while isinstance(pos, int) and pos not in seen and 0 <= pos < len(data):
            seen.add(pos)
            trailer = self._xref_at(pos)
            for k, v in trailer.items():
                self.trailer.setdefault(k, v)
            if isinstance(trailer.get('XRefStm'), int):
                self._xref_at(trailer['XRefStm'])
            pos = trailer.get('Prev')

    def _xref_at(self, pos):
        data = self.data
        m = re.compile(rb'[' + _B + rb']*xref').match(data, pos)
        if m:
            p = m.end()
            while True:
                h = _XSUB.match(data, p)
                if not h:
                    break
                start, count = int(h.group(1)), int(h.group(2))
                p = h.end()
                for i in range(count):
                    e = _XENT.match(data, p)
                    if not e:
                        break
                    if e.group(3) == b'n' and int(e.group(1)) > 0:
                        self.xref.setdefault(start + i, ('o', int(e.group(1))))
                    p = e.end()
            t = data.find(b'trailer', p)
            return _obj(data, t + 7)[0] if t >= 0 else {}
        got = self._indirect(pos)
        st = got[2] if got else None
        if not isinstance(st, Stream) or st.get('Type') != 'XRef':
            raise ValueError('xref')
        w = [int(self.r(x)) for x in self.r(st.get('W'))]
        index = self.r(st.get('Index')) or [0, self.r(st.get('Size'))]
        raw, rowlen, p = st.data(), sum(w), 0
        for k in range(0, len(index) - 1, 2):
            start, count = int(self.r(index[k])), int(self.r(index[k + 1]))
            for i in range(count):
                row = raw[p:p + rowlen]
                p += rowlen
                if len(row) < rowlen:
                    break
                f, q = [], 0
                for n in w:
                    f.append(int.from_bytes(row[q:q + n], 'big'))
                    q += n
                kind = f[0] if w[0] else 1
                if kind == 1:
                    self.xref.setdefault(start + i, ('o', f[1]))
                elif kind == 2:
                    self.xref.setdefault(start + i, ('c', f[1], f[2]))
        return st.d

    def _rebuild(self):
        """Table abimee : on retrouve les objets en parcourant le fichier (la derniere version l'emporte)."""
        for m in re.finditer(rb'trailer', self.data):
            try:
                t = _obj(self.data, m.end())[0]
                if isinstance(t, dict):
                    self.trailer.update(t)
            except Exception:
                pass
        if not isinstance(self.r(self.trailer.get('Root')), dict):
            for num in sorted(self.scan()):
                o = self.get(num)
                if isinstance(o, dict) and o.get('Type') == 'Catalog':
                    self.trailer['Root'] = Ref(num, 0)
                    break

    def scan(self):
        if self._scan is None:
            self._scan = {}
            for m in re.finditer(rb'(?<![0-9])(\d{1,10})[' + _B + rb']+(\d{1,5})[' + _B + rb']+obj\b', self.data):
                self._scan[int(m.group(1))] = m.start()
        return self._scan

    def _indirect(self, pos):
        """(numero, generation, objet) de l'objet ecrit a pos, flux compris."""
        m = _OBJHDR.match(self.data, pos)
        if not m:
            return None
        obj, p = _obj(self.data, m.end())
        if isinstance(obj, dict):
            s = _STREAM.match(self.data, p)
            if s:
                start = s.end()
                n = self.r(obj.get('Length')) if not isinstance(obj.get('Length'), Ref) or obj['Length'].num != int(m.group(1)) else None
                tail = self.data[start + n:start + n + 40] if isinstance(n, int) and n >= 0 else b''
                if b'endstream' in tail:
                    raw = self.data[start:start + n]
                else:  # longueur fausse : jusqu'a endstream
                    e = self.data.find(b'endstream', start)
                    raw = self.data[start:e if e >= 0 else len(self.data)]
                    raw = raw[:-2] if raw.endswith(b'\r\n') else raw[:-1] if raw.endswith((b'\n', b'\r')) else raw
                obj = Stream(obj, raw, self)
        return int(m.group(1)), int(m.group(2)), obj

    def get(self, num):
        if num in self.cache:
            return self.cache[num]
        self.cache[num] = None  # garde contre les boucles
        obj = None
        try:
            where = self.xref.get(num)
            if where and where[0] == 'c':
                obj = self._in_stm(where[1], where[2], num)
            else:
                got = self._indirect(where[1]) if where else None
                if got is None or got[0] != num:
                    off = self.scan().get(num)
                    got = self._indirect(off) if off is not None else None
                    obj = got[2] if got and got[0] == num else self._in_any_stm(num)
                else:
                    obj = got[2]
        except Exception:
            obj = None
        self.cache[num] = obj
        return obj

    def _in_stm(self, stm_num, idx, num):
        objs = self.stms.get(stm_num)
        if objs is None:
            objs, stm = {}, self.get(stm_num)
            if isinstance(stm, Stream):
                raw, first = stm.data(), int(self.r(stm.get('First')) or 0)
                ints = [int(x) for x in re.findall(rb'\d+', raw[:first])]
                for k in range(0, min(len(ints) - 1, 2 * int(self.r(stm.get('N')) or 0)), 2):
                    try:
                        objs[ints[k]] = _obj(raw, first + ints[k + 1])[0]
                    except Exception:
                        pass
            self.stms[stm_num] = objs
        return objs.get(num)

    def _in_any_stm(self, num):
        """Objet absent du fichier a plat : on le cherche dans les flux d'objets (fichier sans table xref valable)."""
        for n in sorted(self.scan()):
            if n in self.stms:
                if num in self.stms[n]:
                    return self.stms[n][num]
                continue
            o = self.cache.get(n) if n in self.cache else self.get(n)
            if isinstance(o, Stream) and o.get('Type') == 'ObjStm':
                found = self._in_stm(n, 0, num)
                if found is not None:
                    return found
        return None

    def r(self, x, depth=0):
        while isinstance(x, Ref) and depth < 20:
            x, depth = self.get(x.num), depth + 1
        return x

    def pages(self):
        out, seen = [], set()

        def walk(node, inherited, depth):
            node = self.r(node)
            if isinstance(node, Stream) or not isinstance(node, dict) or depth > 60 or id(node) in seen:
                return
            seen.add(id(node))
            inh = dict(inherited)
            for k in ('Resources', 'MediaBox', 'Rotate'):
                if k in node:
                    inh[k] = node[k]
            kids = self.r(node.get('Kids'))
            if node.get('Type') == 'Pages' or (isinstance(kids, list) and 'Contents' not in node):
                for k in kids if isinstance(kids, list) else []:
                    walk(k, inh, depth + 1)
            else:
                out.append({**inh, **node})

        root = self.r(self.trailer.get('Root'))
        if isinstance(root, dict):
            walk(root.get('Pages'), {}, 0)
        if not out:  # arbre des pages abime : les objets /Page dans l'ordre du fichier
            for num, _ in sorted(self.scan().items(), key=lambda kv: kv[1]):
                o = self.get(num)
                if isinstance(o, dict) and o.get('Type') == 'Page':
                    out.append(o)
        return out

    def contents(self, page):
        c = self.r(page.get('Contents'))
        parts = c if isinstance(c, list) else [c]
        return b'\n'.join(s.data() for s in (self.r(p) for p in parts) if isinstance(s, Stream))

    def font(self, fonts, name):
        ref = fonts.get(name) if isinstance(fonts, dict) else None
        key = ref.num if isinstance(ref, Ref) else id(ref)
        if key not in self.fonts:
            fd = self.r(ref)
            try:
                self.fonts[key] = _Font(self, fd if isinstance(fd, dict) else {})
            except Exception:
                self.fonts[key] = _Font(self, {})  # police illisible : texte approximatif plutot que rien
        return self.fonts[key]


# ---------- polices : codes -> caracteres ----------

def _glyph_names():
    names = {}
    ascii_names = ('space exclam quotedbl numbersign dollar percent ampersand quotesingle parenleft parenright asterisk plus '
                   'comma hyphen period slash zero one two three four five six seven eight nine colon semicolon less equal '
                   'greater question at').split()
    for i, n in enumerate(ascii_names):
        names[n] = chr(32 + i)
    for i, n in enumerate('bracketleft backslash bracketright asciicircum underscore grave'.split()):
        names[n] = chr(91 + i)
    for i, n in enumerate('braceleft bar braceright asciitilde'.split()):
        names[n] = chr(123 + i)
    accents = {'ACUTE': 'acute', 'GRAVE': 'grave', 'CIRCUMFLEX': 'circumflex', 'DIAERESIS': 'dieresis', 'TILDE': 'tilde',
               'CEDILLA': 'cedilla', 'RING ABOVE': 'ring', 'CARON': 'caron', 'MACRON': 'macron', 'BREVE': 'breve',
               'OGONEK': 'ogonek', 'DOT ABOVE': 'dotaccent', 'DOUBLE ACUTE': 'hungarumlaut', 'STROKE': 'slash'}
    for cp in range(0xC0, 0x250):
        m = re.match(r'LATIN (SMALL|CAPITAL) LETTER (\w) WITH (.+)$', unicodedata.name(chr(cp), ''))
        if m and m.group(3) in accents:
            names.setdefault((m.group(2).lower() if m.group(1) == 'SMALL' else m.group(2)) + accents[m.group(3)], chr(cp))
    names.update({
        'quoteright': '’', 'quoteleft': '‘', 'quotedblleft': '“', 'quotedblright': '”', 'quotesinglbase': '‚',
        'quotedblbase': '„', 'guillemotleft': '«', 'guillemotright': '»', 'guilsinglleft': '‹', 'guilsinglright': '›',
        'endash': '–', 'emdash': '—', 'bullet': '•', 'ellipsis': '…', 'dagger': '†', 'daggerdbl': '‡', 'periodcentered': '·',
        'paragraph': '¶', 'section': '§', 'copyright': '©', 'registered': '®', 'trademark': '™', 'degree': '°',
        'plusminus': '±', 'multiply': '×', 'divide': '÷', 'cent': '¢', 'sterling': '£', 'yen': '¥', 'Euro': '€', 'euro': '€',
        'currency': '¤', 'brokenbar': '¦', 'dieresis': '¨', 'acute': '´', 'cedilla': '¸', 'macron': '¯', 'ordfeminine': 'ª',
        'ordmasculine': 'º', 'exclamdown': '¡', 'questiondown': '¿', 'logicalnot': '¬', 'mu': 'µ', 'onesuperior': '¹',
        'twosuperior': '²', 'threesuperior': '³', 'onequarter': '¼', 'onehalf': '½', 'threequarters': '¾', 'fi': 'fi',
        'fl': 'fl', 'ff': 'ff', 'ffi': 'ffi', 'ffl': 'ffl', 'AE': 'Æ', 'ae': 'æ', 'OE': 'Œ', 'oe': 'œ', 'germandbls': 'ß',
        'Eth': 'Ð', 'eth': 'ð', 'Thorn': 'Þ', 'thorn': 'þ', 'dotlessi': 'ı', 'circumflex': 'ˆ', 'tilde': '˜',
        'perthousand': '‰', 'florin': 'ƒ', 'fraction': '⁄', 'minus': '−', 'nbspace': ' ', 'nonbreakingspace': ' ',
        'sfthyphen': '\xad', 'softhyphen': '\xad', 'hyphen': '-', 'Omega': 'Ω', 'dcroat': 'đ', 'Dcroat': 'Đ',
        'quotereversed': '‛', 'minute': '′', 'second': '″', 'numero': '№', 'arrowright': '→', 'checkmark': '✓'})
    return names


GLYPHS = _glyph_names()


def _glyph(name):
    """Nom de glyphe -> caracteres (eacute, uni00E9, u1F600, f_i, a.sc...)."""
    if name in GLYPHS:
        return GLYPHS[name]
    base = name.split('.')[0]
    if base in GLYPHS:
        return GLYPHS[base]
    if '_' in base:
        return ''.join(_glyph(p) for p in base.split('_'))
    m = re.fullmatch(r'uni((?:[0-9A-Fa-f]{4})+)', base)
    if m:
        return ''.join(chr(int(m.group(1)[i:i + 4], 16)) for i in range(0, len(m.group(1)), 4))
    m = re.fullmatch(r'u([0-9A-Fa-f]{4,6})', base)
    if m and int(m.group(1), 16) < 0x110000:
        return chr(int(m.group(1), 16))
    if len(base) == 1:
        return base
    return ''


def _table(codec):
    t = list(bytes(range(256)).decode(codec, 'replace'))
    return ['' if i < 32 or c == '�' else c for i, c in enumerate(t)]


WINANSI = _table('cp1252')
WINANSI[0xAD] = '-'
MACROMAN = _table('mac_roman')
STANDARD = [chr(i) if 32 <= i < 127 else '' for i in range(256)]
STANDARD[0x27], STANDARD[0x60] = '’', '‘'
for _c, _u in zip(range(0xA1, 0x100), '¡¢£⁄¥ƒ§¤\'“«‹›ﬁﬂ\0–†‡·\0¶•‚„”»…‰\0¿\0`´ˆ˜¯˘˙¨\0˚¸\0˝˛ˇ—' + '\0' * 16 + 'Æ\0ª\0\0\0\0ŁØŒº'
                  + '\0' * 5 + 'æ\0\0\0ı\0\0łøœß'):
    STANDARD[_c] = '' if _u == '\0' else _u
ENCODINGS = {'WinAnsiEncoding': WINANSI, 'MacRomanEncoding': MACROMAN, 'StandardEncoding': STANDARD,
             'PDFDocEncoding': WINANSI}

# largeurs (1/1000 em) des polices standard sans /Widths, caracteres 32 a 126
_HELV = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278] + [556] * 10 + [
    278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778,
    722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222,
    222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]
_TIMES = [250, 333, 408, 500, 500, 833, 778, 180, 333, 333, 500, 564, 250, 333, 250, 278] + [500] * 10 + [
    278, 278, 564, 564, 564, 444, 921, 722, 667, 667, 722, 611, 556, 722, 722, 333, 389, 722, 611, 889, 722, 722, 556, 722,
    667, 556, 611, 722, 722, 944, 722, 722, 611, 333, 278, 333, 469, 500, 333, 444, 500, 444, 500, 444, 333, 500, 500, 278,
    278, 500, 278, 778, 500, 500, 500, 500, 333, 389, 278, 500, 500, 722, 500, 500, 444, 480, 200, 480, 541]
_LIG = {'ﬀ': 'ff', 'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬃ': 'ffi', 'ﬄ': 'ffl', 'ﬅ': 'st', 'ﬆ': 'st',
        ' ': ' ', '\t': ' ', ' ': ' ', ' ': ' ', ' ': ' ', ' ': ' ', ' ': ' '}


def _u16(b):
    if len(b) == 1:
        return chr(b[0])
    return (b + b'\x00' if len(b) % 2 else b).decode('utf-16-be', 'replace')


def _cmap(data):
    """CMap (ToUnicode ou encodage) -> (code -> texte, plages de codes [(octets, bas, haut)], code -> CID)."""
    umap, ranges, cids = {}, [], {}
    for body in re.findall(rb'begincodespacerange(.*?)endcodespacerange', data, re.S):
        h = [_hex(x) for x in re.findall(rb'<([0-9A-Fa-f\s]*)>', body)]
        ranges += [(len(h[i]), int.from_bytes(h[i], 'big'), int.from_bytes(h[i + 1], 'big')) for i in range(0, len(h) - 1, 2)]
    for body in re.findall(rb'beginbfchar(.*?)endbfchar', data, re.S):
        for src, dst in re.findall(rb'<([0-9A-Fa-f\s]*)>\s*<([0-9A-Fa-f\s]*)>', body):
            umap[int.from_bytes(_hex(src), 'big')] = _u16(_hex(dst))
    for body in re.findall(rb'beginbfrange(.*?)endbfrange', data, re.S):
        items = ['[' if a else ']' if b else _hex(h) for h, a, b in re.findall(rb'<([0-9A-Fa-f\s]*)>|(\[)|(\])', body)]
        i = 0
        while i + 2 < len(items):
            lo, hi, dst = items[i], items[i + 1], items[i + 2]
            if not isinstance(lo, bytes) or not isinstance(hi, bytes):
                i += 1
                continue
            a, b = int.from_bytes(lo, 'big'), int.from_bytes(hi, 'big')
            if dst == '[':
                j, k = i + 3, 0
                while j < len(items) and items[j] != ']':
                    if isinstance(items[j], bytes):
                        umap[a + k] = _u16(items[j])
                        k += 1
                    j += 1
                i = j + 1
            elif isinstance(dst, bytes):
                base, n = int.from_bytes(dst, 'big'), max(1, len(dst))
                for k in range(min(b - a, 65535) + 1):
                    v = base + k
                    umap[a + k] = _u16(v.to_bytes(n, 'big')) if v < 1 << (8 * n) else ''
                i += 3
            else:
                i += 1
    for body in re.findall(rb'begincidchar(.*?)endcidchar', data, re.S):
        for src, cid in re.findall(rb'<([0-9A-Fa-f\s]*)>\s*(\d+)', body):
            cids[int.from_bytes(_hex(src), 'big')] = int(cid)
    for body in re.findall(rb'begincidrange(.*?)endcidrange', data, re.S):
        for lo, hi, cid in re.findall(rb'<([0-9A-Fa-f\s]*)>\s*<([0-9A-Fa-f\s]*)>\s*(\d+)', body):
            a, b = int.from_bytes(_hex(lo), 'big'), int.from_bytes(_hex(hi), 'big')
            for k in range(min(b - a, 65535) + 1):
                cids[a + k] = int(cid) + k
    return umap, ranges, cids


def _tt_cmap(font):
    """Glyphe -> caractere, d'apres la table cmap d'une police TrueType incorporee (polices sans ToUnicode)."""
    try:
        tables = {}
        for i in range(struct.unpack_from('>H', font, 4)[0]):
            tag, _, off, _ = struct.unpack_from('>4sIII', font, 12 + 16 * i)
            tables[tag] = off
        base = tables[b'cmap']
        subs = {}
        for i in range(struct.unpack_from('>H', font, base + 2)[0]):
            pid, eid, off = struct.unpack_from('>HHI', font, base + 4 + 8 * i)
            subs[(pid, eid)] = base + off
        key = next((k for k in ((3, 10), (3, 1), (0, 4), (0, 3), (0, 1), (0, 0), (3, 0), (1, 0)) if k in subs), None)
        if key is None:
            return {}
        off, codes = subs[key], {}
        fmt = struct.unpack_from('>H', font, off)[0]
        if fmt == 4:
            seg2 = struct.unpack_from('>H', font, off + 6)[0]
            seg = seg2 // 2
            ends = struct.unpack_from(f'>{seg}H', font, off + 14)
            starts = struct.unpack_from(f'>{seg}H', font, off + 16 + seg2)
            deltas = struct.unpack_from(f'>{seg}h', font, off + 16 + 2 * seg2)
            ro = off + 16 + 3 * seg2
            offs = struct.unpack_from(f'>{seg}H', font, ro)
            for i in range(seg):
                for c in range(starts[i], min(ends[i], 0xFFFE) + 1):
                    if offs[i]:
                        g = struct.unpack_from('>H', font, ro + 2 * i + offs[i] + 2 * (c - starts[i]))[0]
                        g = (g + deltas[i]) & 0xFFFF if g else 0
                    else:
                        g = (c + deltas[i]) & 0xFFFF
                    if g:
                        codes[c] = g
        elif fmt == 12:
            for i in range(struct.unpack_from('>I', font, off + 12)[0]):
                s, e, g = struct.unpack_from('>III', font, off + 16 + 12 * i)
                for c in range(s, min(e, s + 0xFFFF) + 1):
                    codes[c] = g + c - s
        elif fmt == 6:
            first, cnt = struct.unpack_from('>HH', font, off + 6)
            for i, g in enumerate(struct.unpack_from(f'>{cnt}H', font, off + 10)):
                codes[first + i] = g
        elif fmt == 0:
            for c, g in enumerate(font[off + 6:off + 262]):
                codes[c] = g
        out = {}
        for c, g in sorted(codes.items()):
            if key == (3, 0) and 0xF000 <= c <= 0xF0FF:
                c -= 0xF000
            ch = bytes([c]).decode('mac_roman') if key == (1, 0) and c < 256 else chr(c) if c < 0x110000 else ''
            out.setdefault(g, ch)
        return out
    except Exception:
        return {}


class _Font:
    def __init__(self, doc, fd):
        self.doc, self.fd = doc, fd
        sub, r = fd.get('Subtype'), doc.r
        self.base = re.sub(r'^[A-Z]{6}\+', '', str(r(fd.get('BaseFont')) or ''))
        self.cid, self.scale, self.hscale = sub == 'Type0', 0.001, 1.0
        self.umap, self.ranges, self.cids, self._gids, self.unicode_codes = {}, [], {}, None, False
        tu = r(fd.get('ToUnicode'))
        if isinstance(tu, Stream):
            self.umap = _cmap(tu.data())[0]
        self.widths, self.dw = {}, 500
        if self.cid:
            desc = r(fd.get('DescendantFonts'))
            desc = r(desc[0]) if isinstance(desc, list) and desc else {}
            self.desc = desc if isinstance(desc, dict) else {}
            enc = r(fd.get('Encoding'))
            if isinstance(enc, Stream):
                _, self.ranges, self.cids = _cmap(enc.data())
            elif enc and re.search(r'UCS2|UTF16', str(enc)):
                self.unicode_codes = True  # codes = caracteres (polices asiatiques)
            if not self.ranges:
                self.ranges = [(2, 0, 0xFFFF)]
            self.dw = r(self.desc.get('DW'))
            self.dw = self.dw if isinstance(self.dw, (int, float)) else 1000
            w = r(self.desc.get('W')) or []
            i = 0
            while i + 1 < len(w):
                a, b = r(w[i]), r(w[i + 1])
                if isinstance(b, list):
                    for k, v in enumerate(b):
                        v = r(v)
                        if isinstance(a, int) and isinstance(v, (int, float)):
                            self.widths[a + k] = v
                    i += 2
                else:
                    c = r(w[i + 2]) if i + 2 < len(w) else None
                    if isinstance(a, int) and isinstance(b, int) and isinstance(c, (int, float)):
                        for cid in range(a, min(b, a + 65535) + 1):
                            self.widths[cid] = c
                    i += 3
            return
        desc = r(fd.get('FontDescriptor'))
        desc = desc if isinstance(desc, dict) else {}
        # encodage de base, puis /Differences
        enc = r(fd.get('Encoding'))
        base_name = enc if isinstance(enc, Name) else r(enc.get('BaseEncoding')) if isinstance(enc, dict) else None
        if base_name in ENCODINGS:
            self.enc = list(ENCODINGS[base_name])
        elif re.search(r'Symbol|Dingbats|Wingdings|Webdings', self.base) and not self.umap:
            self.enc = [''] * 256  # puces et symboles : pas du texte
        else:
            self.enc = self._builtin(desc) or list(STANDARD if sub in ('Type1', 'MMType1') else WINANSI)
        if isinstance(enc, dict):
            code = 0
            for d in r(enc.get('Differences')) or []:
                d = r(d)
                if isinstance(d, int):
                    code = d
                elif isinstance(d, Name):
                    if 0 <= code < 256:
                        self.enc[code] = _glyph(str(d))
                    code += 1
        if sub == 'Type3':
            fm = r(fd.get('FontMatrix'))
            if isinstance(fm, list) and len(fm) >= 4 and all(isinstance(x, (int, float)) for x in fm[:4]):
                self.scale = abs(fm[0]) or 0.001
                self.hscale = abs(fm[3]) / 0.001 if fm[3] else 1.0
        widths, first = r(fd.get('Widths')), r(fd.get('FirstChar'))
        missing = r(desc.get('MissingWidth'))
        if isinstance(widths, list) and isinstance(first, int):
            for k, v in enumerate(widths):
                v = r(v)
                if isinstance(v, (int, float)):
                    self.widths[first + k] = v
            self.dw = missing if isinstance(missing, (int, float)) and missing else 500
        else:  # police standard sans largeurs : tables approchees
            table = None if 'Courier' in self.base else _TIMES if 'Times' in self.base else _HELV
            for c in range(256):
                ch = unicodedata.normalize('NFKD', self.enc[c] or ' ')[:1]
                self.widths[c] = 600 if table is None else table[ord(ch) - 32] if 32 <= ord(ch) < 127 else 500
        if not self.widths.get(32):
            self.widths[32] = self.widths.get(32) or 250

    def _builtin(self, desc):
        """Encodage interne d'une police Type1 incorporee (« dup 65 /A put »)."""
        ff = self.doc.r(desc.get('FontFile'))
        if not isinstance(ff, Stream):
            return None
        head = ff.data()[:int(self.doc.r(ff.get('Length1')) or 40000)]
        pairs = re.findall(rb'dup\s+(\d+)\s*/(\S+?)\s+put', head)
        if not pairs:
            return None
        enc = [''] * 256
        for code, name in pairs:
            if int(code) < 256:
                enc[int(code)] = _glyph(name.decode('latin-1'))
        return enc

    def _gid_map(self):
        """Glyphe -> caractere depuis la police incorporee (Type0 sans ToUnicode)."""
        if self._gids is None:
            self._gids, desc = {}, self.doc.r(self.desc.get('FontDescriptor'))
            ff = self.doc.r(desc.get('FontFile2')) if isinstance(desc, dict) else None
            if isinstance(ff, Stream):
                self._gids = _tt_cmap(ff.data())
                c2g = self.doc.r(self.desc.get('CIDToGIDMap'))
                if isinstance(c2g, Stream):
                    raw = c2g.data()
                    g2u = self._gids
                    self._gids = {cid: g2u.get(int.from_bytes(raw[2 * cid:2 * cid + 2], 'big'), '')
                                  for cid in range(len(raw) // 2)}
        return self._gids

    def decode(self, s):
        """Octets d'une chaine -> [(texte, largeur en 1/1000 em, espace simple ?)]."""
        out = []
        if not self.cid:
            for c in s:
                u = self.umap.get(c)
                out.append((u if u else self.enc[c], self.widths.get(c, self.dw), c == 32))
            return out
        i, n = 0, len(s)
        while i < n:
            nb = next((k for k, lo, hi in self.ranges if i + k <= n and lo <= int.from_bytes(s[i:i + k], 'big') <= hi),
                      self.ranges[0][0])
            code = int.from_bytes(s[i:i + nb], 'big')
            i += nb
            cid = self.cids.get(code, code)
            u = self.umap.get(code)
            if not u:
                u = chr(code) if self.unicode_codes and code < 0x110000 else self._gid_map().get(cid, '')
            out.append((u, self.widths.get(cid, self.dw), nb == 1 and code == 32))
        return out


# ---------- lecture du contenu des pages ----------

_ID = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
_EI = re.compile(rb'[' + _B + rb']EI(?=[' + _B + rb']|$)')


def _mul(m, n):
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D, e * A + f * C + E, e * B + f * D + F)


def _f(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0


def _show(s, ts, tm, ctm, out, info):
    """Affiche une chaine : morceau (x0, y, x1, hauteur, texte) dans le sens de lecture ; renvoie la matrice avancee."""
    font = ts['font'] or info['dummy']
    size, th, adv, parts = ts['size'], ts['th'], 0.0, []
    for u, w, sp in font.decode(s):
        parts.append(u)
        if not u:
            info['sans'] += 1
        adv += (w * font.scale * size + ts['tc'] + (ts['tw'] if sp else 0.0)) * th
    m, rise = _mul(tm, ctm), ts['rise']
    x0, y0 = rise * m[2] + m[4], rise * m[3] + m[5]
    x1, y1 = adv * m[0] + x0, adv * m[1] + y0
    h = max(0.5, abs(size) * math.hypot(m[2], m[3]) * font.hscale)
    text = ''.join(parts)
    if text:
        if abs(m[1]) > abs(m[0]):  # texte tourne de 90 degres : on se place dans son sens de lecture
            x0, y0, x1 = (y0, -x0, y1) if m[1] > 0 else (-y0, x0, -y1)
        elif m[0] < 0:
            x0, y0, x1 = -x0, -y0, -x1
        out.append((x0, y0, x1, h, text))
    return (tm[0], tm[1], tm[2], tm[3], adv * tm[0] + tm[4], adv * tm[1] + tm[5])


def _run(doc, data, res, ctm, out, info, depth):
    """Interprete un flux de contenu (texte, formes incorporees, images comptees)."""
    fonts, xobjs = doc.r(res.get('Font')), doc.r(res.get('XObject'))
    ts = {'font': None, 'size': 0.0, 'tc': 0.0, 'tw': 0.0, 'th': 1.0, 'tl': 0.0, 'rise': 0.0}
    stack, tm, tlm, ops, pos = [], _ID, _ID, [], 0
    while True:
        try:
            obj, pos = _obj(data, pos, False)
        except _Fin:
            break
        if type(obj) is not Kw:
            ops.append(obj)
            continue
        op = obj
        try:
            if op == 'BT':
                tm = tlm = _ID
            elif op in ('Tj', 'TJ', "'", '"') and ops:
                if op != 'Tj' and op != 'TJ':
                    if op == '"' and len(ops) >= 3:
                        ts['tw'], ts['tc'] = _f(ops[-3]), _f(ops[-2])
                    tlm = tm = _mul((1, 0, 0, 1, 0, -ts['tl']), tlm)
                for it in (ops[-1] if isinstance(ops[-1], list) else [ops[-1]]):
                    if isinstance(it, bytes):
                        tm = _show(it, ts, tm, ctm, out, info)
                    elif isinstance(it, (int, float)):
                        tm = _mul((1, 0, 0, 1, -_f(it) / 1000 * ts['size'] * ts['th'], 0), tm)
            elif op in ('Td', 'TD') and len(ops) >= 2:
                if op == 'TD':
                    ts['tl'] = -_f(ops[-1])
                tlm = tm = _mul((1, 0, 0, 1, _f(ops[-2]), _f(ops[-1])), tlm)
            elif op == 'Tm' and len(ops) >= 6:
                tlm = tm = tuple(_f(v) for v in ops[-6:])
            elif op == 'T*':
                tlm = tm = _mul((1, 0, 0, 1, 0, -ts['tl']), tlm)
            elif op == 'Tf' and len(ops) >= 2:
                ts['font'], ts['size'] = doc.font(fonts, ops[-2]), _f(ops[-1])
            elif op == 'Tc' and ops:
                ts['tc'] = _f(ops[-1])
            elif op == 'Tw' and ops:
                ts['tw'] = _f(ops[-1])
            elif op == 'Tz' and ops:
                ts['th'] = _f(ops[-1]) / 100
            elif op == 'TL' and ops:
                ts['tl'] = _f(ops[-1])
            elif op == 'Ts' and ops:
                ts['rise'] = _f(ops[-1])
            elif op == 'q':
                stack.append((ctm, dict(ts)))
            elif op == 'Q':
                if stack:
                    ctm, ts = stack.pop()
            elif op == 'cm' and len(ops) >= 6:
                ctm = _mul(tuple(_f(v) for v in ops[-6:]), ctm)
            elif op == 'Do' and ops and isinstance(xobjs, dict):
                x = doc.r(xobjs.get(ops[-1]))
                if isinstance(x, Stream) and x.get('Subtype') == 'Form' and depth < 10:
                    mx = doc.r(x.get('Matrix'))
                    mx = tuple(_f(v) for v in mx) if isinstance(mx, list) and len(mx) == 6 else _ID
                    sub = doc.r(x.get('Resources'))
                    _run(doc, x.data(), sub if isinstance(sub, dict) else res, _mul(mx, ctm), out, info, depth + 1)
                elif isinstance(x, Stream) and x.get('Subtype') == 'Image':
                    info['images'] += 1
            elif op == 'BI':  # image en ligne : on saute ses donnees
                while True:
                    o, pos = _obj(data, pos, False)
                    if type(o) is Kw and o == 'ID':
                        break
                m = _EI.search(data, pos)
                pos = m.end() if m else len(data)
                info['images'] += 1
        except _Fin:
            break
        except (TypeError, ValueError, IndexError, KeyError, ZeroDivisionError, OverflowError, AttributeError):
            pass
        ops = []


def _clean(s):
    s = ''.join(_LIG.get(c, c) for c in s)
    s = ''.join(c for c in s if c == '\xad' or unicodedata.category(c)[0] != 'C')
    return unicodedata.normalize('NFC', re.sub(r' {2,}', ' ', s))


def _assemble(chunks):
    """Morceaux dans l'ordre du flux -> lignes (meme ligne de base ; espace quand l'ecart depasse 0,15 em)."""
    lines, cur, last = [], None, None
    for x0, y, x1, h, text in chunks:
        blank = not text.strip()
        if cur is not None:
            hh = max(h, cur['h'])
            if last and text == last[2] and abs(x0 - last[0]) < 0.3 * hh and abs(y - last[1]) < 0.3 * hh:
                continue  # meme texte redessine (faux gras, ombre)
            if abs(y - cur['y']) <= 0.45 * hh and x0 >= cur['x1'] - 1.2 * hh:
                if not cur['texte'].strip():
                    cur['x'] = x0
                elif x0 - cur['x1'] > 0.15 * hh and not cur['texte'].endswith(' ') and not text.startswith(' '):
                    cur['texte'] += ' '
                cur['texte'] += text
                if not blank:
                    cur['x1'], cur['h'] = max(cur['x1'], x1), hh
                last = (x0, y, text)
                continue
        if blank:
            continue
        cur = {'x': x0, 'x1': x1, 'y': y, 'h': h, 'texte': text}
        lines.append(cur)
        last = (x0, y, text)
    out = []
    for ln in lines:
        ln['texte'] = _clean(ln['texte']).strip()
        if ln['texte'].replace('\xad', ''):
            out.append(ln)
    return out


class Pages(list):
    """Pages de lignes ; .compose = document mis en page (InDesign, TeX...) ou les coupures de mots sont probables."""
    compose = False


def lignes(path):
    """PDF -> Pages : pour chaque page, lignes {'x','x1','y','h','texte'} dans l'ordre du document."""
    data = Path(path).read_bytes()
    if b'%PDF' not in data[:1024]:
        raise ErreurPdf("ce fichier n'est pas un vrai PDF (il est peut-être abîmé ou mal renommé).")
    try:
        doc = _Doc(data)
        encrypted = doc.trailer.get('Encrypt') is not None
        pages = doc.pages()
    except Exception as e:
        raise ErreurPdf(f"PDF illisible (structure non reconnue : {e.__class__.__name__}).") from e
    if encrypted:
        raise ErreurPdf("ce PDF est protégé (chiffré). Ouvre-le et enregistre-le sans protection, ou en Word (.docx) "
                        "ou en texte (.txt).")
    if not pages:
        raise ErreurPdf('PDF illisible : aucune page trouvée.')
    out, info = Pages(), {'images': 0, 'sans': 0, 'dummy': _Font(doc, {})}
    for page in pages:
        chunks, res = [], doc.r(page.get('Resources'))
        try:
            _run(doc, doc.contents(page), res if isinstance(res, dict) else {}, _ID, chunks, info, 0)
        except RecursionError:
            pass
        out.append(_assemble(chunks))
    meta = doc.r(doc.trailer.get('Info'))
    made = ' '.join(str(meta.get(k)) for k in ('Creator', 'Producer') if isinstance(meta, dict) and isinstance(meta.get(k), bytes))
    out.compose = bool(re.search(r'InDesign|TeX|Quark|Scribus|Affinity|Publisher', made))
    text = ''.join(ln['texte'] for p in out for ln in p)
    letters = sum(c.isalpha() for c in text)
    if letters < 20:
        if info['sans'] > 20:
            raise ErreurPdf("le texte de ce PDF est écrit avec une police que l'outil ne sait pas lire. "
                            "Enregistre le script en Word (.docx) ou en texte (.txt).")
        if info['images']:
            raise ErreurPdf("ce PDF est une image (document numérisé ou photo) : il n'y a pas de texte à lire. "
                            "Demande le script en Word (.docx) ou en texte (.txt).")
        raise ErreurPdf("ce PDF ne contient pas de texte lisible. Enregistre le script en Word (.docx) ou en texte (.txt).")
    if sum(1 for c in text if c == '�' or unicodedata.category(c) == 'Co') > 0.3 * len(text):
        raise ErreurPdf("le texte de ce PDF est illisible (caractères inconnus). Enregistre le script en Word (.docx) "
                        "ou en texte (.txt).")
    return out


# ---------- lignes -> paragraphes ----------

PAGE_NUM = re.compile(r'^(?:page\s*)?[-–(]?\s*\d{1,4}\s*[-–)]?\.?(?:\s*(?:/|sur|de|of)\s*\d{1,4})?$', re.I)
NEW_PARA = re.compile(r'^(?:[•●○◦▪■□☐✓✔➢►\-–—*·]\s|\d{1,3}[.)]\s|(?:script|vid[ée]o)\s*\d+\s*:?\s*$)|^[^:]{1,40}:$', re.I)
# apres un trait d'union en fin de ligne, ces mots gardent le trait (« peut-être », « dit-il »)
_CLITIC = {'etre', 'il', 'ils', 'elle', 'elles', 'on', 'je', 'tu', 'nous', 'vous', 'moi', 'toi', 'lui', 'leur', 'le', 'la',
           'les', 'y', 'en', 'ci', 'la', 'meme', 'memes', 'ce', 'dessus', 'dessous', 'dedans', 'dehors', 'uns', 'unes', 't'}


def _plain(w):
    return ''.join(c for c in unicodedata.normalize('NFKD', w.lower()) if not unicodedata.combining(c))


def _pitch(lines):
    """Interligne habituel de la page."""
    dys = sorted(a['y'] - b['y'] for a, b in zip(lines, lines[1:])
                 if 0 < a['y'] - b['y'] < 3 * a['h'] and abs(a['h'] - b['h']) < 0.2 * a['h'])
    return dys[len(dys) // 2] if dys else None


def _full(a, b, right):
    """La ligne a va jusqu'au bout : le premier mot de b n'y tenait pas (b continue donc le paragraphe)."""
    cw = (a['x1'] - a['x']) / max(1, len(a['texte']))
    first = b['texte'].split(' ')[0]
    return a['x1'] + (len(first) + 1) * cw >= right - 0.5 * cw


def _join(text, nxt, words, compose):
    """Colle la ligne suivante : coupure de mot (trait d'union) ou simple espace."""
    if text.endswith('\xad'):
        return text[:-1] + nxt
    m = re.search(r'(\w+)-$', text)
    if m and not text.endswith('--') and re.match(r'[^\W\d_]', nxt):
        head, tail = m.group(1), re.match(r'[\w’\']*', nxt).group(0)
        whole, compound = _plain(head + tail), _plain(f'{head}-{tail}')
        if compound in words or _plain(tail) in _CLITIC or not nxt[0].islower():
            return text + nxt
        if whole in words or compose:
            return text[:-1] + nxt  # mot coupe en fin de ligne
        return text + nxt  # Word, Google Docs, Final Draft ne coupent pas les mots : vrai trait d'union
    return f'{text} {nxt}'


def paragraphes(pages):
    """Lignes -> paragraphes : une ligne qui va jusqu'a la marge continue sur la suivante (meme taille, meme retrait,
    interligne normal). Les numeros de page sont retires. Une liste de textes, sans lignes vides."""
    words = Counter()
    for p in pages:
        for ln in p:
            words.update(_plain(w) for w in re.findall(r"[^\W\d_]+(?:-[^\W\d_]+)*", ln['texte']))
    compose = getattr(pages, 'compose', False)
    out, prev = [], None  # prev : derniere ligne du paragraphe en cours, pour continuer sur la page suivante
    for p in pages:
        lines = [ln for ln in p if not PAGE_NUM.match(ln['texte'])]
        if not lines:
            continue
        right, pitch = max(ln['x1'] for ln in lines), _pitch(lines)
        for i, b in enumerate(lines):
            a = prev
            if a is not None and i == 0:
                ok = a['full'] and not re.search(r'[.!?:…»"”]$', out[-1]) and b['texte'][:1].islower()
            elif a is not None:
                dy, hh = a['y'] - b['y'], max(a['h'], b['h'])
                ok = (0 < dy <= (1.35 * pitch + 1 if pitch else 1.6 * hh) and abs(a['h'] - b['h']) <= 0.25 * hh
                      and not a['texte'].endswith(':') and not NEW_PARA.match(b['texte'])
                      and (b['x'] <= a['x'] + 0.8 * hh or (a['first'] and NEW_PARA.match(a['texte']) and b['x'] <= a['x'] + 3 * hh))
                      and _full(a, b, right))
            else:
                ok = False
            if ok:
                out[-1] = _join(out[-1], b['texte'], words, compose)
            else:
                out.append(b['texte'])
            prev = {**b, 'first': not ok}
        prev['full'] = _full(prev, {'texte': 'x' * 6}, right)
    return [re.sub(r'\xad', '', t).strip() for t in out if t.replace('\xad', '').strip()]


def lignes_brutes(pages):
    """Lignes telles qu'affichees, avec une ligne vide la ou il y a un blanc (plus d'un interligne) ou une page."""
    out = []
    for p in pages:
        lines = [ln for ln in p if not PAGE_NUM.match(ln['texte'])]
        pitch = _pitch(lines)
        for a, b in zip([None] + lines, lines):
            if a is None or not pitch or a['y'] - b['y'] > 1.5 * pitch or a['y'] - b['y'] < 0:
                out.append('')
            out.append(b['texte'].replace('\xad', ''))
    return out


def texte(path):
    """Texte d'un PDF : un paragraphe par ligne."""
    return '\n'.join(paragraphes(lignes(path)))


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        print(texte(sys.argv[1]))
    except ErreurPdf as err:
        print(f'PDF : {err}')
