import csv
from pathlib import Path


def write_csv(path: str, headers: list[str], rows: list[list[str]]) -> bool:
    try:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        return True
    except Exception:
        return False


def write_xlsx(path: str, headers: list[str], rows: list[list[str]]) -> bool:
    try:
        from openpyxl import Workbook
    except ImportError:
        return False

    try:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        wb = Workbook()
        ws = wb.active
        ws.append(headers)
        for row in rows:
            ws.append(row)
        wb.save(path)
        return True
    except Exception:
        return False
