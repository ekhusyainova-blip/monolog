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
            "message": "Сервер работает. Добавьте /test к адресу для проверки ИИ."
        },
        headers={"Content-Type": "application/json; charset=utf-8"}
    )

# 3. Тестовый эндпоинт с ПРАВИЛЬНОЙ моделью
@app.get("/test")
async def test_groq():
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # <-- АКтуальная модель
            messages=[{"role": "user", "content": "Ответь ОЧЕНЬ КРАТКО (2 слова): тест успешен"}],
            temperature=0.7,
            timeout=15
        )
        return JSONResponse(
            content={
                "статус": "УСПЕХ ✅",
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
