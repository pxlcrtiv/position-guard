"""Telegram send path: disabled without token, posts the right payload with
one (mocked transport, no network)."""

from __future__ import annotations

import json

import httpx

from position_guard.telegram import TelegramSender


def test_disabled_without_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    sender = TelegramSender(token=None)
    assert sender.enabled is False
    assert sender.send("anything") is None


def test_send_posts_to_bot_api():
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        body = json.loads(request.content)
        assert body["chat_id"] == "987654"
        assert body["text"] == "CRITICAL — your ETH collateral is at 1.12 HF"
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    sender = TelegramSender(
        token="123:abc",
        chat_id="987654",
        transport=httpx.MockTransport(handler),
    )
    assert sender.enabled is True
    result = sender.send("CRITICAL — your ETH collateral is at 1.12 HF")
    assert result is not None and result["ok"] is True
    assert str(calls[0].url).startswith("https://api.telegram.org/bot123:abc/sendMessage")


def test_send_never_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"ok": False, "description": "Forbidden"})

    sender = TelegramSender(token="123:abc", chat_id="42", transport=httpx.MockTransport(handler))
    assert sender.send("hello") is None  # swallowed, logged


def test_chat_id_resolved_from_getme_when_absent():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("getMe"):
            return httpx.Response(200, json={"ok": True, "result": {"id": 555}})
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 9}})

    sender = TelegramSender(token="123:abc", transport=httpx.MockTransport(handler))
    assert sender.send("hi") is not None
    assert sender.chat_id == "555"