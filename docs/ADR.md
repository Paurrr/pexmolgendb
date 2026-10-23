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
**트레이드오프**: 새 탭 추가는 `init_db` 재실행으로 된다. 고정 테이블(`process`, `change_log`)에 더한 컬럼은 `schema.FIXED_ADDED_COLUMNS` 한 곳에 두고 `init_db` 와 `status` 가 같이 본다(ADR-018). 기존 탭에 컬럼을 추가하면 `init_db` 재실행이 빠진 컬럼을 `''` 로 더한다(2026-10-17 승인, 카탈로그를 보고 빠졌을 때만 `ALTER`). 안 돌렸으면 `genviewer status` 가 빠진 컬럼을 보이고 1로 끝난다. **컬럼 이름 변경·삭제·순서 변경은 여전히 마이그레이션이 없다.** JSON 키 구조를 바꾸면 모든 경로가 함께 바뀐다.

### ADR-004: 낙관적 잠금, 자동으로 다시 읽지 않음
**결정**: `device.version` 을 쓰기마다 올린다. 저장은 process별 advisory lock + `FOR UPDATE` 후 화면이 들고 있던 version과 비교해 다르면 `StaleWriteError` 를 내고, 사용자에게 다시 읽기/덮어쓰기/취소를 묻는다. 화면에 없는 device는 지우지 않는다(명시적으로 지운 id만). 남이 바꾼 것은 10초 폴링(etag)으로 배너만 띄운다.
**이유**: 예전에는 저장이 화면 내용으로 DB를 통째로 덮어써서 남의 작업이 사라졌다(PostgreSQL 이전 작업의 Phase 5, 하네스 phase 아님). 편집 중인 내용이 말없이 사라지는 것이 막으려던 바로 그 동작이라 자동 reload는 하지 않는다.
**트레이드오프**: 충돌은 저장할 때에야 알게 된다. 덮어쓰기를 고르면 남의 수정을 의도적으로 지운다. 탭 저장은 통째 교체라 셀 단위 병합이 없다.
**phase 3 보강**: 저장 함수가 결과(bool)를 돌려주고, 취소된 저장 뒤에는 "Saved" 를 띄우지 않으며 다른 process·device로 옮기지 않는다. 옮기던 중 멈추면 process 콤보만 시그널 없이 되돌리고 device 표 선택은 되돌리지 않는다(선택을 코드로 바꾸면 전환 처리가 다시 들어온다). 탭은 내 device 저장이 올린 version을 +1일 때만 따라간다. 덮어쓰기(+2 이상) 뒤의 탭 저장은 남의 변경이 끼어 있으므로 다시 충돌로 묻는다(그 문구의 마지막 수정자는 나다).
**phase 4 보강**: 되돌릴 process가 그 사이 지워졌으면(콤보 목록에 없으면) 되돌리지 않고 넘어간다. 콤보와 device 표가 다른 process를 가리키지 않게 하려는 것이고, 그 편집은 저장할 곳이 없다(2026-10-17 승인). 창 닫기와 Virtuoso device 목록 응답(device 표를 다시 읽는다)도 저장 안 한 편집이 있으면 기존 질문 문구로 묻는다. 창 닫기는 Yes면 저장에 성공했을 때만 닫는다(2026-10-17 승인). 정렬은 기준점을 바꾸지 않는 저장 안 한 변경이다(지운 device·편집 표시·undo가 남는다).
**phase 10 보강**: 내가 지운 행을 뺀 나머지 충돌이 전부 "삭제"면 덮어쓰기를 내놓지 않는다(다시 읽기/취소만). 덮어쓸 행이 없어서, 고르면 device 편집이 조용히 사라지거나 탭 저장이 같은 충돌을 다시 냈다(K20). 남이 먼저 지운 행을 나도 지웠으면 덮어쓰기가 해가 없어서 판단에서 뺀다. 수정과 삭제가 섞인 충돌은 그대로 세 갈래다(K48). 재접속은 device 표나 탭에, CSV 불러오기는 device 표에 저장 안 한 편집이 있으면 먼저 기존 Refresh 질문을 한다(K36). 탭에 저장 안 한 편집이 있으면 device 표 붙여넣기를 거부한다(K37). Remove Process를 확인하면 그 process의 편집은 묻지 않고 버린다. 저장할 곳이 없고, 물으면 반드시 삭제 충돌이 났다(K42). Virtuoso 목록으로 걸러 본 채 저장하면 보이는 행에 그 행들이 refresh 때 갖던 순서값을 화면 순서대로 나눠 준다. 숨은 행과 순서값이 겹치지 않고, 편집 없는 저장은 아무것도 쓰지 않는다(K19). 모두 2026-10-17 승인. 버그 수정은 둘이다. 모델 reset 뒤 같은 행을 다시 눌러도 저장 안 한 탭 편집을 서버 내용으로 덮지 않는다(K17). 붙여넣은 device의 탭 쓰기는 방금 저장한 version으로 낙관적 잠금을 확인한다(K38).
**phase 11 보강**: Virtuoso 로 보낼 대상에 저장하지 않은 device가 하나라도 있으면 아무것도 보내지 않고 `Unsaved Devices` 로 경고한다. 새 행은 id가 없어 탭 내용을 읽을 수 없고, 저장된 것만 골라 보내지도 않는다(K21). 필터가 사이 행을 숨긴 선택은 끌어 놓기를 받지 않는다. 모델의 연속 구간을 옮겨서 숨은 행까지 함께 옮겨졌다(K18). device 표 내보내기 형식은 고른 파일의 확장자(.csv/.xlsx)로 정하고, 둘 다 아니면 메뉴에서 고른 형식이다. CLI는 `.xlsx` 가 아니면 모두 CSV라서, 확장자가 없거나 다른 경우만 둘이 다르다(K16). 모두 2026-10-17 승인.
**phase 12 보강**: device 저장의 "Save Complete" 는 모달이라 그 사이에도 폴링이 돈다. 그래서 다시 읽기(기준점 다시 잡기) 뒤에 낸다. 앞에 내면 내 저장을 남의 변경으로 보고 배너가 떴다(K43). 그 결과 저장 뒤 다시 읽기가 실패하면 "Load Failed" 가 "Save Complete" 보다 먼저 뜬다. 폴링 결과·실패는 그 폴링을 시작한 process·DB(repo identity)가 그대로일 때만 쓴다. process 전환·재접속·닫기 뒤에 도착한 것은 버리고, 그 때문에 다시 읽지는 않는다(K23).

### ADR-005: change_log 는 앱이 같은 트랜잭션에서 쓴다
**결정**: 누가 언제 무엇을 바꿨는지 `change_log` 테이블에 앱이 저장과 같은 트랜잭션으로 쓴다(`repo/audit.write(cur, …)`). 값이 실제로 바뀐 행만 남긴다. 외래키를 걸지 않고, 지워진 것은 자식 행까지 `detail`(JSONB)에 통째로 남긴다. 트리거를 쓰지 않는다. 자동 삭제 없음(`--purge-before`). `genviewer log` 는 `--help` 에 숨긴다(접근 통제가 아니라 요청에 따른 숨김).
**이유**: 전원이 같은 role이라 트리거의 `current_user` 로는 사람을 구분할 수 없다. 탭 저장은 통째 교체라 행 트리거면 셀 하나 고친 저장이 로그 십수 줄이 된다. FK를 걸면 cascade가 이력까지 지운다. 저장이 실패하면 이력도 없어야 한다.
**트레이드오프**: `psql` 로 직접 고친 것은 남지 않는다.
**phase 7 보강**: CSV 불러오기가 새로 만든 process는 GUI의 process 추가와 같은 줄을 불러오기 줄 앞에 남긴다(2026-10-17 승인, K32). 행마다 VALUES를 늘리는 문장(이력, device UPDATE)은 libpq 바인드 파라미터 상한(65,535) 때문에 `audit.BATCH_ROWS`(1,000행)씩 나눠 같은 커서·트랜잭션에서 보낸다. 시간 필터에 넘기는 naive 시각은 클라이언트 로컬 시각으로 보고 tz를 붙인다(서버 세션 TimeZone과 무관하게 맞게). 표시 시각은 아직 세션 TimeZone 기준이다(K46).

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
**phase 7 보강**: 이미 있는 process는 SELECT로만 찾고 행을 잠그지 않는다(`process.find_or_create`, 없을 때만 `INSERT … ON CONFLICT DO NOTHING`). 예전의 `ON CONFLICT DO UPDATE` 는 CSV 불러오기가 커밋할 때까지 그 행을 잡아 GUI가 같은 process를 고르거나 저장하면 55P03으로 실패했다(K5). 풀이 커넥션을 못 주면 한 번 직접 붙어 실제 원인(원문 첫 줄, 비밀번호 가림)을 `DbUnavailableError` 에 싣는다. 그래서 그 실패는 최대 `connect_timeout` 만큼 늦게 뜬다(2026-10-17 승인, K3).
**phase 11 보강**: 창의 접속 확인(시작·재접속)과 Connect 창의 연결 테스트도 `ping()` 의 bool 대신 `connection()` 의 예외를 받아 그 원인을 `user_message` 로 보인다. 원인은 로그 패널의 `Database connect failed: …` 줄과 연결 테스트 칸에만 나오고 "Connect Failed" 상자 문구는 그대로다(2026-10-17 승인, K3). 접속에 실패한 새 Database는 그 자리에서 닫는다. 닫지 않으면 실패마다 풀 워커가 남아 죽은 서버에 계속 붙고, 종료할 때 그 워커를 기다리느라 멈췄다(K22). 닫기는 워커 스레드에서 약 1초 걸린다.

### ADR-009: DB 호출은 워커 스레드, 그동안 입력을 막는다
**결정**: 접속·저장·CSV 불러오기는 `run_blocking`(QThread + 이벤트 루프 + `ExcludeUserInputEvents` + 대기 커서), 폴링·History는 `Task`(비동기)로 돈다.
**이유**: 서버가 죽었거나 남의 잠금 뒤에서 기다리는 동안 창이 굳지 않아야 한다. 저장 중에 화면을 바꾸면 방금 보낸 것과 다른 내용이 저장된 것처럼 보이므로 입력은 받지 않는다.
**트레이드오프**: 아직 GUI 스레드에서 동기로 도는 호출이 남아 있다(ARCHITECTURE 스레딩 절). 입력은 버려지는 것이 아니라 끝난 뒤 처리된다.
**phase 4 보강**: 시작할 때의 접속도 창이 다 이어진 뒤(`QTimer.singleShot(0)`) 돈다. 그래야 시작 접속 실패와 첫 조회 실패가 로그 패널·알림에 보인다(2026-10-17 승인). 다시 접속할 때는 새 DB를 먼저 열고, 실패하면 지금 DB를 계속 쓴다. 옛 DB는 도는 폴링이 끝난 뒤에 닫는다. 작업 중(`is_busy()`)에는 창 닫기를 무시한다(저장 안에서 저장이 다시 돌지 않게).
**phase 12 보강**: 비동기 `Task`(폴링·History)는 시그널을 낸 작업이 지금 작업일 때만 결과를 쓰고, 끝난 그 작업만 지운다. 기다린 뒤 큐에 남은 옛 `finished` 가 돌고 있는 새 작업을 지우면 프로세스가 죽었다. History는 도는 중에 필터나 DB가 바뀌면 보류했다가 끝난 뒤 한 번 더 읽고, 그사이 도착한 옛 결과·실패는 버린다(K23, K41). 동시에 둘을 돌리지는 않는다. 자동 갱신 틱은 도는 중이면 보류하지 않고 건너뛴다. 보류로 만들면 10초보다 오래 걸리는 서버에서 결과가 매번 버려진다. `run_blocking` 은 끝난(`wait()` 가 참인) 자기 `Task` 를 지운다. 탭 섹션의 selection model·콤보 delegate와 다시 만든 탭 페이지도 지운다(K22).

### ADR-010: role 두 개, peer + scram
**결정**: `molgen_owner`(스키마 소유, DDL, `init_db` 만)와 `molgen_app`(테이블 DML만, 모두의 `genviewer.env`). `init_db --owner` 가 DDL 앞에서 `SET ROLE` 해 주인을 정하고 `ALTER DEFAULT PRIVILEGES` 를 건다. 클러스터는 `local=peer`, `host=scram-sha-256`, 원격은 `PGHBA_CIDR`/`PGHBA_DB`/`PGHBA_USER` 로 좁힌다. 전용 스키마 대신 `public`.
**이유**: 전원이 소유자로 붙으면 아무나 `DROP TABLE` 을 할 수 있다. 슈퍼유저 비밀번호를 만들지 않으려면 local을 peer로 둔다(`trust` 는 "인증 없음"). PG 15부터 `public` 은 DB 소유자만 쓸 수 있어 `ALTER DATABASE … OWNER` 가 필요하다.
**트레이드오프**: 사람별 접근 통제는 없다(필요하면 ldap/gss + 사람별 role). TLS를 켜지 않으면 데이터는 평문이다(`PGSSLMODE`).
**phase 9 보강**: `tools/initdb.sh` 는 `PGHBA_CIDR` 를 주면서 `PGAUTH_HOST` 를 비워 두면 무엇도 하기 전에 거부한다. 기본값 `trust` 가 그 원격 대역 전체를 인증 없이 열기 때문이다(2026-10-17 승인, K26). `PGAUTH_HOST=trust` 로 명시한 것은 받고, CIDR 없는 개발 기본값(루프백 trust)은 그대로다. 원격 hba 줄은 주석이 아닌 같은 줄이 있을 때만 건너뛴다(K27).

### ADR-011: 배포는 단일 슬롯 deploy.sh (Pexorche 형태)
**결정**: `tools/deploy.sh <ROOT> <TAG>` 가 `refs/tags/` 로만 detach 체크아웃하고, `uv sync --locked --no-dev --no-editable` 로 `<ROOT>/venv` 를 만들고, venv 인터프리터에 콘솔 스크립트를 넘기는 런처를 `<ROOT>/bin` 에 둔다. `genviewer.env` 는 없을 때만 예시에서 심고(640) 절대 덮지 않으며 `a+rX` 대상에서 뺀다. 마지막에 런처를 실제로 실행해 본다. 롤백은 옛 태그로 다시 돌린다.
**이유**: 여러 도구를 한 사람이 관리하므로 Pexorche와 같은 방식이 낫다(버전별 디렉터리 + `current` 링크 방식은 쓰다가 되돌렸다). Pexorche는 `uv pip install` 이지만 여기는 PySide6→glibc→3.13 사슬 때문에 `uv.lock` 을 그대로 재현하는 `uv sync` 를 쓴다. `--no-editable` 이라야 `src` 를 고쳐도 아무의 앱도 바뀌지 않는다.
**트레이드오프**: 교체가 제자리라 설치 중에 띄우면 반쯤 바뀐 트리를 볼 수 있다. uv 관리 CPython이 배포자 홈에 있으면 남이 실행하지 못한다(`DEPLOY_PYTHON`).
**phase 9 보강**: 트리를 `a+rX` 로 연 뒤 `src/.git` 을 `go-rwx` 로 다시 닫는다. `.git/config` 의 clone URL(토큰을 넣었다면 그것도)을 남이 읽지 못하게 하고, 실행에는 `.git` 이 필요 없다(K28). 그래서 다음 배포도 처음 배포한 사람이 한다. `DEPLOY_COMMANDS` 의 이름이 `venv/bin` 에 없으면 지난 런처를 지우기 전에 멈춘다(K29).

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
**트레이드오프**: 3.9에서 pip는 psycopg 3.2.x를 깔고, 코드는 3.2 이상을 필요로 한다. `tests/test_py39_compat.py` 가 init_db 에서 닿는 모듈의 문법과 3.10+ 이름을 정적으로 검사한다. 실제 3.9 인터프리터로 import해 보지는 않고, psycopg 3.2 API 차이는 검사 밖이다.

### ADR-015: 하네스로 유지보수, 버그만 고친다
**결정**: 2026-10 부터 `pexqa` 와 같은 하네스(`scripts/execute.py`, `phases/`, `.claude/commands/{harness,review}.md`, Stop 훅 = `ruff check src tests && pytest -q -x`)로 유지보수한다. 기능 추가·리팩터는 하지 않고 에러·버그만 고친다. 버그 주장은 실패하는 테스트로 먼저 재현하고, 재현되지 않으면 고치지 않는다. 사용자에게 보이는 동작이 바뀌는 수정은 사용자가 승인한 것만 한다. 구조 개선은 `docs/notes/architecture-proposal.md` 에 제안으로만 둔다.
**이유**: 이미 여러 명이 쓰는 도구라 동작이 바뀌는 비용이 크다. 분석 에이전트가 낸 버그 후보 중에는 실제로 닿지 않는 경로가 있을 수 있다.
**트레이드오프**: 근본 원인(저장 흐름이 컨트롤러 셋에 흩어진 것 등)은 증상 단위로만 고쳐진다. GUI 테스트 기반(pytest-qt, fake repo, controller fixture)은 phase `2-gui-test-infra` 에서 깔았다. 가짜의 의미는 contract test가 실제 PostgreSQL과 맞춰 둔다.

### ADR-016: Virtuoso 소켓은 GUI 스레드의 QTcpSocket 하나
**결정**: `net/` 의 `ConnectionController` 는 GUI 스레드의 `QTcpSocket` 하나로 시그널만 받아 돈다. 워커 스레드와 `waitFor*` 는 없다. 프레임은 그대로 4바이트 big-endian 길이 다음에 UTF-8 본문이다. 0바이트 프레임은 메시지가 아니라서 버린다. 상대가 끊거나 주고받기가 실패하면 Socket 탭에 `ERROR: … failed - …` 를 보이고(상대가 닫으면 옛 문구 `ERROR: recv failed - Server connection closed`) 상태를 Disconnected로 바꾼다(K14). 접속 중의 Connect는 무시하고, 접속 중의 끊기·창 닫기는 그 시도를 abort한다. 2026-10-17 승인(제안 P6, phase 13).
**이유**: QThread 워커 셋이 소켓 하나를 나눠 썼다. 끊김이 상태에 반영되지 않았고(K14), 프레임 중간에서 끊으면 창이 굳었고(K24), 접속 중 창 닫기와 빠른 두 번 Connect는 실행 중인 QThread를 지워 프로세스가 죽었다(K39·K40).
**트레이드오프**: 접속 실패 문구는 Qt 오류를 옛 매핑(`InvalidAddress`/`ConnectionRefused`/`ConnectionTimedOut`)에 맞춘 것이다. OS가 낸 접속 타임아웃은 Qt가 `NetworkError` 로 올려서 `Error: Connection timed out` 으로 보인다(2026-10-18 사용자 확인). Windows에서 잰 실패 시간은 옛 코드의 약 두 배다(거부 약 4초, 타임아웃 약 42초). 호스트 이름은 IPv4만이 아니라 풀린 주소를 차례로 시도한다(옛 코드는 `AF_INET`). 테스트는 127.0.0.1의 `LocalVirtuoso` 에 공개 API로 붙는다. 보내기 `write == -1` 과 RST 말고 다른 소켓 오류는 그렇게 만들 수 없어서 테스트가 없다.

### ADR-017: Description 은 CSV 로 오가고 Virtuoso 로는 가지 않는다
**결정**: device 의 description 을 CSV·xlsx 의 `InstCellName` 다음 `Description` 컬럼으로 내보내고, 불러오기는 그 컬럼이 있으면 읽는다(없으면 빈 값). tab_config 의 탭이 아니라 device 컬럼이라 스키마와 tab_config 는 그대로다. Virtuoso 보내기는 같은 `fetch_export_data` 를 쓰므로 고정 컬럼(`CellType`·`CdsLibName`·`InstCellName`)을 위치가 아니라 이름으로 고르고 Description 은 뺀다. CSV 를 쓸 때(`utils/exporter.write_csv`) Description 의 `,` 는 `;` 로, 줄바꿈은 공백으로 바꾼다. 2026-10-17·18 승인한 기능(K44, phase 18). molgen 은 `pexGenDB_GenDev_Get_Header_Type()` 에 `'Description "string"` 을 등록했다(molgen `c7da3a0`, 읽기만 하고 생성에는 쓰지 않는다).
**이유**: 화면에서 적은 설명이 내보낸 CSV 에 없어서 다시 불러오면 사라졌다. molgen CSV 로더는 따옴표를 모르고 `,` 로만 칸을 나눠서, 쉼표가 든 설명은 그 행의 뒤 컬럼을 밀고 줄바꿈은 행을 가른다. 다른 컬럼은 molgen 문법이라 쉼표가 없고 자유 문장은 Description 뿐이다.
**트레이드오프**: 쉼표·줄바꿈이 든 설명은 CSV 왕복에서 `;`·공백으로 돌아온다(DB·xlsx 는 원문). 불러오기는 바꿔 쓰지 않으므로 다른 곳에서 만든 CSV 의 쉼표는 그대로 저장된다. 등록 전의 molgen 은 이 컬럼에 경고를 내므로 운영에는 molgen 을 먼저 배포한다.

### ADR-018: process 는 (이름, 버전) 쌍이다
**결정**: process 행 하나가 (이름, 버전) 쌍이다(`process.release TEXT NOT NULL DEFAULT ''`, `UNIQUE (name, release)`). device·탭 테이블은 그대로 `process_id` 로 묶이므로 (process, 버전)마다 device 데이터가 따로 있다. 버전은 `S00-V1.0.0.0` 같은 자유 문자열이고 앞뒤 공백만 다듬는다. 옛 process 는 모두 빈 버전 `''` 이 되고, 빈 버전의 문구·출력에는 버전 흔적이 없고 버전이 없던 형태 그대로다(화면 `(none)`, CLI `-`. ADR-020 전에는 예전 문구와 바이트까지 같았고 화면은 `(없음)` 이었다). 이름은 코드·DB 에서 `release`, 화면 라벨 `Version`, CLI 옵션 `--version` 이다. CSV 형식은 그대로(버전 칸 없음, molgen 은 고치지 않음)이고 불러올 때 버전을 정한다. 새 버전은 기존 쌍에서 DB 안에서 복제한다(device 와 탭 행, `REPEATABLE READ` 한 시점, 원본을 잠그지 않음, 이력 한 줄). `change_log.process_release` 가 버전을 남긴다. 옮기기는 `init_db` 의 멱등 DDL 이다(카탈로그를 보고 빠졌을 때만 `ALTER`, 옛 `UNIQUE (name)` 은 이름이 아니라 컬럼으로 찾아 뗀다). GUI 내보내기의 제안 파일 이름은 molgen 이 찾는 `<proc>_<cid>-<ver 점 제거>.<fmt>` 다. 2026-10-21 승인한 기능(phase 19).
**이유**: 같은 process 의 공정 버전마다 device 데이터가 다르다. 코드에는 `device.version`(낙관적 잠금 카운터, ADR-004)과 그 뜻의 `version` 이 200곳 넘게 있어서 새 개념에 같은 이름을 쓰면 섞인다. 빈 버전을 `COMMON`·`ALL` 같은 이름으로 두지 않은 것은 버전 사이의 상속을 구현하지 않아서 그 이름이 거짓말이 되기 때문이다. `release` 를 NULL 허용으로 두지 않은 것은 PG 10~15 의 `UNIQUE` 가 NULL 끼리의 중복을 막지 않기 때문이다.
**트레이드오프**: **배포가 무중단이 아니다.** 옮긴 DB 에 옛 앱이 붙어 있으면, 새 이름을 만드는 옛 코드(`ON CONFLICT (name)`)는 맞는 제약이 없어 42P10 으로 죽고, 옛 Remove Process 는 그 이름의 모든 버전을 지우며, 옛 조회는 같은 이름의 쌍 중 아무것이나 고른다. 그래서 모두 앱을 닫고(`load` 도) `init_db` → `deploy.sh` 순서로 하고, 옛 창이 다 닫힌 뒤에 첫 버전을 만든다(README '배포'). 처음 옮길 때 `init_db` 가 `process`·`change_log` 에 ACCESS EXCLUSIVE 를 한 번 잡는다. 여러 process 가 든 CSV 를 버전으로 불러온 이력 줄은 `process_release` 가 `''` 이라 `log --version` 필터에서 빈 버전 쪽에 잡힌다(K52). History 필터와 `log --process` 는 이름으로 거르므로 모든 버전이 나온다.

### ADR-019: 어두운 테마는 pexqa 토큰
**결정**
- Graphite(어두움, 기본 테마)의 색은 형제 저장소 pexqa 의 `gui/theme.py`("Dim slate") 토큰과 같다.
  - window·panel `#22272e`, base `#1c2128`, text `#c9d1d9`, border `#444c56`, accent `#539bf5`, 선택 `#2c4a72`/`#f0f6fc`, good `#6bc46d`, bad `#f47067` …
- Mist(밝음)는 그대로다.
- 테마마다 달라야 하는 의미 색도 `palette.THEMES` 키로 두고, 모델은 `palette.current_colors()` 로 읽는다.
  - `dirty`: 저장 안 한 셀 배경
  - `unknown_name`: Virtuoso 에 없는 이름
  - `selection`/`selection_text`: 선택
- 그래서 `models/` 가 `utils.palette` 를 import 한다(`tests/test_boundaries.py` 허용 목록).
- 알려진 device 이름은 색을 정하지 않고 테마 글자색을 따른다. Mist 에서는 검정이 다른 칸과 같은 `#20262d` 가 된다.
- 2026-10-22 승인(phase 22).

**이유**
- 모델이 이름 글자를 `Qt.black` 으로, dirty 배경을 밝은 노랑으로 박아 두었다. 그래서 Graphite 에서 대비가 1.6, 1.1 이었다.
- 사용자가 pexqa 와 색을 맞추길 원했다.

**트레이드오프**
- QSS 구조는 그대로 두고 값만 바꿨다. 그래서 눌린 단추, 탭 모양 같은 위젯 모양은 pexqa 와 다를 수 있다.
- Mist 의 빨강 `#ff0000` 은 base 위 대비가 3.8 로 기준(4.5)보다 낮다. 바꾸지 말라는 요청대로 둔다.

### ADR-020: 사용자에게 보이는 문구는 영어
**결정**
- 사용자에게 보이는 문구는 영어다.
  - GUI: 대화상자 본문·질문, 라벨, 툴팁, 배너, 상태 표시줄, 로그 패널, History 화면
  - CLI: `--help`, 출력, 프롬프트
  - `tools/*.sh` 의 출력
- 한국어로 두는 것
  - 코드 주석과 docstring. typer 명령 docstring 은 `--help` 문구라서 영어다.
  - 문서
  - 로그 파일에만 가는 문구
  - 이력 요약 `change_log.summary`
  - `deploy.sh` 의 런처 marker
- 빈 버전 표시는 화면 `(none)`, CLI `-` 다.
- 문장 규칙과 용어표는 UI_GUIDE "문구" 에 있다.
- 2026-10-22 승인(phase 24). 회귀는 `tests/test_english_text.py` 가 막는다.
  - `src/genviewer` 의 문자열 상수·f-string 과 `tools/*.sh` 의 주석 밖 줄에 한글이 있으면 실패한다.
  - 빼는 것은 docstring(typer 명령 것은 본다), 로거 이름(`log`·`logger`·`root`·`logging`)으로 부르는 로그 호출, 이력 요약 함수 7개, 셸 주석, `marker=` 줄이다.
  - `init_db` 의 DDL 라벨 주석(`-- add release to process …`)도 `--dry-run` 에 보이므로 영어다. SQL 본문은 그대로다.
- 한국어 글자에 맞춰 둔 고정 너비는 영어 글자를 자른다. 변경 배너의 `Reload`/`Dismiss` 단추는 같은 값을 최소 너비로 바꿨다(phase 24 step 2).
- `utils/logs.py` 의 "로그 파일을 열지 못했다" 경고는 로그 호출이라 한국어로 두었다. 로그 파일이 없을 때라 실제로는 stderr 로만 나간다.

**이유**
- 사용자가 요청했다.
- 이력 요약은 DB 에 저장되는 데이터다. 바꾸면 옛 줄과 새 줄이 섞이고 History 와 `log --find` 검색이 갈린다.
- 런처 marker 는 다음 배포가 자기 런처를 찾는 식별자다. 바꾸면 옛 런처가 남는다.

**트레이드오프**
- History 와 `genviewer log` 는 영어 화면 안에 한국어 요약을 보인다.
- ADR-018 의 "빈 버전 출력은 예전과 바이트까지 같다" 가 "버전 흔적 없음" 으로 약해졌다.
- README 의 출력 예시를 영어로 다시 맞춰야 한다.
