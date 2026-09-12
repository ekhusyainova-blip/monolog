# app.py
# Monolog — stateless-прокси к Groq + блог + Word-экспорт.
# Ротация моделей: gpt-oss-20b / gpt-oss-120b / qwen3.6-27b.
# Слой B НЕ отправляется. История НЕ отправляется.

import os
import re
import json
import time
import base64
import logging
import itertools
from io import BytesIO
from typing import Optional, List, Dict, Any

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("monolog")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MAX_TOKENS = 2500
TIMEOUT = 90.0

# --- Актуальные модели Groq (после 16.08.2026) ---
MODEL_LIGHT = "openai/gpt-oss-20b"
MODEL_MEDIUM = "openai/gpt-oss-120b"
MODEL_HEAVY = "qwen/qwen3.6-27b"

_DEV_KEYS: List[str] = [k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",") if k.strip()]
_dev_key_cycle = itertools.cycle(_DEV_KEYS) if _DEV_KEYS else None
ALLOW_BYOK = os.getenv("ALLOW_BYOK", "true").lower() == "true"

# --- Blog config ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.getenv("GITHUB_REPO", "ekhusyainova-blip/monolog").strip()
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()
BLOG_PATH = "blog/posts.json"
AUTHOR_SECRET = os.getenv("AUTHOR_SECRET", "").strip()


def _load(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        log.warning(f"Prompt file not found: {path}")
        return ""

LAYER_A = _load("prompts/layer_a.txt")


def mask_key(key: str) -> str:
    if not key or len(key) < 12:
        return "***"
    return f"{key[:6]}...{key[-4:]}"


def next_dev_key() -> Optional[str]:
    if not _dev_key_cycle:
        return None
    return next(_dev_key_cycle)


def pick_key(request: Request):
    if ALLOW_BYOK:
        user_key = request.headers.get("X-Groq-Key", "").strip()
        if user_key.startswith("gsk_"):
            return user_key, "user"
    dev = next_dev_key()
    if dev:
        return dev, "developer"
    return None, "none"


def check_author(request: Request):
    if not AUTHOR_SECRET:
        raise HTTPException(status_code=503, detail="AUTHOR_SECRET не настроен на сервере")
    key = request.headers.get("X-Author-Key", "").strip()
    if key != AUTHOR_SECRET:
        raise HTTPException(status_code=403, detail="Неверный ключ автора")


def pick_model(user_message: str, carried_metrics: Optional[Dict[str, Any]] = None) -> str:
    """Ротация по эвристике.
    Сложные задачи → qwen3.6-27b.
    Средние → gpt-oss-120b.
    Простые → gpt-oss-20b.
    """
    text = (user_message or "").lower()

    # Тяжёлые — статьи, анализ, планы, стратегии
    heavy_keywords = [
        "статья", "лонгрид", "пост", "напиши",
        "проанализируй", "анализ", "план", "стратег",
        "архитектур", "спроектируй", "разработай",
        "документ", "тз", "отчёт", "отчет",
    ]
    if any(kw in text for kw in heavy_keywords):
        return MODEL_HEAVY

    # Средние — длинные запросы или стратегический проект
    if len(user_message or "") > 200:
        return MODEL_MEDIUM
    if carried_metrics:
        passport = carried_metrics.get("passport") or {}
        if passport.get("level") in ("strategic", "systemic"):
            return MODEL_MEDIUM

    # Простые — приветствия, короткие вопросы
    return MODEL_LIGHT


BASE_METRICS = {
    "stability_index": 0.0,
    "indicator_status": "success",
    "cycles_completed": 0,
    "collisions_resolved": "0/0",
    "lots_balance": "+0.0",
    "patterns_applied": [],
    "cognitive_distortions": [],
    "autonomy_levels": [],
    "mind_scale": "micro",
    "human_contribution": 0.0,
    "value_choices": [],
    "consequences_tree": None,
    "dilemma_type": None,
    "impact_map": None,
    "reset_proposal": None,
    "artifact_status": None,
    "required_skills": [],
    "risk_intercept": None,
    "reasoning_trace": None,
    "breakthrough_marker": False,
    "cognitive_pulse": "stable",
    "protocol_integrity": True,
    "developer_mode": False,
    "reminder": None,
    "artifacts": [],
    "passport": {
        "level": "micro", "title": None, "goal": None, "result": None,
        "mission": None, "values": [], "constraints": [], "stakeholders": [],
        "risks": [], "metrics": [], "completion": 0,
    },
    "profile": {
        "values": {}, "patterns": [], "distortions": [], "insights": [],
    },
}


COMPACT_SCHEMA = {
    "stability_index": "float 0-1",
    "indicator_status": "success | warning | critical",
    "cycles_completed": "int",
    "collisions_resolved": "N/N",
    "lots_balance": "+X.X",
    "mind_scale": "micro | tactical | strategic | systemic",
    "human_contribution": "float 0-1",
    "cognitive_pulse": "slow | stable | fast",
    "reasoning_trace": "string | null",
    "breakthrough_marker": "bool",
    "reset_proposal": "{recommended, reset_point, reason} | null",
    "reminder": "{set, at, text} | null",
    "artifact_status": "{type, title, ready, suggested_tags, format} | null",
    "value_choices": "[{question, options: [{label, consequences}]}]",
    "risk_intercept": "{active, requested_action, risk_level, safe_alternative} | null",
    "passport": {
        "level": "micro | tactical | strategic | systemic",
        "title": "string | null",
        "goal": "string | null",
        "result": "string | null",
        "mission": "string | null",
        "values": "[string]",
        "constraints": "[string]",
        "stakeholders": "[string]",
        "risks": "[string]",
        "metrics": "[string]",
        "completion": "int 0-100",
    },
    "profile": {
        "values": "{развитие: 0-1, стабильность: 0-1, свобода: 0-1, контроль: 0-1, связь: 0-1}",
        "patterns": "[string]",
        "distortions": "[string]",
        "insights": "[string]",
    },
    "artifacts": "[{id, name, type, format, stage, version, comment}] (без content!)",
}


def strip_thinking(text: str) -> str:
    if not text:
        return text
    text = re.sub(r" thinking.*?", "", text, flags=re.DOTALL)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL)
    return text.strip()


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    text = strip_thinking(text)
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    chunk = text[start:i + 1]
                    try:
                        return json.loads(chunk)
                    except Exception:
                        break
        start = text.find("{", start + 1)
    return None


def compact_carried(carried: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not carried:
        return {}
    out = {}
    p = carried.get("passport") or {}
    if p:
        out["passport"] = {
            "level": p.get("level"),
            "title": p.get("title"),
            "goal": p.get("goal"),
        }
    pr = carried.get("profile") or {}
    if pr:
        out["profile"] = {
            "values": pr.get("values") or {},
            "patterns": (pr.get("patterns") or [])[:5],
        }
    arts = carried.get("artifacts") or []
    if arts:
        out["artifacts"] = [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "type": a.get("type"),
                "version": a.get("version"),
                "stage": a.get("stage"),
            }
            for a in arts[-5:]
            if isinstance(a, dict)
        ]
    return out


def merge_metrics(incoming: Dict[str, Any], carried: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    carried = carried or {}
    result = {**BASE_METRICS, **carried}

    for k, v in (incoming or {}).items():
        if k in ("passport", "profile", "reminder", "artifacts"):
            continue
        if v is not None:
            result[k] = v

    inc_pass = (incoming or {}).get("passport") or {}
    car_pass = carried.get("passport") or {}
    merged_pass = {**BASE_METRICS["passport"], **car_pass}
    for k, v in inc_pass.items():
        if k == "completion":
            if isinstance(v, (int, float)) and v > (merged_pass.get("completion") or 0):
                merged_pass["completion"] = v
            continue
        if k in ("values", "constraints", "stakeholders", "risks", "metrics"):
            if isinstance(v, list) and v:
                merged_pass[k] = v
        else:
            if v not in (None, "", [], {}):
                merged_pass[k] = v
    result["passport"] = merged_pass

    inc_prof = (incoming or {}).get("profile") or {}
    car_prof = carried.get("profile") or {}
    merged_prof = {**BASE_METRICS["profile"], **car_prof}
    if isinstance(inc_prof.get("values"), dict) and inc_prof["values"]:
        merged_prof["values"] = {**merged_prof.get("values", {}), **inc_prof["values"]}
    for list_key in ("patterns", "distortions", "insights"):
        old = list(merged_prof.get(list_key) or [])
        new = inc_prof.get(list_key) or []
        if isinstance(new, list):
            seen = set(map(str, old))
            for item in new:
                if str(item) not in seen:
                    old.append(item)
                    seen.add(str(item))
        merged_prof[list_key] = old
    result["profile"] = merged_prof

    inc_rem = (incoming or {}).get("reminder")
    result["reminder"] = inc_rem if inc_rem is not None else carried.get("reminder")

    inc_art = (incoming or {}).get("artifacts") or []
    car_art = list(carried.get("artifacts") or [])
    seen_ids = set(a.get("id") for a in car_art if isinstance(a, dict))
    for a in inc_art:
        if not isinstance(a, dict):
            continue
        aid = a.get("id")
        if aid and aid not in seen_ids:
            car_art.append(a)
            seen_ids.add(aid)
    result["artifacts"] = car_art

    return result


SYSTEM_PROMPT = (
    "Ты — когнитивный AI-партнёр Monolog. "
    "Отвечай ТОЛЬКО валидным JSON, без пояснений и размышлений. "
    "Ничего до { и ничего после }. "
    "Формат строго: {\"reply_text\": \"...\", \"metrics\": {...}}\n"
    "reply_text — Markdown-текст ответа на русском языке. "
    "metrics — строго по схеме ниже. Все поля обязательны. "
    "НЕ дублируй содержимое в artifacts.content — только метаданные.\n\n"
    f"=== СЛОЙ A (ИНСТРУКЦИЯ) ===\n{LAYER_A}\n\n"
    f"=== СХЕМА METRICS ===\n{json.dumps(COMPACT_SCHEMA, ensure_ascii=False)}"
)


async def groq_call(messages: List[Dict[str, str]], api_key: str, model: str) -> str:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.6,
    }
    # reasoning_effort только для моделей, которые его поддерживают
    if model.startswith("qwen"):
        payload["reasoning_effort"] = "none"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(GROQ_URL, headers=headers, json=payload)

    remaining = r.headers.get("x-ratelimit-remaining-tokens", "?")
    log.info(f"Groq [{model}] | status={r.status_code} | remaining={remaining}")

    if r.status_code == 429:
        retry_after = r.headers.get("retry-after", "неизвестно")
        raise HTTPException(
            status_code=429,
            detail=f"Лимит Groq исчерпан. Повторите через {retry_after} сек. Или введите свой ключ."
        )
    if r.status_code >= 400:
        log.error(f"Groq error {r.status_code}: {r.text[:300]}")
        # Если модель недоступна — попробуем fallback
        if r.status_code in (400, 404) and "model" in r.text.lower():
            raise HTTPException(status_code=502, detail=f"Модель {model} недоступна")
        raise HTTPException(status_code=r.status_code, detail="Ошибка Groq API")

    data = r.json()
    content = data["choices"][0]["message"]["content"]
    return strip_thinking(content)


# --- GitHub API ---
GITHUB_API = "https://api.github.com"
_blog_cache = {"posts": None, "sha": None, "fetched_at": 0}
BLOG_CACHE_TTL = 300


async def github_get_file():
    now = time.time()
    if _blog_cache["posts"] is not None and (now - _blog_cache["fetched_at"]) < BLOG_CACHE_TTL:
        return _blog_cache["posts"], _blog_cache.get("sha")

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{BLOG_PATH}"
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params={"ref": GITHUB_BRANCH})

    if r.status_code == 404:
        return [], None
    if r.status_code >= 400:
        log.error(f"GitHub get error {r.status_code}: {r.text[:200]}")
        raise HTTPException(status_code=502, detail="Не удалось прочитать блог из GitHub")

    data = r.json()
    content_b64 = data.get("content", "")
    try:
        raw = base64.b64decode(content_b64).decode("utf-8")
        posts = json.loads(raw) if raw.strip() else []
    except Exception:
        posts = []

    _blog_cache["posts"] = posts
    _blog_cache["sha"] = data.get("sha")
    _blog_cache["fetched_at"] = now
    return posts, data.get("sha")


async def github_put_file(posts: list, message: str):
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN не настроен")

    _, sha = await github_get_file()
    content = json.dumps(posts, ensure_ascii=False, indent=2)
    content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{BLOG_PATH}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
    }
    body = {"message": message, "content": content_b64, "branch": GITHUB_BRANCH}
    if sha:
        body["sha"] = sha

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.put(url, headers=headers, json=body)

    if r.status_code >= 400:
        log.error(f"GitHub put error {r.status_code}: {r.text[:200]}")
        raise HTTPException(status_code=502, detail="Не удалось сохранить блог в GitHub")

    _blog_cache["posts"] = posts
    _blog_cache["sha"] = r.json().get("content", {}).get("sha")
    _blog_cache["fetched_at"] = time.time()
    return True


app = FastAPI(title="Monolog MVP")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/")
async def root():
    return FileResponse("index.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "dev_keys": len(_DEV_KEYS),
        "byok": ALLOW_BYOK,
        "blog_ready": bool(GITHUB_TOKEN),
        "author_secret_set": bool(AUTHOR_SECRET),
        "models": {
            "light": MODEL_LIGHT,
            "medium": MODEL_MEDIUM,
            "heavy": MODEL_HEAVY,
        },
    }


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    user_message = (body.get("message") or "").strip()
    attachments = body.get("attachments") or []
    carried_metrics = body.get("carried_metrics") or {}

    if not user_message and not attachments:
        raise HTTPException(status_code=400, detail="Пустое сообщение")

    api_key, source = pick_key(request)
    if not api_key:
        raise HTTPException(status_code=503, detail="Нет доступных ключей. Введите свой ключ Groq.")

    model = pick_model(user_message, carried_metrics)
    log.info(f"Chat | key_source={source} | key={mask_key(api_key)} | model={model} | len={len(user_message)} | files={len(attachments)}")

    compacted = compact_carried(carried_metrics)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    user_content = user_message or "Проанализируй вложения."
    if attachments:
        block = "\n\n=== ВЛОЖЕНИЯ ===\n"
        for a in attachments[:3]:
            block += f"\n[Файл: {a.get('name', 'без имени')}]\n{a.get('text', '')}\n"
        user_content = user_content + block

    if compacted:
        user_content += "\n\n=== СЖАТЫЙ КОНТЕКСТ ПРОЕКТА ===\n" + json.dumps(compacted, ensure_ascii=False)

    messages.append({"role": "user", "content": user_content})

    raw = await groq_call(messages, api_key, model)
    parsed = extract_json(raw)

    if parsed and "reply_text" in parsed:
        metrics = merge_metrics(parsed.get("metrics") or {}, carried_metrics)
        return JSONResponse({
            "reply_text": parsed["reply_text"],
            "metrics": metrics,
            "key_source": source,
            "model_used": model,
        })

    log.warning(f"JSON parse failed. Raw (first 300): {raw[:300]}")
    cleaned = strip_thinking(raw)
    fallback_metrics = merge_metrics({}, carried_metrics)
    fallback_metrics["protocol_integrity"] = False
    fallback_metrics["indicator_status"] = "warning"
    return JSONResponse({
        "reply_text": cleaned or "Не удалось получить корректный ответ. Попробуйте переформулировать.",
        "metrics": fallback_metrics,
        "key_source": source,
        "model_used": model,
    })


@app.post("/export/docx")
async def export_docx(request: Request):
    try:
        from docx import Document
        from docx.shared import Pt
    except ImportError:
        raise HTTPException(status_code=503, detail="python-docx не установлен")

    body = await request.json()
    title = (body.get("title") or "Документ").strip()
    text = (body.get("body") or "").strip()

    if not text:
        raise HTTPException(status_code=400, detail="Пустой текст")

    doc = Document()
    if title:
        doc.add_heading(title, level=0)

    lines = text.split("\n")
    for line in lines:
        s = line.rstrip()
        if not s:
            continue
        if s.startswith("# "):
            doc.add_heading(s[2:].strip(), level=1)
        elif s.startswith("## "):
            doc.add_heading(s[3:].strip(), level=2)
        elif s.startswith("### "):
            doc.add_heading(s[4:].strip(), level=3)
        elif s.startswith("- ") or s.startswith("* "):
            doc.add_paragraph(s[2:].strip(), style="List Bullet")
        elif re.match(r"^\d+\.\s", s):
            doc.add_paragraph(re.sub(r"^\d+\.\s", "", s), style="List Number")
        else:
            p = doc.add_paragraph(s)
            for run in p.runs:
                run.font.size = Pt(11)

    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)

    safe_title = re.sub(r"[^\w\-]+", "_", title or "document")[:60]
    filename = f"{safe_title}.docx"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/blog")
async def blog_list():
    posts, _ = await github_get_file()
    metas = []
    for p in posts:
        metas.append({
            "id": p.get("id"),
            "title": p.get("title"),
            "tags": p.get("tags", []),
            "author": p.get("author", "Эльвира"),
            "created_at": p.get("created_at"),
            "updated_at": p.get("updated_at"),
            "preview": (p.get("body") or "")[:180],
        })
    metas.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return JSONResponse({"posts": metas, "count": len(metas)})


@app.get("/blog/{post_id}")
async def blog_get(post_id: str):
    posts, _ = await github_get_file()
    for p in posts:
        if p.get("id") == post_id:
            return JSONResponse(p)
    raise HTTPException(status_code=404, detail="Статья не найдена")


@app.post("/blog/publish")
async def blog_publish(request: Request):
    check_author(request)
    body = await request.json()
    title = (body.get("title") or "").strip()
    text = (body.get("body") or "").strip()
    tags = body.get("tags") or []
    author = (body.get("author") or "Эльвира").strip()

    if not title or not text:
        raise HTTPException(status_code=400, detail="Нужны заголовок и текст")

    posts, _ = await github_get_file()
    post_id = "post_" + str(int(time.time() * 1000))
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    new_post = {
        "id": post_id,
        "title": title,
        "body": text,
        "tags": tags if isinstance(tags, list) else [],
        "author": author,
        "created_at": now,
        "updated_at": now,
    }
    posts.append(new_post)
    await github_put_file(posts, f"Blog: publish '{title[:50]}'")
    return JSONResponse({"ok": True, "id": post_id})


@app.put("/blog/{post_id}")
async def blog_update(post_id: str, request: Request):
    check_author(request)
    body = await request.json()
    posts, _ = await github_get_file()

    found = None
    for p in posts:
        if p.get("id") == post_id:
            found = p
            break
    if not found:
        raise HTTPException(status_code=404, detail="Статья не найдена")

    if "title" in body and body["title"] is not None:
        found["title"] = (body["title"] or "").strip()
    if "body" in body and body["body"] is not None:
        found["body"] = body["body"]
    if "tags" in body and isinstance(body["tags"], list):
        found["tags"] = body["tags"]
    found["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    await github_put_file(posts, f"Blog: update '{post_id}'")
    return JSONResponse({"ok": True, "id": post_id})


@app.delete("/blog/{post_id}")
async def blog_delete(post_id: str, request: Request):
    check_author(request)
    posts, _ = await github_get_file()
    new_posts = [p for p in posts if p.get("id") != post_id]
    if len(new_posts) == len(posts):
        raise HTTPException(status_code=404, detail="Статья не найдена")
    await github_put_file(new_posts, f"Blog: delete '{post_id}'")
    return JSONResponse({"ok": True})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))