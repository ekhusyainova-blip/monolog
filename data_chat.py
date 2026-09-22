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
        "model": "openai/gpt-oss-20b",
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
        "content_mode": bool(body.get("content_mode")),
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
<html lang="ru" data-theme="dark" data-density="airy" data-accent="soft" data-font="sans" data-layout="narrow">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monolog</title>
<style>
:root[data-theme="dark"]{--bg:#0e0e10;--fg:#e6e6e8;--soft:#a8a8ae;--muted:#6a6a70;--line:#1e1e21;--accent:#7fb1ff}
:root[data-theme="light"]{--bg:#fbfbfc;--fg:#18181a;--soft:#4a4a50;--muted:#8a8a8f;--line:#e7e7ea;--accent:#2563eb}
:root[data-density="airy"]{--lh:1.85;--gap:22px}
:root[data-density="compact"]{--lh:1.55;--gap:14px}
:root[data-accent="sharp"]{--accent:#ff5b5b}
:root[data-font="serif"]{--font:Georgia,serif}
:root[data-font="sans"]{--font:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
:root[data-font="mono"]{--font:ui-monospace,Menlo,monospace}
:root[data-layout="wide"]{--maxw:960px}
:root[data-layout="narrow"]{--maxw:720px}
*{box-sizing:border-box;margin:0;padding:0}
body{font:16px/var(--lh) var(--font);background:var(--bg);color:var(--fg);padding:20px;max-width:var(--maxw);margin:0 auto}
.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;padding-bottom:12px;border-bottom:1px solid var(--line)}
.topbar .left{display:flex;gap:8px;align-items:center}
.topbar .right{display:flex;gap:8px}
.badge{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px;padding:3px 8px;border:1px solid var(--line);border-radius:6px}
.badge.accent{border-color:var(--accent);color:var(--accent)}
.btn{background:none;border:1px solid var(--line);color:var(--soft);font-size:13px;padding:5px 10px;border-radius:6px;cursor:pointer;font-family:inherit}
.btn:hover{color:var(--fg);border-color:var(--accent)}
.slot{margin:0 0 var(--gap)}
.slot-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:center}
.slot-label .toggle{font-size:10px;cursor:pointer;color:var(--muted)}
.slot-label .toggle:hover{color:var(--fg)}
#slot-text{font-size:16px;line-height:var(--lh);white-space:pre-wrap;min-height:20px}
#slot-text:empty::before{content:'—';color:var(--muted)}
.state-grid{display:flex;gap:10px;flex-wrap:wrap}
.state-pill{border:1px solid var(--line);padding:4px 10px;border-radius:12px;font-size:12px;color:var(--soft)}
.state-pill.active{border-color:var(--accent);color:var(--accent)}
.metrics{display:flex;gap:12px;flex-wrap:wrap}
.metric{background:rgba(127,177,255,0.06);border:1px solid var(--line);border-radius:8px;padding:8px 12px;font-size:13px;position:relative}
.metric .k{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:0.5px}
.metric .v{font-weight:600;margin-top:2px}
.metric .save{position:absolute;top:4px;right:4px;font-size:10px;color:var(--muted);cursor:pointer;opacity:0.5;background:none;border:none;padding:2px 4px}
.metric .save:hover{opacity:1;color:var(--accent)}
.metric .save.saved{color:var(--accent);opacity:1}
#slot-extra .row{padding:4px 0;border-bottom:1px solid var(--line);font-size:13px;color:var(--soft)}
#slot-extra .row .k{color:var(--muted);margin-right:8px}
#slot-debug{font:11px/1.5 ui-monospace,monospace;background:#0b0b0d;color:#8a8a8f;padding:10px;border-radius:8px;white-space:pre-wrap;max-height:280px;overflow:auto}
#slot-debug.collapsed{display:none}
#log{display:flex;flex-direction:column;gap:6px;font-size:13px;color:var(--soft);margin-top:10px}
#log.collapsed{display:none}
#log .msg strong{color:var(--fg);margin-right:6px}
#log .msg.user{color:var(--muted)}
.pulse{width:8px;height:8px;border-radius:50%;background:var(--accent);display:inline-block;animation:pulse 1.4s infinite}
@keyframes pulse{0%,100%{opacity:0.3;transform:scale(0.8)}50%{opacity:1;transform:scale(1)}}
form{display:flex;gap:8px;align-items:flex-end;margin-top:16px}
textarea{flex:1;resize:none;background:transparent;color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:10px;font:inherit;min-height:44px;max-height:180px}
textarea:focus{outline:none;border-color:var(--accent)}
button.send{background:var(--accent);color:#fff;border:none;padding:10px 18px;border-radius:8px;cursor:pointer;font-family:inherit}
</style>
</head>
<body>

<div class="topbar">
  <div class="left" id="slot-state">
    <span class="badge" data-state="clarity">ясность</span>
    <span class="badge" data-state="search">поиск</span>
    <span class="badge" data-state="return">возврат</span>
    <span class="badge" data-state="support">сопровождение</span>
  </div>
  <div class="right">
    <button class="btn" onclick="resetAll()">Сброс</button>
    <button class="btn" onclick="toggleHistory()">История</button>
  </div>
</div>

<div class="slot">
  <div class="slot-label">Отражение</div>
  <div id="slot-reflection"><span class="state-pill">не вижу</span></div>
</div>

<div class="slot">
  <div class="slot-label">Полезность</div>
  <div id="slot-usefulness"><span class="state-pill">—</span></div>
</div>

<div class="slot">
  <div class="slot-label">Ответ</div>
  <div id="slot-text"></div>
</div>

<div class="slot">
  <div class="slot-label">Метрики</div>
  <div class="metrics" id="slot-metrics"></div>
</div>

<div class="slot">
  <div class="slot-label">Дополнительно</div>
  <div id="slot-extra"></div>
</div>

<div class="slot">
  <div class="slot-label">
    <span>Отладка</span>
    <span class="toggle" onclick="toggleDebug()">показать</span>
  </div>
  <div id="slot-debug" class="collapsed"></div>
</div>

<div class="slot">
  <div class="slot-label">Ход диалога</div>
  <div id="log" class="collapsed"></div>
</div>

<form id="form">
  <textarea id="input" rows="1" placeholder="Напиши..."></textarea>
  <button class="send" type="submit">Отправить</button>
</form>

<script>
var $ = function(id){ return document.getElementById(id); };
var slotText = $('slot-text');
var slotMetrics = $('slot-metrics');
var slotExtra = $('slot-extra');
var slotDebug = $('slot-debug');
var slotState = $('slot-state');
var slotReflection = $('slot-reflection');
var slotUsefulness = $('slot-usefulness');
var log = $('log');
var form = $('form');
var input = $('input');
var chatHistory = [];

var KNOWN = ['text','state','reflection','usefulness','metrics','style','theme','density','accent','font','layout','routes','silence','prompts_new','a_content'];

function applyStyle(v){
  if(!v) return;
  var h = document.documentElement;
  var s = v.style || {};
  var theme = v.theme || s.theme;
  var density = v.density || s.density;
  var accent = v.accent || s.accent;
  var font = v.font || s.font;
  var layout = v.layout || s.layout;
  if(theme) h.setAttribute('data-theme', theme);
  if(density) h.setAttribute('data-density', density);
  if(accent) h.setAttribute('data-accent', accent);
  if(font) h.setAttribute('data-font', font);
  if(layout) h.setAttribute('data-layout', layout);
}

function setState(state){
  slotState.querySelectorAll('.badge').forEach(function(b){
    b.classList.toggle('active', b.getAttribute('data-state') === state);
  });
}

function setReflection(value){
  if(!value){ slotReflection.innerHTML = '<span class="state-pill">не вижу</span>'; return; }
  slotReflection.innerHTML = '<span class="state-pill active">' + value + '</span>';
}

function setUsefulness(value){
  if(value === undefined || value === null){ slotUsefulness.innerHTML = '<span class="state-pill">—</span>'; return; }
  slotUsefulness.innerHTML = '<span class="state-pill active">' + value + '</span>';
}

function renderMetrics(list){
  slotMetrics.innerHTML = '';
  if(!Array.isArray(list) || !list.length) return;
  list.forEach(function(m){
    var d = document.createElement('div');
    d.className = 'metric';
    var k = document.createElement('div'); k.className='k'; k.textContent = m.key || '';
    var v = document.createElement('div'); v.className='v'; v.textContent = m.value || '';
    var s = document.createElement('button'); s.className='save'; s.textContent = 'сохранить';
    s.onclick = function(){
      var saved = JSON.parse(localStorage.getItem('monolog_saved_metrics') || '[]');
      saved.push({key: m.key, value: m.value, ts: Date.now()});
      localStorage.setItem('monolog_saved_metrics', JSON.stringify(saved));
      s.classList.add('saved');
      s.textContent = 'сохранено';
    };
    d.appendChild(k); d.appendChild(v); d.appendChild(s);
    slotMetrics.appendChild(d);
  });
}

function renderExtra(v){
  slotExtra.innerHTML = '';
  if(!v) return;
  Object.keys(v).forEach(function(k){
    if(KNOWN.indexOf(k) >= 0) return;
    var row = document.createElement('div');
    row.className = 'row';
    row.innerHTML = '<span class="k">' + k + '</span>' + String(v[k]);
    slotExtra.appendChild(row);
  });
}

function addLog(role, text){
  var d = document.createElement('div');
  d.className = 'msg ' + role;
  d.innerHTML = '<strong>' + (role === 'user' ? 'Я:' : 'Monolog:') + '</strong>' + escapeHtml(text);
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

function escapeHtml(s){
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function renderOutput(out){
  if(!out) return;
  var v = out.vars || {};
  if(out.silence){
    slotText.textContent = '';
    slotMetrics.innerHTML = '';
    slotExtra.innerHTML = '';
    return;
  }
  slotText.textContent = v.text || '';
  if(v.state) setState(v.state);
  if(v.reflection) setReflection(v.reflection);
  if(v.usefulness !== undefined) setUsefulness(v.usefulness);
  renderMetrics(v.metrics);
  renderExtra(v);
  applyStyle(v);
  slotDebug.textContent = JSON.stringify(out, null, 2);
}

function resetAll(){
  chatHistory = [];
  slotText.textContent = '';
  slotMetrics.innerHTML = '';
  slotExtra.innerHTML = '';
  slotDebug.textContent = '';
  log.innerHTML = '';
  setReflection(null);
  setUsefulness(null);
  setState(null);
}

function toggleDebug(){
  slotDebug.classList.toggle('collapsed');
  var t = slotDebug.previousElementSibling.querySelector('.toggle');
  t.textContent = slotDebug.classList.contains('collapsed') ? 'показать' : 'скрыть';
}

function toggleHistory(){
  log.classList.toggle('collapsed');
}

async function send(){
  var text = input.value.trim();
  if(!text) return;
  addLog('user', text);
  input.value = '';
  var pulse = document.createElement('span');
  pulse.className = 'pulse';
  slotText.innerHTML = '';
  slotText.appendChild(pulse);
  try {
    var r = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text: text, context: chatHistory})
    });
    var j = await r.json();
    slotText.innerHTML = '';
    if(j.ok && j.data && j.data.output){
      renderOutput(j.data.output);
      chatHistory.push({role: 'user', content: text});
      var v = j.data.output.vars || {};
      if(v.text){
        chatHistory.push({role: 'assistant', content: v.text});
        addLog('bot', v.text);
      }
    } else if(j.error){
      slotText.textContent = '[ошибка] ' + (j.error.message || '');
    } else {
      slotText.textContent = '[ошибка] пустой ответ';
    }
  } catch(e){
    slotText.textContent = '[ошибка сети] ' + e.message;
  }
}

form.addEventListener('submit', function(e){
  e.preventDefault();
  send();
});
input.addEventListener('keydown', function(e){
  if(e.key === 'Enter' && !e.shiftKey){
    e.preventDefault();
    send();
  }
});
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML

import interpret_chat