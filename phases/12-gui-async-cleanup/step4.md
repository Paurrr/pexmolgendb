# Step 4: task-cleanup

## 배경 (phase 12 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 12는 2026-10-17에 `docs/notes/known-issues.md` 를 분류하면서 버그로 정한 GUI 비동기·수명 항목(History 화면의 오류 문구·다시 읽기 경합 K23a·K41, 변경 감지 폴링의 결과 묶기 K23b, Qt 객체 누수 K22 나머지)을 한 step에 하나씩 고친다. 모두 버그이고 승인 대상이 아니다. 사용자에게 보이는 문구를 새로 만들지 않는다.

phase 0~11과 이 phase의 step 0~3이 끝나 있다. step 2·3이 History와 변경 감지 폴링의 `Task` 정리를 "끝난 그 작업만 지운다" 로 바꿨다. 그 둘은 이미 자기 `Task` 를 deleteLater 한다.

모든 step에 같은 규칙이 적용된다.
1. 버그는 **주장**이다. 먼저 실패하는 테스트로 재현하고 RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라.
5. 이 파일의 행 번호는 2026-10-18(phase 11 직후) 기준 대략값이다. 이름으로 찾아라.

## 이 step의 목적

K22 중 "남은 `Task` 객체가 쌓인다" 를 고친다(2026-10-17 분류: 버그). `utils/background.py` 의 `run_blocking` 만 바꾼다.

## 읽어야 할 파일

- `/CLAUDE.md`(GUI 스레드에서 DB를 기다리지 않는다), `/docs/ARCHITECTURE.md`("스레딩")
- `src/genviewer/utils/background.py` 전체
  - `Task(fn, parent)`(QThread)
  - `run_blocking(fn, parent)` (~74-101): `Task(fn, parent)` 를 만들고 `wait` 슬라이스로 기다린 뒤 `task.error`/`task.result` 를 읽는다. Task를 지우지 않는다.
- `run_blocking` 호출부: `controllers/device_tab.py`(접속, CSV 불러오기 — parent는 컨트롤러), `controllers/device_table.py`(device 저장), `controllers/parameter_tab.py`(탭 저장), `dialogs/connection.py`(연결 테스트)
- `tests/test_background.py`(자기 `qapp` fixture로 돈다. GUI conftest를 쓰지 않는다)
- `tests/gui/test_connect_db.py:~128-156`: 테스트가 `Task` 를 직접 만들고 `finally` 에서 `task.wait()` 한다. 그래서 `Task` 가 `finished` 에서 스스로 지워지면 안 된다.

## 버그

- `run_blocking(fn, parent)` 는 부르는 곳마다 `Task(fn, parent)` 를 하나 만든다.
- parent가 있으면(컨트롤러) 그 QThread 객체는 끝난 뒤에도 부모의 자식으로 남는다. 저장·접속·CSV 불러오기를 할 때마다 하나씩 쌓인다.
- parent가 None이면 파이썬 참조가 끝나면서 지워지므로 문제가 없다.

이것은 주장이다. 먼저 재현하라.

## 작업

### 불변식

- `run_blocking` 의 반환값과 예외는 지금과 같다. 결과와 예외는 **해제하기 전에** 읽는다.
- `Task` 는 `wait()` 가 끝났다고 확인된 뒤에만 해제한다. 돌고 있는 QThread는 절대 지우지 않는다.
- 해제 방법은 `deleteLater()` 또는 `setParent(None)` 후 참조 해제다. 어느 쪽이든 parent의 자식 목록에서 사라져야 한다.
- `Task` 클래스 자체(`run`, 시그널)는 바꾸지 않는다. `finished` 에 스스로 지우는 연결을 더하지 않는다. 이유: 폴링·History·테스트가 자기 `Task` 를 직접 관리한다.
- `_nesting`(is_busy), 대기 커서, 입력 제외 처리는 그대로다.

| 경우 | 반환/예외 | parent의 `Task` 자식(지연 삭제 처리 뒤) |
|---|---|---|
| fn 성공, parent 있음 | 값 그대로 | 0 |
| fn 예외, parent 있음 | 같은 예외 | 0 |
| parent None | 지금과 같다 | 해당 없음 |
| Qt 애플리케이션 없음 | `fn()` 직접 호출(지금과 같다) | 해당 없음 |

### 1. 테스트 먼저 (`tests/test_background.py` 에 더한다)

- **성공**
  - 준비: `parent = QObject()`
  - 동작: `background.run_blocking(lambda: 1, parent)` 의 반환을 받는다. 지연 삭제를 쓰면 `QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)` 로 처리한다.
  - 단언: 반환이 1이고 `parent.findChildren(background.Task) == []` 다. **수정 전에는 하나가 남아 실패해야 한다.**
- **예외**: fn이 `ValueError` 를 내면 같은 예외가 올라오고 자식이 0이다. **수정 전에는 실패해야 한다.**
- **여러 번**: 다섯 번 불러도 자식이 0이다.
- **회귀**: 이 파일의 기존 테스트(워커 스레드, 이벤트 루프, 예외 전달, `is_busy`, Qt 없음)가 그대로 통과한다. `tests/gui/test_connect_db.py` 도 그대로 통과한다.

### 2. 수정

- `utils/background.py` `run_blocking`: 기다림이 끝난 뒤 결과·예외를 읽고 Task를 해제한다. 예외가 날 때도 해제한다(`finally` 의 순서 주의: 결과를 먼저 읽는다).
- 모듈 docstring의 설명은 바꾸지 않는다. 필요하면 해제 이유를 한 줄 주석으로 적는다.

### 3. 문서

- 없다.

## Acceptance Criteria

```bash
uv run pytest tests/test_background.py tests/gui/test_connect_db.py -q   # 새 테스트 통과 (수정 전에는 자식 수 단언이 실패해야 한다)
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - `utils/background.py` 가 Qt 티어(3) 밖의 것을 import하지 않는가?
   - 돌고 있는 Task를 지우는 경로가 없는가(`wait()` 가 True를 돌려준 뒤에만)?
   - `Task` 클래스와 그 시그널이 그대로인가?
3. 결과에 따라 `phases/12-gui-async-cleanup/index.json` 의 step 4를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "run_blocking 이 결과·예외를 읽은 뒤 자기 Task 를 해제(<deleteLater|setParent(None)>). RED: <테스트 이름: 단언>. 변이: <…>"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `Task` 가 `finished` 에서 스스로 지워지게 하지 마라. 이유: `tests/gui/test_connect_db.py` 가 자기 Task를 `finally` 에서 `wait()` 한다. 폴링·History는 자기 정리를 따로 한다(step 2·3).
- 끝나기 전에 해제하지 마라. 이유: 돌고 있는 QThread가 지워지면 "QThread: Destroyed while thread is still running" 으로 프로세스가 죽는다.
- `run_blocking` 의 대기 방식(wait 슬라이스, `ExcludeUserInputEvents`, 대기 커서)을 바꾸지 마라. 이유: 모듈 docstring의 이유(빨리 끝나면 quit이 무시된다)와 ADR-009.
- 기존 테스트를 깨뜨리지 마라.
