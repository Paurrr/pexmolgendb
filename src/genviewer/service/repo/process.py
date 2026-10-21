import psycopg
from psycopg import sql

from genviewer.service import schema
from genviewer.service.pool import Database
from genviewer.service.repo import audit

# 지워질 device 에서 이력에 보관할 컬럼. id 는 무엇이 있었는지 짚어보는 용도다.
_DEVICE_COLUMNS = 'id, name, celltype, description, "order"'


def _copy_tab_rows(cur, new_ids: dict[int, int]) -> None:
    """탭 테이블마다 옛 device 들의 행을 id 순으로 읽어 새 device 로 넣는다. 호출자의 트랜잭션.

    id 순으로 넣으므로 device 하나 안의 행 순서(화면·내보내기가 읽는 ORDER BY id)가 원본과
    같다. 행 하나가 문장 하나(executemany)라 행이 많아도 바인드 파라미터 상한(65,535)에 닿지 않는다.
    """
    old_ids = list(new_ids)
    for table, columns in schema.TABLE_COLUMNS.items():
        tbl = sql.Identifier(table)
        cols = sql.SQL(", ").join(map(sql.Identifier, columns))
        rows = cur.execute(
            sql.SQL(
                "SELECT device_id, {cols} FROM {tbl} WHERE device_id = ANY(%s) ORDER BY id"
            ).format(cols=cols, tbl=tbl),
            (old_ids,),
        ).fetchall()
        if not rows:
            continue
        cur.executemany(
            sql.SQL("INSERT INTO {tbl} (device_id, {cols}) VALUES ({vals})").format(
                tbl=tbl,
                cols=cols,
                vals=sql.SQL(", ").join(sql.Placeholder() * (len(columns) + 1)),
            ),
            [(new_ids[r["device_id"]], *(r[c] for c in columns)) for r in rows],
        )


def find_or_create(cur, name: str, release: str = "") -> tuple[int, bool]:
    """(이름, 버전) 쌍의 process id 와, 이번에 새로 만들었는지. 호출자의 트랜잭션 안에서 돈다.

    이미 있는 process 는 SELECT 로만 찾고 행을 잠그지 않는다. 예전의
    ON CONFLICT DO UPDATE 는 이미 있을 때도 그 행을 FOR UPDATE 로 잠가서,
    CSV 불러오기가 커밋할 때까지 GUI 가 같은 process 를 고르거나 저장하지
    못했다(lock_timeout 뒤 55P03). device INSERT 의 외래키 검사가 잡는
    FOR KEY SHARE 와도 부딪혀서 어느 한쪽만 바꿔서는 풀리지 않는다.
    """
    while True:
        row = cur.execute(
            "SELECT id FROM process WHERE name = %s AND release = %s", (name, release)
        ).fetchone()
        if row:
            return row["id"], False
        row = cur.execute(
            "INSERT INTO process (name, release) VALUES (%s, %s) "
            "ON CONFLICT (name, release) DO NOTHING RETURNING id",
            (name, release),
        ).fetchone()
        if row:
            return row["id"], True
        # 그 사이 다른 트랜잭션이 같은 쌍을 만들었다. 다시 읽는다.


class ProcessRepository:
    """process 는 (이름, 버전) 쌍이다. release 가 버전이고 빈 문자열은 "버전 없음" 이다."""

    def __init__(self, db: Database):
        self.db = db

    def get_id(self, name: str, *, release: str = "") -> int | None:
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT id FROM process WHERE name = %s AND release = %s", (name, release)
            ).fetchone()
        return row["id"] if row else None

    def add(self, name: str, *, release: str = "", actor: str = "") -> bool:
        try:
            with self.db.connection() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO process (name, release) VALUES (%s, %s)", (name, release)
                )
                audit.write(cur, actor, [audit.process_add(name, process_release=release)])
            return True
        except psycopg.errors.UniqueViolation:
            # 이미 존재
            return False

    def delete(self, name: str, *, release: str = "", actor: str = "") -> bool:
        """(이름, 버전) 쌍 하나와, cascade 로 함께 사라지는 모든 것.

        같은 이름의 다른 버전과 그 device 는 그대로다. 지우기 전에 내용을 통째로
        이력에 담는다. 이 한 번의 클릭으로 device 수십 개와 그 자식 행 전부가
        사라지는데, 지금까지는 누가 그랬는지조차 남지 않았다.
        """
        with self.db.connection() as conn:
            cur = conn.cursor()
            row = cur.execute(
                "SELECT id FROM process WHERE name = %s AND release = %s", (name, release)
            ).fetchone()
            if row is None:
                # 예전 계약: 없는 것을 지워도 참이다.
                return True

            devices = [
                dict(r)
                for r in cur.execute(
                    f"SELECT {_DEVICE_COLUMNS} FROM device "
                    "WHERE process_id = %s ORDER BY id",
                    (row["id"],),
                ).fetchall()
            ]
            children, truncated = audit.capture_children(
                cur, [d["id"] for d in devices], max_rows=audit.CHILD_ROW_CAP
            )
            for device in devices:
                device["children"] = children.get(device["id"], {})

            cur.execute("DELETE FROM process WHERE id = %s", (row["id"],))
            audit.write(
                cur,
                actor,
                [audit.process_delete(name, devices, truncated, process_release=release)],
            )
        return True

    def exists(self, name: str, *, release: str = "") -> bool:
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM process WHERE name = %s AND release = %s", (name, release)
            ).fetchone()
        return row is not None

    def list_all(self) -> list[str]:
        """서로 다른 process 이름. 버전이 여럿이어도 이름은 한 번이다."""
        with self.db.connection() as conn:
            rows = conn.execute("SELECT DISTINCT name FROM process ORDER BY name").fetchall()
        return [r["name"] for r in rows]

    def list_pairs(self) -> list[tuple[str, str]]:
        """(이름, 버전) 쌍. 이름은 list_all 과 같은 순서, 같은 이름 안에서는 버전의 코드포인트 순.

        빈 버전이 그 이름의 맨 앞이다. 버전을 기본 collation(예 en_US)으로 정렬하면
        '-'·'.' 를 첫 단계에서 무시해서 S00-V1.0 과 S00V1 의 순서가 코드포인트와 달라진다.
        """
        with self.db.connection() as conn:
            rows = conn.execute(
                'SELECT name, release FROM process ORDER BY name, release COLLATE "C"'
            ).fetchall()
        return [(r["name"], r["release"]) for r in rows]

    def list_with_counts(self) -> list[tuple[str, int]]:
        """process 이름과 그 안의 device 수. 이름 순.

        list_all + count_devices 로 하면 process 마다 쿼리가 하나씩 더 나간다.
        LEFT JOIN 이라 device 가 없는 process 도 0 으로 나온다.
        """
        with self.db.connection() as conn:
            rows = conn.execute(
                "SELECT p.name, count(d.id) AS n FROM process p "
                "LEFT JOIN device d ON d.process_id = p.id "
                "GROUP BY p.name ORDER BY p.name"
            ).fetchall()
        return [(r["name"], r["n"]) for r in rows]

    def count_devices(self, name: str, *, release: str = "") -> int:
        """이 (이름, 버전) 쌍을 지우면 cascade 로 함께 사라질 device 수."""
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT count(*) AS n FROM device d JOIN process p ON p.id = d.process_id "
                "WHERE p.name = %s AND p.release = %s",
                (name, release),
            ).fetchone()
        return row["n"] if row else 0

    def clone(
        self, src_name: str, src_release: str, name: str, release: str, *, actor: str = ""
    ) -> int | None:
        """새 (name, release) 를 만들고 원본 (src_name, src_release) 의 device 와 탭 행을 복사한다.

        반환: 복사한 device 수(원본이 비었으면 0). 대상이 이미 있으면 아무것도 만들지 않고 None
        (add 의 "이미 있음" 과 같다). 원본이 없으면 LookupError. 전부 한 트랜잭션이다.

        REPEATABLE READ 라야 device 와 탭 행이 같은 시점의 원본이다. READ COMMITTED 면 device 를
        복사한 뒤 남이 원본 탭을 저장해 커밋했을 때 복사본의 탭만 그 뒤 시점이 된다. 원본 행은
        잠그지 않는다. 잠그면 복제하는 동안 원본을 저장하는 사람이 lock_timeout 뒤 55P03 으로
        실패한다(find_or_create 와 같은 이유). 새 process 는 아직 아무도 고를 수 없어서 advisory
        lock 도 필요 없다.
        """
        try:
            with self.db.connection() as conn:
                cur = conn.cursor()
                # 트랜잭션의 첫 문장이어야 한다. 풀은 트랜잭션 밖의 커넥션을 준다.
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                src = cur.execute(
                    "SELECT id FROM process WHERE name = %s AND release = %s",
                    (src_name, src_release),
                ).fetchone()
                if src is None:
                    raise LookupError(
                        f"원본 process 가 없다: {audit.process_label(src_name, src_release)}"
                    )
                # ON CONFLICT 를 쓰지 않는다. REPEATABLE READ 에서 동시 생성과 부딪히면 40001 이
                # 날 수 있다. 평범한 INSERT 의 UniqueViolation 은 add 와 같은 길이다.
                process_id = cur.execute(
                    "INSERT INTO process (name, release) VALUES (%s, %s) RETURNING id",
                    (name, release),
                ).fetchone()["id"]

                # 같은 order 의 device 끼리는 id 순서다. 그 순서로 하나씩 넣어야 새 id 도 같은
                # 순서가 된다. 옛 id -> 새 id 는 문장마다 받은 id 로 잇는다. INSERT … SELECT …
                # RETURNING 이 돌려주는 행의 순서는 보장되지 않는다.
                devices = cur.execute(
                    f"SELECT {_DEVICE_COLUMNS} FROM device "
                    'WHERE process_id = %s ORDER BY "order", id',
                    (src["id"],),
                ).fetchall()
                new_ids: dict[int, int] = {}
                for d in devices:
                    new_ids[d["id"]] = cur.execute(
                        'INSERT INTO device (process_id, name, celltype, description, "order", '
                        "updated_by) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                        (process_id, d["name"], d["celltype"], d["description"], d["order"], actor),
                    ).fetchone()["id"]

                if new_ids:
                    _copy_tab_rows(cur, new_ids)

                audit.write(
                    cur,
                    actor,
                    [
                        audit.process_add(
                            name,
                            process_release=release,
                            source=(src_name, src_release),
                            devices=len(devices),
                        )
                    ],
                )
            return len(devices)
        except psycopg.errors.UniqueViolation:
            # 이미 존재
            return None

    def get_or_create_id(self, name: str, *, release: str = "", actor: str = "") -> int | None:
        """(이름, 버전) 쌍의 id 조회, 없으면 생성 후 반환."""
        if not name:
            return None
        with self.db.connection() as conn:
            cur = conn.cursor()
            process_id, created = find_or_create(cur, name, release)
            # 새로 만든 경우에만 남긴다. 아니면 process 를 고를 때마다
            # "process 추가" 가 쌓인다.
            if created:
                audit.write(cur, actor, [audit.process_add(name, process_release=release)])
        return process_id
