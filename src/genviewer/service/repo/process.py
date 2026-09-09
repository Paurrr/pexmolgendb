import psycopg

from genviewer.service.pool import Database


class ProcessRepository:
    def __init__(self, db: Database):
        self.db = db

    def get_id(self, name: str) -> int | None:
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT id FROM process WHERE name = %s", (name,)
            ).fetchone()
        return row["id"] if row else None

    def add(self, name: str) -> bool:
        try:
            with self.db.connection() as conn:
                conn.execute("INSERT INTO process (name) VALUES (%s)", (name,))
            return True
        except psycopg.errors.UniqueViolation:
            # 이미 존재
            return False

    def delete(self, name: str) -> bool:
        with self.db.connection() as conn:
            conn.execute("DELETE FROM process WHERE name = %s", (name,))
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

    def count_devices(self, name: str) -> int:
        """이 process 를 지우면 cascade 로 함께 사라질 device 수."""
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT count(*) AS n FROM device d JOIN process p ON p.id = d.process_id "
                "WHERE p.name = %s",
                (name,),
            ).fetchone()
        return row["n"] if row else 0

    def get_or_create_id(self, name: str) -> int | None:
        """id 조회, 없으면 생성 후 반환."""
        if not name:
            return None
        with self.db.connection() as conn:
            row = conn.execute(
                "INSERT INTO process (name) VALUES (%s) "
                "ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name "
                "RETURNING id",
                (name,),
            ).fetchone()
        return row["id"] if row else None
