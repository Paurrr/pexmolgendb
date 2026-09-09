"""스키마의 단일 진실 공급원.

13개 자식 테이블의 이름과 컬럼은 config/tab_config.json 이 이미 선언하고 있다.
db_init 이 그 목록을 손으로 한 번 더 적어두고 있었기 때문에, 탭을 하나
추가하면 두 곳을 고쳐야 했고 어긋나도 아무도 알아채지 못했다. 여기서 생성해서
그 위험을 없앤다.

지금은 SQLite DDL 만 낸다. PostgreSQL 로 넘어갈 때 렌더러만 교체하면 되도록
테이블 구조 자체는 아래 상수로 선언해 둔다.
"""

from config.config import tab_config

PROCESS_TABLE = "process"
DEVICE_TABLE = "device"


def child_tables() -> dict[str, list[str]]:
    """자식 테이블 이름 -> payload 컬럼 목록. tab_config.json 이 원본이다."""
    return {info["table"]: list(info["columns"]) for info in tab_config.values()}


# repo 가 호출자에게서 받은 테이블/컬럼 이름을 검증하는 allow-list.
TABLE_COLUMNS = child_tables()


_SQLITE_PROCESS_DDL = """
    CREATE TABLE IF NOT EXISTS process (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )
    """

_SQLITE_DEVICE_DDL = """
    CREATE TABLE IF NOT EXISTS device (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        process_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        celltype TEXT NOT NULL,
        description TEXT,
        "order" INTEGER DEFAULT 0,
        FOREIGN KEY(process_id) REFERENCES process(id) ON DELETE CASCADE
    )
    """

_SQLITE_DEVICE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_device_process_id ON device(process_id)",
    'CREATE INDEX IF NOT EXISTS idx_device_process_id_order ON device(process_id, "order")',
]


def sqlite_child_ddl(table: str, columns: list[str]) -> str:
    payload = "".join(f"        {c} TEXT,\n" for c in columns)
    return (
        f"    CREATE TABLE IF NOT EXISTS {table} (\n"
        f"        id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        f"        device_id INTEGER,\n"
        f"{payload}"
        f"        FOREIGN KEY(device_id) REFERENCES device(id) ON DELETE CASCADE\n"
        f"    )\n"
    )


def sqlite_all_ddl() -> list[str]:
    """initialize_database 가 순서대로 실행할 DDL 문 목록."""
    out = [_SQLITE_PROCESS_DDL, _SQLITE_DEVICE_DDL, *_SQLITE_DEVICE_INDEXES]
    for table, columns in child_tables().items():
        out.append(sqlite_child_ddl(table, columns))
    return out
