"""Qt 슬롯에서 새는 예외를 화면과 로그로 보낸다.

슬롯에서 예외를 올려보내면 트레이스백이 stderr 로 나간다. 배포본에는 터미널이
없으므로 그것은 **아무 데도 남지 않고**, 사용자는 아무 말도 듣지 못한 채 화면이
안 바뀌는 것만 본다. DB 계층(service/repo/)에는 except 가 거의 없어서 psycopg
예외 대부분이 이 경로를 탄다.

집 안의 알림 방식을 그대로 쓴다: notifyRequested 로 보내면
controllers/main_window.py 가 메시지 박스와 로그 패널에 함께 띄운다. 여기서는
거기에 파일 로그를 더한다.
"""

import functools
import logging

from genviewer.service.errors import StaleWriteError, user_message


def report_error(
    obj, title: str, exc: BaseException, *, logger: logging.Logger | None = None
) -> None:
    """예외 하나를 로그 파일과 화면에 남긴다.

    obj 는 notifyRequested 를 가진 컨트롤러다. 없으면 로그만 남는다 - 알릴 곳이
    없다고 예외를 또 내면 원래 에러가 묻힌다.
    """
    log = logger or logging.getLogger(obj.__class__.__module__)
    log.error("%s", title, exc_info=exc)

    signal = getattr(obj, "notifyRequested", None)
    if signal is None:
        return
    try:
        signal.emit("error", title, user_message(exc))
    except RuntimeError:
        # 창이 이미 닫히는 중이면 C++ 쪽 객체가 사라졌을 수 있다. 로그는 남았다.
        log.debug("알림을 보내지 못했다: %s", title)


def report(title: str):
    """반환값을 쓰지 않는 슬롯에 붙인다.

        @Slot(str)
        @report("Load CSV Failed")
        def on_load_csv_requested(self, path): ...

    Slot 이 바깥에 와야 Qt 가 감싼 함수를 슬롯으로 등록한다.

    StaleWriteError 는 **다시 올려보낸다**. 그것은 에러가 아니라 사용자에게 물어볼
    거리이고, 이미 dialogs/conflict.py 가 다루고 있다. 여기서 잡아버리면 충돌
    다이얼로그가 안 뜬다.

    값을 돌려주는 함수에는 쓰지 말 것. 예외가 나면 None 이 되어 호출자가 분기를
    잘못 탄다. 그런 곳은 report_error() 로 직접 감싼다.
    """

    def decorate(fn):
        logger = logging.getLogger(fn.__module__)

        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            try:
                return fn(self, *args, **kwargs)
            except StaleWriteError:
                raise
            except Exception as exc:
                report_error(self, title, exc, logger=logger)
                return None

        return wrapper

    return decorate
