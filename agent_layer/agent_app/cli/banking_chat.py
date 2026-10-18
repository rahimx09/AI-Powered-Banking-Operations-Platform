import argparse
import asyncio
import getpass
import json
import sys
from collections.abc import Callable, Sequence
from decimal import Decimal
from typing import Any

from agents import Agent, RunState, Runner
from agents.items import ToolApprovalItem
from agents.exceptions import AgentsException
from openai import OpenAIError

from agent_app.agents.triage_agent import create_triage_agent
from agent_app.backend_client.client import BackendClient, BackendError
from agent_app.llm_config import create_gemini_model, load_agent_environment
from agent_app.settings import get_settings
from agent_app.tools.banking_tools import fetch_payment_details


def run_cli(
    client: BackendClient,
    *,
    agent: Agent[BackendClient] | None = None,
    input_fn: Callable[[str], str] | None = None,
    password_fn: Callable[[str], str] | None = None,
    output_fn: Callable[[str], Any] | None = None,
) -> int:
    read_input = input_fn or input
    read_password = password_fn or getpass.getpass
    write_output = output_fn or print
    triage_agent = agent or create_triage_agent()

    try:
        health = client.health_check()
    except BackendError as exc:
        write_output(f"Backend connection failed: {exc}")
        return 1
    if not isinstance(health, dict) or health.get("status") != "ok":
        write_output("Backend connection failed: unexpected health response")
        return 1

    try:
        email = read_input("Email: ").strip()
        password = read_password("Password: ")
    except (EOFError, KeyboardInterrupt):
        write_output("\nLogin cancelled.")
        return 1
    if not email or not password:
        write_output("Email and password are required.")
        return 1

    try:
        client.login(email, password)
        user = client.get_current_user()
    except BackendError as exc:
        write_output(f"Backend authentication failed: {exc}")
        return 1

    if not isinstance(user, dict):
        write_output("Backend authentication failed: invalid user response")
        return 1

    write_output(
        f"Banking Agent ready for {user.get('name') or email}. "
        "Ask about your current balance, or type 'exit' to quit."
    )

    def approve_interruption(
        interruption: ToolApprovalItem,
        state: RunState[BackendClient],
    ) -> None:
        tool_name = interruption.name or "unknown tool"
        write_output(
            f"Approval requested by {interruption.agent.name}: {tool_name}"
        )
        approval_key: tuple[int, Decimal] | None = None
        if tool_name == "make_payment_request":
            try:
                arguments = json.loads(interruption.arguments or "")
                if not isinstance(arguments, dict):
                    raise ValueError("Payment approval arguments must be an object")
                beneficiary_id = arguments.get("beneficiary_id")
                amount = arguments.get("amount")
                decimal_amount, name, account_number, bank_name = (
                    fetch_payment_details(client, beneficiary_id, amount)
                )
                write_output(
                    "Payment details:\n"
                    f"Amount: {decimal_amount:.2f}\n"
                    f"Beneficiary: {name}\n"
                    f"Bank: {bank_name}\n"
                    f"Account number: {account_number}"
                )
                approval_key = (beneficiary_id, decimal_amount)
                approved_details = (name, account_number, bank_name)
            except (BackendError, TypeError, ValueError) as exc:
                write_output(f"Could not verify payment details: {exc}")
                state.reject(
                    interruption,
                    rejection_message=(
                        "Payment was not submitted because its details could "
                        "not be verified."
                    ),
                )
                return
        else:
            write_output(f"Tool arguments: {interruption.arguments or '(unavailable)'}")
            approved_details = None

        while True:
            try:
                answer = read_input("Approve this tool call? Type yes or no: ")
            except (EOFError, KeyboardInterrupt):
                write_output("Approval cancelled; the tool call was rejected.")
                state.reject(
                    interruption,
                    rejection_message="The user rejected this tool call.",
                )
                return
            normalized_answer = answer.strip().lower()
            if normalized_answer in {"yes", "y"}:
                if approval_key is not None and approved_details is not None:
                    client.approve_payment(
                        approval_key[0],
                        approval_key[1],
                        *approved_details,
                    )
                state.approve(interruption)
                return
            if normalized_answer in {"no", "n"}:
                write_output("Tool call rejected; no payment was submitted.")
                state.reject(
                    interruption,
                    rejection_message="The user rejected this tool call.",
                )
                return
            write_output("Please enter yes or no.")
    def get_bene_details_from_cli(missing_fields: set[str]) -> dict[str, str]:
        prompts = {
            "name": "Beneficiary name: ",
            "account_number": "Beneficiary account number: ",
            "bank_name": "Beneficiary bank name: ",
        }
        write_output("Enter the missing beneficiary details:")
        collected: dict[str, str] = {}
        for field, prompt in prompts.items():
            if field not in missing_fields:
                continue
            while True:
                try:
                    value = read_input(prompt).strip()
                except (EOFError, KeyboardInterrupt) as exc:
                    raise ValueError(
                        "Beneficiary creation cancelled; no beneficiary was created"
                    ) from exc
                if value:
                    collected[field] = value
                    break
                write_output(f"{field.replace('_', ' ').capitalize()} is required.")
        return collected

    client.set_beneficiary_details_handler(get_bene_details_from_cli)

    def get_account_type_from_cli() -> str:
        write_output("====== Enter New Account Details ======")
        while True:
            try:
                account_type = read_input("Account type: ").strip()
            except (EOFError, KeyboardInterrupt) as exc:
                raise ValueError(
                    "Account creation cancelled; no account was created"
                ) from exc
            if account_type:
                return account_type
            write_output("Account type is required.")

    client.set_account_type_handler(get_account_type_from_cli)

    def get_ticket_details_from_cli(missing_fields: set[str]) -> dict[str, str]:
        prompts = {
            "title": "Ticket title: ",
            "description": "Issue description: ",
            "category": "Issue category: ",
            "priority": "Ticket priority: ",
        }
        write_output("Enter the missing support-ticket details:")
        collected: dict[str, str] = {}
        for field, prompt in prompts.items():
            if field not in missing_fields:
                continue
            while True:
                try:
                    value = read_input(prompt).strip()
                except (EOFError, KeyboardInterrupt) as exc:
                    raise ValueError(
                        "Ticket creation cancelled; no ticket was created"
                    ) from exc
                if value:
                    collected[field] = value
                    break
                write_output(f"{field.capitalize()} is required.")
        return collected

    client.set_ticket_details_handler(get_ticket_details_from_cli)

    def get_ticket_id_from_cli() -> int:
        while True:
            try:
                value = read_input("Ticket ID: ").strip()
            except (EOFError, KeyboardInterrupt) as exc:
                raise ValueError("Ticket lookup cancelled") from exc
            try:
                ticket_id = int(value)
            except ValueError:
                write_output("Ticket ID must be a positive integer.")
                continue
            if ticket_id > 0:
                return ticket_id
            write_output("Ticket ID must be a positive integer.")

    client.set_ticket_id_handler(get_ticket_id_from_cli)

    try:
        while True:
            try:
                message = read_input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                write_output("\nGoodbye.")
                return 0
            if message.lower() in {"exit", "quit"}:
                write_output("Goodbye.")
                return 0
            if not message:
                continue

            try:
                result = Runner.run_sync(triage_agent, message, context=client)
                while result.interruptions:
                    state = result.to_state()
                    for interruption in result.interruptions:
                        approve_interruption(interruption, state)
                    result = Runner.run_sync(triage_agent, state)
            except (BackendError, AgentsException, OpenAIError, ValueError) as exc:
                write_output(f"Request failed: {exc}")
                continue
            write_output(str(result.final_output))
    finally:
        client.set_beneficiary_details_handler(None)
        client.set_account_type_handler(None)
        client.set_ticket_details_handler(None)
        client.set_ticket_id_handler(None)
        client.clear_approved_payments()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Chat with the BankAI banking agent"
    )
    parser.add_argument(
        "--backend-url",
        help="FastAPI base URL (defaults to BANKING_BACKEND_URL or localhost:8000)",
    )
    parser.add_argument(
        "--model",
        help="Gemini model (defaults to GEMINI_MODEL or gemini-3.8-flash)",
    )
    args = parser.parse_args(argv)

    gemini_client: Any = None
    try:
        load_agent_environment()
        settings = get_settings()
        model, gemini_client = create_gemini_model(args.model)
        agent = create_triage_agent(model=model)
        with BackendClient(
            base_url=args.backend_url or settings.backend_url,
            timeout=settings.backend_timeout_seconds,
        ) as client:
            return run_cli(client, agent=agent)
    except (BackendError, AgentsException, OpenAIError, ValueError) as exc:
        print(f"Configuration or backend error: {exc}", file=sys.stderr)
        return 1
    finally:
        if gemini_client is not None:
            asyncio.run(gemini_client.close())


if __name__ == "__main__":
    raise SystemExit(main())
