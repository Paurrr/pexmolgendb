def to_lisp_list_string(tabs: dict) -> str:
    parts = ["list(nil"]

    for key, value in tabs.items():
        if isinstance(value, (list, tuple)):
            inner = " ".join(f'"{v}"' for v in value)
            parts.append(f"'{key} list({inner})")
        else:
            parts.append(f'\'{key} "{value}"')

    parts.append(")")
    return " ".join(parts)
