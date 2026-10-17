"""tools/deploy.sh - 태그를 공유 디렉터리에 설치하는 부분.

네트워크도 진짜 uv 도 쓰지 않는다. tmp 에 진짜 git 저장소를 만들어 태그를 달고,
PATH 앞에 가짜 uv 를 놓아 venv 처럼 보이는 것을 만들게 한다. 검증 대상은 의존성
설치가 아니라 **스크립트가 디렉터리를 어떻게 바꾸는가** 다.

윈도우(Git Bash)에서도 대부분 돌지만, NTFS 위에서 chmod 와 ln -s 가 실제 의미를
갖지 않으므로 그 두 가지에 기대는 항목은 건너뛴다. 배포 대상은 리눅스다.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DEPLOY = REPO / "tools" / "deploy.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("sh") is None or shutil.which("git") is None,
    reason="sh 나 git 이 없다",
)

posix_only = pytest.mark.skipif(
    sys.platform == "win32",
    reason="윈도우에서는 chmod / ln -s 가 실제 의미를 갖지 않는다",
)

# 가짜 uv. 받은 인자를 기록하고, deploy.sh 가 기대하는 모양의 venv 를 만든다.
# 중첩 heredoc 을 피하려고 printf 로 찍는다.
UV_STUB = """#!/bin/sh
set -e
{
  echo "ARGS: $*"
  echo "ENV: ${UV_PROJECT_ENVIRONMENT:-(없음)}"
} >> "$STUB_RECORD"

venv=${UV_PROJECT_ENVIRONMENT:-}
[ -n "$venv" ] || { echo "stub uv: UV_PROJECT_ENVIRONMENT 가 없다" >&2; exit 1; }
mkdir -p "$venv/bin"

# deploy.sh 는 이 python 으로 두 가지를 묻는다: 패키지 이름, 그리고 console_scripts.
printf '%s\\n' \\
  '#!/bin/sh' \\
  'case "$*" in' \\
  '  *pyproject.toml*) echo genviewer ;;' \\
  '  *) echo "${STUB_COMMANDS:-genviewer}" ;;' \\
  'esac' > "$venv/bin/python"
chmod 755 "$venv/bin/python"

for c in ${STUB_COMMANDS:-genviewer}; do
    printf '%s\\n' '#!/bin/sh' 'exit 0' > "$venv/bin/$c"
    chmod 755 "$venv/bin/$c"
done
"""


@pytest.fixture
def source_repo(tmp_path):
    """태그 둘과 브랜치 하나가 있는 진짜 저장소."""
    src = tmp_path / "source"
    src.mkdir()
    (src / "pyproject.toml").write_text(
        '[project]\nname = "genviewer"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (src / "genviewer.env.example").write_text("PGHOST=example\n", encoding="utf-8")

    def git(*args):
        subprocess.run(["git", "-C", str(src), *args], check=True, capture_output=True)

    def commit(message):
        git("add", "-A")
        git(
            "-c", "user.name=test",
            "-c", "user.email=test@example.invalid",
            "commit", "-q", "-m", message,
        )

    git("init", "-q", "-b", "main")
    commit("first")
    git("tag", "v1.0.0")
    # 태그마다 커밋이 달라야 한다. 같은 커밋에 둘을 달면
    # describe --exact-match 가 어느 쪽을 돌려줄지 알 수 없어 검증이 무의미해진다.
    (src / "marker.txt").write_text("v1.1.0\n", encoding="utf-8")
    commit("second")
    git("tag", "v1.1.0")
    return src


@pytest.fixture
def stub(tmp_path):
    """PATH 앞에 놓을 가짜 uv 와, 그것이 남기는 기록."""
    bindir = tmp_path / "stub_bin"
    bindir.mkdir()
    path = bindir / "uv"
    path.write_text(UV_STUB, encoding="utf-8", newline="\n")
    path.chmod(0o755)
    return {"bindir": bindir, "record": tmp_path / "uv_record.txt"}


# 가짜 chmod. 호출 하나를 인자를 '|' 로 이은 한 줄로 남기고 진짜 chmod 에 넘긴다.
# 진짜를 부르므로 배포는 끝까지 돈다.
CHMOD_STUB = """#!/bin/sh
(IFS='|'; printf '%s\\n' "$*") >> "$CHMOD_RECORD"
exec "$REAL_CHMOD" "$@"
"""


@pytest.fixture
def chmod_record(stub, tmp_path):
    """stub 옆(PATH 앞)에 chmod 기록기를 놓고, deploy() 에 넘길 환경변수를 준다.

    stub 에 넣지 않는 이유: 그러면 CHMOD_RECORD 를 넘기지 않는 다른 테스트가 모두 깨진다.
    진짜 chmod 의 경로는 PATH 를 바꾸기 전에 얻는다(Git Bash 는 /usr/bin/chmod).
    """
    real = subprocess.run(
        ["sh", "-c", "command -v chmod"], capture_output=True, text=True, check=True,
    ).stdout.strip()
    path = stub["bindir"] / "chmod"
    path.write_text(CHMOD_STUB, encoding="utf-8", newline="\n")
    path.chmod(0o755)
    return {"CHMOD_RECORD": tmp_path / "chmod_record.txt", "REAL_CHMOD": real}


def chmod_calls(chmod_record):
    """가짜 chmod 가 받은 인자 목록, 호출 하나에 하나."""
    record = chmod_record["CHMOD_RECORD"]
    if not record.exists():
        return []
    return [ln.split("|") for ln in record.read_text(encoding="utf-8").splitlines()]


def bundle_python(root):
    """README 가 시키는 대로 <ROOT>/python 아래에 uv 관리 CPython 이 있는 것처럼 만든다."""
    interp = root / "python" / "cpython-3.13-test" / "bin" / "python3.13"
    interp.parent.mkdir(parents=True)
    interp.write_text("", encoding="utf-8")
    return interp


@pytest.fixture
def root(tmp_path):
    return tmp_path / "deployed"


def deploy(root, source_repo, stub, tag="v1.0.0", with_url=True, **env):
    """deploy.sh 를 돌리고 CompletedProcess 를 준다."""
    environ = dict(os.environ)
    for key in list(environ):
        if key.startswith(("DEPLOY_", "GENDB_", "PG")):
            environ.pop(key)
    environ["PATH"] = str(stub["bindir"]) + os.pathsep + environ["PATH"]
    environ["STUB_RECORD"] = str(stub["record"])
    environ.setdefault("STUB_COMMANDS", "genviewer genviewer-init-db")
    environ.update({k: str(v) for k, v in env.items()})

    argv = ["sh", str(DEPLOY), str(root), tag]
    if with_url:
        argv.append(str(source_repo))
    return subprocess.run(
        argv, capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=environ,
    )


def run_launcher(root, **env):
    """배포가 만든 런처를 실행하고 CompletedProcess 를 준다.

    환경은 deploy() 처럼 비우고 주어진 값만 더한다. 개발자 셸의 GENDB_CONFIG 가
    섞이면 런처가 무엇을 넘기는지 볼 수 없다.
    """
    environ = dict(os.environ)
    for key in list(environ):
        if key.startswith(("DEPLOY_", "GENDB_", "PG")):
            environ.pop(key)
    environ.update({k: str(v) for k, v in env.items()})
    return subprocess.run(
        ["sh", str(root / "bin" / "genviewer")], capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=environ,
    )


def echo_config_interpreter(root):
    """venv 의 python 을 넘겨받은 GENDB_CONFIG 를 찍는 셸 스크립트로 바꾼다.

    런처가 [ -x .../venv/bin/python ] 로 확인하므로 실행 비트를 준다. Git Bash 는
    #! 로 시작하는 파일을 실행 가능으로 본다.
    """
    python = root / "venv" / "bin" / "python"
    python.write_text(
        '#!/bin/sh\necho "GENDB_CONFIG=${GENDB_CONFIG-unset}"\n',
        encoding="utf-8", newline="\n",
    )
    python.chmod(0o755)


def pinned_tag(root):
    out = subprocess.run(
        ["git", "-C", str(root / "src"), "describe", "--exact-match", "--tags", "HEAD"],
        capture_output=True, text=True,
    )
    return out.stdout.strip()


def uv_calls(stub):
    """가짜 uv 가 받은 인자 목록, 호출 하나에 하나."""
    record = stub["record"].read_text(encoding="utf-8")
    return [ln.split() for ln in record.splitlines() if ln.startswith("ARGS:")]


# --------------------------------------------------------------------------
# 무엇을 받아오는가
# --------------------------------------------------------------------------


def test_a_tag_pins_the_checkout(root, source_repo, stub):
    result = deploy(root, source_repo, stub, tag="v1.0.0")

    assert result.returncode == 0, result.stderr
    assert pinned_tag(root) == "v1.0.0"


def test_a_branch_name_is_refused(root, source_repo, stub):
    """브랜치에 고정하면 '이 태그 배포본' 이 나중에 다른 커밋이 된다.

    refs/tags/ 를 명시하는 것만으로 막힌다 - refs/tags/main 은 없다.
    """
    result = deploy(root, source_repo, stub, tag="main")

    assert result.returncode != 0
    assert pinned_tag(root) != "main"


def test_upgrading_does_not_need_the_url_again(root, source_repo, stub):
    deploy(root, source_repo, stub, tag="v1.0.0")

    result = deploy(root, source_repo, stub, tag="v1.1.0", with_url=False)

    assert result.returncode == 0, result.stderr
    assert pinned_tag(root) == "v1.1.0"


# --------------------------------------------------------------------------
# 어떻게 설치하는가
# --------------------------------------------------------------------------


def test_uv_is_asked_for_a_locked_non_editable_install(root, source_repo, stub):
    """--locked 는 lock 이 pyproject 와 맞는지 검사하고 그대로 재현,
    --no-editable 은 src 가 실행에 관여하지 않게.

    --frozen 은 검사 없이 lock 을 쓴다. pyproject 에만 더한 의존성이 말없이 빠진다.
    """
    deploy(root, source_repo, stub)

    record = stub["record"].read_text(encoding="utf-8")

    calls = uv_calls(stub)
    assert calls, record
    for args in calls:
        assert "--locked" in args, args
        assert "--frozen" not in args, args
    assert "--no-editable" in record
    assert "--no-dev" in record

    # venv 는 프로젝트 안(src/.venv)이 아니라 배포 루트에 놓여야 한다.
    # Git Bash 는 /tmp/... 를, 파이썬은 C:\... 를 보므로 경로 전체는 비교할 수 없다.
    env_line = [ln for ln in record.splitlines() if ln.startswith("ENV:")][0]
    assert env_line.endswith(f"/{root.name}/venv"), env_line


def test_deploy_python_is_passed_through(root, source_repo, stub):
    """경고만 하고 고칠 수단이 없으면 소용이 없다."""
    deploy(root, source_repo, stub, DEPLOY_PYTHON="/usr/bin/python3.13")

    assert "--python /usr/bin/python3.13" in stub["record"].read_text(encoding="utf-8")
    # uv sync 호출이 두 곳이다. 이 분기도 lock 을 검사해야 한다.
    calls = uv_calls(stub)
    assert calls
    for args in calls:
        assert "--locked" in args, args
        assert "--frozen" not in args, args


# --------------------------------------------------------------------------
# 런처
# --------------------------------------------------------------------------


def test_one_launcher_per_command(root, source_repo, stub):
    deploy(root, source_repo, stub)

    names = sorted(p.name for p in (root / "bin").iterdir())
    assert names == ["genviewer", "genviewer-init-db"]


def test_a_launcher_runs_the_venv_interpreter(root, source_repo, stub):
    """사용자에게 uv 나 자기 파이썬을 요구하지 않는 것이 이 런처의 요점이다."""
    deploy(root, source_repo, stub)

    text = (root / "bin" / "genviewer").read_text(encoding="utf-8")

    assert text.startswith("#!/bin/sh")
    exec_line = text.split("exec ", 1)[1]
    assert "/venv/bin/python" in exec_line
    assert "uv" not in exec_line, "실행 줄이 uv 를 부르고 있다"
    assert "\r" not in text, "CRLF shebang 은 리눅스에서 bad interpreter 가 된다"


def test_a_launcher_does_not_choose_the_config_file(root, source_repo, stub):
    """런처가 GENDB_CONFIG 를 정하면 앱은 그 파일만 보고 ~/.genviewer.env 를 건너뛴다.

    정하지 않아도 공용 파일은 찾는다 - 앱이 sys.prefix(<ROOT>/venv) 의 부모를 본다.
    """
    deploy(root, source_repo, stub)
    echo_config_interpreter(root)

    result = run_launcher(root)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "GENDB_CONFIG=unset"


def test_a_launcher_passes_the_users_config_through(root, source_repo, stub):
    """사용자가 셸에서 정한 값은 그대로 앱에 닿아야 한다."""
    deploy(root, source_repo, stub)
    echo_config_interpreter(root)

    result = run_launcher(root, GENDB_CONFIG="/x")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "GENDB_CONFIG=/x"


def test_a_renamed_command_leaves_no_stale_launcher(root, source_repo, stub):
    """없어진 진입점을 가리키는 런처가 남으면 '있는데 안 되는' 명령이 된다."""
    deploy(root, source_repo, stub, STUB_COMMANDS="genviewer genviewer-old")
    site_own = root / "bin" / "site-script"
    site_own.write_text("#!/bin/sh\n", encoding="utf-8")

    deploy(root, source_repo, stub, STUB_COMMANDS="genviewer")

    names = sorted(p.name for p in (root / "bin").iterdir())
    assert names == ["genviewer", "site-script"], "남의 파일을 지웠거나 옛것을 남겼다"


def test_deploy_commands_overrides_discovery(root, source_repo, stub):
    deploy(root, source_repo, stub, DEPLOY_COMMANDS="genviewer")

    assert [p.name for p in (root / "bin").iterdir()] == ["genviewer"]


# --------------------------------------------------------------------------
# 설정 파일 - 업그레이드해도 살아남아야 하고, 남에게 읽히면 안 된다
# --------------------------------------------------------------------------


def test_the_config_is_seeded_from_the_example(root, source_repo, stub):
    deploy(root, source_repo, stub)

    assert (root / "genviewer.env").read_text(encoding="utf-8") == "PGHOST=example\n"


def test_an_existing_config_survives_an_upgrade(root, source_repo, stub):
    """설정이 버전 바깥에 있다는 것이 이 레이아웃의 요점이다."""
    deploy(root, source_repo, stub, tag="v1.0.0")
    (root / "genviewer.env").write_text("PGHOST=우리서버\n", encoding="utf-8")

    deploy(root, source_repo, stub, tag="v1.1.0", with_url=False)

    assert (root / "genviewer.env").read_text(encoding="utf-8") == "PGHOST=우리서버\n"


@posix_only
def test_the_config_is_not_opened_up_by_the_chmod(root, source_repo, stub):
    """스크립트는 트리를 a+rX 로 연다. 이 파일만은 빠져야 한다.

    PGPASSWORD 가 들어 있어서, 아무나 읽게 되면 앱이 스스로 실행을 거부한다.
    """
    deploy(root, source_repo, stub)

    mode = (root / "genviewer.env").stat().st_mode
    assert not mode & 0o004, "설정 파일이 모두에게 읽힌다"
    # 대신 bin/ 은 열려 있어야 다른 사용자가 쓸 수 있다.
    assert (root / "bin" / "genviewer").stat().st_mode & 0o004


@posix_only
def test_the_tree_is_readable_by_others(root, source_repo, stub):
    deploy(root, source_repo, stub)

    for path in (root, root / "bin", root / "src", root / "venv"):
        assert path.stat().st_mode & 0o005, f"{path} 에 다른 사용자가 못 들어간다"


# --------------------------------------------------------------------------
# <ROOT>/python - 확인 절 경고가 uv 관리 CPython 을 두라고 시키는 곳
# --------------------------------------------------------------------------


def test_the_bundled_python_is_opened_up(root, source_repo, stub, chmod_record):
    """venv 의 bin/python 이 <ROOT>/python 안을 가리킨다.

    umask 가 027 이면 uv 가 만든 그 디렉터리에 other 권한이 없어서 다른 사용자는
    인터프리터에서 Permission denied 를 본다. 배포한 사람으로 도는 마지막 확인은
    그것을 보지 못하므로 스크립트가 열어야 한다.
    """
    bundle_python(root)

    result = deploy(root, source_repo, stub, **chmod_record)

    assert result.returncode == 0, result.stderr
    calls = chmod_calls(chmod_record)
    # Git Bash 는 /tmp/... 를, 파이썬은 C:\... 를 보므로 끝부분만 비교한다.
    opened = [
        args for args in calls
        if "-R" in args and "a+rX" in args
        and any(a.endswith(f"/{root.name}/python") for a in args)
    ]
    assert opened, calls


def test_opening_the_python_does_not_open_the_config(
    root, source_repo, stub, chmod_record
):
    """루트를 재귀로 열면 genviewer.env(PGPASSWORD) 가 열리고, 앱이 전원 실행을 거부한다."""
    bundle_python(root)

    result = deploy(root, source_repo, stub, **chmod_record)

    assert result.returncode == 0, result.stderr
    calls = chmod_calls(chmod_record)
    on_config = [args for args in calls if any(a.endswith("genviewer.env") for a in args)]
    assert on_config, calls
    assert all(args[0] == "640" for args in on_config), on_config
    recursive = [args for args in calls if "-R" in args]
    assert recursive, calls
    for args in recursive:
        assert not any(a.rstrip("/.").endswith(f"/{root.name}") for a in args), args


def test_without_a_bundled_python_nothing_more_is_chmodded(
    root, source_repo, stub, chmod_record
):
    """시스템 파이썬을 쓰는 배포가 정상 경로다. 없는 경로를 chmod 하면 set -e 로 죽는다."""
    result = deploy(root, source_repo, stub, **chmod_record)

    assert result.returncode == 0, result.stderr
    calls = chmod_calls(chmod_record)
    assert calls, "chmod 기록기가 끼어 있지 않다"
    # 가짜 uv 의 chmod 755 .../venv/bin/python 도 /python 으로 끝나므로 루트 이름까지 본다.
    touched = [
        args for args in calls
        if any(a.endswith(f"/{root.name}/python") for a in args)
    ]
    assert not touched, touched


@posix_only
def test_the_bundled_python_is_executable_by_others(root, source_repo, stub):
    """umask 027 로 깔린 것처럼 0750 / 0700 을 만들어 두고 실제 권한을 본다."""
    interp = bundle_python(root)
    dirs = [root / "python", interp.parent.parent, interp.parent]
    interp.chmod(0o700)
    for d in dirs:
        d.chmod(0o750)

    result = deploy(root, source_repo, stub)

    assert result.returncode == 0, result.stderr
    for path in [*dirs, interp]:
        assert (path.stat().st_mode & 0o005) == 0o005, f"{path} 를 다른 사용자가 못 쓴다"
    assert ((root / "genviewer.env").stat().st_mode & 0o004) == 0, "설정 파일이 모두에게 읽힌다"


# --------------------------------------------------------------------------
# PATH 에 이미 있는 디렉터리로 링크
# --------------------------------------------------------------------------


@posix_only
def test_link_dir_exposes_the_commands(root, source_repo, stub, tmp_path):
    link_dir = tmp_path / "usr_local_bin"
    link_dir.mkdir()

    result = deploy(root, source_repo, stub, DEPLOY_LINK_DIR=str(link_dir))

    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in link_dir.iterdir()) == [
        "genviewer",
        "genviewer-init-db",
    ]
    assert (link_dir / "genviewer").is_symlink()


@posix_only
def test_link_dir_refuses_to_clobber_someone_elses_file(
    root, source_repo, stub, tmp_path
):
    link_dir = tmp_path / "usr_local_bin"
    link_dir.mkdir()
    (link_dir / "genviewer").write_text("남의 것\n", encoding="utf-8")

    result = deploy(root, source_repo, stub, DEPLOY_LINK_DIR=str(link_dir))

    assert result.returncode != 0
    assert (link_dir / "genviewer").read_text(encoding="utf-8") == "남의 것\n"


@posix_only
def test_link_dir_cleans_up_only_its_own_links(root, source_repo, stub, tmp_path):
    link_dir = tmp_path / "usr_local_bin"
    link_dir.mkdir()
    deploy(
        root, source_repo, stub,
        STUB_COMMANDS="genviewer genviewer-old",
        DEPLOY_LINK_DIR=str(link_dir),
    )
    (link_dir / "unrelated").write_text("사이트 것\n", encoding="utf-8")

    deploy(
        root, source_repo, stub,
        STUB_COMMANDS="genviewer",
        with_url=False,
        DEPLOY_LINK_DIR=str(link_dir),
    )

    assert sorted(p.name for p in link_dir.iterdir()) == ["genviewer", "unrelated"]
