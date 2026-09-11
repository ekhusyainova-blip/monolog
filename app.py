import os
import json
import re
import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEYS_RAW = os.environ.get("GROQ_API_KEYS", "").strip()
if not GROQ_API_KEYS_RAW:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: Переменная GROQ_API_KEYS не задана!")

GROQ_API_KEYS = [k.strip() for k in GROQ_API_KEYS_RAW.split(",") if k.strip()]
if not GROQ_API_KEYS:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: Не найдено ни одного GROQ_API_KEY!")

logger.info(f"Загружено {len(GROQ_API_KEYS)} API ключей Groq")

rotation_state = {
    "current_index": 0,
    "switches_count": 0,
    "keys_stats": [{"key": k[:4] + "***" + k[-4:] if len(k) > 8 else "***", "used": 0, "errors": 0} for k in GROQ_API_KEYS]
}

def get_current_client() -> Groq:
    return Groq(api_key=GROQ_API_KEYS[rotation_state["current_index"]])

def switch_to_next_key():
    rotation_state["current_index"] = (rotation_state["current_index"] + 1) % len(GROQ_API_KEYS)
    rotation_state["switches_count"] += 1
    logger.info(f"Переключение на ключ #{rotation_state['current_index']}")

def call_groq_with_rotation(messages, temperature=0.7, max_tokens=4000, timeout=60):
    attempts = len(GROQ_API_KEYS)
    last_error = None
    for attempt in range(attempts):
        current_idx = rotation_state["current_index"]
        client = get_current_client()
        try:
            logger.info(f"Попытка #{attempt + 1}: ключ #{current_idx}")
            completion = client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout
            )
            rotation_state["keys_stats"][current_idx]["used"] += 1
            logger.info(f"Успех на ключе #{current_idx}")
            return completion.choices[0].message.content
        except Exception as e:
            error_str = str(e)
            rotation_state["keys_stats"][current_idx]["errors"] += 1
            last_error = e
            if "rate_limit_exceeded" in error_str or "429" in error_str or "Request too large" in error_str:
                logger.warning(f"Rate limit на ключе #{current_idx}. Переключаюсь...")
                switch_to_next_key()
                continue
            else:
                logger.error(f"Ошибка Groq: {e}")
                raise e
    raise Exception(f"Все ключи исчерпали лимит. Ошибка: {last_error}")

SYSTEM_PROMPT = '''Ты — когнитивный AI-партнёр Monolog. Отвечай как мудрый партнёр, помогая видеть структуру и истинные цели.

=== ПРИНЦИПЫ ===
1. Направляй, а не ограничивай.
2. Экологичная подача: сложную истину через микро-шаги.
3. Адаптивная глубина: простой вопрос — краткий ответ, сложный — полный каркас.
4. Фокус на главном: одно самое важное действие.
5. Естественные эмодзи для акцентов в тексте.

=== СТАДИИ ГОТОВНОСТИ ===
1 — Гипотеза (идея для размышления)
2 — Тестовый прототип (черновик)
3 — Рабочая версия (прошла валидацию)
4 — Финализировано (утверждено, стабильность > 0.9)

=== РЕЖИМЫ ===
[АЛГОРИТМ] — структурный анализ
[УТОЧНЕНИЕ] — запрос фактов
[РАЗВИЛКА] — варианты с последствиями
[ЭКСПЕРИМЕНТ] — низкорисковое действие
[СМЕНА ФОКУСА] — новая формулировка
[МОЗГОВОЙ ШТУРМ] — генерация идей

=== СТРУКТУРА ОТВЕТА ===
[РЕЖИМ: ...]
[Карта восприятия]
- Суть: [1 предложение]
- Контекст: [скрытые мотивы]
[Решение]
- Главный вывод: [1-2 предложения]
- Следующий шаг: [одно действие]
[Отчёт]
- Ключевой инсайт: [1 предложение]
- Стадия: [1/2/3/4]

=== TRUST MATRIX ===
Уровень 0 (аналитика): автономно
Уровень 1 (артефакты): один клик
Уровень 2 (техника): явное подтверждение
Уровень 3 (коммуникации): явное разрешение
Уровень 4 (финансы): двойное подтверждение

=== ЗАЩИТА ОТ ДЕСТРУКТИВНЫХ ДЕЙСТВИЙ ===
При деструктивном запросе (удаление данных, отправка без подтверждения и т.п.) естественно предложи безопасную альтернативу и передай в JSON флаг risk_intercept.

=== JSON-ПРОТОКОЛ ===
В самом конце ответа ОБЯЗАТЕЛЬНО выведи блок с метриками в формате JSON внутри тегов ```json и ```. Пример:
```json
{
  "stability_index": 0.85,
  "indicator_status": "success",
  "cycles_completed": 2,
  "collisions_resolved": "2/2",
  "lots_balance": "+0.20",
  "patterns_applied": ["декомпозиция"],
  "cognitive_distortions": [],
  "mind_scale": "strategic",
  "human_contribution": 0.60,
  "protocol_integrity": true,
  "risk_intercept": {"active": false},
  "required_skills": [],
  "reasoning_trace": "Базовый анализ"
}
‘’’
@app.post(”/api/chat”)
async def chat_api(request: Request):
data = await request.json()
message = data.get(“message”, “”)
history = data.get(“history”, [])
logger.info(f”НАЧАЛО ОБРАБОТКИ: {message[:40]}…”)
messages = [{"role": "system", "content": SYSTEM_PROMPT}]
for msg in history[-10:]:
    messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
messages.append({"role": "user", "content": message})

raw_reply = ""
try:
    raw_reply = call_groq_with_rotation(messages=messages, temperature=0.7, max_tokens=4000, timeout=60)
except Exception as e:
    logger.error(f"Ошибка Groq: {e}")
    raw_reply = f"Ошибка ИИ: {e}. Обратитесь к разработчику (el.xusyainova@ya.ru)."

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
    "protocol_integrity": False,
    "risk_intercept": {"active": False},
    "required_skills": [],
    "reasoning_trace": "Значения по умолчанию"
}

json_match = re.search(r'```json\s*([\s\S]*?)\s*```', raw_reply, re.IGNORECASE)
if json_match:
    try:
        metrics = json.loads(json_match.group(1))
        reply_text = raw_reply[:json_match.start()].strip()
        logger.info("Метрики успешно распарсены")
    except json.JSONDecodeError:
        logger.warning("Не удалось распарсить JSON метрик")
else:
    logger.warning("Блок JSON метрик не найден")

return JSONResponse(content={"reply_text": reply_text, "metrics": metrics})
@app.get(”/admin/keys”)
async def get_keys_stats():
return JSONResponse(content={
“total_keys”: len(GROQ_API_KEYS),
“current_index”: rotation_state[“current_index”],
“switches”: rotation_state[“switches_count”],
“stats”: rotation_state[“keys_stats”]
})
@app.get(”/health”)
async def health():
return {“status”: “ok”}
if name == “main”:
import uvicorn
uvicorn.run(app, host=“0.0.0.0”, port=int(os.environ.get(“PORT”, 7860)))