import re
from typing import Any

from agents import (
    Agent,
    GuardrailFunctionOutput,
    RunContextWrapper,
    input_guardrail,
    output_guardrail,
)


_MAX_INPUT_LENGTH = 4000
_MAX_OUTPUT_LENGTH = 5000
_INSTRUCTION_OVERRIDE = re.compile(
    r"\b(ignore|disregard|override)\b.{0,60}\b"
    r"(previous|prior|system|developer|all)\b.{0,30}\b(instruction|prompt|rule)s?\b",
    re.IGNORECASE,
)
_PROMPT_DISCLOSURE = re.compile(
    r"\b(reveal|print|show|repeat|disclose)\b.{0,60}\b"
    r"(system|developer|hidden)\s+(prompt|instruction)s?\b",
    re.IGNORECASE,
)
_OTHER_USER_DATA = re.compile(
    r"\b(other|another|someone else['’]s)\b.{0,50}\b"
    r"(user|customer|person)['’]s?\b.{0,50}\b"
    r"(account|balance|transaction|personal|private)\b",
    re.IGNORECASE,
)
_CREDENTIAL_VALUE = re.compile(
    r"\b(password|passcode|pin|otp|one[- ]time code|access token)\b"
    r"\s*(?::|=)\s*(?!required\b|needed\b|not\b)\S+",
    re.IGNORECASE,
)
_USER_CREDENTIAL_STATEMENT = re.compile(
    r"\bmy\s+(password|passcode|pin|otp|one[- ]time code|access token)"
    r"\s+is\s+(?!required\b|needed\b|not\b|unknown\b|hidden\b)\S+",
    re.IGNORECASE,
)
_BEARER_TOKEN = re.compile(r"\bbearer\s+[a-z0-9._~-]{12,}\b", re.IGNORECASE)


def _input_text(input_data: str | list[Any]) -> str:
    if isinstance(input_data, str):
        return input_data
    parts: list[str] = []
    for item in input_data:
        if isinstance(item, dict):
            content = item.get("content")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                parts.extend(
                    part["text"]
                    for part in content
                    if isinstance(part, dict)
                    and isinstance(part.get("text"), str)
                )
    return "\n".join(parts)


@input_guardrail(name="banking_input_safety", run_in_parallel=False)
def banking_input_guardrail(
    _context: RunContextWrapper[Any],
    _agent: Agent[Any],
    input_data: str | list[Any],
) -> GuardrailFunctionOutput:
    text = _input_text(input_data)
    reason: str | None = None
    if len(text) > _MAX_INPUT_LENGTH:
        reason = f"Message exceeds the {_MAX_INPUT_LENGTH}-character limit."
    elif _CREDENTIAL_VALUE.search(text) or _USER_CREDENTIAL_STATEMENT.search(text):
        reason = (
            "Do not share passwords, PINs, one-time codes, or access tokens. "
            "Please remove authentication secrets and try again."
        )
    elif _INSTRUCTION_OVERRIDE.search(text) or _PROMPT_DISCLOSURE.search(text):
        reason = "Requests to override or reveal internal agent instructions are blocked."
    elif _OTHER_USER_DATA.search(text):
        reason = "The agent can only access the authenticated user's own information."

    return GuardrailFunctionOutput(
        output_info=reason or "Input passed banking safety checks.",
        tripwire_triggered=reason is not None,
    )


@output_guardrail(name="banking_output_safety")
def banking_output_guardrail(
    _context: RunContextWrapper[Any],
    _agent: Agent[Any],
    agent_output: Any,
) -> GuardrailFunctionOutput:
    reason: str | None = None
    if not isinstance(agent_output, str) or not agent_output.strip():
        reason = "The agent response must be non-empty text."
    elif len(agent_output) > _MAX_OUTPUT_LENGTH:
        reason = f"Response exceeds the {_MAX_OUTPUT_LENGTH}-character limit."
    elif _CREDENTIAL_VALUE.search(agent_output) or _BEARER_TOKEN.search(
        agent_output
    ):
        reason = "The response appears to contain authentication secrets."

    return GuardrailFunctionOutput(
        output_info=reason or "Output passed banking safety checks.",
        tripwire_triggered=reason is not None,
    )
