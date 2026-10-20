"""Parsers for detected formats: HTML-table .xls first (the actual corpus)."""
from __future__ import annotations

import re

from app.ingestion.constants import (
    FMT_CSV,
    FMT_HTML_TABLE,
    FMT_NATIVE_XLS,
    FMT_PDF,
    FMT_UNKNOWN,
    FMT_XLSX,
)


class ParsedTable:
    def __init__(self, headers: list[str], rows: list[list[str]], meta: dict):
        self.headers = headers
        self.rows = rows
        self.meta = meta


class ParsedPdf:
    def __init__(self, text: str, page_count: int, meta: dict):
        self.text = text
        self.page_count = page_count
        self.meta = meta


def parse_table(path, detected_format: str) -> ParsedTable:
    if detected_format == FMT_HTML_TABLE:
        return _parse_html_table(path)
    if detected_format == FMT_NATIVE_XLS:
        return _parse_native_xls(path)
    if detected_format == FMT_CSV:
        return _parse_csv(path)
    if detected_format == FMT_XLSX:
        raise ValueError("xlsx sheet schema not validated by this parser version")
    raise ValueError(f"unsupported content format: {detected_format}")


def _strip_tags(fragment: str) -> str:
    return re.sub(r"<[^>]+>", "", fragment).replace("&amp;", "&").strip()


def _parse_html_table(path) -> ParsedTable:
    """Parse the MCX 'DateWise' reports: HTML tables saved with an .xls extension."""
    html = path.read_bytes().decode("utf-8", errors="replace")

    header_cells = re.findall(r"<th[^>]*>(.*?)</th>", html, re.S | re.I)
    headers = [_strip_tags(h) for h in header_cells]
    if not headers:
        raise ValueError("no HTML table headers found")

    body_rows: list[list[str]] = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)
        if tds:
            body_rows.append([_strip_tags(td) for td in tds])

    if not body_rows:
        raise ValueError("table has no body rows (empty report)")

    return ParsedTable(headers, body_rows, {"parser": "html_table_v1"})


def _parse_native_xls(path) -> ParsedTable:
    import xlrd  # deferred import: only needed for genuine OLE2 workbooks

    book = xlrd.open_workbook(str(path), on_demand=True)
    sheet = book.sheet_by_index(0)

    def cell_str(r, c) -> str:
        v = sheet.cell_value(r, c)
        return "" if v is None else str(v)

    if sheet.nrows == 0:
        raise ValueError("empty sheet")
    headers = [cell_str(0, c).strip() for c in range(sheet.ncols)]
    rows = [[cell_str(r, c) for c in range(sheet.ncols)] for r in range(1, sheet.nrows)]
    if not rows:
        raise ValueError("sheet has no body rows")
    return ParsedTable(headers, rows, {"parser": "xlrd_v1", "sheet": sheet.name})


def _parse_csv(path) -> ParsedTable:
    import csv
    import io

    text = path.read_bytes().decode("utf-8", errors="replace")
    sample = io.StringIO(text[:8192]).readline()
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        headers = [h.strip() for h in next(reader)]
    except StopIteration:
        raise ValueError("empty CSV file")
    rows = [row for row in reader]
    if not rows:
        raise ValueError("CSV has no body rows")
    return ParsedTable(headers, rows, {"parser": "csv_v1", "delimiter": delimiter})


def parse_pdf(path) -> ParsedPdf:
    from pypdf import PdfReader  # deferred import

    reader = PdfReader(str(path))
    page_count = len(reader.pages)
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    if not text.strip():
        raise ValueError("pdf text extraction produced no text (probably scanned)")
    return ParsedPdf(text, page_count, {"parser": "pypdf_v1"})
