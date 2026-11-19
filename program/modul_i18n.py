"""Tłumaczenia interfejsu – Liber Canticorum.

Mechanizm „podkładania” tłumaczeń bez zmieniania kodu programu:
* teksty interfejsu są pisane po polsku; plik ``i18n/<język>.json`` zawiera pary
  „tekst polski” → „tłumaczenie” (także wzorce z miejscami na liczby i nazwy: ``{n}``, ``{t}``),
* przy pokazaniu każdego okna (i co chwilę dla okna aktywnego) program podmienia teksty
  napisów, przycisków, podpowiedzi, menu, zakładek i tytułów okien,
* nowy język = nowy plik ``i18n/xx.json`` (np. ``de.json``) – pojawi się sam w menu
  Ustawienia → Język / Language,
* ``python3 i18n/wyciagnij_teksty.py`` zbiera z kodu nowe teksty i dopisuje je (z pustym
  tłumaczeniem) do wszystkich plików językowych – tłumacz uzupełnia puste miejsca.

Dane użytkownika (tytuły i teksty pieśni, kategorie, nazwy plików) nie są tłumaczone.
"""
import json
import os
import re

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "i18n")
NAMES = {'pl': "Polski", 'en': "English", 'fr': "Français", 'es': "Español", 'de': "Deutsch", 'it': "Italiano",
         'cs': "Čeština", 'sk': "Slovenčina", 'uk': "Українська", 'pt': "Português", 'sw': "Kiswahili",
         'ja': "日本語", 'zh': "中文", 'vi': "Tiếng Việt", 'nb': "Norsk", 'sv': "Svenska", 'is': "Íslenska",
         'hr': "Hrvatski", 'ar': "العربية", 'lt': "Lietuvių", 'tl': "Filipino (Tagalog)", 'hu': "Magyar",
         'ro': "Română", 'ko': "한국어", 'ml': "മലയാളം", 'la': "Latina"}
RTL = {'ar', 'he', 'fa', 'ur'}                       # języki pisane od prawej do lewej
ALIASES = {'no': 'nb', 'nn': 'nb', 'fil': 'tl'}       # kody systemowe → pliki tłumaczeń

LANG = 'pl'
_EXACT = {}
_PATTERNS = []                     # (regex, szablon tłumaczenia)


def available():
    """[(kod, nazwa)] – polski i języki z plikami w i18n/."""
    out = [('pl', NAMES['pl'])]
    try:
        for f in sorted(os.listdir(DIR)):
            m = re.fullmatch(r"([a-z]{2}(?:_[A-Z]{2})?)\.json", f)
            if m and m.group(1) != 'pl':
                out.append((m.group(1), NAMES.get(m.group(1), m.group(1))))
    except OSError:
        pass
    return out


def _pattern(key):
    """'Zaznaczone pieśni: {n}' → regex z nazwanymi grupami."""
    parts = re.split(r"(\{[a-z]\w*\})", key)
    def grp(p):
        name = p[1:-1]
        return f"(?P<{name}>\\d[\\d\\s.,]*)" if name == "n" else f"(?P<{name}>.*?)"      # {n} – liczba
    rx = "".join(grp(p) if re.fullmatch(r"\{[a-z]\w*\}", p) else re.escape(p) for p in parts)
    return re.compile("^" + rx + "$", re.S)


def load(lang):
    """Wczytuje katalog języka (pl = bez tłumaczenia)."""
    global LANG, _EXACT, _PATTERNS
    LANG, _EXACT, _PATTERNS = ALIASES.get(lang, lang) or 'pl', {}, []
    if LANG == 'pl':
        return
    try:
        with open(os.path.join(DIR, f"{LANG}.json"), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        LANG = 'pl'
        return
    merged = {}
    if LANG != 'en':                 # czego brak w tym języku – po angielsku (a nie po polsku)
        try:
            with open(os.path.join(DIR, "en.json"), encoding="utf-8") as f:
                merged.update({k: v for k, v in (json.load(f).get("teksty") or {}).items() if v})
        except (OSError, ValueError):
            pass
    merged.update({k: v for k, v in (data.get("teksty") or data).items() if v})
    pats = {}
    for k, v in merged.items():
        if k.startswith("_"):
            continue
        if re.search(r"\{[a-z]\w*\}", k):
            pats[k] = v
        else:
            _EXACT[k] = v
    # najpierw wzorce z najdłuższym stałym tekstem (bardziej szczegółowe)
    for k in sorted(pats, key=lambda k: -len(re.sub(r"\{[a-z]\w*\}", "", k))):
        _PATTERNS.append((_pattern(k), pats[k]))


def is_rtl():
    return LANG in RTL


def tr(s):
    """Tłumaczenie tekstu (albo ten sam tekst, gdy brak w katalogu)."""
    if LANG == 'pl' or not s:
        return s
    t = _EXACT.get(s)
    if t is not None:
        return t
    # tekst z akceleratorem „&” albo z wielokropkiem na końcu
    bare = s.replace("&", "")
    if bare != s and bare in _EXACT:
        return _EXACT[bare]
    m = re.fullmatch(r"(.+?)(\s+\((?:Ctrl|Shift|Alt|F\d|Esc|Del|Enter|Space|Spacja)[^()]*\))", s, re.S)
    if m and m.group(1) in _EXACT:                          # „Polecenie  (Ctrl+N)” – skrót bez zmian
        return _EXACT[m.group(1)] + m.group(2)
    m = re.fullmatch(r"(<b>)(.*?)(</b>)", s, re.S)          # pogrubiony napis – tłumacz środek
    if m and m.group(2) in _EXACT:
        return m.group(1) + _EXACT[m.group(2)] + m.group(3)
    for rx, tmpl in _PATTERNS:
        m = rx.match(s)
        if m:
            try:
                return tmpl.format(**{k: tr(v) for k, v in m.groupdict().items()})
            except (KeyError, IndexError, ValueError):
                return s
    return s


_ = tr


def system_language():
    try:
        from PySide6.QtCore import QLocale
        code = QLocale.system().name().split("_")[0]
    except Exception:
        code = "pl"
    code = ALIASES.get(code, code)
    return code if code in dict(available()) else ('en' if code != 'pl' and 'en' in dict(available()) else 'pl')


# ---------------------------------------------------------------------
# podmiana tekstów w oknach Qt
# ---------------------------------------------------------------------
def translate_widget(root):
    """Tłumaczy teksty w oknie i wszystkich jego elementach (idempotentne – przetłumaczone zostają)."""
    if LANG == 'pl':
        return
    from PySide6.QtWidgets import (QWidget, QLabel, QAbstractButton, QLineEdit, QGroupBox, QTabWidget, QMenu,
                                   QComboBox, QMenuBar, QTreeWidget, QDialog, QMainWindow, QTabBar)
    widgets = [root] + root.findChildren(QWidget)
    for w in widgets:
        try:
            if w.isWindow():
                t = w.windowTitle()
                n = tr(t)
                if n != t:
                    w.setWindowTitle(n)
            tip = w.toolTip()
            if tip:
                n = tr(tip)
                if n != tip:
                    w.setToolTip(n)
            if isinstance(w, (QLabel, QAbstractButton)):
                t = w.text()
                n = tr(t)
                if n != t:
                    w.setText(n)
            elif isinstance(w, QLineEdit):
                t = w.placeholderText()
                n = tr(t)
                if n != t:
                    w.setPlaceholderText(n)
            elif isinstance(w, QGroupBox):
                t = w.title()
                n = tr(t)
                if n != t:
                    w.setTitle(n)
            elif isinstance(w, QTabBar):
                for i in range(w.count()):
                    t = w.tabText(i)
                    n = tr(t)
                    if n != t:
                        w.setTabText(i, n)
            elif isinstance(w, QComboBox) and not w.isEditable() and w.property("i18n_no") is not True:
                for i in range(w.count()):
                    t = w.itemText(i)
                    n = tr(t)
                    if n != t:
                        w.setItemText(i, n)
            elif isinstance(w, QTreeWidget):
                h = w.headerItem()
                for c in range(h.columnCount()):
                    t = h.text(c)
                    n = tr(t)
                    if n != t:
                        h.setText(c, n)
            if isinstance(w, (QMenu, QMenuBar)) or w.actions():
                _translate_actions(w.actions())
        except RuntimeError:                         # widżet już usunięty
            continue


def _translate_actions(actions):
    for a in actions:
        try:
            t = a.text()
            n = tr(t)
            if n != t:
                a.setText(n)
            tip = a.toolTip()
            if tip and tr(tip) != tip:
                a.setToolTip(tr(tip))
            m = a.menu()
            if m is not None:
                t = m.title()
                if tr(t) != t:
                    m.setTitle(tr(t))
                _translate_actions(m.actions())
        except RuntimeError:
            continue


def install(app):
    """Włącza tłumaczenie okien: przy pokazaniu i co 0,8 s dla okna aktywnego (teksty zmieniane w trakcie)."""
    if LANG == 'pl':
        return None
    from PySide6.QtCore import QObject, QEvent, QTimer, Qt
    if is_rtl():
        app.setLayoutDirection(Qt.RightToLeft)

    class _Filter(QObject):
        def eventFilter(self, obj, ev):
            if ev.type() == QEvent.Show and getattr(obj, "isWindow", None) and obj.isWindow():
                translate_widget(obj)
            return False
    f = _Filter(app)
    app.installEventFilter(f)
    t = QTimer(app)
    t.setInterval(800)

    def tick():
        w = app.activeWindow()
        if w is not None:
            translate_widget(w)
        for m in app.topLevelWidgets():          # otwarte menu i podpowiedzi
            if m.isVisible() and m.inherits("QMenu"):
                translate_widget(m)
    t.timeout.connect(tick)
    t.start()
    app._lc_i18n = (f, t)
    return f
