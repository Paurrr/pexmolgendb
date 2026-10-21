# Step 3: audit-sources

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

**빈 버전.** `''` 은 "버전 없음" 이고 옛 동작과 같다. repo 메서드의 `release` 인자는 keyword 이고 기본값 `""` 이다(옛 호출자·테스트가 그대로 돈다). 사람이 읽는 process 표시는 `audit.process_label(name, release)` 하나로 만든다(step 1이 만들었다). 빈 버전이면 `name`, 아니면 `f"{name} {release}"` 다. **빈 버전일 때 기존 문구·출력은 바이트까지 그대로여야 한다.**

이 phase의 step (각 step 은 앞 step 이 끝난 코드 위에서 돈다):
- step 0 `schema-release`: DDL·마이그레이션·`status` 진단 (DB)
- step 1 `audit-release`: change_log 에 버전, `process_label`, `recent(release=)` (DB)
- step 2 `process-repo-release`: `ProcessRepository`·`find_or_create` 가 (이름, 버전)을 받는다, `list_pairs` (DB)
- step 3 `audit-sources`: device·탭 저장 이력이 버전을 싣는다 (DB) ← 이 step
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

- **`service/repo/device.py`·`parameter.py` 의 SQL을 바꾸는 step이다.** `GENDB_TEST_PG_DSN`(관리자 DSN)이 없으면 코드를 고치지 말고 `"status": "blocked"` 로 멈춘다. DB 테스트가 skip된 것은 통과가 아니다(`-rs` 로 확인한다).
- SQL은 PostgreSQL 10~15에서 돌아야 한다. 값은 바인드 파라미터로 넘긴다.
- DB 테스트는 `tests/conftest.py` 의 `pg_dsn`·`db` fixture를 쓴다.
- 가짜 device·탭 repo(`tests/gui_support/fakes.py`)는 이력을 쓰지 않는다(이력 가짜는 `store.add_audit` 로만 채운다). 그래서 이 step 은 가짜를 바꾸지 않는다. 가짜가 이력을 쓰는 곳을 찾으면 진짜와 같은 의미로 맞추고 summary에 적는다.

## 선행 step

- step 1: 문장 함수(`device_insert`·`device_update`·`device_delete`·`tab_change`)가 keyword `process_release` 를 받는다.
- step 2: `ProcessRepository.get_or_create_id(name, release=...)` 로 버전 있는 process 를 만들 수 있다.
- `phases/19-process-release/index.json` 의 step 0~2 summary 를 읽어라.

## 이 step의 목적

device 저장(`repo/device.py`)과 탭 저장(`repo/parameter.py`)이 남기는 이력 줄에 그 process 의 버전을 싣는다. 그래야 History 와 `genviewer log` 에서 `sf2p S00-V1.0.0.0/nfet_a` 와 `sf2p/nfet_a` 를 구별할 수 있다.

| 곳 | 지금 | 바뀐 뒤 |
|---|---|---|
| `repo/device.py` `_process_name(cur, process_id)` (~40) | `SELECT name FROM process WHERE id = %s` → 이름 | 이름과 버전을 함께 읽는다(예 `_process_ident(cur, process_id) -> tuple[str, str]`, 이름은 재량). 부르는 곳(`upsert_device` ~145·152, `_log` ~260) 모두 |
| device 이력(`device_insert`·`device_update`·`device_delete`) | `process_release` 없음 → `''` | 그 process 의 `release` |
| `repo/parameter.py` `replace_many_for_device` (~72-78, ~119) | `SELECT d.name, d.version, …, p.name AS process_name … FOR UPDATE OF d` | `p.release AS process_release` 도 읽어 `tab_change(..., process_release=...)` 에 넘긴다. `FOR UPDATE OF d` 는 그대로(process 행을 잠그지 않는다) |
| 이력이 아닌 것(저장 결과, 충돌, version, etag) | | 바뀌지 않는다 |

## 읽어야 할 파일

- `/CLAUDE.md`(CRITICAL: 쓰기와 이력은 같은 트랜잭션), `/docs/ADR.md`(ADR-004, ADR-005), `/docs/ARCHITECTURE.md`(device 저장 흐름)
- `src/genviewer/service/repo/device.py`: `_process_name`, `upsert_device`, `upsert_devices`, `_log`, `_insert_new`
- `src/genviewer/service/repo/parameter.py`: `replace_many_for_device`
- `src/genviewer/service/repo/audit.py`: 문장 함수들, `process_label`, `where_of`
- `tests/test_change_log.py`: device·탭 이력 테스트(`process_id` fixture, `test_filters_narrow_the_result` 등)

## 작업

### 1. 테스트 먼저

DB(`tests/test_change_log.py`):
- `ProcessRepository(db).get_or_create_id("sf2p", release="V1")` 로 만든 process 에서
  - `upsert_devices` 로 device 를 더하고, 고치고, 지운다 → 그 세 이력 줄의 `process_release == "V1"`(RED: 지금 `''`).
  - `upsert_device` 한 줄 저장(붙여넣기 경로) → `"V1"`.
  - `replace_many_for_device` 로 탭을 바꾼다 → 탭 이력 줄의 `process_release == "V1"`.
  - `audit.where_of(row)` 가 `"sf2p V1/<device 이름>"` 이다.
- 빈 버전 process 의 같은 저장은 `process_release == ""` 이고, 이력 줄의 나머지 값(summary, detail, process_name)이 지금과 같다(기존 테스트가 그대로 통과).

수정 전에는 V1 단언이 실패해야 한다.

### 2. 수정

- `repo/device.py`, `repo/parameter.py`: 위 표대로. 이름·버전을 읽는 쿼리를 하나 더 늘리지 말고 지금 읽는 자리에서 함께 읽는다.

### 3. 변이 검사

- `parameter.py` 에서 `process_release` 를 넘기지 않게 해 탭 이력 테스트가 실패하는지 본다. 되돌린다.
- device 쪽 하나(예 `_log` 의 삭제 줄)에서 빼 그 테스트가 실패하는지 본다. 되돌린다.

## Acceptance Criteria

```bash
test -n "$GENDB_TEST_PG_DSN" || { echo "GENDB_TEST_PG_DSN 없음 → blocked"; exit 1; }
uv run pytest tests/test_change_log.py tests/test_concurrency.py tests/test_device_save_guards.py tests/gui/test_fake_repo_contract.py -q -rs   # DSN 사유의 SKIPPED 없음 (없는 파일은 빼고 summary 에 적는다)
uv run ruff check src tests
uv run pytest -q -rs
```

## 검증 절차

1. 위 AC 커맨드를 실행한다. `GENDB_TEST_PG_DSN` 이 없으면 아무것도 고치지 말고 blocked로 끝낸다.
2. 아키텍처 체크리스트를 확인한다.
   - 이력이 저장과 같은 트랜잭션·같은 cursor 로 쓰이는가?
   - `FOR UPDATE OF d` 가 그대로여서 process 행을 잠그지 않는가?
   - 낙관적 잠금(version 비교, `StaleWriteError`)·저장 결과가 그대로인가?
   - 빈 버전 이력이 지금과 같은가?
3. 결과에 따라 `phases/19-process-release/index.json` 의 step 3을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "device.py <함수 이름>(cur, pid) → (name, release), device 이력·parameter.py 탭 이력에 process_release. RED: <테스트 이름: 단언>. 변이: <결과>. DB 테스트: <N passed>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - `GENDB_TEST_PG_DSN` 없음 → `"status": "blocked"`, `"blocked_reason": "GENDB_TEST_PG_DSN 없음"` 후 즉시 중단

## 금지사항

- 저장 쿼리(잠금 순서, version 가드, DELETE 의 `process_id` 가드, advisory lock)를 바꾸지 마라. 이유: 이 step 은 이력 줄의 값만 바꾼다. 동시 편집 계약(ADR-004)은 그대로다.
- `FOR UPDATE OF d` 를 `FOR UPDATE` 로 바꾸지 마라. 이유: process 행까지 잠그면 CSV 불러오기·process 고르기와 부딪힌다(K5).
- summary 문장(`device 추가  …`, `탭 …`)을 바꾸지 마라. 이유: process·버전은 where 칸에 보인다.
- `repo/process.py`·`repo/io.py`·`audit.py`·GUI·CLI 를 고치지 마라.
- 기존 테스트를 깨뜨리지 마라.
