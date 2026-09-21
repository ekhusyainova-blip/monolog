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
    "layer_a": "Я — Monolog.",
    "layer_b": "Я — Monolog.",
    "layer_c": "Я — Monolog.",
    "layer_d": "Я — Monolog.",
    "layer_a_content": "Ты — Monolog.",
}

# A · шина
HANDLERS = {}
EVENTS = []

def on(event_name: str):
    def wrapper(fn):
        HANDLERS.setdefault(event_name, []).append(fn)
        return fn
    return wrapper

def emit(event_name: str, payload: dict):
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
    EVENTS.clear()
    emit("user_message", event)
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
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monolog · Чат</title>
<style>
:root[data-theme="dark"]{--bg:#0f0f10;--fg:#e8e8ea;--muted:#6b6b70;--user:#1c1c1f;--bot:#16161a;--accent:#6ea8fe;--border:#26262b;--code-bg:#0b0b0d}
:root[data-theme="light"]{--bg:#fafafa;--fg:#1a1a1c;--muted:#8a8a8f;--user:#f0f0f3;--bot:#ffffff;--accent:#2563eb;--border:#e5e5e8;--code-bg:#f3f3f5}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{font:15px/1.6 -apple-system,system-ui,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--fg);display:flex;flex-direction:column;align-items:center}
.wrap{width:100%;max-width:820px;display:flex;flex-direction:column;min-height:100dvh;height:100dvh}
header{display:flex;justify-content:space-between;padding:12px 16px;border-bottom:1px solid var(--border);position:sticky;top:0;background:var(--bg);z-index:10}
.theme-btn{background:none;border:1px solid var(--border);color:var(--fg);padding:4px 10px;border-radius:6px;cursor:pointer;font:inherit;font-size:13px}
#log{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
.msg{padding:12px 14px;border-radius:10px;word-wrap:break-word;overflow-wrap:break-word;white-space:pre-wrap;line-height:1.6}
.msg.user{background:var(--user);align-self:flex-end;max-width:85%}
.msg.bot{background:var(--bot);border:1px solid var(--border);align-self:stretch}
.msg .role{font-size:11px;color:var(--muted);margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px}
.msg strong{font-weight:600}
.msg em{font-style:italic;color:var(--muted)}
.msg h1,.msg h2,.msg h3{margin:10px 0 6px;font-size:1.05em}
.msg ul,.msg ol{margin:6px 0 6px 22px}
.msg li{margin:2px 0}
.msg hr{border:none;border-top:1px solid var(--border);margin:10px 0}
.code-block{position:relative;margin:8px 0;background:var(--code-bg);border:1px solid var(--border);border-radius:8px;overflow:hidden}
.code-block pre{padding:12px 14px;padding-top:34px;overflow-x:auto;font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre;margin:0}
.code-block .copy-btn{position:absolute;top:6px;right:6px;background:var(--bot);border:1px solid var(--border);color:var(--fg);padding:3px 10px;border-radius:6px;cursor:pointer;font-size:11px;opacity:0.85}
.code-block .copy-btn:hover{opacity:1}
.code-block .lang{position:absolute;top:8px;left:12px;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px}
footer{padding:12px 16px;border-top:1px solid var(--border);display:flex;gap:8px;background:var(--bg);position:sticky;bottom:0}
textarea{flex:1;resize:none;background:var(--bg);color:var(--fg);border:1px solid var(--border);border-radius:8px;padding:10px 12px;font:inherit;min-height:44px;max-height:200px;white-space:pre-wrap}
button.send{background:var(--accent);color:white;border:none;padding:0 18px;border-radius:8px;cursor:pointer;font:inherit;font-weight:600}
button.send:disabled{opacity:0.5;cursor:not-allowed}
@media (max-width:600px){
  body{font-size:14px}
  .wrap{max-width:100%}
  .msg.user{max-width:92%}
  #log{padding:10px}
  header,footer{padding:10px 12px}
  .code-block pre{font-size:12px;padding:10px 12px;padding-top:32px}
}
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
  <textarea id="input" placeholder="Напиши..." rows="1"></textarea>
  <button class="send" id="send" onclick="send()">→</button>
</footer>
</div>
<script>
var log=document.getElementById('log');
var input=document.getElementById('input');
var sendBtn=document.getElementById('send');
var chatHistory=[];

function setTheme(t){document.documentElement.setAttribute('data-theme',t);localStorage.setItem('monolog_theme',t)}
function toggleTheme(){var cur=document.documentElement.getAttribute('data-theme');setTheme(cur==='dark'?'light':'dark')}
(function(){var s=localStorage.getItem('monolog_theme');if(s)setTheme(s);else if(window.matchMedia('(prefers-color-scheme: light)').matches)setTheme('light')})();

function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}

function renderMarkdown(text){
  var codeBlocks=[];
  text=text.replace(/```(\\w*)\\n([\\s\\S]*?)```/g,function(m,lang,code){
    var idx=codeBlocks.length;
    codeBlocks.push({lang:lang||'text',code:code});
    return '\\u0000CODE'+idx+'\\u0000';
  });
  text=esc(text);
  text=text.replace(/^### (.+)$/gm,'<h3>$1</h3>');
  text=text.replace(/^## (.+)$/gm,'<h2>$1</h2>');
  text=text.replace(/^# (.+)$/gm,'<h1>$1</h1>');
  text=text.replace(/\\*\\*([^*]+)\\*\\*/g,'<strong>$1</strong>');
  text=text.replace(/(?<!\\*)\\*([^*]+)\\*(?!\\*)/g,'<em>$1</em>');
  text=text.replace(/^---$/gm,'<hr>');
  text=text.replace(/^- (.+)$/gm,'<li>$1</li>');
  text=text.replace(/(<li>[\\s\\S]*?<\\/li>)/g,function(m){return '<ul>'+m+'</ul>'});
  text=text.replace(/\\u0000CODE(\\d+)\\u0000/g,function(m,i){
    var b=codeBlocks[+i];
    var lang=b.lang;
    var isJson=(lang==='json'||lang==='');
    var cls=isJson?'code-block json-block':'code-block';
    var label=isJson?'JSON':(lang||'CODE');
    return '<div class="'+cls+'"><span class="lang">'+label+'</span><button class="copy-btn" onclick="copyBlock(this)">Копировать</button><pre><code>'+esc(b.code)+'</code></pre></div>';
  });
  return text;
}

function copyBlock(btn){
  var pre=btn.parentElement.querySelector('pre');
  if(!pre)return;
  var text=pre.innerText;
  if(navigator.clipboard){navigator.clipboard.writeText(text).then(function(){btn.textContent='Скопировано';setTimeout(function(){btn.textContent='Копировать'},1200)})}
}

function addMsg(role,text){
  var d=document.createElement('div');
  d.className='msg '+role;
  var r=document.createElement('div');
  r.className='role';
  r.textContent=(role==='user'?'Я':'Monolog');
  d.appendChild(r);
  var content=document.createElement('div');
  content.className='content';
  if(role==='bot'){content.innerHTML=renderMarkdown(text)}
  else{content.textContent=text}
  d.appendChild(content);
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
    var r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:text,context:chatHistory})});
    var j=await r.json();
    if(j.ok && j.data && j.data.answer){
      addMsg('bot',j.data.answer);
      chatHistory.push({role:'user',content:text});
      chatHistory.push({role:'assistant',content:j.data.answer});
    }else if(j.error){
      addMsg('bot','[ошибка] '+(j.error.message||'неизвестно'));
    }else{
      addMsg('bot','[ошибка] пустой ответ');
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
input.addEventListener('input',function(){
  this.style.height='auto';
  this.style.height=Math.min(this.scrollHeight,200)+'px';
});
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML

# A · импорт B в конце
import chat_b_chat