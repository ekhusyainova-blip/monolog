import os
import gradio as gr
from groq import Groq

# 1. Проверка ключа (если его нет, приложение упадет сразу, и мы это увидим)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
if not GROQ_API_KEY:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: GROQ_API_KEY не найден в Render!")

groq_client = Groq(api_key=GROQ_API_KEY)

# 2. Функция с ПРИНУДИТЕЛЬНЫМ выводом логов (flush=True)
def process_query(message, history):
    # flush=True заставляет Python немедленно отправить текст в логи Render
    print("🚀 НАЧАЛО ОБРАБОТКИ. Сообщение:", message, flush=True) 
    
    try:
        print("⏳ Отправка запроса в Groq...", flush=True)
        
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": f"Ответь ОЧЕНЬ КРАТКО (2 слова) на: {message}"}],
            temperature=0.7,
            timeout=15  # <-- Жесткий таймаут 15 секунд. Если зависнет, мы сразу узнаем.
        )
        
        reply = completion.choices[0].message.content
        print("✅ Ответ от Groq получен успешно!", flush=True)
        return reply
        
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА GROQ: {e}", flush=True)
        return f"Ошибка ИИ: {e}"

# 3. Запуск Gradio с ОТКЛЮЧЕННОЙ очередью (queue=False) для мгновенной реакции
demo = gr.ChatInterface(
    fn=process_query,
    title="🔌 Тест Groq (Без Supabase)",
    description="Если этот тест работает, значит проблема была в коде Supabase или буферизации.",
    theme=gr.themes.Soft(primary_hue="blue")
)

app = demo.app

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)))
