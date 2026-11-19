#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Liber Canticorum – proste widoki dla każdego (zakładki u dołu okna):
Start (kafle najważniejszych funkcji), Teksty, Slajdy, Nuty; „Zaawansowane” to dotychczasowy pełny interfejs.
Wygląd: jasny pergamin bez ozdobników, monogram „C” w rogu.

Licencja: GPL-3.0-or-later.
"""
import html as H

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QFont, QPalette, QPixmap, QIcon, QPainter
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QLineEdit,
                               QListWidget, QListWidgetItem, QPushButton, QComboBox, QTextBrowser, QScrollArea,
                               QSplitter, QSizePolicy, QApplication, QStyleFactory)

# --- kolory: jasny pergamin
PARCHMENT = "#F5EEDC"      # tło okna
PAPER = "#FBF8F1"          # pola tekstowe, listy
BUTTON = "#ECE2CC"
LINE = "#D6C7A6"
INK = "#2F261D"            # tekst
MUTED = "#7A6A55"
ACCENT = "#7A2E3A"         # bordo – zaznaczenie
GOLD = "#A8803A"           # monogram


def apply_theme(app, on=True):
    """Pergamin (styl Fusion + paleta) albo wygląd systemowy."""
    if not on:
        return
    app.setStyle(QStyleFactory.create("Fusion"))
    pal = QPalette()
    for role, col in ((QPalette.Window, PARCHMENT), (QPalette.Base, PAPER), (QPalette.AlternateBase, "#F3EAD6"),
                      (QPalette.Button, BUTTON), (QPalette.Text, INK), (QPalette.WindowText, INK),
                      (QPalette.ButtonText, INK), (QPalette.ToolTipBase, PAPER), (QPalette.ToolTipText, INK),
                      (QPalette.Highlight, ACCENT), (QPalette.HighlightedText, "#FFFFFF"),
                      (QPalette.PlaceholderText, MUTED), (QPalette.Link, ACCENT)):
        pal.setColor(role, QColor(col))
    pal.setColor(QPalette.Disabled, QPalette.Text, QColor("#A89A84"))
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#A89A84"))
    pal.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#A89A84"))
    app.setPalette(pal)
    app.setStyleSheet(f"""
        QToolTip {{ color: {INK}; background: {PAPER}; border: 1px solid {LINE}; }}
        QTabWidget#views > QTabBar::tab {{ min-width: 120px; padding: 9px 18px; font-size: 11pt;
            background: {BUTTON}; border: 1px solid {LINE}; border-top: none; margin-right: 2px;
            border-bottom-left-radius: 6px; border-bottom-right-radius: 6px; }}
        QTabWidget#views > QTabBar::tab:selected {{ background: {PAPER}; color: {ACCENT}; font-weight: bold; }}
        QTabWidget#views::pane {{ border: none; }}
        QFrame#tile {{ background: {PAPER}; border: 1px solid {LINE}; border-radius: 10px; }}
        QFrame#tile:hover {{ border: 1px solid {ACCENT}; background: #FFFDF7; }}
        QLabel#tileTitle {{ font-size: 14pt; font-weight: bold; color: {INK}; }}
        QLabel#tileText {{ font-size: 10pt; color: {MUTED}; }}
        QLabel#tileIcon {{ font-size: 26pt; }}
        QLabel#homeTitle {{ font-family: 'Cormorant Garamond', 'EB Garamond', 'Crimson Text', 'Georgia', serif;
            font-size: 26pt; color: {INK}; }}
        QLabel#homeSub {{ color: {MUTED}; font-size: 11pt; }}
        QPushButton#big {{ font-size: 12pt; padding: 8px 16px; }}
        QListWidget#picker {{ font-size: 12pt; }}
    """)


def serif_font(px, bold=False):
    f = QFont()
    f.setFamilies(["Cormorant Garamond", "EB Garamond", "Crimson Text", "Linux Libertine O", "Georgia",
                   "Noto Serif", "DejaVu Serif", "Liberation Serif", "Times New Roman", "serif"])
    f.setStyleHint(QFont.Serif)
    f.setPixelSize(px)
    f.setBold(bold)
    return f


def logo_path(size=512):
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    for s in (size, 512, 256, 128):
        p = os.path.join(here, "ikony", f"liber_canticorum_{s}.png")
        if os.path.exists(p):
            return p
    return ""


class Monogram(QLabel):
    """Monogram programu: inicjałowe „C” z kancjonału (logo Liber Canticorum)."""

    def __init__(self, size=30, parent=None):
        super().__init__(parent)
        path = logo_path(512 if size > 64 else 128)
        pm = QPixmap(path) if path else QPixmap()
        if pm.isNull():                                    # brak pliku – sama litera
            self.setText("C")
            self.setFont(serif_font(size, True))
            self.setStyleSheet(f"color: {GOLD}; background: transparent; padding: 0 10px;")
        else:
            dpr = self.devicePixelRatioF() if hasattr(self, 'devicePixelRatioF') else 1.0
            pm = pm.scaled(int(size * dpr), int(size * dpr), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            pm.setDevicePixelRatio(dpr)
            self.setPixmap(pm)
            self.setStyleSheet("background: transparent; padding: 2px 8px;")
        self.setToolTip("Liber Canticorum")
        self.setAlignment(Qt.AlignCenter)


def monogram_icon(size=256):
    """Ikona okna: logo programu (inicjał „C” z kancjonału)."""
    path = logo_path(size)
    if path:
        return QIcon(path)
    pm = QPixmap(size, size)
    pm.fill(QColor(PARCHMENT))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QColor(GOLD))
    p.setFont(serif_font(int(size * 0.8), True))
    p.drawText(pm.rect(), Qt.AlignCenter, "C")
    p.end()
    return QIcon(pm)


class Tile(QFrame):
    clicked = Signal()

    def __init__(self, icon, title, text, parent=None):
        super().__init__(parent)
        self.setObjectName("tile")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumSize(230, 96)
        self.setMaximumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        ic = QLabel(icon)
        ic.setObjectName("tileIcon")
        ic.setAlignment(Qt.AlignTop)
        lay.addWidget(ic)
        col = QVBoxLayout()
        col.setSpacing(4)
        t = QLabel(title)
        t.setObjectName("tileTitle")
        d = QLabel(text)
        d.setObjectName("tileText")
        d.setWordWrap(True)
        col.addWidget(t)
        col.addWidget(d)
        col.addStretch(1)
        lay.addLayout(col, 1)
        self.setAccessibleName(title)
        self.setToolTip(text)
        self.setFocusPolicy(Qt.StrongFocus)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(e)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit()
        else:
            super().keyPressEvent(e)


class HomePage(QWidget):
    """Start: kafle najważniejszych funkcji."""

    def __init__(self, tiles, info="", parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(36, 24, 36, 20)
        head = QHBoxLayout()
        head.addWidget(Monogram(84))
        tl = QVBoxLayout()
        t = QLabel("Liber Canticorum")
        t.setObjectName("homeTitle")
        t.setFont(serif_font(40))
        tl.addWidget(t)
        self.sub = QLabel(info or "Śpiewnik, slajdy i nuty dla scholi i chóru")
        self.sub.setObjectName("homeSub")
        tl.addWidget(self.sub)
        head.addLayout(tl, 1)
        outer.addLayout(head)
        outer.addSpacing(14)
        grid = QGridLayout()
        grid.setSpacing(14)
        for k, (icon, title, text, fn) in enumerate(tiles):
            tile = Tile(icon, title, text)
            tile.clicked.connect(fn)
            grid.addWidget(tile, k // 3, k % 3)
        outer.addLayout(grid)
        outer.addStretch(1)

    def set_info(self, text):
        self.sub.setText(text)


class SongPicker(QWidget):
    """Szukaj + lista pieśni (wszystkie albo z bieżącego zestawu). Sygnał chosen(id)."""
    chosen = Signal(int)
    bulk = Signal(str, list)        # ('merge' | 'category' | 'tags', [id…]) – działania na kilku zaznaczonych pieśniach

    def __init__(self, db, set_ids=None, parent=None):
        super().__init__(parent)
        self.db, self.set_ids = db, set_ids or (lambda: [])
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.mode = QComboBox()
        self.mode.addItems(["Wszystkie pieśni", "Pieśni z bieżącego zestawu"])
        self.mode.currentIndexChanged.connect(self.refresh)
        lay.addWidget(self.mode)
        self.cat = QComboBox()
        self.cat.setToolTip("Kategoria pieśni")
        self.cat.currentIndexChanged.connect(self.refresh)
        crow = QHBoxLayout()
        crow.addWidget(self.cat, 1)
        b_cat = QPushButton("⚙")
        b_cat.setFixedWidth(32)
        b_cat.setToolTip("Menedżer kategorii: zmiana nazw, łączenie podobnych, usuwanie")
        b_cat.clicked.connect(lambda: self.bulk.emit('categories', []))
        crow.addWidget(b_cat)
        lay.addLayout(crow)
        self.q = QLineEdit()
        self.q.setPlaceholderText("Szukaj: tytuł albo słowa pieśni…")
        self.q.setClearButtonEnabled(True)
        self.q.textChanged.connect(self.refresh)
        lay.addWidget(self.q)
        self.list = QListWidget()
        self.list.setObjectName("picker")
        self.list.currentItemChanged.connect(self._pick)
        self.list.setSelectionMode(QListWidget.ExtendedSelection)
        self.list.setToolTip("Shift+klik – zaznacz zakres, Ctrl+klik – pojedyncze pieśni; potem: połącz albo nadaj kategorię")
        self.list.itemSelectionChanged.connect(self._sel_changed)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._menu)
        lay.addWidget(self.list, 1)
        self.multi = QWidget()
        ml = QVBoxLayout(self.multi)
        ml.setContentsMargins(0, 2, 0, 2)
        ml.setSpacing(3)
        self.multi_lbl = QLabel()
        self.multi_lbl.setStyleSheet("font-weight: bold;")
        ml.addWidget(self.multi_lbl)
        row = QHBoxLayout()
        for txt, act, tip in (("🔗 Połącz", 'merge', "To ta sama pieśń – połącz w jedną (teksty jako wersje, nuty, nagrania, zestawy)"),
                              ("🏷 Kategoria…", 'category', "Ta sama kategoria dla wszystkich zaznaczonych"),
                              ("Tagi…", 'tags', "Dodaj albo usuń tagi zaznaczonym pieśniom")):
            b = QPushButton(txt)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, a=act: self.bulk.emit(a, self.selected_ids()))
            row.addWidget(b)
        ml.addLayout(row)
        self.multi.setVisible(False)
        lay.addWidget(self.multi)
        self.count = QLabel()
        self.count.setStyleSheet(f"color: {MUTED};")
        lay.addWidget(self.count)

    def fill_categories(self):
        keep = self.cat.currentData()
        self.cat.blockSignals(True)
        self.cat.clear()
        self.cat.addItem("Wszystkie kategorie", None)
        for name, n in self.db.categories():
            self.cat.addItem(f"{name or '(bez kategorii)'}  ({n})", name)
        k = self.cat.findData(keep)
        self.cat.setCurrentIndex(k if k >= 0 else 0)
        self.cat.blockSignals(False)

    def refresh(self, *_):
        if self.cat.count() == 0 or not _:
            self.fill_categories()
        cat = self.cat.currentData()
        cur = self.current()
        self.list.blockSignals(True)
        self.list.clear()
        if self.mode.currentIndex() == 1:
            rows = []
            for label, sid in self.set_ids():
                s = self.db.get(sid)
                if s and (not self.q.text().strip() or self.q.text().lower() in (s['title'] + s['zwrotki_raw']).lower()) \
                        and (cat is None or (s.get('kategoria') or '') == cat):
                    rows.append((sid, f"{label}: {s['title']}" if label else s['title']))
        else:
            rows = [(r['id'], r['title']) for r in self.db.search(self.q.text(), category=cat)]
        for sid, title in rows:
            it = QListWidgetItem(title)
            it.setData(Qt.UserRole, sid)
            self.list.addItem(it)
            if sid == cur:
                self.list.setCurrentItem(it)
        self.list.blockSignals(False)
        self._sel_changed()
        self.count.setText(f"{len(rows)} pieśni")

    def selected_ids(self):
        return [it.data(Qt.UserRole) for it in self.list.selectedItems() if it.data(Qt.UserRole)]

    def _sel_changed(self):
        n = len(self.list.selectedItems())
        self.multi.setVisible(n > 1)
        self.multi_lbl.setText(f"Zaznaczone pieśni: {n}")

    def _menu(self, pos):
        from PySide6.QtWidgets import QMenu
        ids = self.selected_ids()
        if not ids:
            return
        m = QMenu(self)
        if len(ids) > 1:
            m.addAction(f"🔗 Połącz zaznaczone ({len(ids)}) w jedną pieśń…", lambda: self.bulk.emit('merge', ids))
        m.addAction(f"🏷 Kategoria dla zaznaczonych ({len(ids)})…", lambda: self.bulk.emit('category', ids))
        m.addAction(f"Tagi dla zaznaczonych ({len(ids)})…", lambda: self.bulk.emit('tags', ids))
        m.addSeparator()
        m.addAction("Znajdź duplikaty w całej bazie…", lambda: self.bulk.emit('duplicates', ids))
        m.addAction("Menedżer kategorii…", lambda: self.bulk.emit('categories', []))
        m.exec(self.list.viewport().mapToGlobal(pos))

    def current(self):
        it = self.list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def select(self, sid):
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == sid:
                self.list.blockSignals(True)
                self.list.setCurrentRow(i)
                self.list.blockSignals(False)
                self.list.scrollToItem(self.list.item(i))
                return True
        return False

    def reset_filters(self):
        for w in (self.mode, self.cat):
            w.blockSignals(True)
            w.setCurrentIndex(0)
            w.blockSignals(False)
        self.q.blockSignals(True)
        self.q.clear()
        self.q.blockSignals(False)
        self.refresh()

    def _pick(self, it, _prev=None):
        if it:
            self.chosen.emit(it.data(Qt.UserRole))


def _with_picker(page, picker, right):
    sp = QSplitter()
    sp.addWidget(picker)
    sp.addWidget(right)
    sp.setSizes([320, 900])
    sp.setStretchFactor(1, 1)
    lay = QVBoxLayout(page)
    lay.setContentsMargins(10, 10, 10, 6)
    lay.addWidget(sp)


class TextsPage(QWidget):
    """Przeglądanie tekstów pieśni – duże, czytelne litery; akordy na życzenie."""

    def __init__(self, db, set_ids, on_slides, on_edit, parent=None):
        super().__init__(parent)
        self.db, self.sid, self.size, self.chords = db, None, 20, False
        self.picker = SongPicker(db, set_ids)
        self.picker.chosen.connect(self.show_song)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 0, 0, 0)
        bar = QHBoxLayout()
        for txt, fn in (("A−", lambda: self.zoom(-2)), ("A+", lambda: self.zoom(2))):
            b = QPushButton(txt)
            b.setFixedWidth(44)
            b.clicked.connect(fn)
            bar.addWidget(b)
        self.b_ch = QPushButton("🎸 Akordy")
        self.b_ch.setCheckable(True)
        self.b_ch.toggled.connect(self._chords)
        bar.addWidget(self.b_ch)
        bar.addStretch(1)
        b = QPushButton("🖥 Slajdy tej pieśni")
        b.clicked.connect(lambda: self.sid and on_slides(self.sid))
        bar.addWidget(b)
        b = QPushButton("✎ Edytuj")
        b.clicked.connect(lambda: self.sid and on_edit(self.sid))
        bar.addWidget(b)
        rl.addLayout(bar)
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(False)
        rl.addWidget(self.view, 1)
        _with_picker(self, self.picker, right)

    def refresh(self):
        self.picker.refresh()
        if self.sid is None and self.picker.list.count():
            self.picker.list.setCurrentRow(0)

    def zoom(self, d):
        self.size = max(12, min(48, self.size + d))
        self.render()

    def _chords(self, on):
        self.chords = on
        self.render()

    def show_song(self, sid):
        self.sid = sid
        self.render()

    def render(self):
        s = self.db.get(self.sid) if self.sid else None
        if not s:
            self.view.setHtml("")
            return
        has = bool((s.get('akordy') or '').strip())
        self.b_ch.setEnabled(has)
        if self.chords and has:
            import modul_akordy as ak
            self.view.setHtml(ak.chordpro_html(s['title'], s['akordy'], 0, self.size))
            return
        z = self.size
        out = [f"<h2 style='font-size:{int(z * 1.35)}px;margin-bottom:.4em'>{H.escape(s['title'])}</h2>"]
        if s.get('refren'):
            out.append(f"<p style='font-size:{z}px;font-style:italic'><b>Ref.:</b> "
                       + "<br>".join(H.escape(l) for l in s['refren'].splitlines()) + "</p>")
        for v in [v for v in (s.get('zwrotki_raw') or '').split("\n\n") if v.strip()]:
            out.append(f"<p style='font-size:{z}px'>" + "<br>".join(H.escape(l) for l in v.splitlines()) + "</p>")
        meta = " · ".join(x for x in (s.get('kategoria'), s.get('uwagi')) if x)
        if meta:
            out.append(f"<p style='color:{MUTED};font-size:{max(11, z // 2)}px'>{H.escape(meta)}</p>")
        self.view.setHtml(f"<div style='color:{INK}'>{''.join(out)}</div>")


class SlidesPage(QWidget):
    """Slajdy do pieśni: podgląd, miniatury, pokaz jednym przyciskiem."""

    def __init__(self, db, set_ids, build_deck, slide_view_cls, slide_pixmap, on_present, on_present_set,
                 parent=None):
        super().__init__(parent)
        self.db, self.build_deck, self.pix, self.deck, self.sid = db, build_deck, slide_pixmap, [], None
        self.on_present = on_present
        self.picker = SongPicker(db, set_ids)
        self.picker.chosen.connect(self.show_song)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 0, 0, 0)
        bar = QHBoxLayout()
        b = QPushButton("▶ Pokaż na ekranie")
        b.setObjectName("big")
        b.setToolTip("Pokaz na rzutniku / drugim ekranie od zaznaczonego slajdu. Strzałki – kolejny slajd, Esc – koniec.")
        b.clicked.connect(lambda: self.deck and on_present(self.deck, max(0, self.thumbs.currentRow())))
        bar.addWidget(b)
        b = QPushButton("▶ Pokaz całego zestawu")
        b.setObjectName("big")
        b.clicked.connect(on_present_set)
        bar.addWidget(b)
        bar.addStretch(1)
        for txt, d in (("◀", -1), ("▶", 1)):
            bb = QPushButton(txt)
            bb.setFixedWidth(44)
            bb.clicked.connect(lambda _=False, d=d: self.step(d))
            bar.addWidget(bb)
        rl.addLayout(bar)
        self.view = slide_view_cls()
        rl.addWidget(self.view, 3)
        self.thumbs = QListWidget()
        self.thumbs.setViewMode(QListWidget.IconMode)
        self.thumbs.setIconSize(QSize(176, 99))
        self.thumbs.setResizeMode(QListWidget.Adjust)
        self.thumbs.setMovement(QListWidget.Static)
        self.thumbs.setFlow(QListWidget.LeftToRight)
        self.thumbs.setWrapping(False)
        self.thumbs.setFixedHeight(140)
        self.thumbs.currentRowChanged.connect(self._thumb)
        rl.addWidget(self.thumbs)
        self.info = QLabel()
        self.info.setStyleSheet(f"color: {MUTED};")
        rl.addWidget(self.info)
        _with_picker(self, self.picker, right)

    def refresh(self):
        self.picker.refresh()
        if self.sid is None and self.picker.list.count():
            self.picker.list.setCurrentRow(0)

    def show_song(self, sid):
        self.sid = sid
        s = self.db.get(sid)
        self.deck = self.build_deck(s)[0] if s else []
        self.thumbs.blockSignals(True)
        self.thumbs.clear()
        for i, sl in enumerate(self.deck):
            self.thumbs.addItem(QListWidgetItem(QIcon(self.pix(sl, 176)), str(i + 1)))
        self.thumbs.blockSignals(False)
        self.thumbs.setCurrentRow(0 if self.deck else -1)
        self.view.set_slide(self.deck[0] if self.deck else None)
        self.info.setText(f"{len(self.deck)} slajdów. Wygląd slajdów zmienisz w zakładce „Zaawansowane”."
                          if self.deck else "Ta pieśń nie ma tekstu.")

    def _thumb(self, row):
        if 0 <= row < len(self.deck):
            self.view.set_slide(self.deck[row])

    def step(self, d):
        r = self.thumbs.currentRow() + d
        if 0 <= r < len(self.deck):
            self.thumbs.setCurrentRow(r)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Right, Qt.Key_Down, Qt.Key_PageDown):
            self.step(1)
        elif e.key() in (Qt.Key_Left, Qt.Key_Up, Qt.Key_PageUp):
            self.step(-1)
        else:
            super().keyPressEvent(e)


class ScoresPage(QWidget):
    """Przeglądanie nut: pliki nut pieśni, strony do przewijania, odsłuch."""

    def __init__(self, db, set_ids, pages_fn, on_play, on_open, on_search, on_omr, on_melody=None, parent=None):
        super().__init__(parent)
        self.db, self.pages_fn, self.sid = db, pages_fn, None
        self.on_play, self.on_open = on_play, on_open
        self.picker = SongPicker(db, set_ids)
        self.picker.chosen.connect(self.show_song)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 0, 0, 0)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Nuty:"))
        self.files = QComboBox()
        self.files.setMinimumContentsLength(30)
        self.files.currentIndexChanged.connect(self.show_file)
        bar.addWidget(self.files, 1)
        self.b_play = QPushButton("▶ Posłuchaj")
        self.b_play.clicked.connect(lambda: self.aid() and on_play(self.sid, self.aid()))
        bar.addWidget(self.b_play)
        self.b_open = QPushButton("Otwórz w MuseScore / programie")
        self.b_open.clicked.connect(lambda: self.aid() and on_open(self.sid, self.aid()))
        bar.addWidget(self.b_open)
        if on_melody:
            b = QPushButton("🎼 Edytor melodii")
            b.setToolTip("Nowa melodia albo dalsza edycja zaznaczonej (z edytora): nuty, słowa, akordy")
            b.clicked.connect(lambda: self.sid and on_melody(self.sid, self.aid()))
            bar.addWidget(b)
        for txt, d in (("−", -0.15), ("+", 0.15)):
            b = QPushButton(txt)
            b.setFixedWidth(36)
            b.clicked.connect(lambda _=False, d=d: self.zoom(d))
            bar.addWidget(b)
        rl.addLayout(bar)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.pages = QWidget()
        self.pl = QVBoxLayout(self.pages)
        self.pl.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.scroll.setWidget(self.pages)
        rl.addWidget(self.scroll, 1)
        self.empty = QWidget()
        el = QHBoxLayout(self.empty)
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        el.addWidget(self.msg, 1)
        b = QPushButton("🔎 Szukaj nut w MuseScore")
        b.clicked.connect(lambda: self.sid and on_search(self.sid))
        el.addWidget(b)
        b = QPushButton("📷 Rozpoznaj nuty ze skanu")
        b.clicked.connect(lambda: self.sid and on_omr(self.sid))
        el.addWidget(b)
        if on_melody:
            b = QPushButton("🎼 Wpisz melodię")
            b.clicked.connect(lambda: self.sid and on_melody(self.sid, None))
            el.addWidget(b)
        rl.addWidget(self.empty)
        self.scale, self._imgs = 1.0, []
        _with_picker(self, self.picker, right)

    def refresh(self):
        self.picker.refresh()
        if self.sid is None and self.picker.list.count():
            self.picker.list.setCurrentRow(0)

    def aid(self):
        return self.files.currentData()

    def show_song(self, sid):
        from liber_canticorum import SCORE_EXT
        atts = [a for a in self.db.attachments(sid)
                if a['name'].lower().endswith(('.pdf', '.png', '.jpg', '.jpeg', '.mid', '.midi', '.kar') + SCORE_EXT)]
        atts.sort(key=lambda a: a['name'].lower().endswith(('.mid', '.midi', '.kar')))   # nuty przed samym MIDI
        key = (sid, tuple(a['id'] for a in atts))
        if key == getattr(self, '_shown', None):
            self.sid = sid
            return                                         # ta sama pieśń i te same nuty – bez przeliczania
        self._shown = key
        self.sid = sid
        self.files.blockSignals(True)
        self.files.clear()
        for a in atts:
            self.files.addItem((f"{a['opis']}: " if a['opis'] else "") + a['name'], a['id'])
        self.files.blockSignals(False)
        self.msg.setText("Ta pieśń nie ma jeszcze nut. Możesz je znaleźć w MuseScore albo rozpoznać ze skanu."
                         if not atts else "Brakuje nut? Poszukaj innych albo rozpoznaj ze skanu.")
        self.show_file()

    def show_file(self, *_):
        while self.pl.count():
            w = self.pl.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._imgs = []
        aid = self.aid()
        has_play = False
        if aid:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                pages, info, has_play = self.pages_fn(self.sid, aid)
            except Exception as e:                         # uszkodzony plik – nie wywracaj widoku
                pages, info, has_play = [], f"Nie da się pokazać tego pliku: {e}", False
            finally:
                QApplication.restoreOverrideCursor()
            for data in pages:
                pm = QPixmap()
                pm.loadFromData(data)
                self._imgs.append(pm)
            if info:
                lab = QLabel(info)
                lab.setStyleSheet(f"color: {MUTED};")
                self.pl.addWidget(lab)
            self._layout_pages()
        self.b_play.setEnabled(bool(aid) and has_play)
        self.b_open.setEnabled(bool(aid))

    def _layout_pages(self):
        for i in reversed(range(self.pl.count())):
            w = self.pl.itemAt(i).widget()
            if isinstance(w, QLabel) and w.pixmap() is not None and not w.pixmap().isNull():
                self.pl.takeAt(i)
                w.deleteLater()
        width = max(300, int((self.scroll.viewport().width() - 30) * self.scale))
        for pm in self._imgs:
            lab = QLabel()
            lab.setPixmap(pm.scaledToWidth(width, Qt.SmoothTransformation))
            lab.setStyleSheet("background: white; border: 1px solid #D6C7A6;")
            self.pl.addWidget(lab, 0, Qt.AlignHCenter)

    def zoom(self, d):
        self.scale = max(0.4, min(2.5, self.scale + d))
        self._layout_pages()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._imgs:
            self._layout_pages()
