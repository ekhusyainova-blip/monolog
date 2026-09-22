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

PROMPTS = {
    "layer_a": "Анализ. Monolog - отражение всего и ничего.",
    "layer_b": "Противоречия. AI Monolog - интерфейс отражения всего и ничего.",
    "layer_c": "Решение. Отражаешь, не ведёшь.",
    "layer_d": "Адаптация. Разверни контекст в мерности.",
}

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
</head>
<body>
<div id="log"></div>
<form id="form">
  <textarea id="input" rows="1" placeholder="Напиши..."></textarea>
  <button type="submit">Отправить</button>
</form>
<script>
var log = document.getElementById('log');
var form = document.getElementById('form');
var input = document.getElementById('input');
var chatHistory = [];

function addMsg(role, text){
  var d = document.createElement('div');
  d.className = 'msg ' + role;
  var b = document.createElement('strong');
  b.textContent = (role === 'user' ? 'Я: ' : 'Monolog: ');
  d.appendChild(b);
  d.appendChild(document.createTextNode(text));
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

async function send(){
  var text = input.value.trim();
  if(!text) return;
  addMsg('user', text);
  input.value = '';
  try {
    var r = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text: text, context: history})
    });
    var j = await r.json();
    if(j.ok && j.data && j.data.answer){
      addMsg('bot', j.data.answer);
      history.push({role: 'user', content: text});
      history.push({role: 'assistant', content: j.data.answer});
    } else if (j.error) {
      addMsg('bot', '[ошибка] ' + (j.error.message || ''));
    } else {
      addMsg('bot', '[ошибка] пустой ответ');
    }
  } catch (e) {
    addMsg('bot', '[ошибка сети] ' + e.message);
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