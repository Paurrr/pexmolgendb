# 프로젝트: genviewer (저장소 gendb)

molgen(Cadence SKILL 스위트 `genMOLDB`)이 입력으로 받는 CSV의 내용을 공유 PostgreSQL 하나에 두고, PySide6 데스크톱 앱과 CLI(`genviewer`)로 편집·조회·내보내기한다. 서버 프로그램은 없다. 앱이 psycopg로 DB에 직접 붙는다.
이미 동작하는 코드를 하네스(`phases/`, `scripts/execute.py`)로 유지보수한다. **기능 추가·리팩터가 아니라 에러·버그만 고친다.** 구조 제안은 `docs/notes/architecture-proposal.md`, 고치지 않고 기록만 한 문제는 `docs/notes/known-issues.md` 에 있다.

## 기술 스택
- GUI: PySide6 **6.9.3 고정**. RHEL 8(glibc 2.28)에 설치되는 마지막 릴리스다(6.10+ 는 manylinux_2_34). 그래서 앱은 RHEL 7에 올라가지 않는다
- DB: 서버는 RHEL 7 + PostgreSQL 15, 최소 지원은 PG 10
- 린트: ruff. `ruff format` 은 쓰지 않는다
- 형제 저장소가 기준이다: 배포·CLI는 `../Pexorche`, 서비스 계층(config/pool/user)은 fmserver, CSV 컬럼은 `../molgen`, 하네스는 `../pexqa`

## 아키텍처 규칙
- CRITICAL: `service/`, `scripts/`, `config/`, `utils/logs.py`, `utils/user.py`, `utils/exporter.py`, `cli.py`(모듈 수준)는 PySide6를 import하지 않는다. `cli.py` 는 서브커맨드가 없을 때만 `genviewer.main` 을 함수(`root`) 안에서 import한다. 이유: `status` 등은 X가 없는 서버에서도 돌아야 하고, 테스트가 GUI 없이 돈다. `tests/test_boundaries.py` 가 지킨다(함수 안 import 포함). 새 Qt 없는 `utils/` 파일은 그 테스트의 `QT_FREE_MODULES` 에 더한다.
- CRITICAL: `scripts/init_db.py` 와 거기서 닿는 모듈(`service/schema.py`, `config/config.py`, `scripts/__init__.py`)은 Python 3.9에서 import되어야 한다. 이유: RHEL 7 서버에서 `PYTHONPATH=src python3.9 -m genviewer.scripts.init_db` 로 소스에서 돌린다. 런타임에 평가되는 `X | Y`, `match`, `zip(strict=)`, `dataclass(slots=/kw_only=)`, `tomllib` 금지(`from __future__ import annotations` 아래의 주석은 괜찮다). `tests/test_py39_compat.py` 가 닿는 모듈을 import를 따라가며 찾아 정적으로 검사한다.
- CRITICAL: SQL은 PostgreSQL 10~15에서 돌아야 한다. 식별자(테이블·컬럼 이름)는 `psycopg.sql` 로 조립하고 `service/schema.py` 의 `TABLE_COLUMNS` 에 있는 이름만 쓴다. 값은 항상 바인드 파라미터로 넘긴다.
- CRITICAL: 쓰기는 `device.version` 낙관적 잠금(충돌 시 `StaleWriteError`)과 `change_log` 기록을 **같은 트랜잭션**에서 한다(`repo/audit.write(cur, …)`). 화면에 들고 있지 않은 device는 절대 지우지 않는다(명시적으로 지운 id만 삭제).
- CRITICAL: 비밀번호를 화면·로그·argv에 남기지 않는다. 예외는 `str(exc)` 대신 `service.errors.user_message(exc)`, DSN·접속 문자열은 `utils.logs.scrub()` 을 거친다. 이유: psycopg 접속 예외에는 conninfo가 통째로 들어 있다.
- CRITICAL: `config/tab_config.json` 이 테이블 DDL·화면 탭·CSV import/export의 단일 원본이다. 키 구조를 바꾸지 않는다. 컬럼 목록과 `parse` 는 `../molgen/genMOLDB_config.il` 의 `pexGenDB_GenDev_Get_Header_Type()` 과 맞춘다.
- process 는 (이름, 버전) 쌍이다(ADR-018). 버전은 코드·DB 에서 `release`, 화면 `Version`, CLI `--version` 이다. 새 코드에서 process 버전을 `version` 이라고 부르지 않는다. 이유: `device.version` 은 낙관적 잠금 카운터이고 그 뜻의 `version` 이 200곳 넘게 있다. 빈 버전 `''` 은 "버전 없음"이고 그때의 문구·출력에는 버전 흔적(빈 괄호, 남는 공백, version 낱말)이 없다. 버전이 없던 형태 그대로다(화면 `(none)`, CLI `-`. phase 24 전의 화면은 `(없음)`). 사람이 읽는 표시는 `audit.process_label(name, release)` 로 만든다.
- GUI 스레드에서 DB를 기다리지 않는다. 새 DB 호출은 `utils/background.py` 의 `run_blocking`(결과가 필요할 때) 또는 `Task`(비동기)로 돌린다. 워커 스레드에서 위젯을 만지지 않는다. `Task` 의 결과·실패 슬롯은 `self.sender()` 가 지금 작업일 때만 쓰고, 정리(`finished`) 슬롯은 끝난 그 작업(`sender()`)만 `deleteLater` 한다. 이유: 기다린 뒤 큐에 남은 옛 `finished` 가 그 순간의 `self._task`(돌고 있는 새 작업)를 지우면 프로세스가 0xC0000409로 죽는다(phase 12 step 2·3).
- 자동으로 다시 읽지 않는다. 남이 바꾼 것은 배너로 알리고, 언제 읽을지는 사용자가 정한다(편집 중 내용이 말없이 사라지면 안 된다).
- 파일 I/O는 항상 `encoding="utf-8"`. 개발 PC는 Windows(cp949)이고 운영은 RHEL 8이다.
- 새 런타임 의존성은 RHEL 8용 `manylinux_2_28` 이하 휠이 있어야 한다(`uv pip compile pyproject.toml --python-version 3.13 --python-platform x86_64-manylinux_2_28`).
- 사용자에게 보이는 문구(GUI·CLI·`tools/*.sh` 출력)는 영어다(ADR-020, 2026-10-22 승인). 문장 규칙과 용어는 UI_GUIDE "문구" 를 따른다.
  - 한국어로 두는 것: 주석, docstring, 문서, 로그 파일에만 가는 문구, 이력 요약(`change_log.summary`).
  - typer 명령 docstring은 예외다. `--help` 문구라서 영어로 쓴다.
  - 아직 한국어인 화면 문구는 phase 24(`24-english-text`)의 step이 옮긴다. 다른 step은 번역하지 않는다. 이유: 그 문구를 고정한 테스트 수정이 섞인다.
  - 버그 수정 중에 기존 문구를 바꾸지 않는다.

## 개발 프로세스
- CRITICAL: 새 기능 구현 시 반드시 테스트를 먼저 작성하고, 테스트가 통과하는 구현을 작성할 것 (TDD)
- CRITICAL: 버그 수정도 실패하는 테스트로 먼저 재현한다. 재현되지 않으면 고치지 않는다. 분석·리뷰 에이전트의 지적은 주장이다.
- 커밋 메시지는 conventional commits 형식을 따를 것 (feat:, fix:, docs:, refactor:, test:, chore:). 설명은 한국어로 써도 된다.
- 파일 삭제는 `git rm` 또는 Python 코드로 한다 (`rm -rf` 는 훅이 차단한다).
- 셸 스크립트(`tools/*.sh`)는 LF(`.gitattributes`)와 실행 비트(`git update-index --chmod=+x <file>`)로 커밋한다. 이유: Windows는 실행 비트를 잃고 CRLF면 서버에서 `bad interpreter` 가 난다.
- 루트 `scripts/` 는 하네스(execute.py)이고 `src/genviewer/scripts/` 는 관리 도구(init_db)다. 헷갈리지 않는다.

## 테스트 관례
- DB가 필요한 테스트는 `tests/conftest.py` 의 `pg_dsn`/`db` fixture를 쓴다. `GENDB_TEST_PG_DSN` 은 **관리자 DSN**이어야 한다(fixture가 `gendb_test_<pid>` 데이터베이스를 만들고 지운다. 권한 테스트는 CREATE ROLE까지 한다). 없으면 skip된다. 개발 PC 기준선(DB 없음, phase 22 완료 후 2026-10-22)은 Git Bash에서 991 passed / 241 skipped다. `sh` 가 PATH에 없는 셸(PowerShell)에서는 셸 스크립트 테스트 32개(`test_deploy_sh.py`, `test_initdb_sh.py`)가 더 skip되어 959 / 273이 된다. DB를 붙이면 1222 passed / 10 skipped(Windows 권한 테스트만 skip)다.
- 재현했지만 고치지 않기로 한 버그의 테스트는 `pytest.mark.xfail(strict=True, reason="K<번호>: …")` 로 남기고 `docs/notes/known-issues.md` 의 그 항목에 테스트 이름을 적는다(지금은 없다). 고치면 XPASS로 실패하므로 그때 xfail을 뗀다.
- POSIX 권한·심볼릭 링크 테스트는 `posix_only` 로 Windows에서 skip된다. 버그 재현(RED)은 Windows에서 도는 테스트로 보인다.
- 셸 스크립트는 stub 명령을 PATH 앞(initdb.sh 는 `PGBIN`)에 두고 실제로 실행해서 테스트한다(`tests/test_deploy_sh.py`, `tests/test_initdb_sh.py`). 텍스트 토큰 검사만으로 끝내지 않는다.
- GUI 테스트는 `tests/gui/` 에 둔다(pytest-qt, `qt_api = "pyside6"`). `tests/gui/conftest.py` 가 PySide6 import 전에 `QT_QPA_PLATFORM=offscreen` 을 둔다. `tests/test_background.py` 는 자기 `qapp` fixture로 따로 돈다.
- 모달은 autouse `dialogs` fixture가 대신한다. 예/아니오는 `dialogs.answer_question(...)`, 저장 충돌은 `dialogs.answer_conflict(RELOAD|OVERWRITE|CANCEL)` 로 미리 답하고, 뜬 문구는 `dialogs.shown` 의 `(kind, title, text)` 로 단언한다. 답하지 않은 모달·파일 대화상자·메뉴는 `AssertionError` 이고 앱이 삼켜도 teardown에서 실패한다(쓰지 않은 답도). 이유: `@report` 가 `AssertionError` 까지 알림으로 바꾼다.
- 키 입력에 달린 동작(편집 가능 콤보의 completer 등)은 `setEditText` 가 아니라 `from gui_support.keys import type_into` 로 친다(창 활성화와 칸 포커스를 기다린 뒤 친다). 이유: 포커스 없이 치면 completer 가 돌지 않아 수정 전에도 통과한다(phase 20). 정적 Qt 대화상자(`QInputDialog.getItem` 등) 안의 동작은 Python 패치가 닿지 않아 진짜 모달로만 재현된다. 수집 때 잡아 둔 진짜 함수를 테스트 안에서 되돌리고, `QTimer.singleShot(0, …)` 의 drive 는 단언 없이 기록만 하고 finally 에서 모달을 닫는다(`tests/gui/test_load_csv_release.py` 의 `ask_release_typing`). 닫지 않으면 테스트가 멈춘다.
- 레이아웃(위젯 겹침·창 최소 너비)은 `main_window` fixture가 아니라 컨트롤러 없이 `MainWindow("localhost")` 를 직접 띄워 재현하고, `QCoreApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)` 로 확정한 뒤 위젯 geometry로 단언한다. 픽셀 숫자는 박지 않는다. 이유: fixture 창은 컨트롤러가 채운 칸 때문에 이미 넓어서 수정 전에도 통과하고, 너비는 글꼴(앞 테스트의 `apply_theme`)에 따라 달라진다(phase 21, `tests/gui/test_toolbar_min_width.py`).
- GUI 테스트 헬퍼는 `tests/gui_support/` 에 두고 `from gui_support.dialogs import ...` 처럼 import한다(`pythonpath = ["tests"]`). conftest나 다른 테스트 모듈은 import하지 않는다. Qt 없는 테스트 헬퍼는 `tests/fixtures/` 에 둔다(`from fixtures.imports import ...`). "아무 일도 일어나지 않음"은 고정 대기(`qtbot.wait`) 대신 fake가 기록한 호출이나 컨트롤러 상태를 `qtbot.waitUntil` 로 기다린 뒤 단언한다. `waitUntil` 콜백은 bool을 돌려준다(`lambda: fake.sent != []`). 리스트를 돌려주면 pytest-qt가 `ValueError` 를 낸다.
- GUI 테스트의 DB는 `tests/gui_support/fakes.py` 의 `FakeStore`/`Fake*Repository` 다. 의미는 실제 repo가 기준이고 `tests/gui/test_fake_repo_contract.py` 가 같은 기대값을 가짜와 실제 PostgreSQL(`GENDB_TEST_PG_DSN`)에 돌려 고정한다. `service/repo/` 의 의미를 바꾸는 step은 가짜와 contract test도 같이 고친다.
- 컨트롤러 테스트는 `tests/gui/conftest.py` 의 `store`(시드: sf2p/nfet_a·nfet_b, sf4u/pfet_a, 탭 InstTerm·InstSchParam), `device_tab_ctrl`, `main_window` fixture와 `from gui_support.helpers import select_process, select_device_row, edit_device_cell, edit_tab_cell` 로 쓴다. 버전 쌍은 `store.add_process(name, release=...)` 로 넣고 `select_process(ctrl, name, release)` 로 고른다(시드는 모두 빈 버전). 장애는 `store.fail_next(메서드, 예외)`, 남의 변경은 `store.touch_device`/`store.remove_device`, 일어난 일은 `store.calls`/`store.calls_of` 로 본다. actor는 `GENDB_APP_USER=tester` 다. History 화면은 `history_ctrl` fixture로 쓰고 이력 줄은 `store.add_audit(actor, audit.Entry)` 로 넣는다(`main_window` 는 History를 만들지 않는다). 도는 `Task` 를 붙잡아 경합을 만들 때는 `ev = store.hold_next(메서드)` 뒤 `ev.set()` 으로 놓는다(lock 밖에서 기다리고 10초 안전장치가 있다).
- 첫 DB 접속은 `DeviceTabController` 생성자가 `QTimer.singleShot(0)` 으로 예약한다. 컨트롤러나 창을 직접 만드는 테스트는 `qtbot.waitUntil(lambda: ctrl.connected is not None)` 로 기다린 뒤 단언한다(두 fixture는 이미 기다린다). 창 닫기는 `MainWindowController` 의 이벤트 필터(저장 확인)를 거치고, pytest-qt는 fixture 정리보다 **먼저** 등록한 창을 닫는다. 그래서 편집을 남길 수 있는 창은 `qtbot.addWidget(ui, before_close_func=…)` 에서 `shutdown()` 으로 필터를 먼저 뗀다(`main_window` fixture가 그렇게 한다).
- 외부 의존(실제 Virtuoso, 실제 서버)은 테스트에서 붙지 않는다. Virtuoso 소켓 테스트는 `tests/gui_support/virtuoso_server.py` 의 127.0.0.1 로컬 서버(`LocalVirtuoso`)에 공개 API로 붙는다. 실행 중인 스레드를 놓칠 수 있는 재현은 서브프로세스에서 돌린다(`tests/gui_support/virtuoso_child.py`). 접속 실패 경로는 닫힌 포트(`127.0.0.1:1`)로 만든다.

## 명령어
```bash
GENDB_TEST_PG_DSN="postgresql://<user>@127.0.0.1:55433/postgres" uv run pytest -q   # DB 테스트까지
sh -n tools/deploy.sh && sh -n tools/initdb.sh   # 셸 문법 검사 (Windows는 Git Bash sh). 파일마다 따로: `sh -n a b` 는 a 만 본다
uv run python -X utf8 scripts/execute.py <phase>   # 하네스 phase 실행 (-X utf8: cp949 콘솔 대응)
```
