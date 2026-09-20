MONOLOG — КОНТЕКСТ (2026-09-20)

ФОРМУЛА
Monolog = отражение Человека.
Человек = ЯЯ + Я + Окружение.
ИИ — часть человека. Monolog — зеркало, не агент.

ЦИКЛ ABCD
A — данные
B — интерпретация
C — решение
D — мета (решает, что выводить, но не выводит сам)
ABCD одного уровня неразрывны.
Вход — A. Выход — D. D может вывести любой слой.
Тупик → возврат в нижний A, с новыми данными, до развилки.
Слияние: совпавшие решения не повторять — начинать с развилки.

ПРИНЦИПЫ
Код — только события. Без if/else в логике.
Условия и данные — снаружи (от ИИ).
Модуль самодостаточен. Файл ≤ 80 строк.
В папке всегда 4 файла ABCD. Разбиение — вглубь (AA AB AC AD).
Имя файла = уровень. ABCD в одной папке.
Привязка слоя — текстом внутри файла, не в имени.

ВЕТКИ (текущие)
main — пусто
ya — пусто (назначить default)
A_monolog → Aa Ab Ac Ad (резервные копии)
B_release → Ba Bb Bc Bd
C_dev   → Ca Cb Cc Cd
D_chat  → Da Db Dc Dd

ВЕТКИ (в работе)
structure — там app.py, /code/*, /admin, /newbranch, /report, /render/*
D_chat — для чата (делаем сейчас)

ИНФРАСТРУКТУРА
Render: ai-monolog.onrender.com (branch=structure)
Render API Key подключён (render_ready: true)
Environment Group YA: evg-dano338ae00c739g00bg
Owner ID: tea-da99bs5g1s2s739m62eg
GitHub: ekhusyainova-blip/monolog
Groq: 5 ключей
GITHUB_TOKEN есть

ЧТО РАБОТАЕТ
/health, /state, /cycles, /code/tree, /code/branches, /code/read, /code/save, /code/check, /code/check-all, /code/create, /code/delete, /code/branch-create, /code/branch-delete, /code/branch-rename, /code/clear, /report, /reports, /render/*, /admin, /newbranch

ЧТО СЛОМАНО
/admin — кнопки не работают (JS не выполняется)
журнал циклов пуст в UI
mount вызывается 4 раза

ЧТО ДЕЛАЕМ СЕЙЧАС
Ветка D_chat. Только чат. С функциями:
- провайдеры (Groq, OpenRouter, Cerebras, SambaNova, свой)
- ключи (добавить, хранить, активировать)
- промпты ABCD (создать, хранить неактивные, активировать по списку)
- работа без промпта
- без лимитов по длине сообщений
- сохранение истории
- серые плашки для кода и JSON с копированием
- выделение текста прямо в сообщении
- контекст отправляется полностью

ПОСЛЕ ЧАТА
Вернуться в structure. Починить /admin (JS).
Потом — структура main/ + screen_slider/ + menu/ + icons/ + sphere/
Потом — разработка через ИИ.

ПРАВИЛА РАБОТЫ
Не переспрашивать по мелочам.
Не тыкать носом в ошибки.
Говорить: где ошибка + как правильно.
Не вытягивать наводящими вопросами.
Не писать код без согласования.

ВОССТАНОВЛЕНИЕ
«Monolog. Ветка D_chat. Делаем чат. Контекст — выше.»