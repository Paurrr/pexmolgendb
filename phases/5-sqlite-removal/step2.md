# Step 2: remove-sqlite-schema

## 배경 (phase 5 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 5는 예외다. **사용자가 2026-10-17 승인한 제거 작업**이다.
데이터는 공유 PostgreSQL에 있고 `.sqlite` 파일은 더 이상 쓰지 않는다. 그래서 옛 `.sqlite` 이관 도구(`genviewer-import-sqlite`)와 레거시 SQLite 스키마·픽스처를 지운다. 지우기만 한다. 기능을 더하거나 리팩터하지 않는다.

모든 step에 같은 규칙이 적용된다.
1. 버그 수정이 아니므로 RED 재현은 없다. 대신 남거나 바뀐 검사가 **여전히 실패할 수 있는지** 확인한다. 코드를 손으로 망가뜨려 실패를 보고(변이 검사) 손으로 되돌린다. `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 다른 변경까지 사라진다.
2. 파일 삭제는 `git rm` 으로 한다(`rm -rf` 는 훅이 막는다).
3. PostgreSQL DDL·SQL은 바꾸지 않는다. 그래서 하네스 규칙 12(DB 테스트 필수)는 해당하지 않는다.
   - `GENDB_TEST_PG_DSN` 이 설정돼 있으면 `uv run pytest -q -rs` 로 DB 테스트까지 돌린다. summary에 `DB 테스트: <N passed | 안 돎(DSN 없음)>` 을 적는다.
   - DSN이 없어도 `blocked` 가 아니다.
4. 역사를 설명하는 문장은 남긴다. sqlite를 쓰라는 안내가 아니라 지금 구조가 왜 이런지 설명하는 문장이기 때문이다.
   - `README.md` 첫 문단("예전처럼 각자 `.sqlite` 파일을 들고 …")
   - `docs/PRD.md` 첫 문단
   - `docs/ADR.md` ADR-001 결정
   - `src/genviewer/utils/background.py` 모듈 docstring
   - `tests/test_export.py` 의 "SQLite 는 rowid 순서를 …" 주석
5. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.
6. step 순서는 다음과 같다.
   - 0: tab_config 검사를 PostgreSQL DDL 기준으로 옮긴다.
   - 1: 이관 도구와 그 문서를 지운다.
   - 2: 레거시 스키마·픽스처를 지우고 기준선 숫자를 고친다.

## 이 step의 목적

레거시 SQLite 스키마 렌더러(`service/schema.py`)를 지운다. 그것을 검증하던 테스트와 픽스처(`db/init.sqlite`)도 지운다. 그리고 테스트 기준선 숫자를 고친다.
**PostgreSQL DDL은 한 글자도 바뀌지 않는다.**

## 읽어야 할 파일

- `/CLAUDE.md` — Python 3.9 import 규칙, "테스트 관례"의 기준선 문장
- `/README.md` '검사' 절(~518-523 "DB 없이 돌리면 지금 기준 Git Bash 에서 … passed / … skipped 다")
- `src/genviewer/service/schema.py` 에서 읽을 부분:
  - 모듈 docstring(~1-11)
  - `_SQLITE_PROCESS_DDL`·`_SQLITE_DEVICE_DDL`·`_SQLITE_DEVICE_INDEXES`·`sqlite_child_ddl`·`sqlite_all_ddl`(~29-76)
  - PostgreSQL 절 머리 주석 "SQLite 스키마 대비 의도적으로 조인 부분"(~83-96)
- `tests/test_schema.py` — step 0이 `test_child_tables_match_tab_config` 를 PostgreSQL 기준으로 바꿨다.
- `.gitignore` (~18-20)
- 이전 step에서 수정된 파일: `tests/test_schema.py`, `pyproject.toml`, `src/genviewer/scripts/__init__.py`, `README.md`, `CLAUDE.md`, `docs/ADR.md`, `docs/ARCHITECTURE.md`, `docs/PRD.md`, `docs/notes/known-issues.md`

## 작업

### 0. 고치기 전에 PostgreSQL DDL을 저장한다

```bash
uv run python -X utf8 -c "from genviewer.service import schema; print('\n;\n'.join(s.as_string() for s in schema.postgres_all_ddl()))" > "${TMPDIR:-/tmp}/gendb-ddl-before.sql"
```

- 출력 파일은 **저장소 밖**에 둔다. 이유: execute.py가 `git add -A` 로 커밋한다.
- `genviewer-init-db --dry-run` 으로 비교하지 마라. 이유: 문장마다 첫 줄만 찍어서 컬럼이 바뀌어도 모른다.

### 1. `src/genviewer/service/schema.py`

- `_SQLITE_PROCESS_DDL`, `_SQLITE_DEVICE_DDL`, `_SQLITE_DEVICE_INDEXES`, `sqlite_child_ddl`, `sqlite_all_ddl` 을 지운다.
- 모듈 docstring의 마지막 문단을 사실에 맞게 고친다.
  - 지금 문단: "구조는 아래 상수로 선언하고 렌더러를 따로 둔다. 지금 쓰는 것은 PostgreSQL 렌더러(postgres_all_ddl)이고, SQLite 쪽은 예전 .sqlite 파일을 읽어 들일 때만 쓰는 레거시 경로다."
  - SQLite 렌더러가 없어졌다는 것만 반영한다. 예: "구조는 아래 상수로 선언하고 PostgreSQL 렌더러(postgres_all_ddl)가 DDL 을 만든다."
  - 앞 문단은 그대로 둔다.
- PostgreSQL 절 머리 주석 `# SQLite 스키마 대비 의도적으로 조인 부분:` 은 `# 예전 SQLite 스키마 대비 의도적으로 조인 부분:` 으로만 바꾼다. 아래 1~4 항목은 그대로 둔다. 이유: PostgreSQL 컬럼이 `NOT NULL DEFAULT ''` 이고 device 이름에 UNIQUE가 없는 이유를 설명하는 유일한 곳이다.
- 이 파일은 RHEL 7 서버의 Python 3.9에서 import된다(CLAUDE.md). 지우기만 하므로 안전하지만 AC의 `ast.parse` 로 확인한다.

### 2. `tests/test_schema.py`

- 지운다: `import sqlite3`, `LEGACY_DB`, `_schema_of`, `_indexes_of`, `generated` fixture, `test_generated_schema_matches_legacy_database`. 더 쓰이지 않는 import(`Path` 등)도 지운다(ruff F401).
- 모듈 docstring: "(a) tab_config.json 과 (b) 기존 DB 와 일치하는지" 에서 (b)와 그 설명 줄을 지운다. (a) 설명은 남긴다.
- 그대로 둔다: `test_child_tables_match_tab_config`(step 0), `test_device_ddl_has_no_unique_constraint`, `test_ddl_drops_an_old_unique_constraint_whatever_its_name`.

### 3. 파일

- `git rm db/init.sqlite` (`db/` 가 비면 디렉터리도 없어진다)
- `.gitignore` 에서 세 줄과 그 블록의 빈 줄 하나를 지운다: `# SQLite DB — 샘플/픽스처만 추적`, `*.sqlite`, `!db/init.sqlite`

### 4. 확인

- 0번과 같은 명령으로 `"${TMPDIR:-/tmp}/gendb-ddl-after.sql"` 을 만들고 `diff` 한다. 차이가 없어야 한다.
- 변이 검사: `pg_child_ddl` 에서 컬럼 하나를 손으로 빼면 `test_child_tables_match_tab_config` 가 실패하는지 다시 보고 되돌린다. sqlite 테스트가 사라진 뒤에도 tab_config 검사가 살아 있다는 확인이다.
- `git grep -n -i sqlite -- . ':!phases'` 를 돌린다. 나와도 되는 것은 아래뿐이다.
  - 공통 4번의 문장들
  - `schema.py` 의 "예전 SQLite 스키마 대비" 주석 한 줄
  - `README.md` '유지보수 (하네스)' 표의 `5-sqlite-removal` 행. 이 phase 자신을 적은 줄이다.
  - 그 밖의 것이 나왔을 때:
    - 지운 파일·함수·명령을 가리키면 고친다.
    - 역사 설명이면 남기고 summary에 적는다.

### 5. 기준선 숫자

- Git Bash에서 **DSN 없이** `env -u GENDB_TEST_PG_DSN uv run pytest -q` 를 돌린다. 그 숫자로 두 곳을 고친다.
  - `CLAUDE.md` "테스트 관례"의 기준선 문장: 숫자와 날짜(실행한 날), "phase 4 완료 후" → "phase 5 완료 후"
  - `README.md` '검사' 절의 숫자
- PowerShell 숫자는 `sh` 가 필요한 셸 스크립트 테스트를 옮겨 적는다(passed −N, skipped +N). N은 Git Bash에서 `uv run pytest -q tests/test_deploy_sh.py tests/test_initdb_sh.py` 의 passed 수다(phase 4 뒤 2026-10-17 기준 20).
- 예상값(phase 4 완료 기준선과의 차이):
  - phase 4 완료 기준선(2026-10-17)은 DB 없이 Git Bash 427 passed / 124 skipped / 1 xfailed, PowerShell 407 / 144 / 1이다. DB를 붙이면 542 / 9 / 1이다.
  - step 1이 6개(DB 없이 1 passed + 5 skipped)를, 이 step이 1개(passed)를 지운다. 그러니 DB 없이 passed −2, skipped −5다. 예상: Git Bash 425 / 119 / 1, PowerShell 405 / 139 / 1.
  - 예상과 다르면 실제 값을 적고 이유를 summary에 적는다.
- `GENDB_TEST_PG_DSN` 이 있으면 DSN을 붙인 숫자도 **따로** 재서 `CLAUDE.md` 의 "DB를 붙이면 …" 숫자를 고친다(예상 535 passed / 9 skipped / 1 xfailed: 지운 7개가 모두 DB를 붙이면 돈다). DSN이 없으면 그 숫자는 그대로 두고 summary에 "DB 기준선 안 잼"이라고 적는다.

## Acceptance Criteria

```bash
uv run ruff check src tests                  # 린트 통과
uv run pytest -q                             # 전체 통과 (DSN 이 있으면 -rs 로 DB 테스트가 돌았는지 본다)
uv run python -X utf8 -c "from genviewer.service import schema; print('\n;\n'.join(s.as_string() for s in schema.postgres_all_ddl()))" > "${TMPDIR:-/tmp}/gendb-ddl-after.sql"
diff "${TMPDIR:-/tmp}/gendb-ddl-before.sql" "${TMPDIR:-/tmp}/gendb-ddl-after.sql"   # 차이 없음
uv run python -c "import ast; ast.parse(open('src/genviewer/service/schema.py', encoding='utf-8').read(), feature_version=(3, 9))"
uv run genviewer-init-db --dry-run           # 그대로 돈다
git grep -n -i sqlite -- . ':!phases'        # 공통 4번 목록 + schema.py 주석 한 줄 + README 하네스 표의 phase 5 행뿐
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `service/schema.py` 가 PySide6를 import하지 않고 Python 3.9에서 파싱되는가?
   - PostgreSQL DDL이 그대로인가(diff 비어 있음)?
   - `TABLE_COLUMNS`·`child_tables()` 가 그대로인가?
3. 결과에 따라 `phases/5-sqlite-removal/index.json` 의 step 2를 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "schema.py SQLite 렌더러·test_schema 레거시 테스트·db/init.sqlite·.gitignore 줄 삭제, PostgreSQL DDL diff 없음. 변이: <단언>. 기준선 <P> passed / <S> skipped (PowerShell <P-20> / <S+20>), DB 붙임 <D passed | 안 잼>. git grep sqlite 남은 것: <목록>. DB 테스트: <N passed | 안 돎(DSN 없음)>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- PostgreSQL DDL(`_PG_*` 상수, `pg_child_ddl`, `pg_child_index_ddl`, `postgres_all_ddl`)을 바꾸지 마라. 이유: 운영 DB 스키마다. 바꾸면 하네스 규칙 12에 따라 DB 테스트가 필수가 된다. diff가 이것을 지킨다.
- `from psycopg import sql  # noqa: E402` 의 위치나 그 밖의 코드를 정리하지 마라. 이유: 지우기만 하는 step이다(리팩터 금지).
- 설계 이유 주석의 1~4 항목을 지우거나 바꾸지 마라. 이유: 그 컬럼 설계의 유일한 설명이다.
- DDL 저장 파일을 저장소 안에 두지 마라. 이유: execute.py가 `git add -A` 로 커밋한다.
- "DB 없음" 기준선을 DSN을 켠 채로 재지 마라. 이유: CLAUDE.md·README의 그 숫자는 DB 테스트가 skip된 숫자다. DB를 붙인 숫자는 `CLAUDE.md` 의 "DB를 붙이면" 문장에만 따로 적는다.
- 공통 4번의 역사 설명 문장을 지우지 마라.
- 기존 테스트를 깨뜨리지 마라.
