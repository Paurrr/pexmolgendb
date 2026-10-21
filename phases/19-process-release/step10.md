# Step 10: load-csv-release

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
- step 9 `add-clone`: 추가 창(버전, 복제 원본) (GUI)
- step 10 `load-csv-release`: GUI Load CSV 의 버전, 내보내기 파일 이름 (GUI) ← 이 step

모든 step에 같은 규칙이 적용된다.
1. 기능이라 TDD로 한다. 새 동작을 단언하는 테스트를 먼저 쓰고, 수정 전에 실패하는 것을 본다(RED). 그 테스트 이름과 단언을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다. `posix_only` 테스트만으로는 안 된다.
3. 고친 뒤 구현을 손으로 망가뜨려 새 테스트가 실패하는지 보고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
4. 이 파일의 행 번호는 2026-10-21(phase 18 직후) 기준 대략값이다. 이름으로 찾아라. phase 14~17(구조 제안 P2 Prompts·P4 공개 API·P3 SaveCoordinator·P5 남은 동기 DB 호출을 워커로, `docs/notes/architecture-proposal.md`)이 이 phase보다 먼저 끝났을 수 있다. 대화상자 대역, private 이름(`_ask_export_path` 등), DB 호출 위치가 바뀌었으면 실제 코드를 따르고 summary에 적는다. 그 구조를 되돌리지 않는다.
5. `config/tab_config.json` 과 device·탭 테이블의 컬럼을 바꾸지 않는다. `device.version`(낙관적 잠금)의 이름·의미를 바꾸지 않는다.
6. 사용자에게 보이는 새 문구는 그 step 파일이 적은 것만 만든다. 빈 버전일 때 기존 문구는 그대로다. 대화상자 제목은 영어, 본문·CLI 출력·주석은 한국어(CLAUDE.md).
7. 문서(`README.md`, `docs/*.md`, `CLAUDE.md`)는 phase 마무리에서 고친다. step에서는 바꾸지 않는다.
8. molgen 저장소(`../molgen`)를 고치지 마라.

## GUI 테스트 기반

작업 전에 `tests/gui/conftest.py`·`tests/gui_support/` 를 읽고, 이 파일의 서술과 다르면 실제 코드를 따른다.
- `store` 시드: sf2p(nfet_a·nfet_b), sf4u(pfet_a), 버전은 모두 `''`. `seeded_store` 는 바꾸지 마라.
- `device_tab_ctrl` 는 가짜에 붙어 이미 접속한 `DeviceTabController` 다(첫 쌍 `("sf2p","")`).
- `dialogs`(autouse) 는 `QFileDialog.*`·`QInputDialog.*` 를 막는다(부르면 `AssertionError`). 그래서 파일·버전 입력은 view 의 stub 가능한 메서드(`open_file` 을 부르는 자리, 새 `_ask_release`, 내보내기의 `_ask_export_path`) 뒤에 두고 테스트가 monkeypatch 한다. `_ask_release` 자체를 시험할 때는 그 테스트 안에서 `QInputDialog.getItem` 을 monkeypatch 한다(fixture 뒤에 바꾼 것이 이긴다).
- 일어난 일은 `store.calls_of("import_data")`. `run_blocking` 은 워커에서 돈다. 고정 대기(`qtbot.wait`)는 쓰지 않는다.
- `utils/exporter.py` 는 Qt 없는 모듈이다(`tests/test_boundaries.py` 의 `QT_FREE_MODULES` 에 이미 있다). PySide6 를 import 하지 마라.

## 선행 step

- step 5: `IORepository.import_data(path, *, release="", actor="")`(가짜도 같다).
- step 7·8: 툴바 view `pairs()`·`current_pair()`, `DeviceTableController.current_release`.
- `phases/19-process-release/index.json` 의 step 0~9 summary 를 읽어라.

## 이 step의 목적

GUI 에서 CSV 를 불러올 때 버전을 정하고, 내보내기 파일 이름 기본값이 molgen 규칙을 따른다.

### Load CSV

| 곳 | 바뀐 뒤 |
|---|---|
| `views/device_tab.py` `loadCsvRequested` | `Signal(str, str)`(경로, 버전) |
| `DeviceTab._ask_load_csv` | 지금처럼 파일을 고른 뒤(취소면 끝) `self._ask_release()` 로 버전을 묻는다. None(취소)이면 아무것도 내지 않는다. 아니면 `loadCsvRequested.emit(path, release)` |
| `DeviceTab._ask_release() -> str \| None` (새) | `QInputDialog.getItem(self, "Load CSV", "불러올 버전 (비우면 버전 없음):", items, current, editable=True)`. `items` 는 툴바 view 의 쌍에서 모은 **서로 다른 버전**(빈 버전은 `(없음)`, 맨 앞), `current` 는 지금 쌍의 버전 자리. 취소면 None. 고른·친 글자는 앞뒤 공백을 지우고 `(없음)` 이나 빈 글자면 `""` |
| `DeviceTabController.on_load_csv_requested(path, release="")` | `run_blocking(lambda: io_repo.import_data(path, release=release, actor=…))`. Refresh 질문, 끝난 뒤 `refresh_processes()`·`refresh_devices()`, 알림 문구는 **그대로**다. 로그 줄만 버전이 있으면 `f"Imported CSV: {path} (version {release}, device {created}개 추가)."`, 없으면 지금 그대로 |
| 지금 쌍 | 불러오기 뒤에도 그대로다(`set_pairs` 가 지금 쌍을 지킨다). 다른 버전으로 불러왔으면 사용자가 콤보로 옮겨 본다(자동으로 옮기지 않는다) |

### 내보내기 파일 이름

`utils/exporter.py` 에 `export_file_name(process: str, release: str, fmt: str) -> str` 를 더한다. molgen `pexGenDB_GenDev_GetMockInfo`(`../molgen/genMOLDB_gui.il:106-123`)가 찾는 이름 `<proc>_<cid>-<ver 점 제거>.csv` 와 맞춘다. molgen 은 작업 디렉터리 `<proc>/<cid>-<ver>` 의 `<cid>-<ver>` 를 `-` 로 나눠(빈 조각은 버림) 앞 두 조각을 쓰고 `<ver>` 의 점을 지운다.

| release | 결과 (`fmt="csv"`, process `sf2p`) |
|---|---|
| `""` | `sf2p.csv` (지금과 같다) |
| `S00-V1.0.0.0` | `sf2p_S00-V1000.csv` |
| `S00-V1.0-beta` | `sf2p_S00-V10.csv` (molgen 처럼 앞 두 조각) |
| `V1.2` (조각이 하나) | `sf2p_V12.csv` |
| 경로에 못 쓰는 글자(`\ / : * ? " < > \|`)가 든 버전 | 그 글자를 `_` 로 바꾼다(버전 부분만) |

`DeviceTableController.export_selected_devices` 의 제안 이름 `f"{(self.current_process or 'process')}.{fmt}"` 를 `export_file_name(self.current_process or "process", self.current_release, fmt)` 로 바꾼다. 내보내기 내용(`fetch_export_data`)·형식 고르기(확장자)는 그대로다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ARCHITECTURE.md`(CSV 절, 스레딩), `/docs/ADR.md`(ADR-006 CSV 누적, ADR-017, ADR-004 phase 10 보강 K36: 불러오기 전 Refresh 질문)
- `src/genviewer/views/device_tab.py`: `loadCsvRequested`(~69), `device_tab_toolbar_view`(~73), `_ask_load_csv`(~140)
- `src/genviewer/controllers/device_tab.py`: `on_load_csv_requested`(~422), `__init__` 의 `loadCsvRequested` 연결
- `src/genviewer/controllers/main_window.py`: Load CSV 메뉴(`_ask_load_csv` 에 연결, 바꾸지 않는다)
- `src/genviewer/controllers/device_table.py`: `export_selected_devices`(~515-555)
- `src/genviewer/views/device_table.py`: `_ask_export_path`
- `src/genviewer/utils/exporter.py`
- `../molgen/genMOLDB_gui.il` 106-123(읽기만)
- `tests/gui/test_export_format.py`(`_ask_export_path` stub 방식, `sf2p.{fmt}` 단언 ~56), `tests/gui/test_process_list_refresh.py`·`tests/gui/test_reload_guard.py`(`on_load_csv_requested(path)` 직접 호출), `tests/test_export.py`

## 작업

### 1. 테스트 먼저

접속 없이(`tests/test_export.py` 또는 새 파일):
- 위 표의 모든 줄을 단언한다(`xlsx` 하나 포함).

GUI:
- `DeviceTab` 의 `open_file` 자리를 stub 해 경로를 주고 `_ask_release` 를 `lambda: "V1"` 로 바꾼 뒤 `_ask_load_csv()` → `store.calls_of("import_data")` 의 마지막 기록에 `release == "V1"`. `store` 에 `("sf2p","V1")` 이 생기고 지금 쌍은 `("sf2p","")` 그대로다(RED).
- `_ask_release` 가 None 이면 `import_data` 가 불리지 않는다.
- `_ask_release` 자체: `QInputDialog.getItem` 을 monkeypatch 해 받은 `items`·`current` 를 기록한다. 툴바에 `("sf2p","")`,`("sf2p","V1")`,`("sf4u","V2")` 가 있고 지금 쌍이 `("sf2p","V1")` 이면 `items == ["(없음)","V1","V2"]`, current 가 `V1` 자리. `("(없음)", True)` 를 돌려주면 `""`, `("  V3 ", True)` 면 `"V3"`, `(…, False)` 면 None.
- 내보내기: 지금 쌍이 `("sf2p","S00-V1.0.0.0")` 일 때 `_ask_export_path` 가 받은 제안 이름이 `sf2p_S00-V1000.csv`. 빈 버전이면 지금처럼 `sf2p.csv`(기존 테스트).
- 기존 `on_load_csv_requested(path)` 직접 호출 테스트는 그대로 통과한다(기본값 `""`).

수정 전에는 새 테스트가 실패해야 한다.

### 2. 수정

위 명세대로.

### 3. 변이 검사

- `on_load_csv_requested` 가 `release` 를 넘기지 않게 해 Load CSV 테스트가 실패하는지 본다. 되돌린다.
- `export_file_name` 이 점을 지우지 않게 해 표 테스트가 실패하는지 본다. 되돌린다.

## Acceptance Criteria

```bash
uv run pytest tests/test_export.py tests/test_boundaries.py tests/gui/test_export_format.py tests/gui/test_process_list_refresh.py tests/gui/test_reload_guard.py -q
uv run pytest tests/gui -q
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - CSV 내용·헤더가 그대로인가? 빈 버전의 파일 이름 제안과 알림 문구가 그대로인가?
   - 불러오기가 `run_blocking` 으로 돌고, 버전 묻기는 GUI 스레드에서 DB 호출 없이 끝나는가(목록은 툴바가 이미 들고 있다)?
   - `utils/exporter.py` 가 Qt 없이 남았는가?
3. 결과에 따라 `phases/19-process-release/index.json` 의 step 10을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "Load CSV: DeviceTab._ask_release(getItem 편집 가능, '(없음)'→'', 취소 None) → loadCsvRequested(path, release) → on_load_csv_requested(path, release='') → import_data(release=). utils/exporter.export_file_name(process, release, fmt) molgen 규칙, 내보내기 제안 이름에 사용. RED: <테스트 이름: 단언>. 변이: <결과>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- CSV 에 버전 컬럼을 쓰거나 파일 이름에서 버전을 읽지 마라. 이유: 승인된 결정은 "CSV 형식 그대로, 버전은 불러올 때 지정" 이다.
- 불러온 뒤 그 버전으로 자동으로 옮기지 마라. 이유: 자동으로 화면을 바꾸지 않는다(편집 중 내용이 말없이 사라지면 안 된다, CLAUDE.md).
- `on_load_csv_requested` 의 알림 문구와 Refresh 질문을 바꾸지 마라.
- `utils/exporter.py` 에서 PySide6 를 import 하지 마라.
- 기존 테스트를 깨뜨리지 마라.
