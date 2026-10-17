# 프로젝트: genviewer (저장소 gendb)

molgen(Cadence SKILL 스위트 `genMOLDB`)이 입력으로 받는 CSV의 내용을 공유 PostgreSQL 하나에 두고, PySide6 데스크톱 앱과 CLI(`genviewer`)로 편집·조회·내보내기한다. 서버 프로그램은 없다. 앱이 psycopg로 DB에 직접 붙는다.
이미 동작하는 코드를 하네스(`phases/`, `scripts/execute.py`)로 유지보수한다. **기능 추가·리팩터가 아니라 에러·버그만 고친다.** 구조 제안은 `docs/notes/architecture-proposal.md`, 고치지 않고 기록만 한 문제는 `docs/notes/known-issues.md` 에 있다.

## 기술 스택
- Python 3.13 (uv 관리, `src/` 레이아웃, 패키지 `genviewer`). `requires-python = ">=3.13,<3.14"`
- GUI: PySide6 **6.9.3 고정**. RHEL 8(glibc 2.28)에 설치되는 마지막 릴리스다(6.10+ 는 manylinux_2_34). 그래서 앱은 RHEL 7에 올라가지 않는다
- DB: `psycopg[binary,pool]` 3.3 (libpq 번들). 서버는 RHEL 7 + PostgreSQL 15, 최소 지원은 PG 10
- 그 밖: pandas 3 / openpyxl (CSV·xlsx), typer (CLI, `rich_markup_mode=None`)
- 테스트: pytest (DB 테스트는 `GENDB_TEST_PG_DSN`), pytest-qt(GUI, `tests/gui/`, dev 그룹만) / 린트: ruff (`ruff format` 은 쓰지 않는다)
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
- 루트 `scripts/` 는 하네스(execute.py)이고 `src/genviewer/scripts/` 는 관리 도구(init_db)다. 헷갈리지 않는다.

## 테스트 관례
- DB가 필요한 테스트는 `tests/conftest.py` 의 `pg_dsn`/`db` fixture를 쓴다. `GENDB_TEST_PG_DSN` 은 **관리자 DSN**이어야 한다(fixture가 `gendb_test_<pid>` 데이터베이스를 만들고 지운다. 권한 테스트는 CREATE ROLE까지 한다). 없으면 skip된다. 개발 PC 기준선(DB 없음, phase 5 완료 후 2026-10-17)은 Git Bash에서 425 passed / 119 skipped / 1 xfailed다. `sh` 가 PATH에 없는 셸(PowerShell)에서는 셸 스크립트 테스트 20개(`test_deploy_sh.py`, `test_initdb_sh.py`)가 더 skip되어 405 / 139 / 1이 된다. DB를 붙이면 535 passed / 9 skipped / 1 xfailed(Windows 권한 테스트만 skip)다.
- 재현했지만 고치지 않기로 한 버그의 테스트는 `pytest.mark.xfail(strict=True, reason="K<번호>: …")` 로 남기고 `docs/notes/known-issues.md` 의 그 항목에 테스트 이름을 적는다(지금은 K17 하나). 고치면 XPASS로 실패하므로 그때 xfail을 뗀다.
- POSIX 권한·심볼릭 링크 테스트는 `posix_only` 로 Windows에서 skip된다. 버그 재현(RED)은 Windows에서 도는 테스트로 보인다.
- 셸 스크립트는 stub 명령을 PATH 앞(initdb.sh 는 `PGBIN`)에 두고 실제로 실행해서 테스트한다(`tests/test_deploy_sh.py`, `tests/test_initdb_sh.py`). 텍스트 토큰 검사만으로 끝내지 않는다.
- GUI 테스트는 `tests/gui/` 에 둔다(pytest-qt, `qt_api = "pyside6"`). `tests/gui/conftest.py` 가 PySide6 import 전에 `QT_QPA_PLATFORM=offscreen` 을 둔다. `tests/test_background.py` 는 자기 `qapp` fixture로 따로 돈다.
- 모달은 autouse `dialogs` fixture가 대신한다. 예/아니오는 `dialogs.answer_question(...)`, 저장 충돌은 `dialogs.answer_conflict(RELOAD|OVERWRITE|CANCEL)` 로 미리 답하고, 뜬 문구는 `dialogs.shown` 의 `(kind, title, text)` 로 단언한다. 답하지 않은 모달·파일 대화상자·메뉴는 `AssertionError` 이고 앱이 삼켜도 teardown에서 실패한다(쓰지 않은 답도). 이유: `@report` 가 `AssertionError` 까지 알림으로 바꾼다.
- GUI 테스트 헬퍼는 `tests/gui_support/` 에 두고 `from gui_support.dialogs import ...` 처럼 import한다(`pythonpath = ["tests"]`). conftest나 다른 테스트 모듈은 import하지 않는다. "아무 일도 일어나지 않음"은 고정 대기(`qtbot.wait`) 대신 fake가 기록한 호출이나 컨트롤러 상태를 `qtbot.waitUntil` 로 기다린 뒤 단언한다. `waitUntil` 콜백은 bool을 돌려준다(`lambda: fake.sent != []`). 리스트를 돌려주면 pytest-qt가 `ValueError` 를 낸다.
- GUI 테스트의 DB는 `tests/gui_support/fakes.py` 의 `FakeStore`/`Fake*Repository` 다. 의미는 실제 repo가 기준이고 `tests/gui/test_fake_repo_contract.py` 가 같은 기대값을 가짜와 실제 PostgreSQL(`GENDB_TEST_PG_DSN`)에 돌려 고정한다. `service/repo/` 의 의미를 바꾸는 step은 가짜와 contract test도 같이 고친다.
- 컨트롤러 테스트는 `tests/gui/conftest.py` 의 `store`(시드: sf2p/nfet_a·nfet_b, sf4u/pfet_a, 탭 InstTerm·InstSchParam), `device_tab_ctrl`, `main_window` fixture와 `from gui_support.helpers import select_process, select_device_row, edit_device_cell, edit_tab_cell` 로 쓴다. 장애는 `store.fail_next(메서드, 예외)`, 남의 변경은 `store.touch_device`/`store.remove_device`, 일어난 일은 `store.calls`/`store.calls_of` 로 본다. actor는 `GENDB_APP_USER=tester` 다.
- 첫 DB 접속은 `DeviceTabController` 생성자가 `QTimer.singleShot(0)` 으로 예약한다. 컨트롤러나 창을 직접 만드는 테스트는 `qtbot.waitUntil(lambda: ctrl.connected is not None)` 로 기다린 뒤 단언한다(두 fixture는 이미 기다린다). 창 닫기는 `MainWindowController` 의 이벤트 필터(저장 확인)를 거치고, pytest-qt는 fixture 정리보다 **먼저** 등록한 창을 닫는다. 그래서 편집을 남길 수 있는 창은 `qtbot.addWidget(ui, before_close_func=…)` 에서 `shutdown()` 으로 필터를 먼저 뗀다(`main_window` fixture가 그렇게 한다).
- 외부 의존(Virtuoso 소켓, 실제 서버)은 테스트에서 붙지 않는다. Virtuoso 소켓은 `tests/gui_support/fakes.py` 의 `FakeVirtuosoClient` 로 대신한다. 접속 실패 경로는 닫힌 포트(`127.0.0.1:1`)로 만든다.

## 명령어
```bash
uv sync                                   # 의존성 설치 (dev 그룹 포함)
uv run ruff check src tests               # 린트
uv run pytest -q                          # 전체 테스트 (DB 테스트는 skip)
GENDB_TEST_PG_DSN="postgresql://<user>@127.0.0.1:55433/postgres" uv run pytest -q   # DB 테스트까지
uv run pytest tests/gui -q                # GUI 테스트만 (pytest-qt, offscreen)
uv run genviewer                          # GUI
uv run genviewer status                   # 접속·스키마 진단
uv run genviewer-init-db --dry-run        # 실행될 DDL만 본다
sh -n tools/deploy.sh && sh -n tools/initdb.sh   # 셸 문법 검사 (Windows는 Git Bash sh). 파일마다 따로: `sh -n a b` 는 a 만 본다
uv run python -X utf8 scripts/execute.py <phase>   # 하네스 phase 실행 (-X utf8: cp949 콘솔 대응)
```
