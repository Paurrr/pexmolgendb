"""사용자에게 보이는 문구는 영어다 (ADR-020, UI_GUIDE "문구").

`src/genviewer` 의 문자열 상수와 f-string 글자 조각, `tools/*.sh` 의 출력 줄에 한글이 있으면
실패한다. ADR-020 이 한국어로 두는 것은 뺀다.

- 모듈·클래스·함수 docstring 과 그 밖의 식 문장 문자열. typer 명령(`app.command`/`app.callback`)
  의 docstring 은 `--help` 문구라서 본다.
- 로그 호출의 인자(`LOGGER_NAMES` 의 `LOG_METHODS`). 로그 파일로 가는 문구다.
- 이력 요약(`change_log.summary`)을 만드는 함수(`SUMMARY_FUNCTIONS`). DB 에 저장되는 데이터라
  바꾸면 옛 줄과 새 줄이 갈린다.
- 셸의 주석(줄 전체, 줄 끝)과 deploy.sh 의 `marker=` 줄. marker 는 다음 배포가 옛 런처를 찾는
  식별자다.

Python 주석은 AST 에 없어서 따로 뺄 것이 없다. `tests/` 는 보지 않는다(테스트 데이터와 메시지는
범위 밖). AST·텍스트만 보므로 PySide6 없이 돈다.
"""

import ast
import re
import textwrap
from pathlib import Path

import pytest
from fixtures.imports import module_path, package_modules

REPO = Path(__file__).resolve().parents[1]
HANGUL = re.compile("[가-힣]")

# 로그 호출로 보는 `<이름>.<메서드>(...)`. 이름은 src 에서 `logging.getLogger(...)` 를 받는 변수다
# (test_logger_names_match_src 가 맞춘다). 속성(`self.log(...)`)은 로그 패널일 수 있어 보지 않는다.
LOGGER_NAMES = frozenset(
    {
        "logging",  # 모듈 함수 logging.warning(...)
        "log",  # 모듈 로거(controllers, main, net)와 utils/reporting.report_error 의 지역 로거
        "logger",  # utils/reporting.report 의 지역 로거
        "root",  # utils/logs.setup 의 루트 로거
    }
)
LOG_METHODS = frozenset({"debug", "info", "warning", "error", "exception", "critical", "log"})

# typer 명령 데코레이터 `@app.command(...)`, `@app.callback(...)`. 그 docstring 은 --help 다.
TYPER_APP = "app"
TYPER_DECORATORS = frozenset({"command", "callback"})

# 이력 요약을 만드는 함수. (모듈, 함수 이름) 이고 그 함수 안의 문자열만 뺀다.
# 이 함수들이 부르는 도우미(_short, _quoted, process_label, _TAB_LABEL)에는 한글이 없어서
# 넣지 않는다. test_summary_functions_still_hold_korean 이 낡은 항목을 잡는다.
AUDIT = "genviewer.service.repo.audit"
CLI = "genviewer.cli"
SUMMARY_FUNCTIONS = frozenset(
    {
        (AUDIT, "device_insert"),  # 'device 추가  이름 (celltype)'
        (AUDIT, "device_update"),  # 'device 수정  컬럼 "옛" -> "새"'
        (AUDIT, "device_delete"),  # 'device 삭제  …, 자식 행 N개'
        (AUDIT, "tab_change"),  # '탭 X  N행 중 M행 바뀜' / 'N행 -> M행'
        (AUDIT, "csv_import"),  # 'CSV 불러오기  파일  device N개 … 버전 V'
        (AUDIT, "process_add"),  # 'process 추가  … (원본 에서 device N개 복사)'
        (AUDIT, "process_delete"),  # 'process 삭제  …  device N개가 함께 사라짐'
    }
)


def _is_str(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _is_log_call(node: ast.Call) -> bool:
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr in LOG_METHODS
        and isinstance(func.value, ast.Name)
        and func.value.id in LOGGER_NAMES
    )


def _is_typer_command(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if (
            isinstance(target, ast.Attribute)
            and target.attr in TYPER_DECORATORS
            and isinstance(target.value, ast.Name)
            and target.value.id == TYPER_APP
        ):
            return True
    return False


class _KoreanStrings(ast.NodeVisitor):
    """한글이 든 문자열 상수와 f-string 의 (행, 글자)를 모은다."""

    def __init__(self, module: str, allowed: frozenset[tuple[str, str]]) -> None:
        self.module = module
        self.allowed = allowed
        self.found: list[tuple[int, str]] = []
        self._stack: list[str] = []
        self._help_docs: set[int] = set()  # 검사하는 docstring(typer 명령)의 Expr id

    def _allowed_scope(self) -> bool:
        scope = ".".join(self._stack)
        return any(
            self.module == module and (scope == name or scope.startswith(name + "."))
            for module, name in self.allowed
        )

    def _enter(self, node: ast.AST, name: str) -> None:
        self._stack.append(name)
        if not self._allowed_scope():
            self.generic_visit(node)
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if _is_typer_command(node) and node.body and isinstance(node.body[0], ast.Expr):
            self._help_docs.add(id(node.body[0]))
        self._enter(node, node.name)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._enter(node, node.name)

    def visit_Expr(self, node: ast.Expr) -> None:
        # docstring(모듈·클래스·함수)과 대입 뒤에 붙인 설명 같은 식 문장 문자열은 보지 않는다.
        if _is_str(node.value) and id(node) not in self._help_docs:
            return
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if not _is_log_call(node):
            self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        if any(_is_str(part) and HANGUL.search(part.value) for part in node.values):
            self.found.append((node.lineno, ast.unparse(node)))
        for part in node.values:
            if isinstance(part, ast.FormattedValue):
                self.visit(part.value)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and HANGUL.search(node.value):
            self.found.append((node.lineno, node.value))


def korean_strings(
    source: str, module: str, *, allowed: frozenset[tuple[str, str]] = SUMMARY_FUNCTIONS
) -> list[tuple[int, str]]:
    """source 에서 사용자에게 보일 수 있는 한글 문자열의 (행, 글자) 목록."""
    visitor = _KoreanStrings(module, allowed)
    visitor.visit(ast.parse(source))
    return sorted(visitor.found)


def _strip_shell_comment(line: str) -> str:
    """따옴표 밖에서 줄 처음이나 공백 뒤에 오는 `#` 부터 지운다(sh 의 주석 규칙).

    `$#`, `${#x}` 처럼 공백 뒤가 아닌 `#` 은 주석이 아니다. 줄마다 따로 본다.
    """
    quote = None
    escaped = False
    for i, ch in enumerate(line):
        if escaped:
            escaped = False
        elif quote == "'":
            if ch == "'":
                quote = None
        elif ch == "\\":
            escaped = True
        elif quote == '"':
            if ch == '"':
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1].isspace()):
            return line[:i]
    return line


def shell_output_lines(text: str) -> list[tuple[int, str]]:
    """셸 스크립트에서 주석과 `marker=` 줄을 뺀 나머지 중 한글이 든 (행, 줄)."""
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        code = _strip_shell_comment(line)
        if code.lstrip().startswith("marker="):
            continue
        if HANGUL.search(code):
            found.append((number, line))
    return found


# -- 스캐너 자체 검사 ---------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "module"),
    [
        ('QMessageBox.warning(None, "T", "한글")', "genviewer.views.foo"),
        ('@app.command()\ndef status():\n    """한글 도움말."""\n', CLI),
        ('@app.callback(invoke_without_command=True)\ndef root():\n    """한글."""\n', CLI),
        ('@app.command\ndef status():\n    """한글."""\n', CLI),
        ('text = f"{n}개 지움"', "genviewer.views.foo"),
        ('text = f"Deleted {n} " + f"{m:>{w}}행"', "genviewer.views.foo"),
        ('self.log("한글")', "genviewer.controllers.foo"),  # 로그 패널
        ('self.logRequested.emit("한글")', "genviewer.controllers.foo"),
        ('self.log.info("한글")', "genviewer.controllers.foo"),  # 이름이 아닌 속성
        ('x = {"title": "한글"}', "genviewer.views.foo"),
        ('class A:\n    LABEL = "한글"\n', "genviewer.views.foo"),
        # 허용 목록은 (모듈, 함수) 쌍이다. 같은 이름의 다른 모듈, 같은 모듈의 다른 함수는 본다.
        ('def device_insert():\n    return "한글"\n', "genviewer.views.foo"),
        ('def user_text():\n    return "한글"\n', AUDIT),
        ('summary = "device 추가"', AUDIT),  # 모듈 수준
    ],
)
def test_scanner_detects_korean_text(source, module):
    assert korean_strings(source, module)


@pytest.mark.parametrize(
    ("source", "module"),
    [
        ('"""한글 모듈 docstring."""\nx = 1\n', "genviewer.views.foo"),
        ('class A:\n    """한글."""\n', "genviewer.views.foo"),
        ('def f():\n    """한글."""\n', "genviewer.views.foo"),
        ('async def f():\n    """한글."""\n', "genviewer.views.foo"),
        ('X = 1\n"""X 는 한글 설명."""\n', "genviewer.views.foo"),
        ('log.info("한글")', "genviewer.controllers.foo"),
        ('log.warning("%s 한글", f"{x} 한글")', "genviewer.controllers.foo"),
        ('logger.exception("한글 %s", name)', "genviewer.utils.reporting"),
        ('logging.error("한글")', "genviewer.main"),
        ('root.warning("한글 (%s): %s", target, e)', "genviewer.utils.logs"),
        ("# 한글\nx = 1  # 한글\n", "genviewer.views.foo"),
        ('def device_insert(n):\n    return f"device 추가  {n}"\n', AUDIT),
        ('def tab_change():\n    def inner():\n        return "탭"\n', AUDIT),
        ('x = "English only"', "genviewer.views.foo"),
    ],
)
def test_scanner_ignores_text_that_stays_korean(source, module):
    assert korean_strings(source, module) == []


def test_scanner_reports_line_and_text():
    source = textwrap.dedent(
        """
        x = 1
        a = "가"
        b = f"{x}나"
        """
    )
    assert korean_strings(source, "genviewer.views.foo") == [(3, "가"), (4, "f'{x}나'")]


@pytest.mark.parametrize(
    "line",
    [
        'echo "한글"',
        "    echo '한글' >&2",
        'echo "a # 한글"',
        "echo 'x' \"한글\"",
        'echo "$#개"',
        "echo ${#x}개",
        'name="한글"',
    ],
)
def test_shell_scanner_detects_output(line):
    assert shell_output_lines(line) == [(1, line)]


@pytest.mark.parametrize(
    "line",
    [
        "# 한글",
        "    # 한글",
        "#!/bin/sh 한글",
        'PGHBA_DB="${PGHBA_DB:-all}"       # 한글',
        "echo ok  # 한글",
        'marker="genviewer deploy.sh 가 생성"',
        '    marker="한글"',
        'echo "Done."',
    ],
)
def test_shell_scanner_ignores_comments_and_marker(line):
    assert shell_output_lines(line) == []


# -- 실제 소스 ----------------------------------------------------------------


def test_user_visible_python_strings_are_english():
    found = [
        f"{path.relative_to(REPO).as_posix()}:{line}: {text!r}"
        for module, path, _ in package_modules("genviewer")
        for line, text in korean_strings(path.read_text(encoding="utf-8"), module)
    ]
    assert not found, "사용자에게 보이는 한국어 문구 (ADR-020):\n" + "\n".join(found)


def test_shell_output_is_english():
    scripts = sorted((REPO / "tools").glob("*.sh"))
    assert scripts, "tools/*.sh 를 찾지 못했다"
    found = [
        f"{path.relative_to(REPO).as_posix()}:{number}: {line.strip()}"
        for path in scripts
        for number, line in shell_output_lines(path.read_text(encoding="utf-8"))
    ]
    assert not found, "셸 스크립트의 한국어 출력 (ADR-020):\n" + "\n".join(found)


@pytest.mark.parametrize(("module", "function"), sorted(SUMMARY_FUNCTIONS))
def test_summary_functions_still_hold_korean(module, function):
    """허용 목록이 낡지 않는다. 함수가 없어졌거나 한글이 없으면 그 항목을 지운다."""
    path, _ = module_path(module)
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(
        (n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function), None
    )
    assert node is not None, f"{module}.{function} 이 없다"
    lines = range(node.lineno, node.end_lineno + 1)
    found = korean_strings(source, module, allowed=frozenset())
    assert any(line in lines for line, _ in found)


def test_logger_names_match_src():
    """LOGGER_NAMES 는 src 에서 `logging.getLogger(...)` 를 받는 변수 이름 그대로다.

    빠지면 그 로그 호출이 잡히고, 남으면 로거가 아닌 이름의 호출까지 빠진다.
    """
    assigned = set()
    for _, path, _ in package_modules("genviewer"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Assign):
                continue
            calls_get_logger = any(
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "getLogger"
                and isinstance(sub.func.value, ast.Name)
                and sub.func.value.id == "logging"
                for sub in ast.walk(node.value)
            )
            if calls_get_logger:
                assigned.update(t.id for t in node.targets if isinstance(t, ast.Name))
    assert assigned == LOGGER_NAMES - {"logging"}


def test_typer_commands_are_recognised_in_cli():
    """typer 명령 docstring(--help) 검사가 실제 cli.py 에 닿는다. 명령을 더하면 여기도 더한다."""
    path, _ = module_path("genviewer.cli")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    commands = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and _is_typer_command(node)
    }
    assert commands == {"root", "status", "processes", "load", "export", "log"}
