from psycopg import sql

from service import schema
from service.errors import Conflict, StaleWriteError
from service.pool import Database


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
            row = cur.execute(
                "SELECT name, version, updated_by, updated_at FROM device "
                "WHERE id = %s FOR UPDATE",
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

            for table in sorted(payload):  # 결정적 순서
                columns, rows = payload[table]
                tbl = sql.Identifier(table)
                cur.execute(
                    sql.SQL("DELETE FROM {tbl} WHERE device_id = %s").format(tbl=tbl),
                    (device_id,),
                )
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
