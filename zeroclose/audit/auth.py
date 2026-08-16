from __future__ import annotations

import secrets


class AuditorTokenAuth:
    def __init__(self, tokens: set[str] | None = None) -> None:
        self.tokens = tokens or set()

    def issue(self) -> str:
        token = secrets.token_urlsafe(24)
        self.tokens.add(token)
        return token

    def verify(self, token: str) -> bool:
        return token in self.tokens
