# Step 1: remove-import-sqlite

## 배경 (phase 5 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 5는 예외다. **사용자가 2026-10-17 승인한 제거 작업**이다.
데이터는 공유 PostgreSQL에 있고 `.sqlite` 파일은 더 이상 쓰지 않는다. 그래서 옛 `.sqlite` 이관 도구(`genviewer-import-sqlite`)와 레거시 SQLite 스키마·픽스처를 지운다. 지우기만 한다. 기능을 더하거나 리팩터하지 않는다.

모든 step에 같은 규칙이 적용된다.
1. 버그 수정이 아니므로 RED 재현은 없다. 대신 남거나 바뀐 검사가 **여전히 실패할 수 있는지** 확인한다. 코드를 손으로 망가뜨려 실패를 보고(변이 검사) 손으로 되돌린다. `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 다른 변경까지 사라진다.
2. 파일 삭제는 `git rm` 으로 한다(`rm -rf` 는 훅이 막는다).
3. PostgreSQL DDL·SQL은 바꾸지 않는다. 그래서 하네스 규칙 12(DB 테스트 필수)는 해당하지 않는다.
   - `GENDB_TEST_PG_DSN` 이 설정돼 있으면 `uv run pytest -q -rs` 로 DB 테스트까지 돌린다. summary에 `DB 테스트: <N passed | 안 돎(DSN 없음)>` 을 적는다.
   - DSN이 없어도 `blocked` 가 아니다.
4. 역사를 설명하는 문장은 남긴다. sqlite를 쓰라는 안내가 아니라 지금 구조가 왜 이런지 설명하는 문장이기 때문이다.
   - `README.md` 첫 문단("예전처럼 각자 `.sqlite` 파일을 들고 …")
   - `docs/PRD.md` 첫 문단
   - `docs/ADR.md` ADR-001 결정
   - `src/genviewer/utils/background.py` 모듈 docstring
   - `tests/test_export.py` 의 "SQLite 는 rowid 순서를 …" 주석
5. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.
6. step 순서는 다음과 같다.
   - 0: tab_config 검사를 PostgreSQL DDL 기준으로 옮긴다.
   - 1: 이관 도구와 그 문서를 지운다.
   - 2: 레거시 스키마·픽스처를 지우고 기준선 숫자를 고친다.

## 이 step의 목적

옛 `.sqlite` 파일을 PostgreSQL로 옮기던 이관 도구와 그 테스트·진입점·문서를 지운다. 이관 도구는 `genviewer-import-sqlite`(`src/genviewer/scripts/import_sqlite.py`)다.
레거시 스키마(`service/schema.py` 의 SQLite DDL)와 픽스처 `db/init.sqlite` 는 step 2가 지운다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/README.md`, `/docs/ADR.md`, `/docs/ARCHITECTURE.md`, `/docs/PRD.md`, `/docs/notes/known-issues.md`
- `src/genviewer/scripts/import_sqlite.py` — 지울 파일. 무엇을 import하는지 본다(`survive_console_encoding`, `schema`, `current_user`).
- `src/genviewer/scripts/__init__.py` — docstring의 사용 예, `survive_console_encoding`. 이 함수는 `cli.py`·`scripts/init_db.py` 도 쓰므로 남긴다.
- `tests/test_import_sqlite.py` — 지울 파일. 6개 중 1개는 DB 없이 돌고, 5개는 DB 테스트다.
- `pyproject.toml` `[project.scripts]`
- `src/genviewer/scripts/init_db.py` — `--dsn` 기본값(`GENDB_PG_DSN`, ~248)과 DSN이 없을 때의 오류(~273). README로 옮길 문장의 근거다.
- `tools/deploy.sh` 는 읽기만 한다.
  - ~133-139: 지난 배포가 만든 런처를 표시(marker)로 찾아 지운다.
  - ~207-212: `DEPLOY_LINK_DIR` 의 옛 링크를 정리한다.
- 이전 step에서 수정된 파일: `tests/test_schema.py`

## 작업

### 1. 코드

- `git rm src/genviewer/scripts/import_sqlite.py tests/test_import_sqlite.py`
- `pyproject.toml`: `genviewer-import-sqlite = "genviewer.scripts.import_sqlite:main"` 줄을 지운다.
- `uv sync` 로 venv에 남은 옛 실행 파일을 정리한다. 진입점은 `uv.lock` 에 들어 있지 않으므로 `uv lock --check` 가 그대로 통과해야 한다.
- `src/genviewer/scripts/__init__.py`: docstring의 `python -m genviewer.scripts.import_sqlite --sqlite mine.sqlite --dry-run` 줄만 지운다. 이 파일은 Python 3.9에서 import되어야 한다(CLAUDE.md). AC의 `ast.parse` 로 확인한다.

### 2. 문서

- `README.md`
  - '배포' 절: "`[project.scripts]` 에 있는 명령이 전부 나온다(`genviewer`, `genviewer-init-db`, `genviewer-import-sqlite`)." 에서 `genviewer-import-sqlite` 를 뺀다.
  - "## 기존 .sqlite 파일 옮기기" 절(~357-381, 다음 "## 동시 편집" 앞까지)을 통째로 지운다.
    - 단, 이 절에만 있는 init-db 사실이 하나 있다. "`genviewer-init-db` 도 `genviewer.env` 를 읽지 않는다(그쪽은 `--dry-run` 만 DSN 없이 된다)".
    - 이 문장을 '개발 클러스터 (한 번만)' 절에서 `uv run genviewer-init-db …` 코드 블록 바로 뒤로 옮긴다. 예: "`genviewer-init-db` 는 `genviewer.env` 를 읽지 않는다. `--dsn` 이나 `GENDB_PG_DSN` 이 있어야 하고, `--dry-run` 만 DSN 없이 된다."
    - 옮기기 전에 `scripts/init_db.py` 와 맞는지 확인한다. 다르면 코드대로 적고 summary에 적는다.
  - '개발' 절 트리: `scripts/       관리 도구 (init_db, import_sqlite)` → `scripts/       관리 도구 (init_db)`
- `CLAUDE.md` "개발 프로세스": "`src/genviewer/scripts/` 는 관리 도구(init_db, import_sqlite)다" → "관리 도구(init_db)다". 기준선 숫자는 step 2가 고친다.
- `docs/ARCHITECTURE.md` 트리: `init_db(스키마·role·권한), import_sqlite(.sqlite 이관)` → `init_db(스키마·role·권한)`
- `docs/ADR.md`
  - ADR-005 트레이드오프: "`psql` 로 직접 고친 것과 `import_sqlite` 가 쓴 것은 남지 않는다." → "`psql` 로 직접 고친 것은 남지 않는다."
  - ADR-012 결정: "관리 도구(`init_db`, `import_sqlite`)는 argparse." → "관리 도구(`init_db`)는 argparse."
- `docs/PRD.md` "8. **운영 도구**": "`genviewer-import-sqlite`(옛 `.sqlite` 이관), " 를 지운다.
- `docs/notes/known-issues.md`: K4(`import_sqlite --on-conflict merge` …)와 K11(`import_sqlite` 가 `?`·`#`·`%` …) 행을 지운다.

## Acceptance Criteria

```bash
uv run ruff check src tests                  # 린트 통과
uv run pytest -q                             # 전체 통과 (DSN 이 있으면 -rs 로 DB 테스트가 돌았는지 본다)
uv lock --check                              # lock 이 그대로다
uv run python -c "import ast; ast.parse(open('src/genviewer/scripts/__init__.py', encoding='utf-8').read(), feature_version=(3, 9))"
uv run genviewer-init-db --dry-run           # 관리 도구가 그대로 돈다
git grep -n -e import_sqlite -e import-sqlite -- . ':!phases'   # 아무것도 안 나와야 한다 (찾은 것이 없으면 git grep 은 exit 1)
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `scripts/` 가 여전히 PySide6를 import하지 않는가?
   - `tools/deploy.sh` 가 그대로인가(`git diff --stat -- tools` 비어 있음)?
   - 공통 4번의 역사 설명 문장이 남아 있는가?
   - known-issues의 다른 번호가 그대로인가?
3. 결과에 따라 `phases/5-sqlite-removal/index.json` 의 step 1을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "import_sqlite 도구·테스트·진입점 삭제. README(배포 명령 목록, 이관 절 삭제 → init-db 문장을 개발 클러스터 절로 옮김, 트리)·CLAUDE.md·ARCHITECTURE·ADR-005/012·PRD·known-issues K4/K11 정리. DB 테스트: <N passed | 안 돎(DSN 없음)>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요(예: `uv lock --check` 가 실패해 lock을 다시 만들어야 함) → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `tools/deploy.sh` 를 고치지 마라. 이유: 다음 배포 때 표시가 있는 옛 런처(`<ROOT>/bin/genviewer-import-sqlite`)와 그 링크를 deploy.sh가 스스로 지운다(~133-139, ~207-212).
- `service/schema.py`, `tests/test_schema.py`, `db/init.sqlite`, `.gitignore` 를 건드리지 마라. 이유: step 2의 일이다.
- `survive_console_encoding` 을 지우거나 그 docstring 문구를 바꾸지 마라. 이유: `cli.py`·`scripts/init_db.py` 가 쓴다. 이 phase는 지우기만 한다.
- known-issues 번호를 다시 매기지 마라. 이유: phase 파일과 README가 K3·K14·K17 같은 번호로 가리킨다.
- `uv lock` 으로 lock을 다시 만들지 마라. 이유: 진입점 삭제로는 lock이 바뀌지 않아야 한다. 바뀐다면 다른 원인이므로 멈추고 알린다.
- 공통 4번의 역사 설명 문장을 지우지 마라.
- 기존 테스트를 깨뜨리지 마라.
