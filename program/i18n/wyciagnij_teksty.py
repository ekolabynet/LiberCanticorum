"""Zbiera z kodu programu teksty interfejsu i dopisuje brakujące do plików tłumaczeń (i18n/*.json).

Użycie:   python3 i18n/wyciagnij_teksty.py          – uzupełnia en.json, fr.json, es.json… o puste pozycje
          python3 i18n/wyciagnij_teksty.py de       – zakłada nowy język (de.json) z pustymi tłumaczeniami
Tłumacz wpisuje tłumaczenia w miejsce pustych "" – program użyje ich po ponownym uruchomieniu.
Wzorce z miejscami na wartości zapisuje się z nawiasami, np. "Zaznaczone pieśni: {n}": "Selected songs: {n}".
"""
import ast
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
CALLS = {'act', 'addMenu', 'QPushButton', 'QLabel', 'QCheckBox', 'addTab', 'setText', 'setToolTip', 'setWindowTitle',
         'addAction', 'setPlaceholderText', 'QGroupBox', 'addItem', 'addItems', 'btn', 'QRadioButton', 'QToolButton',
         'setTabText', 'setHeaderLabels', 'QAction', 'information', 'warning', 'question', 'critical', 'getText',
         'getItem', 'showMessage', 'tr', '_'}
SKIP = re.compile(r"^(Ctrl|Shift|Alt|F\d+|[\W\d_]+)(\+|$)|^https?://|^[a-z_]+$")


def collect():
    found = []
    for f in sorted(os.listdir(SRC)):
        if not f.endswith(".py") or f.startswith(("generuj_", "spiewnik_slajdy")):
            continue
        tree = ast.parse(open(os.path.join(SRC, f), encoding="utf-8").read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, 'id', '')
            if name not in CALLS:
                continue
            vals = []
            for a in node.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    vals.append(a.value)
                elif isinstance(a, (ast.List, ast.Tuple)):
                    vals += [e.value for e in a.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                elif isinstance(a, ast.JoinedStr):           # f"…{x}…" → wzorzec „…{a}…”
                    parts, k = [], 0
                    for v in a.values:
                        if isinstance(v, ast.Constant):
                            parts.append(v.value)
                        else:
                            parts.append("{" + "abcdefgh"[min(k, 7)] + "}")
                            k += 1
                    vals.append("".join(parts))
            for v in vals:
                if re.search(r"[A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ]{2}", v) and not SKIP.match(v) and len(v) < 500 and v not in found:
                    found.append(v)
    return found


def main():
    texts = collect()
    langs = sys.argv[1:] or [f[:-5] for f in os.listdir(HERE) if re.fullmatch(r"[a-z]{2}(_[A-Z]{2})?\.json", f)]
    json.dump({t: "" for t in texts}, open(os.path.join(HERE, "szablon.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for lang in langs:
        path = os.path.join(HERE, f"{lang}.json")
        try:
            data = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            data = {"_jezyk": lang, "teksty": {}}
        tx = data.setdefault("teksty", {})
        added = 0
        for t in texts:
            if t not in tx:
                tx[t] = ""
                added += 1
        json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        done = sum(1 for v in tx.values() if v)
        print(f"{lang}: {done} przetłumaczonych z {len(tx)} (dopisano {added} nowych)")


if __name__ == "__main__":
    main()
