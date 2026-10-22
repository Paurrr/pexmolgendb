# Step 1: device-name-color

## 배경

이 저장소는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). 이 step이 고치는 것은 둘이다.
- 버그: 어두운 테마에서 device 이름이 안 보인다. 사용자가 2026-10-22에 알렸다.
- 승인된 변경: 어두운 테마의 색을 pexqa와 같게 한다. 사용자가 2026-10-22에 요청하고 승인했다.

step 0이 `utils/palette.py` 에 테마별 키 `dirty`·`unknown_name` 과 `current_colors()` 를 더했다. 먼저 그 코드와 `phases/22-dark-theme/index.json` 의 step 0 summary를 읽어라.

**버그 (주장, 2026-10-22 offscreen 렌더로 확인)**
- `models/device_table.py` `DeviceTableModel.data` 가 Name 칸(0열) `ForegroundRole` 로 테마와 상관없이 두 색을 돌려준다.
  - 알려진 이름: `QColor(Qt.black)`
  - Virtuoso에 없는 이름: `QColor(Qt.red)`
  - Graphite(어두움)에서 검정 글자가 어두운 base 위에 그려진다. 대비는 약 1.6:1이다.
- 같은 함수의 저장 안 한 셀 배경도 테마와 상관없이 `QColor(255, 249, 196)` 이다.
  - Graphite에서는 그 위에 테마의 밝은 글자가 그려진다. 대비는 약 1.13:1이다.
- `QTableView` QSS는 `color` 만 정한다. 그래서 모델의 `ForegroundRole` 이 테마 글자색을 이긴다. 선택된 행은 `selection-color` 가 이겨서 읽힌다.

**고치는 방법 (승인된 동작)**
- 알려진 이름: `ForegroundRole` 에 `None` 을 돌려준다. 그러면 테마 글자색(다른 칸과 같은 색)을 따른다.
  - Mist에서는 #000000 이 #20262d 로 바뀐다. 다른 칸과 같은 색이고 눈으로는 같다.
- 모르는 이름: `QColor(current_colors()["unknown_name"])` 다. Mist는 지금처럼 `#ff0000`, Graphite는 `#f47067` 이다.
- dirty 배경: `QColor(current_colors()["dirty"])` 다. Mist는 지금처럼 `#fff9c4`, Graphite는 `#3a3220` 이다.

규칙:
1. 버그는 **주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다. RED는 Windows 개발 PC에서 보여야 한다.
2. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
3. 고친 뒤 변이 검사를 한다. `Qt.black` 을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다. `git checkout`/`git stash` 로 되돌리지 마라.
4. 행 번호는 2026-10-22 기준 대략값이다. 이름으로 찾아라.
5. 문서(UI_GUIDE "스타일과 색" 표)는 phase 마무리에서 고친다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`: "스타일과 색"
- `src/genviewer/utils/palette.py`: step 0이 바꾼 `THEMES`, `current_colors`
- `src/genviewer/models/device_table.py`: `data`(~35-49)
- `tests/gui_support/theme.py`: step 0이 만든 `preserved_theme`
- `tests/gui/test_theme_colors.py`: step 0. 대비 계산 방식을 참고한다(import하지 말고 필요하면 따로 둔다).
- `tests/gui/test_device_sort.py`(`DIRTY` ~17, `dirty_cells` ~47-53), `tests/gui/test_window_guards.py`(`DIRTY` ~26, `dirty_cells` ~52-57)

## 작업

### 1. 실패하는 테스트 (새 파일 `tests/gui/test_device_name_color.py`)

- 모델을 직접 만든다. `DeviceTableModel(devices, known_device_names={...})` 로 알려진 이름 하나와 모르는 이름 하나를 넣는다. 셀 하나를 `setData` 로 고쳐 dirty로 만든다.
- 테마는 `preserved_theme(app)` 안에서 `apply_theme(app, "graphite")` 로 켠다.
- "실제로 그려지는 글자색"을 구하는 헬퍼를 둔다.
  - `ForegroundRole` 이 `None` 이면 `current_colors()["text"]`, 아니면 그 색이다.
  - 배경도 같다. `BackgroundRole` 이 `None` 이면 `current_colors()["base"]`.
- 테스트(수정 전에 앞의 둘이 실패해야 한다):
  - `test_known_device_name_is_readable_in_graphite`: 알려진 이름 칸의 글자/배경 대비가 4.5 이상이다.
  - `test_dirty_cell_is_readable_in_graphite`: 고친 Description 칸(글자는 None → text)의 대비가 4.5 이상이다.
  - `test_unknown_name_uses_the_theme_color`: graphite에서 `#f47067`, mist에서 `#ff0000` 이다.
  - `test_mist_dirty_background_is_unchanged`: mist에서 dirty 배경이 `QColor(255, 249, 196)` 이다.
  - `test_switching_theme_changes_model_colors`: 같은 모델에서 `apply_theme` 를 mist → graphite로 바꾸면 `data()` 가 새 테마 값을 돌려준다.

### 2. 수정 (`models/device_table.py`)

- `data` 의 두 곳만 바꾼다. 알려진 이름은 `None`, 모르는 이름은 `current_colors()["unknown_name"]`, dirty 배경은 `current_colors()["dirty"]` 다.
- `from genviewer.utils.palette import current_colors` 를 쓴다. 모델은 이미 Qt 모듈이라 경계 규칙에 걸리지 않는다.

### 3. 기존 테스트의 박힌 색

- `tests/gui/test_device_sort.py` 와 `tests/gui/test_window_guards.py` 의 `DIRTY = QColor(255, 249, 196)` 비교를 바꾼다. `dirty_cells` 가 그때의 `QColor(current_colors()["dirty"])` 와 비교하게 한다(호출 때 계산).
- 이유: 앞 테스트가 테마를 바꿨다면 결과가 테스트 순서에 따라 달라진다. step 0의 `preserved_theme` 가 되돌리지만, 비교값을 테마에서 읽어야 그것과 상관없이 맞다.

### 4. 변이 검사

- 알려진 이름을 손으로 `QColor(Qt.black)` 으로 되돌리면 `test_known_device_name_is_readable_in_graphite` 가 실패해야 한다.
- dirty를 `QColor(255, 249, 196)` 로 되돌리면 `test_dirty_cell_is_readable_in_graphite` 가 실패해야 한다.
- 둘 다 다시 고친다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_device_name_color.py -q
uv run pytest tests/gui -q
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 바꾼 `src` 가 `models/device_table.py` 의 `data` 두 곳과 import 하나뿐인가?
   - 탭 표 모델(`models/generic_table.py`)과 Device List 모델은 건드리지 않았는가? 그쪽에는 박힌 색이 없다.
3. 결과에 따라 `phases/22-dark-theme/index.json` 의 step 1을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "DeviceTableModel: 알려진 이름 None, unknown_name/dirty 는 current_colors(). tests/gui/test_device_name_color.py. RED: <테스트 이름: 단언>. DIRTY 비교 2곳은 current_colors 로. 변이: <결과>"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `utils/palette.py` 의 값을 바꾸지 마라. 이유: step 0에서 정했고 테스트로 고정했다. 대비가 모자라면 고치지 말고 summary에 적는다.
- 모델에서 테마 이름으로 분기하지 마라(`if theme == "graphite"`). 키는 `current_colors()` 로 읽는다. 이유: 테마 값은 palette.py 한 곳에서만 정한다.
- 위젯이나 delegate에 색을 직접 박지 마라. 이유: UI_GUIDE "색은 THEMES 키만" 규칙이다.
- 건드리는 파일의 기존 한국어 문구를 번역하지 마라. 이유: phase 24(영어화)의 몫이다.
- 기존 테스트를 깨뜨리지 마라.
