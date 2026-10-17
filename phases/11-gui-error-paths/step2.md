# Step 2: connect-failure-pool

## 배경 (phase 11 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 11은 2026-10-17에 `docs/notes/known-issues.md` 를 분류하면서 고치기로 한 GUI 오류 경로 항목을 한 step에 하나씩 다룬다. 버그(K34·K35, K22 일부)와 **사용자가 2026-10-17 승인한 동작 변경**(K3의 GUI 쪽, K21, K16 내보내기 형식, K18)이 섞여 있다.

phase 0~10이 끝나 있다. 이 phase에 닿는 것:
- phase 7 step 2(`pool-failure-cause`): 풀에서 커넥션을 얻지 못하면 `Database.connection()` 이 한 번 직접 접속해 실제 원인을 `DbUnavailableError` 에 담는다.
- phase 10: 저장·편집 보호. phase 10 step 4가 `connect_db` 앞에 질문(편집이 있을 때)을 넣었다.
- step 0(이 phase): 예외 문자열이 `user_message` 를 거친다. step 1(이 phase): `_open_database` 와 Connect 창 연결 테스트가 원인이 담긴 예외를 보인다. **`_open_database` 의 확인 방법을 step 1이 바꿨다.**

모든 step에 같은 규칙이 적용된다.
1. 버그는 **주장**이다. 먼저 실패하는 테스트로 재현하고 RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라.
5. 이 파일의 행 번호는 2026-10-17(phase 6 전) 기준 대략값이다. 이름으로 찾아라.
6. `DeviceTabController.connect_db`/`_open_database` 는 phase 7·10·11·12가 차례로 건드린다. 이 파일은 그 본문을 인용하지 않는다. 지금 코드를 읽고, 적힌 불변식만 지켜라.

GUI 테스트 기반(phase 2)의 이름을 그대로 쓴다(`dialogs`, `device_tab_ctrl`, `main_window`, `store`, `store.fail_next`, `install_fake_db`). `install_fake_db` 는 `_open_database` 를 `store.open_database` 로 바꾸므로 fixture 안에서는 `_open_database` 본문이 돌지 않는다. `tests/gui_support/fakes.py` 의 `FakeDatabase` 는 `closed`·`close_count` 를 기록한다. 고정 대기(`qtbot.wait`) 금지.

## 이 step의 목적

K22 중 "접속 실패 시 연 풀을 닫지 않는다" 를 고친다. 버그(2026-10-17 분류).

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ARCHITECTURE.md`("DB 접속", "풀"), `/docs/ADR.md`(ADR-009 phase 4 보강)
- `src/genviewer/controllers/device_tab.py`: `_open_database`(step 1이 바꿨다), `connect_db`, `close_db` 의 docstring(닫지 않은 풀이 종료를 멈추게 한 이력)
- `src/genviewer/service/pool.py`: `Database.open()`/`close()`(이미 닫혔으면 아무것도 하지 않는다), `ConnectionPool(open=False)`
- `tests/gui/test_connect_failure.py`(step 1이 만들었다. `OPEN_DATABASE` 와 가짜 `Database`·`load_config` 준비를 재사용한다)
- `tests/gui/test_connect_db.py`

## 버그

`DeviceTabController._open_database` 는 워커 스레드에서 다음 순서로 돈다.
1. `Database(load_config(dsn))` 를 만든다.
2. `open()` 한다. 풀이 백그라운드 접속 워커를 띄운다.
3. 확인한다.

확인이 실패하면 예외만 내고 그 Database를 닫지 않는다. 결과는 다음과 같다.
- 실패할 때마다 열린 풀이 하나씩 남는다. Connect… 를 여러 번 실패하면 여러 개가 남는다.
- 그 풀의 워커는 죽은 서버에 계속 다시 붙으려 한다.
- 종료할 때 `ConnectionPool.__del__` 이 워커 스레드를 join 하려다 멈출 수 있다. 이것은 `close_db` docstring 의 증상이다.

이것은 주장이다. 먼저 재현하라.

## 작업

### 불변식

- `_open_database` 안에서 Database를 만든 뒤 어떤 예외가 나도(`open()` 실패, 확인 실패, 확인이 낸 다른 예외) 그 Database를 닫고 **원래 예외를 그대로** 올린다.
- 닫다가 예외가 나면 로그에만 남기고 원래 예외를 올린다(close 예외가 원인을 가리면 안 된다).
- `load_config` 나 `Database(...)` 생성자가 실패하면 닫을 것이 없다. 원래 예외 그대로다.
- 성공하면 닫지 않는다(지금처럼 연 Database를 돌려준다).
- `connect_db` 의 나머지 동작은 그대로다. 재접속 실패에서 지금 DB를 그대로 쓰고 닫지 않는다(phase 4 G13).

| 경우 | 새 Database | 올라가는 예외 | 지금 DB(재접속일 때) |
|---|---|---|---|
| 성공 | 열린 채 반환 | 없음 | 도는 폴링이 끝난 뒤 닫힘(지금과 같다) |
| 확인 실패(원인 담긴 `DbUnavailableError`) | **닫힘** | 그 예외 | 그대로(닫히지 않음) |
| `open()` 이 예외 | **닫힘**(이미 닫혔으면 아무 일 없음) | 그 예외 | 그대로 |
| `load_config` 예외 | 만들어지지 않음 | 그 예외 | 그대로 |
| close 가 예외 | 닫기 시도함, 로그 남김 | 원래 예외 | 그대로 |

### 1. 테스트 먼저 (`tests/gui/test_connect_failure.py` 에 더한다)

- step 1의 가짜 `Database`(확인 실패)가 만든 인스턴스를 테스트가 잡을 수 있게 한다(리스트에 모으는 팩토리).
- **확인 실패**: `OPEN_DATABASE("host=h")` 가 예외를 낸 뒤 만든 가짜의 `close_count == 1` 이다. **수정 전에는 0이라 실패해야 한다.**
- **`open()` 예외**: `open()` 이 `DbUnavailableError("down")` 을 내는 가짜면 같은 예외가 올라오고 `close_count == 1` 이다.
- **close 예외**: `close()` 가 `RuntimeError` 를 내는 가짜면 올라오는 예외는 원래 접속 실패 예외다.
- **재접속 경로**
  - 준비: `main_window` 에서 `_open_database` 를 `OPEN_DATABASE` 로 돌려놓는다.
  - 동작: 실패하는 Connect… 를 두 번 한다.
  - 단언: 만든 가짜 둘이 모두 닫혔고, 지금 DB(`main_window.device_tab.db`)는 `close_count == 0` 이다.
- **회귀**: 성공하는 가짜면 `close_count == 0` 이고 반환된다. `tests/gui/test_connect_db.py` 가 그대로 통과한다.

### 2. 수정

- `controllers/device_tab.py` `_open_database` 만 고친다. 위 불변식대로 실패 경로에서 새 Database를 닫는다.
- 닫기는 워커 스레드에서 일어난다(지금 이 함수가 도는 곳). 풀 워커가 접속을 시도하는 중이면 `close()` 가 잠시 걸릴 수 있다. 실측 시간을 summary에 적는다.

### 3. 문서

- 없다(K22의 이 부분은 phase 마무리에서 known-issues에서 지운다).

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_connect_failure.py tests/gui/test_connect_db.py -q   # 새 테스트 통과 (수정 전에는 close_count 단언이 실패해야 한다)
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 지금 DB를 닫는 순서(새 DB를 먼저 열고, 성공했을 때만 폴링을 기다린 뒤 옛 DB를 닫는다)가 그대로인가(ARCHITECTURE "DB 접속")?
   - 원래 예외가 바뀌지 않고 올라가는가? 로그 패널 문구가 바뀌지 않았는가?
   - `service/` 를 바꾸지 않았는가?
3. 결과에 따라 `phases/11-gui-error-paths/index.json` 의 step 2를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "_open_database 가 실패 경로에서 새 Database 를 닫고 원래 예외를 올림. RED: <테스트 이름: close_count 단언>. 변이: <…>. close 실측 <N>ms"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 지금 쓰는 DB(`self.db`)를 실패 경로에서 닫지 마라. 이유: 재접속에 실패하면 지금 DB를 계속 쓴다(phase 4 G13, ADR-009).
- close 예외로 원래 예외를 바꾸지 마라. 이유: 사용자에게 보이는 원인(step 1)이 사라진다.
- `connect_db` 의 순서(질문 → 새 DB 열기 → 옛 DB 정리 → `dbChanged`)를 바꾸지 마라. 이유: phase 4·10이 고정한 순서이고 History(phase 12)가 기대한다.
- `Database`·`ConnectionPool` 설정(`service/pool.py`)을 바꾸지 마라. 이유: 이 step의 범위가 아니다.
- 기존 테스트를 깨뜨리지 마라.
