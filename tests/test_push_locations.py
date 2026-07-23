"""Tests for the human-annotation logic in push_locations.

Covers the pure functions that decide how the Selected/Notes columns are read
from the sheet, reconciled with the durable backup file, and written back.
No network or Google Sheets access.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
from push_locations import (  # noqa: E402
    annotation_cells,
    read_sheet_annotations,
    reconcile_annotations,
)

HEADER = ["Name", "Region", "Rating", "Tags"] + [""] * 12  # A..P placeholder


def sheet_row(name: str, selected: str = "", notes: str = "") -> list:
    """Build a 16-wide sheet row with Selected in O (14) and Notes in P (15)."""
    row = [name] + [""] * 15
    row[14] = selected
    row[15] = notes
    return row


class TestReadSheetAnnotations:
    def test_captures_selected_and_notes(self):
        values = [
            HEADER,
            sheet_row("Perfect Charter", "TRUE", "book by June"),
            sheet_row("Nama", "FALSE", ""),
            sheet_row("Deià", "", "stay 2 nights"),
        ]
        ann = read_sheet_annotations(values)
        assert ann["Perfect Charter"] == {"selected": True, "notes": "book by June"}
        assert ann["Deià"] == {"selected": False, "notes": "stay 2 nights"}
        # Unchecked with no note is not recorded.
        assert "Nama" not in ann

    def test_true_is_case_insensitive(self):
        values = [HEADER, sheet_row("X", "true", "")]
        assert read_sheet_annotations(values)["X"]["selected"] is True

    def test_short_rows_do_not_crash(self):
        # A row that never had O/P cells written is shorter than 16.
        values = [HEADER, ["Lonely Venue"]]
        assert read_sheet_annotations(values) == {}


class TestReconcile:
    def test_new_selection_added(self):
        result = reconcile_annotations(
            {}, {"A": {"selected": True, "notes": ""}}, {"A"}
        )
        assert result == {"A": {"selected": True, "notes": ""}}

    def test_uncheck_in_sheet_clears_file_value(self):
        # File said A was selected; the sheet no longer reports it AND A is
        # present in the tab -> the uncheck wins, A is dropped.
        result = reconcile_annotations(
            {"A": {"selected": True, "notes": "old"}}, {}, {"A"}
        )
        assert "A" not in result

    def test_venue_absent_from_sheet_keeps_file_value(self):
        # A is not in the tab (removed/renamed) -> keep it for later restore.
        result = reconcile_annotations(
            {"A": {"selected": True, "notes": "keep"}}, {}, {"B"}
        )
        assert result["A"] == {"selected": True, "notes": "keep"}

    def test_sheet_overrides_file(self):
        result = reconcile_annotations(
            {"A": {"selected": True, "notes": "old"}},
            {"A": {"selected": True, "notes": "new"}},
            {"A"},
        )
        assert result["A"]["notes"] == "new"


class TestAnnotationCells:
    def test_selected_true(self):
        ann = {"A": {"selected": True, "notes": "hi"}}
        assert annotation_cells("A", ann) == ["TRUE", "hi"]

    def test_default_unselected(self):
        assert annotation_cells("Missing", {}) == ["FALSE", ""]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
