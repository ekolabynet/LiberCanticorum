#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Liber Canticorum – śpiewnik tekstowy w PDF (wiele pieśni: numerowane tytuły, zwrotki, akordy z boku).

Tytuły rozpoznawane są po kroju i wielkości pisma, a nie tylko po numerze – dzięki temu „1. Nie chcę…”
(zwrotka) nie myli się z „1. Abba, należę do Ciebie” (tytuł). Akordy, żywa pagina, numery stron,
stopki i ramki z boku strony są pomijane. Wynik to tekst z oznaczonymi tytułami (modul_zbior.MARK),
który rozumie modul_zbior.parse_collection.

Licencja: GPL-3.0-or-later.
"""
import re
from collections import Counter, defaultdict

RE_NUM_TITLE = re.compile(r"^(\d{1,4}\s?[a-zA-Z]?)\.\s+(\S.*)$")
RE_CHORD_TOK = re.compile(r"^[(\[]*([A-Ha-h](is|es|s|#|b)?(m|moll|maj|dim|aug|sus|add)?\d{0,2}"
                          r"(/[A-Ha-h](is|es|#|b)?)?)[)\]]*[.,…]*$")
RE_REPEAT_TOK = re.compile(r"^(/?\s*x\d+|/x\d+|/|\(bis\)|bis|\.\.\.|…|–|-|\|)$", re.I)


def _font(name):
    return re.sub(r"^[A-Z]{6}\+", "", name or "")


def _page_chars(page):
    """Znaki strony: (x0, y0, x1, y1, znak, krój, gruby)."""
    import ctypes
    import pypdfium2.raw as raw
    try:
        from modul_slowa_z_nut import _char_hidden, _CLIP_CACHE
        _CLIP_CACHE.clear()
    except Exception:
        _char_hidden = None
    tp = page.get_textpage()
    buf = ctypes.create_string_buffer(256)
    out = []
    for i in range(tp.count_chars()):
        c = tp.get_text_range(i, 1)
        if not c or not c.strip():
            if out and c in (" ", "\t", "\u00a0", "\r", "\n"):
                out[-1] = out[-1][:7] + (True,) + out[-1][8:]          # odstęp po znaku (z pliku albo dopisany przez PDFium)
            continue
        if '\ue000' <= c <= '\uf8ff':
            continue
        box = tp.get_charbox(i)
        if _char_hidden and _char_hidden(tp, i, box):
            continue
        th = box[3] - box[1]
        try:
            lb = tp.get_charbox(i, loose=True)          # pudełko na całą wysokość pisma – równe w całym wierszu
            box = (box[0], lb[1], box[2], lb[3])
        except Exception:
            pass
        fl = ctypes.c_int()
        try:
            raw.FPDFText_GetFontInfo(tp.raw, i, buf, 256, ctypes.byref(fl))
            name = _font(buf.value.decode('utf-8', 'ignore'))
            weight = raw.FPDFText_GetFontWeight(tp.raw, i)
        except Exception:
            name, weight = "", 400
        bold = weight >= 600 or bool(re.search(r"(?i)bold|black|heavy|semibold", name))
        out.append((box[0], box[1], box[2], box[3], c, name, bold, False, th))
    return out


def _lines(chars):
    """Znaki → wiersze od góry: [{'y', 'h', 'chars'}] (litery wysokie i niskie w jednym wierszu)."""
    chars = sorted(chars, key=lambda c: -(c[1] + c[3]) / 2)
    rows = []
    for c in chars:
        yc, h = (c[1] + c[3]) / 2, c[3] - c[1]
        for r in rows:
            if abs(r['y'] - yc) < 0.35 * max(r['h'], h, 1):
                r['chars'].append(c)
                r['lo'], r['hi'] = min(r['lo'], c[1]), max(r['hi'], c[3])
                if c[4].isalnum():
                    r['hs'].append(c[8])
                break
        else:
            rows.append({'y': yc, 'h': h, 'lo': c[1], 'hi': c[3], 'chars': [c], 'hs': [c[8]] if c[4].isalnum() else []})
    out = []
    for r in rows:
        r['chars'].sort(key=lambda c: c[0])
        hs = sorted(r['hs']) or [r['h']]
        r['h'] = hs[len(hs) // 2]
        ls = sorted(c[3] - c[1] for c in r['chars'])
        r['lh'] = ls[len(ls) // 2]                      # wysokość pisma (pudełko „luźne”) – miara stopnia pisma
        out.append(r)
    out.sort(key=lambda r: -r['y'])
    return out


def _segments(row):
    """Wiersz → odcinki rozdzielone dużą przerwą: [(x0, x1, tekst, [znaki])]."""
    cs, h = row['chars'], max(row['h'], 3)
    segs, cur = [], [cs[0]]
    for c in cs[1:]:
        if c[0] - cur[-1][2] > 2.2 * h:
            segs.append(cur)
            cur = [c]
        else:
            cur.append(c)
    segs.append(cur)
    out = []
    for k, s in enumerate(segs):
        if len(s) == 1 and s[0][4].isalpha() and len(segs) > 1:
            continue                                     # litera działu na marginesie („A”, „B”)
        txt = ""
        for k, c in enumerate(s):
            if k and (s[k - 1][7] or c[0] - s[k - 1][2] > 0.3 * h) and c[4] not in ",.;:!?…)" and s[k - 1][4] not in "(":
                txt += " "
            txt += c[4]
        out.append((s[0][0], s[-1][2], txt.strip(), s))
    return out


def _first_text(segs):
    """Tekst pierwszego odcinka; numer oddzielony tabulatorem („1.⇥Abba…”) łączy się z dalszym tekstem."""
    if len(segs) > 1 and re.fullmatch(r"\d{1,4}\s?[a-zA-Z]?\.", segs[0][2]):
        return segs[0][2] + " " + segs[1][2], segs[0][3] + segs[1][3]
    return segs[0][2], segs[0][3]


def _head_key(row):
    """Klucz żywej paginy: litery bez cyfr i bez pojedynczych liter na marginesie."""
    t = " ".join(s[2] for s in _segments(row))
    return re.sub(r"[\W\d_]+", "", t)


def _is_chord_text(t):
    toks = [x for x in re.split(r"[\s/]+", t.replace("(", " ").replace(")", " ")) if x]
    if not toks:
        return True
    good = sum(1 for x in toks if RE_CHORD_TOK.match(x) or RE_REPEAT_TOK.match(x) or re.fullmatch(r"x?\d", x))
    return good == len(toks) and any(RE_CHORD_TOK.match(x) for x in toks)


def _strip_chords(seg_chars, body_font, h):
    """Koniec odcinka zapisany innym (grubszym) krojem i wyglądający jak akordy – usuń."""
    words, cur = [], [seg_chars[0]]
    for c in seg_chars[1:]:
        if cur[-1][7] or c[0] - cur[-1][2] > 0.3 * h:
            words.append(cur)
            cur = [c]
        else:
            cur.append(c)
    words.append(cur)
    while words:
        w = words[-1]
        txt = "".join(c[4] for c in w)
        other = sum(1 for c in w if c[6] or c[5] != body_font) >= 0.6 * len(w)
        if other and (RE_CHORD_TOK.match(txt) or re.fullmatch(r"[/(]*x?\d?[)]*|\.\.\.|…|/", txt)
                      or re.fullmatch(r"[(]*([A-Ha-h](is|es|m)?\d?/?)+[)]*[.…]*", txt)
                      or (len(txt) <= 9 and re.fullmatch(r"[(\[]*[A-Ha-h][a-hA-H0-9#+/()]*[)\]]*[.…]*", txt))):
            words.pop()
        else:
            break
    return [c for w in words for c in w]


def text_songbook(path, progress=None):
    """Śpiewnik tekstowy PDF → (tekst z oznaczonymi tytułami, nazwa śpiewnika, liczba tytułów) albo None."""
    import pypdfium2 as pdfium
    from modul_zbior import MARK
    doc = pdfium.PdfDocument(path)
    n = len(doc)
    pages = []
    for pi in range(n):
        if progress:
            progress(pi, n)
        page = doc[pi]
        rows = _lines(_page_chars(page))
        pages.append({'w': page.get_width(), 'h': page.get_height(), 'rows': rows})
    doc.close()
    # krój i wysokość tekstu podstawowego
    fonts, heights = Counter(), Counter()
    for pg in pages:
        for r in pg['rows']:
            for c in r['chars']:
                if c[4].isalpha():
                    fonts[c[5]] += 1
            heights[round(r['lh'], 1)] += len(r['chars'])
    if not fonts:
        return None
    body_font = fonts.most_common(1)[0][0]
    body_h = heights.most_common(1)[0][0]
    # żywa pagina i stopki: ten sam napis (bez cyfr) na wielu stronach
    edge = Counter()
    for pg in pages:
        for r in pg['rows']:
            edge[_head_key(r)] += 1
    running = {t for t, k in edge.items() if k >= max(4, n // 6)}
    # kandydaci na tytuły: „123. Tytuł”, grupowani po kroju i wysokości
    groups = defaultdict(list)
    for pi, pg in enumerate(pages):
        for ri, r in enumerate(pg['rows']):
            segs = _segments(r)
            if not segs:
                continue
            ft, fcs = _first_text(segs)
            m = RE_NUM_TITLE.match(ft)
            if not m:
                continue
            letters = [c for c in fcs if c[4].isalpha()]
            if not letters:
                continue
            f = Counter(c[5] for c in letters).most_common(1)[0][0]
            bold = sum(1 for c in letters if c[6]) > 0.6 * len(letters)
            groups[(f, bold, round(r['lh'] / max(body_h, 1) * 5) / 5)].append(
                (pi, ri, int(re.match(r"\d+", m.group(1)).group(0))))
    best, best_score = None, 0
    for key, items in groups.items():
        nums = [x[2] for x in items]
        if len(nums) < 3:
            continue
        up = sum(1 for a, b in zip(nums, nums[1:]) if b > a) / max(1, len(nums) - 1)
        uniq = len(set(nums)) / len(nums)
        score = len(nums) * up * uniq
        if up >= 0.75 and uniq >= 0.8 and score > best_score:
            best, best_score = key, score
    if not best:
        return None
    # tytuł musi się wyróżniać krojem albo wielkością – inaczej to zwykłe numerowane zwrotki
    if best[0] == body_font and not best[1] and best[2] <= 1.0:
        return None
    titles = {(pi, ri) for pi, ri, _ in groups[best]}
    # tekst
    out, book = [], ""
    for pi, pg in enumerate(pages):
        prev_y, gaps = None, []
        rows = pg['rows']
        for a, b in zip(rows, rows[1:]):
            gaps.append(a['y'] - b['y'])
        step = sorted(gaps)[len(gaps) // 2] if gaps else body_h * 1.5
        for ri, r in enumerate(rows):
            raw_t = "".join(c[4] for c in r['chars'])
            if _head_key(r) in running and len(_head_key(r)) >= 6:
                if not book and len(raw_t) > 8:
                    book = re.sub(r"\s*\d+\s*", " ", " ".join(s[2] for s in _segments(r))).strip()
                continue
            if re.fullmatch(r"\d{1,4}", raw_t.strip()) or len(raw_t.strip()) <= 1:
                continue                                    # numer strony, litera działu na marginesie
            if r['lh'] < 0.8 * body_h and (pi, ri) not in titles:
                continue                                    # stopka / przypis drobnym pismem
            if (pi, ri) in titles:
                segs = _segments(r)
                if prev_y is not None:
                    out.append("")
                out.append(MARK + _first_text(segs)[0])
                prev_y = r['y']
                continue
            keep = []
            for x0, x1, t, cs in _segments(r):
                if _is_chord_text(t):
                    continue
                if x0 > 0.55 * pg['w'] and keep == []:
                    continue                                # ramka z boku strony (np. wersja obcojęzyczna)
                cs = _strip_chords(cs, body_font, max(r['h'], 3))
                if not cs:
                    continue
                seg = _segments({'chars': cs, 'h': r['h']})
                keep.append(" ".join(s[2] for s in seg))
            if not keep:
                continue
            line = " ".join(keep).strip()
            line = re.sub(r"\s+([,.;:!?])", r"\1", line)
            if prev_y is not None and prev_y - r['y'] > 1.6 * step:
                out.append("")
            out.append(line)
            prev_y = r['y']
        out.append("")
    # „1.” samo w wierszu (numer w osobnej kolumnie) – dołącz do następnego wiersza
    fixed = []
    for line in out:
        if fixed and re.fullmatch(r"\d{1,2}\.", fixed[-1].strip()) and line.strip():
            fixed[-1] = fixed[-1].strip() + " " + line
        else:
            fixed.append(line)
    return "\n".join(fixed), book, len(titles)


def collection(path, progress=None):
    """Śpiewnik tekstowy PDF → zbiór pieśni (format modul_zbior) albo None."""
    import os
    import modul_zbior as zb
    r = text_songbook(path, progress)
    if not r:
        return None
    text, book, n = r
    if n < 3:
        return None
    book = book or os.path.splitext(os.path.basename(path))[0]
    coll = zb.parse_collection(text, book, min_songs=3, sections=False)
    if coll:
        coll['naglowek'] = coll.get('naglowek') or book
        for sg in coll['piesni']:
            sg['uwagi'] = sg['uwagi'].replace(f"{book} nr ", f"{book}, nr ")
    return coll
