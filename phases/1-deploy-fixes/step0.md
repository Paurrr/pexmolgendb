# Step 0: launcher-config

## 배경 (phase 1 공통)

이 저장소는 이미 여러 명이 쓰는 도구다. 지금은 **에러·버그만 고친다**(CLAUDE.md, ADR-015). phase 1은 배포·클러스터 셸 스크립트(`tools/deploy.sh`, `tools/initdb.sh`)와 deploy.sh 가 만드는 런처(`<ROOT>/bin/<명령>`)의 버그 넷을 하나씩 고친다. 셸 스크립트 테스트는 진짜 `sh`·`git` 으로 스크립트를 실행한다. PATH 앞(또는 `PGBIN`)에 둔 stub 명령이 받은 인자를 파일에 기록하고, 테스트는 그 기록과 결과 디렉터리를 단언한다(`tests/test_deploy_sh.py` 방식). 스크립트 본문의 토큰 검사만으로 끝내지 않는다. 개발 PC는 Windows이고 테스트는 Git Bash `sh` 로 돈다(2026-10-17 기준 `tests/test_deploy_sh.py` 는 개발 PC에서 11 passed / 5 skipped).

모든 step에 같은 규칙이 적용된다.
1. 아래 "버그"는 **분석 에이전트의 주장**이다. 먼저 실패하는 테스트로 재현하고, RED 출력(테스트 이름과 실패한 단언)을 summary에 적는다.
2. RED는 **Windows 개발 PC에서**(Git Bash `sh`) 보여야 한다. `posix_only` 테스트는 개발 PC에서 skip되므로 버그를 증명하지 못한다. `sh`/`git` 이 없어서 skip된 테스트도 RED가 아니다.
3. 재현되지 않으면 `tools/`·`src/` 를 고치지 않는다. 테스트는 특성 테스트로 남기고 `"status": "completed"`, `"summary": "not reproduced: <이유>"` 로 끝낸다.
4. 고친 뒤 수정을 손으로 되돌려 새 테스트가 실패하는지 확인하고 다시 고친다(변이 검사). `git checkout`/`git stash` 로 되돌리지 마라. 이유: 같은 step의 테스트 변경까지 사라진다.
5. 이 파일의 행 번호는 2026-10-17 기준 대략값이다. 이름으로 찾아라.

## 이 step의 목적

`tools/deploy.sh` 가 만드는 런처가 `GENDB_CONFIG` 를 정하지 않게 한다. 그러면 배포본도 README '찾는 순서' 표대로 `~/.genviewer.env`(개인) → `<ROOT>/genviewer.env`(공용) 순으로 설정 파일을 찾는다. 지금은 런처가 `GENDB_CONFIG=<ROOT>/genviewer.env` 를 항상 넘겨서 배포본에서는 개인 파일이 절대 읽히지 않는다.

**사용자 승인 2026-10-17**: README 대로 배포본도 `~/.genviewer.env` 를 읽게 한다. 이 수정 뒤에는 홈에 `~/.genviewer.env` 가 있는 사용자가 공용 파일 대신 그 파일로 붙는다. 의도한 변화다.

## 읽어야 할 파일

- `/CLAUDE.md`, `/docs/ARCHITECTURE.md`(데이터 흐름 "접속 설정", 배포 구조), `/docs/ADR.md`(ADR-007, ADR-011)
- `/README.md` — '찾는 순서'(~58-84. 표 3·4·5번과 그 아래 "**현재 배포본(`tools/deploy.sh` 의 런처)은** …" 항목 ~74-76), '배포'(~236-300)
- `tools/deploy.sh` — 런처 절 주석(~115-127), 런처 heredoc(`cat > "$root/bin/$cmd" <<LAUNCHER`, ~142-163). 특히 ~156-159의 `GENDB_CONFIG` 두 줄과 그 위 주석
- `src/genviewer/service/env_file.py` — `_site_roots()`(~89-110, docstring 마지막 문단 ~96-98), `candidates()`(~113-134), `load()`
- `src/genviewer/service/config.py` — `CONFIG_ENV`, `resolve_dsn()`(`env_file.load(os.environ.get(CONFIG_ENV, "").strip())`)
- `src/genviewer/service/diagnostics.py` — `inspect_config()`, `config_lines()`. `--check-config` 가 찍는 "설정 파일:"·"찾아본 곳:" 줄이 여기서 나온다
- `src/genviewer/utils/logs.py` — `LOG_ENV` 위 주석(~20행, "배포본에서는 런처가 GENDB_CONFIG 만 넘기므로 기본값을 쓴다")
- `tests/test_deploy_sh.py` — `UV_STUB`(가짜 uv가 `venv/bin/python` 을 셸 스크립트로 만든다), `source_repo`/`stub`/`root` fixture, `deploy()` 헬퍼(`DEPLOY_`/`GENDB_`/`PG` 환경변수를 지운다), `test_a_launcher_runs_the_venv_interpreter_and_names_the_config`(~209-222)
- `tests/test_env_file.py` — autouse `clean_env`, `site` fixture, `_fake_module_at`, `test_an_installed_package_does_not_invent_a_candidate`
- `tests/test_cli.py` — `isolated` fixture(`GENDB_CONFIG` 를 없는 파일로 정해 개발자 홈의 설정을 막는다)
- 이전 phase(`0-service-fixes`)에서 수정된 파일: `src/genviewer/service/env_file.py`(`load()` 의 utf-8-sig 읽기), `src/genviewer/utils/logs.py`(`setup()` 의 chmod 조건). 이 step이 고칠 docstring·주석과는 겹치지 않는다.

## 버그

런처 heredoc에 이렇게 있다(heredoc 안이라 `$` 가 `\$` 로 적혀 있다).

```sh
# 설정은 venv 바깥에 있다. 앱이 sys.prefix 의 부모에서 스스로도 찾지만, 명시하면
# 추측이 없어진다.
GENDB_CONFIG="\${GENDB_CONFIG:-\$here/../genviewer.env}"
export GENDB_CONFIG
```

`env_file.candidates(explicit)` 는 `explicit`(= `GENDB_CONFIG`)이 비어 있지 않으면 `[Path(explicit)]` 만 돌려준다. 그래서 배포본에서는 README '찾는 순서' 4번(`~/.genviewer.env`, 개인 파일이 공용 값을 덮어쓴다)이 절대 적용되지 않는다. README와 ARCHITECTURE가 이 어긋남을 "phase `1-deploy-fixes` 에서 고친다" 고 적어 두었다.

런처가 이 줄을 빼도 공용 파일은 찾는다. 런처는 `<ROOT>/venv/bin/python` 을 직접 부르므로 `sys.prefix` 가 `<ROOT>/venv` 다(`site.py` 의 `venv()` 가 실행 파일 경로를 `os.path.abspath` 로 정규화하므로 `bin/../venv` 의 `..` 도 남지 않는다). `_site_roots()` 가 `sys.prefix.parent` 를 후보로 넣으므로 `<ROOT>/genviewer.env` 가 걸린다.

재현: stub 배포(`deploy()`) 뒤 `<root>/venv/bin/python` 을 `echo "GENDB_CONFIG=${GENDB_CONFIG-unset}"` 하는 셸 스크립트로 바꾼다. `GENDB_CONFIG` 가 없는 환경에서 `sh <root>/bin/genviewer` 를 돌리면 `unset` 이 아니라 `.../deployed/bin/../genviewer.env` 가 찍힌다(2026-10-17 개발 PC Git Bash에서 확인).

## 작업

### 1. 테스트 먼저

`tests/test_deploy_sh.py`:

- 런처 실행 헬퍼를 둔다. 환경은 `deploy()` 처럼 `os.environ` 사본에서 `DEPLOY_`/`GENDB_`/`PG` 로 시작하는 변수를 지우고, 인자로 받은 값만 더한다. `["sh", str(root / "bin" / "genviewer")]` 를 `capture_output=True, text=True, encoding="utf-8", errors="replace"` 로 돌린다.
- 배포 뒤 `root / "venv" / "bin" / "python"` 을 덮어쓸 stub은 `#!/bin/sh` 로 시작한다. `newline="\n"` 으로 쓰고 `chmod(0o755)` 한다. 이유: 런처가 `[ -x "$here/../venv/bin/python" ]` 로 확인한다. Git Bash는 `#!` 로 시작하는 파일을 실행 가능으로 본다.
- `GENDB_CONFIG` 없이 런처를 실행하면 stdout이 `GENDB_CONFIG=unset` 이다. **수정 전에는 `.../genviewer.env` 가 찍혀 실패해야 한다.**
- `GENDB_CONFIG=/x` 로 실행하면 `GENDB_CONFIG=/x` 다. 사용자가 정한 값은 그대로 넘어간다(수정 전후 모두 통과).
- `test_a_launcher_runs_the_venv_interpreter_and_names_the_config` 에서 `assert "GENDB_CONFIG" in text and "genviewer.env" in text` 를 지우고, 이름을 `test_a_launcher_runs_the_venv_interpreter` 로 바꾼다. 나머지 단언(`#!/bin/sh`, exec 줄의 `/venv/bin/python`, exec 줄에 uv 없음, CRLF 없음)은 그대로 둔다. 이 테스트가 지키던 "런처가 설정 파일을 명시한다" 는 성질은 이 step이 일부러 없애는 것이고, 대신 위 행동 테스트가 런처의 설정 동작을 지킨다.

`tests/test_env_file.py`(배포 레이아웃 특성 테스트):

- 앱 쪽은 이미 맞으므로 **수정 전에도 통과한다**. 수정이 기대는 사실을 고정하는 테스트다. RED는 위 런처 테스트에서 본다.
- `site` fixture를 쓰지 않고 `_site_roots` 도 패치하지 않는다. 실제 `_site_roots()` 가 `sys.prefix` 에서 배포 루트를 계산하는지를 봐야 한다. 대신 셋을 바꾼다:
  - `monkeypatch.setattr(sys, "prefix", str(tmp_path / "deployed" / "venv"))`
  - `env_file.__file__` → `_fake_module_at(tmp_path / "deployed", "venv", "lib", "python3.13", "site-packages", "genviewer", "service", "env_file.py")`. 비-editable 설치 모양이라 체크아웃 후보가 끼지 않는다
  - `env_file.USER_ENV` → `tmp_path / "home" / ".genviewer.env"`
- 개인 파일이 없으면 `env_file.load()` 가 `tmp_path / "deployed" / "genviewer.env"` 를 돌려주고 그 값이 `os.environ` 에 들어간다.
- 개인 파일이 있으면 `load()` 가 개인 파일을 돌려주고, 공용 파일에만 있는 키는 들어가지 않는다(파일 하나만 읽는다).
- `candidates()` 순서는 개인 파일 → `<deployed>/venv/genviewer.env` → `<deployed>/genviewer.env` 다.

### 2. 수정 (`tools/deploy.sh` 의 런처 heredoc)

- 런처에서 `GENDB_CONFIG=...` 줄, `export GENDB_CONFIG` 줄, 그 위 주석 두 줄을 지운다. 런처는 환경변수를 정하지 않는다. 사용자가 셸에서 정한 `GENDB_CONFIG` 는 상속으로 그대로 넘어간다.
- 나머지(`here=` 계산, venv 확인과 `exit 127`, `exec "$here/../venv/bin/python" "$here/../venv/bin/$cmd" "$@"`)는 그대로 둔다.
- 이유를 적고 싶으면 heredoc 밖, 런처 절 주석(~115-127)에 한두 줄로 적는다. 내용: 런처는 설정 파일을 고르지 않는다. 앱이 `~/.genviewer.env` → `<ROOT>/genviewer.env`(`sys.prefix` 의 부모) 순으로 찾는다.
- `src/` 의 코드는 바꾸지 않는다(아래 문서 절의 docstring·주석만).

### 3. 문서

- `README.md` '찾는 순서': 표 아래의 "**현재 배포본(`tools/deploy.sh` 의 런처)은 3번 `GENDB_CONFIG` 를 항상 공용 파일로 고정해서 넘긴다.** … `phases/1-deploy-fixes` 에 있다." 항목을 지운다. 표 자체는 이제 맞다.
- `README.md` '배포': 확인 항목 하나를 더한다(예: "마지막에 만든 런처를 실제로 실행해 본다" 항목 뒤). 내용: 배포한 뒤 `genviewer --check-config` 를 돌리면 "설정 파일:" 이 `<루트>/genviewer.env` 다. 그 계정에 `~/.genviewer.env` 가 있으면 그 파일이 대신 찍힌다('찾는 순서' 4번). 스크립트 마지막 확인은 `--help` 만 돌리므로 설정 문제는 거기서 드러나지 않는다.
- `docs/ARCHITECTURE.md` 데이터 흐름 "접속 설정" 아래의 "- 배포 런처는 지금 `GENDB_CONFIG=<ROOT>/genviewer.env` 를 항상 넘긴다. …(phase `1-deploy-fixes` step 0에서 고친다)." 줄을 지운다. 그 위 흐름도는 그대로 맞다.
- `src/genviewer/service/env_file.py` `_site_roots()` docstring 마지막 문단("그래도 런처는 GENDB_CONFIG 를 명시해서 넘긴다 - 추측이 하나라도 적은 편이 낫다."): 런처는 GENDB_CONFIG 를 정하지 않으므로 이 후보(`sys.prefix` 의 부모)가 배포본이 공용 파일을 찾는 길이다, 로 고친다.
- `src/genviewer/utils/logs.py` `LOG_ENV` 위 주석(~20행): 런처는 환경변수를 정하지 않으므로 배포본도 따로 주지 않으면 기본 경로를 쓴다, 로 고친다.
- `docs/ADR.md` 는 바꾸지 않는다. ADR-007의 "찾은 첫 파일 하나만" 이 그대로 맞다.

## Acceptance Criteria

```bash
sh -n tools/deploy.sh && sh -n tools/initdb.sh       # 문법 검사 (sh -n 은 첫 파일만 보므로 따로 돌린다)
! git ls-files --eol tools/*.sh | grep -v 'w/lf'     # 작업 트리가 LF 그대로
uv run pytest tests/test_deploy_sh.py tests/test_env_file.py -q -rs   # 새 테스트 통과 (수정 전에는 런처 unset 테스트가 실패해야 한다). -rs 로 새 테스트가 skip 되지 않았는지 본다
uv run ruff check src tests
uv run pytest -q
```

## 검증 절차

1. 위 AC 커맨드를 실행한다.
2. 아키텍처 체크리스트를 확인한다:
   - 런처가 여전히 `#!/bin/sh` POSIX이고 venv 인터프리터를 직접 부르는가(uv 없음)?
   - `env_file` 의 코드(`candidates`, `_site_roots`, `load`)는 그대로이고 docstring만 바뀌었는가?
   - `genviewer.env` 의 640과 `a+rX` 제외(ADR-007, ADR-011)가 그대로인가?
3. 결과에 따라 `phases/1-deploy-fixes/index.json` 의 step 0을 업데이트한다:
   - 성공 → `"status": "completed"`, `"summary": "deploy.sh 런처가 GENDB_CONFIG 를 정하지 않음(사용자 값은 통과), 배포본도 ~/.genviewer.env → <ROOT>/genviewer.env. RED: <테스트 이름>. README 찾는 순서·배포, ARCHITECTURE, env_file docstring, logs.py 주석 정리"`
   - 재현 안 됨 → `"status": "completed"`, `"summary": "not reproduced: <이유>"`
   - 수정 3회 시도 후에도 실패 → `"status": "error"`, `"error_message": "구체적 에러 내용"`
   - 사용자 개입 필요 → `"status": "blocked"`, `"blocked_reason": "구체적 사유"` 후 즉시 중단

## 금지사항

- `env_file._site_roots()` 의 `sys.prefix.parent` 후보를 지우거나 순서를 바꾸지 마라. 이유: 런처가 `GENDB_CONFIG` 를 넘기지 않으면 이 후보가 배포본이 `<ROOT>/genviewer.env` 를 찾는 유일한 길이다. 없어지면 홈에 아무것도 없는 사람이 "접속 정보가 없다" 로 막힌다.
- 앱이 두 파일을 겹쳐 읽게 하지 마라(개인 파일과 공용 파일의 키 단위 병합 등). 이유: ADR-007 "파일은 하나만 읽는다". 값의 출처를 추적할 수 없게 된다.
- `candidates()` 의 "`GENDB_CONFIG` 를 주면 그것만 본다" 를 바꾸지 마라. 이유: README 표 3번의 약속이고, `tests/test_cli.py` 의 `isolated` fixture가 이것으로 개발자 홈의 설정을 막는다.
- 런처에 `unset GENDB_CONFIG` 를 넣거나 다른 환경변수(`GENDB_LOG` 등)를 새로 정하지 마라. 이유: 사용자가 정한 값은 그대로 넘어가야 하고, 그 밖의 동작 변경은 승인 범위 밖이다.
- 런처나 deploy.sh에 bash 전용 문법(`[[ ]]`, `local`, 배열, `$'…'`)을 쓰지 마라. 이유: `#!/bin/sh` 로 돈다.
- 진짜 uv나 PostgreSQL이 필요한 테스트를 만들지 마라. 이유: stub으로 충분하고, 개발 PC에서 RED가 보여야 한다.
- 기존 테스트를 깨뜨리지 마라.
