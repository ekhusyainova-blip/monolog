import os
import json
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
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

if not all([SUPABASE_URL, SUPABASE_KEY, GROQ_API_KEY]):
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: Проверьте переменные окружения в Render!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

# === 2. ЯДРО ПРОМПТА (ЖЕСТКО ОПТИМИЗИРОВАНО ПОД ЛИМИТ 1000 ТОКЕНОВ) ===
SYSTEM_PROMPT = """
Ты — когнитивный ИИ-агент. 
КРИТИЧЕСКОЕ ОГРАНИЧЕНИЕ: Твой ОБЩИЙ ответ (включая блок <think>) НЕ ДОЛЖЕН превышать 800 токенов. Будь предельно лаконичен.

ПРАВИЛА:
1. Анализируй запрос на +1 мета-уровне. Выявляй скрытые потребности.
2. Если параметров >2, проведи ОЧЕНЬ КРАТКИЙ мозговой штурм (тезисно).
3. При коллизиях или неполных данных: НЕ предлагай действий, а запроси уточнение или введи новое условие.
4. Если в запросе есть ключ "Эгида-Эльвира-7", добавь в конец блок [РЕЖИМ: РАЗРАБОТЧИК] с метриками.

СТРУКТУРА ОТВЕТА (строго и кратко, без воды):
1. Индекс стабильности: <0.0 - 1.0>
2. Основной ответ: <1-2 предложения>
3. Стратегический ориентир: <1 предложение>
4. Ближайший шаг: <1 конкретное действие>
"""

# === 3. ВЕБ-ИНТЕРФЕЙС (с улучшенной обработкой долгих ответов) ===
@app.get("/", response_class=HTMLResponse)
async def get_chat():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
        <title>Когнитивный Агент</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f4f4f9; margin: 0; padding: 15px; display: flex; flex-direction: column; height: 100vh; box-sizing: border-box; }
            #chat-box { flex: 1; overflow-y: auto; background: white; border-radius: 16px; padding: 15px; margin-bottom: 15px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
            .message { margin-bottom: 15px; padding: 12px 16px; border-radius: 18px; max-width: 85%; line-height: 1.5; white-space: pre-wrap; word-wrap: break-word; font-size: 15px; }
            .user { background: #007AFF; color: white; align-self: flex-end; margin-left: auto; border-bottom-right-radius: 4px; }
            .assistant { background: #E9E9EB; color: #1c1c1e; align-self: flex-start; border-bottom-left-radius: 4px; }
            .input-area { display: flex; gap: 10px; }
            input { flex: 1; padding: 14px; border: 1px solid #d1d1d6; border-radius: 25px; font-size: 16px; outline: none; background: white; }
            button { padding: 14px 20px; background: #007AFF; color: white; border: none; border-radius: 25px; font-size: 16px; font-weight: 600; cursor: pointer; }
            button:disabled { background: #a1a1aa; }
            #loading { display: none; text-align: center; color: #8e8e93; margin-bottom: 10px; font-size: 14px; }
        </style>
    </head>
    <body>
        <div id="chat-box"></div>
        <div id="loading">Агент анализирует запрос (это может занять до 30 сек)...</div>
        <div class="input-area">
            <input type="text" id="user-input" placeholder="Введите задачу..." autocomplete="off">
            <button onclick="sendMessage()" id="send-btn">➤</button>
        </div>
        <script>
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
                    // Увеличиваем таймаут для медленных ответов на бесплатном Render
                    const controller = new AbortController();
                    const timeoutId = setTimeout(() => controller.abort(), 45000); // 45 секунд

                    const response = await fetch('/api/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message: text }),
                        signal: controller.signal
                    });
                    
                    clearTimeout(timeoutId);
                    
                    if (!response.ok) {
                        throw new Error(`Ошибка сервера: ${response.status}`);
                    }
                    
                    const data = await response.json();
                    // Заменяем переносы строк на <br> для корректного отображения
                    const formattedReply = data.reply.replace(/\\n/g, '<br>').replace(/</g, '&lt;');
                    chatBox.innerHTML += `<div class="message assistant">${formattedReply}</div>`;
                } catch (error) {
                    let errorMsg = "Ошибка сети. Попробуйте еще раз.";
                    if (error.name === 'AbortError') {
                        errorMsg = "Превышено время ожидания ответа. Попробуйте переформулировать запрос короче.";
                    }
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

# === 4. API ДЛЯ ОБРАБОТКИ СООБЩЕНИЙ ===
@app.post("/api/chat")
async def chat_api(request: Request):
    data = await request.json()
    message = data.get("message", "")
    logger.info(f"🚀 НАЧАЛО ОБРАБОТКИ: {message[:40]}...")
    
    session_id = "session_default"
    
    # Шаг 1: Сохранение запроса пользователя
    try:
        supabase.table("chats").insert({
            "session_id": session_id,
            "role": "user",
            "content": message
        }).execute()
        logger.info("✅ Запрос сохранен в Supabase")
    except Exception as e:
        logger.error(f"❌ Ошибка Supabase (user): {e}")

    # Шаг 2: Генерация ответа через Groq
    try:
        logger.info("⏳ Запрос к модели qwen...")
        completion = groq_client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message}
            ],
            temperature=0.7,
            max_tokens=900,  # <-- Безопасный лимит, чтобы не превысить 1000 токенов Groq
            timeout=30       # <-- Защита от зависания Render
        )
        reply = completion.choices[0].message.content
        logger.info("✅ Ответ от Groq успешно получен")
    except Exception as e:
        logger.error(f"❌ Ошибка Groq: {e}")
        reply = f"⚠️ Ошибка ИИ: {e}. Попробуйте задать более короткий вопрос."

    # Шаг 3: Сохранение ответа ассистента
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 7860)))
