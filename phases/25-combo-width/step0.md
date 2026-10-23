# Step 0: version-combo-width

## 배경

이 저장소는 **에러·버그만 고친다**(CLAUDE.md). 이 step은 사용자가 2026-10-23에 요청하고 승인한 화면 변경이다. 버그 수정이 아니므로 "재현되지 않으면 고치지 않는다" 규칙 대신 아래 실패하는 테스트를 먼저 쓰고(TDD) 고친다.

**요청**: Device 탭 툴바의 Version 콤보가 Process 콤보보다 넓어야 한다. process 이름은 대개 10글자 안이고, 버전은 `S00-V1.0.0.0` 처럼 더 길다.

**지금 (2026-10-23, Windows 9pt 맑은 고딕으로 잰 값)**
- `views/device_tab_toolbar.py` ~41-56: `process_selector.setMinimumWidth(160)`, `release_selector.setMinimumWidth(120)`. 둘 다 `AdjustToContents`, 가로 정책 `Preferred`.
- 창을 최소 너비(약 1261px)로 줄이면 두 콤보가 최소 너비로 눌린다. Process 는 `sf2p` 에도 160px 이고, Version 은 120px 이다.
- 콤보 `sizeHint` 너비: 10글자 이름 `abcdefghij` 86px, `S00-V1.0.0.0` 101px, 16글자 `S00-V12.34.56.78` 129px. 그래서 16글자 버전은 최소 너비 창에서 끝이 잘린다.

**승인된 변경**: 최소 너비를 맞바꾼다. Process **120**, Version **160**.
- 두 콤보의 최소 너비 합(280)이 그대로라 툴바 최소 너비와 창 최소 너비가 바뀌지 않는다(K57, phase 21).
- 사용자가 고른 안이다. Version 을 200 으로 더 넓히는 안(창 최소 너비 +40px)은 고르지 않았다.

## 읽어야 할 파일

- `/CLAUDE.md`(테스트 관례의 레이아웃 항목), `/docs/UI_GUIDE.md`(화면 구성)
- `src/genviewer/views/device_tab_toolbar.py`: `__init__` 의 두 콤보(~41-56), `set_pairs`(~199)
- `tests/gui/test_toolbar_min_width.py`: `window` fixture, `_settle`, `_overlapping`, 배너 단추 테스트(테마마다 `preserved_theme` 안에서 `apply_theme`). 새 테스트는 이 파일에 더한다.

## 작업

### 1. 실패하는 테스트 (`tests/gui/test_toolbar_min_width.py` 에 더한다)

CLAUDE.md 레이아웃 관례를 따른다. 컨트롤러 없이 `MainWindow("localhost")` 를 띄우고(`window` fixture), 창을 최소 너비로 줄인 뒤(`resize` 로 최소보다 작게 주면 최소로 맞춰진다) `_settle()` 로 확정하고 위젯 geometry로 단언한다. **픽셀 숫자를 박지 않는다**(offscreen 글꼴은 Windows 와 너비가 다르다). 테마마다(`graphite`, `mist`) `with preserved_theme(qapp):` 안에서 `apply_theme` 한 뒤 잰다.

- `test_version_combo_is_wider_than_process_combo_at_minimum_width[theme]`
  - 툴바 view 의 `set_pairs([("sf2p", ""), ("sf2p", "S00-V1.0.0.0")])` 로 짧은 이름과 흔한 버전을 넣는다.
  - 창 최소 너비에서 `release_selector.width() > process_selector.width()`.
  - 수정 전에 실패해야 한다(160 > 120).
- `test_a_ten_character_name_and_a_long_version_fit_at_minimum_width[theme]`
  - 10글자 이름과 긴 버전 한 쌍을 넣는다. 버전은 수정 전 Version 최소 너비(120)에는 안 들어가고 수정 뒤(160)에는 들어가는 길이를 고른다. Windows 에서는 16글자 `S00-V12.34.56.78` 이 그렇다(129px).
  - offscreen 의 `sizeHint` 를 먼저 재서 고르고, 고른 글자와 잰 값을 summary 에 적는다.
  - 창 최소 너비에서 두 콤보 모두 `width() >= sizeHint().width()`(글자가 잘리지 않는다).
  - 수정 전에 Version 쪽이 실패해야 한다.
- 기존 겹침 테스트(`test_toolbar_widgets_do_not_overlap_*`, `test_long_names_keep_toolbar_widgets_apart`)는 그대로 통과해야 한다.

### 2. 수정 (`views/device_tab_toolbar.py`)

- `process_selector.setMinimumWidth(160)` → `120`, `release_selector.setMinimumWidth(120)` → `160`.
- 두 줄 위에 이유를 한국어 주석 한 줄로 적는다(process 이름은 대개 10글자 안, 버전이 더 길다. 합은 그대로라 창 최소 너비가 같다).
- 다른 것(크기 정책, `AdjustToContents`, 순서, 다른 위젯 너비)은 바꾸지 않는다.

### 3. 확인과 문서

- 수정 전과 뒤에 `MainWindow("localhost").minimumSizeHint().width()` 를 offscreen 에서 재서 같은지 summary 에 적는다(테스트에 숫자로 박지 않는다).
- 변이: 두 숫자를 손으로 되돌리면 새 테스트가 실패하는지 본다. `git checkout`/`git stash` 로 되돌리지 마라.
- `docs/UI_GUIDE.md` "화면 구성" 의 Version 콤보 줄(~50)에 "Version 콤보가 Process 콤보보다 넓다(최소 160 / 120px, 합이 같아 창 최소 너비는 그대로)" 를 더한다.

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
   - 바꾼 `src` 가 `views/device_tab_toolbar.py` 의 최소 너비 두 값과 주석뿐인가?
   - 창 최소 너비가 수정 전과 같은가?
3. 결과에 따라 `phases/25-combo-width/index.json` 의 step 0을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "툴바 콤보 최소 너비 Process 160→120, Version 120→160(views/device_tab_toolbar.py). 테스트: <이름들>. RED: <테스트 이름: 단언>. 긴 버전 글자와 offscreen sizeHint: <값>. 창 최소 너비 전/후: <값>/<값>. 변이: <결과>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 테스트에 픽셀 숫자(120, 160, 129 등)를 박지 마라. 이유: 너비는 글꼴(플랫폼, 앞 테스트의 `apply_theme`)에 따라 달라서 다른 PC 에서 깨진다(phase 21).
- 콤보의 크기 정책이나 `AdjustToContents` 를 바꾸지 마라. 이유: 긴 이름·버전이 들어오면 콤보가 늘어나는 지금 동작을 지킨다.
- 다른 툴바 위젯의 너비와 툴바 가로 정책(`Preferred`, K57)을 바꾸지 마라. 이유: 창 최소 너비가 바뀐다. 사용자가 그 안을 고르지 않았다.
- 화면 문구를 바꾸지 마라. 이유: 너비만 바꾸는 step이다.
- 기존 테스트를 깨뜨리지 마라.
