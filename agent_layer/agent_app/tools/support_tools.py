from agents import RunContextWrapper, function_tool

from agent_app.backend_client.client import BackendClient
from agent_app.backend_client.tickets import create_ticket as post_ticket
from agent_app.backend_client.tickets import get_ticket as fetch_ticket


_TICKET_FIELD_LIMITS = {
    "title": 50,
    "description": 250,
    "category": 50,
    "priority": 50,
}


def create_support_ticket(
    client: BackendClient,
    title: str | None = None,
    description: str | None = None,
    category: str | None = None,
    priority: str | None = None,
) -> dict[str, object]:
    details = {
        "title": title,
        "description": description,
        "category": category,
        "priority": priority,
    }
    for field, value in details.items():
        if value is not None and not isinstance(value, str):
            raise ValueError(f"Ticket {field} must be text")
        if isinstance(value, str):
            details[field] = value.strip()

    missing_fields = {
        field
        for field, value in details.items()
        if not isinstance(value, str) or not value
    }
    if missing_fields:
        collected_details = client.request_ticket_details(missing_fields)
        if not isinstance(collected_details, dict):
            raise ValueError("Ticket details input returned an invalid response")
        for field in missing_fields:
            value = collected_details.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Ticket {field} is required")
            details[field] = value.strip()

    ticket_data = {
        field: value
        for field, value in details.items()
        if isinstance(value, str)
    }
    for field, max_length in _TICKET_FIELD_LIMITS.items():
        if len(ticket_data[field]) > max_length:
            raise ValueError(
                f"Ticket {field} must be at most {max_length} characters"
            )

    response = post_ticket(client, ticket_data)
    return _validated_ticket(response)


def get_support_ticket(
    client: BackendClient,
    ticket_id: int | None = None,
) -> dict[str, object]:
    if ticket_id is None:
        ticket_id = client.request_ticket_id()
    if isinstance(ticket_id, bool) or not isinstance(ticket_id, int) or ticket_id <= 0:
        raise ValueError("Ticket ID must be a positive integer")
    return _validated_ticket(fetch_ticket(client, ticket_id))


def _validated_ticket(response: object) -> dict[str, object]:
    if not isinstance(response, dict):
        raise ValueError("Backend returned an invalid support ticket response")
    ticket_id = response.get("id")
    if isinstance(ticket_id, bool) or not isinstance(ticket_id, int):
        raise ValueError("Backend returned an invalid support ticket ID")
    if any(
        not isinstance(response.get(field), str)
        for field in (
            "title",
            "description",
            "category",
            "priority",
            "status",
            "created_at",
        )
    ):
        raise ValueError("Backend returned incomplete support ticket details")
    return {
        "id": ticket_id,
        "title": response["title"],
        "description": response["description"],
        "category": response["category"],
        "priority": response["priority"],
        "status": response["status"],
        "created_at": response["created_at"],
    }


@function_tool(failure_error_function=None)
def create_ticket(
    context: RunContextWrapper[BackendClient],
    title: str | None = None,
    description: str | None = None,
    category: str | None = None,
    priority: str | None = None,
) -> dict[str, object]:
    """Create a support ticket, prompting the user for any missing required details."""
    return create_support_ticket(
        context.context,
        title,
        description,
        category,
        priority,
    )


@function_tool(failure_error_function=None)
def get_ticket(
    context: RunContextWrapper[BackendClient],
    ticket_id: int | None = None,
) -> dict[str, object]:
    """Fetch one of the authenticated user's support tickets by ID."""
    return get_support_ticket(context.context, ticket_id)
