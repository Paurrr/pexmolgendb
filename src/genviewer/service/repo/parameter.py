from psycopg import sql

from genviewer.service import schema
from genviewer.service.errors import Conflict, StaleWriteError
from genviewer.service.pool import Database
from genviewer.service.repo import audit


def _check(table_name: str, columns: list[str]) -> list[str]:
    """테이블/컬럼 이름을 tab_config 기반 allow-list 로 검증한다.

    f-string 보간을 sql.Identifier 로 바꾸면서, 인용과 별개로 화이트리스트도
    둔다. 모르는 테이블이면 KeyError 로 즉시 터진다.
    """
    known = schema.TABLE_COLUMNS[table_name]
    unknown = set(columns) - set(known)
    if unknown:
        raise KeyError(f"{table_name} 에 없는 컬럼: {sorted(unknown)}")
    return columns


class ParameterRepository:
    def __init__(self, db: Database):
        self.db = db

    def fetch_by_device(
        self, table_name: str, columns: list[str], device_id: int
    ) -> list[dict]:
        _check(table_name, columns)
        # ORDER BY id 필수: 탭의 행 순서가 곧 CSV 컬럼 순서다.
        query = sql.SQL(
            "SELECT {cols} FROM {tbl} WHERE device_id = %s ORDER BY id"
        ).format(
            cols=sql.SQL(", ").join(map(sql.Identifier, columns)),
            tbl=sql.Identifier(table_name),
        )
        with self.db.connection() as conn:
            rows = conn.execute(query, (device_id,)).fetchall()
        return [dict(r) for r in rows]

    def replace_many_for_device(
        self,
        device_id: int,
        payload: dict[str, tuple[list[str], list[dict]]],
        *,
        expected_version: int | None = None,
        actor: str = "",
        force: bool = False,
    ) -> int:
        """여러 탭을 한 트랜잭션으로 교체하고 device 의 version 을 한 번만 올린다.

        payload: {table_name: (columns, rows)}

        탭마다 따로 저장하면 안 된다. version 이 device 단위이므로 첫 탭의
        저장이 version 을 올리는 순간 두 번째 탭의 검사가 실패한다 — 두 탭을
        동시에 저장하는 첫 순간 기능이 스스로 깨진다. 게다가 중간에 예외가 나면
        일부만 쓰인 채 남는다.

        반환: 올라간 새 version.
        """
        for table, (columns, _) in payload.items():
            _check(table, columns)

        with self.db.connection() as conn:
            cur = conn.cursor()

            # 부모 행을 잠근다. 같은 device 를 동시에 저장하는 쪽을 직렬화하고,
            # 그 사이 값이 바뀌지 않았음을 보장한다.
            # FOR UPDATE OF d 로 써야 한다. 그냥 FOR UPDATE 면 조인한 process
            # 행까지 잠가서, 같은 process 안의 서로 다른 device 를 편집하는
            # 사람들이 서로를 기다리게 된다.
            row = cur.execute(
                "SELECT d.name, d.version, d.updated_by, d.updated_at, "
                "       p.name AS process_name, p.release AS process_release "
                "FROM device d JOIN process p ON p.id = d.process_id "
                "WHERE d.id = %s FOR UPDATE OF d",
                (device_id,),
            ).fetchone()
            if row is None:
                raise StaleWriteError([Conflict(device_id, "", "deleted")])
            if (
                not force
                and expected_version is not None
                and row["version"] != expected_version
            ):
                raise StaleWriteError(
                    [
                        Conflict(
                            device_id,
                            row["name"],
                            "stale",
                            row["updated_by"],
                            row["updated_at"],
                        )
                    ]
                )

            entries = []
            for table in sorted(payload):  # 결정적 순서
                columns, rows = payload[table]
                tbl = sql.Identifier(table)
                # RETURNING 으로 옛 행을 공짜로 받는다. 지운 뒤에는 무엇이 있었는지
                # 알 수 없고, 별도 SELECT 를 하면 왕복이 하나 더 는다.
                # id 로 정렬해야 fetch_by_device 가 읽어 주던 순서와 같아진다.
                old = cur.execute(
                    sql.SQL(
                        "DELETE FROM {tbl} WHERE device_id = %s RETURNING id, {cols}"
                    ).format(
                        tbl=tbl,
                        cols=sql.SQL(", ").join(map(sql.Identifier, columns)),
                    ),
                    (device_id,),
                ).fetchall()
                before = [
                    {c: r[c] for c in columns}
                    for r in sorted(old, key=lambda r: r["id"])
                ]
                after = [{c: r.get(c) or "" for c in columns} for r in rows]
                entry = audit.tab_change(
                    row["process_name"],
                    row["name"],
                    device_id,
                    table,
                    before,
                    after,
                    process_release=row["process_release"],
                )
                if entry is not None:
                    entries.append(entry)

                if rows:
                    insert = sql.SQL(
                        "INSERT INTO {tbl} (device_id, {cols}) VALUES ({vals})"
                    ).format(
                        tbl=tbl,
                        cols=sql.SQL(", ").join(map(sql.Identifier, columns)),
                        vals=sql.SQL(", ").join(sql.Placeholder() * (len(columns) + 1)),
                    )
                    # psycopg3 에는 Connection.executemany 가 없다. Cursor 로 해야 한다.
                    cur.executemany(
                        insert,
                        [(device_id, *[r.get(c) or "" for c in columns]) for r in rows],
                    )

            new_version = cur.execute(
                "UPDATE device SET version = version + 1, updated_at = now(), "
                "updated_by = %s WHERE id = %s RETURNING version",
                (actor, device_id),
            ).fetchone()["version"]

            # 내용이 달라진 탭만 남는다. 탭 저장은 값이 그대로여도 version 을
            # 올리는데(그래야 다른 화면이 다시 읽는다), 그때까지 이력에 남기면
            # 저장 버튼을 누를 때마다 줄이 쌓여 아무도 안 보게 된다.
            audit.write(cur, actor, entries)

        return new_version

    def replace_all_for_device(
        self,
        table_name: str,
        columns: list[str],
        device_id: int,
        rows: list[dict],
        *,
        expected_version: int | None = None,
        actor: str = "",
        force: bool = False,
    ) -> int:
        """탭 하나만 교체한다. replace_many_for_device 의 얇은 래퍼."""
        return self.replace_many_for_device(
            device_id,
            {table_name: (columns, rows)},
            expected_version=expected_version,
            actor=actor,
            force=force,
        )
