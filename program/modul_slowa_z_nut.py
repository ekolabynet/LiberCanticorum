# -*- coding: utf-8 -*-
"""Liber Canticorum – import słów pieśni z nut.

Źródła:
  * MuseScore (.mscz, .mscx) – MuseScore 3 i 4, bez uruchamiania MuseScore,
  * MusicXML (.musicxml, .xml, .mxl),
  * MIDI z tekstem (.mid, .kar),
  * PDF z nutami (np. wydruk z MuseScore) – słowa odczytywane z położenia sylab pod pięciolinią.

Wynik: tytuł, refren i zwrotki jako zwykły tekst („Ref.: …”, „1. …”), który program pokazuje w oknie importu
do poprawienia. Licencja: GPL-3.0-or-later (jak cała aplikacja).
"""
import io
import os
import re
import zipfile
import xml.etree.ElementTree as ET

SCORE_LYRICS_EXT = ('.mscz', '.mscx', '.musicxml', '.xml', '.mxl', '.mid', '.midi', '.kar')
_PUNCT_END = re.compile(r'[.,;:!?…]["”»)]?$')
_SENT_END = re.compile(r'[.;:!?…]["”»)]?$')


# ---------------------------------------------------------------------
# wspólne: zdarzenia → tekst
# ---------------------------------------------------------------------
# Zdarzenie = jedna nuta (miejsce w nutach) z sylabami zwrotek: {nr_zwrotki: (sylaba, czy_koniec_słowa)}

def _words(seq):
    """[(sylaba, koniec_słowa)] → lista słów."""
    words, cur = [], ""
    for syl, end in seq:
        cur += syl
        if end:
            if cur.strip():
                words.append(cur.strip())
            cur = ""
    if cur.strip():
        words.append(cur.strip())
    # numer zwrotki wpisany przy pierwszej sylabie („1. Wo-dy”, „2.Mo-cy”) – usuń
    words = [re.sub(r'^\d{1,2}\.\s*', '', w) for w in words]
    return [w for w in words if w]


def _lines(words, max_words=8):
    """Słowa → wiersze: koniec wiersza po interpunkcji (gdy wiersz ma już kilka słów) albo gdy za długi."""
    lines, cur = [], []
    for w in words:
        cur.append(w)
        n = len(cur)
        if (_SENT_END.search(w) and n >= 2) or (_PUNCT_END.search(w) and n >= 4) or n >= max_words + 3 or \
                (n >= max_words and _PUNCT_END.search(w)):
            lines.append(" ".join(cur))
            cur = []
    if cur:
        lines.append(" ".join(cur))
    # bardzo krótki wiersz dołącz do poprzedniego
    out = []
    for ln in lines:
        if out and len(ln.split()) <= 1 and len(out[-1].split()) < max_words:
            out[-1] += " " + ln
        else:
            out.append(ln)
    return out


def events_to_song(events, title=""):
    """Zdarzenia → {'title', 'refren', 'zwrotki': [tekst, …]}.
    Refren = dłuższy fragment, w którym słowa ma tylko pierwsza zwrotka, choć gdzie indziej zwrotek jest więcej."""
    explicit = [e['R'] for e in events if 'R' in e]          # sylaby oznaczone „Ref.”
    events = [{k: v for k, v in e.items() if k != 'R'} for e in events]
    events = [e for e in events if e]
    verses = sorted({v for e in events for v in e})
    if not verses:
        ref = _words(explicit) if explicit else []
        return {'title': title, 'refren': "\n".join(_lines(ref)) if ref else '', 'zwrotki': []}
    if explicit:
        zw = [w for w in (_words([e[v] for e in events if v in e]) for v in verses) if w]
        return {'title': title.strip(), 'refren': "\n".join(_lines(_words(explicit))),
                'zwrotki': ["\n".join(_lines(w)) for w in zw]}
    first = verses[0]
    refrain_idx = set()
    if len(verses) > 1:
        only_first = [set(e) == {first} for e in events]
        k = 0
        while k < len(events):
            if not only_first[k]:
                k += 1
                continue
            j = k
            while j < len(events) and only_first[j]:
                j += 1
            run = events[k:j]
            if len(run) >= 6 and sum(1 for e in run if e[first][1]) >= 3:
                refrain_idx.update(range(k, j))
            k = j
    ref = _words([events[i][first] for i in sorted(refrain_idx)])
    zw = []
    for v in verses:
        seq = [e[v] for i, e in enumerate(events) if v in e and i not in refrain_idx]
        w = _words(seq)
        if w:
            zw.append("\n".join(_lines(w)))
    return {'title': title.strip(), 'refren': "\n".join(_lines(ref)) if ref else '', 'zwrotki': zw}


def song_to_text(song):
    """Tekst w formacie, który rozumie import programu (tytuł, Ref.:, 1., 2., …)."""
    out = [song.get('title') or "Bez tytułu", ""]
    if song.get('refren'):
        out += ["Ref.: " + song['refren'], ""]
    n = len(song.get('zwrotki', []))
    extra = song.get('dopisek', '')
    numbered = n > 1 or bool(re.match(r'\s*\d+\.', extra))
    for i, z in enumerate(song.get('zwrotki', []), 1):
        out += [f"{i}. {z}" if numbered else z, ""]
    if extra:
        out += [extra, ""]
    return "\n".join(out).strip() + "\n"


# ---------------------------------------------------------------------
# MuseScore (.mscz / .mscx)
# ---------------------------------------------------------------------

def _mscx_bytes(path):
    if path.lower().endswith('.mscx'):
        with open(path, 'rb') as f:
            return f.read()
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        try:
            cont = ET.fromstring(z.read('META-INF/container.xml'))
            for rf in cont.iter('rootfile'):
                p = rf.get('full-path', '')
                if p.endswith('.mscx') and p in names:
                    return z.read(p)
        except KeyError:
            pass
        cand = [n for n in names if n.endswith('.mscx') and not n.lower().startswith('excerpts/')]
        if not cand:
            raise RuntimeError("W pliku .mscz nie ma partytury (.mscx).")
        return z.read(cand[0])


def _text_of(el):
    """Tekst elementu MuseScore (bywa z formatowaniem <b>, <i>, <font …/>)."""
    return re.sub(r'\s+', ' ', "".join(el.itertext())).strip() if el is not None else ""


def read_mscx(path):
    root = ET.fromstring(_mscx_bytes(path))
    score = root.find('Score') if root.find('Score') is not None else root
    title = ""
    for t in score.iter('Text'):                     # tytuł z ramki nad nutami
        if (t.findtext('style') or '').strip().lower() == 'title':
            title = _text_of(t.find('text'))
            break
    if not title:
        for m in score.iter('metaTag'):
            if m.get('name') == 'workTitle' and (m.text or '').strip():
                title = m.text.strip()
                break
    best = []
    for staff in score.findall('Staff'):              # pięciolinia z największą liczbą sylab
        events = []
        for measure in staff.iter('Measure'):
            voices = measure.findall('voice') or [measure]
            # w jednym takcie: sylaby z pierwszego głosu, który je ma
            for voice in voices:
                evs = []
                for ch in voice:
                    if ch.tag != 'Chord':
                        continue
                    e = {}
                    for ly in ch.findall('Lyrics'):
                        no = int(ly.findtext('no') or 0)
                        syl = _text_of(ly.find('text'))
                        if not syl:
                            continue
                        kind = (ly.findtext('syllabic') or 'single').strip()
                        e[no] = (syl, kind in ('single', 'end'))
                    if e:
                        evs.append(e)
                if evs:
                    events += evs
                    break
        if sum(len(e) for e in events) > sum(len(e) for e in best):
            best = events
    if not best:
        raise RuntimeError("W nutach nie ma słów (sylab pod nutami).")
    return events_to_song(best, title or os.path.splitext(os.path.basename(path))[0])


# ---------------------------------------------------------------------
# MusicXML (.musicxml / .xml / .mxl)
# ---------------------------------------------------------------------

def _musicxml_bytes(path):
    if not path.lower().endswith('.mxl'):
        with open(path, 'rb') as f:
            return f.read()
    with zipfile.ZipFile(path) as z:
        try:
            cont = ET.fromstring(z.read('META-INF/container.xml'))
            for rf in cont.iter():
                if rf.tag.endswith('rootfile') and rf.get('full-path'):
                    return z.read(rf.get('full-path'))
        except KeyError:
            pass
        cand = [n for n in z.namelist() if n.endswith(('.xml', '.musicxml')) and not n.startswith('META-INF')]
        return z.read(cand[0])


def read_musicxml(path):
    root = ET.fromstring(_musicxml_bytes(path))
    for el in root.iter():                            # bez przestrzeni nazw
        if '}' in el.tag:
            el.tag = el.tag.split('}', 1)[1]
    title = (root.findtext('work/work-title') or root.findtext('movement-title') or "").strip()
    if not title:
        credits = [(float(c.get('font-size') or 0), (c.text or '').strip()) for c in root.iter('credit-words')]
        credits = [c for c in credits if c[1]]
        if credits:
            title = max(credits)[1]
    verse_no = {}
    best = []
    for part in root.findall('part'):
        events = []
        for note in part.iter('note'):
            e = {}
            for ly in note.findall('lyric'):
                num = ly.get('number') or '1'
                if num not in verse_no:
                    m = re.search(r'\d+', num)
                    verse_no[num] = int(m.group()) if m else len(verse_no) + 1
                texts = [t.text or '' for t in ly.findall('text')]
                syl = "".join(texts).strip()      # <elision> łączy kilka sylab na jednej nucie
                if not syl:
                    continue
                kind = (ly.findtext('syllabic') or 'single').strip()
                e[verse_no[num]] = (syl, kind in ('single', 'end'))
            if e:
                events.append(e)
        if sum(len(e) for e in events) > sum(len(e) for e in best):
            best = events
    if not best:
        raise RuntimeError("W nutach nie ma słów (sylab pod nutami).")
    return events_to_song(best, title or os.path.splitext(os.path.basename(path))[0])


# ---------------------------------------------------------------------
# MIDI z tekstem
# ---------------------------------------------------------------------

def read_midi(path):
    from modul_nuty import load_midi_lyrics, lyric_layout
    with open(path, 'rb') as f:
        lyr = load_midi_lyrics(f.read())
    if not lyr:
        raise RuntimeError("W pliku MIDI nie ma zapisanego tekstu.")
    groups, _ = lyric_layout(lyr)
    events = []
    for _t, syls in groups:
        e = {}
        for i, w in enumerate(syls):
            if w.strip():
                e[i] = (w.strip(), w.endswith(' ') or bool(_PUNCT_END.search(w.strip())))
        if e:
            events.append(e)
    return events_to_song(events, os.path.splitext(os.path.basename(path))[0])


# ---------------------------------------------------------------------
# PDF z nutami
# ---------------------------------------------------------------------

_CLIP_CACHE = {}


def _char_hidden(tp, i, box):
    """Czy znak leży poza obszarem przycięcia swojego obiektu tekstowego (niewidoczna kopia tekstu,
    np. ukryta warstwa w śpiewnikach składanych w programach DTP)."""
    try:
        import ctypes
        import pypdfium2.raw as raw
        if not hasattr(raw, 'FPDFText_GetTextObject'):
            return False
        obj = raw.FPDFText_GetTextObject(tp.raw, i)
        return _obj_hidden(obj, box)
    except Exception:
        return False


def _obj_hidden(obj, box):
    """Czy obiekt strony (o ramce box) leży poza swoim obszarem przycięcia."""
    try:
        import ctypes
        import pypdfium2.raw as raw
        if not obj:
            return False
        key = ctypes.cast(obj, ctypes.c_void_p).value
        if key not in _CLIP_CACHE:
            clip = None
            cp = raw.FPDFPageObj_GetClipPath(obj)
            if cp:
                for k in range(raw.FPDFClipPath_CountPaths(cp)):
                    xs, ys = [], []
                    for sgi in range(raw.FPDFClipPath_CountPathSegments(cp, k)):
                        seg = raw.FPDFClipPath_GetPathSegment(cp, k, sgi)
                        x, y = ctypes.c_float(), ctypes.c_float()
                        raw.FPDFPathSegment_GetPoint(seg, ctypes.byref(x), ctypes.byref(y))
                        xs.append(x.value)
                        ys.append(y.value)
                    if xs:
                        b = (min(xs), min(ys), max(xs), max(ys))
                        clip = b if clip is None else (max(clip[0], b[0]), max(clip[1], b[1]),
                                                       min(clip[2], b[2]), min(clip[3], b[3]))
            _CLIP_CACHE[key] = clip
        clip = _CLIP_CACHE[key]
        if clip is None:
            return False
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        return not (clip[0] - 1 <= cx <= clip[2] + 1 and clip[1] - 1 <= cy <= clip[3] + 1)
    except Exception:
        return False


def _pdf_page_items(page):
    """Znaki (x0, y0, x1, y1, znak), krótkie odcinki poziome (x0, x1, y, grubość)
    i pięciolinie [(góra, dół)] od góry strony."""
    _CLIP_CACHE.clear()
    tp = page.get_textpage()
    chars = []
    for i in range(tp.count_chars()):
        c = tp.get_text_range(i, 1)
        if not c or not c.strip() or '\ue000' <= c <= '\uf8ff':     # pomiń znaki nut (czcionka muzyczna)
            continue
        x0, y0, x1, y1 = tp.get_charbox(i)
        if _char_hidden(tp, i, (x0, y0, x1, y1)):
            continue
        try:
            lb = tp.get_charbox(i, loose=True)
            fs = lb[3] - lb[1]                         # stopień pisma (pudełko „luźne”)
        except Exception:
            fs = y1 - y0
        chars.append((x0, y0, x1, y1, c, fs))
    segs, bands, lines, hsum, bandn = [], {}, [], {}, {}
    pw = page.get_width()
    for obj in page.get_objects(max_depth=4):
        if obj.type != 2:                              # FPDF_PAGEOBJ_PATH
            continue
        try:
            x0, y0, x1, y1 = obj.get_bounds() if hasattr(obj, 'get_bounds') else obj.get_pos()
        except Exception:
            continue
        if _obj_hidden(obj.raw, (x0, y0, x1, y1)):
            continue
        w, h = x1 - x0, y1 - y0
        if w > 0.5 and h < 2.2 and w > 2 * h:
            segs.append((x0, x1, (y0 + y1) / 2, h))
            if w > pw * 0.2:
                lines.append((y0 + y1) / 2)            # linia pięciolinii rysowana osobno
            elif h < 1.5:
                ky = round((y0 + y1) / 2, 1)            # linia pięciolinii rysowana takt po takcie
                hsum[ky] = hsum.get(ky, 0) + w
        elif 10 < h < 45 and w > 25:                   # pięciolinia rysowana jednym kształtem (takt po takcie)
            key = (round(y1, 0), round(y0, 0))
            bands[key] = bands.get(key, 0) + w
            bandn[key] = bandn.get(key, 0) + 1
    lines += [y for y, w in hsum.items() if w > pw * 0.25 and y not in lines]
    # pięciolinia jednym kształtem = kilka kształtów (takty) w jednym pasie; jeden szeroki prostokąt to ozdobnik
    staves = [(t, b) for (t, b), w in bands.items() if w > pw * 0.25 and bandn[(t, b)] >= 2]
    ys = sorted({round(y, 1) for y in lines}, reverse=True)
    used = set()
    for i, y in enumerate(ys):                         # 5 równo odległych linii (także przeplecionych z innymi)
        if y in used:
            continue
        for y2 in ys[i + 1:]:
            d = y - y2
            if d > 15:
                break
            if d <= 2 or y2 in used:
                continue
            five = [y]
            for k in range(1, 5):
                hit = [v for v in ys if v not in used and abs(v - (y - k * d)) < 0.4]
                if not hit:
                    break
                five.append(hit[0])
            if len(five) == 5:
                staves.append((five[0], five[4]))
                used.update(five)
                break
    staves.sort(key=lambda s: -s[0])
    clean = []
    for st in staves:                                  # nakładające się pasy = ta sama pięciolinia
        if clean and st[0] > clean[-1][1] - 1:
            if st[0] - st[1] > clean[-1][0] - clean[-1][1]:
                clean[-1] = st
            continue
        clean.append(st)
    return chars, segs, clean


def _text_lines(chars):
    """Znaki → wiersze (od góry): [(y_środek, wysokość, [znaki posortowane po x])]."""
    chars = sorted(chars, key=lambda c: -(c[1] + c[3]) / 2)
    lines = []
    for c in chars:
        yc, h = (c[1] + c[3]) / 2, c[3] - c[1]
        for ln in lines:
            if abs(ln[0] - yc) < 0.45 * max(ln[1], h, 1):
                ln[2].append(c)
                break
        else:
            lines.append([yc, h, [c]])
    # wiersz rozbity na dwa (litery wysokie / niskie, gwiazdka, akcenty) – scal, gdy zakresy pionowe się pokrywają,
    # a znaki nie nachodzą na siebie w poziomie
    def vr(l):
        return min(c[1] for c in l[2]), max(c[3] for c in l[2])
    merged = True
    while merged:
        merged = False
        lines.sort(key=lambda l: -l[0])
        for a, b in zip(lines, lines[1:]):
            (alo, ahi), (blo, bhi) = vr(a), vr(b)
            ov = min(ahi, bhi) - max(alo, blo)
            if ov < 0.5 * min(ahi - alo, bhi - blo) or len(a[2]) < 2 or len(b[2]) < 2:
                continue
            xa = sorted((c[0], c[2]) for c in a[2])
            hit = sum(1 for c in b[2] if any(x0 + 0.3 < c[2] and c[0] < x1 - 0.3 for x0, x1 in xa))
            if hit > 0.15 * len(b[2]):
                continue
            a[2].extend(b[2])
            a[0] = (a[0] + b[0]) / 2
            a[1] = max(a[1], b[1])
            lines.remove(b)
            merged = True
            break
    # przecinki, kropki, cudzysłowy mają inne pudełka niż litery – dołącz je do wiersza obok
    small = re.compile(r'^[,.;:!?\'"’”„«»…\-–]+$')
    main = [l for l in lines if not small.match("".join(c[4] for c in l[2]))]
    for l in lines:
        if l in main or not main:
            continue
        lx = (min(c[0] for c in l[2]) + max(c[2] for c in l[2])) / 2
        cover = [m for m in main if min(c[0] for c in m[2]) - 3 <= lx <= max(c[2] for c in m[2]) + 3]
        near = min(cover or main, key=lambda m: abs(m[0] - l[0]))
        if abs(near[0] - l[0]) < 1.3 * max(near[1], 4):
            near[2].extend(l[2])
        else:
            main.append(l)
    out = []
    for yc, h, cs in main:
        cs.sort(key=lambda c: c[0])
        hs = sorted(c[3] - c[1] for c in cs if c[4].isalnum()) or sorted(c[3] - c[1] for c in cs)
        out.append((yc, hs[len(hs) // 2], cs))
    out.sort(key=lambda l: -l[0])
    return out


def _chunks(line, segs):
    """Wiersz → sylaby [(x0, x1, tekst, czy_dywiz_po)]: przerwa między znakami = nowa sylaba;
    dywiz (znak '-' albo krótka kreska rysowana przez MuseScore) = dalsza część słowa."""
    yc, h, cs = line
    parts, cur = [], [cs[0]]
    for c in cs[1:]:
        if c[0] - cur[-1][2] > 0.22 * h and not (c[4] in ',.;:!?…' and c[0] - cur[-1][2] < 1.2 * h):
            parts.append(cur)
            cur = [c]
        else:
            cur.append(c)
    parts.append(cur)
    out = []
    for p in parts:
        txt = "".join(c[4] for c in p)
        out.append([p[0][0], p[-1][2], txt, False])
    # znak '-' jako osobna „sylaba” albo na końcu sylaby
    merged = []
    for ch in out:
        if ch[2] in ('-', '–', '‐') and merged:
            merged[-1][3] = True
            continue
        if len(ch[2]) > 1 and ch[2][-1] in '-‐' and ch[2][-2].isalpha():
            ch[2] = ch[2][:-1]
            ch[3] = True
        merged.append(ch)
    # kreski rysowane między sylabami (także na końcu wiersza, gdy słowo przechodzi do następnego systemu)
    for k, a in enumerate(merged):
        if a[3]:
            continue
        right = merged[k + 1][0] + 0.5 if k + 1 < len(merged) else a[1] + 4 * h
        for x0, x1, y, th in segs:
            if x0 >= a[1] - 0.5 and x1 <= right and (x1 - x0) < 3.5 * h and \
                    yc - 0.6 * h <= y <= yc + 0.5 * h:
                a[3] = True
                break
    return merged


_META = re.compile(r'(?i)^(sł\.?|muz\.?|słowa|muzyka|opr\.?|oprac|tekst|melodia|©|copyright|www\.|http|'
                   r'tempo|sopran|alt|tenor|bas|organy|s\.?\s*a\.?|t\.?\s*b\.?|ref\.?$|refren$)')


RE_CHORD = re.compile(r"^\(?[A-Ha-h](is|es|s|#|b)?(m|moll|maj|dim|aug|sus|add)?\d{0,2}(/[A-Ha-h](is|es|#|b)?)?\)?$")


def _clean_lyric_line(ln):
    """Usuń z wiersza sylab akordy (A7, fis, D/C), numery taktów i znaki tempa; None gdy to wiersz akordów."""
    if not ln:
        return ln
    bad = sum(1 for ch in ln if RE_CHORD.match(ch[2]) or re.fullmatch(r"\d{1,3}", ch[2]) or "=" in ch[2])
    if bad >= max(2, 0.5 * len(ln)):
        return None
    return [ch for ch in ln if not re.fullmatch(r"\d{1,3}", ch[2]) and not (RE_CHORD.match(ch[2]) and len(ch[2]) > 1
                                                                           and ch[2][0].isupper() and ch[2] not in ("Ach",))]


def read_score_pdf(path, pages=None, extra_text=True, skip=()):
    """Słowa z PDF z nutami. Zwraca słownik pieśni albo None, gdy to nie wygląda na nuty.
    pages – numery stron (od 0) do odczytu; extra_text – dołącz zwykły tekst spod nut (dalsze zwrotki)."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(path)
    blocks, title, title_h, n_staves, extra = [], "", 0, 0, []
    for pi in (pages if pages is not None else range(len(doc))):
        top_lim, bot_lim = 1e9, -1e9
        if isinstance(pi, (tuple, list)):                # (strona, góra, dół) – tylko fragment strony
            pi, top_lim, bot_lim = pi
        page = doc[pi]
        pw, ph = page.get_width(), page.get_height()
        chars, segs, staves = _pdf_page_items(page)
        tp = page.get_textpage()
        staves = [st for st in staves if st[0] < top_lim and st[1] > bot_lim]
        n_staves += len(staves)
        lines = [l for l in _text_lines(chars) if bot_lim < l[0] < top_lim]
        if pi == 0:
            top = [l for l in lines if not staves or l[0] > staves[0][0]]
            if top:
                big = max(top, key=lambda l: l[1])
                title, title_h = _line_text(big, tp), big[1]
        used = set()
        if not staves:
            # strona bez nut – dalsze zwrotki zapisane zwykłym tekstem
            extra += [t for t in (_line_text(l, tp) for l in lines if pi > 0 or pages is not None)
                      if t and not re.fullmatch(r'\d{1,3}', t) and t not in skip]
            continue
        # wiersze sylab pod każdą pięciolinią (do następnej pięciolinii)
        for si, (stop, sbot) in enumerate(staves):
            nxt = staves[si + 1][0] if si + 1 < len(staves) else -1e9
            under = [l for l in lines if nxt < l[0] < sbot - 1]
            under = [l for l in under if not _META.match("".join(c[4] for c in l[2]).strip())]
            if not under:
                continue
            # tylko wiersze tuż pod pięciolinią, zwarte (zwrotki jedna pod drugą)
            block, prev = [], sbot
            for l in under:
                if prev - l[0] > 3.2 * max(l[1], 4) and block:
                    break
                if len(l[2]) >= 2:
                    block.append(l)
                    used.add(id(l))
                prev = l[0]
            if block:
                cl = [_clean_lyric_line(_chunks(l, segs)) for l in block]
                cl = [c for c in cl if c]
                if cl:
                    blocks.append(cl)
        # tekst pod ostatnią pięciolinią strony, który nie jest sylabami (np. dalsze zwrotki, „2. …”)
        last_bot = staves[-1][1]
        below = [l for l in lines if l[0] < last_bot - 1 and id(l) not in used]
        below_text = [_line_text(l, tp) for l in below]
        below_text = [t for t in below_text if t and not re.fullmatch(r'\d{1,3}', t) and not _META.match(t)
                      and t not in skip]
        if len(below_text) >= 2 and extra_text:        # pojedynczy napis (np. stopka) – pomiń
            extra += below_text
    doc.close()
    if n_staves == 0 or not blocks:
        return None
    # ta sama treść pod kilkoma pięcioliniami (np. sopran i alt) – zostaw raz
    uniq, prev_key = [], None
    for b in blocks:
        key = tuple(tuple(ch[2] for ch in ln) for ln in b)
        if key != prev_key:
            uniq.append(b)
        prev_key = key
    # zdarzenia: sylaby z różnych zwrotek w tej samej kolumnie (pod tą samą nutą)
    events = []
    in_ref = [False]
    for b in uniq:
        cols = []                                 # [(x_środek, {zwrotka: (sylaba, koniec)})]
        for vi, ln in enumerate(b):
            v = vi
            if ln and re.fullmatch(r'\d{1,2}\.', ln[0][2]):   # numer zwrotki na początku
                v = int(ln[0][2][:-1]) - 1
                ln = ln[1:]
                in_ref[0] = False
            elif ln and re.match(r'(?i)^(ref(ren)?\.?:?|r\.:?)$', ln[0][2]):   # „Ref.:” przed sylabami refrenu
                in_ref[0] = True
                ln = ln[1:]
            if in_ref[0] and vi == 0:
                v = 'R'
            for x0, x1, txt, hyph in ln:
                xc = (x0 + x1) / 2
                for col in cols:
                    if abs(col[0] - xc) < max(4.0, (x1 - x0) * 0.6):
                        col[1].setdefault(v, (txt, not hyph))
                        break
                else:
                    cols.append([xc, {v: (txt, not hyph)}])
        cols.sort(key=lambda c: c[0])
        events += [c[1] for c in cols]
    if not events:
        return None
    song = events_to_song(events, title.strip() or os.path.splitext(os.path.basename(path))[0])
    song['dopisek'] = "\n".join(extra).strip()
    return song


# ---------------------------------------------------------------------
# Śpiewnik w PDF (wiele pieśni z nutami, np. śpiewnik oazowy)
# ---------------------------------------------------------------------

RE_CREDITS = re.compile(r"(?i)(^|\s)((t|m|sł|muz|tł|opr|sł\. i muz|t\. i m|m\. i t)\.\s*:|(t|m)\.\s*:?\s*i\s*(t|m)\.\s*:?|"
                        r"(t|m)\.\s*:?\s*(wg|ks\.|s\.|o\.)|tł\.\s)")
RE_TEMPO = re.compile(r"^[=♩\s\d.,]+$|^=\s*\d+")


def _fsize(line):
    """Stopień pisma wiersza (mediana „luźnych” wysokości znaków)."""
    v = sorted(c[5] if len(c) > 5 else c[3] - c[1] for c in line[2])
    return v[len(v) // 2] if v else 0


def _is_chord_line(t):
    w = t.replace("(", " ").replace(")", " ").split()
    return bool(w) and sum(1 for x in w if RE_CHORD.match(x) or re.fullmatch(r"\d{1,3}\.?|[-–]", x)) >= 0.7 * len(w)


PART_TAGS = [(("wejści",), "wejście"), (("przygotowanie dar", "ofiarowani"), "przygotowanie darów"),
             (("komuni",), "komunia"), (("uwielbieni", "dziękczynieni"), "uwielbienie"),
             (("rozesłani", "zakończeni", "wyjści"), "zakończenie")]


def songbook_pdf(path, progress=None):
    """Śpiewnik w PDF – kolejne pieśni z nutami (tytuł, autorzy, nuty ze słowami, dalsze zwrotki tekstem).
    Zwraca zbiór w formacie modul_zbior: {'piesni': [...], 'naglowek', 'kategoria'} albo None."""
    import pypdfium2 as pdfium
    from collections import Counter
    doc = pdfium.PdfDocument(path)
    n = len(doc)
    pages = []
    for pi in range(n):
        if progress:
            progress(pi, n)
        page = doc[pi]
        ph = page.get_height()
        chars, segs, staves = _pdf_page_items(page)
        lines = [(l, _line_text(l)) for l in _text_lines(chars)]
        pages.append({'h': ph, 'w': page.get_width(), 'staves': staves, 'lines': lines})
    doc.close()
    # nagłówki i stopki powtarzane na wielu stronach (żywa pagina, nazwa śpiewnika)
    edge = Counter()
    for pg in pages:
        for l, t in pg['lines']:
            if l[0] > pg['h'] * 0.9 or l[0] < pg['h'] * 0.08:
                edge[t] += 1
    running = {t for t, c in edge.items() if c >= max(3, n // 5)}
    book = next((t for t, c in edge.most_common() if t in running and re.search(r"(?i)śpiewnik", t)), "") or \
        (edge.most_common(1)[0][0] if running else "") or os.path.splitext(os.path.basename(path))[0]
    songs, cur, section, subsection = [], None, "", ""
    for pi, pg in enumerate(pages):
        staves = pg['staves']
        body = [(l, t) for l, t in pg['lines'] if t and t not in running and not re.fullmatch(r"\d{1,3}", t)]
        top_y = staves[0][0] if staves else -1
        head = [(l, t) for l, t in body if l[0] > top_y + 1] if len(staves) >= 2 else []
        head = [(l, re.sub(r"^=\s*\d+[.,]?\s+(?=\S)", "", t)) for l, t in head]
        head = [(l, t) for l, t in head if not RE_TEMPO.match(t) and not _is_chord_line(t)]
        title, credits, k_title = "", "", None
        for k, (l, t) in enumerate(head):
            m = RE_CREDITS.search(t)
            if m:
                before = t[:m.start()].strip(" ,;")
                credits = t[m.start():].strip()
                if before and len(before) > 3:
                    title, k_title = before, k
                elif k > 0:
                    title, k_title = head[k - 1][1], k - 1
                break
        if not title and head:
            # bez autorów – największy napis tuż nad nutami
            cand = [(k, l, t) for k, (l, t) in enumerate(head) if len(t) > 3]
            if cand:
                k, l, t = max(cand, key=lambda c: (c[1][1], c[0]))
                title, k_title = t, k
        if title:
            th = head[k_title][0][1]
            def centred(l):
                x0, x1 = min(c[0] for c in l[2]), max(c[2] for c in l[2])
                return abs((x0 + x1) / 2 - pg['w'] / 2) < 0.08 * pg['w']
            def is_head(l, t):
                return (centred(l) and l[1] >= 0.7 * th and len(t) <= 40 and not RE_CREDITS.search(t)
                        and not re.match(r"\d{1,2}\.", t) and not re.search(r"[,.;:!?]$", t))
            heads = [(l, t) for l, t in head[:k_title] if is_head(l, t)]
            first_head = min((k for k, (l, t) in enumerate(head[:k_title]) if is_head(l, t)), default=k_title)
            if cur is not None:                     # koniec poprzedniej pieśni nad nowym tytułem
                cur['more'] += [t for l, t in head[:first_head] if not RE_CREDITS.search(t)]
            big = [k for k, (l, t) in enumerate(heads) if l[1] >= 1.1 * th]
            if big:
                section = heads[big[-1]][1]
                subsection = " – ".join(t for l, t in heads[big[-1] + 1:])
            elif heads:
                subsection = heads[-1][1]
            title = re.sub(r"\s+", " ", title).strip(" .,")
            cur = {'title': title, 'credits': credits, 'pages': [pi], 'section': section,
                   'subsection': subsection, 'skip': {t for l, t in head}, 'more': [], 'title_fs': _fsize(head[k_title][0])}
            songs.append(cur)
        elif cur is not None and (len(staves) >= 2 or len(body) >= 2):
            cur['pages'].append(pi)                 # ciąg dalszy pieśni (nuty albo zwrotki)
        # kolejne pieśni na tej samej stronie: tytuł + autorzy („t.: … m.: …”) niżej, między nutami
        if cur is None or len(staves) < 1:
            continue
        ref_h = cur.get('title_fs') or 12
        below = [(l, t) for l, t in body if l[0] < top_y - 1]
        taken = set()
        for k, (l, t) in enumerate(below):
            m = RE_CREDITS.search(t)
            cred = ""
            if m and (m.start() <= 2 or t[:m.start()].strip()):
                before = t[:m.start()].strip(" ,;")
                cred = t[m.start():].strip()
                if before and len(before) > 3 and _fsize(l) >= 0.85 * ref_h:
                    tl = l
                elif k > 0 and _fsize(below[k - 1][0]) >= 0.85 * ref_h and below[k - 1][0][0] - l[0] < 3 * ref_h \
                        and not RE_CREDITS.search(below[k - 1][1]) and not _is_chord_line(below[k - 1][1]) \
                        and k - 1 not in taken:
                    tl, before = below[k - 1][0], below[k - 1][1]
                else:
                    continue
            elif (_fsize(l) >= 0.9 * ref_h and len(t) > 3 and not _is_chord_line(t) and not RE_TEMPO.match(t)
                  and not re.match(r"\d{1,2}\.", t) and k not in taken
                  and not (k + 1 < len(below) and RE_CREDITS.search(below[k + 1][1]))
                  and any(0 < l[0] - st[0] < 4 * ref_h for st in staves)):
                tl, before = l, t                      # tytuł bez autorów, tuż nad nutami
            else:
                continue
            taken.add(k)
            if k > 0 and tl is below[k - 1][0]:
                taken.add(k - 1)
            y = tl[0] + tl[1]                      # granica: tuż nad tytułem
            # poprzednia pieśń kończy się nad tym tytułem
            last = cur['pages'][-1]
            if isinstance(last, tuple) and last[0] == pi:
                cur['pages'][-1] = (pi, last[1], y)
            elif last == pi:
                cur['pages'][-1] = (pi, 1e9, y)
            cur = {'title': re.sub(r"\s+", " ", before).strip(" .,"), 'credits': cred,
                   'pages': [(pi, y, -1e9)], 'section': section, 'subsection': subsection,
                   'skip': {before, t}, 'more': [], 'title_fs': _fsize(tl)}
            songs.append(cur)
    out = []
    for i, sg in enumerate(songs):
        if progress:
            progress(n + i, n + len(songs))
        song = read_score_pdf(path, pages=sg['pages'], skip=running | sg['skip'])
        ref, verses = "", []
        if song:
            ref = song.get('refren', '')
            verses = list(song.get('zwrotki', []))
            extra = "\n".join([song.get('dopisek', '')] + sg['more'])
            if extra:
                cur_v = None
                for line in extra.splitlines():
                    line = line.strip()
                    if not line or line in sg['skip'] or RE_CREDITS.match(line):
                        continue
                    cm = re.search(r"(?i)(^|\s)(t|m|opr)\.\s*:", line)
                    if cm:                              # autorzy wtrąceni w tekst (np. „Tropy m.: I. Pawlak”)
                        line = line[:cm.start()].strip()
                        if not line:
                            continue
                    m = re.match(r"^(\d{1,2})\.\s*(.*)", line)
                    r = re.match(r"(?i)^(ref(ren)?\.?:?|r\.:)\s*(.*)", line)
                    if m:
                        cur_v = [f"{m.group(1)}. {m.group(2)}"]
                        verses.append(cur_v)
                    elif r and not ref:
                        cur_v = None
                        ref = r.group(3)
                    elif cur_v is not None:
                        cur_v.append(line)
                    elif verses and isinstance(verses[-1], list):
                        verses[-1].append(line)
                    else:
                        cur_v = [line]
                        verses.append(cur_v)
        texts = []
        for k, v in enumerate(verses):
            if isinstance(v, list):
                texts.append("\n".join(v))
            else:
                texts.append(v if re.match(r"\d{1,2}\.", v) or len(verses) == 1 else f"{k + 1}. {v}")
        pnums = list(dict.fromkeys(p[0] if isinstance(p, tuple) else p for p in sg['pages']))
        uw = [f"{book}, s. {pnums[0] + 1}"]
        if sg['section'] or sg['subsection']:
            uw.append(" – ".join(x for x in (sg['section'], sg['subsection']) if x))
        if sg['credits']:
            uw.append(sg['credits'])
        if not ref and not any(str(t).strip() for t in texts):
            uw.append("słów nie odczytano – nuty są obrazkiem; tekst w załączniku PDF")
        import modul_zbior as zb
        cat = zb.guess_category(sg['title']) or zb.guess_category(sg['subsection'])
        if not cat and "części stałe" in sg['section'].lower():
            cat = "Części stałe Mszy"
        low = (sg['subsection'] + " " + sg['section']).lower()
        tags = [tag for words, tag in PART_TAGS if any(w in low for w in words)]
        tl = sg['title'].lower()
        tags += [tag for w, tag in (("kyrie", "kyrie"), ("zmiłuj się", "kyrie"), ("alleluja", "alleluja"),
                                    ("psalm", "psalm"), ("święty", "sanctus"), ("baranku", "agnus dei"))
                 if w in tl and tag not in tags]
        out.append({'title': sg['title'], 'refren': ref, 'zwrotki_raw': "\n\n".join(t for t in texts if t.strip()),
                    'uwagi': " | ".join(uw), 'kategoria': cat, 'tagi': ", ".join(tags), 'youtube': '',
                    'numer': str(pnums[0] + 1), 'pdf': path, 'strony': pnums,
                    'czesc_mszy': " ".join((sg['section'], sg['subsection']))})
    if not out:
        return None
    return {'piesni': out, 'naglowek': book, 'kategoria': ''}


_THUMBS = {}


def pdf_pages_bytes(path, pages):
    """Wybrane strony PDF jako nowy plik (bajty) – nuty pieśni do załącznika.
    Olbrzymie obrazki (np. ikonka głośnika 8000×8000 px) są zmniejszane, żeby plik nie ważył kilkunastu MB."""
    import io
    import pypdfium2 as pdfium
    src = pdfium.PdfDocument(path)
    doc = pdfium.PdfDocument.new()
    doc.import_pages(src, list(pages))
    for pg in doc:
        changed = False
        for o in pg.get_objects(max_depth=4):
            if o.type != 3:                                   # FPDF_PAGEOBJ_IMAGE
                continue
            try:
                meta = o.get_metadata()
                if max(meta.width, meta.height) <= 1600:
                    continue
                key = (path, meta.width, meta.height, getattr(meta, 'bits_per_pixel', 0))
                im = _THUMBS.get(key)
                if im is None:
                    im = o.get_bitmap(render=True).to_pil()
                    im.thumbnail((600, 600))
                    _THUMBS[key] = im
                o.set_bitmap(pdfium.PdfBitmap.from_pil(im.convert("RGB")), pages=[pg])
                changed = True
            except Exception:
                pass
        if changed:
            pg.gen_content()
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    src.close()
    try:                                                      # przepisz – bez osieroconych dużych obiektów
        from pypdf import PdfReader, PdfWriter
        w = PdfWriter(clone_from=PdfReader(io.BytesIO(buf.getvalue())))
        out = io.BytesIO()
        w.write(out)
        if len(out.getvalue()) < len(buf.getvalue()):
            return out.getvalue()
    except Exception:
        pass
    return buf.getvalue()


def looks_like_songbook(path):
    """PDF z kilkoma pieśniami z nutami? (≥ 3 strony z pięcioliniami i ≥ 2 tytuły z autorami)."""
    try:
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(path)
        n = len(doc)
        if n < 3:
            doc.close()
            return False
        music = cred = 0
        for pi in range(min(n, 40)):
            chars, segs, staves = _pdf_page_items(doc[pi])
            if len(staves) >= 2:
                music += 1
                if any(RE_CREDITS.search(_line_text(l)) for l in _text_lines(chars) if l[0] > staves[0][0]):
                    cred += 1
        doc.close()
        return music >= 3 and cred >= 2
    except Exception:
        return False


def _line_text(line, tp=None):
    """Wiersz zwykłego tekstu (nie sylaby): znaki → słowa (ze spacjami z pliku PDF, gdy są)."""
    yc, h, cs = line
    plain = "".join(c[4] for c in cs)
    if tp is not None:
        t = tp.get_text_bounded(left=min(c[0] for c in cs) - 0.5, bottom=min(c[1] for c in cs) - 0.5,
                                right=max(c[2] for c in cs) + 0.5, top=max(c[3] for c in cs) + 0.5)
        t = re.sub(r'[\ue000-\uf8ff]', '', re.sub(r'\s+', ' ', t or '')).strip()
        if t and t.replace(" ", "") == plain.replace(" ", ""):
            return t
    out = ""
    for k, c in enumerate(cs):
        if k and c[0] - cs[k - 1][2] > 0.22 * h and c[4] not in ',.;:!?…':
            out += " "
        out += c[4]
    return out.strip()


# ---------------------------------------------------------------------

def lyrics_from_file(path):
    """Słowa z pliku nut → słownik pieśni. Dla PDF bez nut zwraca None."""
    ext = os.path.splitext(path)[1].lower()
    if ext in ('.mscz', '.mscx'):
        return read_mscx(path)
    if ext in ('.musicxml', '.xml', '.mxl'):
        return read_musicxml(path)
    if ext in ('.mid', '.midi', '.kar'):
        return read_midi(path)
    if ext == '.pdf':
        return read_score_pdf(path)
    raise RuntimeError("Nieobsługiwany rodzaj pliku nut.")


if __name__ == '__main__':
    import sys
    for p in sys.argv[1:]:
        s = lyrics_from_file(p)
        print("=" * 20, p)
        print(song_to_text(s) if s else "(to nie wygląda na nuty)")
