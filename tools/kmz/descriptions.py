"""Build the HTML description shown in a Google My Maps info popup.

My Maps renders a limited HTML subset inside a placemark description: <b>,
<br>, <i>, and <a href>. We escape all text content, then assemble labeled
lines plus clickable Google Maps and References links.
"""

from xml.sax.saxutils import escape, quoteattr

from tools.kmz.models import Venue


def escape_text(value: str) -> str:
    """XML-escape user text for safe inclusion in a description."""
    return escape(value, {'"': "&quot;"})


def build_link(url: str, label: str) -> str:
    """Build an anchor tag, escaping both the href and the label."""
    return f"<a href={quoteattr(url)}>{escape_text(label)}</a>"


def build_description_html(venue: Venue) -> str:
    """Assemble the info-popup HTML for a venue.

    Args:
        venue: The venue to describe.

    Returns:
        An HTML fragment using only My Maps-supported tags.
    """
    blocks: list[str] = []

    if venue.description:
        blocks.append(escape_text(venue.description))

    facts: list[str] = []
    if venue.rating is not None:
        facts.append(f"<b>Rating:</b> {venue.rating}/5")
    if venue.venue_type:
        facts.append(f"<b>Type:</b> {escape_text(venue.venue_type)}")
    if venue.neighborhood:
        facts.append(f"<b>Neighborhood:</b> {escape_text(venue.neighborhood)}")
    if venue.region:
        facts.append(f"<b>Region:</b> {escape_text(venue.region)}")
    if venue.cost_range:
        facts.append(f"<b>Cost:</b> {escape_text(venue.cost_range)}")
    if venue.address:
        facts.append(f"<b>Address:</b> {escape_text(venue.address)}")
    if facts:
        blocks.append("<br>".join(facts))

    if venue.geo_note:
        blocks.append(f"<b>⚠️ Approximate location:</b> {escape_text(venue.geo_note)}")

    links = []
    if venue.google_map_url:
        links.append(build_link(venue.google_map_url, "Open in Google Maps"))
    if venue.references_url:
        links.append(build_link(venue.references_url, "Sources & provenance"))
    if links:
        blocks.append("<br>".join(links))

    if venue.tags:
        blocks.append(f"<i>Tags: {escape_text(venue.tags)}</i>")

    return "<br><br>".join(blocks)
