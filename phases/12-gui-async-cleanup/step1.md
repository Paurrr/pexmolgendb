# Step 1: history-error-text

## 배경 (phase 12 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 12는 2026-10-17에 `docs/notes/known-issues.md` 를 분류하면서 버그로 정한 GUI 비동기·수명 항목(History 화면의 오류 문구·다시 읽기 경합 K23a·K41, 변경 감지 폴링의 결과 묶기 K23b, Qt 객체 누수 K22 나머지)을 한 step에 하나씩 고친다. 모두 버그이고 승인 대상이 아니다. 사용자에게 보이는 문구를 새로 만들지 않는다.

phase 0~11이 끝나 있다. 이 phase에 닿는 것:
- phase 11 step 0(`user-message-sites`): `device_tab_toolbar.get_process_id` 와 `device_tab._on_poll_failed` 가 `user_message` 를 쓴다(로그는 한 줄). 이 step의 본보기다.
- step 0(이 phase): `FakeAuditRepository`(`recent`), `store.add_audit`, `store.hold_next(method)`, `install_fake_history`, `history_ctrl` fixture. `store.fail_next("recent", exc)` 가 된다.

모든 step에 같은 규칙이 적용된다.
1. 버그는 **주장**이다. 먼저 실패하는 테스트로 재현하고 RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라.
5. 이 파일의 행 번호는 2026-10-17(phase 6 전) 기준 대략값이다. 이름으로 찾아라.

테스트 기반: `history_ctrl`(첫 다시 읽기가 끝난 `HistoryTabController`), `store`, `store.add_audit`, `store.fail_next`, `store.calls_of("recent")`. 고정 대기(`qtbot.wait`) 금지. `waitUntil` 콜백은 bool을 돌려준다.

## 이 step의 목적

History 화면의 실패 문구 두 곳이 예외를 그대로(`{exc}`) 쓰는 것을 `user_message` 로 바꾼다. K35와 같은 종류의 CLAUDE.md CRITICAL 위반(2026-10-17 분류: 버그)이다.

## 읽어야 할 파일

- `/CLAUDE.md`(CRITICAL: 비밀번호를 화면·로그에 남기지 않는다), `/docs/UI_GUIDE.md`(원칙 5)
- `src/genviewer/controllers/history_tab.py`: `_on_failed` (~173-179)
- `src/genviewer/service/errors.py`: `user_message`
- `src/genviewer/controllers/device_tab.py`: `_on_poll_failed`(phase 11 step 0이 고친 본보기)
- `tests/gui/test_history_smoke.py`, `tests/gui/conftest.py` 의 `history_ctrl`

## 버그

```python
@Slot(object)
def _on_failed(self, exc: Exception) -> None:
    self._failures += 1
    self.ui.show_count(f"이력을 읽지 못했다: {exc}")
    if self._failures >= POLL_FAILURE_LIMIT:
        self._timer.stop()
        self.logRequested.emit(f"이력 자동 갱신을 중단했다: {exc}")
```

- 이력 읽기가 실패하면 개수 칸(화면)과 세 번째 실패의 로그 패널에 예외 원문이 찍힌다.
- conninfo가 든 예외면 비밀번호가 화면에 나온다.
- 55P03·57014 같은 SQLSTATE별 한국어 안내도 나오지 않는다.

이것은 주장이다. 먼저 재현하라.

## 작업

### 1. 테스트 먼저 (`tests/gui/test_history_errors.py`, 새 파일)

- **개수 칸, 비밀번호**
  - 준비: `store.fail_next("recent", psycopg.OperationalError("connection failed: host=h password=s3cret"))`
  - 동작: `history_ctrl.reload()` 를 부르고 `qtbot.waitUntil(lambda: history_ctrl._task is None and len(store.calls_of("recent")) == n + 1)` 로 기다린다.
  - 단언: 개수 칸(`ui.count_label.text()`)이 `"이력을 읽지 못했다: "` 로 시작하고, `"s3cret"` 이 없고, 줄바꿈이 없다. **수정 전에는 실패해야 한다.**
- **개수 칸, SQLSTATE 안내**: `psycopg.errors.LockNotAvailable(...)` 면 개수 칸에 `_BY_SQLSTATE["55P03"]` 문장이 있다. **수정 전에는 실패해야 한다.**
- **세 번째 실패의 로그**
  - 준비: 로그를 리스트에 받는다. 실패를 세 번 쌓는다.
  - 동작: `reload()` 와 기다림을 세 번 한다.
  - 단언: `"이력 자동 갱신을 중단했다: "` 로 시작하는 줄이 정확히 하나다. `"s3cret"` 과 줄바꿈이 없고, 타이머가 멈췄다(지금과 같다). **수정 전에는 실패해야 한다.**
- **회귀**: 성공하면 개수 칸이 지금처럼 `"N줄"` / `"조건에 맞는 이력이 없다."` 다.

### 2. 수정

- `history_tab.py` `_on_failed`: 두 곳 모두 `user_message(exc)` 를 한 줄로(줄바꿈을 공백으로) 만들어 기존 접두어 뒤에 붙인다.
- 접두어 `"이력을 읽지 못했다: "`·`"이력 자동 갱신을 중단했다: "`, 실패 횟수, 타이머 동작은 그대로 둔다.

### 3. 문서

- 없다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_history_errors.py tests/gui/test_history_smoke.py -q   # 새 테스트 통과 (수정 전에는 문구 테스트가 실패해야 한다)
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 화면·로그 패널로 가는 예외 문자열이 `user_message()` 를 거치는가(CLAUDE.md CRITICAL)?
   - 접두어와 실패 횟수·타이머 동작이 그대로인가?
   - 다시 읽기 경합(`_task` 가드, `set_db`)은 건드리지 않았는가? 그것은 step 2의 몫이다.
3. 결과에 따라 `phases/12-gui-async-cleanup/index.json` 의 step 1을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "history_tab._on_failed 의 개수 칸·로그를 user_message 한 줄로. RED: <테스트 이름: 단언>. 변이: <…>. tests/gui/test_history_errors.py"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 접두어 문구를 바꾸거나 번역하지 마라. 이유: 예외 문자열 부분만 고친다(UI_GUIDE 문구).
- `reload`/`set_db`/`_clear_task` 를 바꾸지 마라. 이유: 경합은 step 2가 재현부터 한다.
- `service/errors.py` 를 바꾸지 마라. 이유: 모든 화면 문구가 함께 바뀐다.
- 기존 테스트를 깨뜨리지 마라.
