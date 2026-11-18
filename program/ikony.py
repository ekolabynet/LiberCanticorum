# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Autorzy projektu Liber Canticorum
"""
Ikony programu: Font Awesome Free (https://fontawesome.com), licencja ikon CC BY 4.0
(plik ikony/LICENSE-FontAwesome.txt). Pliki SVG są barwione kolorem tekstu z bieżącego motywu
systemu, więc pasują do jasnego i ciemnego wyglądu.
"""
import os
import re

from PySide6.QtCore import QByteArray, QRectF, QSettings, QSize, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QAbstractButton, QApplication

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ikony")
_cache = {}

# --- motywy: styl (pełne / konturowe) i kolory przypisane do rodzajów działań
STYLES = [("pelne", "Pełne"), ("kontur", "Konturowe (lżejsze)")]
GROUPS = {
    'plik': ('file-circle-plus', 'floppy-disk', 'copy', 'folder-open', 'file-import', 'file-code', 'html5', 'align-left'),
    'eksport': ('file-pdf', 'file-powerpoint', 'universal-access', 'download', 'file-arrow-down'),
    'pokaz': ('play', 'pause', 'forward-step', 'backward-step', 'display', 'expand', 'image', 'list-ol',
              'mobile-screen-button', 'palette', 'qrcode'),
    'muzyka': ('music', 'headphones', 'youtube', 'paperclip', 'eye'),
    'siec': ('globe', 'link', 'magnifying-glass', 'rotate', 'arrow-up-right-from-square'),
    'usun': ('trash', 'xmark', 'eraser', 'stop', 'right-from-bracket'),
}
THEMES = [   # (klucz, nazwa, kolory grup lub None = kolor tekstu systemu)
    ("system", "Systemowe (kolor tekstu)", None),
    ("jasne", "Jasne pastelowe", {'plik': '#8cbcf0', 'eksport': '#f5b77a', 'pokaz': '#8ed8a8', 'muzyka': '#c3aaf0',
                                  'siec': '#7fd6d6', 'usun': '#f29a9a', 'inne': '#b4bfcc'}),
    ("biale", "Białe / jasne (pod ciemny wygląd)", {'*': '#eeeae0'}),
    ("kolorowe", "Kolorowe", {'plik': '#2f6fd6', 'eksport': '#e07b10', 'pokaz': '#22a052', 'muzyka': '#8a4fd0',
                              'siec': '#11a0a8', 'usun': '#d13b3b', 'inne': '#5f6b7a'}),
    ("zlote", "Złote (liturgiczne)", {'*': '#b8902b', 'usun': '#a8291f'}),
]


def _settings():
    return QSettings("LiberCanticorum", "LiberCanticorum")


def current_style():
    return _settings().value("icon_style", "pelne")


def current_theme():
    return _settings().value("icon_theme", "system")


def group_of(name):
    for g, names in GROUPS.items():
        if name in names:
            return g
    return 'inne'


def theme_color(name):
    colors = next((c for k, _, c in THEMES if k == current_theme()), None)
    if not colors:
        return text_color()
    return QColor(colors.get(group_of(name), colors.get('*', colors.get('inne', '#888888'))))

# napis na przycisku (bez symboli na początku) -> nazwa ikony
BY_LABEL = {
    "Nowa pieśń": "file-circle-plus", "Zapisz w bazie": "floppy-disk", "Duplikuj": "copy", "Usuń z bazy": "trash",
    "Eksport do PDF": "file-pdf", "Eksport do PPTX": "file-powerpoint", "Eksport do DOCX": "align-left", "Eksport dla niewidomych": "universal-access", "Dla niewidomych": "universal-access", "Materiały": "file-arrow-down", "Eksport materiałów": "file-arrow-down",
    "Importuj z pliku": "file-import", "Importuj ze strony WWW": "globe", "Szukaj w śpiewnikach": "magnifying-glass", "Importuj pliki JSON": "file-code", "Importuj z poprzedniej instalacji": "rotate",
    "Eksport śpiewnika offline": "html5", "Otwórz / utwórz inną bazę": "folder-open", "Zakończ": "right-from-bracket",
    "Pokaz od początku": "play", "Pokaz od bieżącego slajdu": "forward-step", "Pokaz zestawu": "list-ol",
    "Czyste tło": "image", "Pilot w telefonie": "mobile-screen-button", "Ścieżka do MuseScore": "gear",
    "Skróty w pokazie": "keyboard", "O programie": "circle-info", "Do zestawu": "arrow-down",
    "Usuń": "trash", "Wyczyść": "eraser", "Pokaz": "play", "PDF": "file-pdf", "PPTX": "file-powerpoint",
    "DOCX": "align-left", "HTML (telefon)": "mobile-screen-button",
    "Dodaj pliki": "paperclip", "Podgląd nut": "eye", "Otwórz w programie": "arrow-up-right-from-square",
    "Zapisz jako": "download", "Odtwarzacz głosów": "headphones", "MIDI – odtwarzanie głosów": "headphones",
    "Test MuseScore": "gear", "Szukaj nut w sieci": "magnifying-glass", "Szukaj nut w MuseScore": "magnifying-glass",
    "Szukaj na YouTube": "youtube", "Dodaj link": "link", "Wideo": "play", "Tylko dźwięk": "headphones",
    "Otwórz w przeglądarce": "globe", "Ustaw jako domyślne": "floppy-disk",
    # okna modułów
    "Szukaj w CPDL": "magnifying-glass", "Dołącz zaznaczone do pieśni": "paperclip", "Wskaż plik": "folder-open",
    "Pokaż też starsze pobrane": "rotate", "Otwórz stronę utworu": "globe", "Pobierz z CPDL i dołącz": "file-arrow-down",
    "Zamknij": "xmark", "Odtwórz": "play", "Pauza": "pause", "Od początku": "backward-step", "Zapisz WAV": "download",
    "SoundFont": "music", "Skąd pobrać": "globe", "Pełny ekran": "expand", "Głosy (MIDI)": "headphones",
    "Otwórz w MuseScore": "arrow-up-right-from-square", "Nowy PIN": "rotate", "Wyłącz pilota": "stop",
    "Klucz API": "gear", "Szukaj": "magnifying-glass", "Dodaj do pieśni": "paperclip",
}
_SYMBOLS = re.compile(r'^[\s▶⏸⏮♪↓📱👁＋+✓…♿📦]+')


def text_color():
    return QApplication.palette().color(QPalette.ButtonText)


def fa_icon(name, color=None):
    """QIcon z pliku ikony/<name>.svg w zadanym kolorze (domyślnie kolor tekstu motywu)."""
    col = QColor(color) if color else theme_color(name)
    style = current_style()
    key = (name, col.name(), style)
    if key in _cache:
        return _cache[key]
    path = os.path.join(ICON_DIR, name + ".svg")
    if style == "kontur" and os.path.exists(os.path.join(ICON_DIR, "kontur", name + ".svg")):
        path = os.path.join(ICON_DIR, "kontur", name + ".svg")
    icon = QIcon()
    if os.path.exists(path):
        try:
            from PySide6.QtSvg import QSvgRenderer
        except ImportError:
            _cache[key] = icon
            return icon
        with open(path, encoding="utf-8") as f:
            svg = f.read().replace("currentColor", col.name())
        r = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        vb = r.viewBoxF()
        dpr = 2.0                                           # ostre na ekranach HiDPI
        for size in (16, 20, 24, 32, 48):
            pm = QPixmap(int(size * dpr), int(size * dpr))
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing)
            s = size * dpr / max(vb.width(), vb.height())
            w, h = vb.width() * s, vb.height() * s
            r.render(p, QRectF((size * dpr - w) / 2, (size * dpr - h) / 2, w, h))
            p.end()
            pm.setDevicePixelRatio(dpr)
            icon.addPixmap(pm)
    _cache[key] = icon
    return icon


def icon_for_label(text):
    clean = _SYMBOLS.sub("", text or "").strip()
    for label, name in BY_LABEL.items():
        if clean == label or clean.startswith(label):
            return name, clean
    return None, clean


def apply_icons(root, strip_symbols=True):
    """Dodaje ikony do przycisków okna według ich napisów (i zdejmuje symbole typu ▶ ♪)."""
    for b in root.findChildren(QAbstractButton):
        if not b.icon().isNull() or b.text() in ("◀", "▶", "A−", "A+"):
            continue
        name, clean = icon_for_label(b.text())
        if name:
            b.setProperty("fa_name", name)
            b.setIcon(fa_icon(name))
            b.setIconSize(QSize(16, 16))
            if strip_symbols and clean != b.text():
                b.setText(clean)


def set_icon(obj, name):
    """Ustawia ikonę i zapamiętuje jej nazwę (do zmiany motywu w locie)."""
    obj.setProperty("fa_name", name)
    obj.setIcon(fa_icon(name))


def refresh_icons(root):
    """Po zmianie motywu: przerysuj ikony wszystkich przycisków i akcji okna."""
    for obj in root.findChildren(QAbstractButton) + root.findChildren(QAction):
        name = obj.property("fa_name")
        if name:
            obj.setIcon(fa_icon(name))
