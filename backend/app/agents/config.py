import os

from agents import OpenAIChatCompletionsModel, set_tracing_export_api_key
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

_gemini_client: AsyncOpenAI | None = None


def get_banking_model() -> OpenAIChatCompletionsModel:
    """Create the Gemini-backed model and configure the separate trace exporter."""
    global _gemini_client

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    tracing_api_key = os.getenv("OPENAI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    missing_keys = [
        name
        for name, value in (
            ("GEMINI_API_KEY", gemini_api_key),
            ("OPENAI_API_KEY", tracing_api_key),
        )
        if not value
    ]
    if missing_keys:
        raise RuntimeError(
            "Banking agent configuration is missing: "
            + ", ".join(missing_keys)
        )

    if _gemini_client is None:
        _gemini_client = AsyncOpenAI(
            api_key=gemini_api_key,
            base_url=GEMINI_BASE_URL,
        )

    set_tracing_export_api_key(tracing_api_key)
    return OpenAIChatCompletionsModel(
        model=model_name,
        openai_client=_gemini_client,
    )


async def close_banking_model() -> None:
    """Close the shared Gemini client when the FastAPI application shuts down."""
    global _gemini_client

    if _gemini_client is not None:
        await _gemini_client.close()
        _gemini_client = None