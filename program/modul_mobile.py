# Liber Canticorum – eksport biblioteki do aplikacji mobilnej (PWA, Android / iOS / przeglądarka)
# Copyright (C) 2026  Liber Canticorum contributors
# GPL-3.0-or-later
"""Plik *.lcm.json* (Liber Canticorum Mobile) – pieśni użytkownika, zapisane zestawy na Mszę
i (opcjonalnie) strony nut jako JPEG. Format opisany w mobile/FORMAT.md."""

import base64
import datetime
import json

FORMAT = "liber-canticorum-mobile"
FORMAT_VERSION = 1


def _jpeg_uri(data, mime="image/jpeg"):
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def song_entry(song, scores=None):
    import liber_canticorum as S
    ref = S.clean_refren_text(song.get('refren', ''))
    verses = S.process_verses(song.get('zwrotki_raw', ''), auto_punctuate=False, reflow=False)
    return {
        'id': song['id'], 'title': song.get('title', ''), 'cat': song.get('kategoria', ''),
        'src': song.get('spiewnik', ''), 'tags': song.get('tagi', ''), 'notes': song.get('uwagi', ''),
        'ref': [l.rstrip() for l in ref.splitlines() if l.strip()],
        'verses': [[l.rstrip() for l in v.split("\n")] for v in verses],
        'chords': song.get('akordy', '') or '',
        'youtube': [l.split("\t")[0] for l in (song.get('youtube') or '').splitlines() if l.strip()],
        'scores': scores or [],
    }


def score_pages(db, sid, score_ext=()):
    """[{name, pages:[data URI]}] – PDF/zdjęcia oraz PDF przeliczony z MuseScore."""
    import modul_nuty
    out = []
    for a in db.attachments(sid):
        name, low = a['name'], a['name'].lower()
        data = None
        if low.endswith('.pdf'):
            data = db.attachment(a['id'])['data']
        elif low.endswith(('.png', '.jpg', '.jpeg')):
            raw = db.attachment(a['id'])['data']
            out.append({'name': a['opis'] or name,
                        'pages': [_jpeg_uri(raw, "image/png" if low.endswith('.png') else "image/jpeg")]})
            continue
        elif score_ext and low.endswith(score_ext):
            d = db.get_derived(a['id'])
            data = d['pdf'] if d and d['pdf'] else None
        if data:
            pages = modul_nuty.pdf_pages_to_jpeg(data, width=1400, quality=72)
            if pages:
                out.append({'name': a['opis'] or name, 'pages': [_jpeg_uri(p) for p in pages]})
    return out


def set_entry(zid, name, date, dane, titles):
    meta = dane.get('meta') or {}
    notes = dane.get('uwagi') or {}
    parts = []
    for part, ids in (dane.get('czesci') or {}).items():
        nn = notes.get(part) or []
        parts.append({'part': part, 'items': [{'id': sid, 'title': titles.get(sid, '?'),
                                               'notes': (nn[i] if i < len(nn) else {}) or {}}
                                              for i, sid in enumerate(ids)]})
    return {'id': zid, 'name': name or date or '', 'date': date or meta.get('data', ''),
            'time': meta.get('godzina', ''), 'place': meta.get('miejsce', ''), 'okres': meta.get('okres', ''),
            'day': meta.get('dzien', ''), 'parts': parts}


def build_export(db, songs, sets, scores=False, score_ext=(), version="", progress=None):
    """songs – słowniki pieśni z bazy; sets – [(id, nazwa, data, dane)]. Zwraca tekst JSON."""
    out = []
    for n, s in enumerate(songs):
        if progress:
            progress(n, len(songs), s.get('title', ''))
        out.append(song_entry(s, score_pages(db, s['id'], score_ext) if scores else None))
    titles = {s['id']: s['title'] for s in out}
    for sid in {i for _, _, _, d in sets for ids in (d.get('czesci') or {}).values() for i in ids} - set(titles):
        g = db.get(sid)
        if g:                                           # pieśń z zestawu spoza wybranego zakresu – też trafia do pliku
            out.append(song_entry(g, score_pages(db, sid, score_ext) if scores else None))
            titles[sid] = g['title']
    data = {'format': FORMAT, 'version': FORMAT_VERSION, 'app': version,
            'made': datetime.datetime.now().isoformat(timespec='seconds'),
            'songs': out, 'sets': [set_entry(*z, titles) for z in sets]}
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
