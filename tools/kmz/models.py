"""Normalized venue model shared across the KMZ toolkit."""

from dataclasses import dataclass


@dataclass
class Venue:
    """One map location, normalized from the sheet or a formatted batch.

    Attributes:
        name: Display name, also the placemark title.
        region: Top-level region (e.g. "Mallorca"); the split-by-region key.
        neighborhood: Town or area within the region.
        venue_type: Category (e.g. "Beach", "Dinner Restaurant").
        emoji: A single emoji used to render the pin icon.
        description: Free-text blurb shown in the info popup.
        cost_range: Dollar-sign string ("$" .. "$$$$$") or "".
        address: Postal address, or "" if unknown.
        latitude: Decimal latitude.
        longitude: Decimal longitude.
        google_map_url: Link to a Google Maps search for the venue.
        references_url: Link to the venue's REFERENCES.md section.
        rating: 1-5 priority, or None if unrated.
        tags: Comma-separated tag string.
        geo_note: Set when the coordinate is an approximate placeholder.
        selected: True when we've committed to going (the Selected column).
        notes: Ad-hoc human notes (the Notes column).
    """

    name: str
    region: str
    neighborhood: str
    venue_type: str
    emoji: str
    description: str
    cost_range: str
    address: str
    latitude: float
    longitude: float
    google_map_url: str
    references_url: str
    rating: int | None
    tags: str
    geo_note: str | None = None
    selected: bool = False
    notes: str = ""
