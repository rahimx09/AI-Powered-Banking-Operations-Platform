from collections.abc import Callable
from decimal import Decimal
from typing import Any


import httpx


class BackendError(Exception):
    """Base exception for backend communication failures."""


class BackendConnectionError(BackendError):
    """The backend could not be reached or returned an unusable response."""


class BackendAPIError(BackendError):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Backend returned HTTP {status_code}: {detail}")


class AuthenticationError(BackendAPIError):
    """Authentication failed or the current access token is no longer valid."""


class BackendClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 10,
        http_client: httpx.Client | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("Backend base URL must not be empty")
        if timeout <= 0:
            raise ValueError("Backend timeout must be greater than zero")

        try:
            parsed_url = httpx.URL(base_url.strip())
        except httpx.InvalidURL as exc:
            raise ValueError("Backend base URL must be a valid HTTP(S) URL") from exc
        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.host
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ValueError(
                "Backend base URL must be an absolute HTTP(S) URL "
                "without a query or fragment"
            )

        self._base_url = str(parsed_url).rstrip("/")
        self._http_client = http_client or httpx.Client(timeout=timeout)
        self._owns_http_client = http_client is None
        self._access_token: str | None = None
        self._approved_payment_details: dict[
            tuple[int, Decimal], list[tuple[str, str, str]]
        ] = {}
        self._beneficiary_details_handler: (
            Callable[[set[str]], dict[str, str]] | None
        ) = None
        self._account_type_handler: Callable[[], str] | None = None
        self._ticket_details_handler: (
            Callable[[set[str]], dict[str, str]] | None
        ) = None
        self._ticket_id_handler: Callable[[], int] | None = None

    def __enter__(self) -> "BackendClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_http_client:
            self._http_client.close()

    def approve_payment(
        self,
        beneficiary_id: int,
        amount: Decimal,
        beneficiary_name: str,
        account_number: str,
        bank_name: str,
    ) -> None:
        key = (beneficiary_id, amount.quantize(Decimal("0.01")))
        self._approved_payment_details.setdefault(key, []).append(
            (beneficiary_name, account_number, bank_name)
        )
    
    def consume_approved_payment(
        self,
        beneficiary_id: int,
        amount: Decimal,
    ) -> tuple[str, str, str] | None:
        key = (beneficiary_id, amount.quantize(Decimal("0.01")))
        approved_details = self._approved_payment_details.get(key)
        if not approved_details:
            return None

        details = approved_details.pop(0)
        if not approved_details:
            del self._approved_payment_details[key]
        return details

    def clear_approved_payments(self) -> None:
        self._approved_payment_details.clear()

    def set_beneficiary_details_handler(
        self,
        handler: Callable[[set[str]], dict[str, str]] | None,
    ) -> None:
        self._beneficiary_details_handler = handler

    def request_beneficiary_details(
        self,
        missing_fields: set[str],
    ) -> dict[str, str]:
        if self._beneficiary_details_handler is None:
            raise ValueError(
                "Beneficary details are incomplete and interactive input is unavailable"
            )
        return self._beneficiary_details_handler(missing_fields)

    def set_account_type_handler(
        self,
        handler: Callable[[], str] | None,
    ) -> None:
        self._account_type_handler = handler

    def request_account_type(self) -> str:
        if self._account_type_handler is None:
            raise ValueError(
                "Account type is missing and interactive input is unavailable"
            )
        return self._account_type_handler()

    def set_ticket_details_handler(
        self,
        handler: Callable[[set[str]], dict[str, str]] | None,
    ) -> None:
        self._ticket_details_handler = handler

    def request_ticket_details(
        self,
        missing_fields: set[str],
    ) -> dict[str, str]:
        if self._ticket_details_handler is None:
            raise ValueError(
                "Ticket details are incomplete and interactive input is unavailable"
            )
        return self._ticket_details_handler(missing_fields)

    def set_ticket_id_handler(
        self,
        handler: Callable[[], int] | None,
    ) -> None:
        self._ticket_id_handler = handler

    def request_ticket_id(self) -> int:
        if self._ticket_id_handler is None:
            raise ValueError(
                "Ticket ID is missing and interactive input is unavailable"
            )
        return self._ticket_id_handler()

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        data: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        authenticated: bool = False,
    ) -> Any:
        headers: dict[str, str] = {}
        if authenticated:
            if self._access_token is None:
                raise AuthenticationError(401, "Log in before making this request")

            headers["Authorization"] = f"Bearer {self._access_token}"

        try:
            response = self._http_client.request(
                method,
                f"{self._base_url}/{path.lstrip('/')}",
                json=json,
                data=data,
                params=params,
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            raise BackendConnectionError("Backend request timed out") from exc
        except httpx.RequestError as exc:
            raise BackendConnectionError(
                f"Could not connect to backend at {self._base_url}"
            ) from exc

        if response.status_code == 401:
            self._access_token = None
            raise AuthenticationError(401, self._response_detail(response))
        if response.is_error:
            raise BackendAPIError(
                response.status_code,
                self._response_detail(response),
            )
        if not response.content:
            return None

        try:
            return response.json()
        except ValueError as exc:
            raise BackendConnectionError(
                "Backend returned a response that was not valid JSON"
            ) from exc

    @staticmethod
    def _response_detail(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            text = response.text.strip()
            return text or response.reason_phrase

        if isinstance(payload, dict) and "detail" in payload:
            return str(payload["detail"])
        return str(payload)

    def health_check(self) -> Any:
        return self.request("GET", "/health")

    def login(self, email: str, password: str) -> None:
        self._access_token = None
        response = self.request(
            "POST",
            "/login",
            data={"username": email, "password": password},
        )
        if not isinstance(response, dict):
            raise BackendConnectionError("Backend returned an invalid login response")

        token = response.get("access_token")
        token_type = response.get("token_type", "bearer")
        if not isinstance(token, str) or not token.strip():
            raise BackendConnectionError("Backend login response did not include a token")
        if not isinstance(token_type, str) or token_type.lower() != "bearer":
            raise BackendConnectionError("Backend returned an unsupported token type")
        self._access_token = token

    def get_current_user(self) -> Any:
        return self.request("GET", "/me", authenticated=True)