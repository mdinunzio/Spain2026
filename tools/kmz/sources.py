"""Load normalized venues from the Locations tab or a formatted batch.

Two inputs are supported:

* ``sheet`` — the live Locations tab of the Spain 2026 spreadsheet. This is
  the source of truth the user edits, so it reflects manual tweaks. The tab
  stores Google Map / References as HYPERLINK formulas whose read-back value
  is just the display label, so those URLs are reconstructed deterministically
  from the venue name and region.
* ``json`` — the formatted batch files under ``parsed/formatted``, which carry
  the real URLs and an approximate-location note.
"""

import json
import re
import unicodedata
import urllib.parse
from pathlib import Path

from mgdio.sheets import fetch_values

from tools.kmz.exceptions import VenueDataError
from tools.kmz.models import Venue

SPREADSHEET_ID = "1L7ZT-ahqt6GCgEozHlVzfL4Ld_pmhqg-c_8bh3iRaeQ"
LOCATIONS_TAB = "Locations"
REPO_BLOB = "https://github.com/mdinunzio/Spain2026/blob/main/REFERENCES.md"
COUNTRY = "Spain"


def slugify(name: str) -> str:
    """Build the REFERENCES.md anchor slug for a venue name."""
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def build_google_map_url(name: str, region: str) -> str:
    """Reconstruct the Google Maps search URL used by the Locations tab."""
    query = urllib.parse.quote(f"{name}, {region}, {COUNTRY}", safe="")
    return f"https://www.google.com/maps/search/{query}"


def build_references_url(name: str) -> str:
    """Reconstruct the REFERENCES.md deep link for a venue."""
    return f"{REPO_BLOB}#{slugify(name)}"


def parse_rating(value: object) -> int | None:
    """Coerce a rating cell/field to an int, or None if blank/invalid."""
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def load_from_sheet(profile: str | None = None) -> list[Venue]:
    """Load venues from the live Locations tab.

    Args:
        profile: Optional mgdio Google profile slug.

    Returns:
        Venues parsed from the tab, skipping rows without coordinates.

    Raises:
        VenueDataError: If the tab is empty or missing required columns.
    """
    kwargs = {"profile": profile} if profile else {}
    rows = fetch_values(SPREADSHEET_ID, LOCATIONS_TAB, **kwargs)
    if not rows:
        raise VenueDataError("Locations tab is empty.")

    header = [h.strip().lower() for h in rows[0]]
    required = {"name", "latitude", "longitude", "emoji"}
    missing = required - set(header)
    if missing:
        raise VenueDataError(f"Locations tab missing columns: {sorted(missing)}")
    index = {col: i for i, col in enumerate(header)}

    def cell(row: list[str], col: str) -> str:
        pos = index.get(col)
        if pos is None or pos >= len(row):
            return ""
        return str(row[pos]).strip()

    def is_selected(row: list[str]) -> bool:
        return cell(row, "selected").upper() == "TRUE"

    venues: list[Venue] = []
    for row in rows[1:]:
        if not row or not cell(row, "name"):
            continue
        lat, lon = cell(row, "latitude"), cell(row, "longitude")
        if not lat or not lon:
            continue
        name, region = cell(row, "name"), cell(row, "region")
        venues.append(
            Venue(
                name=name,
                region=region,
                neighborhood=cell(row, "neighborhood"),
                venue_type=cell(row, "type"),
                emoji=cell(row, "emoji"),
                description=cell(row, "description"),
                cost_range=cell(row, "cost range"),
                address=cell(row, "address"),
                latitude=float(lat),
                longitude=float(lon),
                google_map_url=build_google_map_url(name, region),
                references_url=build_references_url(name),
                rating=parse_rating(cell(row, "rating")),
                tags=cell(row, "tags"),
                selected=is_selected(row),
                notes=cell(row, "notes"),
            )
        )
    if not venues:
        raise VenueDataError("Locations tab has no rows with coordinates.")
    return venues


def load_from_json(formatted_dir: Path) -> list[Venue]:
    """Load venues from every formatted batch JSON file.

    Selected/Notes are human-owned and live only in the sheet (the single
    source of truth), so an offline ``--source json`` build has neither: every
    venue is unselected with no notes. Use ``--source sheet`` for those.

    Args:
        formatted_dir: Directory of ``*.json`` batch files.

    Returns:
        Venues parsed from all batches, skipping rows without coordinates.

    Raises:
        VenueDataError: If no batch files or no usable rows are found.
    """
    batch_files = sorted(formatted_dir.glob("*.json"))
    if not batch_files:
        raise VenueDataError(f"No formatted batches in {formatted_dir}.")

    venues: list[Venue] = []
    for path in batch_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload["locations"]:
            if row.get("latitude") is None or row.get("longitude") is None:
                continue
            venues.append(
                Venue(
                    name=row["name"],
                    region=row.get("region", ""),
                    neighborhood=row.get("neighborhood", ""),
                    venue_type=row.get("type", ""),
                    emoji=row.get("emoji", ""),
                    description=row.get("description", ""),
                    cost_range=row.get("cost_range", ""),
                    address=row.get("address") or "",
                    latitude=float(row["latitude"]),
                    longitude=float(row["longitude"]),
                    google_map_url=row.get("google_map", ""),
                    references_url=f"{REPO_BLOB}#{slugify(row['name'])}",
                    rating=parse_rating(row.get("rating", "")),
                    tags=row.get("tags", ""),
                    geo_note=row.get("geo_note"),
                )
            )
    if not venues:
        raise VenueDataError("No venues with coordinates found in batches.")
    return venues
