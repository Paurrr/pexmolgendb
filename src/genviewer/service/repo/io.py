import re
from collections import defaultdict
from pathlib import Path

import pandas as pd
from psycopg import sql

from genviewer.config.config import delegate_config, tab_config
from genviewer.service.pool import Database


def split_cell(
    text: str, n_columns: int, parse: str, row_per_token: bool = False
) -> list[list[str]]:
    """CSV 셀 하나를 자식 행 목록으로 나눈다.

    규칙의 원본은 molgen 이다. genMOLDB_config.il 의
    pexGenDB_GenDev_Get_Header_Type() 이 컬럼마다 변환 타입을 선언하고
    genMOLDB_csv.il:399-409 가 그것을 구현한다. tab_config.json 의 "parse" 는
    그 표를 옮겨 적은 것이므로 두 파일을 나란히 놓고 대조할 수 있다.

    예전에는 타입과 무관하게 전부 공백으로 쪼갠 뒤 컬럼 수만큼 잘라냈다.
    그래서 "grLayer RX Only" 가 ("grLayer", "RX") 가 되고 "Only" 가 조용히
    사라졌다. 어느 타입에서도 토큰을 버리지 않는 것이 이 함수의 계약이다.
    """
    if parse == "string":
        # 셀 전체가 값 하나다. 쪼개지 않는다.
        values = [text]
    elif parse == "parseStringToVariableValue":
        # 첫 토큰이 이름, 나머지 전체가 값 하나 (공백 유지).
        values = text.split(None, 1)
    elif row_per_token:
        # 셀이 토큰 목록이다 (ForcedInstSchParam). 토큰 하나가 행 하나.
        return [[tok] for tok in text.split()]
    else:
        # 위치 슬롯. 마지막 컬럼이 남은 토큰을 전부 흡수한다.
        values = text.split(None, n_columns - 1)

    values = values[:n_columns]
    values += [""] * (n_columns - len(values))
    return [values]


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

    def import_data(self, input_path: str) -> int:
        """CSV 를 읽어 device 와 탭 테이블에 넣는다. 새로 만든 device 수를 낸다.

        **CSV 행 하나가 device 하나다.** 같은 (CdsLibName, InstCellName) 이 여러
        행에 나와도 각각 별개의 device 가 된다 — 현장 CSV 에서 그것은 정상이다.
        예전에는 ON CONFLICT (process_id, name) 으로 같은 device 에 밀어 넣었고,
        자식 행 삭제가 행 루프 **뒤에** 한 번만 돌았기 때문에 결과가 교체가 아니라
        두 행의 연결이 됐다. 화면에서는 한 탭에 두 행의 내용이 섞여 보였다.

        그래서 재임포트는 멱등하지 않다. 같은 파일을 두 번 넣으면 device 가 두 배가
        된다. 부르는 쪽이 만들어진 개수를 사용자에게 보여줘야 그것을 알아챈다.

        실패하면 예외를 그대로 올려보낸다. 예전에는 여기서 print 하고 False 를
        돌려줬는데, 배포본에는 터미널이 없어서 원인이 아무 데도 남지 않았다.
        """
        data_path = Path(input_path)
        if not data_path.is_file():
            raise FileNotFoundError(f"CSV 파일이 없다: {data_path}")

        # dtype=str: 숫자로 보이는 컬럼이 int64 로 추론되면 셀을 문자열로
        # 다룰 수 없어 통째로 버려졌다.
        # keep_default_na=False: 값이 "NA"/"NULL"/"None" 인 셀은 정상적인
        # 파라미터 값인데 NaN 이 되어 걸러졌다.
        df = pd.read_csv(data_path, dtype=str, keep_default_na=False)

        # 섹션별 메타데이터와 매칭되는 CSV 컬럼을 한 번만 계산한다.
        # 헤더는 molgen 규약대로 같은 이름이 반복되고(CSV_COLUMNS.md 0절),
        # pandas 는 그것을 "AddFGR", "AddFGR.1" 로 구분해 읽는다.
        sections = []
        for section_name, section_info in tab_config.items():
            matched = [
                col
                for col in df.columns
                if re.fullmatch(rf"{re.escape(section_name)}(?:\.\d+)?", col)
            ]
            if matched:
                sections.append((section_info, matched))

        created = 0
        with self.db.connection() as conn:
            cur = conn.cursor()
            rows_by_table: dict[str, list[tuple]] = defaultdict(list)

            for _, row in df.iterrows():
                process_id = self._process_id(cur, row["CdsLibName"])
                if process_id is None:
                    continue

                device_row = cur.execute(
                    "INSERT INTO device (process_id, name, celltype) "
                    "VALUES (%s, %s, %s) RETURNING id",
                    (process_id, row["InstCellName"], row["CellType"]),
                ).fetchone()
                device_id = device_row["id"]
                created += 1

                for section_info, matched in sections:
                    n_columns = len(section_info["columns"])
                    parse = section_info.get("parse", "parseString")
                    row_per_token = section_info.get("row_per_token", False)

                    for col in matched:
                        cell = str(row[col]).strip()
                        if not cell:
                            continue
                        for values in split_cell(cell, n_columns, parse, row_per_token):
                            rows_by_table[section_info["table"]].append(
                                (device_id, *values)
                            )

            # 자식 행을 미리 지우지 않는다. device 가 전부 방금 만들어진 것이라
            # 지울 것이 없다. 예전의 삭제 루프는 CSV 에 없는 섹션까지 포함해 자식
            # 테이블 14개를 전부 비웠기 때문에, AddLayer 컬럼이 빠진 CSV 를 넣으면
            # 기존 add_layers 행이 같이 사라졌다.
            columns_by_table = {
                info["table"]: info["columns"] for info in tab_config.values()
            }
            for table_name, to_insert in rows_by_table.items():
                # 중복 제거를 하지 않는다. 같은 자식 행이 두 번 나오는 것은
                # molgen 에서 적법하다 — 같은 이름의 컬럼 반복이 곧 항목
                # 반복이다 (CSV_COLUMNS.md 0절). 예전에는 둘 중 하나가
                # 조용히 사라졌다.
                full_columns = ["device_id"] + columns_by_table[table_name]
                stmt = sql.SQL("INSERT INTO {tbl} ({cols}) VALUES ({vals})").format(
                    tbl=sql.Identifier(table_name),
                    cols=sql.SQL(", ").join(map(sql.Identifier, full_columns)),
                    vals=sql.SQL(", ").join(sql.Placeholder() * len(full_columns)),
                )
                cur.executemany(stmt, to_insert)

        return created

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

                    # DB 에러를 삼키고 빈 탭을 내보내지 않는다. 그러면 내용이
                    # 빠진 CSV 가 조용히 만들어지고 아무도 알아채지 못한다.
                    data = conn.execute(query, (device_id,)).fetchall()
                    formatted_rows = [
                        ["" if r[c] is None else str(r[c]) for c in columns]
                        for r in data
                    ]
                    tab_data_per_device[device_id][tab] = formatted_rows
                    tab_max_columns[tab] = max(tab_max_columns[tab], len(formatted_rows))

        # Build headers
        headers = ["CellType", "CdsLibName", "InstCellName"]
        for tab in tab_names:
            for _ in range(1, tab_max_columns[tab] + 1):
                headers.append(tab)

        # 정렬 우선순위는 delegate_config 의 celltype 목록에서 가져온다.
        # 예전에는 여기에 목록을 한 번 더 적어두고 있어서 두 곳이 어긋났고,
        # 목록에 없는 celltype 은 전부 맨 뒤로 밀렸다.
        celltype_priority = (
            delegate_config.get("device", {}).get("celltype", {}).get("items", [])
        )
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
