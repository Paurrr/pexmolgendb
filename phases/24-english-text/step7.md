# Step 7: english-guard

## 배경

phase 24는 사용자가 2026-10-22에 요청하고 승인한 변경이다. 사용자에게 보이는 문구를 영어로 바꾼다(ADR-020). step 0~6이 모듈별로 문구를 옮겼다.

이 step은 다시 한국어 문구가 들어오지 못하게 **검사 테스트**를 둔다. 그 검사가 찾은 남은 문구도 옮긴다.

먼저 `phases/24-english-text/index.json` 의 step 0~6 summary를 읽어라.

**한국어로 두는 것(ADR-020)**
- 주석과 docstring. typer 명령 docstring은 `--help` 라서 제외하지 않는다.
- 로그 **파일**에만 가는 문구. `log`, `logger`, `logging` 호출의 인자다.
- 이력 요약. `service/repo/audit.py` 의 요약 함수가 만든다.
- `tools/deploy.sh` 의 런처 `marker`, 그리고 셸 주석.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`: ADR-020, `/docs/UI_GUIDE.md`: "문구"
- `tests/test_boundaries.py`: AST로 src를 훑는 기존 검사. 모듈 경로 찾기와 "스캐너 자체 검사" 패턴을 본다.
- `tests/test_py39_compat.py`: 또 하나의 정적 검사
- `src/genviewer/service/repo/audit.py`: 요약 함수
  - 대략 `device_insert`, `device_update`, `device_delete`, `tab_change`, `csv_import`, `process_add`, `process_delete`, 그리고 그것들이 부르는 도우미
  - 실제 이름은 코드에서 확인한다.
- `src/genviewer/cli.py`: typer 명령 함수(`@app.command`, `@app.callback` 데코레이터)
- `tools/deploy.sh`, `tools/initdb.sh`

## 작업

### 1. 검사 테스트 (새 파일 `tests/test_english_text.py`, Qt 없음)

**Python 문구 검사**
- `src/genviewer/**/*.py` 를 `ast` 로 읽는다(`encoding="utf-8"`).
- 문자열 상수(`ast.Constant` 의 str)와 f-string(`ast.JoinedStr`)의 글자 조각 중 한글(`[가-힣]`)이 든 것을 모은다.
- 빼는 것
  - 모듈, 클래스, 함수의 docstring. 단 typer 명령 함수(`app.command`/`app.callback` 데코레이터)의 docstring은 빼지 않는다.
  - 그 밖의 **식 문장 문자열**(`ast.Expr(Constant(str))`). 대입 뒤에 붙인 설명 문자열 같은 것이다.
  - 로그 호출의 인자. 호출 대상이 `log.<메서드>`, `logger.<메서드>`, `logging.<메서드>`, `<모듈 로거 이름>.<메서드>` 이고 메서드가 `debug/info/warning/error/exception/critical/log` 인 것이다. 로거 변수 이름은 코드에서 확인한다.
  - 허용 목록. `(모듈, 함수 이름)` 튜플이고, 이력 요약을 만드는 audit 함수와 그 도우미다. 각 항목에 이유 주석을 단다.
- 실패 메시지는 `파일:행: 문자열` 목록이다.

**셸 출력 검사**
- `tools/*.sh` 에서 `#` 로 시작하는 주석 줄을 빼고, `marker=` 줄을 뺀 나머지 중 한글이 든 줄을 모은다.
- 기대값은 빈 목록이다.

**스캐너 자체 검사** (`test_boundaries.py` 의 방식)
- 작은 소스 문자열을 parametrize한다.
- 잡혀야 하는 것
  - `QMessageBox.warning(None, "T", "한글")`
  - typer 명령 docstring의 한글
  - f-string 조각의 한글
- 잡히면 안 되는 것
  - 모듈 docstring
  - `log.info("한글")`
  - `# 한글` 주석
  - 허용 목록 함수 안의 문자열

### 2. 남은 문구

- 검사가 잡은 문구는 ADR-020 범위 안이면 영어로 옮긴다. 함께 고정된 테스트도 고친다.
  - 어느 step의 빠뜨림인지 summary에 적는다.
- 범위 밖으로 보이면 허용 목록에 이유와 함께 더한다.
  - 예: 사용자가 결코 보지 않는 내부 가드 문구라면 그렇게 판단한 근거를 적는다.
  - 판단이 어려우면 옮기지 말고 summary에 적는다.

### 3. 변이 검사

- 메시지 상자 문구 하나(예: `dialogs/add_process.py` 의 이유 줄)를 손으로 한국어로 되돌리면 검사가 실패해야 한다. 다시 고친다.
- `tools/initdb.sh` 의 echo 하나를 한국어로 되돌리면 셸 검사가 실패해야 한다. 다시 고친다. 파일은 LF, `100755` 를 유지한다.

## Acceptance Criteria

```bash
uv run ruff check src tests
uv run pytest tests/test_english_text.py tests/test_boundaries.py -q
uv run pytest -q -rs   # GENDB_TEST_PG_DSN 이 있어야 한다. phase 끝이라 전체를 DB 까지 돌린다
```

- `GENDB_TEST_PG_DSN` 이 비어 있으면 `blocked` 로 멈춘다. 이유: phase 24가 서비스·CLI·init_db 문구를 바꿨다. 마지막 step에서 전체를 DB 테스트까지 확인한다.

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 검사 테스트가 PySide6를 import하지 않는가(정적 검사)?
   - 허용 목록이 좁은가? 함수 이름으로 고르고, 모듈 전체를 빼지 않는다.
   - 로그 파일 문구, 주석, docstring의 한국어가 그대로인가?
3. 결과에 따라 `phases/24-english-text/index.json` 의 step 7을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "tests/test_english_text.py(AST 문구 검사 + tools/*.sh 출력 검사 + 스캐너 자체 검사, 허용: audit 요약 함수 <이름들>·로그 호출·docstring·marker). 남은 문구 <n>개 옮김(<파일:행>). 변이: <결과>. DB 테스트: <passed/skipped>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요(DSN 없음 등) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 허용 목록에 모듈 전체나 `views/`·`controllers/` 같은 디렉터리를 넣지 마라. 이유: 검사가 아무것도 지키지 못한다.
- 이력 요약 문장, 로그 파일 문구, 주석, docstring을 번역하지 마라. 이유: ADR-020.
- `marker=` 줄을 바꾸지 마라. 이유: 옛 런처를 찾는 식별자다.
- 테스트 디렉터리(`tests/`)의 한국어를 검사 대상에 넣지 마라. 이유: 테스트 데이터와 메시지는 범위 밖이다.
- 기존 테스트를 깨뜨리지 마라.
