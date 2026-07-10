from __future__ import annotations

import json
import os
import urllib.request

from ai_investor.core.interfaces.providers import Notifier


class ConsoleNotifier(Notifier):
    def send(self, message: str) -> None:
        print(f"[notify] {message}")


class DiscordNotifier(Notifier):
    """Reads DISCORD_WEBHOOK_URL from env. Free, no account tier needed."""

    def __init__(self, webhook_url: str | None = None):
        self.url = webhook_url or os.environ.get("DISCORD_WEBHOOK_URL", "")

    def send(self, message: str) -> None:
        if not self.url:
            print(f"[notify:no-webhook] {message}")
            return
        req = urllib.request.Request(
            self.url,
            data=json.dumps({"content": message[:1900]}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:  # notification failure must never kill a cycle
            print(f"[notify:failed] {e}: {message}")
