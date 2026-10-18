import unittest
from unittest.mock import patch

from agent_app.llm_config import GEMINI_BASE_URL, create_gemini_model


class LlmConfigTests(unittest.TestCase):
    def test_gemini_model_and_openai_tracing_use_separate_keys(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {
                    "GEMINI_API_KEY": "gemini-test-key",
                    "OPENAI_API_KEY": "openai-tracing-test-key",
                    "GEMINI_MODEL": "gemini-env-model",
                    "AGENT_TRACING_ENABLED": "true",
                },
                clear=True,
            ),
            patch("agent_app.llm_config.load_dotenv"),
            patch(
                "agent_app.llm_config.dotenv_values",
                return_value={
                    "GEMINI_API_KEY": "gemini-test-key",
                    "OPENAI_API_KEY": "openai-tracing-test-key",
                    "GEMINI_MODEL": "gemini-env-model",
                    "AGENT_TRACING_ENABLED": "true",
                },
            ),
            patch("agent_app.llm_config.AsyncOpenAI") as openai_client,
            patch("agent_app.llm_config.set_tracing_export_api_key") as set_trace_key,
            patch("agent_app.llm_config.set_tracing_disabled") as disable_tracing,
        ):
            fake_client = openai_client.return_value
            with patch(
                "agent_app.llm_config.OpenAIChatCompletionsModel",
                return_value="configured-model",
            ) as model_class:
                model, client = create_gemini_model()

        self.assertEqual(model, "configured-model")
        self.assertIs(client, fake_client)
        openai_client.assert_called_once_with(
            api_key="gemini-test-key",
            base_url=GEMINI_BASE_URL,
        )
        set_trace_key.assert_called_once_with("openai-tracing-test-key")
        disable_tracing.assert_called_once_with(False)
        model_class.assert_called_once_with(
            model="gemini-env-model",
            openai_client=fake_client,
        )

    def test_cli_model_override_is_used_for_gemini(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {
                    "GEMINI_API_KEY": "gemini-test-key",
                    "OPENAI_API_KEY": "openai-tracing-test-key",
                    "GEMINI_MODEL": "gemini-env-model",
                },
                clear=True,
            ),
            patch("agent_app.llm_config.load_dotenv"),
            patch(
                "agent_app.llm_config.dotenv_values",
                return_value={
                    "GEMINI_API_KEY": "gemini-test-key",
                    "OPENAI_API_KEY": "openai-tracing-test-key",
                    "GEMINI_MODEL": "gemini-env-model",
                },
            ),
            patch("agent_app.llm_config.AsyncOpenAI"),
            patch("agent_app.llm_config.set_tracing_export_api_key"),
            patch(
                "agent_app.llm_config.OpenAIChatCompletionsModel",
                return_value="configured-model",
            ) as model_class,
        ):
            model, _ = create_gemini_model("gemini-cli-model")

        self.assertEqual(model, "configured-model")
        self.assertEqual(
            model_class.call_args.kwargs["model"],
            "gemini-cli-model",
        )

    def test_tracing_is_disabled_by_default_and_only_gemini_key_is_required(self) -> None:
        with (
            patch.dict("os.environ", {"GEMINI_API_KEY": "gemini-test-key"}, clear=True),
            patch("agent_app.llm_config.load_dotenv"),
            patch("agent_app.llm_config.dotenv_values", return_value={}),
            patch("agent_app.llm_config.AsyncOpenAI"),
            patch("agent_app.llm_config.OpenAIChatCompletionsModel"),
            patch("agent_app.llm_config.set_tracing_export_api_key") as set_trace_key,
            patch("agent_app.llm_config.set_tracing_disabled") as disable_tracing,
        ):
            create_gemini_model()

        set_trace_key.assert_not_called()
        disable_tracing.assert_called_once_with(True)

    def test_tracing_requires_openai_key_when_enabled(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {"GEMINI_API_KEY": "gemini-test-key", "AGENT_TRACING_ENABLED": "true"},
                clear=True,
            ),
            patch("agent_app.llm_config.load_dotenv"),
            patch("agent_app.llm_config.dotenv_values", return_value={}),
            self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"),
        ):
            create_gemini_model()

    def test_rejects_invalid_tracing_setting(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {"GEMINI_API_KEY": "gemini-test-key", "AGENT_TRACING_ENABLED": "yes"},
                clear=True,
            ),
            patch("agent_app.llm_config.load_dotenv"),
            patch("agent_app.llm_config.dotenv_values", return_value={}),
            self.assertRaisesRegex(ValueError, "AGENT_TRACING_ENABLED"),
        ):
            create_gemini_model()

    def test_env_file_gemini_key_takes_precedence_over_process_environment(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {
                    "GEMINI_API_KEY": "stale-process-key",
                    "OPENAI_API_KEY": "process-trace-key",
                },
                clear=True,
            ),
            patch("agent_app.llm_config.load_dotenv"),
            patch(
                "agent_app.llm_config.dotenv_values",
                return_value={
                    "GEMINI_API_KEY": "env-file-gemini-key",
                    "OPENAI_API_KEY": "env-file-trace-key",
                },
            ),
            patch("agent_app.llm_config.AsyncOpenAI") as openai_client,
            patch("agent_app.llm_config.set_tracing_export_api_key"),
            patch(
                "agent_app.llm_config.OpenAIChatCompletionsModel",
                return_value="configured-model",
            ),
        ):
            create_gemini_model()

        self.assertEqual(
            openai_client.call_args.kwargs["api_key"],
            "env-file-gemini-key",
        )


if __name__ == "__main__":
    unittest.main()
