# Architecture Decision Records

## 철학
이미 쓰고 있는 도구다. 동작은 보존하고, 고치는 것은 에러·버그(크래시, 데이터 손실, 잘못된 결과, 비밀 노출)뿐이다. 새 인프라는 형제 저장소(Pexorche, fmserver, molgen, pexqa)에 같은 것이 있으면 그 형태를 따른다. 더 나은 설계라는 논증만으로 이미 돌아가는 방식을 바꾸지 않는다. 사람 몇이 쓰는 규모에 맞게 단순한 쪽을 고른다.

---

### ADR-001: 공유 PostgreSQL, 서버 프로그램 없음
**결정**: 각자 들고 다니던 `.sqlite` 대신 PostgreSQL 데이터베이스 하나(`molgen`)를 모두가 쓴다. GUI와 CLI가 psycopg로 직접 붙는다. fmserver처럼 FastAPI 서버를 두지 않는다.
**이유**: 데이터가 사람마다 갈라지는 것이 문제였다. 동시 편집은 서버 프로세스 없이도 낙관적 잠금(ADR-004)으로 풀린다. 서버 장비(RHEL 7)에서 관리할 우리 프로그램이 없어진다.
**트레이드오프**: 모든 클라이언트가 같은 DB role 비밀번호를 갖는다(ADR-010으로 범위를 좁힌다). 서버 쪽 검증 계층이 없어서 규칙은 앱 코드와 DDL이 지킨다.
**phase 5 정리**: 옛 `.sqlite` 이관 도구(`genviewer-import-sqlite`)와 레거시 SQLite 스키마 렌더러·픽스처(`db/init.sqlite`)를 지웠다(2026-10-17 승인, ADR-015의 버그 수정 밖 정리). 옛 파일을 옮겨야 하면 그 이전 커밋에서 도구를 꺼낸다.

### ADR-002: PySide6 6.9.3 + Python 3.13 고정
**결정**: `PySide6==6.9.3`, `requires-python = ">=3.13,<3.14"`, `.python-version` 3.13.
**이유**: 6.9.3이 `manylinux_2_28` 휠을 내는 마지막 릴리스다. RHEL 8의 glibc가 2.28이고, 6.10부터는 2_34(RHEL 9+)다. 그 휠이 `Requires-Python <3.14` 라서 인터프리터도 3.13이 된다.
**트레이드오프**: Qt 보안·버그 수정을 더 받지 못한다. 앱은 RHEL 7에서 돌지 않는다. pandas·numpy도 2_28이라 여유가 없다. 의존성을 올리기 전에 `uv pip compile … --python-platform x86_64-manylinux_2_28` 로 확인한다.

### ADR-003: tab_config.json 이 단일 원본
**결정**: 탭 하나 = molgen CSV 컬럼 하나 = 자식 테이블 하나. `config/tab_config.json` 에서 DDL(`service/schema.py`), 화면 탭, CSV import(`parse`, `row_per_token`), export, 허용 컬럼 목록(`TABLE_COLUMNS`)이 모두 만들어진다. `parse` 는 molgen `genMOLDB_config.il` 의 `pexGenDB_GenDev_Get_Header_Type()` 을 옮겨 적은 것이다.
**이유**: 컬럼 정의가 여러 곳에 있으면 서로 어긋난다. 셀 문법의 기준은 molgen(`CSV_COLUMNS.md`)이다.
**트레이드오프**: DDL이 `CREATE … IF NOT EXISTS` 뿐이라 **기존 탭에 컬럼을 추가하면 마이그레이션이 없다**(새 탭 추가는 `init_db` 재실행으로 된다). JSON 키 구조를 바꾸면 모든 경로가 함께 바뀐다.

### ADR-004: 낙관적 잠금, 자동으로 다시 읽지 않음
**결정**: `device.version` 을 쓰기마다 올린다. 저장은 process별 advisory lock + `FOR UPDATE` 후 화면이 들고 있던 version과 비교해 다르면 `StaleWriteError` 를 내고, 사용자에게 다시 읽기/덮어쓰기/취소를 묻는다. 화면에 없는 device는 지우지 않는다(명시적으로 지운 id만). 남이 바꾼 것은 10초 폴링(etag)으로 배너만 띄운다.
**이유**: 예전에는 저장이 화면 내용으로 DB를 통째로 덮어써서 남의 작업이 사라졌다(PostgreSQL 이전 작업의 Phase 5, 하네스 phase 아님). 편집 중인 내용이 말없이 사라지는 것이 막으려던 바로 그 동작이라 자동 reload는 하지 않는다.
**트레이드오프**: 충돌은 저장할 때에야 알게 된다. 덮어쓰기를 고르면 남의 수정을 의도적으로 지운다. 탭 저장은 통째 교체라 셀 단위 병합이 없다.
**phase 3 보강**: 저장 함수가 결과(bool)를 돌려주고, 취소된 저장 뒤에는 "Saved" 를 띄우지 않으며 다른 process·device로 옮기지 않는다. 옮기던 중 멈추면 process 콤보만 시그널 없이 되돌리고 device 표 선택은 되돌리지 않는다(선택을 코드로 바꾸면 전환 처리가 다시 들어온다). 탭은 내 device 저장이 올린 version을 +1일 때만 따라간다. 덮어쓰기(+2 이상) 뒤의 탭 저장은 남의 변경이 끼어 있으므로 다시 충돌로 묻는다(그 문구의 마지막 수정자는 나다).
**phase 4 보강**: 되돌릴 process가 그 사이 지워졌으면(콤보 목록에 없으면) 되돌리지 않고 넘어간다. 콤보와 device 표가 다른 process를 가리키지 않게 하려는 것이고, 그 편집은 저장할 곳이 없다(2026-10-17 승인). 창 닫기와 Virtuoso device 목록 응답(device 표를 다시 읽는다)도 저장 안 한 편집이 있으면 기존 질문 문구로 묻는다. 창 닫기는 Yes면 저장에 성공했을 때만 닫는다(2026-10-17 승인). 정렬은 기준점을 바꾸지 않는 저장 안 한 변경이다(지운 device·편집 표시·undo가 남는다).

### ADR-005: change_log 는 앱이 같은 트랜잭션에서 쓴다
**결정**: 누가 언제 무엇을 바꿨는지 `change_log` 테이블에 앱이 저장과 같은 트랜잭션으로 쓴다(`repo/audit.write(cur, …)`). 값이 실제로 바뀐 행만 남긴다. 외래키를 걸지 않고, 지워진 것은 자식 행까지 `detail`(JSONB)에 통째로 남긴다. 트리거를 쓰지 않는다. 자동 삭제 없음(`--purge-before`). `genviewer log` 는 `--help` 에 숨긴다(접근 통제가 아니라 요청에 따른 숨김).
**이유**: 전원이 같은 role이라 트리거의 `current_user` 로는 사람을 구분할 수 없다. 탭 저장은 통째 교체라 행 트리거면 셀 하나 고친 저장이 로그 십수 줄이 된다. FK를 걸면 cascade가 이력까지 지운다. 저장이 실패하면 이력도 없어야 한다.
**트레이드오프**: `psql` 로 직접 고친 것은 남지 않는다.

### ADR-006: device 이름 중복 허용, CSV 는 누적
**결정**: `UNIQUE (process_id, name)` 을 없앴다. 식별은 `id` 로만 한다. CSV 한 행이 device 하나이고, 불러올 때마다 새로 쌓인다(만든 개수를 항상 보여준다). `init_db` 가 옛 제약을 카탈로그에서 찾아 뗀다.
**이유**: 같은 이름이 여러 행에 나오는 CSV가 실제로 있고, 제약이 있을 때는 두 행이 한 device로 합쳐지거나 사람이 같은 이름을 추가하면 저장이 SQL 에러로 죽었다.
**트레이드오프**: 같은 파일을 두 번 넣으면 device가 두 배가 된다. 되돌리려면 지운다.

### ADR-007: 접속 설정은 .env 파일 하나, libpq 키 그대로
**결정**: `genviewer.env` 에 `PGHOST`/`PGPORT`/`PGDATABASE`/`PGUSER`/`PGPASSWORD` 등 libpq 이름을 그대로 쓴다. 찾은 첫 파일 **하나만** 읽고(겹쳐 읽지 않음), 이미 있는 환경변수가 이긴다. 비밀이 든 파일을 other가 읽을 수 있으면 실행을 거부한다(리눅스). 줄 전체 주석만, 값 뒤의 `#` 는 값이다.
**이유**: 새로 외울 키가 없다. 파일을 여러 개 겹치면 값의 출처를 추적할 수 없다. 배포 디렉터리에 두면 새로 온 사람이 홈에 아무것도 만들지 않아도 붙는다. DSN 문자열(argv에 보임)과 셸 프로파일(평문)에는 비밀번호를 두지 않는다.
**트레이드오프**: 개인 파일이 있으면 공용 파일은 통째로 안 읽힌다(키 단위 병합 아님). 팀 전원이 같은 비밀번호를 공유한다.

### ADR-008: 일부러 거는 타임아웃
**결정**: 커넥션마다 `lock_timeout=5000ms`, `statement_timeout=15000ms`, `connect_timeout=5s`. `GENDB_PG_*` 로 바꿀 수 있다. CLI `load` 는 `statement_timeout` 을 푼다(직접 정했으면 그 값).
**이유**: 다른 사용자의 `FOR UPDATE` 뒤에서 창이 끝없이 굳으면 안 된다. 사람이 몰리면 "다른 사용자가 저장하는 중이다"(55P03), "처리가 너무 오래 걸려 서버가 취소했다"(57014)가 정상적으로 나오고, 다시 시도하면 된다.
**트레이드오프**: 큰 작업은 타임아웃에 걸릴 수 있다. 앱이 `options`/`connect_timeout` 을 명시하므로 `PGOPTIONS`·`PGCONNECT_TIMEOUT` 은 먹지 않는다.

### ADR-009: DB 호출은 워커 스레드, 그동안 입력을 막는다
**결정**: 접속·저장·CSV 불러오기는 `run_blocking`(QThread + 이벤트 루프 + `ExcludeUserInputEvents` + 대기 커서), 폴링·History는 `Task`(비동기)로 돈다.
**이유**: 서버가 죽었거나 남의 잠금 뒤에서 기다리는 동안 창이 굳지 않아야 한다. 저장 중에 화면을 바꾸면 방금 보낸 것과 다른 내용이 저장된 것처럼 보이므로 입력은 받지 않는다.
**트레이드오프**: 아직 GUI 스레드에서 동기로 도는 호출이 남아 있다(ARCHITECTURE 스레딩 절). 입력은 버려지는 것이 아니라 끝난 뒤 처리된다.
**phase 4 보강**: 시작할 때의 접속도 창이 다 이어진 뒤(`QTimer.singleShot(0)`) 돈다. 그래야 시작 접속 실패와 첫 조회 실패가 로그 패널·알림에 보인다(2026-10-17 승인). 다시 접속할 때는 새 DB를 먼저 열고, 실패하면 지금 DB를 계속 쓴다. 옛 DB는 도는 폴링이 끝난 뒤에 닫는다. 작업 중(`is_busy()`)에는 창 닫기를 무시한다(저장 안에서 저장이 다시 돌지 않게).

### ADR-010: role 두 개, peer + scram
**결정**: `molgen_owner`(스키마 소유, DDL, `init_db` 만)와 `molgen_app`(테이블 DML만, 모두의 `genviewer.env`). `init_db --owner` 가 DDL 앞에서 `SET ROLE` 해 주인을 정하고 `ALTER DEFAULT PRIVILEGES` 를 건다. 클러스터는 `local=peer`, `host=scram-sha-256`, 원격은 `PGHBA_CIDR`/`PGHBA_DB`/`PGHBA_USER` 로 좁힌다. 전용 스키마 대신 `public`.
**이유**: 전원이 소유자로 붙으면 아무나 `DROP TABLE` 을 할 수 있다. 슈퍼유저 비밀번호를 만들지 않으려면 local을 peer로 둔다(`trust` 는 "인증 없음"). PG 15부터 `public` 은 DB 소유자만 쓸 수 있어 `ALTER DATABASE … OWNER` 가 필요하다.
**트레이드오프**: 사람별 접근 통제는 없다(필요하면 ldap/gss + 사람별 role). TLS를 켜지 않으면 데이터는 평문이다(`PGSSLMODE`).

### ADR-011: 배포는 단일 슬롯 deploy.sh (Pexorche 형태)
**결정**: `tools/deploy.sh <ROOT> <TAG>` 가 `refs/tags/` 로만 detach 체크아웃하고, `uv sync --locked --no-dev --no-editable` 로 `<ROOT>/venv` 를 만들고, venv 인터프리터에 콘솔 스크립트를 넘기는 런처를 `<ROOT>/bin` 에 둔다. `genviewer.env` 는 없을 때만 예시에서 심고(640) 절대 덮지 않으며 `a+rX` 대상에서 뺀다. 마지막에 런처를 실제로 실행해 본다. 롤백은 옛 태그로 다시 돌린다.
**이유**: 여러 도구를 한 사람이 관리하므로 Pexorche와 같은 방식이 낫다(버전별 디렉터리 + `current` 링크 방식은 쓰다가 되돌렸다). Pexorche는 `uv pip install` 이지만 여기는 PySide6→glibc→3.13 사슬 때문에 `uv.lock` 을 그대로 재현하는 `uv sync` 를 쓴다. `--no-editable` 이라야 `src` 를 고쳐도 아무의 앱도 바뀌지 않는다.
**트레이드오프**: 교체가 제자리라 설치 중에 띄우면 반쯤 바뀐 트리를 볼 수 있다. uv 관리 CPython이 배포자 홈에 있으면 남이 실행하지 못한다(`DEPLOY_PYTHON`).

### ADR-012: CLI 는 typer, rich 없이, 편집은 창에서만
**결정**: `genviewer` 하나에 서브커맨드(`status`, `processes`, `load`, `export`, 숨김 `log`). 서브커맨드가 없으면 창을 띄운다. `typer.Typer(rich_markup_mode=None, pretty_exceptions_enable=False)`, 콘솔 스크립트는 `main()` 을 가리키고 `main()` 이 인코딩을 손본 뒤 예외를 한 줄 문장으로 바꾼다. 종료 코드 0/1/2/130. 관리 도구(`init_db`)는 argparse.
**이유**: Pexorche의 CLI 형태다. 한국어 Windows 콘솔(cp949)은 rich가 그리는 상자 문자를 못 찍는다. device 편집은 낙관적 잠금·충돌 해결이 창에 얽혀 있어 명령줄로 흉내 내면 거짓말이 된다.
**트레이드오프**: `typer` 가 rich를 끌어온다(`typer-slim` 은 이제 껍데기). CLI만 써도 pandas가 import된다.

### ADR-013: 비밀번호는 포매터에서 한 번에 가린다
**결정**: 파일 로그(`~/.genviewer/genviewer.log`, 1MB × 3)의 포매터가 메시지와 트레이스백을 다 만든 뒤 `password=…`, `PGPASSWORD=…`, URL 안의 비밀번호를 `***` 로 바꾼다(`utils/logs.scrub`). 화면에 보이는 오류는 `user_message()` 를 거친다. 리눅스에서 기본 디렉터리(`~/.genviewer`)만 0700으로 좁히고, `GENDB_LOG` 로 고른 곳은 권한을 건드리지 않는다. chmod 실패는 파일 로그를 끄지 않는다.
**이유**: psycopg 접속 실패 예외에는 conninfo가 통째로 들어 있다. 호출자가 기억해서 가리는 방식은 언젠가 빠뜨린다. 배포본은 런처로 떠서 터미널이 없으므로 에러를 파일로 남겨야 한다.
**트레이드오프**: 로그 패널로 직접 보내는 문자열은 포매터를 지나지 않으므로 호출자가 `scrub()` 해야 한다.

### ADR-014: init_db 는 RHEL 7 서버의 Python 3.9 에서 소스로 돈다
**결정**: `scripts/init_db.py` 와 그것이 닿는 모듈은 Python 3.9 문법만 쓰고 psycopg 하나에만 의존한다. 서버에서는 패키지를 설치하지 않고 `PYTHONPATH=src python3.9 -m genviewer.scripts.init_db` 로 돌린다.
**이유**: 슈퍼유저는 비밀번호가 없어서(ADR-010) 원격으로는 소유자 role에 `--createdb` 와 비밀번호를 줘야 한다. 서버에서 peer로 돌리는 쪽이 단순하다. 서버에는 Python 3.13이 없다.
**트레이드오프**: 3.9에서 pip는 psycopg 3.2.x를 깔고, 코드는 3.2 이상을 필요로 한다. 이 호환을 지키는 자동 테스트가 아직 없다(리뷰로 지킨다).

### ADR-015: 하네스로 유지보수, 버그만 고친다
**결정**: 2026-10 부터 `pexqa` 와 같은 하네스(`scripts/execute.py`, `phases/`, `.claude/commands/{harness,review}.md`, Stop 훅 = `ruff check src tests && pytest -q -x`)로 유지보수한다. 기능 추가·리팩터는 하지 않고 에러·버그만 고친다. 버그 주장은 실패하는 테스트로 먼저 재현하고, 재현되지 않으면 고치지 않는다. 사용자에게 보이는 동작이 바뀌는 수정은 사용자가 승인한 것만 한다. 구조 개선은 `docs/notes/architecture-proposal.md` 에 제안으로만 둔다.
**이유**: 이미 여러 명이 쓰는 도구라 동작이 바뀌는 비용이 크다. 분석 에이전트가 낸 버그 후보 중에는 실제로 닿지 않는 경로가 있을 수 있다.
**트레이드오프**: 근본 원인(저장 흐름이 컨트롤러 셋에 흩어진 것 등)은 증상 단위로만 고쳐진다. GUI 테스트 기반(pytest-qt, fake repo, controller fixture)은 phase `2-gui-test-infra` 에서 깔았다. 가짜의 의미는 contract test가 실제 PostgreSQL과 맞춰 둔다.
