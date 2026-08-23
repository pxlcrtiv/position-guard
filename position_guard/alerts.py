"""Plain-English alert writer.

Two interchangeable backends (mirroring slither-chat's rule/llm pattern):

  - template  (default): deterministic, zero-dependency, always works. Rotates
    through a few hand-written phrasings per state (seeded by address + state,
    so output is stable per position). Produces messages in the shape of the
    project one-liner: "your ETH collateral is at 1.12 HF, ~$762 of margin left".
  - llm       (optional): any OpenAI-compatible /chat/completions endpoint.
    Degrades to the template backend on any failure (no key, timeout, non-2xx,
    malformed JSON), so alerts are never silently dropped.

Config (env vars):
  POSITION_GUARD_ALERT_BACKEND=template|llm   (default template)
  POSITION_GUARD_LLM_BASE_URL  (default https://api.openai.com/v1)
  POSITION_GUARD_LLM_API_KEY
  POSITION_GUARD_LLM_MODEL     (default gpt-4o-mini)
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

import httpx

from .health import margin_left_usd
from .models import Position
from .state import Level

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"

# One (multi-line) phrasing template per state; {asset} is the dominant
# collateral symbol, {protocol} the protocol id, {hf} the rounded HF,
# {margin} the rounded dollar margin.
_TEMPLATES: dict[Level, list[str]] = {
    Level.LIQUIDATION: [
        "LIQUIDATION WINDOW OPEN — {asset} collateral on {protocol} is at {hf} HF with no margin left: {debt} of debt against {collat} of collateral. Repay or add collateral NOW.",
        "Urgent: your {asset} position on {protocol} is liquidatable at {hf} HF. ${margin} of margin means liquidators can take your collateral — add funds immediately.",
    ],
    Level.CRITICAL: [
        "CRITICAL — your {asset} collateral is at {hf} HF, ~${margin} of margin left. A small price move liquidates this {protocol} position; add collateral or reduce debt now.",
        "Your {asset} position on {protocol} is at {hf} HF with only ~${margin} of breathing room. This is liquidation-adjacent — top up or repay today.",
    ],
    Level.WARNING: [
        "WARNING — {asset} collateral on {protocol} drifted to {hf} HF (~${margin} margin). The trend is your enemy here; act while there is still room.",
        "Heads-up: your {asset} position on {protocol} is at {hf} HF, ~${margin} of margin. Worth planning a top-up before it gets tight.",
    ],
    Level.WATCH: [
        "WATCH — {asset} collateral at {hf} HF on {protocol} (~${margin} margin). Keep an eye on it; no action needed yet.",
        "Your {protocol} position is in watch territory: {asset} at {hf} HF, ~${margin} of cushion. Monitoring mode.",
    ],
    Level.HEALTHY: [
        "HEALTHY — {asset} collateral at {hf} HF with ~${margin} of cushion on {protocol}. Nothing to do.",
        "All good: {asset} position on {protocol} sits at {hf} HF with ~${margin} of margin. No action needed.",
    ],
}


def _fmt_usd(value: float) -> str:
    return f"{value:,.0f}"


def _tpl_ctx(position: Position, hf: float | None, level: Level) -> dict:
    return {
        "asset": position.dominant_symbol,
        "protocol": position.protocol,
        "hf": f"{hf:.2f}" if hf is not None else "∞",
        "margin": _fmt_usd(max(0.0, margin_left_usd(position))),
        "debt": _fmt_usd(position.debt_usd),
        "collat": _fmt_usd(position.collateral_usd),
    }


@dataclass
class Alert:
    level: Level
    message: str
    backend: str  # "template" | "llm"
    hf: float | None
    margin_usd: float

    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "message": self.message,
            "backend": self.backend,
            "hf": self.hf,
            "margin_usd": self.margin_usd,
        }


def _deterministic_index(seed: str, n: int) -> int:
    return int(hashlib.sha1(seed.encode()).hexdigest(), 16) % n


class AlertWriter:
    """Writes an alert for a position/state. `backend` defaults to "template";
    llm requires POSITION_GUARD_LLM_API_KEY and falls back gracefully."""

    def __init__(self, backend: str | None = None, transport: httpx.BaseTransport | None = None) -> None:
        self.backend = (backend or os.environ.get("POSITION_GUARD_ALERT_BACKEND", "template")).lower()
        self.base_url = os.environ.get("POSITION_GUARD_LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        self.api_key = os.environ.get("POSITION_GUARD_LLM_API_KEY", "")
        self.model = os.environ.get("POSITION_GUARD_LLM_MODEL", DEFAULT_MODEL)
        self._transport = transport

    def write(self, position: Position, hf: float | None, level: Level) -> Alert:
        if self.backend == "llm" and self.api_key:
            message = self._llm_write(position, hf, level)
            if message:
                return Alert(level, message, "llm", hf, margin_left_usd(position))
        return Alert(level, self._template_write(position, hf, level), "template", hf, margin_left_usd(position))

    # -- template backend ----------------------------------------------------

    def _template_write(self, position: Position, hf: float | None, level: Level) -> str:
        candidates = _TEMPLATES[level]
        idx = _deterministic_index(f"{position.address}:{level.value}", len(candidates))
        return candidates[idx].format(**_tpl_ctx(position, hf, level))

    # -- llm backend ---------------------------------------------------------

    def _llm_write(self, position: Position, hf: float | None, level: Level) -> str | None:
        """Ask an OpenAI-compatible endpoint for a one-sentence alert. Any
        failure returns None and the caller falls back to templates."""
        system = (
            "You write plain-English DeFi risk alerts for a health monitoring tool. "
            "One or two sentences, concrete numbers, no markdown, no preamble, "
            "not financial advice. A health factor (HF) below 1.0 means the "
            "position is liquidatable."
        )
        user = json.dumps(
            {
                "position": position.to_dict(),
                "health_factor": hf,
                "level": level.value,
                "state_label": level.name,
            }
        )
        try:
            client_kwargs: dict = {"timeout": 15.0}
            if self._transport is not None:
                client_kwargs["transport"] = self._transport
            with httpx.Client(**client_kwargs) as client:
                resp = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 140,
                    },
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError):
            return None