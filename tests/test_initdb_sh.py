"""tools/initdb.sh - 이미 있는 클러스터에 다시 돌리는 경우.

진짜 PostgreSQL 은 쓰지 않는다. PGBIN 에 가짜 initdb / pg_ctl / createdb 를 놓고,
각자 받은 인자를 기록하게 한다. 서버가 떠 있는지와 데이터베이스가 있는지는
STUB_STATE 디렉터리의 파일 두 개(running, db)로 흉내 낸다.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
INITDB = REPO / "tools" / "initdb.sh"

pytestmark = pytest.mark.skipif(shutil.which("sh") is None, reason="sh 가 없다")

# 기록은 printf 로 남긴다. 일부 sh 의 echo 는 윈도우 경로의 백슬래시를 해석한다.
INITDB_STUB = """#!/bin/sh
printf '%s\\n' "initdb $*" >> "$STUB_RECORD"
dir=
while [ $# -gt 0 ]; do
    if [ "$1" = "-D" ]; then
        dir=$2
        shift
    fi
    shift
done
[ -n "$dir" ] || { echo "stub initdb: -D 가 없다" >&2; exit 1; }
mkdir -p "$dir"
echo 15 > "$dir/PG_VERSION"
: > "$dir/postgresql.conf"
: > "$dir/pg_hba.conf"
"""

# 마지막 인자가 동작이다. status 의 종료 코드는 진짜 pg_ctl 과 같다(0 떠 있음, 3 안 떠 있음).
PG_CTL_STUB = """#!/bin/sh
printf '%s\\n' "pg_ctl $*" >> "$STUB_RECORD"
for action; do :; done
case "$action" in
    status)
        [ -e "$STUB_STATE/running" ] && exit 0
        exit 3
        ;;
    start)
        if [ "${STUB_START_FAIL:-0}" = "1" ] || [ -e "$STUB_STATE/running" ]; then
            echo "pg_ctl: could not start server" >&2
            exit 1
        fi
        : > "$STUB_STATE/running"
        ;;
    *)
        echo "stub pg_ctl: 모르는 동작 $action" >&2
        exit 2
        ;;
esac
"""

CREATEDB_STUB = """#!/bin/sh
printf '%s\\n' "createdb $*" >> "$STUB_RECORD"
if [ -e "$STUB_STATE/db" ]; then
    echo 'createdb: error: database creation failed: ERROR:  database "molgen" already exists' >&2
    exit 1
fi
: > "$STUB_STATE/db"
"""


@pytest.fixture
def pg(tmp_path):
    """PGBIN 으로 넘길 가짜 바이너리 셋과, 그것들이 남기는 기록·상태."""
    bindir = tmp_path / "pgbin"
    bindir.mkdir()
    for name, body in (
        ("initdb", INITDB_STUB),
        ("pg_ctl", PG_CTL_STUB),
        ("createdb", CREATEDB_STUB),
    ):
        path = bindir / name
        path.write_text(body, encoding="utf-8", newline="\n")
        path.chmod(0o755)
    state = tmp_path / "state"
    state.mkdir()
    return {
        "bindir": bindir,
        "record": tmp_path / "record.txt",
        "state": state,
        "data": tmp_path / "data",
    }


def run_initdb(pg, **env):
    """initdb.sh 를 돌리고 CompletedProcess 를 준다.

    개발 PC 의 PGPORT·PGUSER·PGDATA 같은 값이 섞이지 않게 비우고 주어진 값만 더한다.
    PGDATA 는 반드시 준다. 기본값은 $HOME/pgdata/molgen 이다.
    """
    environ = dict(os.environ)
    for key in list(environ):
        if key.startswith(("PG", "SKIP_START", "LISTEN_ADDRESSES")):
            environ.pop(key)
    environ.update(
        PGBIN=str(pg["bindir"]),
        PGDATA=str(pg["data"]),
        STUB_RECORD=str(pg["record"]),
        STUB_STATE=str(pg["state"]),
    )
    environ.update({k: str(v) for k, v in env.items()})
    return subprocess.run(
        ["sh", str(INITDB)], capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=environ,
    )


def calls(pg, name):
    """기록에서 name 의 호출마다 인자 목록을 준다."""
    if not pg["record"].exists():
        return []
    lines = pg["record"].read_text(encoding="utf-8").splitlines()
    return [line.split()[1:] for line in lines if line.split()[:1] == [name]]


def starts(pg):
    return [args for args in calls(pg, "pg_ctl") if args[-1:] == ["start"]]


def test_a_second_run_on_a_running_cluster_succeeds(pg):
    first = run_initdb(pg)
    assert first.returncode == 0, first.stderr
    second = run_initdb(pg)
    assert second.returncode == 0, second.stderr
    assert "이미 있음" in second.stdout
    assert len(starts(pg)) == 1
    assert len(calls(pg, "initdb")) == 1


def test_a_second_run_says_start_was_skipped(pg):
    run_initdb(pg)
    second = run_initdb(pg)
    assert "==> start 건너뜀 (이미 떠 있다)" in second.stdout


def test_a_failing_start_still_stops_the_script(pg):
    # 포트 충돌처럼 진짜로 못 띄운 경우. || true 로 삼키면 여기서 걸린다.
    result = run_initdb(pg, STUB_START_FAIL=1)
    assert result.returncode != 0
    assert "could not start server" in result.stderr
    assert calls(pg, "createdb") == []


def test_skip_start_does_not_call_pg_ctl(pg):
    result = run_initdb(pg, SKIP_START=1)
    assert "start 건너뜀 (SKIP_START=1)" in result.stdout
    assert calls(pg, "pg_ctl") == []


# PGAUTH_HOST 는 늘 적는다. PGHBA_CIDR 만 주고 비우면 받지 않는다(K26).
HBA_ENV = {
    "PGHBA_CIDR": "10.0.0.0/8",
    "PGHBA_DB": "molgen",
    "PGHBA_USER": "molgen_app",
    "PGAUTH_HOST": "scram-sha-256",
}
HBA_LINE = "host molgen molgen_app 10.0.0.0/8 scram-sha-256"


def hba_lines(pg):
    return (pg["data"] / "pg_hba.conf").read_text(encoding="utf-8").splitlines()


def test_a_commented_out_hba_line_does_not_count_as_present(pg):
    # 사람이 꺼 둔 같은 줄을 "이미 있음" 으로 보면 원격 대역이 말없이 안 열린다(K27).
    assert run_initdb(pg).returncode == 0
    (pg["data"] / "pg_hba.conf").write_text(
        f"# {HBA_LINE}\n", encoding="utf-8", newline="\n",
    )
    result = run_initdb(pg, **HBA_ENV)
    assert result.returncode == 0, result.stderr
    assert hba_lines(pg).count(HBA_LINE) == 1
    assert "pg_hba.conf 에 추가" in result.stdout


def test_an_existing_hba_line_is_not_added_again(pg):
    first = run_initdb(pg, **HBA_ENV)
    assert first.returncode == 0, first.stderr
    assert "pg_hba.conf 에 추가" in first.stdout
    second = run_initdb(pg, **HBA_ENV)
    assert second.returncode == 0, second.stderr
    assert hba_lines(pg).count(HBA_LINE) == 1
    assert "추가" not in second.stdout


# K26: PGHBA_CIDR 를 주면서 PGAUTH_HOST 를 정하지 않으면 기본값 trust 가 그 대역 전체를
# 인증 없이 연다. 그런 실행은 무엇도 하기 전에 거부한다(승인 2026-10-17).
CIDR = "10.0.0.0/8"


def test_a_cidr_without_pgauth_host_is_refused(pg):
    result = run_initdb(pg, PGHBA_CIDR=CIDR)
    assert result.returncode == 1, result.stdout
    assert "PGAUTH_HOST" in result.stderr
    assert "trust" in result.stderr
    assert not pg["record"].exists()
    assert not pg["data"].exists()


def test_a_cidr_without_pgauth_host_is_refused_on_an_existing_cluster(pg):
    assert run_initdb(pg).returncode == 0
    before = pg["record"].read_text(encoding="utf-8")
    result = run_initdb(pg, PGHBA_CIDR=CIDR)
    assert result.returncode == 1, result.stdout
    assert hba_lines(pg) == []
    assert pg["record"].read_text(encoding="utf-8") == before


def test_an_empty_pgauth_host_counts_as_unset(pg):
    result = run_initdb(pg, PGHBA_CIDR=CIDR, PGAUTH_HOST="")
    assert result.returncode == 1, result.stdout
    assert not pg["record"].exists()


def test_an_explicit_trust_with_a_cidr_is_accepted(pg):
    result = run_initdb(pg, PGHBA_CIDR=CIDR, PGAUTH_HOST="trust")
    assert result.returncode == 0, result.stderr
    assert hba_lines(pg) == [f"host all all {CIDR} trust"]


def test_scram_with_a_cidr_is_accepted(pg):
    result = run_initdb(pg, PGHBA_CIDR=CIDR, PGAUTH_HOST="scram-sha-256")
    assert result.returncode == 0, result.stderr
    assert hba_lines(pg) == [f"host all all {CIDR} scram-sha-256"]


def test_without_a_cidr_the_default_host_auth_is_still_trust(pg):
    # 개발 기본값: 원격 대역이 없으면 trust 는 루프백에만 쓰인다.
    result = run_initdb(pg)
    assert result.returncode == 0, result.stderr
    [initdb_args] = calls(pg, "initdb")
    assert "--auth-host=trust" in initdb_args
    assert hba_lines(pg) == []
