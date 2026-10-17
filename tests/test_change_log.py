"""변경 이력이 무엇을 남기고 무엇을 남기지 않는지.

이 파일이 지키는 성질은 넷이다.

  1. 사람이 실제로 바꾼 것만 남는다. 손대지 않은 저장은 한 줄도 남기지 않는다 -
     여기가 무너지면 Save 를 누를 때마다 수십 줄이 쌓여 이력이 못 쓰게 된다.
  2. 실패한 저장은 아무것도 남기지 않는다. 이력은 저장과 같은 트랜잭션이다.
  3. 지워진 것의 이력이 함께 지워지지 않는다. change_log 에 외래키가 없는 이유다.
  4. 이전 값과 이후 값이 둘 다 남는다. "무엇이 어떻게" 에 답할 수 있어야 한다.
"""

from datetime import UTC, datetime, timedelta

import pytest

from genviewer.service.errors import StaleWriteError
from genviewer.service.repo import audit
from genviewer.service.repo.audit import AuditRepository
from genviewer.service.repo.device import DeviceRepository
from genviewer.service.repo.io import IORepository
from genviewer.service.repo.parameter import ParameterRepository
from genviewer.service.repo.process import ProcessRepository

TERM_COLUMNS = ["reserved_key", "cds_inst_term_name"]


@pytest.fixture
def log(db):
    return AuditRepository(db)


@pytest.fixture
def process_id(db):
    return ProcessRepository(db).get_or_create_id("sf2p", actor="관리자")


def _device(name="nfet_b", celltype="NFET", **kw):
    return {"name": name, "celltype": celltype, "description": "", "order": 0, **kw}


def _rows(log, **kw):
    return log.recent(limit=100, **kw)


def _terms(pairs):
    return [{"reserved_key": k, "cds_inst_term_name": v} for k, v in pairs]


# ---------------------------------------------------------------------------
# device
# ---------------------------------------------------------------------------


def test_adding_a_device_is_recorded_with_who_and_where(db, log, process_id):
    DeviceRepository(db).upsert_devices(process_id, [_device()], actor="dh991")

    (row,) = _rows(log, actor="dh991")
    assert row["action"] == audit.INSERT
    assert (row["process_name"], row["device_name"]) == ("sf2p", "nfet_b")
    assert row["detail"]["after"]["celltype"] == "NFET"
    assert "nfet_b" in row["summary"]


def test_an_edit_records_only_the_columns_that_changed(db, log, process_id):
    repo = DeviceRepository(db)
    (dev,) = repo.upsert_devices(process_id, [_device()], actor="dh991").devices
    repo.upsert_devices(
        process_id, [{**dev, "description": "ESD 용"}], actor="jyk"
    )

    row = _rows(log, actor="jyk")[-1]
    assert row["action"] == audit.UPDATE
    # name/celltype/order 는 그대로였다. 담기면 안 된다.
    assert set(row["detail"]["after"]) == {"description"}
    assert row["detail"]["before"]["description"] == ""
    assert row["detail"]["after"]["description"] == "ESD 용"


def test_a_save_that_changes_nothing_records_nothing(db, log, process_id):
    """save_all 은 화면의 device 를 전부 보낸다. 그게 전부 이력이 되면 안 된다.

    이력의 값어치가 통째로 여기 달려 있다. 저장할 때마다 줄이 쌓이면 사람은
    이력을 보지 않게 되고, 그러면 있으나 마나다.
    """
    repo = DeviceRepository(db)
    saved = repo.upsert_devices(
        process_id, [_device("a"), _device("b"), _device("c")], actor="dh991"
    )
    before = len(_rows(log))

    repo.upsert_devices(process_id, [dict(d) for d in saved.devices], actor="dh991")
    assert len(_rows(log)) == before, "손대지 않은 저장이 이력을 남겼다"


def test_only_the_touched_row_is_recorded(db, log, process_id):
    repo = DeviceRepository(db)
    saved = repo.upsert_devices(
        process_id, [_device("a"), _device("b"), _device("c")], actor="dh991"
    )
    payload = [dict(d) for d in saved.devices]
    payload[1]["celltype"] = "PFET"

    repo.upsert_devices(process_id, payload, actor="jyk")

    rows = _rows(log, actor="jyk")
    assert len(rows) == 1
    assert rows[0]["device_name"] == "b"


def test_a_failed_save_records_nothing(db, log, process_id):
    """StaleWriteError 는 트랜잭션을 통째로 되돌린다. 이력도 함께 사라져야 한다."""
    repo = DeviceRepository(db)
    (dev,) = repo.upsert_devices(process_id, [_device()], actor="dh991").devices
    stale = dict(dev)
    repo.upsert_devices(process_id, [{**dev, "description": "먼저"}], actor="A")
    before = len(_rows(log))

    with pytest.raises(StaleWriteError):
        repo.upsert_devices(process_id, [{**stale, "description": "나중"}], actor="B")

    assert len(_rows(log)) == before
    assert not _rows(log, actor="B")


def test_deleting_a_device_keeps_what_disappeared(db, log, process_id):
    dev_repo = DeviceRepository(db)
    par = ParameterRepository(db)
    (dev,) = dev_repo.upsert_devices(process_id, [_device()], actor="dh991").devices
    version = par.replace_all_for_device(
        "inst_terms",
        TERM_COLUMNS,
        dev["id"],
        _terms([("DRN", "d"), ("GATE", "g")]),
        expected_version=dev["version"],
        actor="dh991",
    )

    dev_repo.upsert_devices(
        process_id, [], deleted={dev["id"]: version}, actor="jyk"
    )

    row = _rows(log, actor="jyk")[-1]
    assert row["action"] == audit.DELETE
    assert row["detail"]["before"]["name"] == "nfet_b"
    # cascade 로 함께 사라진 자식 행이 통째로 남아 있어야 한다.
    assert row["detail"]["children"]["inst_terms"] == _terms(
        [("DRN", "d"), ("GATE", "g")]
    )


def test_the_history_of_a_deleted_device_survives(db, log, process_id):
    """change_log 에 외래키를 걸지 않는 이유가 이 테스트다.

    걸었다면 device 가 사라질 때 ON DELETE CASCADE 가 그 device 의 이력까지
    지운다 - 사람이 가장 보고 싶어 하는 바로 그것을.
    """
    repo = DeviceRepository(db)
    (dev,) = repo.upsert_devices(process_id, [_device()], actor="dh991").devices
    # 고친 뒤의 version 으로 지워야 한다. 사본을 보냈으므로 dev 는 옛 값이다.
    (dev,) = repo.upsert_devices(
        process_id, [{**dev, "description": "고침"}], actor="dh991"
    ).devices

    repo.upsert_devices(process_id, [], deleted={dev["id"]: dev["version"]}, actor="jyk")

    actions = [r["action"] for r in _rows(log, device="nfet_b")]
    assert actions == [audit.INSERT, audit.UPDATE, audit.DELETE]


def test_a_single_upsert_records_an_insert_then_an_update(db, log, process_id):
    """붙여넣기와 Insert 다이얼로그가 지나는 길이다."""
    repo = DeviceRepository(db)
    made = repo.upsert_device(process_id, _device(), actor="dh991")
    repo.upsert_device(
        process_id, {**made, "celltype": "PFET"}, actor="jyk"
    )

    rows = _rows(log, device="nfet_b")
    assert [r["action"] for r in rows] == [audit.INSERT, audit.UPDATE]
    assert rows[1]["detail"]["after"] == {"celltype": "PFET"}


def test_updating_a_device_someone_else_deleted_records_nothing(db, log, process_id):
    """행이 없으면 UPDATE 가 아무것도 못 맞춘다. 일어나지 않은 일을 남기면 안 된다."""
    repo = DeviceRepository(db)
    made = repo.upsert_device(process_id, _device(), actor="dh991")
    with db.connection() as conn:
        conn.execute("DELETE FROM device WHERE id = %s", (made["id"],))
    before = len(_rows(log))

    repo.upsert_device(process_id, {**made, "description": "사라진 것"}, actor="jyk")
    assert len(_rows(log)) == before


# ---------------------------------------------------------------------------
# 탭 (자식 테이블)
# ---------------------------------------------------------------------------


def test_a_tab_save_records_before_and_after_in_order(db, log, process_id):
    dev_repo = DeviceRepository(db)
    par = ParameterRepository(db)
    (dev,) = dev_repo.upsert_devices(process_id, [_device()], actor="dh991").devices

    order = [("DRN", "d"), ("GATE", "g"), ("SRC", "s")]
    version = par.replace_all_for_device(
        "inst_terms",
        TERM_COLUMNS,
        dev["id"],
        _terms(order),
        expected_version=dev["version"],
        actor="dh991",
    )
    par.replace_all_for_device(
        "inst_terms",
        TERM_COLUMNS,
        dev["id"],
        _terms(order[:2]),
        expected_version=version,
        actor="jyk",
    )

    row = _rows(log, actor="jyk")[-1]
    assert row["action"] == audit.TAB
    assert row["table_name"] == "inst_terms"
    # 행 순서가 곧 CSV 컬럼 순서다. 뒤집혀 기록되면 이력이 거짓말을 한다.
    assert row["detail"]["before"] == _terms(order)
    assert row["detail"]["after"] == _terms(order[:2])
    assert "3행 -> 2행" in row["summary"]


def test_a_tab_save_with_the_same_content_records_nothing(db, log, process_id):
    """탭 저장은 값이 같아도 version 을 올린다(다른 화면이 다시 읽어야 하니까).

    그 version 증가까지 이력에 남기면, 저장 버튼 한 번에 탭 수만큼 줄이 쌓인다.
    """
    dev_repo = DeviceRepository(db)
    par = ParameterRepository(db)
    (dev,) = dev_repo.upsert_devices(process_id, [_device()], actor="dh991").devices

    rows = _terms([("DRN", "d")])
    version = par.replace_all_for_device(
        "inst_terms", TERM_COLUMNS, dev["id"], rows,
        expected_version=dev["version"], actor="dh991",
    )
    before = len(_rows(log))

    par.replace_all_for_device(
        "inst_terms", TERM_COLUMNS, dev["id"], rows,
        expected_version=version, actor="dh991",
    )
    assert len(_rows(log)) == before


def test_only_the_changed_tab_is_recorded(db, log, process_id):
    dev_repo = DeviceRepository(db)
    par = ParameterRepository(db)
    (dev,) = dev_repo.upsert_devices(process_id, [_device()], actor="dh991").devices

    payload = {
        "inst_terms": (TERM_COLUMNS, _terms([("DRN", "d")])),
        "suffix_cell_name": (["suffix_cell_name"], [{"suffix_cell_name": "_x"}]),
    }
    version = par.replace_many_for_device(
        dev["id"], payload, expected_version=dev["version"], actor="dh991"
    )

    # inst_terms 만 고치고 둘 다 보낸다 - 화면 저장이 늘 그렇게 한다.
    payload["inst_terms"] = (TERM_COLUMNS, _terms([("DRN", "dd")]))
    par.replace_many_for_device(
        dev["id"], payload, expected_version=version, actor="jyk"
    )

    rows = _rows(log, actor="jyk")
    assert [r["table_name"] for r in rows] == ["inst_terms"]


# ---------------------------------------------------------------------------
# process
# ---------------------------------------------------------------------------


def test_creating_a_process_is_recorded_once(db, log):
    repo = ProcessRepository(db)
    repo.get_or_create_id("sf4u", actor="dh991")
    # 이미 있는 것을 다시 고르는 것은 사건이 아니다. 새로 만들었을 때만
    # 남기지 않으면 process 를 고를 때마다 "process 추가" 가 쌓인다.
    repo.get_or_create_id("sf4u", actor="dh991")
    repo.get_or_create_id("sf4u", actor="jyk")

    rows = _rows(log, process="sf4u")
    assert [r["action"] for r in rows] == [audit.PROCESS_ADD]
    assert rows[0]["actor"] == "dh991"


def test_deleting_a_process_keeps_everything_it_took_with_it(db, log, process_id):
    dev_repo = DeviceRepository(db)
    par = ParameterRepository(db)
    dev, _ = dev_repo.upsert_devices(
        process_id, [_device("nfet_b"), _device("pfet_b", "PFET")], actor="dh991"
    ).devices
    par.replace_all_for_device(
        "inst_terms",
        TERM_COLUMNS,
        dev["id"],
        _terms([("DRN", "d")]),
        expected_version=dev["version"],
        actor="dh991",
    )

    assert ProcessRepository(db).delete("sf2p", actor="jyk")

    row = _rows(log, actor="jyk")[-1]
    assert row["action"] == audit.PROCESS_DELETE
    assert row["detail"]["truncated"] is False
    names = [d["name"] for d in row["detail"]["devices"]]
    assert sorted(names) == ["nfet_b", "pfet_b"]
    kept = next(d for d in row["detail"]["devices"] if d["name"] == "nfet_b")
    assert kept["children"]["inst_terms"] == _terms([("DRN", "d")])


def test_adding_a_process_by_name_is_recorded(db, log):
    assert ProcessRepository(db).add("sf9z", actor="dh991")
    (row,) = _rows(log, process="sf9z")
    assert row["action"] == audit.PROCESS_ADD
    assert row["actor"] == "dh991"


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def _devices_csv(tmp_path) -> str:
    csv_path = tmp_path / "devices.csv"
    csv_path.write_text(
        "CdsLibName,InstCellName,CellType\n"
        "sf2p,nfet_b,NFET\n"
        "sf2p,pfet_b,PFET\n"
        "sf4u,nfet_x,NFET\n",
        encoding="utf-8",
    )
    return str(csv_path)


def _process_adds(rows):
    return [r for r in rows if r["action"] == audit.PROCESS_ADD]


def test_a_csv_import_is_one_line_plus_one_per_new_process(db, log, tmp_path):
    created = IORepository(db).import_data(_devices_csv(tmp_path), actor="dh991")
    assert created == 3

    rows = _rows(log, actor="dh991")
    # device 3개를 3줄로 남기지 않는다. 임포트는 한 사건이다.
    (imported,) = [r for r in rows if r["action"] == audit.IMPORT]
    assert imported["detail"]["processes"] == {"sf2p": 2, "sf4u": 1}
    assert "devices.csv" in imported["summary"]
    # 불러오기가 새로 만든 process 는 따로 한 줄씩 남는다. 만든 다음 불러왔다.
    added = _process_adds(rows)
    assert [r["process_name"] for r in added] == ["sf2p", "sf4u"]
    assert all(r["id"] < imported["id"] for r in added)
    assert len(rows) == 3

    with db.connection() as conn:
        who = conn.execute("SELECT DISTINCT updated_by FROM device").fetchall()
    assert [r["updated_by"] for r in who] == ["dh991"]


def test_a_csv_import_records_only_the_processes_it_created(db, log, tmp_path):
    ProcessRepository(db).add("sf2p", actor="관리자")
    IORepository(db).import_data(_devices_csv(tmp_path), actor="dh991")

    mine = _process_adds(_rows(log, actor="dh991"))
    assert [r["process_name"] for r in mine] == ["sf4u"]
    sf2p = _process_adds(_rows(log, process="sf2p"))
    assert [r["actor"] for r in sf2p] == ["관리자"]


def test_importing_the_same_file_again_adds_no_process_line(db, log, tmp_path):
    path = _devices_csv(tmp_path)
    io = IORepository(db)
    io.import_data(path, actor="dh991")
    io.import_data(path, actor="dh991")

    rows = _rows(log, actor="dh991")
    assert [r["action"] for r in rows] == [
        audit.PROCESS_ADD,
        audit.PROCESS_ADD,
        audit.IMPORT,
        audit.IMPORT,
    ]


def test_a_failed_import_records_nothing(db, log, tmp_path):
    """process 를 만든 뒤 InstCellName 이 없어 실패한다. 이력도 같이 롤백된다."""
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("CellType,CdsLibName\nNFET,sf9z\n", encoding="utf-8")

    with pytest.raises(KeyError):
        IORepository(db).import_data(str(csv_path), actor="dh991")

    assert ProcessRepository(db).list_all() == []
    assert _rows(log) == []


# ---------------------------------------------------------------------------
# 한 번에 많이 (K9)
# ---------------------------------------------------------------------------

# 한 줄에 바인드 파라미터 9개. 7,282 × 9 = 65,538 로 한 문장의 상한(65,535)을 넘는다.
_OVER_THE_LIMIT = 7_282


def test_more_lines_than_one_statement_can_bind_are_all_kept(db):
    entries = [audit.process_add(f"p{i}") for i in range(_OVER_THE_LIMIT)]
    with db.connection() as conn:
        audit.write(conn.cursor(), "bulk", entries)

    with db.connection() as conn:
        rows = conn.execute(
            "SELECT actor, process_name FROM change_log ORDER BY id"
        ).fetchall()
    # 순서도 지킨다. 나중에 쓴 줄의 id 가 크다.
    assert [r["process_name"] for r in rows] == [e.process_name for e in entries]
    assert {r["actor"] for r in rows} == {"bulk"}


def test_a_large_write_is_rolled_back_with_the_save(db):
    """나눠 쓰더라도 저장 하나는 트랜잭션 하나다. 실패하면 한 줄도 남지 않는다."""
    entries = [audit.process_add(f"p{i}") for i in range(_OVER_THE_LIMIT)]
    with pytest.raises(RuntimeError), db.connection() as conn:
        audit.write(conn.cursor(), "bulk", entries)
        raise RuntimeError("저장의 다음 단계가 실패했다")

    with db.connection() as conn:
        n = conn.execute("SELECT count(*) AS n FROM change_log").fetchone()["n"]
    assert n == 0


# ---------------------------------------------------------------------------
# 읽기와 정리
# ---------------------------------------------------------------------------


def test_filters_narrow_the_result(db, log, process_id):
    repo = DeviceRepository(db)
    repo.upsert_devices(process_id, [_device("a")], actor="dh991")
    repo.upsert_devices(process_id, [_device("b")], actor="jyk")

    assert [r["device_name"] for r in _rows(log, actor="jyk")] == ["b"]
    assert [r["device_name"] for r in _rows(log, device="a")] == ["a"]
    assert len(_rows(log, process="sf2p")) >= 2
    assert _rows(log, process="없는것") == []


def test_find_reaches_into_the_changed_values(db, log, process_id):
    repo = DeviceRepository(db)
    (dev,) = repo.upsert_devices(process_id, [_device()], actor="dh991").devices
    repo.upsert_devices(
        process_id, [{**dev, "description": "희귀한말"}], actor="dh991"
    )

    rows = _rows(log, contains="희귀한말")
    assert len(rows) == 1
    assert rows[0]["action"] == audit.UPDATE


def test_recent_returns_the_newest_rows_oldest_first(db, log, process_id):
    repo = DeviceRepository(db)
    for i in range(5):
        repo.upsert_devices(process_id, [_device(f"d{i}")], actor="dh991")

    rows = log.recent(limit=3)
    assert [r["device_name"] for r in rows] == ["d2", "d3", "d4"]
    assert rows == sorted(rows, key=lambda r: r["id"])


def test_purge_removes_only_what_is_older(db, log, process_id):
    DeviceRepository(db).upsert_devices(process_id, [_device()], actor="dh991")
    kept = len(_rows(log))
    assert kept

    long_ago = datetime.now() - timedelta(days=365)
    assert log.count_before(long_ago) == 0
    assert log.purge(long_ago) == 0
    assert len(_rows(log)) == kept

    tomorrow = datetime.now() + timedelta(days=1)
    assert log.count_before(tomorrow) == kept
    assert log.purge(tomorrow) == kept
    assert _rows(log) == []


def _other_timezone() -> str:
    """클라이언트 로컬과 다른 TimeZone. 같으면 naive 시각의 어긋남이 드러나지 않는다."""
    return "UTC" if datetime.now().astimezone().utcoffset() else "Asia/Seoul"


@pytest.fixture
def other_tz_db(db, pg_dsn, monkeypatch):
    """세션 TimeZone 이 클라이언트 로컬과 다른 Database. db 가 테이블을 비운 뒤에 연다.

    PGTZ 는 libpq 가 접속할 때 TimeZone 으로 보낸다. 환경변수라 테스트가 끝나면
    monkeypatch 가 되돌리고, DB 수준 설정은 건드리지 않는다.
    """
    from genviewer.service.config import load_config
    from genviewer.service.pool import Database

    tz = _other_timezone()
    monkeypatch.setenv("PGTZ", tz)
    database = Database(load_config(pg_dsn))
    try:
        with database.connection() as conn:
            # 전제가 깨지면(세션 TZ 가 로컬과 같으면) 아래 테스트는 헛되이 통과한다.
            assert conn.execute("SHOW TimeZone").fetchone()["TimeZone"] == tz
        yield database
    finally:
        database.close()


@pytest.mark.parametrize("aware", [False, True], ids=["naive", "aware"])
def test_time_filters_use_the_client_clock_not_the_server_session(other_tz_db, aware):
    """log --since/--purge-before 와 History 기간은 클라이언트 시각으로 고른다 (K6).

    cli._parse_when 과 history_tab._since 는 naive 로컬 시각을 넘긴다. 그대로
    바인드하면 서버가 세션 TimeZone 으로 읽어서, KST 클라이언트와 UTC 세션이면
    9시간 어긋난다(--since 1h 가 비고, --purge-before 가 방금 쓴 줄을 지운다).
    """
    ProcessRepository(other_tz_db).add("sf9z", actor="tz")
    repo = AuditRepository(other_tz_db)

    def minutes_from_now(n):
        if aware:
            return datetime.now(UTC) + timedelta(minutes=n)
        return datetime.now() + timedelta(minutes=n)

    assert [r["process_name"] for r in repo.recent(since=minutes_from_now(-1))] == [
        "sf9z"
    ]
    assert repo.recent(until=minutes_from_now(-1)) == []
    assert [r["process_name"] for r in repo.recent(until=minutes_from_now(1))] == [
        "sf9z"
    ]
    assert repo.count_before(minutes_from_now(-1)) == 0
    assert repo.purge(minutes_from_now(-1)) == 0
    assert [r["process_name"] for r in repo.recent()] == ["sf9z"]
    assert repo.count_before(minutes_from_now(1)) == 1


def test_the_source_is_recorded(db, log, process_id):
    audit.set_source("테스트")
    try:
        DeviceRepository(db).upsert_devices(process_id, [_device()], actor="dh991")
    finally:
        audit.set_source("")

    assert _rows(log, actor="dh991")[-1]["source"] == "테스트"
