"""Send the digest through Gmail SMTP with an app password. Stdlib only."""

import re
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


_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")


def normalize_app_password(value: str) -> str:
    """Google shows app passwords as 'abcd efgh ijkl mnop'; it accepts them without spaces."""
    return "".join(value.split())


def validate_gmail_settings(user: str, app_password: str | None, to: str) -> list[str]:
    """Readable problems with the form input; empty list means OK.

    app_password=None means "keep the saved one" (the field was left blank).
    """
    problems = []
    if not _EMAIL.fullmatch(user.strip()):
        problems.append("Gmail address doesn't look like an email address.")
    if not _EMAIL.fullmatch(to.strip()):
        problems.append("Send digest to: doesn't look like an email address.")
    if app_password is not None:
        cleaned = normalize_app_password(app_password)
        if not (len(cleaned) == 16 and cleaned.isalpha()):
            problems.append(
                "App password should be 16 letters (Google shows it as 4 groups of 4). "
                "Your normal Gmail password won't work here."
            )
    return problems


def send_test_email(
    user: str,
    app_password: str,
    to: str,
    smtp_factory: Callable[..., smtplib.SMTP] | None = None,
) -> None:
    """Same code path as the real digest, with a tiny message."""
    test = Digest(
        subject="JobPilot test email",
        html="<p>It works: JobPilot can send your daily digest.</p>",
        text="It works: JobPilot can send your daily digest.",
        job_ids=(),
    )
    send_message(build_message(test, user, to), user, app_password, smtp_factory)
