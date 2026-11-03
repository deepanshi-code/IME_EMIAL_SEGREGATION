import email
import email.policy
import imaplib
import mailbox
import os
import tempfile
from datetime import date, timedelta
from email.utils import parsedate_to_datetime

from pipeline import parse_eml

IMAP_HOSTS = {"Gmail": "imap.gmail.com", "Outlook / Microsoft 365": "outlook.office365.com",
              "Yahoo": "imap.mail.yahoo.com", "Zoho": "imap.zoho.com"}


def received_date(message):
    try:
        return parsedate_to_datetime(message["date"]).date()
    except (TypeError, ValueError, IndexError):
        return None


def message_item(raw, fallback_source):
    message = email.message_from_bytes(raw, policy=email.policy.default)
    subject = str(message["subject"] or "(no subject)")
    sender = str(message["from"] or "")
    return {
        "source": f"{subject[:60]} – {sender[:40]}" if sender else subject[:80] or fallback_source,
        "received": received_date(message),
        "text": parse_eml(raw),
    }


def read_mbox(raw):
    """Emails from an exported .mbox file (Gmail Takeout, Thunderbird, Apple Mail), newest first."""
    # mailbox needs a file path, so the upload is written to a private temporary file and removed after.
    handle, path = tempfile.mkstemp(suffix=".mbox")
    try:
        with os.fdopen(handle, "wb") as f:
            f.write(raw)
        box = mailbox.mbox(path, create=False)
        items = [message_item(message.as_bytes(), f"mbox message {i + 1}") for i, message in enumerate(box)]
        box.close()
    finally:
        os.remove(path)
    return sorted(items, key=lambda item: item["received"] or date.min, reverse=True)


def read_imap(host, user, password, folder="INBOX", days=7, limit=200, connect=imaplib.IMAP4_SSL):
    """Emails from the last `days` days, newest first. The folder is opened read-only, so nothing in
    the mailbox is changed (not even the "seen" flag). Credentials are used for this call only."""
    since = (date.today() - timedelta(days=days)).strftime("%d-%b-%Y")
    server = connect(host)
    try:
        server.login(user, password)
        status, _ = server.select(f'"{folder}"', readonly=True)
        if status != "OK":
            raise RuntimeError(f"Could not open folder {folder!r}")
        status, data = server.search(None, "SINCE", since)
        ids = data[0].split()[-limit:] if status == "OK" and data and data[0] else []
        items = []
        for message_id in reversed(ids):
            # BODY.PEEK fetches without setting the \Seen flag.
            status, parts = server.fetch(message_id, "(BODY.PEEK[])")
            raw = next((part[1] for part in parts if isinstance(part, tuple)), None) if status == "OK" else None
            if raw:
                items.append(message_item(raw, f"IMAP message {message_id.decode()}"))
        return items
    finally:
        try:
            server.logout()
        except Exception:
            pass
