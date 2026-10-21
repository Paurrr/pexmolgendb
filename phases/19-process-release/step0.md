# Step 0: schema-release

## 배경 (phase 19 공통)

이 저장소는 평소에 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 19는 예외로 **사용자가 2026-10-21 승인한 기능**이다. 승인된 동작은 다음과 같다.

> process 에 버전을 더해 (process, 버전)마다 device 데이터를 따로 관리한다. 버전은 `S00-V1.0.0.0` 같은 자유 문자열이다(앞뒤 공백만 다듬고 형식은 검사하지 않는다).
> - DB: process 행 하나가 (이름, 버전) 쌍이다. `process.release TEXT NOT NULL DEFAULT ''`, `UNIQUE (name, release)`. 지금 있는 process 는 빈 버전 `''` 이 된다. device·탭 테이블은 그대로 `process_id` 로 묶인다.
> - 마이그레이션은 `genviewer-init-db` 의 멱등 DDL 이다. 카탈로그를 보고 빠졌을 때만 ALTER 한다. `change_log.process_release` 도 더한다.
> - CSV 형식은 그대로다(버전 컬럼 없음, molgen 은 고치지 않는다). 불러올 때 버전을 정한다(CLI `load --version`, GUI Load CSV 가 묻는다). 내보내기 내용은 그대로이고 GUI 파일 이름 기본값만 molgen 규칙(`<proc>_<cid>-<ver 점 제거>.csv`)을 따른다.
> - 새 버전은 기존 (process, 버전)에서 DB 안에서 복제할 수 있다(device 와 탭 행, 한 시점 스냅샷).
> - 화면: Device 탭 툴바가 `Process [▾] Version [▾] [+][-]` 콤보 두 개다. 빈 버전은 `(없음)` 으로 보인다.
> - 이력: change_log 에 버전을 남기고 "process / device" 칸에 `sf2p S00-V1.0.0.0/nfet_a` 로 보인다. History 필터는 지금처럼 process 이름이다(모든 버전).
> - `+`(추가)는 저장 안 한 편집이 있으면 먼저 기존 "Save Changes" 를 묻고, 저장이 취소·실패하면 아무것도 만들지 않는다.

**이름 규칙.** 새 개념은 코드·DB 에서 **`release`** 다. 화면 라벨은 `Version`, CLI 옵션은 `--version` 이다. 새 개념에 `version` 이라는 이름(변수·키·컬럼·시그널)을 쓰지 마라. 이유: `device.version` 은 낙관적 잠금 카운터이고 `deviceVersionBumped`·`set_device_version`·`expected_version`·device dict 의 `"version"` 키 등 200곳 넘게 그 뜻으로 쓴다.

**빈 버전.** `''` 은 "버전 없음" 이고 옛 동작과 같다. repo 메서드의 `release` 인자는 keyword 이고 기본값 `""` 이다(옛 호출자·테스트가 그대로 돈다). 사람이 읽는 process 표시는 `audit.process_label(name, release)` 하나로 만든다(step 1이 만든다). 빈 버전이면 `name`, 아니면 `f"{name} {release}"` 다. **빈 버전일 때 기존 문구·출력은 바이트까지 그대로여야 한다.**

이 phase의 step (각 step 은 앞 step 이 끝난 코드 위에서 돈다):
- step 0 `schema-release`: DDL·마이그레이션·`status` 진단 (DB) ← 이 step
- step 1 `audit-release`: change_log 에 버전, `process_label`, `recent(release=)` (DB)
- step 2 `process-repo-release`: `ProcessRepository`·`find_or_create` 가 (이름, 버전)을 받는다, `list_pairs` (DB)
- step 3 `audit-sources`: device·탭 저장 이력이 버전을 싣는다 (DB)
- step 4 `release-clone`: `ProcessRepository.clone` (DB)
- step 5 `io-release`: CSV 불러오기가 버전을 받는다 (DB)
- step 6 `cli-release`: `processes`·`load`·`export`·`log` (DB)
- step 7 `toolbar-pairs-view`: 툴바 view 의 콤보 두 개 (GUI)
- step 8 `selection-pair`: 컨트롤러가 (이름, 버전) 키로 전환·삭제한다 (GUI)
- step 9 `add-clone`: 추가 창(버전, 복제 원본) (GUI)
- step 10 `load-csv-release`: GUI Load CSV 의 버전, 내보내기 파일 이름 (GUI)

모든 step에 같은 규칙이 적용된다.
1. 기능이라 TDD로 한다. 새 동작을 단언하는 테스트를 먼저 쓰고, 수정 전에 실패하는 것을 본다(RED). 그 테스트 이름과 단언을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트만으로는 안 된다.
3. 고친 뒤 구현을 손으로 망가뜨려 새 테스트가 실패하는지 보고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
4. 이 파일의 행 번호는 2026-10-21(phase 18 직후) 기준 대략값이다. 이름으로 찾아라. phase 14~17(구조 제안 P2~P5, `docs/notes/architecture-proposal.md`)이 이 phase보다 먼저 끝났을 수 있다. 대화상자 대역, private 이름, DB 호출 위치가 바뀌었으면 실제 코드를 따르고 summary에 적는다. 그 구조를 되돌리지 않는다.
5. `config/tab_config.json` 과 device·탭 테이블의 컬럼을 바꾸지 않는다. `device.version`(낙관적 잠금)의 이름·의미를 바꾸지 않는다.
6. 사용자에게 보이는 새 문구는 그 step 파일이 적은 것만 만든다. 빈 버전일 때 기존 문구는 그대로다. 대화상자 제목은 영어, 본문·CLI 출력·주석은 한국어(CLAUDE.md).
7. 문서(`README.md`, `docs/*.md`, `CLAUDE.md`)는 phase 마무리에서 고친다. step에서는 바꾸지 않는다.
8. molgen 저장소(`../molgen`)를 고치지 마라.

## DB step 규칙

- **`service/schema.py` 의 DDL을 바꾸는 step이다.** `GENDB_TEST_PG_DSN`(관리자 DSN)이 없으면 코드를 고치지 말고 `"status": "blocked"` 로 멈춘다. DB 테스트가 skip된 것은 통과가 아니다(`-rs` 로 확인한다).
- SQL은 PostgreSQL 10~15에서 돌아야 한다(`MERGE`, `NULLS NOT DISTINCT`, PG 16+ 문법 금지). 값은 바인드 파라미터로 넘긴다.
- `schema.py` 는 **Python 3.9에서 import되어야 한다**(CLAUDE.md CRITICAL, ADR-014, `tests/test_py39_compat.py`). 이 파일에는 `from __future__ import annotations` 가 없어서 모듈 수준 주석도 import 때 평가된다. 런타임 `X | Y`, `match`, `zip(strict=)`, `dataclass(slots=/kw_only=)` 를 쓰지 마라.
- DB 테스트는 `tests/conftest.py` 의 `pg_dsn`·`db` fixture를 쓴다. `db` fixture는 테스트마다 `postgres_all_ddl()` 전체를 한 트랜잭션에서 돌린 뒤 `TRUNCATE` 한다. 그래서 새 DDL 은 이미 옮긴 스키마 위에서 수백 번 돈다. 할 일이 없으면 ALTER 를 실행하지 않아야 한다.

## 이 step의 목적

스키마를 (이름, 버전) 쌍으로 바꾸고, 운영 중인 DB 를 `init_db` 재실행으로 옮길 수 있게 한다. `genviewer status` 는 아직 옮기지 않은 DB 를 알아본다.

| 대상 | 새로 만든 DB(`CREATE TABLE`) | 이미 있는 DB(옮기기) |
|---|---|---|
| `process` | `id`, `name TEXT NOT NULL`, `release TEXT NOT NULL DEFAULT ''`, 테이블 제약 `UNIQUE (name, release)` | `release` 가 없으면 더한다. 컬럼이 정확히 `{name, release}` 인 UNIQUE 제약이 없으면 `process_name_release_key` 로 더한다. 컬럼이 정확히 `{name}` 인 UNIQUE 제약은 **이름이 무엇이든** 뗀다. 순서: 컬럼 → 새 제약 → 옛 제약 |
| `change_log` | 마지막 컬럼으로 `process_release TEXT NOT NULL DEFAULT ''` | 없으면 더한다 |
| `diagnostics.probe` | | 위 두 컬럼이 없으면 `missing_columns` 에 `"process.release"`·`"change_log.process_release"` 를 넣는다(고정 테이블 먼저, 그다음 지금처럼 탭 테이블을 tab_config 순서로). 없는 테이블의 컬럼은 세지 않는다(지금 규칙) |
| `genviewer status` | | 코드 변경 없이 따라온다: `스키마: 컬럼 N개가 없다 (…)` + `genviewer-init-db 를 다시 실행할 것.` + exit 1 |
| `repo/process.py` `find_or_create` | | `ON CONFLICT (name)` → `ON CONFLICT (name, release)`. **이 한 줄만 바꾼다.** 이유: 제약이 바뀌면 `ON CONFLICT (name)` 은 맞는 제약이 없어 42P10 으로 죽는다(CSV 불러오기, 없는 process 고르기). INSERT 는 그대로 `(name)` 이고 `release` 는 DDL 기본값 `''` 이 된다. 나머지 process 쿼리는 step 2 의 일이다 |

새로 만든 DB 와 옮긴 DB 의 모양(컬럼 순서, 제약 컬럼)이 같아야 한다. 그래서 `change_log.process_release` 는 `CREATE TABLE` 에서도 **마지막** 컬럼이고(`ADD COLUMN` 은 끝에 붙는다), `process.release` 는 `name` 바로 다음이다(옛 process 는 `id, name` 뿐이라 끝에 붙어도 같은 자리다).

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ARCHITECTURE.md`(스키마 절, 권한 절), `/docs/ADR.md`(ADR-003 마이그레이션, ADR-006 옛 제약 떼기, ADR-014 Python 3.9)
- `src/genviewer/service/schema.py`: `_PG_PROCESS_DDL`(~52), `_PG_DEVICE_DROP_NAME_UNIQUE`(~82, **카탈로그에서 컬럼으로 제약을 찾는 본보기**, `%` 를 쓰지 않는 이유 주석), `_PG_CHANGE_LOG_DDL`(~127), `pg_child_add_columns_ddl`(~181, 빠진 컬럼만 더하는 DO 블록의 본보기, 첫 줄 `-- …` 주석이 `--dry-run` 라벨이 된다), `postgres_all_ddl`(~225)
- `src/genviewer/scripts/init_db.py`: `build_plan`, `_first_line`(라벨), `run_plan`(DB 단계 전부 한 트랜잭션)
- `src/genviewer/service/diagnostics.py`: `probe`(~161-227, `missing_columns` ~198-204)
- `src/genviewer/cli.py`: `status`(~161-214)
- `src/genviewer/service/repo/process.py`: `find_or_create`
- `tests/test_schema.py`: `_pg_tables`/`_COLUMN`(~13-31, `CREATE TABLE` 본문의 비지 않은 줄마다 `\s*"?(\w+)"?\s` 를 맞춘다), `test_ddl_drops_an_old_unique_constraint_whatever_its_name`(~86), `test_ddl_adds_every_payload_column_after_its_create_table`(~120), `test_ddl_restores_a_missing_column_on_an_existing_table`(~166, finally 로 되살리는 본보기 ~211-217), `test_ddl_twice_leaves_the_same_columns`, `test_ddl_takes_no_table_lock_when_no_column_is_missing`(~234)
- `tests/test_init_db.py`: `test_plan_without_flags_is_ddl_only`, `test_add_column_steps_sit_between_their_create_table_and_the_grants`(라벨이 테이블마다 달라야 한다), `test_identity_columns_need_no_sequence_grant`(`INSERT INTO process (name)` 을 직접 쓴다)
- `tests/test_cli.py`: phase 8 step 1이 만든 status 테스트(`test_status_names_a_missing_column_and_points_at_init_db` 등), `tests/test_py39_compat.py`, `tests/conftest.py`(`db` fixture)

## 작업

### 1. 테스트 먼저

접속 없이(`tests/test_schema.py`):
- 렌더링한 DDL 에서 `process` 의 컬럼이 `id, name, release` 이고 `name` 줄에 `UNIQUE` 가 없으며 `UNIQUE (name, release)` 가 있다. `change_log` 의 마지막 컬럼이 `process_release` 다.
- `test_child_tables_match_tab_config` 등 기존 정규식 테스트가 그대로 통과한다. **테이블 제약은 `UNIQUE (name, release)` 처럼 괄호 앞에 공백을 둔다.** 이유: `_COLUMN` 정규식은 뒤에 공백이 있어야 맞는다. `UNIQUE(name, …)` 이면 `.match()` 가 None 이라 `AttributeError` 로 죽는다.

DB(`tests/test_schema.py`):
- 새 DB: `process.release` 가 `text NOT NULL DEFAULT ''` 이다. `process` 의 UNIQUE 제약은 컬럼이 `{name, release}` 인 것 하나뿐이다. `change_log.process_release` 가 있다.
- **옛 모양에서 옮기기(RED)**: phase 18 의 모양을 손으로 만든다. `process` 는 `release` 가 없고 손으로 이름 붙인 `UNIQUE (name)`(예 `CONSTRAINT process_legacy_uq UNIQUE (name)`)이 있으며, `change_log` 에 `process_release` 가 없다. process `sf2p` 와 그 device 하나, change_log 한 줄을 넣는다. `postgres_all_ddl()` 을 돌린다. 그 뒤:
  - 행이 그대로이고 `release` 는 `''` 이다.
  - `('sf2p', 'V1')` 이 들어간다. `('sf2p', '')` 를 또 넣으면 `UniqueViolation` 이다.
  - 컬럼이 `{name}` 인 UNIQUE 제약이 없다. `change_log.process_release` 가 `''` 로 채워져 있다.
  - **세션 DB 를 망가뜨리지 마라.** 이 테스트는 `pg_dsn`(관리자) 로 임시 데이터베이스를 만들어 그 안에서 하거나, `finally` 에서 손으로 쓴 SQL 로 세션 스키마를 지금 DDL 이 만드는 모양으로 되돌린다. 이유: 수정 전에는 DDL 이 옛 모양을 고치지 못해, 이 테스트 뒤의 DB 테스트가 줄줄이 깨진다.
- **잠금 없음**: `test_ddl_takes_no_table_lock_when_no_column_is_missing` 을 넓힌다. 다른 커넥션이 `process`·`change_log` 를 읽는 트랜잭션(AccessShareLock)을 잡은 채로, `lock_timeout = 500ms` 인 커넥션에서 `postgres_all_ddl()` 전체가 통과한다(이미 옮긴 DB 에서는 ALTER 를 실행하지 않는다).
- **두 번 돌려도 같다**: DDL 을 두 번 돌린 뒤 `process`·`change_log` 의 컬럼과 제약이 한 번 돌린 것과 같다.
- **진단**: `process.release` 가 없는 DB(위 임시 DB 방식이나 finally 로 되살리기)에서 `diagnostics.probe(...).missing_columns == ["process.release"]` 이고 `schema_ready` 가 False 다. `tests/test_cli.py`: 그 DB 로 `genviewer status` 가 exit 1, `스키마: 컬럼 1개가 없다 (process.release)` 와 `genviewer-init-db 를 다시 실행할 것.` 을 낸다.

`tests/test_init_db.py`:
- `build_plan()` 의 단계 라벨에 process 옮기기와 change_log 컬럼 더하기 라벨이 각각 하나씩 있고, 서로·다른 라벨과 겹치지 않는다. `GRANT`·`SET ROLE` 이 들어가지 않는다(`test_plan_without_flags_is_ddl_only`).

수정 전에는 새 DB·옮기기·진단 테스트가 실패해야 한다.

### 2. 수정

- `service/schema.py`
  - `_PG_PROCESS_DDL`: 위 표의 모양.
  - process 옮기기 DO 블록 하나(첫 줄 `-- process 에 release 를 더하고 UNIQUE 를 (name, release) 로 바꾼다` 처럼 `-- …` 라벨). `_PG_DEVICE_DROP_NAME_UNIQUE` 처럼 `pg_constraint` + `pg_attribute` 로 제약 컬럼을 `array_agg(a.attname::text ORDER BY a.attname::text)` 로 모아 `ARRAY[...]::text[]` 와 비교한다(`attname` 은 `name` 타입이라 캐스트가 필요하다). 컬럼은 `pg_attribute`(`NOT attisdropped`)를 보고 없을 때만 더한다. 이름은 `quote_ident` 로 붙이고 **`%` 를 쓰지 마라**(psycopg 자리표시자).
  - `change_log.process_release`: `pg_child_add_columns_ddl` 과 같은 방식(카탈로그를 보고 없을 때만 `ADD COLUMN … TEXT NOT NULL DEFAULT ''`). 일반 함수로 묶어도 된다. 라벨은 탭 테이블 라벨과 겹치지 않게 한다.
  - 고정 테이블에 더한 컬럼의 **원본 하나**를 모듈 상수로 둔다(예 `FIXED_ADDED_COLUMNS = {"process": ("release",), "change_log": ("process_release",)}`). DDL 과 `diagnostics` 가 같은 상수를 본다. 이름·모양은 재량이다.
  - `postgres_all_ddl()` 순서: process `CREATE` → process 옮기기 → device … → change_log `CREATE` → change_log 컬럼 더하기 → change_log 인덱스 → 탭 테이블들(지금 그대로).
- `service/diagnostics.py` `probe`: 있는 고정 테이블의 컬럼도 위 상수와 비교해 `missing_columns` 에 `<테이블>.<컬럼>` 으로 넣는다. 고정 테이블 먼저, 그다음 지금처럼 탭 테이블. 예외를 내지 않는 지금 성질을 지킨다.
- `service/repo/process.py` `find_or_create`: `ON CONFLICT (name)` → `ON CONFLICT (name, release)`. 다른 줄은 바꾸지 않는다.

### 3. 변이 검사

- process 옮기기 블록의 카탈로그 조건을 빼(언제나 ALTER) 잠금 없음 테스트가 55P03 으로 실패하는지 본다. 되돌린다.
- 옛 `UNIQUE (name)` 떼기를 빼 옮기기 테스트가 실패하는지 본다(`('sf2p', 'V1')` 이 UniqueViolation). 되돌린다.
- `probe` 의 고정 테이블 검사를 빼 진단·status 테스트가 실패하는지 본다. 되돌린다.

### 4. 손으로 확인

임시 DB 하나에 phase 18 모양(위 옛 모양)을 만들고 `uv run genviewer-init-db --dsn <그 DB>` 를 두 번 돌린다(옵션 이름은 `--help` 로 확인). 첫 번째 뒤에 `\d process` 모양이 새 DB 와 같고, 두 번째는 바뀌는 것이 없다. `uv run python -X utf8 -m genviewer.scripts.init_db --dry-run` 출력에 새 라벨 두 줄이 보인다. 결과를 summary에 적는다.

## Acceptance Criteria

```bash
test -n "$GENDB_TEST_PG_DSN" || { echo "GENDB_TEST_PG_DSN 없음 → blocked"; exit 1; }
uv run pytest tests/test_schema.py tests/test_init_db.py tests/test_cli.py tests/test_py39_compat.py tests/test_boundaries.py -q -rs   # DSN 사유의 SKIPPED 없음
uv run ruff check src tests
uv run pytest -q -rs
```

## 검증 절차

1. 위 AC 커맨드를 실행한다. `GENDB_TEST_PG_DSN` 이 없으면 아무것도 고치지 말고 blocked로 끝낸다.
2. 아키텍처 체크리스트를 확인한다.
   - 이미 옮긴 DB 에서 ALTER 가 하나도 실행되지 않는가(잠금 테스트)?
   - 옛 제약을 이름이 아니라 컬럼으로 찾는가? DDL 에 `%` 가 없는가?
   - `schema.py` 가 Python 3.9 에서 import 되는가(`test_py39_compat`)?
   - PG 10~15 문법인가(`NULLS NOT DISTINCT` 없음)?
   - device·탭 테이블과 `tab_config.json` 을 바꾸지 않았는가?
3. 결과에 따라 `phases/19-process-release/index.json` 의 step 0을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "schema: process(name, release '' , UNIQUE (name, release)) + 옛 UNIQUE(name) 를 컬럼으로 찾아 떼는 DO 블록, change_log.process_release(마지막 컬럼), 원본 상수 <이름>. diagnostics 가 고정 테이블 컬럼도 봄. find_or_create ON CONFLICT (name, release). RED: <테스트 이름: 단언>. 변이: <결과>. 손 확인: <결과>. DB 테스트: <N passed>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - `GENDB_TEST_PG_DSN` 없음 → `"status": "blocked"`, `"blocked_reason": "GENDB_TEST_PG_DSN 없음"` 후 즉시 중단

## 금지사항

- 카탈로그를 보지 않고 `ALTER TABLE` 을 실행하지 마라(`ADD COLUMN IF NOT EXISTS` 만으로도 안 된다). 이유: `ALTER TABLE` 은 할 일이 없어도 ACCESS EXCLUSIVE 를 잡는다. `init_db` 는 사람들이 쓰는 중에도 다시 돌릴 수 있어야 하고, 테스트 fixture 가 매번 돌린다(phase 8).
- `release` 를 NULL 허용으로 만들지 마라. 이유: PG 10~15 의 UNIQUE 는 NULL 끼리 겹쳐도 막지 않는다(`NULLS NOT DISTINCT` 는 PG 15 부터이고 최소 지원은 PG 10).
- 옛 제약을 이름(`process_name_key`)으로 떼지 마라. 이유: 손으로 만든 DB 는 이름이 다를 수 있다(ADR-006).
- `process.py` 의 다른 쿼리(`get_id`·`add`·`delete`·`list_all` 등)를 고치지 마라. 이유: step 2 의 일이다. 이 step 이 끝난 뒤에도 모든 process 가 `''` 버전이라 이름만으로 찾아도 결과가 같다.
- 새 테이블을 만들지 마라. 이유: `expected_tables()` 는 17개 그대로다. 버전은 process 행의 일부다.
- `device.version` 을 건드리지 마라.
- 기존 테스트를 깨뜨리지 마라.
