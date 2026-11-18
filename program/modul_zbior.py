# -*- coding: utf-8 -*-
"""Liber Canticorum – rozpoznawanie ZBIORU pieśni na jednej stronie lub w jednym pliku
(np. dział śpiewnika internetowego: „1. Tytuł / zwrotki / 2. Tytuł / …”).

Obsługuje typowy zapis śpiewników:
  * numerowane tytuły pieśni, a pod nimi numerowane zwrotki,
  * „ * ” jako koniec wersu, „=” jako znak powtórzenia,
  * „Refren:”, „Antyfona:”, „Ref.”, „Ant.” (odwołania do refrenu na końcu zwrotki są usuwane),
  * linki do nagrań (mp3, YouTube) pod pieśnią,
  * nagłówki działów („Pieśni na Adwent”, „Część druga – od 17 grudnia”).
Licencja: GPL-3.0-or-later.
"""
import html as H
import re
import urllib.parse

MARK = "\u2063"                        # znacznik tytułu wstawiany przy odczycie HTML (akordeony śpiewników)
RE_TITLE = re.compile(r"^(\d{1,4}(?:\s?[A-Za-z])?)\.\s+(\S.{0,90})$")
RE_VERSE = re.compile(r"^(\d{1,2})\.\s*(.*)$")
RE_REF = re.compile(r"^(refren|ref\.|antyfona|ant\.|r\.)\s*:?\s*(.*)$", re.I)
RE_URL = re.compile(r"^(https?://\S+)$")
RE_END_REF = re.compile(r"\s*(\bRef(ren)?\.?|\bAnt(yfona)?\.?)\s*$")
CAT_WORDS = [("adwent", "Adwent"), ("boże narodzenie", "Boże Narodzenie"), ("kolęd", "Boże Narodzenie"),
             ("wielki post", "Wielki Post"), ("wielkopost", "Wielki Post"), ("pasyjn", "Wielki Post"),
             ("triduum", "Triduum Paschalne"), ("wielkanoc", "Wielkanoc"), ("zmartwychwsta", "Wielkanoc"),
             ("ducha święt", "Zesłanie Ducha Świętego"), ("zesłani", "Zesłanie Ducha Świętego"),
             ("maryj", "Maryjne"), ("matki bożej", "Maryjne"), ("eucharyst", "Eucharystyczne"),
             ("najświętszego sakramentu", "Eucharystyczne"), ("serca pana jezusa", "Do Serca Pana Jezusa"),
             ("świętych", "O świętych"), ("pogrzeb", "Pogrzebowe"), ("za zmarłych", "Pogrzebowe"),
             ("ślub", "Ślubne"), ("dla dzieci", "Dla dzieci"), ("okres zwykły", "Okres zwykły"),
             ("części stałe", "Części stałe Mszy"), ("psalm", "Psalmy i śpiewy przed Ewangelią"),
             ("uwielbieni", "Uwielbienie")]


def _is_title(lines, i, expected):
    """Czy wiersz i to tytuł kolejnej pieśni (a nie zwrotka)."""
    m = RE_TITLE.match(lines[i])
    if not m or '*' in lines[i] or len(m.group(2)) > 70 or m.group(2).endswith(('.', ',', ';')):
        return None
    n = _ord(m.group(1))
    back = expected is not None and not (expected < n <= expected + 12 * 30)
    if back and not (abs(n - expected) <= 12 * 30):
        return None
    # po tytule (pomijając puste wiersze) musi być treść: zwrotka, refren, antyfona
    j = i + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j >= len(lines):
        return None
    nxt = lines[j].strip()
    vm = RE_VERSE.match(nxt)
    if RE_TITLE.match(nxt) and '*' not in nxt and len(nxt) < 60 and not (vm and vm.group(2).count(' ') > 6):
        # kolejny „tytuł” zaraz po tytule – to raczej zwrotka 1. bez gwiazdek, sprawdź numer
        if not nxt.startswith("1."):
            return None
    blank_after = i + 1 < len(lines) and not lines[i + 1].strip()
    plain_ok = blank_after and not re.match(r"^\d", nxt) and len(nxt) > 10 and n >= 10 * 30
    if not (RE_VERSE.match(nxt) or RE_REF.match(nxt) or ('*' in nxt and len(nxt) > 20) or plain_ok):
        return None
    if back and not (blank_after and not RE_TITLE.match(nxt)):     # numer się cofa (np. powtórzona pozycja)
        return None
    return n, m.group(2).strip(), re.sub(r"\s", "", m.group(1))


def _ord(numtxt):
    """„779a” → liczba porządkowa (numer * 30 + litera), żeby 779a < 779b < 780."""
    m = re.match(r"(\d+)\s?([A-Za-z]?)", numtxt)
    return int(m.group(1)) * 30 + (ord(m.group(2).lower()) - 96 if m.group(2) else 0)


def _clean_line(t):
    t = t.replace(' ', ' ').strip()
    t = re.sub(r"\s*\*\s*", "\n", t)                       # „ * ” = koniec wersu
    t = re.sub(r"(^|\n)\s*=\s*", r"\1", t)                  # „=” = powtórz
    return "\n".join(l.strip() for l in t.split("\n") if l.strip())


def _song_from_block(num, title, block, source="", section="", category=""):
    ref, verses, notes, links = "", [], [], []
    free = False                     # ostatnia zwrotka bez numeru (np. litania, modlitwa) – kolejne wiersze dopisuj
    brk = False
    for raw in block:
        line = raw.strip()
        if not line:
            brk = True
            continue
        if RE_URL.match(line):
            links.append(line)
            continue
        m = RE_REF.match(line)
        if m and not verses or (m and m.group(1).lower() in ('refren', 'antyfona')):
            body = m.group(2)
            alt = re.split(r"\s+Albo\s+(?=Refren|Antyfona)", body, flags=re.I)
            if not ref:
                ref = _clean_line(RE_END_REF.sub("", alt[0]))
            if len(alt) > 1:
                notes.append("Albo " + alt[1].strip())
            continue
        is_note = re.match(r"(?i)^(lub|albo|można|uwaga|wg|według)\b", line)
        m = RE_VERSE.match(line)
        if m and not is_note:
            verses.append(f"{m.group(1)}. " + _clean_line(RE_END_REF.sub("", m.group(2))))
            free = brk = False
            continue
        if is_note:
            notes.append(line)
        elif verses and not brk and not (re.match(r"(?i)^(K\.|W\.|P\.|Módlmy się|Oremus)", line)
                                         and re.match(r"^\d", verses[-1])):
            # dalszy wiersz tej samej zwrotki / modlitwy / litanii (K./W. po zwrotkach zaczyna nowy blok)
            verses[-1] += "\n" + _clean_line(RE_END_REF.sub("", line))
        elif '*' in line or not verses or len(line) > 25:
            verses.append(_clean_line(RE_END_REF.sub("", line)))       # zwrotka bez numeru
            free = '*' not in line
        else:
            notes.append(line)
        brk = False
    uwagi = []
    if source:
        uwagi.append(f"{source} nr {num}")
    if section:
        uwagi.append(section)
    uwagi += notes
    yt = []
    for u in links:
        name = urllib.parse.unquote(u.rsplit('/', 1)[-1])
        yt.append(f"{u}\tNagranie: {name}")
    return {'title': title, 'refren': ref, 'zwrotki_raw': "\n\n".join(verses), 'uwagi': " | ".join(uwagi),
            'kategoria': category, 'tagi': '', 'youtube': "\n".join(yt), 'numer': num}


def fold_simple(t):
    return re.sub(r"[^a-z ]", "", (t or "").lower().translate(str.maketrans("ąćęłńóśźż", "acelnoszz"))).strip()


def guess_category(text):
    low = (text or "").lower()
    for w, cat in CAT_WORDS:
        if w in low:
            return cat
    return ""


def parse_collection(text, source="", min_songs=3, sections=True):
    """Tekst strony/pliku → {'piesni': [...], 'naglowek', 'kategoria'} albo None, gdy to nie zbiór."""
    lines = [l.rstrip() for l in (text or "").replace('\r', '').split("\n")]
    # stopka strony (zgoda na ciasteczka, tłumacz…) nie należy do ostatniej pieśni
    for k, l in enumerate(lines):
        if re.match(r"(?i)^\s*(korzystając z tej witryny|ta strona (używa|wykorzystuje) (plików )?cookies|translate »|"
                    r"copyright ©|© \d{4})", l):
            lines = lines[:k]
            break
    starts, expected = [], None
    marked = [i for i, l in enumerate(lines) if l.strip().startswith(MARK)]
    if len(marked) >= min(min_songs, 2):                # tytuły oznaczone przy odczycie HTML – pewne
        for i in marked:
            t = lines[i].strip().lstrip(MARK).strip()
            m = re.match(r"^(\d{1,4}(?:\s?[A-Za-z])?)\.\s*(.+)$", t)
            starts.append((i, re.sub(r"\s", "", m.group(1)) if m else str(len(starts) + 1), (m.group(2) if m else t).strip()))
        lines = [l.replace(MARK, "") for l in lines]
    else:
        lines = [l.replace(MARK, "") for l in lines]
        for i, l in enumerate(lines):
            t = _is_title(lines, i, expected)
            if t:
                starts.append((i, t[2], t[1]))
                expected = max(t[0], expected or 0)
    # wymagaj ciągu rosnących numerów; dwie pozycje wystarczą, gdy mają numery śpiewnikowe (≥ 10, np. 782a, 782b)
    if len(starts) < min_songs and not (len(starts) == 2 and all(_ord(str(n)) >= 10 * 30 for _, n, _ in starts)):
        return None
    nums = [_ord(str(n)) for _, n, _ in starts]
    if not marked or len(marked) < min_songs:
        if sum(1 for a, b in zip(nums, nums[1:]) if b > a) < 0.7 * (len(nums) - 1):
            return None
    head_lines = [l.strip() for l in lines[:starts[0][0]] if l.strip()]
    HEAD = (r"(?i)^(pieśni|kolędy|śpiewy|psalmy|części stałe|litanie|nieszpory|godzinki|różaniec|suplikacje|hymny|"
            r"pastorałki|cykle mszalne|pogrzeb|niedzielne pokropienie|gorzkie żale|wielki post|wielki tydzień|adwent|"
            r"narodzenie|okres|przemienienie|wniebowstąpienie)\b")
    header = next((l for l in head_lines if re.match(HEAD, l) and fold_simple(l) not in ("piesni", "spiewnik")
                   and not re.search(r"(?i)\bnumer|\d+\s*[-–]\s*\d+", l) and len(l) < 80), "")
    if not header:                                   # „791-792” / „Koronka…” – nazwa działu po zakresie numerów
        for a, b in zip(head_lines, head_lines[1:]):
            if re.match(r"^\d+\s*[-–]\s*\d+$|^\d+\s*[A-Z]\s*[-–]\s*[A-ZŁ]$|^\d+\s*[A-Z]-[A-Z]$", a) and len(b) < 80:
                header = b
                break
    category = guess_category(header) or (header if header and len(header) < 40 else "") or \
        guess_category(" ".join(head_lines[-4:]))
    songs = []
    shorts = head_lines[head_lines.index(header) + 1:] if header in head_lines else head_lines[-2:]
    shorts = [l for l in shorts if len(l) < 70 and not l.endswith(('.', ':'))]
    section = shorts[-1] if shorts and sections else ""
    for k, (i, num, title) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        block = lines[i + 1:end]
        # nagłówek działu tuż przed następną pieśnią („Część druga – od 17 grudnia”) – nie należy do tej pieśni
        tail = []
        while sections and block and (not block[-1].strip() or (not RE_URL.match(block[-1].strip()) and not RE_VERSE.match(block[-1].strip())
                                                 and not RE_REF.match(block[-1].strip()) and '*' not in block[-1]
                                                 and len(block[-1]) < 80)):
            if block[-1].strip():
                tail.insert(0, block[-1].strip())
            block.pop()
        songs.append(_song_from_block(num, title, block, source, section, category))
        if tail:
            section = tail[-1]
    # ten sam tytuł kilka razy w zbiorze (np. dwie melodie koronki) – dopisz dział i numer, żeby dało się je odróżnić
    from collections import Counter
    cnt = Counter(fold_simple(sg['title']) for sg in songs)
    for sg in songs:
        if cnt[fold_simple(sg['title'])] > 1:
            sect = next((u for u in sg['uwagi'].split(" | ")[1:2]), "")
            sg['title'] = f"{sg['title']} ({', '.join(x for x in (sect, str(sg['numer'])) if x)})"
    return {'piesni': songs, 'naglowek': header, 'kategoria': category}


def source_name(url, page_title=""):
    """Nazwa śpiewnika do uwag: z tytułu strony albo z domeny („spiewniksiedleckiego.pl”)."""
    host = urllib.parse.urlparse(url).netloc.replace("www.", "") if url else ""
    known = {"spiewniksiedleckiego.pl": "Śpiewnik Siedleckiego"}
    return known.get(host) or host or (page_title or "")


def html_for_collection(raw):
    """Przygotowuje HTML śpiewnika do odczytu: tytuły w akordeonach (<button>) jako nagłówki,
    odtwarzacze <audio> jako zwykłe linki do plików."""
    def title(m):
        inner = re.sub(r"(?is)<[^>]+>", " ", m.group(1))
        inner = re.sub(r"[\ue000-\uf8ff]", "", H.unescape(inner))         # ikony z czcionek (strzałki akordeonu)
        inner = re.sub(r"^[^\w„\"(]+", "", re.sub(r"\s+", " ", inner)).strip()
        # przyciski-tytuły pieśni („94. O człowiecze…”) oznacz; inne przyciski zostaw jako zwykły tekst
        if re.match(r"^\d{1,4}(?:\s?[A-Za-z])?\.\s+\S", inner):
            return f"<h4>{MARK}{inner}</h4>"
        return f"<h4>{inner}</h4>" if inner else ""
    raw = re.sub(r"(?is)<button\b[^>]*>(.*?)</button>", title, raw)

    def audio(m):
        src = re.search(r'''(?i)(?:src|href)=["']([^"']+\.(?:mp3|ogg|m4a|wav)[^"']*)''', m.group(0))
        return f"<p>{re.sub(r'[?&]_=\d+$', '', src.group(1))}</p>" if src else ""
    raw = re.sub(r"(?is)<audio\b.*?</audio>", audio, raw)
    return raw


# ---------------------------------------------------------------------
# okno: wybór pieśni ze zbioru
# ---------------------------------------------------------------------
try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QSplitter,
                                   QPlainTextEdit, QComboBox, QLineEdit, QCheckBox, QPushButton, QDialogButtonBox,
                                   QFormLayout, QWidget)
except ImportError:
    QDialog = object


class CollectionDialog(QDialog):
    """Lista pieśni znalezionych na stronie / w pliku – zaznacz, które zaimportować."""

    def __init__(self, coll, exists_fn, categories, source="", parent=None, get_fn=None):
        """exists_fn(tytuł) → id albo None (stare wywołanie) lub similar_fn(pieśń) → [(id, tytuł, podob., powód)];
        get_fn(id) → pieśń z bazy (do podglądu przy łączeniu)."""
        super().__init__(parent)
        self.coll = coll
        self.get_fn = get_fn
        self.cands, self.actions = [], []
        for s in coll['piesni']:
            try:
                c = exists_fn(s)
            except TypeError:
                c = exists_fn(s['title'])
            if isinstance(c, int):
                c = [(c, s['title'], 1.0, "ten sam tytuł")]
            c = list(c or [])
            self.cands.append(c)
            # pewna zgodność → dołącz do istniejącej (nowe nuty i inny tekst jako wersja), inaczej nowa pieśń
            self.actions.append(('merge', c[0][0]) if c and c[0][2] >= 0.9 else ('new', None))
        self.setWindowTitle(f"Zbiór pieśni – {len(coll['piesni'])} znalezionych")
        self.resize(1050, 700)
        lay = QVBoxLayout(self)
        head = coll.get('naglowek') or "Na stronie jest wiele pieśni."
        lay.addWidget(QLabel(f"<b>{head}</b> – znaleziono {len(coll['piesni'])} pieśni"
                             + (f" ({source})" if source else "") +
                             ". Zaznacz, które dodać do bazy. Pieśni, które już są w bazie, są odznaczone."))
        sp = QSplitter()
        self.list = QListWidget()
        for i, s in enumerate(coll['piesni']):
            it = QListWidgetItem()
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked)
            self.list.addItem(it)
            self._label(i)
        self.list.currentRowChanged.connect(self.preview)
        sp.addWidget(self.list)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        arow = QHBoxLayout()
        arow.addWidget(QLabel("Co zrobić:"))
        self.action = QComboBox()
        self.action.activated.connect(self._action_changed)
        arow.addWidget(self.action, 1)
        rl.addLayout(arow)
        self.prev = QPlainTextEdit()
        self.prev.setReadOnly(True)
        rl.addWidget(self.prev, 1)
        sp.addWidget(right)
        sp.setSizes([480, 560])
        lay.addWidget(sp, 1)
        row = QHBoxLayout()
        for txt, val in (("Zaznacz wszystkie", Qt.Checked), ("Odznacz wszystkie", Qt.Unchecked)):
            b = QPushButton(txt)
            b.clicked.connect(lambda _=False, v=val: [self.list.item(i).setCheckState(v) for i in range(self.list.count())])
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        form = QFormLayout()
        self.cat = QComboBox()
        self.cat.setEditable(True)
        self.cat.addItems([""] + list(categories))
        self.cat.setCurrentText(coll.get('kategoria', ''))
        form.addRow("Kategoria dla wszystkich:", self.cat)
        self.tags = QLineEdit()
        self.tags.setPlaceholderText("np. siedlecki, schola")
        form.addRow("Tagi dla wszystkich:", self.tags)
        self.mp3 = QCheckBox("Pobierz nagrania (mp3) jako załączniki pieśni – linki zapisują się zawsze")
        self.mp3.setEnabled(any(s.get('youtube') for s in coll['piesni']))
        form.addRow("", self.mp3)
        self.pages = None
        if any(s.get('strony') for s in coll['piesni']):
            self.pages = QCheckBox("Dołącz nuty – strony śpiewnika z pieśnią jako PDF w załącznikach")
            self.pages.setChecked(True)
            form.addRow("", self.pages)
        lay.addLayout(form)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Importuj zaznaczone")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.list.setCurrentRow(0)

    def _label(self, i):
        s = self.coll['piesni'][i]
        nz = len([v for v in s['zwrotki_raw'].split("\n\n") if v.strip()])
        info = f"{s.get('numer', '')}. {s['title']}   ({nz} zwr." + (", refren" if s['refren'] else "") + \
               (", nagranie" if s.get('youtube') else "") + ")"
        act, target = self.actions[i]
        if act == 'merge':
            t = next((c[1] for c in self.cands[i] if c[0] == target), "?")
            info += f"   → dołączy do „{t}”"
        elif self.cands[i]:
            info += "   (podobna jest w bazie – doda nową)"
        self.list.item(i).setText(info)

    def _action_changed(self, k):
        row = self.list.currentRow()
        if row < 0:
            return
        self.actions[row] = self.action.itemData(k)
        self._label(row)
        self.preview(row)

    def preview(self, row):
        if row < 0:
            return
        s = self.coll['piesni'][row]
        self.action.blockSignals(True)
        self.action.clear()
        self.action.addItem("Dodaj jako nową pieśń", ('new', None))
        for sid, t, sc, why in self.cands[row]:
            self.action.addItem(f"Dołącz do „{t}” ({int(sc * 100)}%, {why}) – inny tekst jako wersja, nuty jako aranżacja",
                                ('merge', sid))
        k = max(0, self.action.findData(self.actions[row]))
        self.action.setCurrentIndex(k)
        self.action.setEnabled(bool(self.cands[row]))
        self.action.blockSignals(False)
        txt = s['title'] + "\n\n"
        if s['refren']:
            txt += "Ref.: " + s['refren'] + "\n\n"
        txt += s['zwrotki_raw']
        if s['uwagi']:
            txt += "\n\n[uwagi] " + s['uwagi']
        if s.get('kategoria') or s.get('tagi'):
            txt += "\n[kategoria] " + (s.get('kategoria') or "–") + ("   [tagi] " + s['tagi'] if s.get('tagi') else "")
        if s.get('strony'):
            txt += "\n[nuty] strony " + ", ".join(str(p + 1) for p in s['strony']) + \
                "\nSłowa spod nut są odczytywane z układu PDF – sprawdź je przed użyciem."
        act, target = self.actions[row]
        if act == 'merge' and self.get_fn:
            b = self.get_fn(target)
            if b:
                txt += f"\n\n────────  W bazie: „{b['title']}”  ────────\n"
                if b.get('refren'):
                    txt += "Ref.: " + b['refren'] + "\n\n"
                txt += b.get('zwrotki_raw', '')
        if s.get('youtube'):
            txt += "\n[nagranie] " + s['youtube'].split("\t")[0]
        self.prev.setPlainText(txt)

    def chosen(self):
        out = []
        for i in range(self.list.count()):
            if self.list.item(i).checkState() == Qt.Checked:
                s = dict(self.coll['piesni'][i])
                s['_akcja'], s['_cel'] = self.actions[i]
                if self.cat.currentText().strip():
                    s['kategoria'] = self.cat.currentText().strip()
                if self.tags.text().strip():
                    s['tagi'] = ", ".join(x for x in (s.get('tagi', ''), self.tags.text().strip()) if x)
                out.append(s)
        return out
