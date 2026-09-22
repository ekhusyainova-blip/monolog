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
  font:17px/1.75 -apple-system,BlinkMacSystemFont,"Inter","SF Pro Text","Segoe UI",Roboto,sans-serif;
  background:#0f0f11;color:#e8e8ea;
  -webkit-font-smoothing:antialiased;letter-spacing:-0.005em;
}
.topbar{
  position:sticky;top:0;z-index:10;
  background:rgba(15,15,17,0.72);
  backdrop-filter:blur(20px) saturate(180%);
  -webkit-backdrop-filter:blur(20px) saturate(180%);
  border-bottom:1px solid rgba(255,255,255,0.05);
  padding:10px 20px;display:flex;align-items:center;justify-content:space-between;
}
.topbar .state{display:flex;gap:6px;align-items:center}
.state-dot{width:9px;height:9px;border-radius:50%;background:#58585e;display:inline-block;transition:background 0.3s}
.state-dot[data-state="clarity"]{background:#6ee7a8}
.state-dot[data-state="search"]{background:#f4c46a}
.state-dot[data-state="return"]{background:#f08a8a}
.state-dot[data-state="support"]{background:#7fb1ff}
.state-label{font-size:11px;color:#8a8a8f;letter-spacing:0.3px}
.topbar .right{display:flex;gap:2px;align-items:center}
.icon-btn{background:none;border:none;color:#8a8a8f;font-size:16px;padding:6px 8px;cursor:pointer;border-radius:6px;line-height:1;font-family:inherit}
.icon-btn:hover{color:#e8e8ea;background:rgba(255,255,255,0.05)}
.badges{display:flex;gap:6px;flex-wrap:wrap;padding:8px 20px;font-size:12px;color:#8a8a8f;border-bottom:1px solid rgba(255,255,255,0.03)}
.badges:empty{display:none}
.badge{padding:3px 8px;border:1px solid rgba(255,255,255,0.08);border-radius:10px}
.badge.accent{border-color:#7fb1ff;color:#7fb1ff}
.wrap{max-width:680px;margin:0 auto;padding:24px 24px 160px;min-height:100vh}
#log{display:flex;flex-direction:column;gap:32px}
.msg.bot{font-size:17px;line-height:1.78;white-space:pre-wrap;word-wrap:break-word;animation:fadeIn 0.5s ease}
.msg.user{
  align-self:flex-end;max-width:82%;
  background:rgba(255,255,255,0.055);border:1px solid rgba(255,255,255,0.07);
  backdrop-filter:blur(14px) saturate(140%);-webkit-backdrop-filter:blur(14px) saturate(140%);
  border-radius:16px;padding:10px 14px;font-size:15px;line-height:1.55;color:#a8a8ae;
  white-space:pre-wrap;word-wrap:break-word;animation:fadeIn 0.3s ease;
}
.msg.cycle{border-left:2px solid #7fb1ff;padding-left:12px;color:#8a8a8f;font-size:15px}
@keyframes fadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
.pulse{display:inline-flex;gap:4px;align-items:center;height:20px}
.pulse span{width:6px;height:6px;border-radius:50%;background:#7fb1ff;animation:pulse 1.4s infinite}
.pulse span:nth-child(2){animation-delay:0.2s}
.pulse span:nth-child(3){animation-delay:0.4s}
@keyframes pulse{0%,100%{opacity:0.25;transform:scale(0.7)}50%{opacity:1;transform:scale(1)}}
form{
  position:fixed;left:0;right:0;bottom:0;
  background:rgba(15,15,17,0.72);backdrop-filter:blur(28px) saturate(180%);
  -webkit-backdrop-filter:blur(28px) saturate(180%);
  border-top:1px solid rgba(255,255,255,0.05);
  padding:12px 20px calc(14px + env(safe-area-inset-bottom,0px));
}
form .inner{max-width:680px;margin:0 auto;display:flex;gap:10px;align-items:flex-end}
textarea{flex:1;resize:none;background:transparent;color:#e8e8ea;border:none;outline:none;padding:10px 4px;font:inherit;font-size:17px;line-height:1.55;min-height:44px;max-height:200px;white-space:pre-wrap}
textarea::placeholder{color:#58585e}
button.send{
  flex-shrink:0;width:40px;height:40px;background:#7fb1ff;color:#0f0f11;
  border:none;border-radius:50%;cursor:pointer;padding:0;
  display:flex;align-items:center;justify-content:center;
  transition:opacity 0.15s,transform 0.1s;
}
button.send:hover{opacity:0.9}
button.send:active{transform:scale(0.94)}
button.send:disabled{opacity:0.35;cursor:not-allowed}
button.send svg{width:18px;height:18px;stroke:#0f0f11;fill:none;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
.sheet{position:fixed;inset:0;background:rgba(15,15,17,0.94);backdrop-filter:blur(28px);-webkit-backdrop-filter:blur(28px);z-index:50;display:none;flex-direction:column}
.sheet.open{display:flex}
.sheet-header{padding:16px 20px;border-bottom:1px solid rgba(255,255,255,0.05);display:flex;justify-content:space-between;align-items:center}
.sheet-body{padding:16px 20px;overflow-y:auto;max-width:680px;margin:0 auto;width:100%}
.history-item{padding:12px 14px;border:1px solid rgba(255,255,255,0.06);border-radius:10px;margin-bottom:8px;cursor:pointer}
.history-item:hover{border-color:#7fb1ff}
.history-item .who{font-size:11px;color:#8a8a8f;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px}
.history-item .what{font-size:14px;color:#a8a8ae;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
</style>
</head>
<body>

<div class="topbar">
  <div class="state">
    <span class="state-dot" id="stateDot"></span>
    <span class="state-label" id="stateLabel">Monolog</span>
  </div>
  <div class="right">
    <button class="icon-btn" onclick="openSheet()" title="история">☰</button>
    <button class="icon-btn" onclick="resetAll()" title="сброс">⟲</button>
  </div>
</div>

<div class="badges" id="badges"></div>

<div class="wrap">
  <div id="log"></div>
</div>

<form id="form">
  <div class="inner">
    <textarea id="input" rows="1" placeholder="Напиши..." autocomplete="off"></textarea>
    <button type="submit" id="send" aria-label="Отправить">
      <svg viewBox="0 0 24 24"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
    </button>
  </div>
</form>

<div class="sheet" id="sheet">
  <div class="sheet-header">
    <span style="color:#8a8a8f;font-size:13px">История</span>
    <button class="icon-btn" onclick="closeSheet()">✕</button>
  </div>
  <div class="sheet-body" id="historyBody"></div>
</div>

<script>
var log = document.getElementById('log');
var form = document.getElementById('form');
var input = document.getElementById('input');
var sendBtn = document.getElementById('send');
var stateDot = document.getElementById('stateDot');
var stateLabel = document.getElementById('stateLabel');
var badges = document.getElementById('badges');
var sheet = document.getElementById('sheet');
var historyBody = document.getElementById('historyBody');

var chatHistory = [];
var DB_NAME = 'monolog';
var DB_STORE = 'sessions';
var db = null;

// ============ IndexedDB ============
function openDB(){
  return new Promise(function(resolve, reject){
    var req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = function(e){
      var d = e.target.result;
      if(!d.objectStoreNames.contains(DB_STORE)){
        d.createObjectStore(DB_STORE, {keyPath: 'id', autoIncrement: true});
      }
    };
    req.onsuccess = function(e){ db = e.target.result; resolve(db); };
    req.onerror = function(e){ reject(e); };
  });
}

function saveSession(history){
  if(!db) return;
  var tx = db.transaction(DB_STORE, 'readwrite');
  tx.objectStore(DB_STORE).add({ts: Date.now(), history: history});
}

function listSessions(){
  return new Promise(function(resolve){
    if(!db) return resolve([]);
    var tx = db.transaction(DB_STORE, 'readonly');
    var req = tx.objectStore(DB_STORE).getAll();
    req.onsuccess = function(){ resolve(req.result || []); };
    req.onerror = function(){ resolve([]); };
  });
}

function clearSessions(){
  if(!db) return;
  var tx = db.transaction(DB_STORE, 'readwrite');
  tx.objectStore(DB_STORE).clear();
}

// ============ Рендер ============
function addMsg(role, text){
  var d = document.createElement('div');
  d.className = 'msg ' + role;
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

function setState(state){
  if(state){
    stateDot.setAttribute('data-state', state);
    stateLabel.textContent = ({
      clarity: 'ясность', search: 'поиск', return: 'возврат', support: 'сопровождение'
    })[state] || 'Monolog';
  } else {
    stateDot.removeAttribute('data-state');
    stateLabel.textContent = 'Monolog';
  }
}

function setBadges(items){
  badges.innerHTML = '';
  if(!items || !items.length) return;
  items.forEach(function(it){
    var b = document.createElement('span');
    b.className = 'badge' + (it.accent ? ' accent' : '');
    b.textContent = it.text;
    badges.appendChild(b);
  });
}

// ============ Маркеры в тексте ============
function parseMarkers(text){
  var out = { clean: text, state: null, reflection: null, usefulness: null, route: null, routeData: '' };
  // [state: search]
  text = text.replace(/\\[state:\\s*(\\w+)\\]/gi, function(_, s){ out.state = s.toLowerCase(); return ''; });
  // [reflection: не вижу]
  text = text.replace(/\\[reflection:\\s*([^\\]]+)\\]/gi, function(_, s){ out.reflection = s.trim(); return ''; });
  // [usefulness: 3/5]
  text = text.replace(/\\[usefulness:\\s*([^\\]]+)\\]/gi, function(_, s){ out.usefulness = s.trim(); return ''; });
  // route
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

// ============ Отправка ============
async function send(){
  var text = input.value.trim();
  if(!text) return;
  addMsg('user', text);
  input.value = '';
  input.style.height = 'auto';

  var pulse = document.createElement('div');
  pulse.className = 'msg bot';
  pulse.innerHTML = '<span class="pulse"><span></span><span></span><span></span></span>';
  log.appendChild(pulse);
  log.scrollTop = log.scrollHeight;

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

      // метрики и состояние
      if(parsed.state) setState(parsed.state);
      var items = [];
      if(parsed.reflection) items.push({text: 'отражение: ' + parsed.reflection, accent: true});
      if(parsed.usefulness) items.push({text: 'полезность: ' + parsed.usefulness});
      setBadges(items);

      if(parsed.clean) addMsg('bot', parsed.clean);

      chatHistory.push({role: 'user', content: text});
      chatHistory.push({role: 'assistant', content: parsed.clean});

      // D → A маршрут
      if(parsed.route === 'A' && parsed.routeData){
        addMsg('cycle', '↻ Monolog продолжил: ' + parsed.routeData);
        // второй цикл — отправляем в A
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
            chatHistory.push({role: 'assistant', content: p2.clean});
          }
        } catch(e2){}
      }

      // сохраняем сессию
      saveSession(chatHistory);
    } else if(j.error){
      addMsg('bot', '[ошибка] ' + (j.error.message || ''));
    } else {
      addMsg('bot', '[ошибка] пустой ответ');
    }
  } catch(e){
    pulse.remove();
    addMsg('bot', '[ошибка сети] ' + e.message);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

// ============ Действия ============
function resetAll(){
  chatHistory = [];
  log.innerHTML = '';
  setState(null);
  setBadges([]);
  clearSessions();
}

async function openSheet(){
  var sessions = await listSessions();
  historyBody.innerHTML = '';
  if(!sessions.length){
    historyBody.innerHTML = '<div style="color:#58585e;text-align:center;padding:40px 0">Пока ничего</div>';
  } else {
    sessions.sort(function(a,b){ return b.ts - a.ts; });
    sessions.forEach(function(s){
      var d = document.createElement('div');
      d.className = 'history-item';
      var firstUser = (s.history || []).find(function(m){return m.role === 'user';});
      d.innerHTML = '<div class="who">' + new Date(s.ts).toLocaleString('ru-RU') + '</div>' +
                    '<div class="what">' + (firstUser ? firstUser.content : '(пусто)') + '</div>';
      d.onclick = function(){
        chatHistory = s.history || [];
        log.innerHTML = '';
        chatHistory.forEach(function(m){
          addMsg(m.role === 'user' ? 'user' : 'bot', m.content);
        });
        closeSheet();
      };
      historyBody.appendChild(d);
    });
  }
  sheet.classList.add('open');
}

function closeSheet(){ sheet.classList.remove('open'); }

// ============ Обработчики ============
form.addEventListener('submit', function(e){ e.preventDefault(); send(); });
input.addEventListener('keydown', function(e){
  if(e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); send(); }
});
input.addEventListener('input', function(){
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 200) + 'px';
});

// ============ Boot ============
openDB().then(function(){
  // стартовая сессия
  if(chatHistory.length === 0){
    setState(null);
  }
}).catch(function(e){
  console.warn('IndexedDB не доступен', e);
});
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML

import interpret_chat