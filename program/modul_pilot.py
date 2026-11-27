# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Autorzy projektu Liber Canticorum
"""
Pilot w telefonie dla programu Liber Canticorum.

Program na komputerze uruchamia mały serwer WWW w sieci lokalnej (Wi-Fi). Telefon otwiera stronę
w zwykłej przeglądarce (skanując kod QR) – bez instalowania aplikacji, działa też na iPhonie.
Z telefonu można: przełączać slajdy, widzieć bieżący i następny slajd, wygaszać ekran, włączać
czyste tło, wybierać pieśni z bazy i uruchamiać zestaw.

Dostęp zabezpiecza 6-cyfrowy PIN (zawarty w kodzie QR). Serwer działa tylko, gdy go włączysz.
"""
import json
import os
import random
import socket
import sqlite3
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QRectF, Qt, Signal
from PySide6.QtGui import QFont, QImage, QPainter
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

DEFAULT_PORT = 8765


def local_ip():
    """Adres IP komputera w sieci lokalnej (bez wysyłania czegokolwiek)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        if not ip.startswith("127."):
            return ip
    except OSError:
        pass
    try:
        from PySide6.QtNetwork import QNetworkInterface, QAbstractSocket
        for a in QNetworkInterface.allAddresses():
            if a.protocol() == QAbstractSocket.IPv4Protocol and not a.isLoopback():
                return a.toString()
    except ImportError:
        pass
    return "127.0.0.1"


def fold(text):
    t = (text or "").translate(str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")).lower()
    return " ".join("".join(ch if ch.isalnum() else " " for ch in t).split())


def image_to_jpeg(img, quality=80):
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "JPG", quality)
    return bytes(ba)


def favicon_uri():
    """Ikona programu (64 px) jako data URI – do strony pilota i śpiewnika offline."""
    import base64
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ikony", "liber_canticorum_64.png")
    try:
        with open(path, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
    except OSError:
        return ""


class PilotServer(QObject):
    """Serwer w osobnym wątku. Polecenia trafiają do programu sygnałem `command`
    (Qt dostarcza go w wątku okna); stan i miniatury podaje okno przez `publish()`."""
    command = Signal(dict)
    uploaded = Signal(int, str, bytes)               # id pieśni, nazwa pliku, dane
    songbook_wanted = Signal(str, bool)              # zakres ('all' | 'set'), z nutami
    song_wanted = Signal(int)                        # id pieśni – tekst, akordy i nuty dla widoku muzyka

    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.token = f"{random.SystemRandom().randint(0, 999999):06d}"
        self.lock = threading.Lock()
        self.state = {}
        self.images = []
        self.httpd = None
        self.thread = None
        self.port = None
        self.pdf_lock = threading.Lock()
        self.page_cache = {}                         # id załącznika -> [jpeg]
        self.songbooks = {}                          # (zakres, nuty) -> (bajty, nazwa pliku)
        self.songbook_events = {}
        self.song_cache = {}                         # id pieśni -> słownik dla widoku muzyka
        self.song_events = {}

    def provide_songbook(self, scope, scores, data, filename):
        """Wywołuje okno po zbudowaniu śpiewnika (wątek okna)."""
        key = (scope, scores)
        with self.lock:
            if data:
                self.songbooks[key] = (data, filename)
            ev = self.songbook_events.get(key)
        if ev:
            ev.set()

    def invalidate(self):
        """Baza się zmieniła – śpiewniki i podglądy nut trzeba zbudować od nowa."""
        with self.lock:
            self.songbooks.clear()
            self.page_cache.clear()
            self.song_cache.clear()

    def provide_song(self, sid, data):
        """Wywołuje okno (wątek okna) z danymi pieśni dla widoku muzyka."""
        with self.lock:
            self.song_cache[sid] = data
            ev = self.song_events.get(sid)
        if ev:
            ev.set()

    def _get_song(self, sid, timeout=20):
        with self.lock:
            if sid in self.song_cache:
                return self.song_cache[sid]
            ev = self.song_events.setdefault(sid, threading.Event())
            ev.clear()
        self.song_wanted.emit(sid)
        ev.wait(timeout)
        with self.lock:
            self.song_events.pop(sid, None)
            return self.song_cache.get(sid)

    def _get_songbook(self, scope, scores, timeout=300):
        key = (scope, scores)
        with self.lock:
            if key in self.songbooks:
                return self.songbooks[key]
            ev = self.songbook_events.setdefault(key, threading.Event())
            ev.clear()
        self.songbook_wanted.emit(scope, scores)
        ev.wait(timeout)
        with self.lock:
            self.songbook_events.pop(key, None)
            return self.songbooks.get(key)

    def _attachment(self, aid, with_data=True):
        try:
            con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            row = con.execute(f"SELECT id, song_id, name, kind{', data' if with_data else ''} FROM attachments WHERE id=?",
                              (aid,)).fetchone()
            con.close()
            return row
        except sqlite3.Error:
            return None

    def _pages(self, aid):
        with self.lock:
            if aid in self.page_cache:
                return self.page_cache[aid]
        row = self._attachment(aid)
        if not row:
            return None
        import modul_nuty
        name, data = row[2].lower(), row[4]
        if name.endswith(modul_nuty.SCORE_EXT):            # MuseScore: PDF przeliczony wcześniej w programie
            try:
                con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
                d = con.execute("SELECT pdf FROM derived WHERE att_id=?", (aid,)).fetchone()
                con.close()
            except sqlite3.Error:
                d = None
            if d and d[0]:
                data, name = d[0], name + ".pdf"
            else:
                thumb = modul_nuty.mscz_thumbnail(data)
                data, name = (thumb, "miniatura.png") if thumb else (b"", "")
        if name.endswith((".png", ".jpg", ".jpeg")):
            pages = [data]
        elif name.endswith(".pdf"):
            with self.pdf_lock:
                pages = modul_nuty.pdf_pages_to_jpeg(data, width=1400, quality=78)
        else:
            pages = []
        with self.lock:
            self.page_cache[aid] = pages
        return pages

    # ---------- start / stop
    def start(self, port=DEFAULT_PORT):
        last = None
        for p in range(port, port + 15):
            try:
                self.httpd = ThreadingHTTPServer(("0.0.0.0", p), self._handler())
                self.port = p
                break
            except OSError as e:
                last = e
        if not self.httpd:
            raise RuntimeError(f"Nie można uruchomić serwera: {last}")
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self.url()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None

    @property
    def running(self):
        return self.httpd is not None

    def url(self, with_pin=True):
        u = f"http://{local_ip()}:{self.port}/"
        return u + f"?k={self.token}" if with_pin else u

    # ---------- stan z programu (wątek okna)
    def publish(self, state, images=None):
        with self.lock:
            self.state = state
            if images is not None:
                self.images = images

    # ---------- obsługa HTTP (wątek serwera)
    def _handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "LiberCanticorumPilot/8.0"

            def log_message(self, *a):
                pass

            def _send(self, code, body, ctype="application/json; charset=utf-8", cache=False):
                if isinstance(body, (dict, list)):
                    body = json.dumps(body, ensure_ascii=False).encode("utf-8")
                elif isinstance(body, str):
                    body = body.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "max-age=3600" if cache else "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _authorized(self, qs):
                pin = self.headers.get("X-Pin") or (qs.get("k") or [""])[0]
                return pin == server.token

            def do_GET(self):
                u = urllib.parse.urlparse(self.path)
                qs = urllib.parse.parse_qs(u.query)
                if u.path in ("/", "/index.html"):
                    return self._send(200, PAGE.replace("__FAVICON__", favicon_uri()), "text/html; charset=utf-8")
                if u.path == "/akordy.js":                  # transpozycja akordów – ten sam kod co w śpiewniku offline
                    try:
                        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "akordy.js"), "rb") as f:
                            return self._send(200, f.read(), "text/javascript; charset=utf-8", cache=True)
                    except OSError:
                        return self._send(404, "")
                if not self._authorized(qs):
                    return self._send(401, {"error": "pin"})
                if u.path == "/api/state":
                    with server.lock:
                        return self._send(200, server.state)
                if u.path.startswith("/api/img/"):
                    try:
                        i = int(u.path.rsplit("/", 1)[-1].split(".")[0])
                        with server.lock:
                            data = server.images[i]
                    except (ValueError, IndexError):
                        return self._send(404, {"error": "brak"})
                    return self._send(200, data, "image/jpeg", cache=True)
                if u.path.startswith("/api/song/"):
                    try:
                        sid = int(u.path.rsplit("/", 1)[-1])
                    except ValueError:
                        return self._send(400, {"error": "id"})
                    data = server._get_song(sid)
                    return self._send(200 if data else 404, data or {"error": "brak"})
                if u.path == "/api/songs":
                    return self._send(200, server.search((qs.get("q") or [""])[0]))
                parts = u.path.strip("/").split("/")
                if len(parts) >= 4 and parts[:2] == ["api", "att"] and parts[2].isdigit():
                    aid = int(parts[2])
                    if parts[3] == "pages":
                        pages = server._pages(aid)
                        return self._send(200 if pages is not None else 404, {"pages": len(pages or [])})
                    if parts[3] == "page" and len(parts) == 5:
                        pages = server._pages(aid) or []
                        try:
                            data = pages[int(parts[4].split(".")[0])]
                        except (ValueError, IndexError):
                            return self._send(404, {"error": "brak"})
                        return self._send(200, data, "image/jpeg", cache=True)
                    if parts[3] == "raw":
                        row = server._attachment(aid)
                        if not row:
                            return self._send(404, {"error": "brak"})
                        self.send_response(200)
                        self.send_header("Content-Type", "application/octet-stream")
                        self.send_header("Content-Disposition",
                                         "attachment; filename*=UTF-8''" + urllib.parse.quote(row[2]))
                        self.send_header("Content-Length", str(len(row[4])))
                        self.end_headers()
                        self.wfile.write(row[4])
                        return
                if u.path == "/spiewnik.html":
                    scope = (qs.get("zakres") or ["all"])[0]
                    scores = (qs.get("nuty") or ["0"])[0] == "1"
                    got = server._get_songbook("set" if scope == "set" else "all", scores)
                    if not got or not got[0]:
                        return self._send(503, {"error": "Nie udało się przygotować śpiewnika"})
                    data, fname = got
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(fname))
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                return self._send(404, {"error": "nie ma"})

            def do_POST(self):
                u = urllib.parse.urlparse(self.path)
                qs = urllib.parse.parse_qs(u.query)
                if not self._authorized(qs):
                    return self._send(401, {"error": "pin"})
                if u.path == "/api/upload":
                    try:
                        sid = int((qs.get("song") or ["0"])[0])
                        name = (qs.get("name") or ["plik"])[0][:200].replace("/", "_").replace("\\", "_")
                        n = int(self.headers.get("Content-Length", 0))
                    except ValueError:
                        return self._send(400, {"error": "parametry"})
                    if not sid or n <= 0 or n > 60 * 1024 * 1024:
                        return self._send(400, {"error": "Plik pusty lub większy niż 60 MB"})
                    data = self.rfile.read(n)
                    server.uploaded.emit(sid, name, data)
                    return self._send(200, {"ok": True})
                if u.path != "/api/cmd":
                    return self._send(404, {"error": "nie ma"})
                try:
                    n = min(int(self.headers.get("Content-Length", 0)), 10000)
                    cmd = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
                except ValueError:
                    return self._send(400, {"error": "json"})
                if not isinstance(cmd, dict) or not isinstance(cmd.get("cmd"), str):
                    return self._send(400, {"error": "cmd"})
                server.command.emit(cmd)
                return self._send(200, {"ok": True})

        return Handler

    def search(self, q, limit=60):
        """Wyszukiwanie w osobnym połączeniu SQLite (tylko odczyt, wątek serwera)."""
        words = fold(q).split()
        try:
            con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            sql = "SELECT id, title, kategoria FROM songs"
            if words:
                sql += " WHERE " + " AND ".join(["search LIKE ?"] * len(words))
            rows = con.execute(sql + " ORDER BY search_title LIMIT ?", [f"%{w}%" for w in words] + [limit]).fetchall()
            con.close()
        except sqlite3.Error:
            return []
        ft = fold(q)
        rows.sort(key=lambda r: (0 if ft and fold(r[1]).startswith(ft) else 1, fold(r[1])))
        return [{"id": r[0], "title": r[1], "kategoria": r[2] or ""} for r in rows]


# =====================================================================
# Okno z kodem QR
# =====================================================================

class QrWidget(QWidget):
    def __init__(self, text=""):
        super().__init__()
        self.matrix = []
        self.setMinimumSize(260, 260)
        self.set_text(text)

    def set_text(self, text):
        try:
            import qrcode
            q = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
            q.add_data(text)
            q.make(fit=True)
            self.matrix = q.get_matrix()
        except ImportError:
            self.matrix = []
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), Qt.white)
        if not self.matrix:
            p.drawText(self.rect(), Qt.AlignCenter | Qt.TextWordWrap, "Kod QR wymaga pakietu qrcode\n(pip install qrcode)")
            return
        n = len(self.matrix)
        s = min(self.width(), self.height()) / n
        x0 = (self.width() - s * n) / 2
        y0 = (self.height() - s * n) / 2
        for y, row in enumerate(self.matrix):
            for x, v in enumerate(row):
                if v:
                    p.fillRect(QRectF(x0 + x * s, y0 + y * s, s + 0.5, s + 0.5), Qt.black)
        p.end()


class PilotDialog(QDialog):
    def __init__(self, server, parent=None):
        super().__init__(parent)
        self.server = server
        self.setWindowTitle("Pilot w telefonie")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<b>Zeskanuj kod aparatem telefonu</b> (telefon i komputer w tej samej sieci Wi-Fi):"))
        who = QHBoxLayout()
        self.b_pilot = QPushButton("📱 Prowadzący – pilot pokazu")
        self.b_music = QPushButton("🎼 Muzyk – tablet z tekstem, akordami i nutami")
        for b in (self.b_pilot, self.b_music):
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, b=b: self._who(b))
            who.addWidget(b)
        self.b_pilot.setChecked(True)
        lay.addLayout(who)
        self.qr = QrWidget(server.url())
        lay.addWidget(self.qr, 1)
        self.addr = QLabel()
        self.addr.setTextInteractionFlags(Qt.TextSelectableByMouse)
        f = QFont()
        f.setPointSize(f.pointSize() + 3)
        self.addr.setFont(f)
        lay.addWidget(self.addr)
        lay.addWidget(QLabel(
            "Bez kodu QR: wpisz adres w przeglądarce telefonu i podaj PIN.\n"
            "Brak Wi-Fi? Włącz hotspot w telefonie i połącz z nim komputer.\n"
            "Windows może zapytać o zgodę zapory – zezwól w sieci prywatnej."))
        row = QHBoxLayout()
        b_new = QPushButton("Nowy PIN")
        b_new.clicked.connect(self.new_pin)
        b_stop = QPushButton("Wyłącz pilota")
        b_stop.clicked.connect(self.stop)
        b_close = QPushButton("Zamknij (pilot działa dalej)")
        b_close.clicked.connect(self.accept)
        row.addWidget(b_new)
        row.addWidget(b_stop)
        row.addStretch()
        row.addWidget(b_close)
        lay.addLayout(row)
        try:
            import ikony
            ikony.apply_icons(self)
        except ImportError:
            pass
        self.refresh()

    def _who(self, b):
        self.b_pilot.setChecked(b is self.b_pilot)
        self.b_music.setChecked(b is self.b_music)
        self.refresh()

    def refresh(self):
        music = getattr(self, 'b_music', None) is not None and self.b_music.isChecked()
        self.qr.set_text(self.server.url() + ("&widok=muzyk" if music else ""))
        self.addr.setText(f"Adres: <b>{self.server.url(False)}</b> &nbsp; PIN: <b>{self.server.token}</b>")

    def new_pin(self):
        self.server.token = f"{random.SystemRandom().randint(0, 999999):06d}"
        self.refresh()

    def stop(self):
        self.server.stop()
        self.done(2)


def render_thumbs(deck, paint_slide, width=640):
    """Miniatury JPEG slajdów (wątek okna)."""
    out = []
    for s in deck:
        h = int(width * s.H / s.W)
        img = QImage(width, h, QImage.Format_RGB32)
        img.fill(Qt.black)
        p = QPainter(img)
        paint_slide(p, s, QRectF(0, 0, width, h))
        p.end()
        out.append(image_to_jpeg(img, 78))
    return out


# =====================================================================
# Strona dla telefonu
# =====================================================================

PAGE = r"""<!DOCTYPE html>
<html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#1b1d22">
<title>Pilot – Liber Canticorum</title>
<link rel="icon" href="__FAVICON__">
<style>
:root{--bg:#15171b;--fg:#eceae4;--mut:#9aa0aa;--acc:#d9b45a;--btn:#2a2e36;--red:#b8352c}
[hidden]{display:none!important}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.35 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;height:100%}
header{display:flex;align-items:center;gap:8px;padding:10px 12px;padding-top:max(10px,env(safe-area-inset-top));background:#0e0f12;position:sticky;top:0;z-index:5}
header h1{font-size:15px;margin:0;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dot{width:10px;height:10px;border-radius:50%;background:#666}.dot.on{background:#3bbf5c}
nav{display:flex;background:#0e0f12;border-bottom:1px solid #2a2e36}
nav button{flex:1;background:none;border:0;color:var(--mut);padding:11px 0;font-size:15px}
nav button.act{color:var(--acc);border-bottom:2px solid var(--acc)}
section{display:none;padding:12px}section.act{display:block}
.cur{width:100%;aspect-ratio:16/9;background:#000 center/contain no-repeat;border-radius:8px;border:1px solid #333;touch-action:pan-y}
.meta{display:flex;justify-content:space-between;color:var(--mut);font-size:14px;margin:6px 2px}
.nextw{display:flex;gap:10px;align-items:center;margin:6px 0 10px}
.next{width:38%;aspect-ratio:16/9;background:#000 center/contain no-repeat;border-radius:6px;opacity:.8;border:1px solid #333}
.nav2{display:grid;grid-template-columns:1fr 1.6fr;gap:10px}
.big{font-size:22px;padding:22px 0;border-radius:12px;border:0;background:var(--btn);color:var(--fg);font-weight:600}
.big.go{background:var(--acc);color:#1b1408}
.row{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}
.btn{padding:12px 4px;border-radius:10px;border:0;background:var(--btn);color:var(--fg);font-size:14px}
.btn.on{background:var(--red)}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-top:12px}
.th{position:relative;aspect-ratio:16/9;background:#000 center/contain no-repeat;border-radius:6px;border:2px solid transparent}
.th.sel{border-color:var(--acc)}
.th span{position:absolute;left:4px;top:2px;font-size:12px;background:#0009;padding:0 5px;border-radius:4px}
input{width:100%;padding:12px;border-radius:10px;border:1px solid #3a3f4a;background:#0f1114;color:var(--fg);font-size:16px}
ul{list-style:none;margin:10px 0;padding:0}
li{padding:12px 10px;border-bottom:1px solid #262a31;display:flex;justify-content:space-between;gap:8px;align-items:center}
li small{color:var(--mut)}
li button{flex:none}
#pin{max-width:320px;margin:40px auto;text-align:center}
/* ---- widok muzyka (tablet): tekst / akordy / nuty bieżącej pieśni, rzutnik obok */
#t7{padding:0}
.mu{display:flex;min-height:calc(100vh - 100px)}
.mlist{width:250px;flex:none;border-right:1px solid #262a31;overflow:auto;max-height:calc(100vh - 160px);position:sticky;top:92px}
.mlist div{padding:9px 10px;border-bottom:1px solid #20242a;font-size:14px;cursor:pointer}
.mlist div.now{background:#3a3220;color:var(--acc)}.mlist div.look{outline:1px dashed var(--acc)}
.mlist small{display:block;color:var(--mut);font-size:12px}.mlist .pt{color:var(--acc);font-size:11px;text-transform:uppercase;letter-spacing:.04em;padding:10px 10px 2px;border:0;cursor:default}
.mmain{flex:1;min-width:0;padding:10px 14px 90px}
.mbar{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:8px}
.mbar .seg{display:flex;border-radius:10px;overflow:hidden}.mbar .seg button{border-radius:0}
.mbar .btn.sel{background:var(--acc);color:#1b1408}
.mh{font-size:20px;margin:2px 0 4px}.msub{color:var(--mut);font-size:13px;margin-bottom:8px}
.mnote{border:1px solid #3a3f4a;border-radius:10px;padding:6px 10px;margin:0 0 10px;font-size:15px}.mnote b{color:var(--acc)}
.mtx{font-size:var(--mfs,22px);line-height:1.4}
.mtx .bl{padding:4px 8px;margin:0 -8px 10px;border-radius:8px;border-left:4px solid transparent;transition:background .25s}
.mtx .bl.ref{font-style:italic;color:#f2e6c4}
.mtx .bl.on{background:#2c2a20;border-left-color:var(--acc)}
.mtx .lab{color:var(--mut);font-size:.7em;margin-right:.3em}
.chd{font-size:var(--mfs,22px);line-height:1.25}
.chd .ln{display:flex;align-items:flex-end;gap:1em;min-height:1.3em}.chd .bd{flex:1;min-width:0}
.chd .sg{display:inline-flex;flex-direction:column;vertical-align:bottom}
.chd .c{color:#ff8a65;font-weight:700;font-size:.85em;white-space:pre;padding-right:3px}
.chd .tx{white-space:pre-wrap}.chd .sd{white-space:nowrap;color:#ff8a65;font-weight:700}.chd .gap-line{min-height:.7em}
.msc img{width:100%;display:block;background:#fff;margin-bottom:8px;border-radius:4px}
.mfoot{position:fixed;left:0;right:0;bottom:0;display:flex;gap:8px;align-items:center;padding:8px 10px;padding-bottom:max(8px,env(safe-area-inset-bottom));background:#0e0f12;border-top:1px solid #2a2e36;z-index:6}
.mfoot .big{padding:12px 0;font-size:18px;flex:1}
.mfoot .mini{width:120px;aspect-ratio:16/9;background:#000 center/contain no-repeat;border-radius:4px;border:1px solid #333;flex:none}
@media (max-width:760px){.mlist{display:none}.mfoot .mini{width:80px}}
.msg{position:fixed;left:50%;bottom:20px;transform:translateX(-50%);background:#000d;padding:10px 16px;border-radius:20px;display:none;z-index:9}
</style></head><body>
<div id="pin" hidden><img src="__FAVICON__" width="72" alt=""><h2>Pilot – Liber Canticorum</h2><p>Podaj PIN widoczny w programie na komputerze:</p>
<input id="pinIn" inputmode="numeric" maxlength="6" placeholder="PIN"><p><button class="big go" style="width:100%" onclick="savePin()">Połącz</button></p></div>
<div id="app" hidden>
<header><span class="dot" id="dot"></span><h1 id="title">Liber Canticorum</h1><small id="mode"></small><button class="btn" onclick="tab('t6')">⇩ Offline</button></header>
<nav><button class="act" data-t="t1">Pokaz</button><button data-t="t7">🎼 Muzyk</button><button data-t="t2">Slajdy</button><button data-t="t3">Pieśni</button><button data-t="t5">Nuty</button><button data-t="t4">Zestaw</button></nav>
<section id="t1" class="act">
 <div class="cur" id="cur"></div>
 <div class="meta"><span id="pos"></span><span id="flags"></span></div>
 <div class="nextw"><div class="next" id="next"></div><small style="color:var(--mut)">następny slajd</small></div>
 <div class="nav2"><button class="big" onclick="cmd('prev')">◀</button><button class="big go" onclick="cmd('next')">▶</button></div>
 <div class="row"><button class="btn" id="bBlack" onclick="cmd('black')">Czarny ekran</button><button class="btn" id="bClean" onclick="cmd('clean')">Czyste tło</button><button class="btn" id="bShow" onclick="cmd(S.presenting?'stop':'start')">Start</button></div>
</section>
<section id="t2"><div class="grid" id="grid"></div></section>
<section id="t7"><div class="mu"><div class="mlist" id="mlist"></div><div class="mmain">
 <div class="mbar"><span class="seg"><button class="btn" data-m="text">Tekst</button><button class="btn" data-m="chords">Akordy</button><button class="btn" data-m="scores">Nuty</button></span>
  <button class="btn" onclick="mfs(-2)">A−</button><button class="btn" onclick="mfs(2)">A+</button>
  <span id="mtr" hidden><button class="btn" onclick="mtr(-1)">−½</button> <b id="mkey" style="color:#ff8a65"></b> <button class="btn" onclick="mtr(1)">+½</button><button class="btn" id="mfl" onclick="mflat()">♭</button></span>
  <select id="msel" class="btn" hidden onchange="mScore(+this.value)"></select>
  <button class="btn" id="mback" hidden onclick="mFollow()">↩ Wróć do rzutnika</button>
  <button class="btn" id="mproj" hidden onclick="mProject()">📽 Na rzutnik</button></div>
 <div class="mh" id="mh"></div><div class="msub" id="msub"></div><div id="mnote"></div><div id="mbody"></div></div></div>
 <div class="mfoot"><button class="big" onclick="cmd('prev_song')" title="Poprzednia pieśń">⏮</button><button class="big" onclick="cmd('prev')">◀</button>
  <div class="mini" id="mmini" onclick="tab('t1')"></div><button class="big go" onclick="cmd('next')">▶</button><button class="big" onclick="cmd('next_song')" title="Następna pieśń">⏭</button></div></section>
<section id="t3"><input id="q" placeholder="Szukaj pieśni (tytuł, słowa)…" oninput="search()"><ul id="songs"></ul></section>
<section id="t4"><button class="big go" style="width:100%" onclick="cmd('open_set')">▶ Pokaz całego zestawu</button><ul id="set"></ul></section>
<section id="t5"><div class="meta"><span id="attTitle"></span></div><ul id="atts"></ul>
 <label class="big" style="display:block;text-align:center;margin-top:8px">＋ Dodaj z telefonu (zdjęcie nut, PDF, MIDI…)
 <input type="file" id="up" multiple accept="image/*,application/pdf,.pdf,.mid,.midi,.mscz,.mscx,.musicxml,.mxl,.mp3,.m4a,.ogg,.wav" hidden onchange="upload(this.files)"></label>
 <div id="viewer"></div></section>
<section id="t6"><h3>Śpiewnik offline</h3><p style="color:var(--mut)">Jeden plik HTML – działa bez internetu i bez komputera:
 tekst dla śpiewających, slajdy na pełnym ekranie, nuty dla organisty (przewijanie dotknięciem lub pedałem).
 Po pobraniu otwórz go z „Pobranych” w przeglądarce.</p>
 <label style="display:flex;gap:8px;align-items:center;margin:10px 0"><input type="checkbox" id="withSc" style="width:auto" checked> z nutami (większy plik)</label>
 <button class="big go" style="width:100%;margin-bottom:10px" onclick="dl('all')">⇩ Cały śpiewnik</button>
 <button class="big" style="width:100%" onclick="dl('set')">⇩ Tylko zestaw</button>
 <p id="dlmsg" style="color:var(--mut)"></p></section>
<div id="pv" style="position:fixed;inset:0;background:#fff;z-index:20;display:none" onclick="pvStep(event)"><img id="pvImg" style="width:100%;height:100%;object-fit:contain"><span id="pvCnt" style="position:absolute;left:8px;bottom:6px;color:#555;font-size:13px"></span><button class="btn" style="position:absolute;top:8px;right:8px" onclick="event.stopPropagation();pvClose()">✕</button></div>
</div>
<div class="msg" id="msg"></div>
<script src="/akordy.js"></script>
<script>
const qs=new URLSearchParams(location.search);
let PIN=qs.get('k')||localStorage.getItem('liber_pin')||'';
if(qs.get('k')){localStorage.setItem('liber_pin',PIN);history.replaceState(null,'',location.pathname);}
let S={},ver=null,timer=null;
const $=id=>document.getElementById(id);
function msg(t){const m=$('msg');m.textContent=t;m.style.display='block';clearTimeout(m._t);m._t=setTimeout(()=>m.style.display='none',1800);}
function savePin(){PIN=$('pinIn').value.trim();localStorage.setItem('liber_pin',PIN);start();}
async function api(path,opt={}){opt.headers=Object.assign({'X-Pin':PIN},opt.headers||{});const r=await fetch(path,opt);
 if(r.status==401){$('app').hidden=true;$('pin').hidden=false;clearInterval(timer);throw 'pin';}return r;}
async function cmd(c,arg){try{navigator.vibrate&&navigator.vibrate(12);}catch(e){}
 try{await api('/api/cmd',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cmd:c,arg:arg})});setTimeout(poll,150);}catch(e){if(e!=='pin')msg('Brak połączenia');}}
function img(i){return `url(/api/img/${i}.jpg?v=${S.ver}&k=${PIN})`;}
// ---------------- widok muzyka
const MU={mode:localStorage.getItem('mu_mode')||'text',fs:+(localStorage.getItem('mu_fs')||22),fl:localStorage.getItem('mu_fl')==='1',
 follow:true,look:null,song:null,sver:null,score:0,cache:{}};
document.querySelectorAll('.mbar .seg button').forEach(b=>b.onclick=()=>{MU.mode=b.dataset.m;localStorage.setItem('mu_mode',MU.mode);mDraw();});
function mfs(d){MU.fs=Math.max(14,Math.min(48,MU.fs+d));localStorage.setItem('mu_fs',MU.fs);mDraw();}
function trKey(){return 'mu_tr_'+(MU.song&&MU.song.id);}
function mtr(d){let k=+(localStorage.getItem(trKey())||0);k=((k+d)%12+18)%12-6;localStorage.setItem(trKey(),k);mDraw();}
function mflat(){MU.fl=!MU.fl;localStorage.setItem('mu_fl',MU.fl?'1':'0');mDraw();}
function mFollow(){MU.follow=true;MU.look=null;mSync(true);}
function mProject(){const k=MU.look;if(k===null)return;MU.follow=true;MU.look=null;cmd('goto_entry',k);}
function mList(){const el=$('mlist');const L=S.setlist||[];const N=S.set_notes||[];let h='',last='';
 L.forEach((s,i)=>{const m=/^(.*?): (.*)$/.exec(s.title)||[0,'',s.title];if(m[1]&&m[1]!==last){h+=`<div class="pt">${esc(m[1])}</div>`;last=m[1];}
  const n=N[i]||{};const sub=[n.tonacja&&('Tonacja: '+n.tonacja),n.wykonawca,n.zwroc||n.uwagi].filter(Boolean).join(' · ');
  h+=`<div data-i="${i}" class="${i===S.set_index?'now':''} ${i===MU.look?'look':''}">${esc(m[2])}${sub?`<small>${esc(sub)}</small>`:''}</div>`;});
 if(!L.length)h='<div class="pt" style="text-transform:none">Zestaw jest pusty – tablet pokazuje bieżącą pieśń z rzutnika.</div>';
 el.innerHTML=h;el.querySelectorAll('div[data-i]').forEach(d=>d.onclick=()=>{const i=+d.dataset.i;
  if(i===S.set_index){mFollow();return;}MU.follow=false;MU.look=i;mLoad((S.setlist[i]||{}).id);});}
async function mLoad(id,force){if(!id){MU.song=null;mDraw();return;}
 if(!force&&MU.cache[id]){MU.song=MU.cache[id];MU.score=0;mDraw();return;}
 try{const r=await api('/api/song/'+id);if(!r.ok)throw 0;MU.cache[id]=await r.json();if(MU.follow||MU.look!==null){MU.song=MU.cache[id];MU.score=0;mDraw();}}catch(e){if(e!=='pin')msg('Nie udało się pobrać pieśni');}}
function mSync(force){mList();$('mmini').style.backgroundImage=S.count?img(S.index):'none';
 if(S.song_ver!==MU.sver){MU.sver=S.song_ver;MU.cache={};force=true;}
 if(MU.follow&&(force||!MU.song||MU.song.id!==S.song_id))mLoad(S.song_id,force);
 else if(MU.follow)mHi();}
function fold(t){return String(t||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/ł/g,'l').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();}
function mHi(){const bl=[...document.querySelectorAll('.mtx .bl')];if(!bl.length||!MU.follow)return;
 const items=S.slide_items||[];let first=null;
 bl.forEach(b=>{const f=fold(b.dataset.t);const on=items.some(it=>{const t=fold(it.text).replace(/^\d+ /,'').slice(0,40);
  return t.length>3&&(it.kind==='ref'?b.classList.contains('ref'):!b.classList.contains('ref'))&&f.includes(t.slice(0,25));});
  b.classList.toggle('on',on);if(on&&!first)first=b;});
 if(first&&first!==MU.lastHi){MU.lastHi=first;first.scrollIntoView({behavior:'smooth',block:'center'});}}
async function mScore(i){MU.score=i;mDraw();}
async function mDraw(){const s=MU.song;document.documentElement.style.setProperty('--mfs',MU.fs+'px');
 document.querySelectorAll('.mbar .seg button').forEach(b=>b.classList.toggle('sel',b.dataset.m===MU.mode));
 $('mback').hidden=MU.follow;$('mproj').hidden=MU.follow||MU.look===null;
 const n=(!MU.follow&&MU.look!==null?(S.set_notes||[])[MU.look]:(S.set_notes||[])[S.set_index])||{};
 const NF=[['wykonawca','Wykonawca'],['tonacja','Tonacja'],['uwagi','Uwagi'],['zwroc','Na co zwrócić uwagę']].filter(([f])=>n[f]);
 $('mnote').innerHTML=NF.length?`<div class="mnote">${NF.map(([f,l])=>`<div><b>${l}:</b> ${esc(n[f])}</div>`).join('')}</div>`:'';
 $('mtr').hidden=true;$('msel').hidden=true;
 if(!s){$('mh').textContent='Brak pieśni';$('msub').textContent='Otwórz pieśń albo pokaz zestawu na komputerze.';$('mbody').innerHTML='';return;}
 $('mh').textContent=s.title;$('msub').textContent=[s.cat,s.src].filter(Boolean).join(' · ');
 let mode=MU.mode;const hasCh=window.Chords&&Chords.hasChords(s.chords);
 if(mode==='chords'&&!hasCh)mode='text';if(mode==='scores'&&!(s.scores||[]).length)mode=hasCh?'chords':'text';
 if(mode!==MU.mode)$('msub').textContent+=(MU.mode==='chords'?'  · brak akordów':'  · brak nut')+' – pokazuję '+(mode==='text'?'tekst':'akordy');
 if(mode==='text'){MU.lastHi=null;$('mbody').innerHTML='<div class="mtx">'+s.blocks.map(b=>`<div class="bl ${b.kind}" data-t="${esc(b.lines.join(' '))}">${b.label?`<span class="lab">${esc(b.label)}</span>`:''}${b.lines.map(esc).join('<br>')}</div>`).join('')+'</div>';mHi();}
 else if(mode==='chords'){const k=+(localStorage.getItem(trKey())||0);const txt=k?Chords.transposeText(s.chords,k,MU.fl):s.chords;
  $('mtr').hidden=false;$('mkey').textContent=(Chords.firstChord(txt)||'·')+(k?` (${k>0?'+':''}${k})`:'');$('mfl').classList.toggle('sel',MU.fl);
  $('mbody').innerHTML='<div class="chd">'+Chords.chordproHtml(txt)+'</div>';}
 else{const sc=s.scores[Math.min(MU.score,s.scores.length-1)];
  if(s.scores.length>1){$('msel').hidden=false;$('msel').innerHTML=s.scores.map((a,i)=>`<option value="${i}" ${i===MU.score?'selected':''}>${esc(a.name)}</option>`).join('');}
  $('mbody').innerHTML='<p class="msub">Ładuję nuty…</p>';
  try{const r=await api(`/api/att/${sc.id}/pages`);const n=(await r.json()).pages;
   $('mbody').innerHTML=n?'<div class="msc">'+[...Array(n).keys()].map(i=>`<img loading="lazy" src="/api/att/${sc.id}/page/${i}.jpg?k=${PIN}" alt="strona ${i+1}">`).join('')+'</div>'
    :'<p class="msub">Brak podglądu tych nut – w programie na komputerze zrób podgląd (MuseScore).</p>';}catch(e){}}}
let wakeM=null;async function mWake(on){try{if(on&&!wakeM)wakeM=await navigator.wakeLock.request('screen');if(!on&&wakeM){await wakeM.release();wakeM=null;}}catch(e){}}
function render(){
 $('dot').classList.toggle('on',true);
 $('title').textContent=S.title||'Liber Canticorum';
 $('mode').textContent=S.presenting?(S.set_mode?'ZESTAW':'POKAZ'):'podgląd';
 $('pos').textContent=S.count?`slajd ${S.index+1} / ${S.count}`:'brak slajdów';
 $('flags').textContent=(S.black?'● czarny ':'')+(S.clean?'● czyste tło':'');
 $('bBlack').classList.toggle('on',!!S.black);$('bClean').classList.toggle('on',!!S.clean);
 $('bShow').textContent=S.presenting?'Zakończ pokaz':'Start pokazu';
 $('cur').style.backgroundImage=S.count?img(S.index):'none';
 $('next').style.backgroundImage=(S.index+1<S.count)?img(S.index+1):'none';
 if(S.ver!==ver){ver=S.ver;const g=$('grid');g.innerHTML='';
  for(let i=0;i<S.count;i++){const d=document.createElement('div');d.className='th';d.style.backgroundImage=img(i);
   d.innerHTML=`<span>${i+1}${S.slides&&S.slides[i]?' · '+esc(S.slides[i].song):''}</span>`;d.onclick=()=>{cmd('goto',i);tab('t1');};g.appendChild(d);}}
 [...document.querySelectorAll('.th')].forEach((d,i)=>d.classList.toggle('sel',i===S.index));
 const sl=$('set');sl.innerHTML='';(S.setlist||[]).forEach((s,i)=>{const li=document.createElement('li');
  li.innerHTML=`<span>${i+1}. ${esc(s.title)}</span><button class="btn">Pokaż</button>`;li.querySelector('button').onclick=()=>{cmd('open_song',s.id);tab('t1');};sl.appendChild(li);});
 if(!(S.setlist||[]).length)sl.innerHTML='<li><small>Zestaw jest pusty – ułóż go w programie na komputerze.</small></li>';
 renderAtts();
 if($('t7').classList.contains('act'))mSync();
}
let attVer=null;
function renderAtts(){const key=JSON.stringify([S.song_id,S.attachments]);if(key===attVer)return;attVer=key;
 $('attTitle').textContent=S.song_title?('Nuty: '+S.song_title):'Brak wybranej pieśni';
 const ul=$('atts');ul.innerHTML='';(S.attachments||[]).forEach(a=>{const li=document.createElement('li');
  const view=/\.(pdf|png|jpe?g|mscz|mscx|musicxml|mxl|xml)$/i.test(a.name);
  li.innerHTML=`<span>${esc(a.name)}<br><small>${esc(a.kind)}</small></span><span>${view?'<button class="btn v">Pokaż</button> ':''}<a class="btn" href="/api/att/${a.id}/raw?k=${PIN}">⇩</a></span>`;
  if(view)li.querySelector('.v').onclick=()=>showAtt(a);ul.appendChild(li);});
 if(!(S.attachments||[]).length)ul.innerHTML='<li><small>Ta pieśń nie ma jeszcze nut. Dodaj zdjęcie lub plik poniżej.</small></li>';}
let PV=[],pvi=0;
async function showAtt(a){const r=await api(`/api/att/${a.id}/pages`);const n=(await r.json()).pages;
 if(!n){msg('Brak podglądu – pobierz plik');return;}PV=[...Array(n).keys()].map(i=>`/api/att/${a.id}/page/${i}.jpg?k=${PIN}`);pvi=0;
 $('pv').style.display='block';try{await $('pv').requestFullscreen();}catch(e){}try{window._wl=await navigator.wakeLock.request('screen');}catch(e){}pvDraw();}
function pvDraw(){$('pvImg').src=PV[pvi];$('pvCnt').textContent=`strona ${pvi+1} / ${PV.length}`;}
function pvStep(e){pvi=Math.max(0,Math.min(PV.length-1,pvi+(e.clientX<innerWidth/3?-1:1)));pvDraw();}
function pvClose(){$('pv').style.display='none';if(document.fullscreenElement)document.exitFullscreen().catch(()=>{});if(window._wl)window._wl.release().catch(()=>{});}
async function upload(files){if(!S.song_id){msg('Najpierw wybierz pieśń');return;}
 for(const f of files){msg('Wysyłam: '+f.name);try{await api(`/api/upload?song=${S.song_id}&name=${encodeURIComponent(f.name)}`,{method:'POST',body:f});msg('Dodano: '+f.name);}catch(e){msg('Błąd wysyłania');}}
 $('up').value='';setTimeout(poll,500);}
function dl(scope){$('dlmsg').textContent='Przygotowuję plik – przy dużej bazie z nutami może to potrwać minutę…';
 location.href=`/spiewnik.html?zakres=${scope}&nuty=${$('withSc').checked?1:0}&k=${PIN}`;setTimeout(()=>$('dlmsg').textContent='',15000);}
document.addEventListener('keydown',e=>{if($('pv').style.display!=='block')return;if(['ArrowRight','PageDown',' '].includes(e.key)){pvi=Math.min(PV.length-1,pvi+1);pvDraw();}
 if(['ArrowLeft','PageUp'].includes(e.key)){pvi=Math.max(0,pvi-1);pvDraw();}if(e.key==='Escape')pvClose();},true);
function esc(t){return String(t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
async function poll(){try{const r=await api('/api/state');S=await r.json();render();}catch(e){$('dot').classList.remove('on');}}
let st=null;async function search(){clearTimeout(st);st=setTimeout(async()=>{const r=await api('/api/songs?q='+encodeURIComponent($('q').value));
 const L=await r.json();const ul=$('songs');ul.innerHTML='';L.forEach(s=>{const li=document.createElement('li');
 li.innerHTML=`<span>${esc(s.title)}<br><small>${esc(s.kategoria)}</small></span><button class="btn">Pokaż</button>`;
 li.querySelector('button').onclick=()=>{cmd('open_song',s.id);tab('t1');msg('Otwieram: '+s.title);};ul.appendChild(li);});
 if(!L.length)ul.innerHTML='<li><small>Brak wyników</small></li>';},250);}
function tab(t){document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('act',b.dataset.t===t));
 document.querySelectorAll('section').forEach(s=>s.classList.toggle('act',s.id===t));
 try{localStorage.setItem('pilot_tab',t);}catch(e){}
 mWake(t==='t7');if(t==='t7')mSync(true);}
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{tab(b.dataset.t);if(b.dataset.t==='t3'&&!$('songs').children.length)search();});
let tx=null;$('cur').addEventListener('touchstart',e=>tx=e.touches[0].clientX,{passive:true});
$('cur').addEventListener('touchend',e=>{if(tx===null)return;const dx=e.changedTouches[0].clientX-tx;tx=null;if(Math.abs(dx)>40)cmd(dx<0?'next':'prev');});
document.addEventListener('keydown',e=>{if($('pv').style.display==='block'||e.target.tagName==='INPUT')return;
 if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();cmd(e.ctrlKey?'next_song':'next');}
 if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();cmd(e.ctrlKey?'prev_song':'prev');}});
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'&&$('t7').classList.contains('act'))mWake(true);});
function start(){$('pin').hidden=true;$('app').hidden=false;poll();clearInterval(timer);timer=setInterval(poll,800);
 const t=qs.get('widok')==='muzyk'?'t7':(localStorage.getItem('pilot_tab')||'');if(t&&$(t))setTimeout(()=>tab(t),300);}
if(PIN)start();else $('pin').hidden=false;
</script></body></html>
"""
