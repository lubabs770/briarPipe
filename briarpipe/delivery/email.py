"""Email gateway over SMTP.

Connection details come from the environment (secrets), not config:

    SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASS, SMTP_FROM

If SMTP isn't configured the gateway runs in **dry-run** mode: it reports what it
*would* send instead of failing, so the rest of a run still completes.
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any

from . import Edition


class EmailGateway:
    name = "email"

    def __init__(self, to: str | None, options: dict[str, Any] | None = None) -> None:
        self.to = to
        self.options = options or {}

    def _smtp_config(self) -> dict[str, Any] | None:
        host = self.options.get("smtp_host") or os.environ.get("SMTP_HOST")
        user = self.options.get("smtp_user") or os.environ.get("SMTP_USER")
        password = os.environ.get("SMTP_PASS")
        if not (host and self.to):
            return None
        return {
            "host": host,
            "port": int(self.options.get("smtp_port") or os.environ.get("SMTP_PORT", 587)),
            "user": user,
            "password": password,
            "sender": self.options.get("smtp_from")
            or os.environ.get("SMTP_FROM")
            or user
            or "briarpipe@localhost",
        }

    def _build_message(self, edition: Edition, sender: str) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = f"{edition.title} — {edition.date}"
        msg["From"] = sender
        msg["To"] = self.to
        msg.set_content(edition.markdown)
        return msg

    def send(self, edition: Edition) -> str:
        cfg = self._smtp_config()
        if cfg is None:
            return (
                f"[dry-run] would email '{edition.title}' to {self.to or '(no recipient)'}; "
                "set SMTP_HOST + delivery.to to send for real"
            )
        msg = self._build_message(edition, cfg["sender"])
        with smtplib.SMTP(cfg["host"], cfg["port"]) as smtp:
            smtp.starttls()
            if cfg["user"] and cfg["password"]:
                smtp.login(cfg["user"], cfg["password"])
            smtp.send_message(msg)
        return f"emailed '{edition.title}' to {self.to}"
