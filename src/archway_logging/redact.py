"""The backstop (section 7): known secret shapes are removed from any text before it is written.

The contract's real protection is structural -- only declared attributes are written, every value is bounded --
so this catches what slips into an exception message or a third-party library's text, never a substitute for
not logging secrets in the first place.
"""
from __future__ import annotations

import re

_PATTERNS = (
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),            # JWT
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"),                                  # bearer credential
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),                                          # GitHub token
    re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),                                            # AWS access key id
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),                                                # provider API key
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
)
_QUERY_SECRET = re.compile(
    r"(?i)([?&;\s](?:code|state|token|access_token|refresh_token|id_token|client_secret|password|secret|"
    r"api_key|apikey|key)=)[^&\s\"']+")
REDACTED = "[redacted]"


def redact(text: str, limit: int) -> str:
    """`text` with known secret shapes replaced, cut to `limit` characters."""
    value = str(text)
    for pattern in _PATTERNS:
        value = pattern.sub(REDACTED, value)
    value = _QUERY_SECRET.sub(lambda m: m.group(1) + REDACTED, value)
    return value if len(value) <= limit else value[: max(0, limit - 1)] + "…"


__all__ = ["REDACTED", "redact"]
