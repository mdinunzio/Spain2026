"""Generate KML for Google My Maps from normalized venues.

Emits a single flat <Document> of placemarks (the shape My Maps imports most
reliably). Each placemark carries an inline <Style> pointing at a relative
icon href inside the KMZ, which is how My Maps adopts a custom pin.
"""

from xml.sax.saxutils import escape

from tools.kmz.descriptions import build_description_html
from tools.kmz.emoji import get_icon_filename
from tools.kmz.models import Venue

ICON_DIR = "icons"
# My Maps / Earth recognize this hosted asset when no custom icon applies.
DEFAULT_ICON = "http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png"


def format_coordinate(value: float) -> str:
    """Format a lat/long value without scientific notation or trailing zeros."""
    return f"{value:.7f}".rstrip("0").rstrip(".")


def build_placemark(venue: Venue) -> str:
    """Render one venue as a KML <Placemark>.

    Args:
        venue: The venue to render. Must have valid coordinates.

    Returns:
        A KML <Placemark> element as a string.
    """
    name = escape(venue.name)
    description = build_description_html(venue)
    icon_href = f"{ICON_DIR}/{get_icon_filename(venue.emoji)}" if venue.emoji else ""
    href = escape(icon_href or DEFAULT_ICON)
    # KML coordinates are longitude,latitude,altitude — longitude first.
    lon = format_coordinate(venue.longitude)
    lat = format_coordinate(venue.latitude)

    return f"""    <Placemark>
      <name>{name}</name>
      <description><![CDATA[{description}]]></description>
      <Style>
        <IconStyle>
          <Icon>
            <href>{href}</href>
          </Icon>
        </IconStyle>
      </Style>
      <Point>
        <coordinates>{lon},{lat},0</coordinates>
      </Point>
    </Placemark>"""


def build_kml(venues: list[Venue], document_name: str) -> str:
    """Build a full KML document for a set of venues.

    Args:
        venues: Venues to include as placemarks, in output order.
        document_name: Name of the <Document> (the My Maps layer name).

    Returns:
        The complete KML document as a string.
    """
    placemarks = "\n".join(build_placemark(venue) for venue in venues)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{escape(document_name)}</name>
{placemarks}
  </Document>
</kml>
"""
