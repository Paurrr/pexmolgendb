"""표를 파일로 쓴다.

**실패를 삼키지 않는다.** 한동안 두 함수가 모든 예외를 잡아 False 를 돌려줬는데,
그러면 권한이 없는 것인지, 경로가 디렉터리인지, 디스크가 찼는지를 아무도 알 수
없었다 - 화면에는 이유 없는 "Fail" 만 떴다. 예외는 부르는 쪽으로 올려보낸다.
GUI 슬롯은 utils/reporting.py 의 @report 가 메시지 박스로 바꾸고, 명령줄은
cli.py 의 main() 이 한 줄 문장으로 바꾼다.
"""

import csv
from pathlib import Path

# molgen 의 CSV 로더(genMOLDB_csv.il 의 pexGenDB_GenDev_Load_CSV_File)는 따옴표를 모르고
# 한 줄을 ',' 로만 나눈다. 따옴표로 감싼 쉼표는 그 행의 뒤 컬럼을 한 칸씩 밀고, 따옴표 안의
# 줄바꿈은 행을 가른다. 다른 열은 molgen 문법이라 쉼표가 없고, 자유 문장은 Description
# 뿐이다. 그래서 CSV 의 Description 값만 ',' 를 ';' 로, 줄바꿈을 공백으로 바꿔 쓴다
# (2026-10-18 승인). 넘겨받은 rows·xlsx·DB 값은 그대로다.
_FREE_TEXT_HEADER = "Description"


def _molgen_safe(value):
    if not isinstance(value, str):
        return value
    for newline in ("\r\n", "\r", "\n"):
        value = value.replace(newline, " ")
    return value.replace(",", ";")


# 파일 이름에 쓸 수 없는 글자(Windows 기준, '/' 는 리눅스에서도). 버전 부분만 '_' 로 바꾼다.
_PATH_UNSAFE = str.maketrans({c: "_" for c in '\\/:*?"<>|'})


def export_file_name(process: str, release: str, fmt: str) -> str:
    """내보내기 파일 이름 제안. molgen 이 찾는 `<proc>_<cid>-<ver 점 제거>.<fmt>` 다.

    molgen pexGenDB_GenDev_GetMockInfo(genMOLDB_gui.il)는 작업 디렉터리 `<proc>/<cid>-<ver>` 의
    `<cid>-<ver>` 를 '-' 로 나눠(빈 조각은 버린다) 앞 두 조각을 쓰고 `<ver>` 의 점을 지운다.
    조각이 하나면 그 조각의 점을 지운다. 조각이 없으면(빈 버전) 지금처럼 `<proc>.<fmt>` 다.
    """
    pieces = [piece for piece in release.split("-") if piece]
    if not pieces:
        return f"{process}.{fmt}"
    if len(pieces) == 1:
        tail = pieces[0].replace(".", "")
    else:
        tail = f"{pieces[0]}-{pieces[1].replace('.', '')}"
    return f"{process}_{tail.translate(_PATH_UNSAFE)}.{fmt}"


def write_csv(path: str, headers: list[str], rows: list[list[str]]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    free_text = {i for i, h in enumerate(headers) if h == _FREE_TEXT_HEADER}
    if free_text:
        rows = [
            [_molgen_safe(v) if i in free_text else v for i, v in enumerate(row)]
            for row in rows
        ]

    with open(path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def write_xlsx(path: str, headers: list[str], rows: list[list[str]]) -> None:
    try:
        from openpyxl import Workbook
    except ImportError as e:
        raise RuntimeError("Writing xlsx needs openpyxl.") from e

    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    for row_idx, values in enumerate([headers, *rows], start=1):
        ws.append(values)
        # openpyxl 은 '=' 로 시작하는 문자열을 수식으로 저장해서, 엑셀이 DB 의 값 대신
        # 계산 결과를 보여 준다. 그런 셀은 문자열 셀로 둔다(값은 글자 그대로). CSV 의
        # '=' 는 molgen 이 원문을 읽으므로 손대지 않는다. CSV 에서 바꾸는 것은
        # Description 의 쉼표·줄바꿈뿐이다(write_csv, molgen 로더가 ',' 로만 나눈다,
        # 2026-10-18 승인). xlsx 는 molgen 이 읽지 않으므로 원문이다.
        for col_idx, value in enumerate(values, start=1):
            if isinstance(value, str) and value.startswith("="):
                ws.cell(row=row_idx, column=col_idx).data_type = "s"
    wb.save(path)
