# 알려진 문제 (기록만, 지금은 고치지 않음)

- 2026-10-17 코드 분석에서 나왔다. **이 문서는 하네스 프롬프트에 주입되지 않는다.**
- 고치기로 한 것은 `phases/0-service-fixes` ~ `phases/4-gui-robustness` 에 있고, 여기에는 없다.
- 아래 항목은 ① 위험이 낮거나, ② 고치면 사용자가 보는 동작이나 내보내는 값이 바뀌거나, ③ 기능 추가에 가까워서 기록만 한다. 고치려면 사용자 승인을 받고 phase를 만든다. 그때도 실패하는 테스트로 먼저 재현한다.
- 행 번호는 2026-10-17 기준이다.

## 데이터·DB

| # | 문제 | 위치 | 왜 기록만 하나 |
|---|---|---|---|
| K1 | `--dsn`·`GENDB_PG_DSN` 을 주면 설정 파일을 읽지 않는다. 그런데 `status`·`--check-config` 는 `inspect_config()` 가 먼저 파일을 읽는다. 그래서 같은 `--dsn` 으로 `status` 는 붙고(`PGPASSWORD=(설정됨)`) `processes`·`load`·`export`·`log`·GUI는 비밀번호가 없다 | `service/config.py:59-61`, `cli.py` status | 파일을 항상 읽게 바꾸면 `--dsn` 으로 다른 서버에 붙을 때 팀 비밀번호가 거기로 간다. 설계 판단이 필요하다. README에 현재 동작을 적었다 |
| K2 | 풀이 `options`·`connect_timeout`·`application_name` 을 명시하므로 `PGOPTIONS`·`PGCONNECT_TIMEOUT`·`PGAPPNAME` 과 DSN 안의 `options=` 가 먹지 않는다 | `service/pool.py:27-41` | 의도된 타임아웃(ADR-008)과 얽혀 있다. README에 `GENDB_PG_*` 를 쓰라고 적었다 |
| K3 | 접속 실패의 실제 원인(비밀번호 틀림 28P01, DB 없음 3D000, 접속 수 초과 53300)이 풀의 `PoolTimeout`("couldn't get a connection after 5.00 sec")에 가려진다. `_BY_SQLSTATE` 의 그 항목들은 풀을 거쳐서는 나오지 않는다. 원인은 풀 로거 경고로만 파일 로그에 남는다 | `service/pool.py`, `service/errors.py:57-64` | phase 0 step 0은 "접속할 수 없다" 문구가 나오게만 고친다. 원인까지 보여주려면 직접 접속을 한 번 더 시도하는 등 새 동작이 필요하다 |
| K4 | `import_sqlite --on-conflict merge` 가 device를 갱신하면서 `version`·`updated_at`·`updated_by` 를 올리지 않고 `change_log` 도 쓰지 않는다. 열려 있는 GUI는 변경을 못 보고, 그 GUI의 저장이 가져온 데이터를 덮는다 | `scripts/import_sqlite.py:170-174, 194-208` | 초기 이관 도구다. "아무도 편집하지 않을 때 돌린다" 로 운영한다 |
| K5 | CLI `load` 가 import 트랜잭션 내내 process 행을 잠근다(`ON CONFLICT DO UPDATE`, `statement_timeout` 0). 그동안 GUI에서 그 process를 고르면 `get_or_create_id` 가 5초 기다리다 55P03으로 실패한다 | `repo/io.py:59-63`, `repo/process.py:113-118` | 큰 파일 불러오기는 사람이 적을 때 한다 |
| K6 | `log --since`·`--purge-before`·History 시간 필터가 naive 로컬 시각을 timestamptz와 비교한다. 서버 세션 TimeZone이 클라이언트와 다르면 어긋난다(UTC 서버 대 KST면 9시간) | `cli.py:305-322`, `repo/audit.py:357-362`, `controllers/history_tab.py:212-216` | 서버 TimeZone이 KST면 문제가 없다. 서버 설정부터 확인한다(`SHOW timezone`) |
| K7 | 기존 탭에 컬럼을 추가해도 마이그레이션이 없다. 저장·import가 42703으로 실패하고 친절한 문구도 없다. `status` 는 테이블 존재만 본다 | `service/schema.py:212-222`, `diagnostics.py:161-169` | 기능 추가다(제안 P7) |
| K8 | `init_db --owner` 를 `--owner` 없이 처음 만든 옛 DB에 다시 돌리면 "must be owner of table" 로 DDL 트랜잭션 전체가 롤백된다 | `scripts/init_db.py:90-100` | 2026-09-15 이전 DB에만 해당한다. 그런 DB는 `ALTER TABLE … OWNER TO` 로 한 번 정리한다 |
| K9 | 한 문장의 파라미터가 65,535개를 넘으면 실패한다(audit 약 7,281건, device 약 10,922개 재정렬) | `repo/audit.py:75-96`, `repo/device.py:320-349` | 지금 규모(process당 수백)에서는 닿지 않는다 |
| K10 | `log --follow` 가 행을 건너뛸 수 있다. IDENTITY id는 커밋이 아니라 삽입 때 정해진다 | `cli.py` log --follow | 보기 전용이다 |
| K11 | `import_sqlite` 가 `?`·`#`·`%` 가 든 sqlite 경로를 열지 못한다(read-only URI를 원시 경로로 만든다) | `scripts/import_sqlite.py:34` | 경로를 바꿔서 돌리면 된다 |

## 내보내기·연동

| # | 문제 | 위치 | 왜 기록만 하나 |
|---|---|---|---|
| K12 | xlsx 내보내기에서 `=` 로 시작하는 값이 수식으로 저장된다(openpyxl) | `utils/exporter.py:35-37` | 고치면 내보내는 값이 바뀐다 |
| K13 | SKILL 문자열을 이스케이프하지 않는다. process 이름이나 파라미터 값에 `"`·`\` 가 있으면 Virtuoso 명령이 깨지거나, 의도한 것 이상의 SKILL이 실행될 수 있다 | `service/virtuoso_protocol.py:13-14`, `utils/lisp.py:6-9` | 값은 팀 내부 사람이 넣고, Cadence 라이브러리 이름에는 따옴표가 없다. 고치면 보내는 문자열이 바뀐다 |
| K14 | Virtuoso 수신 쪽이 연결이 끊긴 것("DISCONNECTED"/"ERROR: …")을 접속 상태에 반영하지 않는다. UI는 계속 Connected라고 한다. UTF-8이 아닌 응답이 오면 수신이 멈춘다 | `net/workers.py:76-101` | phase 4 step 6은 크래시만 막는다. 상태 표시는 동작 변경이다 |
| K15 | Load Libs 요청이 빈 프레임이다(stub) | `service/virtuoso_protocol.py:17-18` | 기능이 아직 없다 |
| K16 | Virtuoso 목록 필터가 부분 문자열(`name in r["name"]`)이라 더 많이 걸릴 수 있다. 내보내기 형식은 메뉴가 정하는데 대화상자는 두 확장자를 다 허용해서, `.csv` 이름에 xlsx가 써질 수 있다 | `controllers/device_table.py:289, 425-436` | 의도인지 불확실하다 |

## GUI (phase에 넣지 않은 것)

| # | 문제 | 위치 | 왜 기록만 하나 |
|---|---|---|---|
| K17 | 같은 device를 다시 클릭하면(모델 reset 뒤 stale QModelIndex) 탭이 다시 로드되어 저장 안 한 탭 편집이 사라질 수 있다 | `controllers/device_table.py:49-50, 222-241`, `controllers/device_tab.py:429-433` | phase 3 step 6이 재현만 하고 고치지 않는다(선택 추적 구조 문제, 제안 P3·QPersistentModelIndex) |
| K18 | 필터가 켜진 상태에서 여러 행을 끌어 옮기면 숨은 행까지 옮겨진다 | `views/device_table.py:217-262` | 정렬 수정(phase 4 step 3)과 같은 원인이지만 별도 재현이 필요하다 |
| K19 | Load Virtuoso 뒤 저장하면 보이는 부분집합에만 `order = 0..k-1` 을 다시 매겨 순서가 겹친다 | `controllers/device_table.py:281-291, 341-342` | 의도한 동작인지 불확실하다. 확인이 필요하다 |
| K20 | "deleted" 충돌에서 덮어쓰기를 고르면 탭 저장은 같은 `StaleWriteError` 를 다시 내고, device 저장은 사라진 device의 편집을 조용히 버린다 | `service/repo/parameter.py:79-80`, `controllers/parameter_tab.py:87` | 덮어쓸 대상이 없는 경우다. 문구 정리가 필요하다 |
| K21 | 저장 안 한 새 행에서 Run Selected를 누르면 `KeyError 'id'` 가 "Send Failed: 'id'" 로 보인다 | `controllers/device_tab.py:278-287` | 무해하다 |
| K22 | 접속 실패 시 연 풀을 닫지 않는다. 남은 `Task` 객체, 매번 새로 만드는 selection model·delegate, 재접속 때 지워지지 않는 탭 섹션이 쌓인다 | `controllers/device_tab.py:130-136`, `utils/background.py:83`, `controllers/tab_section.py:194-232`, `views/parameter_tab.py:23-25` | 누수 규모가 작다. 접속 실패 풀은 phase 4 step 4에서 같이 볼 수 있다 |
| K23 | 필터가 바뀌어도 History 다시 읽기가 진행 중이면 그 변경을 버린다. 폴링 결과가 폴링한 process에 묶여 있지 않아, 그 사이에 process를 바꾸면 엉뚱한 배너가 뜰 수 있다 | `controllers/history_tab.py:122`, `controllers/device_tab.py:189-209` | 낮은 확률, 보기 전용 |
| K24 | 연결을 끊는 동안 상대가 프레임 중간에서 멈추면 GUI가 굳을 수 있다(`recv` 타임아웃 없음, `wait()` 타임아웃 없음) | `net/workers.py:90-92`, `net/controller.py:111-128` | 제안 P6 |
| K25 | `question()` 은 None을 돌려주지 않으므로 `_switch_device_by_index` 의 `choice is None` 분기는 닿지 않는 코드다 | `controllers/device_tab.py:441`, `utils/dialogs.py:21-25` | 동작에 영향 없음 |

## 운영 스크립트

| # | 문제 | 위치 | 왜 기록만 하나 |
|---|---|---|---|
| K26 | `PGHBA_CIDR` 만 주고 `PGAUTH_HOST` 를 안 주면 기본값 `trust` 로 그 대역 전체가 무인증이 된다 | `tools/initdb.sh:24, 68` | README 서버 절이 `PGAUTH_HOST=scram-sha-256` 을 함께 쓴다. 거부하게 바꾸면 기본값이 바뀐다 |
| K27 | 다시 돌릴 때 `listen_addresses`·`port`·pg_hba 줄은 "없을 때만 추가" 라 값을 바꿔도 반영되지 않는다. 주석 처리된 같은 줄도 "있음" 으로 본다(`grep -qF`) | `tools/initdb.sh:50, 57, 69` | 처음 한 번 쓰는 도구다 |
| K28 | `chmod -R a+rX "$root/src"` 가 `.git/config` 도 연다. clone URL에 토큰을 넣었다면 모두가 읽는다 | `tools/deploy.sh:192` | URL에 토큰을 넣지 않는다(README) |
| K29 | `DEPLOY_COMMANDS` 로 없는 명령을 주면 python이 exit 2를 내고, 마지막 확인(126/127만 봄)을 통과한다 | `tools/deploy.sh:250-252` | 자동으로 읽은 명령은 항상 있다 |
| K30 | 윈도우 `SKIP_START=1` 은 첫 실행에서 createdb가 실패한다(서버가 아직 안 떴다) | `tools/initdb.sh:75-102` | README에 "서버를 띄운 뒤 다시 돌린다" 로 적었다 |
