"""Prosty edytor melodii (à la MuseScore) – Liber Canticorum.

Skróty jak w MuseScore:
  1–8   wartość rytmiczna (1 = 64-ka … 4 = ósemka, 5 = ćwierćnuta, 6 = półnuta, 7 = cała, 8 = brevis)
  .     kropka przy wartości
  c d e f g a h   wysokość (wg tonacji; b = B♭ / polskie „B”), oktawa najbliższa poprzedniej nuty
  0     pauza
  ↑ ↓   o półton, Ctrl+↑ ↓ o oktawę;  ← →  poprzednia / następna nuta
  +     łuk (połączenie z następną nutą)
  Backspace / Delete – usuń;  Ctrl+Z – cofnij
  Ctrl+L  słowa: spacja = następna nuta, „-” = dzielenie wyrazu, Esc = koniec
  Ctrl+K  akordy: spacja = następna nuta, Esc = koniec

Melodia zapisywana jest jako głos „Sopran” (Choir Aahs), akordy jako „Organy” (Church Organ):
plik MusicXML (z projektem do dalszej edycji) i plik MIDI dla odtwarzacza.
"""
import copy
import io
import json
import math
import re
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

Q = 96                                     # tyknięć na ćwierćnutę (= divisions w MusicXML)
DUR_KEYS = {1: Q // 16, 2: Q // 8, 3: Q // 4, 4: Q // 2, 5: Q, 6: 2 * Q, 7: 4 * Q, 8: 8 * Q}
TYPE_NAMES = {Q // 16: '64th', Q // 8: '32nd', Q // 4: '16th', Q // 2: 'eighth', Q: 'quarter',
              2 * Q: 'half', 4 * Q: 'whole', 8 * Q: 'breve'}
STEP_NAMES = "CDEFGAB"
STEP_SEMI = [0, 2, 4, 5, 7, 9, 11]
LETTERS = {'c': 0, 'd': 1, 'e': 2, 'f': 3, 'g': 4, 'a': 5, 'h': 6, 'b': 6}
SHARP_ORDER = [3, 0, 4, 1, 5, 2, 6]        # F C G D A E H
FLAT_ORDER = [6, 2, 5, 1, 4, 0, 3]         # B E A D G C F
KEYS = [(-7, "Ces-dur / as-moll"), (-6, "Ges-dur / es-moll"), (-5, "Des-dur / b-moll"), (-4, "As-dur / f-moll"),
        (-3, "Es-dur / c-moll"), (-2, "B-dur / g-moll"), (-1, "F-dur / d-moll"), (0, "C-dur / a-moll"),
        (1, "G-dur / e-moll"), (2, "D-dur / h-moll"), (3, "A-dur / fis-moll"), (4, "E-dur / cis-moll"),
        (5, "H-dur / gis-moll"), (6, "Fis-dur / dis-moll"), (7, "Cis-dur / ais-moll")]
METERS = ["4/4", "3/4", "2/4", "2/2", "3/2", "6/8", "3/8", "9/8", "12/8", "5/4", "6/4"]
PROG_CHOIR, PROG_ORGAN = 52, 19            # GM (od zera): Choir Aahs, Church Organ
DUR_STEPS = [Q // 16, Q // 8, Q // 4, 3 * Q // 8, Q // 2, 3 * Q // 4, Q, 3 * Q // 2, 2 * Q, 3 * Q, 4 * Q, 6 * Q, 8 * Q]


def step_dur(dur, d):
    """Następna krótsza (d<0) / dłuższa (d>0) wartość, także z kropką."""
    k = min(range(len(DUR_STEPS)), key=lambda j: abs(DUR_STEPS[j] - dur))
    return DUR_STEPS[max(0, min(len(DUR_STEPS) - 1, k + d))]


def best_fifths(f):
    """Tonacja o najmniejszej liczbie znaków spośród enharmonicznych (−6…6; Fis-dur zamiast Ges-dur)."""
    f = (f + 5) % 12 - 5                         # −5 … 6
    return f


def key_alter(fifths, step):
    if fifths > 0 and step in SHARP_ORDER[:fifths]:
        return 1
    if fifths < 0 and step in FLAT_ORDER[:-fifths]:
        return -1
    return 0


def midi_of(step, octave, alter):
    return 12 * (octave + 1) + STEP_SEMI[step] + alter


def spell(pitch, fifths, up=True):
    """Wysokość MIDI → (krok, oktawa, znak) – najpierw zgodnie z tonacją, potem bez znaku, potem ♯/♭."""
    cands = []
    for step in range(7):
        for alter in (-1, 0, 1):
            pc = (STEP_SEMI[step] + alter) % 12
            if pc == pitch % 12:
                octave = (pitch - STEP_SEMI[step] - alter) // 12 - 1
                score = 0 if alter == key_alter(fifths, step) else (1 if alter == 0 else (2 if (alter > 0) == up else 3))
                cands.append((score, step, octave, alter))
    _, step, octave, alter = min(cands)
    return step, octave, alter


def split_ticks(t):
    """Długość w tyknięciach → wartości do zapisu [(wartość, kropka)] (od najdłuższej)."""
    out = []
    for base in sorted(TYPE_NAMES, reverse=True):
        while t >= base:
            if t >= base * 3 // 2 and base >= Q // 8 and (base * 3) % 2 == 0:
                out.append((base, True))
                t -= base * 3 // 2
            else:
                out.append((base, False))
                t -= base
    return out


def new_event(step=None, octave=4, alter=0, dur=Q):
    return {'step': step, 'oct': octave, 'alt': alter, 'dur': dur, 'tie': False,
            'lyric': '', 'hyph': False, 'chord': ''}


def is_rest(ev):
    return ev['step'] is None


def pitch(ev):
    return None if is_rest(ev) else midi_of(ev['step'], ev['oct'], ev['alt'])


# ---------------------------------------------------------------------
# akordy: symbol → dźwięki
# ---------------------------------------------------------------------
_ROOT = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'H': 11, 'B': 10}
RE_SYM = re.compile(r"^(?P<root>[A-Ha-h])(?P<acc>is|es|s|#|b(?![a-z]))?(?P<rest>[^/]*)(?:/(?P<bass>[A-Ha-h](?:is|es|s|#|b)?))?$")


def _semi(root, acc):
    n = _ROOT[root.upper()]
    if acc in ('is', '#'):
        n += 1
    elif acc in ('es', 's', 'b'):
        n -= 1
    return n % 12


def parse_chord(sym):
    """'G', 'a', 'D7', 'Fis-moll', 'e7', 'Cmaj7', 'Hdim', 'Dsus4', 'C/E' → (pc_root, interwały, pc_basu, rodzaj, znak)
    albo None. Notacja polska: małe litery i „m” = moll, B = B♭, H = H."""
    m = RE_SYM.match(sym.strip().replace('♯', '#').replace('♭', 'b'))
    if not m:
        return None
    root, acc, rest = m.group('root'), m.group('acc') or '', m.group('rest') or ''
    rest = rest.lstrip('-').lower()
    minor = root.islower() or bool(re.match(r"^(m(?!aj)|moll|min)", rest))
    rest = re.sub(r"^(moll|min|m(?!aj))", "", rest)
    if 'dim' in rest or rest.startswith('0') or rest.startswith('°'):
        iv, kind = [0, 3, 6], 'diminished'
        if '7' in rest:
            iv.append(9)
            kind = 'diminished-seventh'
    elif 'aug' in rest or rest.startswith('+') or rest.startswith('5+'):
        iv, kind = [0, 4, 8], 'augmented'
    elif 'sus2' in rest:
        iv, kind = [0, 2, 7], 'suspended-second'
    elif 'sus' in rest:
        iv, kind = [0, 5, 7], 'suspended-fourth'
    else:
        iv, kind = ([0, 3, 7], 'minor') if minor else ([0, 4, 7], 'major')
    if 'maj7' in rest or '7+' in rest:
        iv.append(11)
        kind = 'major-seventh'
    elif re.search(r"(?<!\d)7", rest) and 'dim' not in rest:
        iv.append(10)
        kind = 'minor-seventh' if minor else ('dominant' if kind == 'major' else kind)
    elif re.search(r"(?<!\d)6", rest):
        iv.append(9)
        kind = 'minor-sixth' if minor else 'major-sixth'
    elif '9' in rest:
        iv += [10, 14]
        kind = 'dominant-ninth'
    rpc = _semi(root, acc)
    bpc = rpc
    if m.group('bass'):
        b = m.group('bass')
        bpc = _semi(b[0], b[1:])
    return rpc, iv, bpc, kind, acc


def chord_pitches(sym):
    """Realizacja na organach: bas w oktawie małej, akord w razsfalowanym położeniu wokół c¹–g¹."""
    p = parse_chord(sym)
    if not p:
        return []
    rpc, iv, bpc, _, _ = p
    bass = 36 + bpc if bpc >= 4 else 48 + bpc          # E2…D#3
    upper = sorted(set(55 + ((rpc + i - 7) % 12) for i in iv))   # G3…F#4
    return [bass] + [u for u in upper if u != bass]


def _xml_step(pc, acc):
    """Klasa wysokości → (krok, znak) do MusicXML; bemole gdy w symbolu był bemol."""
    flat = acc in ('es', 's', 'b')
    for step in range(7):
        for alter in ((-1, 0, 1) if flat else (1, 0, -1)):
            if (STEP_SEMI[step] + alter) % 12 == pc and (alter == 0 or (alter < 0) == flat):
                return STEP_NAMES[step], alter
    for step in range(7):
        for alter in (0, 1, -1):
            if (STEP_SEMI[step] + alter) % 12 == pc:
                return STEP_NAMES[step], alter


# ---------------------------------------------------------------------
# projekt: takty, eksport
# ---------------------------------------------------------------------
class Melody:
    def __init__(self, title="", fifths=0, meter="4/4", tempo=80, pickup=0, events=None):
        self.title, self.fifths, self.meter, self.tempo, self.pickup = title, fifths, meter, tempo, pickup
        self.events = events or []

    # --- zapis / odczyt projektu
    def to_json(self):
        return json.dumps({'wersja': 1, 'tytul': self.title, 'tonacja': self.fifths, 'metrum': self.meter,
                           'tempo': self.tempo, 'przedtakt': self.pickup, 'nuty': self.events}, ensure_ascii=False)

    @classmethod
    def from_json(cls, text):
        d = json.loads(text)
        evs = [dict(new_event(), **e) for e in d.get('nuty', [])]
        return cls(d.get('tytul', ''), d.get('tonacja', 0), d.get('metrum', '4/4'), d.get('tempo', 80),
                   d.get('przedtakt', 0), evs)

    @property
    def beats(self):
        n, d = self.meter.split('/')
        return int(n), int(d)

    @property
    def measure_len(self):
        n, d = self.beats
        return n * 4 * Q // d

    def measures(self):
        """Podział na takty: [[(indeks zdarzenia, początek w takcie, długość, pierwszy kawałek?, łuk dalej?)]]."""
        ml = self.measure_len
        cap = self.pickup if 0 < self.pickup < ml else ml
        out, cur, pos = [], [], 0
        for i, ev in enumerate(self.events):
            left = ev['dur']
            first = True
            while left > 0:
                take = min(left, cap - pos)
                left -= take
                nxt = self.events[i + 1] if i + 1 < len(self.events) else None
                tie_next = ev['tie'] and nxt is not None and not is_rest(ev) and pitch(nxt) == pitch(ev)
                cur.append((i, pos, take, first, left > 0 or tie_next))
                first = False
                pos += take
                if pos >= cap:
                    out.append(cur)
                    cur, pos, cap = [], 0, ml
        if cur:
            out.append(cur)
        return out

    def transpose(self, n, indices=None):
        """Transpozycja o n półtonów: całość (z tonacją i akordami) albo tylko wskazane nuty."""
        if indices is None:
            new_f = best_fifths(self.fifths + 7 * n)
            if n % 12:
                try:
                    from modul_akordy import transpose_chord
                    for ev in self.events:
                        if ev['chord'].strip():
                            ev['chord'] = transpose_chord(ev['chord'].strip(), n, flat=new_f < 0)
                except Exception:
                    pass
            self.fifths = new_f
            indices = range(len(self.events))
        for i in indices:
            ev = self.events[i]
            if not is_rest(ev):
                ev['step'], ev['oct'], ev['alt'] = spell(pitch(ev) + n, self.fifths, n >= 0)

    # --- MusicXML
    def musicxml(self):
        meas = self.measures()
        beats, btype = self.beats
        ml = self.measure_len
        lines = ['<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
                 '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" '
                 '"http://www.musicxml.org/dtds/partwise.dtd">',
                 '<score-partwise version="3.1">',
                 f'<work><work-title>{escape(self.title)}</work-title></work>',
                 '<identification><encoding><software>Liber Canticorum – edytor melodii</software></encoding>',
                 f'<miscellaneous><miscellaneous-field name="liber-canticorum">{escape(self.to_json())}'
                 '</miscellaneous-field></miscellaneous></identification>',
                 '<part-list>',
                 '<score-part id="P1"><part-name>Sopran</part-name><score-instrument id="P1-I1">'
                 '<instrument-name>Choir Aahs</instrument-name></score-instrument>'
                 f'<midi-instrument id="P1-I1"><midi-channel>1</midi-channel><midi-program>{PROG_CHOIR + 1}</midi-program>'
                 '</midi-instrument></score-part>']
        has_chords = any(e['chord'].strip() for e in self.events)
        if has_chords:
            lines.append('<score-part id="P2"><part-name>Organy</part-name><score-instrument id="P2-I1">'
                         '<instrument-name>Church Organ</instrument-name></score-instrument>'
                         f'<midi-instrument id="P2-I1"><midi-channel>2</midi-channel><midi-program>{PROG_ORGAN + 1}'
                         '</midi-program></midi-instrument></score-part>')
        lines.append('</part-list>')

        def attrs(clef):
            sign, line = ('G', 2) if clef == 'G' else ('F', 4)
            return (f'<attributes><divisions>{Q}</divisions><key><fifths>{self.fifths}</fifths></key>'
                    f'<time><beats>{beats}</beats><beat-type>{btype}</beat-type></time>'
                    f'<clef><sign>{sign}</sign><line>{line}</line></clef></attributes>')

        pick = bool(self.pickup) and bool(meas) and sum(c[2] for c in meas[0]) < ml

        def mopen(k, m):
            imp = ' implicit="yes"' if pick and k == 0 else ''
            return f'<measure number="{k if pick else k + 1}"{imp}>'

        # Sopran
        lines.append('<part id="P1">')
        prev_word_open = False
        for k, m in enumerate(meas):
            lines.append(mopen(k, m))
            if k == 0:
                lines.append(attrs('G'))
                lines.append(f'<direction placement="above"><direction-type><metronome><beat-unit>quarter</beat-unit>'
                             f'<per-minute>{self.tempo}</per-minute></metronome></direction-type>'
                             f'<sound tempo="{self.tempo}"/></direction>')
            shown = {}
            for (i, pos, ln, first, tie_on) in m:
                ev = self.events[i]
                if first and ev['chord'].strip():
                    lines.append(self._harmony(ev['chord']))
                pieces = split_ticks(ln)
                for pj, (base, dot) in enumerate(pieces):
                    d = base * 3 // 2 if dot else base
                    x = ['<note>']
                    if is_rest(ev):
                        x.append('<rest/>')
                    else:
                        x.append(f'<pitch><step>{STEP_NAMES[ev["step"]]}</step>'
                                 + (f'<alter>{ev["alt"]}</alter>' if ev['alt'] else '') + f'<octave>{ev["oct"]}</octave></pitch>')
                    x.append(f'<duration>{d}</duration>')
                    tie_start = not is_rest(ev) and (pj < len(pieces) - 1 or tie_on)
                    tie_stop = not is_rest(ev) and (pj > 0 or not first or (i > 0 and self._tied_from_prev(i)))
                    if tie_stop:
                        x.append('<tie type="stop"/>')
                    if tie_start:
                        x.append('<tie type="start"/>')
                    x.append(f'<voice>1</voice><type>{TYPE_NAMES[base]}</type>' + ('<dot/>' if dot else ''))
                    if not is_rest(ev):
                        key = (ev['step'], ev['oct'])
                        want = shown.get(key, key_alter(self.fifths, ev['step']))
                        if ev['alt'] != want:
                            x.append('<accidental>' + {-2: 'flat-flat', -1: 'flat', 0: 'natural', 1: 'sharp', 2: 'double-sharp'}[ev['alt']] + '</accidental>')
                        shown[key] = ev['alt']
                    if tie_start or tie_stop:
                        x.append('<notations>' + ('<tied type="stop"/>' if tie_stop else '') +
                                 ('<tied type="start"/>' if tie_start else '') + '</notations>')
                    if first and pj == 0 and ev['lyric'].strip() and not is_rest(ev):
                        syl = ('middle' if ev['hyph'] else 'end') if prev_word_open else ('begin' if ev['hyph'] else 'single')
                        prev_word_open = ev['hyph']
                        x.append(f'<lyric number="1"><syllabic>{syl}</syllabic><text>{escape(ev["lyric"].strip())}</text></lyric>')
                    x.append('</note>')
                    lines.append(''.join(x))
            if k == len(meas) - 1:
                lines.append('<barline location="right"><bar-style>light-heavy</bar-style></barline>')
            lines.append('</measure>')
        lines.append('</part>')

        # Organy
        if has_chords:
            lines.append('<part id="P2">')
            active = ''
            for k, m in enumerate(meas):
                lines.append(mopen(k, m))
                if k == 0:
                    lines.append(attrs('F'))
                total = sum(c[2] for c in m)
                changes = [(pos, self.events[i]['chord'].strip()) for (i, pos, ln, first, _) in m
                           if first and self.events[i]['chord'].strip()]
                segs, start, cur = [], 0, active
                for pos, sym in changes:
                    if pos > start:
                        segs.append((start, pos - start, cur))
                    start, cur = pos, sym
                segs.append((start, total - start, cur))
                active = cur
                for _, ln, sym in segs:
                    if ln <= 0:
                        continue
                    notes = chord_pitches(sym) if sym else []
                    for base, dot in split_ticks(ln):
                        d = base * 3 // 2 if dot else base
                        if not notes:
                            lines.append(f'<note><rest/><duration>{d}</duration><voice>1</voice><type>{TYPE_NAMES[base]}</type>'
                                         + ('<dot/>' if dot else '') + '</note>')
                            continue
                        for j, p in enumerate(notes):
                            st, oc, al = spell(p, self.fifths)
                            lines.append('<note>' + ('<chord/>' if j else '') +
                                         f'<pitch><step>{STEP_NAMES[st]}</step>' + (f'<alter>{al}</alter>' if al else '') +
                                         f'<octave>{oc}</octave></pitch><duration>{d}</duration><voice>1</voice>'
                                         f'<type>{TYPE_NAMES[base]}</type>' + ('<dot/>' if dot else '') + '</note>')
                if k == len(meas) - 1:
                    lines.append('<barline location="right"><bar-style>light-heavy</bar-style></barline>')
                lines.append('</measure>')
            lines.append('</part>')
        lines.append('</score-partwise>')
        return '\n'.join(lines).encode('utf-8')

    def _tied_from_prev(self, i):
        a, b = self.events[i - 1], self.events[i]
        return a['tie'] and not is_rest(a) and not is_rest(b) and pitch(a) == pitch(b)

    def _harmony(self, sym):
        p = parse_chord(sym)
        if not p:
            return f'<harmony><root><root-step>C</root-step></root><kind text="{escape(sym)}">none</kind></harmony>'
        rpc, _, bpc, kind, acc = p
        st, al = _xml_step(rpc, acc)
        x = f'<harmony><root><root-step>{st}</root-step>' + (f'<root-alter>{al}</root-alter>' if al else '') + '</root>'
        x += f'<kind text="{escape(sym.strip())}">{kind}</kind>'
        if bpc != rpc:
            bs, ba = _xml_step(bpc, acc)
            x += f'<bass><bass-step>{bs}</bass-step>' + (f'<bass-alter>{ba}</bass-alter>' if ba else '') + '</bass>'
        return x + '</harmony>'

    # --- MIDI
    def midi(self):
        import mido
        mid = mido.MidiFile(ticks_per_beat=Q)
        beats, btype = self.beats
        t0 = mido.MidiTrack()
        t0.append(mido.MetaMessage('track_name', name=_latin(self.title or 'Melodia'), time=0))
        t0.append(mido.MetaMessage('marker', text='lc:programs', time=0))
        t0.append(mido.MetaMessage('time_signature', numerator=beats, denominator=btype, time=0))
        t0.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(self.tempo), time=0))
        mid.tracks.append(t0)

        sop = mido.MidiTrack()
        sop.append(mido.MetaMessage('track_name', name='Sopran', time=0))
        sop.append(mido.Message('program_change', channel=0, program=PROG_CHOIR, time=0))
        abs_ev, t, held = [], 0, None              # held: (pitch, start) – nuta połączona łukiem
        for i, ev in enumerate(self.events):
            p = pitch(ev)
            if p is not None:
                if ev['lyric'].strip():
                    abs_ev.append((t, 1, mido.MetaMessage('lyrics', text=_latin(ev['lyric'].strip() + ('-' if ev['hyph'] else ' ')))))
                if held and held[0] == p:
                    pass                                         # ciąg dalszy łuku
                else:
                    if held:
                        abs_ev.append((t, 0, mido.Message('note_off', channel=0, note=held[0], velocity=0)))
                    abs_ev.append((t, 2, mido.Message('note_on', channel=0, note=p, velocity=88)))
                    held = (p, t)
                t += ev['dur']
                if not ev['tie']:
                    abs_ev.append((t, 0, mido.Message('note_off', channel=0, note=p, velocity=0)))
                    held = None
            else:
                if held:
                    abs_ev.append((t, 0, mido.Message('note_off', channel=0, note=held[0], velocity=0)))
                    held = None
                t += ev['dur']
        if held:
            abs_ev.append((t, 0, mido.Message('note_off', channel=0, note=held[0], velocity=0)))
        end = t
        _append_abs(sop, abs_ev)
        mid.tracks.append(sop)

        if any(e['chord'].strip() for e in self.events):
            org = mido.MidiTrack()
            org.append(mido.MetaMessage('track_name', name='Organy', time=0))
            org.append(mido.Message('program_change', channel=1, program=PROG_ORGAN, time=0))
            changes, t = [], 0
            for ev in self.events:
                if ev['chord'].strip() and chord_pitches(ev['chord']):
                    changes.append((t, chord_pitches(ev['chord'])))
                t += ev['dur']
            abs_ev = []
            for k, (start, notes) in enumerate(changes):
                stop = changes[k + 1][0] if k + 1 < len(changes) else end
                for p in notes:
                    abs_ev.append((start, 2, mido.Message('note_on', channel=1, note=p, velocity=58)))
                    abs_ev.append((stop, 0, mido.Message('note_off', channel=1, note=p, velocity=0)))
            _append_abs(org, abs_ev)
            mid.tracks.append(org)
        buf = io.BytesIO()
        mid.save(file=buf)
        return buf.getvalue()

    def chordpro(self):
        """Słowa z akordami w ChordPro (jeden wiersz na frazę zakończoną kropką/przecinkiem lub co 8 wyrazów)."""
        out, word, words = [], "", 0
        pending = ""
        for ev in self.events:
            if ev['chord'].strip():
                pending += f"[{ev['chord'].strip()}]"
            if is_rest(ev) or not ev['lyric'].strip():
                continue
            word += pending + ev['lyric'].strip()
            pending = ""
            if not ev['hyph']:
                out.append(word)
                word = ""
        if word or pending:
            out.append(word + pending)
        lines, cur = [], []
        for w in out:
            cur.append(w)
            if re.search(r"[.,;:!?]$", w) or len(cur) >= 8:
                lines.append(" ".join(cur))
                cur = []
        if cur:
            lines.append(" ".join(cur))
        return "\n".join(lines)

    # --- odczyt MusicXML (własny projekt albo prosta melodia z innego programu)
    @classmethod
    def from_musicxml(cls, data):
        text = data.decode('utf-8', 'replace') if isinstance(data, bytes) else data
        m = re.search(r'<miscellaneous-field name="liber-canticorum">(.*?)</miscellaneous-field>', text, re.S)
        if m:
            import html
            return cls.from_json(html.unescape(m.group(1)))
        root = ET.fromstring(re.sub(r"<!DOCTYPE[^>]*>", "", text).encode('utf-8'))
        mel = cls(title=(root.findtext('.//work-title') or root.findtext('.//movement-title') or ''))
        part = root.find('part')
        if part is None:
            return mel
        div, chord, word_open = Q, '', False
        for meas in part.findall('measure'):
            for el in meas:
                if el.tag == 'attributes':
                    div = int(el.findtext('divisions') or div)
                    if el.find('key/fifths') is not None:
                        mel.fifths = int(el.findtext('key/fifths'))
                    if el.find('time/beats') is not None:
                        mel.meter = f"{el.findtext('time/beats')}/{el.findtext('time/beat-type')}"
                elif el.tag == 'harmony':
                    chord = el.find('kind').get('text') or ''
                    if not chord:
                        st = el.findtext('root/root-step') or 'C'
                        chord = st.replace('B', 'H') + ('' if (el.findtext('kind') or '').startswith('major') else 'm')
                elif el.tag == 'direction' and el.find('sound') is not None and el.find('sound').get('tempo'):
                    mel.tempo = int(float(el.find('sound').get('tempo')))
                elif el.tag == 'note' and el.find('chord') is None and el.find('grace') is None:
                    if (el.findtext('voice') or '1') != '1' or el.find('duration') is None:
                        continue
                    dur = max(1, round(int(el.findtext('duration')) * Q / div))
                    if el.find('rest') is not None:
                        ev = new_event(dur=dur)
                    else:
                        st = STEP_NAMES.index(el.findtext('pitch/step'))
                        ev = new_event(st, int(el.findtext('pitch/octave')), int(float(el.findtext('pitch/alter') or 0)), dur)
                        ev['tie'] = any(t.get('type') == 'start' for t in el.findall('tie'))
                        ly = el.find('lyric')
                        if ly is not None and ly.findtext('text'):
                            ev['lyric'] = ly.findtext('text')
                            ev['hyph'] = (ly.findtext('syllabic') or 'single') in ('begin', 'middle')
                    if chord:
                        ev['chord'], chord = chord, ''
                    prev = mel.events[-1] if mel.events else None
                    if prev and prev['tie'] and not is_rest(ev) and pitch(prev) == pitch(ev) and not ev['lyric'] and not ev['chord']:
                        prev['dur'] += ev['dur']           # nuty związane łukiem → jedna
                        prev['tie'] = ev['tie']
                    else:
                        mel.events.append(ev)
        return mel


def _latin(s):
    """mido zapisuje tekst jako latin-1: polskie znaki przekazujemy jako bajty UTF-8."""
    return s.encode('utf-8').decode('latin-1')


def _append_abs(track, abs_ev):
    abs_ev.sort(key=lambda e: (e[0], e[1]))
    last = 0
    for t, _, msg in abs_ev:
        track.append(msg.copy(time=t - last))
        last = t


# ---------------------------------------------------------------------
# okno edytora
# ---------------------------------------------------------------------
try:
    from PySide6.QtCore import Qt, QRectF, QPointF, Signal
    from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QFontMetrics, QPainterPath, QKeySequence, QShortcut
    from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox, QLineEdit,
                                   QPushButton, QScrollArea, QMessageBox, QFileDialog, QSizePolicy, QToolButton)
except ImportError:                                            # testy bez Qt
    QWidget = QDialog = object

SP = 9                       # odstęp linii pięciolinii (px)
ACCENT = "#7A2E3A"



# czcionki z MuseScore (SIL Open Font License): Leland – znaki nutowe (SMuFL), Edwin – tekst
MUSIC_FONT = None
TEXT_FONT = None
_FONTS_LOADED = False


def load_fonts():
    """Wczytuje czcionki z folderu czcionki/ (raz). Zwraca (rodzina nutowa, rodzina tekstowa) albo None."""
    global MUSIC_FONT, TEXT_FONT, _FONTS_LOADED
    if _FONTS_LOADED:
        return MUSIC_FONT, TEXT_FONT
    _FONTS_LOADED = True
    import os
    from PySide6.QtGui import QFontDatabase
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "czcionki")
    for name, kind in (("Leland.otf", 'm'), ("Edwin-Roman.otf", 't'), ("Edwin-Italic.otf", 't'), ("Edwin-Bold.otf", 't')):
        path = os.path.join(d, name)
        if os.path.isfile(path):
            fid = QFontDatabase.addApplicationFont(path)
            fams = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
            if fams and kind == 'm':
                MUSIC_FONT = fams[0]
            elif fams and kind == 't' and not TEXT_FONT:
                TEXT_FONT = fams[0]
    return MUSIC_FONT, TEXT_FONT


def music_font():
    f = QFont(MUSIC_FONT)
    f.setPixelSize(4 * SP)                      # SMuFL: 1 em = wysokość pięciolinii (4 odstępy)
    return f


class ScoreCanvas(QWidget):
    changed = Signal() if QWidget is not object else None
    status = Signal(str) if QWidget is not object else None

    def __init__(self, melody, parent=None):
        super().__init__(parent)
        self.mel = melody
        self.sel = len(melody.events) - 1 if melody.events else None
        self.cur_dur, self.cur_dot = Q, False
        self.mode = 'notes'                     # notes / lyric / chord
        self.nav = False                        # ostatnio poruszano się strzałkami → cyfra zmienia zaznaczoną nutę
        self.anchor = None                      # początek zaznaczenia wielu nut (Shift)
        self.undo_stack = []
        self.hits = []                          # (QRectF, indeks)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumHeight(300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.clef_glyph = None
        load_fonts()
        if TEXT_FONT:
            f = QFont(TEXT_FONT)
            f.setPointSizeF(self.font().pointSizeF() + 1.5)
            self.setFont(f)

    # --- zmiany
    def push_undo(self):
        self.undo_stack.append((copy.deepcopy(self.mel.events), self.sel, self.mel.fifths))
        del self.undo_stack[:-100]

    def touch(self):
        self.updateGeometry()
        self.update()
        self.changed.emit()
        self.status.emit(self.describe())

    def describe(self):
        dname = {Q // 16: "64-ka", Q // 8: "32-ka", Q // 4: "szesnastka", Q // 2: "ósemka", Q: "ćwierćnuta",
                 2 * Q: "półnuta", 4 * Q: "cała nuta", 8 * Q: "brevis"}[self.cur_dur] + (" z kropką" if self.cur_dot else "")
        mode = {'notes': "Nuty", 'lyric': "SŁOWA (Esc – koniec)", 'chord': "AKORDY (Esc – koniec)"}[self.mode]
        n = len(self.sel_range())
        extra = f"   |   zaznaczone nuty: {n}" if n > 1 else ""
        return f"Tryb: {mode}   |   wartość: {dname}{extra}"

    def input_dur(self):
        return self.cur_dur * 3 // 2 if self.cur_dot else self.cur_dur

    def ref_pitch(self):
        for i in range((self.sel if self.sel is not None else len(self.mel.events) - 1), -1, -1):
            p = pitch(self.mel.events[i])
            if p is not None:
                return p
        return 67                                                  # g¹

    def add_note(self, letter):
        step = LETTERS[letter]
        alter = -1 if letter == 'b' else key_alter(self.mel.fifths, step)
        ref = self.ref_pitch()
        best = min(range(2, 7), key=lambda o: abs(midi_of(step, o, alter) - ref))
        self.insert(new_event(step, best, alter, self.input_dur()))

    def sel_range(self):
        """Indeksy zaznaczonych nut (jedna albo zakres od kotwicy do bieżącej)."""
        if self.sel is None:
            return []
        if self.anchor is None or self.anchor >= len(self.mel.events):
            return [self.sel]
        a, b = sorted((self.anchor, self.sel))
        return list(range(a, b + 1))

    def set_durs(self, dur=None, step=0):
        idx = self.sel_range()
        if not idx:
            return
        self.push_undo()
        for i in idx:
            ev = self.mel.events[i]
            ev['dur'] = dur if dur is not None else step_dur(ev['dur'], step)
        self.touch()

    def insert(self, ev):
        self.anchor = None
        self.push_undo()
        pos = (self.sel + 1) if self.sel is not None else len(self.mel.events)
        self.mel.events.insert(pos, ev)
        self.sel = pos
        self.nav = False
        self.touch()

    def set_pitch(self, delta):
        idx = [i for i in self.sel_range() if not is_rest(self.mel.events[i])]
        if not idx:
            return
        self.push_undo()
        for i in idx:
            ev = self.mel.events[i]
            if abs(delta) == 12:
                ev['oct'] += 1 if delta > 0 else -1
            else:
                ev['step'], ev['oct'], ev['alt'] = spell(pitch(ev) + delta, self.mel.fifths, delta > 0)
        self.touch()

    def delete(self, back=True):
        if self.sel is None or not self.mel.events:
            return
        self.push_undo()
        idx = self.sel_range()
        if len(idx) > 1:
            del self.mel.events[idx[0]:idx[-1] + 1]
            self.anchor = None
            self.sel = idx[0] - 1 if idx[0] > 0 else (0 if self.mel.events else None)
            return self.touch()
        del self.mel.events[self.sel]
        if back:
            self.sel = self.sel - 1 if self.sel > 0 else (0 if self.mel.events else None)
        else:
            self.sel = min(self.sel, len(self.mel.events) - 1) if self.mel.events else None
        if self.sel == -1:
            self.sel = None
        self.touch()

    def undo(self):
        if self.undo_stack:
            self.mel.events, self.sel, self.mel.fifths = self.undo_stack.pop()
            self.anchor = None
            self.touch()

    # --- klawiatura
    def keyPressEvent(self, e):
        k, mod, txt = e.key(), e.modifiers(), e.text()
        ctrl = bool(mod & Qt.ControlModifier)
        if ctrl and k == Qt.Key_L:
            return self.enter_mode('lyric')
        if ctrl and k == Qt.Key_K:
            return self.enter_mode('chord')
        if ctrl and k == Qt.Key_Z:
            return self.undo()
        if self.mode != 'notes':
            return self.text_key(e)
        shift = bool(mod & Qt.ShiftModifier)
        if ctrl and k == Qt.Key_A and self.mel.events:
            self.anchor, self.sel, self.nav = 0, len(self.mel.events) - 1, True
            return self.touch()
        if k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Home, Qt.Key_End):
            if shift and self.sel is not None:
                if self.anchor is None:
                    self.anchor = self.sel
            else:
                self.anchor = None
        if k in (Qt.Key_Left, Qt.Key_Right):
            if self.mel.events:
                n = len(self.mel.events)
                self.sel = max(0, (self.sel if self.sel is not None else n) + (-1 if k == Qt.Key_Left else 1))
                self.sel = min(self.sel, n - 1)
                self.nav = True
                self.touch()
            return
        if k == Qt.Key_Home:
            self.sel, self.nav = (0 if self.mel.events else None), True
            return self.touch()
        if k == Qt.Key_End:
            self.sel, self.nav = (len(self.mel.events) - 1 if self.mel.events else None), True
            return self.touch()
        if k in (Qt.Key_Up, Qt.Key_Down):
            return self.set_pitch((12 if ctrl else 1) * (1 if k == Qt.Key_Up else -1))
        if k == Qt.Key_Backspace:
            return self.delete(True)
        if k == Qt.Key_Delete:
            return self.delete(False)
        if k == Qt.Key_Escape:
            self.nav = False
            self.anchor = None
            return self.touch()
        if txt and txt in "12345678" and not ctrl:
            self.cur_dur, self.cur_dot = DUR_KEYS[int(txt)], False
            if self.nav and self.sel is not None:
                return self.set_durs(self.input_dur())
            return self.touch()
        if txt == '.':
            self.cur_dot = not self.cur_dot and self.cur_dur >= Q // 8
            if self.nav and self.sel is not None:
                return self.set_durs(self.input_dur())
            return self.touch()
        if txt == '0':
            return self.insert(new_event(dur=self.input_dur()))
        if txt == '+':
            if self.sel is not None and not is_rest(self.mel.events[self.sel]):
                self.push_undo()
                self.mel.events[self.sel]['tie'] = not self.mel.events[self.sel]['tie']
                self.touch()
            return
        if txt and txt.lower() in LETTERS and not ctrl:
            return self.add_note(txt.lower())
        super().keyPressEvent(e)

    def enter_mode(self, mode):
        if not self.mel.events:
            self.status.emit("Najpierw wpisz nuty.")
            return
        self.mode = mode
        if self.sel is None:
            self.sel = 0
        if mode == 'lyric':
            self._skip_rests(+1)
        self.touch()

    def _skip_rests(self, d):
        n = len(self.mel.events)
        while self.sel is not None and 0 <= self.sel < n and is_rest(self.mel.events[self.sel]):
            if not 0 <= self.sel + d < n:
                break
            self.sel += d

    def text_key(self, e):
        k, txt = e.key(), e.text()
        field = 'lyric' if self.mode == 'lyric' else 'chord'
        ev = self.mel.events[self.sel]
        n = len(self.mel.events)
        if k in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter):
            self.mode = 'notes'
            return self.touch()
        if k == Qt.Key_Backspace:
            self.push_undo()
            if ev[field]:
                ev[field] = ev[field][:-1]
                if field == 'lyric' and not ev[field]:
                    ev['hyph'] = False
            elif self.sel > 0:
                self.sel -= 1
                if field == 'lyric':
                    self._skip_rests(-1)
                    self.mel.events[self.sel]['hyph'] = False
            return self.touch()
        if k in (Qt.Key_Left, Qt.Key_Right):
            self.sel = max(0, min(n - 1, self.sel + (1 if k == Qt.Key_Right else -1)))
            if field == 'lyric':
                self._skip_rests(1 if k == Qt.Key_Right else -1)
            return self.touch()
        if txt == ' ' or (txt == '-' and field == 'lyric'):
            if field == 'lyric':
                ev['hyph'] = txt == '-'
            if self.sel < n - 1:
                self.sel += 1
                if field == 'lyric':
                    self._skip_rests(+1)
            else:
                self.mode = 'notes'
            return self.touch()
        if txt and txt.isprintable():
            self.push_undo()
            ev[field] += txt
            self.touch()

    # --- mysz
    def mousePressEvent(self, e):
        """Klik – zaznacz; Shift+klik – zaznacz kilka; lewy na zaznaczonej – krótsza wartość, prawy – dłuższa."""
        self.setFocus()
        if self.mode != 'notes':
            self.mode = 'notes'
        for r, i in self.hits:
            if not r.contains(e.position()):
                continue
            right = e.button() == Qt.RightButton
            inside = i in self.sel_range()
            if e.modifiers() & Qt.ShiftModifier and self.sel is not None:
                if self.anchor is None:
                    self.anchor = self.sel
                self.sel = i
            elif right:
                if not inside:
                    self.sel, self.anchor = i, None
                self.nav = True
                return self.set_durs(step=+1)
            elif inside and self.nav:
                return self.set_durs(step=-1)
            else:
                self.sel, self.anchor = i, None
            self.nav = True
            self.touch()
            return
        if not e.modifiers() & Qt.ShiftModifier and self.anchor is not None:
            self.anchor = None
            self.touch()

    def contextMenuEvent(self, e):
        e.accept()                               # prawy przycisk zmienia wartość nuty – bez menu

    # --- rysowanie
    def layout(self, width):
        """Systemy: [(y_pięciolinii, [(takt_k, [(kawałek, x)]...)], szer.)] – ze stałymi szerokościami."""
        meas = self.mel.measures()
        fm = QFontMetrics(self.font())
        lead_first = 60 + 9 * abs(self.mel.fifths) + 26
        lead = 60 + 9 * abs(self.mel.fifths)
        systems, cur, x = [], [], lead_first
        for k, m in enumerate(meas):
            items, w = [], 14
            for chunk in m:
                i, pos, ln, first, _ = chunk
                ev = self.mel.events[i]
                pieces = split_ticks(ln)
                for pj, (base, dot) in enumerate(pieces):
                    pw = 20 + 9 * max(0, math.log2(base / (Q / 4))) + (6 if dot else 0)
                    if first and pj == 0:
                        if ev['lyric']:
                            pw = max(pw, fm.horizontalAdvance(ev['lyric']) + (22 if ev['hyph'] else 10))
                        if ev['chord']:
                            pw = max(pw, fm.horizontalAdvance(ev['chord']) + 12)
                        if not is_rest(ev) and ev['alt'] != key_alter(self.mel.fifths, ev['step']):
                            pw += 8
                    items.append((chunk, pj, base, dot, w))
                    w += pw
            if cur and x + w > width - 10:
                systems.append(cur)
                cur, x = [], lead
            cur.append((k, items, x, w))
            x += w
        if cur:
            systems.append(cur)
        return systems

    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(900, 400)

    def system_height(self):
        return 16 * SP

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#FFFEFA"))
        width = self.width()
        systems = self.layout(width)
        sh = self.system_height()
        need = 30 + 40 + max(1, len(systems)) * sh
        if self.minimumHeight() != need:
            self.setMinimumHeight(need)
        title = self.mel.title or "Melodia"
        f = QFont(self.font())
        f.setPointSize(f.pointSize() + 4)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#333"))
        p.drawText(QRectF(0, 6, width, 30), Qt.AlignHCenter, title)
        p.setFont(self.font())
        self.hits = []
        y0 = 40 + 5 * SP
        shown = {}
        tie_from = None
        if not systems or not self.mel.events:
            self.draw_staff(p, y0, width, True)
            p.setPen(QColor("#888"))
            p.drawText(QRectF(0, y0 + 7 * SP, width, 40), Qt.AlignHCenter,
                       "Wpisz nuty literami c d e f g a h (b = B♭), wartości cyframi 1–8, pauza 0. "
                       "Ctrl+L – słowa, Ctrl+K – akordy.")
            return
        chosen = set(self.sel_range())
        for si, sysm in enumerate(systems):
            top = y0 + si * sh
            end_x = sysm[-1][2] + sysm[-1][3]
            self.draw_staff(p, top, end_x, si == 0)
            for (k, items, mx, mw) in sysm:
                shown = {}
                for (chunk, pj, base, dot, off) in items:
                    i, pos, ln, first, tie_on = chunk
                    ev = self.mel.events[i]
                    x = mx + off
                    selc = QColor(ACCENT) if i in chosen else QColor("#111")
                    if len(chosen) > 1 and i in chosen:
                        p.fillRect(QRectF(x - 5, top - 1.5 * SP, SP * 2.6, 7 * SP), QColor(122, 46, 58, 28))
                    r = self.draw_event(p, ev, x, top, base, dot, selc, shown, first and pj == 0)
                    self.hits.append((r, i))
                    # łuk z poprzedniego kawałka
                    if tie_from is not None and not is_rest(ev):
                        tx, ty, tp = tie_from
                        if tp == pitch(ev):
                            path = QPainterPath(QPointF(tx + 6, ty + SP * 0.7))
                            path.quadTo(QPointF((tx + x) / 2 + 3, ty + SP * 1.6), QPointF(x, ty + SP * 0.7))
                            p.setPen(QPen(QColor("#111"), 1.2))
                            p.setBrush(Qt.NoBrush)
                            p.drawPath(path)
                    last_piece = pj == len(split_ticks(ln)) - 1
                    tie_from = (x, self.ypos(ev, top), pitch(ev)) if (not is_rest(ev) and (not last_piece or tie_on)) else None
                    if first and pj == 0:
                        self.draw_texts(p, ev, x, top, i, selc)
                bx = mx + mw
                p.setPen(QPen(QColor("#111"), 1))
                p.drawLine(QPointF(bx, top), QPointF(bx, top + 4 * SP))
                if si == len(systems) - 1 and k == sysm[-1][0]:
                    p.drawLine(QPointF(bx - 4, top), QPointF(bx - 4, top + 4 * SP))
                    p.fillRect(QRectF(bx - 2, top, 3, 4 * SP), QColor("#111"))
                if mx == sysm[0][2] and si > 0:            # numer taktu na początku systemu
                    p.setPen(QColor("#999"))
                    sf = QFont(self.font())
                    sf.setPointSize(max(7, sf.pointSize() - 3))
                    p.setFont(sf)
                    p.drawText(QPointF(16, top - 6), str(k + (0 if self.mel.pickup else 1)))
                    p.setFont(self.font())

    def ypos(self, ev, top):
        d = ev['oct'] * 7 + ev['step']
        return top + 4 * SP - (d - 30) * SP / 2          # E4 = dolna linia

    # --- rysowanie czcionką nutową Leland (SMuFL, z MuseScore); bez niej – rysunek zastępczy
    def draw_staff(self, p, top, right, first):
        if not MUSIC_FONT:
            return self._draw_staff_plain(p, top, right, first)
        p.setPen(QPen(QColor("#222"), 1))
        for j in range(5):
            p.drawLine(QPointF(14, top + j * SP), QPointF(right, top + j * SP))
        p.drawLine(QPointF(14, top), QPointF(14, top + 4 * SP))
        p.setFont(music_font())
        p.setPen(QColor("#111"))
        p.drawText(QPointF(20, top + 3 * SP), "\uE050")                      # klucz G na 2. linii
        x = 50
        if self.mel.fifths:
            sharp = self.mel.fifths > 0
            pos = [38, 35, 39, 36, 33, 37, 34] if sharp else [34, 37, 33, 36, 32, 35, 31]
            for j in range(abs(self.mel.fifths)):
                p.drawText(QPointF(x, top + 4 * SP - (pos[j] - 30) * SP / 2), "\uE262" if sharp else "\uE260")
                x += 9
        if first:
            n, d = self.mel.beats
            for val, y in ((n, top + SP), (d, top + 3 * SP)):
                txt = "".join(chr(0xE080 + int(c)) for c in str(val))
                w = QFontMetrics(music_font()).horizontalAdvance(txt)
                p.drawText(QPointF(x + 12 - w / 2, y), txt)
        p.setFont(self.font())

    def draw_event(self, p, ev, x, top, base, dot, color, shown, first):
        if not MUSIC_FONT:
            return self._draw_event_plain(p, ev, x, top, base, dot, color, shown, first)
        mf = music_font()
        p.setFont(mf)
        p.setPen(color)
        if is_rest(ev):
            glyph = {8 * Q: "\uE4E2", 4 * Q: "\uE4E3", 2 * Q: "\uE4E4", Q: "\uE4E5", Q // 2: "\uE4E6",
                     Q // 4: "\uE4E7", Q // 8: "\uE4E8", Q // 16: "\uE4E9"}[base]
            y = top + SP if base >= 4 * Q else top + 2 * SP
            p.drawText(QPointF(x, y), glyph)
            if dot:
                p.drawText(QPointF(x + SP * 1.8, top + 1.5 * SP), "\uE1E7")
            p.setFont(self.font())
            return QRectF(x - 2, top - SP, SP * 2.2, 6 * SP)
        y = self.ypos(ev, top)
        d = ev['oct'] * 7 + ev['step']
        head = "\uE0A0" if base >= 8 * Q else ("\uE0A2" if base >= 4 * Q else ("\uE0A3" if base >= 2 * Q else "\uE0A4"))
        hw = QFontMetrics(mf).horizontalAdvance(head)
        p.setPen(QPen(QColor("#222"), 1.2))
        for ld in (range(28, d - 1, -2) if d <= 28 else range(40, d + 1, 2) if d >= 40 else []):
            yy = top + 4 * SP - (ld - 30) * SP / 2
            p.drawLine(QPointF(x - 4, yy), QPointF(x + hw + 4, yy))
        p.setPen(color)
        key = (ev['step'], ev['oct'])
        want = shown.get(key, key_alter(self.mel.fifths, ev['step']))
        if ev['alt'] != want:
            acc = {-2: "\uE264", -1: "\uE260", 0: "\uE261", 1: "\uE262", 2: "\uE263"}[ev['alt']]
            p.drawText(QPointF(x - QFontMetrics(mf).horizontalAdvance(acc) - 3, y), acc)
        shown[key] = ev['alt']
        p.drawText(QPointF(x, y), head)
        if base < 4 * Q:
            up = d < 34
            sx = x + hw - 0.6 if up else x + 0.6
            sy = y - 3.5 * SP if up else y + 3.5 * SP
            flags = {Q // 2: 1, Q // 4: 2, Q // 8: 3, Q // 16: 4}.get(base, 0)
            if flags > 2:
                sy += (-1 if up else 1) * (flags - 2) * SP * 0.75
            p.setPen(QPen(color, 1.3))
            p.drawLine(QPointF(sx, y - (0.15 * SP if up else -0.15 * SP)), QPointF(sx, sy))
            if flags:
                cp = 0xE240 + 2 * (flags - 1) + (0 if up else 1)
                p.setPen(color)
                p.drawText(QPointF(sx - 0.6, sy), chr(cp))
        if dot:
            dy = y - SP / 2 if d % 2 == 0 else y
            p.drawText(QPointF(x + hw + SP * 0.35, dy), "\uE1E7")
        p.setFont(self.font())
        return QRectF(x - 4, min(y, top) - SP, hw + SP, max(y, top + 4 * SP) - min(y, top) + 2 * SP)

    def _draw_staff_plain(self, p, top, right, first):
        p.setPen(QPen(QColor("#222"), 1))
        for j in range(5):
            p.drawLine(QPointF(14, top + j * SP), QPointF(right, top + j * SP))
        p.drawLine(QPointF(14, top), QPointF(14, top + 4 * SP))
        # klucz wiolinowy
        f = QFont("Noto Music")
        f.setPixelSize(int(SP * 7.2))
        if self.clef_glyph is None:
            self.clef_glyph = QFontMetrics(f).inFontUcs4(0x1D11E)
        if self.clef_glyph:
            p.setFont(f)
            p.setPen(QColor("#111"))
            p.drawText(QPointF(18, top + 4 * SP + SP * 1.4), "\U0001D11E")
        else:
            ff = QFont("serif")
            ff.setPixelSize(int(SP * 5.2))
            ff.setItalic(True)
            ff.setBold(True)
            p.setFont(ff)
            p.drawText(QPointF(20, top + 4 * SP + SP * 0.6), "G")
        x = 50
        fk = QFont(self.font())
        fk.setPixelSize(int(SP * 2.6))
        p.setFont(fk)
        if self.mel.fifths:
            sharp = self.mel.fifths > 0
            pos = [38, 35, 39, 36, 33, 37, 34] if sharp else [34, 37, 33, 36, 32, 35, 31]
            for j in range(abs(self.mel.fifths)):
                y = top + 4 * SP - (pos[j] - 30) * SP / 2
                p.drawText(QPointF(x, y + SP * 0.8 if not sharp else y + SP * 0.9), "♯" if sharp else "♭")
                x += 9
        if first:
            n, d = self.mel.beats
            ft = QFont(self.font())
            ft.setPixelSize(int(SP * 2.3))
            ft.setBold(True)
            p.setFont(ft)
            p.drawText(QRectF(x + 2, top - 2, 20, 2 * SP + 2), Qt.AlignCenter, str(n))
            p.drawText(QRectF(x + 2, top + 2 * SP - 2, 20, 2 * SP + 2), Qt.AlignCenter, str(d))
        p.setFont(self.font())

    def _draw_event_plain(self, p, ev, x, top, base, dot, color, shown, first):
        p.setPen(QPen(color, 1.3))
        p.setBrush(QBrush(color))
        if is_rest(ev):
            mid = top + 2 * SP
            if base >= 4 * Q:
                p.fillRect(QRectF(x, top + SP, SP * 1.2, SP * 0.5), color)
            elif base == 2 * Q:
                p.fillRect(QRectF(x, top + 1.5 * SP, SP * 1.2, SP * 0.5), color)
            elif base == Q:
                path = QPainterPath(QPointF(x + 3, mid - 1.5 * SP))
                path.lineTo(x + 8, mid - 0.5 * SP)
                path.lineTo(x + 3, mid + 0.3 * SP)
                path.lineTo(x + 8, mid + 1.2 * SP)
                path.quadTo(QPointF(x, mid + 0.8 * SP), QPointF(x + 4, mid + 1.8 * SP))
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(color, 2.2))
                p.drawPath(path)
            else:
                flags = {Q // 2: 1, Q // 4: 2, Q // 8: 3, Q // 16: 4}.get(base, 1)
                p.setPen(QPen(color, 1.6))
                p.drawLine(QPointF(x + 9, mid - SP), QPointF(x + 4, mid + 1.5 * SP))
                for j in range(flags):
                    yy = mid - SP + j * SP * 0.8
                    p.drawEllipse(QPointF(x + 3 - j, yy + 2), 2.2, 2.2)
                    p.drawLine(QPointF(x + 3 - j, yy + 2), QPointF(x + 9 - j * 0.6, yy))
            if dot:
                p.drawEllipse(QPointF(x + SP * 1.6, mid - SP / 2), 1.8, 1.8)
            return QRectF(x - 2, top - SP, SP * 2, 6 * SP)
        y = self.ypos(ev, top)
        d = ev['oct'] * 7 + ev['step']
        # linie dodane
        p.setPen(QPen(QColor("#222"), 1))
        for ld in range(28, d - 1, -2) if d <= 28 else []:
            yy = top + 4 * SP - (ld - 30) * SP / 2
            p.drawLine(QPointF(x - 4, yy), QPointF(x + SP * 1.4 + 4, yy))
        for ld in range(40, d + 1, 2) if d >= 40 else []:
            yy = top + 4 * SP - (ld - 30) * SP / 2
            p.drawLine(QPointF(x - 4, yy), QPointF(x + SP * 1.4 + 4, yy))
        # znak chromatyczny
        key = (ev['step'], ev['oct'])
        want = shown.get(key, key_alter(self.mel.fifths, ev['step']))
        if ev['alt'] != want:
            fa = QFont(self.font())
            fa.setPixelSize(int(SP * 2.2))
            p.setFont(fa)
            p.setPen(color)
            p.drawText(QPointF(x - 10, y + SP * 0.7), {-1: "♭", 0: "♮", 1: "♯", -2: "𝄫", 2: "𝄪"}[ev['alt']])
            p.setFont(self.font())
        shown[key] = ev['alt']
        # główka
        p.setPen(QPen(color, 1.4))
        hollow = base >= 2 * Q
        p.setBrush(Qt.NoBrush if hollow else QBrush(color))
        p.save()
        p.translate(x + SP * 0.7, y)
        p.rotate(-20)
        p.drawEllipse(QPointF(0, 0), SP * 0.68, SP * 0.46)
        p.restore()
        # laska i chorągiewki
        if base < 4 * Q:
            up = d < 34
            sx = x + SP * 1.33 if up else x + SP * 0.07
            sy = y - 3.4 * SP if up else y + 3.4 * SP
            p.setPen(QPen(color, 1.2))
            p.drawLine(QPointF(sx, y), QPointF(sx, sy))
            flags = {Q // 2: 1, Q // 4: 2, Q // 8: 3, Q // 16: 4}.get(base, 0)
            for j in range(flags):
                fy = sy + (j * SP * 0.8 if up else -j * SP * 0.8)
                path = QPainterPath(QPointF(sx, fy))
                path.quadTo(QPointF(sx + SP * 1.1, fy + (SP * 1.0 if up else -SP * 1.0)),
                            QPointF(sx + SP * 0.8, fy + (SP * 2.0 if up else -SP * 2.0)))
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(color, 1.6))
                p.drawPath(path)
        if dot:
            p.setBrush(QBrush(color))
            dy = y - SP / 2 if d % 2 == 0 else y
            p.drawEllipse(QPointF(x + SP * 1.9, dy), 1.8, 1.8)
        return QRectF(x - 4, min(y, top) - SP, SP * 2.2, max(y, top + 4 * SP) - min(y, top) + 2 * SP)

    def draw_texts(self, p, ev, x, top, i, color):
        fm = QFontMetrics(self.font())
        ly_y = top + 4 * SP + 3.4 * SP
        ch_y = top - 2.4 * SP
        # słowa
        text = ev['lyric']
        editing = (i == self.sel)
        if text or (editing and self.mode == 'lyric' and not is_rest(ev)):
            w = fm.horizontalAdvance(text or " ")
            cx = x + SP * 0.7 - w / 2
            if editing and self.mode == 'lyric':
                p.setPen(QPen(QColor(ACCENT), 1))
                p.setBrush(QColor(255, 240, 200))
                p.drawRect(QRectF(cx - 3, ly_y - fm.ascent() - 2, w + 6, fm.height() + 4))
            p.setPen(QColor("#111"))
            p.drawText(QPointF(cx, ly_y), text)
            if ev['hyph']:
                p.drawText(QPointF(cx + w + 5, ly_y), "–")
        # akordy
        sym = ev['chord']
        if sym or (editing and self.mode == 'chord'):
            fb = QFont(self.font())
            fb.setBold(True)
            p.setFont(fb)
            w = QFontMetrics(fb).horizontalAdvance(sym or " ")
            if editing and self.mode == 'chord':
                p.setPen(QPen(QColor(ACCENT), 1))
                p.setBrush(QColor(255, 240, 200))
                p.drawRect(QRectF(x - 3, ch_y - fm.ascent() - 2, w + 6, fm.height() + 4))
            p.setPen(QColor("#B22222") if parse_chord(sym or "C") else QColor("#888"))
            p.drawText(QPointF(x, ch_y), sym)
            p.setFont(self.font())


class MelodyEditor(QDialog):
    """Okno edytora. on_save(melodia) – zapis do pieśni (zwraca komunikat albo None)."""

    HELP = ("<b>Skróty (jak w MuseScore):</b> c d e f g a h – nuty (b = B♭), 0 – pauza, 1–8 – wartość "
            "(4 ósemka, 5 ćwierćnuta, 6 półnuta, 7 cała), . – kropka, ↑↓ półton, Ctrl+↑↓ oktawa, "
            "←→ wybór nuty (potem cyfra zmienia jej wartość), Shift+←→ / Shift+klik / Ctrl+A – wiele nut, "
            "klik na zaznaczonej nucie – krótsza, prawy klik – dłuższa, + łuk, Backspace – usuń, Ctrl+Z – cofnij. "
            "<b>Ctrl+L</b> – słowa (spacja = następna nuta, - = dzielenie), <b>Ctrl+K</b> – akordy, Esc – koniec.")

    def __init__(self, parent=None, melody=None, title="", on_save=None, on_chords=None, sf_path=None):
        super().__init__(parent)
        self.setWindowTitle("Edytor melodii – " + (title or "nowa melodia"))
        self.resize(1100, 720)
        self.mel = melody or Melody(title=title)
        if not self.mel.title:
            self.mel.title = title
        self.on_save, self.on_chords = on_save, on_chords
        self.saved = True
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Tytuł:"))
        self.e_title = QLineEdit(self.mel.title)
        self.e_title.textChanged.connect(self._meta)
        bar.addWidget(self.e_title, 2)
        bar.addWidget(QLabel("Tonacja:"))
        self.c_key = QComboBox()
        for f, name in KEYS:
            self.c_key.addItem(name, f)
        self.c_key.setCurrentIndex(self.mel.fifths + 7)
        self.c_key.currentIndexChanged.connect(self._key_changed)
        bar.addWidget(self.c_key)
        bar.addWidget(QLabel("Metrum:"))
        self.c_meter = QComboBox()
        self.c_meter.setEditable(True)
        self.c_meter.addItems(METERS)
        self.c_meter.setCurrentText(self.mel.meter)
        self.c_meter.currentTextChanged.connect(self._meta)
        bar.addWidget(self.c_meter)
        bar.addWidget(QLabel("Przedtakt:"))
        self.c_pick = QComboBox()
        for label, t in (("brak", 0), ("ósemka", Q // 2), ("ćwierćnuta", Q), ("ćwierćnuta z kropką", 3 * Q // 2),
                         ("półnuta", 2 * Q), ("3 ćwierćnuty", 3 * Q)):
            self.c_pick.addItem(label, t)
        self.c_pick.setCurrentIndex(max(0, self.c_pick.findData(self.mel.pickup)))
        self.c_pick.currentIndexChanged.connect(self._meta)
        bar.addWidget(self.c_pick)
        bar.addWidget(QLabel("Tempo ♩="))
        self.s_tempo = QSpinBox(minimum=20, maximum=240, value=self.mel.tempo)
        self.s_tempo.valueChanged.connect(self._meta)
        bar.addWidget(self.s_tempo)
        lay.addLayout(bar)

        self.canvas = ScoreCanvas(self.mel)
        self.canvas.changed.connect(self._dirty)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.canvas)
        lay.addWidget(scroll, 1)
        self.status = QLabel(self.canvas.describe())
        self.canvas.status.connect(self.status.setText)
        lay.addWidget(self.status)
        hl = QLabel(self.HELP)
        hl.setWordWrap(True)
        hl.setStyleSheet("color:#555;")
        lay.addWidget(hl)

        btns = QHBoxLayout()
        for label, fn, tip in (("♫ Odtwórz", self.play, "Sopran – chór, akordy – organy"),
                               ("Słowa (Ctrl+L)", lambda: self._mode('lyric'), ""),
                               ("Akordy (Ctrl+K)", lambda: self._mode('chord'), ""),
                               ("⇅ Transponuj…", self.transpose_dialog, "Całość z tonacją i akordami albo zaznaczone nuty"),
                               ("Eksport MusicXML…", self.export_xml, "Do MuseScore i innych programów"),
                               ("Eksport MIDI…", self.export_midi, "")):
            b = QPushButton(label)
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(fn)
            btns.addWidget(b)
        if on_chords:
            b = QPushButton("Akordy ze słowami → widok gitarowy")
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(self.to_chords)
            btns.addWidget(b)
        btns.addStretch(1)
        if on_save:
            b = QPushButton("💾 Zapisz w pieśni")
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(self.save)
            btns.addWidget(b)
        b = QPushButton("Zamknij")
        b.setFocusPolicy(Qt.NoFocus)
        b.clicked.connect(self.close)
        btns.addWidget(b)
        lay.addLayout(btns)
        for w in (self.e_title, self.c_key, self.c_meter, self.c_pick, self.s_tempo):
            w.setFocusPolicy(Qt.ClickFocus)
        self.canvas.setFocus()

    def transpose_dialog(self):
        from PySide6.QtWidgets import QInputDialog
        if not self.mel.events:
            return
        names = dict(KEYS)
        sel = self.canvas.sel_range()
        items, vals = [], []
        for n in list(range(-12, 0)) + list(range(1, 13)):
            f = best_fifths(self.mel.fifths + 7 * n)
            label = {12: "o oktawę w górę", -12: "o oktawę w dół"}.get(n, f"o {abs(n)} półton{'' if abs(n) == 1 else ('y' if abs(n) < 5 else 'ów')} {'w górę' if n > 0 else 'w dół'}")
            items.append(f"{label}  →  {names[f]}")
            vals.append(n)
        default = vals.index(2)
        what = "całą melodię (z tonacją i akordami)"
        if len(sel) > 1:
            what = f"zaznaczone nuty ({len(sel)}) – tonacja bez zmian"
        choice, ok = QInputDialog.getItem(self, "Transpozycja", f"Transponuj {what}:", items, default, False)
        if ok:
            n = vals[items.index(choice)]
            self.canvas.push_undo()
            if len(sel) > 1:
                self.mel.transpose(n, sel)
            else:
                self.mel.transpose(n)
                self.c_key.blockSignals(True)
                self.c_key.setCurrentIndex(self.mel.fifths + 7)
                self.c_key.blockSignals(False)
            self.canvas.touch()
        self.canvas.setFocus()

    def _mode(self, m):
        self.canvas.enter_mode(m)
        self.canvas.setFocus()

    def _dirty(self):
        self.saved = False
        if self.c_key.currentData() != self.mel.fifths:          # np. po cofnięciu transpozycji
            self.c_key.blockSignals(True)
            self.c_key.setCurrentIndex(self.mel.fifths + 7)
            self.c_key.blockSignals(False)

    def _meta(self, *_):
        self.mel.title = self.e_title.text().strip()
        meter = self.c_meter.currentText().strip()
        if re.fullmatch(r"\d{1,2}/(1|2|4|8|16)", meter):
            self.mel.meter = meter
        self.mel.pickup = self.c_pick.currentData() or 0
        self.mel.tempo = self.s_tempo.value()
        self.saved = False
        self.canvas.update()

    def _key_changed(self, *_):
        """Nowa tonacja: nuty zachowują stopnie zgodnie z nową tonacją (jak przepisanie znaków przy kluczu)."""
        old = self.mel.fifths
        new = self.c_key.currentData()
        for ev in self.mel.events:
            if not is_rest(ev) and ev['alt'] == key_alter(old, ev['step']):
                ev['alt'] = key_alter(new, ev['step'])
        self.mel.fifths = new
        self.saved = False
        self.canvas.update()
        self.canvas.setFocus()

    def play(self):
        if not self.mel.events:
            return
        try:
            from modul_nuty import MidiPlayerDialog
            dlg = MidiPlayerDialog(self.mel.midi(), self.mel.title or "Melodia", self)
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Edytor melodii", f"Nie udało się odtworzyć:\n{e}")
        self.canvas.setFocus()

    def _safe_name(self):
        return re.sub(r'[\\/:*?"<>|]+', "_", self.mel.title or "melodia").strip() or "melodia"

    def export_xml(self):
        path, _ = QFileDialog.getSaveFileName(self, "Eksport MusicXML", self._safe_name() + ".musicxml", "MusicXML (*.musicxml)")
        if path:
            with open(path, 'wb') as f:
                f.write(self.mel.musicxml())

    def export_midi(self):
        path, _ = QFileDialog.getSaveFileName(self, "Eksport MIDI", self._safe_name() + ".mid", "MIDI (*.mid)")
        if path:
            with open(path, 'wb') as f:
                f.write(self.mel.midi())

    def to_chords(self):
        text = self.mel.chordpro()
        if not text.strip():
            QMessageBox.information(self, "Edytor melodii", "Wpisz słowa (Ctrl+L) i akordy (Ctrl+K).")
            return
        self.on_chords(text)

    def save(self):
        if not self.mel.events:
            QMessageBox.information(self, "Edytor melodii", "Brak nut do zapisania.")
            return
        msg = self.on_save(self.mel)
        self.saved = True
        if msg:
            self.status.setText(msg)
        self.canvas.setFocus()

    def closeEvent(self, e):
        if not self.saved and self.mel.events and self.on_save:
            r = QMessageBox.question(self, "Edytor melodii", "Zapisać melodię w pieśni?",
                                     QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if r == QMessageBox.Cancel:
                e.ignore()
                return
            if r == QMessageBox.Save:
                self.save()
        super().closeEvent(e)
