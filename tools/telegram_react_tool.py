"""Add an emoji reaction to a Telegram message."""

import json
import logging
from typing import Optional

from tools.registry import registry

logger = logging.getLogger(__name__)

_SCHEMA = {
    "name": "telegram_react",
    "description": (
        "Set an emoji reaction on a Telegram message. Use this to acknowledge "
        "or annotate the current Telegram message with a reaction such as "
        "thumbs up, heart, fire, party, or eyes. Defaults to the current "
        "gateway message when chat_id and message_id are omitted. Only "
        "available when the Telegram gateway is configured."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "emoji": {
                "type": "string",
                "description": (
                    "A Telegram reaction emoji, e.g. '👍', '❤', '🔥', '🎉', "
                    "'👀', '🤔', '😂', '👏', '🙏', or '💯'. Must be supported "
                    "by Telegram reactions."
                ),
            },
            "chat_id": {
                "type": "string",
                "description": (
                    "Telegram chat ID. Defaults to the current session chat "
                    "when omitted."
                ),
            },
            "message_id": {
                "type": "string",
                "description": (
                    "Telegram message ID to react to. Defaults to the message "
                    "that triggered the current session."
                ),
            },
        },
        "required": ["emoji"],
    },
}


def _get_telegram_token() -> Optional[str]:
    try:
        from gateway.config import Platform, load_gateway_config

        config = load_gateway_config()
        pconfig = config.platforms.get(Platform.TELEGRAM)
        if pconfig and pconfig.token:
            return pconfig.token
    except Exception:
        pass
    return None


def _get_current_context() -> tuple[Optional[str], Optional[str]]:
    """Return (chat_id, message_id) from the active gateway session."""
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
        return {"error": "aiohttp not installed"}

    try:
        from gateway.platforms.base import proxy_kwargs_for_aiohttp, resolve_proxy_url

        proxy_url = resolve_proxy_url()
        session_kwargs, request_kwargs = proxy_kwargs_for_aiohttp(proxy_url)
    except Exception:
        session_kwargs, request_kwargs = {}, {}

    url = f"https://api.telegram.org/bot{token}/setMessageReaction"
    payload = {
        "chat_id": chat_id,
        "message_id": int(message_id),
        "reaction": [{"type": "emoji", "emoji": emoji}],
    }

    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10), **session_kwargs
        ) as session:
            async with session.post(url, json=payload, **request_kwargs) as resp:
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


def _run_set_reaction(token: str, chat_id: str, message_id: str, emoji: str) -> dict:
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_call_set_reaction(token, chat_id, message_id, emoji))

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, _call_set_reaction(token, chat_id, message_id, emoji))
        return future.result(timeout=15)


def telegram_react_tool(args: dict, **kwargs) -> str:
    emoji = str(args.get("emoji", "")).strip()
    if not emoji:
        return json.dumps({"error": "emoji is required"})

    chat_id = args.get("chat_id") or None
    message_id = args.get("message_id") or None

    if not chat_id or not message_id:
        ctx_chat_id, ctx_message_id = _get_current_context()
        chat_id = chat_id or ctx_chat_id
        message_id = message_id or ctx_message_id

    if not chat_id:
        return json.dumps({"error": "chat_id could not be determined; pass chat_id explicitly"})
    if not message_id:
        return json.dumps({"error": "message_id could not be determined; pass message_id explicitly"})

    token = _get_telegram_token()
    if not token:
        return json.dumps({"error": "Telegram gateway is not configured or has no bot token"})

    try:
        result = _run_set_reaction(token, str(chat_id), str(message_id), emoji)
    except Exception as exc:
        result = {"error": f"Async execution failed: {exc}"}

    return json.dumps(result)


registry.register(
    name="telegram_react",
    toolset="telegram",
    schema=_SCHEMA,
    handler=lambda args, **kw: telegram_react_tool(args, **kw),
    check_fn=lambda: _get_telegram_token() is not None,
    emoji="👍",
)
