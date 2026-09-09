from psycopg import sql

from genviewer.service.errors import Conflict, StaleWriteError
from genviewer.service.pool import Database
from genviewer.service.schema import ADVISORY_LOCK_CLASS

# device 한 행 + 13개 자식 테이블이 한 사용자가 한 화면에서 편집하는 단위다.
# 그래서 version 은 device 에만 둔다. 자식 테이블에 쓰는 작업도 device 행에
# FOR UPDATE 를 걸고 version 을 올린다 (ParameterRepository 참고).
_SELECT_COLUMNS = (
    'id, process_id, name, celltype, description, "order", version, '
    "updated_at, updated_by"
)


class DeviceRepository:
    def __init__(self, db: Database):
        self.db = db

    def fetch_devices_by_process(self, process_id: int) -> list[dict]:
        """ORDER BY "order", id — "order" 만으로는 전순서가 아니다."""
        with self.db.connection() as conn:
            rows = conn.execute(
                f"SELECT {_SELECT_COLUMNS} FROM device "
                'WHERE process_id = %s ORDER BY "order", id',
                (process_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def upsert_device(self, process_id: int, device: dict, *, actor: str = "") -> dict:
        """단건 upsert. 붙여넣기처럼 새 행을 하나 만들 때 쓴다."""
        with self.db.connection() as conn:
            if device.get("id") is None:
                row = conn.execute(
                    "INSERT INTO device "
                    '  (process_id, name, celltype, description, "order", updated_by) '
                    "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, version",
                    (
                        process_id,
                        device.get("name"),
                        device.get("celltype"),
                        device.get("description") or "",
                        device.get("order", 0),
                        actor,
                    ),
                ).fetchone()
                device["id"] = row["id"]
                device["version"] = row["version"]
            else:
                row = conn.execute(
                    "UPDATE device SET process_id=%s, name=%s, celltype=%s, "
                    'description=%s, "order"=%s, version=version+1, '
                    "updated_at=now(), updated_by=%s WHERE id=%s RETURNING version",
                    (
                        process_id,
                        device.get("name"),
                        device.get("celltype"),
                        device.get("description") or "",
                        device.get("order", 0),
                        actor,
                        device["id"],
                    ),
                ).fetchone()
                if row:
                    device["version"] = row["version"]
        return device

    def upsert_devices(
        self,
        process_id: int,
        devices: list[dict],
        *,
        deleted: dict[int, int] | None = None,
        actor: str = "",
        force: bool = False,
    ) -> list[dict]:
        """화면의 device 목록을 저장한다.

        deleted: {device_id: 화면에 불러왔을 때의 version}. 사용자가 명시적으로
        지운 것만 들어온다. 예전에는 "목록에 없으면 지운다" 였기 때문에, 내가
        열어둔 사이 남이 추가한 device 가 조용히 사라졌다.

        어긋난 version 이 하나라도 있으면 아무것도 쓰지 않고 StaleWriteError 를
        낸다. force=True 면 사전 검사를 건너뛴다 (충돌 다이얼로그의 "덮어쓰기").
        """
        deleted = deleted or {}
        if not devices and not deleted:
            return devices

        known = sorted(
            {d["id"] for d in devices if d.get("id") is not None} | set(deleted)
        )

        with self.db.connection() as conn:
            cur = conn.cursor()

            # 같은 process 에 대한 동시 저장을 직렬화한다. COMMIT 시 자동 해제.
            cur.execute(
                "SELECT pg_advisory_xact_lock(%s::int, %s::int)",
                (ADVISORY_LOCK_CLASS, process_id),
            )

            db_now = {}
            if known:
                # id 순서로 잠근다 — 두 저장이 서로를 기다리는 교착을 막는다.
                rows = cur.execute(
                    "SELECT id, name, version, updated_by, updated_at FROM device "
                    "WHERE id = ANY(%s) ORDER BY id FOR UPDATE",
                    (known,),
                ).fetchall()
                db_now = {r["id"]: r for r in rows}

            if not force:
                conflicts = self._preflight(devices, deleted, db_now)
                if conflicts:
                    # with 블록이 롤백한다 — 아무것도 쓰이지 않는다.
                    raise StaleWriteError(conflicts)

            if deleted:
                # process_id 조건: 그 사이 다른 process 로 옮겨진 device 를
                # 오래된 클라이언트가 지우지 못하게 한다.
                cur.execute(
                    "DELETE FROM device WHERE id = ANY(%s) AND process_id = %s",
                    (sorted(deleted), process_id),
                )

            self._update_existing(cur, devices, actor, force)
            self._insert_new(cur, process_id, devices, actor)

        return devices

    @staticmethod
    def _preflight(
        devices: list[dict], deleted: dict[int, int], db_now: dict[int, dict]
    ) -> list[Conflict]:
        conflicts: list[Conflict] = []

        def check(device_id: int, expected, name: str):
            row = db_now.get(device_id)
            if row is None:
                conflicts.append(Conflict(device_id, name, "deleted"))
            elif expected is not None and row["version"] != expected:
                conflicts.append(
                    Conflict(
                        device_id,
                        row["name"],
                        "stale",
                        row["updated_by"],
                        row["updated_at"],
                    )
                )

        for d in devices:
            if d.get("id") is not None:
                check(d["id"], d.get("version"), d.get("name", ""))
        for device_id, version in deleted.items():
            check(device_id, version, "")
        return conflicts

    @staticmethod
    def _update_existing(
        cur, devices: list[dict], actor: str, force: bool = False
    ) -> None:
        to_update = [d for d in devices if d.get("id") is not None]
        if not to_update:
            return

        # IS DISTINCT FROM 가드는 최적화가 아니다. save_all 은 손대지 않은
        # device 까지 전부 보내므로, 가드가 없으면 한 번 저장할 때마다 process
        # 전체의 version 이 올라가 다른 클라이언트의 캐시를 모두 무효화한다.
        #
        # VALUES 의 명시적 캐스팅도 필수다. 없으면 컬럼 타입이 unknown 이라
        # 행 단위 IS DISTINCT FROM 의 연산자를 결정하지 못한다.
        row_tmpl = sql.SQL(
            "(%s::bigint, %s::integer, %s::text, %s::text, %s::text, %s::integer)"
        )
        # force 일 때는 version 조건을 빼야 한다. 넣어두면 덮어쓰기를 눌러도
        # 오래된 행이 매칭되지 않아 아무것도 쓰이지 않는다.
        version_guard = sql.SQL("") if force else sql.SQL("AND d.version = v.version ")
        stmt = sql.SQL(
            "UPDATE device d SET "
            "  name=v.name, celltype=v.celltype, description=v.description, "
            '  "order"=v.ord, version=d.version+1, updated_at=now(), updated_by=%s '
            "FROM (VALUES {values}) AS v(id, version, name, celltype, description, ord) "
            "WHERE d.id = v.id {version_guard}"
            '  AND (d.name, d.celltype, d.description, d."order") '
            "      IS DISTINCT FROM (v.name, v.celltype, v.description, v.ord) "
            "RETURNING d.id, d.version"
        ).format(
            values=sql.SQL(", ").join([row_tmpl] * len(to_update)),
            version_guard=version_guard,
        )

        params: list = [actor]
        for d in to_update:
            params += [
                d["id"],
                d.get("version"),
                d.get("name"),
                d.get("celltype"),
                d.get("description") or "",
                d.get("order", 0),
            ]

        changed = {r["id"]: r["version"] for r in cur.execute(stmt, params).fetchall()}
        # RETURNING 에 없는 행은 값이 같아 건드리지 않은 것이므로 version 유지.
        for d in to_update:
            if d["id"] in changed:
                d["version"] = changed[d["id"]]

    @staticmethod
    def _insert_new(cur, process_id: int, devices: list[dict], actor: str) -> None:
        for d in [d for d in devices if d.get("id") is None]:
            # ON CONFLICT DO UPDATE 를 쓰면 안 된다. 남이 같은 이름으로 만든
            # device 를 조용히 흡수하는 것은 지금 없애려는 버그와 같은 부류다.
            row = cur.execute(
                "INSERT INTO device "
                '  (process_id, name, celltype, description, "order", updated_by) '
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, version",
                (
                    process_id,
                    d.get("name"),
                    d.get("celltype"),
                    d.get("description") or "",
                    d.get("order", 0),
                    actor,
                ),
            ).fetchone()
            d["id"] = row["id"]
            d["version"] = row["version"]
