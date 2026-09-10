#!/bin/sh
# molgen 전용 PostgreSQL 클러스터를 새로 만들고 기동한다.
#
# fmserver 의 scripts/inidb.csh 를 따르되 포트만 다르게 쓴다 (fmserver 는 55432).
# 이미 돌고 있는 다른 PostgreSQL 인스턴스는 건드리지 않는다.
#
#   PGDATA=... PGPORT=... ./tools/initdb.sh
#
# Windows(Git Bash)에서는 PostgreSQL 바이너리가 PATH 에 없으므로 PGBIN 을 준다:
#   PGBIN="/c/Program Files/PostgreSQL/18/bin" ./tools/initdb.sh
#
# 주의(Windows): Git Bash 에서 pg_ctl start 는 셸에 매여 프롬프트가 돌아오지 않는다.
# SKIP_START=1 로 두고 PowerShell Start-Process 로 따로 띄울 것. 리눅스는 그냥 두면 된다.
set -eu

PGPORT="${PGPORT:-55433}"
PGDATA="${PGDATA:-$HOME/pgdata/molgen}"
PGUSER="${PGUSER:-$(id -un)}"
PGDB="${PGDB:-molgen}"
PGBIN="${PGBIN:-}"
SKIP_START="${SKIP_START:-0}"

if [ -n "$PGBIN" ]; then
    initdb="$PGBIN/initdb"; pg_ctl="$PGBIN/pg_ctl"; createdb="$PGBIN/createdb"
else
    initdb=initdb; pg_ctl=pg_ctl; createdb=createdb
fi

if [ -s "$PGDATA/PG_VERSION" ]; then
    echo "이미 클러스터가 있다: $PGDATA (initdb 건너뜀)"
else
    echo "==> initdb $PGDATA"
    # locale=C: 정렬 규칙이 OS/로캘에 따라 달라지지 않게 고정 (fmserver 와 동일).
    # auth=trust: 루프백 전용 개발 클러스터라서. 공유 서버에서는 scram-sha-256 을 쓸 것.
    "$initdb" -D "$PGDATA" --encoding=UTF8 --locale=C -U "$PGUSER" --auth=trust
fi

# 외부에서 붙지 못하게 루프백으로 묶는다.
if ! grep -q "^listen_addresses" "$PGDATA/postgresql.conf"; then
    echo "listen_addresses = '127.0.0.1'" >> "$PGDATA/postgresql.conf"
fi

if [ "$SKIP_START" = "1" ]; then
    echo "==> start 건너뜀 (SKIP_START=1)"
else
    echo "==> start (port $PGPORT)"
    "$pg_ctl" -D "$PGDATA" -o "-p $PGPORT" -l "$PGDATA/server.log" -w start
fi

echo "==> create database $PGDB"
# --maintenance-db 를 명시하지 않으면 libpq 가 dbname 을 사용자 이름으로 잡아
# 'database "<user>" does not exist' 로 실패한다.
if "$createdb" -h 127.0.0.1 -p "$PGPORT" -U "$PGUSER" -O "$PGUSER" --maintenance-db=postgres "$PGDB" 2>/dev/null; then
    echo "   생성함"
else
    echo "   이미 있음"
fi

echo
echo "완료. 환경변수:"
echo "  GENDB_PG_DSN=postgresql://$PGUSER@127.0.0.1:$PGPORT/$PGDB"
