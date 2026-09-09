import re
from collections import defaultdict
from pathlib import Path

import pandas as pd
import psycopg
from psycopg import sql

from genviewer.config.config import tab_config
from genviewer.service.pool import Database


class IORepository:
    def __init__(self, db: Database):
        self.db = db

    def get_or_create_process_id(self, process_name: str) -> int | None:
        if process_name is None or pd.isna(process_name) or not str(process_name).strip():
            return None
        with self.db.connection() as conn:
            return self._process_id(conn.cursor(), process_name)

    @staticmethod
    def _process_id(cur, process_name) -> int | None:
        if process_name is None or pd.isna(process_name) or not str(process_name).strip():
            return None
        row = cur.execute(
            "INSERT INTO process (name) VALUES (%s) "
            "ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING id",
            (str(process_name).strip(),),
        ).fetchone()
        return row["id"] if row else None

    def import_data(self, input_path: str):
        """CSV 를 읽어 device 와 13개 탭 테이블에 반영한다.

        UNIQUE (process_id, name) 이 생기면서 동작이 바뀌었다. 예전에는 임포트할
        때마다 device 를 새로 만들어서 같은 CSV 를 두 번 넣으면 전부 중복됐다.
        이제는 (process, name) 이 같으면 그 device 를 갱신하고 자식 행을 통째로
        교체한다 — CSV 가 원본이라는 뜻에 맞고 재임포트가 멱등해진다.
        """
        try:
            data_path = Path(input_path)
            if not data_path.is_file():
                return False

            df = pd.read_csv(data_path)

            with self.db.connection() as conn:
                cur = conn.cursor()
                rows_by_table: dict[str, list[tuple]] = defaultdict(list)
                touched_devices: set[int] = set()

                for _, row in df.iterrows():
                    process_id = self._process_id(cur, row["CdsLibName"])
                    if process_id is None:
                        continue

                    device_row = cur.execute(
                        "INSERT INTO device (process_id, name, celltype) "
                        "VALUES (%s, %s, %s) "
                        "ON CONFLICT (process_id, name) DO UPDATE "
                        "   SET celltype = EXCLUDED.celltype "
                        "RETURNING id",
                        (process_id, row["InstCellName"], row["CellType"]),
                    ).fetchone()
                    device_id = device_row["id"]
                    touched_devices.add(device_id)

                    for section_name, section_info in tab_config.items():
                        table_name = section_info["table"]
                        expected_columns = section_info["columns"]
                        n_expected = len(expected_columns)
                        pattern = re.compile(rf"^{re.escape(section_name)}(?:\.\d+)?$")

                        for col in df.columns:
                            if not (pattern.match(col) and pd.notna(row[col])):
                                continue
                            try:
                                values = row[col].strip().split()
                                if len(values) < n_expected:
                                    values += [""] * (n_expected - len(values))
                                else:
                                    values = values[:n_expected]
                                value_dict = dict(
                                    zip(expected_columns, values, strict=True)
                                )
                                rows_by_table[table_name].append(
                                    (device_id, *[value_dict[c] for c in expected_columns])
                                )
                            except (AttributeError, KeyError, TypeError) as e:
                                print(f"CSV cell {row[col]!r} skipped: {e}")

                if touched_devices:
                    ids = sorted(touched_devices)
                    # 이 device 들의 자식 행은 CSV 내용으로 통째로 교체한다.
                    for section_info in tab_config.values():
                        cur.execute(
                            sql.SQL("DELETE FROM {tbl} WHERE device_id = ANY(%s)").format(
                                tbl=sql.Identifier(section_info["table"])
                            ),
                            (ids,),
                        )

                for table_name, to_insert in rows_by_table.items():
                    section_key = next(
                        k for k, v in tab_config.items() if v["table"] == table_name
                    )
                    expected_columns = tab_config[section_key]["columns"]
                    full_columns = ["device_id"] + expected_columns

                    insert_df = pd.DataFrame(to_insert, columns=full_columns)
                    insert_df.drop_duplicates(inplace=True)

                    stmt = sql.SQL("INSERT INTO {tbl} ({cols}) VALUES ({vals})").format(
                        tbl=sql.Identifier(table_name),
                        cols=sql.SQL(", ").join(map(sql.Identifier, full_columns)),
                        vals=sql.SQL(", ").join(sql.Placeholder() * len(full_columns)),
                    )
                    cur.executemany(
                        stmt, list(insert_df.itertuples(index=False, name=None))
                    )

            return True

        except Exception as e:
            print(f"CSV import failed: {e}")
            return False

    def fetch_export_data(
        self, device_info: list[dict[str, str]]
    ) -> tuple[list[str], list[list[str]]]:
        tab_names = list(tab_config.keys())
        tab_max_columns: dict[str, int] = {tab: 0 for tab in tab_names}
        tab_data_per_device: dict[int, dict[str, list[list[str]]]] = {}

        with self.db.connection() as conn:
            for info in device_info:
                device_id = info["id"]
                if not info.get("process_name"):
                    continue

                tab_data_per_device[device_id] = {}

                for tab in tab_names:
                    config = tab_config.get(tab)
                    if not config:
                        continue

                    table = config.get("table")
                    columns = config.get("columns", [])
                    if not table:
                        continue

                    # ORDER BY id 필수: 자식 행의 순서가 CSV 컬럼 순서이고,
                    # PostgreSQL 은 순서를 보장하지 않는다.
                    query = sql.SQL(
                        "SELECT {cols} FROM {tbl} WHERE device_id = %s ORDER BY id"
                    ).format(
                        cols=sql.SQL(", ").join(map(sql.Identifier, columns)),
                        tbl=sql.Identifier(table),
                    )

                    try:
                        data = conn.execute(query, (device_id,)).fetchall()
                        formatted_rows = [
                            ["" if r[c] is None else str(r[c]) for c in columns]
                            for r in data
                        ]
                        tab_data_per_device[device_id][tab] = formatted_rows
                        tab_max_columns[tab] = max(
                            tab_max_columns[tab], len(formatted_rows)
                        )
                    except psycopg.Error:
                        tab_data_per_device[device_id][tab] = []

        # Build headers
        headers = ["CellType", "CdsLibName", "InstCellName"]
        for tab in tab_names:
            for _ in range(1, tab_max_columns[tab] + 1):
                headers.append(tab)

        celltype_priority = [
            "INV",
            "NFET",
            "NFETTW",
            "PFET",
            "RESISTOR",
            "VNCAP",
            "NCAP",
            "PCAP",
            "INDUCTOR",
            "PSUBDIODE",
            "NWDIODE",
            "VPNP",
            "VNPN",
            "LNPN",
            "ESDNFET",
            "ESDPSUBDIODE",
            "ESDNWDIODE",
            "ESDSCR",
        ]
        priority_map = {celltype: idx for idx, celltype in enumerate(celltype_priority)}
        device_info_sorted = sorted(
            device_info,
            key=lambda x: priority_map.get(x.get("celltype", "UNKNOWN"), float("inf")),
        )

        # Pass 2: build rows
        rows: list[list[str]] = []
        for info in device_info_sorted:
            device_id = info["id"]
            process_name = info.get("process_name") or ""
            if not process_name:
                # 1패스에서 건너뛴 device 는 2패스에서도 건너뛴다.
                continue
            celltype = info.get("celltype") or ""
            device_name = info.get("name") or ""

            row = [celltype, process_name, device_name]

            for tab in tab_names:
                tab_rows = tab_data_per_device.get(device_id, {}).get(tab, [])
                for i in range(tab_max_columns[tab]):
                    if i < len(tab_rows):
                        row.append(" ".join(tab_rows[i]))
                    else:
                        row.append("")

            rows.append(row)

        return headers, rows
