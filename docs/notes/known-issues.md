# 알려진 문제 (기록만, 지금은 고치지 않음)

- 2026-10-17 코드 분석에서 나왔다. **이 문서는 하네스 프롬프트에 주입되지 않는다.**
- 고치기로 한 것은 `phases/0-service-fixes` ~ `phases/4-gui-robustness` 에 있고, 여기에는 없다.
- 아래 항목은 ① 위험이 낮거나, ② 고치면 사용자가 보는 동작이나 내보내는 값이 바뀌거나, ③ 기능 추가에 가까워서 기록만 한다. 고치려면 사용자 승인을 받고 phase를 만든다. 그때도 실패하는 테스트로 먼저 재현한다.
- 행 번호는 2026-10-17 기준이다.

## 2026-10-17 분류 (phase 6~13 에서 해소 예정)

phase 5 뒤에 다시 보니 아래 항목이 모두 코드에 남아 있었다. 사용자가 동작 변경을 항목별로 승인했다(2026-10-17). 고친 항목은 각 phase 마무리 때 이 문서에서 지운다.

| phase | 항목 | 구분 |
|---|---|---|
| 7-service-fixes | K31, K6, K5, K9, K13 | 버그 |
| 7-service-fixes | K1, K3(CLI·풀), K10, K32, K12 | 승인된 동작 변경 |
| 8-schema-migration | K7 (제안 P7) | 승인된 기능 |
| 9-ops-script-fixes | K27(주석 줄 오탐만), K28, K29 | 버그 |
| 9-ops-script-fixes | K26 | 승인된 동작 변경 |
| 10-gui-edit-safety | K17, K38 | 버그 |
| 10-gui-edit-safety | K20, K37, K36, K42, K19 | 승인된 동작 변경 |
| 11-gui-error-paths | K34, K35, K22(접속 실패 풀) | 버그 |
| 11-gui-error-paths | K3(GUI), K21, K16(내보내기 형식), K18 | 승인된 동작 변경 |
| 12-gui-async-cleanup | K23, K41, K22(Task·섹션·탭 페이지), history_tab 의 `{exc}`, K43 | 버그 |
| 13-virtuoso-socket | K14, K24, K39, K40 (제안 P6 로 해소) | 버그 + 승인된 구조 변경 |
| 18-csv-description | K44 | 승인된 기능 (molgen 쪽 Description 등록이 먼저) |

- 고치지 않기로 함(2026-10-17): K2, K8, K15, K27 의 나머지(다시 돌릴 때 값 반영), K30, K33, K16 의 Virtuoso 목록 필터(부분 문자열 일치가 의도). K25 는 제안 P3(phase 16) 에서 지운다.

## 데이터·DB

| # | 문제 | 위치 | 왜 기록만 하나 |
|---|---|---|---|
| K1 | `--check-config` 는 `--dsn`·`GENDB_PG_DSN` 이 있어도 설정 파일을 읽는다(status 는 2026-10-18 phase 7 에서 고침) | `cli.py` `_print_config`, `service/diagnostics.py` `inspect_config` | 승인 범위 밖 |
| K2 | 풀이 `options`·`connect_timeout`·`application_name` 을 명시하므로 `PGOPTIONS`·`PGCONNECT_TIMEOUT`·`PGAPPNAME` 과 DSN 안의 `options=` 가 먹지 않는다 | `service/pool.py:27-41` | **고치지 않기로 함(2026-10-17).** 의도된 타임아웃(ADR-008)과 얽혀 있다. README에 `GENDB_PG_*` 를 쓰라고 적었다 |
| K3 | 창의 시작·재접속 알림은 접속 실패의 실제 원인(비밀번호 틀림, DB 없음, 접속 수 초과)을 보여주지 않는다. `_open_database` 가 `ping()` 의 bool 만 보고 고정 문구("서버가 응답하지 않는다")를 낸다. CLI·status 는 2026-10-18 phase 7 에서 고침(풀이 커넥션을 못 주면 한 번 직접 접속해 그 오류의 첫 줄을 싣는다) | `controllers/device_tab.py` `_open_database` | GUI 시작·재접속 문구는 phase 11 step 1 |
| K8 | `init_db --owner` 를 `--owner` 없이 처음 만든 옛 DB에 다시 돌리면 "must be owner of table" 로 DDL 트랜잭션 전체가 롤백된다 | `scripts/init_db.py:90-100` | **고치지 않기로 함(2026-10-17).** 2026-09-15 이전 DB에만 해당한다. 그런 DB는 `ALTER TABLE … OWNER TO` 로 한 번 정리한다 |
| K33 | `upsert_device` 에 `id` 가 있는 dict를 주면 version 검사 없이 덮어쓰고 `process_id` 도 바꾼다 | `repo/device.py:97-` | **고치지 않기로 함(2026-10-17).** 지금 호출자(붙여넣기 `paste_rows`)는 `id` 없는 dict만 넘겨 닿지 않는다. phase 2 step 1이 가짜를 만들다 본 것이고 재현하지 않았다. 가짜도 지금 동작을 그대로 흉내 낸다 |
| K44 | CSV에 Description 컬럼이 없다(molgen 형식). 불러오기로 만든 device는 description이 비고, 내보내기도 Description을 쓰지 않아 내보낸 CSV를 다시 넣으면 description이 따라오지 않는다. 저장된 device의 description은 불러오기가 건드리지 않는다 | `repo/io.py:118-122` (device INSERT), `:217` (export 헤더), `controllers/device_table.py:461-470` (GUI 내보내기 device_info) | 2026-10-17 사용자 제보("CSV import 하면 description 이 날라간다")를 조사하다 확인했다. 저장하지 않은 편집이 사라지는 쪽은 K36이다. 사용자가 같은 날 왕복을 승인했다(phase 18). molgen `pexGenDB_GenDev_Get_Header_Type()` 에 `'Description "string"` 을 먼저 등록해야 한다. 안 그러면 셀마다 `Unknown header type` warn이 뜬다 |
| K46 | 표시 시각이 서버 세션 TimeZone 기준이다. 서버 세션이 UTC면 `log` 출력·History·`log --out` CSV 의 `at` 이 UTC로 찍힌다. 시간 필터(`--since`·`--purge-before`·History 기간)는 2026-10-18 phase 7 에서 클라이언트 시각으로 고쳤다(K6) | `repo/audit.py` `format_line`, `controllers/history_tab.py`, `cli.py` `_write_log_csv` | 표시가 바뀌는 동작 변경이다. 서버 TimeZone이 KST면 문제가 없다(`SHOW timezone`) |

## 내보내기·연동

| # | 문제 | 위치 | 왜 기록만 하나 |
|---|---|---|---|
| K14 | Virtuoso 수신 쪽이 연결이 끊긴 것("DISCONNECTED"/"ERROR: …")을 접속 상태에 반영하지 않는다. UI는 계속 Connected라고 한다. UTF-8이 아닌 응답이 오면 수신이 멈춘다 | `net/workers.py:85-110` | phase 4 step 6은 크래시만 막고, 보내기 실패를 받기 오류와 같은 길(Socket 탭 수신 칸)로 보이게 했다. 상태 표시는 동작 변경이다 |
| K15 | Load Libs 요청이 빈 프레임이다(stub) | `service/virtuoso_protocol.py:17-18` | **고치지 않기로 함(2026-10-17).** 기능이 아직 없다(Virtuoso 쪽 함수가 정해지지 않았다) |
| K16 | Virtuoso 목록 필터가 부분 문자열(`name in r["name"]`)이라 더 많이 걸릴 수 있다. 내보내기 형식은 메뉴가 정하는데 대화상자는 두 확장자를 다 허용해서, `.csv` 이름에 xlsx가 써질 수 있다 | `controllers/device_table.py:296, 473-484` | 필터: **고치지 않기로 함(2026-10-17).** 접미사가 붙은 이름까지 잡는 것이 의도다. 내보내기 형식: phase 11 에서 확장자로 고른다 |

## GUI (phase에 넣지 않은 것)

| # | 문제 | 위치 | 왜 기록만 하나 |
|---|---|---|---|
| K17 | 같은 device를 다시 클릭하면(모델 reset 뒤 stale QModelIndex) 탭이 다시 로드되어 저장 안 한 탭 편집이 사라질 수 있다 | `controllers/device_table.py:51-52, 229-248`, `controllers/device_tab.py:496-500` | 선택 추적 구조 문제다(제안 P3·QPersistentModelIndex). phase 3 step 6이 재현 테스트를 strict xfail로 남겼다(`tests/gui/test_tab_version_sync.py::test_clicking_the_same_row_after_a_device_save_keeps_the_tab_edits`). 고치면 XPASS로 실패하니 그때 xfail을 뗀다 |
| K18 | 필터가 켜진 상태에서 여러 행을 끌어 옮기면 숨은 행까지 옮겨진다 | `views/device_table.py:217-262` | phase 4 step 3이 정렬은 고쳤다(모델의 모든 행을 정렬). 끌어 옮기기는 같은 원인이지만 별도 재현이 필요하다 |
| K19 | Load Virtuoso 뒤 저장하면 보이는 부분집합에만 `order = 0..k-1` 을 다시 매겨 순서가 겹친다 | `controllers/device_table.py:288-298, 358-359` | 의도한 동작인지 불확실하다. 확인이 필요하다 |
| K20 | "deleted" 충돌에서 덮어쓰기를 고르면 탭 저장은 같은 `StaleWriteError` 를 다시 내고, device 저장은 사라진 device의 편집을 조용히 버린다 | `service/repo/parameter.py:79-80`, `controllers/parameter_tab.py:95` | 덮어쓸 대상이 없는 경우다. 문구 정리가 필요하다 |
| K21 | 저장 안 한 새 행에서 Run Selected를 누르면 `KeyError 'id'` 가 "Send Failed: 'id'" 로 보인다 | `controllers/device_tab.py:305-314` | 무해하다 |
| K22 | 접속 실패 시 연 풀을 닫지 않는다. 남은 `Task` 객체, 매번 새로 만드는 selection model·delegate, 재접속 때 지워지지 않는 탭 섹션이 쌓인다 | `controllers/device_tab.py:147-153`, `utils/background.py:83`, `controllers/tab_section.py:203-241`, `views/parameter_tab.py:23-25` | 누수 규모가 작다. phase 4 step 4는 재접속 순서(새 DB 먼저)만 고치고 실패한 풀은 그대로 뒀다 |
| K23 | 필터가 바뀌어도 History 다시 읽기가 진행 중이면 그 변경을 버린다. 폴링 결과가 폴링한 process에 묶여 있지 않아, 그 사이에 process를 바꾸면 엉뚱한 배너가 뜰 수 있다 | `controllers/history_tab.py:122`, `controllers/device_tab.py:210-230` | 낮은 확률, 보기 전용 |
| K24 | 연결을 끊는 동안 상대가 프레임 중간에서 멈추면 GUI가 굳을 수 있다(`recv` 타임아웃 없음, `wait()` 타임아웃 없음) | `net/workers.py:99-101`, `net/controller.py:130-147` | 제안 P6 |
| K25 | `question()` 은 None을 돌려주지 않으므로 `_switch_device_by_index` 의 `choice is None` 분기는 닿지 않는 코드다 | `controllers/device_tab.py:508`, `utils/dialogs.py:21-25` | 동작에 영향 없음 |
| K34 | process 조회 실패 알림 본문이 `user_message()` 가 아니라 `str(e)` 다. 55P03·57014 같은 SQLSTATE별 한국어 안내 대신 원문이 보이고, conninfo가 든 예외라면 그대로 나간다(CLAUDE.md 비밀번호 규칙) | `controllers/device_tab_toolbar.py:150-157` (`get_process_id`) | phase 2 step 2가 코드를 읽다 본 것이고 재현하지 않았다. phase 0 뒤로 접속 실패는 `DbUnavailableError`(conninfo 없음)로 온다. 고치면 알림 문구가 바뀐다 |
| K35 | 변경 감지 폴링이 3회 실패해 멈출 때 로그 패널에 `{exc}` 를 그대로 쓴다(`user_message`·`scrub` 를 거치지 않음) | `controllers/device_tab.py:233-238` (`_on_poll_failed`) | K34와 같다. 로그 패널 문구가 바뀐다 |
| K36 | 재접속(`apply_db`)과 CSV 불러오기 뒤의 `refresh_devices()` 가 저장하지 않은 device 표 편집을 묻지 않고 버린다. process 선택은 phase 3 step 4부터 유지된다 | `controllers/device_tab.py:280-286` (`apply_db`), `:369-370` (CSV 불러오기) | phase 3 step 4가 코드를 읽다 본 것이고 재현하지 않았다. 고치려면 새 확인 질문이 필요하다(동작 변경) |
| K37 | 저장하지 않은 탭 편집이 있을 때 device 표에 붙여넣으면 `paste_payload` 의 `set_device_to_section` 이 탭을 다시 읽어 그 편집이 사라진다. device 표 편집은 phase 3 step 7이 막았다(`Unsaved Changes`) | `controllers/parameter_tab.py:179-186` | phase 3 step 7이 코드를 읽다 본 것이고 재현하지 않았다. 승인 범위(G15b)가 device 표 dirty였다 |
| K38 | 붙여넣기의 탭 쓰기가 version 없이(`expected_version=None`) 나가 버전 확인을 건너뛴다. `on_paste_requested` 가 붙여넣은 device를 모델에서 찾지만 그 행은 `refresh_devices()` 전이라 아직 모델에 없다 | `controllers/device_tab.py:473-479`, `controllers/device_table.py:202-209`, `service/repo/parameter.py:82-84` | phase 3 step 7이 코드를 읽다 본 것이고 재현하지 않았다. 방금 내가 만든 device라 남이 끼어들 틈이 거의 없다 |
| K39 | 창을 닫을 때 Virtuoso 접속(`ConnectWorker`)이 진행 중이면 `ConnectionController.shutdown()` 이 기다리지 않는다. `run_gui` 가 돌아온 뒤 실행 중인 QThread가 지워져 종료가 크래시로 끝날 수 있다 | `net/controller.py:67-77` (`shutdown`) | phase 4 step 6이 코드를 읽다 본 것이고 재현하지 않았다. 기다리면 접속 타임아웃만큼 창이 굳는다(K24와 같은 종류, 제안 P6) |
| K40 | `ConnectWorker` 가 끝났지만 결과가 아직 GUI 큐에 있는 순간의 Connect는 "접속 중" 가드를 지나 새 시도를 시작한다. 두 결과가 다 성공이면 `_start_io_workers` 가 두 번 돌아 앞 IO 워커를 덮어쓸 수 있다 | `net/controller.py:37-52` (`connect`), `:85-99` | phase 4 step 6이 코드를 읽다 본 것이고 재현하지 않았다. Connect를 아주 빠르게 두 번 눌러야 닿는다 |
| K41 | 재접속할 때 History 화면에서 도는 다시 읽기(`Task`)를 기다리지 않는다. 옛 풀이 닫힌 뒤 그 작업이 실패할 수 있고, 그 작업이 남아 있는 동안 `set_db(새)` 의 다시 읽기가 `_task` 가드로 건너뛰어 다음 자동 갱신(10초)까지 새 DB로 읽지 않는다 | `controllers/history_tab.py:76` (`set_db`), `:121-122` (`reload`), `controllers/device_tab.py:155-` (`connect_db`) | phase 4 step 4가 코드를 읽다 본 것이고 재현하지 않았다. History는 `--history` 로 띄웠을 때만 있고 보기 전용이다(K23과 같은 가드) |
| K42 | 저장하지 않은 편집이 있는 process를 Remove Process로 지운 뒤 "Save Changes" 에 예로 답하면, 방금 지운 process의 device를 저장하려다 반드시 "deleted" 충돌이 난다 | `controllers/device_tab_toolbar.py:104-` (`remove_process`), `controllers/device_tab.py:434-` (`_save_before_process_change`) | `tests/gui/test_deleted_process_revert.py::test_cancelling_after_removing_the_process_moves_to_the_first_process` 가 이 흐름을 그대로 돈다(충돌 한 번, 취소하면 다음 process로 넘어간다). 충돌 대화상자에서 빠져나올 수 있고, 질문을 건너뛰게 하면 흐름이 바뀐다(동작 변경) |
| K43 | device를 저장하면 "Save Complete"(모달 `QMessageBox`)가 떠 있는 동안 10초 폴링이 돈다. 그러면 "이 process 가 <나> 님에 의해 변경되었습니다." 배너가 다음 폴링까지 뜬다. `save_all` 이 알림을 `refresh_devices()`(→ `remember_etag`) **전에** 내서, 저장 뒤 etag를 저장 전 기준점과 비교하기 때문이다. 추가·수정·삭제·덮어쓰기 저장이 모두 해당한다 | `controllers/device_table.py:383-384` (`save_all`) | 2026-10-17 사용자 제보("device 추가 후 save 하면 '어떤 사용자가 …' 문구가 뜬다")로 찾았고 일회성 스크립트로 재현했다. phase 12 step 7에서 고친다 |
| K45 | 내 쓰기가 시작되기 직전에 출발한 폴링의 결과가 `remember_etag` 뒤에 도착하면, 저장 전 etag와 새 기준점이 달라 거짓 배너가 뜰 수 있다 | `controllers/device_tab.py:196-230` (`_poll_remote_changes`, `_on_poll_result`), `controllers/device_table.py:306-` (`remember_etag`) | K43을 조사하다 코드를 읽고 본 것이고 재현하지 않았다. 폴링 쿼리가 저장 전체보다 오래 걸려야 닿아서 확률이 매우 낮다. 고치려면 결과를 시작할 때의 기준점에 묶는다(phase 12 step 3과 같은 방식) |

## 운영 스크립트

| # | 문제 | 위치 | 왜 기록만 하나 |
|---|---|---|---|
| K26 | `PGHBA_CIDR` 만 주고 `PGAUTH_HOST` 를 안 주면 기본값 `trust` 로 그 대역 전체가 무인증이 된다 | `tools/initdb.sh:24, 68` | README 서버 절이 `PGAUTH_HOST=scram-sha-256` 을 함께 쓴다. 거부하게 바꾸면 기본값이 바뀐다 |
| K27 | 다시 돌릴 때 `listen_addresses`·`port`·pg_hba 줄은 "없을 때만 추가" 라 값을 바꿔도 반영되지 않는다. 주석 처리된 같은 줄도 "있음" 으로 본다(`grep -qF`) | `tools/initdb.sh:50, 57, 69` | 주석 줄 오탐은 phase 9 에서 고친다. 값 반영: **고치지 않기로 함(2026-10-17).** 처음 한 번 쓰는 도구다 |
| K28 | `chmod -R a+rX "$root/src"` 가 `.git/config` 도 연다. clone URL에 토큰을 넣었다면 모두가 읽는다 | `tools/deploy.sh:192` | URL에 토큰을 넣지 않는다(README) |
| K29 | `DEPLOY_COMMANDS` 로 없는 명령을 주면 python이 exit 2를 내고, 마지막 확인(126/127만 봄)을 통과한다 | `tools/deploy.sh:250-252` | 자동으로 읽은 명령은 항상 있다 |
| K30 | 윈도우 `SKIP_START=1` 은 첫 실행에서 createdb가 실패한다(서버가 아직 안 떴다) | `tools/initdb.sh:75-102` | **고치지 않기로 함(2026-10-17).** README에 "서버를 띄운 뒤 다시 돌린다" 로 적었다 |
