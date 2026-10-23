#!/usr/bin/env python
"""PostgreSQL 프로비저닝.

fmserver/init_db.py 를 따른다: 선언적 Plan/Step, 서버 단계(CREATE ROLE/DATABASE,
autocommit)와 DB 단계(스키마 DDL, 트랜잭션) 분리, skip_if 로 멱등성 확보,
그리고 살아 있는 서버 없이 도는 --dry-run.

  # 무엇을 할지만 본다 (접속 안 함)
  uv run python -m genviewer.scripts.init_db --dry-run

  # 기존 DB 에 스키마만 만든다
  uv run python -m genviewer.scripts.init_db --dsn "$GENDB_PG_DSN"

  # role 과 database 부터 만든다 (관리자 DSN 으로)
  uv run python -m genviewer.scripts.init_db --dsn "postgresql://postgres@host:5433/postgres" \
      --create-role molgen --create-database molgen

  # 공유 서버: 소유자로 붙어 스키마를 만들고, 앱 role 에게 DML 권한을 준다
  uv run python -m genviewer.scripts.init_db --dsn "$GENDB_PG_DSN" --app-role molgen_app

비밀번호는 GENDB_INIT_PASSWORD 환경변수나 프롬프트에서만 받는다.
argv 로는 절대 받지 않는다 - ps 에 남는다.
"""

# 서버(RHEL 7)의 파이썬은 3.9 다. 이 도구는 GUI 를 import 하지 않으므로 거기서
# 돌릴 수 있는데, X | None (3.10+) 이 평가되는 자리에 있으면 import 조차 안 된다.
# 이 한 줄이 애노테이션을 문자열로 만들어 평가 자체를 없앤다. 런타임 동작은 같다.
from __future__ import annotations

import argparse
import getpass
import os
from collections.abc import Callable
from dataclasses import dataclass

from genviewer.scripts import survive_console_encoding
from genviewer.service import schema


@dataclass
class Step:
    label: str
    sql: object  # str | psycopg.sql.Composable
    conn: str  # "server" (autocommit) | "db" (트랜잭션)
    params: tuple | None = None
    skip_if: Callable | None = None


def build_plan(
    create_role: str, create_database: str, owner: str, app_role: str = ""
) -> list[Step]:
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

    # DDL 보다 먼저다. run_plan 은 관리자 DSN 에서 dbname 만 바꿔 붙으므로
    # (114-119행) 그대로 두면 테이블 주인이 --owner 가 아니라 '접속한 계정'이
    # 된다. 그러면 아래 ALTER DEFAULT PRIVILEGES 가 정작 테이블을 만들지 않는
    # role 에 붙어서, 나중에 탭을 추가할 때 권한이 조용히 안 따라간다.
    if owner:
        steps.append(
            Step(
                label=f"SET ROLE {owner}",
                sql=f'SET ROLE "{owner}"',
                conn="db",
            )
        )

    for stmt in schema.postgres_all_ddl():
        steps.append(Step(label=_first_line(stmt), sql=stmt, conn="db"))

    # DDL 뒤에 와야 한다. ON ALL TABLES 는 그 시점에 있는 테이블만 본다.
    if app_role:
        steps.extend(_grant_steps(app_role, create_database))

    return steps


# 앱 role 에게는 DML 만 준다. 모두가 같은 role 로 접속하므로(utils/user.py 참고)
# DDL 권한까지 주면 아무나 실수로 DROP TABLE 을 할 수 있다.
_APP_PRIVILEGES = "SELECT, INSERT, UPDATE, DELETE"


def _grant_steps(app_role: str, create_database: str) -> list[Step]:
    """공유 앱 role 이 테이블을 실제로 쓸 수 있게 한다.

    GRANT 는 그 자체로 멱등하다 - 같은 권한을 다시 줘도 아무 일도 일어나지
    않는다. 그래서 다른 Step 들과 달리 skip_if 를 달지 않는다.

    시퀀스에는 아무것도 주지 않는다. id 컬럼이 전부 GENERATED AS IDENTITY 라
    serial 과 달리 테이블 INSERT 권한만으로 충분하다.
    """
    steps: list[Step] = []

    # DB 이름은 --create-database 로만 알 수 있다 (--dry-run 은 --dsn 없이도
    # 돌아야 해서 DSN 을 파싱할 수 없다). 기존 DB 에 얹는 경로에서는 어차피
    # no-op 이다 - PostgreSQL 15 가 회수한 것은 public '스키마' 의 CREATE 이지
    # 데이터베이스 CONNECT 가 아니라서 PUBLIC 이 여전히 CONNECT 를 갖는다.
    if create_database:
        steps.append(
            Step(
                label=f"GRANT CONNECT ON DATABASE {create_database} TO {app_role}",
                sql=f'GRANT CONNECT ON DATABASE "{create_database}" TO "{app_role}"',
                conn="db",
            )
        )

    steps.append(
        Step(
            label=f"GRANT USAGE ON SCHEMA public TO {app_role}",
            sql=f'GRANT USAGE ON SCHEMA public TO "{app_role}"',
            conn="db",
        )
    )
    steps.append(
        Step(
            label=f"GRANT {_APP_PRIVILEGES} ON ALL TABLES TO {app_role}",
            sql=(
                f"GRANT {_APP_PRIVILEGES} ON ALL TABLES IN SCHEMA public "
                f'TO "{app_role}"'
            ),
            conn="db",
        )
    )

    # 위 문장은 '지금 있는' 테이블만 처리한다. 이건 앞으로 생길 테이블용이다.
    # 탭을 하나 추가하면 테이블이 하나 늘고 init_db 를 다시 돌리게 되는데
    # (README 참고), 이게 없으면 새로 생긴 탭만 조용히 권한 오류가 난다.
    #
    # FOR ROLE 을 안 쓴다. 기본 권한은 '그 role 이 만드는' 객체에만 붙는데,
    # 위의 SET ROLE 덕분에 지금 세션이 곧 테이블을 만드는 role 이다.
    steps.append(
        Step(
            label=f"ALTER DEFAULT PRIVILEGES IN SCHEMA public -> {app_role}",
            sql=(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                f'GRANT {_APP_PRIVILEGES} ON TABLES TO "{app_role}"'
            ),
            conn="db",
        )
    )
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


def _with_password(statement: str, password: str):
    """CREATE ROLE 문에 비밀번호를 끼워 넣는다.

    서버 측 파라미터 바인딩을 쓸 수 없다. CREATE ROLE 은 유틸리티 문이라
    PostgreSQL 이 "syntax error at or near $1" 로 거절한다. 그래서 psycopg 가
    이스케이프한 리터럴로 클라이언트에서 합쳐 보낸다.

    평문은 Step 에 담지 않고 여기서만 만든다 - build_plan 이 만든 plan 은
    --dry-run 이 통째로 출력하기 때문이다. 다만 서버가 log_statement=ddl 이면
    이 문장은 로그에 남는다. 그건 CREATE ROLE 의 성질이지 여기서 못 피한다.
    """
    from psycopg import sql

    head, _, tail = statement.partition("%s")
    return sql.SQL("{}{}{}").format(
        sql.SQL(head), sql.Literal(password), sql.SQL(tail)
    )


def run_plan(steps: list[Step], dsn: str, target_db: str, password: str) -> int:
    import psycopg

    server_steps = [s for s in steps if s.conn == "server"]
    db_steps = [s for s in steps if s.conn == "db"]

    if server_steps:
        with psycopg.connect(dsn, autocommit=True, application_name="genviewer-init-db") as con:
            with con.cursor() as cur:
                for st in server_steps:
                    if st.skip_if is not None and st.skip_if(cur):
                        print(f"skip  {st.label} (already exists)")
                        continue
                    if st.params:
                        cur.execute(_with_password(st.sql, password))
                    else:
                        cur.execute(st.sql)
                    print(f"ok    {st.label}")

    target_dsn = dsn
    if target_db:
        # DSN 의 나머지는 그대로 두고 dbname 만 바꾼다.
        info = psycopg.conninfo.conninfo_to_dict(dsn)
        info["dbname"] = target_db
        target_dsn = psycopg.conninfo.make_conninfo(**info)

    with psycopg.connect(target_dsn, application_name="genviewer-init-db") as con:
        with con.cursor() as cur:
            for st in db_steps:
                cur.execute(st.sql)
                print(f"ok    {st.label}")
        con.commit()

    return 0


def main() -> int:
    survive_console_encoding()
    ap = argparse.ArgumentParser(description="PostgreSQL provisioning")
    ap.add_argument("--dsn", default=os.environ.get("GENDB_PG_DSN", ""))
    ap.add_argument("--create-role", default="", help="Create a LOGIN role with this name.")
    ap.add_argument("--create-database", default="", help="Create a database with this name.")
    ap.add_argument("--owner", default="", help="Owner of the database to create.")
    ap.add_argument(
        "--app-role",
        default="",
        help="Grant table DML privileges to this role (the login everyone shares).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print the steps to run. Does not connect.",
    )
    args = ap.parse_args()

    steps = build_plan(
        args.create_role, args.create_database, args.owner, args.app_role
    )

    if args.dry_run:
        print_plan(steps)
        return 0

    if not args.dsn:
        ap.error("--dsn or GENDB_PG_DSN is required")

    password = ""
    if args.create_role:
        password = os.environ.get("GENDB_INIT_PASSWORD", "")
        if not password:
            password = getpass.getpass(f"Password for role '{args.create_role}': ")
        if not password:
            ap.error("a password is required to create the role")

    return run_plan(steps, args.dsn, args.create_database, password)


if __name__ == "__main__":
    raise SystemExit(main())
