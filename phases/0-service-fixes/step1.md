# Step 1: env-file-bom

## 배경 (phase 0 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 0은 Qt를 쓰지 않는 계층(`service/`, `cli.py`, `utils/logs.py`)의 버그 넷을 하나씩 고친다.

모든 step에 같은 규칙이 적용된다.
1. 아래 "버그"는 **분석 에이전트의 주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 버그를 증명하지 못한다.
3. 재현되지 않으면 `src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.

## 이 step의 목적

UTF-8 BOM으로 시작하는 `genviewer.env` 도 정상적으로 읽히게 한다. 지금은 앱이 "키 이름으로 쓸 수 없다" 며 시작을 거부한다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`(ADR-007 설정 파일)
- `src/genviewer/service/env_file.py` — `load()` 의 `path.read_text(encoding="utf-8")` (~177), `UnicodeDecodeError` 처리(cp949 안내), `parse()` (~54-80, 각 줄 `strip()` 후 `_KEY.fullmatch`)
- `tests/test_env_file.py` — autouse `clean_env`, `site` fixture(개인 파일·설치 디렉터리를 tmp로 돌린다), `write` 헬퍼, `test_a_cp949_file_is_reported_as_encoding`
- 이전 step에서 수정된 파일: `src/genviewer/service/pool.py`, `tests/test_pool.py` (이 step과 관계없음)

## 버그

Windows PowerShell 5.1의 `Out-File -Encoding utf8`/`Set-Content -Encoding utf8` 과 메모장의 "UTF-8 (BOM)" 저장은 파일 앞에 BOM(`EF BB BF`)을 쓴다. `read_text(encoding="utf-8")` 는 BOM을 `'﻿'` 문자로 남긴다. `str.strip()` 은 `'﻿'` 를 공백으로 보지 않으므로 첫 키가 `'﻿PGHOST'` 가 된다. 그러면 `_KEY.fullmatch` 가 실패하고 `ValueError("1행: 키 이름으로 쓸 수 없다: '﻿PGHOST'")` 를 내고, `load()` 가 이것을 `RuntimeError` 로 바꿔 앱이 뜨지 않는다. 사용자에게는 눈에 보이지 않는 문자 때문에 거부되는 것처럼 보인다.

## 작업

### 1. 테스트 먼저 (`tests/test_env_file.py`)

- `site` fixture의 설치 디렉터리 파일에 `b"\xef\xbb\xbfPGHOST=10.1.2.3\nPGPORT=55433\n"` 를 **바이트로** 쓴다(`write_bytes`). `env_file.load()` 가 그 경로를 돌려주고, `os.environ["PGHOST"] == "10.1.2.3"`, `os.environ["PGPORT"] == "55433"` 이다.
- 같은 파일에 PGPASSWORD가 있어도 권한 검사 동작은 그대로다. Windows에서는 검사하지 않으므로 이 step에서 새로 단언할 필요는 없다.
- 기존 `test_a_cp949_file_is_reported_as_encoding` 은 그대로 통과해야 한다. cp949 파일은 여전히 "UTF-8 이 아니다" 안내로 거부된다.

### 2. 수정 (`service/env_file.py`)

- `load()` 에서 파일을 `encoding="utf-8-sig"` 로 읽는다. BOM이 없는 UTF-8 파일은 똑같이 읽히고, BOM이 있으면 벗겨진다.
- 바꾸는 곳은 이 한 줄이다.

### 3. 문서

- 바꿀 문서는 없다. README의 형식 설명은 그대로 맞다.

## Acceptance Criteria

```bash
uv run pytest tests/test_env_file.py -q    # 새 테스트 통과 (수정 전에는 실패해야 한다)
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `service/env_file.py` 가 stdlib만 쓰는가?
   - "파일은 하나만 읽는다", "이미 있는 환경변수가 이긴다" 동작이 그대로인가(기존 테스트)?
3. 결과에 따라 `phases/0-service-fixes/index.json` 의 step 1을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "env_file.load 를 utf-8-sig 로 읽어 BOM 파일 허용. RED: <테스트 이름>"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `parse()` 에서 `'﻿'` 를 지우거나 키 정규식을 넓히지 마라. 이유: 문제는 파일 디코딩 하나뿐이다. `parse()` 는 문자열을 받는 순수 함수이고, 중간 줄에 들어간 이상한 문자는 지금처럼 알려야 한다.
- cp949 등 다른 인코딩으로 "다시 시도해서 읽기" 를 넣지 마라. 이유: 비밀번호가 든 파일을 추측으로 해석하면 안 된다. 지금의 "UTF-8 이 아니다" 안내가 의도된 동작이다.
- 주석 규칙(줄 전체만, 값 뒤의 `#` 는 값)이나 따옴표 규칙을 바꾸지 마라. 이유: 이 step의 범위가 아니다(ADR-007).
- 기존 테스트를 깨뜨리지 마라.
