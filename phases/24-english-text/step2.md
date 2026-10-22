# Step 2: device-screen-text

## 배경

phase 24는 사용자가 2026-10-22에 요청하고 승인한 변경이다. 사용자에게 보이는 문구를 영어로 바꾼다(ADR-020).

이 step은 **Device 화면의 controller·view 문구**를 맡는다. 질문, 경고, 배너, 머리글 메뉴, 로그 패널 줄이 대상이다.

먼저 `phases/24-english-text/index.json` 의 summary를 읽어라. step 0은 서비스 문구를, step 1은 대화상자를 바꿨다.

phase 24 공통 규칙:
1. 승인된 변경이라 RED 대신 변이 검사를 한다. 바꾼 문구 하나를 손으로 되돌려, 고친 테스트가 실패하는지 본다. `git checkout`/`git stash` 로 되돌리지 마라.
2. 대상 파일의 한글 문자열을 `rg -n "[가-힣]" <파일>` 로 찾는다.
   - 주석, docstring, 로그 파일 호출(`log.*`, `logger.*`, `logging.*` 의 인자)은 그대로 둔다.
   - 나머지는 모두 옮긴다. **로그 패널** 줄(`logRequested.emit(...)`, `append_log`)은 화면이라 옮긴다.
   - 용어는 `docs/UI_GUIDE.md` "문구" 의 용어표를 따른다.
3. 그 문구를 고정한 테스트를 `rg` 로 찾아 같이 고친다. 같음, 포함, 없음 단언이 모두 대상이다. 테스트 데이터와 assert 메시지의 한국어는 그대로 둔다.
4. 다른 step 대상 파일의 문구는 건드리지 않는다. 동작, 구조, 이미 영어인 문구도 바꾸지 않는다.
5. README와 UI_GUIDE 서술은 phase 마무리에서 고친다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`: "문구", ADR-018·ADR-020
- `src/genviewer/controllers/device_tab.py`: `REFRESH_QUESTION` 과 접속·폴링·CSV·보내기 문구
- `src/genviewer/controllers/device_tab_toolbar.py`
- `src/genviewer/controllers/device_table.py`: 머리글 정렬 메뉴, 붙여넣기 경고, Save Skipped, 충돌 로그
- `src/genviewer/controllers/parameter_tab.py`: 탭 충돌 로그
- `src/genviewer/controllers/main_window.py`: Virtuoso 목록 도착 때의 Refresh 질문. `REFRESH_QUESTION` 과 같은 글자의 사본이다.
- `src/genviewer/views/device_tab.py`: 배너, Load CSV 버전 라벨

## 작업

### 1. 옮길 문구 (대략, 2026-10-22 기준. 권장 영어)

**`controllers/device_tab.py`**
- `REFRESH_QUESTION` → `"You have unsaved changes.\nReloading from the server discards them. Continue?"`
- `"데이터베이스에 연결했다."` → `"Connected to the database."`
- `"데이터베이스에 연결하지 못했다."` → `"Could not connect to the database."`
- `f"변경 감지 폴링을 중단했다: {reason}"` → `f"Stopped change polling: {reason}"`
- `"서버 내용으로 다시 읽었다."` → `"Reloaded from the server."`
- `"저장하지 않은 device 가 있어 보내지 않았다. 먼저 저장할 것."` → `"Not sent: some devices are unsaved. Save first."`
- `"먼저 DB를 Load 해야 합니다."` (두 곳) → `"Connect to the database first."`
- Load CSV 결과 → `f"Added {created} device(s).\nCSV import always adds new rows - importing the same file again duplicates them."`
  - em dash를 쓰지 않고 ASCII `-` 를 쓴다.
- 로그 줄
  - `f"Imported CSV: {path} (version {release}, {created} device(s) added)."`
  - 빈 버전이면 `f"Imported CSV: {path} ({created} device(s) added)."`
  - 빈 버전일 때 버전 흔적이 없어야 한다(ADR-018).
- 로그 파일 호출(`"접속에 실패한 데이터베이스를 닫지 못했다"`, `"데이터베이스 접속 실패"`)은 그대로 둔다.

**`controllers/device_tab_toolbar.py`**
- `"먼저 DB를 Load 해야 합니다."` → `"Connect to the database first."`
- Add Process 성공의 덧붙임 → `f"\nCopied {copied} device(s) from {src_label}."`
- Remove Process 질문 → `f"Removing process '{label}' also deletes {n} device(s) and their parameters.\nContinue?"`

**`controllers/device_table.py`**
- 머리글 메뉴 `"오름차순 정렬"`/`"내림차순 정렬"` → `"Sort Ascending"`/`"Sort Descending"`
- 붙여넣기 경고 2개. device 편집 쪽과 탭 편집 쪽은 본문이 서로 달라야 한다(UI_GUIDE).
  - device: `"Not pasted: there are unsaved device changes.\nPasting saves immediately and reloads the list, which would discard them. Save first."`
  - 탭: 같은 꼴로 `tab changes` / `reloads the tabs` 다.
- Save Skipped 머리말 → `"These devices were not saved because their CellType is not in the list (the edits were discarded on reload):\n"`
  - 그 뒤 ` - name` 줄은 그대로다.
- 충돌 로그 → `"Save conflict: reloaded from the server."`, `"Save conflict: overwrote with my changes."`, `"Save conflict: save canceled."`

**`controllers/parameter_tab.py`**
- `Tab conflict:` 로그 셋을 device 쪽과 같은 꼴로 바꾼다.

**`controllers/main_window.py`** ~176
- Refresh 질문 본문을 `REFRESH_QUESTION` 과 같은 글자로 둔다. `from genviewer.controllers.device_tab import REFRESH_QUESTION` 으로 import해도 된다.
- 로그 파일 호출 `"저장 실패"` 는 그대로 둔다.

**`views/device_tab.py`**
- 배너
  - 단추 `새로고침` → `Reload`, `닫기` → `Dismiss`
  - 툴팁 `"Reload from the server. Unsaved changes are discarded."`, `"Hide this notice only. The server still differs."`
- 배너 글 → `f"This process was changed by {actor}."`. 사람이 없으면 `another user` 다.
- Load CSV 버전 라벨 → `"Version to import (empty = no version):"`

### 2. 함께 고칠 테스트 (대표)

| 파일 | 고정한 것 |
|---|---|
| `tests/gui/test_reload_guard.py` | REFRESH 글자, 연결 성공·실패, `"먼저 DB를 Load …"` |
| `tests/gui/test_window_guards.py` ~34 | `REFRESH` 튜플 |
| `tests/gui/test_send_device_data.py` ~16 | Unsaved Devices 본문 |
| `tests/gui/test_device_save_guards.py` | Save Skipped, Unsaved Changes 두 본문 |
| `tests/gui/test_add_release.py` ~194, ~218, ~252 | 복사 덧붙임, Load 경고 |
| `tests/gui/test_conflict_deleted_only.py` | 충돌 로그 줄 |
| `tests/gui/test_load_csv_release.py` ~27, ~117, ~135, ~241 | CSV 안내, 로그 줄 둘, 버전 라벨 |
| `tests/gui/test_poll_binding.py`, `tests/gui/test_user_message_sites.py` | 폴링 중단 접두어 |
| `tests/gui/test_process_release_switch.py` ~452 | Remove Process 질문 |
| `tests/gui/test_connect_failure.py` ~211, ~293 | `"데이터베이스에 연결하지 못했다."` |
| 배너 테스트(`test_own_save_banner`, `test_poll_binding`, `test_smoke`, `test_tab_version_sync` 등) | 배너 글에 actor가 들어가는지 |

- 빈 버전 테스트(`…without_a_release_keeps_the_old_lines` 등)는 이름과 성질을 그대로 둔다. 기대 글자만 영어로 바꾼다.

## Acceptance Criteria

```bash
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 질문, 경고의 제목(영어)과 severity가 그대로인가?
   - 로그 파일 호출의 한국어는 그대로인가?
   - `REFRESH_QUESTION` 을 쓰는 세 곳(재접속, 배너 Reload, Virtuoso 목록)이 같은 글자인가?
3. 결과에 따라 `phases/24-english-text/index.json` 의 step 2를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "Device 화면 controller·view 문구 영어화(REFRESH_QUESTION, 배너 Reload/Dismiss, 정렬 메뉴, 붙여넣기·Save Skipped·충돌 로그, Load CSV 안내·로그 줄). 고친 테스트: <파일들>. 변이: <결과>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- History 화면(`controllers/history_tab.py`, `views/history_tab.py`) 문구를 바꾸지 마라. 이유: step 3의 일이다.
- 대화상자 제목(`Refresh`, `Unsaved Changes`, `Save Skipped`, `Remove Process` 등)을 바꾸지 마라. 이유: 이미 영어이고 테스트 fixture가 제목으로 찾는다.
- 이력 요약(`service/repo/audit.py`)을 바꾸지 마라. 이유: ADR-020.
- 질문이 나오는 조건이나 순서를 바꾸지 마라. 이유: 문구만 옮기는 step이다.
- 기존 테스트를 깨뜨리지 마라. 문구에 맞춰 기대값만 바꾼다.
