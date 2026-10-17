#!/bin/sh
# 태그 하나를 리눅스 공유 디렉터리에 설치한다.
#
#   ./tools/deploy.sh <ROOT> <TAG> [<GIT URL>]
#   ./tools/deploy.sh /opt/genviewer v0.3.0 https://git.example/org/gendb.git
#
# URL 은 <ROOT>/src 를 처음 만들 때만 필요하다.
#
# 되돌리려면 옛 태그로 다시 돌린다:
#   ./tools/deploy.sh /opt/genviewer v0.2.0
#
# 만들어지는 모양:
#   <ROOT>/src            태그에 detach 된 체크아웃. 브랜치를 따라 흐르지 않는다
#   <ROOT>/venv           프로젝트와 의존성이 든 가상환경
#   <ROOT>/bin            사용자가 PATH 에 넣는 유일한 디렉터리. 명령만 들어 있다
#   <ROOT>/genviewer.env  접속 설정. 업그레이드해도 건드리지 않는다
#
# uv 는 이 스크립트를 돌릴 때만 필요하고 결과를 쓸 때는 필요 없다. 런처가 venv 의
# 인터프리터를 직접 부르기 때문이다. 배포된 명령을 쓰는 사람은 uv 도 자기 파이썬도
# 없어도 된다.
#
# 주의: 교체가 제자리에서 일어난다. 설치가 도는 동안 앱을 띄우면 반쯤 바뀐 트리를
# 볼 수 있다(파이썬이 모듈을 그때그때 import 한다). 사람들이 쓰지 않는 시간에 돌릴 것.
#
# 환경변수:
#   DEPLOY_PYTHON     venv 를 만들 인터프리터. 예: /usr/bin/python3.13 또는
#                     <ROOT> 아래에 설치해 둔 것
#   DEPLOY_COMMANDS   프로젝트의 console_scripts 를 자동으로 못 읽을 때 쓸,
#                     공백으로 구분한 명령 이름들
#   DEPLOY_LINK_DIR   이미 사용자들 PATH 에 있는 디렉터리. 명령을 거기로 심볼릭
#                     링크해서 아무도 셸 프로파일을 고치지 않아도 되게 한다
set -eu

usage() {
    echo "usage: deploy.sh <install-root> <tag> [git-url]" >&2
    exit 2
}

[ $# -ge 2 ] || usage
root=$1
tag=$2
url=${3:-}

command -v uv >/dev/null 2>&1 || {
    echo "error: uv 가 PATH 에 없다. 배포할 때 필요하고, 결과를 쓸 때는 필요 없다." >&2
    exit 1
}

# 절대 경로로 바꾼다. 심볼릭 링크의 목적지는 링크가 놓인 디렉터리를 기준으로
# 풀리지, 이 스크립트를 돌린 디렉터리를 기준으로 풀리지 않는다.
mkdir -p "$root"
root=$(cd -- "$root" && pwd)

# ---- 소스 체크아웃, 태그에 고정

if [ ! -d "$root/src/.git" ]; then
    [ -n "$url" ] || {
        echo "error: $root/src 가 아직 없다. 저장소 URL 을 세 번째 인자로 줄 것." >&2
        exit 1
    }
    git clone "$url" "$root/src"
fi

git -C "$root/src" fetch --tags --force origin

# refs/tags/ 를 명시한다. 그것만으로 브랜치 이름이 거부된다 - 브랜치에 고정하면
# 'v0.3.0 배포본' 이 나중에 다른 커밋을 가리키게 되어 무엇이 도는지 알 수 없어진다.
git -C "$root/src" checkout --detach "refs/tags/$tag"
echo "pinned $root/src to $tag"

# ---- 가상환경과 설치
#
# uv pip install 이 아니라 uv sync --frozen 을 쓴다. 이 프로젝트는 PySide6 6.9.3 ->
# manylinux_2_28 -> Python 3.13 으로 묶여 있어서, 배포할 때마다 의존성을 다시 푸는
# 것이 아니라 uv.lock 을 그대로 재현해야 한다. pyproject 와 lock 이 어긋나 있으면
# --frozen 이 여기서 막는다.
#
# --no-editable 인 것이 중요하다. editable 로 깔면 코드가 <ROOT>/src 에서 도는데,
# 그러면 누가 그 디렉터리를 고치는 순간 버전을 안 올리고도 전원의 앱이 바뀐다.
# 태그에 고정한 의미가 없어진다.

if [ -n "${DEPLOY_PYTHON:-}" ]; then
    UV_PROJECT_ENVIRONMENT="$root/venv" uv sync --frozen --no-dev --no-editable \
        --project "$root/src" --python "$DEPLOY_PYTHON"
else
    UV_PROJECT_ENVIRONMENT="$root/venv" uv sync --frozen --no-dev --no-editable \
        --project "$root/src"
fi

python="$root/venv/bin/python"

# ---- 어떤 명령을 낼 것인가

pkg=$("$python" -c 'import tomllib,sys;print(tomllib.load(open(sys.argv[1],"rb"))["project"]["name"])' \
      "$root/src/pyproject.toml" 2>/dev/null) || pkg=""

if [ -n "${DEPLOY_COMMANDS:-}" ]; then
    commands=$DEPLOY_COMMANDS
elif [ -n "$pkg" ]; then
    commands=$("$python" -c '
import sys
from importlib.metadata import distribution
eps = distribution(sys.argv[1]).entry_points
print(" ".join(e.name for e in eps if e.group == "console_scripts"))
' "$pkg")
else
    commands=""
fi

[ -n "$commands" ] || {
    echo "error: console_scripts 를 찾지 못했다. DEPLOY_COMMANDS 로 직접 줄 것." >&2
    exit 1
}

# ---- 런처
#
# 사용자 PATH 에 올라가는 것은 이것뿐이다. venv/bin 자체를 올리면 그 안의 python 과
# pip 가 사용자 자신의 것을 가린다.
#
# 런처는 콘솔 스크립트를 실행하지 않고 **인터프리터에 넘긴다.** 콘솔 스크립트의
# shebang 은 venv 안을 가리키는 절대 경로인데 커널이 shebang 을 127바이트에서
# 자르기 때문이다. 공유 경로가 길면 파일이 깨진 것처럼 실패한다. 인터프리터를
# 명령으로 부르면 그 제한을 아예 피한다.
#
# 런처는 자기 실제 경로에서 환경을 찾는다. 그래서 사용자 PATH 에 있는 아무
# 디렉터리로나 심볼릭 링크할 수 있다. 복사본에는 여기로 돌아올 실제 경로가 없으므로
# 애매하게 실패하는 대신 그렇다고 말한다.
#
# 런처는 설정 파일을 고르지 않는다(GENDB_CONFIG 를 정하지 않는다). 앱이
# ~/.genviewer.env -> <ROOT>/genviewer.env(sys.prefix 의 부모) 순으로 찾는다.

marker="genviewer deploy.sh 가 생성"

mkdir -p "$root/bin"

# 지난 배포가 만든 런처를 지운다. 그 사이에 이름이 바뀌거나 없어진 명령이 사라진
# 진입점을 가리킨 채 남아 있으면 안 된다. 표시가 있는 파일만 지우고 나머지는 둔다.
for old in "$root"/bin/*; do
    [ -f "$old" ] || continue
    if grep -q "$marker" "$old" 2>/dev/null; then
        rm -f "$old"
    fi
done

for cmd in $commands; do
    cat > "$root/bin/$cmd" <<LAUNCHER
#!/bin/sh
# 옆에 있는 공유 가상환경에서 $cmd 를 실행한다.
# $marker. 고치지 말 것 - 배포할 때마다 덮어쓴다.
here=\$(cd -- "\$(dirname -- "\$(readlink -f -- "\$0")")" && pwd)
if [ ! -x "\$here/../venv/bin/python" ]; then
    echo "error: \$here/../venv 에 가상환경이 없다." >&2
    echo "       이 런처는 자기 실제 경로로 환경을 찾는다. 복사본은 엉뚱한 데를" >&2
    echo "       본다. 복사하지 말고 링크할 것:" >&2
    echo "         ln -s $root/bin/$cmd <PATH 에 있는 디렉터리>/$cmd" >&2
    # 127 = '명령을 실행할 수 없음'. 배포 끝의 확인이 이 값을 본다.
    exit 127
fi
exec "\$here/../venv/bin/python" "\$here/../venv/bin/$cmd" "\$@"
LAUNCHER
    chmod 755 "$root/bin/$cmd"
done

# ---- 접속 설정
#
# 배포 디렉터리에 이 파일이 있으면 새로 온 사람이 자기 홈에 아무것도 만들지 않아도
# 실행만 하면 붙는다. 이미 있으면 절대 건드리지 않는다 - 사이트가 채워 넣은 값이다.

if [ ! -e "$root/genviewer.env" ]; then
    if [ -f "$root/src/genviewer.env.example" ]; then
        cp "$root/src/genviewer.env.example" "$root/genviewer.env"
        chmod 640 "$root/genviewer.env"
        echo
        echo "$root/genviewer.env 를 만들었다. 값을 채우고 팀 그룹 소유로 둘 것:"
        echo "  vi $root/genviewer.env"
        echo "  chgrp <팀그룹> $root/genviewer.env"
    else
        echo "note: genviewer.env.example 이 없어 설정 파일을 만들지 못했다." >&2
    fi
fi

# ---- 권한
#
# 모두가 읽고 지나갈 수 있게. 쓰는 것은 배포한 사람뿐이다.
#
# genviewer.env 는 **일부러 제외한다.** 거기엔 PGPASSWORD 가 들어 있어서, 아무나
# 읽을 수 있게 되면 앱이 스스로 실행을 거부한다(service/env_file.py 의
# check_permissions). 루트 디렉터리 자체는 지나갈 수 있어야 bin/ 에 닿는다.

chmod a+rx "$root"
chmod -R a+rX "$root/src" "$root/venv" "$root/bin"

# ---- 선택: 이미 사용자들 PATH 에 있는 디렉터리에서 명령을 보이게 한다
#
# 그런 디렉터리가 있는 곳이라면 해 둘 만하다. 이 배포가 사용자에게 요구하는 마지막
# 한 단계가 없어지고, 새로 오는 사람에게 다시 시킬 일도 없다. 복사가 아니라 링크다.

if [ -n "${DEPLOY_LINK_DIR:-}" ]; then
    [ -d "$DEPLOY_LINK_DIR" ] || {
        echo "error: DEPLOY_LINK_DIR=$DEPLOY_LINK_DIR 가 없다." >&2
        echo "       사용자들이 이미 PATH 에 두고 있는 디렉터리여야 한다." >&2
        exit 1
    }

    # 지난 배포가 만든 링크만 정리한다. 그 디렉터리는 우리 것이 아니라 사이트 것이다.
    for old in "$DEPLOY_LINK_DIR"/*; do
        [ -L "$old" ] || continue
        case "$(readlink "$old")" in
            "$root"/bin/*) rm -f "$old" ;;
        esac
    done

    for cmd in $commands; do
        link=$DEPLOY_LINK_DIR/$cmd
        if [ -e "$link" ] || [ -L "$link" ]; then
            echo "error: $link 가 이미 있고 우리가 만든 것이 아니다. 직접 치울 것." >&2
            exit 1
        fi
        ln -s "$root/bin/$cmd" "$link"
        echo "linked $link -> $root/bin/$cmd"
    done
fi

# ---- 확인

interp=$(readlink -f "$python")
case "$interp" in
    "$root"/*) ;;
    "${HOME:-/nonexistent}"/*)
        echo >&2
        echo "warning: venv 의 인터프리터가 $interp 다." >&2
        echo "         내 홈 안이라 다른 사용자가 실행할 수 없다." >&2
        echo "         uv 가 관리하는 CPython 을 거기 두었다. $root 아래에 둘 것:" >&2
        echo >&2
        echo "           rm -rf $root/venv" >&2
        echo "           UV_PYTHON_INSTALL_DIR=$root/python uv python install 3.13" >&2
        echo "           DEPLOY_PYTHON=\$(ls -d $root/python/*/bin/python3.* | head -1) \\" >&2
        echo "             $0 $root $tag" >&2
        echo >&2
        ;;
esac

# 126 은 런처에 실행 권한이 없다는 뜻, 127 은 인터프리터가 없다는 뜻이다. 그 밖의
# 값은 프로그램이 실제로 돌았다는 뜻이고, 이 확인이 보는 것은 거기까지다.
#
# 이 단계가 있는 이유: 사용자가 치는 것은 콘솔 스크립트가 아니라 런처다. 런처의
# 권한이나 경로가 틀렸으면 내일 남의 터미널에서가 아니라 여기서 드러나야 한다.
check_exec() {
    "$1" --help >/dev/null 2>&1 || rc=$?
    rc=${rc:-0}
    if [ "$rc" -eq 126 ] || [ "$rc" -eq 127 ]; then
        echo "error: $1 가 실행되지 않았다 (status $rc)" >&2
        exit 1
    fi
    unset rc
}

# 링크로도 한 번 본다. 심볼릭 링크를 지원하지 않는 파일시스템이나 엉뚱하게 풀리는
# readlink 는 거기서만 드러난다.
for cmd in $commands; do
    check_exec "$root/bin/$cmd"
    if [ -n "${DEPLOY_LINK_DIR:-}" ]; then
        check_exec "$DEPLOY_LINK_DIR/$cmd"
    fi
done

echo
echo "Deployed $tag: $commands"
echo
if [ -n "${DEPLOY_LINK_DIR:-}" ]; then
    echo "$DEPLOY_LINK_DIR 에 링크했다. 사용자들은 이미 그것을 PATH 에 두고 있다."
    echo "따로 바꿀 것이 없다."
else
    echo "사용자는 셸 프로파일에 이 한 줄을 넣는다:"
    echo "  export PATH=\"$root/bin:\$PATH\""
fi
