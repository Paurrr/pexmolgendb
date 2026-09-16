"""명령줄 도구 테스트.

여기서 지키려는 성질은 넷이다.

1. **CLI 가 Qt 를 끌어오지 않는다.** status 한 번 보자고 PySide6 를 통째로
   올리면 X 가 없는 서버에서는 아예 못 돈다. 별도 프로세스에서 확인한다 -
   같은 프로세스에서는 다른 테스트가 이미 올려놨을 수 있다.
2. **도움말이 cp949 로 찍힌다.** 한국어 Windows 콘솔 이야기다. rich 가 도움말을
   상자로 그리면 테두리가 물음표가 된다.
3. **비밀번호가 출력 어디에도 없다.**
4. **실패가 트레이스백이 아니라 한 줄 문장과 종료 코드로 나온다.**
"""

import csv
import subprocess
import sys
from datetime import datetime, timedelta

import pytest
from typer.testing import CliRunner

from genviewer import cli
from genviewer.cli import app
from genviewer.service.repo.process import ProcessRepository

runner = CliRunner()

HEADERS = ["CellType", "CdsLibName", "InstCellName", "AddFGRParam"]
ROWS = [
    ["NFET", "sf2p", "nfet_b", "grLayer RX"],
    ["PFET", "sf2p", "pfet_b", "grLayer NW"],
    ["NFET", "sf4u", "nfet_c", "grLayer RX"],
]


def _csv(path, rows=ROWS):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADERS)
        w.writerows(rows)
    return str(path)


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    """설정 파일과 PG* 환경변수에서 떼어낸다.

    GENDB_CONFIG 가 있으면 env_file 은 그 파일만 본다. 없는 경로를 주면 개발자
    홈에 있는 진짜 설정이 테스트 결과를 바꾸지 못한다.
    """
    monkeypatch.setenv("GENDB_CONFIG", str(tmp_path / "there_is_no_such_file.env"))
    for key in (
        "GENDB_PG_DSN",
        "PGHOST",
        "PGHOSTADDR",
        "PGPORT",
        "PGDATABASE",
        "PGUSER",
        "PGSERVICE",
        "PGPASSWORD",
    ):
        monkeypatch.delenv(key, raising=False)


# --------------------------------------------------------------------------
# DB 불필요.
# --------------------------------------------------------------------------


def test_importing_the_cli_does_not_load_qt():
    """가장 중요한 회귀 방지선. 이게 깨지면 headless 에서 status 가 못 돈다."""
    code = (
        "import sys, genviewer.cli; "
        "sys.exit(any(m.startswith('PySide6') for m in sys.modules))"
    )
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0


@pytest.mark.parametrize(
    "args",
    [["--help"], ["status", "--help"], ["processes", "--help"], ["load", "--help"],
     ["export", "--help"], ["log", "--help"]],
)
def test_help_works_and_a_korean_console_can_print_it(args):
    """배포 스크립트가 런처마다 --help 를 실제로 실행해 본다 (tools/deploy.sh).

    그 출력은 cp949 로 인코딩될 수 있어야 한다. cli.py 가 rich_markup_mode=None
    을 쓰는 이유가 이것이다 - rich 의 도움말 상자(U+2500 대)는 cp949 에 없다.
    """
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    result.output.encode("cp949")


def test_status_without_connection_info_says_where_to_look(isolated):
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 1
    assert "접속 정보가 없다" in result.output
    assert "찾아본 곳:" in result.output


def test_check_config_still_works(isolated):
    """기존 플래그다. 서브커맨드가 생겼다고 사라지면 안 된다 (README 가 안내한다)."""
    result = runner.invoke(app, ["--check-config"])
    assert result.exit_code == 1
    assert "설정 파일:" in result.output
    assert "로그 파일:" in result.output


def test_a_missing_csv_is_reported_before_connecting(isolated, tmp_path):
    """접속 정보가 없어도 파일 이름 오타부터 말해줘야 한다."""
    result = runner.invoke(app, ["load", str(tmp_path / "nope.csv")])
    assert result.exit_code == 1
    assert "nope.csv" in result.output
    assert "Traceback" not in result.output


def test_an_unknown_command_is_a_usage_error(isolated):
    assert runner.invoke(app, ["nosuchthing"]).exit_code == 2


def test_no_password_reaches_the_output(isolated, monkeypatch):
    """URL 형식 DSN 의 비밀번호도 가려야 한다.

    예전 --check-config 는 'password' 라는 낱말이 있을 때만 감췄기 때문에
    postgresql://user:secret@host 형식은 그대로 찍혔다.
    """
    secret = "s3cr3t_must_not_leak"
    monkeypatch.setenv("GENDB_PG_DSN", f"postgresql://someone:{secret}@127.0.0.1:1/x")
    monkeypatch.setenv("PGPASSWORD", secret)

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 1, "붙을 리 없는 주소다"
    assert secret not in result.output


def test_an_unexpected_failure_becomes_one_line(capsys):
    """main() 은 트레이스백 대신 한 줄을 낸다. 예외 문자열의 비밀번호도 가린다.

    psycopg 의 접속 실패 문자열에는 conninfo 가 통째로 들어 있다.
    """
    with pytest.raises(SystemExit) as caught:
        cli._fail(RuntimeError("connection failed: password=topsecret"))
    assert caught.value.code == 1

    err = capsys.readouterr().err
    assert "오류:" in err
    assert "topsecret" not in err


# --------------------------------------------------------------------------
# DB 필요.
# --------------------------------------------------------------------------


def test_processes_lists_names_and_counts(db, pg_dsn, tmp_path):
    runner.invoke(app, ["load", _csv(tmp_path / "in.csv"), "--dsn", pg_dsn])

    result = runner.invoke(app, ["processes", "--dsn", pg_dsn])
    assert result.exit_code == 0, result.output
    assert "sf2p" in result.output and "sf4u" in result.output
    assert "process 2개, device 3개" in result.output


def test_processes_without_any_process_says_so(db, pg_dsn):
    result = runner.invoke(app, ["processes", "--dsn", pg_dsn])
    assert result.exit_code == 0, result.output
    assert "process 가 없다" in result.output


def test_load_adds_devices_and_says_how_many(db, pg_dsn, tmp_path):
    result = runner.invoke(app, ["load", _csv(tmp_path / "in.csv"), "--dsn", pg_dsn])
    assert result.exit_code == 0, result.output
    assert "device 3개를 새로 추가했다" in result.output
    assert dict(ProcessRepository(db).list_with_counts()) == {"sf2p": 2, "sf4u": 1}


def test_loading_the_same_file_twice_adds_again(db, pg_dsn, tmp_path):
    """현 계약이다. 멱등하지 않으므로 개수를 반드시 보여준다."""
    path = _csv(tmp_path / "in.csv")
    runner.invoke(app, ["load", path, "--dsn", pg_dsn])
    runner.invoke(app, ["load", path, "--dsn", pg_dsn])
    assert dict(ProcessRepository(db).list_with_counts()) == {"sf2p": 4, "sf4u": 2}


def test_export_writes_every_device_of_the_process(db, pg_dsn, tmp_path):
    runner.invoke(app, ["load", _csv(tmp_path / "in.csv"), "--dsn", pg_dsn])
    out = tmp_path / "out.csv"

    result = runner.invoke(app, ["export", "sf2p", str(out), "--dsn", pg_dsn])
    assert result.exit_code == 0, result.output

    with open(out, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0][:3] == ["CellType", "CdsLibName", "InstCellName"]
    assert len(rows) == 3, "헤더 + sf2p 의 device 2개"
    assert {r[2] for r in rows[1:]} == {"nfet_b", "pfet_b"}


def test_an_exported_file_loads_back(db, pg_dsn, tmp_path):
    """왕복. export 가 만든 파일을 load 가 그대로 다시 읽어야 한다."""
    runner.invoke(app, ["load", _csv(tmp_path / "in.csv"), "--dsn", pg_dsn])
    out = tmp_path / "out.csv"
    runner.invoke(app, ["export", "sf2p", str(out), "--dsn", pg_dsn])

    result = runner.invoke(app, ["load", str(out), "--dsn", pg_dsn])
    assert result.exit_code == 0, result.output
    assert dict(ProcessRepository(db).list_with_counts())["sf2p"] == 4


def test_export_refuses_an_unknown_process(db, pg_dsn, tmp_path):
    out = tmp_path / "nope.csv"
    result = runner.invoke(app, ["export", "no_such_process", str(out), "--dsn", pg_dsn])
    assert result.exit_code == 1
    assert not out.exists(), "빈 파일을 만들면 나중에 왜 비었는지를 묻게 된다"


def test_export_refuses_a_process_with_no_devices(db, pg_dsn, tmp_path):
    ProcessRepository(db).add("empty_one")
    out = tmp_path / "empty.csv"

    result = runner.invoke(app, ["export", "empty_one", str(out), "--dsn", pg_dsn])
    assert result.exit_code == 1
    assert not out.exists()


def test_status_reports_the_schema_and_the_row_counts(db, pg_dsn, tmp_path, isolated):
    runner.invoke(app, ["load", _csv(tmp_path / "in.csv"), "--dsn", pg_dsn])

    result = runner.invoke(app, ["status", "--dsn", pg_dsn])
    assert result.exit_code == 0, result.output
    assert "접속: 됨" in result.output
    assert "모두 있음" in result.output
    assert "process 2개, device 3개" in result.output


def test_status_points_at_init_db_when_a_table_is_missing(db, pg_dsn, isolated):
    """탭을 추가하고 init-db 를 안 돌린 상태가 이렇게 보인다.

    지우는 것은 탭 테이블이어야 한다. device 를 지우면 CASCADE 가 자식 테이블의
    외래키까지 떼어내는데, 다음 테스트의 픽스처는 CREATE TABLE IF NOT EXISTS 라
    그것을 되살리지 못한다. 그러면 TRUNCATE CASCADE 가 자식 행에 닿지 못해
    세션 내내 남의 테스트가 깨진다.
    """
    with db.connection() as conn:
        conn.execute("DROP TABLE IF EXISTS inst_terms")

    result = runner.invoke(app, ["status", "--dsn", pg_dsn])
    assert result.exit_code == 1
    assert "genviewer-init-db" in result.output


def test_no_subcommand_opens_the_window(monkeypatch, isolated):
    """기존 동작을 고정한다. genviewer --dsn X --host Y 는 그대로 창을 띄운다.

    여기서만 genviewer.main 을 import 한다 - Qt 가 딸려 오는 유일한 경로가
    그것이라는 사실 자체가 이 테스트의 내용이다.
    """
    import genviewer.main as gui

    seen = {}

    def fake(dsn="", host="", history=False):
        seen.update(dsn=dsn, host=host, history=history)
        return 0

    monkeypatch.setattr(gui, "run_gui", fake)
    result = runner.invoke(app, ["--dsn", "D", "--host", "H"])
    assert result.exit_code == 0
    assert seen == {"dsn": "D", "host": "H", "history": False}


def test_the_history_screen_is_off_unless_asked_for(monkeypatch, isolated):
    """--history 없이 띄우면 이력 화면은 아예 만들어지지 않는다."""
    import genviewer.main as gui

    seen = {}
    monkeypatch.setattr(
        gui, "run_gui", lambda dsn="", host="", history=False: seen.update(h=history)
    )
    runner.invoke(app, ["--history"])
    assert seen == {"h": True}


def test_the_log_command_and_history_flag_stay_out_of_the_help(isolated):
    """숨김의 증거. 보안 장치가 아니라 "평소에 눈에 띄지 않는다" 까지다."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "--history" not in result.output
    # 명령 목록에 log 가 없어야 한다. 다른 낱말에 섞인 log 는 세지 않는다.
    commands = result.output.split("Commands:")[1]
    assert not any(line.strip().startswith("log") for line in commands.splitlines())


# --------------------------------------------------------------------------
# DB 필요 - 이력.
# --------------------------------------------------------------------------


def test_log_shows_what_the_load_did(db, pg_dsn, tmp_path):
    runner.invoke(app, ["load", _csv(tmp_path / "in.csv"), "--dsn", pg_dsn])

    result = runner.invoke(app, ["log", "--dsn", pg_dsn])
    assert result.exit_code == 0, result.output
    assert "CSV 불러오기" in result.output
    assert "in.csv" in result.output
    result.output.encode("cp949")


def test_log_on_an_untouched_database_says_so(db, pg_dsn):
    result = runner.invoke(app, ["log", "--dsn", pg_dsn])
    assert result.exit_code == 0, result.output
    assert "이력이 없다" in result.output


def test_log_filters_by_person_and_process(db, pg_dsn, tmp_path):
    ProcessRepository(db).add("sf9z", actor="관리자")
    runner.invoke(app, ["load", _csv(tmp_path / "in.csv"), "--dsn", pg_dsn])

    mine = runner.invoke(app, ["log", "--who", "관리자", "--dsn", pg_dsn])
    assert "sf9z" in mine.output and "in.csv" not in mine.output

    theirs = runner.invoke(app, ["log", "--process", "sf9z", "--dsn", pg_dsn])
    assert "process 추가" in theirs.output


def test_log_can_write_a_csv(db, pg_dsn, tmp_path):
    ProcessRepository(db).add("sf9z", actor="관리자")
    out = tmp_path / "history.csv"

    result = runner.invoke(app, ["log", "--out", str(out), "--dsn", pg_dsn])
    assert result.exit_code == 0, result.output

    with open(out, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0][0] == "시각"
    assert any("sf9z" in cell for cell in rows[1])


def test_purge_needs_a_confirmation_and_then_empties_the_range(db, pg_dsn):
    ProcessRepository(db).add("sf9z", actor="관리자")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    # 물어보는 자리에서 아니오. 이력은 지우면 되돌릴 수 없다.
    no = runner.invoke(
        app, ["log", "--purge-before", tomorrow, "--dsn", pg_dsn], input="n\n"
    )
    assert no.exit_code != 0
    assert "sf9z" in runner.invoke(app, ["log", "--dsn", pg_dsn]).output

    yes = runner.invoke(
        app, ["log", "--purge-before", tomorrow, "--yes", "--dsn", pg_dsn]
    )
    assert yes.exit_code == 0, yes.output
    assert "지웠다" in yes.output
    assert "이력이 없다" in runner.invoke(app, ["log", "--dsn", pg_dsn]).output


def test_a_bad_since_is_a_usage_error(db, pg_dsn):
    result = runner.invoke(app, ["log", "--since", "어제쯤", "--dsn", pg_dsn])
    assert result.exit_code == 2
    assert "시각을 못 읽겠다" in result.output
