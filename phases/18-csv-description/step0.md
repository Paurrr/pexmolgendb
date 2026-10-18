# Step 0: send-fixed-columns

## 배경 (phase 18 공통)

이 저장소는 평소에 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 18은 예외로 **사용자가 2026-10-17 승인한 기능**이다(known-issues K44). 승인된 동작은 다음과 같다.

> 내보내기(GUI·CLI, CSV·xlsx)는 InstCellName 다음에 Description 컬럼을 쓴다. 불러오기는 Description 컬럼이 있으면 그 값을 device.description 에 넣고, 없으면(옛 CSV) 지금처럼 빈 값이다. Virtuoso로 보내는 payload는 바꾸지 않는다.

지금은 이렇게 된다.
- molgen CSV 형식에 Description 컬럼이 없다(`molgen/genMOLDB_config.il` 의 `pexGenDB_GenDev_Get_Header_Type()`).
- 그래서 `IORepository.import_data` 는 `INSERT INTO device (process_id, name, celltype, updated_by)` 로 새 device를 만들고, description은 DDL 기본값 `''` 이 된다.
- `fetch_export_data` 의 헤더는 `CellType, CdsLibName, InstCellName` + 탭이다.
- 결국 화면에서 적은 description은 내보낸 CSV에 없고, 그 CSV를 다시 불러와도 되살아나지 않는다.

이 phase의 step은 다음 순서로 간다.
- step 0: Virtuoso로 보내는 payload가 고정 컬럼을 **이름**으로 고르게 하고 Description을 빼게 한다. 다음 step이 헤더를 바꿔도 payload가 그대로이도록 계약을 먼저 세운다.
- step 1: 서비스 계층 `io.py` 의 import·export, 가짜 `FakeIORepository`, contract test. DB step이다.
- step 2: GUI 내보내기(`export_selected_devices`)가 화면의 description을 넘긴다.

**선행 조건(이 phase 범위 밖)**: molgen의 `pexGenDB_GenDev_Get_Header_Type()` 에 `'Description "string"` 을 등록해야 한다(`'Status` 와 같은 방식). molgen `CSV_COLUMNS.md` 도 고쳐야 한다. 등록하지 않으면 molgen이 셀마다 `Unknown header type: nil, header: Description, …` warn을 낸다(`molgen/genMOLDB_csv.il` `pexGenDB_GenDev_Convert_One_Value`). 운영 배포 전에 molgen 쪽이 먼저 나가야 한다. gendb 테스트는 molgen 없이 돌므로 이 phase의 실행을 막지는 않는다. **molgen 저장소를 고치지 마라.**

모든 step에 같은 규칙이 적용된다.
1. 기능이라 TDD로 한다. 새 동작을 단언하는 테스트를 먼저 쓰고, 수정 전에 실패하는 것을 본다(RED). 그 테스트 이름과 단언을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다.
3. 고친 뒤 구현을 손으로 망가뜨려 새 테스트가 실패하는지 보고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
4. 이 파일의 행 번호는 2026-10-18(phase 13 직후) 기준 대략값이다. phase 7~13이 같은 파일을 바꿨다. 특히 phase 11 step 3(`send_device_data` 의 `Unsaved Devices` 거부), phase 11 step 4(`export_selected_devices` 의 확장자로 형식 고르기), phase 13(Virtuoso 소켓 소비자)이 바꿨다. 이름으로 찾아라.
   - phase 14~17(구조 제안 P2 Prompts·P4 공개 API·P3 SaveCoordinator·P5 남은 동기 DB 호출을 워커로, `docs/notes/architecture-proposal.md`)이 이 phase보다 먼저 끝났을 수 있다. 대화상자 대역(`FakeDialogs` → Prompts 가짜), private 이름(`_ask_export_path` 등), 내보내기·보내기의 DB 호출 위치(워커)가 바뀌었으면 실제 코드를 따르고 summary에 적는다. 그 구조를 되돌리지 않는다.
5. `config/tab_config.json` 의 키 구조를 바꾸지 않는다. Description은 탭이 아니라 device 컬럼이다(`device.description TEXT NOT NULL DEFAULT ''`, 이미 있다). 스키마는 바꾸지 않는다.
6. 사용자에게 보이는 문구(알림·로그)를 새로 만들거나 바꾸지 않는다.
7. 문서(`README.md` 의 `## CSV 컬럼과 탭`, `docs/PRD.md` 3번, molgen 선행 조건)는 phase 마무리에서 고친다. step에서는 바꾸지 않는다.

GUI 테스트 기반(phase 2)은 다음과 같다. 작업 전에 `tests/gui/conftest.py`·`tests/gui_support/` 를 읽고, 이 파일의 서술과 다르면 실제 코드를 따른다.
- `device_tab_ctrl` 는 가짜에 붙어 이미 접속한 `DeviceTabController` 다. 접속하면 sf2p가 골라진다(nfet_a·nfet_b). 탭은 InstTerm·InstSchParam이고 actor는 `tester` 다.
- `dialogs`(autouse) 의 `shown` 은 `(kind, title, text)` 다. 답하지 않은 모달·파일 대화상자·메뉴는 `AssertionError` 이고 teardown에서 실패한다.
- `store.calls_of(name)` 은 가짜 repo 호출 기록이다. `edit_device_cell(ctrl, row, column, value)` 도 쓴다.
- 고정 대기(`qtbot.wait`)는 쓰지 않는다. `waitUntil` 콜백은 bool을 돌려준다.

## 이 step의 목적

`DeviceTabController.send_device_data` 는 `fetch_export_data` 의 헤더를 **위치로** 나눈다. `for i, h in enumerate(headers): if i <= 2: continue` 로 앞 세 개를 고정 컬럼으로 보고, 나머지는 전부 탭 목록(`'<이름> list("…")`)으로 보낸다. step 1이 헤더 4번째에 `Description` 을 넣으면 payload에 `'Description list("…")` 가 끼어든다. 승인된 동작은 "payload는 바꾸지 않는다" 이다.

고정 컬럼을 **이름**으로 고르게 바꾼다.
- `CellType`·`CdsLibName`·`InstCellName` 은 지금처럼 스칼라로 보낸다.
- `Description` 은 보내지 않는다.
- 나머지 헤더는 지금처럼 헤더 순서대로 탭 목록으로 보낸다.

지금 헤더(Description 없음)로 만든 payload는 바이트까지 그대로여야 한다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ARCHITECTURE.md`(Virtuoso 연동 흐름), `/docs/ADR.md`(ADR-003 tab_config 단일 원본)
- `src/genviewer/controllers/device_tab.py` `send_device_data` (~351-416, `@report("Send Failed")`): `tab_indices`, `celltype_idx`/`cds_idx`/`inst_idx`, `unit_data["tabs"]`, `to_lisp_list_string`, `sendDataRequested.emit(result)`. phase 13 뒤에 자리가 옮겨졌으면 `sendDataRequested` 를 내는 곳을 찾아라.
- `src/genviewer/utils/lisp.py` `to_lisp_list_string`
- `src/genviewer/service/repo/io.py` `fetch_export_data`(헤더를 만드는 곳. 이 step에서는 바꾸지 않는다), `tests/gui_support/fakes.py` `FakeIORepository.fetch_export_data`
- phase 11 step 3이 만든 `tests/gui/test_send_device_data.py`(보내기 테스트의 본보기, `sendDataRequested` 를 받는 방법)

## 작업

### 1. 테스트 먼저

`tests/gui/test_send_device_data.py` 에 더한다. 그 파일이 없으면 `tests/gui/test_send_payload_columns.py` 를 새로 만든다.
- `ctrl.sendDataRequested` 를 리스트에 모으고 `ctrl.send_device_data("all")` 을 부른다. 동기로 끝나므로 돌아온 뒤 바로 단언한다.
- **특성 테스트(지금 헤더)**: payload `P0` 가 `pydata = list(` 로 시작한다. `'CellType "NFET"`·`'CdsLibName "sf2p"`·`'InstCellName "nfet_a"`·`'InstTerm list(` 를 담고 `'Description` 은 없다. 수정 전후 모두 통과한다.
- **Description이 4번째(RED)**: `ctrl.io_repo.fetch_export_data` 를 원래 함수를 감싼 것으로 바꾼다(인스턴스 속성, monkeypatch). 헤더 3번 자리에 `"Description"` 을, 각 행 3번 자리에 `"ESD 용"` 을 끼운다. 그래도 payload가 감싸지 않은 호출의 `P0` 와 **같다**. **수정 전에는 `'Description list("ESD 용")` 이 끼어 달라서 실패해야 한다.**
- **Description이 맨 뒤**: 같은 방식으로 헤더 끝에 넣어도 `P0` 와 같다(위치가 아니라 이름으로 고르는지 확인).
- **고정 컬럼 순서가 바뀌어도**: 감싼 헤더에서 `CdsLibName` 과 `InstCellName` 자리를 바꾸고 행도 같이 바꾸면 스칼라 값이 이름에 맞게 간다(`'InstCellName "nfet_a"`). 지금도 `headers.index(...)` 로 찾으므로 수정 전에도 통과할 수 있다(회귀 그물).

### 2. 수정

- `send_device_data` 에서 고정 컬럼을 이름 집합으로 고른다. 예: 모듈 상수 `_FIXED_COLUMNS = ("CellType", "CdsLibName", "InstCellName")`, `_NOT_SENT = ("Description",)`. 이름과 모양은 재량이다.
- 옆에 한두 줄로 이유를 적는다. 예: "Description 은 CSV 에만 쓴다(phase 18 승인). Virtuoso payload 는 그대로다".
- `unit_data` 의 키·순서, `to_lisp_list_string`, `pydata = list(` 형식은 바꾸지 않는다.

### 3. 변이 검사

`if i <= 2` 위치 판단으로 손으로 되돌려 "Description이 4번째" 테스트가 실패하는지 본다. 다시 고친다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_send_device_data.py -q   # (또는 새로 만든 파일) 새 테스트 통과, 수정 전에는 'Description이 4번째' 가 실패해야 한다
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 지금 헤더로 만든 payload가 바이트까지 그대로인가(특성 테스트)?
   - `fetch_export_data`(진짜·가짜)와 `to_lisp_list_string` 을 바꾸지 않았는가?
   - CLAUDE.md CRITICAL 규칙(GUI 스레드, 문구)을 지켰는가?
3. 결과에 따라 `phases/18-csv-description/index.json` 의 step 0을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "send_device_data 가 고정 컬럼을 이름(CellType/CdsLibName/InstCellName)으로 고르고 Description 은 payload 에서 뺌(지금 헤더 payload 불변). RED: <테스트 이름: 단언>. 변이: <결과>. 테스트 파일: <경로>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `fetch_export_data`(`service/repo/io.py`, `tests/gui_support/fakes.py`)의 헤더를 이 step에서 바꾸지 마라. 이유: step 1의 일이다. 이 step은 그 변경이 payload에 새지 않게 막는 계약만 세운다.
- Description을 payload에 넣지 마라(스칼라로도 안 된다). 이유: 승인된 동작이 "payload는 바꾸지 않는다" 이다. molgen의 pydata 변환(`pexGenDB_GenDev_Convert_PyData_to_inputVal`)도 등록 안 된 헤더에 warn을 낸다.
- `to_lisp_list_string`·Virtuoso 소켓 코드(`net/`)를 바꾸지 마라. 이유: 범위 밖이고 phase 13이 정리했다.
- phase 11 step 3의 `Unsaved Devices` 거부를 바꾸지 마라.
- 기존 테스트를 깨뜨리지 마라.
