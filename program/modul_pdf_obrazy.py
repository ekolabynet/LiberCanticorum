#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Liber Canticorum – śpiewnik PDF, w którym nuty są obrazkami (np. skan albo plik z calibre),
a tekstem są tylko nagłówki: nazwa mszy / cyklu (duże pismo), części (KYRIE, SANCTUS…), rubryki.

Każda część (albo cały utwór, gdy nie ma nagłówków części) staje się pieśnią:
tytuł „Msza Rycerska – Kyrie”, kategoria „Części stałe Mszy”, tagi: część i nazwa mszy (z nich
zestaw na Mszę składa „motyw” części stałych), nuty jako załącznik PDF z wyciętych obrazków.
Słowa: gdy jest program tesseract, próba odczytu (OCR) autorów i słów spod nut – jako szkic do sprawdzenia.

Licencja: GPL-3.0-or-later.
"""
import io
import os
import re
import shutil
import subprocess
import tempfile

PARTS = [("kyrie", "Kyrie", "kyrie"), ("panie zmiluj", "Kyrie", "kyrie"), ("gloria", "Gloria", "gloria"),
         ("chwala na wysokosci", "Gloria", "gloria"), ("credo", "Credo", "credo"), ("wierze", "Credo", "credo"),
         ("sanctus", "Sanctus", "sanctus"), ("swiety", "Sanctus", "sanctus"), ("agnus", "Agnus Dei", "agnus dei"),
         ("baranku", "Agnus Dei", "agnus dei"), ("alleluja", "Alleluja", "alleluja"), ("alleluia", "Alleluja", "alleluja"),
         ("aklamacja", "Aklamacja", "aklamacja"), ("psalm", "Psalm", "psalm"), ("sekwencja", "Sekwencja", "sekwencja"),
         ("sequentia", "Sekwencja", "sekwencja"), ("introit", "Introit", "wejście"), ("offertorium", "Ofiarowanie",
                                                                                     "przygotowanie darów"),
         ("communio", "Komunia", "komunia"), ("ite missa", "Ite missa est", "zakończenie"),
         ("benedicamus", "Benedicamus Domino", "zakończenie"), ("requiem", "Requiem", "requiem")]
SMALL = {"o", "w", "i", "z", "na", "do", "od", "pro", "de", "in", "et", "ad", "a", "cum", "per", "dla", "ze", "we"}
RE_CREDITS = re.compile(r"(?i)^\s*(t\.|m\.|sł\.|muz\.|opr\.|harm\.|tł\.|oprac\.)\s*:?")


def _fold(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", (t or "").replace("ł", "l").replace("Ł", "L"))
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def nice(t):
    """„MSZA O ZMARTWYCHWSTANIU PAŃSKIM” → „Msza o Zmartwychwstaniu Pańskim”."""
    words = re.sub(r"\s+", " ", t.strip()).split(" ")
    out = []
    for k, w in enumerate(words):
        lw = w.lower()
        if k and lw in SMALL:
            out.append(lw)
        elif len(w) <= 4 and not re.search(r"[AEIOUYĄĘÓaeiouyąęó]", w):
            out.append(w)                                   # skrót, np. „BMV”
        else:
            out.append(lw[:1].upper() + lw[1:])
    return " ".join(out)


def part_of(t):
    f = _fold(t)
    for key, name, tag in PARTS:
        if f.startswith(key):
            return name, tag
    return None, None


def _is_caps(t):
    letters = [ch for ch in t if ch.isalpha()]
    return len(letters) >= 3 and sum(1 for ch in letters if ch.isupper()) >= 0.85 * len(letters)


def analyse(path):
    """Strony → [{'page', 'h', 'heads': [(y, rozmiar, tekst)], 'notes': [(y, tekst)], 'images': [(x0,y0,x1,y1)]}]."""
    import pypdfium2 as pdfium
    from modul_slowa_z_nut import _pdf_page_items, _text_lines, _line_text, _fsize
    doc = pdfium.PdfDocument(path)
    pages = []
    for pi in range(len(doc)):
        page = doc[pi]
        chars, segs, staves = _pdf_page_items(page)
        lines = [(l[0], _fsize(l), _line_text(l)) for l in _text_lines(chars)]
        imgs = []
        for o in page.get_objects(max_depth=4):
            if o.type == 3:
                b = o.get_bounds()
                if (b[2] - b[0]) * (b[3] - b[1]) > 0.02 * page.get_width() * page.get_height():
                    imgs.append(tuple(b))
        pages.append({'page': pi, 'h': page.get_height(), 'w': page.get_width(), 'lines': lines,
                      'images': sorted(imgs, key=lambda b: -b[3]), 'staves': len(staves)})
    doc.close()
    return pages


def looks_like_image_songbook(path):
    try:
        pages = analyse(path)
    except Exception:
        return False
    with_img = sum(1 for p in pages if p['images'])
    caps = sum(1 for p in pages for y, s, t in p['lines'] if _is_caps(t))
    vector = sum(1 for p in pages if p['staves'] >= 2)
    return len(pages) >= 3 and with_img >= 0.6 * len(pages) and caps >= 3 and vector < 0.2 * len(pages)


def items(pages):
    """Podział na utwory: nagłówek największy = cykl (msza), średni = podtytuł cyklu, najmniejszy = część."""
    sizes = sorted({round(s, 1) for p in pages for y, s, t in p['lines'] if _is_caps(t)}, reverse=True)
    if not sizes:
        return []
    big = sizes[0]
    small = sizes[-1] if len(sizes) > 1 else None
    out, cycle, sub, cur = [], "", "", None
    cyc_lines = []

    def new_item(title, part, tag, pi):
        nonlocal cur
        cur = {'cycle': cycle, 'sub': sub, 'part': part, 'tag': tag, 'title': title, 'regions': [], 'notes': [],
               'page': pi}
        out.append(cur)

    for p in pages:
        pi = p['page']
        events = sorted([(y, s, t) for y, s, t in p['lines']], key=lambda e: -e[0])
        # łączenie wielowierszowych nagłówków cyklu („MSZA / O ZMARTWYCHWSTANIU / PAŃSKIM”)
        merged = []
        for y, s, t in events:
            if merged and _is_caps(t) and _is_caps(merged[-1][2]) and abs(merged[-1][1] - s) < 0.5 \
                    and merged[-1][0] - y < 2.2 * s and part_of(t)[0] is None and part_of(merged[-1][2])[0] is None:
                merged[-1] = (y, s, merged[-1][2] + " " + t)
            else:
                merged.append((y, s, t))
        heads = [(y, s, t) for y, s, t in merged if _is_caps(t)]
        notes = [(y, t) for y, s, t in merged if not _is_caps(t)]
        cuts = []                                   # (y, akcja)
        for y, s, t in heads:
            name, tag = part_of(t)
            if name and (small is None or s <= small + 0.5):
                cuts.append((y, 'part', t, name, tag))
            elif s >= (big + (small or big)) / 2 - 0.3:
                cuts.append((y, 'cycle', t, None, None))
            else:
                cuts.append((y, 'sub', t, name, tag))
        # obrazki i notatki przypisane do kawałków strony między nagłówkami
        bounds = [p['h'] + 1] + [c[0] for c in cuts]
        segments = [(bounds[k], bounds[k + 1] if k + 1 < len(bounds) else -1) for k in range(len(bounds))]
        for k, (top, bot) in enumerate(segments):
            if k > 0:
                y, kind, t, name, tag = cuts[k - 1]
                if kind == 'cycle':
                    cycle, sub = nice(t), ""
                    if not re.search(r"\s", t.strip()):             # sama „MSZA” – dopisz stronę
                        cycle = f"{nice(t)} (s. {pi + 1})"
                    cur = None
                elif kind == 'sub':
                    if name:
                        new_item(f"{cycle} – {name}" if cycle else name, name, tag, pi)
                    else:
                        sub = nice(t)
                        cur = None
                else:
                    new_item(f"{cycle} – {name}" if cycle else name, name, tag, pi)
            imgs = [b for b in p['images'] if bot < (b[1] + b[3]) / 2 < top]
            nts = [t for y, t in notes if bot < y < top]
            if not imgs and not nts:
                continue
            if cur is None:
                title = " – ".join(x for x in (cycle, sub) if x) or f"Utwór (s. {pi + 1})"
                new_item(title, None, None, pi)
            for b in imgs:
                cur['regions'].append((pi, b))
            cur['notes'] += nts
    return [it for it in out if it['regions']]


def render_regions(path, regions, dpi=150):
    """Wycięte obrazki nut → PDF (bajty); kolejne fragmenty jeden pod drugim na stronach A4."""
    import pypdfium2 as pdfium
    from PIL import Image
    doc = pdfium.PdfDocument(path)
    scale = dpi / 72
    crops = []
    for pi, (x0, y0, x1, y1) in regions:
        page = doc[pi]
        ph = page.get_height()
        img = page.render(scale=scale, crop=(x0, y0, page.get_width() - x1, ph - y1)).to_pil().convert("RGB")
        crops.append(img)
    doc.close()
    if not crops:
        return b""
    W = int(8.27 * dpi)
    H = int(11.69 * dpi)
    margin = int(0.5 * dpi)
    pages, cur, y = [], None, margin
    for im in crops:
        if im.width > W - 2 * margin:
            r = (W - 2 * margin) / im.width
            im = im.resize((int(im.width * r), int(im.height * r)))
        if cur is None or y + im.height > H - margin:
            cur = Image.new("RGB", (W, H), "white")
            pages.append(cur)
            y = margin
        cur.paste(im, ((W - im.width) // 2, y))
        y += im.height + int(0.12 * dpi)
    buf = io.BytesIO()
    pages[0].save(buf, "PDF", resolution=dpi, save_all=True, append_images=pages[1:])
    return buf.getvalue()


# ---------------------------------------------------------------------
# OCR (opcjonalnie – gdy jest tesseract)
# ---------------------------------------------------------------------

def ocr_available():
    return bool(shutil.which("tesseract"))


def _ocr_tsv(img, lang="pol"):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "a.png")
        img.save(p)
        try:
            r = subprocess.run(["tesseract", p, "-", "-l", lang, "--psm", "6", "tsv"], capture_output=True,
                               text=True, timeout=60)
        except Exception:
            return []
    rows = []
    for line in r.stdout.splitlines()[1:]:
        f = line.split("\t")
        if len(f) == 12 and f[11].strip():
            try:
                rows.append({'line': (int(f[2]), int(f[3]), int(f[4])), 'conf': float(f[10]), 'text': f[11],
                             'top': int(f[7]), 'left': int(f[6])})
            except ValueError:
                pass
    return rows


RE_SYL = re.compile(r"^[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźżÁÉÍÓÚáéíóúǽæÆ]+[,.;:!?]?$")


def ocr_item(path, regions, max_regions=8):
    """(autorzy, szkic słów) z obrazków nut. Słowa: wiersze z sylabami („Pa - nie, zmi - łuj”) o dobrej pewności."""
    if not ocr_available():
        return "", ""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(path)
    credits, lyr = [], []
    for pi, (x0, y0, x1, y1) in regions[:max_regions]:
        page = doc[pi]
        img = page.render(scale=300 / 72, crop=(x0, y0, page.get_width() - x1, page.get_height() - y1)).to_pil()
        rows = _ocr_tsv(img.convert("L"))
        lines = {}
        for w in rows:
            lines.setdefault(w['line'], []).append(w)
        for key in sorted(lines, key=lambda k: min(w['top'] for w in lines[k])):
            ws = sorted(lines[key], key=lambda w: w['left'])
            text = " ".join(w['text'] for w in ws)
            if RE_CREDITS.match(text):
                credits.append(text.strip())
                continue
            toks = [w for w in ws if w['text'] not in ("-", "–", "_")]
            good = [w for w in toks if RE_SYL.match(w['text']) and w['conf'] >= 55]
            hyph = sum(1 for w in ws if w['text'] in ("-", "–"))
            letters = sum(len(w['text']) for w in good)
            if len(toks) >= 2 and len(good) >= 0.8 * len(toks) and (hyph or len(good) >= 3) \
                    and letters >= 2.2 * len(good):
                t = re.sub(r"\s*[-–]\s*", "", text)        # „Pa - nie” → „Panie”
                t = re.sub(r"\s+", " ", t).strip()
                if t and t not in lyr:
                    lyr.append(t)
    doc.close()
    return "; ".join(dict.fromkeys(credits)), "\n".join(lyr)


def collection(path, progress=None, ocr=True):
    """Zbiór pieśni (format modul_zbior) albo None."""
    pages = analyse(path)
    its = items(pages)
    if len(its) < 2:
        return None
    try:
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(path)
        book = (doc.get_metadata_dict().get('Title') or "").strip()
        doc.close()
    except Exception:
        book = ""
    book = nice(book) if book and _is_caps(book) else book
    book = book or re.sub(r"^[0-9a-f]{8}-", "", os.path.splitext(os.path.basename(path))[0])
    out = []
    for k, it in enumerate(its):
        if progress:
            progress(k, len(its))
        credits, lyr = ocr_item(path, it['regions']) if ocr else ("", "")
        pages_used = sorted({pi for pi, _ in it['regions']})
        uw = [f"{book}, s. {pages_used[0] + 1}"]
        if credits:
            uw.append(credits)
        if it['notes']:
            uw.append(" ".join(it['notes']))
        if not ocr_available():
            uw.append("nuty są obrazkiem – słowa trzeba wpisać")
        tags = [x for x in (it['tag'], it['cycle'] if it['tag'] else "") if x]
        is_ord = it['tag'] in ("kyrie", "gloria", "credo", "sanctus", "agnus dei")
        cat = "Części stałe Mszy" if is_ord or re.search(r"(?i)\b(msza|missa|ordinarium)\b", it['cycle']) else ""
        out.append({'title': it['title'], 'refren': '', 'zwrotki_raw': '', 'szkic': lyr, 'uwagi': " | ".join(uw),
                    'kategoria': cat, 'tagi': ", ".join(tags), 'youtube': '', 'numer': str(pages_used[0] + 1),
                    'pdf': path, 'strony': pages_used, 'regiony': it['regions']})
    return {'piesni': out, 'naglowek': book, 'kategoria': ''}
