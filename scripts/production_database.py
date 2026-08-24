"""Back up or restore the production database using binary-safe subprocess pipes."""

import argparse
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["backup", "restore"])
    parser.add_argument("file", type=Path)
    parser.add_argument("--env-file", default=".env.production")
    parser.add_argument(
        "--project-name", help="Use a separate project for restore drills"
    )
    parser.add_argument(
        "--override", help="Optional local Compose override for restore drills"
    )
    args = parser.parse_args()
    compose = [
        "docker",
        "compose",
        "--env-file",
        args.env_file,
        "-f",
        "compose.production.yml",
    ]
    if args.project_name:
        compose.extend(["-p", args.project_name])
    if args.override:
        compose.extend(["-f", args.override])
    if args.operation == "backup":
        args.file.parent.mkdir(parents=True, exist_ok=True)
        with args.file.open("xb") as output:
            args.file.chmod(0o600)
            result = subprocess.run(
                [
                    *compose,
                    "exec",
                    "-T",
                    "app-db",
                    "pg_dump",
                    "-U",
                    "insightforge",
                    "-d",
                    "insightforge",
                    "--format=custom",
                ],
                stdout=output,
                check=False,
            )
        if result.returncode:
            args.file.unlink()
            raise SystemExit(result.returncode)
        print(
            f"Database backup saved to {args.file}. Also preserve your environment secrets."
        )
    else:
        if not args.file.is_file():
            parser.error("Backup file does not exist")
        # Check the archive before stopping the application.
        with args.file.open("rb") as source:
            subprocess.run(
                [*compose, "exec", "-T", "app-db", "pg_restore", "--list"],
                stdin=source,
                stdout=subprocess.DEVNULL,
                check=True,
            )
        expected = "restore production database"
        if (
            input(f'Type "{expected}" to restore into the configured database: ')
            != expected
        ):
            raise SystemExit("Restore cancelled")
        subprocess.run([*compose, "stop", "api", "web", "proxy"], check=True)
        with args.file.open("rb") as source:
            subprocess.run(
                [
                    *compose,
                    "exec",
                    "-T",
                    "app-db",
                    "pg_restore",
                    "-U",
                    "insightforge",
                    "-d",
                    "insightforge",
                    "--clean",
                    "--if-exists",
                    "--no-owner",
                    "--single-transaction",
                    "--exit-on-error",
                ],
                stdin=source,
                check=True,
            )
        subprocess.run([*compose, "up", "-d", "--wait"], check=True)
        print("Database restored and application restarted.")


if __name__ == "__main__":
    main()
