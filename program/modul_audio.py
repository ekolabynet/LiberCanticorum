# -*- coding: utf-8 -*-
"""Liber Canticorum – nagrania do nauki (MP3) z nut.

Z pliku MIDI (dołączonego albo przeliczonego z MuseScore) powstają:
  * „całość” – wszystkie głosy,
  * każdy głos osobno, na delikatnym podkładzie całej harmonii (organy albo chór, ciszej),
dla śpiewaków, którzy uczą się ze słuchu (także niewidomych).
Brzmienia z SoundFontu (modul_brzmienia); zapis MP3 przez soundfile (libsndfile ≥ 1.1), a gdy MP3
niedostępne – OGG albo WAV. Licencja: GPL-3.0-or-later.
"""
import os
import re

DEFAULT_OPTS = {'full': True, 'voices': True, 'bg': 0.22, 'voice_instr': 'sf:0:52', 'bg_instr': 'sf:0:19',
                'tempo': 1.0, 'format': 'mp3', 'split': True}


def _safe(name):
    name = re.sub(r'[\\/:*?"<>|]+', ' ', name or '').strip()
    return re.sub(r'\s+', ' ', name)[:80] or "utwór"


def audio_formats():
    """Dostępne formaty zapisu (MP3, jeśli libsndfile go obsługuje)."""
    try:
        import soundfile as sf
        av = sf.available_formats()
    except Exception:
        return ['wav']
    return [f for f in ('mp3', 'ogg', 'wav') if f.upper() in av]


def soundfont():
    import modul_brzmienia as B
    try:
        from PySide6.QtCore import QSettings
        custom = QSettings("LiberCanticorum", "LiberCanticorum").value("soundfont", "") or ""
    except Exception:
        custom = ""
    for p in B.find_soundfonts(custom):
        try:
            return B.load_soundfont(p)
        except Exception:
            continue
    return None


def _render(voice, instr, sf, sr, length, tempo, seed=0):
    import numpy as np
    import modul_brzmienia as B
    buf = np.zeros(length, np.float32)
    for k, (start, dur, pitch, vel) in enumerate(voice.notes):
        seg = B.render_note(instr, pitch, max(0.03, dur / tempo), vel, sf, sr, seed=seed * 1000 + k)
        a = int(start / tempo * sr)
        if a < length:
            buf[a:a + len(seg)] += seg[:length - a]
    return buf


def _write(path, buf, sr, fmt):
    import numpy as np
    nz = np.nonzero(np.abs(buf) > 1e-4)[0]
    buf = buf[:nz[-1] + int(0.5 * sr)] if len(nz) else buf[:sr]
    peak = float(np.abs(buf).max()) if len(buf) else 0
    if peak > 0:
        buf = buf * (0.89 / peak)                       # ok. −1 dB
    if fmt == 'wav':
        from modul_nuty import write_wav
        write_wav(path, buf, sr)
        return path
    import soundfile as sf
    sf.write(path, np.clip(buf, -1, 1), sr, format=fmt.upper())
    return path


ROLE_NAMES = {'S': "Sopran", 'A': "Alt", 'T': "Tenor", 'B': "Bas", 'X': "Głos"}
_ROLE_WORDS = [('S', ("sopran", "soprano", "women", "kobiety", "melodia")), ('A', ("alt", "alto")),
               ('T', ("tenor",)), ('B', ("bas", "bass", "men", "mężczyźni"))]


def voice_roles(voices):
    """Rola każdego głosu: S/A/T/B (z nazwy ścieżki albo z wysokości), X gdy nie da się ustalić."""
    roles = []
    n = len(voices)
    for i, v in enumerate(voices):
        low = v.name.lower()
        role = next((r for r, words in _ROLE_WORDS if any(w in low for w in words)), None)
        if role is None:
            role = "SATB"[round(i * 3 / (n - 1))] if 1 < n <= 4 else ('S' if n == 1 else 'X')
        roles.append(role)
    return roles


def count_files(n_voices_sel, variants, tempos):
    """Ile plików powstanie dla jednej pieśni."""
    per = (1 if 'full' in variants else 0) + n_voices_sel * ((1 if 'bg' in variants else 0) + (1 if 'solo' in variants else 0))
    return per * max(1, len(tempos))


def render_song(midi_bytes, out_dir, prefix, opts=None, progress=None):
    """→ lista zapisanych plików. prefix np. „03 Komunia – Pan jest pasterzem moim”.
    opts: voices_sel – role do zapisu ('S','A','T','B','X'); variants – 'full' (całość), 'bg' (głos z podkładem),
    'solo' (sam głos); tempos – np. [1.0] albo [1.0, 0.75]."""
    import numpy as np
    import modul_brzmienia as B
    import modul_nuty as N
    o = dict(DEFAULT_OPTS, **(opts or {}))
    variants = set(o.get('variants') or (['full'] if o.get('full') else []) + (['bg'] if o.get('voices') else []))
    sel = set(o.get('voices_sel') or "SATBX")
    tempos = o.get('tempos') or [o.get('tempo', 1.0)]
    fmt = o['format'] if o['format'] in audio_formats() else audio_formats()[0]
    sf = soundfont()
    sr = B.SR
    vinstr = o['voice_instr'] if sf is not None and sf.preset_name(*map(int, o['voice_instr'].split(':')[1:])) else \
        ('sf:0:52' if sf is not None else 'wb:proste')
    binstr = o['bg_instr'] if sf is not None and o['bg_instr'] and sf.preset_name(*map(int, o['bg_instr'].split(':')[1:])) \
        else vinstr
    raw, _ = N.load_midi(midi_bytes)
    voices = [v for v in N.prepare_voices(raw, split=o['split']) if v.notes]
    if not voices:
        raise RuntimeError("W pliku MIDI nie ma nut.")
    roles = voice_roles(voices)
    chosen = [i for i, r in enumerate(roles) if r in sel] if len(voices) > 1 else []
    rms = lambda x: float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0
    os.makedirs(out_dir, exist_ok=True)
    files = []
    steps = len(tempos) * len(voices) * (2 if binstr != vinstr else 1)
    done = 0
    for tempo in tempos:
        suffix = "" if abs(tempo - 1.0) < 0.01 else f" (wolniej {int(round(tempo * 100))}%)"
        length = int((max(n[0] + n[1] for v in voices for n in v.notes) / tempo + 3.0) * sr)
        parts, harm = [], np.zeros(length, np.float32)
        for i, v in enumerate(voices):
            parts.append(_render(v, vinstr, sf, sr, length, tempo, seed=i))
            done += 1
            if progress:
                progress(done, steps)
        if binstr != vinstr:                            # podkład: cała harmonia innym brzmieniem (organy)
            for i, v in enumerate(voices):
                harm += _render(v, binstr, sf, sr, length, tempo, seed=50 + i)
                done += 1
                if progress:
                    progress(done, steps)
        else:
            harm = sum(parts)
        full = sum(parts)
        ref = np.mean([rms(p) for p in parts]) or 1.0
        harm_n = harm * (ref / (rms(harm) or 1.0))
        if 'full' in variants or len(voices) == 1:
            mix = full + (harm_n * 0.35 if binstr != vinstr else 0)
            files.append(_write(os.path.join(out_dir, f"{_safe(prefix)} – całość{suffix}.{fmt}"), mix, sr, fmt))
        used = {}
        for i in chosen:
            role = roles[i]
            used[role] = used.get(role, 0) + 1
            name = ROLE_NAMES[role] + (f" {used[role]}" if roles.count(role) > 1 else "")
            if role == 'X':
                name = _safe(voices[i].name.split('  (')[0])
            if 'bg' in variants:
                files.append(_write(os.path.join(out_dir, f"{_safe(prefix)} – {name} z podkładem{suffix}.{fmt}"),
                                    parts[i] + harm_n * o['bg'], sr, fmt))
            if 'solo' in variants:
                files.append(_write(os.path.join(out_dir, f"{_safe(prefix)} – {name} sam{suffix}.{fmt}"),
                                    parts[i], sr, fmt))
    return files
