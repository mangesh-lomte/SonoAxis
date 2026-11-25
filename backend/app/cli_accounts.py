"""
Secure local CLI utility for initializing and rotating doctor workstation accounts
without storing plaintext passwords in source code, scripts, or documentation.

Usage:
  python -m backend.app.cli_accounts init-demo
  python -m backend.app.cli_accounts reset-password --username asharma
  python -m backend.app.cli_accounts create-user --username jdoe --full-name "Dr. Jordan Doe" --role Radiologist
  python -m backend.app.cli_accounts list-users
"""
import argparse
import getpass
import os
import secrets
import sys

from backend.app.db.schema import init_db
from backend.app.db.connection import get_db
from backend.app.services.auth_service import AuthService, hash_password


def _prompt_password(label: str, env_var: str | None = None) -> str:
    if env_var and os.environ.get(env_var):
        pw = os.environ[env_var]
        if len(pw) < 8:
            raise ValueError(f"{env_var} must be at least 8 characters.")
        return pw
    if not sys.stdin.isatty():
        return secrets.token_urlsafe(14)
    pw1 = getpass.getpass(f"Enter password for {label} (min 8 chars): ")
    if len(pw1) < 8:
        raise ValueError("Password must be at least 8 characters.")
    pw2 = getpass.getpass(f"Confirm password for {label}: ")
    if pw1 != pw2:
        raise ValueError("Passwords do not match.")
    return pw1


def cmd_init_demo() -> None:
    init_db()
    rad_pw = _prompt_password("Dr. Aarav Sharma (asharma, Radiologist)", "SONOAXIS_RADIOLOGIST_PASSWORD")
    adm_pw = _prompt_password("System Administrator (sysadmin, Administrator)", "SONOAXIS_ADMIN_PASSWORD")

    rad = AuthService.upsert_account_with_password(
        user_id="usr-demo-rad",
        username="asharma",
        password=rad_pw,
        full_name="Dr. Aarav Sharma",
        role="Radiologist",
        designation="Consultant Radiologist (Demo)",
        department="Department of Radiology & Imaging",
        email="aarav.sharma@demo.local",
        is_demo=True,
    )
    adm = AuthService.upsert_account_with_password(
        user_id="usr-demo-admin",
        username="sysadmin",
        password=adm_pw,
        full_name="System Administrator",
        role="Administrator",
        designation="Workstation Administrator (Demo)",
        department="Clinical IT & Governance",
        email="sysadmin@demo.local",
        is_demo=True,
    )
    print(f"Configured fictional accounts: {rad['username']} ({rad['role']}), {adm['username']} ({adm['role']}).")


def cmd_reset_password(username: str) -> None:
    init_db()
    clean = username.strip().lower()
    pw = _prompt_password(clean, "SONOAXIS_NEW_PASSWORD")
    with get_db() as conn:
        row = conn.execute("SELECT id FROM users WHERE lower(username) = ?", (clean,)).fetchone()
        if not row:
            raise SystemExit(f"User '{clean}' not found.")
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(pw), row["id"]),
        )
        conn.execute("UPDATE user_sessions SET revoked = 1 WHERE user_id = ?", (row["id"],))
    print(f"Password rotated and active sessions revoked for '{clean}'.")


def cmd_create_user(username: str, full_name: str, role: str) -> None:
    init_db()
    pw = _prompt_password(username, "SONOAXIS_NEW_PASSWORD")
    u = AuthService.create_user({
        "username": username,
        "password": pw,
        "full_name": full_name,
        "role": role,
        "designation": "Consultant Radiologist" if role == "Radiologist" else "System Administrator",
        "department": "Department of Radiology & Imaging",
    })
    print(f"Created account: {u['username']} ({u['full_name']}, {u['role']}).")


def cmd_list_users() -> None:
    init_db()
    for u in AuthService.list_users():
        tag = "Demo" if u.get("is_demo") else "Standard"
        state = "Active" if u.get("is_active") else "Inactive"
        print(f"- {u['username']:<14} | {u['full_name']:<24} | {u['role']:<14} | {state} | {tag}")


def main() -> None:
    parser = argparse.ArgumentParser(description="SonoAxis local doctor account setup & rotation tool")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-demo", help="Initialize fictional Radiologist and Administrator demo accounts")
    p_reset = sub.add_parser("reset-password", help="Rotate password for an existing account")
    p_reset.add_argument("--username", required=True)

    p_create = sub.add_parser("create-user", help="Register a new doctor or administrator account")
    p_create.add_argument("--username", required=True)
    p_create.add_argument("--full-name", required=True)
    p_create.add_argument("--role", choices=["Radiologist", "Administrator"], default="Radiologist")

    sub.add_parser("list-users", help="List registered accounts")

    args = parser.parse_args()
    if args.command == "init-demo":
        cmd_init_demo()
    elif args.command == "reset-password":
        cmd_reset_password(args.username)
    elif args.command == "create-user":
        cmd_create_user(args.username, args.full_name, args.role)
    elif args.command == "list-users":
        cmd_list_users()


if __name__ == "__main__":
    main()
