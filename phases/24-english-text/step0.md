# Step 0: service-messages

## 배경

이 저장소는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 24는 사용자가 2026-10-22에 요청하고 승인한 변경이다. GUI·CLI·셸 스크립트가 보이거나 묻는 문구를 영어로 바꾼다(ADR-020).

**범위(ADR-020)**
- 한국어로 두는 것: 주석, docstring, 문서, 로그 파일에만 가는 문구, 이력 요약(`change_log.summary`), `deploy.sh` 의 런처 marker.
- 문장 규칙과 용어는 `docs/UI_GUIDE.md` "문구" 의 규칙과 용어표를 따른다.
- 이 step은 **서비스 계층의 공용 문구**를 맡는다. GUI와 CLI가 함께 보여 주는 오류 안내 등이다. 화면·CLI 쪽 자기 문구는 뒤 step이 맡는다.

phase 24 공통 규칙:
1. 승인된 변경이라 RED 대신 변이 검사를 한다. 바꾼 문구 하나를 손으로 한국어로 되돌려, 고친 테스트가 실패하는지 본다. `git checkout`/`git stash` 로 되돌리지 마라.
2. 대상 파일의 한글 문자열을 `rg -n "[가-힣]" <파일>` 로 찾는다.
   - 주석, docstring, 로그 파일 호출(`log.*`, `logger.*`, `logging.*` 의 인자)은 그대로 둔다.
   - 나머지는 모두 옮긴다.
   - 아래 목록은 2026-10-22 조사 기준 대략값이다.
3. 그 문구를 고정한 테스트를 `rg -n "<한국어 조각>" tests` 로 찾아 같이 고친다. 같음 단언, 포함 단언, **없음 단언**(`not in`, `not startswith`)이 모두 대상이다.
   - 없음 단언을 한국어로 두면 아무것도 지키지 않으면서 통과한다.
   - 테스트 **데이터**로 쓴 한국어(device 설명 `"입력단 NMOS"`, 파일 이름 `"없음.csv"` 등)와 테스트 자신의 assert 메시지는 그대로 둔다.
4. 다른 step 대상 파일의 문구는 건드리지 않는다. 같은 문구가 이 step 파일과 다른 step 파일에 따로 있으면 이 step의 것만 바꾸고 summary에 적는다.
5. 동작, 구조, 이미 영어인 문구는 바꾸지 않는다.
6. README 출력 예시와 UI_GUIDE 서술은 phase 마무리에서 고친다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`: "문구"(규칙과 용어표), `/docs/ADR.md`: ADR-020
- `src/genviewer/service/errors.py`(전체): `Conflict.describe`, SQLSTATE 안내, `user_message`
- `src/genviewer/service/config.py`, `src/genviewer/service/env_file.py`
- `src/genviewer/service/repo/io.py`, `repo/process.py`, `repo/parameter.py`
- `src/genviewer/utils/exporter.py`
- `tests/gui_support/fakes.py`: 실제 repo 문구를 그대로 베낀 곳
- `tests/gui/test_fake_repo_contract.py`: 가짜와 실제 PostgreSQL에 같은 기대값을 돌린다

## 작업

### 1. 옮길 문구 (대략, 2026-10-22 기준)

**`service/errors.py`**
- `Conflict.describe()`
  - `"다른 사용자"` → `another user`
  - 동사 `수정/삭제/변경` → `modified/deleted/changed`
  - 줄 `f"{name}: {who} 님이 {verb}{tail}"` → `f"{name}: {verb} by {who}{tail}"`
  - 예: `nfet_b: modified by bob (2026-10-22 10:00)`. 시각 꼬리 형식은 그대로다.
- SQLSTATE별 안내 15개와 접속 불가 안내(~53-70). 예:
  - `"같은 값이 이미 있다."` → `"The same value already exists."`
  - `"서버가 연결을 끊었다. 다시 접속할 것."` → `"The server closed the connection. Connect again."`
  - `"데이터베이스에 접속할 수 없다. 서버 상태와 접속 설정을 확인할 것."` → `"Cannot connect to the database. Check the server and the connection settings."`
  - `"테이블이 없다. genviewer-init-db 를 먼저 실행할 것."` → `"Tables are missing. Run genviewer-init-db first."`

**나머지 파일**
- `service/config.py` ~75: 접속 정보가 없다는 안내(여러 줄). 이름(`--dsn`, 환경변수, `Connect` 다이얼로그, 설정 파일)은 그대로 둔다.
- `service/env_file.py`: ~75, ~78(행 번호·키 이름 오류), ~154(비밀번호 파일 권한 + `chmod 640` 줄), ~179, ~183(읽을 수 없음, UTF-8 아님)
  - 첫 줄 + 들여쓴 둘째 줄 모양은 그대로 둔다. GUI가 첫 줄만 보인다.
- `service/repo/io.py` ~94: `f"CSV 파일이 없다: {data_path}"` → `f"CSV file not found: {data_path}"`
  - `cli.py` ~255가 같은 글자를 따로 찍는다. 그것은 step 4가 같은 영어로 맞춘다. 여기서는 io.py만 바꾸고 summary에 적는다.
- `service/repo/process.py` ~203: `f"원본 process 가 없다: {label}"` → `f"Source process not found: {label}"`
- `service/repo/parameter.py` ~18: 없는 컬럼 가드 문구
- `utils/exporter.py` ~71: `"xlsx 로 쓰려면 openpyxl 이 필요하다."` → `"Writing xlsx needs openpyxl."`
- `tests/gui_support/fakes.py` ~502, ~720: 위 process.py·io.py 문구의 사본. 같은 영어로 바꾼다.

### 2. 함께 고칠 테스트 (대표, `rg` 로 빠짐없이 찾는다)

| 파일 | 고정한 것 |
|---|---|
| `tests/test_logs.py` ~247-270 | errors 문구의 조각(`"오래 걸려"`, `"다른 사용자"`, `"권한"`, `"이미 있다"`, `"접속"`) |
| `tests/test_pool.py` ~70 | `"접속할 수 없다"` |
| `tests/test_env_file.py` ~98, ~103, ~190 | `match="2행"`, `"키 이름"`, `"쓰레기\|행"` |
| `tests/gui/test_add_release.py` ~415 | `user_message(LookupError("원본 process 가 없다: …"))` |
| `tests/gui/test_fake_repo_contract.py` ~363 | 원본 없음 문구. 실제 PG 쪽까지 돈다 |
| `tests/gui/test_device_save_guards.py` ~369, ~396 | `describe()` 줄 `"nfet_b: bob 님이 수정 …"` |
| `tests/test_cli.py` | 위 문구가 섞인 출력. `오류:` 접두어는 step 4가 바꾸니 그대로 두고 메시지 부분만 맞춘다 |

## Acceptance Criteria

```bash
uv run ruff check src tests
uv run pytest tests/test_logs.py tests/test_pool.py tests/test_env_file.py tests/test_py39_compat.py -q
uv run pytest tests/gui -q
uv run pytest -q -rs   # GENDB_TEST_PG_DSN 이 있어야 한다(아래). contract test 실제 쪽까지
```

- `GENDB_TEST_PG_DSN` 이 비어 있으면 `blocked` 로 멈춘다. skip을 통과로 보지 않는다. 이유: `test_fake_repo_contract.py` 의 실제 PostgreSQL 쪽이 바뀐 문구를 단언한다.

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - `user_message` 의 구조는 그대로인가? 첫 줄 머리말, 둘째 줄 이후, `scrub` 을 거친다.
   - 비밀번호를 가리는 경로가 그대로인가?
   - `service/config.py` 가 init_db의 import 경로에 걸리면 Python 3.9 호환이 그대로인가(`test_py39_compat.py`)?
   - 로그 파일 호출의 한국어는 그대로인가?
3. 결과에 따라 `phases/24-english-text/index.json` 의 step 0을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "service 공용 문구 영어화: errors(user_message 머리말·describe 'X: modified by Y'), config, env_file, io, process, parameter, exporter + fakes 사본. 고친 테스트: <파일들>. cli.py 의 같은 CSV 문구는 step 4. 변이: <결과>. DB 테스트: <passed/skipped>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요(DSN 없음 등) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `service/repo/audit.py` 의 이력 요약 문장을 바꾸지 마라. 이유: ADR-020. DB에 저장되는 데이터라 한국어로 둔다.
- 로그 파일에만 가는 문구, 주석, docstring을 번역하지 마라. 이유: ADR-020 범위 밖이다.
- `str(exc)` 로 바꾸거나 `scrub` 을 빼지 마라. 이유: 비밀번호가 샌다(CLAUDE.md CRITICAL).
- 예외 타입, SQLSTATE 매핑, 메시지의 줄 구조를 바꾸지 마라. 이유: 문구만 옮기는 step이다.
- 다른 step 대상 파일(`cli.py`, `dialogs/`, `controllers/`, `views/`, `scripts/`, `tools/`)의 문구를 바꾸지 마라. 이유: 그 step의 테스트 수정과 섞인다.
- 기존 테스트를 깨뜨리지 마라. 문구에 맞춰 기대값만 바꾼다.
