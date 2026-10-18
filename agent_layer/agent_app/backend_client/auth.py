from typing import Any

from .client import BackendClient


def login(client: BackendClient, email: str, password: str) -> None:
    """Authenticate and retain the returned token inside this client instance."""
    client.login(email, password)


def get_current_user(client: BackendClient) -> Any:
    return client.get_current_user()