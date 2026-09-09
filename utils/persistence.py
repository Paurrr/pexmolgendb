import sqlite3


def save_database(source_conn, file_path):
    dest_conn = sqlite3.connect(file_path)
    with dest_conn:
        source_conn.backup(dest_conn)
    dest_conn.close()
