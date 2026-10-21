# Step 9: add-clone

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
- step 8 `selection-pair`: 컨트롤러가 (이름, 버전) 키로 전환·삭제한다 (GUI)
- step 9 `add-clone`: 추가 창(버전, 복제 원본) (GUI) ← 이 step
- step 10 `load-csv-release`: GUI Load CSV 의 버전, 내보내기 파일 이름 (GUI)

모든 step에 같은 규칙이 적용된다.
1. 기능이라 TDD로 한다. 새 동작을 단언하는 테스트를 먼저 쓰고, 수정 전에 실패하는 것을 본다(RED). 그 테스트 이름과 단언을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트만으로는 안 된다.
3. 고친 뒤 구현을 손으로 망가뜨려 새 테스트가 실패하는지 보고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
4. 이 파일의 행 번호는 2026-10-21(phase 18 직후) 기준 대략값이다. 이름으로 찾아라. phase 14~17(구조 제안 P2 Prompts·P4 공개 API·P3 SaveCoordinator·P5 남은 동기 DB 호출을 워커로, `docs/notes/architecture-proposal.md`)이 이 phase보다 먼저 끝났을 수 있다. 대화상자 대역, 저장 확인 흐름, DB 호출 위치가 바뀌었으면 실제 코드를 따르고 summary에 적는다. 그 구조를 되돌리지 않는다.
5. `config/tab_config.json` 과 device·탭 테이블의 컬럼을 바꾸지 않는다. `device.version`(낙관적 잠금)의 이름·의미를 바꾸지 않는다.
6. 사용자에게 보이는 새 문구는 그 step 파일이 적은 것만 만든다. 빈 버전일 때 기존 문구는 그대로다. 대화상자 제목은 영어, 본문·CLI 출력·주석은 한국어(CLAUDE.md).
7. 문서(`README.md`, `docs/*.md`, `CLAUDE.md`)는 phase 마무리에서 고친다. step에서는 바꾸지 않는다.
8. molgen 저장소(`../molgen`)를 고치지 마라.

## GUI 테스트 기반

작업 전에 `tests/gui/conftest.py`·`tests/gui_support/` 를 읽고, 이 파일의 서술과 다르면 실제 코드를 따른다.
- `store` 시드: sf2p(nfet_a·nfet_b), sf4u(pfet_a), 버전은 모두 `''`. 탭은 InstTerm·InstSchParam. actor는 `tester`. `seeded_store` 는 바꾸지 마라. 버전이 필요한 테스트는 그 테스트 안에서 더한다.
- `device_tab_ctrl` 는 가짜에 붙어 이미 접속한 `DeviceTabController` 다(첫 쌍 `("sf2p","")`).
- `dialogs`(autouse): 예/아니오는 `dialogs.answer_question(...)`, 저장 충돌은 `dialogs.answer_conflict(...)`. 뜬 문구는 `dialogs.shown`. 답하지 않은 모달·`QInputDialog.*`·`QDialog.exec` 는 `AssertionError` 다. 그래서 추가 창은 view 의 stub 가능한 메서드(`_ask_add_pair`) 뒤에 두고, 테스트는 그것을 monkeypatch 하거나 컨트롤러 `add_process(...)` 를 직접 부른다. 창 자체는 `exec` 없이 만들어 위젯을 채워 시험한다.
- 새 모듈이 `genviewer.utils.dialogs` 의 `question`·`info`·`warning`·`error`·`critical` 을 import 하면 `tests/gui_support/dialogs.py` 의 `QUESTION_MODULES`/`MESSAGE_MODULES` 에 더해야 한다(`tests/gui/test_dialogs_fixture.py::test_every_dialogs_import_is_patched`). 추가 창은 그것들을 import 하지 않는다(잘못된 입력은 OK 를 끄는 것으로 막는다).
- 장애는 `store.fail_next(메서드, 예외)`, 일어난 일은 `store.calls_of(name)`. `run_blocking` 은 테스트에서도 워커 `Task` 로 돈다. 끝난 뒤를 단언하려면 `qtbot.waitUntil(lambda: store.calls_of("clone") != [])` 처럼 기다린다. 고정 대기(`qtbot.wait`)는 쓰지 않는다.

## 선행 step

- step 4: `ProcessRepository.clone(src_name, src_release, name, release, *, actor="") -> int | None`(대상이 있으면 None, 원본이 없으면 `LookupError`). 가짜도 같다.
- step 7·8: 툴바 view `pairs()`·`current_pair()`·`select_pair`, 컨트롤러 `selectPairRequested`, `processChanged(str, str)`, `DeviceTabController._save_before_process_change`, `remove_process(name, release)`.
- `phases/19-process-release/index.json` 의 step 0~8 summary 를 읽어라.

## 이 step의 목적

`+` 로 (이름, 버전) 쌍을 만들고, 원하면 기존 쌍에서 복제한다. 저장 안 한 편집이 있으면 만들기 **전에** 묻는다.

### 추가 창 `dialogs/add_process.py` (새 파일)

- `AddProcessDialog(QDialog)`, 제목 `"Add Process"`(지금 QInputDialog 제목과 같다).
- 칸(라벨은 툴바처럼 영어): `Process`(편집 가능한 콤보, 항목은 있는 이름들, 처음 값은 지금 이름), `Version`(한 줄 입력, 처음 값은 빈칸), `Copy from`(콤보. 첫 항목 `(복사 안 함)`, 그 뒤 모든 쌍을 `process_label` 로, 처음 값은 `(복사 안 함)`).
- OK 는 다음일 때 꺼진다: 이름이 공백뿐 / 버전이 `(없음)` / (다듬은 이름, 다듬은 버전) 쌍이 이미 있음. 끈 이유를 창 안의 한 줄 라벨로 보인다(예 `이미 있는 process 다.`, `(없음) 은 버전 이름으로 쓸 수 없다.`). 메시지 상자를 띄우지 않는다.
- 결과: `values() -> tuple[str, str, tuple[str, str] | None]` = (다듬은 이름, 다듬은 버전, 복사 원본 쌍 또는 None).
- 생성자는 지금 쌍 목록과 지금 쌍을 받는다(repo 를 모른다).

### view (`views/device_tab_toolbar.py`)

- `addProcessRequested = Signal(str, str, object)`(이름, 버전, 원본 또는 None).
- `open_add_process_dialog` → `self._ask_add_pair()`(창을 만들어 `exec`, OK 면 `values()`, 아니면 None) → None 이 아니면 emit. 지금의 `QInputDialog.getText(… "Add Process", "Enter new process name:")` 는 이 창으로 바뀐다(승인된 화면 변경).

### 컨트롤러 (`controllers/device_tab_toolbar.py` `add_process(name, release="", source=None)`)

순서와 결과:

| 경우 | 결과 |
|---|---|
| DB 없음 | 지금처럼 `"Database Not Loaded"`, 아무것도 안 함 |
| 저장 안 한 편집 있음 → "Save Changes" 질문 | `DeviceTabController` 가 넘겨준 확인 함수(예 `set_add_guard(...)`, 지금 `device_table.set_unsaved_tabs_check` 처럼 callable 을 넘기는 방식)가 `_save_before_process_change()` 를 부른다. **False 면 아무것도 만들지 않고 끝낸다**(알림 없음, 편집·선택 그대로) |
| 예 → 저장 성공(또는 충돌 RELOAD) | 만들기로 간다. 편집은 이미 저장됐다 |
| 아니오 | 만들기로 간다. **만들기에 성공한 뒤, 새 쌍을 고르기 전에** 편집을 버린다(`_on_process_removed` 처럼 dirty 를 풀고 탭을 비운다). 그래서 새 쌍으로 넘어갈 때 질문이 두 번 뜨지 않는다. 만들기가 실패하면 편집은 남는다 |
| 만들기 | `run_blocking` 으로 돌린다. 원본이 없으면 `repo.add(name, release=release, actor=…)`, 있으면 `repo.clone(src_name, src_release, name, release, actor=…)` |
| 이미 있음(add False / clone None) | 지금처럼 `"Duplicate"` 경고 `f"Process '{label}' already exists."`, 목록 다시 읽기, 그 쌍 고르기 |
| 성공 | 목록 다시 읽기 → `selectPairRequested(name, release)`(전환) → `"Success"` 알림 `f"Process '{label}' added."`. 복제면 둘째 줄 `f"{src_label} 에서 device {n}개를 복사했다."`. 로그 `f"Process added: {label}."`(복제면 끝에 ` (from {src_label}, device {n})`) |
| 만들기 예외(원본이 사라진 `LookupError`, DB 오류) | `@report("Process Add Failed")` 가 `user_message` 로 알린다(지금 데코레이터). 아무것도 만들어지지 않았고 편집·선택 그대로 |

`label = process_label(name, release)`, `src_label = process_label(*source)`. 빈 버전·원본 없음이면 문구가 지금과 바이트까지 같다.

**승인된 동작 변경**: 지금은 저장이 취소돼도 process 를 만들고 고르지만 않는다(`tests/gui/test_process_change_save.py::test_adding_a_process_after_cancelling_a_tab_conflict_keeps_the_tab_edits` 가 그 상태를 고정한다). 이제는 만들지 않는다. 그 테스트의 기대값을 "만들지 않음(`store.calls_of("add") == []`, 콤보에 `new_p` 없음, `changes == []`)" 으로 고치고 이름도 뜻에 맞게 바꾼다. 탭 편집이 남는다는 단언과 질문 한 번 단언은 그대로 둔다.

## 읽어야 할 파일

- `/CLAUDE.md`(GUI 스레드, `run_blocking`, 문구 규칙), `/docs/UI_GUIDE.md`, `/docs/ARCHITECTURE.md`(저장 결과, 스레딩), `/docs/ADR.md`(ADR-004 phase 3·4·10 보강)
- `src/genviewer/views/device_tab_toolbar.py`, `src/genviewer/controllers/device_tab_toolbar.py`(step 8 결과, `add_process`)
- `src/genviewer/controllers/device_tab.py`: `_save_before_process_change`, `_on_process_removed`, `__init__` 의 연결, `device_table.set_unsaved_tabs_check(...)` 를 넘기는 방식
- `src/genviewer/dialogs/` 의 다른 창(`insert.py`, `tab_selector.py`) — 창 만드는 관례
- `src/genviewer/utils/background.py`: `run_blocking`
- `src/genviewer/service/repo/audit.py`: `process_label`
- `tests/gui/test_process_change_save.py`(Add Process 절), `tests/gui/test_process_list_refresh.py`(~96 `add_process("new_p")`), `tests/gui/test_device_save_result.py`(~57), `tests/gui/test_dialogs_fixture.py`, `tests/gui_support/dialogs.py`

## 작업

### 1. 테스트 먼저

창(`tests/gui/test_add_process_dialog.py`, `exec` 없이):
- 이름이 빈칸이거나 공백뿐이면 OK 꺼짐. 버전 `(없음)` 이면 꺼짐. `("sf2p","")` 이 이미 있을 때 이름 `sf2p`·버전 빈칸이면 꺼짐, 버전 `V2` 면 켜짐.
- `values()` 가 앞뒤 공백을 지우고, `Copy from` 이 `(복사 안 함)` 이면 원본 None, 쌍을 고르면 그 쌍.

컨트롤러(`tests/gui/test_add_release.py` 등):
- `add_process("sf2p", "V2")` → `store` 에 `("sf2p","V2")`, 콤보가 그 쌍, device 표가 비었다, `"Success"` 문구 `Process 'sf2p V2' added.`.
- `add_process("sf2p", "V2", ("sf2p", ""))` → `clone` 이 불리고(`run_blocking`), V2 의 device 표에 nfet_a·nfet_b 가 보이며 탭 행도 복사됐다. 둘째 줄 `sf2p 에서 device 2개를 복사했다.`
- dirty + 예 + 충돌 CANCEL → `add`·`clone` 이 불리지 않고, 콤보·편집 그대로, 질문 한 번(RED: 지금은 만든다).
- dirty + 아니오 → 만들고 새 쌍으로 넘어가며 `"Save Changes"` 질문은 **한 번**뿐.
- dirty + 아니오 + `store.fail_next("clone", RuntimeError(...))` → `"Process Add Failed"`, 편집이 남고 쌍 그대로.
- 이미 있는 쌍 → `"Duplicate"` 와 그 쌍으로 이동.
- view: `_ask_add_pair` 를 `lambda: ("sf2p", "V2", None)` 로 바꾸고 `+` 버튼을 누르면 위와 같이 만들어진다. None 이면 아무것도 불리지 않는다.
- 빈 버전 추가 `add_process("new_p")` 의 문구·결과가 지금과 같다(기존 테스트).

수정 전에는 새 테스트가 실패해야 한다.

### 2. 수정

위 명세대로. 기존 `add_process(name)` 호출(테스트)은 그대로 돌아야 한다(기본값).

### 3. 변이 검사

- 확인 함수가 False 일 때도 만들게 바꿔 CANCEL 테스트가 실패하는지 본다. 되돌린다.
- "아니오" 의 편집 버리기를 만들기 앞으로 옮겨 실패 테스트(편집이 남아야 함)가 실패하는지 본다. 되돌린다.
- 편집 버리기를 빼서 "질문 한 번" 테스트가 실패하는지 본다. 되돌린다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_add_process_dialog.py tests/gui/test_add_release.py tests/gui/test_process_change_save.py tests/gui/test_dialogs_fixture.py -q   # 새 파일 이름이 다르면 그 파일
uv run pytest tests/gui -q
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 복제·추가가 `run_blocking` 으로 돌고, 워커에서 위젯을 만지지 않는가?
   - 저장이 취소·실패하면 아무것도 만들지 않는가? "아니오" 일 때 질문이 한 번인가?
   - 추가 창이 repo·메시지 상자를 모르는가?
   - 빈 버전·원본 없음의 문구가 지금과 같은가?
3. 결과에 따라 `phases/19-process-release/index.json` 의 step 9를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "dialogs/add_process.AddProcessDialog(Process/Version/Copy from, OK 끄기), view _ask_add_pair·addProcessRequested(str,str,object), add_process(name, release='', source=None): 저장 확인 먼저(False 면 안 만듦), run_blocking add|clone, 아니오면 성공 뒤 편집 버림. 승인된 변경: <고친 기존 테스트 이름>. RED: <테스트 이름: 단언>. 변이: <결과>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 복제·추가를 GUI 스레드에서 동기로 부르지 마라. 이유: 복제는 device 수백 개·탭 행 수천 개를 쓸 수 있다(CLAUDE.md: 새 DB 호출은 `run_blocking`).
- "아니오" 의 편집 버리기를 만들기 전에 하지 마라. 이유: 만들기가 실패하면 편집만 사라진다.
- 추가 창에서 `question`/`warning` 등을 띄우지 마라. 이유: 잘못된 입력은 OK 를 끄는 것으로 충분하고, 띄우면 dialogs fixture 등록이 필요해진다.
- 복제 원본의 기본값을 지금 쌍으로 두지 마라(`(복사 안 함)` 이 기본). 이유: 새 process 를 만들려던 사람이 모르고 device 를 복사하게 된다.
- Remove·전환 흐름(step 8)을 바꾸지 마라.
- 기존 테스트를 깨뜨리지 마라. 승인된 동작 변경에 걸린 테스트만 기대값을 고친다.
