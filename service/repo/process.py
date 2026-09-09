import sqlite3


class ProcessRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def get_id(self, name: str) -> int | None:
        """이름으로 process id 조회"""
        cur = self.conn.cursor()
        cur.execute("SELECT id FROM process WHERE name = ?", (name,))
        row = cur.fetchone()
        return row[0] if row else None

    def add(self, name: str) -> bool:
        cur = self.conn.cursor()
        try:
            cur.execute("INSERT INTO process (name) VALUES (?)", (name,))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            # UNIQUE 충돌 → 이미 존재
            return False

    def delete(self, name: str) -> bool:
        cur = self.conn.cursor()
        try:
            cur.execute("DELETE FROM process WHERE name = ?", (name,))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def exists(self, name: str) -> bool:
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM process WHERE name=?", (name,))
        return cur.fetchone() is not None

    def list_all(self) -> list[str]:
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM process ORDER BY name")
        return [r[0] for r in cur.fetchall()]

    def get_or_create_id(self, name: str) -> int | None:
        """id 조회, 없으면 생성 후 반환"""
        if not name:
            return None
        pid = self.get_id(name)
        if pid:
            return pid
        self.add(name)
        return self.get_id(name)