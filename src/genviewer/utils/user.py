"""앱 사용자 이름.

인증이 아니라 자기 신고다. DB 의 current_user 는 공유 role 이라 귀속에 쓸 수
없으므로, 누가 고쳤는지 보여주려면 앱이 이름을 실어 보내야 한다.
fmserver 의 actor_user 와 같은 태도 — 위조는 못 막고 실수를 막는다.
"""

import getpass
import os

_ENV_ORDER = ("MOLGEN_APP_USER", "USER", "USERNAME", "LOGNAME")


def current_user() -> str:
    for env in _ENV_ORDER:
        value = os.environ.get(env, "").strip()
        if value:
            return value[:64]
    try:
        return getpass.getuser()[:64]
    except Exception:
        return "unknown"
