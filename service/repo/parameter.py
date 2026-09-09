from psycopg import sql

from service import schema
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
        query = sql.SQL("SELECT {cols} FROM {tbl} WHERE device_id = %s ORDER BY id").format(
            cols=sql.SQL(", ").join(map(sql.Identifier, columns)),
            tbl=sql.Identifier(table_name),
        )
        with self.db.connection() as conn:
            rows = conn.execute(query, (device_id,)).fetchall()
        return [dict(r) for r in rows]

    def replace_all_for_device(
        self, table_name: str, columns: list[str], device_id: int, rows: list[dict]
    ):
        _check(table_name, columns)
        tbl = sql.Identifier(table_name)
        with self.db.connection() as conn:
            cur = conn.cursor()
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
                    [
                        (device_id, *[r.get(c) or "" for c in columns])
                        for r in rows
                    ],
                )
