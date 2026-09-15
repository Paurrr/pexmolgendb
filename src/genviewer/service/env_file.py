"""접속 설정 파일(genviewer.env)을 찾아 환경변수로 넣는다.

매번 손으로 치지 않게 하려는 것이다:

    export PGHOST=10.1.2.3 PGPORT=55433 PGDATABASE=molgen PGUSER=molgen_app

서버 주소가 바뀌면 모든 사람이 각자 고쳐야 하고, 오타 하나면 접속이 안 된다.

개인 파일(~/.genviewer.env)뿐 아니라 **설치 디렉터리**도 본다. 그래야 자기 홈에
아무것도 안 만든 사람이 그냥 실행해도 붙는다. 여러 사람이 쓰는 배포에서는 그쪽이
기본값이고, 개인 파일은 그걸 덮어쓰는 용도다.

형식은 .env 다 - KEY=VALUE 한 줄씩. **키는 libpq 이름 그대로** 쓴다:

    PGHOST=10.1.2.3
    PGPORT=55433
    PGDATABASE=molgen
    PGUSER=molgen_app
    PGPASSWORD=...

그래서 새로 외울 키 이름이 없고, DSN 문자열을 조립할 필요도 없다. libpq 가
환경변수에서 알아서 접속 정보를 만든다. GENDB_PG_DSN 한 줄로 적어도 되고,
PGSERVICE 로 ~/.pg_service.conf 에 미룰 수도 있다.

비밀번호가 같은 파일에 들어가므로 권한을 확인한다(check_permissions). libpq 는
~/.pgpass 는 검사해 주지만 이 파일은 자기 것이 아니라서 봐주지 않는다.

여기서는 접속하지 않는다. 환경변수만 채운다.
"""

from __future__ import annotations

import os
import re
import stat
import sys
from pathlib import Path

# 설치 디렉터리에 두는 이름. 배포처마다 값이 다르므로 저장소에는 .example 만 둔다.
SITE_NAME = "genviewer.env"

# 개인 설정. 설치 디렉터리의 공통 값을 덮어쓴다.
USER_ENV = Path.home() / f".{SITE_NAME}"

# 이 키가 들어 있으면 파일에 비밀이 있다고 보고 권한을 확인한다.
SECRET_KEYS = frozenset({"PGPASSWORD"})

# 이것 중 하나라도 있으면 libpq 가 접속 정보를 만들 수 있다.
LIBPQ_KEYS = ("PGSERVICE", "PGHOST", "PGHOSTADDR", "PGDATABASE", "PGUSER")

_KEY = re.compile("[A-Za-z_][A-Za-z0-9_]*")


def parse(text: str) -> dict[str, str]:
    """.env 본문을 읽는다. 규칙은 일부러 적다.

    - 주석은 **줄 전체**만 (# 로 시작). 값 뒤의 # 는 값의 일부다.
      비밀번호에 # 가 들어가는 일이 흔해서 이렇게 했다.
    - 변수 치환($FOO) 없음, 여러 줄 값 없음.
    - 값을 감싼 따옴표 한 쌍은 벗긴다. 앞뒤 공백을 살리고 싶을 때 쓴다.

    형식이 틀린 줄은 조용히 넘기지 않고 알린다. 조용히 넘기면 "왜 이 값이 안
    먹지" 로 시간을 버린다.
    """
    values: dict[str, str] = {}
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()

        key, sep, value = line.partition("=")
        if not sep:
            raise ValueError(f"{lineno}행: KEY=VALUE 형식이 아니다: {line!r}")
        key = key.strip()
        if not _KEY.fullmatch(key):
            raise ValueError(f"{lineno}행: 키 이름으로 쓸 수 없다: {key!r}")
        values[key] = _unquote(value.strip())
    return values


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def _site_roots() -> list[Path]:
    """설치 디렉터리 후보. 배포 형태가 하나가 아니라 몇 군데를 본다.

    - sys.prefix: venv 루트 (.venv/genviewer.env)
    - sys.prefix 의 부모: uv 레이아웃의 배포 루트 (<루트>/.venv 이므로)
    - 패키지에서 세 단계 위: src 레이아웃으로 직접 돌릴 때의 저장소 루트

    tools/deploy.sh 로 설치한 배포본은 <ROOT>/venv 가 sys.prefix 라서 그 부모인
    <ROOT>/genviewer.env 가 두 번째 후보로 걸린다. 그래도 런처는 GENDB_CONFIG 를
    명시해서 넘긴다 - 추측이 하나라도 적은 편이 낫다.
    """
    prefix = Path(sys.prefix)
    roots = [prefix, prefix.parent]

    # src/genviewer/service/env_file.py -> src/genviewer -> src -> 저장소 루트.
    # pyproject.toml 이 있을 때만 넣는다. 배포본은 비-editable 설치라 같은 계산이
    # site-packages 두 단계 위(venv/lib/python3.13)라는 엉뚱한 경로를 내놓는데,
    # 그게 '찾아본 곳' 목록에 뜨면 읽는 사람이 거기 두라는 줄 안다.
    checkout = Path(__file__).resolve().parents[3]
    if (checkout / "pyproject.toml").is_file():
        roots.append(checkout)
    return roots


def candidates(explicit: str = "") -> list[Path]:
    """찾아볼 경로를 순서대로. 먼저 찾은 것이 이긴다.

    explicit 은 GENDB_CONFIG 다. 주어지면 그것만 본다 - 가리켰는데 조용히 다른
    파일이 쓰이면 디버깅이 불가능해진다.
    """
    if explicit:
        return [Path(explicit)]

    paths = [USER_ENV]
    paths.extend(root / SITE_NAME for root in _site_roots())

    # 후보가 겹칠 수 있다 (sys.prefix 의 부모가 저장소 루트와 같은 경우 등).
    # 에러 메시지에 같은 줄이 두 번 나오지 않게 순서를 지키며 중복만 없앤다.
    seen: set[str] = set()
    unique: list[Path] = []
    for p in paths:
        key = str(p)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def check_permissions(path: Path, values: dict[str, str]) -> None:
    """비밀이 든 파일을 아무나 읽을 수 있으면 거부한다.

    group 읽기는 막지 않는다 - 팀이 같이 쓰는 배포 디렉터리에 두는 것이 이 파일의
    용도라서, 그걸 막으면 기능 자체가 없어진다. other 읽기만 본다.

    비밀이 없는 파일은 644 여도 그냥 둔다. 서버 주소는 비밀이 아니다.

    윈도우에서는 검사하지 않는다. NTFS 위에서 stat 이 실제 ACL 과 무관한 값을
    돌려줘서, 검사를 걸면 멀쩡한 파일을 무조건 거부하게 된다.
    """
    if os.name == "nt":
        return
    if not (SECRET_KEYS & set(values)):
        return
    if path.stat().st_mode & stat.S_IROTH:
        raise RuntimeError(
            f"{path} 에 비밀번호가 있는데 모두가 읽을 수 있다.\n"
            f"  chmod 640 {path}"
        )


def libpq_env_present() -> bool:
    """libpq 가 접속 정보를 만들 수 있는 상태인가."""
    return any(os.environ.get(key, "").strip() for key in LIBPQ_KEYS)


def load(explicit: str = "") -> tuple[Path | None, list[Path]]:
    """첫 번째로 찾은 파일을 환경변수에 넣는다. (쓴 파일, 찾아본 경로들).

    **이미 있는 환경변수는 덮지 않는다.** PGPASSWORD=x genviewer 처럼 한 번만
    다르게 주는 것이 되어야 한다.

    여러 파일을 겹쳐 읽지 않는다. 값이 어디서 왔는지 추적할 수 없게 된다.
    """
    searched = candidates(explicit)
    for path in searched:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            raise RuntimeError(f"설정 파일을 읽을 수 없다: {path}\n  {e}") from e
        except UnicodeDecodeError as e:
            # 한국어 윈도우에서 메모장이 cp949 로 저장한 경우가 대부분이다.
            raise RuntimeError(
                f"설정 파일이 UTF-8 이 아니다: {path}\n  {e}"
            ) from e

        try:
            values = parse(text)
        except ValueError as e:
            raise RuntimeError(f"{path}\n  {e}") from e

        if not values:
            continue

        check_permissions(path, values)
        for key, value in values.items():
            os.environ.setdefault(key, value)
        return path, searched

    return None, searched
