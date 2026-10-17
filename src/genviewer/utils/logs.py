"""파일 로그.

배포본은 tools/deploy.sh 가 만든 런처로 뜨기 때문에 붙어 있는 터미널이 없다.
print 나 트레이스백은 그대로 사라진다. "에러가 났다" 는 연락을 받았을 때 파일
하나만 받으면 되도록, 앱이 도는 동안의 경고와 에러를 사용자 홈에 남긴다.

**비밀번호는 절대 남기지 않는다.** main.py 의 --check-config 가 이미 같은 정책을
따른다. 호출자가 기억해서 가리는 방식은 언젠가 빠뜨리므로 포매터에서 한 번에
훑는다 - 메시지뿐 아니라 트레이스백까지 지나가는 곳이 거기 하나다. psycopg 의
접속 실패 예외에는 conninfo 가 통째로 들어 있어서 이 가드가 실제로 필요하다.
"""

import logging
import os
import re
from contextlib import suppress
from logging.handlers import RotatingFileHandler
from pathlib import Path

# 경로를 바꾸고 싶을 때. 런처는 환경변수를 정하지 않으므로 배포본도 따로 주지
# 않으면 기본 경로를 쓴다.
LOG_ENV = "GENDB_LOG"

DEFAULT_DIR = ".genviewer"
DEFAULT_NAME = "genviewer.log"

MAX_BYTES = 1_000_000
BACKUP_COUNT = 3

_SECRET_PATTERNS = (
    # PGPASSWORD=... 도 이 하나로 걸린다 (끝이 password= 다).
    re.compile(r"(?i)(password\s*=\s*)('[^']*'|\"[^\"]*\"|\S+)"),
    # postgresql://user:secret@host
    re.compile(r"(?i)(://[^:/@\s]+:)([^@/\s]+)(@)"),
)

_MASK = "***"

# 지금 쓰이고 있는 로그 파일. --check-config 가 보여준다.
_active: Path | None = None


def scrub(text: str) -> str:
    """문자열에서 비밀번호로 보이는 것을 가린다."""
    if not text:
        return text
    out = str(text)
    out = _SECRET_PATTERNS[0].sub(lambda m: m.group(1) + _MASK, out)
    out = _SECRET_PATTERNS[1].sub(lambda m: m.group(1) + _MASK + m.group(3), out)
    return out


class ScrubbingFormatter(logging.Formatter):
    """메시지와 트레이스백을 다 만든 **뒤에** 비밀을 지운다."""

    def format(self, record: logging.LogRecord) -> str:
        return scrub(super().format(record))


def log_path() -> Path:
    """쓸 로그 파일 경로. 실제로 열리는지는 보지 않는다."""
    override = os.environ.get(LOG_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / DEFAULT_DIR / DEFAULT_NAME


def active_path() -> Path | None:
    """실제로 열린 로그 파일. 못 열었으면 None."""
    return _active


def setup(level: int = logging.INFO, path: Path | None = None) -> Path | None:
    """로그를 건다. 실패해도 예외를 내지 않는다 - 로그 때문에 앱이 죽으면 안 된다.

    연 파일 경로를 돌려준다. 못 열었으면 None 이고, 그때는 stderr 로만 남는다.
    """
    global _active

    formatter = ScrubbingFormatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    root = logging.getLogger()
    root.setLevel(level)

    # 우리가 붙인 것만 걷어낸다. 두 번 불러도 핸들러가 쌓이지 않고, 테스트나
    # 호스트가 따로 달아둔 핸들러는 건드리지 않는다.
    for handler in list(root.handlers):
        if getattr(handler, "_genviewer", False):
            root.removeHandler(handler)
            handler.close()

    stream = logging.StreamHandler()
    stream.setLevel(logging.WARNING)
    stream.setFormatter(formatter)
    stream._genviewer = True
    root.addHandler(stream)

    target = Path(path) if path is not None else log_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            # 기본 위치(~/.genviewer)일 때만 좁힌다. 남이 내 로그를 읽을 이유가 없다.
            # GENDB_LOG 로 고른 곳(/tmp, 팀 공유 디렉터리)은 내 것이 아닐 수 있어
            # 건드리지 않는다. 권한을 못 좁혔다고 파일 로그까지 끄면 에러가 아무 데도
            # 남지 않으므로 chmod 실패는 넘긴다. 경로를 직접 줬으면 홈을 몰라도 된다.
            with suppress(OSError, RuntimeError):
                if target.parent == Path.home() / DEFAULT_DIR:
                    os.chmod(target.parent, 0o700)
        file_handler = RotatingFileHandler(
            target, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
        )
    except OSError as e:
        _active = None
        root.warning("로그 파일을 열지 못했다 (%s): %s", target, e)
        return None

    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    file_handler._genviewer = True
    root.addHandler(file_handler)
    _active = target
    return target
