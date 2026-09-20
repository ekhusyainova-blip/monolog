# data_monolog.py — данные и точка входа AI Monolog
# Слой A. Конфиг, правила, FastAPI app, все роуты, интерфейс.
# 4 самодостаточных файла. Никаких внешних зависимостей.

import os
import re
import json
import time
import hmac
import logging
from typing import List

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("monolog")
SECRET_PATTERN = re.compile(r"(sk_[A-Za-z0-9_\-]{8,}|gsk_[A-Za-z0-9_\-]{8,}|Bearer\s+[A-Za-z0-9_\-\.]{10,})")

def safe_log(msg: str):
    log.info(SECRET_PATTERN.sub("[SECRET]", str(msg)))

# ================= ПРОВАЙДЕРЫ =================

PROVIDERS = {
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1/chat/completions",
        "models": {"light": "openai/gpt-oss-20b", "medium": "openai/gpt-oss-120b", "heavy": "qwen/qwen3.6-27b"},
        "all_models": ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.6-27b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        "reasoning_effort": True,
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1/chat/completions",
        "models": {"light": "openai/gpt-oss-20b:free", "medium": "openai/gpt-oss-120b:free", "heavy": "qwen/qwen-coder:free"},
        "all_models": ["openai/gpt-oss-20b:free", "openai/gpt-oss-120b:free", "qwen/qwen-coder:free", "meta-llama/llama-3.3-70b-instruct:free", "google/gemma-2-9b-it:free"],
        "reasoning_effort": False,
    },
    "cerebras": {
        "name": "Cerebras",
        "base_url": "https://api.cerebras.ai/v1/chat/completions",
        "models": {"light": "gpt-oss-20b", "medium": "gpt-oss-120b", "heavy": "gpt-oss-120b"},
        "all_models": ["gpt-oss-20b", "gpt-oss-120b", "llama3.1-8b", "llama3.1-70b"],
        "reasoning_effort": True,
    },
    "sambanova": {
        "name": "SambaNova",
        "base_url": "https://api.sambanova.ai/v1/chat/completions",
        "models": {"light": "Meta-Llama-3.3-70B-Instruct", "medium": "Meta-Llama-3.3-70B-Instruct", "heavy": "DeepSeek-V3.1"},
        "all_models": ["Meta-Llama-3.3-70B-Instruct", "Meta-Llama-3.1-8B-Instruct", "DeepSeek-V3.1"],
        "reasoning_effort": False,
    },
}

PROVIDER_URLS = {"groq": "https://console.groq.com/keys", "openrouter": "https://openrouter.ai/keys",
                 "cerebras": "https://cloud.cerebras.ai", "sambanova": "https://cloud.sambanova.ai"}

# ================= ПРАВИЛА =================

MODEL_RULES = {
    "heavy_keywords": ["статья", "лонгрид", "пост", "напиши", "проанализируй", "анализ",
                       "план", "стратег", "архитектур", "спроектируй", "разработай",
                       "документ", "тз", "отчёт", "отчет"],
    "long_message_threshold": 200,
    "strategic_levels": ["strategic", "systemic"],
}

PROVIDER_ERRORS = {
    429: "Лимит вашего ключа исчерпан. Повторите через {retry} сек.",
    402: "На провайдере закончились кредиты. Пополните баланс или смените провайдера.",
    401: "Ключ не принят провайдером. Проверьте ключ в настройках → Ключ API.",
    403: "Ключ не принят провайдером. Проверьте ключ в настройках → Ключ API.",
    413: "Запрос слишком длинный. Сократите или прикрепите файл.",
    500: "{name} недоступен. Попробуйте позже.",
    502: "{name} недоступен. Попробуйте позже.",
}

# ================= ЛИМИТЫ =================

MAX_TOKENS = 3500
META_MAX_TOKENS = 800
TIMEOUT = 120.0
MAX_MESSAGE_LEN = 8000
SOFT_MESSAGE_LEN = 4000
MAX_ATTACH_LEN = 3000
MAX_ATTACHMENTS = 3
MAX_BODY_BYTES = 200_000

# ================= ENV =================

_DEV_KEYS_GROQ: List[str] = [k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",") if k.strip()]
ALLOW_BYOK = os.getenv("ALLOW_BYOK", "true").lower() == "true"
MANAGEMENT_KEY = os.getenv("MANAGEMENT_KEY", "").strip()
AUTHOR_SECRET = os.getenv("AUTHOR_SECRET", "").strip()
CORS_ORIGINS_ENV = os.getenv("CORS_ORIGINS", "*").strip()
CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS_ENV.split(",") if o.strip()] or ["*"]

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "ekhusyainova-blip/monolog").strip()
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()
CODE_BRANCH = os.getenv("CODE_BRANCH", "dev").strip()
GITHUB_API = "https://api.github.com"

PATHS = {"blog": "blog/posts.json", "releases": "releases.json",
         "templates": "public/templates.json", "lots": "public/lots.json",
         "reviews": "public/reviews.json", "reputation": "public/reputation.json"}

# ================= ПРОМПТЫ (внутри файла) =================

LAYER_A = ""
LAYER_B = ""
LAYER_A_CONTENT = ""

# ================= МЕТРИКИ =================

BASE_METRICS = {
    "stability_index": 0.0, "indicator_status": "success", "cycles_completed": 0,
    "lots_balance": "+0.0", "index_delta": None, "mind_scale": "micro",
    "human_contribution": 0.0, "cognitive_pulse": "stable", "mode_suggested": "analyst",
    "layer_marker": None, "ai_note": None, "learning_template": None,
    "reset_proposal": None, "reminder": None, "value_choices": [], "risk_intercept": None,
    "social_adaptation": {"active": False, "reason": None, "level": "inactive"},
    "dominant_trait": {"detected": False, "influence": None, "risk": None,
                       "stability_delta": 0.0, "hint": None, "steps": []},
    "passport": {"level": "micro", "title": None, "goal": None, "result": None,
                 "mission": None, "values": [], "constraints": [], "stakeholders": [],
                 "risks": [], "metrics": [], "completion": 0},
    "profile": {"values": {}, "patterns": [], "distortions": [], "insights": [],
                "somatic": {"energy": 0.5, "tension": 0.3, "focus": 0.5, "mood": None, "note": None},
                "skills": []},
    "dimension": None, "priority_drift": None, "mood_board": None,
    "ideas": [], "artifacts": [], "protocol_integrity": True, "management_mode": False,
    "public_index": {"given": 0, "taken": 0, "help_score": 0, "reputation": 0},
}

# ================= ИНТЕРФЕЙС =================

INDEX_HTML = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Monolog</title>
<style>
*{box-sizing:border-box}
body{margin:0;font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:#fafafa;color:#111}
header{padding:12px 16px;border-bottom:1px solid #e5e5e5;display:flex;justify-content:space-between;align-items:center;background:#fff;position:sticky;top:0;z-index:5}
header h1{font-size:17px;margin:0;font-weight:600}
header .status{font-size:12px;color:#666}
#log{padding:16px;max-width:820px;margin:0 auto}
.msg{margin:16px 0}
.msg.user .body{background:#eef4ff;padding:10px 14px;border-radius:14px;white-space:pre-wrap;word-break:break-word}
.msg.assistant .body{white-space:pre-wrap;word-break:break-word}
.block{background:#f4f4f4;border-radius:10px;margin:8px 0;overflow:hidden;border:1px solid #e5e5e5}
.block .head{display:flex;justify-content:space-between;align-items:center;padding:6px 12px;font-size:12px;color:#666;border-bottom:1px solid #e5e5e5;background:#efefef}
.block pre{margin:0;padding:12px;overflow-x:auto;font:13px/1.45 ui-monospace,Menlo,monospace;white-space:pre}
.copy{cursor:pointer;border:0;background:transparent;color:#555;font-size:12px;padding:2px 6px;border-radius:6px}
.copy:hover{background:#e0e0e0}
#bar{position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid #e5e5e5;padding:10px 16px;display:flex;gap:8px;max-width:820px;margin:0 auto}
#bar textarea{flex:1;resize:none;border:1px solid #ddd;border-radius:12px;padding:10px 12px;font:15px/1.4 inherit;min-height:46px;max-height:200px;outline:none}
#bar textarea:focus{border-color:#888}
#bar button{border:0;background:#111;color:#fff;border-radius:12px;padding:0 20px;cursor:pointer;font-size:15px}
#bar button:disabled{background:#999;cursor:default}
#status{font-size:12px;color:#888;padding:4px 16px;max-width:820px;margin:0 auto}
</style></head><body>
<header>
  <h1>Monolog</h1>
  <span class="status" id="hdr">готов</span>
</header>
<div id="status">Напишите сообщение, чтобы начать.</div>
<div id="log"></div>
<div id="bar">
  <textarea id="inp" placeholder="Напишите сообщение…" rows="1"></textarea>
  <button id="send" onclick="send()">→</button>
</div>
<script>
const logEl=document.getElementById('log'),inp=document.getElementById('inp'),st=document.getElementById('status'),hdr=document.getElementById('hdr'),btn=document.getElementById('send');
let lastMetrics={};
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function renderBlocks(blocks){return blocks.map(b=>{
  if(b.type==='text')return '<div class="body">'+esc(b.content)+'</div>';
  return '<div class="block"><div class="head"><span>'+esc(b.lang||b.type)+'</span><button class="copy" onclick="cp(this)">Копировать</button></div><pre>'+esc(b.content)+'</pre></div>';
}).join('')}
function addMsg(role,blocks){const d=document.createElement('div');d.className='msg '+role;d.innerHTML=renderBlocks(blocks);logEl.appendChild(d);window.scrollTo(0,document.body.scrollHeight);return d}
function cp(b){const pre=b.closest('.block').querySelector('pre');navigator.clipboard.writeText(pre.textContent);b.textContent='скопировано';setTimeout(()=>b.textContent='Копировать',900)}
function parseBlocks(text){const blocks=[];let buf='',i=0;text=text||'';
  while(i<text.length){if(text.startsWith('```',i)){if(buf.trim()){blocks.push({type:'text',content:buf});buf=''}
    const j=text.indexOf('\\n',i+3),lang=j>=0?text.slice(i+3,j).trim():'';
    const end=j>=0?text.indexOf('```',j+1):-1;if(end<0){buf+=text.slice(i);break}
    const body=text.slice(j+1,end);
    const isJson=body.trim().startsWith('{')||body.trim().startsWith('[');
    blocks.push({type:lang.toLowerCase()==='json'||(lang===''&&isJson)?'json':'code',lang:lang||'text',content:body.replace(/\\n$/,'')});i=end+3}
  else{buf+=text[i];i++}}
  if(buf.trim())blocks.push({type:'text',content:buf});
  if(!blocks.length)blocks.push({type:'text',content:text});
  return blocks}
async function send(){
  const t=inp.value.trim();if(!t)return;
  addMsg('user',[{type:'text',content:t}]);
  inp.value='';btn.disabled=true;st.textContent='Monolog думает…';hdr.textContent='думает';
  try{
    const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:t,carried_metrics:lastMetrics})});
    const d=await r.json();
    if(!r.ok){st.textContent='Ошибка: '+(d.detail||r.status);hdr.textContent='ошибка';addMsg('assistant',[{type:'text',content:'Ошибка: '+(d.detail||'неизвестная')}]);return}
    lastMetrics=d.metrics||{};
    addMsg('assistant',parseBlocks(d.reply_text||''));
    st.textContent='Готово. Провайдер: '+(d.provider_used||'?')+', модель: '+(d.model_used||'?')+', ключ: '+(d.key_source||'?');
    hdr.textContent='готов';
  }catch(e){st.textContent='Ошибка сети: '+e.message;hdr.textContent='ошибка'}
  finally{btn.disabled=false;inp.focus()}
}
inp.addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();send()}});
async function ping(){try{const r=await fetch('/health');const d=await r.json();hdr.textContent='готов · ключей '+d.dev_keys}catch(e){}}
ping();
</script></body></html>"""

# ================= FASTAPI =================

app = FastAPI(title="Monolog")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS,
                   allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], allow_headers=["*"])

@app.middleware("http")
async def limit_body(request: Request, call_next):
    if request.method in ("POST", "PUT"):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > MAX_BODY_BYTES:
            return JSONResponse({"detail": "Запрос слишком большой. Сократите или прикрепите файл."}, status_code=413)
    return await call_next(request)

# ================= ПРОВЕРКИ =================

def _safe_eq(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return hmac.compare_digest(a, b)

def check_author(request: Request):
    if not AUTHOR_SECRET:
        raise HTTPException(status_code=503, detail="Ключ автора не настроен")
    key = request.headers.get("X-Author-Key", "").strip()
    if not _safe_eq(key, AUTHOR_SECRET):
        raise HTTPException(status_code=403, detail="Неверный ключ автора. Проверьте в настройках.")

def check_management(request: Request):
    if not MANAGEMENT_KEY:
        raise HTTPException(status_code=503, detail="Ключ Управления не настроен")
    key = request.headers.get("X-Management-Key", "").strip()
    if not _safe_eq(key, MANAGEMENT_KEY):
        raise HTTPException(status_code=403, detail="Неверный ключ Управления. Проверьте в настройках.")

# ================= РОУТЫ: БАЗОВЫЕ =================

@app.get("/", response_class=HTMLResponse)
async def root():
    return INDEX_HTML

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0", "dev_keys": len(_DEV_KEYS_GROQ), "byok": ALLOW_BYOK,
            "blog_ready": bool(GITHUB_TOKEN), "public_ready": bool(GITHUB_TOKEN),
            "author_secret_set": bool(AUTHOR_SECRET), "management_key_set": bool(MANAGEMENT_KEY),
            "providers": list(PROVIDERS.keys()), "cors": CORS_ORIGINS,
            "limits": {"max_message_len": MAX_MESSAGE_LEN, "soft_message_len": SOFT_MESSAGE_LEN,
                       "max_tokens": MAX_TOKENS, "meta_max_tokens": META_MAX_TOKENS},
            "prompts_loaded": {"layer_a": bool(LAYER_A), "layer_b": bool(LAYER_B),
                               "layer_a_content": bool(LAYER_A_CONTENT)}}

@app.get("/providers")
async def providers_info():
    out = [{"id": pid, "name": cfg["name"], "url": PROVIDER_URLS.get(pid, ""),
            "models": list(cfg.get("all_models") or [])} for pid, cfg in PROVIDERS.items()]
    return JSONResponse({"providers": out})

# ================= РОУТ: ЧАТ =================

@app.post("/chat")
async def chat(request: Request):
    import interpret_monolog as B
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Некорректный формат запроса")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Тело запроса должно быть объектом")
    B.EVENTS.clear()
    B.emit("chat_request", {"body": body, "request": request})
    if B.EVENTS:
        ev = B.EVENTS[-1]
        if ev["type"] == "chat_response":
            return JSONResponse(ev["data"])
        if ev["type"] == "error":
            raise HTTPException(status_code=ev["data"].get("status", 500), detail=ev["data"].get("detail", "Ошибка"))
    raise HTTPException(status_code=502, detail="Провайдер недоступен. Попробуйте позже.")

# ================= РОУТЫ: ПУБЛИЧНЫЙ СЛОЙ =================

@app.get("/public/templates")
async def public_templates_list(sort: str = "new", limit: int = 100):
    import meta_monolog as D
    return JSONResponse(await D.pub_templates_list(sort, limit))

@app.post("/public/templates")
async def public_templates_publish(request: Request):
    import meta_monolog as D
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Тело запроса должно быть объектом")
    return JSONResponse(await D.pub_templates_publish(body))

@app.get("/public/lots")
async def public_lots_list(sort: str = "new", limit: int = 100):
    import meta_monolog as D
    return JSONResponse(await D.pub_lots_list(sort, limit))

@app.post("/public/lots")
async def public_lots_publish(request: Request):
    import meta_monolog as D
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Тело запроса должно быть объектом")
    return JSONResponse(await D.pub_lots_publish(body))

@app.post("/public/take")
async def public_take(request: Request):
    import meta_monolog as D
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Тело запроса должно быть объектом")
    return JSONResponse(await D.pub_take(body))

@app.post("/public/review")
async def public_review(request: Request):
    import meta_monolog as D
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Тело запроса должно быть объектом")
    return JSONResponse(await D.pub_review(body))

@app.get("/public/profile/{uid}")
async def public_profile(uid: str):
    import meta_monolog as D
    return JSONResponse(await D.pub_profile(uid))

# ================= РОУТЫ: БЛОГ =================

@app.get("/blog")
async def blog_list():
    import meta_monolog as D
    return JSONResponse(await D.blog_list())

@app.get("/blog/{post_id}")
async def blog_get(post_id: str):
    import meta_monolog as D
    return JSONResponse(await D.blog_get(post_id))

@app.post("/blog/publish")
async def blog_publish(request: Request):
    import meta_monolog as D
    check_author(request)
    body = await request.json()
    return JSONResponse(await D.blog_publish(body))

@app.delete("/blog/{post_id}")
async def blog_delete(post_id: str, request: Request):
    import meta_monolog as D
    check_author(request)
    return JSONResponse(await D.blog_delete(post_id))

# ================= РОУТЫ: КОД =================

@app.get("/code/read")
async def code_read(request: Request, path: str):
    import meta_monolog as D
    check_author(request)
    return JSONResponse(await D.code_read(path))

@app.post("/code/save")
async def code_save(request: Request):
    import meta_monolog as D
    check_author(request)
    body = await request.json()
    return JSONResponse(await D.code_save(body))

# ================= РОУТЫ: РЕЛИЗЫ И УПРАВЛЕНИЕ =================

@app.get("/releases")
async def releases_list():
    import meta_monolog as D
    return JSONResponse(await D.releases_list())

@app.post("/releases/save")
async def releases_save(request: Request):
    import meta_monolog as D
    check_author(request)
    body = await request.json()
    return JSONResponse(await D.releases_save(body))

@app.post("/management/check")
async def management_check(request: Request):
    check_management(request)
    return JSONResponse({"ok": True, "management_mode": True})

# ================= ЗАГРУЗКА СЛОЁВ =================

import interpret_monolog  # noqa: F401