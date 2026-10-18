from typing import Any

from .client import BackendClient


def get_accounts(client: BackendClient) -> Any:
    return client.request("GET", "/accounts", authenticated=True)


def get_balance(client: BackendClient) -> Any:
    return client.request("GET", "/account_balance", authenticated=True)


def create_account(client: BackendClient, account_type: str) -> Any:
    return client.request(
        "POST",
        "/accounts",
        json={"account_type": account_type},
        authenticated=True,
    )