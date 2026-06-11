"""Add an emoji reaction to a Telegram message without sending text."""

import json
import logging
from typing import Optional

from tools.registry import registry

logger = logging.getLogger(__name__)

_SCHEMA = {
    "name": "telegram_react",
    "description": (
        "Set an emoji reaction on a Telegram message. Lets the agent acknowledge "
        "a message silently — react with 👍 or ❤ instead of typing text. "
        "Use this as the whole response for short acknowledgement messages "
        "such as 'thanks', 'thank you', 'спасибо', '+1', or 'ок' when no "
        "substantive text answer is needed. Valid as the *only* response: "
        "after a successful call, send no text. "
        "Only available when Telegram gateway is configured.\n\n"
        "Examples:\n"
        "  User says спасибо: telegram_react(emoji='❤')\n"
        "  Silent ack: telegram_react(emoji='👍')\n"
        "  Specific msg: telegram_react(emoji='🔥', chat_id='-1001234', message_id='42')"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "emoji": {
                "type": "string",
                "description": (
                    "A Telegram reaction emoji, e.g. '👍', '❤', '🔥', '🎉', '👀', '🤔', "
                    "'😂', '🥰', '🤯', '👏', '🙏', '💯'. "
                    "Must be in Telegram's supported reaction set."
                ),
            },
            "chat_id": {
                "type": "string",
                "description": (
                    "Telegram chat ID (e.g. '-1001234567890'). "
                    "Defaults to the current session chat when omitted."
                ),
            },
            "message_id": {
                "type": "string",
                "description": (
                    "Telegram message ID to react to. "
                    "Defaults to the message that triggered this session."
                ),
            },
        },
        "required": ["emoji"],
    },
}


def _get_telegram_token() -> Optional[str]:
    try:
        from gateway.config import load_gateway_config, Platform

        config = load_gateway_config()
        pconfig = config.platforms.get(Platform.TELEGRAM)
        if pconfig and pconfig.token:
            return pconfig.token
    except Exception:
        pass
    return None


def _get_current_context() -> tuple[Optional[str], Optional[str]]:
    """Return (chat_id, message_id) from the active gateway session ContextVars."""
    try:
        from gateway.session_context import get_session_env

        chat_id = get_session_env("HERMES_SESSION_CHAT_ID") or None
        message_id = get_session_env("HERMES_SESSION_MESSAGE_ID") or None
        return chat_id, message_id
    except Exception:
        pass
    return None, None


async def _call_set_reaction(token: str, chat_id: str, message_id: str, emoji: str) -> dict:
    try:
        import aiohttp
    except ImportError:
        return {"error": "aiohttp not installed — run: pip install aiohttp"}

    try:
        from gateway.platforms.base import resolve_proxy_url, proxy_kwargs_for_aiohttp

        _proxy = resolve_proxy_url()
        _sess_kw, _req_kw = proxy_kwargs_for_aiohttp(_proxy)
    except Exception:
        _sess_kw, _req_kw = {}, {}

    url = f"https://api.telegram.org/bot{token}/setMessageReaction"
    payload = {
        "chat_id": chat_id,
        "message_id": int(message_id),
        "reaction": [{"type": "emoji", "emoji": emoji}],
    }

    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10), **_sess_kw
        ) as session:
            async with session.post(url, json=payload, **_req_kw) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return {
                        "success": True,
                        "emoji": emoji,
                        "chat_id": chat_id,
                        "message_id": message_id,
                    }
                return {"error": f"Telegram API error: {data.get('description', 'unknown')}"}
    except Exception as exc:
        return {"error": f"Request failed: {exc}"}


def telegram_react_tool(args: dict, **kwargs) -> str:
    emoji: str = args.get("emoji", "").strip()
    if not emoji:
        return json.dumps({"error": "emoji is required"})

    chat_id: Optional[str] = args.get("chat_id") or None
    message_id: Optional[str] = args.get("message_id") or None

    if not chat_id or not message_id:
        ctx_chat_id, ctx_message_id = _get_current_context()
        chat_id = chat_id or ctx_chat_id
        message_id = message_id or ctx_message_id

    if not chat_id:
        return json.dumps({"error": "chat_id could not be determined — pass chat_id= explicitly"})
    if not message_id:
        return json.dumps({"error": "message_id could not be determined — pass message_id= explicitly"})

    token = _get_telegram_token()
    if not token:
        return json.dumps({"error": "Telegram gateway not configured or no bot token found"})

    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, _call_set_reaction(token, chat_id, message_id, emoji))
                result = future.result(timeout=15)
        else:
            result = loop.run_until_complete(_call_set_reaction(token, chat_id, message_id, emoji))
    except Exception as exc:
        result = {"error": f"Async execution failed: {exc}"}

    return json.dumps(result)


registry.register(
    name="telegram_react",
    toolset="messaging",
    schema=_SCHEMA,
    handler=lambda args, **kw: telegram_react_tool(args, **kw),
    check_fn=lambda: _get_telegram_token() is not None,
    emoji="👍",
)
