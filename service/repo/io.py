import re
import sqlite3
from collections import defaultdict
from pathlib import Path

import pandas as pd

from config.config import tab_config


class IORepository:
    def __init__(self, conn: sqlite3.Connection | None = None):
        self.conn = conn

    def get_or_create_process_id(self, process_name: str) -> int:
        if (
            process_name is None
            or pd.isna(process_name)
            or not str(process_name).strip()
        ):
            return None  # 아무것도 하지 않음

        pname = str(process_name).strip()
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO process(name) VALUES (?)", (pname,))
        self.conn.commit()

        cursor.execute("SELECT id FROM process WHERE name=?", (pname,))
        row = cursor.fetchone()
        return row[0] if row else None

    def import_data(self, input_path: str):
        try:
            data_path = Path(input_path)

            if not data_path.exists():
                return

            if not data_path.is_file():
                return

            # CSV 로드
            df = pd.read_csv(data_path)

            # DB 연결
            cursor = self.conn.cursor()

            # 결과를 저장할 리스트
            rows_to_insert = []
            rows_by_table = defaultdict(list)

            for _, row in df.iterrows():
                name = row["InstCellName"]
                celltype = row["CellType"]
                process = row["CdsLibName"]

                process_id = self.get_or_create_process_id(process)
                if process_id is None:
                    continue

                cursor.execute(
                    "INSERT INTO device (process_id, name, celltype) VALUES (?, ?, ?)",
                    (process_id, name, celltype),
                )
                device_id = cursor.lastrowid
                # print(f" Added device_info: {name}, {celltype} → id={device_id}")

                for section_name, section_info in tab_config.items():
                    table_name = section_info["table"]
                    expected_columns = section_info["columns"]
                    n_expected = len(expected_columns)
                    pattern = re.compile(rf"^{re.escape(section_name)}(?:\.\d+)?$")

                    for col in df.columns:
                        if pattern.match(col) and pd.notna(row[col]):
                            try:
                                values = row[col].strip().split()
                                if len(values) < n_expected:
                                    values += [None] * (n_expected - len(values))
                                else:
                                    values = values[:n_expected]
                                value_dict = dict(zip(expected_columns, values, strict=True))
                                rows_by_table[table_name].append(
                                    (
                                        device_id,
                                        *[value_dict[col] for col in expected_columns],
                                    )
                                )
                            except AttributeError as e:
                                print(f"AttributeError error in value {row[col]}: {e}")
                            except KeyError as e:
                                print(f"KeyError error in value {row[col]}: {e}")
                            except TypeError as e:
                                print(f"TypeError error in value {row[col]}: {e}")

            for table_name, rows_to_insert in rows_by_table.items():
                section_key = next(
                    k for k, v in tab_config.items() if v["table"] == table_name
                )
                expected_columns = tab_config[section_key]["columns"]
                full_columns = ["device_id"] + expected_columns

                insert_df = pd.DataFrame(rows_to_insert, columns=full_columns)
                insert_df.drop_duplicates(inplace=True)

                for row in insert_df.itertuples(index=False):
                    cursor.execute(
                        f"""
                            INSERT OR IGNORE INTO {table_name} (
                                {', '.join(full_columns)}
                            ) VALUES ({', '.join(['?'] * len(full_columns))})
                            """,
                        row,
                    )

            self.conn.commit()
            return True

        except Exception:
            self.conn.rollback()
            return False

    def fetch_export_data(
        self, device_info: list[dict[str, str]]
    ) -> tuple[list[str], list[list[str]]]:
        tab_names = list(tab_config.keys())
        tab_max_columns: dict[str, int] = {tab: 0 for tab in tab_names}
        tab_data_per_device: dict[int, dict[str, list[list[str]]]] = {}
        for info in device_info:
            device_id = info["id"]
            process_name = info.get("process_name", None)
            if not process_name:
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

                column_str = ", ".join(columns) if columns else "*"
                query = f"SELECT {column_str} FROM {table} WHERE device_id = ?"

                try:
                    data = self.conn.execute(query, (device_id,)).fetchall()
                    formatted_rows = [
                        ["" if field is None else str(field) for field in row_data]
                        for row_data in data
                    ]
                    tab_data_per_device[device_id][tab] = formatted_rows
                    tab_max_columns[tab] = max(
                        tab_max_columns[tab], len(formatted_rows)
                    )
                except sqlite3.Error:
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

        # 우선순위를 딕셔너리로 매핑 (빠른 lookup)
        priority_map = {celltype: idx for idx, celltype in enumerate(celltype_priority)}

        # 정렬
        device_info_sorted = sorted(
            device_info,
            key=lambda x: priority_map.get(x.get("celltype", "UNKNOWN"), float("inf")),
        )

        # Pass 2: build rows
        rows: list[list[str]] = []
        for info in device_info_sorted:
            device_id = info["id"]
            celltype = info.get("celltype") or ""
            device_name = info.get("name") or ""

            row = [celltype, process_name, device_name]

            for tab in tab_names:
                tab_rows = tab_data_per_device.get(device_id, {}).get(tab, [])
                for i in range(tab_max_columns[tab]):
                    if i < len(tab_rows):
                        row_data = tab_rows[i]
                        formatted = " ".join(
                            map(lambda v: "" if v is None else str(v), row_data)
                        )
                        row.append(formatted)
                    else:
                        row.append("")

            rows.append(row)

        return headers, rows
