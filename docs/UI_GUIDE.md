# UI 가이드 (PySide6)

새 화면을 만들 일은 거의 없다. 이 문서는 버그를 고칠 때 **지금 화면 관례를 깨지 않도록** 적어 둔 것이다. 바꾸지 말고 따른다.

## 원칙
1. 업무용 도구다. 정보 밀도가 우선이고 장식은 없다.
2. 편집 중인 내용을 말없이 버리지 않는다. 버려질 상황(다른 process·device로 이동, 다시 읽기, 창 닫기, 덮어쓰기)이면 먼저 묻는다.
3. 자동으로 다시 읽지 않는다. 남이 바꾼 것은 배너로 알리고 사용자가 [Reload]를 누른다.
4. 실패를 성공처럼 알리지 않는다. 저장이 취소되거나 일부만 됐으면 "Saved" 를 띄우지 않는다.
5. 오류는 메시지 박스와 파일 로그 양쪽에 남긴다(`utils/reporting.report`/`report_error`). 화면 문구는 `user_message(exc)` 로 만든다. `str(exc)` 금지(비밀번호가 샌다).

## 스타일과 색
- `QApplication.setStyle("Fusion")` + `utils/palette.apply_theme`. 기본 테마는 **Graphite**(어두움), 메뉴 View → `Dark Theme`(체크 = Graphite, 끄면 **Mist**(밝음))로 전환한다. 테마를 바꾸는 길은 이것 하나라 체크 상태와 `MainWindowController.theme_name` 이 늘 같다. 저장하지 않는다. 글꼴은 9pt.
- Graphite 의 색은 pexqa `gui/theme.py` 토큰과 같다. Mist 는 phase 22 전 그대로다(ADR-019, `tests/gui/test_theme_colors.py` 가 dict·스타일시트 해시·팔레트로 고정).
- 색은 `palette.THEMES` 의 키(`window`, `panel`, `base`, `text`, `muted`, `border`, `accent`, `good`, `bad`, `selection`, `dirty`, `unknown_name` …)만 쓴다. 위젯·모델에 색을 직접 박지 않는다. 모델은 `palette.current_colors()` 로 지금 테마의 키를 읽는다(테마 이름으로 분기하지 않는다).

| 용도 | 값 |
|---|---|
| 편집했지만 저장 안 한 셀 | 배경 `dirty` (Mist `#fff9c4`, Graphite `#3a3220`, `models/device_table.py`) |
| Virtuoso에 없는 device 이름 | 글자 `unknown_name` (Mist `#ff0000`, Graphite `#f47067`, `known_names` 밖) |
| 알려진 device 이름 | 색을 정하지 않는다(다른 칸과 같은 테마 `text`) |
| 선택 | `selection` / `selection_text` (palette `Highlight`, QSS `selection-*`) |
| 저장 안 한 탭 | 탭 이름 뒤 ` *` (`views/parameter_tab.py`) |
| 성공 / 실패 | 테마의 `good` / `bad` |

## 레이아웃
```
┌ 메뉴: Database | Edit | View ──────────────────────────────────────────────┐
│ 툴바: (빈칸) **Virtuoso** Server [    ] Port [   ] Connect | 상태          │  ← Virtuoso 소켓, DB 아님
├──────────┬─────────────────────────────────────────────────────────────────┤
│ Device   │ DeviceTabToolBar: Process [▾] Version [▾] +/- | Load Virtuoso | … │
│ Socket   │ RefreshBanner (숨김: "This process was changed by X.")              │
│(History) │ QSplitter: [Device List][Filtered List] | Device Info | 파라미터 탭 │
├──────────┴─────────────────────────────────────────────────────────────────┤
│ 로그 패널 ([HH:mm:ss] 줄 단위, Clear)                                      │
└ 상태 표시줄 (2초 문구) ─────────────────── DB: host=… dbname=… user=… ┘
```
- 메뉴(phase 23)
  - Database: `Connect...`, ─, `Save`, ─, `Load CSV...`, `Export Selected Devices...`
  - Edit: `Undo` / `Redo`. 창 동작(단축키)과 **같은 QAction** 이라 메뉴에서 눌러도 포커스 쪽(device 표 / 탭)을 되돌린다.
  - View: 체크 가능한 `Dark Theme`
  - 메뉴 `Save` 에는 단축키를 보이지 않는다. 메뉴 Save 는 device 표와 탭을 전부(`save_db`), Ctrl+S 는 포커스 쪽만 저장한다.
  - `Export Selected Devices...` 는 device 표 오른쪽 클릭 Export 와 같은 `export_selected_devices` 다. 고른 행이 없으면 표의 모든 device 를 낸다(`get_selected_devices` 의 `fallback_to_all`). 표가 비면 `Export` / `No device selected.` 경고다.
  - 메뉴 동작에는 활성/비활성 조건이 없다. 각 함수가 안 될 때 스스로 알린다.
- 위 툴바의 Server·Port·Connect 앞에 굵은 `Virtuoso` 라벨이 있고, Connect 툴팁은 `Connect to the Virtuoso socket` 이다(메뉴 Database → Connect... 는 DB 접속).
- 상태 표시줄 오른쪽 영구 라벨(`DbStatus`)이 지금 붙은 DB 를 늘 보인다. 글자는 `DB: <diagnostics.target_summary(dsn)>`(host·port·dbname·user 화이트리스트. DSN 을 직접 자르거나 쓰지 않는다) 또는 `DB: not connected` 다. 색은 Virtuoso 상태 라벨과 같은 `connected` 속성 + good/bad 다. `MainWindowController` 가 `dbChanged` 로 갱신한다(재접속이 실패하면 옛 대상 그대로).
- 왼쪽 목록이 `QStackedWidget` 페이지를 고른다. History는 `--history` 로 띄웠을 때만 있다.
- 파라미터 탭 순서: `Summary`, `tab_config.json` 의 순서대로 14개, 마지막 `+`(숨긴 탭 다시 열기).
- "Device List"·"Filtered List" 는 Virtuoso 목록을 받은 뒤에만 보인다.
- Version 콤보는 지금 이름의 버전만 보인다. 빈 버전은 `(none)` 으로 보이고 맨 앞이다(ADR-018). 이름을 바꾸면 같은 버전 문자열이 있으면 그것을, 없으면 그 이름의 첫 버전을 고른다. Version 콤보가 Process 콤보보다 넓다(최소 160 / 120px, 합이 같아 창 최소 너비는 그대로, phase 25).
- 창은 DeviceTabToolBar 의 최소 너비보다 좁아지지 않는다(툴바 가로 정책 `Preferred`. `Ignored` 면 고정 너비 단추·콤보가 겹친다, K57 phase 21). 화면이 그보다 좁으면 창 오른쪽이 화면 밖으로 나간다. `»` 넘침 메뉴·가로 스크롤·두 줄 배치는 쓰지 않는다.

## 문구
- 사용자에게 보이는 문구는 **영어**다(ADR-020). GUI, CLI, `tools/*.sh` 출력이 모두 그렇다.
  - 한국어로 두는 것: 주석, docstring(typer 명령 docstring 은 `--help` 라 영어), 로그 파일에만 가는 문구, 이력 요약(`change_log.summary`).
  - 화면 문구는 phase 24 가 모두 옮겼다. 새 문구는 처음부터 영어로 쓴다. `tests/test_english_text.py` 가 한글 문구를 막는다.
  - 한국어 글자에 맞춰 둔 고정 너비(`setFixedWidth`)는 영어 글자를 자를 수 있다. 단추 글자를 바꾸면 `sizeHint` 보다 좁지 않은지 본다(phase 24 의 변경 배너 단추).
  - 버그 수정 중에 기존 문구를 번역하거나 다듬지 않는다.
- 문장 규칙
  - 제목, 단추, 메뉴는 Title Case 다(`Save Conflict`, `Load CSV...`).
  - 본문 문장은 마침표로 끝난다. 질문은 `... Continue?` 처럼 묻는다.
  - 상태 표시줄 문구는 마침표가 없다(`Device table saved`).
  - 개수는 `{n} device(s)`, `{n} row(s)` 로 쓴다.
  - ASCII 만 쓴다. em dash 를 쓰지 않는다. 이유: cp949 콘솔이 그 글자를 출력하지 못한다.
  - 이미 영어인 문구는 바꾸지 않는다.
- 용어표 (따로 도는 step 이 같은 말을 쓰게 한다)

| 한국어 | 영어 |
|---|---|
| 저장하지 않은 편집 | unsaved changes |
| 서버 내용으로 다시 읽기 | reload from the server |
| 충돌 대화상자 단추 다시 읽기 / 내 변경으로 덮어쓰기 / 취소 | Reload / Overwrite with Mine / Cancel |
| 배너 단추 새로고침 / 닫기 | Reload / Dismiss |
| History 단추 새로고침 | Refresh |
| (없음) 빈 버전 | (none) |
| (복사 안 함) | (no copy) |
| (전체) | (all) |
| (모름) | (unknown) |
| 다른 사용자 | another user |
| X 님이 수정 / 삭제 / 변경 | modified / deleted / changed by X |
| 먼저 저장할 것 | Save first. |
| 먼저 DB를 Load 해야 합니다 | Connect to the database first. |
| CLI 의 `오류:` / `중단했다.` | `error:` / `Aborted.` |
- 알림은 controller가 `notifyRequested(severity, title, text)` 로 올리고 `MainWindow.notify` 가 띄운다. severity는 `info` / `warn` / `critical` / 그 밖(error)이다. 로그 패널은 `logRequested`, 상태 표시줄은 `statusMessageRequested`.
- 예/아니오 질문은 `utils/dialogs.question(parent, title, message) -> bool`(Yes/No 두 개뿐, 취소 없음).
- 저장 충돌은 `dialogs/conflict.ask_conflict` 의 세 갈래: **Reload**(RELOAD) / **Overwrite with Mine**(OVERWRITE, force) / **Cancel**(CANCEL, 창 닫기 포함). 충돌 목록은 `Conflict.describe()`("name: modified by X (YYYY-MM-DD HH:MM)"). 내가 지운 행을 뺀 나머지 충돌이 전부 삭제면 Overwrite with Mine 단추를 만들지 않는다(Reload/Cancel 만, 다른 문구는 그대로).
- CSV 불러오기 뒤에는 만든 device 수와 "CSV import always adds new rows" 를 반드시 보여준다.

## 입력과 단축키
| 키 | 어디서 | 동작 |
|---|---|---|
| Ctrl+S | 창 전체 (포커스에 따라 device 표 / 탭) | 저장 |
| `QKeySequence.Undo` / `.Redo` (Ctrl+Z / Windows Ctrl+Y, Linux Ctrl+Shift+Z) | 창 전체 (포커스에 따라) | undo / redo (Edit 메뉴와 같은 동작) |
| Ctrl+C / Ctrl+V | device 표, 탭 표 | 행 복사 / 붙여넣기 |
| Ctrl+I / Ctrl+E / Ctrl+D, Delete | device 표, 탭 표 | 삽입 / 편집 / 삭제 |

- 저장·접속·CSV 불러오기 중에는 대기 커서를 띄우고 사용자 입력 이벤트를 처리하지 않는다(`run_blocking`). 위젯을 비활성화하지는 않는다.
- 값 후보와 검증은 `delegate_config.json`(`items`, `items_by_celltype`, `strict`, `required`, `pattern`, `syntax`)이 정한다. 화면에서 따로 하드코딩하지 않는다.
- device 표 붙여넣기는 바로 저장되고 목록을 다시 읽는다. 저장 안 한 device 편집이나 탭 편집이 있으면 붙여넣지 않고 경고한다(`Unsaved Changes`, 본문은 둘이 다르다. 둘 다면 device 편집 문구).
- Virtuoso 로 보내기(Run Selected / Run All)는 저장하지 않은 device 가 있으면 보내지 않고 경고한다(`Unsaved Devices`).
- device 표 내보내기는 고른 파일의 확장자(.csv / .xlsx)로 형식을 정한다. 둘 다 아니면 메뉴에서 고른 형식이다.
- 재접속(Database → Connect…)은 device 표나 탭에, CSV 불러오기는 device 표에 저장 안 한 편집이 있으면 새로고침과 같은 `Refresh` 질문을 먼저 한다. 아니오면 아무것도 하지 않는다.
- Remove Process(`-`)는 지금 (이름, 버전) 쌍 하나만 지운다. 확인은 controller 의 `Remove Process` 질문 한 번이다(device 수를 알리고, 문구에 `sf2p V2` 처럼 버전이 붙는다. phase 23 전에는 view 가 `Confirm Delete` 를 먼저 물었다). 확인하면 지운 쌍의 저장 안 한 편집은 묻지 않고 버린다(`Save Changes` 도 충돌 대화상자도 없다).
- Add Process(`+`)는 `Add Process` 창(Process 편집 콤보, Version 칸, Copy from 콤보 — 기본 `(no copy)`)을 연다. 이름이 비었거나, 버전이 `(none)` 이거나, 이미 있는 쌍이면 OK 가 꺼지고 뒤의 둘은 창 안에 이유 한 줄을 보인다(메시지 상자 없음). 저장 안 한 편집이 있으면 만들기 전에 `Save Changes` 를 묻고, 저장이 취소·실패하면 아무것도 만들지 않는다.
- Load CSV 는 파일을 고른 뒤 `Load CSV` 질문으로 버전을 묻는다(있는 버전 목록 + 직접 입력, 처음 값은 지금 버전, `(none)`·빈칸은 버전 없음). 불러온 뒤에도 지금 쌍에 머문다.
- 이름·버전을 치는 편집 가능 콤보(Add Process 의 Process 칸, Load CSV 의 버전 칸)는 Qt 기본 completer 를 끈다(`setCompleter(None)`). 친 글자 그대로이고 Enter 도 대소문자까지 같은 항목만 고른다(K56, phase 20). 정적 `QInputDialog.getItem(editable=True)` 은 completer 를 끌 수 없어서 쓰지 않는다.
- device 표 내보내기의 제안 파일 이름은 버전이 있으면 molgen 이 찾는 `<proc>_<cid>-<ver 점 제거>.csv` 다(예: `sf2p S00-V1.0.0.0` → `sf2p_S00-V1000.csv`).
- CellType이 `delegate_config` 목록에 없는 device는 저장하지 않는다. 그런 행을 편집했으면 저장 뒤 경고(`Save Skipped`)로 이름을 알린다.
- 창 닫기: 저장 안 한 편집이 있으면 `Save Changes`(Yes/No)를 묻고, Yes면 `save_db()` 가 True일 때만 닫는다. `run_blocking` 중의 닫기는 무시한다.
- device 표 정렬(머리글 메뉴)은 모델의 모든 행을 정렬하는 undo 가능한 저장 안 한 변경이다. 프록시는 정렬하지 않고 필터는 그대로다.
- 필터가 켜진 상태에서 고른 행이 실제 목록에서 떨어져 있으면(사이 행이 숨어 있으면) 끌어 놓기를 받지 않는다.
- 탭 표 Insert(버튼·Ctrl+I·메뉴)는 device를 고르기 전에는 아무것도 하지 않는다. Ctrl+E는 Edit 버튼과 같은 대화상자(선택한 행 값)를 연다.

## 하지 않는 것
| 금지 | 이유 |
|---|---|
| 남이 바꿨다고 자동으로 다시 읽기 | 편집 중 내용이 말없이 사라진다 (ADR-004) |
| 워커 스레드에서 위젯·QMessageBox 만들기 | Qt는 GUI 스레드에서만 위젯을 다룬다. 결과는 시그널로 넘긴다 |
| 로그 패널에 DSN·예외 문자열을 그대로 쓰기 | 비밀번호가 화면에 찍힌다. `scrub()`/`user_message()` |
| 기존 문구·색·배치를 버그 수정 중에 바꾸기 | 이 단계는 버그만 고친다 (ADR-015) |
