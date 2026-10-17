# Step 4: export-format-by-suffix

## 배경 (phase 11 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 평소에는 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 11은 2026-10-17에 `docs/notes/known-issues.md` 를 분류하면서 고치기로 한 GUI 오류 경로 항목을 한 step에 하나씩 다룬다. 버그(K34·K35, K22 일부)와 **사용자가 2026-10-17 승인한 동작 변경**(K3의 GUI 쪽, K21, K16 내보내기 형식, K18)이 섞여 있다. 승인된 step에는 승인 문장을 그대로 적었다. 그 문장 밖으로 넓히지 마라.

phase 0~10과 이 phase의 step 0~3이 끝나 있다. 이 step에 닿는 것:
- phase 7 step 8(`xlsx-literal`): `utils/exporter.write_xlsx` 가 `=` 로 시작하는 문자열을 문자열 셀로 쓴다. 이 step은 exporter를 바꾸지 않는다.

모든 step에 같은 규칙이 적용된다.
1. 승인된 동작 변경도 테스트를 먼저 쓰고, 지금 코드에서 그 테스트가 어떻게 실패하는지(지금 동작)를 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다.
3. 지금 동작이 설명과 다르면 `src/` 를 고치지 않고 `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라.
5. 이 파일의 행 번호는 2026-10-17(phase 6 전) 기준 대략값이다. 이름으로 찾아라.

GUI 테스트 기반(phase 2)의 이름을 그대로 쓴다.
- `dialogs`: 파일 대화상자(`QFileDialog.get*`)와 메뉴는 막혀 있어 부르면 `AssertionError` 다. 저장 경로는 view의 `_ask_export_path` 를 인스턴스 속성으로 monkeypatch 해서 준다.
- `device_tab_ctrl`, `store`, `store.calls_of`

## 이 step의 목적

(**사용자 승인 2026-10-17**, K16 중 내보내기 형식) 승인 문장: "GUI 내보내기 형식을 메뉴 대신 저장 파일 확장자로 정함(CLI 와 같게). 지금은 xlsx 메뉴로 a.csv 를 고르면 xlsx 바이트가 .csv 에 써짐"

정한 규칙(2026-10-17 계획):
- 확장자가 `.csv` 면 CSV, `.xlsx` 면 xlsx 로 쓴다(대소문자 무시).
- **둘 다 아니면 메뉴에서 고른 형식**을 따른다.

CLI(`cli.py` `export`)는 `.xlsx` 면 xlsx, 그 밖은 전부 CSV다. 확장자가 없거나 다른 경우만 이 규칙과 다르다. 그 경우 GUI는 사용자가 메뉴로 고른 형식이 남는 쪽을 택했다(계획).

K16의 다른 절반(Virtuoso 목록 필터의 부분 문자열 일치)은 **사용자가 고치지 않기로 했다**(의도). 건드리지 않는다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/UI_GUIDE.md`("입력과 단축키")
- `src/genviewer/controllers/device_table.py`
  - `export_selected_devices(fmt)` (~454-488): 메뉴의 `fmt`(`"csv"`/`"xlsx"`)로 writer와 알림 제목 `"Save CSV"`/`"Save XLSX"` 를 고른다.
  - 그것을 부르는 컨텍스트 메뉴(~95-101)
- `src/genviewer/views/device_table.py`: `_ask_export_path` (~81-85, 필터 `"CSV Files (*.csv);;Excel Files (*.xlsx)"`)
- `src/genviewer/utils/exporter.py`: `write_csv`, `write_xlsx`
- `src/genviewer/cli.py`: `export` (~254-288, 확장자로 고르는 본보기)

## 승인된 동작 변경

| 메뉴 | 고른 파일 이름 | 지금 | 바뀐 뒤 |
|---|---|---|---|
| xlsx | `a.csv` | xlsx 바이트를 `a.csv` 에 씀, 제목 "Save XLSX" | **CSV** 로 씀, 제목 "Save CSV" |
| csv | `a.xlsx` | CSV 텍스트를 `a.xlsx` 에 씀 | **xlsx** 로 씀, 제목 "Save XLSX" |
| csv | `a.CSV` | CSV | CSV |
| xlsx | `a`(확장자 없음) | xlsx | xlsx(메뉴) |
| csv | `a.txt` | CSV | CSV(메뉴) |

- 알림 본문(`Success!\n - <파일 이름>`)과 로그 줄(`Exported N row(s) to <파일 이름>.`)은 그대로다. 제목은 실제로 쓴 형식을 따른다.
- 파일 이름에 확장자를 덧붙이거나 바꾸지 않는다.

## 작업

### 1. 테스트 먼저 (`tests/gui/test_export_format.py`, 새 파일)

- 준비: `device_tab_ctrl` 에서 sf2p의 device가 보이는 상태로 둔다. `ctrl.device_table.ui._ask_export_path = lambda suggested: str(tmp_path / name)` 로 경로를 준다.
- 동작: `ctrl.device_table.export_selected_devices(fmt)` 를 직접 부른다(메뉴는 막혀 있다).
- 판정: xlsx는 파일이 `b"PK\x03\x04"`(zip)로 시작하는지, CSV는 그렇지 않고 UTF-8로 읽혀 첫 줄에 `CellType` 이 있는지 본다.
- 위 표의 다섯 줄을 parametrize 하고, 알림 제목(`dialogs.shown[-1][1]`)도 단언한다.
- **수정 전에는 앞의 두 줄(xlsx 메뉴 + `.csv`, csv 메뉴 + `.xlsx`)이 실패해야 한다.**
- 회귀: 저장 경로 대화상자를 취소하면(`""`) 파일이 없고 알림도 없다(지금과 같다).

### 2. 수정

- `controllers/device_table.py` `export_selected_devices`: 경로를 받은 뒤 확장자로 형식을 정한다. 둘 다 아니면 `fmt` 를 쓴다. writer와 제목은 정한 형식을 따른다.
- 대화상자 필터 문자열(`views/device_table.py`)과 제안 파일 이름(`f"{process}.{fmt}"`)은 바꾸지 않는다.

### 3. 문서

- `docs/UI_GUIDE.md` "입력과 단축키" 목록에 한 줄을 더한다: `- device 표 내보내기는 고른 파일의 확장자(.csv / .xlsx)로 형식을 정한다. 둘 다 아니면 메뉴에서 고른 형식이다.`

## Acceptance Criteria

```bash
uv run pytest tests/gui/test_export_format.py -q   # 새 테스트 통과 (수정 전에는 확장자가 메뉴와 다른 두 경우가 실패해야 한다)
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - `utils/exporter.py` 와 CLI를 바꾸지 않았는가?
   - Virtuoso 목록 필터(`refresh_devices` 의 `name in r["name"]`)를 건드리지 않았는가(사용자가 의도로 남김)?
   - 테스트가 실제 파일 대화상자를 열지 않는가?
3. 결과에 따라 `phases/11-gui-error-paths/index.json` 의 step 4를 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "export_selected_devices: .csv/.xlsx 확장자로 형식, 둘 다 아니면 메뉴 (사용자 승인 2026-10-17). 지금 동작(RED): <테스트 이름: 단언>. 변이: <…>. tests/gui/test_export_format.py"`
   - 지금 동작이 설명과 다름 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 파일 이름의 확장자를 바꾸거나 덧붙이지 마라. 이유: 승인된 것은 "확장자로 형식을 정한다" 뿐이다.
- Virtuoso 목록 필터를 정확히 일치로 바꾸지 마라. 이유: 사용자가 2026-10-17에 의도로 남기기로 했다.
- `utils/exporter.py`·`cli.py` 를 바꾸지 마라. 이유: CLI 동작은 이미 확장자 기준이고, 이 step의 범위가 아니다.
- 기존 테스트를 깨뜨리지 마라.
