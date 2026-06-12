from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

GUARD_KEY = b"00000-0000-0000"
DUMMY_CAPTCHA_TOKEN = "1.0000000000000000000000000000000000000000000000000000000000000000"


def sign_claim(queue_token: str, timestamp: int) -> str:
    return hmac.new(GUARD_KEY, f"{queue_token}:{timestamp}".encode(), hashlib.sha256).hexdigest()


async def iter_sse_events(response: httpx.Response) -> AsyncIterator[tuple[str | None, dict[str, Any]]]:
    event: str | None = None
    async for line in response.aiter_lines():
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            try:
                data = json.loads(line[5:].strip())
            except ValueError:
                continue
            yield event, data
