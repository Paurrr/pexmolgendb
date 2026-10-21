from dataclasses import dataclass, field

from psycopg import sql

from genviewer.service.errors import Conflict, StaleWriteError
from genviewer.service.pool import Database
from genviewer.service.repo import audit
from genviewer.service.schema import ADVISORY_LOCK_CLASS

# device 한 행 + 자식 탭 테이블이 한 사용자가 한 화면에서 편집하는 단위다.
# 그래서 version 은 device 에만 둔다. 자식 테이블에 쓰는 작업도 device 행에
# FOR UPDATE 를 걸고 version 을 올린다 (ParameterRepository 참고).
_SELECT_COLUMNS = (
    'id, process_id, name, celltype, description, "order", version, '
    "updated_at, updated_by"
)


@dataclass
class SaveResult:
    """저장 결과. devices 는 id/version 이 채워진 그 목록 그대로다.

    개수를 같이 내는 이유: upsert_devices 는 화면의 모든 device 를 받지만
    IS DISTINCT FROM 가드 때문에 실제로 쓰이는 것은 값이 달라진 행뿐이다.
    호출부가 payload 크기를 저장 건수인 양 보고하면 20개 중 1개만 고쳐도
    "20개 저장됨" 이 된다. UPDATE 의 RETURNING 이 진짜 개수를 이미 알고 있으니
    그것을 위로 올린다.
    """

    devices: list[dict] = field(default_factory=list)
    updated: int = 0
    inserted: int = 0
    deleted: int = 0

    @property
    def written(self) -> int:
        return self.updated + self.inserted + self.deleted


def _process_ident(cur, process_id: int) -> tuple[str, str]:
    """이력에 박을 process (이름, 버전). id 는 process 가 지워지면 읽을 수 없게 된다."""
    row = cur.execute(
        "SELECT name, release FROM process WHERE id = %s", (process_id,)
    ).fetchone()
    return (row["name"], row["release"]) if row else ("", "")


def etag_key(etag: dict | None) -> tuple | None:
    """etag 중 비교에 쓰는 부분만. who 는 표시용이라 뺀다."""
    if etag is None:
        return None
    return (etag["n"], etag["mx"], etag["vs"])


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

    def etag(self, process_id: int) -> dict:
        """이 process 의 device 상태 요약. 값이 달라졌으면 누군가 바꾼 것이다.

        세 집계가 각각 다른 변화를 잡는다.

          count(*)          삽입과 삭제
          sum(version)      수정 (자식 테이블 저장도 device.version 을 올린다)
          max(updated_at)   같은 수만큼 지우고 새로 넣어 앞의 둘이 그대로인 경우

        LISTEN/NOTIFY 대신 이걸 쓰는 이유: NOTIFY 는 풀 밖의 전용 커넥션과
        블로킹 리더가 필요하고, 14개 테이블에 트리거를 달거나 모든 쓰기 경로에
        pg_notify 를 넣어야 한다. LAN 에서 몇 명이 시간당 몇 번 저장하는
        상황이면 10초마다 집계 세 개를 읽는 쪽이 확실히 더 단순하다.

        who 는 배너 문구용이라 비교에는 쓰지 않는다. etag_key() 를 볼 것.
        """
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT count(*) AS n, "
                "       max(updated_at) AS mx, "
                "       coalesce(sum(version), 0) AS vs, "
                "       (SELECT updated_by FROM device WHERE process_id = %(pid)s "
                "         ORDER BY updated_at DESC, id DESC LIMIT 1) AS who "
                "  FROM device WHERE process_id = %(pid)s",
                {"pid": process_id},
            ).fetchone()
        return dict(row)

    def upsert_device(self, process_id: int, device: dict, *, actor: str = "") -> dict:
        """단건 upsert. 붙여넣기처럼 새 행을 하나 만들 때 쓴다."""
        with self.db.connection() as conn:
            # 고치는 것이라면 옛 값을 먼저 잡아 둔다. UPDATE 뒤에는 못 읽는다.
            before = None
            inserting = device.get("id") is None
            if not inserting:
                before = conn.execute(
                    f"SELECT {_SELECT_COLUMNS} FROM device WHERE id = %s FOR UPDATE",
                    (device["id"],),
                ).fetchone()

            if inserting:
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

            cur = conn.cursor()
            if inserting:
                name, release = _process_ident(cur, process_id)
                entry = audit.device_insert(name, device, process_release=release)
            elif before is None:
                # id 는 들고 있는데 행이 없다 - 남이 먼저 지웠다. UPDATE 도 아무
                # 행을 못 맞췄으므로 일어난 일이 없다. 남길 것도 없다.
                entry = None
            else:
                name, release = _process_ident(cur, process_id)
                entry = audit.device_update(
                    name, before, device, process_release=release
                )
            audit.write(cur, actor, [entry] if entry is not None else [])
        return device

    def upsert_devices(
        self,
        process_id: int,
        devices: list[dict],
        *,
        deleted: dict[int, int] | None = None,
        actor: str = "",
        force: bool = False,
    ) -> SaveResult:
        """화면의 device 목록을 저장한다.

        deleted: {device_id: 화면에 불러왔을 때의 version}. 사용자가 명시적으로
        지운 것만 들어온다. 예전에는 "목록에 없으면 지운다" 였기 때문에, 내가
        열어둔 사이 남이 추가한 device 가 조용히 사라졌다.

        어긋난 version 이 하나라도 있으면 아무것도 쓰지 않고 StaleWriteError 를
        낸다. force=True 면 사전 검사를 건너뛴다 (충돌 다이얼로그의 "덮어쓰기").
        """
        deleted = deleted or {}
        if not devices and not deleted:
            return SaveResult(devices)

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
                #
                # 편집 가능한 컬럼을 전부 읽는다. _preflight 는 version/name 만
                # 쓰지만, 이 행이 곧 이력의 "이전 값" 이다 - UPDATE 뒤에는 옛값을
                # 어디서도 다시 구할 수 없고, 이미 잠그려고 읽는 중이라 공짜다.
                rows = cur.execute(
                    f"SELECT {_SELECT_COLUMNS} FROM device "
                    "WHERE id = ANY(%s) ORDER BY id FOR UPDATE",
                    (known,),
                ).fetchall()
                db_now = {r["id"]: r for r in rows}

            if not force:
                conflicts = self._preflight(devices, deleted, db_now)
                if conflicts:
                    # with 블록이 롤백한다 — 아무것도 쓰이지 않는다.
                    raise StaleWriteError(conflicts)

            gone: list[dict] = []
            children: dict[int, dict] = {}
            if deleted:
                # 자식 행을 지우기 전에 읽어 둔다. DELETE 는 cascade 로 자식까지
                # 가져가므로 그 뒤에는 무엇이 사라졌는지 알 길이 없다.
                children, _ = audit.capture_children(cur, sorted(deleted))
                # process_id 조건: 그 사이 다른 process 로 옮겨진 device 를
                # 오래된 클라이언트가 지우지 못하게 한다.
                rows = cur.execute(
                    "DELETE FROM device WHERE id = ANY(%s) AND process_id = %s "
                    "RETURNING id",
                    (sorted(deleted), process_id),
                ).fetchall()
                # RETURNING 으로 세는 이유: 옮겨진 device 는 조건에 걸려 안 지워진다.
                # rowcount 를 믿으면 지우지 않은 것을 지웠다고 이력에 남긴다.
                gone = [db_now[r["id"]] for r in rows if r["id"] in db_now]
            removed = len(gone)

            changed = self._update_existing(cur, devices, actor, force)
            added = self._insert_new(cur, process_id, devices, actor)

            self._log(
                cur,
                process_id,
                actor,
                devices,
                db_now,
                gone,
                children,
                changed,
                added,
            )

        return SaveResult(
            devices, updated=len(changed), inserted=len(added), deleted=removed
        )

    @staticmethod
    def _log(cur, process_id, actor, devices, db_now, gone, children, changed, added):
        """이 트랜잭션이 실제로 쓴 것만 이력에 남긴다.

        changed 는 UPDATE 의 RETURNING 이 돌려준 행뿐이다. save_all 은 화면의
        device 를 전부 보내지만 IS DISTINCT FROM 가드가 값이 같은 행을 걸러내므로,
        손대지 않은 저장은 여기서 한 줄도 만들지 않는다.
        """
        if not (gone or changed or added):
            return

        name, release = _process_ident(cur, process_id)
        payload = {d["id"]: d for d in devices if d.get("id") is not None}
        entries = [
            audit.device_delete(
                name, row, children.get(row["id"], {}), process_release=release
            )
            for row in gone
        ]
        for device_id in changed:
            entry = audit.device_update(
                name, db_now[device_id], payload[device_id], process_release=release
            )
            if entry is not None:
                entries.append(entry)
        entries += [
            audit.device_insert(name, d, process_release=release) for d in added
        ]
        audit.write(cur, actor, entries)

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
    ) -> dict[int, int]:
        """실제로 UPDATE 된 행만 {id: 새 version} 으로 낸다.

        개수가 아니라 id 를 내는 이유: 이력이 "어느 행이" 바뀌었는지 알아야
        이전 값과 짝지을 수 있다. 개수는 호출부에서 len() 으로 낸다.
        """
        to_update = [d for d in devices if d.get("id") is not None]
        if not to_update:
            return {}

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

        # audit.BATCH_ROWS 행씩 나눠 같은 커서로 차례로 보낸다(바인드 파라미터 상한).
        # 행은 upsert_devices 가 이미 FOR UPDATE 로 잠갔고, 가드는 문장마다 똑같이
        # 걸리므로 나눠도 쓰이는 행은 같다. 묶음마다 받은 RETURNING 을 합친다.
        changed: dict[int, int] = {}
        for start in range(0, len(to_update), audit.BATCH_ROWS):
            batch = to_update[start : start + audit.BATCH_ROWS]
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
                values=sql.SQL(", ").join([row_tmpl] * len(batch)),
                version_guard=version_guard,
            )

            params: list = [actor]
            for d in batch:
                params += [
                    d["id"],
                    d.get("version"),
                    d.get("name"),
                    d.get("celltype"),
                    d.get("description") or "",
                    d.get("order", 0),
                ]

            for r in cur.execute(stmt, params).fetchall():
                changed[r["id"]] = r["version"]
        # RETURNING 에 없는 행은 값이 같아 건드리지 않은 것이므로 version 유지.
        for d in to_update:
            if d["id"] in changed:
                d["version"] = changed[d["id"]]
        return changed

    @staticmethod
    def _insert_new(
        cur, process_id: int, devices: list[dict], actor: str
    ) -> list[dict]:
        """새로 INSERT 된 device 를 (id 가 채워진 채로) 낸다."""
        to_insert = [d for d in devices if d.get("id") is None]
        for d in to_insert:
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
        return to_insert
