# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Autorzy projektu Liber Canticorum
"""
Moduł nut dla programu Liber Canticorum.

1. ScoreSearchDialog – wyszukiwanie nut:
   * CPDL (Choral Public Domain Library) – wyszukiwanie w programie, lista plików (PDF, MIDI,
     MusicXML, MuseScore) i pobranie ich jako załączników pieśni,
   * MuseScore.com, IMSLP, Google – wyszukiwanie w przeglądarce (te serwisy nie udostępniają
     otwartego API; pobrany plik dołączasz przyciskiem „Dodaj pliki…”).
2. MidiPlayerDialog – odtwarzacz MIDI do nauki głosów (np. czterogłos SATB):
   wyciszanie głosów, ćwiczenie jednego głosu (pozostałe ciszej), tempo, transpozycja,
   rozdzielanie akordów na głosy, wałek pianoli z kursorem, zapis do WAV.

Zależności: mido, numpy; odtwarzanie dźwięku: sounddevice (bez niego – zapis WAV i odtworzenie
w systemowym odtwarzaczu).
"""
import html
import io
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
import zipfile
from dataclasses import dataclass, field

from PySide6.QtCore import Qt, QElapsedTimer, QFileSystemWatcher, QRectF, QTimer, QUrl, Signal, QPointF
from PySide6.QtGui import (QColor, QDesktopServices, QFont, QImage, QKeySequence, QPainter, QPen, QPixmap,
                           QShortcut)
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QScrollArea, QTabWidget, QSlider, QSpinBox, QVBoxLayout, QWidget,
                               QApplication)

USER_AGENT = "LiberCanticorum/0.12.1 (program parafialny; GPL)"
BROWSER_HEADERS = {
    'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 LiberCanticorum/0.12.1",
    'Accept': "application/json,text/html;q=0.9,*/*;q=0.8", 'Accept-Language': "pl,en;q=0.8",
}
VOICE_COLORS = ['#e05656', '#e0a030', '#4caf50', '#3f7fd9', '#a05ad9', '#30b0b0', '#c0c040', '#d070a0']
SATB = ["Sopran", "Alt", "Tenor", "Bas"]
SCORE_EXT = ('.mscz', '.mscx', '.musicxml', '.mxl', '.xml')           # MuseScore otwiera i przelicza
VIEW_EXT = ('.pdf', '.png', '.jpg', '.jpeg') + SCORE_EXT
DOWNLOAD_EXT = ('.pdf', '.mid', '.midi', '.kar') + SCORE_EXT


# =====================================================================
# MuseScore: wyszukanie programu, konwersja do PDF / MIDI, miniatura
# =====================================================================

APPIMAGE_DIRS = ["~/Applications", "~/Aplikacje", "~/Programy", "~/Programs", "~/AppImages", "~/bin", "~/.local/bin",
                 "~/Pobrane", "~/Downloads", "~/Pulpit", "~/Desktop", "~/Dokumenty", "~/Documents", "~", "/opt",
                 "/opt/appimages", "/usr/local/bin"]


def _version_key(path):
    nums = re.findall(r'\d+', os.path.basename(path))
    return [int(n) for n in nums[:4]] + [os.path.getmtime(path) if os.path.exists(path) else 0]


def find_appimages():
    """Pliki MuseScore*.AppImage w typowych miejscach (najnowsza wersja pierwsza)."""
    import glob
    found = []
    for d in APPIMAGE_DIRS:
        for pat in ("MuseScore*.AppImage", "MuseScore*.appimage", "musescore*.AppImage", "mscore*.AppImage"):
            found += glob.glob(os.path.join(os.path.expanduser(d), pat))
    found = sorted(set(os.path.realpath(f) for f in found if os.path.isfile(f)), key=_version_key, reverse=True)
    return found


def ensure_executable(path):
    """AppImage pobrany z sieci zwykle nie ma prawa do uruchamiania – nadaj je (chmod u+x)."""
    import stat
    if not path or path.startswith('flatpak:') or not os.path.isfile(path) or os.access(path, os.X_OK):
        return True
    try:
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return True
    except OSError:
        return False


def find_musescore(custom=""):
    """Ścieżka do MuseScore (4 lub 3, także AppImage i Flatpak) albo None."""
    import glob
    import shutil
    if custom and (os.path.exists(custom) or shutil.which(custom) or custom.startswith('flatpak:')):
        return custom
    for name in ('MuseScore4', 'mscore4portable', 'musescore4', 'mscore', 'MuseScore3', 'mscore3', 'musescore3', 'musescore'):
        path = shutil.which(name)
        if path:
            return path
    apps = find_appimages()
    if apps:
        return apps[0]
    pats = []
    for pf in (os.environ.get('ProgramFiles'), os.environ.get('ProgramFiles(x86)'), os.environ.get('LOCALAPPDATA')):
        if pf:
            pats += [os.path.join(pf, 'MuseScore*', 'bin', 'MuseScore*.exe'), os.path.join(pf, 'Programs', 'MuseScore*', 'bin', 'MuseScore*.exe')]
    pats += ['/Applications/MuseScore*.app/Contents/MacOS/mscore']
    for pat in pats:
        found = sorted(glob.glob(pat), reverse=True)
        if found:
            return found[0]
    if shutil.which('flatpak') and any(os.path.isdir(d) for d in ('/var/lib/flatpak/app/org.musescore.MuseScore',
                                                                  os.path.expanduser('~/.local/share/flatpak/app/org.musescore.MuseScore'))):
        return 'flatpak:org.musescore.MuseScore'
    return None


_APPIMAGE_NOFUSE = set()          # AppImage, które działają tylko w trybie bez FUSE
_MS_MODE = {}                     # exe -> (bez_FUSE, offscreen) – wariant, który ostatnio zadziałał
LAST_LOG = []                     # dziennik ostatnich uruchomień MuseScore (do diagnostyki)


def _log(line):
    LAST_LOG.append(line)
    del LAST_LOG[:-60]


def last_log_text():
    return "\n".join(LAST_LOG[-40:])


def _ms_command(exe, args, folder=None):
    if exe.startswith('flatpak:'):
        return ['flatpak', 'run'] + ([f'--filesystem={folder}'] if folder else []) + [exe.split(':', 1)[1]] + args
    return [exe] + args


def _run_once(cmd, env, timeout, expect=None):
    """Jedno uruchomienie. Wyjście idzie do pliku (nie do potoku) – MuseScore 4 zostawia w tle proces
    obsługi awarii, który trzymałby potok otwarty. Gdy oczekiwany plik już powstał i przestał rosnąć,
    nie czekamy na zakończenie programu dłużej niż kilka sekund."""
    import subprocess
    import sys
    t0 = time.time()
    with tempfile.TemporaryFile() as out:
        kw = {'creationflags': 0x08000000} if sys.platform == 'win32' else {'start_new_session': True}
        try:
            proc = subprocess.Popen(cmd, env=env, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **kw)
        except OSError as e:
            _log(f"$ {' '.join(cmd)}\n  BŁĄD uruchomienia: {e}")
            return None, str(e), False
        last_size, stable_since, ready = -1, None, False
        while True:
            rc = proc.poll()
            if rc is not None:
                break
            if expect and os.path.exists(expect):
                size = os.path.getsize(expect)
                if size > 0 and size == last_size:
                    stable_since = stable_since or time.time()
                    if time.time() - stable_since > 4:        # plik gotowy, a program nie kończy pracy
                        ready = True
                        break
                else:
                    stable_since = None
                last_size = size
            if time.time() - t0 > timeout:
                break
            time.sleep(0.25)
        if proc.poll() is None:                              # zakończ (razem z procesami potomnymi)
            try:
                if sys.platform == 'win32':
                    proc.kill()
                else:
                    import signal
                    os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        out.seek(0)
        text = out.read()[-4000:].decode('utf-8', 'replace')
    rc = proc.returncode
    ok = (expect is not None and os.path.exists(expect) and os.path.getsize(expect) > 0) or (expect is None and rc == 0)
    _log(f"$ {' '.join(cmd)}\n  kod: {rc}{' (zatrzymany po zapisaniu pliku)' if ready else ''}"
         f"{' (przekroczony czas)' if time.time() - t0 > timeout else ''}, {time.time() - t0:.1f} s, "
         f"{'OK' if ok else 'BRAK WYNIKU'}\n  " + "\n  ".join(text.strip().splitlines()[-8:]))
    return rc, text, ok


def run_musescore(exe, args, timeout=180, folder=None, expect=None):
    """Uruchamia MuseScore w linii poleceń, próbując po kolei wariantów:
    zwykły / bez FUSE (AppImage na Ubuntu 24.04, Mint 22) / bez okien (QT_QPA_PLATFORM=offscreen).
    Zapamiętuje wariant, który zadziałał. Zwraca (powodzenie, tekst wyjścia)."""
    import sys
    ensure_executable(exe)
    base = dict(os.environ)
    headless = sys.platform.startswith('linux') and not (base.get('DISPLAY') or base.get('WAYLAND_DISPLAY'))
    is_appimage = exe.lower().endswith('.appimage')
    variants = [(False, headless)]
    if sys.platform.startswith('linux') and not headless:
        variants.append((False, True))
    if is_appimage:
        variants += [(True, v[1]) for v in list(variants)]
    if exe in _MS_MODE:
        variants.remove(_MS_MODE[exe]) if _MS_MODE[exe] in variants else None
        variants.insert(0, _MS_MODE[exe])
    text = ""
    for nofuse, offscreen in variants:
        env = dict(base)
        if nofuse:
            env['APPIMAGE_EXTRACT_AND_RUN'] = '1'
        if offscreen:
            env['QT_QPA_PLATFORM'] = 'offscreen'
        rc, text, ok = _run_once(_ms_command(exe, args, folder), env, timeout, expect)
        if ok:
            _MS_MODE[exe] = (nofuse, offscreen)
            if nofuse:
                _APPIMAGE_NOFUSE.add(exe)
            return True, text
        if rc is None and not is_appimage:
            break                                            # programu w ogóle nie da się uruchomić
    return False, text


def musescore_version(exe):
    """Wersja MuseScore (np. 'MuseScore4 4.4.4') albo None, gdy programu nie da się uruchomić."""
    ok, out = run_musescore(exe, ['--version'], timeout=90)
    if ok:
        lines = [l for l in out.strip().splitlines() if 'musescore' in l.lower() or re.search(r'\d+\.\d+', l)]
        return (lines or ["MuseScore"])[-1].strip()
    return None


def open_in_musescore(exe, path):
    """Otwiera plik w MuseScore (do edycji) – także gdy to AppImage nieskojarzony z .mscz."""
    import subprocess
    ensure_executable(exe)
    env = dict(os.environ)
    if exe in _APPIMAGE_NOFUSE:
        env['APPIMAGE_EXTRACT_AND_RUN'] = '1'
    env.pop('QT_QPA_PLATFORM', None)                         # tu chcemy zwykłe okno MuseScore
    try:
        subprocess.Popen(_ms_command(exe, [path], os.path.dirname(path)), env=env, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


def convert_score(exe, name, data, outs=('pdf', 'mid', 'spos'), timeout=180):
    """Konwersja pliku MuseScore / MusicXML przez MuseScore (linia poleceń).
    Zwraca {'pdf': bajty, 'mid': bajty, 'spos': bajty} – spos to pozycje nut na stronach (do kursora)."""
    ext = os.path.splitext(name)[1].lower() or '.mscz'
    result = {}
    with tempfile.TemporaryDirectory(prefix="spiewnik_ms_") as tmp:
        src = os.path.join(tmp, "nuty" + ext)
        with open(src, 'wb') as f:
            f.write(data)
        for out in outs:
            dst = os.path.join(tmp, "wynik." + out)
            run_musescore(exe, ['-o', dst, src], timeout=timeout, folder=tmp, expect=dst)
            if os.path.exists(dst) and os.path.getsize(dst) > 0:
                with open(dst, 'rb') as f:
                    result[out] = f.read()
    return result


TEST_XML = ('<?xml version="1.0" encoding="UTF-8"?><score-partwise version="3.1"><work><work-title>Test</work-title></work>'
            '<part-list><score-part id="P1"><part-name>Sopran</part-name></score-part></part-list><part id="P1">'
            '<measure number="1"><attributes><divisions>1</divisions><time><beats>4</beats><beat-type>4</beat-type></time>'
            '<clef><sign>G</sign><line>2</line></clef></attributes>'
            + "".join(f'<note><pitch><step>{s}</step><octave>4</octave></pitch><duration>1</duration><type>quarter</type>'
                      f'<lyric><text>{t}</text></lyric></note>' for s, t in zip("CDEF", ("Al", "le", "lu", "ja")))
            + '</measure></part></score-partwise>')


def test_musescore(exe):
    """Próbna konwersja krótkiego utworu: zwraca (raport tekstowy, czy_wszystko_ok)."""
    import platform
    LAST_LOG.clear()
    t0 = time.time()
    ver = musescore_version(exe)
    res = convert_score(exe, "test.musicxml", TEST_XML.encode("utf-8"), timeout=240)
    lines = [f"System: {platform.platform()}", f"MuseScore: {exe}", f"Wersja: {ver or '(nie odpowiada na --version)'}",
             f"Tryb: {'bez FUSE' if exe in _APPIMAGE_NOFUSE else 'zwykły'}"
             f"{', bez okien (offscreen)' if _MS_MODE.get(exe, (0, 0))[1] else ''}",
             f"PDF: {'OK' if res.get('pdf') else 'BRAK'}   MIDI: {'OK' if res.get('mid') else 'BRAK'}   "
             f"pozycje nut (.spos): {'OK' if res.get('spos') else 'BRAK'}", f"Czas: {time.time() - t0:.1f} s",
             "", "Dziennik:", last_log_text()]
    return "\n".join(lines), bool(res.get('pdf') and res.get('mid'))


def mscz_thumbnail(data):
    """Miniatura pierwszej strony zapisana przez MuseScore w pliku .mscz (PNG) albo None."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for n in z.namelist():
                if n.lower().startswith('thumbnails/') and n.lower().endswith('.png'):
                    return z.read(n)
    except zipfile.BadZipFile:
        pass
    return None


def score_info(name, data):
    """Tytuł, kompozytor i nazwy partii z pliku MuseScore (bez MuseScore)."""
    import xml.etree.ElementTree as ET
    xml = None
    low = name.lower()
    try:
        if low.endswith('.mscz'):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                inner = [n for n in z.namelist() if n.lower().endswith('.mscx')]
                xml = z.read(inner[0]) if inner else None
        elif low.endswith('.mscx'):
            xml = data
        if not xml:
            return {}
        root = ET.fromstring(xml)
        meta = {m.get('name'): (m.text or '').strip() for m in root.iter('metaTag')}
        parts = [(p.findtext('trackName') or p.findtext('Instrument/longName') or '').strip() for p in root.iter('Part')]
        return {'title': meta.get('workTitle', ''), 'composer': meta.get('composer', ''),
                'parts': [x for x in parts if x]}
    except (ET.ParseError, zipfile.BadZipFile, KeyError, IndexError):
        return {}


def _icons(widget):
    try:
        import ikony
        ikony.apply_icons(widget)
    except ImportError:
        pass


def _icon(name):
    try:
        import ikony
        return ikony.fa_icon(name)
    except ImportError:
        from PySide6.QtGui import QIcon
        return QIcon()


def is_pdf(data):
    return bool(data) and data[:5] == b'%PDF-'


# =====================================================================
# Wyszukiwanie nut
# =====================================================================

_WEB_PROFILE = None


def webengine_available():
    """Czy jest wbudowana przeglądarka (QtWebEngine z PySide6-Addons)."""
    try:
        import importlib.util
        return importlib.util.find_spec("PySide6.QtWebEngineWidgets") is not None
    except Exception:
        return False


def web_search_urls(q):
    e = urllib.parse.quote_plus
    return {
        'MuseScore': f"https://musescore.com/sheetmusic?text={e(q)}",
        'IMSLP': f"https://imslp.org/index.php?title=Special:Search&search={e(q)}",
        'CPDL (strona)': f"https://www.cpdl.org/wiki/index.php?search={e(q)}",
        'Google: nuty PDF / MIDI': f"https://www.google.com/search?q={e(q + ' nuty pdf midi')}",
    }


CPDL_API = "https://www.cpdl.org/wiki/api.php"


class Blocked(Exception):
    """Serwis odrzuca zapytania z programów (np. ochrona przed botami)."""


def _get_json(url, params, timeout=20):
    full = url + "?" + urllib.parse.urlencode(dict(params, format='json'))
    req = urllib.request.Request(full, headers=BROWSER_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 429, 503):
            raise Blocked(f"HTTP {e.code}")
        raise
    try:
        return json.loads(body.decode('utf-8'))
    except ValueError:
        raise Blocked("serwer zwrócił stronę zamiast danych (ochrona przed botami)")


def cpdl_search(query, limit=25):
    """[(tytuł strony, fragment)] – MediaWiki API (list=search)."""
    d = _get_json(CPDL_API, {'action': 'query', 'list': 'search', 'srsearch': query, 'srlimit': limit,
                             'srprop': 'snippet'})
    out = []
    for r in d.get('query', {}).get('search', []):
        snippet = r.get('snippet', '')
        for tag in ('<span class="searchmatch">', '</span>'):
            snippet = snippet.replace(tag, '')
        out.append((r['title'], snippet))
    return out


def cpdl_files(page_title):
    """Pliki podpięte do strony utworu w CPDL: [(nazwa, url)]."""
    d = _get_json(CPDL_API, {'action': 'query', 'generator': 'images', 'titles': page_title, 'gimlimit': 100,
                             'prop': 'imageinfo', 'iiprop': 'url'})
    files = []
    for p in d.get('query', {}).get('pages', {}).values():
        info = (p.get('imageinfo') or [{}])[0]
        name = p.get('title', '').split(':', 1)[-1]
        if info.get('url') and os.path.splitext(name)[1].lower() in DOWNLOAD_EXT + ('.mp3', '.ly'):
            files.append((name, info['url']))
    return sorted(files)


def download(url, limit=60 * 1024 * 1024):
    """Pobiera plik; zwraca (bajty, typ zawartości, nazwa z nagłówka lub None)."""
    req = urllib.request.Request(url, headers=BROWSER_HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read(limit + 1)
        ctype = r.headers.get_content_type()
        disp = r.headers.get('Content-Disposition', '')
    if len(data) > limit:
        raise RuntimeError("Plik jest za duży (ponad 60 MB).")
    m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", disp)
    return data, ctype, (urllib.parse.unquote(m.group(1)) if m else None)


def downloads_dir():
    from PySide6.QtCore import QStandardPaths
    d = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
    return d if d and os.path.isdir(d) else os.path.expanduser("~")


class ScoreSearchDialog(QDialog):
    """Okno NIEMODALNE: można w nim szukać, a jednocześnie pracować w programie.
    Pobrane w przeglądarce pliki z nutami pojawiają się tu same (folder Pobrane);
    można je też przeciągnąć do okna albo wskazać przyciskiem."""
    files_downloaded = Signal(list)          # [(nazwa, bajty)]

    def __init__(self, query, settings=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Szukaj i dołącz nuty")
        self.setModal(False)
        self.setAcceptDrops(True)
        self.resize(1000, 820)
        self.opened_at = time.time() - 5
        self.dl_dir = downloads_dir()
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        query = re.sub(r"\s+[–—-]\s+", " ", query or "")      # „Msza Rycerska – Kyrie” → „Msza Rycerska Kyrie”
        self.q = QLineEdit(query)
        self.q.setPlaceholderText("Tytuł pieśni")
        self.q.returnPressed.connect(self.search_musescore)
        row.addWidget(QLabel("Tytuł:"))
        row.addWidget(self.q, 1)
        b = QPushButton("🔎 Szukaj w MuseScore")
        b.setDefault(True)
        b.clicked.connect(self.search_musescore)
        row.addWidget(b)
        lay.addLayout(row)

        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 5)
        # --- MuseScore (najważniejsze)
        ms = QWidget()
        ml = QVBoxLayout(ms)
        ml.setContentsMargins(0, 4, 0, 0)
        self.web = None
        if webengine_available():
            self._build_web(ml)
        else:
            steps = QLabel(
                "<b>Jak to działa:</b><ol>"
                "<li>Kliknij <b>„Szukaj w MuseScore”</b> – otworzy się przeglądarka z wynikami dla tytułu.</li>"
                "<li>Wybierz nuty: <i>melodia</i> (melody, lead sheet, „śpiew”), <i>chór</i> (SATB, choir), "
                "<i>organy / fortepian</i> (organ, piano).</li>"
                "<li>Kliknij <b>Download</b> i wybierz <b>PDF</b> albo <b>MuseScore</b> (.mscz – da się z niego "
                "zrobić MIDI i odczytać słowa). Pobieranie wymaga darmowego konta w MuseScore.</li>"
                "<li>Pobrany plik pojawi się poniżej na liście sam – kliknij <b>„Dołącz zaznaczone do pieśni”</b>.</li>"
                "</ol>", wordWrap=True)
            ml.addWidget(steps)
            inst = QPushButton("Wygodniej: otwieraj MuseScore w oknie programu (jednorazowo pobierze ok. 150 MB)…")
            inst.clicked.connect(self.install_webengine)
            ml.addWidget(inst)
            ml.addStretch(1)
        self.tabs.addTab(ms, "MuseScore")
        # --- inne źródła
        other = QWidget()
        ol = QVBoxLayout(other)
        ol.addWidget(QLabel("<b>CPDL</b> – darmowe nuty chóralne (głównie dawna muzyka, łacina). Szuka się tu bez "
                            "przeglądarki: wybierz utwór, potem plik, i „Pobierz z CPDL i dołącz”.<br>"
                            "<b>IMSLP</b> – nuty klasyczne w domenie publicznej. <b>Google</b> – wszystko inne "
                            "(PDF, MIDI ze stron parafii, chórów).", wordWrap=True))
        web = QHBoxLayout()
        b = QPushButton("Szukaj w CPDL")
        b.clicked.connect(self.search_cpdl)
        web.addWidget(b)
        for name in ('IMSLP', 'Google: nuty PDF / MIDI'):
            bb = QPushButton(name)
            bb.clicked.connect(lambda _=False, n=name: self.open_web(n))
            web.addWidget(bb)
        web.addStretch()
        ol.addLayout(web)
        self.results = QListWidget()
        self.results.currentItemChanged.connect(self.load_files)
        self.results.itemDoubleClicked.connect(self.open_page)
        ol.addWidget(self.results, 1)
        self.files = QListWidget()
        self.files.setSelectionMode(QListWidget.ExtendedSelection)
        ol.addWidget(self.files, 1)
        bb = QHBoxLayout()
        self.b_page = QPushButton("Otwórz stronę utworu")
        self.b_page.clicked.connect(lambda: self.open_page(self.results.currentItem()))
        self.b_get = QPushButton("Pobierz z CPDL i dołącz")
        self.b_get.clicked.connect(self.download_selected)
        bb.addWidget(self.b_page)
        bb.addStretch()
        bb.addWidget(self.b_get)
        ol.addLayout(bb)
        self.tabs.addTab(other, "Inne źródła")

        # --- pobrane pliki (tu trafiają nuty z przeglądarki)
        box = QLabel(f"<b>Pobrane pliki</b> – nuty zapisane w folderze <i>{self.dl_dir}</i> pojawią się tu same. "
                     "Możesz też <b>przeciągnąć plik do tego okna</b>.", wordWrap=True)
        lay.addWidget(box)
        self.local = QListWidget()
        self.local.setSelectionMode(QListWidget.ExtendedSelection)
        self.local.setMinimumHeight(80)
        lay.addWidget(self.local, 1)
        lrow = QHBoxLayout()
        b_att = QPushButton("Dołącz zaznaczone do pieśni")
        b_att.clicked.connect(self.attach_local)
        b_pick = QPushButton("Wskaż plik…")
        b_pick.clicked.connect(self.pick_files)
        b_all = QPushButton("Pokaż też starsze pobrane")
        b_all.clicked.connect(lambda: self.scan_downloads(all_recent=True))
        close = QPushButton("Zamknij")
        close.clicked.connect(self.close)
        lrow.addWidget(b_att)
        lrow.addWidget(b_pick)
        lrow.addWidget(b_all)
        lrow.addStretch()
        lrow.addWidget(close)
        lay.addLayout(lrow)
        self.status = QLabel(wordWrap=True)
        lay.addWidget(self.status)
        lay.setStretchFactor(self.tabs, 5 if self.web is not None else 2)
        if self.web is not None and query:
            QTimer.singleShot(100, self.search_musescore)

        _icons(self)
        self.watcher = QFileSystemWatcher([self.dl_dir], self)
        self.watcher.directoryChanged.connect(lambda _: QTimer.singleShot(800, self.scan_downloads))
        self.poll = QTimer(self, interval=3000, timeout=self.scan_downloads)     # zapas, gdy watcher milczy
        self.poll.start()
        self.scan_downloads()

    # --- pliki lokalne
    def scan_downloads(self, all_recent=False):
        since = time.time() - 7 * 86400 if all_recent else self.opened_at
        have = {self.local.item(i).data(Qt.UserRole) for i in range(self.local.count())}
        try:
            names = os.listdir(self.dl_dir)
        except OSError:
            return
        found = []
        for n in names:
            path = os.path.join(self.dl_dir, n)
            low = n.lower()
            if path in have or not low.endswith(DOWNLOAD_EXT) or low.endswith(('.crdownload', '.part', '.tmp')):
                continue
            try:
                st = os.stat(path)
            except OSError:
                continue
            if st.st_mtime >= since and st.st_size > 0:
                found.append((st.st_mtime, path))
        for _, path in sorted(found, reverse=True):
            self.add_local(path, select=True)
        if found:
            self.status.setText(f"Nowe pliki w Pobranych: {len(found)} – zaznacz i kliknij „Dołącz zaznaczone do pieśni”.")

    def add_local(self, path, select=False):
        for i in range(self.local.count()):
            if self.local.item(i).data(Qt.UserRole) == path:
                return
        it = QListWidgetItem(f"{os.path.basename(path)}   ({os.path.getsize(path) // 1024 + 1} KB)")
        it.setData(Qt.UserRole, path)
        self.local.insertItem(0, it)
        it.setSelected(select)

    def pick_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Wskaż pliki z nutami", self.dl_dir,
                                                "Nuty (" + " ".join("*" + e for e in DOWNLOAD_EXT) + ");;Wszystkie pliki (*)")
        for p in paths:
            self.add_local(p, select=True)
        if paths:
            self.attach_local()

    def attach_local(self):
        items = self.local.selectedItems() or ([self.local.item(0)] if self.local.count() == 1 else [])
        if not items:
            self.status.setText("Zaznacz pliki na liście „Pobrane w przeglądarce”.")
            return
        got = []
        for it in items:
            path = it.data(Qt.UserRole)
            try:
                with open(path, 'rb') as f:
                    got.append((os.path.basename(path), f.read()))
            except OSError as e:
                self.status.setText(f"Nie można odczytać {path}: {e}")
        if got:
            self.files_downloaded.emit(got)
            for it in items:
                it.setText("✓ " + it.text().lstrip("✓ "))
            self.status.setText(f"Dołączono: {', '.join(n for n, _ in got)}")

    # --- przeciągnij i upuść
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        got = []
        for url in e.mimeData().urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                if os.path.isfile(path):
                    with open(path, 'rb') as f:
                        got.append((os.path.basename(path), f.read()))
            elif url.scheme() in ('http', 'https'):
                try:
                    QApplication.setOverrideCursor(Qt.WaitCursor)
                    data, ctype, fname = download(url.toString())
                finally:
                    QApplication.restoreOverrideCursor()
                if ctype == 'text/html':
                    self.status.setText("To link do strony, a nie do pliku. Pobierz plik w przeglądarce – pojawi się na liście sam.")
                    continue
                got.append((fname or os.path.basename(urllib.parse.urlparse(url.toString()).path) or "nuty", data))
        if got:
            self.files_downloaded.emit(got)
            self.status.setText(f"Dołączono: {', '.join(n for n, _ in got)}")
        e.acceptProposedAction()

    # --- MuseScore
    def _build_web(self, lay):
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
        from PySide6.QtCore import QStandardPaths
        nav = QHBoxLayout()
        self.web = QWebEngineView(self)
        root = os.path.join(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or
                            os.path.expanduser("~/.local/share/LiberCanticorum"), "przegladarka")
        os.makedirs(root, exist_ok=True)
        global _WEB_PROFILE
        if _WEB_PROFILE is None:            # jeden profil na cały program – logowanie w MuseScore zostaje
            _WEB_PROFILE = QWebEngineProfile("LiberCanticorum", QApplication.instance())
            _WEB_PROFILE.setPersistentStoragePath(root)
            _WEB_PROFILE.setCachePath(os.path.join(root, "cache"))
            _WEB_PROFILE.setDownloadPath(tempfile.mkdtemp(prefix="lc_nuty_"))
        self.web.setPage(QWebEnginePage(_WEB_PROFILE, self.web))
        _WEB_PROFILE.downloadRequested.connect(self._web_download)
        for txt, fn in (("◀", self.web.back), ("▶", self.web.forward), ("⟳", self.web.reload)):
            b = QPushButton(txt)
            b.setFixedWidth(36)
            b.clicked.connect(fn)
            nav.addWidget(b)
        self.addr = QLabel()
        self.addr.setStyleSheet("color: gray;")
        nav.addWidget(self.addr, 1)
        b = QPushButton("Otwórz w zwykłej przeglądarce")
        b.clicked.connect(lambda: QDesktopServices.openUrl(self.web.url()))
        nav.addWidget(b)
        lay.addLayout(nav)
        lay.addWidget(self.web, 1)
        hint = QLabel("Wybierz nuty i kliknij <b>Download</b> (PDF albo MuseScore) – plik od razu trafi do pieśni. "
                      "Pobieranie wymaga darmowego konta w MuseScore; zalogujesz się raz, program to zapamięta.",
                      wordWrap=True)
        lay.addWidget(hint)
        self.web.urlChanged.connect(lambda u: self.addr.setText(u.toString()[:120]))

    def search_musescore(self):
        q = self.q.text().strip()
        if not q:
            return
        url = web_search_urls(q)['MuseScore']
        self.tabs.setCurrentIndex(0)
        if self.web is not None:
            self.web.load(QUrl(url))
            self.status.setText("Szukam w MuseScore…")
        else:
            QDesktopServices.openUrl(QUrl(url))
            self.status.setText("Otworzyłem MuseScore w przeglądarce. Pobierz nuty (Download → PDF albo MuseScore) – "
                                "plik pojawi się poniżej.")

    def _web_download(self, req):
        if req.page() is not None and self.web is not None and req.page() is not self.web.page():
            return                                    # pobieranie z innego okna
        try:
            req.setDownloadDirectory(tempfile.mkdtemp(prefix="lc_nuty_"))
        except Exception:
            pass
        req.isFinishedChanged.connect(lambda r=req: self._web_done(r))
        req.accept()
        self.status.setText(f"Pobieram: {req.downloadFileName()}…")

    def _web_done(self, req):
        from PySide6.QtWebEngineCore import QWebEngineDownloadRequest
        if req.state() != QWebEngineDownloadRequest.DownloadCompleted:
            self.status.setText(f"Pobieranie przerwane: {req.downloadFileName()}")
            return
        path = os.path.join(req.downloadDirectory(), req.downloadFileName())
        try:
            with open(path, 'rb') as f:
                data = f.read()
        except OSError as e:
            self.status.setText(f"Nie można odczytać pobranego pliku: {e}")
            return
        self.add_local(path)
        if self.local.count():
            self.local.item(0).setText("✓ " + self.local.item(0).text())
        self.files_downloaded.emit([(req.downloadFileName(), data)])
        self.status.setText(f"Dołączono do pieśni: {req.downloadFileName()}")

    def install_webengine(self):
        """Doinstaluj QtWebEngine (PySide6-Addons w tej samej wersji co PySide6) do środowiska programu."""
        import sys
        import PySide6
        from PySide6.QtCore import QProcess
        if QMessageBox.question(self, "MuseScore w programie",
                                "Program pobierze i zainstaluje moduł przeglądarki (PySide6-Addons, ok. 150 MB).\n"
                                "Potrzebny jest internet. Po instalacji uruchom program ponownie.\n\nZainstalować teraz?") \
                != QMessageBox.Yes:
            return
        self.proc = QProcess(self)
        self.status.setText("Instaluję moduł przeglądarki… (to potrwa kilka minut)")
        log = []
        self.proc.readyReadStandardOutput.connect(lambda: log.append(bytes(self.proc.readAllStandardOutput()).decode(
            'utf-8', 'replace')) or self.status.setText("Instaluję… " + log[-1].strip().splitlines()[-1][:100]
                                                         if log[-1].strip() else self.status.text()))
        self.proc.readyReadStandardError.connect(lambda: log.append(bytes(self.proc.readAllStandardError()).decode(
            'utf-8', 'replace')))

        def done(code, _status):
            if code == 0:
                QMessageBox.information(self, "MuseScore w programie",
                                        "Zainstalowano. Zamknij i uruchom program ponownie – MuseScore otworzy się "
                                        "w oknie „Szukaj nut”.")
                self.status.setText("Zainstalowano – uruchom program ponownie.")
            else:
                QMessageBox.warning(self, "MuseScore w programie", "Instalacja się nie udała:\n" +
                                    "".join(log)[-1500:])
        self.proc.finished.connect(done)
        self.proc.start(sys.executable, ["-m", "pip", "install", "--disable-pip-version-check",
                                         f"PySide6-Addons=={PySide6.__version__}"])

    # --- sieć
    def open_web(self, name):
        QDesktopServices.openUrl(QUrl(web_search_urls(self.q.text())[name]))
        self.status.setText("Pobierz plik w przeglądarce (PDF, MuseScore .mscz, MIDI) – pojawi się powyżej na liście „Pobrane”.")

    def _busy(self, on, msg=""):
        self.status.setText(msg)
        if on:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()
        QApplication.processEvents()

    def search_cpdl(self):
        self.results.clear()
        self.files.clear()
        self._busy(True, "Szukam w CPDL…")
        try:
            res = cpdl_search(self.q.text().strip())
        except Blocked as e:
            self._busy(False, f"CPDL nie pozwala programom na wyszukiwanie ({e}) – otwieram CPDL w przeglądarce. "
                              "Pobrany tam plik pojawi się powyżej na liście „Pobrane”.")
            self.open_web('CPDL (strona)')
            return
        except Exception as e:
            self._busy(False, f"Brak połączenia z CPDL ({e}) – otwieram CPDL w przeglądarce. "
                              "Pobrany tam plik pojawi się powyżej na liście „Pobrane”.")
            self.open_web('CPDL (strona)')
            return
        self._busy(False, f"Znaleziono: {len(res)}" if res else "Brak wyników – spróbuj tytułu łacińskiego lub nazwiska kompozytora.")
        for title, snip in res:
            it = QListWidgetItem(title)
            it.setToolTip(snip)
            it.setData(Qt.UserRole, title)
            self.results.addItem(it)

    def load_files(self, item, _prev=None):
        self.files.clear()
        if not item:
            return
        self._busy(True, "Pobieram listę plików…")
        try:
            files = cpdl_files(item.data(Qt.UserRole))
        except Exception as e:
            self._busy(False, f"Błąd: {e} – użyj „Otwórz stronę utworu”.")
            return
        self._busy(False, f"Plików: {len(files)}" if files else "Ta strona nie ma plików (może to strona kompozytora).")
        for name, url in files:
            it = QListWidgetItem(name)
            it.setData(Qt.UserRole, url)
            self.files.addItem(it)

    def open_page(self, item):
        if item:
            QDesktopServices.openUrl(QUrl("https://www.cpdl.org/wiki/index.php/" + urllib.parse.quote(item.data(Qt.UserRole).replace(' ', '_'))))

    def download_selected(self):
        items = self.files.selectedItems()
        if not items:
            return
        got = []
        self._busy(True, "Pobieram…")
        try:
            for it in items:
                data, _, _ = download(it.data(Qt.UserRole))
                got.append((it.text(), data))
        except Exception as e:
            self._busy(False, f"Błąd pobierania: {e} – pobierz w przeglądarce („Otwórz stronę utworu”).")
            if not got:
                return
        else:
            self._busy(False, f"Pobrano: {len(got)}")
        self.files_downloaded.emit(got)

    def closeEvent(self, e):
        self.poll.stop()
        if self.web is not None and _WEB_PROFILE is not None:
            try:
                _WEB_PROFILE.downloadRequested.disconnect(self._web_download)
            except Exception:
                pass
        super().closeEvent(e)


# =====================================================================
# Przeglądarka nut (PDF, obrazy, MuseScore po konwersji)
# =====================================================================

class ScoreViewer(QDialog):
    """Podgląd nut: strona po stronie (strzałki, spacja, pedał Bluetooth, kliknięcie),
    dopasowanie do szerokości lub całej strony, dwie strony obok siebie, pełny ekran."""

    def __init__(self, title, pages, info="", midi=None, open_external=None, parent=None, score=None):
        super().__init__(parent)
        self.score = score
        self.setWindowTitle(f"Nuty – {title}")
        self.setModal(False)
        self.pages = [QImage.fromData(p) for p in pages]
        self.pages = [p for p in self.pages if not p.isNull()]
        self.i, self.mode = 0, 'page'          # 'page' (cała strona) | 'width' (do szerokości, przewijanie)
        self.midi, self.title = midi, title
        self.resize(1000, 800)
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        for txt, fn in (("◀", lambda: self.step(-1)), ("▶", lambda: self.step(1))):
            b = QPushButton(txt)
            b.clicked.connect(fn)
            bar.addWidget(b)
        self.lbl = QLabel()
        bar.addWidget(self.lbl)
        self.b_mode = QPushButton("Do szerokości")
        self.b_mode.clicked.connect(self.toggle_mode)
        bar.addWidget(self.b_mode)
        self.two = QCheckBox("Dwie strony")
        self.two.setChecked(True)
        self.two.toggled.connect(self.draw)
        bar.addWidget(self.two)
        bfs = QPushButton("Pełny ekran (F11)")
        bfs.clicked.connect(self.toggle_fs)
        bar.addWidget(bfs)
        bar.addStretch()
        if midi:
            bm = QPushButton("MIDI – odtwarzanie głosów")
            bm.clicked.connect(self.play_midi)
            bar.addWidget(bm)
        if open_external:
            be = QPushButton("Otwórz w MuseScore / programie")
            be.clicked.connect(open_external)
            bar.addWidget(be)
        lay.addLayout(bar)
        if info:
            il = QLabel(info, wordWrap=True)
            il.setStyleSheet("color: gray;")
            lay.addWidget(il)
        self.scroll = QScrollArea()
        self.scroll.setAlignment(Qt.AlignCenter)
        self.scroll.setStyleSheet("background:#5a5a5a;")
        self.canvas = QLabel()
        self.canvas.setAlignment(Qt.AlignCenter)
        self.scroll.setWidget(self.canvas)
        self.scroll.setWidgetResizable(True)
        lay.addWidget(self.scroll, 1)
        for key, fn in (("Right", lambda: self.step(1)), ("PgDown", lambda: self.step(1)), ("Space", lambda: self.step(1)),
                        ("Left", lambda: self.step(-1)), ("PgUp", lambda: self.step(-1)), ("Home", lambda: self.go(0)),
                        ("End", lambda: self.go(len(self.pages) - 1)), ("F11", self.toggle_fs), ("Esc", self.esc)):
            QShortcut(QKeySequence(key), self, activated=fn)
        self.canvas.mousePressEvent = lambda e: self.step(-1 if e.position().x() < self.canvas.width() / 3 else 1)
        _icons(self)
        QTimer.singleShot(0, self.draw)

    def per_view(self):
        vp = self.scroll.viewport()
        return 2 if self.mode == 'page' and self.two.isChecked() and vp.width() > vp.height() * 1.15 and len(self.pages) > 1 else 1

    def draw(self):
        if not self.pages:
            self.canvas.setText("Brak podglądu.")
            return
        vp = self.scroll.viewport()
        n = self.per_view()
        imgs = self.pages[self.i:self.i + n]
        if self.mode == 'width':
            w = vp.width() - 20
            img = imgs[0].scaledToWidth(max(100, w), Qt.SmoothTransformation)
            self.canvas.setPixmap(QPixmap.fromImage(img))
        else:
            W, H = vp.width() - 10, vp.height() - 10
            scaled = [im.scaled(max(50, (W - 8 * (n - 1)) // n), max(50, H), Qt.KeepAspectRatio, Qt.SmoothTransformation) for im in imgs]
            pm = QPixmap(sum(s.width() for s in scaled) + 8 * (len(scaled) - 1), max(s.height() for s in scaled))
            pm.fill(QColor('#5a5a5a'))
            p = QPainter(pm)
            x = 0
            for s in scaled:
                p.drawImage(x, 0, s)
                x += s.width() + 8
            p.end()
            self.canvas.setPixmap(pm)
        last = min(len(self.pages), self.i + n)
        self.lbl.setText(f"strona {self.i + 1}{'–' + str(last) if last > self.i + 1 else ''} / {len(self.pages)}")

    def step(self, d):
        self.go(self.i + d * self.per_view())

    def go(self, i):
        self.i = max(0, min(len(self.pages) - 1, i))
        self.scroll.verticalScrollBar().setValue(0)
        self.draw()

    def toggle_mode(self):
        self.mode = 'width' if self.mode == 'page' else 'page'
        self.b_mode.setText("Cała strona" if self.mode == 'width' else "Do szerokości")
        self.draw()

    def toggle_fs(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()
        QTimer.singleShot(100, self.draw)

    def esc(self):
        if self.isFullScreen():
            self.toggle_fs()
        else:
            self.close()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, self.draw)

    def play_midi(self):
        try:
            dlg = MidiPlayerDialog(self.midi, self.title, self, score=self.score)
            dlg.show()
        except Exception as e:
            QLabel(str(e)).show()


# =====================================================================
# Nuty PDF -> obrazy stron (tablet, telefon, śpiewnik HTML)
# =====================================================================

def pdf_page_count(data):
    try:
        import pypdfium2 as pdfium
        return len(pdfium.PdfDocument(data))
    except ImportError:
        from pypdf import PdfReader
        return len(PdfReader(io.BytesIO(data)).pages)


def pdf_pages_to_jpeg(data, width=1400, quality=80, max_pages=60):
    """Renderuje strony PDF do JPEG (pypdfium2). Zwraca listę bajtów; [] gdy brak biblioteki."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return []
    out = []
    doc = pdfium.PdfDocument(data)
    try:
        for i in range(min(len(doc), max_pages)):
            page = doc[i]
            w_pt = page.get_width()
            bmp = page.render(scale=width / w_pt)
            img = bmp.to_pil().convert("RGB")
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=quality, optimize=True)
            out.append(buf.getvalue())
    finally:
        doc.close()
    return out


# =====================================================================
# MIDI: wczytanie, głosy, synteza
# =====================================================================

@dataclass
class Voice:
    name: str
    notes: list = field(default_factory=list)       # (start_s, dur_s, pitch, velocity)
    enabled: bool = True
    volume: float = 1.0
    instrument: str = None                           # None = brzmienie wspólne

    @property
    def mean_pitch(self):
        return sum(n[2] for n in self.notes) / len(self.notes) if self.notes else 0

    def polyphony(self):
        ev = sorted([(n[0], 1) for n in self.notes] + [(n[0] + n[1] - 1e-4, -1) for n in self.notes])
        cur = best = 0
        for _, d in ev:
            cur += d
            best = max(best, cur)
        return best


def _need(module):
    try:
        return __import__(module)
    except ImportError:
        raise RuntimeError(f"Ta funkcja wymaga pakietu {module}:\n  pip install {module}")


def load_midi(data):
    """Zwraca (lista głosów, długość w s). Głos = (ścieżka, kanał); perkusja (kanał 10) pomijana."""
    mido = _need('mido')
    mid = mido.MidiFile(file=io.BytesIO(data))
    events = []
    names = {}
    for ti, tr in enumerate(mid.tracks):
        tick = 0
        for msg in tr:
            tick += msg.time
            if msg.type == 'track_name' and msg.name.strip():
                names.setdefault(ti, msg.name.strip())
            events.append((tick, 0 if msg.type == 'set_tempo' else 1, ti, msg))
    events.sort(key=lambda e: (e[0], e[1]))
    tempo, last, t = 500000, 0, 0.0
    open_notes, groups = {}, {}
    for tick, _, ti, msg in events:
        if tick != last:
            t += mido.tick2second(tick - last, mid.ticks_per_beat, tempo)
            last = tick
        if msg.type == 'set_tempo':
            tempo = msg.tempo
        elif msg.type in ('note_on', 'note_off') and msg.channel != 9:
            key = (ti, msg.channel, msg.note)
            if key in open_notes:
                start, vel = open_notes.pop(key)
                groups.setdefault((ti, msg.channel), []).append((start, max(0.03, t - start), msg.note, vel))
            if msg.type == 'note_on' and msg.velocity > 0:
                open_notes[key] = (t, msg.velocity)
    for (ti, ch, note), (start, vel) in open_notes.items():
        groups.setdefault((ti, ch), []).append((start, 0.5, note, vel))
    voices = []
    per_track = {}
    for ti, ch in groups:
        per_track[ti] = per_track.get(ti, 0) + 1
    for (ti, ch), notes in sorted(groups.items()):
        name = names.get(ti, f"Ścieżka {ti + 1}")
        if per_track[ti] > 1:
            name += f" (kanał {ch + 1})"
        voices.append(Voice(name, sorted(notes)))
    length = max((n[0] + n[1] for v in voices for n in v.notes), default=0)
    return voices, length


def midi_timing(data):
    """Mapa tempa i chwile wejścia nut z pliku MIDI: (tpb, [(tick, us/ćwierćnutę)], ticki wejść, ms wejść)."""
    mido = _need('mido')
    mid = mido.MidiFile(file=io.BytesIO(data))
    tempos, onsets = [(0, 500000)], set()
    for tr in mid.tracks:
        tick = 0
        for msg in tr:
            tick += msg.time
            if msg.type == 'set_tempo':
                tempos.append((tick, msg.tempo))
            elif msg.type == 'note_on' and msg.velocity > 0 and getattr(msg, 'channel', 0) != 9:
                onsets.add(tick)
    tempos.sort()
    tpb = mid.ticks_per_beat
    pts, ms = [], 0.0                                   # punkty załamania: (tick, ms, us/ćwierćnutę)
    last_tick, cur = 0, 500000
    for tk, tp in tempos:
        ms += (tk - last_tick) * cur / tpb / 1000
        pts.append((tk, ms, tp))
        last_tick, cur = tk, tp

    def tick2ms(t):
        i = max(0, sum(1 for p in pts if p[0] <= t) - 1)
        tk, base, tp = pts[i]
        return base + (t - tk) * tp / tpb / 1000

    ot = sorted(onsets)
    return tpb, tick2ms, ot, [tick2ms(t) for t in ot]


def load_midi_lyrics(data):
    """Słowa zapisane w pliku MIDI (karaoke .kar / meta 'lyrics'): [(czas_s, sylaba)]."""
    mido = _need('mido')
    mid = mido.MidiFile(file=io.BytesIO(data))
    out, tempo, t, last = [], 500000, 0.0, 0
    events = []
    for tr in mid.tracks:
        tick = 0
        for msg in tr:
            tick += msg.time
            events.append((tick, msg))
    events.sort(key=lambda e: e[0])
    for tick, msg in events:
        if tick != last:
            t += mido.tick2second(tick - last, mid.ticks_per_beat, tempo)
            last = tick
        if msg.type == 'set_tempo':
            tempo = msg.tempo
        elif msg.type in ('lyrics', 'text') and msg.text.strip() and not msg.text.startswith('@'):
            raw = msg.text.encode('latin-1', 'replace')          # mido czyta tekst jako latin-1
            for enc in ('utf-8', 'cp1250'):                     # polskie pliki: UTF-8 albo Windows-1250
                try:
                    txt = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            out.append((t, txt))
    lyr = [x for x in out if x[1] not in ('\r', '\n')]
    return lyr if sum(1 for _ in lyr) >= 4 else []


def _syllable(w):
    """Sylaba z MIDI: '/' i '\\' (karaoke) = podział wiersza; dywiz na końcu = część słowa."""
    w = w.replace('/', ' ').replace('\\', ' ').replace('\r', ' ').replace('\n', ' ')
    if w.rstrip().endswith('-') and not w.endswith(' '):
        return w.rstrip()[:-1]
    return w


def lyric_layout(lyrics, max_len=11, gap=1.6):
    """Grupuje sylaby śpiewane jednocześnie (różne zwrotki) i dzieli na frazy.
    Zwraca (grupy: [(czas, [sylaba_zwrotki1, sylaba_zwrotki2, …])], frazy: [(początek, koniec)])."""
    groups = []
    for t, w in lyrics:
        w = _syllable(w)
        if groups and abs(t - groups[-1][0]) < 0.03:
            groups[-1][1].append(w)
        else:
            groups.append((t, [w]))
    # sylaba bez spacji na końcu = dalsza część słowa (MuseScore dzieli słowa na sylaby bez dywizu)
    chunks, start = [], 0
    punct = re.compile(r'[.,;:!?…]["”»)]?\s*$')
    for k in range(len(groups)):
        syl = groups[k][1]
        word_end = all(w.endswith(' ') or punct.search(w) for w in syl)      # koniec słowa we wszystkich zwrotkach
        sentence = any(re.search(r'[.!?…]["”»)]?\s*$', w) for w in syl)
        end_phrase = word_end and (sentence or (any(punct.search(w) for w in syl) and k + 1 - start >= 6))
        long_gap = k + 1 < len(groups) and groups[k + 1][0] - groups[k][0] > gap
        too_long = k + 1 - start >= max_len and word_end
        if end_phrase or long_gap or too_long or k == len(groups) - 1:
            chunks.append((start, k + 1))
            start = k + 1
    return groups, chunks or [(0, len(groups))]


def split_chords(voice, n=None):
    """Rozdziela akordy jednej ścieżki na osobne głosy wg wysokości (góra = 1. głos).
    Nuty zaczynające się razem są sortowane od najwyższej; wytrzymane nuty z wcześniejszych
    akordów przesuwają numerację (np. gdy bas trzyma, a górne głosy się ruszają)."""
    n = n or min(4, voice.polyphony())
    if n <= 1:
        return [Voice(voice.name, list(voice.notes))]
    out = [Voice(f"{voice.name} – głos {k + 1}") for k in range(n)]
    notes = sorted(voice.notes, key=lambda x: (x[0], -x[2]))
    assigned = []                                  # (koniec, wysokość, głos)
    i = 0
    while i < len(notes):
        t0 = notes[i][0]
        group = []
        while i < len(notes) and notes[i][0] - t0 < 0.03:
            group.append(notes[i])
            i += 1
        held = [a for a in assigned if a[0] > t0 + 0.03]
        free = [k for k in range(n) if k not in {a[2] for a in held}] or list(range(n))
        # wolne głosy po kolei od góry; jeśli nut więcej niż głosów – nadmiar do najniższego
        for j, nt in enumerate(group):
            k = free[min(j, len(free) - 1)]
            out[k].notes.append(nt)
            assigned.append((nt[0] + nt[1], nt[2], k))
    return [v for v in out if v.notes]


def prepare_voices(raw, split=True):
    voices = []
    for v in raw:
        voices += split_chords(v) if split else [Voice(v.name, list(v.notes))]
    voices = [Voice(v.name, sorted(v.notes)) for v in voices]
    if len(voices) == 4:                       # czterogłos: nazwij S A T B wg średniej wysokości
        for name, v in zip(SATB, sorted(voices, key=lambda v: -v.mean_pitch)):
            v.name = f"{name}  ({v.name})" if not v.name.startswith(tuple(SATB)) else v.name
        voices.sort(key=lambda v: -v.mean_pitch)
    return voices


def synthesize(voices, tempo=1.0, transpose=0, practice=None, sr=None, instrument='wb:proste', organ=0.0,
               organ_instr='sf:0:19', sf=None, progress=None):
    """Synteza głosów wybranym brzmieniem (wbudowanym lub z SoundFontu – modul_brzmienia).
    practice – indeks ćwiczonego głosu (reszta ciszej); organ – głośność podkładu organowego 0..1
    dublującego głosy śpiewane."""
    np = _need('numpy')
    import modul_brzmienia as B
    sr = sr or B.SR
    active = [(i, v) for i, v in enumerate(voices) if v.enabled and v.notes]
    length = max((n[0] + n[1] for _, v in active for n in v.notes), default=0) / tempo + 3.0
    buf = np.zeros(int(length * sr) + 1, np.float32)
    total = sum(len(v.notes) for _, v in active) or 1
    done = 0
    for i, v in active:
        gain = v.volume * (1.0 if practice is None or practice == i else 0.25)
        instr = v.instrument or instrument
        layer = organ if organ > 0 and sf is not None and not B.is_organ(instr) else 0.0
        for k, (start, dur, pitch, vel) in enumerate(v.notes):
            s, d = start / tempo, max(0.03, dur / tempo)
            seg = B.render_note(instr, pitch + transpose, d, vel, sf, sr, seed=i * 1000 + k) * gain
            if layer:
                seg2 = B.render_note(organ_instr, pitch + transpose, d, 80, sf, sr, seed=k) * (gain * layer)
                m = max(len(seg), len(seg2))
                seg = np.pad(seg, (0, m - len(seg))) + np.pad(seg2, (0, m - len(seg2)))
            a = int(s * sr)
            if a < len(buf):
                buf[a:a + len(seg)] += seg[:len(buf) - a]
            done += 1
            if progress and done % 40 == 0:
                progress(done, total)
    nz = np.nonzero(np.abs(buf) > 1e-4)[0]
    buf = buf[:nz[-1] + int(0.3 * sr)] if len(nz) else buf[:sr]
    peak = float(np.abs(buf).max()) if len(buf) else 0
    if peak > 0:
        buf *= 0.8 / peak
    return buf, sr


def write_wav(path, buf, sr):
    np = _need('numpy')
    pcm = (np.clip(buf, -1, 1) * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def midi_note_name(p):
    return ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "B", "H"][p % 12] + str(p // 12 - 1)


# =====================================================================
# Wałek pianoli
# =====================================================================

class PianoRoll(QWidget):
    seek = Signal(float)

    PX_PER_S = 90

    def __init__(self):
        super().__init__()
        self.voices, self.length, self.pos, self.tempo, self.transpose = [], 0, 0.0, 1.0, 0
        self.setMinimumHeight(260)

    def set_data(self, voices, length, tempo, transpose):
        self.voices, self.length, self.tempo, self.transpose = voices, length, tempo, transpose
        self.setMinimumWidth(int(length / tempo * self.PX_PER_S) + 80)
        self.update()

    def set_pos(self, s):
        self.pos = s
        self.update()

    def mousePressEvent(self, e):
        self.seek.emit(max(0.0, (e.position().x() - 40) / self.PX_PER_S))

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor('#16181d'))
        notes = [n for v in self.voices for n in v.notes]
        if not notes:
            p.setPen(QColor('#aaa'))
            p.drawText(self.rect(), Qt.AlignCenter, "Brak nut")
            return
        lo = min(n[2] for n in notes) + self.transpose - 2
        hi = max(n[2] for n in notes) + self.transpose + 2
        h = self.height() - 20
        rowh = h / (hi - lo + 1)
        x0 = 40
        # linie oktaw C
        p.setFont(QFont("Sans", 8))
        for pitch in range(lo, hi + 1):
            y = 10 + (hi - pitch) * rowh
            if pitch % 12 == 0:
                p.setPen(QColor('#3a3f4a'))
                p.drawLine(x0, int(y + rowh), self.width(), int(y + rowh))
                p.setPen(QColor('#8a93a3'))
                p.drawText(QRectF(0, y - 2, x0 - 4, rowh + 4), Qt.AlignRight | Qt.AlignVCenter, midi_note_name(pitch))
        # takty co sekundę
        p.setPen(QColor('#22262d'))
        for sec in range(int(self.length / self.tempo) + 1):
            x = x0 + sec * self.PX_PER_S
            p.drawLine(int(x), 0, int(x), self.height())
        for i, v in enumerate(self.voices):
            c = QColor(VOICE_COLORS[i % len(VOICE_COLORS)])
            if not v.enabled:
                c.setAlpha(45)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            for start, dur, pitch, vel in v.notes:
                pp = pitch + self.transpose
                p.drawRoundedRect(QRectF(x0 + start / self.tempo * self.PX_PER_S, 10 + (hi - pp) * rowh + 1,
                                         max(3, dur / self.tempo * self.PX_PER_S - 1), max(2, rowh - 2)), 2, 2)
        x = x0 + self.pos * self.PX_PER_S
        p.setPen(QPen(QColor('#ffffff'), 2))
        p.drawLine(QPointF(x, 0), QPointF(x, self.height()))
        p.end()


# =====================================================================
# Nuty ze słowami zsynchronizowane z odtwarzaniem
# =====================================================================

class _ScoreCanvas(QWidget):
    """Wszystkie strony nut jedna pod drugą + kursor."""
    def __init__(self, owner):
        super().__init__()
        self.o = owner

    def paintEvent(self, e):
        o = self.o
        p = QPainter(self)
        p.fillRect(e.rect(), QColor(106, 106, 106))
        x0 = o._x0()
        for i, (top, pm) in enumerate(o._layout()):
            if top + pm.height() < e.rect().top() or top > e.rect().bottom():
                continue
            p.drawPixmap(int(x0), int(top), pm)
            p.setPen(QColor(230, 230, 230))
            p.drawText(QRectF(x0 + pm.width() + 6, top, 60, 20), Qt.AlignLeft, str(i + 1))
        r = o.cursor_rect()
        if r is not None:
            p.setRenderHint(QPainter.Antialiasing)
            p.fillRect(r, QColor(255, 200, 0, 70))
            p.setPen(QPen(QColor(220, 40, 30), 3))
            p.drawLine(QPointF(r.left() + 2, r.top()), QPointF(r.left() + 2, r.bottom()))
        p.end()

    def mousePressEvent(self, e):
        self.o._click(e.position())


class ScoreFollow(QScrollArea):
    """Strony nut (PDF z MuseScore) jedna pod drugą, z kursorem na bieżącej nucie.
    Widok sam podąża za kursorem; po ręcznym przewinięciu kilka sekund czeka, aż skończysz oglądać.
    Pozycje nut pochodzą z pliku .spos MuseScore."""
    seek = Signal(float)                          # czas w nutach (ms)
    GAP = 14

    def __init__(self, pdf, spos, timing=None):
        """timing – wynik midi_timing() pliku MIDI z tego samego utworu; służy do ustalenia,
        w jakich jednostkach MuseScore zapisał czasy pozycji (ms w MuseScore 3, inne w MuseScore 4)."""
        super().__init__()
        import bisect
        import xml.etree.ElementTree as ET
        self.bisect = bisect
        self.setWidgetResizable(False)
        self.setStyleSheet("QScrollArea{background:#6a6a6a;}")
        self.canvas = _ScoreCanvas(self)
        self.setWidget(self.canvas)
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(pdf)
        self.page_pts = [(doc[i].get_width(), doc[i].get_height()) for i in range(len(doc))]
        doc.close()
        self.pages = [QImage.fromData(b) for b in pdf_pages_to_jpeg(pdf, width=1600, quality=88)]
        root = ET.fromstring(spos)
        self.el = {}
        for e in root.iter('element'):
            self.el[e.get('id')] = tuple(float(e.get(a)) for a in ('x', 'y', 'sx', 'sy')) + (int(float(e.get('page', 0))),)
        raw = sorted((float(e.get('position')), e.get('elid')) for e in root.iter('event') if e.get('elid') in self.el)
        conv, self.unit = self._choose_units([p for p, _ in raw], timing)
        self.events = [(conv(p), elid) for p, elid in raw]
        self.times = [t for t, _ in self.events]
        self.k = self._choose_scale()
        self.cur_page, self.cur_ev, self._cache = 0, -1, {}
        self._user_until = 0.0                     # do kiedy nie przewijać automatycznie (ręczne przewijanie)
        self._auto = False
        for sb in (self.verticalScrollBar(), self.horizontalScrollBar()):
            sb.valueChanged.connect(self._scrolled)
        QTimer.singleShot(0, lambda: self.set_time(0, force=True))

    # ---------- jednostki ----------
    def _choose_scale(self):
        """Ile punktów PDF na jednostkę współrzędnych .spos. MuseScore 3: 1/12 px przy 300 DPI;
        MuseScore 4 zapisuje w innej skali – wybieramy tę, przy której nuty mieszczą się na stronie."""
        if not self.el or not self.page_pts:
            return 72 / 3600
        W, H = self.page_pts[0]
        far_x = max(x + sx for x, y, sx, sy, pg in self.el.values()) or 1
        far_y = max(y + sy for x, y, sx, sy, pg in self.el.values()) or 1
        cands = [72 / 3600, 72 / 4320, 72 / 12000, 72 / 14400, 72 / 300, 72 / 360, 72 / 1200, 1.0]
        ok = [k for k in cands if 0.55 <= far_x * k / W <= 1.0 and far_y * k <= H * 1.02]
        if ok:
            return min(ok, key=lambda k: abs(far_x * k / W - 0.88))
        return 0.88 * W / far_x                      # nieznana skala – dopasuj do szerokości strony

    def _choose_units(self, positions, timing):
        """Wybiera przeliczenie czasu pozycji na ms, które najlepiej trafia w wejścia nut w MIDI."""
        ident = (lambda p: float(p)), "ms"
        if not timing or not positions or not timing[3]:
            return ident
        tpb, tick2ms, on_ticks, on_ms = timing
        pmax = max(positions) or 1
        cands = [ident, ((lambda p: p * 1000.0), "s"), ((lambda p: tick2ms(p)), "tiki"),
                 ((lambda p: tick2ms(p * tpb / 480.0)), "tiki/480"),
                 ((lambda p: tick2ms(p * on_ticks[-1] / pmax)), "tiki (skala)"),
                 ((lambda p: p * on_ms[-1] / pmax), "liniowo")]
        sample = positions[:: max(1, len(positions) // 300)]
        best, best_err = ident, 1e18
        for f, name in cands:
            errs = []
            for p in sample:
                t = f(p)
                j = self.bisect.bisect_left(on_ms, t)
                d = min(abs(t - on_ms[k]) for k in (j - 1, j) if 0 <= k < len(on_ms))
                errs.append(d)
            errs.sort()
            err = errs[len(errs) // 2] + 0.2 * errs[int(len(errs) * 0.9)]
            if f(pmax) > on_ms[-1] * 1.5 + 2000:            # wyraźnie dłużej niż utwór – odrzuć
                err += 1e9
            if err < best_err:
                best, best_err = (f, name), err
        return best

    # ---------- powiększenie i układ ----------
    zoom = 1.0                       # 1.0 = szerokość okna; mniej = widać więcej taktów (cała fraza / strona)
    zoom_changed = Signal(float)

    def _width(self):
        return max(150, int((self.viewport().width() - 40) * self.zoom))

    def _layout(self):
        """[(góra strony w pikselach, pixmapa)] dla bieżącej szerokości."""
        w = self._width()
        if self._cache.get('w') != w:
            pms, top = [], self.GAP
            for img in self.pages:
                pm = QPixmap.fromImage(img.scaledToWidth(w, Qt.SmoothTransformation))
                pms.append((top, pm))
                top += pm.height() + self.GAP
            self._cache = {'w': w, 'pages': pms, 'h': top}
        size = (max(self.viewport().width(), w + 80), self._cache['h'])
        if self.canvas.size().toTuple() != size:
            self.canvas.resize(*size)
        return self._cache['pages']

    def _x0(self):
        return max(10, (self.canvas.width() - self._width()) / 2)

    def set_zoom(self, z):
        self.zoom = max(0.2, min(3.0, z))
        self.zoom_changed.emit(self.zoom)
        self._layout()
        self.canvas.update()
        self._user_until = 0
        self._follow()

    def fit_page(self):
        """Cała strona w oknie."""
        if not self.pages:
            return
        img = self.pages[min(self.cur_page, len(self.pages) - 1)]
        vw, vh = self.viewport().width() - 40, self.viewport().height() - 2 * self.GAP
        self.set_zoom(min(1.0, (vh * img.width() / img.height()) / max(1, vw)))

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:                # Ctrl + kółko = powiększ / pomniejsz
            self.set_zoom(self.zoom * (1.1 if e.angleDelta().y() > 0 else 1 / 1.1))
            e.accept()
        else:
            super().wheelEvent(e)

    def _scrolled(self, *_):
        if not self._auto:                                   # przewinięte ręcznie – nie przeszkadzaj
            self._user_until = time.monotonic() + 5.0

    # ---------- kursor ----------
    def _rect(self, elid):
        x, y, sx, sy, pg = self.el[elid]
        pages = self._layout()
        pg = min(pg, len(pages) - 1)
        top, pm = pages[pg]
        s = self.k * pm.width() / self.page_pts[pg][0]
        return QRectF(self._x0() + x * s - 3, top + y * s - 4, max(sx * s, 8) + 6, sy * s + 8)

    def cursor_rect(self):
        if self.cur_ev < 0 or not self.events:
            return None
        return self._rect(self.events[self.cur_ev][1])

    def _follow(self):
        r = self.cursor_rect()
        if r is None or time.monotonic() < self._user_until:
            return
        self._auto = True
        vb, vh = self.verticalScrollBar(), self.viewport().height()
        top = r.top() - vb.value()
        if top < vh * 0.08 or r.bottom() - vb.value() > vh * 0.85:   # system poza wygodnym pasem –
            vb.setValue(int(r.top() - vh * 0.22))                     # ustaw go w górnej części okna
        self.ensureVisible(int(r.center().x()), int(r.center().y()), 60, 0)
        self._auto = False

    def set_time(self, ms, force=False):
        if not self.events or not self.pages:
            return
        i = max(0, self.bisect.bisect_right(self.times, ms) - 1)
        if i == self.cur_ev and not force:
            return
        old = self.cursor_rect()
        self.cur_ev = i
        self.cur_page = self.el[self.events[i][1]][4]
        r = self.cursor_rect()
        if old is not None:
            self.canvas.update(old.adjusted(-4, -4, 4, 4).toAlignedRect())
        self.canvas.update(r.adjusted(-4, -4, 4, 4).toAlignedRect())
        self._follow()

    def _click(self, pt):
        """Kliknięcie w nuty = przewiń odtwarzanie do tego miejsca."""
        if not self.events:
            return
        pages = self._layout()
        pg = next((i for i, (top, pm) in enumerate(pages) if top - self.GAP <= pt.y() <= top + pm.height()), None)
        if pg is None:
            return
        best, bd = None, 1e18
        for t, elid in self.events:
            if min(self.el[elid][4], len(pages) - 1) != pg:
                continue
            r = self._rect(elid)
            if r.top() - 20 <= pt.y() <= r.bottom() + 20:
                d = abs(r.center().x() - pt.x())
                if d < bd:
                    best, bd = t, d
        if best is not None:
            self._user_until = 0
            self.seek.emit(float(best))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        QTimer.singleShot(0, lambda: (self._layout(), self.canvas.update(), self._follow()))


# =====================================================================
# Okno odtwarzacza
# =====================================================================

class MidiPlayerDialog(QDialog):
    def __init__(self, data, title="MIDI", parent=None, score=None):
        """score – (pdf, spos) z MuseScore: nuty ze słowami z kursorem podczas odtwarzania."""
        super().__init__(parent)
        _need('mido')
        _need('numpy')
        self.setWindowTitle(f"MIDI – odtwarzanie głosów – {title}")
        self.resize(1000, 640)
        self.raw, self.length = load_midi(data)
        if not self.raw:
            raise RuntimeError("Plik MIDI nie zawiera nut.")
        self.buf, self.sr, self.dirty = None, 22050, True
        self.offset = 0.0                    # pozycja startu (s, w czasie po zmianie tempa)
        self.playing = False
        self.clock = QElapsedTimer()
        self.timer = QTimer(self, interval=40, timeout=self.tick)
        self.tmp_wav = None

        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.split = QCheckBox("Rozdziel akordy na głosy")
        self.split.setChecked(any(v.polyphony() > 1 for v in self.raw))
        self.split.toggled.connect(self.rebuild_voices)
        self.tempo = QSpinBox(minimum=25, maximum=200, value=100, suffix=" %", singleStep=5)
        self.tempo.valueChanged.connect(self.params_changed)
        self.transpose = QSpinBox(minimum=-12, maximum=12, value=0, suffix=" półt.")
        self.transpose.valueChanged.connect(self.params_changed)
        self.practice = QComboBox()
        self.practice.currentIndexChanged.connect(self.params_changed)
        top.addWidget(self.split)
        top.addWidget(QLabel("Tempo:"))
        top.addWidget(self.tempo)
        top.addWidget(QLabel("Transpozycja:"))
        top.addWidget(self.transpose)
        top.addWidget(QLabel("Ćwicz głos:"))
        top.addWidget(self.practice)
        top.addStretch()
        lay.addLayout(top)

        # --- brzmienie
        from PySide6.QtCore import QSettings
        import modul_brzmienia as B
        self.B = B
        self.qs = QSettings("LiberCanticorum", "LiberCanticorum")
        self.sf = None
        snd = QHBoxLayout()
        self.instr = QComboBox()
        self.instr.setMinimumWidth(260)
        self.organ = QSlider(Qt.Horizontal, minimum=0, maximum=100)
        self.organ.setMaximumWidth(140)
        self.organ.setValue(int(self.qs.value("midi_organ", 0)))
        self.organ.setToolTip("Podkład organowy pod głosami śpiewanymi (0 = bez organów)")
        self.sf_lbl = QLabel()
        self.sf_lbl.setStyleSheet("color: gray;")
        b_sf = QPushButton("SoundFont…")
        b_sf.setToolTip("Wskaż plik .sf2 / .sf3 z prawdziwymi próbkami chóru i organów")
        b_sf.clicked.connect(self.choose_sf)
        b_get = QPushButton("Skąd pobrać?")
        b_get.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(B.GENERALUSER_URL)))
        snd.addWidget(QLabel("Brzmienie:"))
        snd.addWidget(self.instr)
        snd.addWidget(QLabel("Podkład organowy:"))
        snd.addWidget(self.organ)
        snd.addWidget(b_sf)
        snd.addWidget(b_get)
        snd.addStretch()
        lay.addLayout(snd)
        lay.addWidget(self.sf_lbl)
        self.load_sf(self.qs.value("soundfont", ""))
        self.instr.currentIndexChanged.connect(self.instr_changed)
        self.organ.sliderReleased.connect(self.instr_changed)

        self.voice_box = QGridLayout()
        lay.addLayout(self.voice_box)

        self.roll = PianoRoll()
        self.roll.seek.connect(self.seek_to)
        self.scroll = QScrollArea()
        self.scroll.setWidget(self.roll)
        self.scroll.setWidgetResizable(True)
        self.follow = None
        if score and score[0] and score[1]:
            try:
                self.follow = ScoreFollow(score[0], score[1], midi_timing(data))
                self.follow.seek.connect(lambda ms: self.seek_to(ms / 1000 / (self.tempo.value() / 100)))
            except Exception as e:
                self.follow = None
                print("Nuty z kursorem niedostępne:", e)
        views = QHBoxLayout()
        self.show_score = QCheckBox("Nuty ze słowami (kursor podczas odtwarzania; kliknij nutę, by tam przeskoczyć)")
        self.show_roll = QCheckBox("Wałek pianoli")
        self.show_score.setChecked(self.follow is not None)
        self.show_score.setEnabled(self.follow is not None)
        if self.follow is None:
            self.show_score.setToolTip("Nuty z kursorem są dostępne dla plików MuseScore (.mscz) – otwórz głosy z pliku MuseScore.")
        self.show_roll.setChecked(self.follow is None)
        views.addWidget(self.show_score)
        views.addWidget(self.show_roll)
        views.addStretch()
        from PySide6.QtCore import QSettings
        self._qs = QSettings("LiberCanticorum", "LiberCanticorum")
        if self.follow:
            views.addWidget(QLabel("Nuty:"))
            self.zoom_lbl = QLabel()
            for txt, tip, fn in (("−", "Pomniejsz (Ctrl + kółko myszy)", lambda: self.follow.set_zoom(self.follow.zoom / 1.15)),
                                 ("+", "Powiększ (Ctrl + kółko myszy)", lambda: self.follow.set_zoom(self.follow.zoom * 1.15)),
                                 ("Szerokość", "Dopasuj do szerokości okna", lambda: self.follow.set_zoom(1.0)),
                                 ("Strona", "Cała strona w oknie", lambda: self.follow.fit_page())):
                b = QPushButton(txt)
                b.setToolTip(tip)
                b.setMaximumWidth(90 if len(txt) > 1 else 34)
                b.clicked.connect(fn)
                if txt == "+":
                    views.addWidget(self.zoom_lbl)
                views.addWidget(b)
            self.follow.zoom_changed.connect(lambda z: (self.zoom_lbl.setText(f"{int(z * 100)}%"),
                                                        self._qs.setValue("score_zoom", z)))
            self.follow.zoom = float(self._qs.value("score_zoom", 0.75))
            self.zoom_lbl.setText(f"{int(self.follow.zoom * 100)}%")
        self.lyr_size = int(self._qs.value("lyrics_size", 30))
        self.lyr_buttons = []
        for txt, d in (("A−", -3), ("A+", 3)):
            b = QPushButton(txt)
            b.setToolTip("Wielkość słów pod nutami")
            b.setMaximumWidth(40)
            b.clicked.connect(lambda _=False, d=d: self.set_lyrics_size(self.lyr_size + d))
            views.addWidget(b)
            self.lyr_buttons.append(b)
        lay.addLayout(views)
        from PySide6.QtWidgets import QSplitter
        split = QSplitter(Qt.Vertical)
        if self.follow:
            split.addWidget(self.follow)
        split.addWidget(self.scroll)
        lay.addWidget(split, 1)
        self.show_score.toggled.connect(lambda on: self.follow and self.follow.setVisible(on))
        self.show_roll.toggled.connect(self.scroll.setVisible)
        self.scroll.setVisible(self.show_roll.isChecked())
        self.lyrics = load_midi_lyrics(data)
        self.lyr_groups, self.lyr_chunks = lyric_layout(self.lyrics)
        self.lyr_times = [t for t, _ in self.lyr_groups]
        self.lyr_state = None
        self.lyr_lbl = QLabel()
        self.lyr_lbl.setAlignment(Qt.AlignCenter)
        self.lyr_lbl.setTextFormat(Qt.RichText)
        self.lyr_lbl.setStyleSheet(f"font-size: {self.lyr_size}px; padding: 8px;")
        self.lyr_lbl.setWordWrap(True)
        self.lyr_lbl.setVisible(bool(self.lyrics))
        for b in self.lyr_buttons:
            b.setVisible(bool(self.lyrics))
        lay.addWidget(self.lyr_lbl)
        if self.follow:
            self.resize(1150, 900)

        ctl = QHBoxLayout()
        self.b_play = QPushButton("Odtwórz")
        self.b_play.setIcon(_icon("play"))
        self.b_play.clicked.connect(self.toggle)
        b_start = QPushButton("Od początku")
        b_start.clicked.connect(lambda: self.seek_to(0))
        b_wav = QPushButton("Zapisz WAV…")
        b_wav.clicked.connect(self.save_wav)
        self.pos_lbl = QLabel()
        ctl.addWidget(b_start)
        ctl.addWidget(self.b_play)
        ctl.addWidget(self.pos_lbl)
        ctl.addStretch()
        ctl.addWidget(b_wav)
        lay.addLayout(ctl)
        self.rebuild_voices()
        _icons(self)

    # --- głosy
    def rebuild_voices(self):
        self.stop()
        self.voices = prepare_voices(self.raw, self.split.isChecked())
        while self.voice_box.count():
            w = self.voice_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        for i, v in enumerate(self.voices):
            c = VOICE_COLORS[i % len(VOICE_COLORS)]
            cb = QCheckBox(f"{v.name}   [{midi_note_name(min(n[2] for n in v.notes))}–{midi_note_name(max(n[2] for n in v.notes))}]")
            cb.setChecked(True)
            cb.setStyleSheet(f"QCheckBox {{ color: {c}; font-weight: bold; }}")
            cb.toggled.connect(lambda on, v=v: (setattr(v, 'enabled', on), self.params_changed()))
            sl = QSlider(Qt.Horizontal, minimum=0, maximum=100, value=100)
            sl.setMaximumWidth(140)
            sl.sliderReleased.connect(lambda sl=sl, v=v: (setattr(v, 'volume', sl.value() / 100), self.params_changed()))
            vc = QComboBox()
            vc.addItem("(jak wszystkie)", None)
            for key, label in self.instrument_list():
                vc.addItem(label, key)
            vc.currentIndexChanged.connect(lambda _=0, vc=vc, v=v: (setattr(v, 'instrument', vc.currentData()), self.params_changed()))
            self.voice_box.addWidget(cb, i // 2, (i % 2) * 3)
            self.voice_box.addWidget(sl, i // 2, (i % 2) * 3 + 1)
            self.voice_box.addWidget(vc, i // 2, (i % 2) * 3 + 2)
        self.practice.blockSignals(True)
        self.practice.clear()
        self.practice.addItem("(wszystkie równo)", None)
        for i, v in enumerate(self.voices):
            self.practice.addItem(v.name.split('  (')[0], i)
        self.practice.blockSignals(False)
        self.params_changed()

    # --- brzmienia
    def instrument_list(self):
        items = []
        if self.sf is not None:
            for bank, prog, label in self.B.GM_PRESETS:
                if self.sf.preset_name(bank, prog):
                    items.append((f"sf:{bank}:{prog}", f"♫ {label}"))
        return items or list(self.B.BUILTIN)

    def load_sf(self, path):
        found = self.B.find_soundfonts(path or "")
        self.sf, err = None, ""
        for p in found:
            try:
                self.sf = self.B.load_soundfont(p)
                break
            except Exception as e:
                err = str(e)
        if self.sf:
            self.sf_lbl.setText(f"SoundFont: {self.sf.name}  ({os.path.basename(self.sf.path)}) – barwy oznaczone ♫ to prawdziwe próbki.")
        else:
            self.sf_lbl.setText("⚠ Brak SoundFontu – gra prosty ton. Chór i organy: kliknij „Skąd pobrać?” (darmowy GeneralUser GS), "
                                "pobierz plik .sf2 i wskaż go przyciskiem „SoundFont…”." + (f" ({err})" if err else ""))
            self.sf_lbl.setStyleSheet("color: #b05000;")
        cur = self.instr.currentData() or self.qs.value("midi_instrument", "")
        self.instr.blockSignals(True)
        self.instr.clear()
        for key, label in self.instrument_list():
            self.instr.addItem(label, key)
        idx = self.instr.findData(cur)
        if idx < 0:
            idx = self.instr.findData("sf:0:52" if self.sf else "wb:proste")
        self.instr.setCurrentIndex(max(0, idx))
        self.instr.blockSignals(False)

    def choose_sf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Plik SoundFont", os.path.expanduser("~"), "SoundFont (*.sf2 *.sf3)")
        if not path:
            return
        try:
            self.B.load_soundfont(path)
        except Exception as e:
            self.sf_lbl.setText(f"Nie można wczytać: {e}")
            return
        self.qs.setValue("soundfont", path)
        self.load_sf(path)
        self.rebuild_voices()

    def instr_changed(self, *_):
        self.qs.setValue("midi_instrument", self.instr.currentData())
        self.qs.setValue("midi_organ", self.organ.value())
        self.params_changed()

    def params_changed(self, *_):
        was = self.playing
        cur = self.current_pos()
        self.stop()
        self.dirty = True
        self.roll.set_data(self.voices, self.length, self.tempo.value() / 100, self.transpose.value())
        self.offset = cur
        self.update_pos(cur)
        if was:
            self.play()

    def render(self):
        if self.dirty or self.buf is None:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                organ_instr = 'sf:0:19'
                self.buf, self.sr = synthesize(self.voices, self.tempo.value() / 100, self.transpose.value(),
                                               self.practice.currentData(), instrument=self.instr.currentData() or 'wb:proste',
                                               organ=self.organ.value() / 100, organ_instr=organ_instr, sf=self.sf,
                                               progress=lambda d, t: (self.pos_lbl.setText(f"Przygotowuję dźwięk… {100 * d // t}%"),
                                                                      QApplication.processEvents()))
            finally:
                QApplication.restoreOverrideCursor()
            self.dirty = False
        return self.buf

    # --- odtwarzanie
    def current_pos(self):
        return self.offset + (self.clock.elapsed() / 1000 if self.playing else 0)

    def play(self):
        buf = self.render()
        start = int(self.offset * self.sr)
        if start >= len(buf) - 10:
            self.offset, start = 0.0, 0
        try:
            import sounddevice as sd
            sd.stop()
            sd.play(buf[start:], self.sr)
        except Exception as e:
            self.play_external(buf, str(e))
            return
        self.playing = True
        self.clock.start()
        self.timer.start()
        self.b_play.setText("Pauza")
        self.b_play.setIcon(_icon("pause"))

    def play_external(self, buf, why):
        """Brak sounddevice / urządzenia audio – zapis WAV i systemowy odtwarzacz."""
        self.tmp_wav = os.path.join(tempfile.gettempdir(), "spiewnik_glosy.wav")
        write_wav(self.tmp_wav, buf, self.sr)
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.tmp_wav))
        hint = "zainstaluj pakiet sounddevice" if "No module" in why else \
            "na Linuksie: sudo apt install libportaudio2" if "PortAudio" in why else why
        self.pos_lbl.setText(f"Odtwarzam w systemowym odtwarzaczu – dźwięk w programie niedostępny ({hint}).")

    def stop(self):
        if self.playing:
            self.offset = self.current_pos()
            try:
                import sounddevice as sd
                sd.stop()
            except Exception:
                pass
        self.playing = False
        self.timer.stop()
        self.b_play.setText("Odtwórz")
        self.b_play.setIcon(_icon("play"))

    def toggle(self):
        if self.playing:
            self.stop()
        else:
            self.play()

    def seek_to(self, s):
        was = self.playing
        self.stop()
        self.offset = max(0.0, s)
        self.update_pos(self.offset)
        if was:
            self.play()

    def tick(self):
        pos = self.current_pos()
        total = len(self.buf) / self.sr if self.buf is not None else 0
        if pos >= total:
            self.stop()
            self.offset = 0.0
            pos = 0.0
        self.update_pos(pos)

    def update_pos(self, pos):
        self.roll.set_pos(pos)
        if self.follow:
            self.follow.set_time(pos * (self.tempo.value() / 100) * 1000)
        if self.lyrics:
            self.show_lyrics(pos * (self.tempo.value() / 100))

    def set_lyrics_size(self, px):
        self.lyr_size = max(14, min(72, px))
        self._qs.setValue("lyrics_size", self.lyr_size)
        self.lyr_lbl.setStyleSheet(f"font-size: {self.lyr_size}px; padding: 8px;")

    def show_lyrics(self, t):
        """Tekst pod nutami: cała fraza naraz (osobny wiersz dla każdej zwrotki); zmienia się dopiero
        po zaśpiewaniu frazy, w środku przesuwa się tylko podświetlenie bieżącej sylaby."""
        g = max(0, self.bisect_groups(t) - 1)
        ci = next((k for k, (a, b) in enumerate(self.lyr_chunks) if a <= g < b), len(self.lyr_chunks) - 1)
        state = (ci, g)
        if state == self.lyr_state:
            return                                       # nic się nie zmieniło – bez przerysowania
        self.lyr_state = state
        a, b = self.lyr_chunks[ci]
        nverses = max(len(self.lyr_groups[k][1]) for k in range(a, b))
        rows = []
        for v in range(nverses):
            parts = []
            for k in range(a, b):
                syl = self.lyr_groups[k][1]
                w = syl[v] if v < len(syl) else (syl[0] if len(syl) == 1 else "")
                if not w:
                    continue
                txt = html.escape(w)
                parts.append(f"<span style='color:#c0281c'>{txt}</span>" if k == g else txt)
            if parts:
                label = f"<span style='color:#8a8a8a;font-size:{max(12, self.lyr_size // 2)}px'>{v + 1}.&nbsp;</span>" if nverses > 1 else ""
                rows.append(label + "".join(parts))
        self.lyr_lbl.setText("<br>".join(rows))

    def bisect_groups(self, t):
        import bisect
        return bisect.bisect_right(self.lyr_times, t) if hasattr(self, 'lyr_times') else 0

    def save_wav(self):
        path, _ = QFileDialog.getSaveFileName(self, "Zapisz WAV", os.path.expanduser("~/glosy.wav"), "WAV (*.wav)")
        if path:
            write_wav(path, self.render(), self.sr)

    def closeEvent(self, e):
        self.stop()
        super().closeEvent(e)

    def reject(self):
        self.stop()
        super().reject()
