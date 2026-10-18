#!/bin/sh
# molgen 전용 PostgreSQL 클러스터를 새로 만들고 기동한다.
# 이미 돌고 있는 다른 인스턴스는 건드리지 않는다. 기본 포트는 55433 이다.
#
#   ./tools/initdb.sh                                      개발 PC (리눅스)
#   SKIP_START=1 PGBIN=".../bin" ./tools/initdb.sh         개발 PC (윈도우 Git Bash)
#
# 공유 서버(RHEL 7 + PostgreSQL 15)의 호출 방법과 인증 선택의 이유, root 가
# 따로 해야 하는 것(방화벽/systemd/SELinux)은 README 의 '서버' 절에 있다.
# 거기서 PGAUTH_LOCAL=peer 를 쓰는 이유도 설명한다 - trust 는 '비밀번호 없음'
# 이 아니라 '인증 없음' 이라 공유 서버에 쓰면 안 된다.
#
# 조절할 수 있는 값은 아래 기본값 목록이 전부다.
set -eu

PGPORT="${PGPORT:-55433}"
PGDATA="${PGDATA:-$HOME/pgdata/molgen}"
PGUSER="${PGUSER:-$(id -un)}"
PGDB="${PGDB:-molgen}"
PGBIN="${PGBIN:-}"
SKIP_START="${SKIP_START:-0}"
LISTEN_ADDRESSES="${LISTEN_ADDRESSES:-127.0.0.1}"
PGAUTH_LOCAL="${PGAUTH_LOCAL:-trust}"
PGAUTH_HOST="${PGAUTH_HOST:-trust}"
PGHBA_CIDR="${PGHBA_CIDR:-}"
PGHBA_DB="${PGHBA_DB:-all}"       # 원격으로 열어줄 데이터베이스
PGHBA_USER="${PGHBA_USER:-all}"   # 원격으로 붙을 수 있는 role

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
    #
    # local 과 host 를 나누는 이유: --auth=scram-sha-256 처럼 하나로 주면 initdb 가
    # "must specify a password for the superuser" 로 죽는다. --pwprompt 를 강요당하고
    # 그러면 슈퍼유저 비밀번호를 어딘가 보관해야 한다. local 을 peer 로 두면 그
    # 요구가 사라진다(peer 는 password 계열이 아니다) - 소유자는 유닉스 소켓으로
    # 비밀번호 없이 붙고, 원격 사용자만 scram 을 쓴다.
    "$initdb" -D "$PGDATA" --encoding=UTF8 --locale=C -U "$PGUSER" --auth-local="$PGAUTH_LOCAL" --auth-host="$PGAUTH_HOST"
fi

# 기본은 루프백. 공유 서버는 LISTEN_ADDRESSES='*' 로 연다.
if ! grep -q "^listen_addresses" "$PGDATA/postgresql.conf"; then
    echo "listen_addresses = '$LISTEN_ADDRESSES'" >> "$PGDATA/postgresql.conf"
fi

# 포트도 파일에 적는다. 아래 pg_ctl 의 -o "-p" 는 이 스크립트로 띄울 때만 먹으므로,
# 재부팅 생존용 systemd 유닛처럼 다른 방법으로 띄우면 그 인자가 없어서 기본값
# 5432 로 올라온다. 그러면 모두의 GENDB_PG_DSN(:55433)이 조용히 끊긴다.
if ! grep -q "^port" "$PGDATA/postgresql.conf"; then
    echo "port = $PGPORT" >> "$PGDATA/postgresql.conf"
fi

# initdb --auth-host 은 127.0.0.1 과 ::1 줄만 쓴다. 원격 대역은 여기서 따로 연다.
#
# PGHBA_DB / PGHBA_USER 로 좁히는 것을 권한다. 기본값 all all 이면 앱 계정
# 비밀번호 하나로 postgres 데이터베이스까지 붙을 수 있다. molgen / molgen_app 로
# 좁히면 그 비밀번호가 새도 molgen 밖으로는 못 가고, 소유자 role 은 원격 접속이
# 아예 안 된다 - 로컬 peer 로만 쓰라는 것이 원래 의도였다.
if [ -n "$PGHBA_CIDR" ]; then
    hba_line="host $PGHBA_DB $PGHBA_USER $PGHBA_CIDR $PGAUTH_HOST"
    # 주석 처리된 같은 줄을 있음으로 보지 않게 줄 전체를 비교한다.
    if ! grep -qxF "$hba_line" "$PGDATA/pg_hba.conf"; then
        echo "$hba_line" >> "$PGDATA/pg_hba.conf"
        echo "==> pg_hba.conf 에 추가: $hba_line"
    fi
fi

if [ "$SKIP_START" = "1" ]; then
    echo "==> start 건너뜀 (SKIP_START=1)"
# 이미 떠 있으면(이 스크립트로 띄웠든 systemd 로 띄웠든) start 하지 않는다. 떠 있는
# 서버에 start 하면 pg_ctl 이 exit 1 이라 다시 돌린 실행이 createdb 전에 죽는다.
# pg_ctl status 의 종료 코드: 0 떠 있음, 3 안 떠 있음, 4 데이터 디렉터리가 없거나 잘못됨.
# 0 이 아니면 지금처럼 start 한다. start 를 '|| true' 로 넘기지 않는 이유: 포트 충돌·
# 권한·잘못된 설정으로 진짜 못 띄운 경우는 여기서 멈춰야 한다.
elif "$pg_ctl" -D "$PGDATA" status >/dev/null 2>&1; then
    echo "==> start 건너뜀 (이미 떠 있다)"
else
    echo "==> start (port $PGPORT)"
    "$pg_ctl" -D "$PGDATA" -o "-p $PGPORT" -l "$PGDATA/server.log" -w start
fi

echo "==> create database $PGDB"
# --maintenance-db 를 명시하지 않으면 libpq 가 dbname 을 사용자 이름으로 잡아
# 'database "<user>" does not exist' 로 실패한다.
#
# -h 를 주지 않는다. createdb 는 initdb 와 달리 '클라이언트' 라서 방금 쓴
# pg_hba.conf 에 자기가 걸린다. -h 127.0.0.1 은 TCP = host 줄이므로
# PGAUTH_HOST=scram-sha-256 인 공유 서버에서는 비밀번호를 요구하는데, 슈퍼유저는
# 비밀번호가 없다(PGAUTH_LOCAL=peer 로 둔 이유가 그거다). host 를 비우면 리눅스는
# 유닉스 소켓(= PGAUTH_LOCAL), 윈도우는 localhost 로 붙어 양쪽 다 맞는다.
#
# 실패를 삼키지 않는다. 예전에는 2>/dev/null 로 이유를 지우고 무조건 "이미 있음"
# 으로 떨어져서, DB 가 안 만들어졌는데도 성공한 것처럼 끝났다. -w 는 보이지도 않는
# 비밀번호 프롬프트에서 멈추는 것을 막는다.
if err=$("$createdb" -p "$PGPORT" -U "$PGUSER" -O "$PGUSER" -w --maintenance-db=postgres "$PGDB" 2>&1); then
    echo "   생성함"
elif printf '%s' "$err" | grep -q "already exists"; then
    echo "   이미 있음"
else
    echo "   실패: $err" >&2
    exit 1
fi

echo
echo "완료. 환경변수:"
echo "  GENDB_PG_DSN=postgresql://$PGUSER@127.0.0.1:$PGPORT/$PGDB"
