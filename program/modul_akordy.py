#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Liber Canticorum – akordy do pieśni (widok dla gitarzystów).

Zapis akordów: ChordPro w wierszach tekstu – „[a]Chwalcie [E]Pana” – akord stoi przed sylabą, nad którą
się go gra. Akordy wypisane z boku wiersza (jak w wielu śpiewnikach) zapisuje się po znaku „‖”:
„Pozdrawiam Ciebie, Matko ‖ D e / A D”. Polska notacja: H i B, molowe małą literą (a, e, fis),
krzyżyki „is”, bemole „es”; angielska (B, Bb, Am) też jest rozumiana.

Licencja: GPL-3.0-or-later.
"""
import html as H
import re

SIDE = "‖"
NOTES_PL = ["C", "Cis", "D", "Dis", "E", "F", "Fis", "G", "Gis", "A", "B", "H"]
NOTES_PL_FLAT = ["C", "Des", "D", "Es", "E", "F", "Ges", "G", "As", "A", "B", "H"]
NOTES_EN = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "Bb", "B"]
NOTES_EN_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
_BASE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "H": 11, "B": 10}

RE_CHORD = re.compile(r"^(?P<root>[A-Ha-h])(?P<acc>is|es|s|#|b(?![a-z]))?(?P<rest>(m(?!aj)|moll)?(maj|dim|aug|sus|add)?"
                      r"\d{0,2}[+\-]?(maj|sus|add)?\d{0,2}[+\-]?(/\d{1,2})?)(/(?P<bass>[A-Ha-h](is|es|s|#|b)?))?$")
RE_TOKEN = re.compile(r"^[(\[]*(.+?)[)\]]*[.,…]*$")
RE_REPEAT = re.compile(r"^(/?\s*x\s?\d+|/x\d+|\d\s?x|/|\(bis\)|bis|\.\.\.|…|–|-|\||\(|\))$", re.I)


def is_chord(tok):
    m = RE_TOKEN.match(tok.strip())
    return bool(m and RE_CHORD.match(m.group(1)))


def is_chord_line(line):
    """Wiersz złożony z samych akordów (i znaków powtórzeń: /x2, (bis), …)."""
    toks = [t for t in re.split(r"\s+", line.replace("/", " / ")) if t]
    if not toks:
        return False
    chords = [t for t in toks if is_chord(t)]
    return bool(chords) and all(is_chord(t) or RE_REPEAT.match(t) or re.fullmatch(r"[(\[]?\d{1,2}[)\]]?", t)
                                for t in toks)


def _semi(root, acc, en=False):
    n = _BASE[root.upper()]
    if root.upper() == "B":
        n = 11 if en else 10           # angielskie B = polskie H; polskie B = b
    if acc in ("is", "#"):
        n += 1
    elif acc in ("es", "s", "b"):
        n -= 1
    return n % 12


def _name(n, minor, flat=False, en=False):
    names = (NOTES_EN_FLAT if flat else NOTES_EN) if en else (NOTES_PL_FLAT if flat else NOTES_PL)
    s = names[n % 12]
    return s.lower() if minor and not en else s


def transpose_chord(ch, k, flat=False):
    """Akord przesunięty o k półtonów (zachowuje zapis: małe = moll, sufiksy, bas po „/”)."""
    m = RE_CHORD.match(ch)
    if not m or k % 12 == 0:
        return ch
    root, acc, rest, bass = m.group('root'), m.group('acc') or "", m.group('rest') or "", m.group('bass')
    en = acc in ("#", "b") or "m" in rest[:1] and root.isupper()
    minor = root.islower()
    out = _name(_semi(root, acc, en) + k, minor, flat or (en and acc == "b"), en) + rest
    if bass:
        b = re.match(r"([A-Ha-h])(is|es|s|#|b)?", bass)
        out += "/" + _name(_semi(b.group(1), b.group(2) or "", en) + k, b.group(1).islower(), flat, en)
    return out


def transpose_token(tok, k, flat=False):
    m = re.match(r"^([(\[]*)(.+?)([)\]]*[.,…]*)$", tok)
    if not m or not RE_CHORD.match(m.group(2)):
        return tok
    return m.group(1) + transpose_chord(m.group(2), k, flat) + m.group(3)


def transpose_text(text, k, flat=False):
    """Cały tekst ChordPro przesunięty o k półtonów."""
    def inline(m):
        return "[" + " ".join(transpose_token(t, k, flat) for t in m.group(1).split()) + "]"
    out = []
    for line in (text or "").splitlines():
        body, sep, side = line.partition(SIDE)
        body = re.sub(r"\[([^\]]+)\]", inline, body)
        if sep:
            side = " ".join(transpose_token(t, k, flat) for t in side.split(" "))
        out.append(body + sep + side)
    return "\n".join(out)


def strip_chords(text):
    """ChordPro → sam tekst (do slajdów)."""
    out = []
    for line in (text or "").splitlines():
        line = line.split(SIDE)[0]
        line = re.sub(r"\[[^\]]*\]", "", line)
        out.append(re.sub(r"[ \t]+$", "", line))
    return "\n".join(out)


def has_chords(text):
    return bool(re.search(r"\[[A-Ha-h][^\]]*\]", text or "")) or SIDE in (text or "")


# ---------------------------------------------------------------------
# akordy nad tekstem (zwykły tekst) → ChordPro
# ---------------------------------------------------------------------

def _insert_at(line, chords):
    """chords: [(kolumna_znaku, akord)] – wstawia [akord] przed znakiem (dopełnia spacjami, gdy wiersz krótszy)."""
    out = line
    for col, ch in sorted(chords, key=lambda c: -c[0]):
        if col > len(out):
            out = out + " " * (col - len(out))
        out = out[:col] + f"[{ch}]" + out[col:]
    return out


def chord_lines_to_chordpro(text):
    """Tekst z wierszami akordów nad wierszami słów (układ kolumnowy, np. z kopiowania śpiewnika)
    → ChordPro. Wiersze bez akordów zostają bez zmian."""
    lines = (text or "").splitlines()
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if is_chord_line(ln) and i + 1 < len(lines) and lines[i + 1].strip() and not is_chord_line(lines[i + 1]):
            chords = [(m.start(), m.group(0)) for m in re.finditer(r"\S+", ln) if is_chord(m.group(0))]
            out.append(_insert_at(lines[i + 1], chords))
            i += 2
            continue
        if is_chord_line(ln):
            out.append(" ".join(f"[{t}]" if is_chord(t) else t for t in ln.split()))
        else:
            out.append(ln)
        i += 1
    return "\n".join(out)


def split_side_chords(line):
    """„tekst   D e / A D” (akordy na końcu wiersza) → („tekst”, „D e / A D”)."""
    toks = line.rstrip().split(" ")
    k = len(toks)
    while k > 0 and toks[k - 1] and (is_chord(toks[k - 1]) or RE_REPEAT.match(toks[k - 1])):
        k -= 1
    tail = " ".join(t for t in toks[k:] if t)
    if k < len(toks) and any(is_chord(t) for t in toks[k:]) and k > 0:
        return " ".join(toks[:k]).rstrip(), tail
    return line, ""


_GLUED = re.compile(r"[A-Ha-h](?:is|es|s(?!us)|#|b(?![a-z]))?(?:m(?!aj)|moll)?(?:maj7|maj|dim|aug|sus[24]?|add9|7\+|[2-9]|11|13|\+)*")


def split_glued(tok):
    """„FBad” → [F, B, a, d] (akordy zapisane bez spacji, np. z importu PDF); inaczej [tok]."""
    if is_chord(tok) or len(tok) < 2:
        return [tok]
    out, i = [], 0
    while i < len(tok):
        m = _GLUED.match(tok, i)
        if not m or m.end() == i:
            return [tok]
        out.append(tok[i:m.end()])
        i = m.end()
    return out if all(is_chord(t) for t in out) else [tok]


def side_html(side):
    """Akordy boczne z wyraźnymi odstępami: „F B a d / g C F”."""
    toks = []
    for t in re.split(r"\s+", side.replace("/", " / ")):
        if t:
            toks += split_glued(t)
    sep = "&nbsp;&nbsp;&nbsp;"
    return sep.join("<span style='color:#999'>/</span>" if t == "/" else H.escape(t) for t in toks)


# ---------------------------------------------------------------------
# widok
# ---------------------------------------------------------------------

def chordpro_html(title, text, k=0, size=16, flat=False, show=True, color="#b22222", lyrics_only=False):
    """HTML do wyświetlenia / druku: akordy nad sylabami (kolorem), akordy boczne w prawej kolumnie."""
    if k:
        text = transpose_text(text, k, flat)
    css = (f"body{{font-family:'DejaVu Sans',Arial,sans-serif;font-size:{size}px;}}"
           f"h2{{font-size:{int(size * 1.4)}px;margin:0 0 .6em 0;}}"
           f".c{{color:{color};font-weight:bold;}}")
    rows = [f"<h2>{H.escape(title or '')}</h2>"]
    rows.append("<table cellspacing='0' cellpadding='0' width='100%'>")
    for line in (text or "").splitlines():
        body, _, side = line.partition(SIDE)
        side = side.strip()
        if not body.strip() and not side:
            rows.append(f"<tr><td style='font-size:{size // 2}px'>&nbsp;</td></tr>")
            continue
        parts = re.split(r"(\[[^\]]*\])", body)
        if not show or lyrics_only or len(parts) == 1:
            txt = H.escape(re.sub(r"\[[^\]]*\]", "", body)) or "&nbsp;"
            rows.append(f"<tr><td style='white-space:pre'>{txt}</td>" +
                        (f"<td align='center' width='100%' class='c' style='white-space:pre'>{side_html(side)}</td>"
                         if show and side and not lyrics_only else "<td width='100%'></td>") + "</tr>")
            continue
        # wiersz z akordami nad sylabami: tabela wewnętrzna – akord w górnym wierszu nad swoim kawałkiem tekstu
        cells_top, cells_bot = [], []
        pending = ""
        for p in parts:
            if p.startswith("[") and p.endswith("]"):
                if pending:
                    cells_top.append(pending)
                    cells_bot.append("")
                pending = p[1:-1]
                continue
            if p == "" and not pending:
                continue
            cells_top.append(pending)
            cells_bot.append(p)
            pending = ""
        if pending:
            cells_top.append(pending)
            cells_bot.append("")
        inner = "<table cellspacing='0' cellpadding='0'><tr>" + "".join(
            f"<td class='c' style='white-space:pre;padding-right:{3 if t else 0}px'>{H.escape(t) or '&nbsp;'}</td>"
            for t in cells_top) + "</tr><tr>" + "".join(
            f"<td style='white-space:pre'>{H.escape(b) or '&nbsp;'}</td>" for b in cells_bot) + "</tr></table>"
        rows.append(f"<tr><td>{inner}</td>" +
                    (f"<td align='center' width='100%' class='c' style='white-space:pre'>{side_html(side)}</td>"
                     if side else "<td width='100%'></td>")
                    + "</tr>")
    rows.append("</table>")
    return f"<html><head><style>{css}</style></head><body>{''.join(rows)}</body></html>"


def song_chordpro(song):
    """Tekst z akordami pieśni albo – gdy nie ma – sam tekst (refren i zwrotki)."""
    if (song.get('akordy') or '').strip():
        return song['akordy']
    out = []
    if song.get('refren'):
        out.append("Ref.: " + song['refren'])
    if song.get('zwrotki_raw'):
        out.append(song['zwrotki_raw'])
    return "\n\n".join(out)


try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QCheckBox, QPushButton,
                                   QTextBrowser, QFileDialog, QMessageBox)
    from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument
    from PySide6.QtCore import QMarginsF
except ImportError:                                   # pragma: no cover
    QDialog = object


class ChordView(QDialog):
    """Widok dla gitarzystów: tekst z akordami, transpozycja, wielkość pisma, druk / PDF."""

    def __init__(self, songs, parent=None, start=0):
        super().__init__(parent)
        self.songs, self.idx = songs, start
        self.setWindowTitle("Akordy – widok dla gitarzystów")
        self.resize(820, 900)
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.prev_b = QPushButton("◀")
        self.prev_b.clicked.connect(lambda: self.go(-1))
        self.next_b = QPushButton("▶")
        self.next_b.clicked.connect(lambda: self.go(1))
        bar.addWidget(self.prev_b)
        bar.addWidget(self.next_b)
        bar.addWidget(QLabel("Transpozycja:"))
        self.tr = QSpinBox()
        self.tr.setRange(-11, 11)
        self.tr.setSuffix(" półt.")
        self.tr.valueChanged.connect(self.render)
        bar.addWidget(self.tr)
        self.flat = QCheckBox("bemole")
        self.flat.toggled.connect(self.render)
        bar.addWidget(self.flat)
        bar.addWidget(QLabel("Pismo:"))
        self.size = QSpinBox()
        self.size.setRange(10, 48)
        self.size.setValue(18)
        self.size.valueChanged.connect(self.render)
        bar.addWidget(self.size)
        self.show_c = QCheckBox("akordy")
        self.show_c.setChecked(True)
        self.show_c.toggled.connect(self.render)
        bar.addWidget(self.show_c)
        from PySide6.QtCore import QSettings
        self._qs = QSettings("LiberCanticorum", "LiberCanticorum")
        self.show_g = QCheckBox("chwyty")
        self.show_g.setToolTip("Chwyty akordów na gryfie gitary")
        self.show_g.setChecked(self._qs.value("chord_grips", "true") == "true")
        self.show_g.toggled.connect(lambda on: (self._qs.setValue("chord_grips", on), self.render()))
        bar.addWidget(self.show_g)
        bar.addStretch(1)
        b = QPushButton("Zapisz PDF…")
        b.clicked.connect(self.save_pdf)
        bar.addWidget(b)
        b = QPushButton("Pełny ekran")
        b.clicked.connect(lambda: self.showNormal() if self.isFullScreen() else self.showFullScreen())
        bar.addWidget(b)
        lay.addLayout(bar)
        from modul_instrumenty import ChordStrip
        self.strip = ChordStrip()
        lay.addWidget(self.strip)
        self.view = QTextBrowser()
        lay.addWidget(self.view, 1)
        self.info = QLabel()
        self.info.setStyleSheet("color: gray;")
        lay.addWidget(self.info)
        self.render()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Right, Qt.Key_PageDown, Qt.Key_Space):
            self.go(1)
        elif e.key() in (Qt.Key_Left, Qt.Key_PageUp):
            self.go(-1)
        elif e.key() in (Qt.Key_Plus, Qt.Key_Equal):
            self.tr.setValue(self.tr.value() + 1)
        elif e.key() == Qt.Key_Minus:
            self.tr.setValue(self.tr.value() - 1)
        else:
            super().keyPressEvent(e)

    def go(self, d):
        if 0 <= self.idx + d < len(self.songs):
            self.idx += d
            self.tr.blockSignals(True)
            self.tr.setValue(0)
            self.tr.blockSignals(False)
            self.render()

    def html(self, song):
        return chordpro_html(song.get('title', ''), song_chordpro(song), self.tr.value(), self.size.value(),
                             self.flat.isChecked(), self.show_c.isChecked())

    def render(self, *_):
        if not self.songs:
            return
        s = self.songs[self.idx]
        self.view.setHtml(self.html(s))
        try:
            from modul_instrumenty import song_chords
            names = song_chords(song_chordpro(s), self.tr.value(), self.flat.isChecked())
            self.strip.set_chords(names)
            self.strip.setVisible(self.show_g.isChecked() and bool(names))
        except Exception as e:
            self.strip.setVisible(False)
            print("Chwyty:", e)
        self.prev_b.setEnabled(self.idx > 0)
        self.next_b.setEnabled(self.idx < len(self.songs) - 1)
        has = has_chords(s.get('akordy', ''))
        self.info.setText((f"{self.idx + 1} / {len(self.songs)}   " if len(self.songs) > 1 else "") +
                          ("" if has else "Ta pieśń nie ma jeszcze akordów – dopisz je w zakładce „Akordy”. ") +
                          "Klawisze: ← → kolejna pieśń, + / − transpozycja.")

    def save_pdf(self):
        from PySide6.QtGui import QPdfWriter
        name = (self.songs[self.idx].get('title') if len(self.songs) == 1 else "akordy") or "akordy"
        path, _ = QFileDialog.getSaveFileName(self, "Zapisz akordy jako PDF", f"{name} – akordy.pdf", "PDF (*.pdf)")
        if not path:
            return
        save_pdf(path, self.songs, self.tr.value() if len(self.songs) == 1 else 0, self.size.value(),
                 self.flat.isChecked(), self.show_c.isChecked())
        QMessageBox.information(self, "Akordy", f"Zapisano: {path}")


def save_pdf(path, songs, k=0, size=14, flat=False, show=True):
    """Śpiewnik z akordami do PDF (A4), każda pieśń od nowej strony."""
    from PySide6.QtGui import QPdfWriter, QPainter
    w = QPdfWriter(path)
    w.setPageSize(QPageSize(QPageSize.A4))
    w.setPageMargins(QMarginsF(15, 12, 15, 12), QPageLayout.Millimeter)
    w.setResolution(96)
    p = QPainter(w)
    first = True
    for s in songs:
        doc = QTextDocument()
        doc.setHtml(chordpro_html(s.get('title', ''), song_chordpro(s), k, size, flat, show))
        doc.setPageSize(w.pageLayout().paintRectPixels(96).size().toSizeF())
        for pg in range(doc.pageCount()):
            if not first:
                w.newPage()
            first = False
            p.save()
            h = doc.pageSize().height()
            p.translate(0, -pg * h)
            from PySide6.QtCore import QRectF
            doc.drawContents(p, QRectF(0, pg * h, doc.pageSize().width(), h))
            p.restore()
    p.end()


def separate(text, min_lines=2):
    """Tekst z wierszami akordów nad słowami → (sam tekst, ChordPro) – gdy akordów brak: (tekst, "")."""
    lines = (text or "").splitlines()
    n = sum(1 for l in lines if is_chord_line(l))
    if n < min_lines:
        return text, ""
    plain = "\n".join(l for l in lines if not is_chord_line(l))
    return plain, chord_lines_to_chordpro(text)
