# Step 0: pool-acquire

## 배경 (phase 0 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 0은 Qt를 쓰지 않는 계층(`service/`, `cli.py`, `utils/logs.py`)의 버그 넷을 하나씩 고친다.

모든 step에 같은 규칙이 적용된다.
1. 아래 "버그"는 **분석 에이전트의 주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 버그를 증명하지 못한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.

## 이 step의 목적

`Database.connection()` 이 풀에서 커넥션을 얻지 못했을 때 사용자에게 "데이터베이스에 접속할 수 없다. 서버 상태와 접속 설정을 확인할 것." 이 보이게 한다. 지금은 그 변환 코드가 죽어 있어서 psycopg_pool의 영어 문구("couldn't get a connection after 5.00 sec")만 나온다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ARCHITECTURE.md`(풀 절), `/docs/ADR.md`(ADR-008, ADR-013)
- `src/genviewer/service/pool.py` — `Database.connection()` (~60-67), `ping()` (~69-76)
- `src/genviewer/service/errors.py` — `DbUnavailableError`, `user_message()`, `_UNAVAILABLE`
- `src/genviewer/controllers/device_tab.py` — `_open_database` (~130-136), `connect_db` 의 except 주석 (~146-155). "OperationalError 만 DbUnavailableError 로 바뀌므로" 라고 이 변환을 전제한다
- `src/genviewer/service/diagnostics.py` — `probe` (모든 예외를 `user_message` 로 바꾼다)
- `tests/test_logs.py` — `test_user_message_handles_db_unavailable`
- 설치된 `psycopg_pool` 의 `ConnectionPool.connection` (`.venv/Lib/site-packages/psycopg_pool/pool.py`). `@contextmanager` 이고 `PoolTimeout` 은 `psycopg.OperationalError` 의 하위 클래스다.

## 버그

`pool.py` 는 이렇게 되어 있다.

```python
def connection(self):
    if self._pool.closed:
        self._pool.open()
    try:
        return self._pool.connection(timeout=self.cfg.connect_timeout)
    except psycopg.OperationalError as e:
        raise DbUnavailableError(str(e)) from e
```

`self._pool.connection(...)` 은 제너레이터 기반 컨텍스트 매니저를 **만들기만** 한다. 커넥션 획득(`getconn`)과 `PoolTimeout` 은 호출자의 `with` 가 `__enter__` 할 때 일어난다. 그래서 이 `except` 는 절대 실행되지 않는다. `PoolTimeout` 이 그대로 올라가고, `user_message()` 는 sqlstate도 없고 `DbUnavailableError` 도 아니라서 영어 원문을 보여준다.

재현: 닫힌 포트(`127.0.0.1:1`)로 `Database` 를 만들고 `with db.connection():` 에 들어가면 `DbUnavailableError` 가 아니라 `psycopg_pool.PoolTimeout` 이 난다.

## 작업

### 1. 테스트 먼저 (`tests/test_pool.py`, 새 파일, DB 불필요)

- 닫힌 포트: `DbConfig(dsn="host=127.0.0.1 port=1 dbname=x user=x", connect_timeout=1, pool_min=1, pool_max=1)` 로 `Database` 를 만든다. `with db.connection():` 이 `DbUnavailableError` 를 낸다. `__cause__` 는 `PoolTimeout`(또는 `psycopg.OperationalError`)이고, `user_message(exc)` 에 "접속할 수 없다" 가 들어 있다. 테스트 끝에 반드시 `db.close()` 한다(`finally` 또는 fixture). 이유: 닫지 않으면 풀 워커 스레드가 인터프리터 종료를 붙잡는다.
- 본문 예외는 그대로: `db._pool` 을 가짜로 바꾼다. 가짜는 `closed=False` 이고, `connection(timeout=...)` 이 더미 커넥션을 yield하는 `@contextmanager` 다.
  - `with db.connection(): raise psycopg.OperationalError("boom")` → **`psycopg.OperationalError`**(`DbUnavailableError` 아님)
  - `with db.connection(): raise StaleWriteError([])` → `StaleWriteError`
  - 가짜의 `__exit__` 쪽(yield 뒤)에서 `psycopg.OperationalError` 가 나면(commit 실패 흉내) → 타입이 그대로
  - 정상 종료면 `with` 가 더미 커넥션을 돌려준다
- `ping()` 은 닫힌 포트에서 여전히 `False` 를 돌려준다(예외를 내지 않는다).

### 2. 수정 (`service/pool.py`)

```python
def connection(self) -> AbstractContextManager[psycopg.Connection]: ...
```

- 지금처럼 컨텍스트 매니저 하나가 트랜잭션 하나다(정상 종료 commit, 예외 rollback). 이것은 psycopg_pool이 하므로 그대로 위임한다.
- **커넥션 획득(풀 컨텍스트 매니저의 `__enter__`)에서 난 `psycopg.OperationalError` 만** `DbUnavailableError(str(e))` 로 바꾸고 `from e` 로 원인을 잇는다.
- `with` 본문에서 난 예외와 commit/rollback(`__exit__`)에서 난 예외는 **타입을 바꾸지 않는다**.
- `closed` 면 `open()` 하는 기존 동작은 유지한다.
- `ping()` 은 바꿀 필요가 없을 것이다. 확인만 한다.

### 3. 문서

- `docs/notes/known-issues.md` K3은 그대로 둔다. 이 step은 "접속할 수 없다" 문구만 고치고, 실제 원인(28P01 등)을 보여주는 일은 하지 않는다.

## Acceptance Criteria

```bash
uv run pytest tests/test_pool.py -q        # 새 테스트 통과 (수정 전에는 닫힌 포트 테스트가 실패해야 한다)
uv run ruff check src tests                # 린트 통과
uv run pytest -q                           # 전체 통과 (DB 테스트는 skip 가능)
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `service/pool.py` 가 여전히 PySide6를 import하지 않는가?
   - CLAUDE.md CRITICAL 규칙(비밀번호 노출 금지 등)을 위반하지 않았는가? `DbUnavailableError(str(e))` 의 문자열은 화면에 나갈 때 `user_message()` 가 `scrub()` 한다.
3. 결과에 따라 `phases/0-service-fixes/index.json` 의 step 0을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "pool.connection 획득 실패만 DbUnavailableError 로 변환. RED: <테스트 이름>. tests/test_pool.py 추가"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `with` 본문 전체를 `try/except psycopg.OperationalError` 로 감싸지 마라. 이유: 쿼리 중 끊김(57P01)·타임아웃(57014, 55P03)·`StaleWriteError` 까지 "서버에 접속할 수 없다" 로 바뀌어, `user_message` 의 SQLSTATE별 안내가 사라진다.
- 실패 원인을 보여주려고 직접 `psycopg.connect` 를 한 번 더 시도하는 등 새 동작을 넣지 마라. 이유: 버그 수정 범위를 넘는다(known-issues K3, 별도 승인 필요).
- `DbConfig` 기본값(타임아웃, 풀 크기)이나 풀 생성 인자를 바꾸지 마라. 이유: ADR-008의 의도된 값이다.
- 실제 PostgreSQL 서버가 필요한 테스트를 만들지 마라. 이유: 닫힌 포트와 가짜 풀로 충분하고, 개발 PC에 DB가 없어도 RED가 보여야 한다.
- 기존 테스트를 깨뜨리지 마라.
