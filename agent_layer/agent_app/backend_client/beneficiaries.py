from typing import Any

from .client import BackendClient


def get_beneficiaries(client: BackendClient) -> Any:
    return client.request(
        "GET",
        "/beneficiaries",
        authenticated=True,
    )


def create_beneficiary(
    client: BackendClient,
    beneficiary: dict[str, str],
) -> Any:
    return client.request(
        "POST",
        "/beneficiaries",
        json=beneficiary,
        authenticated=True
    )