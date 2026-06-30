"""Tests for tools/telegram_react_tool.py."""

import asyncio
import json
import threading
from unittest.mock import AsyncMock, MagicMock, patch


def _run(coro):
    return asyncio.run(coro)


def _mock_session(response_json: dict):
    mock_resp = MagicMock()
    mock_resp.json = AsyncMock(return_value=response_json)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.post.return_value = mock_resp
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_session


def test_call_set_reaction_success():
    from tools.telegram_react_tool import _call_set_reaction

    session = _mock_session({"ok": True})
    with patch("aiohttp.ClientSession", return_value=session):
        result = _run(_call_set_reaction("TOKEN", "123", "42", "👍"))

    assert result == {"success": True, "emoji": "👍", "chat_id": "123", "message_id": "42"}
    _, kwargs = session.post.call_args
    assert kwargs["json"]["reaction"] == [{"type": "emoji", "emoji": "👍"}]


def test_call_set_reaction_api_error():
    from tools.telegram_react_tool import _call_set_reaction

    session = _mock_session({"ok": False, "description": "REACTION_INVALID"})
    with patch("aiohttp.ClientSession", return_value=session):
        result = _run(_call_set_reaction("TOKEN", "123", "42", "🦑"))

    assert "REACTION_INVALID" in result["error"]


def test_missing_emoji_returns_error():
    from tools.telegram_react_tool import telegram_react_tool

    assert json.loads(telegram_react_tool({})) == {"error": "emoji is required"}


def test_no_token_returns_error():
    from tools.telegram_react_tool import telegram_react_tool

    with patch("tools.telegram_react_tool._get_telegram_token", return_value=None):
        result = json.loads(telegram_react_tool({"emoji": "👍", "chat_id": "1", "message_id": "2"}))

    assert "not configured" in result["error"]


def test_uses_session_context_when_args_omitted():
    from tools.telegram_react_tool import telegram_react_tool

    react = AsyncMock(return_value={"success": True, "emoji": "🔥"})
    with (
        patch("tools.telegram_react_tool._get_telegram_token", return_value="tok"),
        patch("tools.telegram_react_tool._get_current_context", return_value=("456", "99")) as ctx,
        patch("tools.telegram_react_tool._call_set_reaction", react),
    ):
        result = json.loads(telegram_react_tool({"emoji": "🔥"}))

    ctx.assert_called_once()
    assert result["success"] is True


def test_explicit_args_skip_context_lookup():
    from tools.telegram_react_tool import telegram_react_tool

    react = AsyncMock(return_value={"success": True, "emoji": "❤", "chat_id": "999", "message_id": "7"})
    with (
        patch("tools.telegram_react_tool._get_telegram_token", return_value="tok"),
        patch("tools.telegram_react_tool._get_current_context") as ctx,
        patch("tools.telegram_react_tool._call_set_reaction", react),
    ):
        result = json.loads(telegram_react_tool({"emoji": "❤", "chat_id": "999", "message_id": "7"}))

    ctx.assert_not_called()
    assert result["chat_id"] == "999"


def test_runs_in_worker_thread_without_event_loop():
    from tools.telegram_react_tool import telegram_react_tool

    react = AsyncMock(return_value={"success": True, "emoji": "❤"})
    results = {}

    def worker():
        with (
            patch("tools.telegram_react_tool._get_telegram_token", return_value="tok"),
            patch("tools.telegram_react_tool._call_set_reaction", react),
        ):
            results["value"] = json.loads(
                telegram_react_tool({"emoji": "❤", "chat_id": "1", "message_id": "7"})
            )

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    assert results["value"]["success"] is True


def test_tool_registered_under_telegram_toolset():
    import tools.telegram_react_tool  # noqa: F401
    from tools.registry import registry

    entry = registry.get_entry("telegram_react")
    assert entry is not None
    assert entry.toolset == "telegram"
    assert entry.schema["parameters"]["required"] == ["emoji"]


def test_tool_exposed_only_to_telegram_composite():
    from toolsets import resolve_toolset

    assert "telegram_react" in resolve_toolset("hermes-telegram")
    assert "telegram_react" not in resolve_toolset("hermes-cli")
