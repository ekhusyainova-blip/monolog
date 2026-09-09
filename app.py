import os
import gradio as gr
from supabase import create_client, Client
from groq import Groq

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
# .strip() автоматически удалит случайные пробелы по краям
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

# === ЗАЩИТНАЯ ПРОВЕРКА ===
if not SUPABASE_URL or not SUPABASE_URL.startswith("https://"):
    raise ValueError(f"КРИТИЧЕСКАЯ ОШИБКА: SUPABASE_URL не задан или некорректен! Проверьте настройки Render. Получено: '{SUPABASE_URL}'")

if not SUPABASE_KEY:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: SUPABASE_KEY не задан! Проверьте настройки Render.")

if not GROQ_API_KEY:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: GROQ_API_KEY не задан! Проверьте настройки Render.")

# === ИНИЦИАЛИЗАЦИЯ КЛИЕНТОВ ===
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

# === ФУНКЦИЯ ОБРАБОТКИ СООБЩЕНИЙ (ОСНОВНАЯ ЛОГИКА) ===
def process_query(user_query, session_id="default"):
    # 1. Сохраняем запрос в БД (опционально)
    try:
        supabase.table("chats").insert({
            "session_id": session_id,
            "role": "user",
            "content": user_query,
            "timestamp": "now()"
        }).execute()
    except Exception as e:
        print(f"Ошибка сохранения в Supabase: {e}")
    
    # 2. Генерация ответа через Groq
    prompt = f"""
    Ты — ИИ-агент, работающий по когнитивной модели с циклами мышления.
    Запрос пользователя: {user_query}
    
    Ответь в формате:
    1. Индекс стабильности ответа (0–1)
    2. Основной ответ
    3. Стратегический ориентир
    4. Ближайший шаг
    """
    
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        reply = completion.choices[0].message.content
    except Exception as e:
        reply = f"Ошибка вызова Groq: {e}. Проверьте API-ключ."
    
    # 3. Сохраняем ответ в БД
    try:
        supabase.table("chats").insert({
            "session_id": session_id,
            "role": "assistant",
            "content": reply,
            "timestamp": "now()"
        }).execute()
    except Exception as e:
        print(f"Ошибка сохранения ответа: {e}")
    
    return reply

# === ПРОСТОЙ ИНТЕРФЕЙС (ChatInterface) ===
def chat_interface(message, history):
    return process_query(message)

# === ЗАПУСК ===
demo = gr.ChatInterface(
    fn=chat_interface,
    title="🤖 Ваш когнитивный агент",
    description="Введите задачу, и агент предложит стабильное решение по вашему алгоритму.",
    theme=gr.themes.Soft(primary_hue="blue")
)

if __name__ == "__main__":
    demo.launch()
