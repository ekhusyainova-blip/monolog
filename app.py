import os
import gradio as gr
from supabase import create_client, Client
from groq import Groq

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

# === ИНИЦИАЛИЗАЦИЯ КЛИЕНТОВ ===
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) # <-- Это строка ~23, где происходит краш


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

print
