from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

CLIENT_TIMEOUT_MARGIN = 10.0


@dataclass
class Clearance:
    cookies: dict[str, str]
    user_agent: str
    obtained_at: float = 0.0


class FlareSolverrError(RuntimeError):
    pass


class FlareSolverr:
    def __init__(self, endpoint: str = "http://localhost:8191/v1", timeout: float = 90.0) -> None:
        self.endpoint = endpoint
        self.timeout = timeout

    async def get_clearance(self, url: str) -> Clearance:
        payload: dict[str, Any] = {"cmd": "request.get", "url": url, "maxTimeout": int(self.timeout * 1000)}
        async with httpx.AsyncClient(timeout=self.timeout + CLIENT_TIMEOUT_MARGIN, trust_env=False) as client:
            try:
                resp = await client.post(self.endpoint, json=payload)
            except httpx.HTTPError as exc:
                raise FlareSolverrError(f"cannot reach FlareSolverr at {self.endpoint}: {exc}") from exc
        data = resp.json()
        if data.get("status") != "ok":
            raise FlareSolverrError(f"FlareSolverr failed: {data.get('message')}")
        solution = data["solution"]
        cookies = {ck["name"]: ck["value"] for ck in solution.get("cookies", [])}
        if "cf_clearance" not in cookies:
            raise FlareSolverrError("no cf_clearance in FlareSolverr solution")
        return Clearance(cookies=cookies, user_agent=solution.get("userAgent", ""))
