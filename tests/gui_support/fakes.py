"""DB 없이 도는 가짜 repo. GUI 테스트의 "서버" 다.

컨트롤러가 부르는 repo 메서드 15개를 실제(`genviewer.service.repo`)와 같은 시그니처·의미로
흉내 낸다. 의미의 기준은 실제 repo 이고, `tests/gui/test_fake_repo_contract.py` 가 같은
기대값을 가짜와 실제 PostgreSQL 양쪽에 돌려 고정한다. 실제의 이상한 동작(예: `upsert_device`
는 version 을 보지 않고 덮어쓴다)도 **고치지 않고 그대로** 흉내 낸다. 뒤 phase 의 RED 테스트가
지금 코드의 버그를 드러내야 하기 때문이다.

- 메서드 하나가 트랜잭션 하나다. `store.lock` 을 잡고 돌고(GUI 스레드와 `run_blocking`/`Task`
  워커 스레드가 함께 부른다), 예외를 내면 데이터(process·device·탭 행)를 되돌린다. id 시퀀스와
  시계는 PostgreSQL 처럼 되돌리지 않는다.
- 끝난 호출(정상 반환이든 예외든)은 `store.calls` 에 `(이름, 인자)` 로 남는다. 인자는 기본값을
  채운 호출 시점의 deep copy 다.
- 장애는 `store.fail_next(이름, 예외)`, 남의 변경은 `touch_device`/`remove_device` 로 만든다.
  `store.hold_next(이름)` 은 다음 호출 하나를 돌려준 Event 가 set 될 때까지 붙잡아 둔다(도는 중인
  `Task` 를 재현할 때). 가짜 repo 메서드에는 실제에 없는 인자를 더하지 않는다.
- change_log 는 읽기(`recent`)만 흉내 낸다. 줄은 `store.add_audit` 로 넣는다. 가짜 쓰기 메서드는
  이력을 남기지 않는다.

SQL 도, psycopg 커넥션도 쓰지 않는다. 실제 모듈에서는 순수한 이름만 가져다 쓴다.
"""

import copy
import functools
import inspect
import json
import re
import threading
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from genviewer.config.config import delegate_config, tab_config
from genviewer.service.config import DbConfig
from genviewer.service.errors import Conflict, StaleWriteError
from genviewer.service.repo.audit import Entry, _aware
from genviewer.service.repo.device import SaveResult
from genviewer.service.repo.io import split_cell
from genviewer.service.repo.parameter import _check
from genviewer.service.schema import TABLE_COLUMNS
from genviewer.utils.user import current_user

# 컨트롤러가 부르는 repo 메서드. 이름은 서로 겹치지 않으므로 calls 의 이름이 곧 메서드 이름이다.
REPO_METHODS: tuple[str, ...] = (
    # FakeProcessRepository
    "add",
    "delete",
    "exists",
    "list_all",
    "count_devices",
    "get_or_create_id",
    # FakeDeviceRepository
    "fetch_devices_by_process",
    "etag",
    "upsert_device",
    "upsert_devices",
    # FakeParameterRepository
    "fetch_by_device",
    "replace_many_for_device",
    # FakeIORepository
    "import_data",
    "fetch_export_data",
    # FakeAuditRepository
    "recent",
)
# fail_next 로 실패시킬 수 있고 hold_next 로 붙잡을 수 있는 이름.
FAILABLE: tuple[str, ...] = (*REPO_METHODS, "open_database")

# hold_next 로 붙잡은 호출이 이 시간(초) 안에 풀리지 않으면 AssertionError 를 낸다.
# 테스트가 Event 를 set 하지 않고 끝나도 워커 스레드(와 그것을 wait() 하는 정리)가 멈추지 않게.
HOLD_TIMEOUT = 10.0

# 쓰기 호출 하나가 시계를 1초씩 진행한다. 첫 쓰기가 이 시각이다.
CLOCK_START = datetime(2026, 10, 17, 9, 0, 0, tzinfo=UTC)

# touch_device 가 바꿀 수 있는 device 컬럼.
_TOUCHABLE = ("name", "celltype", "description", "order", "process_id")


def _text(value) -> str:
    """탭 행 값. 실제 `r.get(c) or ""` 와 같고, TEXT 컬럼이라 문자열로 남는다."""
    value = value or ""
    return value if isinstance(value, str) else str(value)


def _repo_store(repo) -> "FakeStore":
    return repo.db.store


def _recorded(
    name: str | None = None, *, store_of: Callable = _repo_store, failable: bool = True
):
    """호출을 store.lock 안에서 돌리고, 끝나면 store.calls 에 남긴다.

    failable 이면 hold_next·fail_next 를 따르고, 예외가 나면 데이터를 호출 전으로 되돌린다.
    hold_next 의 기다림은 store.lock 을 잡기 전이다.
    functools.wraps 가 __wrapped__ 를 남겨서 inspect.signature 는 원래 함수를 본다.
    """

    def decorate(fn):
        method = name or fn.__name__
        signature = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            bound = signature.bind(self, *args, **kwargs)
            bound.apply_defaults()
            arguments = dict(list(bound.arguments.items())[1:])  # self 를 뺀다
            # 호출 시점의 값이다. 메서드가 받은 dict 에 id 를 써 넣어도 기록은 그대로다.
            arguments = copy.deepcopy(arguments)
            store = store_of(self)
            if failable:
                store._wait_if_held(method)
            with store.lock:
                saved = store._snapshot() if failable else None
                try:
                    failure = store._take_failure(method) if failable else None
                    if failure is not None:
                        raise failure
                    return fn(self, *args, **kwargs)
                except BaseException:
                    if saved is not None:
                        store._restore(saved)
                    raise
                finally:
                    # 끝난 뒤에 남긴다. calls 를 보고 기다린 테스트가 반쯤 된 상태를 보지 않게.
                    store.calls.append((method, arguments))

        return wrapper

    return decorate


class FakeStore:
    """가짜 repo 들이 함께 쓰는 "서버" 상태.

    processes: id -> name
    devices:   id -> device 행 dict (키는 실제 `_SELECT_COLUMNS`)
    tab_rows:  table -> device_id -> 행 목록 (그 테이블의 모든 컬럼, 넣은 순서)
    audit:     change_log 줄 (키는 실제 `audit._COLUMNS`, id 순)
    calls:     (메서드 이름, 인자 dict). 끝난 호출만
    """

    def __init__(self) -> None:
        self.processes: dict[int, str] = {}
        self.devices: dict[int, dict] = {}
        self.tab_rows: dict[str, dict[int, list[dict]]] = {t: {} for t in TABLE_COLUMNS}
        self.audit: list[dict] = []
        self.calls: list[tuple[str, dict]] = []
        self.lock = threading.RLock()
        self._failures: dict[str, deque[BaseException]] = defaultdict(deque)
        self._holds: dict[str, deque[threading.Event]] = defaultdict(deque)
        # process·device·이력은 별개의 시퀀스다. 지운 id 는 다시 쓰지 않는다.
        self._next_process_id = 1
        self._next_device_id = 1
        self._next_audit_id = 1
        self._ticks = 0

    # -- 테스트가 쓰는 것 --------------------------------------------------

    def fail_next(self, method: str, exc: BaseException) -> None:
        """그 이름의 다음 호출 하나가 store 를 건드리지 않고 exc 를 낸다. 여러 번 부르면 쌓인다."""
        if method not in FAILABLE:
            raise ValueError(f"fail_next 로 실패시킬 수 없는 이름: {method!r} (가능: {FAILABLE})")
        with self.lock:
            self._failures[method].append(exc)

    def hold_next(self, method: str) -> threading.Event:
        """그 이름의 다음 호출 하나를 돌려준 Event 가 set 될 때까지 붙잡는다. 여러 번 부르면 쌓인다.

        잡힌 호출은 store.lock 을 잡기 전에 기다린다. 그동안 다른 호출(GUI 스레드의 것도)은 평소처럼
        돈다. 풀리면 평소처럼 돌고, fail_next 가 함께 걸려 있으면 그 실패를 낸다. `HOLD_TIMEOUT` 초
        안에 풀리지 않으면 calls 에 남기지 않고 AssertionError 를 낸다.
        """
        if method not in FAILABLE:
            raise ValueError(f"hold_next 로 붙잡을 수 없는 이름: {method!r} (가능: {FAILABLE})")
        event = threading.Event()
        with self.lock:
            self._holds[method].append(event)
        return event

    def calls_of(self, method: str) -> list[dict]:
        """그 이름 호출들의 인자 dict. 끝난 순서대로."""
        with self.lock:
            return [args for name, args in self.calls if name == method]

    @_recorded("open_database", store_of=lambda self: self)
    def open_database(self, dsn: str) -> "FakeDatabase":
        """`DeviceTabController._open_database` 자리. open() 한 새 FakeDatabase 를 준다."""
        db = FakeDatabase(self, dsn)
        db.open()
        return db

    # -- 시드·조작 (calls 에 남지 않고 fail_next 를 따르지 않는다) ------------

    def add_process(self, name: str) -> int:
        with self.lock:
            if self._process_id(name) is not None:
                raise ValueError(f"이미 있는 process: {name!r}")
            self._tick()
            return self._insert_process(name)

    def add_device(
        self,
        process_id: int,
        name: str,
        celltype: str,
        *,
        description: str = "",
        order: int = 0,
        updated_by: str = "seed",
    ) -> dict:
        """device 하나를 넣고 그 행의 복사본을 준다."""
        with self.lock:
            self._require_process(process_id)
            row = self._insert_device(
                process_id, name, celltype, description, order, updated_by, self._tick()
            )
            return dict(row)

    def set_rows(self, table: str, device_id: int, rows: list[dict]) -> None:
        """그 device 의 그 테이블 행을 통째로 바꾼다. 없는 컬럼은 ""."""
        _check(table, sorted({c for r in rows for c in r}))
        with self.lock:
            self._require_device(device_id)
            self._tick()
            self._put_rows(table, device_id, [self._full_row(table, r) for r in rows])

    def touch_device(self, device_id: int, *, actor: str = "other", **changes) -> int:
        """다른 사용자의 저장. changes 를 쓰고 version+1. 새 version 을 준다."""
        unknown = set(changes) - set(_TOUCHABLE)
        if unknown:
            raise ValueError(f"touch_device 가 바꿀 수 없는 컬럼: {sorted(unknown)}")
        with self.lock:
            row = self._require_device(device_id)
            if "process_id" in changes:
                self._require_process(changes["process_id"])
            row.update(changes)
            row["version"] += 1
            row["updated_at"] = self._tick()
            row["updated_by"] = actor
            return row["version"]

    def remove_device(self, device_id: int) -> None:
        """다른 사용자의 삭제. 탭 행까지 지운다."""
        with self.lock:
            self._require_device(device_id)
            self._tick()
            self._drop_device(device_id)

    def find_device(self, name: str) -> dict:
        """그 이름의 첫 device(id 순) 복사본."""
        with self.lock:
            for device_id in sorted(self.devices):
                if self.devices[device_id]["name"] == name:
                    return dict(self.devices[device_id])
        raise KeyError(f"device 가 없다: {name!r}")

    def rows(self, table: str, device_id: int) -> list[dict]:
        """탭 행 복사본(그 테이블의 모든 컬럼, 넣은 순서)."""
        _check(table, [])
        with self.lock:
            return [dict(r) for r in self.tab_rows[table].get(device_id, [])]

    def add_audit(self, actor: str, entry: Entry, *, source: str = "") -> dict:
        """이력 한 줄을 넣고 그 행의 복사본을 준다. 실제 `audit.write` 가 남기는 행과 같은 모양이다.

        at 은 store 시계다. detail 은 JSONB 처럼 JSON 으로 한 번 돌린다(튜플은 리스트, 키는 문자열).
        """
        with self.lock:
            row = {
                "id": self._next_audit_id,
                "at": self._tick(),
                "actor": actor,
                "source": source,
                "action": entry.action,
                "process_name": entry.process_name,
                "device_name": entry.device_name,
                "device_id": entry.device_id,
                "table_name": entry.table_name,
                "summary": entry.summary,
                "detail": json.loads(json.dumps(entry.detail)),
            }
            self._next_audit_id += 1
            self.audit.append(row)
            return copy.deepcopy(row)

    # -- 가짜 repo 가 쓰는 내부 --------------------------------------------

    def _take_failure(self, method: str) -> BaseException | None:
        queue = self._failures.get(method)
        return queue.popleft() if queue else None

    def _wait_if_held(self, method: str) -> None:
        """hold_next 가 걸려 있으면 풀릴 때까지 기다린다. store.lock 을 잡은 채 기다리지 않는다."""
        with self.lock:
            queue = self._holds.get(method)
            event = queue.popleft() if queue else None
        if event is not None and not event.wait(HOLD_TIMEOUT):
            raise AssertionError(f"hold_next({method}) 가 풀리지 않았다")

    def _snapshot(self) -> tuple:
        return copy.deepcopy((self.processes, self.devices, self.tab_rows))

    def _restore(self, saved: tuple) -> None:
        # 테스트가 store.devices 등을 잡고 있어도 같은 객체가 되돌아가도록 제자리에서 바꾼다.
        current_state = (self.processes, self.devices, self.tab_rows)
        for current, before in zip(current_state, saved, strict=True):
            current.clear()
            current.update(before)

    def _tick(self) -> datetime:
        """쓰기 호출 하나에 한 번. 한 호출에서 쓴 행은 같은 시각을 갖는다(실제 now())."""
        now = CLOCK_START + timedelta(seconds=self._ticks)
        self._ticks += 1
        return now

    def _process_id(self, name: str) -> int | None:
        for process_id, process_name in self.processes.items():
            if process_name == name:
                return process_id
        return None

    def _require_process(self, process_id: int) -> None:
        if process_id not in self.processes:
            raise KeyError(f"process 가 없다: id={process_id}")

    def _require_device(self, device_id: int) -> dict:
        row = self.devices.get(device_id)
        if row is None:
            raise KeyError(f"device 가 없다: id={device_id}")
        return row

    def _insert_process(self, name: str) -> int:
        process_id = self._next_process_id
        self._next_process_id += 1
        self.processes[process_id] = name
        return process_id

    def _insert_device(self, process_id, name, celltype, description, order, actor, now) -> dict:
        device_id = self._next_device_id
        self._next_device_id += 1
        row = {
            "id": device_id,
            "process_id": process_id,
            "name": name,
            "celltype": celltype,
            "description": description,
            "order": order,
            "version": 1,
            "updated_at": now,
            "updated_by": actor,
        }
        self.devices[device_id] = row
        return row

    def _drop_device(self, device_id: int) -> None:
        """ON DELETE CASCADE: 탭 행도 사라진다."""
        del self.devices[device_id]
        for by_device in self.tab_rows.values():
            by_device.pop(device_id, None)

    def _drop_process(self, process_id: int) -> None:
        for device_id in [i for i, d in self.devices.items() if d["process_id"] == process_id]:
            self._drop_device(device_id)
        del self.processes[process_id]

    def _devices_of(self, process_id: int) -> list[dict]:
        """ORDER BY "order", id."""
        found = [d for d in self.devices.values() if d["process_id"] == process_id]
        return sorted(found, key=lambda d: (d["order"], d["id"]))

    @staticmethod
    def _full_row(table: str, row: dict, columns: list[str] | None = None) -> dict:
        """그 테이블의 모든 컬럼을 가진 행. columns 밖의 컬럼은 DEFAULT ''."""
        given = list(row) if columns is None else columns
        return {c: _text(row.get(c)) if c in given else "" for c in TABLE_COLUMNS[table]}

    def _put_rows(self, table: str, device_id: int, rows: list[dict]) -> None:
        if rows:
            self.tab_rows[table][device_id] = rows
        else:
            self.tab_rows[table].pop(device_id, None)


class FakeDatabase:
    """`service.pool.Database` 자리. SQL 을 실행하지 않는다.

    실제처럼 만들어진 직후에는 닫혀 있다(`open=False`). 닫힌 채로 repo 를 불러도 동작한다.
    실제 `connection()` 도 닫힌 풀을 다시 연다. 닫은 뒤의 호출은 calls 의 순서로 확인한다.
    """

    def __init__(self, store: FakeStore, dsn: str = "") -> None:
        self.store = store
        self.cfg = DbConfig(dsn=dsn or "fake", app_user=current_user())
        self.closed = True
        self.close_count = 0  # close() 가 불린 횟수. calls 의 "db.close" 는 어느 DB 인지 모른다

    @property
    def user(self) -> str:
        return self.cfg.app_user

    @_recorded("db.open", store_of=lambda self: self.store, failable=False)
    def open(self) -> None:
        self.closed = False

    @_recorded("db.close", store_of=lambda self: self.store, failable=False)
    def close(self) -> None:
        self.closed = True
        self.close_count += 1

    @_recorded("db.ping", store_of=lambda self: self.store, failable=False)
    def ping(self) -> bool:
        return not self.closed

    def connection(self):
        # 가짜로 바꾸지 않은 실제 repo(예: History 의 AuditRepository)가 섞이면 바로 드러나게.
        raise AssertionError(
            "FakeDatabase 는 SQL 을 실행하지 않는다. 실제 repo 가 가짜 DB 에 붙었다"
            " (tests/gui_support/fakes.py 의 Fake*Repository 로 바꿀 것)"
        )


class FakeProcessRepository:
    def __init__(self, db: FakeDatabase) -> None:
        self.db = db

    @_recorded()
    def add(self, name: str, *, actor: str = "") -> bool:
        store = self.db.store
        if store._process_id(name) is not None:
            return False  # 실제는 UniqueViolation 을 잡는다
        store._tick()
        store._insert_process(name)
        return True

    @_recorded()
    def delete(self, name: str, *, actor: str = "") -> bool:
        store = self.db.store
        process_id = store._process_id(name)
        if process_id is None:
            return True  # 예전 계약: 없는 것을 지워도 참이다
        store._tick()
        store._drop_process(process_id)
        return True

    @_recorded()
    def exists(self, name: str) -> bool:
        return self.db.store._process_id(name) is not None

    @_recorded()
    def list_all(self) -> list[str]:
        return sorted(self.db.store.processes.values())

    @_recorded()
    def count_devices(self, name: str) -> int:
        store = self.db.store
        process_id = store._process_id(name)
        if process_id is None:
            return 0
        return len(store._devices_of(process_id))

    @_recorded()
    def get_or_create_id(self, name: str, *, actor: str = "") -> int | None:
        if not name:
            return None
        store = self.db.store
        store._tick()
        process_id = store._process_id(name)
        return process_id if process_id is not None else store._insert_process(name)


class FakeDeviceRepository:
    def __init__(self, db: FakeDatabase) -> None:
        self.db = db

    @_recorded()
    def fetch_devices_by_process(self, process_id: int) -> list[dict]:
        return [dict(d) for d in self.db.store._devices_of(process_id)]

    @_recorded()
    def etag(self, process_id: int) -> dict:
        devices = self.db.store._devices_of(process_id)
        if not devices:
            return {"n": 0, "mx": None, "vs": 0, "who": None}
        last = max(devices, key=lambda d: (d["updated_at"], d["id"]))
        return {
            "n": len(devices),
            "mx": max(d["updated_at"] for d in devices),
            "vs": sum(d["version"] for d in devices),
            "who": last["updated_by"],
        }

    @_recorded()
    def upsert_device(self, process_id: int, device: dict, *, actor: str = "") -> dict:
        store = self.db.store
        if device.get("id") is None:
            row = store._insert_device(
                process_id,
                device.get("name"),
                device.get("celltype"),
                device.get("description") or "",
                device.get("order", 0),
                actor,
                store._tick(),
            )
            device["id"] = row["id"]
            device["version"] = row["version"]
            return device

        row = store.devices.get(device["id"])
        if row is None:
            # 남이 먼저 지웠다. 실제 UPDATE 도 아무 행을 못 맞추고 예외 없이 끝난다.
            return device
        # 실제와 같다: version 을 보지 않고, 값이 같아도 version 을 올린다.
        row.update(
            process_id=process_id,
            name=device.get("name"),
            celltype=device.get("celltype"),
            description=device.get("description") or "",
            order=device.get("order", 0),
            version=row["version"] + 1,
            updated_at=store._tick(),
            updated_by=actor,
        )
        device["version"] = row["version"]
        return device

    @_recorded()
    def upsert_devices(
        self,
        process_id: int,
        devices: list[dict],
        *,
        deleted: dict[int, int] | None = None,
        actor: str = "",
        force: bool = False,
    ) -> SaveResult:
        deleted = deleted or {}
        if not devices and not deleted:
            return SaveResult(devices)

        store = self.db.store
        # 행은 process 와 상관없이 id 로 찾는다(실제 WHERE id = ANY(...)).
        if not force:
            conflicts = self._preflight(store, devices, deleted)
            if conflicts:
                raise StaleWriteError(conflicts)

        now = store._tick()

        # 그 사이 다른 process 로 옮겨진 device 는 지우지 않는다.
        removed = 0
        for device_id in sorted(deleted):
            row = store.devices.get(device_id)
            if row is not None and row["process_id"] == process_id:
                store._drop_device(device_id)
                removed += 1

        updated = 0
        for d in devices:
            if d.get("id") is None:
                continue
            row = store.devices.get(d["id"])
            if row is None:
                continue
            # force 가 아니면 version 이 같아야 맞는다. d 의 version 이 None 이면 맞지 않는다
            # (실제 SQL 의 d.version = v.version 은 NULL 과 같지 않다).
            if not force and row["version"] != d.get("version"):
                continue
            new = (d.get("name"), d.get("celltype"), d.get("description") or "", d.get("order", 0))
            if (row["name"], row["celltype"], row["description"], row["order"]) == new:
                continue  # IS DISTINCT FROM 가드: 값이 같으면 쓰지 않는다
            row["name"], row["celltype"], row["description"], row["order"] = new
            row["version"] += 1
            row["updated_at"] = now
            row["updated_by"] = actor
            d["version"] = row["version"]
            updated += 1

        inserted = 0
        for d in devices:
            if d.get("id") is not None:
                continue
            row = store._insert_device(
                process_id,
                d.get("name"),
                d.get("celltype"),
                d.get("description") or "",
                d.get("order", 0),
                actor,
                now,
            )
            d["id"] = row["id"]
            d["version"] = row["version"]
            inserted += 1

        return SaveResult(devices, updated=updated, inserted=inserted, deleted=removed)

    @staticmethod
    def _preflight(store: FakeStore, devices: list[dict], deleted: dict[int, int]) -> list:
        """실제 DeviceRepository._preflight 와 같은 순서: devices, 그다음 deleted."""
        conflicts: list[Conflict] = []

        def check(device_id: int, expected, name: str) -> None:
            row = store.devices.get(device_id)
            if row is None:
                conflicts.append(Conflict(device_id, name, "deleted"))
            elif expected is not None and row["version"] != expected:
                conflicts.append(
                    Conflict(device_id, row["name"], "stale", row["updated_by"], row["updated_at"])
                )

        for d in devices:
            if d.get("id") is not None:
                check(d["id"], d.get("version"), d.get("name", ""))
        for device_id, version in deleted.items():
            check(device_id, version, "")
        return conflicts


class FakeParameterRepository:
    def __init__(self, db: FakeDatabase) -> None:
        self.db = db

    @_recorded()
    def fetch_by_device(self, table_name: str, columns: list[str], device_id: int) -> list[dict]:
        _check(table_name, columns)
        rows = self.db.store.tab_rows[table_name].get(device_id, [])
        return [{c: r[c] for c in columns} for r in rows]

    @_recorded()
    def replace_many_for_device(
        self,
        device_id: int,
        payload: dict[str, tuple[list[str], list[dict]]],
        *,
        expected_version: int | None = None,
        actor: str = "",
        force: bool = False,
    ) -> int:
        for table, (columns, _) in payload.items():
            _check(table, columns)

        store = self.db.store
        row = store.devices.get(device_id)
        if row is None:
            # force 여도 그렇다. 실제는 잠글 행이 없으면 바로 낸다.
            raise StaleWriteError([Conflict(device_id, "", "deleted")])
        if not force and expected_version is not None and row["version"] != expected_version:
            raise StaleWriteError(
                [Conflict(device_id, row["name"], "stale", row["updated_by"], row["updated_at"])]
            )

        for table, (columns, rows) in payload.items():
            store._put_rows(table, device_id, [store._full_row(table, r, columns) for r in rows])

        # 내용이 같아도 올린다(그래야 다른 화면이 다시 읽는다).
        row["version"] += 1
        row["updated_at"] = store._tick()
        row["updated_by"] = actor
        return row["version"]


class FakeIORepository:
    def __init__(self, db: FakeDatabase) -> None:
        self.db = db

    @_recorded()
    def import_data(self, input_path: str, *, actor: str = "") -> int:
        data_path = Path(input_path)
        if not data_path.is_file():
            raise FileNotFoundError(f"CSV 파일이 없다: {data_path}")

        df = pd.read_csv(data_path, dtype=str, keep_default_na=False)

        # 실제와 같은 섹션 매칭: tab_config 이름 + 선택적 ".숫자" (pandas 가 반복 헤더에 붙인다).
        sections = []
        for section_name, section_info in tab_config.items():
            matched = [
                col
                for col in df.columns
                if re.fullmatch(rf"{re.escape(section_name)}(?:\.\d+)?", col)
            ]
            if matched:
                sections.append((section_info, matched))

        # 실제와 같다: 정확히 "Description" 인 컬럼만 본다. 없으면 빈 값.
        has_description = "Description" in df.columns

        store = self.db.store
        now = store._tick()
        created = 0
        for _, row in df.iterrows():
            process_name = row["CdsLibName"]
            if process_name is None or pd.isna(process_name) or not str(process_name).strip():
                continue
            process_name = str(process_name).strip()
            process_id = store._process_id(process_name)
            if process_id is None:
                process_id = store._insert_process(process_name)

            description = row["Description"] if has_description else ""
            device = store._insert_device(
                process_id, row["InstCellName"], row["CellType"], description, 0, actor, now
            )
            created += 1

            for section_info, matched in sections:
                table = section_info["table"]
                columns = section_info["columns"]
                parse = section_info.get("parse", "parseString")
                row_per_token = section_info.get("row_per_token", False)
                for col in matched:
                    cell = str(row[col]).strip()
                    if not cell:
                        continue
                    for values in split_cell(cell, len(columns), parse, row_per_token):
                        store.tab_rows[table].setdefault(device["id"], []).append(
                            dict(zip(columns, values, strict=True))
                        )
        return created

    @_recorded()
    def fetch_export_data(
        self, device_info: list[dict[str, str]]
    ) -> tuple[list[str], list[list[str]]]:
        store = self.db.store
        tab_names = list(tab_config.keys())
        tab_max_columns: dict[str, int] = {tab: 0 for tab in tab_names}
        tab_data_per_device: dict[int, dict[str, list[list[str]]]] = {}

        # Pass 1: 탭 행을 읽고 탭마다 최대 행 수를 센다.
        for info in device_info:
            device_id = info["id"]
            if not info.get("process_name"):
                continue

            tab_data_per_device[device_id] = {}

            for tab in tab_names:
                config = tab_config.get(tab)
                if not config:
                    continue

                table = config.get("table")
                columns = config.get("columns", [])
                if not table:
                    continue

                data = store.tab_rows[table].get(device_id, [])
                formatted_rows = [
                    ["" if r[c] is None else str(r[c]) for c in columns] for r in data
                ]
                tab_data_per_device[device_id][tab] = formatted_rows
                tab_max_columns[tab] = max(tab_max_columns[tab], len(formatted_rows))

        headers = ["CellType", "CdsLibName", "InstCellName", "Description"]
        for tab in tab_names:
            for _ in range(1, tab_max_columns[tab] + 1):
                headers.append(tab)

        celltype_priority = (
            delegate_config.get("device", {}).get("celltype", {}).get("items", [])
        )
        priority_map = {celltype: idx for idx, celltype in enumerate(celltype_priority)}
        device_info_sorted = sorted(
            device_info,
            key=lambda x: priority_map.get(x.get("celltype", "UNKNOWN"), float("inf")),
        )

        # Pass 2: 행을 만든다. celltype·process·name·description 은 device_info 의 값이다.
        rows: list[list[str]] = []
        for info in device_info_sorted:
            device_id = info["id"]
            process_name = info.get("process_name") or ""
            if not process_name:
                continue
            celltype = info.get("celltype") or ""
            device_name = info.get("name") or ""
            description = info.get("description") or ""

            row = [celltype, process_name, device_name, description]

            for tab in tab_names:
                tab_rows = tab_data_per_device.get(device_id, {}).get(tab, [])
                for i in range(tab_max_columns[tab]):
                    if i < len(tab_rows):
                        row.append(" ".join(tab_rows[i]))
                    else:
                        row.append("")

            rows.append(row)

        return headers, rows


def _ilike(pattern: str) -> re.Pattern:
    """ILIKE 패턴을 정규식으로. `%` 는 아무 글자열, `_` 는 한 글자, `\\` 는 다음 글자 그대로."""
    out = []
    chars = iter(pattern)
    for c in chars:
        if c == "\\":
            out.append(re.escape(next(chars, "")))
        elif c == "%":
            out.append(".*")
        elif c == "_":
            out.append(".")
        else:
            out.append(re.escape(c))
    return re.compile("".join(out), re.IGNORECASE | re.DOTALL)


class FakeAuditRepository:
    def __init__(self, db: FakeDatabase) -> None:
        self.db = db

    @_recorded()
    def recent(
        self,
        *,
        limit: int = 50,
        since: datetime | None = None,
        until: datetime | None = None,
        actor: str = "",
        process: str = "",
        device: str = "",
        contains: str = "",
        after_id: int | None = None,
    ) -> list[dict]:
        """조건에 맞는 줄 중 id 가 큰 쪽에서 limit 개를 id 오름차순으로 준다.

        naive since/until 은 실제처럼 이 PC 의 로컬 시각이다(`audit._aware`). contains 는 실제
        `summary ILIKE '%…%' OR detail::text ILIKE '%…%'` 다. detail 의 글자는 JSONB 출력처럼
        한글을 그대로 둔다(키 순서는 JSONB 와 다를 수 있다).
        """
        match = _ilike(f"%{contains}%") if contains else None
        found = []
        for row in self.db.store.audit:
            if after_id is not None and not row["id"] > after_id:
                continue
            if since is not None and not row["at"] >= _aware(since):
                continue
            if until is not None and not row["at"] < _aware(until):
                continue
            if actor and row["actor"] != actor:
                continue
            if process and row["process_name"] != process:
                continue
            if device and row["device_name"] != device:
                continue
            if match is not None and not (
                match.fullmatch(row["summary"])
                or match.fullmatch(json.dumps(row["detail"], ensure_ascii=False))
            ):
                continue
            found.append(row)
        # ORDER BY id DESC LIMIT n, 그다음 ORDER BY id
        newest = sorted(found, key=lambda r: r["id"], reverse=True)[:limit]
        return copy.deepcopy(sorted(newest, key=lambda r: r["id"]))

