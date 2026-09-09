"""기존 .sqlite 파일 이관 검증.

픽스처는 저장소에 있는 db/init.sqlite — 실제로 쓰이던 레거시 파일이다.
"""

import sqlite3
from pathlib import Path

import pytest

from genviewer.scripts import import_sqlite

LEGACY = Path(__file__).resolve().parent.parent / "db" / "init.sqlite"


def _counts(path: Path) -> dict[str, int]:
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        return {
            t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            for t in ("process", "device", "inst_terms")
        }
    finally:
        conn.close()


def test_legacy_file_passes_validation():
    conn = import_sqlite.open_readonly(LEGACY)
    try:
        assert import_sqlite.validate(conn) == []
        assert import_sqlite.duplicate_devices(conn) == []
    finally:
        conn.close()


def test_import_moves_every_row(db, pg_dsn):
    import_sqlite.import_file(LEGACY, pg_dsn, "fail", "", dry_run=False)

    expected = _counts(LEGACY)
    with db.connection() as conn:
        for table, want in expected.items():
            got = conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
            assert got == want, f"{table}: {got} != {want}"


def test_import_preserves_devices_and_order(db, pg_dsn):
    import_sqlite.import_file(LEGACY, pg_dsn, "fail", "", dry_run=False)

    src = sqlite3.connect(f"file:{LEGACY.as_posix()}?mode=ro", uri=True)
    try:
        want = src.execute(
            'SELECT p.name, d.name, d.celltype, d.description, d."order" '
            "FROM device d JOIN process p ON p.id = d.process_id "
            'ORDER BY p.name, d."order"'
        ).fetchall()
    finally:
        src.close()

    with db.connection() as conn:
        got = [
            (r["pname"], r["dname"], r["celltype"], r["description"], r["order"])
            for r in conn.execute(
                'SELECT p.name AS pname, d.name AS dname, d.celltype, '
                '       d.description, d."order" '
                "FROM device d JOIN process p ON p.id = d.process_id "
                'ORDER BY p.name, d."order"'
            )
        ]
    # 원본의 NULL description 은 "" 로 옮겨진다 (PG 컬럼이 NOT NULL DEFAULT '').
    assert got == [(a, b, c, d or "", e) for a, b, c, d, e in want]


def test_rename_policy_keeps_both(db, pg_dsn):
    import_sqlite.import_file(LEGACY, pg_dsn, "fail", "", dry_run=False)
    import_sqlite.import_file(LEGACY, pg_dsn, "rename", "@bob", dry_run=False)

    with db.connection() as conn:
        names = {r["name"] for r in conn.execute("SELECT name FROM process")}
    assert "sf2p" in names and "sf2p@bob" in names


def test_fail_policy_refuses_a_collision(db, pg_dsn):
    import_sqlite.import_file(LEGACY, pg_dsn, "fail", "", dry_run=False)
    with pytest.raises(SystemExit):
        import_sqlite.import_file(LEGACY, pg_dsn, "fail", "", dry_run=False)


def test_merge_policy_does_not_duplicate(db, pg_dsn):
    import_sqlite.import_file(LEGACY, pg_dsn, "fail", "", dry_run=False)
    before = _counts(LEGACY)
    import_sqlite.import_file(LEGACY, pg_dsn, "merge", "", dry_run=False)

    with db.connection() as conn:
        for table, want in before.items():
            got = conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
            assert got == want, f"{table} 이 merge 후 늘어났다: {got} != {want}"
