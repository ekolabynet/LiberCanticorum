# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Autorzy projektu Liber Canticorum
"""
Moduł YouTube dla programu Liber Canticorum.

* Wyszukiwanie nagrań: przez oficjalne YouTube Data API v3 (własny, darmowy klucz API
  wpisany w programie) albo – bez klucza – w przeglądarce, z wklejeniem linku.
* Odtwarzanie przez oficjalny osadzony odtwarzacz YouTube (zgodnie z regulaminem serwisu):
  - „Wideo” – odtwarzacz na pełnym ekranie rzutnika,
  - „Tylko dźwięk” – małe okienko odtwarzacza na ekranie operatora, a na rzutniku
    czyste tło slajdu (bez tekstu),
  - bez pakietu PySide6-Addons (QtWebEngine) nagranie otwiera się w przeglądarce.

Uwaga: publiczne odtwarzanie nagrań (np. w kościele) może wymagać zgody właścicieli praw.
"""
import json
import re
import urllib.parse
import urllib.request

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget, QApplication)

API_URL = "https://www.googleapis.com/youtube/v3/search"
SETTINGS_KEY = "youtube_api_key"


def video_id(url):
    url = (url or "").strip()
    for pat in (r'(?:v=|/embed/|/shorts/|/live/|youtu\.be/|/v/)([A-Za-z0-9_-]{11})', r'^([A-Za-z0-9_-]{11})$'):
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def watch_url(vid):
    return f"https://www.youtube.com/watch?v={vid}"


def browser_search_url(q):
    return "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(q)


def api_search(query, key, limit=15):
    """[(id, tytuł, kanał)] – YouTube Data API v3 (search.list, 100 jednostek limitu na zapytanie)."""
    params = {'part': 'snippet', 'type': 'video', 'maxResults': limit, 'q': query, 'key': key,
              'relevanceLanguage': 'pl', 'safeSearch': 'strict'}
    req = urllib.request.Request(API_URL + "?" + urllib.parse.urlencode(params))
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode('utf-8'))['error']['message']
        except Exception:
            msg = str(e)
        raise RuntimeError(f"YouTube API: {msg}")
    import html
    return [(it['id']['videoId'], html.unescape(it['snippet']['title']), html.unescape(it['snippet']['channelTitle']))
            for it in data.get('items', []) if it.get('id', {}).get('videoId')]


def webengine_available():
    try:
        from PySide6 import QtWebEngineWidgets  # noqa: F401  # pyflakes: ignore
        del QtWebEngineWidgets
        return True
    except ImportError:
        return False


class YouTubeSearchDialog(QDialog):
    add_requested = Signal(str, str)        # url, opis
    play_requested = Signal(str, str)       # url, tryb: video | audio | browser

    def __init__(self, query, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Nagrania z YouTube")
        self.resize(720, 520)
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.q = QLineEdit(query)
        self.q.returnPressed.connect(self.search)
        b = QPushButton("Szukaj")
        b.clicked.connect(self.search)
        bk = QPushButton("Klucz API…")
        bk.clicked.connect(self.set_key)
        row.addWidget(QLabel("Szukaj:"))
        row.addWidget(self.q, 1)
        row.addWidget(b)
        row.addWidget(bk)
        lay.addLayout(row)
        self.hint = QLabel(wordWrap=True)
        lay.addWidget(self.hint)
        self.results = QListWidget()
        self.results.itemDoubleClicked.connect(lambda it: self.emit_play('video'))
        lay.addWidget(self.results, 1)
        lrow = QHBoxLayout()
        self.link = QLineEdit(placeholderText="…albo wklej link do nagrania z YouTube")
        self.link.returnPressed.connect(self.add_link)
        bl = QPushButton("Dodaj link")
        bl.clicked.connect(self.add_link)
        lrow.addWidget(self.link, 1)
        lrow.addWidget(bl)
        lay.addLayout(lrow)
        brow = QHBoxLayout()
        for txt, fn in (("Dodaj do pieśni", self.add_selected), ("▶ Wideo", lambda: self.emit_play('video')),
                        ("♪ Tylko dźwięk + czyste tło", lambda: self.emit_play('audio')),
                        ("Otwórz w przeglądarce", lambda: self.emit_play('browser'))):
            bb = QPushButton(txt)
            bb.clicked.connect(fn)
            brow.addWidget(bb)
        close = QPushButton("Zamknij")
        close.clicked.connect(self.accept)
        brow.addStretch()
        brow.addWidget(close)
        lay.addLayout(brow)
        try:
            import ikony
            ikony.apply_icons(self)
        except ImportError:
            pass
        self.update_hint()

    def key(self):
        return (self.settings.value(SETTINGS_KEY, "") or "").strip()

    def update_hint(self):
        if self.key():
            self.hint.setText("Wyszukiwanie w programie przez YouTube Data API.")
        else:
            self.hint.setText("Brak klucza API – „Szukaj” otworzy YouTube w przeglądarce; skopiuj link nagrania i wklej go poniżej. "
                              "Darmowy klucz (YouTube Data API v3) utworzysz w Google Cloud Console – wtedy wyniki pokażą się tutaj.")

    def set_key(self):
        k, ok = QInputDialog.getText(self, "Klucz YouTube Data API v3", "Klucz API (pusty = wyszukiwanie w przeglądarce):",
                                     QLineEdit.Normal, self.key())
        if ok:
            self.settings.setValue(SETTINGS_KEY, k.strip())
            self.update_hint()

    def search(self):
        q = self.q.text().strip()
        if not q:
            return
        if not self.key():
            QDesktopServices.openUrl(QUrl(browser_search_url(q)))
            self.link.setFocus()
            return
        self.results.clear()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            res = api_search(q, self.key())
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "YouTube", f"Wyszukiwanie nie powiodło się:\n{e}")
            return
        QApplication.restoreOverrideCursor()
        for vid, title, channel in res:
            it = QListWidgetItem(f"{title}   —   {channel}")
            it.setData(Qt.UserRole, watch_url(vid))
            it.setData(Qt.UserRole + 1, f"{title} ({channel})")
            self.results.addItem(it)
        if not res:
            self.hint.setText("Brak wyników.")

    def _selected(self):
        it = self.results.currentItem()
        if it:
            return it.data(Qt.UserRole), it.data(Qt.UserRole + 1)
        vid = video_id(self.link.text())
        return (watch_url(vid), "") if vid else (None, None)

    def add_selected(self):
        url, title = self._selected()
        if url:
            self.add_requested.emit(url, title)

    def add_link(self):
        vid = video_id(self.link.text())
        if not vid:
            QMessageBox.warning(self, "YouTube", "To nie wygląda na link do nagrania YouTube.")
            return
        title, ok = QInputDialog.getText(self, "Opis nagrania", "Opis (np. wykonawca):")
        self.add_requested.emit(watch_url(vid), title.strip() if ok else "")
        self.link.clear()

    def emit_play(self, mode):
        url, _ = self._selected()
        if url:
            self.play_requested.emit(url, mode)


class PlayerWindow(QWidget):
    """Osadzony odtwarzacz YouTube (wymaga QtWebEngine z PySide6-Addons)."""

    def __init__(self, vid, mode, screen=None):
        super().__init__(None)
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWebEngineCore import QWebEngineSettings
        self.setWindowTitle("YouTube – " + ("wideo" if mode == 'video' else "tylko dźwięk (rzutnik: czyste tło)"))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView()
        self.view.settings().setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, False)
        self.view.settings().setAttribute(QWebEngineSettings.FullScreenSupportEnabled, True)
        lay.addWidget(self.view)
        origin = "https://spiewnik.local"
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="referrer" content="strict-origin-when-cross-origin">
<style>html,body{{margin:0;height:100%;background:#000;overflow:hidden}}iframe{{border:0;width:100%;height:100%}}</style></head>
<body><iframe src="https://www.youtube-nocookie.com/embed/{vid}?autoplay=1&rel=0&playsinline=1&origin={origin}"
 referrerpolicy="strict-origin-when-cross-origin" allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
 allowfullscreen></iframe></body></html>"""
        self.view.setHtml(html, QUrl(origin + "/"))
        QShortcut(QKeySequence("Esc"), self, activated=self.close)
        if screen is not None:
            self.setScreen(screen)
            g = screen.availableGeometry()
            if mode == 'video':
                self.move(screen.geometry().topLeft())
                self.showFullScreen()
            else:
                self.resize(480, 300)
                self.move(g.right() - 500, g.bottom() - 340)
                self.show()
        else:
            self.resize(800, 480)
            self.show()

    def closeEvent(self, e):
        self.view.setHtml("")          # zatrzymaj dźwięk
        super().closeEvent(e)


def play(url, mode, screen=None, parent=None):
    """Odtwarza nagranie. Zwraca okno odtwarzacza albo None (przeglądarka)."""
    vid = video_id(url)
    if not vid:
        QMessageBox.warning(parent, "YouTube", "Nieprawidłowy link do nagrania.")
        return None
    if mode == 'browser' or not webengine_available():
        QDesktopServices.openUrl(QUrl(watch_url(vid)))
        return None
    return PlayerWindow(vid, mode, screen)
