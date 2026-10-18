from typing import Any

from .client import BackendClient


def create_ticket(client: BackendClient, ticket: dict[str, Any]) -> Any:
    return client.request(
        "POST",
        "/ticket",
        json=ticket,
        authenticated=True,
    )


def get_ticket(client: BackendClient, ticket_id: int) -> Any:
    return client.request(
        "GET",
        f"/ticket/{ticket_id}",
        authenticated=True,
    )