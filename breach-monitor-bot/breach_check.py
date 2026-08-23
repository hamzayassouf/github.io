"""Breach lookup logic, kept separate from the Telegram layer.

Uses the free XposedOrNot API (no API key needed) to check whether an
email address has appeared in a known data breach. Swapping in a paid
provider later (e.g. HaveIBeenPwned, or XposedOrNot's Plus API) only
means changing this module — the bot layer doesn't need to know.
"""

from xposedornot import XposedOrNot

_client = XposedOrNot()


def check_email(email: str) -> list[str]:
    """Return the list of breach names an email was found in (empty if none)."""
    result = _client.check_email(email)
    return result.breaches or []
