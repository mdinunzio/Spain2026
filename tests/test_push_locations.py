"""Tests for the annotation-export logic in push_locations.

The sheet is the single source of truth for Selected/Notes; push only reads
them (to dump the git audit export). Covers that read. No network access.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
from push_locations import read_sheet_annotations  # noqa: E402

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
