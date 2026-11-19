#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Liber Canticorum – rozpoznawanie nut ze skanu / zdjęcia / PDF (OMR) programem Audiveris.

Audiveris (wolny program, AGPL, https://github.com/Audiveris/audiveris) zamienia obraz nut na MusicXML (.mxl),
który otwiera MuseScore. Liber Canticorum uruchamia go w tle („-batch -export”), a wynik dołącza do pieśni:
z pliku .mxl da się potem odczytać słowa spod nut, zrobić MIDI i nagrania do nauki.
Audiveris trzeba zainstalować osobno (instalator z wbudowaną Javą albo Flatpak na Linuksie).

Licencja: GPL-3.0-or-later.
"""
import glob
import os
import shutil
import sys
import tempfile

from PySide6.QtCore import QProcess, Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                               QProgressBar)

RELEASES = "https://github.com/Audiveris/audiveris/releases"
IMG_EXT = ('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.pdf')


def find_audiveris(custom=""):
    """Polecenie do uruchomienia Audiveris (lista argumentów) albo None."""
    if custom:
        if custom.startswith("flatpak:"):
            return ["flatpak", "run", custom.split(":", 1)[1]]
        if os.path.isfile(custom):
            return [custom]
    for name in ("Audiveris", "audiveris"):
        p = shutil.which(name)
        if p:
            return [p]
    cands = []
    if sys.platform == "win32":
        for pf in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", ""),
                   os.environ.get("LOCALAPPDATA", "")):
            if pf:
                cands += glob.glob(os.path.join(pf, "Audiveris*", "Audiveris.exe"))
                cands += glob.glob(os.path.join(pf, "Audiveris*", "bin", "Audiveris.bat"))
                cands += glob.glob(os.path.join(pf, "Programs", "Audiveris*", "Audiveris.exe"))
    elif sys.platform == "darwin":
        cands += glob.glob("/Applications/Audiveris*.app/Contents/MacOS/Audiveris")
        cands += glob.glob(os.path.expanduser("~/Applications/Audiveris*.app/Contents/MacOS/Audiveris"))
    else:
        cands += glob.glob("/opt/audiveris/bin/Audiveris") + glob.glob("/opt/Audiveris*/bin/Audiveris")
        cands += glob.glob("/usr/local/bin/Audiveris") + glob.glob(os.path.expanduser("~/.local/opt/audiveris/bin/Audiveris"))
    for c in cands:
        if os.path.isfile(c):
            return [c]
    if sys.platform.startswith("linux") and shutil.which("flatpak"):
        try:
            import subprocess
            r = subprocess.run(["flatpak", "info", "org.audiveris.audiveris"], capture_output=True, timeout=10)
            if r.returncode == 0:
                return ["flatpak", "run", "org.audiveris.audiveris"]
        except Exception:
            pass
    return None


def work_dir():
    """Folder roboczy w katalogu domowym (Flatpak widzi pliki w katalogu domowym, nie zawsze w /tmp)."""
    base = os.path.join(os.path.expanduser("~"), ".cache", "LiberCanticorum", "omr")
    os.makedirs(base, exist_ok=True)
    return tempfile.mkdtemp(prefix="omr_", dir=base)


def parse_pages(sheets, n):
    """„3”, „3-4”, „1 3 5” → numery stron od 1 (puste = wszystkie)."""
    out = []
    for part in (sheets or "").replace(",", " ").split():
        a, _, b = part.partition("-")
        try:
            lo, hi = int(a), int(b or a)
        except ValueError:
            continue
        out += [i for i in range(lo, hi + 1) if 1 <= i <= n and i not in out]
    return out or list(range(1, n + 1))


def pdf_is_vector(path, pages=None):
    """True, gdy któraś ze stron PDF nie zawiera obrazu skanu (nuty zapisane wektorowo, np. z MuseScore,
    Sibeliusa, LilyPonda) – Audiveris rozpoznaje tylko obrazy, więc taki PDF trzeba najpierw zrasteryzować."""
    try:
        import pypdfium2 as pdfium
        import pypdfium2.raw as raw
    except ImportError:
        return False
    try:
        doc = pdfium.PdfDocument(path)
        for i in (pages or range(1, len(doc) + 1)):
            page = doc[i - 1]
            w, h = page.get_size()
            area = 0.0
            for obj in page.get_objects(filter=[raw.FPDF_PAGEOBJ_IMAGE], max_depth=4):
                l, b, r, t = obj.get_pos()
                area += max(0.0, r - l) * max(0.0, t - b)
            if area < 0.5 * w * h:                 # brak obrazu na pół strony – to nie jest skan
                return True
        return False
    except Exception:
        return False
    finally:
        try:
            doc.close()
        except Exception:
            pass


def rasterize_pdf(path, out_path, pages=None, dpi=300):
    """Kopia rastrowa PDF (strony jako obrazy w skali szarości, 300 dpi) – do rozpoznawania w Audiveris.
    pages – numery stron od 1 (domyślnie wszystkie). Zwraca liczbę stron."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(path)
    try:
        imgs = []
        for i in (pages or range(1, len(doc) + 1)):
            bmp = doc[i - 1].render(scale=dpi / 72, grayscale=True, fill_color=(255, 255, 255, 255))
            imgs.append(bmp.to_pil().convert("L"))
    finally:
        doc.close()
    if not imgs:
        return 0
    imgs[0].save(out_path, save_all=True, append_images=imgs[1:], resolution=dpi, quality=95)
    return len(imgs)


def sandbox_cmd(cmd, dirs):
    """Audiveris z Flatpaka widzi tylko część katalogu domowego (np. nie ~/.cache): przy uruchomieniu
    dajemy mu dostęp do folderu z plikiem wejściowym i do folderu wyników (flatpak run --filesystem=…)."""
    if len(cmd) >= 3 and os.path.basename(cmd[0]) == "flatpak" and cmd[1] == "run":
        extra = [f"--filesystem={d}" for d in dict.fromkeys(os.path.abspath(d) for d in dirs if d)]
        return cmd[:2] + extra + cmd[2:]
    return list(cmd)


def args_for(src, out_dir, sheets="", lang="pol", variant=0):
    """Argumenty Audiveris. variant: 0 – język OCR przez -constant (5.3+), 1 – przez -option (starsze), 2 – bez."""
    a = ["-batch", "-export", "-output", out_dir]
    key = "org.audiveris.omr.text.Language.defaultSpecification=" + lang
    if lang and variant == 0:
        a += ["-constant", key]
    elif lang and variant == 1:
        a += ["-option", key]
    if sheets:
        a += ["-sheets"] + sheets.replace(",", " ").split()
    return a + ["--", src]


def results(out_dir):
    """Pliki MusicXML zrobione przez Audiveris (także w podfolderach „książki”), w kolejności."""
    found = []
    for ext in ("*.mxl", "*.musicxml", "*.xml"):
        found += glob.glob(os.path.join(out_dir, "**", ext), recursive=True)
    return sorted(set(found))


class OmrDialog(QDialog):
    """Okno z postępem rozpoznawania: uruchamia Audiveris w tle, pokazuje dziennik, można przerwać."""
    finished_ok = Signal(list)                     # lista ścieżek .mxl

    def __init__(self, cmd, src, sheets="", lang="pol", parent=None):
        super().__init__(parent)
        self.cmd, self.src, self.sheets, self.lang = cmd, src, sheets, lang
        self.out = work_dir()
        self.variant = 0 if lang else 2
        self.files = []
        self.setWindowTitle("Rozpoznawanie nut (Audiveris)")
        self.resize(720, 420)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"Rozpoznaję nuty z pliku <b>{os.path.basename(src)}</b>"
                             + (f" (strony {sheets})" if sheets else "") +
                             ". Jedna strona to zwykle 20 s – 2 min.", wordWrap=True))
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        lay.addWidget(self.bar)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        lay.addWidget(self.log, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        self.b = QPushButton("Przerwij")
        self.b.clicked.connect(self.stop)
        row.addWidget(self.b)
        lay.addLayout(row)
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._read)
        self.proc.finished.connect(self._done)
        self.proc.errorOccurred.connect(self._error)
        self._start()

    def _start(self):
        a = args_for(self.src, self.out, self.sheets, self.lang, self.variant)
        cmd = sandbox_cmd(self.cmd, [os.path.dirname(os.path.abspath(self.src)), self.out])
        self.log.appendPlainText("$ " + " ".join(cmd + a))
        self.proc.start(cmd[0], cmd[1:] + a)

    def _read(self):
        t = bytes(self.proc.readAllStandardOutput()).decode('utf-8', 'replace')
        for line in t.splitlines():
            if line.strip():
                self.log.appendPlainText(line.rstrip())

    def _error(self, err):
        if err == QProcess.FailedToStart:
            self.log.appendPlainText("Nie udało się uruchomić Audiveris.")
            self.bar.setRange(0, 1)
            self.b.setText("Zamknij")

    def _done(self, code, _status):
        self.files = results(self.out)
        text = self.log.toPlainText()
        if not self.files and self.variant < 2 and ("Unknown" in text or "unknown" in text or "not a valid" in text
                                                     or "No option" in text or code != 0):
            self.variant += 1                         # starsza / inna wersja – spróbuj inaczej podać język OCR
            self.log.appendPlainText("— ponawiam z innymi ustawieniami —")
            self._start()
            return
        self.bar.setRange(0, 1)
        self.bar.setValue(1)
        self.b.setText("Zamknij")
        if self.files:
            self.log.appendPlainText(f"\nGotowe: {', '.join(os.path.basename(f) for f in self.files)}")
            self.finished_ok.emit(self.files)
            self.accept()
        else:
            self.log.appendPlainText("\nAudiveris nie zwrócił nut. Najczęstsze powody: zbyt mała rozdzielczość "
                                     "(potrzeba ok. 300 dpi), krzywe lub nieostre zdjęcie, rękopis.")

    def stop(self):
        if self.proc.state() != QProcess.NotRunning:
            self.proc.kill()
            self.proc.waitForFinished(3000)
        self.reject()


def install_help(parent):
    """Okno z informacją, jak zainstalować Audiveris."""
    from PySide6.QtWidgets import QMessageBox
    box = QMessageBox(parent)
    box.setWindowTitle("Audiveris – rozpoznawanie nut")
    box.setTextFormat(Qt.RichText)
    box.setText("Do rozpoznawania nut ze skanu potrzebny jest darmowy program <b>Audiveris</b> "
                "(instaluje się osobno, ok. 130 MB, z wbudowaną Javą).<br><br>"
                "<b>Windows / macOS / Ubuntu:</b> pobierz instalator z działu <i>Assets</i> najnowszego wydania "
                "(plik .msi, .dmg albo .deb).<br>"
                "<b>Linux (Flatpak):</b> <code>flatpak install flathub org.audiveris.audiveris</code><br><br>"
                "Po instalacji Liber Canticorum znajdzie go sam; jeśli nie – Ustawienia → Ścieżka do Audiveris.")
    b = box.addButton("Otwórz stronę z instalatorami", QMessageBox.AcceptRole)
    box.addButton(QMessageBox.Close)
    box.exec()
    if box.clickedButton() is b:
        QDesktopServices.openUrl(QUrl(RELEASES))
