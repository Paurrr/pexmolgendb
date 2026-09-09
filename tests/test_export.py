"""genMOLDB 로 나가는 CSV 계약을 고정하는 테스트.

molgen/CSV_COLUMNS.md §0: "로더가 비어 있지 않은 동명 컬럼을 순서대로 모아
하나의 리스트로 만든다" — 즉 자식 행의 순서는 의미를 갖는다.
"""

from genviewer.service.repo.io import IORepository


def test_each_row_carries_its_own_process_name(db, two_processes):
    """device 마다 CdsLibName 은 자기 process 여야 한다.

    회귀 방지: fetch_export_data 의 2패스가 1패스에서 새어나온 process_name
    변수를 읽어서, 모든 행이 마지막 device 의 process 이름을 갖고 있었다.
    """
    headers, rows = IORepository(db).fetch_export_data(two_processes)
    cds = headers.index("CdsLibName")
    inst = headers.index("InstCellName")
    got = {row[inst]: row[cds] for row in rows}
    assert got == {"nfet_b": "sf2p", "pfet_b": "sf4u"}


def test_child_row_order_is_preserved(db, two_processes):
    """InstTerm 컬럼들은 삽입 순서대로 나와야 한다.

    회귀 방지: 자식 테이블 조회에 ORDER BY 가 없었다. SQLite 는 rowid 순서를
    돌려주지만 PostgreSQL 은 heap 순서라서 UPDATE 후 뒤섞인다.
    """
    headers, rows = IORepository(db).fetch_export_data(two_processes)
    inst = headers.index("InstCellName")
    term_cols = [i for i, h in enumerate(headers) if h == "InstTerm"]
    assert len(term_cols) == 4, "device 당 InstTerm 행이 4개이므로 컬럼도 4개여야 한다"

    for row in rows:
        assert [row[i] for i in term_cols] == ["DRN d", "GATE g", "SRC s", "BULK b"], (
            f"{row[inst]} 의 InstTerm 순서가 깨졌다"
        )
