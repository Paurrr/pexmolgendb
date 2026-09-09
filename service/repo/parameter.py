import sqlite3


class ParameterRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def fetch_by_device(
        self, table_name: str, columns: list[str], device_id: int
    ) -> list[dict]:
        cur = self.conn.cursor()
        cols = ", ".join(columns)
        sql = f"SELECT {cols} FROM {table_name} WHERE device_id=?"
        cur.execute(sql, (device_id,))
        rows = cur.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def replace_all_for_device(
        self, table_name: str, columns: list[str], device_id: int, rows: list[dict]
    ):
        with self.conn:
            self.conn.execute(
                f"DELETE FROM {table_name} WHERE device_id=?", (device_id,)
            )
            placeholders = ", ".join(["?"] * (len(columns) + 1))
            sql = f"INSERT INTO {table_name} (device_id, {', '.join(columns)}) VALUES ({placeholders})"
            data = [(device_id, *[row.get(c, "") for c in columns]) for row in rows]
            if data:
                self.conn.executemany(sql, data)