# app.py
# Точка входа Monolog.
# Переключатель APP_MODE: 'stub' — заглушка, 'full' — полный backend.

import os

APP_MODE = os.getenv("APP_MODE", "stub").strip().lower()


if APP_MODE == "stub":
    from core_backend.stub import app

elif APP_MODE == "full":
    from core_backend.full_app import app

else:
    raise RuntimeError(f"APP_MODE='{APP_MODE}' — неизвестное значение. Используй 'stub' или 'full'.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))