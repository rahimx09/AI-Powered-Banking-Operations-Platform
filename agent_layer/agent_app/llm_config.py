import os
from pathlib import Path

from agents import (
    OpenAIChatCompletionsModel,
    set_tracing_disabled,
    set_tracing_export_api_key,
)
from dotenv import dotenv_values, load_dotenv
from openai import AsyncOpenAI


GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
AGENT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def load_agent_environment() -> None:
    load_dotenv(dotenv_path=AGENT_ENV_FILE, override=False)


def create_gemini_model(
    model_name: str | None = None,
) -> tuple[OpenAIChatCompletionsModel, AsyncOpenAI]:
    load_agent_environment()
    file_settings = dotenv_values(AGENT_ENV_FILE)
    gemini_api_key = (
        file_settings.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY", "")
    ).strip()
    tracing_api_key = (
        file_settings.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    ).strip()
    tracing_setting = file_settings.get("AGENT_TRACING_ENABLED")
    if tracing_setting is None:
        tracing_setting = os.getenv("AGENT_TRACING_ENABLED", "false")
    normalized_tracing_setting = tracing_setting.strip().lower()
    if normalized_tracing_setting not in {"true", "false"}:
        raise ValueError("AGENT_TRACING_ENABLED must be 'true' or 'false'")
    tracing_enabled = normalized_tracing_setting == "true"
    configured_model = (
        model_name or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    ).strip()

    missing_settings = ["GEMINI_API_KEY"] if not gemini_api_key else []
    if tracing_enabled and not tracing_api_key:
        missing_settings.append("OPENAI_API_KEY (required when tracing is enabled)")
    if missing_settings:
        raise ValueError(
            "Missing required agent configuration: "
            + ", ".join(missing_settings)
        )
    if not configured_model:
        raise ValueError("GEMINI_MODEL must not be empty")

    gemini_client = AsyncOpenAI(
        api_key=gemini_api_key,
        base_url=GEMINI_BASE_URL,
    )
    set_tracing_disabled(not tracing_enabled)
    if tracing_enabled:
        set_tracing_export_api_key(tracing_api_key)
    return (
        OpenAIChatCompletionsModel(
            model=configured_model,
            openai_client=gemini_client,
        ),
        gemini_client,
    )
