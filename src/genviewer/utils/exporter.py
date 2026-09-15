"""표를 파일로 쓴다.

**실패를 삼키지 않는다.** 한동안 두 함수가 모든 예외를 잡아 False 를 돌려줬는데,
그러면 권한이 없는 것인지, 경로가 디렉터리인지, 디스크가 찼는지를 아무도 알 수
없었다 - 화면에는 이유 없는 "Fail" 만 떴다. 예외는 부르는 쪽으로 올려보낸다.
GUI 슬롯은 utils/reporting.py 의 @report 가 메시지 박스로 바꾸고, 명령줄은
cli.py 의 main() 이 한 줄 문장으로 바꾼다.
"""

import csv
from pathlib import Path


def write_csv(path: str, headers: list[str], rows: list[list[str]]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def write_xlsx(path: str, headers: list[str], rows: list[list[str]]) -> None:
    try:
        from openpyxl import Workbook
    except ImportError as e:
        raise RuntimeError("xlsx 로 쓰려면 openpyxl 이 필요하다.") from e

    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    wb.save(path)
