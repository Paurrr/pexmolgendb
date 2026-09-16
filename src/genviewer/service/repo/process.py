import psycopg

from genviewer.service.pool import Database
from genviewer.service.repo import audit

# 지워질 device 에서 이력에 보관할 컬럼. id 는 무엇이 있었는지 짚어보는 용도다.
_DEVICE_COLUMNS = 'id, name, celltype, description, "order"'


class ProcessRepository:
    def __init__(self, db: Database):
        self.db = db

    def get_id(self, name: str) -> int | None:
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT id FROM process WHERE name = %s", (name,)
            ).fetchone()
        return row["id"] if row else None

    def add(self, name: str, *, actor: str = "") -> bool:
        try:
            with self.db.connection() as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO process (name) VALUES (%s)", (name,))
                audit.write(cur, actor, [audit.process_add(name)])
            return True
        except psycopg.errors.UniqueViolation:
            # 이미 존재
            return False

    def delete(self, name: str, *, actor: str = "") -> bool:
        """process 하나와, cascade 로 함께 사라지는 모든 것.

        지우기 전에 내용을 통째로 이력에 담는다. 이 한 번의 클릭으로 device
        수십 개와 그 자식 행 전부가 사라지는데, 지금까지는 누가 그랬는지조차
        남지 않았다.
        """
        with self.db.connection() as conn:
            cur = conn.cursor()
            row = cur.execute(
                "SELECT id FROM process WHERE name = %s", (name,)
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

            cur.execute("DELETE FROM process WHERE name = %s", (name,))
            audit.write(
                cur, actor, [audit.process_delete(name, devices, truncated)]
            )
        return True

    def exists(self, name: str) -> bool:
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM process WHERE name = %s", (name,)
            ).fetchone()
        return row is not None

    def list_all(self) -> list[str]:
        with self.db.connection() as conn:
            rows = conn.execute("SELECT name FROM process ORDER BY name").fetchall()
        return [r["name"] for r in rows]

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

    def count_devices(self, name: str) -> int:
        """이 process 를 지우면 cascade 로 함께 사라질 device 수."""
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT count(*) AS n FROM device d JOIN process p ON p.id = d.process_id "
                "WHERE p.name = %s",
                (name,),
            ).fetchone()
        return row["n"] if row else 0

    def get_or_create_id(self, name: str, *, actor: str = "") -> int | None:
        """id 조회, 없으면 생성 후 반환."""
        if not name:
            return None
        with self.db.connection() as conn:
            cur = conn.cursor()
            # xmax = 0 이면 이번에 INSERT 된 행이다. ON CONFLICT DO UPDATE 는
            # 이미 있던 경우에도 행을 돌려주므로 이것 없이는 둘을 구분할 수
            # 없고, process 를 고를 때마다 "process 추가" 가 쌓인다.
            row = cur.execute(
                "INSERT INTO process (name) VALUES (%s) "
                "ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name "
                "RETURNING id, (xmax = 0) AS created",
                (name,),
            ).fetchone()
            if row and row["created"]:
                audit.write(cur, actor, [audit.process_add(name)])
        return row["id"] if row else None
