# -*- coding: utf-8 -*-
"""Liber Canticorum – wyszukiwanie pieśni w śpiewnikach internetowych i nut w MuseScore.

1. TEKSTY. Program buduje (raz, potem na żądanie odświeża) lokalny spis pieśni ze śpiewników:
     * Śpiewnik ks. Siedleckiego (spiewniksiedleckiego.pl) – działy z pełnymi tekstami,
     * Niezbędnik Katolika – Śpiewnik (niezbednik.niedziela.pl) – spis tytułów, tekst pobierany na żądanie.
   Wyszukiwanie działa w tym spisie (szybko, także bez internetu dla już pobranych tekstów).
2. NUTY. Wyszukiwanie w musescore.com; wyniki są dzielone na: MELODIA (jeden głos, instrument solowy)
   – najpierw, potem ARANŻACJE: chóralne, na organy/fortepian, inne zespoły.
3. DOSTĘPNOŚĆ. Dla całej bazy (albo kategorii): czy tekst jest w śpiewnikach i ile jest nut
   (melodia / aranżacje) – tabela z eksportem do CSV.

Teksty i nuty należą do ich autorów i wydawców; program tylko je wyszukuje i pobiera na prośbę
użytkownika, podając źródło. Licencja: GPL-3.0-or-later.
"""
import html as H
import json
import re
import time
import urllib.parse
import urllib.request

UA = {'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 "
                    "LiberCanticorum/0.12.0", 'Accept-Language': "pl,en;q=0.8",
      'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
_TR = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def fold(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").translate(_TR).lower()).strip()


def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        cs = r.headers.get_content_charset() or 'utf-8'
    return raw.decode(cs, errors='replace')


def _text(html_fragment):
    t = re.sub(r"(?is)<(script|style).*?</\1>", "", html_fragment)
    t = re.sub(r"(?i)<br\s*/?>", "\n", t)
    t = re.sub(r"(?i)</(p|div|h\d|li)>", "\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    return "\n".join(re.sub(r"[ \t\xa0]+", " ", H.unescape(l)).strip() for l in t.split("\n"))


# =====================================================================
# Źródła tekstów
# =====================================================================
class Source:
    key, name, home = "", "", ""

    def build(self, progress=None):
        """→ lista wpisów {'klucz','tytul','url','kategoria','numer','piesn' (słownik lub None)}"""
        raise NotImplementedError

    def fetch_song(self, entry):
        """Pełny tekst pieśni dla wpisu bez tekstu → słownik pieśni."""
        return entry.get('piesn')


class Siedlecki(Source):
    key, name, home = 'siedlecki', "Śpiewnik ks. Siedleckiego", "https://spiewniksiedleckiego.pl/?page_id=17"

    def build(self, progress=None):
        import modul_zbior as zb
        index = get(self.home)
        ids = []
        for pid in re.findall(r"spiewniksiedleckiego\.pl/\?page_id=(\d+)", index):
            if pid not in ids and pid not in ('17', '2632', '15', '10', '4374'):
                ids.append(pid)
        out = []
        for k, pid in enumerate(ids):
            if progress and progress(k, len(ids), f"{self.name}: dział {k + 1} z {len(ids)}") is False:
                break
            url = f"https://spiewniksiedleckiego.pl/?page_id={pid}"
            try:
                raw = get(url)
            except Exception:
                continue
            lines = _html_lines(zb.html_for_collection(raw))
            coll = zb.parse_collection("\n".join(lines), self.name, min_songs=2) or \
                zb.parse_collection("\n".join(_html_lines(raw)), self.name, min_songs=2)
            if not coll:
                continue
            for s in coll['piesni']:
                s['zrodlo'] = url
                out.append({'klucz': f"{pid}:{s['numer']}", 'tytul': s['title'], 'url': url,
                            'kategoria': s.get('kategoria') or coll.get('naglowek', ''), 'numer': str(s['numer']),
                            'piesn': s})
            time.sleep(0.3)                          # grzecznie dla serwera
        return out


class Niezbednik(Source):
    key, name, home = 'niezbednik', "Niezbędnik Katolika – Śpiewnik", "https://niezbednik.niedziela.pl/spiewnik"

    def build(self, progress=None):
        if progress:
            progress(0, 1, f"{self.name}: spis pieśni")
        raw = get(self.home)
        out, seen = [], set()
        for m in re.finditer(r'<a[^>]+href="(/artykul/(\d+)/[^"]+)"[^>]*>(.*?)</a>', raw, re.S):
            url, aid, title = m.group(1), m.group(2), _text(m.group(3)).strip()
            if not title or aid in seen or len(title) > 120:
                continue
            seen.add(aid)
            out.append({'klucz': aid, 'tytul': title, 'url': "https://niezbednik.niedziela.pl" + url,
                        'kategoria': '', 'numer': '', 'piesn': None})
        return out

    def fetch_song(self, entry):
        raw = get(entry['url'])
        m = re.search(r"(?is)<article\b.*?</article>", raw)
        body = m.group(0) if m else raw
        cat = re.findall(r'href="\s*/dzial/\d+/[^"]*"[^>]*>(.*?)</a>', body)
        cat = _text(cat[-1]).strip() if cat else ""
        body = re.sub(r"(?is)^.*?</h1>", "", body)                      # po tytule
        body = re.sub(r"(?is)<h2[^>]*>\s*-\s*</h2>", "", body)
        lines = [l for l in _text(body).split("\n")]
        text = "\n".join(lines).strip()
        song = _parse_plain(entry['tytul'], text)
        song['kategoria'] = "" if cat in ("Śpiewnik", "") else cat
        song['zrodlo'] = entry['url']
        song['uwagi'] = self.name
        return song


SOURCES = {s.key: s for s in (Siedlecki(), Niezbednik())}


def _html_lines(raw):
    from modul_liturgia import html_lines
    return html_lines(raw)


def _parse_plain(title, text):
    """Tekst pieśni (zwrotki „1.”, „Ref.”) → słownik pieśni."""
    ref, verses, cur = [], [], None
    for line in text.split("\n"):
        l = line.strip()
        if not l:
            cur = None if cur == 'ref' else cur
            continue
        m = re.match(r"(?i)^(ref(?:ren)?\.?|refren)\s*:?\s*(.*)$", l)
        if m:
            cur = 'ref'
            if m.group(2) and not ref:
                ref.append(m.group(2))
            continue
        m = re.match(r"^(\d{1,2})\.\s*(.*)$", l)
        if m:
            verses.append([f"{m.group(1)}. {m.group(2)}"])
            cur = 'v'
            continue
        if cur == 'ref' and len(ref) < 12:
            ref.append(l)
        elif verses:
            verses[-1].append(l)
        else:
            verses.append([l])
            cur = 'v'
    return {'title': title, 'refren': "\n".join(ref), 'zwrotki_raw': "\n\n".join("\n".join(v) for v in verses),
            'uwagi': '', 'kategoria': '', 'tagi': '', 'youtube': ''}


# ---------------------------------------------------------------------
# spis w bazie programu
# ---------------------------------------------------------------------
def ensure_table(con):
    con.execute("""CREATE TABLE IF NOT EXISTS spiewniki_spis(
        zrodlo TEXT, klucz TEXT, tytul TEXT, szukaj TEXT, url TEXT, kategoria TEXT, numer TEXT,
        piesn TEXT, pobrano TEXT, PRIMARY KEY(zrodlo, klucz))""")
    con.commit()


def store(con, source_key, entries):
    ensure_table(con)
    now = time.strftime("%Y-%m-%d %H:%M")
    con.execute("DELETE FROM spiewniki_spis WHERE zrodlo=?", (source_key,))
    for e in entries:
        s = e.get('piesn')
        search = fold(e['tytul'] + " " + ((s or {}).get('refren', '') + " " + (s or {}).get('zwrotki_raw', ''))[:3000])
        con.execute("INSERT OR REPLACE INTO spiewniki_spis VALUES (?,?,?,?,?,?,?,?,?)",
                    (source_key, e['klucz'], e['tytul'], search, e['url'], e.get('kategoria', ''), e.get('numer', ''),
                     json.dumps(s, ensure_ascii=False) if s else None, now))
    con.commit()


def index_info(con):
    ensure_table(con)
    return {r[0]: (r[1], r[2]) for r in con.execute(
        "SELECT zrodlo, COUNT(*), MAX(pobrano) FROM spiewniki_spis GROUP BY zrodlo")}


def search(con, query, sources=None, limit=60):
    """→ [{'zrodlo','klucz','tytul','url','kategoria','numer','ma_tekst','trafienie','wynik'}]"""
    ensure_table(con)
    q = fold(query)
    words = [w for w in q.split() if len(w) > 1]
    if not words:
        return []
    cond = " AND ".join("szukaj LIKE ?" for _ in words)
    args = [f"%{w}%" for w in words]
    sql = f"SELECT * FROM spiewniki_spis WHERE {cond}"
    if sources:
        sql += " AND zrodlo IN (%s)" % ",".join("?" * len(sources))
        args += list(sources)
    out = []
    for r in con.execute(sql, args):
        ft = fold(r['tytul'])
        score = 0
        if ft == q:
            score = 100
        elif ft.startswith(q):
            score = 80
        elif all(w in ft for w in words):
            score = 60
        elif q in r['szukaj']:
            score = 40                                 # cała fraza w tekście
        else:
            score = 20
        out.append({'zrodlo': r['zrodlo'], 'klucz': r['klucz'], 'tytul': r['tytul'], 'url': r['url'],
                    'kategoria': r['kategoria'], 'numer': r['numer'], 'ma_tekst': bool(r['piesn']),
                    'wynik': score, 'piesn': json.loads(r['piesn']) if r['piesn'] else None})
    out.sort(key=lambda x: (-x['wynik'], x['tytul']))
    return out[:limit]


def get_song(con, hit):
    """Pełny tekst wyniku (dla źródeł tylko ze spisem tytułów – pobiera stronę i zapamiętuje)."""
    if hit.get('piesn'):
        return hit['piesn']
    src = SOURCES[hit['zrodlo']]
    song = src.fetch_song({'tytul': hit['tytul'], 'url': hit['url']})
    con.execute("UPDATE spiewniki_spis SET piesn=?, szukaj=? WHERE zrodlo=? AND klucz=?",
                (json.dumps(song, ensure_ascii=False),
                 fold(hit['tytul'] + " " + song.get('refren', '') + " " + song.get('zwrotki_raw', ''))[:3000],
                 hit['zrodlo'], hit['klucz']))
    con.commit()
    return song


# =====================================================================
# MuseScore
# =====================================================================
MELODIC = ("voice", "vocals", "flute", "recorder", "violin", "oboe", "clarinet", "trumpet", "synthesizer", "whistle",
           "głos", "flet")
CHOIR = ("choir", "satb", "ssa", "ttbb", "vocal ensemble", "mixed chorus", "chorus", "a cappella", "chór")
KEYS = ("piano", "organ", "harmonium", "keyboard", "fortepian", "organy")
ARR_WORDS = ("arr", "jazz", "reharmoni", "variation", "opracowanie", "harmonizacja", "cover", "duet", "trio",
             "quartet", "kwartet")
GROUP_ORDER = ["Melodia", "Chór", "Organy / fortepian", "Inne aranżacje"]


def classify(title, instr):
    """→ grupa: Melodia | Chór | Organy / fortepian | Inne aranżacje."""
    t, i = title.lower(), (instr or "").lower()
    if any(w in t or w in i for w in CHOIR):
        return "Chór"
    solo = "solo" in i or i.count(",") == 0
    if solo and any(w in i for w in MELODIC) and not any(w in t for w in ARR_WORDS):
        return "Melodia"
    if any(w in t for w in ("melodia", "melody", "unisono", "jednogłos")):
        return "Melodia"
    if any(w in i for w in KEYS) and ("solo" in i or "duet" not in i):
        return "Organy / fortepian"
    return "Inne aranżacje"


def musescore_url(query):
    return "https://musescore.com/sheetmusic?text=" + urllib.parse.quote(query)


def musescore_search(query):
    """→ lista {'tytul','url','obsada','czas','autor','grupa'}; wyjątek, gdy strona nie odpowiada."""
    raw = get(musescore_url(query))
    found = []
    # 1) dane strony w JSON (js-store / __NEXT_DATA__ / inne skrypty)
    for blob in re.findall(r'data-content="([^"]{200,})"', raw):
        try:
            _walk(json.loads(H.unescape(blob)), found)
        except Exception:
            pass
    for blob in re.findall(r'(?s)<script[^>]*type="application/json"[^>]*>(.*?)</script>', raw):
        try:
            _walk(json.loads(blob), found)
        except Exception:
            pass
    # 2) zwykły HTML: kafelki <article>
    if not found:
        for block in re.split(r"(?i)<article\b", raw)[1:]:
            block = block.split("</article>")[0]
            m = re.search(r'href="(https://musescore\.com/(?:user/\d+|[\w.-]+)/scores/\d+)"', block)
            if not m:
                continue
            title = ""
            h = re.search(r"(?is)<h3[^>]*>(.*?)</h3>", block)
            if h:
                title = _text(h.group(1)).strip()
            if not title:
                a = re.search(r'(?is)<img[^>]+alt="([^"]+)"', block)
                title = H.unescape(a.group(1)).split(" sheet music")[0] if a else m.group(1)
            instr = [_text(x).strip() for x in re.findall(r'(?is)href="https://musescore\.com/sheetmusic/[^"]+"[^>]*>(.*?)</a>', block)]
            dur = re.search(r">(\d{1,2}:\d{2})<", block)
            alt = re.search(r'(?is)<img[^>]+alt="[^"]* arranged by ([^"]+?) for ([^"]+)"', block)
            found.append({'tytul': title, 'url': m.group(1), 'obsada': ", ".join(x for x in instr if x) or
                          (H.unescape(alt.group(2)) if alt else ""), 'czas': dur.group(1) if dur else "",
                          'autor': H.unescape(alt.group(1)) if alt else ""})
    uniq, seen = [], set()
    for f in found:
        if f['url'] in seen:
            continue
        seen.add(f['url'])
        f['grupa'] = classify(f['tytul'], f['obsada'])
        uniq.append(f)
    uniq.sort(key=lambda f: GROUP_ORDER.index(f['grupa']))
    return uniq


def _walk(node, out):
    if isinstance(node, dict):
        url = node.get('url')
        if not url and isinstance(node.get('share'), dict):
            url = node['share'].get('url')
        if isinstance(url, str) and "/scores/" in url and node.get('title'):
            instr = node.get('instrumentations') or node.get('instruments') or []
            if isinstance(instr, list):
                instr = ", ".join(str(x.get('name', x)) if isinstance(x, dict) else str(x) for x in instr)
            dur = node.get('duration') or ""
            if isinstance(dur, (int, float)):
                dur = f"{int(dur) // 60}:{int(dur) % 60:02d}"
            out.append({'tytul': str(node['title']), 'url': url if url.startswith("http") else "https://musescore.com" + url,
                        'obsada': str(instr or ""), 'czas': str(dur), 'autor': str((node.get('user') or {}).get('name', ''))
                        if isinstance(node.get('user'), dict) else ""})
        for v in node.values():
            _walk(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk(v, out)


def availability(con, songs, check_scores=True, progress=None):
    """Dostępność dla listy pieśni bazy → [{'id','tytul','teksty','melodia','aranzacje','blad'}]."""
    rows = []
    for k, s in enumerate(songs):
        if progress and progress(k, len(songs), s['title']) is False:
            break
        hits = [h for h in search(con, s['title'], limit=10) if h['wynik'] >= 60]
        row = {'id': s['id'], 'tytul': s['title'],
               'teksty': ", ".join(sorted({SOURCES[h['zrodlo']].name.split(' –')[0] for h in hits})),
               'melodia': "", 'aranzacje': "", 'blad': ""}
        if check_scores:
            try:
                res = musescore_search(s['title'])
                q = fold(s['title'])
                res = [r for r in res if q and (q in fold(r['tytul']) or fold(r['tytul']) in q)]
                row['melodia'] = str(sum(1 for r in res if r['grupa'] == "Melodia"))
                row['aranzacje'] = str(sum(1 for r in res if r['grupa'] != "Melodia"))
            except Exception as e:
                row['blad'] = str(e)[:80]
            time.sleep(1.0)                              # nie obciążaj serwisu
        rows.append(row)
    return rows


# =====================================================================
# Okno
# =====================================================================
try:
    from PySide6.QtCore import Qt, Signal, QUrl
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QTabWidget,
                                   QWidget, QSplitter, QTreeWidget, QTreeWidgetItem, QPlainTextEdit, QCheckBox,
                                   QProgressDialog, QApplication, QFileDialog, QComboBox, QMessageBox)
except ImportError:
    QDialog = object


class SearchDialog(QDialog):
    """Szukaj tekstów w śpiewnikach internetowych, potem nut w MuseScore (najpierw melodia, potem aranżacje)."""
    _ms_done = Signal(object, str)

    def __init__(self, con, query, songs_fn, import_fn, insert_fn, attach_dialog_fn, parent=None):
        super().__init__(parent)
        self.con, self.songs_fn, self.import_fn, self.insert_fn = con, songs_fn, import_fn, insert_fn
        self.attach_dialog_fn = attach_dialog_fn
        ensure_table(con)
        self.setWindowTitle("Szukaj pieśni – śpiewniki internetowe i nuty")
        self.setModal(False)
        self.resize(1150, 720)
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Tytuł lub słowa:"))
        self.q = QLineEdit(query or "")
        self.q.returnPressed.connect(self.search_all)
        top.addWidget(self.q, 1)
        b = QPushButton("Szukaj")
        b.clicked.connect(self.search_all)
        top.addWidget(b)
        lay.addLayout(top)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_texts(), "1. Teksty w śpiewnikach")
        self.tabs.addTab(self._tab_scores(), "2. Nuty w MuseScore (najpierw melodia)")
        self.tabs.addTab(self._tab_avail(), "3. Dostępność dla bazy")
        lay.addWidget(self.tabs, 1)
        self._ms_done.connect(self._ms_results)
        self._refresh_info()
        if query:
            self.search_all()

    # ---------- teksty
    def _tab_texts(self):
        w = QWidget()
        l = QVBoxLayout(w)
        h = QHBoxLayout()
        self.src_cb = {}
        for k, s in SOURCES.items():
            cb = QCheckBox(s.name)
            cb.setChecked(True)
            cb.toggled.connect(self.search_texts)
            self.src_cb[k] = cb
            h.addWidget(cb)
        h.addStretch(1)
        self.info = QLabel()
        self.info.setStyleSheet("color: gray;")
        h.addWidget(self.info)
        bu = QPushButton("Pobierz / odśwież spisy pieśni")
        bu.setToolTip("Pobiera spisy pieśni ze śpiewników (raz na jakiś czas). Śpiewnik ks. Siedleckiego – z tekstami.")
        bu.clicked.connect(self.build_indexes)
        h.addWidget(bu)
        l.addLayout(h)
        sp = QSplitter()
        self.t_tree = QTreeWidget()
        self.t_tree.setHeaderLabels(["Tytuł", "Śpiewnik", "Dział / nr"])
        self.t_tree.setRootIsDecorated(False)
        self.t_tree.setColumnWidth(0, 300)
        self.t_tree.currentItemChanged.connect(self.preview_text)
        self.t_tree.itemDoubleClicked.connect(lambda *_: self.import_text())
        sp.addWidget(self.t_tree)
        self.t_prev = QPlainTextEdit()
        self.t_prev.setReadOnly(True)
        sp.addWidget(self.t_prev)
        sp.setSizes([560, 560])
        l.addWidget(sp, 1)
        bh = QHBoxLayout()
        for txt, fn in (("Importuj jako nową pieśń", self.import_text), ("Wstaw tekst do bieżącej pieśni", self.insert_text),
                        ("Otwórz stronę", self.open_text_page), ("Szukaj nut tej pieśni →", self.to_scores)):
            b = QPushButton(txt)
            b.clicked.connect(fn)
            bh.addWidget(b)
        l.addLayout(bh)
        return w

    def _refresh_info(self):
        inf = index_info(self.con)
        parts = [f"{SOURCES[k].name.split(' –')[0]}: {n} ({d})" for k, (n, d) in inf.items() if k in SOURCES]
        self.info.setText("Spisy: " + ("; ".join(parts) if parts else "jeszcze nie pobrane – kliknij przycisk obok"))

    def build_indexes(self):
        keys = [k for k, cb in self.src_cb.items() if cb.isChecked()]
        pd = QProgressDialog("Pobieram spisy pieśni…", "Przerwij", 0, 100, self)
        pd.setWindowTitle("Spisy śpiewników")
        pd.setMinimumDuration(0)
        errors = []
        for key in keys:
            def prog(i, n, label):
                pd.setLabelText(label)
                pd.setValue(int(100 * i / max(1, n)))
                QApplication.processEvents()
                return not pd.wasCanceled()
            try:
                entries = SOURCES[key].build(prog)
                if entries:
                    store(self.con, key, entries)
            except Exception as e:
                errors.append(f"{SOURCES[key].name}: {e}")
            if pd.wasCanceled():
                break
        pd.close()
        self._refresh_info()
        if errors:
            QMessageBox.warning(self, "Spisy śpiewników", "Nie udało się pobrać:\n" + "\n".join(errors))
        self.search_texts()

    def search_texts(self, *_):
        self.t_tree.clear()
        self.t_prev.clear()
        srcs = [k for k, cb in self.src_cb.items() if cb.isChecked()]
        for h in search(self.con, self.q.text(), srcs):
            it = QTreeWidgetItem([h['tytul'], SOURCES[h['zrodlo']].name.split(' –')[0],
                                  " ".join(x for x in (h['kategoria'], f"nr {h['numer']}" if h['numer'] else "") if x)])
            it.setData(0, Qt.UserRole, h)
            self.t_tree.addTopLevelItem(it)
        if not self.t_tree.topLevelItemCount():
            msg = "Brak wyników." if index_info(self.con) else "Najpierw pobierz spisy pieśni (przycisk u góry)."
            self.t_tree.addTopLevelItem(QTreeWidgetItem([msg, "", ""]))

    def _hit_song(self):
        it = self.t_tree.currentItem()
        h = it.data(0, Qt.UserRole) if it else None
        if not h:
            return None, None
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            return h, get_song(self.con, h)
        except Exception as e:
            self.t_prev.setPlainText(f"Nie udało się pobrać tekstu: {e}")
            return h, None
        finally:
            QApplication.restoreOverrideCursor()

    def preview_text(self, *_):
        h, s = self._hit_song()
        if not s:
            return
        txt = s['title'] + "\n\n" + (("Ref.: " + s['refren'] + "\n\n") if s.get('refren') else "") + s.get('zwrotki_raw', '')
        if s.get('uwagi'):
            txt += "\n\n[uwagi] " + s['uwagi']
        txt += "\n\n[źródło] " + h['url']
        self.t_prev.setPlainText(txt)

    def import_text(self):
        h, s = self._hit_song()
        if s:
            self.import_fn(dict(s, zrodlo=h['url']))

    def insert_text(self):
        h, s = self._hit_song()
        if s:
            self.insert_fn(dict(s, zrodlo=h['url']))

    def open_text_page(self):
        it = self.t_tree.currentItem()
        h = it.data(0, Qt.UserRole) if it else None
        if h:
            QDesktopServices.openUrl(QUrl(h['url']))

    def to_scores(self):
        it = self.t_tree.currentItem()
        h = it.data(0, Qt.UserRole) if it else None
        if h:
            self.q.setText(h['tytul'])
        self.tabs.setCurrentIndex(1)
        self.search_scores()

    # ---------- nuty
    def _tab_scores(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(QLabel("Wyniki z musescore.com: najpierw MELODIA (jeden głos), potem aranżacje – chór, organy/fortepian, "
                           "inne. Dwuklik otwiera nuty w przeglądarce; pobrany plik dołączysz w oknie „Szukaj nut”."))
        self.s_tree = QTreeWidget()
        self.s_tree.setHeaderLabels(["Tytuł", "Obsada", "Czas", "Autor opracowania"])
        self.s_tree.setColumnWidth(0, 380)
        self.s_tree.setColumnWidth(1, 260)
        self.s_tree.itemDoubleClicked.connect(self.open_score)
        l.addWidget(self.s_tree, 1)
        h = QHBoxLayout()
        self.s_info = QLabel()
        self.s_info.setStyleSheet("color: gray;")
        h.addWidget(self.s_info, 1)
        for txt, fn in (("Otwórz zaznaczone", lambda: self.open_score(self.s_tree.currentItem())),
                        ("Wyniki w przeglądarce", lambda: QDesktopServices.openUrl(QUrl(musescore_url(self.q.text())))),
                        ("Dołącz pobrany plik nut…", self.attach_dialog_fn)):
            b = QPushButton(txt)
            b.clicked.connect(fn)
            h.addWidget(b)
        l.addLayout(h)
        return w

    def search_scores(self):
        import threading
        q = self.q.text().strip()
        if not q:
            return
        self.s_tree.clear()
        self.s_info.setText("Szukam w MuseScore…")

        def run():
            try:
                self._ms_done.emit(musescore_search(q), "")
            except Exception as e:
                self._ms_done.emit(None, str(e))
        threading.Thread(target=run, daemon=True).start()

    def _ms_results(self, res, err):
        self.s_tree.clear()
        if res is None:
            self.s_info.setText(f"MuseScore nie odpowiedział programowi ({err}). Kliknij „Wyniki w przeglądarce”.")
            return
        groups = {}
        for r in res:
            g = groups.get(r['grupa'])
            if g is None:
                g = QTreeWidgetItem([r['grupa'], "", "", ""])
                f = g.font(0)
                f.setBold(True)
                g.setFont(0, f)
                g.setFirstColumnSpanned(True) if hasattr(g, 'setFirstColumnSpanned') else None
                self.s_tree.addTopLevelItem(g)
                groups[r['grupa']] = g
            it = QTreeWidgetItem([r['tytul'], r['obsada'], r['czas'], r['autor']])
            it.setData(0, Qt.UserRole, r['url'])
            it.setToolTip(0, r['url'])
            g.addChild(it)
        self.s_tree.expandAll()
        n_mel = len([r for r in res if r['grupa'] == "Melodia"])
        self.s_info.setText(f"Znaleziono {len(res)} – melodia: {n_mel}, aranżacje: {len(res) - n_mel}."
                            if res else "Brak wyników w MuseScore (spróbuj krótszego tytułu albo bez polskich znaków).")

    def open_score(self, it, *_):
        if it and it.data(0, Qt.UserRole):
            QDesktopServices.openUrl(QUrl(it.data(0, Qt.UserRole)))

    def search_all(self):
        self.search_texts()
        self.search_scores()

    # ---------- dostępność dla bazy
    def _tab_avail(self):
        w = QWidget()
        l = QVBoxLayout(w)
        l.addWidget(QLabel("Sprawdza dla pieśni z bazy, czy ich tekst jest w pobranych spisach śpiewników i ile jest nut "
                           "w MuseScore (melodia / aranżacje). Przy wielu pieśniach trwa to kilka minut – zapytania idą "
                           "co sekundę, żeby nie obciążać serwisu."))
        h = QHBoxLayout()
        self.av_scope = QComboBox()
        self.av_scope.addItem("pieśni z bieżącej listy (filtr / wyszukiwanie)", 'list')
        self.av_scope.addItem("wszystkie pieśni w bazie", 'all')
        h.addWidget(self.av_scope)
        self.av_ms = QCheckBox("sprawdzaj też MuseScore")
        self.av_ms.setChecked(True)
        h.addWidget(self.av_ms)
        b = QPushButton("Sprawdź")
        b.clicked.connect(self.check_availability)
        h.addWidget(b)
        b2 = QPushButton("Zapisz CSV…")
        b2.clicked.connect(self.save_csv)
        h.addWidget(b2)
        h.addStretch(1)
        l.addLayout(h)
        self.av_tree = QTreeWidget()
        self.av_tree.setHeaderLabels(["Pieśń", "Tekst w śpiewnikach", "Nuty: melodia", "Nuty: aranżacje", "Uwagi"])
        self.av_tree.setRootIsDecorated(False)
        self.av_tree.setColumnWidth(0, 320)
        self.av_tree.setColumnWidth(1, 260)
        self.av_tree.itemDoubleClicked.connect(lambda it, c: (self.q.setText(it.text(0)), self.tabs.setCurrentIndex(1),
                                                              self.search_all()))
        l.addWidget(self.av_tree, 1)
        return w

    def check_availability(self):
        songs = self.songs_fn(self.av_scope.currentData())
        if not songs:
            return
        pd = QProgressDialog("Sprawdzam…", "Przerwij", 0, len(songs), self)
        pd.setMinimumDuration(0)

        def prog(i, n, label):
            pd.setValue(i)
            pd.setLabelText(label)
            QApplication.processEvents()
            return not pd.wasCanceled()
        rows = availability(self.con, songs, self.av_ms.isChecked(), prog)
        pd.close()
        self.av_tree.clear()
        for r in rows:
            it = QTreeWidgetItem([r['tytul'], r['teksty'] or "—", r['melodia'], r['aranzacje'], r['blad']])
            self.av_tree.addTopLevelItem(it)
        self.av_rows = rows

    def save_csv(self):
        rows = getattr(self, 'av_rows', None)
        if not rows:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Zapisz CSV", "dostepnosc_piesni.csv", "CSV (*.csv)")
        if not path:
            return
        import csv
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f, delimiter=';')
            w.writerow(["Pieśń", "Tekst w śpiewnikach", "Nuty: melodia", "Nuty: aranżacje", "Uwagi"])
            for r in rows:
                w.writerow([r['tytul'], r['teksty'], r['melodia'], r['aranzacje'], r['blad']])
