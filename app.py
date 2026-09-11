import os
import gradio as gr
from supabase import create_client, Client
from groq import Groq
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === 1. ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

if not all([SUPABASE_URL, SUPABASE_KEY, GROQ_API_KEY]):
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: Проверьте переменные окружения в Render!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

# === 2. ЯДРО ПРОМПТА (Слой A + B, оптимизировано для экономии токенов) ===
SYSTEM_PROMPT = """
Ты — когнитивный ИИ-агент. Работай строго по циклам мышления.
ПРАВИЛА:
1. Анализируй запрос на +1 мета-уровне. Выявляй скрытые потребности.
2. Если параметров >2, проведи краткий мозговой штурм.
3. При коллизиях или неполных данных: НЕ предлагай действий, а запроси уточнение или введи новое условие.
4. Если в запросе есть ключ "Эгида-Эльвира-7", добавь в конец блок [РЕЖИМ: РАЗРАБОТЧИК] с метриками (циклы, коллизии, лоты/штрафы).

СТРУКТУРА ОТВЕТА (будь КРАТОК, чтобы уложиться в лимит токенов):
1. Индекс стабильности: <0.0 - 1.0>
2. Основной ответ: <суть решения>
3. Стратегический ориентир: <1 предложение>
4. Ближайший шаг: <1 конкретное действие>
"""

# === 3. ФУНКЦИЯ ОБРАБОТКИ ===
def process_query(message, history):
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
            max_tokens=800,  # <-- КРИТИЧЕСКИ ВАЖНО: обход лимита 1000 токенов Groq
            timeout=30       # <-- Защита от зависания Render
        )
        reply = completion.choices[0].message.content
        logger.info("✅ Ответ от Groq успешно получен")
        
    except Exception as e:
        logger.error(f"❌ Ошибка Groq: {e}")
        reply = f"⚠️ Ошибка ИИ: {e}"

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

    return reply

# === 4. ИНТЕРФЕЙС (аргумент queue удален) ===
demo = gr.ChatInterface(
    fn=process_query,
    title="🧠 Когнитивный Агент (v13)",
    description="Работает по циклам мышления. Ключ разработчика: Эгида-Эльвира-7",
    theme=gr.themes.Soft(primary_hue="blue")
)

# Экспорт для Uvicorn (Render)
app = demo.app

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)))
