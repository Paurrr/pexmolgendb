# Step 1: dialogs-text

## 배경

phase 24는 사용자가 2026-10-22에 요청하고 승인한 변경이다. 사용자에게 보이는 문구를 영어로 바꾼다(ADR-020). 이 step은 **대화상자 파일**(`dialogs/`)과 `main.py` 의 오류 상자 문구를 맡는다.

step 0이 서비스 계층 문구를 바꿨다. `phases/24-english-text/index.json` 의 summary를 먼저 읽어라.

phase 24 공통 규칙:
1. 승인된 변경이라 RED 대신 변이 검사를 한다. 바꾼 문구 하나를 손으로 되돌려, 고친 테스트가 실패하는지 본다. `git checkout`/`git stash` 로 되돌리지 마라.
2. 대상 파일의 한글 문자열을 `rg -n "[가-힣]" <파일>` 로 찾는다.
   - 주석, docstring, 로그 파일 호출(`log.*`, `logger.*`, `logging.*` 의 인자)은 그대로 둔다.
   - 나머지는 모두 옮긴다.
   - 용어는 `docs/UI_GUIDE.md` "문구" 의 용어표를 따른다.
3. 그 문구를 고정한 테스트를 `rg` 로 찾아 같이 고친다. 같음, 포함, 없음 단언이 모두 대상이다. 테스트 데이터와 assert 메시지의 한국어는 그대로 둔다.
4. 다른 step 대상 파일의 문구는 건드리지 않는다. 동작, 구조, 이미 영어인 문구도 바꾸지 않는다.
5. README와 UI_GUIDE 서술은 phase 마무리에서 고친다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`: "문구", ADR-018·ADR-020
- `src/genviewer/dialogs/add_process.py`: `NO_RELEASE_TEXT`, `NO_COPY_TEXT`, 이유 줄, `release == NO_RELEASE_TEXT` 거부(~87)
- `src/genviewer/dialogs/conflict.py`, `src/genviewer/dialogs/connection.py`
- `src/genviewer/main.py`: 예외 상자(~30-40)
- `NO_RELEASE_TEXT` 를 쓰는 곳. 읽기만 한다. import한 상수라 글자가 자동으로 따라간다.
  - `src/genviewer/views/device_tab_toolbar.py`: Version 콤보 `r or NO_RELEASE_TEXT`
  - `src/genviewer/views/device_tab.py`: Load CSV 버전 목록, `(없음)` → `""` 되돌림

## 작업

### 1. 옮길 문구 (대략)

**`dialogs/add_process.py`**
- `NO_RELEASE_TEXT = "(없음)"` → `"(none)"`
  - 빈 버전의 화면 표시다. Version 콤보, Load CSV 버전 목록, Add Process 거부 조건이 이 상수 하나를 쓴다.
  - 그래서 `(none)` 이라는 버전 이름은 화면에서 만들 수 없게 된다. 지금 `(없음)` 과 같다.
- `NO_COPY_TEXT = "(복사 안 함)"` → `"(no copy)"`
- 이유 줄
  - `"이미 있는 process 다."` → `"This process already exists."`
  - `f"{NO_RELEASE_TEXT} 은 버전 이름으로 쓸 수 없다."` → `f"{NO_RELEASE_TEXT} cannot be used as a version name."`

**`dialogs/conflict.py`**
- 머리말 `"다른 사용자가 편집 중인 데이터를 먼저 변경했다."` → `"Another user changed this data first."`
- 단추 `다시 읽기` / `내 변경으로 덮어쓰기` / `취소` → `Reload` / `Overwrite with Mine` / `Cancel`
- 툴팁 셋도 옮긴다.
  - Reload: `"Reload from the server. Your unsaved changes are discarded."`
  - Cancel: `"Save nothing. Your changes stay as they are."`
  - Overwrite: `"Replace the other user's change with yours."`

**`dialogs/connection.py`**
- `연결 테스트` → `Test Connection`
- 안내 줄 → `f"Defaults are the current settings ({env_file.SITE_NAME}). Changes here are used for this connection only and are not saved."`
- `연결 중...` → `Connecting...`
- `f"실패: …"` → `f"Failed: …"`
- `연결 성공` → `Connected.`

**`main.py`**
- 오류 상자 제목 `"예기치 못한 오류"` → `"Unexpected Error"`
- 본문 꼬리 `f"\n\n자세한 내용: {where}"` → `f"\n\nDetails: {where}"`
- 로그 파일에만 가는 한국어(`"오류 상자를 띄우지 못했다"`, `"처리되지 않은 예외"` 등)는 그대로 둔다. `tests/gui/test_socket_workers.py` 가 그중 하나를 고정한다.

### 2. 함께 고칠 테스트 (대표)

| 파일 | 고정한 것 |
|---|---|
| `tests/gui/test_add_process_dialog.py` | `EXISTS`, `NO_RELEASE`, `"(복사 안 함)"`, 입력으로 친 `"(없음)"` |
| `tests/gui/test_add_release.py` ~501 | `"(복사 안 함)"` |
| `tests/gui/test_conflict_deleted_only.py` ~33-35 | 단추 글자. 진짜 단추를 찾아 누른다 |
| `tests/gui/test_connect_failure.py` ~312, ~328, ~338 | `"실패: "` 접두어, `"연결 성공"` |
| `tests/gui/test_toolbar_pairs_view.py`, `test_process_release_switch.py`, `test_load_csv_release.py` | 화면의 `"(없음)"` 기대값 → `"(none)"` |

- 빈 버전 테스트("…keeps the old …" 이름)는 이름과 성질을 그대로 둔다. 기대 글자만 `(none)` 으로 바꾼다.
  - 그 성질은 "버전 흔적이 없다" 이고 ADR-018에 적혀 있다.

## Acceptance Criteria

```bash
uv run ruff check src tests
uv run pytest tests/gui/test_add_process_dialog.py tests/gui/test_conflict_deleted_only.py tests/gui/test_connect_failure.py tests/gui/test_toolbar_pairs_view.py tests/gui/test_process_release_switch.py tests/gui/test_load_csv_release.py -q
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 버전 값은 여전히 글자가 아니라 index(`_releases`)로 읽는가? 표시 글자만 바뀌어야 한다.
   - Add Process가 `(none)` 을 버전 이름으로 받지 않는가?
   - 연결 대화상자의 실패 줄이 여전히 `user_message(e)` 를 쓰는가(비밀번호)?
3. 결과에 따라 `phases/24-english-text/index.json` 의 step 1을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "dialogs 문구 영어화: NO_RELEASE_TEXT='(none)', NO_COPY_TEXT='(no copy)', conflict 단추 Reload/Overwrite with Mine/Cancel, connection, main.py 'Unexpected Error'. 고친 테스트: <파일들>. 변이: <결과>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `dialogs/conflict.py` 의 `RELOAD`/`OVERWRITE`/`CANCEL` 값과 창 제목 `"Save Conflict"` 를 바꾸지 마라. 이유: `tests/gui_support/dialogs.py` 의 `CONFLICT_TITLE` 와 저장 경로가 쓴다.
- 빈 버전을 콤보 글자로 판별하는 코드를 새로 만들지 마라. 이유: 버전은 index로 읽는다. K55가 그 이유다.
- `views/`·`controllers/` 의 문구를 바꾸지 마라. 이유: step 2의 일이다. `NO_RELEASE_TEXT` 가 import로 따라가는 것은 괜찮다.
- 로그 파일에만 가는 문구, 주석, docstring을 번역하지 마라.
- 기존 테스트를 깨뜨리지 마라. 문구에 맞춰 기대값만 바꾼다.
