# UI 가이드 (PySide6)

새 화면을 만들 일은 거의 없다. 이 문서는 버그를 고칠 때 **지금 화면 관례를 깨지 않도록** 적어 둔 것이다. 바꾸지 말고 따른다.

## 원칙
1. 업무용 도구다. 정보 밀도가 우선이고 장식은 없다.
2. 편집 중인 내용을 말없이 버리지 않는다. 버려질 상황(다른 process·device로 이동, 다시 읽기, 창 닫기, 덮어쓰기)이면 먼저 묻는다.
3. 자동으로 다시 읽지 않는다. 남이 바꾼 것은 배너로 알리고 사용자가 [새로고침]을 누른다.
4. 실패를 성공처럼 알리지 않는다. 저장이 취소되거나 일부만 됐으면 "Saved" 를 띄우지 않는다.
5. 오류는 메시지 박스와 파일 로그 양쪽에 남긴다(`utils/reporting.report`/`report_error`). 화면 문구는 `user_message(exc)` 로 만든다. `str(exc)` 금지(비밀번호가 샌다).

## 스타일과 색
- `QApplication.setStyle("Fusion")` + `utils/palette.apply_theme`. 기본 테마는 **Graphite**(어두움), 툴바 버튼으로 **Mist**(밝음)와 전환한다. 글꼴은 9pt.
- 색은 `palette.THEMES` 의 키(`window`, `panel`, `base`, `text`, `muted`, `border`, `accent`, `good`, `bad` …)만 쓴다. 위젯에 색을 직접 박지 않는다(예외: 아래 dirty 셀).

| 용도 | 값 |
|---|---|
| 편집했지만 저장 안 한 셀 | 배경 `QColor(255, 249, 196)` (`models/device_table.py`) |
| Virtuoso에 없는 device 이름 | 글자 빨강 (`known_names` 밖) |
| 저장 안 한 탭 | 탭 이름 뒤 ` *` (`views/parameter_tab.py`) |
| 성공 / 실패 | 테마의 `good` / `bad` |

## 레이아웃
```
┌ 메뉴: Database(Connect… / Save / Load CSV) ────────────────────────────────┐
│ 툴바: (빈칸) Theme | Server [    ] Port [   ] Connect | 상태               │  ← Virtuoso 소켓, DB 아님
├──────────┬─────────────────────────────────────────────────────────────────┤
│ Device   │ DeviceTabToolBar: process 콤보 +/- | Load Virtuoso | 라이브러리 … │
│ Socket   │ RefreshBanner (숨김: "이 process 가 X 님에 의해 변경되었습니다.")   │
│(History) │ QSplitter: [Device List][Filtered List] | Device Info | 파라미터 탭 │
├──────────┴─────────────────────────────────────────────────────────────────┤
│ 로그 패널 ([HH:mm:ss] 줄 단위, Clear)                                      │
└ 상태 표시줄 ───────────────────────────────────────────────────────────────┘
```
- 왼쪽 목록이 `QStackedWidget` 페이지를 고른다. History는 `--history` 로 띄웠을 때만 있다.
- 파라미터 탭 순서: `Summary`, `tab_config.json` 의 순서대로 14개, 마지막 `+`(숨긴 탭 다시 열기).
- "Device List"·"Filtered List" 는 Virtuoso 목록을 받은 뒤에만 보인다.

## 문구
- 대화상자 **제목은 영어**(`Save Complete`, `Load Failed`, `Connect Failed` …), **본문과 로그·CLI 출력은 주로 한국어**다. 섞여 있는 것이 현재 상태이고, 버그 수정 중에 기존 문구를 번역하거나 다듬지 않는다.
- 알림은 controller가 `notifyRequested(severity, title, text)` 로 올리고 `MainWindow.notify` 가 띄운다. severity는 `info` / `warn` / `critical` / 그 밖(error)이다. 로그 패널은 `logRequested`, 상태 표시줄은 `statusMessageRequested`.
- 예/아니오 질문은 `utils/dialogs.question(parent, title, message) -> bool`(Yes/No 두 개뿐, 취소 없음).
- 저장 충돌은 `dialogs/conflict.ask_conflict` 의 세 갈래: **다시 읽기**(RELOAD) / **덮어쓰기**(OVERWRITE, force) / **취소**(CANCEL, 창 닫기 포함). 충돌 목록은 `Conflict.describe()`("이름: X 님이 수정 (YYYY-MM-DD HH:MM)"). 내가 지운 행을 뺀 나머지 충돌이 전부 삭제면 덮어쓰기 버튼을 만들지 않는다(다시 읽기/취소만, 다른 문구는 그대로).
- CSV 불러오기 뒤에는 만든 device 수와 "불러올 때마다 새로 쌓인다" 를 반드시 보여준다.

## 입력과 단축키
| 키 | 어디서 | 동작 |
|---|---|---|
| Ctrl+S | 창 전체 (포커스에 따라 device 표 / 탭) | 저장 |
| `QKeySequence.Undo` / `.Redo` (Ctrl+Z / Windows Ctrl+Y, Linux Ctrl+Shift+Z) | 창 전체 (포커스에 따라) | undo / redo |
| Ctrl+C / Ctrl+V | device 표, 탭 표 | 행 복사 / 붙여넣기 |
| Ctrl+I / Ctrl+E / Ctrl+D, Delete | device 표, 탭 표 | 삽입 / 편집 / 삭제 |

- 저장·접속·CSV 불러오기 중에는 대기 커서를 띄우고 사용자 입력 이벤트를 처리하지 않는다(`run_blocking`). 위젯을 비활성화하지는 않는다.
- 값 후보와 검증은 `delegate_config.json`(`items`, `items_by_celltype`, `strict`, `required`, `pattern`, `syntax`)이 정한다. 화면에서 따로 하드코딩하지 않는다.
- device 표 붙여넣기는 바로 저장되고 목록을 다시 읽는다. 저장 안 한 device 편집이나 탭 편집이 있으면 붙여넣지 않고 경고한다(`Unsaved Changes`, 본문은 둘이 다르다. 둘 다면 device 편집 문구).
- Virtuoso 로 보내기(Run Selected / Run All)는 저장하지 않은 device 가 있으면 보내지 않고 경고한다(`Unsaved Devices`).
- 재접속(Database → Connect…)은 device 표나 탭에, CSV 불러오기는 device 표에 저장 안 한 편집이 있으면 새로고침과 같은 `Refresh` 질문을 먼저 한다. 아니오면 아무것도 하지 않는다.
- Remove Process를 확인하면 지운 process의 저장 안 한 편집은 묻지 않고 버린다(`Save Changes` 도 충돌 대화상자도 없다).
- CellType이 `delegate_config` 목록에 없는 device는 저장하지 않는다. 그런 행을 편집했으면 저장 뒤 경고(`Save Skipped`)로 이름을 알린다.
- 창 닫기: 저장 안 한 편집이 있으면 `Save Changes`(Yes/No)를 묻고, Yes면 `save_db()` 가 True일 때만 닫는다. `run_blocking` 중의 닫기는 무시한다.
- device 표 정렬(머리글 메뉴)은 모델의 모든 행을 정렬하는 undo 가능한 저장 안 한 변경이다. 프록시는 정렬하지 않고 필터는 그대로다.
- 탭 표 Insert(버튼·Ctrl+I·메뉴)는 device를 고르기 전에는 아무것도 하지 않는다. Ctrl+E는 Edit 버튼과 같은 대화상자(선택한 행 값)를 연다.

## 하지 않는 것
| 금지 | 이유 |
|---|---|
| 남이 바꿨다고 자동으로 다시 읽기 | 편집 중 내용이 말없이 사라진다 (ADR-004) |
| 워커 스레드에서 위젯·QMessageBox 만들기 | Qt는 GUI 스레드에서만 위젯을 다룬다. 결과는 시그널로 넘긴다 |
| 로그 패널에 DSN·예외 문자열을 그대로 쓰기 | 비밀번호가 화면에 찍힌다. `scrub()`/`user_message()` |
| 기존 문구·색·배치를 버그 수정 중에 바꾸기 | 이 단계는 버그만 고친다 (ADR-015) |
