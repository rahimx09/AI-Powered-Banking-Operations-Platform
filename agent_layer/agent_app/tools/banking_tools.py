import math
from decimal import Decimal, InvalidOperation

from agents import RunContextWrapper, function_tool
from agent_app.backend_client.accounts import (
    create_account as post_account,
    get_accounts,
    get_balance,
)
from agent_app.backend_client.beneficiaries import (
    create_beneficiary as post_beneficiary,
    get_beneficiaries,
)
from agent_app.backend_client.client import BackendAPIError, BackendClient
from agent_app.backend_client.transactions import get_transactions, payment_request


def create_new_account(
    client: BackendClient,
    account_type: str | None = None,
) -> dict[str, object]:
    try:
        existing_accounts = get_accounts(client)
    except BackendAPIError as exc:
        if exc.status_code != 404:
            raise
        existing_accounts = []

    if not isinstance(existing_accounts, list):
        raise ValueError("Backend returned an invalid account list")
    if existing_accounts:
        raise ValueError("User already has an account")

    if account_type is not None and not isinstance(account_type, str):
        raise ValueError("Account type must be text")
    if account_type is None or not account_type.strip():
        account_type = client.request_account_type()
    if not isinstance(account_type, str) or not account_type.strip():
        raise ValueError("Account type is required")

    try:
        response = post_account(client, account_type.strip())
    except BackendAPIError as exc:
        if exc.status_code == 409:
            raise ValueError("User already has an account") from exc
        raise
    if (
        not isinstance(response, dict)
        or not isinstance(response.get("account_number"), str)
        or not isinstance(response.get("account_type"), str)
        or isinstance(response.get("balance"), bool)
        or not isinstance(response.get("balance"), (int, float))
        or not isinstance(response.get("status"), str)
    ):
        raise ValueError("Backend returned an invalid created account response")
    return {
        "account_number": response["account_number"],
        "account_type": response["account_type"],
        "balance": float(response["balance"]),
        "status": response["status"],
    }


@function_tool(failure_error_function=None)
def create_bank_account(
    context: RunContextWrapper[BackendClient],
    account_type: str | None = None,
) -> dict[str, object]:
    """Create an account if the user has none; collect the missing account type."""
    return create_new_account(context.context, account_type)


def create_new_bene(
    client: BackendClient,
    name: str | None = None,
    account_number: str | None = None,
    bank_name: str | None = None,
) -> dict[str, int | str]:
    details = {
        "name": name,
        "account_number": account_number,
        "bank_name": bank_name,
    }
    for field, value in details.items():
        if value is not None and not isinstance(value, str):
            raise ValueError(f"Beneficiary {field.replace('_', ' ')} must be text")
        if isinstance(value, str):
            details[field] = value.strip()

    missing_fields = {
        field
        for field, value in details.items()
        if not isinstance(value, str) or not value
    }
    if missing_fields:
        collected_details = client.request_beneficiary_details(missing_fields)
        if not isinstance(collected_details, dict):
            raise ValueError("Beneficiary details input returned an invalid response")
        for field in missing_fields:
            value = collected_details.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"Beneficiary {field.replace('_', ' ')} is required"
                )
            details[field] = value.strip()

    complete_details = {
        field: value
        for field, value in details.items()
        if isinstance(value, str)
    }
    response = post_beneficiary(client, complete_details)
    if (
        not isinstance(response, dict)
        or isinstance(response.get("id"), bool)
        or not isinstance(response.get("id"), int)
        or any(
            not isinstance(response.get(field), str)
            for field in ("name", "account_number", "bank_name")
        )
    ):
        raise ValueError("Backend returned an invalid created beneficiary response")
    return {
        "id": response["id"],
        "name": response["name"],
        "account_number": response["account_number"],
        "bank_name": response["bank_name"],
    }

@function_tool(failure_error_function=None)
def create_beneficiary(
    context: RunContextWrapper[BackendClient],
    name: str | None = None,
    account_number: str | None = None,
    bank_name: str | None = None,
) -> dict[str, int | str]:
    """Create a beneficiary; ask the user interactively for any missing details."""
    return create_new_bene(context.context, name, account_number, bank_name)
    
def fetch_payment_details(
    client: BackendClient,
    beneficiary_id: int,
    amount: int | float,
) -> tuple[Decimal, str, str, str]:
    if (
        isinstance(beneficiary_id, bool)
        or not isinstance(beneficiary_id, int)
        or beneficiary_id <= 0
    ):
        raise ValueError("Beneficiary ID must be a positive integer")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise ValueError("Payment amount must be a positive number")
    try:
        decimal_amount = Decimal(str(amount))
    except InvalidOperation as exc:
        raise ValueError("Payment amount is invalid") from exc
    if not decimal_amount.is_finite() or decimal_amount <= 0:
        raise ValueError("Payment amount must be a positive finite number")
    if decimal_amount.as_tuple().exponent < -2 or decimal_amount.adjusted() >= 10:
        raise ValueError("Payment amount must have at most 10 whole digits and 2 decimals")

    beneficiary_list = fetch_current_user_beneficiaries(client)
    beneficiary = next(
        (
            item
            for item in beneficiary_list
            if item.get("id") == beneficiary_id
        ),
        None,
    )
    if beneficiary is None:
        raise ValueError("Beneficiary was not found for the authenticated user")

    beneficiary_name = beneficiary.get("name")
    account_number = beneficiary.get("account_number")
    bank_name = beneficiary.get("bank_name")
    if not all(
        isinstance(value, str) and value.strip()
        for value in (beneficiary_name, account_number, bank_name)
    ):
        raise ValueError("Backend returned incomplete beneficiary details")

    return decimal_amount, beneficiary_name, account_number, bank_name


def fetch_payment_request(
    client: BackendClient,
    beneficiary_id: int,
    amount: int | float,
) -> dict[str, object]:
    decimal_amount, beneficiary_name, account_number, bank_name = (
        fetch_payment_details(client, beneficiary_id, amount)
    )
    approved_details = client.consume_approved_payment(
        beneficiary_id,
        decimal_amount,
    )
    if approved_details is None:
        raise ValueError("Payment requires explicit human approval")
    if approved_details != (beneficiary_name, account_number, bank_name):
        raise ValueError(
            "Beneficiary details changed after approval; payment was not submitted"
        )

    response = payment_request(
        client,
        {
            "beneficiary_id": beneficiary_id,
            "amount": float(decimal_amount),
        },
    )
    if not isinstance(response, dict):
        raise ValueError("Backend returned an invalid payment response")

    transaction_id = response.get("transaction_id")
    response_amount = response.get("amount")
    response_name = response.get("beneficiary_name")
    response_account = response.get("beneficiary_account_number")
    response_bank = response.get("beneficiary_bank_name")
    timestamp = response.get("timestamp")
    status = response.get("status")
    remaining_balance = response.get("remaining_balance")
    if (
        isinstance(transaction_id, bool)
        or not isinstance(transaction_id, int)
        or isinstance(response_amount, bool)
        or not isinstance(response_amount, (int, float))
        or not math.isfinite(response_amount)
        or not isinstance(response_name, str)
        or not isinstance(response_account, str)
        or not isinstance(response_bank, str)
        or not isinstance(timestamp, str)
        or not isinstance(status, str)
        or status.lower() != "completed"
        or isinstance(remaining_balance, bool)
        or not isinstance(remaining_balance, (int, float))
        or not math.isfinite(remaining_balance)
    ):
        raise ValueError("Backend returned an invalid payment response")
    if (
        response_name != beneficiary_name
        or response_account != account_number
        or response_bank != bank_name
        or Decimal(str(response_amount)) != decimal_amount
    ):
        raise ValueError("Backend payment response does not match the confirmed payment")

    return {
        "transaction_id": transaction_id,
        "beneficiary_name": response_name,
        "beneficiary_account_number": response_account,
        "beneficiary_bank_name": response_bank,
        "timestamp": timestamp,
        "amount": response_amount,
        "status": status,
        "remaining_balance": remaining_balance,
    }


@function_tool(failure_error_function=None, needs_approval=True)
def make_payment_request(
    context: RunContextWrapper[BackendClient],
    beneficiary_id: int,
    amount: float,
) -> dict[str, object]:
    """Submit a payment approved by a human to one of the user's saved beneficiaries."""
    return fetch_payment_request(context.context, beneficiary_id, amount)


def fetch_current_user_beneficiaries(client: BackendClient) -> list[dict[str, object]]:
    response = get_beneficiaries(client)
    if not isinstance(response, list) or any(
        not isinstance(beneficiary, dict) for beneficiary in response
    ):
        raise ValueError("Backend returned an invalid beneficiaries response")
    return [
        beneficiary
        for beneficiary in response
        if isinstance(beneficiary, dict)
    ]


@function_tool(failure_error_function=None)
def check_current_user_beneficiaries(
    context: RunContextWrapper[BackendClient],
) -> list[dict[str, object]]:
    """Fetch the authenticated user's saved beneficiaries from the backend."""
    return fetch_current_user_beneficiaries(context.context)


def fetch_current_user_transactions(
    client: BackendClient,
    limit: int = 5,
) -> list[dict[str, object]]:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("Transaction limit must be an integer between 1 and 100")

    response = get_transactions(client, limit)
    if not isinstance(response, list) or any(
        not isinstance(transaction, dict) for transaction in response
    ):
        raise ValueError("Backend returned an invalid transaction response")
    return [transaction for transaction in response if isinstance(transaction, dict)]


@function_tool(failure_error_function=None)
def check_current_user_transaction(
    context: RunContextWrapper[BackendClient],
    limit: int = 5,
) -> list[dict[str, object]]:
    """Fetch the authenticated user's most recent transactions from the backend."""
    return fetch_current_user_transactions(context.context, limit)


def fetch_current_user_balance(client: BackendClient) -> float:
    response = get_balance(client)
    if not isinstance(response, dict):
        raise ValueError("Backend returned an invalid account balance response")

    balance = response.get("balance")
    if isinstance(balance, bool) or not isinstance(balance, (int, float)):
        raise ValueError("Backend returned an invalid account balance")
    return float(balance)


@function_tool(failure_error_function=None)
def check_current_user_balance(
    context: RunContextWrapper[BackendClient],
) -> float:
    """Fetch the authenticated user's current account balance from the backend."""
    return fetch_current_user_balance(context.context)


def fetch_current_user_account(client: BackendClient) -> dict[str, object]:
    response = get_accounts(client)
    if not isinstance(response, list):
        raise ValueError("Backend returned an invalid account details response")
    if not response:
        raise ValueError("Backend returned no account details")

    account = response[0]
    if not isinstance(account, dict):
        raise ValueError("Backend returned invalid account details")

    account_number = account.get("account_number")
    account_type = account.get("account_type")
    balance = account.get("balance")
    status = account.get("status")
    if (
        not isinstance(account_number, str)
        or not isinstance(account_type, str)
        or isinstance(balance, bool)
        or not isinstance(balance, (int, float))
        or not isinstance(status, str)
    ):
        raise ValueError("Backend returned invalid account details")

    return {
        "account_number": account_number,
        "account_type": account_type,
        "balance": float(balance),
        "status": status,
    }


@function_tool(failure_error_function=None)
def check_current_user_account(
    context: RunContextWrapper[BackendClient],
) -> dict[str, object]:
    """Fetch the authenticated user's account details from the backend."""
    return fetch_current_user_account(context.context)
