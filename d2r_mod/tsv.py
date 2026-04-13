"""Read/write D2R .txt files (tab-separated, UTF-8 with optional BOM)."""


def read_tsv(content: str) -> list[dict[str, str]]:
    """Parse TSV content into a list of row dicts."""
    content = content.lstrip("\ufeff")
    content = content.replace("\r\n", "\n")
    lines = content.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    if not lines:
        return []
    if not lines[0].strip():
        return []
    headers = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        if not line:
            continue
        values = line.split("\t")
        while len(values) < len(headers):
            values.append("")
        row = dict(zip(headers, values[:len(headers)]))
        for i in range(len(headers), len(values)):
            row[f"_extra_{i}"] = values[i]
        rows.append(row)
    return rows


def read_tsv_file(path: str) -> list[dict[str, str]]:
    """Read a .txt file and parse as TSV."""
    with open(path, "r", encoding="utf-8") as f:
        return read_tsv(f.read())


def write_tsv(rows: list[dict[str, str]], headers: list[str] | None = None) -> str:
    """Serialize row dicts back to TSV content. Output uses \\r\\n line endings."""
    if not rows and not headers:
        return ""
    if headers is None:
        headers = list(rows[0].keys())
    lines = ["\t".join(headers)]
    for row in rows:
        lines.append("\t".join(row.get(h, "") for h in headers))
    return "\r\n".join(lines) + "\r\n"


def write_tsv_file(path: str, rows: list[dict[str, str]],
                   headers: list[str] | None = None) -> None:
    """Write row dicts to a .txt file as TSV."""
    import os
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(write_tsv(rows, headers))
