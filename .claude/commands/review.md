이 프로젝트의 변경 사항을 리뷰하라.

먼저 다음 문서들을 읽어라:
- `/CLAUDE.md`
- `/docs/ARCHITECTURE.md`
- `/docs/ADR.md`

그런 다음 변경 범위를 확인한다. phase 브랜치(`feat-<phase>`)면 `git diff main...HEAD`, 작업 중이면 `git diff HEAD` 와 untracked 파일이다. 아래 체크리스트로 검증하라.

## 체크리스트

1. **아키텍처 준수**
   - ARCHITECTURE.md 디렉토리 구조와 레이어 표를 따르는가? 새 모듈을 추가했다면 트리를 갱신했는가?
   - Qt 금지 구역(`service/`, `scripts/`, `config/`, `utils/logs.py`, `utils/user.py`, `utils/exporter.py`, `cli.py` 의 모듈 수준)에 PySide6 import가 들어오지 않았는가? `cli.py` 는 GUI를 typer 콜백 `root` 안에서만 lazy import한다. `tests/test_boundaries.py` 가 이것을 지킨다. 새 Qt 없는 `utils/` 파일이면 그 테스트의 `QT_FREE_MODULES` 에 더했는가?
   - `scripts/init_db.py` 에서 닿는 모듈(`service/schema.py`, `config/config.py` 등)이 Python 3.9에서 import되는가? 런타임에 평가되는 `X | Y`, `match`, `zip(strict=)`, `dataclass(slots=/kw_only=)`, `tomllib` 가 들어오지 않았는가? `tests/test_py39_compat.py` 가 정적으로 지킨다(서드파티 API 차이는 못 본다).
   - 가드 테스트(`tests/test_boundaries.py`, `tests/test_py39_compat.py`, `tests/fixtures/imports.py`)를 고쳐서 통과시키지 않았는가? 금지 목록에서 모듈을 빼거나 예외를 늘렸으면 사용자 승인이 있어야 한다.
   - ARCHITECTURE "현재 어긋난 곳"(view private 멤버 접근, dialog의 서비스 직접 호출)을 새 코드가 따라 하지 않았는가?
   - 문서가 따라왔는가? 사용자에게 보이는 동작은 README에, 결정은 ADR에, 고친 알려진 문제는 `docs/notes/known-issues.md` 에서 지웠는가?
2. **기술 스택 준수**: ADR에 정의된 기술 선택을 벗어나지 않았는가? 런타임 의존성이나 `uv.lock` 을 바꿨다면 RHEL 8(glibc 2.28)용 `manylinux_2_28` 이하 휠이 있는가(`uv pip compile pyproject.toml --python-version 3.13 --python-platform x86_64-manylinux_2_28`)? PySide6는 6.9.3 고정이다(6.10+ 는 manylinux_2_34).
3. **테스트 존재**
   - 고친 버그마다 수정 전에 실패하던 테스트가 있는가? 수정을 되돌리는 변이로 확인한다. summary의 "RED 확인"도 주장이다. phase 브랜치면 step 커밋의 `src` 변경만 되돌려(`git diff <c>^ <c> -- src > p; git apply -R p`) 그 step의 새 테스트가 summary에 적힌 수만큼 실패하는지 보고 `git checkout -- src` 로 되돌린다(작업 트리가 깨끗할 때만). `service/repo/` 의 의미를 바꾼 step은 가짜(`tests/gui_support/fakes.py`)도 같이 되돌린다(`-- src tests/gui_support`). `src` 만 되돌리면 contract test의 `[fake]` 쪽은 바뀐 가짜로 돌아 RED가 되지 않는다(phase 18 step 1). 테스트 지원 코드가 패치하는 import(예: `QUESTION_MODULES` 의 `question`)까지 사라지면 단언 실패 대신 fixture error가 나므로 그 import는 남기고 다시 본다. step이 새로 만든 이름을 테스트나 지원 코드가 import하면(phase 10의 `conflict.can_overwrite`, `device_table._filtered_orders`) 통째로 되돌렸을 때 수집 오류로 끝난다. 그 이름은 남기고 동작만 되돌린다(예: 늘 True를 내는 stub, 분기 조건을 `False` 로). step이 `git rm` 한 파일은 `git apply -R` 이 untracked로 되살린다. `git checkout -- src` 로는 지워지지 않고 `git clean -f` 는 훅이 막으므로 Python(`pathlib.Path.unlink`)으로 지운다. 되돌린 옛 코드가 실행 중인 스레드를 놓쳐 pytest 프로세스를 통째로 죽일 수 있으면(phase 13의 QThread 워커, `0xC0000409`) 테스트를 하나씩 따로(`pytest <nodeid>` 를 테스트마다) 돌려 실패·멈춤·크래시를 센다.
   - 승인된 정리(삭제) phase는 고친 버그가 없다. 지운 코드를 지키던 성질을 이제 누가 지키는지 보고, 남거나 옮긴 검사가 step이 보지 않은 변이에도 실패하는지 직접 본다(phase 5: 컬럼 순서·이름을 바꾸는 변이).
   - RED가 Windows 개발 PC에서 도는 테스트인가? `posix_only` 테스트만 있으면 개발 PC에서는 skip이라 증명이 안 된다.
   - 테스트가 이름·주석에 적은 성질을 실제로 검사하는가(같은 입력을 두 번 넣고 비교하는 형식적 테스트 금지)?
   - 색·테마를 바꾼 step은 모델·팔레트 값 단언이 실제로 그려지는 색과 같은지 한 번 확인한다. offscreen에서 `apply_theme` 뒤 `view.viewport().grab().toImage()` 의 셀 안 픽셀 중 배경과 대비가 가장 큰 색을 재서, 고치기 전과 뒤를 비교한다. 이유: 테스트는 "역할이 None이면 QSS `color`" 같은 가정 위에서 대비를 계산한다(phase 22 리뷰에서 이 방법으로 가정을 확인했다).
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
