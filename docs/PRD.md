# PRD: genviewer

## 목표
molgen(`genMOLDB`)이 읽는 device CSV의 원본을 각자 들고 다니던 `.sqlite` 파일 대신 공유 PostgreSQL 하나에 두고, 여러 사람이 동시에 편집해도 남의 작업을 잃지 않게 한다.

## 사용자
molgen용 device 데이터를 만들고 고치는 사내 엔지니어 몇 명. RHEL 8 데스크톱(개발은 Windows)에서 GUI로 쓰고, 상태 확인·불러오기·내보내기·이력 조회는 CLI(`genviewer <command>`)로도 한다. 모두 같은 DB role(`molgen_app`)로 붙고, 사람은 OS 로그인 이름(`updated_by`, `change_log.actor`)으로 구분한다.

## 핵심 기능
1. **process / device 편집**: process(이름 + 버전)를 고르면 device 목록(이름, celltype, 설명, 순서)을 보여준다. 추가·삭제·복사/붙여넣기·끌어서 순서 바꾸기·undo/redo. 버전(`S00-V1.0.0.0` 같은 자유 문자열)마다 device 데이터가 따로 있고, 새 버전은 기존 버전에서 복제해 만들 수 있다(ADR-018).
2. **파라미터 탭**: device마다 molgen CSV 컬럼 하나에 대응하는 탭 14개(`config/tab_config.json`). 값 후보·검증은 `config/delegate_config.json`. 요약 탭과 dirty 표시(` *`).
3. **CSV / xlsx**: CSV 불러오기(행마다 새 device, 같은 파일을 두 번 넣으면 두 배, 불러올 때 버전을 정한다), process 단위·선택 device 내보내기(.csv/.xlsx). device 설명은 `InstCellName` 다음 `Description` 컬럼으로 오간다(CSV 에서는 쉼표·줄바꿈을 바꿔 쓴다, Virtuoso 로는 보내지 않는다).
4. **동시 편집**: 저장 시 `device.version` 으로 충돌을 잡아 다시 읽기/덮어쓰기/취소를 묻는다. 10초마다 지금 process가 남에 의해 바뀌었는지 보고 배너로 알린다. 자동으로 다시 읽지 않는다.
5. **변경 이력**: 누가 언제 무엇을 더하고 지우고 고쳤는지 `change_log` 에 쌓고, `genviewer log`(숨김 명령)와 `--history` 화면으로 본다. 값이 실제로 바뀐 것만 남는다.
6. **Virtuoso 연동**: TCP 소켓으로 Virtuoso SKILL 세션에 붙어 device 목록(`filterCellHasSymbolLayout`)을 받아 비교하고, 선택 device를 `pydata = list(...)` SKILL 리스트로 보낸다.
7. **CLI**: `status`, `processes`, `load`, `export`, `log`(숨김), `--check-config`. device 편집은 창에서만 한다.
8. **운영 도구**: `genviewer-init-db`(스키마·권한, 멱등), `tools/initdb.sh`(클러스터), `tools/deploy.sh`(태그 고정 공유 설치).

## 제외 사항
- 서버 프로그램(FastAPI 등). 동시성은 서버 프로세스가 아니라 낙관적 잠금이 처리한다.
- CLI에서 device·탭 편집. 낙관적 잠금과 충돌 해결이 창에 묶여 있다.
- 남이 바꾼 내용을 자동으로 다시 읽기.
- RHEL 7에서 앱 실행(Qt 6가 glibc 2.28을 요구한다). RHEL 7은 DB 서버와 `init_db` 만.
- `psql` 로 직접 고친 내용의 이력, 사람별 DB role.
- 새 기능. 지금 단계는 에러·버그만 고친다(사용자가 승인한 기능만 예외: Description 컬럼 ADR-017, process 버전 ADR-018).
- 버전 사이의 상속(빈 버전 값을 다른 버전이 물려받기). 버전은 서로 독립된 복사본이다.

## 디자인
- 업무용 도구: Qt Fusion 스타일, 어두운 Graphite 테마가 기본(밝은 Mist로 전환), 9pt, 정보 밀도 우선, 장식 없음.
- 저장·접속 중에는 대기 커서로 입력을 막는다. 화면을 바꾸면 방금 보낸 것과 다른 내용이 저장된 것처럼 보이기 때문이다.
