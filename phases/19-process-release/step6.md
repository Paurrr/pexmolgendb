# Step 6: cli-release

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

**이름 규칙.** 새 개념은 코드·DB 에서 **`release`** 다. 화면 라벨은 `Version`, CLI 옵션은 `--version` 이다. 새 개념에 `version` 이라는 이름(변수·키·컬럼·시그널)을 쓰지 마라. 이유: `device.version` 은 낙관적 잠금 카운터이고 `deviceVersionBumped`·`set_device_version`·`expected_version`·device dict 의 `"version"` 키 등 200곳 넘게 그 뜻으로 쓴다. (CLI 옵션 이름 `--version` 만 예외다. 파이썬 인자 이름은 `release` 로 둔다.)

**빈 버전.** `''` 은 "버전 없음" 이고 옛 동작과 같다. repo 메서드의 `release` 인자는 keyword 이고 기본값 `""` 이다(옛 호출자·테스트가 그대로 돈다). 사람이 읽는 process 표시는 `audit.process_label(name, release)` 하나로 만든다(step 1이 만들었다). 빈 버전이면 `name`, 아니면 `f"{name} {release}"` 다. **빈 버전일 때 기존 문구·출력은 바이트까지 그대로여야 한다.**

이 phase의 step (각 step 은 앞 step 이 끝난 코드 위에서 돈다):
- step 0 `schema-release`: DDL·마이그레이션·`status` 진단 (DB)
- step 1 `audit-release`: change_log 에 버전, `process_label`, `recent(release=)` (DB)
- step 2 `process-repo-release`: `ProcessRepository`·`find_or_create` 가 (이름, 버전)을 받는다, `list_pairs` (DB)
- step 3 `audit-sources`: device·탭 저장 이력이 버전을 싣는다 (DB)
- step 4 `release-clone`: `ProcessRepository.clone` (DB)
- step 5 `io-release`: CSV 불러오기가 버전을 받는다 (DB)
- step 6 `cli-release`: `processes`·`load`·`export`·`log` (DB) ← 이 step
- step 7 `toolbar-pairs-view`: 툴바 view 의 콤보 두 개 (GUI)
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

## DB step 규칙

- **CLI 테스트(`tests/test_cli.py`)는 대부분 `db`/`pg_dsn` fixture 를 쓰는 DB 테스트다. `ProcessRepository.list_with_counts` 의 SQL 도 바꾼다.** `GENDB_TEST_PG_DSN`(관리자 DSN)이 없으면 코드를 고치지 말고 `"status": "blocked"` 로 멈춘다. DB 테스트가 skip된 것은 통과가 아니다(`-rs` 로 확인한다).
- SQL은 PostgreSQL 10~15에서 돌아야 한다. 값은 바인드 파라미터로 넘긴다.
- `cli.py` 는 모듈 수준에서 PySide6 를 import 하지 않는다(CLAUDE.md CRITICAL, `tests/test_boundaries.py`).
- CLI 출력 규칙(ADR-012): rich 없음, 표 머리글은 ASCII(한글은 두 칸이라 칸이 어긋난다), 종료 코드 0/1/2/130.

## 선행 step

- step 1: `AuditRepository.recent(release=None|str)`, `process_label`, `where_of`(log 줄의 process 칸).
- step 2: `ProcessRepository` 메서드의 keyword `release`, `list_pairs()`.
- step 5: `IORepository.import_data(path, *, release="", actor="")`.
- `phases/19-process-release/index.json` 의 step 0~5 summary 를 읽어라.

## 이 step의 목적

CLI 가 버전을 다룬다. 옵션 이름은 `--version`(짧은 이름 없음. `-v` 는 이미 `--verbose` 다). 옵션을 주지 않으면 빈 버전이고 지금 동작 그대로다.

| 명령 | 바뀐 뒤 |
|---|---|
| `processes` | 표가 `NAME  VERSION  DEVICE` 세 칸이 된다. 행은 (이름, 버전) 쌍마다 하나, 순서는 `list_pairs` 와 같다. 빈 버전은 `-` 로 찍는다(`(없음)` 은 한글 두 칸이라 칸이 어긋난다). 마지막 줄 `process {쌍 수}개, device {합}개` 는 문장 그대로다. **이 표는 빈 버전만 있어도 VERSION 칸이 생긴다(승인된 출력 변경). 기존 테스트의 기대값을 고친다** |
| `ProcessRepository.list_with_counts()` | `[(name, release, n), …]`, 순서는 `list_pairs` 와 같다(`ORDER BY name, release COLLATE "C"`). 쌍마다 device 수. CLI 만 쓴다 |
| `load CSV [--version V]` | `import_data(path, release=V.strip(), actor=…)`. 출력 첫 줄은 빈 버전이면 지금 그대로, 아니면 `device {n}개를 새로 추가했다 (version {V}).` 둘째 줄(중복 경고)은 그대로 |
| `export PROCESS 파일 [--version V]` | `get_id(process, release=V)` 로 그 쌍만 내보낸다. CSV 내용(`CdsLibName` = 이름)은 그대로다. 없으면 지금처럼 stderr 에 `그런 process 가 없다: {process_label}` 를 쓰고, **같은 이름의 다른 버전이 있으면** 다음 줄에 `있는 버전: a, b`(빈 버전은 `-`, `list_pairs` 순서)를 쓴 뒤 exit 1. device 가 없을 때 문구의 process 자리도 `process_label` |
| `log [--version V]` (숨김 명령) | `recent(release=V)`. 옵션을 안 주면 `None`(거르지 않음), `--version ""` 이면 빈 버전만. `--follow` 도 같은 필터(`_follow` 는 맨 뒤에 `release=None` 인자를 더한다. 테스트가 `_follow` 를 위치 인자 7개로 부른다) |
| `log --out FILE` | CSV 머리글 `process` 다음에 `version` 칸, 값은 `process_release` |
| `status` | 바꾸지 않는다(`process N개` 는 쌍의 수다) |

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ADR.md`(ADR-012 CLI), `README.md` 의 명령줄 절(지금 동작 파악용, 고치지 않는다)
- `src/genviewer/cli.py`: `processes`(~217), `load`(~239), `export`(~264), `log`(~351), `_follow`(~412), `_write_log_csv`(~443)
- `src/genviewer/service/repo/process.py`: `list_with_counts`, `list_pairs`, `get_id`
- `src/genviewer/service/repo/audit.py`: `recent`, `process_label`, `format_line`
- `tests/test_cli.py`: fixture 행(~37-42), `test_processes_*`(~351-363), `list_with_counts` 단언(~370, 378, 403, `dict()` 로 바꾸는 곳은 3-튜플이면 깨진다), `test_export_*`(~381-446), `test_log_filters_by_person_and_process`(~661), `--out`(~672), `_follow` 를 부르는 테스트(~729)

## 작업

### 1. 테스트 먼저

`tests/test_cli.py`(DB):
- `load sf2p.csv --version V1` 뒤 `processes` 가 `sf2p  -` 줄과 `sf2p  V1` 줄을 따로 보이고 device 수가 각각 맞다.
- `export sf2p out.csv --version V1` 은 V1 의 device 만 쓴다. `--version` 없이 내보내면 빈 버전 것만 쓴다(지금 결과와 같다).
- 빈 버전이 없고 V1 만 있는 `sf9x` 를 `--version` 없이 내보내면 exit 1, stderr 에 `그런 process 가 없다: sf9x` 와 `있는 버전: V1`, 파일을 만들지 않는다.
- `export sf2p out.csv --version V9`(없음) 는 `그런 process 가 없다: sf2p V9` 와 `있는 버전: -, V1` 을 낸다.
- `log --version V1` 은 V1 줄만, `log --version ""` 은 빈 버전 줄만, 옵션 없으면 모두.
- `log --out` 파일의 머리글에 `version` 이 `process` 다음에 있다.
- `load --version "  V1  "` 은 `V1` 로 들어간다.
- `--help` 가 cp949 로도 찍힌다(지금 테스트가 모든 명령을 본다).

수정 전에는 위 테스트가 실패해야 한다(`--version` 없음).

### 2. 수정

- `cli.py`: 위 표대로. 옵션은 `typer.Option("--version", help=…)`. 도움말은 한국어 한 줄(예 `"이 버전으로 불러온다. 비우면 버전 없음."`, `"이 버전을 내보낸다. 비우면 버전 없음."`, `"이 버전 것만. \"\" 이면 버전 없는 것만."`).
- `ProcessRepository.list_with_counts`: 위 표대로.
- 기존 테스트 중 `processes` 표와 `list_with_counts` 를 정확히 단언하던 것은 새 모양에 맞게 고친다. 고친 테스트 이름을 summary에 적는다.

### 3. 변이 검사

- `export` 가 `release` 를 넘기지 않게 해 V1 내보내기 테스트가 실패하는지 본다. 되돌린다.
- `log` 에서 `--version` 이 없을 때 `""` 를 넘기게 바꿔(None 대신) "옵션 없으면 모두" 테스트가 실패하는지 본다. 되돌린다.

## Acceptance Criteria

```bash
test -n "$GENDB_TEST_PG_DSN" || { echo "GENDB_TEST_PG_DSN 없음 → blocked"; exit 1; }
uv run pytest tests/test_cli.py tests/test_boundaries.py -q -rs   # DSN 사유의 SKIPPED 없음
uv run ruff check src tests
uv run pytest -q -rs
```

## 검증 절차

1. 위 AC 커맨드를 실행한다. `GENDB_TEST_PG_DSN` 이 없으면 아무것도 고치지 말고 blocked로 끝낸다.
2. 아키텍처 체크리스트를 확인한다.
   - `--version` 없이 쓰는 `load`·`export`·`log` 의 결과와 출력이 지금과 같은가(`processes` 표 제외)?
   - `cli.py` 가 모듈 수준에서 PySide6 를 import 하지 않는가?
   - 표 머리글이 ASCII 인가? 종료 코드가 0/1/2/130 규칙을 지키는가?
3. 결과에 따라 `phases/19-process-release/index.json` 의 step 6을 업데이트한다.
   - 성공 → `"status": "completed"`, `"summary": "cli: processes NAME VERSION DEVICE(빈 버전 '-'), load/export --version(빈 값=버전 없음, export 없으면 '있는 버전:' 줄), log --version(None=전부, ''=버전 없음), --out version 칸, _follow(…, release=None). list_with_counts → (name, release, n). RED: <테스트 이름: 단언>. 변이: <결과>. 고친 기존 테스트: <이름>. DB 테스트: <N passed>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - `GENDB_TEST_PG_DSN` 없음 → `"status": "blocked"`, `"blocked_reason": "GENDB_TEST_PG_DSN 없음"` 후 즉시 중단

## 금지사항

- `-v` 나 다른 짧은 옵션을 `--version` 에 붙이지 마라. 이유: 루트의 `-v` 는 `--verbose` 다.
- 버전 복제 명령이나 process·버전 이름 바꾸기 명령을 만들지 마라. 이유: 승인 범위 밖이다(복제는 GUI 만, CLI 는 device 를 고치지 않는다, ADR-012).
- `export` 가 CSV 에 버전 컬럼을 쓰게 하지 마라. 이유: CSV 형식은 그대로다.
- `status` 출력을 바꾸지 마라.
- GUI 코드를 고치지 마라.
- 기존 테스트를 깨뜨리지 마라. 승인된 출력 변경(`processes` 표)에 걸린 테스트만 기대값을 고친다.
