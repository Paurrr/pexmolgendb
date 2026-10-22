# Step 5: init-db-text

## 배경

phase 24는 사용자가 2026-10-22에 요청하고 승인한 변경이다. 사용자에게 보이는 문구를 영어로 바꾼다(ADR-020).

이 step은 **`init_db`**(관리 도구, RHEL 7 서버의 Python 3.9에서 소스로 돈다, ADR-014)의 출력을 맡는다. 단계 라벨도 대상이다. 단계 라벨은 `service/schema.py` 에 있는 SQL 문의 첫 줄 주석이다.

먼저 `phases/24-english-text/index.json` 의 summary를 읽어라.

**알아 둘 것**
- `scripts/init_db.py` 의 `build_plan` 은 SQL 문마다 `_first_line(stmt)` 를 단계 라벨로 쓴다. 라벨은 `--dry-run` 목록과 `ok …`/`skip … (이미 있음)` 줄로 찍힌다.
- `service/schema.py` 에는 한국어 `--` 주석으로 시작하는 문이 셋 있다(~85, ~144, ~282). 이 셋이 화면에 찍힌다.
  - `-- process 에 release 를 더하고 UNIQUE 를 (name, release) 로 바꾼다`
  - `-- device 의 옛 UNIQUE (process_id, name) 을 뗀다`
  - `-- {tbl} 에 빠진 컬럼을 더한다`
- ~144 문 안에는 한국어 `--` 주석 두 줄이 더 있다. 화면에 찍히지는 않지만, step 7의 검사를 단순하게 두려고 **SQL 문자열 안의 한국어는 모두** 영어로 바꾼다.
- Python `#` 주석과 docstring은 한국어로 둔다. 모듈 docstring, 함수 docstring, 대입 뒤의 설명 문자열이 그것이다.

phase 24 공통 규칙:
1. 승인된 변경이라 RED 대신 변이 검사를 한다. 바꾼 라벨 하나를 손으로 되돌려, 고친 테스트가 실패하는지 본다. `git checkout`/`git stash` 로 되돌리지 마라.
2. 대상 파일의 한글 문자열을 `rg -n "[가-힣]" <파일>` 로 찾는다.
   - 주석, docstring, 로그 파일 호출은 그대로 둔다.
   - 나머지는 모두 옮긴다.
   - 용어는 `docs/UI_GUIDE.md` "문구" 의 용어표를 따른다.
3. 그 문구를 고정한 테스트를 `rg` 로 찾아 같이 고친다. 없음 단언도 대상이다.
4. 다른 step 대상 파일의 문구는 건드리지 않는다. 동작, SQL의 실행 부분, 단계의 수와 순서는 바꾸지 않는다.
5. README의 init_db 예시는 phase 마무리에서 고친다(README ~362-363 등).

## 읽어야 할 파일

- `/CLAUDE.md`(CRITICAL: Python 3.9, PG 10~15), `/docs/ADR.md`: ADR-014, ADR-020
- `src/genviewer/scripts/init_db.py`(전체): `build_plan`, `_first_line`, `print_plan`, 실행 루프, argparse, getpass
- `src/genviewer/scripts/__init__.py`: `survive_console_encoding`. 읽기만 한다.
- `src/genviewer/service/schema.py`: `_PG_PROCESS_MOVE_TO_RELEASE`, `_PG_DEVICE_DROP_NAME_UNIQUE`, 빠진 컬럼을 더하는 함수(~282)
- `tests/test_init_db.py`: 라벨 제약
  - 테이블마다 add 라벨에 테이블 이름이 들어가고 서로 다르다.
  - process 옮기기 라벨에 `"process"` 와 `"release"` 가 들어가고, `change_log` add 라벨에 `"change_log"` 가 들어간다.
- `tests/test_py39_compat.py`

## 작업

### 1. 옮길 문구 (권장 영어)

**`service/schema.py`** (SQL 문자열 안만)
- `-- process 에 release 를 더하고 UNIQUE 를 (name, release) 로 바꾼다` → `-- add release to process and change UNIQUE to (name, release)`
- `-- device 의 옛 UNIQUE (process_id, name) 을 뗀다` → `-- drop the old UNIQUE (process_id, name) from device`
- 그 문 안의 한국어 `--` 주석 두 줄도 같은 뜻의 영어로 바꾼다.
- `-- {tbl} 에 빠진 컬럼을 더한다` → `-- add missing columns to {tbl}`

**`scripts/init_db.py`**
- `f"skip  {st.label} (이미 있음)"` → `f"skip  {st.label} (already exists)"`
- argparse 설명 `"PostgreSQL 프로비저닝"` → `"PostgreSQL provisioning"`
- 옵션 help 다섯 개(`--create-role`, `--create-database`, `--owner`, `--app-role`, `--dry-run`)
- `ap.error("--dsn 또는 GENDB_PG_DSN 이 필요하다")` → `"--dsn or GENDB_PG_DSN is required"`
- getpass 프롬프트 `f"'{role}' role 의 비밀번호: "` → `f"Password for role '{role}': "`
- `ap.error("role 을 만들려면 비밀번호가 필요하다")` → `"a password is required to create the role"`

### 2. 지킬 것

- **Python 3.9**: `init_db.py`, `schema.py`, `config/config.py`, `scripts/__init__.py` 는 3.9에서 import되어야 한다. 문구만 바꾸므로 문법은 그대로다. `tests/test_py39_compat.py` 가 확인한다.
- **SQL 실행 부분은 한 글자도 바꾸지 않는다.** 주석 줄만 바꾼다. psycopg는 파라미터가 있을 때 `%` 를 자리표시자로 읽는다. 영어 주석에 `%` 를 넣지 마라(schema.py 주석이 이유를 적어 두었다).
- 라벨 제약(위)이 그대로 성립해야 한다.

### 3. 함께 고칠 테스트

- `tests/test_init_db.py`: 라벨 글자를 박은 곳이 있으면 고친다. 성질 테스트(유일성, 포함 낱말)는 그대로 통과해야 한다.
- `tests/test_cli.py` 나 다른 곳이 init_db 출력의 한국어(`이미 있음` 등)를 보면 같이 고친다(`rg` 로 찾는다).

## Acceptance Criteria

```bash
uv run ruff check src tests
uv run pytest tests/test_init_db.py tests/test_py39_compat.py tests/test_schema.py -q
uv run python -m genviewer.scripts.init_db --dry-run   # 라벨이 영어인지 눈으로 본다(접속하지 않는다)
uv run pytest -q -rs   # GENDB_TEST_PG_DSN 이 있어야 한다. init_db 를 실제 PG 에 돌리는 테스트까지
```

- `GENDB_TEST_PG_DSN` 이 비어 있으면 `blocked` 로 멈춘다. skip을 통과로 보지 않는다. 이유: `service/schema.py` 의 SQL 글자가 바뀐다(harness 규칙 12).
- `--dry-run` 이 DSN 없이 도는지 먼저 확인한다. 안 되면 그 커맨드는 빼고 summary에 적는다.

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - SQL 문에서 바뀐 것이 `--` 주석 줄뿐인가? `git diff src/genviewer/service/schema.py` 로 본다.
   - PG 10~15 문법을 벗어나지 않았는가? 실행 부분이 그대로이니 그래야 한다.
   - 단계 수와 순서가 그대로인가?
3. 결과에 따라 `phases/24-english-text/index.json` 의 step 5를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "init_db 출력·argparse·getpass 영어화, schema.py SQL 안 한국어 주석(라벨 3개 포함) 영어화. 라벨 제약 그대로. 고친 테스트: <파일들>. 변이: <결과>. DB 테스트: <passed/skipped>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요(DSN 없음 등) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- SQL 문의 실행 부분(키워드, 식별자, 조건, `$$` 블록)을 바꾸지 마라. 이유: 운영 DB에 도는 멱등 DDL이다.
- 3.9에서 못 도는 문법(`X | Y` 런타임 평가, `match`, `zip(strict=)` 등)을 쓰지 마라. 이유: CLAUDE.md CRITICAL.
- Python `#` 주석과 docstring을 번역하지 마라. 이유: ADR-020 범위 밖이다.
- `tools/*.sh` 를 바꾸지 마라. 이유: step 6의 일이다.
- 기존 테스트를 깨뜨리지 마라.
