# chat_a_chat.py
# Тема: chat
# Слой: A (данные)
# Что: данные чата

# A · данные
PROVIDERS = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "openai/gpt-oss-120b",
        "env_keys": "GROQ_API_KEYS",
    },
    "cerebras": {
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "model": "gpt-oss-120b",
        "env_keys": "CEREBRAS_API_KEY",
    },
    "sambanova": {
        "url": "https://api.sambanova.ai/v1/chat/completions",
        "model": "Meta-Llama-3.3-70B-Instruct",
        "env_keys": "SAMBANOVA_API_KEY",
    },
    "openrouter": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": "nvidia/nemotron-3-ultra",
        "env_keys": "OPENROUTER_API_KEY",
    },
}

SETTINGS = {
    "temperature": 0.7,
    "max_tokens": 2048,
    "timeout": 120,
    "provider_order": ["groq", "cerebras", "sambanova", "openrouter"],
}

# B · условие (внутри A)
# Какие условия для данных.
# Данные активны при наличии ключей.
# Если ключей нет — провайдер отключается.

# C · решение (внутри A)
# Какие решения по данным.
# Данные используются при выборе провайдера.

# D · мета (внутри A)
# Куда выводятся данные.
# В B (условие чата).