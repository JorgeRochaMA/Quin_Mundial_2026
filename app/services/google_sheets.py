"""Thin Google Sheets gateway used by the repository layer."""

from __future__ import annotations

from typing import Any

import gspread
import pandas as pd
from gspread.exceptions import WorksheetNotFound
from gspread.utils import rowcol_to_a1

from utils.data import serialize_cell


class GoogleSheetsConfigError(RuntimeError):
    """Raised when Google Sheets credentials are missing or invalid."""


class GoogleSheetsService:
    """Read and write structured records in a Google Spreadsheet."""

    def __init__(self, spreadsheet_id: str, credentials_info: dict[str, Any]) -> None:
        if not spreadsheet_id:
            raise GoogleSheetsConfigError("Missing google_sheets.spreadsheet_id secret.")
        if not credentials_info:
            raise GoogleSheetsConfigError("Missing gcp_service_account secrets.")

        self.client = gspread.service_account_from_dict(credentials_info)
        self.spreadsheet = self.client.open_by_key(spreadsheet_id)

        # Local in-memory cache for the current Streamlit execution.
        # This reduces repeated worksheet/header lookups during the same run.
        self._worksheet_cache: dict[str, gspread.Worksheet] = {}
        self._headers_cache: dict[str, list[str]] = {}

    def get_worksheet(self, title: str, columns: list[str]) -> gspread.Worksheet:
        """Get or create a worksheet without repeatedly fetching all values."""
        if title in self._worksheet_cache:
            return self._worksheet_cache[title]

        try:
            worksheet = self.spreadsheet.worksheet(title)
        except WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(
                title=title,
                rows=500,
                cols=max(20, len(columns)),
            )
            worksheet.update("A1", [columns], value_input_option="USER_ENTERED")
            self._headers_cache[title] = columns

        self._worksheet_cache[title] = worksheet
        return worksheet

    def ensure_headers(self, title: str, worksheet: gspread.Worksheet, columns: list[str]) -> list[str]:
        """Ensure the worksheet has the required headers using only row 1."""
        if title in self._headers_cache:
            return self._headers_cache[title]

        headers = worksheet.row_values(1)

        if not headers:
            worksheet.update("A1", [columns], value_input_option="USER_ENTERED")
            headers = columns

        missing = [column for column in columns if column not in headers]

        if missing:
            headers = headers + missing
            worksheet.update("A1", [headers], value_input_option="USER_ENTERED")

        self._headers_cache[title] = headers
        return headers

    def ensure_worksheet(self, title: str, columns: list[str]) -> gspread.Worksheet:
        """Create a worksheet and header row when it does not exist."""
        worksheet = self.get_worksheet(title, columns)
        self.ensure_headers(title, worksheet, columns)
        return worksheet

    def read_dataframe(self, title: str, columns: list[str]) -> pd.DataFrame:
        """Return worksheet data as a DataFrame with the expected columns."""
        worksheet = self.get_worksheet(title, columns)
        headers = self.ensure_headers(title, worksheet, columns)

        # This is the only full-sheet read in this method.
        values = worksheet.get_all_values()

        if len(values) <= 1:
            return pd.DataFrame(columns=headers)

        rows = values[1:]
        df = pd.DataFrame(rows, columns=headers)

        for column in columns:
            if column not in df.columns:
                df[column] = ""

        return df

    def append_record(self, title: str, record: dict[str, Any], columns: list[str]) -> None:
        """Append a dictionary as a new row."""
        worksheet = self.get_worksheet(title, columns)
        headers = self.ensure_headers(title, worksheet, columns)

        row = [serialize_cell(record.get(column, "")) for column in headers]
        worksheet.append_row(row, value_input_option="USER_ENTERED")

    def upsert_record(
        self,
        title: str,
        record: dict[str, Any],
        columns: list[str],
        key_columns: list[str],
    ) -> None:
        """Update a row matching key columns, or append it if missing."""
        worksheet = self.get_worksheet(title, columns)
        headers = self.ensure_headers(title, worksheet, columns)

        values = worksheet.get_all_values()

        for row_number, row_values in enumerate(values[1:], start=2):
            row = {
                header: row_values[index] if index < len(row_values) else ""
                for index, header in enumerate(headers)
            }

            if all(str(row.get(key, "")) == str(record.get(key, "")) for key in key_columns):
                merged = {**row, **record}
                output = [serialize_cell(merged.get(column, "")) for column in headers]

                start = rowcol_to_a1(row_number, 1)
                end = rowcol_to_a1(row_number, len(headers))

                worksheet.update(
                    f"{start}:{end}",
                    [output],
                    value_input_option="USER_ENTERED",
                )
                return

        self.append_record(title, record, columns)

    def replace_records(self, title: str, records: list[dict[str, Any]], columns: list[str]) -> None:
        """Replace all worksheet data while preserving the schema."""
        worksheet = self.get_worksheet(title, columns)

        rows = [columns]
        rows.extend(
            [
                [serialize_cell(record.get(column, "")) for column in columns]
                for record in records
            ]
        )

        worksheet.clear()
        worksheet.update("A1", rows, value_input_option="USER_ENTERED")

        self._headers_cache[title] = columns