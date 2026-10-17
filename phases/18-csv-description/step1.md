# Step 1: io-description

## 배경 (phase 18 공통)

이 저장소는 평소에 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 18은 예외로 **사용자가 2026-10-17 승인한 기능**이다(known-issues K44). 승인된 동작은 다음과 같다.

> 내보내기(GUI·CLI, CSV·xlsx)는 InstCellName 다음에 Description 컬럼을 쓴다. 불러오기는 Description 컬럼이 있으면 그 값을 device.description 에 넣고, 없으면(옛 CSV) 지금처럼 빈 값이다. Virtuoso로 보내는 payload는 바꾸지 않는다.

지금은 이렇게 된다.
- molgen CSV 형식에 Description 컬럼이 없다(`molgen/genMOLDB_config.il` 의 `pexGenDB_GenDev_Get_Header_Type()`).
- 그래서 `IORepository.import_data` 는 `INSERT INTO device (process_id, name, celltype, updated_by)` 로 새 device를 만들고, description은 DDL 기본값 `''` 이 된다.
- `fetch_export_data` 의 헤더는 `CellType, CdsLibName, InstCellName` + 탭이다.
- 결국 화면에서 적은 description은 내보낸 CSV에 없고, 그 CSV를 다시 불러와도 되살아나지 않는다.

이 phase의 step은 다음 순서로 간다.
- step 0: Virtuoso payload가 고정 컬럼을 이름으로 고르고 Description을 뺀다(끝났다).
- step 1(이 step): `io.py` 의 import·export, 가짜 `FakeIORepository`, contract test. DB step이다.
- step 2: GUI 내보내기가 화면의 description을 넘긴다.

**선행 조건(이 phase 범위 밖)**: molgen의 `pexGenDB_GenDev_Get_Header_Type()` 에 `'Description "string"` 을 등록해야 한다(`'Status` 와 같은 방식). molgen `CSV_COLUMNS.md` 도 고쳐야 한다. 등록하지 않으면 molgen이 셀마다 `Unknown header type` warn을 낸다. 운영 배포 전에 molgen 쪽이 먼저 나가야 한다. gendb 테스트는 molgen 없이 돈다. **molgen 저장소를 고치지 마라.**

모든 step에 같은 규칙이 적용된다.
1. 기능이라 TDD로 한다. 새 동작을 단언하는 테스트를 먼저 쓰고, 수정 전에 실패하는 것을 본다(RED). 그 테스트 이름과 단언을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다. 가짜 쪽 contract test는 DB 없이도 돈다.
3. 고친 뒤 구현을 손으로 망가뜨려 새 테스트가 실패하는지 보고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라.
4. 이 파일의 행 번호는 2026-10-17(phase 6 전) 기준 대략값이다. phase 7(K5 import 잠금, K32 import의 process 이력, K9 파라미터 한도, K12 xlsx 리터럴)이 `io.py`·`exporter.py` 를 바꿨다. 이름으로 찾아라.
   - phase 14~17(구조 제안 P2 Prompts·P4 공개 API·P3 SaveCoordinator·P5 남은 동기 DB 호출을 워커로, `docs/notes/architecture-proposal.md`)이 이 phase보다 먼저 끝났을 수 있다. 대화상자 대역(`FakeDialogs` → Prompts 가짜), private 이름(`_ask_export_path` 등), 내보내기·보내기의 DB 호출 위치(워커)가 바뀌었으면 실제 코드를 따르고 summary에 적는다. 그 구조를 되돌리지 않는다.
5. `config/tab_config.json` 의 키 구조를 바꾸지 않는다. Description은 탭이 아니라 device 컬럼이다(`device.description TEXT NOT NULL DEFAULT ''`, 이미 있다). 스키마는 바꾸지 않는다.
6. 사용자에게 보이는 문구(알림·로그·CLI 출력)를 새로 만들거나 바꾸지 않는다.
7. 문서(`README.md` 의 `## CSV 컬럼과 탭`, `docs/PRD.md` 3번, molgen 선행 조건)는 phase 마무리에서 고친다. step에서는 바꾸지 않는다.

## DB step 규칙

- **`service/repo/io.py` 의 SQL을 바꾸는 step이다.** `GENDB_TEST_PG_DSN`(관리자 DSN)이 없으면 코드를 고치지 말고 `"status": "blocked"` 로 멈춘다. DB 테스트가 skip된 것은 통과가 아니다(`-rs` 로 확인한다).
- SQL은 PostgreSQL 10~15에서 돌아야 한다. 값은 바인드 파라미터로 넘기고 식별자는 `psycopg.sql` 로 만든다(CLAUDE.md CRITICAL).
- DB 테스트는 `tests/conftest.py` 의 `pg_dsn`·`db` fixture를 쓴다.
- `service/repo/` 의 의미를 바꾸므로 **가짜 `FakeIORepository` 와 contract test(`tests/gui/test_fake_repo_contract.py`)를 같이 고친다**(CLAUDE.md 테스트 관례). 같은 기대값을 가짜와 실제 PostgreSQL에 돌린다.

## 이 step의 목적

`IORepository` 가 Description을 왕복시키게 한다.

| 경로 | 지금 | 바뀐 뒤 |
|---|---|---|
| `fetch_export_data` 헤더 | `CellType, CdsLibName, InstCellName, <탭…>` | `CellType, CdsLibName, InstCellName, Description, <탭…>`. device가 몇 개든, description이 전부 비어도 항상 쓴다 |
| `fetch_export_data` 행 | `[celltype, process_name, name, <탭 셀…>]` | `[celltype, process_name, name, description, <탭 셀…>]`. description은 `info.get("description") or ""` 이고 **device_info의 값**이다. name·celltype처럼 DB를 다시 읽지 않는다(`test_export_rows_carry_the_values_in_device_info` 와 같은 의미) |
| `import_data`, CSV에 `Description` 컬럼이 있음 | 무시하고 `''` | 그 행의 값을 그대로 device.description에 넣는다(CellType·InstCellName처럼 다듬지 않는다) |
| `import_data`, `Description` 컬럼이 없음(옛 CSV) | `''` | 지금과 같다(`''`) |
| `import_data`, `Description` 이 반복됨(`Description.1`) | 무시 | 정확히 `Description` 인 첫 컬럼만 본다. 나머지는 지금처럼 무시한다 |
| change_log | 불러오기 한 줄(`audit.csv_import`) | 지금과 같다 |
| CLI `export`/`load` | | 코드 변경 없이 따라온다. `export` 는 `fetch_devices_by_process` 의 dict(`description` 포함)를 `{**d, "process_name": …}` 로 넘긴다 |
| GUI `send_device_data` | | step 0이 Description을 payload에서 뺀다. 그 `device_info` 에는 description이 없어 행 값이 `''` 이지만 보내지 않는다 |
| GUI `export_selected_devices` | | 아직 description을 넘기지 않아 값이 빈다. step 2가 고친다 |

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`(ADR-002 tab_config 단일 원본), `/docs/ARCHITECTURE.md`(io.py, CSV 흐름), `README.md` `## CSV 컬럼과 탭`(이름이 같은 행은 각각 device가 된다)
- `src/genviewer/service/repo/io.py`: `import_data`(~66-170, device INSERT ~118-122), `fetch_export_data`(~172-257, 헤더 ~217, 행 ~245)
- `src/genviewer/service/schema.py`: device DDL(`description TEXT NOT NULL DEFAULT ''`)
- `src/genviewer/cli.py`: `load`, `export`
- `tests/gui_support/fakes.py`: `FakeIORepository.import_data`(`store._insert_device(process_id, name, celltype, description, order, actor, now)` 에 지금 `""` 를 넘긴다), `FakeIORepository.fetch_export_data`
- `tests/gui/test_fake_repo_contract.py`: `CSV_TEXT`, `_import`, `_only_device`, `_device`, export 헤더를 정확히 단언하는 테스트(~661-681), `test_export_rows_carry_the_values_in_device_info`(~684-)
- `tests/test_csv_import.py`: `BASE_HEADERS`, `_round_trip`(DB), `test_a_csv_without_the_required_columns_raises`
- `tests/test_export.py`, `tests/test_cli.py`(`test_an_exported_file_loads_back`, `test_export_writes_every_device_of_the_process`, `HEADERS`)

## 작업

### 1. 테스트 먼저

contract test(`tests/gui/test_fake_repo_contract.py`, 가짜와 PostgreSQL 둘 다):
- 기존 정확한 헤더 단언에 `"Description"` 을 InstCellName 다음에 넣고, 행에도 4번째 값을 넣는다(`_device()` 는 description `""`).
- `test_export_rows_carry_the_values_in_device_info`: device_info에 `"description": "화면 설명"` 을 더하고, 행 4번째가 그 값인지 단언한다.
- 새 테스트: Description 컬럼이 있는 CSV(값에 공백·쉼표·한글, 예 `"ESD 용, 2단"`)를 불러오면 `fetch_devices_by_process` 의 description이 그 값이다.
- 새 테스트: Description 컬럼이 없는 CSV(`CSV_TEXT` 그대로)를 불러오면 description이 `""` 다.
- 새 테스트(왕복): 불러오기 → `fetch_export_data`(fetch한 dict에 process_name을 붙여 넘긴다) → `utils.exporter.write_csv` → 다시 `import_data` → 두 번째 device들의 description이 첫 번째와 같다.

DB 테스트:
- `tests/test_csv_import.py`: `_round_trip` 으로 Description이 공백까지 그대로 나오는지, Description이 없는 CSV의 export 값이 `""` 인지 본다.
- `tests/test_export.py`: 헤더 4번째가 `Description` 이다.
- `tests/test_cli.py`: `genviewer export` 로 쓴 파일의 Description 열에 저장된 description이 있고, `load` 로 다시 넣으면 따라온다. `test_an_exported_file_loads_back` 을 넓히거나 새 테스트를 둔다.

수정 전에는 헤더 단언과 Description 값 단언이 실패해야 한다(가짜·진짜 모두).

### 2. 수정

- `service/repo/io.py`
  - `import_data`: `"Description" in df.columns` 면 `row["Description"]`, 아니면 `""` 를 device INSERT의 `description` 에 넣는다. 바인드 파라미터로 넘긴다.
  - `fetch_export_data`: 헤더와 행에 Description을 InstCellName 다음에 넣는다.
  - 고정 헤더 목록이 두 군데 이상이면 모듈 상수 하나로 묶어도 된다.
- `tests/gui_support/fakes.py` `FakeIORepository`: 진짜와 같은 의미로 고친다. 같은 규칙을 다르게 쓰지 마라. 이유: contract test가 둘을 같은 기대값으로 묶는다.
- `utils/exporter.py`(CSV·xlsx 쓰기)는 헤더·행을 그대로 쓰므로 고치지 않는다. phase 7 step 8의 xlsx 리터럴 처리가 Description에도 그대로 적용되는지만 확인한다(`=` 로 시작하는 description).

### 3. 변이 검사

- 진짜 `import_data` 가 Description을 읽지 않게 손으로 바꾼다. DB 테스트와 contract test(PostgreSQL 쪽)가 실패하는지 본다. 되돌린다.
- 가짜 `fetch_export_data` 에서 Description을 빼 본다. contract test(가짜 쪽)가 실패하는지 본다. 되돌린다.

## Acceptance Criteria

```bash
test -n "$GENDB_TEST_PG_DSN" || { echo "GENDB_TEST_PG_DSN 없음 → blocked"; exit 1; }
uv run pytest tests/gui/test_fake_repo_contract.py tests/test_csv_import.py tests/test_export.py tests/test_cli.py -q -rs   # DSN 사유의 SKIPPED 없음 (수정 전에는 새 단언이 실패해야 한다)
uv run pytest tests/gui/test_send_device_data.py -q   # step 0 의 payload 테스트 그대로 통과 (step 0 이 다른 파일을 만들었으면 그 파일)
uv run ruff check src tests
uv run pytest -q -rs
```

## 검증 절차

1. 위 AC 커맨드를 실행한다. `GENDB_TEST_PG_DSN` 이 없으면 아무것도 고치지 말고 blocked로 끝낸다.
2. 아키텍처 체크리스트를 확인한다.
   - SQL이 PG 10~15에서 도는가? 값이 바인드 파라미터인가?
   - `tab_config.json`·스키마를 바꾸지 않았는가?
   - 가짜와 진짜가 같은 contract test를 통과하는가?
   - Description이 없는 옛 CSV가 지금처럼 들어가는가?
   - Virtuoso payload가 그대로인가(step 0 테스트)?
3. 결과에 따라 `phases/18-csv-description/index.json` 의 step 1을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "io.py: export 헤더/행에 InstCellName 다음 Description(device_info 값), import 는 Description 컬럼이 있으면 device.description 으로(없으면 ''). FakeIORepository 같은 의미, contract test 갱신. RED: <테스트 이름: 단언>. 변이: <결과>. DB 테스트: <N passed>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - `GENDB_TEST_PG_DSN` 없음 → `"status": "blocked"`, `"blocked_reason": "GENDB_TEST_PG_DSN 없음"` 후 즉시 중단

## 금지사항

- `tab_config.json` 에 Description을 넣지 마라. 이유: 탭이 되어 자식 테이블과 화면 탭이 생긴다. Description은 device 컬럼이다.
- 같은 이름의 기존 device에서 description을 가져오거나 기존 device를 고치지 마라. 이유: "CSV 행 하나 = device 하나" 다(README). 불러오기는 새 device만 만든다.
- Description 컬럼이 없는 CSV를 거부하거나 경고하지 마라. 이유: 옛 CSV와 molgen이 만든 CSV는 그 컬럼이 없다. 승인된 동작은 "없으면 빈 값" 이다.
- change_log 형식(`audit.csv_import`)을 바꾸지 마라. 이유: 승인 범위 밖이다.
- molgen 저장소와 `docs/`·README를 바꾸지 마라. 이유: molgen은 선행 조건이고, 문서는 phase 마무리에서 고친다.
- GUI 컨트롤러(`controllers/`)를 바꾸지 마라. 이유: step 0·2의 일이다.
- 기존 테스트를 깨뜨리지 마라. 정확한 헤더를 단언하던 테스트는 승인된 동작에 맞게 기대값을 고친다. 고친 테스트 이름을 summary에 적는다.
