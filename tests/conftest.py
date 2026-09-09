"""SQLite 기반 테스트 픽스처.

Phase 4 에서 PostgreSQL 로 넘어가면 conn 픽스처만 교체하면 되도록,
테스트는 repo 의 공개 API 만 사용한다.
"""

import sqlite3

import pytest

from service.schema import sqlite_all_ddl


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.execute("PRAGMA foreign_keys = ON;")
    for stmt in sqlite_all_ddl():
        c.execute(stmt)
    yield c
    c.close()


@pytest.fixture
def two_processes(conn):
    """process 2개, 각각 device 1개, 자식 행은 순서가 의미를 갖도록 여러 개.

    반환: fetch_export_data 가 받는 형태의 device_info 리스트.
    """
    cur = conn.cursor()
    info = []
    for pname, dname, celltype in [("sf2p", "nfet_b", "NFET"), ("sf4u", "pfet_b", "PFET")]:
        cur.execute("INSERT INTO process (name) VALUES (?)", (pname,))
        pid = cur.lastrowid
        cur.execute(
            'INSERT INTO device (process_id, name, celltype, description, "order") '
            "VALUES (?, ?, ?, ?, ?)",
            (pid, dname, celltype, "", 0),
        )
        did = cur.lastrowid
        # 순서가 뒤섞였는지 확인할 수 있도록 알파벳 역순으로 넣는다.
        for key, term in [("DRN", "d"), ("GATE", "g"), ("SRC", "s"), ("BULK", "b")]:
            cur.execute(
                "INSERT INTO inst_terms (device_id, reserved_key, cds_inst_term_name) "
                "VALUES (?, ?, ?)",
                (did, key, term),
            )
        info.append(
            {"id": did, "process_id": pid, "process_name": pname,
             "name": dname, "celltype": celltype}
        )
    conn.commit()
    return info
