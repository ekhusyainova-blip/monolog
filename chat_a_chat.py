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
    "layer_a": "Ты — Monolog.",
    "layer_b": "Ты — Monolog.",
    "layer_c": "Ты — Monolog.",
    "layer_d": "Ты — Monolog.",
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
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="dark light">
<title>Monolog</title>
<style>
:root[data-theme="dark"]{
  --bg:#0f0f10;
  --fg:#ececee;
  --muted:#7c7c82;
  --dim:#58585e;
  --accent:#6ea8fe;
  --user-text:#b8b8be;
  --border:#1c1c1f;
  --code-bg:#151518;
  --code-border:#1e1e21;
  --slider-bg:#2a2a2e;
  --slider-knob:#e8e8ea;
}
:root[data-theme="light"]{
  --bg:#fbfbfc;
  --fg:#1a1a1c;
  --muted:#8a8a8f;
  --dim:#b5b5ba;
  --accent:#2563eb;
  --user-text:#6b6b70;
  --border:#ececef;
  --code-bg:#f4f4f6;
  --code-border:#e7e7ea;
  --slider-bg:#e0e0e4;
  --slider-knob:#ffffff;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{
  font:16px/1.7 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,sans-serif;
  background:var(--bg);color:var(--fg);
  display:flex;flex-direction:column;
  -webkit-font-smoothing:antialiased;
  text-rendering:optimizeLegibility;
  overscroll-behavior-y:none;
}
.wrap{
  width:100%;max-width:760px;margin:0 auto;
  display:flex;flex-direction:column;flex:1;min-height:0;
  height:100dvh;
  position:relative;
}

/* Ползунок темы — сверху справа */
.theme-slider{
  position:absolute;top:14px;right:16px;
  z-index:10;
  width:44px;height:24px;
  background:var(--slider-bg);
  border-radius:12px;
  cursor:pointer;
  border:none;padding:0;
  transition:background 0.2s;
}
.theme-slider .knob{
  position:absolute;top:2px;left:2px;
  width:20px;height:20px;
  background:var(--slider-knob);
  border-radius:50%;
  transition:transform 0.25s cubic-bezier(0.4,0,0.2,1),background 0.2s;
  box-shadow:0 1px 3px rgba(0,0,0,0.18);
}
:root[data-theme="light"] .theme-slider .knob{
  transform:translateX(20px);
}

#log{
  flex:1;min-height:0;overflow-y:auto;
  padding:56px 20px 20px;
  display:flex;flex-direction:column;gap:22px;
  scroll-behavior:smooth;
}
#log::-webkit-scrollbar{width:0}

.msg{display:flex;flex-direction:column;max-width:100%}
.msg.user{
  align-self:flex-end;max-width:80%;
  color:var(--user-text);
  font-size:15px;line-height:1.55;
  text-align:right;
  white-space:pre-wrap;
}
.msg.bot{
  align-self:stretch;
  font-size:16px;line-height:1.75;
  color:var(--fg);
}
.msg.bot p{margin:0 0 12px}
.msg.bot p:last-child{margin-bottom:0}
.msg.bot strong{font-weight:600;color:var(--fg)}
.msg.bot em{font-style:italic;color:var(--muted)}
.msg.bot h1,.msg.bot h2,.msg.bot h3{margin:18px 0 10px;font-weight:600;line-height:1.3}
.msg.bot h1{font-size:19px}
.msg.bot h2{font-size:17px}
.msg.bot h3{font-size:14px;color:var(--muted);text-transform:uppercase;letter-spacing:0.6px}
.msg.bot ul,.msg.bot ol{margin:8px 0 12px 22px}
.msg.bot li{margin:4px 0}
.msg.bot a{color:var(--accent);text-decoration:none;border-bottom:1px solid color-mix(in srgb,var(--accent) 40%,transparent)}
.msg.bot hr{border:none;border-top:1px solid var(--border);margin:20px 0}
.msg.bot blockquote{border-left:2px solid var(--border);padding:2px 0 2px 12px;margin:10px 0;color:var(--muted)}
.msg.bot code.inline{
  background:var(--code-bg);
  padding:2px 6px;border-radius:4px;
  font:0.92em ui-monospace,"SF Mono",SFMono-Regular,Menlo,monospace;
}

.code-block{
  position:relative;margin:14px 0;
  background:var(--code-bg);
  border:1px solid var(--code-border);
  border-radius:12px;overflow:hidden;
}
.code-block .lang{
  position:absolute;top:10px;left:14px;
  font-size:10px;color:var(--muted);
  text-transform:uppercase;letter-spacing:0.8px;font-weight:500;
}
.code-block pre{
  padding:36px 16px 16px;
  overflow-x:auto;
  font:13px/1.65 ui-monospace,"SF Mono",SFMono-Reg classular,Menlo=",Consolas,monospace;
  white-space:pre;margin:0;color:var(--fg);
}
.code-block .copy-btn{
  position:absolute;top:8px;right:8px;
  background:transparent;border:1px solid transparent;
  color:var(--muted);
  width:28px;height:28px;border-radius:6px;cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  transition:background 0.15s,color 0.15s,border-color 0.15s;
}
.code-block .copy-btn:hover{background:var(--bg);border-color:var(--code-border);color:var(--fg)}
.code-block .copy-btn svg{width:14px;height:14px;stroke:currentColor;fill:none;stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round}
.code-block .copy-btn.copied{color:var(--accent)}

table{width:100%;border-collapse:collapse;margin:14px 0;font-size:14px}
table th,table td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--border)}
table th{font-weight:600;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:0.5px}
table tr:last-child td{border-bottom:none}

/* Композер */
.composer{
  flex-shrink:0;
  padding:10px 16px calc(14px + env(safe-area-inset-bottom, 0px));
  display:flex;align-items:flex-end;gap:10px;
}
.attach-btn{
  flex-shrink:0;
  width:36px;height:36px;
  background:none;border:none;
  color:var(--muted);
  cursor:pointer;padding:0;
  display:flex;align-items:center;justify-content:center;
  border-radius:50%;
  transition:background 0.15s,color 0.15s;
}
.attach-btn:hover{background:var(--code-bg);color:var(--fg)}
.attach-btn svg{width:20px;height:20px;stroke:currentColor;fill:none;stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round}

#input{
  flex:1;resize:none;
  background:none;color:var(--fg);
  border:none;outline:none;
  padding:8px 2px;
  font:16px/1.55 inherit;
  min-height:38px;max-height:200px;
  white-space:pre-wrap;
  overflow-y:auto;
}
#input::placeholder{color:var(--dim)}

.send-btn{
  flex-shrink:0;
  width:36px;height:36px;
  background:transparent;
  color:var(--dim);
  border:none;border-radius:50%;
  cursor:pointer;padding:0;
  display:flex;align-items:center;justify-content:center;
  transition:background 0.15s,color 0.15s,opacity 0.15s;
}
.send-btn svg{width:20px;height:20px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.send-btn.active{background:var(--accent);color:#fff}
.send-btn.active svg{stroke:#fff}
.send-btn:disabled{opacity:0.5;cursor:not-allowed}

@media (max-width:600px){
  #log{padding:52px 16px 16px;gap:20px}
  .msg.user{max-width:85%;font-size:15px}
  .msg.bot{font-size:16px}
  .code-block pre{font-size:12.5px;padding:34px 14px 14px}
  .composer{padding:8px 12px calc(12px + env(safe-area-inset-bottom, 0px))}
  table{font-size:13px}
  table th,table td{padding:7px 9px}
}
</style>
</head>
<body>
<div class="wrap">
  <button class="theme-slider" id="theme" onclick="toggleTheme()" title="Тема" aria-label="Тема">
    <span class="knob"></span>
  </button>
  <div id="log"></div>
  <div class="composer">
    <button class="attach-btn" title="Вложение" aria-label="Вложение">
      <svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>
    </button>
    <textarea id="input" placeholder="Напиши..." rows="1"></textarea>
    <buttonsend-btn" id="send" onclick="send()" title="Отправить" aria-label="Отправить">
      <svg viewBox="0 0 24 24"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
    </button>
  </div>
</div>
<script>
var log=document.getElementById('log');
var input=document.getElementById('input');
var sendBtn=document.getElementById('send');
var chatHistory=[];

var ICON_COPY='<svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
var ICON_CHECK='<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>';

function setTheme(t){
  document.documentElement.setAttribute('data-theme',t);
  localStorage.setItem('monolog_theme',t);
}
function toggleTheme(){
  var cur=document.documentElement.getAttribute('data-theme');
  setTheme(cur==='dark'?'light':'dark');
}
(function(){
  var s=localStorage.getItem('monolog_theme');
  if(s)setTheme(s);
  else if(window.matchMedia('(prefers-color-scheme: light)').matches)setTheme('light');
  else setTheme('dark');
})();

function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}

function renderMarkdown(text){
  var codeBlocks=[];
  text=text.replace(/```(\\w*)\\n([\\s\\S]*?)```/g,function(m,lang,code){
    var idx=codeBlocks.length;
    codeBlocks.push({lang:lang||'text',code:code});
    return '\\u0000CODE'+idx+'\\u0000';
  });

  text=esc(text);

  // Инлайн-код
  text=text.replace(/`([^`\\n]+)`/g,'<code class="inline">$1</code>');

  // Таблицы
  text=text.replace(/(^\\|.+\\|\\s*$\\n?)+/gm,function(block){
    var rows=block.trim().split('\\n').filter(function(r){return r.trim()});
    if(rows.length<2)return block;
    var header=rows[0].split('|').slice(1,-1).map(function(s){return s.trim()});
    var sep=rows[1];
    if(!/^[\\s\\|:\\-]+$/.test(sep))return block;
    var html='<table><thead><tr>';
    header.forEach(function(h){html+='<th>'+h+'</th>'});
    html+='</tr></thead><tbody>';
    for(var i=2;i<rows.length;i++){
      var cells=rows[i].split('|').slice(1,-1).map(function(s){return s.trim()});
      html+='<tr>';
      cells.forEach(function(c){html+='<td>'+c+'</td>'});
      html+='</tr>';
    }
    html+='</tbody></table>';
    return html;
  });

  text=text.replace(/^### (.+)$/gm,'<h3>$1</h3>');
  text=text.replace(/^## (.+)$/gm,'<h2>$1</h2>');
  text=text.replace(/^# (.+)$/gm,'<h1>$1</h1>');
  text=text.replace(/^&gt; (.+)$/gm,'<blockquote>$1</blockquote>');
  text=text.replace(/\\*\\*([^*]+)\\*\\*/g,'<strong>$1</strong>');
  text=text.replace(/(?<!\\*)\\*([^*]+)\\*(?!\\*)/g,'<em>$1</em>');
  text=text.replace(/\\[([^\\]]+)\\]\\(([^\\)]+)\\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>');
  text=text.replace(/^---$/gm,'<hr>');
  text=text.replace(/^[-*] (.+)$/gm,'<li>$1</li>');
  text=text.replace(/(<li>[\\s\\S]*?<\\/li>)/g,function(m){return '<ul>'+m+'</ul>'});

  text=text.split(/\\n{2,}/).map(function(chunk){
    if(/^<(h[1-6]|ul|ol|table|blockquote|hr|div)/.test(chunk.trim()))return chunk;
    return '<p>'+chunk.replace(/\\n/g,'<br>')+'</p>';
  }).join('');

  text=text.replace(/\\u0000CODE(\\d+)\\u0000/g,function(m,i){
    var b=codeBlocks[+i];
    var lang=b.lang;
    var isJson=(lang==='json');
    var label=isJson?'JSON':(lang||'CODE').toUpperCase();
    return '<div class="code-block"><span class="lang">'+label+'</span><button class="copy-btn" onclick="copyBlock(this)" title="Копировать" aria-label="Копировать">'+ICON_COPY+'</button><pre><code>'+esc(b.code)+'</code></pre></div>';
  });

  return text;
}

function copyBlock(btn){
  var pre=btn.parentElement.querySelector('pre');
  if(!pre)return;
  var text=pre.innerText;
  if(navigator.clipboard){
    navigator.clipboard.writeText(text).then(function(){
      btn.innerHTML=ICON_CHECK;
      btn.classList.add('copied');
      setTimeout(function(){btn.innerHTML=ICON_COPY;btn.classList.remove('copied')},1400);
    });
  }
}

function addMsg(role,text){
  var d=document.createElement('div');
  d.className='msg '+role;
  if(role==='bot'){d.innerHTML=renderMarkdown(text)}
  else{d.textContent=text}
  log.appendChild(d);
  log.scrollTop=log.scrollHeight;
}

function updateSendState(){
  var hasText=input.value.trim().length>0;
  if(hasText){sendBtn.classList.add('active');sendBtn.disabled=false}
  else{sendBtn.classList.remove('active');sendBtn.disabled=false}
}

async function send(){
  var text=input.value.trim();
  if(!text)return;
  addMsg('user',text);
  input.value='';
  input.style.height='auto';
  updateSendState();
  try{
    var r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:text,context:chatHistory})});
    var j=await r.json();
    if(j.ok && j.data && j.data.answer){
      addMsg('bot',j.data.answer);
      chatHistory.push({role:'user',content:text});
      chatHistory.push({role:'assistant',content:j.data.answer});
    }else if(j.error){
      addMsg('bot','**Ошибка:** '+(j.error.message||'неизвестно'));
    }else{
      addMsg('bot','**Ошибка:** пустой ответ');
    }
  }catch(e){
    addMsg('bot','**Ошибка сети:** '+e.message);
  }
}

input.addEventListener('keydown',function(e){
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}
});
input.addEventListener('input',function(){
  this.style.height='auto';
  this.style.height=Math.min(this.scrollHeight,200)+'px';
  updateSendState();
});
updateSendState();
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML

# A · импорт B в конце
import chat_b_chat