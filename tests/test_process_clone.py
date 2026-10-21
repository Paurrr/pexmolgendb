"""ProcessRepository.clone 의 PostgreSQL 쪽 성질. 가짜와 같은 의미는 contract test 가 본다.

여기서 보는 것은 가짜가 흉내 낼 수 없는 것이다: 한 시점 스냅샷(복제 도중 남이 원본 탭을 저장해도
복사본은 복제를 시작한 시점의 원본이다), 원본을 잠그지 않음, 한 트랜잭션, 이력 한 줄, 바인드
파라미터 상한, 디스크 위 순서가 아니라 id 순서.

복제 도중에 끼어드는 자리는 `_Hooked` 가 만든다. Database 대역이라 clone 이 실행하는 SQL 은 그대로
PostgreSQL 로 가고, 정한 문장이 처음 돈 직후 한 번 콜백을 부른다(같은 트랜잭션 안).
"""

import re
from contextlib import contextmanager

import pytest
from psycopg import sql

from genviewer.service.repo import audit
from genviewer.service.repo.audit import AuditRepository
from genviewer.service.repo.device import DeviceRepository
from genviewer.service.repo.parameter import ParameterRepository
from genviewer.service.repo.process import ProcessRepository
from genviewer.service.schema import TABLE_COLUMNS

TERMS = ["reserved_key", "cds_inst_term_name"]

# libpq 가 한 문장에 보내는 바인드 파라미터 상한.
PARAM_LIMIT = 65_535


def _terms(*pairs):
    return [{"reserved_key": k, "cds_inst_term_name": v} for k, v in pairs]


def _device(name, celltype="NFET", **kw):
    return {"name": name, "celltype": celltype, "description": "", "order": 0, **kw}


class _Cursor:
    def __init__(self, cur, hook: "_Hooked"):
        self._cur = cur
        self._hook = hook

    def execute(self, query, params=None, **kw):
        result = self._cur.execute(query, params, **kw)
        text = query if isinstance(query, str) else query.as_string(self._cur)
        self._hook.seen(text, self._cur.connection)
        return result

    def __getattr__(self, name):
        return getattr(self._cur, name)


class _Connection:
    def __init__(self, conn, hook: "_Hooked"):
        self._conn = conn
        self._hook = hook

    def cursor(self, *args, **kw):
        return _Cursor(self._conn.cursor(*args, **kw), self._hook)

    def execute(self, query, params=None, **kw):
        return self.cursor().execute(query, params, **kw)

    def __getattr__(self, name):
        return getattr(self._conn, name)


class _Hooked:
    """Database 대역. 그 커넥션에서 `when` 에 맞는 문장이 처음 끝난 직후 `then(conn)` 을 부른다.

    conn 은 복제가 쓰는 그 커넥션(같은 트랜잭션)이다. 복제의 커서를 건드리지 않게 conn.execute 로
    새 커서를 쓴다. 남의 일은 콜백 안에서 db 의 다른 커넥션으로 한다.
    """

    def __init__(self, db, when: str, then):
        self._db = db
        self._when = re.compile(when)
        self._then = then
        self.fired = False

    @contextmanager
    def connection(self):
        with self._db.connection() as conn:
            yield _Connection(conn, self)

    def seen(self, text: str, conn) -> None:
        if not self.fired and self._when.match(text.strip()):
            self.fired = True
            self._then(conn)


FIRST_DEVICE_INSERT = r'INSERT\s+INTO\s+"?device"?\s'
HISTORY_INSERT = r'INSERT\s+INTO\s+"?change_log"?\s'


def _seed(db):
    """원본 sf2p V1: device 셋, nfet_a 에 InstTerm 세 행. (process id, {이름: device}) 를 준다."""
    pid = ProcessRepository(db).get_or_create_id("sf2p", release="V1", actor="kim")
    devices = DeviceRepository(db)
    made = {
        name: devices.upsert_device(pid, _device(name, order=order), actor="kim")
        for name, order in [("nfet_b", 0), ("pfet_c", 1), ("nfet_a", 1)]
    }
    ParameterRepository(db).replace_many_for_device(
        made["nfet_a"]["id"],
        {"inst_terms": (TERMS, _terms(("GATE", "g"), ("DRN", "d"), ("SRC", "s")))},
        actor="kim",
    )
    return pid, made


def _copy_of(db, name: str, release: str) -> dict:
    with db.connection() as conn:
        return conn.execute(
            "SELECT d.* FROM device d JOIN process p ON p.id = d.process_id "
            "WHERE p.name = 'sf2p' AND p.release = %s AND d.name = %s",
            (release, name),
        ).fetchone()


def test_a_tab_save_during_a_clone_does_not_reach_the_copy(db):
    """device 를 복사한 뒤 남이 원본 탭을 저장해도 복사본의 탭은 복제를 시작한 시점이다.

    READ COMMITTED 면 탭 행을 읽는 문장이 그 저장 뒤의 값을 봐서 device 와 탭이 다른 시점이 된다.
    남의 저장은 원본 device 를 FOR UPDATE 로 잠그므로, 복제가 원본을 잠갔다면 lock_timeout 으로
    실패한다.
    """
    _, made = _seed(db)
    par = ParameterRepository(db)

    def save_meanwhile(_conn):
        par.replace_many_for_device(
            made["nfet_a"]["id"], {"inst_terms": (TERMS, _terms(("GATE", "바뀜")))}, actor="lee"
        )

    hooked = _Hooked(db, FIRST_DEVICE_INSERT, save_meanwhile)
    assert ProcessRepository(hooked).clone("sf2p", "V1", "sf2p", "V2", actor="tester") == 3

    assert hooked.fired
    assert par.fetch_by_device("inst_terms", TERMS, made["nfet_a"]["id"]) == _terms(
        ("GATE", "바뀜")
    )
    copy = _copy_of(db, "nfet_a", "V2")
    assert par.fetch_by_device("inst_terms", TERMS, copy["id"]) == _terms(
        ("GATE", "g"), ("DRN", "d"), ("SRC", "s")
    )


def test_a_clone_locks_nothing_of_the_source(db):
    """복제가 다 읽고 이력을 쓴 시점에도 원본의 process·device·탭 행을 남이 바로 잠글 수 있다."""
    pid, made = _seed(db)
    tried = []

    def lock_the_source(_conn):
        with db.connection() as conn:
            conn.execute("SELECT 1 FROM process WHERE id = %s FOR UPDATE NOWAIT", (pid,))
            conn.execute("SELECT 1 FROM device WHERE process_id = %s FOR UPDATE NOWAIT", (pid,))
            conn.execute(
                "SELECT 1 FROM inst_terms WHERE device_id = %s FOR UPDATE NOWAIT",
                (made["nfet_a"]["id"],),
            )
        tried.append(True)

    hooked = _Hooked(db, HISTORY_INSERT, lock_the_source)
    assert ProcessRepository(hooked).clone("sf2p", "V1", "sf2p", "V2", actor="tester") == 3
    assert tried == [True]


def test_a_clone_that_fails_midway_leaves_nothing(db):
    _seed(db)
    log = AuditRepository(db)
    before = log.recent(limit=1000)

    def fail(_conn):
        raise RuntimeError("복제 중간 실패")

    with pytest.raises(RuntimeError, match="복제 중간 실패"):
        ProcessRepository(_Hooked(db, FIRST_DEVICE_INSERT, fail)).clone(
            "sf2p", "V1", "sf2p", "V2", actor="tester"
        )

    assert ProcessRepository(db).list_pairs() == [("sf2p", "V1")]
    with db.connection() as conn:
        assert conn.execute("SELECT count(*) AS n FROM device").fetchone()["n"] == 3
        assert conn.execute("SELECT count(*) AS n FROM inst_terms").fetchone()["n"] == 3
    assert log.recent(limit=1000) == before


def test_a_clone_is_one_history_line_naming_its_source(db):
    _seed(db)
    log = AuditRepository(db)
    before = log.recent(limit=1000)

    assert ProcessRepository(db).clone("sf2p", "V1", "sf2p", "V2", actor="tester") == 3

    after = log.recent(limit=1000)
    assert after[: len(before)] == before  # 원본 쪽 이력은 늘지 않는다
    (line,) = after[len(before) :]
    assert {
        k: line[k]
        for k in ("actor", "action", "process_name", "process_release", "device_name", "summary")
    } == {
        "actor": "tester",
        "action": audit.PROCESS_ADD,
        "process_name": "sf2p",
        "process_release": "V2",
        "device_name": "",
        "summary": "process 추가  sf2p V2  (sf2p V1 에서 device 3개 복사)",
    }
    assert line["detail"] == {"source": {"name": "sf2p", "release": "V1"}, "devices": 3}


def test_adding_a_process_keeps_its_old_history_line(db):
    assert ProcessRepository(db).add("sf9z", actor="dh991")
    (line,) = AuditRepository(db).recent(process="sf9z")
    assert (line["summary"], line["detail"], line["process_release"]) == (
        "process 추가  sf9z",
        {},
        "",
    )


def _rows_of(db, table: str, release: str) -> list[tuple]:
    """그 버전의 모든 탭 행을 (device 이름, 값…) 으로. device 순서, 그 안에서 id 순."""
    columns = TABLE_COLUMNS[table]
    query = sql.SQL(
        "SELECT d.name, {cols} FROM {tbl} t "
        "JOIN device d ON d.id = t.device_id JOIN process p ON p.id = d.process_id "
        'WHERE p.name = %s AND p.release = %s ORDER BY d."order", d.id, t.id'
    ).format(
        cols=sql.SQL(", ").join(sql.Identifier("t", c) for c in columns),
        tbl=sql.Identifier(table),
    )
    with db.connection() as conn:
        return [tuple(r.values()) for r in conn.execute(query, ("sf2p", release)).fetchall()]


def test_a_clone_copies_more_rows_than_one_statement_can_bind(db):
    """device 200개, add_fgrs 만 11,000행(값 5 + device_id = 66,000 파라미터)이어도 복사된다."""
    devices, fgr_rows = 200, 55
    fgr_params = len(TABLE_COLUMNS["add_fgrs"]) + 1
    assert devices * fgr_rows * fgr_params > PARAM_LIMIT

    pid = ProcessRepository(db).get_or_create_id("sf2p", release="V1")
    with db.connection() as conn:
        conn.execute(
            'INSERT INTO device (process_id, name, celltype, "order") '
            "SELECT %s, 'dev' || lpad(g::text, 3, '0'), 'NFET', g / 2 "
            "FROM generate_series(0, %s) g ORDER BY g",
            (pid, devices - 1),
        )
        for table, columns in TABLE_COLUMNS.items():
            conn.execute(
                sql.SQL(
                    "INSERT INTO {tbl} (device_id, {cols}) SELECT d.id, {vals} "
                    "FROM device d CROSS JOIN generate_series(1, %s) g "
                    "WHERE d.process_id = %s ORDER BY d.id, g DESC"
                ).format(
                    tbl=sql.Identifier(table),
                    cols=sql.SQL(", ").join(map(sql.Identifier, columns)),
                    vals=sql.SQL(", ").join(
                        sql.SQL("{} || '-' || d.id || '-' || g").format(sql.Literal(c))
                        for c in columns
                    ),
                ),
                (fgr_rows if table == "add_fgrs" else 2, pid),
            )

    assert ProcessRepository(db).clone("sf2p", "V1", "sf2p", "V2", actor="tester") == devices

    for table in TABLE_COLUMNS:
        source = _rows_of(db, table, "V1")
        assert len(source) == devices * (fgr_rows if table == "add_fgrs" else 2)
        assert _rows_of(db, table, "V2") == source, table


def _without_index_scans(conn) -> None:
    """이 트랜잭션에서 (device_id, id) 인덱스 순서로 읽는 플랜을 끈다.

    큰 테이블에서 플래너가 고르는 순차 스캔·비트맵 힙 스캔은 행이 테이블에 놓인 순서로 돌려준다.
    작은 테스트 테이블에서도 그 경우를 만들려고 쓴다.
    """
    conn.execute("SET LOCAL enable_indexscan = off")
    conn.execute("SET LOCAL enable_indexonlyscan = off")


def test_tab_rows_are_copied_in_id_order_not_in_the_order_the_table_holds_them(db):
    """id 를 정해 넣어 테이블에 놓인 순서(SRC, GATE, DRN)를 id 순서(GATE, DRN, SRC)와 다르게."""
    _, made = _seed(db)
    nfet_a = made["nfet_a"]["id"]
    placed = [(900_003, "SRC", "s"), (900_001, "GATE", "g"), (900_002, "DRN", "d")]
    with db.connection() as conn:
        conn.execute("DELETE FROM inst_terms WHERE device_id = %s", (nfet_a,))
        for row_id, key, value in placed:
            conn.execute(
                "INSERT INTO inst_terms (id, device_id, reserved_key, cds_inst_term_name) "
                "VALUES (%s, %s, %s, %s)",
                (row_id, nfet_a, key, value),
            )
    # 전제: ORDER BY 없이 읽으면 놓인 순서다.
    with db.connection() as conn:
        _without_index_scans(conn)
        held = conn.execute(
            "SELECT reserved_key FROM inst_terms WHERE device_id = ANY(%s)", ([nfet_a],)
        ).fetchall()
    assert [r["reserved_key"] for r in held] == ["SRC", "GATE", "DRN"]

    hooked = _Hooked(db, r"SELECT\s", _without_index_scans)
    assert ProcessRepository(hooked).clone("sf2p", "V1", "sf2p", "V2", actor="tester") == 3

    assert hooked.fired
    copy = _copy_of(db, "nfet_a", "V2")
    assert ParameterRepository(db).fetch_by_device("inst_terms", TERMS, copy["id"]) == _terms(
        ("GATE", "g"), ("DRN", "d"), ("SRC", "s")
    )


def test_a_clone_of_an_existing_pair_is_a_unique_violation_turned_into_none(db):
    """대상이 있으면 None. 그 사이 다른 트랜잭션이 만든 쌍도 같은 길(UniqueViolation)이다."""
    _seed(db)
    other = []

    def someone_creates_it(_conn):
        # 복제의 process INSERT 보다 먼저 커밋되게 원본을 읽은 직후 만든다.
        assert ProcessRepository(db).add("sf2p", release="V2", actor="lee")
        other.append(True)

    hooked = _Hooked(db, r"SELECT\s", someone_creates_it)
    assert ProcessRepository(hooked).clone("sf2p", "V1", "sf2p", "V2", actor="tester") is None
    assert other == [True]
    assert ProcessRepository(db).count_devices("sf2p", release="V2") == 0
