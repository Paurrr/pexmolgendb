# Step 2: gui-export-description

## 배경 (phase 18 공통)

이 저장소는 평소에 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 18은 예외로 **사용자가 2026-10-17 승인한 기능**이다(known-issues K44). 승인된 동작은 다음과 같다.

> 내보내기(GUI·CLI, CSV·xlsx)는 InstCellName 다음에 Description 컬럼을 쓴다. 불러오기는 Description 컬럼이 있으면 그 값을 device.description 에 넣고, 없으면(옛 CSV) 지금처럼 빈 값이다. Virtuoso로 보내는 payload는 바꾸지 않는다.

이 phase의 step은 다음 순서로 간다.
- step 0: Virtuoso payload가 고정 컬럼을 이름으로 고르고 Description을 뺀다(끝났다).
- step 1: `io.py`·가짜·contract test가 Description을 왕복시킨다(끝났다). `fetch_export_data` 는 InstCellName 다음에 Description 헤더를 늘 쓴다. 값은 **넘겨받은 device_info의 `description`** 이다.
- step 2(이 step): GUI 내보내기가 device_info에 화면의 description을 넣는다.

**선행 조건(이 phase 범위 밖)**: molgen의 `pexGenDB_GenDev_Get_Header_Type()` 에 `'Description "string"` 을 등록해야 한다. 운영 배포 전에 molgen 쪽이 먼저 나가야 한다. **molgen 저장소를 고치지 마라.**

모든 step에 같은 규칙이 적용된다.
1. 기능이라 TDD로 한다. 새 동작을 단언하는 테스트를 먼저 쓰고, 수정 전에 실패하는 것을 본다(RED). 그 테스트 이름과 단언을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다.
3. 고친 뒤 구현을 손으로 망가뜨려 새 테스트가 실패하는지 보고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라.
4. 이 파일의 행 번호는 2026-10-18(phase 13 직후) 기준 대략값이다. phase 11 step 4가 `export_selected_devices` 를 바꿨다(형식을 저장 파일 확장자로 고른다). 이름으로 찾아라.
   - phase 14~17(구조 제안 P2 Prompts·P4 공개 API·P3 SaveCoordinator·P5 남은 동기 DB 호출을 워커로, `docs/notes/architecture-proposal.md`)이 이 phase보다 먼저 끝났을 수 있다. 대화상자 대역(`FakeDialogs` → Prompts 가짜), private 이름(`_ask_export_path` 등), 내보내기·보내기의 DB 호출 위치(워커)가 바뀌었으면 실제 코드를 따르고 summary에 적는다. 그 구조를 되돌리지 않는다.
5. `config/tab_config.json` 의 키 구조와 스키마를 바꾸지 않는다.
6. 사용자에게 보이는 문구(알림 "Save CSV"/"Save XLSX", 로그)를 새로 만들거나 바꾸지 않는다.
7. 문서는 phase 마무리에서 고친다. step에서는 바꾸지 않는다.
8. 이 step은 repo 의미를 바꾸지 않는다. DB 테스트가 필요 없다(`GENDB_TEST_PG_DSN` 이 없어도 blocked가 아니다).

GUI 테스트 기반(phase 2)은 다음과 같다. 작업 전에 `tests/gui/conftest.py`·`tests/gui_support/` 를 읽고, 이 파일의 서술과 다르면 실제 코드를 따른다.
- `device_tab_ctrl` 는 가짜에 붙어 이미 접속한 `DeviceTabController` 다. 접속하면 sf2p가 골라진다(nfet_a·nfet_b, description `""`).
- `dialogs`(autouse) 의 `shown` 은 `(kind, title, text)` 다. 파일 대화상자는 막혀 있다. 그래서 저장 경로는 `ctrl.ui.device_table_view._ask_export_path` 를 인스턴스 속성으로 바꿔(monkeypatch) tmp 경로를 돌려준다. phase 11 step 4의 `tests/gui/test_export_format.py` 가 쓰는 방법을 따른다.
- `edit_device_cell(ctrl, row, "description", value)` 로 화면 값을 바꾼다. 저장하지 않으면 dirty로 남는다.
- 고정 대기(`qtbot.wait`)는 쓰지 않는다.

## 이 step의 목적

`DeviceTableController.export_selected_devices` 가 만드는 `device_info` 에는 `id`·`process_id`·`process_name`·`name`·`celltype` 만 있다. step 1 뒤로 내보낸 파일에 Description 헤더는 있지만 값이 늘 빈다. `"description": d.get("description")` 을 더해 화면의 값을 넘긴다. name·celltype과 같은 의미이고, 저장하지 않은 편집이라면 그 편집 값이다. 지금 내보내기가 화면의 name·celltype을 그대로 쓰는 것과 같다.

| 경우 | 지금(step 1 뒤) | 바뀐 뒤 |
|---|---|---|
| 저장된 description이 있는 device를 CSV로 내보냄 | Description 열이 빈다 | 그 값 |
| description을 화면에서 고치고 저장하지 않은 채 내보냄 | 빈다 | 화면 값(name·celltype과 같다) |
| xlsx로 내보냄 | 빈다 | 그 값 |
| 고른 행이 없음 | 모든 행(`get_selected_devices()` 의 기본 fallback) | 지금과 같다 |
| 내보내기 형식 고르기, 알림, 로그 | phase 11 step 4 그대로 | 지금과 같다 |

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`("입력과 단축키", 내보내기)
- `src/genviewer/controllers/device_table.py`: `export_selected_devices`(~516-555, `device_info` 를 만드는 곳), `get_selected_devices`, `refresh_devices`(모델 device dict에 `description` 이 있다)
- `src/genviewer/models/device_table.py`: `_columns`(`name`, `celltype`, `description`), `get_device`, `get_devices`
- `src/genviewer/views/device_table.py`: `_ask_export_path`
- `src/genviewer/utils/exporter.py`: `write_csv`(utf-8), `write_xlsx`
- `src/genviewer/service/repo/io.py` `fetch_export_data`, `tests/gui_support/fakes.py` `FakeIORepository.fetch_export_data`(step 1 결과. 이 step에서는 바꾸지 않는다)
- `tests/gui/test_export_format.py`(phase 11 step 4. 내보내기 GUI 테스트의 본보기)

## 작업

### 1. 테스트 먼저

`tests/gui/test_export_format.py` 에 더하거나 새 파일 `tests/gui/test_export_description.py` 를 만든다.
- 준비: `store.touch_device(nfet_a, actor="kim", description="ESD 용")` 처럼 저장된 description을 만들고 `ctrl.device_table.refresh_devices()` 로 화면에 읽는다. `touch_device` 가 description을 받는지 `_TOUCHABLE` 로 확인한다.
- **CSV(RED)**: `_ask_export_path` 를 `tmp_path / "out.csv"` 로 바꾸고 `ctrl.device_table.export_selected_devices("csv")` 를 부른다. 파일을 `csv` 모듈(`encoding="utf-8"`)로 읽어 헤더 4번째가 `Description` 이고 nfet_a 행 값이 `"ESD 용"` 인지 본다. **수정 전에는 값이 `""` 라 실패해야 한다.**
- **저장 안 한 편집**: `edit_device_cell(ctrl, 1, "description", "화면 값")` 뒤 내보내면 nfet_b 행이 `"화면 값"` 이다.
- **xlsx**: `out.xlsx` 로 내보내고 openpyxl로 읽어 같은 값을 본다.
- 알림은 지금처럼 `("info", "Save CSV"/"Save XLSX", …)` 하나뿐이다(문구 불변).

### 2. 수정

- `export_selected_devices` 의 `device_info` 에 `"description": d.get("description")` 을 더한다.
- 다른 것은 바꾸지 않는다.

### 3. 변이 검사

추가한 키를 손으로 지워 CSV 테스트가 실패하는지 본다. 다시 고친다.

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_export_format.py -q   # (또는 새로 만든 파일) 새 테스트 통과, 수정 전에는 CSV 값 단언이 실패해야 한다
uv run pytest tests/gui/test_fake_repo_contract.py tests/gui/test_send_device_data.py -q   # step 0·1 테스트 그대로 (step 0 이 다른 파일을 만들었으면 그 파일)
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - 내보내기가 GUI 스레드에서 DB를 새로 기다리지 않는가? 이 step은 dict 키 하나만 더했는가?
   - 알림·로그 문구가 그대로인가?
   - Virtuoso payload(`send_device_data`)를 건드리지 않았는가?
3. 결과에 따라 `phases/18-csv-description/index.json` 의 step 2를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "export_selected_devices 가 device_info 에 화면의 description 을 넘김(name·celltype 과 같은 의미). RED: <테스트 이름: 단언>. 변이: <결과>. 테스트 파일: <경로>. 문서(README CSV 절, PRD 3번, molgen 선행 조건)는 phase 마무리"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 내보내기가 description을 DB에서 다시 읽게 하지 마라. 이유: name·celltype은 화면 값을 쓴다. 한 행 안에서 섞이면 같은 파일에 서로 다른 시점의 값이 들어간다.
- `send_device_data` 의 `device_info` 에 description을 넣지 마라. 이유: payload에 쓰지 않는다(step 0). 넣어도 빠지지만 괜히 넣을 이유가 없다.
- 내보내기 형식 고르기(phase 11 step 4)·알림 문구를 바꾸지 마라.
- `io.py`·가짜 repo를 바꾸지 마라. 이유: step 1에서 끝났다.
- 기존 테스트를 깨뜨리지 마라.
