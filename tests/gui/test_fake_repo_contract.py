"""가짜 repo(tests/gui_support/fakes.py)가 실제 repo 와 같은 의미인지 고정한다.

테스트마다 기대값을 직접 적고, 가짜와 실제 PostgreSQL 이 둘 다 그것을 만족해야 한다.
"fake 결과 == real 결과" 비교만 하는 테스트는 두지 않는다. DB 가 없으면 real 쪽이 skip 되어
아무것도 검사하지 않기 때문이다. real 쪽은 GENDB_TEST_PG_DSN 이 있을 때만 돈다
(tests/conftest.py 의 db fixture).

"남의 변경" 은 같은 API 를 다른 actor 로 불러 만든다. 시각은 값이 아니라 datetime 인지와
바뀌었는지만 본다. 이력의 시간 경계는 돌려받은 줄의 at 으로 만든다(실제는 서버 now(), 가짜는
store 시계라 벽시계로 만들 수 없다).
"""

from datetime import datetime
from types import SimpleNamespace

import pytest
from gui_support.fakes import (
    FakeAuditRepository,
    FakeDatabase,
    FakeDeviceRepository,
    FakeIORepository,
    FakeParameterRepository,
    FakeProcessRepository,
    FakeStore,
)

from genviewer.service.errors import Conflict, StaleWriteError
from genviewer.service.repo import audit
from genviewer.service.repo.audit import AuditRepository
from genviewer.service.repo.device import DeviceRepository, etag_key
from genviewer.service.repo.io import IORepository
from genviewer.service.repo.parameter import ParameterRepository
from genviewer.service.repo.process import ProcessRepository
from genviewer.utils.exporter import write_csv

DEVICE_KEYS = {
    "id",
    "process_id",
    "name",
    "celltype",
    "description",
    "order",
    "version",
    "updated_at",
    "updated_by",
}
TERMS = ["reserved_key", "cds_inst_term_name"]
PARAMS = ["reserved_key", "cds_inst_parameter_name"]


@pytest.fixture(params=["fake", "real"])
def backend(request):
    """.process .device .parameter .io .audit 와 이력 시드 .log(actor, entry) 를 가진 namespace.

    real 은 GENDB_TEST_PG_DSN 이 없으면 이 매개변수만 skip 된다.
    """
    if request.param == "real":
        db = request.getfixturevalue("db")
        # audit.write 는 모듈 전역 출처를 쓴다. 앞 테스트(cli.main 은 "cli")가 정한 값이 새지 않게.
        request.getfixturevalue("monkeypatch").setattr(audit, "_source", "")

        def log(actor: str, entry: audit.Entry) -> None:
            with db.connection() as conn:
                audit.write(conn.cursor(), actor, [entry])

        return SimpleNamespace(
            process=ProcessRepository(db),
            device=DeviceRepository(db),
            parameter=ParameterRepository(db),
            io=IORepository(db),
            audit=AuditRepository(db),
            log=log,
        )
    store = FakeStore()
    db = FakeDatabase(store)

    def log(actor: str, entry: audit.Entry) -> None:
        store.add_audit(actor, entry)

    return SimpleNamespace(
        process=FakeProcessRepository(db),
        device=FakeDeviceRepository(db),
        parameter=FakeParameterRepository(db),
        io=FakeIORepository(db),
        audit=FakeAuditRepository(db),
        log=log,
    )


def _device(name, celltype="NFET", **kw):
    return {"name": name, "celltype": celltype, "description": "", "order": 0, **kw}


def _terms(*pairs):
    return [{"reserved_key": k, "cds_inst_term_name": v} for k, v in pairs]


def _names(backend, process_id):
    return [d["name"] for d in backend.device.fetch_devices_by_process(process_id)]


def _row(backend, process_id, device_id):
    rows = backend.device.fetch_devices_by_process(process_id)
    (row,) = [d for d in rows if d["id"] == device_id]
    return row


# -- process ---------------------------------------------------------------


def test_get_or_create_id_is_stable_and_none_for_an_empty_name(backend):
    pid = backend.process.get_or_create_id("sf2p")
    assert isinstance(pid, int)
    assert backend.process.get_or_create_id("sf2p") == pid
    assert backend.process.get_or_create_id("") is None
    assert backend.process.list_all() == ["sf2p"]


def test_add_creates_only_a_new_name(backend):
    assert backend.process.add("sf2p") is True
    assert backend.process.add("sf2p") is False
    assert backend.process.add("sf4u", actor="kim") is True
    assert backend.process.list_all() == ["sf2p", "sf4u"]


def test_list_all_is_sorted_by_name(backend):
    for name in ("sf9x", "sf2p", "sf4u"):
        backend.process.add(name)
    assert backend.process.list_all() == ["sf2p", "sf4u", "sf9x"]


def test_exists_and_count_devices(backend):
    pid = backend.process.get_or_create_id("sf2p")
    backend.process.get_or_create_id("sf4u")
    for name in ("a", "b"):
        backend.device.upsert_device(pid, _device(name))

    assert backend.process.exists("sf2p") is True
    assert backend.process.exists("sf9x") is False
    assert backend.process.count_devices("sf2p") == 2
    assert backend.process.count_devices("sf4u") == 0
    assert backend.process.count_devices("sf9x") == 0


def test_delete_takes_the_devices_and_tab_rows_with_it(backend):
    pid = backend.process.get_or_create_id("sf2p")
    other = backend.process.get_or_create_id("sf4u")
    gone = backend.device.upsert_device(pid, _device("a"))
    kept = backend.device.upsert_device(other, _device("b"))
    backend.parameter.replace_many_for_device(
        gone["id"], {"inst_terms": (TERMS, _terms(("DRN", "d")))}
    )
    backend.parameter.replace_many_for_device(
        kept["id"], {"inst_terms": (TERMS, _terms(("GATE", "g")))}
    )

    assert backend.process.delete("sf2p", actor="kim") is True
    assert backend.process.list_all() == ["sf4u"]
    assert backend.device.fetch_devices_by_process(pid) == []
    assert backend.parameter.fetch_by_device("inst_terms", TERMS, gone["id"]) == []
    assert backend.parameter.fetch_by_device("inst_terms", TERMS, kept["id"]) == _terms(
        ("GATE", "g")
    )
    # 없는 이름을 지워도 참이다
    assert backend.process.delete("sf9x") is True


# -- upsert_device / fetch_devices_by_process ------------------------------


def test_upsert_device_inserts_and_fills_the_given_dict(backend):
    pid = backend.process.get_or_create_id("sf2p")
    new = {"name": "nfet_a", "celltype": "NFET"}  # description·order 가 없으면 기본값

    out = backend.device.upsert_device(pid, new, actor="me")

    assert out is new
    assert isinstance(new["id"], int)
    assert new["version"] == 1
    (row,) = backend.device.fetch_devices_by_process(pid)
    assert set(row) == DEVICE_KEYS
    assert {k: v for k, v in row.items() if k != "updated_at"} == {
        "id": new["id"],
        "process_id": pid,
        "name": "nfet_a",
        "celltype": "NFET",
        "description": "",
        "order": 0,
        "version": 1,
        "updated_by": "me",
    }
    assert isinstance(row["updated_at"], datetime)


def test_upsert_device_with_an_id_bumps_the_version_even_when_nothing_changed(backend):
    pid = backend.process.get_or_create_id("sf2p")
    dev = backend.device.upsert_device(pid, _device("a"), actor="me")
    before = _row(backend, pid, dev["id"])

    again = dict(dev)
    out = backend.device.upsert_device(pid, again, actor="kim")

    assert out is again
    assert again["version"] == 2
    row = _row(backend, pid, dev["id"])
    assert (row["name"], row["version"], row["updated_by"]) == ("a", 2, "kim")
    assert row["updated_at"] != before["updated_at"]


def test_upsert_device_for_a_vanished_id_changes_nothing(backend):
    pid = backend.process.get_or_create_id("sf2p")
    dev = backend.device.upsert_device(pid, _device("a"))
    backend.device.upsert_devices(pid, [], deleted={dev["id"]: 1}, actor="kim")

    mine = {**dev, "description": "내 것"}
    expected = dict(mine)
    out = backend.device.upsert_device(pid, mine, actor="me")

    assert out is mine
    assert mine == expected
    assert backend.device.fetch_devices_by_process(pid) == []


def test_devices_come_back_by_order_then_id_and_only_for_that_process(backend):
    pid = backend.process.get_or_create_id("sf2p")
    other = backend.process.get_or_create_id("sf4u")
    for name, order in [("a", 2), ("b", 1), ("c", 1), ("d", 0)]:
        backend.device.upsert_device(pid, _device(name, order=order))
    backend.device.upsert_device(other, _device("x"))

    assert _names(backend, pid) == ["d", "b", "c", "a"]
    assert _names(backend, other) == ["x"]


# -- upsert_devices --------------------------------------------------------


def test_an_untouched_save_writes_nothing(backend):
    pid = backend.process.get_or_create_id("sf2p")
    first = backend.device.upsert_devices(pid, [_device("a"), _device("b")], actor="me")
    assert (first.updated, first.inserted, first.deleted) == (0, 2, 0)
    before = backend.device.etag(pid)

    view = backend.device.fetch_devices_by_process(pid)
    result = backend.device.upsert_devices(pid, [dict(d) for d in view], actor="me")

    assert (result.updated, result.inserted, result.deleted) == (0, 0, 0)
    assert [d["version"] for d in backend.device.fetch_devices_by_process(pid)] == [1, 1]
    assert etag_key(backend.device.etag(pid)) == etag_key(before)


def test_editing_one_of_two_bumps_only_that_one(backend):
    pid = backend.process.get_or_create_id("sf2p")
    saved = backend.device.upsert_devices(pid, [_device("a"), _device("b")], actor="me").devices

    payload = [dict(d) for d in saved]
    payload[0]["description"] = "바뀜"
    result = backend.device.upsert_devices(pid, payload, actor="kim")

    assert (result.updated, result.inserted, result.deleted) == (1, 0, 0)
    assert [d["version"] for d in payload] == [2, 1]
    a = _row(backend, pid, payload[0]["id"])
    b = _row(backend, pid, payload[1]["id"])
    assert (a["description"], a["version"], a["updated_by"]) == ("바뀜", 2, "kim")
    assert (b["description"], b["version"], b["updated_by"]) == ("", 1, "me")


def test_a_dict_without_an_id_is_inserted(backend):
    pid = backend.process.get_or_create_id("sf2p")
    (existing,) = backend.device.upsert_devices(pid, [_device("a")], actor="me").devices

    new = _device("b", "PFET")
    payload = [dict(existing), new]
    result = backend.device.upsert_devices(pid, payload, actor="me")

    assert result.devices is payload
    assert (result.updated, result.inserted, result.deleted) == (0, 1, 0)
    assert isinstance(new["id"], int)
    assert new["id"] != existing["id"]
    assert new["version"] == 1
    assert _names(backend, pid) == ["a", "b"]


def test_deleted_removes_the_device_and_its_tab_rows(backend):
    pid = backend.process.get_or_create_id("sf2p")
    a, b = backend.device.upsert_devices(pid, [_device("a"), _device("b")], actor="me").devices
    version = backend.parameter.replace_many_for_device(
        b["id"], {"inst_terms": (TERMS, _terms(("DRN", "d")))}, expected_version=1
    )

    result = backend.device.upsert_devices(
        pid, [dict(a)], deleted={b["id"]: version}, actor="me"
    )

    assert (result.updated, result.inserted, result.deleted) == (0, 0, 1)
    assert _names(backend, pid) == ["a"]
    assert backend.parameter.fetch_by_device("inst_terms", TERMS, b["id"]) == []


def test_a_device_missing_from_the_screen_survives(backend):
    pid = backend.process.get_or_create_id("sf2p")
    backend.device.upsert_devices(pid, [_device("a")], actor="me")
    view = backend.device.fetch_devices_by_process(pid)  # 내가 불러온 시점의 목록

    backend.device.upsert_device(pid, _device("kims"), actor="kim")
    result = backend.device.upsert_devices(pid, [dict(d) for d in view], deleted={}, actor="me")

    assert result.deleted == 0
    assert _names(backend, pid) == ["a", "kims"]


def test_a_device_moved_to_another_process_is_not_deleted(backend):
    pid = backend.process.get_or_create_id("sf2p")
    other = backend.process.get_or_create_id("sf4u")
    (dev,) = backend.device.upsert_devices(pid, [_device("a")], actor="me").devices
    moved = backend.device.upsert_device(other, dict(dev), actor="kim")
    assert moved["version"] == 2

    # version 은 맞지만 이제 다른 process 의 device 다
    result = backend.device.upsert_devices(
        pid, [], deleted={dev["id"]: moved["version"]}, actor="me"
    )

    assert result.deleted == 0
    assert backend.device.fetch_devices_by_process(pid) == []
    assert [d["id"] for d in backend.device.fetch_devices_by_process(other)] == [dev["id"]]


def test_a_stale_save_raises_and_writes_nothing(backend):
    pid = backend.process.get_or_create_id("sf2p")
    (dev,) = backend.device.upsert_devices(pid, [_device("a")], actor="me").devices
    mine = {**dev, "description": "내 것"}  # version 1 을 들고 있다
    backend.device.upsert_device(pid, {**dev, "description": "kim 이 먼저"}, actor="kim")

    with pytest.raises(StaleWriteError) as excinfo:
        backend.device.upsert_devices(pid, [mine], actor="me")

    (conflict,) = excinfo.value.conflicts
    assert (conflict.device_id, conflict.device_name, conflict.reason, conflict.updated_by) == (
        dev["id"],
        "a",
        "stale",
        "kim",
    )
    assert isinstance(conflict.updated_at, datetime)
    assert mine["version"] == 1
    row = _row(backend, pid, dev["id"])
    assert (row["description"], row["version"], row["updated_by"]) == ("kim 이 먼저", 2, "kim")


def test_force_overwrites_a_stale_row(backend):
    pid = backend.process.get_or_create_id("sf2p")
    (dev,) = backend.device.upsert_devices(pid, [_device("a")], actor="me").devices
    mine = {**dev, "description": "내 것"}
    backend.device.upsert_device(pid, {**dev, "description": "kim 이 먼저"}, actor="kim")

    result = backend.device.upsert_devices(pid, [mine], actor="me", force=True)

    assert (result.updated, result.inserted, result.deleted) == (1, 0, 0)
    assert mine["version"] == 3
    row = _row(backend, pid, dev["id"])
    assert (row["description"], row["version"], row["updated_by"]) == ("내 것", 3, "me")


def _deleted_by_kim(backend):
    """a, b 를 만들고 kim 이 둘 다 지운다. 내가 들고 있던 사본 둘을 준다."""
    pid = backend.process.get_or_create_id("sf2p")
    a, b = backend.device.upsert_devices(pid, [_device("a"), _device("b")], actor="me").devices
    mine_a, mine_b = dict(a), dict(b)
    backend.device.upsert_devices(pid, [], deleted={a["id"]: 1, b["id"]: 1}, actor="kim")
    return pid, mine_a, mine_b


def test_saving_or_deleting_what_someone_deleted_reports_deleted(backend):
    pid, a, b = _deleted_by_kim(backend)

    with pytest.raises(StaleWriteError) as excinfo:
        backend.device.upsert_devices(
            pid, [{**a, "description": "x"}], deleted={b["id"]: b["version"]}, actor="me"
        )

    # devices 쪽이 먼저, 그다음 deleted 쪽. deleted 쪽은 이름을 모른다.
    assert excinfo.value.conflicts == [
        Conflict(a["id"], "a", "deleted"),
        Conflict(b["id"], "", "deleted"),
    ]
    assert backend.device.fetch_devices_by_process(pid) == []


def test_force_does_not_bring_back_a_deleted_device(backend):
    pid, a, b = _deleted_by_kim(backend)

    result = backend.device.upsert_devices(
        pid, [{**a, "description": "x"}], deleted={b["id"]: b["version"]}, actor="me", force=True
    )

    assert (result.updated, result.inserted, result.deleted) == (0, 0, 0)
    assert backend.device.fetch_devices_by_process(pid) == []


# -- etag ------------------------------------------------------------------


def test_the_etag_of_an_empty_process(backend):
    pid = backend.process.get_or_create_id("sf2p")
    assert backend.device.etag(pid) == {"n": 0, "mx": None, "vs": 0, "who": None}


def test_the_etag_follows_writes_and_names_the_last_actor(backend):
    pid = backend.process.get_or_create_id("sf2p")
    backend.device.upsert_device(pid, _device("a"), actor="me")
    first = backend.device.etag(pid)
    assert (first["n"], first["vs"], first["who"]) == (1, 1, "me")
    assert isinstance(first["mx"], datetime)

    (dev,) = backend.device.fetch_devices_by_process(pid)
    backend.device.upsert_devices(pid, [{**dev, "description": "kim"}], actor="kim")
    second = backend.device.etag(pid)
    assert etag_key(second) != etag_key(first)
    assert (second["n"], second["vs"], second["who"]) == (1, 2, "kim")
    assert second["mx"] != first["mx"]

    # 탭만 저장해도 바뀐다 (device.version 이 집계 버전이다)
    backend.parameter.replace_many_for_device(
        dev["id"], {"inst_terms": (TERMS, _terms(("DRN", "d")))}, actor="lee"
    )
    third = backend.device.etag(pid)
    assert etag_key(third) != etag_key(second)
    assert (third["n"], third["vs"], third["who"]) == (1, 3, "lee")


def test_another_process_does_not_change_the_etag(backend):
    pid = backend.process.get_or_create_id("sf2p")
    other = backend.process.get_or_create_id("sf4u")
    backend.device.upsert_device(pid, _device("a"), actor="me")
    before = backend.device.etag(pid)

    backend.device.upsert_device(other, _device("x"), actor="kim")

    assert backend.device.etag(pid) == before


# -- replace_many_for_device / fetch_by_device -----------------------------


def test_two_tabs_in_one_save_bump_the_version_once(backend):
    pid = backend.process.get_or_create_id("sf2p")
    dev = backend.device.upsert_device(pid, _device("a"), actor="me")

    version = backend.parameter.replace_many_for_device(
        dev["id"],
        {
            "inst_terms": (TERMS, _terms(("DRN", "d"))),
            "inst_sch_params": (
                PARAMS,
                [{"reserved_key": "LENGTH", "cds_inst_parameter_name": "l"}],
            ),
        },
        expected_version=1,
        actor="kim",
    )

    assert version == 2
    row = _row(backend, pid, dev["id"])
    assert (row["version"], row["updated_by"]) == (2, "kim")

    # payload 에 없는 탭은 그대로다
    backend.parameter.replace_many_for_device(
        dev["id"], {"inst_sch_params": (PARAMS, [])}, expected_version=2
    )
    assert backend.parameter.fetch_by_device("inst_terms", TERMS, dev["id"]) == _terms(("DRN", "d"))
    assert backend.parameter.fetch_by_device("inst_sch_params", PARAMS, dev["id"]) == []


def test_tab_rows_come_back_in_insertion_order_with_only_the_requested_columns(backend):
    pid = backend.process.get_or_create_id("sf2p")
    dev = backend.device.upsert_device(pid, _device("a"))

    # 알파벳 순이 아닌 순서. None 과 빠진 값은 "" 가 된다.
    rows = [
        {"reserved_key": "GATE", "cds_inst_term_name": "g"},
        {"reserved_key": "DRN", "cds_inst_term_name": None},
        {"reserved_key": "SRC"},
    ]
    backend.parameter.replace_many_for_device(dev["id"], {"inst_terms": (TERMS, rows)})

    assert backend.parameter.fetch_by_device("inst_terms", TERMS, dev["id"]) == _terms(
        ("GATE", "g"), ("DRN", ""), ("SRC", "")
    )
    assert backend.parameter.fetch_by_device("inst_terms", ["cds_inst_term_name"], dev["id"]) == [
        {"cds_inst_term_name": "g"},
        {"cds_inst_term_name": ""},
        {"cds_inst_term_name": ""},
    ]

    # payload 의 columns 밖의 컬럼은 "" (DEFAULT '') 다
    backend.parameter.replace_many_for_device(
        dev["id"],
        {"inst_terms": (["reserved_key"], [{"reserved_key": "BULK", "cds_inst_term_name": "x"}])},
    )
    assert backend.parameter.fetch_by_device("inst_terms", TERMS, dev["id"]) == _terms(("BULK", ""))


def test_tab_rows_of_a_vanished_device_are_empty(backend):
    pid = backend.process.get_or_create_id("sf2p")
    dev = backend.device.upsert_device(pid, _device("a"))
    backend.device.upsert_devices(pid, [], deleted={dev["id"]: 1})
    assert backend.parameter.fetch_by_device("inst_terms", TERMS, dev["id"]) == []


def test_rewriting_the_same_rows_still_bumps_the_version(backend):
    pid = backend.process.get_or_create_id("sf2p")
    dev = backend.device.upsert_device(pid, _device("a"))
    payload = {"inst_terms": (TERMS, _terms(("DRN", "d")))}

    first = backend.parameter.replace_many_for_device(dev["id"], payload, expected_version=1)
    second = backend.parameter.replace_many_for_device(dev["id"], payload, expected_version=first)

    assert (first, second) == (2, 3)
    assert _row(backend, pid, dev["id"])["version"] == 3


def test_a_stale_tab_save_raises_and_keeps_the_rows(backend):
    pid = backend.process.get_or_create_id("sf2p")
    dev = backend.device.upsert_device(pid, _device("a"))
    mine = backend.parameter.replace_many_for_device(
        dev["id"], {"inst_terms": (TERMS, _terms(("DRN", "d")))}, expected_version=1
    )
    current = _row(backend, pid, dev["id"])
    backend.device.upsert_device(pid, {**current, "description": "kim"}, actor="kim")

    payload = {"inst_terms": (TERMS, _terms(("GATE", "g")))}
    with pytest.raises(StaleWriteError) as excinfo:
        backend.parameter.replace_many_for_device(
            dev["id"], payload, expected_version=mine, actor="me"
        )

    (conflict,) = excinfo.value.conflicts
    assert (conflict.device_id, conflict.device_name, conflict.reason, conflict.updated_by) == (
        dev["id"],
        "a",
        "stale",
        "kim",
    )
    assert isinstance(conflict.updated_at, datetime)
    assert backend.parameter.fetch_by_device("inst_terms", TERMS, dev["id"]) == _terms(("DRN", "d"))
    assert _row(backend, pid, dev["id"])["version"] == 3

    forced = backend.parameter.replace_many_for_device(
        dev["id"], payload, expected_version=mine, actor="me", force=True
    )
    assert forced == 4
    assert backend.parameter.fetch_by_device("inst_terms", TERMS, dev["id"]) == _terms(
        ("GATE", "g")
    )


@pytest.mark.parametrize("force", [False, True])
def test_a_tab_save_for_a_vanished_device_is_deleted_even_with_force(backend, force):
    pid = backend.process.get_or_create_id("sf2p")
    dev = backend.device.upsert_device(pid, _device("a"))
    backend.device.upsert_devices(pid, [], deleted={dev["id"]: 1}, actor="kim")

    with pytest.raises(StaleWriteError) as excinfo:
        backend.parameter.replace_many_for_device(
            dev["id"],
            {"inst_terms": (TERMS, _terms(("DRN", "d")))},
            expected_version=1,
            force=force,
        )

    assert excinfo.value.conflicts == [Conflict(dev["id"], "", "deleted")]
    assert backend.parameter.fetch_by_device("inst_terms", TERMS, dev["id"]) == []


@pytest.mark.parametrize(
    "payload",
    [
        {"inst_terms": (TERMS, _terms(("GATE", "g"))), "no_such_table": (["x"], [])},
        {"inst_terms": ([*TERMS, "no_such_column"], _terms(("GATE", "g")))},
    ],
    ids=["table", "column"],
)
def test_an_unknown_table_or_column_raises_key_error_and_writes_nothing(backend, payload):
    pid = backend.process.get_or_create_id("sf2p")
    dev = backend.device.upsert_device(pid, _device("a"))
    version = backend.parameter.replace_many_for_device(
        dev["id"], {"inst_terms": (TERMS, _terms(("DRN", "d")))}, expected_version=1
    )

    with pytest.raises(KeyError):
        backend.parameter.replace_many_for_device(dev["id"], payload, expected_version=version)

    assert backend.parameter.fetch_by_device("inst_terms", TERMS, dev["id"]) == _terms(("DRN", "d"))
    assert _row(backend, pid, dev["id"])["version"] == version
    with pytest.raises(KeyError):
        backend.parameter.fetch_by_device("no_such_table", ["x"], dev["id"])
    with pytest.raises(KeyError):
        backend.parameter.fetch_by_device("inst_terms", ["no_such_column"], dev["id"])


# -- import_data / fetch_export_data ---------------------------------------

CSV_TEXT = (
    "CellType,CdsLibName,InstCellName,InstTerm,InstTerm,InstSchParam\n"
    "PFET,sf9x,pfet_z,DRN d,,\n"
    "NFET,sf2p,nfet_c,DRN d,GATE g,LENGTH 1 2\n"
)


def _import(backend, tmp_path) -> int:
    backend.process.get_or_create_id("sf2p")
    path = tmp_path / "in.csv"
    path.write_text(CSV_TEXT, encoding="utf-8", newline="")
    return backend.io.import_data(str(path), actor="me")


def _only_device(backend, process_name):
    (dev,) = backend.device.fetch_devices_by_process(
        backend.process.get_or_create_id(process_name)
    )
    return dev


def test_import_makes_a_device_per_row_and_splits_cells(backend, tmp_path):
    assert _import(backend, tmp_path) == 2

    assert backend.process.list_all() == ["sf2p", "sf9x"]
    nfet = _only_device(backend, "sf2p")
    pfet = _only_device(backend, "sf9x")
    fields = ("name", "celltype", "description", "order", "version", "updated_by")
    assert [nfet[k] for k in fields] == ["nfet_c", "NFET", "", 0, 1, "me"]
    assert [pfet[k] for k in fields] == ["pfet_z", "PFET", "", 0, 1, "me"]

    terms = backend.parameter.fetch_by_device
    assert terms("inst_terms", TERMS, nfet["id"]) == _terms(("DRN", "d"), ("GATE", "g"))
    assert terms("inst_sch_params", PARAMS, nfet["id"]) == [
        {"reserved_key": "LENGTH", "cds_inst_parameter_name": "1 2"}
    ]
    assert terms("inst_terms", TERMS, pfet["id"]) == _terms(("DRN", "d"))
    assert terms("inst_sch_params", PARAMS, pfet["id"]) == []


def test_import_of_a_missing_file_raises(backend, tmp_path):
    with pytest.raises(FileNotFoundError):
        backend.io.import_data(str(tmp_path / "없음.csv"))


@pytest.mark.parametrize(
    "csv_text",
    [
        "CellType,InstCellName\nNFET,nfet_c\n",  # CdsLibName 이 없다
        "CellType,CdsLibName\nNFET,sf7n\n",  # InstCellName 이 없다. process 는 이미 만든 뒤다
    ],
    ids=["no-CdsLibName", "no-InstCellName"],
)
def test_import_without_a_required_column_raises_and_writes_nothing(backend, tmp_path, csv_text):
    pid = backend.process.get_or_create_id("sf2p")
    backend.device.upsert_device(pid, _device("a"))
    path = tmp_path / "bad.csv"
    path.write_text(csv_text, encoding="utf-8", newline="")

    with pytest.raises(KeyError):
        backend.io.import_data(str(path), actor="me")

    assert backend.process.list_all() == ["sf2p"]
    assert backend.process.count_devices("sf2p") == 1


def test_export_orders_rows_by_celltype_and_skips_info_without_a_process(backend, tmp_path):
    _import(backend, tmp_path)
    nfet = _only_device(backend, "sf2p")
    pfet = _only_device(backend, "sf9x")
    # process_name 이 빈 info 가 가리키는 device. 건너뛰지 않으면 InstTerm 이 세 칸이 된다.
    stray = backend.device.upsert_device(
        backend.process.get_or_create_id("sf4u"), _device("stray")
    )
    backend.parameter.replace_many_for_device(
        stray["id"], {"inst_terms": (TERMS, _terms(("DRN", "1"), ("GATE", "2"), ("SRC", "3")))}
    )

    headers, rows = backend.io.fetch_export_data(
        [
            {**pfet, "process_name": "sf9x"},
            {**nfet, "process_name": "sf2p"},
            {**stray, "process_name": ""},
        ]
    )

    # Description 은 description 이 전부 비어도 InstCellName 다음에 늘 있다(K44)
    assert headers == [
        "CellType",
        "CdsLibName",
        "InstCellName",
        "Description",
        "InstTerm",
        "InstTerm",
        "InstSchParam",
    ]
    # celltype 우선순위(delegate_config)에서 NFET 이 PFET 보다 앞이다
    assert rows == [
        ["NFET", "sf2p", "nfet_c", "", "DRN d", "GATE g", "LENGTH 1 2"],
        ["PFET", "sf9x", "pfet_z", "", "DRN d", "", ""],
    ]


def test_export_rows_carry_the_values_in_device_info(backend, tmp_path):
    _import(backend, tmp_path)
    nfet = _only_device(backend, "sf2p")

    _, rows = backend.io.fetch_export_data(
        [
            {
                "id": nfet["id"],
                "process_name": "화면 process",
                "name": "화면 이름",
                "celltype": "PFET",
                "description": "화면 설명",
            }
        ]
    )

    assert rows == [
        ["PFET", "화면 process", "화면 이름", "화면 설명", "DRN d", "GATE g", "LENGTH 1 2"]
    ]


def _import_text(backend, tmp_path, text) -> int:
    path = tmp_path / "desc.csv"
    path.write_text(text, encoding="utf-8", newline="")
    return backend.io.import_data(str(path), actor="me")


def test_import_puts_the_description_column_into_the_device(backend, tmp_path):
    """Description 컬럼이 있으면 그 칸이 다듬지 않은 그대로 device.description 이다(K44)."""
    text = (
        "CellType,CdsLibName,InstCellName,Description,InstTerm\n"
        'NFET,sf2p,nfet_c," ESD 용, 2단 ",DRN d\n'
    )
    assert _import_text(backend, tmp_path, text) == 1

    dev = _only_device(backend, "sf2p")
    assert dev["description"] == " ESD 용, 2단 "
    assert backend.parameter.fetch_by_device("inst_terms", TERMS, dev["id"]) == _terms(
        ("DRN", "d")
    )


def test_import_without_a_description_column_leaves_it_empty(backend, tmp_path):
    """옛 CSV 와 molgen 이 만든 CSV 에는 Description 이 없다. 거부하지 않고 빈 값이다."""
    assert _import(backend, tmp_path) == 2

    assert _only_device(backend, "sf2p")["description"] == ""
    assert _only_device(backend, "sf9x")["description"] == ""


def test_import_reads_only_the_first_description_column(backend, tmp_path):
    """반복된 Description(pandas 의 Description.1)은 지금처럼 무시한다."""
    text = (
        "CellType,CdsLibName,InstCellName,Description,Description\n"
        "NFET,sf2p,nfet_c,첫 설명,둘째 설명\n"
    )
    assert _import_text(backend, tmp_path, text) == 1

    assert _only_device(backend, "sf2p")["description"] == "첫 설명"


def test_description_survives_export_and_import_again(backend, tmp_path):
    """불러오기 → 내보내기 → 다시 불러오기에서 description 이 따라온다.

    쉼표·줄바꿈은 넣지 않는다. CSV 쓰기가 molgen 로더에 맞춰 바꿔 쓰는 값이다(step 3).
    """
    text = (
        "CellType,CdsLibName,InstCellName,Description,InstTerm\n"
        "NFET,sf2p,nfet_c, ESD 용 2단 ,DRN d\n"
        "PFET,sf2p,pfet_z,,DRN d\n"
    )
    assert _import_text(backend, tmp_path, text) == 2
    pid = backend.process.get_or_create_id("sf2p")
    first = backend.device.fetch_devices_by_process(pid)

    headers, rows = backend.io.fetch_export_data(
        [{**d, "process_name": "sf2p"} for d in first]
    )
    out = tmp_path / "out.csv"
    write_csv(str(out), headers, rows)
    assert backend.io.import_data(str(out), actor="me") == 2

    first_ids = {d["id"] for d in first}
    again = [d for d in backend.device.fetch_devices_by_process(pid) if d["id"] not in first_ids]
    assert {d["name"]: d["description"] for d in again} == {
        "nfet_c": " ESD 용 2단 ",
        "pfet_z": "",
    }


# -- audit.recent ----------------------------------------------------------

AUDIT_KEYS = {c.strip() for c in audit._COLUMNS.split(",")}
P1, P2, P3 = "process 추가  p1", "process 추가  p2", "process 추가  p3"


def _summaries(rows):
    return [r["summary"] for r in rows]


def _log_three(backend):
    """p1, p2, p3 을 차례로 남기고 그 세 줄을 준다."""
    for name in ("p1", "p2", "p3"):
        backend.log("me", audit.process_add(name))
    rows = backend.audit.recent()
    assert _summaries(rows) == [P1, P2, P3]
    return rows


def test_recent_gives_the_last_lines_oldest_first(backend):
    _log_three(backend)

    assert _summaries(backend.audit.recent(limit=2)) == [P2, P3]
    assert backend.audit.recent(limit=0) == []


def test_recent_filters_by_actor_process_and_device(backend):
    backend.log("kim", audit.process_add("sf2p"))
    backend.log("lee", audit.device_insert("sf2p", {"id": 7, "name": "nfet_a", "celltype": "NFET"}))
    backend.log("kim", audit.device_insert("sf4u", {"id": 8, "name": "pfet_a", "celltype": "PFET"}))

    def found(**filters):
        return [(r["actor"], audit.where_of(r)) for r in backend.audit.recent(**filters)]

    assert found(actor="kim") == [("kim", "sf2p"), ("kim", "sf4u/pfet_a")]
    assert found(process="sf2p") == [("kim", "sf2p"), ("lee", "sf2p/nfet_a")]
    assert found(device="nfet_a") == [("lee", "sf2p/nfet_a")]
    assert found(actor="kim", process="sf4u") == [("kim", "sf4u/pfet_a")]
    assert found(actor="park") == []
    # 빈 문자열은 거르지 않는다
    assert len(found(actor="", process="", device="")) == 3


def test_recent_contains_looks_in_summary_and_detail_ignoring_case(backend):
    backend.log("me", audit.process_add("sf2p"))
    backend.log(
        "me",
        audit.device_insert(
            "sf2p", {"name": "nfet_a", "celltype": "NFET", "description": "측정용 MagicWord"}
        ),
    )  # description 은 summary 에 없고 detail 에만 있다
    backend.log("me", audit.process_add("abc"))

    def found(text):
        return _summaries(backend.audit.recent(contains=text))

    assert found("PROCESS 추가") == ["process 추가  sf2p", "process 추가  abc"]
    assert found("magicword") == ["device 추가  nfet_a (NFET)"]
    assert found("측정용") == ["device 추가  nfet_a (NFET)"]
    assert found("없는 글자") == []
    # 실제 ILIKE 그대로다: 찾을 글자의 `_` 는 아무 한 글자다
    assert found("a_c") == ["process 추가  abc"]


def test_recent_since_is_inclusive_and_until_is_exclusive(backend):
    first, second, third = _log_three(backend)
    assert first["at"] < second["at"] < third["at"]  # 경계를 보려면 세 시각이 달라야 한다

    def found(**filters):
        return _summaries(backend.audit.recent(**filters))

    assert found(since=second["at"]) == [P2, P3]
    assert found(until=second["at"]) == [P1]
    assert found(since=first["at"], until=third["at"]) == [P1, P2]
    # naive 시각은 이 PC 의 로컬 시각으로 본다 (audit._aware)
    local = second["at"].astimezone().replace(tzinfo=None)
    assert found(since=local) == [P2, P3]
    assert found(until=local) == [P1]


def test_recent_after_id(backend):
    first, _, third = _log_three(backend)

    assert _summaries(backend.audit.recent(after_id=first["id"])) == [P2, P3]
    assert _summaries(backend.audit.recent(after_id=first["id"], limit=1)) == [P3]
    assert backend.audit.recent(after_id=third["id"]) == []


def test_recent_rows_have_the_change_log_columns(backend):
    backend.log(
        "kim",
        audit.device_insert(
            "sf2p", {"id": 7, "name": "nfet_a", "celltype": "NFET", "description": "", "order": 2}
        ),
    )
    backend.log("kim", audit.process_add("sf4u"))

    first, second = backend.audit.recent()

    assert set(first) == set(second) == AUDIT_KEYS
    assert isinstance(first["id"], int)
    assert second["id"] > first["id"]
    assert isinstance(first["at"], datetime)
    assert first["at"].tzinfo is not None
    assert {k: v for k, v in first.items() if k not in ("id", "at")} == {
        "actor": "kim",
        "source": "",
        "action": "insert",
        "process_name": "sf2p",
        "device_name": "nfet_a",
        "device_id": 7,
        "table_name": "",
        "summary": "device 추가  nfet_a (NFET)",
        "detail": {"after": {"name": "nfet_a", "celltype": "NFET", "description": "", "order": 2}},
        "process_release": "",
    }
    assert (second["device_name"], second["device_id"], second["detail"]) == ("", None, {})


def test_recent_filters_by_release_only_when_one_is_given(backend):
    backend.log("kim", audit.process_add("sf2p", process_release="V1"))
    backend.log("kim", audit.process_add("sf2p"))
    backend.log(
        "lee",
        audit.device_insert(
            "sf2p", {"id": 7, "name": "nfet_a", "celltype": "NFET"}, process_release="V1"
        ),
    )

    def found(**filters):
        return [
            (r["process_release"], audit.where_of(r)) for r in backend.audit.recent(**filters)
        ]

    assert found(release="V1") == [("V1", "sf2p V1"), ("V1", "sf2p V1/nfet_a")]
    # 빈 문자열은 "버전 없는 것만" 이다 (다른 필터의 빈 문자열과 다르다)
    assert found(release="") == [("", "sf2p")]
    assert found() == found(release=None) == [
        ("V1", "sf2p V1"),
        ("", "sf2p"),
        ("V1", "sf2p V1/nfet_a"),
    ]
    assert found(release="V2") == []
    # process 필터는 이름만 본다 (모든 버전)
    assert len(found(process="sf2p")) == 3
    assert found(process="sf2p", release="V1", actor="lee") == [("V1", "sf2p V1/nfet_a")]
