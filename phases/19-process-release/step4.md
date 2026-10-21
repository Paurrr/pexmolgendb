# Step 4: release-clone

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
- step 4 `release-clone`: `ProcessRepository.clone` (DB) ← 이 step
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

- **`service/repo/process.py` 에 SQL을 더하는 step이다.** `GENDB_TEST_PG_DSN`(관리자 DSN)이 없으면 코드를 고치지 말고 `"status": "blocked"` 로 멈춘다. DB 테스트가 skip된 것은 통과가 아니다(`-rs` 로 확인한다).
- SQL은 PostgreSQL 10~15에서 돌아야 한다. 값은 바인드 파라미터로 넘기고, 탭 테이블·컬럼 이름은 `psycopg.sql` 로 조립하며 `service/schema.py` 의 `TABLE_COLUMNS` 에 있는 이름만 쓴다(CLAUDE.md CRITICAL).
- DB 테스트는 `tests/conftest.py` 의 `pg_dsn`·`db` fixture를 쓴다.
- **가짜(`FakeProcessRepository`)와 contract test 를 같이 고친다.** `tests/gui/test_fake_store.py` 의 `REPO_METHODS`·`PAIRS`·개수도 맞춘다.

## 선행 step

- step 1: `audit.process_add(name, process_release=...)`, `process_label`.
- step 2: `ProcessRepository` 가 (이름, 버전)을 받는다. `FakeStore.releases`, `store.add_process(name, release="")`, `REPO_METHODS` 16.
- `phases/19-process-release/index.json` 의 step 0~3 summary 를 읽어라.

## 이 step의 목적

새 버전을 기존 (process, 버전)의 내용으로 시작할 수 있게 DB 안 복제를 만든다. GUI 는 step 9 가 붙인다.

```
ProcessRepository.clone(src_name, src_release, name, release, *, actor="") -> int | None
```

| 경우 | 결과 |
|---|---|
| 성공 | 새 process `(name, release)` 를 만들고 원본의 device 를 모두 복사한다. 복사한 device 수를 돌려준다(원본이 비었으면 0) |
| `(name, release)` 가 이미 있음 | 아무것도 만들지 않고 None (지금 `add` 의 "이미 있음" 과 같은 뜻) |
| 원본 `(src_name, src_release)` 가 없음 | `LookupError(f"원본 process 가 없다: {process_label(src_name, src_release)}")` 를 낸다. 아무것도 만들지 않는다(롤백) |
| 그 밖의 예외 | 그대로 올린다. 아무것도 남지 않는다(한 트랜잭션) |

복사 규칙(불변식):
1. **한 시점 스냅샷.** device 와 탭 행이 같은 시점의 원본이어야 한다. 트랜잭션을 REPEATABLE READ 로 연다(첫 문장 `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ`. `Database.connection()` 이 이미 문장을 돌린 커넥션을 주면 psycopg 의 `isolation_level` 을 쓰고, 풀에 돌려줄 때 원래 값으로 되돌린다). 원본 행을 잠그지 않는다(`FOR UPDATE`/`FOR SHARE` 금지, K5). 이유: READ COMMITTED 면 device 를 복사한 뒤 남이 원본 탭을 저장해 커밋하면, 복사본의 탭 행이 그 뒤 시점이 되어 device 와 어긋난다.
2. 새 process 는 평범한 `INSERT INTO process (name, release)` 로 만든다. UniqueViolation 이면 None. `ON CONFLICT` 를 쓰지 마라(REPEATABLE READ 에서 동시 생성과 부딪히면 40001 이 날 수 있다. UniqueViolation 은 지금 `add` 와 같은 길이다).
3. device: `name`, `celltype`, `description`, `"order"` 를 그대로 복사한다. 새 id, `version = 1`(DDL 기본값), `updated_by = actor`, `updated_at = now()`. 원본의 순서(`ORDER BY "order", id`)를 지킨다. 같은 `order` 값을 가진 device 들의 상대 순서도 지켜져야 한다(새 id 가 원본 id 순서를 따른다).
4. **옛 id → 새 id 대응을 `INSERT … SELECT … RETURNING` 의 돌려받는 순서에 기대지 마라.** PostgreSQL 은 그 순서를 보장하지 않는다. device 를 하나씩 `INSERT … RETURNING id` 로 넣으며 대응표를 만들거나, 대응을 명시적으로 이을 수 있는 다른 방법을 쓴다.
5. 탭 행: `TABLE_COLUMNS` 의 탭 테이블마다 원본 device 들의 행을 `ORDER BY id` 로 읽어 새 device_id 로 넣는다. device 하나 안의 행 순서(id 순서)가 원본과 같아야 한다(화면·내보내기가 `ORDER BY id` 로 읽는다). 행이 많아도(device 수백 × 탭 14) libpq 파라미터 상한 65,535 를 넘는 문장 하나를 만들지 마라(`audit.BATCH_ROWS` 처럼 나누거나 `executemany`).
6. 원본은 바뀌지 않는다(device·탭 행·version·updated_at 그대로).
7. 이력은 **한 줄**: `audit.process_add(name, process_release=release, source=(src_name, src_release), devices=n)`. `process_add` 를 넓혀 `source`·`devices` keyword 를 받는다. `source` 가 None 이면 summary·detail 이 지금과 바이트까지 같다. 있으면 summary `f"process 추가  {process_label(name, release)}  ({process_label(src_name, src_release)} 에서 device {n}개 복사)"`, detail `{"source": {"name": src_name, "release": src_release}, "devices": n}`. 복사한 device 마다 이력 줄을 쓰지 마라(수백 줄이 된다).
8. advisory lock 은 필요 없다. 새 process 는 아직 아무도 고를 수 없다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`(ADR-004, ADR-005, ADR-008 phase 7 보강 K5), `/docs/ARCHITECTURE.md`(풀: `Database.connection()` 하나가 트랜잭션 하나)
- `src/genviewer/service/pool.py`: `Database.connection`
- `src/genviewer/service/repo/process.py` 전체(step 2 결과), `src/genviewer/service/repo/audit.py`(`process_add`, `BATCH_ROWS`, `capture_children` — 탭 테이블을 도는 본보기)
- `src/genviewer/service/repo/parameter.py`: 탭 행을 읽고 쓰는 SQL 조립(`psycopg.sql`, `TABLE_COLUMNS`)
- `src/genviewer/service/schema.py`: `TABLE_COLUMNS`, `child_tables()`
- `tests/gui_support/fakes.py`: `FakeStore`(`devices`, `tab_rows`, `_insert_device`, `_devices_of`, `_snapshot`/`_restore`), `FakeProcessRepository`, `REPO_METHODS`
- `tests/gui/test_fake_store.py`(`PAIRS`), `tests/gui/test_fake_repo_contract.py`(process·탭 테스트, 탭 행을 넣는 방법)

## 작업

### 1. 테스트 먼저

contract test(가짜와 PostgreSQL 둘 다):
- 원본 `("sf2p", "V1")` 에 device 셋(같은 `order` 값 둘 포함, 설명 하나는 비어 있지 않게)과 탭 행(한 device 에 InstTerm 3행, 값 순서가 id 순서와 다르게)을 넣는다. `clone("sf2p", "V1", "sf2p", "V2", actor="tester")` 는 3 을 돌려준다.
  - V2 의 `fetch_devices_by_process` 가 이름·celltype·설명·order 가 원본과 같은 순서로 나온다. id 는 원본과 다르고 `version == 1`, `updated_by == "tester"`.
  - V2 의 각 device 탭 행이 그 원본 device 의 행과 순서까지 같다.
  - 원본의 device·탭 행·version 이 그대로다.
- 대상이 이미 있으면 None 이고 아무것도 바뀌지 않는다.
- 원본이 비었으면 0 이고 대상 process 는 만들어진다.
- 원본이 없으면 `LookupError` 이고 대상 process 가 없다.
- 이름이 다른 대상도 된다(`clone("sf2p", "V1", "sf9x", "")`).

DB 만(`tests/test_process_clone.py` 새 파일 또는 `tests/test_concurrency.py`):
- **스냅샷(RED 의 핵심)**: 복제가 첫 device 를 INSERT 한 직후, 다른 커넥션이 원본 device 의 탭을 `replace_many_for_device` 로 바꾸고 커밋한다. 복사본의 그 device 탭 행은 **바뀌기 전** 값이다. 끼어들 자리는 커넥션/커서를 감싸는 대역(첫 `INSERT INTO device` 실행 뒤 콜백)이나 monkeypatch 로 만든다. 같은 테스트를 READ COMMITTED 로 되돌린 구현에 돌리면 실패해야 한다(변이 검사로 확인).
- 이력: `change_log` 에 한 줄(`action == "process_add"`, `process_release == "V2"`, summary `process 추가  sf2p V2  (sf2p V1 에서 device 3개 복사)`, detail 의 source·devices). 원본 행은 이력이 늘지 않는다.
- 탭 행이 많은 원본(예 device 200개 × 탭 행 여러 개)도 한 번에 복사된다(파라미터 상한).
- `process_add(name)`(source 없음)의 summary·detail 이 지금과 같다.

수정 전에는 `clone` 이 없어 모두 실패해야 한다.

### 2. 수정

- `service/repo/process.py`: `ProcessRepository.clone`.
- `service/repo/audit.py`: `process_add` 에 keyword `source`·`devices`.
- `tests/gui_support/fakes.py`: `FakeProcessRepository.clone`(같은 시그니처·의미. 원본이 없으면 `LookupError`, 대상이 있으면 None, 실패하면 store 를 되돌린다). `REPO_METHODS` 에 `"clone"`(17개), `test_fake_store.py` 의 `PAIRS`·개수.

### 3. 변이 검사

- REPEATABLE READ 를 빼 스냅샷 테스트가 실패하는지 본다. 되돌린다.
- 탭 행 복사의 `ORDER BY id` 를 빼거나 역순으로 해 순서 테스트가 실패하는지 본다(실패하지 않으면 테스트 데이터의 id 순서와 값 순서를 다르게 만든다). 되돌린다.
- 가짜 `clone` 이 `order` 를 복사하지 않게 해 contract(가짜 쪽)가 실패하는지 본다. 되돌린다.

## Acceptance Criteria

```bash
test -n "$GENDB_TEST_PG_DSN" || { echo "GENDB_TEST_PG_DSN 없음 → blocked"; exit 1; }
uv run pytest tests/gui/test_fake_repo_contract.py tests/gui/test_fake_store.py tests/test_change_log.py tests/test_concurrency.py -q -rs   # DSN 사유의 SKIPPED 없음
uv run pytest tests/test_process_clone.py -q -rs   # 새 파일을 만들었으면
uv run ruff check src tests
uv run pytest -q -rs
```

## 검증 절차

1. 위 AC 커맨드를 실행한다. `GENDB_TEST_PG_DSN` 이 없으면 아무것도 고치지 말고 blocked로 끝낸다.
2. 아키텍처 체크리스트를 확인한다.
   - 복제 전체가 한 트랜잭션·한 스냅샷인가? 원본 행을 잠그지 않는가?
   - 식별자는 `psycopg.sql` + `TABLE_COLUMNS`, 값은 바인드 파라미터인가?
   - 대응표를 RETURNING 순서에 기대지 않는가?
   - 이력이 한 줄이고 같은 트랜잭션인가?
   - 가짜와 진짜가 같은 contract test를 통과하는가?
3. 결과에 따라 `phases/19-process-release/index.json` 의 step 4를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "ProcessRepository.clone(src_name, src_release, name, release, *, actor) -> int|None(대상 있음)|LookupError(원본 없음): REPEATABLE READ <방법>, device 하나씩 RETURNING 대응, 탭 행 id 순 <방법>, 이력 process_add(source=, devices=) 한 줄. FakeProcessRepository.clone, REPO_METHODS 17. RED: <테스트 이름: 단언>. 변이: <결과>. DB 테스트: <N passed>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - `GENDB_TEST_PG_DSN` 없음 → `"status": "blocked"`, `"blocked_reason": "GENDB_TEST_PG_DSN 없음"` 후 즉시 중단

## 금지사항

- 원본 행에 `FOR UPDATE`/`FOR SHARE` 를 걸지 마라. 이유: 복제하는 동안 원본을 쓰는 사람이 `lock_timeout` 뒤 55P03 으로 실패한다(K5). 스냅샷이면 잠그지 않아도 일관된다.
- device 마다 이력을 남기지 마라. 이유: 복제 한 번이 수백 줄이 된다. 무엇을 복사했는지는 원본 이름·버전과 개수로 충분하다.
- `upsert_devices`·`replace_many_for_device` 를 불러 복사하지 마라. 이유: 트랜잭션이 갈라져 한 시점이 아니게 되고, 이력이 수백 줄 남는다.
- GUI·CLI 를 고치지 마라. 이유: step 9 의 일이다. CLI 에는 복제 명령을 만들지 않는다(승인 범위 밖).
- 기존 테스트를 깨뜨리지 마라.
