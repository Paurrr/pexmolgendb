import sqlite3


class DeviceRepository:
    def __init__(self, conn: sqlite3.Connection | None = None):
        self.conn = conn

    def fetch_devices_by_process(self, process_id: int) -> list[tuple]:
        """
        반환: [(id, process_id, name, celltype, description), ...]
        """
        if not self.conn:
            return []

        cur = self.conn.cursor()
        sql = (
            "SELECT id, process_id, name, celltype, description "
            'FROM device WHERE process_id = ? ORDER BY "order"'
        )
        return cur.execute(sql, (process_id,)).fetchall()

    def upsert_device(self, process_id: int, device: dict[str]) -> dict[str]:
        """device dict에 id가 있으면 UPDATE, 없으면 INSERT. 변경된 dict 반환."""
        if not self.conn:
            return device
        cur = self.conn.cursor()

        if device.get("id") is None:
            cur.execute(
                'INSERT INTO device (process_id, name, celltype, description, "order") '
                "VALUES (?, ?, ?, ?, ?)",
                (
                    process_id,
                    device.get("name"),
                    device.get("celltype"),
                    device.get("description"),
                    device.get("order", 0),
                ),
            )
            device["id"] = cur.lastrowid
        else:
            cur.execute(
                "UPDATE device SET process_id = ?, name = ?, celltype = ?, "
                'description = ?, "order" = ? WHERE id = ?',
                (
                    process_id,
                    device.get("name"),
                    device.get("celltype"),
                    device.get("description"),
                    device.get("order", 0),
                    device["id"],
                ),
            )

        self.conn.commit()
        return device

    def upsert_devices(
        self, process_id: int, devices: list[dict[str]]
    ) -> list[dict[str]]:
        """여러 개를 한 트랜잭션으로 upsert."""
        if not self.conn or not devices:
            return devices
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            # 1️⃣ 현재 DB에 있는 id 목록 가져오기
            cur.execute("SELECT id FROM device WHERE process_id = ?", (process_id,))
            existing_ids = {row[0] for row in cur.fetchall()}

            # 2️⃣ 입력 리스트에서 유지해야 할 id 목록
            given_ids = {d["id"] for d in devices if d.get("id") is not None}

            to_delete = existing_ids - given_ids
            if to_delete:
                cur.execute(
                    f"DELETE FROM device WHERE id IN ({','.join(['?']*len(to_delete))})",
                    tuple(to_delete),
                )

            to_update = [
                (
                    process_id,
                    d.get("name"),
                    d.get("celltype"),
                    d.get("description"),
                    d.get("order", 0),
                    d["id"],
                )
                for d in devices
                if d.get("id") is not None
            ]

            if to_update:
                cur.executemany(
                    'UPDATE device SET process_id=?, name=?, celltype=?, description=?, "order"=? '
                    "WHERE id=?",
                    to_update,
                )

            to_insert = [
                (
                    process_id,
                    d.get("name"),
                    d.get("celltype"),
                    d.get("description"),
                    d.get("order", 0),
                )
                for d in devices
                if d.get("id") is None
            ]
            if to_insert:
                cur.executemany(
                    'INSERT INTO device (process_id, name, celltype, description, "order") '
                    "VALUES (?, ?, ?, ?, ?)",
                    to_insert,
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        return devices