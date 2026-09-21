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
  --bg:#0f0f10;--fg:#e8e8ea;--muted:#7a7a80;
  --user-bg:#1a1a1d;--accent:#6ea8fe;--border:#1e1e21;
  --code-bg:#141417;--code-border:#1e1e21;
}
:root[data-theme="light"]{
  --bg:#fbfbfc;--fg:#1a1a1c;--muted:#8a8a8f;
  --user-bg:#efeff2;--accent:#2563eb;--border:#e7e7ea;
  --code-bg:#f4f4f6;--code-border:#e7e7ea;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{
  font:15px/1.65 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,sans-serif;
  background:var(--bg);color:var(--fg);
  display:flex;flex-direction:column;
  -webkit-font-smoothing:antialiased;
  text-rendering:optimizeLegibility;
}
.wrap{
  width:100%;max-width:780px;margin:0 auto;
  display:flex;flex-direction:column;flex:1;min-height:0;
  height:100dvh;
}
header{
  display:flex;align-items:center;justify-content:space-between;
  padding:14px 18px;flex-shrink:0;
}
.title{font-size:13px;color:var(--muted);letter-spacing:0.3px;font-weight:500}
.icon-btn{
  background:none;border:none;color:var(--muted);
  width:32px;height:32px;border-radius:8px;cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  transition:background 0.15s,color 0.15s;
}
.icon-btn:hover{background:var(--user-bg);color:var(--fg)}
.icon-btn svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round}

#log{
  flex:1;min-height:0;overflow-y:auto;
  padding:8px 18px 24px;
  display:flex;flex-direction:column;gap:20px;
  scroll-behavior:smooth;
}
#log::-webkit-scrollbar{width:6px}
#log::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}

.msg{display:flex;flex-direction:column;max-width:100%}
.msg.user{
  align-self:flex-end;max-width:85%;
  background:var(--user-bg);
  padding:10px 14px;border-radius:14px;
  font-size:15px;line-height:1.5;
}
.msg.bot{
  align-self:stretch;background:none;padding:0;
  font-size:15px;line-height:1.7;
}
.msg.bot p{margin:0 0 10px}
.msg.bot p:last-child{margin-bottom:0}
.msg.bot strong{font-weight:600;color:var(--fg)}
.msg.bot em{font-style:italic;color:var(--muted)}
.msg.bot h1,.msg.bot h2,.msg.bot h3{margin:16px 0 8px;font-weight:600;line-height:1.3}
.msg.bot h1{font-size:18px}
.msg.bot h2{font-size:16px}
.msg.bot h3{font-size:15px;color:var(--muted);text-transform:uppercase;letter-spacing:0.5px}
.msg.bot ul,.msg.bot ol{margin:8px 0 12px 22px}
.msg.bot li{margin:4px 0}
.msg.bot a{color:var(--accent);text-decoration:none;border-bottom:1px solid color-mix(in srgb,var(--accent) 40%,transparent)}
.msg.bot a:hover{border-bottom-color:var(--accent)}
.msg.bot hr{border:none;border-top:1pxvar(-- solid var(--border);marginm:18px 0}
.utedmsg.bot blockquote);
{border-left:2px solid var(--border);padding:2px 0 2px 12px;margin:8px 0;color:var(--muted)}

.code-block{
  position:relative;margin:12px 0;
  background:var(--code-bg);border:1px solid var(--code-border);
  border-radius:10px;overflow:hidden;
}
.code-block .lang{
  position:absolute;top:8px;left:12px;
  font-size:10px;color:var(--muted);
  text-transform:uppercase;letter-spacing:0.6px;font-weight:500;
}
.code-block pre{
  padding:34px 14px 14px;
  overflow-x:auto;
  font:13px/1.6 ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
  white-space:pre;margin:0;color:var(--fg);
}
.code-block .copy-btn{
  position:absolute;top:6px;right:6px;
  background:transparent;border:1px solid transparent;
  color:  width:28px;height:28px;border-radius:6px;cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  transition:background 0.15s,color 0.15s,border-color 0.15s;
}
.code-block .copy-btn:hover{background:var(--bg);border-color:var(--code-border);color:var(--fg)}
.code-block .copy-btn svg{width:14px;height:14px;stroke:currentColor;fill:none;stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round}
.code-block .copy-btn.copied{color:var(--accent)}

table{
  width:100%;border-collapse:collapse;margin:12px 0;
  font-size:14px;
}
table th,table td{
  padding:8px 12px;text-align:left;
  border-bottom:1px solid var(--border);
}
table th{font-weight:600;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:0.4px}
table tr:last-child td{border-bottom:none}

footer{
  flex-shrink:0;
  padding:10px 18px calc(14px + env(safe-area-inset-bottom, 0px));
  background:var(--bg);
  border-top:1px solid var(--border);
}
.input-row{
  display:flex;gap:8px;align-items:flex-end;
  background:var(--user-bg);
  border-radius:14px;padding:6px 6px 6px 14px;
}
textarea{
  flex:1;resize:none;background:none;color:var(--fg);
  border:none;outline:none;
  padding:8px 0;font:inherit;line-height:1.5;
  min-height:24px;max-height:160px;
  white-space:pre-wrap;
}
textarea::placeholder{color:var(--muted)}
button.send{
  background:var(--accent);color:#fff;
  border:none;border-radius:10px;
  width:36px;height:36px;flex-shrink:0;
  cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  transition:opacity 0.15s,transform 0.1s;
}
button.send:hover{opacity:0.9}
button.send:active{transform:scale(0.96)}
button.send:disabled{opacity:0.35;cursor:not-allowed}
button.send svg{width:18px;height:18px;stroke:#fff;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}

@media (max-width:600px){
  body{font-size:15px}
  header{padding:12px 14px}
  #log{padding:6px 14px 20px;gap:18px}
  footer{padding:8px 14px calc(12px + env(safe-area-inset-bottom, 0px))}
  .msg.user{max-width:88%}
  .code-block pre{font-size:12px;padding:32px 12px 12px}
  table{font-size:13px}
  table th,table td{padding:6px 8px}
}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="title">Monolog</div>
  <button class="icon-btn" id="theme" onclick="toggleTheme()" title="Тема" aria-label="Тема"></button>
</header>
<div id="log"></div>
<footer>
  <div class="input-row">
    <textarea id="input" placeholder="Напиши..." rows="1"></textarea>
    <button class="send" id="send" onclick="send()" title="Отправить" aria-label="Отправить">
      <svg viewBox="0 0 24 24"><path d="M5 12h14M13 5l7 7-7 7"/></svg>
    </button>
  </div>
</footer>
</div>
<script>
var log=document.getElementById('log');
var input=document.getElementById('input');
var sendBtn=document.getElementById('send');
var themeBtn=document.getElementById('theme');
var chatHistory=[];

var ICON_SUN='<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
var ICON_MOON='<svg viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';
var ICON_COPY='<svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
var ICON_CHECK='<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>';

function setTheme(t){
  document.documentElement.setAttribute('data-theme',t);
  localStorage.setItem('monolog_theme',t);
  themeBtn.innerHTML=(t==='dark')?ICON_SUN:ICON_MOON;
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

  // Заголовки
  text=text.replace(/^### (.+)$/gm,'<h3>$1</h3>');
  text=text.replace(/^## (.+)$/gm,'<h2>$1</h2>');
  text=text.replace(/^# (.+)$/gm,'<h1>$1</h1>');

  // Цитаты
  text=text.replace(/^&gt; (.+)$/gm,'<blockquote>$1</blockquote>');

  // Жирный / курсив
  text=text.replace(/\\*\\*([^*]+)\\*\\*/g,'<strong>$1</strong>');
  text=text.replace(/(?<!\\*)\\*([^*]+)\\*(?!\\*)/g,'<em>$1</em>');

  // Ссылки
  text=text.replace(/\\[([^\\]]+)\\]\\(([^\\)]+)\\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>');

  // Разделитель
  text=text.replace(/^---$/gm,'<hr>');

  // Списки
  text=text.replace(/^[-*] (.+)$/gm,'<li>$1</li>');
  text=text.replace(/(<li>[\\s\\S]*?<\\/li>)/g,function(m){return '<ul>'+m+'</ul>'});

  // Параграфы (одиночные строки, если не блок)
  text=text.split(/\\n{2,}/).map(function(chunk){
    if(/^<(h[1-6]|ul|ol|table|blockquote|hr|div)/.test(chunk.trim()))return chunk;
    return '<p>'+chunk.replace(/\\n/g,'<br>')+'</p>';
  }).join('');

  // Возврат код-блоков
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

async function send(){
  var text=input.value.trim();
  if(!text)return;
  addMsg('user',text);
  input.value='';
  input.style.height='auto';
  sendBtn.disabled=true;
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
  }finally{
    sendBtn.disabled=false;
  }
}

input.addEventListener('keydown',function(e){
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}
});
input.addEventListener('input',function(){
  this.style.height='auto';
  this.style.height=Math.min(this.scrollHeight,160)+'px';
});
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML

# A · импорт B в конце
import chat_b_chat