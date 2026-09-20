# data_chat.py — данные и точка входа блока чата AI Monolog
# Слой A. FastAPI-приложение, роуты, фронт, данные.

import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

app = FastAPI(title="AI Monolog Chat")

# ================= ДАННЫЕ =================

PROVIDERS = [
    {"id": "groq", "name": "Groq", "base_url": "https://api.groq.com/openai/v1",
     "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
     "model_default": "llama-3.3-70b-versatile", "priority": 1, "enabled": True,
     "keys": ["groq_1", "groq_2", "groq_3", "groq_4", "groq_5"]},
    {"id": "openrouter", "name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1",
     "models": ["meta-llama/llama-3.3-70b-instruct:free", "google/gemma-2-9b-it:free"],
     "model_default": "meta-llama/llama-3.3-70b-instruct:free", "priority": 2, "enabled": True,
     "keys": []},
    {"id": "cerebras", "name": "Cerebras", "base_url": "https://api.cerebras.ai/v1",
     "models": ["llama3.3-70b", "llama3.1-8b"], "model_default": "llama3.3-70b",
     "priority": 3, "enabled": True, "keys": []},
    {"id": "sambanova", "name": "SambaNova", "base_url": "https://api.sambanova.ai/v1",
     "models": ["Meta-Llama-3.3-70B-Instruct", "Meta-Llama-3.1-8B-Instruct"],
     "model_default": "Meta-Llama-3.3-70B-Instruct", "priority": 4, "enabled": True, "keys": []},
    {"id": "custom", "name": "Свой", "base_url": "", "models": [], "model_default": "",
     "priority": 5, "enabled": False, "keys": []},
]

KEYS = [
    {"id": f"groq_{i}", "provider_id": "groq", "label": f"Ключ {i}",
     "env_name": f"GROQ_KEY_{i}", "value": "", "state": "ok",
     "cooldown_until": 0, "last_used": 0, "source": "env"}
    for i in range(1, 6)
]

PROMPTS = [
    {"id": "p_a_1", "slot": "layer_a", "name": "default", "text": "", "active": False, "slot_enabled": False, "source": "local", "file_path": "", "ts": 0},
    {"id": "p_a_2", "slot": "layer_a", "name": "strict", "text": "", "active": False, "slot_enabled": False, "source": "local", "file_path": "", "ts": 0},
    {"id": "p_b_1", "slot": "layer_b", "name": "default", "text": "", "active": False, "slot_enabled": False, "source": "local", "file_path": "", "ts": 0},
    {"id": "p_c_1", "slot": "layer_c", "name": "default", "text": "", "active": False, "slot_enabled": False, "source": "local", "file_path": "", "ts": 0},
    {"id": "p_d_1", "slot": "layer_d", "name": "default", "text": "", "active": False, "slot_enabled": False, "source": "local", "file_path": "", "ts": 0},
    {"id": "p_ac_1", "slot": "layer_a_content", "name": "base", "text": "", "active": False, "slot_enabled": False, "source": "local", "file_path": "", "ts": 0},
]

PROMPT_SLOTS = ["layer_a", "layer_b", "layer_c", "layer_d", "layer_a_content"]
MESSAGES = []
CONTEXTS = []

SETTINGS = {
    "provider_mode": "auto", "manual_provider_id": "", "manual_key_id": "",
    "autosave_enabled": True, "autosave_every_n": 20,
    "autoclean_mb": 4, "autoclean_days": 30, "stream": True,
}

UI_STATES = {
    "key_states": {
        "ok": {"label": "работает", "color": "#2e7d32"},
        "cooldown": {"label": "остывает", "color": "#f9a825"},
        "exhausted": {"label": "исчерпан", "color": "#c62828"},
    },
    "providers_mode": {"auto": "Авто (по приоритету)", "manual": "Вручную"},
    "blocks": {
        "text": {"bg": "transparent", "copy": True},
        "code": {"bg": "#f4f4f4", "copy": True},
        "json": {"bg": "#f4f4f4", "copy": True},
    },
}

# ================= ФРОНТ =================

CHAT_HTML = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Monolog Chat</title>
<style>
*{box-sizing:border-box}body{margin:0;font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:#fff;color:#111}
header{padding:10px 14px;border-bottom:1px solid #e5e5e5;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;background:#fff;z-index:5}
header h1{font-size:16px;margin:0}
#log{padding:10px 14px 120px;max-width:820px;margin:0 auto}
.msg{margin:14px 0}
.msg.user .body{background:#eef4ff;padding:10px 12px;border-radius:12px;white-space:pre-wrap;word-break:break-word}
.msg.assistant .body{white-space:pre-wrap;word-break:break-word}
.block{background:#f4f4f4;border-radius:10px;margin:8px 0;overflow:hidden}
.block .head{display:flex;justify-content:space-between;align-items:center;padding:6px 10px;font-size:12px;color:#666;border-bottom:1px solid #e5e5e5}
.block pre{margin:0;padding:10px 12px;overflow-x:auto;font:13px/1.45 ui-monospace,Menlo,monospace;white-space:pre}
.copy{cursor:pointer;border:0;background:transparent;color:#555;font-size:12px}
#bar{position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid #e5e5e5;padding:8px 14px;display:flex;gap:8px;max-width:820px;margin:0 auto}
#bar textarea{flex:1;resize:none;border:1px solid #ddd;border-radius:10px;padding:8px 10px;font:15px/1.4 inherit;min-height:44px;max-height:180px}
#bar button{border:0;background:#111;color:#fff;border-radius:10px;padding:0 16px;cursor:pointer}
.status{font-size:12px;color:#888;padding:2px 14px}
</style></head><body>
<header>
  <h1>AI Monolog Chat</h1>
  <button class="copy" onclick="loadSnapshot()">обновить</button>
</header>
<div class="status" id="status">готов</div>
<div id="log"></div>
<div id="bar">
  <textarea id="inp" placeholder="Напишите сообщение…"></textarea>
  <button onclick="send()">→</button>
</div>
<script>
const log=document.getElementById('log'),inp=document.getElementById('inp'),st=document.getElementById('status');
let cur=null,curBuf='';
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function renderBlocks(blocks){return blocks.map(b=>{
  if(b.type==='text')return '<div class="body">'+esc(b.content)+'</div>';
  return '<div class="block"><div class="head"><span>'+esc(b.lang||b.type)+'</span><button class="copy" onclick="cp(this)">Копировать</button></div><pre>'+esc(b.content)+'</pre></div>';
}).join('')}
function addMsg(role,blocks){const d=document.createElement('div');d.className='msg '+role;d.innerHTML=renderBlocks(blocks);log.appendChild(d);window.scrollTo(0,document.body.scrollHeight);return d}
function cp(btn){const pre=btn.closest('.block').querySelector('pre');navigator.clipboard.writeText(pre.textContent);btn.textContent='скопировано';setTimeout(()=>btn.textContent='Копировать',900)}
async function send(){
  const t=inp.value.trim();if(!t)return;
  addMsg('user',[{type:'text',content:t}]);
  inp.value='';cur=addMsg('assistant',[{type:'text',content:''}]);curBuf='';st.textContent='думает…';
  const r=await fetch('/chat/stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t})});
  const rd=r.body.getReader(),dec=new TextDecoder();let buf='';
  while(true){const {done,value}=await rd.read();if(done)break;buf+=dec.decode(value,{stream:true});
    let idx;while((idx=buf.indexOf('\\n\\n'))>=0){const ev=buf.slice(0,idx);buf=buf.slice(idx+2);handle(ev)}}
  st.textContent='готов';
}
function handle(ev){
  const lines=ev.split('\\n');let type='message',data='';
  for(const l of lines){if(l.startsWith('event:'))type=l.slice(6).trim();else if(l.startsWith('data:'))data+=l.slice(5).trim()}
  if(type==='chunk'){curBuf+=JSON.parse(data).text;cur.innerHTML=renderBlocks(parse(curBuf))}
  else if(type==='status'){st.textContent=JSON.parse(data).state==='start'?'печатает…':'готов'}
  else if(type==='error'){st.textContent='ошибка: '+JSON.parse(data).msg}
}
function parse(text){const blocks=[];let buf='',i=0;
  while(i<text.length){if(text.startsWith('```',i)){if(buf.trim()){blocks.push({type:'text',content:buf});buf=''}
    const j=text.indexOf('\\n',i+3),lang=j>=0?text.slice(i+3,j).trim():'';
    const end=j>=0?text.indexOf('```',j+1):-1;if(end<0){buf+=text.slice(i);break}
    const body=text.slice(j+1,end);
    const isJson=body.trim().startsWith('{')||body.trim().startsWith('[');
    blocks.push({type:lang.toLowerCase()==='json'||(lang===''&&isJson)?'json':'code',lang:lang||'text',content:body.replace(/\\n$/,'')});i=end+3}
  else{buf+=text[i];i++}}
  if(buf.trim())blocks.push({type:'text',content:buf});return blocks}
async function loadSnapshot(){const r=await fetch('/chat/snapshot');const d=await r.json();st.textContent='провайдеров: '+d.providers.length+', ключей: '+d.keys.length+', сообщений: '+d.messages_count}
loadSnapshot();
</script></body></html>"""

# ================= РОУТЫ =================

@app.get("/", response_class=HTMLResponse)
async def root():
    return CHAT_HTML

@app.get("/chat", response_class=HTMLResponse)
async def chat_page():
    return CHAT_HTML

@app.get("/health")
async def health():
    return {"ok": True, "service": "ai-monolog-chat", "messages": len(MESSAGES)}

@app.get("/chat/snapshot")
async def snapshot():
    return {
        "providers": PROVIDERS,
        "keys": [{k: v for k, v in key.items() if k != "value"} for key in KEYS],
        "prompts": PROMPTS,
        "settings": SETTINGS,
        "states": UI_STATES,
        "contexts": CONTEXTS,
        "messages_count": len(MESSAGES),
    }

@app.post("/chat/stream")
async def chat_stream(request: Request):
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "пустое сообщение"}, status_code=400)
    import interpret_chat
    interpret_chat.emit("user_message", {"text": text})
    async def gen():
        while True:
            if interpret_chat.EVENTS:
                ev = interpret_chat.EVENTS.pop(0)
                yield f"event: {ev['type']}\ndata: {json.dumps(ev['data'], ensure_ascii=False)}\n\n"
            else:
                break
    return StreamingResponse(gen(), media_type="text/event-stream")

# ================= ЗАПУСК СЛОЁВ =================

import solve_chat
import meta_chat