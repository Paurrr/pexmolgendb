# Step 0: qt-free-boundaries

## 배경 (phase 6 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 6은 예외다. 구조 제안 P1(`docs/notes/architecture-proposal.md`, 경계 가드 테스트)을 **사용자가 2026-10-17 승인**했다.
CLAUDE.md의 CRITICAL 경계 규칙(Qt 금지 구역, init_db의 Python 3.9 호환)은 지금 주석과 리뷰로만 지켜진다. 이 phase는 그 규칙을 **테스트가** 지키게 한다. 테스트만 더한다. `src/` 는 바꾸지 않는다.

모든 step에 같은 규칙이 적용된다.
1. 버그 수정이 아니므로 RED 재현은 없다. 대신 새 검사가 **실제로 실패할 수 있는지** 확인한다. `src/` 를 손으로 망가뜨려 실패를 본다(변이 검사). 그리고 손으로 되돌린다. `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
2. 지금 코드는 규칙을 지키고 있다(2026-10-17 확인). 새 테스트는 처음부터 통과해야 한다. 통과하지 않으면 테스트가 틀렸거나 진짜 위반을 찾은 것이다.
   - 진짜 위반이면 `src/` 를 고치지 않는다. 그 위반을 summary에 적고 `"status": "blocked"` 로 멈춘다. 이유: 이 phase의 승인 범위는 테스트 추가뿐이다.
3. PostgreSQL을 쓰지 않는다. 하네스 규칙 12(DB 테스트 필수)는 해당하지 않는다.
4. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.
5. step 순서는 다음과 같다.
   - 0: Qt 금지 구역과 레이어 import 가드(이 step)
   - 1: init_db 에서 닿는 모듈의 Python 3.9 호환 가드

## 이 step의 목적

`tests/test_boundaries.py` 가 아래 네 가지를 지키게 한다.
- ① Qt 금지 구역(티어 0~2)은 PySide6도, Qt 쪽 genviewer 모듈도 import하지 않는다. 정적 스캔으로 본다. 함수 안의 import도 본다.
- ② 같은 모듈들을 새 인터프리터에서 전부 import해도 `sys.modules` 에 PySide6가 올라오지 않는다(전이 검사).
- ③ `models/` 는 `views/`·`controllers/` 를 모른다.
- ④ `net/` 은 자기 안에서 닫혀 있다.

형제 저장소 pexqa의 형태(`tests/fixtures/imports.py` + `tests/test_boundaries.py`)를 따른다.

## 읽어야 할 파일

- `/CLAUDE.md`(아키텍처 규칙의 첫 CRITICAL), `/docs/ARCHITECTURE.md`
  - "레이어 (위 → 아래로만 import)" 표(~60-71)와 그 아래 두 줄을 읽는다.
  - 둘째 줄이 "강제: 아직 자동 가드 테스트가 없다 …" 다(~71).
- pexqa(하우스 기준, 이 저장소 밖):
  - `../pexqa/tests/fixtures/imports.py`: `imported_names`, `package_dir`, `package_imports`, `package_sources`
  - `../pexqa/tests/test_boundaries.py`: `forbidden_imports`, 스캐너 자체 테스트, `RUNTIME_SCRIPT` 서브프로세스 검사
  - 저장소 밖 경로라 읽기만 한다. 없으면 이 파일의 설명으로 충분하다.
- `tests/test_cli.py` 의 `test_importing_the_cli_does_not_load_qt`(~72-78)
  - 지금 있는 유일한 Qt 가드다. `genviewer.cli` 하나만 서브프로세스로 본다. 이 테스트는 그대로 둔다.
- `tests/gui/test_dialogs_fixture.py` 의 `_module_name`, `_resolve`, `_bindings`(~323-350)
  - 이 저장소에 이미 있는 AST import 스캐너다(상대 import 해석 방식 참고). 이 파일은 바꾸지 않는다.
- `pyproject.toml` 의 `[tool.pytest.ini_options]`: `pythonpath = ["tests"]` 다. 그래서 헬퍼는 `from fixtures.imports import ...` 로 import된다.
- 검사 대상 모듈(2026-10-17)
  - 티어 0: `src/genviewer/config/`(`__init__.py`, `config.py`), `utils/user.py`, `utils/logs.py`, `utils/validators.py`, `utils/lisp.py`
  - 티어 1: `service/` 전체(`repo/` 포함), `scripts/` 전체
  - 티어 2: `cli.py`, `utils/exporter.py`
  - 패키지 `__init__`: `genviewer/__init__.py`, `utils/__init__.py`, `service/__init__.py`, `service/repo/__init__.py`, `scripts/__init__.py`
  - `__main__.py` 도 대상이다. `from genviewer.cli import main` 만 있다.
- `src/genviewer/cli.py`
  - typer 콜백 `root`(~77-118) 안에 `from genviewer.main import run_gui`(~116)가 있다.
  - Qt로 가는 유일한 허용 경로다. 모듈 수준이 아니라 **함수 `root` 안**이다.
  - 계획 문서에는 "run_gui 안" 이라 적혀 있었다. 실제로는 `root` 안이고, 이 파일이 맞다.
- `src/genviewer/utils/exporter.py`: `write_xlsx` 안에서 `openpyxl` 을 함수 안 import 한다(~26). 허용된다(Qt가 아니다).
- `src/genviewer/models/*.py`: genviewer에서는 `genviewer.utils.validators` 만 import한다(`device_table.py:4`, `generic_table.py:5`).
- `src/genviewer/net/*.py`: genviewer에서는 `genviewer.net.*` 만 import한다(`controller.py:5-6`, `workers.py:7`).

## 작업

### 1. 헬퍼 (`tests/fixtures/__init__.py`, `tests/fixtures/imports.py`)

- pexqa의 `imports.py` 를 옮겨 온다. 독스트링·주석은 한국어로 둔다.
  - `imported_names(source, module, *, is_package=False) -> list[str]`: `import X` → `X`, `from X import y` → `X` 와 `X.y`. 상대 import는 `importlib.util.resolve_name` 으로 절대 이름으로 푼다.
  - `package_dir(package) -> Path`, `package_imports(package) -> Iterator[tuple[Path, str]]`, `package_sources(package)`
- cli.py 예외를 정확히 표현하려면 import가 **어느 함수 안에 있는지** 알아야 한다.
  - 그래서 위치를 함께 주는 함수를 하나 더 둔다. 예: `scoped_imports(source, module, *, is_package=False) -> list[tuple[str, str | None]]`, 즉 `(import 이름, 감싼 함수 이름 또는 None=모듈 수준)`
  - 이름은 재량이다.
  - 클래스 본문의 import는 모듈 수준과 같이 본다(import 시점에 실행된다).
- 이름 충돌을 확인한다. `pythonpath = ["tests"]` 라서 `tests/fixtures/` 가 최상위 패키지 `fixtures` 가 된다.
  - 같은 이름의 설치된 패키지나 기존 `conftest` fixture 이름과 겹치지 않는지 본다(`uv run python -c "import fixtures"` 는 tests 밖에서 실패해야 정상이다).
  - 겹치면 이름을 바꾸고 summary에 적는다.
- `tests/gui_support/` 에 두지 않는다. 이유: 그 패키지는 GUI 테스트 헬퍼 자리다(CLAUDE.md 테스트 관례). 이 헬퍼는 Qt 없이 돈다.

### 2. 테스트 (`tests/test_boundaries.py`, 새 파일)

- 모듈 docstring에 무엇을 지키는지와 이유(CLAUDE.md CRITICAL, `status` 는 X가 없는 서버에서 돈다)를 적는다.

- **Qt 금지 구역 목록은 한 곳에 상수로 둔다.**
  - ARCHITECTURE 레이어 표의 티어 0~2, 그 안의 패키지 `__init__`, `__main__.py` 다.
  - `service`, `scripts`, `config` 는 패키지 단위(하위 전부)로 적는다. 그래야 새 모듈이 자동으로 들어온다.
  - utils는 파일 단위로 적는다.
- **금지 대상**
  - 최상위 `PySide6`, `shiboken6`
  - genviewer의 Qt 쪽 모듈: `genviewer.main`, `genviewer.models`, `genviewer.views`, `genviewer.controllers`, `genviewer.dialogs`, `genviewer.delegates`, `genviewer.net`
  - Qt utils: `genviewer.utils.background`, `dialogs`, `file_dialogs`, `menus`, `palette`, `table_utils`, `reporting`
  - 티어 3을 import하면 Qt가 따라오거나 레이어가 거꾸로 선다.
  - 이 목록도 상수로 두고, 각 항목 옆에 ARCHITECTURE 티어를 주석으로 단다.
- **허용 예외는 하나뿐이다**: `genviewer/cli.py` 의 함수 `root` 안에서 `genviewer.main`(과 `genviewer.main.run_gui`).
  - 같은 import가 모듈 수준이거나 다른 함수에 있으면 위반이다.

테스트(이름은 재량, 성질은 아래와 같다):

- **스캐너 자체 테스트**(pexqa처럼 parametrize). 아래를 잡아야 한다.
  - `import PySide6`, `from PySide6.QtCore import Qt`, `import shiboken6`
  - `from genviewer.views import x`, `from genviewer import controllers`
  - 상대 import `from ..views import x`(모듈 `genviewer.service.foo` 기준)
  - 함수 안의 `from PySide6.QtWidgets import QApplication`
  - 아래는 잡지 않아야 한다.
    - 주석·문자열 속 `PySide6`
    - `import logging`
    - `from genviewer.service import schema`
  - 패키지 `__init__` 에서의 상대 import 해석(`from .. import views` 는 `genviewer.views` 다)도 확인한다.
- **정적 검사**: Qt 금지 구역의 모든 `.py` 에 금지 import가 없다(cli.py `root` 예외만 허용).
  - 실패 메시지에 `파일: import 이름 (함수 이름|모듈 수준)` 을 줄마다 찍는다.
- **전이 검사**(새 인터프리터, `subprocess.run([sys.executable, "-c", SCRIPT], …, encoding="utf-8")`).
  - 금지 구역의 모듈을 전부 import한다. 패키지는 `pkgutil.walk_packages(..., onerror=raise)` 로 돌고, 파일 단위 utils는 이름으로 import한다.
  - 그 뒤 `sys.modules` 에 위 금지 목록이 없는지 본다.
  - 서브프로세스인 이유를 주석에 적는다: pytest-qt가 이 프로세스에 PySide6를 이미 올렸다.
  - `genviewer.__main__` 은 import해도 된다(`if __name__ == "__main__"` 가드가 있다). 확인하고 넣는다.
  - `env` 에 `PYTHONIOENCODING=utf-8` 을 넣는다(cp949 콘솔).
- **models 레이어**: `src/genviewer/models/` 의 genviewer import는 `genviewer.models.*` 와 `genviewer.utils.validators` 뿐이다(ARCHITECTURE: "models는 `utils.validators` 만 안다").
- **net 레이어**: `src/genviewer/net/` 의 genviewer import는 `genviewer.net.*` 뿐이다("`net/` 은 자기 안에서 닫혀 있다").
  - phase 13이 `net/` 을 QTcpSocket으로 다시 쓰더라도 이 규칙은 그대로다.
- 기대값(금지 구역 목록)을 ARCHITECTURE 표에서 손으로 옮겨 적는다. `src/` 를 스캔해 "Qt를 안 쓰는 모듈" 을 자동으로 골라 금지 구역으로 삼지 마라. 이유: 위반한 모듈은 자동으로 목록에서 빠져서 검사가 아무것도 지키지 않는다.

### 3. 변이 검사

아래를 하나씩 손으로 넣고, `uv run pytest tests/test_boundaries.py -q` 에서 **해당 테스트가 실패하는지** 본다. 손으로 되돌린 뒤 통과를 확인한다. 실패한 테스트 이름과 단언 메시지 한 줄을 summary에 적는다.

| 변이 | 실패해야 하는 테스트 |
|---|---|
| `src/genviewer/service/errors.py` 맨 위에 `import PySide6` | 정적 검사, 전이 검사 |
| `src/genviewer/utils/exporter.py` 의 `write_csv` 안에 `from PySide6.QtWidgets import QApplication` | 정적 검사(전이 검사는 함수가 안 불려서 못 잡는다. 정적 검사가 함수 안 import를 보는 이유다) |
| `src/genviewer/cli.py` 모듈 수준에 `import genviewer.main` | 정적 검사, 전이 검사(그리고 기존 `test_importing_the_cli_does_not_load_qt`) |
| `src/genviewer/models/device_state.py` 에 `from genviewer.views import device_tab` | models 레이어 |
| `src/genviewer/net/client.py` 에 `from genviewer.utils import logs` | net 레이어 |

- 변이 검사 뒤 `git diff --stat -- src` 가 비어 있어야 한다.

### 4. 문서

- `docs/ARCHITECTURE.md` 레이어 절의 "강제:" 줄(~71)을 Qt 부분만 고친다.
  - 예: "강제: `tests/test_boundaries.py` 가 Qt 금지 구역(정적 스캔 + 새 인터프리터 import), models·net 의 import 범위를 지킨다. Python 3.9 호환은 아직 리뷰(`/review`)로 지킨다."
  - 3.9 문장은 step 1이 고친다.
- 트리(~52 `tests/`)에 `fixtures/` 한 줄을 더한다(예: "`fixtures/` # Qt 없는 테스트 헬퍼: import 스캐너").

## Acceptance Criteria

```bash
uv run pytest tests/test_boundaries.py -q    # 새 테스트 통과 (skip 없음)
uv run pytest tests/test_cli.py -q           # 기존 Qt 가드 그대로 통과
uv run ruff check src tests                  # 린트 통과 (tests/fixtures 포함)
uv run pytest -q                             # 전체 통과
git diff --stat -- src                       # 비어 있어야 한다 (변이 검사 뒤 되돌렸다)
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `src/` 가 바뀌지 않았는가?
   - 금지 구역 목록이 ARCHITECTURE 레이어 표(티어 0~2)와 CLAUDE.md CRITICAL 목록(`service/`, `scripts/`, `config/`, `utils/logs.py`, `utils/user.py`, `utils/exporter.py`, `cli.py`)을 모두 덮는가?
   - 새 테스트가 개발 PC(Windows)에서 실제로 도는가(skip이 아닌가)?
3. 결과에 따라 `phases/6-boundary-guards/index.json` 의 step 0을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "tests/fixtures/imports.py(pexqa 스캐너 + 함수 위치) + tests/test_boundaries.py: Qt 금지 구역 정적(함수 안 포함, cli.py root 의 genviewer.main 만 허용)·서브프로세스 전이, models→utils.validators 만, net 닫힘. src 불변. 변이: service/errors import PySide6 → <테스트: 단언>, exporter 함수 안 PySide6 → <…>, cli 모듈 수준 genviewer.main → <…>, models→views → <…>, net→utils → <…>. 전체 <N passed / M skipped / 1 xfailed>"`
   - 지금 코드가 규칙을 어긴 것을 찾음 → `"status": "blocked"`, `"blocked_reason": "<파일: import> 가 Qt 금지 구역 규칙을 어긴다. src 수정은 승인 범위 밖"` 후 즉시 중단
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`

## 금지사항

- `src/` 를 바꾸지 마라(변이 검사는 되돌린다). 이유: 이 phase의 승인 범위는 테스트 추가뿐이다.
- 금지 구역 목록을 `src/` 스캔으로 자동 계산하지 마라. 이유: 위반한 모듈이 목록에서 저절로 빠진다.
- 정적 검사를 모듈 수준 import로만 좁히지 마라. 이유: 함수 안 import는 서브프로세스 검사가 못 잡는다(그 함수를 부르지 않으므로).
- `import-linter` 같은 새 의존성을 더하지 마라. 이유: 하우스 방식(pexqa 스캐너)을 따른다(제안 문서 레퍼런스 3). `uv.lock` 이 바뀌면 안 된다.
- `tests/test_cli.py::test_importing_the_cli_does_not_load_qt` 와 `tests/gui/test_dialogs_fixture.py` 의 스캐너를 지우거나 새 헬퍼로 옮기지 마라. 이유: 리팩터는 범위 밖이다.
- 전이 검사를 이 pytest 프로세스 안에서 `sys.modules` 로 하지 마라. 이유: pytest-qt가 PySide6를 이미 올려 두어 항상 실패하거나, 지우면 다른 테스트가 깨진다.
- 기존 테스트를 깨뜨리지 마라.
