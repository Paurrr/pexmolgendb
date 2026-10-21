"""여러 사람이 동시에 편집할 때 작업이 사라지지 않는지 검증한다.

이 마이그레이션 전체가 존재하는 이유가 test_other_users_new_device_survives 다.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import psycopg
import pytest
from psycopg.rows import dict_row

from genviewer.service.config import DbConfig
from genviewer.service.errors import StaleWriteError
from genviewer.service.pool import Database
from genviewer.service.repo import audit
from genviewer.service.repo.audit import AuditRepository
from genviewer.service.repo.device import DeviceRepository
from genviewer.service.repo.io import IORepository
from genviewer.service.repo.parameter import ParameterRepository
from genviewer.service.repo.process import ProcessRepository, find_or_create

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
    ).devices
    victim = next(d for d in devices if d["name"] == "b")

    keep = [d for d in devices if d["name"] != "b"]
    repo.upsert_devices(
        process_id, keep, deleted={victim["id"]: victim["version"]}, actor="A"
    )

    names = {d["name"] for d in repo.fetch_devices_by_process(process_id)}
    assert names == {"a", "c"}


def test_stale_version_raises_and_writes_nothing(db, process_id):
    repo = DeviceRepository(db)
    (dev,) = repo.upsert_devices(process_id, [_device("nfet_b")], actor="A").devices

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
    (dev,) = repo.upsert_devices(process_id, [_device("nfet_b")], actor="A").devices
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
    saved = repo.upsert_devices(process_id, [_device("a"), _device("b")], actor="A")
    devices = saved.devices
    before = {d["id"]: d["version"] for d in repo.fetch_devices_by_process(process_id)}

    # 'a' 만 고치고 둘 다 보낸다.
    payload = [dict(d) for d in devices]
    payload[0]["description"] = "바뀜"
    result = repo.upsert_devices(process_id, payload, actor="A")

    after = {d["id"]: d["version"] for d in repo.fetch_devices_by_process(process_id)}
    changed = [i for i in before if after[i] != before[i]]
    assert len(changed) == 1, "손대지 않은 device 의 version 까지 올라갔다"
    # 보고되는 개수도 payload 크기(2)가 아니라 실제로 쓰인 수(1)여야 한다.
    assert (result.updated, result.inserted, result.deleted) == (1, 0, 0)
    assert saved.inserted == 2, "처음 저장은 두 행 다 새로 들어간다"


def test_save_counts_only_what_the_database_wrote(db, process_id):
    """SaveResult 는 payload 크기가 아니라 DB 가 실제로 쓴 행을 센다.

    이것이 없으면 화면의 device 20개를 전부 보내는 save_all 이 1개만 고쳐도
    "20개 저장됨" 이라고 말한다.
    """
    repo = DeviceRepository(db)
    devices = repo.upsert_devices(
        process_id, [_device("a"), _device("b"), _device("c")], actor="A"
    ).devices

    # 하나도 안 고치고 전부 다시 보낸다.
    untouched = repo.upsert_devices(process_id, [dict(d) for d in devices], actor="A")
    assert untouched.written == 0

    # 하나 고치고, 하나 추가하고, 하나 지운다 — 셋 다 한 번에.
    victim = devices[2]
    payload = [dict(devices[0]), dict(devices[1]), _device("d")]
    payload[0]["description"] = "바뀜"
    mixed = repo.upsert_devices(
        process_id,
        payload,
        deleted={victim["id"]: victim["version"]},
        actor="A",
    )
    assert (mixed.updated, mixed.inserted, mixed.deleted) == (1, 1, 1)
    assert mixed.written == 3


def test_child_tables_bump_the_device_version_once(db, process_id):
    """탭 N개를 저장해도 version 은 한 번만 올라간다.

    탭마다 올리면 첫 탭이 version 을 올리는 순간 두 번째 탭의 검사가 실패해서
    두 탭 동시 저장이 항상 깨진다.
    """
    dev_repo = DeviceRepository(db)
    par = ParameterRepository(db)
    (dev,) = dev_repo.upsert_devices(process_id, [_device("nfet_b")], actor="A").devices
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
    (dev,) = dev_repo.upsert_devices(process_id, [_device("nfet_b")], actor="A").devices
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
    (dev,) = dev_repo.upsert_devices(process_id, [_device("nfet_b")], actor="A").devices

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


def test_duplicate_device_names_are_allowed(db, process_id):
    """같은 이름의 device 두 개가 나란히 들어간다.

    한동안 UNIQUE (process_id, name) 이 두 번째를 UniqueViolation 으로 막았다.
    그런데 현장 CSV 에는 같은 CdsLibName/InstCellName 행이 정상적으로 여러 개
    들어오고, 사람이 Insert 로 같은 이름을 추가하는 것도 막을 이유가 없다.
    이름은 식별자가 아니라 표시용 값이고 식별은 id 가 한다.
    """
    repo = DeviceRepository(db)
    repo.upsert_devices(process_id, [_device("nfet_b")], actor="A")
    repo.upsert_devices(process_id, [_device("nfet_b", "PFET")], actor="B")

    rows = repo.fetch_devices_by_process(process_id)
    assert [r["name"] for r in rows] == ["nfet_b", "nfet_b"]
    assert len({r["id"] for r in rows}) == 2, "같은 행에 덮어썼다"
    assert sorted(r["celltype"] for r in rows) == ["NFET", "PFET"]


def test_a_save_larger_than_one_statement_can_bind(db, process_id):
    """device 가 아주 많은 process 를 정렬하고 저장해도 저장된다 (K9).

    한 문장의 바인드 파라미터는 65,535개까지다. UPDATE 는 행 하나에 6개 +
    actor 1개라 10,923행이면 65,539개다. 이력도 10,923줄이라 한 줄 9개로 넘는다.
    """
    n = 10_923
    with db.connection() as conn:
        conn.execute(
            'INSERT INTO device (process_id, name, celltype, "order") '
            "SELECT %s, 'd' || g, 'NFET', g FROM generate_series(1, %s) g",
            (process_id, n),
        )
    repo = DeviceRepository(db)
    before = repo.fetch_devices_by_process(process_id)
    assert len(before) == n

    # 뒤집는다. order g 인 행은 n - g 가 되어 n 이 홀수여도 그대로인 행이 없다.
    payload = [{**d, "order": i} for i, d in enumerate(reversed(before))]
    result = repo.upsert_devices(process_id, payload, actor="A")

    assert result.updated == n
    old = {d["id"]: d["version"] for d in before}
    after = repo.fetch_devices_by_process(process_id)
    assert all(d["version"] == old[d["id"]] + 1 for d in after)
    assert all(d["version"] == old[d["id"]] + 1 for d in result.devices)
    with db.connection() as conn:
        logged = conn.execute(
            "SELECT count(*) AS n FROM change_log WHERE action = %s", (audit.UPDATE,)
        ).fetchone()["n"]
    assert logged == n


# ---------------------------------------------------------------------------
# CSV 불러오기와 GUI 가 같은 process 를 만질 때 (K5)
# ---------------------------------------------------------------------------


@contextmanager
def _import_in_progress(pg_dsn, process_name, release=""):
    """CLI load 가 process 를 찾고 device 를 넣은 뒤 커밋하기 전 상태로 멈춘다.

    큰 파일이면 load 의 트랜잭션은 이 상태로 오래 있다(statement_timeout 0).
    """
    conn = psycopg.connect(pg_dsn, row_factory=dict_row)
    try:
        cur = conn.cursor()
        process_id = IORepository._process_id(cur, process_name, release)
        cur.execute(
            "INSERT INTO device (process_id, name, celltype, updated_by) "
            "VALUES (%s, %s, %s, %s)",
            (process_id, "from_csv", "NFET", "cli"),
        )
        yield process_id
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def gui_db(pg_dsn):
    """다른 사용자(GUI)의 Database. 잠금을 300ms 만 기다린다."""
    other = Database(DbConfig(dsn=pg_dsn, lock_timeout_ms=300))
    other.open()
    try:
        # 접속 시간을 아래에서 재는 시간에 넣지 않는다.
        with other.connection() as conn:
            conn.execute("SELECT 1")
        yield other
    finally:
        other.close()


@pytest.mark.parametrize("release", ["", "S00-V1.0.0.0"])
def test_choosing_a_process_does_not_wait_for_an_import(db, pg_dsn, gui_db, release):
    """CSV 를 불러오는 동안 GUI 에서 같은 process 를 골라도 기다리지 않는다 (K5).

    예전에는 불러오기가 ON CONFLICT DO UPDATE 로 process 행을 잠근 채 커밋까지
    쥐고 있었고, GUI 의 get_or_create_id 도 같은 DO UPDATE 로 그 행을 잠그려다
    lock_timeout 뒤 55P03 으로 실패했다. 불러오기의 device INSERT 가 외래키
    검사로 잡는 FOR KEY SHARE 도 DO UPDATE(FOR UPDATE)와 부딪히므로 고르는
    쪽도 잠그지 않아야 한다. 버전이 있는 (이름, 버전) 쌍도 같다.
    """
    process_id = ProcessRepository(db).get_or_create_id("sf2p", release=release)
    with _import_in_progress(pg_dsn, "sf2p", release):
        start = time.monotonic()
        got = ProcessRepository(gui_db).get_or_create_id("sf2p", release=release, actor="gui")
        elapsed = time.monotonic() - start

    assert got == process_id
    assert elapsed < 0.3, f"{elapsed:.3f}초 기다렸다"


@pytest.mark.parametrize("release", ["", "S00-V1.0.0.0"])
def test_saving_in_a_process_does_not_wait_for_an_import(db, pg_dsn, gui_db, release):
    """CSV 를 불러오는 동안 같은 process 에 device 를 저장해도 기다리지 않는다.

    저장의 device INSERT 도 외래키 검사로 process 행에 FOR KEY SHARE 를 잡는다.
    불러오기가 process 행을 찾으면서 잠가 두면 여기서 막힌다.
    """
    process_id = ProcessRepository(db).get_or_create_id("sf2p", release=release)
    with _import_in_progress(pg_dsn, "sf2p", release):
        start = time.monotonic()
        saved = DeviceRepository(gui_db).upsert_devices(
            process_id, [_device("nfet_b")], actor="gui"
        )
        elapsed = time.monotonic() - start

    assert saved.inserted == 1
    assert elapsed < 0.3, f"{elapsed:.3f}초 기다렸다"


def _wait_for_a_lock_waiter(db, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with db.connection() as conn:
            row = conn.execute(
                "SELECT count(*) AS n FROM pg_stat_activity "
                "WHERE datname = current_database() AND wait_event_type = 'Lock'"
            ).fetchone()
        if row["n"]:
            return
        time.sleep(0.01)
    raise AssertionError("GUI 쪽이 불러오기의 INSERT 를 기다리지 않았다")


def test_two_creators_of_a_new_process_share_one_row(db, pg_dsn):
    """같은 새 이름을 동시에 만들면 process 는 하나이고 둘 다 같은 id 를 얻는다.

    불러오기가 새 process 를 만들고 커밋하기 전에 GUI 가 같은 이름을 고르면
    GUI 는 불러오기가 끝나기를 기다렸다가 그 행을 받는다. GUI 는 만들지
    않았으므로 process 추가 이력을 남기지 않는다.
    """
    importer = psycopg.connect(pg_dsn, row_factory=dict_row)
    try:
        created = IORepository._process_id(importer.cursor(), "sf9z")
        with ThreadPoolExecutor(max_workers=1) as pool:
            chosen = pool.submit(
                ProcessRepository(db).get_or_create_id, "sf9z", actor="gui"
            )
            _wait_for_a_lock_waiter(db)
            importer.commit()
            got = chosen.result(timeout=10)
    finally:
        importer.rollback()
        importer.close()

    assert got == created
    assert ProcessRepository(db).list_all() == ["sf9z"]
    assert AuditRepository(db).recent(limit=10, actor="gui") == []


def test_two_creators_of_a_new_release_share_one_row(db, pg_dsn):
    """같은 새 (이름, 버전)을 두 커넥션이 동시에 만들면 행은 하나이고 둘 다 같은 id 를 얻는다.

    나중 쪽은 먼저 쪽이 커밋할 때까지 INSERT 에서 기다렸다가 그 행을 다시 읽고,
    자기가 만들지 않았다고 답한다. 같은 이름의 빈 버전은 생기지 않는다.
    """
    first = psycopg.connect(pg_dsn, row_factory=dict_row)
    second = psycopg.connect(pg_dsn, row_factory=dict_row)
    try:
        created, made = find_or_create(first.cursor(), "sf9z", "V1")
        with ThreadPoolExecutor(max_workers=1) as pool:
            found = pool.submit(find_or_create, second.cursor(), "sf9z", "V1")
            _wait_for_a_lock_waiter(db)
            first.commit()
            got = found.result(timeout=10)
        second.commit()
    finally:
        for conn in (first, second):
            conn.rollback()
            conn.close()

    assert made is True
    assert got == (created, False)
    repo = ProcessRepository(db)
    assert repo.list_pairs() == [("sf9z", "V1")]
    assert repo.get_id("sf9z", release="V1") == created
    assert repo.get_id("sf9z") is None
