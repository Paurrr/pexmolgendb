"""명령줄 도구.

  genviewer                        창을 띄운다
  genviewer status                 설정과 접속 상태
  genviewer processes              process 목록
  genviewer load <csv>             CSV 를 불러온다
  genviewer export <process> <파일>  process 하나를 파일로 낸다

숨은 것 둘 - 도움말에 나오지 않는다. 평소에 눈에 띄지 않게 해 달라는
요청이라 감춘 것이지 보안 장치가 아니다.

  genviewer log                    누가 언제 무엇을 바꿨는지
  genviewer --history              창에 이력 화면을 붙여서 띄운다

device 를 더하거나 지우는 것, 탭 내용을 고치는 것은 **창에서만** 한다. 그쪽은
낙관적 잠금과 충돌 해결이 얽혀 있어서 명령줄로 흉내 내면 둘 중 하나는 거짓말이
된다.

Pexorche/cli.py 와 같은 구조다 - 여기는 배선만 하고 판단은 service/ 가 한다.
**PySide6 를 모듈 수준에서 import 하지 않는다.** 창을 띄우는 경로에서만 늦게
가져온다. 그래야 X 도 없는 서버에서 status 가 돌고, 배포 스크립트의 --help
연기 시험이 Qt 를 통째로 올리지 않는다.
"""

import errno
import json
import os
import re
import sys
import time
import traceback
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated

import typer

from genviewer.scripts import survive_console_encoding
from genviewer.service import diagnostics
from genviewer.service.config import DSN_ENV, load_config
from genviewer.service.errors import user_message
from genviewer.service.pool import Database
from genviewer.service.repo import audit
from genviewer.service.repo.audit import AuditRepository
from genviewer.service.repo.device import DeviceRepository
from genviewer.service.repo.io import IORepository
from genviewer.service.repo.process import ProcessRepository
from genviewer.utils.exporter import write_csv, write_xlsx
from genviewer.utils.user import current_user

_TIMEOUT_ENV = "GENDB_PG_STATEMENT_TIMEOUT_MS"

# --verbose 를 봤는지. 예외를 문장으로 줄일지 트레이스백을 통째로 낼지 가른다.
_verbose = False

DsnOpt = Annotated[
    str,
    typer.Option(
        "--dsn",
        help=f"PostgreSQL 접속 문자열. 없으면 {DSN_ENV} 환경변수와 설정 파일을 본다.",
    ),
]

app = typer.Typer(
    add_completion=False,
    pretty_exceptions_enable=False,
    # rich 로 그리지 않는다. 한국어 Windows 콘솔은 cp949 라 rich 의 도움말
    # 상자(U+2500 대)를 인코딩하지 못한다. None 이면 평문으로 떨어진다.
    rich_markup_mode=None,
    # argparse 가 주던 -h 를 그대로 유지한다.
    context_settings={"help_option_names": ["-h", "--help"]},
    help="genMOLDB device 데이터베이스 편집기. 서브커맨드 없이 부르면 창을 띄운다.",
)


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    dsn: DsnOpt = "",
    host: Annotated[
        str, typer.Option("--host", help="Virtuoso 소켓 호스트 이름. 데이터베이스가 아니다.")
    ] = "",
    check_config: Annotated[
        bool,
        typer.Option(
            "--check-config",
            help="어느 설정 파일이 쓰이고 무슨 값이 적용되는지 보여주고 끝낸다.",
        ),
    ] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="실패했을 때 트레이스백까지 보여준다.")
    ] = False,
    history: Annotated[
        bool,
        typer.Option(
            "--history",
            # 평소에는 눈에 띄지 않는다. 이력 화면은 이 옵션으로 띄울 때만
            # 왼쪽 목록에 나타나고, 그냥 genviewer 로 띄우면 항목 자체가 없다.
            hidden=True,
        ),
    ] = False,
) -> None:
    global _verbose
    _verbose = verbose
    # 서브커맨드도 --dsn 을 받는다. 자기 값이 없으면 여기 것을 쓴다.
    ctx.obj = dsn

    if check_config:
        raise typer.Exit(_print_config())

    if ctx.invoked_subcommand is not None:
        return

    # 여기서부터 Qt 다. import 자체를 늦춘다.
    from genviewer.main import run_gui

    raise typer.Exit(run_gui(dsn, host, history=history))


# ---------------------------------------------------------------------------
# 공통
# ---------------------------------------------------------------------------


def _print_config() -> int:
    try:
        info = diagnostics.inspect_config()
    except RuntimeError as e:
        typer.echo(f"설정 파일 오류: {e}", err=True)
        return 1

    for line in diagnostics.config_lines(info):
        typer.echo(line)
    if info.has_connection_info:
        return 0
    typer.echo("접속 정보가 없다. 위 경로 중 한 곳에 설정 파일을 둘 것.", err=True)
    return 1


def _open(ctx: typer.Context, dsn: str, *, statement_timeout_ms: int | None = None) -> Database:
    """설정을 읽고 풀을 연다. 실패는 그대로 올려보낸다 - main() 이 문장으로 바꾼다.

    controllers/device_tab.py 의 _open_database 와 같은 몸통이되 run_blocking 이
    없다. 그쪽은 GUI 스레드를 막지 않으려는 것이고 여기는 막을 스레드가 없다.
    """
    cfg = load_config(dsn or (ctx.obj or ""))
    if statement_timeout_ms is not None and not os.environ.get(_TIMEOUT_ENV, "").strip():
        cfg = replace(cfg, statement_timeout_ms=statement_timeout_ms)
    db = Database(cfg)
    db.open()
    return db


# ---------------------------------------------------------------------------
# 명령
# ---------------------------------------------------------------------------


@app.command()
def status(ctx: typer.Context, dsn: DsnOpt = "") -> None:
    """설정과 접속 상태를 보여준다."""
    try:
        info = diagnostics.inspect_config()
    except RuntimeError as e:
        typer.echo(f"설정 파일 오류: {e}", err=True)
        raise typer.Exit(1) from None

    for line in diagnostics.config_lines(info):
        typer.echo(line)

    override = dsn or (ctx.obj or "")
    if not info.has_connection_info and not override:
        typer.echo("접속 정보가 없다. 위 경로 중 한 곳에 설정 파일을 둘 것.", err=True)
        raise typer.Exit(1)

    cfg = load_config(override)
    typer.echo(f"접속 대상: {diagnostics.target_summary(cfg.dsn)}")

    db = Database(cfg)
    db.open()
    try:
        server = diagnostics.probe(db)
    finally:
        db.close()

    if not server.reachable:
        typer.echo(f"접속: 안 됨 ({server.elapsed:.2f}초)")
        typer.echo(server.message, err=True)
        raise typer.Exit(1)

    typer.echo(f"접속: 됨 ({server.elapsed:.2f}초)")
    typer.echo(f"서버: {server.version}")
    typer.echo(f"계정: {server.user}@{server.database}")

    if server.missing_tables:
        missing = ", ".join(server.missing_tables)
        typer.echo(f"스키마: 테이블 {len(server.missing_tables)}개가 없다 ({missing})")
        typer.echo("genviewer-init-db 를 먼저 실행할 것.", err=True)
        raise typer.Exit(1)

    typer.echo(f"스키마: 테이블 {len(diagnostics.expected_tables())}개 모두 있음")
    typer.echo(f"내용: process {server.processes}개, device {server.devices}개")


@app.command()
def processes(ctx: typer.Context, dsn: DsnOpt = "") -> None:
    """process 목록과 각 process 의 device 수."""
    db = _open(ctx, dsn)
    try:
        rows = ProcessRepository(db).list_with_counts()
    finally:
        db.close()

    if not rows:
        typer.echo("process 가 없다.")
        return

    # 헤더는 ASCII 로 둔다. 한글은 터미널에서 두 칸을 먹는데 len() 은 한 칸으로
    # 세기 때문에, 섞어 쓰면 칸이 어긋난다.
    width = max(len("NAME"), *(len(name) for name, _ in rows))
    typer.echo(f"{'NAME':<{width}}  DEVICE")
    for name, count in rows:
        typer.echo(f"{name:<{width}}  {count:>6}")
    typer.echo(f"process {len(rows)}개, device {sum(n for _, n in rows)}개")


@app.command()
def load(
    ctx: typer.Context,
    csv_path: Annotated[Path, typer.Argument(metavar="CSV", help="불러올 CSV 파일")],
    dsn: DsnOpt = "",
) -> None:
    """CSV 를 불러온다. 행 하나가 device 하나다."""
    # 붙기 전에 본다. 파일 이름을 잘못 친 사람에게 접속 에러를 보여주지 않는다.
    if not csv_path.is_file():
        typer.echo(f"CSV 파일이 없다: {csv_path}", err=True)
        raise typer.Exit(1)

    # 큰 CSV 한 방은 기본 statement_timeout(15초)을 넘긴다. 그 값은 창이 굳지
    # 않게 하려고 걸어둔 것이라 여기서는 의미가 없다. 사람이 직접 정해 뒀으면
    # 그 뜻을 따른다.
    db = _open(ctx, dsn, statement_timeout_ms=0)
    try:
        created = IORepository(db).import_data(str(csv_path), actor=current_user())
    finally:
        db.close()

    typer.echo(f"device {created}개를 새로 추가했다.")
    typer.echo("CSV 는 불러올 때마다 새로 쌓인다 - 같은 파일을 다시 넣으면 중복된다.")


@app.command()
def export(
    ctx: typer.Context,
    process: Annotated[str, typer.Argument(help="내보낼 process 이름")],
    out_path: Annotated[
        Path, typer.Argument(metavar="파일", help="쓸 파일. 확장자가 .xlsx 면 엑셀로 쓴다.")
    ],
    dsn: DsnOpt = "",
) -> None:
    """process 하나를 통째로 파일로 낸다."""
    db = _open(ctx, dsn)
    try:
        process_id = ProcessRepository(db).get_id(process)
        if process_id is None:
            typer.echo(f"그런 process 가 없다: {process}", err=True)
            raise typer.Exit(1)

        devices = DeviceRepository(db).fetch_devices_by_process(process_id)
        if not devices:
            typer.echo(f"process {process} 에 device 가 없다.", err=True)
            raise typer.Exit(1)

        # process_name 을 손으로 넣어야 한다. fetch_export_data 는 이 값이 빈
        # device 를 조용히 건너뛰는데 fetch_devices_by_process 는 그 키를 주지
        # 않는다. 빠뜨리면 에러 없이 빈 파일이 나온다 (GUI 도 같은 자리에서 넣는다).
        info = [{**d, "process_name": process} for d in devices]
        headers, rows = IORepository(db).fetch_export_data(info)
    finally:
        db.close()

    if out_path.suffix.lower() == ".xlsx":
        write_xlsx(str(out_path), headers, rows)
    else:
        write_csv(str(out_path), headers, rows)
    typer.echo(f"device {len(rows)}개를 {out_path} 에 썼다.")


# ---------------------------------------------------------------------------
# 변경 이력 (숨김)
# ---------------------------------------------------------------------------

# --follow 가 다시 물어보는 간격. LISTEN/NOTIFY 를 쓰지 않는 이유는
# service/repo/device.py 의 etag() docstring 에 적힌 것과 같다.
_FOLLOW_SECONDS = 3.0

# --follow 가 한 번에 따라잡는 최대 줄 수. 그 사이에 이보다 많이 쌓였다면
# 최근 것부터 보여준다.
_FOLLOW_CATCHUP = 1000

_WHEN_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")


def _parse_when(text: str) -> datetime:
    """YYYY-MM-DD[ HH:MM[:SS]] 또는 7d / 24h / 30m 같은 상대 시간."""
    text = text.strip()
    match = re.fullmatch(r"(\d+)\s*([dhm])", text)
    if match:
        amount, unit = int(match.group(1)), match.group(2)
        delta = {"d": "days", "h": "hours", "m": "minutes"}[unit]
        return datetime.now() - timedelta(**{delta: amount})
    for fmt in _WHEN_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    typer.echo(
        f"시각을 못 읽겠다: {text}  (YYYY-MM-DD, 'YYYY-MM-DD HH:MM', 7d, 24h)",
        err=True,
    )
    raise typer.Exit(2)


def _emit(rows: list[dict], detail: bool) -> None:
    for row in rows:
        typer.echo(audit.format_line(row))
        if detail:
            for line in audit.format_detail(row):
                typer.echo(line)


@app.command(hidden=True)
def log(
    ctx: typer.Context,
    number: Annotated[int, typer.Option("-n", "--number", help="보여줄 줄 수.")] = 50,
    since: Annotated[
        str, typer.Option("--since", help="이 시각부터. 7d / 24h / 2026-09-01 형식.")
    ] = "",
    who: Annotated[str, typer.Option("--who", help="이 사람이 한 것만.")] = "",
    process: Annotated[str, typer.Option("--process", help="이 process 것만.")] = "",
    device: Annotated[str, typer.Option("--device", help="이 device 것만.")] = "",
    find: Annotated[
        str, typer.Option("--find", help="이 글자가 든 줄만. 바뀐 값까지 뒤진다.")
    ] = "",
    detail: Annotated[
        bool, typer.Option("--detail", help="이전/이후 값을 펼쳐 보여준다.")
    ] = False,
    follow: Annotated[
        bool, typer.Option("--follow", "-f", help="새 줄을 계속 이어 찍는다. Ctrl-C 로 끝.")
    ] = False,
    out: Annotated[str, typer.Option("--out", help="화면 대신 CSV 파일로 쓴다.")] = "",
    purge_before: Annotated[
        str, typer.Option("--purge-before", help="이 시각 이전 이력을 지운다.")
    ] = "",
    yes: Annotated[
        bool, typer.Option("--yes", help="--purge-before 에서 묻지 않고 지운다.")
    ] = False,
    dsn: DsnOpt = "",
) -> None:
    """누가 언제 어떤 데이터를 바꿨는지 본다."""
    db = _open(ctx, dsn)
    try:
        repo = AuditRepository(db)

        if purge_before:
            _purge(repo, _parse_when(purge_before), yes)
            return

        rows = repo.recent(
            limit=number,
            since=_parse_when(since) if since else None,
            actor=who,
            process=process,
            device=device,
            contains=find,
        )

        if out:
            _write_log_csv(out, rows)
            return

        if not rows and not follow:
            typer.echo("이력이 없다.")
            return

        _emit(rows, detail)
        if follow:
            _follow(repo, rows, detail, who, process, device, find)
    finally:
        db.close()


def _follow(
    repo: AuditRepository,
    seen: list[dict],
    detail: bool,
    who: str,
    process: str,
    device: str,
    find: str,
) -> None:
    last = seen[-1]["id"] if seen else repo.latest_id()
    while True:
        time.sleep(_FOLLOW_SECONDS)
        rows = repo.recent(
            limit=_FOLLOW_CATCHUP,
            after_id=last,
            actor=who,
            process=process,
            device=device,
            contains=find,
        )
        if rows:
            _emit(rows, detail)
            last = rows[-1]["id"]


def _write_log_csv(out: str, rows: list[dict]) -> None:
    headers = [
        "시각",
        "사람",
        "출처",
        "동작",
        "process",
        "device",
        "테이블",
        "내용",
        "상세",
    ]
    table = [
        [
            row["at"].strftime("%Y-%m-%d %H:%M:%S"),
            row["actor"],
            row["source"],
            row["action"],
            row["process_name"],
            row["device_name"],
            row["table_name"],
            row["summary"],
            json.dumps(row["detail"], ensure_ascii=False, default=str),
        ]
        for row in rows
    ]
    write_csv(out, headers, table)
    typer.echo(f"{len(table)}줄을 {out} 에 썼다.")


def _purge(repo: AuditRepository, before: datetime, yes: bool) -> None:
    when = before.strftime("%Y-%m-%d %H:%M:%S")
    doomed = repo.count_before(before)
    if not doomed:
        typer.echo(f"{when} 이전 이력이 없다.")
        return
    if not yes:
        # 이력은 지우면 끝이다. 원본 데이터와 달리 다시 만들 방법이 없다.
        typer.confirm(f"{when} 이전 이력 {doomed}줄을 지운다. 계속할까?", abort=True)
    typer.echo(f"{repo.purge(before)}줄을 지웠다.")


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------


def _fail(exc: BaseException) -> None:
    if _verbose:
        traceback.print_exc()
    # str(exc) 를 쓰면 안 된다. psycopg 의 접속 실패 문자열에는 conninfo 가
    # 통째로 들어 있어서 비밀번호가 샌다. user_message 가 가려준다.
    typer.echo(f"오류: {user_message(exc)}", err=True)
    raise SystemExit(1) from None


def main() -> None:
    survive_console_encoding()
    # 이력에 남길 출처. 같은 저장이라도 창에서 한 것과 명령줄에서 한 것을
    # 구분할 수 있어야 한다.
    audit.set_source("cli")
    try:
        app(prog_name="genviewer")
    except KeyboardInterrupt:
        typer.echo("중단했다.", err=True)
        raise SystemExit(130) from None
    except OSError as exc:
        # 파이프를 읽는 쪽이 먼저 닫았다 (genviewer processes 를 head 로 받는 경우).
        # POSIX 는 EPIPE, 윈도우는 EINVAL 로 온다. 앱의 잘못이 아니다.
        if exc.errno not in (errno.EPIPE, errno.EINVAL):
            _fail(exc)
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        raise SystemExit(0) from None
    except Exception as exc:
        _fail(exc)


if __name__ == "__main__":
    main()
