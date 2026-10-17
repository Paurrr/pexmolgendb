이 프로젝트는 Harness 프레임워크를 사용한다. 아래 워크플로우에 따라 작업을 진행하라.

---

## 워크플로우

### A. 탐색

`/docs/` 하위 문서(PRD, ARCHITECTURE, ADR, UI_GUIDE)를 읽고 프로젝트의 기획·아키텍처·설계 의도를 파악한다. 필요시 Explore 에이전트를 병렬로 사용한다. `docs/notes/` 는 프롬프트에 주입되지 않는 참고 문서다(구조 제안, 알려진 문제). 관련이 있으면 직접 연다.

### B. 논의

구현을 위해 구체화하거나 기술적으로 결정해야 할 사항이 있으면 사용자에게 제시하고 논의한다. 이 저장소는 **버그만 고친다**(CLAUDE.md). 기능 추가·리팩터·사용자에게 보이는 동작 변경은 사용자 승인 없이 step에 넣지 않는다.

### C. Step 설계

사용자가 구현 계획 작성을 지시하면 여러 step으로 나뉜 초안을 작성해 피드백을 요청한다.

설계 원칙:

1. **Scope 최소화** — 하나의 step에서 하나의 레이어 또는 모듈만 다룬다. 여러 모듈을 동시에 수정해야 하면 step을 쪼갠다.
2. **자기완결성** — 각 step 파일은 독립된 Claude 세션에서 실행된다. "이전 대화에서 논의한 바와 같이" 같은 외부 참조는 금지한다. 필요한 정보는 전부 파일 안에 적는다.
3. **사전 준비 강제** — 관련 문서 경로와 이전 step에서 생성/수정된 파일 경로를 명시한다. 세션이 코드를 읽고 맥락을 파악한 뒤 작업하도록 유도한다.
4. **시그니처 수준 지시** — 함수/클래스의 인터페이스만 제시하고 내부 구현은 에이전트 재량에 맡긴다. 단, 설계 의도에서 벗어나면 안 되는 핵심 규칙(멱등성, 보안, 데이터 무결성 등)은 반드시 명시한다.
5. **AC는 실행 가능한 커맨드** — "~가 동작해야 한다" 같은 추상적 서술이 아닌 `uv run ruff check src tests && uv run pytest -q` 같은 실제 실행 가능한 검증 커맨드를 포함한다.
6. **주의사항은 구체적으로** — "조심해라" 대신 "X를 하지 마라. 이유: Y" 형식으로 적는다.
7. **네이밍** — step name은 kebab-case slug로, 해당 step의 핵심 모듈/작업을 한두 단어로 표현한다 (예: `pool-acquire`, `env-file-bom`).
8. **버그 주장은 실패하는 테스트로 확인한다** — step에 적은 버그(분석·리뷰 에이전트의 지적 포함)는 주장이다. step은 먼저 실패하는 테스트로 재현하게 하고, RED 출력(테스트 이름과 단언)을 summary에 남기게 한다. 재현되지 않으면 `src/` 를 고치지 않고 테스트를 특성 테스트로 남긴 뒤 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다. RED는 **Windows 개발 PC에서** 보여야 한다. POSIX 전용(`posix_only`) 테스트만으로는 버그를 증명하지 못한다(개발 PC에서 skip된다). 고친 뒤에는 수정을 손으로 되돌려 테스트가 실패하는지 확인한다(`git checkout` 으로 되돌리지 않는다. 같은 step의 다른 변경까지 날아간다). 이유: 분석 단계에서 50건 넘게 나온 후보 중 일부는 실제로 닿지 않는 경로일 수 있다.
9. **범위 밖 수정 금지** — step은 적힌 버그만 고친다. 리팩터·문구 변경·기능 추가를 하지 않고, 작업 중 발견한 다른 버그는 고치지 않고 summary에 적는다. 사용자에게 보이는 동작이 바뀌는 수정(새 확인 대화상자 등)은 사용자가 승인한 것만 step에 넣고, 승인 사실을 step 파일에 적는다. 이유: 사용자 규칙이 "기능이 에러·버그가 아니면 변경 없음"이다.
10. **상태와 동시성 계약은 모든 경로를 적는다** — 저장 경로를 바꾸는 step은 성공, 충돌(`StaleWriteError` 의 `stale`/`deleted`) × 사용자 선택(Reload/Overwrite/Cancel), 예상 밖 예외, 접속 끊김마다 최종 상태(dirty 표시, baseline, `device.version`, 화면 선택, 알림 문구)와 테스트를 step에 적는다. 멈추고 이전 상태로 되돌리는 경로는 되돌릴 대상(이전 process·device)이 그 사이 지워진 경우도 표에 넣는다(phase 3에서 빠뜨려 콤보와 표가 어긋났다). 저장 함수의 반환 계약을 바꾸는 step과 호출부를 바꾸는 step을 나누고, 호출부가 새 계약을 쓰기 전에 계약 step이 먼저 끝나게 순서를 정한다.
11. **GUI 비동기 경로는 결과 × 상태로 적는다** — `run_blocking`/`Task` 콜백마다 결과(성공, 예상 오류, 예상 밖 예외)와 상태(접속 전, 접속 중, 재접속 중, 창 닫는 중)를 곱해 최종 상태와 테스트를 적는다. "아무 일도 일어나지 않음"은 고정 대기(`qtbot.wait`) 대신 fake가 기록한 호출을 `qtbot.waitUntil` 로 기다린 뒤 단언하게 한다.
12. **DB를 바꾸는 step** — `service/repo/`, `service/schema.py`, `scripts/init_db.py` 의 SQL을 바꾸는 step은 DB 테스트(`GENDB_TEST_PG_DSN`)를 AC에 넣고, 그 환경변수가 없으면 `blocked` 로 멈추게 한다(skip을 통과로 보지 않는다). SQL은 PostgreSQL 10~15에서 돌아야 한다(운영 서버는 RHEL 7 + PG 15. MERGE, `NULLS NOT DISTINCT`, PG 16+ 문법 금지).
13. **운영 환경에서만 드러나는 동작은 개발 PC에서 도는 근사 검사를 AC에 넣는다** — `tools/*.sh` 는 stub 명령으로 실제 실행하는 테스트(`tests/test_deploy_sh.py` 방식), RHEL 8 설치 가능성은 lock 휠 태그 확인(`uv pip compile pyproject.toml --python-version 3.13 --python-platform x86_64-manylinux_2_28`), `init_db` 의 Python 3.9 호환은 `ast.parse(..., feature_version=(3, 9))`, 권한 비트는 `posix_only` 테스트로 고정하고, 그래도 남는 것은 README 서버 절에 적게 한다.
14. **구조를 바꾸는 step은 기존 테스트가 아직 그 성질을 지키는지 적는다** — step이 객체 배치나 시그널 연결을 바꾸면 그 경로를 지키던 기존 테스트가 여전히 이름의 성질을 검사하는지 확인하고, 검사 대상이 사라졌으면 새 입력으로 다시 세우게 한다.

### D. 파일 생성

사용자가 승인하면 아래 파일들을 생성한다.

#### D-1. `phases/index.json` (전체 현황)

여러 task를 관리하는 top-level 인덱스. 이미 존재하면 `phases` 배열에 새 항목을 추가한다.

```json
{
  "phases": [
    {
      "dir": "0-mvp",
      "status": "pending"
    }
  ]
}
```

- `dir`: task 디렉토리명.
- `status`: `"pending"` | `"completed"` | `"error"` | `"blocked"`. execute.py가 실행 중 자동으로 업데이트한다.
- 타임스탬프(`completed_at`, `failed_at`, `blocked_at`)는 execute.py가 상태 변경 시 자동 기록한다. 생성 시 넣지 않는다.

#### D-2. `phases/{task-name}/index.json` (task 상세)

```json
{
  "project": "genviewer",
  "phase": "<task-name>",
  "steps": [
    { "step": 0, "name": "pool-acquire", "status": "pending" },
    { "step": 1, "name": "env-file-bom", "status": "pending" }
  ]
}
```

필드 규칙:

- `project`: 프로젝트명 (CLAUDE.md 참조).
- `phase`: task 이름. 디렉토리명과 일치시킨다.
- `steps[].step`: 0부터 시작하는 순번.
- `steps[].name`: kebab-case slug.
- `steps[].status`: 초기값은 모두 `"pending"`.

상태 전이와 자동 기록 필드:

| 전이 | 기록되는 필드 | 기록 주체 |
|------|-------------|----------|
| → `completed` | `completed_at`, `summary` | Claude 세션 (summary), execute.py (timestamp) |
| → `error` | `failed_at`, `error_message` | Claude 세션 (message), execute.py (timestamp) |
| → `blocked` | `blocked_at`, `blocked_reason` | Claude 세션 (reason), execute.py (timestamp) |

`summary`는 step 완료 시 산출물을 한 줄로 요약한 것으로, execute.py가 다음 step 프롬프트에 컨텍스트로 누적 전달한다. 따라서 다음 step에 유용한 정보(생성된 파일, 핵심 결정, RED 테스트 이름, `not reproduced` 여부)를 담아야 한다.

`created_at`은 execute.py가 최초 실행 시 task 레벨에 한 번만 기록한다. step 레벨의 `started_at`도 execute.py가 각 step 시작 시 자동 기록한다. 생성 시 넣지 않는다.

#### D-3. `phases/{task-name}/step{N}.md` (각 step마다 1개)

```markdown
# Step {N}: {이름}

## 읽어야 할 파일

먼저 아래 파일들을 읽고 프로젝트의 아키텍처와 설계 의도를 파악하라:

- `/docs/ARCHITECTURE.md`
- `/docs/ADR.md`
- {이전 step에서 생성/수정된 파일 경로}

이전 step에서 만들어진 코드를 꼼꼼히 읽고, 설계 의도를 이해한 뒤 작업하라.

## 버그

{주장: 파일:행, 재현 시나리오, 기대 동작. "이것은 주장이다. 먼저 재현하라."}

## 작업

{1. 실패하는 테스트 (파일 경로, 테스트가 단언할 성질)
 2. 수정 (시그니처 수준, 지켜야 할 불변식)
 3. 문서 동기화 (README 의 해당 절 등)}

## Acceptance Criteria

```bash
uv run ruff check src tests          # 린트 통과
uv run pytest -q                     # 테스트 통과
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - ARCHITECTURE.md 디렉토리 구조와 레이어 표를 따르는가?
   - ADR 기술 스택을 벗어나지 않았는가?
   - CLAUDE.md CRITICAL 규칙을 위반하지 않았는가?
3. 결과에 따라 `phases/{task-name}/index.json`의 해당 step을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "산출물 한 줄 요약 (RED 테스트 이름 포함)"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 (DB DSN, 외부 인증, 수동 설정 등) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- {이 step에서 하지 말아야 할 것. "X를 하지 마라. 이유: Y" 형식}
- 기존 테스트를 깨뜨리지 마라
```

### E. 실행

```bash
uv run python -X utf8 scripts/execute.py {task-name}         # 순차 실행
uv run python -X utf8 scripts/execute.py {task-name} --push  # 실행 후 push
```

`-X utf8` 은 빼지 않는다. 이유: 개발 PC 콘솔이 cp949라서 execute.py가 출력하는 한글·기호(`✓ ✗ ↻`)에서 인코딩 오류가 난다.

실행 전에 작업 트리를 깨끗하게 둔다. 이유: execute.py는 step마다 `git add -A` 로 커밋하므로 남아 있던 변경이 step 커밋에 섞인다.

execute.py가 자동으로 처리하는 것:

- `feat-{index.json의 phase}` 브랜치 생성/checkout (지금 HEAD에서 갈라진다)
- 가드레일 주입 — CLAUDE.md + `docs/*.md` 전체(이름순, `docs/notes/` 제외)를 매 step 프롬프트에 포함. 그래서 docs는 짧고 정확해야 한다
- 컨텍스트 누적 — 완료된 step의 summary를 다음 step 프롬프트에 전달
- 세션 실행 — `claude -p --dangerously-skip-permissions --output-format json`, 프롬프트는 stdin(Windows 명령줄 길이 제한 회피). 프로젝트 Stop 훅(ruff + pytest)도 세션 안에서 돈다
- 자가 교정 — step마다 총 3회 시도(재시도 2회). 세션이 status를 `error` 로 써도 마지막 시도 전까지는 `pending` 으로 되돌리고 이전 에러 메시지를 프롬프트에 피드백한다
- timeout — 세션당 3600s. 넘기면 실패로 보고 timeout 메시지와 함께 재시도한다
- 출력 기록 — `phases/{task-name}/step{N}-output.json` (exitCode, timedOut, stdout, stderr)
- 2단계 커밋 — 코드 `feat({phase}): step {N} — {name}`, 메타데이터(index.json, output) `chore({phase}): step {N} output`. 마지막에 `chore({phase}): mark phase completed`
- 타임스탬프 — started_at, completed_at, failed_at, blocked_at 자동 기록

에러 복구:

- **error 발생 시**: `phases/{task-name}/index.json`에서 해당 step의 `status`를 `"pending"`으로 바꾸고 `error_message`를 삭제한 뒤 재실행한다.
- **blocked 발생 시**: `blocked_reason`에 적힌 사유를 해결한 뒤(예: `GENDB_TEST_PG_DSN` 설정), `status`를 `"pending"`으로 바꾸고 `blocked_reason`을 삭제한 뒤 재실행한다.
- **step 미루기**: execute.py를 고치지 말고 그 step의 `status` 를 `"deferred"` 로 둔다. execute.py는 남은 첫 `pending` step을 고르므로 deferred step은 건너뛰지만 그 **뒤의** pending step은 실행된다. 그래서 미룰 step은 마지막 step으로 두거나 뒤 step도 함께 deferred로 둔다. 다시 돌릴 때는 그 step과 `phases/index.json` 의 phase를 `"pending"` 으로 되돌리고 커밋한 뒤 재실행한다.

### F. phase 마무리

phase가 completed 되면 다음 phase를 실행하기 전에 아래 순서로 정리한다. 각 항목은 따로 커밋한다.

1. **반영 점검** — `/review` 로 phase 브랜치 변경을 리뷰하고, step 파일 지시(불변식, 재현 테스트, 금지사항)가 코드에 반영됐는지 대조한다. `index.json` summary는 주장으로 보고 코드와 대조한다. 리뷰 에이전트의 지적도 주장이다. 고치기 전에 실패하는 테스트로 재현하고, 재현되지 않으면 고치지 않는다.
2. **docs 동기화** — 실제 구현 기준으로 `docs/ARCHITECTURE.md`(트리, 강제 테스트, 흐름)와 `docs/ADR.md`(phase 중 내린 결정), `README.md`(사용자가 보는 동작), `docs/notes/known-issues.md`(고친 것 지우기, 새로 발견한 것 더하기)를 고친다. 함수 시그니처 세부는 넣지 않는다.
3. **다음 phase step 정렬** — 다음 phase의 step 파일이 참조하는 API 이름·동작·fixture가 실제 코드와 맞는지 확인하고 고친다(`docs(<next-phase>): align step files with phase N implementation`).
4. **가드레일 점검** — CLAUDE.md, `.claude/`(이 파일, review.md, settings.json)에 phase 중 반복된 실수나 새 관례를 반영한다.
5. **합치기** — phase 브랜치를 main에 합친 뒤 main에서 다음 phase를 실행한다. 이유: execute.py는 지금 HEAD에서 `feat-<phase>` 를 갈라내므로, 합치지 않고 돌리면 phase 브랜치가 줄줄이 겹친다.
