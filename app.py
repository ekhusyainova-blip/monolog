import os
import requests
import json
import time
from datetime import datetime
import gradio as gr
from supabase import create_client, Client
from groq import Groq

# === НАСТРОИКИ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ===
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# === ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ ===
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

# === ЛОГИКА АЛГОРИТМА (ЦИКЛЫ, ИНДЕКСЫ, ФИЛЬТРЫ) ===
def process_query(user_query, session_id):
    # 1. Сохраняем запрос в БД
    supabase.table("chats").insert({
        "session_id": session_id,
        "role": "user",
        "content": user_query,
        "timestamp": datetime.now().isoformat()
    }).execute()
    
    # 2. Вызов Groq для генерации ответа (с промптом алгоритма)
    prompt = f"""
    Ты — ИИ-агент, работающии по когнитивнои модели с циклами мышления.
    Запрос пользователя: {user_query}
    
    Ответь в формате:
    1. Индекс стабильности ответа (0–1)
    2. Основнои ответ
    3. Стратегическии ориентир
    4. Ближаишии шаг
    """
    
    completion = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    reply = completion.choices[0].message.content
    
    # 3. Сохраняем ответ в БД
    supabase.table("chats").insert({
        "session_id": session_id,
        "role": "assistant",
        "content": reply,
        "timestamp": datetime.now().isoformat()
    }).execute()
    
    return reply

# === ВЕБ-ИНТЕРФЕИС (Gradio) ===
def chat_interface(message, history):
    session_id = str(time.time())  # простая сессия
    reply = process_query(message, session_id)
    return reply

# === СОЗДАНИЕ ТАБЛИЦ В SUPABASE (выполняется один раз) ===
def init_db():
    try:
        # Проверяем, есть ли таблица "chats"
        supabase.table("chats").select("*").limit(1).execute()
    except:
        # Если нет — создаем через SQL (выполнить вручную в Supabase SQL Editor)
        print("Таблица не наидена. Выполните SQL-скрипт из инструкции.")

# === АВТОПИНГ (чтобы Render не засыпал) ===
def keep_alive():
    try:
        requests.get("https://your-app-name.onrender.com")
    except:
        pass

# === ЗАПУСК ===
with gr.Blocks(theme=gr.themes.Soft(primary_hue="blue"), title="Ваш ИИ-агент") as demo:
    gr.Markdown("# 🤖 Ваш когнитивныи агент")
    gr.Markdown("Введите задачу, и агент предложит стабильное решение по вашему алгоритму.")
    
    chatbot = gr.Chatbot()
    msg = gr.Textbox(label="Ваш запрос", placeholder="Напишите здесь...")
    clear = gr.ClearButton([msg, chatbot])
    
    def respond(message, chat_history):
        reply = chat_interface(message, None)
        chat_history.append((message, reply))
        return "", chat_history
    
    msg.submit(respond, [msg, chatbot], [msg, chatbot])

if __name__ == "__main__":
    demo.launch()
