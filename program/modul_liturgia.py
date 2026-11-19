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
    ('offert', "Antyfona na ofiarowanie", r"antyfona na ofiarowanie"),
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

def self_lang():
    try:
        import modul_i18n
        return modul_i18n.LANG
    except Exception:
        return 'pl'


APP = "Liber Canticorum"


def _tr(t):
    try:
        import modul_i18n
        return modul_i18n.tr(t)
    except Exception:
        return t


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


# ---------------------------------------------------------------------
# czytania w innych językach – Vatican News („Słowo na dziś”) i krajowe mszaliki
# ---------------------------------------------------------------------
VN_SLUGS = {'en': ["word-of-the-day"], 'es': ["evangelio-de-hoy"], 'fr': ["evangile-du-jour"],
            'pt': ["palavra-do-dia"], 'it': ["vangelo-del-giorno-e-parola-del-giorno"],
            'de': ["tagesevangelium-und-tagesliturgie"]}
VN_ALL = [("it", "Italiano"), ("en", "English"), ("fr", "Français"), ("de", "Deutsch"), ("es", "Español"),
          ("pt", "Português"), ("pl", "Polski"), ("ar", "العربية"), ("hy", "Հայերէն"), ("az", "Azərbaycan"),
          ("be", "Беларуская"), ("bg", "Български"), ("cs", "Čeština"), ("eo", "Esperanto"), ("he", "עברית"),
          ("hr", "Hrvatski"), ("hu", "Magyar"), ("id", "Bahasa Indonesia"), ("lv", "Latviešu"), ("lt", "Lietuvių"),
          ("mk", "Македонски"), ("mn", "Монгол"), ("ro", "Română"), ("sq", "Shqip"), ("sk", "Slovenčina"),
          ("sl", "Slovenščina"), ("sv", "Svenska"), ("ru", "Русский"), ("uk", "Українська"), ("hi", "हिन्दी"),
          ("ml", "മലയാളം"), ("ta", "தமிழ்"), ("kn", "ಕನ್ನಡ"), ("vi", "Tiếng Việt"), ("ja", "日本語"), ("ko", "한국어"),
          ("zht", "繁體中文"), ("zh", "简体中文"), ("am", "አማርኛ"), ("ln", "Lingála"), ("rn", "Ikirundi"),
          ("so", "Soomaali"), ("sw", "Kiswahili"), ("ti", "ትግርኛ")]          # języki serwisu vaticannews.va
VN_LANGS = {'en', 'it', 'fr', 'de', 'es', 'pt', 'pl', 'ar', 'cs', 'hr', 'hu', 'lt', 'ro', 'sk', 'sv', 'uk', 'ml',
            'vi', 'ja', 'ko', 'zh', 'sw'}            # języki serwisu vaticannews.va (strony główne)
# krajowe mszaliki z czytaniami na dany dzień (otwierane w przeglądarce)
NATIONAL = {
    'en': [("USCCB – Daily Readings", lambda d: f"https://bible.usccb.org/bible/readings/{d:%m%d%y}.cfm"),
           ("Universalis", lambda d: f"https://universalis.com/{d:%Y%m%d}/mass.htm")],
    'fr': [("AELF – messe du jour", lambda d: f"https://www.aelf.org/{d:%Y-%m-%d}/romain/messe")],
    'de': [("Schott – Erzabtei Beuron", lambda d: f"https://www.erzabtei-beuron.de/schott/schott_anz/index.html?datum={d:%Y-%m-%d}")],
    'it': [("Liturgia del giorno – CEI", lambda d: f"https://www.chiesacattolica.it/liturgia-del-giorno/?data-liturgia={d:%Y%m%d}")],
    'es': [("Evangelio del día – Dominicos", lambda d: "https://www.dominicos.org/predicacion/evangelio-del-dia/hoy/")],
    'la': [("Missale Meum (1962)", lambda d: f"https://missale.bieda.it/en/calendar/{d:%Y-%m-%d}")],
}
_VN_READ = re.compile(r"(?i)^(reading of the day|first reading|lectura del d[ií]a|primera lectura|lecture du jour|"
                      r"premi[eè]re lecture|leitura do dia|primeira leitura|letture? del giorno|prima lettura|"
                      r"lesung( des tages)?|tageslesung|erste lesung)\s*$")
_VN_GOSP = re.compile(r"(?i)^(gospel of the day|evangelio del d[ií]a|[ée]vangile du jour|evangelho do dia|"
                      r"vangelo del giorno|evangelium( des tages| vom tag)?)\s*$")
_VN_STOP = re.compile(r"(?i)^(the words of the popes|las palabras de los papas|les paroles des papes|"
                      r"as palavras dos papas|le parole dei papi|die worte der p[äa]pste|excerpts from the lectionary)")


# Mszał 1962 (usus antiquior) – Missale Meum (API: łacina + angielski)
MM_HOSTS = ("https://missale.bieda.it", "https://www.missalemeum.com")
_MM_MAP = {'introitus': 'ant_wej', 'oratio': 'kolekta', 'lectio': 'czyt1', 'graduale': 'psalm', 'tractus': 'aklamacja',
           'alleluja': 'aklamacja', 'alleluia': 'aklamacja', 'sequentia': 'sekwencja', 'evangelium': 'ewangelia',
           'offertorium': 'offert', 'secreta': 'dary', 'praefatio': 'prefacja', 'communio': 'ant_kom',
           'postcommunio': 'po_kom'}


def _mm_clean(t):
    """Znaczniki Divinum Officium → zwykły tekst."""
    out = []
    for l in (t or "").split("\n"):
        l = l.strip()
        if not l or l.startswith(("&", "$", "#")):
            continue
        l = re.sub(r"[_*]", "", l)
        l = re.sub(r"^(v\.|r\.|V\.|R\.)\s*", lambda m: m.group(1).upper() + " ", l)
        out.append(l)
    return "\n".join(out).strip()


def fetch_missale(date, timeout=25):
    """Proprium Missae z Mszału 1962 na dany dzień – tekst łaciński (Missale Meum)."""
    errors = []
    for host in MM_HOSTS:
        url = f"{host}/en/api/v5/proper/{date:%Y-%m-%d}"
        try:
            req = urllib.request.Request(url, headers=dict(UA, Accept="application/json"))
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode('utf-8'))
        except Exception as e:
            errors.append(f"{url}: {e}")
            continue
        if not data:
            errors.append(f"{url}: pusto")
            continue
        p = data[0]
        secs = {}
        for sec in p.get('sections', []):
            key = _MM_MAP.get(re.sub(r"[^a-z]", "", (sec.get('id') or "").lower()))
            if not key or key in secs:
                continue
            body = sec.get('body') or []
            latin = "\n".join((b[1] if len(b) > 1 and b[1] else b[0]) for b in body if b)
            lines = [l for l in latin.split("\n")]
            sig = ""
            if lines and lines[0].strip().startswith("!"):
                sig = lines.pop(0).strip("! ")
            text = _mm_clean("\n".join(lines))
            if text:
                secs[key] = {'naglowek': SECTION_NAMES[key], 'sigla': sig, 'tekst': text}
        info = p.get('info', {})
        meta = {'dzien': info.get('title') or "", 'kolor': ", ".join(info.get('colors') or [])}
        if secs:
            return {'zrodlo': 'missale', 'url': f"{host}/en/calendar/{date:%Y-%m-%d}", 'data': date.isoformat(),
                    'sekcje': secs, 'meta': meta, 'jezyk': 'la'}
        errors.append(f"{url}: brak tekstów")
    raise RuntimeError("Missale Meum: " + "; ".join(errors[-2:]))


def reading_pages(date, lang=None):
    """Strony z czytaniami na dany dzień: [(grupa, nazwa, adres)] – najpierw język interfejsu."""
    out = []
    for code, name in VN_ALL:
        if VN_SLUGS.get(code):
            out.append(("Vatican News", f"{name} – {_tr('czytania dnia')}", vatican_url(date, code, VN_SLUGS[code][0])))
        else:
            out.append(("Vatican News", name, f"https://www.vaticannews.va/{code}.html"))
    for lg, items in NATIONAL.items():
        for name, fn in items:
            out.append((lg.upper(), name, fn(date)))
    out.append(("PL", "gregorianski.pl – mszalik", SOURCES['gregorianski'][1].format(d=date.isoformat())))
    out.append(("PL", "niezbednik.niedziela.pl", SOURCES['niezbednik'][1].format(d=date.isoformat())))
    out.append(("PL", "opoka.org.pl", SOURCES['opoka'][1].format(d=date.isoformat())))
    out.append(("1962", "Ordo – propria.org", f"https://propria.org/ordo-{date.year}/"))
    try:
        from PySide6.QtCore import QSettings
        custom = json.loads(QSettings("LiberCanticorum", "LiberCanticorum").value("lit_custom_urls", "[]") or "[]")
    except Exception:
        custom = []
    for name, tmpl in custom:
        out.append(("★", name, custom_url(tmpl, date)))
    if lang:
        mine = {lang, {'zh': 'zht'}.get(lang, lang)}
        out.sort(key=lambda r: (0 if r[0] == "★" else 1 if (r[0].lower() in mine or any(
            f"vaticannews.va/{m}/" in r[2] or r[2].endswith(f"vaticannews.va/{m}.html") for m in mine)) else 2))
    return out


def custom_url(tmpl, date):
    """Własny adres z miejscami na datę: {YYYY} {MM} {DD} {YY} {date} (RRRR-MM-DD)."""
    return (tmpl.replace("{YYYY}", f"{date:%Y}").replace("{MM}", f"{date:%m}").replace("{DD}", f"{date:%d}")
            .replace("{YY}", f"{date:%y}").replace("{date}", date.isoformat()))


def vatican_url(date, lang, slug):
    return f"https://www.vaticannews.va/{lang}/{slug}/{date:%Y/%m/%d}.html"


def fetch_vatican(date, lang='en', timeout=20):
    """Czytania dnia z Vatican News w danym języku (czytanie i Ewangelia); gdy w tym języku brak strony – po angielsku.
    → {'zrodlo': 'vatican', 'url', 'data', 'sekcje', 'meta', 'jezyk'}"""
    tries = [(lang, sl) for sl in VN_SLUGS.get(lang, [])]
    if lang != 'en':
        tries.append(('en', "word-of-the-day"))
    errors = []
    for lg, slug in tries:
        url = vatican_url(date, lg, slug)
        try:
            req = urllib.request.Request(url, headers=dict(UA, **{'Accept-Language': f"{lg},en;q=0.8"}))
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode(r.headers.get_content_charset() or 'utf-8', errors='replace')
        except Exception as e:
            errors.append(f"{url}: {e}")
            continue
        lines = html_lines(raw)
        secs, cur, buf, meta = {}, None, [], {}

        def close():
            if cur and buf and cur not in secs:
                body = list(buf)
                sig = ""
                # nagłówek księgi i sigla: „A reading from …” / „17:1-6”
                head = body[0] if body else ""
                for i, l in enumerate(body[:3]):
                    if re.match(r"^\(?[\d][\d,:.\-–a-z ]{1,30}\)?$", l.strip()):
                        sig = l.strip(" ()")
                        del body[i]
                        break
                secs[cur] = {'naglowek': SECTION_NAMES[cur], 'sigla': sig, 'tekst': "\n".join(body).strip(),
                             'tytul': head}
        for i, l in enumerate(lines):
            if re.match(r"(?i)^(date|data|fecha|datum)\s*\d", l) and i + 1 < len(lines):
                meta.setdefault('dzien', lines[i + 1].strip())
            if _VN_STOP.match(l):
                close()
                cur, buf = None, []
                continue
            if _VN_READ.match(l):
                close()
                cur, buf = ('czyt1' if 'czyt1' not in secs else 'czyt2'), []
                continue
            if _VN_GOSP.match(l):
                close()
                cur, buf = 'ewangelia', []
                continue
            if cur:
                buf.append(l)
        close()
        if secs:
            return {'zrodlo': 'vatican', 'url': url, 'data': date.isoformat(), 'sekcje': secs, 'meta': meta,
                    'jezyk': lg}
        errors.append(f"{url}: brak czytań na stronie")
    raise RuntimeError("Vatican News: " + "; ".join(errors[-3:]))


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
                   'po_kom': ["Uwielbienie", "Wyjście"], 'sekwencja': ["Uwielbienie"], 'offert': ["Ofiarowanie"]}
SECTION_WEIGHT = {'ant_wej': 1.3, 'psalm': 1.4, 'ewangelia': 1.3, 'ant_kom': 1.3, 'aklamacja': 1.1,
                  'czyt1': 1.0, 'czyt2': 0.9, 'kolekta': 0.9, 'dary': 0.8, 'prefacja': 0.8, 'po_kom': 0.8,
                  'sekwencja': 1.0, 'offert': 1.2}


_ORDINARY_WORDS = ("kyrie", "gloria", "sanctus", "agnus dei", "baranku bozy", "panie zmiluj sie", "chwala na wysokosci",
                   "swiety, swiety", "swiety swiety", "czesci stale", "ordinarium")


def is_ordinary(song):
    """Część stała Mszy (Kyrie, Gloria, Sanctus, Agnus Dei) – po kategorii, tagach albo tytule."""
    kat = _norm(song.get('kategoria') or "")
    if "czesci stale" in kat or "ordinarium" in kat:
        return True
    def key(x):
        return " " + re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", _norm(x or ""))).strip()
    tags = key(song.get('tagi'))
    title = key(song.get('title'))
    words = [key(w) for w in _ORDINARY_WORDS]
    # tytuł zaczyna się od słów części stałej albo zawiera je po myślniku („Msza Rycerska – Kyrie”)
    return any(w in tags for w in words) or any(title.startswith(w) or (w in title and ("–" in (song.get('title') or "")
                                                                                         or " - " in (song.get('title') or "")))
                                                for w in words)


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
    songs = [s for s in songs if s and not is_ordinary(s)]       # części stałe (Kyrie, Gloria…) nie są propozycjami
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
    out.sort(key=lambda r: (not r['okres'], -r['score']))        # najpierw pieśni z okresu liturgicznego
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
        self.dedit.setLocale(QLocale(QLocale.Polish, QLocale.Poland) if self_lang() == 'pl' else QLocale())
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
        try:
            import modul_i18n
            self.lang = modul_i18n.LANG
        except Exception:
            self.lang = 'pl'
        if self.lang == 'la':                                # po łacinie – Mszał 1962
            self.src.addItem("Missale Romanum 1962 (Missale Meum)", 'missale')
        elif self.lang != 'pl':                              # czytania w języku interfejsu – Vatican News
            self.src.addItem(f"Vatican News – {self.lang.upper()}", 'vatican')
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
        try:
            import modul_i18n
            latin = modul_i18n.LANG == 'la'
        except Exception:
            latin = False
        if True:                                              # krajowe mszaliki i Vatican News w przeglądarce
            nat = QHBoxLayout()
            nat.addWidget(QLabel("Czytania w Twoim języku:"))
            links = list(NATIONAL.get(self.lang, []))
            vl = self.lang if self.lang in VN_LANGS else 'en'
            if VN_SLUGS.get(vl):
                links.append(("Vatican News", lambda d, vl=vl: vatican_url(d, vl, VN_SLUGS[vl][0])))
            else:
                links.append(("Vatican News", lambda d, vl=vl: f"https://www.vaticannews.va/{vl}.html"))
            if self.lang in ('pl', 'la'):
                links = []
            for txt, fn in links:
                b = QPushButton("🌐 " + txt)
                b.clicked.connect(lambda _=False, fn=fn: QDesktopServices.openUrl(QUrl(fn(self.date))))
                nat.addWidget(b)
            b = QPushButton("📋 Strony z czytaniami – wybierz…")
            b.setToolTip("Lista stron z czytaniami na ten dzień: Vatican News we wszystkich językach, krajowe mszaliki,\n"
                         "Mszał 1962 – oraz własne adresy (z datą w adresie)")
            b.clicked.connect(self.pages_dialog)
            nat.addWidget(b)
            nat.addStretch(1)
            lay.addLayout(nat)
        if latin:                                           # po łacinie: liturgia tradycyjna (Mszał 1962)
            trad = QHBoxLayout()
            lab = QLabel("<b>Missale Romanum 1962</b> – usus antiquior:")
            trad.addWidget(lab)
            for txt, fn in (("📜 Proprium diei (Missale Meum)",
                             lambda: QDesktopServices.openUrl(QUrl(
                                 f"https://missale.bieda.it/en/calendar/{self.date.isoformat()}"))),
                            ("📅 Ordo (propria.org)",
                             lambda: QDesktopServices.openUrl(QUrl(f"https://propria.org/ordo-{self.date.year}/")))):
                b = QPushButton(txt)
                b.clicked.connect(fn)
                trad.addWidget(b)
            trad.addStretch(1)
            lay.addLayout(trad)
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
        srow = QHBoxLayout()
        srow.addWidget(QLabel("Źródło:"))
        self.song_src = QComboBox()
        self.song_src.setProperty("i18n_no", True)
        self.song_src.setToolTip("Tylko pieśni z wybranego śpiewnika / zbioru")
        from modul_i18n import tr as _t
        self.song_src.addItem(_t("Wszystkie źródła"), None)
        try:
            for name, n in db.sources():
                self.song_src.addItem(f"{name or _t('(bez źródła)')}  ({n})", name)
        except Exception:
            pass
        keep = self.qs.value("lit_source", None)
        k = self.song_src.findData(keep) if keep is not None else 0
        self.song_src.setCurrentIndex(max(0, k))
        self.song_src.currentIndexChanged.connect(lambda _: (self.qs.setValue("lit_source", self.song_src.currentData()),
                                                        self.suggest()))
        srow.addWidget(self.song_src, 1)
        rl.addLayout(srow)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Pieśń", "Pasuje do", "Nawiązania (słowa i frazy z liturgii)", "Źródło"])
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
        if self.lang != 'pl':
            self.src.setCurrentIndex(0)                       # Vatican News / Mszał 1962 w języku interfejsu
        cached = db.get_liturgy(self._key(date))
        if cached:
            self.show_lit(cached)
        else:
            self.fetch()

    def _key(self, day, lit=None):
        """Klucz pamięci podręcznej: polska liturgia – sama data; Vatican News – data@język."""
        vat = (lit.get('zrodlo') in ('vatican', 'missale')) if lit is not None else \
            self.src.currentData() in ('vatican', 'missale')
        return day.isoformat() + (f"@{self.lang}" if vat else "")

    def fetch(self):
        import threading
        src = self.src.currentData()
        self.b_fetch.setEnabled(False)
        self.text.setHtml("<p><i>Pobieram teksty liturgii…</i></p>")

        day = self.date

        def run():
            try:
                lit = (fetch_vatican(day, self.lang) if src == 'vatican' else
                       fetch_missale(day) if src == 'missale' else
                       fetch_any(day) if src == 'auto' else fetch(day, src))
                self._done.emit((day, lit), "")
            except Exception as e:
                self._done.emit((day, None), str(e))
        threading.Thread(target=run, daemon=True).start()

    def _fetched(self, res, err):
        day, lit = res
        if lit is not None:
            self.db.set_liturgy(self._key(day, lit), lit)       # zapamiętaj także, gdy w międzyczasie wybrano inny dzień
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
            kol = meta['kolor']
            if lit.get('zrodlo') == 'missale':
                kol = ", ".join({'w': "albus", 'r': "ruber", 'g': "viridis", 'v': "violaceus", 'b': "niger",
                                 'p': "rosaceus"}.get(c.strip(), c) for c in kol.split(","))
            parts.append(f"<p>{_tr('Kolor szat:')} {html.escape(kol)}</p>")
        for k, name, _ in SECTIONS:
            s = lit.get('sekcje', {}).get(k)
            if not s:
                continue
            parts.append(f"<h3>{_tr(name)}" + (f" <i>({html.escape(s['sigla'])})</i>" if s.get('sigla') else "") + "</h3>")
            if s.get('refren') and k == 'psalm':
                parts.append(f"<p><b>Refren: {html.escape(s['refren'])}</b></p>")
            body = html.escape(s['tekst']).replace("\n", "<br>")
            parts.append(f"<p>{body}</p>")
        self.text.setHtml("".join(parts) or "<p>(brak tekstów)</p>")
        if lit.get('zrodlo') == 'missale':                  # usus antiquior – bez cyklu lekcjonarza (rok A/B/C)
            self.head.setText(f"<b>{self.date.strftime('%d.%m.%Y')}</b> • {html.escape(meta.get('dzien', ''))}")
        elif meta.get('dzien'):
            self.head.setText(self.head.text().split(" • ")[0] + " • " + html.escape(meta['dzien']))
        src = lit.get('url', '')
        if lit.get('zrodlo') == 'missale':
            self.foot.setText(f"Missale Romanum 1962 – <a href='{src}'>{html.escape(src)}</a> (Missale Meum).")
        elif lit.get('zrodlo') == 'vatican':
            self.foot.setText(_tr("Czytania: <a href='{a}'>{b}</a> (Vatican News, „Słowo na dziś”). Program tylko je "
                                  "wyświetla i pamięta w Twojej bazie, aby działały bez internetu.").replace(
                "{a}", src).replace("{b}", html.escape(src)))
        else:
            self.foot.setText(f"Teksty liturgiczne: <a href='{src}'>{html.escape(src)}</a> (Lekcjonarz mszalny i Mszał rzymski "
                              "– Pallottinum/KEP). Program tylko je wyświetla i pamięta w Twojej bazie, aby działały bez internetu.")
        self.suggest()

    def suggest(self, *_):
        self.tree.clear()
        if not self.lit:
            return
        src = self.song_src.currentData()
        songs = [s for s in self.songs_fn() if s and (src is None or (s.get('spiewnik') or '') == src)]
        srcmap = {s.get('id'): s.get('spiewnik', '') for s in songs}
        res = suggest(self.lit, songs, self.okres, limit=80 if self.only.isChecked() else 30,
                      mode=self.mode.currentIndex(), okres_only=self.okres_only.isChecked())
        if not self.only.isChecked() and res:
            top = res[0]['score']
            res = [r for r in res if r['score'] >= top * 0.15]
        for r in res:
            fr = "; ".join(f"„{f}” ({SECTION_NAMES.get(k, k).lower()})" for k, f in r['frazy'])
            it = QTreeWidgetItem([("★ " if r['okres'] else "") + r['title'], ", ".join(_tr(x) for x in r['parts']), fr or "—",
                                  srcmap.get(r['id']) or ""])
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
        cached = self.db.get_liturgy(self._key(d))
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

    def pages_dialog(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QLineEdit, QHBoxLayout, \
            QPushButton, QInputDialog, QMessageBox
        from PySide6.QtCore import QSettings
        d = QDialog(self)
        d.setWindowTitle(_tr("Strony z czytaniami") + f" – {self.date:%d.%m.%Y}")
        lay = QVBoxLayout(d)
        q = QLineEdit()
        q.setPlaceholderText(_tr("Szukaj: język, kraj, nazwa strony…"))
        lay.addWidget(q)
        lst = QListWidget()
        lay.addWidget(lst, 1)

        def fill():
            lst.clear()
            for grp, name, url in reading_pages(self.date, self.lang):
                if q.text().strip() and q.text().lower() not in f"{grp} {name} {url}".lower():
                    continue
                it = QListWidgetItem(f"{grp}   ·   {name}")
                it.setToolTip(url)
                it.setData(Qt.UserRole, url)
                lst.addItem(it)
        q.textChanged.connect(fill)
        fill()
        lst.itemDoubleClicked.connect(lambda it: QDesktopServices.openUrl(QUrl(it.data(Qt.UserRole))))
        row = QHBoxLayout()

        def open_sel():
            it = lst.currentItem()
            if it:
                QDesktopServices.openUrl(QUrl(it.data(Qt.UserRole)))

        def add_custom():
            name, ok = QInputDialog.getText(d, APP, _tr("Nazwa strony (np. „Mszalik mojej diecezji”):"))
            if not ok or not name.strip():
                return
            tmpl, ok = QInputDialog.getText(d, APP, _tr("Adres strony z czytaniami. Miejsca na datę: {YYYY} {MM} {DD} {YY}, "
                                                        "{date} = RRRR-MM-DD.\nNp. https://example.org/{YYYY}/{MM}/{DD}"),
                                            text="https://")
            if not ok or not tmpl.strip().startswith("http"):
                return
            qs = QSettings("LiberCanticorum", "LiberCanticorum")
            cur = json.loads(qs.value("lit_custom_urls", "[]") or "[]")
            cur.append([name.strip(), tmpl.strip()])
            qs.setValue("lit_custom_urls", json.dumps(cur, ensure_ascii=False))
            fill()

        def del_custom():
            it = lst.currentItem()
            if not it or not it.text().startswith("★"):
                QMessageBox.information(d, APP, _tr("Zaznacz własny adres (★)."))
                return
            qs = QSettings("LiberCanticorum", "LiberCanticorum")
            cur = json.loads(qs.value("lit_custom_urls", "[]") or "[]")
            name = it.text().split("·", 1)[1].strip()
            qs.setValue("lit_custom_urls", json.dumps([c for c in cur if c[0] != name], ensure_ascii=False))
            fill()
        for txt, fn in (("🌐 Otwórz", open_sel), ("✚ Własny adres…", add_custom), ("🗑 Usuń własny", del_custom),
                        ("Zamknij", d.accept)):
            b = QPushButton(txt)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        d.resize(640, 620)
        d.exec()

    def open_web(self):
        src = self.src.currentData()
        if src == 'missale' and not (self.lit or {}).get('url'):
            QDesktopServices.openUrl(QUrl(f"{MM_HOSTS[0]}/en/calendar/{self.date:%Y-%m-%d}"))
            return
        if src == 'vatican' and not (self.lit or {}).get('url'):
            vl = self.lang if self.lang in VN_SLUGS else 'en'
            QDesktopServices.openUrl(QUrl(vatican_url(self.date, vl, VN_SLUGS[vl][0])))
            return
        url = (self.lit or {}).get('url') or SOURCES['gregorianski' if src in ('auto', 'vatican', 'missale') else src][1].format(
            d=self.date.isoformat())
        QDesktopServices.openUrl(QUrl(url))
