def parse(raw: str) -> tuple[str, str]:
    # 앞뒤 큰따옴표 제거
    if raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1]
    if raw.startswith("[DeviceList]"):
        return "DeviceList", raw[len("[DeviceList]") :]
    if raw.startswith("[LibraryList]"):
        return "LibraryList", raw[len("[LibraryList]") :]
    return "Text", raw


def make_filter_cell_has_symbol_layout(process_name: str) -> str:
    p = process_name.strip().lower()
    return f'filterCellHasSymbolLayout(list("{p}" "{p}_esd"))'


def make_library_list_request() -> str:
    return ""


def to_device_state(payload: str) -> dict:
    """
    payload 예: 'dev1,S1,L1,libA; dev2,S2,L2,libB; ...'
    반환: {name: {"S": s, "L": l, "library_name": lib}, ...}
    """
    out = {}
    for item in payload.split(";"):
        item = item.strip()
        if not item:
            continue
        parts = (item.split(",") + [None, None, None, None])[:4]
        name, s, l, lib = parts
        out[name] = {"S": s, "L": l, "library_name": lib}
    return out


def to_library_list(payload: str) -> list[str]:
    libs = []
    seen = set()
    for item in payload.replace("\n", ";").split(";"):
        name = item.strip().strip('"')
        if not name or name in seen:
            continue
        libs.append(name)
        seen.add(name)
    return libs
