# genviewer

옆 디렉토리 `molgen`(Cadence SKILL 스위트 `genMOLDB`)이 입력으로 받는 CSV 를
만들고 관리하는 PySide6 데스크톱 앱.

데이터는 공유 PostgreSQL 한 곳에 있다. 예전처럼 각자 `.sqlite` 파일을 들고
다니지 않는다. 앱은 **데스크톱(RHEL 8 / 윈도우)에서** 돌고, 서버 장비에서
실행하는 것은 아무것도 없다.

## 준비

```sh
uv sync
```

## 실행

접속 정보는 `genviewer.env` 파일 하나에 둔다. 배포 디렉터리에 그 파일이 있으면
**새로 온 사람이 자기 홈에 아무것도 만들지 않아도** 그냥 실행하면 붙는다.

```sh
cp genviewer.env.example genviewer.env
vi genviewer.env
chgrp <팀그룹> genviewer.env && chmod 640 genviewer.env

uv run genviewer
```

형식은 `.env` 다. **키 이름은 libpq 그대로** 라서 새로 외울 것이 없고, 여기 없는
키(`PGSSLMODE`, `PGCONNECT_TIMEOUT` 등)도 그대로 넘어간다.

```sh
PGHOST=10.1.2.3
PGPORT=55433
PGDATABASE=molgen
PGUSER=molgen_app
PGPASSWORD=...
```

주석은 줄 전체만 쓴다 — 값 뒤의 `#` 는 값의 일부다(비밀번호에 `#` 가 흔하다).
나머지 규칙과 `PGSERVICE` 같은 대안은 `genviewer.env.example` 에 적어 두었다.

### 찾는 순서

먼저 찾은 것이 이긴다. **파일은 하나만 읽는다** — 여러 개를 겹쳐 읽으면 값이
어디서 왔는지 추적할 수 없다.

| | 어디 | 쓰는 경우 |
|---|---|---|
| 1 | `--dsn` 인자 / Connect 창 | 일회성 |
| 2 | 이미 설정된 환경변수 | `PGPASSWORD=x uv run genviewer` |
| 3 | `GENDB_CONFIG` 가 가리키는 파일 | 직접 지정. **주면 그것만 본다** |
| 4 | `~/.genviewer.env` | **개인.** 공용 값을 덮어쓴다 |
| 5 | `<배포 디렉터리>/genviewer.env` | **전원 공통.** 한 사람이 관리한다 |

무엇이 읽혔는지는 값 노출 없이 확인할 수 있다. 접속이 안 될 때 첫 번째로 볼 것:

```sh
uv run genviewer --check-config
```

아무 데도 없으면 앱이 **찾아본 경로를 전부 출력한다.**

### 비밀번호

**서버가 만들어 주지 않는다.** `createuser --pwprompt` 가 물어보면 사람이 정한다.
다만 서버가 평문으로 갖고 있지는 않다 — `password_encryption` 이 PG 14부터
`scram-sha-256` 이라 `pg_authid` 에는 SCRAM verifier 만 남고, 덤프해도 원본
비밀번호는 나오지 않는다.

`genviewer.env` 에 `PGPASSWORD` 를 적으면 팀 전원이 그 값을 쓴다. 그래서
**`chmod 640` 은 권장이 아니다. 비밀번호가 든 파일을 아무나 읽을 수 있으면 앱이
실행을 거부한다**(리눅스 한정 — 윈도우에는 대응하는 권한 개념이 없다). group
읽기는 막지 않는다. 팀이 같이 읽는 것이 이 파일의 용도다.

파일에 적기 싫으면 libpq 의 `~/.pgpass` 를 그대로 쓸 수 있다. 다만 각자 홈에
만들어야 해서 "아무것도 안 해도 붙는다" 는 성질은 없어진다.

**DSN 문자열과 셸 프로파일에는 넣지 않는다.** DSN 은 `ps` 에 그대로 보이고
(argv 는 다른 사용자도 읽는다), `.bashrc` 는 평문으로 남는다. 환경변수 자체는
남에게 보이지 않으므로(`/proc/<pid>/environ` 은 0400) 위험한 것은 값이 아니라
**그 값을 적어 둔 파일**이고, 그래서 권한을 확인한다.

`molgen_app` 을 전원이 공유하므로 비밀번호가 새면 허용 대역 안의 누구나 psql 로
붙을 수 있다. 파일을 어디 두느냐와 무관한 설계상의 성질이라, 완화책은 닿는
범위를 좁히고(`PGHBA_*`) 앱 role 에 DDL 권한을 주지 않는 것이다(아래 '서버' 절).
사람별로 나누려면 pg_hba 의 `ldap`/`gss` 인데 사람별 role 이 필요하다.

### 일회성으로 다른 데 붙기

```sh
uv run genviewer --dsn "postgresql://molgen_app@<서버IP>:55433/molgen"
```

메뉴의 **Database → Connect...** 도 같다. 그 창의 값은 **저장되지 않고 이번
접속에만 쓰인다** — 계속 쓸 값은 `genviewer.env` 에 적는다.

`127.0.0.1` 은 **그 앱이 도는 장비 자신**이다. 데스크톱에서 서버에 붙으려면 서버
주소를 적어야 한다. 내 PC 의 개발 클러스터에 붙을 때만 `127.0.0.1` 이다.

> 메인 툴바의 `Server` / `Port` / `Connect` 는 **Virtuoso 소켓**이지 데이터베이스가
> 아니다. `--host` 도 그쪽이다. 둘은 별개다.

## 명령줄

창을 띄우지 않고 할 수 있는 일이 넷 있다. 같은 `genviewer` 명령에 서브커맨드로
붙어 있고 접속 설정도 창과 똑같은 것을 쓴다.

```sh
genviewer                        # 서브커맨드가 없으면 창을 띄운다 (지금까지와 같다)

genviewer status                 # 어디에 붙어 있고 스키마와 행이 얼마나 있는지
genviewer processes              # process 목록과 각 process 의 device 수
genviewer load ./devices.csv     # CSV 를 불러온다
genviewer export sf2p ./out.csv  # process 하나를 파일로 낸다 (.xlsx 도 된다)
```

```
$ genviewer status
설정 파일: /opt/genviewer/genviewer.env
찾아본 곳:
  /home/pdh99/.genviewer.env
  /opt/genviewer/genviewer.env <-- 이것
적용된 값:
  PGHOST=10.1.2.3
  PGPORT=55433
  PGDATABASE=molgen
  PGUSER=molgen_app
  PGPASSWORD=(설정됨)
로그 파일: /home/pdh99/.genviewer/genviewer.log  (GENDB_LOG 로 바꿀 수 있다)
접속 대상: host=10.1.2.3 port=55433 dbname=molgen user=molgen_app
접속: 됨 (0.04초)
서버: PostgreSQL 16.2
계정: molgen_app@molgen
스키마: 테이블 16개 모두 있음
내용: process 2개, device 128개
```

**device 를 더하고 지우는 것, 탭 내용을 고치는 것은 창에서만 한다.** 그쪽은
낙관적 잠금과 충돌 해결이 얽혀 있어서 명령줄로 흉내 내면 둘 중 하나는 거짓말이
된다.

- `--dsn` 은 어디에나 붙는다: `genviewer status --dsn "postgresql://..."`.
- `load` 는 **넣을 때마다 쌓인다.** 같은 파일을 두 번 넣으면 device 가 두 배가
  된다(아래 'CSV 컬럼과 탭'). 그래서 몇 개를 새로 만들었는지 항상 찍는다. 큰
  파일을 위해 `statement_timeout` 을 풀고 도는데, 직접 정해 뒀으면 그 값을 따른다.
- `export` 는 process 를 통째로 낸다. device 를 골라서 내보내는 것은 창 쪽이다.
  device 가 하나도 없으면 빈 파일을 만들지 않고 그렇다고 말한다.
- 종료 코드는 `0` 성공 / `1` 실패 / `2` 사용법 오류 / `130` Ctrl-C 다. 스크립트에서
  `if genviewer status; then ...` 로 쓸 수 있다.
- 실패는 한 줄 문장으로 나온다. 트레이스백까지 보려면 `-v` 를 준다.
- `genviewer --check-config` 는 그대로 있다. `status` 가 그 내용을 다 담고 접속까지
  해 본다.

## 배포

개발 트리에서 그냥 돌리는 것과, 여러 사람이 쓰는 설치본은 분리한다. 설치 단위는
**git 태그**다.

```sh
./tools/deploy.sh /opt/genviewer v0.3.0 https://git.example/org/gendb.git
./tools/deploy.sh /opt/genviewer v0.4.0     # 그 다음부터는 URL 없이
./tools/deploy.sh /opt/genviewer v0.3.0     # 되돌리기 = 옛 태그로 다시
```

```
/opt/genviewer/
├── genviewer.env   접속 설정. 업그레이드해도 건드리지 않는다
├── src             태그에 detach 된 체크아웃
├── venv            프로젝트와 의존성
└── bin             사용자가 PATH 에 넣는 유일한 디렉터리
```

**uv 는 배포할 때만 필요하고 쓸 때는 필요 없다.** `bin/` 의 런처가 venv 의
인터프리터를 직접 부르므로 앱을 쓰는 사람은 uv 도 자기 파이썬도 없어도 된다.
`[project.scripts]` 에 있는 명령이 전부 나온다(`genviewer`, `genviewer-init-db`,
`genviewer-import-sqlite`).

사용자가 셸 프로파일에 한 줄을 넣거나,

```sh
export PATH="/opt/genviewer/bin:$PATH"
```

사이트에 이미 모두의 PATH 에 있는 디렉터리가 있다면 그마저 없앨 수 있다:

```sh
DEPLOY_LINK_DIR=/usr/local/bin ./tools/deploy.sh /opt/genviewer v0.3.0
```

- 태그가 아닌 것(브랜치 이름)을 주면 **거부한다** — `refs/tags/` 로만 체크아웃한다.
  브랜치에 고정하면 "v0.3.0 배포본" 이 나중에 다른 커밋을 가리키게 된다.
- `uv sync --frozen --no-editable` 이라 `uv.lock` 이 그대로 재현되고, **코드는
  site-packages 의 복사본에서 돈다.** `src` 를 고쳐도 아무의 앱도 바뀌지 않는다 —
  버전을 안 올리고 내용만 바뀌는 일이 없어야 태그에 고정한 의미가 있다.
- `genviewer.env` 가 없으면 예시에서 심고 `640` 으로 둔다. **있으면 절대 덮지
  않는다.** 트리는 `a+rX` 로 열지만 이 파일만은 제외한다 — 거기엔 비밀번호가 있고,
  아무나 읽게 되면 앱이 스스로 실행을 거부한다.
- 마지막에 **만든 런처를 실제로 실행해 본다.** 사용자가 치는 것은 콘솔 스크립트가
  아니라 런처다. 권한이나 경로가 틀렸으면 내일 남의 터미널이 아니라 여기서 드러나야
  한다. `DEPLOY_LINK_DIR` 을 썼으면 링크로도 한 번 더 본다.
- venv 인터프리터가 **배포한 사람 홈 안**이면 경고한다. uv 가 관리하는 CPython 을
  쓰면 그렇게 되는데, 그러면 배포한 사람만 실행되고 나머지는 `Permission denied` 를
  본다. `UV_PYTHON_INSTALL_DIR=<루트>/python uv python install 3.13` 으로 파이썬을
  루트 안에 두고 `DEPLOY_PYTHON` 으로 그것을 가리켜 다시 돌린다.

**설치 중에는 앱을 띄우지 않는 편이 좋다.** 교체가 제자리에서 일어나므로 그 사이에
실행하면 반쯤 바뀐 트리를 볼 수 있다(파이썬이 모듈을 그때그때 import 한다).
사람들이 쓰지 않는 시간에 돌린다.

배포 대상은 리눅스다.

### RHEL 8 제약

PySide6 는 **6.9.3** 에 고정돼 있다. 이게 `manylinux_2_28` 휠을 내는 마지막
릴리스이고, RHEL 8 의 glibc 가 2.28 이다. 6.10 부터는 `manylinux_2_34` 라서
RHEL 9 이상에서만 설치된다. 그 휠이 `Requires-Python: <3.14` 이므로 인터프리터도
**3.13** 으로 고정된다 — `.python-version` 과 `requires-python = ">=3.13,<3.14"`
가 그렇게 맞춰져 있다. 같은 이유로 앱은 RHEL 7 에 올라가지 않는다(Qt 6 이
glibc 2.28 을 요구한다). 서버 OS 와는 무관하다 — 아래 '서버' 절.

나머지 의존성은 RHEL 8 에서 더 조이지 않는다(pandas/numpy 는 `manylinux_2_28`,
psycopg-binary 는 glibc 2.17). 올리기 전 교차 확인:

```sh
uv pip compile pyproject.toml --python-version 3.13 --python-platform x86_64-manylinux_2_28
```

배포 호스트에 Python 3.13 이 없으면 `uv python install 3.13` 이 필요하고, 이건
네트워크나 미리 채워둔 `UV_PYTHON_INSTALL_DIR` 를 쓴다.

## CSV 컬럼과 탭

탭 하나가 molgen CSV 컬럼 하나다. 원본은 `config/tab_config.json` 이고, 거기서
테이블 DDL·화면의 탭·import·export 가 전부 만들어진다. 컬럼별 셀 문법의 기준은
옆 디렉토리 `molgen` 이다.

| | |
|---|---|
| `molgen/genMOLDB_config.il` 의 `pexGenDB_GenDev_Get_Header_Type()` | 컬럼 목록과 변환 타입. `tab_config.json` 의 `"parse"` 가 이 표를 옮겨 적은 것이다 |
| `molgen/CSV_COLUMNS.md` | 셀 문법 레퍼런스 (AddLayer / AddFGR 계열, ForcedInstSchParam) |

값 후보와 입력 검증은 `config/delegate_config.json` 이다 (`items`,
`items_by_celltype`, `strict`, `required`, `syntax`, `pattern`).

**탭을 추가한 뒤에는 기존 데이터베이스에도 `genviewer-init-db` 를 다시 돌려야
한다.** 전부 `CREATE TABLE IF NOT EXISTS` 라서 여러 번 돌려도 안전하고 기존
데이터는 건드리지 않는다. 공유 서버라면 `--owner` 를 같이 준다 — 새 테이블이
소유자 명의로 만들어져 앱 role 권한이 자동으로 따라간다(아래 '서버' 절).

### 이름이 같은 행은 각각 device 가 된다

**CSV 행 하나가 device 하나다.** 같은 `CdsLibName` + `InstCellName` 이 여러 행에
나와도 각각 별개로 들어간다. 한동안 `UNIQUE (process_id, name)` 이 있어서 그런
행들이 device 하나로 합쳐졌고 — 두 행의 자식 행이 한 탭에 섞여 보였다 — 사람이
같은 이름으로 device 를 추가하면 저장이 SQL 에러로 죽었다. 이름은 식별자가 아니라
표시용 값이다. 식별은 `id` 가 하고, 참조하는 쪽도 전부 `id` 를 쓴다.

**그래서 CSV 는 불러올 때마다 새로 쌓인다.** 같은 파일을 두 번 넣으면 device 가
두 배가 된다. 불러오기가 끝나면 *"device N개를 새로 추가했다"* 를 보여주므로 그
숫자로 알아챌 수 있다. 되돌리려면 그 device 들을 지운다.

**이미 쓰고 있는 데이터베이스에는 `genviewer-init-db` 를 한 번 더 돌려야 옛 제약이
없어진다.** `CREATE TABLE IF NOT EXISTS` 는 있는 테이블을 손대지 않기 때문이다.
DDL 이 제약 이름을 카탈로그에서 찾아 떼어내므로 손으로 만든 이름이어도 걸린다.
데이터는 건드리지 않는다.

## 기존 .sqlite 파일 옮기기

```sh
# 무엇이 들어갈지 먼저 본다
uv run genviewer-import-sqlite --sqlite mine.sqlite --dry-run

# 여러 사람 파일을 각자 이름으로 구분해서 넣는다 (초기 대량 이관에 권장)
uv run genviewer-import-sqlite --sqlite mine.sqlite --on-conflict rename
```

`--on-conflict` 는 같은 이름의 **process** 가 이미 있을 때의 정책이다.
`fail`(기본) / `rename` / `merge` / `skip`.

device 이름 중복은 막지 않는다. 원본에 같은 이름이 여럿 있으면 그대로 옮겨진다.
`merge` 로 같은 파일을 다시 돌려도 늘어나지 않는다 — 같은 이름끼리 순서대로
짝지어 갱신한다.

## 동시 편집

여러 명이 같은 DB 를 동시에 편집한다. 저장할 때 다른 사람이 먼저 바꾼 것이
있으면 **다시 읽기 / 덮어쓰기 / 취소** 를 묻는다. 내가 화면에 안 들고 있는
device 는 절대 지워지지 않는다 — 명시적으로 지운 것만 삭제된다.

10초마다 지금 보고 있는 process 가 바뀌었는지 확인한다. 바뀌었으면 device
목록 위에 줄이 하나 뜬다.

> 이 process 가 dh991 님에 의해 변경되었습니다.  [새로고침] [닫기]

**자동으로 다시 읽지 않는다.** 편집 중인 내용이 말없이 사라지는 것은 이번
작업에서 없애려던 바로 그 동작이다. 언제 읽을지는 사용자가 정한다.

DB 호출은 워커 스레드에서 돈다. 서버가 죽었거나 다른 사용자의 잠금 뒤에서
기다리는 동안에도 창이 굳지 않는다. 다만 저장·접속이 끝날 때까지 입력은
받지 않는다 — 그 사이에 화면을 바꾸면 방금 보낸 것과 다른 내용이 저장된
것처럼 보이기 때문이다.

## 에러와 로그

DB 에러는 **메시지 박스로 보여주고 같은 내용을 파일에도 남긴다.** 배포본은
런처로 뜨기 때문에 붙어 있는 터미널이 없다 — 예전에는 `print` 와 트레이스백이
아무 데도 남지 않아서, 사용자는 화면이 안 바뀌는 것만 봤다.

| | |
|---|---|
| 위치 | `~/.genviewer/genviewer.log` (`GENDB_LOG` 로 바꾼다) |
| 크기 | 1MB 마다 돌려 쓰고 3개까지 보관 |
| 경로 확인 | `genviewer --check-config` 가 찍어준다 |

자주 보는 것은 타임아웃 둘이다. 풀이 `lock_timeout` 5초와
`statement_timeout` 15초를 **일부러** 걸어 두므로, 사람이 몰리면 "다른 사용자가
저장하는 중이다" 나 "처리가 너무 오래 걸려 서버가 취소했다" 가 나온다. 둘 다
다시 시도하면 된다.

**비밀번호는 로그에 남지 않는다.** `password=` / `PGPASSWORD=` 와 접속 URL 안의
비밀번호는 기록되기 직전에 가려진다 — 트레이스백 안에 있어도 마찬가지다.
psycopg 의 접속 실패 예외에는 conninfo 가 통째로 들어 있어서 이 가드가 실제로
필요하다.

화면 아래 로그 패널은 창을 닫거나 Clear 를 누르면 사라진다. 사람에게 무언가를
받아야 할 때는 위 파일이다.

## 개발

코드는 전부 `src/genviewer/` 아래의 한 패키지다.

```
src/genviewer/
  cli.py         명령줄 진입점 (`genviewer` 명령 / `python -m genviewer`)
  main.py        창 띄우기. cli.py 가 서브커맨드 없이 불릴 때만 쓴다
  config/        tab_config.json, delegate_config.json — 스키마와 UI 의 원본
  service/       DB 계층. Qt 를 import 하지 않는다 (테스트가 GUI 없이 돈다)
                 config.py 접속 설정 / env_file.py 설정 파일 / pool.py 풀
                 schema.py DDL / diagnostics.py 상태 진단 / repo/ 쿼리
  models/ views/ controllers/ delegates/ dialogs/   Qt MVC
  net/           Virtuoso 소켓
  utils/
  scripts/       관리 도구 (init_db, import_sqlite)
tools/           initdb.sh(서버 클러스터), deploy.sh(배포)
tests/
```

### 개발 클러스터 (한 번만)

내 PC 에 혼자 쓰는 클러스터를 세운다. 포트는 `55433` 이 기본값이다(fmserver 가
55432 라서 겹치지 않게). 여러 사람이 붙는 실제 서버는 아래 '서버' 절이다.

```sh
./tools/initdb.sh                                     # 리눅스

# 윈도우 Git Bash 에서는 pg_ctl start 가 셸에 매여 프롬프트가 안 돌아온다.
# SKIP_START=1 로 두고 PowerShell Start-Process 로 따로 띄울 것.
SKIP_START=1 PGBIN="/c/Program Files/PostgreSQL/18/bin" ./tools/initdb.sh
```

`PostgreSQL/18` 은 개발 PC 에 깔린 경로일 뿐 요구 버전이 아니다.

```sh
uv run genviewer-init-db --dry-run        # 접속하지 않고 실행될 SQL 만 본다
uv run genviewer-init-db --dsn "postgresql://<내계정>@127.0.0.1:55433/molgen"
```

### 검사

```sh
uv run ruff check .
uv run pytest                     # DB 필요한 테스트는 skip 된다

# DB 를 붙이면 전부 돈다. 테스트용 데이터베이스를 만들고 끝나면 지운다.
# 관리자 DSN 이어야 한다 - 픽스처가 CREATE DATABASE 를 하고, 권한 테스트는
# CREATE ROLE 까지 한다 (못 하면 그 테스트만 skip 된다).
GENDB_TEST_PG_DSN="postgresql://<user>@127.0.0.1:55433/postgres" uv run pytest
```

## 환경변수

`genviewer.env` 에 적는 것과 셸에서 export 하는 것이 같은 목록이다.

| | |
|---|---|
| `PGHOST` `PGPORT` `PGDATABASE` `PGUSER` `PGPASSWORD` `PGSERVICE` `PGSSLMODE` … | libpq 표준. 접속 정보는 이걸로 준다 |
| `GENDB_PG_DSN` | 접속 문자열 한 줄로 주는 대안. 위 `PG*` 보다 우선한다 |
| `GENDB_CONFIG` | 설정 파일 경로. 주면 **그 파일만** 본다 |
| `GENDB_APP_USER` | `updated_by` 에 기록할 이름 (기본: 로그인 계정) |
| `GENDB_LOG` | 로그 파일 경로 (기본 `~/.genviewer/genviewer.log`) |
| `GENDB_PG_POOL_MIN` / `_MAX` | 커넥션 풀 크기 (기본 1 / 4) |
| `GENDB_PG_CONNECT_TIMEOUT` | 접속 타임아웃 초 (기본 5) |
| `GENDB_PG_LOCK_TIMEOUT_MS` | 행 잠금 대기 한도 (기본 5000) |
| `GENDB_PG_STATEMENT_TIMEOUT_MS` | 쿼리 한도 (기본 15000) |
| `GENDB_TEST_PG_DSN` | 테스트용 관리 DSN. 없으면 DB 테스트가 skip |
| `GENDB_INIT_PASSWORD` | `genviewer-init-db --create-role` 이 쓸 비밀번호 (없으면 프롬프트) |

## 서버 — RHEL 7 / PostgreSQL 15

**genviewer 에는 서버 프로그램이 없다.** 서버 장비에서 도는 것은 PostgreSQL
하나뿐이고, GUI 가 psycopg 로 거기에 직접 붙는다(`service/pool.py`). fmserver 와
다른 지점이다 — fmserver 는 FastAPI 앱이 있어서 uvicorn 이 그걸 띄우지만, 여기엔
띄울 대상이 없다. 동시 편집은 서버 프로세스가 아니라 `device.version` 낙관적
잠금이 처리한다(`tests/test_concurrency.py`).

```
fmserver:   클라이언트 → HTTP → fm-server(FastAPI) → DB
genviewer:  클라이언트 ──────── psycopg ──────────→ PostgreSQL
```

**최소 버전은 PostgreSQL 10** 이다. 버전을 올리는 문법은 `service/schema.py` 의
`BIGINT GENERATED BY DEFAULT AS IDENTITY` 하나뿐이다. 실제 배포는 **15** 이고
(PGDG 가 RHEL 7 에 내는 마지막 메이저), 개발 클러스터가 18이어도 SQL 은 똑같이
돈다. **클라이언트 OS 는 서버 OS 와 무관하다** — `psycopg[binary]` 가 libpq 를
번들한다.

> RHEL 7 은 2024-06 에 EOL 됐다. OS 보안 패치가 더 오지 않는 장비다.

### 순서

| | 어디서 | 필요한 것 |
|---|---|---|
| 1 | `tools/initdb.sh` — 클러스터 생성·기동 | **서버**, PG 패키지만 |
| 2 | `createuser` x2 — role 두 개 | **서버**, PG 패키지만 |
| 3 | `ALTER DATABASE molgen OWNER TO molgen_owner` | **서버**, PG 패키지만 |
| 4 | `init_db` — 스키마와 권한 | 서버 **또는** 데스크톱, psycopg |

4번은 네트워크로 붙으므로 데스크톱에서 돌려도 된다. 다만 슈퍼유저는 비밀번호가
없어서(아래) 원격 접속이 안 되니, 그러려면 소유자 role 에 `--createdb` 와
비밀번호를 줘야 한다. **서버에서 돌리는 쪽이 단순하다.**

서버 파이썬이 3.9 여도 된다. 이 도구들은 GUI 를 import 하지 않고 의존성이
psycopg 하나뿐이라, 패키지를 설치하지 않고 소스에서 바로 돌린다:

```sh
pip install "psycopg[binary]"
PYTHONPATH=src python3.9 -m genviewer.scripts.init_db --dry-run
```

### 1. 클러스터

PGDG el7 패키지는 `/usr/pgsql-15/bin` 에 깔리고 **PATH 에 들어가지 않는다.**
`PGDATA` 는 패키지 기본 경로로 둔다 — SELinux 라벨과 `postgresql-15.service` 가
거기에 맞춰져 있어서, 홈 디렉터리에 두면 그 둘을 손으로 해결해야 한다.

```sh
sudo -u postgres env PGBIN=/usr/pgsql-15/bin PGDATA=/var/lib/pgsql/15/data \
    LISTEN_ADDRESSES='*' PGAUTH_LOCAL=peer PGAUTH_HOST=scram-sha-256 \
    PGHBA_CIDR=10.0.0.0/8 PGHBA_DB=molgen PGHBA_USER=molgen_app \
    ./tools/initdb.sh
```

**인증을 왜 이렇게 나누나.** `initdb --auth=X` 는 local 과 host 를 한꺼번에 정한다:

| local | host | 슈퍼유저 비번 | 결과 |
|---|---|---|---|
| `trust` | `trust` | 불필요 | 개발 기본값. 원격이 무인증 — 공유 서버엔 불가 |
| `scram` | `scram` | **필수** | `initdb` 가 *"must specify a password for the superuser"* 로 거부 |
| `trust` | `scram` | 불필요 | **쉘 계정이 있는 사람 누구나 슈퍼유저.** 안 된다 |
| `peer` | `scram` | 불필요 | 권장 |

`trust` 는 "비밀번호 없음" 이 아니라 **"인증 없음"** 이다 — 그 소켓에 닿는 사람이
`postgres` 를 포함한 아무 role 로나 붙는다. `peer` 는 커널에 유닉스 사용자를 물어
확인하므로 비밀번호보다 강하고, 보관·교체할 비밀이 아예 생기지 않는다.
(윈도우에는 유닉스 소켓이 없어서 개발 기본값은 루프백 + `trust` 로 남는다.)

없는 것은 **슈퍼유저 비밀번호뿐**이다. `molgen_app` 은 TCP 로 붙으니 `host` 줄 →
scram → 비밀번호가 필요하다. 그리고 TLS 를 켜지 않으면 scram 은 비밀번호만
지키고 데이터는 평문으로 흐른다(`PGSSLMODE`).

root 로 따로 해야 하는 것 (스크립트는 sudo 를 쓰지 않는다):

| | |
|---|---|
| 방화벽 | `firewall-cmd --permanent --add-port=55433/tcp` 후 `firewall-cmd --reload`. 막혀 있으면 **서버 로그에 아무것도 안 남고** 클라이언트만 타임아웃된다 |
| 재부팅 생존 | `systemctl enable --now postgresql-15`. `pg_ctl` 로 띄운 것은 재부팅하면 안 올라온다. 유닛은 `-p` 인자를 주지 않으므로 포트가 `postgresql.conf` 에 있어야 하는데, `initdb.sh` 가 적어 둔다 |
| SELinux | 기본 PGDATA 를 쓰면 해당 없음. `getenforce` 로 먼저 확인할 것. 증상은 퍼미션이 멀쩡한데 나는 `Permission denied` 이고 증거는 `ausearch -m avc -ts recent` 에만 있다. 옮겨야 한다면 `semanage fcontext -a -t postgresql_db_t "<PGDATA>(/.*)?"` 후 `restorecon -R` |

### 2-4. role 두 개와 스키마

| role | 쓰는 곳 | 권한 |
|---|---|---|
| `molgen_owner` | `init_db` 만 | 스키마 소유. DDL |
| `molgen_app` | 모두의 `genviewer.env` | 테이블 DML 만 |

**전원이 소유자로 붙으면 안 된다** — 아무나 `DROP TABLE` 을 할 수 있다. 누가
고쳤는지는 DB role 이 아니라 `updated_by`(OS 로그인)로 남으므로
(`utils/user.py`), 접속 계정을 공유해도 귀속은 흐려지지 않는다.

```sh
# 2. role 두 개. -h 를 주지 않는다 - 유닉스 소켓이라야 peer 로 붙는다.
#    비밀번호는 argv 로 주지 않는다 (ps 에 남는다).
sudo -u postgres /usr/pgsql-15/bin/createuser -p 55433 --pwprompt molgen_owner
sudo -u postgres /usr/pgsql-15/bin/createuser -p 55433 --pwprompt molgen_app

# 3. 데이터베이스 소유자를 넘긴다. initdb.sh 의 createdb 가 이미 molgen 을
#    만들어 뒀고, 그 주인은 스크립트를 돌린 계정(위 예에서는 postgres)이다.
sudo -u postgres /usr/pgsql-15/bin/psql -p 55433 \
    -c 'ALTER DATABASE molgen OWNER TO molgen_owner'

# 4. 스키마(테이블) + 권한. --dry-run 으로 먼저 볼 것.
sudo -u postgres env PYTHONPATH=src python3.9 -m genviewer.scripts.init_db \
    --dsn "postgresql:///molgen?host=/var/run/postgresql&port=55433" \
    --owner molgen_owner --app-role molgen_app
```

**3번을 빼먹으면** 4번이 `SET ROLE` 직후 `permission denied for schema public` 로
멈춘다. PostgreSQL 15 부터 `public` 스키마는 데이터베이스 소유자만 쓸 수 있기
때문이다.

이 절차에서 role 을 만드는 것은 2번이고 `init_db` 는 권한만 붙인다
(`--create-role` 옵션이 따로 있지만 여기서는 쓰지 않는다). `--app-role` 을 빼면
**테이블만 만들고 GRANT 를 하지 않아서** 앱이 `permission denied for table device`
를 받는다.

`--owner` 는 이름표가 아니다. `init_db` 가 DDL 앞에서 그 role 로 `SET ROLE` 을
해서 **테이블 주인을 정한다.** 기본 권한(`ALTER DEFAULT PRIVILEGES`)이 그 role 에
붙기 때문에, 나중에 탭을 추가해도 새 테이블 권한이 자동으로 따라간다.

`public` 대신 전용 스키마를 쓰지는 않는다. 데이터베이스를 통째로 molgen 전용으로
쓰는 한 그 안의 `public` 은 이미 우리 것뿐이고, PG 15 가 소유자 외의 생성을 이미
막는다. 한 데이터베이스를 다른 앱과 나눠 써야 할 때만 의미가 있다.
