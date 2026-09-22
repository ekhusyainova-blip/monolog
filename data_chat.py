# data_chat.py
# Тема: chat
# Папка: A (запрос)

import os
import time
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
<html lang="ru" data-theme="dark" data-density="airy" data-accent="soft">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monolog</title>
<style>
:root[data-theme="dark"]{--bg:#0e0e10;--fg:#e6e6e8;--soft:#a8a8ae;--muted:#6a6a70;--accent:#7fb1ff;--line:#1e1e21}
:root[data-theme="light"]{--bg:#fbfbfc;--fg:#18181a;--soft:#4a4a50;--muted:#8a8a8f;--accent:#2563eb;--line:#e7e7ea}
:root[data-density="airy"]{--lh:1.85;--gap:22px}
:root[data-density="compact"]{--lh:1.55;--gap:14px}
:root[data-accent="sharp"]{--accent:#ff5b5b}
*{box-sizing:border-box;margin:0;padding:0}
body{font:16px/var(--lh) -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--fg);padding:24px;max-width:720px;margin:0 auto}
.slot{margin:0 0 var(--gap)}
.slot-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}
#slot-text{font-size:16px;line-height:var(--lh);white-space:pre-wrap}
#slot-metrics{display:flex;gap:12px;flex-wrap:wrap}
.metric{background:rgba(127,177,255,0.08);border:1px solid var(--line);border-radius:8px;padding:8px 12px;font-size:13px}
.metric .k{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:0.5px}
.metric .v{font-weight:600;margin-top:2px}
.metric .v.ok{color:#6ee7a8}
.metric .v.warn{color:#f4c46a}
.metric .v.bad{color:#f08a8a}
#slot-debug{font:11px/1.5 ui-monospace,monospace;background:#0b0b0d;color:#8a8a8f;padding:10px;border-radius:8px;white-space:pre-wrap;max-height:240px;overflow:auto}
#slot-debug:empty{display:none}
#log{margin-top:32px;border-top:1px solid var(--line);padding-top:16px}
#log .msg{margin-bottom:12px;font-size:14px;color:var(--soft)}
#log .msg strong{color:var(--fg)}
form{margin-top:16px;display:flex;gap:8px;align-items:flex-end}
textarea{flex:1;resize:none;background:transparent;color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:10px;font:inherit;min-height:44px}
button{background:var(--accent);color:#fff;border:none;padding:10px 18px;border-radius:8px;cursor:pointer;font:inherit}
</style>
</head>
<body>

<div class="slot"><div class="slot-label">text</div><div id="slot-text">—</div></div>
<div class="slot"><div class="slot-label">metrics</div><div id="slot-metrics"></div></div>
<div class="slot"><div class="slot-label">debug (output от D)</div><div id="slot-debug"></div></div>

<div id="log"></div>

<form id="form">
  <textarea id="input" rows="1" placeholder="Напиши..."></textarea>
  <button type="submit">Отправить</button>
</form>

<script>
var slotText = document.getElementById('slot-text');
var slotMetrics = document.getElementById('slot-metrics');
var slotDebug = document.getElementById('slot-debug');
var log = document.getElementById('log');
var form = document.getElementById('form');
var input = document.getElementById('input');
var chatHistory = [];

function applyStyle(style){
  if(!style) return;
  var html = document.documentElement;
  if(style.theme)   html.setAttribute('data-theme', style.theme);
  if(style.density) html.setAttribute('data-density', style.density);
  if(style.accent)  html.setAttribute('data-accent', style.accent);
}

function renderMetrics(list){
  slotMetrics.innerHTML = '';
  if(!list || !list.length) return;
  list.forEach(function(m){
    var d = document.createElement('div');
    d.className = 'metric';
    var k = document.createElement('div'); k.className='k'; k.textContent = m.key || '';
    var v = document.createElement('div'); v.className='v ' + (m.status || ''); v.textContent = m.value || '';
    d.appendChild(k); d.appendChild(v);
    slotMetrics.appendChild(d);
  });
}

function renderOutput(output){
  if(!output){ slotText.textContent = '—'; return; }
  if(output.text) slotText.textContent = output.text;
  else slotText.textContent = '—';
  renderMetrics(output.metrics || []);
  applyStyle(output.style || {});
  slotDebug.textContent = JSON.stringify(output, null, 2);
}

function addLog(role, text){
  var d = document.createElement('div');
  d.className = 'msg';
  var b = document.createElement('strong');
  b.textContent = (role === 'user' ? 'Я: ' : 'Monolog: ');
  d.appendChild(b);
  d.appendChild(document.createTextNode(text));
  log.appendChild(d);
}

async function send(){
  var text = input.value.trim();
  if(!text) return;
  addLog('user', text);
  input.value = '';
  try {
    var r = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text: text, context: chatHistory})
    });
    var j = await r.json();
    if(j.ok && j.data && j.data.output){
      renderOutput(j.data.output);
      chatHistory.push({role: 'user', content: text});
      if(j.data.output.text) chatHistory.push({role: 'assistant', content: j.data.output.text});
    } else if(j.error){
      slotText.textContent = '[ошибка] ' + (j.error.message || '');
    } else {
      slotText.textContent = '[ошибка] пустой ответ';
    }
  } catch (e) {
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

# A → B
import interpret_chat