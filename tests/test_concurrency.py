"""여러 사람이 동시에 편집할 때 작업이 사라지지 않는지 검증한다.

이 마이그레이션 전체가 존재하는 이유가 test_other_users_new_device_survives 다.
"""

import pytest

from genviewer.service.errors import StaleWriteError
from genviewer.service.repo.device import DeviceRepository
from genviewer.service.repo.parameter import ParameterRepository
from genviewer.service.repo.process import ProcessRepository

TERM_COLUMNS = ["reserved_key", "cds_inst_term_name"]


@pytest.fixture
def process_id(db):
    return ProcessRepository(db).get_or_create_id("sf2p")


def _device(name="nfet_b", celltype="NFET", **kw):
    return {"name": name, "celltype": celltype, "description": "", "order": 0, **kw}


def test_other_users_new_device_survives(db, process_id):
    """A 가 device 를 추가한 뒤 B(추가 전에 불러옴)가 저장해도 A 것이 살아남는다.

    예전 upsert_devices 는 화면에 없는 id 를 전부 지웠기 때문에 여기서 A 의
    작업이 조용히 사라졌다. 이 마이그레이션에서 가장 중요한 단언이다.
    """
    repo = DeviceRepository(db)
    repo.upsert_devices(process_id, [_device("nfet_b")], actor="B")
    b_view = repo.fetch_devices_by_process(process_id)  # B 가 불러온 시점의 목록

    # A 가 device 를 추가한다.
    repo.upsert_devices(process_id, [_device("pfet_b", "PFET")], actor="A")

    # B 는 pfet_b 를 모른 채 자기 목록을 저장한다.
    repo.upsert_devices(process_id, [dict(d) for d in b_view], deleted={}, actor="B")

    names = {d["name"] for d in repo.fetch_devices_by_process(process_id)}
    assert names == {"nfet_b", "pfet_b"}, "A 가 추가한 device 가 사라졌다"


def test_only_explicitly_deleted_rows_are_removed(db, process_id):
    repo = DeviceRepository(db)
    devices = repo.upsert_devices(
        process_id, [_device("a"), _device("b"), _device("c")], actor="A"
    )
    victim = next(d for d in devices if d["name"] == "b")

    keep = [d for d in devices if d["name"] != "b"]
    repo.upsert_devices(
        process_id, keep, deleted={victim["id"]: victim["version"]}, actor="A"
    )

    names = {d["name"] for d in repo.fetch_devices_by_process(process_id)}
    assert names == {"a", "c"}


def test_stale_version_raises_and_writes_nothing(db, process_id):
    repo = DeviceRepository(db)
    (dev,) = repo.upsert_devices(process_id, [_device("nfet_b")], actor="A")

    stale = dict(dev)  # B 가 들고 있는 오래된 사본
    repo.upsert_devices(
        process_id, [{**dev, "description": "A 가 먼저 수정"}], actor="dh991"
    )

    with pytest.raises(StaleWriteError) as excinfo:
        repo.upsert_devices(
            process_id, [{**stale, "description": "B 가 나중에 수정"}], actor="B"
        )

    conflict = excinfo.value.conflicts[0]
    assert conflict.reason == "stale"
    assert conflict.updated_by == "dh991"

    # 아무것도 쓰이지 않았어야 한다.
    current = repo.fetch_devices_by_process(process_id)[0]
    assert current["description"] == "A 가 먼저 수정"


def test_force_overrides_the_conflict(db, process_id):
    repo = DeviceRepository(db)
    (dev,) = repo.upsert_devices(process_id, [_device("nfet_b")], actor="A")
    stale = dict(dev)
    repo.upsert_devices(process_id, [{**dev, "description": "A"}], actor="A")

    repo.upsert_devices(
        process_id, [{**stale, "description": "B 가 덮어씀"}], actor="B", force=True
    )
    assert repo.fetch_devices_by_process(process_id)[0]["description"] == "B 가 덮어씀"


def test_unchanged_save_does_not_bump_version(db, process_id):
    """손대지 않은 device 의 version 은 그대로여야 한다.

    save_all 은 화면의 모든 device 를 보낸다. 가드가 없으면 누군가 저장할 때마다
    process 전체의 version 이 올라가 다른 사용자들이 건드리지도 않은 행에서
    충돌을 맞는다.
    """
    repo = DeviceRepository(db)
    devices = repo.upsert_devices(process_id, [_device("a"), _device("b")], actor="A")
    before = {d["id"]: d["version"] for d in repo.fetch_devices_by_process(process_id)}

    # 'a' 만 고치고 둘 다 보낸다.
    payload = [dict(d) for d in devices]
    payload[0]["description"] = "바뀜"
    repo.upsert_devices(process_id, payload, actor="A")

    after = {d["id"]: d["version"] for d in repo.fetch_devices_by_process(process_id)}
    changed = [i for i in before if after[i] != before[i]]
    assert len(changed) == 1, "손대지 않은 device 의 version 까지 올라갔다"


def test_child_tables_bump_the_device_version_once(db, process_id):
    """탭 N개를 저장해도 version 은 한 번만 올라간다.

    탭마다 올리면 첫 탭이 version 을 올리는 순간 두 번째 탭의 검사가 실패해서
    두 탭 동시 저장이 항상 깨진다.
    """
    dev_repo = DeviceRepository(db)
    par = ParameterRepository(db)
    (dev,) = dev_repo.upsert_devices(process_id, [_device("nfet_b")], actor="A")
    v0 = dev["version"]

    new_version = par.replace_many_for_device(
        dev["id"],
        {
            "inst_terms": (TERM_COLUMNS, [{"reserved_key": "DRN", "cds_inst_term_name": "d"}]),
            "suffix_cell_name": (["suffix_cell_name"], [{"suffix_cell_name": "_x"}]),
            "add_fgr_params": (
                ["parameter_name", "value"],
                [{"parameter_name": "w", "value": "1"}],
            ),
        },
        expected_version=v0,
        actor="A",
    )
    assert new_version == v0 + 1, "탭마다 version 이 올라갔다"


def test_child_write_detects_a_stale_device(db, process_id):
    dev_repo = DeviceRepository(db)
    par = ParameterRepository(db)
    (dev,) = dev_repo.upsert_devices(process_id, [_device("nfet_b")], actor="A")
    stale_version = dev["version"]

    dev_repo.upsert_devices(
        process_id, [{**dev, "description": "A 가 먼저"}], actor="dh991"
    )

    with pytest.raises(StaleWriteError):
        par.replace_many_for_device(
            dev["id"],
            {"inst_terms": (TERM_COLUMNS, [{"reserved_key": "DRN", "cds_inst_term_name": "d"}])},
            expected_version=stale_version,
            actor="B",
        )
    assert par.fetch_by_device("inst_terms", TERM_COLUMNS, dev["id"]) == []


def test_child_row_order_survives_a_rewrite(db, process_id):
    """자식 행은 삽입 순서대로 다시 읽혀야 한다 (CSV 컬럼 순서가 된다)."""
    dev_repo = DeviceRepository(db)
    par = ParameterRepository(db)
    (dev,) = dev_repo.upsert_devices(process_id, [_device("nfet_b")], actor="A")

    order = [("DRN", "d"), ("GATE", "g"), ("SRC", "s"), ("BULK", "b")]
    version = par.replace_all_for_device(
        "inst_terms",
        TERM_COLUMNS,
        dev["id"],
        [{"reserved_key": k, "cds_inst_term_name": v} for k, v in order],
        expected_version=dev["version"],
        actor="A",
    )
    # 한 번 더 써서 id 가 새로 발급되게 한 뒤에도 순서가 유지되는지 본다.
    par.replace_all_for_device(
        "inst_terms",
        TERM_COLUMNS,
        dev["id"],
        [{"reserved_key": k, "cds_inst_term_name": v} for k, v in order],
        expected_version=version,
        actor="A",
    )

    got = par.fetch_by_device("inst_terms", TERM_COLUMNS, dev["id"])
    assert [r["reserved_key"] for r in got] == [k for k, _ in order]


def test_duplicate_device_name_is_rejected(db, process_id):
    """두 사람이 같은 이름으로 device 를 만들면 두 번째는 실패해야 한다."""
    import psycopg

    repo = DeviceRepository(db)
    repo.upsert_devices(process_id, [_device("nfet_b")], actor="A")
    with pytest.raises(psycopg.errors.UniqueViolation):
        repo.upsert_devices(process_id, [_device("nfet_b")], actor="B")
