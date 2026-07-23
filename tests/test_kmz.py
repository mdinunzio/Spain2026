"""Tests for the native KMZ toolkit.

These cover the pure logic (emoji filename derivation, description escaping,
KML shape, KMZ packaging, URL reconstruction) without hitting the network or
Google Sheets.
"""

import zipfile
from pathlib import Path
from xml.dom import minidom

import pytest

from tools.kmz.build import group_venues
from tools.kmz.descriptions import build_description_html, escape_text
from tools.kmz.emoji import get_icon_filename, get_twemoji_basename
from tools.kmz.kml import build_kml, format_coordinate
from tools.kmz.models import Venue
from tools.kmz.package import write_kmz
from tools.kmz.sources import build_google_map_url, build_references_url, slugify


def make_venue(**overrides) -> Venue:
    """Build a Venue with sensible defaults, overridable per test."""
    defaults = dict(
        name="Bens d'Avall",
        region="Mallorca",
        neighborhood="Sóller / Deià coast",
        venue_type="Dinner Restaurant",
        emoji="⭐",
        description="Cliffside fine dining.",
        cost_range="$$$$",
        address="Carretera de Deià, Sóller",
        latitude=39.7765719,
        longitude=2.6666189,
        google_map_url="https://maps.example/x",
        references_url="https://refs.example/x",
        rating=5,
        tags="cliffside, dinner",
    )
    defaults.update(overrides)
    return Venue(**defaults)


class TestTwemojiFilename:
    def test_single_codepoint(self):
        assert get_twemoji_basename("⭐") == "2b50"

    def test_variation_selector_stripped(self):
        # 🏖️ is U+1F3D6 U+FE0F; Twemoji drops the FE0F.
        assert get_twemoji_basename("🏖️") == "1f3d6"

    def test_zwj_sequence_preserved(self):
        # 👩‍🍳 is woman + ZWJ + cooking; all codepoints kept.
        assert get_twemoji_basename("👩‍🍳") == "1f469-200d-1f373"

    def test_keycap_keeps_fe0f(self):
        # Keycap sequences (…U+FE0F U+20E3) must retain the FE0F.
        assert get_twemoji_basename("1️⃣") == "31-fe0f-20e3"

    def test_icon_filename_extension(self):
        assert get_icon_filename("⭐") == "2b50.png"


class TestEscaping:
    def test_escapes_angle_and_amp(self):
        assert escape_text("a & b < c > d") == "a &amp; b &lt; c &gt; d"

    def test_escapes_double_quote(self):
        assert escape_text('say "hi"') == "say &quot;hi&quot;"

    def test_leaves_apostrophe_literal(self):
        # &apos; is not valid HTML4; My Maps renders it literally, so we must
        # NOT escape apostrophes.
        assert escape_text("Bens d'Avall") == "Bens d'Avall"


class TestDescription:
    def test_includes_core_fields(self):
        html = build_description_html(make_venue())
        assert "Cliffside fine dining." in html
        assert "<b>Rating:</b> 5/5" in html
        assert "<b>Cost:</b> $$$$" in html
        assert "<i>Tags: cliffside, dinner</i>" in html

    def test_links_rendered_as_anchors(self):
        html = build_description_html(
            make_venue(google_map_url="https://m/x", references_url="https://r/y")
        )
        assert '<a href="https://m/x">Open in Google Maps</a>' in html
        assert '<a href="https://r/y">Sources &amp; provenance</a>' in html

    def test_geo_note_surfaced(self):
        html = build_description_html(make_venue(geo_note="pinned at town centroid"))
        assert "Approximate location" in html
        assert "pinned at town centroid" in html

    def test_selected_marker(self):
        assert "Selected" in build_description_html(make_venue(selected=True))
        assert "Selected" not in build_description_html(make_venue(selected=False))

    def test_notes_rendered_and_escaped(self):
        html = build_description_html(make_venue(notes='book by June & <hold>'))
        assert "Our notes:" in html
        assert "book by June &amp; &lt;hold&gt;" in html


class TestGrouping:
    def test_split_none_single_group(self):
        groups = group_venues([make_venue()], "none")
        assert list(groups) == ["Spain 2026"]

    def test_split_selected_orders_selected_first(self):
        venues = [
            make_venue(name="Pick", selected=True),
            make_venue(name="Maybe", selected=False),
        ]
        groups = group_venues(venues, "selected")
        assert list(groups) == ["Selected", "Candidates"]
        assert [v.name for v in groups["Selected"]] == ["Pick"]

    def test_split_selected_omits_empty_group(self):
        groups = group_venues([make_venue(selected=False)], "selected")
        assert list(groups) == ["Candidates"]

    def test_split_by_region(self):
        venues = [
            make_venue(name="A", region="Mallorca"),
            make_venue(name="B", region="Costa Brava"),
        ]
        groups = group_venues(venues, "region")
        assert set(groups) == {"Mallorca", "Costa Brava"}

    def test_blank_fields_omitted(self):
        html = build_description_html(
            make_venue(rating=None, cost_range="", tags="", address="")
        )
        assert "Rating:" not in html
        assert "Cost:" not in html
        assert "Tags:" not in html


class TestKml:
    def test_coordinate_formatting(self):
        assert format_coordinate(39.7765719) == "39.7765719"
        assert format_coordinate(2.5) == "2.5"
        assert format_coordinate(-3.0) == "-3"

    def test_longitude_first(self):
        kml = build_kml([make_venue()], "Test")
        # KML requires longitude,latitude,altitude ordering.
        assert "<coordinates>2.6666189,39.7765719,0</coordinates>" in kml

    def test_well_formed_and_counts(self):
        kml = build_kml([make_venue(), make_venue(name="Second")], "Test Layer")
        dom = minidom.parseString(kml)
        assert len(dom.getElementsByTagName("Placemark")) == 2
        assert dom.getElementsByTagName("name")[0].firstChild.data == "Test Layer"

    def test_icon_href_is_relative(self):
        kml = build_kml([make_venue(emoji="⭐")], "Test")
        assert "<href>icons/2b50.png</href>" in kml

    def test_name_xml_escaped(self):
        kml = build_kml([make_venue(name="A & B <co>")], "Test")
        assert "<name>A &amp; B &lt;co&gt;</name>" in kml


class TestPackaging:
    def test_kmz_structure(self, tmp_path: Path):
        icons = {"⭐": ("2b50.png", b"\x89PNG\r\n\x1a\nfake")}
        kml = build_kml([make_venue()], "Test")
        out = write_kmz(tmp_path / "out.kmz", kml, icons)
        with zipfile.ZipFile(out) as archive:
            names = archive.namelist()
            assert "doc.kml" in names
            assert "icons/2b50.png" in names
            assert archive.read("doc.kml").decode("utf-8").startswith("<?xml")

    def test_no_duplicate_members(self, tmp_path: Path):
        icons = {
            "a": ("same.png", b"1"),
            "b": ("same.png", b"2"),
        }
        out = write_kmz(tmp_path / "out.kmz", "<kml/>", icons)
        with zipfile.ZipFile(out) as archive:
            assert archive.namelist().count("icons/same.png") == 1


class TestUrlReconstruction:
    def test_slugify_strips_accents_and_punct(self):
        assert slugify("Bens d'Avall") == "bens-d-avall"
        assert slugify("Café / Bar Miro (La Residencia)") == "cafe-bar-miro-la-residencia"

    def test_google_map_url(self):
        url = build_google_map_url("Bens d'Avall", "Mallorca")
        assert url == (
            "https://www.google.com/maps/search/"
            "Bens%20d%27Avall%2C%20Mallorca%2C%20Spain"
        )

    def test_references_url(self):
        url = build_references_url("Sea Club at Cap Rocat")
        assert url.endswith("REFERENCES.md#sea-club-at-cap-rocat")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
