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
  background:#0f0f11;
  color:#e8e8ea;
  -webkit-font-smoothing:antialiased;
  text-rendering:optimizeLegibility;
  letter-spacing:-0.005em;
}
.wrap{
  max-width:680px;margin:0 auto;
  padding:56px 24px 160px;
  min-height:100vh;
}
#log{display:flex;flex-direction:column;gap:32px}
.msg.bot{
  font-size:17px;line-height:1.78;color:#e8e8ea;
  white-space:pre-wrap;word-wrap:break-word;
  animation:fadeIn 0.5s ease;
}
.msg.user{
  align-self:flex-end;max-width:82%;
  background:rgba(255,255,255,0.055);
  border:1px solid rgba(255,255,255,0.07);
  backdrop-filter:blur(14px) saturate(140%);
  -webkit-backdrop-filter:blur(14px) saturate(140%);
  border-radius:16px;
  padding:10px 14px;
  font-size:15px;line-height:1.55;
  color:#a8a8ae;
  white-space:pre-wrap;word-wrap:break-word;
  animation:fadeIn 0.3s ease;
}
@keyframes fadeIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:translateY(0)}}
.pulse{display:inline-flex;gap:4px;align-items:center;height:20px}
.pulse span{width:6px;height:6px;border-radius:50%;background:#7fb1ff;animation:pulse 1.4s infinite}
.pulse span:nth-child(2){animation-delay:0.2s}
.pulse span:nth-child(3){animation-delay:0.4s}
@keyframes pulse{0%,100%{opacity:0.25;transform:scale(0.7)}50%{opacity:1;transform:scale(1)}}

form{
  position:fixed;left:0;right:0;bottom:0;
  background:rgba(15,15,17,0.72);
  backdrop-filter:blur(28px) saturate(180%);
  -webkit-backdrop-filter:blur(28px) saturate(180%);
  border-top:1px solid rgba(255,255,255,0.05);
  padding:12px 20px calc(14px + env(safe-area-inset-bottom,0px));
}
form .inner{
  max-width:680px;margin:0 auto;
  display:flex;gap:10px;align-items:flex-end;
}
textarea{
  flex:1;resize:none;background:transparent;
  color:#e8e8ea;border:none;outline:none;
  padding:10px 4px;
  font:inherit;font-size:17px;line-height:1.55;
  min-height:44px;max-height:200px;
  white-space:pre-wrap;
}
textarea::placeholder{color:#58585e}
button.send{
  flex-shrink:0;
  width:40px;height:40px;
  background:#7fb1ff;color:#0f0f11;
  border:none;border-radius:50%;
  cursor:pointer;padding:0;
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
      var answer = j.data.output.vars.text;
      addMsg('bot', answer);
      chatHistory.push({role: 'user', content: text});
      chatHistory.push({role: 'assistant', content: answer});
    } else if(j.ok && j.data && j.data.output && j.data.output.silence){
      // молчание
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
  this.style.height = Math.min(this.scrollHeight, 200) + 'px';
});
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML

import interpret_chat