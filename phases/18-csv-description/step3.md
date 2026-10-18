# Step 3: csv-molgen-safe

## 배경 (phase 18 공통)

이 저장소는 평소에 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 18은 예외로 **사용자가 2026-10-17 승인한 기능**이다(known-issues K44). 승인된 동작은 다음과 같다.

> 내보내기(GUI·CLI, CSV·xlsx)는 InstCellName 다음에 Description 컬럼을 쓴다. 불러오기는 Description 컬럼이 있으면 그 값을 device.description 에 넣고, 없으면(옛 CSV) 지금처럼 빈 값이다. Virtuoso로 보내는 payload는 바꾸지 않는다.
>
> 사용자 승인 2026-10-18: CSV 내보내기(GUI·CLI)는 Description 값의 쉼표(`,`)를 `;` 로, 줄바꿈(`\r\n`·`\n`·`\r`)을 공백으로 바꿔 쓴다. molgen CSV 로더(`genMOLDB_csv.il` 의 `pexGenDB_GenDev_Load_CSV_File`)가 따옴표를 모르고 `,` 로만 칸을 나눠서, 쉼표가 든 설명은 그 행의 뒤 컬럼(InstTerm 등)을 밀고 줄바꿈은 행을 가른다. xlsx·DB 값·불러오기는 그대로다. step 3이 한다.

이 phase의 step은 다음 순서로 간다.
- step 0: Virtuoso payload가 고정 컬럼을 이름으로 고르고 Description을 뺀다(끝났다).
- step 1: `io.py`·가짜·contract test가 Description을 왕복시킨다(끝났다). `fetch_export_data` 는 InstCellName 다음에 Description 헤더를 늘 쓴다. 왕복 테스트의 description에는 쉼표·줄바꿈이 없다.
- step 2: GUI 내보내기가 device_info에 화면의 description을 넣는다(끝났다).
- step 3(이 step): CSV 쓰기(`utils/exporter.write_csv`)가 Description 값의 쉼표·줄바꿈을 바꿔 쓴다.

**선행 조건(끝났다)**: molgen의 `pexGenDB_GenDev_Get_Header_Type()` 에 `'Description "string"` 을 등록했다(molgen 커밋 `c7da3a0`, 2026-10-18, `CSV_COLUMNS.md` 9절 포함). 운영 배포는 molgen이 먼저 나가야 한다. gendb 테스트는 molgen 없이 돈다. **molgen 저장소를 고치지 마라.**

모든 step에 같은 규칙이 적용된다.
1. 기능이라 TDD로 한다. 새 동작을 단언하는 테스트를 먼저 쓰고, 수정 전에 실패하는 것을 본다(RED). 그 테스트 이름과 단언을 summary에 적는다.
2. RED는 **Windows 개발 PC에서** 보여야 한다.
3. 고친 뒤 구현을 손으로 망가뜨려 새 테스트가 실패하는지 보고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
4. 이 파일의 행 번호는 2026-10-18(phase 13 직후) 기준 대략값이다. 이름으로 찾아라.
   - phase 14~17(구조 제안 P2 Prompts·P4 공개 API·P3 SaveCoordinator·P5 남은 동기 DB 호출을 워커로, `docs/notes/architecture-proposal.md`)이 이 phase보다 먼저 끝났을 수 있다. 대화상자 대역, private 이름(`_ask_export_path` 등), 내보내기의 DB 호출 위치(워커)가 바뀌었으면 실제 코드를 따르고 summary에 적는다. 그 구조를 되돌리지 않는다.
5. `config/tab_config.json` 의 키 구조와 스키마를 바꾸지 않는다.
6. 사용자에게 보이는 문구(알림 "Save CSV"/"Save XLSX", 로그, CLI 출력)를 새로 만들거나 바꾸지 않는다.
7. 문서(`README.md` 의 `## CSV 컬럼과 탭`, `docs/PRD.md` 3번, `docs/ADR.md`, molgen 선행 조건)는 phase 마무리에서 고친다. step에서는 바꾸지 않는다.
8. 이 step은 SQL과 repo 의미를 바꾸지 않는다. DB 테스트가 필요 없다(`GENDB_TEST_PG_DSN` 이 없어도 blocked가 아니다). 있으면 `-rs` 로 전체를 돌려 summary에 적는다.

GUI 테스트 기반(phase 2)은 다음과 같다. 작업 전에 `tests/gui/conftest.py`·`tests/gui_support/` 를 읽고, 이 파일의 서술과 다르면 실제 코드를 따른다.
- `device_tab_ctrl` 는 가짜에 붙어 이미 접속한 `DeviceTabController` 다. 접속하면 sf2p가 골라진다(nfet_a·nfet_b).
- `dialogs`(autouse) 의 `shown` 은 `(kind, title, text)` 다. 파일 대화상자는 막혀 있어서 저장 경로는 `ctrl.device_table.ui._ask_export_path` 를 인스턴스 속성으로 바꿔 tmp 경로를 돌려준다(`tests/gui/test_export_format.py` 의 `ask_path`).
- 저장된 description은 `store.touch_device(<device>, actor="kim", description=…)` 뒤 `ctrl.device_table.refresh_devices()` 로 화면에 읽는다(step 2가 쓴 방법).
- 고정 대기(`qtbot.wait`)는 쓰지 않는다.

## 이 step의 목적

molgen은 CSV 한 줄을 `,` 로만 나누고 따옴표를 모른다. 지금 gendb의 `write_csv` 는 `csv.writer` 기본값이라 쉼표가 든 값을 `"ESD 용, 2단"` 처럼 따옴표로 감싸 쓰고, 줄바꿈이 든 값은 따옴표 안에 줄바꿈을 그대로 쓴다. molgen 쪽에서는 앞의 것이 그 행의 뒤 컬럼을 한 칸씩 밀고(경고 없이 엉뚱한 파라미터로 생성될 수 있다), 뒤의 것이 행을 둘로 가른다. molgen CSV 형식은 칸 안에 쉼표를 허용하지 않는다(`../molgen/CSV_COLUMNS.md` 0절·9절). 다른 컬럼은 molgen 문법을 따르므로 쉼표가 없고, 자유 문장인 것은 Description뿐이다.

| 경우 | 지금(step 2 뒤) | 바뀐 뒤 |
|---|---|---|
| CSV, Description에 쉼표 | `"ESD 용, 2단"`(따옴표) | `ESD 용; 2단`. 그 줄을 `,` 로 나누면 헤더 수와 같다 |
| CSV, Description에 줄바꿈(`\r\n`·`\n`·`\r`) | 따옴표 안의 줄바꿈 | 줄바꿈 하나마다 공백 하나. 파일의 줄 수 = 행 수 + 1 |
| CSV, 다른 컬럼 | 그대로 | 그대로 |
| CSV, Description 헤더가 없음(`cli.py` 의 `log --out`) | 그대로 | 그대로 |
| xlsx | 원문 | 원문(그대로) |
| DB의 description, 화면 값 | | 바뀌지 않는다. 바꾸는 것은 파일에 쓰는 글자뿐이다 |
| 불러오기(`import_data`) | 쉼표를 그대로 저장 | 그대로 |
| 쉼표 든 description을 CSV로 내보낸 뒤 다시 불러오기 | | `;` 로 돌아온다(승인된 손실) |
| 따옴표(`"`) | csv 모듈이 감싸고 두 번 쓴다 | 그대로. 쉼표·줄바꿈이 없으면 molgen에서 칸이 밀리지 않는다 |

## 읽어야 할 파일

- `/CLAUDE.md`(파일 I/O `encoding="utf-8"`), `/docs/ARCHITECTURE.md`(`utils/exporter`, CSV 흐름)
- `src/genviewer/utils/exporter.py` — `write_csv`, `write_xlsx`(phase 7 step 8의 `=` 리터럴 처리와 그 주석 "CSV 는 molgen 이 원문을 읽으므로 손대지 않는다")
- `write_csv` 를 부르는 곳: `src/genviewer/controllers/device_table.py` `export_selected_devices`, `src/genviewer/cli.py` `export`(device CSV)와 `log --out`(이력 CSV, Description 없음)
- `src/genviewer/service/repo/io.py` `fetch_export_data`(step 1 결과, 헤더 이름 `"Description"`)
- `tests/test_export.py`(Qt 없는 exporter 테스트의 본보기), `tests/gui/test_export_format.py`, step 2가 만든 GUI 내보내기 테스트(`tests/gui/test_export_description.py` 이거나 `test_export_format.py` 에 더한 것)
- `../molgen/genMOLDB_csv.il` `pexGenDB_GenDev_Load_CSV_File`(읽기만 한다. `parseString(line ",")` 로 나눈다)

## 작업

### 1. 테스트 먼저

`tests/test_export.py` 에 더한다(Qt 없음). 헤더는 `["CellType", "CdsLibName", "InstCellName", "Description", "InstTerm"]` 처럼 Description이 중간에 있는 것을 쓴다.
- **쉼표·줄바꿈(RED)**: Description이 `"ESD 용, 2단\r\n둘째 줄\n셋째"` 인 행을 `write_csv` 로 쓴다. 파일을 `encoding="utf-8"` 로 읽어
  - 줄 수가 2다(헤더 + 행 하나, `splitlines()`),
  - 행 줄을 `line.split(",")` 로 나누면(molgen과 같은 방식) 5칸이고 마지막 칸이 InstTerm 값이다,
  - `csv.reader` 로 읽은 Description이 `"ESD 용; 2단 둘째 줄 셋째"` 이고 다른 칸은 원문이다.
  - **수정 전에는 split 칸 수와 줄 수 단언이 실패해야 한다.**
- **다른 컬럼·다른 CSV는 그대로**: 같은 파일의 다른 컬럼에 쉼표가 있으면 csv로 읽은 값이 원문이다. Description 헤더가 없는 CSV(예 `["at", "summary"]`)의 쉼표 값도 원문이다. 수정 전에도 통과한다(특성).
- **xlsx는 원문**: 같은 행을 `write_xlsx` 로 쓰면 그 셀 값이 원문 그대로다. 수정 전에도 통과한다.
- **넘겨받은 rows를 고치지 않는다**: `write_csv` 뒤에도 넘긴 rows가 원문이다. 이유: 호출자가 같은 rows로 다른 형식을 쓸 수 있다.

GUI 경로 하나(step 2가 만든 GUI 내보내기 테스트 파일에 더한다): nfet_a의 저장된 description을 `"ESD 용, 2단"` 으로 두고 `export_selected_devices("csv")` 로 내보내면 csv로 읽은 값이 `"ESD 용; 2단"` 이고, nfet_a 줄을 `split(",")` 로 나눈 칸 수가 헤더 수와 같다. 같은 device를 xlsx로 내보내면 `"ESD 용, 2단"` 이다. 알림은 지금처럼 하나다. **수정 전에는 CSV 단언이 실패해야 한다.**

### 2. 수정

```python
# utils/exporter.py
def write_csv(path: str, headers: list[str], rows: list[list[str]]) -> None: ...   # 시그니처 그대로
```

- 헤더가 정확히 `"Description"` 인 열의 **문자열** 값만 바꿔 쓴다. 줄바꿈(`\r\n` 을 하나로, 그다음 `\r`, `\n`)은 공백 하나로, `,` 는 `;` 로 바꾼다. 그 밖의 값과 열은 그대로다.
- 넘겨받은 `rows` 를 제자리에서 고치지 마라. 쓸 때 바꾼 사본을 쓴다.
- `csv.writer` 의 방언(quoting, lineterminator)은 바꾸지 않는다.
- `write_xlsx` 의 주석 "CSV 는 molgen 이 원문을 읽으므로 손대지 않는다" 를 이 예외에 맞게 고친다(예: "Description 의 쉼표·줄바꿈만 write_csv 가 바꾼다"). 옆에 한두 줄로 이유(molgen 로더가 `,` 로만 나눈다, 2026-10-18 승인)를 적는다.
- 상수 이름·도우미 함수는 재량이다. 새 모듈을 만들지 않는다.

### 3. 변이 검사

각각 손으로 바꿔 해당 테스트가 실패하는 것을 보고 손으로 되돌린다. 실패 단언을 summary에 적는다.
- 쉼표 바꾸기를 뺀다 → 쉼표·줄바꿈 테스트의 split 칸 수, GUI CSV 테스트
- 줄바꿈 바꾸기를 뺀다 → 줄 수 단언
- 모든 열에 적용한다 → "다른 컬럼·다른 CSV는 그대로"
- rows를 제자리에서 고친다 → "넘겨받은 rows를 고치지 않는다"

## Acceptance Criteria

```bash
uv run pytest tests/test_export.py -q                 # 새 테스트 통과 (수정 전에는 쉼표·줄바꿈 테스트가 실패해야 한다)
uv run pytest tests/gui/test_export_format.py -q      # step 2 가 만든 GUI 내보내기 테스트 파일도 (다른 이름이면 그 파일)
uv run pytest tests/gui/test_fake_repo_contract.py tests/gui/test_send_device_data.py -q   # step 0·1 테스트 그대로 (step 0 이 다른 파일을 만들었으면 그 파일)
uv run ruff check src tests
uv run pytest tests/gui -q
uv run pytest -q                                      # DSN 이 있으면 -rs
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다.
   - `utils/exporter.py` 에 PySide6 import가 들어오지 않았는가(Qt 금지 구역, `tests/test_boundaries.py`)?
   - 바뀐 것이 CSV의 Description 열뿐인가? xlsx·불러오기·DB 값·다른 열·이력 CSV가 그대로인가?
   - 파일 I/O가 `encoding="utf-8"` 인가?
   - 알림·로그·CLI 출력 문구가 그대로인가?
3. 결과에 따라 `phases/18-csv-description/index.json` 의 step 3을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "write_csv 가 Description 열의 쉼표를 ';' 로, 줄바꿈을 공백으로 바꿔 씀(molgen 로더가 ',' 로만 나눔, 2026-10-18 승인). xlsx·불러오기·다른 열·이력 CSV 불변, rows 사본. RED: <테스트 이름: 단언>. 변이: <4개 결과>. 테스트: <이름들>. 문서(README CSV 절, PRD 3번, ADR, molgen 선행 조건)는 phase 마무리. DB 테스트: <N passed | 안 돎(DSN 없음)>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- 불러오기(`service/repo/io.py` 의 `import_data`)를 바꾸지 마라. 이유: 승인된 동작은 "불러오기는 그대로" 다. 다른 곳에서 만든 CSV의 쉼표는 그대로 저장한다.
- xlsx(`write_xlsx` 의 값)를 바꾸지 마라. 이유: molgen은 xlsx를 읽지 않고, 승인 범위가 CSV다.
- DB의 description이나 화면 값을 바꾸지 마라. 저장할 때 막거나 경고하지도 마라. 이유: 승인 범위 밖이다. 바꾸는 것은 CSV 파일에 쓰는 글자뿐이다.
- Description 밖의 열, Description 헤더가 없는 CSV를 바꾸지 마라. 이유: 다른 열은 molgen 문법이고, 이력 CSV는 molgen이 읽지 않는다.
- 따옴표(`"`)를 바꾸거나 `csv.writer` 의 quoting을 바꾸지 마라. 이유: 쉼표·줄바꿈이 없으면 molgen에서 칸이 밀리지 않고, gendb 왕복은 csv 모듈이 지킨다.
- `service/repo/io.py`·가짜 repo·컨트롤러를 바꾸지 마라. 이유: step 1·2에서 끝났다. 바꿀 곳은 `write_csv` 하나다.
- molgen 저장소와 `docs/`·README를 바꾸지 마라. 이유: molgen은 끝났고, 문서는 phase 마무리에서 고친다.
- 기존 테스트를 깨뜨리지 마라.
