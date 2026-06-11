"""Tests for telegram_react_tool."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestCallSetReaction:
    def _make_mock_session(self, response_json: dict):
        mock_resp = MagicMock()
        mock_resp.json = AsyncMock(return_value=response_json)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post.return_value = mock_resp
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        return mock_session

    def test_success_response(self):
        from tools.telegram_react_tool import _call_set_reaction

        mock_session = self._make_mock_session({"ok": True})
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = _run(_call_set_reaction("TOKEN", "123", "42", "👍"))

        assert result == {"success": True, "emoji": "👍", "chat_id": "123", "message_id": "42"}

    def test_api_error_propagated(self):
        from tools.telegram_react_tool import _call_set_reaction

        mock_session = self._make_mock_session({"ok": False, "description": "REACTION_INVALID"})
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = _run(_call_set_reaction("TOKEN", "123", "42", "🦑"))

        assert "error" in result
        assert "REACTION_INVALID" in result["error"]

    def test_network_exception(self):
        from tools.telegram_react_tool import _call_set_reaction

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(side_effect=ConnectionError("timeout"))
        mock_session.__aexit__ = AsyncMock(return_value=False)
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = _run(_call_set_reaction("TOKEN", "123", "42", "👍"))

        assert "error" in result


class TestTelegramReactTool:
    def test_missing_emoji_returns_error(self):
        from tools.telegram_react_tool import telegram_react_tool

        result = json.loads(telegram_react_tool({}))
        assert result == {"error": "emoji is required"}

    def test_blank_emoji_returns_error(self):
        from tools.telegram_react_tool import telegram_react_tool

        result = json.loads(telegram_react_tool({"emoji": "   "}))
        assert result == {"error": "emoji is required"}

    def test_no_token_returns_error(self):
        with patch("tools.telegram_react_tool._get_telegram_token", return_value=None):
            from tools.telegram_react_tool import telegram_react_tool
            result = json.loads(telegram_react_tool({"emoji": "👍", "chat_id": "1", "message_id": "2"}))
        assert "configured" in result["error"]

    def test_no_chat_id_returns_error(self):
        with (
            patch("tools.telegram_react_tool._get_telegram_token", return_value="tok"),
            patch("tools.telegram_react_tool._get_current_context", return_value=(None, None)),
        ):
            from tools.telegram_react_tool import telegram_react_tool
            result = json.loads(telegram_react_tool({"emoji": "👍"}))
        assert "chat_id" in result["error"]

    def test_no_message_id_returns_error(self):
        with (
            patch("tools.telegram_react_tool._get_telegram_token", return_value="tok"),
            patch("tools.telegram_react_tool._get_current_context", return_value=("123", None)),
        ):
            from tools.telegram_react_tool import telegram_react_tool
            result = json.loads(telegram_react_tool({"emoji": "👍"}))
        assert "message_id" in result["error"]

    def test_uses_session_context_when_args_omitted(self):
        mock_react = AsyncMock(return_value={"success": True, "emoji": "🔥"})
        with (
            patch("tools.telegram_react_tool._get_telegram_token", return_value="tok"),
            patch("tools.telegram_react_tool._get_current_context", return_value=("456", "99")) as ctx_mock,
            patch("tools.telegram_react_tool._call_set_reaction", mock_react),
        ):
            from tools.telegram_react_tool import telegram_react_tool
            result = json.loads(telegram_react_tool({"emoji": "🔥"}))

        ctx_mock.assert_called_once()
        assert result["success"] is True

    def test_runs_in_worker_thread_without_event_loop(self):
        # Gateway tool handlers run in worker threads (e.g. 'asyncio_1')
        # that have no event loop; asyncio.get_event_loop() raises there.
        import threading

        mock_react = AsyncMock(return_value={"success": True, "emoji": "❤"})
        results = {}

        def worker():
            with (
                patch("tools.telegram_react_tool._get_telegram_token", return_value="tok"),
                patch("tools.telegram_react_tool._call_set_reaction", mock_react),
            ):
                from tools.telegram_react_tool import telegram_react_tool
                results["r"] = json.loads(
                    telegram_react_tool({"emoji": "❤", "chat_id": "1", "message_id": "7"})
                )

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        assert results["r"].get("success") is True, results["r"]

    def test_explicit_args_skip_context_lookup(self):
        mock_react = AsyncMock(return_value={"success": True, "emoji": "❤", "chat_id": "999", "message_id": "7"})
        with (
            patch("tools.telegram_react_tool._get_telegram_token", return_value="tok"),
            patch("tools.telegram_react_tool._get_current_context") as ctx_mock,
            patch("tools.telegram_react_tool._call_set_reaction", mock_react),
        ):
            from tools.telegram_react_tool import telegram_react_tool
            result = json.loads(telegram_react_tool({"emoji": "❤", "chat_id": "999", "message_id": "7"}))

        ctx_mock.assert_not_called()
        assert result["chat_id"] == "999"


class TestGetTelegramToken:
    def test_reads_token_from_dict_shaped_platforms(self):
        from gateway.config import GatewayConfig, Platform, PlatformConfig
        from tools.telegram_react_tool import _get_telegram_token

        cfg = GatewayConfig()
        cfg.platforms[Platform.TELEGRAM] = PlatformConfig(enabled=True, token="123:abc")
        with patch("gateway.config.load_gateway_config", return_value=cfg):
            assert _get_telegram_token() == "123:abc"

    def test_returns_none_when_telegram_absent(self):
        from gateway.config import GatewayConfig
        from tools.telegram_react_tool import _get_telegram_token

        with patch("gateway.config.load_gateway_config", return_value=GatewayConfig()):
            assert _get_telegram_token() is None


class TestRegistration:
    def test_tool_registered_in_messaging_toolset(self):
        import tools.telegram_react_tool  # noqa: F401
        from tools.registry import registry

        tool = registry.get_entry("telegram_react")
        assert tool is not None
        assert tool.toolset == "messaging"

    def test_schema_requires_only_emoji(self):
        import tools.telegram_react_tool  # noqa: F401
        from tools.registry import registry

        schema = registry.get_entry("telegram_react").schema
        assert schema["parameters"]["required"] == ["emoji"]
        assert "chat_id" in schema["parameters"]["properties"]
        assert "message_id" in schema["parameters"]["properties"]
        description = schema["description"].lower()
        assert "спасибо" in description
        assert "short acknowledgement" in description
        assert "no text" in description
