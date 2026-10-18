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
| K8 | `init_db --owner` 를 `--owner` 없이 처음 만든 옛 DB에 다시 돌리면 "must be owner of table" 로 DDL 트랜잭션 전체가 롤백된다 | `scripts/init_db.py:90-100` | **고치지 않기로 함(2026-10-17).** 2026-09-15 이전 DB에만 해당한다. 그런 DB는 `ALTER TABLE … OWNER TO` 로 한 번 정리한다 |
| K33 | `upsert_device` 에 `id` 가 있는 dict를 주면 version 검사 없이 덮어쓰고 `process_id` 도 바꾼다 | `repo/device.py:97-` | **고치지 않기로 함(2026-10-17).** 지금 호출자(붙여넣기 `paste_rows`)는 `id` 없는 dict만 넘겨 닿지 않는다. phase 2 step 1이 가짜를 만들다 본 것이고 재현하지 않았다. 가짜도 지금 동작을 그대로 흉내 낸다 |
| K44 | CSV에 Description 컬럼이 없다(molgen 형식). 불러오기로 만든 device는 description이 비고, 내보내기도 Description을 쓰지 않아 내보낸 CSV를 다시 넣으면 description이 따라오지 않는다. 저장된 device의 description은 불러오기가 건드리지 않는다 | `repo/io.py:118-122` (device INSERT), `:217` (export 헤더), `controllers/device_table.py:461-470` (GUI 내보내기 device_info) | 2026-10-17 사용자 제보("CSV import 하면 description 이 날라간다")를 조사하다 확인했다. 저장하지 않은 편집이 사라지는 쪽은 K36이다. 사용자가 같은 날 왕복을 승인했다(phase 18). molgen `pexGenDB_GenDev_Get_Header_Type()` 에 `'Description "string"` 을 먼저 등록해야 한다. 안 그러면 셀마다 `Unknown header type` warn이 뜬다 |
| K46 | 표시 시각이 서버 세션 TimeZone 기준이다. 서버 세션이 UTC면 `log` 출력·History·`log --out` CSV 의 `at` 이 UTC로 찍힌다. 시간 필터(`--since`·`--purge-before`·History 기간)는 2026-10-18 phase 7 에서 클라이언트 시각으로 고쳤다(K6) | `repo/audit.py` `format_line`, `controllers/history_tab.py`, `cli.py` `_write_log_csv` | 표시가 바뀌는 동작 변경이다. 서버 TimeZone이 KST면 문제가 없다(`SHOW timezone`) |
| K47 | `init_db` 를 다시 돌리면 탭 테이블마다 `CREATE INDEX IF NOT EXISTS` 가 인덱스가 이미 있어도 `ShareLock` 을 잡는다. 열려 있는 쓰기 트랜잭션 뒤에서 기다리고, DDL 트랜잭션이 끝날 때까지 그 탭의 다른 쓰기가 줄을 선다. 읽기는 막지 않는다. 컬럼 더하기는 phase 8 이 카탈로그를 먼저 보게 해서 잠그지 않는다 | `service/schema.py` `pg_child_index_ddl` | 2026-10-18 phase 8 리뷰에서 일회성 스크립트로 재현했다(쓰기 트랜잭션을 연 채 `lock_timeout = 500ms` 로 DDL → `idx_inst_terms_device_id` 에서 55P03). phase 8 전부터 있던 동작이다. 저장 트랜잭션이 짧아서 기다림도 짧다. 고치려면 인덱스도 카탈로그를 보고 없을 때만 만든다 |

## 내보내기·연동

| # | 문제 | 위치 | 왜 기록만 하나 |
|---|---|---|---|
| K15 | Load Libs 요청이 빈 프레임이다(stub) | `service/virtuoso_protocol.py:17-18` | **고치지 않기로 함(2026-10-17).** 기능이 아직 없다(Virtuoso 쪽 함수가 정해지지 않았다) |
| K16 | Virtuoso 목록 필터가 부분 문자열(`name in r["name"]`)이라 더 많이 걸릴 수 있다(내보내기 형식은 2026-10-18 phase 11 에서 파일 확장자로 정하게 고쳤다) | `controllers/device_table.py` `refresh_devices` | **고치지 않기로 함(2026-10-17).** 접미사가 붙은 이름까지 잡는 것이 의도다 |

## GUI (phase에 넣지 않은 것)

| # | 문제 | 위치 | 왜 기록만 하나 |
|---|---|---|---|
| K25 | `question()` 은 None을 돌려주지 않으므로 `_switch_device_by_index` 의 `choice is None` 분기는 닿지 않는 코드다 | `controllers/device_tab.py:508`, `utils/dialogs.py:21-25` | 동작에 영향 없음 |
| K45 | 내 쓰기가 시작되기 직전에 출발한 폴링의 결과가 `remember_etag` 뒤에 도착하면, 저장 전 etag와 새 기준점이 달라 거짓 배너가 뜰 수 있다 | `controllers/device_tab.py` `_poll_remote_changes`·`_on_poll_result`, `controllers/device_table.py` `remember_etag` | K43을 조사하다 코드를 읽고 본 것이고 재현하지 않았다. 폴링 쿼리가 저장 전체보다 오래 걸려야 닿아서 확률이 매우 낮다. 2026-10-18 phase 12 step 3 은 결과를 시작할 때의 process·DB 에 묶었을 뿐 기준점에는 묶지 않아(같은 process 로 돌아온 뒤 도착한 결과는 써야 한다) 이 경합은 그대로다 |
| K48 | 충돌에 "수정"(stale)과 "삭제"(deleted)가 섞여 있으면 지금처럼 다시 읽기/덮어쓰기/취소를 다 내놓는다. 덮어쓰기를 고르면 남이 지운 device의 편집은 쓸 행이 없어 조용히 버려진다 | `controllers/device_table.py` `_write_devices`, `service/repo/device.py` `_update_existing`(force면 사라진 행은 맞는 행이 없어 지나간다) | 2026-10-18 phase 10 step 0이 찾았다. 승인 범위는 남은 충돌이 전부 삭제일 때만 덮어쓰기를 숨기는 것이었다(K20). `tests/gui/test_conflict_deleted_only.py::test_a_stale_and_deleted_conflict_still_offers_overwrite` 가 세 갈래를 고정한다(취소로 끝나서 버려지는 것은 재현하지 않았다) |
| K49 | Remove Process 뒤 process 목록 다시 읽기가 실패하면("Process List Failed") 콤보와 device 표가 지운 process에 머문다. 편집은 버려서 dirty가 아니지만 device 표를 다시 읽지 않아, 지운 device 행이 고친 셀 표시까지 그대로 보인다. 탭은 비었다 | `controllers/device_tab_toolbar.py` `remove_process`, `controllers/device_tab.py` `_on_process_removed` | 2026-10-18 phase 10 step 5가 찾았다. `tests/gui/test_deleted_process_revert.py::test_a_failed_list_refresh_after_removing_still_drops_the_edits` 가 이 상태를 고정한다. 삭제는 성공하고 바로 뒤의 목록 조회만 실패해야 닿는다 |
| K50 | Virtuoso 목록으로 걸러 본 채 저장하면 보이는 행이 자기들의 옛 순서값을 나눠 갖는다(K19). 그래서 refresh 때 이미 겹쳐 있던 순서값(예전의 `0..k-1` 저장이 남긴 것)은 걸러 본 저장으로 풀리지 않는다. 같은 값의 숨은 행이 있으면 새 행이 그 숨은 행 뒤에 올 수 있다 | `controllers/device_table.py` `_filtered_orders` | 2026-10-18 phase 10 step 6이 찾았다. 숨은 행을 보내지 않는 것이 승인 범위다. 필터 없이 저장하면 모든 행이 `0..n-1` 로 다시 매겨져 풀린다 |
| K51 | History 다시 읽기 중에 필터나 DB가 바뀌어 보류된 다시 읽기는 앞 작업이 정리될 때 띄운다. 그 순간 `run_blocking`(저장·접속·CSV 불러오기)이 돌고 있으면(`is_busy()`) 건너뛰고 보류만 남는다. 자동 갱신이 켜져 있으면 다음 틱(10초)이, 꺼져 있으면 사용자의 다음 필터 변경·새로고침이 읽는다 | `controllers/history_tab.py` `_clear_task`, `reload` | 2026-10-18 phase 12 step 2가 남긴 것이고 재현하지 않았다. 보기 전용이고 History는 `--history` 로 띄웠을 때만 있다 |

## 운영 스크립트

| # | 문제 | 위치 | 왜 기록만 하나 |
|---|---|---|---|
| K27 | 다시 돌릴 때 `listen_addresses`·`port`·pg_hba 줄은 "없을 때만 추가" 라 값을 바꿔도 반영되지 않는다 | `tools/initdb.sh:60, 67, 80` | **고치지 않기로 함(2026-10-17).** 처음 한 번 쓰는 도구다. 주석 처리된 같은 hba 줄을 "있음" 으로 보던 것은 2026-10-18 phase 9 에서 고쳤다(`grep -qxF`) |
| K30 | 윈도우 `SKIP_START=1` 은 첫 실행에서 createdb가 실패한다(서버가 아직 안 떴다) | `tools/initdb.sh:75-102` | **고치지 않기로 함(2026-10-17).** README에 "서버를 띄운 뒤 다시 돌린다" 로 적었다 |
