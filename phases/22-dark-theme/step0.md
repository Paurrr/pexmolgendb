# Step 0: graphite-palette

## 배경

이 저장소는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 22는 사용자가 2026-10-22에 요청하고 승인한 변경이다.

**요청**
- 어두운 테마(Graphite)에서 device 이름이 까매서 안 보인다.
- 밝은 테마(Mist)는 그대로 두고, 어두운 테마의 색은 형제 저장소 pexqa(`../pexqa/src/pexqa/gui/theme.py`, "Dim slate")와 같게 해 달라.

**이 step의 범위**
- `utils/palette.py` 의 graphite 값을 pexqa 토큰으로 바꾼다.
- 테마별 색 키를 새로 더한다.
- device 표 모델(`models/device_table.py`)은 step 1이 고친다. 이 step에서는 건드리지 않는다.

규칙:
1. 버그 수정이 아니라 승인된 변경이다. 그래서 RED 대신 **변이 검사**를 한다. 바꾼 값 하나를 손으로 되돌려 새 테스트가 실패하는지 본다. `git checkout`/`git stash` 로 되돌리지 마라.
2. 이 파일의 행 번호는 2026-10-22(phase 21 직후) 기준 대략값이다. 이름으로 찾아라.
3. 문서(UI_GUIDE "스타일과 색", README, ADR)는 phase 마무리에서 고친다. step에서는 바꾸지 않는다.

## 읽어야 할 파일

- `/CLAUDE.md`
- `/docs/UI_GUIDE.md`: "스타일과 색"
- `src/genviewer/utils/palette.py`(전체, ~300행): `THEMES`, `apply_theme`, `_build_palette`, `_build_stylesheet`
- `src/genviewer/controllers/main_window.py`: `_toggle_theme`, `theme_name`. 읽기만 한다.
- `src/genviewer/main.py`: `QApplication.setStyle("Fusion")` 뒤 `apply_theme(app, "graphite")`. 읽기만 한다.
- `tests/gui/conftest.py`, `tests/gui_support/`(헬퍼 배치 관례)

## 작업

### 1. pexqa 토큰 (원본 `../pexqa/src/pexqa/gui/theme.py:20-46`, 2026-10-22 확인)

```
WINDOW #22272e   BASE #1c2128   ALT_BASE #252b33   BUTTON #2d333b   BUTTON_HOVER #373e47
BUTTON_PRESSED #444c56   BORDER #444c56   HEADER #2a3038   TEXT #c9d1d9   TEXT_MUTED #8b949e
ACCENT #539bf5   HIGHLIGHT #2c4a72   HIGHLIGHTED_TEXT #f0f6fc
로그 SUCCESS #6bc46d   ERROR/PATH_MISSING #f47067   상태 WAITING 배경 #3a3220
```

### 2. `THEMES["graphite"]` 를 바꾼다

| 키 | 지금 | 새 값 (pexqa 토큰) |
|---|---|---|
| window | #1f242b | #22272e (WINDOW) |
| panel | #252b33 | #22272e (WINDOW. pexqa는 패널도 Window색이고 경계는 border로 그린다) |
| base | #2b323b | #1c2128 (BASE) |
| alternate | #303944 | #252b33 (ALT_BASE) |
| text | #e6eaee | #c9d1d9 (TEXT) |
| muted | #a9b2bd | #8b949e (TEXT_MUTED) |
| border | #46515e | #444c56 (BORDER) |
| header | #303741 | #2a3038 (HEADER) |
| button | #333b46 | #2d333b (BUTTON) |
| button_hover | #3d4652 | #373e47 (BUTTON_HOVER) |
| button_pressed | #465362 | #444c56 (BUTTON_PRESSED) |
| accent | #7aa2b8 | #539bf5 (ACCENT) |
| accent_soft | #354c5a | #2c4a72 (HIGHLIGHT) |
| accent_text | #10161c | #1c2128 (BASE. accent로 채운 Connect 단추의 글자다. pexqa에는 accent로 채우는 곳이 없다) |
| good | #77c8a3 | #6bc46d (SUCCESS) |
| bad | #df8f92 | #f47067 (ERROR) |

`name` 은 `"Graphite"` 그대로 둔다.

### 3. 새 키를 두 테마에 모두 더한다

mist 값은 지금 쓰는 색 그대로다. 그래서 Mist 화면은 바뀌지 않는다.

| 키 | mist | graphite | 쓰는 곳 |
|---|---|---|---|
| `selection` | `#2f6f73` (= mist accent) | `#2c4a72` (HIGHLIGHT) | palette `Highlight`, QSS `QWidget { selection-background-color }` |
| `selection_text` | `#ffffff` (= mist accent_text) | `#f0f6fc` (HIGHLIGHTED_TEXT) | palette `HighlightedText`, QSS `QWidget { selection-color }` |
| `dirty` | `#fff9c4` (= 지금 `QColor(255, 249, 196)`) | `#3a3220` (WAITING 배경, 노랑 계열) | 저장 안 한 셀 배경 (step 1이 쓴다) |
| `unknown_name` | `#ff0000` (= 지금 `Qt.red`) | `#f47067` (ERROR) | Virtuoso에 없는 device 이름 글자 (step 1이 쓴다) |

- `_build_palette` 의 `Highlight`·`HighlightedText` 는 `accent`·`accent_text` 대신 `selection`·`selection_text` 를 쓴다.
- `_build_stylesheet` 의 맨 위 `QWidget { selection-background-color; selection-color }` 도 이 두 키를 쓴다.
- 나머지 QSS 규칙과 palette 역할 연결은 바꾸지 않는다. 그러면 mist의 palette와 stylesheet 문자열은 바이트까지 지금과 같다. 이것을 테스트로 고정한다.

### 4. `current_colors() -> dict` 를 더한다

- `QApplication.instance()` 의 속성 `themeName`(`apply_theme` 가 남긴다)으로 `THEMES` 의 dict를 돌려준다.
- app이 없거나, 속성이 없거나, 모르는 이름이면 mist다. `apply_theme` 의 기본값과 같다.
- step 1의 모델이 `data()` 안에서 부른다. 가볍게 유지한다(dict 조회만).

### 5. 테스트

**테마 상태 헬퍼** (새 파일 `tests/gui_support/theme.py`)
- `preserved_theme(app)` 컨텍스트 매니저(또는 같은 일을 하는 fixture 헬퍼)를 만든다.
  - 들어갈 때 app의 `font()`, `palette()`, `styleSheet()`, `property("themeName")` 를 저장한다.
  - 나갈 때 그대로 되돌린다.
- 이유: 지금까지 테스트는 `apply_theme` 를 부르지 않았다. 부른 채 두면 뒤 테스트의 글꼴(레이아웃 너비)과 `current_colors()` 결과가 테스트 순서에 따라 바뀐다.
- phase 23 step 1도 이 헬퍼를 쓴다.

**새 파일 `tests/gui/test_theme_colors.py`**
- mist 고정: `THEMES["mist"]` 가 지금 dict(위 새 키 포함, 값은 위 표)와 같다. 리터럴로 적는다.
- mist 바이트 고정: 이 step 전의 `_build_stylesheet(THEMES["mist"])` 결과를 리터럴로 박는다. 길면 `hashlib.sha256` 해시로 박는다. 지금 결과가 그것과 같아야 한다.
  - 해시는 **수정 전 코드**에서 계산해 테스트에 적는다. `selection-*` 줄은 값이 같아서 바뀌지 않는다.
  - `_build_palette(THEMES["mist"])` 의 각 역할 색도 수정 전과 같아야 한다.
- graphite 값: 위 표의 pexqa 값과 같다.
- graphite 대비: 아래 쌍마다 WCAG 대비가 4.5 이상이다. 대비 계산 함수는 테스트 안에 둔다.
  - text/base, text/alternate, text/dirty, unknown_name/base, unknown_name/alternate
  - selection_text/selection, accent_text/accent, text/accent_soft
  - good/panel, bad/panel, muted/panel
- mist에는 대비 기준을 걸지 않는다. 이유: 사용자가 Mist를 바꾸지 말라고 했고, 지금 빨강 `#ff0000` 은 base 위에서 3.8이다.
- `current_colors()`:
  - `apply_theme(app, "graphite")` 뒤에는 graphite dict, `apply_theme(app, "mist")` 뒤에는 mist dict다.
  - `themeName` 이 없거나 `"bogus"` 이면 mist다.
  - `apply_theme` 를 부르는 테스트는 모두 `preserved_theme` 안에서 돈다.

### 6. 변이 검사

- graphite `base` 를 손으로 옛 값 `#2b323b` 로 되돌리면 graphite 값 테스트가 실패해야 한다. 다시 고친다.
- mist `selection` 을 다른 색으로 바꾸면 mist 고정 테스트가 실패해야 한다. 다시 고친다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_theme_colors.py -q
uv run pytest tests/gui -q
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 바꾼 `src` 가 `utils/palette.py` 하나뿐인가?
   - mist의 stylesheet·palette가 바이트까지 그대로인가(테스트가 지키는가)?
   - `utils/palette.py` 는 Qt 모듈이다. `QT_FREE_MODULES` 에 넣지 않는다.
3. 결과에 따라 `phases/22-dark-theme/index.json` 의 step 0을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "graphite=pexqa 토큰, 새 키 selection/selection_text/dirty/unknown_name(mist 는 지금 값), current_colors(), tests/gui_support/theme.py preserved_theme, tests/gui/test_theme_colors.py. 변이: <결과>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `THEMES["mist"]` 의 기존 키 값을 바꾸지 마라. 이유: 사용자가 밝은 테마는 그대로 두라고 했다.
- QSS 규칙의 구조(선택자, 속성, 순서)를 바꾸지 마라. `selection-*` 두 줄이 쓰는 키만 바꾼다. 이유: mist가 바이트까지 같아야 한다.
- `models/device_table.py` 를 고치지 마라. 이유: step 1의 일이다.
- 기본 테마(`main.py` 의 graphite), 글꼴 9pt, Theme 단추를 바꾸지 마라. 이유: 범위 밖이다. Theme 단추는 phase 23이 메뉴로 옮긴다.
- `styleHints().setColorScheme(...)` 같은 OS 색 구성 연동을 더하지 마라. 이유: 사용자가 요청하지 않았다.
- 건드리는 파일의 기존 한국어 문구를 번역하지 마라. 이유: phase 24(영어화)의 몫이고, 그쪽 테스트 수정과 섞인다.
- 기존 테스트를 깨뜨리지 마라.
