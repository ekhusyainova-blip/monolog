import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from groq import Groq

app = FastAPI()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
if not GROQ_API_KEY:
    raise ValueError("КРИТИЧЕСКАЯ ОШИБКА: GROQ_API_KEY не найден!")

groq_client = Groq(api_key=GROQ_API_KEY)

# 1. Эндпоинт: показать ВСЕ доступные модели
@app.get("/models")
async def list_models():
    try:
        models = groq_client.models.list()
        available = [m.id for m in models.data]
        return JSONResponse(
            content={
                "статус": "УСПЕХ ✅",
                "количество_моделей": len(available),
                "доступные_модели": available
            },
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
    except Exception as e:
        return JSONResponse(
            content={"статус": "ОШИБКА ❌", "детали": str(e)},
            headers={"Content-Type": "application/json; charset=utf-8"}
        )

# 2. Эндпоинт: тест с моделью mixtral (обычно доступна на всех тарифах)
@app.get("/test")
async def test_groq():
    try:
        completion = groq_client.chat.completions.create(
            model="mixtral-8x7b-32768",  # <-- Стабильная модель
            messages=[{"role": "user", "content": "Ответь ОЧЕНЬ КРАТКО (2 слова): тест успешен"}],
            temperature=0.7,
            timeout=15
        )
        return JSONResponse(
            content={
                "статус": "УСПЕХ ✅",
                "модель": "mixtral-8x7b-32768",
                "ответ_ИИ": completion.choices[0].message.content
            },
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
    except Exception as e:
        return JSONResponse(
            content={"статус": "ОШИБКА ❌", "детали": str(e)},
            headers={"Content-Type": "application/json; charset=utf-8"}
        )

# 3. Главная страница
@app.get("/")
async def root():
    return JSONResponse(
        content={
            "message": "Сервер работает. Откройте /models для списка моделей или /test для теста.",
            "эндпоинты": ["/models", "/test"]
        },
        headers={"Content-Type": "application/json; charset=utf-8"}
    )
