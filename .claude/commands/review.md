이 프로젝트의 변경 사항을 리뷰하라.

먼저 다음 문서들을 읽어라:
- `/CLAUDE.md`
- `/docs/ARCHITECTURE.md`
- `/docs/ADR.md`

그런 다음 변경 범위를 확인한다. phase 브랜치(`feat-<phase>`)면 `git diff main...HEAD`, 작업 중이면 `git diff HEAD` 와 untracked 파일이다. 아래 체크리스트로 검증하라.

## 체크리스트

1. **아키텍처 준수**
   - ARCHITECTURE.md 디렉토리 구조와 레이어 표를 따르는가? 새 모듈을 추가했다면 트리를 갱신했는가?
   - Qt 금지 구역(`service/`, `scripts/`, `config/`, `utils/logs.py`, `utils/user.py`, `utils/exporter.py`, `cli.py` 의 모듈 수준)에 PySide6 import가 들어오지 않았는가? `cli.py` 는 GUI를 `run_gui` 안에서만 lazy import한다.
   - `scripts/init_db.py` 에서 닿는 모듈(`service/schema.py`, `config/config.py` 등)이 Python 3.9에서 import되는가? 런타임에 평가되는 `X | Y`, `match`, `zip(strict=)`, `dataclass(slots=/kw_only=)`, `tomllib` 가 들어오지 않았는가?
   - ARCHITECTURE "현재 어긋난 곳"(view private 멤버 접근, dialog의 서비스 직접 호출)을 새 코드가 따라 하지 않았는가?
   - 문서가 따라왔는가? 사용자에게 보이는 동작은 README에, 결정은 ADR에, 고친 알려진 문제는 `docs/notes/known-issues.md` 에서 지웠는가?
2. **기술 스택 준수**: ADR에 정의된 기술 선택을 벗어나지 않았는가? 런타임 의존성이나 `uv.lock` 을 바꿨다면 RHEL 8(glibc 2.28)용 `manylinux_2_28` 이하 휠이 있는가(`uv pip compile pyproject.toml --python-version 3.13 --python-platform x86_64-manylinux_2_28`)? PySide6는 6.9.3 고정이다(6.10+ 는 manylinux_2_34).
3. **테스트 존재**
   - 고친 버그마다 수정 전에 실패하던 테스트가 있는가? 수정을 되돌리는 변이로 확인한다. summary의 "RED 확인"도 주장이다. phase 브랜치면 step 커밋의 `src` 변경만 되돌려(`git diff <c>^ <c> -- src > p; git apply -R p`) 그 step의 새 테스트가 summary에 적힌 수만큼 실패하는지 보고 `git checkout -- src` 로 되돌린다(작업 트리가 깨끗할 때만). 테스트 지원 코드가 패치하는 import(예: `QUESTION_MODULES` 의 `question`)까지 사라지면 단언 실패 대신 fixture error가 나므로 그 import는 남기고 다시 본다.
   - RED가 Windows 개발 PC에서 도는 테스트인가? `posix_only` 테스트만 있으면 개발 PC에서는 skip이라 증명이 안 된다.
   - 테스트가 이름·주석에 적은 성질을 실제로 검사하는가(같은 입력을 두 번 넣고 비교하는 형식적 테스트 금지)?
   - 저장 경로: 성공, 충돌(`stale`/`deleted`) × Reload/Overwrite/Cancel, 예외마다 dirty·baseline·version·알림이 맞는가? 저장 함수가 실패를 성공처럼 알리지 않는가("Saved" 문구)? 취소 뒤 이전 상태로 되돌리는 경로는 되돌릴 대상(이전 process·device)이 지워졌을 때도 콤보·표·탭이 같은 대상을 가리키는가?
   - GUI 비동기: `run_blocking`/`Task` 콜백의 실패 경로, 재접속·창 닫기 중 경로가 테스트되는가? "아무 일도 없음"을 `qtbot.wait` 고정 대기로 단언하지 않는가?
   - 셸 스크립트 변경은 stub으로 실제 실행하는 테스트(`tests/test_deploy_sh.py` 방식)가 지키는가? 텍스트 토큰 검사만 있으면 동작을 바꾸는 변이로 확인한다.
   - `repo/`·schema SQL 변경은 DB 테스트가 `GENDB_TEST_PG_DSN` 으로 실제로 돌았는가(skip 아님)?
4. **CRITICAL 규칙**: CLAUDE.md의 CRITICAL 규칙과 아래 항목을 위반하지 않았는가?
   - 쓰기 경로가 `device.version` 낙관적 잠금과 `change_log` 기록을 같은 트랜잭션에서 하는가? 화면에 들고 있지 않은 device를 지우지 않는가?
   - 비밀번호가 화면·로그·argv에 남지 않는가? 예외는 `str(exc)` 대신 `user_message()`, 로그 패널·로그 파일로 가는 DSN은 `scrub()`.
   - SQL 식별자는 `psycopg.sql` 과 `schema.TABLE_COLUMNS` 로만 조립하는가? PG 10~15에서 도는 문법인가?
   - 텍스트 I/O에 `encoding="utf-8"` 이 있는가?
   - 셸 스크립트는 LF와 실행 비트로 커밋되는가(`.gitattributes`, `git update-index --chmod=+x`)?
   - 버그 수정 범위를 넘는 리팩터·문구 변경·기능 추가가 없는가?
5. **빌드 가능**: 아래 명령이 모두 통과하는가?
   ```bash
   uv run ruff check src tests && uv run pytest -q
   ```

## 출력 형식

| 항목 | 결과 | 비고 |
|------|------|------|
| 아키텍처 준수 | ✅/❌ | {상세} |
| 기술 스택 준수 | ✅/❌ | {상세} |
| 테스트 존재 | ✅/❌ | {상세} |
| CRITICAL 규칙 | ✅/❌ | {상세} |
| 빌드 가능 | ✅/❌ | {상세} |

위반 사항이 있으면 수정 방안을 구체적으로 제시하라.
