from __future__ import annotations

import hashlib

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15"
)


def password_hash(username: str) -> str:
    return hashlib.md5(username.encode(), usedforsecurity=False).hexdigest()
