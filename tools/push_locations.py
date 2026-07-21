"""Push formatted venue batches to the Locations tab of the Spain 2026 sheet.

Reads every batch in parsed/formatted, merges venues that appear in more than
one batch, and either appends new rows or updates rows already present in the
tab (matched on Name). Always run with --dry-run first: it prints exactly what
would change without touching the sheet.

Usage:
    python tools/push_locations.py --dry-run
    python tools/push_locations.py --apply
"""

import sys
from pathlib import Path

import click

from mgdio.sheets import fetch_values, write_values

sys.path.insert(0, str(Path(__file__).parent))
from build_references import load_batches, merge_locations  # noqa: E402

SPREADSHEET_ID = "1L7ZT-ahqt6GCgEozHlVzfL4Ld_pmhqg-c_8bh3iRaeQ"
TAB = "Locations"
REPO_BLOB = "https://github.com/mdinunzio/Spain2026/blob/main/REFERENCES.md"

COLUMNS = [
    "Name",
    "Region",
    "Neighborhood",
    "Type",
    "Emoji",
    "Description",
    "Cost Range",
    "Address",
    "Latitude",
    "Longitude",
    "Google Map",
    "References",
    "Rating",
    "Tags",
]


def get_map_formula(row_number: int) -> str:
    """Live HYPERLINK formula keyed off the row's own Name/Region cells."""
    return (
        '=HYPERLINK("https://www.google.com/maps/search/"'
        f'&ENCODEURL($A{row_number}&", "&$B{row_number}&", Spain"),"Map")'
    )


def get_references_formula(row: dict) -> str:
    """HYPERLINK into this venue's REFERENCES.md section on GitHub."""
    anchor = row["references_anchor"].split("#", 1)[-1]
    count = len(row["references"])
    label = f"{count} source{'s' if count != 1 else ''}"
    return f'=HYPERLINK("{REPO_BLOB}#{anchor}","{label}")'


def build_row(row: dict, row_number: int) -> list:
    """Shape one merged venue into a Locations row (columns A..N)."""
    description = row["description"]
    if row.get("geo_note"):
        description += f" [Approximate map pin: {row['geo_note']}.]"
    return [
        row["name"],
        row["region"],
        row["neighborhood"],
        row["type"],
        row["emoji"],
        description,
        row["cost_range"],
        row["address"] or "",
        row["latitude"],
        row["longitude"],
        get_map_formula(row_number),
        get_references_formula(row),
        row["rating"],
        row["tags"],
    ]


def fetch_existing_names(values: list[list]) -> dict[str, int]:
    """Map existing venue Name -> its 1-based sheet row number."""
    if not values:
        return {}
    return {
        r[0].strip(): i
        for i, r in enumerate(values[1:], start=2)
        if r and r[0].strip()
    }


@click.command()
@click.option(
    "--formatted-dir",
    default="parsed/formatted",
    type=click.Path(exists=True, path_type=Path),
)
@click.option("--dry-run", "dry_run", is_flag=True, help="Preview without writing.")
@click.option("--apply", "apply", is_flag=True, help="Actually write to the sheet.")
def main(formatted_dir: Path, dry_run: bool, apply: bool) -> None:
    """Merge formatted batches into the Locations tab."""
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")

    if dry_run == apply:
        raise click.UsageError("Pass exactly one of --dry-run or --apply.")

    locations, batches = load_batches(formatted_dir)
    merged = merge_locations(locations)
    ordered = sorted(merged.values(), key=lambda r: (-r["rating"], r["name"].lower()))

    existing_values = fetch_values(SPREADSHEET_ID, TAB)
    existing = fetch_existing_names(existing_values)
    click.echo(f"Batches: {', '.join(batches)}")
    click.echo(f"Venues to push: {len(ordered)}")
    click.echo(f"Rows already in tab: {len(existing)}")

    appends = [r for r in ordered if r["name"].strip() not in existing]
    updates = [r for r in ordered if r["name"].strip() in existing]
    click.echo(f"  new rows to append: {len(appends)}")
    click.echo(f"  existing rows to update in place: {len(updates)}")

    if dry_run:
        click.echo("\n--- header ---")
        click.echo(" | ".join(COLUMNS))
        click.echo("\n--- first 3 rows as they would be written ---")
        for offset, row in enumerate(ordered[:3]):
            built = build_row(row, offset + 2)
            for col, val in zip(COLUMNS, built):
                shown = str(val)
                if len(shown) > 110:
                    shown = shown[:110] + "…"
                click.echo(f"  {col:<12} {shown}")
            click.echo("")
        click.echo("Dry run only — nothing written.")
        return

    if existing:
        # In-place update: rewrite each matched row at its current position
        # (grouped into contiguous runs to keep the write count low), append
        # new venues below the table, and leave unmatched rows untouched.
        updates_by_row = sorted((existing[r["name"].strip()], r) for r in updates)
        runs: list[list[tuple[int, dict]]] = []
        for row_number, row in updates_by_row:
            if runs and row_number == runs[-1][-1][0] + 1:
                runs[-1].append((row_number, row))
            else:
                runs.append([(row_number, row)])

        total_cells = 0
        for run in runs:
            start, end = run[0][0], run[-1][0]
            payload = [build_row(row, row_number) for row_number, row in run]
            total_cells += write_values(SPREADSHEET_ID, f"{TAB}!A{start}:N{end}", payload)
        click.echo(
            f"Updated {len(updates)} rows in place ({len(runs)} contiguous writes)"
        )

        if appends:
            first_new = len(existing_values) + 1
            payload = [
                build_row(row, first_new + i) for i, row in enumerate(appends)
            ]
            end_row = first_new + len(payload) - 1
            total_cells += write_values(
                SPREADSHEET_ID, f"{TAB}!A{first_new}:N{end_row}", payload
            )
            click.echo(
                f"Appended {len(appends)} new rows at {TAB}!A{first_new}:N{end_row}"
            )
        click.echo(f"Wrote {total_cells} cells total.")
        return

    payload = [COLUMNS]
    payload.extend(build_row(row, i + 2) for i, row in enumerate(ordered))
    end_row = len(payload)
    cells = write_values(SPREADSHEET_ID, f"{TAB}!A1:N{end_row}", payload)
    click.echo(f"Wrote {cells} cells ({len(payload) - 1} venues) to {TAB}!A1:N{end_row}")


if __name__ == "__main__":
    main()
