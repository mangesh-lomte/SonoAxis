import hmac
import hashlib
import secrets
import time
import uuid
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from backend.app.db.connection import get_db

AUTH_SECRET_FILE = Path("D:/sovoice/data/config/auth_secret.key")
SESSION_COOKIE_NAME = "sonoaxis_session"
CSRF_COOKIE_NAME = "sonoaxis_csrf"
SESSION_TTL_SECONDS = 8 * 3600  # 8 hours

LOGIN_RATE_LIMIT_WINDOW_SECONDS = 300
LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 5

_PH = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
    type=Type.ID,  # Argon2id
)

_rate_lock = threading.Lock()
_failed_attempts: Dict[str, List[float]] = {}


class RateLimitError(Exception):
    pass


def _get_signing_secret() -> bytes:
    AUTH_SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    if AUTH_SECRET_FILE.is_file():
        data = AUTH_SECRET_FILE.read_bytes().strip()
        if len(data) >= 32:
            return data
    secret = secrets.token_hex(32).encode("utf-8")
    AUTH_SECRET_FILE.write_bytes(secret)
    return secret


def hash_password(password: str) -> str:
    """Hashes password with Argon2id (t=3, m=64 MiB, p=2, random 16-byte salt)."""
    return _PH.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """Constant-time Argon2id verification against stored hash."""
    if not stored_hash or not stored_hash.startswith("$argon2id$"):
        return False
    try:
        return bool(_PH.verify(stored_hash, password))
    except (VerifyMismatchError, InvalidHashError, Exception):
        return False


def _token_digest(raw_token: str) -> str:
    secret = _get_signing_secret()
    return hmac.new(secret, raw_token.encode("utf-8"), hashlib.sha256).hexdigest()


def _prune_attempts(key: str, now_ts: float) -> List[float]:
    cutoff = now_ts - LOGIN_RATE_LIMIT_WINDOW_SECONDS
    recent = [t for t in _failed_attempts.get(key, []) if t > cutoff]
    if recent:
        _failed_attempts[key] = recent
    else:
        _failed_attempts.pop(key, None)
    return recent


def check_login_rate_limit(client_key: str) -> None:
    now_ts = time.monotonic()
    with _rate_lock:
        recent = _prune_attempts(client_key, now_ts)
        if len(recent) >= LOGIN_RATE_LIMIT_MAX_ATTEMPTS:
            raise RateLimitError(
                "Too many failed login attempts. Account sign-in temporarily locked for 5 minutes."
            )


def record_login_failure(client_key: str) -> None:
    now_ts = time.monotonic()
    with _rate_lock:
        recent = _prune_attempts(client_key, now_ts)
        recent.append(now_ts)
        _failed_attempts[client_key] = recent


def clear_login_failures(client_key: str) -> None:
    with _rate_lock:
        _failed_attempts.pop(client_key, None)


def reset_rate_limiter_for_tests() -> None:
    with _rate_lock:
        _failed_attempts.clear()


def _format_user_row(row) -> Dict[str, Any]:
    d = dict(row)
    full_name = d.get("full_name", "")
    creds = (d.get("credentials") or "").strip()
    display_name = f"{full_name}, {creds}" if creds else full_name
    return {
        "id": d["id"],
        "username": d["username"],
        "full_name": full_name,
        "display_name": display_name,
        "credentials": d.get("credentials") or "",
        "designation": d.get("designation") or "",
        "role": d["role"],
        "department": d.get("department") or "",
        "email": d.get("email") or "",
        "is_active": bool(d.get("is_active", 1)),
        "is_demo": bool(d.get("is_demo", 0)),
        "created_at": d["created_at"],
        "last_login_at": d.get("last_login_at"),
    }


class AuthService:
    @staticmethod
    def authenticate_and_create_session(
        username: str,
        password: str,
        client_ip: str = "local",
        ttl_seconds: int = SESSION_TTL_SECONDS,
        db_path: Optional[str] = None,
    ) -> Tuple[str, str, Dict[str, Any]]:
        clean_user = username.strip().lower()
        rate_key = f"{client_ip}:{clean_user}"
        check_login_rate_limit(rate_key)

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        expires_iso = (now + timedelta(seconds=ttl_seconds)).isoformat()

        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE lower(username) = ?",
                (clean_user,),
            ).fetchone()
            if not row or not verify_password(password, row["password_hash"]):
                record_login_failure(rate_key)
                raise ValueError("Invalid doctor username or password.")
            if not row["is_active"]:
                record_login_failure(rate_key)
                raise PermissionError("Doctor account is inactive. Contact System Administrator.")

            clear_login_failures(rate_key)

            raw_token = secrets.token_urlsafe(36)
            csrf_token = secrets.token_urlsafe(32)
            digest = _token_digest(raw_token)
            sess_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO user_sessions (id, user_id, token_hash, csrf_token, created_at, expires_at, revoked)
                VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                (sess_id, row["id"], digest, csrf_token, now_iso, expires_iso),
            )
            conn.execute(
                "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
                (now_iso, now_iso, row["id"]),
            )
            updated = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
            return raw_token, csrf_token, _format_user_row(updated)

    @staticmethod
    def get_session_and_user_by_token(
        raw_token: str, db_path: Optional[str] = None
    ) -> Optional[Tuple[Dict[str, Any], str]]:
        if not raw_token:
            return None
        digest = _token_digest(raw_token)
        now_iso = datetime.now(timezone.utc).isoformat()
        with get_db(db_path) as conn:
            row = conn.execute(
                """
                SELECT u.*, s.csrf_token AS session_csrf_token
                FROM user_sessions s
                JOIN users u ON s.user_id = u.id
                WHERE s.token_hash = ? AND s.revoked = 0 AND s.expires_at > ? AND u.is_active = 1
                """,
                (digest, now_iso),
            ).fetchone()
            if not row:
                return None
            return _format_user_row(row), (row["session_csrf_token"] or "")

    @staticmethod
    def revoke_session(raw_token: Optional[str], db_path: Optional[str] = None) -> None:
        if not raw_token:
            return
        digest = _token_digest(raw_token)
        with get_db(db_path) as conn:
            conn.execute("UPDATE user_sessions SET revoked = 1 WHERE token_hash = ?", (digest,))

    @staticmethod
    def list_users(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
        with get_db(db_path) as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY role ASC, full_name ASC").fetchall()
            return [_format_user_row(r) for r in rows]

    @staticmethod
    def create_user(data: Dict[str, Any], db_path: Optional[str] = None) -> Dict[str, Any]:
        username = data["username"].strip().lower()
        now = datetime.now(timezone.utc).isoformat()
        user_id = f"usr-{uuid.uuid4().hex[:8]}"
        pw_hash = hash_password(data["password"])

        with get_db(db_path) as conn:
            existing = conn.execute("SELECT id FROM users WHERE lower(username) = ?", (username,)).fetchone()
            if existing:
                raise ValueError(f"Username '{username}' is already registered.")
            conn.execute(
                """
                INSERT INTO users (
                    id, username, password_hash, full_name, credentials, designation,
                    role, department, email, is_active, is_demo, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    user_id,
                    username,
                    pw_hash,
                    data["full_name"].strip(),
                    data.get("credentials", ""),
                    data.get("designation", ""),
                    data.get("role", "Radiologist"),
                    data.get("department", ""),
                    data.get("email", ""),
                    1 if data.get("is_demo") else 0,
                    now,
                    now,
                ),
            )
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return _format_user_row(row)

    @staticmethod
    def upsert_account_with_password(
        user_id: str,
        username: str,
        password: str,
        full_name: str,
        role: str,
        designation: str,
        department: str,
        email: str,
        is_demo: bool = True,
        db_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        clean_user = username.strip().lower()
        now = datetime.now(timezone.utc).isoformat()
        pw_hash = hash_password(password)
        with get_db(db_path) as conn:
            existing = conn.execute(
                "SELECT id FROM users WHERE id = ? OR lower(username) = ?",
                (user_id, clean_user),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE users SET
                        username = ?, password_hash = ?, full_name = ?, credentials = '',
                        designation = ?, role = ?, department = ?, email = ?,
                        is_active = 1, is_demo = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        clean_user, pw_hash, full_name, designation, role,
                        department, email, 1 if is_demo else 0, now, existing["id"],
                    ),
                )
                row = conn.execute("SELECT * FROM users WHERE id = ?", (existing["id"],)).fetchone()
            else:
                conn.execute(
                    """
                    INSERT INTO users (
                        id, username, password_hash, full_name, credentials, designation,
                        role, department, email, is_active, is_demo, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, '', ?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (
                        user_id, clean_user, pw_hash, full_name, designation,
                        role, department, email, 1 if is_demo else 0, now, now,
                    ),
                )
                row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return _format_user_row(row)

    @staticmethod
    def update_user(
        user_id: str,
        updates: Dict[str, Any],
        db_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        with get_db(db_path) as conn:
            existing = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if not existing:
                return None

            target_role = updates.get("role", existing["role"])
            target_active = updates.get("is_active", bool(existing["is_active"]))
            if existing["role"] == "Administrator" and (target_role != "Administrator" or not target_active):
                admin_count = conn.execute(
                    "SELECT COUNT(*) FROM users WHERE role = 'Administrator' AND is_active = 1 AND id != ?",
                    (user_id,),
                ).fetchone()[0]
                if admin_count == 0:
                    raise ValueError("Cannot deactivate or demote the only remaining active Administrator.")

            fields = []
            values = []
            for key in ("full_name", "credentials", "designation", "role", "department", "email"):
                if key in updates and updates[key] is not None:
                    fields.append(f"{key} = ?")
                    values.append(updates[key])
            if "is_active" in updates and updates["is_active"] is not None:
                fields.append("is_active = ?")
                values.append(1 if updates["is_active"] else 0)
            if updates.get("password"):
                fields.append("password_hash = ?")
                values.append(hash_password(updates["password"]))

            if fields:
                fields.append("updated_at = ?")
                values.append(now)
                values.append(user_id)
                conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)

            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return _format_user_row(row)

    @staticmethod
    def change_password(
        user_id: str,
        current_password: str,
        new_password: str,
        db_path: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with get_db(db_path) as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row or not verify_password(current_password, row["password_hash"]):
                raise ValueError("Current password is incorrect.")
            new_hash = hash_password(new_password)
            conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (new_hash, now, user_id),
            )
            # Invalidate existing active sessions on password rotation
            conn.execute("UPDATE user_sessions SET revoked = 1 WHERE user_id = ?", (user_id,))
