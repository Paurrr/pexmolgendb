"""CSV import 가 셀 안의 토큰을 하나도 잃지 않는지 고정하는 테스트.

원본 규칙은 molgen 이다. genMOLDB_config.il 의
pexGenDB_GenDev_Get_Header_Type() 이 컬럼마다 변환 타입을 선언하고
genMOLDB_csv.il:399-409 가 그것을 구현한다. CSV_COLUMNS.md §4 가 특히 명시적이다:

    셀 = `이름 값...` — 첫 토큰이 파라미터 이름, 나머지 전체가 값 하나다
    (공백 유지: `grLayer RX Only` → 값 "RX Only").

예전 임포터는 타입과 무관하게 전부 공백으로 쪼갠 뒤 컬럼 수만큼 잘라내서
"Only" 를 조용히 버렸다. export 는 `" ".join` 이라 맞게 나갔기 때문에,
내보냈다 다시 읽을 때마다 값이 깎여 나갔다.
"""

import csv

import pytest

from genviewer.service.repo.device import DeviceRepository
from genviewer.service.repo.io import IORepository, split_cell
from genviewer.service.repo.parameter import ParameterRepository
from genviewer.service.repo.process import ProcessRepository

# --------------------------------------------------------------------------
# split_cell 단위 테스트 — DB 없이 돈다.
# --------------------------------------------------------------------------

LOSSLESS_CASES = [
    # (셀, 컬럼 수, parse, row_per_token)
    ("grLayer RX Only", 2, "parseStringToVariableValue", False),
    ("nfin 1", 2, "parseStringToVariableValue", False),
    ("NFIN 1:2", 2, "parseStringToVariableValue", False),
    ("NW drawing", 2, "parseStringToVariableValue", False),
    ("w 1.5u * nf", 2, "parseStringToVariableValue", False),
    ("my long suffix", 1, "string", False),
    ("NFIN nfin ALL", 1, "parseString", True),
    ("NW:drawing RX:drawing 0.2|0.3:0.1 SHAPE:ring@0.5 SPLIT:inst", 4,
     "parseString", False),
    ("LAYER:NW:drawing REF:BBOX SPACEY:0.2|0.3 SPACEX:0.1 SHAPE:extend WIDTH:0.5",
     4, "parseString", False),
    ("RXFGR RX:drawing 0.5:0.5 VSS SHAPE:ring SPLIT:inst AddPFGRParam", 5,
     "parseString", False),
]


@pytest.mark.parametrize("cell,n,parse,per_token", LOSSLESS_CASES)
def test_split_cell_loses_no_token(cell, n, parse, per_token):
    """어떤 타입이든 셀의 토큰이 사라지면 안 된다.

    export 가 컬럼을 공백 하나로 다시 이어 붙이므로(io.fetch_export_data),
    토큰 순서가 그대로 남아 있으면 왕복이 원문과 같아진다.
    """
    rows = split_cell(cell, n, parse, per_token)
    assert all(len(r) == n for r in rows), "행마다 컬럼 수가 맞아야 한다"

    rejoined = " ".join(" ".join(r) for r in rows)
    assert rejoined.split() == cell.split()


def test_split_cell_keeps_spaces_inside_the_value():
    """공백은 값 안에서 살아 있어야 한다 — 토큰이 남아 있는 것만으로는 부족하다."""
    assert split_cell("grLayer RX Only", 2, "parseStringToVariableValue") == [
        ["grLayer", "RX Only"]
    ]


def test_split_cell_pads_a_short_cell():
    assert split_cell("grLayer", 2, "parseStringToVariableValue") == [["grLayer", ""]]


def test_split_cell_gives_one_row_per_token():
    """ForcedInstSchParam 셀은 토큰 목록이다 (CSV_COLUMNS.md §8a)."""
    assert split_cell("NFIN nfin ALL", 1, "parseString", True) == [
        ["NFIN"],
        ["nfin"],
        ["ALL"],
    ]


# --------------------------------------------------------------------------
# 왕복 테스트 — DB 필요.
# --------------------------------------------------------------------------

BASE_HEADERS = ["CellType", "CdsLibName", "InstCellName"]
BASE_ROW = ["NFET", "sf2p", "nfet_b"]


def _round_trip(db, tmp_path, extra_headers, extra_values):
    """CSV 한 줄을 넣었다가 export 로 다시 꺼낸다. {헤더: [셀...]} 을 준다."""
    path = tmp_path / "in.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(BASE_HEADERS + extra_headers)
        w.writerow(BASE_ROW + extra_values)

    io = IORepository(db)
    assert io.import_data(str(path)) == 1, "import 가 device 를 하나 만들지 않았다"

    pid = ProcessRepository(db).get_id("sf2p")
    devices = DeviceRepository(db).fetch_devices_by_process(pid)
    info = [{**d, "process_id": pid, "process_name": "sf2p"} for d in devices]

    headers, rows = io.fetch_export_data(info)
    assert len(rows) == 1
    out: dict[str, list[str]] = {}
    for name, cell in zip(headers, rows[0], strict=True):
        out.setdefault(name, []).append(cell)
    return out


def test_a_value_with_a_space_survives_the_round_trip(db, tmp_path):
    """신고된 버그: 'RX Only' 가 'RX' 로 잘렸다."""
    out = _round_trip(db, tmp_path, ["AddFGRParam"], ["grLayer RX Only"])
    assert out["AddFGRParam"] == ["grLayer RX Only"]


def test_every_variable_value_column_keeps_its_spaces(db, tmp_path):
    """같은 원인이 걸려 있던 나머지 컬럼들."""
    cells = {
        "AddPFGRParam": "grLayer RX Only",
        "AddNFGRParam": "grLayer NW Only",
        "PreDefineInstSchParamValue": "w 1.5u * nf",
        "PostDefineInstSchParamValue": "l 20n + dl",
        "SuffixCellName": "my long suffix",
    }
    out = _round_trip(db, tmp_path, list(cells), list(cells.values()))
    for header, cell in cells.items():
        assert out[header] == [cell], f"{header} 가 잘렸다"


def test_positional_columns_keep_their_option_tokens(db, tmp_path):
    """AddLayer/AddFGR 는 컬럼 수보다 토큰이 많다. 남는 토큰을 버리면 안 된다.

    고정 4·5 컬럼이라 옵션 키가 마지막 컬럼에 뭉쳐 들어가지만, export 가
    공백으로 다시 이어 붙이므로 molgen 이 받는 셀은 원문 그대로다.
    """
    add_layer = "NW:drawing RX:drawing 0.2|0.3:0.1 SHAPE:ring@0.5 SPLIT:inst"
    add_fgr = "RXFGR RX:drawing 0.5:0.5 VSS SHAPE:ring SPLIT:inst AddPFGRParam"
    out = _round_trip(db, tmp_path, ["AddLayer", "AddFGR"], [add_layer, add_fgr])
    assert out["AddLayer"] == [add_layer]
    assert out["AddFGR"] == [add_fgr]


def test_forced_inst_sch_param_explodes_into_columns(db, tmp_path):
    """토큰 목록 셀은 행으로 펼쳐졌다가 컬럼들로 나간다.

    molgen 의 pexGenDB_GenDev_GetForcedParams (genMOLDB_csv.il:711-725) 가
    동명 컬럼들을 다시 평탄화하므로 의미가 같다.
    """
    out = _round_trip(db, tmp_path, ["ForcedInstSchParam"], ["NFIN nfin ALL"])
    assert out["ForcedInstSchParam"] == ["NFIN", "nfin", "ALL"]


def test_repeated_columns_become_repeated_rows(db, tmp_path):
    """같은 이름의 컬럼 반복이 항목 반복이다 (CSV_COLUMNS.md §0)."""
    out = _round_trip(
        db,
        tmp_path,
        ["InstTerm", "InstTerm", "InstTerm"],
        ["DRN d", "GATE g", "SRC s"],
    )
    assert out["InstTerm"] == ["DRN d", "GATE g", "SRC s"]


def test_identical_rows_are_not_deduplicated(db, tmp_path):
    """같은 자식 행이 둘 있으면 둘 다 남아야 한다.

    회귀 방지: 임포터가 drop_duplicates 를 걸어 둘 중 하나를 조용히 지웠다.
    """
    out = _round_trip(
        db, tmp_path, ["AddFGRParam", "AddFGRParam"], ["grLayer RX", "grLayer RX"]
    )
    assert out["AddFGRParam"] == ["grLayer RX", "grLayer RX"]


def test_a_value_that_looks_like_a_missing_marker_survives(db, tmp_path):
    """값이 'NA' 인 셀은 정상적인 값이다.

    회귀 방지: pandas 의 기본 na 목록이 NA/NULL/None 을 NaN 으로 바꿔서
    셀이 통째로 사라졌다.
    """
    out = _round_trip(db, tmp_path, ["AddFGRParam"], ["grLayer NA"])
    assert out["AddFGRParam"] == ["grLayer NA"]


def test_a_numeric_looking_column_survives(db, tmp_path):
    """숫자만 있는 컬럼도 문자열로 다뤄야 한다.

    회귀 방지: pandas 가 int64 로 추론하면 셀에 .strip() 을 걸 수 없어
    AttributeError 로 그 셀이 통째로 버려졌다.
    """
    out = _round_trip(db, tmp_path, ["SuffixCellName"], ["123"])
    assert out["SuffixCellName"] == ["123"]


# --------------------------------------------------------------------------
# 이름 중복 — CSV 행 하나가 device 하나다.
# --------------------------------------------------------------------------


def _write_csv(path, headers, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for row in rows:
            w.writerow(row)
    return str(path)


def _devices(db, process="sf2p"):
    pid = ProcessRepository(db).get_id(process)
    return DeviceRepository(db).fetch_devices_by_process(pid)


def test_rows_with_the_same_name_become_separate_devices(db, tmp_path):
    """같은 (CdsLibName, InstCellName) 행 두 개는 device 두 개다.

    신고된 버그: ON CONFLICT (process_id, name) 이 두 행을 한 device 로 묶었고,
    자식 행 삭제가 행 루프 뒤에 한 번만 돌아서 두 행의 내용이 한 탭에 섞였다.
    """
    path = _write_csv(
        tmp_path / "dup.csv",
        BASE_HEADERS + ["AddFGRParam"],
        [
            ["NFET", "sf2p", "nfet_b", "grLayer RX"],
            ["PFET", "sf2p", "nfet_b", "grLayer NW"],
        ],
    )
    assert IORepository(db).import_data(path) == 2

    devices = _devices(db)
    assert [d["name"] for d in devices] == ["nfet_b", "nfet_b"]
    assert len({d["id"] for d in devices}) == 2
    # celltype 도 합쳐지지 않는다. 예전에는 뒤 행이 앞 행을 덮어썼다.
    assert sorted(d["celltype"] for d in devices) == ["NFET", "PFET"]

    par = ParameterRepository(db)
    columns = ["parameter_name", "value"]
    got = [
        [
            f"{r['parameter_name']} {r['value']}"
            for r in par.fetch_by_device("add_fgr_params", columns, d["id"])
        ]
        for d in devices
    ]
    assert got == [["grLayer RX"], ["grLayer NW"]], "두 행의 자식 행이 섞였다"


def test_importing_the_same_file_twice_adds_again(db, tmp_path):
    """재임포트는 멱등하지 않다 — 행마다 device 를 새로 만든다.

    받아들인 대가라 문서가 아니라 테스트로 고정한다. 부르는 쪽이 만들어진
    개수를 사용자에게 보여줘야 한다.
    """
    path = _write_csv(tmp_path / "a.csv", BASE_HEADERS, [BASE_ROW])
    io = IORepository(db)
    assert io.import_data(path) == 1
    assert io.import_data(path) == 1
    assert [d["name"] for d in _devices(db)] == ["nfet_b", "nfet_b"]


def test_a_later_import_does_not_wipe_an_earlier_devices_tabs(db, tmp_path):
    """먼저 넣은 device 의 자식 행은 다음 임포트가 건드리지 않는다.

    회귀 방지: 예전 삭제 루프는 CSV 에 없는 섹션까지 포함해 자식 테이블 14개를
    전부 비웠다. AddLayer 컬럼이 빠진 CSV 를 넣으면 기존 add_layers 가 사라졌다.
    """
    io = IORepository(db)
    first = _write_csv(
        tmp_path / "1.csv",
        BASE_HEADERS + ["AddLayer"],
        [BASE_ROW + ["NW:drawing RX:drawing 0.2 SHAPE:ring"]],
    )
    assert io.import_data(first) == 1
    first_id = _devices(db)[0]["id"]

    second = _write_csv(
        tmp_path / "2.csv", BASE_HEADERS + ["AddFGRParam"], [BASE_ROW + ["grLayer RX"]]
    )
    assert io.import_data(second) == 1

    kept = ParameterRepository(db).fetch_by_device(
        "add_layers", ["layer_name_purpose"], first_id
    )
    assert len(kept) == 1, "먼저 넣은 device 의 자식 행이 사라졌다"


def test_a_missing_file_raises():
    """예전에는 조용히 False 를 돌려줘서 사용자가 'Fail' 만 봤다. DB 가 필요 없다."""
    with pytest.raises(FileNotFoundError):
        IORepository(None).import_data("이런 파일은 없다.csv")


def test_a_csv_without_the_required_columns_raises(db, tmp_path):
    """원인이 올라와야 메시지 박스에 뭐라도 쓸 수 있다.

    회귀 방지: import_data 가 모든 예외를 삼키고 print 했는데, 배포본에는
    터미널이 없어서 원인이 아무 데도 남지 않았다.
    """
    path = _write_csv(tmp_path / "bad.csv", ["CellType", "CdsLibName"], [["NFET", "sf2p"]])
    with pytest.raises(KeyError):
        IORepository(db).import_data(path)


def test_a_failed_import_leaves_no_process_behind(db, tmp_path):
    """불러오기는 트랜잭션 하나다. 실패하면 그 안에서 만든 process 도 남지 않는다."""
    path = _write_csv(tmp_path / "bad.csv", ["CellType", "CdsLibName"], [["NFET", "sf9z"]])
    with pytest.raises(KeyError):
        IORepository(db).import_data(path)
    assert ProcessRepository(db).list_all() == []


# --------------------------------------------------------------------------
# CdsLibName → process id
# --------------------------------------------------------------------------


def _process_id_of(db, name):
    with db.connection() as conn:
        return IORepository._process_id(conn.cursor(), name)


def test_process_id_creates_a_new_process_once(db):
    created = _process_id_of(db, " sf9z ")
    assert created is not None
    assert _process_id_of(db, "sf9z") == created
    assert ProcessRepository(db).list_all() == ["sf9z"]


def test_process_id_finds_an_existing_process(db):
    existing = ProcessRepository(db).get_or_create_id("sf2p")
    assert _process_id_of(db, "sf2p") == existing
    assert ProcessRepository(db).list_all() == ["sf2p"]


@pytest.mark.parametrize("blank", ["", "   ", float("nan"), None])
def test_process_id_is_none_for_a_blank_name(db, blank):
    assert _process_id_of(db, blank) is None
    assert ProcessRepository(db).list_all() == []
