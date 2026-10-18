from agents import Agent, Model
from agent_app.agents.banking_agent import create_banking_agent
from agent_app.agents.support_agent import create_support_agent
from agent_app.backend_client.client import BackendClient
from agent_app.guardrails import banking_input_guardrail, banking_output_guardrail


def create_triage_agent(model: str | Model | None = None) -> Agent[BackendClient]:
    return Agent[BackendClient](
        name="Banking Triage Agent",
        instructions=(
            "You are the BankAI triage agent. Identify the user's primary "
            "request and hand it off to the appropriate specialist. Route "
            "accounts, balances, transactions, beneficiaries, and payments "
            "to the Banking Agent. Route suspected fraud, suspicious activity, "
            "complaints, and general banking issues to the IT Support Agent. "
            "Do not claim that a handoff or operation occurred unless it did. "
            "For unsupported requests, explain the current limits."
        ),
        handoffs=[
            create_banking_agent(model=model),
            create_support_agent(model=model),
        ],
        input_guardrails=[banking_input_guardrail],
        output_guardrails=[banking_output_guardrail],
        model=model,
    )