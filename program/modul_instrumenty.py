"""Widoki instrumentów – Liber Canticorum.

* Klawiatura – podświetla dźwięki grane w odtwarzaczu (kolory głosów).
* Chwyty gitarowe – diagramy akordów na gryfie (otwarte chwyty i barre w kształcie E / A).
"""
import re

try:
    from PySide6.QtCore import Qt, QRectF, QPointF, QSize
    from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics
    from PySide6.QtWidgets import QWidget, QHBoxLayout, QScrollArea, QSizePolicy
except ImportError:                                    # testy bez Qt
    QWidget = object

# ---------------------------------------------------------------------
# akordy → chwyty
# ---------------------------------------------------------------------
_BASE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "H": 11, "B": 10}
RE_NAME = re.compile(r"^(?P<root>[A-Ha-h])(?P<acc>is|es|s(?!us)|#|b(?![a-z]))?(?P<rest>[^/]*)(?:/(?P<bass>.+))?$")

# chwyty otwarte: struny od 6. (E) do 1. (e); -1 = nie grać
OPEN = {
    (0, 'maj'): [-1, 3, 2, 0, 1, 0], (0, '7'): [-1, 3, 2, 3, 1, 0], (0, 'maj7'): [-1, 3, 2, 0, 0, 0],
    (0, 'sus4'): [-1, 3, 3, 0, 1, 1], (0, '6'): [-1, 3, 2, 2, 1, 0], (0, 'add9'): [-1, 3, 2, 0, 3, 0],
    (2, 'maj'): [-1, -1, 0, 2, 3, 2], (2, 'min'): [-1, -1, 0, 2, 3, 1], (2, '7'): [-1, -1, 0, 2, 1, 2],
    (2, 'm7'): [-1, -1, 0, 2, 1, 1], (2, 'maj7'): [-1, -1, 0, 2, 2, 2], (2, 'sus4'): [-1, -1, 0, 2, 3, 3],
    (2, 'sus2'): [-1, -1, 0, 2, 3, 0], (2, '6'): [-1, -1, 0, 2, 0, 2],
    (4, 'maj'): [0, 2, 2, 1, 0, 0], (4, 'min'): [0, 2, 2, 0, 0, 0], (4, '7'): [0, 2, 0, 1, 0, 0],
    (4, 'm7'): [0, 2, 0, 0, 0, 0], (4, 'sus4'): [0, 2, 2, 2, 0, 0], (4, 'maj7'): [0, 2, 1, 1, 0, 0],
    (5, 'maj7'): [-1, -1, 3, 2, 1, 0],
    (7, 'maj'): [3, 2, 0, 0, 0, 3], (7, '7'): [3, 2, 0, 0, 0, 1], (7, 'maj7'): [3, 2, 0, 0, 0, 2],
    (7, '6'): [3, 2, 0, 0, 0, 0], (7, 'sus4'): [3, -1, 0, 0, 1, 3],
    (9, 'maj'): [-1, 0, 2, 2, 2, 0], (9, 'min'): [-1, 0, 2, 2, 1, 0], (9, '7'): [-1, 0, 2, 0, 2, 0],
    (9, 'm7'): [-1, 0, 2, 0, 1, 0], (9, 'maj7'): [-1, 0, 2, 1, 2, 0], (9, 'sus4'): [-1, 0, 2, 2, 3, 0],
    (9, 'sus2'): [-1, 0, 2, 2, 0, 0], (9, '6'): [-1, 0, 2, 2, 2, 2], (9, 'm6'): [-1, 0, 2, 2, 1, 2],
    (11, '7'): [-1, 2, 1, 2, 0, 2],
}
# kształty barre (przesunięcia od progu barre); None = nie grać
E_SHAPE = {'maj': [0, 2, 2, 1, 0, 0], 'min': [0, 2, 2, 0, 0, 0], '7': [0, 2, 0, 1, 0, 0], 'm7': [0, 2, 0, 0, 0, 0],
           'maj7': [0, None, 1, 1, 0, None], 'sus4': [0, 2, 2, 2, 0, 0], '9': [0, 2, 0, 1, 0, 2]}
A_SHAPE = {'maj': [None, 0, 2, 2, 2, 0], 'min': [None, 0, 2, 2, 1, 0], '7': [None, 0, 2, 0, 2, 0],
           'm7': [None, 0, 2, 0, 1, 0], 'maj7': [None, 0, 2, 1, 2, 0], 'sus4': [None, 0, 2, 2, 3, 0],
           'sus2': [None, 0, 2, 2, 0, 0], '6': [None, 0, 2, 2, 2, 2], 'm6': [None, 0, 2, 2, 1, 2],
           'dim': [None, 0, 1, 2, 1, None], 'dim7': [None, 0, 1, 2, 1, 2], 'aug': [None, 0, 3, 2, 2, None],
           'add9': [None, 0, 2, 4, 2, 0]}
QUALITY_NAMES = {'maj': "dur", 'min': "moll", '7': "septyma", 'm7': "moll z septymą", 'maj7': "wielka septyma",
                 'sus4': "kwarta zamiast tercji", 'sus2': "sekunda zamiast tercji", '6': "z sekstą", 'm6': "moll z sekstą",
                 'dim': "zmniejszony", 'dim7': "zmniejszony z septymą", 'aug': "zwiększony", 'add9': "z noną",
                 '9': "nona"}


def guess_english(names):
    """Notacja angielska (B = H, Am = a-moll)? Polska, gdy jest H albo małe litery dla moll."""
    if any(re.match(r"^[Hh]", n) for n in names):
        return False
    if any(re.match(r"^[a-g](?![a-z]*maj)", n) for n in names):
        return False
    return any(re.match(r"^[A-G](#|b(?![a-z]))", n) or re.match(r"^[A-G]m(?!aj)", n) for n in names)


def parse(name, en=False):
    """'a', 'Am', 'Fis-moll', 'D7', 'Hsus4', 'C/E', 'Bb' → (klasa wysokości, rodzaj) albo None."""
    m = RE_NAME.match(name.strip().replace('♯', '#').replace('♭', 'b'))
    if not m:
        return None
    root, acc, rest = m.group('root'), m.group('acc') or '', (m.group('rest') or '').lstrip('-').lower()
    pc = _BASE[root.upper()]
    if root.upper() == 'B':
        pc = 11 if en else 10
    pc = (pc + (1 if acc in ('is', '#') else -1 if acc in ('es', 's', 'b') else 0)) % 12
    minor = root.islower() or bool(re.match(r"^(m(?!aj)|moll|min)", rest))
    rest = re.sub(r"^(moll|min|m(?!aj))", "", rest)
    if 'dim' in rest or rest.startswith(('0', '°')):
        q = 'dim7' if '7' in rest else 'dim'
    elif 'aug' in rest or rest.startswith('+') or rest.startswith('5+'):
        q = 'aug'
    elif 'sus2' in rest:
        q = 'sus2'
    elif 'sus' in rest:
        q = 'sus4'
    elif 'maj7' in rest or '7+' in rest or rest.startswith('maj'):
        q = 'maj7'
    elif 'add9' in rest or 'add2' in rest:
        q = 'add9'
    elif re.search(r"(?<!\d)7", rest):
        q = 'm7' if minor else '7'
    elif re.search(r"(?<!\d)6", rest):
        q = 'm6' if minor else '6'
    elif re.search(r"(?<!\d)9", rest):
        q = 'm7' if minor else '9'
    else:
        q = 'min' if minor else 'maj'
    return pc, q


def shape(name, en=False):
    """Chwyt: {'frets': [6 strun], 'barre': (próg, od struny) albo None} albo None."""
    p = parse(name, en)
    if not p:
        return None
    pc, q = p
    if (pc, q) in OPEN:
        return {'frets': OPEN[(pc, q)], 'barre': None}
    cands = []
    for tmpl, low in ((E_SHAPE, 4), (A_SHAPE, 9)):
        t = tmpl.get(q) or (tmpl.get('min') if q in ('m6', 'm7') else None)
        if not t:
            continue
        r = (pc - low) % 12
        if r == 0 and any(x is not None and x < 0 for x in t):
            r = 12
        frets = [-1 if x is None else r + x for x in t]
        if min(f for f in frets if f >= 0) < 0:
            continue
        first = next(i for i, x in enumerate(t) if x is not None)
        cands.append((max(frets), {'frets': frets, 'barre': (r, first) if r > 0 else None}))
    if not cands:
        return None
    return min(cands, key=lambda c: c[0])[1]


def song_chords(text, k=0, flat=False):
    """Akordy pieśni w kolejności pierwszego wystąpienia (po transpozycji o k półtonów)."""
    from modul_akordy import transpose_chord
    names = re.findall(r"\[([^\]\s]{1,12})\]", text or "")
    for line in (text or "").splitlines():
        if "‖" in line:
            from modul_akordy import split_glued
            for t in re.split(r"[\s/()]+", line.split("‖", 1)[1]):
                if t:
                    names += split_glued(t)
    out = []
    for n in names:
        n = n.strip().strip("()[].,")
        if not n or not RE_NAME.match(n):
            continue
        t = transpose_chord(n, k, flat) if k else n
        if t not in out:
            out.append(t)
    return out


# ---------------------------------------------------------------------
# widżety
# ---------------------------------------------------------------------
class ChordDiagram(QWidget):
    """Jeden chwyt na gryfie: 6 strun, 5 progów, kropki, x / o, barre."""

    def __init__(self, name, en=False, scale=1.0, parent=None):
        super().__init__(parent)
        self.name, self.en, self.sc = name, en, scale
        self.sh = shape(name, en)
        self.setFixedSize(int(96 * scale), int(132 * scale))
        p = parse(name, en)
        self.setToolTip(f"{name}: {QUALITY_NAMES.get(p[1], '')}" if p else name)

    def paintEvent(self, _):
        s = self.sc
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f = QFont(self.font())
        f.setBold(True)
        f.setPixelSize(int(15 * s))
        p.setFont(f)
        p.setPen(QColor("#B22222"))
        p.drawText(QRectF(0, 0, self.width(), 20 * s), Qt.AlignCenter, self.name)
        if not self.sh:
            p.setPen(QColor("#888"))
            f.setBold(False)
            f.setPixelSize(int(11 * s))
            p.setFont(f)
            p.drawText(QRectF(0, 24 * s, self.width(), 80 * s), Qt.AlignCenter | Qt.TextWordWrap, "brak chwytu\nw tabeli")
            return
        frets = self.sh['frets']
        played = [x for x in frets if x > 0]
        top = max(played) if played else 0
        base = 1 if top <= 4 else min(played)
        x0, y0, dx, dy = 18 * s, 34 * s, 13 * s, 18 * s
        ink = QColor("#222")
        p.setPen(QPen(ink, 1))
        for i in range(6):
            p.drawLine(QPointF(x0 + i * dx, y0), QPointF(x0 + i * dx, y0 + 5 * dy))
        for j in range(6):
            p.drawLine(QPointF(x0, y0 + j * dy), QPointF(x0 + 5 * dx, y0 + j * dy))
        if base == 1:
            p.setPen(QPen(ink, 4 * s))
            p.drawLine(QPointF(x0, y0), QPointF(x0 + 5 * dx, y0))
        else:
            f.setBold(False)
            f.setPixelSize(int(11 * s))
            p.setFont(f)
            p.setPen(ink)
            p.drawText(QRectF(x0 + 5 * dx + 3 * s, y0 + 1 * s, 22 * s, dy), Qt.AlignLeft | Qt.AlignVCenter, f"{base}")
        f.setBold(False)
        f.setPixelSize(int(11 * s))
        p.setFont(f)
        r = 5.2 * s
        if self.sh['barre'] and self.sh['barre'][0] >= base:
            bf, first = self.sh['barre']
            y = y0 + (bf - base + 0.5) * dy
            p.setPen(Qt.NoPen)
            p.setBrush(ink)
            p.drawRoundedRect(QRectF(x0 + first * dx - r, y - r, (5 - first) * dx + 2 * r, 2 * r), r, r)
        for i, fr in enumerate(frets):
            x = x0 + i * dx
            if fr < 0:
                p.setPen(QPen(ink, 1.3))
                p.drawLine(QPointF(x - 3.5 * s, y0 - 12 * s), QPointF(x + 3.5 * s, y0 - 5 * s))
                p.drawLine(QPointF(x + 3.5 * s, y0 - 12 * s), QPointF(x - 3.5 * s, y0 - 5 * s))
            elif fr == 0:
                p.setPen(QPen(ink, 1.2))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QPointF(x, y0 - 8.5 * s), 3.6 * s, 3.6 * s)
            else:
                y = y0 + (fr - base + 0.5) * dy
                p.setPen(Qt.NoPen)
                p.setBrush(ink)
                p.drawEllipse(QPointF(x, y), r, r)


class ChordStrip(QScrollArea):
    """Pasek z chwytami wszystkich akordów pieśni."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFixedHeight(150)
        self.setFrameShape(QScrollArea.NoFrame)
        self.inner = QWidget()
        self.lay = QHBoxLayout(self.inner)
        self.lay.setContentsMargins(4, 2, 4, 2)
        self.lay.setSpacing(4)
        self.setWidget(self.inner)

    def set_chords(self, names, en=None):
        while self.lay.count():
            w = self.lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        if en is None:
            en = guess_english(names)
        for n in names:
            self.lay.addWidget(ChordDiagram(n, en))
        self.lay.addStretch(1)


BLACK = {1, 3, 6, 8, 10}


class Keyboard(QWidget):
    """Klawiatura fortepianu z podświetlonymi dźwiękami: set_active({wysokość: kolor})."""

    def __init__(self, lo=36, hi=96, parent=None):
        super().__init__(parent)
        self.lo, self.hi = lo, hi
        self.active = {}
        self.setMinimumHeight(90)
        self.setMaximumHeight(130)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def sizeHint(self):
        return QSize(900, 110)

    def set_range(self, lo, hi):
        lo = max(21, (lo // 12) * 12)                        # od C
        hi = min(108, ((hi // 12) + 1) * 12)
        if hi - lo < 36:
            hi = lo + 36
        self.lo, self.hi = lo, hi
        self.update()

    def set_active(self, active):
        if active != self.active:
            self.active = active
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        whites = [n for n in range(self.lo, self.hi + 1) if n % 12 not in BLACK]
        ww = self.width() / max(1, len(whites))
        h = self.height() - 1
        xs = {}
        for i, n in enumerate(whites):
            xs[n] = i * ww
            col = self.active.get(n)
            p.setPen(QPen(QColor("#555"), 1))
            p.setBrush(QColor(col) if col else QColor("#FFFEFA"))
            p.drawRect(QRectF(i * ww, 0, ww, h))
            if n % 12 == 0:
                p.setPen(QColor("#777"))
                f = QFont(self.font())
                f.setPixelSize(max(8, int(ww * 0.45)))
                p.setFont(f)
                p.drawText(QRectF(i * ww, h - 16, ww, 14), Qt.AlignCenter, f"C{n // 12 - 1}")
        bw, bh = ww * 0.62, h * 0.62
        for n in range(self.lo, self.hi + 1):
            if n % 12 in BLACK and (n - 1) in xs:
                x = xs[n - 1] + ww - bw / 2
                col = self.active.get(n)
                p.setPen(QPen(QColor("#222"), 1))
                p.setBrush(QColor(col) if col else QColor("#222"))
                p.drawRoundedRect(QRectF(x, 0, bw, bh), 2, 2)
