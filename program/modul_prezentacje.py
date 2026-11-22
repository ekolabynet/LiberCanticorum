# Liber Canticorum – import pieśni z prezentacji (PowerPoint .pptx/.pptm/.ppt, Impress .odp)
# Copyright (C) 2026  Liber Canticorum contributors
# GPL-3.0-or-later
"""Każdy plik prezentacji = jedna pieśń, każdy slajd = jedna zwrotka (albo refren).
Powtarzający się slajd to refren. Folder z podfolderami (np. KOLĘDY, MARYJNE) = kategorie.
Bez dodatkowych pakietów: pliki .pptx i .odp to archiwa ZIP z XML. Stary format .ppt
wymaga LibreOffice (konwersja w tle do .pptx)."""

import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

EXT_PPTX = ('.pptx', '.pptm', '.ppsx', '.potx')
EXT_ODP = ('.odp', '.otp')
EXT_PPT = ('.ppt', '.pps')
EXTENSIONS = EXT_PPTX + EXT_ODP + EXT_PPT

_A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
_P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
_R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
_PR = '{http://schemas.openxmlformats.org/package/2006/relationships}'
_SKIP_PH = {'sldNum', 'dt', 'ftr', 'hdr'}

_O_DRAW = '{urn:oasis:names:tc:opendocument:xmlns:drawing:1.0}'
_O_TEXT = '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}'
_O_PRES = '{urn:oasis:names:tc:opendocument:xmlns:presentation:1.0}'


def is_presentation(path):
    n = os.path.basename(path)
    return n.lower().endswith(EXTENSIONS) and not n.startswith(('~$', '.~lock'))


# ---------------------------------------------------------------- odczyt slajdów
def _pptx_paragraph(p):
    out = []
    for el in p.iter():
        if el.tag == _A + 't':
            out.append(el.text or '')
        elif el.tag == _A + 'br':
            out.append('\n')
    return ''.join(out)


def slides_pptx(path):
    """[[wiersze slajdu]] w kolejności pokazu, bez slajdów ukrytych, stopek i numerów stron."""
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        pres = ET.fromstring(z.read('ppt/presentation.xml'))
        rels = ET.fromstring(z.read('ppt/_rels/presentation.xml.rels'))
        targets = {r.get('Id'): r.get('Target') for r in rels.iter(_PR + 'Relationship')}
        out = []
        for sid in pres.iter(_P + 'sldId'):
            t = targets.get(sid.get(_R + 'id'), '')
            t = t.lstrip('/') if t.startswith('/') else os.path.normpath(os.path.join('ppt', t)).replace('\\', '/')
            if t not in names:
                continue
            root = ET.fromstring(z.read(t))
            if root.get('show') == '0':                     # slajd ukryty
                continue
            lines = []
            for sp in root.iter():
                if sp.tag not in (_P + 'sp', _P + 'graphicFrame'):
                    continue
                ph = sp.find(f'.//{_P}ph')
                if ph is not None and ph.get('type') in _SKIP_PH:
                    continue
                block = []
                for p in sp.iter(_A + 'p'):
                    block += re.split(r'[\n\x0b\u2028]', _pptx_paragraph(p).replace('_x000B_', '\n'))
                if any(x.strip() for x in block):
                    if lines:
                        lines.append('')
                    lines += block
            out.append(lines)
        return out


def _odp_text(el):
    out = [el.text or '']
    for ch in el:
        if ch.tag == _O_TEXT + 'line-break':
            out.append('\n')
        elif ch.tag == _O_TEXT + 's':
            out.append(' ' * int(ch.get(_O_TEXT + 'c', '1')))
        elif ch.tag == _O_TEXT + 'tab':
            out.append(' ')
        else:
            out.append(_odp_text(ch))
        out.append(ch.tail or '')
    return ''.join(out)


def slides_odp(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read('content.xml'))
    out = []
    for page in root.iter(_O_DRAW + 'page'):
        lines = []
        for frame in page:
            if frame.tag == _O_PRES + 'notes':
                continue
            if frame.get(_O_PRES + 'class') in ('page-number', 'date-time', 'footer', 'header', 'notes'):
                continue
            block = []
            for el in frame.iter():
                if el.tag in (_O_TEXT + 'p', _O_TEXT + 'h'):
                    block += re.split(r'[\n\x0b\u2028]', _odp_text(el))
            if any(x.strip() for x in block):
                if lines:
                    lines.append('')
                lines += block
        out.append(lines)
    return out


def soffice():
    for name in ('soffice', 'libreoffice'):
        p = shutil.which(name)
        if p:
            return p
    for p in (r"C:\Program Files\LibreOffice\program\soffice.exe",
              r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
              "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        if os.path.exists(p):
            return p
    return None


def slides_ppt(path):
    """Stary PowerPoint (.ppt): konwersja LibreOffice → .pptx w folderze tymczasowym."""
    exe = soffice()
    if not exe:
        raise RuntimeError("Stary format .ppt wymaga LibreOffice (bezpłatny) – albo zapisz plik w PowerPoincie jako .pptx.")
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([exe, '--headless', '--norestore', f'-env:UserInstallation=file://{tmp}/profil',
                        '--convert-to', 'pptx', '--outdir', tmp, path],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120, check=False)
        out = os.path.join(tmp, os.path.splitext(os.path.basename(path))[0] + '.pptx')
        if not os.path.exists(out):
            raise RuntimeError("LibreOffice nie przekonwertował pliku .ppt.")
        return slides_pptx(out)


def read_slides(path):
    """Format rozpoznawany po zawartości, nie po rozszerzeniu (zdarza się .odp zapisany jako .pptx)."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
        if 'ppt/presentation.xml' in names:
            return slides_pptx(path)
        if 'content.xml' in names:
            return slides_odp(path)
        raise RuntimeError("To nie jest prezentacja PowerPoint ani Impress")
    with open(path, 'rb') as f:
        head = f.read(8)
    if head == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':          # stary format Office (OLE) – .ppt
        return slides_ppt(path)
    raise RuntimeError("Nieznany format prezentacji")


# ---------------------------------------------------------------- slajdy → pieśń
def _fold(t):
    t = unicodedata.normalize('NFD', t.lower().replace('ł', 'l'))
    return re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in t if not unicodedata.combining(c))).strip()


_SACRED = r"(bóg|boga|bogu|bogiem|bogiem|boże|bożego|bożej|bożemu|boży|bożym|boża|bożą|jezus\w*|jezu|chryst\w*|" \
          r"mary\w*|duch\w*|ojc\w*|ojcze|pan|pana|panu|panem|panie|pański\w*|pańsk\w*|zbawiciel\w*|stwórc\w*|" \
          r"trójc\w*|najświętsz\w*|baranek|baranka|baranku|barankiem|józef\w*|betlejem|syn|syna|synu|synem|" \
          r"królow\w*|matk\w*|panno|panny|panna|pannę|panną|dziewic\w*|ducha|alleluja|hosanna|amen)"
_RE_SACRED = re.compile(r"(?<![\w])" + _SACRED + r"(?![\w])", re.I)


def _mostly_caps(lines):
    letters = [c for l in lines for c in l if c.isalpha()]
    return len(letters) > 20 and sum(c.isupper() for c in letters) > 0.8 * len(letters)


def _uncaps(line):
    """WERSALIKI → zwykła pisownia: wielka litera na początku wiersza i zdania, nazwy Boże i Maryi."""
    t = line.lower()
    t = re.sub(r"(^\W*|[.!?]\s+)(\w)", lambda m: m.group(1) + m.group(2).upper(), t)
    return _RE_SACRED.sub(lambda m: m.group(0)[:1].upper() + m.group(0)[1:], t)


RE_NUM = re.compile(r"^\s*(\d{1,2})\s*[.)]\s*")
RE_REF = re.compile(r"^\s*(ref(ren)?|r)\s*[.:]\s*", re.I)


def title_from_filename(path):
    t = os.path.splitext(os.path.basename(path))[0]
    t = re.sub(r"\s*\[(naprawione|repaired|kopia)\]\s*", " ", t, flags=re.I)
    t = re.sub(r"\s*[-–]\s*(kopia|copy)(\s*\(\d+\))?\s*$", "", t, flags=re.I)
    t = re.sub(r"^\s*(0\d{0,2}\s*[-_.)]?|\d{1,3}\s*[-_.)])\s*(?=\D)", "", t)   # „01 Barka”, „3. Barka” (ale „1 komunia”)
    t = re.sub(r"[_]+", " ", t).strip()
    if t.isupper() and len(t) > 3:
        t = t[:1] + t[1:].lower()
        t = _RE_SACRED.sub(lambda m: m.group(0)[:1].upper() + m.group(0)[1:], t)
        t = t[:1].upper() + t[1:]
    t = re.sub(r"\.{2,}$", ".", re.sub(r"\s{2,}", " ", t)).strip(" ,;")
    t = t if re.search(r"\b(św|bł|o|ks|nr)\.$", t, re.I) else t.rstrip(".")
    return t[:1].upper() + t[1:]


def song_from_slides(slides, title, category="", source=""):
    """→ słownik pieśni jak w modul_zbior (title, refren, zwrotki_raw, uwagi, kategoria…)."""
    blocks = []
    for sl in slides:
        # znaki z czcionek symboli (np. gwiazdka Wingdings jako koniec półwersu) – usunięte
        lines = [re.sub(r"\s{2,}", " ", re.sub(r"[\uf000-\uf0ff]", " ", l).replace('\xa0', ' ').replace('\t', ' ')).strip(" ")
                 for l in sl]
        lines = [l for l in lines if l]                   # puste wiersze w slajdzie nie dzielą zwrotki
        if lines:
            blocks.append(lines)
    notes = []
    # slajd tytułowy: pierwszy, krótki i zgodny z nazwą pliku (albo sam tytuł przed tekstem)
    if len(blocks) > 1 and len(blocks[0]) <= 2 and len(" ".join(blocks[0])) <= 70:
        f0, ft = _fold(" ".join(blocks[0])), _fold(title)
        if f0 and (f0 == ft or f0 in ft or ft in f0 or len(blocks[0]) == 1 and len(blocks[1]) >= 3):
            if not title.strip():
                title = " ".join(blocks[0])
            blocks.pop(0)
    caps = _mostly_caps([l for b in blocks for l in b])
    if caps:
        blocks = [[_uncaps(l) for l in b] for b in blocks]
        notes.append("tekst był wersalikami – sprawdź wielkie litery")
    if not title.strip() and blocks:
        title = blocks[0][0]
    # refren: slajd oznaczony „Ref.” albo powtarzający się (ten sam tekst co najmniej dwa razy)
    keys = [_fold(" ".join(b)) for b in blocks]
    ref, ref_key = None, None
    for b, k in zip(blocks, keys):
        if RE_REF.match(b[0]):
            ref, ref_key = [x for x in [RE_REF.sub("", b[0])] + b[1:] if x.strip()], k
            break
    if ref is None:
        rep = [k for k in dict.fromkeys(keys) if k and keys.count(k) >= 2]
        if rep:
            ref_key = rep[0]
            ref = blocks[keys.index(ref_key)]
    verses, seen = [], set()
    for b, k in zip(blocks, keys):
        if k == ref_key or k in seen:
            continue
        seen.add(k)
        verses.append("\n".join(b))
    numbered = sum(1 for v in verses if RE_NUM.match(v))
    if numbered and numbered < len(verses):            # część zwrotek bez numeru – numery z kolejności
        verses = [RE_NUM.sub("", v) for v in verses]
        numbered = 0
    if numbered:
        verses = [RE_NUM.sub(lambda m: f"{m.group(1)}. ", v, count=1) for v in verses]
    if source:
        notes.insert(0, source)
    t = title.strip()
    if t.isupper() and len(t) > 3:
        t = title_from_filename(t + ".x")
    return {'title': t or "Bez tytułu", 'refren': "\n".join(ref or []), 'zwrotki_raw': "\n\n".join(verses),
            'uwagi': " | ".join(notes), 'kategoria': category, 'tagi': '', 'youtube': '',
            'numer': '', 'slajdy': len(slides), 'numeruj': bool(numbered),
            '_slajdy': [list(sl) for sl in slides]}


def song_from_file(path, category="", source=""):
    return song_from_slides(read_slides(path), title_from_filename(path), category, source)


def find_presentations(folder):
    """[(ścieżka, kategoria z nazwy podfolderu)] – podfolder najbliższy plikowi."""
    out = []
    for root, dirs, files in os.walk(folder):
        dirs.sort()
        rel = os.path.relpath(root, folder)
        cat = "" if rel == "." else os.path.basename(root)
        cat = re.sub(r"\s{2,}", " ", cat).strip()
        if cat.isupper() and len(cat) > 4:               # „MIŁOSIERDZIE BOŻE” → „Miłosierdzie Boże”, „NSPJ” zostaje
            cat = cat[:1] + _RE_SACRED.sub(lambda m: m.group(0)[:1].upper() + m.group(0)[1:], cat[1:].lower())
        for f in sorted(files):
            p = os.path.join(root, f)
            if is_presentation(p):
                out.append((p, cat))
    return out


# ---------------------------------------------------------------- folder spakowany ZIP
def _zip_name(info):
    """Nazwa pliku z archiwum: UTF-8, stare kodowanie Windows (cp852/cp1250) albo zapis „#U015a”."""
    n = info.filename
    if not info.flag_bits & 0x800:
        raw = n.encode('cp437', errors='replace')
        for enc in ('utf-8', 'cp852', 'cp1250'):
            try:
                n = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
    return re.sub(r'#U([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), n)


def extract_presentations(zip_path, dest):
    """Rozpakowuje z archiwum tylko prezentacje (bez plików wykonywalnych, skrótów itp.), z zachowaniem podfolderów.
    Ścieżki „..” i bezwzględne są odrzucane. Zwraca liczbę plików."""
    n = 0
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            name = _zip_name(info).replace('\\', '/')
            parts = [p for p in name.split('/') if p not in ('', '.')]
            if not parts or '..' in parts or ':' in parts[0] or not is_presentation(parts[-1]):
                continue
            if info.file_size > 200 * 1024 * 1024:
                continue
            target = os.path.join(dest, *parts)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(info) as src, open(target, 'wb') as out:
                shutil.copyfileobj(src, out)
            n += 1
    return n


def zip_has_presentations(zip_path):
    try:
        with zipfile.ZipFile(zip_path) as z:
            return any(is_presentation(_zip_name(i).split('/')[-1]) for i in z.infolist() if not i.is_dir())
    except Exception:
        return False
