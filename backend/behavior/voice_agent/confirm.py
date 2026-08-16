"""Spoken confirm gate for risky voice-agent tools."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

YES = frozenset({"yes", "yeah", "yep", "y", "confirm", "ok", "okay", "do it", "sure"})
NO = frozenset({"no", "nope", "n", "cancel", "stop", "don't", "dont"})


@dataclass
class PendingConfirm:
    tool_name: str
    args: dict[str, Any]
    prompt: str
    created_at: float
    timeout_s: float = 45.0

    def expired(self, now: float | None = None) -> bool:
        return (now or time.time()) - self.created_at > self.timeout_s


class ConfirmGate:
    def __init__(self) -> None:
        self.pending: PendingConfirm | None = None

    def clear(self) -> None:
        self.pending = None

    def arm(self, tool_name: str, args: dict[str, Any], prompt: str) -> PendingConfirm:
        self.pending = PendingConfirm(
            tool_name=tool_name,
            args=dict(args or {}),
            prompt=prompt,
            created_at=time.time(),
        )
        return self.pending

    def interpret(self, utterance: str) -> str | None:
        """Return 'yes', 'no', or None if not a confirm answer / no pending."""
        if not self.pending:
            return None
        if self.pending.expired():
            self.clear()
            return "no"
        text = (utterance or "").strip().lower()
        # take first token-ish phrase
        compact = " ".join(text.replace(",", " ").split())
        if compact in YES or any(compact.startswith(y + " ") for y in YES):
            return "yes"
        if compact in NO or any(compact.startswith(n + " ") for n in NO):
            return "no"
        # bare yes/no contained
        tokens = set(compact.split())
        if tokens & YES and not (tokens & NO):
            return "yes"
        if tokens & NO:
            return "no"
        return None

    def resolve(
        self,
        utterance: str,
        execute: Callable[[str, dict[str, Any]], str],
    ) -> tuple[str | None, bool]:
        """
        If pending confirm, try resolve.
        Returns (reply_or_None, handled).
        handled=True means utterance was consumed by confirm flow.
        """
        if not self.pending:
            return None, False
        if self.pending.expired():
            self.clear()
            return "Confirmation timed out. Cancelled.", True
        decision = self.interpret(utterance)
        if decision is None:
            return (
                f"Please say yes or no. {self.pending.prompt}",
                True,
            )
        pending = self.pending
        self.clear()
        if decision == "no":
            return "Cancelled.", True
        try:
            result = execute(pending.tool_name, pending.args)
        except Exception as exc:  # noqa: BLE001
            return f"Failed: {exc}", True
        return result or "Done.", True
