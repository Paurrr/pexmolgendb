# Step 4: cli-text

## 배경

phase 24는 사용자가 2026-10-22에 요청하고 승인한 변경이다. 사용자에게 보이는 문구를 영어로 바꾼다(ADR-020). 이 step은 **CLI**(`genviewer` 서브커맨드)를 맡는다. 대상은 `--help`, 출력, 프롬프트, `status`/`--check-config` 진단 줄이다.

먼저 `phases/24-english-text/index.json` 의 summary를 읽어라. step 0이 `user_message` 와 `io.py` 의 CSV 없음 문구를 이미 바꿨다.

**범위 메모**
- typer는 명령 함수의 docstring을 `--help` 문구로 쓴다. 그래서 `cli.py` 의 **명령 docstring**(status, processes, load, export, log)은 영어로 바꾼다. 다른 docstring과 주석은 한국어로 둔다.
- `genviewer log` 의 요약 문장은 `change_log.summary` 에 저장된 데이터다. 한국어 그대로 둔다(ADR-020).
  - 바꾸는 것은 `audit.format_line` 의 `(모름)` 하나와 `log --out` CSV의 머리글이다.
- 운영 서버 콘솔은 cp949일 수 있다. 출력은 ASCII만 쓴다.

phase 24 공통 규칙:
1. 승인된 변경이라 RED 대신 변이 검사를 한다. 바꾼 문구 하나를 손으로 되돌려, 고친 테스트가 실패하는지 본다. `git checkout`/`git stash` 로 되돌리지 마라.
2. 대상 파일의 한글 문자열을 `rg -n "[가-힣]" <파일>` 로 찾는다.
   - 주석, 명령이 아닌 docstring, 로그 파일 호출은 그대로 둔다.
   - 나머지는 모두 옮긴다.
   - 용어는 `docs/UI_GUIDE.md` "문구" 의 용어표를 따른다.
3. 그 문구를 고정한 테스트를 `rg` 로 찾아 같이 고친다. 같음, 포함, **없음 단언**이 모두 대상이다. 이력 요약 기대값, 테스트 데이터, assert 메시지의 한국어는 그대로 둔다.
4. 다른 step 대상 파일의 문구는 건드리지 않는다. 동작, 옵션 이름, 종료 코드, 출력 줄의 순서와 개수, 이미 영어인 문구도 바꾸지 않는다.
5. README의 CLI 예시는 phase 마무리에서 고친다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`: "문구", `/docs/ADR.md`: ADR-012(CLI), ADR-018(빈 버전), ADR-020
- `src/genviewer/cli.py`(전체)
- `src/genviewer/service/diagnostics.py`: `--check-config`/`status` 줄, `target_summary` 의 `"(libpq 기본값)"`
- `src/genviewer/service/repo/audit.py`: `format_line` 의 `(모름)`. 이 함수 하나만 바꾼다.
- `tests/test_cli.py`, `tests/test_change_log.py`(`format_line` 정확 비교)

## 작업

### 1. 옮길 문구 (대략, 2026-10-22 기준)

**`cli.py`**
- 옵션·인자 help: `--dsn`, 앱 설명, `--host`, `--check-config`, `--verbose`, load/export/log의 각 옵션, metavar `"파일"` → `"FILE"`.
- 명령 docstring 5개: status, processes, load, export, log.
- 출력(대표, 권장 영어)

| 지금 | 영어 |
|---|---|
| `설정 파일 오류: {e}` | `Config file error: {e}` |
| `접속 정보가 없다. …` | `No connection settings. Put a config file in one of the paths above.` |
| `접속 대상: …` | `Target: …` |
| `접속: 됨 (… 초)` | `Connection: ok (…s)` |
| `접속: 안 됨 (… 초)` | `Connection: failed (…s)` |
| `서버:` / `계정:` | `Server:` / `Account:` |
| `스키마: 테이블 {n}개가 없다 (…)` | `Schema: {n} table(s) missing (…)` |
| `genviewer-init-db 를 먼저 실행할 것.` | `Run genviewer-init-db first.` |
| `스키마: 테이블 {n}개 모두 있음` | `Schema: all {n} table(s) present` |
| `내용: process {n}개, device {m}개` | `Contents: {n} process(es), {m} device(s)` |
| `process 가 없다.` | `No processes.` |
| `process {n}개, device {m}개` | `{n} process(es), {m} device(s)` |
| `CSV 파일이 없다: …` | step 0의 `io.py` 와 같은 `CSV file not found: …` |
| `device {n}개를 새로 추가했다 (version {release}).` | `Added {n} device(s) (version {release}).` |
| `device {n}개를 새로 추가했다.` | `Added {n} device(s).` (빈 버전, 흔적 없음) |
| `CSV 는 불러올 때마다 새로 쌓인다 - …` | GUI step 2와 같은 뜻의 영어, ASCII `-` |
| `그런 process 가 없다: {label}` | `No such process: {label}` |
| `있는 버전: …` | `Versions: …` |
| `process {label} 에 device 가 없다.` | `Process {label} has no devices.` |
| `device {n}개를 {out} 에 썼다.` | `Wrote {n} device(s) to {out}.` |
| `시각을 못 읽겠다: …` | `Cannot parse time: …` (뒤의 형식 안내는 그대로) |
| `이력이 없다.` | `No history.` |
| `log --out` CSV 머리글 `시각/사람/출처/동작/테이블/내용/상세` | `Time/Who/Source/Action/Table/Change/Detail` |
| `{n}줄을 {out} 에 썼다.` | `Wrote {n} row(s) to {out}.` |
| `{when} 이전 이력이 없다.` | `No history before {when}.` |
| 확인 `… 이력 {n}줄을 지운다. 계속할까?` | `Delete {n} history row(s) before {when}? Continue?` (typer confirm) |
| `{n}줄을 지웠다.` | `Deleted {n} row(s).` |
| `오류: {user_message(exc)}` | `error: {user_message(exc)}` |
| `중단했다.` | `Aborted.` |

- `log --out` 머리글 중 이미 영어인 process/version/device 머리글은 그대로 둔다.

**`service/diagnostics.py`**
- `(설정됨, 비밀번호가 들어 있어 감춤)` → `(set, hidden: contains a password)`
- `설정 파일:` → `Config file:`
- `(읽지 않음 - --dsn 또는 GENDB_PG_DSN 이 있다)` → `(not read - --dsn or GENDB_PG_DSN is set)`
- `찾아본 곳:` → `Searched:`
- `<-- 이것` → `<-- this one`
- `적용된 값:` → `Values:`
- `=(설정됨)` → `=(set)`
- `(없음)` → `(none)`
- `로그 파일: … (… 로 바꿀 수 있다)` → `Log file: …  (set {LOG_ENV} to change)`
- `(libpq 기본값)` → `(libpq defaults)`
  - phase 23의 상태 표시줄 DB 라벨도 이 글자를 쓴다. 그 테스트가 이 글자를 고정했으면 같이 고친다.

**`service/repo/audit.py`**
- `format_line` 의 `(모름)` → `(unknown)`. 다른 함수(요약을 만드는 device_insert, tab_change, csv_import, process_add 등)는 건드리지 않는다.
- 사람 칸의 폭 맞춤(`_pad`)은 그대로 둔다. 기대 줄의 공백이 바뀌면 테스트를 맞춘다.

### 2. 함께 고칠 테스트

- `tests/test_cli.py`(약 64곳)
  - 정확 비교, 포함 비교, **없음 단언**(~217, ~218, ~346, ~692, ~736, ~833)을 모두 바꾼다.
  - `오류:` 로 시작하는지 보는 곳은 `error:` 로 바꾼다.
- 빈 버전 테스트(`test_load_without_a_release_keeps_its_old_output`, processes 표의 `-` 줄, `"있는 버전: -, V1"` 등)
  - 이름은 그대로 둔다.
  - 기대 글자를 영어로 바꾼다.
  - "버전 흔적이 없다"는 성질은 지금처럼 단언한다(ADR-018).
- `tests/test_change_log.py`: `format_line` 기대값 중 `(모름)` 이 들어간 줄. 요약 문장 부분은 한국어 그대로다.
- `log` 요약을 비교하는 곳(`line.endswith(summary)` 등)은 한국어 요약 그대로 통과해야 한다.

## Acceptance Criteria

```bash
uv run ruff check src tests
uv run pytest tests/test_cli.py tests/test_change_log.py -q
uv run pytest -q -rs   # GENDB_TEST_PG_DSN 이 있어야 한다. test_cli·test_change_log 의 DB 쪽까지
```

- `GENDB_TEST_PG_DSN` 이 비어 있으면 `blocked` 로 멈춘다. skip을 통과로 보지 않는다. 이유: CLI 출력 테스트의 많은 수가 실제 DB를 쓴다.
- 손 확인을 하고 summary에 첫 줄을 적는다.
  - `uv run genviewer --help`
  - `uv run genviewer status --help`
  - `uv run genviewer --check-config`

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - `cli.py` 모듈 수준에서 PySide6를 import하지 않는가(`tests/test_boundaries.py`)?
   - 출력이 ASCII뿐인가(cp949 콘솔)?
   - `scrub`/`user_message` 를 거치는 경로가 그대로인가(비밀번호)?
3. 결과에 따라 `phases/24-english-text/index.json` 의 step 4를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "CLI 문구 영어화(help·명령 docstring·출력·log --out 머리글·error:/Aborted.), diagnostics, audit.format_line (unknown). 요약 문장은 한국어 그대로. 고친 테스트: <파일들>. 변이: <결과>. DB 테스트: <passed/skipped>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요(DSN 없음 등) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 옵션 이름, 서브커맨드 이름, 종료 코드, 출력 줄의 수와 순서를 바꾸지 마라. 이유: 스크립트가 출력에 기댈 수 있다. 이 step은 문구만 옮긴다.
- 이력 요약을 만드는 audit 함수를 바꾸지 마라. 이유: ADR-020.
- `scripts/init_db.py`, `service/schema.py`, `tools/*.sh` 를 바꾸지 마라. 이유: step 5·6의 일이다.
- non-ASCII 글자(em dash, 화살표 등)를 출력에 넣지 마라. 이유: cp949 콘솔에서 죽거나 깨진다.
- 기존 테스트를 깨뜨리지 마라. 문구에 맞춰 기대값만 바꾼다.
