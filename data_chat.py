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
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monolog</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font:17px/1.75 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#0e0e10;color:#e6e6e8;max-width:680px;margin:0 auto;padding:24px 20px 120px;min-height:100vh}
#log{display:flex;flex-direction:column;gap:20px}
.msg.bot{font-size:17px;line-height:1.75;white-space:pre-wrap;word-wrap:break-word}
.msg.user{color:#8a8a8f;font-size:15px;text-align:right;white-space:pre-wrap;word-wrap:break-word}
.pulse{width:8px;height:8px;border-radius:50%;background:#7fb1ff;display:inline-block;animation:pulse 1.4s infinite}
@keyframes pulse{0%,100%{opacity:0.3;transform:scale(0.8)}50%{opacity:1;transform:scale(1)}}
form{position:fixed;left:0;right:0;bottom:0;background:#0e0e10;padding:14px 20px calc(14px + env(safe-area-inset-bottom,0px));border-top:1px solid #1e1e21;display:flex;gap:8px;align-items:flex-end}
form .inner{max-width:680px;margin:0 auto;width:100%;display:flex;gap:8px;align-items:flex-end}
textarea{flex:1;resize:none;background:transparent;color:#e6e6e8;border:1px solid #1e1e21;border-radius:10px;padding:10px 12px;font:inherit;min-height:44px;max-height:160px}
textarea:focus{outline:none;border-color:#7fb1ff}
button{background:#7fb1ff;color:#fff;border:none;padding:0 18px;height:44px;border-radius:10px;cursor:pointer;font:inherit;font-weight:500;flex-shrink:0}
button:disabled{opacity:0.4;cursor:not-allowed}
</style>
</head>
<body>

<div id="log"></div>

<form id="form">
  <div class="inner">
    <textarea id="input" rows="1" placeholder="Напиши..."></textarea>
    <button type="submit" id="send">→</button>
  </div>
</form>

<script>
var log = document.getElementById('log');
var form = document.getElementById('form');
var input = document.getElementById('input');
var sendBtn = document.getElementById('send');
var chatHistory = [];

function addMsg(role, text){
  var d = document.createElement('div');
  d.className = 'msg ' + role;
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

async function send(){
  var text = input.value.trim();
  if(!text) return;
  addMsg('user', text);
  input.value = '';
  input.style.height = 'auto';

  var pulse = document.createElement('div');
  pulse.className = 'msg bot';
  pulse.innerHTML = '<span class="pulse"></span>';
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
      var answer = j.data.output.vars.text;
      addMsg('bot', answer);
      chatHistory.push({role: 'user', content: text});
      chatHistory.push({role: 'assistant', content: answer});
    } else if(j.ok && j.data && j.data.output && j.data.output.silence){
      // молчание — ничего не показываем
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
input.addEventListener('input', function(){
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 160) + 'px';
});
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML

import interpret_chat