# Step 1: py39-compat

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
   - 0: Qt 금지 구역과 레이어 import 가드(`tests/test_boundaries.py`, `tests/fixtures/imports.py`)
   - 1: init_db 에서 닿는 모듈의 Python 3.9 호환 가드(이 step)

## 이 step의 목적

RHEL 7 서버는 Python 3.9로 `PYTHONPATH=src python3.9 -m genviewer.scripts.init_db` 를 돌린다(ADR-014, README '서버' 절).
그래서 init_db가 닿는 모듈은 3.10+ 문법과 이름을 쓰면 안 된다. 지금은 리뷰로만 지키고, 어기면 서버에서야 드러난다.
`tests/test_py39_compat.py` 가 이 모듈들을 **접속 없이, 3.9 인터프리터 없이** 정적으로 검사하게 한다.

## 읽어야 할 파일

- `/CLAUDE.md`(아키텍처 규칙의 두 번째 CRITICAL: 런타임에 평가되는 `X | Y`, `match`, `zip(strict=)`, `dataclass(slots=/kw_only=)`, `tomllib` 금지, `from __future__ import annotations` 아래의 주석은 괜찮다)
- `/docs/ADR.md` ADR-014(트레이드오프의 "이 호환을 지키는 자동 테스트가 아직 없다(리뷰로 지킨다)")
- `/docs/ARCHITECTURE.md` 레이어 절의 "강제:" 줄(~71, step 0이 Qt 부분을 고쳤다)
- `/README.md` '서버' 절의 "이 3.9 호환을 지키는 자동 테스트는 아직 없다. …" 문단(~615-617)
- step 0이 만든 `tests/fixtures/imports.py`(`imported_names`, 위치를 주는 스캔 함수), `tests/test_boundaries.py`. 같은 일을 하는 함수를 새로 만들지 말고 가져다 쓴다.
- `src/genviewer/scripts/init_db.py`
  - `from __future__ import annotations` 가 있다(~28). 그래서 `tuple | None`(~45-46) 같은 주석은 괜찮다.
  - 모듈 수준 import는 `genviewer.scripts`, `genviewer.service.schema`(~36-37)다.
  - 함수 안 import는 `psycopg.sql`, `psycopg`(~201, ~210)다.
- `src/genviewer/scripts/__init__.py`: `sys` 만 import한다.
- `src/genviewer/service/schema.py`
  - **`from __future__ import annotations` 가 없다.** 그래서 `def child_tables() -> dict[str, list[str]]`(~19)의 주석이 런타임에 평가된다(3.9에서도 `dict[...]` 는 된다).
  - `genviewer.config.config`(~12), `psycopg.sql`(~47)을 import한다.
- `src/genviewer/config/config.py`: `json`, `pathlib` 만 import한다.
- 2026-10-17 기준으로 닿는 genviewer 모듈은 일곱 개다.
  - `genviewer`, `genviewer.scripts`, `genviewer.scripts.init_db`, `genviewer.service`, `genviewer.service.schema`, `genviewer.config`, `genviewer.config.config`
  - 패키지 `__init__` 은 import할 때 실행되므로 포함한다.

## 작업

### 1. 닿는 모듈 계산

- `genviewer.scripts.init_db` 에서 출발한다. import를 따라간다(모듈 수준과 **함수 안** 둘 다).
  - `genviewer.` 로 시작하는 이름을 모듈 파일로 푼다. `from X import y` 에서 `X.y` 가 모듈이면 그것, 아니면 `X` 다.
  - 그 모듈들의 부모 패키지 `__init__` 까지 모은다.
  - 재귀로 닫힐 때까지 반복한다. step 0의 스캐너를 쓴다.
- 손으로 쓴 목록과 비교하지 않는다. 다만 위 일곱 개가 모두 들어 있는지 **하한**으로 단언한다. 그래야 계산이 망가져 빈 집합이 되면 잡힌다.
  - 실패 메시지에 계산된 집합을 찍는다.
- 서드파티(psycopg 등)는 검사하지 않는다. 서버의 psycopg는 3.2.x이고, 그 API 차이는 이 검사의 범위 밖이다(문서에 그렇게 적는다).

### 2. 검사 (`tests/test_py39_compat.py`, 새 파일)

모듈마다 아래를 본다. 위반은 `파일:행: 이유` 로 모아 한 번에 단언한다.

**문법**: `ast.parse(source, feature_version=(3, 9))`.
- 2026-10-17에 Python 3.13에서 확인한 결과는 아래와 같다.
  - 잡는 것: `match`, `except*`, 타입 매개변수(`def f[T]`), `type X = …`
  - 못 잡는 것: 같은 따옴표를 중첩한 f-string(`f"{d["k"]}"`, PEP 701), 런타임 `int | None`
- `feature_version` 은 best-effort이므로 아래 AST·토큰 검사로 보충한다.

**AST 검사**(`ast.NodeVisitor`, 규칙마다 이유를 주석에 적는다):
1. `|` 로 타입을 묶는 것이 **런타임에 평가되는** 자리면 금지한다.
   - 주석(함수 인자·반환, `AnnAssign`)은 그 모듈에 `from __future__ import annotations` 가 **없을 때만** 금지다. 모듈마다 따로 판단한다(schema.py에는 없고 init_db.py에는 있다).
   - 주석 밖의 `BinOp(BitOr)` 는 피연산자가 타입으로 보일 때 금지한다.
     - 타입으로 보는 것: `None` 상수, builtin 타입 이름(`int`, `str`, `bytes`, `float`, `bool`, `list`, `dict`, `tuple`, `set`, `frozenset`, `type`, `object`), `Subscript`(`list[int]`)
     - `isinstance`/`issubclass` 두 번째 인자의 `|` 도 포함한다.
   - 정수 플래그(`re.I | re.M`)는 허용한다. 오탐이 나면 지금 코드에서 통과하는지로 확인한다.
2. `match` 문(`ast.Match`). 문법 검사와 겹쳐도 둔다.
3. `zip(..., strict=…)` 호출.
4. `dataclass(...)`·`dataclasses.dataclass(...)`·`field(...)` 의 `slots=`, `kw_only=`, `match_args=` 키워드.
5. 3.10+ 이름을 쓰면 금지한다. import와 속성 접근(`typing.X`, `datetime.UTC`) 둘 다 본다.
   - `tomllib`
   - `datetime.UTC`(`from datetime import UTC` 포함)
   - `itertools.pairwise`
   - `typing` 의 `TypeAlias`, `ParamSpec`, `Concatenate`, `TypeGuard`, `is_typeddict`(3.10)
   - `typing` 의 `Self`, `LiteralString`, `Never`, `assert_never`, `assert_type`, `reveal_type`, `Required`, `NotRequired`, `Unpack`, `TypeVarTuple`, `dataclass_transform`(3.11)
   - `typing` 의 `override`(3.12), `TypeIs`, `ReadOnly`(3.13)
   - 이 목록은 상수 하나로 둔다.

**토큰 검사**(`tokenize`, f-string, PEP 701):
- f-string의 치환 필드 안에서 바깥과 **같은 따옴표**로 시작하는 문자열, 백슬래시가 든 문자열, 주석은 3.9에서 문법 오류다. 이것을 잡는다.
- 3.12+ tokenize의 `FSTRING_START`/`FSTRING_MIDDLE`/`FSTRING_END` 토큰과 그 사이의 `STRING`·`COMMENT` 토큰으로 판단한다.
- 구현은 재량이다. 아래 변이 검사가 실패하면 된다.

**자체 테스트**(parametrize, 짧은 소스 조각):
- 위 규칙마다 잡아야 하는 조각 하나씩.
- 잡지 않아야 하는 조각
  - `from __future__ import annotations` 아래의 `def f(x: int | None) -> str | None`
  - `x = dict[str, list[str]]()`
  - `flags = re.I | re.M`
  - `n = a | b`(정수)
  - 바깥과 다른 따옴표를 쓴 `f"{d['k']}"`

### 3. 변이 검사

아래를 하나씩 손으로 넣고 `uv run pytest tests/test_py39_compat.py -q` 가 **실패하는지** 본다. 손으로 되돌린 뒤 통과를 확인한다. 실패한 단언 한 줄을 summary에 적는다.

| 변이 | 실패해야 하는 이유 |
|---|---|
| `service/schema.py` 의 `child_tables` 반환 주석을 `dict[str, list[str]] \| None` 으로 | schema.py에는 future import가 없어 런타임에 평가된다 |
| `scripts/init_db.py` 의 아무 함수 안에 `import tomllib` | 3.11 모듈 |
| `config/config.py` 의 함수 하나(없으면 새 함수)에 `return f"{d["k"]}"` | 같은 따옴표 중첩 f-string, `feature_version` 이 못 잡는다 |
| `service/schema.py` 의 함수 하나에 `try: pass` / `except* ValueError: pass` | 3.11 문법 |
| `scripts/init_db.py` 의 `@dataclass` 를 `@dataclass(slots=True)` 로 | 3.10 키워드 |
| `scripts/init_db.py` 에서 `from genviewer.utils import user` 를 함수 안에 더하고 `utils/user.py` 에 `x: int \| None = None` (future import 없이) | 닿는 모듈 계산이 새 모듈을 따라간다 |

- 마지막 변이는 계산이 함수 안 import를 따라가는지 보는 것이다. 두 파일 모두 되돌린다.
- 변이 검사 뒤 `git diff --stat -- src` 가 비어 있어야 한다.

### 4. 문서

- `docs/ARCHITECTURE.md` "강제:" 줄의 Python 3.9 문장을 고친다.
  - 예: "`tests/test_py39_compat.py` 가 init_db 에서 닿는 모듈을 import를 따라가며 찾아 3.9 문법·3.10+ 이름을 정적으로 검사한다."
  - "가드 테스트 제안은 … P1" 은 지운다.
- `docs/ADR.md` ADR-014 트레이드오프의 "이 호환을 지키는 자동 테스트가 아직 없다(리뷰로 지킨다)." 를 고친다.
  - 예: "`tests/test_py39_compat.py` 가 문법과 3.10+ 이름을 정적으로 검사한다. 실제 3.9 인터프리터로 import해 보지는 않고, psycopg 3.2 API 차이는 검사 밖이다."
- `README.md` '서버' 절의 "이 3.9 호환을 지키는 자동 테스트는 아직 없다. …"(~615-617)를 같은 뜻으로 고친다. 모듈 목록은 "테스트가 import를 따라가며 찾는다" 로 바꾼다.

## Acceptance Criteria

```bash
uv run pytest tests/test_py39_compat.py tests/test_boundaries.py -q   # 새 테스트 통과 (skip 없음)
uv run genviewer-init-db --dry-run           # init_db 가 그대로 돈다 (src 불변 확인)
uv run ruff check src tests                  # 린트 통과
uv run pytest -q                             # 전체 통과
git diff --stat -- src                       # 비어 있어야 한다 (변이 검사 뒤 되돌렸다)
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - `src/` 가 바뀌지 않았는가?
   - 닿는 모듈 집합에 위 일곱 개가 모두 있는가(테스트 실패 메시지나 `-s` 출력으로 확인)?
   - CLAUDE.md CRITICAL이 나열한 금지 항목(`X | Y`, `match`, `zip(strict=)`, `dataclass(slots=/kw_only=)`, `tomllib`)을 모두 검사하는가?
3. 결과에 따라 `phases/6-boundary-guards/index.json` 의 step 1을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "tests/test_py39_compat.py: init_db 에서 import 를 따라가 닿는 모듈 <N>개(<목록>)를 feature_version=(3,9) + AST(런타임 |·match·zip strict·dataclass slots/kw_only·3.10+ 이름) + tokenize(PEP 701 f-string) 로 검사. src 불변. 변이: schema 반환 | None → <단언>, tomllib → <…>, 중첩 따옴표 f-string → <…>, except* → <…>, dataclass(slots) → <…>, 함수 안 import 로 utils/user 추가 → <…>. ARCHITECTURE 강제 줄·ADR-014·README 서버 절 갱신. 전체 <N passed / M skipped / 1 xfailed>"`
   - 지금 코드가 규칙을 어긴 것을 찾음 → `"status": "blocked"`, `"blocked_reason": "<파일:행: 이유> 가 3.9 호환 규칙을 어긴다. src 수정은 승인 범위 밖"` 후 즉시 중단
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`

## 금지사항

- `src/` 를 바꾸지 마라(변이 검사는 되돌린다). 이유: 이 phase의 승인 범위는 테스트 추가뿐이다.
- 닿는 모듈 목록을 손으로 쓴 상수로만 검사하지 마라. 이유: init_db가 새 모듈을 import하면 목록이 낡아 그 모듈은 검사 밖에 남는다. 손으로 쓴 일곱 개는 하한으로만 쓴다.
- `uv python install 3.9` 나 3.9 인터프리터 실행에 기대는 테스트를 만들지 마라(있으면 쓰고 없으면 skip하는 형태도 안 된다). 이유: 개발 PC와 하네스 세션에 3.9가 없고, skip은 아무것도 지키지 않는다.
- `from __future__ import annotations` 유무와 상관없이 모든 주석의 `|` 를 금지하지 마라. 이유: init_db.py는 그 import 덕분에 `tuple | None` 을 정당하게 쓴다(지금 코드가 실패하게 된다).
- step 0의 스캐너와 같은 일을 하는 import 해석 함수를 새로 만들지 마라. 이유: 두 곳의 해석이 어긋나면 한쪽만 고쳐진다.
- 기존 테스트를 깨뜨리지 마라.
