# Liber Canticorum – przegląd pieśni przed importem (zbiory, śpiewniki, foldery z prezentacjami)
# Copyright (C) 2026  Liber Canticorum contributors
# GPL-3.0-or-later
"""Tabela pieśni do importu: wiele zaznaczonych naraz → kategoria, źródło, tagi, co zrobić
(nowa / dołącz do podobnej z bazy / pomiń), rozdzielanie „sklejonych” pieśni."""

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMessageBox,
                               QPlainTextEdit, QPushButton, QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

NEW, MERGE, SKIP = 'new', 'merge', 'skip'
LEGEND = ("Każdy wiersz to jedna pieśń. Zaznacz wiersze (Ctrl albo Shift – wiele naraz) i użyj przycisków pod listą.<br>"
          "<b>➕ Nowa</b> – doda pieśń do bazy. <b>🔗 Dołącz</b> – taka pieśń już jest w bazie: tekst trafi do niej jako "
          "wersja, nic nie zostanie nadpisane. <b>⛔ Pomiń</b> – nie importuj. "
          "<b>✂ Rozdziel</b> – gdy w jednym pliku jest kilka pieśni.")


def _fold(t):
    import unicodedata
    t = unicodedata.normalize('NFD', (t or '').lower().replace('ł', 'l'))
    return ''.join(c for c in t if not unicodedata.combining(c))


def _first_line(lines):
    t = re.sub(r"[\uf000-\uf0ff]", " ", next((l for l in lines if l.strip()), "")).strip()
    t = re.sub(r"^\s*(\d{1,2}\s*[.)]|ref(ren)?\s*[.:])\s*", "", t, flags=re.I)
    t = t.strip(" ,;.")
    if len(t) > 50:                                  # długi pierwszy wiersz: do przecinka przed 50. znakiem
        cut = max(t.rfind(",", 0, 50), t.rfind(";", 0, 50), t.rfind("!", 0, 50))
        t = t[:cut] if cut > 15 else t[:50].rsplit(" ", 1)[0]
    return t.strip(" ,;.") or "Bez tytułu"


class SplitDialog(QDialog):
    """Rozdzielenie jednej pozycji na kilka pieśni: zaznacz, od którego slajdu / zwrotki zaczyna się kolejna."""

    def __init__(self, song, parent=None):
        super().__init__(parent)
        self.song = song
        self.setWindowTitle(f"Rozdziel: {song['title']}")
        self.resize(820, 640)
        self.units = self._units(song)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Zaznacz fragmenty, od których zaczyna się <b>kolejna pieśń</b>, i popraw jej tytuł "
                             "(dwuklik w kolumnie „Tytuł”). Pierwszy fragment zawsze zaczyna pieśń."))
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Nowa pieśń", "Tytuł", "Fragment"])
        self.tree.setRootIsDecorated(False)
        self.tree.setWordWrap(True)
        self.tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        for i, (kind, lines) in enumerate(self.units):
            it = QTreeWidgetItem(["", "", ("Ref.: " if kind == 'ref' else "") + " / ".join(lines[:4]) +
                                  (" …" if len(lines) > 4 else "")])
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
            it.setCheckState(0, Qt.Checked if i == 0 or self._looks_like_start(i) else Qt.Unchecked)
            self.tree.addTopLevelItem(it)
        self.tree.itemChanged.connect(self._sync)
        self._sync()
        self.tree.resizeColumnToContents(0)
        self.tree.setColumnWidth(1, 240)
        lay.addWidget(self.tree, 1)
        self.info = QLabel()
        lay.addWidget(self.info)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Rozdziel")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    @staticmethod
    def _units(song):
        if song.get('_slajdy'):
            clean = lambda l: re.sub(r"\s{2,}", " ", re.sub(r"[\uf000-\uf0ff]", " ", l)).strip()
            return [('slide', [clean(l) for l in s if clean(l)]) for s in song['_slajdy'] if any(clean(l) for l in s)]
        out = [('ref', song['refren'].splitlines())] if song.get('refren', '').strip() else []
        out += [('verse', v.splitlines()) for v in song.get('zwrotki_raw', '').split("\n\n") if v.strip()]
        return out

    def _looks_like_start(self, i):
        """Podpowiedź: krótki slajd (sam tytuł) albo zwrotka „1.” po innych zwrotkach."""
        kind, lines = self.units[i]
        if i == 0:
            return True
        nxt = self.units[i + 1][1] if i + 1 < len(self.units) else []
        if len(lines) == 1 and len(lines[0]) <= 40 and nxt and re.match(r"^\s*1\s*[.)]", nxt[0]):
            return True                                  # slajd z samym tytułem przed zwrotką „1.”
        return bool(re.match(r"^\s*1\s*[.)]", lines[0] if lines else "")) and \
            any(re.match(r"^\s*[2-9]\s*[.)]", (u[1] or [""])[0]) for u in self.units[:i])

    def _sync(self, *_):
        self.tree.blockSignals(True)
        n = 0
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if i == 0 and it.checkState(0) != Qt.Checked:
                it.setCheckState(0, Qt.Checked)
            if it.checkState(0) == Qt.Checked:
                n += 1
                if not it.text(1):
                    it.setText(1, self.song['title'] if i == 0 else _first_line(self.units[i][1]))
                it.setForeground(1, self.palette().text())
            else:
                it.setText(1, "")
        self.tree.blockSignals(False)
        if hasattr(self, 'info'):
            self.info.setText(f"Powstanie pieśni: {n}")

    def parts(self):
        """[(tytuł, [jednostki])]"""
        out = []
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            if it.checkState(0) == Qt.Checked or not out:
                out.append((it.text(1).strip() or self.song['title'], []))
            out[-1][1].append(self.units[i])
        return out


class ReviewDialog(QDialog):
    """Przegląd przed importem. Zgodny z dawnym CollectionDialog: chosen(), mp3, ocr, pages."""

    def __init__(self, coll, similar_fn, categories, source="", parent=None, get_fn=None, sources=(),
                 rebuild_fn=None):
        """similar_fn(pieśń) → [(id, tytuł, podobieństwo, powód)]; get_fn(id) → pieśń z bazy;
        rebuild_fn(slajdy, tytuł, kategoria) → pieśń (dla pozycji z prezentacji – po rozdzieleniu)."""
        super().__init__(parent)
        self.similar_fn, self.get_fn, self.rebuild_fn = similar_fn, get_fn, rebuild_fn
        self.songs = [dict(s) for s in coll['piesni']]
        self.categories, self.sources = list(categories), [s for s in sources if s]
        self.cands, self.actions = [], []
        for s in self.songs:
            self._add_state(s)
        self.setWindowTitle(f"Przegląd przed importem – {len(self.songs)} pieśni")
        self.resize(1200, 760)
        lay = QVBoxLayout(self)
        head = coll.get('naglowek') or "Znalezione pieśni"
        top = QLabel(f"<b>{head}</b>" + (f" – {source}" if source else "") + "<br>" + LEGEND)
        top.setWordWrap(True)
        lay.addWidget(top)

        frow = QHBoxLayout()
        self.q = QLineEdit()
        self.q.setPlaceholderText("Szukaj w tytułach i tekstach…")
        self.f_cat = QComboBox()
        self.f_show = QComboBox()
        for lab, key in (("Wszystkie", None), ("➕ Nowe", NEW), ("🔗 Dołączane", MERGE), ("⛔ Pomijane", SKIP),
                         ("⚠ Podobne są w bazie", 'cand'), ("Bez kategorii", 'nocat')):
            self.f_show.addItem(lab, key)
        frow.addWidget(QLabel("Szukaj:"))
        frow.addWidget(self.q, 2)
        frow.addWidget(QLabel("Kategoria:"))
        frow.addWidget(self.f_cat, 1)
        frow.addWidget(QLabel("Pokaż:"))
        frow.addWidget(self.f_show, 1)
        lay.addLayout(frow)

        sp = QSplitter()
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Tytuł", "Zwr.", "Kategoria", "Źródło", "Co zrobić"])
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setSortingEnabled(True)
        self.tree.setAlternatingRowColors(True)
        h = self.tree.header()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for c, w in ((1, 50), (2, 150), (3, 130), (4, 220)):
            self.tree.setColumnWidth(c, w)
        self.tree.itemSelectionChanged.connect(self._selection)
        self.tree.itemDoubleClicked.connect(lambda *_: self.edit_title())
        sp.addWidget(self.tree)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        ar = QHBoxLayout()
        ar.addWidget(QLabel("Co zrobić:"))
        self.action = QComboBox()
        self.action.activated.connect(self._action_changed)
        ar.addWidget(self.action, 1)
        rl.addLayout(ar)
        self.prev = QPlainTextEdit()
        self.prev.setReadOnly(True)
        rl.addWidget(self.prev, 1)
        sp.addWidget(right)
        sp.setSizes([700, 480])
        lay.addWidget(sp, 1)

        brow = QHBoxLayout()
        self.sel_lab = QLabel()
        brow.addWidget(self.sel_lab)
        self.bulk = []
        for txt, tip, fn in (("📂 Kategoria…", "Ustaw kategorię zaznaczonym pieśniom", self.set_category),
                             ("📚 Źródło…", "Ustaw źródło (śpiewnik) zaznaczonym pieśniom", self.set_source),
                             ("🏷 Tagi…", "Dopisz tagi zaznaczonym pieśniom", self.set_tags),
                             ("➕ Nowa", "Zaznaczone dodaj jako nowe pieśni", lambda: self.set_action(NEW)),
                             ("🔗 Dołącz", "Zaznaczone dołącz do najbardziej podobnej pieśni w bazie (jeśli jest)",
                              lambda: self.set_action(MERGE)),
                             ("⛔ Pomiń", "Nie importuj zaznaczonych", lambda: self.set_action(SKIP)),
                             ("✂ Rozdziel…", "Podziel pozycję na kilka pieśni", self.split),
                             ("✎ Tytuł…", "Popraw tytuł", self.edit_title)):
            b = QPushButton(txt)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            brow.addWidget(b)
            self.bulk.append(b)
        brow.addStretch(1)
        b_all = QPushButton("Zaznacz widoczne")
        b_all.clicked.connect(self.tree.selectAll)
        brow.addWidget(b_all)
        lay.addLayout(brow)

        form = QFormLayout()
        self.src_all = QComboBox()
        self.src_all.setEditable(True)
        self.src_all.addItems([""] + self.sources)
        self.src_all.setCurrentText("")
        self.src_all.lineEdit().setPlaceholderText("np. Siedlecki, Śpiewnik parafialny – puste: bez zmian")
        form.addRow("Źródło (śpiewnik) dla wszystkich bez źródła:", self.src_all)
        self.tags = QLineEdit()
        self.tags.setPlaceholderText("np. schola, prezentacje – dopisywane do wszystkich")
        form.addRow("Tagi dla wszystkich:", self.tags)
        self.mp3 = QCheckBox("Pobierz nagrania (mp3) jako załączniki pieśni – linki zapisują się zawsze")
        self.mp3.setEnabled(any(s.get('youtube') for s in self.songs))
        if self.mp3.isEnabled():
            form.addRow("", self.mp3)
        self.ocr = None
        if any(s.get('szkic') for s in self.songs):
            self.ocr = QCheckBox("Wstaw słowa odczytane z obrazków nut (OCR) – tylko szkic, do poprawienia w edytorze")
            form.addRow("", self.ocr)
        self.pages = None
        if any(s.get('strony') for s in self.songs):
            self.pages = QCheckBox("Dołącz nuty – strony śpiewnika z pieśnią jako PDF w załącznikach")
            self.pages.setChecked(True)
            form.addRow("", self.pages)
        lay.addLayout(form)
        self.bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.bb.accepted.connect(self._accept)
        self.bb.rejected.connect(self.reject)
        lay.addWidget(self.bb)

        self.q.textChanged.connect(self._filter)
        self.f_cat.currentIndexChanged.connect(self._filter)
        self.f_show.currentIndexChanged.connect(self._filter)
        self._fill()

    # ---------------------------------------------------------------- stan
    def _add_state(self, s, at=None):
        try:
            c = list(self.similar_fn(s) or [])
        except TypeError:
            c = self.similar_fn(s['title'])
            c = [(c, s['title'], 1.0, "ten sam tytuł")] if isinstance(c, int) else list(c or [])
        act = (MERGE, c[0][0]) if c and c[0][2] >= 0.9 else (NEW, None)
        if at is None:
            self.cands.append(c)
            self.actions.append(act)
        else:
            self.cands.insert(at, c)
            self.actions.insert(at, act)

    def _act_text(self, i):
        act, target = self.actions[i]
        if act == SKIP:
            return "⛔ pomiń"
        if act == MERGE:
            t = next((c[1] for c in self.cands[i] if c[0] == target), "?")
            return f"🔗 dołącz do „{t}”"
        return "➕ nowa" + ("  (⚠ podobna w bazie)" if self.cands[i] else "")

    def _row(self, it, i):
        s = self.songs[i]
        nz = len([v for v in s.get('zwrotki_raw', '').split("\n\n") if v.strip()])
        it.setText(0, s['title'])
        it.setText(1, f"{nz}" + ("+R" if s.get('refren', '').strip() else ""))
        it.setText(2, s.get('kategoria', ''))
        it.setText(3, s.get('spiewnik', ''))
        it.setText(4, self._act_text(i))
        it.setData(0, Qt.UserRole, i)
        grey = self.actions[i][0] == SKIP
        for c in range(5):
            it.setForeground(c, QColor("gray") if grey else self.palette().text())
        if s.get('uwagi'):
            it.setToolTip(0, s['uwagi'])

    def _fill(self):
        keep = set(self._sel()) if hasattr(self, 'tree') else set()
        cur = self.f_cat.currentData()
        self.f_cat.blockSignals(True)
        self.f_cat.clear()
        self.f_cat.addItem("Wszystkie", None)
        cats = sorted({s.get('kategoria', '') for s in self.songs}, key=_fold)
        for c in cats:
            self.f_cat.addItem(c or "(bez kategorii)", c)
        self.f_cat.setCurrentIndex(max(0, self.f_cat.findData(cur)))
        self.f_cat.blockSignals(False)
        self.tree.setSortingEnabled(False)
        self.tree.clear()
        for i in range(len(self.songs)):
            it = QTreeWidgetItem()
            self._row(it, i)
            self.tree.addTopLevelItem(it)
        self.tree.setSortingEnabled(True)
        self._filter()
        for k in range(self.tree.topLevelItemCount()):        # zaznaczenie zostaje po zmianie kategorii
            it = self.tree.topLevelItem(k)
            if it.data(0, Qt.UserRole) in keep and not it.isHidden():
                it.setSelected(True)

    def _refresh_rows(self, idx):
        for k in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(k)
            if it.data(0, Qt.UserRole) in idx:
                self._row(it, it.data(0, Qt.UserRole))
        self._counts()
        self._selection()

    def _filter(self):
        q = _fold(self.q.text()).split()
        cat, show = self.f_cat.currentData(), self.f_show.currentData()
        for k in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(k)
            i = it.data(0, Qt.UserRole)
            s = self.songs[i]
            ok = all(w in _fold(s['title'] + " " + s.get('refren', '') + " " + s.get('zwrotki_raw', '')) for w in q)
            ok = ok and (cat is None or s.get('kategoria', '') == cat)
            if show in (NEW, MERGE, SKIP):
                ok = ok and self.actions[i][0] == show
            elif show == 'cand':
                ok = ok and bool(self.cands[i])
            elif show == 'nocat':
                ok = ok and not s.get('kategoria')
            it.setHidden(not ok)
        self._counts()

    def _counts(self):
        n = {NEW: 0, MERGE: 0, SKIP: 0}
        for a, _ in self.actions:
            n[a] += 1
        self.bb.button(QDialogButtonBox.Ok).setText(f"Importuj ({n[NEW]} nowych, {n[MERGE]} dołączanych)")
        self.setWindowTitle(f"Przegląd przed importem – {len(self.songs)} pieśni, pominięte: {n[SKIP]}")

    def _sel(self):
        return sorted({it.data(0, Qt.UserRole) for it in self.tree.selectedItems() if not it.isHidden()})

    def _selection(self):
        sel = self._sel()
        self.sel_lab.setText(f"Zaznaczone: {len(sel)}")
        for b in self.bulk:
            b.setEnabled(bool(sel))
        self.bulk[6].setEnabled(len(sel) == 1)
        self.bulk[7].setEnabled(len(sel) == 1)
        self._preview(sel[0] if len(sel) == 1 else None, len(sel))

    # ---------------------------------------------------------------- podgląd i akcja jednej pieśni
    def _preview(self, i, n=0):
        self.action.blockSignals(True)
        self.action.clear()
        if i is None:
            self.action.setEnabled(False)
            self.action.blockSignals(False)
            self.prev.setPlainText(f"Zaznaczono {n} pieśni – użyj przycisków pod listą." if n else
                                   "Wybierz pieśń, żeby zobaczyć tekst.")
            return
        s = self.songs[i]
        self.action.addItem("➕ Dodaj jako nową pieśń", (NEW, None))
        for sid, t, sc, why in self.cands[i]:
            self.action.addItem(f"🔗 Dołącz do „{t}” ({int(sc * 100)}%, {why}) – tekst jako wersja", (MERGE, sid))
        self.action.addItem("⛔ Pomiń – nie importuj", (SKIP, None))
        self.action.setCurrentIndex(max(0, self.action.findData(self.actions[i])))
        self.action.setEnabled(True)
        self.action.blockSignals(False)
        txt = s['title'] + "\n\n"
        if s.get('refren'):
            txt += "Ref.: " + s['refren'] + "\n\n"
        txt += s.get('zwrotki_raw', '')
        meta = [("kategoria", s.get('kategoria')), ("źródło", s.get('spiewnik')), ("tagi", s.get('tagi')),
                ("uwagi", s.get('uwagi'))]
        txt += "\n\n" + "\n".join(f"[{k}] {v}" for k, v in meta if v)
        if s.get('szkic'):
            txt += "\n\n[szkic słów z OCR]\n" + s['szkic']
        if s.get('strony'):
            txt += "\n[nuty] strony " + ", ".join(str(p + 1) for p in s['strony'])
        act, target = self.actions[i]
        if act == MERGE and self.get_fn:
            b = self.get_fn(target)
            if b:
                txt += f"\n\n────────  W bazie: „{b['title']}”  ────────\n"
                if b.get('refren'):
                    txt += "Ref.: " + b['refren'] + "\n\n"
                txt += b.get('zwrotki_raw', '')
        self.prev.setPlainText(txt)

    def _action_changed(self, k):
        sel = self._sel()
        if len(sel) == 1:
            self.actions[sel[0]] = self.action.itemData(k)
            self._refresh_rows(set(sel))

    # ---------------------------------------------------------------- działania na zaznaczonych
    def _ask(self, title, label, items, cur=""):
        t, ok = QInputDialog.getItem(self, title, label, [cur] + [x for x in items if x != cur], 0, True)
        return t.strip() if ok else None

    def set_category(self):
        sel = self._sel()
        cur = self.songs[sel[0]].get('kategoria', '') if sel else ''
        cats = sorted(set(self.categories) | {s.get('kategoria', '') for s in self.songs if s.get('kategoria')}, key=_fold)
        t = self._ask("Kategoria", f"Kategoria dla zaznaczonych pieśni ({len(sel)}):", cats, cur)
        if t is not None:
            for i in sel:
                self.songs[i]['kategoria'] = t
            self._fill()

    def set_source(self):
        sel = self._sel()
        cur = self.songs[sel[0]].get('spiewnik', '') if sel else ''
        t = self._ask("Źródło", f"Źródło (śpiewnik) dla zaznaczonych pieśni ({len(sel)}):", self.sources, cur)
        if t is not None:
            for i in sel:
                self.songs[i]['spiewnik'] = t
            if t and t not in self.sources:
                self.sources.append(t)
            self._refresh_rows(set(sel))

    def set_tags(self):
        sel = self._sel()
        t, ok = QInputDialog.getText(self, "Tagi", f"Dopisz tagi zaznaczonym pieśniom ({len(sel)}):")
        if ok and t.strip():
            for i in sel:
                s = self.songs[i]
                s['tagi'] = ", ".join(x for x in (s.get('tagi', ''), t.strip()) if x)
            self._refresh_rows(set(sel))

    def set_action(self, act):
        sel = self._sel()
        none = 0
        for i in sel:
            if act == MERGE:
                if self.cands[i]:
                    self.actions[i] = (MERGE, self.cands[i][0][0])
                else:
                    none += 1
            else:
                self.actions[i] = (act, None)
        self._refresh_rows(set(sel))
        self._filter()
        if none:
            QMessageBox.information(self, "Dołącz", f"Dla {none} z zaznaczonych pieśni nie ma podobnej w bazie – "
                                                    "zostaną dodane jako nowe.")

    def edit_title(self):
        sel = self._sel()
        if len(sel) != 1:
            return
        s = self.songs[sel[0]]
        t, ok = QInputDialog.getText(self, "Tytuł", "Tytuł pieśni:", text=s['title'])
        if ok and t.strip():
            s['title'] = t.strip()
            self._recheck(sel[0])
            self._refresh_rows(set(sel))

    def _recheck(self, i):
        try:
            c = list(self.similar_fn(self.songs[i]) or [])
        except TypeError:
            c = []
        self.cands[i] = c
        if self.actions[i][0] != SKIP:
            self.actions[i] = (MERGE, c[0][0]) if c and c[0][2] >= 0.9 else (NEW, None)

    def split(self):
        sel = self._sel()
        if len(sel) != 1:
            return
        i = sel[0]
        s = self.songs[i]
        dlg = SplitDialog(s, self)
        if not dlg.exec():
            return
        parts = dlg.parts()
        if len(parts) < 2:
            return
        new = []
        for title, units in parts:
            if s.get('_slajdy') and self.rebuild_fn:
                ns = self.rebuild_fn([u[1] for u in units], title, s.get('kategoria', ''))
                ns['_slajdy'] = [u[1] for u in units]
            else:
                ref = next(("\n".join(u[1]) for u in units if u[0] == 'ref'), "")
                ns = {'title': title, 'refren': ref,
                      'zwrotki_raw': "\n\n".join("\n".join(u[1]) for u in units if u[0] != 'ref'),
                      'kategoria': s.get('kategoria', ''), 'tagi': s.get('tagi', ''), 'youtube': ''}
            for k in ('kategoria', 'spiewnik', 'tagi'):
                ns[k] = ns.get(k) or s.get(k, '')
            ns['uwagi'] = " | ".join(x for x in (s.get('uwagi', '').split(" | ")[0], "rozdzielone z „%s”" % s['title']) if x)
            new.append(ns)
        del self.songs[i]
        del self.cands[i]
        del self.actions[i]
        for k, ns in enumerate(new):
            self.songs.insert(i + k, ns)
            self._add_state(ns, i + k)
        self._fill()

    # ---------------------------------------------------------------- wynik
    def _accept(self):
        if not any(a != SKIP for a, _ in self.actions):
            QMessageBox.information(self, "Import", "Wszystkie pieśni są pominięte.")
            return
        self.accept()

    def chosen(self):
        out = []
        src_all, tags_all = self.src_all.currentText().strip(), self.tags.text().strip()
        for s, (act, target) in zip(self.songs, self.actions):
            if act == SKIP:
                continue
            s = dict(s)
            s['_akcja'], s['_cel'] = act, target
            if self.ocr is not None and self.ocr.isChecked() and s.get('szkic') and not s['zwrotki_raw'].strip():
                s['zwrotki_raw'] = s['szkic']
                s['uwagi'] = " | ".join(x for x in (s.get('uwagi', ''), "słowa z OCR – sprawdź") if x)
            if src_all and not s.get('spiewnik'):
                s['spiewnik'] = src_all
            if tags_all:
                s['tagi'] = ", ".join(x for x in (s.get('tagi', ''), tags_all) if x)
            out.append(s)
        return out
