import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from groq import Groq

app = FastAPI()

# 1. Проверка ключа
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
if not GROQ_API_KEY:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: GROQ_API_KEY не найден!")

groq_client = Groq(api_key=GROQ_API_KEY)

# 2. Главная страница
@app.get("/")
async def root():
    return JSONResponse(
        content={
            "message": "Сервер работает. Откройте /test для проверки ИИ.",
            "доступные_модели": ["qwen/qwen3.6-27b", "openai/gpt-oss-20b"]
        },
        headers={"Content-Type": "application/json; charset=utf-8"}
        )

# 3. Тестовый эндпоинт с РАБОЧЕЙ моделью
@app.get("/test")
async def test_groq():
    try:
        completion = groq_client.chat.completions.create(
            model="qwen/qwen3.6-27b",  # <-- ГАРАНТИРОВАННО РАБОЧАЯ МОДЕЛЬ ИЗ ВАШЕГО СПИСКА
            messages=[{"role": "user", "content": "Ответь ОЧЕНЬ КРАТКО (2 слова) на русском: тест успешен"}],
            temperature=0.7,
            timeout=15
        )
        return JSONResponse(
            content={
                "статус": "УСПЕХ ✅",
                "модель": "qwen/qwen3.6-27b",
                "ответ_ИИ": completion.choices[0].message.content
            },
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
    except Exception as e:
        return JSONResponse(
            content={
                "статус": "ОШИБКА ❌",
                "детали": str(e)
            },
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
