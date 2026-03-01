"""XLSX parser for history-ingest spreadsheet uploads."""

from __future__ import annotations

import csv
from io import BytesIO, StringIO
from pathlib import PurePosixPath
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from app.features.history_ingest.infrastructure.parsers.models import FileContent
from app.features.history_ingest.schemas.responses import ParsedFilePayload

SPREADSHEET_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {
    "office": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "package": "http://schemas.openxmlformats.org/package/2006/relationships",
}


class HistoryExcelParser:
    """Extract row dictionaries from the first visible worksheet in an XLSX file."""

    extension = ".xlsx"
    parsed_kind = "spreadsheet"

    def parse(self, content: FileContent) -> ParsedFilePayload:
        """Return workbook rows normalized into the same shape as CSV parsing."""

        try:
            with ZipFile(BytesIO(content.raw_bytes)) as workbook_archive:
                shared_strings = self._load_shared_strings(workbook_archive)
                sheet_path = self._find_first_visible_sheet_path(workbook_archive)
                headers, rows = self._load_sheet_rows(
                    workbook_archive,
                    sheet_path=sheet_path,
                    shared_strings=shared_strings,
                )
        except (BadZipFile, ElementTree.ParseError, KeyError) as exc:
            raise ValueError(f"Failed to parse XLSX workbook: {content.file_name}") from exc

        return ParsedFilePayload(
            file_name=content.file_name,
            extension=content.extension,
            content_type=content.content_type,
            size_bytes=content.size_bytes,
            parsed_kind=self.parsed_kind,
            raw_text=self._build_csv_text(headers, rows),
            structured_data=rows,
            row_count=len(rows),
            warnings=[],
        )

    def _find_first_visible_sheet_path(self, workbook_archive: ZipFile) -> str:
        workbook_xml = ElementTree.fromstring(workbook_archive.read("xl/workbook.xml"))
        workbook_rels_xml = ElementTree.fromstring(
            workbook_archive.read("xl/_rels/workbook.xml.rels")
        )
        relationship_targets = {
            relationship.attrib["Id"]: relationship.attrib["Target"]
            for relationship in workbook_rels_xml.findall("package:Relationship", REL_NS)
        }

        for sheet in workbook_xml.findall("main:sheets/main:sheet", SPREADSHEET_NS):
            if sheet.attrib.get("state") not in (None, "visible"):
                continue
            relationship_id = sheet.attrib.get(f"{{{REL_NS['office']}}}id")
            if not relationship_id:
                continue
            target = relationship_targets.get(relationship_id)
            if target:
                return self._resolve_workbook_target(target)
        raise ValueError("Workbook does not contain a visible worksheet.")

    def _load_sheet_rows(
        self,
        workbook_archive: ZipFile,
        *,
        sheet_path: str,
        shared_strings: list[str],
    ) -> tuple[list[str], list[dict[str, str]]]:
        sheet_xml = ElementTree.fromstring(workbook_archive.read(sheet_path))
        parsed_rows: list[list[str]] = []
        for row in sheet_xml.findall("main:sheetData/main:row", SPREADSHEET_NS):
            cell_values: dict[int, str] = {}
            max_column_index = 0
            for cell in row.findall("main:c", SPREADSHEET_NS):
                column_index = self._column_index_from_reference(cell.attrib.get("r", "A1"))
                max_column_index = max(max_column_index, column_index)
                cell_values[column_index] = self._read_cell_value(
                    cell,
                    shared_strings=shared_strings,
                )
            if max_column_index == 0:
                continue
            parsed_rows.append(
                [
                    cell_values.get(column_index, "")
                    for column_index in range(1, max_column_index + 1)
                ]
            )

        if not parsed_rows:
            return [], []

        header_row_index = next(
            (
                index
                for index, row_values in enumerate(parsed_rows)
                if any(cell.strip() for cell in row_values)
            ),
            None,
        )
        if header_row_index is None:
            return [], []

        headers = parsed_rows[header_row_index]
        rows: list[dict[str, str]] = []
        for row_values in parsed_rows[header_row_index + 1 :]:
            rows.append(
                {
                    header: row_values[index] if index < len(row_values) else ""
                    for index, header in enumerate(headers)
                }
            )
        return headers, rows

    def _load_shared_strings(self, workbook_archive: ZipFile) -> list[str]:
        try:
            shared_strings_xml = workbook_archive.read("xl/sharedStrings.xml")
        except KeyError:
            return []

        shared_strings_root = ElementTree.fromstring(shared_strings_xml)
        return [
            "".join(text for text in string_item.itertext())
            for string_item in shared_strings_root.findall("main:si", SPREADSHEET_NS)
        ]

    def _read_cell_value(
        self,
        cell: ElementTree.Element,
        *,
        shared_strings: list[str],
    ) -> str:
        cell_type = cell.attrib.get("t")
        if cell_type == "inlineStr":
            inline_string = cell.find("main:is", SPREADSHEET_NS)
            return (
                "".join(text for text in inline_string.itertext())
                if inline_string is not None
                else ""
            )

        value = cell.findtext("main:v", default="", namespaces=SPREADSHEET_NS)
        if cell_type == "s" and value:
            try:
                return shared_strings[int(value)]
            except (IndexError, ValueError):
                return ""
        return value

    def _resolve_workbook_target(self, target: str) -> str:
        normalized_target = PurePosixPath(target.lstrip("/"))
        if normalized_target.parts[:1] == ("xl",):
            return str(normalized_target)
        return str(PurePosixPath("xl") / normalized_target)

    def _column_index_from_reference(self, cell_reference: str) -> int:
        letters = "".join(character for character in cell_reference if character.isalpha()).upper()
        column_index = 0
        for letter in letters:
            column_index = (column_index * 26) + (ord(letter) - 64)
        return column_index

    def _build_csv_text(self, headers: list[str], rows: list[dict[str, str]]) -> str:
        if not headers:
            return ""

        buffer = StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(headers)
        for row in rows:
            writer.writerow([row.get(header, "") for header in headers])
        return buffer.getvalue()
