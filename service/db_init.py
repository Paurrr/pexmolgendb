import sqlite3

_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS process (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS device (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        process_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        celltype TEXT NOT NULL,
        description TEXT,
        "order" INTEGER DEFAULT 0,
        FOREIGN KEY(process_id) REFERENCES process(id) ON DELETE CASCADE
    )
    """,
    'CREATE INDEX IF NOT EXISTS idx_device_process_id ON device(process_id)',
    'CREATE INDEX IF NOT EXISTS idx_device_process_id_order ON device(process_id, "order")',
    """
    CREATE TABLE IF NOT EXISTS suffix_cell_name (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        suffix_cell_name TEXT,
        FOREIGN KEY(device_id) REFERENCES device(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS inst_terms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        reserved_key TEXT,
        cds_inst_term_name TEXT,
        FOREIGN KEY(device_id) REFERENCES device(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS inst_sch_params (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        reserved_key TEXT,
        cds_inst_parameter_name TEXT,
        FOREIGN KEY(device_id) REFERENCES device(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS inst_sch_param_ranges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        inst_sch_param_reserved_key TEXT,
        value TEXT,
        FOREIGN KEY(device_id) REFERENCES device(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pre_define_inst_sch_param_values (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        cds_inst_parameter_name TEXT,
        value TEXT,
        FOREIGN KEY(device_id) REFERENCES device(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS post_define_inst_sch_param_values (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        cds_inst_parameter_name TEXT,
        value TEXT,
        FOREIGN KEY(device_id) REFERENCES device(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS post_define_inst_lay_param_values (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        cds_inst_parameter_name TEXT,
        value TEXT,
        FOREIGN KEY(device_id) REFERENCES device(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS add_layers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        layer_name_purpose TEXT,
        reference_layer_name_purpose TEXT,
        value TEXT,
        drawn_type TEXT,
        FOREIGN KEY(device_id) REFERENCES device(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS add_fgrs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        fgr_name TEXT,
        reference_layer_name_purpose TEXT,
        value TEXT,
        term_name TEXT,
        fgr_parameter_header_name TEXT,
        FOREIGN KEY(device_id) REFERENCES device(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS add_fgr_params (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        parameter_name TEXT,
        value TEXT,
        FOREIGN KEY(device_id) REFERENCES device(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS add_nfgr_params (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        parameter_name TEXT,
        value TEXT,
        FOREIGN KEY(device_id) REFERENCES device(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS add_pfgr_params (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        parameter_name TEXT,
        value TEXT,
        FOREIGN KEY(device_id) REFERENCES device(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS add_fgr_first_metals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER,
        layer_name TEXT,
        purpose TEXT,
        FOREIGN KEY(device_id) REFERENCES device(id) ON DELETE CASCADE
    )
    """,
]


def initialize_database(path: str) -> bool:
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        for stmt in _SCHEMA:
            cursor.execute(stmt)
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False
