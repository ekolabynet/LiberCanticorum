#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Autorzy projektu Liber Canticorum
#
# Ten program jest wolnym oprogramowaniem: możesz go rozprowadzać i/lub modyfikować na warunkach
# Powszechnej Licencji Publicznej GNU (GNU GPL) w wersji 3 lub (według twojego wyboru) dowolnej
# późniejszej. Program rozpowszechniany jest BEZ JAKIEJKOLWIEK GWARANCJI – szczegóły w pliku LICENSE.
"""
Liber Canticorum – wolny śpiewnik liturgiczny dla muzyków, chórów i wspólnot Kościoła, wersja 0.15.1 (Qt6 / PySide6)
(łac. „księga pieśni”; liber – księga, a zarazem echo libre – wolny)

Następca skryptu SLAJDY_Generator_Binder 6.1:
- baza pieśni (SQLite, jeden plik) z wyszukiwaniem po tytule, tekście i tagach
  (bez względu na polskie znaki),
- import z DOCX / ODT / PDF / TXT / HTML, ze strony WWW oraz z plików JSON v6.1,
- podgląd na żywo, pokaz pełnoekranowy (także na drugim ekranie / rzutniku),
- eksport do PDF (wbudowany, bez LibreOffice) i PPTX (python-pptx),
- zestaw pieśni (np. na mszę): pokaz lub eksport w jednym pliku,
- kategorie i tagi, tła graficzne, eksport DOCX dostępny dla czytników ekranu (niewidomi),
- załączniki: nuty PDF, MuseScore, MusicXML, MIDI (moduł nut z odtwarzaczem głosów SATB),
- moduł YouTube: wyszukiwanie nagrań, odtwarzanie wideo lub samego dźwięku przy czystym tle.

Zależności: PySide6-Essentials (wymagane); python-pptx, python-docx, pypdf, mido, numpy,
sounddevice (poszczególne funkcje); PySide6-Addons (opcjonalnie: odtwarzacz YouTube w oknie).
"""

import datetime
import html as H

import json
import math
import os
import re
import shutil
import sqlite3
import sys
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser

import tempfile
import threading

from PySide6.QtCore import Qt, QRectF, QSizeF, QMarginsF, QTimer, Signal, QSettings, QSize, QUrl, QStringListModel
from PySide6.QtGui import (QAction, QColor, QDesktopServices, QFont, QGuiApplication, QIcon, QImage,
                           QKeySequence, QPainter, QPageSize, QPdfWriter, QPixmap, QTextBlockFormat,
                           QTextCharFormat, QTextCursor, QTextDocument, QTextOption)
from PySide6.QtWidgets import (QApplication, QCheckBox, QColorDialog, QComboBox, QCompleter, QDialog,
                               QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFontComboBox,
                               QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QInputDialog,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
                               QMessageBox, QToolButton, QPlainTextEdit, QPushButton, QSpinBox, QSplitter, QTabWidget, QTextBrowser,
                               QToolBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, QAbstractItemView)

APP_NAME = "Liber Canticorum"
APP_MOTTO = "wolny śpiewnik liturgiczny dla muzyków, chórów i wspólnot Kościoła"
VERSION = "0.29.1"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
BG_DIR = os.path.join(APP_DIR, "tla")

# kafle „Wesprzyj” na ekranie Start: (ikona, tytuł, opis, adres). Adresy można zmienić w pliku wsparcie.json obok programu.
COPYRIGHT_HTML = """
<h2>Prawa autorskie do pieśni – krótko i życzliwie</h2>
<p>Program jest wolny, ale <b>teksty, melodie i nuty, które do niego wpisujesz, mają swoich autorów</b>.
Prawa do pieśni bywają złożone – jedna pieśń to często kilka utworów naraz:</p>
<ul>
<li><b>tekst</b> (autor słów, a w pieśniach tłumaczonych – także tłumacz),</li>
<li><b>melodia</b> (kompozytor),</li>
<li><b>opracowanie</b> – harmonizacja, aranżacja na chór lub organy, akompaniament,</li>
<li><b>wydanie</b> – redakcja tekstu, skład nut, opracowanie śpiewnika.</li>
</ul>
<p>Majątkowe prawa autorskie wygasają co do zasady <b>70 lat od śmierci twórcy</b> (a w pieśni napisanej razem przez
autora słów i kompozytora – od śmierci tego z nich, który zmarł później; art. 36 ustawy o prawie autorskim).
Dawna pieśń może więc być wolna, a jej <b>współczesne wydanie, nowy przekład czy harmonizacja – nie</b>.
Pieśni „ludowe” i „tradycyjne” też mają często nowsze, chronione wersje tekstu.</p>
<p>Ustawa pozwala <b>korzystać z utworów podczas ceremonii religijnych</b>, jeżeli nie łączy się z tym osiąganie
pośrednio lub bezpośrednio korzyści majątkowej (art. 31 ust. 1). Co innego jednak koncerty, nagrania udostępniane
w internecie, transmisje, kopiowanie i rozpowszechnianie śpiewników czy nut – tu zwykle potrzebna jest zgoda
autorów lub wydawców (np. przez ZAiKS albo bezpośrednio). Teksty liturgiczne (czytania, psalmy, modlitwy) należą
do wydawców ksiąg liturgicznych.</p>
<p><b>Prosimy:</b> szanuj pracę autorów i wydawców – podawaj źródło (w uwagach pieśni), nie publikuj w sieci cudzych
nut i nagrań bez zgody, a śpiewniki z programu (PDF, HTML) traktuj jako pomoc dla własnej wspólnoty.
To nie jest porada prawna – w razie wątpliwości zapytaj wydawcę, ZAiKS albo prawnika.</p>

<h2>Dobre źródła tekstów i nut</h2>
<p>Najlepiej korzystać ze <b>sprawdzonych, starannie opracowanych wydań</b> – mają poprawne teksty, zatwierdzone
do liturgii, i opisane źródła:</p>
<ul>
<li><b>Śpiewnik kościelny ks. Jana Siedleckiego</b> – <a href="https://spiewniksiedleckiego.pl/">spiewniksiedleckiego.pl</a>
(teksty z nagraniami melodii),</li>
<li><b>Śpiewnik Liturgiczny</b> (Lublin, KUL) – wydanie zatwierdzone do liturgii,</li>
<li><b>Mszał, Lekcjonarz, Graduał</b> – teksty liturgiczne (śpiewy międzylekcyjne, antyfony),</li>
<li>nuty w domenie publicznej: <a href="https://www.cpdl.org/">CPDL</a> (chóralne),
<a href="https://imslp.org/">IMSLP</a>; na <a href="https://musescore.com/">MuseScore</a> sprawdzaj licencję opracowania.</li>
</ul>
<p>Wszystkie śpiewy przeznaczone do liturgii powinny mieć aprobatę Konferencji Episkopatu Polski albo władzy
diecezjalnej (Instrukcja Episkopatu Polski z 1979 r., n. 10).</p>

<h2>Podziel się własną pracą</h2>
<p>Wpisałeś melodię albo przygotowałeś własne opracowanie (na scholę, chór, organy)? <b>Udostępnij je na
<a href="https://musescore.com/">MuseScore.com</a> z licencją otwartą</b> – CC0 (domena publiczna) albo CC BY /
CC BY-SA – żeby mogły z niej korzystać inne wspólnoty. W edytorze melodii: „🌍 Udostępnij na MuseScore.com…”.
Udostępniaj tylko to, do czego masz prawo: własne opracowania i melodie z domeny publicznej; w opisie podaj
źródło melodii i słów.</p>

<h2>Dokumenty Kościoła o muzyce</h2>
<ul>
<li>Sobór Watykański II, konstytucja <i>Sacrosanctum Concilium</i> (1963), rozdz. VI „Muzyka sakralna” – podstawa,</li>
<li>Instrukcja <i>Musicam sacram</i> (1967) – <a href="https://musicamsacram.pl/dokumenty/pobierz/ins">tekst</a>,</li>
<li>Instrukcja Episkopatu Polski o muzyce liturgicznej po Soborze Watykańskim II (1979) –
<a href="https://musicamsacram.pl/dokumenty/pobierz/instr79">tekst</a>,</li>
<li>św. Jan Paweł II, <i>List do artystów</i> (1999),</li>
<li>św. Jan Paweł II, <i>Chirograf na stulecie motu proprio „Tra le sollecitudini” o muzyce sakralnej</i> (22.11.2003)
– w serwisie <a href="https://www.vatican.va/">vatican.va</a>,</li>
<li>Benedykt XVI, adhortacja <i>Sacramentum caritatis</i> (2007), n. 42 – o śpiewie liturgicznym,</li>
<li><b>Instrukcja Konferencji Episkopatu Polski o muzyce kościelnej</b> (14.10.2017) – obowiązująca w Polsce –
<a href="https://musicamsacram.pl/dokumenty/pobierz/instr2017">tekst</a>,</li>
<li>Franciszek, list apostolski <i>Desiderio desideravi</i> o formacji liturgicznej (2022).</li>
</ul>
<p>Ustawa o prawie autorskim i prawach pokrewnych (tekst jednolity Dz.U. 2025 poz. 24):
<a href="https://api.sejm.gov.pl/eli/acts/DU/2025/24/text.pdf">PDF</a>.</p>
"""


SUPPORT = [
    ("🤍", "Wesprzyj Ośrodek dla Niewidomych w Laskach",
     "Ośrodek założony przez bł. Matkę Elżbietę Różę Czacką. Towarzystwo Opieki nad Ociemniałymi – szkoła i dom dla niewidomych dzieci. 1,5% podatku: KRS 0000054086.",
     "https://laski.edu.pl/",
     {'odbiorca': "Towarzystwo Opieki nad Ociemniałymi Stowarzyszenie, ul. Brzozowa 75, Laski, 05-080 Izabelin",
      'konta': [("mBank S.A. – konto do darowizn", "02 1140 1010 0000 4399 5800 1002")],
      'tytul': "Darowizna na cele statutowe",
      'inne': "BLIK na telefon: 572 896 588 · 1,5% podatku: KRS 0000054086",
      'zrodlo': "laski.edu.pl/kontakt"}),
    ("⛪", "Wesprzyj Parafię M.B. Królowej Meksyku",
     "Parafia Matki Bożej Królowej Meksyku (z Guadalupe) w Laskach, ul. 3 Maja 40/42.",
     "https://parafiawlaskach.pl/",
     {'odbiorca': "Parafia Matki Bożej Królowej Meksyku, ul. 3 Maja 40/42, 05-080 Laski",
      'konta': [("PKO BP", "18 1020 1026 0000 1102 0016 9920")],
      'szukaj_parafii': True,
      'tytul': "Ofiara na rzecz parafii",
      'zrodlo': "parafiawlaskach.pl/kontakt"}),
    ("ikony/adhoc_znak.png", "Wesprzyj Scholę adHoc",
     "Kochamy muzykę – zwłaszcza chóralną i tę, która towarzyszy liturgii – i nie możemy nie śpiewać :-). Śpiewem służymy wspólnocie parafii M.B. Królowej Meksyku w Laskach; promienie w naszym logo to zachwyt nad niepojętym działaniem Boga. Jesteśmy odpowiedzialni za Mszę o bogactwo łaski dla rodzin – byłych, obecnych i przyszłych, we wszystkich ich potrzebach (to nie jest prosperity gospel :-) ). Modlimy się także za Twoją rodzinę ;-).",
     "https://dowiaryprzezliturgie.pl/adhoc/",
     {'zaangazuj': "Najlepiej wesprzesz nas, śpiewając razem z nami: na Mszy w I niedzielę miesiąca w samo południe w kościele w Laskach (ul. 3 Maja 40/42), a próby mamy we wtorki o 19:00 w domu parafialnym. Zaproś też znajomych i rodzinę! Mieszkasz daleko – choćby na innym kontynencie? Módl się razem z nami w I niedzielę miesiąca i przyślij swoją intencję (kontakt na stronie scholi) – polecimy ją Bogu na Mszy.",
      'baner': "ikony/adhoc_baner.png"}),
    ("🌹", "Wesprzyj projekt Guadalupe500.org",
     "Nowa muzyka na 500-lecie objawień Matki Bożej na wzgórzu Tepeyac w Meksyku (w przygotowaniu).",
     "https://guadalupe500.org/",
     {'zaangazuj': "Komponujesz, śpiewasz, grasz, piszesz teksty albo tłumaczysz? Włącz się w przygotowanie nowej muzyki "
                   "na 500-lecie objawień Matki Bożej z Guadalupe (1531–2031). Zajrzyj na stronę projektu "
                   "i módl się z nami w tej intencji."}),
]


def support_url(title, default):
    """Adres z pliku wsparcie.json (obok programu), jeśli jest – inaczej domyślny."""
    try:
        with open(os.path.join(APP_DIR, "wsparcie.json"), encoding="utf-8") as f:
            return json.load(f).get(title, default)
    except (OSError, ValueError):
        return default


DEFAULT_CATEGORIES = [
    "Adwent", "Boże Narodzenie", "Wielki Post", "Triduum Paschalne", "Wielkanoc", "Zesłanie Ducha Świętego",
    "Okres zwykły", "Maryjne", "Eucharystyczne", "Do Serca Pana Jezusa", "O świętych",
    "Psalmy i śpiewy przed Ewangelią", "Części stałe Mszy", "Uwielbienie", "Pogrzebowe", "Ślubne",
    "Okolicznościowe", "Dla dzieci", "Inne",
]
DEFAULT_TAGS = ["wejście", "przygotowanie darów", "komunia", "dziękczynienie", "zakończenie", "psalm",
                "kyrie", "gloria", "sanctus", "agnus dei", "alleluja", "przed mszą", "po mszy",
                "kanon", "taizé", "schola", "chór", "dzieci", "młodzież", "łacina", "tradycyjna"]
# Zestaw na Mszę: (część, czy może mieć kilka pieśni). Części stałe oraz melodia psalmu i aklamacji – jedna pozycja.
MASS_PARTS = [("Przed mszą", True), ("Wejście", True), ("Kyrie", False), ("Gloria", False), ("Psalm", False),
              ("Alleluja", False), ("Ofiarowanie", True), ("Sanctus", False), ("Agnus Dei", False),
              ("Komunia", True), ("Uwielbienie", True), ("Wyjście", True), ("Po mszy", True)]
DEFAULT_MASS_PARTS = list(MASS_PARTS)
MASS_MULTI = dict(MASS_PARTS)
FREE_PART = "Utwory"                         # zestaw bez okazji (koncert, próba, nabożeństwo): jedna lista
MASS_MULTI[FREE_PART] = True
ORDINARY = ("Kyrie", "Gloria", "Sanctus", "Agnus Dei")
NOTE_FIELDS = (("wykonawca", "Wykonawca"), ("tonacja", "Tonacja"), ("uwagi", "Uwagi"),
               ("zwroc", "Na co zwrócić uwagę"))


SPIEWNIKI_ADRESY = (("siedlecki", "Siedlecki"), ("niezbednik", "Niezbędnik Katolika"),
                    ("niepojeta", "Niepojęta Trójco"), ("spiewnik-oazowy", "Śpiewnik oazowy"),
                    ("oaza", "Śpiewnik oazowy"), ("spiewnikreligijny", "Śpiewnik religijny"),
                    ("liturgia.pl", "Liturgia.pl"), ("adonai", "Adonai.pl"), ("wywrota", "Wywrota"))


def guess_spiewnik(zrodlo):
    """Nazwa źródła (śpiewnika) z adresu strony albo nazwy pliku importu – albo ""."""
    z = fold(zrodlo or "")
    if not z:
        return ""
    for key, name in SPIEWNIKI_ADRESY:
        if key in z:
            return name
    m = re.match(r"https?://(?:www\.)?([^/]+)", (zrodlo or "").strip(), re.I)
    return m.group(1) if m else ""


def source_combo(db, keep=None, all_label="Wszystkie źródła"):
    """Lista wyboru źródła (śpiewnika) – data: None = wszystkie, '' = bez źródła."""
    c = QComboBox()
    c.setProperty("i18n_no", True)
    c.setToolTip("Źródło pieśni – śpiewnik, zbiór")
    from modul_i18n import tr as _t
    c.addItem(_t(all_label), None)
    for name, n in db.sources():
        c.addItem(f"{name or _t('(bez źródła)')}  ({n})", name)
    k = c.findData(keep) if keep is not None else 0
    c.setCurrentIndex(max(0, k))
    return c


def notes_text(notes, sep="\n"):
    return sep.join(f"{lab}: {notes[k]}" for k, lab in NOTE_FIELDS if (notes or {}).get(k))


def apply_mass_parts(parts):
    """Własne części Mszy (kolejność, nazwy, „kilka pieśni”) – zmienia listę dla całego programu."""
    parts = [(str(n).strip(), bool(m)) for n, m in parts if str(n).strip()] or list(DEFAULT_MASS_PARTS)
    MASS_PARTS[:] = parts
    MASS_MULTI.clear()
    MASS_MULTI.update(dict(DEFAULT_MASS_PARTS))
    MASS_MULTI.update(dict(parts))
    MASS_MULTI[FREE_PART] = True


def load_mass_parts():
    try:
        raw = QSettings("LiberCanticorum", "LiberCanticorum").value("mass_parts", "")
        if raw:
            apply_mass_parts(json.loads(raw))
    except (ValueError, TypeError):
        pass          # części stałe – razem z jednej mszy („jeden motyw”)
# po czym rozpoznać część: (początki tytułu, tagi / kategorie) – wszystko po fold()
PART_HINTS = {
    "Kyrie": (("kyrie", "panie zmiluj sie"), ("kyrie",)),
    "Gloria": (("gloria", "chwala na wysokosci"), ("gloria",)),
    "Sanctus": (("sanctus", "swiety, swiety", "swiety swiety"), ("sanctus", "swiety")),
    "Agnus Dei": (("agnus dei", "baranku bozy"), ("agnus dei", "agnus", "baranku bozy")),
    "Psalm": (("psalm", "melodia psalmu"), ("psalm", "psalmy", "melodia psalmu", "psalmy i spiewy przed ewangelia")),
    "Alleluja": (("alleluja", "aklamacja", "melodia aklamacji"), ("alleluja", "aklamacja", "melodia aklamacji",
                                                                  "spiew przed ewangelia")),
    "Przed mszą": ((), ("przed msza",)),
    "Wejście": ((), ("wejscie", "na wejscie")),
    "Ofiarowanie": ((), ("ofiarowanie", "przygotowanie darow")),
    "Komunia": ((), ("komunia", "na komunie")),
    "Uwielbienie": ((), ("uwielbienie", "dziekczynienie")),
    "Wyjście": ((), ("wyjscie", "zakonczenie", "na zakonczenie")),
    "Po mszy": ((), ("po mszy",)),
}
PART_TAGS = {t for _, tags in PART_HINTS.values() for t in tags}


def guess_mass_part(song):
    """Na którą część Mszy pasuje pieśń (z tytułu, tagów, kategorii) – albo None."""
    title = fold(song.get('title', '') or '')
    tags = [fold(t) for t in (song.get('tagi', '') or '').split(',') if t.strip()] + [fold(song.get('kategoria', '') or '')]
    for part, (starts, tg) in PART_HINTS.items():          # najpierw tytuł (np. „Alleluja” w kategorii psalmów)
        if any(title.startswith(x) for x in starts):
            return part
    for part, (starts, tg) in PART_HINTS.items():
        if any(t in tg for t in tags):
            return part
    return None


SCORE_EXT = ('.mscz', '.mscx', '.musicxml', '.mxl', '.xml')     # pliki MuseScore / MusicXML
ATTACH_KINDS = {'.pdf': 'Nuty PDF', '.mscz': 'MuseScore', '.mscx': 'MuseScore', '.musicxml': 'MusicXML',
                '.mxl': 'MusicXML', '.xml': 'MusicXML', '.mid': 'MIDI', '.midi': 'MIDI', '.kar': 'MIDI',
                '.mp3': 'Nagranie', '.ogg': 'Nagranie', '.wav': 'Nagranie', '.flac': 'Nagranie', '.m4a': 'Nagranie',
                '.png': 'Obraz', '.jpg': 'Obraz', '.jpeg': 'Obraz'}

DEFAULT_CFG = {
    'format': '16:9', 'refren_osobno': False, 'powtarzaj_refren': True, 'refren_na_koncu': False,
    'zwrotek_na_slajd': 2, 'auto_interpunkcja': True, 'reflow': True, 'numeruj': True,
    'auto_size': True, 'jednolity_rozmiar': True, 'font_scale': 1.0, 'font_size': 54,
    'max_font': 80, 'font': 'Arial',
    'kolor_tekstu': '#ffffff', 'kolor_refrenu': '#ffff99', 'kolor_tla': '#000000',
    'tlo': '', 'przyciemnienie': 25, 'cien': True, 'margines_x': 7, 'margines_y': 5,
}

# =====================================================================
# 1. TEKST: normalizacja, rozbiór pieśni, przygotowanie bloków
# =====================================================================

_FOLD = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def fold(text):
    """Do wyszukiwania: małe litery, bez polskich znaków i interpunkcji."""
    t = (text or "").translate(_FOLD).lower()
    return re.sub(r'[^a-z0-9]+', ' ', t).strip()


def sanitize_name(name):
    name = name.translate(_FOLD).replace(' ', '_')
    return re.sub(r'[^a-zA-Z0-9_\-]', '', name) or "piesn"


RE_REF = re.compile(r'^(?:ref(?:ren)?\s*\.?\s*:?|r\s*[.:])\s*(.*)$', re.I)
RE_NUM = re.compile(r'^(\d{1,2})\s*[.)]\s*(.*)$')
RE_META = re.compile(r'^(?:\(.*\)|\[.*\]|[\w.]{1,10}\s*(?:pol\.)?\s*:\s.*|(?:sł|muz|tekst|melodia|t|m)\.?\s*:.*)$', re.I)


def tidy_line(line):
    line = line.replace(' ', ' ').replace('\t', ' ')
    line = re.sub(r'([,;:!?])(?=[^\s\d,.;:!?»”"\)\]])', r'\1 ', line)   # "Usłysz,Panie" -> "Usłysz, Panie"
    return re.sub(r'\s{2,}', ' ', line).strip()


def clean_title(t):
    t = t.strip().strip('„”"“\'«»')
    t = re.sub(r'[„”"“«»]', '', t)
    t = re.sub(r'\s*[-–—]\s*tekst( pie[sś]ni)?\s*$', '', t, flags=re.I)
    t = t.strip().rstrip(',.;:').strip()
    if t.isupper() and len(t) > 3:
        t = t[:1] + t[1:].lower()
    return t


def parse_song_text(text, first_line_is_title=True, title=""):
    """Dzieli surowy tekst na: tytuł, refren, zwrotki (surowe), uwagi."""
    lines = [l.replace(' ', ' ').rstrip() for l in text.replace('\r\n', '\n').replace('\r', '\n').split('\n')]
    nonempty = [l for l in lines if l.strip()]
    # tekst "z Worda" z pustą linią po każdym akapicie -> puste linie nic nie znaczą
    blanks = sum(1 for i in range(1, len(lines)) if not lines[i].strip() and lines[i - 1].strip())
    if nonempty and blanks >= 0.7 * len(nonempty):
        lines = nonempty
    if first_line_is_title:
        while lines and not lines[0].strip():
            lines.pop(0)
        if lines:
            t = lines.pop(0)
            title = title or t
    title = clean_title(title)

    pre, notes, ref, verses = [], [], [], []
    cur = None          # 'ref' | 'verse' | 'skip'
    numbered = False
    for raw in lines:
        line = tidy_line(raw)
        if not line:
            if cur in ('ref', 'verse', 'skip'):
                cur = None
            if cur is None and pre and pre[-1] != "":
                pre.append("")
            continue
        m_ref, m_num = RE_REF.match(line), RE_NUM.match(line)
        if m_ref:
            rest = m_ref.group(1).strip()
            if not ref:
                if rest:
                    ref.append(rest)
                cur = 'ref'
            else:
                cur = 'skip'            # powtórzony refren / samo "Ref."
            continue
        if m_num:
            numbered = True
            verses.append([f"{int(m_num.group(1))}. {m_num.group(2).strip()}".strip()])
            cur = 'verse'
            continue
        if not ref and not verses and RE_META.match(line):
            notes.append(line)
            continue
        if cur == 'ref':
            ref.append(line)
        elif cur == 'verse':
            verses[-1].append(line)
        elif cur == 'skip':
            continue
        elif ref or verses:             # nowa, nienumerowana zwrotka
            verses.append([line])
            cur = 'verse'
        else:
            pre.append(line)

    pre_blocks = [b for b in "\n".join(pre).split("\n\n") if b.strip()]
    if not ref and not verses:
        verses = [b.split("\n") for b in pre_blocks]
    else:
        notes += [b.replace("\n", " ") for b in pre_blocks]

    ref_txt = "\n".join(ref).replace(" * ", "\n").replace("*", "").strip()
    zw_txt = "\n\n".join("\n".join(v) for v in verses).strip()
    if not title:
        title = clean_title((ref + [l for v in verses for l in v] + ["Bez tytułu"])[0])[:60]
    return {'title': title, 'refren': ref_txt, 'zwrotki_raw': zw_txt, 'uwagi': " | ".join(notes),
            'config': dict(DEFAULT_CFG, numeruj=numbered or len(verses) > 1)}


def clean_refren_text(text):
    return re.sub(r'^(?:ref(?:ren)?\s*\.?\s*:?|r\s*[.:])\s*', '', text.strip(), flags=re.I)


def smart_punctuate_lines(text_block):
    lines = [l.strip() for l in text_block.splitlines() if l.strip()]
    out = []
    for i, line in enumerate(lines):
        if not line.endswith(('.', ',', ';', ':', '!', '?', '-', '–')):
            line += '.' if i == len(lines) - 1 else ','
        out.append(line)
    return out


def process_verses(raw_text, auto_punctuate=True, reflow=True):
    processed = re.sub(r'(?m)^(\d+\.)', r'\n\n\1', raw_text or "")
    blocks = [b.strip() for b in processed.replace('\r\n', '\n').split('\n\n') if b.strip()]
    result = []
    for block in blocks:
        lines = smart_punctuate_lines(block) if auto_punctuate else [l.strip() for l in block.splitlines() if l.strip()]
        result.append(" ".join(lines) if reflow else "\n".join(lines))
    return result


def song_cfg(song):
    cfg = dict(DEFAULT_CFG)
    cfg.update(song.get('config') or {})
    return cfg


def song_slide_items(song):
    """Lista slajdów; slajd = lista (rodzaj, tekst), rodzaj: 'ref' lub 'verse'."""
    cfg = song_cfg(song)
    verses = process_verses(song.get('zwrotki_raw', ''), cfg['auto_interpunkcja'], cfg['reflow'])
    if cfg['numeruj']:
        verses = [v if re.match(r'^\d+\.', v) else f"{i + 1}. {v}" for i, v in enumerate(verses)]
    ref = clean_refren_text(song.get('refren', ''))
    if ref:
        rl = smart_punctuate_lines(ref) if cfg['auto_interpunkcja'] else [l.strip() for l in ref.splitlines() if l.strip()]
        ref = " ".join(rl) if cfg['reflow'] else "\n".join(rl)
    n = max(1, int(cfg['zwrotek_na_slajd']))
    slides = []
    for i in range(0, len(verses), n):
        batch = [('verse', v) for v in verses[i:i + n]]
        with_ref = bool(ref) and (i == 0 or cfg['powtarzaj_refren'])
        if with_ref and cfg['refren_osobno']:
            slides += [[('ref', ref)], batch]
        elif with_ref:
            slides.append([('ref', ref)] + batch)
        else:
            slides.append(batch)
    if ref and (not verses or cfg['refren_na_koncu']):
        slides.append([('ref', ref)])
    return slides


# =====================================================================
# 2. UKŁAD SLAJDU (Qt) – dopasowanie czcionki, rysowanie
# =====================================================================

H_LOGICAL = 1080           # współrzędne logiczne slajdu; 1 px = 0,5 pt w PPTX


@dataclass
class Slide:
    items: list
    cfg: dict
    W: int = 1920
    H: int = H_LOGICAL
    px: int = 0
    doc: QTextDocument = None
    title: str = ""
    index_in_song: int = 0
    song_id: int = None

    @property
    def mx(self):
        return self.W * float(self.cfg.get('margines_x', 7)) / 100

    @property
    def my(self):
        return self.H * float(self.cfg.get('margines_y', 5)) / 100


def slide_dims(cfg):
    return (1440, H_LOGICAL) if cfg.get('format') == '4:3' else (1920, H_LOGICAL)


def make_doc(items, px, cfg, width):
    doc = QTextDocument()
    doc.setDocumentMargin(0)
    font = QFont(cfg['font'])
    font.setPixelSize(max(1, int(px)))
    font.setBold(True)
    doc.setDefaultFont(font)
    opt = QTextOption(Qt.AlignHCenter)
    opt.setWrapMode(QTextOption.WordWrap)
    doc.setDefaultTextOption(opt)
    cur = QTextCursor(doc)
    for i, (kind, text) in enumerate(items):
        bf = QTextBlockFormat()
        bf.setAlignment(Qt.AlignHCenter)
        bf.setBottomMargin(px * 0.45 if i < len(items) - 1 else 0)
        cf = QTextCharFormat()
        cf.setFont(font)
        cf.setForeground(QColor(cfg['kolor_refrenu'] if kind == 'ref' else cfg['kolor_tekstu']))
        if i == 0:
            cur.setBlockFormat(bf)
            cur.setBlockCharFormat(cf)
        else:
            cur.insertBlock(bf, cf)
        cur.insertText(text.replace('\n', ' '), cf)
    doc.setTextWidth(width)
    return doc


def fit_px(items, cfg, W, H):
    aw = W * (1 - 2 * float(cfg.get('margines_x', 7)) / 100)
    ah = H * (1 - 2 * float(cfg.get('margines_y', 5)) / 100)

    def fits(px):
        d = make_doc(items, px, cfg, aw)
        return d.size().height() <= ah and d.idealWidth() <= aw + 0.5

    lo, hi = 12, max(14, int(cfg['max_font']) * 2)
    if not fits(lo):
        return lo
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if fits(mid):
            lo = mid
        else:
            hi = mid - 1
    return lo


def build_song_deck(song):
    cfg = song_cfg(song)
    W, H = slide_dims(cfg)
    all_items = song_slide_items(song)
    if not all_items:
        return [], 0
    if cfg['auto_size']:
        sizes = [fit_px(it, cfg, W, H) for it in all_items]
        if cfg['jednolity_rozmiar']:
            sizes = [min(sizes)] * len(sizes)
        sizes = [max(8, math.floor(s * float(cfg['font_scale']))) for s in sizes]
    else:
        sizes = [int(cfg['font_size']) * 2] * len(all_items)
    deck = []
    for i, (items, px) in enumerate(zip(all_items, sizes)):
        s = Slide(items=items, cfg=cfg, W=W, H=H, px=px, title=song.get('title', ''), index_in_song=i,
                  song_id=song.get('id'))
        s.doc = make_doc(items, px, cfg, W - 2 * s.mx)
        deck.append(s)
    return deck, min(sizes) // 2


def blank_slide(cfg, title=""):
    W, H = slide_dims(cfg)
    return Slide(items=[], cfg=cfg, W=W, H=H, title=title)


def build_set_deck(songs, separator=True):
    deck = []
    for k, song in enumerate(songs):
        d, _ = build_song_deck(song)
        if separator and k > 0:
            deck.append(blank_slide(song_cfg(song), "— przerwa —"))
        deck += d
    return deck


_BG_CACHE = {}
_BG_LIGHT = {}


def background_presets():
    """Zalecane kolory i marginesy dla teł (tla/tla.json, tworzy generuj_tla.py)."""
    try:
        with open(os.path.join(BG_DIR, "tla.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def is_light_color(c):
    c = QColor(c)
    return 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue() > 140


def list_backgrounds():
    """Nazwy teł z folderu tla/ (bez sufiksu proporcji)."""
    names = set()
    if os.path.isdir(BG_DIR):
        for f in os.listdir(BG_DIR):
            base, ext = os.path.splitext(f)
            if ext.lower() in ('.jpg', '.jpeg', '.png'):
                names.add(re.sub(r'_(16x9|4x3)$', '', base))
    return sorted(names)


def resolve_background(name, W, H):
    """Ścieżka pliku tła dla danej proporcji (nazwa z folderu tla/ albo pełna ścieżka)."""
    if not name:
        return None
    if os.path.isabs(name) and os.path.exists(name):
        return name
    tag = '4x3' if abs(W / H - 4 / 3) < 0.05 else '16x9'
    for cand in (f"{name}_{tag}", name, f"{name}_16x9", f"{name}_4x3"):
        for ext in ('.jpg', '.jpeg', '.png'):
            path = os.path.join(BG_DIR, cand + ext)
            if os.path.exists(path):
                return path
    return None


def background_image(slide):
    path = resolve_background(slide.cfg.get('tlo', ''), slide.W, slide.H)
    if not path:
        return None
    img = _BG_CACHE.get(path)
    if img is None:
        img = QImage(path)
        if img.isNull():
            return None
        _BG_CACHE[path] = img
    return img


def background_is_light(slide):
    img = background_image(slide)
    if img is None:
        return is_light_color(slide.cfg['kolor_tla'])
    key = img.cacheKey()
    if key not in _BG_LIGHT:
        px = img.scaled(1, 1, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).pixelColor(0, 0)
        _BG_LIGHT[key] = is_light_color(px)
    return _BG_LIGHT[key]


def paint_background(p, slide, rect):
    p.fillRect(rect, QColor(slide.cfg['kolor_tla']))
    img = background_image(slide)
    if img is not None:
        # "cover": wypełnij cały slajd, przytnij nadmiar
        sc = max(rect.width() / img.width(), rect.height() / img.height())
        sw, sh = rect.width() / sc, rect.height() / sc
        src = QRectF((img.width() - sw) / 2, (img.height() - sh) / 2, sw, sh)
        p.drawImage(rect, img, src)
        dim = int(slide.cfg.get('przyciemnienie', 0))
        if dim > 0:                     # wyciszenie: ciemne tło przyciemniamy, jasne – rozjaśniamy
            veil = QColor('#f6eed9') if background_is_light(slide) else QColor(0, 0, 0)
            veil.setAlpha(int(255 * dim / 100))
            p.fillRect(rect, veil)


def shadow_doc(slide, light=False):
    if getattr(slide, '_shadow', None) is None:
        d = slide.doc.clone()
        c = QTextCursor(d)
        c.select(QTextCursor.Document)
        cf = QTextCharFormat()
        cf.setForeground(QColor(250, 244, 228, 150) if light else QColor(0, 0, 0, 190))
        c.mergeCharFormat(cf)
        slide._shadow = d
    return slide._shadow


def paint_slide(p, slide, target, black=False, clean=False):
    """Rysuje slajd w prostokącie target (zachowuje proporcje, czarne pasy).
    black – cały ekran czarny; clean – samo tło bez tekstu."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.fillRect(target, Qt.black)
    if slide is None or black:
        p.restore()
        return
    s = min(target.width() / slide.W, target.height() / slide.H)
    w, h = slide.W * s, slide.H * s
    x0, y0 = target.x() + (target.width() - w) / 2, target.y() + (target.height() - h) / 2
    paint_background(p, slide, QRectF(x0, y0, w, h))
    if slide.doc is not None and not clean:
        p.translate(x0, y0)
        p.scale(s, s)
        p.translate(slide.mx, (slide.H - slide.doc.size().height()) / 2)
        if slide.cfg.get('cien') and slide.cfg.get('tlo'):
            if is_light_color(slide.cfg['kolor_tekstu']):          # jasny tekst: cień w prawo-dół
                off = max(2.0, slide.px * 0.045)
                p.translate(off, off)
                shadow_doc(slide).drawContents(p)
                p.translate(-off, -off)
            else:                                                   # ciemny tekst: jasna poświata dookoła
                off = max(1.5, slide.px * 0.035)
                halo = shadow_doc(slide, light=True)
                for dx, dy in ((off, 0), (-off, 0), (0, off), (0, -off), (off, off), (-off, -off), (off, -off), (-off, off)):
                    p.translate(dx, dy)
                    halo.drawContents(p)
                    p.translate(-dx, -dy)
        slide.doc.drawContents(p)
    p.restore()


def background_layer_file(slide, cache):
    """Tło (z przyciemnieniem) jako plik JPG – do PPTX."""
    path = resolve_background(slide.cfg.get('tlo', ''), slide.W, slide.H)
    if not path:
        return None
    key = (path, int(slide.cfg.get('przyciemnienie', 0)), slide.W, slide.H, slide.cfg['kolor_tla'])
    if key not in cache:
        img = QImage(slide.W, slide.H, QImage.Format_RGB32)
        p = QPainter(img)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        paint_background(p, slide, QRectF(0, 0, slide.W, slide.H))
        p.end()
        fd, out = tempfile.mkstemp(suffix='.jpg', prefix='spiewnik_tlo_')
        os.close(fd)
        img.save(out, 'JPG', 88)
        cache[key] = out
    return cache[key]


def slide_pixmap(slide, w=320):
    h = int(w * slide.H / slide.W)
    pm = QPixmap(w, h)
    pm.fill(Qt.black)
    p = QPainter(pm)
    paint_slide(p, slide, QRectF(0, 0, w, h))
    p.end()
    return pm


# =====================================================================
# 3. EKSPORT: PDF (Qt) i PPTX (python-pptx)
# =====================================================================

def export_pdf(deck, path):
    if not deck:
        raise ValueError("Brak slajdów do eksportu.")
    wr = QPdfWriter(path)
    wr.setResolution(150)
    wr.setTitle(deck[0].title)
    wr.setCreator(f"{APP_NAME} {VERSION}")

    def page_size(s):
        return QPageSize(QSizeF(280.0, 280.0 * s.H / s.W), QPageSize.Millimeter, "Slajd")

    wr.setPageSize(page_size(deck[0]))
    wr.setPageMargins(QMarginsF(0, 0, 0, 0))
    p = QPainter(wr)
    for i, s in enumerate(deck):
        if i:
            wr.setPageSize(page_size(s))
            wr.newPage()
        paint_slide(p, s, QRectF(0, 0, wr.width(), wr.height()))
    p.end()


def export_pptx(deck, path):
    try:
        from pptx import Presentation
        from pptx.util import Emu, Pt
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
    except ImportError:
        raise RuntimeError("Eksport PPTX wymaga pakietu python-pptx:\n  pip install python-pptx")
    if not deck:
        raise ValueError("Brak slajdów do eksportu.")
    K = 6350                                    # EMU na piksel logiczny (1080 px = 7,5 cala)
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(deck[0].W * K), Emu(deck[0].H * K)
    layout = prs.slide_layouts[6]
    rgb = lambda c: RGBColor.from_string(QColor(c).name()[1:].upper())
    bg_cache = {}
    for s in deck:
        sl = prs.slides.add_slide(layout)
        sl.background.fill.solid()
        sl.background.fill.fore_color.rgb = rgb(s.cfg['kolor_tla'])
        bg = background_layer_file(s, bg_cache)
        if bg:
            sl.shapes.add_picture(bg, 0, 0, prs.slide_width, prs.slide_height)
        if s.title:
            sl.notes_slide.notes_text_frame.text = s.title
        if not s.items:
            continue
        sx = deck[0].W / s.W                        # inna proporcja niż prezentacja -> skala w poziomie
        mx = s.mx * sx
        tb = sl.shapes.add_textbox(Emu(int(mx * K)), Emu(int(s.my * K)),
                                   Emu(int((deck[0].W - 2 * mx) * K)), Emu(int((s.H - 2 * s.my) * K)))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.NONE
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        pt = s.px * 0.5 * 0.97                     # mały zapas na różnice w renderowaniu
        for j, (kind, text) in enumerate(s.items):
            par = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
            par.alignment = PP_ALIGN.CENTER
            if j < len(s.items) - 1:
                par.space_after = Pt(pt * 0.45)
            for li, line in enumerate(text.split('\n')):
                if li:
                    par.add_line_break()
                r = par.add_run()
                r.text = line
                r.font.size = Pt(pt)
                r.font.bold = True
                r.font.name = s.cfg['font']
                r.font.color.rgb = rgb(s.cfg['kolor_refrenu'] if kind == 'ref' else s.cfg['kolor_tekstu'])
    prs.save(path)
    for f in bg_cache.values():
        try:
            os.remove(f)
        except OSError:
            pass


def export_docx(songs, path, title=None, font_pt=14, subtitle=None):
    """Dokument przyjazny czytnikom ekranu i monitorom brajlowskim:
    prawdziwe nagłówki (nawigacja klawiszem H), język polski, bez tabel, obrazów, kolorów
    i pustych akapitów; wersy zachowane jak w oryginale, refren wyraźnie oznaczony."""
    try:
        from docx import Document
        from docx.shared import Pt
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError:
        raise RuntimeError("Eksport DOCX wymaga pakietu python-docx:\n  pip install python-docx")
    if not songs:
        raise ValueError("Brak pieśni do eksportu.")
    doc = Document()
    title = title or songs[0].get('title', 'Śpiewnik')
    cp = doc.core_properties
    cp.title, cp.language, cp.author = title, 'pl-PL', APP_NAME
    cp.subject = "Teksty pieśni"

    def set_lang(style):
        rpr = style.element.get_or_add_rPr()
        lang = rpr.find(qn('w:lang'))
        if lang is None:
            lang = OxmlElement('w:lang')
            rpr.append(lang)
        for a in ('w:val', 'w:eastAsia', 'w:bidi'):
            lang.set(qn(a), 'pl-PL')

    for name in ('Normal', 'Title', 'Heading 1', 'Heading 2'):
        st = doc.styles[name]
        set_lang(st)
        st.font.name = 'Arial'
        st.font.color.rgb = None
    doc.styles['Normal'].font.size = Pt(font_pt)
    doc.styles['Normal'].paragraph_format.space_after = Pt(font_pt * 0.8)
    doc.styles['Heading 1'].font.size = Pt(font_pt + 6)
    doc.styles['Title'].font.size = Pt(font_pt + 10)
    # ustawienia domyślne dokumentu (docDefaults) też po polsku
    rpr_def = doc.styles.element.find(qn('w:docDefaults'))
    if rpr_def is not None:
        rpr = rpr_def.find(qn('w:rPrDefault'))
        if rpr is not None and rpr.find(qn('w:rPr')) is not None:
            r = rpr.find(qn('w:rPr'))
            lang = r.find(qn('w:lang'))
            if lang is None:
                lang = OxmlElement('w:lang')
                r.append(lang)
            lang.set(qn('w:val'), 'pl-PL')

    def lines_par(label, lines):
        par = doc.add_paragraph()
        if label:
            run = par.add_run(label)
            run.bold = True
            par.add_run().add_break()
        for i, line in enumerate(lines):
            if i:
                par.add_run().add_break()
            par.add_run(line)
        return par

    multi = len(songs) > 1
    if multi:
        doc.add_heading(title, level=0)
        if subtitle:
            doc.add_paragraph(subtitle)
        doc.add_paragraph(f"Liczba pieśni: {len(songs)}. Każda pieśń zaczyna się nagłówkiem pierwszego poziomu.")
    for k, song in enumerate(songs):
        part = f"{song['_czesc']}: " if song.get('_czesc') and song['_czesc'] != FREE_PART else ""
        h = doc.add_heading(f"{k + 1}. {part}{song.get('title', '')}" if multi else song.get('title', ''), level=1)
        if multi and k > 0:
            h.paragraph_format.page_break_before = True
        meta = [x for x in (song.get('kategoria', ''), song.get('uwagi', '')) if x]
        if meta:
            doc.add_paragraph(" • ".join(meta))
        cfg = song_cfg(song)
        ref = clean_refren_text(song.get('refren', ''))
        ref_lines = [l.strip() for l in ref.splitlines() if l.strip()]
        if ref_lines:
            lines_par("Refren:", ref_lines)
        verses = process_verses(song.get('zwrotki_raw', ''), auto_punctuate=False, reflow=False)
        for i, v in enumerate(verses):
            vl = v.split('\n')
            m = re.match(r'^(\d+)\.\s*(.*)$', vl[0])
            if m:
                label, vl[0] = f"Zwrotka {m.group(1)}:", m.group(2)
            else:
                label = f"Zwrotka {i + 1}:" if len(verses) > 1 else None
            lines_par(label, [l for l in vl if l.strip()])
            if ref_lines and cfg.get('powtarzaj_refren') and i < len(verses) - 1:
                doc.add_paragraph("(Refren)")
    doc.save(path)


# ---------------------------------------------------------------------
# Mszalik z pieśniami dla niewidomych (DOCX / TXT / HTML)
# ---------------------------------------------------------------------
MASS_ORDER = [('part', "Przed mszą"), ('part', "Wejście"), ('lit', 'ant_wej'), ('part', "Kyrie"), ('part', "Gloria"),
              ('lit', 'kolekta'), ('lit', 'czyt1'), ('part', "Psalm"), ('lit', 'psalm'), ('lit', 'czyt2'),
              ('lit', 'sekwencja'), ('part', "Alleluja"), ('lit', 'aklamacja'), ('lit', 'ewangelia'),
              ('part', "Ofiarowanie"), ('lit', 'dary'), ('lit', 'prefacja'), ('part', "Sanctus"), ('part', "Agnus Dei"),
              ('lit', 'ant_kom'), ('part', "Komunia"), ('part', "Uwielbienie"), ('lit', 'po_kom'),
              ('part', "Wyjście"), ('part', "Po mszy")]
PART_LABEL = {"Psalm": "Psalm responsoryjny – melodia", "Alleluja": "Aklamacja przed Ewangelią – melodia"}


def song_blocks(song):
    """Pieśń → [(etykieta, [wersy])]: refren, zwrotki, przypomnienia „(Refren)”."""
    out = []
    cfg = song_cfg(song)
    ref = clean_refren_text(song.get('refren', ''))
    ref_lines = [l.strip() for l in ref.splitlines() if l.strip()]
    if ref_lines:
        out.append(("Refren:", ref_lines))
    verses = process_verses(song.get('zwrotki_raw', ''), auto_punctuate=False, reflow=False)
    for i, v in enumerate(verses):
        vl = v.split('\n')
        m = re.match(r'^(\d+)\.\s*(.*)$', vl[0])
        if m:
            label, vl[0] = f"Zwrotka {m.group(1)}:", m.group(2)
        else:
            label = f"Zwrotka {i + 1}:" if len(verses) > 1 else None
        out.append((label, [l for l in vl if l.strip()]))
        if ref_lines and cfg.get('powtarzaj_refren') and i < len(verses) - 1:
            out.append((None, ["(Refren)"]))
    return out


def _with_audio(song):
    """Bloki pieśni + lista nagrań do nauki (jeśli powstały)."""
    out = [('p', lab, lines) for lab, lines in song_blocks(song)]
    if song.get('_nagrania'):
        out.append(('p', "Nagrania do nauki (folder „nagrania”):", list(song['_nagrania'])))
    return out


def mass_program(entries, liturgy=None, title="Msza święta", subtitle="", lit_mode='full'):
    """entries: [(część, pieśń)]; liturgy: wynik modul_liturgia.fetch*; lit_mode: 'full' | 'short' | 'none'.
    → [('h', poziom, tekst) | ('p', etykieta, [wersy])] w kolejności Mszy."""
    import modul_liturgia as ml
    by_part = {}
    for part, song in entries:
        by_part.setdefault(part, []).append(song)
    secs = (liturgy or {}).get('sekcje', {}) if lit_mode != 'none' else {}
    out = [('h', 0, title)]
    if subtitle:
        out.append(('p', None, [subtitle]))
    if all(p in (FREE_PART, None) for p, _ in entries):      # bez okazji albo jedna pieśń – zwykła lista
        if len(entries) == 1:
            song = entries[0][1]
            meta = [x for x in (song.get('kategoria', ''), song.get('uwagi', '')) if x]
            if meta:
                out.append(('p', None, [" • ".join(meta)]))
            out += _with_audio(song)
            return out
        out.append(('p', None, [f"Liczba utworów: {len(entries)}. Każdy utwór zaczyna się nagłówkiem drugiego poziomu "
                                "– klawisz H przechodzi do następnego."]))
        for k, (_, song) in enumerate(entries, 1):
            out.append(('h', 2, f"{k}. {song.get('title', '')}"))
            out += _with_audio(song)
        return out
    out.append(('p', None, ["Części Mszy są nagłówkami drugiego poziomu, pieśni i teksty liturgii – trzeciego. "
                            "Klawisz H przechodzi do następnego nagłówka."]))
    for kind, key in MASS_ORDER:
        if kind == 'part':
            songs = by_part.get(key, [])
            if not songs:
                continue
            out.append(('h', 2, PART_LABEL.get(key, key)))
            for song in songs:
                out.append(('h', 3, ("Pieśń: " if key not in ORDINARY else "") + song.get('title', '')))
                out += _with_audio(song)
        else:
            s = secs.get(key)
            if not s:
                continue
            name = ml.SECTION_NAMES.get(key, key)
            out.append(('h', 2 if key in ('czyt1', 'czyt2', 'ewangelia', 'kolekta', 'dary', 'prefacja', 'po_kom', 'sekwencja')
                        else 3, name + (f" ({s['sigla']})" if s.get('sigla') else "")))
            lines = [l for l in s['tekst'].split("\n") if l.strip()]
            if lit_mode == 'short' and key in ('czyt1', 'czyt2', 'ewangelia', 'prefacja'):
                lines = lines[:2] + (["(…)"] if len(lines) > 2 else [])
            if key == 'psalm' and s.get('refren'):
                out.append(('p', "Refren:", [s['refren']]))
                lines = [l for l in lines if l.strip() != s['refren'].strip() and not l.lower().startswith('refren')]
            out.append(('p', None, lines))
    if liturgy and lit_mode != 'none' and secs:
        out.append(('p', None, [f"Teksty liturgiczne: {liturgy.get('url', '')} (Lekcjonarz i Mszał – Pallottinum)."]))
    return out


def export_program(program, path, fmt, font_pt=14):
    """Zapis mszalika: 'docx' (nagłówki, język polski), 'txt' (UTF-8, dla notatników brajlowskich), 'html'."""
    title = program[0][2] if program and program[0][0] == 'h' else "Msza"
    if fmt == 'txt':
        out = []
        for item in program:
            if item[0] == 'h':
                lvl, t = item[1], item[2]
                out += (["", t.upper(), ""] if lvl == 0 else ["", f"== {t} ==", ""] if lvl == 2 else ["", f"-- {t}", ""])
            else:
                lab, lines = item[1], item[2]
                if lab:
                    out.append(lab)
                out += lines
                out.append("")
        txt = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"
        with open(path, 'w', encoding='utf-8', newline='\r\n') as f:
            f.write(txt)
        return
    if fmt == 'html':
        import html as H
        body, toc, n = [], [], 0
        for item in program:
            if item[0] == 'h':
                lvl, t = item[1], item[2]
                tag = 'h1' if lvl == 0 else f'h{lvl}'
                if lvl == 2:
                    n += 1
                    toc.append(f'<li><a href="#c{n}">{H.escape(t)}</a></li>')
                    body.append(f'<{tag} id="c{n}">{H.escape(t)}</{tag}>')
                else:
                    body.append(f'<{tag}>{H.escape(t)}</{tag}>')
            else:
                lab, lines = item[1], item[2]
                inner = "<br>\n".join(H.escape(l) for l in lines)
                body.append(f"<p>{'<strong>' + H.escape(lab) + '</strong><br>' if lab else ''}{inner}</p>")
        if toc:
            body.insert(1, '<nav aria-label="Części Mszy"><h2>Spis części</h2><ul>' + "".join(toc) + '</ul></nav>')
        page = (f'<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" '
                f'content="width=device-width, initial-scale=1"><title>{H.escape(title)}</title>'
                f'<style>body{{font-family:Arial,sans-serif;font-size:{font_pt + 4}px;line-height:1.5;max-width:46em;'
                f'margin:auto;padding:1em}}h2{{margin-top:2em}}</style></head><body><main>'
                + "\n".join(body) + "</main></body></html>")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(page)
        return
    # DOCX
    from docx import Document
    from docx.shared import Pt
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    doc = Document()
    cp = doc.core_properties
    cp.title, cp.language, cp.author, cp.subject = title, 'pl-PL', APP_NAME, "Msza święta – teksty"
    for name in ('Normal', 'Title', 'Heading 1', 'Heading 2', 'Heading 3'):
        st = doc.styles[name]
        rpr = st.element.get_or_add_rPr()
        lang = rpr.find(qn('w:lang'))
        if lang is None:
            lang = OxmlElement('w:lang')
            rpr.append(lang)
        for a in ('w:val', 'w:eastAsia', 'w:bidi'):
            lang.set(qn(a), 'pl-PL')
        st.font.name = 'Arial'
        st.font.color.rgb = None
    doc.styles['Normal'].font.size = Pt(font_pt)
    doc.styles['Normal'].paragraph_format.space_after = Pt(font_pt * 0.8)
    doc.styles['Heading 2'].font.size = Pt(font_pt + 6)
    doc.styles['Heading 3'].font.size = Pt(font_pt + 3)
    doc.styles['Title'].font.size = Pt(font_pt + 10)
    for item in program:
        if item[0] == 'h':
            doc.add_heading(item[2], level=item[1])
        else:
            lab, lines = item[1], item[2]
            par = doc.add_paragraph()
            if lab:
                r = par.add_run(lab)
                r.bold = True
                par.add_run().add_break()
            for i, line in enumerate(lines):
                if i:
                    par.add_run().add_break()
                par.add_run(line)
    doc.save(path)


# =====================================================================
# 4. IMPORT: pliki i strony WWW
# =====================================================================

def _local(tag):
    return tag.rsplit('}', 1)[-1]


def read_docx(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read('word/document.xml'))
    paras = []
    for p in root.iter():
        if _local(p.tag) != 'p':
            continue
        parts = []
        for el in p.iter():
            t = _local(el.tag)
            if t == 't':
                parts.append(el.text or '')
            elif t in ('br', 'cr'):
                parts.append('\n')
            elif t == 'tab':
                parts.append(' ')
        paras.append(''.join(parts))
    return '\n'.join(paras)


def read_odt(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read('content.xml'))

    def walk(el):
        out = [el.text or '']
        for ch in el:
            t = _local(ch.tag)
            if t == 'line-break':
                out.append('\n')
            elif t == 'tab':
                out.append(' ')
            elif t == 's':
                out.append(' ' * int(ch.get('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}c', '1')))
            else:
                out.append(walk(ch))
            out.append(ch.tail or '')
        return ''.join(out)

    return '\n'.join(walk(el) for el in root.iter() if _local(el.tag) in ('p', 'h'))


def read_pdf(path):
    try:
        from pypdf import PdfReader
        return '\n\n'.join((pg.extract_text() or '') for pg in PdfReader(path).pages)
    except ImportError:
        pass
    try:
        from PySide6.QtPdf import QPdfDocument
        d = QPdfDocument()
        d.load(path)
        return '\n\n'.join(d.getAllText(i).text() for i in range(d.pageCount()))
    except ImportError:
        raise RuntimeError("Import PDF wymaga pakietu pypdf:\n  pip install pypdf")


class _HTMLText(HTMLParser):
    BLOCK = {'p', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre', 'section', 'main',
             'article', 'blockquote', 'ul', 'ol', 'table', 'header', 'footer', 'nav', 'td', 'body', 'span'}
    SKIP = {'script', 'style', 'noscript', 'svg', 'head', 'template', 'iframe', 'nav', 'footer', 'button', 'form'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = [{'tag': '#root', 'parts': [], 'br': 0}]
        self.skip, self.title, self.h1, self._in = 0, "", "", None
        self.candidates = []            # (liczba <br>, tekst) – elementy z łamanymi wierszami

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag in ('title', 'h1'):
            self._in = tag
        if self.skip:
            return
        if tag == 'br':
            self.stack[-1]['parts'].append('\n')
            self.stack[-1]['br'] += 1
        elif tag in self.BLOCK:
            self.stack.append({'tag': tag, 'parts': [], 'br': 0})

    def handle_endtag(self, tag):
        if tag == self._in:
            self._in = None
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip or tag not in self.BLOCK or not any(e['tag'] == tag for e in self.stack[1:]):
            return
        while True:
            e = self.stack.pop()
            text = ''.join(e['parts'])
            if e['br'] >= 3 and e['tag'] != 'span':
                self.candidates.append((e['br'], _norm_html_text(text)))
            sep = '' if e['tag'] == 'span' else '\n'
            self.stack[-1]['parts'].append(sep + text + sep)
            if e['tag'] == tag:
                break

    def handle_data(self, data):
        if self._in == 'title':
            self.title += data
        elif self._in == 'h1' and not self.h1:
            self.h1 = data.strip()
        if not self.skip:
            self.stack[-1]['parts'].append(re.sub(r'[ \t\r\n]+', ' ', data))


def _norm_html_text(text):
    lines = [l.strip() for l in text.split('\n')]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


_last_html_candidate = [None]


def html_to_text(html):
    p = _HTMLText()
    p.feed(html)
    while len(p.stack) > 1:
        p.handle_endtag(p.stack[-1]['tag'])
    text = _norm_html_text(''.join(p.stack[0]['parts']))
    title = (p.h1 or p.title).strip()
    title = re.split(r'\s+[|–—-]\s+', title)[0] if title else ""
    best = max(p.candidates, default=None, key=lambda c: c[0])
    _last_html_candidate[0] = best[1] if best else None
    return text, title


def best_lyrics_range(text):
    """Zgaduje fragment z tekstem pieśni: najdłuższy ciąg krótkich wersów. Zwraca (start, koniec) znaków."""
    cand = _last_html_candidate[0]
    if cand and cand in text:
        a = text.index(cand)
        return a, a + len(cand)
    lines = text.split('\n')
    pos, offs = 0, []
    for l in lines:
        offs.append(pos)
        pos += len(l) + 1
    best, best_score, start, score, blanks, last = (0, len(text)), 0, None, 0, 0, None
    for i, l in enumerate(lines + ['x' * 999]):
        words = len(l.split())
        if not l.strip():
            blanks += 1
            if blanks >= 3 and start is not None:
                if score > best_score:
                    best, best_score = (offs[start], offs[last] + len(lines[last])), score
                start, score = None, 0
            continue
        blanks = 0
        if len(l) <= 160 and words >= 1:
            if start is None:
                start = i
            last = i
            score += 1 if 2 <= words <= 25 else 0
        else:
            if start is not None and score > best_score:
                best, best_score = (offs[start], offs[last] + len(lines[last])), score
            start, score = None, 0
    return best


def fetch_url(url, timeout=20):
    if not re.match(r'^https?://', url):
        url = 'https://' + url
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (LiberCanticorum/0.15.1)'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        cs = r.headers.get_content_charset()
    if not cs:
        m = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', raw[:4000], re.I)
        cs = m.group(1).decode() if m else 'utf-8'
    try:
        return raw.decode(cs, errors='replace')
    except LookupError:
        return raw.decode('utf-8', errors='replace')


def read_any(path):
    """Zwraca (tekst, podpowiedź_tytułu, czy_pierwsza_linia_to_tytuł)."""
    ext = os.path.splitext(path)[1].lower()
    import modul_slowa_z_nut as sn
    if ext in sn.SCORE_LYRICS_EXT:                      # słowa spod nut (MuseScore, MusicXML, MIDI)
        return sn.song_to_text(sn.lyrics_from_file(path)), "", True
    if ext == '.pdf':                                   # PDF z nutami → słowa spod pięciolinii
        try:
            song = sn.read_score_pdf(path)
        except Exception:
            song = None
        if song and (song['zwrotki'] or song['refren']):
            return sn.song_to_text(song), "", True
    if ext == '.docx':
        return read_docx(path), "", True
    if ext == '.odt':
        return read_odt(path), "", True
    if ext == '.pdf':
        return read_pdf(path), "", True
    if ext in ('.html', '.htm'):
        with open(path, 'rb') as f:
            raw = f.read()
        text, title = html_to_text(raw.decode('utf-8', errors='replace'))
        return text, title, False
    for enc in ('utf-8-sig', 'cp1250', 'latin-2'):
        try:
            with open(path, encoding=enc) as f:
                return f.read(), "", True
        except UnicodeDecodeError:
            continue
    raise RuntimeError("Nie rozpoznano kodowania pliku.")


# =====================================================================
# 5. BAZA PIEŚNI (SQLite)
# =====================================================================

def norm_tags(text):
    """'Adwent,  Komunia ;kanon' -> 'adwent, komunia, kanon' (bez duplikatów)."""
    out = []
    for t in re.split(r'[,;#\n]+', text or ''):
        t = re.sub(r'\s+', ' ', t).strip().lower()
        if t and t not in out:
            out.append(t)
    return ", ".join(out)


def title_key(t):
    """Tytuł do porównań: bez nawiasów („(Psalm 62)”), interpunkcji i ogonków."""
    return fold(re.sub(r"\(.*?\)|\[.*?\]", " ", t or ""))


def first_line_key(refren, zwrotki):
    """Pierwszy wiersz tekstu (1. zwrotki, a gdy jej brak – refrenu) do porównań."""
    for txt in (zwrotki, refren):
        for line in (txt or "").splitlines():
            line = re.sub(r"^\s*(\d{1,2}\.|ref(ren)?\.?:?|r\.:?)\s*", "", line, flags=re.I)
            if line.strip():
                return fold(line)[:60]
    return ""


def text_key(refren, zwrotki):
    t = re.sub(r"(?m)^\s*(\d{1,2}\.|ref(ren)?\.?:?)\s*", "", f"{refren or ''}\n{zwrotki or ''}", flags=re.I)
    return fold(t)


def text_similarity(a, b):
    import difflib
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a.split(), b.split(), autojunk=False).ratio()


def merge_song_fields(dst, src):
    """Uzupełnia pieśń dst danymi z src (bez tekstu): kategoria, tagi, uwagi, nagrania, źródło."""
    if not dst.get('kategoria') and src.get('kategoria'):
        dst['kategoria'] = src['kategoria']
    dst['tagi'] = norm_tags(", ".join(x for x in (dst.get('tagi', ''), src.get('tagi', '')) if x))
    notes = [n.strip() for n in (dst.get('uwagi') or '').split(" | ") if n.strip()]
    for n in (src.get('uwagi') or '').split(" | "):
        if n.strip() and n.strip() not in notes:
            notes.append(n.strip())
    dst['uwagi'] = " | ".join(notes)
    yt = [l for l in (dst.get('youtube') or '').splitlines() if l.strip()]
    have = {l.split("\t")[0] for l in yt}
    yt += [l for l in (src.get('youtube') or '').splitlines() if l.strip() and l.split("\t")[0] not in have]
    dst['youtube'] = "\n".join(yt)
    if not (dst.get('akordy') or '').strip() and (src.get('akordy') or '').strip():
        dst['akordy'] = src['akordy']
    if src.get('spiewnik') and src['spiewnik'] not in (dst.get('spiewnik') or ''):
        dst['spiewnik'] = "; ".join(x for x in (dst.get('spiewnik') or '', src['spiewnik']) if x)
    src_z = src.get('zrodlo') or ''
    if src_z and src_z not in (dst.get('zrodlo') or ''):
        dst['zrodlo'] = "; ".join(x for x in (dst.get('zrodlo') or '', src_z) if x)
    return dst


class SongDB:
    COLUMNS = {'kategoria': 'TEXT', 'youtube': 'TEXT', 'akordy': 'TEXT', 'spiewnik': 'TEXT'}

    def __init__(self, path):
        self.path = path
        self.con = sqlite3.connect(path)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.execute("""CREATE TABLE IF NOT EXISTS songs(
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, refren TEXT, zwrotki TEXT, uwagi TEXT,
            tagi TEXT, zrodlo TEXT, config TEXT, created TEXT, modified TEXT, search TEXT, search_title TEXT)""")
        have = {r['name'] for r in self.con.execute("PRAGMA table_info(songs)")}
        for col, typ in self.COLUMNS.items():          # migracja starszych baz
            if col not in have:
                self.con.execute(f"ALTER TABLE songs ADD COLUMN {col} {typ}")
        if 'spiewnik' not in have:                      # źródło (śpiewnik) – odgadnij z adresu / pliku importu
            for r in self.con.execute("SELECT id, zrodlo FROM songs WHERE COALESCE(zrodlo, '') <> ''").fetchall():
                g = guess_spiewnik(r['zrodlo'])
                if g:
                    self.con.execute("UPDATE songs SET spiewnik=? WHERE id=?", (g, r['id']))
        self.con.execute("""CREATE TABLE IF NOT EXISTS attachments(
            id INTEGER PRIMARY KEY, song_id INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
            name TEXT, kind TEXT, data BLOB, added TEXT)""")
        self.con.execute("""CREATE TABLE IF NOT EXISTS derived(
            att_id INTEGER PRIMARY KEY REFERENCES attachments(id) ON DELETE CASCADE, pdf BLOB, mid BLOB, made TEXT)""")
        if 'pos' not in {r['name'] for r in self.con.execute("PRAGMA table_info(derived)")}:
            self.con.execute("ALTER TABLE derived ADD COLUMN pos BLOB")     # pozycje nut (.spos) – kursor w nutach
        # zapisane zestawy na Mszę (z danymi: dzień, godzina, miejsce, okres) i pobrana liturgia dnia
        self.con.execute("""CREATE TABLE IF NOT EXISTS zestawy(
            id INTEGER PRIMARY KEY, nazwa TEXT, data TEXT, dane TEXT, zmieniony TEXT)""")
        self.con.execute("""CREATE TABLE IF NOT EXISTS liturgia(
            data TEXT PRIMARY KEY, zrodlo TEXT, dane TEXT, pobrano TEXT)""")
        # inne wersje tekstu tej samej pieśni (z innego śpiewnika, inne tłumaczenie, dawny tekst)
        self.con.execute("""CREATE TABLE IF NOT EXISTS wersje(
            id INTEGER PRIMARY KEY, song_id INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
            nazwa TEXT, refren TEXT, zwrotki TEXT, uwagi TEXT, zrodlo TEXT, dodano TEXT)""")
        # pary pieśni oznaczone „to nie duplikaty”
        self.con.execute("CREATE TABLE IF NOT EXISTS nie_duplikaty(a INTEGER, b INTEGER, PRIMARY KEY(a, b))")
        # opis załącznika: wersja / aranżacja (np. „Melodia z akordami”, „Chór SATB”, „Śpiewnik oazowy 2026, s. 5”)
        if 'opis' not in {r['name'] for r in self.con.execute("PRAGMA table_info(attachments)")}:
            self.con.execute("ALTER TABLE attachments ADD COLUMN opis TEXT")
        self.con.commit()

    # ---- zestawy na Mszę
    def sets(self):
        return [dict(r) for r in self.con.execute("SELECT id, nazwa, data FROM zestawy ORDER BY data DESC, id DESC")]

    def get_set(self, zid):
        r = self.con.execute("SELECT * FROM zestawy WHERE id=?", (zid,)).fetchone()
        return dict(r, dane=json.loads(r['dane'] or '{}')) if r else None

    def save_set(self, zid, nazwa, data, dane):
        now = datetime.datetime.now().isoformat(timespec='seconds')
        js = json.dumps(dane, ensure_ascii=False)
        if zid:
            self.con.execute("UPDATE zestawy SET nazwa=?, data=?, dane=?, zmieniony=? WHERE id=?", (nazwa, data, js, now, zid))
        else:
            zid = self.con.execute("INSERT INTO zestawy(nazwa, data, dane, zmieniony) VALUES (?,?,?,?)",
                                   (nazwa, data, js, now)).lastrowid
        self.con.commit()
        return zid

    def delete_set(self, zid):
        self.con.execute("DELETE FROM zestawy WHERE id=?", (zid,))
        self.con.commit()

    # ---- liturgia dnia (pamięć podręczna – działa potem bez internetu)
    def get_liturgy(self, data):
        r = self.con.execute("SELECT dane FROM liturgia WHERE data=?", (data,)).fetchone()
        return json.loads(r['dane']) if r else None

    def set_liturgy(self, data, lit):
        self.con.execute("INSERT OR REPLACE INTO liturgia(data, zrodlo, dane, pobrano) VALUES (?,?,?,?)",
                         (data, lit.get('zrodlo', ''), json.dumps(lit, ensure_ascii=False),
                          datetime.datetime.now().isoformat(timespec='seconds')))
        self.con.commit()

    @staticmethod
    def _row(r):
        return {'id': r['id'], 'title': r['title'], 'refren': r['refren'] or '', 'zwrotki_raw': r['zwrotki'] or '',
                'uwagi': r['uwagi'] or '', 'tagi': r['tagi'] or '', 'zrodlo': r['zrodlo'] or '',
                'kategoria': r['kategoria'] or '', 'youtube': r['youtube'] or '',
                'akordy': (r['akordy'] if 'akordy' in r.keys() else '') or '',
                'spiewnik': (r['spiewnik'] if 'spiewnik' in r.keys() else '') or '',
                'config': json.loads(r['config'] or '{}')}

    def get(self, sid):
        r = self.con.execute("SELECT * FROM songs WHERE id=?", (sid,)).fetchone()
        return self._row(r) if r else None

    def save(self, song):
        now = datetime.datetime.now().isoformat(timespec='seconds')
        song['tagi'] = norm_tags(song.get('tagi', ''))
        extra = ""
        if song.get('id'):                               # wersje tekstu też są przeszukiwane
            extra = " ".join(f"{v['nazwa']} {v['refren']} {v['zwrotki']}" for v in self.versions(song['id']))
        search = fold(" ".join([song.get('title', ''), song.get('refren', ''), song.get('zwrotki_raw', ''),
                                song.get('tagi', ''), song.get('uwagi', ''), song.get('kategoria', ''),
                                song.get('spiewnik', ''), extra]))
        vals = (song.get('title') or 'Bez tytułu', song.get('refren', ''), song.get('zwrotki_raw', ''),
                song.get('uwagi', ''), song.get('tagi', ''), song.get('zrodlo', ''),
                json.dumps(song.get('config', {}), ensure_ascii=False), now, search, fold(song.get('title', '')),
                song.get('kategoria', ''), song.get('youtube', ''), song.get('akordy', ''),
                (song.get('spiewnik') or guess_spiewnik(song.get('zrodlo', '')) if not song.get('id') else
                 song.get('spiewnik', '')).strip())
        if song.get('id'):
            self.con.execute("""UPDATE songs SET title=?, refren=?, zwrotki=?, uwagi=?, tagi=?, zrodlo=?, config=?,
                                modified=?, search=?, search_title=?, kategoria=?, youtube=?, akordy=?, spiewnik=?
                                WHERE id=?""", vals + (song['id'],))
        else:
            cur = self.con.execute("""INSERT INTO songs(title, refren, zwrotki, uwagi, tagi, zrodlo, config, modified,
                                      search, search_title, kategoria, youtube, akordy, spiewnik, created)
                                      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", vals + (now,))
            song['spiewnik'] = vals[13]
            song['id'] = cur.lastrowid
        self.con.commit()
        return song['id']

    def set_youtube(self, sid, text):
        self.con.execute("UPDATE songs SET youtube=? WHERE id=?", (text, sid))
        self.con.commit()

    def delete(self, sid):
        self.con.execute("DELETE FROM derived WHERE att_id IN (SELECT id FROM attachments WHERE song_id=?)", (sid,))
        self.con.execute("DELETE FROM attachments WHERE song_id=?", (sid,))
        self.con.execute("DELETE FROM songs WHERE id=?", (sid,))
        self.con.commit()

    def search(self, query="", category=None, tag=None, source=None):
        words = fold(query).split()
        sql = "SELECT id, title, tagi, kategoria, refren, zwrotki, spiewnik FROM songs"
        cond, args = [], []
        if source is not None:
            cond.append("COALESCE(spiewnik, '') = ?")
            args.append(source)
        for w in words:
            cond.append("search LIKE ?")
            args.append(f"%{w}%")
        if category is not None:
            cond.append("COALESCE(kategoria, '') = ?")
            args.append(category)
        if cond:
            sql += " WHERE " + " AND ".join(cond)
        rows = self.con.execute(sql, args).fetchall()
        if tag:
            rows = [r for r in rows if tag in [t.strip() for t in (r['tagi'] or '').split(',')]]
        ft = fold(query)

        def rank(r):
            st = fold(r['title'])
            return (0 if ft and st.startswith(ft) else 1 if ft and all(w in st for w in words) else 2, st)

        return sorted(rows, key=rank)

    def sources(self):
        """[(źródło – śpiewnik, liczba)] – używane w bazie."""
        return [(r[0] or '', r[1]) for r in self.con.execute(
            "SELECT COALESCE(spiewnik, ''), COUNT(*) FROM songs GROUP BY COALESCE(spiewnik, '') ORDER BY 1")]

    def categories(self):
        """[(kategoria, liczba)] – używane w bazie."""
        return [(r[0] or '', r[1]) for r in self.con.execute(
            "SELECT COALESCE(kategoria, ''), COUNT(*) FROM songs GROUP BY COALESCE(kategoria, '') ORDER BY 1")]

    def tags(self):
        counts = {}
        for (t,) in self.con.execute("SELECT tagi FROM songs WHERE tagi <> ''"):
            for x in t.split(','):
                x = x.strip()
                if x:
                    counts[x] = counts.get(x, 0) + 1
        return sorted(counts.items())

    def find_by_title(self, title):
        r = self.con.execute("SELECT id FROM songs WHERE search_title=?", (fold(title),)).fetchone()
        return r['id'] if r else None

    def count(self):
        return self.con.execute("SELECT COUNT(*) FROM songs").fetchone()[0]

    # --- załączniki (nuty PDF, MuseScore, MusicXML, MIDI, nagrania) ---
    def add_attachment(self, sid, path):
        ext = os.path.splitext(path)[1].lower()
        with open(path, 'rb') as f:
            data = f.read()
        cur = self.con.execute("INSERT INTO attachments(song_id, name, kind, data, added) VALUES (?,?,?,?,?)",
                               (sid, os.path.basename(path), ATTACH_KINDS.get(ext, 'Plik'), data,
                                datetime.datetime.now().isoformat(timespec='seconds')))
        self.con.commit()
        return cur.lastrowid

    def add_attachment_bytes(self, sid, name, data, opis=""):
        ext = os.path.splitext(name)[1].lower()
        cur = self.con.execute("INSERT INTO attachments(song_id, name, kind, data, added, opis) VALUES (?,?,?,?,?,?)",
                               (sid, name, ATTACH_KINDS.get(ext, 'Plik'), data,
                                datetime.datetime.now().isoformat(timespec='seconds'), opis))
        self.con.commit()
        return cur.lastrowid

    def attachments(self, sid):
        return self.con.execute("SELECT id, name, kind, length(data) AS size, COALESCE(opis, '') AS opis "
                                "FROM attachments WHERE song_id=? ORDER BY kind, opis, name", (sid,)).fetchall()

    def set_attachment_desc(self, aid, opis):
        self.con.execute("UPDATE attachments SET opis=? WHERE id=?", (opis.strip(), aid))
        self.con.commit()

    def attachment(self, aid):
        return self.con.execute("SELECT * FROM attachments WHERE id=?", (aid,)).fetchone()

    def replace_attachment_data(self, aid, data):
        """Nowa treść załącznika (np. poprawiona melodia); pliki pochodne do przeliczenia."""
        self.con.execute("UPDATE attachments SET data=?, added=? WHERE id=?",
                         (data, datetime.datetime.now().isoformat(timespec='seconds'), aid))
        self.con.execute("DELETE FROM derived WHERE att_id=?", (aid,))
        self.con.commit()

    def get_derived(self, aid):
        return self.con.execute("SELECT pdf, mid, pos FROM derived WHERE att_id=?", (aid,)).fetchone()

    def set_derived(self, aid, pdf, mid, pos=None):
        self.con.execute("INSERT OR REPLACE INTO derived(att_id, pdf, mid, pos, made) VALUES (?,?,?,?,?)",
                         (aid, pdf, mid, pos, datetime.datetime.now().isoformat(timespec='seconds')))
        self.con.commit()

    def delete_attachment(self, aid):
        self.con.execute("DELETE FROM derived WHERE att_id=?", (aid,))
        self.con.execute("DELETE FROM attachments WHERE id=?", (aid,))
        self.con.commit()

    def attachment_counts(self):
        return dict(self.con.execute("SELECT song_id, COUNT(*) FROM attachments GROUP BY song_id").fetchall())

    # ---- cofanie zmian: kopia bazy przed każdą większą zmianą (import, łączenie, usuwanie)
    UNDO_KEEP = 8

    def undo_dir(self):
        d = os.path.join(os.path.dirname(os.path.abspath(self.path)), ".cofnij_" +
                         os.path.splitext(os.path.basename(self.path))[0])
        os.makedirs(d, exist_ok=True)
        return d

    def snapshot(self, label):
        """Kopia całej bazy (spójna – przez mechanizm kopii SQLite) z opisem operacji. Zwraca ścieżkę."""
        try:
            self.con.commit()
            stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            path = os.path.join(self.undo_dir(), f"{stamp}.db")
            dst = sqlite3.connect(path)
            with dst:
                self.con.backup(dst)
            dst.close()
            with open(path[:-3] + ".txt", "w", encoding="utf-8") as f:
                f.write(label)
            snaps = self.snapshots()
            for old in snaps[self.UNDO_KEEP:]:
                for ext in (".db", ".txt"):
                    try:
                        os.remove(old['path'][:-3] + ext)
                    except OSError:
                        pass
            return path
        except Exception:
            return None

    def snapshots(self):
        """[{'path', 'opis', 'kiedy'}] od najnowszej."""
        out = []
        try:
            d = self.undo_dir()
            for f in sorted(os.listdir(d), reverse=True):
                if f.endswith(".db"):
                    p = os.path.join(d, f)
                    try:
                        opis = open(p[:-3] + ".txt", encoding="utf-8").read().strip()
                    except OSError:
                        opis = "zmiana"
                    kiedy = datetime.datetime.fromtimestamp(os.path.getmtime(p))
                    out.append({'path': p, 'opis': opis, 'kiedy': kiedy})
        except OSError:
            pass
        return out

    def restore(self, path):
        """Przywraca bazę z kopii (stan sprzed operacji). Bieżący stan zapisuje jako kopię – można wrócić."""
        tmp = path + ".przywracanie"
        shutil.copyfile(path, tmp)                     # kopia nie zniknie przy porządkowaniu starych kopii
        self.snapshot("Stan przed cofnięciem (można do niego wrócić)")
        src = sqlite3.connect(tmp)
        try:
            src.backup(self.con)
        finally:
            src.close()
            try:
                os.remove(tmp)
            except OSError:
                pass
        self.con.commit()
        for ext in (".db", ".txt"):
            try:
                os.remove(path[:-3] + ext)
            except OSError:
                pass

    # ---- wersje tekstu
    def versions(self, sid):
        return [dict(r) for r in self.con.execute("SELECT * FROM wersje WHERE song_id=? ORDER BY id", (sid,))]

    def get_version(self, vid):
        r = self.con.execute("SELECT * FROM wersje WHERE id=?", (vid,)).fetchone()
        return dict(r) if r else None

    def add_version(self, sid, nazwa, refren, zwrotki, uwagi="", zrodlo=""):
        """Dodaje wersję tekstu – chyba że taka (prawie taka sama) już jest przy pieśni. Zwraca id albo None."""
        main = self.get(sid)
        new = text_key(refren, zwrotki)
        if main and text_similarity(text_key(main['refren'], main['zwrotki_raw']), new) >= 0.97:
            return None
        for v in self.versions(sid):
            if text_similarity(text_key(v['refren'], v['zwrotki']), new) >= 0.97:
                return None
        cur = self.con.execute("INSERT INTO wersje(song_id, nazwa, refren, zwrotki, uwagi, zrodlo, dodano) "
                               "VALUES (?,?,?,?,?,?,?)", (sid, nazwa or "Wersja", refren or "", zwrotki or "", uwagi or "",
                                                          zrodlo or "", datetime.datetime.now().isoformat(timespec='seconds')))
        self.con.commit()
        self._reindex(sid)
        return cur.lastrowid

    def _reindex(self, sid):
        s = self.get(sid)
        if s:
            r = self.con.execute("SELECT modified FROM songs WHERE id=?", (sid,)).fetchone()
            self.save(s)
            self.con.execute("UPDATE songs SET modified=? WHERE id=?", (r['modified'], sid))
            self.con.commit()

    def rename_version(self, vid, nazwa):
        self.con.execute("UPDATE wersje SET nazwa=? WHERE id=?", (nazwa, vid))
        self.con.commit()

    def delete_version(self, vid):
        v = self.get_version(vid)
        self.con.execute("DELETE FROM wersje WHERE id=?", (vid,))
        self.con.commit()
        if v:
            self._reindex(v['song_id'])

    def use_version(self, vid, main_name="Poprzedni tekst główny"):
        """Wersja staje się tekstem głównym, a dotychczasowy tekst główny – wersją (nic nie ginie)."""
        v = self.get_version(vid)
        song = self.get(v['song_id']) if v else None
        if not song:
            return None
        self.con.execute("UPDATE wersje SET nazwa=?, refren=?, zwrotki=?, zrodlo=? WHERE id=?",
                         (main_name, song['refren'], song['zwrotki_raw'], song['zrodlo'], vid))
        song['refren'], song['zwrotki_raw'] = v['refren'] or '', v['zwrotki'] or ''
        if v.get('zrodlo'):
            song['zrodlo'] = v['zrodlo']
        self.save(song)
        return song

    # ---- podobne pieśni i łączenie
    def find_similar(self, title, refren="", zwrotki="", limit=5, exclude=None):
        """[(id, tytuł, podobieństwo 0–1, powód)] – ta sama pieśń pod podobnym tytułem albo z tym samym początkiem tekstu."""
        import difflib
        ft = title_key(title)
        first = first_line_key(refren, zwrotki)
        out = []
        for r in self.con.execute("SELECT id, title, refren, zwrotki FROM songs"):
            if r['id'] == exclude:
                continue
            ot = title_key(r['title'])
            ts = 1.0 if ft and ft == ot else difflib.SequenceMatcher(None, ft, ot).ratio() if ft and ot else 0
            if ts < 0.75 and ft and ot and (ot.startswith(ft) or ft.startswith(ot)) and min(len(ft), len(ot)) >= 12:
                ts = 0.85                                   # „Pokój wam” ~ „Pokój wam (piosenka roku)”
            of = first_line_key(r['refren'], r['zwrotki'])
            fs = difflib.SequenceMatcher(None, first, of).ratio() if first and of and len(first) > 10 else 0
            # tytuł jednej = pierwszy wiersz drugiej (tytuły często są incipitami)
            xs = max(difflib.SequenceMatcher(None, ft, of[:len(ft) + 5]).ratio() if len(ft) >= 10 and of else 0,
                     difflib.SequenceMatcher(None, ot, first[:len(ot) + 5]).ratio() if len(ot) >= 10 and first else 0)
            score = max(ts, 0.95 * fs, 0.9 * xs)
            if score >= 0.78:
                why = "ten sam tytuł" if ts == 1 else "podobny tytuł" if score == ts else "ten sam początek tekstu"
                out.append((r['id'], r['title'], round(score, 2), why))
        out.sort(key=lambda x: -x[2])
        return out[:limit]

    def not_duplicates(self, ids):
        ids = sorted(set(ids))
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                self.con.execute("INSERT OR IGNORE INTO nie_duplikaty(a, b) VALUES (?, ?)", (a, b))
        self.con.commit()

    def duplicate_groups(self, progress=None):
        """Grupy prawdopodobnych duplikatów: [{'ids': [...], 'same': bool, 'why': str}].
        Kandydaci: ten sam tytuł (bez nawiasów, interpunkcji, ogonków), ten sam początek tekstu,
        tytuł jednej = pierwszy wiersz drugiej, bardzo podobny tytuł (literówki)."""
        import difflib
        rows = self.con.execute("SELECT id, title, refren, zwrotki FROM songs").fetchall()
        info = {}
        buckets = {}
        for r in rows:
            tk, fk = title_key(r['title']), first_line_key(r['refren'], r['zwrotki'])
            info[r['id']] = (tk, fk, text_key(r['refren'], r['zwrotki']))
            for key in (("t", tk), ("f", fk[:40]) if len(fk) >= 12 else None, ("x", tk) if len(tk) >= 10 else None,
                        ("p", tk[:10]) if len(tk) >= 6 else None):
                if key and key[1]:
                    buckets.setdefault(key, []).append(r['id'])
            if len(fk) >= 10:
                buckets.setdefault(("x", fk[:len(tk)] if len(tk) >= 10 else fk[:20]), []).append(r['id'])
        ignored = {(a, b) for a, b in self.con.execute("SELECT a, b FROM nie_duplikaty")}
        parent = {}

        def find(x):
            while parent.get(x, x) != x:
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
        why = {}
        seen = set()
        blist = [v for v in buckets.values() if 1 < len(v) <= 60]
        for k, ids in enumerate(blist):
            if progress and k % 50 == 0:
                progress(k, len(blist))
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    pair = (min(a, b), max(a, b))
                    if pair in seen or pair in ignored or a == b:
                        continue
                    seen.add(pair)
                    (ta, fa, xa), (tb, fb, xb) = info[a], info[b]
                    reason = ""
                    if ta and ta == tb:
                        reason = "ten sam tytuł"
                    elif fa and len(fa) >= 12 and difflib.SequenceMatcher(None, fa, fb).ratio() >= 0.9:
                        reason = "ten sam początek tekstu"
                    elif len(ta) >= 10 and fb and difflib.SequenceMatcher(None, ta, fb[:len(ta) + 3]).ratio() >= 0.9 \
                            or len(tb) >= 10 and fa and difflib.SequenceMatcher(None, tb, fa[:len(tb) + 3]).ratio() >= 0.9:
                        reason = "tytuł = początek tekstu drugiej"
                    elif len(ta) >= 6 and difflib.SequenceMatcher(None, ta, tb).ratio() >= 0.9:
                        reason = "bardzo podobny tytuł"
                    if reason:
                        union(a, b)
                        why.setdefault(pair, reason)
        groups = {}
        for a, b in why:
            groups.setdefault(find(a), set()).update((a, b))
        out = []
        for ids in groups.values():
            ids = sorted(ids)
            clusters = []                              # pieśni z tym samym tekstem w grupie
            for i in ids:
                t = info[i][2]
                for c in clusters:
                    if t and text_similarity(info[c[0]][2], t) >= 0.97:
                        c.append(i)
                        break
                else:
                    clusters.append([i])
            same_sets = [c for c in clusters if len(c) > 1]
            reasons = sorted({w for (a, b), w in why.items() if a in ids})
            out.append({'ids': ids, 'same': len(same_sets) == 1 and len(same_sets[0]) == len(ids),
                        'same_sets': same_sets, 'why': ", ".join(reasons)})
        out.sort(key=lambda g: (not g['same'], self.get(g['ids'][0])['title'].lower()))
        return out

    def merge_songs(self, src_id, dst_id, version_name=""):
        """Pieśń src_id dołączana do dst_id: jej tekst (gdy inny) zostaje wersją, załączniki, nagrania, tagi
        i uwagi przechodzą do dst_id, zestawy wskazują na dst_id; src_id znika."""
        a, b = self.get(src_id), self.get(dst_id)
        if not a or not b or src_id == dst_id:
            return None
        merge_song_fields(b, a)
        if a['refren'] or a['zwrotki_raw']:
            if not (b['refren'] or b['zwrotki_raw']):
                b['refren'], b['zwrotki_raw'] = a['refren'], a['zwrotki_raw']
            else:
                self.add_version(dst_id, version_name or a['title'] + (f" ({a['zrodlo']})" if a['zrodlo'] else ""),
                                 a['refren'], a['zwrotki_raw'], a['uwagi'], a['zrodlo'])
        self.save(b)
        self.con.execute("UPDATE attachments SET song_id=?, opis=COALESCE(NULLIF(opis, ''), ?) WHERE song_id=?",
                         (dst_id, a['title'] if fold(a['title']) != fold(b['title']) else "", src_id))
        self.con.execute("UPDATE wersje SET song_id=? WHERE song_id=?", (dst_id, src_id))
        self.dedupe_attachments(dst_id)
        for r in self.con.execute("SELECT id, dane FROM zestawy").fetchall():
            d = json.loads(r['dane'] or '{}')
            ch = False
            for part, ids in (d.get('czesci') or {}).items():
                for k, x in enumerate(ids):
                    if x == src_id:
                        ids[k] = dst_id
                        ch = True
            if ch:
                self.con.execute("UPDATE zestawy SET dane=? WHERE id=?", (json.dumps(d, ensure_ascii=False), r['id']))
        self.con.execute("DELETE FROM songs WHERE id=?", (src_id,))
        self.con.commit()
        return b

    def dedupe_attachments(self, sid):
        """Usuwa powtórzone pliki (identyczna zawartość) przy pieśni – zostaje pierwszy, z opisem z dowolnej kopii."""
        seen = {}
        for r in self.con.execute("SELECT id, data, COALESCE(opis, '') AS opis FROM attachments WHERE song_id=? ORDER BY id",
                                  (sid,)).fetchall():
            key = bytes(r['data'] or b"")
            if key in seen:
                keep = seen[key]
                if r['opis']:
                    self.con.execute("UPDATE attachments SET opis=COALESCE(NULLIF(opis, ''), ?) WHERE id=?", (r['opis'], keep))
                self.con.execute("DELETE FROM derived WHERE att_id=?", (r['id'],))
                self.con.execute("DELETE FROM attachments WHERE id=?", (r['id'],))
            else:
                seen[key] = r['id']

    def merge_import(self, dst_id, new, version_name=""):
        """Pieśń z importu dołączana do istniejącej: uzupełnia puste pola, łączy tagi, uwagi i nagrania,
        a inny tekst zapisuje jako wersję. Zwraca opis tego, co się stało."""
        b = self.get(dst_id)
        merge_song_fields(b, new)
        what = []
        if new.get('refren') or new.get('zwrotki_raw'):
            if not (b['refren'] or b['zwrotki_raw']):
                b['refren'], b['zwrotki_raw'] = new.get('refren', ''), new.get('zwrotki_raw', '')
                what.append("tekst")
            else:
                vid = self.add_version(dst_id, version_name or new.get('zrodlo') or new.get('title'),
                                       new.get('refren', ''), new.get('zwrotki_raw', ''), new.get('uwagi', ''),
                                       new.get('zrodlo', ''))
                what.append("nowa wersja tekstu" if vid else "tekst bez zmian")
        self.save(b)
        return b, what

    def merge_from(self, path, progress=None):
        """Dołącza pieśni z innej bazy (np. poprzedniej instalacji) razem z nutami i podglądami.
        Pieśni o tym samym tytule są pomijane. Obsługuje bazy z wersji 7.0 (bez nowszych kolumn i tabel)."""
        src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        src.row_factory = sqlite3.Row
        tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        cols = {r['name'] for r in src.execute("PRAGMA table_info(songs)")}
        have = {r[0] for r in self.con.execute("SELECT search_title FROM songs")}
        rows = src.execute("SELECT * FROM songs ORDER BY id").fetchall()
        added, skipped, n_att = [], [], 0

        def copy_attachments(old_id, new_id):
            n = 0
            if 'attachments' not in tables:
                return 0
            present = {(a['name'], a['size']) for a in self.attachments(new_id)}
            dcols = {c['name'] for c in src.execute("PRAGMA table_info(derived)")} if 'derived' in tables else set()
            for a in src.execute("SELECT * FROM attachments WHERE song_id=?", (old_id,)).fetchall():
                if (a['name'], len(a['data'] or b'')) in present:
                    continue
                cur = self.con.execute("INSERT INTO attachments(song_id, name, kind, data, added) VALUES (?,?,?,?,?)",
                                       (new_id, a['name'], a['kind'], a['data'], a['added']))
                n += 1
                if dcols:
                    d = src.execute("SELECT * FROM derived WHERE att_id=?", (a['id'],)).fetchone()
                    if d:
                        self.con.execute("INSERT OR REPLACE INTO derived(att_id, pdf, mid, pos, made) VALUES (?,?,?,?,?)",
                                         (cur.lastrowid, d['pdf'], d['mid'], d['pos'] if 'pos' in dcols else None, d['made']))
            return n

        for k, r in enumerate(rows):
            if progress:
                progress(k, len(rows))
            if fold(r['title']) in have:
                # ta pieśń już jest – dołącz tylko brakujące nuty/nagrania i uzupełnij puste pola
                sid = self.find_by_title(r['title'])
                skipped.append(r['title'])
                if sid:
                    cur = self.get(sid)
                    changed = False
                    for key, col in (('kategoria', 'kategoria'), ('tagi', 'tagi'), ('youtube', 'youtube'),
                                     ('akordy', 'akordy')):
                        if col in cols and not cur.get(key) and r[col]:
                            cur[key] = r[col]
                            changed = True
                    if changed:
                        self.save(cur)
                    n_att += copy_attachments(r['id'], sid)
                continue
            song = {'title': r['title'], 'refren': r['refren'] or '', 'zwrotki_raw': r['zwrotki'] or '',
                    'uwagi': r['uwagi'] or '', 'tagi': r['tagi'] or '', 'zrodlo': r['zrodlo'] or '',
                    'kategoria': (r['kategoria'] or '') if 'kategoria' in cols else '',
                    'youtube': (r['youtube'] or '') if 'youtube' in cols else '',
                    'akordy': (r['akordy'] or '') if 'akordy' in cols else '',
                    'config': json.loads(r['config'] or '{}')}
            new_id = self.save(song)
            have.add(fold(song['title']))
            added.append(song['title'])
            n_att += copy_attachments(r['id'], new_id)
        self.con.commit()
        src.close()
        return added, skipped, n_att


def song_from_json_v6(path):
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    if not isinstance(d, dict) or 'title' not in d:
        return None
    return {'title': d.get('title') or 'Bez tytułu', 'refren': d.get('refren', ''), 'zwrotki_raw': d.get('zwrotki_raw', ''),
            'uwagi': d.get('uwagi', ''), 'tagi': d.get('tagi', ''), 'zrodlo': os.path.basename(path),
            'kategoria': d.get('kategoria', ''),
            'config': dict(DEFAULT_CFG, **(d.get('config') or {}))}


def import_file_to_song(path):
    if path.lower().endswith('.json'):
        s = song_from_json_v6(path)
        if not s:
            raise RuntimeError("To nie jest plik pieśni z wersji 6.x")
        return s
    text, title_hint, first_is_title = read_any(path)
    if not first_is_title:
        a, b = best_lyrics_range(text)
        text = text[a:b]
    s = parse_song_text(text, first_is_title, title_hint)
    s['zrodlo'] = os.path.basename(path)
    return s


# =====================================================================
# 6. INTERFEJS
# =====================================================================

class SlideView(QWidget):
    """Podgląd slajdu (i płótno pokazu)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.slide, self.black, self.clean = None, False, False
        self.setMinimumSize(320, 180)

    def set_slide(self, s):
        self.slide = s
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        paint_slide(p, self.slide, QRectF(self.rect()), self.black, self.clean)
        p.end()


class PresentWindow(SlideView):
    changed = Signal(int)
    closed = Signal()

    def __init__(self, deck, start=0, screen=None):
        super().__init__(None)
        self.setWindowTitle("Pokaz – " + APP_NAME)
        self.deck, self.i = deck, max(0, min(start, len(deck) - 1))
        self.setCursor(Qt.BlankCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        if screen is not None:
            self.setScreen(screen)
            self.move(screen.geometry().topLeft())
        self.show_index(self.i)

    def set_deck(self, deck):
        self.deck = deck
        self.show_index(min(self.i, len(deck) - 1))

    def set_clean(self, on):
        self.clean = on
        self.update()

    def show_index(self, i, emit=True):
        if not self.deck:
            self.set_slide(None)
            return
        self.i = max(0, min(i, len(self.deck) - 1))
        self.set_slide(self.deck[self.i])
        if emit:
            self.changed.emit(self.i)

    def keyPressEvent(self, e):
        k = e.key()
        if k in (Qt.Key_Right, Qt.Key_Down, Qt.Key_Space, Qt.Key_PageDown, Qt.Key_Return, Qt.Key_Enter, Qt.Key_N):
            self.show_index(self.i + 1)
        elif k in (Qt.Key_Left, Qt.Key_Up, Qt.Key_PageUp, Qt.Key_Backspace, Qt.Key_P):
            self.show_index(self.i - 1)
        elif k == Qt.Key_Home:
            self.show_index(0)
        elif k == Qt.Key_End:
            self.show_index(len(self.deck) - 1)
        elif k in (Qt.Key_B, Qt.Key_Period, Qt.Key_W):
            self.black = not self.black
            self.update()
        elif k == Qt.Key_C:
            self.set_clean(not self.clean)
        elif k in (Qt.Key_Escape, Qt.Key_Q, Qt.Key_F5):
            self.close()
        else:
            super().keyPressEvent(e)

    def mousePressEvent(self, e):
        self.show_index(self.i + (1 if e.button() == Qt.LeftButton else -1))

    def wheelEvent(self, e):
        self.show_index(self.i + (1 if e.angleDelta().y() < 0 else -1))

    def closeEvent(self, e):
        self.closed.emit()
        super().closeEvent(e)


class TagCompleter(QCompleter):
    """Podpowiedzi tagów dla listy rozdzielanej przecinkami."""

    def splitPath(self, path):
        return [path.split(',')[-1].strip()]

    def pathFromIndex(self, index):
        text = self.widget().text()
        head = text.rsplit(',', 1)[0] + ', ' if ',' in text else ''
        return head + index.data() + ', '


class MergeChoiceDialog(QDialog):
    """Ta sama pieśń jest już w bazie? Wybór: nowa pieśń albo dołączenie do istniejącej (z podglądem obu tekstów)."""

    def __init__(self, song, cands, db, parent=None, existing=False):
        super().__init__(parent)
        self.db, self.song, self.result_id = db, song, None
        self.setWindowTitle("Połącz z inną pieśnią" if existing else "Podobna pieśń jest już w bazie")
        self.resize(1000, 620)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            f"Z którą pieśnią połączyć „<b>{H.escape(song['title'])}</b>”? Tekst drugiej pieśni zostanie "
            "zachowany jako <i>wersja tekstu</i>, a nuty, nagrania, tagi i miejsca w zestawach przejdą do pieśni "
            "wynikowej." if existing else
            f"W bazie są pieśni podobne do „<b>{H.escape(song['title'])}</b>”. Możesz zapisać ją jako nową "
            "albo dołączyć do istniejącej – wtedy jej tekst (jeśli jest inny) będzie <i>wersją tekstu</i>, "
            "a plik nut – kolejną aranżacją tej pieśni."))
        lay.itemAt(0).widget().setWordWrap(True)
        top = QHBoxLayout()
        self.find = QLineEdit()
        self.find.setPlaceholderText("Szukaj innej pieśni w bazie…")
        self.find.textChanged.connect(self._search)
        top.addWidget(self.find)
        lay.addLayout(top)
        sp = QSplitter()
        self.lw = QListWidget()
        self._fill(cands)
        self.lw.currentRowChanged.connect(self._preview)
        sp.addWidget(self.lw)
        self.mine = QPlainTextEdit()
        self.mine.setReadOnly(True)
        self.mine.setPlainText(self._text(song, "Ta pieśń"))
        self.other = QPlainTextEdit()
        self.other.setReadOnly(True)
        sp.addWidget(self.mine)
        sp.addWidget(self.other)
        sp.setSizes([300, 350, 350])
        lay.addWidget(sp, 1)
        self.keep_this = QCheckBox("Tytuł i tekst tej pieśni mają zostać główne (druga stanie się wersją)")
        self.keep_this.setVisible(existing)
        lay.addWidget(self.keep_this)
        bb = QDialogButtonBox()
        self.b_merge = bb.addButton("Połącz z zaznaczoną" if existing else "Dołącz do zaznaczonej",
                                    QDialogButtonBox.AcceptRole)
        if not existing:
            b_new = bb.addButton("Zapisz jako nową pieśń", QDialogButtonBox.ActionRole)
            b_new.clicked.connect(lambda: self._done('new'))
        bb.addButton(QDialogButtonBox.Cancel)
        self.b_merge.clicked.connect(lambda: self._done(self.lw.currentItem().data(Qt.UserRole)
                                                        if self.lw.currentItem() else None))
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.lw.setCurrentRow(0)
        self._preview(0)

    @staticmethod
    def _text(s, head):
        t = f"{head}: {s['title']}\n\n"
        if s.get('refren'):
            t += "Ref.: " + s['refren'] + "\n\n"
        return t + (s.get('zwrotki_raw') or '')

    def _fill(self, cands):
        self.lw.clear()
        for sid, title, sc, why in cands:
            it = QListWidgetItem(f"{title}   ({int(sc * 100)}%, {why})")
            it.setData(Qt.UserRole, sid)
            self.lw.addItem(it)

    def _search(self, q):
        if len(q.strip()) < 2:
            return
        rows = [r for r in self.db.search(q) if r['id'] != self.song.get('id')][:30]
        self._fill([(r['id'], r['title'], 0, "wyszukane") for r in rows])
        self.lw.setCurrentRow(0)

    def _preview(self, row):
        it = self.lw.item(row) if row >= 0 else None
        self.b_merge.setEnabled(it is not None)
        b = self.db.get(it.data(Qt.UserRole)) if it else None
        if not b:
            self.other.setPlainText("")
            return
        t = self._text(b, "W bazie")
        vs = self.db.versions(b['id'])
        n = len(self.db.attachments(b['id']))
        t += f"\n\n[wersje tekstu: {len(vs)}, załączniki: {n}]"
        self.other.setPlainText(t)

    def _done(self, val):
        if val is None:
            return
        self.result_id = val
        self.accept()

    def choose(self):
        """'new', id pieśni w bazie albo None (anulowano)."""
        return self.result_id if self.exec() else None


def similar_categories(names):
    """Grupy podobnych kategorii: ta sama nazwa bez wielkości liter i ogonków, literówki, „Adwent” / „Adwentowe”."""
    import difflib
    def key(n):
        return re.sub(r"[^a-z0-9]", "", fold(n))
    names = [n for n in names if n]
    groups, used = [], set()
    for i, a in enumerate(names):
        if a in used:
            continue
        g = [a]
        for b in names[i + 1:]:
            if b in used:
                continue
            ka, kb = key(a), key(b)
            if not ka or not kb:
                continue
            short, long_ = sorted((ka, kb), key=len)
            cp = len(os.path.commonprefix([ka, kb]))
            if ka == kb or difflib.SequenceMatcher(None, ka, kb).ratio() >= 0.86 or \
                    (len(short) >= 5 and long_.startswith(short) and len(long_) - len(short) <= 4) or \
                    (cp >= 5 and len(ka) - cp <= 3 and len(kb) - cp <= 3):     # Maryjne / Maryjna
                g.append(b)
        if len(g) > 1:
            used.update(g)
            groups.append(g)
    return groups


class CategoryManagerDialog(QDialog):
    """Menedżer kategorii: zmiana nazwy, łączenie (także podobnych), usuwanie; podgląd pieśni w kategorii."""
    FIELD, LISTFN, EXTRA = 'kategoria', 'categories', 'extra_categories'
    T = {'title': "Menedżer kategorii", 'list': "Kategorie (Shift/Ctrl+klik – kilka):",
         'b_ren': ("✎ Zmień nazwę…", "Nowa nazwa kategorii (dla wszystkich jej pieśni)"),
         'b_merge': ("🔗 Połącz zaznaczone…", "Kilka kategorii w jedną (np. „Adwent” i „adwentowe”)"),
         'b_sim': ("🔍 Znajdź podobne", "Zaznacza grupy kategorii, które wyglądają na tę samą"),
         'b_new': ("✚ Nowa kategoria…", "Kategoria na liście wyboru – pieśni dodasz potem"),
         'b_del': ("🗑 Usuń kategorię", "Pieśni z tej kategorii zostaną bez kategorii"),
         'songs': "Pieśni w zaznaczonych kategoriach:", 'none': "(bez kategorii)",
         'count': "Kategorii: {a}.  Zmiany można cofnąć: Plik → Cofnij ostatnie zmiany.",
         'one': "Zaznacz jedną kategorię.", 'ren_q': "Nowa nazwa kategorii „{a}”:",
         'ren_snap': "Zmiana nazwy kategorii „{a}” na „{b}”", 'two': "Zaznacz co najmniej dwie kategorie (Shift/Ctrl+klik).",
         'merge_q': "Połączyć {a} kategorie w jedną.\nWybierz nazwę albo wpisz nową:",
         'merge_snap': "Połączenie kategorii {a} w „{b}”", 'merged': "Połączono – {a} pieśni ma teraz kategorię „{b}”.",
         'nosim': "Nie znalazłem podobnych kategorii.", 'new_q': "Nazwa nowej kategorii:",
         'del_q': "Usunąć kategorie: {a}?\n{b} pieśni zostanie bez kategorii (pieśni nie są usuwane).",
         'del_snap': "Usunięcie kategorii {a}"}

    def _items(self):
        return getattr(self.db, self.LISTFN)()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db, self.changed = db, False
        self.setWindowTitle(self.T['title'])
        self.resize(820, 560)
        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        left.addWidget(QLabel(self.T['list']))
        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.ExtendedSelection)
        self.list.itemSelectionChanged.connect(self.show_songs)
        self.list.itemDoubleClicked.connect(lambda _: self.rename())
        left.addWidget(self.list, 1)
        self.info = QLabel()
        self.info.setWordWrap(True)
        left.addWidget(self.info)
        lay.addLayout(left, 1)
        right = QVBoxLayout()
        for key, fn in (('b_ren', self.rename), ('b_merge', self.merge), ('b_sim', self.find_similar),
                        ('b_new', self.new_cat), ('b_del', self.delete)):
            txt, tip = self.T[key]
            b = QPushButton(txt)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            right.addWidget(b)
        right.addWidget(QLabel(self.T['songs']))
        self.songs = QListWidget()
        right.addWidget(self.songs, 1)
        close = QPushButton("Zamknij")
        close.clicked.connect(self.accept)
        right.addWidget(close)
        lay.addLayout(right, 1)
        self._groups, self._gi = [], 0
        self.fill()

    def extra(self):
        try:
            return json.loads(QSettings("LiberCanticorum", "LiberCanticorum").value(self.EXTRA, "[]") or "[]")
        except ValueError:
            return []

    def fill(self, select=()):
        self.list.clear()
        used = dict(self._items())
        for c in self.extra():
            used.setdefault(c, 0)
        for name in sorted(used, key=lambda n: (n == "", fold(n))):
            it = QListWidgetItem(f"{name or self.T['none']}   ({used[name]})")
            it.setData(Qt.UserRole, name)
            self.list.addItem(it)
            if name in select:
                it.setSelected(True)
        self.info.setText(self.T['count'].format(a=len([n for n in used if n])))

    def selected(self):
        return [it.data(Qt.UserRole) for it in self.list.selectedItems()]

    def show_songs(self):
        self.songs.clear()
        cats = self.selected()
        if not cats:
            return
        for r in self.db.con.execute(f"SELECT title, COALESCE({self.FIELD}, '') AS k FROM songs ORDER BY title").fetchall():
            if r['k'] in cats:
                self.songs.addItem(r['title'] + (f"   [{r['k']}]" if len(cats) > 1 else ""))

    def _set(self, cats, new, label):
        ids = [r['id'] for r in self.db.con.execute(f"SELECT id, COALESCE({self.FIELD}, '') AS k FROM songs").fetchall()
               if r['k'] in cats]
        if ids:
            self.db.snapshot(label)
        for sid in ids:
            s = self.db.get(sid)
            s[self.FIELD] = new
            self.db.save(s)
        ex = [c for c in self.extra() if c not in cats]
        QSettings("LiberCanticorum", "LiberCanticorum").setValue(self.EXTRA, json.dumps(ex, ensure_ascii=False))
        self.changed = True
        self.fill(select=[new])
        return len(ids)

    def rename(self):
        cats = [c for c in self.selected() if c]
        if len(cats) != 1:
            QMessageBox.information(self, APP_NAME, self.T['one'])
            return
        new, ok = QInputDialog.getText(self, APP_NAME, self.T['ren_q'].format(a=cats[0]), text=cats[0])
        if ok and new.strip() and new.strip() != cats[0]:
            n = self._set(cats, new.strip(), self.T['ren_snap'].format(a=cats[0], b=new.strip()))
            self.info.setText(f"Zmieniono nazwę – {n} pieśni.")

    def merge(self):
        cats = self.selected()
        if len(cats) < 2:
            QMessageBox.information(self, APP_NAME, self.T['two'])
            return
        counts = dict(self._items())
        opts = sorted([c for c in cats if c], key=lambda c: -counts.get(c, 0)) or [""]
        new, ok = QInputDialog.getItem(self, APP_NAME, self.T['merge_q'].format(a=len(cats)), opts, 0, True)
        if ok and new.strip():
            n = self._set(cats, new.strip(), self.T['merge_snap'].format(a=', '.join(c or '(bez)' for c in cats), b=new.strip()))
            self.info.setText(self.T['merged'].format(a=n, b=new.strip()))
            self._gi = 0

    def find_similar(self):
        self._groups = similar_categories([n for n, _ in self._items()] + self.extra())
        if self._gi >= len(self._groups):
            self._gi = 0
        if not self._groups:
            self.info.setText(self.T['nosim'])
            return
        g = self._groups[self._gi]
        self._gi += 1
        self.list.clearSelection()
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) in g:
                self.list.item(i).setSelected(True)
                self.list.scrollToItem(self.list.item(i))
        self.info.setText(f"Podobne ({self._gi}/{len(self._groups)}): {', '.join(g)} – kliknij „🔗 Połącz zaznaczone…”, "
                          "albo „🔍 Znajdź podobne”, żeby przejść do następnej grupy.")

    def new_cat(self):
        new, ok = QInputDialog.getText(self, APP_NAME, self.T['new_q'])
        if ok and new.strip():
            ex = self.extra()
            if new.strip() not in ex:
                ex.append(new.strip())
            QSettings("LiberCanticorum", "LiberCanticorum").setValue(self.EXTRA, json.dumps(ex, ensure_ascii=False))
            self.changed = True
            self.fill(select=[new.strip()])

    def delete(self):
        cats = [c for c in self.selected() if c]
        if not cats:
            return
        n = sum(cnt for c, cnt in self._items() if c in cats)
        if QMessageBox.question(self, APP_NAME, self.T['del_q'].format(a=', '.join(cats), b=n)) != QMessageBox.Yes:
            return
        self._set(cats, "", self.T['del_snap'].format(a=', '.join(cats)))


class SourceManagerDialog(CategoryManagerDialog):
    """Menedżer źródeł (śpiewników): zmiana nazwy, łączenie podobnych („Siedlecki” / „Śpiewnik Siedleckiego”), usuwanie."""
    FIELD, LISTFN, EXTRA = 'spiewnik', 'sources', 'extra_sources'
    T = {'title': "Menedżer źródeł", 'list': "Źródła – śpiewniki, zbiory (Shift/Ctrl+klik – kilka):",
         'b_ren': ("✎ Zmień nazwę…", "Nowa nazwa źródła (dla wszystkich jego pieśni)"),
         'b_merge': ("🔗 Połącz zaznaczone…", "Kilka źródeł w jedno (np. „Siedlecki” i „Śpiewnik Siedleckiego”)"),
         'b_sim': ("🔍 Znajdź podobne", "Zaznacza grupy źródeł, które wyglądają na to samo"),
         'b_new': ("✚ Nowe źródło…", "Źródło na liście wyboru – pieśni dodasz potem"),
         'b_del': ("🗑 Usuń źródło", "Pieśni z tego źródła zostaną bez źródła"),
         'songs': "Pieśni z zaznaczonych źródeł:", 'none': "(bez źródła)",
         'count': "Źródeł: {a}.  Zmiany można cofnąć: Plik → Cofnij ostatnie zmiany.",
         'one': "Zaznacz jedno źródło.", 'ren_q': "Nowa nazwa źródła „{a}”:",
         'ren_snap': "Zmiana nazwy źródła „{a}” na „{b}”", 'two': "Zaznacz co najmniej dwa źródła (Shift/Ctrl+klik).",
         'merge_q': "Połączyć {a} źródła w jedno.\nWybierz nazwę albo wpisz nową:",
         'merge_snap': "Połączenie źródeł {a} w „{b}”", 'merged': "Połączono – {a} pieśni ma teraz źródło „{b}”.",
         'nosim': "Nie znalazłem podobnych źródeł.", 'new_q': "Nazwa nowego źródła (śpiewnika, zbioru):",
         'del_q': "Usunąć źródła: {a}?\n{b} pieśni zostanie bez źródła (pieśni nie są usuwane).",
         'del_snap': "Usunięcie źródeł {a}"}


class DuplicatesDialog(QDialog):
    """Szukanie i łączenie duplikatów w bazie."""

    def __init__(self, db, groups, parent=None):
        super().__init__(parent)
        self.db, self.groups, self.merged, self.parent_win = db, groups, 0, parent
        self.setWindowTitle("Duplikaty w bazie")
        self.resize(1150, 680)
        lay = QVBoxLayout(self)
        self.head = QLabel()
        self.head.setWordWrap(True)
        lay.addWidget(self.head)
        sp = QSplitter()
        self.glist = QListWidget()
        self.glist.currentRowChanged.connect(self.show_group)
        sp.addWidget(self.glist)
        mid = QWidget()
        ml = QVBoxLayout(mid)
        ml.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(QLabel("Główna (zostaje):"))
        self.main = QComboBox()
        self.main.currentIndexChanged.connect(self._main_changed)
        row.addWidget(self.main, 1)
        ml.addLayout(row)
        ml.addWidget(QLabel("Połącz z główną (zaznacz):"))
        self.members = QListWidget()
        self.members.currentItemChanged.connect(self._preview)
        ml.addWidget(self.members, 1)
        sp.addWidget(mid)
        self.prev = QPlainTextEdit()
        self.prev.setReadOnly(True)
        sp.addWidget(self.prev)
        sp.setSizes([300, 420, 430])
        lay.addWidget(sp, 1)
        bb = QHBoxLayout()
        b = QPushButton("Połącz zaznaczone w główną")
        b.clicked.connect(self.merge_current)
        bb.addWidget(b)
        b = QPushButton("To nie są duplikaty")
        b.setToolTip("Program zapamięta, że te pieśni są różne, i nie będzie ich więcej proponował.")
        b.clicked.connect(self.ignore_current)
        bb.addWidget(b)
        bb.addStretch(1)
        self.b_auto = QPushButton()
        self.b_auto.clicked.connect(self.merge_identical)
        bb.addWidget(self.b_auto)
        b = QPushButton("Zamknij")
        b.clicked.connect(self.accept)
        bb.addWidget(b)
        lay.addLayout(bb)
        self.fill()

    def _score(self, sid):
        s = self.db.get(sid)
        return (len(self.db.attachments(sid)), len(self.db.versions(sid)), len((s['refren'] or '') + s['zwrotki_raw']),
                -sid)

    def fill(self):
        self.glist.blockSignals(True)
        self.glist.clear()
        for g in self.groups:
            first = self.db.get(g['ids'][0])
            n_s = sum(len(c) for c in g.get('same_sets', []))
            it = QListWidgetItem(f"{first['title'] if first else '?'}  —  {len(g['ids'])} pieśni" +
                                 ("  (ten sam tekst)" if g['same'] else f"  ({n_s} z tym samym tekstem)" if n_s else ""))
            it.setToolTip(g['why'])
            self.glist.addItem(it)
        self.glist.blockSignals(False)
        n_same = sum(1 for g in self.groups if g.get('same_sets'))
        self.head.setText(
            f"Znaleziono <b>{len(self.groups)}</b> grup podobnych pieśni"
            + (f", w tym {n_same} z tym samym tekstem" if n_same else "") + ". "
            "Wybierz pieśń główną i zaznacz te, które mają się z nią połączyć: inny tekst zostanie zachowany jako "
            "<i>wersja</i>, a nuty, nagrania, tagi i miejsca w zestawach przejdą do głównej. "
            "Przed łączeniem robię kopię bazy (Plik → Cofnij ostatnie zmiany)." if self.groups else
            "Nie znalazłem duplikatów. 🙂")
        self.b_auto.setText(f"Połącz automatycznie pieśni z tym samym tekstem ({n_same} grup)")
        self.b_auto.setEnabled(n_same > 0)
        if self.groups:
            self.glist.setCurrentRow(0)
        else:
            self.main.clear()
            self.members.clear()
            self.prev.clear()

    def show_group(self, row):
        if not (0 <= row < len(self.groups)):
            return
        ids = self.groups[row]['ids']
        best = max(ids, key=self._score)
        self.main.blockSignals(True)
        self.main.clear()
        for sid in ids:
            s = self.db.get(sid)
            if s:
                na, nv = len(self.db.attachments(sid)), len(self.db.versions(sid))
                self.main.addItem(f"{s['title']}" + (f"  [{s['kategoria']}]" if s.get('kategoria') else "") +
                                  (f"  · nuty/pliki: {na}" if na else "") + (f"  · wersje: {nv}" if nv else ""), sid)
        self.main.setCurrentIndex(max(0, self.main.findData(best)))
        self.main.blockSignals(False)
        self._main_changed()

    def _main_changed(self, *_):
        row = self.glist.currentRow()
        if not (0 <= row < len(self.groups)):
            return
        main = self.main.currentData()
        self.members.clear()
        for sid in self.groups[row]['ids']:
            if sid == main:
                continue
            s = self.db.get(sid)
            if not s:
                continue
            first = (s['zwrotki_raw'] or s['refren'] or '').strip().splitlines()
            it = QListWidgetItem(f"{s['title']}  —  {first[0][:50] if first else '(bez tekstu)'}")
            it.setData(Qt.UserRole, sid)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked)
            self.members.addItem(it)
        self.members.setCurrentRow(0)
        self._preview()

    def _preview(self, *_):
        main = self.db.get(self.main.currentData()) if self.main.currentData() else None
        it = self.members.currentItem()
        other = self.db.get(it.data(Qt.UserRole)) if it else None
        t = ""
        for head, s in (("GŁÓWNA", main), ("DO POŁĄCZENIA", other)):
            if s:
                t += f"── {head}: {s['title']} ──\n"
                if s.get('refren'):
                    t += "Ref.: " + s['refren'] + "\n\n"
                t += (s.get('zwrotki_raw') or '') + "\n"
                if s.get('uwagi'):
                    t += f"[uwagi] {s['uwagi']}\n"
                t += "\n"
        self.prev.setPlainText(t)

    def _merge(self, main, others):
        for sid in others:
            if self.db.get(sid) and self.db.get(main):
                self.db.merge_songs(sid, main)
                self.merged += 1

    def merge_current(self):
        row = self.glist.currentRow()
        if not (0 <= row < len(self.groups)):
            return
        main = self.main.currentData()
        others = [self.members.item(i).data(Qt.UserRole) for i in range(self.members.count())
                  if self.members.item(i).checkState() == Qt.Checked]
        if not others:
            return
        self.db.snapshot(f"Łączenie duplikatów: „{self.db.get(main)['title']}”")
        self._merge(main, others)
        rest = [sid for sid in self.groups[row]['ids'] if sid != main and sid not in others]
        if rest:
            self.db.not_duplicates([main] + rest)
        self.groups.pop(row)
        self.fill()
        self.glist.setCurrentRow(min(row, len(self.groups) - 1))

    def ignore_current(self):
        row = self.glist.currentRow()
        if 0 <= row < len(self.groups):
            self.db.not_duplicates(self.groups[row]['ids'])
            self.groups.pop(row)
            self.fill()
            self.glist.setCurrentRow(min(row, len(self.groups) - 1))

    def merge_identical(self):
        same = [g for g in self.groups if g.get('same_sets')]
        if not same or QMessageBox.question(
                self, APP_NAME, f"Połączyć pieśni z tym samym tekstem ({len(same)} grup)? W każdej zostaje "
                "pieśń z największą liczbą nut i wersji; pieśni z innym tekstem zostają na liście do decyzji.") \
                != QMessageBox.Yes:
            return
        self.db.snapshot(f"Łączenie duplikatów z tym samym tekstem ({len(same)} grup)")
        rest = []
        for g in self.groups:
            for c in g.get('same_sets', []):
                main = max(c, key=self._score)
                self._merge(main, [x for x in c if x != main])
            left = [i for i in g['ids'] if self.db.get(i)]
            if len(left) > 1:
                rest.append({'ids': left, 'same': False, 'same_sets': [], 'why': g['why']})
        self.groups = rest
        self.fill()


class ImportDialog(QDialog):
    """Pokazuje pobrany tekst; użytkownik zaznacza fragment z pieśnią."""

    def __init__(self, text, title_hint="", first_is_title=True, preselect=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import tekstu")
        self.resize(760, 640)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Zaznacz fragment z tekstem pieśni (bez zaznaczenia – cały tekst). "
                             "Refren rozpoznawany po „Ref.”, zwrotki po numerach „1.”, „2.”…"))
        self.edit = QPlainTextEdit(text)
        self.edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        lay.addWidget(self.edit, 1)
        form = QFormLayout()
        self.title = QLineEdit(title_hint)
        self.first = QCheckBox("Pierwsza linia fragmentu to tytuł (usuń ją z tekstu)")
        self.first.setChecked(first_is_title)
        form.addRow("Tytuł:", self.title)
        form.addRow("", self.first)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Wczytaj do edytora")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        if preselect:
            c = self.edit.textCursor()
            c.setPosition(preselect[0])
            c.setPosition(preselect[1], QTextCursor.KeepAnchor)
            self.edit.setTextCursor(c)
            self.edit.centerCursor()

    def result_song(self):
        sel = self.edit.textCursor().selectedText().replace(' ', '\n')
        text = sel if sel.strip() else self.edit.toPlainText()
        return parse_song_text(text, self.first.isChecked(), self.title.text().strip())


class ColorButton(QPushButton):
    changed = Signal()

    def __init__(self, color="#ffffff"):
        super().__init__()
        self.setFixedWidth(60)
        self.clicked.connect(self.pick)
        self.set_color(color)

    def set_color(self, c):
        self.color = QColor(c).name()
        self.setStyleSheet(f"background:{self.color}; border:1px solid #888; min-height:18px;")

    def pick(self):
        c = QColorDialog.getColor(QColor(self.color), self)
        if c.isValid():
            self.set_color(c.name())
            self.changed.emit()


class MassPage(QWidget):
    """Prosty widok zestawu na Mszę: data, części Mszy z pieśniami, dodawanie / usuwanie, liturgia dnia, pokaz."""

    def __init__(self, mw):
        super().__init__()
        from PySide6.QtWidgets import QDateEdit, QScrollArea
        from PySide6.QtCore import QLocale
        self.QDateEdit, self.QScrollArea = QDateEdit, QScrollArea
        self.mw = mw
        self.setObjectName("massPage")
        # większe pismo – widok czytany z odległości (np. przy pulpicie, na tablecie)
        self.setStyleSheet("#massPage QLabel { font-size: 15pt; } #massPage QLabel#massPart { font-size: 16pt; font-weight: bold; }"
                           " #massPage QPushButton { font-size: 13pt; padding: 6px 12px; }"
                           " #massPage QDateEdit { font-size: 14pt; padding: 4px; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 8)
        top = QHBoxLayout()
        self.head = QLabel()
        f = self.head.font()
        f.setPointSize(f.pointSize() + 6)
        f.setBold(True)
        self.head.setFont(f)
        self.head.setStyleSheet("font-size: 22pt; font-weight: bold;")
        top.addWidget(self.head, 1)
        top.addWidget(QLabel("Dzień:"))
        self.date = self.QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dddd, d MMMM yyyy")
        try:
            import modul_i18n
            self.date.setLocale(QLocale(modul_i18n.LANG) if modul_i18n.LANG != 'pl' else QLocale(QLocale.Polish, QLocale.Poland))
        except Exception:
            self.date.setLocale(QLocale(QLocale.Polish, QLocale.Poland))
        self.date.dateChanged.connect(self._date_changed)
        top.addWidget(self.date)
        lay.addLayout(top)
        self.day = QLabel()
        self.day.setWordWrap(True)
        self.day.setStyleSheet("color: #7a6a55;")
        lay.addWidget(self.day)
        sc = self.QScrollArea()
        sc.setWidgetResizable(True)
        self.inner = QWidget()
        self.grid = QGridLayout(self.inner)
        self.grid.setColumnStretch(2, 1)
        self.grid.setVerticalSpacing(10)
        self.grid.setHorizontalSpacing(18)
        sc.setWidget(self.inner)
        lay.addWidget(sc, 1)
        bar = QHBoxLayout()
        for txt, fn, tip in (("📖 Liturgia dnia i propozycje", self._liturgy,
                              "Czytania i modlitwy z dnia Mszy oraz pasujące pieśni – jednym kliknięciem do zestawu"),
                             ("▶ Pokaż cały zestaw", lambda: self.mw.present_setlist(), "Pokaz slajdów wszystkich pieśni"),
                             ("📦 Materiały…", lambda: self.mw.export_package(), "Teksty, slajdy, nuty i nagrania do jednego folderu"),
                             ("💾 Zapisz zestaw", lambda: self.mw.store_set(), "Zapisuje zestaw w bazie"),
                             ("✚ Nowy zestaw", lambda: (self.mw.new_set(), self.refresh()), "Pusty zestaw"),
                             ("📋 Plan dla muzyków", lambda: self.mw.open_plan(),
                              "Tabela: część, pieśń, tonacja, wykonawca, uwagi, na co zwrócić uwagę – do druku"),
                             ("✎ Części Mszy…", self.edit_parts, "Dodaj, usuń, przemianuj części; własne części; kolejność"),
                             ("⚙ Zaawansowany", lambda: self.mw._go_set_adv(), "Pełny zestaw: rodzaj, godzina, miejsce, "
                              "części stałe z jednej mszy, przeciąganie, zapisane zestawy")):
            b = QPushButton(txt)
            b.setToolTip(tip)
            if txt.startswith("▶"):
                b.setObjectName("big")
            b.clicked.connect(fn)
            bar.addWidget(b)
        lay.addLayout(bar)

    def _date_changed(self, d):
        if self.mw.m_date.date() != d:
            self.mw.m_date.setDate(d)
        self._day_text()

    def _day_text(self):
        try:
            self.day.setText(f"{self.mw.m_okres.currentText()}" + (f"  ·  {self.mw._mass_day}" if getattr(self.mw, '_mass_day', '') else ""))
        except Exception:
            self.day.setText("")

    def refresh(self):
        mw = self.mw
        msza = mw.set_kind() == 'msza'
        self.head.setText("Zestaw na Mszę" if msza else (mw.m_name.text().strip() or "Zestaw utworów"))
        self.date.blockSignals(True)
        self.date.setDate(mw.m_date.date())
        self.date.blockSignals(False)
        self._day_text()
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        tree = mw.setlist
        names = [n for n, _ in tree.part_list()] + [n for n in tree.parts if n not in [x for x, _ in tree.part_list()]]
        for r, part in enumerate(names):
            it = tree.parts[part]
            multi = MASS_MULTI.get(part, True)
            head = QWidget()
            hl = QHBoxLayout(head)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(2)
            lab = QLabel(part)
            lab.setObjectName("massPart")
            if part in ORDINARY:
                lab.setStyleSheet("color: #aa2828;")
            hl.addWidget(lab)
            hl.addStretch(1)
            for txt, tip, fn in (("✎", f"Zmień nazwę części „{part}”", lambda _=False, p=part: self.rename_part(p)),
                                 ("🗑", f"Usuń część „{part}” z zestawu", lambda _=False, p=part: self.delete_part(p)),
                                 ("✚", f"Wstaw nową część po „{part}”", lambda _=False, p=part: self.insert_part(p))):
                b = QToolButton()
                b.setText(txt)
                b.setToolTip(tip)
                b.setAutoRaise(True)
                b.setFixedSize(34, 34)
                b.setStyleSheet("QToolButton { font-size: 15pt; }")
                b.clicked.connect(fn)
                hl.addWidget(b)
            hl.addSpacing(10)
            self.grid.addWidget(head, r, 0, Qt.AlignTop)
            box = QWidget()
            bl = QVBoxLayout(box)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(2)
            for j in range(it.childCount()):
                row = QHBoxLayout()
                notes = tree.notes(part, j)
                t = QLabel(it.child(j).text(0))
                row.addWidget(t)
                sg = mw.db.get(it.child(j).data(0, Qt.UserRole)) or {}
                if sg.get('spiewnik'):
                    sl = QLabel(f"· {sg['spiewnik']}")
                    sl.setStyleSheet("color: #8a7a65; font-size: 11pt;")
                    sl.setToolTip("Źródło (śpiewnik)")
                    row.addWidget(sl)
                nb = QPushButton("📝")
                nb.setFixedWidth(40)
                nb.setStyleSheet("font-size: 14pt;")
                nb.setToolTip("Uwagi: wykonawca, tonacja, uwagi, na co zwrócić uwagę")
                nb.clicked.connect(lambda _=False, p=part, j=j: self.edit_notes(p, j))
                row.addWidget(nb)
                ch = QPushButton("↺")
                ch.setFixedWidth(40)
                ch.setToolTip("Zmień tę pieśń na inną")
                ch.clicked.connect(lambda _=False, p=part, j=j: self.choose(p, replace=j))
                row.addWidget(ch)
                rm = QPushButton("✕")
                rm.setFixedWidth(40)
                rm.setToolTip("Usuń tę pieśń z zestawu")
                rm.clicked.connect(lambda _=False, p=part, j=j: self.remove(p, j))
                row.addWidget(rm)
                if j == it.childCount() - 1 and multi:
                    add = QPushButton("＋ Dodaj")
                    add.setToolTip("Dodaj kolejną pieśń do tej części")
                    add.clicked.connect(lambda _=False, p=part: self.choose(p))
                    row.addSpacing(12)
                    row.addWidget(add)
                row.addStretch(1)
                bl.addLayout(row)
                if notes:
                    nl = QLabel(notes_text(notes, "   •   "))
                    nl.setObjectName("massNotes")
                    nl.setWordWrap(True)
                    nl.setMinimumWidth(640)
                    nl.setStyleSheet("color: #7a5a2a; font-size: 11pt; margin-left: 14px;")
                    nl.setToolTip(notes_text(notes))
                    bl.addWidget(nl)
            if it.childCount() == 0:
                row = QHBoxLayout()
                add = QPushButton("＋ Dodaj")
                add.setToolTip("Wybierz pieśń do tej części (wyszukiwanie po tytule i słowach)")
                add.clicked.connect(lambda _=False, p=part: self.choose(p))
                row.addWidget(add)
                row.addStretch(1)
                bl.addLayout(row)
            self.grid.addWidget(box, r, 1, Qt.AlignTop)
        if tree.kind == 'msza':
            add = QPushButton("✚ Dodaj część Mszy")
            add.setToolTip("Nowa część na końcu zestawu, np. „Do Maryi”, „Na zakończenie”")
            add.clicked.connect(lambda: self.insert_part(None))
            self.grid.addWidget(add, len(names), 0, Qt.AlignTop | Qt.AlignLeft)

    # --- części Mszy wprost z wykazu ---
    def insert_part(self, after):
        name, ok = QInputDialog.getText(self, "Nowa część Mszy", "Nazwa części (np. „Do Maryi”, „Na zakończenie”):")
        name = name.strip() if ok else ""
        if not name:
            return
        parts = list(MASS_PARTS)
        if name in [n for n, _ in parts]:
            QMessageBox.information(self, APP_NAME, f"Część „{name}” już jest w zestawie.")
            return
        k = [n for n, _ in parts].index(after) + 1 if after in [n for n, _ in parts] else len(parts)
        parts.insert(k, (name, True))
        self._store_parts(parts)

    def rename_part(self, part):
        name, ok = QInputDialog.getText(self, "Zmień nazwę części", f"Nowa nazwa części „{part}”:", text=part)
        name = name.strip() if ok else ""
        if not name or name == part:
            return
        if name in [n for n, _ in MASS_PARTS]:
            QMessageBox.information(self, APP_NAME, f"Część „{name}” już jest w zestawie.")
            return
        parts = [(name if n == part else n, m) for n, m in MASS_PARTS]
        if part not in [n for n, _ in MASS_PARTS]:
            parts.append((name, True))
        self._store_parts(parts, {part: name})

    def delete_part(self, part):
        it = self.mw.setlist.parts.get(part)
        n = it.childCount() if it else 0
        parts = [(x, m) for x, m in MASS_PARTS if x != part]
        if not parts:
            return
        msg = f"Usunąć część „{part}” z zestawu na Mszę?"
        if n:
            msg += f"\n\nJej pieśni ({n}) zostaną usunięte z zestawu (same pieśni zostają w bazie)."
        msg += "\n\nDomyślny układ można przywrócić w „✎ Części Mszy…”."
        if QMessageBox.question(self, APP_NAME, msg) != QMessageBox.Yes:
            return
        if it:
            it.takeChildren()
        self._store_parts(parts)

    def _store_parts(self, parts, renamed=None):
        mw = self.mw
        tree = mw.setlist
        if renamed and tree.kind == 'msza':                # pieśni idą za przemianowaną częścią
            for was, n in renamed.items():
                if was in tree.parts:
                    it = tree.parts.pop(was)
                    it.setData(0, Qt.UserRole + 1, n)
                    tree.parts[n] = it
        mw.settings.setValue("mass_parts", json.dumps(parts, ensure_ascii=False))
        apply_mass_parts(parts)
        if mw.set_kind() == 'msza':
            tree.rebuild_parts()
        mw.save_set()
        self.refresh()

    def edit_notes(self, part, j):
        mw = self.mw
        tree = mw.setlist
        it = tree.parts[part].child(j)
        notes = tree.notes(part, j)
        d = QDialog(self)
        d.setWindowTitle(f"Uwagi – {it.text(0)}")
        form = QFormLayout(d)
        form.addRow(QLabel(f"<b>{H.escape(part)}</b>: {H.escape(it.text(0))}"))
        used = []
        try:
            used = json.loads(mw.settings.value("wykonawcy", "[]") or "[]")
        except Exception:
            pass
        perf = QComboBox()
        perf.setEditable(True)
        perf.setProperty("i18n_no", True)
        perf.addItems([""] + [u for u in used if u])
        perf.setCurrentText(notes.get('wykonawca', ''))
        perf.lineEdit().setPlaceholderText("np. schola, organista, kantor, solistka…")
        key = QComboBox()
        key.setEditable(True)
        key.setProperty("i18n_no", True)
        key.addItems([""] + [f"{n}-dur" for n in ("C", "G", "D", "A", "E", "F", "B", "Es", "As")] +
                     [f"{n}-moll" for n in ("a", "e", "h", "d", "g", "c", "f", "fis")])
        key.setCurrentText(notes.get('tonacja', ''))
        key.lineEdit().setPlaceholderText("np. G-dur, o ton niżej, kapodaster 2")
        rem = QPlainTextEdit(notes.get('uwagi', ''))
        rem.setPlaceholderText("np. zwrotki 1, 3, 5; wejście po dzwonkach; organy solo przed")
        rem.setFixedHeight(80)
        att = QPlainTextEdit(notes.get('zwroc', ''))
        att.setPlaceholderText("np. nie przyspieszać w refrenie; wydłużona fermata; uważać na „Amen”")
        att.setFixedHeight(80)
        form.addRow("Wykonawca:", perf)
        form.addRow("Tonacja:", key)
        form.addRow("Uwagi:", rem)
        form.addRow("Na co zwrócić uwagę:", att)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        form.addRow(bb)
        d.resize(620, 420)
        if not d.exec():
            return
        new = {'wykonawca': perf.currentText().strip(), 'tonacja': key.currentText().strip(),
               'uwagi': rem.toPlainText().strip(), 'zwroc': att.toPlainText().strip()}
        tree.set_notes(part, j, new)
        if new['wykonawca'] and new['wykonawca'] not in used:
            mw.settings.setValue("wykonawcy", json.dumps(([new['wykonawca']] + used)[:30], ensure_ascii=False))
        mw.save_set()
        self.refresh()

    def remove(self, part, j):
        it = self.mw.setlist.parts[part]
        if 0 <= j < it.childCount():
            it.removeChild(it.child(j))
        self.mw.setlist._update_labels()
        self.mw.save_set()
        self.refresh()

    def edit_parts(self):
        """Własne części Mszy: dodawanie, usuwanie, zmiana nazwy i kolejności, „kilka pieśni”."""
        mw = self.mw
        d = QDialog(self)
        d.setWindowTitle("Części Mszy")
        lay = QVBoxLayout(d)
        lay.addWidget(QLabel("Części zestawu na Mszę – kolejność, nazwy i własne części (np. „Do Maryi”, „Na zakończenie”).\n"
                             "Zaznaczone pole = w tej części może być kilka pieśni."))
        lst = QListWidget()
        f = lst.font()
        f.setPointSizeF(f.pointSizeF() * 1.4)
        lst.setFont(f)
        for n, m in MASS_PARTS:
            li = QListWidgetItem(n)
            li.setData(Qt.UserRole, n)
            li.setFlags(li.flags() | Qt.ItemIsEditable | Qt.ItemIsUserCheckable)
            li.setCheckState(Qt.Checked if m else Qt.Unchecked)
            lst.addItem(li)
        lay.addWidget(lst, 1)
        row = QHBoxLayout()

        def add():
            name, ok = QInputDialog.getText(d, "Nowa część", "Nazwa części (np. „Do Maryi”, „Na zakończenie”):")
            if ok and name.strip():
                li = QListWidgetItem(name.strip())
                li.setFlags(li.flags() | Qt.ItemIsEditable | Qt.ItemIsUserCheckable)
                li.setCheckState(Qt.Checked)
                k = lst.currentRow() + 1 if lst.currentRow() >= 0 else lst.count()
                lst.insertItem(k, li)
                lst.setCurrentRow(k)

        def move(dd):
            k = lst.currentRow()
            if k < 0 or not 0 <= k + dd < lst.count():
                return
            li = lst.takeItem(k)
            lst.insertItem(k + dd, li)
            lst.setCurrentRow(k + dd)

        def remove():
            k = lst.currentRow()
            if k >= 0:
                lst.takeItem(k)

        def defaults():
            lst.clear()
            for n, m in DEFAULT_MASS_PARTS:
                li = QListWidgetItem(n)
                li.setData(Qt.UserRole, n)
                li.setFlags(li.flags() | Qt.ItemIsEditable | Qt.ItemIsUserCheckable)
                li.setCheckState(Qt.Checked if m else Qt.Unchecked)
                lst.addItem(li)
        for txt, fn, tip in (("✚ Dodaj część…", add, "Nowa część po zaznaczonej"),
                             ("✎ Zmień nazwę", lambda: lst.currentItem() and lst.editItem(lst.currentItem()), "Też: dwuklik"),
                             ("↑", lambda: move(-1), "Wyżej"), ("↓", lambda: move(1), "Niżej"),
                             ("🗑 Usuń", remove, "Pieśni z usuniętej części przejdą do pierwszej części"),
                             ("Przywróć domyślne", defaults, "Standardowe części Mszy")):
            b = QPushButton(txt)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        lay.addWidget(bb)
        d.resize(620, 560)
        if not d.exec():
            return
        parts, renamed = [], {}
        for k in range(lst.count()):
            n = lst.item(k).text().strip()
            if n and n not in [p for p, _ in parts]:
                parts.append((n, lst.item(k).checkState() == Qt.Checked))
                was = lst.item(k).data(Qt.UserRole)
                if was and was != n:
                    renamed[was] = n
        if not parts:
            return
        self._store_parts(parts, renamed)

    def clear_part(self, part):
        it = self.mw.setlist.parts[part]
        it.takeChildren()
        self.mw.setlist._update_labels()
        self.mw.save_set()
        self.refresh()

    def choose(self, part, replace=None):
        mw = self.mw
        d = QDialog(self)
        d.setWindowTitle(f"Pieśń – {part}")
        lay = QVBoxLayout(d)
        q = QLineEdit()
        q.setPlaceholderText("Szukaj: tytuł albo słowa pieśni…")
        qrow = QHBoxLayout()
        qrow.addWidget(q, 1)
        src = source_combo(mw.db, mw.settings.value("mass_src_filter", None))
        qrow.addWidget(src)
        lay.addLayout(qrow)
        lst = QListWidget()
        lay.addWidget(lst, 1)
        hint = QLabel()
        hint.setStyleSheet("color: gray;")
        lay.addWidget(hint)

        def fill():
            lst.clear()
            mw.settings.setValue("mass_src_filter", src.currentData())
            rows = mw.db.search(q.text(), source=src.currentData())
            # najpierw pieśni pasujące do tej części (tagi / tytuł), potem reszta
            guess = getattr(mw.setlist, 'guess', None)
            good = [r for r in rows if guess and guess(r['id']) == part] if not q.text().strip() else []
            for r in good + [r for r in rows if r not in good]:
                li = QListWidgetItem(("★ " if r in good else "") + r['title'] +
                                     (f"   · {r['spiewnik']}" if r['spiewnik'] else ""))
                li.setData(Qt.UserRole, r['id'])
                lst.addItem(li)
            hint.setText("★ – pasuje do tej części (tagi, tytuł). Dwuklik – wybierz." if good else "Dwuklik – wybierz.")
        q.textChanged.connect(fill)
        src.currentIndexChanged.connect(fill)
        fill()
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        lst.itemDoubleClicked.connect(lambda _: d.accept())
        lay.addWidget(bb)
        d.resize(520, 600)
        if d.exec() and lst.currentItem():
            sid = lst.currentItem().data(Qt.UserRole)
            song = mw.db.get(sid)
            if song:
                it = mw.setlist.parts[part]
                if replace is not None and 0 <= replace < it.childCount():
                    ch = it.child(replace)
                    ch.setText(0, song['title'])
                    ch.setData(0, Qt.UserRole, sid)
                    mw.setlist._update_labels()
                else:
                    mw.setlist.add_song(part, sid, song['title'])
                mw.save_set()
                self.refresh()

    def _liturgy(self):
        mw = self.mw
        if mw.set_kind() == 'msza':
            mw.open_liturgy()
        else:
            mw._go_liturgy()
        # po dodaniu pieśni z okna liturgii – odśwież (okno jest niemodalne)
        QTimer.singleShot(1500, self.refresh)


class MassSetTree(QTreeWidget):
    """Zestaw na Mszę: części (stałe nagłówki) i pieśni pod nimi. Pieśni przeciąga się między częściami;
    część stała (np. Kyrie) przyjmuje jedną pozycję – nowa zastępuje poprzednią."""
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.setHeaderHidden(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setIndentation(14)
        self.invisibleRootItem().setFlags(Qt.ItemIsEnabled)          # pieśń nie może wylądować poza częścią
        self.kind = 'msza'
        self._build()

    def part_list(self):
        return MASS_PARTS if self.kind == 'msza' else [(FREE_PART, True)]

    def set_kind(self, kind):
        """'msza' – części Mszy; 'inny' – zwykła lista utworów. Pieśni przechodzą do nowego układu."""
        if kind == self.kind:
            return
        old = self._dump()
        self.kind = kind
        self.clear()
        self._build()
        for part, sid, title, notes in old:
            target = FREE_PART if kind != 'msza' else (getattr(self, 'guess', lambda s: None)(sid) or "Przed mszą")
            self.add_song(target, sid, title, notes)

    def _dump(self):
        return [(p, it.child(k).data(0, Qt.UserRole), it.child(k).text(0), it.child(k).data(0, Qt.UserRole + 2))
                for p, it in self.parts.items() for k in range(it.childCount())]

    def notes(self, part, j):
        """Uwagi do pieśni w zestawie: wykonawca, tonacja, uwagi, na co zwrócić uwagę."""
        it = self.parts[part].child(j)
        return dict(it.data(0, Qt.UserRole + 2) or {})

    def set_notes(self, part, j, notes):
        it = self.parts[part].child(j)
        notes = {k: v for k, v in (notes or {}).items() if v}
        it.setData(0, Qt.UserRole + 2, notes or None)
        it.setToolTip(0, notes_text(notes))

    def all_notes(self):
        """{część: [uwagi…]} – równolegle do listy pieśni części."""
        return {name: [dict(it.child(j).data(0, Qt.UserRole + 2) or {}) for j in range(it.childCount())]
                for name, it in self.parts.items() if it.childCount()}

    def _title(self, part, j):
        return self.parts[part].child(j).text(0)

    def _build(self):
        self.parts = {}
        for name, multi in self.part_list():
            it = QTreeWidgetItem([name])
            it.setData(0, Qt.UserRole + 1, name)
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDropEnabled)
            f = it.font(0)
            f.setBold(True)
            it.setFont(0, f)
            if name in ORDINARY:
                it.setForeground(0, QColor(170, 40, 40))
                it.setToolTip(0, "Część stała – jedna pozycja; wszystkie części stałe najlepiej z jednej mszy.")
            elif not multi:
                it.setToolTip(0, "Melodia psalmu responsoryjnego – jedna pozycja." if name == "Psalm" else
                              "Melodia aklamacji przed Ewangelią – jedna pozycja.")
                it.setText(0, name)
            else:
                it.setToolTip(0, "Można dodać kilka pieśni." if name != FREE_PART else
                              "Utwory w kolejności wykonania – przeciągaj, aby zmienić kolejność.")
            self.addTopLevelItem(it)
            self.parts[name] = it
        self._update_labels()
        self.expandAll()

    def rebuild_parts(self):
        """Po zmianie listy części: ten sam zestaw w nowym układzie (pieśni z usuniętych części – do pierwszej)."""
        old = self._dump()
        self.clear()
        self._build()
        names = [n for n, _ in self.part_list()]
        for part, sid, title, notes in old:
            self.add_song(part if part in names else names[0], sid, title, notes)

    def reset_parts(self):
        for it in self.parts.values():
            it.takeChildren()
        self._update_labels()

    def current_part(self):
        it = self.currentItem()
        if it is None or not it.isSelected():
            return None
        return (it.parent() or it).data(0, Qt.UserRole + 1)

    def add_song(self, part, sid, title, notes=None):
        if part not in self.parts:                         # część spoza bieżącej listy (np. ze starego zestawu)
            MASS_MULTI.setdefault(part, True)
            it = QTreeWidgetItem([part])
            it.setData(0, Qt.UserRole + 1, part)
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDropEnabled)
            f = it.font(0)
            f.setBold(True)
            it.setFont(0, f)
            self.addTopLevelItem(it)
            self.parts[part] = it
        p = self.parts[part]
        if not MASS_MULTI[part]:
            p.takeChildren()
        ch = QTreeWidgetItem([title])
        ch.setData(0, Qt.UserRole, sid)
        ch.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled)
        p.addChild(ch)
        if notes:
            self.set_notes(part, p.childCount() - 1, notes)
        p.setExpanded(True)
        self._update_labels()
        return ch

    def remove_selected(self):
        for it in self.selectedItems():
            if it.parent() is not None:
                it.parent().removeChild(it)
        self._update_labels()

    def entries(self):
        return [(name, it.child(j).data(0, Qt.UserRole))
                for name, it in self.parts.items() for j in range(it.childCount())]

    def _update_labels(self):
        for name, it in self.parts.items():
            n = it.childCount()
            label = {"Psalm": "Psalm – melodia", "Alleluja": "Alleluja – melodia aklamacji"}.get(name, name)
            it.setText(0, label if n == 0 or not MASS_MULTI[name] else f"{label}  ({n})")
            it.setForeground(0, QColor(170, 40, 40) if name in ORDINARY else
                             self.palette().text().color() if n else self.palette().placeholderText().color())

    def dropEvent(self, e):
        target = self.itemAt(e.position().toPoint())
        part = (target.parent() or target) if target is not None else None
        before = set(map(id, (part.child(j) for j in range(part.childCount())))) if part else set()
        super().dropEvent(e)
        if part is not None and not MASS_MULTI[part.data(0, Qt.UserRole + 1)] and part.childCount() > 1:
            kids = [part.child(j) for j in range(part.childCount())]
            new = [k for k in kids if id(k) not in before] or kids[-1:]
            for k in kids:
                if k is not new[0]:
                    part.removeChild(k)
        # gdyby Qt mimo wszystko zagnieździło pieśń w pieśni – przenieś ją do części
        for it in self.parts.values():
            for j in range(it.childCount()):
                ch = it.child(j)
                while ch.childCount():
                    it.insertChild(j + 1, ch.takeChild(0))
        self.expandAll()
        self._update_labels()
        self.changed.emit()


class MainWindow(QMainWindow):
    _conv_done = Signal(int, bytes, bytes, bytes)          # konwersja MuseScore zakończona (z wątku w tle)
    ALL = "— wszystkie —"
    NONE_CAT = "(bez kategorii)"

    def __init__(self, db_path):
        super().__init__()
        self.settings = QSettings("LiberCanticorum", "LiberCanticorum")
        self.db = SongDB(db_path)
        self.song = None
        self.dirty = False
        self.loading = False
        self.deck = []
        self.present = None
        self.present_set = False
        self.yt_player = None
        self.midi_dialogs = []
        self.pilot = None
        self._pilot_ver = None
        self.pilot_timer = QTimer(self, interval=300, timeout=self.pilot_publish)
        self._conv_done.connect(self._on_conv_done)
        self.setAcceptDrops(True)
        self.rebuild_timer = QTimer(self, singleShot=True, interval=250, timeout=self.rebuild_deck)
        self._build_ui()
        self._build_actions()
        self.refresh_filters()
        self.refresh_list()
        self.restore_set()
        self.new_song(ask=False)
        self.resize(1440, 900)
        v = self.settings.value("view2", self.V_START, type=int)
        self.views.setCurrentIndex(v if 0 <= v < self.views.count() else self.V_START)
        self._view_changed(self.views.currentIndex())

    # ================= budowa interfejsu =================
    def _build_ui(self):
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(4, 4, 4, 4)
        self.search = QLineEdit(placeholderText="Szukaj: tytuł, słowa, tagi…  (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh_list)
        ll.addWidget(self.search)
        fl = QGridLayout()
        self.f_cat, self.f_tag, self.f_src = QComboBox(), QComboBox(), QComboBox()
        self.f_src.setProperty("i18n_no", True)
        for w in (self.f_cat, self.f_tag, self.f_src):
            w.currentIndexChanged.connect(self.refresh_list)
            w.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            w.setMinimumContentsLength(10)
        fl.addWidget(QLabel("Kategoria:"), 0, 0)
        fl.addWidget(self.f_cat, 0, 1)
        fl.addWidget(QLabel("Tag:"), 1, 0)
        fl.addWidget(self.f_tag, 1, 1)
        fl.addWidget(QLabel("Źródło:"), 2, 0)
        fl.addWidget(self.f_src, 2, 1)
        ll.addLayout(fl)
        self.results = QTreeWidget()
        self.results.setHeaderHidden(True)
        self.results.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.results.itemActivated.connect(self._on_result)
        self.results.itemClicked.connect(self._on_result)
        self.results.setContextMenuPolicy(Qt.CustomContextMenu)
        self.results.customContextMenuRequested.connect(self._results_menu)
        ll.addWidget(self.results, 2)
        self.count_lbl = QLabel()
        ll.addWidget(self.count_lbl)
        b_add = QPushButton("↓ Do zestawu")
        b_add.setToolTip("Dodaje zaznaczone pieśni do części zaznaczonej w zestawie\n"
                         "(bez zaznaczenia – do części rozpoznanej z tagów, np. „komunia”).")
        b_add.clicked.connect(self.add_to_set)
        ll.addWidget(b_add)
        gb = QGroupBox("Zestaw – przeciągaj pieśni, aby zmienić kolejność lub część Mszy")
        gl = QVBoxLayout(gb)
        zh = QHBoxLayout()
        zh.addWidget(QLabel("Zestaw:"))
        self.set_combo = QComboBox()
        self.set_combo.setToolTip("Zapisane zestawy (najnowsze u góry). Wybierz, aby wczytać.")
        self.set_combo.activated.connect(self.load_saved_set)
        zh.addWidget(self.set_combo, 1)
        for txt, tip, fn in (("💾", "Zapisz zestaw w bazie", self.store_set), ("✚", "Nowy zestaw", self.new_set),
                             ("🗑", "Usuń zapisany zestaw", self.delete_saved_set)):
            b = QPushButton(txt)
            b.setToolTip(tip)
            b.setFixedWidth(34)
            b.clicked.connect(fn)
            zh.addWidget(b)
        gl.addLayout(zh)
        kh = QHBoxLayout()
        self.m_kind = QComboBox()
        self.m_kind.addItem("Msza", 'msza')
        self.m_kind.addItem("Bez okazji", 'inny')
        self.m_kind.setToolTip("Rodzaj zestawu: Msza (z jej częściami) albo bez okazji –\nzwykła lista utworów na koncert, próbę, nabożeństwo.")
        self.m_kind.activated.connect(self._kind_changed)
        kh.addWidget(self.m_kind)
        self.m_name = QLineEdit()
        self.m_name.setPlaceholderText("nazwa, np. Koncert kolęd, Próba chóru")
        self.m_name.textEdited.connect(self.save_set)
        kh.addWidget(self.m_name, 1)
        gl.addLayout(kh)
        dh = QHBoxLayout()
        from PySide6.QtWidgets import QDateEdit, QTimeEdit
        from PySide6.QtCore import QDate, QTime
        from PySide6.QtCore import QLocale
        self.m_date = QDateEdit(QDate.currentDate())
        self.m_date.setLocale(QLocale(QLocale.Polish, QLocale.Poland) if __import__('modul_i18n').LANG == 'pl' else QLocale())
        self.m_date.setCalendarPopup(True)
        self.m_date.setDisplayFormat("ddd d.MM.yyyy")
        self.m_time = QTimeEdit(QTime(10, 0))
        self.m_time.setDisplayFormat("HH:mm")
        self.m_place = QLineEdit()
        self.m_place.setPlaceholderText("miejsce (kościół, kaplica)")
        dh.addWidget(self.m_date)
        dh.addWidget(self.m_time)
        dh.addWidget(self.m_place, 1)
        gl.addLayout(dh)
        oh = QHBoxLayout()
        self.mass_only = []                       # widoczne tylko dla Mszy
        self.m_okres = QComboBox()
        self.m_okres.setEditable(True)
        import modul_liturgia
        self.m_okres.addItems(modul_liturgia.OKRESY)
        self.m_okres.setToolTip("Okres liturgiczny – ustawia się sam z daty; można zmienić.")
        oh.addWidget(self.m_okres, 1)
        b_lit = QPushButton("📖 Liturgia dnia i propozycje…")
        b_lit.setToolTip("Pobiera czytania, antyfony i modlitwy z dnia\ni szuka w bazie pieśni, które do nich nawiązują.")
        b_lit.clicked.connect(self.open_liturgy)
        oh.addWidget(b_lit)
        self.mass_only += [self.m_okres, b_lit]
        gl.addLayout(oh)
        self.m_day = QLabel("")
        self.m_day.setWordWrap(True)
        self.m_day.setStyleSheet("color: gray;")
        gl.addWidget(self.m_day)
        self.mass_only.append(self.m_day)
        self.m_date.dateChanged.connect(self._mass_date_changed)
        for w_ in (self.m_time, ):
            w_.timeChanged.connect(self.save_set)
        self.m_place.textEdited.connect(self.save_set)
        self.m_okres.currentTextChanged.connect(self.save_set)
        mh = QHBoxLayout()
        lab_cs = QLabel("Części stałe:")
        mh.addWidget(lab_cs)
        self.mass_only.append(lab_cs)
        self.mass_combo = QComboBox()
        self.mass_combo.setToolTip("Kyrie, Gloria, Sanctus i Agnus Dei z jednej mszy (jeden motyw).\n"
                                   "Lista z tagów pieśni oznaczonych jako części stałe, np. tag „Msza o Aniołach”.")
        self.mass_combo.activated.connect(self.fill_ordinary)
        mh.addWidget(self.mass_combo, 1)
        self.mass_only.append(self.mass_combo)
        gl.addLayout(mh)
        self.setlist = MassSetTree()
        self.setlist.guess = lambda sid: guess_mass_part(self.db.get(sid) or {})
        self.setlist.setMinimumHeight(220)
        self.setlist.changed.connect(self.save_set)
        self.setlist.itemDoubleClicked.connect(
            lambda it, _c: it.data(0, Qt.UserRole) and self.open_song(it.data(0, Qt.UserRole)))
        gl.addWidget(self.setlist)
        g = QGridLayout()
        buttons = [("Usuń", self.remove_from_set), ("Wyczyść", self.clear_set), ("▶ Pokaz", self.present_setlist),
                   ("PDF", lambda: self.export_set('pdf')), ("PPTX", lambda: self.export_set('pptx')),
                   ("DOCX", lambda: self.export_set('docx')), ("HTML (telefon)", lambda: self.export_html('set')),
                   ("📦 Materiały…", self.export_package), ("♿ Dla niewidomych…", self.export_blind),
                   ("📝 Uwagi…", self._notes_selected), ("📋 Plan dla muzyków", self.open_plan)]
        for i, (txt, fn) in enumerate(buttons):
            b = QPushButton(txt)
            b.clicked.connect(fn)
            g.addWidget(b, i // 3, i % 3)
            if i == 7:
                b.setToolTip("Wszystko do jednego folderu: teksty (DOCX/TXT/HTML), slajdy, nuty PDF\n"
                             "i nagrania do nauki MP3 (całość i wybrane głosy).")
            if i == 8:
                b.setToolTip("Mszalik z pieśniami dla czytnika ekranu i monitora brajlowskiego:\n"
                             "DOCX, TXT lub HTML, z czytaniami i modlitwami z dnia w kolejności Mszy, plus nagrania głosów.")
            if i >= 7:
                f = b.font()
                f.setBold(True)
                b.setFont(f)
        self.sep_chk = QCheckBox("Czarny slajd między pieśniami")
        self.sep_chk.setChecked(self.settings.value("separator", True, type=bool))
        self.sep_chk.toggled.connect(lambda v: self.settings.setValue("separator", v))
        gl.addLayout(g)
        gl.addWidget(self.sep_chk)
        ll.addWidget(gb, 3)

        # ---- środek: zakładki edytora
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_text_tab(), "Tekst")
        self.tabs.addTab(self._build_cfg_tab(), "Wygląd slajdów")
        self.tabs.addTab(self._build_chords_tab(), "Akordy")
        self.tabs.addTab(self._build_media_tab(), "Nuty, wersje i nagrania")

        # ---- prawa: podgląd + miniatury
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(4, 4, 4, 4)
        self.view = SlideView()
        rl.addWidget(self.view, 3)
        self.info = QLabel()
        rl.addWidget(self.info)
        self.thumbs = QListWidget()
        self.thumbs.setViewMode(QListWidget.IconMode)
        self.thumbs.setIconSize(QSize(200, 113))
        self.thumbs.setResizeMode(QListWidget.Adjust)
        self.thumbs.setMovement(QListWidget.Static)
        self.thumbs.setSpacing(4)
        self.thumbs.currentRowChanged.connect(self.on_thumb)
        rl.addWidget(self.thumbs, 2)

        sp = QSplitter()
        sp.addWidget(left)
        sp.addWidget(self.tabs)
        sp.addWidget(right)
        sp.setSizes([320, 520, 600])
        self.advanced = sp
        self._build_views()
        # stopka na każdej zakładce: licencja (kliknięcie – „O programie i licencja”)
        try:
            from modul_i18n import tr as _t
        except Exception:
            _t = lambda x: x
        lic = QLabel(f"<a href='about' style='color:#7a6a55; text-decoration:none'>{APP_NAME} {VERSION} · "
                     + _t("wolne oprogramowanie – licencja GNU GPL 3.0") + " · " + _t("ikona CC BY-SA 4.0") + " · "
                     + _t("ikony Font Awesome CC BY 4.0") + " · " + _t("teksty i nuty – prawa ich autorów")
                     + "</a> · <a href='copy' style='color:#7A2E3A'>" + _t("prawa autorskie i dobre źródła") + "</a>")
        lic.setToolTip("O programie i licencja · prawa autorskie do pieśni")
        lic.linkActivated.connect(lambda k: self.copyright_info() if k == 'copy' else self.about())
        self.statusBar().addPermanentWidget(lic)
        # listy, których tekst program odczytuje jako wartość (wygląd slajdów, okres) – nie tłumaczyć
        for c in list(getattr(self, 'w', {}).values()) + [getattr(self, 'm_okres', None)]:
            if isinstance(c, QComboBox):
                c.setProperty("i18n_no", True)

    def _build_text_tab(self):
        w = QWidget()
        ml = QVBoxLayout(w)
        form = QFormLayout()
        self.e_title = QLineEdit()
        self.e_cat = QComboBox()
        self.e_cat.setEditable(True)
        self.e_cat.setInsertPolicy(QComboBox.NoInsert)
        self.e_cat.lineEdit().setPlaceholderText("wybierz lub wpisz nową")
        self.e_tags = QLineEdit(placeholderText="po przecinku, np. komunia, kanon, schola")
        self.tag_model = QStringListModel()
        comp = TagCompleter(self.tag_model, self)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchContains)
        self.e_tags.setCompleter(comp)
        self.e_notes = QLineEdit(placeholderText="autor, uwagi (nie trafia na slajdy)")
        self.e_src = QComboBox()
        self.e_src.setEditable(True)
        self.e_src.setInsertPolicy(QComboBox.NoInsert)
        self.e_src.setProperty("i18n_no", True)
        self.e_src.lineEdit().setPlaceholderText("śpiewnik / zbiór, np. Siedlecki, Niepojęta Trójco – wybierz lub wpisz")
        self.e_src.setToolTip("Źródło tekstu (śpiewnik, zbiór, wydawca) – do filtrowania listy i propozycji z liturgii")
        form.addRow("Tytuł:", self.e_title)
        form.addRow("Kategoria:", self.e_cat)
        form.addRow("Źródło:", self.e_src)
        form.addRow("Tagi:", self.e_tags)
        form.addRow("Uwagi:", self.e_notes)
        ml.addLayout(form)
        ml.addWidget(QLabel("Refren:"))
        self.e_ref = QPlainTextEdit()
        self.e_ref.setMaximumHeight(110)
        ml.addWidget(self.e_ref)
        ml.addWidget(QLabel("Zwrotki (numerowane „1.”, „2.” lub oddzielone pustą linią):"))
        self.e_verses = QPlainTextEdit()
        ml.addWidget(self.e_verses, 1)
        for x in (self.e_title, self.e_tags, self.e_notes):
            x.textChanged.connect(self.on_edit)
        self.e_cat.currentTextChanged.connect(self.on_edit)
        self.e_src.currentTextChanged.connect(self.on_edit)
        for x in (self.e_ref, self.e_verses):
            x.textChanged.connect(self.on_edit)
        return w

    def _build_cfg_tab(self):
        box = QWidget()
        g = QGridLayout(box)
        self.w = {}

        def chk(key, label, r, c):
            x = QCheckBox(label)
            x.toggled.connect(self.on_edit)
            self.w[key] = x
            g.addWidget(x, r, c)

        self.w['format'] = QComboBox()
        self.w['format'].addItems(['16:9', '4:3'])
        self.w['format'].currentIndexChanged.connect(self.on_edit)
        self.w['zwrotek_na_slajd'] = QSpinBox(minimum=1, maximum=10)
        self.w['zwrotek_na_slajd'].valueChanged.connect(self.on_edit)
        self.w['font'] = QFontComboBox()
        self.w['font'].currentFontChanged.connect(self.on_edit)
        self.w['font_scale'] = QDoubleSpinBox(minimum=0.3, maximum=2.0, singleStep=0.05, decimals=2)
        self.w['font_scale'].valueChanged.connect(self.on_edit)
        self.w['font_size'] = QSpinBox(minimum=10, maximum=200, suffix=" pt")
        self.w['font_size'].valueChanged.connect(self.on_edit)
        self.w['max_font'] = QSpinBox(minimum=20, maximum=200, suffix=" pt")
        self.w['max_font'].valueChanged.connect(self.on_edit)
        self.w['przyciemnienie'] = QSpinBox(minimum=0, maximum=90, suffix=" %")
        self.w['przyciemnienie'].valueChanged.connect(self.on_edit)
        self.w['przyciemnienie'].setToolTip("Ciemne tło – przyciemnia, jasne – rozjaśnia ozdobniki")
        for key in ('margines_x', 'margines_y'):
            self.w[key] = QSpinBox(minimum=0, maximum=35, suffix=" %")
            self.w[key].valueChanged.connect(self.on_edit)
        for key in ('kolor_tekstu', 'kolor_refrenu', 'kolor_tla'):
            self.w[key] = ColorButton()
            self.w[key].changed.connect(self.on_edit)
        self.bg_combo = QComboBox()
        self.bg_combo.setIconSize(QSize(64, 36))
        self.fill_bg_combo()
        self.bg_combo.currentIndexChanged.connect(self.on_bg_combo)

        r = 0                                               # najczęściej zmieniane – na górze
        g.addWidget(QLabel("<b>Zwrotek na slajd:</b>"), r, 0)
        g.addWidget(self.w['zwrotek_na_slajd'], r, 1)
        g.addWidget(QLabel("<b>Obraz tła:</b>"), r, 2)
        g.addWidget(self.bg_combo, r, 3)
        r += 1
        g.addWidget(QLabel("Format:"), r, 0)
        g.addWidget(self.w['format'], r, 1)
        hl3 = QHBoxLayout()
        hl3.addWidget(QLabel("Wyciszenie tła:"))
        hl3.addWidget(self.w['przyciemnienie'])
        hl3.addStretch()
        g.addLayout(hl3, r, 2, 1, 2)
        r += 1
        chk('refren_osobno', "Refren na osobnym slajdzie", r, 0)
        chk('powtarzaj_refren', "Powtarzaj refren", r, 1)
        chk('refren_na_koncu', "Refren także na końcu", r, 2)
        chk('numeruj', "Numeruj zwrotki", r, 3)
        r += 1
        chk('auto_interpunkcja', "Auto-interpunkcja", r, 0)
        chk('reflow', "Łącz wersy (reflow)", r, 1)
        chk('auto_size', "Auto-rozmiar czcionki", r, 2)
        chk('jednolity_rozmiar', "Jeden rozmiar w pieśni", r, 3)
        r += 1
        g.addWidget(QLabel("Czcionka:"), r, 0)
        g.addWidget(self.w['font'], r, 1)
        g.addWidget(QLabel("Skala / maks.:"), r, 2)
        hl = QHBoxLayout()
        hl.addWidget(self.w['font_scale'])
        hl.addWidget(self.w['max_font'])
        g.addLayout(hl, r, 3)
        r += 1
        g.addWidget(QLabel("Stały rozmiar:"), r, 0)
        g.addWidget(self.w['font_size'], r, 1)
        hl2 = QHBoxLayout()
        for key, lab in (('kolor_tekstu', "Tekst"), ('kolor_refrenu', "Refren"), ('kolor_tla', "Tło")):
            hl2.addWidget(QLabel(lab))
            hl2.addWidget(self.w[key])
        hl2.addStretch()
        g.addLayout(hl2, r, 2, 1, 2)
        r += 1
        chk('cien', "Cień / poświata pod tekstem", r, 0)
        g.addWidget(QLabel("Marginesy (bok / góra-dół):"), r, 2)
        hl4 = QHBoxLayout()
        hl4.addWidget(self.w['margines_x'])
        hl4.addWidget(self.w['margines_y'])
        g.addLayout(hl4, r, 3)
        r += 1
        self.bg_hint = QLabel("Wybór tła ustawia zalecane kolory tekstu i marginesy (można je potem zmienić).")
        self.bg_hint.setStyleSheet("color: gray;")
        g.addWidget(self.bg_hint, r, 0, 1, 4)
        r += 1
        b = QPushButton("Ustaw jako domyślne dla nowych pieśni")
        b.clicked.connect(self.save_default_cfg)
        g.addWidget(b, r, 0, 1, 2)
        b2 = QPushButton("Zastosuj do wszystkich pieśni w bazie…")
        b2.setToolTip("Ten wygląd slajdów (format, czcionka, kolory, tło, marginesy, układ) dostaną wszystkie\n"
                      "pieśni w bazie i nowe pieśni. Można to cofnąć: Plik → Cofnij ostatnie zmiany.")
        b2.clicked.connect(self.apply_cfg_to_all)
        g.addWidget(b2, r, 2, 1, 2)
        g.setRowStretch(r + 1, 1)
        return box

    def _build_chords_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        info = QLabel("Akordy w zapisie ChordPro: <b>[a]Chwalcie [E]Pana</b> – akord przed sylabą, nad którą się go gra. "
                      "Akordy z boku wiersza po znaku <b>‖</b>: „Pozdrawiam Cię, Matko ‖ D e / A D”. "
                      "Można też wkleić tekst z wierszami akordów nad słowami – „Zamień akordy nad tekstem” ustawi je "
                      "nad właściwymi sylabami. Slajdy pokazują sam tekst; akordy są w widoku dla gitarzystów.")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.e_chords = QPlainTextEdit()
        f = QFont("DejaVu Sans Mono")
        f.setStyleHint(QFont.Monospace)
        self.e_chords.setFont(f)
        self.e_chords.setPlaceholderText("[G]Chrystus Pan, Boży Syn, Zb[a]awca nasz, zgodził się\n"
                                         "[G]wziąć mój grzech, za mnie umrzeć c[C]hciał.")
        self.e_chords.textChanged.connect(self.on_edit)
        lay.addWidget(self.e_chords, 1)
        row = QHBoxLayout()
        for txt, fn in (("🎸 Widok dla gitarzystów…", self.show_chords),
                        ("Zamień akordy nad tekstem na ChordPro", self.chords_from_lines),
                        ("Wstaw tekst pieśni (bez akordów)", self.chords_from_text),
                        ("Transponuj ±…", self.chords_transpose)):
            b = QPushButton(txt)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        return w

    def show_chords(self, songs=None):
        import modul_akordy as ak
        if songs is None or isinstance(songs, bool):
            songs = [self.editor_song()]
        dlg = ak.ChordView(songs, self)
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        dlg.show()
        self._chord_view = dlg

    def show_set_chords(self):
        songs = [self.db.get(sid) for _, sid in self.set_entries()]
        songs = [s for s in songs if s]
        if not songs:
            QMessageBox.information(self, APP_NAME, "Zestaw jest pusty.")
            return
        self.show_chords(songs)

    def chords_from_lines(self):
        import modul_akordy as ak
        t = self.e_chords.toPlainText()
        new = ak.chord_lines_to_chordpro(t)
        if new == t:
            self.statusBar().showMessage("Nie znalazłem wierszy z samymi akordami nad tekstem.", 5000)
            return
        self.e_chords.setPlainText(new)

    def chords_from_text(self):
        s = self.editor_song()
        if self.e_chords.toPlainText().strip() and QMessageBox.question(
                self, APP_NAME, "Zastąpić obecne akordy samym tekstem pieśni?") != QMessageBox.Yes:
            return
        import modul_akordy as ak
        self.e_chords.setPlainText(ak.song_chordpro(dict(s, akordy="")))

    def chords_transpose(self):
        import modul_akordy as ak
        k, ok = QInputDialog.getInt(self, APP_NAME, "Transponuj akordy o półtony (np. 2 = o całą nutę w górę, −3 = w dół):",
                                    2, -11, 11)
        if ok and k:
            self.e_chords.setPlainText(ak.transpose_text(self.e_chords.toPlainText(), k))

    def _build_media_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        gb = QGroupBox("Nuty i pliki (PDF, MuseScore, MusicXML, MIDI, nagrania)")
        gl = QVBoxLayout(gb)
        self.att_list = QListWidget()
        self.att_list.itemDoubleClicked.connect(lambda it: self.preview_attachment())
        self.att_list.currentItemChanged.connect(self._att_buttons)
        gl.addWidget(self.att_list)
        g = QGridLayout()
        self.b_att = {}
        for i, (key, txt, fn) in enumerate([
                ('add', "Dodaj pliki… (lub przeciągnij tutaj)", self.add_attachments), ('view', "👁 Podgląd nut", self.preview_attachment),
                ('open', "Otwórz w programie (MuseScore…)", self.open_attachment), ('save', "Zapisz jako…", self.save_attachment),
                ('midi', "MIDI – odtwarzanie głosów…", self.play_midi), ('del', "Usuń", self.delete_attachment),
                ('search', "Szukaj nut w MuseScore…", self.search_scores),
                ('lyrics', "Słowa z tych nut → do tekstu pieśni…", self.lyrics_from_attachment),
                ('omr', "Rozpoznaj nuty z tego skanu (Audiveris)…", self.omr_attachment),
                ('melody', "🎼 Edytor melodii (nowa / ta melodia)…", lambda: self.melody_editor(self._sel_aid())),
                ('desc', "Wersja / aranżacja (opis)…", self.describe_attachment),
                ('merge', "Połącz z inną pieśnią…", self.merge_song_dialog)]):
            b = QPushButton(txt)
            b.clicked.connect(fn)
            self.b_att[key] = b
            g.addWidget(b, i // 2, i % 2)
        gl.addLayout(g)
        lay.addWidget(gb, 1)

        gv = QGroupBox("Wersje tekstu (z innych śpiewników, inne tłumaczenia, dawny tekst)")
        vl = QVBoxLayout(gv)
        self.ver_list = QListWidget()
        self.ver_list.itemDoubleClicked.connect(lambda it: self.show_version())
        self.ver_list.currentItemChanged.connect(self._ver_buttons)
        vl.addWidget(self.ver_list)
        g3 = QGridLayout()
        self.b_ver = {}
        for i, (key, txt, fn) in enumerate([
                ('view', "👁 Pokaż i porównaj", self.show_version), ('use', "Ustaw jako tekst główny", self.use_version),
                ('add', "Zapisz bieżący tekst jako wersję…", self.store_text_as_version),
                ('ren', "Zmień nazwę…", self.rename_version), ('del', "Usuń wersję", self.delete_version)]):
            b = QPushButton(txt)
            b.clicked.connect(fn)
            self.b_ver[key] = b
            g3.addWidget(b, i // 3, i % 3)
        vl.addLayout(g3)
        lay.addWidget(gv, 1)

        gy = QGroupBox("Nagrania z YouTube")
        yl = QVBoxLayout(gy)
        self.yt_list = QListWidget()
        self.yt_list.itemDoubleClicked.connect(lambda it: self.play_youtube_selected('video'))
        yl.addWidget(self.yt_list)
        g2 = QGridLayout()
        for i, (txt, fn) in enumerate([("Szukaj na YouTube…", self.youtube_search),
                                       ("Dodaj link…", self.youtube_add_link),
                                       ("▶ Wideo", lambda: self.play_youtube_selected('video')),
                                       ("♪ Tylko dźwięk + czyste tło", lambda: self.play_youtube_selected('audio')),
                                       ("Otwórz w przeglądarce", lambda: self.play_youtube_selected('browser')),
                                       ("Usuń", self.youtube_remove)]):
            b = QPushButton(txt)
            b.clicked.connect(fn)
            g2.addWidget(b, i // 2, i % 2)
        yl.addLayout(g2)
        lay.addWidget(gy, 1)
        self.media_hint = QLabel()
        self.media_hint.setWordWrap(True)
        lay.addWidget(self.media_hint)
        return w

    # ---- widoki proste (zakładki u dołu): Start, Teksty, Slajdy, Nuty, Zaawansowane
    V_START, V_TEXTS, V_SLIDES, V_SCORES, V_MASS, V_ADV = range(6)

    def _build_views(self):
        import modul_widoki as mw
        self.views = QTabWidget()
        self.views.setObjectName("views")
        self.views.setTabPosition(QTabWidget.South)
        self.views.setDocumentMode(True)
        tiles = [
            ("📖", "Teksty pieśni", "Przeglądaj i czytaj słowa – duże litery, wyszukiwanie po tytule i słowach.",
             lambda: self.views.setCurrentIndex(self.V_TEXTS)),
            ("🖥", "Slajdy i pokaz", "Wybierz pieśń i pokaż ją na rzutniku jednym przyciskiem.",
             lambda: self.views.setCurrentIndex(self.V_SLIDES)),
            ("🎼", "Nuty", "Zobacz nuty pieśni i posłuchaj melodii; poszukaj nut w MuseScore.",
             lambda: self.views.setCurrentIndex(self.V_SCORES)),
            ("⛪", "Zestaw na Mszę", "Zaplanuj pieśni na Mszę: części, liturgia dnia, eksport i pokaz.",
             self._go_set),
            ("🎵", "Edytor melodii", "Wpisz nuty, słowa i akordy jak w MuseScore; posłuchaj (chór i organy) i zapisz w pieśni.",
             self._go_melody),
            ("📖", "Liturgia z dnia", "Czytania, psalm i modlitwy z dzisiejszej Mszy oraz pasujące pieśni z Twojej bazy.",
             self._go_liturgy),
            ("🧹", "Porządki w bazie", "Duplikaty, kategorie, cofanie ostatnich zmian.", self.tidy_dialog),
            ("📥", "Importuj śpiewnik lub plik", "PDF, DOCX, TXT, nuty MuseScore – także całe śpiewniki.",
             self.import_files),
            ("🎸", "Akordy", "Tekst z akordami dla gitarzystów, z transpozycją.", self._go_chords),
            ("📱", "Pilot w telefonie", "Przełączaj slajdy z telefonu albo tabletu.", self.open_pilot),
            ("⚙", "Zaawansowane", "Pełny edytor: wygląd slajdów, załączniki, wersje, eksport, ustawienia.",
             lambda: self.views.setCurrentIndex(self.V_ADV)),
        ]
        if __import__('modul_i18n').LANG == 'la':          # po łacinie (dla tradycjonalistów) – bez kafla gitary :-)
            tiles = [t for t in tiles if t[1] != "Akordy"]
        self.home = mw.HomePage(tiles, support=[(ic, t, d, (lambda u=u, t=t, d=d, a=a: self._open_support(t, u, d, a)))
                                                for ic, t, d, u, a in SUPPORT])
        self._add_lang_button()
        self.v_texts = mw.TextsPage(self.db, self.set_entries, self._go_slides, self._go_edit)
        self.v_slides = mw.SlidesPage(self.db, self.set_entries, build_song_deck, SlideView, slide_pixmap,
                                      lambda deck, i: self._open_present(deck, i, True), self.present_setlist)
        self.v_mass = MassPage(self)
        self.v_scores = mw.ScoresPage(self.db, self.set_entries, self._attachment_pages, self._v_play,
                                      self._v_open, self._v_search, self._v_omr, self._v_melody)
        for w, name in ((self.home, "Start"), (self.v_texts, "Teksty"), (self.v_slides, "Slajdy"),
                        (self.v_scores, "Nuty"), (self.v_mass, "Msza"), (self.advanced, "Zaawansowane")):
            self.views.addTab(w, name)
        self.views.setCornerWidget(mw.Monogram(26), Qt.BottomRightCorner)
        self.cur_sid, self._prev_view = None, None
        for page in (self.v_texts, self.v_slides, self.v_scores):
            page.picker.chosen.connect(self._set_cur)
            page.picker.bulk.connect(self._picker_bulk)
        self.views.currentChanged.connect(self._view_changed)
        self.setCentralWidget(self.views)
        self.setWindowIcon(app_icon())

    def _set_cur(self, sid):
        self.cur_sid = sid

    def _view_changed(self, i):
        if hasattr(self, 'toolbar'):
            self.toolbar.setVisible(i == self.V_ADV)
        self.settings.setValue("view2", i)
        if self._prev_view == self.V_ADV and self.song and self.song.get('id'):
            self.cur_sid = self.song['id']                # pieśń z edytora idzie do pozostałych zakładek
        self._prev_view = i
        if i == self.V_START:
            self.home.set_info(f"Śpiewnik, slajdy i nuty dla scholi i chóru  ·  w bazie: {self.db.count()} pieśni")
        elif i in (self.V_TEXTS, self.V_SLIDES, self.V_SCORES):
            page = self.views.widget(i)
            sid = self.cur_sid if self.cur_sid and self.db.get(self.cur_sid) else page.sid
            page.sid = sid
            page.refresh()
            if sid:
                if not page.picker.select(sid):           # odfiltrowana – pokaż ją mimo filtrów
                    page.picker.reset_filters()
                    page.picker.select(sid)
                page.show_song(sid)
        elif i == self.V_MASS:
            self.v_mass.refresh()
        elif i == self.V_ADV and self.cur_sid and (not self.song or self.song.get('id') != self.cur_sid):
            if self.db.get(self.cur_sid):
                self.open_song(self.cur_sid)

    def _show_in(self, view, sid):
        self.cur_sid = sid
        page = self.views.widget(view)
        page.sid = sid
        self.views.setCurrentIndex(view)
        page.picker.q.clear()
        page.picker.refresh()
        page.picker.select(sid)
        page.show_song(sid)

    def _go_slides(self, sid):
        self._show_in(self.V_SLIDES, sid)

    def _go_edit(self, sid):
        self.cur_sid = sid
        self.views.setCurrentIndex(self.V_ADV)
        self.open_song(sid)
        self.tabs.setCurrentIndex(0)

    def _go_set(self):
        self.views.setCurrentIndex(self.V_MASS)

    def _go_set_adv(self):
        self.views.setCurrentIndex(self.V_ADV)
        self.setlist.setFocus()

    def _go_new(self):
        self.views.setCurrentIndex(self.V_ADV)
        self.new_song()
        self.tabs.setCurrentIndex(0)
        self.e_title.setFocus()

    def _go_chords(self):
        page = self.v_texts
        self.views.setCurrentIndex(self.V_TEXTS)
        page.b_ch.setChecked(True)

    def _ensure_open(self, sid, aid=None):
        """Pieśń z widoku prostego → otwarta w edytorze (i zaznaczony załącznik)."""
        if not self.song or self.song.get('id') != sid:
            if not self.maybe_save():
                return False
            s = self.db.get(sid)
            if not s:
                return False
            self.load_into_editor(s)
        self.refresh_media()
        if aid:
            for i in range(self.att_list.count()):
                if self.att_list.item(i).data(Qt.UserRole) == aid:
                    self.att_list.setCurrentRow(i)
        return True

    def _v_play(self, sid, aid):
        if self._ensure_open(sid, aid):
            self.play_midi()

    def _v_open(self, sid, aid):
        if self._ensure_open(sid, aid):
            self.open_attachment()

    def _v_search(self, sid):
        if self._ensure_open(sid):
            self.search_scores()

    def _go_melody(self):
        """Kafel „Edytor melodii”: melodia bieżącej pieśni albo nowa pieśń z melodią."""
        sid = self.cur_sid if self.cur_sid and self.db.get(self.cur_sid) else None
        if sid:
            s = self.db.get(sid)
            box = QMessageBox(QMessageBox.Question, APP_NAME, f"Edytor melodii – dla której pieśni?", parent=self)
            b_cur = box.addButton(f"„{s['title']}”", QMessageBox.AcceptRole)
            b_new = box.addButton("Nowa pieśń", QMessageBox.ActionRole)
            box.addButton("Anuluj", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() not in (b_cur, b_new):
                return
            if box.clickedButton() is b_new:
                sid = None
        if sid is None:
            title, ok = QInputDialog.getText(self, APP_NAME, "Tytuł nowej pieśni (słowa można dopisać później):")
            if not ok or not title.strip():
                return
            sid = self.db.save({'title': title.strip(), 'refren': '', 'zwrotki_raw': '', 'config': self.default_cfg()})
            self.refresh_list()
            self.cur_sid = sid
        aid = None
        for a in self.db.attachments(sid):                     # ostatnio zapisana melodia z edytora
            if a['name'].lower().endswith('.musicxml') and a['opis'].startswith("Melodia"):
                aid = a['id']
        self.views.setCurrentIndex(self.V_SCORES)
        self.v_scores.picker.reset_filters()
        self.v_scores.picker.select(sid)
        self._v_melody(sid, aid)

    def _v_melody(self, sid, aid=None):
        if self._ensure_open(sid, aid):
            self.melody_editor(aid)
            self.v_scores._shown = None
            self.v_scores.show_song(sid)

    def _sel_aid(self):
        it = self.att_list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def melody_editor(self, aid=None):
        """Prosty edytor melodii: nowa melodia albo dalsza edycja zapisanego pliku MusicXML."""
        import modul_edytor as me
        if not self.ensure_saved("Aby zapisać melodię w pieśni"):
            return
        sid, title = self.song['id'], self.song.get('title', '')
        mel, edit_aid = None, None
        row = self.db.attachment(aid) if aid else None
        if row and row['name'].lower().endswith(('.musicxml', '.xml')):
            try:
                mel, edit_aid = me.Melody.from_musicxml(bytes(row['data'])), aid
            except Exception as e:
                QMessageBox.warning(self, APP_NAME, f"Nie udało się odczytać melodii z tego pliku:\n{e}\nOtwieram nową melodię.")
        state = {'aid': edit_aid}

        def save(m):
            base = re.sub(r'[\\/:*?"<>|]+', "_", m.title or title or "melodia").strip() or "melodia"
            xml, mid = m.musicxml(), m.midi()
            if state['aid']:
                xname = self.db.attachment(state['aid'])['name']
                self.db.replace_attachment_data(state['aid'], xml)
            else:
                xname = base + " (melodia).musicxml"
                state['aid'] = self.db.add_attachment_bytes(sid, xname, xml, "Melodia – edytor")
            mname = os.path.splitext(xname)[0] + ".mid"
            old = [a for a in self.db.attachments(sid) if a['name'] == mname]
            if old:
                self.db.replace_attachment_data(old[0]['id'], mid)
            else:
                self.db.add_attachment_bytes(sid, mname, mid, "Melodia – edytor")
            self.convert_in_background(state['aid'])
            self.pilot_invalidate()
            self.refresh_media()
            self.refresh_list()
            return f"Zapisano w pieśni „{title}”: {xname} i {mname}"

        def chords(text):
            cur = self.e_chords.toPlainText().strip()
            if cur and QMessageBox.question(self, APP_NAME, "Pieśń ma już akordy. Zastąpić je słowami z akordami z edytora melodii?") != QMessageBox.Yes:
                return
            self.e_chords.setPlainText(text)
            self.statusBar().showMessage("Akordy wstawione – zapisz pieśń (Ctrl+S).", 6000)

        dlg = me.MelodyEditor(self, mel, title, on_save=save, on_chords=chords)
        dlg.exec()

    def _v_omr(self, sid):
        if self._ensure_open(sid):
            self.omr_from_file()
            self.v_scores.show_song(sid)

    def _attachment_pages(self, sid, aid):
        """Strony nut do podglądu: ([jpeg…], opis, czy da się odtworzyć)."""
        import modul_nuty
        a = self.db.attachment(aid)
        if not a:
            return [], "", False
        name, data, low = a['name'], a['data'], a['name'].lower()
        if low.endswith('.pdf'):
            return modul_nuty.pdf_pages_to_jpeg(data, width=1600, quality=85), "", False
        if low.endswith(('.png', '.jpg', '.jpeg')):
            return [data], "", False
        if low.endswith(SCORE_EXT):
            pdf, midi, pos = self._derived_now(a['id'], name, data)
            if pdf:
                return modul_nuty.pdf_pages_to_jpeg(pdf, width=1600, quality=85), "", True
            thumb = modul_nuty.mscz_thumbnail(data)
            return ([thumb] if thumb else []), ("Pokazuję miniaturę 1. strony – pełny podgląd wymaga MuseScore "
                                               "(Zaawansowane → Ustawienia → Ścieżka do MuseScore)."), True
        if low.endswith(('.mid', '.midi', '.kar')):
            return [], "Plik MIDI – kliknij „Posłuchaj”.", True
        return [], "", False

    TB_SHORT = {"Nowa pieśń": "Nowa", "Zapisz w bazie": "Zapisz", "Eksport do PDF…": "PDF", "Eksport do PPTX…": "PPTX",
                "Eksport do DOCX…": "DOCX", "♿ Eksport dla niewidomych (DOCX, TXT, HTML, MP3)…": "Niewidomi", "Importuj z pliku (DOCX, ODT, PDF, TXT, HTML)…": "Import",
                "Importuj ze strony WWW…": "Z WWW", "Szukaj w śpiewnikach internetowych i nut w MuseScore…": "Szukaj w sieci", "Pokaz od początku": "Pokaz", "📱 Pilot w telefonie / tablecie…": "Pilot"}

    def _build_actions(self):
        import ikony
        tb = QToolBar("Główne")
        tb.setMovable(False)
        tb.setIconSize(QSize(22, 22))
        self.toolbar = tb
        self.addToolBar(tb)
        m_file = self.menuBar().addMenu("&Plik")
        m_song = self.menuBar().addMenu("P&ieśń")
        m_show = self.menuBar().addMenu("P&okaz")
        m_set = self.menuBar().addMenu("&Ustawienia")
        m_help = self.menuBar().addMenu("Pomo&c")

        def act(menu, text, fn, key=None, on_tb=False):
            name, clean = ikony.icon_for_label(text)
            a = QAction(clean or text, self)
            if name:
                ikony.set_icon(a, name)
            a.setIconText(self.TB_SHORT.get(text, clean))
            a.setToolTip(clean + (f"  ({key})" if key else ""))
            a.triggered.connect(fn)
            if key:
                a.setShortcut(QKeySequence(key))
            menu.addAction(a)
            if on_tb:
                tb.addAction(a)
            return a

        act(m_song, "Nowa pieśń", lambda: self.new_song(), "Ctrl+N", True)
        act(m_song, "Zapisz w bazie", self.save_song, "Ctrl+S", True)
        act(m_song, "Duplikuj", self.duplicate_song)
        act(m_song, "Usuń z bazy", self.delete_song)
        act(m_song, "Szukaj nut w MuseScore (po tytule)…", self.search_scores, "Ctrl+M")
        act(m_song, "Rozpoznaj nuty ze skanu / zdjęcia (Audiveris)…", self.omr_from_file)
        act(m_song, "🎼 Edytor melodii (nuty, słowa, akordy)…", lambda: self.melody_editor(), "Ctrl+Shift+N")
        act(m_song, "🎸 Akordy – widok dla gitarzystów…", self.show_chords, "Ctrl+G")
        act(m_song, "🎸 Akordy całego zestawu…", self.show_set_chords)
        act(m_song, "Połącz z inną pieśnią (ta sama pieśń, inna wersja)…", self.merge_song_dialog)
        act(m_song, "Kategoria dla zaznaczonych pieśni…", self.bulk_category)
        act(m_song, "Tagi dla zaznaczonych pieśni (dodaj / usuń)…", self.bulk_tags)
        act(m_song, "📚 Źródło (śpiewnik) dla zaznaczonych pieśni…", self.bulk_source)
        act(m_song, "Zapisz bieżący tekst jako wersję…", self.store_text_as_version)
        m_song.addSeparator()
        act(m_song, "Eksport do PDF…", lambda: self.export_current('pdf'), "Ctrl+E", True)
        act(m_song, "Eksport do PPTX…", lambda: self.export_current('pptx'), "Ctrl+Shift+E", True)
        act(m_song, "Eksport do DOCX…", lambda: self.export_current('docx'), "Ctrl+D", True)
        act(m_song, "📦 Eksport materiałów (teksty, nuty PDF, nagrania MP3)…", self.export_song_package, "Ctrl+Shift+M")
        act(m_song, "♿ Eksport dla niewidomych (DOCX, TXT, HTML, MP3)…", self.export_song_blind, "Ctrl+Shift+D", True)
        tb.addSeparator()
        act(m_file, "Importuj z pliku (DOCX, ODT, PDF, TXT, HTML)…", self.import_files, "Ctrl+I", True)
        act(m_file, "Importuj słowa z nut (MuseScore, MusicXML, PDF z nutami, MIDI)…", self.import_from_scores)
        act(m_file, "Importuj ze strony WWW…", self.import_url, "Ctrl+U", True)
        act(m_file, "Szukaj w śpiewnikach internetowych i nut w MuseScore…", self.search_online, "Ctrl+Shift+F", True)
        act(m_file, "Importuj pliki JSON z wersji 6.x…", self.import_json_v6)
        act(m_file, "Importuj z poprzedniej instalacji (baza, nuty, ustawienia)…", self.import_previous)
        m_file.addSeparator()
        act(m_file, "↶ Cofnij ostatnie zmiany w bazie (import, łączenie, usuwanie)…", self.undo_db_dialog, "Ctrl+Shift+Z")
        act(m_file, "Znajdź i połącz duplikaty pieśni…", self.find_duplicates)
        act(m_file, "🏷 Menedżer kategorii (zmiana nazw, łączenie, usuwanie)…", self.category_manager)
        act(m_file, "📚 Menedżer źródeł – śpiewników (zmiana nazw, łączenie, usuwanie)…", self.source_manager)
        m_file.addSeparator()
        act(m_file, "Eksport śpiewnika offline HTML (telefon, tablet)…", lambda: self.export_html(None), "Ctrl+H")
        m_file.addSeparator()
        act(m_file, "Otwórz / utwórz inną bazę…", self.choose_db)
        act(m_file, "Zakończ", self.close, "Ctrl+Q")
        tb.addSeparator()
        act(m_show, "Pokaz od początku", lambda: self.start_present(0), "F5", True)
        act(m_show, "Pokaz od bieżącego slajdu", lambda: self.start_present(self.thumbs.currentRow()), "Shift+F5")
        act(m_show, "Pokaz zestawu", self.present_setlist, "Ctrl+F5")
        act(m_show, "Czyste tło na rzutniku (bez tekstu) – wł./wył.", self.toggle_clean, "Ctrl+Shift+C")
        act(m_show, "📱 Pilot w telefonie / tablecie…", self.open_pilot, "Ctrl+P", True)
        m_show.addSeparator()
        self.screen_menu = m_show.addMenu("Ekran pokazu")
        self.screen_menu.aboutToShow.connect(self.fill_screen_menu)
        act(m_set, "Ścieżka do MuseScore (AppImage, .exe…) – podgląd plików .mscz…", self.set_musescore_path)
        act(m_set, "Ścieżka do Audiveris (rozpoznawanie nut ze skanu)…", self.set_audiveris_path)
        a_perg = QAction("Wygląd: jasny pergamin (po ponownym uruchomieniu)", self, checkable=True)
        a_perg.setChecked(self.settings.value("pergamin", True, type=bool))
        a_perg.toggled.connect(lambda v: (self.settings.setValue("pergamin", v), self.settings.sync(),
                                          self.statusBar().showMessage("Zmiana wyglądu po ponownym uruchomieniu.", 6000)))
        m_set.addAction(a_perg)
        act(m_set, "Test MuseScore (próbna konwersja z raportem)…", self.test_musescore)
        m_lang = m_set.addMenu("🌐 Język / Language")
        try:
            import modul_i18n
            cur = self.settings.value("language", "") or modul_i18n.LANG
            for code, name in modul_i18n.available():
                a = QAction(name, self, checkable=True)
                a.setChecked(code == cur)
                a.triggered.connect(lambda _=False, c=code: self.set_language(c))
                m_lang.addAction(a)
        except Exception:
            pass
        m_tb = m_set.addMenu("Pasek narzędzi")
        m_tb.setIcon(ikony.fa_icon("sliders") if os.path.exists(os.path.join(ikony.ICON_DIR, "sliders.svg")) else QIcon())
        from PySide6.QtGui import QActionGroup
        grp = QActionGroup(self)
        for key, label, style in (("under", "Ikony z podpisem", Qt.ToolButtonTextUnderIcon),
                                  ("beside", "Ikony z napisem obok", Qt.ToolButtonTextBesideIcon),
                                  ("icon", "Same ikony", Qt.ToolButtonIconOnly)):
            a = m_tb.addAction(label)
            a.setCheckable(True)
            a.setActionGroup(grp)
            a.setChecked(self.settings.value("toolbar_style", "under") == key)
            a.triggered.connect(lambda _=False, k=key, st=style: (self.settings.setValue("toolbar_style", k),
                                                                     self.toolbar.setToolButtonStyle(st)))
        m_ic = m_set.addMenu("Ikony")
        m_ic.setIcon(ikony.fa_icon("palette"))
        for title, items, key in (("Styl", ikony.STYLES, "icon_style"),
                                  ("Kolory", [(k, n) for k, n, _ in ikony.THEMES], "icon_theme")):
            m_ic.addSeparator()
            hdr = m_ic.addAction(title)
            hdr.setEnabled(False)
            g = QActionGroup(self)
            cur = self.settings.value(key, items[0][0])
            for k, n in items:
                a = m_ic.addAction(n)
                a.setCheckable(True)
                a.setActionGroup(g)
                a.setChecked(cur == k)
                a.triggered.connect(lambda _=False, kk=key, v=k: self.set_icon_theme(kk, v))
        tb.setToolButtonStyle({"under": Qt.ToolButtonTextUnderIcon, "beside": Qt.ToolButtonTextBesideIcon,
                               "icon": Qt.ToolButtonIconOnly}.get(self.settings.value("toolbar_style", "under"),
                                                                   Qt.ToolButtonTextUnderIcon))
        act(m_help, "Skróty w pokazie", lambda: QMessageBox.information(self, APP_NAME, (
            "→ / spacja / PgDn – dalej\n← / PgUp – wstecz\nHome / End – początek / koniec\n"
            "B – czarny ekran\nC – czyste tło (bez tekstu)\nEsc – koniec pokazu\n\n"
            "Pilot w telefonie: Pokaz → Pilot w telefonie (Ctrl+P), zeskanuj kod QR.")))
        act(m_help, "O programie i licencja", self.about)
        act(m_help, "© Prawa autorskie do pieśni, dobre źródła, dokumenty Kościoła…", self.copyright_info)
        act(m_help, "🌍 Udostępnij swoje melodie i aranżacje na MuseScore.com…",
            lambda: __import__('modul_edytor').share_musescore(self))
        ikony.apply_icons(self)
        self.search_icon = self.search.addAction(ikony.fa_icon("magnifying-glass"), QLineEdit.LeadingPosition)
        self.search_icon.setProperty("fa_name", "magnifying-glass")
        self._decor_icons()
        sc = QAction(self)
        sc.setShortcut(QKeySequence("Ctrl+F"))
        sc.triggered.connect(lambda: (self.search.setFocus(), self.search.selectAll()))
        self.addAction(sc)
        self.statusBar().showMessage(f"Baza: {self.db.path}")

    def _decor_icons(self):
        import ikony
        self.screen_menu.setIcon(ikony.fa_icon("display"))
        for i, name in enumerate(("align-left", "palette", "music")):
            self.tabs.setTabIcon(i, ikony.fa_icon(name))

    def set_icon_theme(self, key, value):
        """Zmiana stylu lub kolorów ikon – od razu w całym oknie."""
        import ikony
        self.settings.setValue(key, value)
        self.settings.sync()
        ikony.refresh_icons(self)
        self._decor_icons()
        for d in list(self.midi_dialogs) + [getattr(self, 'score_dlg', None)]:
            if d is not None:
                ikony.refresh_icons(d)

    def about(self):
        QMessageBox.about(self, APP_NAME, (
            f"<h2 style='margin:0'>{APP_NAME}</h2><i>{APP_MOTTO}</i> &nbsp; – &nbsp; wersja {VERSION}<br><br>"
            "<i>Liber canticorum</i> – po łacinie „księga pieśni”; <i>liber</i> to księga, "
            "a zarazem echo <i>libre</i> – wolny, jak wolne oprogramowanie.<br><br>"
            "Program do przygotowywania i wyświetlania slajdów z tekstami pieśni, nut i nagrań.<br><br>"
            "Licencja: <b>GNU GPL w wersji 3 lub późniejszej</b> – możesz używać, kopiować, zmieniać "
            "i rozpowszechniać program, także zmieniony, pod warunkiem udostępnienia kodu źródłowego "
            "na tej samej licencji. Program jest dostarczany bez żadnej gwarancji.<br>"
            "Obrazy teł z folderu <i>tla</i>: CC0 (domena publiczna).<br>"
            "Ikony: <a href='https://fontawesome.com'>Font Awesome Free</a> (Fonticons, Inc.), licencja CC BY 4.0.<br>"
            "Ikona programu: inicjał C z pierwszej strony Kancjonału staniąteckiego A z 1586 r. "
            "(<i>Cancional pyosnek rozmaitich a naboznych</i>; Opactwo Mniszek Benedyktynek w Staniątkach), fot. Mkonik80, "
            "<a href='https://commons.wikimedia.org/wiki/File:Staniatki-kanc-A-001.jpg'>Wikimedia Commons</a>, "
            "CC BY-SA 4.0; ikona: CC BY-SA 4.0.<br><br>"
            "Teksty pieśni, nuty i nagrania dodaje użytkownik – za prawa do nich odpowiada on sam."))

    # ================= lista / wyszukiwanie / filtry =================
    def refresh_filters(self):
        if hasattr(self, 'mass_combo'):
            self.refresh_mass_combo()
        cur_c, cur_t, cur_s = self.f_cat.currentText(), self.f_tag.currentText(), self.f_src.currentText()
        cats, tags, srcs = self.db.categories(), self.db.tags(), self.db.sources()
        for combo, items, cur in ((self.f_cat, cats, cur_c), (self.f_tag, tags, cur_t), (self.f_src, srcs, cur_s)):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(__import__("modul_i18n").tr(self.ALL), None)
            for name, n in items:
                combo.addItem(f"{name or __import__('modul_i18n').tr('(bez źródła)' if combo is self.f_src else self.NONE_CAT)} ({n})", name)
            idx = combo.findText(cur, Qt.MatchStartsWith) if cur and cur != self.ALL else 0
            combo.setCurrentIndex(max(0, idx))
            combo.blockSignals(False)
        used = [c for c, _ in cats if c]
        try:
            used += json.loads(self.settings.value("extra_categories", "[]") or "[]")   # nowe z menedżera kategorii
        except ValueError:
            pass
        cur = self.e_cat.currentText()
        self.e_cat.blockSignals(True)
        self.e_cat.clear()
        self.e_cat.addItem("")
        self.e_cat.addItems(sorted(set(DEFAULT_CATEGORIES) | set(used), key=lambda x: (x not in DEFAULT_CATEGORIES, DEFAULT_CATEGORIES.index(x) if x in DEFAULT_CATEGORIES else 0, x)))
        self.e_cat.setCurrentText(cur)
        self.e_cat.blockSignals(False)
        self.tag_model.setStringList(sorted(set(DEFAULT_TAGS) | {t for t, _ in tags}))
        cur = self.e_src.currentText()
        self.e_src.blockSignals(True)
        self.e_src.clear()
        self.e_src.addItems([""] + sorted({x for x, _ in srcs if x} | {n for _, n in SPIEWNIKI_ADRESY}))
        self.e_src.setCurrentText(cur)
        self.e_src.blockSignals(False)

    def refresh_list(self):
        self.results.clear()
        q = self.search.text()
        cat = self.f_cat.currentData()
        tag = self.f_tag.currentData()
        rows = self.db.search(q, cat, tag, self.f_src.currentData())
        att = self.db.attachment_counts()
        words = fold(q).split()
        groups = {}
        order = {c: i for i, c in enumerate(DEFAULT_CATEGORIES)}
        for r in rows:
            groups.setdefault(r['kategoria'] or '', []).append(r)
        for cat_name in sorted(groups, key=lambda c: (c == '', order.get(c, 99), c)):
            top = QTreeWidgetItem([f"{cat_name or self.NONE_CAT}  ({len(groups[cat_name])})"])
            f = top.font(0)
            f.setBold(True)
            top.setFont(0, f)
            top.setFlags(Qt.ItemIsEnabled)
            self.results.addTopLevelItem(top)
            for r in groups[cat_name]:
                text = r['title'] + ("  ♪" if att.get(r['id']) else "")
                body = (r['refren'] or '') + "\n" + (r['zwrotki'] or '')
                if words and not all(w in fold(r['title']) for w in words):
                    for line in body.splitlines():
                        if words[0] in fold(line):
                            text += f"  —  …{line.strip()[:45]}…"
                            break
                if r['spiewnik']:
                    text += f"  · {r['spiewnik']}"
                it = QTreeWidgetItem([text])
                it.setData(0, Qt.UserRole, r['id'])
                it.setToolTip(0, (f"Źródło: {r['spiewnik']}\n" if r['spiewnik'] else "") +
                              (f"Tagi: {r['tagi']}\n\n" if r['tagi'] else "") + body.strip()[:400])
                top.addChild(it)
            top.setExpanded(True)
        self.count_lbl.setText(f"{len(rows)} z {self.db.count()} pieśni")

    def _on_result(self, item, col=0):
        sid = item.data(0, Qt.UserRole)
        if sid:
            self.open_song(sid)

    def _results_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        m = QMenu(self)
        n = len(self.selected_result_ids())
        m.addAction(f"Kategoria dla zaznaczonych ({n})…", self.bulk_category)
        m.addAction(f"Tagi dla zaznaczonych ({n})…", self.bulk_tags)
        m.addAction(f"Źródło dla zaznaczonych ({n})…", self.bulk_source)
        m.addAction("↓ Do zestawu", self.add_to_set)
        m.addSeparator()
        m.addAction("Znajdź i połącz duplikaty…", self.find_duplicates)
        m.exec(self.results.viewport().mapToGlobal(pos))

    def selected_result_ids(self):
        return [it.data(0, Qt.UserRole) for it in self.results.selectedItems() if it.data(0, Qt.UserRole)]

    # ================= edycja =================
    def cfg_from_widgets(self):
        c = {}
        for k, w in self.w.items():
            if isinstance(w, QCheckBox):
                c[k] = w.isChecked()
            elif isinstance(w, QFontComboBox):
                fam = w.currentFont().family()          # zachowaj żądaną nazwę (np. Arial), gdy Qt podstawił zamiennik
                req = getattr(self, '_font_req', None)
                c[k] = req if req and fam == self._font_resolved else fam
            elif isinstance(w, QComboBox):
                c[k] = w.currentText()
            elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
                c[k] = w.value()
            elif isinstance(w, ColorButton):
                c[k] = w.color
        c['tlo'] = self.bg_combo.currentData() or ''
        return c

    def load_into_editor(self, song):
        self._pending_attach = None
        self.loading = True
        self.song = song
        self.e_title.setText(song.get('title', ''))
        self.e_cat.setCurrentText(song.get('kategoria', ''))
        self.e_src.setCurrentText(song.get('spiewnik', ''))
        self.e_tags.setText(song.get('tagi', ''))
        self.e_notes.setText(song.get('uwagi', ''))
        self.e_ref.setPlainText(song.get('refren', ''))
        self.e_verses.setPlainText(song.get('zwrotki_raw', ''))
        self.e_chords.setPlainText(song.get('akordy', ''))
        cfg = song_cfg(song)
        for k, w in self.w.items():
            v = cfg[k]
            if isinstance(w, QCheckBox):
                w.setChecked(bool(v))
            elif isinstance(w, QFontComboBox):
                w.setCurrentFont(QFont(v))
                self._font_req, self._font_resolved = v, w.currentFont().family()
            elif isinstance(w, QComboBox):
                w.setCurrentText(str(v))
            elif isinstance(w, QSpinBox):
                w.setValue(int(v))
            elif isinstance(w, QDoubleSpinBox):
                w.setValue(float(v))
            elif isinstance(w, ColorButton):
                w.set_color(v)
        self.select_bg(cfg.get('tlo', ''))
        self.loading = False
        self.set_dirty(False)
        self.rebuild_deck()
        self.thumbs.setCurrentRow(0)
        self.refresh_media()

    def editor_song(self):
        s = dict(self.song or {})
        s.update({'title': self.e_title.text().strip() or "Bez tytułu", 'tagi': norm_tags(self.e_tags.text()),
                  'kategoria': self.e_cat.currentText().strip(), 'uwagi': self.e_notes.text().strip(),
                  'spiewnik': self.e_src.currentText().strip(),
                  'refren': self.e_ref.toPlainText().strip(), 'zwrotki_raw': self.e_verses.toPlainText().strip(),
                  'akordy': self.e_chords.toPlainText().rstrip(),
                  'config': self.cfg_from_widgets()})
        return s

    def on_edit(self, *_):
        if self.loading:
            return
        self.set_dirty(True)
        self.rebuild_timer.start()

    def set_dirty(self, d):
        self.dirty = d
        t = (self.song or {}).get('title') or "(nowa)"
        self.setWindowTitle(f"{'● ' if d else ''}{t} – {APP_NAME} {VERSION}")

    def maybe_save(self):
        if not self.dirty:
            return True
        r = QMessageBox.question(self, APP_NAME, "Zapisać zmiany w bieżącej pieśni?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Save:
            return self.save_song()
        return r == QMessageBox.Discard

    def default_cfg(self):
        try:
            return dict(DEFAULT_CFG, **json.loads(self.settings.value("default_cfg", "{}")))
        except Exception:
            return dict(DEFAULT_CFG)

    def save_default_cfg(self):
        self.settings.setValue("default_cfg", json.dumps(self.cfg_from_widgets()))
        self.settings.sync()                             # od razu na dysk – nie dopiero przy zamykaniu
        self.statusBar().showMessage("Zapisano ustawienia domyślne dla nowych pieśni.", 4000)

    SONG_OWN_CFG = ('numeruj',)                          # zależy od pieśni, nie od wyglądu

    def apply_cfg_to_all(self):
        n = self.db.count()
        if QMessageBox.question(self, APP_NAME, f"Zastosować bieżący wygląd slajdów do wszystkich {n} pieśni w bazie?\n"
                                "(Numerowanie zwrotek każda pieśń zachowuje swoje.)\n"
                                "Można to cofnąć: Plik → Cofnij ostatnie zmiany w bazie.") != QMessageBox.Yes:
            return
        cfg = self.cfg_from_widgets()
        self.db.snapshot("Wygląd slajdów dla wszystkich pieśni")
        k = 0
        for r in self.db.con.execute("SELECT id, config FROM songs").fetchall():
            old = json.loads(r['config'] or '{}')
            new = dict(old, **{key: v for key, v in cfg.items() if key not in self.SONG_OWN_CFG})
            if new != old:
                self.db.con.execute("UPDATE songs SET config=? WHERE id=?", (json.dumps(new, ensure_ascii=False), r['id']))
                k += 1
        self.db.con.commit()
        self.settings.setValue("default_cfg", json.dumps(cfg))
        self.settings.sync()
        if self.song and self.song.get('id'):
            self.song['config'] = dict(self.song.get('config', {}), **{key: v for key, v in cfg.items()
                                                                       if key not in self.SONG_OWN_CFG})
        self.pilot_invalidate()
        self.statusBar().showMessage(f"Zmieniono wygląd {k} pieśni; nowe pieśni też dostaną ten wygląd.", 8000)

    def new_song(self, ask=True, song=None):
        if ask and not self.maybe_save():
            return
        song = song or {'title': '', 'refren': '', 'zwrotki_raw': '', 'config': self.default_cfg()}
        self.load_into_editor(song)
        if song.get('zwrotki_raw') or song.get('refren'):
            self.set_dirty(True)
        self.e_title.setFocus()

    def open_song(self, sid):
        if self.song and self.song.get('id') == sid:
            return
        if not self.maybe_save():
            return
        s = self.db.get(sid)
        if s:
            self.load_into_editor(s)

    def save_song(self):
        s = self.editor_song()
        if not s.get('id'):
            cands = self.db.find_similar(s['title'], s.get('refren', ''), s.get('zwrotki_raw', ''))
            if cands:
                choice = MergeChoiceDialog(s, cands, self.db, self).choose()
                if choice is None:
                    return False
                if choice != 'new':
                    return self._save_into_existing(s, choice)
        self.db.save(s)
        self.song = s
        pend, self._pending_attach = getattr(self, '_pending_attach', None), None
        if pend and s.get('id') and os.path.isfile(pend):
            self.convert_in_background(self.db.add_attachment(s['id'], pend))
        self.loading = True
        self.e_tags.setText(s['tagi'])
        self.loading = False
        self.set_dirty(False)
        self.refresh_filters()
        self.refresh_list()
        self.refresh_media()
        self.pilot_invalidate()
        self.statusBar().showMessage(f"Zapisano: {s['title']}", 4000)
        return True

    def _save_into_existing(self, s, target):
        """Nowa (zaimportowana / wpisana) pieśń dołączona do istniejącej: inny tekst jako wersja, plik nut jako aranżacja."""
        self.db.snapshot(f"Dołączenie „{s['title']}” do „{self.db.get(target)['title']}”")
        label = s.get('zrodlo') or "Wersja " + datetime.date.today().isoformat()
        song, what = self.db.merge_import(target, s, version_name=label)
        pend, self._pending_attach = getattr(self, '_pending_attach', None), None
        if pend and os.path.isfile(pend):
            aid = self.db.add_attachment(target, pend)
            self.db.set_attachment_desc(aid, label)
            self.convert_in_background(aid)
            what.append("nuty")
        self.dirty = False
        self.load_into_editor(self.db.get(target))
        self.refresh_filters()
        self.refresh_list()
        self.refresh_media()
        self.pilot_invalidate()
        self.statusBar().showMessage(f"Dołączono do „{song['title']}”: {', '.join(what) or 'uwagi i tagi'}.", 8000)
        return True

    def merge_song_dialog(self):
        """Bieżąca pieśń jest tą samą pieśnią co inna w bazie – połącz (tekst jako wersja, nuty, nagrania, zestawy)."""
        if not self.ensure_saved("Aby połączyć pieśni"):
            return
        s = self.song
        cands = self.db.find_similar(s['title'], s['refren'], s['zwrotki_raw'], limit=8, exclude=s['id'])
        dlg = MergeChoiceDialog(s, cands, self.db, self, existing=True)
        target = dlg.choose()
        if target in (None, 'new'):
            return
        b = self.db.get(target)
        keep_this = dlg.keep_this.isChecked()
        src, dst = (target, s['id']) if keep_this else (s['id'], target)
        self.db.snapshot(f"Połączenie „{s['title']}” z „{b['title']}”")
        res = self.db.merge_songs(src, dst)
        self.dirty = False
        self.load_into_editor(self.db.get(dst))
        self.refresh_filters()
        self.refresh_list()
        self.refresh_media()
        self.restore_set()
        self.pilot_invalidate()
        if res:
            self.statusBar().showMessage(f"Połączono w „{res['title']}”. Wersje tekstu i nuty – zakładka „Nuty i wersje”.", 8000)

    def find_duplicates(self):
        if self.dirty and not self.maybe_save():
            return
        from PySide6.QtWidgets import QProgressDialog
        pd = QProgressDialog("Szukam duplikatów…", None, 0, 100, self)
        pd.setWindowTitle(APP_NAME)
        pd.setMinimumDuration(300)

        def prog(i, n):
            pd.setValue(int(100 * i / max(n, 1)))
            QApplication.processEvents()
        try:
            groups = self.db.duplicate_groups(prog)
        finally:
            pd.close()
        dlg = DuplicatesDialog(self.db, groups, self)
        dlg.exec()
        if dlg.merged:
            sid = (self.song or {}).get('id')
            self.dirty = False
            if sid and self.db.get(sid):
                self.load_into_editor(self.db.get(sid))
            else:
                self.new_song(ask=False)
            self.refresh_filters()
            self.refresh_list()
            self.restore_set()
            self.pilot_invalidate()
            self.statusBar().showMessage(f"Połączono {dlg.merged} duplikatów. Można to cofnąć: Plik → Cofnij ostatnie zmiany.",
                                         10000)

    def _bulk_ids(self):
        ids = self.selected_result_ids()
        if not ids:
            QMessageBox.information(self, APP_NAME, "Zaznacz pieśni na liście w zakładce „Zaawansowane” "
                                    "(Ctrl+klik – pojedyncze, Shift+klik – zakres, Ctrl+A – wszystkie widoczne).")
            self.views.setCurrentIndex(self.V_ADV)
            self.results.setFocus()
        return ids

    def _picker_bulk(self, action, ids):
        """Działania na pieśniach zaznaczonych w prostych widokach (Teksty, Slajdy, Nuty)."""
        if action == 'merge':
            self.merge_ids(ids)
        elif action == 'category':
            self.bulk_category(ids)
        elif action == 'tags':
            self.bulk_tags(ids)
        elif action == 'source':
            self.bulk_source(ids)
        elif action == 'duplicates':
            self.find_duplicates()
        elif action == 'categories':
            self.category_manager()
        elif action == 'sources':
            self.source_manager()
        self._refresh_pickers()

    def _open_support(self, title, url, desc="", acc=None):
        """Kafel „Wesprzyj”: okno z opisem, numerem konta (do skopiowania) i stroną WWW."""
        url = support_url(title, url)
        import modul_i18n
        title, desc = modul_i18n.tr(title), modul_i18n.tr(desc)
        d = QDialog(self)
        d.setWindowTitle(title)
        lay = QVBoxLayout(d)
        if acc and acc.get('baner'):
            pm = QPixmap(os.path.join(APP_DIR, acc['baner']))
            if not pm.isNull():
                b = QLabel()
                b.setPixmap(pm.scaledToWidth(620, Qt.SmoothTransformation))
                b.setAlignment(Qt.AlignCenter)
                lay.addWidget(b)
        h = QLabel(f"<h2>{H.escape(title)}</h2><p>{H.escape(desc)}</p>")
        h.setWordWrap(True)
        lay.addWidget(h)
        if acc and acc.get('szukaj_parafii'):
            if modul_i18n.LANG != 'pl':                      # za granicą: najbliższa parafia MB z Guadalupe
                from urllib.parse import quote
                q = modul_i18n.tr("parafia Matki Bożej z Guadalupe")
                bf = QPushButton("🔎 Znajdź najbliższą parafię Matki Bożej z Guadalupe")
                f_ = bf.font()
                f_.setPointSizeF(f_.pointSizeF() * 1.2)
                f_.setBold(True)
                bf.setFont(f_)
                bf.clicked.connect(lambda: QDesktopServices.openUrl(
                    QUrl("https://www.google.com/maps/search/" + quote(q))))
                lay.addWidget(bf)
        if acc and acc.get('zaangazuj'):
            z = QLabel(f"<b>{modul_i18n.tr('Jak się włączyć?')}</b><br>{H.escape(modul_i18n.tr(acc['zaangazuj']))}")
            z.setWordWrap(True)
            lay.addWidget(z)
        if acc and acc.get('konta'):
            lay.addWidget(QLabel(f"<b>{modul_i18n.tr('Odbiorca:')}</b> {H.escape(acc['odbiorca'])}", wordWrap=True))
            for bank, nr in acc['konta']:
                row = QHBoxLayout()
                lab = QLabel(f"<b>{H.escape(bank)}:</b><br><span style='font-size:15pt; font-family:monospace'>{nr}</span>")
                lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
                row.addWidget(lab, 1)
                b = QPushButton("📋 Kopiuj numer")
                b.clicked.connect(lambda _=False, nr=nr: (QGuiApplication.clipboard().setText(nr.replace(" ", "")),
                                                           self.statusBar().showMessage("Skopiowano numer konta.", 4000)))
                row.addWidget(b)
                lay.addLayout(row)
            if acc.get('tytul'):
                lay.addWidget(QLabel(f"<b>{modul_i18n.tr('Tytuł przelewu (propozycja):')}</b> {H.escape(acc['tytul'])}", wordWrap=True))
            if acc.get('inne'):
                lay.addWidget(QLabel(H.escape(acc['inne']), wordWrap=True))
            src = QLabel(f"<span style='color:gray'>Dane ze strony {H.escape(acc.get('zrodlo', ''))} – przed przelewem "
                         "sprawdź je na stronie odbiorcy.</span>", wordWrap=True)
            lay.addWidget(src)
        row = QHBoxLayout()
        if url:
            b = QPushButton("🌐 Otwórz stronę")
            b.setObjectName("big")
            b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
            row.addWidget(b)
        else:
            row.addWidget(QLabel("Strona jest w przygotowaniu – zajrzyj wkrótce."))
        row.addStretch(1)
        c = QPushButton("Zamknij")
        c.clicked.connect(d.accept)
        row.addWidget(c)
        lay.addLayout(row)
        d.setMinimumWidth(640 if acc and acc.get('baner') else 560)
        d.exec()

    def copyright_info(self):
        d = QDialog(self)
        d.setWindowTitle("Prawa autorskie do pieśni i dobre źródła")
        lay = QVBoxLayout(d)
        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setHtml(__import__('modul_i18n').tr(COPYRIGHT_HTML.strip()))
        lay.addWidget(tb)
        b = QPushButton("Zamknij")
        b.clicked.connect(d.accept)
        lay.addWidget(b, 0, Qt.AlignRight)
        d.resize(760, 720)
        d.exec()

    def _add_lang_button(self):
        """Przycisk języka na ekranie Start: 🌐 + kod języka, menu z dostępnymi językami."""
        from PySide6.QtWidgets import QToolButton, QMenu
        try:
            import modul_i18n
        except Exception:
            return
        cur = self.settings.value("language", "") or modul_i18n.LANG
        b = QToolButton()
        b.setText(f"🌐 {cur.upper()}")
        b.setToolTip("Język / Language / Langue / Idioma")
        b.setPopupMode(QToolButton.InstantPopup)
        b.setStyleSheet("QToolButton { font-size: 14pt; padding: 6px 12px; border: 1px solid #D9C49A; border-radius: 8px; }"
                        " QToolButton::menu-indicator { image: none; }")
        m = QMenu(b)
        for code, name in modul_i18n.available():
            a = m.addAction(("✓ " if code == cur else "    ") + name)
            a.triggered.connect(lambda _=False, c=code: self.set_language(c))
        b.setMenu(m)
        self.home.add_corner(b)
        self.lang_button = b

    def set_language(self, code):
        self.settings.setValue("language", code)
        self.settings.sync()
        if getattr(self, 'lang_button', None) is not None:
            self.lang_button.setText(f"🌐 {code.upper()}")
        import modul_i18n
        msg = {'pl': "Język zmieni się po ponownym uruchomieniu programu.",
               'en': "The language will change after restarting the program.",
               'fr': "La langue changera après le redémarrage du programme.",
               'es': "El idioma cambiará después de reiniciar el programa."}.get(code, "Restart the program to change the language.")
        QMessageBox.information(self, APP_NAME, msg)

    def tidy_dialog(self):
        """Kafel „Porządki w bazie”: duże przyciski do najczęstszych porządków."""
        d = QDialog(self)
        d.setWindowTitle("Porządki w bazie")
        lay = QVBoxLayout(d)
        lay.addWidget(QLabel(f"<b>W bazie: {self.db.count()} pieśni.</b> Każdą zmianę można cofnąć."))
        for txt, tip, fn in (
                ("🔗  Znajdź i połącz duplikaty pieśni", "Te same pieśni zapisane kilka razy – połącz w jedną "
                 "(teksty jako wersje, nuty, nagrania, zestawy)", self.find_duplicates),
                ("🏷  Menedżer kategorii", "Zmiana nazw, łączenie podobnych („Adwent” / „adwentowe”), nowe, usuwanie",
                 self.category_manager),
                ("📚  Menedżer źródeł (śpiewników)", "Zmiana nazw, łączenie podobnych („Siedlecki” / „Śpiewnik Siedleckiego”), "
                 "nowe, usuwanie; źródło dla wielu pieśni – zaznacz je na liście i „📚 Źródło…”", self.source_manager),
                ("↶  Cofnij ostatnie zmiany w bazie", "Import, łączenie, kategorie, usuwanie – powrót do stanu sprzed zmiany",
                 self.undo_db_dialog)):
            b = QPushButton(txt)
            b.setObjectName("big")
            b.setToolTip(tip)
            b.setMinimumHeight(44)
            b.clicked.connect(lambda _=False, fn=fn: (d.accept(), fn()))
            lay.addWidget(b)
            hint = QLabel(tip)
            hint.setWordWrap(True)
            hint.setStyleSheet("color: gray;")
            lay.addWidget(hint)
            lay.addSpacing(10)
        tip = QLabel("Kilka pieśni naraz: na liście w Tekstach, Slajdach albo Nutach zaznacz je <b>Shift+klik</b> "
                     "(zakres) lub <b>Ctrl+klik</b> – pod listą pojawią się „Połącz”, „Kategoria…” i „Tagi…”.")
        tip.setWordWrap(True)
        lay.addWidget(tip)
        bb = QPushButton("Zamknij")
        bb.clicked.connect(d.reject)
        lay.addWidget(bb)
        d.setMinimumWidth(560)
        d.adjustSize()
        d.exec()
        self._refresh_pickers()

    def source_manager(self):
        self.category_manager(SourceManagerDialog)

    def category_manager(self, cls=None):
        if self.dirty and not self.maybe_save():
            return
        dlg = (cls if isinstance(cls, type) else CategoryManagerDialog)(self.db, self)
        dlg.exec()
        if dlg.changed:
            sid = (self.song or {}).get('id')
            if sid and self.db.get(sid):
                self.dirty = False
                self.load_into_editor(self.db.get(sid))
            self.refresh_filters()
            self.refresh_list()
            self._refresh_pickers()
            self.pilot_invalidate()

    def _refresh_pickers(self):
        for page in (self.v_texts, self.v_slides, self.v_scores):
            page.picker.fill_categories()
            page.picker.refresh()

    def merge_ids(self, ids):
        """Kilka zaznaczonych pieśni to ta sama pieśń: wybierz główną, reszta do niej dołącza."""
        ids = [i for i in ids if self.db.get(i)]
        if len(ids) < 2:
            return
        if self.dirty and not self.maybe_save():
            return
        songs = [self.db.get(i) for i in ids]
        labels = []
        for s in songs:
            first = next((l.strip() for l in (s['refren'] + "\n" + s['zwrotki_raw']).splitlines() if l.strip()), "")
            n_att = len(self.db.attachments(s['id']))
            labels.append(f"{s['title']}   – {first[:40]}" + (f"   [nuty/pliki: {n_att}]" if n_att else ""))
        choice, ok = QInputDialog.getItem(
            self, "Połącz pieśni",
            f"Połączyć {len(ids)} pieśni w jedną? Wybierz pieśń GŁÓWNĄ (zostanie jej tytuł i tekst).\n"
            "Teksty pozostałych zostaną zapisane jako wersje, a nuty, nagrania, tagi, uwagi i zestawy przejdą do głównej.\n"
            "Można to cofnąć: Plik → Cofnij ostatnie zmiany.", labels, 0, False)
        if not ok:
            return
        dst = ids[labels.index(choice)]
        self.db.snapshot(f"Połączenie {len(ids)} pieśni w „{self.db.get(dst)['title']}”")
        for sid in ids:
            if sid != dst:
                self.db.merge_songs(sid, dst)
        if self.song and self.song.get('id') in ids:
            self.dirty = False
            self.load_into_editor(self.db.get(dst))
        self.cur_sid = dst
        self.refresh_filters()
        self.refresh_list()
        self.restore_set()
        self.pilot_invalidate()
        self._refresh_pickers()
        for page in (self.v_texts, self.v_slides, self.v_scores):
            if page.picker.select(dst):
                page.show_song(dst)
        self.statusBar().showMessage(f"Połączono {len(ids)} pieśni w „{self.db.get(dst)['title']}”. "
                                     "Można cofnąć: Plik → Cofnij ostatnie zmiany.", 8000)

    def bulk_category(self, ids=None):
        ids = ids if isinstance(ids, list) and ids else self._bulk_ids()
        if not ids:
            return
        if self.dirty and not self.maybe_save():
            return
        try:
            extra = json.loads(self.settings.value("extra_categories", "[]") or "[]")
        except ValueError:
            extra = []
        cats = sorted({c for c, _ in self.db.categories() if c} | set(DEFAULT_CATEGORIES) | set(extra))
        cat, ok = QInputDialog.getItem(self, APP_NAME, f"Kategoria dla {len(ids)} zaznaczonych pieśni\n"
                                       "(wybierz albo wpisz nową; „(bez kategorii)” usuwa kategorię):",
                                       ["(bez kategorii)"] + cats, 1 if cats else 0, True)
        if not ok:
            return
        cat = "" if cat.strip() in ("", "(bez kategorii)") else cat.strip()
        self.db.snapshot(f"Kategoria „{cat or 'brak'}” dla {len(ids)} pieśni")
        for sid in ids:
            s = self.db.get(sid)
            if s and (s.get('kategoria') or '') != cat:
                s['kategoria'] = cat
                self.db.save(s)
        self._after_bulk(f"Ustawiono kategorię „{cat or '(bez kategorii)'}” dla {len(ids)} pieśni.")

    def bulk_source(self, ids=None):
        ids = ids if isinstance(ids, list) and ids else self._bulk_ids()
        if not ids:
            return
        if self.dirty and not self.maybe_save():
            return
        srcs = sorted({x for x, _ in self.db.sources() if x} | {n for _, n in SPIEWNIKI_ADRESY})
        src, ok = QInputDialog.getItem(self, APP_NAME, f"Źródło (śpiewnik, zbiór) dla {len(ids)} zaznaczonych pieśni\n"
                                       "(wybierz albo wpisz; „(bez źródła)” usuwa):", ["(bez źródła)"] + srcs, 0, True)
        if not ok:
            return
        src = "" if src.strip() in ("", "(bez źródła)") else src.strip()
        self.db.snapshot(f"Źródło „{src or 'brak'}” dla {len(ids)} pieśni")
        for sid in ids:
            s_ = self.db.get(sid)
            if s_ and (s_.get('spiewnik') or '') != src:
                s_['spiewnik'] = src
                self.db.save(s_)
        self._after_bulk(f"Ustawiono źródło „{src or '(bez źródła)'}” dla {len(ids)} pieśni.")

    def bulk_tags(self, ids=None):
        ids = ids if isinstance(ids, list) and ids else self._bulk_ids()
        if not ids:
            return
        if self.dirty and not self.maybe_save():
            return
        txt, ok = QInputDialog.getText(self, APP_NAME, f"Tagi dla {len(ids)} zaznaczonych pieśni, po przecinku.\n"
                                       "Minus przed tagiem usuwa go, np.: komunia, adwent, -kolęda")
        if not ok or not txt.strip():
            return
        add = [t.strip() for t in txt.split(",") if t.strip() and not t.strip().startswith("-")]
        rem = {fold(t.strip()[1:].strip()) for t in txt.split(",") if t.strip().startswith("-")}
        self.db.snapshot(f"Tagi dla {len(ids)} pieśni: {txt.strip()}")
        for sid in ids:
            s = self.db.get(sid)
            if not s:
                continue
            cur = [t.strip() for t in (s.get('tagi') or '').split(",") if t.strip() and fold(t.strip()) not in rem]
            s['tagi'] = norm_tags(", ".join(cur + add))
            self.db.save(s)
        self._after_bulk(f"Zmieniono tagi {len(ids)} pieśni.")

    def _after_bulk(self, msg):
        sel = set(self.selected_result_ids())
        sid = (self.song or {}).get('id')
        if sid and sid in sel and self.db.get(sid):
            self.dirty = False
            self.load_into_editor(self.db.get(sid))
        self.refresh_filters()
        self.refresh_list()
        from PySide6.QtWidgets import QTreeWidgetItemIterator
        it = QTreeWidgetItemIterator(self.results)
        while it.value():                                  # zaznaczenie zostaje – można od razu dodać tagi
            if it.value().data(0, Qt.UserRole) in sel:
                it.value().setSelected(True)
            it += 1
        self.pilot_invalidate()
        self.statusBar().showMessage(msg + " Można cofnąć: Plik → Cofnij ostatnie zmiany.", 8000)

    def store_text_as_version(self):
        if not self.ensure_saved("Aby zapisać wersję"):
            return
        name, ok = QInputDialog.getText(self, APP_NAME, "Nazwa wersji (np. „Śpiewnik siedlecki”, „tekst dawny”):",
                                        text="Wersja " + datetime.date.today().isoformat())
        if not ok:
            return
        s = self.editor_song()
        vid = self.db.add_version(s['id'], name.strip() or "Wersja", s['refren'], s['zwrotki_raw'], "", s.get('zrodlo', ''))
        self.refresh_media()
        self.statusBar().showMessage("Zapisano wersję tekstu." if vid else "Taka wersja już jest.", 5000)

    def undo_db_dialog(self):
        snaps = self.db.snapshots()
        if not snaps:
            QMessageBox.information(self, APP_NAME, "Nie ma zapisanych zmian do cofnięcia.\n"
                                    "Kopia bazy powstaje przed każdym importem, łączeniem i usunięciem pieśni.")
            return
        d = QDialog(self)
        d.setWindowTitle("Cofnij ostatnie zmiany w bazie")
        d.resize(620, 360)
        lay = QVBoxLayout(d)
        lay.addWidget(QLabel("Wybierz zmianę – baza wróci do stanu <b>sprzed</b> niej (cofnięte zostaną też "
                             "wszystkie późniejsze zmiany).<br>Bieżący stan zostanie zachowany jako kopia, "
                             "więc cofnięcie też da się cofnąć."))
        lw = QListWidget()
        for sn in snaps:
            it = QListWidgetItem(f"{sn['kiedy']:%d.%m %H:%M:%S}   {sn['opis']}")
            it.setData(Qt.UserRole, sn['path'])
            lw.addItem(it)
        lw.setCurrentRow(0)
        lay.addWidget(lw, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Cofnij do stanu sprzed tej zmiany")
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        lw.itemDoubleClicked.connect(lambda *_: d.accept())
        lay.addWidget(bb)
        if not d.exec() or not lw.currentItem():
            return
        if self.dirty and not self.maybe_save():
            return
        try:
            self.db.restore(lw.currentItem().data(Qt.UserRole))
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Nie udało się przywrócić bazy:\n{e}")
            return
        sid = (self.song or {}).get('id')
        self.dirty = False
        cur = self.db.get(sid) if sid else None
        if cur:
            self.load_into_editor(cur)
        else:
            self.new_song(ask=False)
        self.refresh_filters()
        self.refresh_list()
        self.refresh_media()
        self.restore_set()
        self.refresh_set_combo()
        self.pilot_invalidate()
        self.statusBar().showMessage("Przywrócono bazę sprzed wybranej zmiany.", 8000)

    def ensure_saved(self, why):
        if self.song and self.song.get('id') and not self.dirty:
            return True
        if self.song and self.song.get('id'):
            return self.save_song()
        if QMessageBox.question(self, APP_NAME, f"{why} – najpierw trzeba zapisać pieśń w bazie. Zapisać teraz?") == QMessageBox.Yes:
            return self.save_song()
        return False

    def duplicate_song(self):
        s = self.editor_song()
        s.pop('id', None)
        s['title'] += " (kopia)"
        self.new_song(song=s)

    def delete_song(self):
        if not self.song or not self.song.get('id'):
            return
        if QMessageBox.question(self, APP_NAME, f"Usunąć z bazy pieśń „{self.song['title']}” razem z jej załącznikami?\n"
                                "Można to cofnąć: Plik → Cofnij ostatnie zmiany w bazie.") != QMessageBox.Yes:
            return
        self.db.snapshot(f"Usunięcie pieśni „{self.song['title']}”")
        self.db.delete(self.song['id'])
        self.pilot_invalidate()
        self.dirty = False
        self.refresh_filters()
        self.refresh_list()
        self.restore_set()
        self.new_song(ask=False)

    # ================= tła =================
    def fill_bg_combo(self):
        self.bg_combo.blockSignals(True)
        self.bg_combo.clear()
        self.bg_combo.addItem("(brak – jednolity kolor)", "")
        for name in list_backgrounds():
            path = resolve_background(name, 1920, 1080)
            icon = QIcon(QPixmap(path).scaled(64, 36, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)) if path else QIcon()
            label = name.replace('jasny_', 'jasne: ').replace('_', ' ').replace('choral', 'chorał').replace('gradual', 'graduał')
            label = label.replace('boze', 'Boże').replace('swiety', 'Święty').replace('witraz', 'witraż')
            self.bg_combo.addItem(icon, label, name)
        self.bg_combo.addItem("Inny plik…", "__inny__")
        self.bg_combo.blockSignals(False)

    def select_bg(self, name):
        self.bg_combo.blockSignals(True)
        i = self.bg_combo.findData(name)
        if i < 0 and name:
            self.bg_combo.insertItem(self.bg_combo.count() - 1, os.path.basename(name), name)
            i = self.bg_combo.findData(name)
        self.bg_combo.setCurrentIndex(max(0, i))
        self.bg_combo.blockSignals(False)

    def on_bg_combo(self, idx):
        if self.bg_combo.currentData() == "__inny__":
            path, _ = QFileDialog.getOpenFileName(self, "Obraz tła", os.path.expanduser("~"), "Obrazy (*.jpg *.jpeg *.png)")
            self.select_bg(path if path else (self.song or {}).get('config', {}).get('tlo', ''))
        self.apply_bg_preset(self.bg_combo.currentData() or '')
        self.on_edit()

    def apply_bg_preset(self, name):
        """Zalecane kolory i marginesy dla wybranego tła (z tla/tla.json)."""
        pr = background_presets().get(name)
        if name == '':
            pr = {'kolor_tekstu': '#ffffff', 'kolor_refrenu': '#ffff99', 'margines_x': 7, 'margines_y': 5}
        if not pr:
            return
        was = self.loading
        self.loading = True
        for k in ('kolor_tekstu', 'kolor_refrenu'):
            if k in pr:
                self.w[k].set_color(pr[k])
        for k in ('margines_x', 'margines_y'):
            if k in pr:
                self.w[k].setValue(int(pr[k]))
        if 'jasne' in pr:
            self.w['przyciemnienie'].setValue(15 if pr['jasne'] else 25)
        self.loading = was

    # ================= slajdy =================
    def rebuild_deck(self):
        song = self.editor_song()
        deck, pt = build_song_deck(song)
        self.deck = deck
        row = max(0, self.thumbs.currentRow())
        self.thumbs.blockSignals(True)
        self.thumbs.clear()
        for i, s in enumerate(deck):
            self.thumbs.addItem(QListWidgetItem(QIcon(slide_pixmap(s, 200)), str(i + 1)))
        self.thumbs.blockSignals(False)
        self.thumbs.setCurrentRow(min(row, len(deck) - 1))
        self.view.set_slide(deck[self.thumbs.currentRow()] if deck else None)
        cfg = song_cfg(song)
        self.info.setText(f"{len(deck)} slajdów • czcionka {pt} pt" + (" (auto)" if cfg['auto_size'] else ""))
        if self.present and not self.present_set:
            self.present.set_deck(deck)

    def on_thumb(self, row):
        if 0 <= row < len(self.deck):
            self.view.set_slide(self.deck[row])
            if self.present and not self.present_set:
                self.present.show_index(row, emit=False)

    # ================= pokaz =================
    def fill_screen_menu(self):
        self.screen_menu.clear()
        cur = self.settings.value("screen", "")
        for sc in QGuiApplication.screens():
            g = sc.geometry()
            a = self.screen_menu.addAction(f"{sc.name()}  {g.width()}×{g.height()}")
            a.setCheckable(True)
            a.setChecked(sc.name() == cur)
            a.triggered.connect(lambda _=False, n=sc.name(): self.settings.setValue("screen", n))
        a = self.screen_menu.addAction("Automatycznie (drugi ekran, jeśli jest)")
        a.setCheckable(True)
        a.setChecked(not cur)
        a.triggered.connect(lambda: self.settings.setValue("screen", ""))

    def pick_screen(self):
        screens = QGuiApplication.screens()
        name = self.settings.value("screen", "")
        for sc in screens:
            if sc.name() == name:
                return sc
        mine = self.screen()
        others = [s for s in screens if s is not mine]
        return others[0] if others else mine

    def _open_present(self, deck, start, is_set):
        if not deck:
            QMessageBox.information(self, APP_NAME, "Brak slajdów do pokazania.")
            return
        if self.present:
            self.present.close()
        self.present_set = is_set
        self.present = PresentWindow(deck, start, self.pick_screen())
        self.present.changed.connect(self.on_present_changed)
        self.present.closed.connect(self.on_present_closed)
        self.present.showFullScreen()
        self.present.activateWindow()
        self.present.setFocus()

    def start_present(self, start=0):
        self._open_present(self.deck, max(0, start), False)

    def toggle_clean(self):
        if self.present:
            self.present.set_clean(not self.present.clean)

    def present_clean_background(self):
        """Rzutnik: samo tło bieżącej pieśni, bez tekstu (np. podczas nagrania)."""
        if not self.present:
            deck = self.deck or [blank_slide(self.editor_song()['config'])]
            self._open_present(deck, max(0, self.thumbs.currentRow()), False)
        if self.present:
            self.present.set_clean(True)

    def on_present_changed(self, i):
        if not self.present_set:
            self.thumbs.blockSignals(True)
            self.thumbs.setCurrentRow(i)
            self.thumbs.blockSignals(False)
            if 0 <= i < len(self.deck):
                self.view.set_slide(self.deck[i])
        else:
            s = self.present.deck[i]
            self.statusBar().showMessage(f"Pokaz zestawu: slajd {i + 1}/{len(self.present.deck)} – {s.title}")

    def on_present_closed(self):
        self.present = None
        self.present_set = False

    # ================= zestaw =================
    def add_to_set(self):
        ids = self.selected_result_ids()
        if not ids and self.song and self.song.get('id'):
            ids = [self.song['id']]
        chosen = self.setlist.current_part()
        last = None
        for sid in ids:
            song = self.db.get(sid)
            if song:
                part = FREE_PART if self.set_kind() != 'msza' else (chosen or guess_mass_part(song) or "Przed mszą")
                last = self.setlist.add_song(part, sid, song['title'])
        if last is not None:
            self.setlist.scrollToItem(last)
        self.save_set()

    def remove_from_set(self):
        self.setlist.remove_selected()
        self.save_set()

    def clear_set(self):
        self.setlist.reset_parts()
        self.mass_combo.setCurrentIndex(0)
        self.save_set()

    def set_entries(self):
        """[(część, id pieśni)] w kolejności Mszy."""
        return self.setlist.entries()

    def set_ids(self):
        return [sid for _, sid in self.set_entries()]

    def _set_parts(self):
        data = {}
        for part, sid in self.set_entries():
            data.setdefault(part, []).append(sid)
        return data

    def set_kind(self):
        return self.m_kind.currentData() or 'msza'

    def _kind_changed(self, *_):
        kind = self.set_kind()
        self.setlist.set_kind(kind)
        for w_ in self.mass_only:
            w_.setVisible(kind == 'msza')
        self.m_name.setVisible(kind != 'msza')
        self.save_set()

    def mass_meta(self):
        """Dane Mszy z formularza nad zestawem."""
        return {'rodzaj': self.set_kind(), 'nazwa': self.m_name.text().strip(),'data': self.m_date.date().toString("yyyy-MM-dd"), 'godzina': self.m_time.time().toString("HH:mm"),
                'miejsce': self.m_place.text().strip(), 'okres': self.m_okres.currentText().strip(),
                'dzien': getattr(self, '_mass_day', '') or '', 'motyw': self.mass_combo.currentData() or ''}

    def mass_title(self, with_day=True):
        m = self.mass_meta()
        d = datetime.date.fromisoformat(m['data'])
        dni = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
        head = "Msza święta" if m['rodzaj'] == 'msza' else (m['nazwa'] or "Zestaw utworów")
        t = f"{head} – {dni[d.weekday()]} {d.day}.{d.month:02d}.{d.year}, godz. {m['godzina']}"
        if m['miejsce']:
            t += f", {m['miejsce']}"
        return t

    def save_set(self, *_):
        if getattr(self, '_loading_set', False):
            return
        self.settings.setValue("setlist_msza", json.dumps(self._set_parts(), ensure_ascii=False))
        self.settings.setValue("setlist_uwagi", json.dumps(self.setlist.all_notes(), ensure_ascii=False))
        self.settings.setValue("setlist", json.dumps(self.set_ids()))
        self.settings.setValue("setlist_msza_motyw", self.mass_combo.currentData() or "")
        self.settings.setValue("setlist_meta", json.dumps(dict(self.mass_meta(), zid=getattr(self, 'current_set_id', None)),
                                                          ensure_ascii=False))

    def _apply_meta(self, meta):
        from PySide6.QtCore import QDate, QTime
        self._loading_set = True
        try:
            self.m_kind.setCurrentIndex(max(0, self.m_kind.findData(meta.get('rodzaj', 'msza'))))
            self.m_name.setText(meta.get('nazwa', ''))
            kind = self.set_kind()
            for w_ in self.mass_only:
                w_.setVisible(kind == 'msza')
            self.m_name.setVisible(kind != 'msza')
            if meta.get('data'):
                self.m_date.setDate(QDate.fromString(meta['data'], "yyyy-MM-dd"))
            if meta.get('godzina'):
                self.m_time.setTime(QTime.fromString(meta['godzina'], "HH:mm"))
            self.m_place.setText(meta.get('miejsce', ''))
            self._update_day_info(set_okres=not meta.get('okres'))
            if meta.get('okres'):
                self.m_okres.setCurrentText(meta['okres'])
        finally:
            self._loading_set = False

    def _mass_date_changed(self, *_):
        self._update_day_info(set_okres=True)
        self.save_set()

    def _update_day_info(self, set_okres=False):
        import modul_liturgia as ml
        d = self.m_date.date().toPython()
        info = ml.okres_liturgiczny(d)
        if set_okres:
            self.m_okres.blockSignals(True)
            self.m_okres.setCurrentText(info['okres'])
            self.m_okres.blockSignals(False)
        lit = self.db.get_liturgy(d.isoformat())
        self._mass_day = (lit or {}).get('meta', {}).get('dzien', '')
        txt = f"Rok {info['rok_niedzielny']}, {info['rok_powszedni']}"
        if self._mass_day:
            txt = f"{self._mass_day} • " + txt
        if lit:
            txt += " • liturgia pobrana"
        self.m_day.setText(txt)

    # ---- zapisane zestawy
    def refresh_set_combo(self):
        self.set_combo.blockSignals(True)
        self.set_combo.clear()
        self.set_combo.addItem("(niezapisany – 💾 zapisuje w bazie)", None)
        for z in self.db.sets():
            self.set_combo.addItem(z['nazwa'] or z['data'], z['id'])
        i = self.set_combo.findData(getattr(self, 'current_set_id', None))
        self.set_combo.setCurrentIndex(max(0, i))
        self.set_combo.blockSignals(False)

    def store_set(self):
        meta = self.mass_meta()
        name = self.mass_title().replace("Msza święta – ", "")
        if meta['rodzaj'] != 'msza':
            name = "♪ " + name
        zid = getattr(self, 'current_set_id', None)
        self.current_set_id = self.db.save_set(zid, name, meta['data'], {'meta': meta, 'czesci': self._set_parts(),
                                                                         'uwagi': self.setlist.all_notes()})
        self.refresh_set_combo()
        self.save_set()
        self.statusBar().showMessage(f"Zapisano zestaw: {name}", 5000)

    def new_set(self):
        if self.set_entries() and QMessageBox.question(self, APP_NAME, "Zacząć nowy, pusty zestaw?\n"
                                                       "(Bieżący zostaje w bazie, jeśli był zapisany 💾.)") != QMessageBox.Yes:
            return
        self.current_set_id = None
        self.setlist.reset_parts()
        self.mass_combo.setCurrentIndex(0)
        self.refresh_set_combo()
        self.save_set()

    def load_saved_set(self, *_):
        zid = self.set_combo.currentData()
        if not zid:
            return
        z = self.db.get_set(zid)
        if not z:
            return
        self.current_set_id = zid
        self._fill_set(z['dane'].get('czesci', {}), z['dane'].get('meta', {}).get('rodzaj', 'msza'),
                       z['dane'].get('uwagi') or {})
        self._apply_meta(z['dane'].get('meta', {}))
        motyw = z['dane'].get('meta', {}).get('motyw', '')
        self.settings.setValue("setlist_msza_motyw", motyw)
        self.refresh_mass_combo()
        self.save_set()

    def delete_saved_set(self):
        zid = self.set_combo.currentData()
        if not zid or QMessageBox.question(self, APP_NAME, f"Usunąć z bazy zapisany zestaw „{self.set_combo.currentText()}”?") \
                != QMessageBox.Yes:
            return
        self.db.delete_set(zid)
        self.current_set_id = None
        self.refresh_set_combo()
        self.save_set()

    def _fill_set(self, data, kind=None, notes=None):
        if kind:
            self.setlist.kind = None                  # wymuś przebudowę
            self.setlist.set_kind(kind)
        self.setlist.reset_parts()
        notes = notes or {}
        names = [n for n, _ in self.setlist.part_list()]
        for part in names + [p for p in data if p not in names]:
            nl = notes.get(part) or []
            for j, sid in enumerate(data.get(part, [])):
                song = self.db.get(sid)
                if song:
                    self.setlist.add_song(part, sid, song['title'], nl[j] if j < len(nl) else None)

    def restore_set(self):
        self.setlist.reset_parts()
        try:
            data = json.loads(self.settings.value("setlist_msza", "") or "null")
        except Exception:
            data = None
        if not isinstance(data, dict):                        # zestaw z wersji < 8.6: zwykła lista
            try:
                ids = json.loads(self.settings.value("setlist", "[]"))
            except Exception:
                ids = []
            data = {}
            for sid in ids:
                song = self.db.get(sid)
                if song:
                    data.setdefault(guess_mass_part(song) or "Przed mszą", []).append(sid)
        try:
            meta = json.loads(self.settings.value("setlist_meta", "") or "{}")
        except Exception:
            meta = {}
        try:
            notes = json.loads(self.settings.value("setlist_uwagi", "") or "{}")
        except Exception:
            notes = {}
        self._fill_set(data, meta.get('rodzaj', 'msza'), notes if isinstance(notes, dict) else {})
        self.refresh_mass_combo()
        self.current_set_id = meta.get('zid')
        if self.current_set_id and not self.db.get_set(self.current_set_id):
            self.current_set_id = None
        self._apply_meta(meta)
        self.refresh_set_combo()

    def ordinary_cycles(self):
        """{nazwa mszy: {część: (id, tytuł)}} – z tagów pieśni rozpoznanych jako części stałe."""
        cycles = {}
        for r in self.db.search(""):
            song = {'title': r['title'], 'tagi': r['tagi'] or '', 'kategoria': r['kategoria'] or ''}
            part = guess_mass_part(song)
            if part not in ORDINARY:
                continue
            for t in (x.strip() for x in song['tagi'].split(',')):
                if t and fold(t) not in PART_TAGS | {fold(x) for x in DEFAULT_TAGS} | {'czesci stale', 'czesci stale mszy'}:
                    name = t[:1].upper() + t[1:]
                    head = r['title'][:len(t)]
                    if fold(head) == fold(t):               # pisownia z tytułu: „Msza Rycerska – Kyrie”
                        name = head
                    key = next((k for k in cycles if fold(k) == fold(name)), None)
                    if key is None:
                        key = name
                    elif key != name and name != name[:1] + name[1:].lower():
                        cycles[name] = cycles.pop(key)       # wolę pisownię z wielkimi literami z tytułu
                        key = name
                    cycles.setdefault(key, {}).setdefault(part, (r['id'], r['title']))
        return cycles

    def refresh_mass_combo(self):
        keep = self.settings.value("setlist_msza_motyw", "") or ""
        self.mass_combo.blockSignals(True)
        self.mass_combo.clear()
        cycles = self.ordinary_cycles()
        self.mass_combo.addItem("(wybierz mszę – uzupełni Kyrie, Gloria, Sanctus, Agnus Dei)" if cycles
                                else "(brak – oznacz części stałe tagiem z nazwą mszy)", "")
        for name in sorted(cycles, key=fold):
            have = ", ".join(p for p in ORDINARY if p in cycles[name])
            self.mass_combo.addItem(f"{name}  ({have})", name)
        i = next((j for j in range(self.mass_combo.count())
                  if (self.mass_combo.itemData(j) or "").lower() == keep.lower()), 0)
        self.mass_combo.setCurrentIndex(max(0, i))
        self.mass_combo.blockSignals(False)

    def fill_ordinary(self, *_):
        if self.set_kind() != 'msza':
            return
        name = self.mass_combo.currentData()
        if not name:
            return
        cyc = next((v for k, v in self.ordinary_cycles().items() if k.lower() == name.lower()), {})
        for part in ORDINARY:
            if part in cyc:
                sid, title = cyc[part]
                self.setlist.add_song(part, sid, title)
        missing = [p for p in ORDINARY if p not in cyc]
        self.statusBar().showMessage(f"Części stałe: {name}" +
                                     (f" – brak w bazie: {', '.join(missing)}" if missing else ""), 8000)
        self.save_set()

    # ---- liturgia dnia
    def _go_liturgy(self):
        """Kafel „Liturgia z dnia”: dzisiejsza liturgia i propozycje pieśni (dodawanie do bieżącego zestawu)."""
        import datetime as _dt
        import modul_liturgia as ml
        d = _dt.date.today()
        try:
            okres = ml.okres_liturgiczny(d).get('okres')
        except Exception:
            okres = self.m_okres.currentText()

        def songs():
            return [self.db.get(r['id']) for r in self.db.search("")]

        def add(part, sid):
            song = self.db.get(sid)
            if not song:
                return
            if self.set_kind() != 'msza':
                QMessageBox.information(self, APP_NAME, "Bieżący zestaw nie jest Mszą – pieśń można dodać w „Zestawie na Mszę”.")
                return
            self.setlist.add_song(part, sid, song['title'])
            self.save_set()
            self.statusBar().showMessage(f"Dodano do zestawu ({part}): {song['title']}", 5000)

        def open_song(sid):
            if sid and self._ensure_open(sid):
                self.views.setCurrentIndex(self.V_ADV)

        dlg = ml.LiturgyDialog(d, self.db, songs, okres or self.m_okres.currentText(), [p for p, _ in MASS_PARTS],
                               add, open_song, self)
        dlg.show()

    def open_liturgy(self):
        import modul_liturgia as ml
        if self.set_kind() != 'msza':
            return
        d = self.m_date.date().toPython()

        def songs():
            return [self.db.get(r['id']) for r in self.db.search("")]

        def add(part, sid):
            song = self.db.get(sid)
            if song:
                self.setlist.add_song(part, sid, song['title'])
                self.save_set()
                self.statusBar().showMessage(f"Dodano do zestawu ({part}): {song['title']}", 5000)

        dlg = ml.LiturgyDialog(d, self.db, songs, self.m_okres.currentText(), [p for p, _ in MASS_PARTS],
                               add, lambda sid: sid and self.open_song(sid), self)
        dlg.finished.connect(lambda *_: (self._update_day_info(), self.save_set()))
        dlg.show()

    def export_song_blind(self):
        self.export_song_package(blind=True)

    def export_song_package(self, blind=False):
        song = self.editor_song()
        if not (song.get('refren') or song.get('zwrotki_raw')):
            QMessageBox.information(self, APP_NAME, "Pieśń nie ma tekstu.")
            return
        self.export_package(single=song, blind=blind)

    def export_blind(self):
        self.export_package(blind=True)

    def song_midi(self, song):
        """MIDI pieśni: dołączony plik MIDI albo przeliczony z nut MuseScore/MusicXML."""
        sid = song.get('id')
        if not sid:
            return None
        atts = self.db.attachments(sid)
        for a in atts:
            if a['name'].lower().endswith(('.mid', '.midi', '.kar')):
                return self.db.attachment(a['id'])['data']
        for a in atts:
            if a['name'].lower().endswith(SCORE_EXT):
                full = self.db.attachment(a['id'])
                try:
                    mid = self._derived_now(full['id'], full['name'], full['data'])[1]
                except Exception:
                    mid = None
                if mid:
                    return mid
        return None

    def song_scores_pdf(self, song):
        """PDF-y nut pieśni: dołączone PDF albo przeliczone z MuseScore/MusicXML → [(nazwa, bajty)]."""
        out = []
        if not song.get('id'):
            return out
        for a in self.db.attachments(song['id']):
            low = a['name'].lower()
            if low.endswith('.pdf'):
                out.append((a['name'], self.db.attachment(a['id'])['data']))
            elif low.endswith(SCORE_EXT):
                full = self.db.attachment(a['id'])
                try:
                    pdf = self._derived_now(full['id'], full['name'], full['data'])[0]
                except Exception:
                    pdf = None
                if pdf:
                    out.append((os.path.splitext(a['name'])[0] + ".pdf", pdf))
        return out

    def export_package(self, single=None, blind=False):
        """Eksport materiałów zestawu albo pieśni do jednego folderu: teksty (DOCX/TXT/HTML), slajdy (PDF/PPTX),
        nuty (PDF), nagrania do nauki (MP3: całość i wybrane głosy). „Dla niewidomych” to wariant tekstów."""
        import modul_audio
        if single:
            entries, lit = [(None, single)], None
        else:
            entries = [(s['_czesc'], s) for s in self.set_songs()]
            lit = self.db.get_liturgy(self.mass_meta()['data']) if self.set_kind() == 'msza' else None
        if not entries and not lit:
            QMessageBox.information(self, APP_NAME, "Zestaw jest pusty.")
            return
        st = self.settings
        pre = "blindpkg" if blind else "pkg"
        val = lambda k, d: st.value(f"{pre}_{k}", d, type=type(d))
        dlg = QDialog(self)
        dlg.setWindowTitle(("Eksport dla niewidomych – " if blind else "Eksport materiałów – ") +
                           (f"„{single.get('title', '')}”" if single else "zestaw"))
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Wszystkie wybrane pliki trafią do jednego nowego folderu."))
        acc = QCheckBox("♿ Wersja dla niewidomych i słabowidzących (teksty z nagłówkami, bez obrazków, większa czcionka)")
        acc.setChecked(blind or val("acc", False))
        lay.addWidget(acc)

        gt = QGroupBox("Teksty")
        ft = QFormLayout(gt)
        row = QHBoxLayout()
        fmts = {}
        for key, label, d in (('docx', "DOCX", True), ('txt', "TXT", blind), ('html', "HTML", False)):
            cb = QCheckBox(label)
            cb.setChecked(val(f"t_{key}", d))
            fmts[key] = cb
            row.addWidget(cb)
        row.addStretch(1)
        ft.addRow("Formaty:", row)
        mode = QComboBox()
        mode.addItem("Pełne teksty liturgii", 'full')
        mode.addItem("Skrócone (początki czytań)", 'short')
        mode.addItem("Tylko pieśni", 'none')
        mode.setCurrentIndex(0 if lit else 2)
        if not single and self.set_kind() == 'msza':
            ft.addRow("Liturgia dnia:", mode)
        size = QSpinBox()
        size.setRange(10, 36)
        size.setSuffix(" pt")
        size.setValue(val("pt", 18 if blind else 13))
        ft.addRow("Czcionka:", size)
        lay.addWidget(gt)

        gs = QGroupBox("Slajdy i nuty")
        fs = QFormLayout(gs)
        row2 = QHBoxLayout()
        sl_pdf = QCheckBox("slajdy PDF")
        sl_pdf.setChecked(val("s_pdf", not blind))
        sl_pptx = QCheckBox("slajdy PPTX")
        sl_pptx.setChecked(val("s_pptx", False))
        row2.addWidget(sl_pdf)
        row2.addWidget(sl_pptx)
        row2.addStretch(1)
        fs.addRow("Slajdy:", row2)
        row3 = QHBoxLayout()
        sc = QCheckBox("nuty PDF (dołączone i z MuseScore)")
        sc.setChecked(val("n_pdf", not blind))
        sc_one = QCheckBox("także w jednym pliku")
        sc_one.setChecked(val("n_one", True))
        rec = QCheckBox("dołączone nagrania (mp3…)")
        rec.setChecked(val("n_rec", False))
        for w_ in (sc, sc_one, rec):
            row3.addWidget(w_)
        row3.addStretch(1)
        fs.addRow("Nuty:", row3)
        lay.addWidget(gs)

        ga = QGroupBox("Nagrania do nauki z nut (MIDI / MuseScore)")
        ga.setCheckable(True)
        ga.setChecked(val("audio", blind))
        al = QFormLayout(ga)
        rv = QHBoxLayout()
        vcb = {}
        for role, label in (('S', "Sopran"), ('A', "Alt"), ('T', "Tenor"), ('B', "Bas"), ('X', "inne")):
            cb = QCheckBox(label)
            cb.setChecked(role in val("a_voices", "SATB"))
            vcb[role] = cb
            rv.addWidget(cb)
        rv.addStretch(1)
        al.addRow("Głosy:", rv)
        rw = QHBoxLayout()
        var = {}
        for key, label, d in (('full', "całość", True), ('bg', "głos z podkładem", True), ('solo', "sam głos", False)):
            cb = QCheckBox(label)
            cb.setChecked(key in val("a_var", "full,bg").split(','))
            var[key] = cb
            rw.addWidget(cb)
        rw.addStretch(1)
        al.addRow("Warianty:", rw)
        rt = QHBoxLayout()
        t_norm = QCheckBox("tempo z nut")
        t_norm.setChecked(val("a_tn", True))
        t_slow = QCheckBox("wolniej:")
        t_slow.setChecked(val("a_ts", False))
        slow = QSpinBox()
        slow.setRange(50, 95)
        slow.setSuffix(" %")
        slow.setValue(val("a_slow", 75))
        for w_ in (t_norm, t_slow, slow):
            rt.addWidget(w_)
        rt.addStretch(1)
        al.addRow("Tempo:", rt)
        bg = QSpinBox()
        bg.setRange(5, 80)
        bg.setSuffix(" %")
        bg.setValue(val("a_bg", 22))
        al.addRow("Głośność podkładu:", bg)
        vin = QComboBox()
        for key, label in (('sf:0:52', "Chór „aa”"), ('sf:0:53', "Chór „uu”"), ('sf:0:0', "Fortepian"),
                           ('sf:0:19', "Organy"), ('sf:0:73', "Flet")):
            vin.addItem(label, key)
        vin.setCurrentIndex(max(0, vin.findData(val("a_vin", 'sf:0:52'))))
        al.addRow("Brzmienie głosów:", vin)
        bin_ = QComboBox()
        for key, label in (('sf:0:19', "Organy kościelne"), ('sf:0:20', "Fisharmonia"), ('sf:0:48', "Smyczki"),
                           ('', "To samo co głosy")):
            bin_.addItem(label, key)
        bin_.setCurrentIndex(max(0, bin_.findData(val("a_bin", 'sf:0:19'))))
        al.addRow("Brzmienie podkładu:", bin_)
        afmt = QComboBox()
        for f in modul_audio.audio_formats():
            afmt.addItem(f.upper(), f)
        al.addRow("Format:", afmt)
        with_notes = [e for e in entries if e[1].get('id') and any(
            a['name'].lower().endswith(('.mid', '.midi', '.kar') + SCORE_EXT) for a in self.db.attachments(e[1]['id']))]
        est = QLabel()
        est.setWordWrap(True)
        al.addRow(est)
        lay.addWidget(ga)

        def update_estimate(*_):
            nv = sum(1 for cb in vcb.values() if cb.isChecked())
            vs = {k for k, cb in var.items() if cb.isChecked()}
            tempos = ([1.0] if t_norm.isChecked() else []) + ([slow.value() / 100] if t_slow.isChecked() else [])
            per = modul_audio.count_files(nv, vs, tempos)
            n = per * len(with_notes)
            warn = "  ⚠ dużo plików – ogranicz głosy lub warianty" if n > 40 else ""
            est.setText(f"Nuty ma {len(with_notes)} z {len(entries)} utworów → powstanie ok. {n} plików "
                        f"({per} na utwór).{warn}" + ("" if modul_audio.soundfont() else
                                                      "  ⚠ Brak SoundFontu – zabrzmi prosty ton."))
            est.setStyleSheet("color: #b05000;" if warn else "color: gray;")
        for w_ in list(vcb.values()) + list(var.values()) + [t_norm, t_slow]:
            w_.toggled.connect(update_estimate)
        slow.valueChanged.connect(update_estimate)
        update_estimate()
        if not with_notes:
            ga.setChecked(False)
            ga.setEnabled(False)

        def acc_changed(on):
            if on:
                fmts['docx'].setChecked(True)
                fmts['txt'].setChecked(True)
                size.setValue(max(size.value(), 18))
        acc.toggled.connect(acc_changed)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Wybierz folder i zapisz…")
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if not dlg.exec():
            return
        # zapamiętaj wybór
        for k, cb in fmts.items():
            st.setValue(f"{pre}_t_{k}", cb.isChecked())
        for k, v in (("acc", acc.isChecked()), ("pt", size.value()), ("s_pdf", sl_pdf.isChecked()),
                     ("s_pptx", sl_pptx.isChecked()), ("n_pdf", sc.isChecked()), ("n_one", sc_one.isChecked()),
                     ("n_rec", rec.isChecked()), ("audio", ga.isChecked()),
                     ("a_voices", "".join(r for r, cb in vcb.items() if cb.isChecked())),
                     ("a_var", ",".join(k for k, cb in var.items() if cb.isChecked())), ("a_tn", t_norm.isChecked()),
                     ("a_ts", t_slow.isChecked()), ("a_slow", slow.value()), ("a_bg", bg.value()),
                     ("a_vin", vin.currentData()), ("a_bin", bin_.currentData())):
            st.setValue(f"{pre}_{k}", v)
        chosen = [k for k, cb in fmts.items() if cb.isChecked()]
        tempos = ([1.0] if t_norm.isChecked() else []) + ([slow.value() / 100] if t_slow.isChecked() else [])
        audio = ga.isChecked() and ga.isEnabled() and tempos and (
            var['full'].isChecked() or (any(cb.isChecked() for cb in vcb.values()) and
                                        (var['bg'].isChecked() or var['solo'].isChecked())))
        if not (chosen or audio or sl_pdf.isChecked() or sl_pptx.isChecked() or sc.isChecked() or rec.isChecked()):
            QMessageBox.information(self, APP_NAME, "Nie wybrano niczego do zapisania.")
            return
        m = self.mass_meta()
        if single:
            base = single.get('title') or 'Pieśń'
        elif m['rodzaj'] != 'msza':
            base = f"{m['nazwa'] or 'Zestaw'} {m['data']}"
        else:
            base = f"Msza {m['data']} {m['godzina'].replace(':', '.')}"
        if acc.isChecked():
            base += " – dla niewidomych"
        base = modul_audio._safe(base.replace(':', '.'))
        parent = QFileDialog.getExistingDirectory(self, "Folder, w którym powstanie folder z materiałami",
                                                  st.value("export_dir", os.path.expanduser("~")))
        if not parent:
            return
        st.setValue("export_dir", parent)
        out = os.path.join(parent, base)
        k = 2
        while os.path.exists(out):
            out = os.path.join(parent, base + f" ({k})")
            k += 1
        os.makedirs(out)
        errors, written = [], []
        if not single and any(s_.get('_uwagi') for _, s_ in entries):
            try:
                pth = os.path.join(out, "00 Plan dla muzyków.html")
                with open(pth, "w", encoding="utf-8") as f:
                    f.write(self.plan_html([s_ for _, s_ in entries]))
                written.append(pth)
            except Exception as e:
                errors.append(f"plan: {e}")
        labels = [f"{n + 1:02d} " + (f"{part} – " if part and part != FREE_PART else "") + song.get('title', '')
                  for n, (part, song) in enumerate(entries)] if len(entries) > 1 else [entries[0][1].get('title', '')]
        from PySide6.QtWidgets import QProgressDialog
        pd = QProgressDialog("Przygotowuję materiały…", "Przerwij", 0, 100 * (len(entries) + 2), self)
        pd.setWindowTitle("Eksport materiałów")
        pd.setMinimumDuration(0)
        step = [0]

        def tick(label, inc=100):
            step[0] += inc
            pd.setValue(min(pd.maximum(), step[0]))
            pd.setLabelText(label)
            QApplication.processEvents()
            return not pd.wasCanceled()
        # nuty PDF i dołączone nagrania
        all_pdfs = []
        if sc.isChecked() or rec.isChecked():
            for (part, song), label in zip(entries, labels):
                if not tick(f"Nuty: {song.get('title', '')}", 0):
                    break
                if sc.isChecked():
                    for j, (name, data) in enumerate(self.song_scores_pdf(song)):
                        path = os.path.join(out, "nuty", f"{modul_audio._safe(label)} – nuty" + (f" {j + 1}" if j else "") + ".pdf")
                        os.makedirs(os.path.dirname(path), exist_ok=True)
                        with open(path, 'wb') as f:
                            f.write(data)
                        written.append(path)
                        all_pdfs.append(path)
                if rec.isChecked() and song.get('id'):
                    for a in self.db.attachments(song['id']):
                        if a['kind'] == 'Nagranie':
                            path = os.path.join(out, "nagrania", f"{modul_audio._safe(label)} – {a['name']}")
                            os.makedirs(os.path.dirname(path), exist_ok=True)
                            with open(path, 'wb') as f:
                                f.write(self.db.attachment(a['id'])['data'])
                            written.append(path)
                                
            if sc.isChecked() and sc_one.isChecked() and len(all_pdfs) > 1:
                try:
                    from pypdf import PdfWriter
                    wr = PdfWriter()
                    for pth in all_pdfs:
                        wr.append(pth)
                    one = os.path.join(out, f"{base} – nuty.pdf")
                    with open(one, 'wb') as f:
                        wr.write(f)
                    written.append(one)
                except Exception as e:
                    errors.append(f"łączenie nut: {e}")
        # nagrania do nauki
        if audio:
            opts = {'voices_sel': "".join(r for r, cb in vcb.items() if cb.isChecked()),
                    'variants': [k for k, cb in var.items() if cb.isChecked()], 'tempos': tempos,
                    'bg': bg.value() / 100, 'voice_instr': vin.currentData(), 'bg_instr': bin_.currentData(),
                    'format': afmt.currentData()}
            adir = os.path.join(out, "nagrania")
            for (part, song), label in zip(entries, labels):
                if (part, song) not in with_notes:
                    continue
                if not tick(f"Nagrania: {song.get('title', '')}\n(synteza głosów może chwilę potrwać)", 0):
                    break
                try:
                    mid = self.song_midi(song)
                    if not mid:
                        raise RuntimeError("brak MIDI (zainstaluj MuseScore, aby przeliczyć nuty)")
                    files = modul_audio.render_song(mid, adir, label, opts)
                    song['_nagrania'] = [os.path.basename(f) for f in files]
                    written += files
                except Exception as e:
                    errors.append(f"{song.get('title', '')}: {e}")
                tick(f"Nagrania: {song.get('title', '')}")
        # teksty
        try:
            tick("Teksty…", 0)
            if single:
                prog = mass_program(entries, None, single.get('title') or "Pieśń", "", 'none')
            else:
                prog = mass_program(entries, lit, self.mass_title(),
                                    self._mass_subtitle() if m['rodzaj'] == 'msza' else "", mode.currentData())
            for kind in chosen:
                path = os.path.join(out, base + "." + kind)
                export_program(prog, path, kind, size.value())
                written.append(path)
        except Exception as e:
            errors.append(f"teksty: {e}")
        # slajdy
        try:
            if sl_pdf.isChecked() or sl_pptx.isChecked():
                tick("Slajdy…", 0)
                deck = build_set_deck([s for _, s in entries], self.sep_chk.isChecked()) if not single else \
                    (self.deck or build_song_deck(single))
                if sl_pdf.isChecked():
                    export_pdf(deck, os.path.join(out, base + " – slajdy.pdf"))
                    written.append("slajdy.pdf")
                if sl_pptx.isChecked():
                    export_pptx(deck, os.path.join(out, base + " – slajdy.pptx"))
                    written.append("slajdy.pptx")
        except Exception as e:
            errors.append(f"slajdy: {e}")
        pd.setValue(pd.maximum())
        msg = f"Zapisano {len(written)} plików w folderze:\n{out}"
        if errors:
            msg += "\n\nNie udało się:\n  " + "\n  ".join(errors[:10])
        QMessageBox.information(self, APP_NAME, msg)
        QDesktopServices.openUrl(QUrl.fromLocalFile(out))

    def set_songs(self):
        if self.dirty and self.song and self.song.get('id') in self.set_ids():
            self.save_song()
        out = []
        idx = {}
        for part, sid in self.set_entries():
            j = idx[part] = idx.get(part, -1) + 1
            song = self.db.get(sid)
            if song:
                song = dict(song)
                song['_czesc'] = part
                song['_uwagi'] = self.setlist.notes(part, j)
                out.append(song)
        return out

    def _notes_selected(self):
        it = self.setlist.currentItem()
        if it is None or it.parent() is None:
            QMessageBox.information(self, APP_NAME, "Zaznacz pieśń w zestawie.")
            return
        part = it.parent().data(0, Qt.UserRole + 1)
        self.v_mass.edit_notes(part, it.parent().indexOfChild(it))

    def plan_html(self, songs=None):
        """Plan zestawu dla muzyków: część, pieśń, tonacja, wykonawca, uwagi, na co zwrócić uwagę."""
        songs = self.set_songs() if songs is None else songs
        rows = []
        for n, s_ in enumerate(songs, 1):
            u = s_.get('_uwagi') or {}
            part = s_.get('_czesc') if s_.get('_czesc') != FREE_PART else ''
            rows.append("<tr>" + "".join(f"<td>{H.escape(str(x))}</td>" for x in (
                n, part or '', s_.get('title', '') + (f" ({s_['spiewnik']})" if s_.get('spiewnik') else ''),
                u.get('tonacja', ''), u.get('wykonawca', ''),
                u.get('uwagi', ''), u.get('zwroc', ''))) + "</tr>")
        title = H.escape(self.mass_title())
        return f"""<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:sans-serif;margin:2em}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #999;padding:.4em .6em;vertical-align:top;text-align:left}}th{{background:#eee}}
td:nth-child(7){{color:#a02020;font-weight:bold}}@media print{{body{{margin:0}}}}</style></head><body>
<h1>{title}</h1><p>Plan dla muzyków</p><table><tr><th>#</th><th>Część</th><th>Pieśń</th><th>Tonacja</th><th>Wykonawca</th>
<th>Uwagi</th><th>Na co zwrócić uwagę</th></tr>{''.join(rows)}</table></body></html>"""

    def open_plan(self):
        songs = self.set_songs()
        if not songs:
            QMessageBox.information(self, APP_NAME, "Zestaw jest pusty.")
            return
        import tempfile
        path = os.path.join(tempfile.gettempdir(), sanitize_name("Plan " + self.mass_title()) + ".html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.plan_html(songs))
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def present_setlist(self):
        songs = self.set_songs()
        if not songs:
            QMessageBox.information(self, APP_NAME, "Zestaw jest pusty – dodaj pieśni z listy wyszukiwania.")
            return
        self._open_present(build_set_deck(songs, self.sep_chk.isChecked()), 0, True)

    # ================= eksport =================
    FILTERS = {'pdf': "PDF (*.pdf)", 'pptx': "PowerPoint (*.pptx)", 'docx': "Word – dostępny dla czytników ekranu (*.docx)"}

    def _export(self, base, kind, deck_fn, songs_fn, title=None, subtitle=None):
        last = self.settings.value("export_dir", os.path.expanduser("~"))
        path, _ = QFileDialog.getSaveFileName(self, "Eksport", os.path.join(last, f"{sanitize_name(base)}.{kind}"), self.FILTERS[kind])
        if not path:
            return
        if not path.lower().endswith('.' + kind):
            path += '.' + kind
        self.settings.setValue("export_dir", os.path.dirname(path))
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            if kind == 'docx':
                export_docx(songs_fn(), path, title or base.replace('_', ' '), subtitle=subtitle)
            else:
                deck = deck_fn()
                (export_pdf if kind == 'pdf' else export_pptx)(deck, path)
            self.statusBar().showMessage(f"Zapisano: {path}", 6000)
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Błąd eksportu:\n{e}")
        finally:
            QApplication.restoreOverrideCursor()

    def export_current(self, kind):
        if not self.deck and kind != 'docx':
            QMessageBox.information(self, APP_NAME, "Brak slajdów do eksportu.")
            return
        song = self.editor_song()
        self._export(song['title'], kind, lambda: self.deck, lambda: [song])

    def export_set(self, kind):
        songs = self.set_songs()
        if not songs:
            QMessageBox.information(self, APP_NAME, "Zestaw jest pusty.")
            return
        m = self.mass_meta()
        base = (f"Msza {m['data']} {m['godzina'].replace(':', '.')}" if m['rodzaj'] == 'msza'
                else f"{m['nazwa'] or 'Zestaw'} {m['data']}") + (f" {m['miejsce']}" if m['miejsce'] else "")
        if kind == 'docx':
            self._export(base, kind, None, lambda: songs, title=self.mass_title(), subtitle=self._mass_subtitle())
        else:
            self._export(base, kind, lambda: build_set_deck(songs, self.sep_chk.isChecked()), lambda: songs)

    def _mass_subtitle(self):
        m = self.mass_meta()
        return " • ".join(x for x in (m.get('dzien'), m.get('okres')) if x)

    # ================= nuty i nagrania =================
    def refresh_media(self):
        self.att_list.clear()
        self.yt_list.clear()
        sid = (self.song or {}).get('id')
        if sid:
            for a in self.db.attachments(sid):
                it = QListWidgetItem(f"[{a['kind']}]  " + (f"{a['opis']}:  " if a['opis'] else "") +
                                     f"{a['name']}   ({a['size'] // 1024 + 1} KB)")
                it.setData(Qt.UserRole, a['id'])
                it.setData(Qt.UserRole + 1, a['kind'])
                it.setData(Qt.UserRole + 2, a['name'])
                if a['name'].lower().endswith(SCORE_EXT):
                    d = self.db.get_derived(a['id'])
                    it.setText(it.text() + ("   ✓ podgląd i MIDI" if d and d['pdf'] else "   (podgląd po konwersji w MuseScore)"))
                self.att_list.addItem(it)
            for line in (self.song.get('youtube') or '').splitlines():
                if line.strip():
                    url, _, title = line.partition('\t')
                    it = QListWidgetItem(title or url)
                    it.setData(Qt.UserRole, url)
                    it.setToolTip(url)
                    self.yt_list.addItem(it)
        self.ver_list.clear()
        if sid:
            for v in self.db.versions(sid):
                first = first_line_key(v['refren'], v['zwrotki'])
                it = QListWidgetItem(f"{v['nazwa']}   – {(v['zwrotki'] or v['refren'] or '').strip().splitlines()[0][:60] if (v['zwrotki'] or v['refren'] or '').strip() else '(pusty)'}")
                it.setData(Qt.UserRole, v['id'])
                it.setToolTip(first)
                self.ver_list.addItem(it)
        self.media_hint.setText("" if sid else "Zapisz pieśń w bazie, aby dołączać nuty, wersje i nagrania.")
        self._att_buttons()
        self._ver_buttons()

    def _ver_buttons(self, *_):
        it = self.ver_list.currentItem()
        for k in ('view', 'use', 'ren', 'del'):
            self.b_ver[k].setEnabled(it is not None)
        self.b_ver['add'].setEnabled(bool((self.song or {}).get('id')))

    def _cur_version(self):
        it = self.ver_list.currentItem()
        return self.db.get_version(it.data(Qt.UserRole)) if it else None

    def show_version(self):
        v = self._cur_version()
        if not v:
            return
        import difflib
        main = self.editor_song()
        a = (("Ref.: " + main['refren'] + "\n\n") if main['refren'] else "") + main['zwrotki_raw']
        b = (("Ref.: " + v['refren'] + "\n\n") if v['refren'] else "") + (v['zwrotki'] or '')
        d = QDialog(self)
        d.setWindowTitle(f"Wersja: {v['nazwa']}")
        d.resize(1100, 650)
        lay = QVBoxLayout(d)
        info = " | ".join(x for x in (v.get('zrodlo'), v.get('uwagi'), (v.get('dodano') or '')[:10]) if x)
        if info:
            lay.addWidget(QLabel(info))
        hd = difflib.HtmlDiff(wrapcolumn=55)
        tb = QTextBrowser()
        tb.setHtml(hd.make_file(a.splitlines(), b.splitlines(), "Tekst główny", H.escape(v['nazwa']), context=False)
                   .replace('<table class="diff" summary="Legends">', '<table style="display:none">'))
        lay.addWidget(tb, 1)
        row = QHBoxLayout()
        bu = QPushButton("Ustaw tę wersję jako tekst główny")
        bu.clicked.connect(lambda: (d.accept(), self.use_version()))
        row.addWidget(bu)
        row.addStretch(1)
        bc = QPushButton("Zamknij")
        bc.clicked.connect(d.reject)
        row.addWidget(bc)
        lay.addLayout(row)
        d.exec()

    def use_version(self):
        v = self._cur_version()
        if not v or not self.ensure_saved("Aby zmienić tekst główny"):
            return
        self.db.snapshot(f"Zamiana tekstu głównego „{self.song['title']}” na wersję „{v['nazwa']}”")
        song = self.db.use_version(v['id'])
        if song:
            self.dirty = False
            self.load_into_editor(self.db.get(song['id']))
            self.refresh_media()
            self.refresh_list()
            self.pilot_invalidate()
            self.statusBar().showMessage("Wersja jest teraz tekstem głównym; poprzedni tekst został zapisany jako wersja.", 7000)

    def rename_version(self):
        v = self._cur_version()
        if not v:
            return
        name, ok = QInputDialog.getText(self, APP_NAME, "Nazwa wersji:", text=v['nazwa'])
        if ok and name.strip():
            self.db.rename_version(v['id'], name.strip())
            self.refresh_media()

    def delete_version(self):
        v = self._cur_version()
        if v and QMessageBox.question(self, APP_NAME, f"Usunąć wersję tekstu „{v['nazwa']}”?") == QMessageBox.Yes:
            self.db.snapshot(f"Usunięcie wersji „{v['nazwa']}”")
            self.db.delete_version(v['id'])
            self.refresh_media()

    def describe_attachment(self):
        it = self.att_list.currentItem()
        if not it:
            return
        aid = it.data(Qt.UserRole)
        row = self.db.con.execute("SELECT COALESCE(opis, '') FROM attachments WHERE id=?", (aid,)).fetchone()
        presets = ["", "Melodia", "Melodia z akordami", "Chór SATB", "Chór 3-głosowy", "Schola", "Organy", "Fortepian",
                   "Gitara", "Kwartet smyczkowy", "Nagranie"] + sorted({v['opis'] for v in map(dict, self.db.con.execute(
                       "SELECT DISTINCT opis FROM attachments WHERE COALESCE(opis, '') <> ''"))})
        cur = row[0] if row else ""
        items = list(dict.fromkeys([cur] + presets))
        text, ok = QInputDialog.getItem(self, APP_NAME, "Wersja / aranżacja tego pliku\n"
                                        "(np. „Chór SATB”, „Organy”, „Śpiewnik oazowy 2026”):", items, 0, True)
        if ok:
            self.db.set_attachment_desc(aid, text)
            self.refresh_media()

    def _att_buttons(self, *_):
        it = self.att_list.currentItem()
        for k in ('open', 'save', 'del', 'desc'):
            self.b_att[k].setEnabled(it is not None)
        name = (it.data(Qt.UserRole + 2) or '').lower() if it else ''
        self.b_att['view'].setEnabled(name.endswith(('.pdf', '.png', '.jpg', '.jpeg') + SCORE_EXT))
        self.b_att['midi'].setEnabled(name.endswith(('.mid', '.midi', '.kar') + SCORE_EXT))
        self.b_att['lyrics'].setEnabled(name.endswith(('.pdf', '.mid', '.midi', '.kar') + SCORE_EXT))
        self.b_att['omr'].setEnabled(name.endswith(('.pdf', '.png', '.jpg', '.jpeg', '.tif', '.tiff')))

    def add_attachments(self):
        if not self.ensure_saved("Aby dołączyć pliki"):
            return
        last = self.settings.value("attach_dir", os.path.expanduser("~"))
        exts = " ".join("*" + e for e in ATTACH_KINDS)
        paths, _ = QFileDialog.getOpenFileNames(self, "Dołącz nuty / pliki", last, f"Nuty i nagrania ({exts});;Wszystkie (*)")
        if not paths:
            return
        self.settings.setValue("attach_dir", os.path.dirname(paths[0]))
        for p in paths:
            aid = self.db.add_attachment(self.song['id'], p)
            self.convert_in_background(aid)
        self.pilot_invalidate()
        self.refresh_media()
        self.refresh_list()

    def _attachment_tempfile(self):
        it = self.att_list.currentItem()
        if not it:
            return None
        a = self.db.attachment(it.data(Qt.UserRole))
        folder = os.path.join(tempfile.gettempdir(), "spiewnik_zalaczniki")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"{a['id']}_{a['name']}")
        with open(path, 'wb') as f:
            f.write(a['data'])
        return path

    def open_attachment(self):
        path = self._attachment_tempfile()
        if path and path.lower().endswith(SCORE_EXT):          # pliki MuseScore – wprost w MuseScore (też AppImage)
            exe = self.musescore()
            if exe:
                import modul_nuty
                if modul_nuty.open_in_musescore(exe, path):
                    self.statusBar().showMessage(f"Otwieram w MuseScore: {os.path.basename(path)}", 5000)
                    return
        if path and not QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            QMessageBox.warning(self, APP_NAME, "Brak programu do otwarcia tego pliku (np. MuseScore dla .mscz).")

    def save_attachment(self):
        it = self.att_list.currentItem()
        if not it:
            return
        a = self.db.attachment(it.data(Qt.UserRole))
        path, _ = QFileDialog.getSaveFileName(self, "Zapisz plik", os.path.join(os.path.expanduser("~"), a['name']))
        if path:
            with open(path, 'wb') as f:
                f.write(a['data'])

    def delete_attachment(self):
        it = self.att_list.currentItem()
        if it and QMessageBox.question(self, APP_NAME, f"Usunąć załącznik „{it.text()}”?") == QMessageBox.Yes:
            self.db.delete_attachment(it.data(Qt.UserRole))
            self.pilot_invalidate()
            self.refresh_media()
            self.refresh_list()

    # --- MuseScore: konwersja do PDF (podgląd) i MIDI (głosy)
    def musescore(self):
        import modul_nuty
        return modul_nuty.find_musescore(self.settings.value("musescore", ""))

    def set_musescore_path(self):
        import modul_nuty
        cur = self.musescore() or ""
        apps = modul_nuty.find_appimages()
        start = os.path.dirname(cur) if cur and not cur.startswith('flatpak:') else (os.path.dirname(apps[0]) if apps else os.path.expanduser("~"))
        path, _ = QFileDialog.getOpenFileName(
            self, "Wskaż MuseScore: plik AppImage (Linux), MuseScore4.exe (Windows), mscore…", start,
            "MuseScore (*.AppImage *.appimage *.exe mscore* MuseScore* musescore*);;Wszystkie pliki (*)")
        if not path:
            return
        if not modul_nuty.ensure_executable(path):
            QMessageBox.warning(self, APP_NAME, f"Nie mogę nadać prawa do uruchamiania plikowi:\n{path}\n\n"
                                                 "W terminalu: chmod +x \"" + path + "\"")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ver = modul_nuty.musescore_version(path)
        finally:
            QApplication.restoreOverrideCursor()
        if not ver:
            msg = ("Nie udało się uruchomić tego pliku jako MuseScore.\n\n"
                   "Dla AppImage spróbuj w terminalu:  \"" + path + "\" --version\n"
                   "Jeśli pojawi się błąd FUSE, zainstaluj:  sudo apt install libfuse2  (Ubuntu 22.04: libfuse2,\n"
                   "Ubuntu 24.04 / Mint 22: libfuse2t64).") if path.lower().endswith('.appimage') else \
                  "Nie udało się uruchomić tego pliku jako MuseScore."
            if QMessageBox.question(self, APP_NAME, msg + "\n\nZapisać tę ścieżkę mimo to?") != QMessageBox.Yes:
                return
        self.settings.setValue("musescore", path)
        nofuse = path in modul_nuty._APPIMAGE_NOFUSE
        QMessageBox.information(self, APP_NAME, f"MuseScore: {path}\n{ver or '(nie odpowiada na --version)'}\n\n"
                                "Sprawdź konwersję: Ustawienia → Test MuseScore." +
                                ("\n\nAppImage działa bez FUSE (tryb rozpakowania) – konwersje mogą trwać kilka sekund dłużej. "
                                 "Szybciej: sudo apt install libfuse2 (lub libfuse2t64)." if nofuse else ""))

    def musescore_failed(self, what):
        """Komunikat, gdy MuseScore nie przeliczył pliku – z rozróżnieniem przyczyny i dziennikiem."""
        import modul_nuty
        exe = self.musescore()
        if not exe:
            QMessageBox.information(self, APP_NAME, f"{what}: do plików MuseScore potrzebny jest MuseScore na tym komputerze.\n"
                                                    "Wskaż go: Ustawienia → Ścieżka do MuseScore (np. plik .AppImage).")
            return
        box = QMessageBox(QMessageBox.Warning, APP_NAME,
                          f"{what}: MuseScore ({os.path.basename(exe)}) nie przeliczył tego pliku do MIDI/PDF.\n\n"
                          "Uruchom: Ustawienia → Test MuseScore – i jeśli test też się nie uda, skopiuj raport "
                          "(przycisk „Pokaż szczegóły”).", parent=self)
        box.setDetailedText(modul_nuty.last_log_text() or "(brak dziennika)")
        box.exec()

    def test_musescore(self):
        import modul_nuty
        exe = self.musescore()
        if not exe:
            QMessageBox.information(self, APP_NAME, "Nie znaleziono MuseScore. Wskaż go: Ustawienia → Ścieżka do MuseScore.")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.statusBar().showMessage("Test MuseScore – próbna konwersja (do kilku minut przy pierwszym uruchomieniu)…")
        QApplication.processEvents()
        try:
            report, ok = modul_nuty.test_musescore(exe)
        finally:
            QApplication.restoreOverrideCursor()
        box = QMessageBox(QMessageBox.Information if ok else QMessageBox.Warning, "Test MuseScore",
                          ("✓ MuseScore działa: podgląd nut i MIDI – odtwarzanie głosów będą dostępne." if ok else
                           "✗ MuseScore nie przeliczył próbnego utworu.\nSkopiuj raport (Pokaż szczegóły → zaznacz → Ctrl+C) "
                           "i prześlij go, to dopasuję program do Twojej wersji MuseScore."), parent=self)
        box.setDetailedText(report)
        b_copy = box.addButton("Kopiuj raport", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Ok)
        box.exec()
        if box.clickedButton() is b_copy:
            QApplication.clipboard().setText(report)
            self.statusBar().showMessage("Raport testu skopiowany do schowka.", 6000)
        if ok:                                                # wcześniej nieudane konwersje – spróbuj ponownie
            self.refresh_media()

    def convert_in_background(self, aid):
        """Pliki MuseScore/MusicXML: w tle przelicz do PDF i MIDI (zapamiętane w bazie)."""
        row = self.db.attachment(aid)
        if not row or not row['name'].lower().endswith(SCORE_EXT):
            return
        exe = self.musescore()
        if not exe:
            self.statusBar().showMessage("Brak MuseScore – plik zapisany, podgląd tylko jako miniatura (Ustawienia → MuseScore).", 8000)
            return
        import modul_nuty
        name, data = row['name'], row['data']
        self.statusBar().showMessage(f"MuseScore przelicza „{name}” do PDF i MIDI…")

        def work():
            res = modul_nuty.convert_score(exe, name, data)
            self._conv_done.emit(aid, res.get('pdf') or b'', res.get('mid') or b'', res.get('spos') or b'')

        threading.Thread(target=work, daemon=True).start()

    def _on_conv_done(self, aid, pdf, mid, pos):
        if not self.db.attachment(aid):
            return
        self.db.set_derived(aid, pdf or None, mid or None, pos or None)
        self.pilot_invalidate()
        self.refresh_media()
        self.statusBar().showMessage("MuseScore: gotowy podgląd nut i MIDI." if pdf else
                                    "MuseScore nie przeliczył pliku – uruchom Ustawienia → Test MuseScore.", 10000)

    def _derived_now(self, aid, name, data):
        """PDF/MIDI z pliku MuseScore – z bazy albo przeliczone teraz (z kursorem oczekiwania)."""
        d = self.db.get_derived(aid)
        exe = self.musescore()
        if d and (d['pdf'] or d['mid']) and ((d['pos'] and d['mid']) or not exe):
            return d['pdf'], d['mid'], d['pos']
        if not exe:
            return None, None, None
        import modul_nuty
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.statusBar().showMessage(f"MuseScore przelicza „{name}”…")
        QApplication.processEvents()
        try:
            res = modul_nuty.convert_score(exe, name, data)
        finally:
            QApplication.restoreOverrideCursor()
        self.db.set_derived(aid, res.get('pdf'), res.get('mid'), res.get('spos'))
        self.pilot_invalidate()
        return res.get('pdf'), res.get('mid'), res.get('spos')

    def _staves_for(self, a):
        """(partie z widocznością, funkcja przeliczająca nuty z inną widocznością) dla pliku MuseScore."""
        import modul_nuty
        name, data, aid = a['name'], a['data'], a['id']
        parts = modul_nuty.staves_visibility(name, data)
        if len(parts) < 2 or not self.musescore():
            return None
        saved = self.settings.value(f"staves/{aid}", "")
        try:
            want = json.loads(saved) if saved else None
        except ValueError:
            want = None
        if want and len(want) == len(parts):
            parts = [(nm, bool(w)) for (nm, _), w in zip(parts, want)]

        def render(want):
            new = modul_nuty.set_staves_visibility(name, data, want)
            if not new:
                return None
            d = self.db.get_derived(aid)
            need_mid = not (d and d['mid'])
            res = modul_nuty.convert_score(self.musescore(), name, new,
                                           outs=('pdf', 'spos', 'mid') if need_mid else ('pdf', 'spos'))
            if res.get('pdf') and res.get('spos'):
                mid = res.get('mid') if need_mid else d['mid']        # dźwięk ten sam – widoczność go nie zmienia
                self.db.set_derived(aid, res['pdf'], mid, res['spos'])   # widać wszędzie (podgląd, Nuty, odtwarzacz)
                self.settings.setValue(f"staves/{aid}", json.dumps([bool(w) for w in want]))
                self.pilot_invalidate()
            return res.get('pdf'), res.get('spos')
        return parts, render

    def preview_attachment(self):
        it = self.att_list.currentItem()
        if not it:
            return
        import modul_nuty
        a = self.db.attachment(it.data(Qt.UserRole))
        name, data, low = a['name'], a['data'], a['name'].lower()
        midi, info, score = None, "", None
        if low.endswith('.pdf'):
            pages = modul_nuty.pdf_pages_to_jpeg(data, width=1600, quality=85)
        elif low.endswith(('.png', '.jpg', '.jpeg')):
            pages = [data]
        elif low.endswith(SCORE_EXT):
            pdf, midi, pos = self._derived_now(a['id'], name, data)
            score = (pdf, pos) if pdf and pos else None
            meta = modul_nuty.score_info(name, data)
            info = " • ".join(x for x in (meta.get('title'), meta.get('composer'),
                                          ("głosy: " + ", ".join(meta['parts'])) if meta.get('parts') else "") if x)
            if pdf:
                pages = modul_nuty.pdf_pages_to_jpeg(pdf, width=1600, quality=85)
            else:
                thumb = modul_nuty.mscz_thumbnail(data)
                pages = [thumb] if thumb else []
                info = (info + " • " if info else "") + (
                    "Pokazuję miniaturę 1. strony – MuseScore nie przeliczył pliku (Ustawienia → Test MuseScore)."
                    if self.musescore() else
                    "Pokazuję miniaturę 1. strony – pełny podgląd wymaga MuseScore (Ustawienia → Ścieżka do MuseScore).")
        else:
            return
        if not pages:
            QMessageBox.information(self, APP_NAME, "Nie udało się przygotować podglądu tego pliku.")
            return
        dlg = modul_nuty.ScoreViewer(f"{self.song['title']} – {name}", pages, info, midi, self.open_attachment, self, score=score)
        self.midi_dialogs.append(dlg)
        dlg.finished.connect(lambda *_: self.midi_dialogs.remove(dlg) if dlg in self.midi_dialogs else None)
        dlg.show()

    def play_midi(self):
        it = self.att_list.currentItem()
        if not it:
            return
        a = self.db.attachment(it.data(Qt.UserRole))
        data, score = a['data'], None
        if a['name'].lower().endswith(SCORE_EXT):
            pdf, data, pos = self._derived_now(a['id'], a['name'], a['data'])
            score = (pdf, pos) if pdf and pos else None
            if not data:
                self.musescore_failed("MIDI – odtwarzanie głosów")
                return
        staves = self._staves_for(a) if score else None
        transposer = None
        if score and self.musescore():
            name, raw, exe = a['name'], a['data'], self.musescore()

            def transposer(k, want, colors=None):
                import modul_nuty as mn
                new = mn.transpose_score(name, raw, k, want)
                if new and colors:
                    new = mn.color_score(name, new, colors) or new
                if not new:
                    return None
                res = mn.convert_score(exe, name, new, outs=('pdf', 'spos'))
                return res.get('pdf'), res.get('spos')
        try:
            import modul_nuty
            dlg = modul_nuty.MidiPlayerDialog(data, f"{self.song['title']} – {a['name']}", self, score=score,
                                              staves=staves, transposer=transposer)
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Nie można uruchomić odtwarzacza MIDI:\n{e}")
            return
        self.midi_dialogs.append(dlg)
        dlg.finished.connect(lambda *_: self.midi_dialogs.remove(dlg) if dlg in self.midi_dialogs else None)
        dlg.show()

    def search_scores(self):
        try:
            import modul_nuty
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Brak modułu nut:\n{e}")
            return
        if getattr(self, 'score_dlg', None) and self.score_dlg.isVisible():
            self._score_target()
            self.score_dlg.q.setText(re.sub(r"\s+[–—-]\s+", " ", self.editor_song()['title']))
            self.score_dlg.search_musescore()
            self.score_dlg.raise_()
            self.score_dlg.activateWindow()
            return
        self.score_dlg = modul_nuty.ScoreSearchDialog(self.editor_song()['title'], self.settings, self)
        self.score_dlg.files_downloaded.connect(self._attach_downloaded)
        self._score_target()
        self.score_dlg.show()                      # niemodalne – program dalej działa

    def _score_target(self):
        """Okno szukania nut zapisuje do pieśni, dla której je otwarto (nawet gdy w międzyczasie otworzysz inną)."""
        dlg = self.score_dlg
        sid = self.song.get('id') if self.song else None
        title = self.song.get('title', '') if self.song else ''
        dlg.target_sid, dlg.target_title = sid, title
        dlg.setWindowTitle(f"Szukaj i dołącz nuty – do pieśni „{title}”" if sid else "Szukaj i dołącz nuty")
        if hasattr(dlg, 'b_save'):
            dlg.b_save.setToolTip(f"Zapisuje zaznaczone pliki jako nuty pieśni „{title}”" if sid else "")

    # --- przeciągnij i upuść na okno programu
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        local = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile() and os.path.isfile(u.toLocalFile())]
        remote = [u.toString() for u in e.mimeData().urls() if u.scheme() in ('http', 'https')]
        e.acceptProposedAction()
        lyrics_ext = ('.docx', '.odt', '.txt', '.htm', '.html', '.json')
        attach, lyrics = [], []
        for p in local:
            low = p.lower()
            if low.endswith(lyrics_ext):
                lyrics.append(p)
            elif low.endswith('.pdf') and self.tabs.currentIndex() != 2:
                box = QMessageBox(QMessageBox.Question, APP_NAME, f"Plik PDF: {os.path.basename(p)}\nCo z nim zrobić?")
                b1 = box.addButton("Dołącz jako nuty", QMessageBox.AcceptRole)
                b2 = box.addButton("Importuj tekst pieśni", QMessageBox.ActionRole)
                box.addButton(QMessageBox.Cancel)
                box.exec()
                if box.clickedButton() is b1:
                    attach.append(p)
                elif box.clickedButton() is b2:
                    lyrics.append(p)
            else:
                attach.append(p)
        files = []
        for p in attach:
            with open(p, 'rb') as f:
                files.append((os.path.basename(p), f.read()))
        for url in remote:
            try:
                import modul_nuty
                QApplication.setOverrideCursor(Qt.WaitCursor)
                data, ctype, fname = modul_nuty.download(url)
            except Exception as ex:
                self.statusBar().showMessage(f"Nie udało się pobrać {url}: {ex}", 8000)
                continue
            finally:
                QApplication.restoreOverrideCursor()
            if ctype == 'text/html':
                self.statusBar().showMessage("Upuszczono link do strony – pobierz plik w przeglądarce i przeciągnij plik.", 8000)
                continue
            files.append((fname or os.path.basename(url.split('?')[0]) or "plik", data))
        if files:
            self.tabs.setCurrentIndex(2)
            self._attach_downloaded(files)
        if lyrics:
            self.import_paths(lyrics)

    def _attach_downloaded(self, files):
        """files: [(nazwa, bajty)] pobrane w oknie szukania nut – do pieśni, dla której otwarto okno."""
        dlg = getattr(self, 'score_dlg', None)
        sid = getattr(dlg, 'target_sid', None) if dlg else None
        if not sid or not self.db.get(sid):
            if not self.ensure_saved("Aby dołączyć pobrane nuty"):
                return
            sid = self.song['id']
            if dlg:
                self._score_target()
        title = self.db.get(sid)['title']
        have = {bytes(self.db.attachment(a['id'])['data']) for a in self.db.attachments(sid)}
        added, same = [], []
        for name, data in files:
            if bytes(data) in have:                       # ten sam plik już jest przy pieśni
                same.append(name)
                continue
            aid = self.db.add_attachment_bytes(sid, name, data)
            have.add(bytes(data))
            added.append(name)
            self.convert_in_background(aid)
        msg = (f"Dołączono do „{title}”: {', '.join(added)}" if added else "") + \
              (f"  (już były: {', '.join(same)})" if same else "")
        self.statusBar().showMessage(msg, 8000)
        if dlg:
            dlg.status.setText(msg)
        self.pilot_invalidate()
        self.refresh_media()
        self.refresh_list()

    # --- YouTube ---
    def _yt_lines(self):
        return [l for l in (self.song.get('youtube') or '').splitlines() if l.strip()]

    def _yt_store(self, lines):
        self.song['youtube'] = "\n".join(lines)
        self.db.set_youtube(self.song['id'], self.song['youtube'])
        self.refresh_media()

    def youtube_search(self):
        try:
            import modul_youtube
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Brak modułu YouTube:\n{e}")
            return
        dlg = modul_youtube.YouTubeSearchDialog(self.editor_song()['title'], self.settings, self)
        dlg.add_requested.connect(self._yt_add)
        dlg.play_requested.connect(self.play_youtube)
        dlg.exec()

    def youtube_add_link(self):
        url, ok = QInputDialog.getText(self, "Nagranie z YouTube", "Link do nagrania:")
        if ok and url.strip():
            title, ok2 = QInputDialog.getText(self, "Nagranie z YouTube", "Opis (np. wykonawca):")
            self._yt_add(url.strip(), title.strip() if ok2 else "")

    def _yt_add(self, url, title):
        if not self.ensure_saved("Aby zapamiętać nagranie"):
            return
        lines = [l for l in self._yt_lines() if l.split('\t')[0] != url]
        self._yt_store(lines + [f"{url}\t{title}".rstrip()])

    def youtube_remove(self):
        it = self.yt_list.currentItem()
        if it:
            self._yt_store([l for l in self._yt_lines() if l.split('\t')[0] != it.data(Qt.UserRole)])

    def play_youtube_selected(self, mode):
        it = self.yt_list.currentItem() or self.yt_list.item(0)
        if not it:
            QMessageBox.information(self, APP_NAME, "Brak nagrań – wyszukaj lub dodaj link.")
            return
        self.play_youtube(it.data(Qt.UserRole), mode)

    def play_youtube(self, url, mode):
        try:
            import modul_youtube
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Brak modułu YouTube:\n{e}")
            return
        if mode == 'audio':
            self.present_clean_background()
        if self.yt_player:
            self.yt_player.close()
        screen = self.pick_screen() if mode == 'video' else self.screen()
        self.yt_player = modul_youtube.play(url, mode, screen, self)
        if self.yt_player is None and mode != 'browser':
            self.statusBar().showMessage("Odtwarzanie w przeglądarce (brak PySide6-Addons dla wbudowanego odtwarzacza).", 8000)

    # ================= śpiewnik HTML (telefon / tablet) =================
    def _songbook_songs(self, scope):
        if scope == 'set':
            return self.set_songs()
        if scope == 'filter':
            ids = [self.results.topLevelItem(i).child(j).data(0, Qt.UserRole)
                   for i in range(self.results.topLevelItemCount()) for j in range(self.results.topLevelItem(i).childCount())]
            return [s for s in (self.db.get(i) for i in ids) if s]
        return [s for s in (self.db.get(r['id']) for r in self.db.search("")) if s]

    def build_songbook(self, scope, scores, title=None):
        import modul_html
        songs = self._songbook_songs(scope)
        if not songs:
            raise ValueError("Brak pieśni do eksportu.")
        title = title or (f"Zestaw {datetime.date.today()}" if scope == 'set' else "Śpiewnik")

        def atts(sid):
            out = []
            for a in self.db.attachments(sid):
                low = a['name'].lower()
                if low.endswith(('.pdf', '.png', '.jpg', '.jpeg')):
                    out.append((a['name'], a['kind'], self.db.attachment(a['id'])['data']))
                elif low.endswith(SCORE_EXT):
                    d = self.db.get_derived(a['id'])
                    if d and d['pdf']:
                        out.append((a['name'], 'MuseScore', d['pdf']))
            return out

        def progress(i, n, t):
            self.statusBar().showMessage(f"Śpiewnik HTML: {i + 1}/{n} – {t}")
            QApplication.processEvents()

        notes, parts, seen = self.setlist.all_notes(), [], {}
        for part, sid in self.set_entries():             # części zestawu z uwagami dla muzyków
            j = seen.get(part, 0)
            seen[part] = j + 1
            nn = notes.get(part) or []
            if not parts or parts[-1][0] != part:
                parts.append((part, []))
            parts[-1][1].append({'id': sid, 'notes': {k: v for k, v in ((nn[j] if j < len(nn) else {}) or {}).items() if v}})
        return modul_html.build_songbook_html(songs, title, atts if scores else None, scores,
                                              set_ids=self.set_ids(), progress=progress, set_parts=parts)

    def export_html(self, scope=None):
        if scope is None:
            items = ["Cała baza", "Tylko pieśni widoczne na liście (wyszukiwanie / filtr)", "Tylko zestaw"]
            choice, ok = QInputDialog.getItem(self, "Śpiewnik offline HTML", "Co wyeksportować?", items, 0, False)
            if not ok:
                return
            scope = ['all', 'filter', 'set'][items.index(choice)]
        scores = QMessageBox.question(self, "Śpiewnik offline HTML",
                                      "Dołączyć nuty (PDF i zdjęcia) – tryb dla organisty i chóru na tablecie?\n"
                                      "Plik będzie większy.") == QMessageBox.Yes
        base = f"Zestaw {datetime.date.today()}" if scope == 'set' else "Spiewnik"
        last = self.settings.value("html_dir", self.settings.value("export_dir", os.path.expanduser("~")))
        path, _ = QFileDialog.getSaveFileName(self, "Śpiewnik offline HTML", os.path.join(last, sanitize_name(base) + ".html"),
                                              "Strona HTML (*.html)")
        if not path:
            return
        if not path.lower().endswith('.html'):
            path += '.html'
        self.settings.setValue("html_dir", os.path.dirname(path))
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            text = self.build_songbook(scope, scores, base.replace('_', ' '))
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
            self.statusBar().showMessage(f"Zapisano śpiewnik: {path} ({len(text.encode()) // 1024} KB)", 8000)
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Błąd eksportu:\n{e}")
        finally:
            QApplication.restoreOverrideCursor()

    # ================= pilot w telefonie =================
    def open_pilot(self):
        try:
            import modul_pilot
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Brak modułu pilota:\n{e}")
            return
        if self.pilot is None or not self.pilot.running:
            self.pilot = modul_pilot.PilotServer(self.db.path, self)
            self.pilot.command.connect(self.on_pilot_command)
            self.pilot.uploaded.connect(self.on_pilot_upload)
            self.pilot.songbook_wanted.connect(self.on_pilot_songbook)
            try:
                self.pilot.start()
            except Exception as e:
                QMessageBox.critical(self, APP_NAME, str(e))
                self.pilot = None
                return
            self._pilot_ver = None
            self.pilot_publish()
            self.pilot_timer.start()
        dlg = modul_pilot.PilotDialog(self.pilot, self)
        dlg.resize(420, 560)
        if dlg.exec() == 2:
            self.pilot_timer.stop()
            self.pilot = None
            self.statusBar().showMessage("Pilot wyłączony.", 4000)
        else:
            self.statusBar().showMessage(f"Pilot działa: {self.pilot.url(False)}  PIN {self.pilot.token}")

    def pilot_invalidate(self):
        if self.pilot:
            self.pilot.invalidate()
            self._pilot_ver = None

    def _pilot_deck(self):
        if self.present:
            return self.present.deck, self.present.i
        return self.deck, max(0, self.thumbs.currentRow())

    def pilot_publish(self):
        if not self.pilot or not self.pilot.running:
            return
        import modul_pilot
        deck, idx = self._pilot_deck()
        ver = f"{id(deck)}-{len(deck)}"
        images = None
        if ver != self._pilot_ver:
            images = modul_pilot.render_thumbs(deck, paint_slide)
            self._pilot_ver = ver
        sid = deck[idx].song_id if deck and 0 <= idx < len(deck) and deck[idx].song_id else (self.song or {}).get('id')
        song = self.db.get(sid) if sid else None
        atts = [{'id': a['id'], 'name': a['name'], 'kind': a['kind']} for a in self.db.attachments(sid)] if sid else []
        state = {
            'ver': ver, 'presenting': self.present is not None, 'set_mode': bool(self.present_set),
            'index': idx, 'count': len(deck), 'black': bool(self.present and self.present.black),
            'clean': bool(self.present and self.present.clean),
            'title': (deck[idx].title if deck and 0 <= idx < len(deck) else self.editor_song()['title']),
            'slides': [{'song': s.title} for s in deck],
            'setlist': [{'id': sid, 'title': (f"{part}: " if part != FREE_PART else "") + (self.db.get(sid) or {}).get('title', '')}
                        for part, sid in self.set_entries()],
            'song_id': sid, 'song_title': song['title'] if song else '', 'attachments': atts,
        }
        self.pilot.publish(state, images)

    def on_pilot_command(self, c):
        cmd, arg = c.get('cmd'), c.get('arg')
        p = self.present
        if cmd in ('next', 'prev', 'goto'):
            if not p:
                start = int(arg) if cmd == 'goto' and isinstance(arg, int) else max(0, self.thumbs.currentRow())
                self.start_present(start)
                return
            i = p.i + 1 if cmd == 'next' else p.i - 1 if cmd == 'prev' else int(arg) if isinstance(arg, int) else p.i
            p.show_index(i)
        elif cmd == 'black' and p:
            p.black = not p.black
            p.update()
        elif cmd == 'clean' and p:
            p.set_clean(not p.clean)
        elif cmd == 'start':
            self.start_present(max(0, self.thumbs.currentRow()))
        elif cmd == 'stop' and p:
            p.close()
        elif cmd == 'open_set':
            self.present_setlist()
        elif cmd == 'open_song' and isinstance(arg, int):
            if self.dirty:
                if self.song and self.song.get('id'):
                    self.save_song()                     # pilot nie może pytać – zapisz zmiany
                else:
                    self.statusBar().showMessage("Pilot: na komputerze jest niezapisana nowa pieśń – najpierw ją zapisz.", 8000)
                    return
            s = self.db.get(arg)
            if not s:
                return
            self.load_into_editor(s)
            if p and not self.present_set:
                p.set_deck(self.deck)
                p.show_index(0)
            else:
                self.start_present(0)
        self.pilot_publish()

    def on_pilot_upload(self, sid, name, data):
        if not self.db.get(sid):
            return
        aid = self.db.add_attachment_bytes(sid, name, data)
        self.convert_in_background(aid)
        self.pilot_invalidate()
        if self.song and self.song.get('id') == sid:
            self.refresh_media()
        self.refresh_list()
        self.statusBar().showMessage(f"Z telefonu dodano: {name}", 6000)

    def on_pilot_songbook(self, scope, scores):
        try:
            text = self.build_songbook(scope, scores)
            name = ("Zestaw" if scope == 'set' else "Spiewnik") + f"_{datetime.date.today()}.html"
            self.pilot.provide_songbook(scope, scores, text.encode('utf-8'), name)
            self.statusBar().showMessage(f"Pilot: wysłano śpiewnik offline ({len(text.encode()) // 1024} KB)", 6000)
        except Exception as e:
            self.pilot.provide_songbook(scope, scores, None, "")
            self.statusBar().showMessage(f"Pilot: błąd śpiewnika – {e}", 8000)

    # ================= import =================
    def import_files(self):
        last = self.settings.value("import_dir", os.path.expanduser("~"))
        paths, _ = QFileDialog.getOpenFileNames(self, "Import pieśni", last,
                                                "Teksty (*.docx *.odt *.pdf *.txt *.html *.htm *.json);;"
                                                "Nuty ze słowami (*.mscz *.mscx *.musicxml *.mxl *.xml *.pdf *.mid *.kar);;Wszystkie (*)")
        if not paths:
            return
        self.settings.setValue("import_dir", os.path.dirname(paths[0]))
        self.import_paths(paths)

    def search_online(self):
        """Okno: teksty w śpiewnikach internetowych → nuty w MuseScore (melodia, potem aranżacje) → dostępność dla bazy."""
        import modul_szukaj as ms
        if getattr(self, 'online_dlg', None) and self.online_dlg.isVisible():
            self.online_dlg.raise_()
            self.online_dlg.activateWindow()
            return

        def songs(scope):
            if scope == 'all':
                ids = [r['id'] for r in self.db.search("")]
            else:
                ids = []
                for i in range(self.results.topLevelItemCount()):
                    top = self.results.topLevelItem(i)
                    ids += [top.child(j).data(0, Qt.UserRole) for j in range(top.childCount())] or \
                        ([top.data(0, Qt.UserRole)] if top.data(0, Qt.UserRole) else [])
            return [s for s in (self.db.get(i) for i in ids if i) if s]

        def import_song(sg):
            if not self.maybe_save():
                return
            song = {'title': sg['title'], 'refren': sg.get('refren', ''), 'zwrotki_raw': sg.get('zwrotki_raw', ''),
                    'uwagi': sg.get('uwagi', ''), 'kategoria': sg.get('kategoria', ''), 'tagi': sg.get('tagi', ''),
                    'zrodlo': sg.get('zrodlo', ''), 'youtube': sg.get('youtube', ''),
                    'config': dict(self.default_cfg(), numeruj=sg.get('zwrotki_raw', '').count("\n\n") > 0)}
            self.new_song(ask=False, song=song)     # przy zapisie: pytanie o połączenie z podobną pieśnią w bazie
            self.raise_()
            self.statusBar().showMessage("Wczytano do edytora – sprawdź i zapisz (Ctrl+S).", 6000)

        def insert(sg):
            cur = self.editor_song()
            if (cur.get('refren') or cur.get('zwrotki_raw')) and QMessageBox.question(
                    self, APP_NAME, "Bieżąca pieśń ma już tekst. Zastąpić go tekstem ze śpiewnika?") != QMessageBox.Yes:
                return
            cur['refren'], cur['zwrotki_raw'] = sg.get('refren', ''), sg.get('zwrotki_raw', '')
            cur['title'] = cur.get('title') or sg['title']
            if sg.get('zrodlo') and not cur.get('zrodlo'):
                cur['zrodlo'] = sg['zrodlo']
            self.load_into_editor(cur)
            self.set_dirty(True)
            self.statusBar().showMessage("Wstawiono tekst – sprawdź i zapisz (Ctrl+S).", 6000)

        q = self.editor_song().get('title') or self.search.text()
        self.online_dlg = ms.SearchDialog(self.db.con, q, songs, import_song, insert, self.search_scores, self)
        self.online_dlg.show()

    def import_collection(self, coll, source=""):
        """Import wielu pieśni z jednej strony / pliku (np. dział śpiewnika internetowego)."""
        import modul_zbior as zb
        if not self.maybe_save():
            return
        cats = sorted(set(DEFAULT_CATEGORIES) | {c for c, _ in self.db.categories() if c})
        dlg = zb.CollectionDialog(coll, lambda sg: self.db.find_similar(sg['title'], sg.get('refren', ''),
                                                                        sg.get('zwrotki_raw', '')),
                                  cats, source, self, get_fn=self.db.get)
        if not dlg.exec():
            return
        songs = dlg.chosen()
        if not songs:
            return
        self.db.snapshot(f"Import {len(songs)} pieśni: {source or coll.get('naglowek') or 'zbiór'}")
        merged, same = [], []
        from PySide6.QtWidgets import QProgressDialog
        pd = QProgressDialog("Importuję pieśni…", "Przerwij", 0, len(songs), self)
        pd.setMinimumDuration(300)
        ok, errors = [], []
        for i, sg in enumerate(songs):
            if pd.wasCanceled():
                break
            pd.setValue(i)
            pd.setLabelText(sg['title'])
            QApplication.processEvents()
            song = {'title': sg['title'], 'refren': sg['refren'], 'zwrotki_raw': sg['zwrotki_raw'],
                    'uwagi': sg['uwagi'], 'tagi': sg.get('tagi', ''), 'kategoria': sg.get('kategoria', ''),
                    'zrodlo': source, 'youtube': sg.get('youtube', ''), 'akordy': sg.get('akordy', ''),
                    'config': dict(self.default_cfg(), numeruj=sg['zwrotki_raw'].count("\n\n") > 0)}
            try:
                label = (sg.get('uwagi') or '').split(" | ")[0] or source or sg['title']
                if sg.get('_akcja') == 'merge' and sg.get('_cel') and self.db.get(sg['_cel']):
                    song, what = self.db.merge_import(sg['_cel'], song, version_name=label)
                    if not what or what == ["tekst bez zmian"]:
                        same.append(sg['title'])
                    else:
                        merged.append(f"{sg['title']} → {song['title']}" + (f" ({', '.join(what)})" if what else ""))
                else:
                    self.db.save(song)
                    label = ""
                have = {(a['name'], a['size']) for a in self.db.attachments(song['id'])}
                if dlg.mp3.isChecked() and song.get('id'):
                    import modul_nuty
                    for line in song['youtube'].splitlines():
                        u = line.split("\t")[0]
                        if re.search(r"\.(mp3|ogg|m4a|wav)(\?|$)", u, re.I):
                            data, _, fname = modul_nuty.download(u)
                            name = fname or urllib.parse.unquote(u.rsplit('/', 1)[-1].split('?')[0])
                            if (name, len(data)) not in have:
                                self.db.add_attachment_bytes(song['id'], name, data, label)
                if getattr(dlg, 'pages', None) is not None and dlg.pages.isChecked() and sg.get('pdf') \
                        and sg.get('strony') and song.get('id'):
                    import modul_slowa_z_nut as sn
                    if sg.get('regiony'):                   # nuty-obrazki: tylko fragmenty stron z tą częścią
                        import modul_pdf_obrazy as mo
                        data = mo.render_regions(sg['pdf'], sg['regiony'])
                    else:
                        data = sn.pdf_pages_bytes(sg['pdf'], sg['strony'])
                    safe = re.sub(r'[\\/:*?"<>|]+', ' ', sg['title']).strip() or "nuty"
                    if (f"{safe} – nuty.pdf", len(data)) not in have:
                        self.db.add_attachment_bytes(song['id'], f"{safe} – nuty.pdf", data,
                                                     (sg.get('uwagi') or '').split(" | ")[0])
                ok.append(sg['title'])
            except Exception as e:
                errors.append(f"{sg['title']}: {e}")
        pd.setValue(len(songs))
        self.pilot_invalidate()
        self.refresh_filters()
        self.refresh_list()
        n_new = len(ok) - len(merged) - len(same)
        msg = f"Nowe pieśni: {n_new}."
        if merged:
            msg += f"\nDołączone do istniejących: {len(merged)}\n  " + "\n  ".join(merged[:15])
        if same:
            msg += f"\nJuż były w bazie z tym samym tekstem (uzupełniono tylko uwagi, tagi, nuty): {len(same)}"
        msg += "\n\nZmiany można cofnąć: Plik → Cofnij ostatnie zmiany w bazie…"
        if errors:
            msg += "\n\nBłędy:\n  " + "\n  ".join(errors[:12])
        QMessageBox.information(self, APP_NAME, msg)

    def import_songbook_pdf(self, path):
        """Śpiewnik PDF z wieloma pieśniami z nutami → lista do zaznaczenia (słowa + strony z nutami)."""
        import modul_slowa_z_nut as sn
        from PySide6.QtWidgets import QProgressDialog
        pd = QProgressDialog("Czytam śpiewnik…", None, 0, 100, self)
        pd.setWindowTitle(APP_NAME)
        pd.setMinimumDuration(200)

        def prog(i, n):
            pd.setValue(int(100 * i / max(n, 1)))
            QApplication.processEvents()
        try:
            coll = sn.songbook_pdf(path, prog)
        except Exception as e:
            coll = None
            QMessageBox.warning(self, APP_NAME, f"Nie udało się odczytać śpiewnika:\n{e}")
        finally:
            pd.close()
        if not coll:
            return False
        self.import_collection(coll, os.path.basename(path))
        return True

    def import_image_songbook_pdf(self, path):
        """Śpiewnik, w którym nuty są obrazkami, a tekstem tylko nagłówki (msze: Kyrie, Sanctus…)."""
        import modul_pdf_obrazy as mo
        from PySide6.QtWidgets import QProgressDialog
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ok = mo.looks_like_image_songbook(path)
        finally:
            QApplication.restoreOverrideCursor()
        if not ok:
            return False
        pd = QProgressDialog("Czytam śpiewnik (nuty są obrazkami" + (", odczyt OCR" if mo.ocr_available() else "")
                             + ")…", None, 0, 100, self)
        pd.setWindowTitle(APP_NAME)
        pd.setMinimumDuration(200)

        def prog(i, k):
            pd.setValue(int(100 * i / max(k, 1)))
            QApplication.processEvents()
        try:
            coll = mo.collection(path, prog)
        except Exception as e:
            coll = None
            QMessageBox.warning(self, APP_NAME, f"Nie udało się odczytać śpiewnika:\n{e}")
        finally:
            pd.close()
        if not coll:
            return False
        self.import_collection(coll, os.path.basename(path))
        return True

    def import_text_songbook_pdf(self, path):
        """Śpiewnik tekstowy PDF (numerowane tytuły, zwrotki, akordy) → lista pieśni do zaznaczenia."""
        import modul_pdf_tekst as pt
        from PySide6.QtWidgets import QProgressDialog
        try:
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(path)
            n = len(doc)
            doc.close()
        except Exception:
            return False
        if n < 2:
            return False
        pd = QProgressDialog("Czytam śpiewnik…", None, 0, 100, self)
        pd.setWindowTitle(APP_NAME)
        pd.setMinimumDuration(300)

        def prog(i, k):
            pd.setValue(int(100 * i / max(k, 1)))
            QApplication.processEvents()
        try:
            coll = pt.collection(path, prog)
        except Exception:
            coll = None
        finally:
            pd.close()
        if not coll or len(coll['piesni']) < 3:
            return False
        self.import_collection(coll, os.path.basename(path))
        return True

    def import_paths(self, paths):
        if len(paths) == 1 and paths[0].lower().endswith('.pdf'):
            import modul_slowa_z_nut as sn
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                book = sn.looks_like_songbook(paths[0])
            finally:
                QApplication.restoreOverrideCursor()
            if book and self.import_songbook_pdf(paths[0]):
                return
            if not book and self.import_image_songbook_pdf(paths[0]):
                return
            if not book and self.import_text_songbook_pdf(paths[0]):
                return
        if len(paths) == 1 and not paths[0].lower().endswith('.json'):
            try:
                text, hint, first = read_any(paths[0])
            except Exception as e:
                QMessageBox.critical(self, APP_NAME, f"Nie udało się odczytać pliku:\n{e}")
                return
            import modul_zbior as zb
            coll = zb.parse_collection(text, os.path.splitext(os.path.basename(paths[0]))[0])
            if coll:
                self.import_collection(coll, os.path.basename(paths[0]))
                return
            import modul_akordy as ak
            text, chords = ak.separate(text)              # akordy nad słowami → osobno (widok dla gitarzystów)
            pre = best_lyrics_range(text) if not first else None
            dlg = ImportDialog(text, hint, first, pre, self)
            if dlg.exec() and self.maybe_save():
                s = dlg.result_song()
                if chords:
                    cl = chords.splitlines()
                    if cl and fold(cl[0]) == fold(s.get('title', '')):
                        cl = cl[1:]
                    s['akordy'] = "\n".join(cl).strip("\n")
                s['zrodlo'] = os.path.basename(paths[0])
                s['config'] = dict(self.default_cfg(), numeruj=s['config']['numeruj'])
                self.new_song(ask=False, song=s)
                if self._is_score_file(paths[0]):
                    self._pending_attach = paths[0]
                    self.statusBar().showMessage("Po zapisaniu pieśni plik nut zostanie do niej dołączony.", 10000)
            return
        self.batch_import(paths)

    def batch_import(self, paths):
        cat, ok = QInputDialog.getItem(self, "Import", "Kategoria dla importowanych pieśni (można zmienić później):",
                                       [""] + DEFAULT_CATEGORIES, 0, True)
        cat = cat.strip() if ok else ""
        self.db.snapshot(f"Import {len(paths)} plików")
        ok_list, skipped, errors = [], [], []
        for p in paths:
            try:
                s = import_file_to_song(p)
                if self.db.find_by_title(s['title']):
                    skipped.append(s['title'])
                    continue
                if not p.lower().endswith('.json'):
                    s['config'] = dict(self.default_cfg(), numeruj=s['config'].get('numeruj', True))
                if cat and not s.get('kategoria'):
                    s['kategoria'] = cat
                self.db.save(s)
                if self._is_score_file(p) and s.get('id'):
                    self.convert_in_background(self.db.add_attachment(s['id'], p))
                ok_list.append(s['title'])
            except Exception as e:
                errors.append(f"{os.path.basename(p)}: {e}")
        self.pilot_invalidate()
        self.refresh_filters()
        self.refresh_list()
        msg = f"Zaimportowano: {len(ok_list)}"
        if skipped:
            msg += f"\nPominięto (już są w bazie): {len(skipped)}\n  " + "\n  ".join(skipped[:15])
        if errors:
            msg += f"\nBłędy: {len(errors)}\n  " + "\n  ".join(errors[:15])
        QMessageBox.information(self, APP_NAME, msg)

    @staticmethod
    def _is_score_file(path):
        import modul_slowa_z_nut as sn
        low = path.lower()
        if low.endswith(sn.SCORE_LYRICS_EXT):
            return True
        if low.endswith('.pdf'):
            try:
                return bool(sn.read_score_pdf(path))
            except Exception:
                return False
        return False

    def import_from_scores(self):
        last = self.settings.value("import_dir", os.path.expanduser("~"))
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Słowa z nut", last,
            "Nuty ze słowami (*.mscz *.mscx *.musicxml *.mxl *.xml *.pdf *.mid *.midi *.kar);;Wszystkie (*)")
        if not paths:
            return
        self.settings.setValue("import_dir", os.path.dirname(paths[0]))
        self.import_paths(paths)

    # --- rozpoznawanie nut ze skanu (Audiveris)
    def audiveris(self):
        import modul_omr
        return modul_omr.find_audiveris(self.settings.value("audiveris", ""))

    def set_audiveris_path(self):
        import modul_omr
        cur = self.audiveris()
        path, _ = QFileDialog.getOpenFileName(
            self, "Wskaż program Audiveris (Audiveris, Audiveris.exe, Audiveris.bat)",
            os.path.dirname(cur[0]) if cur and os.path.isabs(cur[0]) else os.path.expanduser("~"),
            "Audiveris (Audiveris* audiveris*);;Wszystkie pliki (*)")
        if path:
            self.settings.setValue("audiveris", path)
            self.settings.sync()
            self.statusBar().showMessage(f"Audiveris: {path}", 6000)
        elif not cur:
            modul_omr.install_help(self)

    def omr_from_file(self):
        if not self.ensure_saved("Aby dołączyć rozpoznane nuty"):
            return
        last = self.settings.value("attach_dir", os.path.expanduser("~"))
        path, _ = QFileDialog.getOpenFileName(self, "Skan, zdjęcie albo PDF z nutami", last,
                                              "Nuty – obraz lub PDF (*.png *.jpg *.jpeg *.tif *.tiff *.pdf);;Wszystkie (*)")
        if not path:
            return
        self.settings.setValue("attach_dir", os.path.dirname(path))
        attach_src = QMessageBox.question(self, APP_NAME, "Dołączyć do pieśni także sam skan (obok rozpoznanych nut)?") \
            == QMessageBox.Yes
        if attach_src:
            aid = self.db.add_attachment(self.song['id'], path)
            self.db.set_attachment_desc(aid, "Skan")
            self.refresh_media()
        self._run_omr(path)

    def omr_attachment(self):
        it = self.att_list.currentItem()
        if not it or not self.ensure_saved("Aby rozpoznać nuty"):
            return
        import modul_omr
        a = self.db.attachment(it.data(Qt.UserRole))
        tmp = os.path.join(modul_omr.work_dir(), os.path.basename(a['name']) or "skan.pdf")
        with open(tmp, 'wb') as f:
            f.write(a['data'])
        self._run_omr(tmp)

    def _run_omr(self, path):
        import modul_omr
        cmd = self.audiveris()
        if not cmd:
            modul_omr.install_help(self)
            return
        sheets = ""
        if path.lower().endswith('.pdf'):
            try:
                import pypdfium2 as pdfium
                doc = pdfium.PdfDocument(path)
                n = len(doc)
                doc.close()
            except Exception:
                n = 1
            if n > 1:
                txt, ok = QInputDialog.getText(self, APP_NAME, f"PDF ma {n} stron. Które rozpoznać? "
                                               "(np. 3 albo 3-4; puste = wszystkie)")
                if not ok:
                    return
                sheets = txt.strip()
        dlg = modul_omr.OmrDialog(cmd, path, sheets, "pol", self)
        got = []
        dlg.finished_ok.connect(got.extend)
        dlg.exec()
        if not got:
            if dlg.result() != QDialog.Rejected or dlg.b.text() == "Zamknij":
                QMessageBox.information(self, APP_NAME, "Nie udało się rozpoznać nut. Sprawdź dziennik w oknie Audiveris "
                                        "albo spróbuj skanu w 300 dpi.")
            return
        sid = self.song['id']
        base = os.path.splitext(os.path.basename(path))[0]
        new_ids = []
        for k, f in enumerate(got):
            with open(f, 'rb') as fh:
                data = fh.read()
            name = f"{self.song['title'] or base}" + (f" ({k + 1})" if len(got) > 1 else "") + " – rozpoznane" + \
                os.path.splitext(f)[1]
            aid = self.db.add_attachment_bytes(sid, re.sub(r'[\\/:*?"<>|]+', ' ', name), data,
                                               "Rozpoznane ze skanu (Audiveris) – do sprawdzenia")
            new_ids.append(aid)
        self.refresh_media()
        self.refresh_list()
        self.pilot_invalidate()
        cur = self.editor_song()
        msg = (f"Rozpoznane nuty dołączono do pieśni ({len(got)} plik"
               + ("i" if 1 < len(got) < 5 else "ów" if len(got) >= 5 else "") + "). "
               "Otwórz je w MuseScore, popraw błędy rozpoznania i zapisz – MuseScore zapisze .mscz, "
               "który też możesz dołączyć.")
        if not (cur.get('refren') or cur.get('zwrotki_raw')):
            if QMessageBox.question(self, APP_NAME, msg + "\n\nPieśń nie ma tekstu – wstawić słowa odczytane spod nut?") \
                    == QMessageBox.Yes:
                for i in range(self.att_list.count()):
                    if self.att_list.item(i).data(Qt.UserRole) == new_ids[0]:
                        self.att_list.setCurrentRow(i)
                        self.lyrics_from_attachment()
                        break
        else:
            QMessageBox.information(self, APP_NAME, msg)

    def lyrics_from_attachment(self):
        """Słowa spod nut z załącznika → refren i zwrotki bieżącej pieśni (po podglądzie)."""
        it = self.att_list.currentItem()
        if not it:
            return
        import tempfile
        import modul_slowa_z_nut as sn
        a = self.db.attachment(it.data(Qt.UserRole))
        tmp = os.path.join(tempfile.mkdtemp(prefix="lc_slowa_"), os.path.basename(a['name']) or "nuty")
        with open(tmp, 'wb') as f:
            f.write(a['data'])
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            song = sn.lyrics_from_file(tmp)
        except Exception as e:
            song, err = None, str(e)
        else:
            err = "To nie wygląda na nuty ze słowami (np. skan bez warstwy tekstu)."
        finally:
            QApplication.restoreOverrideCursor()
        if not song or not (song['zwrotki'] or song['refren']):
            QMessageBox.information(self, APP_NAME, f"Nie udało się odczytać słów z „{a['name']}”.\n{err}")
            return
        dlg = ImportDialog(sn.song_to_text(song), self.song.get('title') or song['title'], True, None, self)
        dlg.setWindowTitle("Słowa z nut – sprawdź i popraw")
        if not dlg.exec():
            return
        new = dlg.result_song()
        cur = self.editor_song()
        if (cur.get('refren') or cur.get('zwrotki_raw')) and QMessageBox.question(
                self, APP_NAME, "Pieśń ma już tekst. Zastąpić go słowami z nut?") != QMessageBox.Yes:
            return
        cur['refren'], cur['zwrotki_raw'] = new['refren'], new['zwrotki_raw']
        if not cur.get('title'):
            cur['title'] = new['title']
        self.load_into_editor(cur)
        self.set_dirty(True)
        self.tabs.setCurrentIndex(0)
        self.statusBar().showMessage("Wstawiono słowa z nut – sprawdź podział na wiersze i zapisz.", 8000)

    def import_json_v6(self):
        d = QFileDialog.getExistingDirectory(self, "Folder z plikami JSON z wersji 6.x")
        if d:
            paths = [os.path.join(d, f) for f in sorted(os.listdir(d))
                     if f.endswith('.json') and not f.startswith(('_last_session', 'slajdy_config'))]
            self.batch_import(paths)

    def import_url(self):
        url, ok = QInputDialog.getText(self, "Import ze strony", "Adres strony z tekstem pieśni:")
        if not ok or not url.strip():
            return
        import modul_zbior as zb
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            raw = fetch_url(url.strip())
            text, title = html_to_text(raw)
            coll_text, _ = html_to_text(zb.html_for_collection(raw))
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, f"Nie udało się pobrać strony:\n{e}")
            return
        finally:
            QApplication.restoreOverrideCursor()
        coll = zb.parse_collection(coll_text, zb.source_name(url.strip(), title)) or \
            zb.parse_collection(text, zb.source_name(url.strip(), title))
        if coll:
            self.import_collection(coll, url.strip())
            return
        dlg = ImportDialog(text, title, False, best_lyrics_range(text), self)
        if dlg.exec() and self.maybe_save():
            s = dlg.result_song()
            s['zrodlo'] = url.strip()
            s['config'] = dict(self.default_cfg(), numeruj=s['config']['numeruj'])
            self.new_song(ask=False, song=s)

    def previous_databases(self):
        """Bazy z poprzednich instalacji: foldery obok tego programu i ostatnio używane ścieżki."""
        import glob
        cur = os.path.realpath(self.db.path)
        top = os.path.dirname(APP_DIR) if os.path.basename(APP_DIR) == "program" else APP_DIR
        parent = os.path.dirname(top)
        found = _old_install_dbs() + glob.glob(os.path.join(parent, "*", "spiewnik.db")) + \
            glob.glob(os.path.join(parent, "*", "liber_canticorum.db")) + \
            glob.glob(os.path.join(parent, "*", "program", "liber_canticorum.db"))
        for org, app in (("Spiewnik", "SpiewnikSlajdy"), ("LiberCanticorum", "LiberCanticorum")):
            p = QSettings(org, app).value("db_path", "")
            if p:
                found.append(p)
        out = []
        for p in found:
            rp = os.path.realpath(p)
            if os.path.isfile(rp) and rp != cur and rp not in out:
                out.append(rp)
        return sorted(out, key=os.path.getmtime, reverse=True)

    def import_previous(self):
        if not self.maybe_save():
            return
        cands = self.previous_databases()
        labels = []
        for p in cands:
            try:
                con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
                n = con.execute("SELECT COUNT(*) FROM songs").fetchone()[0]
                con.close()
            except sqlite3.Error:
                continue
            labels.append((f"{p}   ({n} pieśni, {datetime.datetime.fromtimestamp(os.path.getmtime(p)):%Y-%m-%d %H:%M})", p))
        other = "Wskaż plik bazy (.db)…"
        choice, ok = QInputDialog.getItem(self, "Import z poprzedniej instalacji", "Znalezione bazy pieśni:",
                                          [l for l, _ in labels] + [other], 0, False)
        if not ok:
            return
        if choice == other:
            path, _ = QFileDialog.getOpenFileName(self, "Baza pieśni z poprzedniej instalacji",
                                                  os.path.dirname(APP_DIR), "Baza śpiewnika (*.db)")
            if not path:
                return
        else:
            path = dict(labels)[choice]
        box = QMessageBox(QMessageBox.Question, "Import z poprzedniej instalacji",
                          f"Baza: {path}\n\nCo zrobić?\n\n"
                          "• Dołącz pieśni – dodaje pieśni (z nutami, nagraniami i podglądami), których tu jeszcze nie ma.\n"
                          "• Zastąp bieżącą bazę – bieżąca baza zostaje zachowana jako kopia zapasowa (.bak).", parent=self)
        b_merge = box.addButton("Dołącz pieśni", QMessageBox.AcceptRole)
        b_repl = box.addButton("Zastąp bieżącą bazę", QMessageBox.DestructiveRole)
        box.addButton(QMessageBox.Cancel)
        chk = QCheckBox("Przenieś też ustawienia z poprzedniej wersji (motywy, zestaw, MuseScore, SoundFont…)")
        box.setCheckBox(chk)
        box.exec()
        clicked = box.clickedButton()
        if clicked not in (b_merge, b_repl):
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if clicked is b_merge:
                self.db.snapshot(f"Dołączenie pieśni z innej bazy: {os.path.basename(path)}")
                added, skipped, n_att = self.db.merge_from(
                    path, lambda k, n: (self.statusBar().showMessage(f"Import: {k + 1}/{n}"), QApplication.processEvents()))
                msg = (f"Dodano pieśni: {len(added)}.\nDołączono nut i nagrań: {n_att}.\n"
                       f"Pieśni, które już były (uzupełnione o brakujące nuty i pola): {len(skipped)}.")
                if skipped:
                    msg += "\n  " + "\n  ".join(skipped[:12]) + ("\n  …" if len(skipped) > 12 else "")
            else:
                import shutil
                target = self.db.path
                backup = f"{target}.bak-{datetime.datetime.now():%Y%m%d-%H%M%S}"
                self.db.con.close()
                if os.path.exists(target):
                    shutil.copy2(target, backup)
                shutil.copy2(path, target)
                self.db = SongDB(target)                    # migracja kolumn starszych baz przy otwarciu
                msg = f"Bieżąca baza zastąpiona bazą:\n{path}\n\nKopia zapasowa poprzedniej:\n{backup}"
            if chk.isChecked():
                msg += "\n\n" + self.import_old_settings()
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, APP_NAME, f"Import nie powiódł się:\n{e}")
            return
        QApplication.restoreOverrideCursor()
        self.pilot_invalidate()
        self.refresh_filters()
        self.refresh_list()
        self.restore_set()
        self.new_song(ask=False)
        QMessageBox.information(self, "Import z poprzedniej instalacji", msg)

    def import_old_settings(self):
        """Kopiuje ustawienia z wersji „Śpiewnik – slajdy” (7.x) – bez ścieżki bazy."""
        old = QSettings("Spiewnik", "SpiewnikSlajdy")
        keys = [k for k in old.allKeys() if k not in ("db_path",)]
        for k in keys:
            self.settings.setValue(k, old.value(k))
        self.settings.sync()
        return (f"Przeniesiono ustawień: {len(keys)}. Część (motywy ikon, pasek narzędzi) zadziała po ponownym "
                "uruchomieniu programu.") if keys else "Nie znaleziono ustawień z poprzedniej wersji."

    def choose_db(self):
        if not self.maybe_save():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Baza pieśni", os.path.dirname(self.db.path),
                                              "Baza śpiewnika (*.db)", options=QFileDialog.DontConfirmOverwrite)
        if path:
            self.settings.setValue("db_path", path)
            self.db = SongDB(path)
            self.statusBar().showMessage(f"Baza: {path}")
            self.refresh_filters()
            self.refresh_list()
            self.restore_set()
            self.new_song(ask=False)

    def closeEvent(self, e):
        if not self.maybe_save():
            e.ignore()
            return
        for w in [self.present, self.yt_player] + list(self.midi_dialogs):
            if w:
                w.close()
        if self.pilot:
            self.pilot.stop()
        try:
            self.settings.sync()
        except Exception:
            pass
        e.accept()


def migrate_settings():
    """Ustawienia z wcześniejszych wersji („Śpiewnik – slajdy”) przechodzą do Liber Canticorum."""
    new = QSettings("LiberCanticorum", "LiberCanticorum")
    if new.allKeys():
        return
    old = QSettings("Spiewnik", "SpiewnikSlajdy")
    for k in old.allKeys():
        new.setValue(k, old.value(k))
    new.sync()


def _old_install_dbs():
    """Bazy z wcześniejszych wersji w folderach obok (układ stary: baza w folderze głównym,
    nowy od 9.1: w podfolderze „program”)."""
    import glob
    top = os.path.dirname(APP_DIR) if os.path.basename(APP_DIR) == "program" else APP_DIR
    parent = os.path.dirname(top)
    out = []
    for pat in ("Spiewnik_slajdy*", "LiberCanticorum*"):
        for d in glob.glob(os.path.join(parent, pat)):
            if os.path.realpath(d) == os.path.realpath(top):
                continue
            for f in ("spiewnik.db", "liber_canticorum.db", os.path.join("program", "liber_canticorum.db")):
                if os.path.isfile(os.path.join(d, f)):
                    out.append(os.path.join(d, f))
    return out


def default_db_path():
    """Baza pieśni: wskazana w ustawieniach, obok programu, albo przejęta z wcześniejszej wersji."""
    import glob
    import shutil
    s = QSettings("LiberCanticorum", "LiberCanticorum")
    p = s.value("db_path", "")
    if p and os.path.exists(p):
        return p
    base = APP_DIR if os.access(APP_DIR, os.W_OK) else os.path.expanduser("~")
    target = os.path.join(base, "liber_canticorum.db")
    if os.path.exists(target):
        return target
    if os.path.exists(os.path.join(base, "spiewnik.db")):          # program rozpakowany w starym folderze
        return os.path.join(base, "spiewnik.db")
    old = sorted(_old_install_dbs(), key=os.path.getmtime, reverse=True)      # stare wersje obok
    if old:
        shutil.copy2(old[0], target)                                 # kopia – stara baza zostaje nietknięta
        s.setValue("migrated_from", old[0])
    return target


def app_icon():
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        path = os.path.join(APP_DIR, "ikony", f"liber_canticorum_{size}.png")
        if os.path.exists(path):
            icon.addFile(path, QSize(size, size))
    return icon


def main():
    if APP_DIR not in sys.path:
        sys.path.insert(0, APP_DIR)            # moduły modul_nuty / modul_youtube obok programu
    if sys.platform == "win32":                # własna ikona na pasku zadań Windows
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LiberCanticorum.LiberCanticorum")
        except Exception:
            pass
    try:                                       # pozwala później (po sprawdzeniu) wczytać wbudowaną przeglądarkę
        from PySide6.QtCore import QCoreApplication
        QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("LiberCanticorum")
    app.setWindowIcon(app_icon())
    try:
        import modul_widoki
        modul_widoki.apply_theme(app, QSettings("LiberCanticorum", "LiberCanticorum").value("pergamin", True, type=bool))
    except Exception:
        pass
    migrate_settings()
    load_mass_parts()
    try:                                                   # język interfejsu (pliki i18n/*.json)
        import modul_i18n
        lang = QSettings("LiberCanticorum", "LiberCanticorum").value("language", "") or modul_i18n.system_language()
        modul_i18n.load(lang)
        modul_i18n.install(app)
    except Exception as e:
        print("Tłumaczenia:", e)
    w = MainWindow(default_db_path())
    w.show()
    mig = QSettings("LiberCanticorum", "LiberCanticorum").value("migrated_from", "")
    if mig and not QSettings("LiberCanticorum", "LiberCanticorum").value("migrated_info_shown", False, type=bool):
        QSettings("LiberCanticorum", "LiberCanticorum").setValue("migrated_info_shown", True)
        w.statusBar().showMessage(f"Przejęto bazę pieśni z wcześniejszej wersji: {mig} (kopia – oryginał nietknięty).", 15000)
    code = app.exec()
    # Zakończenie bez sprzątania obiektów Qt przez Pythona: PySide6 + Python 3.14 potrafi przy tym
    # paść (SIGBUS w ~QObject przy destroyQCoreApplication). Dane są już zapisane – zamykamy bazę
    # i ustawienia, a potem kończymy proces od razu.
    try:
        w.db.con.commit()
        w.db.con.close()
    except Exception:
        pass
    try:
        QSettings("LiberCanticorum", "LiberCanticorum").sync()
        from PySide6.QtCore import QThreadPool
        QThreadPool.globalInstance().waitForDone(3000)
    except Exception:
        pass
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


if __name__ == "__main__":
    main()
