# Step 2: cli-oserror

## 배경 (phase 0 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 0은 Qt를 쓰지 않는 계층(`service/`, `cli.py`, `utils/logs.py`)의 버그 넷을 하나씩 고친다.

모든 step에 같은 규칙이 적용된다.
1. 아래 "버그"는 **분석 에이전트의 주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 버그를 증명하지 못한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.

## 이 step의 목적

Windows에서 잘못된 파일 이름(`out?.csv`, `a:b.csv`)으로 `genviewer export`·`genviewer log --out` 을 실행하면, 지금은 파일도 메시지도 없이 종료 코드 0으로 끝난다. 이것을 다른 실패와 똑같이 "오류: …" 한 줄과 종료 코드 1로 끝나게 한다. 파이프가 먼저 닫힌 경우(`genviewer processes | head`)는 지금처럼 조용히 0으로 끝난다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`(ADR-012 CLI: 종료 코드 0/1/2/130, 실패는 한 줄)
- `src/genviewer/cli.py` — `main()` (~475-494)의 `except OSError` 분기, `_fail()` (~466-472)
- `src/genviewer/utils/exporter.py` — `write_csv` (파일을 연다)
- `src/genviewer/service/errors.py` — `user_message()` (OSError면 `str(exc)` 첫 줄을 쓴다. 파일 이름이 들어간다)
- `tests/test_cli.py` — `test_an_unexpected_failure_becomes_one_line`(`capsys` 로 stderr 확인), `isolated` fixture
- 이전 step에서 수정된 파일: `src/genviewer/service/pool.py`, `src/genviewer/service/env_file.py` (관계없음)

## 버그

```python
except OSError as exc:
    # 파이프를 읽는 쪽이 먼저 닫았다 (genviewer processes 를 head 로 받는 경우).
    # POSIX 는 EPIPE, 윈도우는 EINVAL 로 온다. 앱의 잘못이 아니다.
    if exc.errno not in (errno.EPIPE, errno.EINVAL):
        _fail(exc)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, sys.stdout.fileno())
    raise SystemExit(0) from None
```

Windows에서는 `open("out?.csv", "w")` 도 `OSError(errno.EINVAL, …, "out?.csv")` 를 낸다. click은 EPIPE가 아닌 OSError를 다시 올리므로 이 분기에 닿고, "닫힌 파이프" 로 오인해 stdout을 devnull로 돌린 뒤 **exit 0** 으로 끝난다. 사용자는 성공했다고 믿지만 파일은 없다. 파이프 쓰기 실패와 파일 열기 실패는 `exc.filename` 으로 구분할 수 있다. 파일 열기 실패는 파일 이름이 있고, stdout 쓰기 실패는 없다.

## 작업

### 1. 테스트 먼저 (`tests/test_cli.py`)

`cli.app` 을 예외를 내는 가짜 함수로 monkeypatch하고 `cli.main()` 을 부른다. DB는 필요 없다.

- `OSError(errno.EINVAL, "Invalid argument", "out?.csv")` → `SystemExit` 코드 **1**, stderr에 `오류:` 와 `out?.csv` 가 있다.
- `OSError(errno.EINVAL, "Invalid argument")`(파일 이름 없음, Windows의 닫힌 파이프) → 코드 **0**, stderr에 `오류:` 없음.
- `BrokenPipeError(errno.EPIPE, "Broken pipe")`(파일 이름 없음) → 코드 **0**. 인자 없는 `BrokenPipeError()` 는 `errno` 가 None이라 실제 파이프 오류 모양이 아니다. 쓰지 마라.
- `OSError(errno.EACCES, "Permission denied", "out.csv")` → 코드 1(지금도 그렇다. 회귀 방지).
- 코드 0 경로는 `os.dup2(devnull, sys.stdout.fileno())` 를 부른다. 그러니 테스트가 pytest의 진짜 stdout을 devnull로 돌리지 않게 `cli.os.dup2` 와 `cli.os.open` 을 기록만 하는 가짜로 바꾸고, `cli.sys.stdout` 은 `fileno()` 를 가진 가짜 객체로 바꾼다. 이유: capsys 아래의 `sys.stdout` 은 `fileno()` 가 없어 `io.UnsupportedOperation` 이 나고, 진짜로 dup2하면 이후 테스트 출력이 사라진다.
- Windows 전용 확인(`@pytest.mark.skipif(sys.platform != "win32", ...)`): 가짜 `app` 안에서 진짜 `write_csv(tmp_path / "out?.csv", ["a"], [["1"]])` 를 부른다. 실제 Windows 예외 모양(EINVAL + filename)에서도 코드 1이고 stderr에 `오류:` 가 있다. 이 테스트가 수정 전에 실패해야 RED다.

### 2. 수정 (`cli.py` 의 `main()`)

- "닫힌 파이프" 로 보고 조용히 0으로 끝내는 것은 errno가 EPIPE 또는 EINVAL **이고** `exc.filename is None` 일 때뿐이다. 그 밖의 OSError는 모두 `_fail(exc)` 로 간다(한 줄 오류, 코드 1).
- 주석을 이 기준에 맞게 고친다(파일 열기 실패와 구분하는 이유를 한 줄로).

### 3. 문서

- README "명령줄" 절의 종료 코드 설명(0/1/2/130)은 그대로 맞다. 바꿀 것이 없다.

## Acceptance Criteria

```bash
uv run pytest tests/test_cli.py -q         # 새 테스트 통과 (수정 전에는 EINVAL+filename 경우가 실패해야 한다)
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `cli.py` 가 모듈 수준에서 PySide6를 import하지 않는가(`test_importing_the_cli_does_not_load_qt`)?
   - 오류 문구가 `user_message()` 를 거치는가(비밀번호 노출 금지)?
3. 결과에 따라 `phases/0-service-fixes/index.json` 의 step 2를 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "cli.main: filename 있는 OSError 는 파이프로 보지 않고 exit 1. RED: <테스트 이름>"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- EINVAL을 조건에서 아예 빼지 마라. 이유: Windows에서 `genviewer processes | head` 처럼 읽는 쪽이 먼저 닫힌 파이프는 정말로 EINVAL로 온다. 그것까지 오류로 만들면 동작이 바뀐다.
- `KeyboardInterrupt` 분기("중단했다.")나 typer가 EPIPE를 exit 1로 바꾸는 동작을 손대지 마라. 이유: 이 step의 범위가 아니고, 분석에서 표시 문제(cosmetic)로만 분류됐다.
- `export`·`log --out` 명령 쪽에 파일 이름 검사를 새로 넣지 마라. 이유: 실패를 정확히 알리는 것이 목적이지 입력 검증 기능을 더하는 것이 아니다.
- 기존 테스트를 깨뜨리지 마라.
