# Step 3: log-dir-chmod

## 배경 (phase 0 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 0은 Qt를 쓰지 않는 계층(`service/`, `cli.py`, `utils/logs.py`)의 버그 넷을 하나씩 고친다.

모든 step에 같은 규칙이 적용된다.
1. 아래 "버그"는 **분석 에이전트의 주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 버그를 증명하지 못한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.

## 이 step의 목적

`GENDB_LOG` 로 로그 파일을 기본 위치(`~/.genviewer/genviewer.log`) 밖으로 옮겼을 때 파일 로그가 꺼지거나 남의 디렉터리 권한이 바뀌지 않게 한다. 배포본은 런처로 떠서 붙어 있는 터미널이 없으므로, 파일 로그가 꺼지면 에러가 아무 데도 남지 않는다(ADR-013).

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`(ADR-013)
- `src/genviewer/utils/logs.py` — `LOG_ENV`, `DEFAULT_DIR`, `DEFAULT_NAME`, `log_path()`, `setup()` (~71-116). 특히 `target.parent.mkdir(...)` 다음의 `if os.name != "nt": os.chmod(target.parent, 0o700)` (~99-102)와 `except OSError` → `return None`
- `src/genviewer/main.py` — `logs.setup()` 호출 (~81, 인자 없음 → `log_path()`)
- `tests/test_logs.py` — `restore_root_logger` fixture, `test_setup_writes_the_message_to_the_file`, `test_setup_survives_a_path_it_cannot_open`
- 이전 step에서 수정된 파일: `src/genviewer/service/pool.py`, `service/env_file.py`, `cli.py` (관계없음)

## 버그

`setup()` 은 로그 파일의 부모 디렉터리가 무엇이든 리눅스에서 `chmod 0700` 한다. 주석은 "홈 밑의 디렉터리다" 라고 가정한다.
- `GENDB_LOG=/tmp/genviewer.log`: `/tmp` 는 root 소유라 `os.chmod` 가 `PermissionError` 를 낸다. 같은 `try` 의 `except OSError` 가 이것을 받아 `None` 을 돌려주므로 **파일 로그가 통째로 꺼진다**. 쓸 수 있는 디렉터리인데도 그렇다. 경고는 stderr로만 가는데, 런처로 띄운 앱에는 stderr가 보이지 않는다.
- `GENDB_LOG=$HOME/team-logs/me.log` 처럼 사용자가 소유한 공유 디렉터리면, 그 디렉터리가 조용히 0700이 되어 팀원이 못 읽는다.

## 작업

### 1. 테스트 먼저 (`tests/test_logs.py`)

Windows에서도 리눅스 분기를 타게 해야 RED가 보인다. **전역 `os.name` 을 바꾸지 말고**, `utils/logs.py` 가 쓰는 `os` 이름만 프록시로 바꾼다.

```python
class _PosixOs:  # 테스트 안 헬퍼: name 만 "posix", chmod 는 기록하거나 실패, 나머지는 진짜 os 에 위임
    name = "posix"
    def __init__(self, real, chmod): ...
    def __getattr__(self, attr): ...
# monkeypatch.setattr(logs, "os", _PosixOs(os, chmod=...))
```

- 기본 위치가 아닌 경로(`setup(path=tmp_path / "elsewhere" / "gv.log")`)에서 chmod가 `PermissionError` 를 내도 `setup()` 은 그 경로를 돌려주고 파일 핸들러가 붙어 있다(로그 한 줄을 쓰고 파일에서 읽어 확인). **수정 전에는 `None` 이 나와 실패해야 한다.**
- 같은 경우에 chmod는 아예 불리지 않는다(기록이 비어 있다). 사용자가 고른 디렉터리의 권한을 바꾸지 않는다.
- 기본 위치: `Path.home()` 을 `tmp_path` 로 바꾸고(`monkeypatch.setattr(logs.Path, "home", ...)` 등) 인자 없이 `setup()` 을 부르면 `chmod(<tmp_path>/.genviewer, 0o700)` 이 정확히 한 번 기록된다(지금 동작 유지).
- 기본 위치에서 chmod가 실패해도 파일 로그는 켜진다.
- `restore_root_logger` fixture가 핸들러를 정리하는지 확인하고, 새 테스트도 그 아래서 돈다.

### 2. 수정 (`utils/logs.py` 의 `setup()`)

- `chmod 0700` 은 **기본 로그 디렉터리(`Path.home() / DEFAULT_DIR`)일 때만** 한다. `GENDB_LOG` 나 `path=` 로 다른 곳을 가리키면 권한을 건드리지 않는다.
- chmod가 실패해도 파일 로그를 끄지 않는다. 디렉터리를 만들거나 파일을 여는 데 실패했을 때만 지금처럼 `None` 을 돌려준다.
- `os.name != "nt"` 조건(Windows는 chmod 안 함)은 유지한다.
- 주석("홈 밑의 디렉터리다")을 실제 조건에 맞게 고친다.

### 3. 문서

- README "에러와 로그" 표는 그대로 맞다. `logs.py:19` 의 "런처가 GENDB_CONFIG 만 넘기므로" 주석은 phase 1 step 0이 정리하므로 **여기서는 건드리지 않는다**.

## Acceptance Criteria

```bash
uv run pytest tests/test_logs.py -q        # 새 테스트 통과 (수정 전에는 PermissionError 경우가 실패해야 한다)
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `utils/logs.py` 가 stdlib만 쓰는가(티어 0)?
   - 비밀번호 가림(`ScrubbingFormatter`) 동작이 그대로인가(기존 테스트)?
3. 결과에 따라 `phases/0-service-fixes/index.json` 의 step 3을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "logs.setup: 기본 디렉터리만 chmod 0700, chmod 실패가 파일 로그를 끄지 않음. RED: <테스트 이름>"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `monkeypatch.setattr(os, "name", "posix")` 처럼 전역 `os.name` 을 바꾸지 마라. 이유: Python 3.13의 `pathlib.Path()` 가 `os.name` 을 보고 `PosixPath` 를 골라 Windows에서 "cannot instantiate 'PosixPath'" 로 터진다.
- 기본 디렉터리의 chmod 0700을 없애지 마라. 이유: 홈 밑의 로그는 남이 읽을 이유가 없다는 기존 의도다. 바꾸는 것은 다른 위치일 때뿐이다.
- 로그 파일 위치·크기·보관 개수(`MAX_BYTES`, `BACKUP_COUNT`)를 바꾸지 마라. 이유: 이 step의 범위가 아니다.
- 기존 테스트를 깨뜨리지 마라.
