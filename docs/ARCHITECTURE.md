# 아키텍처

이 문서는 현재 구조와 경계 규칙을 담는다. phase 진행 기록은 `phases/index.json` 에 있다.
- 문서 지도: 무엇을 → `PRD.md`, 왜 → `ADR.md`, 화면 → `UI_GUIDE.md`, 작업 규칙 → `/CLAUDE.md`, 사용자·운영 절차 → `/README.md`. 구조 제안과 알려진 문제는 `docs/notes/`(프롬프트에 주입되지 않음).
- 이 문서는 경계와 흐름만 고정한다. 함수 시그니처 세부는 실제 코드가 기준이다.

## 한눈에 보기
```
RHEL 8 데스크톱 / Windows 개발 PC                         RHEL 7 서버
┌──────────────────────────────────────┐                ┌───────────────────────┐
│ genviewer (GUI, PySide6)             │   psycopg      │ PostgreSQL 15 (:55433)│
│ genviewer <cmd> (CLI, typer)         │ ─────────────→ │  db molgen            │
│   service/ (Qt-free) ── pool ────────┼── libpq 번들 ──│  role molgen_app (DML)│
└──────────────┬───────────────────────┘                │  role molgen_owner(DDL)│
               │ TCP (4바이트 길이 + UTF-8)              │ init_db (Py 3.9, 소스) │
               ↓                                        └───────────────────────┘
        Cadence Virtuoso SKILL 세션
```
- 서버 장비에서 도는 우리 프로그램은 없다. 동시 편집은 `device.version` 낙관적 잠금이 처리한다.
- 접속 설정은 `genviewer.env`(libpq 키) 하나. 배포는 `tools/deploy.sh` 가 git 태그를 `<ROOT>/{src,venv,bin}` 에 설치한다.

## 디렉토리 구조
```
src/genviewer/
  __main__.py  cli.py       # 진입점. typer 앱, 서브커맨드 없으면 main.run_gui (함수 안 lazy import)
  main.py                   # Qt 부팅, Fusion + 테마, 마지막 예외 그물(sys/threading excepthook), audit source "gui"
  config/                   # tab_config.json(탭 = CSV 컬럼 = 테이블), delegate_config.json(값 후보·검증), config.py 로더
  service/                  # Qt-free. 테스트가 GUI 없이 돈다
    config.py               #   DbConfig(frozen), resolve_dsn/load_config: --dsn > GENDB_PG_DSN > 설정 파일 > PG*
    env_file.py             #   genviewer.env 찾기(파일 하나만)·파싱·권한 검사·os.environ.setdefault
    pool.py                 #   Database: psycopg_pool.ConnectionPool(open=False, dict_row, lock/statement timeout)
    errors.py               #   Conflict, StaleWriteError, DbUnavailableError, user_message(SQLSTATE → 한국어)
    schema.py               #   tab_config → DDL, TABLE_COLUMNS 허용 목록 (Python 3.9 호환)
    diagnostics.py          #   --check-config / status 진단 (값 노출 없이)
    virtuoso_protocol.py    #   Virtuoso 메시지 파싱·명령 문자열 (순수 함수)
    repo/                   #   쿼리. 호출 하나 = 트랜잭션 하나
      device.py             #     목록, etag, upsert_devices(잠금·preflight·DML·audit)
      parameter.py          #     탭 행 읽기, replace_many_for_device(버전 확인 후 통째 교체)
      process.py            #     process 목록·추가·삭제·get_or_create
      io.py                 #     CSV import(pandas), export 데이터
      audit.py              #     change_log 쓰기(호출자의 cursor)·읽기·포맷·purge
  scripts/                  # 관리 도구 (argparse). init_db(스키마·role·권한)
  models/                   # QAbstractTableModel: device_table(dirty·undo), generic_table(탭), device_state, parameter_summary, sorting_proxy
  views/                    # QWidget. 위젯을 만들고 의도 시그널을 낸다. main_window, device_tab, device_table, parameter_tab, tab_section, history_tab, socket_tab …
  controllers/              # QObject. view 시그널 ↔ repo 호출. main_window, device_tab(접속·폴링), device_table(저장·충돌), parameter_tab, tab_section(device별 모델 캐시), device_tab_toolbar, history_tab, socket_tab
  dialogs/                  # conflict(다시 읽기/덮어쓰기/취소), connection(Connect…), insert, tab_selector
  delegates/combo_box.py    # delegate_config 기반 콤보
  net/                      # Virtuoso 소켓: client(Client), workers(Connect/Receive/Send QThread), controller(ConnectionController)
  utils/                    # background(run_blocking, Task, is_busy), logs(파일 로그, scrub), reporting(report 데코레이터),
                            # exporter(csv/xlsx), lisp(SKILL 리스트), validators, user(current_user), palette, dialogs, menus …
tools/                      # initdb.sh(클러스터 생성·기동), deploy.sh(태그 설치·런처)
tests/                      # pytest. conftest: pg_dsn/db fixture (GENDB_TEST_PG_DSN)
  gui/                      #   pytest-qt GUI 테스트. conftest: offscreen, autouse dialogs(모달 가짜), store/device_tab_ctrl/main_window
  gui_support/              #   GUI 테스트 헬퍼 패키지(pythonpath=tests): dialogs.py, fakes.py(FakeStore·FakeDatabase·Fake*Repository·FakeVirtuosoClient), helpers.py(시드, install_fake_db·install_fake_history, 사용자 동작)
  fixtures/                 #   Qt 없는 테스트 헬퍼 패키지(pythonpath=tests): imports.py(import 스캐너, test_boundaries.py·test_py39_compat.py 가 쓴다)
scripts/                    # 하네스 execute.py (+ test_execute.py). 앱 코드가 아니다 (ruff 제외)
phases/                     # 하네스 step 파일
docs/                       # 이 문서들. notes/ 는 주입 제외
```

## 레이어 (위 → 아래로만 import)
| 티어 | 패키지 | import 해도 되는 것 |
|---|---|---|
| 0 | `config/`, `utils/user.py`, `utils/logs.py`, `utils/validators.py`, `utils/lisp.py` | stdlib |
| 1 | `service/`, `service/repo/` | 티어 0, psycopg, psycopg_pool, pandas(`repo/io.py`) |
| 1 | `scripts/` | `service.schema`, `config`, `utils.user`, psycopg(함수 안) |
| 2 | `cli.py`, `utils/exporter.py` | 티어 0·1. **PySide6 금지** (`cli.py` 는 typer 콜백 `root` 안에서만 `genviewer.main`) |
| 3 | `models/`, `delegates/`, `views/`, `dialogs/`, `net/`, Qt `utils/*`(background, dialogs, file_dialogs, menus, palette, table_utils), `utils/reporting.py`(Qt 없음, `service.errors` 사용) | 아래 티어 전부, PySide6 |
| 4 | `controllers/`, `main.py` | 전부 |

- models는 `utils.validators` 만 안다. `net/` 은 자기 안에서 닫혀 있다.
- 강제: `tests/test_boundaries.py` 가 Qt 금지 구역(티어 0~2, 함수 안까지 보는 정적 스캔 + 새 인터프리터 import, 예외는 `cli.py` 의 `root` 안 `genviewer.main` 뿐)과 models·net 의 import 범위를 지킨다. `tests/test_py39_compat.py` 가 init_db 에서 닿는 모듈을 import를 따라가며 찾아(함수 안 import·부모 패키지 포함) 3.9 문법·런타임 `X | Y`·3.10+ 키워드와 이름·PEP 701 f-string을 정적으로 검사한다(3.9 인터프리터로 import해 보지는 않는다).

### 현재 어긋난 곳 (따라 하지 않는다)
- `dialogs/connection.py` 가 `service.pool.Database` 를 직접 만들어 연결 테스트(`connection()` 으로 `SELECT 1`)를 한다(view 쪽에서 서비스 호출).
- `MainWindowController`·`DeviceTabController`·`DeviceTableController` 가 다른 컴포넌트의 private 멤버를 부른다(`_open_connect`, `_clear_tabs`, `_selected_source_rows`, `_map_to_source_row` 등).
- `utils/reporting.py` 가 `service.errors` 를 import한다(utils → service 역방향).
- 모델 소유가 섞여 있다. 어떤 view는 자기 모델을 만들고, `TabSectionController`·`HistoryTabController` 는 controller가 만든다.

## 데이터 흐름

**접속 설정** (`service/config.py`, `env_file.py`)
```
--dsn / Connect 창 ─┐
GENDB_PG_DSN ───────┴→ 있으면 그대로 사용 (설정 파일은 읽지 않는다)
없으면 → env_file.load(GENDB_CONFIG)
          GENDB_CONFIG 가 있으면 그 파일만, 없으면 ~/.genviewer.env → sys.prefix/genviewer.env
          → sys.prefix.parent/genviewer.env(배포 루트) → 체크아웃 루트(pyproject.toml 있을 때)
          처음 찾은 비어 있지 않은 파일 하나만 읽어 os.environ.setdefault (이미 있는 환경변수가 이긴다)
       → GENDB_PG_DSN 이 생겼으면 그것, PG* 가 있으면 "" (libpq 가 환경변수로 조립), 없으면 찾아본 경로를 담아 RuntimeError
```

**DB 접속** (`DeviceTabController.connect_db`): 시작 접속은 생성자가 `QTimer.singleShot(0)` 으로 예약한다(창의 로그 패널·알림이 이어진 뒤에 돈다. 그때까지 `connected` 는 None). 새 DB를 먼저 연다(`run_blocking`). 확인은 `ping()`(원인을 삼키고 bool만 준다) 대신 `connection()` 으로 `SELECT 1` 을 돌리고, `open()` 이나 확인이 실패하면 그 새 DB를 닫은 뒤 원인이 담긴 예외를 그대로 올린다(로그 패널 `Database connect failed: <user_message>`). 실패하면 지금 DB·repo·폴링을 그대로 둔다. 성공하면 폴링 타이머를 멈추고 도는 폴링 `Task` 를 기다린 뒤 옛 DB를 닫고 `dbChanged(새)` 를 한 번 낸다. 로그 패널로 가는 DSN은 `scrub()` 을 거친다. Connect… 창의 입구(`_on_connect`)는 device 표나 탭이 dirty면 `connect_db` 를 부르기 전에 Refresh 질문을 하고, 아니오면 아무것도 하지 않는다(시작 접속은 묻지 않는다).

**풀** (`service/pool.py`): `ConnectionPool(min 1, max 4, open=False, check=check_connection)`. 접속 옵션 `-c lock_timeout=5000 -c statement_timeout=15000`(의도된 값, ADR-008), `connect_timeout=5`, `application_name=genviewer:<user>`. `Database.connection()` 하나가 트랜잭션 하나(정상 종료 commit, 예외 rollback). 커넥션을 얻지 못한 것(`PoolTimeout`)만 `DbUnavailableError` 가 되고(그때 한 번 직접 접속해 실제 원인을 설명으로 싣는다), `with` 본문·commit 에서 난 예외는 타입 그대로 올라간다(`user_message` 의 SQLSTATE별 안내가 살아 있게).

**device 저장** (`repo/device.py: upsert_devices`, 한 트랜잭션)
```
pg_advisory_xact_lock(process) → SELECT … FOR UPDATE ORDER BY id (= audit before 값)
→ _preflight: version 불일치/사라진 행 → StaleWriteError (force 면 건너뜀)
→ 지울 device 의 자식 행 캡처 → DELETE (process_id 가드)
→ UPDATE … FROM VALUES (version 가드 + IS DISTINCT FROM, version+1) → INSERT
→ audit.write(cur, …)  (값이 실제로 바뀐 행만)
```
- 탭 저장(`repo/parameter.py: replace_many_for_device`): `FOR UPDATE OF d` → `expected_version` 비교 → 테이블마다 DELETE … RETURNING + INSERT → `device.version+1` → audit.
- GUI 쪽: 모델이 dirty·baseline을 들고 있다. 컨트롤러가 `run_blocking` 으로 repo를 부르고, `StaleWriteError` 면 `dialogs/conflict.ask_conflict` 로 RELOAD / OVERWRITE(force) / CANCEL을 묻는다. 내가 지운 행을 뺀 나머지 충돌이 전부 deleted면 OVERWRITE를 내놓지 않는다(`conflict.can_overwrite`, 테스트 가짜도 같은 함수로 판단한다).
- 붙여넣기: device 행을 바로 저장하고, 그 저장이 돌려준 version으로 탭 행을 쓴다(`pasteRequested` 가 version을 싣는다). device 표나 탭이 dirty면 붙여넣지 않는다.
- Remove Process: 삭제가 성공하면 `processRemoved` 가 목록을 다시 채우기 전에 지금 process의 device·탭 편집을 버린다(저장할 곳이 없다).
- 저장 결과: device·탭 `save_all()` 과 `DeviceTabController.save_db()` 는 bool이다(저장했거나 쓸 것이 없으면 True, 취소·다시 읽기·건너뛴 편집이면 False, 예외는 그대로). 호출부(Database → Save, Ctrl+S, process·device 전환)는 False면 "Saved" 를 띄우지 않고, 편집이 남아 있으면 옮기지 않는다. process 콤보는 `select_process_silently` 로 시그널 없이 되돌린다(되돌릴 process가 목록에 없으면 False이고, 그때는 되돌리지 않고 새 process로 넘어간다).
- 창 닫기: `MainWindowController` 가 창에 이벤트 필터를 달아 Close를 판단한다(뷰는 컨트롤러를 모른다). `is_busy()` 면 무시하고, dirty면 묻고 `save_db()` 가 True일 때만 닫는다. `shutdown()` 이 먼저 필터를 뗀다.
- 탭 로드 실패: `TabSectionController.update_model` 이 행을 읽지 못하면 섹션을 모델 없이 비우고 dirty를 푼다(이전 device의 모델이 남아 이 device에 저장되지 않게). 붙여넣기도 그 탭은 건너뛴다.
- 탭 섹션 수명: `TabSectionController` 는 device마다 모델을 캐시하고(`model_by_device`), 콤보 delegate는 컬럼마다 하나를 모든 모델이 같이 쓴다(후보는 `index.model()` 의 celltype). `setModel` 이 표·머리글에 새로 만든 selection model 중 지금 쓰지 않는 것은 지운다. 접속·재접속의 `rebuild_tabs` 는 떼어 낸 옛 섹션(과 그 컨트롤러)·옛 "+" 를 지우고 Summary는 다시 쓴다.
- device 정렬: `DeviceTableModel.sort_rows` 가 모델의 모든 행을 정렬한다. 기준점은 그대로라 지운 device·편집 표시·undo가 남는다. 끌어 옮기기(`DeviceTableView.dropEvent`)는 고른 행이 모델에서도 이어져 있을 때만 받는다(필터가 사이 행을 숨겼으면 `ignore`).
- 순서값: `save_all` 은 보통 화면 순서대로 `order = 0..n-1` 을 매긴다. 마지막 `refresh_devices` 가 Virtuoso 목록으로 숨긴 행이 있었으면, 보내는 행끼리 그때 읽은 자기들의 옛 순서값을 화면 순서대로 나눠 갖는다(`_filtered_orders`, 숨은 행은 보내지 않는다).
- version 동기화: 탭 저장이 올린 version은 `deviceVersionChanged` 로 device 표에, device 저장이 올린 version은 `deviceVersionBumped` 로 탭에 간다. 탭은 정확히 +1일 때만 받는다(덮어쓰기로 남의 변경 위에 썼으면 다음 탭 저장이 충돌로 묻는다).

**변경 감지**: `DeviceTabController` 의 10초 `QTimer` → `Task(repo.etag(process_id))` → 기억한 etag와 다르면 배너. 연속 3회 실패하면 멈추고, 다시 접속하면 되살아난다. 자동으로 다시 읽지 않는다. 결과는 폴링을 시작한 process·DB가 그대로일 때만 쓴다(전환·재접속 뒤 도착한 결과는 버린다). History 화면도 10초마다 `Task` 로 다시 읽고, 줄을 고르면 멈춘다. 다시 읽는 중에 필터를 바꾸거나 DB가 바뀌면 끝난 뒤 한 번 더 읽고, 그사이 도착한 옛 결과는 버린다.

**스키마**: `tab_config.json` 의 탭마다 자식 테이블 하나(`id IDENTITY`, `device_id … ON DELETE CASCADE`, payload `TEXT NOT NULL DEFAULT ''`, `(device_id, id)` 인덱스). 고정 테이블 `process`, `device`(version, updated_at, updated_by), `change_log`(FK 없음, JSONB detail). 전부 `CREATE … IF NOT EXISTS` + 탭 테이블의 빠진 컬럼은 카탈로그를 보고 `ADD COLUMN`(다 있으면 `ALTER` 를 실행하지 않아 ACCESS EXCLUSIVE 를 잡지 않는다)이라 `init_db` 는 여러 번 돌려도 된다. 같은 원본이 `TABLE_COLUMNS`, 화면 탭(`views/parameter_tab.py`), CSV import(`parse`, `row_per_token`), export, `diagnostics.expected_tables`(17개)와 탭 테이블의 컬럼을 만든다. DDL과 tab_config의 어긋남(테이블 집합, 컬럼 이름·순서)은 `tests/test_schema.py` 가 접속 없이 렌더링한 PostgreSQL DDL로 잡는다.

**권한** (`scripts/init_db.py`): `SET ROLE <owner>` 후 DDL → `GRANT USAGE ON SCHEMA public`, `GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES` → `ALTER DEFAULT PRIVILEGES`(새 탭 테이블도 자동). 시퀀스 권한은 IDENTITY라 필요 없다.

## 스레딩
- `utils/background.run_blocking(fn, parent)`: `Task`(QThread)에서 fn을 돌리고 GUI 스레드는 `processEvents(ExcludeUserInputEvents)` 로 돌면서 대기 커서를 띄운다. 예외는 호출 지점에서 다시 난다. 끝난 `Task` 는 결과·예외를 읽은 뒤 지운다(parent 아래 쌓이지 않게). 접속·저장·CSV 불러오기·연결 테스트가 이것을 쓴다.
- `Task` 단독(비동기): 변경 감지 폴링, History 다시 읽기. `done`/`failed` 시그널은 GUI 스레드에서 받는다. 결과·실패는 시그널을 낸 작업(`sender()`)이 지금 작업일 때만 쓰고, 정리(`finished`)는 끝난 그 작업만 지운다. 기다린 뒤 큐에 남은 옛 `finished` 가 돌고 있는 새 작업을 지우면 프로세스가 죽는다.
- 아직 GUI 스레드에서 동기로 도는 DB 호출이 있다(process 목록·추가·삭제, 탭 로드, 복사·붙여넣기, export). 새 코드는 이 패턴을 따르지 않는다.
- psycopg 커넥션은 스레드끼리 공유하지 않는다(풀에서 호출마다 꺼낸다).
- `net/` 은 QThread 워커 셋(Connect/Receive/Send)이 `Client` 소켓 하나를 쓴다. 접속 중의 Connect는 무시하고, 보내기 실패는 받기 오류처럼 `received` 로 간다. 창을 닫으면 `ConnectionController.shutdown()` 이 받기·보내기 워커를 멈춘다(접속 중인 ConnectWorker는 기다리지 않는다, known-issues K39).
- 워커 스레드에서 샌 예외(`QThread.run`)는 PySide6가 그 스레드에서 `sys.excepthook` 을 부른다. `main.py` 의 hook은 로그를 남기고, 상자는 GUI 스레드일 때만 연다.

## 배포 구조
```
<ROOT>/genviewer.env   접속 설정 (640, 배포가 덮지 않음, a+rX 대상에서 제외)
<ROOT>/src             태그에 detach 된 체크아웃 (.git 은 배포한 사람만, go-rwx)
<ROOT>/venv            uv sync --locked --no-dev --no-editable (코드는 site-packages 사본에서 돈다)
<ROOT>/bin             런처: venv 인터프리터에 콘솔 스크립트를 넘긴다 (shebang 127바이트 제한 회피)
<ROOT>/python          (선택) DEPLOY_PYTHON 용 CPython. 있으면 a+rX
```

## 용어
- **process**: molgen의 공정/라이브러리 단위(`CdsLibName`). device를 묶는다.
- **device**: CSV 한 행. 이름은 표시용이고 중복될 수 있으며, 식별은 `id` 로 한다.
- **탭 / 자식 테이블**: CSV 컬럼 하나. device마다 여러 행.
- **etag**: process 하나의 device 상태 요약 `count(*)`, `sum(version)`, `max(updated_at)`(+ 표시용 `who`). 셋 중 하나라도 다르면 누군가 바꾼 것이다. 변경 감지에 쓴다(LISTEN/NOTIFY 대신, `repo/device.py` docstring).
- **actor**: 이력에 남는 사람 이름(`GENDB_APP_USER` 또는 OS 로그인).
