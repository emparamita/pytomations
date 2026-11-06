#!/usr/bin/env python3
"""Manage the project's explicitly local Oracle Free development database."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from decimal import Decimal
import os
from pathlib import Path
import re
import subprocess
import sys

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = ROOT / ".local-db.env"
COMPOSE_FILE = ROOT / ".agents" / "local-db" / "compose.yaml"
CONTAINER_SERVICE = "oracle"
TABLE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]*$")
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def load_local_config(env_file: Path) -> None:
    if not env_file.is_file():
        raise FileNotFoundError(
            f"Missing {env_file}; copy .agents/local-db/.local-db.env.example "
            "to .local-db.env and set local-only passwords."
        )
    load_dotenv(env_file, override=True)


def validate_local_credentials() -> None:
    for key in ("LOCAL_ORACLE_PASSWORD", "LOCAL_DB_PASSWORD"):
        password = os.environ.get(key, "")
        if not password or password.startswith("change-this-"):
            raise ValueError(f"Set a strong local-only {key} in .local-db.env before using the database.")
        if not re.fullmatch(r"[A-Za-z0-9._#-]+", password):
            raise ValueError(f"{key} may contain letters, digits, dot, underscore, hash, and hyphen only.")
    username = os.environ.get("LOCAL_DB_USER", "local_app")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_$#]{0,127}", username):
        raise ValueError("LOCAL_DB_USER must be a simple Oracle username")


def compose(env_file: Path, args: list[str], dry_run: bool) -> None:
    command = [
        "docker", "compose", "--env-file", str(env_file),
        "--file", str(COMPOSE_FILE), *args,
    ]
    if dry_run:
        print(f"Would run: {' '.join(command)}")
        print("Oracle listener is bound to 127.0.0.1 only; no production URL is used.")
        return
    subprocess.run(command, cwd=ROOT, check=True)


def start(env_file: Path, dry_run: bool) -> None:
    load_local_config(env_file)
    validate_local_credentials()
    compose(env_file, ["up", "--detach", CONTAINER_SERVICE], dry_run)
    if not dry_run:
        print("Started the local Oracle Free container; wait for its health check before connecting.")


def status(env_file: Path, dry_run: bool) -> None:
    load_local_config(env_file)
    compose(env_file, ["ps", CONTAINER_SERVICE], dry_run)


def execute_script(script_path: Path, env_file: Path, dry_run: bool) -> None:
    load_local_config(env_file)
    validate_local_credentials()
    script = script_path.expanduser().resolve()
    if not script.is_file():
        raise FileNotFoundError(f"SQL script not found: {script}")
    password = os.environ.get("LOCAL_DB_PASSWORD") or os.environ.get("LOCAL_ORACLE_PASSWORD")
    if not password:
        raise ValueError("LOCAL_DB_PASSWORD or LOCAL_ORACLE_PASSWORD must be set in the local DB env file")
    username = os.environ.get("LOCAL_DB_USER", "local_app")
    if dry_run:
        print(f"Would execute {script} against local schema {username} at {os.environ.get('LOCAL_DB_DSN', '127.0.0.1:1521/FREEPDB1')}")
        return
    # Credentials are sent over stdin, not included in the Docker/SQL*Plus argv.
    sqlplus_input = (
        "WHENEVER OSERROR EXIT FAILURE\n"
        "WHENEVER SQLERROR EXIT SQL.SQLCODE\n"
        f'CONNECT {username}/"{password}"@//127.0.0.1:1521/FREEPDB1\n'
        f"{script.read_text(encoding='utf-8')}\nEXIT\n"
    )
    subprocess.run(
        ["docker", "exec", "--interactive", "local-db-oracle", "sqlplus", "-s", "/nolog"],
        cwd=ROOT,
        input=sqlplus_input,
        check=True,
        text=True,
    )


def _dsn_host(dsn: str) -> str:
    host = dsn.removeprefix("//").split("/", 1)[0].rsplit(":", 1)[0].strip("[]")
    if host not in LOOPBACK_HOSTS:
        raise ValueError(
            "Refusing database access: LOCAL_DB_DSN must use localhost, "
            "127.0.0.1, or ::1. This helper is local-only."
        )
    return host


def _row_value(data_type: str, size: int, precision: int | None, scale: int | None,
               row_index: int, column_index: int) -> object:
    normalized = data_type.upper()
    if normalized in {"NUMBER", "FLOAT", "BINARY_FLOAT", "BINARY_DOUBLE"}:
        if scale in (None, 0):
            return row_index * 100 + column_index
        decimal_places = min(max(scale, 0), 6)
        return Decimal(f"{row_index}.{column_index % (10 ** decimal_places):0{decimal_places}d}")
    if normalized == "DATE":
        return datetime(2024, 1, 1) + timedelta(days=row_index, seconds=column_index)
    if normalized.startswith("TIMESTAMP"):
        return datetime(2024, 1, 1) + timedelta(days=row_index, seconds=column_index)
    if normalized in {"CHAR", "NCHAR", "VARCHAR", "VARCHAR2", "NVARCHAR2"}:
        if size < 1:
            raise ValueError(f"Invalid character width for {data_type}: {size}")
        return f"v{row_index:010d}_{column_index}"[:size]
    if normalized == "CLOB" or normalized == "NCLOB":
        return f"Synthetic validation row {row_index}, column {column_index}"
    if normalized == "BLOB":
        return f"synthetic-{row_index}-{column_index}".encode()
    if normalized == "RAW":
        return f"{row_index:08x}{column_index:08x}".encode()[:size]
    raise ValueError(f"Unsupported Oracle column type: {data_type}")


def seed_data(table: str, row_count: int, env_file: Path, dry_run: bool) -> None:
    if not TABLE_RE.fullmatch(table):
        raise ValueError("Use a simple table name in the current schema (no SQL expressions or schema prefixes).")
    if row_count < 1:
        raise ValueError("--rows must be at least 1")
    load_local_config(env_file)
    validate_local_credentials()
    dsn = os.environ.get("LOCAL_DB_DSN", "127.0.0.1:1521/FREEPDB1")
    _dsn_host(dsn)
    user = os.environ.get("LOCAL_DB_USER", "local_app")
    password = os.environ.get("LOCAL_DB_PASSWORD") or os.environ.get("LOCAL_ORACLE_PASSWORD")
    if not password:
        raise ValueError("Set LOCAL_DB_PASSWORD or LOCAL_ORACLE_PASSWORD in .local-db.env")
    if dry_run:
        print(f"Would seed {row_count} rows into {table.upper()} on local database {dsn}.")
        return
    try:
        import oracledb
    except ImportError as exc:
        raise RuntimeError(
            "Install the local database driver with "
            "`python -m pip install -r .agents/local-db/requirements.txt`."
        ) from exc

    connection = oracledb.connect(user=user, password=password, dsn=dsn)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT column_name, data_type, data_length, data_precision, data_scale,
                       nullable, data_default, identity_column
                FROM user_tab_columns
                WHERE table_name = :table_name
                ORDER BY column_id
                """,
                table_name=table.upper(),
            )
            metadata = [
                (name, data_type, data_length, precision, scale, nullable, default_value, identity)
                for name, data_type, data_length, precision, scale, nullable, default_value, identity
                in cursor.fetchall()
            ]
            if not metadata:
                raise ValueError(f"Table {table.upper()} was not found in the connected user's schema.")
            writable = [
                column for column in metadata
                if column[6] is None and column[7] != "YES"
            ]
            if not writable:
                raise ValueError(f"Table {table.upper()} has no writable columns.")
            column_names = [column[0] for column in writable]
            quoted_table = '"' + table.upper() + '"'
            quoted_columns = ", ".join('"' + name.replace('"', '""') + '"' for name in column_names)
            binds = ", ".join(f":{index + 1}" for index in range(len(column_names)))
            statement = f"INSERT INTO {quoted_table} ({quoted_columns}) VALUES ({binds})"
            values = []
            for row_index in range(1, row_count + 1):
                values.append(
                    tuple(
                        _row_value(data_type, data_length, precision, scale, row_index, column_index)
                        for column_index, (_, data_type, data_length, precision, scale, *_)
                        in enumerate(writable)
                    )
                )
            cursor.executemany(statement, values)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    print(f"Inserted {row_count} rows into {table.upper()}.")


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE, help=f"local-only DB env file (default: {DEFAULT_ENV_FILE.name})")
    commands = ap.add_subparsers(dest="command", required=True)
    start_parser = commands.add_parser("start", help="start Oracle Free with Docker Compose")
    start_parser.add_argument("--dry-run", action="store_true", help="show the local-only Docker command without running it")
    status_parser = commands.add_parser("status", help="show the local Oracle container status")
    status_parser.add_argument("--dry-run", action="store_true")
    execute = commands.add_parser("execute_script", help="execute a SQL script against local FREEPDB1")
    execute.add_argument("script", type=Path)
    execute.add_argument("--dry-run", action="store_true")
    seed = commands.add_parser("seed_data", help="insert synthetic rows into a local schema table")
    seed.add_argument("table", help="simple table name in the connected user's schema")
    seed.add_argument("--rows", type=int, default=100, help="rows to insert (default: 100)")
    seed.add_argument("--dry-run", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = parser()
    args = ap.parse_args(argv)
    try:
        if args.command == "start":
            start(args.env_file, args.dry_run)
        elif args.command == "status":
            status(args.env_file, args.dry_run)
        elif args.command == "execute_script":
            execute_script(args.script, args.env_file, args.dry_run)
        else:
            seed_data(args.table, args.rows, args.env_file, args.dry_run)
    except (FileNotFoundError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"local-db: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
