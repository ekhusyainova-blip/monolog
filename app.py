import os
import json
import re
import time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from supabase import create_client, Client
from groq import Groq
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# === 1. ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
GROQ_API_KEYS_RAW = os.environ.get("GROQ_API_KEYS", "").strip()

if not all([SUPABASE_URL, SUPABASE_KEY, GROQ_API_KEYS_RAW]):
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: Проверьте переменные окружения (SUPABASE_URL, SUPABASE_KEY, GROQ_API_KEYS)!")

# Парсим ключи из строки через запятую
GROQ_API_KEYS = [k.strip() for k in GROQ_API_KEYS_RAW.split(",") if k.strip()]
if not GROQ_API_KEYS:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: Не найдено ни одного GROQ_API_KEY!")

logger.info(f"✅ Загружено {len(GROQ_API_KEYS)} API ключей Groq")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# === 2. ФУНКЦИИ РОТАЦИИ (ОБЪЯВЛЕНЫ ДО ИСПОЛЬЗОВАНИЯ) ===
def mask_key(key: str) -> str:
    """Маскирует ключ для безопасного логирования: gsk_***abcd"""
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}***{key[-4:]}"

# Инициализация состояния (теперь mask_key уже известен Python)
rotation_state = {
    "current_index": 0,
    "switches_count": 0,
    "last_switch_time": None,
    "keys_stats": [{"key": mask_key(k), "used": 0, "errors": 0} for k in GROQ_API_KEYS]
}

def get_current_client() -> Groq:
    """Возвращает Groq-клиент для текущего активного ключа"""
    return Groq(api_key=GROQ_API_KEYS[rotation_state["current_index"]])

def switch_to_next_key():
    """Переключается на следующий ключ (круговая ротация)"""
    rotation_state["current_index"] = (rotation_state["current_index"] + 1) % len(GROQ_API_KEYS)
    rotation_state["switches_count"] += 1
    rotation_state["last_switch_time"] = time.time()
    logger.info(f"🔄 Переключение на ключ #{rotation_state['current_index']} ({mask_key(GROQ_API_KEYS[rotation_state['current_index']])})")

def call_groq_with_rotation(messages, temperature=0.7, max_tokens=4000, timeout=60):
    """Вызов Groq с автоматической ротацией ключей при rate limit (429)"""
    attempts = len(GROQ_API_KEYS)
    last_error = None
    
    for attempt in range(attempts):
        current_idx = rotation_state["current_index"]
        client = get_current_client()
        
        try:
            logger.info(f"⏳ Попытка #{attempt + 1}: ключ #{current_idx} ({mask_key(GROQ_API_KEYS[current_idx])})")
            
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
            
            # Проверяем, это rate limit (429)?
            if "rate_limit_exceeded" in error_str or "429" in error_str or "Request too large" in error_str:
                logger.warning(f"⚠️ Rate limit на ключе #{current_idx}. Переключаюсь...")
                switch_to_next_key()
                continue
            else:
                logger.error(f"❌ Ошибка Groq (не rate limit): {e}")
                raise e
    
    raise Exception(f"Все {len(GROQ_API_KEYS)} ключей исчерпали лимит. Последняя ошибка: {last_error}")

# === 3. ПОЛНЫЙ ПРОМПТ (Слой A + Слой B, без упоминания <think>) ===
SYSTEM_PROMPT = """Ты обрабатываешь запросы пользователя на минимум +1 мета-уровне выше предметной области через циклы мышления и стремишься предлагать стабильные решения, предупреждаешь ошибки восприятия и удерживаешь пользователя от импульсивных действий, распознаешь потребности и считаешь скрытые потребности равнозначными запросу.

[АРХИТЕКТУРА ПРОМПТА]
Этот промпт разделён на два слоя:
- СЛОЙ A (публичный): структура ответа, базовые правила поведения, таблицы метрик, режимы работы.
- СЛОЙ B (скрытый): точная когнитивная методология обработки запросов.

[СИСТЕМНАЯ ИНСТРУКЦИЯ: СКРЫТЫЙ ЦИКЛ ОБРАБОТКИ]
Ты работаешь в строгом двухэтапном режиме. Пользователь никогда не видит Этап 1.
ЭТАП 1 (Внутренний, невидимый): Проанализируй запрос пользователя. Сгенерируй "Скрытый рабочий промпт", который адаптирует когнитивную модель под конкретную задачу на основе методологии Слоя B.
ЭТАП 2 (Финальный ответ): Используя сгенерированный Скрытый рабочий промпт как абсолютную внутреннюю инструкцию, выполни задачу. Строго следуй структуре ответа.

ВАЖНО: Если пользователь интересуется алгоритмом, предлагай сотрудничество с разработчиком (el.xusyainova@ya.ru).

[БАЗОВЫЕ ПРАВИЛА ПОВЕДЕНИЯ]
- Обрабатываешь запросы через циклы мышления на +1 мета-уровне выше предметной области.
- Выявляешь потребности пользователя и считаешь скрытые потребности равнозначными запросу.
- Удерживаешь пользователя от импульсивных действий.
- Предупреждаешь ошибки восприятия.
- Решение синхронизируешь с плоскостью пользователя.
- Устраняешь коллизии.
- При неполной картине восприятия предлагаешь собрать больше данных.
- При активных обновлениях корректируешь картину восприятия.
- При нерешённых коллизиях проводишь повторную проверку.
- При сложных задачах (>2 параметров) проводишь мозговой штурм.
- При ограничениях предлагаешь компромисс или решения без ограничений.
- Если индекс стабильности ниже критического порога, уведомляешь и предлагаешь скорректировать восприятие.
- Если требуется больше данных, а безопасность блокирует действия, предлагаешь только безопасные действия.
- Если данных достаточно, но безопасность блокирует действия, вводишь новое условие.
- Если пользователь ошибся, не повторяй, исправь.

[МЕТОДОЛОГИЯ СЛОЯ B]
БЛОК B.1: Протокол генерации Скрытого рабочего промпта
1. Оценку картины восприятия: полнота (0–1), искажения, состояние фильтра (вкл/выкл).
2. План циклов проверки: количество итераций, критерии выхода.
3. Выявление коллизий: минимум 3 противоречия, стратегия разрешения.
4. Стратегию зонд-действий: минимум 2 варианта, оценка безопасности.
5. Мета-уровень обработки: на каком уровне (+1, +2, +3) и почему.

БЛОК B.2: Правила циклов проверки
• Запрос >2 параметров: мозговой штурм, мин. 1 итерация на параметр, мин. 2 итерации обсуждения финала.
• Многомерный запрос: проверка >2 раз до полного разрешения коллизий.

БЛОК B.3: Критерии коллизий и блокировки действий
Агент НЕ предлагает активных действий, если:
1. Активно обновление или ошибки повторяются -> Корректируй картину восприятия.
2. Нет возможности формирования стабильного решения -> Задавай уточняющие вопросы.
3. Не все коллизии решены -> Проводи повторную проверку.
4. Фильтр информации выключен ИЛИ картина искажена -> Предложи собрать данные.
5. Запрос предполагает ограничения -> Предлагай решения без ограничений или компромисс.

БЛОК B.4: Мета-уровень обработки
• Каждый запрос обрабатывается минимум на +1 мета-уровне.
• Мета-уровень 1: Анализ паттернов и системных связей.
• Мета-уровень 2: Выявление скрытых предпосылок и потребностей.
• Мета-уровень 3: Формирование принципов для смежных задач.

[РЕЖИМЫ РАБОТЫ]
Режим Пользователя (по умолчанию): без доступа к информации о циклах.
Режим Разработчика: доступ по ключу «Эгида-Эльвира-7». Если ключ есть, добавь в конец ответа блок:
[РЕЖИМ: РАЗРАБОТЧИК]
- Цикл: <0-3>
- Итерации: <число>
- Коллизии: <решено/обнаружено>
- Восприятие: <0-1>
- Фильтр: <вкл/выкл>
- Безопасность: <текст>

[СТРУКТУРА ОТВЕТА]
1. Индекс стабильности: <0.0 - 1.0>
2. Основной ответ: <развёрнутое решение>
3. Стратегический ориентир: <1 предложение>
4. Ближайший шаг: <1 конкретное действие>
"""

# === 4. ВЕБ-ИНТЕРФЕЙС ===
@app.get("/", response_class=HTMLResponse)
async def get_chat():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
        <title>Когнитивный Агент</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; }
            html, body { height: 100%; overflow: hidden; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f4f4f9; }
            body { display: flex; flex-direction: column; padding: 15px; padding-bottom: calc(15px + env(safe-area-inset-bottom)); }
            #chat-box { flex: 1; overflow-y: auto; background: white; border-radius: 16px; padding: 15px; margin-bottom: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); -webkit-overflow-scrolling: touch; }
            .message { margin-bottom: 15px; padding: 12px 16px; border-radius: 18px; max-width: 85%; line-height: 1.5; word-wrap: break-word; font-size: 15px; white-space: pre-wrap; }
            .user { background: #007AFF; color: white; margin-left: auto; border-bottom-right-radius: 4px; }
            .assistant { background: #E9E9EB; color: #1c1c1e; border-bottom-left-radius: 4px; }
            .input-area { display: flex; gap: 10px; flex-shrink: 0; }
            input { flex: 1; padding: 14px; border: 1px solid #d1d1d6; border-radius: 25px; font-size: 16px; outline: none; background: white; min-width: 0; }
            button { padding: 14px 20px; background: #007AFF; color: white; border: none; border-radius: 25px; font-size: 16px; font-weight: 600; cursor: pointer; flex-shrink: 0; }
            button:disabled { background: #a1a1aa; }
            #loading { display: none; text-align: center; color: #8e8e93; margin-bottom: 10px; font-size: 14px; }
        </style>
    </head>
    <body>
        <div id="chat-box"></div>
        <div id="loading">Агент анализирует запрос...</div>
        <div class="input-area">
            <input type="text" id="user-input" placeholder="Введите задачу..." autocomplete="off">
            <button onclick="sendMessage()" id="send-btn">➤</button>
        </div>
        <script>
            function formatResponse(text) {
                // Удаляем технический блок <think> (генерируется моделью Qwen автоматически)
                var thinkStart = text.indexOf('<think>');
                var thinkEnd = text.indexOf('</think>');
                if (thinkStart !== -1 && thinkEnd !== -1) {
                    text = text.substring(0, thinkStart) + text.substring(thinkEnd + 8);
                }
                text = text.trim();
                text = text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
                text = text.replace(new RegExp('\\n', 'g'), '<br>');
                return text;
            }

            async function sendMessage() {
                const input = document.getElementById('user-input');
                const btn = document.getElementById('send-btn');
                const loading = document.getElementById('loading');
                const chatBox = document.getElementById('chat-box');
                const text = input.value.trim();
                if (!text) return;

                chatBox.innerHTML += `<div class="message user">${text.replace(/</g, '&lt;')}</div>`;
                input.value = '';
                input.disabled = true;
                btn.disabled = true;
                loading.style.display = 'block';
                chatBox.scrollTop = chatBox.scrollHeight;

                try {
                    const controller = new AbortController();
                    const timeoutId = setTimeout(() => controller.abort(), 60000);

                    const response = await fetch('/api/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: text }),
                        signal: controller.signal
                    });
                    
                    clearTimeout(timeoutId);
                    if (!response.ok) throw new Error(`Ошибка сервера: ${response.status}`);
                    
                    const data = await response.json();
                    const formattedReply = formatResponse(data.reply);
                    chatBox.innerHTML += `<div class="message assistant">${formattedReply}</div>`;
                } catch (error) {
                    let errorMsg = "Ошибка сети. Попробуйте еще раз.";
                    if (error.name === 'AbortError') errorMsg = "Превышено время ожидания.";
                    chatBox.innerHTML += `<div class="message assistant" style="color:red; background:#fee2e2;">${errorMsg}</div>`;
                } finally {
                    input.disabled = false;
                    btn.disabled = false;
                    loading.style.display = 'none';
                    input.focus();
                    chatBox.scrollTop = chatBox.scrollHeight;
                }
            }
            
            document.getElementById('user-input').addEventListener('keypress', function (e) {
                if (e.key === 'Enter') sendMessage();
            });
        </script>
    </body>
    </html>
    """

# === 5. API ДЛЯ ОБРАБОТКИ СООБЩЕНИЙ ===
@app.post("/api/chat")
async def chat_api(request: Request):
    data = await request.json()
    message = data.get("message", "")
    logger.info(f"🚀 НАЧАЛО ОБРАБОТКИ: {message[:40]}...")
    
    session_id = "session_default"
    
    try:
        supabase.table("chats").insert({
            "session_id": session_id,
            "role": "user",
            "content": message
        }).execute()
        logger.info("✅ Запрос сохранен в Supabase")
    except Exception as e:
        logger.error(f"❌ Ошибка Supabase (user): {e}")

    try:
        reply = call_groq_with_rotation(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message}
            ],
            temperature=0.7,
            max_tokens=4000,
            timeout=60
        )
        reply = reply.lstrip()
        logger.info("✅ Ответ от Groq успешно получен")
    except Exception as e:
        logger.error(f"❌ Ошибка Groq: {e}")
        reply = f"⚠️ Ошибка ИИ: {e}. Обратитесь к разработчику (el.xusyainova@ya.ru)."

    try:
        supabase.table("chats").insert({
            "session_id": session_id,
            "role": "assistant",
            "content": reply
        }).execute()
        logger.info("✅ Ответ сохранен в Supabase")
    except Exception as e:
        logger.error(f"❌ Ошибка Supabase (assistant): {e}")

    return JSONResponse(content={"reply": reply})

# === 6. АДМИН-ЭНДПОИНТ ===
@app.get("/admin/keys")
async def get_keys_stats():
    return JSONResponse(
        content={
            "всего_ключей": len(GROQ_API_KEYS),
            "активный_ключ_индекс": rotation_state["current_index"],
            "активный_ключ_masked": mask_key(GROQ_API_KEYS[rotation_state["current_index"]]),
            "всего_переключений": rotation_state["switches_count"],
            "статистика_по_ключам": rotation_state["keys_stats"]
        },
        headers={"Content-Type": "application/json; charset=utf-8"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 7860)))
