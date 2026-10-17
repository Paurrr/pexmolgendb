def skill_string(value) -> str:
    # SKILL 문자열 리터럴. 백슬래시를 먼저 바꿔야 따옴표 앞에 붙인 백슬래시가 다시 바뀌지 않는다
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def to_lisp_list_string(tabs: dict) -> str:
    parts = ["list(nil"]

    for key, value in tabs.items():
        if isinstance(value, (list, tuple)):
            inner = " ".join(skill_string(v) for v in value)
            parts.append(f"'{key} list({inner})")
        else:
            parts.append(f"'{key} {skill_string(value)}")

    parts.append(")")
    return " ".join(parts)
