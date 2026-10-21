# Step 7: toolbar-pairs-view

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
- step 7 `toolbar-pairs-view`: 툴바 view 의 콤보 두 개 (GUI) ← 이 step
- step 8 `selection-pair`: 컨트롤러가 (이름, 버전) 키로 전환·삭제한다 (GUI)
- step 9 `add-clone`: 추가 창(버전, 복제 원본) (GUI)
- step 10 `load-csv-release`: GUI Load CSV 의 버전, 내보내기 파일 이름 (GUI)

모든 step에 같은 규칙이 적용된다.
1. 기능이라 TDD로 한다. 새 동작을 단언하는 테스트를 먼저 쓰고, 수정 전에 실패하는 것을 본다(RED). 그 테스트 이름과 단언을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트만으로는 안 된다.
3. 고친 뒤 구현을 손으로 망가뜨려 새 테스트가 실패하는지 보고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
4. 이 파일의 행 번호는 2026-10-21(phase 18 직후) 기준 대략값이다. 이름으로 찾아라. phase 14~17(구조 제안 P2~P5, `docs/notes/architecture-proposal.md`)이 이 phase보다 먼저 끝났을 수 있다. 대화상자 대역, private 이름, DB 호출 위치가 바뀌었으면 실제 코드를 따르고 summary에 적는다. 그 구조를 되돌리지 않는다.
5. `config/tab_config.json` 과 device·탭 테이블의 컬럼을 바꾸지 않는다. `device.version`(낙관적 잠금)의 이름·의미를 바꾸지 않는다.
6. 사용자에게 보이는 새 문구는 그 step 파일이 적은 것만 만든다. 빈 버전일 때 기존 문구는 그대로다. 대화상자 제목은 영어, 본문·CLI 출력·주석은 한국어(CLAUDE.md).
7. 문서(`README.md`, `docs/*.md`, `CLAUDE.md`)는 phase 마무리에서 고친다. step에서는 바꾸지 않는다.
8. molgen 저장소(`../molgen`)를 고치지 마라.

## GUI 테스트 기반

작업 전에 `tests/gui/conftest.py`·`tests/gui_support/` 를 읽고, 이 파일의 서술과 다르면 실제 코드를 따른다.
- GUI 테스트는 `tests/gui/` 에 둔다(pytest-qt, offscreen). 이 step 의 테스트는 view 하나(`DeviceTabToolBar`)를 `qtbot.addWidget` 으로 직접 만들어 쓴다. DB·컨트롤러가 필요 없다.
- `dialogs`(autouse) 가 모달을 대신한다. 답하지 않은 모달은 `AssertionError` 다. 이 step 은 모달을 띄우지 않는다.
- 고정 대기(`qtbot.wait`)는 쓰지 않는다. 시그널은 리스트에 모아 동기로 단언한다.

## 선행 step

- step 2: `ProcessRepository.list_pairs()` 가 `[(name, release), …]` 를 이름 순, 같은 이름 안에서 버전 코드포인트 순으로 준다(빈 버전이 맨 앞). 이 step 은 그 목록을 받을 view API 를 만든다.
- `phases/19-process-release/index.json` 의 step 0~6 summary 를 읽어라.

## 이 step의 목적

툴바 **view**(`views/device_tab_toolbar.py`)에 Version 콤보를 더하고, 두 콤보를 묶어 (이름, 버전) 쌍을 다루는 API 를 만든다. 컨트롤러는 이 step 에서 바꾸지 않는다(step 8). 그래서 **옛 API(`set_processes`, `select_process`, `select_process_silently`, `process_selector.currentTextChanged` 를 컨트롤러가 듣는 것)는 그대로 남기고 지금처럼 동작해야 한다.** 이 step 이 끝나도 앱 동작은 그대로다(Version 콤보는 비어 있다).

배치(UI_GUIDE 의 툴바 줄): `Process [process 콤보] Version [version 콤보] [+] [-] Load Virtuoso | Library …`. Version 라벨·콤보는 Process 라벨·콤보와 같은 크기 정책(라벨 Fixed, 콤보 Preferred + `AdjustToContents`, 최소 폭은 재량, 예 120).

새 view API:

| 이름 | 계약 |
|---|---|
| `selectionChanged = Signal(str, str)` | (이름, 버전). **사용자 동작 한 번 또는 실제로 바뀐 선택 한 번에 정확히 한 번** 낸다. 옛 `process_selector.currentTextChanged` 와 별개다 |
| `set_pairs(pairs: list[tuple[str, str]])` | 두 콤보를 시그널 없이 다시 채운다. process 콤보에는 서로 다른 이름을 `pairs` 순서대로, version 콤보에는 고른 이름의 버전을 `pairs` 순서대로 넣는다. 선택 규칙: (1) 지금 쌍이 목록에 있으면 그대로 (2) 지금 이름은 있고 버전이 없으면 그 이름의 첫 버전 (3) 이름도 없으면 첫 쌍 (4) 목록이 비면 둘 다 빈다. 채운 뒤 쌍이 바뀌었으면(빈 쌍 `("", "")` 으로 바뀐 것 포함) `selectionChanged` 를 한 번 낸다 |
| `select_pair(name, release)` | 그 쌍을 고른다. 바뀌었으면 `selectionChanged` 한 번. 없는 쌍이면 아무것도 하지 않는다 |
| `select_silently(name, release) -> bool` | 시그널 없이 그 쌍을 고른다. 없으면 **아무것도 바꾸지 않고** False |
| `current_pair() -> tuple[str, str]` | 지금 쌍. 비었으면 `("", "")` |
| `pairs() -> list[tuple[str, str]]`, `releases_of(name) -> list[str]` | 지금 목록(step 9·10 의 입력 창이 쓴다) |
| 사용자가 process 콤보를 바꿈 | version 콤보를 그 이름의 버전으로 시그널 없이 다시 채우고, **지금 버전 문자열이 그 이름에도 있으면 그것, 없으면 첫 버전**을 고른 뒤 `selectionChanged(새 이름, 그 버전)` 한 번 |
| 사용자가 version 콤보를 바꿈 | `selectionChanged(지금 이름, 새 버전)` 한 번 |

빈 버전 표시: version 콤보 항목 글자는 `(없음)`(모듈 상수, 예 `NO_RELEASE_TEXT = "(없음)"`). **버전은 글자가 아니라 index 로 view 가 들고 있는 목록에서 읽는다.** `currentText()` 로 읽지 마라. 이유: `(없음)` 이 진짜 버전 `""` 이다. itemData 를 쓰려면 PySide6 에서 `""` 가 그대로 돌아오는지 테스트로 확인한다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`(툴바 줄, 문구 규칙), `/docs/ARCHITECTURE.md`(레이어: view 는 위젯을 만들고 의도 시그널을 낸다)
- `src/genviewer/views/device_tab_toolbar.py` 전체: `set_processes`(~158, clear·addItems 가 시그널을 두 번 내는 문제를 막는 주석), `select_process`, `select_process_silently`
- `src/genviewer/controllers/device_tab_toolbar.py`: 옛 API 를 어떻게 쓰는지(이 step 에서는 바꾸지 않는다)
- `tests/gui/conftest.py`, `tests/gui/test_process_list_refresh.py`(옛 `set_processes` 의 시그널 한 번 규칙을 지키는 테스트)

## 작업

### 1. 테스트 먼저

새 `tests/gui/test_toolbar_pairs_view.py`(view 만):
- 빈 view 에 `set_pairs([("sf2p",""),("sf2p","V1"),("sf4u","")])` → process 콤보 `["sf2p","sf4u"]`, version 콤보 `["(없음)","V1"]`, `current_pair() == ("sf2p","")`, `selectionChanged` 한 번 `("sf2p","")`.
- 같은 목록으로 다시 `set_pairs` → 시그널 없음.
- `("sf2p","V1")` 을 고른 뒤, 목록에서 V1 만 빠진 `set_pairs` → `("sf2p","")` 로 바뀌고 시그널 한 번. 이름째 빠지면 첫 쌍. 빈 목록이면 `("", "")` 한 번.
- 사용자가 version 콤보를 바꾸면(`setCurrentIndex` 로 흉내) `("sf2p","V1")` 한 번.
- 지금 `("sf2p","V1")` 에서 process 콤보를 V1 이 있는 이름으로 바꾸면 그 이름의 V1 이, 없는 이름으로 바꾸면 그 이름의 첫 버전이 골라지고 시그널은 한 번이다(중간 쌍으로 두 번 내지 않는다).
- `select_silently("sf4u","")` → True, 시그널 없음, `current_pair()` 바뀜. `select_silently("sf9x","")` → False 이고 두 콤보·`current_pair()` 그대로.
- `select_pair` 는 바뀔 때만 한 번.
- version 콤보 글자가 `(없음)` 이어도 `current_pair()[1] == ""`.
- 옛 API 회귀: `set_processes(["a","b"])` 와 `select_process_silently` 가 지금처럼 동작한다(기존 `test_process_list_refresh.py` 등이 그대로 통과).

수정 전에는 새 API 가 없어 실패해야 한다.

### 2. 수정

- `views/device_tab_toolbar.py`: Version 라벨·콤보, 위 API. 사용자 변경은 콤보의 `currentIndexChanged`(또는 `activated`)를 view 안에서 받아 처리한다. 프로그램이 채우거나 고를 때는 `blockSignals` 로 막고 필요한 한 번만 직접 낸다(지금 `set_processes` 의 방식).
- 옛 API 와 `process_selector` 는 이 step 에서 지우지 않는다. 컨트롤러가 아직 쓴다.

### 3. 변이 검사

- process 콤보 변경 때 version 콤보를 채우며 시그널을 막지 않게 해 "시그널 한 번" 테스트가 실패하는지 본다. 되돌린다.
- `current_pair()` 가 `currentText()` 로 버전을 읽게 해 `(없음)` 테스트가 실패하는지 본다. 되돌린다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_toolbar_pairs_view.py -q   # 새 테스트 통과, 수정 전에는 실패
uv run pytest tests/gui -q
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - view 가 repo·컨트롤러를 모르는가(위젯과 의도 시그널만)?
   - 사용자 동작 한 번에 `selectionChanged` 가 정확히 한 번인가?
   - 옛 API 가 그대로 동작해 기존 GUI 테스트가 모두 통과하는가?
   - 기존 문구·라벨을 바꾸지 않았는가(새로 더한 것은 `Version` 라벨과 `(없음)` 뿐)?
3. 결과에 따라 `phases/19-process-release/index.json` 의 step 7을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "views/device_tab_toolbar: Version 라벨·release_selector(빈 버전 '(없음)', index 로 읽음), selectionChanged(str,str), set_pairs/select_pair/select_silently/current_pair/pairs/releases_of. 옛 API 그대로. RED: <테스트 이름: 단언>. 변이: <결과>. 테스트 파일: tests/gui/test_toolbar_pairs_view.py"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 컨트롤러(`controllers/`)를 고치지 마라. 이유: step 8 의 일이다. 이 step 은 view 계약만 세운다.
- 옛 API(`set_processes`, `select_process`, `select_process_silently`, `process_selector` 시그널)를 지우거나 동작을 바꾸지 마라. 이유: 컨트롤러와 기존 테스트가 아직 쓴다. step 8 이 지운다.
- view 에서 repo 를 부르거나 `question` 등 모달을 띄우지 마라.
- `(없음)` 을 버전 값으로 쓰지 마라(표시용 글자다).
- 기존 테스트를 깨뜨리지 마라.
