# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Autorzy projektu Liber Canticorum
"""
Brzmienia dla odtwarzacza głosów (MIDI) – bez zewnętrznych programów.

1. SoundFont (.sf2, a z pakietem `soundfile` także .sf3 z MuseScore) – prawdziwe próbki:
   Choir Aahs, Voice Oohs, Church Organ, Reed Organ… Własny, prosty odtwarzacz formatu SF2:
   strefy klawiszy/dynamiki, strojenie, pętle próbek, obwiednia głośności. Bez filtrów i modulatorów.

SoundFont: znajdowany automatycznie (np. biblioteka brzmień MuseScore, FluidR3, GeneralUser GS)
albo wskazany w odtwarzaczu. Darmowy GeneralUser GS: https://schristiancollins.com/generaluser.php
"""
import glob
import io
import os
import struct

import numpy as np

SR = 32000

BUILTIN = [('wb:proste', 'Prosty ton (gdy brak SoundFontu)')]
GM_PRESETS = [                      # (bank, program, nazwa) – standard General MIDI
    (0, 52, 'Choir Aahs – chór „aa”'), (0, 53, 'Voice Oohs – chór „uu”'), (0, 19, 'Church Organ – organy kościelne'),
    (0, 20, 'Reed Organ – fisharmonia'), (0, 16, 'Drawbar Organ'), (0, 0, 'Fortepian'), (0, 48, 'Smyczki'),
    (0, 54, 'Synth Voice'), (0, 73, 'Flet'),
]
GENERALUSER_URL = "https://schristiancollins.com/generaluser.php"


# =====================================================================
# Prosty ton awaryjny (gdy na komputerze nie ma żadnego SoundFontu)
# =====================================================================

def render_builtin(kind, pitch, dur, vel, sr=SR, seed=0):
    f0 = 440.0 * 2 ** ((pitch - 69) / 12)
    release = 0.06
    n = int((dur + release) * sr)
    t = np.arange(n, dtype=np.float32) / sr
    w = sum(a * np.sin(2 * np.pi * f0 * k * t) for k, a in ((1, 1.0), (2, 0.35), (3, 0.12)) if f0 * k < sr / 2)
    env = np.minimum(1.0, t / 0.015) * np.where(t < dur, 1.0, np.maximum(0.0, 1 - (t - dur) / release))
    return (w * env * (vel / 127) * 0.8).astype(np.float32)


# =====================================================================
# SoundFont 2 (.sf2) i 3 (.sf3) – minimalny odtwarzacz
# =====================================================================

GEN_DEFAULTS = {33: -12000, 34: -12000, 35: -12000, 36: -12000, 37: 0, 38: -12000, 48: 0, 51: 0, 52: 0,
                54: 0, 56: 100, 58: -1, 0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 12: 0, 45: 0, 50: 0}
ADDITIVE = {33, 34, 35, 36, 37, 38, 48, 51, 52}          # generatory presetu dodawane do instrumentu
RANGE_GENS = {43, 44}


class SoundFont:
    def __init__(self, path):
        self.path = path
        with open(path, 'rb') as f:
            self.buf = f.read()
        b = self.buf
        if b[:4] != b'RIFF' or b[8:12] != b'sfbk':
            raise ValueError("To nie jest plik SoundFont (.sf2/.sf3).")
        self.name = os.path.basename(path)
        self.smpl_off = self.smpl_len = 0
        pd = {}
        for cid, off, size in self._chunks(12, len(b)):
            if cid == b'LIST':
                ltype = b[off:off + 4]
                for sid, soff, ssize in self._chunks(off + 4, off + size):
                    if ltype == b'sdta' and sid == b'smpl':
                        self.smpl_off, self.smpl_len = soff, ssize
                    elif ltype == b'pdta':
                        pd[sid.decode('latin-1')] = (soff, ssize)
                    elif ltype == b'INFO' and sid == b'INAM':
                        self.name = b[soff:soff + ssize].split(b'\0')[0].decode('latin-1', 'replace') or self.name
        self.phdr = [struct.unpack_from('<20sHHHIII', b, pd['phdr'][0] + i * 38) for i in range(pd['phdr'][1] // 38)]
        self.pbag = [struct.unpack_from('<HH', b, pd['pbag'][0] + i * 4) for i in range(pd['pbag'][1] // 4)]
        self.pgen = [struct.unpack_from('<HH', b, pd['pgen'][0] + i * 4) for i in range(pd['pgen'][1] // 4)]
        self.inst = [struct.unpack_from('<20sH', b, pd['inst'][0] + i * 22) for i in range(pd['inst'][1] // 22)]
        self.ibag = [struct.unpack_from('<HH', b, pd['ibag'][0] + i * 4) for i in range(pd['ibag'][1] // 4)]
        self.igen = [struct.unpack_from('<HH', b, pd['igen'][0] + i * 4) for i in range(pd['igen'][1] // 4)]
        self.shdr = [struct.unpack_from('<20sIIIIIBbHH', b, pd['shdr'][0] + i * 46) for i in range(pd['shdr'][1] // 46)]
        self.presets = {}
        for i in range(len(self.phdr) - 1):                  # ostatni rekord to terminator EOP
            name, prog, bank, bag0 = self.phdr[i][:4]
            self.presets[(bank, prog)] = (i, name.split(b'\0')[0].decode('latin-1', 'replace'))
        self._samples = {}
        self._regions = {}
        self._onsets = {}
        self._tunes = {}
        self.tight = True                                   # wyrównuj wolne początki próbek
        self.retune = True                                  # dostrój próbki dokładnie do wysokości nominalnej

    def detune(self, sid, root=None):
        """Odchyłka stroju próbki w centach (zmierzona w pętli); 0 gdy nie da się zmierzyć pewnie."""
        if (sid, root) in self._tunes:
            return self._tunes[(sid, root)]
        data, rate, orig, corr, ls, le = self.sample(sid)
        if root is not None:
            orig = root
        dev = 0.0
        try:
            f_exp = 440.0 * 2 ** ((orig - 69) / 12) / 2 ** (corr / 1200)      # częstotliwość nagrania przed korektą
            if 0 < ls < le <= len(data) and le - ls > rate * 0.1 and 30 < f_exp < 2500:   # tylko dźwięki trwające (pętla)
                devs = []
                half = (le - ls) // 2
                for a in (ls, ls + half):
                    x = data[a:a + min(half, int(0.3 * rate))].astype(np.float64)
                    x = x - x.mean()
                    n = len(x)
                    spec = np.fft.rfft(x, 2 * n)
                    c = np.fft.irfft(spec * np.conj(spec))[:n]
                    c /= (c[0] or 1)
                    lag0 = rate / f_exp
                    lo, hi = int(lag0 * 0.97), int(lag0 * 1.03) + 2      # tylko w pobliżu oczekiwanej wysokości
                    if not (hi + 1 < n and lo > 2):
                        break
                    k = lo + int(np.argmax(c[lo:hi]))
                    if c[k] < 0.85 or k in (lo, hi - 1):
                        break
                    y0, y1, y2 = c[k - 1], c[k], c[k + 1]
                    d = 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2) if (y0 - 2 * y1 + y2) else 0
                    devs.append(1200 * np.log2((rate / (k + d)) / f_exp))
                if len(devs) == 2 and abs(devs[0] - devs[1]) < 4 and abs(sum(devs) / 2) <= 35:
                    dev = sum(devs) / 2
        except Exception:
            dev = 0.0
        self._tunes[(sid, root)] = float(dev)
        return float(dev)

    def onset(self, sid):
        """Indeks próbki, od którego dźwięk ma już ~30% głośności (najwyżej 0,35 s, przed pętlą)."""
        if sid in self._onsets:
            return self._onsets[sid]
        data, rate, orig, corr, ls, le = self.sample(sid)
        lim = int(0.4 * rate)
        w = max(1, int(0.01 * rate))
        if len(data) < 4 * w:
            self._onsets[sid] = 0
            return 0
        env = np.convolve(np.abs(data[:int(1.2 * rate)]), np.ones(w) / w, 'same')
        # poziom „ustalony”: średnia z pętli (albo z 0,4–1,0 s) – do niego mierzymy narastanie
        a, b = (ls, min(le, ls + int(0.5 * rate))) if 0 < ls < le and ls < len(env) else (int(0.4 * rate), len(env))
        steady = float(np.abs(data[a:b]).mean() * 1.4) if b > a else float(env.max())
        off = 0
        if steady > 0:
            k = int(np.argmax(env >= 0.5 * steady)) if (env >= 0.5 * steady).any() else 0
            off = max(0, min(k - w, lim))
            if 0 < ls <= off:
                off = max(0, ls - w)
            if off < int(0.02 * rate):                     # szybki atak – zostaw jak jest
                off = 0
        self._onsets[sid] = off
        return off

    def _chunks(self, off, end):
        b = self.buf
        known = {b'LIST', b'ifil', b'isng', b'INAM', b'irom', b'iver', b'ICRD', b'IENG', b'IPRD', b'ICOP', b'ICMT',
                 b'ISFT', b'smpl', b'sm24', b'phdr', b'pbag', b'pmod', b'pgen', b'inst', b'ibag', b'imod', b'igen', b'shdr'}
        ok = lambda o: o + 8 <= len(b) and b[o:o + 4] in known
        while off + 8 <= end:
            cid = b[off:off + 4]
            size = struct.unpack_from('<I', b, off + 4)[0]
            yield cid, off + 8, size
            nxt = off + 8 + size
            # RIFF wymaga wyrównania do 2 bajtów, ale niektóre pliki (np. .sf3 z MuseScore) go nie mają
            if size & 1 and not (ok(nxt) and not ok(nxt + 1)):
                nxt += 1
            off = nxt

    @staticmethod
    def _zone_gens(bags, gens, i0, i1):
        """Lista stref: słownik generatorów (zakresy jako (lo, hi), reszta jako liczba ze znakiem)."""
        zones = []
        for j in range(i0, i1):
            g0, g1 = bags[j][0], bags[j + 1][0]
            z = {}
            for oper, amt in gens[g0:g1]:
                if oper in RANGE_GENS:
                    z[oper] = (amt & 0xFF, amt >> 8)
                elif oper in (41, 53):
                    z[oper] = amt
                else:
                    z[oper] = amt - 65536 if amt >= 32768 else amt
            zones.append(z)
        return zones

    def preset_name(self, bank, prog):
        p = self.presets.get((bank, prog)) or self.presets.get((0, prog))
        return p[1] if p else None

    def regions(self, bank, prog, key, vel):
        ck = (bank, prog, key, vel // 16)
        if ck in self._regions:
            return self._regions[ck]
        p = self.presets.get((bank, prog)) or self.presets.get((0, prog))
        out = []
        if p:
            pi = p[0]
            pzones = self._zone_gens(self.pbag, self.pgen, self.phdr[pi][3], self.phdr[pi + 1][3])
            pglob = pzones[0] if pzones and 41 not in pzones[0] else {}
            for pz in pzones:
                if 41 not in pz or not self._in(pz, pglob, key, vel):
                    continue
                ii = pz[41]
                izones = self._zone_gens(self.ibag, self.igen, self.inst[ii][1], self.inst[ii + 1][1])
                iglob = izones[0] if izones and 53 not in izones[0] else {}
                for iz in izones:
                    if 53 not in iz or not self._in(iz, iglob, key, vel):
                        continue
                    g = dict(GEN_DEFAULTS)
                    g.update({k: v for k, v in iglob.items() if k not in RANGE_GENS})
                    g.update({k: v for k, v in iz.items() if k not in RANGE_GENS})
                    for src in (pglob, pz):
                        for k, v in src.items():
                            if k in ADDITIVE:
                                g[k] = g.get(k, 0) + v
                    out.append(g)
        self._regions[ck] = out
        return out

    @staticmethod
    def _in(z, glob, key, vel):
        kr = z.get(43, glob.get(43, (0, 127)))
        vr = z.get(44, glob.get(44, (0, 127)))
        return kr[0] <= key <= kr[1] and vr[0] <= vel <= vr[1]

    def sample(self, sid):
        """(dane float32, częstotliwość próbkowania, oryginalna wysokość, korekta, początek pętli, koniec pętli)."""
        if sid in self._samples:
            return self._samples[sid]
        name, start, end, ls, le, rate, orig, corr, link, stype = self.shdr[sid]
        if stype & 0x10:                                    # SF3: próbka skompresowana (Ogg Vorbis)
            try:
                import soundfile
            except ImportError:
                raise RuntimeError("Plik .sf3 wymaga pakietu soundfile (pip install soundfile) – albo użyj pliku .sf2.")
            raw = self.buf[self.smpl_off + start:self.smpl_off + end]
            data, rate2 = soundfile.read(io.BytesIO(raw), dtype='float32')
            if data.ndim > 1:
                data = data.mean(axis=1)
            res = (data, rate2 or rate, orig, corr, ls, le)      # pętla względem początku próbki
        else:
            a = np.frombuffer(self.buf, dtype='<i2', count=end - start, offset=self.smpl_off + 2 * start)
            res = (a.astype(np.float32) / 32768.0, rate, orig, corr, ls - start, le - start)
        self._samples[sid] = res
        return res

    def render(self, bank, prog, pitch, dur, vel, sr=SR):
        regs = self.regions(bank, prog, int(pitch), int(vel))
        if not regs:
            return None
        outs = []
        for g in regs:
            data, rate, orig, corr, ls, le = self.sample(g[53])
            if len(data) < 4:
                continue
            root = g[58] if g[58] >= 0 else orig
            cents = (pitch - root) * g[56] + g[51] * 100 + g[52] + corr
            if self.retune:
                cents -= self.detune(g[53], root)
            ratio = 2 ** (cents / 1200) * rate / sr
            tc = lambda v: 2 ** (max(v, -12000) / 1200)
            delay, attack, hold, decay, release = tc(g[33]), tc(g[34]), tc(g[35]), tc(g[36]), min(tc(g[38]), 3.0)
            sus_db = max(0, min(g[37], 1440)) / 10
            n = int((dur + release) * sr)
            # wolny początek próbki (np. chór „aa” – do 0,3 s ciszy i narastania) przesuwa nutę w czasie:
            # zaczynamy od miejsca, gdzie dźwięk już brzmi, żeby wszystkie nuty wchodziły równo z rytmem
            off = self.onset(g[53]) if self.tight else 0
            pos = off + np.arange(n, dtype=np.float64) * ratio
            looping = g[54] in (1, 3) and 0 <= ls < le <= len(data)
            if looping:
                L = le - ls
                pos = np.where(pos < le, pos, ls + np.mod(pos - ls, L))
            else:
                n = min(n, int((len(data) - 2) / ratio))
                pos = pos[:n]
                if n <= 0:
                    continue
            i = pos.astype(np.int64)
            frac = (pos - i).astype(np.float32)
            nxt = np.where(looping & (i + 1 >= le), ls, i + 1) if looping else np.minimum(i + 1, len(data) - 1)
            w = data[i] * (1 - frac) + data[nxt] * frac
            # obwiednia głośności (w dB): opóźnienie, atak, utrzymanie, wybrzmienie do poziomu podtrzymania, zwolnienie
            t = np.arange(n, dtype=np.float32) / sr
            att = np.clip((t - delay) / max(attack, 1e-3), 0, 1)
            t_dec = np.clip(t - delay - attack - hold, 0, None)
            db = -np.minimum(sus_db, 100 * t_dec / max(decay, 1e-3))
            db_off = float(np.interp(dur, t, db)) if n else 0.0
            rel = np.where(t > dur, (t - dur) * 100 / max(release, 1e-3), 0)
            db = np.where(t > dur, db_off - rel, db)
            env = att * (10 ** (db / 20))
            if off:
                k = min(n, int(0.006 * sr))                 # krótkie wejście bez trzasku
                env[:k] *= np.linspace(0, 1, k, dtype=np.float32)
            gain = 10 ** (-(g[48] * 0.4) / 200) * (vel / 127) ** 2
            outs.append((w * env * gain).astype(np.float32))
        if not outs:
            return None
        n = max(len(o) for o in outs)
        mix = np.zeros(n, np.float32)
        for o in outs:
            mix[:len(o)] += o
        return mix


_SF_CACHE = {}


def load_soundfont(path):
    if path not in _SF_CACHE:
        _SF_CACHE.clear()                                    # trzymamy w pamięci jeden plik
        _SF_CACHE[path] = SoundFont(path)
    return _SF_CACHE[path]


def find_soundfonts(custom=""):
    """Pliki SoundFont na komputerze (najpierw wskazany, potem typowe miejsca, w tym MuseScore)."""
    home = os.path.expanduser("~")
    pats = []
    for root in (home, os.path.join(home, "Documents"), os.path.join(home, "Dokumenty")):
        pats += [os.path.join(root, "MuseScore*", "SoundFonts", "*.sf[23]"), os.path.join(root, "SoundFonts", "*.sf[23]")]
    pats += [os.path.join(home, ".local", "share", "soundfonts", "*.sf[23]"), os.path.join(home, ".fluidsynth", "*.sf[23]"),
             "/usr/share/sounds/sf2/*.sf2", "/usr/share/soundfonts/*.sf[23]", "/usr/share/sounds/sf3/*.sf3",
             "/usr/share/mscore*/sound/*.sf[23]", "/usr/share/musescore*/sound/*.sf[23]", "/usr/local/share/soundfonts/*.sf[23]",
             "/Applications/MuseScore*.app/Contents/Resources/sound/*.sf[23]", "/Library/Audio/Sounds/Banks/*.sf[23]",
             os.path.join(os.path.dirname(os.path.abspath(__file__)), "*.sf[23]")]
    for pf in (os.environ.get('ProgramFiles'), os.environ.get('ProgramFiles(x86)')):
        if pf:
            pats += [os.path.join(pf, "MuseScore*", "sound", "*.sf[23]"), os.path.join(pf, "MuseScore*", "share", "sound", "*.sf[23]")]
    pats.append("C:/soundfonts/*.sf[23]")
    found = []
    if custom and os.path.isfile(custom):
        found.append(custom)
    import importlib.util
    sf3_ok = importlib.util.find_spec("soundfile") is not None
    for pat in pats:
        for p in glob.glob(pat):
            rp = os.path.realpath(p)                         # dowiązania (default-GM.sf2 itp.) -> prawdziwy plik
            if (rp.lower().endswith('.sf2') or sf3_ok) and os.path.isfile(rp) and rp not in [os.path.realpath(x) for x in found]:
                found.append(rp)

    def score(p):           # wolimy duże, „ogólne” banki z chórem i organami
        n = os.path.basename(p).lower()
        pref = 0 if 'generaluser' in n else 1 if 'musescore_general' in n or 'ms basic' in n else 2 if 'fluidr3' in n else 3
        return (0 if p == custom else 1, pref, -os.path.getsize(p))

    return sorted(found, key=score)


# =====================================================================
# Wspólne wejście: wyrenderuj nutę danym brzmieniem
# =====================================================================

def render_note(instr, pitch, dur, vel, sf=None, sr=SR, seed=0):
    """instr: 'sf:bank:program' (SoundFont) albo 'wb:proste' – prosty ton, gdy brak SoundFontu."""
    if instr.startswith('sf:') and sf is not None:
        _, bank, prog = instr.split(':')
        out = sf.render(int(bank), int(prog), pitch, dur, vel, sr)
        if out is not None:
            return out
    return render_builtin('proste', pitch, dur, vel, sr, seed)


def is_organ(instr):
    return instr in ('sf:0:19', 'sf:0:20', 'sf:0:16')
