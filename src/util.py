def _extract_title_from_markdown(document: str) -> str:
    for line in document.splitlines():
        cleaned_line = line.strip()
        if cleaned_line.startswith("#"):
            return cleaned_line.lstrip("#").strip()
    return ""


def _extract_excerpt_from_markdown(document: str, max_length: int = 400) -> str:
    lines = []
    for line in document.splitlines():
        cleaned_line = line.strip()
        if not cleaned_line:
            continue
        if cleaned_line.startswith("#"):
            continue
        if cleaned_line.startswith("<!--") and cleaned_line.endswith("-->"):
            continue
        lines.append(cleaned_line)

    excerpt = " ".join(lines)
    if len(excerpt) <= max_length:
        return excerpt

    return excerpt[: max_length - 3].rstrip() + "..."
