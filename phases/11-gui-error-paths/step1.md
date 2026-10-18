# Step 1: connect-failure-cause

## 배경 (phase 11 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 11은 2026-10-17에 `docs/notes/known-issues.md` 를 분류하면서 고치기로 한 GUI 오류 경로 항목을 한 step에 하나씩 다룬다. 버그(K34·K35, K22 일부)와 **사용자가 2026-10-17 승인한 동작 변경**(K3의 GUI 쪽, K21, K16 내보내기 형식, K18)이 섞여 있다. 승인된 step에는 승인 문장을 그대로 적었다. 그 문장 밖으로 넓히지 마라.

phase 0~10이 끝나 있다. 이 phase에 닿는 것:
- phase 7 step 2(`pool-failure-cause`): 풀에서 커넥션을 얻지 못하면 `Database.connection()` 이 한 번 직접 접속해 그 실제 원인(첫 줄, `scrub` 거침)을 `DbUnavailableError` 에 담는다. `ping()` 은 여전히 bool이다. 정확한 API는 `src/genviewer/service/pool.py` 와 `phases/7-service-fixes/index.json` 의 summary로 확인하라.
- phase 10: 저장·편집 보호(삭제 충돌의 덮어쓰기 숨김, 같은 행 재클릭, 붙여넣기 version·탭 dirty 거부, 재접속·CSV 불러오기 전 질문, Remove Process 뒤 편집 버림, 걸러 본 저장의 순서값). `controllers/device_tab.py`·`device_table.py`·`dialogs/conflict.py` 가 바뀌었다. phase 10 step 4가 `_on_connect` 에서 `connect_db` 를 부르기 전에 질문(편집이 있을 때)을 넣었다. `connect_db` 본문은 그대로다.
- step 0(이 phase): process 조회 실패 알림·폴링 중단 로그가 `user_message` 를 거친다.

모든 step에 같은 규칙이 적용된다.
1. 버그는 **주장**이다. 먼저 실패하는 테스트로 재현하고 RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다. 승인된 동작 변경도 테스트를 먼저 쓰고, 지금 코드에서 그 테스트가 어떻게 실패하는지(지금 동작)를 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 증명이 되지 못한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. 이 파일의 행 번호는 2026-10-18(phase 10 직후) 기준 대략값이다. 이름으로 찾아라.
6. `DeviceTabController.connect_db`/`_open_database` 는 phase 7·10·11·12가 차례로 건드린다. 이 파일은 그 본문을 인용하지 않는다. 지금 코드를 읽고, 적힌 불변식만 지켜라.

GUI 테스트 기반(phase 2)의 이름을 그대로 쓴다. 작업 전에 `tests/gui/conftest.py`·`tests/gui_support/` 를 읽고, 이 파일의 서술과 다르면 실제 코드를 따른다.
- `dialogs`(autouse `FakeDialogs`): `answer_question`, `answer_conflict`, `shown`(`(kind, title, text)`, severity `warn` → kind `warning`). 답하지 않은 모달·파일 대화상자·메뉴는 `AssertionError`(teardown 실패).
- `device_tab_ctrl`, `main_window`, `store`(sf2p: nfet_a·nfet_b / sf4u: pfet_a, 탭 InstTerm·InstSchParam), `store.calls_of`, `store.fail_next`.
- `install_fake_db(monkeypatch, store)` 가 `DeviceTabController._open_database` 를 `store.open_database` 로 바꾼다. 그래서 fixture 안에서는 `_open_database` 본문이 돌지 않는다.
- `tests/gui_support/fakes.py` 의 `FakeDatabase(store, dsn)`: `open()`, `close()`(`closed`, `close_count`), `ping()`(닫혀 있지 않으면 True). `connection()` 은 `AssertionError` 를 낸다(가짜 DB 에서 SQL 을 돌리지 않는다).
- 고정 대기(`qtbot.wait`) 금지. `waitUntil` 콜백은 bool을 돌려준다.

## 이 step의 목적

(**사용자 승인 2026-10-17**, K3) 승인 문장: "풀 타임아웃이면 한 번 직접 접속해 실제 원인(비밀번호 틀림·DB 없음·접속 수 초과)을 기존 SQLSTATE 안내 문구로 보임. 실패할 때 대기가 최대 5초 더 길어짐."

서비스 쪽(`Database.connection()` 이 원인을 담은 `DbUnavailableError` 를 낸다)은 phase 7 step 2가 끝냈다. psycopg 3.3.5는 접속 실패에 `.sqlstate` 를 채우지 않으므로 원인은 SQLSTATE 안내 대신 실제 오류 문장(첫 줄, 비밀번호 가림)으로 나온다. phase 7 step 2의 summary로 실제 결과를 확인하라.

이 step은 GUI의 두 곳이 그 원인을 보이게 한다.
1. `DeviceTabController._open_database`: 확인이 `ping()` 의 bool이라, 실패하면 원인 없이 고정 문구 `DbUnavailableError("서버가 응답하지 않는다")` 를 낸다. 그래서 로그 패널의 `Database connect failed: …` 줄에 실제 원인이 나오지 않는다.
2. Connect 창(`dialogs/connection.py` `ConnectionDialog._on_test`)의 "연결 테스트": `probe()` 가 `ping()` 의 bool을 받아 `"실패: 접속할 수 없다"` 를 띄운다. 그 밖의 예외는 `f"실패: {e}"`(`str(e)`, CLAUDE.md 위반)다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ARCHITECTURE.md`("DB 접속", "풀"), `/docs/ADR.md`(ADR-008, ADR-009 phase 4 보강, ADR-013), `/README.md`("일회성으로 다른 데 붙기")
- `src/genviewer/service/pool.py`: `Database.connection()`, `ping()`. phase 7 step 2가 바꾼 실패 경로를 읽는다.
- `src/genviewer/service/errors.py`: `user_message`, `DbUnavailableError`, `_UNAVAILABLE`
- `src/genviewer/controllers/device_tab.py`: `_open_database`(staticmethod, 워커 스레드에서 돈다), `connect_db`, `_on_connect`
- `src/genviewer/dialogs/connection.py`: `prefill()`, `ConnectionDialog.__init__`, `dsn()`, `_on_test`. `probe()` 는 `load_config`·`Database`·`run_blocking` 을 함수 안에서 import한다.
- `tests/gui/test_connect_db.py`(phase 4의 재접속 테스트. 실패하면 지금 DB를 그대로 쓴다)
- 이전 step에서 수정된 파일: `git diff main...HEAD --stat` 으로 확인한다.

## 승인된 동작 변경

사용자가 2026-10-17 확인한 범위: 원인은 로그 패널의 `Database connect failed: …` 줄과 Connect 창의 연결 테스트 결과 칸에만 보인다. "Connect Failed" 상자 문구는 바꾸지 않는다. 원인 문장은 SQLSTATE 안내가 아니라 실제 오류의 첫 줄(비밀번호 가림)이다(psycopg 3.3.5 는 접속 실패에 SQLSTATE 가 없다).

| 화면 | 지금 | 바뀐 뒤 |
|---|---|---|
| 로그 패널, 접속 실패 줄 | `Database connect failed: 데이터베이스에 접속할 수 없다. …\n\n서버가 응답하지 않는다` | 같은 접두어 + `user_message(e)`. 상세가 실제 원인이 된다(예: `FATAL: password authentication failed for user "app"`) |
| "Connect Failed" 알림 상자 | `데이터베이스에 연결하지 못했다.` | **그대로**(문구를 바꾸지 않는다) |
| Connect 창 연결 테스트, 실패 | `실패: 접속할 수 없다` 또는 `실패: {str(e)}` | `실패: ` + `user_message(e)` (원인 포함, 비밀번호 가림) |
| Connect 창 연결 테스트, 성공 | `연결 성공` | 그대로 |

불변식:
- 원인은 `user_message(e)` 로만 화면에 간다.
- `_open_database` 는 실패하면 예외를 낸다(지금처럼). 성공하면 연 Database를 돌려준다(지금처럼).
- `service/` 는 이 step에서 바꾸지 않는다. 원인을 내는 공개 경로를 그대로 쓴다. 원인이 담긴 예외가 올라오는 확인이 service에 따로 없으면 controller·dialog에서 `with db.connection() as conn: conn.execute("SELECT 1")` 처럼 확인한다.
- `ping()` 의 동작(bool, 예외를 삼킨다)은 바꾸지 않는다.
- 실패한 Database를 닫는 처리는 이 step에서 더하지 않는다. step 2(connect-failure-pool)가 재현부터 한다.

### 결과 × 상태 (`connect_db` 의 `run_blocking(_open_database)`)

| 결과 | 접속 전(시작할 때의 첫 접속) | 접속 중(Connect… 로 다시 접속) |
|---|---|---|
| 성공 | 지금과 같다 | 지금과 같다(새 DB로 바꾸고 `dbChanged` 한 번) |
| 예상 오류: 원인이 담긴 `DbUnavailableError` | `connected = False`, 로그 `Database connect failed: <user_message, 원인 포함>`, 알림 없음 | 지금 DB·repo·폴링 그대로, 알림 "Connect Failed"(문구 그대로) + 같은 로그 줄 |
| 예상 밖 예외(`load_config` 의 RuntimeError, psycopg 의 다른 오류) | 위와 같은 경로. 로그 줄은 `user_message` | 위와 같은 경로 |
| 창 닫는 중 | `run_blocking` 중의 닫기는 무시된다(`is_busy`, phase 4). 바꾸지 않는다 | 같다 |

연결 테스트(`_on_test` 의 `run_blocking(probe)`)도 같다. 성공이면 `연결 성공`, 어떤 예외든 `실패: ` + `user_message(e)` 다. 버튼은 어느 경우든 다시 켜진다(지금처럼 `finally`).

## 작업

### 1. 테스트 먼저 (`tests/gui/test_connect_failure.py`, 새 파일. step 2도 이 파일에 더한다)

준비
- `install_fake_db` 가 `_open_database` 를 바꾸기 전에 원래 함수를 잡아 둔다. 모듈 수준에서 `OPEN_DATABASE = DeviceTabController.__dict__["_open_database"].__func__` 처럼 한다.
- `genviewer.controllers.device_tab` 모듈의 `Database` 와 `load_config` 를 monkeypatch 한다.
  - `load_config` 자리: `lambda dsn: DbConfig(dsn=dsn or "x", app_user="tester")`
  - `Database` 자리: 접속 실패를 흉내 내는 작은 가짜 클래스. `FakeDatabase` 를 이어받아도 된다.
    - `ping()` 은 False다(실제 `ping` 은 예외를 삼키고 False를 준다).
    - phase 7 step 2 이후 실제 `connection()` 이 내는 것과 같은 모양을 낸다. 예: `DbUnavailableError('FATAL: password authentication failed for user "app"')`
    - 모양은 phase 7 step 2의 코드를 보고 맞춘다.
- Connect 창은 `genviewer.dialogs.connection.prefill` 을 고정 dict를 돌려주게 monkeypatch 한 뒤 만든다. 이유: `prefill()` 이 `env_file.load` 로 개발 PC의 실제 `genviewer.env` 를 `os.environ` 에 넣는다. `probe()` 가 쓰는 `genviewer.service.pool.Database`·`genviewer.service.config.load_config` 도 monkeypatch 한다.

테스트
- **`_open_database` 원인**: `OPEN_DATABASE("host=h")` 가 `DbUnavailableError` 를 낸다. 그 `user_message` 에 `"password authentication failed"` 가 있다. **수정 전에는 "서버가 응답하지 않는다" 라 실패해야 한다.**
- **재접속 실패 로그**
  - 준비: `main_window` 에서 `monkeypatch.setattr(DeviceTabController, "_open_database", staticmethod(OPEN_DATABASE))` 로 원래 함수를 돌려놓는다. 위 가짜 `Database` 를 쓴다.
  - 동작: `main_window.ui.device_tab_view.dbConnectRequested.emit("host=other")`
  - 단언: 로그 패널(`main_window.ui.log_te.toPlainText()`)에 `"Database connect failed:"` 와 원인 문장이 있다. `dialogs.shown` 의 제목은 `["Connect Failed"]` 이고 본문은 지금 문구 그대로다. 지금 DB를 그대로 쓴다(phase 4 단언). **수정 전에는 원인이 없어 실패해야 한다.**
  - phase 10 step 4의 질문은 편집이 없으면 뜨지 않는다. 편집을 만들지 않는다.
- **연결 테스트 실패**: `ConnectionDialog()` 를 만들고 `_on_test()` 를 부른다. `status_label.text()` 가 `"실패: "` 로 시작하고 원인 문장이 있으며, `"s3cret"`(비밀번호 칸에 넣은 값)이 없다. **수정 전에는 `"실패: 접속할 수 없다"` 라 실패해야 한다.**
- **연결 테스트, 예상 밖 예외**: `load_config` 자리가 `RuntimeError("bad password=s3cret")` 를 내면 `status_label` 에 `"s3cret"` 이 없다. 수정 전에는 `str(e)` 라 실패한다.
- **회귀**
  - 확인이 성공하는 가짜면 `OPEN_DATABASE` 가 그 db를 돌려주고 `open()` 이 불렸다.
  - 연결 테스트는 `"연결 성공"` 이다.
  - `tests/gui/test_connect_db.py` 가 그대로 통과한다.

### 2. 수정

- `controllers/device_tab.py` `_open_database`: bool 확인 대신 원인이 담긴 예외가 올라오는 확인을 쓴다. 성공 경로·반환값은 그대로 둔다.
- `dialogs/connection.py` `_on_test`: `probe()` 가 원인이 담긴 예외를 내게 한다. 실패 표시는 `"실패: " + user_message(e)` 로 한다. `"연결 중..."`·`"연결 성공"`·버튼 다시 켜기는 그대로 둔다.
- 두 곳 다 `service/` 는 바꾸지 않는다.

### 3. 문서

- `README.md` "일회성으로 다른 데 붙기" 절의 "접속에 실패하면 아래 로그 패널에 `Database connect failed: …` 가 남고" 문장 근처에 한 문장을 더한다. 내용: 그 줄과 Connect 창의 연결 테스트에 실제 원인(비밀번호 틀림, DB 없음 등. 비밀번호는 가려진다)이 나온다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_connect_failure.py tests/gui/test_connect_db.py -q   # 새 테스트 통과 (수정 전에는 원인 테스트가 실패해야 한다)
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 원인이 `user_message` 로만 화면에 가는가(CLAUDE.md CRITICAL)?
   - `service/` 를 바꾸지 않았는가? `dialogs/connection.py` 에 새 서비스 호출을 더하지 않았는가? 이미 있는 `probe()` 안에서만 바꾸고, ARCHITECTURE "현재 어긋난 곳" 을 넓히지 않는다.
   - "Connect Failed" 알림 문구와 로그 접두어가 그대로인가?
   - 테스트가 개발 PC의 실제 `genviewer.env` 를 읽지 않는가(`prefill` monkeypatch)?
3. 결과에 따라 `phases/11-gui-error-paths/index.json` 의 step 1을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "_open_database·Connect 창 연결 테스트가 phase 7 step 2 의 원인 담긴 DbUnavailableError 를 user_message 로 보임(확인 방법: <쓴 경로>). RED: <테스트 이름: 단언>. 변이: <…>. tests/gui/test_connect_failure.py (OPEN_DATABASE·가짜 Database 준비는 step 2 가 재사용)"`
   - 재현 안 됨(지금도 원인이 보임) → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `service/pool.py`·`service/errors.py` 를 바꾸지 마라. 이유: 서비스 쪽은 phase 7 step 2가 끝냈고, 바꾸면 CLI 출력도 함께 바뀐다.
- "Connect Failed" 알림 문구나 로그 접두어를 바꾸지 마라. 이유: 승인 범위는 "원인 표시" 뿐이다(UI_GUIDE 문구).
- 실패한 Database를 닫는 코드를 더하지 마라. 이유: step 2가 그 누수를 재현부터 한다. 여기서 고치면 step 2의 RED가 사라진다.
- `ping()` 의 동작을 바꾸지 마라. 이유: bool을 기대하는 다른 호출자와 `FakeDatabase` 가 있다.
- 테스트에서 실제 `genviewer.env` 를 읽게 두지 마라. 이유: 개발 PC 의 비밀번호가 `os.environ` 에 들어가 다른 테스트로 샌다.
- 기존 테스트를 깨뜨리지 마라.
