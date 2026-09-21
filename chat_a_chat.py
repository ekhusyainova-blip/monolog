INDEX_HTML = """<!DOCTYPE html>
<html lang="ru" data-theme="dark" data-fontsize="md">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, interactive-widget=resizes-content">
<meta name="color-scheme" content="dark light">
<title>Monolog</title>
<style>
:root[data-theme="dark"]{
  --bg:#0f0f10; --fg:#ececee; --muted:#7c7c82; --dim:#58585e;
  --accent:#6ea8fe;
  --glass:rgba(255,255,255,0.055);
  --glass-strong:rgba(255,255,255,0.09);
  --glass-border:rgba(255,255,255,0.07);
  --code-bg:#151518; --code-border:#1e1e21;
  --slider-bg:rgba(255,255,255,0.08);
  --slider-knob:#d8d8dc;
  --topbar:rgba(20,20,22,0.72);
  --handle:rgba(255,255,255,0.18);
  --sheet-glass:rgba(28,28,32,0.72);
}
:root[data-theme="light"]{
  --bg:#fbfbfc; --fg:#1a1a1c; --muted:#8a8a8f; --dim:#b5b5ba;
  --accent:#2563eb;
  --glass:rgba(0,0,0,0.035);
  --glass-strong:rgba(0,0,0,0.06);
  --glass-border:rgba(0,0,0,0.05);
  --code-bg:#f4f4f6; --code-border:#e7e7ea;
  --slider-bg:rgba(0,0,0,0.06);
  --slider-knob:#ffffff;
  --topbar:rgba(251,251,252,0.72);
  --handle:rgba(0,0,0,0.18);
  --sheet-glass:rgba(255,255,255,0.72);
}
:root[data-fontsize="sm"]{--fs:14px}
:root[data-fontsize="md"]{--fs:16px}
:root[data-fontsize="lg"]{--fs:18px}
:root[data-fontsize="xl"]{--fs:21px}

*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{
  font:var(--fs)/1.7 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,sans-serif;
  background:var(--bg);color:var(--fg);
  display:flex;flex-direction:column;
  -webkit-font-smoothing:antialiased;
  overscroll-behavior-y:none;
}
.wrap{
  width:100%;max-width:760px;margin:0 auto;
  display:flex;flex-direction:column;flex:1;min-height:0;
  height:100dvh;position:relative;overflow:hidden;
}

/* Верхняя полупрозрачная полоса */
.topbar{
  position:absolute;top:0;left:0;right:0;
  height:44px;z-index:20;
  background:var(--topbar);
  backdrop-filter:saturate(180%) blur(18px);
  -webkit-backdrop-filter:saturate(180%) blur(18px);
  border-bottom:1px solid transparent;
  transition:border-color 0.2s;
  display:flex;align-items:center;justify-content:flex-end;
  padding:0 14px;gap:12px;
  pointer-events:none;
}
.topbar > *{pointer-events:auto}
.topbar.scrolled{border-bottom-color:var(--glass-border)}

.font-ctl{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--muted);user-select:none}
.font-aa{background:none;border:none;padding:2px 4px;color:var(--muted);cursor:pointer;font:inherit;letter-spacing:0.3px;font-weight:600}
.font-aa:hover{color:var(--fg)}
.font-slider{width:0;opacity:0;overflow:hidden;transition:width 0.25s,opacity 0.2s;display:flex;align-items:center;height:22px}
.font-ctl.open .font-slider{width:70px;opacity:1}
.font-track{position:relative;width:70px;height:2px;background:var(--slider-bg);border-radius:1px}
.font-track .knob{position:absolute;top:-6px;width:14px;height:14px;background:var(--slider-knob);border-radius:50%;box-shadow:0 1px 3px rgba(0,0,0,0.2);transition:left 0.15s}

.theme-slider{width:34px;height:18px;background:var(--slider-bg);border-radius:9px;cursor:pointer;border:none;padding:0;position:relative;opacity:0.72;transition:opacity 0.15s}
.theme-slider:hover{opacity:1}
.theme-slider .knob{position:absolute;top:2px;left:2px;width:14px;height:14px;background:var(--slider-knob);border-radius:50%;transition:transform 0.25s cubic-bezier(0.4,0,0.2,1);box-shadow:0 1px 2px rgba(0,0,0,0.18)}
:root[data-theme="light"] .theme-slider .knob{transform:translateX(16px)}

#log{
  flex:1;min-height:0;overflow-y:auto;
  padding:60px 20px 40px;
  display:flex;flex-direction:column;gap:22px;
  scroll-behavior:smooth;
}
#log::-webkit-scrollbar{width:0}

.msg{display:flex;flex-direction:column;max-width:100%}
.msg.user{
  align-self:flex-end;max-width:82%;
  background:var(--glass);
  backdrop-filter:blur(14px) saturate(140%);
  -webkit-backdrop-filter:blur(14px) saturate(140%);
  border:1px solid var(--glass-border);
  border-radius:14px;
  padding:10px 14px;
  font-size:calc(var(--fs) - 1px);
  line-height:1.55;
  color:var(--fg);
  white-space:pre-wrap;
}
.msg.bot{align-self:stretch;font-size:var(--fs);line-height:1.75;color:var(--fg);background:none}
.msg.bot p{margin:0 0 12px}
.msg.bot p:last-child{margin-bottom:0}
.msg.bot strong{font-weight:600;color:var(--fg)}
.msg.bot em{font-style:italic;color:var(--muted)}
.msg.bot h1,.msg.bot h2,.msg.bot h3{margin:18px 0 10px;font-weight:600;line-height:1.3}
.msg.bot h1{font-size:calc(var(--fs) + 3px)}
.msg.bot h2{font-size:calc(var(--fs) + 1px)}
.msg.bot h3{font-size:calc(var(--fs) - 2px);color:var(--muted);text-transform:uppercase;letter-spacing:0.6px}
.msg.bot ul,.msg.bot ol{margin:8px 0 12px 22px}
.msg.bot li{margin:4px 0}
.msg.bot a{color:var(--accent);text-decoration:none;border-bottom:1px solid color-mix(in srgb,var(--accent) 40%,transparent)}
.msg.bot hr{border:none;border-top:1px solid var(--glass-border);margin:20px 0}
.msg.bot blockquote{border-left:2px solid var(--glass-border);padding:2px 0 2px 12px;margin:10px 0;color:var(--muted)}
.msg.bot code.inline{background:var(--code-bg);padding:2px 6px;border-radius:4px;font:0.92em ui-monospace,"SF Mono",SFMono-Regular,Menlo,monospace}

.code-block{position:relative;margin:14px 0;background:var(--code-bg);border:1px solid var(--code-border);border-radius:12px;overflow:hidden}
.code-block .lang{position:absolute;top:10px;left:14px;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:0.8px;font-weight:500}
.code-block pre{padding:36px 16px 16px;overflow-x:auto;font:13px/1.65 ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;white-space:pre;margin:0;color:var(--fg)}
.code-block .copy-btn{position:absolute;top:8px;right:8px;background:transparent;border:1px solid transparent;color:var(--muted);width:28px;height:28px;border-radius:6px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background 0.15s,color 0.15s,border-color 0.15s}
.code-block .copy-btn:hover{background:var(--bg);border-color:var(--code-border);color:var(--fg)}
.code-block .copy-btn svg{width:14px;height:14px;stroke:currentColor;fill:none;stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round}
.code-block .copy-btn.copied{color:var(--accent)}

table{width:100%;border-collapse:collapse;margin:14px 0;font-size:calc(var(--fs) - 2px)}
table th,table td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--glass-border)}
table th{font-weight:600;color:var(--muted);font-size:calc(var(--fs) - 4px);text-transform:uppercase;letter-spacing:0.5px}
table tr:last-child td{border-bottom:none}

/* Композер */
.composer-wrap{
  flex-shrink:0;position:relative;z-index:15;
  background:var(--bg);
  padding-bottom:env(safe-area-inset-bottom, 0px);
}
.composer-wrap::before{
  content:'';position:absolute;left:0;right:0;top:-24px;height:24px;
  background:linear-gradient(to top, var(--bg), transparent);
  pointer-events:none;
}

/* Язычок шторки */
.sheet-handle{
  display:flex;flex-direction:column;align-items:center;gap:0;
  padding:8px 0 2px;
  cursor:grab;touch-action:none;user-select:none;
  -webkit-tap-highlight-color:transparent;
}
.sheet-handle:active{cursor:grabbing}
.sheet-handle .bar{
  width:36px;height:4px;border-radius:2px;
  background:var(--handle);
  transition:width 0.2s,background 0.2s;
}
.sheet-handle .hint{
  margin-top:4px;
  font-size:10px;color:var(--muted);
  letter-spacing:0.6px;text-transform:uppercase;
  opacity:0;transform:translateY(-2px);
  transition:opacity 0.35s,transform 0.35s;
  font-weight:500;
}
.sheet-handle.hint-on .hint{opacity:0.75;transform:translateY(0)}
.sheet-handle.hint-on .bar{width:44px;background:var(--muted)}

.composer{
  display:flex;align-items:flex-end;gap:6px;
  padding:4px 14px 12px;
}
.attach-btn{
  flex-shrink:0;width:30px;height:30px;
  background:none;border:none;border-radius:8px;
  color:var(--dim);cursor:pointer;padding:0;
  display:flex;align-items:center;justify-content:center;
  transition:color 0.15s,background 0.15s;
  margin-bottom:4px;
}
.attach-btn:hover{color:var(--muted);background:var(--glass)}
.attach-btn svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}

.input-glass{flex:1;background:transparent;border:none;border-radius:12px;padding:8px 10px;transition:background 0.2s}
.input-glass:focus-within{
  background:var(--glass);
  backdrop-filter:blur(12px) saturate(140%);
  -webkit-backdrop-filter:blur(12px) saturate(140%);
}
#input{
  display:block;width:100%;
  resize:none;background:none;color:var(--fg);
  border:none;outline:none;padding:0;
  font:inherit;
  min-height:calc(var(--fs) * 1.55);
  max-height:180px;
  white-space:pre-wrap;overflow-y:auto;
  caret-color:var(--accent);
  -webkit-tap-highlight-color:transparent;
}
#input:focus{outline:none}
#input::placeholder{color:var(--dim);transition:opacity 0.3s}

/* ===== Шторка — матовое стекло ===== */
.sheet{
  position:absolute;left:0;right:0;bottom:0;
  background:transparent;
  backdrop-filter:blur(0px) saturate(100%);
  -webkit-backdrop-filter:blur(0px) saturate(100%);
  border-top-left-radius:20px;border-top-right-radius:20px;
  border-top:1px solid transparent;
  transform:translateY(100%);
  transition:transform 0.34s cubic-bezier(0.4,0,0.2,1),
             backdrop-filter 0.34s ease,
             -webkit-backdrop-filter 0.34s ease,
             background 0.34s ease,
             border-color 0.34s ease;
  max-height:78dvh;
  display:flex;flex-direction:column;
  z-index:30;
  will-change:transform,backdrop-filter;
}
.sheet.dragging{transition:none}
.sheet.open{
  background:var(--sheet-glass);
  backdrop-filter:blur(28px) saturate(180%);
  -webkit-backdrop-filter:blur(28px) saturate(180%);
  border-top-color:var(--glass-border);
  box-shadow:0 -20px 60px rgba(0,0,0,0.22);
}
.sheet .sheet-grab{
  width:36px;height:4px;border-radius:2px;
  background:var(--handle);
  margin:10px auto 6px;flex-shrink:0;
}
.sheet .sheet-body{overflow-y:auto;padding:6px 20px 24px}
.sheet .sheet-title{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin:14px 0 6px;font-weight:600}
.sheet .sheet-item{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:10px;color:var(--fg);cursor:pointer;font-size:calc(var(--fs) - 2px);transition:background 0.15s}
.sheet .sheet-item:hover{background:var(--glass)}
.sheet .sheet-item .ico{width:18px;height:18px;flex-shrink:0;color:var(--muted);display:flex;align-items:center;justify-content:center;font-size:14px}

/* Затемнение фона под шторкой */
.scrim{
  position:absolute;inset:0;z-index:25;
  background:rgba(0,0,0,0.28);
  opacity:0;pointer-events:none;
  transition:opacity 0.34s ease;
}
.scrim.on{opacity:1;pointer-events:auto}
:root[data-theme="light"] .scrim{background:rgba(0,0,0,0.12)}

@media (max-width:600px){
  #log{padding:56px 16px 34px;gap:20px}
  .msg.user{max-width:86%}
  .composer{padding:2px 10px 10px;gap:4px}
  .composer-wrap::before{top:-18px;height:18px}
  .code-block pre{font-size:12.5px;padding:34px 14px 14px}
  table{font-size:calc(var(--fs) - 3px)}
  table th,table td{padding:7px 9px}
  .sheet{max-height:82dvh}
}
</style>
</head>
<body>
<div class="wrap" id="wrap">

  <div class="topbar" id="topbar">
    <div class="font-ctl" id="fontCtl">
      <button class="font-aa" id="aaBtn" title="Размер шрифта" aria-label="Размер шрифта">Aa</button>
      <div class="font-slider" id="fontSlider">
        <div class="font-track" id="fontTrack">
          <div class="knob" id="fontKnob"></div>
        </div>
      </div>
    </div>
    <button class="theme-slider" id="theme" onclick="toggleTheme()" title="Тема" aria-label="Тема">
      <span class="knob"></span>
    </button>
  </div>

  <div id="log"></div>

  <div class="scrim" id="scrim"></div>

  <div class="composer-wrap" id="composerWrap">
    <div class="sheet-handle" id="sheetHandle" title="Потяни вверх">
      <div class="bar"></div>
      <div class="hint">потяни вверх</div>
    </div>
    <div class="composer">
      <button class="attach-btn" id="attachBtn" title="Вложение" aria-label="Вложение">
        <svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>
      </button>
      <div class="input-glass" id="inputGlass">
        <textarea id="input" rows="1" placeholder=""></textarea>
      </div>
    </div>
  </div>

  <div class="sheet" id="sheet">
    <div class="sheet-grab"></div>
    <div class="sheet-body">
      <div class="sheet-title">Чаты</div>
      <div class="sheet-item"><span class="ico">💬</span>Текущий чат</div>
      <div class="sheet-item"><span class="ico">+</span>Новый чат</div>

      <div class="sheet-title">Модули</div>
      <div class="sheet-item" data-mod="chat"><span class="ico">◯</span>Чат — активен</div>
      <div class="sheet-item" data-mod="tools"><span class="ico">◯</span>Инструменты</div>
      <div class="sheet-item" data-mod="status"><span class="ico">◯</span>Статус</div>
      <div class="sheet-item" data-mod="dashboard"><span class="ico">◯</span>Dashboard</div>

      <div class="sheet-title">Настройки</div>
      <div class="sheet-item" onclick="fontCtl.classList.add('open');closeSheet()"><span class="ico">Aa</span>Размер шрифта</div>
      <div class="sheet-item" onclick="toggleTheme();closeSheet()"><span class="ico">◐</span>Тема</div>
      <div class="sheet-item" onclick="location.reload()"><span class="ico">↺</span>Сбросить</div>
    </div>
  </div>

</div>
<script>
var log=document.getElementById('log');
var input=document.getElementById('input');
var chatHistory=[];
var topbar=document.getElementById('topbar');
var composerWrap=document.getElementById('composerWrap');
var sheet=document.getElementById('sheet');
var sheetHandle=document.getElementById('sheetHandle');
var scrim=document.getElementById('scrim');
var fontCtl=document.getElementById('fontCtl');
var aaBtn=document.getElementById('aaBtn');
var fontTrack=document.getElementById('fontTrack');
var fontKnob=document.getElementById('fontKnob');

var ICON_COPY='<svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
var ICON_CHECK='<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>';

/* ===== Плейсхолдер от ИИ ===== */
var PH_KEY='monolog_placeholder';
var PH_CACHE_KEY='monolog_placeholder_at';
var PH_TTL=1000*60*30;

function setPlaceholder(p){
  if(!p)return;
  input.setAttribute('placeholder',p);
}

async function fetchPlaceholder(){
  var cached=localStorage.getItem(PH_KEY);
  var cachedAt=parseInt(localStorage.getItem(PH_CACHE_KEY)||'0',10);
  if(cached)setPlaceholder(cached);
  if(cached && (Date.now()-cachedAt)<PH_TTL)return;
  try{
    var r=await fetch('/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        text:'Напиши одну очень короткую фразу-приглашение для плейсхолдера поля ввода в чате. 2-5 слов. Без кавычек, без точки в конце, без пояснений. Только саму фразу. Пиши каждый раз новую.',
        context:[]
      })
    });
    var j=await r.json();
    var answer=j && j.data && j.data.answer ? j.data.answer.trim() : '';
    answer=answer.split('\\n')[0].replace(/^["'«»\\s]+|["'«»\\s.]+$/g,'').slice(0,40);
    if(answer){
      localStorage.setItem(PH_KEY,answer);
      localStorage.setItem(PH_CACHE_KEY,String(Date.now()));
      setPlaceholder(answer);
    }
  }catch(e){}
}
fetchPlaceholder();

/* Тема */
function setTheme(t){
  document.documentElement.setAttribute('data-theme',t);
  localStorage.setItem('monolog_theme',t);
}
function toggleTheme(){
  var cur=document.documentElement.getAttribute('data-theme');
  setTheme(cur==='dark'?'light':'dark');
}
(function(){
  var s=localStorage.getItem('monolog_theme');
  if(s)setTheme(s);
  else if(window.matchMedia('(prefers-color-scheme: light)').matches)setTheme('light');
  else setTheme('dark');
})();

/* Размер шрифта */
var FONT_STEPS=['sm','md','lg','xl'];
function setFont(idx){
  idx=Math.max(0,Math.min(FONT_STEPS.length-1,idx));
  document.documentElement.setAttribute('data-fontsize',FONT_STEPS[idx]);
  localStorage.setItem('monolog_font',String(idx));
  var pct=idx/(FONT_STEPS.length-1);
  fontKnob.style.left=(pct*(70-14))+'px';
}
(function(){
  var s=parseInt(localStorage.getItem('monolog_font')||'1',10);
  setFont(s);
})();
aaBtn.addEventListener('click',function(e){
  e.stopPropagation();
  fontCtl.classList.toggle('open');
});
document.addEventListener('click',function(e){
  if(!fontCtl.contains(e.target))fontCtl.classList.remove('open');
});
var draggingFont=false;
function setFontFromEvent(x){
  var rect=fontTrack.getBoundingClientRect();
  var v=Math.max(0,Math.min(rect.width,x-rect.left));
  var idx=Math.round((v/rect.width)*(FONT_STEPS.length-1));
  setFont(idx);
}
fontTrack.addEventListener('pointerdown',function(e){draggingFont=true;setFontFromEvent(e.clientX);fontTrack.setPointerCapture(e.pointerId);});
fontTrack.addEventListener('pointermove',function(e){if(draggingFont)setFontFromEvent(e.clientX);});
fontTrack.addEventListener('pointerup',function(e){draggingFont=false;try{fontTrack.releasePointerCapture(e.pointerId)}catch(_){}});

/* ===== Шторка ===== */
var sheetOpen=false;
var sheetH=0;
var drag={active:false,startY:0,currentY:0,startTranslate:0};

function measureSheet(){
  sheetH=sheet.getBoundingClientRect().height || 0;
  if(sheetOpen)sheet.style.transform='translateY(0px)';
}
window.addEventListener('resize',measureSheet);
setTimeout(measureSheet,60);

function openSheet(){
  sheetOpen=true;
  sheet.classList.add('open');
  sheet.style.transform='';
  scrim.classList.add('on');
}
function closeSheet(){
  sheetOpen=false;
  sheet.classList.remove('open');
  sheet.style.transform='';
  scrim.classList.remove('on');
}

function onDown(e){
  if(e.target.closest('#input'))return;
  if(e.target.closest('.attach-btn'))return;
  if(e.target.closest('.font-ctl'))return;
  if(e.target.closest('.theme-slider'))return;
  drag.active=true;
  drag.startY=(e.touches?e.touches[0].clientY:e.clientY);
  drag.currentY=drag.startY;
  drag.startTranslate=sheetOpen?0:sheetH;
  sheet.classList.add('dragging');
  sheet.style.transform='translateY('+drag.startTranslate+'px)';
  if(!sheetOpen)sheetHandle.classList.add('hint-on');
}

function onMove(e){
  if(!drag.active)return;
  drag.currentY=(e.touches?e.touches[0].clientY:e.clientY);
  var dy=drag.currentY-drag.startY;
  var newTranslate=drag.startTranslate+dy;
  newTranslate=Math.max(0,Math.min(sheetH,newTranslate));
  sheet.style.transform='translateY('+newTranslate+'px)';
  /* Матовое стекло проявляется пропорционально подъёму */
  var progress=1-(newTranslate/sheetH);
  var blur=progress*28;
  var alpha=progress;
  sheet.style.backdropFilter='blur('+blur+'px) saturate('+(100+progress*80)+'%)';
  sheet.style.webkitBackdropFilter='blur('+blur+'px) saturate('+(100+progress*80)+'%)';
  /* Фон проявляется */
  var bg=document.documentElement.getAttribute('data-theme')==='dark'
    ? 'rgba(28,28,32,'+(0.72*alpha)+')'
    : 'rgba(255,255,255,'+(0.72*alpha)+')';
  sheet.style.background=bg;
  scrim.style.opacity=String(alpha*0.9);
}

function onUp(){
  if(!drag.active)return;
  drag.active=false;
  sheet.classList.remove('dragging');
  sheet.style.transform='';
  sheet.style.backdropFilter='';
  sheet.style.webkitBackdropFilter='';
  sheet.style.background='';
  scrim.style.opacity='';

  var dy=drag.currentY-drag.startY;
  var movedUp=dy<0;
  var distance=-dy;
  var threshold=sheetH*0.32;
  var velocity=Math.abs(dy);

  if(movedUp && velocity>70){openSheet();return}
  if(movedUp && distance>threshold){openSheet();return}
  closeSheet();
}

sheetHandle.addEventListener('pointerdown',function(e){
  e.preventDefault();
  onDown(e);
  try{sheetHandle.setPointerCapture(e.pointerId)}catch(_){}
});
sheetHandle.addEventListener('pointermove',onMove);
sheetHandle.addEventListener('pointerup',onUp);
sheetHandle.addEventListener('pointercancel',onUp);

composerWrap.addEventListener('pointerdown',function(e){
  if(e.target.closest('#input'))return;
  if(e.target.closest('.attach-btn'))return;
  if(e.target.closest('.font-ctl'))return;
  if(e.target.closest('.theme-slider'))return;
  onDown(e);
});
document.addEventListener('pointermove',onMove);
document.addEventListener('pointerup',onUp);
document.addEventListener('pointercancel',onUp);

scrim.addEventListener('click',closeSheet);

/* Один раз мигнём подсказкой */
(function(){
  if(localStorage.getItem('monolog_handle_seen'))return;
  setTimeout(function(){
    sheetHandle.classList.add('hint-on');
    setTimeout(function(){
      sheetHandle.classList.remove('hint-on');
      localStorage.setItem('monolog_handle_seen','1');
    },2400);
  },900);
})();

/* Верхняя полоса при скролле */
log.addEventListener('scroll',function(){
  if(log.scrollTop>4)topbar.classList.add('scrolled');
  else topbar.classList.remove('scrolled');
});

/* ===== Markdown ===== */
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}

function renderMarkdown(text){
  var codeBlocks=[];
  text=text.replace(/```(\\w*)\\n([\\s\\S]*?)```/g,function(m,lang,code){
    var idx=codeBlocks.length;
    codeBlocks.push({lang:lang||'text',code:code});
    return '\\u0000CODE'+idx+'\\u0000';
  });
  text=esc(text);
  text=text.replace(/`([^`\\n]+)`/g,'<code class="inline">$1</code>');
  text=text.replace(/(^\\|.+\\|\\s*$\\n?)+/gm,function(block){
    var rows=block.trim().split('\\n').filter(function(r){return r.trim()});
    if(rows.length<2)return block;
    var header=rows[0].split('|').slice(1,-1).map(function(s){return s.trim()});
    var sep=rows[1];
    if(!/^[\\s\\|:\\-]+$/.test(sep))return block;
    var html='<table><thead><tr>';
    header.forEach(function(h){html+='<th>'+h+'</th>'});
    html+='</tr></thead><tbody>';
    for(var i=2;i<rows.length;i++){
      var cells=rows[i].split('|').slice(1,-1).map(function(s){return s.trim()});
      html+='<tr>';
      cells.forEach(function(c){html+='<td>'+c+'</td>'});
      html+='</tr>';
    }
    html+='</tbody></table>';
    return html;
  });
  text=text.replace(/^### (.+)$/gm,'<h3>$1</h3>');
  text=text.replace(/^## (.+)$/gm,'<h2>$1</h2>');
  text=text.replace(/^# (.+)$/gm,'<h1>$1</h1>');
  text=text.replace(/^&gt; (.+)$/gm,'<blockquote>$1</blockquote>');
  text=text.replace(/\\*\\*([^*]+)\\*\\*/g,'<strong>$1</strong>');
  text=text.replace(/(?<!\\*)\\*([^*]+)\\*(?!\\*)/g,'<em>$1</em>');
  text=text.replace(/\\[([^\\]]+)\\]\\(([^\\)]+)\\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>');
  text=text.replace(/^---$/gm,'<hr>');
  text=text.replace(/^[-*] (.+)$/gm,'<li>$1</li>');
  text=text.replace(/(<li>[\\s\\S]*?<\\/li>)/g,function(m){return '<ul>'+m+'</ul>'});
  text=text.split(/\\n{2,}/).map(function(chunk){
    if(/^<(h[1-6]|ul|ol|table|blockquote|hr|div)/.test(chunk.trim()))return chunk;
    return '<p>'+chunk.replace(/\\n/g,'<br>')+'</p>';
  }).join('');
  text=text.replace(/\\u0000CODE(\\d+)\\u0000/g,function(m,i){
    var b=codeBlocks[+i];
    var lang=b.lang;
    var isJson=(lang==='json');
    var label=isJson?'JSON':(lang||'CODE').toUpperCase();
    return '<div class="code-block"><span class="lang">'+label+'</span><button class="copy-btn" onclick="copyBlock(this)" title="Копировать" aria-label="Копировать">'+ICON_COPY+'</button><pre><code>'+esc(b.code)+'</code></pre></div>';
  });
  return text;
}

function copyBlock(btn){
  var pre=btn.parentElement.querySelector('pre');
  if(!pre)return;
  var text=pre.innerText;
  if(navigator.clipboard){
    navigator.clipboard.writeText(text).then(function(){
      btn.innerHTML=ICON_CHECK;
      btn.classList.add('copied');
      setTimeout(function(){btn.innerHTML=ICON_COPY;btn.classList.remove('copied')},1400);
    });
  }
}

function addMsg(role,text){
  var d=document.createElement('div');
  d.className='msg '+role;
  if(role==='bot'){d.innerHTML=renderMarkdown(text)}
  else{d.textContent=text}
  log.appendChild(d);
  log.scrollTop=log.scrollHeight;
}

async function send(){
  var text=input.value.trim();
  if(!text)return;
  addMsg('user',text);
  input.value='';
  input.style.height='auto';
  try{
    var r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:text,context:chatHistory})});
    var j=await r.json();
    if(j.ok && j.data && j.data.answer){
      addMsg('bot',j.data.answer);
      chatHistory.push({role:'user',content:text});
      chatHistory.push({role:'assistant',content:j.data.answer});
    }else if(j.error){
      addMsg('bot','**Ошибка:** '+(j.error.message||'неизвестно'));
    }else{
      addMsg('bot','**Ошибка:** пустой ответ');
    }
  }catch(e){
    addMsg('bot','**Ошибка сети:** '+e.message);
  }
}

input.addEventListener('keydown',function(e){
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}
});
input.addEventListener('input',function(){
  this.style.height='auto';
  this.style.height=Math.min(this.scrollHeight,180)+'px';
});
</script>
</body>
</html>"""