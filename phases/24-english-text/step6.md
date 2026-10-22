# Step 6: shell-text

## 배경

phase 24는 사용자가 2026-10-22에 요청하고 승인한 변경이다. 사용자에게 보이는 문구를 영어로 바꾼다(ADR-020).

이 step은 **`tools/initdb.sh` 와 `tools/deploy.sh` 의 출력**을 맡는다. 대상은 `echo` 와 `printf` 줄, 그리고 deploy.sh가 만드는 런처가 실행될 때 찍는 줄이다.

먼저 `phases/24-english-text/index.json` 의 summary를 읽어라.

**바꾸지 않는 것**
- `tools/deploy.sh` ~145 `marker="genviewer deploy.sh 가 생성"`.
  - 생성된 런처의 주석에 들어간다(~162).
  - 다음 배포는 `grep -q "$marker"` 로 자기가 만든 옛 런처를 찾아 지운다.
  - 바꾸면 옛 배포가 만든 런처를 못 알아봐서, 이름이 바뀌거나 빠진 명령의 런처가 남는다(ADR-020).
- 셸 주석(`#` 줄)은 한국어로 둔다. 런처에 써 넣는 주석 줄(~161-162)도 주석이다.

phase 24 공통 규칙:
1. 승인된 변경이라 RED 대신 변이 검사를 한다. 바꾼 echo 하나를 손으로 되돌려, 고친 테스트가 실패하는지 본다. `git checkout`/`git stash` 로 되돌리지 마라.
2. 대상 파일의 한글을 `rg -n "[가-힣]" tools/*.sh` 로 찾는다. 출력 줄만 옮긴다. 주석과 marker는 그대로 둔다.
3. 그 문구를 고정한 테스트를 같이 고친다. 없음 단언(`test_initdb_sh.py` ~192 `"추가" not in`)도 대상이다. 테스트 안 stub 스크립트의 자기 메시지는 그대로 둔다.
4. 동작, 종료 코드, 출력 줄의 수와 순서는 바꾸지 않는다.
5. README의 셸 출력 예시는 phase 마무리에서 고친다.

## 읽어야 할 파일

- `/CLAUDE.md`: 셸 스크립트 규칙. LF로 커밋하고 실행 비트를 유지한다. 셸 테스트는 stub으로 실제 실행한다.
- `/docs/ADR.md`: ADR-011(deploy.sh), ADR-020
- `tools/initdb.sh`(전체), `tools/deploy.sh`(전체)
- `tests/test_initdb_sh.py`, `tests/test_deploy_sh.py`: PATH·`PGBIN` 앞에 stub을 두고 실제로 실행한다.
- `.gitattributes`

## 작업

### 1. 옮길 출력 (대략, 권장 영어)

**`tools/initdb.sh`**
- ~21-22 (stderr)
  - `"error: PGHBA_CIDR needs PGAUTH_HOST too (e.g. PGAUTH_HOST=scram-sha-256)."`
  - `"       The default trust opens that whole range without authentication. To really do that, set PGAUTH_HOST=trust."`
- ~46 `"Cluster already exists: $PGDATA (skipping initdb)"`
- ~82 `"==> added to pg_hba.conf: $hba_line"`
- ~87 `"==> skipping start (SKIP_START=1)"`
- ~94 `"==> skipping start (already running)"`
- ~114 `"   created"`
- ~116 `"   already exists"`
- ~118 (stderr) `"   failed: $err"`
- ~123 `"Done. Environment:"`

**`tools/deploy.sh`**
- error/warning/note 줄(~46, ~59, ~114, ~123, ~226-227, ~242, ~257-259, ~278, ~191)
  - 접두어 `error:`/`warning:`/`note:` 는 그대로 둔다. 뒤 문장만 옮긴다.
- 생성 런처가 실행 때 찍는 줄(~165-168). heredoc 안의 `\$` 이스케이프를 그대로 지킨다.
- 안내 줄
  - ~187 `"Created $root/genviewer.env. Fill in the values and give it to the team group:"`
  - ~189 `chgrp <team-group> …`
  - ~297-298 `"Linked into $DEPLOY_LINK_DIR. Users already have it on PATH."` / `"Nothing else to change."`
  - ~300 `"Users add this line to their shell profile:"`

### 2. 함께 고칠 테스트

- `tests/test_initdb_sh.py` ~134, ~142, ~155, ~182, ~188, ~192(없음 단언)를 새 출력에 맞춘다.
  - ~192는 "두 번째 실행에서는 pg_hba 줄을 더하지 않는다"는 뜻이다. 영어 출력의 같은 낱말로 바꾼다. 예: `"added to pg_hba.conf" not in second.stdout`.
  - 이 단언이 실제로 무엇을 지키는지 확인한다. 그 줄을 다시 찍게 손으로 바꿨을 때 실패해야 한다.
- `tests/test_deploy_sh.py`: deploy.sh 출력을 보는 단언이 있으면 맞춘다. marker를 보는 단언은 그대로 둔다.

### 3. 셸 파일 규칙

- 고친 뒤 LF인지 확인한다: `python -c "import sys;print(any(b'\r\n' in open(p,'rb').read() for p in sys.argv[1:]))" tools/initdb.sh tools/deploy.sh` 가 `False` 여야 한다.
- 실행 비트가 그대로인지 확인한다: `git ls-files -s tools/` 가 두 파일 모두 `100755` 여야 한다. 바뀌었으면 `git update-index --chmod=+x <file>` 로 되돌린다.
- 문법 검사는 파일마다 따로 한다. `sh -n a b` 는 a만 본다.

## Acceptance Criteria

```bash
sh -n tools/deploy.sh
sh -n tools/initdb.sh
uv run ruff check src tests
uv run pytest tests/test_initdb_sh.py tests/test_deploy_sh.py -q
uv run pytest -q
```

- Git Bash에서 돌린다. `sh` 가 PATH에 없으면 셸 테스트 32개가 skip된다. skip이면 통과로 보지 말고 `blocked` 로 멈춘다.

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - `marker=` 줄과 셸 주석이 그대로인가? `git diff tools/` 로 본다.
   - 동작 줄(변수, 조건, 명령)은 그대로이고 출력 글자만 바뀌었는가?
   - 두 파일이 LF이고 `100755` 인가?
3. 결과에 따라 `phases/24-english-text/index.json` 의 step 6을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "tools/initdb.sh·deploy.sh 출력 영어화(marker·주석 그대로, LF·100755 유지). 고친 테스트: <파일들>. 변이: <결과>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요(`sh` 없음 등) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `marker=` 값과 그것을 쓰는 `grep` 을 바꾸지 마라. 이유: 옛 배포의 런처를 찾는 식별자다.
- 셸 주석을 번역하지 마라. 이유: ADR-020 범위 밖이다.
- echo 말고 다른 줄(변수, 조건, 명령, 종료 코드)을 바꾸지 마라. 이유: 운영 서버 배포 스크립트다.
- 파일을 CRLF로 저장하지 마라. 실행 비트를 잃지 마라. 이유: 서버에서 `bad interpreter` 가 난다(CLAUDE.md).
- `genviewer.env.example` 의 주석을 바꾸지 마라. 이유: 주석이고 범위 밖이다.
- 기존 테스트를 깨뜨리지 마라.
