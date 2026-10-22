# Step 0: toolbar-min-width

## 배경

이 저장소는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 21은 K57을 고친다. K57은 사용자가 phase 19 GUI 손 확인을 하다가 찾았다. 사용자가 2026-10-22에 버그로 정하고 고치는 방법도 골랐다. 사용자에게 보이는 문구는 바꾸지 않는다.

**K57.** 창을 줄이면 Device 탭 툴바(`DeviceTabControlToolBar`)의 위젯이 서로 겹친다. 이 툴바는 `Process [▾] Version [▾] [+] [-] Load Virtuoso | Library [▾] [+] Load Libs | Gen Layout [Off] | Run [Selected] [All]` 줄이다.
- 원인은 `views/device_tab_toolbar.py` `DeviceTabToolBar.__init__` 의 두 줄이다: `self.setMinimumSize(0, 0)` 과 `self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)`.
  - 가로 정책이 `Ignored` 라서 부모 레이아웃이 툴바의 최소 너비를 모른다. 그래서 창이 툴바보다 좁아질 수 있다.
  - 툴바 안의 단추는 너비가 고정이고(`setFixedWidth`), 콤보는 최소 너비(160/120/150)가 있다. 그래서 툴바가 좁게 잡혀도 이것들은 줄지 않고 서로 겹친다.
- 원래 코드부터 그랬다(`ec15565`). phase 19가 Version 라벨과 콤보를 더해 툴바 최소 너비가 약 210px 늘었고, 그만큼 더 넓은 창에서부터 겹친다.
- 겹치는 곳은 이 툴바뿐이다. 창 전체를 재 보니 다른 부모 아래에서 겹치는 형제 위젯은 없었다. QTabBar 스크롤 단추가 탭 위에 얹히는 것은 Qt의 원래 모양이다.

**사용자가 고른 동작** (2026-10-22, AskUserQuestion: "창 최소 너비를 툴바에 맞춤")
- 창은 툴바의 최소 너비보다 좁아지지 않는다. 툴바 위젯은 겹치지 않는다.
- 화면이 그보다 좁으면 창 오른쪽이 화면 밖으로 나가는 것을 받아들인다.
- 하지 않는 것: QToolBar `»` 넘침 메뉴, 가로 스크롤, 두 줄 배치.

**확인한 사실** (2026-10-22, 개발 PC, PySide6 6.9.3)
- 실제 Windows 플랫폼(맑은 고딕 9pt, Fusion, `apply_theme`)
  - 툴바 레이아웃 최소 너비는 1163px다.
  - 창의 나머지(왼쪽 목록 96 + Device Info + 빈 파라미터 탭)는 그보다 훨씬 좁다. 그래서 창 너비가 약 1260px보다 작으면 툴바가 겹친다.
  - 기본 창 1200px에서도 조금 겹친다.
- offscreen(테스트 환경, 글꼴 Sans Serif)
  - 툴바 레이아웃 최소 너비는 1373px다.
  - `MainWindow("localhost")` 를 기본 크기 1200으로 띄우면 툴바는 1102px를 받고 직계 자식 6쌍이 겹친다.
  - `resize(800, 700)` 이면 창은 779까지 줄고 겹치는 쌍이 늘어난다.
- 가로 정책만 `QSizePolicy.Preferred` 로 바꿔 보면(세로 `Fixed` 그대로) 겹침이 0이 된다.
  - offscreen에서 창 최소 너비가 1471이 되고, 기본 1200으로 띄워도 1471로 커진다. `resize(800, 700)` 도 1471에서 멈춘다.
  - 긴 process 이름이나 버전을 넣어도 겹치지 않는다. 콤보(`AdjustToContents`, `Preferred`)는 최소 너비까지만 줄고 툴바 최소 너비는 그대로다.
- `setMinimumSize(0, 0)` 은 영향이 없다. Qt는 0보다 큰 명시 최소값만 쓴다(qSmartMinSize). 그래서 정책만 바꾸면 된다.
- **`main_window` fixture로는 재현되지 않는다.**
  - 컨트롤러가 채운 Device Info(최소 550)와 파라미터 탭(최소 884) 때문에, offscreen에서는 창 최소 너비가 이미 1536이다. 툴바보다 넓어서 수정 전에도 겹치지 않는다.
  - 그래서 테스트는 컨트롤러 없이 `MainWindow("localhost")` 를 직접 만든다. 이때 파라미터 탭은 비어 있는데, 실제 앱도 device를 고르기 전에는 그렇다.
  - 이 방식으로 만든 세 테스트가 수정 전에 3개 모두 실패하고, 정책만 바꾸면 3개 모두 통과했다.

규칙:
1. 버그는 **주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 변이 검사를 한다.
   - 정책을 손으로 `Ignored` 로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다.
   - `git checkout`/`git stash` 로 되돌리지 마라.
5. 이 파일의 행 번호는 2026-10-22(phase 20 직후) 기준 대략값이다. 이름으로 찾아라.
6. 문서(UI_GUIDE "레이아웃", README)는 phase 마무리에서 고친다. step에서는 바꾸지 않는다.

**GUI 테스트 기반**
- 작업 전에 `tests/gui/conftest.py` 와 `tests/gui_support/` 를 읽는다. 이 파일의 서술과 다르면 실제 코드를 따른다.
- 고정 대기(`qtbot.wait`)는 쓰지 않는다. 레이아웃은 `QCoreApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)` 로 확정한 뒤 단언한다.
- 겹침 단언에 픽셀 숫자를 박지 않는다. 글꼴(앞 테스트가 `apply_theme` 를 불렀는지)에 따라 너비가 달라진다.

## 읽어야 할 파일

- `/CLAUDE.md`
- `/docs/UI_GUIDE.md`: "레이아웃"
- `src/genviewer/views/device_tab_toolbar.py`: `DeviceTabToolBar.__init__`(~29-146), `set_pairs`, `current_pair`
- `src/genviewer/views/device_tab.py`: `DeviceTab.__init__`. 툴바가 `QVBoxLayout` 맨 위에 있다. 읽기만 한다.
- `src/genviewer/views/main_window.py`: `MainWindow.__init__`(`resize(1200, 700)`, `setMinimumSize(0, 0)`). 읽기만 한다.
- `tests/gui/conftest.py`: `main_window` fixture. 이 버그에는 쓰지 않는 이유가 위에 있다.

## 버그

```python
self.setMinimumSize(0, 0)
self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)   # 부모가 툴바 최소 너비를 모른다
self.setFixedHeight(34)
```

이것은 주장이다. 먼저 재현하라.

## 작업

### 1. 실패하는 테스트 (`tests/gui/test_toolbar_min_width.py`, 새 파일)

공통:
- 창은 `MainWindow("localhost")` 를 직접 만들고 `qtbot.addWidget(ui)` 한 뒤 `ui.show()` + `qtbot.waitExposed(ui)` 로 띄운다. 컨트롤러는 붙이지 않는다(DB 없음).
- 툴바는 `ui.device_tab_view.device_tab_toolbar_view` 다.
- 헬퍼 `_overlapping(toolbar) -> list[tuple[str, str]]`
  - 툴바의 **직계** 자식 중 `isVisible()` 인 `QWidget` 끼리 `geometry().intersects` 인 쌍을 돌려준다.
  - 실패 메시지에서 알아볼 수 있게 위젯 글자나 타입 이름을 담는다.
- 단언 전에 `QCoreApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)` 로 레이아웃을 확정한다.

테스트(셋 다 수정 전에 실패해야 한다):
- `test_toolbar_widgets_do_not_overlap_at_the_default_size`: 띄운 그대로(기본 1200×700) `_overlapping(toolbar) == []`.
- `test_shrinking_the_window_keeps_toolbar_widgets_apart`
  - `ui.resize(800, 700)` 뒤 `_overlapping(toolbar) == []` 다.
  - `toolbar.width() >= toolbar.layout().minimumSize().width()` 다.
- `test_long_names_keep_toolbar_widgets_apart`
  - `toolbar.set_pairs([("sf2p", ""), (<30자 넘는 이름>, <30자 넘는 버전>)])` 로 긴 쌍을 넣는다.
  - 그 쌍을 콤보로 고르고(`current_pair()` 가 그 쌍인지 먼저 단언한다) `ui.resize(800, 700)` 한다.
  - 그 뒤 `_overlapping(toolbar) == []` 다.

### 2. 수정 (`views/device_tab_toolbar.py`)

- `DeviceTabToolBar.__init__` 의 `self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)` 를 `QSizePolicy.Preferred, QSizePolicy.Fixed` 로 바꾼다.
- 그 위에 한국어 주석 한 줄을 단다. 예: `# Ignored 면 창이 툴바보다 좁아져 고정 너비 단추·콤보가 겹친다(K57).`
- 다른 것은 바꾸지 않는다.

### 3. 변이 검사

- 정책을 `Ignored` 로 되돌려 새 테스트 3개가 실패하는지 본다. 다시 `Preferred` 로 둔다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_toolbar_min_width.py -q
uv run pytest tests/gui -q
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 바꾼 `src` 가 `device_tab_toolbar.py` 의 정책 한 줄과 주석뿐인가?
   - 문구, 단추·콤보의 너비, 순서가 그대로인가?
   - 기존 GUI 테스트(`test_toolbar_pairs_view.py`, `test_add_release.py`, `test_load_csv_release.py` 등)가 바뀌지 않고 통과하는가?
3. 결과에 따라 `phases/21-toolbar-min-width/index.json` 의 step 0을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "DeviceTabToolBar 가로 정책 Ignored→Preferred(창 최소 너비가 툴바를 따른다). tests/gui/test_toolbar_min_width.py(MainWindow 직접, 컨트롤러 없음). RED: <테스트 이름: 단언>. 변이: <결과>"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `views/main_window.py` 를 고치지 마라(`setMinimumSize(0, 0)`, `resize(1200, 700)` 포함). 이유: 창 최소 크기는 이미 레이아웃을 따른다. 막힌 곳은 툴바의 `Ignored` 하나다.
- 툴바의 `setMinimumSize(0, 0)` 줄을 지우지 마라. 이유: 효과가 없고 범위 밖이다.
- 콤보 최소 너비, 단추 고정 너비, `setFixedHeight(34)`, 문구, 위젯 순서, 간격을 바꾸지 마라. 이유: 버그 수정 범위가 아니고, 사용자가 모양을 바꾸자고 하지 않았다.
- 툴바를 `QToolBar` 로 바꾸거나 `QScrollArea` 로 감싸거나 두 줄로 나누지 마라. 이유: 사용자가 고르지 않은 동작이다.
- 테스트에 `main_window` fixture를 쓰지 마라. 이유: 그 창은 다른 칸 때문에 이미 툴바보다 넓어서 수정 전에도 통과한다.
- 단언에 픽셀 숫자(1373, 1471 등)를 박지 마라. 이유: 글꼴에 따라 다르다(실제 Windows는 1163).
- 기존 테스트를 깨뜨리지 마라.
