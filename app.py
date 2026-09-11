import os
from fastapi import FastAPI
from groq import Groq

# Создаем простое веб-приложение
app = FastAPI()

# 1. Проверка ключа
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
if not GROQ_API_KEY:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: GROQ_API_KEY не найден в Render!")

groq_client = Groq(api_key=GROQ_API_KEY)

# 2. Главная страница
@app.get("/")
async def root():
    return {"message": "Сервер работает исправно. Добавьте /test к адресу в браузере для проверки ИИ."}

# 3. Тестовый эндпоинт для ИИ
@app.get("/test")
async def test_groq():
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Ответь ОЧЕНЬ КРАТКО (2 слова): тест успешен"}],
            temperature=0.7,
            timeout=15  # Жесткий таймаут 15 секунд
        )
        return {
            "статус": "УСПЕХ ✅", 
            "ответ_ИИ": completion.choices[0].message.content
        }
    except Exception as e:
        return {
            "статус": "ОШИБКА ❌", 
            "детали": str(e)
        }
