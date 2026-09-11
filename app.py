import os
import gradio as gr
from supabase import create_client, Client
from groq import Groq
import logging

# Настройка логирования для четкого отслеживания в Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === 1. ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

if not all([SUPABASE_URL, SUPABASE_KEY, GROQ_API_KEY]):
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: Проверьте переменные окружения в Render (SUPABASE_URL, SUPABASE_KEY, GROQ_API_KEY)!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

# === 2. ЯДРО ПРОМПТА (Слой A + Слой B, оптимизированная версия) ===
SYSTEM_PROMPT = """
Ты — когнитивный ИИ-агент, работающий по строгим циклам мышления.
[ПРАВИЛА ОБРАБОТКИ]
1. Обрабатывай запрос на +1 мета-уровне выше предметной области.
2. Выявляй скрытые потребности и синхронизируй решение с плоскостью пользователя.
3. Если запрос содержит >2 параметров, проведи мозговой штурм (мин. 1 итерация на параметр, мин. 2 итерации обсуждения финала).
4. При коллизиях, неполной картине восприятия или выключенном фильтре информации: НЕ предлагай активных действий. Предложи собрать данные, скорректировать восприятие или ввести новое условие.
5. Если пользователь ввёл ключ "Эгида-Эльвира-7", добавь в конец ответа блок [РЕЖИМ: РАЗРАБОТЧИК] с технической метрикой (циклы, коллизии, лоты/штрафы, оценка восприятия).

[СТРУКТУРА ОТВЕТА]
1. Индекс стабильности: <0.0 - 1.0>
2. Основной ответ: <развернутое решение>
3. Стратегический ориентир: <кратко>
4. Ближайший шаг: <конкретное действие>
"""

# === 3. ФУНКЦИЯ ОБРАБОТКИ ===
def process_query(message, history):
    logger.info(f"🚀 НАЧАЛО ОБРАБОТКИ: {message[:40]}...")
    session_id = "session_default" # Временно фиксированная, позже можно сделать динамическую генерацию UUID
    
    # Шаг 1: Сохранение запроса пользователя в Supabase
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
        logger.info("⏳ Запрос к модели qwen/qwen3.6-27b...")
        completion = groq_client.chat.completions.create(
            model="qwen/qwen3.6-27b", # Проверенная рабочая модель с нативным мышлением
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message}
            ],
            temperature=0.7,
            timeout=30 # Критически важно: обрывает зависший запрос через 30 сек, спасая Render Free
        )
        reply = completion.choices[0].message.content
        logger.info("✅ Ответ от Groq успешно получен")
        
    except Exception as e:
        logger.error(f"❌ Ошибка Groq: {e}")
        reply = f"⚠️ Ошибка ИИ: {e}. Проверьте API-ключ или лимиты."

    # Шаг 3: Сохранение ответа ассистента в Supabase
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

# === 4. ИНТЕРФЕЙС ===
demo = gr.ChatInterface(
    fn=process_query,
    title="🧠 Когнитивный Агент (v13)",
    description="Работает по циклам мышления. Для активации режима разработчика введите в чат ключ: Эгида-Эльвира-7",
    theme=gr.themes.Soft(primary_hue="blue"),
    queue=False # КРИТИЧЕСКИ ВАЖНО: отключает внутреннюю очередь Gradio, предотвращая зависания на мобильных
)

# Экспорт для Uvicorn (Render)
app = demo.app

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)))
