"""Create a new, ignored production environment without printing its secrets."""

import argparse
import getpass
import re
import secrets
from pathlib import Path

import bcrypt
from cryptography.fernet import Fernet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--domain", required=True, help="Public DNS name without https://"
    )
    parser.add_argument("--email", required=True, help="Certificate renewal contact")
    parser.add_argument(
        "--database-targets", default="", help="Comma-separated host:port pairs"
    )
    parser.add_argument("--access-mode", choices=["public", "owner"], default="public")
    parser.add_argument("--username", default="owner")
    parser.add_argument(
        "--provider", choices=["groq", "openai", "anthropic"], default="groq"
    )
    parser.add_argument("--model", help="Provider-specific model ID")
    parser.add_argument("--output", default=".env.production")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", args.domain):
        parser.error("Use a DNS hostname without a scheme, path or port")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", args.username):
        parser.error(
            "Username must contain only letters, numbers, underscores or hyphens"
        )
    password_hash, api_key = "", ""
    if args.access_mode == "owner":
        if not args.database_targets:
            parser.error("Owner mode requires --database-targets")
        password = getpass.getpass("Owner password (at least 16 characters): ")
        if len(password) < 16 or len(password.encode()) > 72:
            parser.error(
                "Password must be at least 16 characters and at most 72 UTF-8 bytes"
            )
        if getpass.getpass("Confirm owner password: ") != password:
            parser.error("Passwords do not match")
        api_key = getpass.getpass(f"{args.provider} API key: ").strip()
        if not api_key:
            parser.error("The selected provider's API key is required")
        password_hash = bcrypt.hashpw(
            password.encode(), bcrypt.gensalt(rounds=12)
        ).decode()
    values = {
        "DOMAIN": args.domain.lower(),
        "ACME_EMAIL": args.email,
        "ADMIN_USERNAME": args.username,
        "ADMIN_PASSWORD_HASH": password_hash,
        "ACCESS_MODE": args.access_mode,
        "POSTGRES_PASSWORD": secrets.token_hex(32),
        "SECRET_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "ACCESS_PROXY_TOKEN": secrets.token_urlsafe(48),
        "EXTERNAL_DB_ALLOWED_TARGETS": args.database_targets.lower(),
        "AI_PROVIDER": args.provider,
        "AI_MODEL": (
            args.model
            or {
                "groq": "openai/gpt-oss-120b",
                "openai": "gpt-6-luna",
                "anthropic": "claude-sonnet-5-5",
            }[args.provider]
        )
        if args.access_mode == "owner"
        else "",
        "GROQ_API_KEY": api_key if args.provider == "groq" else "",
        "OPENAI_API_KEY": api_key if args.provider == "openai" else "",
        "ANTHROPIC_API_KEY": api_key if args.provider == "anthropic" else "",
    }
    if any("'" in value or "\n" in value or "\r" in value for value in values.values()):
        parser.error("Configuration values cannot contain quotes or line breaks")
    path = Path(args.output)
    # Exclusive creation protects existing encryption keys and database passwords.
    with path.open("x", encoding="utf-8") as output:
        path.chmod(0o600)
        output.write(
            "# Keep this file private. Back it up separately from the database.\n"
        )
        for key, value in values.items():
            output.write(f"{key}='{value}'\n")
    print(f"Created {path}. No secrets were printed. Keep this file out of Git.")


if __name__ == "__main__":
    main()
