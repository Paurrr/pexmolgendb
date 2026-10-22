# Step 3: history-text

## 배경

phase 24는 사용자가 2026-10-22에 요청하고 승인한 변경이다. 사용자에게 보이는 문구를 영어로 바꾼다(ADR-020). 이 step은 **History 화면**(`genviewer --history`)의 틀 문구를 맡는다.

**이력 요약 칸의 내용은 바꾸지 않는다.** 그것은 `change_log.summary` 에 저장된 데이터이고, ADR-020에 따라 한국어다(예: `device 추가  nfet_a (NFET)`). 바꾸는 것은 그 주변이다. 기간 콤보, 열 이름, 자리표시, 단추, 개수 줄, `(모름)`.

먼저 `phases/24-english-text/index.json` 의 summary를 읽어라.

phase 24 공통 규칙:
1. 승인된 변경이라 RED 대신 변이 검사를 한다. 바꾼 문구 하나를 손으로 되돌려, 고친 테스트가 실패하는지 본다. `git checkout`/`git stash` 로 되돌리지 마라.
2. 대상 파일의 한글 문자열을 `rg -n "[가-힣]" <파일>` 로 찾는다.
   - 주석, docstring, 로그 파일 호출(`log.*`, `logger.*`, `logging.*` 의 인자)은 그대로 둔다.
   - 나머지는 모두 옮긴다. 로그 패널 줄도 옮긴다.
   - 용어는 `docs/UI_GUIDE.md` "문구" 의 용어표를 따른다.
3. 그 문구를 고정한 테스트를 `rg` 로 찾아 같이 고친다. 같음, 포함, 없음 단언이 모두 대상이다. 이력 요약 기대값과 테스트 데이터는 한국어 그대로 둔다.
4. 다른 step 대상 파일의 문구는 건드리지 않는다. 동작, 구조, 이미 영어인 문구도 바꾸지 않는다.
5. README와 UI_GUIDE 서술은 phase 마무리에서 고친다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`: "문구", `/docs/ADR.md`: ADR-020
- `src/genviewer/views/history_tab.py`: 기간 항목(~29-32), `HEADERS`(~35), 자리표시, 단추, 체크, `(전체)`(~122와 ~130, 두 곳이 같은 글자여야 한다)
- `src/genviewer/controllers/history_tab.py`: `(모름)`, 개수 줄, 오류 줄, 자동 갱신 중단 로그
- `tests/gui/conftest.py`: `history_ctrl` fixture. 기간을 글자가 아니라 `findData("")` 로 고른다.

## 작업

### 1. 옮길 문구 (대략, 권장 영어)

**`views/history_tab.py`**
- 기간: `최근 1일`/`최근 7일`/`최근 30일`/`전체` → `Last 1 day`/`Last 7 days`/`Last 30 days`/`All`. 항목 data는 그대로다.
- 열 이름: `시각`/`사람`/`출처`/`process / device`/`내용` → `Time`/`Who`/`Source`/`process / device`/`Change`
- 상세 자리표시 → `"Select a row to see the changed values here."`
- 사람 칸 자리표시 → `"Who"`
- 찾기 칸 자리표시 → `"Find text (searches changed values too)"`
- `새로고침` → `Refresh`
- `자동` → `Auto`, 툴팁 `"Reloads every 10 seconds."`
- `기간` → `Period`
- `(전체)` → `(all)` (두 곳)

**`controllers/history_tab.py`**
- `(모름)` → `(unknown)` (두 곳)
- `"데이터베이스에 붙어 있지 않다."` → `"Not connected to the database."`
- `"조건에 맞는 이력이 없다."` → `"No history matches."`
- `f"{n}줄"` → `f"{n} row(s)"`
- `f"{n}줄  (줄을 고른 동안은 자동 갱신을 멈춘다)"` → `f"{n} row(s)  (auto refresh paused while a row is selected)"`
- `f"{n}줄  (더 있다. 기간을 좁힐 것)"` → `f"{n} row(s)  (more exist; narrow the period)"`
- `f"이력을 읽지 못했다: {reason}"` → `f"Could not read history: {reason}"`
- `f"이력 자동 갱신을 중단했다: {reason}"` → `f"Stopped history auto refresh: {reason}"`

### 2. 함께 고칠 테스트 (대표)

| 파일 | 고정한 것 |
|---|---|
| `tests/gui/test_history_errors.py` | 오류 접두어 둘, 결과 없음, `"1줄"` |
| `tests/gui/test_history_reload.py` | 오류 접두어(**없음 단언** ~83, ~110), 접속 안 됨, 결과 없음, `"1줄"`/`"2줄"` |
| `tests/gui/test_history_smoke.py` | `"2줄"`, `"1줄"`, process 콤보 항목 `["(전체)", …]` |

- 이력 요약 기대값(`"device 추가  nfet_a (NFET)"`, `"process 추가  sf9x"`)은 그대로 둔다.
- `rg -n "줄\"|(전체)|(모름)" tests/gui` 로 남은 곳을 찾는다.

## Acceptance Criteria

```bash
uv run ruff check src tests
uv run pytest tests/gui/test_history_errors.py tests/gui/test_history_reload.py tests/gui/test_history_smoke.py -q
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 기간·process 필터의 값(data, `(all)` 판별)이 그대로 동작하는가?
   - 요약 칸과 상세 칸의 데이터(요약, 바뀐 값)는 손대지 않았는가?
3. 결과에 따라 `phases/24-english-text/index.json` 의 step 3을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "History 화면 틀 문구 영어화(기간 Last N days/All, 열 Time/Who/Source/process / device/Change, (all), (unknown), N row(s), 오류 줄). 요약 칸은 한국어 그대로. 고친 테스트: <파일들>. 변이: <결과>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `service/repo/audit.py` 를 바꾸지 마라. 이유: 요약은 데이터이고 한국어다(ADR-020). CLI `log` 의 `(모름)` 은 step 4가 바꾼다.
- 찾기(`find`)의 동작을 바꾸지 마라. 한국어 요약을 한국어로 찾을 수 있어야 한다.
- 기간 항목의 data와 기본값(최근 7일)을 바꾸지 마라. 이유: 문구만 옮기는 step이다.
- 기존 테스트를 깨뜨리지 마라. 문구에 맞춰 기대값만 바꾼다.
