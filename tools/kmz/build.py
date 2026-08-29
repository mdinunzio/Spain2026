"""Build KMZ file(s) for Google My Maps from the Locations tab.

Always reads the live Locations tab (the single source of truth). Single layer
by default; pass --split-by to emit one KMZ per region/type/selected, so each
imports as its own toggleable My Maps layer. Pass --filter to build a curated
single-purpose export (selected picks, lunch spots, cafes, bars) instead of
everything.

Usage:
    python -m tools.kmz.build
    python -m tools.kmz.build --split-by region
    python -m tools.kmz.build --filter selected --upload
    python -m tools.kmz.build --filter lunch --upload
    python -m tools.kmz.build --filter cafes --upload
    python -m tools.kmz.build --filter bars --upload
"""

import re
import sys
from pathlib import Path

import click

from tools.kmz.emoji import render_icons
from tools.kmz.exceptions import KmzError
from tools.kmz.kml import build_kml
from tools.kmz.models import Venue
from tools.kmz.package import write_kmz
from tools.kmz.sources import load_from_sheet
from tools.kmz.upload import upload_kmz

DEFAULT_OUT = Path("parsed/kmz")
DEFAULT_CACHE = Path(".twemoji-cache")
MY_MAPS_LAYER_LIMIT = 10

# Curated single-purpose exports, layered on top of --split-by. Each maps to
# one predicate over the full venue list and one output filename/doc label.
#
# A venue's Type is exclusive (one row, one category), but its Tags are not —
# a Dinner Restaurant tagged "lunch" genuinely works as a lunch spot, and a
# hotel restaurant tagged "cocktails" genuinely works as a drinks stop. So
# these filters match on Type *or* a tag-substring check, letting one venue
# land in more than one export instead of being locked to its Type.
#
# Substrings (not exact tags) so every phrasing variant is caught in one shot
# — "lunch", "quick-lunch", "lunch-deal", "no-tuesday-lunch", a future
# "casual-lunch", etc. all match on the root "lunch" without listing each one.
# Each substring here was checked against the live tag vocabulary for false
# positives (e.g. "wine" matches only wine-* tags, nothing unrelated).
LUNCH_TAG_SUBSTRINGS = ("lunch",)
CAFE_TAG_SUBSTRINGS = (
    "cafe", "coffee", "brunch", "breakfast", "baker", "roast", "pastr",
    "matcha", "churro", "ensaimada", "llonguet", "flat-white", "bagel",
)
BAR_TAG_SUBSTRINGS = (
    "cocktail", "wine", "vermout", "vermut", "cava", "mixolog", "speakeasy",
    "nightcap", "aperitif", "mezcal", "agave", "drink", "beach-bar",
)


def has_tag_substring(venue: Venue, substrings: tuple[str, ...]) -> bool:
    """Whether any of a venue's comma-separated tags contains any substring."""
    tags = (t.strip().lower() for t in (venue.tags or "").split(","))
    return any(sub in tag for tag in tags if tag for sub in substrings)


def _is_bar(venue: Venue) -> bool:
    # "wine" (the substring) legitimately matches wine-bar/wine-list/wine-geek/
    # catalan-wine/etc., but every Winery-type venue also carries a bare
    # "wine" tag — a winery tour is a scheduled tasting, not a quick-drink
    # stop, so exclude that Type outright regardless of which tag matched.
    if venue.venue_type == "Winery":
        return False
    return venue.venue_type in {"Bar", "Cocktail Bar", "Wine Bar"} or has_tag_substring(
        venue, BAR_TAG_SUBSTRINGS
    )


FILTER_PREDICATES = {
    "all": lambda v: True,
    "selected": lambda v: v.selected,
    "lunch": lambda v: v.venue_type == "Lunch Restaurant" or has_tag_substring(v, LUNCH_TAG_SUBSTRINGS),
    "cafes": lambda v: v.venue_type == "Cafe" or has_tag_substring(v, CAFE_TAG_SUBSTRINGS),
    "bars": _is_bar,
}
FILTER_LABELS = {
    "all": "Spain 2026",
    "selected": "Spain 2026 · Selected",
    "lunch": "Spain 2026 · Lunch Spots",
    "cafes": "Spain 2026 · Cafés",
    "bars": "Spain 2026 · Bars & Drinks",
}


def slugify_filename(text: str) -> str:
    """Make a filesystem-safe slug for an output filename."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "venues"


def group_venues(
    venues: list[Venue], split_by: str, none_label: str = "Spain 2026"
) -> dict[str, list[Venue]]:
    """Partition venues into named groups per the split dimension.

    Args:
        venues: Venues to group.
        split_by: One of "none", "region", "type", "selected".
        none_label: Group/document label to use when split_by is "none".

    Returns:
        Ordered mapping of group label -> venues. A single group under
        none_label when split_by is "none". For "selected", the committed
        venues come first as "Selected", the rest as "Candidates".
    """
    if split_by == "none":
        return {none_label: venues}

    if split_by == "selected":
        groups: dict[str, list[Venue]] = {}
        for venue in venues:
            label = "Selected" if venue.selected else "Candidates"
            groups.setdefault(label, []).append(venue)
        return {k: groups[k] for k in ("Selected", "Candidates") if k in groups}

    key = "region" if split_by == "region" else "venue_type"
    groups = {}
    for venue in venues:
        label = getattr(venue, key) or "Uncategorized"
        groups.setdefault(label, []).append(venue)
    return dict(sorted(groups.items()))


def order_for_output(venues: list[Venue]) -> list[Venue]:
    """Sort venues highest-rating first, then by name."""
    return sorted(venues, key=lambda v: (-(v.rating or 0), v.name.lower()))


@click.command()
@click.option(
    "--filter",
    "venue_filter",
    type=click.Choice(list(FILTER_PREDICATES)),
    default="all",
    help="Restrict to one curated subset before building. Default: everything.",
)
@click.option(
    "--split-by",
    type=click.Choice(["none", "region", "type", "selected"]),
    default="none",
    help="Emit one KMZ per group. Default: a single combined layer.",
)
@click.option(
    "--out",
    type=click.Path(path_type=Path),
    default=DEFAULT_OUT,
    help="Output directory for the .kmz file(s).",
)
@click.option(
    "--cache-dir",
    type=click.Path(path_type=Path),
    default=DEFAULT_CACHE,
    help="Where to cache downloaded emoji PNGs.",
)
@click.option(
    "--upload",
    is_flag=True,
    help="Upload the built KMZ(s) to the Spain 2026 Drive kmz folder.",
)
@click.option("--profile", default=None, help="mgdio Google profile.")
def main(
    venue_filter: str,
    split_by: str,
    out: Path,
    cache_dir: Path,
    upload: bool,
    profile: str | None,
) -> None:
    """Generate KMZ file(s) for Google My Maps from the Locations tab."""
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")

    try:
        venues = load_from_sheet(profile)
    except KmzError as error:
        raise click.ClickException(str(error)) from error

    venues = [v for v in venues if FILTER_PREDICATES[venue_filter](v)]
    if not venues:
        raise click.ClickException(f"No venues match --filter={venue_filter}.")

    click.echo(
        f"Loaded {len(venues)} venues from the Locations tab (filter={venue_filter})."
    )
    groups = group_venues(venues, split_by, FILTER_LABELS[venue_filter])
    click.echo(f"Split by {split_by}: {len(groups)} file(s).")
    if len(groups) > MY_MAPS_LAYER_LIMIT:
        click.echo(
            f"Warning: {len(groups)} groups exceeds the My Maps {MY_MAPS_LAYER_LIMIT}-"
            "layer limit; some layers won't import. Consider --split-by region.",
            err=True,
        )

    try:
        written = []
        for label, members in groups.items():
            ordered = order_for_output(members)
            icons = render_icons({v.emoji for v in ordered if v.emoji}, cache_dir)
            kml = build_kml(ordered, label)
            filter_suffix = "" if venue_filter == "all" else f"_{venue_filter}"
            split_suffix = "" if split_by == "none" else f"_{slugify_filename(label)}"
            kmz_path = out / f"spain2026{filter_suffix}{split_suffix}.kmz"
            write_kmz(kmz_path, kml, icons)
            written.append((kmz_path, len(ordered), len(icons)))
    except KmzError as error:
        raise click.ClickException(str(error)) from error

    click.echo("")
    for path, venue_count, icon_count in written:
        click.echo(f"  {path}  ({venue_count} pins, {icon_count} icons)")
    click.echo(f"\nWrote {len(written)} KMZ file(s) to {out}/")
    if len(written) > 1:
        click.echo(
            "Import each file into My Maps as its own layer (Add layer → Import)."
        )

    if upload:
        click.echo("\nUploading to Google Drive…")
        try:
            for path, _, _ in written:
                name, link, replaced = upload_kmz(path, profile=profile)
                verb = "Updated" if replaced else "Uploaded"
                click.echo(f"  {verb} {name}  {link}")
        except Exception as error:  # mgdio/Drive errors are not KmzError
            raise click.ClickException(f"Drive upload failed: {error}") from error


if __name__ == "__main__":
    main()
