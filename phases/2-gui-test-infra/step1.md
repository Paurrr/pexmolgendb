# Step 1: fake-repos

## 배경 (phase 2 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). 다음 phase `3-gui-save-fixes` 와 `4-gui-robustness` 는 GUI 컨트롤러의 버그를 실패하는 테스트로 재현한 뒤 고친다. phase 2는 그 테스트를 쓸 수 있는 **GUI 테스트 기반만** 깐다. step 0은 pytest-qt와 모달 대화상자 가짜(`dialogs` fixture), step 1은 실제 repo와 같은 의미의 가짜 repo(`tests/gui_support/fakes.py`), step 2는 가짜 repo에 붙은 컨트롤러 fixture와 헬퍼다. **`src/` 는 한 줄도 바꾸지 않는다.**

모든 step에 같은 규칙이 적용된다.
1. `src/` 를 고치지 않는다. 이 phase에는 고칠 버그가 없으므로 "실패하는 테스트로 먼저 재현" 규칙 대신 **지금 코드의 동작을 그대로 드러내는 테스트만** 쓴다. 테스트를 쓰다 버그로 보이는 동작을 만나면 고치지 말고, 그 동작을 단언하지도 말고(뒤 phase가 고치면 깨질 단언을 남기지 않는다), summary에 `파일:행 — 관찰` 로 적는다.
2. 새 의존성은 pytest-qt 하나뿐이다(사용자 승인 2026-10-17). step 0이 넣었다.
3. 이 파일들에 적은 이름(fixture, 클래스, 메서드, 헬퍼, 모듈 경로)은 phase 3/4 step 파일이 그대로 쓴다. 이름·인자·의미를 바꾸지 마라. 더하는 것은 괜찮다.
4. 테스트 기반도 변이 검사를 한다. 가짜·fixture의 핵심 규칙 하나를 손으로 망가뜨려 그것을 지키는 테스트가 실패하는지 보고 되돌린다. `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 다른 변경까지 사라진다.
5. "아무 일도 일어나지 않음"은 고정 대기(`qtbot.wait`, `time.sleep`) 대신 fake가 기록한 호출이나 컨트롤러 상태를 `qtbot.waitUntil` 로 기다린 뒤 단언한다.
6. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.

## 이 step의 목적

컨트롤러가 부르는 repo 메서드 14개를 DB 없이 흉내 내는 가짜를 만든다. 이 가짜가 phase 3/4 RED 테스트의 "서버"다. 의미가 실제와 다르면 RED가 거짓이 된다. 그래서 같은 기대값을 가짜와 실제 PostgreSQL repo 양쪽에 돌리는 contract test로 의미를 고정한다. 테스트가 장애(`fail_next`)와 남의 변경(`touch_device`, `remove_device`)을 만들 수 있고, 일어난 호출을 기록(`calls`)으로 볼 수 있어야 한다.

## 읽어야 할 파일

먼저 아래 파일들을 읽고 설계 의도를 파악하라.

- `/CLAUDE.md`, `/docs/ARCHITECTURE.md`(데이터 흐름: device 저장, 탭 저장, 변경 감지, 용어 etag), `/docs/ADR.md`(ADR-004 낙관적 잠금, ADR-006 이름 중복 허용)
- `src/genviewer/controllers/device_tab.py` — `set_repo` (~91-97)가 네 repo를 **이 모듈의 이름** `IORepository`, `DeviceRepository`, `ParameterRepository`, `ProcessRepository` 로 만든다(step 2가 이 이름을 가짜로 바꾼다). `_open_database` (~129-136), `connect_db` (~138-169: `db.cfg.dsn` 을 로그에 쓰고 다시 붙을 때 `db.close()`), `_poll_remote_changes` (~176-194: `Task` 워커 스레드에서 `repo.etag`)
- 컨트롤러가 부르는 repo 메서드(가짜가 구현할 전부, 2026-10-17 grep):
  - `DeviceRepository`: `fetch_devices_by_process`, `etag`, `upsert_device`, `upsert_devices` — `controllers/device_table.py` ~263, ~311, ~323, ~375, `controllers/device_tab.py` ~189
  - `ParameterRepository`: `fetch_by_device`(`device_table.py` ~169, `tab_section.py` ~189), `replace_many_for_device`(`parameter_tab.py` ~97)
  - `ProcessRepository`: `add`, `list_all`, `exists`, `count_devices`, `delete`, `get_or_create_id`(`device_tab_toolbar.py` ~86-147)
  - `IORepository`: `import_data`(`device_tab.py` ~339), `fetch_export_data`(`device_tab.py` ~289, `device_table.py` ~424)
- 실제 의미: `src/genviewer/service/repo/device.py`(전체: `SaveResult`, `etag_key`, `_preflight`, `_update_existing`, `_insert_new`), `repo/parameter.py`(`_check`, `replace_many_for_device`), `repo/process.py`, `repo/io.py`(`split_cell`, `import_data`, `fetch_export_data`), `service/errors.py`(`Conflict`, `StaleWriteError`), `service/pool.py`(`Database`: `cfg`, `user`, `open`, `close`, `connection`, `ping`), `service/config.py`(`DbConfig`), `service/schema.py`(`TABLE_COLUMNS`, device DDL 기본값 ~110-121)
- 실제 의미를 지키는 DB 테스트(contract test 기대값의 출처): `tests/test_concurrency.py`, `tests/test_change_detection.py`, `tests/test_csv_import.py`, `tests/test_export.py`, `tests/conftest.py`(`db`, `two_processes`)
- 이전 step에서 만든 파일: `pyproject.toml`(`pythonpath = ["tests"]`, `qt_api`), `tests/gui/conftest.py`, `tests/gui_support/__init__.py`, `tests/gui_support/dialogs.py`, `tests/gui/test_dialogs_fixture.py`

## 작업

### 1. 가짜 (`tests/gui_support/fakes.py`, 새 파일)

```python
class FakeStore:
    processes: dict[int, str]                     # id -> name
    devices: dict[int, dict]                      # id -> 행 dict (키는 아래 "공통")
    tab_rows: dict[str, dict[int, list[dict]]]    # table -> device_id -> 행 목록
    calls: list[tuple[str, dict]]                 # (메서드 이름, 인자 dict). 끝난 호출만
    lock: threading.RLock
    def fail_next(self, method: str, exc: BaseException) -> None: ...
    def calls_of(self, method: str) -> list[dict]: ...
    def open_database(self, dsn: str) -> "FakeDatabase": ...
    # 시드·조작 (calls 에 남지 않고 fail_next 를 따르지 않는다)
    def add_process(self, name: str) -> int: ...
    def add_device(self, process_id: int, name: str, celltype: str, *,
                   description: str = "", order: int = 0, updated_by: str = "seed") -> dict: ...
    def set_rows(self, table: str, device_id: int, rows: list[dict]) -> None: ...
    def touch_device(self, device_id: int, *, actor: str = "other", **changes) -> int: ...
    def remove_device(self, device_id: int) -> None: ...
    def find_device(self, name: str) -> dict: ...
    def rows(self, table: str, device_id: int) -> list[dict]: ...

class FakeDatabase:
    def __init__(self, store: FakeStore, dsn: str = "") -> None: ...
    store: FakeStore
    cfg: DbConfig            # DbConfig(dsn=dsn or "fake", app_user=current_user())
    user: str                # property, cfg.app_user
    closed: bool
    def open(self) -> None: ...
    def close(self) -> None: ...
    def ping(self) -> bool: ...
    def connection(self): ...   # 항상 AssertionError

class FakeProcessRepository:
    def __init__(self, db: FakeDatabase) -> None: ...
    def add(self, name: str, *, actor: str = "") -> bool: ...
    def delete(self, name: str, *, actor: str = "") -> bool: ...
    def exists(self, name: str) -> bool: ...
    def list_all(self) -> list[str]: ...
    def count_devices(self, name: str) -> int: ...
    def get_or_create_id(self, name: str, *, actor: str = "") -> int | None: ...

class FakeDeviceRepository:
    def __init__(self, db: FakeDatabase) -> None: ...
    def fetch_devices_by_process(self, process_id: int) -> list[dict]: ...
    def etag(self, process_id: int) -> dict: ...
    def upsert_device(self, process_id: int, device: dict, *, actor: str = "") -> dict: ...
    def upsert_devices(self, process_id: int, devices: list[dict], *,
                       deleted: dict[int, int] | None = None, actor: str = "",
                       force: bool = False) -> SaveResult: ...

class FakeParameterRepository:
    def __init__(self, db: FakeDatabase) -> None: ...
    def fetch_by_device(self, table_name: str, columns: list[str], device_id: int) -> list[dict]: ...
    def replace_many_for_device(self, device_id: int,
                                payload: dict[str, tuple[list[str], list[dict]]], *,
                                expected_version: int | None = None, actor: str = "",
                                force: bool = False) -> int: ...

class FakeIORepository:
    def __init__(self, db: FakeDatabase) -> None: ...
    def import_data(self, input_path: str, *, actor: str = "") -> int: ...
    def fetch_export_data(self, device_info: list[dict[str, str]]) -> tuple[list[str], list[list[str]]]: ...
```

가짜 repo는 실제처럼 `Database` 자리에 `FakeDatabase` 를 받고 `db.store` 를 쓴다. 매개변수 이름·종류·기본값은 실제 메서드와 같아야 한다(아래 시그니처 테스트). 실제 repo에 있지만 컨트롤러가 부르지 않는 메서드(`get_id`, `list_with_counts`, `replace_all_for_device`, `get_or_create_process_id`)는 만들지 않는다.

### 2. 의미 (실제 repo에서 옮긴 규칙)

**공통**
- 메서드 하나는 트랜잭션 하나처럼 원자적이다. `store.lock` 을 잡고 돌고(GUI 스레드와 `run_blocking`/`Task` 워커 스레드가 함께 부른다), 예외를 내면 store를 바꾸지 않는다.
- `calls` 에는 **끝난** 호출(정상 반환이든 예외든)을 `(이름, 인자)` 로 남긴다. 인자는 매개변수 이름 → 값 dict이고, 기본값을 채운 **호출 시점의 deep copy** 다(`inspect.signature(...).bind(...)` + `apply_defaults()`). 이름은 메서드 이름 그대로(`"upsert_devices"`). `FakeDatabase` 는 `"db.open"`, `"db.close"`, `"db.ping"`, `FakeStore.open_database` 는 `"open_database"`. repo 메서드 14개의 이름은 서로 겹치지 않는다. 끝난 뒤 기록하는 이유: 테스트가 `qtbot.waitUntil(lambda: store.calls_of("etag"))` 로 기다렸을 때 가짜 쪽 일은 이미 끝나 있어야 한다.
- `fail_next(method, exc)`: 그 이름의 다음 호출 하나가 store를 건드리지 않고 `exc` 를 낸다(호출은 `calls` 에 남는다). 여러 번 부르면 순서대로 쌓인다. 모르는 이름이면 `ValueError`.
- 돌려주는 dict·list는 복사본이다. 예외: `upsert_device`/`upsert_devices` 는 실제처럼 **받은 dict에** `id`/`version` 을 써 넣고, `upsert_device` 는 받은 그 dict를, `upsert_devices` 는 `SaveResult(devices=받은 그 리스트, …)` 를 돌려준다.
- 쓰기 호출 하나가 가짜 시계를 한 번 진행한다(`2026-10-17 09:00:00+00:00` 에서 1초씩, tz-aware `datetime`). 한 호출에서 쓴 행은 같은 `updated_at` 을 갖는다(실제 `now()` 는 트랜잭션 시작 시각). 시드·조작 헬퍼의 쓰기도 시계를 진행한다.
- id는 process와 device가 각각 1부터 오르는 별개 시퀀스이고, 지운 id는 다시 쓰지 않는다.
- device 행 dict의 키는 `id, process_id, name, celltype, description, order, version, updated_at, updated_by`(실제 `_SELECT_COLUMNS`). 새 행 기본값: description `""`, order `0`, version `1`, updated_by = actor.
- 탭 행: `tab_rows[table][device_id]` 는 그 테이블의 **모든** 컬럼(`schema.TABLE_COLUMNS[table]`)을 가진 dict의 리스트이고, 순서는 넣은 순서다(실제 `ORDER BY id`).
- device가 지워지면(process 삭제 cascade 포함) 그 device의 탭 행도 모두 사라진다(`ON DELETE CASCADE`).
- change_log(audit)는 흉내 내지 않는다.

**ProcessRepository**
- `list_all()`: 이름 오름차순.
- `add(name, *, actor)`: 이미 있으면 False(실제는 UniqueViolation을 잡는다), 없으면 만들고 True. 이름을 strip하지 않는다.
- `exists(name)`. `count_devices(name)`: process가 없으면 0.
- `delete(name, *, actor)`: process와 그 device·탭 행을 지운다. 없는 이름이어도 True.
- `get_or_create_id(name, *, actor)`: 빈 이름(falsy)이면 None. 있으면 그 id, 없으면 만들어서 id.

**DeviceRepository**
- `fetch_devices_by_process(process_id)`: 그 process의 device를 `(order, id)` 순으로.
- `etag(process_id)`: `{"n": 개수, "mx": max(updated_at) 또는 None, "vs": sum(version) 또는 0, "who": (updated_at, id)가 가장 큰 행의 updated_by 또는 None}`. `etag_key()` 에 그대로 들어가야 한다.
- `upsert_device(process_id, device, *, actor)`: `device.get("id") is None` 이면 INSERT(name, celltype, `description or ""`, `order` 기본 0, version 1, updated_by=actor)하고 `device["id"]`, `device["version"]` 을 쓴다. id가 있으면 **version 검사 없이** process_id·name·celltype·description(`or ""`)·order(기본 0)를 쓰고 version+1, updated_at, updated_by=actor. 값이 같아도 올린다. 그 id의 행이 없으면 아무것도 쓰지 않고 device를 그대로 돌려준다(예외 없음).
- `upsert_devices(process_id, devices, *, deleted=None, actor="", force=False) -> SaveResult`:
  1. `deleted = deleted or {}`. devices와 deleted가 모두 비면 `SaveResult(devices)` 를 돌려주고 아무것도 하지 않는다(시계도 그대로).
  2. 사전 검사(`force` 가 아닐 때만): id가 있는 각 d와 deleted의 각 (id, version)에 대해, 행이 없으면 `Conflict(id, <d 쪽은 d.get("name", ""), deleted 쪽은 "">, "deleted")`, 기대 version이 None이 아니고 행의 version과 다르면 `Conflict(id, 행 name, "stale", 행 updated_by, 행 updated_at)`. 하나라도 있으면 아무것도 쓰지 않고 `StaleWriteError(conflicts)`(devices 순서, 그다음 deleted 순서). 행은 process와 상관없이 id로 찾는다.
  3. 삭제: deleted의 id 중 **process_id가 이 process인** 행만 지운다(다른 process로 옮겨진 행은 남는다). `deleted` 수 = 실제로 지운 수.
  4. 수정: id가 있는 각 d에 대해, 행이 있고, (`force` 이거나 행 version == `d.get("version")`)이고, `(name, celltype, description, order)` 가 `(d.get("name"), d.get("celltype"), d.get("description") or "", d.get("order", 0))` 와 다를 때만 그 네 값을 쓰고 version+1, updated_at, updated_by=actor. process_id는 바꾸지 않는다. 쓴 행만 `d["version"]` 을 새 값으로 바꾼다. `force` 가 아닌데 `d.get("version")` 이 None이면 맞는 행이 없어 쓰지 않는다(실제 SQL의 `d.version = v.version` 은 NULL과 맞지 않는다).
  5. 삽입: id가 None인 각 d를 이 process에 넣고 `d["id"]`, `d["version"] = 1`.
  6. `SaveResult(devices, updated=쓴 수, inserted=넣은 수, deleted=지운 수)`.

**ParameterRepository**
- 테이블·컬럼 이름은 `schema.TABLE_COLUMNS` 로 검사한다. 모르는 테이블이나 없는 컬럼이면 `KeyError`(실제 `_check`).
- `fetch_by_device(table_name, columns, device_id)`: 요청한 컬럼만 가진 dict 리스트, 넣은 순서. device가 없으면 `[]`.
- `replace_many_for_device(device_id, payload, *, expected_version=None, actor="", force=False) -> int`:
  - payload `{table: (columns, rows)}` 전체를 먼저 검사한다(KeyError면 아무것도 안 쓴다).
  - device가 없으면 **force여도** `StaleWriteError([Conflict(device_id, "", "deleted")])`.
  - `not force and expected_version is not None and 행 version != expected_version` 이면 `StaleWriteError([Conflict(device_id, 행 name, "stale", 행 updated_by, 행 updated_at)])`.
  - payload의 테이블마다 그 device의 행을 지우고 rows를 순서대로 넣는다. 값은 `r.get(c) or ""`, payload에 없는 그 테이블의 컬럼은 `""`. payload에 없는 테이블은 그대로다.
  - 내용이 같아도 device version+1, updated_at, updated_by=actor. 새 version을 돌려준다.

**IORepository**
- `import_data(input_path, *, actor)`: 파일이 없으면 `FileNotFoundError`. `pandas.read_csv(path, dtype=str, keep_default_na=False)`. 행마다 CdsLibName이 비었거나 NaN이면 그 행을 건너뛰고, 아니면 strip한 이름의 process를 찾거나 만든다. device를 새로 만든다(name = InstCellName 그대로, celltype = CellType, description `""`, order 0, version 1, updated_by = actor). 섹션 매칭(`tab_config` 이름 + 선택적 `.숫자`)과 셀 분해는 실제 `genviewer.service.repo.io.split_cell` 을 import해 쓰고, 탭 행은 실제와 같은 순서(tab_config 순서 × 매칭된 CSV 컬럼 순서 × split_cell 결과 순서)로 붙인다. 필수 컬럼이 없어 KeyError 등이 나면 아무것도 쓰지 않는다. 만든 device 수를 돌려준다.
- `fetch_export_data(device_info)`: 실제 함수의 두 패스를 그대로 옮긴다. `process_name` 이 빈 info는 건너뛴다. 헤더는 `["CellType", "CdsLibName", "InstCellName"]` 다음에 tab_config 순서로 탭 이름을 (그 탭의 device별 행 수 최댓값)번 반복한다. 행의 celltype·process·name은 **device_info의 값**이다(store 값이 아니다). 정렬은 `delegate_config["device"]["celltype"]["items"]` 순서(목록에 없으면 맨 뒤, 안정 정렬). 셀은 탭 행의 컬럼 값을 `" "` 로 이은 문자열, 없는 칸은 `""`.

**FakeDatabase / open_database**
- `open()`, `close()` 는 `closed` 를 바꾸고 기록한다. 여러 번 불러도 된다. `ping()` 은 `not closed` 를 돌려준다.
- `connection()` 은 `AssertionError("FakeDatabase 는 SQL 을 실행하지 않는다 …")`. 이유: 가짜로 바꾸지 않은 실제 repo(예: History 화면의 `AuditRepository`)가 섞이면 바로 드러나야 한다.
- 닫힌 FakeDatabase로 repo를 불러도 그대로 동작한다. 실제 `Database.connection()` 도 닫힌 풀을 다시 연다. 닫은 뒤의 호출은 `calls` 의 순서(`"db.close"` 뒤)로 확인한다.
- `store.open_database(dsn)`: `("open_database", {"dsn": dsn})` 를 기록하고 `fail_next` 를 따르며, `open()` 한 새 `FakeDatabase(store, dsn)` 을 돌려준다. step 2가 `DeviceTabController._open_database` 를 `staticmethod(store.open_database)` 로 바꾼다. 접속 실패는 `store.fail_next("open_database", DbUnavailableError("…"))` 로 만든다.

**시드·조작 헬퍼**
- `add_process`, `add_device`(복사본을 돌려준다), `set_rows`(그 device의 그 테이블 행을 통째로 바꾼다. 없는 컬럼은 `""`, 모르는 테이블·컬럼은 KeyError).
- `touch_device(device_id, *, actor="other", **changes)`: 다른 사용자의 저장 흉내. changes(name/celltype/description/order)를 쓰고 version+1, updated_at, updated_by=actor. 새 version을 돌려준다.
- `remove_device(device_id)`: 다른 사용자의 삭제 흉내(탭 행까지).
- `find_device(name)`: 그 이름의 첫 device(id 순) 복사본, 없으면 KeyError. `rows(table, device_id)`: 탭 행 복사본. `calls_of(method)`: 그 이름 호출들의 인자 dict 리스트.

### 3. contract test (`tests/gui/test_fake_repo_contract.py`, 새 파일)

```python
@pytest.fixture(params=["fake", "real"])
def backend(request):   # .process .device .parameter .io 를 가진 namespace
    ...                 # real: db = request.getfixturevalue("db")  (GENDB_TEST_PG_DSN 없으면 이 매개변수만 skip)
                        # fake: FakeDatabase(FakeStore()) 로 네 가짜 repo
```

각 테스트는 **기대값을 직접 적고** 두 backend가 모두 만족해야 한다. "남의 변경"은 같은 API를 다른 actor로 불러 만든다(`upsert_device(..., actor="kim")`). 시각은 값이 아니라 `isinstance(datetime)` 과 바뀌었는지만 본다.
- process: `get_or_create_id` 두 번이 같은 id, 빈 이름은 None, `add` 중복 False·새 이름 True, `list_all` 정렬, `exists`, `count_devices`, `delete` 가 device·탭 행까지 지우고 없는 이름도 True.
- `upsert_device`: 새 dict에 id와 version 1이 써지고 같은 객체가 돌아온다. `fetch_devices_by_process` 행의 키 집합, `updated_by == actor`. id가 있으면 값이 같아도 version+1. 사라진 id는 예외 없이 그대로.
- `fetch_devices_by_process`: order를 뒤집어 넣어 `(order, id)` 순서를 확인한다. 다른 process의 device는 보이지 않는다.
- `upsert_devices`: 손대지 않은 저장은 `updated == 0`, version·`etag_key` 그대로. 두 개 중 하나만 고치면 `updated == 1` 이고 그 dict만 version+1. id 없는 dict는 `inserted == 1` 에 id가 채워진다. `deleted={id: version}` 은 `deleted == 1` 이고 탭 행까지 사라진다. 화면 목록에 없는 남의 device는 남는다. 다른 process로 옮겨진 device(`upsert_device(다른 pid, 그 dict)`)는 `deleted` 로 지워지지 않는다(`deleted == 0`).
- stale: "kim"이 먼저 고친 device를 옛 version으로 저장하면 `StaleWriteError`, conflicts는 reason `"stale"`, updated_by `"kim"`, updated_at은 datetime 하나이고 행 값은 그대로다. `force=True` 면 내 값이 쓰이고 version+1.
- deleted: 남이 지운 device를 저장하거나 `deleted` 로 지우려 하면 reason `"deleted"`. `force=True` 면 예외 없이 `updated == deleted == 0` 이고 행이 다시 생기지 않는다.
- etag: 빈 process는 `n 0, vs 0, mx None, who None`. 쓰기 뒤에는 `etag_key` 가 바뀌고 `who` 는 마지막 actor다. 다른 process의 쓰기는 etag를 바꾸지 않는다.
- `replace_many_for_device`: 두 탭을 한 번에 쓰면 version은 한 번만 +1이고 돌려준 값이 fetch의 version과 같다. `fetch_by_device` 는 넣은 순서(알파벳 순이 아닌 순서로 넣는다)와 요청한 컬럼만 돌려준다. None과 빠진 값은 `""`. 같은 내용을 다시 써도 version+1. expected_version이 틀리면 stale이고 내용 그대로, force면 통과. device가 없으면 force여도 deleted. 모르는 테이블·컬럼은 KeyError이고 아무것도 쓰이지 않는다.
- `import_data`: 먼저 `get_or_create_id("sf2p")` 를 하고 `tmp_path` 에 UTF-8로 아래 CSV를 쓴다. 2를 돌려주고, process는 `["sf2p", "sf9x"]` 가 되고, nfet_c의 inst_terms는 `[{DRN, d}, {GATE, g}]`, inst_sch_params는 `[{"reserved_key": "LENGTH", "cds_inst_parameter_name": "1 2"}]`, pfet_z의 inst_terms는 `[{DRN, d}]` 이다. 없는 파일은 `FileNotFoundError`, CdsLibName 열이 없는 CSV는 `KeyError` 이고 device 수가 그대로다(`tests/test_csv_import.py` 의 `test_a_csv_without_the_required_columns_raises`).
  ```
  CellType,CdsLibName,InstCellName,InstTerm,InstTerm,InstSchParam
  PFET,sf9x,pfet_z,DRN d,,
  NFET,sf2p,nfet_c,DRN d,GATE g,LENGTH 1 2
  ```
- `fetch_export_data`: 위 두 device와 `process_name` 이 빈 info 하나를 넘기면 headers는 `["CellType", "CdsLibName", "InstCellName", "InstTerm", "InstTerm", "InstSchParam"]` 이고, rows는 celltype 우선순위(NFET이 PFET보다 앞)대로 `[["NFET", "sf2p", "nfet_c", "DRN d", "GATE g", "LENGTH 1 2"], ["PFET", "sf9x", "pfet_z", "DRN d", "", ""]]` 이다.

### 4. 가짜 전용 테스트 (`tests/gui/test_fake_store.py`, 새 파일)

- 시그니처: 네 쌍(가짜, 실제) 각각에서 가짜의 공개 메서드 집합이 위 목록과 같고, 메서드마다 `[(p.name, p.kind, p.default) for p in inspect.signature(...).parameters.values()]` 가 실제와 같다(주석은 비교하지 않는다).
- `fail_next`: 다음 한 번만, 쌓인 순서대로, store 불변, `calls` 에 남음, 모르는 이름은 ValueError.
- `calls` 의 인자는 호출 시점 복사본이다(`upsert_devices` 뒤 받은 dict에 id가 생겨도 기록된 인자에는 없다). 돌려준 행을 고쳐도 store는 그대로다.
- `FakeDatabase`: `connection()` 은 AssertionError, `open`/`close`/`ping` 기록과 `closed`, `cfg.dsn`(빈 dsn이면 `"fake"`), `user == cfg.app_user`. `open_database` 는 열린 FakeDatabase를 주고 `fail_next("open_database", …)` 를 따른다.
- 시드·조작: `touch_device` 가 version+1·updated_by를 쓰고 `etag_key` 를 바꾼다. `remove_device` 가 탭 행까지 지운다. 둘 다 `calls` 에 남지 않는다. `find_device` 없는 이름은 KeyError.

변이 검사: "값이 같으면 version을 올리지 않는다"(수정 4단계)를 망가뜨리면 contract test의 fake 쪽이 실패하는지, 삭제의 process_id 조건을 빼면 옮겨진 device 테스트가 실패하는지 확인하고 되돌린다. DB가 없어도 fake 쪽에서 보여야 한다.

### 5. 문서

- `CLAUDE.md` "테스트 관례"에 한 줄: GUI 테스트의 DB는 `tests/gui_support/fakes.py` 의 `FakeStore`/`Fake*Repository` 다. 의미는 실제 repo가 기준이고 `tests/gui/test_fake_repo_contract.py` 가 같은 기대값을 가짜와 실제 PostgreSQL(`GENDB_TEST_PG_DSN`)에 돌려 고정한다. `service/repo/` 의 의미를 바꾸는 step은 가짜와 contract test도 같이 고친다.
- `docs/ARCHITECTURE.md` 디렉토리 구조의 `gui_support/` 줄에 `fakes.py(FakeStore·FakeDatabase·Fake*Repository)` 를 더한다.

## Acceptance Criteria

```bash
uv run ruff check src tests                  # 린트 (import 정렬은 uv run ruff check --fix tests 로 고쳐도 된다)
uv run pytest tests/gui -q                   # contract(fake 쪽)·가짜 전용 테스트 통과, real 쪽은 DSN 없으면 skip
uv run pytest -q                             # 전체 통과
git status --porcelain -- src                # 출력이 비어 있어야 한다 (src 불변)
# GENDB_TEST_PG_DSN 이 있으면 real 쪽까지:
# GENDB_TEST_PG_DSN="postgresql://<user>@127.0.0.1:55433/postgres" uv run pytest tests/gui/test_fake_repo_contract.py -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다. `GENDB_TEST_PG_DSN` 이 설정돼 있으면 contract test를 real 쪽까지 돌린다. 이 step은 SQL을 바꾸지 않으므로 DSN이 없어도 `blocked` 가 아니다. 대신 real 쪽이 돌았는지 summary에 적는다.
2. 아키텍처 체크리스트를 확인한다:
   - `src/` 가 바뀌지 않았는가?
   - `fakes.py` 가 psycopg 커넥션이나 SQL을 쓰지 않는가(`TABLE_COLUMNS`, `split_cell`, `SaveResult`, `Conflict`, `StaleWriteError`, `DbConfig` 같은 순수 이름만 import)?
   - 모든 contract test가 기대값을 직접 적는가("fake 결과 == real 결과" 비교만 하는 테스트가 없는가)?
3. 결과에 따라 `phases/2-gui-test-infra/index.json` 의 step 1을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "tests/gui_support/fakes.py: FakeStore(calls/calls_of/fail_next/open_database, add_process/add_device/set_rows/touch_device/remove_device/find_device/rows), FakeDatabase, Fake{Process,Device,Parameter,IO}Repository(메서드 14개). contract test N개 × fake/real(real: <passed | skipped — DSN 없음>), 가짜 전용 M개. 관찰: <없음 또는 파일:행 — 관찰>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `src/` 를 고치지 마라. 실제 repo에서 이상한 동작(예: `upsert_device` 가 version 검사 없이 덮어쓴다)을 봐도 가짜는 **지금 동작을 그대로** 흉내 낸다. 이유: phase 3/4의 RED 테스트가 지금 코드의 버그를 드러내야 한다. 고쳐진 동작을 흉내 내면 RED가 사라진다. 관찰은 summary에 적는다.
- 가짜가 psycopg 커넥션, SQL, 실제 `Database` 를 쓰지 마라. 이유: 개발 PC에는 DB가 없고, GUI 테스트는 DB 없이 돌아야 한다.
- 실제 모듈의 순수 이름(`schema.TABLE_COLUMNS`, `split_cell`, `SaveResult`, `Conflict`, `StaleWriteError`, `etag_key`, `tab_config`, `delegate_config`)을 다시 정의하지 마라. import해서 쓴다. 이유: 같은 의미를 두 곳에 두면 어긋난다.
- contract test를 "fake 결과 == real 결과" 비교로만 쓰지 마라. 이유: DB가 없으면 real 쪽이 skip되어 아무것도 검사하지 않는다.
- 가짜가 store 안의 dict·list를 그대로 돌려주지 마라. 이유: `save_all` 이 받은 dict에 `order` 를 쓰는 등 컨트롤러가 받은 값을 고치므로, 저장하지 않은 편집이 "서버"에 들어간 것처럼 보인다.
- 가짜 repo 메서드에 실제에 없는 인자나 동작을 더하지 마라. 장애·남의 변경은 `FakeStore` 의 `fail_next`·조작 헬퍼로 만든다. 이유: 컨트롤러는 실제 시그니처로 부른다(시그니처 테스트가 지킨다).
- change_log(audit)를 흉내 내지 마라. 이유: 이 phase의 컨트롤러 fixture는 이력을 읽지 않는다(History 화면은 범위 밖). 범위만 커진다.
- DB가 없어 real 쪽이 skip된다고 그 매개변수를 지우거나 xfail로 바꾸지 마라.
- 기존 테스트를 깨뜨리지 마라.
