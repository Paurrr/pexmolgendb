"""device 표 내보내기 형식은 고른 파일의 확장자로 정한다 (phase 11 step 4, K16 중 내보내기 형식).

사용자 승인 2026-10-17: "GUI 내보내기 형식을 메뉴 대신 저장 파일 확장자로 정함(CLI 와 같게).
지금은 xlsx 메뉴로 a.csv 를 고르면 xlsx 바이트가 .csv 에 써짐". 확장자가 .csv / .xlsx
(대소문자 무시)가 아니면 메뉴에서 고른 형식을 따른다. 파일 이름은 바꾸지 않는다.
"""

from pathlib import Path

import pytest

ZIP_MAGIC = b"PK\x03\x04"


def ask_path(ctrl, path: Path | str) -> list[str]:
    """저장 경로 대화상자 대신 path 를 돌려준다. 제안된 파일 이름을 기록해 돌려준다."""
    suggested: list[str] = []

    def fake(name: str) -> str:
        suggested.append(name)
        return str(path)

    ctrl.device_table.ui._ask_export_path = fake
    return suggested


def written_format(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(ZIP_MAGIC):
        return "xlsx"
    first_line = data.decode("utf-8").splitlines()[0]
    assert "CellType" in first_line, first_line
    return "csv"


@pytest.mark.parametrize(
    ("fmt", "name", "expected"),
    [
        ("xlsx", "a.csv", "csv"),
        ("csv", "a.xlsx", "xlsx"),
        ("csv", "a.CSV", "csv"),
        ("xlsx", "a.CSV", "csv"),  # 대소문자 무시는 메뉴와 다를 때만 드러난다
        ("xlsx", "a", "xlsx"),
        ("csv", "a.txt", "csv"),
    ],
)
def test_the_file_suffix_decides_the_export_format(
    device_tab_ctrl, dialogs, tmp_path, fmt, name, expected
):
    ctrl = device_tab_ctrl
    assert ctrl.device_table.ui.model_safe().rowCount() > 0  # sf2p 의 device 가 보인다
    path = tmp_path / name
    suggested = ask_path(ctrl, path)

    ctrl.device_table.export_selected_devices(fmt)

    assert suggested == [f"sf2p.{fmt}"]
    assert written_format(path) == expected
    assert sorted(p.name for p in tmp_path.iterdir()) == [name]
    title = "Save XLSX" if expected == "xlsx" else "Save CSV"
    assert dialogs.shown == [("info", title, f"Success!\n - {name}")]


@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_cancelling_the_save_dialog_writes_nothing(device_tab_ctrl, dialogs, tmp_path, fmt):
    ctrl = device_tab_ctrl
    ask_path(ctrl, "")

    ctrl.device_table.export_selected_devices(fmt)

    assert list(tmp_path.iterdir()) == []
    assert dialogs.shown == []
