import re


def normalize_value(value) -> str:
    return str(value).strip() if value is not None else ""


def allowed_items(field_config: dict, celltype: str | None = None) -> list[str]:
    items = field_config.get("items") or []
    by_celltype = field_config.get("items_by_celltype") or {}
    if celltype and celltype in by_celltype:
        return by_celltype[celltype]
    return items


def validate_field_value(
    value,
    field_config: dict,
    *,
    celltype: str | None = None,
    label: str = "Value",
) -> tuple[bool, str]:
    text = normalize_value(value)

    if field_config.get("required", False) and not text:
        return False, f"{label} is required."

    if not text:
        return True, ""

    items = allowed_items(field_config, celltype)
    if field_config.get("strict", False) and items and text not in items:
        return False, f"{label} must be one of: {', '.join(items)}."

    syntax = field_config.get("syntax") or {}
    if syntax.get("kind") == "layer_purpose":
        ok, message = _validate_layer_purpose(text, syntax, label)
        if not ok:
            return False, message

    pattern = field_config.get("pattern")
    if pattern and not re.fullmatch(pattern, text):
        return False, field_config.get(
            "message", f"{label} has an invalid format."
        )

    return True, ""


def _validate_layer_purpose(
    text: str, syntax: dict, label: str
) -> tuple[bool, str]:
    separator = syntax.get("separator", ":")
    purposes = syntax.get("purposes") or []
    example = syntax.get("example", f"NW{separator}drawing")

    # 참조 슬롯에는 LPP 대신 BBOX 가 올 수 있다 (CSV_COLUMNS.md 1a/2a).
    # 구분자가 없으니 아래 검사를 그대로 태우면 유효한 값이 거부된다.
    bare = syntax.get("bare_values") or []
    if any(text.casefold() == b.casefold() for b in bare):
        return True, ""

    if text.count(separator) != 1:
        hint = f", or one of: {', '.join(bare)}" if bare else ""
        return False, (
            f"{label} must use Layer{separator}Purpose, e.g. {example}{hint}."
        )

    layer, purpose = [part.strip() for part in text.split(separator, 1)]
    if not layer or not purpose:
        return False, f"{label} must include both layer and purpose."

    if purposes and purpose not in purposes:
        return False, f"Purpose must be one of: {', '.join(purposes)}."

    return True, ""
