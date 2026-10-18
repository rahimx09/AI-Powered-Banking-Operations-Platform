import argparse
import getpass
import json
import sys
from collections.abc import Callable, Sequence
from typing import Any
from urllib.parse import quote

from agent_app.backend_client.client import BackendClient, BackendError
from agent_app.settings import get_settings


MENU = """\
Banking actions:
  1  List accounts             2  Open an account
  3  Show account balance      4  List transactions
  5  Create a transaction      6  Create a support ticket
  7  Get a support ticket      8  List beneficiaries
  9  Find beneficiaries by name
  10 Add a beneficiary         11 Make a payment
  12 Create a user             13 Find a user by ID
  14 Find a user by email      15 Show my profile
Type help to show this menu again, or exit to quit.
"""


def _required_input(
    prompt: str,
    read_input: Callable[[str], str],
    write_output: Callable[[str], Any],
) -> str:
    while True:
        value = read_input(prompt).strip()
        if value:
            return value
        write_output("This value is required.")


def _positive_integer(
    prompt: str,
    read_input: Callable[[str], str],
    write_output: Callable[[str], Any],
) -> int:
    while True:
        value = read_input(prompt).strip()
        try:
            number = int(value)
        except ValueError:
            write_output("Enter a whole number greater than zero.")
            continue
        if number > 0:
            return number
        write_output("Enter a whole number greater than zero.")


def _show_result(
    label: str,
    result: Any,
    write_output: Callable[[str], Any],
) -> None:
    write_output(label)
    write_output(json.dumps(result, indent=2, default=str))


def _run_action(
    client: BackendClient,
    action: str,
    read_input: Callable[[str], str],
    read_password: Callable[[str], str],
    write_output: Callable[[str], Any],
) -> None:
    required = lambda prompt: _required_input(prompt, read_input, write_output)
    positive_integer = lambda prompt: _positive_integer(
        prompt, read_input, write_output
    )

    if action == "1":
        result = client.request("GET", "/accounts", authenticated=True)
        label = "Accounts:"
    elif action == "2":
        result = client.request(
            "POST",
            "/accounts",
            json={"account_type": required("Account type: ")},
            authenticated=True,
        )
        label = "Account created:"
    elif action == "3":
        result = client.request("GET", "/account_balance", authenticated=True)
        label = "Account balance:"
    elif action == "4":
        limit = positive_integer("Maximum transactions (1-100): ")
        if limit > 100:
            raise ValueError("Transaction limit must be between 1 and 100.")
        result = client.request(
            "GET",
            "/transactions",
            params={"limit": limit},
            authenticated=True,
        )
        label = "Transactions:"
    elif action == "5":
        amount = required("Amount: ")
        transaction_type = required("Type (credit/debit): ").lower()
        if transaction_type not in {"credit", "debit"}:
            raise ValueError("Transaction type must be credit or debit.")
        description = read_input("Description (optional): ").strip() or None
        result = client.request(
            "POST",
            "/transactions",
            json={
                "amount": amount,
                "type": transaction_type,
                "description": description,
            },
            authenticated=True,
        )
        label = "Transaction created:"
    elif action == "6":
        result = client.request(
            "POST",
            "/ticket",
            json={
                "title": required("Title: "),
                "description": required("Description: "),
                "category": required("Category: "),
                "priority": required("Priority: "),
            },
            authenticated=True,
        )
        label = "Support ticket created:"
    elif action == "7":
        ticket_id = positive_integer("Ticket ID: ")
        result = client.request(
            "GET", f"/ticket/{ticket_id}", authenticated=True
        )
        label = "Support ticket:"
    elif action == "8":
        result = client.request("GET", "/beneficiaries", authenticated=True)
        label = "Beneficiaries:"
    elif action == "9":
        name = quote(required("Beneficiary name: "), safe="")
        result = client.request(
            "GET", f"/beneficiaries/{name}", authenticated=True
        )
        label = "Matching beneficiaries:"
    elif action == "10":
        result = client.request(
            "POST",
            "/beneficiaries",
            json={
                "name": required("Name: "),
                "account_number": required("Account number: "),
                "bank_name": required("Bank name: "),
            },
            authenticated=True,
        )
        label = "Beneficiary added:"
    elif action == "11":
        beneficiary_id = positive_integer("Beneficiary ID: ")
        amount = required("Amount: ")
        confirmation = read_input(
            "Submit this payment? This will debit your account (yes/no): "
        ).strip().lower()
        if confirmation not in {"yes", "y"}:
            write_output("Payment cancelled.")
            return
        result = client.request(
            "POST",
            "/payment-requests",
            json={"beneficiary_id": beneficiary_id, "amount": amount},
            authenticated=True,
        )
        label = "Payment completed:"
    elif action == "12":
        name = required("Name: ")
        email = required("Email: ")
        password = read_password("Password: ")
        if not password:
            raise ValueError("Password is required.")
        result = client.request(
            "POST",
            "/create_user",
            json={
                "name": name,
                "email": email,
                "password": password,
            },
        )
        label = "User created:"
    elif action == "13":
        user_id = positive_integer("User ID: ")
        result = client.request(
            "GET", f"/create_user/{user_id}", authenticated=True
        )
        label = "User:"
    elif action == "14":
        email = quote(required("Email: "), safe="")
        result = client.request(
            "GET", f"/create_user/email/{email}", authenticated=True
        )
        label = "User:"
    elif action == "15":
        result = client.get_current_user()
        label = "Your profile:"
    else:
        raise ValueError("Unknown action. Enter help to see available actions.")

    _show_result(label, result, write_output)


def run_cli(
    client: BackendClient,
    *,
    check_backend: bool = False,
    input_fn: Callable[[str], str] | None = None,
    password_fn: Callable[[str], str] | None = None,
    output_fn: Callable[[str], Any] | None = None,
) -> int:
    read_input = input_fn or input
    read_password = password_fn or getpass.getpass
    write_output = output_fn or print

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

    name = user.get("name")
    write_output(f"Connected to BankAI backend as {name or email}.")
    if check_backend:
        return 0

    write_output(MENU)
    while True:
        try:
            action = read_input("bankai> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            write_output("\nGoodbye.")
            return 0
        if action in {"exit", "quit"}:
            write_output("Goodbye.")
            return 0
        if not action:
            continue
        if action in {"help", "menu"}:
            write_output(MENU)
            continue
        try:
            _run_action(
                client,
                action,
                read_input,
                read_password,
                write_output,
            )
        except (EOFError, KeyboardInterrupt):
            write_output("\nAction cancelled.")
        except (BackendError, ValueError) as exc:
            write_output(f"Request failed: {exc}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Interactive command-line client for the BankAI backend"
    )
    parser.add_argument(
        "--backend-url",
        help="FastAPI base URL (defaults to BANKING_BACKEND_URL or localhost:8000)",
    )
    parser.add_argument(
        "--check-backend",
        action="store_true",
        help="log in, verify the authenticated backend connection, and exit",
    )
    args = parser.parse_args(argv)

    try:
        settings = get_settings()
        with BackendClient(
            base_url=args.backend_url or settings.backend_url,
            timeout=settings.backend_timeout_seconds,
        ) as client:
            return run_cli(client, check_backend=args.check_backend)
    except (BackendError, ValueError) as exc:
        print(f"Configuration or backend error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
