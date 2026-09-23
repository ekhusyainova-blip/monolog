# data_chat.py
# Тема: chat
# Папка: A (запрос)

import os
import time
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
    "cooldown_sec": 65,
}

def load_keys(name):
    raw = os.getenv(name, "").strip()
    return [k.strip() for k in raw.split(",") if k.strip()] if raw else []

KEYS = {name: load_keys(cfg["env"]) for name, cfg in PROVIDERS.items()}

PROMPTS_PATH = Path(__file__).resolve().parent / "prompts_chat.json"

def load_prompts():
    try:
        data = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
        return data.get("prompts", {})
    except Exception as e:
        print(f"[data_chat] prompts load error: {e}", flush=True)
        return {
            "layer_a": "Ты — Monolog.",
            "layer_b": "Ты — Monolog.",
            "layer_c": "Ты — Monolog.",
            "layer_d": "Ты — Monolog.",
            "layer_a_content": "Ты — Monolog, другой голос.",
        }

PROMPTS = load_prompts()

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
html,body{height:100%}
body{
  font:17px/1.78 -apple-system,BlinkMacSystemFont,"Inter","SF Pro Text","Segoe UI",Roboto,sans-serif;
  background:#0f0f11;color:#e8e8ea;
  -webkit-font-smoothing:antialiased;letter-spacing:-0.005em;
  overflow:hidden;
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
  transition:opacity 0.6s ease, box-shadow 0.6s ease;
}
.sphere::after{
  content:'';
  position:absolute;top:18%;left:24%;
  width:30%;height:24%;
  background:radial-gradient(ellipse, rgba(255,255,255,0.85), transparent 70%);
  border-radius:50%;
  filter:blur(1px);
}

@keyframes breathe{
  0%,100%{transform:scale(1);opacity:0.85}
  50%{transform:scale(1.08);opacity:1}
}
@keyframes spin{
  0%{transform:scale(1)}
  50%{transform:scale(1.15)}
  100%{transform:scale(1)}
}
@keyframes flash{
  0%{transform:scale(1);opacity:1}
  40%{transform:scale(1.35);opacity:1;box-shadow:0 0 24px rgba(127,177,255,0.9)}
  100%{transform:scale(1);opacity:0.85;box-shadow:none}
}
@keyframes shaky{
  0%,100%{transform:translateX(0) scale(1)}
  25%{transform:translateX(-1px) scale(0.98)}
  75%{transform:translateX(1px) scale(1.02)}
}
@keyframes glad{
  0%,100%{transform:scale(1);filter:brightness(1)}
  50%{transform:scale(1.12);filter:brightness(1.35)}
}

.sphere[data-state="clarity"]{box-shadow:inset 0 0 8px rgba(110,231,168,0.4), inset -2px -2px 6px rgba(110,231,168,0.45), 0 2px 6px rgba(0,0,0,0.35)}
.sphere[data-state="search"]{box-shadow:inset 0 0 8px rgba(244,196,106,0.4), inset -2px -2px 6px rgba(244,196,106,0.45), 0 2px 6px rgba(0,0,0,0.35)}
.sphere[data-state="return"]{box-shadow:inset 0 0 8px rgba(240,138,138,0.4), inset -2px -2px 6px rgba(240,138,138,0.45), 0 2px 6px rgba(0,0,0,0.35)}
.sphere[data-state="support"]{box-shadow:inset 0 0 8px rgba(127,177,255,0.5), inset -2px -2px 6px rgba(127,177,255,0.55), 0 2px 6px rgba(0,0,0,0.35)}

.sphere[data-mode="calm"]{animation:breathe 4.5s ease-in-out infinite}
.sphere[data-mode="think"]{animation:spin 1.1s ease-in-out infinite;opacity:0.95}
.sphere[data-mode="say"]{animation:flash 1.2s ease-out}
.sphere[data-mode="idle"]{animation:none;opacity:0.3;filter:grayscale(0.4)}
.sphere[data-mode="warn"]{animation:shaky 0.5s ease-in-out 3;box-shadow:0 0 16px rgba(240,138,138,0.7), inset -2px -2px 6px rgba(240,138,138,0.55)}
.sphere[data-mode="glad"]{animation:glad 1.4s ease-in-out}

/* ==== Лента — один ответ ==== */
.wrap{
  max-width:680px;margin:0 auto;
  padding:80px 24px 200px;min-height:100vh;
}
#log{display:flex;flex-direction:column;gap:24px}
.msg.bot{
  font-size:17px;line-height:1.78;
  white-space:pre-wrap;word-wrap:break-word;
  animation:fadeIn 0.6s ease;
}
.msg.user{
  align-self:flex-end;max-width:80%;
  color:#8a8a8f;font-size:14px;text-align:right;
  white-space:pre-wrap;word-wrap:break-word;
  animation:fadeIn 0.3s ease, fadeOut 0.6s ease 1.8s forwards;
  opacity:0.7;
}
.msg.cycle{
  border-left:2px solid #7fb1ff;padding-left:12px;
  color:#8a8a8f;font-size:15px;
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

/* ==== Нижняя плашка — матовое стекло ==== */
form{
  position:fixed;left:0;right:0;bottom:0;
  background:rgba(20,20,24,0.55);
  backdrop-filter:blur(32px) saturate(180%);
  -webkit-backdrop-filter:blur(32px) saturate(180%);
  border-top:1px solid rgba(255,255,255,0.05);
  padding:14px 20px calc(16px + env(safe-area-inset-bottom,0px));
  transition:transform 0.35s cubic-bezier(0.4,0,0.2,1);
}
form.hidden{transform:translateY(110%)}
form .inner{
  max-width:680px;margin:0 auto;
  display:flex;gap:10px;align-items:flex-end;
}
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

<div class="wrap">
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
var input = document.getElementById('input');
var sendBtn = document.getElementById('send');
var sphere = document.getElementById('sphere');
var chatHistory = [];

// ==== Состояние сферы ====
function setState(state){
  if(state){
    sphere.setAttribute('data-state', state);
  } else {
    sphere.removeAttribute('data-state');
  }
}

function setSphereMode(mode){
  if(!mode) return;
  sphere.setAttribute('data-mode', mode);
  if(mode === 'say' || mode === 'glad' || mode === 'warn'){
    setTimeout(function(){
      sphere.setAttribute('data-mode', 'calm');
    }, mode === 'warn' ? 1600 : 1300);
  }
}

// ==== Лента ====
function clearLog(){ log.innerHTML = ''; }

function addMsg(role, text){
  var d = document.createElement('div');
  d.className = 'msg ' + role;
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
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

// ==== Маркеры ====
function parseMarkers(text){
  var out = { clean: text, state: null, reflection: null, usefulness: null, route: null, routeData: '', sphere: null };
  text = text.replace(/\\[state:\\s*(\\w+)\\]/gi, function(_, s){ out.state = s.toLowerCase(); return ''; });
  text = text.replace(/\\[reflection:\\s*([^\\]]+)\\]/gi, function(_, s){ out.reflection = s.trim(); return ''; });
  text = text.replace(/\\[usefulness:\\s*([^\\]]+)\\]/gi, function(_, s){ out.usefulness = s.trim(); return ''; });

  var mSphere = text.match(/\\[sphere:\\s*(\\w+)\\]/i);
  if(mSphere){
    out.sphere = mSphere[1].toLowerCase();
    text = text.replace(/\\[sphere:\\s*\\w+\\]/i, '');
  }

  var routeRe = /—\\s*—\\s*—\\s*route:\\s*(\\w+)\\s*—\\s*—\\s*—([\\s\\S]*)$/i;
  var m = text.match(routeRe);
  if(m){
    out.route = m[1].toUpperCase();
    out.routeData = m[2].trim();
    text = text.slice(0, m.index);
  }
  out.clean = text.trim();
  return out;
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
    var r = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text: text, context: chatHistory})
    });
    var j = await r.json();
    pulse.remove();

    if(j.ok && j.data && j.data.output && j.data.output.vars && j.data.output.vars.text){
      var raw = j.data.output.vars.text;
      var parsed = parseMarkers(raw);

      if(parsed.state) setState(parsed.state);
      if(parsed.sphere) setSphereMode(parsed.sphere);
      else setSphereMode('say');

      if(parsed.clean) addMsg('bot', parsed.clean);

      var items = [];
      if(parsed.reflection) items.push({text: 'отражение: ' + parsed.reflection, accent: true});
      if(parsed.usefulness) items.push({text: 'полезность: ' + parsed.usefulness});
      if(items.length) addBadges(items);

      chatHistory.push({role: 'user', content: text});
      chatHistory.push({role: 'assistant', content: parsed.clean});

      if(parsed.route === 'A' && parsed.routeData){
        addMsg('cycle', '↻ Monolog продолжил: ' + parsed.routeData);
        setSphereMode('think');
        try {
          var r2 = await fetch('/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({text: parsed.routeData, context: chatHistory})
          });
          var j2 = await r2.json();
          if(j2.ok && j2.data && j2.data.output && j2.data.output.vars && j2.data.output.vars.text){
            var p2 = parseMarkers(j2.data.output.vars.text);
            if(p2.clean) addMsg('bot', p2.clean);
            if(p2.state) setState(p2.state);
            if(p2.sphere) setSphereMode(p2.sphere);
            else setSphereMode('say');
            chatHistory.push({role: 'assistant', content: p2.clean});
          }
        } catch(e2){}
      }
    } else if(j.error){
      setSphereMode('warn');
      addMsg('bot', '[тихо] Monolog сейчас не отвечает.');
    } else {
      setSphereMode('idle');
      addMsg('bot', '[тихо] Monolog молчит.');
    }
  } catch(e){
    pulse.remove();
    setSphereMode('warn');
    addMsg('bot', '[тихо] Monolog не отвечает.');
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

// ==== Укатывание ввода ====
var lastScroll = 0;
document.addEventListener('scroll', function(){
  var y = window.scrollY || document.documentElement.scrollTop;
  if(y > lastScroll && y > 60 && document.activeElement !== input){
    form.classList.add('hidden');
  } else if(y < lastScroll - 10 || y < 30){
    form.classList.remove('hidden');
  }
  lastScroll = y;
}, { passive: true });

document.addEventListener('click', function(e){
  if(e.target.closest('form') || e.target.closest('.sphere-wrap')) return;
  if(e.target.closest('.msg')) return;
  form.classList.toggle('hidden');
  if(!form.classList.contains('hidden')) input.focus();
});

// ==== Обработчики ====
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