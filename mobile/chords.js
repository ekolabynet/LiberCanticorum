// Liber Canticorum Mobile – akordy (ChordPro), transpozycja. Port z program/modul_akordy.py.
// GPL-3.0-or-later
'use strict';
(function (root) {
  const SIDE = '‖';
  const NOTES_PL = ['C', 'Cis', 'D', 'Dis', 'E', 'F', 'Fis', 'G', 'Gis', 'A', 'B', 'H'];
  const NOTES_PL_FLAT = ['C', 'Des', 'D', 'Es', 'E', 'F', 'Ges', 'G', 'As', 'A', 'B', 'H'];
  const NOTES_EN = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'Bb', 'B'];
  const NOTES_EN_FLAT = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B'];
  const BASE = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, H: 11, B: 10 };

  const RE_CHORD = /^(?<root>[A-Ha-h])(?<acc>is|es|s|#|b(?![a-z]))?(?<rest>(m(?!aj)|moll)?(maj|dim|aug|sus|add)?\d{0,2}[+\-]?(maj|sus|add)?\d{0,2}[+\-]?(\/\d{1,2})?)(\/(?<bass>[A-Ha-h](is|es|s|#|b)?))?$/;
  const RE_TOKEN = /^[(\[]*(.+?)[)\]]*[.,…]*$/;
  const RE_REPEAT = /^(\/?\s*x\s?\d+|\/x\d+|\d\s?x|\/|\(bis\)|bis|\.\.\.|…|–|-|\||\(|\))$/i;
  const isUpper = c => c === c.toUpperCase() && c !== c.toLowerCase();
  const isLower = c => c === c.toLowerCase() && c !== c.toUpperCase();
  const mod = (n, m) => ((n % m) + m) % m;

  function isChord(tok) {
    const m = RE_TOKEN.exec(tok.trim());
    return !!(m && RE_CHORD.test(m[1]));
  }

  function semi(root, acc, en) {
    let n = BASE[root.toUpperCase()];
    if (root.toUpperCase() === 'B') n = en ? 11 : 10;   // angielskie B = polskie H; polskie B = b
    if (acc === 'is' || acc === '#') n += 1;
    else if (acc === 'es' || acc === 's' || acc === 'b') n -= 1;
    return mod(n, 12);
  }

  function name(n, minor, flat, en) {
    const names = en ? (flat ? NOTES_EN_FLAT : NOTES_EN) : (flat ? NOTES_PL_FLAT : NOTES_PL);
    const s = names[mod(n, 12)];
    return minor && !en ? s.toLowerCase() : s;
  }

  function transposeChord(ch, k, flat) {
    const m = RE_CHORD.exec(ch);
    if (!m || mod(k, 12) === 0) return ch;
    const g = m.groups, root = g.root, acc = g.acc || '', rest = g.rest || '', bass = g.bass;
    const en = acc === '#' || acc === 'b' || (rest.slice(0, 1).includes('m') && isUpper(root));
    const minor = isLower(root);
    let out = name(semi(root, acc, en) + k, minor, flat || (en && acc === 'b'), en) + rest;
    if (bass) {
      const b = /([A-Ha-h])(is|es|s|#|b)?/.exec(bass);
      out += '/' + name(semi(b[1], b[2] || '', en) + k, isLower(b[1]), flat, en);
    }
    return out;
  }

  function transposeToken(tok, k, flat) {
    const m = /^([(\[]*)(.+?)([)\]]*[.,…]*)$/.exec(tok);
    if (!m || !RE_CHORD.test(m[2])) return tok;
    return m[1] + transposeChord(m[2], k, flat) + m[3];
  }

  function transposeText(text, k, flat) {
    return (text || '').split(/\r?\n/).map(line => {
      const i = line.indexOf(SIDE);
      let body = i < 0 ? line : line.slice(0, i);
      let side = i < 0 ? null : line.slice(i + 1);
      body = body.replace(/\[([^\]]+)\]/g, (_, c) =>
        '[' + c.split(/\s+/).filter(Boolean).map(t => transposeToken(t, k, flat)).join(' ') + ']');
      if (side !== null) side = side.split(' ').map(t => transposeToken(t, k, flat)).join(' ');
      return side === null ? body : body + SIDE + side;
    }).join('\n');
  }

  function stripChords(text) {
    return (text || '').split(/\r?\n/).map(l => l.split(SIDE)[0].replace(/\[[^\]]*\]/g, '').replace(/[ \t]+$/, '')).join('\n');
  }

  function hasChords(text) {
    return /\[[A-Ha-h][^\]]*\]/.test(text || '') || (text || '').includes(SIDE);
  }

  const GLUED = /[A-Ha-h](?:is|es|s(?!us)|#|b(?![a-z]))?(?:m(?!aj)|moll)?(?:maj7|maj|dim|aug|sus[24]?|add9|7\+|[2-9]|11|13|\+)*/y;

  function splitGlued(tok) {
    if (isChord(tok) || tok.length < 2) return [tok];
    const out = [];
    let i = 0;
    while (i < tok.length) {
      GLUED.lastIndex = i;
      const m = GLUED.exec(tok);
      if (!m || m.index + m[0].length === i) return [tok];
      out.push(m[0]);
      i += m[0].length;
    }
    return out.every(isChord) ? out : [tok];
  }

  // pierwszy akord pieśni – do wyświetlenia tonacji
  function firstChord(text) {
    const m = /\[([^\]\s]+)/.exec(text || '');
    if (m && RE_CHORD.test(m[1].replace(/^[(\[]+|[)\].,…]+$/g, ''))) return m[1].replace(/^[(\[]+|[)\].,…]+$/g, '');
    const i = (text || '').indexOf(SIDE);
    if (i >= 0) {
      const t = text.slice(i + 1).split(/\s+/).flatMap(splitGlued).find(isChord);
      if (t) return RE_TOKEN.exec(t)[1];
    }
    return '';
  }

  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  function sideHtml(side) {
    const toks = [];
    side.replace(/\//g, ' / ').split(/\s+/).filter(Boolean).forEach(t => toks.push(...splitGlued(t)));
    return toks.map(t => t === '/' ? '<span class="sl">/</span>' : esc(t)).join('<span class="gap"> </span>');
  }

  // HTML: akordy nad sylabami (segmenty inline-block), akordy boczne w prawej kolumnie
  function chordproHtml(text, opts) {
    opts = opts || {};
    if (opts.k) text = transposeText(text, opts.k, opts.flat);
    const rows = [];
    for (const line of (text || '').split(/\r?\n/)) {
      const i = line.indexOf(SIDE);
      const body = i < 0 ? line : line.slice(0, i);
      const side = i < 0 ? '' : line.slice(i + 1).trim();
      if (!body.trim() && !side) { rows.push('<div class="ln gap-line"></div>'); continue; }
      const parts = body.split(/(\[[^\]]*\])/);
      let inner;
      if (parts.length === 1 || opts.lyricsOnly) {
        inner = '<span class="tx">' + (esc(body.replace(/\[[^\]]*\]/g, '')) || '&nbsp;') + '</span>';
      } else {
        const segs = [];
        let pending = '';
        for (const p of parts) {
          if (p.startsWith('[') && p.endsWith(']')) {
            if (pending) segs.push([pending, '']);
            pending = p.slice(1, -1);
            continue;
          }
          if (p === '' && !pending) continue;
          segs.push([pending, p]);
          pending = '';
        }
        if (pending) segs.push([pending, '']);
        inner = segs.map(([c, t]) => '<span class="sg"><b class="c">' + (esc(c) || '&nbsp;') + '</b><span class="tx">' +
          (esc(t) || '&nbsp;') + '</span></span>').join('');
      }
      rows.push('<div class="ln"><div class="bd">' + inner + '</div>' +
        (side && !opts.lyricsOnly ? '<div class="sd c">' + sideHtml(side) + '</div>' : '') + '</div>');
    }
    return rows.join('');
  }

  const api = { SIDE, isChord, transposeChord, transposeToken, transposeText, stripChords, hasChords, splitGlued,
    firstChord, chordproHtml, esc };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Chords = api;
})(typeof self !== 'undefined' ? self : this);
