"""Optional Telegram send path — plain HTTPS to the Bot API (no extra deps).

Enabled only when TELEGRAM_BOT_TOKEN is set (and, optionally,
TELEGRAM_CHAT_ID — defaults to the bot's own chat_id off getMe). Silent no-op
otherwise, so demos and defaults work with zero keys.
"""

from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger("position_guard.telegram")

API = "https://api.telegram.org/bot{token}/"


class TelegramSender:
    def __init__(
        self,
        token: str | None = None,
        chat_id: str | None = None,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.timeout = timeout
        self._transport = transport

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def send(self, text: str) -> dict | None:
        """Send one message. Returns the API's parsed JSON, or None when
        disabled (no token) or on any transport error (never raises)."""
        if not self.enabled:
            return None
        try:
            client_kwargs: dict = {"timeout": self.timeout}
            if self._transport is not None:
                client_kwargs["transport"] = self._transport
            with httpx.Client(**client_kwargs) as client:
                if not self.chat_id:
                    me = client.get(API.format(token=self.token) + "getMe")
                    me.raise_for_status()
                    self.chat_id = str(me.json()["result"]["id"])
                resp = client.post(
                    API.format(token=self.token) + "sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "disable_web_page_preview": True,
                    },
                )
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            log.warning("telegram send failed: %s", exc)
            return None