from datetime import datetime


AUTHOR = "Gabriel Esteban Castañeda Barreto"


def signature_html():
    return (
        "<div style='margin-top:22px;padding:14px 16px;border:1px solid #2b332e;"
        "border-radius:8px;background:#171c19;color:#f5f4ef;'>"
        "<div style='font-size:12px;color:#ff4b1f;font-weight:800;'>AUTOR</div>"
        f"<div style='font-size:16px;font-weight:900;'>{AUTHOR}</div>"
        "</div>"
    )


def add_streamlit_signature(st):
    st.markdown(signature_html(), unsafe_allow_html=True)


def _clean(value):
    text = "" if value is None else str(value)
    replacements = {
        "≤": "<=",
        "≥": ">=",
        "≈": "~=",
        "°": " deg",
        "–": "-",
        "—": "-",
        "’": "'",
        "“": '"',
        "”": '"',
        "\n": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _wrap(text, width=95):
    words = _clean(text).split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        if len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current += " " + word
    lines.append(current)
    return lines


def _pdf_text(text):
    encoded = _clean(text).encode("latin-1", errors="replace").decode("latin-1")
    return encoded.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _append_wrapped(lines, text, prefix="", width=95):
    for wrapped in _wrap(text, width):
        lines.append(prefix + wrapped)


def _paginate(lines, max_lines=48):
    pages = []
    for index in range(0, len(lines), max_lines):
        pages.append(lines[index:index + max_lines])
    return pages or [[]]


def _build_pdf_document(title, pages):
    objects = []

    def add_object(content):
        objects.append(content)
        return len(objects)

    page_refs = []
    content_refs = []
    font_ref = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for page_lines in pages:
        commands = ["BT", "/F1 16 Tf", "50 800 Td", f"({_pdf_text(title)}) Tj"]
        commands += ["/F1 9 Tf", "0 -16 Td", f"({_pdf_text('Autor: ' + AUTHOR)}) Tj"]
        commands += ["/F1 8 Tf", "0 -13 Td", f"({_pdf_text('Generado: ' + datetime.now().strftime('%Y-%m-%d %H:%M'))}) Tj"]
        commands += ["/F1 10 Tf", "0 -24 Td"]
        for idx, line in enumerate(page_lines):
            if idx:
                commands.append("0 -13 Td")
            commands.append(f"({_pdf_text(line)}) Tj")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", errors="replace")
        content_ref = add_object(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
        content_refs.append(content_ref)
        page_refs.append(None)

    pages_ref = len(objects) + len(pages) + 1
    for index, content_ref in enumerate(content_refs):
        page_ref = add_object(
            (
                f"<< /Type /Page /Parent {pages_ref} 0 R /MediaBox [0 0 612 842] "
                f"/Resources << /Font << /F1 {font_ref} 0 R >> >> "
                f"/Contents {content_ref} 0 R >>"
            ).encode("ascii")
        )
        page_refs[index] = page_ref

    kids = " ".join(f"{ref} 0 R" for ref in page_refs)
    actual_pages_ref = add_object(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_refs)} >>".encode("ascii"))
    catalog_ref = add_object(f"<< /Type /Catalog /Pages {actual_pages_ref} 0 R >>".encode("ascii"))

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, content in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(content)
        pdf.extend(b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_ref} 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(pdf)


def build_technical_pdf(title, sections, tables=None):
    lines = []
    for section_title, section_lines in sections:
        lines.append(_clean(section_title).upper())
        for line in section_lines:
            _append_wrapped(lines, line, "  ")
        lines.append("")

    for table in tables or []:
        columns = table.get("columns", [])
        rows = table.get("rows", [])
        if not columns or not rows:
            continue
        lines.append(_clean(table.get("title", "Tabla")).upper())
        _append_wrapped(lines, " | ".join(columns), "  ", 110)
        for row in rows:
            _append_wrapped(lines, " | ".join(_clean(value) for value in row), "  ", 110)
        lines.append("")

    lines.append("FIRMA DEL AUTOR")
    lines.append(f"  {AUTHOR}")
    return _build_pdf_document(title, _paginate(lines))
