# Step 5: io-release

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
- step 3 `audit-sources`: device·탭 저장 이력이 버전을 싣는다 (DB)
- step 4 `release-clone`: `ProcessRepository.clone` (DB)
- step 5 `io-release`: CSV 불러오기가 버전을 받는다 (DB) ← 이 step
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

- **`service/repo/io.py` 의 SQL을 바꾸는 step이다.** `GENDB_TEST_PG_DSN`(관리자 DSN)이 없으면 코드를 고치지 말고 `"status": "blocked"` 로 멈춘다. DB 테스트가 skip된 것은 통과가 아니다(`-rs` 로 확인한다).
- SQL은 PostgreSQL 10~15에서 돌아야 한다. 값은 바인드 파라미터로 넘긴다.
- DB 테스트는 `tests/conftest.py` 의 `pg_dsn`·`db` fixture를 쓴다.
- `service/repo/` 의 의미를 바꾸므로 **가짜 `FakeIORepository` 와 contract test 를 같이 고친다**. 시그니처는 진짜와 같아야 하고(`tests/gui/test_fake_store.py`), 호출 기록 dict 를 정확히 단언하는 테스트는 기대값을 고친다.

## 선행 step

- step 1: `audit.Entry.process_release`, `process_label`.
- step 2: `find_or_create(cur, name, release="")`, `audit.process_add(name, process_release=...)`.
- `phases/19-process-release/index.json` 의 step 0~4 summary 를 읽어라.

## 이 step의 목적

CSV 불러오기가 버전을 받는다. CSV 형식은 그대로다(버전 컬럼 없음). 버전은 불러오는 사람이 정한다.

```
IORepository.import_data(input_path, *, release="", actor="") -> int
```

| 대상 | 바뀐 뒤 |
|---|---|
| process 찾기 | 행마다 `(CdsLibName.strip(), release.strip())` 쌍으로 `find_or_create`. 한 파일의 모든 행이 같은 버전이다. 이름이 빈 행은 지금처럼 건너뛴다 |
| `release` 다듬기 | 앞뒤 공백을 지운다(CdsLibName 과 같은 규칙). 지운 뒤 빈 문자열이면 빈 버전 |
| 이미 있는 쌍 | 그 쌍에 device 를 더한다(CSV 는 누적, ADR-006). 같은 이름의 다른 버전은 건드리지 않는다 |
| 새로 만든 쌍의 이력 | `audit.process_add(name, process_release=release)` |
| 불러오기 이력 `audit.csv_import` | keyword `release=""` 를 받는다. process 가 하나뿐이면 지금처럼 `process_name` 을 채우고 `process_release` 도 채운다. 여럿이면 둘 다 빈다. detail 에 `"release": release` 를 더한다. summary 는 빈 버전이면 지금 그대로, 아니면 끝에 `f"  버전 {release}"` 를 붙인다 |
| `fetch_export_data` | **바꾸지 않는다.** `CdsLibName` 은 넘겨받은 `process_name`(이름) 그대로다. 버전은 CSV 에 쓰지 않는다 |
| 안 쓰는 `get_or_create_process_id` | 바꾸지 않는다(호출자 없음, 범위 밖) |

같은 CSV 를 다른 버전으로 불러오면 그 버전으로 device 가 복사된다. 이것은 승인된 사용법이다(예: `sf2p.csv` 를 `--version S00-V1.0.0.0` 으로 불러오기).

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`(ADR-006 CSV 누적, ADR-008 phase 7 보강 K5, ADR-017 Description), `/docs/ARCHITECTURE.md`(CSV 절)
- `src/genviewer/service/repo/io.py`: `_find_or_create`/`_process_id`(~56-68), `import_data`(~70-189: `new_processes`, `per_process`, 이력)
- `src/genviewer/service/repo/process.py`: `find_or_create`(step 2)
- `src/genviewer/service/repo/audit.py`: `csv_import`, `process_add`
- `tests/gui_support/fakes.py`: `FakeIORepository.import_data`(~673)
- `tests/gui/test_fake_repo_contract.py`: `CSV_TEXT`, `_import`, `test_import_makes_a_device_per_row_and_splits_cells`
- `tests/test_csv_import.py`(`test_process_id_*`, `test_a_failed_import_leaves_no_process_behind`), `tests/test_change_log.py`(CSV 불러오기의 process 이력 테스트 ~350-404)

## 작업

### 1. 테스트 먼저

contract test(가짜와 PostgreSQL 둘 다):
- `CSV_TEXT`(sf2p 행들)를 빈 버전으로 한 번, `release="V1"` 로 한 번 불러온다. `list_pairs()` 에 `("sf2p", "")` 와 `("sf2p", "V1")` 이 있고, 두 쌍의 device 수가 각각 CSV 행 수다(RED: 지금은 인자가 없다).
- `release="  V1  "` 은 `"V1"` 로 다듬어진다.
- 이미 있는 `("sf2p", "V1")` 에 다시 불러오면 그 쌍에만 더해지고 빈 버전 쪽 수는 그대로다.

DB:
- `tests/test_change_log.py`: `release="V1"` 로 새 process 를 만든 불러오기는 `process_add` 줄(`process_release == "V1"`, summary `process 추가  sf2p V1`)과 `csv_import` 줄(`process_release == "V1"`, summary 끝 `  버전 V1`, detail `release == "V1"`)을 남긴다. 빈 버전 불러오기의 줄은 지금과 같다.
- `tests/test_csv_import.py`: 실패한 불러오기(필수 컬럼 없음)는 버전이 있어도 process 를 남기지 않는다.

수정 전에는 위 테스트가 실패해야 한다.

### 2. 수정

- `service/repo/io.py`: 위 표대로. `_find_or_create`/`_process_id` 는 버전을 받되(기본값 `""`) 이름이 비면 None 인 지금 규칙을 지킨다.
- `service/repo/audit.py` `csv_import`: keyword `release`.
- `tests/gui_support/fakes.py` `FakeIORepository.import_data`: 같은 시그니처·의미.
- 호출자(`cli.py` `load`, `controllers/device_tab.py` `on_load_csv_requested`)는 바꾸지 않는다(빈 버전으로 지금처럼 돈다).

### 3. 변이 검사

- 진짜 `import_data` 가 `release` 를 무시하게 해 contract(PostgreSQL 쪽)가 실패하는지 본다. 되돌린다.
- 가짜가 `release` 를 다듬지 않게 해 contract(가짜 쪽)가 실패하는지 본다. 되돌린다.

## Acceptance Criteria

```bash
test -n "$GENDB_TEST_PG_DSN" || { echo "GENDB_TEST_PG_DSN 없음 → blocked"; exit 1; }
uv run pytest tests/gui/test_fake_repo_contract.py tests/gui/test_fake_store.py tests/test_csv_import.py tests/test_export.py tests/test_change_log.py tests/test_cli.py -q -rs   # DSN 사유의 SKIPPED 없음
uv run ruff check src tests
uv run pytest -q -rs
```

## 검증 절차

1. 위 AC 커맨드를 실행한다. `GENDB_TEST_PG_DSN` 이 없으면 아무것도 고치지 말고 blocked로 끝낸다.
2. 아키텍처 체크리스트를 확인한다.
   - CSV 형식(헤더·내보내기)이 그대로인가? `fetch_export_data` 를 바꾸지 않았는가?
   - 이미 있는 process 행을 잠그지 않는가(K5)?
   - 빈 버전 불러오기의 결과·이력이 지금과 같은가?
   - 가짜와 진짜가 같은 contract test를 통과하는가?
3. 결과에 따라 `phases/19-process-release/index.json` 의 step 5를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "io.import_data(path, *, release='', actor): 모든 행이 (CdsLibName, release.strip()) 쌍, process_add·csv_import 이력에 release(csv_import summary 끝 '  버전 V'). fetch_export_data 그대로. FakeIORepository 같은 의미. RED: <테스트 이름: 단언>. 변이: <결과>. DB 테스트: <N passed>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - `GENDB_TEST_PG_DSN` 없음 → `"status": "blocked"`, `"blocked_reason": "GENDB_TEST_PG_DSN 없음"` 후 즉시 중단

## 금지사항

- CSV 에 버전 컬럼을 읽거나 쓰지 마라. 이유: 승인된 결정은 "CSV 형식 그대로" 이고, molgen 은 버전을 파일 이름으로 구분한다. 등록 안 된 컬럼은 molgen 이 경고한다.
- 파일 이름에서 버전을 추측하지 마라. 이유: molgen 파일 이름은 버전의 점을 지운 것이라 원래 값을 되살릴 수 없다(승인 때 버린 선택지).
- `fetch_export_data`·`utils/exporter.py` 를 바꾸지 마라.
- CLI·GUI 호출자를 바꾸지 마라. 이유: step 6·10 의 일이다.
- 기존 테스트를 깨뜨리지 마라.
