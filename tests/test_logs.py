"""파일 로그와 에러 문장 변환.

DB 도 Qt 도 필요 없다. 배포본에는 터미널이 없어서 print/트레이스백이 아무 데도
남지 않는다는 것이 이 모듈이 존재하는 이유이므로, "파일에 남는다" 와 "비밀번호는
안 남는다" 둘 다 고정한다.
"""

import logging

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
        ("57014", "오래 걸려"),  # statement_timeout - pool.py 가 일부러 건다
        ("55P03", "다른 사용자"),  # lock_timeout - 위와 같다
        ("42P01", "genviewer-init-db"),
        ("42501", "권한"),
        ("23505", "이미 있다"),
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
    assert "접속" in user_message(DbUnavailableError("서버가 응답하지 않는다"))
