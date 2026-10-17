"""Virtuoso 로 보내는 SKILL 문자열을 고정하는 테스트(Qt·DB 없음).

SKILL 문자열 리터럴은 큰따옴표로 감싸고, 안에서는 `\\\\` 와 `\\"` 를 이스케이프로 읽는다.
값에 `"`·`\\` 가 있어도 넣은 값 그대로 Virtuoso 에 가야 한다(K13).
"""

import pytest

from genviewer.service.virtuoso_protocol import make_filter_cell_has_symbol_layout
from genviewer.utils.lisp import to_lisp_list_string


def _read_skill_strings(text: str) -> tuple[list[str], str]:
    """SKILL 코드에서 문자열 리터럴의 값들과, 리터럴을 `""` 로 바꾼 나머지 코드를 돌려준다.

    이 읽개가 푸는 이스케이프는 `\\\\` 와 `\\"` 뿐이다.
    다른 이스케이프나 닫히지 않은 따옴표는 실패다.
    """
    values = []
    code = []
    i = 0
    while i < len(text):
        if text[i] != '"':
            code.append(text[i])
            i += 1
            continue
        value = []
        i += 1
        while True:
            if i >= len(text):
                pytest.fail(f"닫히지 않은 문자열: {text!r}")
            ch = text[i]
            if ch == '"':
                i += 1
                break
            if ch == "\\":
                escaped = text[i + 1 : i + 2]
                if escaped not in ("\\", '"'):
                    pytest.fail(f"모르는 이스케이프 \\{escaped}: {text!r}")
                value.append(escaped)
                i += 2
                continue
            value.append(ch)
            i += 1
        values.append("".join(value))
        code.append('""')
    return values, "".join(code)


def test_list_string_keeps_quotes_and_backslashes_in_values():
    text = to_lisp_list_string({"InstTerm": ['a"b', "c\\d", "plain"], "Desc": 'x"y'})

    values, code = _read_skill_strings(text)
    assert values == ['a"b', "c\\d", "plain", 'x"y']
    assert code == "list(nil 'InstTerm list(\"\" \"\" \"\") 'Desc \"\" )"


def test_list_string_value_ending_with_a_backslash_closes_its_string():
    text = to_lisp_list_string({"InstTerm": ["a\\"], "Desc": "b\\"})

    values, code = _read_skill_strings(text)
    assert values == ["a\\", "b\\"]
    assert code == "list(nil 'InstTerm list(\"\") 'Desc \"\" )"


@pytest.mark.parametrize(
    ("process_name", "expected"),
    [
        ('My"Lib', ['my"lib', 'my"lib_esd']),
        ("Lib\\", ["lib\\", "lib\\_esd"]),
    ],
)
def test_filter_command_keeps_quotes_and_backslashes_in_the_process_name(process_name, expected):
    values, code = _read_skill_strings(make_filter_cell_has_symbol_layout(process_name))

    assert values == expected
    assert code == 'filterCellHasSymbolLayout(list("" ""))'


# -- 특수 문자가 없는 값은 바이트 단위로 지금과 같다 (수정 전 출력을 그대로 적었다) ----------


@pytest.mark.parametrize(
    ("tabs", "expected"),
    [
        (
            {"InstTerm": ["DRN d", "GATE g"], "Desc": "x"},
            'list(nil \'InstTerm list("DRN d" "GATE g") \'Desc "x" )',
        ),
        (
            {"CellType": "nfet", "InstSchParam": ("w 1u", "l 한글"), "Empty": [], "N": 3},
            'list(nil \'CellType "nfet" \'InstSchParam list("w 1u" "l 한글") '
            "'Empty list() 'N \"3\" )",
        ),
    ],
)
def test_list_string_without_special_characters_is_unchanged(tabs, expected):
    assert to_lisp_list_string(tabs) == expected


def test_filter_command_without_special_characters_is_unchanged():
    assert (
        make_filter_cell_has_symbol_layout(" SF2P ")
        == 'filterCellHasSymbolLayout(list("sf2p" "sf2p_esd"))'
    )
