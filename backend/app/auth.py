"""Demo authentication.

Uses a simple in-memory token store (dict).  Tokens are UUID4 strings.
No expiry for the demo — suitable for a 2-day jury session only.

Usage (in route handlers):
    from .auth import require_role
    user = require_role(request, "admin")
"""
from __future__ import annotations

import secrets
from typing import Literal

from fastapi import HTTPException, Request

from .config import USERS

# ---------------------------------------------------------------------------
# Token store: token -> {"username": ..., "role": ...}
# ---------------------------------------------------------------------------
_TOKENS: dict[str, dict] = {}


def login(username: str, password: str) -> dict:
    """Validate credentials and return a token dict, or raise HTTP 401."""
    entry = USERS.get(username)
    if not entry or entry[0] != password:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = secrets.token_hex(32)
    _TOKENS[token] = {"username": username, "role": entry[1]}
    return {"token": token, "role": entry[1], "username": username}


def logout(token: str) -> None:
    _TOKENS.pop(token, None)


def _get_token(request: Request) -> str | None:
    """Extract the bearer token from the Authorization header or a query param."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    # Fallback: ?token=... (useful for SSE EventSource which can't set headers)
    return request.query_params.get("token")


def get_current_user(request: Request) -> dict | None:
    token = _get_token(request)
    if not token:
        return None
    return _TOKENS.get(token)


def require_auth(request: Request) -> dict:
    """Return the current user or raise HTTP 401."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_role(request: Request, role: Literal["citizen", "admin"]) -> dict:
    """Return the current user if they have the required role, else raise HTTP 403."""
    user = require_auth(request)
    if user["role"] != role:
        raise HTTPException(
            status_code=403,
            detail=f"This endpoint requires the '{role}' role",
        )
    return user


def require_admin(request: Request) -> dict:
    return require_role(request, "admin")
