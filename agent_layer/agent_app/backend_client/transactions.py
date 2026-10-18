from typing import Any

from .client import BackendClient


def get_transactions(client: BackendClient, limit: int = 5) -> Any:
    return client.request(
        "GET",
        "/transactions",
        params={"limit": limit},
        authenticated=True,
    )


def create_transaction(
    client: BackendClient,
    transaction: dict[str, Any],
) -> Any:
    return client.request(
        "POST",
        "/transactions",
        json=transaction,
        authenticated=True,
    )

def payment_request(
    client: BackendClient,
    payment: dict[str, int | float],
) -> Any:
    return client.request(
        "POST",
        "/payment-requests",
        json=payment,
        authenticated=True,
    )