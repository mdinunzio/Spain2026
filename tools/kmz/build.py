"""Build KMZ file(s) for Google My Maps from the Locations tab.

Always reads the live Locations tab (the single source of truth). Single layer
by default; pass --split-by to emit one KMZ per region/type/selected, so each
imports as its own toggleable My Maps layer.

Usage:
    python -m tools.kmz.build
    python -m tools.kmz.build --split-by region
    python -m tools.kmz.build --split-by selected --upload
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


def slugify_filename(text: str) -> str:
    """Make a filesystem-safe slug for an output filename."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "venues"


def group_venues(venues: list[Venue], split_by: str) -> dict[str, list[Venue]]:
    """Partition venues into named groups per the split dimension.

    Args:
        venues: Venues to group.
        split_by: One of "none", "region", "type", "selected".

    Returns:
        Ordered mapping of group label -> venues. A single "Spain 2026" group
        when split_by is "none". For "selected", the committed venues come
        first as "Selected", the rest as "Candidates".
    """
    if split_by == "none":
        return {"Spain 2026": venues}

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

    click.echo(f"Loaded {len(venues)} venues from the Locations tab.")
    groups = group_venues(venues, split_by)
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
            suffix = "" if split_by == "none" else f"_{slugify_filename(label)}"
            kmz_path = out / f"spain2026{suffix}.kmz"
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
