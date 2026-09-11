import os
import json
import re
import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from groq import Groq
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Разрешаем CORS для корректной работы фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === 1. ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
GROQ_API_KEYS_RAW = os.environ.get("GROQ_API_KEYS", "").strip()

if not all([SUPABASE_URL, SUPABASE_KEY, GROQ_API_KEYS_RAW]):
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: Проверьте переменные окружения (SUPABASE_URL, SUPABASE_KEY, GROQ_API_KEYS)!")

GROQ_API_KEYS = [k.strip() for k in GROQ_API_KEYS_RAW.split(",") if k.strip()]
if not GROQ_API_KEYS:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: Не найдено ни одного GROQ_API_KEY!")

logger.info(f"✅ Загружено {len(GROQ_API_KEYS)} API ключей Groq")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# === 2. РОТАЦИЯ КЛЮЧЕЙ ===
rotation_state = {
    "current_index": 0,
    "switches_count": 0,
    "last_switch_time": None,
    "keys_stats": [{"key": k[:4] + "***" + k[-4:] if len(k) > 8 else "***", "used": 0, "errors": 0} for k in GROQ_API_KEYS]
}

def get_current_client() -> Groq:
    return Groq(api_key=GROQ_API_KEYS[rotation_state["current_index"]])

def switch_to_next_key():
    rotation_state["current_index"] = (rotation_state["current_index"] + 1) % len(GROQ_API_KEYS)
    rotation_state["switches_count"] += 1
    rotation_state["last_switch_time"] = time.time()
    logger.info(f"🔄 Переключение на ключ #{rotation_state['current_index']}")

def call_groq_with_rotation(messages, temperature=0.7, max_tokens=4000, timeout=60):
    attempts = len(GROQ_API_KEYS)
    last_error = None
    
    for attempt in range(attempts):
        current_idx = rotation_state["current_index"]
        client = get_current_client()
        
        try:
            logger.info(f"⏳ Попытка #{attempt + 1}: ключ #{current_idx}")
            completion = client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout
            )
            rotation_state["keys_stats"][current_idx]["used"] += 1
            logger.info(f"✅ Успех на ключе #{current_idx}")
            return completion.choices[0].message.content
            
        except Exception as e:
            error_str = str(e)
            rotation_state["keys_stats"][current_idx]["errors"] += 1
            last_error = e
            
            if "rate_limit_exceeded" in error_str or "429" in error_str or "Request too large" in error_str:
                logger.warning(f"⚠️ Rate limit на ключе #{current_idx}. Переключаюсь...")
                switch_to_next_key()
                continue
            else:
                logger.error(f"❌ Ошибка Groq: {e}")
                raise e
    
    raise Exception(f"Все {len(GROQ_API_KEYS)} ключей исчерпали лимит. Последняя ошибка: {last_error}")

# === 3. СИСТЕМНЫЙ ПРОМПТ ===
# ВАЖНО: Используем ''' (тройные одинарные кавычки), чтобы внутренние ``` не ломали строку Python
SYSTEM_PROMPT = '''Ты — когнитивный AI-партнёр Monolog. Отвечай как эксперт-консультант. Используй Markdown. Без эмодзи. Без жёстких служебных заголовков.

[ПРАВИЛА]
1. Текст ответа должен быть естественным диалогом. Начинай с главного вывода, давай структурированное объяснение, завершай следующим шагом.
2. При значимом решении явно разграничивай: что зависит от ценностных установок пользователя, а что — от алгоритма.
3. Если задача многомерная (>5 параметров), сожми её до 2-3 ключевых измерений, реши, разверни и верифицируй.
4. Если обнаружен тупик, предложи альтернативный вектор. Если стабильность низкая (<0.5), мягко предупреди об этом в тексте.
5. НИКОГДА не используй эмодзи.

[ГЕНЕРАЦИЯ МЕТРИК]
В самом конце своего ответа, после всего текста, ОБЯЗАТЕЛЬНО выведи блок с метриками в формате JSON внутри тегов ```json и ```. Это нужно для панели управления. Пример:
```json
{
  "stability_index": 0.85,
  "indicator_status": "success",
  "cycles_completed": 2,
  "collisions_resolved": "2/2",
  "lots_balance": "+0.20",
  "patterns_applied": ["декомпозиция", "синхронизация_плоскости"],
  "cognitive_distortions": [],
  "mind_scale": "strategic",
  "human_contribution": 0.60,
  "protocol_integrity": true
}
‘’’
=== 4. API: ПОЛУЧЕНИЕ ИЛИ СОЗДАНИЕ ПРОЕКТА ===
@app.get(”/api/project”)
async def get_or_create_project(user_id: str = “anonymous_test”):
result = supabase.table(“projects”).select(”*”).eq(“user_id”, user_id).eq(“is_archived”, False).order(“created_at”, desc=True).limit(1).execute()
if result.data:
    return JSONResponse(content={"project": result.data[0]})

new_project = {
    "user_id": user_id,
    "name": "Новый проект",
    "description": "Автоматически созданный проект"
}
insert_result = supabase.table("projects").insert(new_project).execute()
return JSONResponse(content={"project": insert_result.data[0], "created": True})
=== 5. API: ОБРАБОТКА СООБЩЕНИЯ ===
@app.post(”/api/chat”)
async def chat_api(request: Request):
data = await request.json()
message = data.get(“message”, “”)
project_id = data.get(“project_id”, None)
user_id = data.get(“user_id”, “anonymous_test”)
logger.info(f"🚀 НАЧАЛО ОБРАБОТКИ: {message[:40]}...")

if not project_id:
    proj_res = supabase.table("projects").select("id").eq("user_id", user_id).eq("is_archived", False).order("created_at", desc=True).limit(1).execute()
    if proj_res.data:
        project_id = proj_res.data[0]["id"]
    else:
        new_proj = supabase.table("projects").insert({"user_id": user_id, "name": "Новый проект"}).execute()
        project_id = new_proj.data[0]["id"]

# Шаг 1: Сохранение запроса пользователя
try:
    supabase.table("chats").insert({
        "project_id": project_id,
        "user_id": user_id,
        "role": "user",
        "content": message
    }).execute()
    logger.info("✅ Запрос пользователя сохранён в Supabase")
except Exception as e:
    logger.error(f"❌ Ошибка Supabase (user): {e}")

# Шаг 2: Генерация ответа через Groq
raw_reply = ""
try:
    logger.info("⏳ Запрос к модели qwen...")
    raw_reply = call_groq_with_rotation(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message}
        ],
        temperature=0.7,
        max_tokens=4000,
        timeout=60
    )
    logger.info("✅ Ответ от Groq получен")
except Exception as e:
    logger.error(f"❌ Ошибка Groq: {e}")
    raw_reply = f"⚠️ Ошибка ИИ: {e}. Обратитесь к разработчику (el.xusyainova@ya.ru)."

# Шаг 3: Парсинг текста и метрик
reply_text = raw_reply
metrics = {
    "stability_index": 0.5,
    "indicator_status": "warning",
    "cycles_completed": 1,
    "collisions_resolved": "0/0",
    "lots_balance": "0.00",
    "patterns_applied": [],
    "cognitive_distortions": [],
    "mind_scale": "micro",
    "human_contribution": 0.5,
    "protocol_integrity": False
}

# Ищем блок ```json ... ``` в конце ответа
json_match = re.search(r'```json\s*([\s\S]*?)\s*```', raw_reply, re.IGNORECASE)
if json_match:
    try:
        metrics = json.loads(json_match.group(1))
        # Удаляем блок JSON из текста ответа, чтобы пользователь его не видел
        reply_text = raw_reply[:json_match.start()].strip()
        logger.info("✅ Метрики успешно распарсены из ответа модели")
    except json.JSONDecodeError:
        logger.warning("⚠️ Не удалось распарсить JSON метрик, используются значения по умолчанию")
else:
    logger.warning("⚠️ Блок JSON метрик не найден в ответе модели")

# Шаг 4: Сохранение ответа ассистента с метриками
try:
    supabase.table("chats").insert({
        "project_id": project_id,
        "user_id": user_id,
        "role": "assistant",
        "content": reply_text,
        "metrics": metrics
    }).execute()
    logger.info("✅ Ответ ассистента сохранён в Supabase")
except Exception as e:
    logger.error(f"❌ Ошибка Supabase (assistant): {e}")

return JSONResponse(content={
    "reply_text": reply_text,
    "metrics": metrics,
    "project_id": project_id
})
=== 6. АДМИН-ЭНДПОИНТ (статистика ключей) ===
@app.get(”/admin/keys”)
async def get_keys_stats():
return JSONResponse(
content={
“всего_ключей”: len(GROQ_API_KEYS),
“активный_ключ_индекс”: rotation_state[“current_index”],
“всего_переключений”: rotation_state[“switches_count”],
“статистика_по_ключам”: rotation_state[“keys_stats”]
},
headers={“Content-Type”: “application/json; charset=utf-8”}
)
if name == “main”:
import uvicorn
uvicorn.run(app, host=“0.0.0.0”, port=int(os.environ.get(“PORT”, 7860)))