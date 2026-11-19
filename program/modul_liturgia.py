# -*- coding: utf-8 -*-
"""Liber Canticorum – liturgia dnia.

* okres liturgiczny i rok czytań wyliczane z daty (bez internetu),
* pobieranie tekstów Mszy z dnia: antyfony, kolekta, czytania, psalm, aklamacja, Ewangelia,
  modlitwa nad darami, prefacja, modlitwa po Komunii – ze stron:
    - gregorianski.pl/mszalik (pełny mszalik),
    - niezbednik.niedziela.pl (czytania),
    - opoka.org.pl/liturgia (czytania),
* wyszukiwanie w bazie pieśni nawiązujących do słów i fraz z liturgii.

Teksty liturgiczne należą do ich wydawców (Lekcjonarz, Mszał – Pallottinum / KEP); program ich nie
rozpowszechnia – pobiera je na bieżąco ze stron źródłowych, jak przeglądarka, i trzyma w bazie użytkownika.
Licencja kodu: GPL-3.0-or-later.
"""
import datetime
import html
import json
import re
import urllib.request
from html.parser import HTMLParser

# ---------------------------------------------------------------------
# kalendarz
# ---------------------------------------------------------------------
OKRESY = ["Adwent", "Okres Narodzenia Pańskiego", "Okres zwykły", "Wielki Post", "Triduum Paschalne",
          "Okres wielkanocny"]
# okres → kategoria pieśni w bazie (do podpowiedzi)
OKRES_KATEGORIA = {"Adwent": "Adwent", "Okres Narodzenia Pańskiego": "Boże Narodzenie",
                   "Wielki Post": "Wielki Post", "Triduum Paschalne": "Triduum Paschalne",
                   "Okres wielkanocny": "Wielkanoc", "Okres zwykły": "Okres zwykły"}


def wielkanoc(rok):
    """Niedziela Wielkanocna (algorytm Meeusa/Jonesa/Butchera)."""
    a, b, c = rok % 19, rok // 100, rok % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mies = (h + l - 7 * m + 114) // 31
    dzien = ((h + l - 7 * m + 114) % 31) + 1
    return datetime.date(rok, mies, dzien)


def poczatek_adwentu(rok):
    """I niedziela Adwentu: czwarta niedziela przed Bożym Narodzeniem."""
    bn = datetime.date(rok, 12, 25)
    ostatnia_ndz = bn - datetime.timedelta(days=(bn.weekday() + 1) % 7 or 7)
    return ostatnia_ndz - datetime.timedelta(weeks=3)


def chrzest_panski(rok):
    """Niedziela po 6 stycznia (w Polsce Objawienie Pańskie 6 I)."""
    d = datetime.date(rok, 1, 7)
    while d.weekday() != 6:
        d += datetime.timedelta(days=1)
    return d


def okres_liturgiczny(d):
    """→ {'okres', 'rok_niedzielny' (A/B/C), 'rok_powszedni' (I/II), 'opis'}"""
    if isinstance(d, datetime.datetime):
        d = d.date()
    w = wielkanoc(d.year)
    adw = poczatek_adwentu(d.year)
    rok_lit = d.year + 1 if d >= adw else d.year
    if d >= adw and d < datetime.date(d.year, 12, 25):
        okres = "Adwent"
    elif d >= datetime.date(d.year, 12, 25) or d <= chrzest_panski(d.year):
        okres = "Okres Narodzenia Pańskiego"
    elif w - datetime.timedelta(days=46) <= d < w - datetime.timedelta(days=3):
        okres = "Wielki Post"
    elif w - datetime.timedelta(days=3) <= d <= w:
        okres = "Triduum Paschalne"
    elif w < d <= w + datetime.timedelta(days=49):
        okres = "Okres wielkanocny"
    else:
        okres = "Okres zwykły"
    rn = {1: "A", 2: "B", 0: "C"}[rok_lit % 3]
    rp = "I" if rok_lit % 2 else "II"
    return {'okres': okres, 'rok_niedzielny': rn, 'rok_powszedni': rp,
            'opis': f"{okres}, rok {rn}, {rp}"}


# ---------------------------------------------------------------------
# pobieranie i odczyt stron
# ---------------------------------------------------------------------
SOURCES = {
    'gregorianski': ("gregorianski.pl – mszalik (antyfony, kolekta, prefacja, czytania)",
                     "https://gregorianski.pl/mszalik/{d}"),
    'niezbednik': ("niezbednik.niedziela.pl – czytania", "https://niezbednik.niedziela.pl/liturgia/{d}"),
    'opoka': ("opoka.org.pl – czytania", "https://opoka.org.pl/liturgia/{d}"),
}
SECTIONS = [  # klucz, nazwa, wzorzec nagłówka (po złożeniu do małych liter)
    ('ant_wej', "Antyfona na wejście", r"antyfona na wej[sś]cie"),
    ('kolekta', "Kolekta", r"kolekta"),
    ('czyt1', "Pierwsze czytanie", r"(pierwsze czytanie|1\.\s*czytanie|i czytanie)"),
    ('psalm', "Psalm responsoryjny", r"psalm( responsoryjny)?"),
    ('czyt2', "Drugie czytanie", r"(drugie czytanie|2\.\s*czytanie|ii czytanie)"),
    ('sekwencja', "Sekwencja", r"sekwencja"),
    ('aklamacja', "Aklamacja przed Ewangelią",
     r"(aklamacja( przed ewangeli[aą])?|werset przed ewangeli[aą]( \(alleluja\))?|[sś]piew przed ewangeli[aą])"),
    ('ewangelia', "Ewangelia", r"ewangelia( na dzi[sś])?"),
    ('dary', "Modlitwa nad darami", r"modlitwa nad darami"),
    ('prefacja', "Prefacja", r"prefacja"),
    ('ant_kom', "Antyfona na Komunię", r"antyfona na komuni[eęi]"),
    ('po_kom', "Modlitwa po Komunii", r"modlitwa po komunii"),
]
SECTION_NAMES = {k: n for k, n, _ in SECTIONS}
_HEAD_RE = [(k, re.compile(r"^(?:" + p + r")\s*(?:\((?P<ref>.*)\))?\s*$", re.I)) for k, _, p in SECTIONS]
_STOP_RE = re.compile(r"^(homilie|polecamy|rozwa[żz]ania|je[żz]eli chcesz|czytania na \d|informacje o serwisie|"
                      r"\^ na g[oó]r[eę]|wybierz dzie[nń]|komentarz|z [żz]ycia ko[sś]cio[łl]a|pom[oó][żz] w rozwoju|"
                      r"liturgia godzin|czytania liturgiczne pochodz)", re.I)
_REF_RE = re.compile(r"^\(?\s*(por\.\s*)?[1-3]?\s?[A-ZŁŚŻ][a-ząćęłńóśźż]{0,5}\.?\s*\d+\s*(\(\d+\))?\s*[,:]\s*\d")

UA = {'User-Agent': "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 "
                    "LiberCanticorum/0.15.1", 'Accept-Language': "pl,en;q=0.8"}


class _Lines(HTMLParser):
    """HTML → wiersze tekstu (nowy wiersz przy elementach blokowych); pomija skrypty i style."""
    BLOCK = {'p', 'div', 'br', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'section', 'article',
             'header', 'footer', 'blockquote', 'dt', 'dd', 'td', 'th', 'ul', 'ol', 'table', 'span_block'}
    SKIP = {'script', 'style', 'noscript', 'svg', 'iframe', 'template', 'button', 'select'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag == 'br':
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)

    def lines(self):
        txt = "".join(self.out).replace("\xa0", " ")
        return [re.sub(r"[ \t]+", " ", l).strip() for l in txt.split("\n") if l.strip()]


def html_lines(raw):
    p = _Lines()
    p.feed(raw)
    p.close()
    return p.lines()


def _section_of(line):
    t = line.strip().rstrip('.')
    if len(t) > 90 or t.endswith(':'):
        return None, None
    for k, rx in _HEAD_RE:
        m = rx.match(t)
        if m:
            ref = (m.group('ref') or "").strip()
            return k, (ref if re.search(r"\d", ref) else "")
    return None, None


def parse_lines(lines):
    """Wiersze strony → {klucz: {'naglowek', 'sigla', 'tekst', 'refren'}} + metadane."""
    found = {}
    cur, buf, ref = None, [], ""

    def close():
        if cur is None:
            return
        body = [l for l in buf]
        sig = ref
        # sigla w osobnym wierszu tuż po nagłówku: „( Ez 34, 11-12 )”
        if body and _REF_RE.match(body[0]) and len(body[0]) < 100:
            sig = sig or re.sub(r"^\(\s*(.*?)\s*\)$", r"\1", body[0].strip())
            body = body[1:]
        text = "\n".join(body).strip()
        if len(text) >= 25 and cur not in found:      # pierwsze niepuste wystąpienie (zakładki bywają puste)
            found[cur] = {'naglowek': SECTION_NAMES[cur], 'sigla': sig, 'tekst': text}

    for line in lines:
        if _STOP_RE.match(line):
            close()
            cur, buf, ref = None, [], ""
            continue
        k, r = _section_of(line)
        if k:
            close()
            cur, buf, ref = k, [], r
            continue
        if cur:
            buf.append(line)
    close()
    for k, s in found.items():
        s['refren'] = _refrain(s['tekst'], k)
        if k == 'aklamacja':
            s['werset'] = "\n".join(l for l in s['tekst'].split("\n") if not re.match(r"(?i)^(alleluja|chwała tobie|refren)", l))
    meta = {}
    for line in lines[:400]:
        m = re.match(r"^\d{4}-\d{2}-\d{2}:\s*(.+)$", line)
        if m:
            meta['dzien'] = m.group(1).strip()
            break
    for line in lines[:400]:
        m = re.search(r"(?i)kolor(?: szat)?:\s*([a-ząćęłńóśźż]+)", line)
        if m and 'kolor' not in meta:
            meta['kolor'] = m.group(1).lower()
        m = re.match(r"(?i)^(uroczysto[sś][cć]|[sś]wi[eę]to|wspomnienie|niedziela|.*niedziela (zwyk[łl]a|adwentu|wielkiego postu|wielkanocna)).{3,120}$", line)
        if m and 'dzien' not in meta and not line.endswith(':'):
            meta['dzien'] = line.strip()
    return found, meta


def _refrain(text, key):
    """Refren psalmu = wiersz powtarzający się kilka razy (albo oznaczony „Refren:”)."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for l in lines:
        m = re.match(r"(?i)^(refren|r\.)\s*:?\s*(.+)$", l)
        if m and len(m.group(2)) > 3:
            return m.group(2).strip()
    if key not in ('psalm', 'aklamacja'):
        return ""
    counts = {}
    for l in lines:
        counts[l] = counts.get(l, 0) + 1
    rep = [l for l in lines if counts[l] >= 2 and len(l) > 6]
    return rep[0] if rep else ""


def fetch(date, source='gregorianski', timeout=20):
    """Pobiera liturgię dnia. → {'zrodlo', 'url', 'data', 'sekcje', 'meta'}"""
    d = date.isoformat() if hasattr(date, 'isoformat') else str(date)
    url = SOURCES[source][1].format(d=d)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode(r.headers.get_content_charset() or 'utf-8', errors='replace')
    secs, meta = parse_lines(html_lines(raw))
    if not secs:
        raise RuntimeError("Nie znalazłem tekstów liturgii na stronie (zmienił się jej układ?).")
    return {'zrodlo': source, 'url': url, 'data': d, 'sekcje': secs, 'meta': meta}


def fetch_any(date, order=('gregorianski', 'niezbednik', 'opoka')):
    """Próbuje kolejnych źródeł; czytania uzupełnia z następnych, jeśli w pierwszym ich brak."""
    errors, result = [], None
    for src in order:
        try:
            r = fetch(date, src)
        except Exception as e:
            errors.append(f"{src}: {e}")
            continue
        if result is None:
            result = r
        else:
            for k, v in r['sekcje'].items():
                result['sekcje'].setdefault(k, dict(v, zrodlo=src))
            for k, v in r['meta'].items():
                result['meta'].setdefault(k, v)
        if all(k in result['sekcje'] for k in ('czyt1', 'psalm', 'ewangelia')):
            break
    if result is None:
        raise RuntimeError("Nie udało się pobrać liturgii:\n" + "\n".join(errors))
    result['bledy'] = errors
    return result


# ---------------------------------------------------------------------
# dopasowanie pieśni
# ---------------------------------------------------------------------
_TR = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
STOP = set("""a aby ach albo ale ani az bo by byc byl byla bylo byly bede bedzie beda bez bo co czy dla do gdy gdyz go
i ich im ja jak jako je jego jej jest jestem jestes jesli juz kiedy kto ktora ktore ktorego ktorej ktory ktorzy ku
ma mam mi mna mnie moj moja moje mu my na nad nam nas nasz nasza nasze nie niech niego niej nim niz no o od on ona
one oni ono oraz po pod przez przy sa sie swoj swoja swoje swych ta tak take tam te tego tej ten to tobie toba ty
tych tylko tym u w we wam was wasz wszystko wszyscy wszystkich wy z za ze zas ze zeby oto lecz wiec bowiem tez
alleluja amen r refren""".split())
# słowa bardzo częste w pieśniach i liturgii – małą wagę dają same
COMMON = set("pan pana panu panie pane bog boga bogu boze jezus jezu chryst ducha duch swiet zawsz wszed ojcze ojca".split())


def _norm(s):
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").translate(_TR).lower())


def stem(w):
    return w[:5] if len(w) > 5 else w


def tokens(text):
    """[(rdzeń, słowo_oryginalne)] bez słów nieistotnych."""
    out = []
    for orig in re.findall(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+", text or ""):
        w = _norm(orig).strip()
        if len(w) >= 3 and w not in STOP:
            out.append((stem(w), orig))
    return out


# która część liturgii podpowiada którą część Mszy
SECTION_TO_PART = {'ant_wej': ["Wejście"], 'kolekta': ["Wejście"], 'czyt1': ["Ofiarowanie", "Wyjście"],
                   'psalm': ["Ofiarowanie", "Komunia"], 'czyt2': ["Ofiarowanie", "Uwielbienie"],
                   'aklamacja': ["Uwielbienie", "Komunia"], 'ewangelia': ["Komunia", "Uwielbienie", "Ofiarowanie"],
                   'dary': ["Ofiarowanie"], 'prefacja': ["Uwielbienie"], 'ant_kom': ["Komunia"],
                   'po_kom': ["Uwielbienie", "Wyjście"], 'sekwencja': ["Uwielbienie"]}
SECTION_WEIGHT = {'ant_wej': 1.3, 'psalm': 1.4, 'ewangelia': 1.3, 'ant_kom': 1.3, 'aklamacja': 1.1,
                  'czyt1': 1.0, 'czyt2': 0.9, 'kolekta': 0.9, 'dary': 0.8, 'prefacja': 0.8, 'po_kom': 0.8,
                  'sekwencja': 1.0}


MATCH_MODES = [  # (nazwa, min. długość frazy w słowach, waga pojedynczych słów, próg)
    ("Szeroko – pojedyncze słowa i krótkie frazy (więcej propozycji)", 2, 1.3, 0.08),
    ("Zrównoważone – słowa i frazy (zalecane)", 2, 1.0, 0.15),
    ("Frazy – co najmniej 3 kolejne słowa z liturgii", 3, 0.5, 0.3),
    ("Ściśle – tylko długie frazy (4+ słowa), najtrafniejsze", 4, 0.2, 0.4),
]


def suggest(liturgy, songs, okres=None, limit=40, mode=1, okres_only=False):
    """songs: [{'id','title','refren','zwrotki_raw' lub 'zwrotki','kategoria','tagi'}]
    → [{'id','title','score','parts','frazy': [(sekcja, fraza)], 'okres': bool}] od najlepszej."""
    import math
    _, min_run, word_w, thr = MATCH_MODES[max(0, min(len(MATCH_MODES) - 1, mode))]
    docs = []
    df = {}
    for s in songs:
        text = " \n".join([s.get('title') or "", s.get('refren') or "", s.get('zwrotki_raw') or s.get('zwrotki') or ""])
        tk = tokens(text)
        stems = [t for t, _ in tk]
        st = set(stems)
        for t in st:
            df[t] = df.get(t, 0) + 1
        bigr = {(stems[i], stems[i + 1]) for i in range(len(stems) - 1)}
        orig = {}
        for t, o in tk:
            orig.setdefault(t, o)
        docs.append((s, st, bigr, orig))
    n = max(1, len(docs))
    idf = {t: math.log(1 + n / c) for t, c in df.items()}
    secs = liturgy.get('sekcje', {})
    lit = []
    for k, sec in secs.items():
        txt = sec.get('tekst', '')
        if k == 'psalm' and sec.get('refren'):
            txt += ("\n" + sec['refren']) * 3            # refren psalmu liczy się mocniej
        tk = tokens(txt)
        lit.append((k, tk, [t for t, _ in tk]))
    kat = OKRES_KATEGORIA.get(okres or "", "")
    out = []
    for s, st, bigr, orig in docs:
        score, parts, frazy = 0.0, {}, []
        for k, tk, stems in lit:
            w = SECTION_WEIGHT.get(k, 1.0)
            hit = {t for t in stems if t in st}
            if not hit:
                continue
            sc = sum(idf.get(t, 0) * (0.3 if t in COMMON else 1.0) for t in hit) * w * word_w
            # frazy: kolejne słowa liturgii występujące obok siebie w pieśni
            best = []
            run = []
            for i, (t, o) in enumerate(tk):
                if run and (run[-1][0], t) in bigr:
                    run.append((t, o))
                else:
                    if len(run) >= min_run:
                        best.append(run)
                    run = [(t, o)] if t in st else []
            if len(run) >= min_run:
                best.append(run)
            ph = 0.0
            seen = set()
            for r in best:
                key = tuple(t for t, _ in r)
                if key in seen or all(t in COMMON for t in key):      # „Pan Bóg” sam niczego nie znaczy
                    continue
                seen.add(key)
                ph += 2.5 * (len(r) - 1) * sum(idf.get(t, 0) for t, _ in r) / len(r)
                frazy.append((k, " ".join(o for _, o in r)))
            sc = (sc + ph * w) / (1 + 0.15 * len(stems) ** 0.5) / (1 + 0.12 * len(st) ** 0.5)
            score += sc
            for p in SECTION_TO_PART.get(k, []):
                parts[p] = parts.get(p, 0) + sc
        is_okres = bool(kat) and (s.get('kategoria') or "") == kat
        if okres_only and not is_okres:
            continue
        if min_run >= 3 and not frazy:                       # tryb „frazy”: same pojedyncze słowa nie wystarczą
            continue
        if is_okres:
            score += 0.4
        if score <= thr:
            continue
        frazy.sort(key=lambda f: -len(f[1]))
        out.append({'id': s.get('id'), 'title': s.get('title'), 'score': round(score, 2),
                    'parts': [p for p, _ in sorted(parts.items(), key=lambda x: -x[1])][:2],
                    'frazy': frazy[:4], 'okres': is_okres})
    out.sort(key=lambda r: -r['score'])
    return out[:limit]


def liturgy_text(lit, sections=None, with_refs=True):
    """Liturgia jako tekst (do eksportu)."""
    out = []
    for k, name, _ in SECTIONS:
        if sections and k not in sections:
            continue
        s = lit.get('sekcje', {}).get(k)
        if not s:
            continue
        out.append(name + (f" ({s['sigla']})" if with_refs and s.get('sigla') else ""))
        out.append(s['tekst'])
        out.append("")
    return "\n".join(out).strip()


# ---------------------------------------------------------------------
# okno: liturgia dnia + propozycje pieśni
# ---------------------------------------------------------------------
try:
    from PySide6.QtCore import Qt, Signal, QUrl
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QLabel, QSplitter,
                                   QTextBrowser, QTreeWidget, QTreeWidgetItem, QWidget, QCheckBox, QApplication)
except ImportError:                                   # moduł działa też bez Qt (testy, skrypty)
    QDialog = object


class LiturgyDialog(QDialog):
    """Teksty Mszy z dnia i pieśni z bazy, które do nich nawiązują."""
    _done = Signal(object, str)

    def __init__(self, date, db, songs_fn, okres, parts, add_fn, open_fn, parent=None):
        super().__init__(parent)
        self.date, self.db, self.songs_fn, self.okres = date, db, songs_fn, okres
        self.add_fn, self.open_fn = add_fn, open_fn
        self.lit = None
        self.setWindowTitle(f"Liturgia dnia {date.strftime('%d.%m.%Y')} – propozycje pieśni")
        self.resize(1250, 780)
        from PySide6.QtCore import QSettings, QDate, QLocale
        from PySide6.QtWidgets import QDateEdit
        self.qs = QSettings("LiberCanticorum", "LiberCanticorum")
        lay = QVBoxLayout(self)
        # wybór dnia: ◀ / kalendarz (dzień, miesiąc, rok) / ▶ / Dziś
        nav = QHBoxLayout()
        for txt, d, tip in (("◀◀", -7, "Tydzień wcześniej"), ("◀", -1, "Dzień wcześniej")):
            b = QPushButton(txt)
            b.setToolTip(tip)
            b.setFixedWidth(46)
            b.clicked.connect(lambda _=False, d=d: self.shift(d))
            nav.addWidget(b)
        self.dedit = QDateEdit(QDate(date.year, date.month, date.day))
        self.dedit.setCalendarPopup(True)
        self.dedit.setDisplayFormat("dddd, d MMMM yyyy")
        self.dedit.setLocale(QLocale(QLocale.Polish, QLocale.Poland))
        self.dedit.setToolTip("Wybierz dzień z kalendarza albo zmień dzień, miesiąc i rok strzałkami / kółkiem myszy")
        self.dedit.setStyleSheet("font-size: 13pt; padding: 3px;")
        self.dedit.dateChanged.connect(lambda q: self.set_date(q.toPython()))
        nav.addWidget(self.dedit)
        for txt, d, tip in (("▶", 1, "Dzień później"), ("▶▶", 7, "Tydzień później")):
            b = QPushButton(txt)
            b.setToolTip(tip)
            b.setFixedWidth(46)
            b.clicked.connect(lambda _=False, d=d: self.shift(d))
            nav.addWidget(b)
        b = QPushButton("Dziś")
        b.clicked.connect(lambda: self.dedit.setDate(QDate.currentDate()))
        nav.addWidget(b)
        b = QPushButton("Najbliższa niedziela")
        b.clicked.connect(self.next_sunday)
        nav.addWidget(b)
        nav.addStretch(1)
        lay.addLayout(nav)
        top = QHBoxLayout()
        info = okres_liturgiczny(date)
        self.head = QLabel(f"<b>{date.strftime('%d.%m.%Y')}</b> – {info['opis']}")
        top.addWidget(self.head, 1)
        top.addWidget(QLabel("Źródło:"))
        self.src = QComboBox()
        self.src.addItem("Automatycznie (najpierw pełny mszalik)", 'auto')
        for k, (name, _) in SOURCES.items():
            self.src.addItem(name, k)
        top.addWidget(self.src)
        self.b_fetch = QPushButton("Pobierz")
        self.b_fetch.clicked.connect(self.fetch)
        top.addWidget(self.b_fetch)
        self.b_web = QPushButton("Otwórz stronę")
        self.b_web.clicked.connect(self.open_web)
        top.addWidget(self.b_web)
        lay.addLayout(top)
        sp = QSplitter()
        self.text = QTextBrowser()
        self.text.setOpenExternalLinks(True)
        sp.addWidget(self.text)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(QLabel("<b>Pieśni z bazy nawiązujące do liturgii</b> (★ = z kategorii okresu)"))
        mrow = QHBoxLayout()
        mrow.addWidget(QLabel("Dopasowanie:"))
        self.mode = QComboBox()
        for name, *_ in MATCH_MODES:
            self.mode.addItem(name)
        self.mode.setToolTip("Szeroko – więcej propozycji (także pojedyncze wspólne słowa).\n"
                             "Frazy / ściśle – tylko pieśni, w których powtarzają się całe zwroty z czytań, psalmu, antyfon.")
        self.mode.setCurrentIndex(int(self.qs.value("lit_match_mode", 1)))
        self.mode.currentIndexChanged.connect(lambda i: (self.qs.setValue("lit_match_mode", i), self.suggest()))
        mrow.addWidget(self.mode, 1)
        rl.addLayout(mrow)
        frow = QHBoxLayout()
        self.only = QCheckBox("Pokaż też słabsze dopasowania")
        self.only.toggled.connect(self.suggest)
        frow.addWidget(self.only)
        self.okres_only = QCheckBox("Tylko pieśni z kategorii okresu")
        self.okres_only.setChecked(self.qs.value("lit_okres_only", "false") == "true")
        self.okres_only.toggled.connect(lambda on: (self.qs.setValue("lit_okres_only", on), self.suggest()))
        frow.addWidget(self.okres_only)
        frow.addStretch(1)
        rl.addLayout(frow)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Pieśń", "Pasuje do", "Nawiązania (słowa i frazy z liturgii)"])
        self.tree.setRootIsDecorated(False)
        self.tree.setColumnWidth(0, 230)
        self.tree.setColumnWidth(1, 120)
        self.tree.itemDoubleClicked.connect(lambda it, c: self.open_fn(it.data(0, Qt.UserRole)))
        self.tree.currentItemChanged.connect(self._sel)
        rl.addWidget(self.tree, 1)
        bh = QHBoxLayout()
        bh.addWidget(QLabel("Do części:"))
        self.part = QComboBox()
        self.part.addItems(parts)
        bh.addWidget(self.part)
        b = QPushButton("↓ Dodaj do zestawu")
        b.clicked.connect(self.add)
        bh.addWidget(b)
        b2 = QPushButton("Otwórz pieśń")
        b2.clicked.connect(lambda: self.tree.currentItem() and self.open_fn(self.tree.currentItem().data(0, Qt.UserRole)))
        bh.addWidget(b2)
        rl.addLayout(bh)
        sp.addWidget(right)
        sp.setSizes([620, 620])
        lay.addWidget(sp, 1)
        self.foot = QLabel()
        self.foot.setWordWrap(True)
        self.foot.setOpenExternalLinks(True)
        self.foot.setStyleSheet("color: gray;")
        lay.addWidget(self.foot)
        self._done.connect(self._fetched)
        cached = db.get_liturgy(date.isoformat())
        if cached:
            self.show_lit(cached)
        else:
            self.fetch()

    def fetch(self):
        import threading
        src = self.src.currentData()
        self.b_fetch.setEnabled(False)
        self.text.setHtml("<p><i>Pobieram teksty liturgii…</i></p>")

        day = self.date

        def run():
            try:
                lit = fetch_any(day) if src == 'auto' else fetch(day, src)
                self._done.emit((day, lit), "")
            except Exception as e:
                self._done.emit((day, None), str(e))
        threading.Thread(target=run, daemon=True).start()

    def _fetched(self, res, err):
        day, lit = res
        if lit is not None:
            self.db.set_liturgy(day.isoformat(), lit)       # zapamiętaj także, gdy w międzyczasie wybrano inny dzień
        if day != self.date:
            return
        self.b_fetch.setEnabled(True)
        if lit is None:
            self.text.setHtml(f"<p><b>Nie udało się pobrać liturgii.</b></p><p>{html.escape(err)}</p>"
                              "<p>Sprawdź połączenie z internetem albo wybierz inne źródło. "
                              "Przycisk „Otwórz stronę” pokaże teksty w przeglądarce.</p>")
            self.suggest()
            return
        self.show_lit(lit)

    def show_lit(self, lit):
        self.lit = lit
        meta = lit.get('meta', {})
        parts = []
        if meta.get('dzien'):
            parts.append(f"<h2>{html.escape(meta['dzien'])}</h2>")
        if meta.get('kolor'):
            parts.append(f"<p>Kolor szat: {html.escape(meta['kolor'])}</p>")
        for k, name, _ in SECTIONS:
            s = lit.get('sekcje', {}).get(k)
            if not s:
                continue
            parts.append(f"<h3>{name}" + (f" <i>({html.escape(s['sigla'])})</i>" if s.get('sigla') else "") + "</h3>")
            if s.get('refren') and k == 'psalm':
                parts.append(f"<p><b>Refren: {html.escape(s['refren'])}</b></p>")
            body = html.escape(s['tekst']).replace("\n", "<br>")
            parts.append(f"<p>{body}</p>")
        self.text.setHtml("".join(parts) or "<p>(brak tekstów)</p>")
        if meta.get('dzien'):
            self.head.setText(self.head.text().split(" • ")[0] + " • " + html.escape(meta['dzien']))
        src = lit.get('url', '')
        self.foot.setText(f"Teksty liturgiczne: <a href='{src}'>{html.escape(src)}</a> (Lekcjonarz mszalny i Mszał rzymski "
                          "– Pallottinum/KEP). Program tylko je wyświetla i pamięta w Twojej bazie, aby działały bez internetu.")
        self.suggest()

    def suggest(self, *_):
        self.tree.clear()
        if not self.lit:
            return
        res = suggest(self.lit, self.songs_fn(), self.okres, limit=80 if self.only.isChecked() else 30,
                      mode=self.mode.currentIndex(), okres_only=self.okres_only.isChecked())
        if not self.only.isChecked() and res:
            top = res[0]['score']
            res = [r for r in res if r['score'] >= top * 0.15]
        for r in res:
            fr = "; ".join(f"„{f}” ({SECTION_NAMES.get(k, k).lower()})" for k, f in r['frazy'])
            it = QTreeWidgetItem([("★ " if r['okres'] else "") + r['title'], ", ".join(r['parts']), fr or "—"])
            it.setData(0, Qt.UserRole, r['id'])
            it.setData(1, Qt.UserRole, r['parts'])
            it.setToolTip(2, fr)
            it.setToolTip(0, f"trafność: {r['score']}")
            self.tree.addTopLevelItem(it)
        if not res:
            self.tree.addTopLevelItem(QTreeWidgetItem(["(brak wyraźnych nawiązań w bazie)", "", ""]))

    def shift(self, days):
        self.dedit.setDate(self.dedit.date().addDays(days))

    def next_sunday(self):
        import datetime as _dt
        from PySide6.QtCore import QDate
        t = _dt.date.today()
        d = t + _dt.timedelta(days=(6 - t.weekday()) % 7)
        self.dedit.setDate(QDate(d.year, d.month, d.day))

    def set_date(self, d):
        """Inny dzień: nagłówek, okres liturgiczny, teksty (z pamięci albo pobrane) i propozycje."""
        if d == self.date:
            return
        self.date = d
        info = okres_liturgiczny(d)
        self.okres = info.get('okres') or self.okres
        self.setWindowTitle(f"Liturgia dnia {d.strftime('%d.%m.%Y')} – propozycje pieśni")
        self.head.setText(f"<b>{d.strftime('%d.%m.%Y')}</b> – {info['opis']}")
        self.lit = None
        self.tree.clear()
        cached = self.db.get_liturgy(d.isoformat())
        if cached:
            self.show_lit(cached)
        else:
            self.fetch()

    def _sel(self, it, _prev=None):
        if it and it.data(1, Qt.UserRole):
            i = self.part.findText(it.data(1, Qt.UserRole)[0])
            if i >= 0:
                self.part.setCurrentIndex(i)

    def add(self):
        it = self.tree.currentItem()
        if it and it.data(0, Qt.UserRole):
            self.add_fn(self.part.currentText(), it.data(0, Qt.UserRole))

    def open_web(self):
        src = self.src.currentData()
        url = (self.lit or {}).get('url') or SOURCES['gregorianski' if src == 'auto' else src][1].format(d=self.date.isoformat())
        QDesktopServices.openUrl(QUrl(url))
