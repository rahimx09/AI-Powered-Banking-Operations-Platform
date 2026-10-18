import json
import unittest
from urllib.parse import parse_qs

import httpx

from agent_app.backend_client.client import (
    AuthenticationError,
    BackendAPIError,
    BackendClient,
    BackendConnectionError,
)
from agent_app.cli.chat import run_cli


class BackendClientTests(unittest.TestCase):
    def test_rejects_invalid_backend_urls(self) -> None:
        for url in ("", "backend.test", "ftp://backend.test", "http://backend.test?x=1"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                BackendClient(url)

    def test_login_uses_form_auth_and_protects_me_with_runtime_token(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path == "/login":
                self.assertEqual(request.method, "POST")
                self.assertEqual(
                    parse_qs(request.content.decode()),
                    {"username": ["user@example.com"], "password": ["secret"]},
                )
                return httpx.Response(
                    200,
                    json={"access_token": "test-token", "token_type": "bearer"},
                )

            self.assertEqual(request.url.path, "/me")
            self.assertEqual(
                request.headers["Authorization"],
                "Bearer test-token",
            )
            return httpx.Response(200, json={"id": 7, "name": "Test User"})

        http_client = httpx.Client(transport=httpx.MockTransport(handler))
        client = BackendClient("http://backend.test", http_client=http_client)
        client.login("user@example.com", "secret")

        self.assertEqual(
            client.get_current_user(),
            {"id": 7, "name": "Test User"},
        )
        self.assertEqual([request.url.path for request in requests], ["/login", "/me"])
        http_client.close()

    def test_unauthorized_response_clears_token(self) -> None:
        call_count = 0

        def handler(_: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json={"access_token": "test-token"})
            return httpx.Response(401, json={"detail": "Invalid or expired token"})

        http_client = httpx.Client(transport=httpx.MockTransport(handler))
        client = BackendClient("http://backend.test", http_client=http_client)
        client.login("user@example.com", "secret")
        with self.assertRaises(AuthenticationError):
            client.get_current_user()
        with self.assertRaisesRegex(AuthenticationError, "Log in before"):
            client.get_current_user()
        self.assertEqual(call_count, 2)
        http_client.close()

    def test_http_errors_and_timeouts_are_reported(self) -> None:
        http_client = httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(503, json={"detail": "Unavailable"})
            )
        )
        client = BackendClient("http://backend.test", http_client=http_client)
        with self.assertRaises(BackendAPIError) as error:
            client.health_check()
        self.assertEqual(error.exception.status_code, 503)
        self.assertIn("Unavailable", str(error.exception))
        http_client.close()

        def timeout(_: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out")

        http_client = httpx.Client(transport=httpx.MockTransport(timeout))
        client = BackendClient("http://backend.test", http_client=http_client)
        with self.assertRaises(BackendConnectionError) as error:
            client.health_check()
        self.assertIn("timed out", str(error.exception))
        http_client.close()


class CliTests(unittest.TestCase):
    def test_backend_check_authenticates_and_does_not_print_credentials(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/health":
                return httpx.Response(200, json={"status": "ok"})
            if request.url.path == "/login":
                self.assertEqual(
                    parse_qs(request.content.decode()),
                    {"username": ["user@example.com"], "password": ["secret"]},
                )
                return httpx.Response(
                    200,
                    json={"access_token": "runtime-only-token"},
                )
            if request.url.path == "/me":
                self.assertEqual(
                    request.headers["Authorization"],
                    "Bearer runtime-only-token",
                )
                return httpx.Response(
                    200,
                    json={"id": 7, "name": "Test User", "email": "user@example.com"},
                )
            self.fail(f"Unexpected request: {request.url}")
            return httpx.Response(500)

        http_client = httpx.Client(transport=httpx.MockTransport(handler))
        client = BackendClient("http://backend.test", http_client=http_client)
        output: list[str] = []
        result = run_cli(
            client,
            check_backend=True,
            input_fn=lambda _: "user@example.com",
            password_fn=lambda _: "secret",
            output_fn=output.append,
        )

        self.assertEqual(result, 0)
        self.assertEqual(output, ["Connected to BankAI backend as Test User."])
        self.assertNotIn("secret", json.dumps(output))
        self.assertNotIn("runtime-only-token", json.dumps(output))
        http_client.close()

    def test_interactive_loop_supports_exit_without_sending_message(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            if request.url.path == "/health":
                return httpx.Response(200, json={"status": "ok"})
            if request.url.path == "/login":
                return httpx.Response(200, json={"access_token": "runtime-token"})
            if request.url.path == "/me":
                return httpx.Response(200, json={"name": "Test User"})
            self.fail(f"Unexpected request: {request.url}")
            return httpx.Response(500)

        http_client = httpx.Client(transport=httpx.MockTransport(handler))
        client = BackendClient("http://backend.test", http_client=http_client)
        messages = iter(("user@example.com", "exit"))
        output: list[str] = []
        result = run_cli(
            client,
            input_fn=lambda _: next(messages),
            password_fn=lambda _: "secret",
            output_fn=output.append,
        )

        self.assertEqual(result, 0)
        self.assertEqual([request.url.path for request in requests], ["/health", "/login", "/me"])
        self.assertEqual(output[-1], "Goodbye.")
        http_client.close()

    def test_interactive_cli_exposes_every_mounted_backend_route(self) -> None:
        requests: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append((request.method, request.url.path))
            if request.url.path == "/health":
                return httpx.Response(200, json={"status": "ok"})
            if request.url.path == "/login":
                return httpx.Response(200, json={"access_token": "cli-token"})
            if request.url.path == "/me":
                return httpx.Response(200, json={"name": "Test User"})
            return httpx.Response(200, json={"ok": True})

        http_client = httpx.Client(transport=httpx.MockTransport(handler))
        client = BackendClient("http://backend.test", http_client=http_client)
        answers = iter(
            (
                "user@example.com",
                "1",
                "2", "savings",
                "3",
                "4", "5",
                "5", "25.00", "credit", "test deposit",
                "6", "Question", "Please help", "support", "normal",
                "7", "1",
                "8",
                "9", "Alex Smith",
                "10", "Alex Smith", "123456", "Example Bank",
                "11", "1", "5.00", "yes",
                "12", "New User", "new@example.com",
                "13", "2",
                "14", "new@example.com",
                "15",
                "exit",
            )
        )
        output: list[str] = []

        result = run_cli(
            client,
            input_fn=lambda _: next(answers),
            password_fn=lambda _: "secret",
            output_fn=output.append,
        )

        self.assertEqual(result, 0)
        self.assertEqual(
            requests,
            [
                ("GET", "/health"),
                ("POST", "/login"),
                ("GET", "/me"),
                ("GET", "/accounts"),
                ("POST", "/accounts"),
                ("GET", "/account_balance"),
                ("GET", "/transactions"),
                ("POST", "/transactions"),
                ("POST", "/ticket"),
                ("GET", "/ticket/1"),
                ("GET", "/beneficiaries"),
                ("GET", "/beneficiaries/Alex Smith"),
                ("POST", "/beneficiaries"),
                ("POST", "/payment-requests"),
                ("POST", "/create_user"),
                ("GET", "/create_user/2"),
                ("GET", "/create_user/email/new@example.com"),
                ("GET", "/me"),
            ],
        )
        http_client.close()


if __name__ == "__main__":
    unittest.main()
