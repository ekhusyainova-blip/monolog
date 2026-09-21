# data_chat.py · MVP чата Monolog
# A-файл с 4 фрагментами: A (данные), B (интерпретация), C (решение), D (мета)
# Плюс: FIX, OFF/FILTER/STUB (служебные флаги)
# v3 · переписан целиком

import os
import json
import time
import httpx
from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

# ============================================================
# СЛУЖЕБНЫЕ ФЛАГИ
# ============================================================

OFF = False
FILTER = False  # задел, не реализован в MVP
STUB = False

# ============================================================
# ФРАГМЕНТ A · ДАННЫЕ
# ============================================================

PROVIDERS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "openai/gpt-oss-120b",
        ...
    },
    "openrouter": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "meta-llama/llama-3.3-70b-instruct:free",  # пока оставь, потом проверишь
        ...
    },
    "cerebras": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "gpt-oss-120b",
        ...
    },
    "sambanova": {
        "url": "https://api.sambanova.ai/v1/chat/completions",
        "model": "gpt-oss-120b",
        ...
    },
}

def load_keys(env_name):
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return []
    return [k.strip() for k in raw.split(",") if k.strip()]

KEYS = {
    "groq": load_keys("GROQ_API_KEYS"),
    "openrouter": load_keys("OPENROUTER_API_KEY"),
    "cerebras": load_keys("CEREBRAS_API_KEY"),
    "sambanova": load_keys("SAMBANOVA_API_KEY"),
}

PROMPTS = {
    "layer_a": "Ты — Monolog. Факты. Что есть.",
    "layer_b": "Ты — Monolog. Интерпретации. Что значит.",
    "layer_c": "Ты — Monolog. Решения. Что делать.",
    "layer_d": "Ты — Monolog. Мета. Откуда смотрю.",
    "layer_a_content": "Ты — Monolog. Аварийный слой. Просто отражай.",
    "chat_meta_fallback": json.dumps({"layer": "A", "action": "reflect", "payload": {}}),
}

SETTINGS = {
    "theme": "dark",
    "stream": False,
    "max_tokens": 2048,
    "temperature": 0.7,
    "timeout": 120,
    "provider_order": ["groq", "openrouter", "cerebras", "sambanova"],
}

CONTEXTS = []
LOCAL_LAYER_A_CONTENT = PROMPTS["layer_a_content"]
FIX = {"layer": "A", "action": "reflect", "payload": {}}

# ============================================================
# ФРАГМЕНТ B · ИНТЕРПРЕТАЦИЯ
# ============================================================

def parse_event(body):
    return {
        "text": (body.get("text") or "").strip(),
        "context_id": body.get("context_id"),
        "context": body.get("context"),
        "provider": body.get("provider"),
        "stream": body.get("stream", SETTINGS["stream"]),
    }

def resolve_context(event):
    if event.get("context"):
        return event["context"]
    if event.get("context_id"):
        for c in CONTEXTS:
            if c["id"] == event["context_id"]:
                return c["messages"]
    return []

def build_request(event, context):
    system = "\n".join([
        PROMPTS["layer_a"],
        PROMPTS["layer_b"],
        PROMPTS["layer_c"],
        PROMPTS["layer_d"],
    ]) if not STUB else LOCAL_LAYER_A_CONTENT

    messages = [{"role": "system", "content": system}]
    for msg in context[-20:]:
        messages.append(msg)
    messages.append({"role": "user", "content": event["text"]})

    return {
        "messages": messages,
        "temperature": SETTINGS["temperature"],
        "max_tokens": SETTINGS["max_tokens"],
    }

def meta_request(text):
    if STUB or OFF:
        return FIX
    return FIX

# ============================================================
# ФРАГМЕНТ C · РЕШЕНИЕ
# ============================================================

def pick_provider(preferred=None):
    if preferred and preferred in KEYS and KEYS[preferred]:
        return preferred
    for name in SETTINGS["provider_order"]:
        if KEYS.get(name):
            return name
    raise HTTPException(503, "Нет доступных провайдеров: все ключи пусты")

def pick_key(provider):
    keys = KEYS[provider]
    if not keys:
        raise HTTPException(503, "Нет ключей для " + provider)
    idx = int(time.time()) % len(keys)
    return keys[idx]

def _provider_headers(provider, key):
    headers = {
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = os.getenv("OPENROUTER_REFERER", "https://monolog.app")
        headers["X-Title"] = os.getenv("OPENROUTER_TITLE", "Monolog")
    return headers

def _provider_body(provider, payload, stream):
    cfg = PROVIDERS[provider]
    body = dict(payload)
    body["model"] = cfg["model"]
    if cfg["reasoning_effort"]:
        body["reasoning_effort"] = cfg["reasoning_effort"]
    if stream:
        body["stream"] = True
    return body

async def call_provider(provider, payload):
    key = pick_key(provider)
    cfg = PROVIDERS[provider]
    headers = _provider_headers(provider, key)
    body = _provider_body(provider, payload, stream=False)
    async with httpx.AsyncClient(timeout=SETTINGS["timeout"]) as client:
        r = await client.post(cfg["url"], headers=headers, json=body)
        r.raise_for_status()
        return r.json()

async def call_provider_stream(provider, payload):
    key = pick_key(provider)
    cfg = PROVIDERS[provider]
    headers = _provider_headers(provider, key)
    body = _provider_body(provider, payload, stream=True)

    async def gen():
        async with httpx.AsyncClient(timeout=SETTINGS["timeout"]) as client:
            async with client.stream("POST", cfg["url"], headers=headers, json=body) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if line:
                        yield line + "\n\n"
    return gen()

# ============================================================
# ФРАГМЕНТ D · МЕТА
# ============================================================

def build_response(answer, meta, provider):
    return {
        "ok": True,
        "data": {"answer": answer, "meta": meta, "provider": provider},
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

def build_error(code, cls, msg):
    return {
        "ok": False,
        "error": {"code": code, "class": cls, "message": msg},
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

# ============================================================
# APP И РОУТЫ
# ============================================================

app = FastAPI(title="Monolog Chat")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    if OFF:
        return {"ok": True, "status": "off"}
    if STUB:
        return {"ok": True, "status": "stub"}
    return {
        "ok": True,
        "status": "alive",
        "providers": {name: len(KEYS.get(name, [])) for name in PROVIDERS},
    }

@app.post("/chat")
async def chat(request: Request):
    if OFF:
        raise HTTPException(503, "Сервис отключён")
    body = await request.json()
    event = parse_event(body)
    if not event["text"]:
        return JSONResponse(build_error(400, "validation", "Пустой текст"), status_code=400)

    provider = pick_provider(event["provider"])
    context = resolve_context(event)
    payload = build_request(event, context)
    meta = meta_request(event["text"])
    try:
        data = await call_provider(provider, payload)
        answer = data["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        return JSONResponse(build_error(e.response.status_code, "provider", str(e)), status_code=502)
    except httpx.HTTPError as e:
        return JSONResponse(build_error(502, "provider", str(e)), status_code=502)
    return JSONResponse(build_response(answer, meta, provider))

@app.post("/chat/stream")
async def chat_stream(request: Request):
    if OFF:
        raise HTTPException(503, "Сервис отключён")
    body = await request.json()
    event = parse_event(body)
    if not event["text"]:
        return JSONResponse(build_error(400, "validation", "Пустой текст"), status_code=400)

    provider = pick_provider(event["provider"])
    context = resolve_context(event)
    payload = build_request(event, context)
    try:
        stream = await call_provider_stream(provider, payload)
    except httpx.HTTPError as e:
        return JSONResponse(build_error(502, "provider", str(e)), status_code=502)
    return StreamingResponse(stream, media_type="text/event-stream")

@app.post("/chat/multi")
async def chat_multi(request: Request):
    if OFF:
        raise HTTPException(503, "Сервис отключён")
    body = await request.json()
    event = parse_event(body)
    providers = body.get("providers") or SETTINGS["provider_order"][:2]
    results = {}
    for name in providers:
        if not KEYS.get(name):
            continue
        try:
            payload = build_request(event, [])
            data = await call_provider(name, payload)
            results[name] = data["choices"][0]["message"]["content"]
        except Exception as e:
            results[name] = "[ошибка: " + str(e) + "]"
    return JSONResponse({
        "ok": True,
        "data": results,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })

@app.get("/contexts")
async def list_contexts():
    return {"ok": True, "data": [{"id": c["id"], "title": c.get("title", "")} for c in CONTEXTS]}

@app.post("/contexts/save")
async def save_context(request: Request):
    body = await request.json()
    cid = body.get("id") or str(int(time.time()))
    CONTEXTS.append({
        "id": cid,
        "title": body.get("title", "Без названия"),
        "messages": body.get("messages", []),
    })
    return {"ok": True, "data": {"id": cid}}

@app.delete("/contexts/{cid}")
async def delete_context(cid: str):
    global CONTEXTS
    CONTEXTS = [c for c in CONTEXTS if c["id"] != cid]
    return {"ok": True}

@app.get("/prompts")
async def list_prompts():
    return {"ok": True, "data": PROMPTS}

@app.post("/prompts/save")
async def save_prompt(request: Request, x_author_key: Optional[str] = Header(None, alias="X-Author-Key")):
    if os.getenv("AUTHOR_SECRET") and x_author_key != os.getenv("AUTHOR_SECRET"):
        raise HTTPException(401, "Неверный ключ автора")
    body = await request.json()
    for k, v in body.items():
        if k in PROMPTS:
            PROMPTS[k] = v
    return {"ok": True, "data": PROMPTS}

# ============================================================
# ИНТЕРФЕЙС
# ============================================================

INDEX_HTML = """<!DOCTYPE html>
<html lang="ru" data-theme="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monolog · Чат</title>
<style>
:root[data-theme="dark"]{--bg:#0f0f10;--fg:#e8e8ea;--muted:#6b6b70;--user:#1c1c1f;--bot:#16161a;--accent:#6ea8fe;--border:#26262b}
:root[data-theme="light"]{--bg:#fafafa;--fg:#1a1a1c;--muted:#8a8a8f;--user:#f0f0f3;--bot:#ffffff;--accent:#2563eb;--border:#e5e5e8}
*{box-sizing:border-box;margin:0;padding:0}
body{font:15px/1.5 -apple-system,system-ui,sans-serif;background:var(--bg);color:var(--fg);display:flex;flex-direction:column;height:100vh}
header{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--border)}
.title{font-weight:600}
.theme-btn{background:none;border:1px solid var(--border);color:var(--fg);padding:4px 10px;border-radius:6px;cursor:pointer;font:inherit}
#log{flex:1;overflow-y:auto;padding:16px}
.msg{max-width:720px;margin:0 auto 12px;padding:12px 14px;border-radius:10px;white-space:pre-wrap;word-wrap:break-word}
.msg.user{background:var(--user)}
.msg.bot{background:var(--bot);border:1px solid var(--border)}
.msg .role{font-size:11px;color:var(--muted);margin-bottom:6px}
footer{padding:12px 16px;border-top:1px solid var(--border);display:flex;gap:8px;max-width:720px;margin:0 auto;width:100%}
textarea{flex:1;resize:none;background:var(--bg);color:var(--fg);border:1px solid var(--border);border-radius:8px;padding:10px 12px;font:inherit;min-height:44px;max-height:200px}
button.send{background:var(--accent);color:white;border:none;padding:0 18px;border-radius:8px;cursor:pointer;font:inherit}
button.send:disabled{opacity:0.5;cursor:not-allowed}
.meta{font-size:11px;color:var(--muted);margin-top:6px}
</style>
</head>
<body>
<header>
  <div class="title">Monolog · Чат</div>
  <button class="theme-btn" onclick="toggleTheme()">Тема</button>
</header>
<div id="log"></div>
<footer>
  <textarea id="input" placeholder="Напиши..."></textarea>
  <button class="send" id="send" onclick="send()">→</button>
</footer>
<script>
var log=document.getElementById('log');
var input=document.getElementById('input');
var sendBtn=document.getElementById('send');
var history=[];

function setTheme(t){document.documentElement.setAttribute('data-theme',t);localStorage.setItem('monolog_theme',t)}
function toggleTheme(){var cur=document.documentElement.getAttribute('data-theme');setTheme(cur==='dark'?'light':'dark')}
(function(){var saved=localStorage.getItem('monolog_theme');if(saved)setTheme(saved);else if(window.matchMedia('(prefers-color-scheme: light)').matches)setTheme('light')})();

function addMsg(role,text,meta){
  var d=document.createElement('div');
  d.className='msg '+role;
  var roleDiv=document.createElement('div');
  roleDiv.className='role';
  roleDiv.textContent=(role==='user'?'Я':'Monolog');
  d.appendChild(roleDiv);
  var textNode=document.createTextNode(text);
  d.appendChild(textNode);
  if(meta){var m=document.createElement('div');m.className='meta';m.textContent=meta;d.appendChild(m)}
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
      addMsg('bot',j.data.answer,j.data.provider);
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
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML