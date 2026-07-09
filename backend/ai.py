import os

from google import genai
from google.genai import types


from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env.example")

load_dotenv()
import os
from dotenv import load_dotenv

loaded = load_dotenv()

print("Loaded .env:", loaded)
print("Current directory:", os.getcwd())
print("GEMINI_API_KEY:", repr(os.getenv("GEMINI_API_KEY")))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# Free-tier-friendly model. If Google renames/retires this model, check
# https://ai.google.dev/gemini-api/docs/models for the current free-tier
# model name and update MODEL_NAME below.
MODEL_NAME = "gemini-2.0-flash"

GENERAL_SYSTEM_PROMPT = (
    "あなたは武蔵野大学の学生向けAI相談アシスタントです。"
    "イベント、部活・サークル、ゼミ、研究、就職・インターンシップに関する質問に、"
    "親切で分かりやすい日本語で答えてください。分からないことは正直に「分かりません」と答え、"
    "大学の公式窓口に確認するよう案内してください。"
)


def _build_event_context(event) -> str:
    category_labels = {
        "event": "イベント",
        "club": "部活・サークル",
        "seminar": "ゼミ",
        "research": "研究",
        "career": "就職・インターンシップ",
    }
    return (
        f"以下は、学生が質問している具体的な投稿の情報です。この情報を踏まえて回答してください。\n"
        f"カテゴリー: {category_labels.get(event.category, event.category)}\n"
        f"タイトル: {event.title}\n"
        f"説明: {event.description or '（説明なし）'}\n"
        f"チーム人数: {event.team_size}人\n"
        f"定員: {event.max_participants if event.max_participants else '定員なし'}\n"
    )


def ask_gemini(message: str, event=None) -> str:
    """
    Sends a single message to Gemini and returns the reply text.
    `event` is an optional models.Event — when provided, its details are
    included as context so the AI can answer questions specific to that
    posting.

    Raises RuntimeError if GEMINI_API_KEY isn't configured, so the caller
    can turn that into a clean HTTP error instead of a confusing crash.
    """
    if not _client:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it as an environment variable "
            "on your backend (Render: Environment tab; locally: .env file)."
        )

    system_prompt = GENERAL_SYSTEM_PROMPT
    if event is not None:
        system_prompt += "\n\n" + _build_event_context(event)

    response = _client.models.generate_content(
        model=MODEL_NAME,
        contents=message,
        config=types.GenerateContentConfig(system_instruction=system_prompt),
    )
    return response.text