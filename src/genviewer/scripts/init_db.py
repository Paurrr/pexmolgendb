#!/usr/bin/env python
"""molgen PostgreSQL 프로비저닝.

fmserver/init_db.py 를 따른다: 선언적 Plan/Step, 서버 단계(CREATE ROLE/DATABASE,
autocommit)와 DB 단계(스키마 DDL, 트랜잭션) 분리, skip_if 로 멱등성 확보,
그리고 psycopg 도 살아 있는 서버도 없이 도는 --dry-run.

  # 무엇을 할지만 본다 (접속 안 함)
  uv run python -m genviewer.scripts.init_db --dry-run

  # 기존 DB 에 스키마만 만든다
  uv run python -m genviewer.scripts.init_db --dsn "$MOLGEN_PG_DSN"

  # role 과 database 부터 만든다 (관리자 DSN 으로)
  uv run python -m genviewer.scripts.init_db --dsn "postgresql://postgres@host:5433/postgres" \
      --create-role molgen --create-database molgen

비밀번호는 MOLGEN_INIT_PASSWORD 환경변수나 프롬프트에서만 받는다.
argv 로는 절대 받지 않는다 — ps 에 남는다.
"""

import argparse
import getpass
import os
from collections.abc import Callable
from dataclasses import dataclass

from genviewer.service import schema


@dataclass
class Step:
    label: str
    sql: object  # str | psycopg.sql.Composable
    conn: str  # "server" (autocommit) | "db" (트랜잭션)
    params: tuple | None = None
    skip_if: Callable | None = None


def build_plan(create_role: str, create_database: str, owner: str) -> list[Step]:
    steps: list[Step] = []

    if create_role:
        steps.append(
            Step(
                label=f"CREATE ROLE {create_role}",
                sql=f'CREATE ROLE "{create_role}" LOGIN PASSWORD %s',
                conn="server",
                params=("<password>",),
                skip_if=lambda cur: bool(
                    cur.execute(
                        "SELECT 1 FROM pg_roles WHERE rolname = %s", (create_role,)
                    ).fetchone()
                ),
            )
        )

    if create_database:
        own = f' OWNER "{owner}"' if owner else ""
        steps.append(
            Step(
                label=f"CREATE DATABASE {create_database}{own}",
                # CREATE DATABASE 는 파라미터 바인딩이 안 되고 트랜잭션 안에서도 못 돈다.
                sql=f'CREATE DATABASE "{create_database}"{own}',
                conn="server",
                skip_if=lambda cur: bool(
                    cur.execute(
                        "SELECT 1 FROM pg_database WHERE datname = %s",
                        (create_database,),
                    ).fetchone()
                ),
            )
        )

    for stmt in schema.postgres_all_ddl():
        steps.append(Step(label=_first_line(stmt), sql=stmt, conn="db"))

    return steps


def _first_line(stmt) -> str:
    text = stmt.as_string() if hasattr(stmt, "as_string") else str(stmt)
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line if len(line) <= 88 else line[:85] + "..."
    return "<empty>"


def print_plan(steps: list[Step]) -> None:
    print(f"{len(steps)} steps\n")
    for i, st in enumerate(steps, 1):
        print(f"{i:3}. [{st.conn:6}] {st.label}")


def run_plan(steps: list[Step], dsn: str, target_db: str, password: str) -> int:
    import psycopg

    server_steps = [s for s in steps if s.conn == "server"]
    db_steps = [s for s in steps if s.conn == "db"]

    if server_steps:
        with psycopg.connect(dsn, autocommit=True, application_name="molgen-init-db") as con:
            with con.cursor() as cur:
                for st in server_steps:
                    if st.skip_if is not None and st.skip_if(cur):
                        print(f"skip  {st.label} (이미 있음)")
                        continue
                    params = (password,) if st.params else None
                    cur.execute(st.sql, params)
                    print(f"ok    {st.label}")

    target_dsn = dsn
    if target_db:
        # DSN 의 나머지는 그대로 두고 dbname 만 바꾼다.
        info = psycopg.conninfo.conninfo_to_dict(dsn)
        info["dbname"] = target_db
        target_dsn = psycopg.conninfo.make_conninfo(**info)

    with psycopg.connect(target_dsn, application_name="molgen-init-db") as con:
        with con.cursor() as cur:
            for st in db_steps:
                cur.execute(st.sql)
                print(f"ok    {st.label}")
        con.commit()

    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="molgen PostgreSQL 프로비저닝")
    ap.add_argument("--dsn", default=os.environ.get("MOLGEN_PG_DSN", ""))
    ap.add_argument("--create-role", default="", help="이 이름으로 LOGIN role 생성")
    ap.add_argument("--create-database", default="", help="이 이름으로 database 생성")
    ap.add_argument("--owner", default="", help="생성할 database 의 owner")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="실행할 단계만 출력한다. 접속하지 않는다.",
    )
    args = ap.parse_args()

    steps = build_plan(args.create_role, args.create_database, args.owner)

    if args.dry_run:
        print_plan(steps)
        return 0

    if not args.dsn:
        ap.error("--dsn 또는 MOLGEN_PG_DSN 이 필요하다")

    password = ""
    if args.create_role:
        password = os.environ.get("MOLGEN_INIT_PASSWORD", "")
        if not password:
            password = getpass.getpass(f"'{args.create_role}' role 의 비밀번호: ")
        if not password:
            ap.error("role 을 만들려면 비밀번호가 필요하다")

    return run_plan(steps, args.dsn, args.create_database, password)


if __name__ == "__main__":
    raise SystemExit(main())
