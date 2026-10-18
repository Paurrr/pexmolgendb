# 구조 제안: 유지보수하기 쉬운 형태로 (제안만, 구현하지 않음)

- 작성: 2026-10-17. 2026-10-17 코드 분석에서 나왔다.
- **이 문서는 하네스 프롬프트에 주입되지 않는다**(`docs/notes/`). step 세션은 이것을 할 일로 읽으면 안 된다.
- 지금 단계는 버그만 고친다(ADR-015). 아래 항목은 하나씩 사용자 승인을 받은 뒤 별도 phase로만 진행한다. 모든 항목이 **사용자가 보는 동작을 바꾸지 않는 것**을 전제로 한다.
- **2026-10-17 사용자 승인**: P1~P7 전부 승인했다. 담당 phase는 아래와 같다. 끝나면 이 표에 완료를 적는다.
  - P1 → `6-boundary-guards` — 2026-10-18 완료(`tests/test_boundaries.py`, `tests/test_py39_compat.py`, 헬퍼 `tests/fixtures/imports.py`)
  - P7 → `8-schema-migration` — 2026-10-18 완료(`schema.pg_child_add_columns_ddl`, `diagnostics.ServerInfo.missing_columns`)
  - P6 → `13-virtuoso-socket`. known-issues K14·K24·K39·K40을 먼저 재현한 뒤 재작성으로 없앤다.
  - P2 → `14-prompts`
  - P4 → `15-public-api`
  - P3 → `16-save-coordinator`
  - P5 → `17-async-db-calls`. 대기 커서가 더 자주 뜨는 것은 승인된 보이는 변화다.
  - phase 14~17의 step 파일은 phase 13을 합친 뒤 그때 코드 기준으로 쓴다.

## 진단: 무엇이 유지보수를 어렵게 하나

| 증상 | 근거 | 결과 |
|---|---|---|
| 저장 흐름이 컨트롤러 셋에 흩어져 있다 | `DeviceTabController.save_db`, `DeviceTableController.save_all`/`_write_devices`, `ParameterTabController.save_all`/`_apply`, `_switch_device_by_index`, `on_process_changed` 가 각자 dirty 확인·저장·충돌 처리를 한다 | 같은 종류의 버그가 여러 곳에서 난다(phase 3의 G1~G5: 탭 미저장, 취소가 취소되지 않음, 내 저장에 내가 충돌) |
| 대화상자가 코드 곳곳에서 직접 뜬다 | `QMessageBox`, `utils/dialogs.question`, `dialogs/conflict.ask_conflict`, `QFileDialog` 를 각 모듈이 `from … import` 해서 부른다 | GUI 테스트가 모듈마다 monkeypatch해야 한다. GUI 테스트가 0개였던 이유 중 하나 |
| 컴포넌트끼리 private 멤버를 부른다 | `parameter_tab._clear_tabs()`, `ui._selected_source_rows`, `ui._map_to_source_row`, `device_tab_view._open_connect` … | 한쪽을 고치면 다른 쪽이 조용히 깨진다 |
| 경계가 테스트로 지켜지지 않는다 | Qt 금지 구역과 init_db의 Python 3.9 호환은 주석과 리뷰로만 지킨다 | 누군가 `service/` 에 Qt를 import하거나 3.10 문법을 쓰면 서버에서야 드러난다 |
| GUI 스레드에서 도는 동기 DB 호출 | process 목록·추가·삭제, 탭 로드(device 클릭마다 14쿼리), 복사·붙여넣기, export | 서버가 느리면 창이 타임아웃(최대 15초)까지 굳는다 |
| 소켓 수명 관리가 QThread 셋에 나뉘어 있다 | `net/` Connect/Receive/Send 워커, 소켓 타임아웃 없음, 종료 시 멈추지 않음 | 두 번 클릭·연결 끊김·종료에서 크래시와 멈춤 위험(phase 4 step 6) |

## 레퍼런스

1. **pexqa (하우스 기준, `../pexqa`)**: 같은 사람이 PyQt5 레거시를 PySide6 + Qt-free core로 다시 쓴 저장소다. 그대로 가져올 수 있는 것:
   - `tests/test_boundaries.py` + `tests/fixtures/imports.py`(`package_imports` 스캐너): 패키지별 import 금지를 테스트로 강제한다.
   - `gui.prompts.Prompts`: QMessageBox/QFileDialog를 한 객체로 모으고 테스트에서 `FakePrompts` 로 바꾼다.
   - `gui.workers.Bridge` / `run_in_thread`: 시그널에는 순수 데이터만 싣는다. 비동기 콜백 첫 줄 `if self.closed: return`, busy 해제는 `finally`.
   - CLAUDE.md의 "이유: …(phase N 리뷰)" 식 규칙 누적, `phases/` 마무리 절차.
2. **Pexorche / fmserver (하우스 기준)**: CLI(typer, `main()` 에서 예외를 문장으로)와 서비스 계층(frozen dataclass 설정, 풀 설정)은 이미 이 형태다. 바꿀 것이 없다.
3. **import-linter** (`seddonym/import-linter`, 외부): `forbidden`/`layers` contract로 "이 패키지는 저 패키지를 import하지 않는다"를 선언하고 간접 import까지 검사한다. pexqa 스캐너의 외부 대안이다. 의존성이 하나 늘고 하우스 방식과 달라지므로 **pexqa 스캐너를 우선**한다.
4. **Martin Fowler, *Presentation Model* / Michael Feathers, *The Humble Dialog Box***: 위젯은 얇게(humble) 두고, 판단(저장할지, 무엇이 dirty인지, 충돌을 어떻게 처리할지)은 Qt 없이 테스트할 수 있는 객체로 뺀다. 지금의 passive view + controller 구조는 이미 절반쯤 와 있다. 저장 판단만 한곳으로 모으면 된다.
5. **Qt Model/View 문서**: `QPersistentModelIndex`(모델 reset 뒤에도 유효한 인덱스), `QSortFilterProxyModel.mapToSource`. phase 4의 G8(필터 중 정렬)과 선택 추적 버그의 근본 원인이 proxy 행과 source 행을 섞어 쓰는 데 있다.
6. **Qt `QTcpSocket`**: 이벤트 루프 기반 소켓이다. 스레드 없이 `readyRead`/`disconnected` 시그널로 동작해 워커 수명 문제가 없어진다.

## 제안 (순서대로, 각각 별도 phase, 사용자 승인 후)

| # | 제안 | 바뀌는 것 | 위험 | 근거 |
|---|---|---|---|---|
| P1 | **경계 가드 테스트** | 테스트만 추가: ① `service/`·`scripts/`·`config/`·`cli.py`·`utils/{logs,user,exporter,validators,lisp}.py` 에 PySide6 import 금지(간접 포함). ② `init_db` 에서 닿는 모듈을 `ast.parse(feature_version=(3, 9))` 로 검사. ③ `models/` 는 `controllers/`·`views/` 를 import하지 않음 | 없음(코드 불변) | pexqa `test_boundaries.py`. CLAUDE.md CRITICAL 규칙을 리뷰가 아니라 테스트가 지키게 된다 |
| P2 | **Prompts 주입** | `utils/prompts.py` 에 `Prompts`(info/warning/error/question/ask_conflict/파일 대화상자)를 두고 controller와 view가 그것만 부른다 | 낮음. 화면 동작은 그대로 | pexqa `gui.prompts`. phase 2의 monkeypatch fixture가 `FakePrompts` 하나로 줄어든다 |
| P3 | **저장 조정자(SaveCoordinator)** | device 표와 탭의 "dirty인가 → 저장 → 충돌 처리 → 결과(bool)"를 객체 하나로 모으고, process·device 전환, 메뉴 Save, Ctrl+S, 창 닫기가 모두 그것을 부른다 | 중간. 저장 경로 전체를 건드린다. phase 3 테스트가 그물이다 | Presentation Model. G1~G5·G6가 같은 원인에서 나왔다 |
| P4 | **private 접근을 공개 API로** | view가 `selected_source_rows()`, `clear_tabs()` 같은 공개 메서드를 내고 controller는 그것만 부른다. `dialogs/connection.py` 의 DB ping을 controller로 옮긴다 | 낮음 | ARCHITECTURE "현재 어긋난 곳" |
| P5 | **남은 동기 DB 호출을 워커로** | process 조작·탭 로드·export를 `run_blocking`/`Task` 로 | 중간. 재진입(대기 중 클릭)을 다뤄야 한다 | ADR-009의 의도를 끝까지 적용 |
| P6 | **`net/` 을 `QTcpSocket` 으로** | QThread 워커 셋을 이벤트 기반 소켓 하나로. 프레임(4바이트 길이 + UTF-8)은 그대로 | 중간. Virtuoso 쪽과 실제로 붙여 봐야 한다 | Qt 문서. G14 계열이 구조적으로 사라진다 |
| P7 | **컬럼 추가 마이그레이션** (기능) | `init_db` 가 기존 탭 테이블에 `ALTER TABLE … ADD COLUMN IF NOT EXISTS`(PG 9.6+)를 생성. `status` 가 컬럼까지 확인 | 기능 추가라 별도 승인 | ADR-003의 트레이드오프 |

- 권하지 않는 것: `genviewer/gui/` 아래로 GUI 패키지를 통째로 옮기는 대이동(pexqa 형태). import 경로가 전부 바뀌는 비용에 비해 P1 가드 테스트가 같은 이점(경계 강제)을 준다.
- 순서 이유: P1은 위험이 없고 이후 모든 작업의 그물이다. P2는 P3의 테스트를 쉽게 만든다. P3·P4는 phase 3·4 버그 수정이 끝난 뒤 그 테스트를 그물로 삼는다.
