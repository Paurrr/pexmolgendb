"""경계 가드 테스트용 import 스캐너 (pexqa `tests/fixtures/imports.py` 와 같은 형태).

AST만 보므로 PySide6 없이 돌고, 주석·문자열·docstring 속 이름은 잡지 않는다.
"""

import ast
import importlib.util
from collections.abc import Iterator
from pathlib import Path


class _ScopedImports(ast.NodeVisitor):
    """import 이름과 그 import 를 감싼 함수를 모은다."""

    def __init__(self, package: str) -> None:
        self.package = package
        self.found: list[tuple[str, str | None, int]] = []
        self._stack: list[str] = []
        self._functions = 0

    def _scope(self) -> str | None:
        # 클래스 본문은 import 시점에 실행되므로 함수 안이 아니면 모듈 수준이다.
        return ".".join(self._stack) if self._functions else None

    def _enter(self, node: ast.AST, name: str, *, function: bool) -> None:
        self._stack.append(name)
        self._functions += function
        self.generic_visit(node)
        self._functions -= function
        self._stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._enter(node, node.name, function=True)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._enter(node, node.name, function=True)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._enter(node, node.name, function=False)

    def visit_Import(self, node: ast.Import) -> None:
        self.found.extend((alias.name, self._scope(), node.lineno) for alias in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        base = node.module or ""
        if node.level:
            base = importlib.util.resolve_name("." * node.level + base, self.package)
        scope = self._scope()
        self.found.append((base, scope, node.lineno))
        self.found.extend((f"{base}.{alias.name}", scope, node.lineno) for alias in node.names)


def located_imports(
    source: str, module: str, *, is_package: bool = False
) -> list[tuple[str, str | None, int]]:
    """(import 이름, 감싼 함수 이름, 행) 목록. 이름과 함수 이름은 `scoped_imports` 와 같다."""
    visitor = _ScopedImports(module if is_package else module.rpartition(".")[0])
    visitor.visit(ast.parse(source))
    return visitor.found


def scoped_imports(
    source: str, module: str, *, is_package: bool = False
) -> list[tuple[str, str | None]]:
    """(import 이름, 감싼 함수 이름) 목록. 모듈 수준(클래스 본문 포함)이면 함수 이름은 None 이다.

    이름은 `imported_names` 와 같다. 함수 이름은 감싼 정의를 점으로 잇는다
    (`root`, `Exporter.write`, `outer.inner`).
    """
    return [
        (name, scope)
        for name, scope, _ in located_imports(source, module, is_package=is_package)
    ]


def imported_names(source: str, module: str, *, is_package: bool = False) -> list[str]:
    """import 대상 모듈과 `from X import y` 의 X.y 를 절대 이름으로 반환한다.

    상대 import 는 module 기준으로 푼다. 패키지 `__init__` 이면 is_package=True 로 준다.
    """
    return [name for name, _ in scoped_imports(source, module, is_package=is_package)]


def package_dir(package: str) -> Path:
    spec = importlib.util.find_spec(package)
    assert spec is not None and spec.submodule_search_locations, f"{package} 패키지를 찾을 수 없다"
    return Path(spec.submodule_search_locations[0])


def module_path(module: str) -> tuple[Path, bool]:
    """모듈 파일 경로와 패키지(`__init__.py`) 여부.

    모듈 자체는 실행하지 않는다(상위 패키지는 import 된다).
    """
    spec = importlib.util.find_spec(module)
    assert spec is not None and spec.origin, f"{module} 모듈을 찾을 수 없다"
    return Path(spec.origin), spec.submodule_search_locations is not None


def package_modules(package: str) -> Iterator[tuple[str, Path, bool]]:
    """패키지 아래(하위 패키지 포함) 모든 .py 파일의 (모듈 이름, 경로, 패키지 여부)."""
    root = package_dir(package)
    files = sorted(root.rglob("*.py"))
    assert files, f"{root} 에 .py 파일이 없다"
    for path in files:
        parts = (*package.split("."), *path.relative_to(root).with_suffix("").parts)
        is_package = parts[-1] == "__init__"
        yield ".".join(parts[:-1] if is_package else parts), path, is_package


def package_imports(package: str) -> Iterator[tuple[Path, str]]:
    """패키지 아래 모든 .py 파일의 (패키지 기준 상대 경로, import 이름)."""
    root = package_dir(package)
    for module, path, is_package in package_modules(package):
        for name in imported_names(path.read_text(encoding="utf-8"), module, is_package=is_package):
            yield path.relative_to(root), name


def package_sources(package: str) -> Iterator[tuple[Path, str]]:
    """패키지 아래 모든 .py 파일의 (패키지 기준 상대 경로, 소스)."""
    root = package_dir(package)
    for path in sorted(root.rglob("*.py")):
        yield path.relative_to(root), path.read_text(encoding="utf-8")
