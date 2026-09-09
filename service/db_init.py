import sqlite3

from service.schema import sqlite_all_ddl


def initialize_database(path: str) -> bool:
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        for stmt in sqlite_all_ddl():
            cursor.execute(stmt)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Database initialization failed: {e}")
        return False
