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


RE_TOC = re.compile(r"^(\S.*?\S)\s*(\.\s?){4,}\s*\d{1,4}$")


def _fold(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", (t or "").replace("ł", "l").replace("Ł", "L"))
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _nice_case(t):
    """„CHRYSTUS PAN, BOŻY SYN” → „Chrystus pan, boży syn” (gdy tytuł zapisano kapitalikami)."""
    letters = [ch for ch in t if ch.isalpha()]
    if letters and sum(1 for ch in letters if ch.isupper()) > 0.8 * len(letters):
        t = t.lower()
        return t[:1].upper() + t[1:]
    return t


def _smallcaps(row):
    """Tytuł pisany kapitalikami („CHRYSTUS PAN, BOŻY SYN”): wielkie zostają tylko litery naprawdę wyższe."""
    cs = [c for c in row['chars'] if c[4].isalpha()]
    if not cs or any(c[4].islower() for c in cs):
        return ""
    plain = [c[8] for c in cs if c[4] in "ABCDEFGHIJKLMNOPRSTUWYZ"]   # bez znaków diakrytycznych
    if not plain:
        return ""
    hi, lo = max(plain), min(plain)
    if hi - lo < 0.12 * hi:
        return ""                                      # wszystkie równe – zwykłe wersaliki
    cut = (hi + lo) / 2
    txt, prev = "", None
    for c in row['chars']:
        if prev is not None and (prev[7] or c[0] - prev[2] > 0.3 * row['h']) and c[4] not in ",.;:!?)":
            txt += " "
        ch = c[4]
        if ch.isalpha():
            base = c[8] - (0.18 * hi if ch in "ĄĆĘŁŃÓŚŹŻ" else 0)
            ch = ch if base >= cut else ch.lower()
        txt += ch
        prev = c
    return txt.strip()


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
        if len(s) == 1 and s[0][4].isalpha() and len(segs) > 1 and s[0][2] < 0.08 * row.get('pw', 1e9):
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
        for r in rows:
            r['pw'] = page.get_width()
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
    # spis treści („Tytuł ........ 51”) – do sprawdzania tytułów i ich zapisu (małe/wielkie litery)
    toc = {}
    for pg in pages:
        for r in pg['rows']:
            t = " ".join(s[2] for s in _segments(r))
            m = RE_TOC.match(t)
            if m:
                toc[_fold(m.group(1))] = m.group(1).strip()
    if best and best[0] == body_font and not best[1] and best[2] <= 1.0:
        best = None                     # tytuł musi się wyróżniać krojem albo wielkością – to zwykłe zwrotki
    names = {}
    if best:
        titles = {(pi, ri) for pi, ri, _ in groups[best]}
    else:
        # tytuły bez numerów: wiersze innym (grubszym / większym) pismem, które nie są akordami
        ugroups = defaultdict(list)
        for pi, pg in enumerate(pages):
            for ri, r in enumerate(pg['rows']):
                segs = _segments(r)
                if not segs:
                    continue
                t = " ".join(x[2] for x in segs)
                letters = [c for c in r['chars'] if c[4].isalpha()]
                ws = _words(r['chars'], max(r['h'], 3))
                if len(letters) < 3 or _is_chord_text(t) or RE_TOC.match(t) or _head_key(r) in running \
                        or (ws and all(_chordish(w) for _, w in ws)):
                    continue
                f = Counter(c[5] for c in letters).most_common(1)[0][0]
                bold = sum(1 for c in letters if c[6]) > 0.6 * len(letters)
                ratio = round(r['lh'] / max(body_h, 1) * 10) / 10
                if f == body_font and not bold and ratio <= 1.05:
                    continue
                if re.match(r"(?i)^(ref|refren|ant|k\.|w\.|\d+\.)", t):
                    continue
                ugroups[(f, bold, ratio)].append((pi, ri, t))
        cand = [(k, v) for k, v in ugroups.items() if len(v) >= 3]
        if not cand:
            return None

        def uscore(kv):
            k, v = kv
            in_toc = sum(1 for _, _, t in v if _fold(t) in toc)
            return (in_toc, len(v))
        key, items = max(cand, key=uscore)
        if toc and uscore((key, items))[0] < 0.3 * len(items):
            return None
        titles = {(pi, ri) for pi, ri, _ in items}
        for pi, ri, t in items:
            names[(pi, ri)] = toc.get(_fold(t)) or _smallcaps(pages[pi]['rows'][ri]) or _nice_case(t)
    # tekst (out) i ten sam tekst z akordami w zapisie ChordPro (outc)
    out, outc, book = [], [], ""
    for pi, pg in enumerate(pages):
        rows = pg['rows']
        kept = []                    # (y, tekst, czy_tytuł, ile_pominiętych_wierszy_przed, tekst_z_akordami)
        skipped, pending = 0, None   # pending: akordy z wiersza nad tekstem [(x, akord)]
        for ri, r in enumerate(rows):
            raw_t = "".join(c[4] for c in r['chars'])
            if _head_key(r) in running and len(_head_key(r)) >= 6:
                if not book and len(raw_t) > 8:
                    book = re.sub(r"\s*\d+\s*", " ", " ".join(s[2] for s in _segments(r))).strip()
                continue
            words = _words(r['chars'], max(r['h'], 3))
            if words and all(_chordish(w) for _, w in words) and any(RE_CHORD_TOK.match(w) for _, w in words) \
                    and (pi, ri) not in titles and not (len(words) == 1 and words[0][0] < 0.08 * pg['w']):
                if pending:                                  # dwa wiersze akordów z rzędu – pierwszy osobno
                    kept.append((r['y'], "", False, skipped, " ".join(f"[{w}]" for _, w in pending)))
                pending = [(x, w) for x, w in words]
                skipped += 1
                continue
            if re.fullmatch(r"[|\s]*\d{1,4}[|\s]*", raw_t) or len(raw_t.strip()) <= 1:
                continue                                    # numer strony, litera działu na marginesie
            if r['lh'] < 0.8 * body_h and (pi, ri) not in titles:
                continue                                    # stopka / przypis drobnym pismem
            if (pi, ri) in titles:
                t = MARK + (names.get((pi, ri)) or _first_text(_segments(r))[0])
                kept.append((r['y'], t, True, skipped, t))
                skipped, pending = 0, None
                continue
            if RE_TOC.match(" ".join(x[2] for x in _segments(r))):
                continue                                    # wiersz spisu treści
            keep_chars, side = [], []
            for x0, x1, t, cs in _segments(r):
                if _is_chord_text(t):
                    if keep_chars or x0 > 0.3 * pg['w']:
                        side.append(t)                      # akordy z boku wiersza
                    continue
                if x0 > 0.55 * pg['w'] and not keep_chars:
                    continue                                # ramka z boku strony (np. wersja obcojęzyczna)
                kept_cs = _strip_chords(cs, body_font, max(r['h'], 3))
                if len(kept_cs) < len(cs):
                    tail = _segments({'chars': cs[len(kept_cs):], 'h': r['h']})
                    side.append(" ".join(x[2] for x in tail))
                if kept_cs:
                    if keep_chars:
                        keep_chars.append(None)             # przerwa między odcinkami = spacja
                    keep_chars += kept_cs
            line, pos = _text_pos(keep_chars, max(r['h'], 3))
            line = re.sub(r"\s+([,.;:!?])", r"\1", line).strip()
            if line:
                cl, _ = _text_pos(keep_chars, max(r['h'], 3))
                if pending:
                    pm = re.match(r"^\s*(\d{1,2}\.|ref(ren)?\.?:?|r\.:?|ant\.?:?|k\.:?|w\.:?)\s*", cl, re.I)
                    pre = pm.end() if pm else 0               # akord nie przed numerem zwrotki / „Ref.:”
                    ins = []
                    for x, ch in pending:
                        k = next((idx for (cx0, cx1, idx) in pos if cx1 > x + 0.5), None)
                        ins.append((len(cl) if k is None else max(k, pre), ch))
                    cl = _insert(cl, ins)
                cl = re.sub(r"\s+([,.;:!?])", r"\1", cl).strip()
                if side:
                    cl += " ‖ " + " ".join(side)
                kept.append((r['y'], line, False, skipped, cl))
                skipped, pending = 0, None
            else:
                skipped += 1                                # wiersz akordów – nie jest przerwą między zwrotkami
        if pending:
            kept.append((kept[-1][0] if kept else 0, "", False, 0, " ".join(f"[{w}]" for _, w in pending)))
        # odstęp między zwrotkami: przerwa wyraźnie większa niż zwykła między wierszami tekstu
        gaps = sorted((a[0] - b[0]) / (b[3] + 1) for a, b in zip(kept, kept[1:]) if not a[2] and not b[2] and a[1] and b[1])
        step = gaps[len(gaps) // 4] if gaps else body_h * 1.5
        prev = None
        for y, line, is_t, sk, cl in kept:
            if not line:                                   # sam wiersz akordów (np. przygrywka)
                outc.append(cl)
                continue
            if prev is not None and (is_t or (prev - y) / (sk + 1) > 1.45 * step):
                out.append("")
                outc.append("")
            out.append(line)
            outc.append(cl)
            prev = y
        out.append("")
        outc.append("")
    if not book:
        try:
            first = [" ".join(s[2] for s in _segments(r)) for r in pages[0]['rows']]
            book = " ".join(first)[:80] if 0 < len(" ".join(first)) <= 80 else ""
            book = re.sub(r"(\d) (?=\d)", r"\1", book)
        except Exception:
            book = ""
    # „1.” samo w wierszu (numer w osobnej kolumnie) – dołącz do następnego wiersza
    def fix(lines):
        fixed = []
        for line in lines:
            if fixed and re.fullmatch(r"\d{1,2}\.", fixed[-1].strip()) and line.strip():
                fixed[-1] = fixed[-1].strip() + " " + line
            else:
                fixed.append(line)
        return "\n".join(fixed)
    global LAST_CHORDS
    spaced = []
    for line in outc:                                  # zwrotka / refren od nowego akapitu (jak w tekście)
        if spaced and spaced[-1].strip() and re.match(r"^(\[[^\]]*\])*\s*(\d{1,2}\.\s|ref(ren)?\.?:)", line, re.I):
            spaced.append("")
        spaced.append(line)
    LAST_CHORDS = fix(spaced)
    return fix(out), book, len(titles)


LAST_CHORDS = ""


def _words(chars, h):
    """Znaki wiersza → słowa [(x0, tekst)]."""
    out, cur = [], []
    for c in chars:
        if cur and (cur[-1][7] or c[0] - cur[-1][2] > 0.3 * h):
            out.append((cur[0][0], "".join(x[4] for x in cur)))
            cur = []
        cur.append(c)
    if cur:
        out.append((cur[0][0], "".join(x[4] for x in cur)))
    return out


def _chordish(w):
    return bool(RE_CHORD_TOK.match(w) or RE_REPEAT_TOK.match(w)
                or re.fullmatch(r"[(\[]?x?\d{1,2}[+\-]?[)\]]?|/x\d|[_I|]+", w)
                or re.fullmatch(r"[(\[]*([A-Ha-h](is|es)?(m|sus|maj|add|dim|aug)?\d{0,2}[+\-]?/?)+[)\]]*[.…]*", w)
                and len(w) <= 12)


def _text_pos(chars, h):
    """Znaki (None = przerwa) → (tekst, [(x0, x1, indeks_w_tekście)])."""
    txt, pos, prev = "", [], None
    for c in chars:
        if c is None:
            if txt and not txt.endswith(" "):
                txt += " "
            prev = None
            continue
        if prev is not None and (prev[7] or c[0] - prev[2] > 0.3 * h) and c[4] not in ",.;:!?…)" \
                and prev[4] not in "(" and not txt.endswith(" "):
            txt += " "
        pos.append((c[0], c[2], len(txt)))
        txt += c[4]
        prev = c
    return txt, pos


def _insert(line, ins):
    for k, ch in sorted(ins, key=lambda t: -t[0]):
        line = line[:k] + f"[{ch}]" + line[k:]
    return line


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
    book = book or re.sub(r"^[0-9a-f]{8}-", "", os.path.splitext(os.path.basename(path))[0])
    coll = zb.parse_collection(text, book, min_songs=3, sections=False)
    if coll:
        # akordy: ten sam podział na pieśni po oznaczonych tytułach
        import modul_akordy as ak
        blocks, cur = [], None
        for line in LAST_CHORDS.split("\n"):
            if line.startswith(zb.MARK):
                cur = []
                blocks.append(cur)
            elif cur is not None:
                cur.append(line)
        if len(blocks) == len(coll['piesni']):
            for sg, b in zip(coll['piesni'], blocks):
                t = "\n".join(b).strip("\n")
                t = re.sub(r"\n{3,}", "\n\n", t)
                if ak.has_chords(t):
                    sg['akordy'] = t
        coll['naglowek'] = coll.get('naglowek') or book
        for sg in coll['piesni']:
            sg['uwagi'] = sg['uwagi'].replace(f"{book} nr ", f"{book}, nr ")
    return coll
