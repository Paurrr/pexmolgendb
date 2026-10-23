"""파일 로그와 에러 문장 변환.

DB 도 Qt 도 필요 없다. 배포본에는 터미널이 없어서 print/트레이스백이 아무 데도
남지 않는다는 것이 이 모듈이 존재하는 이유이므로, "파일에 남는다" 와 "비밀번호는
안 남는다" 둘 다 고정한다.
"""

import errno
import logging
import os
from pathlib import Path

import pytest

from genviewer.service.errors import DbUnavailableError, user_message
from genviewer.utils import logs


@pytest.fixture(autouse=True)
def restore_root_logger():
    """setup() 은 루트 로거를 건드린다. 테스트 사이에 새지 않게 되돌린다."""
    root = logging.getLogger()
    before = list(root.handlers)
    level = root.level
    yield
    for handler in list(root.handlers):
        if handler not in before:
            root.removeHandler(handler)
            handler.close()
    for handler in before:
        if handler not in root.handlers:
            root.addHandler(handler)
    root.setLevel(level)
    logs._active = None


# --------------------------------------------------------------------------
# scrub
# --------------------------------------------------------------------------


def test_scrub_hides_a_conninfo_password():
    """psycopg 의 접속 실패 예외에는 conninfo 가 통째로 들어 있다."""
    out = logs.scrub("connection failed: host=db user=me password=s3cr3t dbname=x")
    assert "s3cr3t" not in out
    assert "host=db" in out and "dbname=x" in out


def test_scrub_hides_pgpassword():
    """PGPASSWORD= 도 끝이 password= 라 같은 규칙에 걸린다."""
    assert "s3cr3t" not in logs.scrub("PGPASSWORD=s3cr3t")


def test_scrub_hides_a_password_in_a_url():
    out = logs.scrub("postgresql://me:s3cr3t@db.example:5432/molgen")
    assert "s3cr3t" not in out
    assert "db.example:5432/molgen" in out


def test_scrub_leaves_ordinary_text_alone():
    text = "device 3개를 새로 추가했다."
    assert logs.scrub(text) == text


# --------------------------------------------------------------------------
# setup
# --------------------------------------------------------------------------


def test_log_path_follows_the_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv(logs.LOG_ENV, str(tmp_path / "somewhere.log"))
    assert logs.log_path() == tmp_path / "somewhere.log"


def test_setup_writes_the_message_to_the_file(tmp_path):
    target = tmp_path / "logs" / "genviewer.log"
    assert logs.setup(path=target) == target
    assert logs.active_path() == target

    logging.getLogger("genviewer.test").error("접속 실패 password=s3cr3t")
    for handler in logging.getLogger().handlers:
        handler.flush()

    text = target.read_text(encoding="utf-8")
    assert "접속 실패" in text
    # 포매터에서 가리므로 호출자가 기억하지 않아도 새지 않는다.
    assert "s3cr3t" not in text


def test_setup_scrubs_the_traceback_too(tmp_path):
    """예외 문자열에 비밀이 있으면 트레이스백에도 그대로 실린다."""
    target = tmp_path / "genviewer.log"
    logs.setup(path=target)
    try:
        raise RuntimeError("host=db password=s3cr3t")
    except RuntimeError:
        logging.getLogger("genviewer.test").exception("실패")
    for handler in logging.getLogger().handlers:
        handler.flush()

    text = target.read_text(encoding="utf-8")
    assert "Traceback" in text
    assert "s3cr3t" not in text


def test_setup_survives_a_path_it_cannot_open(tmp_path):
    """로그를 못 열었다고 앱이 죽으면 안 된다."""
    blocker = tmp_path / "blocker"
    blocker.write_text("파일이지 디렉터리가 아니다", encoding="utf-8")

    assert logs.setup(path=blocker / "genviewer.log") is None
    assert logs.active_path() is None
    # stderr 핸들러는 남아 있어야 한다.
    assert any(getattr(h, "_genviewer", False) for h in logging.getLogger().handlers)


def test_setup_twice_does_not_stack_handlers(tmp_path):
    logs.setup(path=tmp_path / "a.log")
    logs.setup(path=tmp_path / "b.log")
    ours = [h for h in logging.getLogger().handlers if getattr(h, "_genviewer", False)]
    assert len(ours) == 2  # stderr 하나 + 파일 하나


# --------------------------------------------------------------------------
# setup - 로그 디렉터리 권한 (리눅스 분기)
# --------------------------------------------------------------------------


class _PosixOs:
    """logs 모듈이 보는 os 만 리눅스처럼 보이게 한다.

    전역 os.name 을 바꾸면 pathlib.Path() 가 PosixPath 를 골라 Windows 에서 터진다.
    name 만 "posix" 이고, chmod 는 실제로 바꾸지 않고 기록하거나 PermissionError 를
    낸다. 나머지는 진짜 os 에 넘긴다.
    """

    name = "posix"

    def __init__(self, real, refuse=False):
        self._real = real
        self._refuse = refuse
        self.chmods = []

    def chmod(self, path, mode):
        self.chmods.append((Path(path), mode))
        if self._refuse:
            # /tmp 처럼 root 가 가진 디렉터리에서 나는 것과 같다.
            raise PermissionError(errno.EPERM, "Operation not permitted", str(path))

    def __getattr__(self, attr):
        return getattr(self._real, attr)


def _pretend_posix(monkeypatch, refuse=False):
    fake = _PosixOs(os, refuse=refuse)
    monkeypatch.setattr(logs, "os", fake)
    return fake


def _setup_at(how, target, monkeypatch):
    """사용자가 로그 위치를 고르는 두 가지 길. main.py 는 인자 없이 부른다."""
    if how == "env":
        monkeypatch.setenv(logs.LOG_ENV, str(target))
        return logs.setup()
    monkeypatch.delenv(logs.LOG_ENV, raising=False)
    return logs.setup(path=target)


def _assert_logged_to(target):
    logging.getLogger("genviewer.test").error("파일에 남아야 한다")
    for handler in logging.getLogger().handlers:
        handler.flush()
    assert "파일에 남아야 한다" in target.read_text(encoding="utf-8")


@pytest.mark.parametrize("how", ["path", "env"])
def test_setup_keeps_the_file_log_when_a_chosen_dir_refuses_chmod(
    how, monkeypatch, tmp_path
):
    """GENDB_LOG=/tmp/genviewer.log 같은 경우. 쓸 수 있는 곳인데 로그가 꺼지면 안 된다."""
    _pretend_posix(monkeypatch, refuse=True)
    target = tmp_path / "elsewhere" / "gv.log"

    assert _setup_at(how, target, monkeypatch) == target
    assert logs.active_path() == target
    _assert_logged_to(target)


@pytest.mark.parametrize("how", ["path", "env"])
def test_setup_leaves_a_chosen_dir_permissions_alone(how, monkeypatch, tmp_path):
    """$HOME/team-logs 같은 공유 디렉터리가 조용히 0700 이 되면 팀원이 못 읽는다."""
    fake = _pretend_posix(monkeypatch)

    _setup_at(how, tmp_path / "team-logs" / "me.log", monkeypatch)
    assert fake.chmods == []


def test_setup_restricts_the_default_dir(monkeypatch, tmp_path):
    """홈 밑의 기본 위치는 지금처럼 0700. 남이 내 로그를 읽을 이유가 없다."""
    fake = _pretend_posix(monkeypatch)
    monkeypatch.setattr(logs.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv(logs.LOG_ENV, raising=False)

    assert logs.setup() == tmp_path / ".genviewer" / "genviewer.log"
    assert fake.chmods == [(tmp_path / ".genviewer", 0o700)]


def test_setup_keeps_the_file_log_when_the_default_chmod_fails(monkeypatch, tmp_path):
    """권한을 못 좁혔다고 파일 로그까지 끄면 에러가 아무 데도 남지 않는다."""
    _pretend_posix(monkeypatch, refuse=True)
    monkeypatch.setattr(logs.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.delenv(logs.LOG_ENV, raising=False)

    target = tmp_path / ".genviewer" / "genviewer.log"
    assert logs.setup() == target
    _assert_logged_to(target)


def test_setup_with_a_chosen_path_does_not_need_a_home(monkeypatch, tmp_path):
    """경로를 직접 주면 지금은 홈을 몰라도 된다. 기본 위치 비교 때문에 죽으면 안 된다."""
    _pretend_posix(monkeypatch)

    def no_home(cls):
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(logs.Path, "home", classmethod(no_home))
    target = tmp_path / "elsewhere" / "gv.log"
    assert _setup_at("path", target, monkeypatch) == target


# --------------------------------------------------------------------------
# user_message
# --------------------------------------------------------------------------


class _FakePgError(Exception):
    """sqlstate 를 가진 psycopg 예외 흉내. psycopg 없이 분기만 본다."""

    def __init__(self, sqlstate, text=""):
        super().__init__(text)
        self.sqlstate = sqlstate


@pytest.mark.parametrize(
    "sqlstate,expected",
    [
        ("57014", "took too long"),  # statement_timeout - pool.py 가 일부러 건다
        ("55P03", "Another user"),  # lock_timeout - 위와 같다
        ("42P01", "genviewer-init-db"),
        ("42501", "permission"),
        ("23505", "already exists"),
    ],
)
def test_user_message_explains_known_sqlstates(sqlstate, expected):
    assert expected in user_message(_FakePgError(sqlstate))


def test_user_message_scrubs_the_detail():
    exc = _FakePgError("28P01", "connection failed: password=s3cr3t")
    assert "s3cr3t" not in user_message(exc)


def test_user_message_never_returns_empty():
    """빈 메시지 박스는 트레이스백보다 나쁘다."""
    assert user_message(ValueError()) == "ValueError"
    assert user_message(RuntimeError("뭔가 잘못됐다")) == "뭔가 잘못됐다"


def test_user_message_handles_db_unavailable():
    assert "Cannot connect" in user_message(DbUnavailableError("서버가 응답하지 않는다"))
