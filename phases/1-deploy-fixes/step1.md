# Step 1: deploy-locked

## 배경 (phase 1 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 1은 배포·클러스터 셸 스크립트(`tools/deploy.sh`, `tools/initdb.sh`)와 deploy.sh 가 만드는 런처(`<ROOT>/bin/<명령>`)의 버그 넷을 하나씩 고친다. 셸 스크립트 테스트는 진짜 `sh`·`git` 으로 스크립트를 실행한다. PATH 앞(또는 `PGBIN`)에 둔 stub 명령이 받은 인자를 파일에 기록하고, 테스트는 그 기록과 결과 디렉터리를 단언한다(`tests/test_deploy_sh.py` 방식). 스크립트 본문의 토큰 검사만으로 끝내지 않는다. 개발 PC는 Windows이고 테스트는 Git Bash `sh` 로 돈다(2026-10-17 기준 `tests/test_deploy_sh.py` 는 개발 PC에서 11 passed / 5 skipped).

모든 step에 같은 규칙이 적용된다.
1. 아래 "버그"는 **분석 에이전트의 주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서**(Git Bash `sh`) 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 버그를 증명하지 못한다. `sh`/`git` 이 없어서 skip된 테스트도 RED가 아니다.
3. 재현되지 않으면 `tools/`·`src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.

## 이 step의 목적

`tools/deploy.sh` 의 `uv sync` 를 `--frozen` 대신 `--locked` 로 부른다. 그러면 `pyproject.toml` 과 `uv.lock` 이 어긋난 태그를 배포할 때 배포가 그 자리에서 멈춘다. 지금 스크립트 주석은 `--frozen` 이 막는다고 적었지만, 실제로 `--frozen` 은 검사하지 않는다.

**사용자 승인 2026-10-17**: lock이 pyproject와 어긋난 태그는 이제 배포가 실패한다. 지금은 lock에 적힌 대로 조용히 깔린다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`(ADR-011, 특히 트레이드오프 마지막 문장), `/docs/ARCHITECTURE.md`(배포 구조)
- `/README.md` '배포'(~236-300) — "`uv sync --frozen --no-editable` 이라 …" 항목과 그 아래 "주의: `--frozen` 은 … `phases/1-deploy-fixes` 에 있다." 하위 항목(~274-279)
- `tools/deploy.sh` — "가상환경과 설치" 절 주석(~71-80), `uv sync` 호출 두 곳(~82-88: `DEPLOY_PYTHON` 이 있을 때와 없을 때)
- `tests/test_deploy_sh.py` — `UV_STUB`(받은 인자를 `ARGS: $*` 한 줄로 기록), `test_uv_is_asked_for_a_locked_non_editable_install`(~174-187), `test_deploy_python_is_passed_through`(~190-194)
- `uv sync --help` 의 `--locked`, `--frozen` 설명
- 이전 step에서 수정된 파일: `tools/deploy.sh`(런처 heredoc), `tests/test_deploy_sh.py`(런처 테스트), `tests/test_env_file.py`, `README.md`('찾는 순서', '배포'), `docs/ARCHITECTURE.md`, `src/genviewer/service/env_file.py`(docstring), `src/genviewer/utils/logs.py`(주석). 같은 파일이지만 이 step이 고칠 절과는 겹치지 않는다.

## 버그

`tools/deploy.sh` 주석은 이렇게 말한다.

```sh
# uv pip install 이 아니라 uv sync --frozen 을 쓴다. … 배포할 때마다 의존성을 다시 푸는
# 것이 아니라 uv.lock 을 그대로 재현해야 한다. pyproject 와 lock 이 어긋나 있으면
# --frozen 이 여기서 막는다.
```

uv에서 두 플래그의 뜻은 다르다.
- `--frozen`: lock을 갱신하지 않고, **최신인지 검사하지도 않고** lock의 버전을 그대로 쓴다. pyproject에만 더한 의존성은 에러 없이 환경에서 빠진다.
- `--locked`: lock이 최신인지 단언한다. 아니면 에러로 끝난다(`… needs to be updated, but --locked was provided. To update the lockfile, run uv lock.`).
- 둘은 같이 쓸 수 없다. `uv sync --locked --frozen` 은 `error: the argument '--locked' cannot be used with '--frozen'` 로 거부된다(uv 0.11.25에서 확인).

결과: 의존성을 pyproject에 더하고 `uv lock` 을 잊은 태그를 배포하면 배포는 성공으로 끝나지만, 새 의존성이 venv에 없다. 사용자는 실행 중에 `ImportError` 를 본다. 스크립트 마지막 확인(`--help`)은 그 import 경로에 닿지 않을 수 있다.

재현(테스트): 가짜 uv의 기록에 `--frozen` 이 있고 `--locked` 가 없다. 진짜 uv로 불일치를 재현하는 테스트는 두지 않는다. 네트워크와 시간이 들고, 플래그의 뜻은 uv가 정한다.

## 작업

### 1. 테스트 먼저 (`tests/test_deploy_sh.py`)

- `test_uv_is_asked_for_a_locked_non_editable_install`: `assert "--frozen" in record` 를 `--locked` 가 있고 `--frozen` 이 없다는 단언으로 바꾼다. 기록에서 `ARGS:` 로 시작하는 줄마다 본다. docstring의 "--frozen 은 uv.lock 재현" 도 `--locked` 의 뜻(lock이 pyproject와 맞는지 검사하고 그대로 재현)으로 고친다. **수정 전에는 실패해야 한다.**
- `test_deploy_python_is_passed_through`: `DEPLOY_PYTHON` 분기에서도 `--locked` 가 있고 `--frozen` 이 없다는 단언을 더한다. 이유: `uv sync` 호출이 두 곳이라 한쪽만 고치는 실수를 막아야 한다. **수정 전에는 실패해야 한다.**
- `--no-editable`, `--no-dev`, venv 위치(`ENV:` 줄) 단언은 그대로 둔다.

### 2. 수정 (`tools/deploy.sh`)

- 두 `uv sync` 호출에서 `--frozen` 을 `--locked` 로 바꾼다. 다른 인자(`--no-dev --no-editable --project "$root/src"`, `--python "$DEPLOY_PYTHON"`)와 `UV_PROJECT_ENVIRONMENT="$root/venv"` 는 그대로 둔다.
- "가상환경과 설치" 절 주석을 실제 뜻으로 고친다: `--locked` 는 lock이 pyproject와 맞는지 검사하고, 어긋나면 배포를 여기서 멈춘다. lock을 고치지는 않는다. 태그를 달기 전에 `uv lock` 결과를 커밋해야 한다.
- 실패를 따로 감싸는 메시지는 넣지 않는다. uv 자체 문구가 `uv lock` 을 하라고 알려 준다. `set -eu` 라 그 자리에서 멈춘다. 이때 `src` 는 이미 새 태그로 옮겨졌지만 venv는 이전 배포 그대로다. `--no-editable` 이라 사용자 앱은 옛 버전으로 계속 돈다. 이것은 지금의 다른 uv 실패와 같은 상태다. 바꾸지 않는다.

### 3. 문서

- `README.md` '배포': "`uv sync --frozen --no-editable` 이라" 를 `uv sync --locked --no-editable` 로 고친다. pyproject와 lock이 어긋난 태그는 거기서 멈춘다(태그 전에 `uv lock`)는 말을 한 마디 더한다. 그 아래 "주의: `--frozen` 은 … `phases/1-deploy-fixes` 에 있다." 하위 항목은 지운다.
- `docs/ADR.md` ADR-011: 결정의 `uv sync --no-dev --no-editable` 를 `uv sync --locked --no-dev --no-editable` 로 고친다. 트레이드오프 마지막 문장("현재 `--frozen` 은 lock과 pyproject의 불일치를 검사하지 않는다(phase `1-deploy-fixes` 에서 `--locked` 로 바꾼다).")은 지운다.
- `docs/ARCHITECTURE.md` 배포 구조의 `<ROOT>/venv  uv sync --no-dev --no-editable` 에도 `--locked` 를 넣는다.

## Acceptance Criteria

```bash
sh -n tools/deploy.sh && sh -n tools/initdb.sh       # 문법 검사 (sh -n 은 첫 파일만 보므로 따로 돌린다)
! git ls-files --eol tools/*.sh | grep -v 'w/lf'     # 작업 트리가 LF 그대로
uv lock --locked                                     # 지금 lock이 pyproject와 맞다. 어긋나 있으면 다음 배포부터 실패한다
uv run pytest tests/test_deploy_sh.py -q -rs         # 바꾼 테스트 통과 (수정 전에는 두 테스트가 실패해야 한다). skip 없이 돌았는지 -rs 로 본다
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - ADR-011대로 `uv.lock` 을 그대로 재현하는가(배포 중에 lock을 다시 풀지 않는가)?
   - `--no-editable`, `--no-dev`, `UV_PROJECT_ENVIRONMENT="$root/venv"` 가 두 호출 모두에 그대로 있는가?
   - deploy.sh가 여전히 POSIX `#!/bin/sh` 인가?
3. 결과에 따라 `phases/1-deploy-fixes/index.json` 의 step 1을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "deploy.sh uv sync 두 곳을 --frozen → --locked (lock 불일치면 배포 중단), 주석 정정. RED: <테스트 이름>. README 배포·ADR-011·ARCHITECTURE 정리"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - `uv lock --locked` 가 lock이 어긋났다고 실패 → `"status": "blocked"`, `"blocked_reason": "uv.lock 이 pyproject.toml 과 맞지 않음. uv lock 으로 갱신할지 사람이 정해야 함"` 후 즉시 중단
   - 그 밖에 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `--frozen` 과 `--locked` 를 같이 주지 마라. 이유: uv가 인자 단계에서 거부해서 모든 배포가 실패한다.
- `uv.lock` 이나 `pyproject.toml` 을 고치지 마라(`uv lock` 실행 포함). 이유: 의존성 변경은 이 step의 범위가 아니고, lock 갱신은 사람이 정한다.
- deploy.sh 안에서 `uv lock` 이나 `uv pip install` 을 부르지 마라. 이유: ADR-011. PySide6 6.9.3 → manylinux_2_28 → Python 3.13 사슬 때문에 배포는 lock을 다시 풀지 않고 그대로 재현해야 한다.
- `--no-editable`, `--no-dev` 를 빼지 마라. 이유: ADR-011. editable이면 `src` 를 고치는 순간 전원의 앱이 바뀐다.
- `DEPLOY_COMMANDS` 로 없는 명령을 줄 때의 확인 누락(known-issues K29)은 고치지 마라. 이유: 기록만 한 문제이고 이 step의 범위가 아니다.
- 기존 테스트를 깨뜨리지 마라.
