"""Send the digest through Gmail SMTP with an app password. Stdlib only."""

import smtplib
from collections.abc import Callable
from email.message import EmailMessage

from jobpilot.digest import Digest

GMAIL_HOST = "smtp.gmail.com"
GMAIL_PORT = 587  # STARTTLS: connect in plain text, then upgrade to TLS before login


class MailError(Exception):
    """Sending failed. The message never contains the password."""


def build_message(digest: Digest, sender: str, to: str) -> EmailMessage:
    """One email with two versions: plain text first, HTML as the preferred alternative."""
    msg = EmailMessage()
    msg["Subject"] = digest.subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(digest.text)
    msg.add_alternative(digest.html, subtype="html")
    return msg


def send_message(
    msg: EmailMessage,
    user: str,
    app_password: str,
    smtp_factory: Callable[..., smtplib.SMTP] | None = None,
) -> None:
    factory = smtp_factory or smtplib.SMTP  # looked up at call time: easy to fake in tests
    try:
        with factory(GMAIL_HOST, GMAIL_PORT, timeout=30) as smtp:
            smtp.starttls()  # encrypt BEFORE sending credentials
            smtp.login(user, app_password)
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        raise MailError(
            "Gmail rejected the login. Use a 16-character app password "
            "(myaccount.google.com/apppasswords), not your normal password."
        ) from e
    except (smtplib.SMTPException, OSError) as e:
        raise MailError(f"Could not send email: {type(e).__name__}") from e
