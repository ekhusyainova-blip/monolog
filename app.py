import os
import gradio as gr
from supabase import create_client, Client
from groq import Groq
import logging

# Настройка логирования для четкого отслеживания в Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

# === ЗАЩИТНАЯ ПРОВЕРКА ===
if not SUPABASE_URL or not SUPABASE_URL.startswith("https://"):
    raise ValueError(f"КРИТИЧЕСКАЯ ОШИБКА: SUPABASE_URL некорректен! Получено: '{SUPABASE_URL}'")
if not SUPABASE_KEY or not SUPABASE_KEY.startswith("eyJ"):
    raise ValueError(f"КРИТИЧЕСКАЯ ОШИБКА: SUPABASE_KEY некорректен!")
if not GROQ_API_KEY:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: GROQ_API_KEY не задан!")

# === ИНИЦИАЛИЗАЦИЯ ===
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

# === ФУНКЦИЯ ОБРАБОТКИ ===
def process_query(user_query, history):
    logger.info(f"🚀 НАЧАЛО ОБРАБОТКИ. Запрос: {user_query[:30]}...")
    
    # 1. Сохраняем запрос в БД
    try:
        supabase.table("chats").insert({
            "session_id": "default",
            "role": "user",
            "content": user_query
        }).execute()
        logger.info("✅ Запрос сохранен в Supabase")
    except Exception as e:
        logger.error(f"❌ Ошибка Supabase (запрос): {e}")

    # 2. Генерация ответа через Groq
    # ВАЖНО: Добавлен timeout=30, чтобы избежать вечного зависания на Render
    prompt = f"""
    Ты — ИИ-агент, работающий по когнитивной модели с циклами мышления.
    Запрос пользователя: {user_query}

    Ответь строго в формате:
    1. Индекс стабильности ответа (0–1)
    2. Основной ответ
    3. Стратегический ориентир
    4. Ближайший шаг
    """

    try:
        logger.info("⏳ Отправка запроса в Groq...")
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            timeout=30  # <-- КРИТИЧЕСКИ ВАЖНО: обрывает зависший запрос через 30 сек
        )
        reply = completion.choices[0].message.content
        logger.info("✅ Ответ от Groq получен")
    except Exception as e:
        logger.error(f"❌ Ошибка Groq: {e}")
        reply = f"⚠️ Ошибка ИИ: {e}. Проверьте API-ключ или лимиты."

    # 3. Сохраняем ответ в БД
    try:
        supabase.table("chats").insert({
            "session_id": "default",
            "role": "assistant",
            "content": reply
        }).execute()
        logger.info("✅ Ответ сохранен в Supabase")
    except Exception as e:
        logger.error(f"❌ Ошибка Supabase (ответ): {e}")

    return reply

# === ИНТЕРФЕЙС ===
# history передается автоматически в gr.ChatInterface
demo = gr.ChatInterface(
    fn=process_query,
    title="🤖 Когнитивный агент",
    description="Введите задачу. Агент работает по циклам мышления.",
    theme=gr.themes.Soft(primary_hue="blue")
)

app = demo.app

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)))
