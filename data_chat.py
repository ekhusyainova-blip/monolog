# data_chat.py
# Тема: chat
# Папка: A (запрос)

import os
import json
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

PROVIDERS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "openai/gpt-oss-120b",
        "env": "GROQ_API_KEYS",
    },
}

SETTINGS = {
    "temperature": 0.7,
    "max_tokens": 2048,
    "timeout": 120,
}

def load_keys(name):
    raw = os.getenv(name, "").strip()
    return [k.strip() for k in raw.split(",") if k.strip()] if raw else []

KEYS = {name: load_keys(cfg["env"]) for name, cfg in PROVIDERS.items()}

# ==== Стартер ====
STARTER_PATH = Path(__file__).resolve().parent / "starter.md"

def load_starter():
    try:
        return STARTER_PATH.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[data_chat] starter load error: {e}", flush=True)
        return "Ты — интерфейс отражения восприятия."

STARTER = load_starter()

HANDLERS = {}
EVENTS = []

def on(name):
    def wrap(fn):
        HANDLERS.setdefault(name, []).append(fn)
        return fn
    return wrap

def emit(name, payload):
    for fn in HANDLERS.get(name, []):
        fn(payload)

app = FastAPI(title="Monolog Chat")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {
        "ok": True,
        "status": "alive",
        "providers": {n: len(KEYS.get(n, [])) for n in PROVIDERS},
    }

@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    event = {
        "text": (body.get("text") or "").strip(),
        "context": body.get("context") or [],
        "reflection": body.get("reflection") or "",
        "first_time": bool(body.get("first_time", False)),
    }
    if not event["text"]:
        return JSONResponse(
            {"ok": False, "error": {"code": 400, "class": "validation", "message": "Пустой текст"}},
            status_code=400,
        )
    EVENTS.clear()
    emit("user_message", event)
    if not EVENTS:
        return JSONResponse(
            {"ok": False, "error": {"code": 500, "class": "internal", "message": "Нет ответа"}},
            status_code=500,
        )
    return JSONResponse(EVENTS[-1])

INDEX_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Monolog</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;margin:0;padding:0;overflow:hidden}
body{
  font:17px/1.78 -apple-system,BlinkMacSystemFont,"Inter","SF Pro Text","Segoe UI",Roboto,sans-serif;
  background:#0f0f11;color:#e8e8ea;
  -webkit-font-smoothing:antialiased;letter-spacing:-0.005em;
}

.wrap{
  max-width:680px;margin:0 auto;
  padding:80px 24px 120px;
  height:100%;
  overflow-y:auto;
  -webkit-overflow-scrolling:touch;
  position:relative;
}

/* ==== Сфера ==== */
.sphere-wrap{
  position:fixed;top:18px;left:18px;z-index:20;
  pointer-events:none;
}
.sphere{
  width:26px;height:26px;border-radius:50%;
  position:relative;
  background:radial-gradient(circle at 30% 25%, rgba(255,255,255,0.55), rgba(255,255,255,0.08) 40%, rgba(127,177,255,0.12) 70%, rgba(127,177,255,0.28) 100%);
  backdrop-filter:blur(6px) saturate(160%);
  -webkit-backdrop-filter:blur(6px) saturate(160%);
  box-shadow:
    inset 0 0 8px rgba(255,255,255,0.25),
    inset -2px -2px 6px rgba(127,177,255,0.35),
    0 2px 6px rgba(0,0,0,0.35);
  transition:opacity 0.8s ease, box-shadow 0.8s ease, transform 0.8s ease, filter 0.8s ease, background 0.8s ease;
}
.sphere::after{
  content:'';
  position:absolute;top:18%;left:24%;
  width:30%;height:24%;
  background:radial-gradient(ellipse, rgba(255,255,255,0.85), transparent 70%);
  border-radius:50%;
  filter:blur(1px);
}

@keyframes breathe-slow{0%,100%{transform:scale(1);opacity:0.8}50%{transform:scale(1.06);opacity:0.95}}
@keyframes breathe-fast{0%,100%{transform:scale(1);opacity:0.9}50%{transform:scale(1.16);opacity:1}}
@keyframes flash{0%{transform:scale(1)}40%{transform:scale(1.4);box-shadow:0 0 28px rgba(127,177,255,0.9)}100%{transform:scale(1)}}
@keyframes shaky{0%,100%{transform:translateX(0)}25%{transform:translateX(-1.5px) scale(0.97)}75%{transform:translateX(1.5px) scale(1.03)}}
@keyframes glad{0%,100%{transform:scale(1);filter:brightness(1)}50%{transform:scale(1.14);filter:brightness(1.4)}}
@keyframes ripple{0%{transform:scale(1);opacity:0.9}50%{transform:scale(1.08);opacity:1}100%{transform:scale(1);opacity:0.9}}

.sphere[data-state="clarity"]{box-shadow:inset 0 0 8px rgba(110,231,168,0.5), inset -2px -2px 6px rgba(110,231,168,0.5), 0 0 20px rgba(110,231,168,0.2), 0 2px 6px rgba(0,0,0,0.35)}
.sphere[data-state="search"]{box-shadow:inset 0 0 8px rgba(244,196,106,0.5), inset -2px -2px 6px rgba(244,196,106,0.5), 0 0 20px rgba(244,196,106,0.2), 0 2px 6px rgba(0,0,0,0.35)}
.sphere[data-state="return"]{box-shadow:inset 0 0 8px rgba(240,138,138,0.5), inset -2px -2px 6px rgba(240,138,138,0.5), 0 0 20px rgba(240,138,138,0.2), 0 2px 6px rgba(0,0,0,0.35)}
.sphere[data-state="support"]{box-shadow:inset 0 0 8px rgba(127,177,255,0.55), inset -2px -2px 6px rgba(127,177,255,0.55), 0 0 20px rgba(127,177,255,0.25), 0 2px 6px rgba(0,0,0,0.35)}

.sphere[data-mode="calm"]{animation:breathe-slow 5s ease-in-out infinite}
.sphere[data-mode="think"]{animation:breathe-fast 1.4s ease-in-out infinite}
.sphere[data-mode="say"]{animation:flash 1.3s ease-out}
.sphere[data-mode="idle"]{animation:none;opacity:0.25;filter:grayscale(0.6)}
.sphere[data-mode="warn"]{animation:shaky 0.5s ease-in-out 3;box-shadow:0 0 16px rgba(240,138,138,0.7), inset -2px -2px 6px rgba(240,138,138,0.55)}
.sphere[data-mode="glad"]{animation:glad 1.4s ease-in-out}
.sphere[data-mode="listen"]{animation:ripple 2.2s ease-in-out infinite;box-shadow:0 0 24px rgba(127,177,255,0.5), inset 0 0 12px rgba(255,255,255,0.35)}

#log{display:flex;flex-direction:column;gap:24px}
.msg.bot{
  font-size:var(--text-size, 17px);
  font-style:var(--text-style, normal);
  font-weight:var(--text-weight, 400);
  color:var(--text-color, #e8e8ea);
  line-height:1.78;
  white-space:pre-wrap;word-wrap:break-word;
  animation:fadeIn 0.7s ease;
}
.msg.user{
  align-self:flex-end;max-width:80%;
  color:#8a8a8f;font-size:14px;text-align:right;
  white-space:pre-wrap;word-wrap:break-word;
  animation:fadeIn 0.3s ease, fadeOut 0.8s ease 2s forwards;
  opacity:0.7;
}
.msg.badges{display:flex;gap:8px;flex-wrap:wrap;padding-top:4px}
.badge{
  font-size:12px;color:#a8a8ae;
  padding:4px 10px;
  border:1px solid rgba(255,255,255,0.08);
  border-radius:12px;
  background:rgba(255,255,255,0.03);
}
.badge.accent{border-color:rgba(127,177,255,0.4);color:#7fb1ff}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
@keyframes fadeOut{to{opacity:0;max-height:0;margin:0;padding:0}}
.pulse{display:inline-flex;gap:4px;align-items:center;height:20px}
.pulse span{width:6px;height:6px;border-radius:50%;background:#7fb1ff;animation:pulse 1.4s infinite}
.pulse span:nth-child(2){animation-delay:0.2s}
.pulse span:nth-child(3){animation-delay:0.4s}
@keyframes pulse{0%,100%{opacity:0.25;transform:scale(0.7)}50%{opacity:1;transform:scale(1)}}

form{
  position:fixed;left:0;right:0;bottom:0;
  background:rgba(20,20,24,0.55);
  backdrop-filter:blur(32px) saturate(180%);
  -webkit-backdrop-filter:blur(32px) saturate(180%);
  border-top:1px solid rgba(255,255,255,0.05);
  padding:14px 20px calc(16px + env(safe-area-inset-bottom,0px));
  transition:transform 0.6s cubic-bezier(0.22,1,0.36,1), opacity 0.4s ease;
  will-change:transform;
  z-index:10;
}
form.hidden{transform:translateY(115%);opacity:0}
form.fast{transition:transform 0.25s cubic-bezier(0.4,0,0.2,1), opacity 0.2s ease}
form .inner{max-width:680px;margin:0 auto;display:flex;gap:10px;align-items:flex-end}
textarea{
  flex:1;resize:none;background:transparent;
  color:#e8e8ea;border:none;outline:none;
  padding:10px 4px;font:inherit;font-size:17px;line-height:1.55;
  min-height:44px;max-height:180px;
  white-space:pre-wrap;
  caret-color:#7fb1ff;
}
textarea::placeholder{color:#58585e}
button.send{
  flex-shrink:0;width:40px;height:40px;
  background:#7fb1ff;color:#0f0f11;
  border:none;border-radius:50%;cursor:pointer;padding:0;
  display:flex;align-items:center;justify-content:center;
  transition:opacity 0.15s,transform 0.1s;
}
button.send:hover{opacity:0.9}
button.send:active{transform:scale(0.94)}
button.send:disabled{opacity:0.35;cursor:not-allowed}
button.send svg{width:18px;height:18px;stroke:#0f0f11;fill:none;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
</style>
</head>
<body>

<div class="sphere-wrap">
  <div class="sphere" id="sphere" data-mode="calm"></div>
</div>

<div class="wrap" id="wrap">
  <div id="log"></div>
</div>

<form id="form">
  <div class="inner">
    <textarea id="input" rows="1" placeholder="" autocomplete="off"></textarea>
    <button type="submit" id="send" aria-label="Отправить">
      <svg viewBox="0 0 24 24"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
    </button>
  </div>
</form>

<script>
var log = document.getElementById('log');
var form = document.getElementById('form');
var wrap = document.getElementById('wrap');
var input = document.getElementById('input');
var sendBtn = document.getElementById('send');
var sphere = document.getElementById('sphere');
var chatHistory = [];
var firstTime = true;

// ==== IndexedDB ====
var DB_NAME = 'monolog';
var STORE = 'reflection';

function openDB(){
  return new Promise(function(resolve, reject){
    var req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = function(){
      req.result.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
    };
    req.onsuccess = function(){ resolve(req.result); };
    req.onerror = function(){ reject(req.error); };
  });
}

async function saveReflection(text){
  try{
    var db = await openDB();
    var tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).add({ text: text, ts: Date.now() });
  } catch(e){ console.warn('saveReflection', e); }
}

async function getReflection(){
  try{
    var db = await openDB();
    var tx = db.transaction(STORE, 'readonly');
    var req = tx.objectStore(STORE).getAll();
    return await new Promise(function(resolve){
      req.onsuccess = function(){ resolve(req.result || []); };
      req.onerror = function(){ resolve([]); };
    });
  } catch(e){ return []; }
}

function reflectionToText(items){
  if(!items || !items.length) return '';
  // берём последние 20 записей, собираем в сводку
  var tail = items.slice(-20);
  return 'ОТРАЖЕНИЕ ВОСПРИЯТИЯ\n\n' + tail.map(function(r){ return r.text; }).join('\n\n');
}

// ==== Сфера ====
function setSphereMode(mode){
  if(!mode) return;
  sphere.setAttribute('data-mode', mode);
  if(mode === 'say' || mode === 'glad' || mode === 'warn'){
    setTimeout(function(){
      sphere.setAttribute('data-mode', 'calm');
    }, mode === 'warn' ? 1600 : 1300);
  }
}

function clearLog(){ log.innerHTML = ''; }

function addMsg(role, text){
  var d = document.createElement('div');
  d.className = 'msg ' + role;
  d.textContent = text;
  log.appendChild(d);
  wrap.scrollTop = wrap.scrollHeight;
  return d;
}

function addBadges(items){
  if(!items || !items.length) return;
  var d = document.createElement('div');
  d.className = 'msg badges';
  items.forEach(function(it){
    var b = document.createElement('span');
    b.className = 'badge' + (it.accent ? ' accent' : '');
    b.textContent = it.text;
    d.appendChild(b);
  });
  log.appendChild(d);
}

// ==== Парсер маркеров ====
function extractMarkerJSON(text, name){
  var re = new RegExp('\\\\[' + name + ':\\\\s*(\\\\{[\\\\s\\\\S]*?\\\\})\\\\]', 'i');
  var m = text.match(re);
  if(!m) return { obj: null, text: text };
  try{
    var obj = JSON.parse(m[1]);
    return { obj: obj, text: text.replace(m[0], '').trim() };
  } catch(e){
    return { obj: null, text: text };
  }
}

function parseMarkers(raw){
  var out = {
    clean: raw,
    sphere: null,
    background: null,
    textStyle: null,
    metrics: null,
    state: null,
    route: null,
    routeData: ''
  };
  var r;

  r = extractMarkerJSON(out.clean, 'sphere');     out.sphere = r.obj;     out.clean = r.text;
  r = extractMarkerJSON(out.clean, 'background'); out.background = r.obj; out.clean = r.text;
  r = extractMarkerJSON(out.clean, 'text');       out.textStyle = r.obj;  out.clean = r.text;
  r = extractMarkerJSON(out.clean, 'metrics');    out.metrics = r.obj;    out.clean = r.text;
  r = extractMarkerJSON(out.clean, 'state');      out.state = r.obj;      out.clean = r.text;

  var routeRe = /—\\s*—\\s*—\\s*route:\\s*(\\w+)\\s*—\\s*—\\s*—([\\s\\S]*)$/i;
  var rm = out.clean.match(routeRe);
  if(rm){
    out.route = rm[1].toUpperCase();
    out.routeData = rm[2].trim();
    out.clean = out.clean.slice(0, rm.index);
  }

  out.clean = out.clean.trim();
  return out;
}

// ==== Применение ====
function applySphere(params){
  if(!params) return;
  Object.keys(params).forEach(function(k){
    if(k === 'opacity') sphere.style.opacity = params[k];
    else if(k === 'scale') sphere.style.transform = 'scale(' + params[k] + ')';
    else if(k === 'hue') sphere.style.filter = 'hue-rotate(' + params[k] + 'deg)';
    else if(k === 'blur') sphere.style.filter = (sphere.style.filter || '') + ' blur(' + params[k] + 'px)';
    else if(k === 'glow') sphere.style.boxShadow = '0 0 ' + (params[k] * 40) + 'px rgba(127,177,255,' + params[k] + ')';
    else if(k === 'shift_x') sphere.style.marginLeft = params[k] + 'px';
    else if(k === 'shift_y') sphere.style.marginTop = params[k] + 'px';
    else if(k === 'speed') sphere.style.animationDuration = params[k] + 's';
    else if(k === 'color') sphere.style.background = params[k];
  });
}

function applyBackground(params){
  if(!params) return;
  // фон управляется через body.style, без ::before
  Object.keys(params).forEach(function(k){
    if(k === 'hue') document.body.style.filter = 'hue-rotate(' + params[k] + 'deg)';
    else if(k === 'color') document.body.style.background = params[k];
  });
}

function applyTextStyle(params){
  if(!params) return;
  var root = document.documentElement;
  Object.keys(params).forEach(function(k){
    if(k === 'size') root.style.setProperty('--text-size', params[k] + 'px');
    else if(k === 'italic') root.style.setProperty('--text-style', params[k] ? 'italic' : 'normal');
    else if(k === 'bold') root.style.setProperty('--text-weight', params[k] ? '600' : '400');
    else if(k === 'color') root.style.setProperty('--text-color', params[k]);
  });
}

function applyMetrics(params){
  if(!params) return;
  var items = [];
  Object.keys(params).forEach(function(k){
    items.push({text: k + ': ' + params[k]});
  });
  addBadges(items);
}

function applyState(params){
  if(!params) return;
  if(params.mode){
    sphere.setAttribute('data-state', params.mode);
  }
}

// ==== Отправка ====
async function send(){
  var text = input.value.trim();
  if(!text) return;

  var userMsg = addMsg('user', text);
  setTimeout(function(){ userMsg.remove(); }, 2400);
  input.value = '';
  input.style.height = 'auto';

  clearLog();
  setSphereMode('think');

  var pulse = document.createElement('div');
  pulse.className = 'msg bot';
  pulse.innerHTML = '<span class="pulse"><span></span><span></span><span></span></span>';
  log.appendChild(pulse);

  sendBtn.disabled = true;
  try {
    var reflectionText = firstTime ? reflectionToText(await getReflection()) : '';

    var r = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        text: text,
        context: chatHistory,
        reflection: reflectionText,
        first_time: firstTime
      })
    });
    var j = await r.json();
    pulse.remove();

    if(j.ok && j.data && j.data.output && j.data.output.vars && j.data.output.vars.text){
      var parsed = parseMarkers(j.data.output.vars.text);

      if(parsed.sphere) applySphere(parsed.sphere);
      if(parsed.background) applyBackground(parsed.background);
      if(parsed.textStyle) applyTextStyle(parsed.textStyle);
      if(parsed.metrics) applyMetrics(parsed.metrics);
      if(parsed.state) applyState(parsed.state);
      setSphereMode('say');

      if(parsed.clean) addMsg('bot', parsed.clean);

      chatHistory.push({role: 'user', content: text});
      chatHistory.push({role: 'assistant', content: parsed.clean});
      await saveReflection(parsed.clean);

      firstTime = false;

      if(parsed.route === 'A' && parsed.routeData){
        setSphereMode('think');
        try {
          var r2 = await fetch('/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
              text: parsed.routeData,
              context: chatHistory,
              reflection: '',
              first_time: false
            })
          });
          var j2 = await r2.json();
          if(j2.ok && j2.data && j2.data.output && j2.data.output.vars && j2.data.output.vars.text){
            var p2 = parseMarkers(j2.data.output.vars.text);
            if(p2.clean) addMsg('bot', p2.clean);
            if(p2.sphere) applySphere(p2.sphere);
            if(p2.state) applyState(p2.state);
            chatHistory.push({role: 'assistant', content: p2.clean});
            await saveReflection(p2.clean);
          }
        } catch(e2){}
      }
    } else if(j.error){
      setSphereMode('warn');
    } else {
      setSphereMode('idle');
    }
  } catch(e){
    pulse.remove();
    setSphereMode('warn');
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

// ==== Скролл: ввод уезжает/появляется ====
var lastScroll = 0;
wrap.addEventListener('scroll', function(){
  var y = wrap.scrollTop;
  var focused = document.activeElement === input;
  if(y > lastScroll && y > 60 && !focused){
    form.classList.add('hidden');
  } else if(y < lastScroll - 10 || y < 30){
    form.classList.remove('hidden');
  }
  lastScroll = y;
}, { passive: true });

document.addEventListener('click', function(e){
  if(e.target.closest('form') || e.target.closest('.sphere-wrap')) return;
  if(e.target.closest('.msg')) return;
  if(!form.classList.contains('hidden')){
    form.classList.add('fast');
    form.classList.add('hidden');
    setTimeout(function(){ form.classList.remove('fast'); }, 300);
  } else {
    form.classList.remove('hidden');
    form.classList.add('fast');
    setTimeout(function(){ form.classList.remove('fast'); }, 300);
    input.focus();
  }
});

form.addEventListener('submit', function(e){ e.preventDefault(); send(); });
input.addEventListener('keydown', function(e){
  if(e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); send(); }
});
input.addEventListener('input', function(){
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 180) + 'px';
});
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML

import interpret_chat