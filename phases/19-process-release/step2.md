# Step 2: process-repo-release

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
- step 2 `process-repo-release`: `ProcessRepository`·`find_or_create` 가 (이름, 버전)을 받는다, `list_pairs` (DB) ← 이 step
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

- **`service/repo/process.py` 의 SQL을 바꾸는 step이다.** `GENDB_TEST_PG_DSN`(관리자 DSN)이 없으면 코드를 고치지 말고 `"status": "blocked"` 로 멈춘다. DB 테스트가 skip된 것은 통과가 아니다(`-rs` 로 확인한다).
- SQL은 PostgreSQL 10~15에서 돌아야 한다. 값은 바인드 파라미터로 넘긴다.
- DB 테스트는 `tests/conftest.py` 의 `pg_dsn`·`db` fixture를 쓴다.
- `service/repo/` 의 의미를 바꾸므로 **가짜(`tests/gui_support/fakes.py`)와 contract test(`tests/gui/test_fake_repo_contract.py`)를 같이 고친다**. `tests/gui/test_fake_store.py` 는 가짜 메서드의 시그니처(기본값 포함)가 진짜와 같아야 하고, 가짜의 공개 메서드가 `REPO_METHODS`·`PAIRS` 와 정확히 같아야 한다고 단언한다. 가짜가 기록하는 호출 dict 에는 기본값 인자도 들어가므로, 인자를 더하면 그 dict 를 정확히 단언하는 테스트도 고친다.

## 선행 step

- step 0: `process(name, release)`, `UNIQUE (name, release)`, `find_or_create` 의 `ON CONFLICT (name, release)`.
- step 1: `audit.process_label`, `process_add`/`process_delete` 의 keyword `process_release`.
- `phases/19-process-release/index.json` 의 step 0·1 summary 를 읽어라.

## 이 step의 목적

`ProcessRepository` 와 `find_or_create` 가 (이름, 버전) 쌍을 다루게 한다. 호출자(GUI 툴바, CLI, `repo/io.py`)는 이 step 에서 바꾸지 않는다. 그들은 `release` 를 넘기지 않으므로 지금처럼 빈 버전 `''` 을 다룬다(바뀌는 것 없음).

| 메서드 | 바뀐 뒤 |
|---|---|
| `find_or_create(cur, name, release="")` (모듈 함수) | `WHERE name = %s AND release = %s` 로 찾고, 없으면 `INSERT INTO process (name, release) … ON CONFLICT (name, release) DO NOTHING RETURNING id`. 잠그지 않는 지금 성질(ADR-008, K5)을 지킨다 |
| `get_id(name, *, release="")` | 그 쌍의 id 또는 None |
| `add(name, *, release="", actor="")` | 그 쌍을 만든다. 이미 있으면 False(UniqueViolation). 이력 `audit.process_add(name, process_release=release)` |
| `delete(name, *, release="", actor="")` | **그 쌍 하나만** 지운다. 찾은 id 로 `DELETE FROM process WHERE id = %s`. 같은 이름의 다른 버전과 그 device·탭 행은 그대로다. 없으면 True(지금 계약). 이력 `audit.process_delete(..., process_release=release)` |
| `exists(name, *, release="")`, `count_devices(name, *, release="")` | 그 쌍 기준 |
| `get_or_create_id(name, *, release="", actor="")` | 그 쌍. 빈 이름이면 None(지금). 새로 만들었을 때만 이력 |
| `list_all()` | **서로 다른 이름**을 지금 순서(`ORDER BY name`, DB 정렬)로. 버전이 여럿이어도 이름은 한 번. History 의 process 필터 콤보가 쓴다 |
| `list_pairs()` (새 메서드) | `[(name, release), …]`. 이름은 `list_all` 과 같은 순서, 같은 이름 안에서는 버전을 코드포인트 순서로(`ORDER BY name, release COLLATE "C"`). 빈 버전 `''` 이 그 이름의 맨 앞이다. 툴바가 쓸 것이다(step 8) |
| `list_with_counts()` | 이 step 에서는 바꾸지 않는다(step 6 이 CLI 와 함께 바꾼다) |

버전 정렬을 `COLLATE "C"` 로 하는 이유: 기본 collation(예 en_US)은 `-`·`.` 를 첫 단계에서 무시해서 `S00-V1.0` 과 `S00V1` 의 순서가 Python 정렬(가짜)과 달라진다. 이름 순서는 지금 `list_all` 그대로 둔다(process 콤보 순서가 바뀌지 않게).

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`(ADR-005 이력, ADR-008 phase 7 보강: find_or_create 가 잠그지 않는 이유)
- `src/genviewer/service/repo/process.py` 전체
- `src/genviewer/service/repo/audit.py`: `process_add`, `process_delete`, `process_label`
- `src/genviewer/service/repo/io.py`: `_find_or_create`/`_process_id`(~56-68, `find_or_create(cur, name)` 를 부른다. 이 step 에서는 바꾸지 않는다), 안 쓰는 `get_or_create_process_id`(~50)
- `tests/gui_support/fakes.py`: `REPO_METHODS`(~47), `FakeStore.processes`(~148), `add_process`(~199), `_snapshot`/`_restore`(~305), `_process_id`(~321), `_insert_process`(~337), `_drop_process`(~366), `FakeProcessRepository`(~427-473)
- `tests/gui/test_fake_store.py`: `PAIRS`(~38-52), 메서드 수(15) 단언, `add` 호출 기록을 정확히 단언하는 곳(~128, 130, 216, 329)
- `tests/gui/test_fake_repo_contract.py`: process 테스트들(`test_get_or_create_id_is_stable_and_none_for_an_empty_name`, `test_add_creates_only_a_new_name`, `test_list_all_is_sorted_by_name`, `test_exists_and_count_devices`, `test_delete_takes_the_devices_and_tab_rows_with_it`)
- `tests/test_concurrency.py`: K5 테스트(`test_two_creators_of_a_new_process_share_one_row` 등), `tests/test_change_log.py`: process 추가·삭제 이력 테스트

## 작업

### 1. 테스트 먼저

contract test(가짜와 PostgreSQL 둘 다):
- `add("sf2p")` 뒤 `add("sf2p", release="V1")` 이 True, `add("sf2p", release="V1")` 을 또 하면 False.
- `get_or_create_id("sf2p")` 와 `get_or_create_id("sf2p", release="V1")` 의 id 가 다르고, 각각 두 번 불러도 같다.
- `exists`·`count_devices` 가 쌍마다 따로다(V1 에 device 를 둘 넣으면 `count_devices("sf2p", release="V1") == 2`, `count_devices("sf2p") ==` 빈 버전 쪽 수).
- **`delete("sf2p", release="V1")` 뒤 빈 버전 `sf2p` 의 device·탭 행이 그대로다(RED: 지금은 이름으로 지워 둘 다 사라진다).** V1 의 device·탭 행은 사라진다.
- `list_all() == ["sf2p", "sf4u"]`(버전이 여럿이어도 이름 한 번).
- `list_pairs()` 가 `("sf2p", "")`, `("sf2p", "S00-V1.0")`, `("sf2p", "S00V1")`, `("sf4u", "")` 순서다(코드포인트: `-` 가 `V` 보다 앞).

DB:
- `tests/test_concurrency.py`: 두 커넥션이 동시에 `find_or_create(cur, "sf9z", "V1")` 하면 한 행을 같이 쓴다(지금 K5 테스트의 버전 판). 이미 있는 쌍을 찾을 때 행을 잠그지 않는다(지금 테스트가 같은 성질을 보면 그것을 넓힌다).
- `tests/test_change_log.py`: `add("sf2p", release="V1")`·`delete("sf2p", release="V1")` 의 이력 줄 `process_release == "V1"`, summary `process 추가  sf2p V1` / `process 삭제  sf2p V1  device …`. `get_or_create_id(..., release="V1")` 가 새로 만들 때만 한 줄.

수정 전에는 위 테스트가 실패해야 한다(없는 인자, `list_pairs` 없음, 이름으로 지움).

### 2. 수정

- `service/repo/process.py`: 위 표대로. 쿼리는 모두 쌍으로 찾는다.
- `tests/gui_support/fakes.py`:
  - `FakeStore` 에 버전을 둔다. 권장: `processes: dict[int, str]`(id → 이름)는 그대로 두고 나란한 `releases: dict[int, str]` 을 더한다. 이유: `store.processes` 를 이름으로 읽는 테스트·헬퍼가 많다. `_snapshot`/`_restore`·`_insert_process(name, release="")`·`_drop_process`·`_process_id(name, release="")` 가 함께 다룬다.
  - 테스트용 `add_process(name, release="")`.
  - `FakeProcessRepository`: 진짜와 같은 시그니처·의미. `list_all` 은 서로 다른 이름을 정렬, `list_pairs` 는 (이름, 버전)을 정렬(가짜는 Python 정렬. contract 의 이름은 소문자 ASCII 라 DB 이름 순서와 같다).
  - `REPO_METHODS` 에 `"list_pairs"` 를 더하고(16개), `test_fake_store.py` 의 `PAIRS`·개수·호출 기록 기대값을 맞춘다. 모듈 docstring 의 개수 서술도 맞춘다.
- 호출자(`controllers/device_tab_toolbar.py`, `cli.py`, `repo/io.py`)는 바꾸지 않는다.

### 3. 변이 검사

- 진짜 `delete` 를 이름으로 지우게 되돌려(`WHERE name = %s`) 삭제 contract(PostgreSQL 쪽)가 실패하는지 본다. 되돌린다.
- `find_or_create` 의 SELECT 에서 `AND release = %s` 를 빼 contract 가 실패하는지 본다. 되돌린다.
- 가짜 `list_all` 에서 중복 제거를 빼 contract(가짜 쪽)가 실패하는지 본다. 되돌린다.

## Acceptance Criteria

```bash
test -n "$GENDB_TEST_PG_DSN" || { echo "GENDB_TEST_PG_DSN 없음 → blocked"; exit 1; }
uv run pytest tests/gui/test_fake_repo_contract.py tests/gui/test_fake_store.py tests/test_concurrency.py tests/test_change_log.py tests/test_csv_import.py tests/test_cli.py -q -rs   # DSN 사유의 SKIPPED 없음
uv run pytest tests/gui -q
uv run ruff check src tests
uv run pytest -q -rs
```

## 검증 절차

1. 위 AC 커맨드를 실행한다. `GENDB_TEST_PG_DSN` 이 없으면 아무것도 고치지 말고 blocked로 끝낸다.
2. 아키텍처 체크리스트를 확인한다.
   - `delete` 가 그 쌍 하나만 지우는가? 같은 이름의 다른 버전 device·탭 행이 남는가?
   - `find_or_create` 가 이미 있는 행을 잠그지 않는가(K5)?
   - 이력이 저장과 같은 트랜잭션인가?
   - 가짜와 진짜가 같은 contract test를 통과하는가? `REPO_METHODS`·`PAIRS` 가 맞는가?
   - 호출자를 바꾸지 않았는가(빈 버전 동작 그대로)?
3. 결과에 따라 `phases/19-process-release/index.json` 의 step 2를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "process.py: find_or_create(cur, name, release='') + 모든 메서드 keyword release='', delete 는 id 로 그 쌍만, list_all 은 DISTINCT 이름, 새 list_pairs()(name 순, release COLLATE C). 이력에 process_release. FakeStore.releases(병렬 dict)·add_process(name, release=''), REPO_METHODS 16. RED: <테스트 이름: 단언>. 변이: <결과>. 고친 기존 테스트: <이름>. DB 테스트: <N passed>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - `GENDB_TEST_PG_DSN` 없음 → `"status": "blocked"`, `"blocked_reason": "GENDB_TEST_PG_DSN 없음"` 후 즉시 중단

## 금지사항

- `release` 인자를 필수로 만들지 마라(기본값 `""` keyword). 이유: GUI·CLI·io 호출자는 뒤 step 이 바꾼다. 그 전까지 빈 버전으로 지금처럼 돌아야 suite 가 step 마다 초록이다.
- `find_or_create` 에 `ON CONFLICT … DO UPDATE` 나 `FOR UPDATE` 를 쓰지 마라. 이유: CSV 불러오기가 커밋할 때까지 GUI 가 같은 process 를 고르거나 저장하지 못했다(K5, ADR-008).
- `list_all` 의 반환 타입을 바꾸지 마라(이름 목록). 이유: History 가 그대로 쓴다. 쌍이 필요한 곳은 `list_pairs` 를 쓴다.
- `list_with_counts`·`repo/io.py`·`repo/device.py`·`repo/parameter.py`·컨트롤러·`cli.py` 를 고치지 마라. 이유: step 3·5·6·8 의 일이다.
- `seeded_store`(GUI 시드)를 바꾸지 마라.
- 기존 테스트를 깨뜨리지 마라. 호출 기록을 정확히 단언하던 테스트만 기대값을 고친다.
