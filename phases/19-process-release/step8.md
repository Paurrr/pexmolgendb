# Step 8: selection-pair

## 배경 (phase 19 공통)

이 저장소는 평소에 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 19는 예외로 **사용자가 2026-10-21 승인한 기능**이다. 승인된 동작은 다음과 같다.

> process 에 버전을 더해 (process, 버전)마다 device 데이터를 따로 관리한다. 버전은 `S00-V1.0.0.0` 같은 자유 문자열이다(앞뒤 공백만 다듬고 형식은 검사하지 않는다).
> - DB: process 행 하나가 (이름, 버전) 쌍이다. `process.release TEXT NOT NULL DEFAULT ''`, `UNIQUE (name, release)`. 지금 있는 process 는 빈 버전 `''` 이 된다. device·탭 테이블은 그대로 `process_id` 로 묶인다.
> - 마이그레이션은 `genviewer-init-db` 의 멱등 DDL 이다. 카탈로그를 보고 빠졌을 때만 ALTER 한다. `change_log.process_release` 도 더한다.
> - CSV 형식은 그대로다(버전 컬럼 없음, molgen 은 고치지 않는다). 불러올 때 버전을 정한다(CLI `load --version`, GUI Load CSV 가 묻는다). 내보내기 내용은 그대로이고 GUI 파일 이름 기본값만 molgen 규칙(`<proc>_<cid>-<ver 점 제거>.csv`)을 따른다.
> - 새 버전은 기존 (process, 버전)에서 DB 안에서 복제할 수 있다(device 와 탭 행, 한 시점 스냅샷).
> - 화면: Device 탭 툴바가 `Process [▾] Version [▾] [+][-]` 콤보 두 개다. 빈 버전은 `(없음)` 으로 보인다.
> - 이력: change_log 에 버전을 남기고 "process / device" 칸에 `sf2p S00-V1.0.0.0/nfet_a` 로 보인다. History 필터는 지금처럼 process 이름이다(모든 버전).
> - `+`(추가)는 저장 안 한 편집이 있으면 먼저 기존 "Save Changes" 를 묻고, 저장이 취소·실패하면 아무것도 만들지 않는다.

**이름 규칙.** 새 개념은 코드·DB 에서 **`release`** 다. 화면 라벨은 `Version`, CLI 옵션은 `--version` 이다. 새 개념에 `version` 이라는 이름(변수·키·컬럼·시그널)을 쓰지 마라. 이유: `device.version` 은 낙관적 잠금 카운터이고 `deviceVersionBumped`·`set_device_version`·`expected_version`·device dict 의 `"version"` 키 등 200곳 넘게 그 뜻으로 쓴다.

**빈 버전.** `''` 은 "버전 없음" 이고 옛 동작과 같다. repo 메서드의 `release` 인자는 keyword 이고 기본값 `""` 이다(옛 호출자·테스트가 그대로 돈다). 사람이 읽는 process 표시는 `audit.process_label(name, release)` 하나로 만든다(step 1이 만들었다). 빈 버전이면 `name`, 아니면 `f"{name} {release}"` 다. **빈 버전일 때 기존 문구·출력은 바이트까지 그대로여야 한다.**

이 phase의 step (각 step 은 앞 step 이 끝난 코드 위에서 돈다):
- step 0 `schema-release`: DDL·마이그레이션·`status` 진단 (DB)
- step 1 `audit-release`: change_log 에 버전, `process_label`, `recent(release=)` (DB)
- step 2 `process-repo-release`: `ProcessRepository`·`find_or_create` 가 (이름, 버전)을 받는다, `list_pairs` (DB)
- step 3 `audit-sources`: device·탭 저장 이력이 버전을 싣는다 (DB)
- step 4 `release-clone`: `ProcessRepository.clone` (DB)
- step 5 `io-release`: CSV 불러오기가 버전을 받는다 (DB)
- step 6 `cli-release`: `processes`·`load`·`export`·`log` (DB)
- step 7 `toolbar-pairs-view`: 툴바 view 의 콤보 두 개 (GUI)
- step 8 `selection-pair`: 컨트롤러가 (이름, 버전) 키로 전환·삭제한다 (GUI) ← 이 step
- step 9 `add-clone`: 추가 창(버전, 복제 원본) (GUI)
- step 10 `load-csv-release`: GUI Load CSV 의 버전, 내보내기 파일 이름 (GUI)

모든 step에 같은 규칙이 적용된다.
1. 기능이라 TDD로 한다. 새 동작을 단언하는 테스트를 먼저 쓰고, 수정 전에 실패하는 것을 본다(RED). 그 테스트 이름과 단언을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트만으로는 안 된다.
3. 고친 뒤 구현을 손으로 망가뜨려 새 테스트가 실패하는지 보고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
4. 이 파일의 행 번호는 2026-10-21(phase 18 직후) 기준 대략값이다. 이름으로 찾아라. phase 14~17(구조 제안 P2 Prompts·P4 공개 API·P3 SaveCoordinator·P5 남은 동기 DB 호출을 워커로, `docs/notes/architecture-proposal.md`)이 이 phase보다 먼저 끝났을 수 있다. 저장 확인 흐름(`_save_before_process_change`)이 SaveCoordinator 로 옮겨졌거나 process 목록 조회가 워커로 갔으면 실제 코드를 따르고 summary에 적는다. 그 구조를 되돌리지 않는다.
5. `config/tab_config.json` 과 device·탭 테이블의 컬럼을 바꾸지 않는다. `device.version`(낙관적 잠금)의 이름·의미를 바꾸지 않는다.
6. 사용자에게 보이는 새 문구는 그 step 파일이 적은 것만 만든다. 빈 버전일 때 기존 문구는 그대로다. 대화상자 제목은 영어, 본문·CLI 출력·주석은 한국어(CLAUDE.md).
7. 문서(`README.md`, `docs/*.md`, `CLAUDE.md`)는 phase 마무리에서 고친다. step에서는 바꾸지 않는다.
8. molgen 저장소(`../molgen`)를 고치지 마라.

## GUI 테스트 기반

작업 전에 `tests/gui/conftest.py`·`tests/gui_support/` 를 읽고, 이 파일의 서술과 다르면 실제 코드를 따른다.
- `store` 시드: sf2p(nfet_a·nfet_b), sf4u(pfet_a), 버전은 모두 `''`. 탭은 InstTerm·InstSchParam. actor는 `tester`. `seeded_store` 는 바꾸지 마라. 버전이 필요한 테스트는 그 테스트 안에서 `store.add_process(name, release=...)`·`store.add_device(...)` 로 더하고 `refresh_processes()` 로 목록을 다시 읽힌다.
- `device_tab_ctrl` 는 가짜에 붙어 이미 접속한 `DeviceTabController` 다(접속하면 첫 쌍 `("sf2p","")` 가 골라진다). `main_window` 도 있다.
- `dialogs`(autouse): 예/아니오는 `dialogs.answer_question(...)`, 저장 충돌은 `dialogs.answer_conflict(RELOAD|OVERWRITE|CANCEL)`. 뜬 문구는 `dialogs.shown` 의 `(kind, title, text)`. 답하지 않은 모달·메뉴는 `AssertionError` 이고 teardown에서 실패한다.
- 장애는 `store.fail_next(메서드, 예외)`, 남의 변경은 `store.touch_device`/`store.remove_device`, 일어난 일은 `store.calls_of(name)`. `edit_device_cell(ctrl, row, column, value)`, `edit_tab_cell`, `select_device_row` 를 쓴다.
- 고정 대기(`qtbot.wait`)는 쓰지 않는다. `qtbot.waitUntil` 콜백은 bool을 돌려준다.

## 선행 step

- step 2: `ProcessRepository` 의 keyword `release`, `list_pairs()`. 가짜도 같다(`FakeStore.releases`, `store.add_process(name, release="")`).
- step 7: 툴바 view 의 `selectionChanged(str, str)`, `set_pairs`, `select_pair`, `select_silently`, `current_pair`, `pairs`, `releases_of`, 빈 버전 글자 `(없음)`. 옛 API 는 아직 남아 있다.
- `phases/19-process-release/index.json` 의 step 0~7 summary 를 읽어라.

## 이 step의 목적

컨트롤러가 process 를 **(이름, 버전) 쌍**으로 고르고, 되돌리고, 지운다. device·탭·저장·폴링은 지금처럼 `process_id` 로 돈다. 이 step 이 끝나면 옛 view API 를 지운다.

### 바꿀 것

**툴바 컨트롤러** (`controllers/device_tab_toolbar.py`)
- `processChanged = Signal(str, str)`, `processRemoved = Signal(str, str)`(이름, 버전).
- `ui.selectionChanged` 를 `on_process_changed(name, release)` 에 잇는다. `process_selector.currentTextChanged` 연결은 뗀다.
- `setProcessesRequested`/`setProcessRequested` 를 쌍 판으로 바꾼다(예 `setPairsRequested(list)` → `ui.set_pairs`, `selectPairRequested(str, str)` → `ui.select_pair`).
- `refresh_processes()` 는 `repo.list_pairs()` 를 쓴다. 이름·`@report("Process List Failed")` 는 그대로.
- `select_process_silently(name, release="") -> bool` → `ui.select_silently`.
- `get_current_process()` 는 **이름**을 돌려준다(Load Virtuoso 가 쓴다, `main_window._action_load_virtuoso`). `get_current_release()` 를 더한다.
- `get_process_id(name, release="")` → `repo.get_or_create_id(name, release=release, actor=…)`.
- `remove_process(name, release="")`: `exists`·`count_devices`·`delete` 에 `release` 를 넘기고, 성공하면 `processRemoved.emit(name, release)` 뒤 `refresh_processes()`(지금 순서). 문구의 process 자리는 `process_label(name, release)`(빈 버전이면 지금 그대로): `"Not Found"`, `"Remove Process"` 질문, `"Removed"`, `report_error` 제목 `f"Remove Failed: {label}"`, 로그 `f"Process removed: {label}."`.
- `add_process(name)`: 이 step 에서는 지금 동작 그대로(빈 버전으로 만들고 `selectPairRequested(name, "")`). step 9 가 바꾼다.
- `@Slot(...)` 데코레이터의 인자 수를 새 시그널과 맞춘다. 이유: `@Slot(str)` 이 붙은 두 인자 핸들러는 PySide6 가 인자 하나로 부를 수 있다.

**툴바 view** (`views/device_tab_toolbar.py`)
- `removeProcessRequested = Signal(str, str)`. `open_remove_process_dialog` 는 `current_pair()` 를 쓰고 확인 문구의 process 자리에 `process_label` 을 쓴다(`"Confirm Delete"`, 빈 버전이면 지금 그대로). 빈 쌍이면 아무것도 하지 않는다.
- 옛 API(`set_processes`, `select_process`, `select_process_silently`)를 지운다. `process_selector` 위젯은 남는다(두 콤보 중 하나다).

**DeviceTabController** (`controllers/device_tab.py`)
- `on_process_changed(name, release)`: 저장 확인(`_save_before_process_change`)이 False 면 `select_process_silently(dt.current_process, dt.current_release)` 로 **두 콤보를** 되돌린다(목록에 없으면 넘어간다, 지금 규칙). 넘어가면 `get_process_id(name, release)`, `set_current_process(name)`, `set_current_release(release)`, `set_current_process_id(id)`, `refresh_devices()`, 탭 비우기. 빈 이름이면 셋 다 비운다. 로그 `f"Selected process: {label}."`.
- `_on_process_removed(name, release)`: **쌍으로** 비교한다. 이유: 이름만 비교하면 `("sf2p","V1")` 을 지울 때 `("sf2p","V2")` 를 보던 편집이 묻지도 않고 버려진다(K42 회귀).
- 시그널 연결의 인자 수를 맞춘다.

**DeviceTableController** (`controllers/device_table.py`)
- `current_release` 와 `set_current_release(release)` 를 더한다(기본 `""`).
- `current_process` 는 **이름 그대로**다. `process_name`(CSV `CdsLibName`, Virtuoso payload)으로 쓰인다. 버전을 섞지 마라.
- `current_process_id`, `dirty_by_process_id`, etag, 폴링 키 `(process_id, repo)` 는 바꾸지 않는다.

**테스트 헬퍼·기존 테스트**
- `tests/gui_support/helpers.py` `select_process(ctrl, name, release="")`: 쌍이 목록에 있는지 단언하고, 사용자처럼 고른다. 이름이 다르면 process 콤보를 바꾸고(view 가 버전을 자동으로 고른다), 그 뒤 버전이 원하는 것과 다르면 version 콤보를 바꾼다(사용자 동작 두 번 = 전환 두 번). 한 번에 옮겨야 하는 테스트는 `ui.select_pair` 를 쓴다. 기존 호출 `select_process(ctrl, "sf2p")` 는 그대로 돈다.
- `processChanged.connect(changes.append)` 로 기록하던 테스트(`test_deleted_process_revert.py`, `test_process_list_refresh.py`, `test_process_change_save.py` 의 `record_process_changes` 류)는 두 인자를 받게 고치고 기대값을 `("sf2p", "")` 꼴로 바꾼다.
- 툴바가 `list_all` 대신 `list_pairs` 를 부르므로 `store.calls_of("list_all")`·`fail_next("list_all", …)` 를 쓰던 테스트(`test_smoke.py`, `test_connect_db.py`, `test_process_list_refresh.py`, `test_deleted_process_revert.py` 등, grep 으로 찾는다)는 `list_pairs` 로 고친다. History 가 부르는 `list_all` 은 그대로다.
- `test_deleted_process_revert.py` 의 `test_a_remove_that_deletes_nothing_keeps_the_edits` 는 `delete` 를 `lambda name, *, actor="": False` 로 바꾼다. `release=` 를 받게 고친다(안 그러면 TypeError 가 "Remove Failed" 로 보여 테스트가 엉뚱하게 실패한다).
- `tests/gui/conftest.py` 의 docstring(“sf2p 가 골라진다”)을 쌍 기준으로 맞춘다.
- 고친 기존 테스트 이름을 summary에 적는다. 단언의 **성질**(시그널 한 번, 되돌리기, 편집 버리기)은 그대로 둔다.

### 상태표 (모든 경로의 최종 상태)

P = 지금 쌍 `(A, a)`(id p), T = 대상 `(B, b)`. "전환" = `on_process_changed(T)`.

| 사건 | 콤보 최종 | current (이름, 버전, id) | dirty | repo 호출·알림 |
|---|---|---|---|---|
| 사용자가 process 콤보를 B 로 | B, 버전은 a 가 B 에 있으면 a 아니면 B 의 첫 버전 | → 전환 | | `processChanged` 한 번 |
| 사용자가 version 콤보를 b 로 | (A, b) | → 전환 | | 한 번 |
| 전환, dirty 아님 | T | (B, b, 새 id) | F | `get_or_create_id(B, release=b)`, `fetch_devices_by_process`, `etag`. 배너 숨김, 탭 비움 |
| 전환, dirty, "Save Changes" 아니오 | T | (B, b, id) | F | 쓰기 없음(다시 읽어 편집이 버려진다) |
| 전환, dirty, 예, 저장 True(또는 충돌 RELOAD) | T | (B, b, id) | F | `upsert_devices`/`replace_many_for_device` 뒤 위와 같다 |
| 전환, dirty, 예, 충돌 CANCEL 이나 저장 예외로 편집이 남음, P 가 목록에 있음 | **P 로 되돌림(시그널 없음)** | 그대로 | T | `get_or_create_id` 없음 |
| 같은 상황인데 P 가 그 사이 목록에서 사라짐(남이 지움 + 목록 갱신) | T | (B, b, id) | F | 되돌릴 곳이 없어 넘어간다(phase 4 규칙) |
| `get_or_create_id` 예외 | T | (B, b, None) | F | `"Process Lookup Failed"` |
| `refresh_processes`, P 가 목록에 있음 | P | 그대로 | 그대로 | `list_pairs` 만, 시그널 없음 |
| `refresh_processes`, P 없고 A 의 다른 버전 있음 | (A, 첫 버전) | → 전환 | | 한 번 |
| `refresh_processes`, A 가 통째로 없음 / 목록이 빔 | 첫 쌍 / 빈 콤보 | → 전환 / ("", "", None), 질문 없음 | | 한 번 |
| 첫 접속 | 첫 쌍 | (첫 쌍, id) | F | `get_or_create_id` 정확히 한 번 |
| 다시 접속, P 가 새 목록에 있음 | P | 그대로 | 그대로 | `get_or_create_id` 없음 |
| `list_pairs` 예외 | 그대로 | 그대로 | 그대로 | `"Process List Failed"` |
| Remove, 지금 쌍 (A, a), 확인 | (A, 다른 버전) 또는 첫 쌍 | → 전환, **질문 없음** | F | `exists`·`count_devices`·`delete(A, release=a)` → `processRemoved(A, a)` 가 편집을 버림 → `list_pairs` |
| Remove (A, a) 인데 지금은 (A, a2) (예: 다른 경로로 지움) | (A, a2) | 그대로 | 그대로 | 편집을 버리지 않는다 |
| Remove 의 `delete` 예외 | 그대로 | 그대로 | T | `f"Remove Failed: {label}"` |
| Remove 성공 뒤 목록 갱신 실패 | 지운 쌍이 남아 보임 | 지운 쌍 | F | `"Process List Failed"`(지금 K49 와 같은 상태, `test_a_failed_list_refresh_after_removing_still_drops_the_edits`) |

## 읽어야 할 파일

- `/CLAUDE.md`(GUI 스레드, Task 규칙), `/docs/ARCHITECTURE.md`(저장 결과, 창 닫기, 변경 감지), `/docs/ADR.md`(ADR-004 phase 3·4·10 보강), `/docs/UI_GUIDE.md`, `docs/notes/known-issues.md`(K42, K49)
- `src/genviewer/views/device_tab_toolbar.py`(step 7 결과), `src/genviewer/controllers/device_tab_toolbar.py` 전체
- `src/genviewer/controllers/device_tab.py`: `__init__` 의 시그널 연결(~76-110), `apply_db`, `_poll_remote_changes`/`_poll_is_current`(process_id 키, 바꾸지 않는다), `on_process_changed`(~479), `_on_process_removed`(~508), `_save_before_process_change`(~517)
- `src/genviewer/controllers/device_table.py`: `current_process`/`current_process_id`(~74-79), `refresh_devices`, `set_current_*`(~557)
- `src/genviewer/controllers/main_window.py`: `_action_load_virtuoso`(이름만 쓴다, 바꾸지 않는다), `_may_close`
- `tests/gui_support/helpers.py`(`select_process`, 시드), `tests/gui/test_process_change_save.py`, `test_deleted_process_revert.py`, `test_process_list_refresh.py`, `test_poll_binding.py`, `test_connect_db.py`, `test_smoke.py`

## 작업

### 1. 테스트 먼저

새 `tests/gui/test_process_release_switch.py`(이름은 재량). 각 테스트가 `store.add_process("sf2p", release="V2")` + device(예 `nfet_v2`)를 더하고 `ctrl.device_tab_toolbar.refresh_processes()` 한 뒤:
- version 콤보로 V2 를 고르면 device 표가 V2 의 device 만 보이고 `dt.current_process == "sf2p"`, `dt.current_release == "V2"`, `current_process_id` 가 V2 의 id 다. `get_or_create_id` 기록에 `release == "V2"`(RED).
- V2 에서 device 를 고친(dirty) 채 빈 버전을 고르고 "Save Changes" 예 → 저장 충돌 CANCEL(`store.touch_device` 로 충돌을 만든다) → 두 콤보가 `("sf2p","V2")` 로 되돌아가고 편집이 남는다.
- 같은 상황에서 되돌릴 V2 가 그 사이 지워지고 목록이 갱신됐으면 새 쌍으로 넘어간다.
- `("sf2p","V2")` 를 보며 dirty 인 채로 `("sf2p","")` 를 Remove 하면(컨트롤러 `remove_process("sf2p", "")` 직접 호출 + 질문 예) V2 의 편집이 남는다(dirty 그대로). 지금 쌍 V2 를 Remove 하면 질문 없이 `("sf2p","")` 로 넘어가고 V2 의 device 만 지워진다(`store` 에 빈 버전 device 가 남는다).
- Remove 확인 문구가 `Process 'sf2p V2' 을(를) 삭제하면 device 1개와 …` 이고, 빈 버전이면 지금 문구 그대로다.
- 폴링: V2 를 보는 동안 빈 버전 쪽 device 를 남이 바꿔도 배너가 뜨지 않는다(etag 는 process_id 기준, 지금 `test_poll_binding.py` 방식).
- 첫 접속은 `get_or_create_id` 를 한 번 부르고 쌍은 `("sf2p","")` 다.

수정 전에는 버전을 고르는 테스트가 실패해야 한다(컨트롤러가 `selectionChanged` 를 듣지 않는다).

### 2. 수정

위 "바꿀 것" 대로. 상태표의 모든 줄을 기존 테스트나 새 테스트가 덮는지 확인하고, 덮지 않는 줄은 테스트를 더한다.

### 3. 변이 검사

- `_on_process_removed` 를 이름만 비교하게 되돌려 "다른 버전 Remove" 테스트가 실패하는지 본다. 되돌린다.
- 되돌리기를 `select_process_silently(dt.current_process)`(버전 없음)로 바꿔 CANCEL 테스트가 실패하는지 본다. 되돌린다.
- `get_process_id` 가 `release` 를 넘기지 않게 해 V2 전환 테스트가 실패하는지 본다. 되돌린다.

창을 띄워 손으로 확인하는 것은 이 step 에서 하지 않는다(세션이 창이 닫히기를 기다리며 멈춘다). phase 마무리에서 사람이 한다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_process_release_switch.py tests/gui/test_toolbar_pairs_view.py -q   # 새 테스트 통과 (파일 이름이 다르면 그 파일)
uv run pytest tests/gui -q
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 상태표의 모든 줄에 테스트가 있는가?
   - `current_process` 가 이름 그대로여서 내보내기·Virtuoso payload 의 `CdsLibName` 이 그대로인가(`tests/gui/test_send_device_data.py` 통과)?
   - 폴링·저장·dirty 가 `process_id` 기준 그대로인가?
   - 빈 버전일 때 모든 문구가 지금과 같은가?
   - 워커 스레드에서 위젯을 만지지 않는가? 새 동기 DB 호출을 GUI 스레드에 더하지 않았는가(지금 있는 동기 호출의 인자만 바꿨는가)?
3. 결과에 따라 `phases/19-process-release/index.json` 의 step 8을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "툴바 컨트롤러 processChanged/processRemoved(str,str), selectionChanged 연결, list_pairs, select_process_silently(name, release), get_process_id(name, release), remove_process(name, release) 문구 process_label. DeviceTabController 쌍 되돌리기·쌍 비교 _on_process_removed. DeviceTableController.current_release. 옛 view API 삭제. helpers.select_process(ctrl, name, release=''). RED: <테스트 이름: 단언>. 변이: <결과>. 고친 기존 테스트: <이름>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `current_process` 에 버전을 섞지 마라(예 `"sf2p V2"`). 이유: 내보내기 CSV 의 `CdsLibName`, Virtuoso payload, Load Virtuoso 필터가 이 값을 Cadence 라이브러리 이름으로 쓴다.
- 폴링 키·etag·`dirty_by_process_id` 를 쌍으로 바꾸지 마라. 이유: 이미 `process_id` 가 쌍마다 다르다.
- Add(+)의 흐름을 바꾸지 마라. 이유: step 9 의 일이다(추가 창, 저장 먼저 묻기, 복제).
- Load CSV·내보내기 파일 이름을 바꾸지 마라. 이유: step 10 의 일이다.
- History 화면을 바꾸지 마라. 이유: 승인대로 process 이름 필터 그대로다.
- 새 질문·알림을 만들지 마라(문구의 process 자리에 버전이 붙는 것만 바뀐다).
- 기존 테스트의 단언 성질을 약하게 만들지 마라. 시그널 인자·호출 이름이 바뀐 만큼만 고친다.
