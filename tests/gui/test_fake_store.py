"""가짜 repo 자기 검사. contract test 가 다루지 않는 가짜만의 장치를 본다.

시그니처(컨트롤러는 실제 시그니처로 부른다), calls 기록, fail_next, FakeDatabase, 시드·조작 헬퍼.
"""

import copy
import inspect
import threading
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from gui_support.fakes import (
    CLOCK_START,
    REPO_METHODS,
    FakeDatabase,
    FakeDeviceRepository,
    FakeIORepository,
    FakeParameterRepository,
    FakeProcessRepository,
    FakeStore,
)

from genviewer.service.errors import DbUnavailableError
from genviewer.service.repo.device import DeviceRepository, etag_key
from genviewer.service.repo.io import IORepository
from genviewer.service.repo.parameter import ParameterRepository
from genviewer.service.repo.process import ProcessRepository

TERMS = ["reserved_key", "cds_inst_term_name"]

PAIRS = [
    (
        FakeProcessRepository,
        ProcessRepository,
        {"add", "delete", "exists", "list_all", "count_devices", "get_or_create_id"},
    ),
    (
        FakeDeviceRepository,
        DeviceRepository,
        {"fetch_devices_by_process", "etag", "upsert_device", "upsert_devices"},
    ),
    (FakeParameterRepository, ParameterRepository, {"fetch_by_device", "replace_many_for_device"}),
    (FakeIORepository, IORepository, {"import_data", "fetch_export_data"}),
]


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def repos(store):
    db = FakeDatabase(store)
    return SimpleNamespace(
        process=FakeProcessRepository(db),
        device=FakeDeviceRepository(db),
        parameter=FakeParameterRepository(db),
        io=FakeIORepository(db),
    )


def _public_methods(cls) -> set[str]:
    return {n for n, _ in inspect.getmembers(cls, inspect.isfunction) if not n.startswith("_")}


def _params(fn) -> list[tuple]:
    return [(p.name, p.kind, p.default) for p in inspect.signature(fn).parameters.values()]


def _terms(*pairs):
    return [{"reserved_key": k, "cds_inst_term_name": v} for k, v in pairs]


# -- 시그니처 ----------------------------------------------------------------


@pytest.mark.parametrize("fake,real,methods", PAIRS, ids=[f.__name__ for f, _, _ in PAIRS])
def test_a_fake_has_exactly_the_methods_the_controllers_call(fake, real, methods):
    assert _public_methods(fake) == methods
    assert methods <= _public_methods(real)


def test_repo_methods_lists_all_fourteen():
    union = set().union(*(methods for _, _, methods in PAIRS))
    assert len(REPO_METHODS) == len(set(REPO_METHODS)) == 14
    assert set(REPO_METHODS) == union


@pytest.mark.parametrize(
    "fake,real,method",
    [(f, r, m) for f, r, methods in PAIRS for m in ["__init__", *sorted(methods)]],
    ids=[f"{f.__name__}.{m}" for f, _, methods in PAIRS for m in ["__init__", *sorted(methods)]],
)
def test_a_fake_method_has_the_real_signature(fake, real, method):
    # 주석(타입)은 비교하지 않는다. 이름·종류·기본값만.
    assert _params(getattr(fake, method)) == _params(getattr(real, method))


# -- calls -----------------------------------------------------------------


def test_calls_record_the_bound_arguments_with_defaults(store, repos):
    pid = store.add_process("sf2p")

    repos.device.upsert_devices(pid, [])
    repos.parameter.fetch_by_device("inst_terms", ["reserved_key"], 7)
    repos.process.add("sf4u", actor="kim")

    assert store.calls == [
        (
            "upsert_devices",
            {"process_id": pid, "devices": [], "deleted": None, "actor": "", "force": False},
        ),
        (
            "fetch_by_device",
            {"table_name": "inst_terms", "columns": ["reserved_key"], "device_id": 7},
        ),
        ("add", {"name": "sf4u", "actor": "kim"}),
    ]
    assert store.calls_of("add") == [{"name": "sf4u", "actor": "kim"}]
    assert store.calls_of("delete") == []


def test_calls_keep_the_arguments_as_they_were_at_call_time(store, repos):
    pid = store.add_process("sf2p")
    new = {"name": "a", "celltype": "NFET"}

    repos.device.upsert_devices(pid, [new], actor="me")

    assert "id" in new  # 받은 dict 에는 id 가 써졌다
    (args,) = store.calls_of("upsert_devices")
    assert args["devices"] == [{"name": "a", "celltype": "NFET"}]
    assert args["devices"][0] is not new


def test_a_call_is_recorded_after_its_work_is_done(store, repos, monkeypatch):
    pid = store.add_process("sf2p")
    seen_during_work = []
    insert = store._insert_device

    def spy(*args):
        seen_during_work.append(list(store.calls))
        return insert(*args)

    monkeypatch.setattr(store, "_insert_device", spy)
    repos.device.upsert_device(pid, {"name": "a", "celltype": "NFET"})

    assert seen_during_work == [[]]
    assert [name for name, _ in store.calls] == ["upsert_device"]


def test_a_raising_call_is_recorded_too(store, repos):
    with pytest.raises(KeyError):
        repos.parameter.fetch_by_device("no_such_table", [], 1)
    assert store.calls_of("fetch_by_device") == [
        {"table_name": "no_such_table", "columns": [], "device_id": 1}
    ]


def test_returned_rows_are_copies(store, repos):
    pid = store.add_process("sf2p")
    dev = store.add_device(pid, "a", "NFET")
    store.set_rows("inst_terms", dev["id"], _terms(("DRN", "d")))
    before = copy.deepcopy((store.processes, store.devices, store.tab_rows))

    dev["name"] = "고침"
    repos.device.fetch_devices_by_process(pid)[0]["name"] = "고침"
    repos.parameter.fetch_by_device("inst_terms", TERMS, dev["id"])[0]["reserved_key"] = "X"
    repos.process.list_all().append("sf9x")
    store.find_device("a")["name"] = "고침"
    store.rows("inst_terms", dev["id"])[0]["reserved_key"] = "X"
    store.rows("inst_terms", dev["id"]).clear()

    assert (store.processes, store.devices, store.tab_rows) == before


def test_calls_from_worker_threads_are_serialized(store, repos):
    pid = store.add_process("sf2p")

    def work(i):
        repos.device.upsert_device(pid, {"name": f"d{i}", "celltype": "NFET"})

    threads = [threading.Thread(target=work, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(store.devices) == list(range(1, 9))
    assert len(store.calls_of("upsert_device")) == 8


# -- fail_next -------------------------------------------------------------


def test_fail_next_fails_only_the_next_call(store, repos):
    boom = RuntimeError("boom")
    store.fail_next("add", boom)

    with pytest.raises(RuntimeError) as excinfo:
        repos.process.add("sf2p")
    assert excinfo.value is boom
    assert store.processes == {}

    assert repos.process.add("sf2p") is True
    assert store.calls == [("add", {"name": "sf2p", "actor": ""})] * 2


def test_fail_next_queues_in_order_per_method(store, repos):
    first, second = RuntimeError("1"), DbUnavailableError("2")
    store.fail_next("list_all", first)
    store.fail_next("list_all", second)

    assert repos.process.exists("sf2p") is False  # 다른 이름은 영향이 없다
    with pytest.raises(RuntimeError) as a:
        repos.process.list_all()
    with pytest.raises(DbUnavailableError) as b:
        repos.process.list_all()
    assert (a.value, b.value) == (first, second)
    assert repos.process.list_all() == []
    assert len(store.calls_of("list_all")) == 3


def test_a_failed_write_leaves_the_store_and_the_given_dicts_alone(store, repos):
    pid = store.add_process("sf2p")
    dev = store.add_device(pid, "a", "NFET")
    gone = store.add_device(pid, "b", "NFET")
    store.set_rows("inst_terms", gone["id"], _terms(("DRN", "d")))
    before = copy.deepcopy((store.processes, store.devices, store.tab_rows))
    payload = [{**dev, "description": "바뀜"}, {"name": "c", "celltype": "NFET"}]

    store.fail_next("upsert_devices", RuntimeError("x"))
    with pytest.raises(RuntimeError):
        repos.device.upsert_devices(pid, payload, deleted={gone["id"]: 1})

    assert (store.processes, store.devices, store.tab_rows) == before
    assert payload == [{**dev, "description": "바뀜"}, {"name": "c", "celltype": "NFET"}]


def test_an_exception_midway_rolls_the_data_back(store, repos, tmp_path):
    """두 번째 행에서 KeyError 가 나도 첫 행이 만든 process·device 가 남지 않는다."""
    path = tmp_path / "bad.csv"
    # InstCellName 이 없다. process 를 만든 뒤 device 를 만들 때 KeyError 가 난다.
    path.write_text("CellType,CdsLibName\nNFET,sf2p\n", encoding="utf-8")

    with pytest.raises(KeyError):
        repos.io.import_data(str(path))

    assert (store.processes, store.devices) == ({}, {})


@pytest.mark.parametrize("name", ["get_id", "nope", "db.connection"])
def test_fail_next_rejects_an_unknown_name(store, name):
    with pytest.raises(ValueError):
        store.fail_next(name, RuntimeError())


# -- FakeDatabase / open_database ------------------------------------------


def test_fake_database_refuses_sql(store):
    db = FakeDatabase(store)
    with pytest.raises(AssertionError, match="SQL"):
        db.connection()
    with pytest.raises(AssertionError), db.connection():
        pass


def test_fake_database_open_close_ping_are_recorded(store):
    db = FakeDatabase(store)
    assert db.closed is True  # 실제처럼 만든 직후에는 닫혀 있다

    db.open()
    assert db.closed is False
    assert db.ping() is True
    db.close()
    db.close()  # 여러 번 불러도 된다
    assert db.closed is True
    assert db.ping() is False

    assert store.calls == [
        ("db.open", {}),
        ("db.ping", {}),
        ("db.close", {}),
        ("db.close", {}),
        ("db.ping", {}),
    ]


def test_fake_database_config(store, monkeypatch):
    monkeypatch.setenv("GENDB_APP_USER", "tester")
    db = FakeDatabase(store)
    assert db.store is store
    assert db.cfg.dsn == "fake"
    assert db.cfg.app_user == "tester"
    assert db.user == "tester"
    assert FakeDatabase(store, "host=x").cfg.dsn == "host=x"


def test_repos_still_work_on_a_closed_database(store):
    db = FakeDatabase(store)
    db.close()
    assert FakeProcessRepository(db).add("sf2p") is True
    assert [name for name, _ in store.calls] == ["db.close", "add"]


def test_open_database_gives_an_open_database(store):
    db = store.open_database("host=x")

    assert isinstance(db, FakeDatabase)
    assert db.store is store
    assert db.closed is False
    assert db.cfg.dsn == "host=x"
    assert store.calls_of("open_database") == [{"dsn": "host=x"}]
    assert store.calls_of("db.open") == [{}]


def test_open_database_follows_fail_next(store):
    store.fail_next("open_database", DbUnavailableError("x"))

    with pytest.raises(DbUnavailableError):
        store.open_database("")
    assert store.calls_of("open_database") == [{"dsn": ""}]
    assert store.calls_of("db.open") == []

    assert store.open_database("").closed is False


# -- 시드·조작 헬퍼 ------------------------------------------------------------


def test_seed_helpers_are_not_recorded_and_ignore_fail_next(store):
    for method in ("add", "upsert_device", "replace_many_for_device", "fetch_by_device"):
        store.fail_next(method, RuntimeError(method))

    pid = store.add_process("sf2p")
    dev = store.add_device(pid, "a", "NFET")
    store.set_rows("inst_terms", dev["id"], _terms(("DRN", "d")))
    store.touch_device(dev["id"])
    store.find_device("a")
    store.rows("inst_terms", dev["id"])
    store.remove_device(dev["id"])

    assert store.calls == []


def test_add_device_uses_the_defaults_and_its_own_id_sequence(store):
    store.add_process("sf2p")
    pid = store.add_process("sf4u")

    dev = store.add_device(pid, "a", "NFET")

    assert pid == 2
    assert dev["id"] == 1  # process 와 device 는 별개의 시퀀스다
    assert {k: v for k, v in dev.items() if k != "updated_at"} == {
        "id": 1,
        "process_id": pid,
        "name": "a",
        "celltype": "NFET",
        "description": "",
        "order": 0,
        "version": 1,
        "updated_by": "seed",
    }
    assert isinstance(dev["updated_at"], datetime)
    with pytest.raises(KeyError):
        store.add_device(99, "x", "NFET")
    with pytest.raises(ValueError):
        store.add_process("sf2p")


def test_deleted_ids_are_not_reused(store, repos):
    pid = store.add_process("sf2p")
    a = repos.device.upsert_device(pid, {"name": "a", "celltype": "NFET"})
    repos.device.upsert_devices(pid, [], deleted={a["id"]: 1})
    b = repos.device.upsert_device(pid, {"name": "b", "celltype": "NFET"})
    assert b["id"] > a["id"]

    repos.process.delete("sf2p")
    assert repos.process.get_or_create_id("sf2p") > pid


def test_the_clock_moves_one_second_per_write(store, repos):
    pid = store.add_process("sf2p")  # 첫 쓰기 = CLOCK_START
    result = repos.device.upsert_devices(
        pid, [{"name": "a", "celltype": "NFET"}, {"name": "b", "celltype": "NFET"}]
    )
    a, b = (store.devices[d["id"]] for d in result.devices)

    # 한 호출에서 쓴 행은 같은 시각이다 (실제 now() 는 트랜잭션 시작 시각)
    assert a["updated_at"] == b["updated_at"] == CLOCK_START + timedelta(seconds=1)
    assert a["updated_at"].tzinfo is not None

    repos.device.upsert_devices(pid, [])  # 아무것도 하지 않으면 시계도 그대로
    repos.device.fetch_devices_by_process(pid)  # 읽기는 시계를 움직이지 않는다
    store.touch_device(a["id"])
    assert store.devices[a["id"]]["updated_at"] == CLOCK_START + timedelta(seconds=2)


def test_touch_device_is_another_users_save(store, repos):
    pid = store.add_process("sf2p")
    dev = store.add_device(pid, "a", "NFET")
    before = repos.device.etag(pid)

    version = store.touch_device(dev["id"], actor="kim", description="kim 이 고침")

    assert version == 2
    row = store.find_device("a")
    assert (row["description"], row["version"], row["updated_by"]) == ("kim 이 고침", 2, "kim")
    assert row["updated_at"] != dev["updated_at"]
    after = repos.device.etag(pid)
    assert etag_key(after) != etag_key(before)
    assert after["who"] == "kim"

    assert store.touch_device(dev["id"]) == 3
    assert store.find_device("a")["updated_by"] == "other"
    with pytest.raises(ValueError):
        store.touch_device(dev["id"], version=9)
    with pytest.raises(KeyError):
        store.touch_device(999)


def test_remove_device_takes_its_tab_rows(store, repos):
    pid = store.add_process("sf2p")
    gone = store.add_device(pid, "a", "NFET")
    kept = store.add_device(pid, "b", "NFET")
    store.set_rows("inst_terms", gone["id"], _terms(("DRN", "d")))
    store.set_rows("inst_sch_params", gone["id"], [{"reserved_key": "LENGTH"}])
    store.set_rows("inst_terms", kept["id"], _terms(("GATE", "g")))
    before = repos.device.etag(pid)

    store.remove_device(gone["id"])

    assert gone["id"] not in store.devices
    assert all(gone["id"] not in by_device for by_device in store.tab_rows.values())
    assert store.rows("inst_terms", kept["id"]) == _terms(("GATE", "g"))
    assert etag_key(repos.device.etag(pid)) != etag_key(before)
    with pytest.raises(KeyError):
        store.remove_device(gone["id"])


def test_find_device_set_rows_and_rows(store):
    pid = store.add_process("sf2p")
    first = store.add_device(pid, "a", "NFET")
    store.add_device(pid, "a", "PFET")  # 이름은 중복될 수 있다

    assert store.find_device("a")["id"] == first["id"]
    with pytest.raises(KeyError):
        store.find_device("없음")

    store.set_rows("inst_terms", first["id"], [{"reserved_key": "DRN"}])
    assert store.rows("inst_terms", first["id"]) == _terms(("DRN", ""))
    store.set_rows("inst_terms", first["id"], [])
    assert store.rows("inst_terms", first["id"]) == []
    with pytest.raises(KeyError):
        store.set_rows("no_such_table", first["id"], [])
    with pytest.raises(KeyError):
        store.set_rows("inst_terms", first["id"], [{"no_such_column": "x"}])
    with pytest.raises(KeyError):
        store.set_rows("inst_terms", 999, [])
    with pytest.raises(KeyError):
        store.rows("no_such_table", first["id"])
