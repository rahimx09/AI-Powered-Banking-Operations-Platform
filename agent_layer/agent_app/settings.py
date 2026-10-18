import math
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    backend_url: str
    backend_timeout_seconds: float


def get_settings() -> Settings:
    backend_url = os.getenv(
        "BANKING_BACKEND_URL",
        "http://127.0.0.1:8000",
    ).strip().rstrip("/")
    if not backend_url:
        raise ValueError("BANKING_BACKEND_URL must not be empty")

    raw_timeout = os.getenv("BANKING_BACKEND_TIMEOUT_SECONDS", "10")
    try:
        timeout = float(raw_timeout)
    except ValueError as exc:
        raise ValueError(
            "BANKING_BACKEND_TIMEOUT_SECONDS must be a number"
        ) from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError(
            "BANKING_BACKEND_TIMEOUT_SECONDS must be greater than zero"
        )

    return Settings(
        backend_url=backend_url,
        backend_timeout_seconds=timeout,
    )