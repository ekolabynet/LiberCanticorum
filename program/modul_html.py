# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Autorzy projektu Liber Canticorum
"""
Śpiewnik offline w jednym pliku HTML – na telefon i tablet (Android, iPhone, iPad, komputer).

Plik działa bez internetu i bez programu: wystarczy otworzyć go w przeglądarce.
* lista pieśni z wyszukiwaniem (bez polskich znaków) i kategoriami, zestaw w kolejności,
* tryb TEKST (dla scholi / śpiewających): duża czcionka, motyw jasny / ciemny / sepia,
* tryb SLAJDY: pełny ekran jak w programie (tła, kolory) – np. telefon/tablet podłączony do rzutnika,
* tryb NUTY (dla organisty / chóru): strony PDF jako obrazy, przewracanie dotknięciem, klawiszami
  lub pedałem Bluetooth, dwie strony obok siebie w poziomie, ekran nie gaśnie.

Plik powstaje w programie (Eksport → Śpiewnik HTML) albo pobiera się przez pilota po Wi-Fi.
"""
import base64
import datetime
import html
import json
import os

import liber_canticorum as S


def favicon_uri():
    """Ikona programu (64 px) jako data URI – do strony pilota i śpiewnika offline."""
    import base64
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ikony", "liber_canticorum_64.png")
    try:
        with open(path, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
    except OSError:
        return ""


def _b64(data, mime="image/jpeg"):
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def build_songbook_html(songs, title="Śpiewnik", attachments_for=None, include_scores=True,
                        include_backgrounds=True, set_ids=None, progress=None):
    """songs – lista pieśni (słowniki z bazy); attachments_for(song_id) -> [(nazwa, rodzaj, bajty)].
    set_ids – kolejność zestawu (opcjonalnie). Zwraca tekst HTML."""
    import modul_nuty
    assets = {}                  # klucz -> data URI (tła i strony nut, bez duplikatów)
    out_songs = []
    for n, song in enumerate(songs):
        if progress:
            progress(n, len(songs), song.get('title', ''))
        cfg = S.song_cfg(song)
        deck, _ = S.build_song_deck(song)
        W, H = S.slide_dims(cfg)
        bg_key, light = None, S.is_light_color(cfg['kolor_tla'])
        if include_backgrounds and deck:
            path = S.resolve_background(cfg.get('tlo', ''), W, H)
            if path:
                bg_key = "bg:" + path
                if bg_key not in assets:
                    with open(path, "rb") as f:
                        assets[bg_key] = _b64(f.read(), "image/png" if path.lower().endswith(".png") else "image/jpeg")
                light = S.background_is_light(deck[0])
        ref = S.clean_refren_text(song.get('refren', ''))
        lyrics = {
            'ref': [l.strip() for l in ref.splitlines() if l.strip()],
            'verses': [v.split("\n") for v in S.process_verses(song.get('zwrotki_raw', ''), auto_punctuate=False, reflow=False)],
            'repeat': bool(cfg.get('powtarzaj_refren')),
        }
        scores = []
        if include_scores and attachments_for and song.get('id'):
            for name, kind, data in attachments_for(song['id']):
                low = name.lower()
                if low.endswith(".pdf") or data[:5] == b"%PDF-":
                    pages = modul_nuty.pdf_pages_to_jpeg(data, width=1400, quality=72)
                    keys = []
                    for i, pg in enumerate(pages):
                        k = f"sc:{song['id']}:{name}:{i}"
                        assets[k] = _b64(pg)
                        keys.append(k)
                    if keys:
                        scores.append({'name': name, 'pages': keys})
                elif low.endswith((".png", ".jpg", ".jpeg")):
                    k = f"sc:{song['id']}:{name}"
                    assets[k] = _b64(data, "image/png" if low.endswith(".png") else "image/jpeg")
                    scores.append({'name': name, 'pages': [k]})
        out_songs.append({
            'id': song.get('id') or n + 1, 'title': song.get('title', ''), 'cat': song.get('kategoria', ''),
            'tags': song.get('tagi', ''), 'notes': song.get('uwagi', ''), 'lyrics': lyrics, 'scores': scores,
            'chords': song.get('akordy', '') or '',
            'slides': [{'items': s.items, 'px': s.px} for s in deck],
            'look': {'W': W, 'H': H, 'mx': float(cfg.get('margines_x', 7)), 'my': float(cfg.get('margines_y', 5)),
                     'font': cfg['font'], 'text': cfg['kolor_tekstu'], 'ref': cfg['kolor_refrenu'], 'bgc': cfg['kolor_tla'],
                     'bg': bg_key, 'dim': int(cfg.get('przyciemnienie', 0)) if bg_key else 0, 'light': light,
                     'shadow': bool(cfg.get('cien')) and bool(bg_key)},
        })
    data = {'title': title, 'made': datetime.date.today().isoformat(), 'songs': out_songs,
            'set': [i for i in (set_ids or []) if any(s['id'] == i for s in out_songs)],
            'version': S.VERSION}
    js_data = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    js_assets = json.dumps(assets).replace("</", "<\\/")
    return (TEMPLATE.replace("__TITLE__", html.escape(title))
            .replace("__DATA__", js_data).replace("__ASSETS__", js_assets).replace("__FAVICON__", favicon_uri()))


TEMPLATE = r"""<!DOCTYPE html>
<html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#1b1d22">
<meta name="generator" content="Liber Canticorum (GPL-3.0-or-later)">
<link rel="icon" href="__FAVICON__">
<title>__TITLE__</title>
<style>
:root{--bg:#f6f1e6;--fg:#2b1d12;--mut:#7d6a55;--card:#fffaf0;--line:#e3d6bf;--acc:#a3201c;--btn:#ebe1cd}
body.dark{--bg:#15171b;--fg:#ece8df;--mut:#9aa0aa;--card:#1e2126;--line:#2c3038;--acc:#e0b85a;--btn:#2a2e36}
body.sepia{--bg:#efe2c4;--fg:#3b2a17;--mut:#7d6a55;--card:#f6ebd2;--line:#d8c39c;--acc:#9b2c1c;--btn:#e3d2ad}
[hidden]{display:none!important}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.4 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 12px;padding-top:max(10px,env(safe-area-inset-top))}
.bar{display:flex;gap:8px;align-items:center}
.bar h1{flex:1;font-size:18px;margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
button{font:inherit;color:var(--fg);background:var(--btn);border:0;border-radius:10px;padding:9px 12px}
button.acc{background:var(--acc);color:#fff}
input,select{font:inherit;color:var(--fg);background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px;width:100%}
.filters{display:grid;grid-template-columns:1fr auto;gap:8px;margin-top:8px}
main{padding:8px 12px 80px;max-width:900px;margin:auto}
h2.cat{font-size:14px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:18px 4px 6px}
.song{display:flex;justify-content:space-between;align-items:center;padding:12px;margin:4px 0;background:var(--card);border:1px solid var(--line);border-radius:12px}
.song small{color:var(--mut)}
.badge{font-size:12px;color:var(--mut);margin-left:6px}
.view{display:none}.view.act{display:block}
.tools{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}
.lyr{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;font-size:var(--fs,22px);line-height:1.45}
.lyr .ref{color:var(--acc);font-weight:600}
.lyr p{margin:0 0 .8em}
.lyr .lab{font-size:.7em;color:var(--mut);display:block}
.meta{color:var(--mut);font-size:14px;margin:4px 2px}
.chd .l{white-space:pre-wrap;margin:0}.chd .w{display:inline-block;position:relative;padding-top:1.15em;white-space:pre}
.chd .w b{position:absolute;top:0;left:0;color:var(--acc);font-size:.85em}.chd .side{float:right;color:var(--acc);font-weight:700;font-size:.85em}
.chd .gap{height:.7em}
/* pełny ekran: slajdy i nuty */
#stage{position:fixed;inset:0;background:#000;display:none;z-index:20;touch-action:manipulation;user-select:none}
#slide{position:absolute;overflow:hidden;background:#000 center/cover no-repeat}
#veil{position:absolute;inset:0}
#tbox{position:absolute;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;font-weight:700;overflow:hidden}
#tbox p{margin:0;white-space:pre-line}
#hud{position:absolute;top:8px;right:8px;display:flex;gap:6px;opacity:0;transition:opacity .3s}
#hud.show{opacity:1}
#hud button{background:#000a;color:#fff;padding:10px 14px}
#cnt{position:absolute;left:10px;bottom:8px;color:#fff8;font-size:13px;opacity:0;transition:opacity .3s}
#cnt.show{opacity:1}
#pages{position:absolute;inset:0;display:flex;justify-content:center;align-items:center;gap:6px;background:#fff}
#pages img{max-width:100%;max-height:100%;object-fit:contain;flex:1 1 0;min-width:0}
.sc img{width:100%;border:1px solid var(--line);border-radius:6px;margin:6px 0;background:#fff}
footer{color:var(--mut);font-size:12px;text-align:center;margin:30px 0}
</style></head><body>
<header><div class="bar"><button id="back" hidden onclick="home()">←</button><h1 id="h1"></h1>
<button onclick="theme()" title="Motyw">◐</button></div>
<div class="filters" id="filters"><input id="q" placeholder="Szukaj: tytuł lub słowa…" oninput="list()"><select id="cat" onchange="list()"></select></div></header>
<main>
<div class="view act" id="vList"><div id="setbox"></div><div id="songs"></div><footer id="foot"></footer></div>
<div class="view" id="vSong">
 <div class="tools"><button class="acc" onclick="present(cur,0)">▶ Slajdy</button><button id="bScore" onclick="scoresFull(cur)">♪ Nuty</button>
 <button id="bCh" onclick="toggleCh()">🎸 Akordy</button><span id="trb" hidden><button onclick="tr(-1)">♭−</button><button onclick="tr(1)">♯+</button></span>
 <button onclick="fs(-2)">A−</button><button onclick="fs(2)">A+</button><button onclick="nextSong(-1)">◀ pieśń</button><button onclick="nextSong(1)">pieśń ▶</button></div>
 <div class="meta" id="smeta"></div><div class="lyr" id="lyr"></div><div class="sc" id="sc"></div>
</div>
</main>
<div id="stage"><div id="slide"><div id="veil"></div><div id="tbox"></div></div><div id="pages" hidden></div>
<div id="hud"><button onclick="step(-1)">◀</button><button onclick="step(1)">▶</button><button onclick="closeStage()">✕</button></div><div id="cnt"></div></div>
<script id="data" type="application/json">__DATA__</script>
<script id="assets" type="application/json">__ASSETS__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const A=JSON.parse(document.getElementById('assets').textContent);
const $=id=>document.getElementById(id);
const fold=t=>(t||'').toLowerCase().replace(/ł/g,'l').normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[^a-z0-9]+/g,' ').trim();
D.songs.forEach(s=>s._f=fold(s.title+' '+s.lyrics.ref.join(' ')+' '+s.lyrics.verses.flat().join(' ')+' '+s.tags+' '+s.cat));
const byId=Object.fromEntries(D.songs.map(s=>[s.id,s]));
let cur=null,order=D.songs,mode=null,deck=[],di=0,wake=null;
const esc=t=>String(t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function store(k,v){try{if(v===undefined)return localStorage.getItem(k);localStorage.setItem(k,v)}catch(e){return null}}
// ---- motyw i czcionka
const THEMES=['','sepia','dark'];let th=+(store('sp_th')||0);document.body.className=THEMES[th];
function theme(){th=(th+1)%3;document.body.className=THEMES[th];store('sp_th',th);}
let FS=+(store('sp_fs')||22);document.documentElement.style.setProperty('--fs',FS+'px');
function fs(d){FS=Math.max(14,Math.min(48,FS+d));document.documentElement.style.setProperty('--fs',FS+'px');store('sp_fs',FS);}
// ---- lista
function init(){$('h1').textContent=D.title;const cats=[...new Set(D.songs.map(s=>s.cat||''))].sort();
 $('cat').innerHTML='<option value="*">wszystkie</option>'+cats.map(c=>`<option value="${esc(c)}">${esc(c||'(bez kategorii)')}</option>`).join('');
 $('foot').textContent=`${D.songs.length} pieśni · ${D.made} · działa bez internetu · Liber Canticorum`;
 if(D.set.length){$('setbox').innerHTML=`<h2 class="cat">Zestaw</h2>`+D.set.map((id,i)=>{const s=byId[id];
  return `<div class="song" onclick="openSong(${id},true)"><span>${i+1}. ${esc(s.title)}</span><button class="acc" onclick="event.stopPropagation();presentSet(${i})">▶</button></div>`}).join('')
  +`<div class="tools"><button class="acc" onclick="presentSet(0)">▶ Slajdy całego zestawu</button></div>`;}
 list();}
function list(){const q=fold($('q').value),c=$('cat').value;
 const L=D.songs.filter(s=>(c==='*'||(s.cat||'')===c)&&q.split(' ').every(w=>s._f.includes(w)));
 const g={};L.forEach(s=>(g[s.cat||'']=g[s.cat||'']||[]).push(s));
 $('songs').innerHTML=Object.keys(g).sort().map(k=>`<h2 class="cat">${esc(k||'(bez kategorii)')}</h2>`+g[k].sort((a,b)=>a.title.localeCompare(b.title,'pl')).map(s=>
  `<div class="song" onclick="openSong(${s.id})"><span>${esc(s.title)}${s.scores.length?'<span class="badge">♪ nuty</span>':''}</span><small>${s.slides.length} sl.</small></div>`).join('')).join('')||'<p class="meta">Brak wyników.</p>';
 $('setbox').hidden=!!(q||c!=='*');order=L;}
function home(){show('vList');$('back').hidden=true;$('filters').hidden=false;$('h1').textContent=D.title;history.replaceState(null,'','#');}
function show(v){document.querySelectorAll('.view').forEach(x=>x.classList.toggle('act',x.id===v));scrollTo(0,0);}
// ---- pieśń
function openSong(id,fromSet){const s=byId[id];cur=s;if(fromSet)order=D.set.map(i=>byId[i]);
 $('h1').textContent=s.title;$('back').hidden=false;$('filters').hidden=true;
 $('smeta').textContent=[s.cat,s.notes].filter(Boolean).join(' · ');
 const L=s.lyrics;let h='';if(L.ref.length)h+=`<p class="ref"><span class="lab">Refren</span>${L.ref.map(esc).join('<br>')}</p>`;
 L.verses.forEach((v,i)=>{let lines=v.slice(),lab='';const m=lines[0].match(/^(\d+)\.\s*(.*)$/);if(m){lab='Zwrotka '+m[1];lines[0]=m[2];}
  h+=`<p>${lab?`<span class="lab">${lab}</span>`:''}${lines.map(esc).join('<br>')}</p>`;
  if(L.ref.length&&L.repeat&&i<L.verses.length-1)h+=`<p class="ref"><span class="lab">Refren</span>${esc(L.ref[0])}…</p>`;});
 $('lyr').innerHTML=h||'<p class="meta">(brak tekstu)</p>';
 $('bCh').hidden=!s.chords;if(CH&&s.chords)drawCh();else{$('trb').hidden=true;}
 $('bScore').hidden=!s.scores.length;
 $('sc').innerHTML=s.scores.map(sc=>`<h2 class="cat">${esc(sc.name)}</h2>`+sc.pages.map(k=>`<img loading="lazy" src="${A[k]}">`).join('')).join('');
 show('vSong');history.replaceState(null,'','#'+id);}
function nextSong(d){if(!cur)return;const i=order.indexOf(cur);const n=order[i+d];if(n)openSong(n.id,order!==D.songs&&D.set.length&&order.length===D.set.length);}
// ---- akordy (widok dla gitarzystów)
let CH=store('sp_ch')==='1',TR=0;
const PL=['C','Cis','D','Dis','E','F','Fis','G','Gis','A','B','H'],BASE={C:0,D:2,E:4,F:5,G:7,A:9,H:11,B:10};
function tch(c,k){const m=c.match(/^([A-Ha-h])(is|es|s)?(.*?)(?:\/([A-Ha-h])(is|es|s)?)?$/);if(!m||!k)return c;
 const one=(r,a)=>{let n=BASE[r.toUpperCase()];if(a==='is')n++;else if(a)n--;let x=PL[((n+k)%12+12)%12];return r===r.toLowerCase()?x.toLowerCase():x;};
 return one(m[1],m[2])+m[3]+(m[4]?'/'+one(m[4],m[5]):'');}
function tline(t){return t.replace(/[A-Ha-h](?:is|es|s)?[^\s\]\/]*(?:\/[A-Ha-h](?:is|es|s)?)?/g,x=>tch(x,TR));}
function drawCh(){const s=cur;let h='';(s.chords||'').split('\n').forEach(line=>{const [body,side]=line.split('‖');
 if(!body.trim()&&!side){h+='<div class="gap"></div>';return;}
 let parts=body.split(/(\[[^\]]*\])/),out='',pend='';
 parts.forEach(p=>{if(/^\[.*\]$/.test(p)){if(pend)out+=`<span class="w"><b>${esc(pend)}</b> </span>`;pend=tline(p.slice(1,-1));return;}
  if(!p&&!pend)return;out+=pend?`<span class="w"><b>${esc(pend)}</b>${esc(p)||' '}</span>`:esc(p);pend='';});
 if(pend)out+=`<span class="w"><b>${esc(pend)}</b> </span>`;
 h+=`<p class="l">${side?`<span class="side">${esc(tline(side.trim()))}</span>`:''}${out}</p>`;});
 $('lyr').innerHTML=`<div class="chd">${h}</div>`;$('trb').hidden=false;$('bCh').textContent='🎸 Tekst';}
function toggleCh(){CH=!CH;store('sp_ch',CH?'1':'0');TR=0;$('bCh').textContent='🎸 Akordy';openSong(cur.id);}
function tr(d){TR+=d;drawCh();}
// ---- pełny ekran
async function enter(){const st=$('stage');st.style.display='block';
 try{if(st.requestFullscreen)await st.requestFullscreen();else if(st.webkitRequestFullscreen)st.webkitRequestFullscreen();}catch(e){}
 try{wake=await navigator.wakeLock.request('screen');}catch(e){}
 hud();}
function closeStage(){$('stage').style.display='none';mode=null;if(document.fullscreenElement)document.exitFullscreen().catch(()=>{});if(wake){wake.release().catch(()=>{});wake=null;}}
document.addEventListener('fullscreenchange',()=>{if(!document.fullscreenElement&&mode)closeStage();});
let ht=null;function hud(){$('hud').classList.add('show');$('cnt').classList.add('show');clearTimeout(ht);ht=setTimeout(()=>{$('hud').classList.remove('show');$('cnt').classList.remove('show');},2500);}
function present(s,start){deck=s.slides.map(sl=>({s,sl}));if(!deck.length)return;mode='slides';di=start||0;$('pages').hidden=true;$('slide').hidden=false;enter().then(drawSlide);}
function presentSet(i){deck=[];D.set.forEach((id,k)=>{const s=byId[id];if(k>0)deck.push({s,sl:null});s.slides.forEach(sl=>deck.push({s,sl}));});
 let start=0;for(let k=0,c=0;k<deck.length;k++){if(deck[k].sl&&deck[k].s===byId[D.set[i]]){start=k;break;}}
 mode='slides';di=start;$('pages').hidden=true;$('slide').hidden=false;enter().then(drawSlide);}
function drawSlide(){if(mode!=='slides')return;const {s,sl}=deck[di],L=s.look,box=$('slide'),t=$('tbox');
 const vw=innerWidth,vh=innerHeight,sc=Math.min(vw/L.W,vh/L.H),w=L.W*sc,h=L.H*sc;
 Object.assign(box.style,{width:w+'px',height:h+'px',left:(vw-w)/2+'px',top:(vh-h)/2+'px',backgroundColor:L.bgc,backgroundImage:L.bg?`url(${A[L.bg]})`:'none'});
 $('veil').style.background=L.dim?(L.light?`rgba(246,238,217,${L.dim/100})`:`rgba(0,0,0,${L.dim/100})`):'none';
 Object.assign(t.style,{left:L.mx+'%',right:L.mx+'%',top:L.my+'%',bottom:L.my+'%',fontFamily:`"${L.font}",Arial,Helvetica,sans-serif`});
 const light=isLight(L.text);t.style.textShadow=!L.shadow?'none':light?`${h*.004}px ${h*.004}px ${h*.004}px rgba(0,0,0,.8)`:`0 0 ${h*.008}px rgba(250,244,228,.95),0 0 ${h*.004}px rgba(250,244,228,.95)`;
 if(!sl){t.innerHTML='';box.style.backgroundImage='none';box.style.backgroundColor='#000';$('veil').style.background='none';}
 else{let size=sl.px/1080*h;t.innerHTML=sl.items.map(([k,x],i)=>`<p style="color:${k==='ref'?L.ref:L.text};margin-bottom:${i<sl.items.length-1?.45:0}em">${esc(x)}</p>`).join('');
  t.style.fontSize=size+'px';t.style.lineHeight='1.15';let n=0;while(t.scrollHeight>t.clientHeight+1&&n++<40){size*=.95;t.style.fontSize=size+'px';}}
 $('cnt').textContent=`${s.title} · ${di+1}/${deck.length}`;}
function isLight(c){const m=c.match(/[0-9a-f]{2}/gi);if(!m)return true;const[r,g,b]=m.map(x=>parseInt(x,16));return .299*r+.587*g+.114*b>140;}
// ---- nuty (organista / chór)
let pages=[],pi=0;
function scoresFull(s){pages=s.scores.flatMap(sc=>sc.pages);if(!pages.length)return;mode='pages';pi=0;$('slide').hidden=true;$('pages').hidden=false;enter().then(drawPages);}
function drawPages(){if(mode!=='pages')return;const two=innerWidth>innerHeight*1.15&&pages.length>1;
 const ks=two?[pages[pi],pages[pi+1]].filter(Boolean):[pages[pi]];$('pages').innerHTML=ks.map(k=>`<img src="${A[k]}">`).join('');
 $('cnt').textContent=`${cur.title} · strona ${pi+1}${two&&ks.length>1?'–'+(pi+2):''} / ${pages.length}`;}
function step(d){hud();if(mode==='slides'){di=Math.max(0,Math.min(deck.length-1,di+d));drawSlide();}
 else if(mode==='pages'){const two=innerWidth>innerHeight*1.15?2:1;pi=Math.max(0,Math.min(pages.length-1,pi+d*two));drawPages();}}
$('stage').addEventListener('click',e=>{if(e.target.closest('#hud'))return;step(e.clientX<innerWidth/3?-1:1);});
let tx=null;$('stage').addEventListener('touchstart',e=>tx=e.touches[0].clientX,{passive:true});
$('stage').addEventListener('touchend',e=>{if(tx===null)return;const dx=e.changedTouches[0].clientX-tx;tx=null;if(Math.abs(dx)>50){e.preventDefault();step(dx<0?1:-1);}});
document.addEventListener('keydown',e=>{if(!mode)return;if(['ArrowRight','ArrowDown','PageDown',' ','Enter'].includes(e.key)){e.preventDefault();step(1);}
 else if(['ArrowLeft','ArrowUp','PageUp','Backspace'].includes(e.key)){e.preventDefault();step(-1);}else if(e.key==='Escape')closeStage();});
addEventListener('resize',()=>{if(mode==='slides')drawSlide();if(mode==='pages')drawPages();});
document.addEventListener('visibilitychange',async()=>{if(mode&&document.visibilityState==='visible'){try{wake=await navigator.wakeLock.request('screen');}catch(e){}}});
init();const h=+location.hash.slice(1);if(byId[h])openSong(h);
</script></body></html>
"""
