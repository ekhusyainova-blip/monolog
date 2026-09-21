# chat_a_chat.py
# Тема: chat
# Слой: A (данные, точка входа, шина, app, роуты)

import os
import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# A · данные
PROVIDERS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "openai/gpt-oss-120b",
        "env_keys": "GROQ_API_KEYS",
    },
    "cerebras": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "gpt-oss-120b",
        "env_keys": "CEREBRAS_API_KEY",
    },
    "sambanova": {
        "url": "https://api.sambanova.ai/v1/chat/completions",
        "model": "Meta-Llama-3.3-70B-Instruct",
        "env_keys": "SAMBANOVA_API_KEY",
    },
    "openrouter": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "nvidia/nemotron-3-ultra",
        "env_keys": "OPENROUTER_API_KEY",
    },
}

SETTINGS = {
    "temperature": 0.7,
    "max_tokens": 2048,
    "timeout": 120,
    "provider_order": ["groq", "cerebras", "sambanova", "openrouter"],
    "cooldown_sec": 65,
}

def load_keys(env_name: str) -> list:
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return []
    return [k.strip() for k in raw.split(",") if k.strip()]

KEYS = {
    "groq": load_keys("GROQ_API_KEYS"),
    "cerebras": load_keys("CEREBRAS_API_KEY"),
    "sambanova": load_keys("SAMBANOVA_API_KEY"),
    "openrouter": load_keys("OPENROUTER_API_KEY"),
}

PROMPTS = {
    "layer_a": "Ты — Monolog. Факты. Что есть.",
    "layer_b": "Ты — Monolog. Интерпретации. Что значит.",
    "layer_c": "Ты — Monolog. Решения. Что делать.",
    "layer_d": "Ты — Monolog. Мета. Откуда смотрю.",
}

# A · шина
HANDLERS = {}
EVENTS = []

def on(event_name: str):
    """Декоратор регистрации обработчика."""
    def wrapper(fn):
        HANDLERS.setdefault(event_name, []).append(fn)
        return fn
    return wrapper

def emit(event_name: str, payload: dict):
    """Вызвать все обработчики события."""
    for fn in HANDLERS.get(event_name, []):
        fn(payload)

# A · app и роуты
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
        "providers": {name: len(KEYS.get(name, [])) for name in PROVIDERS},
    }

@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    event = {
        "text": (body.get("text") or "").strip(),
        "context": body.get("context"),
        "provider": body.get("provider"),
    }
    if not event["text"]:
        return JSONResponse(
            {"ok": False, "error": {"code": 400, "class": "validation", "message": "Пустой текст"}},
            status_code=400,
        )
    # очистить буфер
    EVENTS.clear()
    # запустить цепочку
    emit("user_message", event)
    # ждать ответа
    if not EVENTS:
        return JSONResponse(
            {"ok": False, "error": {"code": 500, "class": "internal", "message": "Нет ответа от цепочки"}},
            status_code=500,
        )
    return JSONResponse(EVENTS[-1])

# A · интерфейс
INDEX_HTML = """<!DOCTYPE html>
<html lang="ru" data-theme="dark">
<head>
<meta charset="utf-8">
<title>Monolog · Чат</title>
<style>
:root[data-theme="dark"]{--bg:#0f0f10;--fg:#e8e8ea;--muted:#6b6b70;--user:#1c1c1f;--bot:#16161a;--accent:#6ea8fe;--border:#26262b}
:root[data-theme="light"]{--bg:#fafafa;--fg:#1a1a1c;--muted:#8a8a8f;--user:#f0f0f3;--bot:#ffffff;--accent:#2563eb;--border:#e5e5e8}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{font:15px/1.5 -apple-system,system-ui,sans-serif;background:var(--bg);color:var(--fg);display:flex;flex-direction:column;align-items:center}
.wrap{width:100%;max-width:720px;display:flex;flex-direction:column;height:100vh}
header{display:flex;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--border)}
.theme-btn{background:none;border:1px solid var(--border);color:var(--fg);padding:4px 10px;border-radius:6px;cursor:pointer;font:inherit;font-size:13px}
#log{flex:1;overflow-y:auto;padding:16px}
.msg{max-width:100%;margin:0 auto 12px;padding:12px 14px;border-radius:10px;word-wrap:break-word}
.msg.user{background:var(--user)}
.msg.bot{background:var(--bot);border:1px solid var(--border)}
.msg .role{font-size:11px;color:var(--muted);margin-bottom:6px}
footer{padding:12px 16px;border-top:1px solid var(--border);display:flex;gap:8px}
textarea{flex:1;resize:none;background:var(--bg);color:var(--fg);border:1px solid var(--border);border-radius:8px;padding:10px 12px;font:inherit;min-height:44px;max-height:200px}
button.send{background:var(--accent);color:white;border:none;padding:0 18px;border-radius:8px;cursor:pointer;font:inherit}
button.send:disabled{opacity:0.5}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div>Monolog · Чат</div>
  <button class="theme-btn" onclick="toggleTheme()">Тема</button>
</header>
<div id="log"></div>
<footer>
  <textarea id="input" placeholder="Напиши..."></textarea>
  <button class="send" id="send" onclick="send()">→</button>
</footer>
</div>
<script>
var log=document.getElementById('log');
var input=document.getElementById('input');
var sendBtn=document.getElementById('send');
var history=[];

function setTheme(t){document.documentElement.setAttribute('data-theme',t);localStorage.setItem('monolog_theme',t)}
function toggleTheme(){var cur=document.documentElement.getAttribute('data-theme');setTheme(cur==='dark'?'light':'dark')}
(function(){var s=localStorage.getItem('monolog_theme');if(s)setTheme(s);else if(window.matchMedia('(prefers-color-scheme: light)').matches)setTheme('light')})();

function addMsg(role,text){
  var d=document.createElement('div');
  d.className='msg '+role;
  var r=document.createElement('div');
  r.className='role';
  r.textContent=(role==='user'?'Я':'Monolog');
  d.appendChild(r);
  d.appendChild(document.createTextNode(text));
  log.appendChild(d);
  log.scrollTop=log.scrollHeight;
}

async function send(){
  var text=input.value.trim();
  if(!text)return;
  addMsg('user',text);
  input.value='';
  sendBtn.disabled=true;
  try{
    var r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:text,context:history})});
    var j=await r.json();
    if(j.ok){
      addMsg('bot',j.data.answer);
      history.push({role:'user',content:text});
      history.push({role:'assistant',content:j.data.answer});
    }else{
      addMsg('bot','[ошибка] '+(j.error?j.error.message:'неизвестно'));
    }
  }catch(e){
    addMsg('bot','[ошибка сети] '+e.message);
  }finally{
    sendBtn.disabled=false;
  }
}

input.addEventListener('keydown',function(e){
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}
});
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML

# A · импорт B в конце
import chat_b_chat