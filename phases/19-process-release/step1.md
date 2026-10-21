# Step 1: audit-release

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

**빈 버전.** `''` 은 "버전 없음" 이고 옛 동작과 같다. repo 메서드의 `release` 인자는 keyword 이고 기본값 `""` 이다(옛 호출자·테스트가 그대로 돈다). 사람이 읽는 process 표시는 `audit.process_label(name, release)` 하나로 만든다(이 step이 만든다). 빈 버전이면 `name`, 아니면 `f"{name} {release}"` 다. **빈 버전일 때 기존 문구·출력은 바이트까지 그대로여야 한다.**

이 phase의 step (각 step 은 앞 step 이 끝난 코드 위에서 돈다):
- step 0 `schema-release`: DDL·마이그레이션·`status` 진단 (DB)
- step 1 `audit-release`: change_log 에 버전, `process_label`, `recent(release=)` (DB) ← 이 step
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

- **`service/repo/audit.py` 의 SQL을 바꾸는 step이다.** `GENDB_TEST_PG_DSN`(관리자 DSN)이 없으면 코드를 고치지 말고 `"status": "blocked"` 로 멈춘다. DB 테스트가 skip된 것은 통과가 아니다(`-rs` 로 확인한다).
- SQL은 PostgreSQL 10~15에서 돌아야 한다. 값은 바인드 파라미터로 넘긴다.
- DB 테스트는 `tests/conftest.py` 의 `pg_dsn`·`db` fixture를 쓴다.
- `service/repo/` 의 의미를 바꾸므로 **가짜(`tests/gui_support/fakes.py`)와 contract test(`tests/gui/test_fake_repo_contract.py`)를 같이 고친다**. `tests/gui/test_fake_store.py` 는 가짜 메서드의 시그니처(기본값 포함)가 진짜와 같아야 한다고 단언한다. 가짜가 기록하는 호출 dict 에는 기본값 인자도 들어가므로, 인자를 더하면 그 dict 를 정확히 단언하는 테스트도 고친다.

## 선행 step

- step 0 이 `change_log.process_release TEXT NOT NULL DEFAULT ''`(마지막 컬럼)를 만들었다. `phases/19-process-release/index.json` 의 step 0 summary 를 읽어라.

## 이 step의 목적

이력 모듈(`service/repo/audit.py`)이 버전을 싣고 보이고 거를 수 있게 한다. **이 step 은 audit 모듈과 그 가짜만 바꾼다.** 이력을 쓰는 쪽(device·탭 저장, process 추가·삭제, CSV 불러오기)이 실제 버전을 넘기는 것은 step 2·3·5 의 일이다. 그래서 이 step 이 끝나도 앱이 남기는 이력의 `process_release` 는 모두 `''` 이다.

| 대상 | 바뀐 뒤 |
|---|---|
| `Entry` | 필드 `process_release: str = ""` 를 **맨 뒤에** 더한다(위치 인자로 만드는 곳이 깨지지 않게) |
| `write(cur, actor, entries)` | `process_release` 도 넣는다. 행마다 파라미터 10개. `BATCH_ROWS` 위 주석의 숫자("이력은 9개" 등)를 맞게 고친다 |
| `_COLUMNS` | `process_release` 를 넣는다(`recent` 가 돌려주는 dict 의 키가 된다) |
| `process_label(name, release) -> str` (새 함수) | `release` 가 비면 `name`, 아니면 `f"{name} {release}"`. 화면·CLI·이력 문장이 모두 이것을 쓴다 |
| `where_of(row)` | process 자리를 `process_label(row["process_name"], row.get("process_release", ""))` 로 만든다. process 가 없으면 지금처럼 `-`. 빈 버전이면 **지금과 바이트까지 같다** |
| 문장 만드는 함수 `device_insert`·`device_update`·`device_delete`·`tab_change`·`process_add`·`process_delete` | keyword `process_release: str = ""` 를 받아 `Entry.process_release` 에 넣는다. `process_add`/`process_delete` 의 summary 는 이름 자리에 `process_label` 을 쓴다(빈 버전이면 지금 문장 그대로). device·탭 summary 는 바꾸지 않는다(process 는 where 칸에 보인다) |
| `csv_import` | 이 step 에서는 바꾸지 않는다(step 5) |
| `AuditRepository.recent(...)` | keyword `release: str \| None = None` 을 더한다. `None` 이면 거르지 않고, 문자열이면(빈 문자열 포함) `process_release = %s` 로 거른다. 다른 필터(`process` 등)는 지금처럼 빈 문자열이 "거르지 않음" 이다 |
| `format_line`·`format_detail` | `where_of` 를 쓰므로 따라온다 |
| History 화면(`controllers/history_tab.py`)·CLI `log` | 바꾸지 않는다. `recent` 를 `release` 없이 부르므로 지금처럼 모든 버전이 나온다 |

`release` 를 `None` 기본값으로 두는 이유: step 6 의 `genviewer log --version ""` 로 "버전 없는 것만" 을 고를 수 있어야 한다. 빈 문자열이 이미 "거르지 않음" 이면 그것을 표현할 수 없다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`(ADR-005 change_log), `/docs/ARCHITECTURE.md`
- `src/genviewer/service/repo/audit.py` 전체: `Entry`(~58), `BATCH_ROWS`·`write`(~71-109), 문장 함수들(~173-294), `where_of`(~302), `format_line`, `_COLUMNS`(~338), `AuditRepository.recent`(~359)
- `src/genviewer/service/schema.py`: step 0 이 만든 `change_log` DDL
- `tests/gui_support/fakes.py`: `FakeStore.add_audit`(~268, "실제 `audit.write` 가 남기는 행과 같은 모양"), `FakeAuditRepository.recent`(~822)
- `tests/gui/test_fake_repo_contract.py`: `AUDIT_KEYS`(`audit._COLUMNS` 에서 만든다), 이력 행 dict 를 정확히 단언하는 테스트(~900 근처, `test_recent_rows_have_the_change_log_columns`), `test_recent_filters_by_actor_process_and_device`
- `tests/gui/test_fake_store.py`: `recent` 호출 기록을 정확히 단언하는 곳(~627-638)
- `tests/gui/test_history_smoke.py`: `recent` 호출 기록 단언(~44-53)
- `tests/test_change_log.py`: `audit.write` 를 쓰는 DB 테스트, "9개" 를 적은 주석·단언(~410)

## 작업

### 1. 테스트 먼저

접속 없이:
- `process_label("sf2p", "") == "sf2p"`, `process_label("sf2p", "S00-V1.0.0.0") == "sf2p S00-V1.0.0.0"`.
- `where_of({"process_name": "sf2p", "process_release": "V1", "device_name": "nfet_a"}) == "sf2p V1/nfet_a"`. 빈 버전·process 없음·device 없음은 지금 결과 그대로다(`process_release` 키가 없는 옛 dict 도 그대로).
- `process_add("sf2p", process_release="V1")` 의 `process_release == "V1"`, summary 가 `"process 추가  sf2p V1"`. 빈 버전이면 지금 summary 와 같다. `process_delete` 도 같은 방식. `device_insert`·`device_update`·`device_delete`·`tab_change` 가 `process_release` 를 Entry 에 싣는다.

contract test(가짜와 PostgreSQL 둘 다, `tests/gui/test_fake_repo_contract.py`):
- `process_release` 가 `"V1"`·`""` 인 줄을 하나씩 넣는다(진짜는 `audit.write`, 가짜는 `store.add_audit`, 지금 테스트가 넣는 방식을 따른다). `recent(release="V1")` 는 V1 줄만, `recent(release="")` 는 빈 버전 줄만, `recent()` 는 둘 다.
- 돌려받은 행에 `process_release` 키가 있고 넣은 값이다. 정확한 행 dict 단언에 `"process_release": ""` 를 더한다.

DB(`tests/test_change_log.py`):
- `audit.write` 로 `process_release="V1"` 인 Entry 를 쓰고 `change_log` 를 직접 읽으면 그 값이다. `BATCH_ROWS` 를 넘는 줄 수에서도 값이 줄마다 맞다(파라미터 개수 변경 확인).

수정 전에는 위 테스트가 실패해야 한다(없는 함수·인자·키).

### 2. 수정

- `service/repo/audit.py`: 위 표대로.
- `tests/gui_support/fakes.py`:
  - `FakeStore.add_audit` 가 `"process_release": entry.process_release` 를 행에 넣는다.
  - `FakeAuditRepository.recent` 에 같은 시그니처(`release: str | None = None`)와 같은 의미의 필터를 더한다.
- 호출 기록을 정확히 단언하던 테스트(`test_fake_store.py`, `test_history_smoke.py`)는 `release=None` 이 기록에 들어가는 것에 맞춰 기대값을 고친다. 고친 테스트 이름을 summary에 적는다.

### 3. 변이 검사

- 진짜 `recent` 의 `release` 조건을 빼 contract(PostgreSQL 쪽)가 실패하는지 본다. 되돌린다.
- `write` 가 `process_release` 를 넣지 않게 해(컬럼 기본값 `''`) DB 테스트가 실패하는지 본다. 되돌린다.
- 가짜 `recent` 의 필터를 빼 contract(가짜 쪽)가 실패하는지 본다. 되돌린다.

## Acceptance Criteria

```bash
test -n "$GENDB_TEST_PG_DSN" || { echo "GENDB_TEST_PG_DSN 없음 → blocked"; exit 1; }
uv run pytest tests/gui/test_fake_repo_contract.py tests/gui/test_fake_store.py tests/gui/test_history_smoke.py tests/test_change_log.py tests/test_cli.py -q -rs   # DSN 사유의 SKIPPED 없음
uv run ruff check src tests
uv run pytest -q -rs
```

## 검증 절차

1. 위 AC 커맨드를 실행한다. `GENDB_TEST_PG_DSN` 이 없으면 아무것도 고치지 말고 blocked로 끝낸다.
2. 아키텍처 체크리스트를 확인한다.
   - 빈 버전의 `where_of`·summary 가 바이트까지 그대로인가?
   - 이력 쓰기가 저장과 같은 트랜잭션(호출자의 cursor)이라는 성질을 지켰는가(CLAUDE.md CRITICAL)?
   - 가짜와 진짜가 같은 contract test를 통과하는가?
   - `recent(release=None)` 이 거르지 않고 `""` 은 빈 버전만 고르는가?
3. 결과에 따라 `phases/19-process-release/index.json` 의 step 1을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "audit: Entry.process_release(맨 뒤), write 10 params, _COLUMNS, process_label(name, release), where_of 가 'name release/device', 문장 함수 keyword process_release, recent(release=None|str). 가짜 add_audit·recent 같은 의미. RED: <테스트 이름: 단언>. 변이: <결과>. 고친 기존 테스트: <이름>. DB 테스트: <N passed>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - `GENDB_TEST_PG_DSN` 없음 → `"status": "blocked"`, `"blocked_reason": "GENDB_TEST_PG_DSN 없음"` 후 즉시 중단

## 금지사항

- `repo/device.py`·`repo/parameter.py`·`repo/process.py`·`repo/io.py` 를 고치지 마라. 이유: 이력에 실제 버전을 싣는 것은 step 2·3·5 의 일이다. 이 step 은 받을 자리만 만든다.
- History 화면·CLI `log` 를 고치지 마라. 이유: History 필터는 승인대로 process 이름 그대로이고, CLI 는 step 6 의 일이다.
- `Entry` 의 기존 필드 순서를 바꾸지 마라. 새 필드는 맨 뒤다.
- `change_log` 에 process id 컬럼이나 외래키를 더하지 마라. 이유: 이력은 원본이 지워져도 읽혀야 해서 이름 문자열로 남긴다(ADR-005).
- 기존 테스트를 깨뜨리지 마라. 호출 기록·행 dict 를 정확히 단언하던 테스트만 승인된 동작에 맞게 기대값을 고친다.
