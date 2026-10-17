# Step 0: cli-verbose-scrub

## 배경 (phase 7 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 7은 2026-10-17 `docs/notes/known-issues.md` 분류에서 Qt를 쓰지 않는 계층(`cli.py`, `service/`, `service/repo/`, `utils/exporter.py`, `utils/lisp.py`)에 남은 항목을 한 step에 하나씩 처리한다. 항목은 두 종류다.

- **버그**(승인 없이 고친다): K31, K6, K5, K9, K13. 분석에서 나온 **주장**이다. 재현부터 한다.
- **사용자가 승인한 동작 변경**(2026-10-17): K1, K3, K10, K32, K12. step 파일에 적힌 승인 문장대로만 바꾼다. 새 동작을 단언하는 테스트를 먼저 쓰고 실패를 본 뒤 구현한다(TDD).

모든 step에 같은 규칙이 적용된다.
1. 버그 step: 실패하는 테스트로 먼저 재현하고 RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 버그를 증명하지 못한다.
2. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
3. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 보고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
4. 승인 step: 승인 문장 밖의 동작(기존 문구, 종료 코드, 다른 명령)을 바꾸지 않는다. 새 문구는 그 step 파일에 적힌 것만 쓴다.
5. DB step(3·4·5·6·7): `GENDB_TEST_PG_DSN`(관리자 DSN)이 있어야 한다. 없으면 코드를 고치지 말고 `"status": "blocked"` 로 멈춘다. DB 테스트가 skip된 것은 통과가 아니다(`-rs` 로 확인한다). SQL은 PostgreSQL 10~15에서 돌아야 하고, 식별자는 `psycopg.sql` 과 `schema.TABLE_COLUMNS`/`child_tables()` 로만 조립하며, 값은 바인드 파라미터로만 넘긴다. 쓰기는 `device.version` 잠금과 `change_log` 기록을 같은 트랜잭션에서 한다.
6. 고쳤으면 `docs/notes/known-issues.md` 에서 그 K 행을 지운다(재현 안 됐으면 남기고 summary에 적는다). 사용자에게 보이는 동작이 바뀌면 README 의 해당 절을 고친다. CLAUDE.md 의 테스트 기준선 숫자는 고치지 않는다(phase 마무리에서 고친다).
7. 이 파일의 행 번호는 2026-10-17(phase 5 직후) 기준 대략값이다. 앞 step 이 같은 파일을 바꿨을 수 있다(`cli.py`: step 0·1·4, `service/pool.py`: 2, `repo/audit.py`: 3·4·6·7, `repo/io.py`: 5·6). 이름으로 찾고, 앞 step 의 summary(`phases/7-service-fixes/index.json`)를 먼저 읽어라.
8. 비밀번호를 화면·로그·argv에 남기지 마라. 예외 문구는 `user_message(exc)`, DSN·접속 문자열은 `utils.logs.scrub()` 을 거친다(CLAUDE.md CRITICAL).

DB 테스트는 `tests/conftest.py` 의 `pg_dsn`(세션마다 만드는 `gendb_test_<pid>` DB 의 DSN)과 `db`(스키마가 적용된 빈 `Database`, 테스트마다 TRUNCATE) fixture를 쓴다.

## 이 step의 목적

(버그 K31) `genviewer -v …` 가 실패할 때 찍는 트레이스백이 `scrub()` 을 거치게 한다. 지금은 예외 문자열(접속 실패면 conninfo, 비밀번호 포함)이 그 터미널에 그대로 나올 수 있다.

## 읽어야 할 파일

- `/CLAUDE.md`(비밀번호 규칙), `/docs/ADR.md`(ADR-012 CLI, ADR-013 비밀번호를 포매터에서 가린다)
- `src/genviewer/cli.py`
  - `_verbose` 전역 (~55), `root` 콜백이 `-v` 를 받는 곳 (~91-105)
  - `_fail` (~466-472): `if _verbose: traceback.print_exc()` 다음에 `user_message(exc)` 한 줄
  - `main` (~475-495): `_fail` 을 `except` 블록 안에서 부른다
- `src/genviewer/utils/logs.py` — `scrub` (~43-50): `password=…`, `PGPASSWORD=…`, URL 안의 비밀번호를 가린다
- `tests/test_cli.py`
  - `test_an_unexpected_failure_becomes_one_line` (~139-150): `_verbose` 가 False 인 경로만 본다
  - `_main_failing_with` (~153-179): `main()` 을 실패시키는 헬퍼

## 버그

```python
def _fail(exc: BaseException) -> None:
    if _verbose:
        traceback.print_exc()
    # str(exc) 를 쓰면 안 된다. ...
    typer.echo(f"오류: {user_message(exc)}", err=True)
```

`traceback.print_exc()` 는 예외 메시지를 그대로 stderr 에 쓴다. 예외 문자열에 `password=topsecret` 이나 `postgresql://u:topsecret@host/db` 가 들어 있으면 `-v` 를 준 터미널에 비밀번호가 찍힌다. 그 아래 `오류:` 줄은 `user_message` 가 가리므로, 같은 출력 안에서 한쪽만 가려진다.

이것은 주장이다. 먼저 재현하라.

## 작업

### 1. 실패하는 테스트 (`tests/test_cli.py`, DB 불필요)

- `monkeypatch.setattr(cli, "_verbose", True)` 로 `-v` 상태를 만든다.
- **반드시 `except` 블록 안에서** `_fail` 을 부른다. `main()` 이 실제로 그렇게 부른다. 블록 밖에서 부르면 수정 전의 `print_exc()` 가 `NoneType: None` 만 찍어 테스트가 헛되이 통과한다.
  ```python
  try:
      raise RuntimeError("connection failed: password=topsecret")
  except RuntimeError as exc:
      with pytest.raises(SystemExit):
          cli._fail(exc)
  ```
- `capsys.readouterr().err` 에 대해 단언한다.
  - `"topsecret"` 이 없다.
  - `"Traceback"` 은 있다. `-v` 의 쓸모가 사라지면 안 된다.
  - 마지막 줄은 지금처럼 `오류:` 로 시작한다.
  - 종료 코드는 1이다.
- `parametrize` 로 두 형태를 다 본다: `password=topsecret` 과 `postgresql://someone:topsecret@127.0.0.1:1/x`.
- 수정 전에는 `"topsecret" not in err` 단언이 실패해야 한다. 그 출력을 summary에 적는다.

### 2. 수정 (`src/genviewer/cli.py` `_fail`)

- `-v` 일 때 트레이스백 문자열을 만든 뒤 `scrub()` 을 거쳐 stderr 로 쓴다.
- 트레이스백은 인자로 받은 `exc` 에서 만든다(`traceback.format_exception(exc)`). 그래야 `except` 블록 밖에서 불려도 같은 내용이 나온다.
- 출력 순서(트레이스백 → `오류:` 한 줄), 종료 코드 1, `오류:` 문구는 그대로 둔다.

### 3. 변이 검사

- `print_exc()` 로 되돌리면 새 테스트가 실패하는지 본다.
- `scrub(...)` 만 빼도 실패하는지 본다.
- 둘 다 손으로 되돌린다.

### 4. 문서

- README `## 명령줄` 의 "실패는 한 줄 문장으로 나온다. 트레이스백까지 보려면 `-v` 를 준다." 뒤에 "(그때도 비밀번호는 가려진다)" 를 붙인다.
- `docs/notes/known-issues.md` 의 K31 행을 지운다.

## Acceptance Criteria

```bash
uv run pytest tests/test_cli.py -q        # 새 테스트 통과 (수정 전에는 실패해야 한다)
uv run ruff check src tests
uv run pytest -q                          # 전체 통과 (DSN 이 있으면 -rs 로 DB 테스트가 돌았는지 본다)
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - `cli.py` 가 모듈 수준에서 PySide6 를 import 하지 않는가?
   - `str(exc)` 를 화면에 내는 새 경로가 생기지 않았는가?
3. 결과에 따라 `phases/7-service-fixes/index.json` 의 step 0을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "cli._fail: -v 트레이스백을 format_exception(exc) → scrub() 으로 출력. RED: <테스트 이름>[<형태>] (assert 'topsecret' not in err 실패). 변이: print_exc 복원 → 실패, scrub 제거 → 실패. DB 테스트: <N passed | 안 돎(DSN 없음)>"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `-v` 에서 트레이스백을 없애거나 줄이지 마라. 이유: 사용자가 일부러 켜는 진단 출력이다. 가리는 것은 비밀번호뿐이다.
- `user_message` 나 `오류:` 문구, 종료 코드를 바꾸지 마라. 이유: 이 step 의 범위가 아니다(ADR-015).
- 가리기를 `_fail` 밖(예: typer 전역 설정)으로 옮기지 마라. 이유: 다른 출력까지 바뀐다.
- 기존 테스트를 깨뜨리지 마라.
