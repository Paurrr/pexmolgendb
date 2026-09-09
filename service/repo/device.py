from service.pool import Database

# 모델과 주고받는 device dict 의 필드. version 은 아직 읽기만 한다
# (낙관적 잠금은 다음 단계).
DEVICE_FIELDS = ("id", "process_id", "name", "celltype", "description", "order", "version")


class DeviceRepository:
    def __init__(self, db: Database):
        self.db = db

    def fetch_devices_by_process(self, process_id: int) -> list[dict]:
        """반환: [{id, process_id, name, celltype, description, order, version}, ...]

        SQLite 시절에는 튜플이었다. version 이 붙으면서 위치 언패킹은 유지보수가
        어려워지므로 dict 로 바꿨다.

        ORDER BY "order", id: "order" 만으로는 전순서가 아니라서 값이 같은
        device 들의 순서가 불확정이 된다.
        """
        with self.db.connection() as conn:
            rows = conn.execute(
                'SELECT id, process_id, name, celltype, description, "order", version '
                'FROM device WHERE process_id = %s ORDER BY "order", id',
                (process_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def upsert_device(self, process_id: int, device: dict) -> dict:
        """id 가 있으면 UPDATE, 없으면 INSERT. 변경된 dict 반환."""
        with self.db.connection() as conn:
            if device.get("id") is None:
                row = conn.execute(
                    "INSERT INTO device (process_id, name, celltype, description, \"order\") "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING id, version",
                    (
                        process_id,
                        device.get("name"),
                        device.get("celltype"),
                        device.get("description") or "",
                        device.get("order", 0),
                    ),
                ).fetchone()
                device["id"] = row["id"]
                device["version"] = row["version"]
            else:
                row = conn.execute(
                    'UPDATE device SET process_id = %s, name = %s, celltype = %s, '
                    'description = %s, "order" = %s WHERE id = %s RETURNING version',
                    (
                        process_id,
                        device.get("name"),
                        device.get("celltype"),
                        device.get("description") or "",
                        device.get("order", 0),
                        device["id"],
                    ),
                ).fetchone()
                if row:
                    device["version"] = row["version"]
        return device

    def upsert_devices(self, process_id: int, devices: list[dict]) -> list[dict]:
        """여러 개를 한 트랜잭션으로 upsert.

        NOTE: 화면에 없는 device 를 전부 지우는 기존 동작을 그대로 옮긴 것이다.
        여러 사람이 동시에 편집하면 남의 작업이 사라진다. 다음 단계에서
        명시적 deleted_ids + 낙관적 잠금으로 교체한다.
        """
        if not devices:
            return devices

        with self.db.connection() as conn:
            cur = conn.cursor()
            existing = {
                r["id"]
                for r in cur.execute(
                    "SELECT id FROM device WHERE process_id = %s", (process_id,)
                ).fetchall()
            }
            given = {d["id"] for d in devices if d.get("id") is not None}

            to_delete = sorted(existing - given)
            if to_delete:
                cur.execute("DELETE FROM device WHERE id = ANY(%s)", (to_delete,))

            to_update = [
                (
                    process_id,
                    d.get("name"),
                    d.get("celltype"),
                    d.get("description") or "",
                    d.get("order", 0),
                    d["id"],
                )
                for d in devices
                if d.get("id") is not None
            ]
            if to_update:
                cur.executemany(
                    'UPDATE device SET process_id=%s, name=%s, celltype=%s, '
                    'description=%s, "order"=%s WHERE id=%s',
                    to_update,
                )

            to_insert = [d for d in devices if d.get("id") is None]
            for d in to_insert:
                row = cur.execute(
                    'INSERT INTO device (process_id, name, celltype, description, "order") '
                    "VALUES (%s, %s, %s, %s, %s) RETURNING id, version",
                    (
                        process_id,
                        d.get("name"),
                        d.get("celltype"),
                        d.get("description") or "",
                        d.get("order", 0),
                    ),
                ).fetchone()
                d["id"] = row["id"]
                d["version"] = row["version"]

        return devices
