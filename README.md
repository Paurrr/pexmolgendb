# molgenviewer

옆 디렉토리 `molgen`(Cadence SKILL 스위트 `genMOLDB`)이 입력으로 받는 CSV 를
만들고 관리하는 PySide6 데스크톱 앱.

데이터는 공유 PostgreSQL 한 곳에 있다. 예전처럼 각자 `.sqlite` 파일을 들고
다니지 않는다.

## 준비

```sh
uv sync
```

## 서버 준비 (한 번만)

```sh
# 클러스터 생성 + 기동 (fmserver 는 55432, 여기는 55433)
PGBIN="/c/Program Files/PostgreSQL/18/bin" ./tools/initdb.sh   # 윈도우
./tools/initdb.sh                                              # 리눅스

# 스키마 생성. 먼저 --dry-run 으로 무엇이 실행될지 볼 수 있다 (접속 안 함).
uv run python scripts/init_db.py --dry-run
uv run python scripts/init_db.py --dsn "postgresql://<user>@127.0.0.1:55433/molgen"
```

윈도우 Git Bash 에서는 `pg_ctl start` 가 셸에 매여 프롬프트가 돌아오지 않는다.
`SKIP_START=1` 로 두고 PowerShell `Start-Process` 로 따로 띄울 것.

비밀번호는 DSN 에 넣지 말고 libpq 의 `~/.pgpass`
(윈도우는 `%APPDATA%\postgresql\pgpass.conf`)를 쓴다. psycopg 가 번들한 libpq 가
자동으로 읽는다.

## 실행

```sh
export MOLGEN_PG_DSN="postgresql://<user>@127.0.0.1:55433/molgen"
uv run python main.py

# 또는
uv run python main.py --dsn "postgresql://..." --host <virtuoso-host>
```

접속 정보는 메뉴의 **Database → Connect...** 에서도 바꿀 수 있다.

> 메인 툴바의 `Server` / `Port` / `Connect` 는 **Virtuoso 소켓**이지
> 데이터베이스가 아니다. 둘은 별개다.

## 기존 .sqlite 파일 옮기기

```sh
# 무엇이 들어갈지 먼저 본다
uv run python scripts/import_sqlite.py --sqlite mine.sqlite --dry-run

# 여러 사람 파일을 각자 이름으로 구분해서 넣는다 (초기 대량 이관에 권장)
uv run python scripts/import_sqlite.py --sqlite mine.sqlite --on-conflict rename
```

`--on-conflict` 는 같은 이름의 process 가 이미 있을 때의 정책이다.
`fail`(기본) / `rename` / `merge` / `skip`.

## 동시 편집

여러 명이 같은 DB 를 동시에 편집한다. 저장할 때 다른 사람이 먼저 바꾼 것이
있으면 **다시 읽기 / 덮어쓰기 / 취소** 를 묻는다. 내가 화면에 안 들고 있는
device 는 절대 지워지지 않는다 — 명시적으로 지운 것만 삭제된다.

## 개발

```sh
uv run ruff check .
uv run pytest                     # DB 필요한 테스트는 skip 된다

# DB 를 붙이면 전부 돈다. 테스트용 데이터베이스를 만들고 끝나면 지운다.
MOLGEN_TEST_PG_DSN="postgresql://<user>@127.0.0.1:55433/postgres" uv run pytest
```

## 환경변수

| | |
|---|---|
| `MOLGEN_PG_DSN` | 접속 문자열 (필수, `--dsn` 으로도 지정 가능) |
| `MOLGEN_APP_USER` | `updated_by` 에 기록할 이름 (기본: 로그인 계정) |
| `MOLGEN_PG_POOL_MIN` / `_MAX` | 커넥션 풀 크기 (기본 1 / 4) |
| `MOLGEN_PG_CONNECT_TIMEOUT` | 접속 타임아웃 초 (기본 5) |
| `MOLGEN_PG_LOCK_TIMEOUT_MS` | 행 잠금 대기 한도 (기본 5000) |
| `MOLGEN_PG_STATEMENT_TIMEOUT_MS` | 쿼리 한도 (기본 15000) |
| `MOLGEN_TEST_PG_DSN` | 테스트용 관리 DSN |

## 배포 시 주의 — RHEL 8

PySide6 는 **6.9.3** 에 고정돼 있다. 이게 `manylinux_2_28` 휠을 내는 마지막
릴리스이고, RHEL 8 의 glibc 가 2.28 이다. 6.10 부터는 `manylinux_2_34` 라서
RHEL 9 이상에서만 설치된다.

그 휠이 `Requires-Python: <3.14` 이므로 인터프리터도 **3.13** 으로 고정된다.
`.python-version` 과 `requires-python` 이 그렇게 맞춰져 있다. 나머지 의존성은
RHEL 8 에서 더 조이지 않는다 — pandas/numpy 는 `manylinux_2_28`,
psycopg-binary 는 `manylinux2014`(glibc 2.17) 휠이다.

올리기 전에 교차 확인:

```sh
uv pip compile pyproject.toml --python-version 3.13     --python-platform x86_64-manylinux_2_28
```

배포 호스트에 Python 3.13 이 없으면 `uv python install 3.13` 이 필요하고,
이건 네트워크나 미리 채워둔 `UV_PYTHON_INSTALL_DIR` 를 쓴다.
