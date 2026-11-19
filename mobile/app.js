// Liber Canticorum Mobile – wolny śpiewnik liturgiczny (PWA)
// Copyright (C) 2026  Liber Canticorum contributors – GPL-3.0-or-later
// Dane (pieśni, zestawy, nuty) wpisuje użytkownik w programie na komputerze i przenosi plikiem *.lcm.json.
'use strict';
const APP_VERSION = '0.29.0';
const FORMAT = 'liber-canticorum-mobile';
const $ = id => document.getElementById(id);
const esc = Chords.esc;

// ---------------------------------------------------------------- ustawienia (localStorage – tylko wygoda)
const PREF_KEY = 'lc-prefs';
let P = { fs: 20, theme: 'dark', lang: '', mode: 'chords', flat: false, tr: {}, repeatRef: false, cat: '', src: '' };
try { Object.assign(P, JSON.parse(localStorage.getItem(PREF_KEY) || '{}')); } catch (e) { }
function savePrefs() { try { localStorage.setItem(PREF_KEY, JSON.stringify(P)); } catch (e) { } }

// ---------------------------------------------------------------- język (PL / EN)
const EN = {
  'Pieśni': 'Songs', 'Zestawy': 'Sets', 'Ustawienia': 'Settings', 'Szukaj…': 'Search…',
  'Wszystkie kategorie': 'All categories', 'Wszystkie źródła': 'All sources', 'pieśni': 'songs',
  'Tekst': 'Lyrics', 'Akordy': 'Chords', 'Nuty': 'Scores', 'Ref.': 'Ref.',
  'Twój śpiewnik jest pusty': 'Your songbook is empty',
  'Aplikacja nie zawiera żadnych pieśni – wpisujesz je sam w programie Liber Canticorum na komputerze, a tu przenosisz plikiem.':
    'The app ships with no songs – you enter them yourself in Liber Canticorum on your computer and bring them here as a file.',
  'Na komputerze: Plik → 📱 Eksport do aplikacji mobilnej (albo w pilocie: ⇩ Offline → Biblioteka do aplikacji).':
    'On your computer: File → 📱 Export to the mobile app (or in the remote: ⇩ Offline → Library for the app).',
  '📥 Importuj plik': '📥 Import file', 'Brak wyników': 'No results',
  'Brak zestawów – ułóż zestaw na Mszę w programie na komputerze i wyeksportuj go.':
    'No sets yet – arrange a Mass set in the desktop program and export it.',
  'Transpozycja': 'Transpose', 'Tonacja': 'Key', 'Wykonawca': 'Performer', 'Uwagi': 'Notes',
  'Na co zwrócić uwagę': 'Watch out for', 'Poprzednia': 'Previous', 'Następna': 'Next',
  'Import': 'Import', 'Biblioteka zawiera już pieśni. Co zrobić z nowym plikiem?':
    'The library already has songs. What should be done with the new file?',
  'Dołącz / zaktualizuj': 'Add / update', 'Zastąp wszystko': 'Replace everything', 'Anuluj': 'Cancel',
  'To nie jest plik Liber Canticorum (.lcm.json).': 'This is not a Liber Canticorum file (.lcm.json).',
  'Zaimportowano': 'Imported', 'zestawów': 'sets', 'stron nut': 'score pages',
  'Wygląd': 'Appearance', 'Ciemny motyw': 'Dark theme', 'Wielkość tekstu': 'Text size', 'Język': 'Language',
  'Bemole w transpozycji (Es, As zamiast Dis, Gis)': 'Flats when transposing (Eb, Ab instead of D#, G#)',
  'Refren po każdej zwrotce': 'Refrain after every verse', 'Dane': 'Data',
  'Usuń wszystkie dane z telefonu': 'Delete all data from this phone',
  'Usunąć wszystkie pieśni, zestawy i nuty z tej aplikacji?': 'Delete all songs, sets and scores from this app?',
  'Usunięto.': 'Deleted.', 'O aplikacji': 'About',
  'wolny śpiewnik liturgiczny dla muzyków, chórów i wspólnot Kościoła': 'a free liturgical songbook for musicians, choirs and Church communities',
  'Zajęte miejsce': 'Storage used', 'Zainstaluj aplikację': 'Install the app',
  'Ostatni import': 'Last import', 'Brak nut dla tej pieśni.': 'No scores for this song.',
  'strona': 'page', 'str.': 'p.', 'Nagrania': 'Recordings', 'Pieśń nie istnieje (może usunięta przy imporcie).': 'Song not found (maybe removed by an import).',
  'Zestaw': 'Set', 'Ekran nie wygaśnie, gdy pieśń jest otwarta.': 'The screen stays on while a song is open.',
  'Pliki zostają tylko na tym urządzeniu – aplikacja niczego nie wysyła.': 'Files stay on this device only – the app sends nothing anywhere.',
  'Kod źródłowy i program na komputer': 'Source code and the desktop program',
  'Wszystkie': 'All', 'bez źródła': 'no source', 'bez kategorii': 'no category'
};
const LANG = P.lang || ((navigator.language || 'pl').toLowerCase().startsWith('pl') ? 'pl' : 'en');
const t = s => (LANG === 'pl' ? s : (EN[s] || s));
document.documentElement.lang = LANG;

// ---------------------------------------------------------------- IndexedDB
let DB;
function idb() {
  return new Promise((ok, err) => {
    const r = indexedDB.open('liber-canticorum', 1);
    r.onupgradeneeded = () => {
      const d = r.result;
      d.createObjectStore('songs', { keyPath: 'id' });
      d.createObjectStore('sets', { keyPath: 'id' });
      d.createObjectStore('pages');
      d.createObjectStore('meta');
    };
    r.onsuccess = () => ok(r.result);
    r.onerror = () => err(r.error);
  });
}
function tx(stores, mode, fn) {
  return new Promise((ok, err) => {
    const x = DB.transaction(stores, mode);
    const res = fn(x);
    x.oncomplete = () => ok(res);
    x.onerror = () => err(x.error);
    x.onabort = () => err(x.error);
  });
}
function getAll(store) {
  return new Promise((ok, err) => {
    const r = DB.transaction(store).objectStore(store).getAll();
    r.onsuccess = () => ok(r.result); r.onerror = () => err(r.error);
  });
}
function getOne(store, key) {
  return new Promise((ok, err) => {
    const r = DB.transaction(store).objectStore(store).get(key);
    r.onsuccess = () => ok(r.result); r.onerror = () => err(r.error);
  });
}

let SONGS = [], SETS = [], BYID = new Map();
async function loadAll() {
  SONGS = await getAll('songs');
  SETS = await getAll('sets');
  BYID = new Map(SONGS.map(s => [s.id, s]));
  SONGS.forEach(s => { s._f = fold([s.title, ...(s.ref || []), ...(s.verses || []).flat(), s.tags, s.src, s.cat].join(' ')); s._t = fold(s.title); });
  SONGS.sort((a, b) => a.title.localeCompare(b.title, LANG));
  SETS.sort((a, b) => (b.date || '').localeCompare(a.date || '') || b.id - a.id);
}
const fold = s => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/ł/g, 'l').replace(/Ł/g, 'l').toLowerCase();

// ---------------------------------------------------------------- import pliku z komputera
async function dataUriToBlob(uri) { return (await fetch(uri)).blob(); }

async function importText(text) {
  let data;
  try { data = JSON.parse(text); } catch (e) { data = null; }
  if (!data || data.format !== FORMAT || !Array.isArray(data.songs)) { alert(t('To nie jest plik Liber Canticorum (.lcm.json).')); return; }
  let mode = 'merge';
  if (SONGS.length) {
    mode = await ask(t('Import'), t('Biblioteka zawiera już pieśni. Co zrobić z nowym plikiem?'),
      [['merge', t('Dołącz / zaktualizuj'), 'go'], ['replace', t('Zastąp wszystko')], [null, t('Anuluj')]]);
    if (!mode) return;
  }
  busy(true);
  try {
    const pages = [];
    for (const s of data.songs) {
      s.scores = await Promise.all((s.scores || []).map(async (sc, si) => {
        for (let pi = 0; pi < sc.pages.length; pi++) pages.push([`${s.id}/${si}/${pi}`, await dataUriToBlob(sc.pages[pi])]);
        return { name: sc.name, n: sc.pages.length };
      }));
    }
    await tx(['songs', 'sets', 'pages', 'meta'], 'readwrite', x => {
      if (mode === 'replace') ['songs', 'sets', 'pages'].forEach(n => x.objectStore(n).clear());
      const ps = x.objectStore('pages');
      if (mode === 'merge') {                      // nuty importowanych pieśni zastępowane w całości
        for (const s of data.songs) ps.delete(IDBKeyRange.bound(`${s.id}/`, `${s.id}/￿`));
      }
      data.songs.forEach(s => x.objectStore('songs').put(s));
      (data.sets || []).forEach(z => x.objectStore('sets').put(z));
      pages.forEach(([k, b]) => ps.put(b, k));
      x.objectStore('meta').put({ made: data.made, app: data.app, at: new Date().toISOString() }, 'last');
    });
    try { if (navigator.storage && navigator.storage.persist) await navigator.storage.persist(); } catch (e) { }
    await loadAll();
    toast(`${t('Zaimportowano')} – ${t('Pieśni')}: ${data.songs.length}, ${t('Zestawy')}: ${(data.sets || []).length}, ${t('Nuty')}: ${pages.length} ${t('str.')}`);
    location.hash = '#/';
    route();
  } catch (e) {
    alert('Import: ' + e);
  } finally { busy(false); }
}
function pickFile() { $('file').value = ''; $('file').click(); }
$('file').onchange = async () => { const f = $('file').files[0]; if (f) importText(await f.text()); };
if ('launchQueue' in window) {                    // otwarcie pliku .lcm.json z menedżera plików (file_handlers)
  window.launchQueue.setConsumer(async p => { for (const h of p.files || []) importText(await (await h.getFile()).text()); });
}

// ---------------------------------------------------------------- drobne elementy interfejsu
function ask(title, text, buttons) {
  return new Promise(ok => {
    $('mBox').innerHTML = `<h3>${esc(title)}</h3><p>${esc(text)}</p>` +
      buttons.map((b, i) => `<button class="btn wide ${b[2] || ''}" data-i="${i}">${esc(b[1])}</button>`).join('');
    $('modal').hidden = false;
    $('mBox').querySelectorAll('button').forEach(el => el.onclick = () => { $('modal').hidden = true; ok(buttons[+el.dataset.i][0]); });
  });
}
let toastTimer;
function toast(msg) {
  let el = $('toast');
  if (!el) { el = document.createElement('div'); el.id = 'toast'; document.body.appendChild(el);
    el.style.cssText = 'position:fixed;left:50%;transform:translateX(-50%);bottom:84px;background:var(--card);border:1px solid var(--line);padding:10px 14px;border-radius:12px;z-index:40;max-width:90vw;text-align:center'; }
  el.textContent = msg; el.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.hidden = true, 4000);
}
function busy(on) { document.body.style.cursor = on ? 'progress' : ''; document.body.style.opacity = on ? '.6' : ''; }
function applyLook() {
  document.documentElement.classList.toggle('light', P.theme === 'light');
  document.documentElement.style.setProperty('--fs', P.fs + 'px');
  document.querySelector('meta[name=theme-color]').content = P.theme === 'light' ? '#fbf8f1' : '#1b1d22';
}
function header(title, back, tools) {
  $('h1').textContent = title;
  $('back').hidden = !back;
  $('logo').hidden = !!back;
  $('back').onclick = () => { if (history.length > 1) history.back(); else location.hash = back; };
  $('tools').innerHTML = tools || '';
}
function navOn(v) { document.querySelectorAll('#nav a').forEach(a => a.classList.toggle('on', a.dataset.v === v)); }

// ---------------------------------------------------------------- blokada wygaszania ekranu
let wake = null;
async function keepAwake(on) {
  try {
    if (on && !wake && 'wakeLock' in navigator) { wake = await navigator.wakeLock.request('screen'); wake.onrelease = () => wake = null; }
    if (!on && wake) { await wake.release(); wake = null; }
  } catch (e) { wake = null; }
}
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && location.hash.startsWith('#/song/')) keepAwake(true); });

// ---------------------------------------------------------------- widok: lista pieśni
let Q = '';
function viewSongs() {
  navOn('songs'); header('Liber Canticorum', null, `<button class="ib" id="imp" title="${esc(t('📥 Importuj plik'))}">📥</button>`);
  $('imp').onclick = pickFile;
  const main = $('main');
  if (!SONGS.length) {
    main.innerHTML = `<div class="empty"><img src="icons/icon-192.png" alt=""><h2>${esc(t('Twój śpiewnik jest pusty'))}</h2>
      <p>${esc(t('Aplikacja nie zawiera żadnych pieśni – wpisujesz je sam w programie Liber Canticorum na komputerze, a tu przenosisz plikiem.'))}</p>
      <p class="small">${esc(t('Na komputerze: Plik → 📱 Eksport do aplikacji mobilnej (albo w pilocie: ⇩ Offline → Biblioteka do aplikacji).'))}</p>
      <button class="btn go" id="imp2">${esc(t('📥 Importuj plik'))}</button>${installBtn()}</div>`;
    $('imp2').onclick = pickFile; bindInstall();
    return;
  }
  const cats = [...new Set(SONGS.map(s => s.cat || ''))].sort((a, b) => a.localeCompare(b, LANG));
  const srcs = [...new Set(SONGS.flatMap(s => (s.src || '').split(';').map(x => x.trim())))].sort((a, b) => a.localeCompare(b, LANG));
  const opt = (v, lab, cur) => `<option value="${esc(v)}" ${v === cur ? 'selected' : ''}>${esc(lab)}</option>`;
  main.innerHTML = `<div class="search"><input type="search" id="q" placeholder="${esc(t('Szukaj…'))}" value="${esc(Q)}" autocomplete="off"></div>
    <div class="filters"><select id="fc">${opt('', t('Wszystkie kategorie'), P.cat)}${cats.map(c => opt(c || '∅', c || '(' + t('bez kategorii') + ')', P.cat)).join('')}</select>
    <select id="fs">${opt('', t('Wszystkie źródła'), P.src)}${srcs.map(c => opt(c || '∅', c || '(' + t('bez źródła') + ')', P.src)).join('')}</select></div>
    <div class="count" id="cnt"></div><ul class="list" id="ul"></ul>`;
  const draw = () => {
    const q = fold(Q).trim().split(/\s+/).filter(Boolean);
    let L = SONGS.filter(s => q.every(w => s._f.includes(w)));
    if (P.cat) L = L.filter(s => (s.cat || '∅') === P.cat);
    if (P.src) L = L.filter(s => (s.src || '').split(';').map(x => x.trim() || '∅').includes(P.src));
    if (q.length) L.sort((a, b) => (b._t.includes(q.join(' ')) - a._t.includes(q.join(' '))) || a.title.localeCompare(b.title, LANG));
    $('cnt').textContent = `${L.length} ${t('pieśni')}`;
    $('ul').innerHTML = L.length ? L.slice(0, 600).map(s => `<li><a href="#/song/${s.id}">${esc(s.title)}${s.chords ? ' <span class="c" style="color:var(--ch)">♯</span>' : ''}${(s.scores || []).length ? ' 🎼' : ''}
      <small>${esc([s.cat, s.src].filter(Boolean).join(' · ') || firstLine(s))}</small></a></li>`).join('') : `<li class="empty">${esc(t('Brak wyników'))}</li>`;
  };
  $('q').oninput = e => { Q = e.target.value; draw(); };
  $('fc').onchange = e => { P.cat = e.target.value; savePrefs(); draw(); };
  $('fs').onchange = e => { P.src = e.target.value; savePrefs(); draw(); };
  draw();
}
const firstLine = s => ((s.verses && s.verses[0] && s.verses[0][0]) || (s.ref && s.ref[0]) || '');

// ---------------------------------------------------------------- widok: pieśń
function flatSet(z) {
  const out = [];
  (z.parts || []).forEach(p => p.items.forEach(it => out.push({ part: p.part, ...it })));
  return out;
}
async function viewSong(id, ctx) {
  navOn(ctx.set != null ? 'sets' : 'songs');
  const s = BYID.get(id);
  if (!s) { header('', '#/'); $('main').innerHTML = `<p class="empty">${esc(t('Pieśń nie istnieje (może usunięta przy imporcie).'))}</p>`; return; }
  keepAwake(true);
  const z = ctx.set != null ? SETS.find(x => x.id === ctx.set) : null;
  const list = z ? flatSet(z) : null;
  const idx = list ? Math.min(Math.max(0, ctx.i || 0), list.length - 1) : -1;
  const entry = list ? list[idx] : null;
  const hasCh = Chords.hasChords(s.chords);
  const hasSc = (s.scores || []).length > 0;
  let mode = P.mode;
  if (mode === 'chords' && !hasCh) mode = 'text';
  if (mode === 'scores' && !hasSc) mode = hasCh ? 'chords' : 'text';
  const k = P.tr[id] || 0;
  header(s.title, z ? `#/set/${z.id}` : '#/', `<button class="ib" id="am">A−</button><button class="ib" id="ap">A+</button>`);
  $('am').onclick = () => { P.fs = Math.max(12, P.fs - 2); savePrefs(); applyLook(); };
  $('ap').onclick = () => { P.fs = Math.min(48, P.fs + 2); savePrefs(); applyLook(); };
  const tab = (m, lab, on) => on ? `<button class="btn ${m === mode ? 'go' : ''}" data-m="${m}">${esc(t(lab))}</button>` : '';
  let html = '';
  if (entry) html += `<div class="meta">${esc(t('Zestaw'))}: ${esc(z.name)} · <b>${esc(entry.part)}</b> (${idx + 1}/${list.length})</div>`;
  const n = entry && entry.notes || {};
  const notes = [['wykonawca', 'Wykonawca'], ['tonacja', 'Tonacja'], ['uwagi', 'Uwagi'], ['zwroc', 'Na co zwrócić uwagę']].filter(([f]) => n[f]);
  if (notes.length) html += `<div class="notebox">${notes.map(([f, l]) => `<div><b>${esc(t(l))}:</b> ${esc(n[f])}</div>`).join('')}</div>`;
  if (hasCh || hasSc) html += `<div class="tabs">${tab('text', 'Tekst', true)}${tab('chords', 'Akordy', hasCh)}${tab('scores', 'Nuty', hasSc)}</div>`;
  if (mode === 'chords') {
    const key = Chords.firstChord(Chords.transposeText(s.chords, k, P.flat));
    html += `<div class="bar"><span class="small">${esc(t('Transpozycja'))}</span><button class="ib" id="tm">−½</button>
      <span class="key" title="${esc(t('Tonacja'))}">${esc(key || '·')}${k ? ` <small>(${k > 0 ? '+' : ''}${k})</small>` : ''}</span>
      <button class="ib" id="tp">+½</button><button class="ib" id="t0" ${k ? '' : 'disabled'}>0</button>
      <button class="ib ${P.flat ? 'on' : ''}" id="tf" title="${esc(t('Bemole w transpozycji (Es, As zamiast Dis, Gis)'))}">♭</button></div>
      <div class="cp">${Chords.chordproHtml(s.chords, { k, flat: P.flat })}</div>`;
  } else if (mode === 'scores') {
    html += `<div class="scores" id="sc">${(s.scores || []).map((sc, si) => `<figure data-si="${si}"><img data-k="${id}/${si}/0" alt=""><figcaption>${esc(sc.name)} · ${sc.n} ${esc(t('str.'))}</figcaption></figure>`).join('')}</div>`;
  } else {
    html += `<div class="lyr">${lyricsHtml(s)}</div>`;
  }
  if (s.notes) html += `<p class="note">${esc(s.notes)}</p>`;
  if ((s.youtube || []).length) html += `<div class="yt small"><b>${esc(t('Nagrania'))}:</b>${s.youtube.map(u => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(u)}</a>`).join('')}</div>`;
  html += `<p class="small">${esc([s.cat, s.src, s.tags].filter(Boolean).join(' · '))}</p>`;
  if (list) {
    const prev = list[idx - 1], next = list[idx + 1];
    html += `<div class="setnav">${prev ? `<a class="btn" href="#/song/${prev.id}?set=${z.id}&i=${idx - 1}">← ${esc(prev.title)}</a>` : '<span style="flex:1"></span>'}
      ${next ? `<a class="btn go" href="#/song/${next.id}?set=${z.id}&i=${idx + 1}">${esc(next.title)} →</a>` : ''}</div>`;
  }
  $('main').innerHTML = html;
  $('main').querySelectorAll('.tabs button').forEach(b => b.onclick = () => { P.mode = b.dataset.m; savePrefs(); route(); });
  if (mode === 'chords') {
    const setK = v => { v = ((v + 18) % 12) - 6; if (v) P.tr[id] = v; else delete P.tr[id]; savePrefs(); route(); };
    $('tm').onclick = () => setK(k - 1); $('tp').onclick = () => setK(k + 1); $('t0').onclick = () => setK(0);
    $('tf').onclick = () => { P.flat = !P.flat; savePrefs(); route(); };
  }
  if (mode === 'scores') {
    for (const img of $('main').querySelectorAll('img[data-k]')) {
      const b = await getOne('pages', img.dataset.k);
      if (b) img.src = URL.createObjectURL(b);
    }
    $('main').querySelectorAll('figure').forEach(f => f.onclick = () => openViewer(id, +f.dataset.si, s.scores[+f.dataset.si].n));
  }
  if (list) swipe($('main'), dir => {
    const j = idx + dir;
    if (list[j]) location.hash = `#/song/${list[j].id}?set=${z.id}&i=${j}`;
  });
}
function lyricsHtml(s) {
  const ref = (s.ref || []).length ? `<div class="ref"><span class="small">${esc(t('Ref.'))}</span><br>${s.ref.map(esc).join('<br>')}</div>` : '';
  const vs = (s.verses || []).map((v, i) => `<div class="v">${/^\s*\d+[.)]/.test(v[0] || '') ? '' : `<span class="n">${i + 1}.</span>`}${v.map(esc).join('<br>')}</div>`);
  if (!vs.length) return ref || (s.chords ? `<div class="cp lo">${Chords.chordproHtml(s.chords, { lyricsOnly: true })}</div>` : '');
  return P.repeatRef && ref ? vs.map(v => v + ref).join('') : ref + vs.join('');
}
function swipe(el, fn) {
  let x0 = null, y0 = 0;
  el.ontouchstart = e => { x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; };
  el.ontouchend = e => {
    if (x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0, dy = e.changedTouches[0].clientY - y0;
    x0 = null;
    if (Math.abs(dx) > 90 && Math.abs(dy) < 50) fn(dx < 0 ? 1 : -1);
  };
}

// ---------------------------------------------------------------- przeglądarka nut (pełny ekran, dotknięcie / pedał)
let V = null;
async function openViewer(sid, si, n) {
  V = { sid, si, n, p: 0, urls: [] };
  for (let i = 0; i < n; i++) { const b = await getOne('pages', `${sid}/${si}/${i}`); V.urls.push(b ? URL.createObjectURL(b) : ''); }
  $('viewer').hidden = false;
  try { await $('viewer').requestFullscreen(); } catch (e) { }
  drawViewer();
}
function drawViewer() { $('vImg').src = V.urls[V.p]; $('vCnt').textContent = `${t('strona')} ${V.p + 1} / ${V.n}`; }
function stepViewer(d) { if (!V) return; V.p = Math.max(0, Math.min(V.n - 1, V.p + d)); drawViewer(); }
function closeViewer() {
  $('viewer').hidden = true;
  if (document.fullscreenElement) document.exitFullscreen().catch(() => { });
  if (V) V.urls.forEach(u => u && URL.revokeObjectURL(u));
  V = null;
}
$('viewer').onclick = e => { if (e.target.id !== 'vClose') stepViewer(e.clientX < innerWidth / 3 ? -1 : 1); };
$('vClose').onclick = e => { e.stopPropagation(); closeViewer(); };
document.addEventListener('keydown', e => {
  if (!V) return;
  if (['ArrowRight', 'PageDown', ' ', 'ArrowDown'].includes(e.key)) { stepViewer(1); e.preventDefault(); }
  if (['ArrowLeft', 'PageUp', 'ArrowUp'].includes(e.key)) { stepViewer(-1); e.preventDefault(); }
  if (e.key === 'Escape') closeViewer();
}, true);

// ---------------------------------------------------------------- widok: zestawy na Mszę
function viewSets() {
  navOn('sets'); header(t('Zestawy'));
  $('main').innerHTML = SETS.length ? `<ul class="list">${SETS.map(z => `<li><a href="#/set/${z.id}">${esc(z.name)}
      <small>${esc([z.date, z.time, z.place, z.day].filter(Boolean).join(' · '))}</small></a></li>`).join('')}</ul>`
    : `<p class="empty">${esc(t('Brak zestawów – ułóż zestaw na Mszę w programie na komputerze i wyeksportuj go.'))}</p>`;
}
function viewSet(id) {
  navOn('sets');
  const z = SETS.find(x => x.id === id);
  if (!z) { location.hash = '#/sets'; return; }
  header(z.name, '#/sets');
  let i = 0, html = `<div class="meta">${esc([z.date, z.time, z.place, z.okres, z.day].filter(Boolean).join(' · '))}</div>`;
  for (const p of z.parts || []) {
    html += `<div class="part">${esc(p.part)}</div><ul class="list">`;
    for (const it of p.items) {
      const n = it.notes || {};
      const extra = [n.tonacja && `${t('Tonacja')}: ${n.tonacja}`, n.wykonawca, n.uwagi, n.zwroc].filter(Boolean).join(' · ');
      html += `<li><a href="#/song/${it.id}?set=${z.id}&i=${i}">${esc(it.title)}${BYID.has(it.id) ? '' : ' ⚠'}<small>${esc(extra)}</small></a></li>`;
      i++;
    }
    html += '</ul>';
  }
  $('main').innerHTML = html;
}

// ---------------------------------------------------------------- widok: ustawienia
let installEvt = null;
window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); installEvt = e; });
const installBtn = () => installEvt ? `<button class="btn wide" id="inst">⤓ ${esc(t('Zainstaluj aplikację'))}</button>` : '';
function bindInstall() { const b = $('inst'); if (b) b.onclick = async () => { installEvt.prompt(); installEvt = null; b.remove(); }; }

async function viewSettings() {
  navOn('settings'); header(t('Ustawienia'));
  const last = await getOne('meta', 'last');
  let used = '';
  try { const e = await navigator.storage.estimate(); used = (e.usage / 1048576).toFixed(1) + ' MB'; } catch (e) { }
  const chk = (id, on, lab) => `<div class="row"><label for="${id}">${esc(t(lab))}</label><input type="checkbox" id="${id}" ${on ? 'checked' : ''}></div>`;
  $('main').innerHTML = `
    <section><h2>${esc(t('Dane'))}</h2>
      <button class="btn go wide" id="imp">${esc(t('📥 Importuj plik'))}</button>
      <p class="small">${esc(t('Na komputerze: Plik → 📱 Eksport do aplikacji mobilnej (albo w pilocie: ⇩ Offline → Biblioteka do aplikacji).'))}<br>
      ${esc(t('Pliki zostają tylko na tym urządzeniu – aplikacja niczego nie wysyła.'))}</p>
      <p class="small">${esc(t('Pieśni'))}: ${SONGS.length} · ${esc(t('Zestawy'))}: ${SETS.length}${used ? ' · ' + esc(t('Zajęte miejsce')) + ': ' + used : ''}
      ${last ? '<br>' + esc(t('Ostatni import')) + ': ' + esc((last.at || '').slice(0, 16).replace('T', ' ')) + (last.app ? ' (Liber Canticorum ' + esc(last.app) + ')' : '') : ''}</p>
      ${installBtn()}
    </section>
    <section><h2>${esc(t('Wygląd'))}</h2>
      ${chk('dark', P.theme !== 'light', 'Ciemny motyw')}
      <div class="row"><label>${esc(t('Wielkość tekstu'))}</label><button class="ib" id="am">A−</button><b>${P.fs}</b><button class="ib" id="ap">A+</button></div>
      ${chk('flat', P.flat, 'Bemole w transpozycji (Es, As zamiast Dis, Gis)')}
      ${chk('rr', P.repeatRef, 'Refren po każdej zwrotce')}
      <div class="row"><label for="lg">${esc(t('Język'))}</label><select id="lg" style="width:auto">
        <option value="">Auto</option><option value="pl" ${P.lang === 'pl' ? 'selected' : ''}>Polski</option><option value="en" ${P.lang === 'en' ? 'selected' : ''}>English</option></select></div>
      <p class="small">${esc(t('Ekran nie wygaśnie, gdy pieśń jest otwarta.'))}</p>
    </section>
    <section><h2>${esc(t('O aplikacji'))}</h2>
      <p><b>Liber Canticorum</b> ${APP_VERSION} – ${esc(t('wolny śpiewnik liturgiczny dla muzyków, chórów i wspólnot Kościoła'))}.</p>
      <p class="small">GPL-3.0-or-later · <a href="https://github.com/ekolabynet/LiberCanticorum" target="_blank" rel="noopener">${esc(t('Kod źródłowy i program na komputer'))}</a></p>
    </section>
    <section><button class="btn wide" id="wipe">🗑 ${esc(t('Usuń wszystkie dane z telefonu'))}</button></section>`;
  $('imp').onclick = pickFile; bindInstall();
  $('dark').onchange = e => { P.theme = e.target.checked ? 'dark' : 'light'; savePrefs(); applyLook(); };
  $('flat').onchange = e => { P.flat = e.target.checked; savePrefs(); };
  $('rr').onchange = e => { P.repeatRef = e.target.checked; savePrefs(); };
  $('am').onclick = () => { P.fs = Math.max(12, P.fs - 2); savePrefs(); applyLook(); viewSettings(); };
  $('ap').onclick = () => { P.fs = Math.min(48, P.fs + 2); savePrefs(); applyLook(); viewSettings(); };
  $('lg').onchange = e => { P.lang = e.target.value; savePrefs(); location.reload(); };
  $('wipe').onclick = async () => {
    if (!confirm(t('Usunąć wszystkie pieśni, zestawy i nuty z tej aplikacji?'))) return;
    await tx(['songs', 'sets', 'pages', 'meta'], 'readwrite', x => ['songs', 'sets', 'pages', 'meta'].forEach(n => x.objectStore(n).clear()));
    await loadAll(); toast(t('Usunięto.')); viewSettings();
  };
}

// ---------------------------------------------------------------- routing (#/…) – przycisk „wstecz” w Androidzie działa naturalnie
function route() {
  const h = location.hash || '#/';
  const [path, qs] = h.slice(1).split('?');
  const q = new URLSearchParams(qs || '');
  const seg = path.split('/').filter(Boolean);
  if (!h.startsWith('#/song/')) keepAwake(false);
  if (V) closeViewer();
  window.scrollTo(0, 0);
  if (seg[0] === 'song') return viewSong(+seg[1], { set: q.has('set') ? +q.get('set') : null, i: +(q.get('i') || 0) });
  if (seg[0] === 'sets') return viewSets();
  if (seg[0] === 'set') return viewSet(+seg[1]);
  if (seg[0] === 'settings') return viewSettings();
  return viewSongs();
}
window.addEventListener('hashchange', route);
document.querySelectorAll('[data-t]').forEach(el => el.textContent = t(el.dataset.t));

(async function start() {
  applyLook();
  try { DB = await idb(); await loadAll(); } catch (e) { $('main').innerHTML = `<p class="empty">IndexedDB: ${esc(e)}</p>`; return; }
  route();
  if ('serviceWorker' in navigator && location.protocol !== 'file:') navigator.serviceWorker.register('sw.js').catch(() => { });
})();
