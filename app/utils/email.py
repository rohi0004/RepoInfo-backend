"""Transactional email service.

Renders HTML/text via Jinja2 templates baked into `templates/emails/`. Delivery
uses aiosmtplib-style asyncio.to_thread indirection over the stdlib smtplib so
we don't pull in another dependency. In development, emails are logged instead
of sent when SMTP credentials are absent.
"""

from __future__ import annotations

import asyncio
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from app.core.config import settings
from app.core.logging import logger

try:
    _env = Environment(
        loader=PackageLoader("app", "templates/emails"),
        autoescape=select_autoescape(["html", "xml"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
except Exception:  # templates dir may not yet be shipped in dev
    _env = None  # type: ignore[assignment]


@dataclass(slots=True)
class EmailPayload:
    to: str
    subject: str
    text: str
    html: str | None = None


class EmailService:
    def _render(self, template: str, context: dict) -> tuple[str, str]:
        if _env is None:
            body = f"{template}: {context}"
            return body, body
        try:
            html = _env.get_template(f"{template}.html").render(**context)
        except Exception:
            html = ""
        text = _env.get_template(f"{template}.txt").render(**context) if _env else ""
        return text, html

    async def send(self, payload: EmailPayload) -> None:
        if not settings.SMTP_HOST or not settings.SMTP_USER:
            logger.info(f"[EMAIL:noop] to={payload.to} subject={payload.subject}")
            logger.debug(payload.text)
            return
        msg = EmailMessage()
        msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>"
        msg["To"] = payload.to
        msg["Subject"] = payload.subject
        msg.set_content(payload.text)
        if payload.html:
            msg.add_alternative(payload.html, subtype="html")
        await asyncio.to_thread(self._smtp_send, msg)

    def _smtp_send(self, msg: EmailMessage) -> None:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            if settings.SMTP_TLS:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

    async def send_verification(self, *, to: str, otp: str, name: str) -> None:
        text = (
            f"Hi {name},\n\nYour RepoInfo verification code is: {otp}\n\n"
            f"This code expires in {settings.OTP_EXPIRE_MINUTES} minutes."
        )
        await self.send(EmailPayload(to=to, subject="Verify your email", text=text))

    async def send_password_reset(self, *, to: str, reset_url: str, name: str) -> None:
        text = (
            f"Hi {name},\n\nUse the link below to reset your password. It expires in "
            f"{settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes.\n\n{reset_url}\n\n"
            "If you did not request a reset, you can safely ignore this email."
        )
        await self.send(EmailPayload(to=to, subject="Reset your password", text=text))


email_service = EmailService()
