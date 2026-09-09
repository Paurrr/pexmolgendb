"""관리용 명령줄 도구. GUI 없이 도는 것들이다.

  python -m genviewer.scripts.init_db --dry-run
  python -m genviewer.scripts.import_sqlite --sqlite mine.sqlite --dry-run
"""

import sys


def survive_console_encoding() -> None:
    """콘솔이 못 그리는 글자 때문에 도구가 죽지 않게 한다.

    한국어 Windows 콘솔은 cp949 다. 한글은 멀쩡히 나오지만 em dash 같은
    글자는 인코딩이 안 돼서 print 가 UnicodeEncodeError 로 죽는다 — 출력
    한 줄 때문에 이관 작업이 중단된다. 물음표로 보이는 편이 낫다.

    콘솔 인코딩 자체는 건드리지 않는다. UTF-8 로 바꿔버리면 한글이 전부
    깨져 보인다.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")
