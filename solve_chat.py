# solve_chat.py

from groq import Groq
from interpret_chat import build_messages

client = Groq(api_key=os.environ["GROQ_API_KEY"])

MODEL = "openai/gpt-oss-120b"


def solve(reflection: str, query: str, first_time: bool) -> str:
    messages = build_messages(reflection, query, first_time)

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
    )

    return response.choices[0].message.content