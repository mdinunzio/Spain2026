"""Native KMZ toolkit for Google My Maps.

Converts the Spain 2026 Locations data into KMZ files with emoji pin icons,
without depending on mapitquick.com. Emoji are rendered deterministically
from Twemoji PNGs so pins look identical on every machine.
"""

from tools.kmz.models import Venue

__all__ = ["Venue"]
