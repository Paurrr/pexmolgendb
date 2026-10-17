"""레이어 경계 강제 (CLAUDE.md 아키텍처 규칙의 첫 CRITICAL, ARCHITECTURE "레이어" 표).

- Qt 금지 구역(티어 0~2, 그 안의 패키지 `__init__`, `__main__.py`)은 PySide6도, Qt 쪽 genviewer
  모듈(티어 3·4)도 import하지 않는다. `status` 등은 X가 없는 서버에서 돌아야 하고, 테스트가 GUI
  없이 돈다. 허용 예외는 `cli.py` 의 함수 `root` 안의 `genviewer.main` 하나다(창을 띄우는 경로).
- `models/` 는 genviewer 에서 `utils.validators` 만 안다. `net/` 은 자기 안에서 닫혀 있다.

정적 검사는 함수 안의 import도 본다. 새 인터프리터 import 검사는 그 함수를 부르지 않으므로
못 잡는다.
"""

import json
import os
import subprocess
import sys
import textwrap

import pytest
from fixtures.imports import (
    module_path,
    package_dir,
    package_imports,
    package_modules,
    scoped_imports,
)

# Qt 금지 구역. ARCHITECTURE 레이어 표에서 손으로 옮겨 적는다(src 를 스캔해 고르면 위반한 모듈이
# 저절로 빠진다). 패키지는 하위 전부라서 새 모듈이 자동으로 들어온다.
QT_FREE_PACKAGES = (
    "genviewer.config",  # 티어 0
    "genviewer.service",  # 티어 1 (repo/ 포함)
    "genviewer.scripts",  # 티어 1
)
QT_FREE_MODULES = (
    "genviewer",  # 패키지 __init__
    "genviewer.__main__",  # python -m genviewer → cli.main
    "genviewer.utils",  # 패키지 __init__
    "genviewer.utils.user",  # 티어 0
    "genviewer.utils.logs",  # 티어 0
    "genviewer.utils.validators",  # 티어 0
    "genviewer.utils.lisp",  # 티어 0
    "genviewer.cli",  # 티어 2
    "genviewer.utils.exporter",  # 티어 2
)

# Qt 금지 구역이 import하면 안 되는 것. 티어 3·4를 import하면 Qt가 따라오거나 레이어가 거꾸로 선다.
FORBIDDEN_TOP_LEVEL = frozenset({"PySide6", "shiboken6"})
FORBIDDEN_MODULES = (
    "genviewer.main",  # 티어 4
    "genviewer.controllers",  # 티어 4
    "genviewer.models",  # 티어 3
    "genviewer.views",  # 티어 3
    "genviewer.dialogs",  # 티어 3
    "genviewer.delegates",  # 티어 3
    "genviewer.net",  # 티어 3
    "genviewer.utils.background",  # 티어 3 (Qt utils)
    "genviewer.utils.dialogs",  # 티어 3 (Qt utils)
    "genviewer.utils.file_dialogs",  # 티어 3 (Qt utils)
    "genviewer.utils.menus",  # 티어 3 (Qt utils)
    "genviewer.utils.palette",  # 티어 3 (Qt utils)
    "genviewer.utils.table_utils",  # 티어 3 (Qt utils)
    "genviewer.utils.reporting",  # 티어 3 (Qt 없음, service.errors 사용)
)

# 유일한 예외: cli.py 의 함수 root 안에서 창을 띄울 때만 genviewer.main 을 가져온다.
ALLOWED_MODULE = "genviewer.cli"
ALLOWED_SCOPE = "root"
ALLOWED_NAMES = frozenset({"genviewer.main", "genviewer.main.run_gui"})


def _within(name: str, packages) -> bool:
    return any(name == package or name.startswith(package + ".") for package in packages)


def _is_forbidden(name: str) -> bool:
    return name.partition(".")[0] in FORBIDDEN_TOP_LEVEL or _within(name, FORBIDDEN_MODULES)


def boundary_violations(
    source: str, module: str, *, is_package: bool = False
) -> list[tuple[str, str | None]]:
    """Qt 금지 구역 규칙을 어기는 (import 이름, 감싼 함수 이름 또는 None=모듈 수준)."""
    return [
        (name, scope)
        for name, scope in scoped_imports(source, module, is_package=is_package)
        if _is_forbidden(name)
        and not (module == ALLOWED_MODULE and scope == ALLOWED_SCOPE and name in ALLOWED_NAMES)
    ]


def _outside(name: str, allowed: tuple[str, ...]) -> bool:
    """genviewer 안의 import 가 allowed 밖이면 True.

    `from genviewer.utils import validators` 의 `genviewer.utils` 처럼 허용 모듈의 상위 패키지
    자체는 밖으로 치지 않는다(그 `__init__` 은 Qt 금지 구역 검사가 본다).
    """
    if not _within(name, ("genviewer",)) or _within(name, allowed):
        return False
    return not any(package.startswith(name + ".") for package in allowed)


def _qt_free_files():
    files = {}
    for package in QT_FREE_PACKAGES:
        for module, path, is_package in package_modules(package):
            files[module] = (path, is_package)
    for module in QT_FREE_MODULES:
        files[module] = module_path(module)
    return dict(sorted(files.items()))


# -- 스캐너 자체 검사 ---------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "module"),
    [
        ("import PySide6", "genviewer.service.foo"),
        ("from PySide6.QtCore import Qt", "genviewer.service.foo"),
        ("import shiboken6", "genviewer.service.foo"),
        ("from genviewer.views import x", "genviewer.service.foo"),
        ("from genviewer import controllers", "genviewer.service.foo"),
        ("from ..views import x", "genviewer.service.foo"),
        ("import genviewer.main", "genviewer.service.foo"),
        ("from genviewer.utils.reporting import report", "genviewer.service.foo"),
        ("from genviewer.utils import background", "genviewer.service.foo"),
        ("def f():\n    from PySide6.QtWidgets import QApplication\n", "genviewer.service.foo"),
    ],
)
def test_scanner_detects_forbidden_imports(source, module):
    assert boundary_violations(source, module)


@pytest.mark.parametrize(
    "source",
    [
        "import logging\nfrom genviewer.service import schema",
        '# import PySide6\nx = "from PySide6 import Qt"\n"""import PySide6"""',
        "from genviewer.utils import logs\nfrom genviewer.utils.logs import scrub",
    ],
)
def test_scanner_ignores_allowed_imports_comments_and_strings(source):
    assert boundary_violations(source, "genviewer.service.foo") == []


def test_scanner_resolves_relative_import_from_package_init():
    # genviewer/service/__init__.py 에서 `from .. import views` 는 genviewer.views 다.
    assert boundary_violations("from .. import views", "genviewer.service", is_package=True) == [
        ("genviewer.views", None)
    ]
    assert boundary_violations("from . import views", "genviewer.service", is_package=True) == []


def test_scanner_reports_enclosing_function():
    source = textwrap.dedent(
        """
        import os

        class Writer:
            import csv

            def write(self):
                import json

        def outer():
            def inner():
                import re
        """
    )
    assert scoped_imports(source, "genviewer.service.foo") == [
        ("os", None),
        ("csv", None),  # 클래스 본문은 import 시점에 돈다
        ("json", "Writer.write"),
        ("re", "outer.inner"),
    ]


@pytest.mark.parametrize(
    ("source", "module", "allowed"),
    [
        ("def root():\n    from genviewer.main import run_gui\n", "genviewer.cli", True),
        ("def root():\n    import genviewer.main\n", "genviewer.cli", True),
        ("from genviewer.main import run_gui\n", "genviewer.cli", False),
        ("import genviewer.main\n", "genviewer.cli", False),
        ("def other():\n    from genviewer.main import run_gui\n", "genviewer.cli", False),
        ("def root():\n    def inner():\n        import genviewer.main\n", "genviewer.cli", False),
        ("def root():\n    from genviewer.views import x\n", "genviewer.cli", False),
        ("def root():\n    import PySide6\n", "genviewer.cli", False),
        ("def root():\n    from genviewer.main import run_gui\n", "genviewer.service.x", False),
    ],
)
def test_cli_root_is_the_only_exception(source, module, allowed):
    assert (boundary_violations(source, module) == []) is allowed


@pytest.mark.parametrize(
    ("name", "outside"),
    [
        ("genviewer.utils.validators", False),
        ("genviewer.utils.validators.normalize_value", False),
        ("genviewer.models.device_table", False),
        ("genviewer.utils", False),  # from genviewer.utils import validators
        ("genviewer", False),  # from genviewer import models
        ("PySide6.QtCore", False),  # genviewer 밖은 이 검사의 대상이 아니다
        ("genviewer.utils.logs", True),
        ("genviewer.views", True),
        ("genviewer.service.errors", True),
    ],
)
def test_layer_scanner_for_models(name, outside):
    assert _outside(name, ("genviewer.models", "genviewer.utils.validators")) is outside


# -- 실제 소스 ----------------------------------------------------------------


def test_qt_free_zone_list_matches_files():
    """목록의 이름이 실제 파일을 가리킨다(오타로 검사가 비지 않게)."""
    files = _qt_free_files()
    assert "genviewer.service.repo.device" in files
    assert "genviewer.scripts.init_db" in files
    assert "genviewer.config.config" in files
    for module in QT_FREE_MODULES:
        path, _ = files[module]
        assert path.is_file(), module


def test_qt_free_sources_have_no_forbidden_imports():
    src = package_dir("genviewer").parent
    violations = [
        f"{path.relative_to(src).as_posix()}: {name} ({scope or '모듈 수준'})"
        for module, (path, is_package) in _qt_free_files().items()
        for name, scope in boundary_violations(
            path.read_text(encoding="utf-8"), module, is_package=is_package
        )
    ]
    assert not violations, "Qt 금지 구역이 금지 모듈을 import 한다:\n" + "\n".join(violations)


def test_cli_root_still_imports_main():
    """예외가 실제로 쓰이는 곳. root 가 이름을 바꾸면 이 예외도 같이 고친다."""
    path, _ = module_path(ALLOWED_MODULE)
    imports = scoped_imports(path.read_text(encoding="utf-8"), ALLOWED_MODULE)
    assert ("genviewer.main", ALLOWED_SCOPE) in imports


RUNTIME_SCRIPT = textwrap.dedent(
    """
    import importlib
    import json
    import pkgutil
    import sys

    spec = json.loads(sys.argv[1])


    def onerror(name):
        raise


    for package in spec["packages"]:
        root = importlib.import_module(package)
        for info in pkgutil.walk_packages(root.__path__, package + ".", onerror=onerror):
            importlib.import_module(info.name)
    for module in spec["modules"]:
        importlib.import_module(module)

    forbidden = spec["forbidden"]
    loaded = sorted(
        m for m in sys.modules if any(m == f or m.startswith(f + ".") for f in forbidden)
    )
    if loaded:
        print("\\n".join(loaded))
        sys.exit(1)
    """
)


def test_importing_qt_free_zone_does_not_load_qt():
    # pytest-qt 가 이 프로세스에 PySide6 를 이미 올렸으므로 새 인터프리터에서 검사한다.
    # genviewer.__main__ 은 `if __name__ == "__main__"` 가드가 있어 import 해도
    # main() 이 돌지 않는다.
    spec = {
        "packages": list(QT_FREE_PACKAGES),
        "modules": list(QT_FREE_MODULES),
        "forbidden": sorted(FORBIDDEN_TOP_LEVEL) + list(FORBIDDEN_MODULES),
    }
    proc = subprocess.run(
        [sys.executable, "-c", RUNTIME_SCRIPT, json.dumps(spec)],
        capture_output=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"


def test_models_import_only_validators_from_genviewer():
    allowed = ("genviewer.models", "genviewer.utils.validators")
    offenders = sorted(
        (path.as_posix(), name)
        for path, name in package_imports("genviewer.models")
        if _outside(name, allowed)
    )
    assert offenders == []


def test_net_is_self_contained():
    # phase 13 이 net/ 을 QTcpSocket 으로 다시 써도 이 규칙은 그대로다.
    offenders = sorted(
        (path.as_posix(), name)
        for path, name in package_imports("genviewer.net")
        if _outside(name, ("genviewer.net",))
    )
    assert offenders == []
