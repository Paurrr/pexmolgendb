"""키보드 입력 헬퍼. `from gui_support.keys import type_into` 로 쓴다.

편집 가능한 `QComboBox` 의 completer(K56)처럼 포커스를 가진 칸에서만 도는 동작을 보려면
`setEditText` 가 아니라 실제 키 입력이 필요하다.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit


def type_into(qtbot, line_edit: QLineEdit, text: str) -> None:
    """line_edit 의 글자를 지우고 text 를 한 글자씩 친다.

    치기 전에 창 활성화와 칸의 포커스를 기다린다. 포커스가 없는 칸에 치면 completer 가 돌지
    않아서 버그가 숨는다(수정 전에도 통과한다). 얻지 못하면 `waitUntil` 의 timeout 으로 실패한다.
    `helpers.py` 의 "기다리지 않는다" 규칙의 예외다. 결과가 아니라 동작의 전제를 기다린다.
    """
    window = line_edit.window()
    if not window.isVisible():
        window.show()
    window.activateWindow()
    qtbot.waitUntil(window.isActiveWindow)
    line_edit.setFocus()
    qtbot.waitUntil(line_edit.hasFocus)
    line_edit.selectAll()
    qtbot.keyClick(line_edit, Qt.Key_Delete)
    for char in text:
        qtbot.keyClick(line_edit, char)
