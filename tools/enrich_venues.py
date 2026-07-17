"""Join curated venue extractions with Apify post metadata and geocode them.

Reads a curated venues JSON (venue content extracted from a source guide, each
venue tagged with the Instagram shortcodes it came from) plus the raw Apify
scraper dataset, then emits a Locations-tab-shaped JSON into parsed/formatted.

Usage:
    python tools/enrich_venues.py CURATED_JSON APIFY_JSON OUT_JSON [--region REGION]
"""

import json
import re
import sys
import unicodedata
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import click

from mgdio.maps import geocode

# Rough bounding box for Mallorca; geocodes outside it are almost certainly
# the geocoder falling back to a same-named place on the mainland.
MALLORCA_BOUNDS = (39.2, 40.1, 2.2, 3.6)  # lat_min, lat_max, lng_min, lng_max


@dataclass
class SourcePost:
    """Verified provenance for one Instagram post, from the Apify scrape."""

    shortcode: str
    url: str
    handle: str
    creator: str
    posted: str
    likes: int
    views: int


def load_source_posts(apify_path: Path) -> dict[str, SourcePost]:
    """Index the Apify dataset by shortcode."""
    records = json.loads(apify_path.read_text(encoding="utf-8"))
    return {
        r["shortCode"]: SourcePost(
            shortcode=r["shortCode"],
            url=r["url"],
            handle=r.get("ownerUsername", ""),
            creator=(r.get("ownerFullName") or "").strip(),
            posted=r.get("timestamp", "")[:10],
            likes=r.get("likesCount") or 0,
            views=r.get("videoPlayCount") or 0,
        )
        for r in records
    }


def slugify(name: str) -> str:
    """Build a REFERENCES.md anchor slug from a venue name."""
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def get_map_url(name: str, region: str) -> str:
    """Build a Google Maps search URL for a venue."""
    query = urllib.parse.quote_plus(f"{name}, {region}, Spain")
    return f"https://www.google.com/maps/search/{query}"


def is_in_bounds(lat: float, lng: float) -> bool:
    """Check whether a coordinate falls inside the expected region."""
    lat_min, lat_max, lng_min, lng_max = MALLORCA_BOUNDS
    return lat_min <= lat <= lat_max and lng_min <= lng <= lng_max


def fetch_coordinates(query: str) -> tuple[float | None, float | None, str | None]:
    """Geocode a query, returning (latitude, longitude, formatted_address)."""
    hits = geocode(query)
    if not hits:
        return None, None, None
    best = hits[0]
    return best.latitude, best.longitude, best.formatted_address


def build_location_row(
    venue: dict,
    posts: dict[str, SourcePost],
    region: str,
) -> dict:
    """Shape one curated venue into a Locations-tab row with provenance."""
    references = []
    for shortcode in venue["sources"]:
        post = posts.get(shortcode)
        if post is None:
            raise KeyError(f"{venue['name']}: shortcode {shortcode} not in Apify data")
        references.append(
            {
                "shortcode": post.shortcode,
                "url": post.url,
                "creator": post.creator,
                "handle": f"@{post.handle}",
                "posted": post.posted,
                "likes": post.likes,
                "views": post.views,
            }
        )

    lat, lng, resolved = fetch_coordinates(venue["geo"])
    flags = []
    if lat is None:
        flags.append("geocode-failed")
    elif not is_in_bounds(lat, lng):
        flags.append("geocode-out-of-bounds")
    if venue.get("geo_approx"):
        flags.append("location-approximate")

    return {
        "name": venue["name"],
        "region": region,
        "neighborhood": venue["neighborhood"],
        "type": venue["type"],
        "emoji": venue["emoji"],
        "description": venue["description"],
        "cost_range": venue["cost_range"],
        "address": venue["address_stated"] or resolved,
        "latitude": lat,
        "longitude": lng,
        "google_map": get_map_url(venue["name"], region),
        "references_anchor": f"REFERENCES.md#{slugify(venue['name'])}",
        "references": references,
        "rating": venue["rating"],
        "tags": ", ".join(sorted(venue["tags"])),
        "source_rating_raw": venue["manus_rating"],
        "geocode_query": venue["geo"],
        "geo_note": venue.get("geo_approx"),
        "flags": flags,
    }


def find_collisions(rows: list[dict]) -> list[tuple[tuple, list[str]]]:
    """Group rows that geocoded to an identical point.

    A shared coordinate is legitimate for co-located venues (a hotel and its
    restaurant), but for distinct venues it means the geocoder quietly fell
    back to a town or neighborhood centroid instead of resolving the venue.
    """
    seen: dict[tuple, list[str]] = {}
    for row in rows:
        if row["latitude"] is None:
            continue
        key = (round(row["latitude"], 4), round(row["longitude"], 4))
        seen.setdefault(key, []).append(row["name"])
    return [(k, v) for k, v in seen.items() if len(v) > 1]


@click.command()
@click.argument("curated_json", type=click.Path(exists=True, path_type=Path))
@click.argument("apify_json", type=click.Path(exists=True, path_type=Path))
@click.argument("out_json", type=click.Path(path_type=Path))
@click.option("--region", default="Mallorca", help="Region label for every row.")
def main(curated_json: Path, apify_json: Path, out_json: Path, region: str) -> None:
    """Merge curated venues with Apify provenance, geocode, and write OUT_JSON."""
    # Venue names carry accents and emoji; the default Windows console codec
    # (cp1252) cannot encode them and would crash the run mid-geocode.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")

    curated = json.loads(curated_json.read_text(encoding="utf-8"))
    posts = load_source_posts(apify_json)

    rows = []
    for venue in curated["venues"]:
        row = build_location_row(venue, posts, region)
        rows.append(row)
        marker = " ".join(row["flags"]) or "ok"
        click.echo(f"  {row['name'][:44]:<46} {marker}")

    out_json.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "batch": curated["batch"],
        "region": region,
        "source_count": len(posts),
        "venue_count": len(rows),
        "locations": rows,
    }
    out_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    click.echo(f"\nWrote {len(rows)} locations to {out_json}")

    flagged = [r for r in rows if r["flags"]]
    if flagged:
        click.echo(f"\n{len(flagged)} row(s) with approximate or failed coordinates:")
        for row in flagged:
            click.echo(f"  {row['name']}: {', '.join(row['flags'])}")

    collisions = find_collisions(rows)
    if collisions:
        click.echo("\nVenues sharing a coordinate (confirm each is co-located):")
        for point, names in collisions:
            click.echo(f"  {point}: {', '.join(names)}")

    if any("geocode-failed" in r["flags"] for r in rows):
        sys.exit(1)


if __name__ == "__main__":
    main()
