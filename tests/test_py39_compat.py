"""init_db 가 닿는 모듈의 Python 3.9 호환 (CLAUDE.md 아키텍처 규칙의 두 번째 CRITICAL, ADR-014).

RHEL 7 서버는 `PYTHONPATH=src python3.9 -m genviewer.scripts.init_db` 로 소스에서 돈다.
그래서 init_db 에서 import 를 따라가 닿는 genviewer 모듈(함수 안 import 와 부모 패키지
`__init__` 포함)은 3.9 에서 import 되고 돌아야 한다. 3.9 인터프리터 없이 정적으로 본다.

- 문법: `ast.parse(feature_version=(3, 9))`. best-effort 라서 아래 둘로 보충한다.
- AST: 런타임에 평가되는 `X | Y`, `match`, `zip(strict=)`, `dataclass(slots=/kw_only=/
  match_args=)`, 3.10+ 이름(`NEWER_NAMES`).
- 토큰: 3.12 에서 풀린 f-string 치환 필드 제약(PEP 701).

범위 밖: 서드파티(psycopg 등). 서버의 psycopg 는 3.2.x 이고 그 API 차이는 이 검사가 보지 않는다.
`sys.version_info` 분기는 이해하지 못한다. 필요해지면 그때 예외를 더한다.
"""

import ast
import io
import string
import textwrap
import tokenize

import pytest
from fixtures.imports import imported_names, located_imports, package_dir, package_modules

ENTRY = "genviewer.scripts.init_db"

# 2026-10-17 에 닿던 모듈. 하한으로만 쓴다(계산이 망가져 집합이 비면 잡히게).
# 검사 대상은 이 목록이 아니라 import 를 따라가 계산한 집합이다.
MINIMUM_REACHABLE = frozenset(
    {
        "genviewer",
        "genviewer.scripts",
        "genviewer.scripts.init_db",
        "genviewer.service",
        "genviewer.service.schema",
        "genviewer.config",
        "genviewer.config.config",
    }
)

# 3.9 에 없는 표준 라이브러리 이름 -> 생긴 버전. 모듈 이름이면 그 아래 이름도 전부다.
NEWER_NAMES = {
    "tomllib": "3.11",
    "datetime.UTC": "3.11",
    "itertools.pairwise": "3.10",
    "typing.TypeAlias": "3.10",
    "typing.ParamSpec": "3.10",
    "typing.Concatenate": "3.10",
    "typing.TypeGuard": "3.10",
    "typing.is_typeddict": "3.10",
    "typing.Self": "3.11",
    "typing.LiteralString": "3.11",
    "typing.Never": "3.11",
    "typing.assert_never": "3.11",
    "typing.assert_type": "3.11",
    "typing.reveal_type": "3.11",
    "typing.Required": "3.11",
    "typing.NotRequired": "3.11",
    "typing.Unpack": "3.11",
    "typing.TypeVarTuple": "3.11",
    "typing.dataclass_transform": "3.11",
    "typing.override": "3.12",
    "typing.TypeIs": "3.13",
    "typing.ReadOnly": "3.13",
}

# `|` 의 피연산자가 이것이면 타입 결합으로 본다(`int | None`, `list[str] | None`).
# 정수 플래그(`re.I | re.M`)나 이름끼리(`a | b`)는 값 연산일 수 있으므로 허용한다.
BUILTIN_TYPES = frozenset(
    "int str bytes float bool list dict tuple set frozenset type object".split()
)

# 3.10 에 생긴 키워드. 3.9 에서는 TypeError 로 import(클래스 정의) 자체가 죽는다.
DATACLASS_CALLS = frozenset(
    {
        "dataclass",
        "dataclasses.dataclass",
        "field",
        "dataclasses.field",
        "make_dataclass",
        "dataclasses.make_dataclass",
    }
)
DATACLASS_KEYWORDS = frozenset({"slots", "kw_only", "match_args"})


def reachable_modules(entry: str = ENTRY) -> dict:
    """entry 에서 import 를 따라가 닿는 genviewer 모듈 -> (경로, 패키지 여부).

    모듈 수준과 함수 안 import 를 모두 따라간다(함수가 불리면 import 된다). 이름마다 앞부분을
    잘라 가며 genviewer 의 실제 모듈 파일인 것을 모은다. 그래서 부모 패키지 `__init__`(import 할 때
    실행된다)이 들어가고, `from X import y` 는 스캐너가 주는 X 와 X.y 중 X.y 가 모듈이면 그것까지
    들어간다. genviewer 밖(stdlib, psycopg)은 파일 목록에 없으므로 빠진다.
    """
    files = {
        module: (path, is_package) for module, path, is_package in package_modules("genviewer")
    }
    reached: dict = {}
    todo = [entry]
    while todo:
        name = todo.pop()
        parts = name.split(".")
        for end in range(1, len(parts) + 1):
            module = ".".join(parts[:end])
            if module not in files or module in reached:
                continue
            reached[module] = files[module]
            path, is_package = files[module]
            source = path.read_text(encoding="utf-8")
            todo.extend(imported_names(source, module, is_package=is_package))
    return dict(sorted(reached.items()))


def _newer_name(name: str) -> str | None:
    for newer, version in NEWER_NAMES.items():
        if name == newer or name.startswith(newer + "."):
            return version
    return None


def _dotted(node: ast.AST) -> str | None:
    """`a.b.c` 같은 이름 사슬이면 그 문자열, 아니면 None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


def _is_bitor(node: ast.AST) -> bool:
    return isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr)


def _is_type_like(node: ast.AST) -> bool:
    return (
        (isinstance(node, ast.Constant) and node.value is None)
        or (isinstance(node, ast.Name) and node.id in BUILTIN_TYPES)
        or isinstance(node, ast.Subscript)
    )


class _Py39Visitor(ast.NodeVisitor):
    """3.9 에서 import 하거나 실행할 때 죽는 AST 를 (행, 이유)로 모은다."""

    def __init__(self, future_annotations: bool) -> None:
        self.future_annotations = future_annotations
        self.found: set[tuple[int, str]] = set()
        self._in_annotation = 0

    def _report(self, node: ast.AST, reason: str) -> None:
        self.found.add((node.lineno, reason))

    # 주석(annotation)은 `from __future__ import annotations` 가 있으면 문자열로 남아 평가되지
    # 않는다. 없으면 정의할 때 평가되므로 그 안의 `|` 는 피연산자와 상관없이 타입 결합이다
    # (3.9 의 type 에는 `__or__` 가 없다). future import 는 모듈마다 따로 본다.
    def _annotation(self, node: ast.expr | None) -> None:
        if node is None or self.future_annotations:
            return
        self._in_annotation += 1
        self.visit(node)
        self._in_annotation -= 1

    def visit_arg(self, node: ast.arg) -> None:
        self._annotation(node.annotation)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._annotation(node.annotation)
        self.visit(node.target)
        if node.value is not None:
            self.visit(node.value)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        # returns 만 주석으로 따로 본다. 인자 주석은 visit_arg 가 본다.
        self._annotation(node.returns)
        for child in (*node.decorator_list, node.args, *node.body):
            self.visit(child)

    visit_AsyncFunctionDef = visit_FunctionDef

    # 주석 밖의 `X | Y` 는 실행할 때 평가된다(별칭 `T = int | None`, 기본값 등).
    def visit_BinOp(self, node: ast.BinOp) -> None:
        if _is_bitor(node) and (
            self._in_annotation or _is_type_like(node.left) or _is_type_like(node.right)
        ):
            self._report(node, "런타임에 평가되는 X | Y 타입 결합 (3.10+)")
        self.generic_visit(node)

    # match 문은 3.10 문법이다. feature_version 검사와 겹쳐도 둔다.
    def visit_Match(self, node: ast.Match) -> None:
        self._report(node, "match 문 (3.10+)")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _dotted(node.func)
        keywords = {keyword.arg for keyword in node.keywords}
        # isinstance 의 두 번째 인자는 늘 타입이므로 사용자 클래스끼리의 `|` 도 타입 결합이다.
        if name in ("isinstance", "issubclass") and len(node.args) >= 2 and _is_bitor(node.args[1]):
            self._report(node, f"{name} 의 X | Y 타입 결합 (3.10+)")
        # zip(strict=) 는 3.10 키워드다. 3.9 에서는 TypeError.
        if name in ("zip", "builtins.zip") and "strict" in keywords:
            self._report(node, "zip(strict=) (3.10+)")
        if name in DATACLASS_CALLS:
            for keyword in sorted(keywords & DATACLASS_KEYWORDS):
                self._report(node, f"{name}({keyword}=) (3.10+)")
        self.generic_visit(node)

    # 속성으로 쓰는 3.10+ 이름(`typing.Self`, `datetime.UTC`). import 는 py39_violations 가 본다.
    def visit_Attribute(self, node: ast.Attribute) -> None:
        name = _dotted(node)
        version = _newer_name(name) if name else None
        if version:
            self._report(node, f"{name} ({version}+)")
        self.generic_visit(node)


def _fstring_violations(source: str) -> set[tuple[int, str]]:
    """3.12 이전에는 f-string 치환 필드 안에 쓸 수 없던 것(PEP 701).

    3.9 는 f-string 을 먼저 보통 문자열로 읽으므로 치환 필드 안에 바깥 따옴표가 나오면 거기서
    문자열이 끝나고, 치환 필드 안의 백슬래시와 주석은 문법 오류다. feature_version 은 이것을
    못 잡는다. 3.12+ tokenize 는 f-string 을 FSTRING_START … FSTRING_END 로 쪼개고 치환 필드를
    OP `{` `}` 로 내므로, 열린 f-string 마다 따옴표와 `{` 깊이를 쌓아 두고 판단한다.
    """
    found: set[tuple[int, str]] = set()
    stack: list[list] = []  # 열린 f-string 마다 [따옴표, 치환 필드 `{` 깊이]
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.FSTRING_END:
            stack.pop()
        # 이 토큰을 치환 필드 안에 품은 f-string 의 따옴표들. 맨 위 f-string 은 지금 치환 필드
        # 안일 때만이고, 그 아래는 안쪽 f-string 이 그 치환 필드 안에서 열렸으므로 늘 해당한다.
        quotes = [quote for quote, _ in stack[:-1]]
        if stack and stack[-1][1]:
            quotes.append(stack[-1][0])
        if quotes:
            line = tok.start[0]
            if any(quote in tok.string for quote in quotes):
                found.add((line, "f-string 치환 필드 안에 바깥과 같은 따옴표 (3.12+)"))
            if "\\" in tok.string:
                found.add((line, "f-string 치환 필드 안의 백슬래시 (3.12+)"))
            if tok.type == tokenize.COMMENT:
                found.add((line, "f-string 치환 필드 안의 주석 (3.12+)"))
        if tok.type == tokenize.FSTRING_START:
            stack.append([tok.string.lstrip(string.ascii_letters), 0])
        elif stack and tok.type == tokenize.OP and tok.string in ("{", "}"):
            # 치환 필드 안의 dict·set 중괄호도 짝이 맞으므로 깊이만 세면 된다.
            stack[-1][1] += 1 if tok.string == "{" else -1
    return found


def py39_violations(source: str, module: str, *, is_package: bool = False) -> list[tuple[int, str]]:
    """Python 3.9 에서 import 하거나 실행할 때 죽는 곳의 (행, 이유) 목록."""
    found: set[tuple[int, str]] = set()
    try:
        ast.parse(source, feature_version=(3, 9))
    except SyntaxError as exc:
        found.add((exc.lineno or 0, f"3.9 문법이 아니다: {exc.msg}"))
    imports = located_imports(source, module, is_package=is_package)
    # __future__ import 는 모듈 맨 위에만 올 수 있다.
    future = ("__future__.annotations", None) in {(name, scope) for name, scope, _ in imports}
    visitor = _Py39Visitor(future_annotations=future)
    visitor.visit(ast.parse(source))
    found |= visitor.found
    for name, _, line in imports:
        version = _newer_name(name)
        if version:
            found.add((line, f"{name} ({version}+)"))
    found |= _fstring_violations(source)
    return sorted(found)


# -- 검사기 자체 검사 ---------------------------------------------------------

FUTURE = "from __future__ import annotations\n"


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        # 런타임에 평가되는 X | Y
        ("def f(x: int | None):\n    pass\n", "X | Y"),
        ("def f() -> str | None:\n    pass\n", "X | Y"),
        ("def f(x: Foo | Bar):\n    pass\n", "X | Y"),  # 주석이면 사용자 클래스도
        ("x: int | None = None\n", "X | Y"),
        ("class A:\n    x: list[int] | None = None\n", "X | Y"),
        ("T = int | None\n", "X | Y"),
        ("T = None | str\n", "X | Y"),
        ("T = list[int] | Foo\n", "X | Y"),
        ("T = Foo | Bar | None\n", "X | Y"),
        ("ok = isinstance(x, Foo | Bar)\n", "isinstance"),
        ("ok = issubclass(x, Foo | Bar)\n", "issubclass"),
        (FUTURE + "T = int | None\n", "X | Y"),  # future import 는 주석만 바꾼다
        # match
        ("match x:\n    case 1:\n        pass\n", "match 문"),
        # zip(strict=)
        ("pairs = zip(a, b, strict=True)\n", "zip(strict=)"),
        # dataclass 3.10 키워드
        ("@dataclass(slots=True)\nclass A:\n    x: int\n", "dataclass(slots=)"),
        ("@dataclasses.dataclass(kw_only=True)\nclass A:\n    x: int\n", "kw_only="),
        ("@dataclass(match_args=False)\nclass A:\n    x: int\n", "match_args="),
        ("class A:\n    x: int = field(kw_only=True)\n", "field(kw_only=)"),
        # 3.10+ 이름 (import 와 속성)
        ("import tomllib\n", "tomllib (3.11+)"),
        ("def load():\n    import tomllib\n", "tomllib (3.11+)"),
        ("from tomllib import loads\n", "tomllib"),
        ("from datetime import UTC\n", "datetime.UTC (3.11+)"),
        ("import datetime\nnow = datetime.datetime.now(datetime.UTC)\n", "datetime.UTC (3.11+)"),
        ("from itertools import pairwise\n", "itertools.pairwise (3.10+)"),
        ("from typing import TypeAlias\n", "typing.TypeAlias (3.10+)"),
        ("from typing import Self\n", "typing.Self (3.11+)"),
        ("import typing\nT = typing.Self\n", "typing.Self (3.11+)"),
        ("from typing import override\n", "typing.override (3.12+)"),
        ("from typing import TypeIs\n", "typing.TypeIs (3.13+)"),
        # feature_version 이 잡는 문법
        ("try:\n    pass\nexcept* ValueError:\n    pass\n", "3.9 문법"),
        ("def f[T](x: T) -> T:\n    return x\n", "3.9 문법"),
        ("type X = int\n", "3.9 문법"),
        # PEP 701 f-string
        ('x = f"{d["k"]}"\n', "같은 따옴표"),
        ("x = f'{d['k']}'\n", "같은 따옴표"),
        ('x = f"{f"{y}"}"\n', "같은 따옴표"),
        ('x = f"{f\'{d["k"]}\'}"\n', "같은 따옴표"),  # 바깥의 바깥 따옴표
        ('x = f"""{d["""k"""]}"""\n', "같은 따옴표"),
        ("x = f\"{'\\n'.join(y)}\"\n", "백슬래시"),
        ('x = f"""{\n    y  # 주석\n}"""\n', "주석"),
    ],
)
def test_checker_detects(source, reason):
    found = py39_violations(source, "genviewer.service.foo")
    assert any(reason in why for _, why in found), found


@pytest.mark.parametrize(
    "source",
    [
        FUTURE + "def f(x: int | None) -> str | None:\n    pass\n",
        FUTURE + "x: int | None = None\n",
        FUTURE + "class A:\n    params: tuple | None = None\n",
        "x = dict[str, list[str]]()\n",
        "def child_tables() -> dict[str, list[str]]:\n    pass\n",
        'def f(x: "int | None"):\n    pass\n',
        "import re\nflags = re.I | re.M\n",
        "n = a | b\n",
        "merged = {**a} | b\n",
        "ok = isinstance(x, (int, str))\n",
        "pairs = zip(a, b)\n",
        "@dataclass\nclass A:\n    x: int = field(default=0)\n",
        "from typing import Optional\nimport datetime\nnow = datetime.timezone.utc\n",
        "x = f\"{d['k']}\"\n",
        'x = f"""{d["k"]}"""\n',
        "x = f'{a:>{w}}' + f'{{lit}}' + f'\\n{y}'\n",
        "x = f'{ {1: 2}[1] }'\n",
    ],
)
def test_checker_allows(source):
    assert py39_violations(source, "genviewer.service.foo") == []


def test_checker_reports_line():
    source = textwrap.dedent(
        """
        from __future__ import annotations

        import os


        def f():
            import tomllib
        """
    )
    assert py39_violations(source, "genviewer.service.foo") == [(8, "tomllib (3.11+)")]


# -- 실제 소스 ----------------------------------------------------------------


def test_reachable_modules_include_known_minimum():
    reached = set(reachable_modules())
    assert MINIMUM_REACHABLE <= reached, (
        f"계산한 집합: {sorted(reached)}\n빠진 것: {sorted(MINIMUM_REACHABLE - reached)}"
    )


def test_reachable_modules_are_py39_compatible():
    src = package_dir("genviewer").parent
    violations = [
        f"{path.relative_to(src).as_posix()}:{line}: {reason}"
        for module, (path, is_package) in reachable_modules().items()
        for line, reason in py39_violations(
            path.read_text(encoding="utf-8"), module, is_package=is_package
        )
    ]
    assert not violations, "init_db 에서 닿는 모듈이 Python 3.9 에서 죽는다:\n" + "\n".join(
        violations
    )
