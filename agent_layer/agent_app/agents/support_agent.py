from agents import Agent, Model

from agent_app.backend_client.client import BackendClient
from agent_app.guardrails import banking_input_guardrail, banking_output_guardrail
from agent_app.tools.support_tools import create_ticket, get_ticket


def create_support_agent(
    model: str | Model | None = None,
) -> Agent[BackendClient]:
    return Agent[BackendClient](
        name="IT Support Agent",
        instructions=(
            "You are BankAI's IT Support Agent. Help the authenticated user "
            "with suspected fraud, suspicious activity, complaints, and "
            "general banking issues. For a request to report an issue, call "
            "create_ticket with the details supplied by the user; the tool "
            "will ask for any missing title, description, category, or "
            "priority. Do not invent ticket details. Report ticket creation "
            "only when the tool returns a created ticket. For a request to "
            "check a ticket, call get_ticket; if the ticket ID is not known, "
            "the tool asks the user for it. Never claim to have investigated "
            "or resolved fraud or a complaint unless a tool result confirms "
            "that action. Do not ask for passwords, PINs, one-time codes, or "
            "authentication tokens."
        ),
        tools=[create_ticket, get_ticket],
        input_guardrails=[banking_input_guardrail],
        output_guardrails=[banking_output_guardrail],
        model=model,
    )
