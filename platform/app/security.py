"""Passwords, session tokens and a small in-memory rate limiter. Standard library only."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

# ---- passwords: scrypt with a random salt, stored as "scrypt$N$r$p$salt$hash" ----
_N, _R, _P = 2 ** 14, 8, 1
_COMMON = {"password12", "password123", "1234567890", "qwertyuiop", "iloveyou12", "welcome123", "admin12345", "letmein1234"}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return "$".join(["scrypt", str(_N), str(_R), str(_P), base64.b64encode(salt).decode(), base64.b64encode(dk).decode()])


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, dk = stored.split("$")
        if scheme != "scrypt":
            return False
        calc = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except Exception:
        return False


# A real hash to compare against when the email does not exist, so a login takes the same time either way.
_DUMMY = hash_password("not-a-real-password")


def burn_time() -> None:
    verify_password("x", _DUMMY)


def password_problem(password: str, email: str = "") -> str | None:
    """Returns a message when the password is too weak, else None."""
    if len(password) < 10:
        return "Use at least 10 characters."
    if len(password) > 128:
        return "That password is too long (128 characters at most)."
    low = password.lower()
    if low in _COMMON or (email and low == email.lower()) or len(set(password)) < 4:
        return "That password is too easy to guess. Try a longer phrase."
    return None


# ---- session tokens: the browser holds the random token; the database holds only its hash ----
def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---- rate limiter (per process; resets on restart) ----
class RateLimiter:
    def __init__(self) -> None:
        self.hits: dict[str, list[float]] = {}

    def allow(self, key: str, limit: int, window: int) -> bool:
        """Records one attempt and returns False when `key` has already made `limit` attempts in `window` seconds."""
        now = time.time()
        recent = [t for t in self.hits.get(key, []) if now - t < window]
        if len(recent) >= limit:
            self.hits[key] = recent
            return False
        self.hits[key] = recent + [now]
        return True

    def reset(self) -> None:
        self.hits.clear()


limiter = RateLimiter()
