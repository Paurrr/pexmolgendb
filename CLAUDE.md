# 프로젝트: genviewer (저장소 gendb)

molgen(Cadence SKILL 스위트 `genMOLDB`)이 입력으로 받는 CSV의 내용을 공유 PostgreSQL 하나에 두고, PySide6 데스크톱 앱과 CLI(`genviewer`)로 편집·조회·내보내기한다. 서버 프로그램은 없다. 앱이 psycopg로 DB에 직접 붙는다.
이미 동작하는 코드를 하네스(`phases/`, `scripts/execute.py`)로 유지보수한다. **기능 추가·리팩터가 아니라 에러·버그만 고친다.** 구조 제안은 `docs/notes/architecture-proposal.md`, 고치지 않고 기록만 한 문제는 `docs/notes/known-issues.md` 에 있다.

## 기술 스택
- Python 3.13 (uv 관리, `src/` 레이아웃, 패키지 `genviewer`). `requires-python = ">=3.13,<3.14"`
- GUI: PySide6 **6.9.3 고정**. RHEL 8(glibc 2.28)에 설치되는 마지막 릴리스다(6.10+ 는 manylinux_2_34). 그래서 앱은 RHEL 7에 올라가지 않는다
- DB: `psycopg[binary,pool]` 3.3 (libpq 번들). 서버는 RHEL 7 + PostgreSQL 15, 최소 지원은 PG 10
- 그 밖: pandas 3 / openpyxl (CSV·xlsx), typer (CLI, `rich_markup_mode=None`)
- 테스트: pytest (DB 테스트는 `GENDB_TEST_PG_DSN`) / 린트: ruff (`ruff format` 은 쓰지 않는다)
- 형제 저장소가 기준이다: 배포·CLI는 `../Pexorche`, 서비스 계층(config/pool/user)은 fmserver, CSV 컬럼은 `../molgen`, 하네스는 `../pexqa`

## 아키텍처 규칙
- CRITICAL: `service/`, `scripts/`, `config/`, `utils/logs.py`, `utils/user.py`, `utils/exporter.py`, `cli.py`(모듈 수준)는 PySide6를 import하지 않는다. `cli.py` 는 서브커맨드가 없을 때만 `genviewer.main` 을 함수 안에서 import한다. 이유: `status` 등은 X가 없는 서버에서도 돌아야 하고, 테스트가 GUI 없이 돈다.
- CRITICAL: `scripts/init_db.py` 와 거기서 닿는 모듈(`service/schema.py`, `config/config.py`, `scripts/__init__.py`)은 Python 3.9에서 import되어야 한다. 이유: RHEL 7 서버에서 `PYTHONPATH=src python3.9 -m genviewer.scripts.init_db` 로 소스에서 돌린다. 런타임에 평가되는 `X | Y`, `match`, `zip(strict=)`, `dataclass(slots=/kw_only=)`, `tomllib` 금지(`from __future__ import annotations` 아래의 주석은 괜찮다).
- CRITICAL: SQL은 PostgreSQL 10~15에서 돌아야 한다. 식별자(테이블·컬럼 이름)는 `psycopg.sql` 로 조립하고 `service/schema.py` 의 `TABLE_COLUMNS` 에 있는 이름만 쓴다. 값은 항상 바인드 파라미터로 넘긴다.
- CRITICAL: 쓰기는 `device.version` 낙관적 잠금(충돌 시 `StaleWriteError`)과 `change_log` 기록을 **같은 트랜잭션**에서 한다(`repo/audit.write(cur, …)`). 화면에 들고 있지 않은 device는 절대 지우지 않는다(명시적으로 지운 id만 삭제).
- CRITICAL: 비밀번호를 화면·로그·argv에 남기지 않는다. 예외는 `str(exc)` 대신 `service.errors.user_message(exc)`, DSN·접속 문자열은 `utils.logs.scrub()` 을 거친다. 이유: psycopg 접속 예외에는 conninfo가 통째로 들어 있다.
- CRITICAL: `config/tab_config.json` 이 테이블 DDL·화면 탭·CSV import/export의 단일 원본이다. 키 구조를 바꾸지 않는다. 컬럼 목록과 `parse` 는 `../molgen/genMOLDB_config.il` 의 `pexGenDB_GenDev_Get_Header_Type()` 과 맞춘다.
- GUI 스레드에서 DB를 기다리지 않는다. 새 DB 호출은 `utils/background.py` 의 `run_blocking`(결과가 필요할 때) 또는 `Task`(비동기)로 돌린다. 워커 스레드에서 위젯을 만지지 않는다.
- 자동으로 다시 읽지 않는다. 남이 바꾼 것은 배너로 알리고, 언제 읽을지는 사용자가 정한다(편집 중 내용이 말없이 사라지면 안 된다).
- 파일 I/O는 항상 `encoding="utf-8"`. 개발 PC는 Windows(cp949)이고 운영은 RHEL 8이다.
- 새 런타임 의존성은 RHEL 8용 `manylinux_2_28` 이하 휠이 있어야 한다(`uv pip compile pyproject.toml --python-version 3.13 --python-platform x86_64-manylinux_2_28`).
- 사용자에게 보이는 문구는 지금 관례를 따른다(대화상자 제목은 영어, 본문·CLI 출력·주석은 한국어). 버그 수정 중에 기존 문구를 바꾸지 않는다.

## 개발 프로세스
- CRITICAL: 새 기능 구현 시 반드시 테스트를 먼저 작성하고, 테스트가 통과하는 구현을 작성할 것 (TDD)
- CRITICAL: 버그 수정도 실패하는 테스트로 먼저 재현한다. 재현되지 않으면 고치지 않는다. 분석·리뷰 에이전트의 지적은 주장이다.
- 커밋 메시지는 conventional commits 형식을 따를 것 (feat:, fix:, docs:, refactor:, test:, chore:). 설명은 한국어로 써도 된다.
- 파일 삭제는 `git rm` 또는 Python 코드로 한다 (`rm -rf` 는 훅이 차단한다).
- 셸 스크립트(`tools/*.sh`)는 LF(`.gitattributes`)와 실행 비트(`git update-index --chmod=+x <file>`)로 커밋한다. 이유: Windows는 실행 비트를 잃고 CRLF면 서버에서 `bad interpreter` 가 난다.
- 루트 `scripts/` 는 하네스(execute.py)이고 `src/genviewer/scripts/` 는 관리 도구(init_db, import_sqlite)다. 헷갈리지 않는다.

## 테스트 관례
- DB가 필요한 테스트는 `tests/conftest.py` 의 `pg_dsn`/`db` fixture를 쓴다. `GENDB_TEST_PG_DSN` 은 **관리자 DSN**이어야 한다(fixture가 `gendb_test_<pid>` 데이터베이스를 만들고 지운다. 권한 테스트는 CREATE ROLE까지 한다). 없으면 skip된다. 개발 PC 기준선(DB 없음, 2026-10-17)은 Git Bash에서 99 passed / 86 skipped다. `sh` 가 PATH에 없는 셸(PowerShell)에서는 deploy.sh 테스트 11개가 더 skip되어 88 / 97이 된다.
- POSIX 권한·심볼릭 링크 테스트는 `posix_only` 로 Windows에서 skip된다. 버그 재현(RED)은 Windows에서 도는 테스트로 보인다.
- 셸 스크립트는 stub 명령을 PATH 앞에 두고 실제로 실행해서 테스트한다(`tests/test_deploy_sh.py`). 텍스트 토큰 검사만으로 끝내지 않는다.
- Qt 테스트는 `QT_QPA_PLATFORM=offscreen` 으로 돈다(`tests/test_background.py`). 예상하지 않은 모달 대화상자가 테스트를 멈추게 두지 않는다.
- 외부 의존(Virtuoso 소켓, 실제 서버)은 테스트에서 붙지 않는다. 접속 실패 경로는 닫힌 포트(`127.0.0.1:1`)로 만든다.

## 명령어
```bash
uv sync                                   # 의존성 설치 (dev 그룹 포함)
uv run ruff check src tests               # 린트
uv run pytest -q                          # 전체 테스트 (DB 테스트는 skip)
GENDB_TEST_PG_DSN="postgresql://<user>@127.0.0.1:55433/postgres" uv run pytest -q   # DB 테스트까지
uv run genviewer                          # GUI
uv run genviewer status                   # 접속·스키마 진단
uv run genviewer-init-db --dry-run        # 실행될 DDL만 본다
sh -n tools/deploy.sh tools/initdb.sh     # 셸 문법 검사 (Windows는 Git Bash sh)
uv run python -X utf8 scripts/execute.py <phase>   # 하네스 phase 실행 (-X utf8: cp949 콘솔 대응)
```
