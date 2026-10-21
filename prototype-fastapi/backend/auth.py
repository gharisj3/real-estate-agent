"""Staff accounts and login sessions.
Passwords are stored only as salted scrypt hashes. Session tokens are stored only as hashes.
"""
import hashlib
import hmac
import os
import re
import secrets
import time

from fastapi import HTTPException, Request

from .database import get_connection

COOKIE_NAME = "propdesk_session"
SESSION_SECONDS = 8 * 3600
MIN_PASSWORD_LENGTH = 10
MAX_FAILURES = 5
FAILURE_WINDOW = 300

_N, _R, _P = 2**14, 8, 1
_failures: dict = {}


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p), dklen=32
        )
        return hmac.compare_digest(digest, bytes.fromhex(digest_hex))
    except ValueError:
        return False


_DUMMY_HASH = hash_password("dummy-password-for-timing")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_or_update_staff(username: str, password: str) -> bool:
    """Returns True if a new account was created, False if an existing password was reset."""
    if not re.fullmatch(r"[A-Za-z0-9._-]{3,50}", username):
        raise ValueError("Username must be 3-50 letters, numbers, dots, dashes or underscores.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    password_hash = hash_password(password)
    conn = get_connection()
    try:
        existing = conn.execute("SELECT id FROM staff WHERE username = ?", (username,)).fetchone()
        if existing:
            conn.execute("UPDATE staff SET password_hash = ? WHERE id = ?", (password_hash, existing["id"]))
            conn.execute("DELETE FROM sessions WHERE staff_id = ?", (existing["id"],))
        else:
            conn.execute("INSERT INTO staff (username, password_hash) VALUES (?, ?)", (username, password_hash))
        conn.commit()
        return existing is None
    finally:
        conn.close()


def check_login(username: str, password: str):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM staff WHERE username = ?", (username,)).fetchone()
    finally:
        conn.close()
    ok = verify_password(password, row["password_hash"] if row else _DUMMY_HASH)
    return dict(row) if row and ok else None


def too_many_failures(key) -> bool:
    now = time.time()
    recent = [t for t in _failures.get(key, []) if now - t < FAILURE_WINDOW]
    _failures[key] = recent
    return len(recent) >= MAX_FAILURES


def record_failure(key) -> None:
    _failures.setdefault(key, []).append(time.time())


def clear_failures(key) -> None:
    _failures.pop(key, None)


def start_session(staff_id: int) -> str:
    token = secrets.token_urlsafe(32)
    conn = get_connection()
    try:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (int(time.time()),))
        conn.execute(
            "INSERT INTO sessions (token_hash, staff_id, expires_at) VALUES (?, ?, ?)",
            (_token_hash(token), staff_id, int(time.time()) + SESSION_SECONDS),
        )
        conn.commit()
    finally:
        conn.close()
    return token


def end_session(token: str) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
        conn.commit()
    finally:
        conn.close()


def require_staff(request: Request) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT s.id, s.username FROM sessions x JOIN staff s ON s.id = x.staff_id "
                "WHERE x.token_hash = ? AND x.expires_at > ?",
                (_token_hash(token), int(time.time())),
            ).fetchone()
        finally:
            conn.close()
        if row:
            return dict(row)
    raise HTTPException(status_code=401, detail="Please log in.")
