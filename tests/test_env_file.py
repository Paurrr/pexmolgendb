"""genviewer.env 를 찾아 환경변수로 넣는 부분.

여기가 틀리면 증상이 "접속이 안 된다" 하나로만 나타나고, 원인이 파일 위치인지
파싱인지 우선순위인지 구분이 안 된다. 그래서 세 가지를 따로 본다.

GUI 도 DB 도 띄우지 않는다. 진짜 홈 디렉터리와 저장소 파일을 보지 않도록
후보 경로를 전부 tmp_path 로 바꿔 놓고 돌린다.
"""

import os
import sys

import pytest

from genviewer.service import env_file


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """os.environ 을 통째로 복원한다.

    env_file.load 는 os.environ.setdefault 로 직접 넣기 때문에 monkeypatch 가
    되돌려 주지 않는다. 안 지우면 앞 테스트의 PGHOST 가 다음 테스트를 통과시킨다.
    """
    saved = dict(os.environ)
    for key in list(os.environ):
        if key.startswith(("PG", "GENDB_")):
            monkeypatch.delenv(key, raising=False)
    yield
    os.environ.clear()
    os.environ.update(saved)


@pytest.fixture
def site(tmp_path, monkeypatch):
    """설치 디렉터리와 개인 파일 자리를 tmp_path 로 옮긴다."""
    install = tmp_path / "install"
    install.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(env_file, "USER_ENV", home / ".genviewer.env")
    monkeypatch.setattr(env_file, "_site_roots", lambda: [install])
    return {"install": install, "user": home / ".genviewer.env"}


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# 파싱 - 규칙이 적은 대신 그 적은 규칙이 정확해야 한다
# --------------------------------------------------------------------------


def test_key_and_value():
    assert env_file.parse("PGHOST=10.1.2.3\nPGPORT=55433\n") == {
        "PGHOST": "10.1.2.3",
        "PGPORT": "55433",
    }


def test_comments_and_blank_lines_are_skipped():
    text = "# 주석\n\n   \nPGHOST=h\n"
    assert env_file.parse(text) == {"PGHOST": "h"}


def test_export_prefix_is_allowed():
    """.env 를 셸에서 source 해 본 사람이 export 를 붙여 두는 일이 흔하다."""
    assert env_file.parse("export PGHOST=h\n") == {"PGHOST": "h"}


def test_a_hash_inside_a_value_is_part_of_the_value():
    """비밀번호에 # 가 흔하다. 줄 끝 주석을 지원하면 그게 조용히 잘린다."""
    assert env_file.parse("PGPASSWORD=a#b # c\n") == {"PGPASSWORD": "a#b # c"}


def test_quotes_are_stripped_and_inner_spaces_kept():
    got = env_file.parse('PGPASSWORD="  두 칸  "\n')
    assert got == {"PGPASSWORD": "  두 칸  "}


def test_shell_metacharacters_survive():
    """셸을 거치지 않으므로 $ 와 백슬래시가 그대로 남아야 한다."""
    raw = "p w$x" + chr(92) + "y'z"
    assert env_file.parse("PGPASSWORD=" + raw + "\n") == {"PGPASSWORD": raw}


def test_only_the_first_equals_splits():
    assert env_file.parse("GENDB_PG_DSN=postgresql://a@b/c?x=1\n") == {
        "GENDB_PG_DSN": "postgresql://a@b/c?x=1"
    }


def test_a_line_without_equals_is_reported():
    """조용히 넘기면 '왜 이 값이 안 먹지' 로 시간을 버린다."""
    with pytest.raises(ValueError, match="Line 2"):
        env_file.parse("PGHOST=h\n그냥 글자\n")


def test_a_bad_key_is_reported():
    with pytest.raises(ValueError, match="key name"):
        env_file.parse("PG HOST=h\n")


# --------------------------------------------------------------------------
# 어느 파일을 보는가
# --------------------------------------------------------------------------


def test_an_explicit_path_is_the_only_candidate():
    """GENDB_CONFIG 로 가리켰는데 조용히 다른 파일이 쓰이면 디버깅이 불가능하다."""
    paths = env_file.candidates("/somewhere/x.env")

    assert len(paths) == 1
    assert paths[0].name == "x.env"


def test_the_personal_file_comes_before_the_install_directory(site):
    paths = env_file.candidates()
    assert paths[0] == site["user"]
    assert site["install"] / env_file.SITE_NAME in paths


def test_duplicate_candidates_are_listed_once(monkeypatch, tmp_path):
    """에러 메시지에 같은 줄이 두 번 나오면 읽는 사람이 오해한다."""
    same = tmp_path / "same"
    monkeypatch.setattr(env_file, "_site_roots", lambda: [same, same])
    paths = env_file.candidates()
    assert len(paths) == len(set(str(p) for p in paths))


def test_the_personal_file_wins(site):
    write(site["install"] / env_file.SITE_NAME, "PGHOST=site\n")
    write(site["user"], "PGHOST=personal\n")

    used, _ = env_file.load()

    assert used == site["user"]
    assert os.environ["PGHOST"] == "personal"


def test_the_install_directory_is_used_when_there_is_no_personal_file(site):
    """이 기능의 요점 - 홈에 아무것도 안 만든 사람이 그냥 붙어야 한다."""
    write(site["install"] / env_file.SITE_NAME, "PGHOST=site\n")

    used, _ = env_file.load()

    assert used == site["install"] / env_file.SITE_NAME
    assert os.environ["PGHOST"] == "site"


def test_nothing_found_returns_the_places_it_looked(site):
    used, searched = env_file.load()

    assert used is None
    assert site["user"] in searched


# --------------------------------------------------------------------------
# 환경변수로 넣는 방식
# --------------------------------------------------------------------------


def test_an_existing_variable_is_not_overwritten(site, monkeypatch):
    """PGPASSWORD=x genviewer 처럼 한 번만 다르게 주는 것이 되어야 한다."""
    write(site["install"] / env_file.SITE_NAME, "PGHOST=file\nPGPORT=1\n")
    monkeypatch.setenv("PGHOST", "explicit")

    env_file.load()

    assert os.environ["PGHOST"] == "explicit"
    assert os.environ["PGPORT"] == "1"


def test_an_empty_file_is_skipped(site):
    """주석만 있는 파일 때문에 뒤 후보를 못 보면 안 된다."""
    write(site["user"], "# 아직 안 채움\n")
    write(site["install"] / env_file.SITE_NAME, "PGHOST=site\n")

    used, _ = env_file.load()

    assert used == site["install"] / env_file.SITE_NAME


def test_a_broken_file_names_itself(site):
    path = write(site["install"] / env_file.SITE_NAME, "PGHOST=h\n쓰레기\n")

    with pytest.raises(RuntimeError, match="쓰레기|Line"):
        env_file.load()
    assert path.is_file()


def test_a_utf8_bom_file_is_read(site):
    """PowerShell 5.1 의 -Encoding utf8 과 메모장의 'UTF-8 (BOM)' 이 BOM 을 붙인다.

    BOM 이 첫 키에 붙어 남으면 눈에 안 보이는 문자 때문에 앱이 뜨지 않는다.
    """
    path = site["install"] / env_file.SITE_NAME
    path.write_bytes(b"\xef\xbb\xbfPGHOST=10.1.2.3\nPGPORT=55433\n")

    used, _ = env_file.load()

    assert used == path
    assert os.environ["PGHOST"] == "10.1.2.3"
    assert os.environ["PGPORT"] == "55433"


def test_a_cp949_file_is_reported_as_encoding(site):
    """한국어 윈도우 메모장이 이렇게 저장한다. UnicodeDecodeError 만 나오면 원인을 모른다."""
    path = site["install"] / env_file.SITE_NAME
    path.write_bytes("# 주석\nPGHOST=h\n".encode("cp949"))

    with pytest.raises(RuntimeError, match="UTF-8"):
        env_file.load()


def test_libpq_env_present(monkeypatch):
    assert not env_file.libpq_env_present()
    monkeypatch.setenv("PGHOST", "h")
    assert env_file.libpq_env_present()


# --------------------------------------------------------------------------
# 권한 - 비밀번호가 같은 파일에 들어가므로
# --------------------------------------------------------------------------

posix_only = pytest.mark.skipif(
    sys.platform == "win32", reason="윈도우에는 유닉스 권한이 없어 chmod 가 의미 없다"
)


@posix_only
def test_a_world_readable_file_with_a_password_is_refused(site):
    """libpq 는 이 파일을 검사해 주지 않는다(자기 passfile 이 아니다)."""
    path = write(site["install"] / env_file.SITE_NAME, "PGPASSWORD=hunter2\n")
    path.chmod(0o644)

    with pytest.raises(RuntimeError, match="chmod 640"):
        env_file.load()


@posix_only
def test_a_group_readable_file_with_a_password_is_accepted(site):
    """팀이 같이 읽는 것은 의도한 구성이다. 막으면 이 기능이 무의미해진다."""
    path = write(site["install"] / env_file.SITE_NAME, "PGPASSWORD=hunter2\n")
    path.chmod(0o640)

    used, _ = env_file.load()

    assert used == path


@posix_only
def test_a_world_readable_file_without_a_password_is_fine(site):
    """서버 주소는 비밀이 아니다. 여기까지 막으면 과하다."""
    path = write(site["install"] / env_file.SITE_NAME, "PGHOST=h\n")
    path.chmod(0o644)

    used, _ = env_file.load()

    assert used == path


# --------------------------------------------------------------------------
# 설치 디렉터리 후보 - 배포본에서 엉뚱한 경로를 내놓으면 안 된다
# --------------------------------------------------------------------------


def _fake_module_at(base, *parts):
    """base 아래 주어진 경로에 env_file.py 가 있는 것처럼 꾸민다."""
    path = base.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return path


def test_a_source_checkout_is_a_candidate(monkeypatch, tmp_path):
    """개발 트리에서 직접 돌릴 때는 저장소 루트를 봐야 한다."""
    fake = _fake_module_at(tmp_path, "repo", "src", "genviewer", "service", "env_file.py")
    (tmp_path / "repo" / "pyproject.toml").write_text("", encoding="utf-8")
    monkeypatch.setattr(env_file, "__file__", str(fake))

    assert tmp_path / "repo" in env_file._site_roots()


def test_an_installed_package_does_not_invent_a_candidate(monkeypatch, tmp_path):
    """비-editable 설치에서 같은 계산은 venv/lib/python3.13 을 내놓는다.

    찾지는 못하니 동작은 같지만, 접속 실패 메시지의 '찾아본 곳' 에 그 줄이 뜨면
    거기 설정을 두라는 뜻으로 읽힌다.
    """
    fake = _fake_module_at(
        tmp_path, "venv", "lib", "python3.13", "site-packages",
        "genviewer", "service", "env_file.py",
    )
    monkeypatch.setattr(env_file, "__file__", str(fake))

    roots = env_file._site_roots()

    assert tmp_path / "venv" / "lib" / "python3.13" not in roots


# --------------------------------------------------------------------------
# tools/deploy.sh 배포본 - 런처가 GENDB_CONFIG 를 정하지 않으므로 앱이 스스로 찾는다
# --------------------------------------------------------------------------


@pytest.fixture
def deployed(tmp_path, monkeypatch):
    """<ROOT>/venv 가 sys.prefix 인 비-editable 배포본처럼 꾸민다.

    site fixture 와 달리 _site_roots 를 패치하지 않는다. sys.prefix 에서 배포 루트를
    계산하는 것까지 봐야 한다 - 런처가 GENDB_CONFIG 를 넘기지 않으면 그것이 공용
    파일을 찾는 유일한 길이다.
    """
    root = tmp_path / "deployed"
    monkeypatch.setattr(sys, "prefix", str(root / "venv"))
    fake = _fake_module_at(
        root, "venv", "lib", "python3.13", "site-packages",
        "genviewer", "service", "env_file.py",
    )
    monkeypatch.setattr(env_file, "__file__", str(fake))
    user = tmp_path / "home" / ".genviewer.env"
    monkeypatch.setattr(env_file, "USER_ENV", user)
    return {"root": root, "shared": root / env_file.SITE_NAME, "user": user}


def test_a_deployed_install_finds_the_shared_file(deployed):
    """홈에 아무것도 없는 사람이 <ROOT>/genviewer.env 로 붙어야 한다."""
    write(deployed["shared"], "PGHOST=shared\n")

    used, _ = env_file.load()

    assert used == deployed["shared"]
    assert os.environ["PGHOST"] == "shared"


def test_a_deployed_install_prefers_the_personal_file(deployed):
    """개인 파일이 있으면 그것 하나만 읽는다. 공용 파일의 키가 섞이지 않는다."""
    write(deployed["shared"], "PGHOST=shared\nPGPORT=1\n")
    write(deployed["user"], "PGHOST=personal\n")

    used, _ = env_file.load()

    assert used == deployed["user"]
    assert os.environ["PGHOST"] == "personal"
    assert "PGPORT" not in os.environ


def test_a_deployed_install_looks_in_readme_order(deployed):
    assert env_file.candidates() == [
        deployed["user"],
        deployed["root"] / "venv" / env_file.SITE_NAME,
        deployed["shared"],
    ]
